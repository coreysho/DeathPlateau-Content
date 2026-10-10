#!/usr/bin/env python3
"""Every tool a skill reads must actually be readable by that skill.

A tool in this build is wired to its skill by PARAMS ON THE OBJ, not by a list in a script, so an
item can look exactly like an axe - right category, right wearpos, right model - and chop nothing,
because the one line that tells Woodcutting about it is missing. Nothing else checks that: the
compiler is happy, rs2check is happy, and the item is only broken when somebody tries to use it.

That is what happened to the 3rd Age axe, which sat in the game as a clue reward with no
woodcutting_struct on it.

WHAT EACH SKILL READS, found by grepping the skill's own scripts rather than assumed:
  Woodcutting  param=woodcutting_struct -> a struct carrying param=skill_anim
  Mining       param=mining_rate and param=mining_animation, both on the obj

  python3 tools/skilltools_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = bad = 0


def check(what, good, detail=''):
    global ok, bad
    if good:
        ok += 1
        print(f'  ok   {what}')
    else:
        bad += 1
        print(f'  FAIL {what}{(" - " + detail) if detail else ""}')


def vertex_labels(b):
    """The per-vertex transform-group byte of a 377 .ob2, read from the 18-byte trailer forward.

    Inlined rather than imported from the super-repo's tools/models/posepreview.py: a battery that
    lives in content and reaches outside it only works on one machine.
    """
    p = len(b) - 18
    g2 = lambda o: (b[o] << 8) | b[o + 1]
    vcount, fcount, tcount = g2(p), g2(p + 2), b[p + 4]
    f_tex, f_pri, f_alpha, f_flabel, f_vlabel = b[p + 5], b[p + 6], b[p + 7], b[p + 8], b[p + 9]
    if f_vlabel != 1:
        return None, vcount
    o = vcount + fcount                                   # vertex flags, then face types
    if f_pri == 255:
        o += fcount
    if f_flabel == 1:
        o += fcount
    if f_tex == 1:
        o += fcount
    return list(b[o:o + vcount]), vcount


def read(rel):
    return open(os.path.join(C, *rel.split('/')), encoding='utf-8', errors='replace').read()


def objs():
    """every obj config in the tree -> {name: {field: [values]}}"""
    out = {}
    for root, _d, files in os.walk(os.path.join(C, 'scripts')):
        for f in files:
            if not f.endswith('.obj'):
                continue
            cur = None
            for line in open(os.path.join(root, f), encoding='utf-8', errors='replace'):
                line = line.split('//')[0].strip()
                m = re.match(r'^\[([a-z0-9_]+)\]$', line)
                if m:
                    cur = m.group(1)
                    out[cur] = {'_file': os.path.relpath(os.path.join(root, f), C)}
                elif cur and '=' in line:
                    k, v = line.split('=', 1)
                    k, v = k.strip(), v.strip()
                    # `param=mining_rate,7` is the param NAMED mining_rate - keying it under
                    # "param" puts every param in one bucket and makes every item look unwired,
                    # which is how the first run of this reported bronze pickaxes as broken.
                    if k == 'param' and ',' in v:
                        k, v = v.split(',', 1)
                    out[cur].setdefault(k, []).append(v)
    return out


def structs():
    names = set()
    for root, _d, files in os.walk(os.path.join(C, 'scripts')):
        for f in files:
            if not f.endswith('.struct'):
                continue
            for line in open(os.path.join(root, f), encoding='utf-8', errors='replace'):
                m = re.match(r'^\[([a-z0-9_]+)\]$', line.strip())
                if m:
                    names.add(m.group(1))
    return names


def main():
    o = objs()
    st = structs()
    # a cert is the noted copy of an item and is never wielded, so it never needs the tool params
    real = {n: d for n, d in o.items() if not n.startswith('cert_') and 'certlink' not in d}

    # category=weapon_axe COVERS BATTLEAXES, and a battleaxe is a weapon rather than a tool - it
    # chops nothing in Old School either. The data does not tell the two apart, so the exclusion is
    # by name and is written out rather than hidden in a regex.
    NOT_A_HATCHET = ('battleaxe', 'dharok', 'blessed_axe', 'anger_axeq')
    allaxes = [n for n, d in real.items() if d.get('category') == ['weapon_axe']]
    axes = sorted(n for n in allaxes if not any(k in n for k in NOT_A_HATCHET))
    print('WOODCUTTING - a hatchet is wired in THREE places and needs all three')
    print(f'  ({len(axes)} hatchets; {len(allaxes) - len(axes)} battleaxes and quest axes excluded)')

    missing = [n for n in axes if 'woodcutting_struct' not in real[n]]
    check('each names a woodcutting_struct', not missing, ', '.join(missing))
    dangling = [f'{n} -> {real[n]["woodcutting_struct"][0]}' for n in axes
                if 'woodcutting_struct' in real[n] and real[n]['woodcutting_struct'][0] not in st]
    check('and each struct it names exists', not dangling, ', '.join(dangling))

    # THE TWO CHECKS THAT MATTER, and the two that nothing had. A config can be perfect and the axe
    # still chop nothing, because the skill finds your axe through a HARDCODED LADDER and rates it
    # through a PER-TREE TABLE, and neither of those knows what the obj config says. The gilded axe
    # carried param=woodcutting_struct and a chop animation and was in neither, so it was a
    # decoration; the 3rd Age axe was in none of the three.
    ladder = read('scripts/skill_woodcutting/scripts/woodcut.rs2')
    ladder = ladder[ladder.index('[proc,woodcutting_best_axe]'):]
    ladder = ladder[:ladder.index('[proc,', 10)].replace('return(', 'return (')
    unreachable = [n for n in axes if f'return ({n});' not in ladder]
    check('each can be returned by woodcutting_best_axe', not unreachable, ', '.join(unreachable))

    # Counted per TABLE THAT USES AXES AT ALL. The Kharazi jungle table has no success chances for
    # anybody, because its vegetation is cut with a machete and always gives way - so demanding a
    # row there would fail every axe in the game, including bronze.
    trees = read('scripts/skill_woodcutting/configs/trees.dbrow').replace('\r\n', '\n')
    cur, per_table = None, {}
    for line in trees.split('\n'):
        m = re.match(r'^\[([a-z0-9_]+)\]$', line.strip())
        if m:
            cur = m.group(1)
            per_table[cur] = set()
        elif line.startswith('data=successchance,') and cur:
            per_table[cur].add(line.split(',')[1])
    chopped = {t: have for t, have in per_table.items() if have}
    nochance = sorted({f'{n} (missing from {t})' for t, have in chopped.items()
                       for n in axes if n not in have})
    check(f'and each has a success chance on all {len(chopped)} axe-chopped tree tables',
          not nochance, ', '.join(nochance))

    print('\nMINING - every weapon_pickaxe must carry a rate and an animation')
    picks = sorted(n for n, d in real.items() if d.get('category') == ['weapon_pickaxe'])
    print(f'  ({len(picks)} pickaxes)')
    for field in ('mining_rate', 'mining_animation'):
        missing = [n for n in picks if field not in real[n]]
        check(f'every pickaxe carries param={field}', not missing, ', '.join(missing))
    zero = [n for n in picks if real[n].get('mining_rate', ['0'])[0] == '0']
    check('and none of them mines at rate 0', not zero, ', '.join(zero))

    worn_rig(real)

    print(f'\n{ok} ok, {bad} FAIL')
    sys.exit(1 if bad else 0)


def worn_rig(real):
    """A worn model must sit on a transform group the player's animations actually drive.

    Not a skilling check, but the same shape of bug and found the same way. Every vertex of a worn
    model carries a label naming a transform group; the player's animation moves those groups. A
    label the animation never touches means the item is drawn once in the right place and then
    stays there while its owner walks out from under it - which is how an imported dragonfire
    shield and the dragon defenders behaved, hanging in the air.

    SCOPED TO SHIELDS ON PURPOSE. The first version of this generalised to every wearpos and
    reported two hundred perfectly good items - every weapon on group 27, every robe on 17-25 -
    because "the groups most models use" is not a rule, it is a histogram. A shield is the case
    where the rule is real and flat: it is one rigid thing hanging off one bone, and in this
    build's wardrobe that bone is group 28 for all but a handful of imports. A check that cries
    wolf is worse than no check, so this one only speaks about shields.
    """
    import collections
    print('\nWORN SHIELDS - on the transform group the rest of the wardrobe uses')
    paths = {}
    for root, _dirs, files in os.walk(os.path.join(C, 'models')):
        for f in files:
            if f.endswith('.ob2'):
                paths.setdefault(f[:-4], os.path.join(root, f))

    seen = {}
    for name, d in real.items():
        if d.get('category') != ['armour_shield'] or 'manwear' not in d:
            continue
        mw = d['manwear'][0].split(',')[0]
        if mw in paths:
            lbl, _vc = vertex_labels(open(paths[mw], 'rb').read())
            seen[name] = set(lbl or [])
    # The four Falador shields sit on group 22 instead, and they are listed rather than fixed. 22
    # is a group the rig DOES drive - the hands models use it - so they move with the player, which
    # is the opposite of the failure this check exists for. Whether a shield belongs on the hand
    # bone rather than the shield bone is a question about how they look, and nobody has reported
    # them; moving four working items on a hunch is not what a battery is for.
    KNOWN = {'falador_shield_1', 'falador_shield_2', 'falador_shield_3', 'falador_shield_4'}
    counts = collections.Counter(g for s in seen.values() for g in s)
    group = counts.most_common(1)[0][0] if counts else None
    print(f'  ({len(seen)} shields; the wardrobe puts {counts[group]} of them on group {group})')
    offenders = sorted(f'{n} ({sorted(s)})' for n, s in seen.items()
                       if s and group not in s and n not in KNOWN)
    check(f'every shield is on group {group}', not offenders, '; '.join(offenders))


main()
