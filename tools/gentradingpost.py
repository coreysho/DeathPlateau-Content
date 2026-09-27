#!/usr/bin/env python3
"""Write the Trading Post's four windows, and take their ids in interface.pack.

    python3 tools/gentradingpost.py            # write the .if files and take pack ids
    python3 tools/gentradingpost.py --check     # exit 1 if any of them would change

THE WINDOWS. Three main panels, one side panel, every one of them the same frame the shop and
the boss window use (tradebacking tiles across 12..500, a b12 title, "Close Window" top right):

  tradingpost          the lists: Browse, My listings, My offers, Collection box. One inv grid
                       whose right-click options the script rewrites per tab with if_setinvop.
  tradingpost_listing  one listing: the item, who sells it, the price, the offers on it. The
                       seller can pick an offer, see what is in it, and accept or decline.
  tradingpost_offer    building an offer: coins, plus up to twelve items from the inventory.
  tradingpost_side     the player's inventory beside all three - "List" to sell, or "Offer"
                       while an offer is being built.

WHY THREE MAIN PANELS AND NOT ONE WITH HIDDEN LAYERS. Opening a different main panel is what
fires [if_close] on the one before, and that is the one place the barter window can hand its
items back - on Back, on Close, on walking away and on logout alike. A hidden layer has no close.

The script that drives them is scripts/tradingpost/scripts/tradingpost.rs2, and it is not
generated: nothing in it repeats.
"""
import os, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(C, 'tools'))
from genbosskills import read, take, take_order  # noqa: E402

OUT = os.path.join(C, 'scripts', 'tradingpost', 'interfaces')
IFPACK = os.path.join(C, 'pack', 'interface.pack')
IFORDER = os.path.join(C, 'pack', 'interface.order')

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 300
TILE_W, TILE_H = 88, 60
ORANGE = '0xFF981F'
WHITE = '0xFFFFFF'
YELLOW = '0xFFFF00'
GREY = '0x808080'


SHOP = os.path.join(C, 'scripts', 'shop', 'interfaces', 'shop_template.if')


def shop_frame():
    """Every graphic in the shop window - its tradebacking tiles, the steel border round the whole
    viewport and the bar under the title - as (name, {key: value}) in file order. Borrowed whole so
    these windows sit exactly where every shop does, filling the view with nothing of the world
    showing round the edges. The first version drew only the backing, and looked adrift."""
    out, cur = [], None
    for line in read(SHOP).split('\n'):
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            cur = (line[1:-1], {})
            out.append(cur)
        elif '=' in line and cur is not None:
            k, v = line.split('=', 1)
            cur[1][k] = v
    return [(n, kv) for n, kv in out if kv.get('type') == 'graphic']


class Panel:
    def __init__(self, name, blurb):
        self.name = name
        self.names = []
        self.parent = None
        self.origin = (0, 0)
        self.out = ['// %s. GENERATED - do not hand-edit.' % blurb,
                    '//   python3 tools/gentradingpost.py', '']

    def com(self, nm, **kv):
        self.names.append(nm)
        self.out.append('[%s]' % nm)
        if self.parent and kv.get('type') != 'layer':
            self.out.append('layer=%s' % self.parent)
            kv['x'] = kv['x'] - self.origin[0]
            kv['y'] = kv['y'] - self.origin[1]
        for k, v in kv.items():
            self.out.append('%s=%s' % (k, v))
        self.out.append('')

    # HIDING TAKES A LAYER. The 377 client honours `hide` only on a layer - Client.drawInterface
    # skips a hidden layer's children, and draws a hidden text or inv regardless - so everything the
    # script shows and hides sits in a layer of its own, named <thing>_box, and the script hides the
    # box. The first version hid the buttons themselves; nothing hid, and they drew over each other.
    def box(self, nm, x, y, w, h):
        self.com(nm, type='layer', x=x, y=y, width=w, height=h)
        self.parent, self.origin = nm, (x, y)

    def unbox(self):
        self.parent, self.origin = None, (0, 0)

    def frame(self):
        for n, kv in shop_frame():
            self.com('frame_' + n.replace('com_', ''),
                     **{k: (int(v) if k in ('x', 'y', 'width', 'height') else v) for k, v in kv.items()})

    def title(self, text):
        # the shop's own title and close-button positions, in the bar its frame draws
        self.com('title', type='text', x=PANEL_X, y=29, width=PANEL_W, height=14,
                 font='b12_full', shadowed='yes', center='yes', colour=ORANGE, text=text)
        self.com('close', type='text', x=420, y=29, width=68, height=11, buttontype='close',
                 font='p11_full', shadowed='yes', text='Close Window', colour=GREY, overcolour=WHITE)

    def text(self, nm, x, y, w, text, colour=WHITE, font='p12_full', center=False, h=14):
        kv = dict(type='text', x=x, y=y, width=w, height=h, font=font, shadowed='yes')
        if center:
            kv['center'] = 'yes'
        kv.update(colour=colour, text=text)
        self.com(nm, **kv)

    # A clickable line of text: orange, white under the mouse, one option.
    def button(self, nm, x, y, w, text, option=None, center=False):
        kv = dict(type='text', x=x, y=y, width=w, height=14, buttontype='normal', font='p12_full',
                  shadowed='yes')
        if center:
            kv['center'] = 'yes'
        kv.update(colour=ORANGE, overcolour=WHITE, text=text, option=option or text)
        self.com(nm, **kv)

    # a button the script can hide: the button, in a layer of exactly its size
    def hbutton(self, nm, x, y, w, text, option=None, center=False):
        self.box(nm + '_box', x, y, w, 14)
        self.button(nm, x, y, w, text, option, center)
        self.unbox()

    def inv(self, nm, x, y, cols, rows, margin, options):
        kv = dict(type='inv', x=x, y=y, width=cols, height=rows, margin=margin)
        for i, o in enumerate(options):
            kv['option%d' % (i + 1)] = o
        self.com(nm, **kv)

    def body(self):
        return '\n'.join(self.out)


# Content starts under the shop frame's title bar, which ends at about y=52.
TOP = 58


def lists():
    p = Panel('tradingpost', 'THE TRADING POST - the lists')
    p.frame()
    p.title('Trading Post')
    # four tabs across the top; the script colours the open one white
    for i, (nm, label) in enumerate([('tab_browse', 'Browse'), ('tab_mine', 'My listings'),
                                     ('tab_offers', 'My offers'), ('tab_box', 'Collection box')]):
        p.button(nm, 44 + i * 108, TOP, 100, label, center=True)
    p.text('status', PANEL_X, TOP + 18, PANEL_W, '', colour=YELLOW, font='p11_full', center=True)
    # 8 x 4: an item is 32 wide and the margin 15, so 8*47-15 = 361 wide, centred
    p.inv('grid', 76, TOP + 36, 8, 4, '15,15', ['Inspect', 'Buy-now'])
    p.text('empty', PANEL_X, TOP + 100, PANEL_W, '', colour=GREY, center=True)
    # the bottom row; the script hides whichever do not apply to the open tab
    p.hbutton('search', 30, 276, 80, 'Search', 'Search by name')
    p.hbutton('showall', 112, 276, 80, 'Show all')
    p.hbutton('prev', 300, 276, 80, '< Previous', 'Previous page', center=True)
    p.hbutton('next', 390, 276, 80, 'Next >', 'Next page', center=True)
    p.hbutton('collectall', 30, 276, 120, 'Collect all')
    p.text('hint', PANEL_X, 294, PANEL_W, '', colour=ORANGE, font='p11_full', center=True)
    return p


OFFER_ROWS = 8


def listing():
    p = Panel('tradingpost_listing', 'THE TRADING POST - one listing')
    p.frame()
    p.title('')
    p.inv('item', 30, TOP + 4, 1, 1, '0,0', [])
    for i in range(5):
        # 244 wide, which is up to the button column at 320: a lot's price line carries what one
        # costs as well, and the widest that can really be is 244px (tools/tradingpost_battery.py).
        p.text('info%d' % i, 76, TOP + i * 14, 244, '', colour=WHITE if i else YELLOW)
    # what the viewer can do, right-hand column. They share rows because they never show together:
    # a seller sees only Take down, and a buyer sees Make an offer or Withdraw, never both.
    p.hbutton('buynow', 320, TOP, 170, 'Buy now')
    p.hbutton('cancel', 320, TOP, 170, 'Take down this listing')
    p.hbutton('makeoffer', 320, TOP + 16, 170, 'Make an offer')
    p.hbutton('withdraw', 320, TOP + 16, 170, 'Withdraw my offer')
    # the offers, public: anyone can see who has bid what, only the seller can open one
    p.text('offers_title', 24, TOP + 76, 280, 'Offers', colour=ORANGE, font='b12_full')
    for i in range(OFFER_ROWS):
        p.hbutton('row%d' % i, 24, TOP + 94 + i * 16, 284, '', 'Select')
    p.box('offers_none_box', 24, TOP + 94, 284, 14)
    p.text('offers_none', 24, TOP + 94, 284, 'No offers yet.', colour=GREY)
    p.unbox()
    # the chosen offer, seller only - one layer, shown and hidden as a piece
    p.box('sel_box', 316, TOP + 76, 180, 160)
    p.text('sel_title', 320, TOP + 76, 170, '', colour=ORANGE, font='b12_full')
    p.inv('offer_items', 320, TOP + 94, 4, 3, '10,8', [])
    p.button('accept', 320, TOP + 220, 80, 'Accept', 'Accept offer')
    p.button('decline', 410, TOP + 220, 80, 'Decline', 'Decline offer')
    p.unbox()
    p.button('back', 24, 296, 80, '< Back', 'Back')
    p.text('hint', 110, 296, 380, '', colour=ORANGE, font='p11_full', center=True)
    return p


def offer():
    p = Panel('tradingpost_offer', 'THE TRADING POST - making an offer')
    p.frame()
    p.title('')
    p.text('info', PANEL_X, TOP + 2, PANEL_W, '', colour=WHITE, center=True)
    p.text('coins', PANEL_X, TOP + 24, PANEL_W, '', colour=YELLOW, font='b12_full', center=True)
    p.button('setcoins', 196, TOP + 42, 120, 'Set coins', center=True)
    # 6 x 2: 6*47-15 = 267 wide, centred
    p.inv('barter', 122, TOP + 68, 6, 2, '15,15', ['Remove', 'Remove-5', 'Remove-All', 'Remove-X'])
    p.text('hint', PANEL_X, TOP + 160, PANEL_W, 'Click items in your inventory to add them to your offer.',
           colour=ORANGE, font='p11_full', center=True)
    p.button('submit', 176, TOP + 190, 160, 'Make this offer', center=True)
    p.button('back', 24, 296, 80, '< Back', 'Back')
    return p


def side():
    p = Panel('tradingpost_side', 'THE TRADING POST - the inventory beside it')
    # the same grid shop_template_side uses; the options are rewritten per window
    p.inv('inv', 16, 8, 4, 7, '10,4', ['List'])
    return p


def prune(names, check):
    """Drop the ids this generator took for components it no longer writes - the first version's
    frame tiles, above all - so interface.pack names nothing that is not in a .if file."""
    import re
    ours = re.compile(r'^\d+=(tradingpost(_listing|_offer|_side)?)(:\w+)?$')
    keep = set(names)
    lines = read(IFPACK).rstrip('\n').split('\n')
    gone = [l for l in lines if ours.match(l) and l.split('=', 1)[1] not in keep]
    if gone and not check:
        open(IFPACK, 'w', newline='').write('\n'.join(l for l in lines if l not in gone) + '\n')
        ids = {l.split('=', 1)[0] for l in gone}
        order = [l for l in read(IFORDER).rstrip('\n').split('\n') if l.strip() not in ids]
        open(IFORDER, 'w', newline='').write('\n'.join(order) + '\n')
    return gone


PANELS = [lists, listing, offer, side]


def main():
    check = '--check' in sys.argv
    panels = [f() for f in PANELS]
    want = {os.path.join(OUT, p.name + '.if'): p.body() for p in panels}
    names = []
    for p in panels:
        names += [p.name] + ['%s:%s' % (p.name, n) for n in p.names]

    if check:
        bad = [os.path.relpath(path, C) for path, body in want.items()
               if not os.path.exists(path) or read(path) != body]
        _, added = take(IFPACK, names, True)
        if prune(names, True):
            bad.append('interface.pack has ids for components no longer written')
        if added:
            bad.append('interface.pack is missing %d ids' % len(added))
        if bad:
            print('gentradingpost --check: ' + '; '.join(bad))
            return 1
        print('gentradingpost --check: all four windows and their ids are already what this writes')
        return 0

    os.makedirs(OUT, exist_ok=True)
    for path, body in want.items():
        open(path, 'w', newline='').write(body)
        print('wrote %s' % os.path.relpath(path, C))
    gone = prune(names, False)
    ids, added = take(IFPACK, names, False)
    take_order(IFORDER, [ids[n] for n in names], False)
    print('%d components across %d windows, %d new interface ids, %d dropped'
          % (len(names), len(panels), len(added), len(gone)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
