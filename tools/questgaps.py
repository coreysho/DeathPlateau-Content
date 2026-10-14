"""Which quests were invented around the cache, instead of built from it?

Ghosts Ahoy and Monkey Madness both gave themselves away the same way: the 377 cache shipped the
real quest's pieces, named after what they do, and nothing in the content referenced them.

    ahoy_ghost_protestor   placed at 3658,3504, 0 scripts   - Gravingas, who hands out the petition
    ahoy_ghost_villager    twelve placements, 0 scripts     - the ghosts who sign it
    ahoy_subquest_bow      four bits, never read            - Robin's game of Rune-Draw
    ahoy_killed_lobster    one bit, never read              - the giant lobster in the chest
    mm_denture_crate       0 scripts                        - where the dentures actually are
    mm_crate_over_hole     0 scripts                        - the crate you fall through

A quest built FROM the cache uses what the cache gave it. A quest invented ON TOP of the cache leaves
those pieces lying there, and the NAMES of what is left over describe the steps that are missing.
This finds the leftovers per quest, so the next rebuild is chosen by evidence rather than by which
quest somebody happens to remember.

    python tools/questgaps.py                  every quest, worst first
    python tools/questgaps.py ahoy mm          just those
    python tools/questgaps.py -v ahoy          and list every leftover symbol

WHAT IT CANNOT TELL YOU: whether a leftover matters. Some are scenery, some belong to another quest
that shares a prefix, and some are later content the cache ships early - Monkey Madness II's seven
greegrees are configured and deliberately unobtainable. Read the names; do not total the columns.

The varbit column is the sharpest of the four. A cache that defines four bits for one quest's card
game was not speculating about a card game. Locs are the bluntest: most of a quest's locs are
scenery and were never going to be scripted, which is why they are weighted near zero in the ranking.
"""
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)
SCRIPTS = os.path.join(CONTENT, 'scripts')
UNPACK = os.path.join(SCRIPTS, '_unpack', '377')
QUESTS = os.path.join(SCRIPTS, 'quests')

KINDS = ['npc', 'obj', 'loc', 'varbit']
CACHE_FILES = {'npc': 'all.npc', 'obj': 'all.obj', 'loc': 'all.loc', 'varbit': 'all.varbit'}

# a varbit defined for a quest step is near-proof; a loc is usually a bush
WEIGHT = {'varbit': 6, 'npc': 3, 'obj': 2, 'loc': 0.15}

TOO_SHORT = 3            # 'ahoy' is four; 'mm' is handled by the directory-stem rule
USED_ENOUGH = 8          # a prefix the quest barely says is not the quest's
CONFIG_EXT = ('rs2', 'loc', 'npc', 'obj', 'enum', 'dbrow', 'dbtable', 'param', 'struct', 'varp',
              'varbit', 'inv', 'seq', 'if', 'constant', 'category', 'hunt', 'mesanim')


def read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def cache_symbols():
    """Every [name] in the cache, by kind, plus each one's category.

    THE CATEGORY MATTERS because it is a second way of being used. ahoy_ghost_banker carries
    category=bank_teller and ahoy_ghost_shopkeeper carries category=shop_keeper and
    param=owned_shop,ahoy_generalshop - and [apnpc1,_bank_teller] and [opnpc1,_shop_keeper] handle
    them without ever naming them. Port Phasmatys's bank and general store work. The first version of
    this tool reported both as unscripted, which is the same mistake as a checker that only matches
    one syntax: a confident zero, arrived at by not looking.
    """
    out = {}
    cats = {}
    for kind in KINDS:
        path = os.path.join(UNPACK, CACHE_FILES[kind])
        if not os.path.exists(path):
            out[kind] = set()
            continue
        text = read(path)
        out[kind] = set(re.findall(r'^\[([a-z0-9_]+)\]', text, re.M))
        name = None
        for line in text.splitlines():
            m = re.match(r'^\[([a-z0-9_]+)\]', line)
            if m:
                name = m.group(1)
            elif name and line.startswith('category='):
                cats[name] = line.split('=', 1)[1].strip()
    return out, cats


def walk_text(root, skip_unpack=True):
    chunks = []
    for base, dirs, files in os.walk(root):
        if skip_unpack and os.path.normpath(base).startswith(os.path.normpath(UNPACK)):
            continue
        if skip_unpack:
            dirs[:] = [d for d in dirs if d != '_unpack']
        for f in files:
            if f.rsplit('.', 1)[-1] in CONFIG_EXT:
                chunks.append(read(os.path.join(base, f)))
    return '\n'.join(chunks)


def owned_prefixes(mine_text, quest_name, elsewhere_counts):
    """The prefixes this quest OWNS, not merely mentions.

    The first version took any word the quest used eight times, which handed quest_legends
    fifty-eight prefixes - 'cert', 'human', 'skill', 'attack' - and then reported two thousand
    unused objs, every certificate in the game among them. A prefix belongs to a quest only if the
    quest is where it mostly lives, counted against the rest of the content tree. Shared vocabulary
    fails that; ahoy_, mm_ and radimus_ pass it.
    """
    mine = defaultdict(int)
    for word in re.findall(r'\b([a-z][a-z0-9]*)_[a-z0-9_]+\b', mine_text):
        if len(word) > TOO_SHORT:
            mine[word] += 1
    out = []
    for word, n in mine.items():
        if n < USED_ENOUGH:
            continue
        theirs = elsewhere_counts.get(word, 0) - n
        if n >= theirs:
            out.append(word)
    stem = quest_name.replace('quest_', '').replace('miniquest_', '')
    if mine.get(stem, 0) >= 2 and stem not in out:
        out.append(stem)
    return sorted(set(out))


def main(argv):
    verbose = '-v' in argv or '--verbose' in argv
    wanted = [a for a in argv if not a.startswith('-')]

    cache, cats = cache_symbols()
    whole = walk_text(SCRIPTS)
    used = set(re.findall(r'\b([a-z0-9_]{4,})\b', whole))

    # how often each prefix appears across the whole content tree, for the ownership test
    everywhere = defaultdict(int)
    for word in re.findall(r'\b([a-z][a-z0-9]*)_[a-z0-9_]+\b', whole):
        everywhere[word] += 1

    rows = []
    for quest in sorted(os.listdir(QUESTS)):
        qdir = os.path.join(QUESTS, quest)
        if not os.path.isdir(qdir):
            continue
        stem = quest.replace('quest_', '').replace('miniquest_', '')
        if wanted and stem not in wanted and quest not in wanted:
            continue
        mine_text = walk_text(qdir, skip_unpack=False)
        pres = owned_prefixes(mine_text, quest, everywhere)
        if not pres:
            continue
        unused = {k: [] for k in KINDS}
        total = 0
        for kind in KINDS:
            for name in sorted(cache[kind]):
                if not any(name.startswith(p + '_') for p in pres):
                    continue
                total += 1
                if name in used:
                    continue
                cat = cats.get(name)
                # the category counts as a reference: [opnpc1,_shop_keeper] names no npc
                if cat and (cat in used or ('_' + cat) in used):
                    continue
                unused[kind].append(name)
        if not total:
            continue
        score = sum(WEIGHT[k] * len(v) for k, v in unused.items())
        rows.append((score, quest, pres, total, unused))

    rows.sort(reverse=True)
    print('%-24s %6s %6s  %s' % ('quest', 'cache', 'score', 'leftovers by kind'))
    print('-' * 76)
    shown = 0
    for score, quest, pres, total, unused in rows:
        if score <= 0 and not verbose:
            continue
        shown += 1
        bits = '  '.join('%s:%d' % (k, len(unused[k])) for k in KINDS if unused[k])
        print('%-24s %6d %6.0f  %s' % (quest, total, score, bits))
        if verbose:
            print('      prefixes: ' + ', '.join(pres))
            for kind in KINDS:
                for name in unused[kind]:
                    print('      %-7s %s' % (kind, name))
    print('')
    print('%d quests have cache symbols nothing in the content uses.' % shown)
    print('Score weights varbits 6, npcs 3, objs 2, locs 0.15 - a bit defined for a quest step is')
    print('near-proof of that step; a loc is usually a bush. Read the names, not the totals.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
