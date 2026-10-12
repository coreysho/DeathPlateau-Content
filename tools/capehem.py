#!/usr/bin/env python3
"""Pin a long cape's HEM to a fixed bucket and leave the rest of it depth-sorted.

WHAT WAS REPORTED. Boots showing through the back of a Max cape, from the ordinary camera: behind
the player and looking down.

WHY IT HAPPENS, and it is not the cape's bucket. tools/wearpriority.py puts every cape in bucket
10 and that is right - a cape has to be behind you from the front and in front of you from behind,
and 10 is the only bucket that asks the depth. But bucket 10 is not drawn in one go. Model.method382
flushes it in three places, and THE FIRST IS AT PRIORITY 0, BEFORE bucket 0's own faces, for every
face further away than the average depth of buckets 1 and 2. Look down at a player from behind and
a long cape's hem is further than that average, so it goes out in that first group - and then the
feet, which are the only thing in bucket 0, are painted straight over it.

WHAT DOES NOT WORK, measured before this was written. Moving the feet up one bucket fixes that view
completely (boots through the max cape, four pitches by five angles: 21204 -> 4516) and wrecks the
front, because the feet are also IN the average that decides how much of the cape is flushed early.
With them in it the average drops, less of the cape goes out early, and what is left lands over the
legs - a red apron across the thighs. Over the whole legal camera range it is three times worse:
21853 -> 67663. The feet at bucket 0 are load-bearing and this tool leaves them there.

WHAT DOES WORK. Split the cape instead of moving the body. The lower half is the only part that has
to beat a boot, and it is also the part that never has to sort against a torso, so it can take a
fixed bucket: 1, which is above the feet (0) and below leg armour (2). The upper half stays at 10,
where it still sorts against the body both ways round. For the Max cape, over four pitches by four
angles with front and side included:

    all of it at 10 (shipped)   10170        hem below y -90    7135
    hem below the midpoint       3279        hem below y -120   9811

The optimum is the midpoint and it is sharp, which is why this measures every model rather than
applying the rule on sight: each candidate is scored against the model's own shipped bytes and the
shipped bytes are kept unless the split wins by a clear margin.

Scored with tools/wearrender.py, which paints the merged models in the client's priority order and
again z-buffered and counts the pixels where the two disagree. For a cape that count is the right
measure and the docstring there says why: there is no artistic intent to protect, a cape simply has
to sort by depth.

  python3 tools/capehem.py                     # report
  python3 tools/capehem.py --apply
  python3 tools/capehem.py --only max_cape     # one obj, with its numbers
"""
import argparse, importlib.util, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


wr = load('wearrender', os.path.join(HERE, 'wearrender.py'))
for cand in (r'C:\LostCityServer\tools\models', os.path.join(CONTENT, '..', 'tools', 'models')):
    if os.path.isdir(cand):
        sys.path.insert(0, cand)
        break
from osrs2ob2 import parse_ob2, encode, roundtrip        # noqa: E402

# Four pitches across the legal range (Client.orbitCameraPitch clamps to 128..383) and four yaws,
# so the front and the sides count as much as the back. A conclusion drawn from behind alone is
# exactly how the feet idea passed.
PITCHES = (128, 260, 330, 383)
YAWS = (0, 512, 1024, 1536)
SIZE = 96
ZOOM = 1500            # tools/wearrender.py's own default

# A cape whose hem stops at the waist cannot reach a boot, and nothing here would help it. -60 is
# well above the shortest thing this finds worth splitting and well below the backpacks and the
# shoulder parrot, which are not capes at all.
HEM_REACHES = -60

# The split has to EARN the change. A model within a few per cent either way is noise in a pixel
# count, and churning a hundred models for noise is how the last pass had to be undone.
MARGIN = 0.15


def wrong_pixels(parts):
    total = 0
    merged = wr.Merged(parts)
    for xan in PITCHES:
        for yan in YAWS:
            c = wr.draw(merged, SIZE, xan, yan, ZOOM, painter=True)
            t = wr.draw(merged, SIZE, xan, yan, ZOOM, painter=False)
            total += int((c != t).any(axis=2).sum())
    return total


def hem_priorities(m):
    """Faces below the model's own vertical midpoint -> 1, the rest -> 10.

    y grows DOWNWARD in these models, so the hem is the largest y and a face is judged by its
    lowest vertex: a face that straddles the line belongs with the half it hangs into."""
    lo, hi = min(m['vy']), max(m['vy'])
    mid = (lo + hi) // 2
    return [1 if max(m['vy'][m['fa'][i]], m['vy'][m['fb'][i]], m['vy'][m['fc'][i]]) > mid else 10
            for i in range(m['fcount'])], mid


def back_models(content):
    """{model path: {obj names}} for every back-slot worn model."""
    objs, cur = {}, None
    for root, _d, files in os.walk(os.path.join(content, 'scripts')):
        for f in files:
            if not f.endswith('.obj'):
                continue
            for line in open(os.path.join(root, f), encoding='utf-8', errors='replace'):
                s = line.split('//')[0].strip()
                m = re.match(r'^\[([a-z0-9_]+)\]$', s)
                if m:
                    cur = m.group(1)
                    objs[cur] = {}
                elif cur and '=' in s:
                    k, v = s.split('=', 1)
                    objs[cur].setdefault(k.strip(), v.strip())
    out = {}
    for name, d in objs.items():
        if d.get('wearpos') != 'back':
            continue
        for key in ('manwear', 'womanwear'):
            v = d.get(key)
            if not v:
                continue
            p = os.path.join(content, 'models', 'obj', v.split(',')[0] + '.ob2')
            if os.path.exists(p):
                out.setdefault(p, set()).add(name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default=CONTENT)
    ap.add_argument('--only', help='one obj name')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    body = wr.body_parts(a.content)
    models = back_models(a.content)
    tmp = os.path.join(tempfile.gettempdir(), 'capehem_candidate.ob2')
    kept = skipped = unchanged = 0
    for path, names in sorted(models.items()):
        if a.only and a.only not in names:
            continue
        raw = open(path, 'rb').read()
        m = parse_ob2(raw)
        if set(m['pri']) != {10}:
            skipped += 1
            continue
        if max(m['vy']) < HEM_REACHES:
            skipped += 1
            continue
        pri, mid = hem_priorities(m)
        if 1 not in pri or 10 not in pri:
            skipped += 1
            continue
        m['pri'] = pri
        b = encode(m)
        ok, why = roundtrip(b, m)
        if not ok:
            print(f'  {os.path.basename(path):<46} round trip failed: {why}')
            skipped += 1
            continue
        open(tmp, 'wb').write(b)

        shipped = wrong_pixels(body + [(wr.obr.Model(path),
                                        wr.face_priorities(path, m['fcount'], m['vcount']))])
        split = wrong_pixels(body + [(wr.obr.Model(tmp),
                                      wr.face_priorities(tmp, m['fcount'], m['vcount']))])
        win = shipped - split
        verdict = 'kept' if win > shipped * MARGIN else 'no'
        print(f'  {os.path.basename(path):<46} mid y={mid:>5}  shipped={shipped:>6}  '
              f'split={split:>6}  {verdict}')
        if verdict == 'kept':
            kept += 1
            if a.apply:
                open(path, 'wb').write(b)
        else:
            unchanged += 1
    print(f'\n  {kept} split, {unchanged} left as shipped, {skipped} not candidates')
    if not a.apply:
        print('  dry run - pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
