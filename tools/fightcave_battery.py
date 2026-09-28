"""Battery for the TzHaar Fight Cave.

The cave is 63 waves of monsters that the cache already had the art for and no content at all.
What can break silently here is not the fighting - that is the engine's own combat - it is the
ARITHMETIC and the ADDRESSING: a wave table off by one tier, a spawn point where a five-tile Jad
does not fit, a monster counted from the instance next door, an npc_add duration the engine's own
validator rejects at runtime while compiling perfectly.

So nothing here is compared against itself. The monsters' numbers come from tools/fightcavespec.json,
which records the OSRS cache's records; the wave table is GENERATED from the enum's own thresholds
and checked against thirteen cells of the wiki's table; and the arena's geometry is re-measured off
maps/m37_79.jm2 every run rather than trusted from the spec.

    python3 tools/fightcave_battery.py
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='', errors='replace').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def blocks(txt):
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[([\w.]+)\]', b)
        if not m: continue
        d = {}
        for l in b.split('\n')[1:]:
            l = l.split('//')[0].strip()
            if '=' in l:
                k, v = l.split('=', 1)
                d.setdefault(k, []).append(v)
        out[m.group(1)] = d
    return out

def consts(txt):
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r'(?m)^\^(\w+)\s*=\s*(.+?)\s*$', txt)}

def param(d, key):
    for pv in d.get('param', []):
        k, _, v = pv.partition(',')
        if k == key: return v
    return None

def seqframes(txt):
    """{seq name: [frame names]} out of a .seq config - enough to answer "is this seq real" and
    "how many frames does it hold"."""
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[([\w.]+)\]', b)
        if m: out[m.group(1)] = re.findall(r'(?m)^frame\d+=(\S+)', b)
    return out

SPEC = json.loads(read('tools/fightcavespec.json'))
MON = SPEC['monsters']
CONST = consts(read('scripts/minigames/game_fightcave/configs/fightcave.constant'))
ENUM = read('scripts/minigames/game_fightcave/configs/fightcave.enum')
RS2 = read('scripts/minigames/game_fightcave/scripts/fightcave.rs2')
MRS2 = read('scripts/minigames/game_fightcave/scripts/fightcave_monsters.rs2')
REW = read('scripts/minigames/game_fightcave/scripts/fightcave_reward.rs2')
ALLNPC = blocks(read('scripts/_unpack/377/all.npc'))
ALLOBJ = blocks(read('scripts/_unpack/377/all.obj'))
ALLSEQ = blocks(read('scripts/_unpack/377/all.seq'))
DEATH = read('scripts/player/scripts/death.rs2')
MELEE = read('scripts/skill_combat/scripts/npc/npc_combat_melee.rs2')
# The cave's animations, converted from OSRS, plus the one the pet round converted first.
SEQS_OSRS = dict(seqframes(read('scripts/minigames/game_fightcave/configs/fightcave.seq')),
                 **seqframes(read('scripts/npc/configs/boss_pets.seq')))

def enumrows(name):
    b = ENUM.split('[' + name + ']', 1)[-1].split('\n[', 1)[0]
    return dict(m.groups() for m in re.finditer(r'(?m)^val=([^,]+),(.+)$', b))

# ============================================================================ the arena, measured
BLOCK_SHAPES = {0, 1, 2, 3, 9, 10, 11}

def entry_const():
    """The entry tile as ^fightcave_entry states it. NOT as the spec states it: a check that reads
    the spec and then floods from the spec compares the spec with itself, and the mutation run is
    what said so - moving ^fightcave_entry onto the clipped tile under the exit loc went unnoticed."""
    m = re.fullmatch(r'0_%s_(\d+)_(\d+)' % SPEC['arena']['square'], CONST['fightcave_entry'])
    return (int(m.group(1)), int(m.group(2))) if m else (-1, -1)

def pack(name):
    return {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/' + name).split('\n') if '=' in l)}

def npc_spawns(sq, name):
    """Where one npc is spawned in a square. The .jm2 stores npc IDS, not names - grepping the name
    finds nothing and reads as "no spawns anywhere"."""
    want = pack('npc.pack').get(name)
    out = []
    t = read('maps/m%s.jm2' % sq)
    if '==== NPC ====' not in t: return out
    for l in t.split('==== NPC ====', 1)[1].split('\n====', 1)[0].split('\n'):
        m = re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+):\s*(\d+)', l)
        if m and int(m.group(4)) == want:
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return out

def fits1(x, z):
    """Walkable in its own right, rather than merely being the tile the flood was seeded on - a
    flood counts its seed whether anything can stand there or not."""
    return any((0, x + dx, z + dz) in REACH for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))

def arena():
    """(reachable tiles, blocked tiles) of m37_79 level 0, flooded from the entry tile."""
    t = read('maps/m%s.jm2' % SPEC['arena']['square'])
    blocked = set()
    for l in t.split('==== MAP ====', 1)[1].split('\n====', 1)[0].split('\n'):
        m = re.match(r'^\s*(\d) (\d+) (\d+): ?(.*)', l)
        if not m: continue
        fl = re.search(r'\bf(\d+)', m.group(4))
        if fl and int(fl.group(1)) & 1:
            blocked.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    locs = []
    for l in t.split('==== LOC ====', 1)[1].split('\n', 1)[1].split('\n'):
        m = re.match(r'^\s*(\d) (\d+) (\d+): (\d+) (\d+)', l)
        if not m: continue
        lv, x, z, oid, sh = (int(m.group(k)) for k in (1, 2, 3, 4, 5))
        locs.append((oid, lv, x, z))
        if sh in BLOCK_SHAPES: blocked.add((lv, x, z))
    ex, ez = entry_const()
    start = (0, ex, ez)
    seen = {start}; q = [start]
    while q:
        lv, x, z = q.pop()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (lv, x + dx, z + dz)
            if 0 <= n[1] < 64 and 0 <= n[2] < 64 and n not in seen and n not in blocked:
                seen.add(n); q.append(n)
    return seen, locs

print('1. the arena is a place a player can be put, and a five-tile monster can stand in it')
REACH, LOCS = arena()
ex, ez = entry_const()
check(list((ex, ez)) == SPEC['arena']['entry'] and (0, ex, ez) in REACH and fits1(ex, ez),
      '^fightcave_entry is the tile the spec measured from, and a tile a player can stand on: %d,%d'
      % (ex, ez))
check(len(REACH) == SPEC['arena']['reachable_tiles'],
      'the reachable arena is the size the spec measured: %d' % len(REACH))
def fits5(x, z):
    return all((0, x + dx, z + dz) in REACH for dx in range(5) for dz in range(5))
five = [(x, z) for (lv, x, z) in REACH if fits5(x, z)]
check(len(five) == SPEC['arena']['tiles_fitting_size5'],
      '...of which the spec\'s count have a 5x5 clear block: %d' % len(five))
for k, (x, z) in sorted(SPEC['arena']['spawns'].items()):
    check((x, z) in five, 'the %s spawn is a tile a five-tile monster fits on' % k.upper())
    want = '0_%s_%d_%d' % (SPEC['arena']['square'], x, z)
    check(CONST.get('fightcave_spawn_' + k) == want,
          '...and ^fightcave_spawn_%s is that tile: %s' % (k, CONST.get('fightcave_spawn_' + k)))
pts = list(SPEC['arena']['spawns'].values())
closest = min(abs(a[0]-b[0]) + abs(a[1]-b[1]) for i, a in enumerate(pts) for b in pts[i+1:])
check(closest == SPEC['arena']['closest_two_spawns'],
      'no two spawn points are closer than the spec measured: %d tiles' % closest)
# the two doors, and that something answers them
for key, lbl in (('city_loc', 'fightcave_enter'), ('exit_loc', 'fightcave_leave')):
    nm = SPEC['arena'][key]
    check('[oploc1,%s] @%s;' % (nm, lbl) in RS2, '%s has a handler' % nm)
    check(param(ALLNPC.get(nm, {}), 'x') is None, '...(and %s is a loc, not an npc)' % nm)
check('0_%s' % SPEC['arena']['square'] in CONST.get('fightcave_template', ''),
      'the template square is the arena itself: %s' % CONST.get('fightcave_template'))
check(int(CONST['fightcave_zones']) * 8 == 64,
      'and the instance copies all 64 tiles of it: %s zones a side' % CONST['fightcave_zones'])

# ============================================================================ 2
print('2. every monster carries the cache\'s numbers, its tier and a death that ends the wave')
for name, s in sorted(MON.items(), key=lambda kv: kv[1]['tier']):
    d = ALLNPC.get(name, {})
    check(bool(d), '%s has a config block' % name)
    check(d.get('vislevel', [None])[0] == str(s['level']), '...level %d' % s['level'])
    got = [d.get(k, ['1'])[0] for k in ('attack', 'defence', 'strength', 'hitpoints', 'ranged', 'magic')]
    check(got == [str(v) for v in s['stats']], '...with the cache\'s stats %s' % ','.join(got))
    check(d.get('size', ['1'])[0] == str(s['size']),
          '...and the size the art record already had: %d' % s['size'])
    check(param(d, 'fightcave_tier') == str(s['tier']), '...tagged tier %d' % s['tier'])
    for k in ('attack_anim', 'defend_anim', 'death_anim'):
        a = param(d, k)
        # The roster wears OSRS animations now, so a seq is real if it is in the cave's own
        # converted set or - for Jad's stand, which the pet round converted first - in the pet's.
        check(a is not None and (a in ALLSEQ or a in SEQS_OSRS),
              '...%s is a real seq: %s' % (k, a))
    check(param(d, 'damagetype') is not None, '...and it has a damage type at all')
    check('[ai_queue3,%s]' % name in MRS2, '...and its death is hooked')
# the five b duplicates the cache carries and the wave builder does not use
for b in ('_1b', '_2b', '_3b', '_4b', '_5b'):
    nm = 'tzhaar_fightcave_swarm' + b
    if nm not in ALLNPC: continue
    check(param(ALLNPC[nm], 'fightcave_tier') is None,
          '%s is left as the cache left it, so it cannot turn up in a wave' % nm)

# ============================================================================ 3
print('3. the wave table, generated from the enum and checked against the wiki')
TH = {int(k): int(CONST[v.lstrip('^')]) for k, v in enumrows('fightcave_tier_threshold').items()}
NPCOF = {int(k): v for k, v in enumrows('fightcave_tier_npc').items()}
check(sorted(TH) == [1, 2, 3, 4, 5], 'five tiers have a threshold')
check([TH[t] for t in sorted(TH)] == [1, 3, 7, 15, 31],
      '...and they are the 2^k-1 series: %s' % [TH[t] for t in sorted(TH)])
check(all(NPCOF[t] in ALLNPC for t in sorted(NPCOF)), 'each tier names an npc that exists')
check(sorted(int(t) for t in NPCOF) == [1, 2, 3, 4, 5], '...one per tier, 1 to 5')
def wave(n):
    out = []; m = n
    while m > 0:
        for t in sorted(TH, reverse=True):
            if m >= TH[t]:
                out.append(t); m -= TH[t]; break
        else:
            return None                      # no tier fits: the table would loop for ever
    return out
bad = [n for n in range(1, SPEC['wave_boundaries']['last_wave'] + 1) if wave(n) is None]
check(not bad, 'every wave from 1 to 62 terminates: %s' % (bad[:5] or 'yes'))
for n, want in sorted((int(k), v) for k, v in SPEC['wave_anchors'].items()):
    got = wave(n)
    check(got == want, 'wave %d is the wiki\'s: %s' % (n, got))
B = SPEC['wave_boundaries']
for tier, key in ((3, 'tokxil_first_heads'), (4, 'mejkot_first_heads'), (5, 'ketzek_first_heads')):
    n = B[key]
    check(wave(n) == [tier] and max(wave(n - 1)) < tier,
          'tier %d first heads a wave at %d and not before' % (tier, n))
check(wave(B['last_wave']) == [5, 5], 'the last ordinary wave is two of the top tier')
check(int(CONST['fightcave_jad_wave']) == B['jad_wave'] == int(CONST['fightcave_waves']),
      'and wave %d is TzTok-Jad, alone' % B['jad_wave'])
check('if ($wave >= ^fightcave_jad_wave) {' in RS2 and 'tzhaar_fightcave_swarm_boss)' in RS2,
      '...which the wave builder spawns instead of composing anything')
cyc = enumrows('fightcave_cycle_spawn')
check(len(cyc) == int(CONST['fightcave_cycle']) == 15,
      'the spawn cycle is 15 steps long: %d' % len(cyc))
check([int(cyc[str(i)]) for i in range(15)] == [0, 1, 2, 3, 1, 0, 4, 3, 2, 0, 1, 4, 3, 2, 4],
      '...in the order the wiki gives: SE SW C NW SW SE S NW C SE SW S NW C S')

# ============================================================================ 4
print('4. the instance is addressed, counted and freed correctly')
check('npc_add($at, $type, ^fightcave_npc_life);' in RS2,
      'a spawned monster is given a real lifetime')
check(int(CONST['fightcave_npc_life']) >= 1,
      '...which is not 0, because DurationValid rejects that at RUNTIME: %s' % CONST['fightcave_npc_life'])
for f, src in (('fightcave.rs2', RS2), ('fightcave_monsters.rs2', MRS2)):
    bad = re.findall(r'npc_add\([^;]*,\s*0\)', src)
    check(not bad, '%s adds no npc with a 0 duration: %s' % (f, bad[:2] or 'none'))
ALIVE = RS2.split('[proc,fightcave_alive]', 1)[-1].split('\n[', 1)[0]
check('npc_param(fightcave_tier) ! null' in ALIVE, 'the alive count tests the tier param')
check('instance_find(npc_coord) = %fightcave_instance' in ALIVE,
      '...AND the instance, so the cave next door cannot hold this wave open')
END = RS2.split('[proc,fightcave_end]', 1)[-1].split('\n[', 1)[0]
check(END.index('p_teleport(^fightcave_outside);') < END.index('instance_delete($inst);'),
      'the player is teleported out before the instance is deleted, not after')
check('%fightcave_instance = null;' in END, '...and the pointer is cleared with it')
BUILD = RS2.split('[proc,fightcave_build]', 1)[-1].split('\n[', 1)[0]
check('instance_delete($base);' in BUILD,
      'a half-built cave is deleted rather than entered')
check('queue*(fightcave_died, 0)(npc_uid);' in MRS2,
      'a monster\'s death reaches the player through a queue, which is where the protected pointer is')
check('[queue,fightcave_died]' in RS2, '...and that is what fightcave_died is')

# ============================================================================ 5
print('5. the rewards, and that they are the only source either of them has')
def tok(n): return n * (n + 1) if n > 0 else 0
check(tok(int(CONST['fightcave_waves'])) + int(CONST['fightcave_tokkul_jad'])
      == int(CONST['fightcave_full_run_tokkul']) == SPEC['tokkul']['full_run'],
      'a full run pays %d Tokkul, which is the figure the wiki quotes on its own'
      % SPEC['tokkul']['full_run'])
check('multiply($waves, add($waves, 1))' in REW,
      'and the formula in the script is the wiki\'s N * (N + 1)')
check('~obj_giveorbank(tzhaar_cape_fire, 1);' in REW, 'killing Jad hands over the Fire cape')
check('inv_add(bank, $obj, $count);' in REW,
      '...and nothing is dropped on the floor of an instance that is about to be deleted')
def givers(obj):
    hits = []
    for root, _, fs in os.walk(os.path.join(C, 'scripts')):
        for f in sorted(fs):
            if not f.endswith('.rs2'): continue
            src = open(os.path.join(root, f), newline='', errors='replace').read()
            if re.search(r'(inv_add|obj_add|~obj_giveorbank)\([^;]*\b%s\b' % obj, src):
                hits.append(f)
    return sorted(hits)
check('tzhaar_cape_fire' in ALLOBJ and 'tzhaar_token' in ALLOBJ, 'both rewards are real objs')
check(givers('tzhaar_cape_fire') == ['fightcave_reward.rs2'],
      'the cave is the ONLY source of a Fire cape: %s' % (', '.join(givers('tzhaar_cape_fire')) or 'nothing'))
# Tokkul is a different case and the check says so rather than pretending otherwise: the four
# TzHaar city monsters already dropped it, so the cave is a new source and not the first one.
check(givers('tzhaar_token') == ['fightcave_exchange.rs2', 'fightcave_reward.rs2',
                                 'tzhaar_hur.rs2', 'tzhaar_ket.rs2', 'tzhaar_mej.rs2',
                                 'tzhaar_xil.rs2'],
      'and Tokkul comes from the cave, the cape exchange, and the four city drop tables that '
      'already had it: %s'
      % ', '.join(givers('tzhaar_token')))

# ============================================================================ 6
print('6. the mechanics that make it the Fight Cave rather than 63 waves of furniture')
KIH = ALLNPC['tzhaar_fightcave_swarm_1a']
check(param(KIH, 'prayer_drain') == '1', 'Tz-Kih drains a prayer point')
check('queue(fightcave_prayer_drain, 0, npc_param(prayer_drain));' in MELEE,
      '...and it is param-driven, not keyed on the npc type')
check(MRS2.count('tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);') == 2,
      'Tz-Kek splits into exactly two')
check(param(ALLNPC['tzhaar_fightcave_swarm_2spawn'], 'fightcave_tier') is not None,
      '...and the halves count towards the wave, so it cannot end with them alive')
MEJ = MRS2.split('[proc,mejkot_attack]', 1)[-1].split('\n[', 1)[0]
check('multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)' in MEJ,
      'Yt-MejKot only heals once it is below half health')
check(MEJ.index('~fightcave_melee(') < MEJ.index('~fightcave_heal_others;')
      and MEJ.split('~fightcave_heal_others;', 1)[1].strip() == '}',
      '...and the heal is the last thing it does, because it walks the npc pointer')
check(MRS2.count('.npc_queue(9, ^fightcave_heal_amount, 0);') == 2,
      'both healers heal through a queue on the target, since there is no .npc_statheal: %d of 2'
      % MRS2.count('.npc_queue(9, ^fightcave_heal_amount, 0);'))
JAD = ALLNPC['tzhaar_fightcave_swarm_boss']
anims = {param(JAD, k) for k in ('crushattack_anim', 'rangeattack_anim', 'magicattack_anim')}
check(len(anims) == 3 and all(a in SEQS_OSRS for a in anims),
      'TzTok-Jad has three distinct attack animations: %s' % ', '.join(sorted(anims)))
check(param(JAD, 'magicattack_anim') == 'osrs_seq_2656' and len(SEQS_OSRS['osrs_seq_2656']) >= 31,
      '...the 31-frame breath is the magic one')
check(param(JAD, 'rangeattack_anim') == 'osrs_seq_2652',
      '...the rear-and-slam with the splash on the ground is the ranged one')
JA = MRS2.split('[proc,jad_attack]', 1)[-1].split('\n[', 1)[0]
check('%fightcave_jad_called = 0 & npc_stat(hitpoints) <= ^fightcave_jad_heal_hp' in JA,
      'the healers come at %s hitpoints, once' % CONST['fightcave_jad_heal_hp'])
check(int(CONST['fightcave_jad_heal_hp']) < MON['tzhaar_fightcave_swarm_boss']['stats'][3],
      '...which is below his %d, or they would come the moment he spawned'
      % MON['tzhaar_fightcave_swarm_boss']['stats'][3])
check(MRS2.count('tzhaar_fightcave_swarm_boss_cleric, ^fightcave_npc_life);') == 1
      and 'while ($i < ^fightcave_jad_healers)' in MRS2,
      'and there are %s of them, from one loop' % CONST['fightcave_jad_healers'])
HUR = MRS2.split('[proc,hurkot_heal_jad]', 1)[-1].split('\n[', 1)[0]
check('.npc_type = tzhaar_fightcave_swarm_boss' in HUR, 'a Yt-HurKot heals Jad and only Jad')
check('npc_canreach = true' in MRS2.split('[proc,hurkot_attack]', 1)[-1].split('\n[', 1)[0],
      '...and fights back instead when something is next to it (where its swing reaches)')
check('if (~in_fightcave(coord) = true) {' in DEATH and '@fightcave_death;' in DEATH,
      'dying in the cave is caught before the ordinary death')
FD = RS2.split('[label,fightcave_death]', 1)[-1].split('\n[', 1)[0]
check('~player_death_lose_items' not in FD and '~pvp_death_lose_items' not in FD,
      '...and keeps the player\'s items, because the cave is safe')
check('~fightcave_end(sub(%fightcave_wave, 1));' in FD,
      '...and pays for the waves that were survived, not the one they died on')

# ============================================================================ 7
print('7. Tokkul is worth having, and the pet exists')
INV727 = blocks(read('scripts/_unpack/727/all.inv'))
TRADERS = blocks(read('scripts/areas/area_karamja/configs/tzhaar_traders.npc'))
SHOP = read('scripts/shop/scripts/shop.rs2')
SHOPPARAM = read('scripts/shop/configs/shopkeeper.param')
PETNPC = blocks(read('scripts/npc/configs/boss_pets.npc'))
PETOBJ = blocks(read('scripts/npc/configs/boss_pets.obj'))
PETSEQ = blocks(read('scripts/npc/configs/boss_pets.seq'))

# --- the currency, which said "coins" in six places
for what, needle in (('the till it counts', 'inv_total(inv, %shop_currency)'),
                     ('what it takes', 'inv_del(inv, %shop_currency, $added_amt)'),
                     ('what it pays', 'inv_add(inv, %shop_currency, $total_value)'),
                     ('the space it checks', 'inv_itemspace(inv, %shop_currency,'),
                     ('what it refuses to buy', '$item = %shop_currency'),
                     ('what it says you are short of, in both places it prints it', None)):
    if needle is None:
        # TWICE, not once: the currency's name is printed in the price quote AND in "you don't have
        # enough", and testing for presence let the second be replaced by the word coins unnoticed.
        check(SHOP.count('oc_name(%shop_currency)') == 2,
              'the shop reads its currency for %s: %d' % (what, SHOP.count('oc_name(%shop_currency)')))
    else:
        check(needle in SHOP, 'the shop reads its currency for %s' % what)
check(SHOP.count('%shop_currency =') == 2,
      '...and the currency is set in exactly those two places and nowhere else: %d'
      % SHOP.count('%shop_currency ='))
check('%shop_currency = coins;' in SHOP.split('[proc,openshop]', 1)[-1].split('\n[', 1)[0],
      '~openshop still sets coins, so its 38 callers did not have to change')
check('%shop_currency = npc_param(shop_currency);' in SHOP,
      '...and a shopkeeper\'s own shop reads the param')
cp = SHOPPARAM.split('[shop_currency]', 1)[-1].split('\n[', 1)[0]
check('default=coins' in cp,
      '...whose default is coins, so every shopkeeper that predates this keeps its till')

# --- the three traders and the three shops that had nobody to open them
WANT = {'tzhaar_shopkeeper_equipment': 'tzhaar_shop_equipment',
        'tzhaar_shopkeeper_oreandgem': 'tzhaar_shop_oreandgem',
        'tzhaar_shopkeeper_rune': 'tzhaar_shop_rune'}
check(sorted(TRADERS) == sorted(WANT), 'there are three TzHaar traders and no strangers')
for npc, shop in sorted(WANT.items()):
    d = TRADERS.get(npc, {})
    check(param(d, 'owned_shop') == shop, '%s owns %s' % (npc, shop))
    check(param(d, 'shop_currency') == 'tzhaar_token', '...and trades in Tokkul')
    check(d.get('category', [None])[0] == 'shop_keeper',
          '...on the category the shop triggers hang off')
    check(d.get('op3', [None])[0] == 'Trade' and d.get('op1', [None])[0] == 'Talk-to',
          '...with Trade and Talk-to')
    check('op2' not in d and d.get('vislevel', [None])[0] == 'hide',
          '...and cannot be attacked, so you can stand beside it')
    s = INV727.get(shop, {})
    stock = sorted(int(k[5:]) for k in s if re.fullmatch(r'stock\d+', k))
    check(stock == list(range(1, len(stock) + 1)),
          '%s stock numbering has no gaps or duplicates: %d entries' % (shop, len(stock)))
    check(len(stock) > 0, '...and it is not empty')
    check(all(len(v[0].split(',')) == 3 for k, v in s.items() if re.fullmatch(r'stock\d+', k)),
          '...and every line has its count and restock rate')
# the rune shop was the one with every line commented out
RUNE = INV727['tzhaar_shop_rune']
check(len(RUNE) and sorted(v[0].split(',')[0] for k, v in RUNE.items() if k.startswith('stock'))
      == ['airrune', 'bodyrune', 'chaosrune', 'deathrune', 'earthrune', 'firerune', 'mindrune', 'waterrune'],
      'the rune shop sells the eight runes its own commented-out lines listed')
# and the equipment shop still sells the whole obsidian set
EQUIP = {v[0].split(',')[0] for k, v in INV727['tzhaar_shop_equipment'].items() if k.startswith('stock')}
check(EQUIP == {'tzhaar_throwingring', 'tzhaar_splitsword', 'tzhaar_spikeshield', 'tzhaar_knife',
                'tzhaar_staff', 'tzhaar_mace', 'tzhaar_maul', 'tzhaar_cape_obsidian'},
      '...and the equipment shop the whole obsidian set: %d items' % len(EQUIP))
# spawned, and somewhere a player can reach
CITY = '38_80'
for npc in sorted(WANT):
    at = npc_spawns(CITY, npc)
    check(len(at) == 1, '%s is spawned once in m%s' % (npc, CITY))

# --- TzRek-Jad
PET, ITEM = 'bosspet_tzrek_jad', 'bosspet_tzrek_jad_item'
check(PET in PETNPC and ITEM in PETOBJ, 'TzRek-Jad exists as both an npc and an item')
check(param(PETNPC[PET], 'pet_item_id') == ITEM, '...and the npc names the item')
check(param(PETOBJ[ITEM], 'follower_id') == PET, '...and the item names the npc')
check(PETNPC[PET].get('category', [None])[0] == 'bosspet'
      and PETOBJ[ITEM].get('category', [None])[0] == 'bosspet',
      '...both on the category the four follower triggers hang off')
petseqs = [PETNPC[PET].get('readyanim', [''])[0], PETNPC[PET].get('walkanim', [''])[0]]
check(all(s.startswith('osrs_seq_') for s in petseqs),
      'both its animations are converted from OSRS, so they share a base and still walk-merge: %s'
      % ', '.join(petseqs))
check(all(s in PETSEQ for s in petseqs), '...and both are present in boss_pets.seq')
check(PETNPC[PET].get('resizeh', [None])[0] == '20',
      'and it is rendered at the cache\'s own 20, which is the joke')
ROLL = REW.split('[proc,fightcave_pet_roll]', 1)[-1].split('\n[', 1)[0]
check('random(^fightcave_pet_rate) ! 0' in ROLL, 'the pet rolls at ^fightcave_pet_rate')
check(int(CONST['fightcave_pet_rate']) == 200, '...which is 200, the rate for a plain kill')
check('~obj_gettotal(%s) > 0' % ITEM in ROLL and ('%%follower_obj = %s' % ITEM) in ROLL,
      '...and never gives a second one, counting pack, bank, worn and the one out following you')
check('~obj_giveorbank(%s, 1);' % ITEM in ROLL and 'obj_add' not in ROLL,
      '...and hands it over rather than dropping it in an instance about to be deleted')
check('~fightcave_pet_roll;' in REW.split('[proc,fightcave_reward]', 1)[-1].split('\n[', 1)[0],
      'and killing Jad is what rolls it')

# ============================================================================ 8
print('8. The roster wears OSRS art, models and animations both')
ART = SPEC['roster_art']
FCSEQ = blocks(read('scripts/minigames/game_fightcave/configs/fightcave.seq'))
PETSEQ2 = blocks(read('scripts/npc/configs/boss_pets.seq'))
MODELPACK = {l.split('=', 1)[1] for l in read('pack/model.pack').split('\n') if '=' in l}

def seqinfo(d):
    """(frame count, priority) of a .seq block, straight out of the config."""
    return (len([k for k in d if re.fullmatch(r'frame\d+', k)]),
            int(d['priority'][0]) if 'priority' in d else None)

def ob2_faces(path):
    """(face info, face colours) out of a 377 .ob2. Section order is Model.java's, and the walk is
    reconciled against the file length so a wrong order cannot return plausible bytes - the same
    guard tools/superior_battery.py's vertex_labels() uses."""
    b = open(os.path.join(C, path), 'rb').read(); n = len(b); o = n - 18
    g2 = lambda i: (b[i] << 8) | b[i + 1]
    vc, fc, tc = g2(o), g2(o + 2), b[o + 4]
    f_tex, f_pri, f_alpha, f_flabel, f_vlabel = b[o + 5], b[o + 6], b[o + 7], b[o + 8], b[o + 9]
    xlen, ylen, zlen, flen = g2(o + 10), g2(o + 12), g2(o + 14), g2(o + 16)
    p = vc + fc
    if f_pri == 255: p += fc
    if f_flabel == 1: p += fc
    info = list(b[p:p + fc]) if f_tex == 1 else [0] * fc
    col_at = p + (fc if f_tex == 1 else 0) + (vc if f_vlabel == 1 else 0) + (fc if f_alpha == 1 else 0) + flen
    if col_at + fc * 2 + tc * 6 + xlen + ylen + zlen != n - 18:
        raise ValueError('%s: section walk does not reconcile' % path)
    return info, [g2(col_at + 2 * i) for i in range(fc)]

for npc, d in sorted(ART['npcs'].items()):
    rec = ALLNPC[npc]
    # --- the models
    check([rec.get('model%d' % k, [None])[0] for k in range(1, len(d['models']) + 1)]
          == d['models'],
          '%s wears OSRS npc %d\'s %d model(s)' % (npc, d['osrs'], len(d['models'])))
    check(all('model%d' % k not in rec for k in range(len(d['models']) + 1, 6)),
          '...and no leftover model line from the 377 record it replaced')
    check(all(m in MODELPACK for m in d['models']), '...each with its own model.pack line')
    check(all(os.path.exists(os.path.join(C, 'models/npc', m + '.ob2')) for m in d['models']),
          '...and its own .ob2 on disk')
    check('recol1s' not in rec and 'recol1d' not in rec,
          '...and no recolour line, because OSRS bakes its recolours into the mesh')
    # --- the art numbers nobody had to change
    a = d['art']
    got = dict(ambient=rec.get('ambient', [None])[0], contrast=rec.get('contrast', [None])[0],
               size=rec.get('size', ['1'])[0], resizeh=rec.get('resizeh', [None])[0],
               resizev=rec.get('resizev', [None])[0])
    want = {k: (None if v is None else str(v)) for k, v in a.items()}
    check(got == want,
          '...and its ambient, contrast, size and resizes are the cache\'s own, unchanged: %s'
          % ', '.join('%s=%s' % (k, v) for k, v in sorted(want.items()) if v is not None))
    # --- the animations
    for field, (oid, was) in sorted(d['anims'].items()):
        want_name = 'osrs_seq_%d' % oid
        got_name = (rec.get(field, [None])[0] if field in ('readyanim', 'walkanim')
                    else param(rec, field))
        check(got_name == want_name,
              '%s.%s is %s, where the 377 record had %s' % (npc, field, want_name, was))
        blk = FCSEQ.get(want_name) or PETSEQ2.get(want_name)
        check(blk is not None, '...and %s is a real seq in the tree' % want_name)
        if blk is None or was not in ALLSEQ:
            continue
        ofr, opr = seqinfo(blk)
        wfr, wpr = seqinfo(ALLSEQ[was])
        check(ofr == wfr, '...and it holds the same %d frames %s holds' % (wfr, was))
        check((opr is None) == (wpr is None),
              '...and agrees with it on whether the animation takes priority at all')

# The pairing is only forced if (frames, priority) is unique inside the family, so that is the
# check - derived from all.seq every run, not asserted in the spec.
for npc, d in sorted(ART['npcs'].items()):
    stated = set(d['stated_by_record'].values())
    inferred = sorted({was for f, (oid, was) in d['anims'].items() if oid not in stated})
    sigs = [seqinfo(ALLSEQ[w]) for w in inferred if w in ALLSEQ]
    check(len(sigs) == len(set(sigs)),
          '%s: the %d animations that had to be inferred have %d distinct (frames, priority) '
          'signatures, so each has exactly one OSRS partner' % (npc, len(sigs), len(set(sigs))))

# Jad is the one family whose priorities do NOT carry across, so say so rather than let the
# priority-class check above imply they did.
JX = ART['jad_priority_exception']
jadseqs = {was: seqinfo(ALLSEQ[was])[0] for was in JX['frames']}
check(jadseqs == JX['frames'],
      'TzTok-Jad\'s three attacks are %s frames, all distinct, which is what separates them when '
      'the priority does not: 377 gives them %d and OSRS gives them %d'
      % (', '.join(str(v) for v in sorted(jadseqs.values())),
         JX['era377_attack_priority'], JX['osrs_attack_priority']))

# Nothing 377 left behind
# What became of the animations the roster dropped. This is NOT the per-field check above said
# twice: it asks who ELSE wears them, because the cave's Tok-Xil was borrowing the POH statue's
# models and the Fight Pit shares four of the six animation sets. Nothing there was touched, and
# the check is what says so.
NPCTXT = read('scripts/_unpack/377/all.npc')
def wearers(family):
    out = set()
    for b in re.split(r'(?m)^(?=\[)', NPCTXT):
        m = re.match(r'\[([\w.]+)\]', b)
        if m and re.search(r'=%s\w+' % family, b.split(']', 1)[1]):
            out.add(m.group(1))
    return sorted(out)
for family, left in (('firebat_', ['tzhaar_fightcave_swarm_1b', 'tzhaar_fightpit_swarm_1a',
                                   'tzhaar_fightpit_swarm_1b']),
                     ('lavabeast_', ['tzhaar_fightcave_swarm_2b', 'tzhaar_fightpit_swarm_2a',
                                     'tzhaar_fightpit_swarm_2b']),
                     ('magmaquris_', ['poh_tok_xil', 'tzhaar_fightcave_swarm_3b',
                                      'tzhaar_fightpit_swarm_3a', 'tzhaar_fightpit_swarm_3b']),
                     ('lizard_cleric_', ['tzhaar_fightcave_swarm_4b']),
                     ('igniferum_', ['tzhaar_fightcave_swarm_5b']),
                     ('lordmagmus_', [])):
    check(wearers(family) == left,
          'the 377 %s set is worn by %s now' % (family.rstrip('_'),
          ', '.join(left) if left else 'NOTHING AT ALL - TzTok-Jad was its only user'))
# And the five 'b' duplicates that still carry 377 art cannot turn up in a wave or on a map.
for k in range(1, 6):
    b = 'tzhaar_fightcave_swarm_%db' % k
    check(param(ALLNPC[b], 'fightcave_tier') is None and not npc_spawns('37_79', b)
          and not npc_spawns('38_80', b),
          '%s has no tier and no spawn, so its 377 art is never seen' % b)
check(not any(s in MRS2 for s in ('lizard_cleric_heal', 'lordmagmus_', 'igniferum_', 'magmaquris_')),
      'and the scripts name no 377 cave animation either - the healer\'s is osrs_seq_2639')
check(MRS2.count('npc_anim(osrs_seq_2639, 0);') == 2,
      '...in BOTH places it is played: the Yt-MejKot aura and the Yt-HurKot heal')

# Jad's mesh is the pet's, once, under the name of the thing it is
check('npc_bosspet_tzrek_jad_1' not in read('pack/model.pack')
      and not os.path.exists(os.path.join(C, 'models/npc/npc_bosspet_tzrek_jad_1.ob2')),
      'the old name of Jad\'s mesh is gone from the pack and the disk')
PETNPC2 = blocks(read('scripts/npc/configs/boss_pets.npc'))
check(PETNPC2['bosspet_tzrek_jad']['model1'][0] == 'npc_tztok_jad_1'
      == ALLNPC['tzhaar_fightcave_swarm_boss']['model1'][0],
      '...and TzRek-Jad and TzTok-Jad name the same one file, a resize apart')

import hashlib
newmodels = sorted({m for d in ART['npcs'].values() for m in d['models']})
hashes = {}
for m in newmodels:
    h = hashlib.sha1(open(os.path.join(C, 'models/npc', m + '.ob2'), 'rb').read()).hexdigest()
    hashes.setdefault(h, []).append(m)
dupes = {h: v for h, v in hashes.items() if len(v) > 1}
check(not dupes, 'no two of the %d imported meshes are the same bytes under two names: %s'
      % (len(newmodels), dupes or 'none'))
check(len(FCSEQ) == 34 and 'osrs_seq_2650' not in FCSEQ,
      'fightcave.seq holds 34 seqs and NOT osrs_seq_2650, which boss_pets.seq already had')
check('osrs_seq_2650' in PETSEQ2, '...and that one is still where the pet round put it')
texfaces = 0
for m in newmodels:
    info, col = ob2_faces('models/npc/' + m + '.ob2')
    texfaces += sum(1 for i in info if i & 2)
check(texfaces == 0,
      'and not one of the %d imported faces is textured, so every colour crossed over exactly: '
      '%d textured' % (sum(len(ob2_faces('models/npc/' + m + '.ob2')[1]) for m in newmodels), texfaces))

# ============================================================================ 9
print('9. The Fire cape exchange')
EX = SPEC['exchange']
XRS2 = read('scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2')
FCOBJ = blocks(read('scripts/minigames/game_fightcave/configs/fightcave.obj'))
PETOBJ2 = blocks(read('scripts/npc/configs/boss_pets.obj'))
OBJPACK = {l.split('=', 1)[1] for l in read('pack/obj.pack').split('\n') if '=' in l}
NPCPACK = {l.split('=', 1)[1] for l in read('pack/npc.pack').split('\n') if '=' in l}
ROLL2 = XRS2.split('[proc,fightcave_exchange_roll]', 1)[-1].split('\n[', 1)[0]

# --- the ladder
for key, const in (('cape', 'fightcave_exchange_cape_rate'), ('meta', 'fightcave_exchange_meta_rate'),
                   ('pet', 'fightcave_exchange_pet_rate')):
    # The label prints the CONSTANT, not the spec: these mutations move the spec, and a label
    # that quotes the mutated value matches the mutated output instead of the claim.
    check(int(CONST[const]) == EX['rates'][key], '^%s is %s' % (const, CONST[const]))
# No check here restates the three above by comparing them with each other: 1/100 > 1/50 = 1/50
# cannot fail unless one of those three has already failed, and a check that can only fail
# alongside another one steals its attribution. What IS independent is the order the code rolls
# them in, which is what makes the ladder a ladder.
order = [ROLL2.find(s) for s in ('^fightcave_exchange_cape_rate', '^fightcave_exchange_meta_rate',
                                 '^fightcave_exchange_pet_rate', '^fightcave_exchange_tokkul_min')]
check(all(x > 0 for x in order) and order == sorted(order),
      '...and the roll asks in the order the rates were chosen for - the 1/%d cape first, then the '
      '1/%d metamorphosis, then the 1/%d pet, Tokkul last - so one cape buys one thing'
      % (EX['rates']['cape'], EX['rates']['meta'], EX['rates']['pet']))
# ...and rarest first, which is what makes the order the RIGHT order rather than just an order.
# Retuning the three is what this catches: a cape made commoner than a pet would still roll first
# and would quietly stop being the prize.
check([EX['rates'][k] for k in ('cape', 'meta', 'pet')]
      == sorted((EX['rates'][k] for k in ('cape', 'meta', 'pet')), reverse=True),
      '...rarest first: 1/%d, 1/%d, 1/%d'
      % (EX['rates']['cape'], EX['rates']['meta'], EX['rates']['pet']))
check(ROLL2.count('return;') == 3,
      '...with a return after each hit, so a cape cannot pay twice')
check(int(CONST['fightcave_exchange_tokkul_min']) == EX['tokkul'][0]
      and int(CONST['fightcave_exchange_tokkul_max']) == EX['tokkul'][1]
      and 'calc(^fightcave_exchange_tokkul_min\n    + random(calc(^fightcave_exchange_tokkul_max '
          '- ^fightcave_exchange_tokkul_min + 1)))' in XRS2,
      'the consolation is a flat roll between %d and %d Tokkul inclusive' % tuple(EX['tokkul']))

# --- the cape it eats
check(XRS2.count('inv_del(inv, tzhaar_cape_fire, 1);') == 1,
      'exactly one line deletes the Fire cape')
check(XRS2.count('inv_total(inv, tzhaar_cape_fire) < 1') == 2,
      '...and the cape is checked TWICE: ~p_choice2 pauses, and a paused player can bank the thing '
      'they were just asked about')
# split on the CALL, not the word: the file's own header comment says "~p_choice2 pauses", and
# splitting on the bare name puts the whole header on the left and finds nothing there.
before, after = XRS2.split('~p_choice2(', 1)
check('inv_total(inv, tzhaar_cape_fire) < 1' in before
      and 'inv_total(inv, tzhaar_cape_fire) < 1' in after.split('inv_del', 1)[0],
      '...once on each side of the pause, and the delete comes after the second one')

# --- Mej-Jal, who had an op and no handler at all
MEJ = ALLNPC['tzhaar_fightcave_master']
check(MEJ.get('op1', [None])[0] == 'Talk-to' and MEJ.get('op3', [None])[0] == 'Exchange',
      'TzHaar-Mej-Jal has Talk-to and Exchange')
check('[opnpc1,tzhaar_fightcave_master]' in XRS2 and '[opnpc3,tzhaar_fightcave_master]' in XRS2,
      '...and BOTH have a handler now: op1 was in the cache with nothing behind it, which made the '
      'one npc who explains the cave a dead click')
check(XRS2.count('@multi3(') == 1
      and 'fightcave_exchange' in XRS2.split('@multi3(', 1)[1].split(');', 1)[0],
      '...and the exchange is reachable from the conversation as well as the right-click')

# --- the Infernal cape
CAPE, FIRE = 'tzhaar_cape_infernal', 'tzhaar_cape_fire'
check(CAPE in FCOBJ and CAPE in OBJPACK, 'the Infernal cape exists and is in obj.pack')
for k, v in sorted(EX['infernal_bonuses'].items()):
    check(param(FCOBJ[CAPE], k) == str(v), '...param %s is the cache\'s %d' % (k, v))
check(FCOBJ[CAPE].get('cost', [None])[0] == str(EX['infernal']['cost']),
      '...and the cost is the cache\'s %d' % EX['infernal']['cost'])
fire = ALLOBJ[FIRE]
same = [k for k in fire if k not in ('param',)]
check([k for k in same if k not in FCOBJ[CAPE]] == [],
      '...and the record is a line-for-line parallel of the Fire cape\'s: every field the Fire '
      'cape has, the Infernal cape has')
check(FCOBJ[CAPE].get('tradeable', [None])[0] == 'no' == fire.get('tradeable', [None])[0],
      '...including tradeable=no, which is how this fork ships the Fire cape')
check(len(FCOBJ[CAPE].get('param', [])) == len(EX['infernal_bonuses']),
      '...and it carries exactly the %d bonuses and no invented thirteenth'
      % len(EX['infernal_bonuses']))
# --- the cape's own texture, which is a slot this fork added
INF = EX['infernal']
TEXPACK = {int(l.split('=')[0]): l.split('=', 1)[1]
           for l in read('pack/texture.pack').split('\n') if '=' in l}
check(TEXPACK.get(INF['local_texture']) == INF['texture_name'],
      'texture %d is %s in texture.pack' % (INF['local_texture'], INF['texture_name']))
check(max(TEXPACK) == INF['local_texture'] and sorted(TEXPACK) == list(range(max(TEXPACK) + 1)),
      '...and the texture ids are contiguous 0-%d, which the packer requires and the client\'s '
      'own eviction loop assumes' % max(TEXPACK))
texpng = os.path.join(C, 'textures', INF['texture_name'] + '.png')
check(os.path.exists(texpng), '...and its image is in content/textures')
if os.path.exists(texpng):
    import hashlib, struct, zlib

    def png_pixels(path):
        """(width, height, RGBA bytes) from a non-interlaced 8-bit PNG, using zlib and nothing else.

        THE PIXELS, NOT THE FILE. Hashing the file was the first thing tried and it was wrong: the
        bridge that copies a file to the laptop re-encodes PNGs - same pixels, 5,770 more bytes -
        so a file hash fails there for a reason that has nothing to do with the image."""
        raw = open(path, 'rb').read()
        if raw[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('not a PNG')
        w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', raw[16:29])
        if (depth, interlace) != (8, 0) or ctype not in (2, 6):
            raise ValueError('only 8-bit non-interlaced RGB/RGBA is read here')
        chan = 4 if ctype == 6 else 3
        idat, p = b'', 8
        while p < len(raw):
            n = struct.unpack('>I', raw[p:p + 4])[0]
            if raw[p + 4:p + 8] == b'IDAT':
                idat += raw[p + 8:p + 8 + n]
            p += 12 + n
        d = zlib.decompress(idat)
        stride = w * chan
        out = bytearray(); prev = bytearray(stride)
        for y in range(h):
            f = d[y * (stride + 1)]
            line = bytearray(d[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
            for x in range(stride):
                a = line[x - chan] if x >= chan else 0
                b = prev[x]
                c = prev[x - chan] if x >= chan else 0
                if f == 1: line[x] = (line[x] + a) & 0xff
                elif f == 2: line[x] = (line[x] + b) & 0xff
                elif f == 3: line[x] = (line[x] + ((a + b) >> 1)) & 0xff
                elif f == 4:
                    pp = a + b - c
                    pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                    line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xff
                elif f != 0:
                    raise ValueError('unknown PNG filter %d' % f)
            out += line; prev = line
        return w, h, bytes(out), chan

    w, h, pix, chan = png_pixels(texpng)
    check((w, h) == (128, 128), '...at 128x128, like the other 50: %dx%d' % (w, h))
    check(hashlib.sha1(pix).hexdigest() == INF['texture_pixels_sha1'],
          '...and its pixels are OSRS sprite %d\'s own, unaltered' % INF['osrs_sprite'])
    cols = {pix[i:i + 3] for i in range(0, len(pix), chan)}
    check(len(cols) == INF['texture_colours'] <= 255,
          '...in %d colours, under the 255 above which the packer quantises silently' % len(cols))

for m, n in (('obj_tzhaar_cape_infernal', 'the inventory model'),
             ('obj_tzhaar_cape_infernal_manwear', 'the male one'),
             ('obj_tzhaar_cape_infernal_womanwear', 'the female one')):
    info, col = ob2_faces('models/obj/' + m + '.ob2')
    lit = [c for c, i in zip(col, info) if i & 2]
    # Measured counts in the label, spec values in the comparison, because the mutations for
    # these move the SPEC - and a label quoting the spec would move with it.
    check(len(lit) == INF['lava_faces'] and set(lit) == {INF['local_texture']},
          '%s carries its %d crust faces on texture %s, OSRS %d\'s own image'
          % (n, len(lit), ', '.join(str(x) for x in sorted(set(lit))), INF['osrs_texture']))
    check(INF['wrong_hsl'] not in col,
          '...and no face of it is left on the olive green that came of reading the OSRS texture '
          'index by position')
# The geometry, which the invisible cape was blamed on and was never at fault: the crust layer
# was dying mid-draw on a negative palette index in the client (see fightcavespec's note), and
# the reversed-winding build shipped to chase it turned the cape inside out - a plain red sheet,
# the lining seen from outside. A file hash is the right check: each model is a deterministic
# function of the cache, and both a re-import that "fixes" the winding again and one that picks
# up a different source model change every byte.
import hashlib as _h
for m, sha in sorted(INF['model_sha1'].items()):
    got = _h.sha1(open(os.path.join(C, 'models/obj', m + '.ob2'), 'rb').read()).hexdigest()
    check(got == sha,
          "%s is the cache's own geometry, %s" % (m, INF['winding']))

finfo, fcol = ob2_faces('models/obj/obj_tzhaar_cape_fire.ob2')
check(sum(1 for i in finfo if i & 2) == INF['fire_cape_lava_faces'],
      'and the Fire cape still wears its own %d lava faces, untouched by any of this'
      % sum(1 for i in finfo if i & 2))

# Nothing in the tree may name a texture slot that does not exist: that is the failure the
# client's getTexels() guard exists to survive, and it should never be reached.
worst, worstfile = -1, None
for sub in ('npc', 'obj', 'loc', 'com', 'idk', 'spot'):
    d = os.path.join(C, 'models', sub)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not f.endswith('.ob2'):
            continue
        try:
            info, col = ob2_faces('models/%s/%s' % (sub, f))
        except ValueError:
            continue
        for c, i in zip(col, info):
            if i & 2 and c > worst:
                worst, worstfile = c, '%s/%s' % (sub, f)
check(worst <= max(TEXPACK),
      'and the highest texture id any model in the tree names is %d (%s), which texture.pack has'
      % (worst, worstfile))

# --- JalRek-Jad
JPET, JITEM = 'bosspet_jalrek_jad', 'bosspet_jalrek_jad_item'
check(JPET in PETNPC2 and JITEM in PETOBJ2 and JPET in NPCPACK and JITEM in OBJPACK,
      'JalRek-Jad exists as an npc and an item, both packed')
check(param(PETNPC2[JPET], 'pet_item_id') == JITEM and param(PETOBJ2[JITEM], 'follower_id') == JPET,
      '...and the two name each other')
check(PETNPC2[JPET].get('category', [None])[0] == 'bosspet'
      == PETOBJ2[JITEM].get('category', [None])[0],
      '...on the category the four follower triggers hang off')
jseqs = [PETNPC2[JPET].get('readyanim', [''])[0], PETNPC2[JPET].get('walkanim', [''])[0]]
check(jseqs == ['osrs_seq_%d' % EX['jalrek']['readyanim'], 'osrs_seq_%d' % EX['jalrek']['walkanim']],
      '...wearing the cache\'s own pair, %s' % ', '.join(jseqs))
check(all(s in PETSEQ2 for s in jseqs),
      '...both converted from OSRS so they share a base and still walk-merge')
check(PETNPC2[JPET].get('resizeh', [None])[0] == str(EX['jalrek']['resize'])
      and PETNPC2[JPET].get('ambient', [None])[0] == str(EX['jalrek']['ambient']),
      '...at the cache\'s resize %d and ambient %d' % (EX['jalrek']['resize'], EX['jalrek']['ambient']))

# --- who can roll what
META = XRS2.split('[proc,fightcave_metamorphose]', 1)[-1].split('\n[', 1)[0]
HAS = XRS2.split('[proc,fightcave_has_pet]', 1)[-1].split('\n[', 1)[0]
# "Owns this pet" is ~pet_owned in npc/scripts/follower.rs2 now - one answer for the whole game,
# counting the pack, the bank, what you are wearing, what is following you and what Probita is
# holding after a death. What it counts is tools/follower_battery.py's business; that this asks it
# rather than rolling its own two-thirds of the answer is this one's.
check('return(~pet_owned($pet));' in HAS,
      '"do they have this pet" delegates to ~pet_owned, the one answer in the tree')
def guard(rate):
    """The eligibility line that wraps one rung of the ladder - the if whose body rolls that rate."""
    m = re.search(r'if \(([^\n]*)\) \{\n    if \(random\(\^fightcave_exchange_%s_rate\)' % rate,
                  ROLL2)
    return m.group(1) if m else ''
check('~fightcave_has_pet(bosspet_tzrek_jad_item) = true' in guard('meta')
      and '~fightcave_has_pet(bosspet_jalrek_jad_item) = false' in guard('meta'),
      'the metamorphosis needs TzRek-Jad and no JalRek-Jad, which is what "must already have the '
      'pet" means')
check('~fightcave_has_pet(bosspet_tzrek_jad_item) = false' in guard('pet')
      and '~fightcave_has_pet(bosspet_jalrek_jad_item) = false' in guard('pet'),
      '...and the plain pet needs neither, so metamorphosing is never undone by a later roll')
check('npc_finduid(%follower_uid) = true' in META and 'npc_del;' in META
      and '~follower_spawn(bosspet_jalrek_jad);' in META,
      'the metamorphosis transforms the pet OUT FOLLOWING you in place, through the same '
      '~follower_spawn every other pet spawn in the game goes through')
check('inv_del(inv, bosspet_tzrek_jad_item, 1);' in META
      and 'inv_del(bank, bosspet_tzrek_jad_item, 1);' in META,
      '...and the pack and the bank as well, so all three places the pet can be are covered')
check(META.count('inv_add(inv, bosspet_jalrek_jad_item, 1);')
      + META.count('inv_add(bank, bosspet_jalrek_jad_item, 1);') == 2
      and 'inv_add' not in META.split('~follower_spawn(bosspet_jalrek_jad);', 1)[0],
      '...and it never hands over a second pet: one goes out for every one that comes in')
check('~obj_giveorbank(' in ROLL2 and 'obj_add' not in ROLL2,
      'everything the exchange pays goes to the pack or the bank, never the floor')

# --- and the two new items have exactly one source in the game
ALLRS2 = []
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if f.endswith('.rs2'):
            ALLRS2.append((os.path.relpath(os.path.join(root, f), C),
                           open(os.path.join(root, f), newline='', errors='replace').read()))
# HANDED OVER by exactly one script, not merely NAMED by one: JalRek-Jad has a voice now
# (npc/scripts/pet_talk.rs2 dispatches every pet's dialogue on its item), and being spoken to is
# not a way to obtain one. The check is about sources, so it looks at the calls that give an item.
GIVE = r'(?:inv_add|obj_add|~obj_giveorbank|~bosspet_roll|~skillpet_roll(?:_each)?)\([^;]*\b%s\b'
for obj in (CAPE, JITEM):
    where = sorted(p for p, t in ALLRS2
                   if re.search(GIVE % obj, '\n'.join(l.split('//')[0] for l in t.split('\n'))))
    check(where == ['scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2'],
          '%s is handed over by exactly one script in the tree, the exchange: %s' % (obj, where))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
