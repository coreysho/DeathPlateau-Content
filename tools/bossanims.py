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


# Files that NAME every npc in the game without spawning any of them. An npc that appears only in
# these is a record nothing can ever put in front of a player, and its animations cannot be a bug.
CATALOGUES = ('npc_drops.dbrow', 'npc_browser_ui.rs2', 'elemental_weakness.enum', 'npcdrops',
              'slayer_tasks.dbrow', 'task_name.enum', 'bossart', 'collectionlog')


def spawn_counts(names):
    """npc name -> (static map spawns, scripts that name it other than a catalogue)."""
    ids = {}
    with open(os.path.join(ROOT, 'pack', 'npc.pack'), encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if '=' in line:
                i, n = line.split('=', 1)
                if n in names:
                    ids[int(i)] = n
    onmap = {n: 0 for n in names}
    maps = os.path.join(ROOT, 'maps')
    if os.path.isdir(maps):
        for fn in os.listdir(maps):
            if not fn.endswith('.jm2'):
                continue
            with open(os.path.join(maps, fn), encoding='utf-8', errors='replace') as fh:
                sec = None
                for line in fh:
                    if line.startswith('===='):
                        sec = line.strip().strip('= ')
                        continue
                    if sec != 'NPC' or ':' not in line:
                        continue
                    try:
                        nid = int(line.split(':', 1)[1])
                    except ValueError:
                        continue
                    if nid in ids:
                        onmap[ids[nid]] += 1
    inscript = {n: 0 for n in names}
    want = re.compile(r'(' + '|'.join(re.escape(n) for n in names) + r')') if names else None
    for dirpath, _d, files in os.walk(SCRIPTS):
        for fn in files:
            if not fn.endswith(('.rs2', '.enum', '.dbrow')):
                continue
            if any(c in fn for c in CATALOGUES):
                continue
            with open(os.path.join(dirpath, fn), encoding='utf-8', errors='replace') as fh:
                body = fh.read()
            for m in set(want.findall(body)) if want else ():
                inscript[m] += 1
    return onmap, inscript


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
    ap.add_argument('--kit', metavar='NPC',
                    help='instead of auditing, list every sequence on this npc own rig - that is, '
                         'everything it could be wired to')
    a = ap.parse_args()

    anim_ids = {n: i for i, n in packmap('anim').items()}
    sets = anim_sets()

    # ---------------------------------------------------------------- sequences -> label groups
    seq_groups, seq_bad, seq_frames, seq_meta = {}, {}, {}, {}
    for name, body, _p in config_blocks('seq'):
        groups, unknown, frames = set(), [], []
        bits = []
        for k in ('priority', 'replayoff', 'walkmerge', 'stretches'):
            if k in body:
                bits.append('%s=%s' % (k, body[k][0]))
        seq_meta[name] = ' '.join(bits)
        for key, vals in body.items():
            if not re.match(r'^frame\d+$', key):
                continue
            for v in vals:
                frames.append(v)
                fid = anim_ids.get(v)
                hit = sets.get(fid) if fid is not None else None
                if hit is None:
                    unknown.append(v)
                else:
                    groups |= hit[1]
        seq_groups[name] = groups
        seq_frames[name] = frames
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

    # ---------------------------------------------------------------- --kit
    # What is there to wire? A creature's sequences all live on the same frame set, so the set its
    # cache-stated readyanim uses is the shelf to look on. This is tools/models/seqfind474.py's
    # question asked of this build's own packed animations.
    if a.kit:
        for name, body, path in config_blocks('npc'):
            if name != a.kit:
                continue
            own = set()
            for key in ('readyanim', 'walkanim'):
                for v in body.get(key, []):
                    for seq in v.split(','):
                        own |= {st for st, _g in
                                (sets[anim_ids[f]] for f in seq_frames.get(seq.strip(), [])
                                 if f in anim_ids and anim_ids[f] in sets)}
            print('%s stands and walks on %s (%s)' % (name, '/'.join(sorted(own)) or '?', path))
            for key in ('readyanim', 'walkanim', 'param'):
                for v in body.get(key, []):
                    if key != 'param' or 'anim' in v:
                        print('    %-10s %s' % (key, v))
            print('')
            print('every sequence on that rig:')
            for seq in sorted(seq_frames):
                seq_sets = {st for st, _g in (sets[anim_ids[f]] for f in seq_frames[seq]
                                              if f in anim_ids and anim_ids[f] in sets)}
                if seq_sets & own:
                    print('    %-40s %3d frames  %s' % (seq, len(seq_frames[seq]), seq_meta.get(seq, '')))
            return 0
        print('no npc called %s' % a.kit)
        return 2

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
        # WHAT IS SITTING ON ITS RIG UNUSED. A creature's sequences are authored as a set on one
        # frame set, so the shelf to look on is the set its own stand and walk use. Only a name is
        # proposed - never applied - and only when the word in it says what it is for.
        shelf = []
        if dead or suspect:
            # A param that is SET to the wrong thing needs a proposal just as much as a missing one.
            # cave_goblin_guard1 was wired by hand to human_blunt_pound, which misses 106 of the 157
            # groups its mesh has, and the shelf stayed silent because the param was not empty - so
            # the one npc whose fix was already written down read as unfixable.
            flagged = {f.split('=')[0] for f in dead + suspect}
            own_sets = {st for st, _g in (sets[anim_ids[f]] for seq in
                                          [v.strip() for key in ('readyanim', 'walkanim')
                                           for vv in body.get(key, []) for v in vv.split(',')]
                                          for f in seq_frames.get(seq, [])
                                          if f in anim_ids and anim_ids[f] in sets)}
            for seq in sorted(seq_frames):
                seq_sets = {st for st, _g in (sets[anim_ids[f]] for f in seq_frames[seq]
                                              if f in anim_ids and anim_ids[f] in sets)}
                if not (seq_sets & own_sets):
                    continue
                low = seq.lower()
                for word, param in (('attack', 'attack_anim'), ('defend', 'defend_anim'),
                                    ('block', 'defend_anim'), ('parry', 'defend_anim'),
                                    ('death', 'death_anim'), ('die', 'death_anim'),
                                    ('sink', 'death_anim')):
                    if word in low and (param in flagged or not any(
                            v.startswith(param + ',') for v in body.get('param', []))):
                        shelf.append('%s,%s' % (param, seq))
                        break
        rows.append((lvl, name, table, dead, suspect, bool(own_outside), os.path.relpath(path, ROOT),
                     off, sorted(set(shelf))))

    # NOTHING THAT IS NEVER SPAWNED IS A BUG. Three of the first dozen findings were records nothing
    # can reach: a second Ket-Zek left on the old animations after the live one was reimported, a
    # Swan Song kalphite named only by the drop tables, and Echned Zekin, who has 150 hitpoints, no
    # Attack option and is only ever talked to. The catalogues that list every npc in the game are
    # excluded, or everything looks spawned.
    onmap, inscript = spawn_counts({r[1] for r in rows if r[3] or r[4]})
    rows = [r + (onmap.get(r[1], 0), inscript.get(r[1], 0)) for r in rows]

    rows.sort(key=lambda r: (-r[0], r[1]))
    unreachable = [r for r in rows if (r[3] or r[4]) and not r[9] and not r[10]]
    rows = [r for r in rows if r not in unreachable]
    dead_rows = [r for r in rows if r[3]]
    susp_rows = [r for r in rows if r[4] and not r[3]]
    loose = sum(1 for r in rows if r[5])

    for title, group, key in (('BROKEN - the animation cannot play', dead_rows, 3),
                              ('WRONG RIG - a human animation on a mesh that is not human', susp_rows, 4)):
        if not group:
            continue
        print('==== %s' % title)
        for row in group:
            where = ('%d on the map' % row[9]) if row[9] else ('%d script%s' % (row[10], '' if row[10] == 1 else 's'))
            print('%-34s level %-5s labels %-4s %-14s %s' % (row[1][:34], row[0] or '-', row[2], where, row[6]))
            for p in row[key]:
                print('    %s' % p)
            if row[8]:
                print('    ON ITS OWN RIG, UNUSED: %s' % '  '.join(row[8]))
            else:
                print('    nothing on its own rig to wire: this creature has no such animation here')
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
    print('  %d set aside: flagged, but nothing on any map or in any script spawns them' % len(unreachable))
    if a.verbose and unreachable:
        print('')
        print('==== NEVER SPAWNED, so not a bug')
        for row in unreachable:
            print('%-34s level %-5s %s' % (row[1][:34], row[0] or '-', row[6]))
    print('  %d whose own cache-stated stand or walk also reaches past it, which is why a partial'
          % loose)
    print('    overshoot on its own is not reported: one frame set serves a whole family.')
    return 1 if dead_rows or susp_rows else 0


if __name__ == '__main__':
    sys.exit(main())
