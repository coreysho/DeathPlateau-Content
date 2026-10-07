#!/usr/bin/env python3
"""Where a loc is PLACED, read out of maps/*.jm2 rather than out of a running server.

    python tools/wherelocmap.py macro_theatre_floor macro_spotlight
    python tools/wherelocmap.py --prefix macro_theatre
    python tools/wherelocmap.py --square 31_74

WHY THIS EXISTS. Engine-TS/tools/sim/eventplaces.ts asks the booted world which locs are in a zone,
and that is not the same question. GameMap only adds a loc to a zone when its type is active, and a
great deal of scenery is not: a signpost you read, a theatre wall, a stage floor. Those locs are in
the map and on the player's screen, and invisible to anything that walks the zones. Asking the
server "is the Mime's theatre built" answered no for a theatre that has been sitting in m31_74 all
along - 106 walls, 84 floor tiles, 84 chairs and two spotlights.

The .jm2 LOC section is "<level> <x> <z>: <id> <shape> [<angle>]" with x and z local to the square,
so a world coordinate is (square x * 64 + x, square z * 64 + z).
"""
import argparse, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = os.path.join(ROOT, 'maps')
PACK = os.path.join(ROOT, 'pack', 'loc.pack')


def names():
    by_id, by_name = {}, {}
    with open(PACK, encoding='utf-8') as fh:
        for line in fh:
            if '=' not in line:
                continue
            i, n = line.strip().split('=', 1)
            by_id[int(i)] = n
            by_name[n] = int(i)
    return by_id, by_name


def placements(square):
    """[(level, x, z, id, shape, angle)] for one square, world coordinates."""
    path = os.path.join(MAPS, 'm%s.jm2' % square)
    if not os.path.exists(path):
        return []
    sx, sz = (int(v) * 64 for v in square.split('_'))
    out, inloc = [], False
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.strip()
            if line.startswith('===='):
                inloc = 'LOC' in line
                continue
            if not inloc or ':' not in line:
                continue
            head, _, tail = line.partition(':')
            lv, x, z = (int(v) for v in head.split())
            bits = tail.split()
            out.append((lv, sx + x, sz + z, int(bits[0]),
                        int(bits[1]) if len(bits) > 1 else 10,
                        int(bits[2]) if len(bits) > 2 else 0))
    return out


def squares():
    return sorted(f[1:-4] for f in os.listdir(MAPS) if f.startswith('m') and f.endswith('.jm2'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('locs', nargs='*')
    ap.add_argument('--prefix', help='every loc whose name starts with this')
    ap.add_argument('--square', help='list what is in one square instead')
    a = ap.parse_args()
    by_id, by_name = names()

    if a.square:
        rows = placements(a.square)
        bag = {}
        for lv, x, z, lid, shape, angle in rows:
            k = by_id.get(lid, 'loc_%d' % lid)
            bag.setdefault(k, []).append((lv, x, z))
        print('%s: %d placements, %d kinds' % (a.square, len(rows), len(bag)))
        for k in sorted(bag, key=lambda k: -len(bag[k])):
            lv, x, z = bag[k][0]
            print('  %-36s x%-4d first %d,%d,%d' % (k, len(bag[k]), lv, x, z))
        return

    want = set(a.locs)
    if a.prefix:
        want |= {n for n in by_name if n.startswith(a.prefix)}
    if not want:
        raise SystemExit('name a loc, or --prefix, or --square')
    ids = {}
    for n in sorted(want):
        if n not in by_name:
            print('%-36s NOT IN loc.pack' % n)
            continue
        ids[by_name[n]] = n
    found = {n: [] for n in ids.values()}
    for sq in squares():
        for lv, x, z, lid, shape, angle in placements(sq):
            if lid in ids:
                found[ids[lid]].append((sq, lv, x, z))
    for n in sorted(found):
        hits = found[n]
        if not hits:
            print('%-36s not placed anywhere' % n)
            continue
        sqs = sorted({h[0] for h in hits})
        sq, lv, x, z = hits[0]
        print('%-36s x%-4d in %s, first %d,%d,%d' % (n, len(hits), ','.join(sqs), lv, x, z))


if __name__ == '__main__':
    main()
