"""Which monsters hand a player a pile of items that will not fit in their inventory.

Asked for as "run an audit on other monsters dropping large amounts of unnoted items", after a
greater abyssal demon's 60 pure essence turned up loose on the floor.

TWO PLACES SAY WHAT A MONSTER DROPS, AND ONLY ONE OF THEM IS THE DROP. The obj_add calls in
scripts/drop_tables/scripts/*.rs2 are what actually hits the floor; scripts/drop_tables/configs/
npc_drops.dbrow is the table the in-game Drops viewer reads. Editing only the dbrow changes the
picture and not the loot, which is how the first version of this tool "fixed" that demon without
touching the essence it drops. Both are swept here, and --fix rewrites both.

THE RULE IS THE INVENTORY, not the number. A stackable item is one slot however many there are, so
500 rune arrows are fine. An UNSTACKABLE one is a slot each: 60 pure essence is 60 slots out of 28,
so most of the drop cannot be picked up at all. Every such item that has a noted form - something
with certlink= pointing at it - should be dropped in that form instead, because that is one slot and
the bank takes it.

So a drop is reported when ALL of:
  * the obj is unstackable (stackable=no, the default) and is not itself a note, and
  * it has a cert_* twin, and
  * the count, or the top of a range, is at least --min (default 10).

Counts the parser cannot read - calc(random(101) + 100) and friends - are listed separately for a
person to judge rather than guessed at.

    python3 tools/notedrops.py                 # the default sweep
    python3 tools/notedrops.py --min 2         # every multi-drop, to argue about the small ones
    python3 tools/notedrops.py --fix           # rewrite the reportable drops to their noted twin
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DROPS = os.path.join(ROOT, 'scripts', 'drop_tables', 'configs', 'npc_drops.dbrow')
SCRIPTS = os.path.join(ROOT, 'scripts', 'drop_tables', 'scripts')


def load_objs():
    """name -> {'stackable': bool, 'cert': name or None, 'isnote': bool} over every .obj in the tree.

    Every .obj file, not just _unpack/377/all.obj: the certs for items this fork added live beside
    the items, and reading only the unpacked cache made ore and bar drops look unnotable.
    """
    objs = {}
    certlink = {}
    for base, _dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        for f in files:
            if not f.endswith('.obj'):
                continue
            name = None
            with open(os.path.join(base, f), encoding='utf8', errors='replace') as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith('[') and line.endswith(']'):
                        name = line[1:-1]
                        objs.setdefault(name, {'stackable': False, 'cert': None, 'isnote': False})
                    elif name is None or '=' not in line:
                        continue
                    elif line.startswith('stackable='):
                        objs[name]['stackable'] = line.split('=', 1)[1].strip() == 'yes'
                    elif line.startswith('certlink='):
                        certlink[line.split('=', 1)[1].strip()] = name
                    elif line.startswith('certtemplate='):
                        # A NOTE IS ALREADY THE ANSWER. Cert records carry nothing but certlink and
                        # certtemplate, so they read as unstackable off their own lines, and the
                        # first version of this reported 119 rows of "Silver ore (noted) x100" as
                        # piles that could not be noted. The template is what makes them one slot.
                        objs[name]['isnote'] = True
    for base, cert in certlink.items():
        if base in objs:
            objs[base]['cert'] = cert
    return objs


DROP = re.compile(r'^data=drop,([^,]+),(.*),([0-9]+(?:-[0-9]+)?),(.+)$')
OBJADD = re.compile(r'obj_add\(npc_coord,\s*([A-Za-z_]\w*),\s*([^,]+),\s*\^lootdrop_duration\)')


def table_rows():
    """(lines, [(line index, npc, obj, label, count text, rate)], newline) for the Drops viewer."""
    # newline='' so the file's own line endings survive a --fix: writing an LF file back as CRLF
    # would show as 8,591 changed lines in a diff of 33 real ones.
    with open(DROPS, encoding='utf8', errors='replace', newline='') as fh:
        raw = fh.read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    lines = raw.replace('\r\n', '\n').split('\n')
    npc = '?'
    out = []
    for i, line in enumerate(lines):
        if line.startswith('data=npc,'):
            npc = line.split(',', 1)[1].strip()
        m = DROP.match(line.strip())
        if m:
            out.append((i, npc, m.group(1), m.group(2), m.group(3), m.group(4)))
    return lines, out, nl


def script_rows():
    """({path: [lines, newline]}, [(path, line index, obj, count text)]) for every obj_add."""
    files, out = {}, []
    for f in sorted(os.listdir(SCRIPTS)):
        if not f.endswith('.rs2'):
            continue
        path = os.path.join(SCRIPTS, f)
        with open(path, encoding='utf8', errors='replace', newline='') as fh:
            raw = fh.read()
        nl = '\r\n' if '\r\n' in raw else '\n'
        lines = raw.replace('\r\n', '\n').split('\n')
        files[path] = [lines, nl]
        for i, line in enumerate(lines):
            m = OBJADD.search(line)
            if m:
                out.append((path, i, m.group(1), m.group(2).strip()))
    return files, out


def top(count_text):
    """The biggest number a count can be, or None when it is an expression."""
    if not re.fullmatch(r'[0-9]+(-[0-9]+)?', count_text):
        return None
    return int(count_text.split('-')[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--min', type=int, default=10)
    ap.add_argument('--fix', action='store_true')
    args = ap.parse_args()

    objs = load_objs()
    lines, drops, nl = table_rows()
    files, adds = script_rows()

    def pile(obj, count_text):
        """('pile', cert, n) / ('computed', None, text) for a drop worth reporting, else None."""
        info = objs.get(obj)
        if info is None or info['stackable'] or info['isnote'] or not info['cert']:
            return None
        n = top(count_text)
        if n is None:
            return ('computed', None, count_text)
        if n < args.min:
            return None
        return ('pile', info['cert'], n)

    # ------------------------------------------------------------- what actually hits the floor
    script_hits, computed = [], []
    for path, i, obj, count in adds:
        r = pile(obj, count)
        if r is None:
            continue
        (computed if r[0] == 'computed' else script_hits).append(
            (path, i, obj, count, r[1]))

    def size(row):
        return top(row[3]) or 0

    print('%d obj_add drops across %d drop scripts, and %d rows in npc_drops.dbrow'
          % (len(adds), len(files), len(drops)))
    print('')
    print('  %d DROPS hand over %d or more of an unstackable item that has a noted form:'
          % (len(script_hits), args.min))
    for path, _i, obj, count, cert in sorted(script_hits, key=lambda r: -size(r)):
        print('    %-32s %-28s x%-9s -> %s' % (os.path.basename(path), obj, count, cert))
    print('')
    print('  %d drop a count this cannot read, which a person has to judge:' % len(computed))
    for path, _i, obj, count, _c in computed:
        print('    %-32s %-28s x%s' % (os.path.basename(path), obj, count))

    # -------------------------------------------------- and what the Drops viewer says they do
    table_hits, unnotable, unknown = [], [], []
    for i, npc, obj, label, count, rate in drops:
        info = objs.get(obj)
        n = top(count) or 0
        if info is None:
            if n >= args.min:
                unknown.append((npc, obj, count))
            continue
        r = pile(obj, count)
        if r is None:
            if n >= args.min and not info['stackable'] and not info['isnote']:
                unnotable.append((npc, obj, count))
            continue
        table_hits.append((i, npc, obj, label, count, rate, r[1]))

    print('')
    print('  %d ROWS of the Drops viewer show the same kind of pile:' % len(table_hits))
    for _i, npc, obj, _label, count, rate, cert in sorted(table_hits, key=lambda r: -(top(r[4]) or 0)):
        print('    %-32s %-28s x%-9s %-10s -> %s' % (npc, obj, count, rate, cert))
    if unnotable:
        print('')
        print('  %d rows show a pile with NO noted form:' % len(unnotable))
        for npc, obj, count in sorted(unnotable, key=lambda r: -(top(r[2]) or 0)):
            print('    %-32s %-28s x%s' % (npc, obj, count))
    if unknown:
        print('')
        print('  %d rows name an obj no .obj file declares:' % len(unknown))
        for npc, obj, count in unknown:
            print('    %-32s %-28s x%s' % (npc, obj, count))

    if args.fix:
        touched = set()
        for path, i, obj, _count, cert in script_hits:
            flines = files[path][0]
            flines[i] = flines[i].replace('obj_add(npc_coord, %s,' % obj,
                                          'obj_add(npc_coord, %s,' % cert, 1)
            touched.add(path)
        for path in touched:
            flines, fnl = files[path]
            with open(path, 'w', encoding='utf8', newline='') as fh:
                fh.write(fnl.join(flines))
        for i, _npc, _obj, label, count, rate, cert in table_hits:
            noted = label if label.endswith('(noted)') else label + ' (noted)'
            lines[i] = 'data=drop,%s,%s,%s,%s' % (cert, noted, count, rate)
        with open(DROPS, 'w', encoding='utf8', newline='') as fh:
            fh.write(nl.join(lines))
        print('')
        print('rewrote %d drops in %d scripts and %d viewer rows to their noted twin'
              % (len(script_hits), len(touched), len(table_hits)))
    return 1 if unknown else 0


if __name__ == '__main__':
    sys.exit(main())
