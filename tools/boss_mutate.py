#!/usr/bin/env python3
"""Mutation test for tools/boss_battery.py.

A check that cannot fail is worse than no check. Each entry breaks one thing the battery claims to
catch - in a throwaway copy, never in place - and the battery has to go red with the named check
among the ones that fired.

HAS THE ANCHOR UNIQUENESS RULE. A find string matching twice changes something other than what it
names while still coming back red, which looks like coverage and is not.

    python3 tools/boss_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'boss_mutate_work')

SPC = 'tools/bosskillspec.json'
VAR = 'scripts/bosses/configs/boss_kills.varp'
CST = 'scripts/bosses/configs/boss_kills.constant'
ENM = 'scripts/bosses/configs/boss_kills.enum'
IFF = 'scripts/bosses/interfaces/boss_kills.if'
RS2 = 'scripts/bosses/scripts/boss_kills.rs2'
DTH = 'scripts/skill_combat/scripts/npc/npc_death.rs2'
QL = 'scripts/interfaces/questlist.if'

MUTS = [
 # ---- which fourteen
 # 12 when this was written; two more bosses have a counter since.
 (CST, '^boss_kills_count = 14', '^boss_kills_count = 13',
  '1 ^boss_kills_count is counted from the spec rather than typed'),
 (CST, '^boss_kills_none = -1', '^boss_kills_none = 0',
  '1 and ^boss_kills_none is -1'),
 (SPC, '"npc": "mole_giant"', '"npc": "mole_giant_deluxe"',
  '1 every npc the spec names is a real npc'),
 # THE NAME DRIFT this battery exists to catch: a window that disagrees with the monster.
 (SPC, '"name": "Giant Mole"', '"name": "The Giant Mole"',
  "1 each boss's display name is its own npc record's name="),
 (SPC, '"npc": "kalphite_flyingqueen"', '"npc": "kalphite_queen"',
  '1 the Kalphite Queen is counted on the FLYING form'),

 # ---- the varps, and protect=no above all
 (VAR, '[boss_kc_mole]\nscope=perm\nprotect=no', '[boss_kc_mole]\nscope=perm',
  '2 and every one is protect=no'),
 (VAR, '[boss_kc_kbd]\nscope=perm', '[boss_kc_kbd]\nscope=temp',
  '2 every one is scope=perm'),
 (VAR, '[boss_kc_jad]', '[boss_kc_jadx]',
  '2 the spec names fourteen bosses with fourteen distinct keys'),
 (VAR, '[boss_kc_kq]\nscope=perm\nprotect=no',
       '[boss_kc_kq]\nscope=perm\nprotect=no\ntransmit=yes',
  '2 none is transmitted'),

 # ---- the two tables
 (ENM, 'val=chaoselemental,6', 'val=chaoselemental,7',
  "3 boss_kill_name maps each slot to that boss's name"),
 (ENM, 'default=-1', 'default=0',
  '3 ...and everything else in the game answers -1'),
 (ENM, 'val=11,Giant Mole', 'val=11,Giant mole',
  "3 boss_kill_name maps each slot to that boss's name"),

 # ---- credit, and counting once
 # THE GUARD THAT WENT MISSING FOR A BUILD, and the build went green with it gone.
 (RS2, 'if (npc_findhero = ^false) {\n    return;\n}\n', '',
  '4 the first thing ~boss_kill_record does is refuse a kill with no hero'),
 (RS2, 'if (npc_findhero = ^false) {',
       'if (finduid(%npc_aggressive_player) = false) {',
  '4 ...and it does NOT use %npc_aggressive_player'),
 (RS2, 'queue(boss_kill_announce, 0, $slot);\n', '',
  '4 the message is queued exactly once per counted kill'),
 # CROSS-WIRING: slot 3 adds to slot 4's counter. Nothing errors, and every count is wrong.
 (RS2, 'case 3 : %boss_kc_zilyana = add(%boss_kc_zilyana, 1);',
       'case 3 : %boss_kc_kreearra = add(%boss_kc_kreearra, 1);',
  '4 and every slot increments ITS OWN counter, by one'),
 (RS2, 'case 5 : %boss_kc_kq = add(%boss_kc_kq, 1);',
       'case 5 : %boss_kc_kq = add(%boss_kc_kq, 2);',
  '4 and every slot increments ITS OWN counter, by one'),
 (RS2, 'switch_int ($slot) {\n    case 0 : %boss_kc_jad',
       'switch_int ($slot) {\n    case default : return;\n    case 0 : %boss_kc_jad',
  '4 ...with a default case, and it is the LAST one'),
 (RS2, 'case 9 : return(%boss_kc_dag_prime);', 'case 9 : return(%boss_kc_dag_rex);',
  '4 the read-back switch reads the same counters, slot for slot'),
 (RS2, 'case default : return(0);', 'case default : return(1);',
  "4 ...and an unknown slot reads as no kills rather than as the first boss's"),

 # ---- the hook
 (DTH, '~boss_kill_record;\n', '',
  '5 ~boss_kill_record is called exactly once from npc_death.rs2'),
 (DTH, '~barrows_potential;\n', '~barrows_potential;\n~boss_kill_record;\n',
  '5 ~boss_kill_record is called exactly once from npc_death.rs2'),

 # ---- the window and its one row
 (IFF, 'text=Dagannoth Rex', 'text=Dagganoth Rex',
  '6 each row is labelled with its own boss'),
 (IFF, '[count7]\ntype=text', '[count7x]\ntype=text',
  '6 each row is labelled with its own boss'),
 (IFF, 'buttontype=close', 'buttontype=normal',
  '6 there is a close button, and it is buttontype=close'),
 (RS2, '$total = add($total, ~boss_kills_count(boss_kills:count4, ~boss_kill_get(4)));', '',
  '6 ...and pushes every count into its own box'),
 (RS2, '~boss_kills_count(boss_kills:count5, ~boss_kill_get(5))',
  '~boss_kills_count(boss_kills:count5, ~boss_kill_get(6))',
  '6 ...and pushes every count into its own box'),
 (RS2, 'if_openmain(boss_kills);', 'if_close;',
  '6 the opener opens the window'),
 (RS2, '[proc,boss_kills_open]', '[if_button,questlist:boss_kills] ~boss_kills_open;\n\n[proc,boss_kills_open]',
  '6 the quest list has no "Boss kill counts" row'),
 (SPC, '"key": "mole"', '"key": "molerat"',
  '7 tools/genbosskills.py --check'),
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
            print('  SKIP (pattern not found) %-40s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        if n > 1:
            print('  SKIP (matches %d times, not unique) %-30s %s' % (n, os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'boss_battery.py')],
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
        print('  %-5s %-72s %s' % (state, why, note))
    print()
    if loose:
        print('%d caught by a check other than the one named' % loose)
    print('%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
