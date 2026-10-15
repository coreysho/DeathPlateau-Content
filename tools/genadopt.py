#!/usr/bin/env python3
"""Adopt a panel out of the 377 cache: rename it, name its components, move it, repack it.

WHY THIS IS A TOOL AND NOT A HAND EDIT. scripts/interfaces/ holds 280 interfaces straight out of
the cache. 213 still carry their cache id and every component in them is com_<n>, so a script that
used one would read `if_settext(inter_53:com_21, ...)` and nobody, including whoever wrote it,
could say what com_21 was. Adopting one means renaming the interface and its components and
re-taking every id in pack/interface.pack and pack/interface.order. That was done by hand once
(tools/genancientbook.py, for inter_267) and this round needed it six more times, which is the
moment it stops being a hand edit.

THE NAMES COME FROM THE PANEL'S OWN TEXT. A rule in tools/adoptspec.json matches components on one
field and a regex, and the regex's named groups feed the name template - so the smelt window's 32
buttons are named from what each button SAYS ("Smelt 1 @lre@Silver" -> smelt_1_silver), not from a
list somebody typed. That matters for one specific reason: the panel's column order is Bronze,
Iron, SILVER, STEEL, Gold... and smelting.struct lists the bars Bronze, Iron, STEEL, SILVER, Gold.
A hand-written list would have swapped two columns and nothing would have noticed.

`expect` on each rule is the count that must match. A panel that is not the one the spec thinks it
is fails the count rather than quietly renaming the wrong components.

WHAT IS NOT RENAMED. Anything no rule matches keeps its com_<n>. Nothing else names those, and a
name nobody uses is a name that goes stale.

THE FILE IS REWRITTEN LINE BY LINE. Only block headers, the `layer=`/`overlayer=` references that
follow a rename, and an added header comment change. Everything else - every coordinate, colour,
graphic, script operand - is copied through byte for byte, which is what makes "154 components
there, 154 here" a meaningful sentence in a battery rather than a coincidence.

    python3 tools/genadopt.py            # every panel in the spec
    python3 tools/genadopt.py smelt_window
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, 'tools/adoptspec.json')
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')


def read(p):
    return open(p, newline='').read()


def nl_of(t):
    return '\r\n' if t.count('\r\n') > t.count('\n') / 2 else '\n'


def blocks(text):
    """(name, kv, lines) per [block], in file order. The raw lines are kept so the rewrite can be
    line-level rather than a re-serialisation, which would reorder or reformat fields."""
    out, name, kv, buf = [], None, {}, []
    for raw in text.replace('\r\n', '\n').split('\n'):
        m = re.match(r'^\[([A-Za-z0-9_]+)\]\s*$', raw)
        if m:
            if name is not None or buf:
                out.append((name, kv, buf))
            name, kv, buf = m.group(1), {}, [raw]
            continue
        buf.append(raw)
        m = re.match(r'^([A-Za-z0-9_]+)=(.*)$', raw)
        if m:
            kv.setdefault(m.group(1), m.group(2).strip())
    if name is not None or buf:
        out.append((name, kv, buf))
    return out


def check_products(panel, blks):
    """The seven silver products are declared in the spec with the cache's own Make text and its
    own you-need-a-mould text, and both are asserted against the file. This is the same discipline
    as the smelt window's regex join, written longhand because the products cannot be told apart by
    a pattern - and it is still a join: a panel whose labels have moved fails here rather than
    naming the wrong slot."""
    prods = panel.get('products')
    if not prods:
        return None
    makes = [kv.get('text') for n, kv, _ in blks
             if kv.get('type') == 'text' and (kv.get('text') or '').startswith('Make')]
    needs = [kv.get('text') for n, kv, _ in blks
             if kv.get('type') == 'text' and (kv.get('text') or '').startswith('You need')]
    if makes != [p['make'] for p in prods]:
        raise SystemExit('%s: the Make labels are not what the spec declares\n  file: %r\n  spec: %r'
                         % (panel['iface'], makes, [p['make'] for p in prods]))
    if needs != [p['need'] for p in prods]:
        raise SystemExit('%s: the you-need labels are not what the spec declares\n  file: %r\n  spec: %r'
                         % (panel['iface'], needs, [p['need'] for p in prods]))
    return [p['key'] for p in prods]


def rename_map(panel, blks):
    """Which com_<n> becomes what. Rules run in spec order; naming one component twice, or two
    components the same, is an error rather than a silent overwrite."""
    parent = {n: kv['layer'] for n, kv, _ in blks if n and kv.get('layer')}
    keys = check_products(panel, blks)
    rename, taken = {}, set()
    for rule in panel['rules']:
        pat = re.compile(rule['pattern'])
        hits = []
        for n, kv, _ in blks:
            if not n:
                continue
            m = pat.match(kv.get(rule['field'], '') or '')
            if not m:
                continue
            target = n
            if rule.get('target') == 'parent':
                target = parent.get(n)
                if target is None:
                    raise SystemExit('%s: %s has no layer= to name' % (panel['iface'], n))
            hits.append((target, m.groupdict()))
        if len(hits) != rule['expect']:
            raise SystemExit('%s: rule %r matched %d, expected %d'
                             % (panel['iface'], rule['pattern'], len(hits), rule['expect']))
        for i, (target, groups) in enumerate(hits, 1):
            fields = dict(groups)
            fields['order'] = i
            # `group` turns a flat run of matches into per-cell numbering: the tan window's 32
            # buttons are four per cell in file order, so {cell} is 1..8 and {order} is 1..32.
            if rule.get('group'):
                fields['cell'] = (i - 1) // rule['group'] + 1
            if keys:
                fields['product'] = keys[i - 1]
            nm = rule['name'].format(**fields)
            if rule.get('lower'):
                nm = nm.lower()
            if target in rename:
                raise SystemExit('%s: %s matched twice (%s and %s)'
                                 % (panel['iface'], target, rename[target], nm))
            if nm in taken:
                raise SystemExit('%s: two components would be called %s' % (panel['iface'], nm))
            rename[target] = nm
            taken.add(nm)
    return rename


def adopt(panel):
    src = os.path.join(ROOT, panel['src'])
    dst = os.path.join(ROOT, panel['dst'])
    # Idempotent: after the first run the cache file is gone and the adopted one is the input. The
    # join is on text the rename does not touch, so it gives the same answer either way.
    from_cache = os.path.exists(src)
    raw = read(src if from_cache else dst)
    nl = nl_of(raw)
    blks = blocks(raw)
    # Re-reading our own output: drop the header written last time, or the file grows one copy per
    # run. blocks() files everything before the first [block] under the name None, and the cache
    # files have nothing there, so this can only ever remove a header this generator wrote.
    if not from_cache and blks and blks[0][0] is None:
        blks = blks[1:]
    rename = rename_map(panel, blks)

    out = []
    for name, kv, buf in blks:
        for ln in buf:
            m = re.match(r'^\[([A-Za-z0-9_]+)\]\s*$', ln)
            if m and m.group(1) in rename:
                out.append('[%s]' % rename[m.group(1)])
                continue
            m = re.match(r'^(layer|overlayer)=([A-Za-z0-9_]+)\s*$', ln)
            if m and m.group(2) in rename:
                out.append('%s=%s' % (m.group(1), rename[m.group(2)]))
                continue
            out.append(ln)

    head = [
        "// %s - THE 377 CACHE'S OWN PANEL, adopted, not rebuilt." % panel['iface'],
        '//',
        '// %s' % panel['what'],
        '//',
        '// GENERATED by tools/genadopt.py from %s. Edit tools/adoptspec.json,' % panel['src'],
        '// not this file. Every component not named by a rule keeps its com_<n>, because nothing',
        '// else refers to it. Everything but the headers and the layer references that follow',
        '// them is copied through byte for byte.',
        '',
    ]
    body = nl.join(head + out).rstrip('\r\n') + nl
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(body.encode('utf-8'))
    if from_cache and os.path.abspath(src) != os.path.abspath(dst):
        os.unlink(src)
    return [n for n, _, _ in blocks(body) if n], rename


def repack(panels):
    """Re-take every component id for the adopted interfaces in one pass.

    The interface KEEPS the id it already had in the pack - an interface id is what if_openmain
    puts on the wire and there is no reason to move it. Only the component rows are dropped and
    re-taken, because their names change.
    """
    pack = [l for l in read(PACK).replace('\r\n', '\n').split('\n') if l]
    order_raw = read(ORDER)
    onl = nl_of(order_raw)
    ids_order = [l for l in order_raw.replace('\r\n', '\n').split('\n') if l.strip()]

    old_for = {p['iface']: re.match(r'.*/(inter_\d+)\.if$', p['src']).group(1) for p in panels}
    keep, dropped, own, had = [], set(), {}, {}
    for l in pack:
        i, nm = l.split('=', 1)
        base = nm.split(':', 1)[0]
        hit = next((f for f, old in old_for.items() if base in (old, f)), None)
        if hit is None:
            keep.append(l)
        elif ':' not in nm:
            own[hit] = i
            keep.append('%s=%s' % (i, hit))
        else:
            dropped.add(i)
            # WHAT ID THIS COMPONENT ALREADY HAD. Every component of the panel is dropped here and
            # re-emitted below, and re-emitting them from max(used) + 1 moved the whole panel to
            # the end of the pack EVERY RUN - 474 components renumbered by a re-run that changed
            # nothing else, which is why windows_battery's "re-running them changes nothing" was
            # red. An interface id is part of what the packed artefact means, so a component whose
            # name has not changed gets its own id back and only a new name takes a new one. The
            # first adoption still allocates fresh, because that is when the names change: com_21
            # becomes smelt_1_silver and there is no old id under that name.
            had[(hit, nm.split(':', 1)[1])] = int(i)
    ids_order = [l for l in ids_order if l not in dropped]
    used = {int(l.split('=', 1)[0]) for l in keep}
    nxt = max(used) + 1
    mine = {}
    for p in panels:
        iface = p['iface']
        if iface not in own:
            raise SystemExit('%s has no id in interface.pack under %s or %s'
                             % (iface, old_for[iface], iface))
        got = []
        for n in p['_names']:
            i = had.get((iface, n))
            if i is None or i in used:
                while nxt in used:
                    nxt += 1
                i = nxt
                nxt += 1
            keep.append('%s=%s:%s' % (i, iface, n))
            ids_order.append(str(i))
            used.add(i)
            got.append(i)
        mine[iface] = got
    keep.sort(key=lambda l: int(l.split('=', 1)[0]))
    ids_order.sort(key=int)
    ids = [l.split('=', 1)[0] for l in keep]
    assert len(ids) == len(set(ids)), 'duplicate interface id'
    nms = [l.split('=', 1)[1] for l in keep]
    assert len(nms) == len(set(nms)), 'duplicate interface name'
    assert set(ids_order) == set(ids), 'interface.order and interface.pack disagree'
    open(PACK, 'w', encoding='utf-8', newline='').write('\n'.join(keep) + '\n')
    open(ORDER, 'w', encoding='utf-8', newline='').write(onl.join(ids_order) + onl)
    return mine, own


def main():
    spec = json.load(open(SPEC, encoding='utf-8'))
    want = sys.argv[1:] or None
    panels = [p for p in spec['panels'] if not want or p['iface'] in want]
    if not panels:
        raise SystemExit('no panel in tools/adoptspec.json called %s' % ', '.join(want or []))
    for p in panels:
        names, rename = adopt(p)
        p['_names'] = names
        p['_renamed'] = len(rename)
    mine, own = repack(panels)
    for p in panels:
        print('%-15s id %-6s %3d components, %2d named  <- %s'
              % (p['iface'], own[p['iface']], len(p['_names']), p['_renamed'], p['src']))


main()
