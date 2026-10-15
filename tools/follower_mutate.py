#!/usr/bin/env python3
"""Mutation test for tools/follower_battery.py. Same runner as pet_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed, not that the check aimed at it works.

    python3 tools/follower_mutate.py [filter]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'follower_mutate_work')

FOL = 'scripts/npc/scripts/follower.rs2'
CAT = 'scripts/quests/quest_fluffs/scripts/pet.rs2'
BOSS = 'scripts/npc/scripts/boss_pets.rs2'
SKILL = 'scripts/npc/scripts/skill_pets.rs2'
EXCH = 'scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2'
LOGIN = 'scripts/login_logout/scripts/login.rs2'
LOGOUT = 'scripts/login_logout/scripts/logout.rs2'
DEATH = 'scripts/player/scripts/death.rs2'
PRS2 = 'scripts/npc/scripts/probita.rs2'
PNPC = 'scripts/npc/configs/probita.npc'
INV = 'scripts/npc/configs/follower.inv'
IF = 'scripts/npc/interfaces/probita_main.if'
MAP = 'maps/m40_51.jm2'
SPEC = 'tools/followerspec.json'
PETOBJ = 'scripts/npc/configs/boss_pets.obj'
BOSSNPC = 'scripts/npc/configs/boss_pets.npc'
FORMNPC = 'scripts/npc/configs/pet_forms.npc'
FORMCONST = 'scripts/npc/configs/pet_forms.constant'
META = 'scripts/npc/scripts/pet_metamorph.rs2'
TALK = 'scripts/npc/scripts/pet_talk.rs2'
VAR = 'scripts/npc/scripts/pet_variants.rs2'
VARENUM = 'scripts/npc/configs/pet_variants.enum'
RCRS2 = 'scripts/skill_runecraft/scripts/runecraft.rs2'
RCTIARA = 'scripts/skill_runecraft/scripts/runecraft_tiaras.rs2'
RCALTARS = 'scripts/skill_runecraft/scripts/runecraft_altars.rs2'
OBJPACK = 'pack/obj.pack'
PICKIF = 'scripts/npc/interfaces/rift_metamorph.if'
FORMCONST2 = FORMCONST
MODELPACK = 'pack/model.pack'
NPCPACK = 'pack/npc.pack'
IFPACK = 'pack/interface.pack'
IFORDER = 'pack/interface.order'

MUTS = [
 # 1 - one owner for the slot
 (FOL, '[proc,follower_spawn](npc $type)', '[proc,follower_spawn2](npc $type)',
  '1 follower_spawn is defined once'),
 (FOL, '[proc,follower_logout]', '[proc,follower_logout2]',
  '1 follower_logout is defined once'),
 (FOL, '[proc,follower_death]', '[proc,follower_death2]',
  '1 follower_death is defined once'),
 (FOL, '\n[queue,follower_login]', '\n[queue,follower_login2]',
  '1 follower_login is defined once'),
 (FOL, '[proc,follower_is_cat](namedobj $item)(boolean)', '[proc,follower_is_cat2](namedobj $item)(boolean)',
  '1 follower_is_cat is defined once'),
 (FOL, '[proc,pet_owned](namedobj $pet)(boolean)', '[proc,pet_owned2](namedobj $pet)(boolean)',
  '1 pet_owned is defined once'),
 (CAT, '[proc,cat_spawn](npc $type)', '[proc,follower_logout]\nreturn;\n\n[proc,cat_spawn](npc $type)',
  '1 the cat quest defines none of them any more'),
 (CAT, '~follower_spawn($type);', 'npc_add(coord, $type, ^max_32bit_int);',
  '1 ...and ~cat_spawn claims the slot through ~follower_spawn'),
 (LOGIN, 'queue(follower_login, 0, 0);', '',
  '1 login.rs2 queues follower_login'),
 (LOGOUT, '~follower_logout;', '',
  '1 logout.rs2 calls ~follower_logout'),
 (DEATH, '~follower_death;', '',
  '1 death.rs2 calls ~follower_death'),
 (FOL, '%follower_uid = npc_uid;\n%npc_attacking_uid = uid;',
        '%follower_uid = npc_uid;\n%follower_uid = npc_uid;\n%npc_attacking_uid = uid;',
  '1 the slot is claimed once in npc/scripts/follower.rs2'),
 (BOSS, '~follower_spawn($type);', '~follower_spawn($type);\n%follower_uid = npc_uid;',
  '1 every other write of it follows an npc_changetype_keepall on the line before'),
 (BOSS, '~follower_spawn($type);', '~follower_spawn($type);\nnpc_setmode(playerfollow);',
  '1 and the pets and the metamorphosis no longer set follow mode themselves'),

 # 2 - no pet gets cat behaviour
 (SPEC, '"cat_categories": [\n    "kitten",', '"cat_categories": [\n    "bosspet",\n    "kitten",',
  '2 ~follower_is_cat names exactly the cat categories'),
 (FOL, ' | oc_category($item) = overgrown', '',
  '2 ~follower_is_cat names exactly the cat categories'),
 (PETOBJ, 'category=bosspet\nparam=follower_id,bosspet_kbd',
          'category=cat\nparam=follower_id,bosspet_kbd',
  '2 ...and not one of the 20 pet items carries a cat category'),
 (SPEC, '"pet_items": 20', '"pet_items": 19',
  '2 there are 20 pet items outside the cat system'),
 (FOL, 'if (~follower_is_cat(%follower_obj) = true) {\n    npc_say("Meeeew!");',
        'npc_say("Meeeew!");\nif (~follower_is_cat(%follower_obj) = true) {',
  '2 the login respawn puts the miaow and the growth timer behind ~follower_is_cat'),
 (FOL, 'if (oc_param(%follower_obj, follower_id) = null) {\n    %follower_obj = null;\n    return;\n}',
        'if (oc_param(%follower_obj, follower_id) = 0) {\n    %follower_obj = null;\n    return;\n}',
  '2 ...and empties the slot rather than spawning null when the item is no longer a follower'),
 (CAT, '~follower_spawn($type);\nnpc_say("Miaow!");',
        '~follower_spawn($type);\nnpc_say("Miaow!");\nsettimer(petcat_growth, 150);',
  '2 petcat_growth is started in exactly two places'),
 (CAT, '    if (~follower_is_cat(nc_param(npc_type, pet_item_id)) = false) {\n'
       '        cleartimer(petcat_growth);\n        return;\n    }\n', '',
  '2 the growth timer clears itself for a follower that is not a cat'),
 (CAT, '    if (~follower_is_cat(nc_param(npc_type, pet_item_id)) = false) {\n'
       '        cleartimer(petcat_growth);\n        return;\n    }\n'
       '    def_category $cat_cat = oc_category(nc_param(npc_type, pet_item_id));',
       '    def_category $cat_cat = oc_category(nc_param(npc_type, pet_item_id));\n'
       '    if (~follower_is_cat(nc_param(npc_type, pet_item_id)) = false) {\n'
       '        cleartimer(petcat_growth);\n        return;\n    }',
  '2 ...and it does that BEFORE it reads the cat growth stage'),

 # 3 - death
 (FOL, 'def_namedobj $pet = %follower_obj;\n%follower_uid = null;\n%follower_obj = null;',
        '%follower_uid = null;\n%follower_obj = null;\ndef_namedobj $pet = %follower_obj;',
  '3 death remembers which pet it was before it empties the slot'),
 (FOL, 'inv_add(lostpet_store, $pet, 1);', '',
  '3 ...and puts it in lostpet_store, on the far side of the cat test'),
 (FOL, '    %cat_growth = 0;\n', '',
  '3 ...while a cat still goes for good, growth and all'),
 (FOL, 'mes("Your pet is waiting for you at Probita\'s in East Ardougne.");',
        'mes("Your pet has wandered off.");',
  '3 ...and the player is told where the pet went'),
 (FOL, 'inv_add(lostpet_store, $pet, 1);',
        'inv_add(lostpet_store, $pet, 1);\ninv_del(lostpet_store, $pet, 1);',
  '3 nothing in the lifecycle takes a pet back OUT of the store'),

 # 4 - one answer to "owns this pet"
 (FOL, 'if (~obj_gettotal($pet) > 0) {\n    return(true);\n}\n', '',
  '4 ~pet_owned counts the pack, the bank and what you are wearing'),
 (FOL, 'if (%follower_obj = $pet) {\n    return(true);\n}\n', '',
  '4 ~pet_owned counts what is following you'),
 (FOL, 'if (inv_total(lostpet_store, $pet) > 0) {\n    return(true);\n}\n', '',
  '4 ~pet_owned counts what Probita is holding'),
 (BOSS, 'if (~pet_owned($pet) = true) {\n    return;\n}',
        'if (~obj_gettotal($pet) > 0) {\n    return;\n}\nif (%follower_obj = $pet) {\n    return;\n}',
  '4 the boss pet roll gives its pet through ~pet_receive'),
 (SKILL, 'if (~pet_owned($pet) = true) {\n    return;\n}',
        'if (~obj_gettotal($pet) > 0) {\n    return;\n}\nif (%follower_obj = $pet) {\n    return;\n}',
  '4 the skilling pet roll gives its pet through ~pet_receive'),
 (EXCH, 'return(~pet_owned($pet));',
        'if (%follower_obj = $pet) {\n    return(true);\n}\nreturn(false);',
  '4 the Fight Cave exchange gives its pet through ~pet_receive'),

 # 5 - Probita
 (PNPC, '\nop3=Check', '\nop3=Reclaim',
  "5 her ops are the cache's own"),
 (PNPC, 'wanderrange=0', 'wanderrange=5',
  '5 ...she has no combat level and does not wander off'),
 (PNPC, 'readyanim=human_ready', 'readyanim=human_walk_f',
  '5 ...and moves on the 377 human animations, like the estate agent'),
 (NPCPACK, '=probita\n', '=probita_npc\n',
  '5 ...and a line in npc.pack'),
 (PNPC, 'model7=npc_probita_7\n', '',
  '5 her record names 7 models and 2 chatheads'),
 (MODELPACK, '=npc_probita_3\n', '=npc_probita_three\n',
  '5 ...every one of them packed and on disk'),
 (SPEC, '"npc_probita_head2":', '"npc_probita_head2_renamed":',
  "5 ...and every one is OSRS npc 5906's own art, re-encoded"),
 (MAP, '0 58 29: 3947', '0 58 30: 3947',
  '5 she is spawned exactly once, at [0, 58, 29]'),
 (SPEC, '"aemad_tile": [\n      0,\n      53,\n      30\n    ]',
        '"aemad_tile": [\n      0,\n      53,\n      31\n    ]',
  "5 ...in the same map square as Aemad's Adventuring Supplies"),
 (SPEC, '"reach": 6', '"reach": 3',
  '5 ...and 5 tiles from him'),
 (MAP, '\n==== NPC ====', '\n0 58 29: 1088\n\n==== NPC ====',
  '5 ...on a tile with nothing standing on it'),

 # 6 - the window
 (IF, '[pets]', '[petgrid]',
  '6 the window has an inv grid called pets'),
 (IF, 'type=inv\nx=124\ny=106\nwidth=6', 'type=inv\nx=124\ny=106\nwidth=5',
  '6 ...6 slots across by 4 down'),
 (INV, '\nsize=24', '\nsize=20',
  '6 ...and lostpet_store holds exactly as many as the window can show'),
 (SPEC, '"pet_items": 20', '"pet_items": 25',
  '6 ...which is enough for every pet item in the tree'),
 (INV, '\nsize=24', '\nsize=24\nstackall=yes',
  '6 ...saved with the character, and nothing stacks in it'),
 (IF, 'option1=Reclaim', 'option1=Take',
  '6 ...and its one option is Reclaim'),
 (IFPACK, '=probita_main:hint\n', '=probita_main:hint_renamed\n',
  '6 ...with every one of its 80 components'),
 (IFORDER, '\n20045', '',
  '6 interface.order and interface.pack agree exactly'),
 (PRS2, 'if_openmain(probita_main);', '',
  '6 Check opens the window'),
 (PRS2, '[opnpc3,probita] ~probita_open;', '[opnpc2,probita] ~probita_open;',
  '6 ...off op3, which is the op the cache gives her for it'),
 (PRS2, 'inv_transmit(lostpet_store, probita_main:pets);', '',
  '6 ...transmitting the store to the grid'),
 (PRS2, '[if_close,probita_main]\ninv_stoptransmit(probita_main:pets);', '',
  '6 ...and stopping when it closes'),
 (IF, '[subtitle]', '[caption]',
  '6 ...subtitle is set by the script and exists in the .if'),
 (PRS2, 'inv_size(lostpet_store) - inv_freespace(lostpet_store)', 'inv_size(lostpet_store)',
  '6 ~probita_count is the used slots of the store'),
 (PRS2, 'inv_moveitem(lostpet_store, inv, $pet, 1);',
        'inv_del(lostpet_store, $pet, 1);\ninv_add(inv, $pet, 1);',
  '6 ...and it touches only inv_freespace, inv_getobj, inv_moveitem'),
 (PRS2, 'if (inv_freespace(inv) = 0) {\n    mes("You don\'t have enough inventory space to take that.");\n    return;\n}\n', '',
  '6 ...refusing without a free slot'),
 (PRS2, 'sound_synth(pick, 1, 0);', 'inv_del(inv, coins, 1);\nsound_synth(pick, 1, 0);',
  '6 nothing in the bureau names a currency - reclaiming is free'),
 # 7 - the metamorphosis rings
 (SPEC, '"pet_records": 51', '"pet_records": 50',
  '7 there are 54 pet npc records, base forms and metamorphosis forms together'),
 (FORMNPC, 'param=metamorph_next,skillpet_chinchompa\n',
           'param=metamorph_next,skillpet_chinchompa_red\n',
  '7 skillpet_chinchompa is a closed ring of 4 forms'),
 (FORMNPC, 'param=pet_item_id,skillpet_heron_item', 'param=pet_item_id,skillpet_rocky_item',
  '7 ...and its forms carry 1 pet item(s)'),
 (FORMNPC, 'op4=Metamorphosis\ncategory=bosspet\nparam=pet_item_id,skillpet_heron_item',
           'category=bosspet\nparam=pet_item_id,skillpet_heron_item',
  '7 ...and every form in it has the right-click'),
 (MODELPACK, '=npc_skillpet_heron_great_blue_1\n', '=npc_skillpet_heron_great_blue_one\n',
  '7 ...and all 4 of their models are packed and on disk'),
 (BOSSNPC, 'op3=Talk-to\ncategory=bosspet\nparam=pet_item_id,bosspet_giant_mole_item',
           'op3=Talk-to\nop4=Metamorphosis\ncategory=bosspet\nparam=pet_item_id,bosspet_giant_mole_item',
  '7 no pet has the right-click without a ring to spend it on'),
 (SPEC, '"skillpet_rift_guardian": {\n      "forms": 15,\n      "items": 1,\n      "bits": [\n        4,\n        7',
        '"skillpet_rift_guardian": {\n      "forms": 15,\n      "items": 1,\n      "bits": [\n        4,\n        5',
  '7 skillpet_rift_guardian has enough of %pet_form to hold its 15 forms'),
 (SPEC, '"skillpet_heron": {\n      "forms": 2,\n      "items": 1,\n      "bits": [\n        1,\n        1',
        '"skillpet_heron": {\n      "forms": 2,\n      "items": 1,\n      "bits": [\n        2,\n        2',
  '7 no two rings share a bit of %pet_form'),
 (FORMCONST, '^pet_form_rift_hi = 7', '^pet_form_rift_hi = 6',
  '7 ...and rift says the same range in pet_forms.constant'),
 (META, '    case skillpet_heron_item :\n        %pet_form = setbit_range_toint', '    case default : %pet_form = setbit_range_toint',
  '7 the two halves of %pet_form name the same items in the same order'),
 (SPEC, '"bosspet_tzrek_jad": {\n      "forms": 2,\n      "items": 2,\n      "bits": null',
        '"bosspet_tzrek_jad": {\n      "forms": 2,\n      "items": 2,\n      "bits": [\n        8,\n        8\n      ]',
  '7 ...and they are exactly the rings whose forms share one item'),
 (META, '~follower_spawn($next);\n', '',
  '7 the right-click spawns the next ALLOWED form through ~follower_spawn'),
 (META, 'if (nc_param($next, pet_item_id) = $item) {\n    ~pet_form_set($item, ~pet_form_index($item, $next));\n}',
        '~pet_form_set($item, ~pet_form_index($item, $next));',
  '7 ...and only remembers a form when the item did not change'),
 (BOSS, 'def_npc $type = ~pet_form(last_item);',
        'def_npc $type = oc_param(last_item, follower_id);',
  '7 and a pet put down comes back in the form it was in, not its base one'),
 (FOL, '~follower_spawn(~pet_form(%follower_obj));',
       '~follower_spawn(oc_param(%follower_obj, follower_id));',
  '2 ...and respawns whatever the slot remembers, in the form it was last put in'),

 # 8 - the dialogue
 (TALK, 'switch_obj (npc_param(pet_item_id))', 'switch_npc (npc_type)',
  '8 talking to a pet dispatches on its ITEM'),
 (TALK, '    case skillpet_beaver_item : ~pettalk_beaver;\n', '',
  '8 all 20 pets have a voice of their own'),
 (TALK, 'case skillpet_beaver_item : ~pettalk_beaver;', 'case skillpet_beaver_item : ~pettalk_beavers;',
  '8 ...and every one of them is a proc that exists'),
 (TALK, '[proc,pettalk_heron]\nswitch_int (random(3))', '[proc,pettalk_heron]\nswitch_int (random(2))',
  '8 ...each with 3 things to say, chosen at random'),
 (TALK, '    case default : ~pettalk_default;\n', '',
  '8 a pet added without a voice falls back to the old line rather than saying nothing'),
 (TALK, '~follower_refollow;', '',
  '8 and the pet goes back to following afterwards'),
 (TALK, '[proc,pettalk_default]', '[proc,pettalk_default]\nnpc_setmode(playerfollow);',
  "8 follow mode is set in the slot's own file, for the cats' vermin hunt in the cat quest, for a teased larupia and for Ivan Strom's escort"),
 # 9 - the looks that are not a right-click
 (VARENUM, 'val=blurite_ore,skillpet_rock_golem_blurite\n', '',
  '9 the golem answers to 11 ores and a plain rock, and nothing else'),
 (OBJPACK, '=blurite_ore\n', '=blurite_ore_renamed\n',
  '9 ...every one of which is a real item in this build'),
 (VARENUM, 'val=rock,skillpet_rock_golem\n', 'val=rock,skillpet_rock_golem_clay\n',
  "9 ...and a plain rock is what puts it back, which is Old School's own way round"),
 (VARENUM, 'val=clay,skillpet_rock_golem_clay', 'val=clay,skillpet_heron',
  "9 ...and every look it names belongs to skillpet_rock_golem's own ring"),
 (VARENUM, 'val=guam_seed,skillpet_tangleroot_herb',
           'val=guam_seed,skillpet_tangleroot_herb\nval=redwood_logs,skillpet_tangleroot_herb',
  '9 the tangleroot answers to acorn and guam_seed and nothing else'),
 (VARENUM, 'val=acorn,skillpet_tangleroot\n', 'val=acorn,skillpet_tangleroot_herb\n',
  '9 ...and an acorn is what puts it back'),
 (VARENUM, 'val=lawrune,skillpet_rift_guardian_f4', 'val=lawrune,skillpet_rift_guardian_f10',
  '9 ...no two altars painting the same colour'),
 (VARENUM, 'val=deathrune,skillpet_rift_guardian_f11\n', '',
  '9 ...and the guardian has a colour for every one of them and for nothing else'),
 (VARENUM, 'val=airrune,skillpet_rift_guardian_f2', 'val=airrune,skillpet_rift_guardian',
  '9 ...so fire paints the base, 7354 - the same guardian a tiara gives, with no altar behind it'),
 (VAR, 'inv_del(inv, $seed, 1);\n', '',
  '9 ...and the seed IS consumed'),
 (VAR, 'def_npc $form = enum(obj, npc, golem_ore_form, $ore);',
       'def_npc $form = enum(obj, npc, golem_ore_form, $ore);\ninv_del(inv, $ore, 1);',
  '9 the ore is not consumed - it is a sample, not a sacrifice'),
 (VAR, '[opheldu,_bosspet]\n~pet_use_item(last_item, last_useitem, false);\n', '',
  '9 an item can be used on a pet standing in front of you or sitting in your pack'),
 (VAR, 'if ($out = true & npc_finduid(%follower_uid) = true) {',
       'if (npc_finduid(%follower_uid) = true) {',
  '9 ...and only respawned when there is something standing there to respawn'),
 (VAR, '%rift_unlocked = setbit(%rift_unlocked, 0);\n', '',
  '9 bit 0 of %rift_unlocked - the base guardian, the fire one - is always set'),
 (VAR, '%rift_unlocked = setbit(%rift_unlocked,\n    ~pet_form_index(skillpet_rift_guardian_item, ~rift_form($rune)));',
       '%rift_unlocked = setbit(%rift_unlocked, 1);',
  "9 ...and crafting at an altar sets that colour's own bit for good"),
 (VAR, '    if (getbit_range(%pet_form, ^pet_form_rift_locked_lo, ^pet_form_rift_locked_hi) = 0) {\n        // Out and following',
       '    if (1 = 1) {\n        // Out and following',
  '9 a locked guardian still unlocks the colour but is not repainted by the altar'),
 (VAR, 'if (npc_param(pet_item_id) ! skillpet_rift_guardian_item) {\n    ~displaymessage(^dm_default);\n    return;\n}\n', '',
  "9 Locking is the guardian's alone, and says so rather than silently doing nothing"),
 (RCALTARS, '~runecraft_combo_rune(waterrune, water_talisman, mistrune, 6, 80, airrune);',
            '~runecraft_combo_rune(waterrune, water_talisman, mistrune, 6, 80, waterrune);',
  '9 every combination-rune call passes the rune of the altar it stands at'),
 (RCTIARA, '~rift_guardian_roll(null, 1);', '~rift_guardian_roll(airrune, 1);',
  '9 ...and the tiara passes null, so a tiara gives the base guardian, the fire one'),
 (RCRS2, '~rift_guardian_roll($rune, $total_ess);',
         '~skillpet_roll_each(skillpet_rift_guardian_item, runecraft, ^skillpet_rift_guardian_base, $total_ess);',
  '9 runecraft.rs2 rolls the guardian through the wrapper that knows the rune'),
 (META, 'if ($item ! skillpet_rift_guardian_item) {\n    return(true);\n}\n', '',
  '9 only the rift guardian has to earn its colours'),
 (FORMNPC, 'op4=Metamorphosis\nop5=Locking\ncategory=bosspet\nparam=pet_item_id,skillpet_rift_guardian_item\nparam=metamorph_next,skillpet_rift_guardian_f3',
           'op4=Metamorphosis\ncategory=bosspet\nparam=pet_item_id,skillpet_rift_guardian_item\nparam=metamorph_next,skillpet_rift_guardian_f3',
  '9 op5=Locking is on all 15 guardian records and on no other pet'),
 (FORMNPC, 'op3=Talk-to\ncategory=bosspet\nparam=pet_item_id,skillpet_rock_golem_item\nparam=metamorph_next,skillpet_rock_golem_copper',
           'op3=Talk-to\nop4=Metamorphosis\ncategory=bosspet\nparam=pet_item_id,skillpet_rock_golem_item\nparam=metamorph_next,skillpet_rock_golem_copper',
  '9 ...and not one form in it has the right-click, because nothing cycles this pet'),
 (SPEC, '"skillpet_rock_golem": {\n      "forms": 12,\n      "items": 1,\n      "bits": [\n        8,\n        11',
        '"skillpet_rock_golem": {\n      "forms": 12,\n      "items": 1,\n      "bits": [\n        8,\n        9',
  '9 skillpet_rock_golem has enough of %pet_form to hold its 12 forms'),
 (META, '~pet_form_nextallowed($item, npc_type)', 'npc_param(metamorph_next)',
  '7 the right-click spawns the next ALLOWED form through ~follower_spawn'),
 # 9 - the picker window
 (PICKIF, '[cell13]\ntype=layer', '[cell14]\ntype=layer',
  '9 the picker has a cell for the base guardian and for each of the 12 altars, and for nothing else'),
 (PICKIF, 'model=npc_skillpet_rift_guardian_f9_1', 'model=npc_skillpet_rift_guardian_f8_1',
  '9 ...each showing the model of the form at that ring index'),
 (PICKIF, 'text=Nature', 'text=Natures',
  '9 ...and labelled with the altar that unlocks it'),
 (VAR, 'if_sethide(rift_metamorph:icon0, ~rift_locked(0));',
       'if_sethide(rift_metamorph:icon0, ~rift_locked(0));\nif_settext(rift_metamorph:name0, "");',
  '9 the picker has no script-set text'),
 (PICKIF, '[icon0]\nlayer=cell0\ntype=layer\nx=36\ny=16',
          '[icon0]\nlayer=cell0\ntype=layer\nx=36\ny=6',
  '9 every cell of the grid is laid out identically'),
 (PICKIF, '[name0]\nlayer=cell0\ntype=text\nx=0\ny=52',
          '[name0]\nlayer=cell0\ntype=text\nx=0\ny=68',
  '9 ...and the guardian and its label sit centred in it'),
 (IFPACK, '=rift_metamorph:name13\n', '=rift_metamorph:name13_renamed\n',
  '9 ...with every one of its 137 components in interface.pack'),
 (META, '~rift_metamorph_open;\n    return;\n', '',
  "9 the guardian's right-click opens that window instead of cycling"),
 (VAR, 'if_sethide(rift_metamorph:icon7, ~rift_locked(7));\n', '',
  '9 ...and every cell is both hidden when locked and clickable, each naming its own ring index'),
 (VAR, '[if_button,rift_metamorph:hit9] ~rift_pick(9);', '[if_button,rift_metamorph:hit9] ~rift_pick(8);',
  '9 ...and every cell is both hidden when locked and clickable, each naming its own ring index'),
 (VAR, 'if (~rift_locked($index) = true) {\n    mes("You have not unlocked that colour yet. Craft at its altar with your guardian out.");\n    return;\n}\n', '',
  '9 choosing a colour you have not unlocked says so rather than doing nothing'),
 (VAR, '~pet_form_walk(skillpet_rift_guardian_item, $index)',
       '~pet_form(skillpet_rift_guardian_item)',
  '9 ...and a cell is an index into the ring, walked the same way the login respawn walks it'),
 (META, '~rift_locked(~pet_form_index($item, $form))', 'testbit(%rift_unlocked, 0)',
  '9 ...and what it may wear is what %rift_unlocked says, read in exactly one place'),
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
        # The anchor must be UNIQUE in the file. Four mutations in the first run of this harness
        # landed in the file's own COMMENTS - '[queue,follower_login]' and 'size=24' are both
        # written in prose above the code they describe - and a mutation that changes a comment is
        # a green tick that proves nothing. Requiring one match turns that whole class of mistake
        # into a loud skip. Worth backporting to the older harnesses, which all replace the first
        # match and would say nothing.
        n = raw.count(f)
        if n != 1:
            print('  SKIP (pattern %s) %-40s %s'
                  % ('not found' if n == 0 else 'matches %d times' % n,
                     os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'follower_battery.py')],
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
                fired[0][:56] if fired else
                'a non-zero exit with no check named, which is a crash and not a catch')
            loose += 1
        print('  %-5s %-72s %s' % (state, why, note))
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
