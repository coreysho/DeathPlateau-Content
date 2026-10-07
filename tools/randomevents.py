"""Which of 2006scape's random events this build has, and what each missing one would cost.

The list is the one on https://2006scape.fandom.com/wiki/Random_Event (read 2026-10-06), typed out
below exactly as that page groups them. For each, this says whether the content implements it and -
when it does not - whether the 377 cache has the npc it needs, because that is what separates "write
a script" from "import a character from a later cache first".

WHAT COUNTS AS IMPLEMENTED is a script file under scripts/macro events, or a named proc the rest of
the tree calls. Nothing here guesses from an npc existing: the Evil Chicken has a record in the cache
and no random event behind it, which is precisely the kind of thing this is for.

    python3 tools/randomevents.py            # the table
    python3 tools/randomevents.py --missing  # only what is not in yet
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EVENTS_DIR = os.path.join(ROOT, 'scripts', 'macro events')
# THE CAST IS NOT IN THE 377 CACHE and looking for it there is how this tool first reported that
# seventeen events needed a character imported from a later cache. They do not: somebody built the
# whole lot out of 377 parts - idk_* heads and jaws, obj_*_manwear pieces, recolours - and they are
# sitting in "macro events"/configs/antimacro.npc with their own animations, waiting for a script.
ANTIMACRO_NPC = os.path.join(ROOT, 'scripts', 'macro events', 'configs', 'antimacro.npc')
ALL_NPC = os.path.join(ROOT, 'scripts', '_unpack', '377', 'all.npc')

# (group, wiki name, the proc or script that would implement it, the cache npc it needs)
# A cache npc of None means the event needs no character of its own.
EVENTS = [
    ('Woodcutting', 'Broken axe', 'macro_event_lost_axe', None),
    ('Woodcutting', 'Tree Ent', 'macro_event_ent', None),
    # THE WIKI'S "Tree spirit" IS THIS BUILD'S "dryad" EVENT. npc_dryhad is the model; all six
    # macro_dryhadguardian_* records are named "Tree spirit", which is what a player sees.
    ('Woodcutting', 'Tree spirit', 'macro_event_dryad', None),
    # Not a macro event at all here - nests fall from the tree you are cutting, in
    # skill_woodcutting/scripts/bird_nest.rs2, which is where 2006 put them too.
    ('Woodcutting', "Bird's nest", 'scripts/skill_woodcutting/scripts/bird_nest.rs2', None),
    ('Mining', 'Pickaxe breaking', 'macro_event_lost_pickaxe', None),
    ('Mining', 'Smoking rocks', 'macro_event_gas', None),
    ('Mining', 'Rock Golem', 'macro_event_rock_golem', None),
    ('Farming', 'Spade breaking', 'macro_event_lost_spade', None),
    ('Fishing', 'Big fish', 'macro_event_big_fish', None),
    ('Fishing', 'River troll', 'macro_event_river_troll', None),
    ('Fishing', 'Whirlpools', 'macro_event_whirlpool', None),
    # THE JAILER IS THE PILLORY. 2006scape lists it twice - here under Thieving, with the
    # description "You are teleported to a cell in Seers' village, Varrock or Yanille where you
    # need to solve a Puzzle to escape", and again under Npc's as "Pillory" with no description at
    # all. Those are one event: runescape.wiki/w/Pillory puts the cages in exactly those three
    # towns, has you escape by picking a symbol lock, and its update history says that until 25
    # February 2009 being caught was something that only happened to "members using Thieving" -
    # which is why 2006scape files it under Thieving. The RuneScape wiki's complete list of 43
    # historical randoms has no Jailer in it at all.
    ('Thieving', 'Jailer', 'macro_event_pillory', 'macro_pillory_guard'),
    ('Thieving', 'Watchman', 'macro_event_watchman', None),
    ('Monster spawns', 'Evil Chicken', 'macro_event_evil_chicken', 'chickenquest_evil_chicken'),
    ('Monster spawns', 'Swarm', 'macro_event_swarm', None),
    ('Monster spawns', 'Poison cloud', 'macro_event_poisonous_gas', None),
    ('Monster spawns', 'Zombie', 'macro_event_zombie', None),
    ('Monster spawns', 'Shade', 'macro_event_shade', None),
    ("Npc's", "Cap'n Hand", 'macro_event_capn_hand', 'macro_pirate'),
    ("Npc's", 'Jekyll and Hyde', 'macro_event_jekyll', 'macro_jekyll'),
    ("Npc's", 'Evil Bob', 'macro_event_evil_bob', 'macro_evil_bob_outside'),
    ("Npc's", "Cap'n Arnav", 'macro_event_arnav', 'macro_combilock_pirate'),
    ("Npc's", 'The certers', 'macro_event_certer', 'macro_niles'),
    ("Npc's", 'Dr. Ford', 'macro_event_dr_ford', 'macro_doctor'),
    ("Npc's", 'Candlelight', 'macro_event_candlelight', None),
    ("Npc's", 'Drill Demon', 'macro_event_drilldemon', 'macro_drilldemon'),
    ("Npc's", 'Drunken dwarf', 'macro_event_drunken_dwarf', None),
    ("Npc's", 'Freaky forester', 'macro_event_forester', 'macro_forester_m'),
    ("Npc's", 'Genie', 'macro_event_genie', None),
    ("Npc's", 'Gravedigger', 'macro_event_gravedigger', 'macro_gravedigger'),
    ("Npc's", 'Kiss the frog', 'macro_event_frog', 'macro_frog_prince'),
    ("Npc's", 'Mime', 'macro_event_mime', 'macro_mime'),
    ("Npc's", 'Mysterious old man', 'macro_event_mysterious_old_man', None),
    ("Npc's", 'Pillory', 'macro_event_pillory', 'macro_pillory_guard'),
    ("Npc's", 'Prison pete', 'macro_event_prisonpete', 'prisonpete_pete'),
    ("Npc's", 'Quiz master', 'macro_event_quiz', 'macro_magneson'),
    ("Npc's", 'Rick Turpentine', 'macro_event_rick_turpentine', 'macro_highwayman'),
    ("Npc's", 'Sandwich Lady', 'macro_event_sandwich_lady', 'macro_sandwich_lady_npc'),
    ('Other', 'Strange box', 'macro_event_strange_box', None),
    ('Other', 'Strange plant', 'macro_event_triffid', None),
]


def implemented():
    """The set of event names the content has a script or a proc for.

    Mostly scripts/macro events, but not only: an entry naming a path is looked for at that path,
    because two of 2006's randoms are not macro events in this tree - a bird's nest falls out of the
    tree you are cutting, the way it did in 2006.
    """
    names = set()
    for base, _dirs, files in os.walk(EVENTS_DIR):
        for f in files:
            if f.endswith('.rs2'):
                names.add(f[:-4])
                src = open(os.path.join(base, f), encoding='utf8', errors='replace').read()
                for m in re.finditer(r'\[(?:proc|label|queue),(macro_\w+)', src):
                    names.add(m.group(1))
    return names


def cache_npcs():
    """Every npc debugname this build declares, cache and random-event cast alike."""
    out = set()
    for path in (ANTIMACRO_NPC, ALL_NPC):
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if line.startswith('[') and line.endswith(']'):
                    out.add(line[1:-1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--missing', action='store_true')
    args = ap.parse_args()

    have = implemented()
    npcs = cache_npcs()

    done, needs_script, needs_npc = [], [], []
    for group, name, script, npc in EVENTS:
        # A script counts when its own file exists, or when any proc/label in the tree is named for
        # it - the general events live together in one file rather than one file each.
        ok = (script.endswith('.rs2') and os.path.exists(os.path.join(ROOT, script)))             or script in have or any(n.startswith(script) for n in have)
        if ok:
            done.append((group, name, script))
        elif npc is None or npc in npcs:
            needs_script.append((group, name, script, npc))
        else:
            needs_npc.append((group, name, script, npc))

    total = len(EVENTS)
    if not args.missing:
        print('%d of 2006scape\'s %d random events are in:' % (len(done), total))
        for group, name, script in done:
            print('    %-16s %-24s %s' % (group, name, script))
        print('')

    print('%d more need only a script - the npc is in the 377 cache, or none is needed:'
          % len(needs_script))
    for group, name, script, npc in needs_script:
        print('    %-16s %-24s %s' % (group, name, npc or 'no npc of its own'))
    print('')
    print('%d need a character this cache does not have, so a model import comes first:'
          % len(needs_npc))
    for group, name, script, npc in needs_npc:
        print('    %-16s %s' % (group, name))
    return 0


if __name__ == '__main__':
    sys.exit(main())
