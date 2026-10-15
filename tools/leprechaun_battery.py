"""Battery for the bigger bank and the tool leprechaun's store.

Two things in one round because they are the same thing twice: a store that outgrew the shape it
was kept in. The bank outgrew a 5000-byte packet buffer and the leprechaun outgrew three bits per
tool. So group 1-4 are the bank and group 5-9 are the leprechaun.

WHAT THIS CHECKS THAT NOTHING ELSE DOES. tools/leprechaun_sim.py models the BEHAVIOUR (conservation,
caps, placeholders) and engine/tools/invfullcheck.ts runs the real encoder against the real packed
configs. This checks the things neither can see: that the numbers are OSRS's rather than convenient
(tools/leprechaunspec.json, written from the wiki before any of it was built), that the interface
and the packs agree, that the dialogue reaches the new window and the old store is gone, and that
the engine and client halves of the bank change are both actually there - the client is a separate
repo, so the only thing this can check about it is the source, which is exactly the thing that
silently does not get changed.

    python3 tools/leprechaun_battery.py [path/to/Engine-TS] [path/to/Client-Java]
"""
import json, math, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(C), 'engine')
# THE CLIENT CLONE IS 'javaclient' HERE, and 'client' was a guess that never matched: this check
# has reported "pass its path as argv[2]" rather than looking at the client since it was written.
# Both names are tried, and LOSTCITY_CLIENT wins over either, the same shape poh_battery uses for
# the engine clone.
CLIENT = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('LOSTCITY_CLIENT') or next(
    (os.path.join(os.path.dirname(C), _n) for _n in ('javaclient', 'client')
     if os.path.isdir(os.path.join(os.path.dirname(C), _n))),
    os.path.join(os.path.dirname(C), 'client'))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')
def readat(root, p):
    f = os.path.join(root, p)
    return open(f, newline='').read().replace('\r\n', '\n') if os.path.exists(f) else None

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt): return '\n'.join(l.split('//')[0] for l in txt.split('\n'))
def block(txt, n):
    return txt.split('[' + n + ']', 1)[1].split('\n[', 1)[0] if '[' + n + ']' in txt else ''
def const(txt, n):
    # a trailing // comment is allowed on a constant line, and several of the bank's carry one
    m = re.search(r'(?m)^\^' + n + r' = (\d+)\s*(?://.*)?$', txt)
    return int(m.group(1)) if m else None

SPEC = json.load(open(os.path.join(C, 'tools/leprechaunspec.json')))

BANKC = read('scripts/interface_bank/configs/bank.constant')
BANKIF = read('scripts/interface_bank/interfaces/bank_main.if')
BANKRS = read('scripts/interface_bank/scripts/bank.rs2')
GENTABS = read('tools/genbanktabs.py')
SIM = read('tools/banktab_sim.py')
LCONST = read('scripts/skill_farming/configs/leprechaun.constant')
LINV = read('scripts/skill_farming/configs/leprechaun.inv')
LENUM = read('scripts/skill_farming/configs/leprechaun.enum')
LRS = read('scripts/skill_farming/scripts/leprechaun.rs2')
LIF = read('scripts/skill_farming/interfaces/leprechaun_window.if')
NPCS = read('scripts/skill_farming/scripts/farming_npcs.rs2')
FVARP = read('scripts/skill_farming/configs/farming.varp')
IPACK = read('pack/interface.pack')
IORDER = read('pack/interface.order')
ALLOBJ = read('scripts/_unpack/377/all.obj')
OSRSOBJ = read('scripts/general/configs/osrs_items.obj')
CBOBJ = read('scripts/skill_farming/configs/compost_bucket.obj')
DECLARED = set(re.findall(r'(?m)^\[(\w+)\]$', ALLOBJ + OSRSOBJ + CBOBJ))

# ============================================================================ 1
print("1. the bank is OSRS's size, and the free limit is OSRS's too")
TOTAL = const(BANKC, 'bank_total_slots')
FREE = const(BANKC, 'bank_free_slots')
check(TOTAL == 1410,
      'a members bank is 1410 spaces - 900 base, 60 for the security features, 450 purchased (%s)' % TOTAL)
check(FREE == 910, 'and a free one is 910 - 400 + the same 60 + the same 450 (%s)' % FREE)
check('size=^bank_total_slots' in block(read('scripts/interface_bank/configs/bank.inv'), 'bank'),
      'the inv is sized by the constant, not by a number written twice')
gate = code(block(BANKRS, 'proc,bank_check_nobreak'))
check('playermember = ^false' in gate and '^bank_free_slots' in gate,
      'the free limit is a check on playermember, not a second inv - an inv size is static and '
      'cannot differ per player')
check('inv_size(bank), inv_freespace(bank)) >= ^bank_free_slots' in gate,
      '...and it counts slots in use rather than trusting a running total')

# ============================================================================ 2
print('2. the grid has a square for every slot, including the padding the tabs waste')
# THE COLUMN COUNT IS READ, NOT REMEMBERED. It was 8 when this was written and the grid is 12
# wide now, which moved the worst-case tab padding from 56 cells to 88 and the row count from 184
# to 125 - so a remembered 8 had this section arguing with a grid that was right. It comes out of
# tools/bankgeom.py, which is where genbanktabs.py gets it, and the interface is checked to agree
# with that rather than with a number here. tools/banktab_sim.py reads it off the interface for the
# same reason and says so in its own docstring.
TABS = const(read('scripts/interface_bank/configs/bank.constant'), 'bank_tabs')
grid = block(BANKIF, 'bank')
W = int(re.search(r'(?m)^COLS = (\d+)$', read('tools/bankgeom.py')).group(1))
rows = int(re.search(r'(?m)^height=(\d+)$', grid).group(1))
pad = TABS * (W - 1)
check(int(re.search(r'(?m)^width=(\d+)$', grid).group(1)) == W,
      'the grid is as many columns as bankgeom.py says, which is what the generator wrote: %d' % W)
check(rows == math.ceil((TOTAL + pad) / W),
      'and ceil((%d + %d) / %d) = %d rows, which is what the generator computes (%d)'
      % (TOTAL, pad, W, math.ceil((TOTAL + pad) / W), rows))
check(rows * W >= TOTAL + pad,
      'so all %d slots stay reachable with eight maximally ragged tabs: %d cells for %d + %d'
      % (TOTAL, rows * W, TOTAL, pad))
check('GRID_ROWS = -(-(bank_slots() + SLOT_PAD) // GRID_W)' in GENTABS,
      'the row count is DERIVED from ^bank_total_slots, so the two cannot drift')
bs = GENTABS.split('def bank_slots()', 1)[1].split('\ndef ', 1)[0]
# comments stripped: the generator's own notes are allowed to SAY 1410; what must not be there is
# the number as code, where it would be a second source of truth
gencode = '\n'.join(l.split('#')[0] for l in GENTABS.split('\n'))
check('bank.constant' in bs and re.search(r'\b%d\b' % TOTAL, gencode) is None,
      '...by reading bank.constant inside bank_slots(), and the size appears nowhere in the '
      'generator as a literal - which is the only version of this the generator cannot fake')
layer = block(BANKIF, 'com_92')
scroll = int(re.search(r'(?m)^scroll=(\d+)$', layer).group(1))
margin = re.search(r'(?m)^margin=(\d+),(\d+)$', grid)
pitch = int(margin.group(2)) + 32
check(scroll == rows * pitch,
      'the layer can be scrolled to the last row: scroll %d = %d rows x %d (%d)'
      % (rows * pitch, rows, pitch, scroll))
# _grid_rows() became _grid(key), which reads the column count as well as the row count - the
# change the grid's widening needed and the one this check had not followed.
check("SIZE = _const('bank_total_slots')" in SIM and "def _grid(key)" in SIM
      and "_grid('width')" in SIM and "_grid('height')" in SIM,
      'banktab_sim.py reads all three numbers out of the configs - a sim carrying its own 352 '
      'slots, or its own 8 columns, would have gone on passing after the bank grew')

# ============================================================================ 3
print('3. the packet the bigger bank has to fit through')
ENC = readat(ENGINE, 'src/network/game/server/codec/UpdateInvFullEncoder.ts')
SOCK = readat(ENGINE, 'src/server/ClientSocket.ts')
CLI = readat(CLIENT, 'src/main/java/jagex2/client/Client.java')
if ENC is None or SOCK is None:
    check(False, 'the engine repo is not beside content - pass its path as argv[1]')
else:
    check('for (let slot = capacity - 1; slot >= 0; slot--)' in ENC and 'return slot + 1;' in ENC,
          'UPDATE_INV_FULL transmits up to the last OCCUPIED slot, not the whole component')
    check('todo: size should be the index of the last non-empty slot' not in ENC,
          "...which was the encoder's own todo, so the todo is gone")
    check('length += 4;' in ENC,
          "test() counts the four header bytes encode() writes (p2 component, p2 size), not three")
    check(re.search(r'(?m)^\s*out = Packet\.alloc\(2\);', SOCK) is not None,
          "ClientSocket.out is alloc(2) = 30000 bytes: 1410 slots at 7 bytes each is 9873, and "
          "Packet's writes go through DataView, which throws past the end rather than wrapping")
if CLI is None:
    check(False, 'the client repo is not beside content - pass its path as argv[2]')
else:
    check(re.search(r'public Packet in = Packet\.alloc\(2\);', CLI) is not None,
          'and the client reads a whole variable-length packet into Packet.alloc(2) to match - '
          'BOTH ends, or the bank crashes whichever one was left at 5000')
    check('invSlotObjId[var112] = 0' in CLI.replace(' ', '').replace('var108.', '')
          or 'invSlotObjId[var112] = 0' in CLI,
          'the trim is safe because the client already zeroes every slot past the transmitted '
          'size, so a short transmit clears the tail instead of leaving stale icons')

# ============================================================================ 4
print('4. the two bank generators stopped growing the file')
for g in ('tools/genbanktabs.py', 'tools/genbankbar.py'):
    src = read(g)
    check("re.sub(r'\\n*' + re.escape(MARK_A)" in src,
          '%s eats the blank lines its block sat behind, so a round trip is a no-op rather than '
          'two more blank lines' % os.path.basename(g))

# ============================================================================ 5
print("5. the leprechaun's capacities are OSRS's, item by item")
SLOTS = const(LCONST, 'leprechaun_slots')
check(SLOTS == len(SPEC['store']),
      '%d slots, one per thing the wiki says he holds (%s)' % (len(SPEC['store']), SLOTS))
slotmap = code(block(LRS, 'proc,leprechaun_slot'))
slotmap = re.sub(r',\s*\n\s*', ', ', slotmap)
capmap = re.sub(r',\s*\n\s*', ', ', code(block(LRS, 'proc,leprechaun_cap')))
accepted = {}
for objs, tag in re.findall(r'(?m)^\s*case ([^:]+?)\s*:\s*return\(\^leprechaun_slot_(\w+)\);', slotmap):
    for o in objs.split(','):
        accepted[o.strip()] = const(LCONST, 'leprechaun_slot_' + tag)
caps = {}
for names, cap in re.findall(r'(?m)^\s*case ([^:]+?)\s*:\s*return\(\^leprechaun_cap_(\w+)\);', capmap):
    if names.strip() == 'default':
        continue
    for n in names.split(','):
        caps[const(LCONST, n.strip().lstrip('^'))] = const(LCONST, 'leprechaun_cap_' + cap)
dflt = const(LCONST, 'leprechaun_cap_' + re.search(r'case default : return\(\^leprechaun_cap_(\w+)\);', capmap).group(1))
def cap_of(slot): return caps.get(slot, dflt)

for row in SPEC['store']:
    name, slot, want = row['obj'], row['slot'], row['cap']
    check(accepted.get(name) == slot,
          '%s is slot %d (%s)' % (name, slot, accepted.get(name)))
    # the obj leads and the numbers trail, so this check has the SAME NAME whether it is the spec
    # or the code that was changed - a message that led with the expected number could not be
    # attributed to itself after a spec mutation
    check(cap_of(slot) == want,
          "%s: the cap is the wiki's number (spec %d, code %s)" % (name, want, cap_of(slot)))
check(sorted(set(accepted.values())) == list(range(SLOTS)),
      'the switch reaches every slot and invents none: %s' % sorted(set(accepted.values())))
check(const(LCONST, 'leprechaun_cap_tool') == 100
      and const(LCONST, 'leprechaun_cap_supply') == 1000
      and const(LCONST, 'leprechaun_cap_single') == 1,
      'the three caps are 100, 1000 and 1 and nothing else')

# the two the wiki lists that are NOT here, and the reason has to be that they do not exist
for missing in SPEC['not_in_this_cache']:
    hits = [n for n in DECLARED if missing.replace('gricollers_can', 'gricoller') in n]
    check(not hits,
          'no %s obj exists in this cache, so leaving its slot out is forced rather than lazy'
          % missing)
    check(missing not in accepted, '...and nothing pretends to accept one')

# ============================================================================ 6
print('6. the store is an inv, and the window is that inv')
inv = block(LINV, 'leprechaun_store')
check('scope=perm' in inv, "the store is perm - it is the player's, and he holds it everywhere")
check('stackall=yes' in inv,
      'and stackall, because a hundred rakes do not stack on their own and the COUNT is the answer')
check('size=^leprechaun_slots' in inv, 'sized by the constant')
check('415=leprechaun_store' in read('pack/inv.pack'),
      'registered in pack/inv.pack, or the packer never sees it')
grid = block(LIF, 'store')
check(int(re.search(r'(?m)^width=(\d+)$', grid).group(1))
      * int(re.search(r'(?m)^height=(\d+)$', grid).group(1)) == SLOTS,
      'the grid has exactly %d squares' % SLOTS)
check('type=inv' in grid,
      'it is an inv component, so the client draws the icons, the counts and the faded '
      'placeholders for nothing')
for i, word in enumerate(('Withdraw-1', 'Withdraw-5', 'Withdraw-10', 'Withdraw-all',
                          'Withdraw-as-note'), start=1):
    check('option%d=%s' % (i, word) in grid, 'option %d is %s' % (i, word))
    check('[inv_button%d,leprechaun_window:store]' % i in LRS, '...and inv_button%d handles it' % i)
check('[if_button,leprechaun_window:depositall]' in LRS
      and 'buttontype=normal' in block(LIF, 'depositall'),
      "Deposit-everything is a button, which is OSRS's Deposit-all")
check('inv_transmit(leprechaun_store, leprechaun_window:store)' in LRS
      and '[if_close,leprechaun_window]' in LRS and 'inv_stoptransmit' in LRS,
      'the inv is transmitted on open and the transmit is stopped on close')
names = ['leprechaun_window'] + ['leprechaun_window:%s' % n
                                 for n in re.findall(r'(?m)^\[(\w+)\]$', LIF)]
packed = dict(l.split('=', 1)[::-1] for l in IPACK.split('\n') if l)
missing = [n for n in names if n not in packed]
check(not missing, 'every component is in pack/interface.pack (%s)' % (missing[:3] or 'all %d' % len(names)))
order = set(l.strip() for l in IORDER.split('\n') if l.strip())
check(all(packed[n] in order for n in names if n in packed),
      'and every one of them is in pack/interface.order - an id in one and not the other packs a '
      'component with type -1 and the client throws on load')

# ============================================================================ 7
print('7. the placeholders, which are what keeps the window readable and the slots canonical')
ph = dict(re.findall(r'(?m)^val=(\d+),(\S+)$', LENUM))
check(len(ph) == SLOTS, 'the enum has a row per slot (%d)' % len(ph))
check(all(ph[str(r['slot'])] == r['obj'] for r in SPEC['store']),
      "and each row is the spec's obj for that slot")
check('default=null' in LENUM, 'with a default, so a slot out of range answers null rather than 0')
plc = code(block(LRS, 'proc,leprechaun_placeholders'))
check('inv_getobj(leprechaun_store, $slot) = null' in plc
      and 'inv_placeholder(leprechaun_store, $slot, enum(int, namedobj, leprechaun_items, $slot))' in plc,
      'every empty slot gets its own item back as a placeholder')
dep = code(block(LRS, 'proc,leprechaun_deposit'))
check('if (~leprechaun_held($slot) = 0) {' in dep
      and 'inv_placeholder(leprechaun_store, $slot, null);' in dep,
      'a deposit clears the placeholder in its target slot first, so the slot the add looks for '
      'is the only free one - which is what lets a can at one dose replace a placeholder at another')
check('~leprechaun_placeholders;' in dep, '...and puts every placeholder back afterwards')
wd = code(block(LRS, 'proc,leprechaun_withdraw'))
check('~leprechaun_placeholders;' in wd, 'a withdrawal that empties a slot re-places its placeholder too')
check('return(inv_getnum(leprechaun_store, $slot));' in code(block(LRS, 'proc,leprechaun_held')),
      'held reads the COUNT, so a placeholder counts as nothing held and the caps are not fooled')
check('if ($held < 1) {' in wd,
      '...and a withdrawal from a placeholder slot says he is holding none rather than moving one')

# ============================================================================ 8
print('8. notes, both ways')
nonote = set(SPEC['no_note_form'])
for row in SPEC['store']:
    name = row['obj']
    has = 'cert_%s' % name in DECLARED
    check(has == (name not in nonote),
          '%s: a note form exists exactly when the spec says one does (cache %s, spec %s)'
          % (name, 'yes' if has else 'no', 'no' if name in nonote else 'yes'))
check('inv_moveitem_uncert(inv, leprechaun_store' in dep,
      "a deposit goes through inv_moveitem_uncert, so a NOTED stack stores as the plain item - "
      "'noted versions of these items can be stored'")
check('~leprechaun_slot(oc_uncert($obj))' in dep,
      '...and the slot is chosen from the unnoted obj, or a note would find no slot at all')
check('inv_moveitem_cert(leprechaun_store, inv' in wd,
      'Withdraw-as-note goes through inv_moveitem_cert')
check('$give = oc_cert($obj);' in wd and 'if ($give = $obj) {' in wd,
      '...and refuses when the obj has no note, rather than handing back the plain item silently')
check('This item can not be withdrawn as a note' in block(LRS, 'proc,leprechaun_withdraw'),
      "...in the bank's own words")
kind = code(block(LRS, 'proc,leprechaun_deposit_kind'))
check('oc_cert($obj)' in kind and 'inv_total(inv, $note)' in kind,
      'Deposit-everything takes the loose ones and the noted stack')
sweep = code(block(LRS, 'proc,leprechaun_deposit_all'))
check('while ($slot < inv_size(leprechaun_store))' in sweep,
      "the sweep walks HIS slots, not the player's inventory: deleting out of an inventory while "
      'walking it skips whatever shuffles down into a slot already passed')
swept = set(ph.values()) | set(re.findall(r'~leprechaun_deposit_kind\((\w+)\)', sweep))
check(swept == set(accepted),
      'and between the enum rows and the variants it names, it sweeps exactly what he accepts (%s)'
      % (sorted(set(accepted) ^ swept) or 'exact match'))

# ============================================================================ 9
print('9. the store this replaces is gone, and nobody loses a rake to it')
check('[proc,farming_store_get]' not in NPCS and '[proc,farming_store_set]' not in NPCS,
      'the bit-packed getters are gone')
check('farming_leprechaun_toolmenu' not in NPCS and 'farming_leprechaun_tools' not in NPCS,
      'and so is the two-deep "which of three tools" menu')
check('case 1 : ~leprechaun_window;' in NPCS, 'Talk-to reaches the window instead')
check('%farming_store_tools' not in code(NPCS),
      'nothing outside the migration touches the old varp any more')
mig = code(block(LRS, 'proc,leprechaun_migrate'))
check('if (%farming_store_tools = 0) {' in mig,
      'the migration is skipped when the varp is empty, which is every visit after the first')
check('%farming_store_tools = 0;' in mig,
      '...and zeroes it when it is not, so opening the window twice cannot migrate twice')
reads = re.findall(r'%farming_store_tools', code(LRS))
check(len(reads) == len(re.findall(r'%farming_store_tools', mig + code(block(LRS, 'proc,leprechaun_migrate_tool')))),
      'every mention of the varp in the new file is inside the migration (%d)' % len(reads))
for tag in ('rake', 'dibber', 'spade', 'trowel', 'secateurs', 'can'):
    lo, hi = (const(LCONST, 'leprechaun_old_%s_lo' % tag), const(LCONST, 'leprechaun_old_%s_hi' % tag))
    want = SPEC['legacy']['bits'][{'can': 'watering_can', 'trowel': 'gardening_trowel'}.get(tag, tag)]
    check([lo, hi] == want,
          'the old %s field is the bits farming.varp documented (spec %s, code %s)'
          % (tag, want, [lo, hi]))
check((1 << (const(LCONST, 'leprechaun_old_rake_hi') - const(LCONST, 'leprechaun_old_rake_lo') + 1)) - 1
      == SPEC['legacy']['max_per_tool'],
      'three bits is where the old cap of seven came from (%d)' % SPEC['legacy']['max_per_tool'])
check('DEAD as of' in FVARP and '[leprechaun_store]' in FVARP,
      'farming.varp says the varp is dead and where the store went')
useitem = code(block(NPCS, 'opnpcu,farming_tools_leprechaun'))
check('~leprechaun_slot(oc_uncert($item)) >= 0' in useitem
      and useitem.index('~leprechaun_deposit') < useitem.index('~farming_note_obj'),
      'using something on him STORES it if he will keep it, and only then tries to note it')
check('~farming_note_obj($item);' in NPCS and '~farming_leprechaun_fill_can;' in NPCS,
      '...and the two things he already did - noting produce, filling a can - are untouched: '
      'the CALLS, not just a name that something longer starts with')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
