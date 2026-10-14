#!/usr/bin/env python3
"""Generate every slayer helmet colour from tools/slayerhelmspec.json.

Writes three files and appends to one pack:

  configs/slayer_helm_colours.obj    one obj per colour per imbue state
  configs/slayer_helm.param          the three params the inheritance doors read
  scripts/slayer_helm_colours.rs2    the recolour, and Check/Disassemble for every colour
  pack/obj.pack                      the names, appended in spec order, id-stable

THE ART IS OSRS'S OWN. An earlier version of this generator made a colour by putting two recolour
pairs on the plain helmet's model, which only ever repainted the mask and the strap. OSRS's
variants are separately authored meshes with different horns, spines and, in one case, a hood, so
each colour here names its own imported model set instead. tools/models/importosrs.py did the
importing, from the osrs_obj id in the spec; the generator only points at the result. The camera
is the cache's too - the plain helmet faces 1791 and every recolour 1773.

RECOLOUR PAIRS SURVIVE for the three OSRS itself recolours: Twisted repaints its own model, and
Radiant is a ten-pair repaint of the Oathplate model. Those come out of the cache as HSL16 and are
stored here as the RGB15 a .obj config wants. A source matching no face does nothing at all and
reports no error, so battery group 67 checks every source against the model's real face colours.

WHY A GENERATOR for 28 items: because they differ from each other in a name, five model lines and
a camera, and everything else - the wear positions, the weight, the defences, the equip gate, the
Check and Disassemble ops - has to stay identical to the plain helmet it is a recolour of. That is
exactly the shape that drifts when it is 28 hand-written blocks.

MEMBERSHIP IS THREE PARAMS. slayer_headgear is anything that gives the on-task melee bonus - both
masks and every helmet. slayer_helmet is the four protections a helmet inherits from its parts, so
helmets only: a bare mask has no earmuffs in it. slayer_imbued is the ranged and magic boost. The
three procs that read them are fixed-size no matter how many colours exist.

ONLY THE COLOURS WITH A source BLOCK CAN BE OBTAINED. The rest are built anyway - Corey asked to
be able to look at them with ::give - and they get no head, no unlock and no [opheldu] trigger,
and their Disassemble hands back five parts rather than six. tools/obtainable.py reads this same
spec and lists them by name rather than being silenced.

    python3 tools/genslayerhelm.py
"""
import os, io, json, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_OBJ = 'scripts/skill_slayer/configs/slayer_helm_colours.obj'
OUT_PARAM = 'scripts/skill_slayer/configs/slayer_helm.param'
OUT_RS2 = 'scripts/skill_slayer/scripts/slayer_helm_colours.rs2'
OBJ_PACK = 'pack/obj.pack'
BASE = 'slayer_helm'

# Lines the base block owns that a colour must NOT inherit: it has its own art, its own camera,
# its own name, and its params are decided per variant. Copying the model lines was the whole bug
# this round fixed; copying param=slayer_* gave every colour each param twice in the last one.
# param=ornament_ is excluded for the same reason as param=imbue_: the pairing is to ONE obj. The
# plain helmet points at slayer_helm_gravedigger, so a colour inheriting that line would let a
# Gravedigger kit be used on a red helmet and hand back the plain Gravedigger helm, throwing the
# red away. The plain helmet gained those params after this file was last generated, so a rebuild
# quietly added them to all fourteen colours - caught by reading the regenerated diff.
OVERRIDDEN = ('name=', 'desc=', 'model=', 'manwear=', 'womanwear=', 'manhead=', 'womanhead=',
              '2dzoom=', '2dxan=', '2dyan=', '2dzan=', '2dxof=', '2dyof=',
              'recol', 'param=slayer_', 'param=imbue_', 'param=ornament_')


def read(p):
    return io.open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')


def crlf(p):
    raw = open(os.path.join(ROOT, p), 'rb').read()
    return raw.count(b'\r\n') > raw.count(b'\n') / 2


def write(p, lines):
    path = os.path.join(ROOT, p)
    nl = '\r\n' if (os.path.exists(path) and crlf(p)) else '\n'
    open(path, 'wb').write((nl.join(lines).rstrip('\r\n') + nl).encode('utf-8'))


def block(text, name):
    m = re.search(r'^\[%s\]\n(.*?)(?=\n\[|\Z)' % re.escape(name), text, re.S | re.M)
    return m.group(1).split('\n') if m else None


def pack_append(path, names):
    """Append names to a tracked name-map pack, id-stable. Preserves line endings."""
    full = os.path.join(ROOT, path)
    s = io.open(full, newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    lines = s.replace('\r\n', '\n').rstrip('\n').split('\n')
    have = {l.split('=', 1)[1]: int(l.split('=', 1)[0]) for l in lines if '=' in l}
    nxt = max(have.values()) + 1
    added = []
    for nm in names:
        if nm in have:
            continue
        lines.append('%d=%s' % (nxt, nm))
        have[nm] = nxt
        added.append(nm)
        nxt += 1
    open(full, 'wb').write((nl.join(lines) + nl).encode('utf-8'))
    return have, added


def models_for(spec, c):
    """The five model lines a colour carries. womanhead is its own file because that is what the
    importer writes - the cache gives both heads the same model id and the plain helmet on disk
    already has the pair."""
    if c['models'] == 'plain':
        stem = spec['base_models']['plain']
    else:
        stem = 'obj_%s_%s' % (BASE, c['models'])
    return ['model=%s' % stem,
            'manwear=%s_manwear,0' % stem,
            'womanwear=%s_womanwear,0' % stem,
            'manhead=%s_manhead' % stem,
            'womanhead=%s_womanhead' % stem]


def main():
    spec = json.loads(read('tools/slayerhelmspec.json'))
    items = read('scripts/general/configs/osrs_items.obj')
    base = block(items, BASE)
    basei = block(items, BASE + '_i')
    if base is None or basei is None:
        raise SystemExit('genslayerhelm: %s / %s_i are not in osrs_items.obj' % (BASE, BASE))

    objpack = {l.split('=', 1)[1].strip() for l in read(OBJ_PACK).split('\n') if '=' in l}
    modelpack = {l.split('=', 1)[1].strip() for l in read('pack/model.pack').split('\n') if '=' in l}
    err = []
    seen = set()
    for c in spec['colours']:
        if c['key'] in seen:
            err.append('%s appears twice' % c['key'])
        seen.add(c['key'])
        for line in models_for(spec, c):
            nm = line.split('=', 1)[1].split(',')[0]
            if nm not in modelpack:
                err.append('%s wants %s, which is not in pack/model.pack - import it first'
                           % (c['key'], nm))
        s = c.get('source')
        if s and s['head'] not in objpack:
            err.append('%s needs %s, which is not in pack/obj.pack' % (c['key'], s['head']))
    bits = [c['source']['bit'] for c in spec['colours'] if 'source' in c]
    if len(set(bits)) != len(bits):
        err.append('two colours share an unlock bit: %s' % bits)
    if err:
        raise SystemExit('\n'.join('  ERROR ' + e for e in err))

    # ------------------------------------------------------------------ obj.pack
    names = []
    for c in spec['colours']:
        names += ['%s_%s' % (BASE, c['key']), '%s_%s_i' % (BASE, c['key'])]
    ids, added = pack_append(OBJ_PACK, names)

    # ------------------------------------------------------------------ the params
    write(OUT_PARAM, [
        '// What a piece of slayer headgear IS, read by the three procs that decide what it gives.',
        '//',
        '// GENERATED by tools/genslayerhelm.py - do not hand-edit.',
        '//',
        '// The alternative was a list of item names inside ~black_mask_on_task, ~slayer_helm_worn',
        '// and ~black_mask_imbued_on_task, growing by two entries every time a colour is added -',
        '// and there are fourteen of them. A category would have been simpler again, but an obj',
        '// gets exactly one and these are already armour_helmet, which the Entrana monk and the',
        '// desert heat both read.',
        '',
        '// Both masks and every helmet: the on-task 7/6 melee bonus.',
        '[slayer_headgear]',
        'type=boolean',
        'default=no',
        '',
        '// Helmets only. A bare black mask has no earmuffs, nose peg or facemask in it.',
        '[slayer_helmet]',
        'type=boolean',
        'default=no',
        '',
        '// The imbued pair and their recolours: 15% to ranged and magic accuracy and damage.',
        '[slayer_imbued]',
        'type=boolean',
        'default=no',
    ])

    # ------------------------------------------------------------------ the objs
    o = ['// Every slayer helmet colour.',
         '//',
         '// GENERATED by tools/genslayerhelm.py from tools/slayerhelmspec.json - do not hand-edit.',
         '//',
         '// Each one carries OSRS\'S OWN MODEL for that colour, imported by tools/models/importosrs.py',
         '// - they are separately authored meshes, not repaints of the plain helmet, which is why',
         '// the red one has different horns and the hooded one is a hood. The camera comes from the',
         '// cache too. Only Twisted and Radiant carry recolour pairs, because only those two are',
         '// recolours in OSRS as well.',
         '//',
         '// Everything else - the wear positions, the weight, the defences, the equip gate, the',
         '// Check and Disassemble ops - is copied from the plain helmet and its imbued twin, so a',
         '// colour cannot quietly have different stats from the helmet it is a colour of.',
         '']
    made = []
    for c in spec['colours']:
        for imbued in (False, True):
            key = '%s_%s%s' % (BASE, c['key'], '_i' if imbued else '')
            label = '%s slayer helmet%s' % (c['label'], ' (i)' if imbued else '')
            made.append((key, c, imbued))
            src = basei if imbued else base
            desc = next((l.strip()[5:] for l in src if l.strip().startswith('desc=')), '')
            o += ['[%s]' % key, 'name=%s' % label, 'desc=%s' % desc]
            o += models_for(spec, c)
            cam = c['camera']
            o += ['2dzoom=%d' % cam['zoom'], '2dxan=%d' % cam['xan'], '2dyan=%d' % cam['yan'],
                  '2dxof=%d' % cam['xof'], '2dyof=%d' % cam['yof']]
            for n, (s, d) in enumerate(c['recol'], start=1):
                o += ['recol%ds=%d' % (n, s), 'recol%dd=%d' % (n, d)]
            for line in src:
                line = line.strip()
                if not line or line.startswith('//') or line.startswith(OVERRIDDEN):
                    continue
                o.append(line)
            o += ['param=slayer_headgear,yes', 'param=slayer_helmet,yes']
            # The imbue pairing is per COLOUR, which is why param=imbue_ is overridden rather than
            # copied: copying the plain helmet's line would point every colour's imbue at the plain
            # imbued helmet, and every colour's Uncharge at the plain one. iop5=Uncharge IS copied,
            # because that line is the same on all fourteen.
            if imbued:
                o.append('param=slayer_imbued,yes')
                o.append('param=imbue_from,%s' % key[:-2])
            else:
                o.append('param=imbue_into,%s_i' % key)
            o.append('')
    write(OUT_OBJ, o)

    # ------------------------------------------------------------------ the script
    withsrc = [c for c in spec['colours'] if 'source' in c]
    r = ['// Recolouring a slayer helmet, and what every colour keeps.',
         '//',
         '// GENERATED by tools/genslayerhelm.py from tools/slayerhelmspec.json - do not hand-edit.',
         '//',
         '// OSRS: buy the unlock with Slayer reward points, then use the head on the helmet. The head',
         '// is consumed. Each colour has its own unlock and its own head, and both are checked - an',
         '// unlock without a head does nothing, and a head without the unlock says why.',
         '//',
         '// ONLY %d OF THE %d COLOURS HAVE A SOURCE. The rest exist so they can be looked at with' % (len(withsrc), len(spec['colours'])),
         '// ::give and get no trigger here at all; the black one becomes real the moment the King',
         '// Black Dragon does. tools/obtainable.py reports them by name rather than being told to',
         '// ignore them.',
         '//',
         '// A SCROLL OF IMBUING WORKS ON EVERY COLOUR, and costs this file no trigger: the pairing',
         '// is the param=imbue_into / param=imbue_from pair on each obj above, and',
         '// skill_slayer/scripts/imbue_scroll.rs2 is one proc that reads them.',
         '//',
         '// NO COLOUR HAS AN UNCHARGE OP, because no slayer helmet in the OSRS cache has one - all',
         '// twenty-six are Wear / Check / Disassemble. Getting a scroll back out of a helmet is',
         '// Disassemble, which hands back the imbued black mask, and then Uncharge on the mask.',
         '//',
         '// THE IMBUE SURVIVES THE RECOLOUR IN BOTH DIRECTIONS. An imbued helmet recoloured stays',
         '// imbued, which is what the paired _i variants are for. Nothing here can turn an imbued',
         '// helmet into a plain one, because the player paid for it.',
         '']
    for c in withsrc:
        s = c['source']
        # ONE TRIGGER, ON THE HEAD. [opheldu,X] normalises which way round the click came and runs
        # the first half that carries a trigger, so a second one on the helmet is not a fallback -
        # it is a duplicate, and a duplicate trigger is a hard build error.
        r += ['// ---- %s: %s, unlocked with %s' % (c['label'].lower(), s['head_label'], s['unlock']),
              '[opheldu,%s] @slayer_recolour_%s;' % (s['head'], c['key']),
              '',
              '[label,slayer_recolour_%s]' % c['key'],
              'if (~slayer_helm_recolour_pair(%s) = false) {' % s['head'],
              '    ~displaymessage(^dm_default);',
              '    return;',
              '}',
              'if (~slayer_has_unlock(%d) = false) {' % s['bit'],
              '    mes("You need the %s unlock from a Slayer master to do that.");' % s['unlock'],
              '    return;',
              '}',
              'def_namedobj $into = %s_%s;' % (BASE, c['key']),
              'if (inv_total(inv, %s_i) > 0) {' % BASE,
              '    $into = %s_%s_i;' % (BASE, c['key']),
              '}',
              'inv_del(inv, %s, 1);' % s['head'],
              'if (inv_total(inv, %s_i) > 0) {' % BASE,
              '    inv_del(inv, %s_i, 1);' % BASE,
              '} else {',
              '    inv_del(inv, %s, 1);' % BASE,
              '}',
              'inv_add(inv, $into, 1);',
              '~objbox($into, "You fix the %s onto your slayer helmet.", 250, 0, 0);' % s['head_label'].lower(),
              '']
    r += ['// The two halves of the use, either way round: a head and a helmet of some kind.',
          '[proc,slayer_helm_recolour_pair](namedobj $head)(boolean)',
          'if (inv_total(inv, $head) < 1) {',
          '    return(false);',
          '}',
          'if (inv_total(inv, %s) > 0 | inv_total(inv, %s_i) > 0) {' % (BASE, BASE),
          '    return(true);',
          '}',
          'return(false);',
          '']
    r += ['// Check and Disassemble, for every colour. A colour WITH a head gives it back on',
          '// disassembly - taking the helmet apart does not destroy it, the same way the five parts',
          '// survive. A colour with no head gives back five things, not six.', '']
    for key, c, imbued in made:
        r.append('[opheld3,%s] @slayer_helm_check;' % key)
    r.append('')
    # AND THE SAME CHECK WHILE IT IS ON YOUR HEAD. Every colour carries wearop1=Check, copied from
    # the plain helmet along with the rest of its config, but only the opheld3 above was ever
    # generated - so Check worked in the pack and did nothing at all when worn, on all fourteen
    # colours and both imbue states. tools/sim/wearop.ts sweeps for exactly that: a worn option
    # with no [label,wearop<n>_...] behind it. The plain helmet has had both since slayer_helm.rs2.
    r += ['// The worn Check, which wearop1=Check on every colour needs behind it.', '']
    for key, c, imbued in made:
        r.append('[label,wearop1_%s] @slayer_helm_check;' % key)
    r.append('')
    for key, c, imbued in made:
        mask = 'black_mask_i' if imbued else 'black_mask'
        if 'source' in c:
            r.append('[opheld4,%s] @slayer_helm_split_coloured(%s, %s);'
                     % (key, mask, c['source']['head']))
        else:
            r.append('[opheld4,%s] @slayer_helm_split_headless(%s);' % (key, mask))
    r += ['',
          '[label,slayer_helm_split_coloured](namedobj $mask, namedobj $head)',
          'if (inv_freespace(inv) < 5) {',
          '    mes("You need five free inventory spaces to disassemble your slayer helmet.");',
          '    return;',
          '}',
          'inv_delslot(inv, last_slot);',
          '~slayer_helm_give_parts($mask);',
          'inv_add(inv, $head, 1);',
          'mes("You disassemble your slayer helmet.");',
          '',
          '// A colour nothing in the game can make yet: there is no head to hand back.',
          '[label,slayer_helm_split_headless](namedobj $mask)',
          'if (inv_freespace(inv) < 4) {',
          '    mes("You need four free inventory spaces to disassemble your slayer helmet.");',
          '    return;',
          '}',
          'inv_delslot(inv, last_slot);',
          '~slayer_helm_give_parts($mask);',
          'mes("You disassemble your slayer helmet.");',
          '',
          '[proc,slayer_helm_give_parts](namedobj $mask)',
          'inv_add(inv, $mask, 1);',
          'inv_add(inv, slayer_earmuffs, 1);',
          'inv_add(inv, slayer_facemask, 1);',
          'inv_add(inv, slayer_nosepeg, 1);',
          'inv_add(inv, wallbeast_spike_helmet, 1);',
          '']
    write(OUT_RS2, r)

    print('%s: %d helmets, %d colours' % (OUT_OBJ, len(made), len(spec['colours'])))
    for c in spec['colours']:
        print('   %-12s models=%-10s recol=%-2d %s'
              % (c['key'], c['models'], len(c['recol']),
                 ('source: %s + %s' % (c['source']['head'], c['source']['unlock']))
                 if 'source' in c else 'no source - ::give only'))
    print('%s: 3 params' % OUT_PARAM)
    print('%s: %d with a source, unlock bits %s'
          % (OUT_RS2, len(withsrc), [c['source']['bit'] for c in withsrc]))
    print('%s: %d appended%s' % (OBJ_PACK, len(added), (' (%s..%s)' % (added[0], added[-1])) if added else ''))
    return made


if __name__ == '__main__':
    main()
