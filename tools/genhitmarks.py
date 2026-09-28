#!/usr/bin/env python3
"""Build sprites/hitmarks.png: 377's five hitsplats followed by three of Old School's.

    0 block       377's own (blue)
    1 damage      377's own (red)
    2 poison      377's own (green)
    3 disease     377's own, the blocked-disease one (orange)
    4 disease     377's own (yellow)
    5 venom       OSRS sprite 1632 (OSRS hitsplat 5) - the dark teal splat
    6 heal        OSRS sprite 1629 (OSRS hitsplat 6) - the purple cross
    7 max hit     OSRS sprite 3571 (OSRS hitsplat 43, DAMAGE_MAX_ME, in its default style) - the red
                  splat with the gold rim

Old School numbers its hitsplats 0-6 in the same order 377 did and carried on from there, so venom and
heal keep their Old School numbers here; the max hit is Old School's 43 and takes the next free slot.
The sprite ids come from the OSRS hitsplat configs (config archive 32): each names a single
"background" sprite, and every one of these is a 25x25 canvas - the size 377's own are, so they drop
into the sheet's 25x25 grid (meta/hitmarks.opt) as they are.

The first five cells are copied out of the committed sheet, not regenerated, so running this again
only ever rewrites 5-7. Magenta (0xFF00FF) is the packer's transparent colour; a source pixel that is
exactly magenta is nudged to 0xFE00FE.

The engine's HitType (src/engine/entity/HitType.ts), scripts/skill_combat/configs/hitmark.constant
and the client's loader (Client.java, `hitmarks`) all count on this order.

    python tools/genhitmarks.py [--cache "C:/LostCityServer/caches/newest cache"]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)
SHEET = os.path.join(CONTENT, 'sprites', 'hitmarks.png')
TOOLS = 'C:/LostCityServer/tools/models'   # flatcache.py and osrssprite.py
CELL = 25
KEEP = 5                                   # 377's own, copied through untouched
OSRS = [(1632, 'venom'), (1629, 'heal'), (3571, 'max hit')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default='C:/LostCityServer/caches/newest cache')
    args = ap.parse_args()

    sys.path.insert(0, TOOLS)
    from flatcache import Store
    import osrssprite
    from PIL import Image

    old = Image.open(SHEET).convert('RGBA')
    if old.size[0] < CELL * KEEP:
        sys.exit(f'{SHEET} has fewer than {KEEP} cells')
    sheet = Image.new('RGBA', (CELL * (KEEP + len(OSRS)), CELL), (255, 0, 255, 255))
    sheet.paste(old.crop((0, 0, CELL * KEEP, CELL)), (0, 0))

    st = Store(args.cache)
    for i, (gid, what) in enumerate(OSRS):
        g = osrssprite.decode(st.read(8, gid))
        if g is None:
            sys.exit(f'sprite {gid} ({what}) did not decode')
        if g['width'] != CELL or g['height'] != CELL:
            sys.exit(f'sprite {gid} ({what}) is a {g["width"]}x{g["height"]} canvas, not {CELL}x{CELL}')
        s, pal = g['sprites'][0], g['palette']
        x0 = CELL * (KEEP + i) + s['ox']
        y0 = s['oy']
        for k, v in enumerate(s['px']):
            if v == 0:
                continue
            c = pal[v]
            rgb = (c >> 16 & 255, c >> 8 & 255, c & 255)
            if rgb == (255, 0, 255):
                rgb = (254, 0, 254)
            sheet.putpixel((x0 + k % s['w'], y0 + k // s['w']), rgb + (255,))
        print(f'cell {KEEP + i}: OSRS sprite {gid} ({what})')

    sheet.save(SHEET)
    print(f'wrote {SHEET} ({sheet.size[0]}x{sheet.size[1]})')


if __name__ == '__main__':
    main()
