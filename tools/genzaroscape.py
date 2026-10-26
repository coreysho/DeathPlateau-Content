#!/usr/bin/env python3
"""The Zaros mage arena cape: Old School's own cape model, repainted Zarosian purple.

WHERE THE ART COMES FROM. Old School has no Zaros god cape - the Mage Arena has three gods and
Zaros is not one of them. What it does have is the "Imbued mage arena cape", obj 29448, which is
the unlock TOKEN rather than a worn cape: it carries an inventory model and nothing else, no
wearpos and no worn models at all. So the icon is Old School's (imported by
tools/models/importosrs.py as obj_imbued_zaros_cape) and the worn half is this build's own imbued
cape model with the colour changed - which is also the only way to be sure the back of the player
matches the icon in the bank.

BAKED, NOT RECOLOUR PAIRS, and that is forced. An obj config carries six recolour pairs and they
apply to every model the obj names. The imported icon uses six colours by itself and the worn model
two more, so a config cannot hold both halves. The Undertaker's outfit hit the same wall and took
the same way out: write the model again with the colour in it.

ONE RULE, NOT A TABLE OF PAIRS: every face's HUE becomes Zaros purple and its saturation and
lightness are left alone. That keeps the shading the artist drew, and it leaves the white trim white
for free - a face with saturation 0 is grey whatever its hue says.

  python3 tools/genzaroscape.py            # report
  python3 tools/genzaroscape.py --apply
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

ZAROS_HUE = 47          # ~264 degrees: violet, and distinct from all three god capes (39-42)

# (source model, written as) - the icon is the import, the worn pair is the Saradomin cape's, whose
# body is one blue and whose trim is white. Guthix's and Zamorak's worn models are the same mesh in
# another colour, so which one is copied changes nothing after the hue is replaced.
PARTS = [
    ('obj_imbued_zaros_cape', 'obj_imbued_zaros_cape'),
    ('obj_imbued_saradomin_cape_manwear', 'obj_imbued_zaros_cape_manwear'),
    ('obj_imbued_saradomin_cape_womanwear', 'obj_imbued_zaros_cape_womanwear'),
]


def repaint(col):
    """Hue to Zaros purple; saturation and lightness untouched."""
    return (ZAROS_HUE << 10) | (col & 0x3FF)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default=CONTENT)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    mdir = os.path.join(a.content, 'models', 'obj')
    written = []
    for src, dst in PARTS:
        path = os.path.join(mdir, src + '.ob2')
        if not os.path.exists(path):
            raise SystemExit(f'{src}.ob2 is missing - run importosrs.py for obj 29448 first')
        m = parse_ob2(open(path, 'rb').read())
        before = sorted(set(m['colour']))
        m['colour'] = [repaint(c) for c in m['colour']]
        after = sorted(set(m['colour']))
        b = encode(m)
        ok, why = roundtrip(b, m)
        if not ok:
            raise SystemExit(f'{dst} does not survive a round trip: {why}')
        print(f'  {dst:42s} {m["fcount"]:4d} faces, {len(before)} colours -> {len(after)}')
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
