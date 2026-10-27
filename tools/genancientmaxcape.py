#!/usr/bin/env python3
"""The imbued ancient max cape and hood: the Max cape's own models, with Old School's recolour
baked into them.

WHY BAKED RATHER THAN recol= LINES, which is how every other max cape variant in this build does
it. AN OBJ CONFIG HOLDS SIX RECOLOUR PAIRS. Old School's imbued ancient max cape (obj 34625 in
OpenRS2 cache 2746) carries TWELVE and its hood carries eleven, because the ancient recolour
repaints the emblem as well as the cloth - and every one of those twelve source colours is present
in this build's converted obj_max_cape. Six of twelve is not a cosmetic compromise, it is half an
item: the cape would come out black with a Max cape's emblem still on it.

So the pairs are applied to the mesh instead and written out as models of their own, which is the
way out the Undertaker's outfit took when it hit the same wall. tools/genmaxvariants.py then names
these models through the variant's `models` key instead of writing recol lines.

THE PAIRS ARE JAGEX'S OWN, read out of the item table rather than transcribed, so a colour here is
a colour Old School's client would produce.

  python3 tools/genancientmaxcape.py            # report
  python3 tools/genancientmaxcape.py --apply
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)
for cand in (r'C:\LostCityServer\tools\models', os.path.join(CONTENT, '..', 'tools', 'models')):
    if os.path.isdir(cand):
        sys.path.insert(0, cand)
        break
from osrs2ob2 import parse_ob2, encode, roundtrip        # noqa: E402
from animconv474 import pack_append                      # noqa: E402

# obj 34625, Imbued ancient max cape - twelve pairs, HSL16 both sides.
CAPE = {815: 22, 675: 16, 673: 12, 668: 8, 784: 8,
        4820: 49600, 5714: 49600, 5708: 49589, 5706: 49575, 5683: 49575,
        972: 55213, 945: 55207}
# obj 34627, Imbued ancient max hood - eleven.
HOOD = {685: 26, 815: 22, 675: 16, 673: 12, 668: 8, 914: 12, 784: 8,
        4820: 49600, 5458: 49618, 972: 55213, 945: 55207}

PARTS = ([('obj_max_cape%s' % s, 'obj_imbued_ancient_max_cape%s' % s, CAPE)
          for s in ('', '_manwear', '_womanwear')] +
         [('obj_max_hood%s' % s, 'obj_imbued_ancient_max_hood%s' % s, HOOD)
          for s in ('', '_manwear', '_womanwear', '_manhead', '_womanhead')])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default=CONTENT)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    mdir = os.path.join(a.content, 'models', 'obj')
    written = []
    for src, dst, table in PARTS:
        path = os.path.join(mdir, src + '.ob2')
        if not os.path.exists(path):
            raise SystemExit(f'{src}.ob2 is missing')
        m = parse_ob2(open(path, 'rb').read())
        hit = sum(1 for c in m['colour'] if c in table)
        m['colour'] = [table.get(c, c) for c in m['colour']]
        b = encode(m)
        ok, why = roundtrip(b, m)
        if not ok:
            raise SystemExit(f'{dst} does not survive a round trip: {why}')
        print(f'  {dst:42s} {m["fcount"]:4d} faces, {hit} repainted')
        if a.apply:
            open(os.path.join(mdir, dst + '.ob2'), 'wb').write(b)
            written.append(dst)
    if a.apply:
        ids, _ = pack_append(os.path.join(a.content, 'pack', 'model.pack'), written)
        for n in written:
            print(f'  model.pack {ids[n]} = {n}')
    else:
        print('  dry run - pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
