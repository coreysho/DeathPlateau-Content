#!/usr/bin/env python3
"""Build the Land of the Frogs - map square 32_75 - from nothing.

    python tools/genfrogcave.py            # writes maps/m32_75.jm2
    python tools/genfrogcave.py --dry-run

WHY IT IS GENERATED AND NOT HAND-WRITTEN. A .jm2 is 16,384 possible tile lines; the clearing below
is described here in fifteen lines of arithmetic, which is the only form in which anybody can see
what shape it is or move a tree without counting.

WHY IT HAD TO BE BUILT AT ALL. Every other random event room in this game was already in the maps -
Leo's cemetery, Damien's yard, Pete's cell, Bob's island, the forester's clearing, the Mime's
theatre, the Quiz Master's set. The Land of the Frogs is not, and cannot be imported: the rev 474
cache holds XTEA keys for 732 of its map squares and none of the unkeyed ones can be read, and a
pass over every one of the 565 regions it CAN read finds no frog cave anywhere in it. Old School
deleted the place when the random events were retired. So this is the one room in the set that is
mine rather than Jagex's, and it is built out of locs the 377 cache already has - the same palette
the Freaky Forester's clearing is made of, which is the nearest thing to it that exists.
"""
import argparse, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'C:/LostCityServer/tools/models')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import jm2  # noqa: E402

SQUARE = '32_75'
BASE_X, BASE_Z = 32 * 64, 75 * 64          # 2048, 4800

# The clearing, in local tiles. Everything outside it is flagged blocked, which is what makes the
# ring of trees a wall rather than scenery you can walk through.
X0, X1 = 22, 41
Z0, Z1 = 22, 41
HEIGHT = 0                                  # dead flat; nothing here is on a slope
GRASS, GRASS2 = 50, 48                      # the two underlays the forester's clearing uses

# Everything below is already in loc.pack and placed somewhere else in the world, so nothing new is
# imported for this room. loc_8973 and loc_8974 are the two trees that wall in the Freaky
# Forester's clearing, three squares east of here.
TREE_A, TREE_B = 'loc_8973', 'loc_8974'
PLANT_A, PLANT_B, DAISY = 'plant1', 'plant2', 'daisys'
LILY_A, LILY_B = 'waterlily1', 'waterlily3'

# One herald, six ordinary frogs in hats and one wearing a crown. The crown is npc_2469i2 and is
# the whole of the puzzle - runescape.wiki: "the player then had to speak to the frog with the
# crown and kiss them". They all wander, so it is never in the same place twice.
HERALD = 'macro_frog_crier'
FROG = 'macro_frog_noncombat'
ROYAL = 'macro_frog_royal'
FROGS = [(26, 27), (30, 34), (36, 26), (33, 30), (28, 38), (38, 35)]
ROYAL_AT = (31, 29)
HERALD_AT = (31, 24)


def pack(name):
    out = {}
    with open(os.path.join(ROOT, 'pack', name + '.pack'), encoding='utf-8') as fh:
        for line in fh:
            if '=' in line:
                i, n = line.strip().split('=', 1)
                out[n] = int(i)
    return out


def build():
    locs_by_name, npcs_by_name = pack('loc'), pack('npc')
    land, locs, npcs = {}, [], []

    for x in range(64):
        for z in range(64):
            inside = X0 <= x <= X1 and Z0 <= z <= Z1
            # A chequer of the two grasses so the floor is not one flat colour.
            un = GRASS if (x + z) % 3 else GRASS2
            land[(0, x, z)] = dict(h=HEIGHT, ov=None, shape=0, rot=0,
                                   flags=0 if inside else 1, un=un)

    def put(name, x, z, shape=10, angle=0):
        locs.append((locs_by_name[name], 0, x, z, shape, angle))

    # THE WALL IS A RING OF TREES, on ground that is blocked anyway. A tree is TWO BY TWO and is
    # anchored at its south-west corner, so a ring sitting one tile out ate the first row and
    # column of the clearing: the anchors here are two tiles out on the south and west and one on
    # the north and east, which puts all four footprints wholly outside it. They step in twos for
    # the same reason - at every tile they would overlap each other.
    for x in range(X0 - 2, X1 + 2, 2):
        for z in (Z0 - 2, Z1 + 1):
            put(TREE_A if (x + z) % 4 else TREE_B, x, z, 10, (x + z) % 4)
    for z in range(Z0 - 2, Z1 + 2, 2):
        for x in (X0 - 2, X1 + 1):
            put(TREE_A if (x + z) % 4 else TREE_B, x, z, 10, (x + z) % 4)

    # Undergrowth goes in the tree line, where the ground is blocked anyway. plant1 and plant2 are
    # centrepieces and they BLOCK: scattered through the clearing they turned twenty tiles of it
    # into a maze, which a player hunting a hopping frog does not need.
    for i, (x, z) in enumerate([(X0 - 4, Z0 + 4), (X1 + 3, Z0 + 7), (X0 - 4, Z1 - 5),
                                (X1 + 3, Z1 - 2), (X0 + 6, Z0 - 4), (X1 - 4, Z1 + 3)]):
        put(PLANT_A if i % 2 else PLANT_B, x, z, 10, i % 4)

    # Inside, nothing but ground decor - daisies and a scatter of lily pads for the frogs to sit
    # by. Both are shape 22, which the client draws flat on the tile and nothing walks into.
    taken = {ROYAL_AT, HERALD_AT, (31, 26)} | set(FROGS)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            if (x, z) in taken:
                continue
            n = (x * 7 + z * 13) % 11
            if n == 2:
                put(DAISY, x, z, 22, (x + z) % 4)
            elif n == 3:
                put(LILY_A if (x + z) % 2 else LILY_B, x, z, 22, (x + z) % 4)

    npcs.append((npcs_by_name[HERALD], 0, HERALD_AT[0], HERALD_AT[1]))
    npcs.append((npcs_by_name[ROYAL], 0, ROYAL_AT[0], ROYAL_AT[1]))
    for x, z in FROGS:
        npcs.append((npcs_by_name[FROG], 0, x, z))
    return land, locs, npcs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    land, locs, npcs = build()
    walk = sum(1 for d in land.values() if not d['flags'])
    print('%s: %d walkable tiles (%d..%d x %d..%d local), %d locs, %d npcs'
          % (SQUARE, walk, X0, X1, Z0, Z1, len(locs), len(npcs)))
    print('   world x %d..%d, z %d..%d'
          % (BASE_X + X0, BASE_X + X1, BASE_Z + Z0, BASE_Z + Z1))
    if a.dry_run:
        return
    out = os.path.join(ROOT, 'maps', 'm%s.jm2' % SQUARE)
    jm2.write(out, land, locs, npcs, [])
    print('   wrote %s' % out)


if __name__ == '__main__':
    main()
