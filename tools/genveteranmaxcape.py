#!/usr/bin/env python3
"""The Veteran max cape and hood: the Max cape's own models, repainted bronze, with the Veteran
device struck into the back of the cape.

WHY MODELS RATHER THAN recol= LINES, which is how eleven of the fourteen variants do it. The
recolour alone is a config job and was one until the device was asked for - and a device is
GEOMETRY. An obj config can repaint a model; it cannot add a triangle to one. So the pairs are
applied to the mesh here and written out as models of their own, the way the imbued ancient max
cape did when it hit the same wall from the other side (twelve recolour pairs into a six-pair
config). tools/genmaxvariants.py then names these through the variant's `models` key.

THE BRONZE IS THE VETERAN CAPE'S OWN RAMP. An hsl16 is (hue>>2)<<10 | (sat>>5)<<7 | light>>1, and
obj_veteran_cape_manwear's cloth is one ramp - hue 4, saturation 4 - at several lightnesses. The
Max cape's recolour sources are likewise one red ramp (hue 0), so each destination keeps its
SOURCE'S LIGHTNESS and takes the veteran hue and saturation: the shading survives instead of
being flattened to one flat bronze. The gold trim is deliberately untouched, which is what a max
cape variant is - a Saradomin max cape is blue cloth under the same gold.

THE DEVICE'S VERTEX LABELS COME FROM THE CLOTH UNDER EACH ONE, and that is the one place this
parts company with tools/models/genveterancape.py. A worn model is skinned to the player through
vertex labels, and that generator gives the whole device a SINGLE label - which is right there,
because the attack cape's emblem sits on one label's worth of cloth. The Max cape's back is not
like that: it is a patchwork of labels 9, 11, 14, 15 and 16 interleaved so finely that the largest
square of one label anywhere on the midline is twelve units across, against a device of
twenty-four. A one-label device there would move rigidly while the cloth under it moved five ways,
and tear off in exactly the poses nobody renders. Taking each vertex's label from the cloth
beneath it makes the device deform with the cape instead, which is what something printed on
fabric does.

THE DEPTH IS STILL CONSTANT, though, and for the reason that generator records: a device that
follows the cloth's curve gets a different normal per triangle, and because model coordinates are
whole numbers a gentle slope quantises into a staircase of them. One depth for the whole device
gives one normal. It is measured over the device's OWN FOOTPRINT rather than over the cape, since
the frontmost point of the whole cape is the hem and a device placed there floats clear of its own
backing - which is a fault this build has already shipped once.

  python3 tools/genveteranmaxcape.py             # report
  python3 tools/genveteranmaxcape.py --apply
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)
for cand in (r'C:\LostCityServer\tools\models', os.path.join(CONTENT, '..', 'tools', 'models')):
    if os.path.isdir(cand):
        sys.path.insert(0, cand)
        break
from osrs2ob2 import parse_ob2, encode, roundtrip        # noqa: E402
from animconv474 import pack_append                      # noqa: E402
import dpglyph                                           # noqa: E402

# hsl16 -> hsl16. Source lightness kept, veteran hue 4 and saturation 4 applied. The darkest cape
# shade would land on lightness 16, which has no rgb15 that converts back to it - irrelevant here,
# since nothing is written through a config, but it is kept at 18 so the baked models and the
# recolour pairs recorded in tools/maxcapevariantspec.json describe the same cape.
CAPE = {668: 4636, 675: 4643, 784: 4626, 815: 4655, 673: 4641}
HOOD = {815: 4655, 784: 4626, 675: 4643, 685: 4653, 914: 4626, 945: 4657}

# THE CLOTH IS LOOKED FOR BY ITS NEW COLOUR, because the repaint happens first: by the time the
# device is placed, the five red shades the recolour named are gone and the bronze is there
# instead. Both sets are accepted so the order of the two steps cannot silently matter.
def cloth_of(table):
    return set(table) | set(table.values())

# The device: dark on bronze, with a lighter rim just behind it so it reads as struck into the
# cloth rather than painted on. The Veteran cape's own two colours, so the rank reads as one thing
# whichever cape a player is wearing.
EMBLEM_RGB = (58, 32, 14)
EMBLEM_RIM_RGB = (206, 142, 84)

# Where the device goes on each cape model, and how big.
#
#   plane  - which two axes the back lies in; the third is depth
#   centre - (across, up) in that plane, measured off the surface map in the docstring above
#   size   - the device's width in model units
#   mirror/flip - the glyph is drawn for a viewer; each mesh is seen from its own side
#
# The worn models are seen from behind (mirror), the inventory model lies on its face (flip).
# Every reflection also reverses winding, which orient() puts back.
CAPES = {
    # z 8, not the 23 that proportion with the worn model suggested: the inventory mesh is
    # cut away at the sides higher up, and a 24-unit footprint there runs off the cloth.
    'obj_max_cape': dict(plane='xz', centre=(0, 6), size=24.0, mirror=False, flip=True),
    # y -112 is the highest centre at which a 24-unit footprint is clear cloth on BOTH worn
    # meshes - the woman's cape is cut differently and -115 ran off it. One number for the two, so
    # the cape is the same cape whoever wears it.
    'obj_max_cape_manwear': dict(plane='xy', centre=(0, -112), size=24.0, mirror=True, flip=False),
    'obj_max_cape_womanwear': dict(plane='xy', centre=(0, -112), size=24.0, mirror=True, flip=False),
}

PARTS = ([('obj_max_cape%s' % s, 'obj_veteran_max_cape%s' % s, CAPE)
          for s in ('', '_manwear', '_womanwear')] +
         [('obj_max_hood%s' % s, 'obj_veteran_max_hood%s' % s, HOOD)
          for s in ('', '_manwear', '_womanwear', '_manhead', '_womanhead')])


def hsl24to16(h, s, l):
    if l > 243: s >>= 4
    elif l > 217: s >>= 3
    elif l > 192: s >>= 2
    elif l > 179: s >>= 1
    return (((h & 0xff) >> 2) << 10) + ((s >> 5) << 7) + (l >> 1)


def rgb_to_hsl16(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mn, mx = min(r, g, b), max(r, g, b)
    h = s = 0.0
    l = (mn + mx) / 2.0
    if mn != mx:
        s = (mx - mn) / (mx + mn) if l < 0.5 else (mx - mn) / (2.0 - mx - mn)
        if r == mx: h = (g - b) / (mx - mn)
        elif g == mx: h = (b - r) / (mx - mn) + 2.0
        else: h = (r - g) / (mx - mn) + 4.0
    h /= 6.0
    return hsl24to16(int(h * 256.0), max(0, min(255, int(s * 256.0))), max(0, min(255, int(l * 256.0))))


def orient(tris, spec):
    """Turn a device to face the way this mesh is seen from.

    EVERY REFLECTION ALSO REVERSES WINDING, so an odd number of them needs the triangles reversed
    or the client culls the whole device away.
    """
    refl = 0
    if spec['mirror']:
        tris = [[(1.0 - x, y) for x, y in t] for t in tris]
        refl += 1
    if spec['flip']:
        tris = [[(x, 1.0 - y) for x, y in t] for t in tris]
        refl += 1
    return [list(reversed(t)) for t in tris] if refl % 2 else tris


def axes(plane):
    """(across, up, depth, sign). sign is +1 where 'outward' means a larger coordinate."""
    return ('vx', 'vy', 'vz', 1) if plane == 'xy' else ('vx', 'vz', 'vy', -1)


def back_faces(m, cloth, A, U, D, sign):
    """The cloth faces that face the viewer, as triangles in the (across, up) plane.

    Outward is decided by the signed area in that projection: a face wound the other way is the
    cape's inside, and sampling it would put the device on the lining.

    THE SIGN IS ALREADY IN THE PROJECTION. Each point below is (across, up, sign * depth), so the
    third axis always increases outward whichever mesh this is, and the test is simply "wound
    anticlockwise". Testing the sign AGAIN here - which this did at first - cancels it out on the
    inventory model, whose sign is -1: the device was placed against the lining, finished up
    behind the outer cloth, and the icon showed a plain bronze cape with nothing on it.
    """
    out = []
    for i in range(m['fcount']):
        if m['colour'][i] not in cloth:
            continue
        a, b, c = m['fa'][i], m['fb'][i], m['fc'][i]
        p = [(m[A][v], m[U][v], sign * m[D][v]) for v in (a, b, c)]
        s = ((p[1][0] - p[0][0]) * (p[2][1] - p[0][1])
             - (p[1][1] - p[0][1]) * (p[2][0] - p[0][0]))
        if s <= 0:
            continue
        labs = [m['vlab'][v] for v in (a, b, c)] if m['vlab'] is not None else None
        out.append((p, m['pri'][i], labs))
    return out


def under(tris, x, u):
    """The frontmost cloth at (across, up): (depth, priority, label) - or None if there is none."""
    best = None
    for p, pri, labs in tris:
        (x0, u0, d0), (x1, u1, d1), (x2, u2, d2) = p
        den = (u1 - u2) * (x0 - x2) + (x2 - x1) * (u0 - u2)
        if den == 0:
            continue
        l0 = ((u1 - u2) * (x - x2) + (x2 - x1) * (u - u2)) / den
        l1 = ((u2 - u0) * (x - x2) + (x0 - x2) * (u - u2)) / den
        l2 = 1.0 - l0 - l1
        if l0 < -0.001 or l1 < -0.001 or l2 < -0.001:
            continue
        d = l0 * d0 + l1 * d1 + l2 * d2
        if best is None or d > best[0]:
            lab = max(set(labs), key=labs.count) if labs else 0
            best = (d, pri, lab)
    return best


def add_device(m, cloth, spec, verbose=True):
    A, U, D, sign = axes(spec['plane'])
    tris = back_faces(m, cloth, A, U, D, sign)
    if not tris:
        raise SystemExit('found no outward-facing cloth to put the device on')

    ca, cu = spec['centre']
    size = spec['size']
    half = size / 2.0

    # The footprint, sampled on a grid. Every point of it has to be cloth, or the device is partly
    # over the gold trim or off the edge of the cape and this is the wrong place for it.
    hits, misses = [], 0
    # FIFTEEN, not nine. A nine-point grid passed a footprint on the inventory mesh that a
    # finer one found a hole in - the sample points simply stepped over it.
    steps = 15
    for i in range(steps):
        for j in range(steps):
            x = ca - half + size * i / (steps - 1.0)
            u = cu - half + size * j / (steps - 1.0)
            h = under(tris, x, u)
            if h is None:
                misses += 1
            else:
                hits.append(h)
    if misses:
        raise SystemExit('%d of %d points under the device are not cloth - move it'
                         % (misses, steps * steps))

    # ONE DEPTH, AND IT IS THE DEPTH AT THE DEVICE'S OWN CENTRE.
    #
    # The Veteran cape takes the frontmost point of the emblem it replaces, and that is right
    # there because the attack cape's emblem sits on flat cloth. This cape has no flat part: it
    # curves steadily away from the hem, about one unit of depth for every six of height, so the
    # frontmost point of a 24-unit footprint is four units proud of the far edge of it. Measured
    # that way the device stood four units off the top of its own backing.
    #
    # Flush at the centre halves that: the upper half sits just inside the cloth, the lower half
    # just outside, and neither is ever more than about two units away. Being inside the cloth
    # costs nothing, because priorities 0..9 are drawn in strict ascending order BEFORE depth is
    # considered - a device above the cloth's priority paints over it however deep it sits.
    centre = under(tris, ca, cu)
    depth = centre[0] if centre else max(h[0] for h in hits)
    # ABOVE THE WHOLE CAPE, not just above the cloth under the device. The gold trim is priority 5
    # and some of the cloth is too, so a rim at 5 would be painted over by whichever of them the
    # face order happened to put last. The attack cape carries its own emblem two above its cloth
    # and draws correctly in game, which is the precedent for going this high on a cape at all.
    top = max(m['pri']) if m['pri'] else 0
    rim_pri = top + 1
    ink_pri = top + 2

    if verbose:
        lo, hi = min(h[0] for h in hits), max(h[0] for h in hits)
        print('    device %.0f wide at (%d, %d), depth %.1f, cloth %.1f..%.1f '
              '(sits %.1f inside to %.1f proud), priority %d/%d'
              % (size, ca, cu, depth, lo, hi, hi - depth, depth - lo, rim_pri, ink_pri))
        print('    labels under it: %s' % sorted({h[2] for h in hits}))

    cache = {}

    def vert(nx, ny, lift):
        key = (round(nx, 4), round(ny, 4), lift)
        if key in cache:
            return cache[key]
        x = ca + (nx - 0.5) * size
        u = cu + (ny - 0.5) * size
        h = under(tris, x, u)
        pos = {A: round(x), U: round(u), D: round(sign * (depth + lift))}
        m['vx'].append(pos['vx']); m['vy'].append(pos['vy']); m['vz'].append(pos['vz'])
        if m['vlab'] is not None:
            # THE LABEL OF THE CLOTH UNDER THIS VERTEX, not one label for the whole device.
            m['vlab'].append(h[2] if h else 0)
        m['vcount'] += 1
        cache[key] = m['vcount'] - 1
        return cache[key]

    def face(a, b, c, colour, priority):
        m['fa'].append(a); m['fb'].append(b); m['fc'].append(c)
        m['colour'].append(colour); m['pri'].append(priority)
        if m['flab'] is not None: m['flab'].append(0)
        if m['alpha'] is not None: m['alpha'].append(0)
        if m['finfo'] is not None: m['finfo'].append(0)
        m['fcount'] += 1

    rim = orient(dpglyph.veteran(dilate=1)[0], spec)
    ink = orient(dpglyph.veteran()[0], spec)
    for t in rim:
        a, b, c = (vert(x, y, 0.0) for x, y in t)
        face(a, b, c, rgb_to_hsl16(*EMBLEM_RIM_RGB), rim_pri)
    for t in ink:
        a, b, c = (vert(x, y, 1.0) for x, y in t)
        face(a, b, c, rgb_to_hsl16(*EMBLEM_RGB), ink_pri)
    return len(rim) + len(ink)


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
            raise SystemExit('%s.ob2 is missing' % src)
        m = parse_ob2(open(path, 'rb').read())
        hit = sum(1 for c in m['colour'] if c in table)
        m['colour'] = [table.get(c, c) for c in m['colour']]
        print('  %-36s %4d faces, %3d repainted' % (dst, m['fcount'], hit))
        if src in CAPES:
            added = add_device(m, cloth_of(table), CAPES[src])
            print('    %d device faces, %d total' % (added, m['fcount']))
        b = encode(m)
        ok, why = roundtrip(b, m)
        if not ok:
            raise SystemExit('%s does not survive a round trip: %s' % (dst, why))
        if a.apply:
            open(os.path.join(mdir, dst + '.ob2'), 'wb').write(b)
            written.append(dst)
    if a.apply:
        ids, _ = pack_append(os.path.join(a.content, 'pack', 'model.pack'), written)
        for n in written:
            print('  model.pack %s = %s' % (ids[n], n))
    else:
        print('  dry run - pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
