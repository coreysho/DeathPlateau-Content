#!/usr/bin/env python3
"""A cape face the artist put BELOW the body's bucket loses to the body. Give those faces depth.

WHAT IS WRONG. Every cape here carries the per-face priorities its artist gave it - the Max cape's
642 faces sit at 1, 4 and 5, the Attack cape's at 0, 5, 6 and 7. The body they are worn over does
not: this build's kit torso is at 2 and 3 and worn body armour at 3. So every cape face the artist
placed below 3 is painted over by the torso wherever the two overlap on screen, and those faces are
the collar and the shoulder - the top of the cape, which is exactly where it was reported from the
game as "all capes clipping around the same area".

WHY IT IS NOT A RENUMBERING. Those faces cannot take another FIXED bucket either. Raising the Max
cape's 1s to 4 was tried first and photographed: the back improved and the chest went red, because a
collar that beats the torso from behind also beats it from the front, where the cape is behind the
body and should lose. There is no fixed bucket that is above the torso from one side and below it
from the other.

Bucket 10 is the one that asks the depth, which is the only answer that holds from both sides. So
the faces below 3 move there and every other face keeps the value its artist chose - the Max cape's
4s and 5s are untouched, and only its 150 collar and shoulder faces move.

MEASURED IN THE CLIENT, NOT IN A RENDERER OF OUR OWN. tools/wearrender.py was wrong about this
question eight times running in October 2026; what decided this was
javaclient/tools/clienttests/run_wearshots.py, which dresses a real player on a real server and
photographs him with the client's own code, on a character with the long hair and black top the
fault was reported on.

  python3 tools/capecollar.py           # report
  python3 tools/capecollar.py --apply
"""
import argparse, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)
for cand in (r'C:\LostCityServer\tools\models', os.path.join(CONTENT, '..', 'tools', 'models')):
    if os.path.isdir(cand):
        sys.path.insert(0, cand)
        break
from osrs2ob2 import parse_ob2, encode, roundtrip        # noqa: E402

# The bucket the body occupies: the default kit's torso is 2 and 3, worn body armour is 3. A cape
# face below that is painted over by whichever of them the player is wearing.
BODY_BUCKET = 3
DEPTH_SORTED = 10


def back_models(content):
    """{model path: {obj names}} for every back-slot worn model."""
    objs, cur = {}, None
    for path in sorted(glob.glob(os.path.join(content, 'scripts/**/*.obj'), recursive=True)):
        for line in open(path, encoding='utf-8', errors='replace'):
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


def npc_models(content):
    """Every model an npc is built from - not ours to retune, whatever it does for a player.

    Human npcs are made out of the player kit, and moving a shared mesh for the player's sake broke
    the Undertaker the same hour it shipped. A cape is rarely one of these, but the check is cheap
    and the alternative is finding out from the game again.
    """
    out = set()
    for path in sorted(glob.glob(os.path.join(content, 'scripts/**/*.npc'), recursive=True)):
        for line in open(path, encoding='utf-8', errors='replace'):
            s = line.split('//')[0].strip()
            if '=' not in s:
                continue
            k, v = s.split('=', 1)
            if re.match(r'^(model|head)\d*$', k.strip()):
                out.add(v.strip().split(',')[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default=CONTENT)
    ap.add_argument('--only', help='one obj name')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    npcs = npc_models(a.content)
    moved = untouched = shared = 0
    for path, names in sorted(back_models(a.content).items()):
        if a.only and a.only not in names:
            continue
        if os.path.basename(path)[:-4] in npcs:
            shared += 1
            continue
        m = parse_ob2(open(path, 'rb').read())
        low = sum(1 for v in m['pri'] if v < BODY_BUCKET)
        if not low:
            untouched += 1
            continue
        was = sorted(set(m['pri']))
        m['pri'] = [DEPTH_SORTED if v < BODY_BUCKET else v for v in m['pri']]
        b = encode(m)
        ok, why = roundtrip(b, m)
        if not ok:
            print(f'  {os.path.basename(path):<46} round trip failed: {why}')
            continue
        moved += 1
        print(f'  {os.path.basename(path):<46} {was} -> {sorted(set(m["pri"]))}  ({low} of {m["fcount"]} faces)')
        if a.apply:
            open(path, 'wb').write(b)
    print(f'\n  {moved} capes retuned, {untouched} had nothing below bucket {BODY_BUCKET}, '
          f'{shared} left alone because an npc is made of them too')
    if not a.apply:
        print('  dry run - pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
