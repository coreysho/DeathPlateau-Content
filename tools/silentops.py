#!/usr/bin/env python3
"""Which op labels the cache advertises that nothing in this content answers.

THE COMPANION TO interfaceindex.py. That tool reads the unidentified interface pool and says what
each panel IS; this one reads the loc configs and says which right-click options exist in the world
and have no trigger behind them. Both exist for the same reason: the 377 cache is ahead of this
fork's content and the symptom of the gap is silence - the option appears in the menu, the player
clicks it, and nothing happens, with no error and no log line.

WHY IT REPORTS VERBS AND NOT LOCS. Asking "which loc ops have no trigger" gives 2,206 answers, most
of them fine: a door handled by a multiloc shell, a ladder covered by a category trigger, scenery
that was never meant to do anything. That list is noise and noise gets switched off. Asking "which
op LABELS have no answered loc ANYWHERE in the game" gives about a hundred, and they read as
features rather than as oversights: Smelt on seven furnaces, Churn on two dairy churns, Refuel and
Pedal and Put-ore-on for a Blast Furnace nobody built, Grab on the Magic Training Arena's bone
piles.

THIS IS A REPORT, NOT A RULE. It is deliberately not an rs2check rule: a hundred entries is a
hundred decisions, most of them "not yet", and a checker that goes red on correct code gets
ignored. Run it when choosing what to build.

IT MIRRORS THE ENGINE'S OWN DISPATCH, which matters more here than it looks. OpLocHandler resolves
multivarp/multivarbit to the VARIANT only to decide whether the option exists, and then
Player.getOpTrigger looks the trigger up on LocType.get(target.type) - the loc as the map placed
it, which is the SHELL - and then on its category. So a shell's advertised options are its own plus
every variant's, while the trigger that answers them is always the shell's. A first version of this
tool checked each variant for a trigger of its own and so reported ten canoeing ops as silent that
canoeing.rs2 answers on the four station shells; the comment at the top of that file is this tool
crying wolf, preserved. [aploc<n>] answers option n as well, for the same reason [apnpc<n>] does -
thirty of those exist - and they counted for nothing until now.

    python3 tools/silentops.py            # verbs on at most 12 locs
    python3 tools/silentops.py --all
"""
import collections, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = None if '--all' in sys.argv else 12


def main():
    # EVERY .loc FILE, NOT JUST THE CACHE'S. This read scripts/_unpack/377/all.loc alone until
    # 15 October and so saw half the world: 2,704 locs with an option out of 6,167, because every
    # loc this fork has written - quest scenery, farming patches, cooking ranges, the canoe stations
    # - lives in a content .loc beside its scripts. It also meant the multiloc map was half built,
    # which is how fourteen farming Guide options read as silent while their shells answered them
    # from scripts/skill_farming/configs/farming.loc.
    locfiles = sorted(glob.glob(os.path.join(ROOT, 'scripts/**/*.loc'), recursive=True))
    pack = set(l.strip().split('=', 1)[1]
               for l in open(os.path.join(ROOT, 'pack/loc.pack'), encoding='utf-8') if '=' in l)
    ops, cats = collections.defaultdict(dict), {}
    shells = collections.defaultdict(set)   # variant -> the shells that can show it
    for path in locfiles:
        loc = open(path, encoding='utf-8', errors='ignore').read()
        for b in re.split(r'\n(?=\[)', loc):
            m = re.match(r'\[([\w]+)\]', b)
            if not m:
                continue
            n = m.group(1)
            c = re.search(r'^category=(\w+)$', b, re.M)
            if c:
                cats[n] = c.group(1)
            for v in re.findall(r'^multiloc=\d+,(\w+)$', b, re.M):
                shells[v].add(n)
            if n not in pack:
                continue
            for k, v in re.findall(r'^op([1-5])=(.*)$', b, re.M):
                ops[n][int(k)] = v.strip()

    blob = []
    for dp, _, fs in os.walk(os.path.join(ROOT, 'scripts')):
        if '_unpack' in dp:
            continue
        for f in fs:
            if f.endswith('.rs2'):
                blob.append(open(os.path.join(dp, f), encoding='utf-8', errors='ignore').read())
    body = '\n'.join(blob)
    # [aploc<n>] answers option n as surely as [oploc<n>] does: one fires where the player stands,
    # the other after the walk, and the engine takes whichever the content wrote.
    trig = set(re.findall(r'\[(?:op|ap)loc([1-5]),\s*([\w]+)\s*\]', body))

    verb = collections.defaultdict(set)
    for n, d in ops.items():
        for k, v in d.items():
            verb[v].add((n, k))
    def direct(n, k):
        return (str(k), n) in trig or (cats.get(n) and (str(k), '_' + cats[n]) in trig)

    def answers(n, k):
        # the loc's own trigger or its category's, and for a multiloc variant the shell's, because
        # the shell is the type the map placed and so the type the lookup is made on
        return direct(n, k) or any(direct(sh, k) for sh in shells.get(n, ()))

    rows = []
    for v, s in sorted(verb.items()):
        answered = sum(1 for n, k in s if answers(n, k))
        if answered == 0:
            rows.append((len(s), v, sorted(n for n, _ in s)))
    rows.sort()
    shown = 0
    for c, v, ns in rows:
        if LIMIT and c > LIMIT:
            continue
        shown += 1
        print('  %-24s %3d   %s' % (v, c, ', '.join(ns[:5]) + (' ...' if len(ns) > 5 else '')))
    print()
    print('%d op labels no loc in the game answers (%d shown)' % (len(rows), shown))
    print('%d locs in the pack carry an op; %d op slots in total' %
          (len(ops), sum(len(d) for d in ops.values())))


main()
