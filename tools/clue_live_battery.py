#!/usr/bin/env python3
"""Scroll boxes and one trail per tier, live: runs tools/clue_live.ts inside the engine.

    python3 tools/clue_live_battery.py <engine dir>

Build first (the test reads the packed scripts). The TS file has to sit beside the engine's
tools/sim/harness.ts to resolve its imports, so it is copied there for the run and removed after."""
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
dst = os.path.join(E, 'tools', 'sim', '_clue_live.ts')
# Booting the world creates the trading post's sqlite under data/; leave the engine as it was found.
tp = os.path.join(E, 'data', 'tradingpost')
tp_existed = os.path.exists(tp)
shutil.copy(os.path.join(C, 'tools', 'clue_live.ts'), dst)
try:
    env = dict(os.environ, BUILD_SRC_DIR=C, NODE_MEMBERS='true')
    r = subprocess.run(['npx', 'tsx', 'tools/sim/_clue_live.ts'], cwd=E, env=env, capture_output=True,
                       text=True, timeout=900, shell=(os.name == 'nt'))
    lines = [l for l in r.stdout.splitlines() if l[:1].isdigit() or l.startswith('  ok') or l.startswith('  FAIL')]
    print('\n'.join(lines))
    failed = sum(1 for l in lines if l.startswith('  FAIL'))
    if not failed and 'ALL PASS' not in r.stdout:
        # every check printed passed but the run never reached its end: say so, and show why
        failed = 1
        print('  FAIL the run stopped before its last check - its last output:')
        print('\n'.join('       ' + l for l in (r.stdout + r.stderr).splitlines()[-25:]))
finally:
    os.remove(dst)
    if not tp_existed and os.path.exists(tp):
        shutil.rmtree(tp)
print('\nALL PASS' if not failed else '\n%d FAILED' % failed)
sys.exit(1 if failed else 0)
