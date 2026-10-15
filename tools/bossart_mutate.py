#!/usr/bin/env python3
"""Mutation test for tools/bossart_battery.py.

Each entry breaks one thing the battery claims to catch - in a throwaway copy, never in place -
and the battery has to go red, naming the check it was written for. Same runner as poh_mutate.py,
including its "caught by its own check" reporting: a mutation that trips some OTHER check proves
only that something noticed.

    python3 tools/bossart_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'bossart_mutate_work')

NPC = 'scripts/npc/configs/boss_pets.npc'
OBJ = 'scripts/npc/configs/boss_pets.obj'
DRG = 'scripts/npc/configs/dragons.npc'
DSQ = 'scripts/npc/configs/dragons.seq'
SPEC = 'tools/bossartspec.json'

MUTS = [
 # 1 - a model pointed at art that is not the art the spec measured. This is the helmet round's
 # mistake in one line: the config is still self-consistent, and only the shape gives it away.
 (NPC, 'model1=npc_bosspet_giant_mole_1', 'model1=npc_bosspet_dagannoth_rex_1',
  '1 bosspet_giant_mole names exactly the models the spec measured'),
 (NPC, 'model1=npc_bosspet_dagannoth_rex_1\nhead1', 'model1=npc_nonexistent_mole\nhead1',
  '1 bosspet_dagannoth_rex names exactly the models the spec measured'),
 (SPEC, '"verts": 278', '"verts": 279',
  '1 ...and is the mesh the spec measured'),
 # 2 - the KBD
 (DRG, 'model1=npc_king_dragon_1\nmodel2=npc_king_dragon_2',
       'model1=npc_king_dragon\nmodel2=npc_king_dragon_2',
  '2 it carries all five imported models'),
 (DRG, 'walkanim=osrs_seq_4635\nreadyanim=osrs_seq_90',
       'walkanim=osrs_seq_4635\nreadyanim=osrs_seq_90\nrecol1s=15855\nrecol1d=2112',
  '2 and no recol pairs'),
 (DRG, 'walkanim=osrs_seq_4635\nreadyanim=osrs_seq_90',
       'walkanim=osrs_seq_4635\nreadyanim=osrs_seq_90\nresizeh=160',
  '2 and no resize'),
 # a chromatic dragon dragged onto the OSRS mesh with the KBD - the leak this round had to avoid
 (DRG, '[black_dragon]\nname=Black dragon\ndesc=A fierce dragon with black scales!\nmodel1=npc_king_dragon',
       '[black_dragon]\nname=Black dragon\ndesc=A fierce dragon with black scales!\nmodel1=npc_king_dragon_1',
  '2 black_dragon did not follow the KBD onto the OSRS mesh'),
 # 3 - the animations
 (DRG, 'param=attack_anim,osrs_seq_91', 'param=attack_anim,dragon_attack',
  '3 its attack_anim is osrs_seq_91'),
 (DRG, 'param=death_anim,osrs_seq_92', 'param=death_anim,osrs_seq_89',
  '3 its death_anim is osrs_seq_92'),
 (DSQ, 'priority=6\nframe1=anim_osrs_6813_1', 'frame1=anim_osrs_6813_1',
  '3 ...and its own priority (6)'),
 # seqs 89 and 91 share frame group 6816, so this lands in whichever block comes first -
 # the point is a frame number that is not part of 1..n, and either block proves it.
 (DSQ, 'frame11=anim_osrs_6816_11\ndelay11=', 'frame99=anim_osrs_6816_11\ndelay11=',
  '3 ...with the 21 frames OSRS seq 89 has'),
 (DSQ, 'frame1=anim_osrs_6815_1', 'frame1=anim_osrs_6815_99',
  '3 ...and every frame is in anim.pack'),
 # 5 - the pets
 (NPC, 'resizeh=45\nresizev=45', 'resizeh=40\nresizev=40',
  '5 ...resizeh is the cache\'s 45'),
 (NPC, 'walkanim=osrs_seq_3313\nreadyanim=osrs_seq_3309',
       'walkanim=osrs_seq_2849\nreadyanim=osrs_seq_3309',
  '5 ...walk is OSRS seq 3313'),
 (NPC, 'readyanim=osrs_seq_6236\nvislevel=hide', 'readyanim=osrs_seq_6236\nvislevel=99',
  '5 ...with no combat level, and the every-tick timer that drives [ai_timer,_bosspet]'),
 # 6 - a placeholder creeping back
 (OBJ, 'model=obj_bosspet_giant_mole_item', 'model=obj_bird_egg_red',
  '6 obj_bird_egg_red (the recoloured bird egg) appears in neither pet config'),
 # 7 - the icons
 (OBJ, '2dzoom=8016', '2dzoom=2256', '7 ...2dzoom is the cache\'s 8016'),
 (OBJ, 'model=obj_bosspet_kbd_item\nmembers=yes',
       'model=obj_bosspet_kbd_item\n2dzoom=2000\nmembers=yes',
  '7 ...2dzoom is the cache\'s default (absent)'),
 (OBJ, 'recol1s=10594\nrecol1d=19810\n', '', '7 ...and carries the cache\'s 4 recolour pair(s)'),
 # 8 - the two halves of a pet naming each other
 (NPC, 'param=pet_item_id,bosspet_giant_mole_item', 'param=pet_item_id,bosspet_kbd_item',
  '8 bosspet_giant_mole names bosspet_giant_mole_item'),
 (OBJ, 'param=follower_id,bosspet_dagannoth_rex', 'param=follower_id,bosspet_dagannoth_prime',
  '8 ...and bosspet_dagannoth_rex_item names it back'),
 (OBJ, '[bosspet_kbd_item]\nname=Prince black dragon', '[bosspet_kbd_item]\nname=Prince black dragon\ntradeable=yes',
  '8 ...and the item is untradeable, as the cats are'),
 # 10 - the sweep, which is now the whole of this group: WHERE a pet comes from moved to
 # tools/pet_battery.py when petspec.json took ownership of the rates, and its mutations live in
 # tools/pet_mutate.py. Nothing here should test a drop table.
 ('tools/petspec.json', '"skillpet_chinchompa": {', '"skillpet_chinchompa_typo": {',
  '10 every pet item is either rolled by something or declared sourceless'),
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
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'bossart_battery.py')],
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
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:58] if fired else 'a non-zero exit')
            loose += 1
        print('  %-5s %-58s %s' % (state, why, note))
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
