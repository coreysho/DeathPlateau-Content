#!/usr/bin/env python3
"""Two sweeps over every .obj config in this build. Both were asked for on 2026-10-03 and both
found things nobody had reported.

  ITEMS THAT SHARE A NAME. The Rogue outfit existed twice - the cache's five unused Rogues' Den
  pieces beside the wired-up set in skilling_outfits - and neither the build nor rs2check minds,
  because two configs with the same display name are perfectly legal. Most matches here are
  legitimate (a premade cocktail and the mixed one, the undead food, the boardgame pieces), so
  this prints and does not judge: it is a list to read, not a gate.

  VARIANTS AGAINST THEIR BASE. "X (t)", "X (g)" and the rest are the same armour with a recolour,
  so they should carry the same bonuses. Studded body (t) and Studded chaps (t) carried NONE -
  cosmetic armour that defended nothing - and Black mask (i) was missing the two attack penalties
  the plain mask has. The four that remain are the imbued rings and the magic shortbow (i), whose
  whole point is that their numbers differ.

    python3 tools/objsweep.py .
"""
import sys, os, glob, re, collections

CONTENT = sys.argv[1]
objs = {}          # name -> dict of key -> list of values
order = []
for path in glob.glob(os.path.join(CONTENT, 'scripts', '**', '*.obj'), recursive=True):
    cur = None
    for line in open(path, newline='', encoding='latin-1').read().replace('\r\n', '\n').split('\n'):
        line = line.split('//')[0].strip()
        if not line: continue
        if line.startswith('[') and line.endswith(']'):
            cur = line[1:-1]
            objs[cur] = collections.defaultdict(list); objs[cur]['_file'] = [path]
            order.append(cur)
        elif cur and '=' in line:
            k, v = line.split('=', 1)
            objs[cur][k.strip()].append(v.strip())

def one(o, k):
    v = objs[o].get(k)
    return v[0] if v else None

print(f'{len(objs)} obj configs\n')

# ---------------------------------------------------------------- duplicate items
# Two configs with the SAME display name that are both real, obtainable items. Certs, templates and
# the holiday eggs legitimately share names, so those are not duplicates.
print('=== ITEMS THAT SHARE A NAME ===')
byname = collections.defaultdict(list)
for o in order:
    n = one(o, 'name')
    if not n or n == 'null': continue
    if one(o, 'certlink') or one(o, 'certtemplate'): continue
    byname[n].append(o)
for n, os_ in sorted(byname.items()):
    if len(os_) < 2: continue
    # only interesting when they are the same KIND of thing - same wearpos, or both unwearable
    kinds = {one(o, 'wearpos') for o in os_}
    if len(kinds) != 1: continue
    files = {os.path.basename(objs[o]['_file'][0]) for o in os_}
    if len(files) == 1 and 'all.obj' in files: continue      # within the cache dump: 377's own
    print(f'  "{n}": ' + ', '.join(f'{o} [{os.path.basename(objs[o]["_file"][0])}]' for o in os_))

# ---------------------------------------------------------------- trimmed variants
print('\n=== TRIMMED / GILDED VARIANTS AGAINST THEIR BASE ===')
BONUS = ['stabattack','slashattack','crushattack','magicattack','rangeattack',
         'stabdefence','slashdefence','crushdefence','magicdefence','rangedefence',
         'meleestr','rangestr','magicdamage','prayerbonus','weight','levelrequire']
def params(o):
    out = {}
    for p in objs[o].get('param', []):
        k, _, v = p.partition(',')
        out[k.strip()] = v.strip()
    return out
SUFFIX = re.compile(r'^(?P<base>.+?) \((?P<tag>t|g|or|i|l|lt|h\d|cr|sk|p|p\+|p\+\+|deg|c|u)\)$')
bad = 0
for o in order:
    n = one(o, 'name')
    if not n: continue
    m = SUFFIX.match(n)
    if not m: continue
    if not one(o, 'wearpos'): continue
    base_name = m.group('base')
    cands = [b for b in byname.get(base_name, []) if one(b, 'wearpos') == one(o, 'wearpos')]
    if len(cands) != 1: continue
    b = cands[0]
    bp, op = params(b), params(o)
    missing = [k for k in BONUS if k in bp and bp[k] != op.get(k)]
    if missing:
        bad += 1
        print(f'  {o} ("{n}") vs {b}:')
        for k in missing:
            print(f'      {k}: base {bp[k]}, variant {op.get(k, "MISSING")}')
    if one(b, 'category') and one(o, 'category') != one(b, 'category'):
        print(f'  {o} ("{n}"): category {one(o, "category")}, base {b} has {one(b, "category")}')
print(f'\n{bad} variant(s) with bonuses that do not match the base')
