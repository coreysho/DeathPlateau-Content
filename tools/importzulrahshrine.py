#!/usr/bin/env python3
"""Zulrah's shrine, lifted out of the two OSRS squares it straddles and put down on one of ours.

WHY THIS EXISTS AND WHY tools/models/importosrsmap.py COULD NOT DO IT. The shrine is an island in
the middle of the Poison Waste lake, at OSRS world x 2262-2276, z 3067-3078 - which crosses the
z = 3072 line, so half of it is in OSRS's m35_47 and half in m35_48. m35_47 is free here, but
m35_48 IS THE POISON WASTE REGICIDE USES (regicide_gathering.rs2 reads the coal tar at (22,55) and
some eighty sulphur rocks off that square), and importosrsmap.py rewrites a whole square: importing
OSRS's m35_48 would erase Regicide's. There is no OSRS rectangle importer - import474rect.py is
474-only - so this is the rectangle importer for the one rectangle this round needs.

WHAT IT DOES. Copies a 32x32 world rectangle of OSRS terrain and locs, spanning both squares, onto
one 377 square at a zone-aligned offset, so the shrine can be instanced the way the Fight Cave's
arena is (one 4x4 block of zones, instance_setzone). Loc ids go through the same
osrslocimport.resolve() the map importer uses - reuse a 377 loc when it is provably the same object,
import it as osrsloc_<id> otherwise - so nothing is decided differently here than it is there.

  python3 tools/importzulrahshrine.py --maps "<rev236 cache>" --cache "<newest cache>" \
      --content . --out scripts/areas/area_zulrah/configs/zulrah_shrine [--dry-run]

THE OVERLAY REMAP, which this shares with the Zul-Andra square and is the second reason for a file
of our own. OSRS overlays 580 and 583 are two of the water-edge blends in the 44x/56x/57x/58x family
and are past the end of the 377 flo table, so they would be written into the .jm2 as floor ids the
client cannot draw. What they are is settled by a square both caches have: on m33_48 OSRS paints
565/568/571/574/577/451/454 across 2,536 tiles where 377 paints gungywater (6) across 2,623. So the
whole family is 377's gungywater, and 580/583 are remapped to it - here, and in --fix-overlays mode
over an already-imported square (which is how maps/m34_47.jm2 got its 1,939 of them).

  python3 tools/importzulrahshrine.py --content . --fix-overlays maps/m34_47.jm2
"""
import argparse, os, sys

# The cache decoders live beside the checkout, in LostCityServer/tools/models. A worktree is not
# beside it, so --models says where they are and this is only the default.
DEFAULT_MODELS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'tools', 'models')

# OSRS water-edge overlays with no 377 id -> gungywater. See the docstring for the evidence.
OVERLAY_REMAP = {580: 6, 583: 6}

# The shrine, and where it lands. The rectangle is 32x32 of lake with the island in the middle of
# it; the destination offset is a multiple of 8 so the block is four zones by four.
SRC_X, SRC_Z, SIZE = 2256, 3056, 32
DST_SQUARE = (36, 79)
DST_OFF = 16


def fix_overlays(path):
    import jm2
    land, locs, npcs, objs = jm2.read(path)
    n = 0
    for t in land.values():
        if t.get('ov') in OVERLAY_REMAP:
            t['ov'] = OVERLAY_REMAP[t['ov']]
            n += 1
    jm2.write(path, land, locs, npcs, objs)
    print(f'# {path}: {n} overlay(s) remapped {OVERLAY_REMAP}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--maps'); ap.add_argument('--cache')
    ap.add_argument('--content', required=True)
    ap.add_argument('--out')
    ap.add_argument('--fix-overlays')
    ap.add_argument('--models', default=DEFAULT_MODELS,
                    help='LostCityServer/tools/models (defaults to the one beside the checkout)')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    sys.path.insert(0, a.models)

    if a.fix_overlays:
        fix_overlays(os.path.join(a.content, a.fix_overlays))
        return

    import importosrsmap as IM, jm2
    import osrslocimport as LI
    from osrsloc import load_osrs_locs
    from flatcache import Store
    from animconv474 import pack_append

    src = IM.MapSource(a.maps)
    st = Store(a.cache)
    locs, _ = load_osrs_locs(st)
    c377 = LI.Content377(a.content)
    texnames = set()
    for l in open(os.path.join(a.content, 'pack', 'texture.pack')):
        if '=' in l:
            i = int(l.split('=', 1)[0])
            if i in LI.SHARED_TEXTURES:
                texnames.add(i)

    # Read both source squares whole, then take only the rectangle out of them.
    tiles, placed = {}, []
    for reg in sorted({f'{(SRC_X + dx) >> 6}_{(SRC_Z + dz) >> 6}'
                       for dx in (0, SIZE - 1) for dz in (0, SIZE - 1)}):
        rx, rz = map(int, reg.split('_'))
        ms = (rx << 8) | rz
        t = src.terrain(reg, ms)
        for lv in range(4):
            for x in range(64):
                for z in range(64):
                    tiles[(lv, rx * 64 + x, rz * 64 + z)] = dict(t[lv][x][z])
        for (oid, lv, x, z, sh, rot) in src.locs(reg, ms):
            placed.append((oid, lv, rx * 64 + x, rz * 64 + z, sh, rot))
        print(f'# read m{reg}')

    land = {}
    bad = set()
    for lv in range(4):
        for dx in range(SIZE):
            for dz in range(SIZE):
                t = tiles.get((lv, SRC_X + dx, SRC_Z + dz))
                if t is None:
                    continue
                if t['ov'] in OVERLAY_REMAP:
                    t['ov'] = OVERLAY_REMAP[t['ov']]
                if t['ov'] is not None and t['ov'] > 255:
                    bad.add(t['ov'])
                land[(lv, DST_OFF + dx, DST_OFF + dz)] = t
    if bad:
        print(f'# floor ids still past the 377 flo table: {sorted(bad)}')

    inrect = [p for p in placed
              if SRC_X <= p[2] < SRC_X + SIZE and SRC_Z <= p[3] < SRC_Z + SIZE]
    results = {}
    for (oid, lv, x, z, sh, rot) in inrect:
        if oid not in results:
            results[oid] = LI.resolve(st, locs, c377, oid)
    imp = sorted({r[1] for r in results.values() if r[0] == 'import'})
    reuse = sorted({r[1] for r in results.values() if r[0] == 'reuse'})
    drop = {k: r[1] for k, r in results.items() if r[0] == 'drop'}
    print(f'# {len(inrect)} locs in the rectangle; '
          f'{len(reuse)} loc ids reused as-is, {len(imp)} to import, {len(drop)} dropped {drop}')
    if a.dry_run:
        return

    lines = ["// Zulrah's shrine - OSRS locs imported by tools/importzulrahshrine.py, which uses",
             '// tools/models/osrslocimport.py exactly as tools/models/importosrsmap.py does.',
             '// Models re-encoded by osrs2ob2.py with the loc recolours baked in.', '']
    model_files, anim_names = {}, {}
    for oid in imp:
        LI.import_loc(st, locs, oid, a.content, texnames, anim_names, lines, model_files)
    if imp:
        pack_append(os.path.join(a.content, 'pack', 'loc.pack'), [f'osrsloc_{i}' for i in imp])
        pack_append(os.path.join(a.content, 'pack', 'model.pack'), list(model_files))
        os.makedirs(os.path.join(a.content, 'models', 'loc'), exist_ok=True)
        for n, b in model_files.items():
            open(os.path.join(a.content, 'models', 'loc', n + '.ob2'), 'wb').write(b)
        print(f'# wrote {len(model_files)} loc models')
    locpack = {}
    for l in open(os.path.join(a.content, 'pack', 'loc.pack')):
        if '=' in l:
            i, n = l.strip().split('=', 1)
            locpack[n] = int(i)

    out = []
    for (oid, lv, x, z, sh, rot) in inrect:
        r = results[oid]
        nid = r[1] if r[0] == 'reuse' else (locpack[f'osrsloc_{r[1]}'] if r[0] == 'import' else None)
        if nid is not None:
            out.append((nid, lv, DST_OFF + x - SRC_X, DST_OFF + z - SRC_Z, sh, rot))
    reg = f'{DST_SQUARE[0]}_{DST_SQUARE[1]}'
    jm2.write(os.path.join(a.content, 'maps', f'm{reg}.jm2'), land, out, [], [])
    print(f'# wrote maps/m{reg}.jm2 ({len(land)} tiles, {len(out)} locs)')
    if a.out and lines:
        path = os.path.join(a.content, a.out + '.loc')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w', newline='').write('\r\n'.join(lines))
        print(f'# wrote {a.out}.loc')


if __name__ == '__main__':
    main()
