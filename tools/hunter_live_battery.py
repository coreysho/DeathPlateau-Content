#!/usr/bin/env python3
"""Box trapping, live: runs tools/hunter_live.ts inside the engine against the built pack.

    python3 tools/hunter_live_battery.py <engine dir>

Build first (the test reads the packed scripts and maps). The TS file has to sit inside the engine
to resolve its '#/' imports, so it is copied into <engine>/tools for the run and removed after.
Four passes. Box traps at level 70 (four traps, everything must work) and 40 (below the grey
chinchompa's 53, so a trap in their clearing must stay empty - the level gate). Bird snares at 25,
among the tropical wagtails, and at 10, below the wagtail's 19 - the same gate for snares. And the
Hunter skillcape: refused at 50, worn at 99, and its emote and graphic play. And deadfalls on the
northern boulders at 40, and at 30 - below the barb-tailed kebbit's 33, the only prey there. And a
pitfall at 40: spikes, a tease, the jump, a larupia in the pit - with the tease's level gate. And
Feldip weasel tracking at 10: trails from a burrow, every hint checked against the real bearing.
And net traps in each of the four areas - swamp lizards at Canifis (40), orange salamanders at Uzer (50,
and 40, below their 47: nothing comes, and the traps fall over), red at Ourania (60), black in the Bone
Yard (70): every young tree set and dismantled, both geometries sprung and checked, a real catch, the
cap, standing on the net, ownership, the leash, [logout] and Release.
And the desert (hunter_desert.rs2): desert devil tracking at Uzer at 20 - the ground, the gate, trails to a
catch - golden warbler snares at 20 and at 4 (below their 5: nothing comes), and Artimeus's Nardah Hunter Shop.
And the Rellekka grounds at 60, 45 and 8:
the map (spawns, boulders, pits, the trail's nodes and drifts, the ground walkable from the Keldagrim pass,
the plateau's steps both ways), then a polar kebbit trail, both butterflies netted into jars and let out, a
cerulean twitch in a snare, a sabre-toothed kebbit under a deadfall and a kyatt teased into a pit - each
creature's level gate at the lower levels.
And imp catching with magic boxes north-east of Yanille at 75 (and at 65, below the 71 to lay one: the
gate) - bait, a real catch, Retrieve, the imp's respawn, the cap, the leash, [logout] - and the
imp-in-a-box's Talk-to, banking and limits. And Aleck's Hunter Emporium in Yanille: the refit, Aleck
and Leon and their shops, a purchase, the butterfly net, the hunters' crossbow's level and ammunition.
cap, standing on the net, ownership, the leash, [logout] and Release. And the Piscatoris hunter area: its imported
ground (spawns, tracking nodes, the walk in, the fenced enclosure, no dead ops), common and razor-backed kebbit
tracking, copper longtail snares, prickly kebbit deadfalls and chinchompa box traps at 60, 30 and 8 (each gate), and
falconry at 70 and 50 (below the dark and dashing kebbits): Matthias, the glove, a catch of each, a miss, a falcon
left to give up, the stile, and a teleport out.

The box, snare, Rellekka, imp and Piscatoris trap passes do not wait on luck: a watch for a catch keeps a prey
in reach of every trap, lays again whatever fell over
after its duration, and runs for as long as the creature's catch odds at that level say it must for a miss
to be a one-in-a-million event (catchBudget and keepPreyNear at the top of hunter_live.ts)."""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# THE ENGINE CLONE IS A SIBLING, under either of the two names it goes by, and LOSTCITY_ENGINE wins
# over both - the shape poh_battery uses. Two of the four live batteries defaulted to '../Engine-TS'
# alone, which is the upstream repo's name and not this one's, so running them without an argument
# died on FileNotFoundError .../Engine-TS/tools/_<name>_live.ts instead of finding the engine beside
# them. All four agree now.
_EROOTS = ([os.environ['LOSTCITY_ENGINE']] if os.environ.get('LOSTCITY_ENGINE') else []) \
    + [os.path.join(C, '..', e) for e in ('engine', 'Engine-TS')]
E = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else next(
    (r for r in _EROOTS if os.path.isdir(os.path.join(r, 'tools'))), _EROOTS[-1]))
dst = os.path.join(E, 'tools', '_hunter_live.ts')
# Booting the world creates the trading post's sqlite under data/; leave the engine as it was found.
tp = os.path.join(E, 'data', 'tradingpost')
tp_existed = os.path.exists(tp)
shutil.copy(os.path.join(C, 'tools', 'hunter_live.ts'), dst)
failed = 0
try:
    PASSES = (('box', '70'), ('box', '40'), ('snare', '25'), ('snare', '10'), ('deadfall', '40'), ('deadfall', '30'), ('pitfall', '40'), ('graahk', '45'), ('tracking', '10'), ('cape', '50'),
              ('net', '40', 'canifis'), ('net', '50', 'uzer'), ('net', '40', 'uzer'), ('net', '60', 'ourania'), ('net', '70', 'boneyard'),
              ('desert', '20', 'devil'), ('desert', '20', 'warbler'), ('desert', '4', 'warbler'), ('desert', '20', 'shop'),
              ('rellekka', '60'), ('rellekka', '45'), ('rellekka', '8'),
              ('imp', '75'), ('imp', '65'), ('emporium', '60'),
              # the Piscatoris hunter area: the map, tracking, the traps (with each level gate), falconry
              ('pisc_map', '70'), ('pisc_track', '60'), ('pisc_traps', '60'), ('pisc_traps', '30'), ('pisc_traps', '8'), ('falconry', '70'), ('falconry', '50'))
    for trap, level, *area in PASSES:
        env = dict(os.environ, HTRAP=trap, HLEVEL=level, HAREA=(area or [''])[0], BUILD_SRC_DIR=C, NODE_PRODUCTION='true', NODE_MEMBERS='true')
        r = subprocess.run(['npx', 'tsx', 'tools/_hunter_live.ts'], cwd=E, env=env, capture_output=True, text=True, timeout=900, shell=os.name == 'nt')
        lines = [l for l in r.stdout.splitlines() if l.startswith('  ok') or l.startswith('  FAIL')]
        print(f'== {trap}{" at " + area[0] if area else ""}, Hunter {level}')
        print('\n'.join(lines))
        bad = sum(1 for l in lines if l.startswith('  FAIL'))
        if r.returncode and not bad:
            # every check passed but the process still failed: say so, and show why, rather than
            # counting a failure nobody can find
            bad = 1
            print(f'  FAIL the pass exited {r.returncode} with no failing check - its last output:')
            tail = [l for l in (r.stdout + r.stderr).splitlines() if 'ERR_INVALID_MODULE' not in l and 'OnDemand' not in l]
            print('\n'.join('       ' + l for l in tail[-25:]))
        failed += bad
finally:
    os.remove(dst)
    if not tp_existed and os.path.exists(tp):
        shutil.rmtree(tp)
print('\nALL PASS' if not failed else f'\n{failed} FAILED')
sys.exit(1 if failed else 0)
