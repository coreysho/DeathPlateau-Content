#!/usr/bin/env python3
"""Mutation test for tools/combat_battery.py and for rs2check's rules 19, 21 and 22.

Every entry breaks one of the 2026-09-21 play fixes and expects the named check to go red. Entries
whose name ends in (rs2check) are run against tools/rs2check.py instead of the battery, because the
general case of each bug lives in a rule rather than in a check here.

    python3 tools/combat_mutate.py              # all of them
    python3 tools/combat_mutate.py "autocast"   # just the ones whose name contains that
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'combat_mutate_work')

AUTO = 'scripts/skill_combat/scripts/player/auto_cast.rs2'
ROWS = 'scripts/skill_combat/configs/magic/magic_combat_spells.dbrow'
ALLOBJ = 'scripts/_unpack/377/all.obj'
OBSIDIAN = 'scripts/skill_combat/configs/melee/obsidian.obj'
SECATEURS = 'scripts/general/configs/osrs_items.obj'
IBANPVM = 'scripts/skill_combat/scripts/player/spells/scripts/ibans_blast.rs2'
STAFFIF = 'scripts/skill_combat/interfaces/magic/combat_staff_2.if'
ROCKSKIN = 'scripts/skill_prayer/scripts/prayers/rockskin.rs2'
CLARITY = 'scripts/skill_prayer/scripts/prayers/clarity.rs2'

MUTS = [
 # ---- 1, the autocast arming: the papercut behind "autocasting fire wave" then a melee swing
 (AUTO, '    %autocast_set = 1;\n', '',
  '1 autocast is turned ON by choosing, the way OSRS does it'),
 (AUTO, '''    %autocast_set = 1;
    if_settext''', '''    if_settext''',
  '1 autocast is turned ON by choosing, the way OSRS does it'),
 # arming BEFORE the requirement check, so a spell you cannot cast still lights the lamp
 (AUTO, '''    def_dbrow $spell_data = ~get_spell_data($spell);
    if (~check_spell_requirements($spell_data) = false) {
        return;
    }''', '''    %autocast_set = 1;
    def_dbrow $spell_data = ~get_spell_data($spell);
    if (~check_spell_requirements($spell_data) = false) {
        return;
    }''',
  '1 after the requirement check, so a spell you cannot cast does not arm it'),
 # the lamp and the state disagreeing - the button would read a bit nothing writes
 (STAFFIF, 'script1op1=testbit,lastcastspell,0', 'script1op1=testbit,lastcastspell,1',
  '1 autocast_set is one bit of lastcastspell'),

 # ---- 2, the five rows. Removing one is the exact bug that was reported.
 (ROWS, 'data=spell,^iban_blast\n', 'data=spell,^iban_blast_gone\n',
  '2 iban_blast has a row under its own spell id - this is the whole bug'),
 (ROWS, 'data=spell,^saradomin_strike\n', 'data=spell,^saradomin_strike_gone\n',
  '2 saradomin_strike has a row under its own spell id - this is the whole bug'),
 # ...and rs2check is what finds it in a repo nobody has cast anything in
 (ROWS, 'data=spell,^crumble_undead\n', 'data=spell,^crumble_undead_gone\n',
  '2 a spell script asking for a row that is not there (rs2check)'),
 # a number that is not the wiki's
 # ANCHORED ON THE ROW. magic_dart is also level 50 for 30xp and sits ABOVE iban_blast in the
 # file, so the first version of this mutation edited the wrong spell and the battery - which does
 # not check magic_dart - stayed green.
 (ROWS, '''data=spellcom,magic:iban_blast
data=levelrequired,50''', '''data=spellcom,magic:iban_blast
data=levelrequired,55''',
  '2 iban_blast: level 50, 30.0 xp, max 25'),
 # the units: stat_advance takes tenths, and this file stored x100 - ten times the wiki - until
 # 2026-09-23
 (ROWS, '''data=levelrequired,50
data=experience,300
data=maxhit,25''', '''data=levelrequired,50
data=experience,3000
data=maxhit,25''',
  '2 iban_blast: level 50, 30.0 xp, max 25'),
 (ROWS, 'data=runesrequired,firerune,5,deathrune,1,null,null',
        'data=runesrequired,firerune,4,deathrune,1,null,null',
  '2 and costs firerune,5,deathrune,1'),
 (ROWS, 'data=wornrequired,saradomin_staff\n', '',
  '2 and needs saradomin_staff wielded, with a message saying so'),
 # a god spell given a projectile it should not have
 (ROWS, '''data=spotanim_target,gunthix_claw,92''',
        '''data=spotanim_proj,ibanblast_travel,43,31,51,16,-5,64,10
data=spotanim_target,gunthix_claw,92''',
  '2 no god spell carries a projectile - in OSRS they land on the target'),
 # two god spells sharing one impact, which is the copy-paste this file is full of the shape of
 (ROWS, 'data=spotanim_target,zamorak_flame,92', 'data=spotanim_target,saradomin_lightning,92',
  '2 and each has its own impact effect, not one shared between them'),
 # the field player_magic.rs2 reads with no guard
 (ROWS, 'data=anim,human_castcrumbleundead\n', '',
  '2 a combat row missing a field the code reads unguarded (rs2check)'),

 # ---- 3, the attack sounds. The reported crash, and the two the sweep found beside it.
 (ALLOBJ, 'param=crush_sound,staff_hit\nparam=defend_anim,human_blunt_block\ntradeable=no',
          'param=defend_anim,human_blunt_block\ntradeable=no',
  '3 a weapon swung on a style it has no sound for (rs2check)'),
 (OBSIDIAN, 'param=crush_sound,mace_crush\ncategory=weapon_crush',
            'param=slash_sound,mace_crush\ncategory=weapon_crush',
  '3 a sound filed under a style the weapon is never swung on (rs2check)'),
 (SECATEURS, 'param=stab_sound,hacksword_stab\n', '',
  '3 half a weapon\'s styles left silent (rs2check)'),

 # ---- 4, the charges
 (IBANPVM, '%iban_staff_charges = sub(%iban_staff_charges, 1);', '',
  '4 a cast at an npc costs one charge and is refused at zero'),
 (IBANPVM, 'if (%iban_staff_charges < 1) {', 'if (%iban_staff_charges < 0) {',
  '4 a cast at an npc costs one charge and is refused at zero'),

 # ---- 5, the prayer press that used to be thrown away
 (ROCKSKIN, 'queue(retry_prayer_rockskin, 0, 0);', '%prayer3 = %prayer3;',
  '5 every prayer queues its own retry and returns on the direct path'),
 # the success path forgetting to return - it would queue a second toggle and turn the prayer
 # straight back off again, which looks exactly like the bug being fixed
 (ROCKSKIN, '    @activate_prayer_rockskin;\n    return;\n}',
            '    @activate_prayer_rockskin;\n}',
  '5 every prayer queues its own retry and returns on the direct path'),
 # the retry pointed at somebody else's prayer, which is what copying eighteen files invites
 (ROCKSKIN, '[queue,retry_prayer_rockskin]\n@activate_prayer_rockskin;',
            '[queue,retry_prayer_rockskin]\n@activate_prayer_thickskin;',
  '5 every prayer queues its own retry and returns on the direct path'),
 # the resync coming back beside the queue, so the orb is corrected off before the queue can run
 (ROCKSKIN, 'queue(retry_prayer_rockskin, 0, 0);',
            'queue(retry_prayer_rockskin, 0, 0);\n%prayer3 = %prayer3;',
  '5 and none of them still falls through to a bare varp resync'),
 # THE PINNED ONE, now pinned the other way round: the interrupt coming BACK, which is what an
 # upstream merge would quietly do to this file
 (ROCKSKIN, '[label,activate_prayer_rockskin]\n',
            '[label,activate_prayer_rockskin]\np_clearpendingaction;\n',
  '5 and none of them clears your pending action any more'),
 # the citation tidied away with the line, which is how a traded-away behaviour becomes one
 # nobody can remember the reason for
 (CLARITY, '// https://youtu.be/j-Z-43CzpZQ?t=120, '
           'https://youtu.be/NT74s7nJwAo?t=21, https://www.youtube.com/watch?v=fcRgR_4ZbdA', '',
  '5 with the three videos upstream cited kept beside the decision'),

 # ---- 6, the obsidian staff's stance
 # ANCHORED ON ITS OWN COMMENT. 23 other staves carry the identical human_staffready +
 # human_stafforb_pummel + human_stafforb_block run of params, and replace(find, repl, 1) takes
 # the FIRST match - so the first version of these edited a DIFFERENT staff and the obby-specific
 # checks stayed green. Same fault as the Magic Dart mutation in round 2.
 # Anchored on the end of the obby's second comment (the walk round), which no other staff carries.
 (ALLOBJ, 'so it was built for another skeleton.\nparam=ready_baseanim,human_staffready',
          'so it was built for another skeleton.\nparam=ready_baseanim,thzaar_staff_ready',
  '6 the obsidian staff is held the way the other 32 staves are held'),
 (ALLOBJ, 'so it was built for another skeleton.\nparam=ready_baseanim,human_staffready\nparam=walk_f_baseanim,human_halberdwalk_f',
          'so it was built for another skeleton.\nparam=ready_baseanim,human_staffready\nparam=walk_f_baseanim,thzaar_staff_walk',
  '6 and, being two-handed, walks, runs and turns the way the halberds do'),
 (ALLOBJ, 'param=turnonspot_baseanim,human_halberdturnonspot\nparam=crushattack_anim,human_stafforb_pummel',
          'param=turnonspot_baseanim,human_halberdturnonspot\nparam=crushattack_anim,barrows_quarterstaff_attack',
  '6 its attack and defend are the human_stafforb pair 23 other staves use, untouched'),
 # A DIFFERENT STAFF - Iban's - so the obby-specific checks above cannot be what catches it. This
 # is the invariant the outlier was found against and it has to hold for the next staff too.
 (ALLOBJ, 'param=crushattack_anim,human_blunt_pound\n// All three staff styles are crush',
          'param=running_baseanim,thzaar_staff_walk\nparam=crushattack_anim,human_blunt_pound\n'
          '// All three staff styles are crush',
  '6 and no weapon_staff walks other than as the player (one-handed) or a halberd (two-handed)'),
]


def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    muts = [m for m in MUTS if not only or only in m[3]]
    fails = loose = 0
    for path, find, repl, why in muts:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-34s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        # rs2check REFUSES TO RUN ANYWHERE BUT content/scripts - see the note beside engine.rs2 in it
        if why.endswith('(rs2check)'):
            cmd, cwd = [sys.executable, os.path.join(W, 'tools', 'rs2check.py')], os.path.join(W, 'scripts')
        else:
            cmd, cwd = [sys.executable, os.path.join(W, 'tools', 'combat_battery.py')], W
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        if named.endswith(' (rs2check)'):
            named = named[:-len(' (rs2check)')]
        if why.endswith('(rs2check)'):
            # the rule number is the claim; an ERROR line carrying one of the three is on point
            fired = [l for l in r.stdout.split('\n') if l.startswith('ERROR')]
            onpoint = any((' rule 19 ' in l or ' rule 21 ' in l or ' rule 22 ' in l) for l in fired)
        else:
            fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
            onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:52] if fired else 'a non-zero exit')
            loose += 1
        print('  %-5s %-64s %s' % (state, why, note))
    print()
    if fails:
        print('%d MUTATIONS SURVIVED' % fails)
    elif loose:
        print('every mutation was caught, but %d by a check other than its own' % loose)
    else:
        print('every mutation was caught, each by its own check')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
