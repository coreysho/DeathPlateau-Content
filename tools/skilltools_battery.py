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

    print(f'\n{ok} ok, {bad} FAIL')
    sys.exit(1 if bad else 0)


main()
