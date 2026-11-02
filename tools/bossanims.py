#!/usr/bin/env python3
"""Does each fighting npc's attack, block and death animation actually MOVE its own model?

tools/npcanims.py answers a different question - "does a sequence named for this creature exist and
go unwired" - and it now reports zero. This asks the one that question cannot reach: an npc whose
combat params name a sequence that exists, is wired, and does nothing to that particular mesh.

HOW THE CLIENT DECIDES, which is the whole of this check. Model.method369 applies one transform to
one vertex-label group:

        if (var9 < this.field1225.length) { ... }        // var9 is the label group

`field1225` is the model's own label-to-vertices table, built from the vertex-label block in the
.ob2 and sized by the highest label the mesh uses. A transform aimed at a group the mesh does not
have falls off that `if` and is **silently discarded** - no exception, no log, nothing in the engine
to notice. A sequence whose groups are all out of range is a boss standing perfectly still while it
hits you; one whose groups partly overlap is a boss that moves the wrong half of itself.

So the test is a containment test, and it needs no render and no running world:

  * `models/anim_<n>.anim` is one frame set. The client's AnimFrame.method262 reads the four section
    lengths off the last eight bytes, the frame ids out of the head (`total g2`, then
    `total x (id g2, groupCount g1)`), and ONE AnimBase after the del block - whose `labels` are the
    groups every frame in that set is allowed to move.
  * a `.seq` config names its frames (`frame1=anim_31644`) and `pack/anim.pack` maps name to id, so
    a sequence's label groups are its set's.
  * an npc's `model1..N` are .ob2 files under `models/`, and the trailer's f_vlabel flag says
    whether a vertex-label block is there; the highest label in it is the mesh's table size.

WHAT WAS TRIED AND IS WRONG. Comparing the SET a combat sequence lives in against the set the npc's
own readyanim/walkanim live in looks like the obvious test and gives 115 false positives at level
100 alone: the God Wars knights stand on a converted 474 set and swing on 377's native
human_sword_slash, and both are correct because both are human. Comparing AnimBase CONTENT is no
better - a base only lists the groups that one animation touches, so a stand and a slash on the same
creature differ legitimately. Only the mesh can say, which is what the client does.

  python tools/bossanims.py                 every fighting npc, worst first
  python tools/bossanims.py --level 100     only npcs at or above that combat level
  python tools/bossanims.py --npc kalphite  only npcs whose config name matches
  python tools/bossanims.py --verbose       show the ones that are fine as well

WHAT IT STILL CANNOT SEE. A sequence on a mesh it fits can be the wrong sequence - the README for
tools/clientprobe records two of Zulrah's colours "diving" by playing the rise, whose first frame is
the snake not being there. For that, render it: tools/models/posepreview.py poses a mesh with a
sequence frame by frame, and tools/clientprobe/PoseRender.java does the same through the client's own
AnimFrame and Pix3D.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, 'models')
SCRIPTS = os.path.join(ROOT, 'scripts')

# combat.param's own fallbacks, read by skill_combat/scripts/npc when a param is absent.
FALLBACK = {
    'attack_anim': 'human_unarmedpunch',
    'defend_anim': 'human_unarmedblock',
    'death_anim': 'human_death',
}


def packmap(name):
    out = {}
    with open(os.path.join(ROOT, 'pack', name + '.pack'), encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if '=' in line:
                i, n = line.split('=', 1)
                out[int(i)] = n
    return out


def anim_sets():
    """frame id -> (set name, frozenset of label groups that set's frames may move)."""
    out = {}
    for fn in sorted(os.listdir(MODELS)):
        if not fn.endswith('.anim'):
            continue
        with open(os.path.join(MODELS, fn), 'rb') as fh:
            b = fh.read()
        if len(b) < 10:
            continue
        g2 = lambda o: int.from_bytes(b[o:o + 2], 'big')
        head_len, tran1, tran2, dl = g2(len(b) - 8), g2(len(b) - 6), g2(len(b) - 4), g2(len(b) - 2)
        total = g2(0)
        if head_len + 2 > len(b) or total * 3 > head_len:
            continue
        # AnimBase: size g1 | types[size] g1 | per group: count g1 + that many label bytes
        p = head_len + 2 + tran1 + tran2 + dl
        if p >= len(b) - 8:
            continue
        n = b[p]
        q = p + 1 + n
        groups = set()
        for _ in range(n):
            if q >= len(b):
                break
            c = b[q]; q += 1
            groups.update(b[q:q + c]); q += c
        groups = frozenset(groups)
        name = fn[:-5]
        for k in range(total):
            out[g2(2 + k * 3)] = (name, groups)
    return out


def model_labels(path):
    """The highest vertex label + 1 for one .ob2, or None when the mesh carries no labels."""
    with open(path, 'rb') as fh:
        b = fh.read()
    if len(b) < 18:
        return None
    t = len(b) - 18
    g2 = lambda o: int.from_bytes(b[o:o + 2], 'big')
    vcount, fcount, tcount = g2(t), g2(t + 2), b[t + 4]
    f_tex, f_pri, f_alpha, f_flabel, f_vlabel = b[t + 5], b[t + 6], b[t + 7], b[t + 8], b[t + 9]
    if f_vlabel != 1:
        return 0
    # the client's own offset walk (Model.method357), as far as the vertex-label block
    o = vcount + fcount
    if f_pri == 255:
        o += fcount
    if f_flabel == 1:
        o += fcount
    if f_tex == 1:
        o += fcount
    if o + vcount > len(b):
        return None
    return max(b[o:o + vcount], default=-1) + 1


def config_blocks(ext):
    for dirpath, _dirs, files in os.walk(SCRIPTS):
        for fn in files:
            if not fn.endswith('.' + ext):
                continue
            path = os.path.join(dirpath, fn)
            name, body = None, {}
            with open(path, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    line = line.strip()
                    m = re.match(r'^\[([a-zA-Z0-9_]+)\]$', line)
                    if m:
                        if name:
                            yield name, body, path
                        name, body = m.group(1), {}
                        continue
                    if not name or '=' not in line or line.startswith('//'):
                        continue
                    k, v = line.split('=', 1)
                    body.setdefault(k.strip(), []).append(v.strip())
            if name:
                yield name, body, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=int, default=0)
    ap.add_argument('--npc')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    anim_ids = {n: i for i, n in packmap('anim').items()}
    sets = anim_sets()

    # ---------------------------------------------------------------- sequences -> label groups
    seq_groups, seq_bad = {}, {}
    for name, body, _p in config_blocks('seq'):
        groups, unknown = set(), []
        for key, vals in body.items():
            if not re.match(r'^frame\d+$', key):
                continue
            for v in vals:
                fid = anim_ids.get(v)
                hit = sets.get(fid) if fid is not None else None
                if hit is None:
                    unknown.append(v)
                else:
                    groups |= hit[1]
        seq_groups[name] = groups
        if unknown:
            seq_bad[name] = unknown

    # ---------------------------------------------------------------- models -> label table size
    model_file = {}
    for dirpath, _d, files in os.walk(MODELS):
        for fn in files:
            if fn.endswith('.ob2'):
                model_file.setdefault(fn[:-4], os.path.join(dirpath, fn))
    label_cache = {}

    def labels_of(model_name):
        if model_name not in label_cache:
            p = model_file.get(model_name)
            label_cache[model_name] = model_labels(p) if p else None
        return label_cache[model_name]

    rows = []
    for name, body, path in config_blocks('npc'):
        if a.npc and a.npc.lower() not in name.lower():
            continue
        if 'multinpc' in body:            # a shell carries no art of its own
            continue
        hp = body.get('hitpoints', ['0'])[0]
        ops = [v for k, vs in body.items() if re.match(r'^op\d$', k) for v in vs]
        if not ((hp.isdigit() and int(hp) > 0) or any('Attack' in o for o in ops)):
            continue
        lvl = body.get('vislevel', ['0'])[0]
        lvl = int(lvl) if lvl.isdigit() else 0
        if lvl < a.level:
            continue

        # the biggest label table across the npc's merged models is what a transform is tested against
        table, unknown_model = 0, False
        for k, vs in body.items():
            if not re.match(r'^model\d*$', k):
                continue
            for v in vs:
                n = labels_of(v)
                if n is None:
                    unknown_model = True
                else:
                    table = max(table, n)
        if table == 0 and not unknown_model:
            continue                      # a mesh with no labels animates with nothing; not this audit

        # CALIBRATION. readyanim and walkanim come out of the cache's own npc record, so they are
        # this creature's real animations and whatever they do is correct by definition. If they
        # also reach past the mesh's table - and they nearly always do, because one frame set serves
        # a creature's whole family and the biggest variant sets the group count - then reaching
        # past it is normal and only a TOTAL miss means anything.
        own = set()
        for key in ('readyanim', 'walkanim'):
            for v in body.get(key, []):
                for seq in v.split(','):
                    own |= seq_groups.get(seq.strip(), set())
        own_outside = sorted(g for g in own if g >= table)

        dead, suspect, off = [], [], []
        for param, fb in FALLBACK.items():
            got = None
            for v in body.get('param', []):
                if v.startswith(param + ','):
                    got = v.split(',', 1)[1].strip()
            if got == 'null':
                # an explicit null is a DECISION, not an omission. Zulrah's attack and defend are
                # both null with a long comment above them: playing the attack animation set off a
                # flicker nobody could find, so it was taken out on purpose. A tool cannot read
                # intent, but it can tell "somebody wrote null here" from "nobody wrote anything".
                off.append(param)
                continue
            using, how = (got, '') if got else (fb, ' (the fallback, no param)')
            if using not in seq_groups:
                dead.append('%s=%s%s: no such sequence' % (param, using, how))
                continue
            if using in seq_bad:
                dead.append('%s=%s%s: frames in no .anim set (%s)'
                            % (param, using, how, ', '.join(seq_bad[using][:3])))
                continue
            groups = seq_groups[using]
            if not groups:
                dead.append('%s=%s%s: the sequence moves no label group at all' % (param, using, how))
                continue
            outside = sorted(g for g in groups if g >= table)
            if len(outside) == len(groups):
                dead.append('%s=%s%s: every group it moves (%s) is outside this mesh\'s %d, so the '
                            'animation does nothing at all'
                            % (param, using, how, ','.join(map(str, outside[:6])), table))
            elif outside and not own_outside and len(outside) * 2 > len(groups):
                # worse than the creature's own stand and walk, which fit exactly - and by more
                # than half its groups, because a two-group overshoot is the family-variant case
                # again (troll_attack reaches two past troll_general's own mesh and is correct).
                suspect.append('%s=%s%s: %d of %d groups outside this mesh\'s %d (%s), where its own '
                               'stand and walk fit exactly'
                               % (param, using, how, len(outside), len(groups), table,
                                  ','.join(map(str, outside[:6]))))
        rows.append((lvl, name, table, dead, suspect, bool(own_outside), os.path.relpath(path, ROOT), off))

    rows.sort(key=lambda r: (-r[0], r[1]))
    dead_rows = [r for r in rows if r[3]]
    susp_rows = [r for r in rows if r[4] and not r[3]]
    loose = sum(1 for r in rows if r[5])

    for title, group, key in (('BROKEN - the animation cannot play', dead_rows, 3),
                              ('WRONG RIG - a human animation on a mesh that is not human', susp_rows, 4)):
        if not group:
            continue
        print('==== %s' % title)
        for row in group:
            print('%-34s level %-5s labels %-4s %s' % (row[1][:34], row[0] or '-', row[2], row[6]))
            for p in row[key]:
                print('    %s' % p)
        print('')
    if a.verbose:
        print('==== fine')
        for row in rows:
            if not row[3] and not row[4]:
                print('%-34s level %-5s labels %-4s' % (row[1][:34], row[0] or '-', row[2]))
        print('')
    offs = [r for r in rows if r[7] and not r[3] and not r[4]]
    if offs:
        print('==== SWITCHED OFF ON PURPOSE (param=...,null)')
        for row in offs:
            print('%-34s level %-5s %s: %s' % (row[1][:34], row[0] or '-', ', '.join(row[7]), row[6]))
        print('')
    print('%d fighting npcs with a labelled mesh checked' % len(rows))
    print('  %d whose animation cannot play at all' % len(dead_rows))
    print('  %d on an animation that misses more than half this mesh, where its own stand fits' % len(susp_rows))
    print('  %d with an animation deliberately set to null' % len(offs))
    print('  %d whose own cache-stated stand or walk also reaches past it, which is why a partial'
          % loose)
    print('    overshoot on its own is not reported: one frame set serves a whole family.')
    return 1 if dead_rows or susp_rows else 0


if __name__ == '__main__':
    sys.exit(main())
