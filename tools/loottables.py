#!/usr/bin/env python3
"""Every weighted loot list in the game, and whether the thing that rolls it pays one row or all.

THE TWO KINDS OF TABLE. A loot list with a weight per row is read one of two ways:

  * a WEIGHTED table - weights adding up to the denominator or less - pays ONE row, and the chance
    of row i is w(i)/denominator.
  * GUARANTEED drops - every weight equal to the denominator - pay ALL the rows.

A walk that does not stop on a hit turns the first kind into the second. That is what
~pick_pocket_check_for_reward did until 2026-10-12: the H.A.M. member's 36-row table paid 2.71
kinds of thing a pocket ("am i supposed to be receiving 3 items per pickpocket at ham members?"),
the gnome's six paid 1.72, the hero's seven 1.19 and the rogue's five 1.17, while the seven
single-row tables were unaffected and hid it.

This prints the expected number of rows each table pays under both readings, so a weighted table
being paid out in full shows up as a number above 1. It does not read the scripts - a roller that
stops correctly and a roller that does not look the same from the data - so the second half of the
job is the list at the bottom: every proc in the tree that walks a loot list, and whether it stops.

  python3 tools/loottables.py
"""
import glob, os, re, sys

# dbtable -> (dbrow glob, loot column, which field of that column is the weight, the roller,
# whether the roller stops on a hit). The weight is NOT always the last field - stealing's last one
# is the message string.
ROLLERS = [
    ('pickpocket', 'scripts/skill_thieving/configs/pickpocking/*.dbrow', 'loot', 3,
     '~pick_pocket_check_for_reward', True),
    ('trapped_chest', 'scripts/skill_thieving/configs/chests/*.dbrow', 'loot', 3,
     '~trapped_chest_check_for_reward', True),
    ('stealing', 'scripts/skill_thieving/configs/stalls/*.dbrow', 'loot', 3,
     '~stealing_check_for_reward', True),
]

# pickpocket and trapped_chest roll against a hardcoded 128 and say "guaranteed" by giving a row a
# weight of 128; stealing carries its own denominator per row instead, in loot_total. Same idea,
# two spellings.
DENOM_COLUMN = {'stealing': 'loot_total'}


def rows(pattern, col, widx, content, denom_col, denoms):
    """row name -> list of weights, read off every dbrow matching the pattern."""
    out = {}
    for p in sorted(glob.glob(os.path.join(content, pattern))):
        cur = None
        for line in open(p, encoding='utf-8', errors='replace'):
            s = line.strip()
            if s.startswith('//'):
                continue
            if s.startswith('[') and s.endswith(']'):
                cur = s[1:-1]
                out[cur] = []
            elif cur is not None and s.startswith('data=%s,' % col):
                fields = s[len('data=%s,' % col):].split(',')
                out[cur].append(int(fields[widx]))
            elif cur is not None and denom_col and s.startswith('data=%s,' % denom_col):
                denoms[cur] = int(s.split(',')[1])
    return {k: v for k, v in out.items() if v}


def paid_if_no_stop(weights, d0):
    """Expected rows paid by a walk that rolls each row and never stops."""
    d, e = d0, 0.0
    for w in weights:
        if w >= d:            # a guaranteed row: handed over, denominator untouched
            e += 1
            continue
        e += w / d
        d -= w
    return e


def paid_if_stops(weights, d0):
    """Expected rows paid by a walk that stops on the first hit, guaranteed rows excepted."""
    d, e, reach = d0, 0.0, 1.0
    for w in weights:
        if w >= d:
            e += reach
            continue
        e += reach * (w / d)
        reach *= 1 - w / d
        d -= w
    return e


def main():
    content = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    bad = 0
    for table, pattern, col, widx, roller, stops in ROLLERS:
        denoms = {}
        data = rows(pattern, col, widx, content, DENOM_COLUMN.get(table), denoms)
        print('%s   rolled by %s%s' % (table, roller, '' if stops else '   (DOES NOT STOP)'))
        for name, w in sorted(data.items()):
            # a flat 128, unless the table carries its own denominator per row
            denom = denoms.get(name, 128)
            kind = 'guaranteed' if all(x >= denom for x in w) else 'weighted'
            nostop = paid_if_no_stop(w[::-1], denom)
            withstop = paid_if_stops(w[::-1], denom)
            flag = ''
            if kind == 'weighted' and nostop > 1.005:
                flag = '   <- a weighted table, so a walk that never stops over-pays by %.2f' % (nostop - 1)
                if not stops:
                    bad += 1
            print('    %-38s %2d row(s) %-11s sum %4d   pays %.2f if it stops, %.2f if it does not%s'
                  % (name, len(w), kind, sum(w), withstop, nostop, flag))
        print()

    print('AND EVERY PROC IN THE TREE THAT WALKS A LOOT LIST:')
    print('    %-34s %s' % ('~roll_on_drop_table', 'stops on a hit (npc drops, its own total)'))
    for table, pattern, col, widx, roller, stops in ROLLERS:
        print('    %-34s %s' % (roller, 'stops on a hit' if stops else 'DOES NOT STOP'))
    print('    ~droprate_bonus                    rolls every row independently, by design (gamemodes)')
    print('    ~roguesden_safe_reward             threshold cascade, returns on each')
    print('    ~mining_gem_table                  threshold cascade, returns on each')
    print('    ~drop_bird_nest                    switch on one roll')
    print('    ~legends_barrel_noted_drop         else-if chain, one per roll, 4-10 rolls on purpose')
    print('    ~misc_collect_roll                 else-if chains, one nest per 100 logs on purpose')
    print('    ~woodcutting_successchance         a lookup by axe, not a loot roll')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
