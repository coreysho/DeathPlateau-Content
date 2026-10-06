"""Battery for the FOLLOWER LIFECYCLE and Probita's bureau.

tools/pet_battery.py covers where pets come from (rates and base chances) and
tools/bossart_battery.py covers what they look like. Neither covers what happens to one after you
get it, which is how a pet could be destroyed by a bad tick of the Kalphite Queen and how every
boss pet in the game said "Meow!" every ninety seconds for as long as anyone had one out.

Against tools/followerspec.json. Six groups:

  1. one owner for the slot - the lifecycle scripts, and who calls them
  2. no pet gets cat behaviour - the dispatch, and the categories it dispatches on
  3. death - the pet goes to Probita, the cat goes for good, and the ordering that makes that safe
  4. ownership - one answer to "owns this pet", used everywhere, counting all four places
  5. Probita herself - her record, her art, and where she stands
  6. her window - the .if, the packs, the script, and that nothing is ever charged
  7. the metamorphosis rings - closed, consistent, and remembered in bits wide enough to hold them
  8. the dialogue - one voice per pet, and the follow mode put back afterwards
  9. the looks that are not a right-click - an ore, a seed, and the altar you crafted at

    python3 tools/follower_battery.py
"""
import hashlib, json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt):
    """The source with its comments gone. A claim in a comment is not a claim in the game."""
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

def blocks(txt):
    """[name] blocks -> {name: body}, for a .npc/.obj/.if/.inv config."""
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[([\w+]+)\]', b)
        if m: out[m.group(1)] = code(b)
    return out

def trigger(txt, head):
    """The body of one [trigger,subject] block: from its header to the next [ at column 0."""
    m = re.search(r'(?m)^\[' + re.escape(head) + r'\][^\n]*\n(.*?)(?=^\[|\Z)', txt, re.S)
    return code(m.group(1)) if m else None

SPEC = json.loads(read('tools/followerspec.json'))
LOST, PROB = SPEC['lostpet'], SPEC['probita']

FOLLOWER = read('scripts/npc/scripts/follower.rs2')
CATRS2   = read('scripts/quests/quest_fluffs/scripts/pet.rs2')
BOSSRS2  = read('scripts/npc/scripts/boss_pets.rs2')
SKILLRS2 = read('scripts/npc/scripts/skill_pets.rs2')
EXCH     = read('scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2')
LOGIN    = read('scripts/login_logout/scripts/login.rs2')
LOGOUT   = read('scripts/login_logout/scripts/logout.rs2')
DEATH    = read('scripts/player/scripts/death.rs2')
PROBRS2  = read('scripts/npc/scripts/probita.rs2')
PROBNPC  = read('scripts/npc/configs/probita.npc')
INV      = read('scripts/npc/configs/follower.inv')
IFACE    = read('scripts/npc/interfaces/%s.if' % PROB['iface'])
MAP      = read('maps/%s.jm2' % PROB['map'])
PETOBJ   = read('scripts/npc/configs/boss_pets.obj') + '\n' + read('scripts/npc/configs/skill_pets.obj')
ALLOBJ   = read('scripts/_unpack/377/all.obj')
DAVE     = read('scripts/quests/quest_100/scripts/hundred_dave.rs2')
META     = read('scripts/npc/scripts/pet_metamorph.rs2')
TALK     = read('scripts/npc/scripts/pet_talk.rs2')
FORMNPC  = read('scripts/npc/configs/pet_forms.npc')
FORMCONST= read('scripts/npc/configs/pet_forms.constant')
VAR      = read('scripts/npc/scripts/pet_variants.rs2')
VARENUM  = read('scripts/npc/configs/pet_variants.enum')
RCROW    = read('scripts/skill_runecraft/configs/runecraft.dbrow')
RCALTARS = read('scripts/skill_runecraft/scripts/runecraft_altars.rs2')

# Every .rs2 in the tree, for the "this is the only place that does X" claims.
RS2 = {}
for root, _, files in os.walk(os.path.join(C, 'scripts')):
    for f in files:
        if f.endswith('.rs2'):
            p = os.path.relpath(os.path.join(root, f), C)
            RS2[p] = code(read(p))

def defines(name):
    """Which files define this proc/queue/label, by its header."""
    pat = re.compile(r'(?m)^\[(?:proc|queue|label|timer),' + re.escape(name) + r'\]')
    return sorted(p for p, t in RS2.items() if pat.search(t))

def callers(pat):
    return sorted(p for p, t in RS2.items() if re.search(pat, t))

print('\n-- 1. one owner for the follower slot ------------------------------------------')

for name, kind in (('follower_spawn', 'proc'), ('follower_logout', 'proc'),
                   ('follower_death', 'proc'), ('follower_login', 'queue'),
                   ('follower_is_cat', 'proc'), ('pet_owned', 'proc')):
    d = defines(name)
    check(d == ['scripts/npc/scripts/follower.rs2'],
          '%s is defined once, in npc/scripts/follower.rs2: %s' % (name, d or 'nowhere'))

check(not re.search(r'(?m)^\[(?:proc|queue),follower_', CATRS2),
      'the cat quest defines none of them any more - it is a caller like everything else')
check('~follower_spawn(' in code(CATRS2),
      '...and ~cat_spawn claims the slot through ~follower_spawn')

check('queue(follower_login, 0, 0);' in code(LOGIN), 'login.rs2 queues follower_login')
check('~follower_logout;' in code(LOGOUT), 'logout.rs2 calls ~follower_logout')
check('~follower_death;' in code(DEATH), 'death.rs2 calls ~follower_death')

# The one spawn. Every OTHER write of %follower_uid = npc_uid is a changetype follow-up: the cat
# growing up, or Recipe for Disaster's hell-cat - the npc is the same npc, so the slot is only
# being told its new type. A NEW npc_uid in the slot anywhere else is a second spawn path.
spawn = SPEC['spawn_line']
sites = {p: t.count(spawn) for p, t in RS2.items() if spawn in t}
check(sites.get('scripts/npc/scripts/follower.rs2') == 1,
      'the slot is claimed once in npc/scripts/follower.rs2, and is written in %d files: %s'
      % (len(sites), ', '.join(sorted(os.path.basename(p) for p in sites))))
loose = []
for p, t in sorted(RS2.items()):
    if p == 'scripts/npc/scripts/follower.rs2':
        continue
    for m in re.finditer(re.escape(spawn), t):
        if not re.search(r'npc_changetype_keepall\([^;]*\);\s*$', t[:m.start()]):
            loose.append(os.path.basename(p))
check(not loose,
      'every other write of it follows an npc_changetype_keepall on the line before - the same npc '
      'being told its new type, not a second spawn path: %s' % (sorted(set(loose)) or 'none loose'))

check('npc_setmode(playerfollow);' in code(FOLLOWER)
      and code(BOSSRS2).count('npc_setmode(playerfollow)') == 0
      and code(EXCH).count('npc_setmode(playerfollow)') == 0,
      'and the pets and the metamorphosis no longer set follow mode themselves')

print('\n-- 2. no pet gets cat behaviour -----------------------------------------------')

iscat = trigger(FOLLOWER, 'proc,follower_is_cat')
named = set(re.findall(r'oc_category\(\$item\) = (\w+)', iscat or ''))
check(named == set(SPEC['cat_categories']),
      '~follower_is_cat names exactly the cat categories %s: %s'
      % (SPEC['cat_categories'], sorted(named)))

# The categories are not a guess: they are what the cache's own cat items carry.
cat_items = {n: re.search(r'category=(\w+)', b) for n, b in blocks(ALLOBJ).items()
             if 'param=follower_id,' in b}
cats = {(m.group(1) if m else None) for m in cat_items.values()}
check(cats == set(SPEC['cat_categories']),
      'all %d follower items in the 377 cache carry one of them: %s'
      % (len(cat_items), sorted(c or 'none' for c in cats)))

pet_items = {n: b for n, b in blocks(PETOBJ).items() if 'param=follower_id,' in b}
petcats = {re.search(r'category=(\w+)', b).group(1) for b in pet_items.values()}
check(not (petcats & set(SPEC['cat_categories'])),
      '...and not one of the %d pet items carries a cat category: %s'
      % (len(pet_items), sorted(petcats)))
check(len(pet_items) == LOST['pet_items'],
      'there are %d pet items outside the cat system' % len(pet_items))

logn = trigger(FOLLOWER, 'queue,follower_login')
# The say and the timer must be INSIDE the cat branch, which is a claim about order: the guard
# first, both lines after it.
guard = logn.find('~follower_is_cat(')
check(guard != -1 and logn.find('npc_say(') > guard and logn.find('settimer(petcat_growth') > guard,
      'the login respawn puts the miaow and the growth timer behind ~follower_is_cat')
check('~follower_spawn(~pet_form(%follower_obj));' in logn,
      '...and respawns whatever the slot remembers, in the form it was last put in')
check('oc_param(%follower_obj, follower_id) = null' in logn,
      '...and empties the slot rather than spawning null when the item is no longer a follower')

settimers = {p: t.count('settimer(petcat_growth') for p, t in RS2.items()
             if 'settimer(petcat_growth' in t}
check(settimers == {'scripts/npc/scripts/follower.rs2': 1,
                    'scripts/quests/quest_fluffs/scripts/pet.rs2': 1},
      'petcat_growth is started in exactly two places, the login cat branch and ~cat_spawn: %s'
      % settimers)

grow = trigger(CATRS2, 'timer,petcat_growth')
cg = grow.find('~follower_is_cat(')
check(cg != -1 and 'cleartimer(petcat_growth)' in grow[cg:cg + 200],
      'the growth timer clears itself for a follower that is not a cat, so an old save stops meowing')
check(cg < grow.find('def_category $cat_cat'),
      '...and it does that BEFORE it reads the cat growth stage, which a pet does not have')

print('\n-- 3. death ------------------------------------------------------------------')

dth = trigger(FOLLOWER, 'proc,follower_death')
i_keep = dth.find('def_namedobj $pet = %follower_obj;')
i_clear = dth.find('%follower_obj = null;')
i_store = dth.find('inv_add(%s, $pet, 1)' % LOST['inv'])
i_cat = dth.find('~follower_is_cat($pet)')
check(i_keep != -1 and i_clear != -1 and i_keep < i_clear,
      'death remembers which pet it was before it empties the slot')
check(i_store != -1 and i_store > i_cat > i_clear,
      '...and puts it in %s, on the far side of the cat test' % LOST['inv'])
check('%cat_growth = 0;' in dth and 'npc_del;' in dth,
      '...while a cat still goes for good, growth and all')
check(re.search(r'mes\("[^"]*Probita', dth) is not None,
      '...and the player is told where the pet went')
check('inv_del(%s' % LOST['inv'] not in code(FOLLOWER),
      'nothing in the lifecycle takes a pet back OUT of the store - only Probita does')

print('\n-- 4. one answer to "owns this pet" ------------------------------------------')

own = trigger(FOLLOWER, 'proc,pet_owned')
for frag, what in (('~obj_gettotal($pet) > 0', 'the pack, the bank and what you are wearing'),
                   ('%follower_obj = $pet', 'what is following you'),
                   ('inv_total(%s, $pet) > 0' % LOST['inv'], "what Probita is holding")):
    check(frag in own, '~pet_owned counts %s' % what)

# Every way a pet is handed out goes through ~pet_receive, which asks ~pet_owned and nothing else.
rec = trigger(FOLLOWER, 'proc,pet_receive')
check(rec.find('~pet_owned($pet)') > -1 and rec.find('~pet_owned($pet)') < rec.find('~follower_spawn'),
      '~pet_receive turns away a pet owned anywhere before it gives one')
check('%follower_obj = null & npc_finduid(%follower_uid) = false' in rec and '~follower_spawn(~pet_form($pet))' in rec,
      'with nothing following, the pet comes out and follows you')
check('inv_add(inv, $pet, 1)' in rec and 'inv_add(%s, $pet, 1)' % LOST['inv'] in rec,
      "with a follower out it goes in the pack, and with the pack full to Probita's")
for src, name, frag in ((BOSSRS2, 'the boss pet roll', '~pet_receive_later($pet, 0)'),
                        (SKILLRS2, 'the skilling pet roll', '~pet_receive($pet)'),
                        (EXCH, 'the Fight Cave exchange', '~pet_receive(bosspet_tzrek_jad_item)')):
    c = code(src)
    check(frag in c and '%follower_obj = $pet' not in c and 'obj_add(npc_coord, $pet' not in c,
          '%s gives its pet through ~pet_receive' % name)

print('\n-- 5. Probita ----------------------------------------------------------------')

rec = blocks(PROBNPC).get(PROB['npc'])
check(rec is not None, 'there is a [%s] npc record' % PROB['npc'])
ops = dict(re.findall(r'op(\d)=(.+)', rec or ''))
check(ops == PROB['ops'], "her ops are the cache's own, %s: %s" % (PROB['ops'], ops))
check('vislevel=hide' in rec and 'wanderrange=0' in rec,
      '...she has no combat level and does not wander off')
check('readyanim=human_ready' in rec and 'walkanim=human_walk_f' in rec,
      '...and moves on the 377 human animations, like the estate agent')

pack = {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/model.pack').split('\n') if l)}
npcpack = {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/npc.pack').split('\n') if l)}
check(PROB['npc'] in npcpack, '...and a line in npc.pack')
pid = npcpack.get(PROB['npc'])
named_models = re.findall(r'(?:model|head)\d+=(\S+)', rec or '')
check(len(named_models) == PROB['models'] + PROB['heads'],
      'her record names %d models and %d chatheads' % (PROB['models'], PROB['heads']))
missing = [m for m in named_models if m not in pack
           or not os.path.exists(os.path.join(C, 'models/npc', m + '.ob2'))]
check(not missing, '...every one of them packed and on disk: %s' % (missing or 'all present'))
bad = [m for m in named_models
       if hashlib.sha1(open(os.path.join(C, 'models/npc', m + '.ob2'), 'rb').read()).hexdigest()
       != PROB['model_sha1'].get(m)]
check(not bad, "...and every one is OSRS npc %d's own art, re-encoded: %s"
      % (PROB['osrs'], bad or 'all nine match'))

npcsec = MAP.split('==== NPC ====')[1].split('====')[0]
spawns = re.findall(r'(?m)^(\d) (\d+) (\d+): (\d+)$', npcsec)
mine = [(int(a), int(b), int(c)) for a, b, c, i in spawns if pid is not None and int(i) == pid]
check(mine == [tuple(PROB['tile'])],
      'she is spawned exactly once, at %s in maps/%s.jm2: %s'
      % (PROB['tile'], PROB['map'], mine))
aemad = [(int(a), int(b), int(c)) for a, b, c, i in spawns
         if int(i) == npcpack.get('aemad', -1)]
check(tuple(PROB['aemad_tile']) in aemad,
      "...in the same map square as Aemad's Adventuring Supplies %s" % PROB['aemad_tile'])
lv, x, z = PROB['tile']
alv, ax, az = PROB['aemad_tile']
check(lv == alv and max(abs(x - ax), abs(z - az)) <= PROB['reach'],
      '...and %d tiles from him, which is what "the small building next to Aemad\'s" means'
      % max(abs(x - ax), abs(z - az)))
locsec = MAP.split('==== LOC ====')[1].split('====')[0]
onher = [l for l in locsec.split('\n') if l.startswith('%d %d %d:' % (lv, x, z))]
solid = [l for l in onher if int(re.search(r': (\d+)', l).group(1)) and
         (len(l.split(':')[1].split()) == 1 or int(l.split(':')[1].split()[1]) in (10, 11))]
check(not solid, '...on a tile with nothing standing on it: %s' % (onher or 'bare ground'))

print('\n-- 6. the window -------------------------------------------------------------')

coms = blocks(IFACE)
grid = coms.get('pets')
check(grid is not None and 'type=inv' in grid, 'the window has an inv grid called pets')
gw = int(re.search(r'width=(\d+)', grid).group(1))
gh = int(re.search(r'height=(\d+)', grid).group(1))
# The label quotes the SPEC's numbers, not the measured ones: a label that prints what it just
# measured moves with the mutation and never names the check that caught it.
check((gw, gh) == (LOST['grid_cols'], LOST['grid_rows']),
      '...%d slots across by %d down' % (LOST['grid_cols'], LOST['grid_rows']))
size = int(re.search(r'size=(\d+)', blocks(INV)[LOST['inv']]).group(1))
check(size == gw * gh,
      '...and %s holds exactly as many as the window can show: %d = %d'
      % (LOST['inv'], size, gw * gh))
check(size >= LOST['pet_items'],
      '...which is enough for every pet item in the tree (%d)' % LOST['pet_items'])
check('scope=%s' % LOST['scope'] in blocks(INV)[LOST['inv']]
      and 'stackall' not in blocks(INV)[LOST['inv']],
      '...saved with the character, and nothing stacks in it, so used slots ARE pets')
check('option1=Reclaim' in grid and 'interactable=yes' in grid,
      '...and its one option is Reclaim')

ifpack = [l for l in read('pack/interface.pack').split('\n') if l]
ids = {n: int(i) for i, n in (l.split('=', 1) for l in ifpack)}
order = [int(l) for l in read('pack/interface.order').split('\n') if l.strip()]
check(PROB['iface'] in ids, 'the window itself is in interface.pack')
absent = [n for n in coms if '%s:%s' % (PROB['iface'], n) not in ids]
check(not absent, '...with every one of its %d components: %s'
      % (len(coms), absent or 'all present'))
check(set(order) == set(ids.values()) and len(order) == len(ids),
      'interface.order and interface.pack agree exactly - an id in one and not the other packs a '
      'component with type -1 and the client throws on load')

pc = code(PROBRS2)
check('if_openmain(%s);' % PROB['iface'] in pc, 'Check opens the window')
check('[opnpc3,%s] ~probita_open;' % PROB['npc'] in pc,
      "...off op3, which is the op the cache gives her for it")
check('inv_transmit(%s, %s:pets);' % (LOST['inv'], PROB['iface']) in pc,
      '...transmitting the store to the grid')
check('inv_stoptransmit(%s:pets);' % PROB['iface'] in pc
      and '[if_close,%s]' % PROB['iface'] in pc,
      '...and stopping when it closes')
for com in ('subtitle', 'help'):
    check('if_settext(%s:%s,' % (PROB['iface'], com) in pc and com in coms,
          '...%s is set by the script and exists in the .if' % com)
check('inv_size(%s) - inv_freespace(%s)' % (LOST['inv'], LOST['inv']) in pc,
      '~probita_count is the used slots of the store')

recl = trigger(PROBRS2, 'inv_button1,%s:pets' % PROB['iface'])
check(recl is not None, 'clicking a pet in the grid is handled')
ops_used = sorted(set(re.findall(r'\b(inv_\w+)\(', recl or '')))
check(ops_used == sorted(PROB['free']['reclaim_inv_ops']),
      '...and it touches only %s: %s' % (', '.join(sorted(PROB['free']['reclaim_inv_ops'])), ops_used))
check('inv_freespace(inv) = 0' in (recl or ''),
      '...refusing without a free slot, the same way picking a pet up off the ground does')
bad = [w for w in PROB['free']['forbidden_symbols'] if re.search(r'\b%s\b' % w, pc)]
check(not bad, 'nothing in the bureau names a currency - reclaiming is free: %s'
      % (bad or 'no coins anywhere'))

print('\n-- 7. the metamorphosis rings ------------------------------------------------')

PETRECS = {}
# The Pet snakeling's base record is the one pet that does not live in boss_pets.npc: it is in
# area_zulrah/configs/zulrah.npc beside the snake it drops from, which is where the rest of Zulrah's
# configs are. Leaving it out made its ring look open at the base.
for src in (read('scripts/npc/configs/boss_pets.npc'), read('scripts/npc/configs/skill_pets.npc'),
            read('scripts/areas/area_zulrah/configs/zulrah.npc'), FORMNPC):
    for n, b in blocks(src).items():
        # A PET RECORD IS ONE THAT CARRIES THE ITEM, not every record in these files. zulrah.npc is
        # read for the one pet in it and holds eight other npcs; without this the count below became
        # "61 pet records" and meant nothing.
        if 'param=pet_item_id' in b:
            PETRECS[n] = b
# The label prints the MEASURED count, because the mutation for this moves the spec's. Tenth time
# this has come up: print the side the mutation does not touch.
check(len(PETRECS) == SPEC['pet_records'],
      'there are %d pet npc records, base forms and metamorphosis forms together' % len(PETRECS))

def rec_item(n): 
    m = re.search(r'param=pet_item_id,(\w+)', PETRECS[n]); return m.group(1) if m else None
def rec_next(n):
    m = re.search(r'param=metamorph_next,(\w+)', PETRECS[n]); return m.group(1) if m else None

# Walk each ring from its named base. A ring that does not come back to where it started is the
# failure this checks for: the walk in ~pet_form would run off the end of it.
for base, want in sorted(SPEC['rings'].items()):
    ring, at, ok = [base], rec_next(base), True
    while at and at != base and len(ring) < 40:
        ring.append(at)
        at = rec_next(at)
    check(at == base and len(ring) == want['forms'],
          '%s is a closed ring of %d forms: %d, %s'
          % (base, want['forms'], len(ring), 'closed' if at == base else 'OPEN at ' + str(at)))
    items = sorted({rec_item(n) for n in ring})
    check(len(items) == want['items'],
          '...and its forms carry %d pet item(s), which is what decides whether %%pet_form has to '
          'remember the form at all: %s' % (want['items'], items))
    # Whether a ring HAS a right-click is a property of the ring: the rock golem's looks come off
    # an ore and the tangleroot's off a seed, and neither carries the op in the cache or here.
    if want['op4']:
        missing = [n for n in ring if 'op4=Metamorphosis' not in PETRECS[n]]
        check(not missing, '...and every form in it has the right-click: %s'
              % (missing or 'all %d' % len(ring)))
    else:
        stray = [n for n in ring if 'op4=Metamorphosis' in PETRECS[n]]
        check(not stray, '...and not one form in it has the right-click, because nothing cycles '
              'this pet: %s' % (stray or 'none of %d' % len(ring)))
    models = [m for n in ring for m in re.findall(r'(?:model|head)\d+=(\S+)', PETRECS[n])]
    gone = [m for m in models if m not in pack
            or not os.path.exists(os.path.join(C, 'models/npc', m + '.ob2'))]
    check(not gone, '...and all %d of their models are packed and on disk: %s'
          % (len(models), gone or 'all present'))

# No pet outside a ring may carry the op: op4 with no metamorph_next is a right-click that says
# "Nothing happens", which is worse than no right-click.
stray = [n for n in PETRECS if 'op4=Metamorphosis' in PETRECS[n] and not rec_next(n)]
check(not stray, 'no pet has the right-click without a ring to spend it on: %s'
      % (stray or 'none'))

# The bit ranges: wide enough for their own ring, and not overlapping.
CONSTNAME = {'bosspet_kalphite_queen': 'kalphite', 'skillpet_heron': 'heron',
             'skillpet_chinchompa': 'chinchompa', 'skillpet_rift_guardian': 'rift',
             'skillpet_rock_golem': 'golem', 'skillpet_tangleroot': 'tangleroot',
             'bosspet_snakeling': 'snakeling'}
owner = {}
for base, want in sorted(SPEC['rings'].items()):
    if want['bits'] is None:
        check('%s_item' % base not in (GET_SRC := code(META).split('[proc,pet_form_get]', 1)[-1]
                                       .split('\n[', 1)[0]),
              '%s spends no %%pet_form bits, because its two forms are two items' % base)
        continue
    lo, hi = want['bits']
    # Labels quote the RING, never the range: the mutations for these move the range.
    check(2 ** (hi - lo + 1) >= want['forms'],
          '%s has enough of %%pet_form to hold its %d forms' % (base, want['forms']))
    for b in range(lo, hi + 1):
        owner.setdefault(b, []).append(base)
    name = CONSTNAME.get(base)
    check(name is not None
          and re.search(r'\^pet_form_%s_lo\s*=\s*%d' % (name, lo), FORMCONST) is not None
          and re.search(r'\^pet_form_%s_hi\s*=\s*%d' % (name, hi), FORMCONST) is not None,
          '...and %s says the same range in pet_forms.constant'
          % (name or base + ' has no constant at all'))
clash = {b: v for b, v in owner.items() if len(v) > 1}
check(not clash, 'no two rings share a bit of %%pet_form: %s'
      % (clash or 'bits %s, one owner each' % sorted(owner)))

GET = trigger(META, 'proc,pet_form_get')
SET = trigger(META, 'proc,pet_form_set')
gets = re.findall(r'case (\w+_item) :', GET or '')
sets = re.findall(r'case (\w+_item) :', SET or '')
check(gets == sets and gets,
      'the two halves of %%pet_form name the same items in the same order: %s' % (gets == sets))
check(sorted(gets) == sorted(b + '_item' for b, w in SPEC['rings'].items() if w['bits']),
      '...and they are exactly the rings whose forms share one item: %s' % sorted(gets))

op = trigger(META, 'opnpc4,_bosspet')
check('~pet_form_nextallowed($item, npc_type)' in op and '~follower_spawn($next);' in op,
      'the right-click spawns the next ALLOWED form through ~follower_spawn - allowed because the '
      'rift guardian only cycles colours it has unlocked')
i_same = op.find('nc_param($next, pet_item_id) = $item')
i_set = op.find('~pet_form_set(')
check(i_same != -1 and i_set > i_same,
      '...and only remembers a form when the item did not change, which is what keeps TzRek-Jad '
      'and JalRek-Jad out of the bits')
check('~pet_form(last_item)' in code(BOSSRS2),
      'and a pet put down comes back in the form it was in, not its base one')

print('\n-- 8. the dialogue -----------------------------------------------------------')

tk = trigger(TALK, 'opnpc3,_bosspet')
check(tk is not None and 'switch_obj (npc_param(pet_item_id))' in tk,
      'talking to a pet dispatches on its ITEM, so every metamorphosis form answers as itself')
cases = dict(re.findall(r'case (\w+_item) : ~(\w+);', tk or ''))
petitems = sorted(n for n in blocks(PETOBJ) if 'param=follower_id,' in blocks(PETOBJ)[n])
check(sorted(cases) == petitems,
      'all %d pets have a voice of their own: %d cases%s'
      % (len(petitems), len(cases),
         '' if sorted(cases) == petitems else ', missing ' + str(sorted(set(petitems) - set(cases)))))
absent = [p for p in cases.values() if not defines(p)]
check(not absent, '...and every one of them is a proc that exists: %s' % (absent or 'all present'))
thin = []
for proc in sorted(set(cases.values())):
    body = trigger(TALK, 'proc,' + proc) or ''
    if ('random(%d)' % SPEC['talk']['variants']) not in body \
       or len(set(re.findall(r'case (\d) :', body))) != SPEC['talk']['variants']:
        thin.append(proc)
check(not thin, '...each with %d things to say, chosen at random: %s'
      % (SPEC['talk']['variants'], thin or 'all %d' % len(set(cases.values()))))
check('case default : ~%s;' % SPEC['talk']['default_proc'] in tk,
      'a pet added without a voice falls back to the old line rather than saying nothing')
check('~follower_refollow;' in code(TALK),
      'and the pet goes back to following afterwards - ~chatnpc leaves it on playerfaceclose')
follow = {p: t.count('npc_setmode(playerfollow)') for p, t in RS2.items()
          if 'npc_setmode(playerfollow)' in t and 'macro' not in p}
# The third is not a follower at all: a teased spined larupia chases the hunter who poked it, which is
# what springs a pitfall (skill_hunter, 2026-09-23). It is named here so that the set stays closed -
# a fourth file setting playerfollow still has to explain itself.
check(set(follow) == {'scripts/npc/scripts/follower.rs2',
                      'scripts/quests/quest_fluffs/scripts/pet.rs2',
                      'scripts/skill_hunter/scripts/hunter_traps.rs2'},
      'follow mode is set in the slot\'s own file, for the cats\' vermin hunt in the cat quest, and for a teased larupia: %s'
      % sorted(os.path.basename(p) for p in follow))

print('\n-- 9. the looks that are not a right-click -----------------------------------')

V = SPEC['variants']
def enum_rows(name):
    b = re.search(r'(?m)^\[' + name + r'\]\n(.*?)(?=^\[|\Z)', VARENUM, re.S)
    return dict(re.findall(r'(?m)^val=(\w+),(\w+)$', b.group(1))) if b else {}

objpack = {n for i, n in (l.split('=', 1) for l in read('pack/obj.pack').split('\n') if l)}
GOLEM = enum_rows('golem_ore_form')
check(sorted(GOLEM) == sorted(V['golem_ores']),
      'the golem answers to %d ores and a plain rock, and nothing else: %s'
      % (len(V['golem_ores']) - 1, sorted(set(GOLEM) ^ set(V['golem_ores'])) or 'exactly those'))
missing = [o for o in GOLEM if o not in objpack]
check(not missing, '...every one of which is a real item in this build: %s'
      % (missing or 'all %d' % len(GOLEM)))
check(GOLEM.get('rock') == 'skillpet_rock_golem',
      "...and a plain rock is what puts it back, which is Old School's own way round")
TANG = enum_rows('tangleroot_seed_form')
check(sorted(TANG) == sorted(V['tangleroot_seeds']),
      'the tangleroot answers to %s and nothing else: %s'
      % (' and '.join(V['tangleroot_seeds']), sorted(TANG)))
check(TANG.get('acorn') == 'skillpet_tangleroot', '...and an acorn is what puts it back')
absent = [n for n in PETRECS if n.startswith('skillpet_tangleroot_')
          and n != 'skillpet_tangleroot_herb']
check(not absent, 'the four tangleroot looks whose seeds do not exist here are NOT imported - an '
      'npc nothing can reach is dead weight: %s' % (absent or 'none of them'))

# Every form these two tables name has to be in that pet's own ring, or the pet would be repainted
# into something that is not one of its looks.
for table, base in ((GOLEM, 'skillpet_rock_golem'), (TANG, 'skillpet_tangleroot')):
    ring, at = [base], rec_next(base)
    while at and at != base:
        ring.append(at); at = rec_next(at)
    off = sorted(set(table.values()) - set(ring))
    check(not off, '...and every look it names belongs to %s\'s own ring: %s'
          % (base, off or 'all %d' % len(set(table.values()))))

check('[opnpcu,_bosspet]' in code(VAR) and '[opheldu,_bosspet]' in code(VAR),
      'an item can be used on a pet standing in front of you or sitting in your pack, as Old '
      'School allows')
gold = trigger(VAR, 'proc,golem_ore')
tang = trigger(VAR, 'proc,tangleroot_seed')
check('inv_del(' not in (gold or ''),
      'the ore is not consumed - it is a sample, not a sacrifice')
check('inv_del(inv, $seed, 1);' in (tang or ''),
      '...and the seed IS consumed, which is what makes the acorn that puts it back a real cost')
wear = trigger(VAR, 'proc,pet_wearform')
check('~pet_form_set(' in (wear or '') and '~follower_spawn($form);' in (wear or ''),
      'a new look is remembered and, if the pet is out, respawned in it')
check('if ($out = true & npc_finduid(%follower_uid) = true) {' in (wear or ''),
      '...and only respawned when there is something standing there to respawn')

# The rift guardian: twelve altars, twelve colours, and the mapping covers exactly the altars this
# build has - no more (a colour nothing can unlock) and no fewer (an altar that paints nothing).
RUNES = re.findall(r'data=rune,(\w+)', RCROW)
RIFT = enum_rows('rift_rune_form')
check(len(RUNES) == V['rift_altars'],
      'this build has %d runecrafting altars' % len(RUNES))
check(sorted(RIFT) == sorted(RUNES),
      '...and the guardian has a colour for every one of them and for nothing else: %s'
      % (sorted(set(RIFT) ^ set(RUNES)) or 'exactly those'))
check(len(set(RIFT.values())) == len(RIFT),
      '...no two altars painting the same colour: %d colours for %d altars'
      % (len(set(RIFT.values())), len(RIFT)))
gring, at = ['skillpet_rift_guardian'], rec_next('skillpet_rift_guardian')
while at and at != 'skillpet_rift_guardian':
    gring.append(at); at = rec_next(at)
off = sorted(set(RIFT.values()) - set(gring))
check(not off, "...and every colour is one of the guardian's own fifteen: %s"
      % (off or 'all %d' % len(RIFT)))
# ...and it is Jagex's mapping, not a guess: each form's OSRS npc id is the '// OSRS npc' comment
# on its record, and Jagex's config name for that id (RuneLite's gameval NpcID,
# SKILLPET_RUNECRAFTING_<ALTAR>) says which altar it is for. The first mapping here was chosen by
# recolour matching and crossed four altars; this is the check that would have caught it.
OSRSID = {}
for src in (read('scripts/npc/configs/skill_pets.npc'), FORMNPC):
    for b in re.split(r'(?m)^(?=\[)', src):
        m = re.match(r'\[(\w+)\]\n// OSRS npc (\d+)', b)
        if m: OSRSID[m.group(1)] = m.group(2)
GAMEVAL = V['rift_gameval']
unnamed = [f for f in gring if GAMEVAL.get(OSRSID.get(f)) is None]
check(not unnamed, "every one of the guardian's fifteen records names its OSRS npc, and Jagex's "
      'config names that npc for an altar: %s' % (unnamed or 'all %d' % len(gring)))
crossed = sorted((r, f, GAMEVAL.get(OSRSID.get(f))) for r, f in RIFT.items()
                 if GAMEVAL.get(OSRSID.get(f)) != r[:-4])
check(not crossed, '...and every altar paints the form Jagex names for it: %s'
      % (crossed or 'all %d' % len(RIFT)))
check(RIFT.get('firerune') == 'skillpet_rift_guardian',
      '...so fire paints the base, 7354 - the same guardian a tiara gives, with no altar behind it')

for f in V['rift_roll_hooks']:
    check('~rift_guardian_roll(' in code(read(f)),
          '%s rolls the guardian through the wrapper that knows the rune' % os.path.basename(f))
check('~rift_guardian_roll(null, 1);' in code(read(V['rift_roll_hooks'][2])),
      '...and the tiara passes null, so a tiara gives the base guardian, the fire one')
# The combination-rune path: the colour follows the ALTAR, and a mist rune can be bound at either
# the air altar or the water one - so every call has to pass the rune of the altar it sits under.
altar, wrong = None, []
for line in code(RCALTARS).split('\n'):
    m = re.match(r'\[oplocu,(\w+)_altar\]', line)
    if m: altar = m.group(1)
    if '~runecraft_combo_rune(' in line:
        arg = line.rstrip(');').rsplit(',', 1)[-1].strip()
        if arg != altar + 'rune': wrong.append((altar, arg))
check(not wrong, 'every combination-rune call passes the rune of the altar it stands at: %s'
      % (wrong or 'all twelve'))

unlock = trigger(VAR, 'proc,rift_unlock')
check('setbit(%rift_unlocked, 0)' in (unlock or ''),
      'bit 0 of %rift_unlocked - the base guardian, the fire one - is always set, so the right-click has '
      'somewhere to go back to')
check('~pet_form_index(skillpet_rift_guardian_item, ~rift_form($rune))' in (unlock or ''),
      '...and crafting at an altar sets that colour\'s own bit for good')
allowed = trigger(META, 'proc,pet_form_allowed')
check('if ($item ! skillpet_rift_guardian_item) {' in (allowed or '')
      and 'return(true);' in (allowed or ''),
      'only the rift guardian has to earn its colours; every other pet may wear all of its looks')
check('~rift_locked(~pet_form_index($item, $form))' in (allowed or '')
      and 'testbit(%rift_unlocked' in code(VAR),
      '...and what it may wear is what %rift_unlocked says, read in exactly one place')
lock = trigger(VAR, 'opnpc5,_bosspet')
check(lock is not None and 'npc_param(pet_item_id) ! skillpet_rift_guardian_item' in lock,
      'Locking is the guardian\'s alone, and says so rather than silently doing nothing')
check('^pet_form_rift_locked_lo' in lock and 'setbit_range_toint' in lock,
      '...and it toggles the one bit of %pet_form that is not a form number')
roll = trigger(VAR, 'proc,rift_guardian_roll')
check('^pet_form_rift_locked_lo' in (roll or ''),
      'a locked guardian still unlocks the colour but is not repainted by the altar')
locked_recs = [n for n in PETRECS if 'op5=Locking' in PETRECS[n]]
check(sorted(locked_recs) == sorted(gring),
      'op5=Locking is on all %d guardian records and on no other pet: %d records'
      % (len(gring), len(locked_recs)))

# The picker window. Its cells ARE the ring, in ring order, which is what lets fifteen one-line
# handlers stand in for a table - so the window drifting out of step with the ring is the failure
# this checks for.
PICK = blocks(read('scripts/npc/interfaces/rift_metamorph.if'))
cellnums = sorted(int(n[4:]) for n in PICK if re.fullmatch(r'cell\d+', n))
RUNENAME = {f: r for r, f in RIFT.items()}
# A cell is named for its RING INDEX, not its position, and only the colours an altar in THIS
# build can unlock get one: a cell for a colour nothing can ever reach is a dead square.
want_cells = [i for i, f in enumerate(gring) if i == 0 or f in RUNENAME]
check(cellnums == want_cells,
      'the picker has a cell for the base guardian and for each of the %d altars, and for nothing '
      'else: %s' % (len(RIFT), cellnums if cellnums != want_cells else 'ring indices %s' % want_cells))
# The grid is the whole answer: the window carries no text the script has to keep current. It used
# to caption the grid with a count of unlocked colours, which said what the grid already shows -
# and said it wrongly, because constants are NOT substituted inside if_settext string literals, so
# it printed "^rift_pickable_colours" at the player. So the only thing the script does to this
# window is hide icons, and this is the check that keeps it that way.
blank = [n for n in PICK if re.search(r'(?m)^text=\s*$', PICK[n])]
check('if_settext(rift_metamorph:' not in code(VAR) and not blank,
      'the picker has no script-set text, so nothing in it can go stale or print the name of a '
      'constant at the player: %s' % (blank or 'no empty text component, no if_settext'))
# ...and the guardian is centred in its cell. The model BOX is not the guardian: rendered with
# tools/ifrender.py at this camera the mesh comes out 26x28 at offset (9, 0) inside the 44x50 box,
# and the label's ink is the top 9 rows of its 13-tall component. Centring the box put the
# guardian high and left of its cell's middle, which is the complaint these numbers answer, so
# what gets measured here is the DRAWN rectangle and the label INK. Re-measure if either changes -
# tools/genriftpicker.py holds the same four numbers and a note saying so.
DRAWN_W, DRAWN_H, DRAWN_OX, DRAWN_OY, NAME_INK = 26, 28, 9, 0, 9
# twelve cells, four by three at 116 (genriftpicker.py says why)
CELL_W, CELL_H = 116, 78


def geom(name, i):
    b = PICK['%s%d' % (name, i)]
    return tuple(int(re.search(r'(?m)^%s=(-?\d+)$' % k, b).group(1)) for k in 'xy')


layouts = {(geom('icon', i), geom('name', i)) for i in cellnums}
check(len(layouts) == 1, 'every cell of the grid is laid out identically: %d layouts across %d '
      'cells' % (len(layouts), len(cellnums)))
ragged = []
for i in cellnums:
    (ix, iy), (nx, ny) = geom('icon', i), geom('name', i)
    left, right = ix + DRAWN_OX, CELL_W - (ix + DRAWN_OX + DRAWN_W)
    top, bottom = iy + DRAWN_OY, CELL_H - (ny + NAME_INK)
    if abs(left - right) > 1 or abs(top - bottom) > 1:
        ragged.append((i, left, right, top, bottom))
check(not ragged, '...and the guardian and its label sit centred in it, margins even to within a '
      'pixel: %s' % (ragged or 'all %d cells' % len(cellnums)))
wrong = []
for i in cellnums:
    want = re.search(r'model1=(\S+)', PETRECS[gring[i]]).group(1)
    got = re.search(r'model=(\S+)', PICK.get('model%d' % i, '') or 'model=-')
    if not got or got.group(1) != want:
        wrong.append((i, gring[i], got.group(1) if got else None))
check(not wrong, '...each showing the model of the form at that ring index: %s'
      % (wrong or 'all %d' % len(cellnums)))
wrong = []
for i in cellnums:
    rune = RUNENAME.get(gring[i])
    want = rune[:-4].capitalize() if rune else 'Plain'
    got = re.search(r'text=(.*)', PICK.get('name%d' % i, ''))
    if not got or got.group(1).strip() != want:
        wrong.append((i, want, got.group(1).strip() if got else None))
check(not wrong, '...and labelled with the altar that unlocks it: %s'
      % (wrong or 'all %d' % len(cellnums)))
absent = [n for n in PICK if 'rift_metamorph:%s' % n not in ids]
check('rift_metamorph' in ids and not absent,
      '...with every one of its %d components in interface.pack: %s'
      % (len(PICK), absent or 'all present'))
op = trigger(META, 'opnpc4,_bosspet')
check('if ($item = skillpet_rift_guardian_item) {' in op and '~rift_metamorph_open;' in op,
      "the guardian's right-click opens that window instead of cycling")
pc = code(VAR)
hides = sorted(int(x) for x, y in
               re.findall(r'if_sethide\(rift_metamorph:icon(\d+), ~rift_locked\((\d+)\)\);', pc)
               if x == y)
buttons = sorted(int(x) for x, y in
                 re.findall(r'\[if_button,rift_metamorph:hit(\d+)\] ~rift_pick\((\d+)\);', pc)
                 if x == y)
check(hides == cellnums and buttons == cellnums,
      '...and every cell is both hidden when locked and clickable, each naming its own ring index: '
      '%d hides, %d buttons' % (len(hides), len(buttons)))
pick = trigger(VAR, 'proc,rift_pick')
check('~rift_locked($index) = true' in (pick or '') and 'mes(' in (pick or ''),
      'choosing a colour you have not unlocked says so rather than doing nothing')
check('~pet_form_walk(skillpet_rift_guardian_item, $index)' in (pick or ''),
      '...and a cell is an index into the ring, walked the same way the login respawn walks it')

print('\nALL PASS' if not fails else '\n%d FAILED' % fails)
sys.exit(1 if fails else 0)
