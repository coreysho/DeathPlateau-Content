#!/usr/bin/env python3
"""Generate the nine abyssal whip recolours, their kits and the lookup they are applied through.

    python3 tools/genwhipcolours.py [--check]

NINE COLOURS, FROM THREE PLACES. Two are Old School's own and are lifted exactly: the volcanic
whip's orange is its real recolNd (31169), read out of the OSRS cache with importosrs.py, and
frozen is an interpretation of its model's baked-in ice blue, because Old School made that one a
separate mesh rather than a recolour. Six are originals, chosen off a rendered contact sheet rather
than from hex arithmetic. The ninth is the Undertaker's own: black with bone links, the same black
and bone the Gravedigger slayer helmet wears, because the whole shelf is his.

THE SOURCE COLOURS ARE MEASURED, AND THERE ARE THREE OF THEM, NOT TWO. tools/models/ob2palette.py
on the two meshes says the whip is a coil of ALTERNATING segments - 108 faces of near-black and 68
of dark maroon - and, crucially, that the near-black is NOT the same value in both meshes:

    obj_abyssal_whip          hsl16 0   (recolNs 0)     + hsl16 528 (recolNs 6210)
    obj_abyssal_whip_manwear  hsl16 16  (recolNs 4228)  + hsl16 528 (recolNs 6210)

A kit written with two pairs would recolour the icon in the backpack and leave the whip in the
player's hand its original colour. A recolNs that matches no face on a mesh is simply ignored, so
listing all three is free and is what makes the worn whip match the inventory one.

THE RESULTS ARE UNTRADEABLE, and that is an economy decision rather than a convention. Death tokens
are earned by killing players in the Wilderness and cannot be traded; an abyssal whip can be. A
tradeable recoloured whip would let a player turn tokens into gp at whatever the colour fetched -
the same faucet the vote ticket's shop_will_not_buy param exists to stop. Revert hands back a plain
whip, which is tradeable again, so nothing is locked away: only the colour is bound to the player
who earned it.

EVERY COLOURED WHIP IS A COPY OF THE PLAIN RECORD, field for field, with only the name, the
examine, the recolours, tradeable and two params changed. The whip's record carries its attack
bonuses, its special attack, its four walk animations, its run, ready and turn animations and its
hit sound; a colour that retyped any of those by hand could silently be a worse weapon than the
whip it is a colour of.

CATEGORY IS NOT TOUCHED, which is why Revert is nine generated triggers and not one on a category.
weapon_whip is what drives the attack style, the animations and the special - and an obj has ONE
category, so a [category=whip_coloured] line would REPLACE it and quietly turn every coloured whip
into a weapon the combat code does not recognise. That is exactly the bug the graceful recolours
shipped with and tools/sim/graceful.ts caught; here it is designed out instead.
"""
import re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
PLAIN = os.path.join(HERE, '..', 'scripts', '_unpack', '377', 'all.obj')
OUT_OBJ = os.path.join(HERE, '..', 'scripts', 'areas', 'area_wilderness', 'configs', 'whip_colours.obj')
OUT_ENUM = os.path.join(HERE, '..', 'scripts', 'areas', 'area_wilderness', 'configs', 'whip_colours.enum')
OUT_REVERT = os.path.join(HERE, '..', 'scripts', 'areas', 'area_wilderness', 'scripts', 'whip_revert.rs2')

BASE = 'abyssal_whip'
# The three measured source colours - see the header. DARK_INV and DARK_WORN are the same segments
# on two meshes; SEG is the maroon links, identical in both.
SRC_DARK_INV, SRC_DARK_WORN, SRC_SEG = 0, 4228, 6210

# (key, label, dark rgb555 or None to leave the coil black, segment rgb555, token price)
# A colour that leaves the dark segments alone keeps the whip reading as an abyssal whip; the two
# that repaint both are the ones that deliberately do not.
COLOURS = [
    ('volcanic',  'Volcanic',  None,          (30, 14, 1),  500),  # OSRS's own recolNd, 31169
    ('frozen',    'Frozen',    (13, 19, 26),  (22, 28, 31), 500),  # OSRS's ice blue, as a recolour
    ('venom',     'Venom',     None,          (6, 26, 2),   500),
    ('gilded',    'Gilded',    None,          (30, 24, 6),  500),
    ('shadow',    'Shadow',    None,          (16, 4, 24),  500),
    ('bloodbark', 'Bloodbark', (8, 0, 0),     (26, 2, 2),   500),
    ('tempest',   'Tempest',   None,          (6, 20, 31),  500),
    ('bone',      'Bone',      (19, 18, 15),  (29, 28, 24), 500),
    # The house colour, and the dearest for it: black with bone links is what the Gravedigger slayer
    # helmet wears, and it is priced with that kit rather than with the other eight.
    ('gravedigger', 'Gravedigger', None,      (29, 28, 24), 800),
]


def rgb15(t):
    if t is None:
        return None
    for v in t:
        if not 0 <= v <= 31:
            raise SystemExit('rgb555 channel out of range: %r' % (t,))
    return (t[0] << 10) | (t[1] << 5) | t[2]


def plain_block():
    """The [abyssal_whip] record out of the unpacked 377 config, as text."""
    txt = open(PLAIN).read()
    m = re.search(r'^\[%s\]\n(.*?)(?=^\[|\Z)' % BASE, txt, re.S | re.M)
    if not m:
        raise SystemExit('%s is not in %s' % (BASE, PLAIN))
    return m.group(1)


def recoloured(body, dark, seg):
    """The plain record's body with its name, examine and any recolours replaced, and made
    untradeable. Nothing else is dropped: see the header on why a copy has to be complete."""
    keep = [l for l in body.split('\n')
            if not re.match(r'^(name|desc|recol\ds|recol\dd|tradeable)=', l)]
    body = '\n'.join(keep).rstrip('\n')
    pairs = []
    if dark is not None:
        pairs += ['recol%ds=%d' % (len(pairs) // 2 + 1, SRC_DARK_INV),
                  'recol%dd=%d' % (len(pairs) // 2 + 1, dark)]
        pairs += ['recol%ds=%d' % (len(pairs) // 2 + 1, SRC_DARK_WORN),
                  'recol%dd=%d' % (len(pairs) // 2 + 1, dark)]
    pairs += ['recol%ds=%d' % (len(pairs) // 2 + 1, SRC_SEG),
              'recol%dd=%d' % (len(pairs) // 2 + 1, seg)]
    return '\n'.join(pairs) + '\n' + body + '\ntradeable=no'


def main():
    check = '--check' in sys.argv
    plain = plain_block()

    obj = ['''// THE NINE ABYSSAL WHIP RECOLOURS AND THEIR KITS.
//
// GENERATED by tools/genwhipcolours.py - do not hand-edit, regenerate.
//
// Each whip is a field-for-field copy of [abyssal_whip] in scripts/_unpack/377/all.obj with its
// recolour pairs in front of it, because that record carries the whip's attack bonuses, its
// special, its five animations and its hit sound - a colour must not quietly be a worse weapon
// than the whip it is a colour of. See the generator's header for where the three source colours
// come from and why there are three rather than two.
''']
    enum_result, enum_kit, pack_names = [], [], []

    for cnum, (key, label, dark_rgb, seg_rgb, cost) in enumerate(COLOURS, start=1):
        dark, seg = rgb15(dark_rgb), rgb15(seg_rgb)
        nm = '%s_%s' % (BASE, key)
        obj.append('// ---------------------------------------------------------------- %s' % label)
        obj.append('[%s]' % nm)
        obj.append('name=%s abyssal whip' % label)
        obj.append('desc=A weapon from the abyss, in %s colours.' % label.lower())
        obj.append(recoloured(plain, dark, seg))
        # The way back out. The plain whip declares iop2=Wield and nothing else, so this adds an
        # option rather than replacing one - and without it a colour is a one-way door.
        obj.append('iop5=Revert')
        obj.append('param=whip_from,%s' % BASE)
        obj.append('param=whip_colour,%d' % cnum)
        obj.append('')
        enum_result.append('val=%d,%s' % (cnum, nm))
        pack_names.append(nm)

        kit = 'whip_kit_%s' % key
        obj.append('''// The kit. The whip's own inventory model in the colour it makes, so the shop window and the
// backpack both show what is being bought. Untradeable, which also means the Undertaker cannot buy
// it back - ~can_sell_obj refuses untradeables at every shop in this build.''')
        obj.append('[%s]' % kit)
        obj.append('name=%s whip kit' % label)
        obj.append('desc=Use it on an abyssal whip to recolour it. Revert takes it back off.')
        obj.append('model=obj_abyssal_whip')
        if dark is not None:
            obj.append('recol1s=%d\nrecol1d=%d\nrecol2s=%d\nrecol2d=%d\nrecol3s=%d\nrecol3d=%d'
                       % (SRC_DARK_INV, dark, SRC_DARK_WORN, dark, SRC_SEG, seg))
        else:
            obj.append('recol1s=%d\nrecol1d=%d' % (SRC_SEG, seg))
        obj.append('2dxof=-2\n2dyof=56\n2dzoom=840\n2dxan=280')
        # cost IS the token price: the Undertaker runs at 1000 per mille, so ~calc_shop_value's
        # scale($mult, 1000, $cost) hands back the number written here.
        obj.append('cost=%d' % cost)
        obj.append('members=yes')
        obj.append('tradeable=no')
        obj.append('category=whip_kit')
        obj.append('param=whip_colour,%d' % cnum)
        obj.append('')
        enum_kit.append('val=%d,%s' % (cnum, kit))
        pack_names.append(kit)

    enum = ['''// GENERATED by tools/genwhipcolours.py - do not hand-edit, regenerate.
//
// Two directions of the same pairing. The kit carries param=whip_colour and looks its result up in
// the first; a coloured whip carries the same number and looks its kit up in the second, so Revert
// hands back the kit that made it.

[whip_colour_result]
inputtype=int
outputtype=namedobj
// WITHOUT A DEFAULT A MISS RETURNS OBJ 0, which is a real item - so whip_colours.rs2's
// `if ($into = null)` guard, which it has, could never fire and a bad key would hand over whatever
// obj 0 happens to be. rs2check rule 17 is the one that catches this.
default=null''']
    enum += enum_result
    enum.append('')
    enum.append('[whip_colour_kit]')
    enum.append('inputtype=int')
    enum.append('outputtype=namedobj')
    enum.append('default=null')
    enum += enum_kit
    enum.append('')

    revert = ['''// Revert, one trigger per coloured whip.
//
// GENERATED by tools/genwhipcolours.py - do not hand-edit, regenerate.
//
// NINE TRIGGERS RATHER THAN ONE ON A CATEGORY, AND IT HAS TO BE. An obj has ONE category, and a
// coloured whip's is weapon_whip - inherited from the plain record, and what drives its attack
// style, its animations and its special attack. A category=whip_coloured line would REPLACE that
// (the packer writes code 94 per category= line and ObjType.decode assigns), silently turning
// every colour into a weapon the combat code does not recognise. The graceful recolours shipped
// with exactly that bug and tools/sim/graceful.ts caught it; here it is designed out, at the cost
// of nine generated lines.
''']
    for cnum, (key, label, _d, _s, _c) in enumerate(COLOURS, start=1):
        revert.append('[opheld5,%s_%s] @whip_revert;' % (BASE, key))
    revert.append('')

    files = {OUT_OBJ: '\n'.join(obj) + '\n',
             OUT_ENUM: '\n'.join(enum),
             OUT_REVERT: '\n'.join(revert)}
    changed = []
    for path, text in files.items():
        old = open(path).read() if os.path.exists(path) else None
        if old != text:
            changed.append(os.path.relpath(path, os.path.join(HERE, '..')))
            if not check:
                open(path, 'w').write(text)
    if check:
        print('genwhipcolours --check: would change ' + (', '.join(changed) if changed else 'nothing'))
        return 1 if changed else 0
    print('genwhipcolours: %d objs (%d whips + %d kits), %d files written'
          % (len(pack_names), len(COLOURS), len(COLOURS), len(changed)))
    for n in pack_names:
        print('  ' + n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
