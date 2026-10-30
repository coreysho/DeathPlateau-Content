"""Battery for the face priorities of every model a player wears.

WHY THIS FILE EXISTS. On 30 October all 164 cape-slot models were moved to priority 10, the
client's depth-sorted group, to stop them painting themselves over armour they are behind. It was
signed off with a sweep that reported zero disagreement on all 164 from the front AND from the
back - and that sweep was vacuous. It compared each model as shipped against the same model forced
to priority 10, and the models on disk were already at priority 10, so it was comparing a drawing
with itself. The real before-and-after, against the bytes the models were imported with, is 63,742
pixels gained and 529,170 lost: 152 of the 164 came out worse, and from behind the armour under
the cape is painted straight through the middle of it. That is a hole in the back of the cape,
and it is what shipped.

So the rule here is not "capes must not be at 10". It is that the priorities of a worn model are
LOAD-BEARING and a change to them has to be argued for one model at a time. The table beside this
file records what EVERY worn model ships with - every slot, not just the back - and a change to any
of them fails this battery until the table is updated, which is the point where someone has to
render the thing from the other side.

The slot widened on 30 October, when the Armadyl chainskirt turned out to have the same shape of
fault in the other direction: 20 of its 234 faces hang below the ankle line, inside the boot, and
at priority 1 against a boot's 0 they are painted over it - the legs drawn through the boots. Those
twenty went to group 0, where the client depth-sorts within a priority group, and the feet come out
2,700 pixels more visible across five boots and the bare foot, at every angle and both poses. It is
NOT a rule for every legs model: a robe's hem is meant to hang over a boot, and moving its hem the
same way bursts the boot through it ten times over. The chainskirt's sub-ankle geometry is 22 units
wide against a 17-unit boot - a greave grazing it - where those robes are 33 and 43.

    python3 tools/wornpriority_battery.py
    python3 tools/wornpriority_battery.py --update     # after measuring, not before

Measure with tools/models/WearSweep.java: --selfdiff for what a change does to the model itself,
--culprits for the individual faces at fault, both against the AUTHORED bytes and a gender-matched
kit.
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(C, 'tools', 'wornpriorities.txt')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1


def g1(b, o): return b[o]
def g2(b, o): return (b[o] << 8) | b[o + 1]


def priorities(path):
    """The per-face priority of a 377 .ob2, as a {priority: faces} histogram.

    Only the header and the priority section are decoded. Model.java reads the trailer backwards
    from the end of the file and then walks the body in a section order that is NOT the order the
    flag bytes appear in; what matters here is only that the priority section, when there is one,
    sits straight after the face types.
    """
    b = open(path, 'rb').read()
    h = len(b) - 18
    vcount, fcount, tcount = g2(b, h), g2(b, h + 2), g1(b, h + 4)
    f_pri = g1(b, h + 6)
    if f_pri != 255:
        return {f_pri: fcount}            # one priority for the whole model, stored in the header
    o = vcount + fcount                   # vertex flags, then face types
    out = {}
    for i in range(fcount):
        out[b[o + i]] = out.get(b[o + i], 0) + 1
    return out


# every slot a player can wear something in; a model is listed once however many slots name it
SLOTS = ('hat', 'back', 'front', 'righthand', 'torso', 'lefthand', 'legs', 'head', 'hands', 'feet')


def wornmodels():
    """Every manwear/womanwear model named by an obj config with a wearpos."""
    names = set()
    for root, _, files in os.walk(C):
        if os.sep + '.git' in root: continue
        for f in files:
            if not f.endswith('.obj'): continue
            back, models = False, []
            def flush():
                if back: names.update(models)
            for ln in open(os.path.join(root, f), encoding='utf-8', errors='replace'):
                ln = ln.strip()
                if ln.startswith('['):
                    flush(); back, models = False, []
                elif ln.startswith('wearpos=') and ln.split('=', 1)[1].strip() in SLOTS:
                    back = True
                elif ln.startswith('manwear=') or ln.startswith('womanwear='):
                    v = ln.split('=', 1)[1].split(',')[0].strip()
                    if v: models.append(v)
            flush()
    out = {}
    for n in sorted(names):
        p = os.path.join(C, 'models', 'obj', n + '.ob2')
        if os.path.exists(p): out[n] = p
    return out


def histogram(path):
    return ' '.join('%d:%d' % kv for kv in sorted(priorities(path).items()))


def main():
    models = wornmodels()
    rows = {n: histogram(p) for n, p in models.items()}

    if '--update' in sys.argv:
        with open(TABLE, 'w') as fh:
            fh.write('# Face priorities of every back-slot model, one per line: name, then\n'
                     '# priority:faces for each group the model uses.\n'
                     '#\n'
                     '# A LINE HERE IS A CLAIM THAT SOMEBODY LOOKED AT THE BACK VIEW. Priority 10\n'
                     '# is the client\'s depth-sorted group and it is the right answer for a cape\n'
                     '# only where the measurement says so - see tools/capepriority_battery.py.\n')
            for n in sorted(rows):
                fh.write('%s %s\n' % (n, rows[n]))
        print('wrote %s (%d models)' % (TABLE, len(rows)))
        return 0

    check(os.path.exists(TABLE), 'tools/wornpriorities.txt is checked in')
    if not os.path.exists(TABLE):
        print(); print('1 FAILED'); return 1
    want = {}
    for ln in open(TABLE):
        ln = ln.split('#')[0].strip()
        if not ln: continue
        f = ln.split(None, 1)
        want[f[0]] = f[1].strip() if len(f) > 1 else ''

    check(set(want) == set(rows),
          'the table lists exactly the %d worn models the configs name%s'
          % (len(rows), '' if set(want) == set(rows) else
             ': missing %s, stale %s' % (sorted(set(rows) - set(want))[:4],
                                         sorted(set(want) - set(rows))[:4])))

    moved = [n for n in sorted(rows) if n in want and rows[n] != want[n]]
    check(not moved,
          'no worn model\'s face priorities have moved without the table moving with them%s'
          % ('' if not moved else ': ' + ', '.join(
              '%s %s -> %s' % (n, want[n], rows[n]) for n in moved[:4])))

    # The specific regression this file was written for: a blanket pass that puts every face of
    # every cape in the depth-sorted group. The table above would catch it, but it is worth
    # saying out loud which models are allowed to be there. Hands and weapons live at 10 and 11
    # by the client's own convention, so this is a count that has to match, not a small number.
    at10 = sorted(n for n in rows if rows[n] == '10:%d' % sum(priorities(models[n]).values()))
    allowed = sorted(n for n in want if want[n].startswith('10:') and ' ' not in want[n])
    check(at10 == allowed,
          'the %d models wholly in the depth-sorted group are the ones the table allows%s'
          % (len(allowed), '' if at10 == allowed else
             ': unexpected %s' % sorted(set(at10) - set(allowed))[:6]))

    print()
    print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
