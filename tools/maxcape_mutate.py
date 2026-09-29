#!/usr/bin/env python3
"""Mutation test for tools/maxcape_battery.py.

A check that cannot fail is worse than no check: it reads as coverage and is not. Each entry below
breaks one thing the battery claims to catch - in a throwaway copy of the tree, never in place - and
the battery has to go red. Every mistake here is one that was actually made while building the round,
or one the 377 client or compiler fails quietly on.

The runner is the same one poh_mutate.py uses, copied rather than shared: one tree copy, one mutation
at a time, restore, and the checker named in the entry must exit non-zero. If a third of these
appears the runner is worth lifting into a module of its own.

    python3 tools/maxcape_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'maxcape_mutate_work')

MUTS = [
 # (file, find, replace, which check group must go red)
 ('scripts/skillcapes/configs/max_cape.obj',
  'param=prayerbonus,4', 'param=prayerbonus,3',
  '2 and the +4 prayer a trimmed one gives'),
 ('scripts/skillcapes/configs/max_cape.obj',
  'param=magicdefence,9', 'param=magicdefence,8',
  '2 the +9 all-round defence of a Cape of Accomplishment'),
 ('scripts/skillcapes/configs/max_cape.obj',
  'iop4=Features', 'iop4=Features\niop5=Destroy',
  '2 the ops are Wear, Teleports and Features'),
 ('scripts/skillcapes/configs/max_cape.obj',
  '[max_hood]\nname=Max hood', '[max_hood]\nname=Max hood\nparam=prayerbonus,4',
  '2 and carries no bonuses at all, as in OSRS'),
 ('scripts/skillcapes/scripts/skillcape_equip.rs2',
  'if (~skillcape_count_99s < ~skillcape_stats) {',
  'if (~skillcape_count_99s < 23) {',
  '3 the gate counts 99s against the caped skills rather than naming skills'),
 ('scripts/skillcapes/scripts/skillcape_shop.rs2',
  'return(calc(^skillcape_price * ~skillcape_stats));',
  'return(2277000);',
  '3 the price is the skillcape price times that same count'),
 ('scripts/player/configs/stat.enum',
  'val=22,construction\n', '',
  '3 the enum holds every skill this build has, Construction in and Hunter out'),
 ('scripts/skillcapes/scripts/skillcape_shop.rs2',
  'if (inv_freespace(inv) < $missing) {', 'if (inv_freespace(inv) < 0) {',
  '3 which asks for room for the missing pieces only'),
 ('scripts/skillcapes/configs/skillcape.enum',
  'val=construction,construction_cape\n', '',
  '4 skillcape_cape covers all 22 skills'),
 ('scripts/skillcapes/configs/skillcape.enum',
  'val=construction_cape,skillcape_construction\n', '',
  '4 and every one of those capes has both an emote and a graphic'),
 # The condition gained the variants in the Max-cape-variants round, so the anchor moved with it.
 # It SKIPped for one run first, which is the harness saying the mutation no longer describes the
 # code - the right failure for it to have.
 ('scripts/skillcapes/scripts/skillcape_shop.rs2',
  'if ($cape = max_cape | enum(obj, namedobj, maxvariant_source, $cape) ! null) {',
  'if ($cape = max_hood) {',
  '4 the emote button knows about the Max cape'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'if ($back = max_cape) {\n    return(true);\n}\n',
  '',
  '5 ~skillcape_worn answers true for the Max cape whatever the skill asked about'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'case 2 : @skillcape_agility_boost;', 'case 2 : mes("Nothing happens.");',
  '5 Features reaches the ring of life, the run-energy boost and the spellbook swap'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'case 3 : @skillcape_teleport(0_40_53_50_3);', 'case 3 : @skillcape_teleport(0_40_53_50_9);',
  '5 and every coordinate in the menu is one a cape already teleports to'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'if (~wilderness_level(coord) > 20) {\n    mes("A mysterious force blocks your teleport.");\n    mes("You can\'t use this teleport after level 20 wilderness.");\n    return;\n}\nif (~pre_tele_checks(coord) = false) {\n    return;\n}\nif_close;\np_stopaction;',
  'if_close;\np_stopaction;',
  '5 with the wilderness and pre-teleport guards every other cape teleport has'),
 ('scripts/skillcapes/scripts/skillcape_equip.rs2',
  '[opheld2,construction_cape] @skillcape_require(stat_base(construction), "Construction", last_slot);',
  '[opheld2,construction_cape] @skillcape_unavailable("Construction");',
  '6 it is no longer refused for a skill that does not exist'),
 ('scripts/skillcapes/scripts/skillcape_equip.rs2',
  '[opheld2,hunter_cape] @skillcape_require(stat_base(hunter), "Hunter", last_slot);',
  '[opheld2,hunter_cape] @skillcape_unavailable("Hunter");',
  '6 no cape is refused as unavailable any more'),
 ('scripts/skill_hunter/scripts/hunting_expert.rs2',
  'if (~skillcape_offer(hunter) = true) {\n    return;\n}\n', '',
  '6 and the Hunting expert sells it'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  'if (~skillcape_offer(construction) = true) {\n    return;\n}\n', '',
  '6 the estate agent sells it'),
 # the Crafting emote holds the same prop, and comes first in the file - so this has to name the
 # construction block's own first frame to hit the right one of the two.
 ('scripts/skillcapes/configs/skillcape_emotes.seq',
  'replaceheldright=skillcape_prop_crafting_r\nframe1=anim_osrs_11524_1',
  'replaceheldright=skillcape_prop_cooking\nframe1=anim_osrs_11524_1',
  '7 and it holds the prop the cache says it holds - obj 9894, the one the'),
 ('scripts/skillcapes/configs/skillcape_emotes.seq',
  '[skillcape_construction_emote]\n// OSRS seq 4953', '[skillcape_construction_emote]\n// OSRS seq 4951',
  '7 it is OSRS seq 4953 - the one id the 22 imported emotes skipped'),
 ('scripts/skillcapes/configs/skillcape_emotes.spotanim',
  '[skillcape_construction]\n// OSRS spotanim 820\nmodel=spot_skillcape_construction',
  '[skillcape_construction]\n// OSRS spotanim 820\nmodel=spot_skillcape_constructionx',
  '7 its model is in model.pack'),
 ('scripts/skillcapes/configs/skillcape_npcs.npc',
  '[skillcape_mac]\n// OSRS npc 1053\nname=Mac\ndesc=A master of all things.',
  '[skillcape_mac]\n// OSRS npc 1053\nname=Mac\ndesc=A master of all things.\nop2=Attack',
  '8 and cannot be attacked, whatever level the cache gave him'),
 ('maps/m44_55.jm2',
  '0 15 22: 3925', '0 25 22: 3925',
  '8 his tile and the eight around it are clear'),
 ('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc',
  'hitpoints=150', 'hitpoints=15',
  '9 level 129, 150 hitpoints and the four combat stats OSRS gives it'),
 ('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc',
  'param=attackrate,4', 'param=attackrate,6',
  '9 its attack speed is OSRS\'s 4 ticks'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.constant',
  '^elder_chaos_maxhit = 17', '^elder_chaos_maxhit = 7',
  '9 its maximum hit is OSRS\'s 17'),
 ('scripts/areas/area_wilderness/scripts/elder_chaos_druid.rs2',
  '~elder_chaos_blast;\n\n[ai_opplayer2,elder_chaos_druid]\nif (~npc_combat_spell_checks = false) {\n    return;\n}\n~elder_chaos_blast;',
  '~elder_chaos_blast;\n\n[ai_opplayer2,elder_chaos_druid]\nif (~npc_check_notcombat = false) {\n    return;\n}\n~npc_default_attack;',
  '9 and it never punches'),
 ('scripts/drop_tables/scripts/elder_chaos_druid.rs2',
  '} else if ($slot < 9) {', '} else if ($slot < 8) {',
  '10 four monk tops, four bottoms, then the three pieces'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.constant',
  '^elder_chaos_slots = 11', '^elder_chaos_slots = 12',
  '10 the robe table has 11 slots'),
 ('scripts/drop_tables/scripts/elder_chaos_druid.rs2',
  'obj_add(npc_coord, snape_grass, 1, ^lootdrop_duration);',
  'obj_add(npc_coord, snape_grass_x, 1, ^lootdrop_duration);',
  '10 every item the table drops is a real obj'),
 ('scripts/drop_tables/scripts/elder_chaos_druid.rs2',
  '} else if ($random < 121) {', '} else if ($random < 91) {',
  '10 the if-chain\'s thresholds only ever go up'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.obj',
  'param=magicattack,10', 'param=magicattack,12',
  '11 elder_chaos_top'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.obj',
  'param=levelrequire,40\n\n[elder_chaos_robe]', 'param=levelrequire,30\n\n[elder_chaos_robe]',
  '11 and 40 Magic to wear'),
 ('scripts/levelrequire/scripts/tier40.rs2',
  '[opheld2,elder_chaos_top] @levelrequire_magic(40, last_slot);',
  '[opheld2,elder_chaos_top] @levelrequire_magic_and_defence(40, 40, last_slot);',
  '11 gated on Magic alone in tier40.rs2 - no Defence requirement anywhere'),
 ('maps/m50_56.jm2',
  '0 41 24: 3926', '0 39 24: 3926',
  '12 and none is standing inside a tree or a rock'),
 ('maps/m50_56.jm2',
  '0 35 25: 3926\n', '',
  '12 and the spawn count is what it was'),
]

# ---- 13: the Max cape variants -----------------------------------------------------------
# Appended rather than written into the literal above because these entries carry rs2 source with
# brackets at column 0, and there is no reliable way to find that list's end by text.
#
# EVERY ANCHOR BELOW WAS CONFIRMED TO APPEAR EXACTLY ONCE in its file before being written down.
# This harness replaces the first match and has no uniqueness rule of its own - that lives in
# tools/follower_mutate.py and tools/gamemode_mutate.py and is still worth backporting.
_VOBJ = 'scripts/skillcapes/configs/max_cape_variants.obj'
_VEN = 'scripts/skillcapes/configs/max_cape_variants.enum'
_VRS = 'scripts/skillcapes/scripts/max_cape_variants.rs2'
_GEN = 'scripts/areas/area_mage_arena/configs/god_cape.enum'
_GGR = 'scripts/areas/area_mage_arena/scripts/god_gear.rs2'
_MAC = 'scripts/areas/area_mage_arena/configs/mage_arena.constant'
_PRK = 'scripts/skillcapes/scripts/skillcape_perks.rs2'
_SHP = 'scripts/skillcapes/scripts/skillcape_shop.rs2'
_SPL = 'scripts/skill_combat/scripts/player/spells/scripts/saradomin_strike.rs2'
_BMG = 'scripts/areas/area_mage_arena/scripts/battle_mage.rs2'
_SPC = 'tools/maxcapevariantspec.json'

MUTS += [
 # --- a variant's bonuses are its source cape's, and OSRS's
 (_VOBJ, 'param=strengthbonus,8', 'param=strengthbonus,7',
  "13 each variant cape's combat bonuses are exactly its SOURCE cape's"),
 (_SPC, '"strengthbonus": 8', '"strengthbonus": 7',
  "13 ...and the same numbers the spec took out of OSRS's item table"),
 (_VOBJ, '[imbued_zamorak_max_hood]', '[imbued_zamorak_max_hoodie]',
  '13 the generated config holds exactly the'),
 (_VOBJ, 'model=obj_max_hood\nmanwear=obj_max_hood_manwear,0',
         'model=obj_max_hoodie\nmanwear=obj_max_hood_manwear,0',
  '13 and every model those sixteen name is in model.pack AND on disk'),

 # --- a variant is not a Max cape
 (_VOBJ, 'category=armour_cape\nparam=stabattack,1',
         'category=armour_cape\niop3=Teleports\nparam=stabattack,1',
  '13 not one of the sixteen carries iop3, iop4 or iop5'),
 (_PRK, 'case cooking, crafting, runecraft, firemaking : return(true);',
        'case cooking, crafting, runecraft, firemaking, agility : return(true);',
  '13 the four skills a variant still answers true for are exactly Cooking'),
 (_PRK, 'case default : return(false);\n    }\n}',
        'case default : return(true);\n    }\n}',
  '13 ...and every other skill is refused by a default case'),
 (_PRK, 'if (enum(obj, namedobj, maxvariant_source, $back) ! null) {',
        'if (false = true) {',
  '13 ~skillcape_worn asks maxvariant_source whether the worn cape is a variant'),
 # THE ORDER CHECK: moving the variant branch ABOVE the plain cape's makes a Max cape answer
 # true for four skills only - the bug the order exists to prevent.
 (_PRK, 'if ($back = max_cape) {\n    return(true);\n}',
        '',
  '13 ...and the plain Max cape is answered BEFORE that branch'),
 (_SHP, 'if ($cape = max_cape | enum(obj, namedobj, maxvariant_source, $cape) ! null) {',
        'if ($cape = max_cape) {',
  '13 ...and about the variants, which keep the emote and almost nothing else'),

 # --- the god table
 (_GEN, 'val=imbued_guthix_max_cape,^god_guthix', 'val=imbued_guthix_max_cape,^god_zamorak',
  '13 god_cape_god maps TWELVE capes to their god'),
 (_GEN, 'val=zamorak_staff,^god_zamorak', 'val=zamorak_staff,^god_guthix',
  '13 and god_staff_god maps the three staves'),
 (_MAC, '^god_none = 0', '^god_none = 1',
  '13 ...with ^god_none at zero and no two gods sharing a number'),

 # --- the nine sites go through one proc
 (_SPL, 'if (~god_cape_and_staff(^god_saradomin) = true) {',
        'if (inv_total(worn, saradomin_cape) > 0) {',
  '13 no script anywhere still tests for a god cape by name'),
 (_BMG, 'if (~god_cape_and_staff(^god_zamorak) = true & %npc_aggressive_player ! uid) {',
        'if (%npc_aggressive_player ! uid) {',
  '13 and all nine rewired sites call it'),
 # The syntax error the compiler rejects and rs2check does not - put back, to prove the check
 # that forbids it reads the CODE and not the comment that explains it.
 (_GGR, 'if (~god_worn_staff = $god) {\n    return(true);\n}\nreturn(false);',
        'return(~god_worn_staff = $god);',
  '13 the god test is a proc that writes both comparisons out'),
 # THIS ENTRY WAS MIS-AIMED and survived: it deletes a STAFF trigger and named the check about
 # CAPE triggers, which correctly did not fire. The staff half had no check at all until then.
 (_GGR, '[opheld2,guthix_staff] @god_staff_equip(^god_guthix);', '',
  '13 and all three god staves have the mirror trigger'),
 (_VRS, '[opheld2,imbued_guthix_max_cape] @god_cape_equip(^god_guthix);', '',
  '13 and all twelve god capes have an equip trigger that refuses the staff of another god'),
 (_VRS, '[opheld2,imbued_zamorak_max_cape] @god_cape_equip(^god_zamorak);', '',
  '13 ...and exactly the six god variants get one'),

 # --- combine and knife are exact inverses
 (_VRS, 'inv_del(inv, max_hood, 1);', '',
  '13 combining consumes all three items'),
 (_VRS, 'inv_add(inv, $hood, 1);\n~doubleobjbox($variant',
        '~doubleobjbox($variant',
  '13 ...and hands back the variant and its own hood'),
 (_VRS, 'inv_add(inv, $source, 1);', '',
  '13 a knife gives back exactly those three'),
 (_VRS, 'if (last_useitem ! knife) {', 'if (false = true) {',
  '13 ...and only a knife does it'),
 (_VRS, '[opheldu,fire_max_cape] @maxvariant_split;', '',
  '13 every variant answers the knife'),
 (_VRS, '[opheldu,max_cape]\ndef_namedobj', '[opheldu,max_cape]\n[opheldu,max_cape]\ndef_namedobj',
  '13 and the combine is ONE trigger on the Max cape rather than eight'),

 # --- the enums the whole thing hangs off
 (_VEN, 'val=tzhaar_cape_infernal,infernal_max_cape', 'val=tzhaar_cape_infernal,fire_max_cape',
  '13 tools/genmaxvariants.py --check'),
 (_VEN, 'val=guthix_max_cape,guthix_cape', 'val=guthix_max_cape,zamorak_cape',
  '13 tools/genmaxvariants.py --check'),

 # --- the source capes stay untouched. A duplicate param line is exactly what my own wrong
 # "fix" put there, so that is what this mutation puts back.
 ('scripts/_unpack/377/all.obj', 'param=rangeattack,1\nparam=stabdefence,11',
  'param=rangeattack,1\nparam=rangeattack,1\nparam=stabdefence,11',
  '13 no source cape carries a duplicated param line'),
 (_SPC, '"a_finding_of_mine_that_was_wrong"', '"a_finding_of_mine_that_was_quietly_dropped"',
  '13 ...and the wrong finding is written down in the spec rather than quietly dropped'),

 # --- the recolours, which decide whether six of them look like anything
 (_VOBJ, 'recol1s=12354\nrecol1d=10', 'recol1s=12355\nrecol1d=10',
  '13 and tools/maxvariantrender.py'),
]

# ---- 13: the Accumulator max cape, which is a device and not just a colour ----------------------
# The one variant whose point is behaviour rather than a name. Every mutation here leaves a cape
# that looks perfect in the render and the config and does nothing on the player's back, which is
# the failure mode the checks exist for.
_AVA = 'scripts/quests/quest_animmag/scripts/avas_device.rs2'

MUTS += [
 (_AVA, 'def_namedobj $source = enum(obj, namedobj, maxvariant_source, $cape);',
        'def_namedobj $source = null;',
  '13 ~avas_device turns a worn Max cape variant back into the device it was fused with'),
 (_AVA, 'if ($cape = avas_attractor) {\n    return(avas_attractor);\n}\n', '',
  '13 ...and it still returns each of the two plain devices'),
 (_AVA, '[proc,avas_attract]\ndef_namedobj $device = ~avas_device;',
        '[proc,avas_attract]\ndef_obj $device = inv_getobj(worn, ^wearpos_back);',
  '13 ...and neither reads the cape slot itself any more'),
 (_AVA, '[proc,ranged_ammo_saved]()(boolean)\ndef_namedobj $device = ~avas_device;',
        '[proc,ranged_ammo_saved]()(boolean)\ndef_namedobj $device = null;',
  '13 both halves of what a device does'),
 (_VEN, 'val=avas_accumulator,accumulator_max_cape', 'val=avas_attractor,accumulator_max_cape',
  '13 the enum says both directions'),
 (_GEN, 'val=zamorak_cape,^god_zamorak',
        'val=zamorak_cape,^god_zamorak\nval=accumulator_max_cape,^god_zamorak',
  '13 and the accumulator variant is in NO god table'),
 (_SPC, '"assembler_max_cape"', '"assembler_max_cape_removed"',
  '13 ...and both are still listed there by name'),

 # --- the Features menu, whose check pointed at a dispatch line for a whole round
 (_PRK, '[opheld4,max_cape] @max_cape_features;', '[opheld4,max_cape] @skillcape_spellbook;',
  '5 the Features op dispatches to one label'),
 (_PRK, 'case 3 : @skillcape_spellbook;', 'case 3 : @skillcape_toggle_rol;',
  '5 Features reaches the ring of life'),
]


def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    fails = 0
    loose = 0
    for path, find, repl, why in MUTS:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-44s %s' % (path, why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'maxcape_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        # WHICH check went red matters. A mutation that trips some OTHER check still exits
        # non-zero, so counting exit codes alone proves only that something noticed - not that the
        # check this mutation was written for is doing anything. This harness had no attribution
        # at all until tools/mutate_labels.py went looking: it printed red or GREEN from the exit
        # code and stopped, which is the weaker thing the other harnesses exist to avoid. Its
        # labels were then rewritten from the checks that actually fire, measured rather than
        # guessed, and three checks were reworded on the way because a value in the middle of a
        # claim makes a label that goes stale the moment the value does.
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in f for f in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'
            fails += 1
        elif onpoint:
            # More than one check firing means the mutation is broader than the check it names.
            # Not a failure, but worth saying: a mutation that trips four checks proves less about
            # any one of them than a mutation that trips one.
            note = 'caught by its own check'
            if len(fired) > 1:
                note += ' (and %d other%s)' % (len(fired) - 1, '' if len(fired) == 2 else 's')
            state = 'red'
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:60] if fired else 'a non-zero exit with no check named, which is a '
                                            'crash and not a catch')
            loose += 1
        print('  %-5s %-62s %s' % (state, why, note))
        # NOTE: fails was already incremented in the `if not ok` branch above. A second one here
        # counted every survivor twice, so a run with five survivors announced ten - which is the
        # kind of number that makes a reader distrust the whole report. Found while five of these
        # entries really did survive.
    print()
    if loose:
        print('%d caught by a check other than the one named - see the note beside each' % loose)
    print('%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
