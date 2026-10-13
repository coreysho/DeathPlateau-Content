#!/usr/bin/env python3
"""Generate the nine Graceful recolours, their kits and the lookup they are applied through.

    python3 tools/gengracefulcolours.py [--check]

WHY NINE, AND WHY THESE NAMES. Old School's graceful recolours are the five Great Kourend house
colours, and Great Kourend does not exist in this build - no map squares, no npcs, no favour. The
names had to be re-homed whatever happened, so they are re-homed to the thing that pays for them:
ONE COLOUR PER ROOFTOP COURSE. Marks of grace only drop on those nine courses, so the shelf and the
currency now describe each other.

WHY THE COLOURS ARE AUTHORED HERE RATHER THAN IMPORTED. Old School's house gracefuls cannot be
imported: all fourteen of them (ids 13579-13668, 21061, 21063) share one inventory model and ONE
WORN MODEL PAIR (manwear 31004 / womanwear 31011) and carry no recolour fields at all, as
objconfig474 decodes them - the same decoder importosrs.py uses and which reads recolours correctly
for everything else. There is nothing in the cache to copy. So these are recolour pairs written
against the real meshes, which is how [fountain_of_heroes] is built from [fountain] and how the
games necklace is built from the ruby necklace.

THE TWO SOURCE COLOURS ARE MEASURED, NOT GUESSED. tools/models/ob2palette.py dumps a .ob2's face
colours; all six graceful meshes share hsl16 8417 (recolNs 32656, the garment) and hsl16 8396
(recolNs 22160, the trim), and they are the two largest face groups on every piece. Recolouring
that pair changes a whole set consistently, which is why there are two and not five.

EVERY COLOURED PIECE IS A COPY OF THE PLAIN ONE, field for field, with only the name, the examine,
the recolours and two params changed. That is not tidiness - the ENTIRE graceful effect is the
plain record's own `weight=` line and its `param=energy_restore`, with no script anywhere
(skilling_outfits/scripts/outfit_effects.rs2 says so). A colour that retyped those by hand could
silently be worth less than the piece it is a colour of, which is the mistake genslayerhelm.py
writes out at length for the slayer helmets.

NOT ADDED TO outfits.enum, deliberately: that enum is what the skilling-outfit roll draws from, and
a colour should not be something agility xp hands you. You earn the plain set and colour it.
"""
import re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUTFITS = os.path.join(HERE, '..', 'scripts', 'skilling_outfits', 'configs', 'outfits.obj')
OUT_OBJ = os.path.join(HERE, '..', 'scripts', 'skilling_outfits', 'configs', 'graceful_colours.obj')
OUT_ENUM = os.path.join(HERE, '..', 'scripts', 'skilling_outfits', 'configs', 'graceful_colours.enum')
OUT_REVERT = os.path.join(HERE, '..', 'scripts', 'skilling_outfits', 'scripts', 'graceful_revert.rs2')

# The garment and the trim, as ob2palette.py reports them for all six meshes.
SRC_MAIN = 32656
SRC_TRIM = 22160

# The six pieces, in slot order. The slot number is what the kit looks up.
PIECES = ['hood', 'top', 'legs', 'boots', 'gloves', 'cape']

# One per rooftop course, in course order (Draynor first, Ardougne last), each a garment colour and
# a trim colour as RGB555 triples - 0-31 per channel, which is what a config's recolNd packs.
COLOURS = [
    ('draynor',     'Draynor',           (9, 11, 4),  (5, 7, 2)),   # murky village olive
    ('alkharid',    'Al Kharid',         (25, 20, 4), (17, 13, 2)),  # desert gold
    ('varrock',     'Varrock',           (17, 4, 4),  (7, 2, 2)),    # Varrock red over black
    ('canifis',     'Canifis',           (9, 7, 11),  (5, 4, 6)),    # Morytania violet-grey
    ('falador',     'Falador',           (27, 28, 29), (11, 15, 21)),  # white over Asgarnian blue
    ('seers',       "Seers' Village",    (5, 15, 14), (2, 8, 7)),    # Kandarin teal
    ('pollnivneach', 'Pollnivneach',     (24, 14, 7), (15, 8, 3)),   # burnt desert orange
    ('rellekka',    'Rellekka',          (15, 21, 25), (7, 11, 14)),  # Fremennik ice blue
    ('ardougne',    'Ardougne',          (13, 5, 17), (7, 2, 10)),   # Ardougne royal purple
]

KIT_COST = 50   # marks. Grace sells at the item's own cost (skill_agility/configs/grace.npc).


def rgb15(t):
    r, g, b = t
    for v in t:
        if not 0 <= v <= 31:
            raise SystemExit('rgb555 channel out of range: %r' % (t,))
    return (r << 10) | (g << 5) | b


def plain_blocks():
    """The six [graceful_*] records out of outfits.obj, as text."""
    txt = open(OUTFITS).read()
    out = {}
    for piece in PIECES:
        name = 'graceful_%s' % piece
        m = re.search(r'^\[%s\]\n(.*?)(?=^\[|\Z)' % name, txt, re.S | re.M)
        if not m:
            raise SystemExit('%s is not in outfits.obj' % name)
        out[piece] = m.group(1)
    return out


def recolour(body, main, trim):
    """The plain record's body with its name, examine and recolours replaced."""
    keep = []
    for line in body.split('\n'):
        if re.match(r'^(name|desc|recol\ds|recol\dd)=', line):
            continue
        # graceful_slot IS STRIPPED, and leaving it in was a real bug. It identifies a PLAIN piece
        # for a kit to work on; a copy that kept it was a coloured piece a second kit would happily
        # recolour again - and that silently destroyed the first kit, because applying one consumes
        # it and only Revert gives one back. A Falador kit on a Varrock cape turned it Falador and
        # ate 50 marks of Varrock dye with no message. tools/sim/graceful.ts caught it.
        #
        # Without it, ~graceful_recolour falls into its "that is already recoloured, Revert it
        # first" branch, which costs nothing and says what to do.
        if re.match(r'^param=graceful_slot,', line):
            continue
        keep.append(line)
    body = '\n'.join(keep).rstrip('\n')
    return ('recol1s=%d\nrecol1d=%d\nrecol2s=%d\nrecol2d=%d\n' % (SRC_MAIN, main, SRC_TRIM, trim)) + body


def main():
    check = '--check' in sys.argv
    plain = plain_blocks()

    obj = ['''// THE NINE GRACEFUL RECOLOURS AND THEIR KITS.
//
// GENERATED by tools/gengracefulcolours.py - do not hand-edit, regenerate.
//
// Each piece is a field-for-field copy of its plain record in skilling_outfits/configs/outfits.obj
// with two recolour pairs in front of it, because the whole graceful effect is that record's own
// weight= and param=energy_restore and a colour must not quietly be worth less than the piece it
// is a colour of. See the generator's header for where the two source colours come from and why
// Old School's own house colours could not be imported.
''']
    enum_result = []
    enum_kit = []
    pack_names = []

    for cnum, (key, label, main_rgb, trim_rgb) in enumerate(COLOURS, start=1):
        main, trim = rgb15(main_rgb), rgb15(trim_rgb)
        obj.append('// ---------------------------------------------------------------- %s' % label)
        for snum, piece in enumerate(PIECES, start=1):
            nm = 'graceful_%s_%s' % (piece, key)
            obj.append('[%s]' % nm)
            obj.append('name=%s graceful %s' % (label, piece))
            obj.append('desc=Graceful %s, in the colours of %s.' % (piece, label))
            obj.append(recolour(plain[piece], main, trim))
            # The way back out. The plain pieces have no op4, so this adds one rather than
            # replacing anything - and without it a coloured piece is a one-way door.
            obj.append('iop4=Revert')
            obj.append('param=graceful_from,graceful_%s' % piece)
            obj.append('param=graceful_colour,%d' % cnum)
            obj.append('')
            enum_result.append('val=%d,%s' % (cnum * 10 + snum, nm))
            pack_names.append(nm)

        kit = 'graceful_kit_%s' % key
        obj.append('''// The kit. A swatch of the cloth: the cape's own inventory model in the colour it makes, so the
// shop window and the backpack both show what you are buying. Untradeable, which also means Grace
// cannot buy it back - ~can_sell_obj refuses untradeables at every shop in this build.''')
        obj.append('[%s]' % kit)
        obj.append('name=%s graceful kit' % label)
        obj.append('desc=Use it on any graceful piece to recolour it. Revert takes it back off.')
        obj.append('model=obj_graceful_cape')
        obj.append('recol1s=%d\nrecol1d=%d\nrecol2s=%d\nrecol2d=%d' % (SRC_MAIN, main, SRC_TRIM, trim))
        obj.append('2dzoom=2320\n2dxan=564\n2dyan=827\n2dxof=2\n2dyof=2')
        obj.append('cost=%d' % KIT_COST)
        obj.append('members=yes')
        obj.append('tradeable=no')
        obj.append('category=graceful_kit')
        obj.append('param=graceful_colour,%d' % cnum)
        obj.append('')
        enum_kit.append('val=%d,%s' % (cnum, kit))
        pack_names.append(kit)

    revert = ['''// Revert, one trigger per coloured piece.
//
// GENERATED by tools/gengracefulcolours.py - do not hand-edit, regenerate.
//
// FIFTY-FOUR TRIGGERS RATHER THAN ONE ON A CATEGORY, AND IT HAS TO BE. The first version gave every
// coloured piece category=graceful_coloured and hung one [opheld4,_graceful_coloured] off it - and
// an obj has ONE category, not a list. The packer writes code 94 per category= line and
// ObjType.decode assigns, so that line silently REPLACED the armour_helmet / armour_cape /
// armour_body the piece inherited from the plain record, and every colour quietly stopped being
// armour as far as anything reading oc_category was concerned. tools/sim/graceful.ts caught it as
// 54 category mismatches.
//
// minigames/game_trail/scripts/ornament_kit.rs2 hit exactly this and wrote it out at length: a
// godsword (or) fought with unarmed attack speeds because its category had been overwritten the
// same way. One trigger per item is the fix there and it is the fix here, and since this file is
// generated the count costs nothing.
//
// They all jump to the same label; the piece and the colour come off the obj's own params.''']
    for key, label, _m, _t in COLOURS:
        for piece in PIECES:
            revert.append('[opheld4,graceful_%s_%s] @graceful_revert;' % (piece, key))

    enum = ['''// The recolour lookup.
//
// GENERATED by tools/gengracefulcolours.py - do not hand-edit, regenerate.
//
// ONE KEY, NOT TWO, because an rs2 enum takes a single input: the key is colour * 10 + slot, which
// is readable in the file (31 is Varrock's hood) and has room for nine slots a colour against the
// six that exist.

[graceful_colour_result]
inputtype=int
outputtype=namedobj''']
    enum += enum_result
    enum.append('')
    enum.append('// And back the other way, for Revert: which kit a colour hands back.')
    enum.append('[graceful_colour_kit]')
    enum.append('inputtype=int')
    enum.append('outputtype=namedobj')
    enum += enum_kit

    print('%d coloured pieces + %d kits = %d objs' % (len(COLOURS) * len(PIECES), len(COLOURS), len(pack_names)))
    if check:
        print('--check: nothing written')
        return
    open(OUT_OBJ, 'w').write('\n'.join(obj) + '\n')
    open(OUT_ENUM, 'w').write('\n'.join(enum) + '\n')
    open(OUT_REVERT, 'w').write('\n'.join(revert) + '\n')
    print('wrote', OUT_OBJ)
    print('wrote', OUT_ENUM)
    print('wrote', OUT_REVERT)
    # The pack needs an id per obj; print them so they can be appended.
    print('\n'.join(pack_names), file=open(os.path.join(HERE, '.graceful_pack_names'), 'w'))


if __name__ == '__main__':
    main()
