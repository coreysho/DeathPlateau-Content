#!/usr/bin/env python3
"""The collection log, live: runs tools/collectionlog_live.ts inside the engine against the built pack.

    python3 tools/collectionlog_live_battery.py <engine dir>

Build first (the test reads the packed scripts). The TS file has to sit inside the engine to resolve
its '#/' imports, so it is copied into <engine>/tools for the run and removed after. One pass: three
real Giant Mole kills, the broadcast and Barrows hooks, a casket with a previous casket's leftovers
still in the reward inv, a real hard casket, the window's numbers, and a save and reload.

Also runs tools/gencollectionlog.py --check first, so a spec edited without regenerating is a
failure here rather than a surprise in game."""
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
failed = 0
r = subprocess.run([sys.executable, os.path.join(C, 'tools', 'gencollectionlog.py'), '--check'],
                   capture_output=True, text=True)
print('== generator')
print(('  ok   ' if r.returncode == 0 else '  FAIL ') + (r.stdout.strip() or r.stderr.strip()))
failed += 1 if r.returncode else 0

dst = os.path.join(E, 'tools', '_collectionlog_live.ts')
# Booting the world creates the trading post's sqlite under data/; leave the engine as it was found.
tp = os.path.join(E, 'data', 'tradingpost')
tp_existed = os.path.exists(tp)
shutil.copy(os.path.join(C, 'tools', 'collectionlog_live.ts'), dst)
try:
    env = dict(os.environ, BUILD_SRC_DIR=C, NODE_PRODUCTION='true', NODE_MEMBERS='true')
    r = subprocess.run(['npx', 'tsx', 'tools/_collectionlog_live.ts'], cwd=E, env=env, capture_output=True,
                       text=True, timeout=900, shell=(os.name == 'nt'))
    lines = [l for l in r.stdout.splitlines() if l.startswith('  ok') or l.startswith('  FAIL')]
    print('== live')
    print('\n'.join(lines))
    bad = sum(1 for l in lines if l.startswith('  FAIL'))
    if r.returncode and not bad:
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
