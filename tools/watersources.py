#!/usr/bin/env python3
"""Every water source the minimap advertises, and whether a bucket can actually be filled there.

THE GAME ALREADY SAYS WHERE THE WATER IS. water_source_icon is the little blue marker drawn on the
minimap, and the maps carry 98 of them. Filling a container, though, is driven by a category:
[oplocu,_watersource] in general_use/scripts/water_sources.rs2 takes buckets, jugs, vials, bowls
and watering cans, and [oplocu,_well] takes a bucket only. A loc with a marker beside it and no
category is a tap the game points at and then refuses to use - which is what "can't use a bucket
on the water pump in Falador" turned out to be: loc_11661, name "Waterpump", at 2947,3382, with a
marker at 2950,3382 and no category at all.

So the marker is the evidence. This pairs every marker with the water-ish loc nearest it and
reports any that the handlers do not cover; --apply writes the category in.

  wells get `well`, because that is what the existing [oplocu,_well] covers and a well in this
  game fills a bucket and nothing else.
  everything else gets `watersource`.

A loc with its own [oplocu,<name>] trigger keeps it - a specific trigger beats a category one -
so adding the category only adds the fill path and cannot shadow a quest's own handler.

NOT EVERYTHING WITH A MARKER NEXT TO IT IS WATER. A plain "Barrel" is not one: the three
sitting by a marker are a brewer's barrel, Bob's barrel from Murder Mystery and the Seers' flour
barrel, each of them next to a sink that IS the marker's subject. So the marker has to be on the
loc or touching it, and a barrel has to say water in its own name.

  python3 tools/watersources.py              # report
  python3 tools/watersources.py --apply
"""
import argparse, collections, glob, os, re, sys

# A plain "Barrel" is not a water source in this game - the ones by a marker turned out to be a
# brewer's barrel, Bob's barrel from Murder Mystery and the Seers' flour barrel, all of which sit
# near a sink that is. Only a barrel that says water in its own name counts.
WATER_WORDS = ('fountain', 'pump', 'sink', 'well', 'tap', 'water barrel')
# The marker is not always on the loc: Falador's water pump stands at 2947,3382 with its marker
# three tiles away at 2950,3382. Three is as far as it ever is, and with plain barrels out of the
# word list above, three no longer drags anything in that is not water.
NEAR = 3
EXCLUDE = {}


def loc_names(content):
    out = {}
    for line in open(os.path.join(content, 'pack/loc.pack'), encoding='utf-8'):
        i, _, n = line.strip().partition('=')
        if i.isdigit():
            out[int(i)] = n
    return out


def loc_configs(content):
    """name -> (file, dict). Keeps the FIRST declaration, which is the one the build uses."""
    out = {}
    for p in sorted(glob.glob(os.path.join(content, 'scripts/**/*.loc'), recursive=True)):
        cur = None
        for line in open(p, encoding='utf-8', errors='replace'):
            s = line.strip()
            if s.startswith('//'):
                continue
            if s.startswith('[') and s.endswith(']'):
                cur = s[1:-1]
                out.setdefault(cur, (p, {}))
            elif cur and '=' in s and out[cur][1] is not None:
                k, v = s.split('=', 1)
                out[cur][1].setdefault(k, v)
    return out


def placements(content, names):
    marks = []
    grid = collections.defaultdict(list)
    icons = {i for i, n in names.items() if n == 'water_source_icon'}
    for f in sorted(glob.glob(os.path.join(content, 'maps/m*.jm2'))):
        mx, mz = os.path.basename(f)[1:-4].split('_')
        mx, mz = int(mx), int(mz)
        section = False
        for line in open(f, encoding='utf-8', errors='replace'):
            if line.startswith('===='):
                section = 'LOC' in line
                continue
            if not section:
                continue
            p = line.split()
            if len(p) < 4 or not p[3].isdigit():
                continue
            lv, x, z = int(p[0]), mx * 64 + int(p[1]), mz * 64 + int(p[2].rstrip(':'))
            if int(p[3]) in icons:
                marks.append((lv, x, z))
            else:
                grid[(lv, x >> 2, z >> 2)].append((x, z, int(p[3])))
    return marks, grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content',
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    names = loc_names(a.content)
    cfgs = loc_configs(a.content)
    marks, grid = placements(a.content, names)

    found = {}
    for lv, x, z in marks:
        for dx in (-4, 0, 4):
            for dz in (-4, 0, 4):
                for ox, oz, lid in grid.get((lv, (x + dx) >> 2, (z + dz) >> 2), []):
                    if max(abs(ox - x), abs(oz - z)) > NEAR:
                        continue
                    n = names.get(lid)
                    if not n or n not in cfgs:
                        continue
                    label = cfgs[n][1].get('name', '').lower()
                    if any(w in label for w in WATER_WORDS):
                        found.setdefault(n, (label, lv, x, z))

    want_well, want_source, skipped, already = [], [], [], []
    for n, (label, lv, x, z) in sorted(found.items()):
        cat = cfgs[n][1].get('category')
        if n in EXCLUDE:
            skipped.append((n, label, EXCLUDE[n]))
        elif cat in ('watersource', 'well'):
            already.append(n)
        elif 'well' in label:
            want_well.append((n, label, x, z))
        else:
            want_source.append((n, label, x, z))

    for title, rows, cat in (('-> category=well', want_well, 'well'),
                             ('-> category=watersource', want_source, 'watersource')):
        print(f'{title}   [{len(rows)}]')
        for n, label, x, z in rows:
            print(f'    {n:<28} "{label}"   e.g. {x},{z}')
    print(f'\nleft alone:')
    for n, label, why in skipped:
        print(f'    {n:<28} "{label}"   {why}')
    print(f'\n{len(marks)} markers, {len(found)} water locs beside them, '
          f'{len(already)} already fillable, {len(want_well) + len(want_source)} to fix')

    if a.apply:
        for rows, cat in ((want_well, 'well'), (want_source, 'watersource')):
            for n, _, _, _ in rows:
                path = cfgs[n][0]
                src = open(path, encoding='utf-8', newline='').read()
                nl = '\r\n' if '\r\n' in src else '\n'
                t = src.replace('\r\n', '\n')
                m = re.search(r'^\[' + re.escape(n) + r'\]\n', t, re.M)
                assert m, n
                t = t[:m.end()] + f'category={cat}\n' + t[m.end():]
                open(path, 'w', encoding='utf-8', newline='').write(t.replace('\n', nl))
        print(f'\nwrote {len(want_well) + len(want_source)} categories')
    else:
        print('\ndry run - pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
