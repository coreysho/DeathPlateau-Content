"""The Temple of Light's two generated files. Run from content/.

    python tools/genlighttemple.py

Writes:
  scripts/quests/quest_mourning2/scripts/mourning2_graph.rs2   the beam graph, carrying a colour
  scripts/quests/quest_mourning2/scripts/mourning2_doors.rs2   the fourteen doors of light
  scripts/quests/quest_mourning2/scripts/mourning2_pillars.rs2 the thirty-five pillar sockets

WHERE EACH PART COMES FROM, because the two halves have different sources:

  The VERTICAL EDGES are derived here, from the pillar table in the file's own header: the pillars
  stack, so the same room on the next floor up is a vertical neighbour, and the beam between them is
  the lower pillar's _up varbit. They are rebuilt on every run, so this is the file to change if the
  third dimension is ever wrong.

  The HORIZONTAL EDGE TABLE is read back out of the existing mourning2_graph.rs2 and re-emitted. It was
  extracted from maps/m29_72.jm2 once - every edge is the real run of mourning_light_temple_beam_*
  tiles between two real pillars - and that extraction is not repeated here, because re-deriving a
  graph that is already correct and already verified symmetric (86 edges) only risks disagreeing
  with it. The parse is lossless and the re-emission is idempotent: run this twice and the second
  run is a no-op. Anything that needs the edges CHANGED - the vertical beams, for one - changes
  them here, in the table, and this file re-emits them.

  The DOOR TABLE is derived fresh, from the map and from configs/mourning2.loc:

    * every mourning_door_* placement on maps/m29_72.jm2
    * the colour it shows when shut, which is multiloc=0 of the door's own multiloc
      (mourning_door_of_light_<colour>, or mourning_crystal_magenta, which despite its name is a
      magenta door of light and not a crystal at all)
    * the beam segment it stands in, found by looking at the door's tile and its neighbours for a
      mourning_light_temple_beam_* loc and reading that beam's multivar

  A door opens when the light standing in its doorway is the colour the door shows. A door whose
  shut state is BLACK shows no colour at all, so any light opens it - which is how the door to the
  Death Altar works, and why its varbit is called mourning_light_door_1_c_first_time.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GRAPH = os.path.join(ROOT, 'scripts/quests/quest_mourning2/scripts/mourning2_graph.rs2')
DOORS = os.path.join(ROOT, 'scripts/quests/quest_mourning2/scripts/mourning2_doors.rs2')
PILLARS = os.path.join(ROOT, 'scripts/quests/quest_mourning2/scripts/mourning2_pillars.rs2')
LOCCFG = os.path.join(ROOT, 'scripts/quests/quest_mourning2/configs/mourning2.loc')
LOCPACK = os.path.join(ROOT, 'pack/loc.pack')
MAP = os.path.join(ROOT, 'maps/m29_72.jm2')

NL = chr(10)

# the cache's own colour numbering, read off any pillar's multiloc list:
#   multiloc=1,..._red  2,..._yellow  3,..._green  4,..._cyan  5,..._blue  6,..._magenta  7,..._white
COLOURNAME = {1: 'red', 2: 'yellow', 3: 'green', 4: 'cyan', 5: 'blue', 6: 'magenta', 7: 'white'}
COLOUR = {'red': 1, 'yellow': 2, 'orange': 2, 'green': 3, 'cyan': 4, 'blue': 5,
          'magenta': 6, 'purple': 6, 'white': 7}


def read(path):
    return io.open(path, encoding='utf-8', errors='replace', newline='').read().replace('\r\n', NL)


def write(path, text):
    old, nl = '', NL
    if os.path.exists(path):
        raw = io.open(path, encoding='utf-8', errors='replace', newline='').read()
        old = raw.replace(chr(13) + NL, NL)
        nl = chr(13) + NL if chr(13) + NL in raw else NL
    io.open(path, 'w', encoding='utf-8', newline='').write(text.replace(NL, nl))
    return 'unchanged' if old == text else 'written'


# --------------------------------------------------------------------------- the edge table
def parse_pillars_header(header):
    """pillar id -> (floor, room) off the header table the extractor wrote."""
    out = {}
    for m in re.finditer(r'// (\d+)\s+floor (\d) pillar ([0-9a-z]+)\s', header):
        out[int(m.group(1))] = (int(m.group(2)), m.group(3))
    return out


def vertical_edges(pillars, ups):
    """THE THIRD DIMENSION, derived rather than measured: the pillars stack - floor 1 room 3 is on
    (42,57) and so are floor 2 room 3 and floor 3 room 3 - so a vertical edge is the same room on
    the next floor up, where both pillars exist. The beam between them is the LOWER pillar's
    <floor>_<room>_up varbit, which is also the varbit its own loc renders, because the cache's lit
    pillar model is a pillar with light going up out of it.

    The shaft is the one exception and the one the old trace hardcoded: floor 3 pillar a drops two
    floors onto floor 1 pillar b, with no floor 2 pillar in between."""
    byroom = {}
    for pid, (floor, room) in pillars.items():
        byroom[(floor, room)] = pid
    edges = {}
    for pid, (floor, room) in sorted(pillars.items()):
        above = byroom.get((floor + 1, room))
        if above is None:
            continue
        seg = ups.get(pid)
        edges[(pid, 5)] = ([seg] if seg else [], above)
        edges[(above, 6)] = ([seg] if seg else [], pid)
    # the shaft, which is a chute and not a corridor
    edges[(29, 6)] = ([], 6)
    return edges


def parse_graph(src):
    """(pillar, dir) -> ([segment varbit, ...], next pillar), plus the three list procs."""
    edges = {}
    body = src.split('[proc,m2_edge]')[1].split('[proc,')[0]
    pillar = None
    direction = None
    for line in body.splitlines():
        s = line.strip()
        m = re.match(r'case (\d+) :$', s)
        if m:
            # the outer switch is on $pillar and the inner on $dir; depth tells them apart
            if line.startswith('    case '):
                pillar = int(m.group(1))
                direction = None
            else:
                direction = int(m.group(1))
                edges[(pillar, direction)] = ([], None)
            continue
        m = re.match(r'%(mourning_light_temple_[a-z0-9_]+) = (?:1|\$colour);$', s)
        if m and direction is not None:
            edges[(pillar, direction)][0].append(m.group(1))
            continue
        # ONLY the returns inside an inner case body, which are indented twelve spaces. The proc's
        # own trailing return(0) is at the left margin, and a first version of this matched it too -
        # which silently rewrote the LAST edge in the table, pillar 35 west, from 34 to 0 and broke
        # the one route the sim drives.
        m = re.match(r'return\((\d+)\);$', s) if line.startswith('            return(') else None
        if m and direction is not None:
            segs, _ = edges[(pillar, direction)]
            edges[(pillar, direction)] = (segs, int(m.group(1)))
    assert all(v[1] is not None for v in edges.values()), 'an edge with no return'

    def varlist(proc):
        chunk = src.split('[proc,%s]()()' % proc)[1].split('[proc,')[0]
        return re.findall(r'%(mourning_light_temple_[a-z0-9_]+) = 0;', chunk)

    ups = {}
    chunk = src.split('[proc,m2_pillar_up]')[1].split('[proc,')[0]
    for m in re.finditer(r'case (\d+) : %(mourning_light_temple_[a-z0-9_]+) = \$colour;', chunk):
        ups[int(m.group(1))] = m.group(2)
    header = src.split('[proc,m2_edge]')[0]
    return edges, varlist('m2_dark'), ups, varlist('m2_pillars_dark'), header


def emit_graph(edges, dark, ups, pdark, header, bysegment, crossings):
    out = [header.rstrip(NL), '']
    out.append('// Returns the pillar the beam arrives at - 0 if it leaves the building - AND the colour it is')
    out.append('// carrying when it gets there, which is not always the colour it set out with: a crossing tile')
    out.append('// where another beam is already standing adds the two together.')
    out.append('[proc,m2_edge](int $pillar, int $dir, int $colour)(int, int)')
    out.append('switch_int ($pillar) {')
    for pillar in sorted({p for p, _ in edges}):
        out.append('    case %d :' % pillar)
        out.append('        switch_int ($dir) {')
        for (p, d), (segs, nxt) in sorted(edges.items()):
            if p != pillar:
                continue
            out.append('        case %d :' % d)
            for s in segs:
                out.append('            %%%s = $colour;' % s)
                for var, axis in sorted(bysegment.get(s, ())):
                    out.append('            $colour = ~m2_cross_%s(%d, $colour);'
                               % (var.replace('mourning_pillar_light_cross_', ''), axis))
            out.append('            return(%d, $colour);' % nxt)
        out.append('        }')
    out.append('}')
    out.append('return(0, $colour);')
    out.append('')
    out.append('// Every segment back to dark. The trace clears the whole temple and relights only')
    out.append('// the path the beam actually takes, so a mirror that breaks the path puts out')
    out.append('// everything after it without anything having to work out what "after" means.')
    out.append('[proc,m2_dark]()()')
    for s in dark:
        out.append('%%%s = 0;' % s)
    out.append('// and the ten crossing tiles, which are enums rather than plain colours')
    for var in sorted(crossings):
        out.append('%%%s = 0;' % var)
    out.append('')
    out.append('// Each pillar has its own <floor>_<room>_up varbit on mourning_quest_vert_beams1-5, and')
    out.append('// the pillar loc is a multiloc on it: 0 is dark and 1-7 are the seven colours.')
    out.append('[proc,m2_pillar_up](int $pillar, int $colour)()')
    out.append('switch_int ($pillar) {')
    for p in sorted(ups):
        out.append('    case %d : %%%s = $colour;' % (p, ups[p]))
    out.append('}')
    out.append('')
    out.append('[proc,m2_pillars_dark]()()')
    for s in pdark:
        out.append('%%%s = 0;' % s)
    out.append(emit_cross_procs(crossings))
    return NL.join(out)


# --------------------------------------------------------------------------- the door table
def locnames():
    ids = {}
    for line in io.open(LOCPACK, encoding='utf-8'):
        if '=' in line:
            i, n = line.strip().split('=', 1)
            ids[int(i)] = n
    return ids


def mapgrid(ids):
    grid = {}
    body = read(MAP).split('==== LOC ====')[1]
    for line in body.splitlines():
        m = re.match(r'(\d+) (\d+) (\d+): (\d+)', line.strip())
        if m:
            pl, x, z, lid = (int(m.group(i)) for i in (1, 2, 3, 4))
            grid.setdefault((pl, x, z), []).append(ids.get(lid, '?'))
    return grid


def doortable():
    cfg = read(LOCCFG)
    beamvar, shutcolour = {}, {}
    for block in re.split(NL + r'(?=\[)', cfg):
        m = re.match(r'\[([a-z0-9_]+)\]', block)
        if not m:
            continue
        name = m.group(1)
        mv = re.search(r'multivar=([a-z0-9_]+)', block)
        if name.startswith('mourning_light_temple_beam_') and mv:
            beamvar[name] = mv.group(1)
        if re.match(r'mourning_door_\d', name):
            shut = re.search(r'multiloc=0,([a-z0-9_]+)', block)
            shutcolour[name] = shut.group(1) if shut else None

    ids = locnames()
    grid = mapgrid(ids)
    placed = {}
    for (pl, x, z), ns in grid.items():
        for n in ns:
            if n in shutcolour:
                placed.setdefault(n, []).append((pl, x, z))

    rows = []
    for door in sorted(placed):
        shut = shutcolour[door] or ''
        m = re.search(r'(red|yellow|orange|green|cyan|blue|magenta|purple|white|black)$', shut)
        colour = 0 if (not m or m.group(1) == 'black') else COLOUR[m.group(1)]
        # the beam this doorway stands in: nearest beam loc to any of the door's tiles
        best = None
        for pl, x, z in sorted(placed[door]):
            for dist in (0, 1, 2):
                for dx in range(-dist, dist + 1):
                    dz = dist - abs(dx)
                    for sz in ({dz, -dz} if dz else {0}):
                        for n in grid.get((pl, x + dx, z + sz), []):
                            if n in beamvar and best is None:
                                best = beamvar[n]
        rows.append((door, colour, best, sorted(placed[door])))
    return rows


def emit_doors(rows):
    out = ["// GENERATED by tools/genlighttemple.py from maps/m29_72.jm2 and configs/mourning2.loc.",
           '// Do not hand-edit.',
           '//',
           '// A door of light shows the colour that opens it. Fourteen doorways carve the three floors',
           '// into rooms, each one a two-state multiloc: shut it is a door of light in its own colour',
           "// (yellow for the pair on floor 1 room 1, cyan for room 13, blue for floor 2 room 16,",
           '// magenta for three more), and open it is white, with Pass-through instead of Pass.',
           '//',
           '// So the lock is: the light standing in the doorway has to be that colour. A door whose shut',
           '// state is BLACK shows no colour, and any light opens it - which is the door to the Death',
           '// Altar, and is why its varbit is mourning_light_door_1_c_first_time.',
           '//',
           '// ~m2_doors is called by the trace once the beams are drawn. The colour each door reads is',
           '// the colour of the beam segment it stands in, which the table below pairs up.',
           '']
    # the Pass triggers belong with the table: each one hands the label the two things it needs,
    # the door's own varbit (open or shut) and the colour the door shows when it is shut
    for door, colour, seg, tiles in rows:
        out.append('[oploc1,%s] @mt_door_pass(%%%s, %s);'
                   % (door, door, '^mt_colour_' + COLOURNAME[colour] if colour else '^mt_colour_dark'))
    out.append('')
    out.append('[proc,m2_doors]()()')
    for door, colour, seg, tiles in rows:
        if seg is None:
            out.append('// %s stands in no beam at all, so no light can ever reach it: it is shut for good.'
                       % door)
            out.append('%%%s = ^mt_off;' % door.replace('mourning_door_', 'mourning_door_'))
            continue
        where = ' '.join('p%d(%d,%d)' % t for t in tiles)
        out.append('// %s   %s' % (door, where))
        if colour == 0:
            out.append('if (%%%s > ^mt_colour_dark) {' % seg)
        else:
            out.append('if (%%%s = ^mt_colour_%s) {' % (seg, COLOURNAME[colour]))
        out.append('    %%%s = ^mt_on;' % door)
        out.append('} else {')
        out.append('    %%%s = ^mt_off;' % door)
        out.append('}')
    out.append('')
    return NL.join(out)


# --------------------------------------------------------------------------- the pillar sockets
def emit_pillars(order):
    """order is pillar id -> loc name, read back out of the file being replaced."""
    out = ['// GENERATED by tools/genlighttemple.py. Do not hand-edit.',
           '//',
           '// Thirty-five pillars, each with a socket at head height. The pillars carry no ops of',
           '// their own - they are multilocs whose children are the lit pillar models - so Search is',
           '// the op every lit state carries, and using a fitting on one is how it goes in. Both',
           '// triggers hand straight over to the labels in quest_mourning2.rs2, which is where the',
           '// socket logic lives: a socket takes a hand mirror (four rotations) or a crystal.',
           '']
    for pid in sorted(order):
        out.append('[oplocu,%s] @mt_use_on_pillar(%d);' % (order[pid], pid))
    out.append('')
    for pid in sorted(order):
        out.append('[oploc1,%s] @mt_search_pillar(%d);' % (order[pid], pid))
    out.append('')
    return NL.join(out)


def parse_pillars(src):
    order = {}
    for m in re.finditer(r'\[oploc(?:1|u),(mourning_temple_pillar_[a-z0-9_]+)\] @mt_\w+\((\d+)\);', src):
        order[int(m.group(2))] = m.group(1)
    return order


# --------------------------------------------------------------------------- the crossing tiles
# TEN TILES WHERE TWO CORRIDORS CROSS AND NO PILLAR STANDS. Each is a
# mourning_light_temple_beam_cross_<floor>_<room> loc on a mourning_pillar_light_cross_* varbit,
# and those varbits are 28-state enums where every other light varbit in the building is a 3-bit
# colour:
#
#    1-7    a north-south beam, in the seven colours
#    8-14   an east-west beam
#    15-21  a vertical beam
#    22-28  a crossed beam - two of them, at once
#
# Nothing wrote them, so ten tiles in the middle of lit corridors stayed dark. Which segment runs
# through which crossing, and on which axis, is read off the map here: the beam locs on the tiles
# north and south of a crossing belong to its north-south run and the ones east and west to its
# east-west run, and each of those locs carries the segment varbit as its own multivar.
CROSS_NS = 0
CROSS_EW = 7
CROSS_VERT = 14
CROSS_BOTH = 21


def crosstable():
    """segment varbit -> [(crossing varbit, axis base), ...], and the crossings themselves."""
    cfg = read(LOCCFG)
    beamvar, crossvar = {}, {}
    for block in re.split(NL + r'(?=\[)', cfg):
        m = re.match(r'\[([a-z0-9_]+)\]', block)
        if not m:
            continue
        name = m.group(1)
        mv = re.search(r'multivar=([a-z0-9_]+)', block)
        if not mv:
            continue
        if name.startswith('mourning_light_temple_beam_cross_'):
            crossvar[name] = mv.group(1)
        elif name.startswith('mourning_light_temple_beam_'):
            beamvar[name] = mv.group(1)

    ids = locnames()
    grid = mapgrid(ids)
    bysegment = {}
    crossings = {}
    for (pl, x, z), ns in sorted(grid.items()):
        for n in ns:
            if n not in crossvar:
                continue
            var = crossvar[n]
            # ONE OF THE ELEVEN IS NOT A CROSSING AT ALL: the loc at floor 2 room 8 is a
            # beam_cross loc whose multivar is mourning_light_temple_2_8_up, a plain three-bit
            # colour, so it is a vertical beam and the vertical edges already light it.
            if var.endswith('_up'):
                continue
            crossings[var] = (pl, x, z)
            for dx, axis in ((1, CROSS_EW), (-1, CROSS_EW)):
                for nb in grid.get((pl, x + dx, z), []):
                    if nb in beamvar:
                        bysegment.setdefault(beamvar[nb], set()).add((var, axis))
            for dz, axis in ((1, CROSS_NS), (-1, CROSS_NS)):
                for nb in grid.get((pl, x, z + dz), []):
                    if nb in beamvar:
                        bysegment.setdefault(beamvar[nb], set()).add((var, axis))
    return bysegment, crossings


def emit_cross_procs(crossings):
    out = ['',
           '// Each crossing tile gets its own proc, because a varbit cannot be passed to one. $axis',
           '// is 0 for a north-south beam, 7 for east-west, 14 for a vertical one; a beam arriving',
           '// at a tile that already holds a beam on ANOTHER axis makes it a crossed beam, and the',
           '// colour it is drawn in is the two colours added - which is the only way anything in',
           '// this temple can be magenta.']
    for var in sorted(crossings):
        short = var.replace('mourning_pillar_light_cross_', '')
        out.append('')
        out.append('[proc,m2_cross_%s](int $axis, int $colour)(int)' % short)
        out.append('def_int $now = %%%s;' % var)
        out.append('if ($now = ^mt_colour_dark) {')
        out.append('    %%%s = add($axis, $colour);' % var)
        out.append('    return($colour);')
        out.append('}')
        out.append('if ($now > $axis & $now <= add($axis, ^mt_colour_white)) {')
        out.append('    // the same axis again: the two together are what shows')
        out.append('    def_int $both = ~mt_colour_add(sub($now, $axis), $colour);')
        out.append('    %%%s = add($axis, $both);' % var)
        out.append('    return($both);')
        out.append('}')
        out.append('// TWO BEAMS CROSSING, and they add - which is the only way to magenta.')
        out.append('def_int $sum = ~mt_colour_add(~mt_cross_colour($now), $colour);')
        out.append('%%%s = add(^mt_cross_both, $sum);' % var)
        out.append('return($sum);')
    out.append('')
    return NL.join(out)


def main():
    src = read(GRAPH)
    edges, dark, ups, pdark, header = parse_graph(src)
    horizontal = len(edges)
    pillars = parse_pillars_header(header)
    assert len(pillars) == 35, 'parsed %d pillars from the header' % len(pillars)
    # a re-run must not double-count: the vertical edges are derived, so they are rebuilt every time
    edges = {k: v for k, v in edges.items() if k[1] <= 4}
    horizontal = len(edges)
    edges.update(vertical_edges(pillars, ups))
    print('  edge table: %d horizontal edges, %d vertical, over %d pillars; %d segments cleared'
          % (horizontal, len(edges) - horizontal, len({p for p, _ in edges}), len(dark)))
    # symmetry is the check that the extraction was right, and it has to stay true
    opposite = {1: 3, 2: 4, 3: 1, 4: 2, 5: 6, 6: 5}
    for (p, d), (_, n) in edges.items():
        if n and (n, opposite[d]) not in edges:
            # The shaft is a chute, not a corridor: floor 3 pillar a takes the light and
            # drops it two floors. Every other asymmetry would be a mistake.
            print('  one-way edge (expected only for the shaft): %d --%d--> %d' % (p, d, n))
    bysegment, crossings = crosstable()
    print('  %d crossing tiles, on %d segments' % (len(crossings), len(bysegment)))
    print('  graph: ' + write(GRAPH, emit_graph(edges, dark, ups, pdark, header, bysegment, crossings)))
    rows = doortable()
    for door, colour, seg, tiles in rows:
        print('  door %-24s colour %d  %s' % (door, colour, seg or 'NO BEAM - shut for good'))
    print('  doors: ' + write(DOORS, emit_doors(rows)))
    order = parse_pillars(read(PILLARS))
    assert len(order) == 35, 'expected 35 pillars, parsed %d' % len(order)
    print('  pillars: ' + write(PILLARS, emit_pillars(order)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
