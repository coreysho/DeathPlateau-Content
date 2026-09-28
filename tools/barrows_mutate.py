#!/usr/bin/env python3
"""Mutation test for tools/barrows_battery.py. Same runner as fightcave_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed, which is not the same as the check being aimed right.

Most of these are CROSS-WIRINGS rather than broken code - Torag's mound leading to Karil's crypt,
Guthan's sarcophagus handing over Verac, Karil's death setting Torag's bit. That is the whole risk
in the Barrows: six of everything, all named alike, and a swap that compiles and plays.

    python3 tools/barrows_mutate.py [filter]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'barrows_mutate_work')

CONST = 'scripts/areas/area_barrows/configs/barrows.constant'
VARBIT = 'scripts/areas/area_barrows/configs/barrows.varbit'
ENUM = 'scripts/areas/area_barrows/configs/barrows.enum'
TUN = 'scripts/areas/area_barrows/scripts/barrows_tunnels.rs2'
CHEST = 'scripts/areas/area_barrows/scripts/barrows_chest.rs2'
TELE = 'scripts/areas/area_barrows/scripts/barrows_teleport.rs2'
TOBJ = 'scripts/areas/area_barrows/configs/barrows.obj'
DEATH = 'scripts/skill_combat/scripts/npc/npc_death.rs2'
ALLVARP = 'scripts/_unpack/377/all.varp'
ALLVARBIT = 'scripts/_unpack/377/all.varbit'
ALLLOC = 'scripts/_unpack/377/all.loc'
ALLSEQ = 'scripts/_unpack/377/all.seq'
SKELTABLE = 'scripts/drop_tables/scripts/skeleton_barrows_skeleton_armed.rs2'
COMBATPARAM = 'scripts/skill_combat/configs/npc_combat.param'
COMBAT = 'scripts/areas/area_barrows/scripts/barrows_combat.rs2'
SETS = 'scripts/areas/area_barrows/scripts/barrows_sets.rs2'
PUZZLE = 'scripts/areas/area_barrows/scripts/barrows_puzzle.rs2'
CHESTIF = 'scripts/areas/area_barrows/interfaces/barrows_chest.if'
INVCFG = 'scripts/areas/area_barrows/configs/barrows.inv'
GENCHEST = 'tools/genbarrowschest.py'
ALLOBJ = 'scripts/_unpack/377/all.obj'
PMELEE = 'scripts/skill_combat/scripts/player/player_melee.rs2'
PRANGED = 'scripts/skill_combat/scripts/player/player_ranged.rs2'
PMAGIC = 'scripts/skill_combat/scripts/player/player_magic.rs2'
VMELEE = 'scripts/skill_combat/scripts/pvp/pvp_melee.rs2'
CHESTSPEC = 'tools/barrowschestspec.json'
RS2 = 'scripts/areas/area_barrows/scripts/barrows.rs2'
STAIRS = 'scripts/ladders+stairs/scripts/stairs.rs2'
SPADE = 'scripts/general_use/scripts/spade.rs2'
ALLNPC = 'scripts/_unpack/377/all.npc'
ANIMSPEC = 'tools/karilanimspec.json'
XBOWSEQ = 'scripts/skill_combat/configs/ranged/osrs_crossbow_anims.seq'
SEQPACK = 'pack/seq.pack'
ANIMPACK = 'pack/anim.pack'
SETPACK = 'pack/animset.pack'
BASEPACK = 'pack/base.pack'
PZIF = 'scripts/areas/area_barrows/interfaces/barrows_puzzle.if'
PZENUM = 'scripts/areas/area_barrows/configs/barrows_puzzle.enum'
PZSPEC = 'tools/barrowspuzzlespec.json'
PZOPT = 'sprites/meta/barrows_puzzle.opt'
PZGEN = 'tools/genbarrowspuzzle.py'
ALLNPC = 'scripts/_unpack/377/all.npc'
SPEC = 'tools/barrowsspec.json'
SURFACE = 'maps/m55_51.jm2'
VARPPACK = 'pack/varp.pack'

MUTS = [
 # --- the mounds, which are terrain and so are re-measured off the map every run
 (CONST, '^barrows_mound_ahrim = 0_55_51_46_25', '^barrows_mound_ahrim = 0_55_51_44_25',
  "1 ahrim's mound coordinate"),
 (CONST, '^barrows_mound_dharok = 0_55_51_56_35', '^barrows_mound_dharok = 0_55_51_46_25',
  '1 the six coordinates are on six different hills'),
 (CONST, '^barrows_mound_torag = 0_55_51_34_20', '^barrows_mound_torag = 0_55_52_34_20',
  '1 all six sit on level 0 of m55_51'),
 (SPEC, '"dharok": "north-east"', '"dharok": "south-east"',
  "1 dharok's mound lies north-east of the middle"),
 (CONST, '^barrows_mound_radius = 2', '^barrows_mound_radius = 8',
  '1 no two mounds are within two radii'),
 # a seventh hill, raised on the map itself - the check counts them rather than trusting six
 (SURFACE, '0 0 0: h27 u50', '0 0 0: h80 u50',
  '1 m55_51 has exactly six hills above h70'),
 # ...and a hill taller than Ahrim's, which the wiki says is the tall one
 (SURFACE, '0 38 34: h79 u115', '0 38 34: h90 u115',
  "1 Ahrim's mound is also the tallest"),

 # --- the crypt tiles, re-measured against the map's own loc occupancy
 (CONST, '^barrows_crypt_ahrim = 3_55_151_37_39', '^barrows_crypt_ahrim = 3_55_151_35_34',
  "2 ahrim's drop tile (37,39) is free floor"),
 (CONST, '^barrows_crypt_ahrim = 3_55_151_37_39', '^barrows_crypt_ahrim = 3_55_151_36_39',
  "2 ahrim's drop tile is beside HIS OWN staircase"),
 (CONST, '^barrows_crypt_torag = 3_55_151_45_20', '^barrows_crypt_torag = 3_55_151_26_20',
  "2 torag's drop tile is nearest HIS OWN sarcophagus"),
 (CONST, '^barrows_crypt_verac = 3_55_151_57_39', '^barrows_crypt_verac = 0_55_151_57_39',
  '2 all six sit on level 3 of m55_151'),

 # --- digging in
 (RS2, '$crypt = ^barrows_crypt_guthan;', '$crypt = ^barrows_crypt_karil;',
  "3 guthan's mound leads to"),
 (RS2, 'if ($crypt = null) {\n    return(false);\n}', 'if ($crypt = null) {\n    return(true);\n}',
  '3 the dig reports false in exactly one place'),
 (RS2, 'distance(coord, ^barrows_mound_verac) <= ^barrows_mound_radius',
       'distance(coord, ^barrows_mound_verac) <= 2',
  '3 all six branches measure against ^barrows_mound_radius'),
 (SPADE, 'if (~barrows_mound_dig = true) {\n    return;\n}\n\n// Everything else\np_arrivedelay;',
         '// Everything else\np_arrivedelay;\nif (~barrows_mound_dig = true) {\n    return;\n}',
  '4 spade.rs2 asks the Barrows BEFORE its own dig'),

 # --- climbing out
 (STAIRS, '[oploc1,barrows_stairs_karil] @barrows_climb_out(^barrows_mound_karil);',
          '[oploc1,barrows_stairs_karil] @barrows_climb_out(^barrows_mound_torag);',
  "5 karil's staircase climbs out onto"),
 (STAIRS, '[oploc1,barrows_stairs_verac] @barrows_climb_out(^barrows_mound_verac);',
          '[oploc1,barrows_stairs_verac]\nswitch_coord (loc_coord) {\n'
          '    case default : @unhandled_stairs(loc_coord);\n}',
  '5 no Barrows staircase is left routed'),

 # --- the sarcophagi
 (RS2, '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_torag);',
       '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_verac, ^barrows_bit_torag);',
  '6 barrow_torag_sarcophagus hands over'),
 (RS2, '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_torag);',
       '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_verac);',
  '6 barrow_torag_sarcophagus hands over'),
 (RS2, '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_torag);\n',
       '',
  '6 every sarcophagus in the cache has a handler'),
 (RS2, 'if (testbit(%barrows_kills, $bit) = ^true) {',
       'npc_add(coord, $brother, ^barrows_brother_life);\n'
       'if (testbit(%barrows_kills, $bit) = ^true) {',
  '6 the sarcophagus reads the kill bit BEFORE it adds anybody'),
 (RS2, 'npc_add(coord, $brother, ^barrows_brother_life);',
       'npc_add(coord, $brother, ^max_32bit_int);',
  '6 a woken brother is added with ^barrows_brother_life, not forever'),
 (RS2, '%aggressive_npc = npc_uid;\n', '',
  '6 and he comes out fighting'),

 # --- the deaths, and the compile-time lesson about where the write has to live
 (RS2, '%barrows_killed_karil = ^true;', '%barrows_killed_torag = ^true;',
  "7 karil's death sets"),
 (RS2, '%barrows_killed_ahrim = ^true;',
       '~barrows_brother_killed(^barrows_bit_ahrim);\n\n'
       '[proc,barrows_brother_killed](int $bit)\n'
       '%barrows_kills = setbit(%barrows_kills, $bit);',
  '7 the bit is written only inside the death triggers'),
 (RS2, 'if (npc_findhero = ^false) {\n    return;\n}\n%barrows_killed_ahrim = ^true;',
       '%barrows_killed_ahrim = ^true;\nif (npc_findhero = ^false) {\n    return;\n}',
  '7 ahrim finds his killer before he writes to him'),
 (RS2, 'gosub(npc_death);\nif (npc_findhero = ^false) {\n    return;\n}\n'
       '%barrows_killed_dharok = ^true;',
       '%barrows_killed_dharok = ^true;',
  "7 dharok's death still dies properly"),

 # --- the var and the bits
 (CONST, '^barrows_bit_verac = 5', '^barrows_bit_verac = 4',
  '8 the six bits are 0-5 with no collision'),
 (CONST, '^barrows_brothers = 6', '^barrows_brothers = 5',
  '8 ^barrows_brothers counts the brothers there are'),

 # --- the brothers against Old School's own infoboxes
 (ALLNPC, 'param=strengthbonus,72\nparam=damagetype,^stab_style',
          'param=strengthbonus,72\nparam=damagetype,^crush_style',
  '9 verac attacks with stab'),
 (ALLNPC, 'param=attackrate,5\nparam=magicattack,-50', 'param=attackrate,4\nparam=magicattack,-50',
  '9 guthan attacks every 5 ticks'),
 (ALLNPC, 'param=attackrate,6\nparam=magicattack,73',
          'param=attackrate,6\nparam=slashattack,68\nparam=magicattack,73',
  '9 ahrim carries no invented per-style attack bonus'),
 (ALLNPC, 'param=stabdefence,252', 'param=stabdefence,253',
  "9 dharok's stab defence is"),
 (ALLNPC, 'param=rangeattack,134', 'param=rangeattack,140',
  "9 karil's ranged bonus is"),
 (ALLNPC, 'param=attack_anim,barrow_torag_crush',
          'param=attack_anim,barrow_torag_crushed',
  "9 torag's attack_anim is a real animation"),
 (ALLNPC, 'param=strengthbonus,105', 'param=strengthbonus,106',
  "9 dharok's strength bonus is"),
 (SPEC, '"combat": 98,\n      "speed": 6,', '"combat": 99,\n      "speed": 6,',
  '9 ahrim is combat 98 on the right-click'),
 # --- the run's storage, which is the cache's and not ours
 (VARBIT, '[barrows_entry_crypt]\nbasevar=barrows\nstartbit=0\nendbit=2',
          '[barrows_entry_crypt]\nbasevar=barrows\nstartbit=6\nendbit=8',
  '10 barrows_entry_crypt sits in %barrows bits 0-2'),
 (VARBIT, '[barrows_chest_paid]\nbasevar=barrows\nstartbit=3\nendbit=3',
          '[barrows_chest_paid]\nbasevar=barrows\nstartbit=9\nendbit=9',
  '10 barrows_chest_paid sits in %barrows bit 3'),
 ('pack/varbit.pack', '2114=barrows_entry_crypt\n', '',
  '10 barrows_entry_crypt is in pack/varbit.pack'),
 (ALLVARP, '[barrows_kills]\nprotect=no\ntransmit=yes', '[barrows_kills]\ntransmit=yes',
  '10 [barrows_kills] is protect=no'),
 (ALLVARBIT, '[barrows_killed_dharok]\nbasevar=barrows_kills\nstartbit=1\nendbit=1',
             '[barrows_killed_dharok]\nbasevar=barrows_kills\nstartbit=2\nendbit=2',
  '10 barrows_killed_dharok is bit 1 of %barrows_kills'),
 (ALLVARBIT, '[barrows_killed_monster]\nbasevar=barrows_kills\nstartbit=6\nendbit=15',
             '[barrows_killed_monster]\nbasevar=barrows_kills\nstartbit=6\nendbit=14',
  '10 barrows_killed_monster holds the reward potential and is wide enough'),
 (CHEST, 'mes("You close the chest.");', 'mes("You close the chest.");\n%barrows_killed = 0;',
  '10 nothing reads or writes a %barrows_killed varp any more'),

 # --- the maze
 (ENUM, 'val=7,34922', 'val=7,65535', '11 every maze still leaves all four ladders'),
 (ENUM, 'val=7,34922', 'val=7,2442', '11 and no row is a duplicate of another'),
 (ENUM, 'val=23,64868\n', '', '11 barrows_mazes holds ^barrows_mazes = 24 rows'),
 (ENUM, 'default=0', 'default=1', '11 a miss opens every door rather than shutting one'),
 (ENUM, 'val=3,33073', 'val=3,0', '11 every maze shuts something'),
 (CONST, '^barrows_mazes = 24', '^barrows_mazes = 23',
  '11 barrows_mazes holds ^barrows_mazes = 24 rows'),
 (CONST, '^barrows_door_first = 10', '^barrows_door_first = 11', '11 gate a is %barrows bit 10'),
 (CONST, '^barrows_door_last = 25', '^barrows_door_last = 24',
  '11 ^barrows_door_first..last is exactly sixteen bits wide'),

 # --- the equipment table
 (ENUM, 'val=2,barrows_ahrim_legs', 'val=2,barrows_dharok_legs',
  "12 piece 2 is one of ahrim's"),
 (ENUM, 'val=20,barrows_verac_head', 'val=20,barrows_verac_headd',
  "12 piece 20 is one of verac's"),
 (ENUM, 'val=1,barrows_ahrim_body', 'val=1,barrows_ahrim_head', '12 no piece is listed twice'),
 (ENUM, 'default=null', 'default=barrows_ahrim_head', '12 and says null out loud on a miss'),
 (CHEST, '~barrows_nth_killed(random($brothers))', '~barrows_nth_unkilled(random($brothers))',
  '12 and picks the brother from the ones that are DEAD'),
 (CHEST, 'if (testbit(%barrows_kills, $bit) = ^true) {\n        if ($n = 0) {',
         'if (testbit(%barrows_kills, $bit) = ^false) {\n        if ($n = 0) {',
  '12 ~barrows_nth_killed counts the killed bits'),
 (TUN, 'if (testbit(%barrows_kills, $bit) = ^false) {\n        if ($n = 0) {',
        'if (testbit(%barrows_kills, $bit) = ^true) {\n        if ($n = 0) {',
  '12 ...and its mirror, which a door uses, counts the live ones'),

 # --- the chest's own numbers
 (CONST, '^barrows_rolls_max = 7', '^barrows_rolls_max = 8', '13 one roll to start and seven at most'),
 (CONST, '^barrows_equip_step = 58', '^barrows_equip_step = 57', '13 which is 1/392 with 1 brother'),
 (CONST, '^barrows_potential_max = 1012', '^barrows_potential_max = 1014',
  '13 ...and that is arithmetic rather than three numbers'),
 (CONST, '^barrows_rp_mind = 381', '^barrows_rp_mind = 380', '13 mindrune needs 381 reward potential'),
 (CONST, '^barrows_rp_keyhalf = 1006', '^barrows_rp_keyhalf = 1000',
  '13 keyhalf needs 1006 reward potential'),
 (CONST, '^barrows_loot_coins_high = 774', '^barrows_loot_coins_high = 775',
  '13 coins comes 2-774 at a time'),
 (CHESTSPEC, '"rp": 881', '"rp": 880', '13 boltrack needs 881 reward potential'),
 (CHEST, '} else if ($roll >= ^barrows_rp_blood) {\n    ~barrows_reward_add(bloodrune,',
         '} else if ($roll >= ^barrows_rp_blood) {\n    ~barrows_reward_add(chaosrune,',
  '13 the blood band pays bloodrune'),
 (CHEST, 'if ($roll >= ^barrows_rp_dragonmed) {', 'if ($roll >= ^barrows_rp_mind) {',
  '13 the chest tests the bands from the top down'),
 (CHEST, 'add(random($potential), 1)', 'random($potential)',
  '13 the roll is a value in 1..potential'),

 # --- paying twice, and clearing the run
 (CHEST, 'p_delay(1);\n%barrows_chest_paid = ^true;', 'p_delay(1);',
  '14 looting marks the chest paid'),
 (CHEST, 'if (%barrows_chest_paid = ^true) {\n    if (~barrows_reward_held > 0) {',
         'if (%barrows_chest_paid = ^false) {\n    if (~barrows_reward_held > 0) {',
  '14 and a chest that has paid and been emptied says the same rather than rolling again'),
 (CHEST, 'if (%barrows_entry_crypt = ^barrows_entry_none) {\n    mes("You search the chest and find nothing of interest.");\n    return;\n}\n',
         '',
  '14 a search with no run behind it still finds nothing of interest'),
 (CHEST, '~barrows_chest_window($rolls, $potential);',
         '%barrows_kills = 0;\n~barrows_chest_window($rolls, $potential);',
  '14 looting clears NOTHING'),
 (TUN, '%barrows_chest_paid = ^false;\n%barrows_chest_open = ^false;',
        '%barrows_chest_open = ^false;',
  '14 the next dig is what clears the last run'),
 (TUN, 'if (%barrows_entry_crypt ! ^barrows_entry_none & %barrows_chest_paid = ^false) {',
        'if (%barrows_entry_crypt ! ^barrows_entry_none) {',
  '14 ...and a run still owed its chest is never cleared'),

 # --- the doors
 (CONST, '^barrows_spawn_skeleton = 64', '^barrows_spawn_skeleton = 60', '15 a skeleton on 52'),
 (CONST, '^barrows_spawn_bloodworm = 96', '^barrows_spawn_bloodworm = 100', '15 a bloodworm on 32'),
 (CONST, '^barrows_spawn_crowd = 11', '^barrows_spawn_crowd = 12',
  '15 nothing comes through into a room already holding 11'),
 (TUN, 'if (%barrows_entry_crypt = ^barrows_entry_none) {\n    return;\n}\nif (~barrows_crowd',
        'if (~barrows_crowd',
  '15 a door with no run behind it lets nothing out'),
 (TUN, 'if (~barrows_crowd($where) >= ^barrows_spawn_crowd) {\n    return;\n}\n'
       'def_int $roll = random(^barrows_spawn_denom);',
       'def_int $roll = random(^barrows_spawn_denom);\n'
       'if (~barrows_crowd($where) >= ^barrows_spawn_crowd) {\n    return;\n}',
  '15 ...checked before the roll'),
 (TUN, 'if (%barrows_chest_paid = ^true) {\n    $roll = 0;\n}', '',
  '15 after the chest has paid, every door is a brother'),
 (TUN, '~barrows_nth_unkilled(random($left))', '~barrows_nth_killed(random($left))',
  "15 a door's brother is one the player has NOT killed"),
 (TUN, '[oploc1,barrows_door_d_l] ~barrows_door_open(^left);\n', '',
  '15 all thirty-two doorway leaves are accounted for'),

 # --- the passage and the ladder
 (CONST, '^barrows_chamber_tile_a = 0_55_151_15_48', '^barrows_chamber_tile_a = 0_55_151_14_48',
  "16 chamber a's drop tile is floor a player can stand on"),
 (CONST, '^barrows_chamber_tile_a = 0_55_151_15_48', '^barrows_chamber_tile_a = 0_55_151_47_48',
  "16 chamber a's drop tile is beside ITS OWN ladder"),
 (CONST, '^barrows_chamber_g = 2', '^barrows_chamber_g = 3',
  '16 the four chambers are numbered 0..3'),
 (TUN, 'case ^barrows_chamber_c : return(^barrows_chamber_tile_c);',
        'case ^barrows_chamber_c : return(^barrows_chamber_tile_g);',
  '16 chamber g answers with g\'s tile'),
 (TUN, 'case ^barrows_chamber_i : %barrows_chamber_i = ^true;',
        'case ^barrows_chamber_i : %barrows_chamber_a = ^true;',
  '16 and opening chamber i lights i\'s ladder'),
 (TUN, 'case ^barrows_bit_torag : return(^barrows_mound_torag);',
        'case ^barrows_bit_torag : return(^barrows_mound_karil);',
  "16 the ladder puts a player who came in by torag's crypt back on torag's mound"),
 (TUN, 'def_int $chamber = ~barrows_open_chamber;', 'def_int $chamber = -1;',
  '16 coming back down the same run reuses the chamber'),
 (RS2, 'if (%barrows_entry_crypt = add($bit, 1)) {', 'if (%barrows_entry_crypt = $bit) {',
  '16 the sarcophagus of the entry crypt gives the passage'),

 # --- reward potential
 (DEATH, '~barrows_potential;\n', '', '17 [proc,npc_death] pays reward potential'),
 (TUN, 'if (inzone(^barrows_tunnel_sw, ^barrows_tunnel_ne, npc_coord) = ^false) {\n    return;\n}',
        '',
  '17 and nothing outside the tunnels pays anything'),
 (TUN, 'if (~barrows_brother_bit(npc_type) >= 0) {\n    return;\n}', '',
  '17 a BROTHER pays nothing into the pool'),
 (TUN, 'min(add(%barrows_killed_monster, nc_vislevel(npc_type)), ^barrows_potential_cap)',
        'add(%barrows_killed_monster, nc_vislevel(npc_type))',
  "17 what it pays is the dead thing's own combat level, capped"),
 (CONST, '^barrows_potential_cap = 1000', '^barrows_potential_cap = 1001',
  '17 the pool caps at 1000'),
 (CHESTSPEC, '"barrows_bloodworm": 52', '"barrows_bloodworm": 53',
  '17 barrows_bloodworm is combat 52'),

 # --- the teleport
 (TOBJ, 'stackable=yes', 'stackable=no', '18 it stacks, which is the point of a tab'),
 (TOBJ, 'iop1=Break', 'iop2=Break', '18 and its one option is Break'),
 (TOBJ, '2dzoom=465', '2dzoom=400', "18 its 2dzoom is the lectern tablets' own"),
 (CONST, '^barrows_tele_dest = 0_55_51_45_48', '^barrows_tele_dest = 0_55_51_45_47',
  '18 it lands on 0_55_51_45_48, the tile Corey asked for'),
 (CONST, '^barrows_tele_rate = 10', '^barrows_tele_rate = 8', '18 the chest pays one at 1/10'),
 (CONST, '^barrows_tele_high = 6', '^barrows_tele_high = 8', '18 and pays 4 to 6 of them'),
 (CHEST, 'if (random(^barrows_tele_rate) = 0) {\n    ~barrows_reward_add(barrows_teleport,\n'
         '                        ~barrows_between(^barrows_tele_low, ^barrows_tele_high));\n}', '',
  '18 the chest is the only thing in the game that hands one over'),
 (TELE, 'inv_del(inv, barrows_teleport, 1);', 'mes("");',
  '18 breaking one spends exactly one'),
 (TELE, 'if (~pre_tele_checks(coord) = false) {\n    return;\n}', '',
  '18 and it is not a way out of deep wilderness'),
 # --- a handler that cannot fire, which is what shipped
 (TUN, '[oploc1,barrows_door_a_l] ~barrows_door_open(^left);',
        '[oploc1,barrows_door_unlocked_l] ~barrows_door_open(^left);',
  '19 op1 on barrows_door_n_r'),
 (TUN, '[oploc1,_barrows_ladder]', '[oploc1,barrows_ladder]',
  '19 op1 on category barrows_ladder'),
 (CHEST, '[oploc1,barrows_stone_chest]', '[oploc1,barrows_stone_chest_closed]',
  '19 op1 on barrows_stone_chest'),
 (CHEST, '[oploc2,barrows_stone_chest]', '[oploc2,barrows_stone_chest_open]',
  '19 op2 on barrows_stone_chest'),
 # The doors no longer answer to a category of their own - they wear the double-door ones - so the
 # dead-click check is fed from the ladder side instead. Note that removing ONE door's explicit
 # trigger would NOT show up here: the generic double-door handler would quietly take it, which is
 # why the thirty-two are counted separately.
 (TUN, '[oploc1,_barrows_ladder]\np_arrivedelay;', 'p_arrivedelay;',
  '19 no Barrows loc on either map has an option nothing handles'),
 (ALLLOC, '[barrows_ladder_g]\ncategory=barrows_ladder', '[barrows_ladder_g]',
  '19 no Barrows loc on either map has an option nothing handles'),
 (CHEST, '[oploc2,barrows_stone_chest]\np_arrivedelay;\np_stopaction;\n'
         'facesquare(loc_coord);\n%barrows_chest_open = ^false;\nmes("You close the chest.");',
         '',
  '19 no Barrows loc on either map has an option nothing handles'),
 (CHEST, '~barrows_chest_search;', 'mes("");',
  '19 one op1 handler opens the chest and searches it'),

 # --- the dig that would not stop
 (RS2, 'anim(null, 0);\nreturn(true);', 'return(true);',
  '20 the dig animation is stopped after the telejump'),

 # --- the tunnels paying out
 (ALLNPC, '[barrows_rat]', '[barrows_rat]\nparam=death_drop,bones',
  '21 barrows_rat drops nothing'),
 (SKELTABLE, '[label,barrows_skeleton_armed_drop_table]',
             '[ai_queue3,barrows_skeleton_armed] @barrows_skeleton_armed_drop_table;\n\n'
             '[label,barrows_skeleton_armed_drop_table]',
  '21 ...and has no death trigger of its own to put it back on a table'),
 (COMBATPARAM, '[death_drop]\ntype=namedobj\ndefault=bones',
               '[death_drop]\ntype=namedobj\ndefault=null',
  '21 and death_drop really does default to bones'),
 (RS2, 'if (~barrows_brother_here($brother) = ^true) {\n'
       '    mes("You search the sarcophagus. It is empty - its occupant is already up.");\n'
       '    return;\n}\n', '',
  '22 and a box whose brother is already out hands over nobody'),
 (CHEST, 'npc_findall(coord, $brother, 64, 0);', 'npc_findall(coord, $brother, 64, 1);',
  '22 and it looks for him without needing to see him'),
 # --- the brothers' styles, hits and effects
 (ALLNPC, 'param=rangebonus,55\n', '',
  "23 karil's max hit comes out of his own record"),
 (SPEC, '"maxhit": 24', '"maxhit": 25', "23 guthan's max hit comes out of his own record"),
 (CONST, '^barrows_ahrim_maxhit = 20', '^barrows_ahrim_maxhit = 19',
  "23 ahrim's max hit comes out of his own record"),
 (COMBAT, 'return(add($maxhit, scale(sub(npc_basestat(hitpoints), npc_stat(hitpoints)), 100, $maxhit)));',
           'return($maxhit);',
  '23 ...and that is the line that does it'),
 (COMBAT, 'if (npc_type ! barrows_dharok) {\n    return($maxhit);\n}\n', '',
  '23 and nobody else gets it'),
 (COMBAT, '[ai_queue1,barrows_ahrim] ~npc_default_retaliate_ap;\n', '',
  '23 ahrim retaliates AT RANGE'),
 (COMBAT, '[ai_applayer2,barrows_karil] ~barrows_karil_shoot;',
           '[ai_opplayer2_unused,barrows_karil] ~barrows_karil_shoot;',
  '23 ...and both being walked up to and standing off send him to the same ranged attack'),
 (COMBAT, '[ai_opplayer2,barrows_torag] ~barrows_melee;\n', '',
  '23 torag swings, through his own handler'),
 (COMBAT, 'def_int $damage = ~barrows_melee_damage;\n~playerhit_n_melee($damage, npc_param(attackrate));',
           '~npc_meleeattack;',
  '23 no brother goes through the plain melee attack'),
 (CONST, '^barrows_verac_pierce_pct = 25', '^barrows_verac_pierce_pct = 30',
  "23 verac's prayer pierce is 25%"),
 (COMBAT, 'if (npc_type = barrows_verac & random(100) < ^barrows_verac_pierce_pct) {\n'
          '    return(add(random($maxhit), 1));\n}\n', '',
  '23 ...and a pierced hit is decided BEFORE the rolls'),
 (COMBAT, 'return(add(random($maxhit), 1));', 'return(randominc($maxhit));',
  '23 and it lands for one to his max, never nothing'),
 (CONST, '^barrows_guthan_effect_pct = 25', '^barrows_guthan_effect_pct = 20',
  "23 guthan's Infestation fires on 25% of his landed hits"),
 (CONST, '^barrows_ahrim_effect_pct = 20', '^barrows_ahrim_effect_pct = 25',
  "23 ahrim's Blighted Aura fires on 20% of his landed hits"),
 (COMBAT, 'spotanim_npc(barrows_torag_effect, 92, 0);',
           'spotanim_npc(barrows_guthan_effect, 92, 0);',
  '23 ...and it is the one HIS case plays'),
 (COMBAT, 'npc_statheal(hitpoints, $damage, 0);', 'npc_statheal(hitpoints, 1, 0);',
  '23 Guthan heals for THE DAMAGE HE DEALT'),
 (COMBAT, 'scale($percent, 100, runenergy)', 'scale($percent, 100, 100)',
  "23 and Torag's fifth is a fifth of what is LEFT"),
 (COMBAT, 'queue(barrows_karil_drain, 0, ^barrows_karil_agility_pct);',
           'stat_sub(agility, 0, ^barrows_karil_agility_pct);',
  '23 barrows_karil_drain reaches the player through his own queue'),
 (COMBAT, '~get_spell_data(^iban_blast)', '~get_spell_data(^wind_blast)',
  "23 Ahrim's attack is Iban's Blast"),
 (COMBAT, '~npc_player_hit_roll(^magic_style)', '~npc_player_hit_roll(^melee_style)',
  '23 ...and his aura rolls on THE SAME hit roll'),
 (COMBAT, 'case 1 : return(^weaken);', 'case 1 : return(^confuse);',
  '23 ...all three of them'),
 # anchored on the line above it: crossbowbolt_travel is a projectile several npcs fire, and the
 # runner replaces the FIRST match.
 (ALLNPC, 'param=rangebonus,55\nparam=proj_travel,crossbowbolt_travel',
          'param=rangebonus,55',
  '23 ...and he has a bolt to fire'),

 # --- the prayer drain
 (CONST, '^barrows_drain_interval = 30', '^barrows_drain_interval = 50',
  '24 a face appears every 30 ticks'),
 (CONST, '^barrows_drain_base = 8', '^barrows_drain_base = 7',
  '24 and takes 8 points before any brother is down'),
 (COMBAT, 'add(^barrows_drain_base, ~barrows_brothers_killed)', '^barrows_drain_base',
  '24 and the rise is one point per brother'),
 (COMBAT, 'inzone(^barrows_crypt_sw, ^barrows_crypt_ne, coord) = ^false\n    & ', '',
  '24 it drains in the crypts AND the tunnels'),
 (COMBAT, 'cleartimer(barrows_prayer_drain);\n    return;', 'return;',
  '24 ...and takes itself off the moment the player is anywhere else'),
 (RS2, '~barrows_drain_start;\n', '',
  '24 both ways underground start it'),
 (CONST, '^barrows_crypt_sw = 3_55_151_0_0', '^barrows_crypt_sw = 3_55_152_0_0',
  '24 and the two zones really are one square at two levels'),
 # --- the doors
 (ALLLOC, '[barrows_door_c_r]\ncategory=double_door_open_and_close_right',
          '[barrows_door_c_r]\ncategory=double_door_open_and_close_left',
  '25 barrows_door_c_r wears the r double-door category'),
 (ALLLOC, 'param=next_loc_stage,barrows_door_inactive_r',
          'param=next_loc_stage,barrows_door_unlocked_r',
  '25 ...and opens into barrows_door_inactive_r'),
 (TUN, '~open_and_close_double_door(~check_axis_locactive(coord), $side);', 'p_teleport(coord);',
  "25 the door is opened by the game's own double-door proc"),
 (TUN, '~open_and_close_double_door(~check_axis_locactive(coord), $side);\n~barrows_door_spawn(coord);',
        '~barrows_door_spawn(coord);\n~open_and_close_double_door(~check_axis_locactive(coord), $side);',
  '25 and what comes through does so after the door is open'),
 (ALLLOC, '[barrows_door_inactive_l]\nname=Door', '[barrows_door_inactive_l]\nop1=Open\nname=Door',
  '25 and the opened form carries no option'),

 # --- the armour sets
 (ALLOBJ, '[barrows_guthan_body]\nparam=barrows_set,3',
          '[barrows_guthan_body]\nparam=barrows_set,4',
  '26 barrows_guthan_body carries set 3'),
 (ALLOBJ, '[barrows_torag_weapon]\nparam=barrows_set,5\n',
          '[barrows_torag_weapon]\n',
  '26 barrows_torag_weapon carries set 5'),
 (ALLOBJ, '[barrows_karil_head_50]\nname=Karils coif 50',
          '[barrows_karil_head_50]\nparam=barrows_set,4\nname=Karils coif 50',
  '26 nothing outside the twenty-four carries a set id'),
 (CONST, '^barrows_set_guthan = 3', '^barrows_set_guthan = 7',
  '26 guthan is set 3, which is his bit plus one'),
 (CONST, '^barrows_set_effect_pct = 25', '^barrows_set_effect_pct = 20',
  '26 five of the six fire on 25% of qualifying hits'),
 (SETS, 'if (~barrows_set_piece(^wearpos_rhand) ! $set) {\n    return(^false);\n}\n', '',
  '26 a full set means the rhand slot too'),
 (SETS, 'def_int $set = oc_param($item, barrows_set);\nif ($set ! 0) {\n    return($set);\n}\n', '',
  '26 ...and a piece is asked for its set first'),
 (SETS, 'if ($item = null) {\n    return(0);\n}\n', '',
  '26 and an empty slot is answered before anything is asked of it'),
 (SETS, 'divide(multiply(multiply($maxhit, $missing), $max), 10000)',
         'divide(multiply($maxhit, $missing), 100)',
  "26 Dharok's bonus is maxhit x missing x maximum / 10000"),
 (SETS, 'if ($missing <= 0) {\n    return($maxhit);\n}\n', '',
  '26 and a player at full health gets nothing'),
 (SETS, '$style = ^magic_style & ~barrows_set_worn(^barrows_set_ahrim) = ^true\n    & random(100)',
         '~barrows_set_worn(^barrows_set_ahrim) = ^true\n    & random(100)',
  "26 Ahrim's drain answers only to a magic hit, on the monster path"),
 (SETS, 'npc_statsub(strength, ^barrows_ahrim_strength_drain, 0);',
         'npc_statsub(defence, ^barrows_ahrim_strength_drain, 0);',
  "26 Ahrim's five levels come off a monster with npc_statsub"),
 (SETS, '.healenergy(sub(0, scale(^barrows_torag_energy_pct, 100, .runenergy)));',
         '.healenergy(sub(0, ^barrows_torag_energy_pct));',
  "26 and Karil's fifth of Agility and Torag's fifth of the energy LEFT"),
 (SETS, 'if ($damage <= 0) {\n    return;\n}\nif ($style = ^magic_style & ~barrows_set_worn(^barrows_set_ahrim)',
         'if ($style = ^magic_style & ~barrows_set_worn(^barrows_set_ahrim)',
  '26 and nothing fires on a hit that did not land'),
 (PMELEE, '~barrows_set_hit_npc($damage_capped, %damagetype);', '',
  '26 the player melee path fires the sets'),
 (PMAGIC, '~barrows_set_hit_npc($damage_capped, ^magic_style);',
           '~barrows_set_hit_player($damage_capped, ^magic_style);',
  '26 and no monster path fires the player version'),
 (PMELEE, '$maxhit = ~barrows_dharok_maxhit($maxhit);\n', '',
  "26 Dharok's scaling is on both melee paths"),
 (PMELEE, '| ~barrows_verac_ignores = true) {', ') {',
  "26 Verac's pierce is an alternative to the monster hit roll"),
 (VMELEE, '^melee_style) = true & $verac = false', '^melee_style) = true',
  '26 ...and in pvp it skips the 40% prayer reduction as well'),
 (PRANGED, '~barrows_set_hit_npc($damage_capped, %damagetype);', '',
  '26 the player ranged path fires the sets'),
 # --- the reward window
 (INVCFG, '[barrows_reward_store]\nscope=perm', '[barrows_reward_store]\nscope=temp',
  '27 ...and is scope=perm'),
 (INVCFG, 'size=8', 'size=6',
  '27 it has room for every roll one chest can make'),
 ('pack/inv.pack', '414=barrows_reward_store\n', '',
  '27 and it is in pack/inv.pack'),
 # A mutation to the GENERATOR can only ever be caught by byte-identity, because the battery
 # re-runs it in place before any other check reads the window - the same wall poh_mutate_spec.py
 # was written for. The "every option has a handler" check is mutation-tested from the SCRIPT side
 # instead, by taking one [inv_button] away.
 (GENCHEST, "colour='0xFFFF00')", "colour='0x00FF00')",
  '27 and the window it writes is byte-identical to the one in the tree'),
 (GENCHEST, "com('takeall', type='text'", "com('takeall', type='rect'",
  '27 and the window it writes is byte-identical to the one in the tree'),
 (CHEST, '[inv_button3,barrows_chest:loot] ~barrows_reward_bank(last_slot);\n', '',
  '27 the grid\'s option3 ("Bank") is handled'),
 (CHEST, '[if_button,barrows_chest:takeall] ~barrows_reward_takeall;\n', '',
  '27 and so is the Take everything button'),
 (CHEST, '~barrows_reward_flush;\ndef_int $rolls', 'def_int $rolls',
  '27 the flush survives in exactly one place, immediately before a new chest rolls'),
 (CHEST, 'if ($take <= 0) {\n    mes("You do not have enough room to take that.");\n    return;\n}\n',
          '',
  '27 a stack that will not fit at all says so and stays put'),
 (CHEST, '~barrows_reward_add(coins,', '~obj_giveorbank(coins,',
  '27 nothing goes straight to the pack or the bank any more'),
 (CHEST, 'inv_transmit(barrows_reward_store, barrows_chest:loot);\n', '',
  '27 and the script transmits one into the other'),
 # THE SECOND TRANSMIT, and it needs the proc header in the pattern to reach it: the replace above
 # takes the FIRST occurrence, and for a while that was the only one either side tested. Deleting
 # one while the other stood is exactly what walked through the old blanket check.
 (CHEST, '[proc,barrows_chest_reopen]\ninv_transmit(barrows_reward_store, barrows_chest:loot);\n',
         '[proc,barrows_chest_reopen]\n',
  '27 reopening transmits and opens and does NOT roll again'),

 # --- the door before the chest
 (CONST, '^barrows_puzzles = 8', '^barrows_puzzles = 6',
  "28 %barrows_puzzle's 3 bits hold exactly"),
 (VARBIT, '[barrows_puzzle_solved]\nbasevar=barrows\nstartbit=4\nendbit=4',
          '[barrows_puzzle_solved]\nbasevar=barrows\nstartbit=9\nendbit=9',
  '28 barrows_puzzle_solved sits in %barrows bit 4'),
 (PUZZLE, '~barrows_shift;\nreturn(^false);', 'return(^false);',
  '28 the right answer opens the door for the run and a wrong one shifts the tunnels'),
 (PUZZLE, '%barrows_puzzle_solved = ^false;\n', '',
  '28 a shift re-lays the maze, re-rolls the puzzle and locks the door again'),
 (PUZZLE, 'if (%barrows_entry_crypt = ^barrows_entry_none) {\n    return(^true);\n}\n', '',
  '28 ...and a door opened with no run behind it asks nothing'),
 (TUN, '[oploc1,barrows_door_j_l] ~barrows_door_puzzle(^left);',
        '[oploc1,barrows_door_j_l] ~barrows_door_open(^left);',
  '28 both halves of gate j ask it'),
 (TUN, '[oploc1,barrows_door_c_l] ~barrows_door_open(^left);',
        '[oploc1,barrows_door_c_l] ~barrows_door_puzzle(^left);',
  '28 and those are the four that ask the puzzle'),
 (TUN, 'if (~barrows_puzzle_gate = ^false) {\n    return;\n}\n', '',
  '28 and a wrong answer means the door does not open at all'),
 (TUN, '%barrows_puzzle = random(^barrows_puzzles);\n    ~mesbox("You have found', '~mesbox("You have found',
  '28 the puzzle is rolled with the maze, on the way in'),
 # ---- Karil's OSRS crossbow animation
 (ANIMSPEC, '"delays_identical": true', '"delays_identical": false',
  "ahrim: the 377 animation is OSRS's frame for frame"),
 (ALLNPC, 'param=attack_anim,barrows_quarterstaff_attack',
          'param=attack_anim,osrs_karil_crossbow_fire',
  '...and ahrim still names it'),
 (ANIMSPEC, '"cache377_frames": 7', '"cache377_frames": 22',
  'Karil is the exception: 377 gives the crossbow'),
 (XBOWSEQ, '[osrs_karil_crossbow_fire]', '[osrs_karil_crossbow_fire_gone]',
  '[osrs_karil_crossbow_fire] is in the generated .seq config'),
 (SEQPACK, '=osrs_karil_crossbow_run\n', '=osrs_karil_crossbow_run_gone\n',
  '...and registered in pack/seq.pack, or nothing can name it'),
 (XBOWSEQ, 'frame22=anim_osrs_11654_1\ndelay22=3\n', '',
  "...with OSRS seq 2075's 22 frames"),
 # the one that is not cosmetic: a converted frame's own baked delay is 1, so a missing delay
 # line does not fall back to OSRS's timing - it falls back to playing the animation flat out
 (XBOWSEQ, 'frame8=anim_osrs_11654_8\ndelay8=6', 'frame8=anim_osrs_11654_8',
  "...and a delay line per frame, equal to OSRS's"),
 (XBOWSEQ, 'delay1=21', 'delay1=7',
  "...and a delay line per frame, equal to OSRS's"),
 (ANIMPACK, '=anim_osrs_11654_15\n', '=anim_osrs_11654_15_gone\n',
  '...and every frame it names is in pack/anim.pack'),
 (XBOWSEQ, '// OSRS seq 2075\nwalkmerge', '// OSRS seq 2075\npriority=1\nwalkmerge',
  "...and OSRS's priority, once"),
 (XBOWSEQ, '[osrs_karil_crossbow_walk]\n// OSRS seq 2076',
           '[osrs_karil_crossbow_walk]\n// OSRS seq 2076\npriority=6',
  "...and OSRS's priority, once"),
 (SETPACK, '=anim_osrs_11654\n', '=anim_osrs_11654_gone\n',
  '...and is registered in pack/animset.pack'),
 (BASEPACK, '=base_osrs_11654\n', '=base_osrs_11654_gone\n',
  '...and its base in pack/base.pack'),
 (ALLOBJ, '[barrows_karil_weapon_50]', '[barrows_karil_weapon_50x]',
  'the crossbows that can be held are exactly the five checked above'),
 (ALLOBJ, 'param=rangeattack_anim,osrs_karil_crossbow_fire\nparam=defend_anim,human_unarmedblock\n'
          'param=rangeattack_sound,crossbow\nparam=damagetype,^ranged_style\n'
          'param=ready_baseanim,osrs_karil_crossbow_ready',
          'param=rangeattack_anim,osrs_karil_crossbow_fire\nparam=defend_anim,human_unarmedblock\n'
          'param=rangeattack_sound,crossbow\nparam=damagetype,^ranged_style\n'
          'param=ready_baseanim,barrows_repeating_crossbow_ready',
  'nothing still points at the 377 crossbow animations'),
 # the degrade states, one at a time: the 25% bow left behind is the failure this group exists for
 (ALLOBJ, '[barrows_karil_weapon_25]\nname=Karils x-bow 25',
          '[barrows_karil_weapon_25]\nname=Karils x-bow 25\nparam=rangeattack_anim,barrow_dharok_slash',
  'barrows_karil_weapon_25 fires with the OSRS animation'),
 (ALLOBJ, '[barrows_karil_weapon_broken]\nname=Karils x-bow 0',
          '[barrows_karil_weapon_broken]\nname=Karils x-bow 0\nparam=ready_baseanim,human_dh_weapon_ready',
  '...and the one that cannot names no animation at all'),
 (ALLOBJ, '// walk-merges two frames built on the same skeleton (Model.java: "if (!sameSkeleton(...))"',
          '// walk-merges two frames built on the same base',
  'and the obj records why the whole set had to move'),
 (ALLOBJ, '[barrows_karil_ammo]\nname=Bolt rack', '[barrows_karil_ammo]\nname=Bolt bundle',
  "...and it really is the bolt rack"),
 # anchored on the line above it: 'param=proj_travel,crossbowbolt_travel' appears on THREE npcs
 # in all.npc, and the unanchored version of this mutation edited one of the other two and was
 # quite correctly not caught. param=rangebonus,55 is Karil's alone.
 (ALLNPC, 'param=rangebonus,55\nparam=proj_travel,crossbowbolt_travel',
          'param=rangebonus,55\nparam=proj_travel,crossbowbolt_launch',
  '...and Karil fires exactly that, so the two cannot drift'),
 # ---- the crash: banking the chest's remainder from an if_close, which has no protected access
 (CHEST, 'inv_stoptransmit(barrows_chest:loot);\n', 'inv_stoptransmit(barrows_chest:loot);\n~barrows_reward_flush;\n',
  'closing the window does NOT bank the remainder inline'),
 # ---- and the fix for that crash, which let a MONSTER bank your loot by closing the window
 (CHEST, 'inv_stoptransmit(barrows_chest:loot);\n',
         'inv_stoptransmit(barrows_chest:loot);\nqueue(barrows_reward_bank_rest, 0, 0);\n',
  'and does not queue it either: the chest keeps what it paid until you take it'),
 # the flush escaping back out of the one place it belongs
 (CHEST, '~barrows_reward_flush;\ndef_int $rolls',
         '~barrows_reward_flush;\n~barrows_reward_flush;\ndef_int $rolls',
  'the flush survives in exactly one place, immediately before a new chest rolls'),
 # handing the loot back AFTER banking it, which is the same bug with extra steps
 (CHEST, 'if (~barrows_reward_held > 0) {\n        ~barrows_chest_reopen;\n        return;\n    }\n',
         '',
  'and a chest that has already paid hands its loot back before anything is banked'),
 (CHEST, '    ~barrows_chest_reopen;\n', '    mes("The chest is empty.");\n',
  'by reopening the window, so being attacked costs you nothing but the walk back'),
 # "is there anything left" answered from a varp instead of from the store it is about
 (CHEST, 'if (inv_getobj(barrows_reward_store, $slot) ! null) {',
         'if (%barrows_chest_paid = ^true) {',
  'and "is there anything left" is asked of the store itself, slot by slot'),
 # a reopen that rolls again - a second chest for the price of being interrupted
 (CHEST, '[proc,barrows_chest_reopen]\ninv_transmit',
         '[proc,barrows_chest_reopen]\n~barrows_reward_roll(1, 1);\ninv_transmit',
  'reopening transmits and opens and does NOT roll again'),
 (CHEST, '~barrows_reward_flush;\ndef_int $rolls', 'def_int $rolls',
  'the flush survives in exactly one place, immediately before a new chest rolls'),

 # ---- the picture puzzle
 # the .if rather than the enum: this moves the answer SHAPE and leaves the enum and the spec
 # agreeing with each other, which is the only way to reach the third of the three checks alone
 (PZIF, '[set0pick0]\nlayer=set0\ntype=graphic\nx=172\ny=172\nwidth=32\nheight=32\ngraphic=barrows_puzzle,4',
        '[set0pick0]\nlayer=set0\ntype=graphic\nx=172\ny=172\nwidth=32\nheight=32\ngraphic=barrows_puzzle,0',
  '...and that slot is the one holding the right shape'),
 (PZENUM, 'default=-1', 'default=0',
  '...and a default of -1, so a puzzle number nothing matches can never be answered right'),
 (PZENUM, 'val=7,1\n', '',
  '...and the answer table is keyed 0..7, which is what random() rolls'),
 (PZENUM, 'val=2,2', 'val=2,1',
  'and the right answer is not always in the same place - every slot is the answer at least twice'),
 # the spec's own slot field, which nothing used to read
 (PZSPEC, '"slot": 0,\n      "candidates"', '"slot": 1,\n      "candidates"',
  '...and the spec agrees with itself: candidate'),
 (PZIF, '[set0pick0]\nlayer=set0\ntype=graphic', '[set0pick0]\nlayer=set0\ntype=rect',
  'puzzle 0 draws its three candidates in the order the spec says'),
 (PZIF, '[set3]\ntype=layer', '[set3]\ntype=graphic',
  'puzzle 3 lives in a layer, because if_sethide only works on those'),
 (PUZZLE, 'if_sethide(barrows_puzzle:set5, ^true);\n', '',
  'showing a puzzle hides all 8 layers first'),
 (PUZZLE, '    case 6 : if_sethide(barrows_puzzle:set6, ^false);\n', '',
  '...and every puzzle number can then show its own'),
 (PUZZLE, 'if_addresumebutton(barrows_puzzle:pick2);\n', '',
  '...and slot 2 is registered as a resume button, or clicking it does nothing'),
 (PUZZLE, 'if_openmain(barrows_puzzle);', 'if_openchat(barrows_puzzle);',
  'the puzzle opens as a main modal'),
 (PUZZLE, 'p_pausebutton;', 'p_delay(1);',
  '...and p_pausebutton suspends the script until one is clicked'),
 (PUZZLE, '    case barrows_puzzle:pick2 : return(~barrows_puzzle_right(2));\n}\nreturn(-1);',
          '    case barrows_puzzle:pick2 : return(~barrows_puzzle_right(2));\n}\nreturn(0);',
  'closing the window without answering returns -1, not a wrong answer'),
 (PUZZLE, 'if ($answer = -1) {\n    return(^false);\n}\n', '',
  '...and the gate returns without shifting the tunnels, so a misclick on Close costs nothing'),
 (PUZZLE, 'if ($pick = enum(int, int, barrows_puzzle_answer, %barrows_puzzle)) {',
          'if ($pick = 1) {',
  'the pick is judged against the generated table, not a number written twice'),
 (PZOPT, '32x32', '16x16',
  '...and its .opt splits it into 32x32 tiles, or every index is wrong'),
 (PZSPEC, '"cols": 6', '"cols": 4',
  '...and the sheet is as many tiles wide as the spec says'),
 (PZGEN, "raise SystemExit('puzzle %d offers its answer twice' % i)", 'pass',
  'the generator refuses to emit a puzzle whose answer is also one of its wrong options'),
 (PZGEN, "raise SystemExit('slot %d is the answer in only %d puzzle(s) - too guessable'", "print('slot %d is the answer in only %d puzzle(s) - fine'",
  '...or a set where one slot is almost never the answer'),
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
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'barrows_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state = 'red'
            note = 'caught by its own check' + ('' if len(fired) == 1
                                                else ' (and %d others)' % (len(fired) - 1))
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:56] if fired else 'a non-zero exit with no check named, which is a crash '
                                            'and not a catch')
            loose += 1
        print('  %-5s %-70s %s' % (state, why, note))
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
