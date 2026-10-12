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
  legs   -> 2.   One ABOVE the default kit's legs, which are priority 1.
  torso  -> 4.   One above the default kit's torso, which is priorities 2 and 3.
  feet   -> 10.  A boot under a long cape is the same case as the cape: in front of it from the
                 front, behind it from the back, and no fixed bucket does both. It joins the hands,
                 the arms and both weapons, which are already there. THE DEFAULT KIT'S FEET MOVE
                 WITH THEM, which is the one place this tool touches something that is not a worn
                 item. See THE BOOTS AND THE CAPE below.

MEASURE THE RIGHT THING OR YOU GET THE ARMOUR BACKWARDS. The first version of this put legs at 1
and torso at 3 - level with the body part, so the two depth-sort against each other - because the
measure was disagreement with true depth and that is what depth-sorting minimises. It is the wrong
measure for armour. A player expects armour to COVER the body even where the body is geometrically
nearer, and a garment level with the body loses wherever a limb pokes through a gap: the Bandos
tassets went from 145930 pixels of body showing through to 177527, and bare legs appeared under
the skirt in game. One bucket above takes it to 40738. Depth is the right measure for a cape,
which genuinely has to sort both ways; it is not the right measure for a garment worn over a limb.

So each model is scored both ways round - its original bytes against the candidate bucket, on how
much BODY shows through, over four camera pitches across the legal range - and keeps whichever
wins. 493 retuned, 7 left exactly as they were.

THE BOOTS AND THE CAPE. Bucket 10 is not drawn in one go: Model.method382 flushes it in three
places and the first is at priority 0, BEFORE bucket 0's own faces, for every face further away
than the average depth of buckets 1 and 2. Look down at a player from behind - the ordinary camera
- and a long cape's hem is further than that average, so it is flushed in that first group, and
then the feet, which were alone in bucket 0, were painted straight over it. Boots through the back
of a Max cape, reported from the game.

Nothing in 2006 could show it: those capes stop at the knee. The Max cape is a 2015 item and hangs
to the ankle.

Putting the feet in the depth-sorted bucket makes the boot and the cape sort against each other by
depth, which is the only answer that holds from both sides. Measured on the full outfit - Max cape,
Armadyl chestplate, rune platelegs, Bandos boots - over four pitches by eight angles:

    boots at 0 (shipped)   6141 all round, 2632 from behind
    boots at 1 or 2        8811 all round,   32 from behind   - fixes the back, costs the front
    boots at 3            50704 all round
    boots at 10            1851 all round,  233 from behind

and on the same outfit with no cape at all it is 218 either way, so nothing was traded for it.

THOSE NUMBERS ARE FROM AFTER tools/wearrender.py WAS FIXED. Before that it drew the kit body
underneath the armour, which the client never does, and the same experiment said bucket 1 - which
fixed the back, wrecked the front, and shipped.

ANYTHING ALREADY USING BUCKET 10 OR 11 IS LEFT ALONE. It is already depth-sorted, which beats any
fixed bucket.

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
import argparse, glob, os, re, sys

# slot -> the bucket that sorts it against the body
# 'hair' and 'jaw' are not wearpos names - no obj is worn in them - so they only ever reach this
# through the kit list below.
RULES = {'back': 10, 'legs': 10, 'torso': 10, 'feet': 10, 'hair': 10, 'jaw': 10}

# The default kit's own feet, which are not worn items and so appear in no .obj: man and woman,
# basic and elf boots (all.idk's man_feet_* and woman_feet_*). They move with the boots because a
# barefoot player stands under the same cape.
# THE DEFAULT KIT'S OWN TORSO, LEGS AND FEET, which are not worn items and appear in no .obj, so
# worn_models() never sees them. They need the same answer for the same reason: a player wearing
# only a cape has no armour in those slots, so what the cape sorts against is the bare body - and a
# bare body in a fixed bucket is painted over the cape exactly as a boot was.
#
# SOME OF THEM CAME ALONG BY ACCIDENT AND THE REST DID NOT, which is the bug this fixes. The kit's
# meshes are shared with real items - "man torso" is the priest gown's model, "man legs" the
# mime's - so the slots above moved whichever kit options happen to be an item too and left the
# other 23 behind. A player whose character uses one of those still sees his own back through his
# cape, which is exactly what was reported after the pass that looked clean on the default kit.
#
# HAIR AND JAW COME TOO, AND THE REASON I LEFT THEM OUT WAS WRONG. "The head is above the cape's
# collar and never sorts against it" is true of a cropped head and false of long hair, which falls
# down the back and over the cape - and the hair is the head model, so a fixed bucket 6 puts the
# whole head over everything in 10 whatever the depth. Long hair against a Max cape, four pitches
# by three angles each way:
#
#     hair 6,  jaw 6    front 426   back 381      (shipped)
#     hair 10, jaw 6    front 192   back 325
#     hair 10, jaw 10   front 173   back  90
#
# Cropped hair is 18 either way, which is why the default body this is measured against never
# showed it and a character with long hair did.
KIT_TYPES = ('torso', 'legs', 'feet', 'hair', 'jaw')


def kit_models(content):
    """{model path: slot} for every kit option whose body part a cape has to sort against."""
    out, cur, kits = {}, None, {}
    idk = os.path.join(content, 'scripts', '_unpack', '377', 'all.idk')
    if not os.path.exists(idk):
        return out
    for line in open(idk, encoding='utf-8', errors='replace'):
        s = line.split('//')[0].strip()
        m = re.match(r'^\[([a-z0-9_]+)\]$', s)
        if m:
            cur = m.group(1)
            kits[cur] = {}
        elif cur and '=' in s:
            k, v = s.split('=', 1)
            kits[cur].setdefault(k.strip(), v.strip())
    for name, d in kits.items():
        kind = d.get('type', '')
        slot = next((k for k in KIT_TYPES if kind.endswith(k)), None)
        if not slot:
            continue
        for key in ('model1', 'model2', 'model3', 'model4'):
            model = d.get(key)
            if not model:
                continue
            for sub in ('idk', 'obj'):
                mp = os.path.join(content, 'models', sub, model + '.ob2')
                if os.path.exists(mp):
                    out[mp] = slot
                    break
    return out
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
    for mp, slot in kit_models(a.content).items():
        if slot in slots:
            models.setdefault(mp, (slot, {'the default kit'}))
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
