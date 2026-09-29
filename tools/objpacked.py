#!/usr/bin/env python3
"""Decode the PACKED obj table and answer questions about it, not about the configs.

WHY THIS EXISTS. Twice now a claim about how an item behaves has been wrong because it was reasoned
from the .obj configs rather than read from the artefact the server actually loads. The worst was
the notes round: a whole engine patch was written, built and discarded because tools/pack already
derived the forward certificate link, and nothing had ever loaded the packed data to look.

The configs are source. data/pack/server/obj.dat is the artefact. A rule about the artefact has to
be checked against the artefact.

HOW IT SELF-VALIDATES. The server stream is one count followed by every obj's opcodes terminated
by a 0, so there are no offsets to resync on: a single mis-sized read desynchronises everything
after it. That means the decode cannot be subtly wrong and still produce 8,000 debugnames that
match pack/obj.pack - so the name check below is not a nicety, it is the proof that every other
number this prints came off the right bytes. It is checked first and nothing else is reported if
it fails.

Needs a build to have run: it reads ../engine/data/pack/server/obj.dat.

    python3 tools/objpacked.py                 # the graceful/outfit report, and the checks
    python3 tools/objpacked.py <name> [...]    # dump what the artefact says about these objs
"""
import io, json, os, struct, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# WHERE THE ENGINE IS. In order: an explicit path argument, then $LOSTCITY_ENGINE, then a sibling
# clone under either name it goes by - "engine" in CI and in the cloud, "Engine-TS" on the laptop.
# The environment variable is what tools/poh_mutate.py sets: it copies the CONTENT tree to a
# scratch directory, so a sibling lookup from there finds nothing, and a check that cannot look is
# a check that fails for every mutation and drowns out the one under test.
def enginedirs():
    env = os.environ.get('LOSTCITY_ENGINE')
    roots = ([env] if env else []) + [os.path.join(C, '..', e) for e in ('engine', 'Engine-TS')]
    return roots

DEFAULTS = [os.path.join(r, 'data', 'pack', 'server', 'obj.dat') for r in enginedirs()]
DEFAULT = next((d for d in DEFAULTS if os.path.exists(d)), DEFAULTS[0])

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1


class P:
    def __init__(self, d):
        self.d, self.p = d, 0

    def g1(self):
        self.p += 1
        return self.d[self.p - 1]

    def g1b(self):
        v = self.g1()
        return v - 256 if v > 127 else v

    def g2(self):
        self.p += 2
        return struct.unpack('>H', self.d[self.p - 2:self.p])[0]

    def g2s(self):
        self.p += 2
        return struct.unpack('>h', self.d[self.p - 2:self.p])[0]

    def g3(self):
        return (self.g1() << 16) | self.g2()

    def g4s(self):
        self.p += 4
        return struct.unpack('>i', self.d[self.p - 4:self.p])[0]

    def gjstr(self):
        out = bytearray()
        while True:
            b = self.g1()
            if b == 10:
                break
            out.append(b)
        return out.decode('latin-1')


def decode_one(buf):
    """One obj's opcodes, exactly as ObjType.decodeType reads them. Returns a dict."""
    o = {'params': {}}
    while True:
        code = buf.g1()
        if code == 0:
            return o
        elif code == 1:   o['model'] = buf.g2()
        elif code == 2:   o['name'] = buf.gjstr()
        elif code == 3:   o['desc'] = buf.gjstr()
        elif code in (4, 5, 6):  buf.g2()
        elif code in (7, 8):     buf.g2s()
        elif code == 10:  buf.g2()
        elif code == 11:  o['stackable'] = True
        elif code == 12:  o['cost'] = buf.g4s()
        elif code == 13:  o['wearpos'] = buf.g1()
        elif code == 14:  o['wearpos2'] = buf.g1()
        elif code == 15:  pass
        elif code == 16:  o['members'] = True
        elif code == 23:  buf.g2(); buf.g1b()
        elif code == 24:  buf.g2()
        elif code == 25:  buf.g2(); buf.g1b()
        elif code == 26:  buf.g2()
        elif code == 27:  o['wearpos3'] = buf.g1()
        elif 30 <= code < 35:  o.setdefault('op', {})[code - 30] = buf.gjstr()
        elif 35 <= code < 40:  o.setdefault('iop', {})[code - 35] = buf.gjstr()
        elif code == 40:
            # THE RECOLOUR LIST, kept rather than skipped. Twelve of the Max cape variants have no
            # model of their own and are the plain cape recoloured, so "did the recolour survive
            # the pack" is the only question that decides whether six of them look right - and it
            # is a question about the artefact, not the config. The config writes rgb15 and the
            # packer converts with ColorConversion.rgb15toHsl16, so what is stored here is hsl16
            # and comparable with the OSRS cache's own numbers directly.
            o['recol'] = [(buf.g2(), buf.g2()) for _ in range(buf.g1())]
        elif code == 75:  o['weight'] = buf.g2s()
        elif code in (78, 79, 90, 91, 92, 93, 94, 95):  buf.g2()
        elif code == 96:  buf.g1()
        elif code == 97:  o['certlink'] = buf.g2()
        elif code == 98:  o['certtemplate'] = buf.g2()
        elif 100 <= code < 110:
            buf.g2(); buf.g2()
        elif code in (110, 111, 112):  buf.g2()
        elif code in (113, 114):  buf.g1b()
        elif code == 115:  buf.g1()
        elif 120 <= code < 128:  o.setdefault('wearop', {})[code - 120] = buf.gjstr()  # worn options
        elif code == 201:  buf.g2()
        elif code == 249:
            for _ in range(buf.g1()):
                key = buf.g3()
                if buf.g1():
                    o['params'][key] = buf.gjstr()
                else:
                    o['params'][key] = buf.g4s()
        elif code == 250:  o['debugname'] = buf.gjstr()
        else:
            raise SystemExit('objpacked: unknown obj opcode %d at byte %d - the decode is out of '
                             'step with the engine, so nothing it prints can be trusted'
                             % (code, buf.p))


def load(path):
    buf = P(io.open(path, 'rb').read())
    count = buf.g2()
    return [decode_one(buf) for _ in range(count)], count


def packnames(kind):
    """id -> name from a pack file, or None when it is not there to be read.

    obj.pack is tracked, but param.pack is GENERATED - the deploy deletes it and the build writes
    it again - so a fresh clone with no build has one and not the other. This used to raise
    FileNotFoundError from inside main(), which the battery reported as a bare non-zero exit with
    no line saying why. A check whose own condition raises is a crash and not a check; this
    returns None and lets main() say what is missing.
    """
    fp = os.path.join(C, 'pack', '%s.pack' % kind)
    if not os.path.exists(fp):
        return None
    out = {}
    for line in io.open(fp, encoding='utf-8'):
        if '=' in line:
            a, b = line.strip().split('=', 1)
            out[int(a)] = b
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith('.dat') else DEFAULT
    if not os.path.exists(path):
        print('no packed obj table at %s - run the build first' % path)
        return 2

    objs, count = load(path)
    names = packnames('obj')
    _params = packnames('param')
    missing = [k for k, v in (('obj', names), ('param', _params)) if v is None]
    if missing:
        print('no %s in pack/ - it is generated, so run the build first'
              % ' or '.join('%s.pack' % m for m in missing))
        return 2
    params = {v: k for k, v in _params.items()}

    # ---- the proof that the decode is aligned, before anything else is reported
    decoded = {i: o.get('debugname') for i, o in enumerate(objs) if o.get('debugname')}
    wrong = [i for i, n in decoded.items() if names.get(i) != n]
    print('%d objs in the packed table, %d of them named' % (count, len(decoded)))
    check(not wrong, 'every packed debugname is the name pack/obj.pack gives that id, so the '
                     'decode is aligned and the rest of this is about real bytes: %s'
                     % ('all of them' if not wrong else
                        ['%d packed=%s pack=%s' % (i, decoded[i], names.get(i)) for i in wrong[:3]]))
    if wrong:
        return 1

    byname = {n: objs[i] for i, n in decoded.items()}

    # ---- a dump mode, for asking about specific objs
    asked = [a for a in sys.argv[1:] if not a.endswith('.dat')]
    if asked:
        for a in asked:
            o = byname.get(a)
            if not o:
                print('  %s: not in the packed table' % a)
                continue
            ps = {names.get(k, k) if False else params.get(k, k): v for k, v in o['params'].items()}
            print('  %-22s weight=%s params=%s' % (a, o.get('weight', 0), ps or '{}'))
        return 0

    # ---- Graceful, which is the round this was written for
    print()
    print('Graceful, as the server will read it')
    # THE EXPECTED NUMBERS ARE NOT WRITTEN HERE. They come out of tools/gracefulspec.json, which
    # is where the wiki figures, Corey's chosen total and the arithmetic that turns it into six
    # whole percents all live. A number typed twice is a number that drifts once: this file asks
    # whether the ARTEFACT agrees with the spec, and poh_battery.py group 64b asks whether
    # the CONFIGS do, so a spec edited alone goes red in both directions.
    spec = json.load(open(os.path.join(C, 'tools', 'gracefulspec.json')))
    GRACE = {n: (int(round(spec['osrs']['weight_kg'][n] * 1000)), pct)
             for n, pct in spec['result']['per_piece_pct'].items()}
    WANT_TOTAL = spec['result']['total_pct']
    WANT_WEIGHT = int(round(spec['osrs']['weight_total_kg'] * 1000))
    OSRS_TOTAL = spec['osrs']['full_set_total_pct']
    restore = params.get('energy_restore')
    check(restore is not None, 'the energy_restore param is in pack/param.pack, so an obj can '
                               'carry it at all')
    bad = []
    for n, (grams, pct) in sorted(GRACE.items()):
        o = byname.get(n)
        if not o:
            bad.append('%s is not in the packed table' % n)
            continue
        if o.get('weight', 0) != grams:
            bad.append('%s weight packed as %s, wanted %s' % (n, o.get('weight', 0), grams))
        got = o['params'].get(restore)
        if got != pct:
            bad.append('%s energy_restore packed as %s, wanted %s' % (n, got, pct))
    check(not bad, "each Graceful piece's weight and energy_restore survived the pack, negative "
                   'weights included: %s' % (bad[:3] or 'all six'))

    tot_w = sum(byname[n].get('weight', 0) for n in GRACE if n in byname)
    tot_p = sum(byname[n]['params'].get(restore, 0) for n in GRACE if n in byname)
    check(tot_w == WANT_WEIGHT, 'the six together take OSRS\'s weight off a player, read back out '
                                'of the artefact rather than added up from the config: %s grams, '
                                'wanted %s' % (tot_w, WANT_WEIGHT))
    check(tot_p == WANT_TOTAL, 'and the six restore run energy by the spec\'s total, read out of '
                               'the artefact - a departure above OSRS\'s own %s%% full set, asked '
                               'for by name: %s percent, wanted %s'
                               % (OSRS_TOTAL, tot_p, WANT_TOTAL))

    # ---- the Max cape variants, if they are in this build yet
    vspec = os.path.join(C, 'tools', 'maxcapevariantspec.json')
    if os.path.exists(vspec):
        print()
        print('The Max cape variants, as the server will read them')
        VS = json.load(open(vspec))
        pmap = {v: k for k, v in VS['param_ids'].items()}     # name -> OSRS param id
        vbad, rbad, nbad = [], [], []
        for v in VS['variants']:
            for part, suffix in (('cape', '_max_cape'), ('hood', '_max_hood')):
                name = v['key'] + suffix
                obj = byname.get(name)
                if not obj:
                    nbad.append(name)
                    continue
                # the recolour list, straight against the OSRS cache's own pairs
                want = [tuple(x) for x in (v[part]['recol'] or [])]
                got = [tuple(x) for x in (obj.get('recol') or [])]
                if got != want:
                    rbad.append('%s recol packed as %s, the OSRS table says %s'
                                % (name, got[:2] or 'none', want[:2] or 'none'))
            obj = byname.get(v['key'] + '_max_cape')
            if not obj:
                continue
            for pname, pv in (v['bonuses'] or {}).items():
                pid = params.get(pname)
                if pid is None:
                    vbad.append('%s: no param called %s in pack/param.pack' % (v['key'], pname))
                    continue
                if obj['params'].get(pid) != pv:
                    vbad.append('%s %s packed as %s, wanted %s'
                                % (v['key'], pname, obj['params'].get(pid), pv))
        # COUNTED FROM THE SPEC. The loop above always was; only these sentences said "sixteen"
        # and "eight", and they were wrong the day a ninth variant arrived while the checks were
        # still right. A message that states a number has to get it from the same place the check
        # does.
        npieces, nvariants = 2 * len(VS['variants']), len(VS['variants'])
        check(not nbad, 'all %d variant pieces are in the packed table: %s'
                        % (npieces, nbad[:4] or 'all %d' % npieces))
        check(not vbad, "each variant cape's combat bonuses survived the pack, read out of the "
                        'artefact: %s' % (vbad[:3] or 'all %d agree' % nvariants))
        # THE SERVER TABLE CARRIES NO RECOLOURS AT ALL, and finding that out is worth more than
        # the check that went here. A recolour is a CLIENT concern - the model is recoloured when
        # it is drawn - so ObjType.decodeType never reads opcode 40 into the server's obj.dat and
        # every variant comes back with an empty list. So this cannot be the place the recolours
        # are verified, and the check that tried to was deleted rather than weakened.
        #
        # tools/maxvariantrender.py is where they ARE verified, and it checks the thing that
        # actually matters: that each source colour exists on the model it is applied to. A pair
        # that matches nothing is a piece that renders as a plain Max cape.
        check(not [x for x in rbad if 'packed as none' not in x],
              'the server obj table carries no recolour lists, which is expected - a recolour is '
              'drawn by the client - so nothing here disagrees with the OSRS table either: %s'
              % (len(rbad) and '%d empty, as they should be' % len(rbad) or 'nothing to compare'))

    # ---- nothing else in the game carries the param by accident
    others = sorted(n for n, o in byname.items()
                    if restore is not None and restore in o['params'] and n not in GRACE)
    check(not others, 'and no other obj in the game carries energy_restore, so the bonus cannot '
                      'be picked up from somewhere unintended: %s' % (others[:5] or 'none'))

    print()
    print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
