#!/usr/bin/env python3
"""Write the six clue hunter outfit records from tools/cluehunterspec.json, and render them.

WHY A GENERATOR FOR SIX RECORDS. Because of the signs. The OSRS item table stores a negative
bonus as an unsigned 32-bit int - the Helm of Raedwald's -6 magic attack comes back as
4294967290 - and writing that through by hand or by a careless import would put the largest magic
attack bonus in the game on a leather helmet. The spec holds the signed values, this writes them,
and tools/clue_battery.py checks the config against the spec so neither can drift alone.

    python3 tools/gencluehunter.py                 # write the config
    python3 tools/gencluehunter.py --check          # exit 1 if it would change
    python3 tools/gencluehunter.py --render out.png # and look at the six before shipping
"""
import json, os, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(C, 'tools'))
SPEC = os.path.join(C, 'tools', 'cluehunterspec.json')
OUT = os.path.join(C, 'scripts', 'minigames', 'game_trail', 'configs', 'clue_hunter.obj')
OUT_RS2 = os.path.join(C, 'scripts', 'minigames', 'game_trail', 'scripts', 'clue_hunter.rs2')
# wearpos constant per piece, so the worn test looks in the slot the piece is actually worn in -
# the mistake the Rogue outfit's battery check exists to catch.
SLOT = {'hat': '^wearpos_hat', 'torso': '^wearpos_torso', 'legs': '^wearpos_legs',
        'hands': '^wearpos_hands', 'feet': '^wearpos_feet', 'back': '^wearpos_back'}
CATEGORY = {'hat': 'armour_helmet', 'torso': 'armour_body', 'legs': 'armour_legs',
            'hands': 'armour_hands', 'feet': 'armour_boots', 'back': 'armour_cape'}


def build(spec):
    d = spec['departures']
    L = ['// THE CLUE HUNTER OUTFIT. GENERATED - do not hand-edit.',
         '//   python3 tools/gencluehunter.py',
         '//',
         '// Six objs out of a modern OSRS cache (19687, 19689, 19691, 19693, 19695, 19697), models',
         '// re-encoded by tools/models/importosrs.py. The bonuses, wearpos rows, weights and 2d',
         '// cameras below are the item table\'s own numbers, SIGNED: the cache stores the helm\'s',
         '// -6 magic attack as 4294967290, and writing that through would have put the largest',
         '// magic attack bonus in the game on a leather helmet.',
         '//',
         '// WHAT THEY DO IS NOT OSRS\'S. In OSRS this outfit has leather-armour stats, counts as',
         '// warm clothing, and does nothing whatsoever for clues. Here the full set gives a',
         '// %d%% chance of a double casket and a %d%% chance of skipping a trail step - both asked'
         % (d['double_casket_pct'], d['skip_step_pct']),
         '// for by name. clue_hunter.rs2 holds them and claude/clue-hunter-outfit.md says why.',
         '//',
         '// NO DESTROY OP, though OSRS gives every piece one at inventory op 5: opheld5 is Drop in',
         '// this build, served globally by player/scripts/drop.rs2, so a Destroy there would take',
         '// Drop off the item. tradeable=no instead, the way this fork ships an earned set.',
         '']
    for p in spec['pieces']:
        L.append('[%s]' % p['local'])
        L.append('name=%s' % p['osrs_name'])
        if p.get('desc'):
            L.append('desc=%s' % p['desc'])
        L.append('model=obj_%s' % p['local'])
        L.append('manwear=obj_%s_manwear,0' % p['local'])
        # THE SECOND WORN MODEL IS THE SLEEVES, and leaving it out is not a missing detail: the garb
        # also carries wearpos2 'arms', which HIDES the player's own arms. One without the other is a
        # torso with nothing below the shoulders, in every animation.
        if p.get('manwear2'):
            L.append('manwear2=obj_%s_manwear2' % p['local'])
        L.append('womanwear=obj_%s_womanwear,0' % p['local'])
        if p.get('womanwear2'):
            L.append('womanwear2=obj_%s_womanwear2' % p['local'])
        if p.get('manhead'):
            L.append('manhead=obj_%s_manhead' % p['local'])
        if p.get('womanhead'):
            L.append('womanhead=obj_%s_womanhead' % p['local'])
        L.append('wearpos=%s' % p['wearpos'])
        if p.get('wearpos2'):
            L.append('wearpos2=%s' % p['wearpos2'])
        for cfg, k in (('2dzoom', 'zoom2d'), ('2dxan', 'xan2d'), ('2dyan', 'yan2d'),
                       ('2dxof', 'xof2d'), ('2dyof', 'yof2d')):
            if p.get(k) is not None:
                L.append('%s=%s' % (cfg, p[k]))
        L.append('iop2=Wear')
        if p.get('cost') is not None:
            L.append('cost=%d' % p['cost'])
        L.append('members=yes')
        L.append('tradeable=no')
        if p.get('weight') is not None:
            L.append('weight=%dg' % p['weight'])
        L.append('category=%s' % CATEGORY[p['wearpos']])
        for k, v in p['bonuses'].items():
            L.append('param=%s,%d' % (k, v))
        L.append('')
    return '\n'.join(L)


def build_rs2(spec):
    d, src = spec['departures'], spec['source']
    P = spec['pieces']
    L = ['// WHAT THE CLUE HUNTER OUTFIT DOES. GENERATED - do not hand-edit.',
         '//   python3 tools/gencluehunter.py',
         '//',
         "// NONE OF THIS IS OSRS'S. There the outfit has leather-armour stats, counts as warm",
         '// clothing, and does nothing at all for clues - no casket bonus, no step reduction. All',
         '// three effects below were asked for by name, and tools/cluehunterspec.json records that',
         '// under what_osrs_actually_does so nobody later reads them as canon.',
         '//',
         '// WHERE EACH ONE IS HOOKED, and why there:',
         '//   ~clue_hunter_doubles   the three ~trail_clue_<tier>_reward procs, right after they',
         '//                          work out how many times to roll - which is the only place a',
         '//                          "double casket" can mean anything precise.',
         '//   ~clue_hunter_skips     ~trail_clue_progress in trail_clue_helper.rs2, which every',
         '//                          tier goes through, so one hook covers easy, medium and hard.',
         '//   ~clue_hunter_droproll  inside the same reward loop, once per roll. It does NOT ask',
         '//                          whether the set is worn, for the obvious reason.',
         '',
         '// ALL SIX, EACH IN THE SLOT IT IS ACTUALLY WORN IN. Corey asked for a full-set effect, so',
         '// a partial set does nothing beyond its stats. Looking a piece up in the wrong slot is',
         '// the mistake the Rogue outfit battery check was written for, and clue_battery.py checks',
         '// this the same way - against the wearpos in the obj config, not against a list here.',
         '[proc,clue_hunter_worn]()(boolean)']
    for pc in P:
        L.append('if (inv_getobj(worn, %s) ! %s) {' % (SLOT[pc['wearpos']], pc['local']))
        L.append('    return(false);')
        L.append('}')
    L += ['return(true);',
          '',
          '// A DOUBLED CASKET IS TWICE THE ROLLS. A casket rolls 2 + random(3) times, so doubling',
          '// the count gives 4, 6 or 8 - exactly two caskets\' worth of the same table, rather than',
          '// a second roll on a different one.',
          '[proc,clue_hunter_doubles]()(boolean)',
          'if (~clue_hunter_worn = false) {',
          '    return(false);',
          '}',
          'if (random(100) < ^clue_hunter_double_pct) {',
          '    return(true);',
          '}',
          'return(false);',
          '',
          '// A SKIPPED STEP advances the trail twice for one hand-in. This is not a new idea in the',
          '// file: ~trail_clue_<tier>_complete already finishes a trail early when progress + 2',
          '// reaches maxsteps and a coin flip agrees, so early completion predates the outfit.',
          '[proc,clue_hunter_skips]()(boolean)',
          'if (~clue_hunter_worn = false) {',
          '    return(false);',
          '}',
          'if (random(100) < ^clue_hunter_skip_pct) {',
          '    return(true);',
          '}',
          'return(false);',
          '',
          '// THE SET COMES OUT OF CASKETS, one roll per piece per casket roll, and only for a piece',
          '// the player does not already have somewhere - inventory, bank or worn. Two reasons: an',
          '// untradeable outfit piece arriving twice is pure clutter, and skipping the ones already',
          '// owned is what makes the rate for a given piece exactly 1/^clue_hunter_drop_denom until',
          '// it is found, which is the number that was asked for.',
          '//',
          '// DELIBERATELY NOT IN THE RARE TABLES. Those reach 1/97 a roll through arithmetic that',
          '// is derived and commented in the reward scripts, and six new entries would move every',
          '// existing rare\'s rate and make that comment wrong.',
          '[proc,clue_hunter_droproll]']
    for pc in P:
        L.append('if (~obj_gettotal(%s) = 0 & random(^clue_hunter_drop_denom) = 0) {' % pc['local'])
        L.append('    inv_add(trail_rewardinv, %s, 1);' % pc['local'])
        L.append('}')
    L.append('')
    return '\n'.join(L)


def render(spec, out_png):
    import ob2render
    from PIL import Image, ImageDraw
    size, cols, pad, lab = 192, 3, 8, 16
    tiles = []
    for p in spec['pieces']:
        path = os.path.join(C, 'models', 'obj', 'obj_%s.ob2' % p['local'])
        if not os.path.exists(path):
            print('  MISSING %s' % path)
            return 1
        m = ob2render.Model(path)
        cam = {}
        for k, arg in (('xan2d', 'xan'), ('yan2d', 'yan'), ('zoom2d', 'zoom'),
                       ('xof2d', 'xof'), ('yof2d', 'yof')):
            if p.get(k) is not None:
                cam[arg] = p[k]
        tiles.append((p['local'], ob2render.render(m, size=size, **cam), m))
        print('  %-24s %d verts, %d faces' % (p['local'], m.vcount, m.fcount))
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new('RGB', (cols * (size + pad) + pad, rows * (size + pad + lab) + pad),
                   (18, 18, 20))
    d = ImageDraw.Draw(im)
    for i, (name, tile, m) in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = pad + c * (size + pad), pad + r * (size + pad + lab)
        im.paste(tile, (x, y))
        d.text((x + 2, y + size + 3), '%s  %dv/%df' % (name, m.vcount, m.fcount),
               fill=(190, 190, 195))
    im.save(out_png)
    print('wrote', out_png)
    return 0


def main():
    spec = json.load(open(SPEC))
    text = build(spec)
    if '--render' in sys.argv:
        return render(spec, sys.argv[sys.argv.index('--render') + 1])
    want = {OUT: text, OUT_RS2: build_rs2(spec)}
    if '--check' in sys.argv:
        bad = []
        for path, body in want.items():
            # Line-ending blind: the repo is LF and text=auto can hand a Windows checkout CRLF.
            have = open(path, newline='').read() if os.path.exists(path) else None
            if have is None or have.replace('\r\n', '\n') != body:
                bad.append(os.path.relpath(path, C))
        if bad:
            print('gencluehunter --check: %s would change' % ', '.join(bad))
            return 1
        print('gencluehunter --check: both generated files are already what this writes')
        return 0
    for path, body in want.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w', newline='').write(body)
        print('wrote %s' % os.path.relpath(path, C))
    return 0


if __name__ == '__main__':
    sys.exit(main())
