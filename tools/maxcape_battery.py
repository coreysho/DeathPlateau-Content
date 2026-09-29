"""Battery for the Max cape, the Construction cape and the elder chaos druid robes.

Everything here is PARSED OUT of the delivered files - the item bonuses from the .obj configs, the
requirement and the price from the scripts that compute them, the spawns from the real maps, the
drop rates from the drop table's own arithmetic - so a change to one of them cannot pass a check
still asserting the old value. The numbers on the right-hand side of a comparison are OSRS's, from
oldschool.runescape.wiki (Max_cape, Max_hood, Elder_chaos_druid and the three robe pages).

    python3 tools/maxcape_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

def nocomment(txt):
    """The code with // comments and string bodies taken out.

    WRITTEN BECAUSE MY OWN COMMENT PASSED A CHECK. Two checks below quote the exact thing they
    forbid - return(a = b), and a second [opheldu,max_cape] - and the comments beside the code
    explain the trap by naming it, so a raw-text search found the comment and called it the code.
    Third time in this project. A check has to read the code.
    """
    out = []
    for line in txt.split('\n'):
        out.append(re.sub(r'"[^"]*"', '""', line).split('//')[0])
    return '\n'.join(out)

def pack(name):
    out = {}
    for line in read('pack/' + name).split('\n'):
        if '=' in line:
            i, n = line.split('=', 1)
            out[n.strip()] = int(i)
    return out

def blocks(txt):
    """A .obj/.npc config into {name: {key: [values]}}."""
    out = {}
    cur = None
    for line in txt.split('\n'):
        line = line.split('//')[0].strip()
        if not line: continue
        if line.startswith('[') and line.endswith(']'):
            cur = {}; out[line[1:-1]] = cur; continue
        if cur is None or '=' not in line: continue
        k, v = line.split('=', 1)
        cur.setdefault(k, []).append(v)
    return out

OBJP, NPCP, MODELP = pack('obj.pack'), pack('npc.pack'), pack('model.pack')
SEQP, SPOTP, ANIMP = pack('seq.pack'), pack('spotanim.pack'), pack('anim.pack')
MAXOBJ = blocks(read('scripts/skillcapes/configs/max_cape.obj'))
CAPES = blocks(read('scripts/skillcapes/configs/skillcapes.obj'))
ELDER = blocks(read('scripts/areas/area_wilderness/configs/elder_chaos.obj'))
ECDNPC = blocks(read('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc'))
MACNPC = blocks(read('scripts/skillcapes/configs/skillcape_npcs.npc'))
EQUIP = read('scripts/skillcapes/scripts/skillcape_equip.rs2')
PERKS = read('scripts/skillcapes/scripts/skillcape_perks.rs2')
SHOP = read('scripts/skillcapes/scripts/skillcape_shop.rs2')
SCENUM = read('scripts/skillcapes/configs/skillcape.enum')
STATENUM = read('scripts/player/configs/stat.enum')
TIER40 = read('scripts/levelrequire/scripts/tier40.rs2')
DROPS = read('scripts/drop_tables/scripts/elder_chaos_druid.rs2')
CONST = read('scripts/skillcapes/configs/skillcape.constant') + '\n' \
      + read('scripts/areas/area_wilderness/configs/elder_chaos.constant')
def const(n):
    return int(re.search(r'\^' + n + r'\s*=\s*(-?\d+)', CONST).group(1))

def enum_rows(txt, name):
    body = txt.split('[' + name + ']', 1)[1].split('\n[', 1)[0]
    return dict(re.findall(r'^val=([^,\n]+),(.*)$', body, re.M))

STATS = enum_rows(STATENUM, 'stats')

# ============================================================================ 1
print('1. the two items are real, and every model they name is in the cache')
check(set(MAXOBJ) == {'max_cape', 'max_hood'}, 'max_cape.obj holds the cape and the hood')
for name in ('max_cape', 'max_hood'):
    check(name in OBJP, '%s has an id in obj.pack (%s)' % (name, OBJP.get(name)))
missing = []
for name, cfg in list(MAXOBJ.items()) + list(ELDER.items()):
    for key in ('model', 'manwear', 'womanwear', 'manwear2', 'womanwear2', 'manhead', 'womanhead'):
        for v in cfg.get(key, []):
            m = v.split(',')[0]
            if m not in MODELP or not os.path.exists(os.path.join(C, 'models', 'obj', m + '.ob2')):
                missing.append((name, m))
check(not missing, 'all %d models of the five new items are in model.pack and on disk: %s'
      % (sum(len(c.get(k, [])) for c in list(MAXOBJ.values()) + list(ELDER.values())
             for k in ('model', 'manwear', 'womanwear', 'manwear2', 'womanwear2', 'manhead', 'womanhead')),
         missing[:3] or 'yes'))

# ============================================================================ 2
print('2. the Max cape wears like a trimmed skillcape, and keeps its Drop option')
prm = {}
for p in MAXOBJ['max_cape'].get('param', []):
    k, v = p.split(',', 1)
    prm[k] = v
check(all(prm.get(k) == '9' for k in ('stabdefence', 'slashdefence', 'crushdefence',
                                      'magicdefence', 'rangedefence')),
      'the +9 all-round defence of a Cape of Accomplishment: %s' % prm)
check(prm.get('prayerbonus') == '4', 'and the +4 prayer a trimmed one gives')
# the same defence a real skill cape carries, read off the Attack cape rather than written twice
acape = {p.split(',')[0]: p.split(',')[1] for p in CAPES['attack_cape'].get('param', [])}
check(all(acape.get(k) == prm.get(k) for k in ('stabdefence', 'magicdefence')),
      'which is the same number the Attack cape carries, not a second opinion')
check(MAXOBJ['max_cape'].get('category') == ['armour_cape'], 'it is an armour_cape like the rest')
check(MAXOBJ['max_cape'].get('tradeable') == ['no'] and MAXOBJ['max_hood'].get('tradeable') == ['no'],
      'neither piece is tradeable')
iops = {k: v[0] for k, v in MAXOBJ['max_cape'].items() if k.startswith('iop')}
check(iops == {'iop2': 'Wear', 'iop3': 'Teleports', 'iop4': 'Features'},
      'the ops are Wear, Teleports and Features: %s' % iops)
check('iop5' not in iops, "and iop5 is left alone, so Drop still works on an untradeable cape")
check(MAXOBJ['max_hood'].get('iop2') == ['Wear'] and len(
      [k for k in MAXOBJ['max_hood'] if k.startswith('iop')]) == 1,
      'the hood only wears, like every other skillcape hood')
check(MAXOBJ['max_hood'].get('param') is None, 'and carries no bonuses at all, as in OSRS')

# ============================================================================ 3
print('3. it needs 99 in every skill that HAS a cape, and Mac charges by the skill')
# THE COUNT IS NOT THE STATS ENUM ANY MORE. Hunter (stat 22, 2026-09-22) is a real stat that levels
# and saves with no way to train it, no cape row and no converted emote, so counting it would have
# made the Max cape unbuyable and unwearable - re-checked on every equip - for a skill nobody can
# advance. ~skillcape_stats counts the skills with a cape instead, which is skillcape_cape, and
# adding a hunter row there is the single edit that folds it back in.
CAPED = sorted(set(enum_rows(SCENUM, 'skillcape_cape')))
UNCAPED = sorted(set(STATS.values()) - set(CAPED))
gate = EQUIP.split('[opheld2,max_cape]', 1)[1].split('\n[', 1)[0]
check('~skillcape_count_99s < ~skillcape_stats' in gate,
      'the gate counts 99s against the caped skills rather than naming skills')
check('~equip(last_slot)' in gate, 'and equips when they are all there')
stats_proc = SHOP.split('[proc,skillcape_stats]', 1)[1].split('\n[', 1)[0]
check('skillcape_cape' in stats_proc and '! null' in stats_proc,
      'and that count is read off skillcape_cape, so a capeless stat cannot lock the cape')
count_proc = SHOP.split('[proc,skillcape_count_99s]', 1)[1].split('\n[', 1)[0]
check('skillcape_cape' in count_proc,
      '...and so is the tally of 99s, or the two would disagree and the gate could never be met')
# VALUES AFTER THE CLAIM, NOT INSIDE IT. A mutation's label is the wording of the check it is
# written for, so a number in the middle of a claim changes the wording the moment the number
# changes, and the label stops matching. Three labels in this file were unmatchable for that
# reason; tools/mutate_labels.py is what found them.
check('construction' in CAPED, 'Construction has a cape, as it has since the houses landed')
check(set(CAPED) <= set(STATS.values()),
      'every caped skill is a real stat: %s' % (sorted(set(CAPED) - set(STATS.values())) or 'yes'))
# Hunter was the one stat without a cape from 2026-09-22 until box traps and bird snares gave it
# content on the 23rd; every stat has one again.
check(UNCAPED == [], 'and every stat has one: %s' % (UNCAPED or 'yes'))
price = SHOP.split('[proc,maxcape_price]', 1)[1].split('\n[', 1)[0]
check('^skillcape_price * ~skillcape_stats' in price,
      'the price is the skillcape price times that same count')
check(const('skillcape_price') == 99000, 'a skillcape is 99,000 coins, as in OSRS')
check(const('skillcape_price') * len(CAPED) == 2277000,
      'so the Max cape comes to %s coins - 99,000 a skill, the way OSRS prices its own'
      % format(const('skillcape_price') * len(CAPED), ','))
check(not re.search(r'\b2277000\b', SHOP), 'and that total is nowhere written down as a literal')
mac = SHOP.split('[opnpc1,skillcape_mac]', 1)[1].split('\n[', 1)[0]
check('~maxcape_ready = false' in mac, 'Mac checks the requirement before he offers anything')
check('%maxcape_bought = 1' in mac, 'remembers that you bought one')
check('~maxcape_give' in mac, 'and replaces a lost piece through the same one proc')
give = SHOP.split('[proc,maxcape_give]', 1)[1].split('\n[', 1)[0]
check('inv_freespace(inv) < $missing' in give, 'which asks for room for the missing pieces only')
check(give.count('~obj_gettotal') == 2,
      'and looks in the inventory, the bank and the worn slots for each piece')

# ============================================================================ 4
print('4. every caped skill has all three pieces and an emote - the random pick cannot come up empty')
capes = enum_rows(SCENUM, 'skillcape_cape')
capes_t = enum_rows(SCENUM, 'skillcape_cape_t')
hoods = enum_rows(SCENUM, 'skillcape_hood')
for tbl, name in ((capes_t, 'skillcape_cape_t'), (hoods, 'skillcape_hood')):
    missing = sorted(set(CAPED) - set(tbl))
    check(not missing, '%s covers every caped skill: %s' % (name, missing or 'yes'))
    extra = sorted(set(tbl) - set(CAPED))
    check(not extra, '...and no skill the plain table does not have: %s' % (extra or 'yes'))
eseq = enum_rows(SCENUM, 'skillcape_emote_seq')
espot = enum_rows(SCENUM, 'skillcape_emote_spot')
bad = [k for k in CAPED if capes[k] not in eseq or capes[k] not in espot]
check(not bad, 'and every one of those capes has both an emote and a graphic: %s' % (bad or 'yes'))
bad = [k for k in CAPED if capes_t[k] not in eseq or capes_t[k] not in espot]
check(not bad, 'trimmed included: %s' % (bad or 'yes'))
# The emote button moved with the 474 Emotes tab (c1113a88): controls.if is gone, and the Skillcape
# emote is emotes:skill_cape now. Asked for by name, so a later move fails here as a check rather than
# as an IndexError on the split.
EMOTE_TRIGGER = '[if_button,emotes:skill_cape]'
check(EMOTE_TRIGGER in SHOP, 'the Skillcape emote button is %s' % EMOTE_TRIGGER)
emote = SHOP.split(EMOTE_TRIGGER, 1)[1].split('\n[', 1)[0] if EMOTE_TRIGGER in SHOP else ''
check('$cape = max_cape' in emote, 'the emote button knows about the Max cape')
check('maxvariant_source' in emote,
      '...and about the variants, which keep the emote and almost nothing else')
check('~skillcape_random_cape' in emote,
      'and picks a CAPED skill, not a stat - a capeless stat came up null and refused the emote')
pick = SHOP.split('[proc,skillcape_random_cape]', 1)[1].split('\n[', 1)[0]
check('random(~skillcape_stats)' in pick, '...uniformly over exactly the skills that have one')
check('return(null)' in pick, '...and still answers null rather than running off the end')
check(sorted(int(k) for k in STATS) == list(range(1, len(STATS) + 1)),
      'the stats enum really is 1..%d with no gap, or that walk could miss' % len(STATS))

# ============================================================================ 5
print('5. it has every perk, through the one proc that answers them all')
worn = PERKS.split('[proc,skillcape_worn]', 1)[1].split('\n[', 1)[0]
check('if ($back = max_cape) {\n    return(true);' in worn,
      '~skillcape_worn answers true for the Max cape whatever the skill asked about')
check(before(worn, 'max_cape', 'skillcape_cape'),
      'before it looks the individual capes up, so no table needs a Max cape row')
tele = PERKS.split('[opheld3,max_cape]', 1)[1].split('\n[', 1)[0]
# THE MENU MOVED INTO A LABEL and this check did not follow it. [opheld4,max_cape] is one line
# now - @max_cape_features - so reading the trigger's body found a dispatch and no menu, and the
# check had been red since the worn-options round with the feature working perfectly. Read the
# label, and assert the trigger still reaches it, which is what the old split used to cover.
check('[opheld4,max_cape] @max_cape_features;' in PERKS,
      'the Features op dispatches to one label, so the backpack menu and the worn menu are the '
      'same menu')
feat = PERKS.split('[label,max_cape_features]', 1)[1].split('\n[', 1)[0]
check('~p_choice5_header' in tele and tele.count('@skillcape_teleport(') == 3
      and '@skillcape_teleport_house' in tele,
      'Teleports offers the three guild teleports and the house, all through the single capes\' own labels')
check('~p_choice4_header' in feat and '@skillcape_toggle_rol' in feat
      and '@skillcape_agility_boost' in feat and '@skillcape_spellbook' in feat,
      'Features reaches the ring of life, the run-energy boost and the spellbook swap')
# every destination the menu names is a destination a single cape teleports to
single = set(re.findall(r'@skillcape_teleport\((\S+?)\);', PERKS.split('[opheld3,max_cape]', 1)[0]))
menu = set(re.findall(r'@skillcape_teleport\((\S+?)\);', tele))
check(menu <= single, 'and every coordinate in the menu is one a cape already teleports to: %s'
      % (sorted(menu - single) or 'all three'))
for lbl in ('skillcape_teleport', 'skillcape_teleport_house', 'skillcape_toggle_rol',
            'skillcape_agility_boost', 'skillcape_spellbook'):
    check('[label,%s]' % lbl in PERKS, 'the %s label exists' % lbl)
check(PERKS.count('[label,skillcape_teleport_house]') == 1
      and PERKS.count('~poh_enter(false)') == 1,
      'the house teleport is written once and ends in ~poh_enter, the tablet\'s own call')
house = PERKS.split('[label,skillcape_teleport_house]', 1)[1].split('\n[', 1)[0]
check('~wilderness_level(coord) > 20' in house and '~pre_tele_checks(coord) = false' in house,
      'with the wilderness and pre-teleport guards every other cape teleport has')

# ============================================================================ 6
print('6. the Construction cape is wearable now that the skill is')
check('@skillcape_unavailable("Construction")' not in EQUIP,
      'it is no longer refused for a skill that does not exist')
check(EQUIP.count('@skillcape_require(stat_base(construction), "Construction", last_slot)') == 2,
      'both the plain and the trimmed cape gate on 99 Construction')
check(not re.search(r'^\[opheld2,\w+\] @skillcape_unavailable', EQUIP, re.M),
      'no cape is refused as unavailable any more')
check(EQUIP.count('@skillcape_require(stat_base(hunter), "Hunter", last_slot)') == 2,
      'both Hunter capes gate on 99 Hunter')
EXPERT = read('scripts/skill_hunter/scripts/hunting_expert.rs2')
check('~skillcape_offer(hunter) = true' in EXPERT.split('[opnpc1,hunting_expert]', 1)[1].split('\n[', 1)[0],
      'and the Hunting expert sells it, first thing on Talk-to like every master')
check('[opheld3,construction_cape] @skillcape_teleport_house;' in PERKS
      and '[opheld3,construction_cape_t] @skillcape_teleport_house;' in PERKS,
      'and its own op is the teleport home OSRS gives it')
agent = read('scripts/skill_construction/scripts/poh_portal.rs2')
offer = agent.split('[opnpc1,poh_estate_agent]', 1)[1].split('\n[', 1)[0]
check('~skillcape_offer(construction) = true' in offer, 'the estate agent sells it')
check(before(offer, '~skillcape_offer', '%poh_owned'),
      'from the top of his Talk-to, before his own dialogue')

# ============================================================================ 7
print('7. the Construction cape emote, which was the gap in a block of 24')
SEQ = read('scripts/skillcapes/configs/skillcape_emotes.seq')
SPOT = read('scripts/skillcapes/configs/skillcape_emotes.spotanim')
for name in ('skillcape_construction_emote', 'skillcape_construction'):
    check('[%s]' % name in SEQ, '%s is in the seq file' % name)
check('[skillcape_construction]' in SPOT, 'and the graphic is in the spotanim file')
body = SEQ.split('[skillcape_construction_emote]', 1)[1].split('\n[', 1)[0]
check('// OSRS seq 4953' in body, 'it is OSRS seq 4953 - the one id the 22 imported emotes skipped')
frames = re.findall(r'^frame\d+=(\S+)$', body, re.M)
check(len(frames) == 113, 'all %d frames of it' % len(frames))
check(all(f in ANIMP for f in frames), 'every frame is in anim.pack')
check('replaceheldright=skillcape_prop_crafting_r' in body,
      'and it holds the prop the cache says it holds - obj 9894, the one the Crafting emote also uses')
check('skillcape_prop_crafting_r' in OBJP, 'which is an obj that exists')
sbody = SPOT.split('[skillcape_construction]', 1)[1].split('\n[', 1)[0]
check('// OSRS spotanim 820' in sbody, 'the graphic is OSRS spotanim 820 - the other gap in the block')
check(re.search(r'^model=(\S+)$', sbody, re.M).group(1) in MODELP, 'its model is in model.pack')
check(re.search(r'^anim=(\S+)$', sbody, re.M).group(1) == 'skillcape_construction',
      'and it animates with the seq of the same name')
# the block really is 24 wide with these two filling it
# the player emotes are the odd ids of the block; the even ones beside them are the graphics' own
seqs = sorted(int(m) for m in re.findall(r'// OSRS seq (49\d\d)', SEQ))
player = [n for n in seqs if n % 2]
check(player == list(range(4937, 4982, 2)),
      'the emote seqs are the 23 odd ids from 4937 to 4981 with none missing: %d of them' % len(player))
check(len(seqs) == 2 * len(player), 'each with its graphic\'s animation beside it')

# ============================================================================ 8
print('8. Mac, and where he stands')
check('skillcape_mac' in MACNPC, 'his config is beside the other new masters')
check(MACNPC['skillcape_mac'].get('op1') == ['Talk-to'], 'he talks')
check('op2' not in MACNPC['skillcape_mac'], 'and cannot be attacked, whatever level the cache gave him')
check(MACNPC['skillcape_mac'].get('vislevel') == ['hide'], 'his combat level is hidden, like the other masters')
check('skillcape_mac' in NPCP, 'he has an id in npc.pack (%s)' % NPCP.get('skillcape_mac'))
sec = None; spots = []; solid = set()
for line in read('maps/m44_55.jm2').split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCP['skillcape_mac']: spots.append((lv, x, z))
    if sec == 'LOC' and lv == 0:
        d = data.split()
        if len(d) < 2 or int(d[1]) != 22: solid.add((x, z))
check(len(spots) == 1, 'he is placed exactly once, got %d' % len(spots))
if spots:
    lv, x, z = spots[0]
    ring = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (x + dx, z + dz) in solid]
    check(lv == 0 and not ring, 'his tile and the eight around it are clear: (%d,%d) %s'
          % (2816 + x, 3520 + z, ring or 'all nine'))
    check(2816 + x < 2837, 'and it is west of the guild wall, as near OSRS\'s island as this map gets')

# ============================================================================ 9
print('9. the elder chaos druid is the cache\'s and the wiki\'s monster')
d = ECDNPC['elder_chaos_druid']
WIKI = {'vislevel': '129', 'hitpoints': '150', 'attack': '98', 'strength': '98',
        'defence': '65', 'magic': '110', 'ranged': '1'}
bad = [(k, d.get(k), v) for k, v in WIKI.items() if d.get(k) != [v]]
check(not bad, 'level 129, 150 hitpoints and the four combat stats OSRS gives it: %s' % (bad or 'all seven'))
check(d.get('op2') == ['Attack'], 'it can be attacked')
check(d.get('huntmode') == ['ranged'] and int(d['huntrange'][0]) >= 8,
      'it hunts at range and from %s tiles away - aggressive, as the wiki says' % d.get('huntrange'))
prm = dict(p.split(',', 1) for p in d.get('param', []))
check(prm.get('attackrate') == '4', 'its attack speed is OSRS\'s 4 ticks')
check(prm.get('damagetype') == '^magic_style', 'and it hits with magic')
check(const('elder_chaos_maxhit') == 17, 'its maximum hit is OSRS\'s 17')
check('param=stabdefence' not in read('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc')
      and 'attackbonus' not in str(prm),
      'it carries no attack or defence bonuses, which is what the wiki\'s block says')
ecd = read('scripts/areas/area_wilderness/scripts/elder_chaos_druid.rs2')
check('[ai_applayer2,elder_chaos_druid]' in ecd and '[ai_opplayer2,elder_chaos_druid]' in ecd,
      'it casts whether you are next to it or not - it has no melee attack in OSRS')
check('~npc_default_attack' not in ecd, 'and it never punches')
check('npc_param(attackrate)' in ecd, 'the cast speed is read from the config, not written twice')
check('~npc_spell_success($spell_data, ^elder_chaos_maxhit, $duration)' in ecd,
      'and the damage is the constant, not the borrowed spell\'s own')

# ============================================================================ 10
print('10. the robes drop at OSRS\'s rate, out of a table that adds up')
thresholds = [int(m) for m in re.findall(r'\$random < (\d+)', DROPS)]
check(thresholds == sorted(thresholds), 'the if-chain\'s thresholds only ever go up: %s' % thresholds[:6])
check(const('elder_chaos_table') == 129, 'the table is rolled out of 129, as OSRS rolls it')
check(max(thresholds) == 128 and 'else if' in DROPS.split('$random < 128')[1],
      'and the last slot is the 129th, so nothing falls off the end')
check(const('elder_chaos_slots') == 11, 'the robe table has 11 slots')
rt = DROPS.split('[proc,elder_chaos_robe_table]', 1)[1]
for piece in ('elder_chaos_hood', 'elder_chaos_robe', 'elder_chaos_top'):
    check(rt.count('obj_add(npc_coord, %s, 1,' % piece) == 1, '%s takes exactly one of them' % piece)
slots = [int(m) for m in re.findall(r'\$slot < (\d+)', rt)]
check(slots == [4, 8, 9, 10], 'four monk tops, four bottoms, then the three pieces: %s' % slots)
rate = const('elder_chaos_table') * const('elder_chaos_slots')
check(rate == 1419, 'which makes each piece 1 in %d - OSRS\'s own figure' % rate)
objs = set(re.findall(r'obj_add\(npc_coord, (\w+),', DROPS))
bad = sorted(o for o in objs if o not in OBJP)
check(not bad, 'every item the table drops is a real obj: %s' % (bad or '%d of them' % len(objs)))
check('npc_param(death_drop)' in DROPS, 'and bones always drop, from the npc\'s own param')

# ============================================================================ 11
print('11. the robes themselves, and the one requirement they have')
WIKISTATS = {'elder_chaos_top': (10, 8), 'elder_chaos_robe': (6, 6), 'elder_chaos_hood': (5, 4)}
for name, (atk, dfc) in WIKISTATS.items():
    prm = dict(p.split(',', 1) for p in ELDER[name].get('param', []))
    check(prm.get('magicattack') == str(atk) and prm.get('magicdefence') == str(dfc),
          '%s: +%d magic attack, +%d magic defence' % (name, atk, dfc))
    check(prm.get('levelrequire') == '40', 'and 40 Magic to wear')
    check(name in OBJP, 'with an id in obj.pack (%s)' % OBJP.get(name))
    check('[opheld2,%s] @levelrequire_magic(40, last_slot);' % name in TIER40,
          'gated on Magic alone in tier40.rs2 - no Defence requirement anywhere')
    body = read('scripts/areas/area_wilderness/configs/elder_chaos.obj')
    check('levelrequire_magic_and_defence' not in TIER40.split(name, 1)[1].split('\n')[0],
          'not on the two-stat gate the splitbark pieces use')
check(ELDER['elder_chaos_top'].get('wearpos') == ['torso']
      and ELDER['elder_chaos_robe'].get('wearpos') == ['legs']
      and ELDER['elder_chaos_hood'].get('wearpos') == ['hat'],
      'the three of them fill the torso, legs and hat slots')

# ============================================================================ 12
print('12. the druids stand around the Chaos altar, on ground they fit on')
LOCP = pack('loc.pack')
altar = [n for n, i in LOCP.items() if n == 'chaos_altar']
sec = None; spots = []; solid = set(); altars = []
alt_ids = {i for n, i in LOCP.items() if 'altar' in n}
for line in read('maps/m50_56.jm2').split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCP['elder_chaos_druid']: spots.append((lv, x, z))
    if sec == 'LOC' and lv == 0:
        d = data.split()
        if int(d[0]) in alt_ids and (x, z) not in altars: altars.append((x, z))
        if len(d) < 2 or int(d[1]) != 22: solid.add((x, z))
check(len(spots) == 8, 'and the spawn count is what it was: %d' % len(spots))
check(len(altars) == 1, 'and one altar on the square (%s)'
      % ', '.join('%d,%d' % (3200 + x, 3584 + z) for x, z in altars))
if altars and spots:
    ax, az = altars[0]
    far = [(3200 + x, 3584 + z) for lv, x, z in spots if max(abs(x - ax), abs(z - az)) > 5]
    check(not far, 'every one is within five tiles of it: %s' % (far or 'all eight'))
    on = [(3200 + x, 3584 + z) for lv, x, z in spots if (x, z) in solid]
    check(not on, 'and none is standing inside a tree or a rock: %s' % (on or 'all eight clear'))
    check(all(lv == 0 for lv, x, z in spots), 'all on ground level')
    wild = [3584 + z for lv, x, z in spots]
    check(min(wild) >= 3520, 'all of them in the Wilderness (z %d-%d)' % (min(wild), max(wild)))
    lvls = sorted({(z - 3520) // 8 + 1 for z in wild})
    check(max(lvls) <= 20, 'in wilderness levels %s - inside the 20 that teleports still work in'
          % '-'.join(str(l) for l in (lvls[0], lvls[-1])))

print('13. the Max cape variants: a cape and a hood each, and none of them is a Max cape')

import json as _json
import subprocess as _sp

VSPEC = _json.loads(read('tools/maxcapevariantspec.json'))
VOBJ = blocks(read('scripts/skillcapes/configs/max_cape_variants.obj'))
VENUM = read('scripts/skillcapes/configs/max_cape_variants.enum')
GENUM = read('scripts/areas/area_mage_arena/configs/god_cape.enum')
VRS2 = read('scripts/skillcapes/scripts/max_cape_variants.rs2')
PERKS = read('scripts/skillcapes/scripts/skillcape_perks.rs2')
GODGEAR = read('scripts/areas/area_mage_arena/scripts/god_gear.rs2')
MACONST = read('scripts/areas/area_mage_arena/configs/mage_arena.constant')
KEYS = [v['key'] for v in VSPEC['variants']]
NAMES = ['%s_max_%s' % (k, part) for k in KEYS for part in ('cape', 'hood')]

# ---- they all exist, and only they. COUNTED FROM THE SPEC, not written down: a ninth variant
# arrived (the Accumulator max cape, once Animal Magnetism gave the build an Ava's accumulator)
# and every hard-coded eight and sixteen in this group went red at once while nothing was wrong.
check(sorted(VOBJ) == sorted(NAMES),
      'the generated config holds exactly the %d pieces the spec names, a cape and a hood for '
      'each of the %d variants: %s'
      % (len(NAMES), len(KEYS), sorted(set(VOBJ) ^ set(NAMES)) or 'exactly those'))
check(all(n in OBJP for n in NAMES),
      'every one has an id in pack/obj.pack, so the packer can see it: %s'
      % ([n for n in NAMES if n not in OBJP][:3] or 'all %d' % len(NAMES)))
_missing_models = []
for n, f in VOBJ.items():
    for k in ('model', 'manwear', 'womanwear', 'manhead', 'womanhead'):
        for v in f.get(k, []):
            mdl = v.split(',')[0]
            if mdl not in MODELP or not os.path.exists(os.path.join(C, 'models/obj', mdl + '.ob2')):
                _missing_models.append('%s/%s=%s' % (n, k, mdl))
check(not _missing_models,
      'and every model those sixteen name is in model.pack AND on disk: %s'
      % (_missing_models[:3] or 'all of them'))

# ---- A VARIANT'S BONUSES ARE ITS SOURCE CAPE'S, read off the SOURCE rather than written twice.
# This is the whole definition of a variant, so it is checked against the other config and not
# against the spec: the spec comparison is a separate check below, and the two catch different
# mistakes - this one catches a variant drifting from its cape, that one catches both drifting
# together away from OSRS.
ALLOBJ = {}
for _rel in ('scripts/_unpack/377/all.obj',
             'scripts/minigames/game_fightcave/configs/fightcave.obj',
             'scripts/areas/area_mage_arena/configs/mage_arena_2.obj',
             'scripts/quests/quest_animmag/configs/animmag.obj'):
    ALLOBJ.update(blocks(read(_rel)))
def _params(f):
    out = {}
    for v in f.get('param', []):
        k, _, n = v.partition(',')
        if n.lstrip('-').isdigit():
            out[k] = int(n)
    return out
_bad = []
for v in VSPEC['variants']:
    src = ALLOBJ.get(v['source_cape'])
    var = VOBJ.get('%s_max_cape' % v['key'])
    if src is None or var is None:
        _bad.append('%s: cannot find both records' % v['key'])
        continue
    want = _params(src)
    got = _params(var)
    if got != want:
        _bad.append('%s: variant %s, source %s' % (v['key'], got, want))
check(not _bad,
      "each variant cape's combat bonuses are exactly its SOURCE cape's, compared record to "
      'record: %s' % (_bad[:2] or 'all %d match their source' % len(KEYS)))
_sbad = []
for v in VSPEC['variants']:
    got = _params(VOBJ.get('%s_max_cape' % v['key'], {}))
    if got != {k: int(x) for k, x in v['bonuses'].items()}:
        _sbad.append('%s: config %s, spec %s' % (v['key'], got, v['bonuses']))
check(not _sbad,
      "...and the same numbers the spec took out of OSRS's item table, so source and variant "
      'cannot have drifted together: %s' % (_sbad[:2] or 'all %d' % len(KEYS)))
check(not [n for n, f in VOBJ.items() if n.endswith('_max_hood') and f.get('param')],
      'no hood carries a combat bonus, which is what every skillcape hood in this build does')

# ---- NONE OF THEM IS A MAX CAPE. This is the perk-stripping, from the item side.
_ops = [(n, k) for n, f in VOBJ.items() for k in f if k in ('iop3', 'iop4', 'iop5')]
check(not _ops,
      'not one of the sixteen carries iop3, iop4 or iop5 - no Teleports and no Features - which '
      "is OSRS's own list for all eight of them where the plain cape has four ops: %s"
      % (_ops[:3] or 'Wear and nothing else'))
check(all(f.get('iop2') == ['Wear'] for f in VOBJ.values()),
      '...and every one does carry Wear, so they can be put on at all')
check(all(f.get('tradeable') == ['no'] for f in VOBJ.values()),
      'and none of them is tradeable, like the Max cape they are made from')

# ---- the perk allowlist
_worn = PERKS.split('[proc,skillcape_worn]', 1)[1].split('\n[', 1)[0] if \
    '[proc,skillcape_worn]' in PERKS else ''
check('enum(obj, namedobj, maxvariant_source, $back) ! null' in nocomment(_worn),
      '~skillcape_worn asks maxvariant_source whether the worn cape is a variant, rather than '
      'carrying a list of the eight that would need editing when a ninth arrives')
check(before(nocomment(_worn), '$back = max_cape', 'maxvariant_source'),
      '...and the plain Max cape is answered BEFORE that branch, so it keeps every perk while the '
      'variants keep four - the order is what decides it')
# EXACTLY these four, not "these four are among them". The first version searched for the four
# names and passed while a mutation added agility beside them - a check that cannot see an extra
# is not checking a list, it is checking a subset.
_allow = nocomment(_worn).split('switch_stat', 1)[1].split('}', 1)[0] \
    if 'switch_stat' in nocomment(_worn) else ''
_cases = re.findall(r'^\s*case ([^:]+):', _allow, re.M)
_skills = sorted(x.strip() for c in _cases if 'default' not in c for x in c.split(','))
check(_skills == ['cooking', 'crafting', 'firemaking', 'runecraft'],
      'the four skills a variant still answers true for are exactly Cooking, Crafting, Runecraft '
      "and Firemaking - the Cooks' Guild, the Crafting Guild, essence pouches and warm clothing: "
      '%s' % (_skills or 'none found'))
check('case default : return(false)' in _allow.replace('  ', ' '),
      '...and every other skill is refused by a default case, so a perk added to this file later '
      'is inherited by the Max cape and NOT by a variant, which is the right way round')
_emote = read('scripts/skillcapes/scripts/skillcape_shop.rs2')
check('$cape = max_cape | enum(obj, namedobj, maxvariant_source, $cape) ! null' in _emote,
      'the skillcape emote treats a variant like the Max cape, which is the one other thing OSRS '
      'lets a variant keep - and it is the same line, not a second copy of the random pick')

# ---- THE GOD TABLE: twelve capes, not six
_gblock = GENUM.split('[god_cape_god]', 1)[1].split('\n[', 1)[0] if '[god_cape_god]' in GENUM else ''
_gvals = dict(re.findall(r'^val=(\w+),\^god_(\w+)$', _gblock, re.M))
_wantgod = {}
for _g in ('saradomin', 'guthix', 'zamorak'):
    _wantgod['%s_cape' % _g] = _g
    _wantgod['imbued_%s_cape' % _g] = _g
    _wantgod['%s_max_cape' % _g] = _g
    _wantgod['imbued_%s_max_cape' % _g] = _g
check(_gvals == _wantgod,
      'god_cape_god maps TWELVE capes to their god - three plain, three imbued and the six Max '
      'cape variants - and nothing else: %s'
      % (sorted(set(_gvals.items()) ^ set(_wantgod.items()))[:3] or 'exactly the twelve'))
_sblock = GENUM.split('[god_staff_god]', 1)[1].split('\n[', 1)[0] if '[god_staff_god]' in GENUM else ''
_svals = dict(re.findall(r'^val=(\w+),\^god_(\w+)$', _sblock, re.M))
check(_svals == {'saradomin_staff': 'saradomin', 'guthix_staff': 'guthix',
                 'zamorak_staff': 'zamorak'},
      'and god_staff_god maps the three staves, which is the other half of every god test')
check(all(('^god_%s = ' % g) in MACONST for g in ('none', 'saradomin', 'guthix', 'zamorak')),
      'all four god ids are defined in mage_arena.constant, including ^god_none, which is what a '
      'cape belonging to no god answers')
_ids = dict(re.findall(r'\^god_(\w+) = (\d+)', MACONST))
check(_ids.get('none') == '0' and len(set(_ids.values())) == len(_ids),
      '...with ^god_none at zero and no two gods sharing a number: %s' % _ids)
check(all(n in OBJP for n in _wantgod),
      'and every cape the table names is a real obj: %s'
      % ([n for n in _wantgod if n not in OBJP][:3] or 'all twelve'))

# ---- THE NINE SITES GO THROUGH ONE PROC. The strong form: the old shape appears nowhere.
_sites = []
for _root, _dirs, _files in os.walk(os.path.join(C, 'scripts')):
    for _fn in _files:
        if not _fn.endswith('.rs2'):
            continue
        _rel = os.path.relpath(os.path.join(_root, _fn), C)
        _t = '\n'.join(l.split('//')[0] for l in read(_rel).split('\n'))
        if re.search(r'inv_total\(worn, (saradomin|guthix|zamorak)_cape\)', _t):
            _sites.append(_rel)
check(len(_sites) == 0,
      'no script anywhere still tests for a god cape by name - all nine sites that did go through '
      '~god_cape_and_staff, so a cape added to the table is accepted by all of them at once: %s'
      % (_sites[:3] or 'none left'))
# COUNT THE CALLS, not the files. Nine sites were rewired: three god spells x two copies, plus
# three battle mages in one file. A per-file check passed while a mutation deleted one of the
# three calls inside battle_mage.rs2, because the file still contained the other two.
_users = {}
for _root, _dirs, _files in os.walk(os.path.join(C, 'scripts')):
    for _fn in _files:
        if _fn.endswith('.rs2'):
            _rel = os.path.relpath(os.path.join(_root, _fn), C)
            _n = nocomment(read(_rel)).count('~god_cape_and_staff(')
            if _n:
                # KEYED BY PATH, NOT BASENAME. The player and pvp copies of each god spell have
                # the SAME file name in different folders, so a basename key collapsed six files
                # into three and the count came out half.
                _users[_rel.replace('\\', '/')] = _n
check(sum(_users.values()) == 9 and len(_users) == 7 and _users.get(
        'scripts/areas/area_mage_arena/scripts/battle_mage.rs2') == 3,
      'and all nine rewired sites call it - the three god spells once each in the player copy and '
      'once each in the pvp one, and the battle mages three times in one file: %d calls across '
      '%d files' % (sum(_users.values()), len(_users)))
check('return(~god_worn_staff = $god)' not in nocomment(GODGEAR)
      and '[proc,god_cape_and_staff](int $god)(boolean)' in GODGEAR,
      'the god test is a proc that writes both comparisons out, because `=` is a comparison '
      'inside an if and not an expression - the server compiler rejects return(a = b) where '
      'rs2check does not')
check('check_conflicting_god_cape' not in GODGEAR
      and 'check_conflicting_god_staff' not in GODGEAR,
      'the two pair-at-a-time conflict procs are gone: they named capes two at a time, which '
      'does not survive a fourth cape per god')
_gcape_triggers = re.findall(r'^\[opheld2,(\w+)\] @god_cape_equip\(\^god_(\w+)\);$',
                             GODGEAR + '\n' + VRS2, re.M)
check(sorted(_gcape_triggers) == sorted((n, g) for n, g in _wantgod.items()),
      'and all twelve god capes have an equip trigger that refuses the staff of another god - the '
      'six new ones in max_cape_variants.rs2 calling the same label: %d of 12'
      % len(_gcape_triggers))
_gstaff = re.findall(r'^\[opheld2,(\w+)\] @god_staff_equip\(\^god_(\w+)\);$',
                     nocomment(GODGEAR), re.M)
check(sorted(_gstaff) == [('guthix_staff', 'guthix'), ('saradomin_staff', 'saradomin'),
                          ('zamorak_staff', 'zamorak')],
      'and all three god staves have the mirror trigger, refusing the cape of another god - the '
      'other half of the conflict, and nothing was checking it until a mutation deleted one: %s'
      % sorted(_gstaff))
check(len(re.findall(r'^\[opheld2,\w+_max_cape\] @god_cape_equip', VRS2, re.M)) == 6,
      '...and exactly the six god variants get one, not the fire and infernal ones, which have '
      'no god to conflict with and fall through to [opheld2,_]')

# ---- THE COMBINE AND THE KNIFE are exact inverses
_comb = VRS2.split('[label,maxvariant_combine]', 1)[1].split('\n[', 1)[0] if \
    '[label,maxvariant_combine]' in VRS2 else ''
_split = VRS2.split('[label,maxvariant_split]', 1)[1].split('\n[', 1)[0] if \
    '[label,maxvariant_split]' in VRS2 else ''
check(all(x in _comb for x in ('inv_del(inv, max_cape, 1)', 'inv_del(inv, max_hood, 1)',
                               'inv_del(inv, $source, 1)')),
      'combining consumes all three items - the cape, the hood and the source cape - which is '
      "OSRS's own requirement and the reason the hood has to be with you")
check('inv_add(inv, $variant, 1)' in _comb and 'inv_add(inv, $hood, 1)' in _comb,
      '...and hands back the variant and its own hood, because the Max hood became the new one')
check(all(x in _split for x in ('inv_add(inv, max_cape, 1)', 'inv_add(inv, max_hood, 1)',
                                'inv_add(inv, $source, 1)')),
      'a knife gives back exactly those three, so the pair of operations is lossless')
check('last_useitem ! knife' in _split,
      '...and only a knife does it - anything else on a variant falls through to the default '
      'message')
_knives = re.findall(r'^\[opheldu,(\w+)_max_cape\] @maxvariant_split;$', VRS2, re.M)
check(sorted(_knives) == sorted(KEYS),
      'every variant answers the knife, declared on the CAPES rather than on the knife '
      'because [opheldu,knife] is already taken by the fruit-cutting handler: %d of %d'
      % (len(_knives), len(KEYS)))
check(nocomment(VRS2).count('[opheldu,max_cape]') == 1,
      'and the combine is ONE trigger on the Max cape rather than eight, because OpHeldUHandler '
      "tries the target item's trigger first and the used item's second")
check('inv_freespace(inv) < 1' in _comb and 'inv_freespace(inv) < 1' in _split,
      'both directions check for room first, since both end up holding more items than they '
      'started with at the moment the swap happens')

# ---- THE SOURCE CAPES ARE UNTOUCHED, which is the point after a wrong finding.
# I claimed both Tzhaar capes were missing param=rangeattack,1 and "fixed" them; both already had
# it, and the grep that said otherwise could not match the word. fightcave_battery caught the
# duplicate. The spec records the whole thing under a_finding_of_mine_that_was_wrong. This check
# is what stops it coming back: a variant is derived from its source, so the source must not have
# been edited to make the derivation come out.
_srcbad = []
for v in VSPEC['variants']:
    src = ALLOBJ.get(v['source_cape'])
    if src is None:
        _srcbad.append('%s missing' % v['source_cape'])
        continue
    if len(src.get('param', [])) != len(set(src.get('param', []))):
        _srcbad.append('%s has a duplicate param line' % v['source_cape'])
check(not _srcbad,
      'no source cape carries a duplicated param line - which is what "fixing" a bonus that was '
      'already there looks like in a config: %s'
      % (_srcbad[:3] or 'all %d clean' % len(KEYS)))
check('a_finding_of_mine_that_was_wrong' in VSPEC,
      '...and the wrong finding is written down in the spec rather than quietly dropped, with the '
      'regex that caused it')

# ---- THE ACCUMULATOR MAX CAPE IS AN AVA'S ACCUMULATOR, which is the only reason to own one.
# Its bonuses are already checked against avas_accumulator by the derived-from-source check above,
# because animmag.obj is one of the files ALLOBJ reads. What is checked here is the BEHAVIOUR: the
# ammunition saving and the metal attraction, which live in the quest's scripts and not in a config.
AVAS = read('scripts/quests/quest_animmag/scripts/avas_device.rs2')
def _proc(txt, head):
    return txt.split(head, 1)[1].split('\n[', 1)[0] if head in txt else ''
_dev = nocomment(_proc(AVAS, '[proc,avas_device]'))
_saved = nocomment(_proc(AVAS, '[proc,ranged_ammo_saved]'))
_pull = nocomment(_proc(AVAS, '[proc,avas_attract]'))
check('enum(obj, namedobj, maxvariant_source, $cape)' in _dev,
      "~avas_device turns a worn Max cape variant back into the device it was fused with in one "
      'enum lookup, so no script in the build names accumulator_max_cape at all')
# NAMING A DEVICE IS NOT ANSWERING WITH IT. The first version of this check searched _dev for the
# two names and passed while a mutation deleted the attractor's whole branch - the names were still
# there in the enum comparison two lines further down. The RETURN is what a caller sees.
check(all('return(%s);' % d in _dev for d in ('avas_accumulator', 'avas_attractor')),
      '...and it still returns each of the two plain devices worn on its own, which is the '
      'ordinary case')
check('~avas_device' in _saved and '~avas_device' in _pull,
      'both halves of what a device does - the ammo that comes back and the metal that is pulled '
      'in - ask that one proc')
check('inv_getobj(worn, ^wearpos_back)' not in _saved
      and 'inv_getobj(worn, ^wearpos_back)' not in _pull,
      '...and neither reads the cape slot itself any more, so the saving and the attraction '
      'cannot end up disagreeing about what is worn')
check('val=accumulator_max_cape,avas_accumulator' in VENUM
      and 'val=avas_accumulator,accumulator_max_cape' in VENUM,
      'the enum says both directions - an accumulator makes the cape, and the cape came from an '
      'accumulator - which is what makes the lookup above find it')
check('accumulator_max_cape' not in GENUM,
      'and the accumulator variant is in NO god table: it has no god, and a cape that belongs to '
      'none has to answer ^god_none like any other')
_ranged = [k for k in KEYS if 'accumulator' in k or 'attractor' in k]
check(_ranged == ['accumulator'],
      "one device variant, not two: OSRS's assembler max capes need Ava's assembler, which is "
      'post-2006 and not in this build, so they stay in the spec under not_buildable_here: %s'
      % _ranged)
check('assembler_max_cape' in VSPEC['not_buildable_here']
      and 'masori_assembler_max_cape' in VSPEC['not_buildable_here'],
      '...and both are still listed there by name, so leaving them out was a decision and not an '
      'oversight')

# ---- the generators reproduce what is checked in
_gen = _sp.run([sys.executable, os.path.join(C, 'tools/genmaxvariants.py'), '--check'],
               capture_output=True, text=True, cwd=C)
check(_gen.returncode == 0,
      'tools/genmaxvariants.py --check: the four generated files and both pack files are already '
      'what it writes, so nothing here was hand-edited%s'
      % ('' if _gen.returncode == 0 else ': ' + _gen.stdout.strip()[:220]))
_ren = _sp.run([sys.executable, os.path.join(C, 'tools/maxvariantrender.py')],
               capture_output=True, text=True, cwd=C)
check(_ren.returncode == 0,
      'and tools/maxvariantrender.py: every recolour source still matches faces on the model it '
      'is applied to, apart from the two OSRS itself leaves inert on a hood - a source that '
      'matches nothing is a piece that renders as a plain Max cape%s'
      % ('' if _ren.returncode == 0 else ': ' + '\n'.join(
          l for l in _ren.stdout.split('\n') if 'FAIL' in l)[:300]))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
