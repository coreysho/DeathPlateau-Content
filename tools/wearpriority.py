#!/usr/bin/env python3
"""Put each worn model in the priority bucket that sorts it correctly against the player.

THE PROBLEM. The client has no z-buffer. Faces are painted in an order set by priority: twelve
buckets, 0 to 9 drawn back to front in a fixed order, so a face at 5 goes over a face at 3
wherever they overlap on screen whatever their real depth (Model.method382). Buckets 10 and 11 are
the exception - faces there keep their depth and are flushed by depth at priorities 0, 3 and 5.
Within any one bucket faces are drawn far to near, so a bucket is internally depth-sorted.

Two things follow, and both were being got wrong:

  * splitting a garment across several buckets forces part of it over another part regardless of
    the camera. A skirt's back panel paints over its front. That is a defect in every case, and
    tools/wearrender.py --scan found 281 worn models doing it.
  * which bucket a garment is in decides how it sorts against the BODY. The only bucket that
    depth-sorts a garment against a body part is the one that body part is already in.

SO THE RULES, one per slot, measured rather than assumed:

Only the primary manwear/womanwear model is touched; see WEAR_KEYS.

  back   -> 10.  A cape has to be behind you from the front and in front of you from behind, and
                 no fixed bucket does both. Bucket 10 is the one that asks the depth.
  legs   -> 1.   The default kit's legs are priority 1, and so are the vanilla platelegs.
  torso  -> 3.   The default kit's torso is priorities 2 and 3.

ANYTHING ALREADY USING BUCKET 10 OR 11 IS LEFT ALONE. It is already depth-sorted, which beats any
fixed bucket, and in the first torso sweep every single regression turned out to be one of those
being flattened. With them excluded the sweeps come out:

  legs    106 models   74 better at 1, 0 worse, 32 unchanged
  torso    76 models   71 better at 3, 3 worse, 2 unchanged   (worse by 6, 33 and 69 pixels)
  back    159 models  measured one at a time; see the cape commit

Pixel counts are from tools/wearrender.py: the worn models merged the way ClientPlayer does and
painted twice, once in the client's priority order and once z-buffered, over four camera angles on
a dressed body. Examples, shipped -> fixed:

  bandos tassets  20191 -> 1843     ankou top        3538 -> 278     max cape      50522 -> 12897
  verac's legs    29142 -> 2385     ahrim's body     1748 -> 329     zamorak cape  55981 -> 13317
  ankou leggings  37159 ->  545     iron chainbody   1358 -> 316     cape of leg.  32279 ->  9418

WHAT IS NOT TOUCHED. Torso models that use bucket 10 (the robes), anything in a slot not listed,
and any model whose faces already all sit in the right bucket. The womanwear models are changed
with their manwear twins - same garment, same rule - though the sweeps were run against the male
kit.

THE EDIT IS THE SMALLEST AVAILABLE. Where a model carries per-face priorities - the 255 sentinel
in its header - every entry is overwritten and the file's layout is untouched, so it reverses by
writing the old bytes back. Where it carries one priority for the whole model, that byte changes.

  python3 tools/wearpriority.py                # report
  python3 tools/wearpriority.py --apply
"""
import argparse, glob, os, sys

# slot -> the bucket that sorts it against the body
RULES = {'back': 10, 'legs': 1, 'torso': 3}
PER_FACE = 255
DEPTH_SORTED = (10, 11)

# ONLY THE PRIMARY MODEL. manwear2 and manwear3 are the second part of an item - a platebody's
# arms, a chestplate's shoulders - and they cover a body part with its own bucket (the kit's arms
# are at 10, not 3). Nothing here measured those, so nothing here touches them.
WEAR_KEYS = ('manwear', 'womanwear')


def worn_models(content):
    """{model path: (slot, {obj names})} for every model a worn obj puts on the player."""
    objs = {}
    for p in sorted(glob.glob(os.path.join(content, 'scripts/**/*.obj'), recursive=True)):
        cur = None
        for line in open(p, encoding='utf-8', errors='replace'):
            s = line.strip()
            if s.startswith('//'):
                continue
            if s.startswith('[') and s.endswith(']'):
                cur = s[1:-1]
                objs[cur] = {}
            elif cur and '=' in s:
                k, v = s.split('=', 1)
                objs[cur].setdefault(k, v)
    out = {}
    for name, d in objs.items():
        slot = d.get('wearpos')
        if slot not in RULES:
            continue
        for key in WEAR_KEYS:
            v = d.get(key)
            if not v:
                continue
            mp = os.path.join(content, 'models', 'obj', v.split(',')[0] + '.ob2')
            if not os.path.exists(mp):
                continue
            # A model worn in two different slots by two different objs is left out rather than
            # given one slot's answer: there is no single right bucket for it.
            got = out.setdefault(mp, [slot, set()])
            if got[0] != slot:
                got[0] = None
            got[1].add(name)
    return {p: (s, n) for p, (s, n) in out.items() if s}


def priorities(b):
    o = len(b) - 18
    vcount = (b[o] << 8) | b[o + 1]
    fcount = (b[o + 2] << 8) | b[o + 3]
    pri = b[o + 6]
    if pri != PER_FACE:
        return pri, None, fcount, {pri}
    start = vcount + fcount        # vertex flags, then face types, then priorities
    sec = b[start:start + fcount]
    return PER_FACE, start, fcount, set(sec)


def retune(path, want, apply):
    b = bytearray(open(path, 'rb').read())
    hdr, start, fcount, have = priorities(b)
    if have & set(DEPTH_SORTED) and want not in DEPTH_SORTED:
        return 'already depth-sorted, left alone', False
    if have == {want}:
        return None, False
    was = ','.join(str(v) for v in sorted(have))
    if hdr == PER_FACE:
        b[start:start + fcount] = bytes([want]) * fcount
    else:
        b[len(b) - 18 + 6] = want
    if apply:
        open(path, 'wb').write(bytes(b))
    return f'{was} -> {want}', True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content',
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--slot', action='append', choices=sorted(RULES), default=None)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    slots = a.slot or sorted(RULES)
    models = worn_models(a.content)
    counts = {}
    for path, (slot, names) in sorted(models.items()):
        if slot not in slots:
            continue
        what, did = retune(path, RULES[slot], a.apply)
        counts.setdefault(slot, [0, 0, 0])
        counts[slot][2] += 1
        if did:
            counts[slot][0] += 1
            print(f'  {slot:<6} {os.path.basename(path):<48} {what}')
        elif what:
            counts[slot][1] += 1
    print()
    for slot in slots:
        c = counts.get(slot, [0, 0, 0])
        print(f'  {slot:<6} {c[2]:>4} models   {c[0]:>4} retuned   '
              f'{c[1]:>4} already depth-sorted   {c[2]-c[0]-c[1]:>4} already right')
    if not a.apply:
        print('\n  dry run - pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
