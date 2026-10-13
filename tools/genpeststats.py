#!/usr/bin/env python3
"""Give the 377 cache's Pest Control npcs their combat stats, from the OSRS cache's own numbers.

    python3 tools/genpeststats.py ../caches/osrs [--check]

WHY THIS EXISTS. All 54 pest npcs - seven monster families at five tiers each, four portals and the
four Void Knights - were already in the 377 cache with full art, animations and vislevels, and NOT
ONE of them carried a single combat stat. They had never been fought, because the minigame was
never built (minigames/game_pest/configs/pest.constant records that). Writing 54 records' worth of
hitpoints/attack/strength/defence by hand is 54 chances to put a number in the wrong row, so this
reads them out of the OSRS cache instead and writes them in.

THE TIER MAPPING IS CONFIRMED BY TWO INDEPENDENT SOURCES, which is the only reason to trust it:
the 377 records' own vislevels ascend in five steps (shifter 37/56/75/94/113, brawler
50/75/100/128/157) and the OSRS records for the same name ascend in five steps of stats in the same
order. Neither was derived from the other. Where 377 has an a/b pair (shifters, torchers, defilers)
OSRS has two consecutive records with identical stats, which is the same split.

IDEMPOTENT: a record that already has hitpoints= is left alone, so running this twice is a no-op
and --check reports what would change without writing.
"""
import re, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools', 'models'))
from flatcache import Store
from osrsnpc import load_osrs_npcs

ALL_NPC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', '_unpack', '377', 'all.npc')

# 377 name prefix -> (OSRS name, how the family fights, defence-bonus, attack range)
# damagetype and the bonuses are this repo's own params; the attack style follows the stats array
# (a torcher has magic and no strength, a defiler has ranged and no strength, the rest are melee).
FAMILIES = [
    ('pest_shifter',  'Shifter',  'crush', 1),
    ('pest_ravager',  'Ravager',  'crush', 1),
    ('pest_spinner',  'Spinner',  'magic', 1),
    ('pest_torcher',  'Torcher',  'magic', 8),
    ('pest_defiler',  'Defiler',  'range', 8),
    ('pest_brawler',  'Brawler',  'crush', 1),
    ('pest_splatter', 'Splatter', 'crush', 1),
]
STYLE = {'crush': '^crush_style', 'magic': '^magic_style', 'range': '^ranged_style'}

# THE PEST NPC BLOCK in the OSRS cache. Every monster, portal and Void Knight this file cares about
# sits in one contiguous run of ids, which is how the cache was built - one minigame, one block.
#
# The window is not tidiness, it is correctness: searching the whole cache by NAME finds a sixth
# "Splatter" at id 15550, a size-3 creature with 1000 hitpoints and 250 strength from content a
# decade later, and a positional mapping that swallowed it would have handed a tier-5 pest splatter
# the stats of whatever that is. The guard below caught it; this is the fix.
ID_RANGE = (1680, 1800)

# The generator owns the text between these two markers in each record it writes, and replaces it
# wholesale. Anything outside them - the cache's own art, models, animations and vislevel - is
# never touched.
# The portals' hitpoints and defence, the two numbers a solo game is tuned on. See the comment
# where they are used for the measurement that set them.
PORTAL_HP = 50
PORTAL_DEF = 10

BEGIN = '// --- genpeststats.py BEGIN: do not hand-edit, regenerate ---'
END = '// --- genpeststats.py END ---'


def osrs_records(recs, name):
    """Every OSRS record called `name`, in id order, as (atk, def, str, hp, rng, mag).

    POSITIONAL, not deduplicated. An earlier version collapsed identical stat tuples to find the
    five tiers and broke on the Torcher, whose tier-5 pair is 70 and 71 hitpoints - six distinct
    tuples for five tiers. Mapping the nth 377 record to the nth OSRS record needs no dedup and
    keeps that one-hitpoint difference, which is real.
    """
    lo, hi = ID_RANGE
    return [tuple(d.get('stats', [0] * 6)[:6])
            for _i, d in sorted((i, d) for i, d in recs.items()
                                if str(d.get('name', '')) == name and lo <= i <= hi)]


def main():
    cache = sys.argv[1] if len(sys.argv) > 1 else '../caches/osrs'
    check = '--check' in sys.argv
    recs, _bad = load_osrs_npcs(Store(cache))
    txt = open(ALL_NPC).read()

    plan = {}
    for prefix, osrs_name, style, rng in FAMILIES:
        stats = osrs_records(recs, osrs_name)
        # Which 377 records this family has, in tier then a/b order.
        names = [nm for t in range(1, 6) for suffix in ('', 'a', 'b')
                 for nm in ['%s_%d%s' % (prefix, t, suffix)]
                 if '[%s]\n' % nm in txt]
        if len(names) != len(stats):
            raise SystemExit('%s: %d records in 377 but %d in OSRS - the positional mapping '
                             'would be wrong' % (osrs_name, len(names), len(stats)))
        for nm, (atk, dfc, stn, hp, rngstat, mag) in zip(names, stats):
            t = int(re.search(r'_(\d)[ab]?$', nm).group(1))
            if True:
                lines = ['hitpoints=%d' % hp, 'attack=%d' % atk, 'strength=%d' % stn,
                         'defence=%d' % dfc]
                if rngstat:
                    lines.append('ranged=%d' % rngstat)
                if mag and style == 'magic':
                    lines.append('magic=%d' % mag)
                # A flat defence bonus per tier, so a tier-5 pest is not shredded by a whip the way
                # a bonus-less npc is. Scaled off the tier, not sourced - OSRS keeps these in a
                # separate table this decoder does not read.
                bonus = 5 * t
                for which in ('stab', 'slash', 'crush', 'magic', 'range'):
                    lines.append('param=%sdefence,%d' % (which, bonus))
                lines.append('param=damagetype,%s' % STYLE[style])
                lines.append('huntmode=%s' % ('aggressive_ranged' if rng > 1 else 'aggressive_melee'))
                lines.append('huntrange=%d' % (8 if rng > 1 else 5))
                lines.append('attackrange=%d' % rng)
                lines.append('wanderrange=4')
                lines.append('param=pest_tier,%d' % t)
                plan[nm] = lines

    # The four portals.
    #
    # NOT OLD SCHOOL'S NUMBERS, and this is the one place in this file that departs from them.
    # OSRS's novice portal has 250 hitpoints and 120 defence, which is tuned for five to
    # twenty-five players hitting it at once. Measured against one player (engine
    # tools/sim/_ttk.ts) a maxed account with an abyssal whip took 203 TICKS to drop one of those -
    # four of them is 812 ticks of swinging against a 500-tick clock, before any walking between
    # portals 37 tiles apart and before the pests get a say. It was not hard, it was impossible.
    #
    # PORTAL_HP and PORTAL_DEF below are chosen against that measurement, not guessed, and the
    # measurement is the test: a maxed player should drop one in well under a quarter of the clock
    # so that four plus travel fits, and an under-levelled one should not.
    #
    # It still cannot fight back - attack and strength stay at 1, which IS Old School's.
    for n in (1, 2, 3, 4):
        plan['pest_portal_%d_active' % n] = [
            'hitpoints=%d' % PORTAL_HP, 'attack=1', 'strength=1', 'defence=%d' % PORTAL_DEF,
            'param=stabdefence,0', 'param=slashdefence,0', 'param=crushdefence,0',
            'param=magicdefence,0', 'param=rangedefence,0',
            'param=death_anim,pest_portal_death',
            'param=pest_portal,1',
            # A PORTAL MUST NOT MOVE. Without this it wanders - the default wanderrange is not zero
            # - and a size-3 objective drifting off the tile the island scan picked for it was
            # exactly what tools/sim/pestsolo.ts caught (one portal reporting 11,54 for 10,55).
            # huntmode is left unset for the same reason: it has nothing to hunt.
            'wanderrange=0',
        ]

    # The four Void Knights. No combat stats - he is not a combatant, he is a clock (see
    # minigames/game_pest/configs/pest_solo.constant) - but he must not wander off the tile the
    # island scan picked for him.
    for n in (1, 2, 3, 4):
        plan['pest_voidknight_control%d' % n] = ['wanderrange=0']

    changed, same = [], []
    for nm, lines in sorted(plan.items()):
        m = re.search(r'^\[%s\]\n(.*?)(?=^\[|\Z)' % re.escape(nm), txt, re.S | re.M)
        if not m:
            raise SystemExit('%s is not in all.npc' % nm)
        body = m.group(1)
        block = BEGIN + '\n' + '\n'.join(lines) + '\n' + END + '\n'
        # THE BLOCK IS REPLACED, NOT APPENDED TO, which is what makes this re-runnable. The first
        # version keyed idempotence on "does the record already carry the first line this plan
        # would add" - which is true until a NUMBER CHANGES, and then it appended a second
        # hitpoints= line below the first. Lowering the portals' hitpoints and defence is exactly
        # that case, so the generator now owns the text between its own two markers.
        old = re.search(r'^%s\n.*?^%s\n' % (re.escape(BEGIN), re.escape(END)), body, re.S | re.M)
        if old:
            if old.group(0) == block:
                same.append(nm)
                continue
            new = body[:old.start(0)] + block + body[old.end(0):]
        else:
            # First time: appended at the end of the record, after the art and the existing
            # params, the way area_wilderness/configs/ankou.npc orders them.
            new = body.rstrip('\n') + '\n' + block + '\n'
        txt = txt[:m.start(1)] + new + txt[m.end(1):]
        changed.append(nm)

    print('%d records written, %d already current' % (len(changed), len(same)))
    for nm in changed:
        hp = [l for l in plan[nm] if l.startswith('hitpoints=')]
        print('   %-26s %s' % (nm, hp[0] if hp else '(no combat stats)'))
    if check:
        print('--check: nothing written')
        return
    open(ALL_NPC, 'w').write(txt)
    print('wrote', ALL_NPC)


if __name__ == '__main__':
    main()
