#!/usr/bin/env python3
"""Write the Max cape variants and their hoods from tools/maxcapevariantspec.json.

WHY A GENERATOR. Two obj records per variant, each naming up to five models, a five- or six-pair
recolour list, a 2d camera and up to eleven combat params: about four hundred numbers, every one
of which came out of the OSRS item table. Typing them is how a wrong bonus gets in and stays in.

MOST OF THEM REUSE MODELS THIS BUILD ALREADY HAS. In OSRS the six god max capes and the Accumulator
max cape are the plain Max cape's own model (29630 / 29616 / 29624) with five recolours, and their
hoods are the max hood's model with six - so here they point at obj_max_cape* and obj_max_hood*,
which the Max cape round already converted, and carry recol lines. Only fire and infernal are real
models, imported by tools/models/importosrs.py (not in this repo: it lives beside the OSRS cache on
Corey's machine).

THE RECOLOUR NUMBERS. The cache stores recolours as HSL16, which is what the CLIENT wants; an .obj
config writes RGB15 and the packer converts with ColorConversion.rgb15toHsl16. So each cache value
is reversed into an rgb15 that converts back to it, and the reversal is checked rather than assumed
- a value with no preimage is an error, not a warning. rgb15_to_hsl16 below is a mirror of the
engine's ColorConversion, and the thing that proves the mirror is right is not this file: it is
tools/objpacked.py reading the recolours back out of the PACKED table and comparing them with the
cache's own numbers, end to end.

    python3 tools/genmaxvariants.py            # write the .obj and take pack ids
    python3 tools/genmaxvariants.py --check     # exit 1 if either would change
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(C, 'tools', 'maxcapevariantspec.json')
OUT = os.path.join(C, 'scripts', 'skillcapes', 'configs', 'max_cape_variants.obj')
OUT_ENUM = os.path.join(C, 'scripts', 'skillcapes', 'configs', 'max_cape_variants.enum')
OUT_RS2 = os.path.join(C, 'scripts', 'skillcapes', 'scripts', 'max_cape_variants.rs2')
OUT_GOD = os.path.join(C, 'scripts', 'areas', 'area_mage_arena', 'configs', 'god_cape.enum')
OBJPACK = os.path.join(C, 'pack', 'obj.pack')
# god id -> (constant, plain cape, imbued cape, staff). The ids are in skillcape.constant; this
# file only needs the ORDER to be the same, which the battery checks rather than trusts.
GODS = [('saradomin', 'saradomin_cape', 'imbued_saradomin_cape', 'saradomin_staff'),
        ('guthix',    'guthix_cape',    'imbued_guthix_cape',    'guthix_staff'),
        ('zamorak',   'zamorak_cape',   'imbued_zamorak_cape',   'zamorak_staff')]
# Which variant key belongs to which god, and whether it is the imbued one.
GOD_OF = {'saradomin': 'saradomin', 'guthix': 'guthix', 'zamorak': 'zamorak',
          'imbued_saradomin': 'saradomin', 'imbued_guthix': 'guthix',
          'imbued_zamorak': 'zamorak'}
WEARPOS = ['hat', 'back', 'front', 'righthand', 'torso', 'lefthand', 'arms', 'legs',
           'head', 'hands', 'feet', 'jaw', 'ring', 'quiver']
# The two variants whose models are their own. Everything else wears the plain cape's.
OWN_MODELS = ('fire', 'infernal')
# The comments this file writes are prose, so the counts in them are spelled out. A number that
# can only be read as a digit is a comment nobody proofreads.
WORDS = {0: 'no', 1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six', 7: 'seven',
         8: 'eight', 9: 'nine', 10: 'ten', 11: 'eleven', 12: 'twelve'}


def word(n):
    return WORDS.get(n, str(n))


def rgb15_to_hsl16(v):
    """Mirror of the engine's ColorConversion.rgb15toHsl16 (src/util/ColorConversion.ts)."""
    r = ((v >> 10) & 0x1F) / 31.0
    g = ((v >> 5) & 0x1F) / 31.0
    b = (v & 0x1F) / 31.0
    mn, mx = min(r, g, b), max(r, g, b)
    h = s = 0.0
    li = (mn + mx) / 2.0
    if mn != mx:
        d = mx - mn
        s = d / (mx + mn) if li < 0.5 else d / (2.0 - mx - mn)
        if mx == r:   h = (g - b) / d
        elif mx == g: h = 2.0 + (b - r) / d
        else:         h = 4.0 + (r - g) / d
    h /= 6.0
    hi, si, lo = int(h * 256.0), int(s * 256.0), int(li * 256.0)
    si = max(0, min(255, si))
    lo = max(0, min(255, lo))
    if lo > 243:   si >>= 4
    elif lo > 217: si >>= 3
    elif lo > 192: si >>= 2
    elif lo > 179: si >>= 1
    return ((hi & 0xFF) >> 2 << 10) + ((si & 0xFF) >> 5 << 7) + (lo >> 1)


_REV = None
def hsl16_to_rgb15(h):
    """The brightest rgb15 that the engine converts back to this hsl16. Errors if there is none."""
    global _REV
    if _REV is None:
        _REV = {}
        for v in range(32768):
            _REV.setdefault(rgb15_to_hsl16(v), []).append(v)
    hits = _REV.get(h)
    if not hits:
        raise SystemExit('genmaxvariants: hsl16 %d has no rgb15 preimage, so this recolour cannot '
                         'be written as a config value at all' % h)
    v = max(hits, key=lambda x: sum(((x >> 10) & 31, (x >> 5) & 31, x & 31)))
    assert rgb15_to_hsl16(v) == h, 'the reversal does not round-trip'
    return v


def record(local, o, bonuses, model_base, is_hood):
    L = ['[%s]' % local,
         'name=%s' % o['osrs_name']]
    if o.get('desc'):
        L.append('desc=%s' % o['desc'])
    L.append('model=obj_%s' % model_base)
    L.append('manwear=obj_%s_manwear,0' % model_base)
    L.append('womanwear=obj_%s_womanwear,0' % model_base)
    if is_hood:
        L.append('manhead=obj_%s_manhead' % model_base)
        L.append('womanhead=obj_%s_womanhead' % model_base)
    for k in ('wearpos', 'wearpos2'):
        v = o.get(k)
        if v is not None:
            L.append('%s=%s' % (k, WEARPOS[v]))
    for cfg, k in (('2dzoom', 'zoom2d'), ('2dxan', 'xan2d'), ('2dyan', 'yan2d'),
                   ('2dyof', 'yof2d')):
        if o.get(k) is not None:
            L.append('%s=%s' % (cfg, o[k]))
    for n, pair in enumerate(o.get('recol') or [], start=1):
        src, dst = pair
        L.append('recol%ds=%d' % (n, hsl16_to_rgb15(src)))
        L.append('recol%dd=%d' % (n, hsl16_to_rgb15(dst)))
    L.append('iop2=Wear')
    if o.get('cost') is not None:
        L.append('cost=%d' % o['cost'])
    if o.get('members'):
        L.append('members=yes')
    L.append('tradeable=no')
    if o.get('weight') is not None:
        L.append('weight=%dg' % o['weight'])
    if not is_hood:
        L.append('category=armour_cape')
    for k, v in bonuses.items():
        L.append('param=%s,%d' % (k, v))
    return L


def build(spec):
    n = len(spec['variants'])
    L = ['// THE %s MAX CAPE VARIANTS AND THEIR HOODS. GENERATED - do not hand-edit.'
         % word(n).upper(),
         '//   python3 tools/genmaxvariants.py',
         '// The numbers come from tools/maxcapevariantspec.json, which took them out of the OSRS',
         '// item table rather than off the wiki. Every bonus below is its SOURCE cape\'s, which is',
         '// what a variant is: the max cape\'s look-and-name over the source cape\'s stats.',
         '//',
         '// A VARIANT IS NOT A MAX CAPE. It carries iop2=Wear and nothing else - no Teleports, no',
         '// Features - which is the cache\'s own list for every one of them, where the plain cape',
         '// has four ops. The perks go the same way: skillcape_perks.rs2 answers true for four',
         '// skills only, and claude/max-cape-variants.md says which four and why.',
         '//',
         '// THE ACCUMULATOR MAX CAPE SAVES AMMUNITION, and that does not come from here either:',
         '// it comes from the accumulator fused into it. ~avas_device in the Animal Magnetism',
         '// scripts reads the cape slot and asks maxvariant_source what it came from, so the',
         '// variant is an Ava\'s accumulator for bows, thrown weapons, the blowpipe and the magnet.',
         '//',
         '// The %s variants with no models of their own are the plain Max cape\'s model with five'
         % word(n - len(OWN_MODELS)),
         '// recolours, and the max hood\'s with six, exactly as OSRS has them.',
         '']
    names = []
    for v in spec['variants']:
        key = v['key']
        own = key in OWN_MODELS
        cape_local = '%s_max_cape' % key
        hood_local = '%s_max_hood' % key
        L += record(cape_local, v['cape'], v['bonuses'],
                    cape_local if own else 'max_cape', False) + ['']
        L += record(hood_local, v['hood'], {},
                    hood_local if own else 'max_hood', True) + ['']
        names += [cape_local, hood_local]
    return '\n'.join(L), names


def build_enums(spec):
    """The three variant tables, keyed so every script that needs one is a single enum() call."""
    V = spec['variants']
    L = ['// LOOKUP TABLES FOR THE MAX CAPE VARIANTS. GENERATED - do not hand-edit.',
         '//   python3 tools/genmaxvariants.py',
         '//',
         '// Three tables rather than one, because three different questions get asked: what does',
         '// this source cape combine INTO, what hood comes with a variant, and what did a variant',
         '// come FROM. The third is also how "is this a variant at all" is asked - a null answer',
         '// means it is not one - which is why skillcape_perks.rs2 needs no list of its own.',
         '',
         '[maxvariant_cape]',
         '// source cape -> the variant it makes with a Max cape',
         'inputtype=obj',
         'outputtype=namedobj',
         'default=null']
    for v in V:
        L.append('val=%s,%s_max_cape' % (v['source_cape'], v['key']))
    L += ['',
          '[maxvariant_hood]',
          '// variant cape -> the hood that comes with it',
          'inputtype=obj',
          'outputtype=namedobj',
          'default=null']
    for v in V:
        L.append('val=%s_max_cape,%s_max_hood' % (v['key'], v['key']))
    L += ['',
          '[maxvariant_source]',
          '// variant cape -> the source cape it came from. A null answer means "not a variant".',
          'inputtype=obj',
          'outputtype=namedobj',
          'default=null']
    for v in V:
        L.append('val=%s_max_cape,%s' % (v['key'], v['source_cape']))
    L.append('')
    return '\n'.join(L)


def build_god(spec):
    """Every god cape and god staff there is, mapped to its god. Twelve capes, not six.

    THIS IS THE FILE THAT MAKES THE VARIANTS REAL GOD CAPES. god_gear.rs2 used to name capes in
    pairs - check_conflicting_god_cape(zamorak_cape, guthix_cape) - which does not extend: six
    capes a god would mean four arguments per call and nine call sites to remember. A table keyed
    by obj answers "which god is this" in one enum() lookup, and adding a cape is one line here.
    """
    by_god = {}
    for v in spec['variants']:
        g = GOD_OF.get(v['key'])
        if g:
            by_god.setdefault(g, []).append('%s_max_cape' % v['key'])
    L = ['// WHICH GOD A CAPE OR A STAFF BELONGS TO. GENERATED - do not hand-edit.',
         '//   python3 tools/genmaxvariants.py',
         '//',
         '// A cape not in this table answers ^god_none, which is how "wearing no god cape" and',
         '// "wearing an ordinary cape" come out the same - god_gear.rs2 leans on that.',
         '//',
         '// THE SIX MAX CAPE VARIANTS ARE IN HERE, and that is the decision this round made: the',
         "// wiki's God capes page lists them as god capes, and OSRS's own item table gives a",
         '// variant the SAME god param as the plain cape (40 Saradomin, 41 Zamorak, 42 Guthix).',
         '// tools/maxcapevariantspec.json records the evidence and that it is a judgement call.',
         '',
         '[god_cape_god]',
         'inputtype=obj',
         'outputtype=int',
         'default=0']
    for god, plain, imbued, _staff in GODS:
        L.append('// %s' % god)
        L.append('val=%s,^god_%s' % (plain, god))
        L.append('val=%s,^god_%s' % (imbued, god))
        for name in by_god.get(god, []):
            L.append('val=%s,^god_%s' % (name, god))
    L += ['',
          '[god_staff_god]',
          'inputtype=obj',
          'outputtype=int',
          'default=0']
    for god, _p, _i, staff in GODS:
        L.append('val=%s,^god_%s' % (staff, god))
    L.append('')
    return '\n'.join(L)


def build_rs2(spec):
    V = spec['variants']
    L = ['// COMBINING AND TAKING APART THE MAX CAPE VARIANTS. GENERATED - do not hand-edit.',
         '//   python3 tools/genmaxvariants.py',
         '//',
         "// HOW OSRS DOES IT: use the source cape on the Max cape with the Max HOOD in your",
         '// inventory too, and all three become the variant cape and its own hood. It is free, and',
         '// a knife on the variant gives the three back. tools/maxcapevariantspec.json quotes the',
         '// wiki for both halves.',
         '//',
         '// ONE TRIGGER FOR THE COMBINE, not eight. OpHeldUHandler tries the target item\'s trigger',
         '// first and the used item\'s second, so [opheldu,max_cape] fires whichever way round the',
         "// player does it, and maxvariant_cape turns the other item into the answer. The knife",
         '// half has to go the other way - on the variants - because [opheldu,knife] is already',
         '// taken by the gnome cooking fruit-cutting handler and may only be declared once.',
         '',
         '[opheldu,max_cape]',
         'def_namedobj $variant = enum(obj, namedobj, maxvariant_cape, last_useitem);',
         'if ($variant = null) {',
         '    ~displaymessage(^dm_default);',
         '    return;',
         '}',
         '@maxvariant_combine($variant);',
         '',
         '// THE HOOD IS A REQUIREMENT, NOT A COURTESY. OSRS asks for cape, hood and source cape,',
         '// and the reason is that the variant has its own hood to hand back - there is nothing to',
         '// turn into a Fire max hood if the Max hood is in the bank.',
         '[label,maxvariant_combine](namedobj $variant)',
         'def_namedobj $source = enum(obj, namedobj, maxvariant_source, $variant);',
         'def_namedobj $hood = enum(obj, namedobj, maxvariant_hood, $variant);',
         'if (inv_total(inv, max_hood) = 0) {',
         '    mes("You need the Max hood with you as well - the new cape comes with its own.");',
         '    return;',
         '}',
         'if (inv_freespace(inv) < 1) {',
         '    mes("You do not have enough inventory space to do that.");',
         '    return;',
         '}',
         'inv_del(inv, max_cape, 1);',
         'inv_del(inv, max_hood, 1);',
         'inv_del(inv, $source, 1);',
         'inv_add(inv, $variant, 1);',
         'inv_add(inv, $hood, 1);',
         '~doubleobjbox($variant, $hood, "You fuse the two capes together. The Max cape takes on a new form, and the hood with it.", 200);',
         '',
         '// A KNIFE TAKES IT APART, which is OSRS\'s own free way back - Mac also buys a variant',
         '// back for coins there, and that is not implemented because Mac does not sell the',
         '// variants here in the first place.',
         '[label,maxvariant_split]',
         'if (last_useitem ! knife) {',
         '    ~displaymessage(^dm_default);',
         '    return;',
         '}',
         '// last_item is an obj, not a namedobj - rs2check rule 7 said so before the build',
         '// did. inv_del takes an obj anyway; only inv_add needs the narrower type, and the',
         '// two things added back come out of the enums already typed namedobj.',
         'def_obj $variant = last_item;',
         'def_namedobj $source = enum(obj, namedobj, maxvariant_source, $variant);',
         'def_namedobj $hood = enum(obj, namedobj, maxvariant_hood, $variant);',
         'if (inv_total(inv, $hood) = 0) {',
         '    mes("You need the matching hood with you - it goes back to being a Max hood.");',
         '    return;',
         '}',
         'if (inv_freespace(inv) < 1) {',
         '    mes("You do not have enough inventory space to do that.");',
         '    return;',
         '}',
         'inv_del(inv, $variant, 1);',
         'inv_del(inv, $hood, 1);',
         'inv_add(inv, max_cape, 1);',
         'inv_add(inv, max_hood, 1);',
         'inv_add(inv, $source, 1);',
         '// human_fletching: the knife-in-hand animation viking_olaf.rs2 uses for the same',
         '// gesture. There is no human_craft in all.seq - rs2check rule 14 caught that too.',
         'anim(human_fletching, 0);',
         '~doubleobjbox(max_cape, $source, "You cut the capes apart. The Max cape and its hood are whole again.", 200);',
         '']
    for v in V:
        L.append('[opheldu,%s_max_cape] @maxvariant_split;' % v['key'])
    ngod = sum(1 for v in V if GOD_OF.get(v['key']))
    L += ['',
          '// THE %s GOD VARIANTS EQUIP LIKE A GOD CAPE, so the staff of another god refuses them.'
          % word(ngod).upper(),
          '// The other %s need no trigger at all: [opheld2,_] in player/scripts/equip.rs2 wears'
          % word(len(V) - ngod),
          '// anything that has nothing more specific to say.']
    for v in V:
        g = GOD_OF.get(v['key'])
        if g:
            L.append('[opheld2,%s_max_cape] @god_cape_equip(^god_%s);' % (v['key'], g))
    L.append('')
    return '\n'.join(L)


# THERE IS NO take_enum_ids, and that is deliberate. pack/enum.pack is GENERATED - it is in
# .gitignore and deploy_build.sh deletes it before every build, which then assigns ids from the
# .enum files themselves. An earlier version of this file appended ids to it; they were correct,
# and they were also wiped by the next build's rm and re-derived. pack/obj.pack is different: it
# is tracked, and an obj's id is part of what a save file means, so that one is taken here.


def take_ids(names, check):
    txt = open(OBJPACK, newline='').read()
    have = dict(re.findall(r'^(\d+)=(\S+)$', txt.replace('\r\n', '\n'), re.M))
    have = {n: int(i) for i, n in have.items()}
    nxt = max(have.values()) + 1
    added = []
    lines = txt.replace('\r\n', '\n').rstrip('\n').split('\n')
    for n in names:
        if n in have:
            continue
        lines.append('%d=%s' % (nxt, n))
        added.append('%d=%s' % (nxt, n))
        nxt += 1
    new = '\n'.join(lines) + '\n'
    if not check and added:
        open(OBJPACK, 'w', newline='\n').write(new)
    return added


def main():
    check = '--check' in sys.argv
    spec = json.load(open(SPEC))
    want = {OUT: build(spec)[0], OUT_ENUM: build_enums(spec),
            OUT_RS2: build_rs2(spec), OUT_GOD: build_god(spec)}
    names = build(spec)[1]
    if check:
        bad = []
        for path, text in want.items():
            have = open(path, newline='').read() if os.path.exists(path) else None
            # LINE-ENDING BLIND. The repo is LF and .gitattributes has text=auto, so a checkout on
            # Windows can hand this file back with CRLF - and a byte comparison would then report
            # "would change" on a tree nobody had touched. The content is what is being checked.
            if have is None or have.replace('\r\n', '\n') != text.replace('\r\n', '\n'):
                bad.append('%s would change' % os.path.relpath(path, C))
        missing = take_ids(names, True)
        if missing:
            bad.append('obj.pack is missing %s' % ', '.join(missing))
        if bad:
            print('genmaxvariants --check: ' + '; '.join(bad))
            return 1
        print('genmaxvariants --check: the four generated files and pack/obj.pack are already '
              'what this writes')
        return 0
    for path, text in want.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w', newline='').write(text)
        print('wrote %s' % os.path.relpath(path, C))
    added = take_ids(names, False)
    print('%d records, %d obj.pack ids%s (enum.pack is generated, so nothing is taken there)'
          % (len(names), len(added), (' (%s..%s)' % (added[0], added[-1])) if added else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
