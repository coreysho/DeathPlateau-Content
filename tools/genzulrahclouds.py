#!/usr/bin/env python3
"""Where Zulrah's venom clouds land - measured off the shrine, not off the player.

    python3 tools/genzulrahclouds.py --content . [--print]

WHY THIS EXISTS. The first cut of the barrage dropped its cloud on the tile the player happened to
be standing on, and the owner is right that that is wrong. The OSRS wiki says the opposite twice:

    "The forms and when and where Zulrah spawns snakelings and toxic clouds are predictable: there
    are four possible patterns for the fight that dictate what it will do next."
        - oldschool.runescape.wiki /w/Zulrah, Sept 2026

    "At the start of the fight, Zulrah will always be in its green form in the middle of the shrine.
    It will never attack directly at the start; rather, Zulrah will fill the area with venom clouds,
    LEAVING THE TIPS ON THE EAST AND WEST SIDES CLEAR."
        - oldschool.runescape.wiki /w/Zulrah/Strategies, "Fight overview", Sept 2026

A cloud that lands where you stand cannot leave anything clear, and a fight whose clouds follow you
is not one a rotation can be memorised for. So the clouds belong to the ARENA, and this script works
out which tiles they cover by reading the arena.

WHAT THE WIKI GIVES AND WHAT IT DOES NOT. It gives the union - a full barrage run covers the
platform except the two horns - and it gives the count of barrages per phase (those are already in
zulrah.enum). It gives NO tile-exact list anywhere: the rotation guides are pictures, and
/w/Zulrah/Strategies carries no {{Map}} markup or coordinates for clouds at all. So the tiles below
are DERIVED FROM THE PLATFORM, by a rule stated here in full, and the two things that are ours
rather than the wiki's are said out loud at the bottom.

HOW THE COVER IS DERIVED.
  1. The walkway is the level-0 tiles of maps/m36_79.jm2 that are not lake (overlay 85), flood
     filled from the tile the boat lands you on. It is 71 tiles, a horseshoe open to the north:
     a south lobe and two arms running up to a horn each.
  2. THE TIPS ARE THE LAST TWO ROWS OF THE ARMS - z37 and z38, seven tiles, three on the west horn
     and four on the east. No cloud centre may sit where its 3x3 would reach them.
  3. Every other walkway tile must end up inside some cloud. Centres are walkway tiles, never open
     water: the orbs land on the platform, which is where the clouds are meant to be in the way.
     They are chosen greedily - the centre whose 3x3 covers the most tiles still uncovered, ties
     broken by x then z - so the list is the same every run.

WHAT IS OURS. Three things, and none of them is presented as Old School's:
  * HOW DEEP THE TIPS ARE. The wiki names them and does not measure them. Two rows is the smallest
    clear patch a 3x3 cloud cannot creep into that still holds a player who has stepped to the very
    end of an arm, so two rows is what this uses.
  * THE ORDER within a phase. The wiki says four barrages fill the platform; it does not say which
    third of it goes first. Here a barrage lays the tiles NEAREST ZULRAH first, measured from the
    centre of the 5x5 block it surfaced in, because the clouds come out of the snake - so a phase
    fought in the south floods the south lobe first and pushes the player up an arm, and a phase
    fought in the middle floods the inner edges first. The union after four barrages is the same
    whichever order is used, which is the part the wiki does state.
  * THE SPLIT. Four barrages is a full fill, so barrage k of a run lays tiles [k*T/4, (k+1)*T/4) of
    that ordering, and a run of fewer than four barrages simply does not finish the fill. The wiki
    gives no account of a two-barrage phase's coverage.
"""
import argparse, os
from collections import deque

# The shrine square and the rectangle importzulrahshrine.py put it on: local (16,16), 32x32.
SQUARE = (36, 79)
WATER = 85               # the lake overlay, as the imported square writes it
ENTRY = (28, 29)         # ^zulrah_entry - the tile the boat lands you on, inside the south lobe
CLOUD_RADIUS = 1         # ^zulrah_cloud_radius: a cloud is 3x3
TIP_ROWS = 2             # how deep "the tips on the east and west sides" are - see the docstring
BARRAGES = 4             # a full fill is four barrages - the wiki's longest barrage run
STRIDE = 16              # enum key = position * STRIDE + index, so the keys read per position
# ^zulrah_pos_middle/south/west/east, and Zulrah is 5x5, so the centre is the corner plus (2,2).
POSITIONS = [('middle', 26, 31), ('south', 26, 23), ('west', 17, 31), ('east', 35, 31)]


def walkway(land):
    """The shrine platform: non-lake level-0 tiles reachable from the tile the boat lands on."""
    def ground(x, z):
        t = land.get((0, x, z))
        return t is not None and t['ov'] != WATER
    seen, q = set(), deque([ENTRY])
    while q:
        x, z = q.popleft()
        if (x, z) in seen or not ground(x, z):
            continue
        seen.add((x, z))
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q.append((x + dx, z + dz))
    return seen


def cover(tiles):
    """Cloud centres covering every walkway tile except the tips, which no cloud may reach."""
    top = max(z for _, z in tiles)
    tips = {(x, z) for (x, z) in tiles if z > top - TIP_ROWS}
    want = tiles - tips
    centres = []
    while want:
        best = max((c for c in sorted(tiles) if not box(c) & tips),
                   key=lambda c: (len(want & box(c)), -c[0], -c[1]))
        hit = want & box(best)
        if not hit:
            raise SystemExit(f'# unreachable: {sorted(want)}')
        centres.append(best)
        want -= hit
    return centres, tips


def box(c):
    r = CLOUD_RADIUS
    return {(c[0] + dx, c[1] + dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', required=True)
    ap.add_argument('--models', default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'tools', 'models'))
    ap.add_argument('--print', action='store_true', dest='show')
    a = ap.parse_args()
    import sys
    sys.path.insert(0, a.models)
    import jm2

    land, _, _, _ = jm2.read(os.path.join(a.content, 'maps', f'm{SQUARE[0]}_{SQUARE[1]}.jm2'))
    tiles = walkway(land)
    centres, tips = cover(tiles)
    covered = set().union(*(box(c) for c in centres)) & tiles
    assert covered | tips == tiles and not (covered & tips), 'the cover and the tips must partition the walkway'
    print(f'# walkway {len(tiles)} tiles, {len(centres)} cloud centres, {len(tips)} tiles of tip left clear')
    print(f'# tips: {sorted(tips)}')

    if a.show:
        xs = sorted({x for x, _ in tiles}); zs = sorted({z for _, z in tiles})
        for z in range(zs[-1], zs[0] - 1, -1):
            row = ''
            for x in range(xs[0], xs[-1] + 1):
                row += ('O' if (x, z) in centres else 'o') if (x, z) in covered or (x, z) in centres \
                    else ('+' if (x, z) in tips else '.')
            print(f'# z{z:2d} {row}')

    lines = [
        "// GENERATED by tools/genzulrahclouds.py - do not hand-edit, re-run it. The derivation, the",
        "// wiki sentences it answers to and the two things in it that are ours are all in that file's",
        "// docstring. In short: a venom barrage's clouds belong to the shrine and to the phase, never",
        "// to the tile the player is standing on, and four barrages cover the whole platform except",
        f"// the {len(tips)} tiles of horn at the north end of the two arms.",
        '',
        '// Zulrah\'s surfacing place * ^zulrah_cloud_stride + how far into the fill -> the cloud\'s tile.',
        '// Nearest the snake first; see the generator for why the order is ours and the union is not.',
        '[zulrah_cloud_fill]',
        'inputtype=int',
        'outputtype=coord',
        f'default={SQUARE[0]}_{SQUARE[1]}_{ENTRY[0]}_{ENTRY[1]}'.replace(f'{SQUARE[0]}_', f'0_{SQUARE[0]}_', 1),
    ]
    for p, (name, px, pz) in enumerate(POSITIONS):
        cx, cz = px + 2, pz + 2
        order = sorted(centres, key=lambda c: ((c[0] - cx) ** 2 + (c[1] - cz) ** 2, c[0], c[1]))
        lines.append(f'// {name}, from ({cx},{cz}) outwards')
        for i, (x, z) in enumerate(order):
            lines.append(f'val={p * STRIDE + i},0_{SQUARE[0]}_{SQUARE[1]}_{x}_{z}')
    path = os.path.join(a.content, 'scripts', 'areas', 'area_zulrah', 'configs', 'zulrah_clouds.enum')
    open(path, 'w', newline='').write('\r\n'.join(lines) + '\r\n')
    print(f'# wrote {path}')

    c = [
        '// GENERATED by tools/genzulrahclouds.py - do not hand-edit, re-run it.',
        '',
        '// How many clouds a full fill of the platform takes, and the stride between one surfacing',
        "// place's list and the next in zulrah_clouds.enum.",
        f'^zulrah_cloud_fill_count = {len(centres)}',
        f'^zulrah_cloud_stride = {STRIDE}',
        '// A full fill is this many barrages - the longest barrage run the wiki lists for any phase,',
        '// and the run the opening phase of all four rotations uses to cover the shrine.',
        f'^zulrah_cloud_barrages = {BARRAGES}',
    ]
    path = os.path.join(a.content, 'scripts', 'areas', 'area_zulrah', 'configs', 'zulrah_clouds.constant')
    open(path, 'w', newline='').write('\r\n'.join(c) + '\r\n')
    print(f'# wrote {path}')


if __name__ == '__main__':
    main()
