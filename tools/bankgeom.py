#!/usr/bin/env python3
"""The bank window's geometry, in one place.

WHY. Three generators draw into bank_main.if - genbankframe.py (the window itself), genbanktabs.py
(the tab row and the item grid) and genbankbar.py (the bottom button row) - and every one of them
has to agree about where the window's edges are. When those numbers lived in three files the tab
row and the button row were pinned to a frame neither of them could see, so the window could not
be resized without hand-checking all three. They come from here now.

HOW BIG THE WINDOW CAN BE. A main interface is drawn into a 512x334 root: PackShared gives EVERY
interface that size, and Client.drawInterfaceLayer sets the clip to it, so nothing outside is
drawn. That is true in both window modes - Layout.mainX/mainY centre a 512x334 main interface in
whatever room the side panels leave - so there is exactly one bank size to design, it is bounded by
512x334, and in fixed mode it sits inside the viewport and never covers the inventory panel.

The old window was 488x305 at (12, 20) and showed 8 columns x 5 rows = 40 slots, with 38px of dead
gutter to the left of the first column. This one takes the whole 512x334 bar a 3px margin and
tightens the cells to the inventory's own spacing, and shows 12 x 6 = 72.

HOW THE FRAME IS DRAWN. Not as a border sprite - the 377 chrome is a set of 36x36 tiles whose
visible content is a six-pixel bar down the middle (rows/cols 15..20 of the tile; the rest is
magenta). So a bar whose top edge is at Y is a component at Y - 15, which is why the frame
components have negative coordinates at the top and left. The four corners are 25x30 steelborder
tiles, and the interior is tiled with the single 88x60 tradebacking sprite.
"""

# The root every interface is packed at, and therefore the hard ceiling on the window.
ROOT_W, ROOT_H = 512, 334

# ---- the frame. (L, T) is the top-left pixel of the bars themselves, not of their tiles.
BAR = 6                      # how thick a frame bar draws
BAR_OFF = 15                 # where that bar sits inside its 36x36 tile
FRAME_L, FRAME_T = 3, 3
FRAME_R, FRAME_B = 503, 325  # the left column of the right bar / the top row of the bottom bar

# The usable inside of the frame.
IN_L, IN_T = FRAME_L + BAR, FRAME_T + BAR      # 9, 9
IN_R, IN_B = FRAME_R - 1, FRAME_B - 1          # 502, 324
IN_W, IN_H = IN_R - IN_L + 1, IN_B - IN_T + 1

# ---- the title bar: the caption, the close link, and the bar ruled under them
TITLE_Y = 12                 # the caption's text row
CLOSE_Y = TITLE_Y + 2        # "Close Window" sits two pixels lower, as it always has
CLOSE_W, CLOSE_H = 68, 11
SEP_Y = 28                   # the bar between the title and the tab row

# ---- the tab row. 32 tall, not 27: an obj icon is drawn at roughly its inventory size and a tall
# item (a vial, a staff) overflowed a 27px box. Model components are clipped at the BOTTOM and
# nowhere else, so the overspill above sat on the window chrome.
TAB_Y, TAB_H = 35, 32

# ---- the item grid. The scroll layer, and the inv drawn inside it.
CELL = 32                    # an obj icon
MARGIN = 6                   # the gap between cells, horizontally and vertically
PITCH = CELL + MARGIN        # what the client steps by: (marginX + 32)
COLS = 12
VISIBLE_ROWS = 6             # what fits between the tab row and the buttons - see the assertions

GRID_X, GRID_Y = 12, 71
GRID_W = 468
# The layer's height is the ROWS, exactly: a row that only half fits is drawn half, because the
# layer clips it, so a height that is not a whole number of rows shows a sliced row of items at
# the bottom of every bank. The trailing margin is not part of it - the last row has nothing
# under it to be separated from.
GRID_H = VISIBLE_ROWS * PITCH - MARGIN
SCROLLBAR = 16               # drawn just outside the layer's right edge by Client.drawInterface

# Centre the columns in the layer rather than leaving the old 38px gutter on the left. The first
# row starts flush with the top of the layer for the same reason the height is exact.
INV_X = (GRID_W - (COLS * PITCH - MARGIN)) // 2
INV_Y = 0

# The block of columns, in window coordinates. The tab row and the button row line up with it
# rather than with the window, which is off-centre from the columns by the width of the scrollbar.
# 377 aligned none of the three with each other (grid 75..436, tabs 37..460, buttons 38..470).
COL_X, COL_W = GRID_X + INV_X, COLS * PITCH - MARGIN

# ---- the bottom button row, centred under the columns
BTN = 36
BTN_SLOTS = 12
BTN_PITCH = BTN
BTN_Y = 295
BTN_X0 = COL_X + (COL_W - BTN_SLOTS * BTN_PITCH) // 2

# ---- the nine tabs, spread across the columns
TABS = 9
TAB_PITCH = COL_W // TABS
TAB_W = TAB_PITCH - 3
TAB_X0 = COL_X


def tiles(start, end, size):
    """Tile [start, end) with `size`-wide pieces, the last one pulled back to land flush on `end`.

    The 377 chrome does exactly this - the bank's backing row ended at x=412 rather than x=452 so
    that the last 88px tile finished on the frame - and the overlap is invisible because the tiles
    are a repeating texture.
    """
    span = end - start
    if span <= 0:
        return []
    n = -(-span // size)
    out = [start + i * size for i in range(n - 1)]
    out.append(end - size)
    return out


def slot_x(i):
    """x of button slot i on the bottom row."""
    return BTN_X0 + i * BTN_PITCH


def tab_x(k):
    """x of tab k in the tab row."""
    return TAB_X0 + k * TAB_PITCH


def check():
    """Everything above has to stay inside the root and out of everything else's way."""
    assert FRAME_L >= 0 and FRAME_T >= 0
    assert FRAME_R + BAR <= ROOT_W, 'the right frame bar falls off the root'
    assert FRAME_B + BAR <= ROOT_H, 'the bottom frame bar falls off the root'
    assert SEP_Y > TITLE_Y, 'the title rule is above the caption'
    assert TAB_Y >= SEP_Y + BAR, 'the tab row overlaps the title rule'
    assert GRID_Y >= TAB_Y + TAB_H, 'the grid overlaps the tab row'
    assert GRID_Y + GRID_H <= BTN_Y, f'{VISIBLE_ROWS} rows do not fit above the button row'
    assert (GRID_H + MARGIN) // PITCH == VISIBLE_ROWS, 'the layer is not a whole number of rows'
    assert BTN_Y + BTN <= FRAME_B + BAR + 1, 'the button row falls out of the window'
    assert GRID_X + GRID_W + SCROLLBAR <= IN_R, 'no room for the scrollbar'
    assert INV_X >= 0, f'{COLS} columns do not fit in {GRID_W}px'
    assert tab_x(TABS - 1) + TAB_W <= IN_R, 'the tab row runs past the frame'
    assert slot_x(BTN_SLOTS - 1) + BTN <= IN_R, 'the button row runs past the frame'
    assert BTN_X0 >= IN_L, 'the button row starts outside the frame'


check()

if __name__ == '__main__':
    print(f'window {FRAME_L},{FRAME_T} .. {FRAME_R + BAR},{FRAME_B + BAR} '
          f'({FRAME_R + BAR - FRAME_L}x{FRAME_B + BAR - FRAME_T}) in {ROOT_W}x{ROOT_H}')
    print(f'grid {COLS} cols x {VISIBLE_ROWS} visible rows = {COLS * VISIBLE_ROWS} slots on screen, '
          f'cell pitch {PITCH}')
    print(f'tabs {TABS} x {TAB_W} at pitch {TAB_PITCH}, x {tab_x(0)}..{tab_x(TABS - 1) + TAB_W}')
    print(f'buttons {BTN_SLOTS} x {BTN} at y {BTN_Y}, x {slot_x(0)}..{slot_x(BTN_SLOTS - 1) + BTN}')
