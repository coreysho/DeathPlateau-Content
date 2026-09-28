"""Battery for the Barrows: the dig in, the climb out, the sarcophagi and the six brothers.

Everything about the Barrows except the scripts was already in the cache and on the maps, and
nothing about it was clickable. That shape is what this battery is built around: the risk here is
not logic, it is ADDRESSING. Six mounds, six crypts, six staircases, six sarcophagi, six brothers
and six bits, all named alike and all easy to cross-wire in a way that compiles, runs, and quietly
sends the player who dug into Torag's mound out of Karil's staircase.

So none of the geometry is trusted from the constants. The mounds are RE-MEASURED off
maps/m55_51.jm2 every run - they are terrain, not locs, because Old School digs into them - and the
crypt tiles are re-measured off maps/m55_151.jm2 against the map's own loc occupancy. The brothers'
numbers are compared against tools/barrowsspec.json, which records Old School's monster infoboxes,
rather than against themselves.

    python3 tools/barrows_battery.py
"""
import json, os, re, sys
from collections import deque

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='', errors='replace').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

BROS = ('ahrim', 'dharok', 'guthan', 'karil', 'torag', 'verac')
SPEC = json.load(open(os.path.join(C, 'tools/barrowsspec.json')))

CONST = read('scripts/areas/area_barrows/configs/barrows.constant')
VARBIT = read('scripts/areas/area_barrows/configs/barrows.varbit')
ENUM  = read('scripts/areas/area_barrows/configs/barrows.enum')
RS2   = read('scripts/areas/area_barrows/scripts/barrows.rs2')
TUN   = read('scripts/areas/area_barrows/scripts/barrows_tunnels.rs2')
CHEST = read('scripts/areas/area_barrows/scripts/barrows_chest.rs2')
TELE  = read('scripts/areas/area_barrows/scripts/barrows_teleport.rs2')
COMBAT = read('scripts/areas/area_barrows/scripts/barrows_combat.rs2')
SETS = read('scripts/areas/area_barrows/scripts/barrows_sets.rs2')
PUZZLE = read('scripts/areas/area_barrows/scripts/barrows_puzzle.rs2')
CHESTIF = read('scripts/areas/area_barrows/interfaces/barrows_chest.if')
INVCFG = read('scripts/areas/area_barrows/configs/barrows.inv')
ALLOBJ = read('scripts/_unpack/377/all.obj')
PMELEE = read('scripts/skill_combat/scripts/player/player_melee.rs2')
PRANGED = read('scripts/skill_combat/scripts/player/player_ranged.rs2')
PMAGIC = read('scripts/skill_combat/scripts/player/player_magic.rs2')
VMELEE = read('scripts/skill_combat/scripts/pvp/pvp_melee.rs2')
VRANGED = read('scripts/skill_combat/scripts/pvp/pvp_ranged.rs2')
VMAGIC = read('scripts/skill_combat/scripts/pvp/pvp_magic.rs2')
DEATH = read('scripts/skill_combat/scripts/npc/npc_death.rs2')
ALLVARP = read('scripts/_unpack/377/all.varp')
ALLVARBIT = read('scripts/_unpack/377/all.varbit')
ALLLOC = read('scripts/_unpack/377/all.loc')
CHESTSPEC = json.load(open(os.path.join(C, 'tools/barrowschestspec.json')))
sys.path.insert(0, os.path.join(C, 'tools'))
import barrowsmaze
STAIRS = read('scripts/ladders+stairs/scripts/stairs.rs2')
SPADE  = read('scripts/general_use/scripts/spade.rs2')
NPCCFG = read('scripts/_unpack/377/all.npc')

def objblock(name):
    """The raw text of one [name] block in all.obj - the whole block, comments and all, because
    some of what is checked about the crossbows IS the comment recording why."""
    return ALLOBJ.split('[' + name + ']', 1)[1].split('\n[', 1)[0] if '[' + name + ']' in ALLOBJ else ''

def npcblock(name):
    return NPCCFG.split('[' + name + ']', 1)[1].split('\n[', 1)[0] if '[' + name + ']' in NPCCFG else ''

def consts(txt):
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r'(?m)^\^(\w+)\s*=\s*(.+?)\s*$', txt)}
K = consts(CONST)

def coord(lit):
    """level_mapx_mapz_localx_localz -> (level, mapx, mapz, x, z)"""
    p = lit.split('_')
    return tuple(int(v) for v in p) if len(p) == 5 else None

def nocomment(txt):
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

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

def param(d, key):
    for pv in d.get('param', []):
        k, _, v = pv.partition(',')
        if k.strip() == key: return v.strip()
    return None

# --- the map, read rather than trusted --------------------------------------------------------
def heights(path, level=0):
    out = {}
    for line in read(path).split('==== MAP ====')[1].split('==== ')[0].split('\n'):
        m = re.match(r'^(\d+) (\d+) (\d+):(.*)$', line.strip())
        if not m: continue
        if int(m.group(1)) != level: continue
        h = re.search(r'\bh(-?\d+)', m.group(4))
        if h: out[(int(m.group(2)), int(m.group(3)))] = int(h.group(1))
    return out

def locrows(path):
    out = []
    for line in read(path).split('==== LOC ====')[1].split('==== ')[0].split('\n'):
        # "level x z: id shape [rot]" - THE ROTATION IS OMITTED WHEN IT IS ZERO, which is what
        # hid two of the six staircases from the first version of this parser.
        m = re.match(r'^(\d+) (\d+) (\d+): (\d+) (\d+)(?: (\d+))?\s*$', line.strip())
        if m: out.append(tuple(int(m.group(i) or 0) for i in range(1, 7)))
    return out

LOCNAME = {}
for line in read('pack/loc.pack').split('\n'):
    if '=' in line:
        i, n = line.strip().split('=', 1)
        LOCNAME[int(i)] = n
LOCID = {v: k for k, v in LOCNAME.items()}

LOCSIZE = {}
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if not f.endswith('.loc'): continue
        for b in re.split(r'(?m)^(?=\[)', read(os.path.relpath(os.path.join(root, f), C))):
            m = re.match(r'\[(\w+)\]', b)
            if not m: continue
            w = re.search(r'(?m)^width=(\d+)', b)
            l = re.search(r'(?m)^length=(\d+)', b)
            LOCSIZE[m.group(1)] = (int(w.group(1)) if w else 1, int(l.group(1)) if l else 1)

def footprint(x, z, locid, rot):
    w, l = LOCSIZE.get(LOCNAME.get(locid), (1, 1))
    if rot % 2 == 1: w, l = l, w
    return {(x + dx, z + dz) for dx in range(w) for dz in range(l)}

# =============================================================================================
print('--- the six mounds are the map\'s own six hills')
# =============================================================================================
MOUND = {b: coord(K.get('barrows_mound_' + b, '')) for b in BROS}
check(all(MOUND.values()), 'all six ^barrows_mound_* are coordinate literals: %s'
      % [b for b in BROS if not MOUND[b]])
check(sorted(set((c[0], c[1], c[2]) for c in MOUND.values())) == [(0, 55, 51)],
      'all six sit on level 0 of m55_51, the surface map: %s'
      % sorted(set((c[0], c[1], c[2]) for c in MOUND.values())))

H = heights('maps/m55_51.jm2', 0)
# A mound is a connected island of high ground, so the map is asked for its islands rather than
# for tiles that beat their neighbours: every one of the six peaks is a PLATEAU two to six tiles
# across, so a strict local-maximum test finds nothing at all - which is how this check started.
THRESH = 70
seen, comps = set(), []
for k in H:
    if H[k] < THRESH or k in seen: continue
    q, c = deque([k]), []
    seen.add(k)
    while q:
        cur = q.popleft(); c.append(cur)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                n = (cur[0] + dx, cur[1] + dz)
                if n not in seen and H.get(n, 0) >= THRESH:
                    seen.add(n); q.append(n)
    comps.append(c)
check(len(comps) == 6, 'm55_51 has exactly six hills above h%d - one per brother, no seventh to '
                       'confuse a pairing: %d' % (THRESH, len(comps)))

PEAKS = [{t for t in c if H[t] == max(H[x] for x in c)} for c in comps]
owner = {}
for b in BROS:
    _, _, _, x, z = MOUND[b]
    hit = [i for i, p in enumerate(PEAKS) if (x, z) in p]
    owner[b] = hit[0] if len(hit) == 1 else None
    check(len(hit) == 1, '%s\'s mound coordinate (%d,%d) is a PEAK tile of one hill, not its slope '
          '(h%s, hill peaks at h%s)'
          % (b, x, z, H.get((x, z)), max(H[t] for t in comps[hit[0]]) if hit else '?'))
check(len(set(owner.values())) == 6 and None not in owner.values(),
      'the six coordinates are on six different hills, so no two brothers share a mound')

CENTRE = (sum(MOUND[b][3] for b in BROS) / 6.0, sum(MOUND[b][4] for b in BROS) / 6.0)
def d2(b):
    return (MOUND[b][3] - CENTRE[0]) ** 2 + (MOUND[b][4] - CENTRE[1]) ** 2
check(min(BROS, key=d2) == 'ahrim',
      'Ahrim\'s mound is the most central of the six, which is the wiki\'s own description of it')
check(max(BROS, key=lambda b: H[(MOUND[b][3], MOUND[b][4])]) == 'ahrim',
      'Ahrim\'s mound is also the tallest (h%d), the other half of that description'
      % H[(MOUND['ahrim'][3], MOUND['ahrim'][4])])

# EAST is +x and NORTH is +z, and the wiki gives each brother's crypt a compass direction. With
# five outer hills against five directions the pairing is forced, not chosen - so it is checkable.
WANT = {'north': (0, +1), 'south': (0, -1), 'east': (+1, 0), 'west': (-1, 0),
        'north-east': (+1, +1), 'north-west': (-1, +1),
        'south-east': (+1, -1), 'south-west': (-1, -1)}
for b in BROS:
    face = SPEC['mound_compass'][b]
    if face == 'centre': continue
    wx, wz = WANT[face]
    dx, dz = MOUND[b][3] - CENTRE[0], MOUND[b][4] - CENTRE[1]
    ok = (wx == 0 or (dx > 0) == (wx > 0)) and (wz == 0 or (dz > 0) == (wz > 0))
    if wx == 0: ok = ok and abs(dx) < abs(dz)
    if wz == 0: ok = ok and abs(dz) < abs(dx)
    check(ok, '%s\'s mound lies %s of the middle, as the wiki places his crypt (dx%+.1f dz%+.1f)'
          % (b, face, dx, dz))

RADIUS = int(K['barrows_mound_radius'])
worst = min(((max(abs(MOUND[a][3] - MOUND[b][3]), abs(MOUND[a][4] - MOUND[b][4])), a, b)
             for i, a in enumerate(BROS) for b in BROS[i + 1:]))
check(worst[0] > 2 * RADIUS,
      'no two mounds are within two radii of each other, so the dig can never match two brothers '
      '(closest pair %s/%s at %d tiles, radius %d)' % (worst[1], worst[2], worst[0], RADIUS))

# =============================================================================================
print()
print('--- the six crypt tiles are real floor next to the right staircase')
# =============================================================================================
CRYPT = {b: coord(K.get('barrows_crypt_' + b, '')) for b in BROS}
check(all(CRYPT.values()), 'all six ^barrows_crypt_* are coordinate literals')
check(sorted(set((c[0], c[1], c[2]) for c in CRYPT.values())) == [(3, 55, 151)],
      'all six sit on level 3 of m55_151, where the crypts are built')
check(len(set((c[3], c[4]) for c in CRYPT.values())) == 6, 'the six crypt tiles are six tiles')

ROWS = locrows('maps/m55_151.jm2')
BLOCKED = set()
for lv, x, z, i, shape, rot in ROWS:
    if lv == 3 and shape in (9, 10, 11):
        BLOCKED |= footprint(x, z, i, rot)

PLACED = {}
for name in [f'barrow_{b}_sarcophagus' for b in BROS] + [f'barrows_stairs_{b}' for b in BROS]:
    i = LOCID.get(name)
    hits = [r for r in ROWS if r[3] == i and r[0] == 3]
    PLACED[name] = hits
    check(len(hits) == 1, '%s is on the map exactly once at level 3 (%d placements)'
          % (name, len(hits)))

for b in BROS:
    _, _, _, x, z = CRYPT[b]
    check((x, z) not in BLOCKED,
          '%s\'s drop tile (%d,%d) is free floor - nothing on the map stands on it' % (b, x, z))
    st = PLACED['barrows_stairs_' + b]
    if not st: continue
    foot = footprint(st[0][1], st[0][2], st[0][3], st[0][5])
    near = min(max(abs(x - fx), abs(z - fz)) for fx, fz in foot)
    check(near == 1, '%s\'s drop tile is beside HIS OWN staircase (%d tiles away)' % (b, near))

SARC = {}
for b in BROS:
    hits = PLACED['barrow_%s_sarcophagus' % b]
    if hits:
        SARC[b] = footprint(hits[0][1], hits[0][2], hits[0][3], hits[0][5])
for b in BROS:
    _, _, _, x, z = CRYPT[b]
    dist = {o: min(max(abs(x - fx), abs(z - fz)) for fx, fz in f) for o, f in SARC.items()}
    nearest = min(dist, key=lambda o: dist[o])
    check(nearest == b, '%s\'s drop tile is nearest HIS OWN sarcophagus, not a neighbour\'s '
          '(nearest: %s at %d)' % (b, nearest, dist[nearest]))

# =============================================================================================
print()
print('--- digging in, climbing out')
# =============================================================================================
DIG = nocomment(RS2.split('[proc,barrows_mound_dig]', 1)[1].split('\n[', 1)[0])
for b in BROS:
    # The branch that matches this mound must telejump to THIS crypt: the one cross-wiring that
    # would be invisible in play until somebody noticed the wrong sarcophagus in front of them.
    m = re.search(r'distance\(coord, \^barrows_mound_%s\)[^{]*\{\s*\$crypt = \^barrows_crypt_(\w+);'
                  % b, DIG)
    check(bool(m) and m.group(1) == b,
          '%s\'s mound leads to %s\'s crypt' % (b, m.group(1) if m else 'nothing'))
check(len(re.findall(r'\^barrows_mound_radius', DIG)) == 6,
      'all six branches measure against ^barrows_mound_radius, so one edit moves all six')
check(DIG.count('return(false)') == 1
      and re.search(r'if \(\$crypt = null\) \{\s*return\(false\);', DIG),
      'the dig reports false in exactly one place, and only when no mound matched - anything else '
      'would let a mound dig fall through to a clue')
check(DIG.strip().endswith('return(true);') and 'p_telejump($crypt);' in DIG,
      'and reports true after the telejump, which is what spends the dig')

SP = nocomment(SPADE)
check('~barrows_mound_dig' in SP, 'spade.rs2 asks the Barrows at all')
check(SP.index('~barrows_mound_dig') < SP.index('p_arrivedelay'),
      'spade.rs2 asks the Barrows BEFORE its own dig, so a mound dig is never also a clue dig')
check('~barrows_mound_dig' in re.split(r'(?m)^\[', SP)[
          [i for i, s in enumerate(re.split(r'(?m)^\[', SP)) if s.startswith('opheld1,spade')][0]],
      'and it asks inside [opheld1,spade] rather than in some other trigger')

for b in BROS:
    m = re.search(r'\[oploc1,barrows_stairs_%s\]\s*@barrows_climb_out\(\^barrows_mound_(\w+)\);' % b,
                  nocomment(STAIRS))
    check(bool(m) and m.group(1) == b,
          '%s\'s staircase climbs out onto %s\'s mound' % (b, m.group(1) if m else 'nothing'))
check(not re.search(r'\[oploc1,barrows_stairs_\w+\][^[]*unhandled_stairs', nocomment(STAIRS)),
      'no Barrows staircase is left routed to @unhandled_stairs')

# =============================================================================================
print()
print('--- the sarcophagi hand over one brother each')
# =============================================================================================
SEARCH = nocomment(RS2.split('[proc,barrows_search]', 1)[1].split('\n[', 1)[0])
check(SEARCH.index('testbit(%barrows_kills') < SEARCH.index('npc_add('),
      'the sarcophagus reads the kill bit BEFORE it adds anybody, so a dead brother cannot be '
      'searched out of his own box twice')
check('^barrows_brother_life' in SEARCH and '^max_32bit_int' not in SEARCH,
      'a woken brother is added with ^barrows_brother_life, not forever')
check('~barrows_brother_engage' in SEARCH and '%aggressive_npc = npc_uid' in SEARCH,
      'and he comes out fighting, and interrupts what the player was doing')
# Opplayer2 is a melee approach: the brother walks into contact before he swings. That is right for
# four of them and wrong for Ahrim and Karil, who stood beside the player doing nothing because the
# melee approach never let their magic and ranged attacks fire. Applayer2 attacks from range.
ENGAGE = nocomment(RS2.split('[proc,barrows_brother_engage]', 1)[1].split('\n[', 1)[0])
check(re.search(r'barrows_ahrim.*barrows_karil[^\n]*\)\s*\{\s*npc_setmode\(applayer2\)', ENGAGE, re.S) is not None,
      '...Ahrim and Karil engage from range (applayer2)')
check('npc_setmode(opplayer2)' in ENGAGE,
      '...and the four melee brothers walk in to fight (opplayer2)')
# A BROTHER WHO IS ALREADY UP IS NOT IN HIS BOX. The kill bit only says he is dead; searching the
# sarcophagus of a brother who is out and still alive used to add a second copy of him, and two of
# him is two sets of armour for one fight.
check('~barrows_brother_here($brother) = ^true' in SEARCH
      and SEARCH.index('~barrows_brother_here') < SEARCH.index('npc_add('),
      'and a box whose brother is already out hands over nobody')
here = nocomment(CHEST.split('[proc,barrows_brother_here]', 1)[1].split('\n[', 1)[0])
# HuntVis: 0 is OFF, 1 is LINEOFSIGHT, 2 is LINEOFWALK. A presence test across a tunnel needs OFF,
# or a brother two rooms away answers "not here" and a second one is handed out.
check(re.search(r'npc_findall\(coord, \$brother, 64, 0\);', here),
      'and it looks for him without needing to see him, which is HuntVis 0')

# Every sarcophagus the CACHE has, not every one the script happens to mention.
for b in BROS:
    m = re.search(r'\[oploc1,barrow_%s_sarcophagus\] ~barrows_search\((\w+), \^barrows_bit_(\w+)\);'
                  % b, nocomment(RS2))
    check(bool(m) and m.group(1) == 'barrows_' + b and m.group(2) == b,
          'barrow_%s_sarcophagus hands over %s against bit %s'
          % (b, m.group(1) if m else 'nobody', m.group(2) if m else '-'))
cachesarcs = sorted(n for n in LOCID if re.fullmatch(r'barrow_\w+_sarcophagus', n))
handled = sorted(re.findall(r'\[oploc1,(barrow_\w+_sarcophagus)\]', nocomment(RS2)))
check(cachesarcs == handled,
      'every sarcophagus in the cache has a handler and none is invented: %s' % (
          sorted(set(cachesarcs) ^ set(handled)) or 'all six'))

# =============================================================================================
print()
print('--- a death sets his own bit, in his own trigger')
# =============================================================================================
for b in BROS:
    body = nocomment(RS2).split('[ai_queue3,barrows_%s]' % b, 1)
    check(len(body) == 2, 'barrows_%s has a death trigger' % b)
    if len(body) != 2: continue
    body = body[1].split('\n[', 1)[0]
    m = re.search(r'%barrows_killed_(\w+) = \^true;', body)
    check(bool(m) and m.group(1) == b,
          '%s\'s death sets %s\'s bit' % (b, m.group(1) if m else 'nothing'))
    check('gosub(npc_death);' in body and 'npc_findhero = ^false' in body,
          '%s\'s death still dies properly and only credits a player it found' % b)
    check(bool(m) and 'npc_findhero' in body and body.index('npc_findhero') < m.start(),
          '%s finds his killer before he writes to him' % b)
# THE COMPILE-TIME LESSON, pinned so a tidy-up cannot undo it: route this write through a label or
# a proc and the [ 'p_active_player' ] it needs lands on the CALL SITE, which is the trigger, where
# npc_findhero has not run yet - "Attempt to access uninitialized pointer", and no way round it
# except putting the write back where it is now.
holders = [seg for seg in re.split(r'(?m)^(?=\[)', nocomment(RS2))
           if re.search(r'%barrows_killed_\w+ = \^true', seg)]
check(len(holders) == len(BROS)
      and all(h.startswith('[ai_queue3,barrows_') for h in holders),
      'the bit is written only inside the death triggers, never behind a label or a proc: %s'
      % [h.split(']', 1)[0] + ']' for h in holders])

bits = {b: int(K['barrows_bit_' + b]) for b in BROS}
check(sorted(bits.values()) == [0, 1, 2, 3, 4, 5],
      'the six bits are 0-5 with no collision: %s' % bits)
check(int(K['barrows_brothers']) == len(BROS),
      '^barrows_brothers counts the brothers there are: %s' % K['barrows_brothers'])

# =============================================================================================
print()
print('--- the brothers themselves, against Old School\'s infoboxes')
# =============================================================================================
NPC = blocks(NPCCFG)
SEQS = set()
for line in read('pack/seq.pack').split('\n'):
    if '=' in line: SEQS.add(line.strip().split('=', 1)[1])
DEFBONUS = {'stab': 'stabdefence', 'slash': 'slashdefence', 'crush': 'crushdefence',
            'magic': 'magicdefence', 'ranged': 'rangedefence'}
for b in BROS:
    s = SPEC['brothers'][b]
    d = NPC.get('barrows_' + b, {})
    check(bool(d), 'barrows_%s exists as an npc' % b)
    if not d: continue
    got = {k: int(d[k][0]) for k in s['levels'] if k in d}
    check(got == s['levels'], '%s\'s levels are the infobox\'s: %s' % (b, got))
    check(d.get('vislevel', [None])[0] == str(s['combat']),
          '%s is combat %d on the right-click' % (b, s['combat']))
    check(param(d, 'attackrate') == str(s['speed']),
          '%s attacks every %d ticks' % (b, s['speed']))
    check(param(d, 'damagetype') == '^%s_style' % s['style'],
          '%s attacks with %s, which is the style his max hit is listed against (got %s)'
          % (b, s['style'], param(d, 'damagetype')))
    for k, pname in DEFBONUS.items():
        want = s['defensive'][k]
        got = int(param(d, pname) or 0)
        check(got == want, '%s\'s %s defence is %+d' % (b, k, want) if got == want
              else '%s\'s %s defence is %+d, infobox says %+d' % (b, k, got, want))
    check(int(param(d, 'strengthbonus') or 0) == s['aggressive']['strengthbonus'],
          '%s\'s strength bonus is %+d' % (b, s['aggressive']['strengthbonus']))
    check(int(param(d, 'magicattack') or 0) == s['aggressive']['magicbonus'],
          '%s\'s magic bonus is %+d' % (b, s['aggressive']['magicbonus']))
    check(int(param(d, 'rangeattack') or 0) == s['aggressive']['rangedbonus'],
          '%s\'s ranged bonus is %+d' % (b, s['aggressive']['rangedbonus']))
    # The infobox gives one melee Attack bonus and it is +0 for all six, so a per-style melee
    # attack bonus cannot be sourced from it - and two of them were sitting here, each a copy of
    # that brother's strength bonus.
    melee = {p: param(d, p) for p in ('stabattack', 'slashattack', 'crushattack')
             if param(d, p) is not None}
    check(s['aggressive']['attackbonus'] != 0 or not melee,
          '%s carries no invented per-style attack bonus (infobox gives +0): %s' % (b, melee or '-'))
    for p in ('attack_anim', 'defend_anim'):
        a = param(d, p)
        check(a is None or a in SEQS, '%s\'s %s is a real animation: %s' % (b, p, a))
    if s['aggressive']['rangedstrength']:
        check(param(d, 'rangedstrength') is None
              and 'rangedstrength' not in read('scripts/engine.rs2'),
              '%s\'s +%d ranged strength has nowhere to go in this engine, and is not faked'
              % (b, s['aggressive']['rangedstrength']))

# =============================================================================================
print()
print('--- the run is stored in the cache\'s own varbits, not in a var of ours')
# =============================================================================================
def varbits(txt):
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', b)
        if not m:
            continue
        base = re.search(r'(?m)^basevar=(\w+)', b)
        lo = re.search(r'(?m)^startbit=(\d+)', b)
        hi = re.search(r'(?m)^endbit=(\d+)', b)
        if base and lo and hi:
            out[m.group(1)] = (base.group(1), int(lo.group(1)), int(hi.group(1)))
    return out

VB = varbits(ALLVARBIT)
VB.update(varbits(VARBIT))
VBPACK = [l.strip().split('=', 1)[1] for l in read('pack/varbit.pack').split('\n') if '=' in l]

# THE CHECK THAT MAKES testbit(%barrows_kills, $bit) LEGITIMATE. Every read of a brother's kill
# goes to the base var by bit number and every write goes through the named varbit, so the two
# only agree while the cache's bit order and ^barrows_bit_* stay the same six in the same order.
for b in BROS:
    name = 'barrows_killed_' + b
    check(VB.get(name) == ('barrows_kills', bits[b], bits[b]),
          '%s is bit %d of %%barrows_kills, which is where ^barrows_bit_%s points: %s'
          % (name, bits[b], b, VB.get(name)))
mon = VB.get('barrows_killed_monster')
check(mon and mon[0] == 'barrows_kills' and (1 << (mon[2] - mon[1] + 1)) > int(K['barrows_potential_cap']),
      'barrows_killed_monster holds the reward potential and is wide enough for %s of it: bits %s'
      % (K['barrows_potential_cap'], mon[1:] if mon else '-'))
check(VB.get('barrows_chest_open', ('', 0, 0))[0] == 'barrows_kills',
      'barrows_chest_open is the chest multiloc\'s own bit, on the same var')

# The two this round added, and the only two it needed.
check(VB.get('barrows_entry_crypt') == ('barrows', 0, 2),
      'barrows_entry_crypt sits in %%barrows bits 0-2, below everything the cache uses: %s'
      % (VB.get('barrows_entry_crypt'),))
check(VB.get('barrows_chest_paid') == ('barrows', 3, 3),
      'barrows_chest_paid sits in %%barrows bit 3: %s' % (VB.get('barrows_chest_paid'),))
ours = {'barrows_entry_crypt', 'barrows_chest_paid'}
theirs = [(n, v) for n, v in VB.items() if v[0] == 'barrows' and n not in ours]
clash = [n for n, v in theirs
         for o in ours if VB[o][1] <= v[2] and v[1] <= VB[o][2]]
check(not clash, 'and neither overlaps a varbit the cache already had: %s' % (clash or 'none'))
for n in sorted(ours):
    check(n in VBPACK, '%s is in pack/varbit.pack, without which it will not resolve' % n)

# THE INVENTED VAR IS GONE. %barrows_killed was a duplicate of barrows_killed_* written before
# anybody looked at the cache's varbits; this is the check that keeps it from coming back.
allrs2 = []
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if f.endswith('.rs2'):
            allrs2.append((os.path.relpath(os.path.join(root, f), C),
                           read(os.path.relpath(os.path.join(root, f), C))))
check(not [p for p, t in allrs2 if '%barrows_killed ' in t or '%barrows_killed=' in t],
      'nothing reads or writes a %barrows_killed varp any more')
check('barrows_killed\n' not in read('pack/varp.pack')
      and '=barrows_killed\n' not in read('pack/varp.pack'),
      'and it is out of pack/varp.pack too')
kills = ALLVARP.split('[barrows_kills]', 1)
check(len(kills) == 2 and re.match(r'\s*protect=no', kills[1]),
      '[barrows_kills] is protect=no, which is what lets a death write it at all')

# =============================================================================================
print()
print('--- the maze is chosen from rows that the map says can be finished')
# =============================================================================================
def enumblock(name):
    b = ENUM.split('[%s]' % name, 1)
    return b[1].split('\n[', 1)[0] if len(b) == 2 else ''

MZ = enumblock('barrows_mazes')
masks = [int(v) for _, v in re.findall(r'(?m)^val=(\d+),(\d+)$', MZ)]
ids = [int(k) for k, _ in re.findall(r'(?m)^val=(\d+),(\d+)$', MZ)]
check(len(masks) == int(K['barrows_mazes']),
      'barrows_mazes holds ^barrows_mazes = %s rows: %d' % (K['barrows_mazes'], len(masks)))
check(ids == list(range(len(ids))), 'keyed 0..%d with no gap, which is what random() indexes'
      % (len(ids) - 1))
check(len(set(masks)) == len(masks), 'and no row is a duplicate of another')
check(re.search(r'(?m)^default=0$', MZ),
      'a miss opens every door rather than shutting one, because obj 0 of a maze is a run nobody '
      'can finish')
# RE-MEASURED, not trusted: every row is flood-filled against maps/m55_151.jm2 on every run.
bad = [m for m in masks if not barrowsmaze.solves(m)]
check(not bad, 'every maze still leaves all four ladders able to walk to the chest: %s'
      % ['0x%04X' % m for m in bad])
check(all(0 < m < 0xFFFF for m in masks),
      'every maze shuts something and leaves something open')
check(not barrowsmaze.solves(0xFFFF),
      'and the map agrees that shutting all sixteen would NOT be finishable, so the check above '
      'can fail')
# The mask's bit order IS the varbits' bit order, which is the whole reason one write lays a maze.
for i, L in enumerate(barrowsmaze.LETTERS):
    want = int(K['barrows_door_first']) + i
    check(VB.get('barrows_door_' + L) == ('barrows', want, want),
          'gate %s is %%barrows bit %d, so bit %d of a mask is its lock: %s'
          % (L, want, i, VB.get('barrows_door_' + L)))
check(int(K['barrows_door_last']) - int(K['barrows_door_first']) + 1 == 16,
      '^barrows_door_first..last is exactly sixteen bits wide')

# =============================================================================================
print()
print('--- the twenty-four pieces, and only from a brother who was killed')
# =============================================================================================
EQ = enumblock('barrows_equipment')
eq = dict((int(k), v) for k, v in re.findall(r'(?m)^val=(\d+),(\w+)$', EQ))
check(len(eq) == len(BROS) * int(K['barrows_equip_pieces']),
      'barrows_equipment holds four pieces for each of the six brothers: %d' % len(eq))
check(re.search(r'(?m)^default=null$', EQ),
      'and says null out loud on a miss, because obj 0 is a real item')
objpack = set(l.strip().split('=', 1)[1] for l in read('pack/obj.pack').split('\n') if '=' in l)
for i in range(len(BROS) * 4):
    b = BROS[i // 4]
    name = eq.get(i, '')
    check(name.startswith('barrows_%s_' % b) and name in objpack,
          'piece %d is one of %s\'s and is a real obj: %s' % (i, b, name or '-'))
check(sorted(eq.values()) == sorted(set(eq.values())), 'no piece is listed twice')
# The address the chest builds, brother*4 + 0..3, is the address this table is keyed on.
check('multiply($bit, ^barrows_equip_pieces)' in CHEST
      and 'random(^barrows_equip_pieces)' in CHEST,
      'the chest addresses it as brother * four + a piece, the order it is written in')
check('~barrows_nth_killed(random($brothers))' in CHEST,
      'and picks the brother from the ones that are DEAD, evenly')
nk = [nocomment(x) for x in CHEST.split('[proc,barrows_nth_killed]', 1)]
check(len(nk) == 2 and 'testbit(%barrows_kills, $bit) = ^true' in nk[1],
      '~barrows_nth_killed counts the killed bits rather than all six')
nu = [nocomment(x) for x in TUN.split('[proc,barrows_nth_unkilled]', 1)]
check(len(nu) == 2 and 'testbit(%barrows_kills, $bit) = ^false' in nu[1],
      '...and its mirror, which a door uses, counts the live ones')

# =============================================================================================
print()
print('--- the chest pays what the wiki says it pays')
# =============================================================================================
CS = CHESTSPEC
check(int(K['barrows_rolls_base']) == CS['rolls']['base']
      and int(K['barrows_rolls_max']) == CS['rolls']['max'],
      'one roll to start and seven at most')
check('min(add(^barrows_rolls_base, $brothers), ^barrows_rolls_max)' in CHEST,
      'and a roll for every brother killed in between')
check(int(K['barrows_equip_base']) == CS['equipment']['base']
      and int(K['barrows_equip_step']) == CS['equipment']['step'],
      'the armour chance is 1/(%d - %d * brothers)' % (CS['equipment']['base'],
                                                       CS['equipment']['step']))
for n, odds in sorted(CS['equipment']['odds'].items(), key=lambda kv: int(kv[0])):
    got = int(K['barrows_equip_base']) - int(K['barrows_equip_step']) * int(n)
    check(got == odds, 'which is 1/%d with %s brother(s) down: 1/%d' % (odds, n, got))
check(int(K['barrows_potential_cap']) == CS['potential']['monster_cap']
      and int(K['barrows_potential_brother']) == CS['potential']['per_brother']
      and int(K['barrows_potential_max']) == CS['potential']['max'],
      'the pool caps at %d, a brother is worth %d, and the two make %d'
      % (CS['potential']['monster_cap'], CS['potential']['per_brother'], CS['potential']['max']))
check(int(K['barrows_potential_cap'])
      + len(BROS) * int(K['barrows_potential_brother']) == int(K['barrows_potential_max']),
      '...and that is arithmetic rather than three numbers that happen to be written down')

BANDS = [(r['item'], r['rp'], r['low'], r['high']) for r in CS['table']]
KCONST = {'mindrune': 'mind', 'chaosrune': 'chaos', 'deathrune': 'death', 'bloodrune': 'blood',
          'boltrack': 'boltrack', 'keyhalf': 'keyhalf', 'dragonmed': 'dragonmed'}
for item, rp, lo, hi in BANDS:
    if item == 'coins':
        continue
    c = K.get('barrows_rp_' + KCONST[item])
    check(c is not None and int(c) == rp,
          '%s needs %d reward potential before it can be rolled: %s' % (item, rp, c))
edges = [1] + [rp for item, rp, _, _ in BANDS if item != 'coins'] + [int(K['barrows_potential_max']) + 1]
widths = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
check(sum(widths) == int(K['barrows_potential_max']),
      'the bands tile 1..%s with nothing left over: %s = %d'
      % (K['barrows_potential_max'], ' + '.join(str(w) for w in widths), sum(widths)))
check(widths == [380, 125, 125, 125, 125, 125, 6, 1],
      'and they are the wiki\'s own widths: %s' % widths)
for item, rp, lo, hi in BANDS:
    key = 'coins' if item == 'coins' else KCONST[item]
    if lo == hi == 1:
        continue
    check(int(K['barrows_loot_%s_low' % key]) == lo
          and int(K['barrows_loot_%s_high' % key]) == hi,
          '%s comes %d-%d at a time' % (item, lo, hi))
# THE ORDER OF THE IF-CHAIN IS THE WHOLE TABLE. Tested ascending it would pay coins for every
# roll, silently, and every band constant would still be right.
chain = re.findall(r'\$roll >= \^barrows_rp_(\w+)', CHEST)
check(chain == ['dragonmed', 'keyhalf', 'boltrack', 'blood', 'death', 'chaos', 'mind'],
      'the chest tests the bands from the top down, or it would pay coins for everything: %s'
      % chain)
PAYS = {'dragonmed': 'dragon_med_helm', 'boltrack': 'barrows_karil_ammo', 'blood': 'bloodrune',
        'death': 'deathrune', 'chaos': 'chaosrune', 'mind': 'mindrune'}
for band, obj in sorted(PAYS.items()):
    seg = CHEST.split('$roll >= ^barrows_rp_%s' % band, 1)
    check(len(seg) == 2 and obj in seg[1].split('} else')[0],
          'the %s band pays %s' % (band, obj))
# The key band holds an if/else of its own for the two halves, so its branch ends at the next
# BAND rather than at the next else - which is what the first version of this check cut on.
seg = CHEST.split('$roll >= ^barrows_rp_keyhalf', 1)
body = seg[1].split('} else if (', 1)[0] if len(seg) == 2 else ''
check('keyhalf1' in body and 'keyhalf2' in body,
      'the key band pays one half of the crystal key or the other')
check('~barrows_reward_add(coins,' in CHEST, 'and everything below the first band is coins')
check('add(random($potential), 1)' in CHEST,
      'the roll is a value in 1..potential, inclusive at both ends, as the wiki words it')
check('~barrows_between' in CHEST and 'add($low, random(add(sub($high, $low), 1)))' in CHEST,
      'and so is every quantity')
# Paying twice, and paying for nothing.
check('%barrows_chest_paid = ^true;' in CHEST, 'looting marks the chest paid')
# nocomment() FIRST, and this check learned why the hard way: a comment added elsewhere in the
# file mentioned ~barrows_chest_search by name, the raw-text grep found it after the marker, and
# the check went green while the actual call was deleted. Same fault as the four slices that
# swallowed the next block's comments - a check that greps source has to grep CODE.
check('[oploc1,barrows_stone_chest]' in CHEST and '[oploc2,barrows_stone_chest]' in CHEST
      and '~barrows_chest_search' in nocomment(CHEST).split('[oploc1,barrows_stone_chest]', 1)[1],
      'one op1 handler opens the chest and searches it, branching on the bit the multiloc reads')
loot = nocomment(CHEST.split('[proc,barrows_chest_search]', 1)[1])
check('%barrows_chest_paid = ^true' in loot
      and loot.index('%barrows_chest_paid = ^true') < loot.index('~barrows_reward_roll'),
      '...before it rolls anything, so an interrupted payout cannot be taken twice')
# THE TWO REFUSALS SPLIT APART when an already-paid chest learned to hand its loot back: a
# search with no run behind it still finds nothing, but a chest that has paid and not been
# emptied reopens instead. They used to be one condition and the check used to read it as one.
check('%barrows_entry_crypt = ^barrows_entry_none' in loot
      and loot.index('%barrows_entry_crypt = ^barrows_entry_none') < loot.index('%barrows_chest_paid = ^true'),
      'a search with no run behind it still finds nothing of interest')
check('%barrows_chest_paid = ^true' in loot
      and 'find nothing of interest' in loot.split('%barrows_chest_paid = ^true', 1)[1].split('~barrows_reward_roll', 1)[0],
      '...and a chest that has paid and been emptied says the same rather than rolling again')
check('%barrows = 0' not in CHEST and '%barrows_kills = 0' not in CHEST,
      'looting clears NOTHING, because the run is what holds the ladder the player still has to '
      'climb and the brothers a door may still send')
begin = nocomment(TUN.split('[proc,barrows_begin_run]', 1)[1].split('\n[', 1)[0])
check(re.search(r'(?m)^%barrows_chest_paid = \^false;$', begin)
      and re.search(r'(?m)^%barrows_kills = 0;$', begin)
      and '~barrows_shut_ladders' in begin,
      'the next dig is what clears the last run - its bits, its chest and its ladder')
check('%barrows_entry_crypt ! ^barrows_entry_none & %barrows_chest_paid = ^false' in begin,
      '...and a run still owed its chest is never cleared out from under the player')

# =============================================================================================
print()
print('--- what comes through a door')
# =============================================================================================
D = CS['door_spawn']
check(int(K['barrows_spawn_denom']) == D['_denominator'], 'the door rolls out of 128')
check(int(K['barrows_spawn_brother']) == D['brother'],
      'a brother on %d of them' % D['brother'])
check(int(K['barrows_spawn_skeleton']) - int(K['barrows_spawn_brother']) == D['skeleton'],
      'a skeleton on %d' % D['skeleton'])
check(int(K['barrows_spawn_bloodworm']) - int(K['barrows_spawn_skeleton']) == D['bloodworm'],
      'a bloodworm on %d' % D['bloodworm'])
check(int(K['barrows_spawn_denom']) - int(K['barrows_spawn_bloodworm']) == D['crypt_rat'],
      'and a crypt rat on the remaining %d' % D['crypt_rat'])
check(int(K['barrows_spawn_crowd']) == D['crowd'],
      'nothing comes through into a room already holding %d' % D['crowd'])
spawn = nocomment(TUN.split('[proc,barrows_door_spawn]', 1)[1].split('\n[', 1)[0])
check('%barrows_entry_crypt = ^barrows_entry_none' in spawn,
      'a door with no run behind it lets nothing out')
check('~barrows_crowd($where) >= ^barrows_spawn_crowd' in spawn,
      'and neither does a crowded room')
check(spawn.index('^barrows_spawn_crowd') < spawn.index('random(^barrows_spawn_denom)'),
      '...checked before the roll, so a crowded room does not eat a brother')
check('%barrows_chest_paid = ^true' in spawn and '$roll = 0;' in spawn,
      'after the chest has paid, every door is a brother - the wiki\'s own guarantee')
NPCPACK = set(l.strip().split('=', 1)[1] for l in read('pack/npc.pack').split('\n') if '=' in l)
for n in ('barrows_skeleton_armed', 'barrows_skeleton_unarmed', 'barrows_bloodworm', 'barrows_rat'):
    check(n in spawn and n in NPCPACK, '%s is real and is what a door can send' % n)
sb = nocomment(TUN.split('[proc,barrows_spawn_brother]', 1)[1].split('\n[', 1)[0])
check('~barrows_nth_unkilled(random($left))' in sb,
      'a door\'s brother is one the player has NOT killed, picked evenly')
check('sub(^barrows_brothers, ~barrows_brothers_killed)' in sb
      and '$left <= 0' in sb,
      '...and with all six down it sends something else rather than nothing or a seventh brother')

# Every gate on the map has a lock bit, and the locked form is the one with no option on it -
# which is why a locked door needs no handler and no "it will not budge" message.
LOCB = blocks(ALLLOC)
check('op1' in LOCB.get('barrows_door_unlocked_l', {})
      and 'op1' in LOCB.get('barrows_door_unlocked_r', {}),
      'the unlocked door carries Open')
check(not [o for o in ('op1', 'op2', 'op3', 'op4', 'op5')
           if o in LOCB.get('barrows_door_locked_l', {})
           or o in LOCB.get('barrows_door_locked_r', {})],
      'and the locked one carries no option at all, which is 377\'s own "this one will not open"')
check('[oploc1,_barrows_door]' not in TUN,
      'no category trigger is left over from when one handler served every doorway')
for L in barrowsmaze.LETTERS:
    for half in ('l', 'r'):
        d = LOCB.get('barrows_door_%s_%s' % (L, half), {})
        check(d.get('multivar', [None])[0] == 'barrows_door_' + L
              and 'multiloc' in d,
              'barrows_door_%s_%s reads gate %s\'s own bit' % (L, half, L))
check('~open_and_close_double_door' in nocomment(TUN),
      'a door is opened rather than walked through')

# =============================================================================================
print()
print('--- the passage in and the ladder out')
# =============================================================================================
walk, doors, ladders, chesttile = barrowsmaze.tunnel()
for L in sorted(ladders):
    c = coord(K['barrows_chamber_tile_' + L])
    check(c and (c[0], c[1], c[2]) == (0, 55, 151),
          'chamber %s\'s drop tile is on the tunnel level: %s' % (L, K['barrows_chamber_tile_' + L]))
    check(c and (c[3], c[4]) in walk,
          'chamber %s\'s drop tile is floor a player can stand on' % L)
    lx, lz = ladders[L]
    check(c and max(abs(c[3] - lx), abs(c[4] - lz)) == 1,
          'chamber %s\'s drop tile is beside ITS OWN ladder' % L)
ct = {L: coord(K['barrows_chamber_tile_' + L]) for L in sorted(ladders)}
check(len(set((v[3], v[4]) for v in ct.values())) == len(ct), 'the four drop tiles are four tiles')
idx = {L: int(K['barrows_chamber_' + L]) for L in sorted(ladders)}
check(sorted(idx.values()) == list(range(int(K['barrows_chambers']))),
      'the four chambers are numbered 0..%d, which is what random() rolls: %s'
      % (int(K['barrows_chambers']) - 1, idx))
for L in sorted(ladders):
    m = re.search(r'case \^barrows_chamber_%s : return\(\^barrows_chamber_tile_(\w+)\);' % L,
                  nocomment(TUN))
    check(bool(m) and m.group(1) == L,
          'chamber %s answers with %s\'s tile' % (L, m.group(1) if m else 'nothing'))
    m = re.search(r'case \^barrows_chamber_%s : %%barrows_chamber_(\w+) = \^true;' % L,
                  nocomment(TUN))
    check(bool(m) and m.group(1) == L, 'and opening chamber %s lights %s\'s ladder'
          % (L, m.group(1) if m else 'nothing'))
check(LOCB.get('barrows_ladder_a', {}).get('multivar', [None])[0] == 'barrows_chamber_a',
      'a ladder is a multiloc on its chamber\'s bit, so it does not exist until the run opens it')
check('[oploc1,_barrows_ladder]' in TUN,
      'and all four are served by one handler, through their own category')
for b in BROS:
    m = re.search(r'case \^barrows_bit_%s : return\(\^barrows_mound_(\w+)\);' % b,
                  nocomment(TUN.split('[proc,barrows_entry_mound]', 1)[1]))
    check(bool(m) and m.group(1) == b,
          'the ladder puts a player who came in by %s\'s crypt back on %s\'s mound'
          % (b, m.group(1) if m else 'nothing'))
psg = nocomment(TUN.split('[proc,barrows_passage]', 1)[1].split('\n[', 1)[0])
check('~barrows_open_chamber' in psg and '$chamber < 0' in psg,
      'coming back down the same run reuses the chamber it opened rather than rolling a new one')
check('enum(int, int, barrows_mazes, random(^barrows_mazes))' in psg,
      'and the maze is laid once, on the way in')
check('~barrows_passage' in RS2 and '%barrows_entry_crypt = add($bit, 1)' in RS2,
      'the sarcophagus of the entry crypt gives the passage instead of its brother')
check('~barrows_begin_run' in RS2.split('[proc,barrows_mound_dig]', 1)[1].split('\n[', 1)[0],
      'and the run is drawn by the first dig, before any box is searched')

# =============================================================================================
print()
print('--- reward potential')
# =============================================================================================
check('~barrows_potential;' in nocomment(DEATH),
      '[proc,npc_death] pays reward potential, which is the one place every death passes through')
check(nocomment(DEATH).index('~barrows_potential') > nocomment(DEATH).index('npc_arrivedelay'),
      '...while the npc is still there to be asked what it was')
pot = nocomment(TUN.split('[proc,barrows_potential]', 1)[1].split('\n[', 1)[0])
check('inzone(^barrows_tunnel_sw, ^barrows_tunnel_ne, npc_coord)' in pot,
      'and nothing outside the tunnels pays anything')
check('~barrows_brother_bit(npc_type) >= 0' in pot,
      'a BROTHER pays nothing into the pool: his two points are added by the chest off his own '
      'bit, and the 1000 + 6*2 cap is what says he is worth two and not his combat level')
check('npc_findhero = ^false' in pot and '%barrows_entry_crypt = ^barrows_entry_none' in pot,
      'and a kill with no player or no run behind it pays nothing')
check('min(add(%barrows_killed_monster, nc_vislevel(npc_type)), ^barrows_potential_cap)' in pot,
      'what it pays is the dead thing\'s own combat level, capped at ^barrows_potential_cap')
check('multiply($brothers, ^barrows_potential_brother)' in CHEST,
      'and the chest is where the brothers\' two points each are added')
NPCS = blocks(NPCCFG)
for n, lvl in sorted(CS['tunnel_monsters'].items()):
    got = NPCS.get(n, {}).get('vislevel', [None])[0]
    check(got == str(lvl), '%s is combat %d, which is what it pays: %s' % (n, lvl, got))
check(int(K['barrows_spawn_range']) > 0 and 'npc_findallany($where, ^barrows_spawn_range, 1)' in TUN,
      'the crowd is counted with npc_findallany around the tile stepped onto')

# =============================================================================================
print()
print('--- the Barrows teleport')
# =============================================================================================
T = CS['teleport']
TOBJ = blocks(read('scripts/areas/area_barrows/configs/barrows.obj')).get('barrows_teleport', {})
check(bool(TOBJ), 'barrows_teleport exists as an obj')
check('barrows_teleport' in objpack, '...and is in pack/obj.pack')
check(TOBJ.get('stackable', [None])[0] == 'yes', 'it stacks, which is the point of a tab')
check(TOBJ.get('iop1', [None])[0] == 'Break', 'and its one option is Break')
# THE SAME ICON CAMERA AS THE FOURTEEN LECTERN TABLETS, which is what makes it read as a tablet
# in the pack rather than a thing of its own. Compared against a tablet, not against a number.
TAB = blocks(read('scripts/skill_construction/configs/poh_tablets.obj')).get('poh_tab_varrock', {})
for f in ('2dzoom', '2dxan', '2dyof'):
    check(TOBJ.get(f) == TAB.get(f) and TOBJ.get(f) is not None,
          'its %s is the lectern tablets\' own: %s' % (f, TOBJ.get(f, ['-'])[0]))
check(TOBJ.get('model', [None])[0] == 'obj_barrows_teleport'
      and 'obj_barrows_teleport' in set(l.strip().split('=', 1)[1]
                                        for l in read('pack/model.pack').split('\n') if '=' in l),
      'its model is imported, named and packed')
check(os.path.exists(os.path.join(C, 'models/obj/obj_barrows_teleport.ob2')),
      '...and the .ob2 is actually in the tree')
check(K['barrows_tele_dest'] == T['destination'],
      'it lands on %s, the tile Corey asked for: %s' % (T['destination'], K['barrows_tele_dest']))
check(int(K['barrows_tele_rate']) == T['rate'],
      'the chest pays one at 1/%d' % T['rate'])
check(int(K['barrows_tele_low']) == T['low'] and int(K['barrows_tele_high']) == T['high'],
      'and pays %d to %d of them' % (T['low'], T['high']))
check('random(^barrows_tele_rate) = 0' in CHEST
      and '~barrows_between(^barrows_tele_low, ^barrows_tele_high)' in CHEST,
      'which is what the chest actually rolls')
# ~barrows_reward_add is in the list because the chest pays into its own store now, and
# inv_add is what that proc does - so the store's own file would otherwise look like a source.
gives = sorted(p for p, t in allrs2
               if re.search(r'(?:inv_add|obj_add|~obj_giveorbank|~barrows_reward_add)'
                            r'\([^;]*\bbarrows_teleport\b', nocomment(t)))
check(gives == ['scripts/areas/area_barrows/scripts/barrows_chest.rs2'],
      'the chest is the only thing in the game that hands one over: %s' % gives)
check('[opheld1,barrows_teleport]' in TELE and 'inv_del(inv, barrows_teleport, 1);' in TELE,
      'breaking one spends exactly one')
check('~pre_tele_checks(coord) = false' in TELE and '~wilderness_level(coord) > 20' in TELE,
      'and it is not a way out of deep wilderness, a duel or the trawler')

# =============================================================================================
print()
print('--- every handler is on a loc that is actually on the map')
# =============================================================================================
# THE FAULT THIS SECTION EXISTS FOR. A multiloc has a shell on the map and children it resolves
# to, and the ops the player sees come from the CHILD - so a trigger on the child looks right and
# reads right. It never fires. Player.getOpTrigger looks the script up on
# LocType.get(target.type), the type that is ON THE MAP, and does not resolve the multiloc,
# even though OpLocHandler resolved one moments earlier to decide whether the op exists at all.
# Three of this round's four handlers were written on children: both halves of every door, all
# four ladders and the chest, so the tunnels had no working doors and the chest could not be
# opened. Every check that existed asked whether the trigger was WRITTEN DOWN. This one asks
# whether it can run.
LOCCFG = {}
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if not f.endswith('.loc'):
            continue
        LOCCFG.update(blocks(read(os.path.relpath(os.path.join(root, f), C))))

PLACED = set()
for m in ('maps/m55_51.jm2', 'maps/m55_151.jm2'):
    for line in read(m).split('==== LOC ====')[1].split('==== ')[0].split('\n'):
        mm = re.match(r'^(\d+) (\d+) (\d+): (\d+) (\d+)(?: (\d+))?\s*$', line.strip())
        if mm:
            PLACED.add(LOCNAME.get(int(mm.group(4)), '?'))
PLACEDCAT = {}
for n in PLACED:
    c = LOCCFG.get(n, {}).get('category', [None])[0]
    if c:
        PLACEDCAT.setdefault(c, []).append(n)

def ops_of(name):
    """Every op number the player can ever see on this loc, its multiloc children included."""
    d = LOCCFG.get(name, {})
    out = set()
    for i in range(1, 6):
        if 'op%d' % i in d:
            out.add(i)
    for mv in d.get('multiloc', []):
        child = mv.split(',', 1)[1].strip() if ',' in mv else ''
        cd = LOCCFG.get(child, {})
        for i in range(1, 6):
            if 'op%d' % i in cd:
                out.add(i)
    return out

BARROWSRS2 = [('areas/area_barrows/scripts/barrows.rs2', RS2),
              ('areas/area_barrows/scripts/barrows_tunnels.rs2', TUN),
              ('areas/area_barrows/scripts/barrows_chest.rs2', CHEST),
              ('ladders+stairs/scripts/stairs.rs2', STAIRS)]
trigs = []
for where, txt in BARROWSRS2:
    for m in re.finditer(r'(?m)^\[oploc(\d),(\w+)\]', nocomment(txt)):
        if 'barrow' in m.group(2):
            trigs.append((where, int(m.group(1)), m.group(2)))
check(len(trigs) >= 10, 'the Barrows declares %d loc handlers to check' % len(trigs))
for where, op, name in trigs:
    if name.startswith('_'):
        cat = name[1:]
        holders = PLACEDCAT.get(cat, [])
        check(bool(holders),
              'op%d on category %s: %d locs on the Barrows maps carry it'
              % (op, cat, len(holders)))
        for h in holders:
            check(op in ops_of(h),
                  '...and %s really has an op%d for it to catch: %s'
                  % (h, op, sorted(ops_of(h)) or 'no ops at all'))
    else:
        check(name in PLACED,
              'op%d on %s: that loc is on one of the Barrows maps' % (op, name))
        check(op in ops_of(name),
              '...and it has an op%d, on itself or on a multiloc child: %s'
              % (op, sorted(ops_of(name)) or 'no ops at all'))
# The reverse, which is the dead-click question: every op a Barrows loc on the map can show has
# a handler somewhere in the tree.
ALLTRIG = set()
for p_, t in allrs2:
    for m in re.finditer(r'(?m)^\[oploc(\d),(\w+)\]', nocomment(t)):
        ALLTRIG.add((int(m.group(1)), m.group(2)))
dead = []
for n in sorted(PLACED):
    if not n.startswith('barrow'):
        continue
    cat = LOCCFG.get(n, {}).get('category', [None])[0]
    for op in sorted(ops_of(n)):
        if (op, n) in ALLTRIG or (cat and (op, '_' + cat) in ALLTRIG):
            continue
        dead.append('%s op%d "%s"' % (n, op, (LOCCFG.get(n, {}).get('op%d' % op, ['?'])[0])))
check(not dead, 'no Barrows loc on either map has an option nothing handles: %s' % (dead or 'none'))

# =============================================================================================
print()
print('--- the dig ends, and the tunnels pay nothing')
# =============================================================================================
dig = nocomment(RS2.split('[proc,barrows_mound_dig]', 1)[1].split('\n[', 1)[0])
# .rindex on a string that is not there RAISES, and a crash is not a catch - ninth time in this
# project, so the membership test comes first.
check('anim(human_dig_barrows, 0);' in dig and 'anim(null, 0);' in dig
      and dig.rindex('anim(null, 0);') > dig.index('p_telejump'),
      'the dig animation is stopped after the telejump - human_dig_barrows is loops=8 and outlives '
      'the script that started it, so without this the player keeps digging inside the crypt')
# "a tad quicker" (owner, 2026-09-27): four ticks of waiting before the telejump, not five - p_delay(n)
# holds n + 1; the telejump lands the tick after, so five from the spade to the crypt where it was six
# (Engine-TS tools/sim/visuals.ts measures it) - and a stroke quicker than human_dig_long's 39 client
# ticks (its frames' own delays, 4,4,4,4,6,3,4 in anim_84, and its delay8=10)
check(sum(int(n) + 1 for n in re.findall(r'p_delay\((\d+)\)', dig.split('p_telejump', 1)[0])) == 4,
      'four ticks of waiting before the telejump (were five)')
DIGSEQ = read('scripts/areas/area_barrows/configs/barrows.seq').split('[human_dig_barrows]', 1)
DIGDELAYS = [int(d) for d in re.findall(r'(?m)^delay\d+=(\d+)', DIGSEQ[1].split('\n[', 1)[0])] if len(DIGSEQ) == 2 else []
check(len(DIGDELAYS) == 8 and sum(DIGDELAYS) < 39,
      'the Barrows dig strokes are quicker than human_dig_long: %d client ticks a stroke, not 39' % sum(DIGDELAYS))
check(len(DIGSEQ) == 2 and re.search(r'(?m)^loops=[2-9]', DIGSEQ[1].split('\n[', 1)[0]),
      '...which is worth checking because the seq really does loop: %s'
      % (re.search(r'(?m)^loops=(\d+)', DIGSEQ[1].split('\n[', 1)[0]).group(1)
         if len(DIGSEQ) == 2 and re.search(r'(?m)^loops=(\d+)', DIGSEQ[1].split('\n[', 1)[0])
         else 'no loops line'))

# NOTHING IN THE TUNNELS DROPS ANYTHING. The two skeletons were on the ordinary skeleton table -
# coins, arrows, runes, a herb and a shot at the ultra-rare - in a place whose entire reward is
# the chest. And death_drop DEFAULTS TO BONES, so a monster that says nothing still drops bones
# through [ai_queue3,_] -> ~npc_default_death: saying null out loud is the only way to drop
# nothing.
TUNNELMON = sorted(CS['tunnel_monsters'])
for n in TUNNELMON:
    d = NPCS.get(n, {})
    check(param(d, 'death_drop') == 'null',
          '%s drops nothing, said out loud because death_drop defaults to bones: %s'
          % (n, param(d, 'death_drop')))
    owners = sorted(p_ for p_, t in allrs2
                    if re.search(r'(?m)^\[ai_queue3,%s\]' % n, nocomment(t)))
    check(not owners, '...and has no death trigger of its own to put it back on a table: %s'
          % owners)
check(param(NPCS.get('death_drop_probe', {}), 'death_drop') is None
      and re.search(r'(?m)^default=bones$',
                    read('scripts/skill_combat/configs/npc_combat.param')
                    .split('[death_drop]', 1)[1].split('\n[', 1)[0]),
      'and death_drop really does default to bones, which is why the line above is needed')

# =============================================================================================
print()
print('--- the brothers fight the way Old School says, and hit as hard')
# =============================================================================================
# THE MAX HITS ARE RE-DERIVED, not stored. Every one of them comes out of the engine's own formula
# from the bonuses the infoboxes give, so this section is what says the stat blocks are right -
# and it is the check that would have caught Karil's missing ranged strength, because without it
# his max hit computes to 11 against the wiki's 20.
def eff_stat(level):
    # ~combat_effective_stat(level, 100) is scale(max(100,100), 100, level), which is level.
    return level + 9  # the 'style bonus' of 1 that every npc gets

def engine_maxhit(level, bonus):
    # ~combat_maxhit(~combat_stat(...)) = (effective * (bonus + 64) + 320) / 640
    return (eff_stat(level) * (bonus + 64) + 320) // 640

for b in BROS:
    sp = SPEC['brothers'][b]
    d = NPC.get('barrows_' + b, {})
    e = sp['effect']
    if e['style'] == 'ranged':
        got = engine_maxhit(sp['levels']['ranged'], int(param(d, 'rangebonus') or 0))
    elif e['style'] == 'magic':
        got = int(K['barrows_ahrim_maxhit'])
    else:
        got = engine_maxhit(sp['levels']['strength'], int(param(d, 'strengthbonus') or 0))
    # The expected number stays OUT of the leading text: a mutation to the spec would otherwise
    # rewrite the message this check is identified by.
    check(got == sp['maxhit'],
          "%s's max hit comes out of his own record through the engine's formula: %d, wiki %d"
          % (b, got, sp['maxhit']))
# Dharok at one hitpoint, which is the whole of Wretched Strength.
dh = SPEC['brothers']['dharok']
base = engine_maxhit(dh['levels']['strength'], 105)
check(base + (99 * base) // 100 == dh['maxhit_at_1'],
      "dharok at one hitpoint hits %d, which is his %d plus one per cent of it for each of the 99 "
      'he is missing: %d' % (dh['maxhit_at_1'], base, base + (99 * base) // 100))
check('scale(sub(npc_basestat(hitpoints), npc_stat(hitpoints)), 100, $maxhit)' in COMBAT,
      '...and that is the line that does it')
check(re.search(r'if \(npc_type ! barrows_dharok\) \{\s*return\(\$maxhit\);', COMBAT),
      'and nobody else gets it')

# THE AI. A bare damagetype does not stop the engine handing an npc the melee AI every npc gets:
# [ai_queue1,_] sets opplayer2 and [ai_opplayer2,_] swings. This is the check for the bug Corey
# found - Ahrim walking up and hitting people with his staff.
for b in BROS:
    st = SPEC['brothers'][b]['effect']['style']
    if st == 'melee':
        check('[ai_opplayer2,barrows_%s] ~barrows_melee;' % b in COMBAT,
              '%s swings, through his own handler' % b)
        check('[ai_queue1,barrows_%s]' % b not in COMBAT,
              '...and keeps the default melee retaliate, which is the right one for him')
    else:
        check('[ai_queue1,barrows_%s] ~npc_default_retaliate_ap;' % b in COMBAT,
              '%s retaliates AT RANGE, which is what sets applayer2' % b)
        check('[ai_applayer2,barrows_%s]' % b in COMBAT
              and '[ai_opplayer2,barrows_%s] npc_setmode(applayer2);' % b in COMBAT,
              '...and both being walked up to and standing off send him to the same %s attack' % st)
check('~npc_meleeattack' not in COMBAT,
      'no brother goes through the plain melee attack, because every one of them has something '
      'the plain one does not do')

# VERAC'S PIERCE skips the rolls rather than weighting them: "ignoring prayer and armour" means
# the attack roll that returns zero under Protect from Melee is never consulted, and neither is
# the player's defence.
pierce = nocomment(COMBAT.split('[proc,barrows_melee_damage]', 1)[1].split('\n[', 1)[0])
check(int(K['barrows_verac_pierce_pct']) == SPEC['brothers']['verac']['effect']['chance'],
      "verac's prayer pierce is %d%%" % SPEC['brothers']['verac']['effect']['chance'])
check('npc_type = barrows_verac & random(100) < ^barrows_verac_pierce_pct' in pierce
      and pierce.index('barrows_verac_pierce_pct') < pierce.index('~npc_melee_attack_roll'),
      '...and a pierced hit is decided BEFORE the rolls, so neither prayer nor armour is asked')
check('return(add(random($maxhit), 1));' in pierce,
      'and it lands for one to his max, never nothing')

# THE FOUR EFFECTS THAT NEED A PICTURE have one, and it is the cache's own - all four spotanims
# were sitting in 377 unused.
SPOT = set(l.strip().split('=', 1)[1] for l in read('pack/spotanim.pack').split('\n') if '=' in l)
efx = nocomment(COMBAT.split('[proc,barrows_effect]', 1)[1].split('\n[', 1)[0])
for b in BROS:
    e = SPEC['brothers'][b]['effect']
    got = int(K.get('barrows_%s_effect_pct' % b, -1)) if b != 'dharok' and b != 'verac' else e['chance']
    if b not in ('dharok', 'verac'):
        check(got == e['chance'], "%s's %s fires on %d%% of his landed hits: %s"
              % (b, e['name'], e['chance'], got))
    if e['spotanim']:
        check(e['spotanim'] in SPOT, "%s's %s has the cache's own graphic: %s"
              % (b, e['name'], e['spotanim']))
        # Slice HIS case out of the switch rather than regexing across it: a lazy match that
        # wandered into the next case would call any brother's graphic his.
        seg = efx.split('case barrows_%s :' % b, 1)
        seg = seg[1].split('\n    case ', 1)[0] if len(seg) == 2 else ''
        plays = re.findall(r'spotanim_npc\((\w+),', seg)
        check(plays == [e['spotanim']],
              '...and it is the one HIS case plays: %s' % (plays or 'none'))
    else:
        check('case barrows_%s :' % b not in efx,
              '%s has no case in the effect switch, because his effect is a number' % b)
check(int(K['barrows_ahrim_strength_drain']) == 5, "Ahrim's aura takes five levels of Strength")
check(int(K['barrows_karil_agility_pct']) == 20, "Karil's bolt takes a fifth of Agility")
check(int(K['barrows_torag_energy_pct']) == 20, "Torag's hammers take a fifth of the energy left")
check('npc_statheal(hitpoints, $damage, 0);' in efx,
      'Guthan heals for THE DAMAGE HE DEALT, which is why the effect takes it as an argument')
check('scale($percent, 100, runenergy)' in COMBAT,
      "and Torag's fifth is a fifth of what is LEFT, not a fifth of the bar")
# Every player-side write goes through a queue: an npc script has the player but not protected
# access to him, which is the same wall the kill bits ran into.
for q in ('barrows_ahrim_drain', 'barrows_karil_drain', 'barrows_torag_drain'):
    check('[queue,%s]' % q in COMBAT and 'queue(%s, 0,' % q in COMBAT,
          '%s reaches the player through his own queue' % q)
check('stat_sub(strength, $amount, 0);' in COMBAT and 'stat_sub(agility, 0, $percent);' in COMBAT,
      "and the two stat drains are flat for Ahrim's five levels and a percentage for Karil's fifth")

# AHRIM CASTS A REAL SPELL, so the freeze and debuff paths are the engine's.
check('~get_spell_data(^iban_blast)' in COMBAT
      and SPEC['ahrim_spell']['spell'] == 'iban_blast',
      "Ahrim's attack is Iban's Blast, the one dark burst in the spell table")
check('~npc_player_hit_roll(^magic_style)' in COMBAT,
      '...and his aura rolls on THE SAME hit roll the cast makes, not a second one')
check('~npc_cast_spell(~barrows_ahrim_debuff' in COMBAT
      and int(K['barrows_ahrim_debuff_odds']) == 4,
      'and one cast in four is Confuse, Weaken or Curse, which the wiki lists')
dbf = nocomment(COMBAT.split('[proc,barrows_ahrim_debuff]', 1)[1].split('\n[', 1)[0])
check(sorted(re.findall(r'\^(confuse|weaken|curse)', dbf)) == ['confuse', 'curse', 'weaken'],
      '...all three of them: %s' % sorted(re.findall(r'\^(\w+)\)', dbf)))
check('param=rangebonus,55' in NPCCFG.replace('\r\n', '\n'),
      "Karil's +55 ranged strength is on his record, which is the only reason his max hit is 20")
check(param(NPC.get('barrows_karil', {}), 'proj_travel') == 'crossbowbolt_travel',
      '...and he has a bolt to fire, which ~npc_rangeattack needs: %s'
      % param(NPC.get('barrows_karil', {}), 'proj_travel'))

# =============================================================================================
print()
print('--- the prayer drain')
# =============================================================================================
PD = SPEC['prayer_drain']
check(int(K['barrows_drain_interval']) == PD['interval_ticks'],
      'a face appears every %d ticks, which is the wiki\'s %d seconds'
      % (PD['interval_ticks'], PD['interval_seconds']))
check(int(K['barrows_drain_base']) == PD['base'],
      'and takes %d points before any brother is down' % PD['base'])
check(int(K['barrows_drain_base']) + len(BROS) * PD['per_brother'] == PD['max'],
      '...rising to %d with all six dead, which is arithmetic and not a third number' % PD['max'])
drain = nocomment(COMBAT.split('[timer,barrows_prayer_drain]', 1)[1].split('\n[', 1)[0])
check('add(^barrows_drain_base, ~barrows_brothers_killed)' in drain,
      'and the rise is one point per brother, counted off the kill bits')
check('inzone(^barrows_crypt_sw, ^barrows_crypt_ne, coord)' in drain
      and 'inzone(^barrows_tunnel_sw, ^barrows_tunnel_ne, coord)' in drain,
      'it drains in the crypts AND the tunnels, which are the same map square two levels apart')
check('cleartimer(barrows_prayer_drain);' in drain,
      '...and takes itself off the moment the player is anywhere else')
check('stat(prayer) = 0' in drain and drain.index('stat(prayer) = 0') < drain.index('stat_sub'),
      'and a player with no prayer left is not told about it every eighteen seconds')
check('~barrows_drain_start;' in nocomment(RS2) and '~barrows_drain_start;' in nocomment(TUN),
      'both ways underground start it - the dig and the passage')
check(coord(K['barrows_crypt_sw']) and coord(K['barrows_crypt_sw'])[0] == 3
      and coord(K['barrows_tunnel_sw'])[0] == 0
      and coord(K['barrows_crypt_sw'])[1:3] == coord(K['barrows_tunnel_sw'])[1:3],
      'and the two zones really are one square at two levels: %s and %s'
      % (K['barrows_crypt_sw'], K['barrows_tunnel_sw']))

# =============================================================================================
print()
print('--- the six armour sets')
# =============================================================================================
AS = CHESTSPEC['armour_sets']
SLOTS = ('head', 'body', 'legs', 'weapon')
OBJB = blocks(ALLOBJ)
# THE SET IS NOT TESTED BY ITEM NAME, because a "Dharoks helm 50" is a different obj from a
# "Dharoks helm" and there are a hundred and twenty degraded stages. The twenty-four undamaged
# pieces carry param=barrows_set; every stage already carried param=fixed pointing back at the
# piece it repairs into, which is the second half of the lookup.
for b in BROS:
    want = AS['sets'][b]['id']
    check(int(K['barrows_set_' + b]) == want,
          '%s is set %d, which is his bit plus one' % (b, want))
    for slot in SLOTS:
        d = OBJB.get('barrows_%s_%s' % (b, slot), {})
        check(param(d, 'barrows_set') == str(want),
              'barrows_%s_%s carries set %d' % (b, slot, want))
stages = [n for n in OBJB if re.fullmatch(r'barrows_(%s)_(%s)_\w+' % ('|'.join(BROS),
                                                                      '|'.join(SLOTS)), n)]
check(len(stages) == len(BROS) * len(SLOTS) * 5,
      'the six sets have %d degraded stages between them: %d'
      % (len(BROS) * len(SLOTS) * 5, len(stages)))
badfix = [n for n in stages
          if param(OBJB[n], 'fixed') is None
          or param(OBJB.get(param(OBJB[n], 'fixed'), {}), 'barrows_set') is None]
check(not badfix,
      'and every one of them resolves to a piece that knows its set, through param=fixed: %s'
      % (badfix[:3] or 'all of them'))
tagged = sorted(n for n, d in OBJB.items() if param(d, 'barrows_set') not in (None, '0'))
check(len(tagged) == len(BROS) * len(SLOTS),
      'nothing outside the twenty-four carries a set id: %d' % len(tagged))
# A 0% piece cannot satisfy a set effect however it resolves, because it cannot be worn.
broken = ['barrows_%s_%s_broken' % (b, s) for b in BROS for s in SLOTS]
check(not [n for n in broken if 'iop2' in OBJB.get(n, {})],
      'and a 0% piece has no Wear option, so it can never be in the worn inventory at all')

worn = nocomment(SETS.split('[proc,barrows_set_worn]', 1)[1].split('\n[', 1)[0])
for slot in ('hat', 'torso', 'legs', 'rhand'):
    check('~barrows_set_piece(^wearpos_%s) ! $set' % slot in worn,
          'a full set means the %s slot too, and all four from ONE brother' % slot)
piece = nocomment(SETS.split('[proc,barrows_set_piece]', 1)[1].split('\n[', 1)[0])
check('oc_param($item, barrows_set)' in piece and 'oc_param($item, fixed)' in piece
      and piece.index('barrows_set') < piece.index('fixed'),
      '...and a piece is asked for its set first and resolved through param=fixed only if it has '
      'none, which is what makes every degradation stage count')
check('$item = null' in piece and piece.index('$item = null') < piece.index('oc_param'),
      'and an empty slot is answered before anything is asked of it, because oc_param(null) is '
      'not a question this engine likes')

check(int(K['barrows_set_effect_pct']) == AS['chance'],
      'five of the six fire on %d%% of qualifying hits, which is one number and not five'
      % AS['chance'])
guarded = sorted(set(re.findall(r'\^barrows_set_(\w+)\) = \^true\s*\n?\s*& random\(100\) < \^barrows_set_effect_pct', SETS)
                     + re.findall(r'barrows_set_(\w+)\) = \^false\) \{\s*\n\s*return\(\^false\);\s*\n\}\s*\nif \(random\(100\) < \^barrows_set_effect_pct', SETS)))
check(guarded == ['ahrim', 'guthan', 'karil', 'torag', 'verac'],
      '...and it is the gate on exactly those five sets: %s' % guarded)
check('^barrows_set_effect_pct' not in nocomment(SETS).split('[proc,barrows_dharok_maxhit]', 1)[1]
      .split('\n[', 1)[0],
      "and Dharok's is not one of them, because his is arithmetic on every hit")

# DHAROK'S FORMULA, computed rather than quoted: damage x (1 + missing/100 x maximum/100).
dh = nocomment(SETS.split('[proc,barrows_dharok_maxhit]', 1)[1].split('\n[', 1)[0])
check('divide(multiply(multiply($maxhit, $missing), $max), 10000)' in dh,
      "Dharok's bonus is maxhit x missing x maximum / 10000, which is the wiki's formula with "
      'both hundreds folded into one divide')
D = AS['sets']['dharok']
for maxhp, hp, want in ((99, 1, D['at_99_and_1']), (10, 1, D['at_10_and_1']), (99, 99, 0)):
    got = ((maxhp - hp) * maxhp) // 100
    check(got == want, 'at %d hitpoints with %d left that is +%d%%, and the wiki says +%d%%'
          % (maxhp, hp, got, want))
check('stat_base(hitpoints)' in dh and 'stat(hitpoints)' in dh,
      '...off the player\'s own maximum and current hitpoints')
check('$missing <= 0' in dh,
      'and a player at full health gets nothing rather than a divide on zero')

# WHICH STYLES EACH EFFECT ANSWERS TO. Getting this wrong is the kind of thing that never looks
# broken: Ahrim's staff can be swung, and a melee hit with it must not drain Strength.
npchit = nocomment(SETS.split('[proc,barrows_set_hit_npc]', 1)[1].split('\n[', 1)[0])
plhit = nocomment(SETS.split('[proc,barrows_set_hit_player]', 1)[1].split('\n[', 1)[0])
check('$style = ^magic_style & ~barrows_set_worn(^barrows_set_ahrim)' in npchit,
      "Ahrim's drain answers only to a magic hit, on the monster path")
check('~barrows_set_worn(^barrows_set_guthan)' in npchit
      and '$style' not in npchit.split('barrows_set_guthan', 1)[1].split('\n}', 1)[0],
      "Guthan's heal answers to any hit, which is what the wiki says")
check('barrows_set_karil' not in npchit and 'barrows_set_torag' not in npchit,
      "and neither Karil's nor Torag's is on the monster path, because a monster has no Agility "
      'and no run energy')
check('$style = ^ranged_style & ~barrows_set_worn(^barrows_set_karil)' in plhit,
      "Karil's drain answers only to a ranged hit, on the player path")
check('^melee_style | $style = ^stab_style | $style = ^slash_style | $style = ^crush_style' in plhit
      and 'barrows_set_torag' in plhit,
      "Torag's answers to any of the melee styles, which is what %damagetype actually holds")
check('npc_statsub(strength, ^barrows_ahrim_strength_drain, 0);' in npchit,
      "Ahrim's five levels come off a monster with npc_statsub, which is what makes the effect "
      'possible on one at all')
check('.stat_sub(agility, 0, ^barrows_karil_agility_pct);' in plhit
      and '.healenergy(sub(0, scale(^barrows_torag_energy_pct, 100, .runenergy)));' in plhit,
      "and Karil's fifth of Agility and Torag's fifth of the energy LEFT come off the other player")
check('$damage <= 0' in npchit and '$damage <= 0' in plhit,
      'and nothing fires on a hit that did not land')

# THE HOOKS. Six paths, and the monster ones must not call the player one or the other way round.
for name, txt, hook in (('player melee', PMELEE, '~barrows_set_hit_npc($damage_capped, %damagetype);'),
                        ('player ranged', PRANGED, '~barrows_set_hit_npc($damage_capped, %damagetype);'),
                        ('player magic', PMAGIC, '~barrows_set_hit_npc($damage_capped, ^magic_style);'),
                        ('pvp melee', VMELEE, '~barrows_set_hit_player($damage, %damagetype);'),
                        ('pvp ranged', VRANGED, '~barrows_set_hit_player($damage, %damagetype);'),
                        ('pvp magic', VMAGIC, '~barrows_set_hit_player($damage, ^magic_style);')):
    check(hook in nocomment(txt), 'the %s path fires the sets' % name)
check('~barrows_set_hit_player' not in nocomment(PMELEE) + nocomment(PRANGED) + nocomment(PMAGIC),
      'and no monster path fires the player version')
check('~barrows_set_hit_npc' not in nocomment(VMELEE) + nocomment(VRANGED) + nocomment(VMAGIC),
      'nor the other way round')
check('~barrows_dharok_maxhit($maxhit);' in nocomment(PMELEE)
      and '~barrows_dharok_maxhit(%com_maxhit)' in nocomment(VMELEE),
      "Dharok's scaling is on both melee paths and only the melee paths")
check('~barrows_dharok_maxhit' not in nocomment(PRANGED) + nocomment(PMAGIC),
      '...because his weapon is a greataxe')
check('| ~barrows_verac_ignores = true) {' in nocomment(PMELEE),
      "Verac's pierce is an alternative to the monster hit roll, not a change to it")
vm = nocomment(VMELEE)
check('$verac = ~barrows_verac_ignores;' in vm
      and '~pvp_hit_roll(%damagetype) = true | $verac = true' in vm
      and '^melee_style) = true & $verac = false' in vm,
      "...and in pvp it skips the 40% prayer reduction as well, because a prayer it ignores cannot "
      'also halve the hit')

# =============================================================================================
print()
print('--- the doors open like doors')
# =============================================================================================
DR = CHESTSPEC['doors']
for L in barrowsmaze.LETTERS:
    for half, side in (('l', 'left'), ('r', 'right')):
        name = 'barrows_door_%s_%s' % (L, half)
        d = LOCCFG.get(name, {})
        check(d.get('category', [None])[0] == DR['categories'][half],
              '%s wears the %s double-door category' % (name, half))
        check(param(d, 'next_loc_stage') == 'barrows_door_inactive_%s' % half,
              '...and opens into barrows_door_inactive_%s, which is the same model with no ops' % half)
        # The four gates into the chest room name the puzzle handler instead, which calls this
        # one once the door has been answered.
        check('[oploc1,%s] ~barrows_door_open(^%s);' % (name, side) in TUN
              or '[oploc1,%s] ~barrows_door_puzzle(^%s);' % (name, side) in TUN,
              '...and names its own handler, so the generic door trigger never takes it')
DOORTRIG = r'(?m)^\[oploc1,barrows_door_\w_[lr]\] ~barrows_door_(?:open|puzzle)\(\^(?:left|right)\);$'
check(len(re.findall(DOORTRIG, TUN)) == 32,
      'all thirty-two doorway leaves are accounted for: %d' % len(re.findall(DOORTRIG, TUN)))
check(not [o for o in ('op1', 'op2', 'op3', 'op4', 'op5')
           if o in LOCCFG.get('barrows_door_inactive_l', {})
           or o in LOCCFG.get('barrows_door_inactive_r', {})],
      'and the opened form carries no option, because it is already open')
dopen = nocomment(TUN.split('[proc,barrows_door_open]', 1)[1].split('\n[', 1)[0])
check('~open_and_close_double_door(~check_axis_locactive(coord), $side);' in dopen,
      "the door is opened by the game's own double-door proc, not by a copy of it")
check('~agility_exactmove' not in nocomment(TUN) and 'p_teleport($end)' not in nocomment(TUN),
      '...and nothing steps the player through a shut door any more')
check('~barrows_door_spawn(coord);' in dopen
      and dopen.index('~open_and_close_double_door') < dopen.index('~barrows_door_spawn'),
      'and what comes through does so after the door is open, on the tile the player ends on')

# =============================================================================================
print()
print('--- the reward window')
# =============================================================================================
ivb = blocks(INVCFG).get('barrows_reward_store', {})
check(bool(ivb), 'barrows_reward_store exists as an inv')
check(ivb.get('scope', [None])[0] == 'perm',
      '...and is scope=perm, because a disconnect between the roll and the last click must not '
      'lose a set piece out of a run that is already over')
size = int(ivb.get('size', [0])[0])
check(size >= int(K['barrows_rolls_max']) + 1,
      'it has room for every roll one chest can make plus the teleport tabs: %d slots for %s + 1'
      % (size, K['barrows_rolls_max']))
check('barrows_reward_store' in set(l.strip().split('=', 1)[1]
                                    for l in read('pack/inv.pack').split('\n') if '=' in l),
      'and it is in pack/inv.pack')

# THE WINDOW REGENERATES BYTE-IDENTICAL. Group 35's lesson from the POH round: a generated file
# nobody re-runs the generator over is a file that has quietly stopped matching its generator.
import subprocess
before = open(os.path.join(C, 'scripts/areas/area_barrows/interfaces/barrows_chest.if'), 'rb').read()
packbefore = open(os.path.join(C, 'pack/interface.pack'), 'rb').read()
orderbefore = open(os.path.join(C, 'pack/interface.order'), 'rb').read()
r = subprocess.run([sys.executable, os.path.join(C, 'tools/genbarrowschest.py')],
                   capture_output=True, text=True, cwd=os.path.join(C, 'tools'))
after = open(os.path.join(C, 'scripts/areas/area_barrows/interfaces/barrows_chest.if'), 'rb').read()
check(r.returncode == 0, 'tools/genbarrowschest.py runs: %s' % (r.stderr.strip()[-120:] or 'ok'))
check(after == before, 'and the window it writes is byte-identical to the one in the tree')
check(open(os.path.join(C, 'pack/interface.pack'), 'rb').read() == packbefore
      and open(os.path.join(C, 'pack/interface.order'), 'rb').read() == orderbefore,
      '...and so are both interface packs, which is what says the ids are stable')
check('size=%d' % size in read('tools/genbarrowschest.py').replace('SIZE', '')
      or 'inv_size()' in read('tools/genbarrowschest.py'),
      'and the generator reads the slot count out of the inv config rather than repeating it')

IFB = blocks(CHESTIF)
check(IFB.get('loot', {}).get('type', [None])[0] == 'inv',
      'the grid is the STORE - an inv component, so the client draws the icons, the counts and the '
      'hover names for nothing')
check(int(IFB['loot']['width'][0]) * int(IFB['loot']['height'][0]) == size,
      'and it is exactly as big as the store: %s x %s for %d slots'
      % (IFB['loot']['width'][0], IFB['loot']['height'][0], size))
# SCOPED TO THE WINDOW PROC, not to the whole file. It used to read `in CHEST`, and the mutation
# harness walked straight through deleting this transmit: there are TWO of them, one here and one
# in the reopen proc, so a blanket `in CHEST` stayed true on the strength of the other one - and
# the reopen check, which IS scoped, stayed true on the strength of itself. Same fault as the
# flush check below and the TzHaar shop round before it: a blanket check sitting on top of a
# precise one catches nothing the precise one does not already catch.
window = nocomment(CHEST.split('[proc,barrows_chest_window]', 1)[1].split('\n[', 1)[0])
check('inv_transmit(barrows_reward_store, barrows_chest:loot);' in window
      and 'if_openmain(barrows_chest);' in window,
      'and the script transmits one into the other')
# NO DEAD CLICKS IN THE WINDOW, which is the same rule the POH round put on a house.
opts = sorted(k for k in IFB['loot'] if re.fullmatch(r'option\d', k))
for o in opts:
    n = o[-1]
    check('[inv_button%s,barrows_chest:loot]' % n in CHEST,
          'the grid\'s %s ("%s") is handled' % (o, IFB['loot'][o][0]))
check(IFB.get('takeall', {}).get('option', [None])[0] is not None
      and '[if_button,barrows_chest:takeall]' in CHEST,
      'and so is the Take everything button')
check(IFB.get('close', {}).get('buttontype', [None])[0] == 'close',
      'the close button is the client\'s own, which needs no handler')
check('[if_close,barrows_chest]' in CHEST and 'inv_stoptransmit(barrows_chest:loot);' in CHEST,
      'closing the window stops the transmit')
clos = nocomment(CHEST.split('[if_close,barrows_chest]', 1)[1].split('\n[', 1)[0])
# CLOSING THE WINDOW MUST NOT EMPTY THE CHEST, and this check has now asserted three different
# things - which is the point of writing it from both sides each time. It first asserted the flush
# was called here (that crashed: an if_close has no protected access and both invs are protect=yes).
# Then it asserted the flush was queued. Being attacked closes the modal, so that let a monster
# bank your loot for you - and INV_MOVEITEM drops the overflow ON THE FLOOR when the destination
# is full, which turned an interruption into Barrows loot lying in a crypt. Now nothing about
# banking happens on close at all.
check('~barrows_reward_flush;' not in clos,
      'closing the window does NOT bank the remainder inline - an if_close script has no '
      'protected access and both invs require it')
check('queue(' not in clos and 'barrows_reward_bank_rest' not in CHEST,
      '...and does not queue it either: the chest keeps what it paid until you take it')
search = nocomment(CHEST.split('[proc,barrows_chest_search]', 1)[1].split('\n[', 1)[0])
# THE ONE PLACE THE FLUSH STILL RUNS. A new run resets %barrows_chest_paid (barrows_begin_run),
# so an old chest's loot is banked immediately before a new chest rolls and the window only ever
# shows one chest's payout.
check(CHEST.count('~barrows_reward_flush;') == 1 and '~barrows_reward_flush;' in search
      and search.index('~barrows_reward_flush') < search.index('~barrows_reward_roll'),
      'the flush survives in exactly one place, immediately before a new chest rolls')
check('~barrows_reward_held' in search
      and search.index('~barrows_reward_held') < search.index('~barrows_reward_flush'),
      '...and a chest that has already paid hands its loot back before anything is banked')
check('~barrows_chest_reopen;' in search,
      '...by reopening the window, so being attacked costs you nothing but the walk back')
held = nocomment(CHEST.split('[proc,barrows_reward_held]', 1)[1].split('\n[', 1)[0])
check('inv_getobj(barrows_reward_store' in held and 'inv_size(barrows_reward_store)' in held,
      'and "is there anything left" is asked of the store itself, slot by slot')
reopen = nocomment(CHEST.split('[proc,barrows_chest_reopen]', 1)[1].split('\n[', 1)[0])
check('inv_transmit(barrows_reward_store, barrows_chest:loot);' in reopen
      and 'if_openmain(barrows_chest);' in reopen and '~barrows_reward_roll' not in reopen,
      'reopening transmits and opens and does NOT roll again')
# (The "emptied BEFORE a new chest rolls" check that used to sit here is gone: the one above
# already asserts the ordering AND that there is exactly one flush, so the two overlapped and a
# mutation to the flush could only ever be attributed to one of them. Same fault the TzHaar shop
# round found - a blanket check sitting on top of a precise one.)
check('~obj_giveorbank' not in CHEST,
      'nothing goes straight to the pack or the bank any more - every reward lands in the store')
# Nine band payouts, a piece of equipment, and the teleport tabs.
check(len(re.findall(r'~barrows_reward_add\(', CHEST)) == 11,
      'and all eleven things the chest can pay go through one add: %d'
      % len(re.findall(r'~barrows_reward_add\(', CHEST)))
take = nocomment(CHEST.split('[proc,barrows_reward_take]', 1)[1].split('\n[', 1)[0])
check('$take <= 0' in take and 'You do not have enough room' in take,
      'a stack that will not fit at all says so and stays put rather than half-vanishing')
check('if_settext(barrows_chest:subtitle' in CHEST and '~pluralise($rolls, "roll")' in CHEST,
      'and the window says how many rolls it made and at what potential, which is the one thing '
      'about a Barrows reward a player cannot work out by looking')

# =============================================================================================
print()
print('--- the door before the chest')
# =============================================================================================
pz = VB.get('barrows_puzzle')
check(pz and pz[0] == 'barrows' and (1 << (pz[2] - pz[1] + 1)) == int(K['barrows_puzzles']),
      "%%barrows_puzzle's %d bits hold exactly ^barrows_puzzles = %s of them"
      % ((pz[2] - pz[1] + 1) if pz else 0, K['barrows_puzzles']))
check(VB.get('barrows_puzzle_solved') == ('barrows', 4, 4),
      'barrows_puzzle_solved sits in %%barrows bit 4: %s'
      % (VB.get('barrows_puzzle_solved'),))
check('barrows_puzzle_solved' in VBPACK, '...and is in pack/varbit.pack')

# ---- THE PUZZLE IS PICTURES NOW, so what is checked is that the art, the answer table and the
# script agree. All three come out of one run of tools/genbarrowspuzzle.py, and the point of these
# checks is that they still do: the slot the script tests has to be the slot the picture puts the
# right shape in, and nothing about the .if or the enum says which that is on its own.
PZSPEC = json.load(open(os.path.join(C, 'tools/barrowspuzzlespec.json')))
PZIF = read('scripts/areas/area_barrows/interfaces/barrows_puzzle.if')
PZENUM = read('scripts/areas/area_barrows/configs/barrows_puzzle.enum')
PZGEN = read('tools/genbarrowspuzzle.py')
NPUZ = int(K['barrows_puzzles'])

def ifcoms(txt):
    out = {}
    for chunk in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', chunk)
        if not m:
            continue
        out[m.group(1)] = dict(re.findall(r'(?m)^(\w+)=(.*)$', chunk))
    return out

PZC = ifcoms(PZIF)

check(len(PZSPEC['puzzles']) == NPUZ,
      'there are %d puzzles and %d of them are drawn' % (NPUZ, len(PZSPEC['puzzles'])))

# the answer table: one row per puzzle, keyed 0..n-1, and every value a real slot
rows = {int(a): int(b) for a, b in re.findall(r'(?m)^val=(\d+),(\d+)$', PZENUM)}
check(sorted(rows) == list(range(NPUZ)),
      '...and the answer table is keyed 0..%d, which is what random() rolls: %s'
      % (NPUZ - 1, sorted(rows)))
check(all(0 <= v <= 2 for v in rows.values()),
      '...with every answer a real slot: %s' % sorted(set(rows.values())))
check('default=-1' in PZENUM,
      '...and a default of -1, so a puzzle number nothing matches can never be answered right')

# THE ONE THAT MATTERS: for every puzzle, the slot the enum names must be the slot the interface
# put the answer shape in. This is the join between the picture and the script, and it is the only
# thing here that a person could not see by looking at the window.
def gfx(name):
    """the sprite a component draws, and only if it is a graphic component at all. Asking for
    'graphic' alone is not enough: a mutation that turned a candidate into a type=rect left the
    graphic= line sitting there unread, and the check passed."""
    c = PZC.get(name, {})
    return c.get('graphic') if c.get('type') == 'graphic' else 'not a graphic: %s' % c.get('type')

for i, p in enumerate(PZSPEC['puzzles']):
    shown = [gfx('set%dpick%d' % (i, k)) for k in range(3)]
    want = ['barrows_puzzle,%d' % PZSPEC['tiles'].index(t) for t in p['candidates']]
    check(shown == want,
          'puzzle %d draws its three candidates in the order the spec says (%s)'
          % (i, 'ok' if shown == want else '%s vs %s' % (shown, want)))
    answer = 'barrows_puzzle,%d' % PZSPEC['tiles'].index(p['answer'])
    # THREE WAYS OF SAYING WHERE THE ANSWER IS, and all three have to agree: the spec's own slot
    # field, the order the spec lists its candidates in, and the enum the script reads. The spec's
    # slot used to be checked by nothing at all - a mutation moved it and the battery did not
    # notice, because every other check happened to read 'candidates' instead.
    check(p['candidates'][p['slot']] == p['answer'],
          '...and the spec agrees with itself: candidate %d of puzzle %d IS its answer'
          % (p['slot'], i))
    check(rows.get(i) == p['slot'],
          '...and the answer table says the same slot as the spec (%s vs %s)'
          % (rows.get(i), p['slot']))
    check(rows.get(i) is not None and shown[rows[i]] == answer,
          '...and that slot is the one holding the right shape (slot %s)' % rows.get(i))
    check(shown.count(answer) == 1,
          '...which is the only slot holding it, so there is exactly one right answer')
    seq = [gfx('set%dseq%d' % (i, k)) for k in range(3)]
    check(all(x and x.startswith('barrows_puzzle,') for x in seq),
          '...and its three sequence shapes are drawn: %s' % p['why'])

# ONE check, not two: "every slot is the answer at least twice" already implies "all three slots
# get used", and a single-row mutation can break it, where the weaker version needed two rows
# changed at once and so could not be mutation-tested at all.
_counts = [list(rows.values()).count(k) for k in (0, 1, 2)]
check(min(_counts) >= 2,
      'and the right answer is not always in the same place - every slot is the answer at least '
      'twice: %s' % _counts)

# every puzzle has a layer, and the script hides every layer it has
for i in range(NPUZ):
    check(PZC.get('set%d' % i, {}).get('type') == 'layer',
          'puzzle %d lives in a layer, because if_sethide only works on those' % i)
show = nocomment(PUZZLE.split('[proc,barrows_puzzle_show]', 1)[1].split('\n[', 1)[0])
hidden = set(re.findall(r'if_sethide\(barrows_puzzle:set(\d+), \^true\);', show))
shown_one = set(re.findall(r'if_sethide\(barrows_puzzle:set(\d+), \^false\);', show))
check(hidden == {str(i) for i in range(NPUZ)},
      'showing a puzzle hides all %d layers first: %d hidden' % (NPUZ, len(hidden)))
check(shown_one == {str(i) for i in range(NPUZ)},
      '...and every puzzle number can then show its own: %d cases' % len(shown_one))

# the ask: a modal question answered without leaving the script
ask = nocomment(PUZZLE.split('[proc,barrows_puzzle_ask]', 1)[1].split('\n[', 1)[0])
check('if_openmain(barrows_puzzle);' in ask, 'the puzzle opens as a main modal')
for i in range(3):
    check('if_addresumebutton(barrows_puzzle:pick%d);' % i in ask,
          '...and slot %d is registered as a resume button, or clicking it does nothing' % i)
check('p_pausebutton;' in ask and 'switch_component (last_com)' in ask,
      '...and p_pausebutton suspends the script until one is clicked, so the door handler keeps '
      'its loc context and its protected access')
check(ask.rstrip().endswith('return(-1);'),
      'closing the window without answering returns -1, not a wrong answer')
gate0 = nocomment(PUZZLE.split('[proc,barrows_puzzle_gate]', 1)[1].split('\n[', 1)[0])
# .find(), not .index(): a mutation that deletes ~barrows_shift makes .index() RAISE, and the
# harness reports a non-zero exit with no check named - "a crash is not a catch", which this
# project has now written down ten times.
check('if ($answer = -1) {' in gate0 and 0 <= gate0.find('$answer = -1') < gate0.find('~barrows_shift'),
      '...and the gate returns without shifting the tunnels, so a misclick on Close costs nothing')
right = nocomment(PUZZLE.split('[proc,barrows_puzzle_right]', 1)[1].split('\n[', 1)[0])
check('enum(int, int, barrows_puzzle_answer, %barrows_puzzle)' in right,
      'the pick is judged against the generated table, not a number written twice')

# the sprite sheet the whole thing draws from
PZPNG = os.path.join(C, 'sprites/barrows_puzzle.png')
check(os.path.exists(PZPNG), 'sprites/barrows_puzzle.png exists - the packer scans sprites/*.png')
check(read('sprites/meta/barrows_puzzle.opt').strip() == '%dx%d' % (PZSPEC['tile'], PZSPEC['tile']),
      '...and its .opt splits it into %dx%d tiles, or every index is wrong'
      % (PZSPEC['tile'], PZSPEC['tile']))
from PIL import Image
_im = Image.open(PZPNG).convert('RGB')
_cols = {c for _, c in (_im.getcolors(65536) or [])}
# the number trails rather than leads, so this check has the same NAME whether the sheet or the
# spec was changed - a message built around the expected value cannot be attributed to itself
check(_im.width == PZSPEC['cols'] * PZSPEC['tile'] and _im.height % PZSPEC['tile'] == 0,
      '...and the sheet is as many tiles wide as the spec says, which is what fixes every sprite '
      'index (spec %d, sheet %d)' % (PZSPEC['cols'], _im.width // PZSPEC['tile']))
check((_im.width // PZSPEC['tile']) * (_im.height // PZSPEC['tile']) >= len(PZSPEC['tiles']),
      '...with a cell for all %d tiles' % len(PZSPEC['tiles']))
check((255, 0, 255) in _cols,
      'the background is 0xFF00FF, which is the only colour the packer makes transparent')
check(len(_cols) - 1 <= 255,
      '...and %d other colours, under the 255 the palette holds before it quantizes' % (len(_cols) - 1))
# the generator refuses to produce a puzzle with no right answer or two - checked because that
# guarantee is the whole reason the art is drawn here rather than imported
check('offers its answer twice' in PZGEN and 'duplicate candidates' in PZGEN,
      'the generator refuses to emit a puzzle whose answer is also one of its wrong options')
check('too guessable' in PZGEN,
      '...or a set where one slot is almost never the answer')

gate = nocomment(PUZZLE.split('[proc,barrows_puzzle_gate]', 1)[1].split('\n[', 1)[0])
check('%barrows_puzzle_solved = ^true;' in gate and '~barrows_shift;' in gate,
      'the right answer opens the door for the run and a wrong one shifts the tunnels')
check('%barrows_entry_crypt = ^barrows_entry_none' in gate,
      '...and a door opened with no run behind it asks nothing')
shift = nocomment(PUZZLE.split('[proc,barrows_shift]', 1)[1].split('\n[', 1)[0])
check('enum(int, int, barrows_mazes, random(^barrows_mazes))' in shift
      and '%barrows_puzzle = random(^barrows_puzzles);' in shift
      and '%barrows_puzzle_solved = ^false;' in shift,
      'a shift re-lays the maze, re-rolls the puzzle and locks the door again - so a wrong answer '
      'is not a free retry')
check('%barrows_kills' not in shift and '%barrows_entry_crypt' not in shift,
      '...and touches nothing about the run itself: the brothers you killed stay killed and the '
      'reward potential stays earned')

# WHICH GATES ASK IT, derived off the map rather than read off a list: the chest's own room is
# joined to the rest of the tunnel by exactly four gates, and those are the four the puzzle
# belongs on.
want = sorted(barrowsmaze.chest_gates())
check(len(want) == 4, "the chest's room is reached through four gates, by the map: %s" % want)
asked = sorted(set(re.findall(r'\[oploc1,barrows_door_(\w)_[lr]\] ~barrows_door_puzzle\(',
                              nocomment(TUN))))
check(asked == want, 'and those are the four that ask the puzzle: %s' % asked)
for L in want:
    for half in ('l', 'r'):
        check('[oploc1,barrows_door_%s_%s] ~barrows_door_puzzle(' % (L, half) in TUN,
              'both halves of gate %s ask it, because either leaf opens the doorway' % L)
plain = sorted(set(re.findall(r'\[oploc1,barrows_door_(\w)_[lr]\] ~barrows_door_open\(',
                              nocomment(TUN))))
check(not (set(plain) & set(want)),
      'and no gate does both: %s' % sorted(set(plain) & set(want)))
check(len(plain) + len(asked) == 16, 'all sixteen gates are one or the other: %d + %d'
      % (len(plain), len(asked)))
dp = nocomment(TUN.split('[proc,barrows_door_puzzle]', 1)[1].split('\n[', 1)[0])
check('~barrows_puzzle_gate = ^false' in dp and 'return;' in dp
      and dp.index('~barrows_puzzle_gate') < dp.index('~barrows_door_open'),
      'and a wrong answer means the door does not open at all')
check('%barrows_puzzle = random(^barrows_puzzles);' in nocomment(TUN),
      'the puzzle is rolled with the maze, on the way in')
check('%barrows_puzzle_solved = ^false;' in begin,
      'and a new run locks the door again')

print('--- Karil shoots with the OSRS animation')
# The one Barrows attack animation that actually differs between the two caches. Everything here
# is compared against tools/karilanimspec.json, which was written by decoding BOTH caches before
# any of it was imported - so a check passing means the server agrees with OSRS, not with itself.
ANIMSPEC = json.load(open(os.path.join(C, 'tools/karilanimspec.json')))
SEQCFG = read('scripts/skill_combat/configs/ranged/osrs_crossbow_anims.seq')
SEQPACK = read('pack/seq.pack')
ANIMPACK = read('pack/anim.pack')
SETPACK = read('pack/animset.pack')
BASEPACK = read('pack/base.pack')

def seqblock(name):
    return SEQCFG.split('[' + name + ']', 1)[1].split('\n[', 1)[0] if '[' + name + ']' in SEQCFG else ''

# the five that were deliberately left alone, and the measurement that says why
for who, d in ANIMSPEC['unchanged'].items():
    check(d['delays_identical'],
          '%s: the 377 animation is OSRS\'s frame for frame and delay for delay '
          '(%d frames, %d ticks), so it was left alone' % (who, d['frames'], d['ticks']))
    check('param=attack_anim,%s' % d['seq'] in npcblock('barrows_' + who),
          '...and %s still names it' % who)

# ...and the one that is not
fire = ANIMSPEC['imported']['osrs_karil_crossbow_fire']
check(fire['differs'] and fire['cache377_frames'] == 7 and fire['osrs_frames'] == 22,
      'Karil is the exception: 377 gives the crossbow %d frames over %d ticks where OSRS gives '
      '%d over %d' % (fire['cache377_frames'], fire['cache377_ticks'],
                      fire['osrs_frames'], fire['osrs_ticks']))

for name, d in ANIMSPEC['imported'].items():
    blk = seqblock(name)
    check(blk != '', '[%s] is in the generated .seq config' % name)
    check('%s\n' % name in SEQPACK or SEQPACK.rstrip().endswith('=' + name),
          '...and registered in pack/seq.pack, or nothing can name it')
    frames = re.findall(r'(?m)^frame\d+=(\S+)$', blk)
    delays = [int(x) for x in re.findall(r'(?m)^delay\d+=(\d+)$', blk)]
    check(len(frames) == d['osrs_frames'],
          '...with OSRS seq %d\'s %d frames (%d)' % (d['osrs_seq'], d['osrs_frames'], len(frames)))
    # EVERY frame needs its own delay line here, and that is not cosmetic: a converted frame's
    # OWN baked delay is 1, because animconvosrs puts OSRS's timing in the seq where OSRS keeps
    # it. A missing delay line falls back to that 1 and the animation plays several times too
    # fast - which is exactly the failure a 377 seq with no delay lines does NOT have.
    check(delays == d['osrs_delays'],
          '...and a delay line per frame, equal to OSRS\'s (%d ticks)' % d['osrs_ticks'])
    missing = [f for f in frames if '=' + f + '\n' not in ANIMPACK + '\n']
    check(not missing, '...and every frame it names is in pack/anim.pack (%s)'
          % (missing[:3] or 'all %d' % len(frames)))
    # EXACTLY ONE priority line, and only where OSRS has one. The first version of this asked
    # whether 'priority=6' appeared anywhere in the block, and a mutation that ADDED priority=1
    # above it passed - the old line was still there. Counting the lines catches both.
    prios = re.findall(r'(?m)^priority=(\d+)$', blk)
    check(prios == ([str(d['osrs_priority'])] if d['osrs_priority'] is not None else []),
          '...and OSRS\'s priority, once: %s (got %s)'
          % (d['osrs_priority'] if d['osrs_priority'] is not None else 'none', prios))

groups = sorted(set(re.findall(r'frame\d+=anim_osrs_(\d+)_\d+', SEQCFG)), key=int)
check(len(groups) == 4, 'the four animations come from four frame groups (%s)' % groups)
for g in groups:
    check(os.path.exists(os.path.join(C, 'models/anim_osrs_%s.anim' % g)),
          'models/anim_osrs_%s.anim exists' % g)
    check('=anim_osrs_%s\n' % g in SETPACK + '\n', '...and is registered in pack/animset.pack' )
    check('=base_osrs_%s\n' % g in BASEPACK + '\n',
          '...and its base in pack/base.pack - an OSRS frame plays on the OSRS skeleton, not '
          'the 377 one')

# THE DEGRADE STATES. Five crossbow objs, not one: the pristine item and the four charge states.
# Miss one and the animation changes as the crossbow wears out.
XBOWS = ('barrows_karil_weapon', 'barrows_karil_weapon_100', 'barrows_karil_weapon_75',
         'barrows_karil_weapon_50', 'barrows_karil_weapon_25')
for w in XBOWS:
    blk = nocomment(objblock(w))
    # ONE line per param, not "the right value appears somewhere in the block". A mutation that
    # ADDED a second rangeattack_anim naming a 377 animation passed the substring version of this
    # check, and a duplicate param is a real config error in its own right - the packer takes one
    # of the two and which one is not obvious from reading the file.
    got = dict()
    for k in ('rangeattack_anim', 'ready_baseanim', 'walk_f_baseanim', 'walk_b_baseanim',
              'walk_l_baseanim', 'walk_r_baseanim', 'running_baseanim'):
        got[k] = re.findall(r'(?m)^param=%s,(\S+)$' % k, blk)
    check(got['rangeattack_anim'] == ['osrs_karil_crossbow_fire'],
          '%s fires with the OSRS animation, and names it once (%s)'
          % (w, got['rangeattack_anim']))
    check(got['ready_baseanim'] == ['osrs_karil_crossbow_ready']
          and all(got['walk_%s_baseanim' % d] == ['osrs_karil_crossbow_walk'] for d in 'fblr')
          and got['running_baseanim'] == ['osrs_karil_crossbow_run'],
          '...and its ready, four walks and run come across with it, once each')
# EVERY crossbow that can be held, not just the pristine one: there are six objs and the sixth,
# barrows_karil_weapon_broken ("Karils x-bow 0"), carries no iop2=Wield and no animation params at
# all, because a fully degraded crossbow cannot be wielded. Counting to five would have passed by
# luck; this asks the objs which of them can be held. The first version of this check DID count to
# five, and went red on the broken one - which is how the exclusion came to be stated rather than
# assumed.
allxbow = [n for n in re.findall(r'(?m)^\[(barrows_karil_weapon\w*)\]$', ALLOBJ)]
wieldable = [n for n in allxbow if 'iop2=Wield' in objblock(n)]
check(sorted(wieldable) == sorted(XBOWS),
      'the crossbows that can be held are exactly the five checked above (%d objs, %d wieldable)'
      % (len(allxbow), len(wieldable)))
check(all('_anim,' not in objblock(n) and '_baseanim,' not in objblock(n)
          for n in allxbow if n not in wieldable),
      '...and the one that cannot names no animation at all: %s'
      % ([n for n in allxbow if n not in wieldable] or 'none'))
# WHY the whole set moves and not just the attack: the client only walk-merges two frames built on
# the same skeleton, so an OSRS fire against a 377 walk drops one of the two.
check('sameSkeleton' in nocomment(objblock('barrows_karil_weapon')) or 'sameSkeleton' in objblock('barrows_karil_weapon'),
      'and the obj records why the whole set had to move, not just the attack')
check(not re.search(r'param=\w+,barrows_repeating_crossbow_\w+', ALLOBJ + NPCCFG),
      'nothing still points at the 377 crossbow animations')

# The bolt itself is the AMMUNITION's, not a choice made here.
ammo = objblock('barrows_karil_ammo')
check('param=proj_travel,crossbowbolt_travel' in ammo,
      'the bolt rack says what it looks like in flight: crossbowbolt_travel')
check('param=proj_travel,crossbowbolt_travel' in npcblock('barrows_karil'),
      '...and Karil fires exactly that, so the two cannot drift')
check('name=Bolt rack' in ammo,
      '...and it really is the bolt rack - OSRS\'s ammunition for this crossbow, already in the '
      'cache, so there was nothing to import')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
