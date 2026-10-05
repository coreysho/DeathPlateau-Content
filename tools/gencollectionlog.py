#!/usr/bin/env python3
"""The collection log: write every generated file from tools/collectionlogspec.json.

    python3 tools/gencollectionlog.py            # write the files and take pack ids
    python3 tools/gencollectionlog.py --check     # exit 1 if anything would change

WHAT IS DATA AND WHAT IS GENERATED. The pages themselves - which tabs, which entries, which items,
which counters, which rewards - are dbrows, and the script that draws the window reads them with
db_find / db_getfield, so the rs2 has no item list in it anywhere. What cannot be data is written
here from the same spec:

  * collection_log.dbrow          the tabs, entries and rewards, as rows of the tables in
                                  configs/collection_log.dbtable
  * collection_log_items.enum     every DISTINCT item once, for the overall X/Y (an item on two
                                  pages counts once, as in Old School)
  * collection_log_counters.varp  one perm varp per counter the log keeps itself
  * collection_log.constant       sizes the window and the code have to agree on
  * collection_log.if             the window
  * collection_log_ui.rs2         the switches: this engine cannot address a component or a varp
                                  by number at runtime, so "row 7" and "counter 101" are generated
                                  switch_int cases, the way boss_kills.rs2's are
  * pack/varp.pack, inv.pack, interface.pack, interface.order - ids for all of the above

HOW TO CHANGE IT - edit tools/collectionlogspec.json, then run this, then build:

  * an item on a page: add its obj name to the entry's "items". If nothing already logs it (the
    call sites are listed at the top of collection_log.rs2), put ~collection_log_add(<obj>, <count>)
    beside the obj_add / inv_add that hands it out. Nobody's save changes: the log is keyed by obj.
  * a page: a new object in a tab's "entries" - key, name, counters, items. Its place in the list is
    its place in the file.
  * a tab: a new object in "tabs". The strip divides its width between however many there are.
  * a counter: boss:<key> reads a kill count that already exists; anything else is declared under
    "own_counters", gets its own perm varp here, and is bumped with
    ~collection_log_counter_add(^collection_log_counter_<key>, 1) where the thing it counts happens.
  * a reward: a new object in "rewards" with an unused bit (0-31). ~collection_log_rewards pays it
    the next time an item is logged or the log is opened, including to players already past it.
    Never reuse or renumber a bit: it is what records "already paid" in the save.

A list that outgrows the window scrolls on its own: the entry list past fifteen rows, the grid past
five rows of eight. ^collection_log_capacity (the spec's "capacity") may be raised, never lowered.

THE WINDOW'S SHAPE is Old School's (interface 621): a tab strip, the entries of the open tab in a
list on the left, and on the right the entry's name, "Obtained: X/Y", its kill count and its items,
faded where they have not been obtained. The frame is 377's own smithing window (genmenus.window),
the same one the Slayer Rewards and Construction windows use - the OSRS one is drawn by client
scripts this client does not run. The faded icons are free: an inv slot holding an obj with a
count of zero is what the bank's placeholders are, and the client already draws that faded with
no number under it (javaclient Client.java, "Bank placeholders").
"""
import json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import genmenus as G
import ifids

C = os.path.dirname(HERE)
SPEC = os.path.join(C, 'tools', 'collectionlogspec.json')
BOSSSPEC = os.path.join(C, 'tools', 'bosskillspec.json')
DIR = os.path.join(C, 'scripts', 'collection_log')
OUT_DBROW = os.path.join(DIR, 'configs', 'collection_log.dbrow')
OUT_ENUM = os.path.join(DIR, 'configs', 'collection_log_items.enum')
OUT_VARP = os.path.join(DIR, 'configs', 'collection_log_counters.varp')
OUT_CONST = os.path.join(DIR, 'configs', 'collection_log.constant')
OUT_IF = os.path.join(DIR, 'interfaces', 'collection_log.if')
OUT_RS2 = os.path.join(DIR, 'scripts', 'collection_log_ui.rs2')
HANDVARP = os.path.join(DIR, 'configs', 'collection_log.varp')
HANDINV = os.path.join(DIR, 'configs', 'collection_log.inv')
QUESTLIST = os.path.join(C, 'scripts', 'interfaces', 'questlist.if')
VARPPACK = os.path.join(C, 'pack', 'varp.pack')
INVPACK = os.path.join(C, 'pack', 'inv.pack')
IFACE = 'collection_log'

# Own counters start here so they can never collide with a boss slot (boss_kills.constant).
OWN_BASE = 100

# ---------------------------------------------------------------- geometry
# The 377 smithing frame spans 12..500 x 20..320 with its border inside that; everything below
# sits on the tradebacking between y=48 and y=298.
# The tab strip shares 472px between however many tabs the spec has: four are 115px each.
TAB_Y, TAB_H, TAB_X, TAB_SPAN, TAB_GAP = 50, 16, 20, 472, 4
LIST_X, LIST_Y, LIST_W, LIST_H, ROW_H = 20, 72, 150, 226, 15
PANEL_X = 192
NAME_Y, LINE1_Y, LINE2_Y = 74, 90, 104
# The counters share their lines with "Obtained": counter 0 on its line and counter 2 on the next are
# RIGHT-aligned across the whole page (the script moves them by the width their text leaves), and
# counter 1 sits on the left of the second line. Split into two fixed columns, a boss's name and
# kill count ("Commander Zilyana kills: 1,234") ran past the window's edge.
PAGE_W = 294
RIGHT_ALIGNED = (0, 2)
RULE_Y = 119
COLS, MARGIN_X, MARGIN_Y = 8, 4, 2
PITCH_Y = 32 + MARGIN_Y
# THE SCROLLBAR IS DRAWN OUTSIDE THE LAYER IT SCROLLS. Client.drawInterface puts it at x + width and
# makes it SCROLLBAR_W wide, so a grid sized to fill the panel hangs its bar over the panel's border.
# That is what it did: the panel used to be derived from the grid (pagebox ended at GRID_X + GRID_W +
# 4) which left the bar twelve pixels out on the window's steel edge however the numbers were set.
# So the PANEL is the fixed thing now - it is the window that cannot grow - and the grid is measured
# back from its inner edge, leaving the bar exactly inside it.
SCROLLBAR_W = 16
PANEL_R = 490                                       # the page panel's right edge, at the window's
GRID_Y, GRID_H = 124, 172
GRID_W = COLS * (32 + MARGIN_X) - MARGIN_X          # eight whole cells and no more: 284
GRID_X = PANEL_R - SCROLLBAR_W - GRID_W             # 190
COUNTERS = 3        # two lines: "Obtained" and counter 0, then counters 1 and 2

ORANGE, WHITE = '0xFF981F', '0xFFFFFF'
# The same three browns as the Slayer Rewards window, so the two read as one family.
ROW_OFF, ROW_HOVER, ROW_ON = '0x4A3F31', '0x6F6250', '0x8C7F63'
TAB_OFF, TAB_ON = '0x3E3529', '0x6F6250'
LINE = '0x5A4F3D'


def read(p):
    return open(p, newline='', encoding='utf-8').read()


def crlf(path):
    return os.path.exists(path) and G._crlf(path)


def nl_of(path, fallback):
    return '\r\n' if crlf(path if os.path.exists(path) else fallback) else '\n'


def to_nl(text, nl):
    text = text.replace('\r\n', '\n')
    return text.replace('\n', nl) if nl == '\r\n' else text


# ---------------------------------------------------------------- spec
def load():
    spec = json.load(open(SPEC, encoding='utf-8'))
    bosses = json.load(open(BOSSSPEC, encoding='utf-8'))['bosses']
    boss_index = {b['key']: i for i, b in enumerate(bosses)}
    own = {c['key']: OWN_BASE + i for i, c in enumerate(spec['own_counters'])}

    objs = set()
    for base, _, files in os.walk(os.path.join(C, 'scripts')):
        for f in files:
            if f.endswith('.obj'):
                objs.update(re.findall(r'^\[([^\]]+)\]', read(os.path.join(base, f)), re.M))

    entries, keys, distinct, errors = [], set(), [], []
    for t, tab in enumerate(spec['tabs']):
        for e in tab['entries']:
            if e['key'] in keys:
                errors.append('entry %s is listed twice' % e['key'])
            keys.add(e['key'])
            if not e['items']:
                errors.append('%s has no items' % e['key'])
            if len(e['items']) != len(set(e['items'])):
                errors.append('%s lists an item twice' % e['key'])
            for o in e['items']:
                if o not in objs:
                    errors.append('%s: no obj config defines %s' % (e['key'], o))
                if o.startswith('cert_'):
                    errors.append('%s: %s is a cert - list the item, the log stores the uncert' % (e['key'], o))
                if o not in distinct:
                    distinct.append(o)
            if len(e['counters']) > COUNTERS:
                errors.append('%s has %d counters; the window shows %d' % (e['key'], len(e['counters']), COUNTERS))
            ids = []
            for label, ref in e['counters']:
                if ref.startswith('boss:'):
                    if ref[5:] not in boss_index:
                        errors.append('%s: %s is not in bosskillspec.json' % (e['key'], ref))
                        continue
                    ids.append((label, boss_index[ref[5:]]))
                elif ref in own:
                    ids.append((label, own[ref]))
                else:
                    errors.append('%s: counter %s is neither boss:<key> nor an own counter' % (e['key'], ref))
            entries.append(dict(e, tab=t, counter_ids=ids))
    if len(distinct) > spec['capacity']:
        errors.append('%d distinct items but capacity is %d' % (len(distinct), spec['capacity']))
    bits = [r['bit'] for r in spec['rewards']]
    if len(bits) != len(set(bits)) or any(b < 0 or b > 31 for b in bits):
        errors.append('reward bits must be unique and 0..31 (one varp); add a second varp to go past 32')
    for r in spec['rewards']:
        if r['entry'] is not None and r['entry'] not in keys:
            errors.append('reward %s: no entry %s' % (r['key'], r['entry']))
        if r['reward'] is not None and r['reward'][0] not in objs:
            errors.append('reward %s: no obj %s' % (r['key'], r['reward'][0]))
    if errors:
        raise SystemExit('gencollectionlog: ' + '\n  '.join([''] + errors))
    return spec, entries, distinct


def grid_rows(entries):
    return max(math.ceil(len(e['items']) / COLS) for e in entries)


def list_rows(spec):
    return max(len(t['entries']) for t in spec['tabs'])


# ---------------------------------------------------------------- configs
HEAD = ('// GENERATED by tools/gencollectionlog.py from tools/collectionlogspec.json - do not hand-edit.\n'
        '//   python3 tools/gencollectionlog.py\n')


def build_dbrow(spec, entries):
    L = [HEAD + '//\n'
         '// THE PAGES OF THE COLLECTION LOG. The window reads these and nothing else: a tab row names\n'
         '// the tab and lists its entries in display order, an entry row lists its items in display\n'
         '// order and the counters it shows. The tables are in collection_log.dbtable, which says what\n'
         '// every column is for.\n']
    for t, tab in enumerate(spec['tabs']):
        L.append('[collection_log_tab_%d]' % t)
        L.append('table=collection_log_tab')
        L.append('data=tab,%d' % t)
        L.append('data=name,%s' % tab['name'])
        for e in tab['entries']:
            L.append('data=entries,collection_log_%s' % e['key'])
        # The tab's DISTINCT items, for the quest tab's per-tab progress bars: an item on two of the
        # tab's pages counts once there, as it does in the overall total.
        seen = []
        for e in tab['entries']:
            seen += [o for o in e['items'] if o not in seen]
        for o in seen:
            L.append('data=items,%s' % o)
        L.append('')
    for e in entries:
        L.append('// %s: %d items' % (e['name'], len(e['items'])))
        L.append('[collection_log_%s]' % e['key'])
        L.append('table=collection_log_entry')
        L.append('data=name,"%s"' % e['name'])
        for o in e['items']:
            L.append('data=items,%s' % o)
        for label, cid in e['counter_ids']:
            L.append('data=counters,"%s",%d' % (label, cid))
        L.append('')
    L.append('// REWARDS. See collection_log.dbtable for the columns and collection_log.rs2')
    L.append('// (~collection_log_rewards) for how they are paid. Each needs its OWN bit, forever.')
    for r in spec['rewards']:
        L.append('[collection_log_reward_%s]' % r['key'])
        L.append('table=collection_log_reward')
        L.append('data=bit,%d' % r['bit'])
        if r['entry'] is not None:
            L.append('data=entry,collection_log_%s' % r['entry'])
        L.append('data=threshold,%d' % r['threshold'])
        if r['reward'] is not None:
            L.append('data=reward,%s,%d' % (r['reward'][0], r['reward'][1]))
        if r.get('message'):
            L.append('data=message,"%s"' % r['message'])
        L.append('')
    return '\n'.join(L).rstrip('\n') + '\n'


def build_enum(distinct):
    L = [HEAD + '//\n'
         '// EVERY ITEM THE LOG LISTS, ONCE. The overall "Collection Log - X/Y" counts these: an item on\n'
         '// two pages is one item, as in Old School. The pages themselves are dbrows; this exists only\n'
         '// because "the distinct union of a list column over every row" is not a query dbtables have.\n',
         '[collection_log_items]', 'inputtype=int', 'outputtype=namedobj', 'default=null']
    for i, o in enumerate(distinct):
        L.append('val=%d,%s' % (i, o))
    L += ['',
          '// AND BACK AGAIN: obj -> its index above, or -1 for an obj the log does not list. This is',
          '// the "is it in the log at all" test ~collection_log_add makes on every call, and the way it',
          '// turns the plain obj a drop or a casket hands it into the namedobj inv_add insists on.',
          '[collection_log_item_index]', 'inputtype=obj', 'outputtype=int', 'default=-1']
    for i, o in enumerate(distinct):
        L.append('val=%s,%d' % (o, i))
    return '\n'.join(L) + '\n'


def build_varp(spec):
    L = [HEAD + '//\n'
         '// THE COUNTERS THE LOG KEEPS ITSELF, one full perm varp each - a count has no ceiling a bit\n'
         '// range could hold. The boss kill counts are not here; they are boss_kills.varp\'s and the log\n'
         '// only reads them.\n'
         '//\n'
         '// protect=no because the Barrows chest and the caskets are player context but a counter must\n'
         '// be writable from wherever the thing it counts happens, and boss_kills.varp explains what\n'
         '// protect=yes costs in an npc-context death.\n']
    for i, c in enumerate(spec['own_counters']):
        L.append('// counter id %d' % (OWN_BASE + i))
        L.append('[collection_log_count_%s]' % c['key'])
        L.append('scope=perm')
        L.append('protect=no')
        L.append('')
    return '\n'.join(L).rstrip('\n') + '\n'


def build_const(spec, entries, distinct):
    L = [HEAD + '//\n// Sizes the window, the invs and the code have to agree on.']
    L.append('^collection_log_capacity = %d' % spec['capacity'])
    L.append('^collection_log_tabs = %d' % len(spec['tabs']))
    L.append('^collection_log_rows = %d' % list_rows(spec))
    L.append('^collection_log_view_size = %d' % (COLS * grid_rows(entries)))
    L.append('^collection_log_counters = %d' % COUNTERS)
    L.append('^collection_log_own_base = %d' % OWN_BASE)
    for i, c in enumerate(spec['own_counters']):
        L.append('^collection_log_counter_%s = %d' % (c['key'], OWN_BASE + i))
    L.append('// The fills the script paints: a row at rest and the open one, a tab at rest and the open one.')
    L.append('^collection_log_row_off = %s' % ROW_OFF)
    L.append('^collection_log_row_on = %s' % ROW_ON)
    L.append('^collection_log_tab_off = %s' % TAB_OFF)
    L.append('^collection_log_tab_on = %s' % TAB_ON)
    return '\n'.join(L) + '\n'


# ---------------------------------------------------------------- interface
def components(spec, entries):
    coms = [c for c in G.window('Collection Log') if c[0] != 'subtitle']
    for i, tab in enumerate(spec['tabs']):
        TAB_W = (TAB_SPAN - (len(spec['tabs']) - 1) * TAB_GAP) // len(spec['tabs'])
        x = TAB_X + i * (TAB_W + TAB_GAP)
        coms.append(('tab%dfill' % i, dict(type='rect', x=x, y=TAB_Y, width=TAB_W, height=TAB_H,
                                           fill='yes', colour=TAB_OFF)))
        coms.append(('tab%d' % i, dict(type='text', x=x, y=TAB_Y + 1, buttontype='normal', width=TAB_W,
                                       height=TAB_H - 2, center='yes', font='b12_full', shadowed='yes',
                                       text=tab['name'], colour=ORANGE, overcolour=WHITE,
                                       option='View')))
    # Two ruled boxes, the list and the page, the way Old School's window divides.
    coms.append(('listbox', dict(type='rect', x=LIST_X - 2, y=LIST_Y - 2, width=LIST_W + 4,
                                 height=LIST_H + 4, colour=LINE)))
    coms.append(('pagebox', dict(type='rect', x=PANEL_X - 4, y=LIST_Y - 2, width=PANEL_R - PANEL_X + 4,
                                 height=LIST_H + 4, colour=LINE)))
    rows = list_rows(spec)
    scroll = rows * ROW_H if rows * ROW_H > LIST_H else 0
    coms.append(('list', dict(type='layer', x=LIST_X, y=LIST_Y, width=LIST_W, height=LIST_H, scroll=scroll)))
    for i in range(rows):
        coms.append(('row%d' % i, dict(layer='list', type='layer', x=0, y=i * ROW_H, width=LIST_W,
                                       height=ROW_H, hide='yes')))
        # The rect is the button and covers the whole row; its FILL is how the open entry shows,
        # because if_sethide only works on layers (genmenus.py, note 1).
        coms.append(('r%dbox' % i, dict(layer='row%d' % i, type='rect', x=0, y=0, buttontype='normal',
                                        width=LIST_W, height=ROW_H - 1, fill='yes', colour=ROW_OFF,
                                        overcolour=ROW_HOVER, option='View')))
        coms.append(('r%dname' % i, dict(layer='row%d' % i, type='text', x=4, y=1, width=LIST_W - 8,
                                         height=ROW_H - 2, font='p12_full', shadowed='yes', text='',
                                         colour=ORANGE)))
    coms.append(('name', dict(type='text', x=PANEL_X, y=NAME_Y, width=GRID_W, height=14,
                              font='b12_full', shadowed='yes', text='', colour=ORANGE)))
    coms.append(('obtained', dict(type='text', x=PANEL_X, y=LINE1_Y, width=PAGE_W // 2,
                                  height=13, font='p12_full', shadowed='yes', text='', colour=ORANGE)))
    lines = [LINE1_Y, LINE2_Y, LINE2_Y]
    for i in range(COUNTERS):
        x, y = PANEL_X, lines[i]
        coms.append(('counter%d' % i, dict(type='text', x=x, y=y, width=PAGE_W, height=13,
                                           font='p12_full', shadowed='yes', text='', colour=ORANGE)))
    coms.append(('rule', dict(type='rect', x=PANEL_X - 2, y=RULE_Y, width=PANEL_R - PANEL_X,
                              height=1, fill='yes', colour=LINE)))
    grows = grid_rows(entries)
    gscroll = grows * PITCH_Y if grows * PITCH_Y - MARGIN_Y > GRID_H else 0
    coms.append(('grid', dict(type='layer', x=GRID_X, y=GRID_Y, width=GRID_W, height=GRID_H, scroll=gscroll)))
    # "Check" is what puts the item's name on the menu - 377 has no hover tooltip for an inv slot -
    # and its handler says how many have been obtained. NOT interactable: that flag is what makes the
    # client add an item's own backpack options (Wield, Eat, Drop...) to its menu, so a logged dragon
    # axe offered "Wield". The menu is the grid's own Check, then Examine and Cancel, as Old School's.
    coms.append(('items', dict(layer='grid', type='inv', x=0, y=0, width=COLS, height=grows,
                               interactable='no', margin='%d,%d' % (MARGIN_X, MARGIN_Y), option1='Check')))
    return coms


# ---------------------------------------------------------------- rs2
def build_rs2(spec, entries):
    rows = list_rows(spec)
    tabs = len(spec['tabs'])
    o = [HEAD.rstrip('\n'),
         '//',
         '// THE SWITCHES. This engine cannot address a component or a varp by number at runtime, so',
         '// everything the window does "to row $i" or "to counter $id" is a switch_int written out here.',
         '// The logic - what goes in a row, what counts as obtained - is all in collection_log.rs2;',
         '// nothing in this file knows what any page contains.',
         '']
    o.append('// One row of the entry list: its name, and the fill that marks it open. A row past the end of')
    o.append('// the tab is hidden, which only works because every row is its own layer.')
    o.append('[proc,collection_log_row](int $i, boolean $hide, string $text, int $fill)')
    o.append('switch_int ($i) {')
    for i in range(rows):
        o.append('    case %d :' % i)
        o.append('        if_sethide(collection_log:row%d, $hide);' % i)
        o.append('        if_settext(collection_log:r%dname, $text);' % i)
        o.append('        if_setcolour(collection_log:r%dbox, $fill);' % i)
    o.append('}')
    o.append('')
    o.append('// One tab: its fill and its label, bright for the open one.')
    o.append('[proc,collection_log_tab_paint](int $i, int $fill, string $text)')
    o.append('switch_int ($i) {')
    for i in range(tabs):
        o.append('    case %d :' % i)
        o.append('        if_setcolour(collection_log:tab%dfill, $fill);' % i)
        o.append('        if_settext(collection_log:tab%d, $text);' % i)
    o.append('}')
    o.append('')
    o.append('// One counter line of the open entry. Blank text is how an unused one disappears. Counters')
    o.append('// %s are right-aligned across the page: moved right by the width their text leaves.'
             % ' and '.join(str(i) for i in RIGHT_ALIGNED))
    o.append('[proc,collection_log_counter_text](int $i, string $text)')
    o.append('switch_int ($i) {')
    for i in range(COUNTERS):
        if i in RIGHT_ALIGNED:
            o.append('    case %d :' % i)
            o.append('        if_settext(collection_log:counter%d, $text);' % i)
            o.append('        if_setposition(collection_log:counter%d, max(0, sub(%d, stringwidth($text, p12_full))), 0);'
                     % (i, PAGE_W))
        else:
            o.append('    case %d : if_settext(collection_log:counter%d, $text);' % (i, i))
    o.append('}')
    o.append('')
    o.append('// READ A COUNTER BY ID. Below ^collection_log_own_base it is a boss kill count, which')
    o.append('// ~boss_kill_get already switches on; above it, one of the log\'s own varps.')
    o.append('[proc,collection_log_counter_get](int $id)(int)')
    o.append('if ($id < ^collection_log_own_base) {')
    o.append('    return(~boss_kill_get($id));')
    o.append('}')
    o.append('switch_int ($id) {')
    for c in spec['own_counters']:
        o.append('    case ^collection_log_counter_%s : return(%%collection_log_count_%s);' % (c['key'], c['key']))
    o.append('}')
    o.append('return(0);')
    o.append('')
    o.append('// ADD TO ONE OF THE LOG\'S OWN COUNTERS. The boss kill counts are ~boss_kill_record\'s to keep,')
    o.append('// so an id below the base does nothing here rather than counting a kill twice.')
    o.append('[proc,collection_log_counter_add](int $id, int $n)')
    o.append('switch_int ($id) {')
    for c in spec['own_counters']:
        o.append('    case ^collection_log_counter_%s : %%collection_log_count_%s = add(%%collection_log_count_%s, $n);'
                 % (c['key'], c['key'], c['key']))
    o.append('}')
    o.append('')
    o.append('// The clicks.')
    for i in range(tabs):
        o.append('[if_button,collection_log:tab%d] ~collection_log_select_tab(%d);' % (i, i))
    for i in range(rows):
        o.append('[if_button,collection_log:r%dbox] ~collection_log_select_entry(%d);' % (i, i))
    return '\n'.join(o) + '\n'


# ---------------------------------------------------------------- quest list row
QL_ROW = 'collection_log'
MARK = '// APPENDED by tools/gencollectionlog.py'


def patch_questlist(text):
    """Take this generator's old "Collection log" row back OUT of the quest list.

    The row sat under "Boss kill counts" until the quest tab got pages of its own
    (tools/genquesttab.py): the log opens from the Collection Log and Character Summary pages now, and
    the quest list is quests only. The removal stays so that a checkout still carrying the row loses
    it on the next run.
    """
    nl = '\r\n' if '\r\n' in text else '\n'
    t = text.replace('\r\n', '\n')
    i = t.find(MARK)
    if i >= 0:
        # From the marker to the blank line that ends the block (a block has none inside it).
        k = t.find('\n\n', t.find('\n[%s]\n' % QL_ROW, i) + 1)
        t = t[:i].rstrip('\n') + ('\n\n' + t[k:].lstrip('\n') if k >= 0 else '\n')
    return t.replace('\n', nl)


# ---------------------------------------------------------------- pack ids
def take(path, names, check):
    """Give every name an id in a tracked pack file, keeping the ones it already has."""
    txt = read(path)
    nl = '\r\n' if '\r\n' in txt else '\n'
    have = {n: int(i) for i, n in re.findall(r'^(\d+)=(\S+?)\r?$', txt, re.M)}
    used = set(have.values())
    nxt = max(used) + 1 if used else 0
    added = []
    for n in names:
        if n in have:
            continue
        while nxt in used:
            nxt += 1
        have[n] = nxt
        used.add(nxt)
        added.append(n)
    if added and not check:
        lines = ['%d=%s' % (i, n) for n, i in sorted(have.items(), key=lambda kv: kv[1])]
        open(path, 'w', newline='').write(nl.join(lines) + nl)
    return added


def config_names(path):
    return re.findall(r'^\[([^\]]+)\]', read(path), re.M)


def main():
    check = '--check' in sys.argv
    spec, entries, distinct = load()
    want = {}
    for path, body, like in [
            (OUT_DBROW, build_dbrow(spec, entries), OUT_DBROW),
            (OUT_ENUM, build_enum(distinct), OUT_DBROW),
            (OUT_VARP, build_varp(spec), OUT_DBROW),
            (OUT_CONST, build_const(spec, entries, distinct), OUT_DBROW),
            (OUT_IF, G.emit(components(spec, entries)), QUESTLIST),
            (OUT_RS2, build_rs2(spec, entries), os.path.join(C, 'scripts/bosses/scripts/boss_kills.rs2'))]:
        want[path] = to_nl(body, nl_of(path, like))
    qtext = patch_questlist(read(QUESTLIST))
    want[QUESTLIST] = qtext

    varps = config_names(HANDVARP) + ['collection_log_count_%s' % c['key'] for c in spec['own_counters']]
    invs = config_names(HANDINV)
    bad = []
    for path, body in want.items():
        have = read(path) if os.path.exists(path) else None
        if have != body:
            bad.append(os.path.relpath(path, C))
            if not check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, 'w', newline='', encoding='utf-8').write(body)
    a1 = take(VARPPACK, varps, check)
    a2 = take(INVPACK, invs, check)
    if check:
        packed = set(re.findall(r'^\d+=(\S+?)\r?$', read(ifids.PACK), re.M))
        ids_ok = all('%s:%s' % (IFACE, n) in packed for n, _ in components(spec, entries)) and IFACE in packed
        if bad or a1 or a2 or not ids_ok:
            print('gencollectionlog --check: would change %s' % ', '.join(
                bad + (['varp.pack'] if a1 else []) + (['inv.pack'] if a2 else []) +
                ([] if ids_ok else ['interface.pack'])))
            return 1
        print('gencollectionlog --check: everything is already what this writes')
        return 0
    for line in ifids.sync([IFACE, 'questlist']):
        print(line)
    print('%d tabs, %d entries, %d distinct items (capacity %d), grid %dx%d; wrote %d files, '
          '%d varp ids, %d inv ids' % (len(spec['tabs']), len(entries), len(distinct), spec['capacity'], COLS,
                                       grid_rows(entries), len(bad), len(a1), len(a2)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
