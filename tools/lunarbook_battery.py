"""Battery for the Lunar spellbook (skill_magic/interfaces/lunar_magic.if and everything it casts).

WHAT IS AT RISK. The book is generated from 474's interface 430 by LostCityServer
tools/models/genlunar474.py, and the spells' levels and runes live twice: in the buttons' client-side
greying scripts (the cache's own numbers) and in skill_magic/configs/lunar_spells.dbrow (what the
server charges). If the two drift, a spell is lit and refuses, or grey and casts. A button with no
trigger is a dead click. And Vengeance is PvP: its hooks sit in the two queues every hit on a player
passes through, where a mistake is a loop or a missing rebound, and nothing about either fails to
compile.

So this checks the join (every button against its row), that every button answers, how the book is
reached, Vengeance's wiring, astral runes, and that the generator still makes the checked-in file.
The behaviour itself is Engine-TS tools/sim/run.ts `vengeance`, `lunar` and `lunarspells`.

    python3 tools/lunarbook_battery.py
"""
import os, re, sys, glob, shutil, subprocess, tempfile

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IF = 'scripts/skill_magic/interfaces/lunar_magic.if'
ROWS = 'scripts/skill_magic/configs/lunar_spells.dbrow'

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1

def read(p):
    return open(os.path.join(C, p), newline='', encoding='utf-8').read().replace('\r\n', '\n')

def blocks(text):
    out = {}
    for b in re.split(r'(?m)^\[', text)[1:]:
        n = b.split(']')[0]
        d = {}
        for l in b.split('\n')[1:]:
            if '=' in l and not l.lstrip().startswith('//'):
                k, v = l.split('=', 1)
                d[k.strip()] = v.strip()
        out[n] = d
    return out

BOOK = blocks(read(IF))
BTN = {n: d for n, d in BOOK.items() if 'buttontype' in d}
rows = {}
for b in re.split(r'(?m)^\[', read(ROWS))[1:]:
    name = b.split(']')[0].replace('magic_spell_', '')
    level = int(re.search(r'data=levelrequired,(\d+)', b).group(1))
    runes = re.search(r'data=runesrequired,(.*)', b).group(1).split(',')
    rows[name] = (level, [(runes[i], int(runes[i + 1])) for i in range(0, 6, 2) if runes[i] != 'null'])
SRC = ''
for f in glob.glob(os.path.join(C, 'scripts', '**', '*.rs2'), recursive=True):
    SRC += open(f, encoding='utf-8', errors='replace').read().replace('\r\n', '\n') + '\n'

# ============================================================================ 1
print('1. the book against the spell table')
check(len(BTN) == 40, "474's forty spells, forty buttons: %d" % len(BTN))
check(set(BTN) - {'lunar_home_teleport'} == set(rows),
      'every spell but Lunar Home Teleport has a row, and every row a button: %s'
      % (sorted(set(BTN) ^ (set(rows) | {'lunar_home_teleport'})) or 'yes'))
wrong = []
for n, (level, runes) in sorted(rows.items()):
    d = BTN.get(n, {})
    scripts = {}
    for k, v in d.items():
        m = re.match(r'^script(\d+)op1$', k)
        if m:
            scripts[int(m.group(1))] = v
    got_runes = []
    got_level = None
    for i, first in sorted(scripts.items()):
        cmp = int(d.get('script%d' % i, 'gt,-99').split(',')[1])
        if first == 'stat_level,magic':
            got_level = cmp + 1
        else:
            got_runes.append((first.split(',')[-1], cmp + 1))
    if got_level != level or got_runes != runes:
        wrong.append((n, (got_level, got_runes), (level, runes)))
check(not wrong, "each button greys at its row's level and runes, in the row's order: %s" % (wrong[:2] or 'all 39'))
wrong = []
for n, (level, runes) in sorted(rows.items()):
    tip = BOOK.get('tip_%s_title' % n, {}).get('text', '')
    if not tip.startswith('Level %d : ' % level):
        wrong.append((n, tip))
check(not wrong, "...and each hover panel says the same level: %s" % (wrong[:2] or 'all 39'))
def sprite(d, k):
    m = re.match(r'^i474_(\d+),0$', d.get(k, ''))
    return int(m.group(1)) if m else None
wrong = [n for n, d in BTN.items() if n != 'lunar_home_teleport' and (sprite(d, 'graphic') is None or sprite(d, 'activegraphic') != sprite(d, 'graphic') - 50)]
check(not wrong, "each icon is 474's, lit 50 below dark, as on the other two books: %s" % (wrong[:3] or 'all 39'))
home = BTN.get('lunar_home_teleport', {})
check(sprite(home, 'graphic') == 356 and 'activegraphic' not in home, 'Lunar Home Teleport needs nothing, so is always lit (356)')
ops = [op for d in BTN.values() for k, op in d.items() if re.match(r'^script\d+op\d+$', k) and 'astralrune' in op]
check('inv_count,inventory:inv,astralrune' in ops and 'inv_count,rune_pouch_mirror:runes,astralrune' in ops,
      'astral is counted in the pack and in the rune pouch')
check(not any(re.search(r'wornitems:worn,.*astral', o) for o in ops), '...and by no staff, as none supplies it')

# ============================================================================ 2
print('2. every button answers')
KINDS = {'player': ('opplayert', 'applayert'), 'npc': ('opnpct', 'apnpct'), 'heldobj': ('opheldt',), 'loc': ('oploct',)}
dead = []
for n, d in sorted(BTN.items()):
    have = set(re.findall(r'(?m)^\[(\w+),lunar_magic:%s\]' % n, SRC))
    if d['buttontype'] == 'normal':
        if 'if_button' not in have:
            dead.append(n)
    else:
        for kind in d.get('actiontarget', '').split(','):
            if not any(t in have for t in KINDS[kind]):
                dead.append('%s (%s)' % (n, kind))
check(not dead, 'a trigger of the right kind behind every button: %s' % (dead or 'all 40'))
anyt = re.findall(r'(?m)^\[\w+,lunar_magic:(\w+)\]', SRC)
check(set(anyt) <= set(BTN), 'and no trigger names a button the book does not have: %s' % (sorted(set(anyt) - set(BTN)) or 'none'))

# ============================================================================ 3
print('3. how the book is reached')
SB = read('scripts/skill_magic/scripts/spellbooks.rs2')
check('case ^spellbook_lunar : if_settab(lunar_magic, ^tab_magic);' in SB, '~spellbook_tab shows lunar_magic for ^spellbook_lunar')
check(re.search(r'\^spellbook_lunar = 2\b', read('scripts/skill_magic/configs/spellbook.constant')) is not None, '...which is %spellbook 2')
check('~spellbook_tab;' in read('scripts/login_logout/scripts/login.rs2'), 'login restores whichever book, through it')
stray = [f for f in glob.glob(os.path.join(C, 'scripts', '**', '*.rs2'), recursive=True)
         if not f.endswith('spellbooks.rs2') and 'tutorial' not in f
         and re.search(r'if_settab\((ancient_magic|lunar_magic), \^tab_magic\)', open(f, encoding='utf-8', errors='replace').read())]
check(not stray, 'nothing else sends a spellbook tab of its own (the tutorial only ever shows the normal book): %s'
      % ([os.path.relpath(f, C) for f in stray] or 'nothing'))
ISLE = read('scripts/areas/area_lunar_isle/scripts/lunar_isle.rs2')
check('[oploc2,astral_altar]' in ISLE and '%lunar_unlocked = true;' in ISLE and '~set_spellbook(^spellbook_lunar);' in ISLE,
      'praying at the Astral altar unlocks the book and puts you on it')
check(re.search(r'\^lunar_unlock_magic = 65\b', read('scripts/areas/area_lunar_isle/configs/lunar_isle.constant')) is not None,
      '...at 65 Magic')
check('%lunar_unlocked = true' in read('scripts/skillcapes/scripts/skillcape_perks.rs2'), 'the Magic cape offers Lunar once it is unlocked')
# boolean varps start at -1: `= false` is true of nobody who has never set them
bad = re.findall(r'%(?:lunar_unlocked|vengeance|spellbook_swapped) = false\)', SRC)
check(not bad, 'no Lunar boolean varp is tested `= false`, which is never true of an unset one: %s' % (bad[:3] or 'none'))
check('[opnpc3,lokar_searunner]' in ISLE and '[opnpc1,lokar_searunner]' in ISLE, 'Lokar Searunner sails, by Talk-to and by Travel')

# ============================================================================ 4
print('4. Vengeance')
PVP = read('scripts/skill_combat/scripts/pvp/pvp_combat.rs2')
NPC = read('scripts/skill_combat/scripts/npc/npc_combat.rs2')
VENG = read('scripts/skill_magic/scripts/lunar/vengeance.rs2')
# (2026-09-27) the hit carries its hitsplat too - ^hitmark_max for a max hit - and lands through
# ~damage_self_hitmark; a monster's lands in ~combat_damage_player_hit, which [queue,combat_damage_player]
# and [queue,combat_maxhit_player] both call (skill_combat/scripts/hitmark_max.rs2)
check('[queue,pvp_damage](int $damage, player_uid $attacker, int $hitmark)' in PVP and '.queue*(pvp_damage, $delay)($damage, uid, $hitmark);' in PVP,
      'a pvp hit carries the uid of whoever dealt it')
q = PVP.split('[queue,pvp_damage]', 1)[1].split('\n[', 1)[0]
check('~vengeance_rebound_player($damage, $attacker);' in q and '~damage_self_hitmark($damage, $hitmark);' in q
      and q.index('~vengeance_rebound_player') < q.index('~damage_self_hitmark($damage, $hitmark);'),
      '...and the queue answers it with vengeance before the damage lands')
q = NPC.split('[proc,combat_damage_player_hit]', 1)[1].split('\n[', 1)[0]
check('~combat_damage_player_hit($damage, ^hitmark_damage);' in NPC.split('[queue,combat_damage_player]', 1)[1].split('\n[', 1)[0]
      and '~vengeance_rebound_npc($damage);' in q and '~damage_self_hitmark($damage, $hitmark);' in q
      and q.index('~vengeance_rebound_npc') < q.index('~damage_self_hitmark($damage, $hitmark);'),
      "an npc's hit is answered the same way, in combat_damage_player")
q = VENG.split('[queue,vengeance_damage]', 1)[1].split('\n[', 1)[0]
check('pvp_damage' not in q and 'combat_damage_player' not in q and 'recoil' not in q and '~damage_self($damage);' in q,
      'the rebound is its own queue straight to ~damage_self: it cannot set off recoil, vengeance or Smite')
q = PVP.split('[queue,recoil_damage]', 1)[1].split('\n[', 1)[0]
check('vengeance' not in q, '...nor can recoil\'s rebound set off vengeance')
CQ = read('scripts/player/scripts/combat_clearqueue.rs2')
check(CQ.count('clearqueue(vengeance_damage);') == 2, 'death clears a pending rebound, both ways round, as it does recoil\'s')
check('return(max(1, scale(75, 100, min($damage, stat(hitpoints)))));' in VENG,
      '75% of the damage the hit did, rounded down, never under 1')
check(re.search(r'\^vengeance_cooldown_ticks = 50\b', read('scripts/skill_magic/configs/lunar.constant')) is not None
      and VENG.count('%vengeance_cooldown = add(map_clock, ^vengeance_cooldown_ticks);') == 2,
      'one 50-tick cooldown, set on the caster by both spells')
check('if (.%option_aid = ^aid_no)' in VENG, 'Vengeance Other asks for Accept Aid')
check(re.search(r'(?ms)^\[vengeance\]\ntype=boolean\nprotect=no', read('scripts/skill_magic/configs/lunar.varp')) is not None,
      '%vengeance is temp (gone at logout) and writable through the secondary pointer')

# ============================================================================ 5
print('5. astral runes and the altar')
objs = read('pack/obj.pack')
check(re.search(r'(?m)^\d+=astralrune$', objs) is not None, 'astralrune is an obj')
check('astralrune' in read('scripts/storage_items/configs/rune_pouch.enum'), '...that the rune pouch holds')
RC = read('scripts/skill_runecraft/configs/runecraft.dbrow').split('[runecraft_astral]', 1)[-1]
check('data=rune,astralrune' in RC and 'data=level,82' in RC and 'data=require_blankrune_high,true' in RC,
      'the astral row: level 82, pure essence')
LOC = read('scripts/areas/area_lunar_isle/configs/lunar_isle.loc').split('[astral_altar]', 1)[-1].split('\n[', 1)[0]
check('category=rc_altar' in LOC and 'param=rune_type,^astral' in LOC and 'op2=Pray' in LOC,
      'the Astral altar crafts (rc_altar) and prays')

# ============================================================================ 6
print('6. the generator still makes the checked-in book')
# LostCityServer is content's parent in the standard layout; LOSTCITYSERVER points elsewhere
LCS = os.environ.get('LOSTCITYSERVER', os.path.dirname(C))
gen = os.path.join(LCS, 'tools', 'models', 'genlunar474.py')
cache = os.path.join(LCS, 'caches', '474 cache')
if not (os.path.exists(gen) and os.path.isdir(cache)):
    print('  skip genlunar474.py and the 474 cache are not beside this checkout')
else:
    tmp = tempfile.mkdtemp()
    try:
        for d in ('tools', 'fonts', 'sprites', 'scripts/skill_magic/interfaces'):
            shutil.copytree(os.path.join(C, d), os.path.join(tmp, d))
        os.makedirs(os.path.join(tmp, 'pack'))
        for f in ('interface.pack', 'interface.order'):
            shutil.copy(os.path.join(C, 'pack', f), os.path.join(tmp, 'pack', f))
        r = subprocess.run([sys.executable, gen, cache, '--content=' + tmp], capture_output=True, text=True)
        same = r.returncode == 0 and open(os.path.join(tmp, IF), 'rb').read() == open(os.path.join(C, IF), 'rb').read()
        check(same, 'byte for byte: %s' % ('yes' if same else (r.stderr.strip().split('\n')[-1] if r.returncode else 'it differs')))
        same = open(os.path.join(tmp, 'pack', 'interface.pack'), 'rb').read() == open(os.path.join(C, 'pack', 'interface.pack'), 'rb').read()
        check(same, '...and its ids are the ones in interface.pack')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

print()
print('%d FAILED' % fails if fails else 'ALL PASS')
sys.exit(1 if fails else 0)
