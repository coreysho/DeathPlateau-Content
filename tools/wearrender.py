#!/usr/bin/env python3
"""Render worn items together the way the CLIENT orders them, and next to how they ought to look.

WHY THIS EXISTS. ob2render.py draws one model with a z-buffer, so it always shows the right
answer. The client has no z-buffer: it paints faces in an order decided by each face's PRIORITY
(Model.method382), and where that order disagrees with the real depth you get one item bleeding
through another. A cape showing through a chestplate is exactly that, and a z-buffered render of
either model on its own cannot show it.

So this does both, side by side:

  left   the client's painter order - twelve priority buckets drawn 0..9, with buckets 10 and 11
         flushed by depth at priorities 0, 3 and 5 against the average depth of buckets 1+2, 3+4
         and 6+8. That is Model.method382 line for line.
  right  the same models z-buffered: what you should be seeing.
  below  the pixels where they differ, which is the glitch.

THE PRIORITIES THEMSELVES. Buckets 0..9 are a fixed back-to-front order, so a face at 5 is painted
over a face at 3 wherever the two overlap on screen, whatever their real depth. Bucket 10 is the
one that asks: faces in it are interleaved by their actual depth, so a surface that is behind the
body from the front and in front of it from the back - which is what a cape is - sorts correctly
from either side. Vanilla body models use it (rune platebody keeps 34 faces there); the 2006 capes
do not, because they are narrow enough that a fixed order never shows.

WHAT THE PIXEL COUNT IS AND IS NOT. It counts disagreement with depth, not badness. Priorities
exist precisely to override depth where an artist wanted it - a cape's collar belongs over the
shoulder it is physically behind - so a model can disagree and be right. The count is trustworthy
for two questions and no others:

  * does a model contradict ITSELF? A garment's back panel painting over its front is wrong in
    every case, and --scan asks exactly that, one model at a time with nothing else in the scene.
  * does a surface that must sort by depth sort by depth? A cape has to be behind you from the
    front and in front of you from behind; there is no artistic intent to protect.

For armour over a body it is weaker evidence: the body is modelled larger than some armour
encloses, so true depth shows a limb through a skirt that the player would rather not see, and
the count punishes the fixed priority that hides it. Read those numbers as a direction, confirm
them with the picture, and A/B against the old bytes before believing a change.

AND SWEEP THE WHOLE CAMERA. Pitch is clamped to 128..383 in Client.orbitCameraPitch, and a
conclusion drawn at one pitch does not hold across the range - a first pass at xan=150 alone
rated eighteen garments improvements that the full range says are not.

  python3 tools/wearrender.py --out /tmp/cape.png max_cape armadyl_chestplate bandos_tassets
  python3 tools/wearrender.py --out /tmp/cape.png --yan 1024 imbued_zamorak_cape rune_platebody
"""
import argparse, glob, importlib.util, os, re, sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'ob2render', os.path.join(HERE, '..', '..', '..', '..', '..', '..', '..',
                              'LostCityServer', 'tools', 'models', 'ob2render.py'))


def load_ob2render():
    for cand in ('C:/LostCityServer/tools/models/ob2render.py',
                 os.path.join(HERE, '..', '..', 'tools', 'models', 'ob2render.py')):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location('ob2render', cand)
            mod = importlib.util.module_from_spec(spec)
            sys.modules['ob2render'] = mod
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit('cannot find tools/models/ob2render.py')


obr = load_ob2render()


# ---------------------------------------------------------------- the configs
def obj_configs(content):
    """name -> {key: value, 'recol': [(s, d)]} for every obj in the content."""
    out = {}
    for p in sorted(glob.glob(os.path.join(content, 'scripts/**/*.obj'), recursive=True)):
        cur = None
        for line in open(p, encoding='utf-8', errors='replace'):
            s = line.strip()
            if s.startswith('//'):
                continue
            if s.startswith('[') and s.endswith(']'):
                cur = s[1:-1]
                out[cur] = {'recols': {}, 'recold': {}}
            elif cur and '=' in s:
                k, v = s.split('=', 1)
                m = re.fullmatch(r'recol(\d)([sd])', k)
                if m:
                    out[cur]['recol' + m.group(2)][int(m.group(1))] = int(v)
                else:
                    out[cur].setdefault(k, v)
    return out


def worn_models(cfg, content, woman=False):
    """The .ob2 paths an obj puts on the player, with its recolour pairs."""
    pre = 'womanwear' if woman else 'manwear'
    paths = []
    for key in (pre, pre + '2', pre + '3'):
        v = cfg.get(key)
        if not v:
            continue
        name = v.split(',')[0]
        p = os.path.join(content, 'models', 'obj', name + '.ob2')
        if os.path.exists(p):
            paths.append(p)
        else:
            print(f'  warning: {key}={name} has no .ob2', file=sys.stderr)
    pairs = [(cfg['recols'][i], cfg['recold'][i])
             for i in sorted(cfg['recols']) if i in cfg['recold']]
    return paths, pairs


# THE BODY UNDERNEATH. Measuring a cape against armour with no player inside flatters the cape:
# half of what bleeds through would have been hidden by a torso. These are the first model of each
# male kit slot in all.idk - the default body - so the test figure is a dressed player and not two
# floating shells.
BODY = ['obj_priest_gown_manwear',          # man_torso_basic
        'obj_doctor_gown_manwear2',         # man_arms_basic
        'obj_cert_drill_top_manwear3',      # man_hands
        'obj_macro_mime_legs_manwear',      # man_legs_basic
        'idk_42',                           # man_feet_basic
        'obj_feud_desert_disguise_manwear'] # man_head


# ---------------------------------------------------------------- priorities
def face_priorities(path, fcount, vcount):
    """The per-face priority array, or the model-wide one repeated. 255 in the header's priority
    byte is the client's "this model carries one per face" sentinel; anything else is the whole
    model's priority (Model.java: field1210 = -field1123 - 1)."""
    b = open(path, 'rb').read()
    o = len(b) - 18
    pri = b[o + 6]
    if pri != 255:
        return np.full(fcount, pri, np.int32)
    start = vcount + fcount          # vertex flags, then face types, then priorities
    return np.array(list(b[start:start + fcount]), np.int32)


# ---------------------------------------------------------------- merge
class Merged:
    """What ClientPlayer does with new Model(count, parts, -89): one model, every part's faces
    keeping its own priority."""

    def __init__(self, parts):
        vx, vy, vz, fa, fb, fc, col, pri, alpha, finfo = [], [], [], [], [], [], [], [], [], []
        base = 0
        for m, pr in parts:
            vx.append(m.vx); vy.append(m.vy); vz.append(m.vz)
            fa.append(m.fa + base); fb.append(m.fb + base); fc.append(m.fc + base)
            col.append(m.colour); pri.append(pr)
            alpha.append(m.alpha if m.alpha is not None else np.zeros(m.fcount, np.int32))
            finfo.append(m.finfo if m.finfo is not None else np.zeros(m.fcount, np.int32))
            base += m.vcount
        self.vx = np.concatenate(vx); self.vy = np.concatenate(vy); self.vz = np.concatenate(vz)
        self.fa = np.concatenate(fa); self.fb = np.concatenate(fb); self.fc = np.concatenate(fc)
        self.colour = np.concatenate(col); self.pri = np.concatenate(pri)
        self.alpha = np.concatenate(alpha); self.finfo = np.concatenate(finfo)
        self.vcount = len(self.vx); self.fcount = len(self.fa)

    def height(self):
        return int(max(0, -int(self.vy.min())))


# ---------------------------------------------------------------- the client's order
def client_order(pri, depth):
    """Model.method382, line for line. `depth` is each face's depth bucket, larger = farther.

    Faces are bucketed by priority. Buckets 0..9 are drawn in order. Buckets 10 and 11 hold their
    depth and are flushed - farthest first - before priority 0 while farther than the mean depth
    of buckets 1+2, before priority 3 while farther than that of 3+4, and before priority 5 while
    farther than that of 6+8; whatever is left is drawn last, in front of everything."""
    buckets = [[] for _ in range(12)]
    # The client fills walking depth from far to near, so each bucket comes out far-first.
    for f in np.argsort(-depth, kind='stable'):
        buckets[int(pri[f])].append(int(f))

    def mean(a, b):
        n = len(buckets[a]) + len(buckets[b])
        if n == 0:
            return 0
        return (sum(depth[f] for f in buckets[a]) + sum(depth[f] for f in buckets[b])) / n

    m12, m34, m68 = mean(1, 2), mean(3, 4), mean(6, 8)
    stream = buckets[10] + buckets[11]            # the client walks 10 then 11, both far-first
    si = 0
    out = []

    def flush(limit):
        nonlocal si
        while si < len(stream) and depth[stream[si]] > limit:
            out.append(stream[si]); si += 1

    for p in range(10):
        if p == 0:
            flush(m12)
        elif p == 3:
            flush(m34)
        elif p == 5:
            flush(m68)
        out.extend(buckets[p])
    out.extend(stream[si:])
    return out


# ---------------------------------------------------------------- render
def project(m, size, xan, yan, zoom, xof=0, yof=0):
    SIN, COS = obr.SIN, obr.COS
    sx, sy, sz = m.vx.astype(np.int64), m.vy.astype(np.int64), m.vz.astype(np.int64)
    s_y, c_y = SIN[yan & 2047], COS[yan & 2047]
    s_x, c_x = SIN[xan & 2047], COS[xan & 2047]
    if yan:
        t = (s_y * sz + c_y * sx) >> 16
        sz = (c_y * sz - s_y * sx) >> 16
        sx = t
    a5 = m.height() // 2 + ((s_x * zoom) >> 16) + yof
    a6 = yof + ((c_x * zoom) >> 16)
    v18 = (a5 * s_x + a6 * c_x) >> 16
    X = xof + sx; Y = a5 + sy; Z = a6 + sz
    dep = ((s_x * Y + c_x * Z) >> 16)
    dep = np.where(dep <= 0, 1, dep)
    vy_ = ((c_x * Y - s_x * Z) >> 16)
    sc = size / 32.0
    return (((X * 512.0) / dep) * sc + size / 2,
            ((vy_ * 512.0) / dep) * sc + size / 2,
            dep - v18)


CULL = 1


def draw(m, size, xan, yan, zoom, painter, bg=(28, 28, 32)):
    px, py, pz = project(m, size, xan, yan, zoom)
    if obr.PALETTE is None:
        obr.PALETTE = obr.build_palette()
    light = obr.face_lightness(m)
    fdepth = (pz[m.fa] + pz[m.fb] + pz[m.fc]) / 3.0

    if painter:
        order = client_order(m.pri, fdepth)
        zbuf = None
    else:
        order = list(np.argsort(-fdepth))
        zbuf = np.full((size, size), 1 << 30, np.float64)

    img = np.zeros((size, size, 3), np.uint8)
    img[:] = bg
    for i in order:
        if (m.finfo[i] & 2) != 0 or m.alpha[i] >= 255:
            continue
        ia, ib, ic = m.fa[i], m.fb[i], m.fc[i]
        x0, y0, x1, y1, x2, y2 = px[ia], py[ia], px[ib], py[ib], px[ic], py[ic]
        # BACKFACE CULL, which method382 does with the same signed area before it buckets a face
        # at all. Without it the painter pass paints the inside of every model and the whole
        # figure comes out black.
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if area * CULL <= 0:
            continue
        rgb = obr.PALETTE[obr.adjust_lightness(int(m.colour[i]), light[i])]
        minx, maxx = int(max(0, min(x0, x1, x2))), int(min(size - 1, max(x0, x1, x2)))
        miny, maxy = int(max(0, min(y0, y1, y2))), int(min(size - 1, max(y0, y1, y2)))
        if minx > maxx or miny > maxy:
            continue
        gx, gy = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
        w0 = (x1 - x0) * (gy - y0) - (gx - x0) * (y1 - y0)
        w1 = (x2 - x1) * (gy - y1) - (gx - x1) * (y2 - y1)
        w2 = (x0 - x2) * (gy - y2) - (gx - x2) * (y0 - y2)
        inside = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
        if not inside.any():
            continue
        if zbuf is None:
            img[miny:maxy + 1, minx:maxx + 1][inside] = rgb
        else:
            z = fdepth[i]
            sub = zbuf[miny:maxy + 1, minx:maxx + 1]
            hit = inside & (z < sub)
            sub[hit] = z
            img[miny:maxy + 1, minx:maxx + 1][hit] = rgb
    return img


def label(img, text):
    from PIL import ImageDraw
    im = Image.fromarray(img)
    ImageDraw.Draw(im).text((4, 2), text, fill=(210, 210, 210))
    return im


def scan(content, size=96, angles=(0, 512, 1024, 1536)):
    """Every worn model on its own, in the client's order against true depth.

    A model whose faces all share one priority is drawn in pure depth order by construction, so it
    can never disagree with itself - the only models that can are the ones carrying per-face
    priorities, and a big disagreement there means the split is fighting its own geometry rather
    than shaping it. The comparison is against the same model flattened to one bucket, which is
    the best any single model can do alone."""
    cfgs = obj_configs(content)
    seen = {}
    for name, d in cfgs.items():
        v = d.get('manwear')
        if not v:
            continue
        p = os.path.join(content, 'models', 'obj', v.split(',')[0] + '.ob2')
        if os.path.exists(p):
            seen.setdefault(p, name)
    rows = []
    for p, name in sorted(seen.items()):
        try:
            mdl = obr.Model(p)
        except Exception:
            continue
        pri = face_priorities(p, mdl.fcount, mdl.vcount)
        if len(set(pri.tolist())) < 2:
            continue                      # one bucket already: depth order by construction
        a = b = 0
        for y in angles:
            m1 = Merged([(mdl, pri)])
            m2 = Merged([(mdl, np.full(mdl.fcount, 10, np.int32))])
            for m, acc in ((m1, 'a'), (m2, 'b')):
                c = draw(m, size, 150, y, 1500, painter=True)
                tr = draw(m, size, 150, y, 1500, painter=False)
                n = int((c != tr).any(axis=2).sum())
                if acc == 'a':
                    a += n
                else:
                    b += n
        if a > b:
            rows.append((a - b, a, b, name, os.path.basename(p), sorted(set(pri.tolist()))))
    rows.sort(reverse=True)
    print(f'{"gap":>7} {"shipped":>8} {"flat":>6}  obj / model / priorities')
    for gap, a, b, name, mdl, ps in rows[:40]:
        print(f'{gap:>7} {a:>8} {b:>6}  {name:<28} {mdl:<40} {ps}')
    print()
    print(f'{len(rows)} worn models disagree with their own depth more than one flat bucket would')


def body_parts(content):
    parts = []
    for name in BODY:
        for sub in ('obj', 'idk'):
            p = os.path.join(content, 'models', sub, name + '.ob2')
            if os.path.exists(p):
                mdl = obr.Model(p)
                parts.append((mdl, face_priorities(p, mdl.fcount, mdl.vcount)))
                break
    return parts


def scan_situ(content, slot, flat, size=96, angles=(0, 512, 1024, 1536)):
    """Every model worn in one slot, on a dressed body, as shipped against one flat bucket.

    Alone, any flat bucket scores the same - a single bucket is pure depth order. In situ it is
    not: the bucket decides how the garment sorts against the BODY underneath, and the only
    bucket that depth-sorts against a body part is the one that body part is already in. The
    legs of the default kit are priority 1, which is also what the vanilla platelegs use."""
    cfgs = obj_configs(content)
    body = body_parts(content)
    seen = {}
    for name, d in cfgs.items():
        if d.get('wearpos') != slot:
            continue
        v = d.get('manwear')
        if not v:
            continue
        p = os.path.join(content, 'models', 'obj', v.split(',')[0] + '.ob2')
        if os.path.exists(p):
            seen.setdefault(p, name)
    rows = []
    for p, name in sorted(seen.items()):
        try:
            mdl = obr.Model(p)
        except Exception:
            continue
        pri = face_priorities(p, mdl.fcount, mdl.vcount)
        if len(set(pri.tolist())) < 2 and pri[0] == flat:
            continue                                  # already there
        # ALREADY DEPTH-SORTED, LEAVE IT. A model using bucket 10 or 11 has its faces interleaved
        # by real depth, which is a better answer than any fixed bucket; flattening those is what
        # every regression in the first torso sweep turned out to be.
        if set(pri.tolist()) & {10, 11}:
            continue
        a = b = 0
        for y in angles:
            for use, acc in ((pri, 'a'), (np.full(mdl.fcount, flat, np.int32), 'b')):
                m = Merged(body + [(mdl, use)])
                c = draw(m, size, 150, y, 1500, painter=True)
                tr = draw(m, size, 150, y, 1500, painter=False)
                n = int((c != tr).any(axis=2).sum())
                if acc == 'a':
                    a += n
                else:
                    b += n
        rows.append((a - b, a, b, name, os.path.basename(p), sorted(set(pri.tolist()))))
    rows.sort(reverse=True)
    better = [r for r in rows if r[0] > 0]
    worse = [r for r in rows if r[0] < 0]
    print(f'{"gain":>7} {"shipped":>8} {"flat":>6}  obj / model / priorities')
    for gap, a, b, name, mdl, ps in rows:
        if abs(gap) < 200:
            continue
        print(f'{gap:>7} {a:>8} {b:>6}  {name:<30} {mdl:<42} {ps}')
    print()
    print(f'{len(rows)} models in slot {slot}: {len(better)} better at flat {flat}, '
          f'{len(worse)} worse, {len(rows)-len(better)-len(worse)} unchanged')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('objs', nargs='*', help='obj config names, drawn together')
    ap.add_argument('--content', default=os.path.join(HERE, '..'))
    ap.add_argument('--out', default='/tmp/wearrender.png')
    ap.add_argument('--size', type=int, default=260)
    ap.add_argument('--xan', type=int, default=150)
    ap.add_argument('--yan', type=int, default=0, help='0 faces you, 1024 is from behind')
    ap.add_argument('--zoom', type=int, default=1500)
    ap.add_argument('--cull', type=int, default=1, choices=(1, -1),
                    help='winding sign kept; -1 if the figure comes out inside-out')
    ap.add_argument('--woman', action='store_true')
    ap.add_argument('--body', action='store_true', help='draw the default male kit underneath')
    ap.add_argument('--repri', action='append', default=[], metavar='OBJ=N',
                    help='try an obj at priority N without editing the model, e.g. max_cape=10')
    ap.add_argument('--scan-situ', metavar='SLOT=PRI',
                    help='every model in a slot, on a body, shipped against one flat bucket')
    ap.add_argument('--scan', action='store_true',
                    help='sweep every worn model for a priority split that fights its own geometry')
    a = ap.parse_args()

    if a.scan:
        scan(a.content)
        return
    if a.scan_situ:
        slot, flat = a.scan_situ.split('=')
        scan_situ(a.content, slot, int(flat))
        return

    global CULL
    CULL = a.cull
    repri = {}
    for r in a.repri:
        k, v = r.split('=')
        repri[k] = int(v)
    cfgs = obj_configs(a.content)
    parts = []
    if a.body:
        for name in BODY:
            # idk kit parts live in models/idk, worn-item meshes in models/obj, and the body uses
            # both. Looking in one place only lost the feet and the head without saying so.
            for sub in ('obj', 'idk'):
                p = os.path.join(a.content, 'models', sub, name + '.ob2')
                if os.path.exists(p):
                    break
            else:
                raise SystemExit(f'body part {name} has no .ob2 in models/obj or models/idk')
            mdl = obr.Model(p)
            parts.append((mdl, face_priorities(p, mdl.fcount, mdl.vcount)))
    for name in a.objs:
        if name not in cfgs:
            raise SystemExit(f'no such obj: {name}')
        paths, pairs = worn_models(cfgs[name], a.content, a.woman)
        if not paths:
            print(f'  warning: {name} puts nothing on', file=sys.stderr)
        for p in paths:
            mdl = obr.Model(p)
            if pairs:
                mdl.recolour(pairs)
            pri = face_priorities(p, mdl.fcount, mdl.vcount)
            if name in repri:
                pri = np.full(mdl.fcount, repri[name], np.int32)
            print(f'  {name:<26} {os.path.basename(p):<38} {mdl.fcount:>4}f '
                  f'pri={sorted(set(pri.tolist()))}')
            parts.append((mdl, pri))
    if not parts:
        raise SystemExit('nothing to draw')
    m = Merged(parts)
    print(f'  merged: {m.vcount} vertices, {m.fcount} faces')

    c = draw(m, a.size, a.xan, a.yan, a.zoom, painter=True)
    t = draw(m, a.size, a.xan, a.yan, a.zoom, painter=False)
    d = np.zeros_like(c)
    diff = (c != t).any(axis=2)
    d[diff] = (255, 40, 40)
    print(f'  pixels the client paints wrong: {int(diff.sum())}')

    sheet = Image.new('RGB', (a.size * 3 + 16, a.size), (18, 18, 20))
    sheet.paste(label(c, 'client order'), (0, 0))
    sheet.paste(label(t, 'correct (z-buffered)'), (a.size + 8, 0))
    sheet.paste(label(d, 'difference'), (a.size * 2 + 16, 0))
    sheet.save(a.out)
    print('  ' + a.out)


if __name__ == '__main__':
    main()
