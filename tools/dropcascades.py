#!/usr/bin/env python3
"""The npc death tables are hand-written threshold cascades. This checks that each one IS a cascade.

HOW A DEATH TABLE IS WRITTEN. 221 files in scripts/drop_tables/scripts, nearly all of this shape:

    def_int $random = random(128);
    if ($random < 4) {          obj_add(... iron_scimitar ...)
    } else if ($random < 6) {   obj_add(... steel_sq_shield ...)
    } else if ($random < 126) { obj_add(... coins ...)
    }

One roll, cumulative thresholds, and what makes the rows mutually exclusive is the `else` on every
branch after the first. Drop an `else` and the kill pays BOTH rows whenever the roll satisfies both
conditions - the same class of bug as ~pick_pocket_check_for_reward paying every row of its table
instead of one (tools/loottables.py).

TWO IDIOMS ARE BOTH FINE, and an earlier version of this tool called 9 of 256 cascades broken
because it only knew the first:

  * else-if chains, as above.
  * a bare `if` per row where every branch RETURNS - ~tindel_roll_sword, ~kraken_rare_seed and
    ~mining_gem_table are all written this way, and a branch that returns is as exclusive as an
    else. A jump (@label) counts the same way.

And cascades both NEST and SIT SIDE BY SIDE: macro_event_zombie puts a whole second cascade on the
same roll inside its `else if (map_members = ^true)` branch, while macro_event_river_troll puts one
cascade in an `if (map_members = ^true)` and another in the `else`. Brace depth alone cannot tell
those two apart - the river troll's pair are at the SAME depth and are still mutually exclusive - so
conditions are grouped by the identity of the block that encloses them, which is the line the brace
opened on. Getting that wrong is what made an earlier version of this call 9 of 257 cascades broken
when none of them were.

WHAT IS FLAGGED:

  MIXED/MISSING ELSE  a bare `if` after another condition on the same roll at the same depth, where
                      the earlier branch does not exit. Every roll under the lower threshold pays
                      twice.
  NOT INCREASING      a threshold at or below the one before it at the same depth. The branch is
                      unreachable, or it overlaps the one above it.
  OVER THE BOUND      a threshold above the roll's ceiling. random(128) never returns 128, so
                      `< 130` is just `always`, and anything below it is dead.

Deliberately NOT flagged: a cascade that does not reach its ceiling. random(128) topping out at 126
means 2 rolls in 128 drop nothing but the npc's own death_drop, which is normal and very common.

  python3 tools/dropcascades.py                                    # the whole tree
  python3 tools/dropcascades.py --glob "scripts/drop_tables/**/*.rs2"
  python3 tools/dropcascades.py --all                              # every cascade, not just faults
  python3 tools/dropcascades.py --selftest                         # prove the checks still fire
"""
import argparse, glob, os, re, sys

ROLL = re.compile(r'\bdef_int\s+(\$\w+)\s*=\s*random\w*\(\s*([^()]+?)\s*\)')
COND = re.compile(r'^\s*(\}?\s*else\s+)?if\s*\(\s*(\$\w+)\s*<\s*([^()\s]+)\s*\)(.*)$')
CONST = re.compile(r'^\s*(\^\w+)\s*=\s*(-?\d+)\s*$')


def constants(content):
    """Every ^name = number in the tree.

    A roll's ceiling is as often a constant as a literal - elder_chaos_druid rolls
    random(^elder_chaos_table) - and the first version of this tool only matched digits, so it
    skipped every cascade like that without saying so. 164 of 221 death scripts looked like they
    had a cascade; the rest were a mix of guaranteed-drop-only files and this blind spot.
    """
    out = {}
    for p in glob.glob(os.path.join(content, 'scripts/**/*.constant'), recursive=True):
        for line in open(p, encoding='utf-8', errors='replace'):
            m = CONST.match(line.split('//')[0])
            if m:
                out[m.group(1)] = int(m.group(2))
    return out


def number(tok, consts):
    """An int from a literal or a ^constant, or None if it is something this tool cannot read."""
    tok = tok.strip()
    if re.fullmatch(r'-?\d+', tok):
        return int(tok)
    return consts.get(tok)
EXIT = re.compile(r'\breturn\b|@\w+')


def walk_blocks(code, line_no, stack):
    """Update the stack of enclosing blocks, each identified by the line its brace opened on.

    Returns the stack as it stands AT this line - which for a line beginning with `}` is the stack
    after the close, so that `} else if (...)` is read as a sibling of the branch it follows rather
    than as a child of it.
    """
    opened_here = []
    for ch in code:
        if ch == '{':
            stack.append(line_no)
            opened_here.append(line_no)
        elif ch == '}':
            if stack:
                stack.pop()
    # the condition on this line belongs outside anything the line itself opened
    at = tuple(s for s in stack if s not in opened_here)
    return at, stack


def scan(path, consts, skipped):
    """Every cascade in the file: (var, bound, roll line, depth, [(line, is_else, thresh, exits)])."""
    text = open(path, encoding='utf-8', errors='replace').read().replace('\r\n', '\n')
    lines = text.split('\n')
    chains = {}
    order = []
    rolls = {}
    stack = []
    for i, line in enumerate(lines, 1):
        code = line.split('//')[0]
        here, stack = walk_blocks(code, i, stack)
        m = ROLL.search(code)
        if m:
            var = m.group(1)
            bound = number(m.group(2), consts)
            if bound is None:
                skipped.append((path, i, m.group(0).strip()))
                rolls.pop(var, None)
                continue
            rolls[var] = (bound, i)
            # a fresh roll invalidates any open chain on that variable
            for key in list(chains):
                if key[0] == var:
                    pass
            continue
        c = COND.match(code)
        if not c:
            continue
        var = c.group(2)
        thresh = number(c.group(3), consts)
        if var not in rolls:
            continue
        if thresh is None:
            skipped.append((path, i, c.group(0).strip()))
            continue
        bound, at = rolls[var]
        key = (var, at, here)   # same roll, same enclosing block = the same cascade
        if key not in chains:
            chains[key] = []
            order.append((key, bound))
        # does this branch leave the cascade? the body may be on the same line or the next few
        body = c.group(4)
        exits = bool(EXIT.search(body))
        if not exits:
            # look ahead until the brace this condition opened closes again
            d = 0
            started = False
            for j in range(i - 1, min(i + 60, len(lines))):
                seg = lines[j].split('//')[0]
                for ch in seg:
                    if ch == '{':
                        d += 1
                        started = True
                    elif ch == '}':
                        d -= 1
                if started and d <= 0:
                    exits = bool(EXIT.search('\n'.join(lines[i - 1:j + 1])))
                    break
                if not started and j > i - 1 and seg.strip():
                    exits = bool(EXIT.search(seg))
                    break
        chains[key].append((i, bool(c.group(1)), thresh, exits))
    return [(key[0], bound, key[1], len(key[2]), chains[key]) for key, bound in order]


def faults_of(bound, conds):
    """A bare `if` is only a fault when the branch BEFORE it can fall through into it.

    Requiring every branch to exit was too strict: barrows_door_spawn returns out of its first
    branch and then runs an else-if chain for the rest, which is exclusive and perfectly readable.
    What matters is the one immediately above.
    """
    out = []
    prev = None
    for n, (line, is_else, thresh, exits) in enumerate(conds):
        if n > 0 and not is_else and not conds[n - 1][3]:
            out.append(('MIXED/MISSING ELSE', line, thresh))
        if prev is not None and thresh <= prev:
            out.append(('NOT INCREASING', line, thresh))
        if thresh > bound:
            out.append(('OVER THE BOUND', line, thresh))
        prev = thresh
    return out


# A zero is only worth something if the tool can still see the bug, so --selftest mutates a sample
# three ways and checks that each mutation is caught and the unmutated copy is not.
SAMPLE = """[ai_queue3,selftest_npc]
def_int $random = random(128);
if ($random < 4) {
    obj_add(npc_coord, iron_scimitar, 1, ^lootdrop_duration);
} else if ($random < 10) {
    obj_add(npc_coord, chaosrune, 6, ^lootdrop_duration);
} else if ($random < 60) {
    obj_add(npc_coord, coins, 35, ^lootdrop_duration);
} else if ($random < 126) {
    obj_add(npc_coord, coal, 1, ^lootdrop_duration);
}
"""

MUTATIONS = [
    ('clean', None, None, None),
    ('missing_else', '} else if ($random < 10) {', '}' + chr(10) + 'if ($random < 10) {',
     'MIXED/MISSING ELSE'),
    ('not_increasing', '} else if ($random < 60) {', '} else if ($random < 9) {', 'NOT INCREASING'),
    ('over_bound', '} else if ($random < 126) {', '} else if ($random < 400) {', 'OVER THE BOUND'),
]


def selftest():
    import tempfile
    bad = 0
    for name, old, new, want in MUTATIONS:
        src = SAMPLE if old is None else SAMPLE.replace(old, new, 1)
        if old is not None and src == SAMPLE:
            print('  FAIL %-16s the mutation did not apply' % name)
            bad += 1
            continue
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'x.rs2')
            open(f, 'w', encoding='utf-8', newline='').write(src)
            found = []
            for var, bound, at, depth, conds in scan(f, {}, []):
                if len(conds) >= 2:
                    found += [k for k, _, _ in faults_of(bound, conds)]
            if want is None:
                ok = not found
            else:
                ok = want in found
            print('  %s %-16s %s' % ('ok  ' if ok else 'FAIL', name,
                                     'no fault' if not found else ', '.join(sorted(set(found)))))
            if not ok:
                bad += 1
    print('  self-test: %s' % ('every injected fault is caught' if not bad else 'BROKEN'))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content',
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--glob', default='scripts/**/*.rs2')
    ap.add_argument('--selftest', action='store_true',
                    help='prove the checks still fire, then carry on')
    a = ap.parse_args()

    if a.selftest and selftest():
        return 2

    consts = constants(a.content)
    skipped = []
    total = bad = 0
    for p in sorted(glob.glob(os.path.join(a.content, a.glob), recursive=True)):
        rel = os.path.relpath(p, a.content).replace(os.sep, '/')
        for var, bound, at, depth, conds in scan(p, consts, skipped):
            if len(conds) < 2:
                continue
            total += 1
            f = faults_of(bound, conds)
            if f:
                bad += 1
            if not f and not a.all:
                continue
            style = 'else-if' if conds[1][1] else ('return-per-row' if all(c[3] for c in conds) else 'bare ifs')
            print('%s:%d   %s = random(%d), %d branches at depth %d, %s%s'
                  % (rel, at, var, bound, len(conds), depth, style, '' if f else '   ok'))
            for kind, line, thresh in f:
                print('      %-20s line %d, threshold %d' % (kind, line, thresh))
    print()
    print('%d constants resolved' % len(consts))
    print('%d cascades of two or more branches, %d with a fault' % (total, bad))
    if skipped:
        print('%d rolls or thresholds this tool could not read - the blind spot, listed so it is '
              'not silent:' % len(skipped))
        for p, i, what in skipped:
            print('    %s:%d  %s' % (os.path.relpath(p, a.content).replace(os.sep, '/'), i, what))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
