#!/usr/bin/env python3
"""Build the Staff Zone - map square 22_56 - from nothing.

    python tools/genstaffzone.py            # writes maps/m22_56.jm2
    python tools/genstaffzone.py --dry-run  # the report and the plan, no file
    python tools/genstaffzone.py --preview  # an ASCII plan of the square

WHAT IT IS. One square nobody can walk to, reached only by "::sz" (Engine-TS's ClientCheatHandler,
staffModLevel >= 2) and left by "::home" like anywhere else. Four districts on one flat plateau:

    THE CAMP    the middle, where ::sz lands you: altar, signpost, a table to stand round.
    THE OFFICE  north-west, a brick room with a lectern, bookcases and TWO HOLDING CELLS -
                3x3 cages of prison bars with a door, for a player brought here mid-investigation.
    THE VAULT   north-east, bank booths and two bankers, plus the general store's keeper and
                assistant so stock and prices can be read off the live economy.
    THE RANGE   the south half: five attackable dummies, archery targets, a bare stone pad to
                ::npcadd a boss onto, and a railed sparring ring floored like the Duel Arena.

WHY SQUARE 22_56. 2,004 surface squares are free; this one is fully isolated (every one of its
eight neighbours is empty, so no edge of a real map square is ever in view), it is at the same
latitude as Burthorpe and the real Death Plateau - 22_56 is the plateau's own row, five squares
west of anything that exists - and x/z 1408..1471, 3584..3647 is outside both wilderness
rectangles (Player.isInWilderness) and far inside the 14-bit coord packing. maps/ignore.csv keeps
it off the generated world map, so it is not findable by looking.

WHY IT IS GENERATED AND NOT HAND-WRITTEN. Same reason as the Land of the Frogs (tools/genfrogcave.py):
a .jm2 is 16,384 possible tile lines, and the four districts here are described below in arithmetic
you can read and move a wall in.

NOTHING NEW IS IMPORTED. Every loc and npc placed here is already in the packs and already wired by
content somewhere else - the altar is [oploc1,_prayer_altar], the booths [oploc2,bankbooth], the
bankers [apnpc3,_bank_teller], the dummies [oploc2,sworddummy], the cell doors [oploc1,_door_closed],
the shop pair [opnpc1,generalshopkeeper5]. So the zone works the day it is packed, with no new
scripts behind it but the ::sz teleport itself.

TERRAIN IS THE REAL PLATEAU'S. Underlay 94 and overlay 83 are what maps/m44_56.jm2 and its
neighbours are made of (1,348 tiles of o83 over u94 across Death Plateau and Trollheim), so the
snowline here is the same snowline, not a colour somebody picked. Indoors uses the Edgeville bank's
own floor (overlay 3/4 chequer, flag 4) and the ring uses the Duel Arena's (overlay 76).

ONE CHECK THAT MATTERS. Every wall, cage and fence this lays down is flood-filled from the ::sz
arrival tile before the file is written, and the script refuses to write if any district - or any
cell, with its door counted as passable - cannot be walked to. A staff zone you cannot cross is
the one failure a map generator can and should catch.

A NOTE ON A FREE-TO-PLAY WORLD. GameMap.init skips every tile outside maps/free2play.csv when
NODE_MEMBERS is false. The default is true and this world runs members, so the square is not
listed; a free-to-play world would need it added there as well.
"""
import argparse, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'C:/LostCityServer/tools/models')
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), 'tools', 'models'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import jm2  # noqa: E402

SQUARE = '22_56'
BASE_X, BASE_Z = 22 * 64, 56 * 64          # 1408, 3584

HEIGHT = 120                               # flat: the plateau's own height, and no slope seams
SNOW = 94                                  # underlay: grey_blue_underlay, Death Plateau's ground
ROCK = 83                                  # overlay: the worn plateau surface over it
WOOD = 4                                   # woodenfloor - the Office
BANK_A, BANK_B = 3, 4                      # the Edgeville bank's own two-tile chequer - the Vault
PAD = 10                                   # darkstone - the boss pad
RING = 76                                  # duel_arena - the sparring ring
INDOORS = 4                                # tile flag: under a roof, as every bank tile is
BLOCKED = 1

# The plateau. Everything outside it is blocked, which is what makes the rock line a wall.
X0, X1 = 8, 55
Z0, Z1 = 8, 55

ARRIVE = (32, 32)                          # ::sz lands here -> 0_22_56_32_32

# Interiors, inclusive. Walls go on the outer edges of these tiles, so the interior is walkable.
OFFICE = (12, 24, 38, 52)
VAULT = (38, 50, 38, 50)
CELLS = [(20, 22, 40, 42), (20, 22, 45, 47)]   # 3x3 each, inside the Office
OFFICE_DOOR = (18, 'south')
VAULT_DOOR = (44, 'south')
CELL_DOOR = 'south'

CAMP = (27, 37, 27, 37)
PAD_RECT = (28, 35, 12, 19)
RING_RECT = (42, 50, 12, 20)

WALL = 'brickwall'
DOOR = 'loc_1513'                          # "Large door", [oploc1,_door_closed] - opens and shuts
BARS = 'prisonbars'                        # the cages, as tools/genpillory.py uses them
FENCE = 'railing'
TORCH = 'torch'
ROCKS = ('death_mountainrocks_1', 'death_rockslide5')

# shape, and the rotation that puts a wall on each edge of its own tile
STRAIGHT, CORNER, DECOR, CENTRE, GROUND = 0, 2, 4, 10, 22
EDGE_ROT = {'west': 0, 'north': 1, 'east': 2, 'south': 3}
# A corner covers two edges: 0 west+north, 1 north+east, 2 east+south, 3 south+west
CORNER_ROT = {('west', 'south'): 3, ('west', 'north'): 0, ('east', 'north'): 1, ('east', 'south'): 2}


def pack(name):
    out = {}
    with open(os.path.join(ROOT, 'pack', name + '.pack'), encoding='utf-8') as fh:
        for line in fh:
            if '=' in line:
                i, n = line.strip().split('=', 1)
                out[n] = int(i)
    return out


class Square:
    """The square being built, and the collision it implies - walls as edges, locs as footprints."""

    def __init__(self, locs_by_name, npcs_by_name):
        self.names, self.npc_names = locs_by_name, npcs_by_name
        self.land, self.locs, self.npcs = {}, [], []
        self.walls = {}          # (x, z) -> set of blocked edges
        self.doors = set()       # (x, z, edge) a door sits on: shut, but staff open it
        self.full = set()        # tiles a centrepiece stands on
        self.wall_layer = set()  # (x, z) that already carry a wall-layer loc - one each, no more

    # --- terrain ---

    def tile(self, x, z, overlay=None, flags=0, underlay=SNOW, height=HEIGHT):
        self.land[(0, x, z)] = dict(h=height, ov=overlay, shape=0, rot=0, flags=flags, un=underlay)

    def floor(self, rect, overlay, flags=0, chequer=None):
        x0, x1, z0, z1 = rect
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                ov = overlay if chequer is None else (overlay if (x + z) % 2 else chequer)
                self.tile(x, z, overlay=ov, flags=flags)

    # --- locs ---

    def put(self, name, x, z, shape=CENTRE, rot=0, blocks=1):
        self.locs.append((self.names[name], 0, x, z, shape, rot))
        if shape in (CENTRE, CENTRE + 1):
            for dx in range(blocks):
                self.full.add((x + dx, z) if rot % 2 == 0 else (x, z + dx))

    def wall(self, name, x, z, edges, door=False):
        """One wall-layer loc on this tile, covering one edge or two. Nothing else may share it."""
        if (x, z) in self.wall_layer:
            raise SystemExit('two wall locs on tile %d,%d - the client draws one' % (x, z))
        self.wall_layer.add((x, z))
        if len(edges) == 1:
            self.locs.append((self.names[name], 0, x, z, STRAIGHT, EDGE_ROT[edges[0]]))
        else:
            key = tuple(edges) if tuple(edges) in CORNER_ROT else tuple(reversed(edges))
            self.locs.append((self.names[name], 0, x, z, CORNER, CORNER_ROT[key]))
        self.walls.setdefault((x, z), set()).update(edges)
        if door:
            for e in edges:
                self.doors.add((x, z, e))

    def enclose(self, rect, name, door_at=None, door_name=None):
        """A wall ring on the outer edges of an interior rect: straights, and a corner per corner."""
        x0, x1, z0, z1 = rect
        for x in range(x0, x1 + 1):
            for z, edge in ((z0, 'south'), (z1, 'north')):
                corner = ('west',) if x == x0 else ('east',) if x == x1 else ()
                is_door = door_at is not None and door_at[1] == edge and door_at[0] == x and not corner
                self.wall(door_name if is_door else name, x, z, list(corner) + [edge], door=is_door)
        for z in range(z0 + 1, z1):
            for x, edge in ((x0, 'west'), (x1, 'east')):
                is_door = door_at is not None and door_at[1] == edge and door_at[0] == z
                self.wall(door_name if is_door else name, x, z, [edge], door=is_door)

    def npc(self, name, x, z):
        self.npcs.append((self.npc_names[name], 0, x, z))

    # --- the check ---

    def walkable(self, x, z):
        if not (X0 <= x <= X1 and Z0 <= z <= Z1):
            return False
        d = self.land.get((0, x, z))
        return d is not None and not d['flags'] & BLOCKED and (x, z) not in self.full

    def crossable(self, x, z, edge, doors_shut=False):
        """Can you step off (x, z) over this edge? A door is passable unless we are asking whether
        a shut one holds - which is the whole question a holding cell asks."""
        def blocks(tx, tz, te):
            if te not in self.walls.get((tx, tz), ()):
                return False
            return doors_shut or (tx, tz, te) not in self.doors

        if blocks(x, z, edge):
            return False
        nx, nz, back = {'west': (x - 1, z, 'east'), 'east': (x + 1, z, 'west'),
                        'north': (x, z + 1, 'south'), 'south': (x, z - 1, 'north')}[edge]
        return not blocks(nx, nz, back)

    def reachable(self, doors_shut=False):
        seen, stack = {ARRIVE}, [ARRIVE]
        while stack:
            x, z = stack.pop()
            for edge in EDGE_ROT:
                if not self.crossable(x, z, edge, doors_shut):
                    continue
                n = {'west': (x - 1, z), 'east': (x + 1, z),
                     'north': (x, z + 1), 'south': (x, z - 1)}[edge]
                if n not in seen and self.walkable(*n):
                    seen.add(n)
                    stack.append(n)
        return seen


def build():
    sq = Square(pack('loc'), pack('npc'))

    # THE PLATEAU, and the blocked rock line round it.
    for x in range(64):
        for z in range(64):
            inside = X0 <= x <= X1 and Z0 <= z <= Z1
            sq.tile(x, z, overlay=ROCK if inside else None, flags=0 if inside else BLOCKED)

    # Rocks, all of them standing on ground that is blocked anyway - they are the horizon, not scenery
    # to walk round. Two tiles clear of the plateau edge so a 2x2 footprint never reaches into it.
    for x in range(X0 - 3, X1 + 4, 3):
        for z in (Z0 - 3, Z1 + 2):
            sq.put(ROCKS[(x + z) % 2], x, z, CENTRE, (x + z) % 4)
    for z in range(Z0 - 3, Z1 + 4, 3):
        for x in (X0 - 3, X1 + 2):
            sq.put(ROCKS[(x + z) % 2], x, z, CENTRE, (x + z) % 4)

    # ---- THE CAMP: where ::sz lands. Nothing here is walled; it is a camp, not a building.
    sq.put('altar', 28, 35, CENTRE, 0, blocks=2)       # width 2: op1 Pray-at, a table's width clear of it
    sq.put('signpost', 34, 32)
    sq.put('roundtable', 33, 35)
    sq.put('chair', 32, 35, CENTRE, 0)
    sq.put('chair', 34, 35, CENTRE, 2)
    sq.put('chair', 33, 36, CENTRE, 1)

    # ---- THE OFFICE
    sq.floor(OFFICE, WOOD, flags=INDOORS)
    sq.enclose(OFFICE, WALL, door_at=OFFICE_DOOR, door_name=DOOR)
    x0, x1, z0, z1 = OFFICE
    sq.put('favour_podium_lectern', 17, 50)
    for i, x in enumerate((13, 14, 15)):
        sq.put('bookcase', x, z1, CENTRE, 1)
    sq.put('table', 15, 45)
    sq.put('chair', 14, 45, CENTRE, 0)
    sq.put('chair', 16, 45, CENTRE, 2)
    sq.locs.append((sq.names[TORCH], 0, x0, 44, DECOR, EDGE_ROT['west']))
    sq.locs.append((sq.names[TORCH], 0, x0, 48, DECOR, EDGE_ROT['west']))
    sq.locs.append((sq.names[TORCH], 0, x1, 44, DECOR, EDGE_ROT['east']))

    # The two cells. Bars on every edge but the door's, one wall loc per tile, and the flood fill
    # below walks through the shut door to prove a cell can be got into and out of.
    for cx0, cx1, cz0, cz1 in CELLS:
        sq.enclose((cx0, cx1, cz0, cz1), BARS,
                   door_at=((cx0 + cx1) // 2, CELL_DOOR), door_name=DOOR)

    # ---- THE VAULT
    sq.floor(VAULT, BANK_A, flags=INDOORS, chequer=BANK_B)
    sq.enclose(VAULT, WALL, door_at=VAULT_DOOR, door_name=DOOR)
    vx0, vx1, vz0, vz1 = VAULT
    for x in range(40, 44):
        sq.put('bankbooth', x, 48, CENTRE, 1)
    sq.locs.append((sq.names['banknoticeboard'], 0, 45, vz1, DECOR, EDGE_ROT['north']))
    sq.npc('banker1', 41, 49)
    sq.npc('banker2', 43, 49)
    sq.npc('generalshopkeeper5', 46, 43)
    sq.npc('generalassistant5', 47, 43)
    sq.put('table', 46, 44)

    # ---- THE RANGE
    for i, x in enumerate(range(14, 24, 2)):
        sq.put('sworddummy', x, 20)                    # op2 Attack, wired in area_varrock
    sq.put('target', 14, 23)
    sq.put('target', 16, 23)

    sq.floor(PAD_RECT, PAD)                            # bare pad: ::npcadd wants room, not scenery

    sq.floor(RING_RECT, RING)
    rx0, rx1, rz0, rz1 = RING_RECT
    for x in range(rx0 + 1, rx1):                      # corners left open - the way in, no gate
        sq.wall(FENCE, x, rz0, ['south'])
        sq.wall(FENCE, x, rz1, ['north'])
    for z in range(rz0 + 1, rz1):
        sq.wall(FENCE, rx0, z, ['west'])
        sq.wall(FENCE, rx1, z, ['east'])

    return sq


def districts():
    return {'camp': CAMP, 'office': OFFICE, 'vault': VAULT,
            'pad': PAD_RECT, 'ring': RING_RECT,
            'cell 1': CELLS[0], 'cell 2': CELLS[1]}


def preview(sq, seen):
    marks = {}
    for name, (x0, x1, z0, z1) in districts().items():
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                marks[(x, z)] = name[0].upper()
    lines = []
    for z in range(63, -1, -1):
        row = ''
        for x in range(64):
            if (x, z) == ARRIVE:
                row += '@'
            elif (x, z) in sq.wall_layer:
                row += '#'
            elif (x, z) in sq.full:
                row += 'o'
            elif sq.walkable(x, z):
                row += marks.get((x, z), '.' if (x, z) in seen else '!')
            else:
                row += ' '
        lines.append('%2d %s' % (z, row))
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--preview', action='store_true')
    a = ap.parse_args()

    sq = build()
    seen = sq.reachable()
    walk = sum(1 for x in range(64) for z in range(64) if sq.walkable(x, z))

    print('%s: world x %d..%d, z %d..%d' % (SQUARE, BASE_X + X0, BASE_X + X1, BASE_Z + Z0, BASE_Z + Z1))
    print('   %d walkable tiles, %d reachable from ::sz (0_%s_%d_%d), %d locs, %d npcs'
          % (walk, len(seen), SQUARE, ARRIVE[0], ARRIVE[1], len(sq.locs), len(sq.npcs)))

    bad = []
    for name, (x0, x1, z0, z1) in districts().items():
        tiles = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if sq.walkable(x, z)]
        out = [t for t in tiles if t not in seen]
        print('   %-7s %2d/%-2d tiles reachable' % (name, len(tiles) - len(out), len(tiles)))
        if out or not tiles:
            bad.append((name, out))
    stranded = sum(1 for x in range(64) for z in range(64) if sq.walkable(x, z) and (x, z) not in seen)
    print('   %d walkable tiles stranded anywhere on the square' % stranded)

    # AND THE CELLS HOLD. The fill above walks through a shut door, which is what proves a cell can
    # be entered and left; this one treats every door as shut, and a cell tile it can still reach is
    # a cage with a gap in it.
    shut = sq.reachable(doors_shut=True)
    for i, (x0, x1, z0, z1) in enumerate(CELLS, 1):
        leaks = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1) if (x, z) in shut]
        print('   cell %d holds with the door shut: %s' % (i, 'no - %s' % leaks[:3] if leaks else 'yes'))
        if leaks:
            bad.append(('cell %d leaks' % i, leaks))

    if a.preview:
        print(preview(sq, seen))

    if bad:
        raise SystemExit('REFUSING TO WRITE: unreachable %s' % ', '.join(n for n, _ in bad))

    if a.dry_run:
        return
    out = os.path.join(ROOT, 'maps', 'm%s.jm2' % SQUARE)
    jm2.write(out, sq.land, sq.locs, sq.npcs, [])
    print('   wrote %s' % out)
    print('   %s' % register())


def register():
    """Give the square its two ids in pack/map.pack, which is what makes the build see it at all.

    MapPack is a PackFile built with verify=false (Engine-TS/tools/pack/PackFile.ts), so a .jm2 with
    no ID line is not an error - it is silently skipped, and the square is simply not in the build:
    no collision on the server, no archive for the client, and a ::sz into a black void. Found that
    way, before anybody saw the zone.

    Two ids per square, m for the terrain and l for the locs, appended after the highest in the file
    rather than slotted into the gaps left by the original cache's own numbering - which is what was
    done for the Land of the Frogs (1552/1553) and for every square added since. The ids mean nothing
    to the client beyond matching the version list the build writes from this same file.
    """
    path = os.path.join(ROOT, 'pack', 'map.pack')
    raw = open(path, newline='').read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    lines = [l for l in raw.split(nl) if l.strip()]
    have = {l.split('=', 1)[1]: int(l.split('=', 1)[0]) for l in lines}
    want = ['m%s' % SQUARE, 'l%s' % SQUARE]
    if all(n in have for n in want):
        return 'pack/map.pack already has %s (%s)' % (', '.join(want), ', '.join(str(have[n]) for n in want))
    nxt = max(have.values()) + 1
    for n in want:
        if n in have:
            raise SystemExit('pack/map.pack has %s but not its pair - fix it by hand' % n)
        lines.append('%d=%s' % (nxt, n))
        nxt += 1
    open(path, 'w', newline='').write(nl.join(lines) + nl)
    return 'pack/map.pack: added %s' % ', '.join(lines[-2:])


if __name__ == '__main__':
    main()
