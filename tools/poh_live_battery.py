#!/usr/bin/env python3
"""House guests, live: runs tools/poh_live.ts inside the engine against the built pack.

    python3 tools/poh_live_battery.py [engine dir]      (default ../engine, or ../Engine-TS)

Build first (the test reads the packed scripts and maps). The TS file has to sit inside the engine
to resolve its '#/' imports, so it is copied into <engine>/tools for the run and removed after.
One pass: an owner in their Rimmington house and a friend visiting through Friend's house - a name
nobody has, Expel Guests, the exit portal, the owner leaving, building mode, and your own name."""
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
dst = os.path.join(E, 'tools', '_poh_live.ts')
# Booting the world creates the trading post's sqlite under data/; leave the engine as it was found.
tp = os.path.join(E, 'data', 'tradingpost')
tp_existed = os.path.exists(tp)
shutil.copy(os.path.join(C, 'tools', 'poh_live.ts'), dst)
try:
    env = dict(os.environ, BUILD_SRC_DIR=C, NODE_PRODUCTION='true', NODE_MEMBERS='true')
    r = subprocess.run(['npx', 'tsx', 'tools/_poh_live.ts'], cwd=E, env=env, capture_output=True, text=True, timeout=900, shell=os.name == 'nt')
    lines = [l for l in r.stdout.splitlines() if l.startswith('  ok') or l.startswith('  FAIL')]
    print('\n'.join(lines))
    failed = sum(1 for l in lines if l.startswith('  FAIL')) + (1 if r.returncode and not any('FAIL' in l for l in lines) else 0)
    if r.returncode and not any('FAIL' in l for l in lines):
        print(r.stdout[-3000:]); print(r.stderr[-3000:])
finally:
    os.remove(dst)
    if not tp_existed and os.path.exists(tp):
        shutil.rmtree(tp)
print('\nALL PASS' if not failed else f'\n{failed} FAILED')
sys.exit(1 if failed else 0)
