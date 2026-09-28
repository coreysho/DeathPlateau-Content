#!/usr/bin/env python3
"""Generate the XP rate chooser the RuneScape Guide opens on Tutorial Island.

WHY A GENERATOR. Not the three buttons - the panel: sixty-odd backing tiles and border pieces plus
pack/interface.pack and pack/interface.order having to agree on every component. The framing and
the repack are tools/genbarrowschest.py's, which took them from tools/genriftpicker.py.

WHAT IT DRAWS. Three columns, one per mode, each a box holding the mode's name, its multiplier in
large type, two lines saying what it costs you, the mode's drop-rate boost, and a Choose button.
The rates come out of scripts/gamemodes/configs/gamemode.constant so the picture and the varp cannot
disagree - the button that says 5x writes the number the constant calls 5x.

THE DROP-RATE LINE IS EMPTY HERE, on purpose. ~xprate_choose fills it with if_settext every time the
window opens, straight from ^droprate_boost_realism / _5x / _10x - so changing a boost in
gamemode.constant changes the chooser with no rerun of this, and the client (which wipes server-set
text when a main interface is replaced) is handed it afresh on every show. What this does check is
that the line FITS: the widest thing the script can write, at the widest boost the constants could
reasonably hold, against the box, with the client's own font metrics (tools/ifrender.py).

NO HIGHLIGHT, AND THE WHOLE BOX IS THE BUTTON. The first version made each box a
buttontype=select rect over script1op1=pushvar,xp_rate so the chosen mode would light itself up
client-side, with a separate "Choose" text button inside it. Both halves of that were wrong. The
select rect covers the text, and a select button takes clicks and shows its own option - so it
would have swallowed the click the script was waiting on and left p_pausebutton suspended forever.
And the highlight had nothing to highlight: ~xprate_choose returns early once a rate is set, so
the window is only ever open while the rate is UNSET. One rect per mode, buttontype=normal, with
overcolour for hover, which a rect honours.

    python3 tools/genxpratechooser.py
    python3 tools/ifrender.py ../scripts/gamemodes/interfaces/xprate_choose.if /tmp/x.png
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFACE = 'xprate_choose'
IF = os.path.join(ROOT, 'scripts/gamemodes/interfaces/%s.if' % IFACE)
CONST = os.path.join(ROOT, 'scripts/gamemodes/configs/gamemode.constant')
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 240
TILE_W, TILE_H = 88, 60
BOX_W, BOX_H = 140, 140
BOX_Y = 86
COL_OFF = '0x3E3529'
COL_ON = '0x6F6250'
# the drop-rate line: ~droprate_boost_line writes "Drop rates: +25%" or "Drop rates: Normal" into it
DROPS_FONT = 'p12_full'
DROPS_WIDEST = ('Drop rates: +999%', 'Drop rates: Normal')


def read(p):
    return open(p, newline='').read().replace('\r\n', '\n')


def const(name):
    m = re.search(r'(?m)^\^%s = (\d+)' % name, read(CONST))
    if not m:
        raise SystemExit('gamemode.constant does not define ^%s' % name)
    return int(m.group(1))


# name, the constant holding its rate, the two lines under the number, and the constant holding its
# drop-rate boost (which xprate.rs2 reads - here it is only checked to exist).
# WORDED AS A TRADE, not as a reward: the whole point of offering a slow mode is that it is worth
# choosing, and a menu that says "1x" against "10x" with no other information is not a choice.
# Realism says EXPERIENCE, not "every rate": its drop rates are the boosted ones, and the line under
# the blurb says so.
MODES = [
    ('Realism', 'xprate_realism',
     ['Experience exactly as', 'Old School has it.'], 'droprate_boost_realism'),
    ('5x', 'xprate_5x',
     ['Five times the', 'experience.'], 'droprate_boost_5x'),
    ('10x', 'xprate_10x',
     ['Ten times the', 'experience.'], 'droprate_boost_10x'),
]


def main():
    want = const('xprate_modes')
    if want != len(MODES):
        raise SystemExit('^xprate_modes is %d and there are %d modes here' % (want, len(MODES)))
    rates = [const(c) for _, c, _, _ in MODES]
    boosts = [const(d) for _, _, _, d in MODES]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ifrender
    fnt = ifrender.font(DROPS_FONT)
    for s in DROPS_WIDEST + tuple('Drop rates: +%d%%' % b for b in boosts):
        if fnt.width(s) > BOX_W - 8:
            raise SystemExit('"%s" is %dpx in %s and the box is %d' % (s, fnt.width(s), DROPS_FONT, BOX_W))
    if len(set(rates)) != len(rates):
        raise SystemExit('two modes share a rate: %s' % rates)
    if const('xprate_unset') in rates:
        raise SystemExit('a mode uses the "never chosen" value, so choosing it would not stick')

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
                width=min(TILE_W, PANEL_X + PANEL_W - x), height=TILE_H, graphic='tradebacking,0')
            n += 1
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

    com('title', type='text', x=PANEL_X, y=PANEL_Y + 10, width=PANEL_W, height=14, center='yes',
        font='b12_full', shadowed='yes', text='How fast do you want to level?',
        colour='0xFFFF00')
    com('hint', type='text', x=PANEL_X, y=PANEL_Y + 28, width=PANEL_W, height=14, center='yes',
        font='p12_full', shadowed='yes', text='You choose once, here, and it is permanent.',
        colour='0xFF981F')
    # A CLOSE BUTTON ON A MANDATORY CHOICE, on purpose. p_pausebutton means closing aborts the
    # asking script, which leaves the rate at 0 - read as 1x - and the guide asks again next time
    # you talk to him. A window with no way out would be a window that can strand a player if
    # anything else goes wrong, and the self-healing version costs nothing.
    com('close', type='text', x=PANEL_X + 412, y=PANEL_Y + 8, buttontype='close', width=68,
        height=11, font='p11_full', shadowed='yes', text='Close Window', colour='0xC00000',
        overcolour='0xFFFFFF')

    gap = (PANEL_W - len(MODES) * BOX_W) // (len(MODES) + 1)
    for i, (label, cname, lines, _) in enumerate(MODES):
        x = PANEL_X + gap + i * (BOX_W + gap)
        rate = const(cname)
        com('pick%d' % i, type='rect', x=x, y=BOX_Y, buttontype='normal', width=BOX_W,
            height=BOX_H, fill='yes', colour=COL_OFF, overcolour=COL_ON, option='Choose %s' % label)
        com('name%d' % i, type='text', x=x, y=BOX_Y + 14, width=BOX_W, height=14, center='yes',
            font='b12_full', shadowed='yes', text=label, colour='0xFFFFFF')
        # the rate line only where it ADDS something: on the 5x and 10x boxes the name already is
        # the multiplier, and a box reading "5x" over "5x" is a box that says one thing twice
        if label.lower() != '%dx' % rate:
            com('rate%d' % i, type='text', x=x, y=BOX_Y + 40, width=BOX_W, height=20,
                center='yes', font='b12_full', shadowed='yes', text='%dx' % rate,
                colour='0xFFFF00')
        # every blurb at the SAME y, whether its box carries a rate line or not, so the three
        # boxes read as one row rather than three of slightly different heights
        for j, line in enumerate(lines):
            com('blurb%d_%d' % (i, j), type='text', x=x, y=BOX_Y + 74 + j * 13, width=BOX_W,
                height=13, center='yes', font='p11_full', shadowed='yes', text=line,
                colour='0xC8C8C8')
        # the drop-rate boost, under the blurb in the hint's orange - no text here, the script
        # writes it from the constant on every open (see the docstring)
        com('drops%d' % i, type='text', x=x, y=BOX_Y + 110, width=BOX_W, height=14, center='yes',
            font=DROPS_FONT, shadowed='yes', text='', colour='0xFF981F')

    body = '\n'.join(out)
    os.makedirs(os.path.dirname(IF), exist_ok=True)
    open(IF, 'w', newline='').write(
        '// GENERATED by tools/genxpratechooser.py - do not hand edit.\n'
        '// Scripts: gamemodes/scripts/xprate.rs2. Rates come from gamemodes/configs/gamemode.constant.\n'
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

    print('%s: %d modes at rates %s, drop boosts %s, %d components, ids %d..%d'
          % (IFACE, len(MODES), rates, boosts, len(names), min(mine), max(mine)))


main()
