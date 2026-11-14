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


def configs(ext):
    """every config of one extension in the tree -> {name: {field: [values]}}, like objs()"""
    out = {}
    for root, _d, files in os.walk(os.path.join(C, 'scripts')):
        for f in files:
            if not f.endswith(ext):
                continue
            cur = None
            for line in open(os.path.join(root, f), encoding='utf-8', errors='replace'):
                line = line.split('//')[0].strip()
                m = re.match(r'^\[([a-z0-9_]+)\]$', line)
                if m:
                    cur = m.group(1)
                    out.setdefault(cur, {})
                elif cur and '=' in line:
                    k, v = line.split('=', 1)
                    k, v = k.strip(), v.strip()
                    if k == 'param' and ',' in v:
                        k, v = v.split(',', 1)
                    out[cur].setdefault(k, []).append(v)
    return out


def all_rs2():
    text = []
    for root, _d, files in os.walk(os.path.join(C, 'scripts')):
        for f in files:
            if f.endswith('.rs2'):
                text.append(open(os.path.join(root, f), encoding='utf-8', errors='replace').read())
    return '\n'.join(text)


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

    woodcut_trees()
    worn_rig(real)

    print(f'\n{ok} ok, {bad} FAIL')
    sys.exit(1 if bad else 0)


def woodcut_trees():
    """A TREE IS WIRED IN THREE PLACES TOO, and so is the Ent that spawns at it.

    Same shape of bug as the axes above, one level out. A loc can carry op1="Chop down", op3=hidden
    and a stump of its very own and still chop nothing, because woodcut.rs2 is reached by
    `category=` and the logs come out of a dbrow the category knows nothing about. Ape Atoll's two
    Jungle Trees were in exactly that state, placed 123 times, with 377's own cache telling anyone
    who looked that they were meant to be choppable.

    The Ent is worse, because it hides from the usual report. Twenty-one of the thirty-six Ents in
    antimacro.npc had op1="Chop down" and no category=macro_event_ent, so [opnpc1,_macro_event_ent]
    never saw the click - at an ordinary tree, an oak, a willow, a yew, a maple or a magic tree.
    opsweep had them all along, filed under "not placed anywhere on the map", which is true of
    every Ent and says nothing, because an Ent arrives by npc_add.

    WHAT THE SKILL ACTUALLY READS, grepped out of woodcut.rs2 and macro_event_ent.rs2:
      the loc    category= -> [oploc1,_tree] / [oploc1,_jungle_tree] / [oploc1,_jungle_bush]
                 a row in woodcutting_trees naming it, or db_find comes back null
                 op3=hidden, or p_oploc(3) returns early and it chops once and stops
                 param=next_loc_stage, or loc_change is handed a null type
      the Ent    category=macro_event_ent, param=ent_tree_loc naming the loc it replaced
    """
    CHOP = ('tree', 'jungle_tree', 'jungle_bush')
    locs = configs('.loc')
    npcs = configs('.npc')
    rs2 = all_rs2()

    rows = set()
    cur = None
    for line in read('scripts/skill_woodcutting/configs/trees.dbrow').replace('\r\n', '\n').split('\n'):
        line = line.split('//')[0].strip()
        m = re.match(r'^\[([a-z0-9_]+)\]$', line)
        if m:
            cur = m.group(1)
        elif line.startswith('data=tree,'):
            rows.add(line.split(',', 1)[1])

    chopped = sorted(n for n, d in locs.items() if d.get('category', [None])[0] in CHOP)
    print(f'\nWOODCUTTING TREES - {len(chopped)} locs carry a chopping category, {len(rows)} rows name a tree')

    missing = [n for n in chopped if n not in rows]
    check('each has a row in woodcutting_trees', not missing, ', '.join(missing))
    nohidden = [n for n in chopped if 'hidden' not in locs[n].get('op3', [])]
    check('and op3=hidden, so p_oploc(3) can keep it swinging', not nohidden, ', '.join(nohidden))
    nostage = [n for n in chopped if 'next_loc_stage' not in locs[n]]
    check('and a param=next_loc_stage to fall into', not nostage, ', '.join(nostage))
    dangling = [f"{n} -> {locs[n]['next_loc_stage'][0]}" for n in chopped
                if 'next_loc_stage' in locs[n] and locs[n]['next_loc_stage'][0] not in locs]
    check('and that stage is a loc that exists', not dangling, ', '.join(dangling))

    # THE OTHER DIRECTION, and it needs the multiloc escape. The five farmed trees - the
    # *_fullygrown_2 variants - have no category of their own; their patch shell carries
    # category=farming_patch and farming_actions.rs2 reads this same dbrow through it. A variant's
    # trigger comes from whatever type is standing in the world, so the shell's category is the one
    # that dispatches.
    shell_of = {}
    for shell, d in locs.items():
        for ml in d.get('multiloc', []):
            shell_of.setdefault(ml.split(',', 1)[1], []).append(shell)
    unreachable = []
    for t in sorted(rows):
        if t not in locs:
            unreachable.append(f'{t} (no such loc)')
            continue
        if locs[t].get('category', [None])[0] in CHOP:
            continue
        if f'[oploc1,{t}]' in rs2:
            continue
        if any(locs[s].get('category') for s in shell_of.get(t, [])):
            continue
        unreachable.append(t)
    check('every row names a loc something can dispatch', not unreachable, ', '.join(unreachable))

    # ---- the Ents
    # Left out on purpose, with the reason, rather than hidden in a filter: these carry no
    # param=ent_tree_loc and nothing points at them, so giving them the dispatching category would
    # turn silence into "Nothing interesting happens."
    SPARE = ('macro_ent_dead_tree5', 'macro_ent_dead_tree9', 'macro_ent_dead_tree11',
             'macro_ent_evergreen3', 'macro_ent_tree2')
    # dramentree has its own [oploc1,dramentree] which never calls ~macro_randomwoodcutting, and no
    # row in woodcutting_trees, so macro_ent_dramen cannot spawn and cannot work if it did.
    DRAMEN = 'macro_ent_dramen'

    pairs = [(n, locs[n]['ent'][0]) for n in chopped if 'ent' in locs[n]]
    print(f'  ({len(pairs)} of them name an Ent)')
    gone = [f'{t} -> {e}' for t, e in pairs if e not in npcs]
    check('each Ent a tree names exists', not gone, ', '.join(gone))
    for field, want in (('category', 'macro_event_ent'), ('moverestrict', 'nomove'), ('wanderrange', '0')):
        wrong = [f'{e} ({t})' for t, e in pairs if e in npcs and want not in npcs[e].get(field, [])]
        check(f'and carries {field}={want}', not wrong, ', '.join(wrong))
    backwards = [f"{e} -> {npcs[e].get('ent_tree_loc', ['nothing'])[0]} (not {t})" for t, e in pairs
                 if e in npcs and npcs[e].get('ent_tree_loc', [None])[0] != t]
    check('and names that same tree in param=ent_tree_loc', not backwards, ', '.join(backwards))

    ents = sorted(n for n, d in npcs.items() if 'macro_event_ent' in d.get('category', []))
    named = {e for _t, e in pairs}
    orphan = [e for e in ents if e not in named]
    check(f'and all {len(ents)} Ents with that category are reachable from a tree', not orphan, ', '.join(orphan))
    silent = [n for n in SPARE + (DRAMEN,) if 'macro_event_ent' in npcs.get(n, {}).get('category', [])]
    check('the Ents nothing can spawn stay silent rather than saying nothing interesting happens',
          not silent, ', '.join(silent))


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
