#!/usr/bin/env python3
"""Re-implement the bank tab arithmetic from bank_tabs.rs2 and beat on it.

WHY. A tab is a RANGE of one ordered list, so every count is load-bearing: get one wrong and
every tab above it shows somebody else's items. Nothing in the build checks that, and it is not
the kind of thing that shows up as a crash - it shows up as a player's bank quietly reshuffling.
So the procs are transcribed here and run against random sequences, asserting the invariants the
rs2 cannot assert for itself.

Transcribed from scripts/interface_bank/scripts/bank_tabs.rs2 - if that changes, change this.
"""
import os, random, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TABS = 8

def _const(name):
    """Read a ^constant out of bank.constant. The bank's capacity and the grid's row count are the
    two numbers this file's capacity proof is ABOUT, so reading them beats writing them down again:
    a sim that carried its own 352 would have gone on passing after the bank was made bigger."""
    src = open(os.path.join(ROOT, 'scripts/interface_bank/configs/bank.constant'),
               encoding='utf-8').read()
    m = re.search(r'^\^%s = (\d+)' % name, src, re.M)
    if not m:
        sys.exit('cannot find ^%s in bank.constant' % name)
    return int(m.group(1))

def _grid(key):
    """width= (columns) or height= (rows) on the [bank] inv component, i.e. what
    tools/genbanktabs.py last wrote out of tools/bankgeom.py. Both are read rather than written
    down here, because the padding this file's capacity proof is about is a function of the
    COLUMN count - a sim carrying its own 8 would have gone on passing after the grid was
    widened to 12 and the worst-case padding grew from 56 cells to 88."""
    src = open(os.path.join(ROOT, 'scripts/interface_bank/interfaces/bank_main.if'),
               encoding='utf-8').read()
    m = re.search(r'^\[bank\]\n(?:.*\n)*?%s=(\d+)$' % key, src, re.M)
    if not m:
        sys.exit('cannot find the bank grid %s in bank_main.if' % key)
    return int(m.group(1))

SIZE = _const('bank_total_slots')


def _release_contract():
    """THE CLIENT DECIDES WHAT A PLACEHOLDER IS FROM THIS FILE, and it cannot be checked there.

    Client.java offers the "Release" option on any inv component slot holding a zero count. A zero
    count is NOT unique to a placeholder - 35 shop invs in this content carry 272 lines stocked at
    0, and every one of those items offered Release until 2026-09-21, reported from play against
    the Shantay Pass shop, whose bucket, bowl and jug are all stocked at 0.

    The client now gates it on the component's FIRST OPTION beginning with "Withdraw", rather than
    on a hardcoded component id that nobody editing the content would think to look at. That makes
    this file's option wording a contract between two repositories, and this is the half that lives
    here - a check in the client could never go red when the content renamed an option.

    THE GATE IS NOT EXACT, AND SAYING SO IS THE POINT. Four components carry Withdraw options and
    the party drop chest's five are spelled identically to the bank's, so no wording can separate
    them. What makes it correct is that only the bank ever holds a zero count: placeholders are the
    only thing that makes one, and shops - which do stock 0 - carry Value and Buy instead. That is
    what is checked here, rather than a uniqueness that does not hold.
    """
    bank = open(os.path.join(ROOT, 'scripts/interface_bank/interfaces/bank_main.if'),
                encoding='utf-8').read()
    block = re.search(r'^\[bank\]\n((?:(?!^\[).*\n)*)', bank, re.M)
    if not block:
        sys.exit('cannot find the [bank] component in bank_main.if')
    opts = dict(re.findall(r'^(option\d)=(.*)$', block.group(1), re.M))
    if not opts.get('option1', '').startswith('Withdraw'):
        sys.exit('the bank grid\'s option1 is %r, which does not start with "Withdraw" - '
                 'Client.java gates the placeholder Release option on exactly that prefix, so '
                 'renaming it silently removes the only way to clear a placeholder'
                 % opts.get('option1'))
    print('the bank grid\'s option1 is %r, which is what Client.java gates the placeholder '
          'Release option on' % opts['option1'])

    # THE SHOP SIDE, which is the half that was actually broken: a shop grid must never carry a
    # Withdraw option, because shop invs are the only ones in the game stocked at zero.
    shop = open(os.path.join(ROOT, 'scripts/shop/interfaces/shop_template.if'),
                encoding='utf-8').read()
    sopts = re.findall(r'^option1=(.*)$', shop, re.M)
    if not sopts:
        sys.exit('the shop template has no option1 to check')
    if any(o.startswith('Withdraw') for o in sopts):
        sys.exit('a shop grid carries a Withdraw option: %s - every zero-stock line in the game '
                 'would offer Release' % sopts)
    print('and no shop grid does, so none of the 272 zero-stock shop lines can offer it')

    # ...and any NEW component that grows Withdraw options gets looked at, because the reason the
    # gate is safe is that none of these ever holds a zero count.
    KNOWN = {'bank', 'store', 'inv', 'playerinv'}
    seen = set()
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith('.if'):
                continue
            cur = None
            for line in open(os.path.join(dirpath, fn), encoding='utf-8', errors='replace'):
                t = line.split('//')[0].strip()
                if t.startswith('[') and t.endswith(']'):
                    cur = t[1:-1]
                elif t.startswith('option1=') and t[8:].startswith('Withdraw'):
                    seen.add(cur)
    new = sorted(seen - KNOWN)
    if new:
        sys.exit('these components have grown Withdraw options since this was written: %s - the '
                 'client will offer Release on any zero-count slot in them, so check that they '
                 'cannot hold one' % ', '.join(new))
    print('and the %d components carrying Withdraw options are the known ones, none of which can '
          'hold a zero count: %s' % (len(KNOWN), ', '.join(sorted(KNOWN))))


_release_contract()

class Bank:
    def __init__(s):
        s.items = []            # the gapless ordered list; each entry is an opaque id
        s.c = [0] * (TABS + 1)  # c[1..8]

    # ---- transcribed procs. The untabbed block LEADS the list:
    #        [ untabbed ][ tab1 ][ tab2 ] ... [ tab8 ]
    def numbered_total(s):
        return sum(s.c[i] for i in range(1, TABS + 1))
    def untabbed(s):
        return len(s.items) - s.numbered_total()
    def start(s, tab):
        if tab == 0:
            return 0
        return s.untabbed() + sum(s.c[i] for i in range(1, tab))
    def of_slot(s, slot):
        return s.of_slot2(slot, s.untabbed())

    def of_slot2(s, slot, untabbed):
        # The untabbed length is DERIVED, so it slides the moment an item leaves the bank. Anything
        # asking who owned a slot after that has to supply the length it HAD.
        end = untabbed
        if slot < end:
            return 0
        for i in range(1, TABS + 1):
            end += s.c[i]
            if slot < end:
                return i
        return 0
    def closegap(s, slot):
        if slot < len(s.items):
            s.items.pop(slot)
    def removed(s, slot):
        # Mirrors ~banktab_removed, which runs AFTER the withdrawal has already taken the item out
        # of the bank. The sim used to pop afterwards, which quietly gave it a pre-removal view the
        # real script never has - and that is exactly why it missed the bug where withdrawing the
        # last untabbed item was blamed on tab 1.
        s.items.pop(slot)
        tab = s.of_slot2(slot, s.untabbed() + 1)
        if tab:
            s.c[tab] = max(0, s.c[tab] - 1)
        s.compact()
    def removed_guarded(s, slot, occupied):
        # ~banktab_removed in full: its first two lines return without doing anything if the slot
        # still holds an obj. A PLACEHOLDER is an obj - the bank slot with a count of zero that
        # ~bank_withdraw_request drops in when the padlock is on - so a withdrawal that left one
        # behind reaches this and correctly changes nothing. Releasing the stub clears the slot
        # first, so the same call then does the real work.
        if occupied:
            return
        s.removed(slot)

    def insert(s, frm, to):
        it = s.items.pop(frm)
        s.items.insert(to, it)
    def move_to(s, slot, tab):
        frm = s.of_slot(slot)
        if frm == tab:
            return
        s.place(slot, tab, frm)

    def append(s, slot, tab):
        # ~banktab_append - the drop-on-the-padding gesture. Same as move_to but with no early
        # return, because appending within your own tab is a legitimate reorder.
        s.place(slot, tab, s.of_slot(slot))

    def dragged(s, frm, to):
        # insert-mode drag: the shift moves the item across a break, so one tab loses an item and
        # the other gains one. Worked out BEFORE the shift, while the slot numbers still mean what
        # they say. Swap mode needs none of this - two items trade places and every range keeps
        # its length.
        ft, tt = s.of_slot(frm), s.of_slot(to)
        if ft == tt:
            return
        if ft:
            s.c[ft] -= 1
        if tt:
            s.c[tt] += 1

    def insert_drag(s, frm, to):
        s.dragged(frm, to)
        s.insert(frm, to)
        s.compact()

    def swap_drag(s, a, bx):
        # The rearrange mode only decides what happens WITHIN a tab. A drag that crosses a tab
        # boundary is always a move: the player asked for the item to go there, not for whatever
        # was there to come back. bank.rs2's [inv_buttond] makes the same test.
        if s.of_slot(a) != s.of_slot(bx):
            s.insert_drag(a, bx)
            return
        s.items[a], s.items[bx] = s.items[bx], s.items[a]
        s.compact()

    def reverse(s, frm, to):
        # inv_movetoslot SWAPS, so reversing a run costs half its length
        a, bx = frm, to
        while a < bx:
            s.items[a], s.items[bx] = s.items[bx], s.items[a]
            a += 1
            bx -= 1

    def swap_tabs(s, x, y):
        # [A][middle][B] -> [B][middle][A]: reverse each part, then reverse the whole span.
        if x == y or x < 0 or y < 0:
            return
        lo, hi = (x, y) if x < y else (y, x)
        ls, lc = s.start(lo), s.c[lo]
        hs, hc = s.start(hi), s.c[hi]
        if lc == 0 and hc == 0:
            return
        if lc:
            s.reverse(ls, ls + lc - 1)
        if hs > ls + lc:
            s.reverse(ls + lc, hs - 1)
        if hc:
            s.reverse(hs, hs + hc - 1)
        s.reverse(ls, hs + hc - 1)
        s.c[lo], s.c[hi] = hc, lc
        s.compact()

    def place(s, slot, tab, in_tab):
        if in_tab > 0:
            s.c[in_tab] -= 1
        n = len(s.items)
        numbered = s.numbered_total()
        if tab == 0:
            dest = n - numbered - 1
        else:
            dest = n - numbered - 1
            for i in range(1, tab + 1):
                dest += s.c[i]
            s.c[tab] += 1
        s.insert(slot, dest)
        s.compact()
    def deposit(s, obj, viewing):
        s.items.append(obj)
        s.place(len(s.items) - 1, viewing, -1)
    def compact(s):
        # tabs in use must be 1..n with no holes. Nothing MOVES - an empty tab occupies zero slots,
        # so renumbering the tabs above it down leaves every item exactly where it was.
        dst = 1
        for src in range(1, TABS + 1):
            if s.c[src] > 0:
                s.c[dst] = s.c[src]
                dst += 1
        while dst <= TABS:
            s.c[dst] = 0
            dst += 1

    def validate(s):
        occupied = len(s.items)
        total = s.numbered_total()
        tab = TABS
        while tab > 0 and total > occupied:
            excess = total - occupied
            if s.c[tab] <= excess:
                total -= s.c[tab]; s.c[tab] = 0
            else:
                s.c[tab] -= excess; total = occupied
            tab -= 1
        # validate runs on OPEN, and opening is when the player looks at the tab row - so it is
        # where a hole left by an older filing, or punched by the clamp above, has to be closed.
        s.compact()

    # ---- invariants
    def check(s, where):
        # no holes in the tab numbering
        seen_empty = False
        for t in range(1, TABS + 1):
            if s.c[t] == 0:
                seen_empty = True
            elif seen_empty:
                raise AssertionError(f'{where}: tab {t} is in use but a lower tab is empty: {s.c[1:]}')
        assert all(x >= 0 for x in s.c), f'{where}: negative count {s.c}'
        assert s.numbered_total() <= len(s.items), \
            f'{where}: tabs claim {s.numbered_total()} of {len(s.items)} items -> a tab points past the end'
        # the untabbed block leads, so the last numbered tab must end exactly at the end of the list
        if s.numbered_total() > 0:
            last = max(t for t in range(1, TABS + 1) if s.c[t] > 0)
            assert s.start(last) + s.c[last] == len(s.items), \
                f'{where}: tab {last} ends at {s.start(last) + s.c[last]}, list is {len(s.items)}'
        assert len(s.items) == len(set(s.items)), f'{where}: an item was duplicated'
        # every item is in exactly one tab, and the ranges tile the list in order
        seen = 0
        for t in range(1, TABS + 1):
            for i in range(s.start(t), s.start(t) + s.c[t]):
                assert s.of_slot(i) == t, f'{where}: slot {i} should be tab {t}, of_slot says {s.of_slot(i)}'
                seen += 1
        assert seen == s.numbered_total()
        for i in range(0, s.untabbed()):
            assert s.of_slot(i) == 0, f'{where}: slot {i} in the leading untabbed block is not tab 0'
        assert s.untabbed() >= 0, f'{where}: the tabs claim more than the bank holds'

def run(seed):
    rnd = random.Random(seed)
    b = Bank(); nxt = 0
    for step in range(400):
        act = rnd.random()
        if act < 0.35 and len(b.items) < SIZE:
            b.deposit(nxt, rnd.choice([0] + list(range(1, TABS + 1)))); nxt += 1
        elif act < 0.6 and b.items:
            b.removed(rnd.randrange(len(b.items)))
        elif act < 0.75 and b.items:
            b.move_to(rnd.randrange(len(b.items)), rnd.randrange(0, TABS + 1))
        elif act < 0.80 and len(b.items) > 1:
            b.swap_tabs(rnd.randrange(1, TABS + 1), rnd.randrange(1, TABS + 1))
        elif act < 0.85 and len(b.items) > 1:
            b.insert_drag(rnd.randrange(len(b.items)), rnd.randrange(len(b.items)))
        elif act < 0.9 and len(b.items) > 1:
            b.swap_drag(rnd.randrange(len(b.items)), rnd.randrange(len(b.items)))
        else:
            # simulate items vanishing behind the bank's back (death, other scripts),
            # then the guard that runs on open
            for _ in range(rnd.randrange(1, 4)):
                if b.items: b.items.pop(rnd.randrange(len(b.items)))
            b.validate()
            b.compact()
        b.check(f'seed {seed} step {step}')
    return b

worst = 0
for seed in range(400):
    b = run(seed)
    worst = max(worst, len(b.items))
print(f'400 seeds x 400 operations: all invariants held (largest bank reached {worst} items)')

# Targeted cases. Layout: items 0..9, c1=3 c2=3, so untabbed is slots 0-3, tab1 is 4-6, tab2 is 7-9.
# These pin the arithmetic in ~banktab_place, which computes the item's FINAL index rather than
# "one past the end of the range" - that is what removed the old off-by-one correction.
b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
b.check('setup')
assert b.untabbed() == 4 and b.start(1) == 4 and b.start(2) == 7

b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
b.move_to(4, 2)                     # first item of tab 1 -> tab 2
b.check('rightward move')
assert b.c[1] == 2 and b.c[2] == 4, f'counts wrong: {b.c[1:3]}'
assert b.items == [0, 1, 2, 3, 5, 6, 7, 8, 9, 4], f'item landed wrong: {b.items}'
assert b.of_slot(9) == 2, 'it should be the last item of tab 2'
print('rightward move across a boundary lands at the end of the destination tab')

b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
b.move_to(9, 1)                     # last item of tab 2 -> tab 1
b.check('leftward move')
assert b.c[1] == 4 and b.c[2] == 2, f'counts wrong: {b.c[1:3]}'
assert b.items == [0, 1, 2, 3, 4, 5, 6, 9, 7, 8], f'item landed wrong: {b.items}'
assert b.of_slot(7) == 1, 'it should be the last item of tab 1'
print('leftward move across a boundary lands at the end of the destination tab')

# out of a tab and back into the untabbed block, which now LEADS the list
b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
b.move_to(4, 0)                     # first item of tab 1 -> untabbed
b.check('move to untabbed')
assert b.c[1] == 2 and b.c[2] == 3, f'counts wrong: {b.c[1:3]}'
assert b.items == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], f'item landed wrong: {b.items}'
assert b.of_slot(4) == 0, 'it should now be the last item of the untabbed block'
print('moving out of a tab puts the item at the end of the leading untabbed block')

# a deposit while a tab is open goes into that tab, not onto the end of the list
b = Bank(); b.items = list(range(6)); b.c[1] = 2; b.c[2] = 2
b.deposit(99, 1)
b.check('deposit into an open tab')
assert b.c[1] == 3, f'deposit did not join tab 1: {b.c[1:3]}'
assert b.of_slot(b.items.index(99)) == 1
print('a deposit with tab 1 open joins tab 1 rather than landing on the end of the list')

# and a deposit with no tab open lands at the end of the untabbed block, ahead of the tabs
b = Bank(); b.items = list(range(6)); b.c[1] = 2; b.c[2] = 2
b.deposit(99, 0)
b.check('deposit untabbed')
assert b.c[1] == 2 and b.c[2] == 2
assert b.of_slot(b.items.index(99)) == 0 and b.items.index(99) == b.untabbed() - 1
print('an untabbed deposit lands at the end of the untabbed block, ahead of every tab')

# ===================================================================================================
# The "all items" cell map
# ===================================================================================================
# Transcribed from Component.rebuildCellMap in the client. This is the half that can silently HIDE
# an item: the breaks push everything down, and if the map ran off the end of the grid an item would
# simply stop being drawn with nothing to say so.
# The grid needs room for up to TABS * (WIDTH - 1) padding cells on top of the real slots, so it
# is taller than the inv. Every number is read rather than written down - see _const and _grid.
WIDTH, ROWS = _grid('width'), _grid('height')
CELLS = WIDTH * ROWS
SLOTS = SIZE
assert CELLS >= SLOTS + (TABS * (WIDTH - 1)), (
    'the grid is too short for %d slots plus %d cells of worst-case tab padding: %d cells'
    % (SLOTS, TABS * (WIDTH - 1), CELLS))

def cellmap_drop(first, count, breaks):
    """The DROP map from Component.rebuildCellMap: same as cellmap, except the blank cells that pad
    a block out to the end of its row aim at that block's last item instead of at nothing."""
    broken = any(b > 0 for b in breaks)
    d = [-1] * CELLS
    first = first if count >= 0 else 0
    count = count if count >= 0 else CELLS
    cell = 0
    slot = first
    while slot < first + count and cell < CELLS:
        if broken:
            for b in breaks:
                if b == slot and slot > first and cell % WIDTH != 0:
                    pad = cell + WIDTH - cell % WIDTH
                    while cell < pad and cell < CELLS:
                        d[cell] = slot - 1
                        cell += 1
        if cell >= CELLS:
            break
        d[cell] = slot
        cell += 1
        slot += 1
    return d

def cellmap(first, count, breaks):
    broken = any(b > 0 for b in breaks)
    if count < 0 and not broken:
        return None
    m = [-1] * CELLS
    first = first if count >= 0 else 0
    count = count if count >= 0 else CELLS
    cell = 0
    slot = first
    while slot < first + count and cell < CELLS:
        if broken:
            for b in breaks:
                if b == slot and cell % WIDTH != 0:
                    cell += WIDTH - cell % WIDTH
        if cell >= CELLS:
            break
        m[cell] = slot
        cell += 1
        slot += 1
    return m

def all_view(b):
    breaks = [b.start(t) for t in range(1, TABS + 1)]
    m = cellmap(0, -1, breaks)
    # None is the client's "identity mapping" case - every break is 0, i.e. no tab is in use, so
    # the all-items view is just the plain contiguous list. Spell it out rather than special-case
    # it at every call site.
    return (m if m is not None else list(range(CELLS))), breaks

fail = 0
for seed in range(400):
    b = run(seed)
    m, breaks = all_view(b)
    shown = [s for s in m if s >= 0]
    # every real item is reachable, in order. shown is slot NUMBERS, so the test is that the
    # first len(items) of them are 0..n-1 - i.e. no item was skipped or reordered by the padding.
    if shown[:len(b.items)] != list(range(len(b.items))):
        print(f'seed {seed}: all-view order wrong'); fail += 1
    # each tab starts on a fresh row
    for t in range(1, TABS + 1):
        if b.c[t] == 0:
            continue
        cell = m.index(b.start(t))
        if cell % WIDTH != 0 and b.start(t) != 0:
            print(f'seed {seed}: tab {t} starts mid-row at cell {cell}'); fail += 1
    # nothing is dropped off the bottom at realistic sizes
    if len(shown) < len(b.items):
        print(f'seed {seed}: {len(b.items) - len(shown)} items pushed off the grid '
              f'({len(b.items)} items, 8 tabs)'); fail += 1
assert fail == 0, f'{fail} all-view failures'
print('400 seeds: the all-items view shows every item, in order, each tab starting on a fresh row')

# the worst case: eight tabs each holding one item wastes seven cells per tab
b = Bank()
b.items = list(range(16))
for t in range(1, 9):
    b.c[t] = 1
m, breaks = all_view(b)
shown = [s for s in m if s >= 0]
assert shown[:16] == list(range(16)), 'worst case lost an item'
for t in range(1, 9):
    assert m.index(b.start(t)) % WIDTH == 0 or b.start(t) == 0
print('worst case (8 tabs x 1 item): the untabbed block leads, then 8 rows of one, nothing lost')

# and the capacity cost of the breaks at full tilt
# the capacity question the extra rows exist to answer: a FULL bank, eight tabs each ragged
# enough to waste the maximum 7 cells. Every one of the slots must still be reachable.
b = Bank(); b.items = list(range(SLOTS))
for t in range(1, 9):
    # one item more than a full row: two rows, WIDTH - 1 cells wasted, the worst a tab can do
    b.c[t] = WIDTH + 1
m, _ = all_view(b)
shown = [s for s in m if s >= 0]
assert shown[:SLOTS] == list(range(SLOTS)), \
    f'full bank + worst-case padding loses items: only {len(shown)} of {SLOTS} reachable'
print(f'full bank ({SLOTS}) with 8 maximally ragged tabs: all {SLOTS} reachable in {CELLS} cells '
      f'({CELLS - SLOTS} spare)')
print('ALL PASS')

# an insert-mode drag across a break moves the item between tabs and the counts follow
b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3     # untabbed 0-3, tab1 4-6, tab2 7-9
b.insert_drag(4, 8)                 # first of tab 1 -> inside tab 2
b.check('insert across a break')
assert b.c[1] == 2 and b.c[2] == 4, f'counts did not follow the drag: {b.c[1:3]}'
assert b.of_slot(8) == 2
print('an insert drag across a break moves the item between tabs and the counts follow')

# a swap WITHIN a tab changes nothing about the sizes
b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
before = list(b.c)
b.swap_drag(4, 6)                   # both ends inside tab 1
b.check('swap inside a tab')
assert b.c == before, f'swap should not resize a tab: {b.c[1:3]}'
assert b.items[4] == 6 and b.items[6] == 4
print('a swap inside one tab trades two items and leaves every tab the same size')

# and in swap mode a drag ACROSS a break is a move, not a swap
b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
b.swap_drag(4, 8)
b.check('cross-tab drag in swap mode')
assert b.c[1] == 2 and b.c[2] == 4, f'the counts did not follow the move: {b.c[1:3]}'
assert b.items[8] == 4, 'the dragged item should have landed on the slot it was dropped on'
assert 8 not in b.items[:5], 'nothing should have come back the other way'
print('in swap mode a drag across a break moves the item rather than trading two')

# dragging one tab onto another trades their contents, and leaves everything between alone
b = Bank(); b.items = list(range(12))
b.c[1] = 2; b.c[2] = 3; b.c[3] = 1          # untabbed 0-5, tab1 6-7, tab2 8-10, tab3 11
assert b.untabbed() == 6
tab1 = b.items[b.start(1):b.start(1) + b.c[1]]
tab2 = b.items[b.start(2):b.start(2) + b.c[2]]
tab3 = b.items[b.start(3):b.start(3) + b.c[3]]
untabbed = b.items[:b.untabbed()]
b.swap_tabs(1, 3)
b.check('tab swap')
assert b.items[:b.untabbed()] == untabbed, 'the untabbed block should not move'
assert b.items[b.start(1):b.start(1) + b.c[1]] == tab3, f'tab 1 should hold the old tab 3: {b.items}'
assert b.items[b.start(3):b.start(3) + b.c[3]] == tab1, f'tab 3 should hold the old tab 1: {b.items}'
assert b.items[b.start(2):b.start(2) + b.c[2]] == tab2, f'tab 2 should be untouched: {b.items}'
print('swapping two tabs trades their contents and leaves the tabs between them alone')

# swapping with an empty tab moves the contents across rather than doing nothing
b = Bank(); b.items = list(range(8)); b.c[1] = 3
b.swap_tabs(1, 2)
b.check('swap with an empty tab')
assert b.c[1] == 3, 'compaction should pull the contents back down to tab 1'
print('swapping a tab with an empty one is a no-op after compaction, which is the sane answer')

# THE REGRESSION THIS ORDERING EXISTS FOR. Withdrawing the LAST untabbed item used to be blamed on
# tab 1, because the untabbed block's derived length had already slid one place by the time anyone
# asked. Tab 1 lost an item it never gave up - "taking something out pulled another item into a tab
# it was never in". Reproduced here with the naive (wrong) question, then with the right one.
b = Bank(); b.items = list(range(8)); b.c[1] = 3     # untabbed 0-4, tab1 5-7
assert b.untabbed() == 5
tab1_before = b.items[b.start(1):]
b.items.pop(4)                                       # withdraw the last untabbed item
naive = b.of_slot2(4, b.untabbed())                  # asking with the ALREADY-SLID length
right = b.of_slot2(4, b.untabbed() + 1)              # asking with the length it had
assert naive == 1, 'the naive question should wrongly blame tab 1'
assert right == 0, 'the right question should say untabbed'
print('withdrawing the last untabbed item: naive lookup blames tab 1, corrected lookup says untabbed')

b = Bank(); b.items = list(range(8)); b.c[1] = 3
b.removed(4)
b.check('withdraw the last untabbed item')
assert b.c[1] == 3, f'tab 1 should be untouched, got {b.c[1]}'
assert b.items[b.start(1):] == tab1_before, 'tab 1 should still hold exactly the same items'
print('and the fixed ~banktab_removed leaves tab 1 holding exactly what it held')

# The same at every boundary. The slot just below tab t belongs to tab t-1 (or to the untabbed
# block when t is 1), so exactly that owner should shrink and nobody else should be touched. This
# is the general form of the bug: whoever owned the slot pays, and only them.
for t in range(1, 4):
    b = Bank(); b.items = list(range(12)); b.c[1] = 2; b.c[2] = 2; b.c[3] = 2
    slot = b.start(t) - 1
    owner = b.of_slot(slot)
    before = {k: b.items[b.start(k):b.start(k) + b.c[k]] for k in range(1, 4)}
    b.removed(slot)
    b.check(f'withdraw just below tab {t}')
    for k in range(1, 4):
        got = b.items[b.start(k):b.start(k) + b.c[k]]
        if k == owner:
            assert len(got) == len(before[k]) - 1, f'tab {k} should lose exactly one: {before[k]} -> {got}'
        else:
            assert got == before[k], f'tab {k} was not the owner but changed: {before[k]} -> {got}'
print('withdrawing at any boundary charges the tab that owned the slot, and only that tab')

# Dropping an item on a TAB BUTTON files it into that tab - the append path, and the only way to
# reach a tab that is empty. (Dropping inside another tab's block in the grid is a different thing:
# that is an ordinary swap, so the two items trade places AND trade tabs. See swap_drag below.)
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3   # untabbed 0-5, tab1 6-8, tab2 9-11
src = b.start(1)                       # first item of tab 1
item = b.items[src]
dst = b.start(2) + 1                   # somewhere inside tab 2
assert b.of_slot(src) == 1 and b.of_slot(dst) == 2
b.move_to(src, b.of_slot(dst))
b.check('cross-tab drag')
assert b.c[1] == 2 and b.c[2] == 4, f'counts wrong: {b.c[1:3]}'
assert b.items[b.start(2):b.start(2) + b.c[2]][-1] == item, 'it should be the last item of tab 2'
assert item not in b.items[b.start(1):b.start(1) + b.c[1]], 'and gone from tab 1'
print('dropping on a tab button appends the item to that tab')

# dragging into the untabbed block works the same way
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3
src = b.start(2)
item = b.items[src]
b.move_to(src, b.of_slot(0))
b.check('drag into the untabbed block')
assert b.c[2] == 2, f'tab 2 should have lost it: {b.c[1:3]}'
assert b.items[b.untabbed() - 1] == item, 'it should be the last untabbed item'
print('and dropping on the All button puts it back in the untabbed block')

# The padding after a tab is a drop target aimed at that tab, not dead space. This is what "moving
# items to the breaks doesn't work" actually was: those cells hit no slot, so the client sent no
# packet at all and the drag looked ignored.
b = Bank(); b.items = list(range(14))
b.c[1] = 3; b.c[2] = 3          # untabbed 0-7 (one full row), tab1 8-10, tab2 11-13
breaks = [b.start(t) for t in range(1, TABS + 1)]
m = cellmap(0, -1, breaks)
d = cellmap_drop(0, -1, breaks)
pad = [c for c in range(CELLS) if m[c] < 0 and d[c] >= 0]
assert pad, 'there should be padding cells after a ragged tab'
for c in pad:
    tab_of_pad = b.of_slot(d[c])
    # the padding directly follows its own block, so its target is that block's last item
    assert d[c] == max(x for x in m[:c] if x >= 0), f'cell {c} aims at {d[c]}, not the block above it'
print(f'{len(pad)} padding cells are drop targets aimed at the tab they pad, not dead space')

# and a real cell's drop target is still just itself
real = [c for c in range(CELLS) if m[c] >= 0]
assert all(d[c] == m[c] for c in real), 'a cell holding an item should drop onto itself'
print('cells that hold an item still target themselves, so ordinary drags are unchanged')

# A drag across a break MOVES. This went back and forth twice before it settled. It was briefly
# "file the dragged item into the target tab", which left the other item where it was so both ended
# up in the destination; that was corrected to a true swap, which was wrong the other way - the item
# under the cursor came back into the source tab, which is nothing the player asked for ("this isnt
# supposed to be a swap feature, just a move to"). It is an insert: one tab loses an item, the other
# gains one, and every other item keeps its neighbours.
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3   # untabbed 0-5, tab1 6-8, tab2 9-11
src, dst = b.start(1), b.start(2) + 1
mine, theirs = b.items[src], b.items[dst]
b.swap_drag(src, dst)
b.check('cross-tab move')
assert b.c[1] == 2 and b.c[2] == 4, f'the counts did not follow the move: {b.c[1:3]}'
assert b.of_slot(b.items.index(mine)) == 2, 'the dragged item should now be in tab 2'
assert b.of_slot(b.items.index(theirs)) == 2, 'and the one it was dropped on should have stayed put'
assert b.items[dst] == mine, 'the dragged item should sit exactly where it was dropped'
print('a drag across a break moves the item into the target tab and nothing comes back')

# ---------------------------------------------------------------------------------------------
# Placeholders. The tab arithmetic needs no changes for them, and that is the claim worth pinning:
# a placeholder OCCUPIES its slot, the ranges are positional, so a stub is just a position like
# any other. What changes is whether ~banktab_removed does anything.
# ---------------------------------------------------------------------------------------------

# withdrawing the last of a stack with the padlock ON leaves a stub, so nothing leaves the list
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3   # untabbed 0-5, tab1 6-8, tab2 9-11
items_before, counts_before = list(b.items), list(b.c)
b.removed_guarded(b.start(1), True)                            # first item of tab 1, stub left
b.check('withdraw with placeholders on')
assert b.items == items_before, 'a stub keeps the list exactly as it was'
assert b.c == counts_before, f'no tab should have shrunk: {b.c[1:3]}'
print('withdrawing the last of a stack with the padlock on moves nothing and shrinks no tab')

# and with it OFF the slot really empties, which is the behaviour that was there all along
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3
gone = b.items[b.start(1)]
b.removed_guarded(b.start(1), False)
b.check('withdraw with placeholders off')
assert gone not in b.items, 'the item should have left the list'
assert b.c[1] == 2 and b.c[2] == 3, f'only the tab that owned it should shrink: {b.c[1:3]}'
print('and with the padlock off it leaves, closing its gap and shrinking its own tab')

# releasing one stub is the same operation, just deferred
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3
stub = b.start(2) + 1                                          # a stub sitting inside tab 2
held = b.items[stub]
b.removed_guarded(stub, True)                                  # the withdrawal that made it
b.removed_guarded(stub, False)                                 # ~bank_release clears it first
b.check('release one')
assert held not in b.items and b.c[2] == 2, f'tab 2 should be down to two: {b.c[1:3]}'
print('releasing a stub takes it out of its tab exactly as a withdrawal without one would have')

# release-all walks TOP DOWN, because closing a gap shifts everything above the slot down by one.
# Walking upwards would move slots the loop had not reached yet out from under it.
b = Bank(); b.items = list(range(16)); b.c[1] = 4; b.c[2] = 4   # untabbed 0-7, tab1 8-11, tab2 12-15
stubs = {2, 5, 9, 10, 14}
survivors = [x for i, x in enumerate(b.items) if i not in stubs]
for slot in sorted(stubs, reverse=True):
    b.removed_guarded(slot, False)
b.check('release all')
assert b.items == survivors, 'every non-stub should have kept its order'
assert b.c[1] == 2, f'tab 1 held two stubs and should be down to two: {b.c[1]}'
assert b.c[2] == 3, f'tab 2 held one stub and should be down to three: {b.c[2]}'
print('releasing every stub top down leaves the survivors in order with the right tab sizes')

# Dropping on the PADDING after a tab's items appends to that tab. The client aims a padding cell at
# its block's LAST ITEM (that is what invCellDrop is for), and inserting AT that slot lands the
# dragged obj one place short of the end - the item that was last stays last. Corey dragged d boots
# onto the blank space after a seed box and expected them to end up after it: "the dboots should
# just go after the seed box and everything should move one slot to refill the missing d boots".
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3   # untabbed 0-5, tab1 6-8, tab2 9-11
mine = b.items[b.start(1)]                                     # first item of tab 1
last_untabbed = b.items[b.untabbed() - 1]                      # what the padding cell aims at
b.append(b.start(1), 0)                                        # dropped on the untabbed block's padding
b.check('append onto the untabbed block')
assert b.c[1] == 2 and b.c[2] == 3, f'only the source tab should shrink: {b.c[1:3]}'
assert b.items[b.untabbed() - 1] == mine, 'the dragged item should be LAST in the block it joined'
assert b.items[b.untabbed() - 2] == last_untabbed, 'and the item that was last should now be second to last'
print('dropping on the padding after a block appends to it rather than landing one short')

# and the same gesture aimed at a numbered tab
b = Bank(); b.items = list(range(12)); b.c[1] = 3; b.c[2] = 3
mine = b.items[0]
b.append(0, 2)
b.check('append onto tab 2')
assert b.c[1] == 3 and b.c[2] == 4, f'tab 2 should have grown by one: {b.c[1:3]}'
assert b.items[b.start(2) + b.c[2] - 1] == mine, 'the dragged item should be last in tab 2'
print('and appending onto a numbered tab puts the item on the end of that tab')
