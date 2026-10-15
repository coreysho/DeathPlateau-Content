#!/usr/bin/env python3
"""Mutation test for tools/leprechaun_battery.py. Same runner as compost_mutate.py, with one
addition: some of what the battery checks lives in the OTHER TWO REPOS, so the work tree gets a
copy of the three engine and client files it reads and the battery is pointed at those. A mutation
to the client's packet buffer has to be catchable, because the client is the half most likely to be
left behind - it is a separate checkout and a separate build.

Every entry breaks one thing and expects the battery to go red with the check that is named. A
GREEN line is a hole in the battery.

    python3 tools/leprechaun_mutate.py                 # all of them
    python3 tools/leprechaun_mutate.py "placeholder"   # just the ones whose name contains that
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(C), 'engine')
# The client clone is 'javaclient' here; 'client' was a guess that matched nothing, so this exited
# before running a single mutation. Both names are tried, and LOSTCITY_CLIENT wins over either.
CLIENT = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('LOSTCITY_CLIENT') or next(
    (os.path.join(os.path.dirname(C), _n) for _n in ('javaclient', 'client')
     if os.path.isdir(os.path.join(os.path.dirname(C), _n))),
    os.path.join(os.path.dirname(C), 'client'))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'leprechaun_mutate_work')

# the only three files the battery reads outside the content tree, copied in so they can be broken
FOREIGN = {
    'engine:src/network/game/server/codec/UpdateInvFullEncoder.ts': ENGINE,
    'engine:src/server/ClientSocket.ts': ENGINE,
    'client:src/main/java/jagex2/client/Client.java': CLIENT,
}

BC = 'scripts/interface_bank/configs/bank.constant'
BIF = 'scripts/interface_bank/interfaces/bank_main.if'
BRS = 'scripts/interface_bank/scripts/bank.rs2'
BINV = 'scripts/interface_bank/configs/bank.inv'
GT = 'tools/genbanktabs.py'
GB = 'tools/genbankbar.py'
BSIM = 'tools/banktab_sim.py'
ENC = 'engine:src/network/game/server/codec/UpdateInvFullEncoder.ts'
SOCK = 'engine:src/server/ClientSocket.ts'
CLI = 'client:src/main/java/jagex2/client/Client.java'

LC = 'scripts/skill_farming/configs/leprechaun.constant'
LI = 'scripts/skill_farming/configs/leprechaun.inv'
LE = 'scripts/skill_farming/configs/leprechaun.enum'
LRS = 'scripts/skill_farming/scripts/leprechaun.rs2'
LIF = 'scripts/skill_farming/interfaces/leprechaun_window.if'
NPC = 'scripts/skill_farming/scripts/farming_npcs.rs2'
FV = 'scripts/skill_farming/configs/farming.varp'
SPEC = 'tools/leprechaunspec.json'
IPACK = 'pack/interface.pack'
IORDER = 'pack/interface.order'
NVPACK = 'pack/inv.pack'
ALLOBJ = 'scripts/_unpack/377/all.obj'

MUTS = [
 # ---- 1 the bank's size
 (BC, '^bank_total_slots = 1410', '^bank_total_slots = 1400',
  '1 a members bank is 1410 spaces'),
 (BC, '^bank_free_slots = 910', '^bank_free_slots = 60',
  '1 and a free one is 910'),
 (BINV, 'size=^bank_total_slots', 'size=1410',
  '1 the inv is sized by the constant, not by a number written twice'),
 (BRS, 'if (playermember = ^false) {', 'if (^false = ^true) {',
  '1 the free limit is a check on playermember'),
 (BRS, '(sub(inv_size(bank), inv_freespace(bank)) >= ^bank_free_slots)',
       '(inv_freespace(bank) = 0)',
  '1 ...and it counts slots in use rather than trusting a running total'),

 # ---- 2 the grid
 (BIF, 'clientcode=206\nwidth=12\nheight=125', 'clientcode=206\nwidth=11\nheight=125',
  '2 the grid is as many columns as bankgeom.py says'),
 (BIF, 'clientcode=206\nwidth=12\nheight=125', 'clientcode=206\nwidth=12\nheight=118',
  '2 and ceil((1410 + 88) / 12) = 125 rows'),
 (BIF, 'height=222\nscroll=4750', 'height=222\nscroll=1938',
  '2 the layer can be scrolled to the last row'),
 (GT, 'GRID_ROWS = -(-(bank_slots() + SLOT_PAD) // GRID_W)', 'GRID_ROWS = 184',
  '2 the row count is DERIVED from ^bank_total_slots'),
 (GT, "    return int(m.group(1))", "    return 1410",
  '2 ...by reading bank.constant inside bank_slots()'),
 (BSIM, "SIZE = _const('bank_total_slots')", "SIZE = 1410",
  '2 banktab_sim.py reads all three numbers out of the configs'),

 # ---- 3 the packet
 (ENC, 'for (let slot = capacity - 1; slot >= 0; slot--) {\n'
       '            if (inv.get(slot)) {\n'
       '                return slot + 1;\n'
       '            }\n'
       '        }\n        return 0;', '        return capacity;',
  '3 UPDATE_INV_FULL transmits up to the last OCCUPIED slot'),
 (ENC, '    private static size(message: UpdateInvFull): number {',
       '    // todo: size should be the index of the last non-empty slot\n'
       '    private static size(message: UpdateInvFull): number {',
  "3 ...which was the encoder's own todo, so the todo is gone"),
 (ENC, 'length += 4;', 'length += 3;',
  '3 test() counts the four header bytes'),
 (SOCK, '    out = Packet.alloc(2);', '    out = Packet.alloc(1);',
  '3 ClientSocket.out is alloc(2) = 30000 bytes'),
 (CLI, 'public Packet in = Packet.alloc(2);', 'public Packet in = Packet.alloc(1);',
  '3 and the client reads a whole variable-length packet into Packet.alloc(2) to match'),
 (CLI, 'var108.invSlotObjId[var112] = 0;', 'var108.invSlotObjId[var112] = -1;',
  '3 the trim is safe because the client already zeroes every slot past the transmitted size'),

 # ---- 4 the generators
 (GT, "body = re.sub(r'\\n*' + re.escape(MARK_A)", "body = re.sub(re.escape(MARK_A)",
  '4 genbanktabs.py eats the blank lines its block sat behind'),
 (GB, "body = re.sub(r'\\n*' + re.escape(MARK_A)", "body = re.sub(re.escape(MARK_A)",
  '4 genbankbar.py eats the blank lines its block sat behind'),

 # ---- 5 the capacities
 (LC, '^leprechaun_slots = 12', '^leprechaun_slots = 11',
  '5 12 slots, one per thing the wiki says he holds'),
 (LRS, 'case rake : return(^leprechaun_slot_rake);', 'case rake : return(^leprechaun_slot_spade);',
  '5 rake is slot 0'),
 (LC, '^leprechaun_cap_tool = 100', '^leprechaun_cap_tool = 50',
  '5 the three caps are 100, 1000 and 1'),
 (LC, '^leprechaun_cap_supply = 1000', '^leprechaun_cap_supply = 100',
  "5 bucket_compost: the cap is the wiki's number"),
 (LC, '^leprechaun_cap_single = 1', '^leprechaun_cap_single = 2',
  "5 bottomless_bucket: the cap is the wiki's number"),
 (LRS, '    case ^leprechaun_slot_can, ^leprechaun_slot_bottomless : return(^leprechaun_cap_single);',
        '    case ^leprechaun_slot_bottomless : return(^leprechaun_cap_single);',
  "5 watering_can_8: the cap is the wiki's number"),
 (SPEC, '{ "slot": 0,  "obj": "rake",                "cap": 100,  "kind": "tool" }',
        '{ "slot": 0,  "obj": "rake",                "cap": 200,  "kind": "tool" }',
  "5 rake: the cap is the wiki's number"),
 (LRS, '    case bottomless_bucket, bottomless_bucket_filled : return(^leprechaun_slot_bottomless);',
        '',
  '5 the switch reaches every slot and invents none'),
 (LRS, 'case plant_cure : return(^leprechaun_slot_cure);',
       'case plant_cure : return(^leprechaun_slot_cure);\n'
       '    case bucket_water : return(^leprechaun_slot_bucket);',
  '8 and between the enum rows and the variants it names, it sweeps exactly what he accepts'),

 # ---- 6 the inv and the window
  # anchored on the block header: 'scope=perm' also appears in this file's own comment, and an
 # earlier version of this mutation edited the comment and was quite correctly not caught
 (LI, '[leprechaun_store]\nscope=perm', '[leprechaun_store]\nscope=temp', '6 the store is perm'),
 (LI, 'stackall=yes', 'protect=no', '6 and stackall'),
 (LI, 'size=^leprechaun_slots', 'size=12', '6 sized by the constant'),
 (NVPACK, '415=leprechaun_store\n', '', '6 registered in pack/inv.pack'),
 (LIF, 'type=inv\nx=60\ny=72\nwidth=6\nheight=2', 'type=inv\nx=60\ny=72\nwidth=5\nheight=2',
  '6 the grid has exactly 12 squares'),
 (LIF, 'option5=Withdraw-as-note', 'option5=Withdraw-note', '6 option 5 is Withdraw-as-note'),
 (LRS, '[inv_button5,leprechaun_window:store] ~leprechaun_withdraw(last_slot, ^max_32bit_int, true);\n',
       '', '6 ...and inv_button5 handles it'),
 (LRS, '[if_button,leprechaun_window:depositall] ~leprechaun_deposit_all;\n', '',
  '6 Deposit-everything is a button'),
 (LRS, 'inv_stoptransmit(leprechaun_window:store);', 'mes("closed");',
  '6 the inv is transmitted on open and the transmit is stopped on close'),
 (IPACK, '=leprechaun_window:store\n', '=leprechaun_window:store_gone\n',
  '6 every component is in pack/interface.pack'),

 # ---- 7 the placeholders
 (LE, 'val=0,rake', 'val=0,spade', '7 and each row is the spec\'s obj for that slot'),
 (LE, 'default=null\n', '', '7 with a default'),
 (LE, 'val=11,bucket_supercompost\n', '', '7 the enum has a row per slot'),
 (LRS, 'inv_placeholder(leprechaun_store, $slot, enum(int, namedobj, leprechaun_items, $slot));',
       'mes("empty");',
  '7 every empty slot gets its own item back as a placeholder'),
 (LRS, 'if (~leprechaun_held($slot) = 0) {\n    inv_placeholder(leprechaun_store, $slot, null);\n}\n'
       'inv_moveitem_uncert(inv, leprechaun_store, $obj, $n);',
       'inv_moveitem_uncert(inv, leprechaun_store, $obj, $n);',
  '7 a deposit clears the placeholder in its target slot first'),
 (LRS, 'inv_moveitem_uncert(inv, leprechaun_store, $obj, $n);\n~leprechaun_placeholders;',
       'inv_moveitem_uncert(inv, leprechaun_store, $obj, $n);',
  '7 ...and puts every placeholder back afterwards'),
 (LRS, 'return(inv_getnum(leprechaun_store, $slot));', 'return(~leprechaun_cap($slot));',
  '7 held reads the COUNT'),
 (LRS, 'def_int $held = ~leprechaun_held($slot);\nif ($held < 1) {',
       'def_int $held = ~leprechaun_cap($slot);\nif ($held < 0) {',
  '7 ...and a withdrawal from a placeholder slot says he is holding none'),

 # ---- 8 notes
 (ALLOBJ, '[cert_rake]', '[cert_rake_gone]', '8 rake: a note form exists exactly when the spec says one does'),
 (SPEC, '"no_note_form": ["fairy_enchanted_secateurs"', '"no_note_form": ["rake", "fairy_enchanted_secateurs"',
  '8 rake: a note form exists exactly when the spec says one does'),
 (LRS, 'inv_moveitem_uncert(inv, leprechaun_store, $obj, $n);',
       'inv_moveitem(inv, leprechaun_store, $obj, $n);',
  '8 a deposit goes through inv_moveitem_uncert'),
 (LRS, 'def_int $slot = ~leprechaun_slot(oc_uncert($obj));',
       'def_int $slot = ~leprechaun_slot($obj);',
  '8 ...and the slot is chosen from the unnoted obj'),
 (LRS, 'inv_moveitem_cert(leprechaun_store, inv, $obj, $take);',
       'inv_moveitem(leprechaun_store, inv, $obj, $take);',
  '8 Withdraw-as-note goes through inv_moveitem_cert'),
 (LRS, '    if ($give = $obj) {\n        mes("This item can not be withdrawn as a note.");'
       ' // the bank\'s wording, 2005\n        return;\n    }\n', '',
  '8 ...and refuses when the obj has no note'),
 (LRS, 'def_obj $note = oc_cert($obj);\nif ($note ! $obj) {\n'
       '    $moved = add($moved, ~leprechaun_deposit($note, inv_total(inv, $note)));\n}\n', '',
  '8 Deposit-everything takes the loose ones and the noted stack'),
 (LRS, 'while ($slot < inv_size(leprechaun_store)) {\n'
       '    $moved = add($moved, ~leprechaun_deposit_kind(enum(int, namedobj, leprechaun_items, $slot)));',
       'while ($slot < inv_size(inv)) {\n'
       '    $moved = add($moved, ~leprechaun_deposit_kind(enum(int, namedobj, leprechaun_items, $slot)));',
  '8 the sweep walks HIS slots'),

 # ---- 9 the old store
 (NPC, 'case 1 : ~leprechaun_window;', 'case 1 : ~farming_leprechaun_fill_can;',
  '9 Talk-to reaches the window instead'),
 (NPC, '[proc,farming_leprechaun_fill_can]',
       '[proc,farming_store_get](int $a, int $b)(int)\nreturn(0);\n\n[proc,farming_leprechaun_fill_can]',
  '9 the bit-packed getters are gone'),
 (NPC, 'mes("The leprechaun fills your watering can.");',
       'mes("The leprechaun fills your watering can.");\n%farming_store_tools = 0;',
  '9 nothing outside the migration touches the old varp any more'),
 (LRS, 'if (%farming_store_tools = 0) {\n    return;\n}\n', '',
  '9 the migration is skipped when the varp is empty'),
 (LRS, '%farming_store_tools = 0;\nmes("The leprechaun puts everything',
       'mes("The leprechaun puts everything',
  '9 ...and zeroes it when it is not'),
 (LC, '^leprechaun_old_rake_hi = 2', '^leprechaun_old_rake_hi = 3',
  '9 the old rake field is the bits farming.varp documented'),
 (SPEC, '"rake": [0, 2]', '"rake": [0, 3]',
  '9 the old rake field is the bits farming.varp documented'),
 (FV, '// DEAD as of 2026-09-18', '// Tool leprechaun storage.',
  '9 farming.varp says the varp is dead and where the store went'),
 (NPC, 'if (~leprechaun_slot(oc_uncert($item)) >= 0) {', 'if (^false = ^true) {',
  '9 using something on him STORES it if he will keep it'),
 (NPC, '~farming_note_obj($item)', '~farming_note_obj_gone($item)',
  '9 ...and the two things he already did - noting produce, filling a can - are untouched'),
]


def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    os.makedirs(W)
    shutil.copytree(C, os.path.join(W, 'content'),
                    ignore=shutil.ignore_patterns('.git', '__pycache__'))
    for tagged, root in FOREIGN.items():
        tag, rel = tagged.split(':', 1)
        dst = os.path.join(W, tag, rel)
        src = os.path.join(root, rel)
        if not os.path.exists(src):
            sys.exit('cannot find %s - pass the engine and client paths as argv[2] and argv[3]' % src)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    only = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('/') else None
    muts = [m for m in MUTS if not only or only in m[3]]
    fails = loose = 0
    for path, find, repl, why in muts:
        if ':' in path:
            tag, rel = path.split(':', 1)
            p = os.path.join(W, tag, rel)
        else:
            p = os.path.join(W, 'content', path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-30s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'content', 'tools', 'leprechaun_battery.py'),
                            os.path.join(W, 'engine'), os.path.join(W, 'client')],
                           capture_output=True, text=True, cwd=os.path.join(W, 'content'))
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:52] if fired else 'a crash')
            loose += 1
        print('  %-5s %-62s %s' % (state, why, note))
    print()
    if fails:
        print('%d MUTATIONS SURVIVED' % fails)
    elif loose:
        print('every mutation was caught, but %d by a check other than its own' % loose)
    else:
        print('every mutation was caught, each by its own check')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
