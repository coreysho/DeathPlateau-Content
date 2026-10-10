#!/usr/bin/env python3
"""Put every back-slot model in the renderer's depth-sorted priority bucket.

THE PROBLEM. The client has no z-buffer. It paints faces in an order set by each face's priority:
twelve buckets, 0 to 9 drawn back to front in a fixed order, so a face at priority 5 is painted
over a face at priority 3 wherever the two overlap on screen, whatever their real depth
(Model.method382). A cape sits at priorities 4, 5 and 6; the Armadyl chestplate is at 3 and the
Bandos tassets at 0 to 3. So the cape paints over them, and you see a cape-coloured smear across
the armour. tools/wearrender.py reproduces it: the Max cape covers the entire torso and legs.

WHY A FIXED PRIORITY CANNOT WORK HERE. A cape has to be BEHIND the body when you look at the
player from the front and IN FRONT of it when you look from behind. No fixed bucket does both.
That is exactly what bucket 10 is for: faces in it carry their depth and are flushed by depth at
priorities 0, 3 and 5, against the mean depth of buckets 1+2, 3+4 and 6+8. Vanilla body models
already use it - the rune platebody keeps 34 of its faces there - and so do the three back-slot
items in this content that happen to be solid objects rather than sheets (the diving backpack, the
sack, the shoulder parrot).

The 2006 capes were narrow enough to get away with fixed priorities: they barely crossed the body's
silhouette. The imported ones are wider and the imported armour is a different shape, so they do.

MEASURED, over four camera angles, pixels where the client's paint order disagrees with true
depth, on a dressed body wearing an Armadyl chestplate and Bandos tassets:

    max cape             50522 -> 12897        runecraft cape       56358 -> 6732
    imbued zamorak cape  55981 -> 13317        construction cape(t) 55462 -> 5797
    zamorak cape (2006)  35018 -> 10706        strength cape        55639 -> 7058
    cape of legends      32279 ->  9418        ardougne cloak 4     47601 -> 8867

Nothing measured got worse. Ava's attractor is unchanged: it is a small device, not a sheet, and
never crosses the armour.

HOW. Where a model carries per-face priorities - the 255 sentinel in its header - every entry is
set to 10 and the file's layout is untouched, which is the smallest possible edit and reverses by
writing the old bytes back. Where it carries one priority for the whole model, that byte becomes
10. Nothing else in the file changes.

  python3 tools/capedepth.py                # report
  python3 tools/capedepth.py --apply
"""
import argparse, glob, os, sys

DEPTH_SORTED = 10
PER_FACE = 255


def back_slot_models(content):
    """Every .ob2 that a wearpos=back obj puts on the player."""
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
        if d.get('wearpos') != 'back':
            continue
        for key in ('manwear', 'manwear2', 'manwear3',
                    'womanwear', 'womanwear2', 'womanwear3'):
            v = d.get(key)
            if not v:
                continue
            mp = os.path.join(content, 'models', 'obj', v.split(',')[0] + '.ob2')
            if os.path.exists(mp):
                out.setdefault(mp, set()).add(name)
    return out


def retune(path, apply):
    """Returns (what, changed)."""
    b = bytearray(open(path, 'rb').read())
    o = len(b) - 18
    vcount = (b[o] << 8) | b[o + 1]
    fcount = (b[o + 2] << 8) | b[o + 3]
    pri = b[o + 6]
    if pri == DEPTH_SORTED:
        return 'already depth-sorted', False
    if pri == PER_FACE:
        start = vcount + fcount                  # vertex flags, then face types, then priorities
        section = b[start:start + fcount]
        if all(v == DEPTH_SORTED for v in section):
            return 'already depth-sorted', False
        was = sorted(set(section))
        b[start:start + fcount] = bytes([DEPTH_SORTED]) * fcount
        what = 'per-face ' + ','.join(str(v) for v in was) + ' -> 10'
    else:
        b[o + 6] = DEPTH_SORTED
        what = f'whole model {pri} -> 10'
    if apply:
        open(path, 'wb').write(bytes(b))
    return what, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    models = back_slot_models(a.content)
    changed = 0
    for path in sorted(models):
        what, did = retune(path, a.apply)
        if did:
            changed += 1
            print(f'  {os.path.basename(path):<48} {what}')
    print()
    print(f'{len(models)} back-slot models, {changed} retuned'
          + ('' if a.apply else '  (dry run - pass --apply)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
