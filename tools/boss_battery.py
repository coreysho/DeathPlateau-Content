#!/usr/bin/env python3
"""Battery for the boss kill counts.

Everything is PARSED OUT of the delivered files - the display names from each boss's own .npc
record, the mapping from the enum, the increments from the generated switch, the window from the
.if - so a change to one of them cannot pass a check still asserting the old value.

    python3 tools/boss_battery.py
"""
import json, os, re, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1

def nocomment(txt):
    """The code with // comments and string bodies removed. Every battery here that lacked one
    has had a check pass on its own comment at least once; this one starts with it."""
    return '\n'.join(re.sub(r'"[^"]*"', '""', l).split('//')[0] for l in txt.split('\n'))

def pack(name):
    out = {}
    for line in read('pack/' + name).split('\n'):
        if '=' in line:
            i, n = line.split('=', 1)
            out[n.strip()] = int(i)
    return out

def blocks(txt):
    out, cur = {}, None
    for line in txt.split('\n'):
        t = line.split('//')[0].strip()
        if not t:
            continue
        m = re.match(r'^\[([\w:]+)\]$', t)
        if m:
            cur = {}
            out[m.group(1)] = cur
            continue
        if cur is None or '=' not in t:
            continue
        k, v = t.split('=', 1)
        cur.setdefault(k, []).append(v)
    return out

SPEC = json.loads(read('tools/bosskillspec.json'))
B = SPEC['bosses']
KEYS = [b['key'] for b in B]
# Every npc record a boss can die in - its own, then whatever "forms" names. Only Zulrah has more
# than one (three colours, one snake), and tools/genbosskills.py has the same helper.
NPCS = {b['key']: [b['npc']] + list(b.get('forms', [])) for b in B}
ALLNPCS = [n for b in B for n in NPCS[b['key']]]
NPCP, VARPP, IFP = pack('npc.pack'), pack('varp.pack'), pack('interface.pack')
VARP = blocks(read('scripts/bosses/configs/boss_kills.varp'))
CONST = read('scripts/bosses/configs/boss_kills.constant')
ENUM = read('scripts/bosses/configs/boss_kills.enum')
IFACE = blocks(read('scripts/bosses/interfaces/boss_kills.if'))
RS2 = read('scripts/bosses/scripts/boss_kills.rs2')
DEATH = read('scripts/skill_combat/scripts/npc/npc_death.rs2')
QL = blocks(read('scripts/interfaces/questlist.if'))
QLRAW = read('scripts/interfaces/questlist.if')

print('1. the bosses, and they are the ones the tree actually has')
# Twelve to begin with, thirteen since the Kraken (2026-09-21, area_kraken_cove), fourteen since
# Zulrah (2026-09-28, area_zulrah).
check(len(B) == 14 and len(set(KEYS)) == 14,
      'the spec names fourteen bosses with fourteen distinct keys: %d' % len(B))
check(re.search(r'^\^boss_kills_count = %d$' % len(B), CONST, re.M) is not None,
      '^boss_kills_count is counted from the spec rather than typed: %d' % len(B))
check(re.search(r'^\^boss_kills_none = -1$', CONST, re.M) is not None,
      "and ^boss_kills_none is -1, which is the enum's default and so the 'not a boss' answer")
_missing = [n for n in ALLNPCS if n not in NPCP]
check(not _missing, 'every npc the spec names is a real npc, forms included: %s'
      % (_missing or 'all %d' % len(ALLNPCS)))

# THE DISPLAY NAMES COME FROM THE NPC RECORDS, not from the spec. This is the check that would
# catch a window disagreeing with what the player sees over the monster's head.
_npcnames = {}
for _root, _d, _files in os.walk(os.path.join(C, 'scripts')):
    for _fn in _files:
        if not _fn.endswith('.npc'):
            continue
        _rel = os.path.relpath(os.path.join(_root, _fn), C)
        _cur = None
        for _line in read(_rel).split('\n'):
            _t = _line.split('//')[0].strip()
            _m = re.match(r'^\[(\w+)\]$', _t)
            if _m:
                _cur = _m.group(1)
            elif _cur and _t.startswith('name='):
                _npcnames.setdefault(_cur, _t[5:])
_nbad = ['%s: record %r, spec %r' % (n, _npcnames.get(n), b['name'])
         for b in B for n in NPCS[b['key']] if _npcnames.get(n) != b['name']]
check(not _nbad,
      "each boss's display name is its own npc record's name=, read out of the record - and every "
      'form of a boss carries the same name, so the window says one thing whichever colour died: '
      '%s' % (_nbad[:2] or 'all %d records agree' % len(ALLNPCS)))
check(sorted(NPCS['zulrah']) == ['zulrah', 'zulrah_magma', 'zulrah_tanzanite'],
      "Zulrah's three colours are three npc records against ONE slot - the fight moves between "
      'them with npc_changetype_keepall, which retypes the one snake rather than adding a second, '
      'so a fight is still one death: %s' % sorted(NPCS['zulrah']))
check(any(b['npc'] == 'kalphite_flyingqueen' for b in B)
      and not any(b['npc'] == 'kalphite_queen' for b in B),
      'the Kalphite Queen is counted on the FLYING form and not the first - the first does not '
      'die, which is why its drop table is hooked there too, and counting both would double '
      'every kill')

print('2. one perm varp each, and protect=no, which is the whole reason this works')
check(sorted(VARP) == sorted('boss_kc_%s' % k for k in KEYS),
      'one varp per boss, named after its key - one per BOSS and not per npc record, so Zulrah\'s '
      'three colours share a counter: %s'
      % (sorted(set(VARP) ^ {'boss_kc_%s' % k for k in KEYS}) or 'exactly %d' % len(B)))
check(all(f.get('scope') == ['perm'] for f in VARP.values()),
      'every one is scope=perm, so a kill count is the account\'s for good')
# THE CHECK THIS ROUND EXISTS TO HAVE. Varps are PROTECTED by default and writing one needs the
# p_active_player pointer an npc-context death does not have. Four builds were spent on the
# symptom before the varp declaration turned out to be the cause.
check(all(f.get('protect') == ['no'] for f in VARP.values()),
      'and every one is protect=no - without it the write from [proc,npc_death] fails the build '
      'with "Attempt to access corrupted pointer", which is what %barrows_killed_monster\'s base '
      'varp has carried the whole time')
check(all('boss_kc_%s' % k in VARPP for k in KEYS),
      'and each has an id in pack/varp.pack: %s'
      % ([k for k in KEYS if 'boss_kc_%s' % k not in VARPP] or 'all %d' % len(B)))
check(not [f for f in VARP.values() if f.get('transmit')],
      'none is transmitted - the window is filled by if_settext, so the client never needs them')

print('3. the two tables: npc -> slot, and slot -> name')
_ib = ENUM.split('[boss_kill_index]', 1)[1].split('\n[', 1)[0] if '[boss_kill_index]' in ENUM else ''
_iv = dict((n, int(i)) for n, i in re.findall(r'^val=(\w+),(-?\d+)$', _ib, re.M))
_want_iv = {n: i for i, b in enumerate(B) for n in NPCS[b['key']]}
check(_iv == _want_iv,
      'boss_kill_index maps every npc record to its boss\'s slot, 0..%d, in the spec\'s order: %s'
      % (len(B) - 1, sorted(set(_iv.items()) ^ set(_want_iv.items()))[:2]
         or 'exactly the %d records' % len(ALLNPCS)))
check('default=-1' in _ib and 'inputtype=npc' in _ib and 'outputtype=int' in _ib,
      '...and everything else in the game answers -1, which is ^boss_kills_none')
_nb = ENUM.split('[boss_kill_name]', 1)[1].split('\n[', 1)[0] if '[boss_kill_name]' in ENUM else ''
_nv = dict((int(i), n) for i, n in re.findall(r'^val=(\d+),(.+)$', _nb, re.M))
check(_nv == {i: b['name'] for i, b in enumerate(B)},
      'boss_kill_name maps each slot to that boss\'s name: %s'
      % (sorted(set(_nv.items()) ^ {(i, b['name']) for i, b in enumerate(B)})[:2]
         or 'all %d' % len(B)))

print('4. a kill is credited to the hero, and counted once')
_rec = nocomment(RS2).split('[proc,boss_kill_record]', 1)[1].split('\n[', 1)[0] \
    if '[proc,boss_kill_record]' in nocomment(RS2) else ''
# THE GUARD WENT MISSING FOR ONE BUILD while the pointer error was being chased, and the build
# went GREEN with it gone. That is why it is checked by name and checked FIRST.
check(_rec.strip().startswith('if (npc_findhero = ^false) {'),
      'the first thing ~boss_kill_record does is refuse a kill with no hero - the same test every '
      'drop table in this tree opens with, so the count goes to whoever the loot did')
check('%npc_aggressive_player' not in _rec,
      "...and it does NOT use %npc_aggressive_player, which is the LAST attacker and a different "
      'thing')
check(_rec.count('queue(boss_kill_announce') == 1,
      'the message is queued exactly once per counted kill, because mes() wants a player context '
      'an npc-context death does not have')
_sw = _rec.split('switch_int', 1)[1].split('}', 1)[0] if 'switch_int' in _rec else ''
_cases = dict(re.findall(r'case (\d+) : %boss_kc_(\w+) = add\(%boss_kc_\2, 1\);', _sw))
check({int(k): v for k, v in _cases.items()} == {i: b['key'] for i, b in enumerate(B)},
      'and every slot increments ITS OWN counter, by one - the cross-wiring that would count the '
      'wrong boss and never error: %d of %d cases right' % (len(_cases), len(B)))
# LAST, not merely present. A mutation that moved the default to the front of the switch walked
# straight through an `in` test - and a default ahead of the numbered cases is a switch where
# nothing else is ever reached.
_swlines = [l.strip() for l in _sw.split('\n') if l.strip().startswith('case ')]
check(_swlines and _swlines[-1] == 'case default : return;'
      and len([l for l in _swlines if 'default' in l]) == 1,
      '...with a default case, and it is the LAST one - a default ahead of the numbered cases is '
      'a switch where none of them is ever reached: %s' % (_swlines[-1:] or 'no cases at all'))
_get = nocomment(RS2).split('[proc,boss_kill_get]', 1)[1].split('\n[', 1)[0] \
    if '[proc,boss_kill_get]' in nocomment(RS2) else ''
_reads = dict(re.findall(r'case (\d+) : return\(%boss_kc_(\w+)\);', _get))
check({int(k): v for k, v in _reads.items()} == {i: b['key'] for i, b in enumerate(B)},
      'the read-back switch reads the same counters, slot for slot: %d of %d'
      % (len(_reads), len(B)))
check('case default : return(0);' in _get,
      '...and an unknown slot reads as no kills rather than as the first boss\'s')

print('5. hooked in the one place every death passes through')
_dc = nocomment(DEATH)
check(_dc.count('~boss_kill_record;') == 1,
      '~boss_kill_record is called exactly once from npc_death.rs2: %d'
      % _dc.count('~boss_kill_record;'))
_elsewhere = []
for _root, _d, _files in os.walk(os.path.join(C, 'scripts')):
    for _fn in _files:
        if not _fn.endswith('.rs2'):
            continue
        _rel = os.path.relpath(os.path.join(_root, _fn), C)
        if '~boss_kill_record' in nocomment(read(_rel)) and 'boss_kills.rs2' not in _rel:
            _elsewhere.append(os.path.basename(_rel))
check(_elsewhere == ['npc_death.rs2'],
      'and from nowhere else, so no boss can be counted twice or missed: %s' % _elsewhere)
_ai = []
for _root, _d, _files in os.walk(os.path.join(C, 'scripts')):
    for _fn in _files:
        if _fn.endswith('.rs2'):
            _rel = os.path.relpath(os.path.join(_root, _fn), C)
            _t = nocomment(read(_rel))
            for b in B:
                if re.search(r'^\[ai_queue3,%s\]' % re.escape(b['npc']), _t, re.M):
                    _ai.append(b['npc'])
check(len(_ai) >= 8,
      'and at least eight of them already carry an [ai_queue3] of their own, which is why there '
      'was no per-boss hook to use: %d do' % len(_ai))
# ZULRAH IS THE ONE THAT LOOKS LIKE AN EXCEPTION. Its [ai_queue3] is not an engine drop table but
# its own death script, and the only thing that brings the kill to ~boss_kill_record is the
# gosub(npc_death) that script opens with. Take that line out and the counter silently stops -
# which is exactly the failure these two checks exist to catch.
_zd = nocomment(read('scripts/areas/area_zulrah/scripts/zulrah_drops.rs2'))
_zq = sorted(re.findall(r'^\[ai_queue3,(zulrah\w*)\]', _zd, re.M))
check(_zq == ['zulrah', 'zulrah_magma', 'zulrah_tanzanite'],
      "all three of Zulrah's colours die through the one death script in zulrah_drops.rs2: %s"
      % _zq)
check(_zd.count('gosub(npc_death)') == 1,
      '...and that script opens with exactly one gosub(npc_death), which is the whole of how a '
      'Zulrah kill reaches ~boss_kill_record - once per kill, whatever colour it was wearing: %d'
      % _zd.count('gosub(npc_death)'))

print('6. the window, and the one row that opens it')
# EXACTLY name0..nameN and count0..countN. The first version counted components whose name
# STARTED WITH 'count', so renaming count7 to count7x kept the total at twelve and the check
# passed while the opener's if_settext pointed at a component that no longer existed.
_wantrows = {'name%d' % i for i in range(len(B))} | {'count%d' % i for i in range(len(B))}
_haverows = {n for n in IFACE if re.match(r'^(name|count)\d+$', n)}
check(_haverows == _wantrows and not [n for n in IFACE
                                      if re.match(r'^(name|count)', n) and n not in _wantrows],
      '%d name rows and %d count rows, named exactly name0..name%d and count0..count%d: '
      '%s' % (len(B), len(B), len(B) - 1, len(B) - 1,
              sorted(_haverows ^ _wantrows)[:3] or 'exactly the %d' % (2 * len(B))))
_rowbad = ['name%d' % i for i, b in enumerate(B)
           if IFACE.get('name%d' % i, {}).get('text') != [b['name']]]
check(not _rowbad, 'each row is labelled with its own boss: %s'
      % (_rowbad[:2] or 'all %d' % len(B)))
check(all(IFACE.get('count%d' % i, {}).get('text') == ['0'] for i in range(len(B))),
      "and each count starts at 0 rather than blank - an empty row reads as a broken window")
check(IFACE.get('close', {}).get('buttontype') == ['close'],
      'there is a close button, and it is buttontype=close')
_ifmissing = [n for n in IFACE if 'boss_kills:%s' % n not in IFP]
check(not _ifmissing and 'boss_kills' in IFP,
      'every component and the interface itself have ids in pack/interface.pack: %s'
      % (_ifmissing[:3] or '%d of them' % len(IFACE)))
_order = set(int(x) for x in read('pack/interface.order').split('\n') if x.strip().isdigit())
_oblank = [n for n in IFACE if IFP.get('boss_kills:%s' % n) not in _order]
check(not _oblank and IFP['boss_kills'] in _order,
      'and interface.order agrees about all of them, which the packer requires: %s'
      % (_oblank[:3] or 'all present'))
_open = nocomment(RS2).split('[proc,boss_kills_open]', 1)[1].split('\n[', 1)[0] \
    if '[proc,boss_kills_open]' in nocomment(RS2) else ''
check('if_openmain(boss_kills);' in _open,
      'the opener opens the window')
_sets = re.findall(r'~boss_kills_count\(boss_kills:count(\d+), ~boss_kill_get\((\d+)\)\)',
                   _open)
check([(str(i), str(i)) for i in range(len(B))] == _sets,
      '...and pushes every count into its own box, the right count to the right box: %d of %d'
      % (len(_sets), len(B)))
check('if_settext(boss_kills:subtitle,' in _open and '$total' in _open,
      '...and the total of them into the subtitle')
# The window opens from the quest tab's Server Statistics page now; the quest list is quests only.
check('[if_button,questlist:boss_kills]' not in nocomment(RS2) and 'boss_kills' not in QL
      and '\n[boss_kills]\n' not in QLRAW,
      'the quest list has no "Boss kill counts" row and no trigger for one')
_qt = read(os.path.join(C, 'scripts/questtab/scripts/questtab.rs2'))
check(re.search(r'\[if_button,questtab_sstats:act_bosses\]\s*~boss_kills_open;', _qt) is not None,
      "Server Statistics' Quick actions open the window")

print('7. the generator reproduces what is checked in')
r = subprocess.run([sys.executable, os.path.join(C, 'tools/genbosskills.py'), '--check'],
                   capture_output=True, text=True, cwd=C)
check(r.returncode == 0,
      'tools/genbosskills.py --check: every generated file and both pack files are already what '
      'it writes%s' % ('' if r.returncode == 0 else ': ' + r.stdout.strip()[:220]))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
