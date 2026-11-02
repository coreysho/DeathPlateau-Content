"""Battery for Recipe for Disaster's sub-quest rewards.

WHY THIS FILE EXISTS. Until 1 November the quest paid one quest point per sub-quest and nothing
else: not a single stat_advance in ten sub-quests, and no reward scroll, where every other quest
in the build ends on ~send_quest_complete. It was reported on the Mountain Dwarf and was true of
all nine. Nothing asserted any of it, so nothing noticed.

The numbers below are Old School's, from the wiki's per-sub-quest reward lists cross-checked
against its Quest experience rewards table. They are written here as data rather than read out of
the script, so a change to the script that quietly alters a payout fails this instead of shipping.

ONE ROW IS CONTESTED and it is a filing error rather than a number: the wiki's Full guide lists
Skrach's four 1,500s under Evil Dave. The sub-quest pages and the experience table agree with each
other against it, and Dave's own page gives 7,000 Cooking and nothing else.

    python3 tools/rfd_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

# name -> the experience that sub-quest hands over, by skill
REWARDS = {
    'cook':    {},
    'dwarf':   {'cooking': 1000, 'slayer': 1000},
    'goblins': {'cooking': 1000, 'farming': 1000, 'crafting': 1000},
    'pirate':  {'cooking': 1000, 'crafting': 1000, 'fishing': 1000, 'smithing': 1000},
    'guide':   {'cooking': 2500, 'magic': 2500},
    'dave':    {'cooking': 7000},
    'ogre':    {'woodcutting': 1500, 'cooking': 1500, 'crafting': 1500, 'ranged': 1500},
    'varze':   {'cooking': 4000, 'hitpoints': 4000},
    'monkey':  {'cooking': 10000, 'agility': 10000},
}

QUEST = read('scripts/quests/quest_100/scripts/quest_100.rs2')
REWARD_PROC = QUEST.split('[proc,hundred_subquest_reward]', 1)[-1].split('[proc,hundred_subquest_scroll]', 1)[0]

# ---- the payouts
shipped = {}
cur = None
for line in REWARD_PROC.split('\n'):
    m = re.match(r'\s*case \^hundred_bit_(\w+) :', line)
    if m:
        cur = m.group(1); shipped[cur] = {}
        continue
    m = re.match(r'\s*stat_advance\((\w+), (\d+)\);', line)
    if m and cur:
        shipped[cur][m.group(1)] = int(m.group(2))

check(set(shipped) == set(REWARDS),
      'every sub-quest but the finale has a reward case: %s'
      % (sorted(set(REWARDS) ^ set(shipped)) or '%d of %d' % (len(shipped), len(REWARDS))))
for name in sorted(REWARDS):
    check(shipped.get(name) == REWARDS[name],
          '  %-8s pays %s' % (name, REWARDS[name] or 'a quest point and nothing else')
          + ('' if shipped.get(name) == REWARDS[name] else ' - ships %s' % shipped.get(name)))

# ---- THE FINALE MUST NOT BE IN THERE. hundred_culinaromancer.rs2 sets that bit and then opens
# its own ~send_quest_complete; a case here would put a second scroll on top of it.
check('^hundred_bit_culinaromancer' not in REWARD_PROC,
      'the Culinaromancer has no case - it opens its own quest-complete scroll and a case here '
      'would announce the finale twice')

# ---- every sub-quest actually reaches the award, and the award reaches the reward
SCRIPTS = os.path.join(C, 'scripts/quests/quest_100/scripts')
awarded = set()
for f in sorted(os.listdir(SCRIPTS)):
    if not f.endswith('.rs2'): continue
    for m in re.findall(r'~hundred_award_subquest\(\^hundred_bit_(\w+)\)', read('scripts/quests/quest_100/scripts/' + f)):
        awarded.add(m)
check(awarded == set(REWARDS) | {'culinaromancer'},
      'all ten sub-quests call ~hundred_award_subquest: %s'
      % (sorted((set(REWARDS) | {'culinaromancer'}) ^ awarded) or '10 of 10'))
check('~hundred_subquest_reward($bit);' in QUEST,
      '...and ~hundred_award_subquest pays the reward out, rather than only setting the bit - '
      'which is what it did before')

# ---- the scroll must not mark the whole quest done
SCROLL = QUEST.split('[proc,hundred_subquest_scroll]', 1)[-1]
check('if_setcolour' not in SCROLL and 'send_quest_complete' not in SCROLL,
      "the sub-quest scroll does not recolour the quest list or call ~send_quest_complete: "
      'Recipe for Disaster is ONE list entry with ten steps, and either would paint it green '
      'on the first sub-quest')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
