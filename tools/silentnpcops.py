#!/usr/bin/env python3
"""Which npc right-click options the world offers that nothing in this content answers.

THE NPC HALF OF silentops.py, which does the same for locs, and it reads the same way: the 377
cache is ahead of this fork's content, and the symptom of the gap is silence - the option is in
the menu, the player clicks it, and nothing happens, with no error and no log line.

WHY IT FILTERS ON SPAWNED, where the loc tool filters on verbs. Asking "which npc ops have no
trigger" gives about 1,400 answers and most are harmless, because all.npc carries the whole cache
and the maps spawn a fraction of it: an npc nobody places cannot be clicked. The maps are the
filter that makes the list mean something - an npc that IS placed and has an option nothing
answers is a dead click a player can find. 451 npc types are in that state, so the default output
is the ops whose npc is placed at most twelve times, which is where the one-offs live; --all prints
every one.

HOW THE ENGINE DISPATCHES, which this has to mirror exactly or the list is wrong both ways:
  * the trigger is looked up on the npc's OWN type and then its category - Player.getOpTrigger
    takes NpcType.get(target.type), so [opnpc1,<name>] or [opnpc1,_<category>];
  * a multinpc shell OFFERS its variants' options - OpNpcHandler resolves multivarp/multivarbit to
    decide whether the option exists at all - but the trigger is still looked up on the shell. So a
    handler written against the variant never fires, which is how Devin Mendelberg
    (swan_boat_colonist -> swan_colonist_1) sat there with a Talk-to that did nothing;
  * an [apnpc<n>] counts as answering op <n>: a sealed cage has no tile beside it and the approach
    trigger is the only way in (glough.rs2 says so at the top).
Attack is skipped - combat needs no script - and so is an option the cache marks 'hidden'.

THIS IS A REPORT, NOT A RULE, for the same reason silentops.py is not one: most entries are "not
yet" rather than "wrong", and a checker that goes red on correct code gets switched off. What it is
good for is the difference between the two, which it cannot tell you and a person can.

    python3 tools/silentnpcops.py            # ops on npcs placed at most 12 times
    python3 tools/silentnpcops.py --all
"""
import collections, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = None if '--all' in sys.argv else 12


def read(path):
    return open(path, encoding='utf-8', errors='ignore').read()


def npc_configs():
    """{name: {'ops': {n: label}, 'category': str|None, 'name': str|None, 'multinpc': [name]}}"""
    out = {}
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in sorted(files):
            if not fn.endswith('.npc'):
                continue
            cur = None
            for line in read(os.path.join(dirpath, fn)).split('\n'):
                line = line.split('//')[0].strip()
                m = re.fullmatch(r'\[(\w+)\]', line)
                if m:
                    cur = out.setdefault(m.group(1), {'ops': {}, 'category': None, 'name': None,
                                                      'multinpc': []})
                    continue
                if cur is None or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                if re.fullmatch(r'op[1-5]', k):
                    cur['ops'][int(k[-1])] = v
                elif k == 'category':
                    cur['category'] = v
                elif k == 'name':
                    cur['name'] = v
                elif k == 'multinpc':
                    cur['multinpc'].append(v.split(',', 1)[1] if ',' in v else v)
    return out


def triggers():
    """{trigger name: {op numbers}} - [opnpc<n>,x] and [apnpc<n>,x] both answer op <n>."""
    out = collections.defaultdict(set)
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in files:
            if not fn.endswith('.rs2'):
                continue
            for m in re.finditer(r'^\[(?:op|ap)npc([1-5]),([^\]]+)\]',
                                 read(os.path.join(dirpath, fn)), re.M):
                out[m.group(2).strip()].add(int(m.group(1)))
    return out


def spawn_counts():
    """{npc name: how many times the maps place it}"""
    ids = {}
    for line in read(os.path.join(ROOT, 'pack/npc.pack')).split('\n'):
        if '=' in line:
            i, n = line.strip().split('=', 1)
            ids[i] = n
    out = collections.Counter()
    mapdir = os.path.join(ROOT, 'maps')
    for fn in sorted(os.listdir(mapdir)):
        if not fn.endswith('.jm2'):
            continue
        src = read(os.path.join(mapdir, fn))
        i = src.find('==== NPC ====')
        if i < 0:
            continue
        j = src.find('==== OBJ ====', i)
        for line in src[i:j if j > 0 else len(src)].split('\n')[1:]:
            if ': ' in line:
                out[ids.get(line.rsplit(': ', 1)[1].strip(), '?')] += 1
    return out


def main():
    npcs, trig, spawned = npc_configs(), triggers(), spawn_counts()

    def answered(name, op):
        d = npcs[name]
        return (op in trig.get(name, ())
                or (d['category'] and op in trig.get('_' + d['category'], ()))
                or op in trig.get('_', ()))

    rows = []
    for name, d in npcs.items():
        placed = spawned.get(name, 0)
        if not placed:
            continue
        # what the client will offer: the shell's own options, plus its variants' (OpNpcHandler)
        offered = dict(d['ops'])
        for v in d['multinpc']:
            for op, label in npcs.get(v, {'ops': {}})['ops'].items():
                offered.setdefault(op, label)
        dead = [(op, label) for op, label in sorted(offered.items())
                if label and label != 'hidden' and not re.search('attack', label, re.I)
                and not answered(name, op)]
        if dead:
            shown_name = d['name'] or next((npcs[v]['name'] for v in d['multinpc']
                                            if v in npcs and npcs[v]['name']), None)
            rows.append((placed, name, shown_name, dead))

    rows.sort(key=lambda r: (r[0], r[1]))
    shown = 0
    for placed, name, shown_name, dead in rows:
        if LIMIT and placed > LIMIT:
            continue
        shown += 1
        print('  %-34s %-24s x%-4d %s' % (name, (shown_name or '?')[:24], placed,
                                          ', '.join('op%d=%s' % (op, label) for op, label in dead)))
    print()
    print('%d npc types are placed in the maps and carry an op nothing answers (%d shown), '
          'at %d spawn points in all' % (len(rows), shown, sum(r[0] for r in rows)))
    print('%d npc types carry an op at all; %d of those the maps never place, so nothing can click them'
          % (sum(1 for d in npcs.values() if d['ops']),
             sum(1 for n, d in npcs.items() if d['ops'] and not spawned.get(n, 0))))


main()
