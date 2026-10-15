#!/usr/bin/env python3
"""Every mutation must name the check it is written for, and every harness must check that it did.

WHY THIS EXISTS. A mutation harness breaks one thing and requires a checker to go red. Counting
exit codes proves only that SOMETHING noticed - so the harnesses carry a label per mutation naming
the check it was written for, and report "caught by its own check" when a FAIL line contains that
text. That attribution is the whole difference between "a check fired" and "the right check fired".

It had quietly stopped being true in three different ways, and none of them showed up in a run:

  1. 130 of poh_mutate's 266 labels matched no check anywhere - slugs like "hide-needs-a-layer"
     rather than a check's words - so for half that harness "caught by its own check" could never
     print and every one of them read as "caught, but by".
  2. slayer_mutate and maxcape_mutate had no attribution at all. They print red or GREEN from the
     exit code and stop, which is the weaker thing the other harnesses were built to stop doing.
  3. A check's wording was edited and its label left behind, which turns a working mutation into a
     "caught, but by" and looks like an imprecise mutation rather than a stale label.

None of those is visible from a green run, which is why it is a tool. It costs one run of each
checker - about two minutes - against six hours to run the mutations themselves.

    python3 tools/mutate_labels.py            # audit: what does not line up
    python3 tools/mutate_labels.py -v         # and list every offending label
"""
import importlib.util, os, re, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(C, 'tools')

# A mutation whose label ends in one of these is checked by something other than its harness's
# battery, and poh_mutate's checker_for() routes it there. Not a labelling fault.
OTHER_CHECKER = ('(rs2check)', '(build sim)', '(furn sim)')

# (spec) is deliberately NOT above. A spec-routed mutation is run by a different HARNESS -
# tools/poh_mutate_spec.py, which regenerates before it checks - but it is checked by the same
# battery, so its label must match a check exactly as every other one does. Exempting it would let
# a stale spec label rot unnoticed, which is the fault this tool exists to catch. The suffix is
# stripped before matching.
SUFFIX_ONLY = ('(spec)',)

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1


def harnesses():
    """Every *_mutate.py, and the checker each one actually runs - read out of the source rather
    than listed here, so a harness added later is audited without anyone remembering to add it."""
    out = {}
    for fn in sorted(os.listdir(TOOLS)):
        if not fn.endswith('_mutate.py'):
            continue
        src = open(os.path.join(TOOLS, fn), encoding='utf-8', newline='').read()
        # Two shapes in the tree: the checker named inline at the subprocess call, and
        # poh_mutate's checker_for(), which returns a path per mutation. Read both, because a
        # harness this cannot identify is a harness this cannot audit - and saying so is the
        # point, but only when it is really unreadable.
        # The join may carry intermediate segments: gamemode_mutate and leprechaun_mutate copy the
        # tree with a content/ directory inside the work dir, so theirs read
        # os.path.join(W, 'content', 'tools', 'x_battery.py'). Both of them were reported as
        # unreadable - which is this check failing on its own regex rather than on a harness.
        got = re.findall(r"os\.path\.join\(W,(?: '[\w.]+',)* 'tools', '(\w+\.py)'\)", src)
        got += [m for m in re.findall(r"return '(?:tools/)?(\w+\.py)'", src)]
        out[fn[:-3]] = (sorted(set(got)), src)
    return out


def messages(checker):
    """Every check message a checker prints, on a clean tree."""
    r = subprocess.run([sys.executable, os.path.join(TOOLS, checker)],
                       capture_output=True, text=True, cwd=C)
    out = []
    for line in r.stdout.split('\n'):
        t = line.strip()
        if t.startswith('ok ') or t.startswith('FAIL '):
            out.append(re.sub(r'^(ok|FAIL)\s+', '', t))
    return out


def muts(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, name + '.py'))
    m = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [name]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = argv
    return m.MUTS


def main():
    verbose = '-v' in sys.argv
    H = harnesses()
    cache = {}
    total = unmatched = 0

    print('%d mutation harnesses' % len(H))
    print()

    for name in sorted(H):
        checkers, src = H[name]
        # ---- does it attribute at all?
        attributes = 'caught by its own check' in src
        check(attributes,
              '%s says which check caught each mutation, rather than only that one did' % name)
        if not checkers:
            check(False, '%s: could not tell which checker it runs, so its labels cannot be '
                         'audited - name it as os.path.join(W, ..., \'tools\', \'x.py\')' % name)
            continue

        hay = []
        for c in checkers:
            if c not in cache:
                cache[c] = messages(c)
            hay += cache[c]
        check(hay, '%s\'s checker prints checks this can read: %s'
                   % (name, ', '.join(checkers)))

        bad = []
        n = 0
        for _p, _f, _r, why in muts(name):
            label = why.split(' ', 1)[1] if why[:1].isdigit() else why
            if label.endswith(OTHER_CHECKER):
                continue
            for suf in SUFFIX_ONLY:
                if label.endswith(suf):
                    label = label[:-len(suf)].strip()
            n += 1
            if not any(label in h for h in hay):
                bad.append(why)
        total += n
        unmatched += len(bad)
        check(not bad,
              '%s: every label is the wording of a check its own checker prints, so "caught by '
              'its own check" can actually happen: %s'
              % (name, '%d of %d match nothing' % (len(bad), n) if bad else 'all %d' % n))
        if bad and verbose:
            for b in bad:
                print('         %s' % b)

    print()
    print('%d labels audited, %d matching no check' % (total, unmatched))
    print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
