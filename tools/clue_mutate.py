#!/usr/bin/env python3
"""Mutation test for tools/clue_battery.py.

A check that cannot fail is worse than no check: it reads as coverage and is not. Each entry breaks
one thing the battery claims to catch - in a throwaway copy of the tree, never in place - and the
battery has to go red, with the check named in the entry among the ones that fired.

THIS HARNESS HAS THE ANCHOR UNIQUENESS RULE, which tools/follower_mutate.py and
tools/gamemode_mutate.py have and the five older ones do not. A find string matching more than once
is a mutation that changes something other than what it names - four of them did exactly that in
one round of the pet work, silently - so a non-unique pattern is a SKIP and a failure here rather
than a quiet first-match replace.

    python3 tools/clue_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'clue_mutate_work')

OBJ = 'scripts/minigames/game_trail/configs/clue_hunter.obj'
RS2 = 'scripts/minigames/game_trail/scripts/clue_hunter.rs2'
HLP = 'scripts/minigames/game_trail/scripts/trail_clue_helper.rs2'
CST = 'scripts/minigames/game_trail/configs/trail.constant'
SPC = 'tools/cluehunterspec.json'
EZ = 'scripts/minigames/game_trail/scripts/easy/trail_clue_easy_reward.rs2'
MD = 'scripts/minigames/game_trail/scripts/medium/trail_clue_medium_reward.rs2'
HD = 'scripts/minigames/game_trail/scripts/hard/trail_clue_hard_reward.rs2'

MUTS = [
 # (file, find, replace, the check that must go red)
 # ---- the pieces themselves
 (OBJ, 'param=magicattack,-6', 'param=magicattack,-5',
  "1 every piece's bonuses are the item table's, signed"),
 # THE SIGN TRAP, put back exactly as it would arrive from a careless read.
 (OBJ, 'param=magicattack,-6', 'param=magicattack,4294967290',
  '1 and no bonus on any piece is an unconverted unsigned int'),
 # A SIGN FLIP, which is a different mistake from an off-by-one and worth its own entry. It is
 # named at the equality check deliberately: the guard beside that check - "the negatives really
 # are negative" - can only go red if EVERY negative in the file disappears, and any edit that
 # does that also breaks equality with the spec. So the guard has no mutation of its own, and
 # saying so here is better than pointing one at it and reading "caught, but by".
 (OBJ, 'param=magicattack,-6\nparam=rangeattack,-2', 'param=magicattack,6\nparam=rangeattack,2',
  "1 every piece's bonuses are the item table's, signed"),
 (OBJ, '[clue_hunter_cloak]', '[clue_hunter_cape]',
  '1 the generated config holds exactly the six pieces the spec names'),
 (OBJ, 'model=obj_clue_hunter_boots\n', 'model=obj_clue_hunter_sandals\n',
  '1 and every model they name is in model.pack AND on disk'),
 (OBJ, 'wearpos=feet', 'wearpos=hands',
  "1 and every wearpos row is the cache's"),
 (OBJ, 'tradeable=no\nweight=700g', 'weight=700g',
  '1 all six are untradeable'),
 (OBJ, 'iop2=Wear\ncost=1\nmembers=yes\ntradeable=no\nweight=700g',
       'iop2=Wear\niop5=Destroy\ncost=1\nmembers=yes\ntradeable=no\nweight=700g',
  '1 and none carries an inventory op 5'),

 # ---- the full-set test
 (RS2, 'if (inv_getobj(worn, ^wearpos_feet) ! clue_hunter_boots) {',
       'if (inv_getobj(worn, ^wearpos_hands) ! clue_hunter_boots) {',
  '3 all six are looked for, each in the slot its own obj record gives it'),
 (RS2, 'if (inv_getobj(worn, ^wearpos_back) ! clue_hunter_cloak) {\n    return(false);\n}\n',
        '',
  '3 all six are looked for, each in the slot its own obj record gives it'),
 (RS2, 'if (inv_getobj(worn, ^wearpos_hands) ! clue_hunter_gloves) {\n    return(false);\n}',
        'if (inv_getobj(worn, ^wearpos_hands) ! clue_hunter_gloves) {\n    return(true);\n}',
  '3 and a missing piece fails the whole test'),

 # ---- the two effects
 (RS2, 'if (random(100) < ^clue_hunter_double_pct) {',
        'if (random(100) < 10) {',
  '4 ...and the chance is ^clue_hunter_double_pct rather than a number written into the script'),
 (RS2, 'if (random(100) < ^clue_hunter_skip_pct) {',
        'if (random(100) < 10) {',
  '4 ...and the chance is ^clue_hunter_skip_pct rather than a number written into the script'),
 # The worn test moved AFTER the roll, which is the "a lock after the window opens" mistake in
 # another shape: a partial set would still burn a draw and, worse, the proc would return true.
 (RS2, '[proc,clue_hunter_doubles]()(boolean)\nif (~clue_hunter_worn = false) {\n    return(false);\n}\n',
        '[proc,clue_hunter_doubles]()(boolean)\n',
  '4 ~clue_hunter_doubles asks for the full set BEFORE it rolls'),
 (RS2, '[proc,clue_hunter_skips]()(boolean)\nif (~clue_hunter_worn = false) {\n    return(false);\n}\n',
        '[proc,clue_hunter_skips]()(boolean)\n',
  '4 ~clue_hunter_skips asks for the full set BEFORE it rolls'),

 # ---- the drop
 (RS2, '[proc,clue_hunter_droproll]\n',
        '[proc,clue_hunter_droproll]\nif (~clue_hunter_worn = false) {\n    return;\n}\n',
  '5 the drop roll does NOT ask whether the outfit is worn'),
 (RS2, 'if (~obj_gettotal(clue_hunter_garb) = 0 & random(^clue_hunter_drop_denom) = 0) {',
        'if (random(^clue_hunter_drop_denom) = 0) {',
  '5 each piece is rolled only when the player has none of it anywhere'),
 (RS2, 'inv_add(trail_rewardinv, clue_hunter_trousers, 1);', 'mes("");',
  '5 and every one goes into the reward inv the casket already pays into'),

 # ---- the hooks
 (HLP, 'if (~clue_hunter_skips = true) {', 'if (false = true) {',
  '6 the skip is in ~trail_clue_progress'),
 (HLP, '    %trail_progress = setbit_range_toint(%trail_progress, calc(~get_trail_progress($tier) + 1), $lo, $hi);\n    mes(',
        '    mes(',
  '6 ...and it advances the counter a SECOND time rather than replacing the first'),
 (EZ, '$rolls = calc($rolls * 2);', '$rolls = calc(8);',
  '6 ...and it doubles the count rather than setting it, so a easy casket rolls 4-8 instead of 2-4'),
 (MD, '    ~clue_hunter_droproll;\n', '',
  '6 ...and the piece drop is INSIDE the roll loop, so it is once per roll as asked (medium)'),
 # THE SHAPE has to change, not just the neighbourhood: the first version of this entry added a
 # redundant `$rolls = calc($rolls);` line after the declaration, which left the declaration - and
 # therefore the regex that reads the roll count - exactly where it was. It survived, correctly.
 (HD, 'def_int $rolls = calc(4 + random(3));', 'def_int $rolls = 5;',
  "6 hard's casket roll count can be read out of its reward proc"),

 # ---- the existing tables
 (EZ, 'case 26 : inv_add(trail_rewardinv, willow_longbow, 1);',
       'case 26 : inv_add(trail_rewardinv, willow_longbow, 1);\n'
       '    case 27 : inv_add(trail_rewardinv, clue_hunter_boots, 1);',
  "7 easy's normal table still has exactly as many cases as its own random()"),
 # random(34) was the hard rare table's bound until 2026-10-04 replaced it with Old School's own
 # 158. The bound to bend is the switch's own, not the random(8) that branches into the elite and
 # master table above it.
 (HD, 'def_int $random = random(158);', 'def_int $random = random(159);',
  "7 hard's rare table still has exactly as many cases as its own random()"),

 # ---- the spec's arithmetic and the constants
 (SPC, '"expected_rolls_for_the_set": 1837', '"expected_rolls_for_the_set": 1800',
  '8 the rolls-for-the-set figure is 750 x H(6) recomputed and truncated'),
 (SPC, '"easy": 612', '"easy": 600',
  "8 and each tier's casket figure divides that by the roll count read out of THAT tier's"),
 (CST, '^clue_hunter_drop_denom = 750', '^clue_hunter_drop_denom = 700',
  '8 ^clue_hunter_drop_denom is 750 in trail.constant, the same as in the spec'),

 # ---- the scroll box cap, which is off by a sentinel and not by a big number
 (CST, '^trail_easy_stackcap = ^trail_stackcap_none', '^trail_easy_stackcap = 2',
  '9 ^trail_easy_stackcap is ^trail_stackcap_none'),
 (CST, '^trail_stackcap_none = -1', '^trail_stackcap_none = 0',
  '9 ...and the sentinel is -1'),
 (CST, '^clue_hunter_pieces = 6', '^clue_hunter_pieces = 5',
  '8 and ^clue_hunter_pieces is 6, counted from the spec rather than typed'),
 (SPC, '"casket_effect": null', '"casket_effect": "doubles it"',
  "2 the spec records that OSRS's clue hunter outfit has NO casket effect"),
 (SPC, '"full_set_only": true', '"full_set_only": false',
  '2 ...and that the effects are full-set only'),
 (OBJ, 'name=Clue hunter cloak', 'name=Clue hunter cape',
  '9 tools/gencluehunter.py --check'),
]


def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    fails = loose = 0
    for path, find, repl, why in MUTS:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        n = raw.count(f)
        if n == 0:
            print('  SKIP (pattern not found) %-44s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        # THE UNIQUENESS RULE. A pattern matching twice means this entry silently changes something
        # other than what it claims to, and the run still comes back red - which is worse than a
        # missing mutation because it looks like coverage.
        if n > 1:
            print('  SKIP (pattern matches %d times, not unique) %-26s %s'
                  % (n, os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'clue_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'
            fails += 1
        elif onpoint:
            note = 'caught by its own check'
            if len(fired) > 1:
                note += ' (and %d other%s)' % (len(fired) - 1, '' if len(fired) == 2 else 's')
            state = 'red'
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:60] if fired else 'a non-zero exit with no check named, which is a '
                                            'crash and not a catch')
            loose += 1
        print('  %-5s %-70s %s' % (state, why, note))
    print()
    if loose:
        print('%d caught by a check other than the one named - see the note beside each' % loose)
    print('%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
