#!/usr/bin/env python3
"""Every map square survives the packer's one-byte fields, and names a floor that exists.

    python3 tools/mapcheck.py            every square
    python3 tools/mapcheck.py 42_51      one of them

WHY THIS EXISTS. tools/pack/map/Pack.js writes a tile as single bytes - p1(opcode), p1(overlay),
p1(flags + 49), p1(underlay + 81), p1(height) - and the client walks them back with 1-byte
opcodes. A value that does not fit is truncated on the way out, so the client reads an opcode
that was never written and builds no terrain for the WHOLE square. What that looks like in game
is black ground everywhere and every loc still drawing, because locs are a separate file.

Witchaven shipped exactly that: 458 sea tiles carrying overlay 443 against a flo.pack that ends
at 175. Nothing caught it - not rs2check, not the build, not a walked quest manifest, because none
of them is the renderer. It took two deploys to find and this check would have found it before the
first one.

Three faults are reported:

  OVERFLOW   a field that cannot fit in a byte. Fatal for the square.
  MISMATCH   the tile does not decode back to what was written. Fatal.
  NO FLOOR   an overlay or underlay naming a flo id that is not in flo.pack. The client indexes
             off the end of its table.

A fourth is a warning rather than a failure:

  UNDERLAY-IS-OVERLAY   underlays and overlays share one table here, so a tile can name a floor
             written to be an overlay. It still DRAWS - it takes that floor's colour - but that
             colour is rarely the one the source cache meant, so it is usually a graft that passed
             an id through without translating it. 126 tiles in content predate this check, most
             of them Keldagrim's water, and that is the evidence it renders rather than blanking:
             nobody has ever reported black ground there.
"""
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)
MAPS = os.path.join(CONTENT, 'maps')

FIELDS = (('h', r'\bh(\d+)'), ('o', r'\bo(\d+)'), ('shape', r'\bs(\d+)'),
          ('rot', r'\br(\d+)'), ('f', r'\bf(\d+)'), ('u', r'\bu(\d+)'))


def floors():
    """(every flo id, the ids that are overlays) - underlays and overlays share one table."""
    ids, overlay = set(), set()
    names = {}
    for line in io.open(os.path.join(CONTENT, 'pack', 'flo.pack'), encoding='utf-8'):
        if '=' in line:
            i, n = line.strip().split('=', 1)
            ids.add(int(i))
            names[int(i)] = n
    cfg, cur = {}, None
    for path in glob.glob(os.path.join(CONTENT, 'scripts', '**', '*.flo'), recursive=True):
        for line in io.open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^\[([a-z0-9_]+)\]', line.strip())
            if m:
                cur = m.group(1)
                cfg[cur] = {}
            elif cur and '=' in line:
                k, v = line.strip().split('=', 1)
                cfg[cur][k] = v
    for i, n in names.items():
        if (cfg.get(n) or {}).get('overlay') == 'yes':
            overlay.add(i)
    return ids, overlay, names


def encode(t):
    """Exactly what tools/pack/map/Pack.js writes for one tile."""
    out = []
    h = t['h'] if t['h'] != -1 else 0
    if h == 0 and t['o'] == -1 and t['f'] == -1 and t['u'] == -1:
        return [0]
    if t['o'] != -1:
        op = 2
        if t['shape'] != -1:
            op += t['shape'] << 2
        if t['rot'] != -1:
            op += t['rot']
        out += [op, t['o']]
    if t['f'] != -1:
        out.append(t['f'] + 49)
    if t['u'] != -1:
        out.append(t['u'] + 81)
    if h != 0:
        out += [1, h]
    else:
        out.append(0)
    return out


def decode(b):
    """And exactly how the client walks it back."""
    t = {'h': 0, 'o': -1, 'shape': -1, 'rot': -1, 'f': -1, 'u': -1}
    p = 0
    while p < len(b):
        a = b[p]
        p += 1
        if a == 0:
            return t
        if a == 1:
            t['h'] = b[p]
            return t
        if a <= 49:
            t['o'] = b[p]
            p += 1
            t['shape'] = (a - 2) >> 2
            t['rot'] = (a - 2) & 3
        elif a <= 81:
            t['f'] = a - 49
        else:
            t['u'] = a - 81
    return t


def check(path, ids, overlay, names):
    reg = os.path.basename(path)[1:-4]
    txt = io.open(path, encoding='utf-8', errors='replace').read()
    if '==== MAP ====' not in txt:
        return []
    sec = txt.split('==== MAP ====')[1].split('==== LOC')[0]
    bad = []
    seen_under_overlay = {}
    for m in re.finditer(r'^(\d) (\d+) (\d+):\s*(.*)$', sec, re.M):
        lv, x, z, rest = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        t = {k: -1 for k, _ in FIELDS}
        for k, pat in FIELDS:
            g = re.search(pat, rest)
            if g:
                t[k] = int(g.group(1))
        where = 'm%s L%d %d,%d' % (reg, lv, x, z)
        raw = encode(t)
        if any(v > 255 or v < 0 for v in raw):
            bad.append(('OVERFLOW', where, 'writes %s' % raw))
            continue
        back = decode(bytes(raw))
        if back['o'] != t['o'] or back['u'] != t['u'] or back['h'] != max(t['h'], 0):
            bad.append(('MISMATCH', where, '%s -> %s' % (t, back)))
        if t['o'] != -1 and (t['o'] - 1) not in ids:
            bad.append(('NO FLOOR', where, 'overlay %d means flo %d, which is not in flo.pack'
                        % (t['o'], t['o'] - 1)))
        if t['u'] != -1:
            if t['u'] not in ids:
                bad.append(('NO FLOOR', where, 'underlay %d is not in flo.pack' % t['u']))
            elif t['u'] in overlay:
                seen_under_overlay.setdefault(t['u'], 0)
                seen_under_overlay[t['u']] += 1
    for u, n in sorted(seen_under_overlay.items()):
        bad.append(('UNDERLAY-IS-OVERLAY', 'm%s' % reg,
                    'underlay %d is %s, written as an overlay - %d tile(s) take its colour,'
                    ' which is probably not the one intended'
                    % (u, names.get(u, '?'), n)))
    return bad


def main():
    ids, overlay, names = floors()
    want = sys.argv[1:] 
    paths = sorted(glob.glob(os.path.join(MAPS, 'm*.jm2')))
    if want:
        paths = [p for p in paths if os.path.basename(p)[1:-4] in want]
    fatal = 0
    warn = 0
    for p in paths:
        for kind, where, why in check(p, ids, overlay, names):
            if kind == 'UNDERLAY-IS-OVERLAY':
                warn += 1
                print('WARN  %-20s %s  %s' % (kind, where, why))
            else:
                fatal += 1
                if fatal <= 40:
                    print('FAIL  %-20s %s  %s' % (kind, where, why))
    print('%d map square(s): %d fatal, %d warning(s)' % (len(paths), fatal, warn))
    return 1 if fatal else 0


if __name__ == '__main__':
    sys.exit(main())
