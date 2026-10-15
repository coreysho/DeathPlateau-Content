#!/usr/bin/env python3
"""Mutation test for tools/pet_battery.py. Same runner as poh_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed.

    python3 tools/pet_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'pet_mutate_work')

ROLL = 'scripts/npc/scripts/skill_pets.rs2'
FOLL = 'scripts/npc/scripts/follower.rs2'
BRS2 = 'scripts/npc/scripts/boss_pets.rs2'
CONST = 'scripts/npc/configs/skill_pets.constant'
BCONST = 'scripts/npc/configs/boss_pets.constant'
MINE = 'scripts/skill_mining/configs/mine.dbrow'
TREES = 'scripts/skill_woodcutting/configs/trees.dbrow'
GWD = 'scripts/bosses/godwars/scripts/gwd_drops.rs2'
SPEC = 'tools/petspec.json'
MINERS2 = 'scripts/skill_mining/scripts/mining.rs2'
RC = 'scripts/skill_runecraft/scripts/runecraft.rs2'
VARRS2 = 'scripts/npc/scripts/pet_variants.rs2'
GNOME = 'scripts/skill_agility/scripts/gnome_course.rs2'
FISH = 'scripts/skill_fishing/scripts/fishing.rs2'
FSTRUCT = 'scripts/skill_fishing/configs/fishing.struct'
MEMBER = 'scripts/skill_fishing/scripts/fishing_spots/memberfish.rs2'
TRAWL = 'scripts/minigames/game_trawler/scripts/trawler_win.rs2'
FARM = 'scripts/skill_farming/scripts/farming_actions.rs2'
ALLOBJ = 'scripts/_unpack/377/all.obj'
THIEF = 'scripts/skill_thieving/scripts/thieving.rs2'
PICKROW = 'scripts/skill_thieving/configs/pickpocking/pickpocket.dbrow'
STALLROW = 'scripts/skill_thieving/configs/stalls/stealing.dbrow'
HUNT = 'scripts/skill_hunter/scripts/hunter_traps.rs2'

MUTS = [
 # 1 - the formula itself
 (ROLL, 'calc($base - (stat_base($stat) * ^skillpet_level_step))',
        'calc($base - (stat_base($stat) * 25))',
  '1 the chance is base - (level * step)'),
 (ROLL, 'stat_base($stat)', 'stat($stat)',
  '1 and it is the UNBOOSTED level'),
 (CONST, '^skillpet_no_roll = 0', '^skillpet_no_roll = -1',
  '1 and that sentinel is 0'),
 (ROLL, 'if ($chance < 1) {', 'if ($chance < -1) {',
  '1 the chance is floored at 1'),
 # ~pet_receive owns the duplicate test and the full-pack path now (npc/scripts/follower.rs2),
 # so these bend the funnel rather than the roll. The roll's own job is the rate.
 (FOLL, 'if (~pet_owned($pet) = true) {\n    mes("You have a funny feeling like you would have been followed...");\n    return;\n}\n', '',
  '1 ...and ~pet_receive refuses one the player owns anywhere'),
 # the inv sweep moved in front of the roll - correct, but one sweep per ACTION rather than per pet
 # the guards moved in front of the roll: correct behaviour, but one inventory sweep per ACTION
 # rather than one per pet earned - a skilling hook runs on every log and every ore.
 (ROLL, '''if (random($chance) ! 0) {
    return;
}
// Old School's rules, as every pet''', '''if (~pet_owned($pet) = true) {
    return;
}
if (random($chance) ! 0) {
    return;
}
// Old School's rules, as every pet''',
  '1 and the roll does not ask who owns what BEFORE it has rolled'),
 # follower.rs2 has two of these - the death path's and ~pet_receive's - so the one this is
 # aimed at is named by the message beneath it.
 (FOLL, '''inv_add(lostpet_store, $pet, 1);
    mes("You have a funny feeling like you're being followed, but you have no room for it.");''',
        'mes("It escapes.");',
  "1 ...and a full pack sends it to Probita's rather than the floor"),
 # 2 - the boss rates
 (BRS2, '[proc,bosspet_roll](namedobj $pet, int $rate)', '[proc,bosspet_roll](namedobj $pet)',
  '2 the rate is an argument'),
 (BCONST, '^bosspet_gwd_droprate = 5000', '^bosspet_gwd_droprate = 3000',
  '2 ^bosspet_gwd_droprate is 5,000'),
 (GWD, '~bosspet_roll(bosspet_kril_item, ^bosspet_gwd_droprate);',
       '~bosspet_roll(bosspet_kril_item, ^bosspet_droprate);',
  '2 ...at ^bosspet_gwd_droprate, which is 1 in 5000'),
 (GWD, '~bosspet_roll(bosspet_zilyana_item, ^bosspet_gwd_droprate);\n', '',
  '2 bosspet_zilyana_item is rolled in exactly one place'),
 # a pet rolled twice - once in its own table and once in someone else's
 (GWD, '~bosspet_roll(bosspet_kree_item, ^bosspet_gwd_droprate);',
       '~bosspet_roll(bosspet_kree_item, ^bosspet_gwd_droprate);\n~bosspet_roll(bosspet_graardor_item, ^bosspet_gwd_droprate);',
  '2 bosspet_graardor_item is rolled in exactly one place'),
 # 3 - a base that drifts from the wiki
 (MINE, 'data=pet_base,42377', 'data=pet_base,42000',
  '3 skillpet_rock_golem: runite_rock_table is 42377'),
 (TREES, 'data=pet_base,72321', 'data=pet_base,145013',
  '3 skillpet_beaver: magic_tree_table is 72321'),
 (CONST, '^skillpet_rift_guardian_base = 1795758', '^skillpet_rift_guardian_base = 1795000',
  '3 skillpet_rift_guardian: ^skillpet_rift_guardian_base is 1795758'),
 (CONST, '^skillpet_squirrel_barbarian = 44376', '^skillpet_squirrel_barbarian = 35609',
  '3 skillpet_squirrel: ^skillpet_squirrel_barbarian is 44376'),
 # a row that grows a base the spec has never heard of
 (MINE, '[blurite_rock]\ntable=mining_table',
        '[granite_rock]\ntable=mining_table\ndata=pet_base,741600\n\n[blurite_rock]\ntable=mining_table',
  '3 skillpet_rock_golem: nothing else in mine.dbrow carries a base'),
 # 4 - a base so small the formula runs out at 99
 (CONST, '^skillpet_squirrel_wilderness = 34666', '^skillpet_squirrel_wilderness = 2400',
  '4 skillpet_squirrel: its smallest base'),
 # 5 - a hook that stops rolling, or rolls the wrong skill
 (MINERS2, '~skillpet_roll(skillpet_rock_golem_item, mining, db_getfield($data, mining_table:pet_base, 0));',
           '~skillpet_roll(skillpet_rock_golem_item, fishing, db_getfield($data, mining_table:pet_base, 0));',
  '5 ...against mining'),
 # The rift guardian's roll lives in ~rift_guardian_roll now (npc/scripts/pet_variants.rs2), which
 # is where the rune is known - its colour comes off the altar.
 (VARRS2, '~skillpet_roll_each(skillpet_rift_guardian_item, runecraft, ^skillpet_rift_guardian_base, $times);',
          '~skillpet_roll(skillpet_rift_guardian_item, runecraft, ^skillpet_rift_guardian_base);',
  '5 ...and the Rift guardian rolls once per essence, not once per click'),
 (RC, '~rift_guardian_roll($rune, $total_ess);', '',
  '5 skillpet_rift_guardian_item rolls in runecraft.rs2, through ~rift_guardian_roll'),
 (VARRS2, '~skillpet_roll_each(skillpet_rift_guardian_item, runecraft, ^skillpet_rift_guardian_base, $times);',
          '~skillpet_roll_each(skillpet_rift_guardian_item, fishing, ^skillpet_rift_guardian_base, $times);',
  '5 ...and ~rift_guardian_roll rolls it against runecraft'),
 (GNOME, '    ~skillpet_roll(skillpet_squirrel_item, agility, ^skillpet_squirrel_gnome);\n', '',
  '5 skillpet_squirrel_item rolls in gnome_course.rs2'),
 # ---- 3, the three newest pets' bases
 (FSTRUCT, 'param=fishing_pet_base,82243', 'param=fishing_pet_base,116129',
  '3 skillpet_heron: fishing_struct_shark is 82243'),
 (FSTRUCT, '[fishing_struct_mantaray]',
           '[fishing_struct_cod]\nparam=fishing_pet_base,1147827\n\n[fishing_struct_mantaray]',
  '3 skillpet_heron: nothing else in fishing.struct carries a base'),
 (ALLOBJ, 'param=farming_pet_base,160594', 'param=farming_pet_base,281040',
  '3 skillpet_tangleroot: watermelon_seed is 160594'),
 # The gnome is its OWN band at 108,718 - an earlier pass of the spec had it in with the hero and
 # the elf at 99,175, and nothing but this would ever have shown it.
 (PICKROW, 'data=pet_base,108718', 'data=pet_base,99175',
  '3 skillpet_rocky: pickpocket_gnome is 108718'),
 (STALLROW, 'data=pet_base,124066', 'data=pet_base,36490',
  '3 skillpet_rocky: stealing_bakery_stall is 124066'),
 (CONST, '^skillpet_heron_big_net = 1147827', '^skillpet_heron_big_net = 1056000',
  '3 skillpet_heron: ^skillpet_heron_big_net is 1147827'),
 (CONST, '^skillpet_heron_trawler = 5000', '^skillpet_heron_trawler = 50000',
  '3 skillpet_heron: ^skillpet_heron_trawler is 5000'),

 # ---- 5, a hook rolling against the wrong skill
 (FISH, '~skillpet_roll(skillpet_heron_item, fishing,',
        '~skillpet_roll(skillpet_heron_item, agility,', '5 ...against fishing'),
 (FARM, '~skillpet_roll(skillpet_tangleroot_item, farming,',
        '~skillpet_roll(skillpet_tangleroot_item, woodcutting,', '5 ...against farming'),
 (THIEF, '~skillpet_roll(skillpet_rocky_item, thieving,',
         '~skillpet_roll(skillpet_rocky_item, mining,', '5 ...against thieving'),

 # ---- 5 again, for the chinchompa: rolled on a box trap, against Hunter
 (HUNT, '~skillpet_roll(skillpet_chinchompa_item, hunter, ^skillpet_chinchompa_grey);',
        '~skillpet_roll(skillpet_chinchompa_item, fishing, ^skillpet_chinchompa_grey);',
  '5 ...against hunter'),

 # ---- 6, a pet quietly marked unwired in the spec. Every pet has a source since box trapping
 # (2026-09-23); one that stops having one has to be said out loud, not slip past as "pending".
 (SPEC, '"skillpet_chinchompa": {\n   "stat": "hunter",\n   "wired": true',
        '"skillpet_chinchompa": {\n   "stat": "hunter",\n   "wired": false',
  '6 none is pending'),

 # ---- 8, WHEN each of the three rolls
 # A tier of fish rolling at another tier's rate. Invisible without this: the roll still happens,
 # the pet still drops, and only the maths over ten thousand catches would ever say.
 (FISH, 'struct_param($struct1, fishing_pet_base)', 'struct_param($struct2, fishing_pet_base)',
  '8 ...each off the struct of the fish it just caught'),
 (FISH, '\n        ~skillpet_roll(skillpet_heron_item, fishing, struct_param($struct2, fishing_pet_base));', '',
  '8 all four catches in fish_roll and fish_roll_loc roll'),
 (MEMBER, 'if ($caught > 0) {', 'if ($caught > -1) {',
  '8 ...and only when the haul caught something'),
 (MEMBER, '    ~fishing_xp(1);\n    $caught = calc($caught + 1);', '    ~fishing_xp(1);',
  '8 every item the net can bring up counts towards that'),
 (MEMBER, '~skillpet_roll(skillpet_heron_item, fishing, ^skillpet_heron_big_net);',
          '~skillpet_roll(skillpet_heron_item, fishing, ^skillpet_heron_big_net);\n~skillpet_roll(skillpet_heron_item, fishing, ^skillpet_heron_big_net);',
  '8 the big net rolls once per haul, not once per item'),
 (MEMBER, '^skillpet_heron_big_net', '^skillpet_heron_trawler',
  '8 ...at the activity constant, because OSRS gives one figure for big net fishing'),
 (TRAWL, '    inv_add(trawler_rewardinv, raw_mantaray, 1);',
         '    inv_add(trawler_rewardinv, raw_mantaray, 1);\n    ~skillpet_roll(skillpet_heron_item, fishing, ^skillpet_heron_trawler);',
  '8 and the trawler does not also roll per fish out of the net'),
 (FARM, '~farming_xp(oc_param($seed, farming_check_xp));\n~farming_pet_roll($seed);',
        '~farming_xp(oc_param($seed, farming_check_xp));',
  '8 check-health rolls, which is where a tree rolls'),
 # The roll after the clear: the patch is already empty, and on a server where clearing resets the
 # patch's seed this is the roll reading whatever is there next.
 (FARM, 'anim(null, 0);\n~farming_pet_roll($seed);\n~farming_clear_patch($patch);',
        'anim(null, 0);\n~farming_clear_patch($patch);\n~farming_pet_roll($seed);',
  '8 ...the roll comes before the clear, while the seed is still known'),
 # A roll on every pick rather than on the pick that clears: a ranarr patch would roll five times.
 (FARM, 'inv_add(inv, $produce, 1);\nmes("You harvest <lowercase(oc_name($produce))>.");\n~farming_xp(oc_param($seed, farming_harvest_xp));',
        'inv_add(inv, $produce, 1);\nmes("You harvest <lowercase(oc_name($produce))>.");\n~farming_xp(oc_param($seed, farming_harvest_xp));\n~farming_pet_roll($seed);',
  '8 the two harvests that clear the patch roll, and only those'),
 (FARM, '    if ($left <= 1) {\n        ~farming_pet_roll($seed);',
        '    if ($left <= 1) {',
  '8 picking regrowing produce rolls once and only on the last mushroom'),
 # A bush that loses its check-health keeps a base that can then never fire: the patch regrows
 # instead of clearing, so nothing ever rolls for it.
 (ALLOBJ, 'param=farming_check_state,250', 'param=farming_check_state,0',
  '8 every family that never clears its patch has a check-health to roll at'),
 (THIEF, '~trapped_chest_check_for_reward($data);',
         '~trapped_chest_check_for_reward($data);\n~skillpet_roll(skillpet_rocky_item, thieving, 36490);',
  '8 a trapped chest gives no pet, as in OSRS'),
 (THIEF, '~skillpet_roll(skillpet_rocky_item, thieving, db_getfield($data, stealing:pet_base, 0));',
         '~skillpet_roll(skillpet_rocky_item, thieving, db_getfield($data, pickpocket:pet_base, 0));',
  '8 ...one off stealing:pet_base'),
 (THIEF, '~thieving_xp($experience);\n~skillpet_roll(skillpet_rocky_item, thieving, db_getfield($data, pickpocket:pet_base, 0));',
         '~thieving_xp($experience);\nsound_synth(pick, 1, 0);\n~skillpet_roll(skillpet_rocky_item, thieving, db_getfield($data, pickpocket:pet_base, 0));',
  '8 and each roll sits on the line after the xp it belongs to'),
 # Thieving going round its own funnel: the pet still rolls, but the Rogue outfit never turns up.
 (THIEF, '~thieving_xp($experience);\n~skillpet_roll(skillpet_rocky_item, thieving, db_getfield($data, stealing:pet_base, 0));',
         'stat_advance(thieving, $experience);\n~skillpet_roll(skillpet_rocky_item, thieving, db_getfield($data, stealing:pet_base, 0));',
  '8 ...which is the funnel, not a direct award'),
 # 7 - the two halves of a pet losing track of each other
 ('scripts/npc/configs/skill_pets.obj', 'param=follower_id,skillpet_beaver',
  'param=follower_id,skillpet_heron', '7 ...and the item names the npc'),
 ('scripts/npc/configs/skill_pets.npc', 'category=bosspet\nfollower=yes\nparam=pet_item_id,skillpet_rocky_item',
  'follower=yes\nparam=pet_item_id,skillpet_rocky_item',
  '7 ...both on the category the four follower triggers hang off'),
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
            print('  SKIP (pattern not found) %-40s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'pet_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:56] if fired else 'a non-zero exit')
            loose += 1
        print('  %-5s %-62s %s' % (state, why, note))
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
