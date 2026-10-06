#!/usr/bin/env python3
"""Generate the Gravedigger's "what is in this coffin" window.

    python tools/gendiggercoffin.py
    python tools/ifids.py macro_digger_coffin

WHY A WINDOW AND NOT A MESSAGE. Every grave good in the event is called "Item" and examines as "It
seems bleached with age" - that is deliberate, it is what stops the puzzle being solved by reading.
So the contents have to be SEEN, which means models, which means an interface. The nine
macro_digger_interface_slot_* varbits in antimacro.varbit say a nine-slot grid was the intention;
this is that grid, as one type=inv component rather than nine model components, so the client draws
it with the same code that draws the backpack and the slots behave the way a player expects.

The frame is tools/genmenus.py's window(), which is the 377 smithing window's chrome - the same
frame the Construction menus use, so a new window does not look like a new game.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import genmenus as G  # noqa: E402

OUT = os.path.join(ROOT, 'scripts', 'macro events', 'interfaces', 'macro_digger_coffin.if')

# The frame runs x 12..500, y 20..320, with the title at y=30 and the subtitle at y=48. A 3x3 grid
# of 32px slots with the inventory's own 12,8 margin is 124 x 112, centred at x=256 and sat under
# the subtitle with room to breathe.
COLS = ROWS = 3
SLOT, MX, MY = 32, 12, 8
GRID_W = COLS * SLOT + (COLS - 1) * MX
GRID_H = ROWS * SLOT + (ROWS - 1) * MY
# The frame's inside runs y 60..320 under the subtitle; this centres the grid in what is left.
GRID_Y = 60 + (320 - 60 - GRID_H) // 2


def build():
    coms = G.window('Coffin')
    coms.append(('inv', dict(type='inv', x=256 - GRID_W // 2, y=GRID_Y,
                             width=COLS, height=ROWS, margin='%d,%d' % (MX, MY))))
    return coms


def main():
    coms = build()
    text = G.emit(coms)
    nl = '\r\n' if G._crlf(os.path.join(ROOT, 'scripts', 'interface_chat', 'interfaces', 'multiobj4.if')) else '\n'
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'wb').write(text.replace('\n', nl).encode('utf-8'))
    print('macro_digger_coffin.if  %d components, %dx%d grid at %d,%d'
          % (len(coms), COLS, ROWS, 256 - GRID_W // 2, GRID_Y))
    print('now run: python tools/ifids.py macro_digger_coffin')


if __name__ == '__main__':
    main()
