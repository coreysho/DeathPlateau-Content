#!/usr/bin/env python3
"""Generate the POH furniture Search window, and register it in the interface packs.

WHY A WINDOW. Twenty-one pieces of furniture carry op1=Search and fifteen of them have published
contents - the larder's groceries, the workshop's five tool stores, the kitchen's seven shelves -
and every one of them answered with a message and no items (DeathPlateau-Bugs#93). The cache's own
`desc` lines say what should be in them: loc_13699 reads "Hammer, chisel, saw and shears."

A chat menu cannot do it. ~p_choice holds five options and the teak shelves hold nine items, and
"one of each in a single click" is fine for a tool rack and wrong for a larder. The one precedent
in this repo is the tool leprechaun's window - a grid of fixed slots with inv_button withdrawals -
and the owner picked that shape, so this is a generic version of it.

WHAT IS DIFFERENT FROM THE LEPRECHAUN'S. His grid is a STORE: a perm inv, counts that mean how
many he is holding, and five withdraw amounts. This one is a PICKER. The contents are unlimited -
every wiki page says so - so the inv behind it is temp, filled on open from the piece's own list,
holds one of each for the icon, and taking an item adds to the player without removing from the
grid. One option, "Take", and the grid never changes while it is open.

WHY A GENERATOR. Not the twelve slots - the panel: sixty-odd backing tiles and border pieces, and
pack/interface.pack and pack/interface.order having to agree exactly on every one. The framing and
the repack are tools/genleprechaun.py's, which took them from tools/genbarrowschest.py, which took
them from tools/genriftpicker.py, where the rules for both are written down.

    python3 genpohsearch.py
    python3 ifrender.py ../scripts/skill_construction/interfaces/poh_search_window.if /tmp/s.png
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The interface, NOT the inv - two different names on purpose, the same reason genleprechaun.py
# gives: inv_transmit takes an inv and if_openmain takes an interface, and one debugname for both
# leaves every call site ambiguous to the reader.
IFACE = 'poh_search_window'
IF = os.path.join(ROOT, 'scripts/skill_construction/interfaces/%s.if' % IFACE)
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')
INV = os.path.join(ROOT, 'scripts/skill_construction/configs/poh_search.inv')
CONST = os.path.join(ROOT, 'scripts/skill_construction/configs/construction.constant')

# 240 is FOUR whole backing tiles. 190 was not, so the bottom row was drawn 10px tall and the
# frame sat on nothing - visible the moment ifrender.py drew it. The rest of this geometry is
# genleprechaun.py's unchanged, which is the point: its window is also twelve slots in two rows.
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 240
TILE_W, TILE_H = 88, 60
# Six across puts twelve in two rows, which is the leprechaun's geometry. Twelve is three more
# than the biggest list (teak shelves 2, nine items), so a family gaining an item needs no change
# here. ICON is an inventory icon and GAP is what margin means - the space BETWEEN icons - so the
# pitch is the sum of the two.
COLS = 6
ICON = 32
GAP = 40
STEP = ICON + GAP
GRID_Y = 72


def read(p):
    return open(p, newline='').read().replace('\r\n', '\n')


def inv_size():
    """The slot count, followed from poh_search.inv through to the constant it names, so the window
    and the inv behind it cannot disagree about how many squares there are."""
    body = read(INV).split('[poh_search_items]', 1)[1].split('\n[', 1)[0]
    size = re.search(r'(?m)^size=(.+)$', body).group(1).strip()
    if size.startswith('^'):
        m = re.search(r'(?m)^%s = (\d+)$' % re.escape(size), read(CONST))
        if not m:
            raise SystemExit('poh_search.inv says size=%s and construction.constant does not define it' % size)
        return int(m.group(1))
    return int(size)


def main():
    slots = inv_size()
    rows = (slots + COLS - 1) // COLS
    grid_w = COLS * STEP - GAP
    grid_x = PANEL_X + (PANEL_W - grid_w) // 2

    out = []

    def com(name, **kv):
        out.append('[%s]' % name)
        for k, v in kv.items():
            out.append('%s=%s' % (k.rstrip('_'), v))
        out.append('')

    n = 0
    for y in range(PANEL_Y, PANEL_Y + PANEL_H, TILE_H):
        for x in range(PANEL_X, PANEL_X + PANEL_W, TILE_W):
            com('frame%d' % n, type='graphic', x=x, y=y,
                width=min(TILE_W, PANEL_X + PANEL_W - x), height=min(TILE_H, PANEL_Y + PANEL_H - y),
                graphic='tradebacking,0')
            n += 1
    # the four 25x30 corners sit INSIDE the panel's corners, so the right-hand pair starts 25
    # short of its right edge. Every offset in this block is genleprechaun.py's, kept as the
    # relation it is so that changing PANEL_H does not silently unstitch the frame.
    for i, (x, y) in enumerate(((PANEL_X, PANEL_Y), (PANEL_X + PANEL_W - 25, PANEL_Y),
                                (PANEL_X, PANEL_Y + PANEL_H - 30),
                                (PANEL_X + PANEL_W - 25, PANEL_Y + PANEL_H - 30))):
        com('corner%d' % i, type='graphic', x=x, y=y, width=25, height=30,
            graphic='steelborder,%d' % i)
    for i, x in enumerate(range(PANEL_X + 25, PANEL_X + PANEL_W - 24, 36)):
        com('top%d' % i, type='graphic', x=x, y=PANEL_Y - 15, width=36, height=36,
            graphic='steelborder2,0')
        com('bottom%d' % i, type='graphic', x=x, y=PANEL_Y + PANEL_H - 21, width=36, height=36,
            graphic='miscgraphics,3')
    for i, y in enumerate(range(PANEL_Y + 29, PANEL_Y + PANEL_H - 30, 36)):
        com('left%d' % i, type='graphic', x=PANEL_X - 15, y=y, width=36, height=36,
            graphic='miscgraphics,2')
        com('right%d' % i, type='graphic', x=PANEL_X + PANEL_W - 21, y=y, width=36, height=36,
            graphic='steelborder2,1')

    # BOTH TEXTS ARE WRITTEN AT RUNTIME, which is the whole point of one window for fifteen pieces:
    # ~poh_search_open sets the title to the piece's own name and the subtitle to its line. The
    # text here is only what the interface editor and ifrender.py show.
    com('title', type='text', x=PANEL_X, y=PANEL_Y + 10, width=PANEL_W, height=14, center='yes',
        font='b12_full', shadowed='yes', text='Search', colour='0xFFFF00')
    com('subtitle', type='text', x=PANEL_X, y=PANEL_Y + 28, width=PANEL_W, height=14, center='yes',
        font='p12_full', shadowed='yes', text='Take what you need.', colour='0xFF981F')
    com('close', type='text', x=PANEL_X + 412, y=PANEL_Y + 8, buttontype='close', width=68,
        height=11, font='p11_full', shadowed='yes', text='Close Window', colour='0xC00000',
        overcolour='0xFFFFFF')
    # THE GRID. An inv component is transmitted once and the client draws the icons and the hover
    # text for nothing; its option comes back as [inv_button1] with last_slot already filled in.
    # ONE option, because there is one thing to do: the contents are unlimited, so there is no
    # amount to choose and nothing to put back.
    com('items', type='inv', x=grid_x, y=GRID_Y, width=COLS, height=rows,
        interactable='yes', margin='%d,%d' % (GAP, GAP), option1='Take')
    com('hint', type='text', x=PANEL_X, y=GRID_Y + rows * STEP - GAP + 36, width=PANEL_W,
        height=26, center='yes', font='p11_full', shadowed='yes',
        text='There is as much of each of these as you want.', colour='0xC8C8C8')

    body = '\n'.join(out)
    os.makedirs(os.path.dirname(IF), exist_ok=True)
    open(IF, 'w', newline='').write(
        '// GENERATED by tools/genpohsearch.py - do not hand edit.\n'
        '// Scripts: skill_construction/scripts/poh_search.rs2. The grid IS poh_search_items.\n'
        + body)
    names = re.findall(r'^\[([A-Za-z0-9_]+)\]$', body, re.M)

    pack = [l for l in read(PACK).split('\n') if l]
    order_raw = open(ORDER, encoding='utf-8', newline='').read()
    order_crlf = '\r\n' in order_raw
    ids_order = [l for l in order_raw.replace('\r\n', '\n').split('\n') if l.strip()]

    existing, keep, dropped = {}, [], set()
    for l in pack:
        i, nm = l.split('=', 1)
        if nm == IFACE or nm.startswith(IFACE + ':'):
            existing[nm] = i
            dropped.add(i)
            continue
        keep.append(l)
    ids_order = [l for l in ids_order if l not in dropped]
    used = {int(l.split('=', 1)[0]) for l in keep}
    nxt = max(used) + 1

    def take(nm):
        nonlocal nxt
        i = existing.get(nm)
        if i is None or int(i) in used:
            while nxt in used:
                nxt += 1
            i = str(nxt); nxt += 1
        used.add(int(i))
        keep.append('%s=%s' % (i, nm))
        ids_order.append(i)
        return int(i)

    mine = [take(IFACE)] + [take('%s:%s' % (IFACE, n)) for n in names]
    keep.sort(key=lambda l: int(l.split('=', 1)[0]))
    ids_order.sort(key=int)
    ids = [l.split('=', 1)[0] for l in keep]
    assert len(ids) == len(set(ids)), 'duplicate interface id'
    nm = [l.split('=', 1)[1] for l in keep]
    assert len(nm) == len(set(nm)), 'duplicate interface name'
    assert set(ids_order) == set(ids), 'interface.order and interface.pack disagree'
    open(PACK, 'w', encoding='utf-8', newline='').write('\n'.join(keep) + '\n')
    open(ORDER, 'w', encoding='utf-8', newline='').write(
        ('\r\n' if order_crlf else '\n').join(ids_order) + ('\r\n' if order_crlf else '\n'))
    print('%s: %d slots in %d rows, %d components, ids %d..%d'
          % (IFACE, slots, rows, len(names), min(mine), max(mine)))


main()
