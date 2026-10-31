#!/usr/bin/env python3
"""Mutation test for tools/fightcave_battery.py. Same runner as pet_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed.

    python3 tools/fightcave_mutate.py [filter]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'fightcave_mutate_work')

CONST = 'scripts/minigames/game_fightcave/configs/fightcave.constant'
ENUM = 'scripts/minigames/game_fightcave/configs/fightcave.enum'
RS2 = 'scripts/minigames/game_fightcave/scripts/fightcave.rs2'
MRS2 = 'scripts/minigames/game_fightcave/scripts/fightcave_monsters.rs2'
REW = 'scripts/minigames/game_fightcave/scripts/fightcave_reward.rs2'
ALLNPC = 'scripts/_unpack/377/all.npc'
SPEC = 'tools/fightcavespec.json'
SHOP = 'scripts/shop/scripts/shop.rs2'
WALLET = 'scripts/shop/scripts/shop_wallet.rs2'
FOLL = 'scripts/npc/scripts/follower.rs2'
SHOPPARAM = 'scripts/shop/configs/shopkeeper.param'
TRADERS = 'scripts/areas/area_karamja/configs/tzhaar_traders.npc'
INV727 = 'scripts/_unpack/727/all.inv'
PETNPC = 'scripts/npc/configs/boss_pets.npc'
PETOBJ = 'scripts/npc/configs/boss_pets.obj'
CITYMAP = 'maps/m38_80.jm2'
DEATH = 'scripts/player/scripts/death.rs2'
MELEE = 'scripts/skill_combat/scripts/npc/npc_combat_melee.rs2'
XRS2 = 'scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2'
FCOBJ = 'scripts/minigames/game_fightcave/configs/fightcave.obj'
FCSEQ = 'scripts/minigames/game_fightcave/configs/fightcave.seq'
ALLSEQ = 'scripts/_unpack/377/all.seq'
MODELPACK = 'pack/model.pack'
TEXPACK = 'pack/texture.pack'
NPCPACK = 'pack/npc.pack'

MUTS = [
 # 1 - the arena, and a spawn a five-tile monster cannot stand on
 (CONST, '^fightcave_entry = 0_37_79_44_61', '^fightcave_entry = 0_37_79_44_62',
  '1 ^fightcave_entry is the tile the spec measured from, and a tile a player can stand on'),
 (SPEC, '"c": [26, 31]', '"c": [2, 21]',
  '1 the C spawn is a tile a five-tile monster fits on'),
 (CONST, '^fightcave_spawn_nw = 0_37_79_4_56', '^fightcave_spawn_nw = 0_37_79_4_57',
  '1 ...and ^fightcave_spawn_nw is that tile'),
 (CONST, '^fightcave_zones = 8', '^fightcave_zones = 4',
  '1 and the instance copies all 64 tiles of it'),
 (RS2, '[oploc1,loc_9356] @fightcave_enter;\n', '',
  '1 loc_9356 has a handler'),
 # 2 - a monster whose numbers have drifted off the cache
 (ALLNPC, 'strength=960\nhitpoints=250', 'strength=960\nhitpoints=255',
  '2 ...with the cache\'s stats'),
 (ALLNPC, 'param=fightcave_tier,6', 'param=fightcave_tier,5',
  '2 ...tagged tier 6'),
 (ALLNPC, 'param=attack_anim,osrs_seq_2655', 'param=attack_anim,osrs_seq_26555',
  '2 ...attack_anim is a real seq'),
 (MRS2, '[ai_queue3,tzhaar_fightcave_swarm_5a] @fightcave_monster_death;\n', '',
  '2 ...and its death is hooked'),
 # a b duplicate quietly given a tier, which would let it into a wave
 (ALLNPC, '[tzhaar_fightcave_swarm_1b]', '[tzhaar_fightcave_swarm_1b]\nparam=fightcave_tier,1',
  '2 tzhaar_fightcave_swarm_1b is left as the cache left it, so it cannot turn up in a wave'),
 # 3 - the wave table
 (CONST, '^fightcave_tier_tokxil = 7', '^fightcave_tier_tokxil = 8',
  '3 ...and they are the 2^k-1 series'),
 (CONST, '^fightcave_tier_tzkih = 1', '^fightcave_tier_tzkih = 2',
  '3 every wave from 1 to 62 terminates'),
 (SPEC, '"15": [4]', '"15": [3]',
  '3 wave 15 is the wiki\'s: [4]'),
 (ENUM, 'val=3,tzhaar_fightcave_swarm_3a', 'val=3,tzhaar_fightcave_swarm_3aa',
  '3 each tier names an npc that exists'),
 (CONST, '^fightcave_waves = 63', '^fightcave_waves = 64',
  '3 and wave 63 is TzTok-Jad, alone'),
 (ENUM, 'val=6,4\nval=7,3', 'val=6,3\nval=7,3',
  '3 ...in the order the wiki gives: SE SW C NW SW SE S NW C SE SW S NW C S'),
 (CONST, '^fightcave_cycle = 15', '^fightcave_cycle = 14',
  '3 the spawn cycle is 15 steps long: 15'),
 # 4 - the instance
 (CONST, '^fightcave_npc_life = 30000', '^fightcave_npc_life = 0',
  '4 ...which is not 0, because DurationValid rejects that at RUNTIME'),
 (MRS2, 'tzhaar_fightcave_swarm_boss_cleric, ^fightcave_npc_life);',
        'tzhaar_fightcave_swarm_boss_cleric, 0);',
  '4 fightcave_monsters.rs2 adds no npc with a 0 duration'),
 (RS2, ' & instance_find(npc_coord) = %fightcave_instance', '',
  '4 ...AND the instance, so the cave next door cannot hold this wave open'),
 (RS2, '''p_teleport(^fightcave_outside);
// The player is out before the instance goes: anyone still inside is standing on unallocated
// collision, which blocks every step they try to take.
instance_delete($inst);''', '''instance_delete($inst);
p_teleport(^fightcave_outside);''',
  '4 the player is teleported out before the instance is deleted, not after'),
 (RS2, '''            instance_delete($base);
''', '',
  '4 a half-built cave is deleted rather than entered'),
 (MRS2, 'queue*(fightcave_died, 0)(npc_uid);', 'npc_setmode(none);',
  '4 a monster\'s death reaches the player through a queue, which is where the protected pointer is'),
 # 5 - the rewards
 (CONST, '^fightcave_tokkul_jad = 4000', '^fightcave_tokkul_jad = 3000',
  '5 a full run pays 8032 Tokkul, which is the figure the wiki quotes on its own'),
 (REW, 'return(multiply($waves, add($waves, 1)));', 'return(multiply($waves, $waves));',
  '5 and the formula in the script is the wiki\'s N * (N + 1)'),
 (MRS2, '[proc,hurkot_heal_jad]', 'inv_add(inv, tzhaar_cape_fire, 1);\n\n[proc,hurkot_heal_jad]',
  '5 the cave is the ONLY source of a Fire cape'),
 (REW, 'inv_add(bank, $obj, $count);', 'obj_add(coord, $obj, $count, 100);',
  '5 ...and nothing is dropped on the floor of an instance that is about to be deleted'),
 # 6 - the mechanics
 (ALLNPC, 'param=prayer_drain,1\n', '',
  '6 Tz-Kih drains a prayer point'),
 (MELEE, 'queue(fightcave_prayer_drain, 0, npc_param(prayer_drain));',
         'queue(fightcave_prayer_drain, 0, 1);',
  '6 ...and it is param-driven, not keyed on the npc type'),
 (MRS2, '''npc_add(map_findsquare($home, 1, 2, ^map_findsquare_lineofwalk), tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);
npc_setmode(opplayer2);
npc_add(map_findsquare($home, 1, 2, ^map_findsquare_lineofwalk), tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);
npc_setmode(opplayer2);''',
        '''npc_add(map_findsquare($home, 1, 2, ^map_findsquare_lineofwalk), tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);
npc_setmode(opplayer2);''',
  '6 Tz-Kek splits into exactly two'),
 (ALLNPC, 'param=fightcave_tier,2\n\n[tzhaar_fightcave_swarm_3a]', '\n[tzhaar_fightcave_swarm_3a]',
  '6 ...and the halves count towards the wave, so it cannot end with them alive'),
 (MRS2, 'if (multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)) {', 'if (random(2) = 0) {',
  '6 Yt-MejKot only heals once it is below half health'),
 (MRS2, '''~fightcave_melee(npc_param(attack_anim));
// Last, because the heal walks the secondary npc pointer: nothing below may need this npc.
if (multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)) {
    ~fightcave_heal_others;
}''', '''if (multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)) {
    ~fightcave_heal_others;
}
~fightcave_melee(npc_param(attack_anim));''',
  '6 ...and the heal is the last thing it does, because it walks the npc pointer'),
 (MRS2, '.npc_queue(9, ^fightcave_heal_amount, 0);\n    }\n}\n\n// The far end', 'npc_say("heal");\n    }\n}\n\n// The far end',
  '6 both healers heal through a queue on the target, since there is no .npc_statheal'),
 (ALLNPC, 'param=magicattack_anim,osrs_seq_2656', 'param=magicattack_anim,osrs_seq_2652',
  '6 TzTok-Jad has three distinct attack animations'),
 (CONST, '^fightcave_jad_heal_hp = 150', '^fightcave_jad_heal_hp = 250',
  '6 ...which is below his 250, or they would come the moment he spawned'),
 (MRS2, 'if (%fightcave_jad_called = 0 & npc_stat(hitpoints) <= ^fightcave_jad_heal_hp) {',
        'if (npc_stat(hitpoints) <= ^fightcave_jad_heal_hp) {',
  '6 the healers come at 150 hitpoints, once'),
 (CONST, '^fightcave_jad_healers = 4', '^fightcave_jad_healers = 4\n^fightcave_unused = 1'),
 (MRS2, '.npc_type = tzhaar_fightcave_swarm_boss)', '.npc_type = tzhaar_fightcave_swarm_5a)',
  '6 a Yt-HurKot heals Jad and only Jad'),
 (DEATH, 'if (~in_fightcave(coord) = true) {\n    @fightcave_death;\n}\n', '',
  '6 dying in the cave is caught before the ordinary death'),
 (RS2, '''~prayer_deactivate_all;
~fightcave_end(sub(%fightcave_wave, 1));''', '''~prayer_deactivate_all;
~player_death_lose_items;
~fightcave_end(sub(%fightcave_wave, 1));''',
  '6 ...and keeps the player\'s items, because the cave is safe'),
 (RS2, '~fightcave_end(sub(%fightcave_wave, 1));\n~stat_reset_all;',
        '~fightcave_end(%fightcave_wave);\n~stat_reset_all;',
  '6 ...and pays for the waves that were survived, not the one they died on'),
 # 7 - Tokkul, the three shops and the pet
 # The till, what it spends and what it names all moved behind the wallet procs when a shop could
 # be paid in vote points, so these bend the wallet rather than shop.rs2's old inv_total/inv_del.
 (SHOP, 'def_int $current_gp = ~shop_wallet_total;',
        'def_int $current_gp = inv_total(inv, coins);',
  '7 the shop reads its currency for the till it counts'),
 (WALLET, 'return(inv_total(inv, %shop_currency));', 'return(inv_total(inv, coins));',
  '7 ~shop_wallet_total asks which wallet this shop uses and falls through to the obj one'),
 (SHOP, '~shop_wallet_spend($added_amt);', 'inv_del(inv, coins, $added_amt);',
  '7 the shop reads its currency for what it takes'),
 (WALLET, 'inv_del(inv, %shop_currency, $amount);', 'inv_del(inv, coins, $amount);',
  '7 ~shop_wallet_spend asks which wallet this shop uses and falls through to the obj one'),
 (SHOP, 'inv_add(inv, %shop_currency, $total_value);', 'inv_add(inv, coins, $total_value);',
  '7 the shop reads its currency for what it pays'),
 (SHOP, 'inv_itemspace(inv, %shop_currency,', 'inv_itemspace(inv, coins,',
  '7 the shop reads its currency for the space it checks'),
 (SHOP, 'if ($item = %shop_currency) {', 'if ($item = coins) {',
  '7 the shop reads its currency for what it refuses to buy'),
 (SHOP, 'mes("You don\'t have enough <~shop_wallet_name>.");',
        'mes("You don\'t have enough coins.");',
  '7 the shop reads its currency for what it says you are short of, and both prices it quotes'),
 (SHOP, 'mes("<$item_name>: shop will buy for <tostring($item_value)> <~shop_wallet_name>.");',
        'mes("<$item_name>: shop will buy for <tostring($item_value)>gp.");',
  '7 the shop reads its currency for what it says you are short of, and both prices it quotes'),
 (WALLET, 'return(lowercase(oc_name(%shop_currency)));', 'return("coins");',
  '7 ~shop_wallet_name asks which wallet this shop uses and falls through to the obj one'),
 (SHOP, '%shop_currency = npc_param(shop_currency);',
        '%shop_currency = npc_param(shop_currency);\n%shop_currency = coins;',
  '7 ...and the currency is set in exactly those three places and nowhere else'),
 (SHOP, '%shop_currency = coins;\n%shop_wallet = ^shop_wallet_inv;\n', '',
  '7 ~openshop still sets coins, so its 38 callers did not have to change'),
 (SHOP, '%shop_currency = npc_param(shop_currency);\n', '',
  '7 ...and a shopkeeper\'s own shop reads the param'),
 (SHOPPARAM, '[shop_currency]\ntype=namedobj\ndefault=coins',
             '[shop_currency]\ntype=namedobj\ndefault=null',
  '7 ...whose default is coins, so every shopkeeper that predates this keeps its till'),
 # a trader pointed at the wrong shop, or taking the wrong money
 (TRADERS, 'param=owned_shop,tzhaar_shop_rune', 'param=owned_shop,tzhaar_shop_general',
  '7 tzhaar_shopkeeper_rune owns tzhaar_shop_rune'),
 (TRADERS, 'param=shop_currency,tzhaar_token\nparam=shop_sell_multiplier,1000\nparam=shop_buy_multiplier,600\nparam=shop_delta,10\nparam=shop_title,TzHaar-Hur-Tel',
           'param=shop_sell_multiplier,1000\nparam=shop_buy_multiplier,600\nparam=shop_delta,10\nparam=shop_title,TzHaar-Hur-Tel',
  '7 ...and trades in Tokkul'),
 (TRADERS, 'vislevel=hide\nop1=Talk-to\nop3=Trade\ncategory=shop_keeper\nparam=owned_shop,tzhaar_shop_equipment',
           'vislevel=hide\nop1=Talk-to\nop3=Trade\nparam=owned_shop,tzhaar_shop_equipment',
  '7 ...on the category the shop triggers hang off'),
 (TRADERS, 'vislevel=hide\nop1=Talk-to\nop3=Trade\ncategory=shop_keeper\nparam=owned_shop,tzhaar_shop_oreandgem',
           'vislevel=hide\nop1=Talk-to\nop2=Attack\nop3=Trade\ncategory=shop_keeper\nparam=owned_shop,tzhaar_shop_oreandgem',
  '7 ...and cannot be attacked, so you can stand beside it'),
 # the rune shop's numbering, which was broken in the file all along
 (INV727, 'stock6=bodyrune,5000,100', 'stock5=bodyrune,5000,100',
  '7 tzhaar_shop_rune stock numbering has no gaps or duplicates'),
 (INV727, 'stock8=deathrune,250,100', 'stock8=deathrune,250',
  '7 ...and every line has its count and restock rate'),
 (INV727, 'stock1=firerune,5000,100', 'stock1=lavarune,5000,100',
  '7 the rune shop sells the eight runes its own commented-out lines listed'),
 (INV727, 'stock8=tzhaar_cape_obsidian,1,100', 'stock8=tzhaar_cape_fire,1,100',
  '7 ...and the equipment shop the whole obsidian set'),
 (CITYMAP, '0 30 5: 3944\n', '',
  '7 tzhaar_shopkeeper_rune is spawned once in m38_80'),
 # the pet
 (PETNPC, 'param=pet_item_id,bosspet_tzrek_jad_item', 'param=pet_item_id,bosspet_kbd_item',
  '7 ...and the npc names the item'),
 (PETOBJ, 'param=follower_id,bosspet_tzrek_jad', 'param=follower_id,bosspet_kbd',
  '7 ...and the item names the npc'),
 (PETNPC, 'readyanim=osrs_seq_2650\nwalkanim=osrs_seq_5805',
          'readyanim=lordmagmus_ready\nwalkanim=osrs_seq_5805',
  '7 both its animations are converted from OSRS, so they share a base and still walk-merge'),
 (PETNPC, 'resizeh=20\nresizev=20\nreadyanim=osrs_seq_2650',
          'resizeh=40\nresizev=20\nreadyanim=osrs_seq_2650',
  '7 and it is rendered at the cache\'s own 20, which is the joke'),
 (CONST, '^fightcave_pet_rate = 200', '^fightcave_pet_rate = 100',
  '7 ...which is 200, the rate for a plain kill'),
 (FOLL, 'if (~obj_gettotal($pet) > 0) {\n    return(true);\n}\n', '',
  '7 ...which never gives a second one, counting pack, bank, worn, the one out following you'),
 (FOLL, 'inv_add(lostpet_store, $pet, 1);\n    mes("You have a funny feeling like you\'re being followed, but you have no room for it.");',
        'obj_add(coord, $pet, 1, 100);',
  "7 ...and a full pack sends it to Probita's rather than the floor of an instance about to be"),
 (REW, '~pet_receive_later(bosspet_tzrek_jad_item, 1);', '~pet_receive_later(bosspet_tzrek_jad_item, 0);',
  "7 ...and hands it to ~pet_receive, a tick later because Jad's own death is still resolving"),
 (REW, '~fightcave_pet_roll;\n', '',
  '7 and killing Jad is what rolls it'),
 # ---------------------------------------------------------------------------- 8, the OSRS art
 (ALLNPC, 'model1=npc_tztok_jad_1\nsize=5', 'model1=npc_fightcave_tzkih_1\nsize=5',
  "8 tzhaar_fightcave_swarm_boss wears OSRS npc 3127's 1 model(s)"),
 (ALLNPC, 'model3=npc_fightcave_hurkot_3\n', '',
  "8 tzhaar_fightcave_swarm_boss_cleric wears OSRS npc 3128's 3 model(s)"),
 (ALLNPC, 'model1=npc_fightcave_ketzek_1\nmodel2', 'model1=npc_fightcave_ketzek_1\nmodel5=npc_fightcave_ketzek_1\nmodel2',
  '8 ...and no leftover model line from the 377 record it replaced'),
 (MODELPACK, '=npc_fightcave_ketzek_4', '=npc_fightcave_ketzek_44',
  '8 ...each with its own model.pack line'),
 (ALLNPC, 'model1=npc_fightcave_hurkot_1', 'recol1s=6144\nrecol1d=6276\nmodel1=npc_fightcave_hurkot_1',
  '8 ...and no recolour line, because OSRS bakes its recolours into the mesh'),
 (ALLNPC, 'walkanim=osrs_seq_2634\nreadyanim=osrs_seq_2636\nambient=30\ncontrast=30\nresizeh=35',
          'walkanim=osrs_seq_2634\nreadyanim=osrs_seq_2636\nambient=40\ncontrast=30\nresizeh=35',
  "8 ...and its ambient, contrast, size and resizes are the cache's own, unchanged"),
 (ALLNPC, 'readyanim=osrs_seq_2631', 'readyanim=osrs_seq_2632',
  '8 tzhaar_fightcave_swarm_3a.readyanim is osrs_seq_2631, where the 377 record had magmaquris_ready'),
 (FCSEQ, '[osrs_seq_2637]\n// OSRS seq 2637\n', '[osrs_seq_26370]\n// OSRS seq 2637\n',
  '8 ...and osrs_seq_2637 is a real seq in the tree'),
 (FCSEQ, '[osrs_seq_2638]\n// OSRS seq 2638\npriority=10\n', '[osrs_seq_2638]\n// OSRS seq 2638\n',
  '8 ...and agrees with it on whether the animation takes priority at all'),
 (ALLSEQ, '[firebat_death]\npriority=10', '[firebat_death]\npriority=6',
  '8 tzhaar_fightcave_swarm_1a: the 3 animations that had to be inferred'),
 (MRS2, 'npc_anim(osrs_seq_2639, 0);\n.npc_findallany(npc_coord, 10',
        'npc_anim(osrs_seq_2637, 0);\n.npc_findallany(npc_coord, 10',
  '8 ...in BOTH places it is played'),
 (MRS2, '// osrs_seq_2652 rears up', '// lordmagmus_smash rears up',
  '8 and the scripts name no 377 cave animation either'),
 (ALLNPC, 'readyanim=osrs_seq_2624\nwalkanim=osrs_seq_2623\nresizeh=80',
          'readyanim=osrs_seq_2624\nwalkanim=lavabeast_walk\nresizeh=80',
  '8 tzhaar_fightcave_swarm_2spawn.walkanim is osrs_seq_2623'),
 (ALLNPC, '[tzhaar_fightcave_swarm_3b]', '[tzhaar_fightcave_swarm_3b]\nparam=fightcave_tier,3',
  '8 tzhaar_fightcave_swarm_3b has no tier and no spawn'),
 (ALLNPC, 'readyanim=thzaar_staff_ready', 'readyanim=lordmagmus_ready',
  '8 the 377 lordmagmus set is worn by NOTHING AT ALL'),
 (MODELPACK, '=npc_tztok_jad_1', '=npc_bosspet_tzrek_jad_1',
  "8 the old name of Jad's mesh is gone from the pack and the disk"),
 (PETNPC, 'model1=npc_tztok_jad_1', 'model1=npc_bosspet_kril_1',
  '8 ...and TzRek-Jad and TzTok-Jad name the same one file, a resize apart'),
 (FCSEQ, '[osrs_seq_2618]', '[osrs_seq_2650]\nframe1=anim_osrs_12622_1\ndelay1=4\n\n[osrs_seq_2618]',
  '8 fightcave.seq holds 34 seqs and NOT osrs_seq_2650'),
 # ---------------------------------------------------------------------------- 9, the exchange
 (SPEC, '"cape": 300', '"cape": 200',
  '9 ^fightcave_exchange_cape_rate is 300'),
 (SPEC, '"meta": 50', '"meta": 60',
  '9 ^fightcave_exchange_meta_rate is 50'),
 (SPEC, '"pet": 25', '"pet": 30',
  '9 ^fightcave_exchange_pet_rate is 25'),
 # the ladder inverted: a cape commoner than a pet, still rolled first, quietly not the prize.
 # In the SPEC, not the constant, because that is the side the rarest-first check reads - moving the
 # constant fires the constant-equals-spec check above instead and the label lands on the wrong one.
 (SPEC, '"cape": 300', '"cape": 20',
  '9 ...rarest first'),
 (XRS2, 'if (random(^fightcave_exchange_cape_rate) = 0) {\n    ~obj_giveorbank(tzhaar_cape_infernal, 1);',
         'if (random(^fightcave_exchange_pet_rate) = 0) {\n    ~obj_giveorbank(tzhaar_cape_infernal, 1);',
  '9 ...and the roll asks in the order the rates were chosen for'),
 (XRS2, '    ~fightcave_metamorphose;\n        return;', '    ~fightcave_metamorphose;',
  '9 ...with a return after each hit, so a cape cannot pay twice'),
 (CONST, '^fightcave_exchange_tokkul_max = 1000', '^fightcave_exchange_tokkul_max = 1200',
  '9 the consolation is a flat roll between 500 and 1000 Tokkul inclusive'),
 (XRS2, 'inv_del(inv, tzhaar_cape_fire, 1);\n~fightcave_exchange_roll;',
         'inv_del(inv, tzhaar_cape_fire, 1);\ninv_del(inv, tzhaar_cape_fire, 1);\n~fightcave_exchange_roll;',
  '9 exactly one line deletes the Fire cape'),
 (XRS2, 'if (inv_total(inv, tzhaar_cape_fire) < 1) {\n    ~chatnpc("<p,neutral>You carry no cape of fire.");',
         'if (inv_total(inv, tzhaar_cape_fire) > 100) {\n    ~chatnpc("<p,neutral>You carry no cape of fire.");',
  '9 ...once on each side of the pause, and the delete comes after the second one'),
 (ALLNPC, 'op3=Exchange\n', '',
  '9 TzHaar-Mej-Jal has Talk-to and Exchange'),
 (XRS2, '[opnpc1,tzhaar_fightcave_master] @fightcave_talk;\n', '',
  '9 ...and BOTH have a handler now'),
 (XRS2, '@multi3("What is this place?", fightcave_talk_place,\n        "I have a Fire cape to exchange.", fightcave_exchange,',
         '@multi3("What is this place?", fightcave_talk_place,\n        "I have a Fire cape.", fightcave_talk_place,',
  '9 ...and the exchange is reachable from the conversation as well as the right-click'),
 (FCOBJ, 'param=strengthbonus,8', 'param=strengthbonus,4',
  "9 ...param strengthbonus is the cache's 8"),
 (FCOBJ, 'param=magicdefence,12', 'param=magicdefence,11',
  "9 ...param magicdefence is the cache's 12"),
 (FCOBJ, 'cost=80000', 'cost=65000',
  "9 ...and the cost is the cache's 80000"),
 (FCOBJ, '2dzoom=2086\n', '',
  "9 ...and the record is a line-for-line parallel of the Fire cape's"),
 (FCOBJ, '\ntradeable=no', '\ntradeable=yes',
  '9 ...including tradeable=no, which is how this fork ships the Fire cape'),
 (FCOBJ, 'param=prayerbonus,2', 'param=prayerbonus,2\nparam=magicdamage,5',
  '9 ...and it carries exactly the 12 bonuses and no invented thirteenth'),
 (SPEC, '"lava_faces": 30', '"lava_faces": 31',
  '9 the inventory model carries its 30 crust faces'),
 (SPEC, '"wrong_hsl": 12818', '"wrong_hsl": 924',
  '9 ...and no face of it is left on the olive green'),
 (SPEC, '"fire_cape_lava_faces": 25', '"fire_cape_lava_faces": 24',
  '9 and the Fire cape still wears its own 25 lava faces'),
 # the texture slot this fork added
 (TEXPACK, '50=lavacrust', '50=lavacrusty',
  '9 texture 50 is lavacrust in texture.pack'),
 (TEXPACK, '49=canvas\n50=lavacrust', '49=canvas\n51=lavacrust',
  '9 ...and the texture ids are contiguous'),
 (SPEC, '"texture_pixels_sha1": "1f1fd2c9c972380c6db15d4ecdaa4b66a683d00b"',
        '"texture_pixels_sha1": "0000000000000000000000000000000000000000"',
  "9 ...and its pixels are OSRS sprite 318's own, unaltered"),
 (SPEC, '"texture_colours": 204', '"texture_colours": 205',
  '9 ...in 204 colours, under the 255 above which the packer quantises silently'),
 (SPEC, '"obj_tzhaar_cape_infernal_manwear": "f4b94fe215ba2ec1abb42ee111f4f490a60d213f"',
        '"obj_tzhaar_cape_infernal_manwear": "0000000000000000000000000000000000000000"',
  "9 obj_tzhaar_cape_infernal_manwear is the cache's own geometry"),
 (SPEC, '"local_texture": 50', '"local_texture": 40',
  '9 the inventory model carries its 30 crust faces'),
 (PETOBJ, 'param=follower_id,bosspet_jalrek_jad', 'param=follower_id,bosspet_tzrek_jad',
  '9 ...and the two name each other'),
 (NPCPACK, '=bosspet_jalrek_jad\n', '=bosspet_jalrek_jad_notpacked\n',
  '9 JalRek-Jad exists as an npc and an item, both packed'),
 (PETNPC, 'readyanim=osrs_seq_7589', 'readyanim=osrs_seq_7590',
  "9 ...wearing the cache's own pair"),
 (PETNPC, 'ambient=-10', 'ambient=0',
  "9 ...at the cache's resize 20 and ambient -10"),
 (XRS2, 'return(~pet_owned($pet));', 'return(false);',
  '9 "do they have this pet" delegates to ~pet_owned, the one answer in the tree'),
 (XRS2, '~fightcave_has_pet(bosspet_tzrek_jad_item) = true', '~fightcave_has_pet(bosspet_tzrek_jad_item) = false',
  '9 the metamorphosis needs TzRek-Jad and no JalRek-Jad'),
 (XRS2, 'if (~fightcave_has_pet(bosspet_tzrek_jad_item) = false & ~fightcave_has_pet(bosspet_jalrek_jad_item) = false) {',
         'if (~fightcave_has_pet(bosspet_jalrek_jad_item) = false) {',
  '9 ...and the plain pet needs neither'),
 (XRS2, '~follower_spawn(bosspet_jalrek_jad);', 'npc_add(coord, bosspet_jalrek_jad, ^max_32bit_int);',
  '9 the metamorphosis transforms the pet OUT FOLLOWING you in place'),
 (XRS2, 'inv_del(bank, bosspet_tzrek_jad_item, 1);', 'inv_del(inv, bosspet_tzrek_jad_item, 1);',
  '9 ...and the pack and the bank as well, so all three places the pet can be are covered'),
 (XRS2, '~follower_spawn(bosspet_jalrek_jad);',
        '~follower_spawn(bosspet_jalrek_jad);\ninv_add(inv, bosspet_jalrek_jad_item, 1);',
  '9 ...and it never hands over a second pet'),
 (XRS2, '~obj_giveorbank(tzhaar_token, $tokkul);', 'obj_add(coord, tzhaar_token, $tokkul, 100);',
  '9 everything the exchange pays goes to the pack or the bank, never the floor'),
 (REW, '~obj_giveorbank(bosspet_tzrek_jad_item, 1);',
        '~obj_giveorbank(bosspet_tzrek_jad_item, 1);\ninv_add(inv, tzhaar_cape_infernal, 1);',
  '9 tzhaar_cape_infernal is handed over by exactly one script in the tree, the exchange'),
]
MUTS = [m for m in MUTS if len(m) == 4]

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
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'fightcave_battery.py')],
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
            note = 'caught by its own check' + ('' if len(fired) == 1 else ' (and %d others)' % (len(fired) - 1))
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:56] if fired else 'a non-zero exit with no check named, which is a crash and not a catch')
            loose += 1
        print('  %-5s %-66s %s' % (state, why, note))
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
