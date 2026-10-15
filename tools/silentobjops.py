#!/usr/bin/env python3
"""Which item options the cache advertises that nothing in this content answers.

THE THIRD OF THREE. tools/silentops.py asks this of locs and tools/silentnpcops.py of npcs; this
one asks it of objs, and of all three classes of option an obj can carry:

    iop1-5      the inventory menu     Read, Rub, Empty, Open, Check, Play...
    op1-5       on the ground          almost always just Take
    wearop1-8   worn, in the tab       a cape's Teleport, a slayer helmet's Check

The symptom is the same in all three: the option appears in the menu, the player clicks it, and
nothing happens at all - no message, no error, no log line.

IT MIRRORS THE ENGINE, option class by option class, because each is dispatched differently:

    iop<n>     OpHeldHandler -> ScriptProvider.getByTrigger(OPHELD<n>, obj, category), which is the
               obj's own trigger, then its category's, then a GLOBAL [opheld<n>,_]. Those globals
               are real behaviour and not a fallthrough: [opheld2,_] is equip (player/scripts/
               equip.rs2) and [opheld5,_] is drop, which is why Wear, Wield and Drop never appear
               in this report however few objs name them.
    op<n>      OpObjHandler -> the APOBJ<n> trigger, the same three ways. [opobj3,_] is pickup, so
               Take is answered everywhere too.
    wearop<n>  WearOpHandler, which looks a LABEL up by name because the script compiler's trigger
               list is compiled into an npm package and nothing here can add to it:
               [label,wearop<n>_<obj>] for one obj and [label,wearop<n>__<category>] for a family.

THE DEFAULTS ARE NOT IN THE FILES, which is what makes this honest: ObjType's own defaults are
op3=Take and iop5=Drop, and they live in the engine rather than in any .obj, so reading the config
files sees only what somebody wrote down. An obj that explicitly re-declares one is reported like
any other.

AND IT READS EVERY .obj FILE, not just the cache's. silentops.py spent its first weeks reading
scripts/_unpack/377/all.loc alone and so knew half the world; the fork's own objs - quest items,
rewards, the house - live in content .obj files beside their scripts.

    python3 tools/silentobjops.py            # verbs on at most 12 objs
    python3 tools/silentobjops.py --all
"""
import collections, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = None if '--all' in sys.argv else 12


def read(path):
    return open(path, encoding='utf-8', errors='ignore').read()


def main():
    pack = set(l.strip().split('=', 1)[1]
               for l in open(os.path.join(ROOT, 'pack/obj.pack'), encoding='utf-8') if '=' in l)
    # {kind: {obj: {n: label}}} for the three classes, and the obj's category beside it
    ops = {'iop': collections.defaultdict(dict), 'op': collections.defaultdict(dict),
           'wearop': collections.defaultdict(dict)}
    cats = {}
    for path in sorted(glob.glob(os.path.join(ROOT, 'scripts/**/*.obj'), recursive=True)):
        for b in re.split(r'\n(?=\[)', read(path)):
            m = re.match(r'\[([\w]+)\]', b)
            if not m:
                continue
            n = m.group(1)
            c = re.search(r'^category=(\w+)$', b, re.M)
            if c:
                cats[n] = c.group(1)
            if n not in pack:
                continue
            for kind, hi in (('iop', 5), ('op', 5), ('wearop', 8)):
                for k, v in re.findall(r'^%s([1-%d])=(.*)$' % (kind, hi), b, re.M):
                    ops[kind][n][int(k)] = v.strip()

    body = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'scripts')):
        if '_unpack' in dirpath:
            continue
        for f in files:
            if f.endswith('.rs2'):
                body.append(read(os.path.join(dirpath, f)))
    body = '\n'.join(body)

    held = set(re.findall(r'\[opheld([1-5]),\s*([\w]+)\s*\]', body))
    held_global = set(re.findall(r'\[opheld([1-5]),?\s*_?\s*\]', body))
    gobj = set(re.findall(r'\[(?:op|ap)obj([1-5]),\s*([\w]+)\s*\]', body))
    gobj_global = set(re.findall(r'\[(?:op|ap)obj([1-5]),?\s*_?\s*\]', body))
    worn = set(re.findall(r'\[label,wearop([1-8])_([\w]+)\]', body))

    def answered(kind, obj, k):
        cat = cats.get(obj)
        if kind == 'iop':
            return (str(k), obj) in held or (cat and (str(k), '_' + cat) in held) \
                or str(k) in held_global
        if kind == 'op':
            return (str(k), obj) in gobj or (cat and (str(k), '_' + cat) in gobj) \
                or str(k) in gobj_global
        # the worn label: the obj's own name, else _<category> (the handler's double underscore)
        return (str(k), obj) in worn or (cat and (str(k), '_' + cat) in worn)

    # 'hidden' IS NOT AN OPTION ON THE GROUND, and the engine says so in one line:
    # OpObjHandler refuses `type.op[op - 1] === 'hidden'` outright, the way OpLocHandler does for
    # locs, so those are slots held for the engine to drive and not menu entries anybody can click.
    # The four it hid here were a firework, two hunter traps and a magic box. The inventory handler
    # does NOT make the same check - OpHeldHandler only refuses null - so an iop called 'hidden'
    # would be a live option, and if one ever appears it belongs in this report.
    for obj, d in list(ops['op'].items()):
        for k, v in list(d.items()):
            if v == 'hidden':
                del d[k]
        if not d:
            del ops['op'][obj]

    TITLES = {'iop': 'IN THE INVENTORY', 'op': 'ON THE GROUND', 'wearop': 'WORN, IN THE TAB'}
    total = 0
    for kind in ('iop', 'op', 'wearop'):
        verb = collections.defaultdict(set)
        for obj, d in ops[kind].items():
            for k, v in d.items():
                verb[v].add((obj, k))
        rows = []
        for v, s in sorted(verb.items()):
            if not any(answered(kind, obj, k) for obj, k in s):
                rows.append((len(s), v, sorted(obj for obj, _ in s)))
        rows.sort()
        total += len(rows)
        print()
        print('==== %s (%d option labels nothing answers) ====' % (TITLES[kind], len(rows)))
        for c, v, ns in rows:
            if LIMIT and c > LIMIT:
                continue
            print('  %-24s %3d   %s' % (v, c, ', '.join(ns[:5]) + (' ...' if len(ns) > 5 else '')))
    print()
    print('%d option labels in all, across the three classes, that nothing answers' % total)
    for kind in ('iop', 'op', 'wearop'):
        print('  %-8s %5d objs carry one, %5d option slots in total'
              % (kind, len(ops[kind]), sum(len(d) for d in ops[kind].values())))


main()
