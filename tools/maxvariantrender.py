#!/usr/bin/env python3
"""Render every Max cape variant piece, and prove their recolours actually bite.

THE CHECK THIS EXISTS FOR. All but the fire and infernal pieces have no model of their own: they
are the plain Max cape's model with a recolour list taken from the OSRS item table. That list names SOURCE
COLOURS on OSRS's model - and this build's model is a re-encoding of it. If the re-encoding moved
a colour, every recolour would silently match nothing, all six god capes would render as a plain
Max cape, and no config, no linter and no packed-data check would notice. Nothing would look
broken; it would look like the wrong cape.

So this reads each recolour pair out of the GENERATED config, applies it through ob2render's own
Model.recolour - the same rgb15 -> hsl16 path ObjConfig.ts uses - and counts the faces it hits.

TWO PAIRS ARE MEANT TO HIT NOTHING, and finding that out is why this file exists. A hood's
six-pair list is the cape's five pairs with one appended - the same five sources, in order - and
two of those five (hsl16 668 and 673) are colours of the cape and of no hood model. So they do
nothing on a hood, in OSRS exactly as here: the OSRS models were decoded out of index 7 and carry
the same face counts and the same colour sets as the converted ones, which is also the evidence
that the conversion did not move a colour at all. Those two are listed in the spec under
recolours.inert_in_osrs_too and are expected to miss. Every OTHER source missing is an error.

    python3 tools/maxvariantrender.py                      # check only
    python3 tools/maxvariantrender.py out.png              # check, and write a contact sheet
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(C, 'tools'))
OBJ = os.path.join(C, 'scripts', 'skillcapes', 'configs', 'max_cape_variants.obj')
MDIR = os.path.join(C, 'models', 'obj')


def records(text):
    """[(local, {key: [values]})] for every block in the generated .obj."""
    out = []
    cur = None
    for line in text.replace('\r\n', '\n').split('\n'):
        line = line.split('//')[0].strip()
        if not line:
            continue
        m = re.match(r'^\[(\w+)\]$', line)
        if m:
            cur = (m.group(1), {})
            out.append(cur)
        elif cur and '=' in line:
            k, v = line.split('=', 1)
            cur[1].setdefault(k, []).append(v)
    return out


def main():
    out_png = sys.argv[1] if len(sys.argv) > 1 else None
    if not os.path.exists(OBJ):
        print('no %s - run tools/genmaxvariants.py first' % os.path.relpath(OBJ, C))
        return 2
    import ob2render
    spec = json.load(open(os.path.join(C, 'tools', 'maxcapevariantspec.json')))
    global INERT
    INERT = spec['recolours']['inert_in_osrs_too']['pairs']

    recs = records(open(OBJ, newline='').read())
    # COUNTED FROM THE SPEC. A hard-coded 16 here turned into a failure the day a ninth variant
    # was added, which is the one thing this check must not do: it exists to catch a recolour
    # that stopped biting, not to notice that the spec grew.
    want = 2 * len(spec['variants'])
    if len(recs) != want:
        print('expected %d records in %s (a cape and a hood for each of the %d variants in the '
              'spec), found %d' % (want, os.path.relpath(OBJ, C), len(spec['variants']), len(recs)))
        return 1

    fails, tiles = [], []
    for local, f in recs:
        model = f['model'][0]                      # obj_<something>
        path = os.path.join(MDIR, model + '.ob2')
        if not os.path.exists(path):
            fails.append('%s: model %s is not on disk' % (local, model))
            continue
        pairs = []
        for n in range(1, 9):
            sv, dv = f.get('recol%ds' % n), f.get('recol%dd' % n)
            if not sv:
                break
            pairs.append((int(sv[0]), int(dv[0])))
        m = ob2render.Model(path)
        missed = []
        for sv, dv in pairs:
            sh = ob2render.rgb15_to_hsl16(sv) if sv >= 100 else sv
            if int((m.colour == sh).sum()) == 0:
                missed.append(sh)
        want = sorted(INERT) if (local.endswith('_max_hood') and pairs) else []
        if sorted(missed) != want:
            fails.append('%s: the recolour sources that match no face on %s are %s, and the spec '
                         'says they should be %s - a source that matches nothing does nothing, so '
                         'the piece renders as a plain Max cape'
                         % (local, model, sorted(missed) or 'none', want or 'none'))
        if pairs:
            m.recolour(pairs)
        # THE RECORD'S OWN INVENTORY CAMERA, not the renderer's default. A cape seen from the
        # default angle is a flat sliver: 2dxan=687 is what turns it into the icon a player sees,
        # and an icon rendered at the wrong angle tells you nothing about whether it is right.
        cam = {}
        for key, arg in (('2dxan', 'xan'), ('2dyan', 'yan'), ('2dzan', 'zan'),
                         ('2dzoom', 'zoom'), ('2dxof', 'xof'), ('2dyof', 'yof')):
            if key in f:
                cam[arg] = int(f[key][0])
        tiles.append((local, m, len(pairs), cam))
        print('  %-28s %-26s %d recolour(s), %d faces, %d inert'
              % (local, model, len(pairs), m.fcount, len(missed)))

    if out_png:
        from PIL import Image, ImageDraw
        size, cols, pad, lab = 192, 4, 8, 16
        rows = (len(tiles) + cols - 1) // cols
        im = Image.new('RGB', (cols * (size + pad) + pad, rows * (size + pad + lab) + pad),
                       (18, 18, 20))
        d = ImageDraw.Draw(im)
        for i, (local, m, npairs, cam) in enumerate(tiles):
            r, c = divmod(i, cols)
            x, y = pad + c * (size + pad), pad + r * (size + pad + lab)
            im.paste(ob2render.render(m, size=size, **cam), (x, y))
            d.text((x + 2, y + size + 3), '%s  %dr' % (local, npairs), fill=(190, 190, 195))
        im.save(out_png)
        print('wrote', out_png)

    for f in fails:
        print('  FAIL %s' % f)
    print('ALL PASS' if not fails else '%d FAILED' % len(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
