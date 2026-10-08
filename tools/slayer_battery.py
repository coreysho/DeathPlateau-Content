"""Battery for the Slayer Rewards window.

Everything is parsed out of the delivered files - the rewards from the enums, the layout from the
.if, the click budget from the constants - and the text is MEASURED with the same font the client
draws it in (tools/ifrender.font), so "it fits" is a fact rather than a character count.

    python3 tools/slayer_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(C, 'tools'))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def before(hay, a, b):
    """a appears before b - and False rather than an exception when either is missing.

    A CHECK WHOSE OWN CONDITION RAISES IS A CRASH, NOT A CHECK. hay.index(x) throws when x is
    gone, which is exactly what a mutation removes: the battery blew up, the mutation harness
    counted the non-zero exit as caught, and no check had fired. Five were found that way in one
    afternoon, and each was hiding the fact that nothing asserted the thing was there at all.
    """
    return a in hay and b in hay and hay.index(a) < hay.index(b)

IF = read('scripts/skill_slayer/interfaces/slayer_rewards.if')
UI = read('scripts/skill_slayer/scripts/slayer_ui.rs2')
WIN = read('scripts/skill_slayer/scripts/slayer_window.rs2')
REW = read('scripts/skill_slayer/scripts/slayer_rewards.rs2')
PTS = read('scripts/skill_slayer/scripts/slayer_points.rs2')
MASTER = read('scripts/skill_slayer/scripts/slayer_master.rs2')
ENUMS = read('scripts/skill_slayer/configs/slayer_rewards.enum')
CONST = read('scripts/skill_slayer/configs/slayer.constant')
GEN = read('tools/genslayerui.py')

def const(n):
    m = re.search(r'\^' + n + r'\s*=\s*(0x[0-9A-Fa-f]+|-?\d+)', CONST)
    return int(m.group(1), 0) if m else None

def code(txt):
    """The source with its comments and string literals taken out. A check that reads prose finds
    what the prose talks ABOUT - this file's own header mentions the p_choice menu the window
    replaced, which is not the same as the window calling one."""
    out = []
    for line in txt.split('\n'):
        out.append(re.sub(r'"[^"]*"', '""', line).split('//')[0])
    return '\n'.join(out)

def nocom(txt):
    """The source with only its comments taken out. code() also blanks string literals, which is
    right for "does this call p_choice" and wrong for "what does this string interpolate"."""
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

def coms(txt):
    out, cur = {}, None
    for line in txt.split('\n'):
        line = line.split('//')[0].strip()
        if not line: continue
        if line.startswith('[') and line.endswith(']'):
            cur = {}; out[line[1:-1]] = cur; continue
        if cur is None or '=' not in line: continue
        k, v = line.split('=', 1)
        cur[k] = v
    return out

def rows(name):
    body = ENUMS.split('[' + name + ']', 1)[1].split('\n[', 1)[0]
    return dict(re.findall(r'^val=([^,\n]+),(.*)$', body, re.M))

COM = coms(IF)
TABS = ['Unlock', 'Extend', 'Buy', 'Tasks', 'Cosmetics']

# ============================================================================ 1
print('1. the window exists, and every piece of it is registered')
check(len(COM) == 150, 'the interface has %d components' % len(COM))
pack = {}
for line in read('pack/interface.pack').split('\n'):
    if '=' in line:
        i, n = line.split('=', 1)
        pack[n.strip()] = int(i)
check('slayer_rewards' in pack, 'slayer_rewards has an id in interface.pack (%s)' % pack.get('slayer_rewards'))
missing = [n for n in COM if 'slayer_rewards:' + n not in pack]
check(not missing, 'and so does every component: %s' % (missing[:3] or 'all %d' % len(COM)))
order = [int(l) for l in read('pack/interface.order').split('\n') if l.strip()]
ids = set(pack.values())
check(set(order) <= ids, 'interface.order names nothing that is not in the pack')
mine = [pack['slayer_rewards:' + n] for n in COM] + [pack['slayer_rewards']]
check(set(mine) <= set(order), 'and the whole window is in the order, or the client would not load it')
check(len(set(mine)) == len(mine), 'no id is used twice')

# ============================================================================ 2
print('2. it is the five OSRS tabs, in OSRS\'s order')
for i, name in enumerate(TABS):
    check('tab%d' % i in COM and COM['tab%d' % i].get('text') == name,
          'tab %d is %s' % (i, name))
    check(COM['tab%d' % i].get('buttontype') == 'normal', '  and it is clickable')
    check('tab%dfill' % i in COM and COM['tab%dfill' % i].get('fill') == 'yes',
          '  with a fill behind it that marks the open tab')
check(const('slayer_tab_count') == len(TABS), 'and ^slayer_tab_count agrees there are %d' % len(TABS))
for n, i in (('unlock', 0), ('extend', 1), ('buy', 2), ('tasks', 3), ('cosmetics', 4)):
    check(const('slayer_tab_' + n) == i, '^slayer_tab_%s is %d, the column it is drawn in' % (n, i))

# ============================================================================ 3
print('3. the list is long enough that no tab ever needs a second page')
nrows = len([n for n in COM if re.fullmatch(r'row\d+', n)])
counts = {'Unlock': len(rows('slayer_unlock_name')), 'Extend': len(rows('slayer_extend_name')),
          'Buy': len(rows('slayer_buy_obj')), 'Tasks': const('slayer_task_rows'), 'Cosmetics': 0}
# VALUES AFTER THE CLAIM, NOT INSIDE IT. A mutation's label is the wording of the check it is
# written for, so a number in the middle of a claim changes the wording the moment the number
# changes - and the label stops matching. Four labels in this file were unmatchable for
# exactly that reason, and tools/mutate_labels.py is what found them.
check(nrows >= max(counts.values()),
      'the window has a row for every entry the longest tab needs: %d rows, %d wanted by %s'
      % (nrows, max(counts.values()), max(counts, key=counts.get)))
check(all(COM['row%d' % i].get('type') == 'layer' for i in range(nrows)),
      'every row is a layer, which is the only thing if_sethide works on')
for i in range(nrows):
    check(COM['r%dbox' % i].get('option') == 'Select',
          'row %d carries one option, on the rect rather than on either label' % i) if i == 0 else None
opts = [n for n in COM if 'option' in COM[n]]
check(len(opts) == nrows, 'exactly %d components carry an option - one per row' % nrows)

# ============================================================================ 4
print('4. every string the window shows fits the component it is drawn in')
import ifrender
def width(s, font):
    return ifrender.font(font).width(re.sub(r'@\w{3}@', '', s))
bad = []
for tbl, comp in (('slayer_unlock_desc', 'desc0'), ('slayer_buy_desc', 'desc0')):
    w = int(COM[comp]['width'])
    f = COM[comp].get('font', 'p12_full')
    for k, v in rows(tbl).items():
        if width(v, f) > w:
            bad.append((tbl, k, width(v, f), w))
check(not bad, 'every description line is inside the %dpx panel: %s'
      % (int(COM['desc0']['width']), bad[:2] or 'all %d of them'
         % (len(rows('slayer_unlock_desc')) + len(rows('slayer_buy_desc')))))
namew = int(COM['r0name']['width'])
bad = [(n, width(n, 'p12_full')) for n in list(rows('slayer_unlock_name').values())
       + list(rows('slayer_extend_name').values()) if width(n, 'p12_full') > namew]
check(not bad, 'every reward name is inside the %dpx name column: %s' % (namew, bad[:2] or 'all of them'))
costw = int(COM['r0cost']['width'])
widest = max(width('%d points' % int(c), 'p12_full')
             for c in list(rows('slayer_unlock_cost').values()) + list(rows('slayer_extend_cost').values())
             + list(rows('slayer_buy_cost').values()))
check(widest <= costw, 'the widest price (%dpx) fits the %dpx price column' % (widest, costw))
check(width('unlocked', 'p12_full') <= costw, 'and so does the word it shows instead when you own one')
# two lines per description, which is what ^slayer_desc_lines promises
for tbl in ('slayer_unlock_desc', 'slayer_buy_desc'):
    keys = sorted(int(k) for k in rows(tbl))
    per = {}
    for k in keys: per.setdefault(k // 3, []).append(k % 3)
    check(all(v == [0, 1] for v in per.values()),
          '%s is exactly two lines per entry, as ^slayer_desc_lines says' % tbl)
check(const('slayer_desc_lines') == 2, 'and that constant is 2')
# Cosmetics holds the two helmet recolour unlocks - the tab OSRS keeps them in.
cos_name, cos_bit, cos_cost = rows('slayer_cosmetic_name'), rows('slayer_cosmetic_bit'), rows('slayer_cosmetic_cost')
check(list(cos_name.values()) == ['Unholy Helmet', 'Kalphite Khat'],
      'Cosmetics is the two recolour unlocks: %s' % list(cos_name.values()))
check(sorted(int(v) for v in cos_bit.values()) == [5, 6],
      'on bits 5 and 6, which is what slayer_helm_colours.rs2 reads')
check(all(int(v) == 1000 for v in cos_cost.values()),
      "at OSRS's 1,000 points each")
colours = read('scripts/skill_slayer/scripts/slayer_helm_colours.rs2')
check('~slayer_has_unlock(5)' in colours and '~slayer_has_unlock(6)' in colours,
      'and the recolour itself still asks for those two bits')
desc = WIN.split('[proc,slayer_ui_desc]', 1)[1].split('\n[', 1)[0]
check('slayer_cosmetic_desc' in desc, 'the tab describes its two rows')
take = WIN.split('[proc,slayer_ui_take]', 1)[1].split('\n[', 1)[0]
check('~slayer_buy_cosmetic' in take, 'and Confirm buys the unlock')
check('available yet' not in code(WIN),
      'nothing in the window still says the recolours are missing')

# ============================================================================ 5
print('5. the four browns are the same in the interface and in the script')
for name, com, key in (('slayer_ui_row_off', 'r0box', 'colour'),
                       ('slayer_ui_tab_off', 'tab0fill', 'colour')):
    check(int(COM[com][key], 0) == const(name),
          '^%s is the colour the .if paints %s with: 0x%06X' % (name, com, const(name)))
check(const('slayer_ui_row_on') != const('slayer_ui_row_off'), 'a selected row is a different brown')
check(const('slayer_ui_tab_on') != const('slayer_ui_tab_off'), 'and so is the open tab')
for c in ('slayer_ui_row_on', 'slayer_ui_row_off', 'slayer_ui_tab_on', 'slayer_ui_tab_off'):
    check("^%s" % c in WIN, '^%s is read by the window script' % c)
check('if_setcolour' in UI, 'and the draw paints them with if_setcolour')
check('0x4A3F31' in GEN and '0x3E3529' in GEN,
      'the generator holds the dark halves, since they are what the interface is written with')

# ============================================================================ 6
print('6. one opening of the window cannot run out of instructions')
clicks, per = const('slayer_ui_clicks'), const('slayer_ui_click_ops')
check(clicks > 0 and per > 0, 'both numbers are recorded: %d clicks at %d opcodes' % (clicks, per))
check(clicks * per < 400000,
      'and their product is inside the 500,000 opcodes a script gets: %d x %d is %s'
      % (clicks, per, format(clicks * per, ',')))
loop = WIN.split('[proc,slayer_rewards_window]', 1)[1].split('\n[', 1)[0]
check('while ($clicks < ^slayer_ui_clicks)' in loop, 'the loop is bounded by that constant')
check('while (true)' not in WIN, 'and is not a while(true), which would hang the player script')
check('p_pausebutton' in loop and 'if_close' in loop, 'it waits for a click and closes on the way out')
draw = UI.split('[proc,slayer_ui_draw]', 1)[1].split('\n[', 1)[0]
check(draw.count('~slayer_ui_row') == 11, 'a redraw paints all eleven rows')
check('enum_getoutputcount' not in draw, 'and the draw itself counts nothing it can be told')

# ============================================================================ 7
print('7. the masters open it, and the chat menu it replaced is gone')
check('~slayer_rewards_window' in MASTER, 'a master\'s "spend my Slayer points" opens the window')
check('@slayer_master_rewards' not in MASTER, 'and no longer jumps to the old chat menu')
for gone in ('slayer_master_rewards', 'slayer_rewards_unlocks', 'slayer_rewards_extends',
             'slayer_rewards_buy', 'slayer_rewards_cancel', 'slayer_rewards_block',
             'slayer_rewards_unblock'):
    check('[label,%s]' % gone not in REW + PTS, 'the %s label is gone, not just unused' % gone)
WINCODE = code(WIN)
check('p_choice' not in WINCODE, 'the window asks nothing through the chat box')
for p in ('~chatnpc', '~chatplayer'):
    check(p not in WINCODE, 'and says nothing as the npc (%s)' % p)

# ============================================================================ 8
print('8. buying something still goes through the one proc that owns the effect')
take = WIN.split('[proc,slayer_ui_take]', 1)[1].split('\n[', 1)[0]
for proc in ('~slayer_buy_unlock', '~slayer_buy_extend', '~slayer_buy_item', '~slayer_do_task'):
    check(proc in take, 'Confirm reaches %s' % proc)
check('%slayer_points < $cost' in take,
      'and Confirm compares the points against the cost at all')
if '%slayer_points < $cost' in take and '~slayer_buy_unlock' in take:
    check(before(take, '%slayer_points < $cost', '~slayer_buy_unlock'),
          'and it checks the points before it reaches any of them')
check('~slayer_ui_owned($tab, $sel) = true' in take, 'and refuses what you already own')
check(REW.count('%slayer_points = sub(') == 4 and PTS.count('%slayer_points = sub(') == 2,
      'points are spent in six places: unlock, cosmetic, extend, item, cancel, block - the imbue '
      'was the seventh until it became a Scroll of imbuing drop')
check('setbit(%slayer_unlocks' in REW and 'setbit(%slayer_extends' in REW,
      'the unlock and the extend are the bits they always were')
bits = rows('slayer_unlock_bit')
check(sorted(int(v) for v in bits.values()) == [0, 1, 2, 3, 4],
      'the five unlocks own five distinct bits: %s' % sorted(int(v) for v in bits.values()))
check(bits['0'] == '4', "and Bigger and Badder is still bit 4, which is what superiors.rs2 reads")

# ============================================================================ 9
print('9. the rewards themselves are OSRS\'s, and every row can answer for itself')
WIKI = {'Bigger and Badder': 50, 'Gargoyle Smasher': 120, 'Slug Salter': 10,
        'Reptile Freezer': 10, 'Ring Bling': 150}
names, costs = rows('slayer_unlock_name'), rows('slayer_unlock_cost')
got = {names[k]: int(costs[k]) for k in names}
check(got == WIKI, 'the five unlock prices are the wiki\'s: %s' % (got if got != WIKI else 'all five'))
# The rune pouch is 750 points from a slayer master in OSRS, the same as the herb sack, so it
# belongs in this list rather than as an exception to it.
BUY = {'slayer_ring_8': 75, 'herb_sack': 750, 'looting_bag': 10, 'rune_pouch': 750}
bobj, bcost = rows('slayer_buy_obj'), rows('slayer_buy_cost')
# .get, not [k]: a row with an obj and no price is a real mistake and the check below is what says
# so, and this line crashing instead was the eighth time in this repo that a battery answered a
# mutation with a traceback. A crash is not a catch - it says nothing about which claim broke.
got = {bobj[k]: int(bcost[k]) for k in bobj if k in bcost}
check(got == BUY, 'and so are the four things you can buy: %s'
      % ('all four' if got == BUY else got))
objp = {n.strip(): int(i) for i, n in
        (l.split('=', 1) for l in read('pack/obj.pack').split('\n') if '=' in l)}
bad = [o for o in bobj.values() if o not in objp]
check(not bad, 'each of which is a real obj: %s' % (bad or ', '.join(bobj.values())))
# EVERY BUY ROW IS AN ITEM NOW. The imbue was row 3 and was the only row that handed over no obj -
# it needed a name table of its own, an ^slayer_buy_imbue row number, and a special case in
# ~slayer_ui_name. The imbue is a Scroll of imbuing drop now (poh_battery group 66), so all three
# are gone, and this is the check that they stay gone rather than growing back one at a time.
check(sorted(int(k) for k in bcost) == sorted(int(k) for k in bobj)
      and sorted(int(k) for k in bcost) == list(range(len(BUY))),
      'the Buy tab is keyed 0..%d with no gap and every row has both an obj and a price - a gap '
      'draws a blank row, because the tab counts its rows with enum_getoutputcount' % (len(BUY) - 1))
check('slayer_buy_name' not in ENUMS and 'slayer_buy_imbue' not in CONST
      and '~slayer_ui_buy_name' not in WIN,
      'and no row is a service: the name table, the row constant and the special case that read '
      'them are all gone with the points imbue')
check(const('slayer_cancel_cost') == 30 and const('slayer_block_cost') == 100,
      'cancelling is 30 points and blocking 100, as they were before the window')
check(const('slayer_task_rows') == 6, 'the Tasks tab is cancel, block and four block slots')
for tbl in ('slayer_unlock_name', 'slayer_unlock_cost', 'slayer_unlock_bit'):
    check(sorted(int(k) for k in rows(tbl)) == list(range(len(WIKI))),
          '%s is keyed 0..%d with no gap' % (tbl, len(WIKI) - 1))

# Every price the window can show has to be spelled by a table: the engine has no digit grouping,
# so tostring would draw "1000 points" where OSRS draws "1,000 points".
def grouped(n): return '{:,}'.format(n)
prices = set()
for tbl in ('slayer_unlock_cost', 'slayer_extend_cost', 'slayer_buy_cost', 'slayer_cosmetic_cost'):
    prices |= {int(v) for v in rows(tbl).values()}
for c in ('slayer_cancel_cost', 'slayer_block_cost'):
    prices.add(const(c))
spell = rows('slayer_cost_text')
missing = sorted(p for p in prices if str(p) not in spell)
check(not missing, 'every price the window can show has a slayer_cost_text row: %s'
      % (missing or '%d prices' % len(prices)))
wrong = sorted('%s->%s' % (p, spell[str(p)]) for p in prices
               if str(p) in spell and spell[str(p)] != grouped(p))
check(not wrong, 'and each one is that number with its thousands separator: %s'
      % (wrong or 'up to ' + grouped(max(prices))))
check(any(',' in v for v in spell.values()),
      'at least one of them actually needs the separator, or the table proves nothing')
ct = nocom(WIN).split('[proc,slayer_ui_cost_text]', 1)[1].split('\n[', 1)[0]
check('slayer_cost_text' in ct and 'tostring' not in ct,
      'and ~slayer_ui_cost_text reaches for the table, not tostring')

# ============================================================================ 10
print('10. the generator still produces exactly what is checked in')
import subprocess
kept = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/skill_slayer/interfaces/slayer_rewards.if',
    'scripts/skill_slayer/scripts/slayer_ui.rs2',
    'scripts/skill_slayer/configs/slayer_rewards.enum',
    'pack/interface.pack', 'pack/interface.order']}
r = subprocess.run([sys.executable, os.path.join(C, 'tools/genslayerui.py')],
                   capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/genslayerui.py runs clean'
      + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
fresh = {f: open(os.path.join(C, f), 'rb').read() for f in kept}
moved = [os.path.basename(f) for f in kept if fresh[f] != kept[f]]
for f in kept:
    if fresh[f] != kept[f]:
        open(os.path.join(C, f), 'wb').write(kept[f])
check(not moved, 're-running it changes nothing: %s' % (moved or 'byte-identical'))
# The same trap genmenus.py fell into: HEAD is one entry of the line list holding many lines, so a
# writer that joins straight onto nl leaves those newlines LF on Windows and the file goes out
# mixed - invisible to git and to any Linux run. Two checks, because the first cannot fire here.
mixed = [os.path.basename(f) for f, b in fresh.items()
         if b.count(b'\r\n') and b.count(b'\n') - b.count(b'\r\n')]
check(not mixed, 'and every file it writes has one kind of line ending: %s'
      % (mixed or 'all %d uniform' % len(fresh)))
check("body = nl.join(src).replace('\\r\\n', '\\n')" in GEN,
      'the writer normalises before it converts, which is what keeps that true')
check('genmenus' in GEN and 'G.repack' in GEN,
      'and it shares genmenus\' frame and its interface ids rather than copying either')
# ============================================================================ 11
print('11. no master can hand out a task that nothing in the game counts')
# THE CHECK THAT WOULD HAVE CAUGHT THE DUST DEVIL. A kill counts towards a task through ONE route:
# npc_death reads param=slayer_category off the npc it killed. Nothing in the task tables knows
# whether such an npc exists and nothing in the npc configs knows whether a master gives the task,
# so the two drifted apart: finishing Desert Treasure opened the dust devil task while the nineteen
# dust devils carried no category at all, and the five Slayer Tower mages carried category= - a
# different field, which counts for nothing. Three masters each gave a task that could not be done.
#
# So: every task a master can hand out either has a monster that counts AND is spawned somewhere, or
# is refused outright in validate_slayer_target. The third state - assignable and impossible - is
# what this group exists to stop anybody checking in again.
TASK = read('scripts/skill_slayer/scripts/slayer_task.rs2')
MASTER_ROWS = read('scripts/skill_slayer/configs/slayer_master_tasks.dbrow')
TASK_ROWS = read('scripts/skill_slayer/configs/slayer_tasks.dbrow')

row_task = {}
cur = None
for line in nocom(TASK_ROWS).splitlines():
    line = line.strip()
    if line.startswith('['):
        cur = line[1:-1]
    elif line.startswith('data=task,') and cur:
        row_task[cur] = line.split(',', 1)[1].strip()
assigned = {}
cur = None
for line in nocom(MASTER_ROWS).splitlines():
    line = line.strip()
    if line.startswith('['):
        cur = line[1:-1].split('_task_table')[0]
    elif line.startswith('data=task,') and cur:
        t = row_task.get(line.split(',', 1)[1].strip())
        if t:
            assigned.setdefault(t, set()).add(cur)
check(len(assigned) > 50, 'the five tables between them hand out %d different tasks' % len(assigned))

# what carries each category, and whether any of it is actually spawned on a map
name2id = {}
for line in read('pack/npc.pack').splitlines():
    if '=' in line:
        i, n = line.split('=', 1)
        name2id[n.strip()] = int(i)
spawned_ids = set()
mapdir = os.path.join(C, 'maps')
spawn_line = re.compile(r'^\s*\d+\s+\d+\s+\d+\s*:\s*(\d+)')
for f in os.listdir(mapdir):
    if not f.endswith('.jm2'):
        continue
    txt = open(os.path.join(mapdir, f), newline='').read()
    if '==== NPC ====' not in txt:
        continue
    sec = re.split(r'(?m)^====', txt.split('==== NPC ====', 1)[1])[0]
    for line in sec.splitlines():
        m = spawn_line.match(line)
        if m:
            spawned_ids.add(int(m.group(1)))
tagged, live = {}, {}
for root, _dirs, files in os.walk(os.path.join(C, 'scripts')):
    for f in files:
        if not f.endswith('.npc'):
            continue
        txt = open(os.path.join(root, f), newline='').read().replace('\r\n', '\n')
        for block in re.split(r'(?m)^\[', txt)[1:]:
            nm = block.split(']', 1)[0]
            m = re.search(r'(?m)^param=slayer_category,(\S+)', block.split(']', 1)[1])
            if m:
                tagged.setdefault(m.group(1).strip(), []).append(nm)
                if name2id.get(nm) in spawned_ids:
                    live.setdefault(m.group(1).strip(), []).append(nm)
check(len(spawned_ids) > 500 and sum(len(v) for v in tagged.values()) > 200,
      'read %d spawned npc kinds and %d tagged monsters to hold them against'
      % (len(spawned_ids), sum(len(v) for v in tagged.values())))

# a task refused for every player: "case ^x[, ^y] : return (false);" with nothing in between
VALIDATE = nocom(TASK).split('[proc,validate_slayer_target]', 1)[1].split('\n[', 1)[0]
blocked = set()
for case, body in re.findall(r'case ([^:]+):((?:(?!\n    case |\n\}).)*)', VALIDATE, re.S):
    if body.strip().startswith('return (false)'):
        blocked.update(t.strip() for t in case.split(',') if t.strip().startswith('^'))
check(len(blocked) >= 3, 'validate_slayer_target refuses %d tasks outright: %s'
      % (len(blocked), ', '.join(sorted(b[1:] for b in blocked))))

impossible = sorted(t[1:] for t in assigned if t not in tagged and t not in blocked)
check(not impossible, 'every task a master gives has a monster that counts: %s'
      % (', '.join(impossible) or 'all %d' % len(assigned)))
# The wall beast is the one monster with no map spawn by design - the crevices spawn it
# (skill_slayer/scripts/npcs/wall_beast.rs2), which is why it is named here rather than skipped.
unspawned = sorted(t[1:] for t in assigned
                   if t in tagged and t not in live and t not in blocked and t != '^slayer_wallbeast')
check(not unspawned, 'and one that is somewhere to be found: %s'
      % (', '.join(unspawned) or 'all of them'))
# Spawned is not the same as reachable, and the dark beast is the one that proves it: eleven of
# them stand in the Mourning's End Part II slave mines, whose locs have no handler, so there is
# no way in. It is named here rather than quietly skipped, so that when the mines open and
# somebody takes the refusal out, this line is the next thing to go.
walled_in = {'^slayer_darkbeast'}
pointless = sorted(t[1:] for t in blocked if t in live and t not in walled_in)
check(not pointless, 'and nothing is refused that would have worked: %s'
      % (', '.join(pointless) or 'none'))

# ============================================================================ 12
print('12. the Rewards right-click, on every master')
NPCS = read('scripts/_unpack/377/all.npc')
missing = []
for i in range(1, 6):
    block = NPCS.split('[slayer_master_%d]' % i, 1)[1].split('\n[', 1)[0]
    if 'op3=Rewards' not in block:
        missing.append('slayer_master_%d' % i)
check(not missing, 'all five masters carry the option: %s' % (', '.join(missing) or 'Turael to Duradel'))
check('[opnpc3,_slayer_master] ~slayer_rewards_window;' in nocom(MASTER),
      'op3 opens the same window the chat line opens, for the category rather than one npc at a time')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
