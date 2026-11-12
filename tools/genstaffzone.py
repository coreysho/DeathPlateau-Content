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

# THE PALETTE IS WHITE WOLF MOUNTAIN'S, NOT DEATH PLATEAU'S, and that is a correction.
#
# The first build took the ground from maps/m44_56.jm2 on the reasoning that Death Plateau is the
# plateau this server is named after. Rendered with the real client code (tools/models/renderscene.py)
# it is dull brown - and correctly so: flo "mountain_dark" is 0x464034, the Death Plateau IS a brown
# rocky shelf above Burthorpe, and a staff zone floored in it looks like a car park. White Wolf
# Mountain, two squares south, is where the snow is: "ice", 0xeeeeee.
#
# A MAP TILE'S FLO ID IS ONE MORE THAN THE FLO'S OWN. The client resolves both underlay and overlay
# through FloType.field796[id - 1] (World.java), so writing 54 into a .jm2 draws flo 53. Every
# colour in the first two versions of this file was one out, which is how the "lightrock" sparring
# ring rendered in swamp green. So nothing here is a number: flo() takes the name out of
# content/pack/flo.pack and adds the one, and the names below are the names in that file.
def pack(name):
    out = {}
    with open(os.path.join(ROOT, 'pack', name + '.pack'), encoding='utf-8') as fh:
        for line in fh:
            if '=' in line:
                i, n = line.strip().split('=', 1)
                out[n] = int(i)
    return out


_FLO = pack('flo')


def flo(name):
    return _FLO[name] + 1


HEIGHT = 120                               # the plateau floor: flat, so nothing walks on a slope
PEAK = 246                                 # the ring of mountains around it, at the square's edge
SNOW = flo('ice')                          # 0xeeeeee - what White Wolf Mountain is covered in
ROCK_UN = flo('darkrock')                  # 0x4d4d4d - the lower slopes of the ring
ROCK_OV = flo('lightrock')                 # 0x767676 - patches, paths and the sparring ring
WOOD = flo('woodenfloor')                  # the Office. The first build wrote 4 and got cliff4,
                                           # a grey stone slab, which is why it looked like a cell
VAULT_FLOOR = flo('cliff4')                # 0x888888 - one pale stone floor. The bank's two-tile
                                           # chequer read as a kitchen, which a vault is not
PAD = flo('darkstone')                     # 0x222222 - the boss pad, bare and unmistakable
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
# Worn tracks: the camp to each district's door, as pairs of tiles. Straight lines only - two
# segments make a corner where they meet, which is all a path up here needs to be.
PATHS = [((32, 32), (32, 44)), ((18, 37), (32, 37)), ((44, 37), (32, 37)),
         ((32, 32), (32, 20)), ((20, 21), (32, 21)), ((46, 21), (32, 21))]
PAD_RECT = (28, 35, 12, 19)
RING_RECT = (42, 50, 12, 20)

WALL = 'brickwall'
DOOR = 'loc_1513'                          # "Large door", [oploc1,_door_closed] - opens and shuts
# THE CELLS ARE DRAYNOR JAIL'S, NOT A FENCE. prisonbars is a wall loc that draws a short railing,
# and eight of them round a 3x3 room read in game as scattered fence posts rather than a cage. The
# jail at 3126,3244 is built of oldbigstone_castlewall with prisonwindow set into it and a
# hanginglantern over the door, so that is what a holding cell is here too.
CELL_WALL = 'oldbigstone_castlewall'
CELL_WINDOW = 'prisonwindow'
LANTERN = 'hanginglantern'
FENCE = 'railing'
TORCH = 'torch'
FIRE = 'fire_graphic'                      # anim=wiztorch, active=no - a fire that burns and does nothing
SNOW_DECOR = ('snow1', 'snow2', 'snow3')   # the drifts White Wolf is covered in
TREES = ('evergreen', 'deadtree2_snowy')
ROCKS = ('death_mountainrocks_1', 'death_rockslide5')

# shape, and the rotation that puts a wall on each edge of its own tile
STRAIGHT, CORNER, DECOR, CENTRE, GROUND = 0, 2, 4, 10, 22
EDGE_ROT = {'west': 0, 'north': 1, 'east': 2, 'south': 3}
# A corner covers two edges: 0 west+north, 1 north+east, 2 east+south, 3 south+west
CORNER_ROT = {('west', 'south'): 3, ('west', 'north'): 0, ('east', 'north'): 1, ('east', 'south'): 2}


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

    def floor(self, rect, overlay, flags=0, chequer=None, underlay=SNOW):
        x0, x1, z0, z1 = rect
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                ov = overlay if chequer is None else (overlay if (x + z) % 2 else chequer)
                self.tile(x, z, overlay=ov, flags=flags, underlay=underlay)

    # --- locs ---

    def put(self, name, x, z, shape=CENTRE, rot=0, w=1, l=1):
        """Something standing on the ground, and the tiles it stands on.

        THE FOOTPRINT IS CHECKED, because a loc's own width and length are in its config and not in
        my head: the fountain is 2x2, the furnace and a wilderness obelisk are 3x3, a telescope is
        1x3 and the trading post is 2x1. Laying a dozen of them out by eye put two on one tile and
        another across the path on the first attempt. A rotated loc swaps its width and length -
        the client does, so this does.

        Ground decor (shape 22) is not a footprint: a rug and a drift are painted on the tile and
        nothing stands on them, so they are not recorded and do not collide.
        """
        self.locs.append((self.names[name], 0, x, z, shape, rot))
        if shape not in (CENTRE, CENTRE + 1):
            return
        ww, ll = (w, l) if rot % 2 == 0 else (l, w)
        for dx in range(ww):
            for dz in range(ll):
                t = (x + dx, z + dz)
                if t in self.full:
                    raise SystemExit('two locs on tile %d,%d - the second is %s' % (t[0], t[1], name))
                if t == ARRIVE:
                    raise SystemExit('%s stands on the ::sz arrival tile' % name)
                indoors = any(x0 <= t[0] <= x1 and z0 <= t[1] <= z1
                              for x0, x1, z0, z1 in (OFFICE, VAULT))
                if on_path(*t) and not indoors:
                    raise SystemExit('%s at %d,%d stands in the path' % (name, t[0], t[1]))
                self.full.add(t)

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

    def decor(self, name, x, z, edge, offset=False):
        """Something hung on the wall of this tile: a window, a lantern, a torch.

        WALLDECOR is its own loc layer, so it shares a tile with the wall it hangs on and with
        whatever stands on that tile - which is why these are not routed through put() or wall().
        """
        self.locs.append((self.names[name], 0, x, z,
                          DECOR + (1 if offset else 0), EDGE_ROT[edge]))

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


def _hash(a, b):
    """A deterministic 0..1 from a pair of ints. No seed, no random: the same map every run."""
    h = (a * 73856093) ^ (b * 19349663)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xffff) / 65535.0


def noise(x, z, cell):
    """Smooth value noise: the corners of a cell-sized grid, interpolated.

    A hash taken per tile is static and a hash taken per 3x3 block is a grid of squares - the first
    build's rock patches were the second, and rendered as a chequerboard of mud with hard right
    angles across a snowfield. Interpolating between grid corners gives blobs with soft edges, which
    is what a patch of bare rock looks like from above.
    """
    gx, gz = x / cell, z / cell
    x0, z0 = int(gx // 1), int(gz // 1)
    fx, fz = gx - x0, gz - z0
    fx = fx * fx * (3 - 2 * fx)                       # smoothstep, so cells do not show as creases
    fz = fz * fz * (3 - 2 * fz)
    n00, n10 = _hash(x0, z0), _hash(x0 + 1, z0)
    n01, n11 = _hash(x0, z0 + 1), _hash(x0 + 1, z0 + 1)
    return (n00 * (1 - fx) + n10 * fx) * (1 - fz) + (n01 * (1 - fx) + n11 * fx) * fz


def on_path(x, z):
    """A worn track, one tile wide with a ragged edge.

    One tile, not three. Three was a brown motorway through the middle of the zone - the render
    showed a cross you could have landed a plane on - and a path up here is a line of footprints.
    """
    for (ax, az), (bx, bz) in PATHS:
        if ax == bx and x == ax and min(az, bz) <= z <= max(az, bz):
            return True
        if az == bz and z == az and min(ax, bx) <= x <= max(ax, bx):
            return True
        # the ragged half-tile either side, so the line is not drawn with a ruler
        if ax == bx and abs(x - ax) == 1 and min(az, bz) <= z <= max(az, bz) and _hash(x, z) < 0.45:
            return True
        if az == bz and abs(z - az) == 1 and min(ax, bx) <= x <= max(ax, bx) and _hash(x, z) < 0.45:
            return True
    return False


def rock_patch(x, z):
    """Where the snow is worn through to bare rock on the plateau floor, as overlay 22.

    White Wolf Mountain is roughly seven tiles of snow to three of rock, and the rock is in drifts
    with soft edges. This thresholds the smooth noise above, and DITHERS the band either side of the
    threshold - a tile close to the edge goes either way on its own hash - so the boundary comes out
    ragged at tile scale instead of as a drawn line. The client can draw a diagonal half-tile
    (overlay shape 1 and up, which is what m44_54 uses) but a ragged edge needs no shapes at all.
    """
    if on_path(x, z):
        return ROCK_OV
    n = noise(x, z, 9)
    if n > 0.76:
        return ROCK_OV
    if n > 0.68 and _hash(x * 3, z * 5) < (n - 0.68) / 0.08:
        return ROCK_OV
    return None


def relief(x, z):
    """A few units of height on the open plateau, and dead flat everywhere that is built on.

    WHY AT ALL. Snow in this client is lit, not textured: White Wolf Mountain reads as bright white
    because every slope on it catches the light differently. One flat plane catches it all the same
    way, and 2,278 tiles of it rendered as a sheet of grey card - which is what the floor looked
    like after the palette was fixed and before this was added.

    WHY SO LITTLE. Six units is a third of a step. It shades the ground without putting anything on
    a slope: the districts, their doors and the ring stay exactly level, and so does a one-tile
    margin round each of them, so no wall ever meets ground that is not flat under it.
    """
    for x0, x1, z0, z1 in (OFFICE, VAULT, PAD_RECT, RING_RECT, CELLS[0], CELLS[1]):
        if x0 - 2 <= x <= x1 + 2 and z0 - 2 <= z <= z1 + 2:
            return HEIGHT
    return HEIGHT + int(round((noise(x, z, 11) - 0.5) * 16))


def build():
    sq = Square(pack('loc'), pack('npc'))

    # THE PLATEAU FLOOR, and the mountains that ring it.
    #
    # A BOWL, NOT A SLAB. The first build was one flat height across all 64 squares, with eight
    # tiles of blocked ground round the walkable part and a few rocks on it. Rendered, that is a
    # brown table top with a black void past its edge, and in game you can see the edge of the
    # world from the camp. Here the ground outside the plateau RISES instead - steeply, to the
    # square's border - so the zone sits in a snow cirque with a horizon of peaks and no void in
    # any direction. It costs nothing in collision: the ring is flagged blocked either way, and
    # the height is only what the client draws.
    for x in range(64):
        for z in range(64):
            inside = X0 <= x <= X1 and Z0 <= z <= Z1
            if inside:
                sq.tile(x, z, overlay=rock_patch(x, z), flags=0, underlay=SNOW, height=relief(x, z))
                continue
            # how far outside the plateau this tile is, 1 at the foot of the slope
            d = max(X0 - x, x - X1, Z0 - z, z - Z1, 0)
            far = max(X0, 63 - X1, Z0, 63 - Z1)
            climb = (d / far) ** 1.6
            # Ridges and gullies, from the same smooth noise as everything else. A modulo pattern
            # here drew the mountainside as a regular chequer of brown diamonds on white - a quilt,
            # not a mountain - which is what the first render of this slope showed.
            jag = (noise(x, z, 6) - 0.5) * 46 * min(1.0, d / 3)
            h = int(HEIGHT + (PEAK - HEIGHT) * climb + jag)
            # A SNOW LINE, the right way up. Rock is the lower slope and the snow caps the peaks -
            # the first cut had it backwards (more rock the higher it went) and rendered the ring as
            # a wall of brown with a white skirt, which is a quarry, not a mountain.
            r = noise(x, z, 7) - d / (far * 1.3)
            ov = ROCK_OV if r > 0.34 else None
            sq.tile(x, z, overlay=ov, flags=BLOCKED, underlay=SNOW if ov is None else ROCK_UN,
                    height=min(255, max(0, h)))

    # A TREE LINE ON THE SLOPES, which is what hides the square's own border - every one of them
    # stands on ground that is blocked anyway, so none of them is in the way of anything.
    for x in range(2, 62, 3):
        for z in range(2, 62, 3):
            if X0 - 1 <= x <= X1 + 1 and Z0 - 1 <= z <= Z1 + 1:
                continue
            n = _hash(x * 3 + 1, z * 7 + 5)
            if n < 0.42:
                sq.put(TREES[0 if _hash(x, z) < 0.62 else 1], x, z, CENTRE, (x + z) % 4)
            elif n < 0.56:
                sq.put(ROCKS[(x + z) % 2], x, z, CENTRE, (x + z) % 4)

    # DRIFTS ON THE PLATEAU ITSELF. Ground decor, so nothing blocks and nothing is in the way; it
    # is what stops 2,278 tiles of flat white reading as a bedsheet.
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            if (x * 13 + z * 7) % 9 == 0 and not any(a <= x <= b and c <= z <= d
                                                     for a, b, c, d in (OFFICE, VAULT)):
                sq.put(SNOW_DECOR[(x + z) % 3], x, z, GROUND, (x + z) % 4)

    # ---- THE CAMP: where ::sz lands. Nothing here is walled; it is a camp, not a building.
    #
    # Laid out round the paths rather than across them, which the footprint check enforces - the
    # first version had a chair standing in the middle of the north path and nobody noticed.
    sq.put('altar', 28, 35, CENTRE, 0, w=2)            # width 2: op1 Pray-at
    sq.put('fountain', 35, 34, CENTRE, 0, w=2, l=2)    # the one thing up here that is not grey
    sq.put('telescope', 27, 29, CENTRE, 0, l=3)        # 1x3, pointed at the sky over the peaks

    # Two warriors either side of the way in from the south, because a staff zone may as well
    # announce itself.
    sq.put('statue_malewarrior', 30, 28)
    sq.put('statue_femalewarrior', 34, 28)

    # The four kingdoms on the camp's south edge. Asgarnia is Burthorpe's, which is the closest
    # thing to a claim this plateau has.
    for i, (fx, flag) in enumerate(((28, 'flagpole_asgarnia'), (29, 'flagpole_kandarin'),
                                    (35, 'flagpole_ardougne'), (36, 'flagpole'))):
        sq.put(flag, fx, 27)

    sq.put('table', 35, 30)
    sq.put('chair', 34, 30, CENTRE, 0)
    sq.put('chair', 36, 30, CENTRE, 2)
    sq.put('signpost', 34, 33)
    # Four fires, two of them flanking the arrival tile. Nothing up here is lit otherwise: the
    # render came back a dark field with an altar in it, and a camp at altitude with no fire reads
    # as abandoned. fire_graphic is anim=wiztorch and active=no - it burns and cannot be clicked.
    for fx, fz in ((29, 32), (35, 32), (27, 34), (37, 34)):
        sq.put(FIRE, fx, fz)

    # ---- THE OFFICE
    sq.floor(OFFICE, WOOD, flags=INDOORS)
    sq.enclose(OFFICE, WALL, door_at=OFFICE_DOOR, door_name=DOOR)
    x0, x1, z0, z1 = OFFICE
    sq.put('favour_podium_lectern', 17, 50)
    for x in (13, 14, 15):
        sq.put('bookshelf_old_tall', x, z1, CENTRE, 1)
    sq.put('globe_model', 17, 46)
    for i, (cx, cz) in enumerate(((13, 39), (14, 39), (13, 40))):
        sq.put(('crate2', 'boxes', 'sacks')[i], cx, cz)
    sq.put('candles', 23, 51)
    # A rug under the desk: ground decor, so it collides with nothing and the table stands on it.
    for dx in (-1, 0, 1):
        for dz in (-1, 0, 1):
            piece = ('rugmiddle_verydark' if (dx, dz) == (0, 0)
                     else 'rugcorner_verydark' if dx and dz else 'rugside_verydark')
            rot = (0 if dz == 1 else 2 if dz == -1 else 1 if dx == -1 else 3)
            sq.put(piece, 15 + dx, 45 + dz, GROUND, rot)
    sq.put('table', 15, 45)
    sq.put('chair', 14, 45, CENTRE, 0)
    sq.put('chair', 16, 45, CENTRE, 2)
    for tz in (42, 46, 50):
        sq.decor(TORCH, x0, tz, 'west')
        sq.decor(TORCH, x1, tz, 'east')
    sq.decor(LANTERN, 17, z1, 'north')

    # The two cells, built the way Draynor jail is: solid stone, a barred window in each wall that
    # has room for one, and a lantern over the door. One wall loc per tile, and the flood fill below
    # walks through the shut door to prove a cell can still be got into and out of.
    for cx0, cx1, cz0, cz1 in CELLS:
        door_x = (cx0 + cx1) // 2
        sq.enclose((cx0, cx1, cz0, cz1), CELL_WALL, door_at=(door_x, CELL_DOOR), door_name=DOOR)
        # a window in the three walls that are not the door, set in the middle tile of each
        sq.decor(CELL_WINDOW, door_x, cz1, 'north')
        sq.decor(CELL_WINDOW, cx0, (cz0 + cz1) // 2, 'west')
        sq.decor(CELL_WINDOW, cx1, (cz0 + cz1) // 2, 'east')
        sq.decor(LANTERN, door_x, cz0, 'south')

    # ---- THE VAULT
    sq.floor(VAULT, VAULT_FLOOR, flags=INDOORS)
    sq.enclose(VAULT, WALL, door_at=VAULT_DOOR, door_name=DOOR)
    vx0, vx1, vz0, vz1 = VAULT
    # ROTATION 2, AND IT IS READ OFF EDGEVILLE RATHER THAN GUESSED. The booths at 3095,3489 and
    # 3095,3491 are rot 3 with their banker to the EAST; the pair at 3096,3493 and 3098,3493 are
    # rot 0 with their banker to the SOUTH. So the banker's side runs 0 south, 1 west, 2 north,
    # 3 east. These two bankers stand north of the counter, which makes it rot 2 - it was built at
    # rot 1 and faced the players sideways.
    for x in range(40, 44):
        sq.put('bankbooth', x, 48, CENTRE, 2)
    sq.decor('banknoticeboard', 45, vz1, 'north')
    for tz in (41, 45, 49):
        sq.decor(TORCH, vx0, tz, 'west')
        sq.decor(TORCH, vx1, tz, 'east')
    sq.npc('banker1', 41, 49)
    sq.npc('banker2', 43, 49)
    sq.npc('generalshopkeeper5', 46, 43)
    sq.npc('generalassistant5', 47, 43)
    sq.put('table', 46, 44)

    # THE TRADING POST, which is the one thing in here that is not a copy of something in Edgeville:
    # it is this server's own (scripts/tradingpost), and a staff zone is exactly where somebody
    # wants to read what the economy is asking for a whip without walking to the bank. width 2,
    # forceapproach=south, so the two tiles below it are kept clear. The icon loc goes on the same
    # tile it does at 3084,3492, so it shows on the minimap here too.
    sq.put('trading_post', 46, 49, CENTRE, 0, w=2)
    sq.put('trading_post_icon', 46, 49, GROUND, 0)
    for i, (cx, cz) in enumerate(((50, 40), (50, 41), (49, 40), (50, 43))):
        sq.put(('crate2', 'barrel', 'boxes', 'sacks')[i], cx, cz)
    sq.put('candles', 39, 49)

    # ---- THE RANGE
    # z 18, not 20: the east-west path runs along z 21 and its ragged edge reaches z 20, so two of
    # these five were standing in it. x stops at 21 to stay clear of the furnace's 3x3 at 22.
    for x in range(13, 23, 2):
        sq.put('sworddummy', x, 18)                    # op2 Attack, wired in area_varrock
    sq.put('target', 14, 23)
    sq.put('target', 16, 23)

    # A corner to test a skill in, which is what staff on a live world actually need: a furnace
    # (3x3, approached from the east, so 25,17 is left open), an anvil beside it, and a wheel.
    sq.put('furnace1', 22, 16, CENTRE, 0, w=3, l=3)
    sq.put('anvil', 26, 17)
    sq.put('spinningwheel', 26, 15)                    # forceapproach=south: 26,14 stays clear
    # A cannon nobody can fire and a wilderness obelisk nobody can step through. Both are here
    # because they are the sort of thing you walk over to look at.
    sq.put('cannon', 38, 23, CENTRE, 0, l=2)
    sq.put('obelisk_earth', 38, 26, CENTRE, 0, w=3, l=3)

    sq.floor(PAD_RECT, PAD)                            # bare pad: ::npcadd wants room, not scenery

    # Rock swept clear of snow, not the Duel Arena's own floor - overlay 76 came out bright yellow
    # sand against the white, which is a beach with a fence round it.
    sq.floor(RING_RECT, ROCK_OV, underlay=ROCK_UN)
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
