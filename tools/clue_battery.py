#!/usr/bin/env python3
"""Battery for the clue hunter outfit and the three things it does.

Everything is PARSED OUT of the delivered files - the bonuses from the obj config, the effects from
the scripts that hold them, the roll counts from the three reward procs - so a change to one of
them cannot pass a check still asserting the old value. The numbers on the right-hand side are the
OSRS item table's, through tools/cluehunterspec.json, except the three Corey chose, which the spec
marks as departures.

Section 10 is treasure trails themselves: clues and caskets named by tier, the scroll boxes, and one
trail per tier. What those do at run time - a second clue arriving as a box, the stack limit, opening
a box once the trail is done - is exercised against the real engine by tools/clue_live_battery.py.

    python3 tools/clue_battery.py
"""
import json, os, re, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1

def before(hay, a, b):
    """a appears before b, False rather than an exception when either is missing."""
    return a in hay and b in hay and hay.index(a) < hay.index(b)

def nocomment(txt):
    """The code with // comments and string bodies removed.

    Every battery in this tree that did not have one has had a check pass on its own comment at
    least once. This one starts with it.
    """
    return '\n'.join(re.sub(r'"[^"]*"', '""', l).split('//')[0] for l in txt.split('\n'))

def pack(name):
    out = {}
    for line in read('pack/' + name).split('\n'):
        if '=' in line:
            i, n = line.split('=', 1)
            out[n.strip()] = int(i)
    return out

def blocks(txt):
    out, cur = {}, None
    for line in txt.split('\n'):
        line = line.split('//')[0].strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            cur = {}
            out[line[1:-1]] = cur
            continue
        if cur is None or '=' not in line:
            continue
        k, v = line.split('=', 1)
        cur.setdefault(k, []).append(v)
    return out

def params(f):
    out = {}
    for v in f.get('param', []):
        k, _, n = v.partition(',')
        if n.lstrip('-').isdigit():
            out[k] = int(n)
    return out

SPEC = json.loads(read('tools/cluehunterspec.json'))
OBJP, MODELP = pack('obj.pack'), pack('model.pack')
CH = blocks(read('scripts/minigames/game_trail/configs/clue_hunter.obj'))
RS2 = read('scripts/minigames/game_trail/scripts/clue_hunter.rs2')
HELPER = read('scripts/minigames/game_trail/scripts/trail_clue_helper.rs2')
CONST = read('scripts/minigames/game_trail/configs/trail.constant')
TIERS = {t: read('scripts/minigames/game_trail/scripts/%s/trail_clue_%s_reward.rs2' % (t, t))
         for t in ('easy', 'medium', 'hard')}
PIECES = SPEC['pieces']
NAMES = [p['local'] for p in PIECES]

print('1. the six pieces are real items with OSRS\'s own numbers')
check(sorted(CH) == sorted(NAMES),
      'the generated config holds exactly the six pieces the spec names: %s'
      % (sorted(set(CH) ^ set(NAMES)) or 'exactly the six'))
check(all(n in OBJP for n in NAMES),
      'each has an id in pack/obj.pack: %s' % ([n for n in NAMES if n not in OBJP] or 'all six'))
_mm = []
for n, f in CH.items():
    for k in ('model', 'manwear', 'womanwear', 'manhead', 'womanhead'):
        for v in f.get(k, []):
            mdl = v.split(',')[0]
            if mdl not in MODELP or not os.path.exists(
                    os.path.join(C, 'models/obj', mdl + '.ob2')):
                _mm.append('%s/%s' % (n, mdl))
check(not _mm, 'and every model they name is in model.pack AND on disk: %s' % (_mm[:3] or 'all 22'))
_bad = [p['local'] for p in PIECES if params(CH[p['local']]) != p['bonuses']]
check(not _bad,
      "every piece's bonuses are the item table's, signed: %s" % (_bad or 'all six agree'))

# THE SIGN TRAP, checked as a property and not just by equality. The cache stores -6 as
# 4294967290; a careless read writes that straight into a config, and param=magicattack,4294967290
# is not a small mistake - it is the largest magic attack bonus in the game. No real bonus in this
# build is anywhere near a thousand, so anything that big is an unsigned int that was never
# converted.
_huge = ['%s %s=%d' % (n, k, v) for n, f in CH.items() for k, v in params(f).items() if abs(v) > 1000]
check(not _huge,
      'and no bonus on any piece is an unconverted unsigned int - the cache stores the helm\'s -6 '
      'magic attack as 4294967290, and nothing here is within a thousand of that: %s'
      % (_huge[:2] or 'all in range'))
check(any(v < 0 for f in CH.values() for v in params(f).values()),
      '...while the negatives really are negative, so the conversion happened rather than the '
      'fields being dropped')
_wp = [p['local'] for p in PIECES
       if CH[p['local']].get('wearpos', [None])[0] != p['wearpos']
       or CH[p['local']].get('wearpos2', [None])[0] != p['wearpos2']]
check(not _wp, 'and every wearpos row is the cache\'s: %s' % (_wp or 'all six'))
check(all(f.get('tradeable') == ['no'] for f in CH.values()),
      'all six are untradeable, which is how this fork ships an earned set')
check(not [n for n, f in CH.items() if 'iop5' in f],
      'and none carries an inventory op 5 - OSRS puts Destroy there and this build puts Drop, so '
      'carrying OSRS\'s would take Drop off the item')

print('2. what OSRS actually does, recorded so nobody reads the effects as canon')
_o = SPEC['what_osrs_actually_does']
check(_o['casket_effect'] is None and _o['step_effect'] is None,
      "the spec records that OSRS's clue hunter outfit has NO casket effect and NO step effect - "
      'every effect in this round is a departure')
check('departures' in SPEC and SPEC['departures'].get('full_set_only') is True,
      '...and that the effects are full-set only, which is what was asked for')

print('3. the full-set test looks in the slot each piece is actually worn in')
_worn = nocomment(RS2).split('[proc,clue_hunter_worn]', 1)[1].split('\n[', 1)[0] \
    if '[proc,clue_hunter_worn]' in nocomment(RS2) else ''
SLOTC = {'hat': '^wearpos_hat', 'torso': '^wearpos_torso', 'legs': '^wearpos_legs',
         'hands': '^wearpos_hands', 'feet': '^wearpos_feet', 'back': '^wearpos_back'}
_sbad = []
for p in PIECES:
    # THE SLOT COMES FROM THE OBJ CONFIG, not from a list in this file. That is the difference
    # between checking the code and restating it: if the config's wearpos moved, this moves too.
    slot = SLOTC[CH[p['local']].get('wearpos', ['?'])[0]]
    want = 'if (inv_getobj(worn, %s) ! %s) {' % (slot, p['local'])
    if want not in _worn:
        _sbad.append(p['local'])
check(not _sbad,
      'all six are looked for, each in the slot its own obj record gives it: %s'
      % (_sbad or 'all six'))
check(_worn.count('return(false);') == len(PIECES) and _worn.count('return(true);') == 1,
      'and a missing piece fails the whole test - %d early exits for %d pieces and one success'
      % (_worn.count('return(false);'), len(PIECES)))

print('4. both effects are full-set only, read their constants, and never share a draw')
for proc, const in (('clue_hunter_doubles', '^clue_hunter_double_pct'),
                    ('clue_hunter_skips', '^clue_hunter_skip_pct')):
    body = nocomment(RS2).split('[proc,%s]' % proc, 1)[1].split('\n[', 1)[0] \
        if '[proc,%s]' % proc in nocomment(RS2) else ''
    check(before(body, '~clue_hunter_worn = false', const),
          '~%s asks for the full set BEFORE it rolls, so a partial set never draws at all' % proc)
    check(const in body and not re.search(r'random\(100\) < \d', body),
          '...and the chance is %s rather than a number written into the script' % const)
check(nocomment(RS2).count('random(100)') == 2,
      'the two effects roll separately - two draws, not one shared between them, which is what '
      '"one roll each" meant: %d draws' % nocomment(RS2).count('random(100)'))

print('5. the pieces drop from caskets, and the drop does not need the set')
_drop = nocomment(RS2).split('[proc,clue_hunter_droproll]', 1)[1].split('\n[', 1)[0] \
    if '[proc,clue_hunter_droproll]' in nocomment(RS2) else ''
check('~clue_hunter_worn' not in _drop,
      'the drop roll does NOT ask whether the outfit is worn, for the obvious reason')
_dbad = [p['local'] for p in PIECES
         if 'if (~obj_gettotal(%s) = 0 & random(^clue_hunter_drop_denom) = 0) {' % p['local']
         not in _drop]
check(not _dbad,
      'each piece is rolled only when the player has none of it anywhere - ~obj_gettotal is '
      'inventory, bank and worn - so an untradeable piece never arrives twice: %s'
      % (_dbad or 'all six'))
check(_drop.count('inv_add(trail_rewardinv,') == len(PIECES),
      'and every one goes into the reward inv the casket already pays into: %d of %d'
      % (_drop.count('inv_add(trail_rewardinv,'), len(PIECES)))
check(not re.search(r'random\(\d{2,}\)', _drop),
      'the denominator is a constant here too, not a bare number')

print('6. the hooks: one for the skip, three for the double and the drop')
_prog = nocomment(HELPER).split('[proc,trail_clue_progress]', 1)[1].split('\n[', 1)[0] \
    if '[proc,trail_clue_progress]' in nocomment(HELPER) else ''
check('~clue_hunter_skips = true' in _prog,
      'the skip is in ~trail_clue_progress, which every tier goes through - so one hook covers '
      'easy, medium and hard, and a fourth tier would be covered too')
check(_prog.count('setbit_range_toint') == 2,
      '...and it advances the counter a SECOND time rather than replacing the first, which is '
      'what a skipped step is: %d advances' % _prog.count('setbit_range_toint'))
_elsewhere = []
for _root, _dirs, _files in os.walk(os.path.join(C, 'scripts')):
    for _fn in _files:
        if not _fn.endswith('.rs2'):
            continue
        rel = os.path.relpath(os.path.join(_root, _fn), C)
        if '~clue_hunter_skips' in nocomment(read(rel)) and 'clue_hunter.rs2' not in rel:
            _elsewhere.append(os.path.basename(rel))
check(_elsewhere == ['trail_clue_helper.rs2'],
      'and it is hooked in exactly one place, so no tier can be missed or done twice: %s'
      % _elsewhere)

ROLLS = {}
for t, txt in TIERS.items():
    code = nocomment(txt)
    m = re.search(r'def_int \$rolls = calc\((\d+) \+ random\((\d+)\)\);', code)
    check(m is not None, "%s's casket roll count can be read out of its reward proc" % t)
    if not m:
        continue
    ROLLS[t] = (int(m.group(1)), int(m.group(2)))
    body = code.split('[proc,trail_clue_%s_reward]' % t, 1)[1].split('\n[', 1)[0]
    check(before(body, '$rolls = calc(%s + random(%s))' % m.groups(), '~clue_hunter_doubles'),
          '...and the double is asked AFTER the count is worked out, which is the only place it '
          'can multiply anything (%s)' % t)
    check('$rolls = calc($rolls * 2);' in body,
          '...and it doubles the count rather than setting it, so a %s casket rolls %d-%d instead '
          'of %d-%d' % (t, ROLLS[t][0] * 2, (ROLLS[t][0] + ROLLS[t][1] - 1) * 2,
                        ROLLS[t][0], ROLLS[t][0] + ROLLS[t][1] - 1))
    check(before(body, '~clue_hunter_droproll', '$roll = calc($roll + 1)'),
          '...and the piece drop is INSIDE the roll loop, so it is once per roll as asked (%s)' % t)

print('7. the existing casket tables are untouched')
_tabs = {'easy': 27, 'medium': None, 'hard': None}
for t, txt in TIERS.items():
    code = nocomment(txt)
    for kind in ('normal', 'rare'):
        body = code.split('[proc,trail_clue_%s_%s]' % (t, kind), 1)[1].split('\n[', 1)[0] \
            if '[proc,trail_clue_%s_%s]' % (t, kind) in code else ''
        m = re.search(r'def_int \$random = random\((\d+)\);', body)
        cases = len(re.findall(r'^\s*case \d+ :', body, re.M))
        check(m is not None and cases == int(m.group(1)),
              "%s's %s table still has exactly as many cases as its own random() - %s -, so "
              'nothing was added to it and no case was orphaned'
              % (t, kind, '%d of %s' % (cases, m.group(1)) if m else 'unreadable'))
        check(not [n for n in NAMES if n in body],
              '...and no clue hunter piece is in it (%s %s), because the pieces have their own '
              'roll and the 1/97 arithmetic in the comment above it stays true' % (t, kind))

print('8. the spec\'s own arithmetic, recomputed')
src = SPEC['source']
# 750 x H(6) IS EXACTLY 1837.5, which is the one case where recomputing a figure needs a stated
# convention or the check argues with the spec about half a roll. It was an integer when the
# denominator was 1,500 - 1500 x H(6) = 3675 - and halving it to land the set at about 600 caskets
# rather than 1,200 put the .5 in. The spec truncates and so does this, because a figure for "how
# many rolls the set takes" should not round up to a roll that has not happened; the three casket
# figures below divide the truncated number, so all four agree.
H = sum(1.0 / k for k in range(1, len(PIECES) + 1))
want_rolls = int(src['denominator'] * H)
check(src['expected_rolls_for_the_set'] == want_rolls,
      'the rolls-for-the-set figure is %d x H(%d) recomputed and truncated, not a remembered '
      'number: %d against %d'
      % (src['denominator'], len(PIECES), src['expected_rolls_for_the_set'], want_rolls))
_cbad = []
for t, (base, span) in ROLLS.items():
    avg = base + (span - 1) / 2.0
    want = round(want_rolls / avg)
    if src['expected_caskets_for_the_set'].get(t) != want:
        _cbad.append('%s: spec %s, %d/%.1f = %d'
                     % (t, src['expected_caskets_for_the_set'].get(t), want_rolls, avg, want))
check(not _cbad,
      "and each tier's casket figure divides that by the roll count read out of THAT tier's "
      'reward proc - the three are not the same: %s' % (_cbad or src['expected_caskets_for_the_set']))
check(src['expected_caskets_for_the_set'].get('easy') in range(550, 675),
      '...and the easy figure is the "about 600 caskets" that was asked for: %s'
      % src['expected_caskets_for_the_set'].get('easy'))
for c, v in (('^clue_hunter_double_pct', SPEC['departures']['double_casket_pct']),
             ('^clue_hunter_skip_pct', SPEC['departures']['skip_step_pct']),
             ('^clue_hunter_drop_denom', src['denominator'])):
    check(re.search(r'^%s = %d$' % (re.escape(c), v), CONST, re.M) is not None,
          '%s is %d in trail.constant, the same as in the spec' % (c, v))
check(re.search(r'^\^clue_hunter_pieces = %d$' % len(PIECES), CONST, re.M) is not None,
      'and ^clue_hunter_pieces is %d, counted from the spec rather than typed' % len(PIECES))

print('9. the generator reproduces what is checked in')
r = subprocess.run([sys.executable, os.path.join(C, 'tools/gencluehunter.py'), '--check'],
                   capture_output=True, text=True, cwd=C)
check(r.returncode == 0,
      'tools/gencluehunter.py --check: both generated files are already what it writes, so '
      'nothing here was hand-edited%s' % ('' if r.returncode == 0 else ': ' + r.stdout.strip()[:200]))

print('10. tier names, scroll boxes, and one trail per tier')
ALLOBJ = blocks(read('scripts/_unpack/377/all.obj'))
_nbad = []
for n, f in ALLOBJ.items():
    m = re.match(r'trail_(clue|casket)_(easy|medium|hard)$', (f.get('category') or [''])[0])
    if m:
        want = '%s (%s)' % ('Clue scroll' if m.group(1) == 'clue' else 'Casket', m.group(2))
        if f.get('name') != [want]:
            _nbad.append('%s=%s' % (n, f.get('name')))
check(not _nbad, 'every clue scroll and casket says its tier in its name, e.g. "Casket (easy)": %s'
      % (_nbad[:3] or 'all of them'))
BOX = blocks(read('scripts/minigames/game_trail/configs/scroll_box.obj'))
_bbad = [t for t in ('easy', 'medium', 'hard')
         if BOX.get('trail_scrollbox_' + t, {}).get('name') != ['Scroll box (%s)' % t]
         or BOX['trail_scrollbox_' + t].get('stackable') != ['yes']
         or BOX['trail_scrollbox_' + t].get('category') != ['trail_scrollbox']
         or 'trail_tier,^trail_tier_%s' % t not in BOX['trail_scrollbox_' + t].get('param', [])]
check(not _bbad, 'three scroll boxes, stackable, each carrying its own tier: %s' % (_bbad or 'all three'))
check(all(n in OBJP for n in BOX), 'and each has an id in pack/obj.pack')
# NO TIER HAS A LIMIT, by the owner's call on 2026-10-02 - "drop the limit on the scroll box so
# you can get however many you want" (c697ae9e). This check asked for the wiki's base 2 and went
# red that day. Boxes stack and are untradeable, so a backlog costs one inventory slot per tier
# and cannot be sold; there is nothing for a cap to protect. What still has to be true is the
# MECHANISM, because the cap is turned off by a sentinel rather than by a big number: every tier
# names ^trail_stackcap_none, and every place that compares against a cap tests for that sentinel
# by name, so setting a tier back to a real number makes its limit work again, message and all.
for t in ('easy', 'medium', 'hard'):
    check(re.search(r'^\^trail_%s_stackcap = \^trail_stackcap_none$' % t, CONST, re.M) is not None,
          '^trail_%s_stackcap is ^trail_stackcap_none - no limit, as the owner asked' % t)
check(re.search(r'^\^trail_stackcap_none = -1$', CONST, re.M) is not None,
      '...and the sentinel is -1, which no count can reach by accident')
_capsites = []
for _r, _d, _f in os.walk(os.path.join(C, 'scripts')):
    for _fn in _f:
        if _fn.endswith('.rs2') and '^trail_stackcap_none' in nocomment(
                open(os.path.join(_r, _fn), newline='').read().replace('\r\n', '\n')):
            _capsites.append(_fn)
check(len(_capsites) >= 2,
      'and the places that compare against a cap test for the sentinel by name, so a real number '
      'put back works again: %s' % ', '.join(sorted(_capsites)))
_calls = {t: nocomment(txt).count('~trail_complete(^trail_tier_%s);' % t) for t, txt in TIERS.items()}
check(all(v == 1 for v in _calls.values()),
      'each reward proc ends its trail through ~trail_complete with its own tier, once: %s' % _calls)
_status = []
for _root, _dirs, _files in os.walk(os.path.join(C, 'scripts')):
    for _fn in _files:
        if _fn.endswith('.rs2'):
            rel = os.path.relpath(os.path.join(_root, _fn), C)
            for l in nocomment(read(rel)).split('\n'):
                if re.search(r'%trail_status = ', l) and not re.search(r', 5, 8\);', l):
                    _status.append('%s: %s' % (_fn, l.strip()))
check(_status == ['trail_clue_helper.rs2: %trail_status = clearbit_range(%trail_status, 0, 4);'],
      "nothing writes %%trail_status's old step bits but the one-time move in ~trail_login: %s" % _status)

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
