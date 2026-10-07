#!/usr/bin/env python3
"""Put the three pillory cages where the game already says they belong.

    python tools/genpillory.py [--dry-run]

runescape.wiki/w/Pillory: "The pillory cages were situated in three RuneScape locations: east of
the general store in Varrock, the western part of Seers' Village, and slightly north of the bank in
Yanille." Those are three descriptions, not three coordinates - but the build does not need them,
because IT ALREADY HAS THE TRAMPS. pillory_tramp_thrower_varrock, _seers and _yanille are three
npcs in antimacro.npc, each placed in its own town, and the wiki says of them: "Outside the
pillory, the tramp, a non-player character, throws rotten tomatoes at the players inside." A man
standing in the street throwing tomatoes at nothing is standing next to where the cage goes. So the
cages are placed from the tramps, one tile from each, and nothing here is guessed.

A cage is four wall locs on one tile - plain bars on three sides and the door on the fourth, facing
away from the tramp so the guard can stand at it. The player is put inside and cannot leave until
the lock is picked; see "macro events"/scripts/general/macro_event_pillory.rs2.
"""
import argparse, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = os.path.join(ROOT, 'maps')

# tramp npc -> (cage tile, which way the door faces, where the guard stands). The door angle is a
# wall rotation: 0 west, 1 north, 2 east, 3 south.
CAGES = [
    ('pillory_tramp_thrower_varrock', (3228, 3413), 1, (3228, 3414)),
    ('pillory_tramp_thrower_seers', (2683, 3485), 1, (2683, 3486)),
    ('pillory_tramp_thrower_yanille', (2606, 3101), 1, (2606, 3102)),
]
GUARD = 'macro_pillory_guard'
BARS = 'prisonbars'
DOOR = 'macro_pillory_door'


def pack(name):
    out = {}
    with open(os.path.join(ROOT, 'pack', name + '.pack'), encoding='utf-8') as fh:
        for line in fh:
            if '=' in line:
                i, n = line.strip().split('=', 1)
                out[n] = int(i)
    return out


def sections(text):
    """[(header, [lines])] in file order, so an insert lands in the right one."""
    out, cur = [], None
    for line in text.split('\n'):
        if line.startswith('===='):
            cur = (line, [])
            out.append(cur)
        elif cur is not None:
            cur[1].append(line)
        else:
            out.append((None, [line]))
    return out


def rebuild(secs):
    parts = []
    for head, lines in secs:
        if head is not None:
            parts.append(head)
        parts.extend(lines)
    return '\n'.join(parts)


def add(square, loclines, npclines, dry):
    path = os.path.join(MAPS, 'm%s.jm2' % square)
    raw = open(path, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    secs = sections(raw.replace('\r\n', '\n'))
    added = 0
    for head, lines in secs:
        if head is None:
            continue
        want = loclines if 'LOC' in head else npclines if 'NPC' in head else None
        if not want:
            continue
        have = {l.strip() for l in lines}
        fresh = [l for l in want if l not in have]
        if not fresh:
            continue
        # keep the trailing blank line that separates the sections
        while lines and not lines[-1].strip():
            lines.pop()
        lines.extend(fresh)
        lines.append('')
        added += len(fresh)
    if added and not dry:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(rebuild(secs).replace('\n', nl))
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    L, N = pack('loc'), pack('npc')
    for tramp, (cx, cz), door_angle, (gx, gz) in CAGES:
        square = '%d_%d' % (cx >> 6, cz >> 6)
        lx, lz = cx & 63, cz & 63
        # the three sides that are not the door
        angles = [r for r in (0, 1, 2, 3) if r != door_angle]
        loclines = ['0 %d %d: %d 0 %d' % (lx, lz, L[BARS], r) for r in angles]
        loclines.append('0 %d %d: %d 0 %d' % (lx, lz, L[DOOR], door_angle))
        gsq = '%d_%d' % (gx >> 6, gz >> 6)
        assert gsq == square, 'the guard must be in the same square as his cage'
        npclines = ['0 %d %d: %d' % (gx & 63, gz & 63, N[GUARD])]
        n = add(square, loclines, npclines, a.dry_run)
        print('%-34s cage %d,%d door angle %d, guard %d,%d  -> m%s (%d lines%s)'
              % (tramp, cx, cz, door_angle, gx, gz, square, n, ', dry run' if a.dry_run else ''))


if __name__ == '__main__':
    main()
