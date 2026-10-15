"""Battery for where the pets come from: the boss rates, and the skilling pets' per-action rolls.

tools/bossart_battery.py covers the ART. This covers the NUMBERS, against tools/petspec.json,
which records every rate and base chance and cites the wiki they came from. Nothing in the game is
allowed to hold a number the spec does not, and no base the spec holds is allowed to be missing
from the game - a pet that rolls at the wrong rate is otherwise invisible until someone does the
maths over ten thousand kills.

    python3 tools/pet_battery.py
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt):
    """The source with its comments gone. A rate in a comment is not a rate in the game."""
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

SPEC = json.loads(read('tools/petspec.json'))
ROLL = read('scripts/npc/scripts/skill_pets.rs2')
BOSSRS2 = read('scripts/npc/scripts/boss_pets.rs2')
CONST = read('scripts/npc/configs/skill_pets.constant')
BCONST = read('scripts/npc/configs/boss_pets.constant')
PETNPC = read('scripts/npc/configs/boss_pets.npc') + '\n' + read('scripts/npc/configs/skill_pets.npc')
PETOBJ = read('scripts/npc/configs/boss_pets.obj') + '\n' + read('scripts/npc/configs/skill_pets.obj')

def const(txt, n):
    m = re.search(r'\^' + n + r'\s*=\s*(\d+)', txt)
    return int(m.group(1)) if m else None

def rows(path):
    """dbrow blocks -> {block: {field: value}}"""
    out = {}
    for b in re.split(r'(?m)^(?=\[)', read(path)):
        m = re.match(r'\[(\w+)\]', b)
        if not m: continue
        d = {}
        for l in b.split('\n')[1:]:
            l = l.split('//')[0].strip()
            if l.startswith('data='):
                k, _, v = l[5:].partition(',')
                d.setdefault(k, []).append(v)
        out[m.group(1)] = d
    return out

def params(path):
    """[name] blocks -> {name: {param: value}}, for a struct or obj config."""
    out = {}
    for b in re.split(r'(?m)^(?=\[)', read(path)):
        m = re.match(r'\[([\w+]+)\]', b)
        if not m: continue
        d = {}
        for l in b.split('\n')[1:]:
            l = l.split('//')[0].strip()
            if l.startswith('param='):
                k, _, v = l[6:].partition(',')
                d.setdefault(k, []).append(v)
        out[m.group(1)] = d
    return out


def table(spec):
    """One entry of a pet's "tables" -> ({block: {key: [values]}}, key)."""
    reader = {'dbrow': rows, 'param': params}[spec['kind']]
    return reader(spec['path']), spec['key']


# ============================================================================ 1
print('1. the roll is OSRS\'s formula, and it reads the level OSRS reads')
step = const(CONST, 'skillpet_level_step')
check(step == SPEC['level_step'], 'the level step is the spec\'s %d' % SPEC['level_step'])
body = code(ROLL).split('[proc,skillpet_roll]', 1)[1].split('\n[', 1)[0]
check('calc($base - (stat_base($stat) * ^skillpet_level_step))' in body,
      'the chance is base - (level * step), which is 1 in (B - level*25)')
check('stat_base(' in body and 'stat(' not in body.replace('stat_base(', ''),
      'and it is the UNBOOSTED level - a dwarven stout must not improve the odds')
check('random($chance)' in body, 'the roll is random(chance)')
check('^skillpet_no_roll' in body and body.index('^skillpet_no_roll') < body.index('random($chance)'),
      'an action with no base is refused before the roll, not after')
check(const(CONST, 'skillpet_no_roll') == 0,
      'and that sentinel is 0, so a missing table entry reads as "no pet" rather than "always"')
check('$chance < 1' in body, 'the chance is floored at 1, so a base added carelessly cannot divide by nothing')
# ~pet_owned (npc/scripts/follower.rs2) is the one answer to "owns this pet" - pack, bank, worn,
# following, and waiting at Probita's after a death. .find rather than .index: this check used to
# say body.index('~obj_gettotal'), and when that call moved behind ~pet_owned the battery raised
# ValueError instead of failing. A crash is not a catch.
# A pet is received the way every pet is: ~pet_receive (npc/scripts/follower.rs2) - it follows you,
# or goes in the pack, or to Probita's, and a pet owned anywhere (~pet_owned) is not given twice.
check('~pet_receive($pet)' in body, 'a successful roll hands the pet to ~pet_receive, as every pet is given')
check(body.find('~pet_receive') > body.find('random($chance)') > -1,
      'and only after the roll succeeds, so ~pet_owned is one inv sweep per pet rather than per action')
check('obj_add(' not in code(body), 'and a skilling pet never lands on the floor')
check('~pet_owned' not in body,
      'and the roll does not ask who owns what BEFORE it has rolled - that is one inventory sweep '
      'per log and per ore rather than one per pet earned')
# AND THE FUNNEL'S OWN HALF, because a skilling pet is only as right as what it is handed to. These
# two were checked here when the roll did them itself; they moved to ~pet_receive with everything
# else, and this battery has to follow them rather than assume another one is watching.
_FOLL = read('scripts/npc/scripts/follower.rs2')
_owned = _FOLL.split('[proc,pet_owned]', 1)[1].split('\n[', 1)[0] if '[proc,pet_owned]' in _FOLL else ''
_recv = _FOLL.split('[proc,pet_receive]', 1)[1].split('\n[', 1)[0] if '[proc,pet_receive]' in _FOLL else ''
check('~pet_owned($pet) = true' in _recv and '~obj_gettotal($pet) > 0' in _owned
      and '%follower_obj = $pet' in _owned and 'inv_total(lostpet_store, $pet) > 0' in _owned,
      '...and ~pet_receive refuses one the player owns anywhere - pack, bank, worn, the one out '
      'following them, and the one waiting at Probita\'s')
check('inv_add(lostpet_store, $pet, 1);' in _recv and 'obj_add(' not in code(_recv),
      '...and a full pack sends it to Probita\'s rather than the floor')

# ============================================================================ 2
print('2. the boss pets roll at their own rate, named at the call site')
check('[proc,bosspet_roll](namedobj $pet, int $rate)' in BOSSRS2,
      'the rate is an argument, so a family cannot inherit another family\'s number')
check('random($rate)' in code(BOSSRS2), 'and it is what the roll uses')
check(const(BCONST, 'bosspet_droprate') == 3000, '^bosspet_droprate is 3,000')
check(const(BCONST, 'bosspet_gwd_droprate') == 5000, '^bosspet_gwd_droprate is 5,000')
RATE_CONST = {3000: '^bosspet_droprate', 5000: '^bosspet_gwd_droprate'}
for pet, d in sorted(SPEC['boss'].items()):
    item = pet + '_item'
    hits = []
    for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
        for fn in files:
            if not fn.endswith('.rs2'): continue
            rel = os.path.join(dirpath, fn)[len(C) + 1:]
            for m in re.finditer(r'~bosspet_roll\(([^)]*)\)', code(read(rel))):
                if m.group(1).split(',')[0].strip() == item:
                    hits.append((os.path.basename(rel), m.group(1)))
    check(len(hits) == 1, '%s is rolled in exactly one place: %s'
          % (item, [h[0] for h in hits] or 'NOWHERE'))
    if len(hits) != 1: continue
    where, args = hits[0]
    check(where == d['table'], '...and it is %s' % d['table'])
    want = RATE_CONST[d['rate']]
    check(args.split(',')[1].strip() == want,
          '...at %s, which is 1 in %d' % (want, d['rate']))
check(len(SPEC['boss']) == 10, 'all ten boss pets are accounted for')

# ============================================================================ 3
print('3. every base chance in the game is the spec\'s, and the spec cites the wiki')
check('oldschool.runescape.wiki' in SPEC['wiki'], 'the spec says where its numbers came from')
wired = {k: v for k, v in SPEC['skill'].items() if v['wired']}
check(len(wired) == 8, 'all eight skilling pets are wired: %s' % sorted(wired))
for pet, d in sorted(wired.items()):
    for spec in d.get('tables', []):
        tbl, key = table(spec)
        # One line per base rather than a count. Verbose - the farming table alone is 57 - but a
        # count makes every base share one check, and then a mutation that moves one of them is
        # "caught" by a check that names none of them.
        for blk, want in sorted(spec['bases'].items()):
            got = tbl.get(blk, {}).get(key, [None])[0]
            check(got == str(want), '%s: %s is %s' % (pet, blk, want))
        extra = [b for b in tbl if key in tbl[b] and b not in spec['bases']]
        # Named per table, not "...and nothing else": every pet has one of these checks, and a
        # shared wording means a mutation aimed at one of them is "caught" by another's.
        check(not extra, '%s: nothing else in %s carries a base the spec does not know: %s'
              % (pet, os.path.basename(spec['path']), extra or 'none of %d blocks' % len(tbl)))
    for cn, want in sorted(d.get('constants', {}).items()):
        check(const(CONST, cn) == want, '%s: ^%s is %s' % (pet, cn, want))

# ============================================================================ 4
print('4. no base can outrun the formula at 99')
# Read from the GAME, not from the spec: this is a claim about what ships. Group 3 is what holds
# the two equal, so a number lowered in one place is caught there and here.
for pet, d in sorted(wired.items()):
    vals = []
    for spec in d.get('tables', []):
        tbl, key = table(spec)
        vals += [int(v[0]) for b, f in tbl.items() if (v := f.get(key)) and int(v[0]) > 0]
    vals += [c for cn in d.get('constants', {}) if (c := const(CONST, cn))]
    worst = min(vals) if vals else None
    check(worst is None or worst - 99 * SPEC['level_step'] >= 1,
          '%s: its smallest base (%s) still leaves a chance at 99: 1 in %s'
          % (pet, worst, worst - 99 * SPEC['level_step'] if worst else 'n/a'))

# ============================================================================ 5
print('5. every hook the spec names really rolls for that pet, with that skill')
# The rift guardian's three hooks call ~rift_guardian_roll instead of the roll itself: its colour
# comes off the altar, so the wrapper in npc/scripts/pet_variants.rs2 has to see the rune. The
# wrapper is where the roll then happens, and it is checked here like any other hook.
WRAP = {'skillpet_rift_guardian': ('~rift_guardian_roll', 'scripts/npc/scripts/pet_variants.rs2')}
for pet, d in sorted(wired.items()):
    item = pet + '_item'
    wrapper = WRAP.get(pet)
    for f in d['hooks']:
        t = code(read(f))
        if wrapper:
            check(wrapper[0] + '(' in t,
                  '%s rolls in %s, through %s' % (item, os.path.basename(f), wrapper[0]))
            continue
        m = [x for x in re.findall(r'~skillpet_roll(?:_each)?\(([^)]*)\)', t)
             if x.split(',')[0].strip() == item]
        check(bool(m), '%s rolls in %s' % (item, os.path.basename(f)))
        if not m: continue
        stats = {x.split(',')[1].strip() for x in m}
        check(stats == {d['stat']}, '...against %s' % d['stat'])
    if wrapper:
        t = code(read(wrapper[1]))
        m = [x for x in re.findall(r'~skillpet_roll(?:_each)?\(([^)]*)\)', t)
             if x.split(',')[0].strip() == item]
        check(bool(m) and {x.split(',')[1].strip() for x in m} == {d['stat']},
              '...and %s rolls it against %s' % (wrapper[0], d['stat']))
    if d.get('per') == 'essence':
        t = code(read(wrapper[1] if wrapper else d['hooks'][0]))
        check('~skillpet_roll_each(' in t and '$times' in t,
              '...and the Rift guardian rolls once per essence, not once per click')
    if d.get('per') == 'lap':
        for f in d['hooks']:
            t = code(read(f))
            check('_course_progress = 0;' in t and '~skillpet_roll(' in t,
                  '...and %s rolls on completing a lap' % os.path.basename(f))

# ============================================================================ 6
print('6. every pet has a source')
# There used to be one exception: the Baby chinchompa, built before Hunter existed and handed over
# nowhere on purpose. Box trapping (2026-09-23) is its source now, so every pet is wired - and a
# pet added later without one has to come back here and say why, rather than slip through.
pending = {k: v for k, v in SPEC['skill'].items() if not v['wired']}
check(len(pending) == 0, 'none is pending: %s' % sorted(pending))

# ============================================================================ 7
print('7. each pet names its item and each item names its pet back')
def blocks(txt):
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', b)
        if m: out[m.group(1)] = b
    return out
NB, OB = blocks(PETNPC), blocks(PETOBJ)
allpets = sorted(list(SPEC['boss']) + list(SPEC['skill']))
check(len(allpets) == 18, 'eighteen pets in the spec')
for pet in allpets:
    item = pet + '_item'
    check(pet in NB, '%s has an npc config' % pet)
    check(item in OB, '...and an item config')
    if pet not in NB or item not in OB: continue
    check('param=pet_item_id,%s' % item in NB[pet], '...the npc names the item')
    check('param=follower_id,%s' % pet in OB[item], '...and the item names the npc')
    check('category=bosspet' in NB[pet] and 'category=bosspet' in OB[item],
          '...both on the category the four follower triggers hang off')
    check('tradeable=no' in OB[item], '...and the item is untradeable')

# ============================================================================ 8
print('8. WHEN the three newest roll, which no base table can say')
FISH = code(read('scripts/skill_fishing/scripts/fishing.rs2'))
MEMBER = code(read('scripts/skill_fishing/scripts/fishing_spots/memberfish.rs2'))
TRAWL = code(read('scripts/minigames/game_trawler/scripts/trawler_win.rs2'))
FARM = code(read('scripts/skill_farming/scripts/farming_actions.rs2'))
THIEF = code(read('scripts/skill_thieving/scripts/thieving.rs2'))

# --- the Heron. Every catch that pays xp must also roll, and it must roll on the struct the fish
# came from: reading $struct1's base after catching $struct2's fish is a whole tier of fish rolling
# at the wrong rate, and nothing else would ever show it.
pairs = re.findall(r'~fishing_xp\(struct_param\((\$struct\d), productexp\)\);\s*'
                   r'~skillpet_roll\(skillpet_heron_item, fishing, '
                   r'struct_param\((\$struct\d), fishing_pet_base\)\);', FISH)
check(len(pairs) == 4, 'all four catches in fish_roll and fish_roll_loc roll: %d' % len(pairs))
check(all(a == b for a, b in pairs),
      '...each off the struct of the fish it just caught: %s' % (pairs or 'none'))
check(FISH.count('~fishing_xp(') == 4 and FISH.count('~skillpet_roll(') == 4,
      'and nothing in fishing.rs2 pays fishing xp without rolling')
# --- the big net is one haul of up to nine things, so it rolls once, for the haul
big = MEMBER.split('[proc,fish_roll_big_net]', 1)[1].split('\n[', 1)[0]
check(big.count('~skillpet_roll(') == 1,
      'the big net rolls once per haul, not once per item: %d' % big.count('~skillpet_roll('))
check('if ($caught > 0) {' in big, '...and only when the haul caught something')
check(big.count('$caught = calc($caught + 1);') == big.count('inv_add(inv,'),
      'every item the net can bring up counts towards that: %d adds, %d counted'
      % (big.count('inv_add(inv,'), big.count('$caught = calc($caught + 1);')))
check('^skillpet_heron_big_net' in big,
      '...at the activity constant, because OSRS gives one figure for big net fishing')
# --- the trawler is one roll per game landed, and its net can only be pulled once
netop = TRAWL.split('[oploc1,game_trawler_reward_net]', 1)[1].split('\n[', 1)[0]
check(netop.count('~skillpet_roll(') == 1, 'the trawler rolls once for the net')
check('^skillpet_heron_trawler' in netop, '...at its own constant')
check('%trawler_catch = 0;' in netop and '%trawler < 3 | %trawler_catch = 0' in TRAWL,
      '...which is once per game landed, the net being emptied and gated on a finished journey')
check(TRAWL.count('~skillpet_roll(') == 1,
      'and the trawler does not also roll per fish out of the net: %d rolls'
      % TRAWL.count('~skillpet_roll('))

# --- the Tangleroot. Check-health where the family has one, the FINAL harvest where it does not.
check(FARM.count('[proc,farming_pet_roll]') == 1, 'one proc names the pet and the skill')
proc = FARM.split('[proc,farming_pet_roll](namedobj $seed)', 1)[1].split('\n[', 1)[0]
check('~skillpet_roll(skillpet_tangleroot_item, farming, oc_param($seed, farming_pet_base))' in proc,
      '...and reads the base off the seed that grew there')
check(FARM.count('~farming_pet_roll($seed);') == 4, 'four call sites: %d'
      % FARM.count('~farming_pet_roll($seed);'))
chk = FARM.split('[proc,farming_check_health]', 1)[1].split('\n[', 1)[0]
check('~farming_pet_roll($seed);' in chk, 'check-health rolls, which is where a tree rolls')
harv = FARM.split('[proc,farming_harvest]', 1)[1].split('\n[', 1)[0]
check(harv.count('~farming_pet_roll($seed);') == 2 and harv.count('~farming_clear_patch(') == 2,
      'the two harvests that clear the patch roll, and only those: %d rolls, %d clears'
      % (harv.count('~farming_pet_roll($seed);'), harv.count('~farming_clear_patch(')))
for i, half in enumerate(harv.split('~farming_clear_patch(')[:-1]):
    check(half.rstrip().endswith('~farming_pet_roll($seed);'),
          '...the roll comes before the clear, while the seed is still known (%d)' % (i + 1))
pick = FARM.split('[proc,farming_pick_produce]', 1)[1].split('\n[', 1)[0]
check(pick.count('~farming_pet_roll($seed);') == 1,
      'picking regrowing produce rolls once and only on the last mushroom: %d'
      % pick.count('~farming_pet_roll($seed);'))
check('~farming_pet_roll($seed);' in pick.split('if ($left <= 1) {', 1)[-1].split('}', 1)[0],
      '...which is the pick that empties the patch, mushrooms having no check-health')
# Every seed with a base must be able to reach a roll: a family with no check-health that never
# clears its patch would hold a base that can never fire.
seeds = params('scripts/_unpack/377/all.obj')
fam = {'6': 'tree', '7': 'fruit_tree', '8': 'cactus', '9': 'calquat', '12': 'spirit_tree',
       '5': 'bush'}
unreachable = [s for s, f in seeds.items()
               if int((f.get('farming_pet_base') or ['0'])[0]) > 0
               and (f.get('farming_family') or ['0'])[0] in fam
               and int((f.get('farming_check_state') or ['0'])[0]) == 0]
check(not unreachable, 'every family that never clears its patch has a check-health to roll at: %s'
      % (unreachable or 'all of them do'))

# --- the Rocky. Two rolls, and the chests get none.
check(THIEF.count('~skillpet_roll(') == 2, 'thieving rolls in exactly two places: %d'
      % THIEF.count('~skillpet_roll('))
for what, col in (('pick_pocket', 'pickpocket:pet_base'), ('steal_from_stall', 'stealing:pet_base')):
    m = re.search(r'~skillpet_roll\(skillpet_rocky_item, thieving, '
                  r'db_getfield\(\$data, ' + re.escape(col) + r', 0\)\);', THIEF)
    check(bool(m), '...one off %s' % col)
dis = THIEF.split('[proc,disarm_trapped_chest]', 1)[1].split('\n[', 1)[0]
check('~skillpet_roll(' not in dis,
      'a trapped chest gives no pet, as in OSRS - only pickpocketing, stalls, Pyramid Plunder and '
      'the Sorceress\'s Garden have a figure')
# The roll must sit with the xp: a success that pays xp cannot then skip the roll, and a roll that
# drifted away from its xp would fire on a failed attempt. The xp line is ~thieving_xp now rather
# than a bare stat_advance - Thieving got a funnel so the Rogue outfit could be found while
# training it (poh_battery group 64) - and the roll still sits directly under it.
check(len(re.findall(r'~thieving_xp\(\$experience\);\n~skillpet_roll\(', THIEF)) == 2,
      'and each roll sits on the line after the xp it belongs to')
check('stat_advance(thieving,' not in THIEF,
      '...which is the funnel, not a direct award, so the outfit roll sees it too')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
