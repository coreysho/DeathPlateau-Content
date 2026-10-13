#!/usr/bin/env python3
"""The Void Knights' reward window: writes the interface and the code that fills it.

WHY A WINDOW AND NOT THE CHAT BOX. Commendation points used to be spent through nested p_choice
menus - five items, then "show me the helmets", then a confirm - which is not what Old School does
and cannot show a price list, let alone an experience table whose numbers change with your level.
Old School's reward window is a list with a description and a confirm, and this is that.

IT IS THE SLAYER WINDOW'S SHAPE ON PURPOSE (tools/genslayerui.py). Both windows have the same
problem - a currency that is a varp rather than an obj, so ~openshop cannot be used - and solving
it twice in two different-looking windows would be solving it worse. Same frame from genmenus,
same row geometry, same Back/Confirm, same browns.

WHAT IS DIFFERENT, and it is the one thing: the Experience tab sells a quantity. Old School trades
points 1, 10 or 100 at a time and pays a bonus on the larger batches, so this window carries an
amount selector that the Slayer one has no need for. It is three buttons in a layer, shown on the
Experience tab and hidden on the Equipment tab, because if_sethide only works on layers.

    python3 tools/genvoidui.py [--check]
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genmenus as G

ROOT = G.ROOT
ORANGE, WHITE, YELLOW = '0xFF981F', '0xFFFFFF', '0xFFFF00'
ROW_OFF, ROW_HOVER, TAB_OFF = '0x4A3F31', '0x6F6250', '0x3E3529'

TABS = ['Experience', 'Equipment']
TAB_Y, TAB_H, TAB_X, TAB_W, TAB_GAP = 66, 14, 16, 92, 4

# Seven rows: seven skills on one tab and seven items on the other, so neither needs a page.
ROWS, ROW_Y, ROW_STEP, ROW_H = 7, 90, 15, 14
ROW_X, ROW_W, COST_W = 26, 460, 120

# The amount selector sits between the list and the description, where the eye already is after
# picking a row.
AMOUNTS = [('1', 1), ('10', 10), ('100', 100)]
AMT_Y, AMT_H, AMT_W, AMT_GAP = 200, 14, 60, 8
AMT_LABEL_W = 96

DESC_Y, DESC_STEP, DESC_LINES = 228, 14, 2
BUTTON_Y = 266


def components():
    coms = G.window('Void Knight Rewards')
    for i, name in enumerate(TABS):
        x = TAB_X + i * (TAB_W + TAB_GAP)
        coms.append(('tab%dfill' % i, dict(type='rect', x=x, y=TAB_Y, width=TAB_W, height=TAB_H,
                                           fill='yes', colour=TAB_OFF)))
        coms.append(('tab%d' % i, dict(type='text', x=x, y=TAB_Y, buttontype='normal',
                                       width=TAB_W, height=TAB_H, center='yes', font='b12_full',
                                       shadowed='yes', text=name, colour=ORANGE,
                                       overcolour=WHITE)))
    for i in range(ROWS):
        coms.append(('row%d' % i, dict(type='layer', x=ROW_X, y=ROW_Y + i * ROW_STEP,
                                       width=ROW_W, height=ROW_H, scroll=0)))
        # The rect is the button and the text sits on it: a component carries one option string,
        # and "Select" belongs to the row rather than to either label.
        coms.append(('r%dbox' % i, dict(layer='row%d' % i, type='rect', x=0, y=0,
                                        buttontype='normal', width=ROW_W, height=ROW_H,
                                        fill='yes', colour=ROW_OFF, overcolour=ROW_HOVER,
                                        option='Select')))
        coms.append(('r%dname' % i, dict(layer='row%d' % i, type='text', x=6, y=1,
                                         width=ROW_W - COST_W - 12, height=ROW_H - 2,
                                         font='p12_full', shadowed='yes', text='', colour=WHITE)))
        coms.append(('r%dcost' % i, dict(layer='row%d' % i, type='text', x=ROW_W - COST_W - 4, y=1,
                                         width=COST_W, height=ROW_H - 2, center='yes',
                                         font='p12_full', shadowed='yes', text='', colour=WHITE)))

    # The amount selector, in a layer of its own so the Equipment tab can hide the lot with one
    # if_sethide - which is the only thing if_sethide works on.
    coms.append(('amounts', dict(type='layer', x=ROW_X, y=AMT_Y, width=ROW_W, height=AMT_H,
                                 scroll=0)))
    coms.append(('amtlabel', dict(layer='amounts', type='text', x=6, y=1, width=AMT_LABEL_W,
                                  height=AMT_H - 2, font='p12_full', shadowed='yes',
                                  text='Points to trade:', colour=WHITE)))
    for i, (label, _n) in enumerate(AMOUNTS):
        x = AMT_LABEL_W + 12 + i * (AMT_W + AMT_GAP)
        coms.append(('amt%dfill' % i, dict(layer='amounts', type='rect', x=x, y=0,
                                           buttontype='normal', width=AMT_W, height=AMT_H,
                                           fill='yes', colour=ROW_OFF, overcolour=ROW_HOVER,
                                           option='Select')))
        coms.append(('amt%d' % i, dict(layer='amounts', type='text', x=x, y=1, width=AMT_W,
                                       height=AMT_H - 2, center='yes', font='p12_full',
                                       shadowed='yes', text=label, colour=WHITE)))

    for i in range(DESC_LINES):
        coms.append(('desc%d' % i, dict(type='text', x=ROW_X + 6, y=DESC_Y + i * DESC_STEP,
                                        width=ROW_W - 12, height=13, font='p12_full',
                                        shadowed='yes', text='', colour=YELLOW)))
    coms.append(('back', dict(type='text', x=ROW_X + 6, y=BUTTON_Y, buttontype='normal',
                              width=88, height=14, center='yes', font='b12_full', shadowed='yes',
                              text='Back', colour=ORANGE, overcolour=WHITE)))
    coms.append(('confirm', dict(type='text', x=ROW_X + ROW_W - 94, y=BUTTON_Y,
                                 buttontype='normal', width=88, height=14, center='yes',
                                 font='b12_full', shadowed='yes', text='Confirm',
                                 colour=ORANGE, overcolour=WHITE)))
    return coms


HEAD = '''// The Void Knights' reward window - what fills it and what its clicks do.
//
// GENERATED by tools/genvoidui.py. The rows and the interface are both its work; the rewards
// themselves are data in configs/pest_rewards.enum and every effect is in pest_rewards.rs2, which
// holds the one implementation of each. Edit the generator or the enums, not this file.
//
// THE SHAPE IS THE SLAYER WINDOW'S, which is Old School interface 426's: a tab strip, a list, a
// description and Back / Confirm. ~void_ui_draw repaints every row on every click, so it is
// deliberately cheap - seven rows of two if_settexts and a handful of enum reads. The engine
// spends ONE opcode budget on a whole window session, which is why the click loop is bounded by
// ^pest_ui_clicks.'''


def rs2():
    o = [HEAD, '']
    o.append('// One row: the name on the left, the price or the experience on the right, hidden')
    o.append('// when the tab has nothing to put in it. if_sethide only works on layers, which is')
    o.append('// why every row is one.')
    for i in range(ROWS):
        o.append('[proc,void_ui_row%d](int $tab, int $i, int $sel, int $amount)' % i)
        o.append('if ($i >= ~void_ui_count($tab)) {')
        o.append('    if_sethide(pest_rewards:row%d, true);' % i)
        o.append('    return;')
        o.append('}')
        o.append('if_sethide(pest_rewards:row%d, false);' % i)
        o.append('if_settext(pest_rewards:r%dname, "<~void_ui_tint($tab, $i)><~void_ui_name($tab, $i)>");' % i)
        o.append('if_settext(pest_rewards:r%dcost, "<~void_ui_tint($tab, $i)><~void_ui_cost_text($tab, $i, $amount)>");' % i)
        o.append('if_setcolour(pest_rewards:r%dbox, ~void_ui_row_fill($sel, $i));' % i)
        o.append('')
    o.append('// The whole window, repainted. $sel is -1 for nothing selected.')
    o.append('[proc,void_ui_draw](int $tab, int $sel, int $amount)')
    o.append('if_settext(pest_rewards:subtitle, "<~void_ui_points_text>");')
    for i, name in enumerate(TABS):
        o.append('if_settext(pest_rewards:tab%d, "<~void_ui_tabtint($tab, %d)>%s");' % (i, i, name))
        o.append('if_setcolour(pest_rewards:tab%dfill, ~void_ui_tab_fill($tab, %d));' % (i, i))
    for i in range(ROWS):
        o.append('~void_ui_row%d($tab, %d, $sel, $amount);' % (i, i))
    o.append('// The amount selector belongs to the Experience tab and nothing else.')
    o.append('if_sethide(pest_rewards:amounts, ~void_ui_amounts_hidden($tab));')
    for i, (_label, n) in enumerate(AMOUNTS):
        o.append('if_setcolour(pest_rewards:amt%dfill, ~void_ui_amount_fill($amount, %d));' % (i, n))
    for i in range(DESC_LINES):
        o.append('if_settext(pest_rewards:desc%d, "<~void_ui_desc($tab, $sel, $amount, %d)>");' % (i, i))
    o.append('')
    o.append('// Every button the window can answer with, added after the draw.')
    o.append('[proc,void_ui_buttons](int $tab)')
    for i in range(len(TABS)):
        o.append('if_addresumebutton(pest_rewards:tab%d);' % i)
    o.append('def_int $i = 0;')
    o.append('while ($i < ~void_ui_count($tab)) {')
    o.append('    ~void_ui_rowbutton($i);')
    o.append('    $i = calc($i + 1);')
    o.append('}')
    o.append('if ($tab = ^pest_tab_xp) {')
    for i in range(len(AMOUNTS)):
        o.append('    if_addresumebutton(pest_rewards:amt%dfill);' % i)
    o.append('}')
    o.append('if_addresumebutton(pest_rewards:back);')
    o.append('if_addresumebutton(pest_rewards:confirm);')
    o.append('')
    o.append('// A resume button per row, by index. switch_int rather than seven ifs so an unused')
    o.append('// row costs one comparison.')
    o.append('[proc,void_ui_rowbutton](int $i)')
    o.append('switch_int ($i) {')
    for i in range(ROWS):
        o.append('    case %d : if_addresumebutton(pest_rewards:r%dbox);' % (i, i))
    o.append('}')
    o.append('')
    o.append('// Which row was clicked, or -1. The window reads last_com once and asks this.')
    o.append('[proc,void_ui_clicked_row]()(int)')
    o.append('switch_component (last_com) {')
    for i in range(ROWS):
        o.append('    case pest_rewards:r%dbox : return(%d);' % (i, i))
    o.append('}')
    o.append('return(-1);')
    o.append('')
    o.append('// Which tab was clicked, or -1.')
    o.append('[proc,void_ui_clicked_tab]()(int)')
    o.append('switch_component (last_com) {')
    for i in range(len(TABS)):
        o.append('    case pest_rewards:tab%d : return(%d);' % (i, i))
    o.append('}')
    o.append('return(-1);')
    o.append('')
    o.append('// Which amount button was clicked, or -1. The value, not the index: the window')
    o.append('// carries the number of points and never the button that set it.')
    o.append('[proc,void_ui_clicked_amount]()(int)')
    o.append('switch_component (last_com) {')
    for i, (_label, n) in enumerate(AMOUNTS):
        o.append('    case pest_rewards:amt%dfill : return(%d);' % (i, n))
    o.append('}')
    o.append('return(-1);')
    return o


def main():
    check = '--check' in sys.argv
    coms = components()
    names = [n for n, _ in coms]
    if len(names) != len(set(names)):
        raise SystemExit('duplicate component name')

    if_path = os.path.join(ROOT, 'scripts/minigames/game_pest/interfaces/pest_rewards.if')
    rs_path = os.path.join(ROOT, 'scripts/minigames/game_pest/scripts/pest_rewards_ui.rs2')
    os.makedirs(os.path.dirname(if_path), exist_ok=True)

    text = G.emit(coms)
    if G._crlf(os.path.join(ROOT, 'scripts/interfaces/skill_guide.if')):
        text = text.replace('\r\n', '\n').replace('\n', '\r\n')
    src = rs2()
    nl = '\r\n' if G._crlf(os.path.join(ROOT, 'scripts/minigames/game_pest/scripts/pest_solo.rs2')) else '\n'
    body = nl.join(src).replace('\r\n', '\n').rstrip('\n')
    if nl == '\r\n':
        body = body.replace('\n', '\r\n')
    body = (body + nl).encode('utf-8')

    if check:
        same = (os.path.exists(if_path) and open(if_path, 'rb').read() == text.encode('utf-8')
                and os.path.exists(rs_path) and open(rs_path, 'rb').read() == body)
        print('--check: %s' % ('nothing would change' if same else 'WOULD CHANGE'))
        raise SystemExit(0 if same else 1)

    open(if_path, 'wb').write(text.encode('utf-8'))
    print('pest_rewards.if     %3d components' % len(coms))
    open(rs_path, 'wb').write(body)
    print('pest_rewards_ui.rs2 %3d lines' % len(src))
    G.repack({'pest_rewards': names}, [])


if __name__ == '__main__':
    main()
