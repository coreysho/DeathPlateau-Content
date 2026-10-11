#!/usr/bin/env python3
"""Fighting npcs whose own attack, block and death animations exist and are not wired up.

An npc states its walk and stand in the config - walkanim and readyanim - but its combat three
are params: attack_anim, defend_anim and death_anim, read by skill_combat/scripts/npc. With none
of them it falls back to combat.param's defaults, which are human_unarmedpunch, human_unarmedblock
and human_death. So a zombie in Melzar's Maze throws a punch like a man, which is what "animation
bug in Melzar's castle" was.

THE NAMING IS THE EVIDENCE. A creature's sequences are named as a set: zombie_walk, zombie_ready,
zombie_attack, zombie_block, zombie_death. So take the stem of what the npc already uses to walk
or stand, look for the rest of the set in seq.pack, and report any that exist and are not
referenced. Nothing is guessed - a line is only proposed where the cache already holds a sequence
named for that creature.

The same stems carry sounds in synth.pack (rock_crab_attack, rock_crab_hit, rock_crab_death), so
those are reported too, under attack_sound, defend_sound and death_sound.

  python3 tools/npcanims.py                # report
  python3 tools/npcanims.py --apply
  python3 tools/npcanims.py --npc zombie   # just the ones whose stem matches
"""
import argparse, glob, os, re, sys

# seq suffix -> the param that should carry it
ANIM = {'attack': 'attack_anim', 'block': 'defend_anim', 'death': 'death_anim'}
# synth suffix -> param. "hit" is the noise a creature makes when IT is hit, hence defend_sound.
SOUND = {'attack': 'attack_sound', 'hit': 'defend_sound', 'death': 'death_sound'}

# What npc_combat.param already falls back to. Writing one of these changes nothing, so a
# proposal equal to the default is dropped - which is most of the human npcs, whose death anim
# and death sound ARE the default.
DEFAULTS = {'attack_anim': 'human_unarmedpunch', 'death_anim': 'human_death',
            'defend_anim': 'human_unarmedblock', 'attack_sound': 'unarmed_punch',
            'defend_sound': 'human_hit4', 'death_sound': 'human_death'}

# A human npc using a human sequence is already right; these only matter where a creature has
# sequences of its own and is punching like a man instead.
HUMAN_STEMS = ('human', 'man', 'woman')


def pack(path):
    out = set()
    for line in open(path, encoding='utf-8'):
        i, _, n = line.strip().partition('=')
        if i.isdigit():
            out.add(n)
    return out


def npc_configs(content):
    out = {}
    for p in sorted(glob.glob(os.path.join(content, 'scripts/**/*.npc'), recursive=True)):
        cur = None
        for line in open(p, encoding='utf-8', errors='replace'):
            s = line.strip()
            if s.startswith('//'):
                continue
            if s.startswith('[') and s.endswith(']'):
                cur = s[1:-1]
                out.setdefault(cur, (p, {}, []))
            elif cur and '=' in s:
                k, v = s.split('=', 1)
                if k == 'param' and ',' in v:
                    pk, pv = v.split(',', 1)
                    out[cur][1].setdefault('param:' + pk, pv)
                else:
                    out[cur][1].setdefault(k, v)
    return out


def stems(cfg):
    """What a creature's sequences are called, from what it already walks and stands with."""
    got = []
    for key in ('walkanim', 'readyanim'):
        v = cfg.get(key, '')
        v = v.split(',')[0]
        for suffix in ('_walk', '_ready', '_stand'):
            if v.endswith(suffix):
                got.append(v[:-len(suffix)])
    return list(dict.fromkeys(got))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content',
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--npc', help='only stems containing this')
    ap.add_argument('--human', action='store_true',
                    help='include human npcs, whose defaults are already human sequences')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    seqs = pack(os.path.join(a.content, 'pack/seq.pack'))
    synths = pack(os.path.join(a.content, 'pack/synth.pack'))
    cfgs = npc_configs(a.content)

    rows = []
    for name, (path, cfg, _) in sorted(cfgs.items()):
        if cfg.get('op2') != 'Attack' and cfg.get('op1') != 'Attack':
            continue                                   # not something you fight
        missing = []
        for stem in stems(cfg):
            if a.npc and a.npc not in stem:
                continue
            if not a.human and stem.startswith(HUMAN_STEMS):
                continue
            for suffix, param in ANIM.items():
                if 'param:' + param in cfg:
                    continue
                cand = f'{stem}_{suffix}'
                if cand in seqs and DEFAULTS.get(param) != cand:
                    missing.append((param, cand))
            for suffix, param in SOUND.items():
                if 'param:' + param in cfg:
                    continue
                cand = f'{stem}_{suffix}'
                if cand in synths and DEFAULTS.get(param) != cand:
                    missing.append((param, cand))
        if missing:
            seen = {}
            for p, v in missing:
                seen.setdefault(p, v)
            rows.append((name, path, seen))

    for name, path, seen in rows:
        print(f'  {name:<34} ' + '  '.join(f'{k}={v}' for k, v in sorted(seen.items())))
    print(f'\n{len(rows)} fighting npcs with a sequence or synth named for them that is not wired')

    if a.apply:
        for name, path, seen in rows:
            src = open(path, encoding='utf-8', newline='').read()
            nl = '\r\n' if '\r\n' in src else '\n'
            t = src.replace('\r\n', '\n')
            m = re.search(r'^\[' + re.escape(name) + r'\]\n((?:(?!^\[).*\n)*)', t, re.M)
            assert m, name
            add = ''.join(f'param={k},{v}\n' for k, v in sorted(seen.items()))
            t = t[:m.end(1)] + add + t[m.end(1):]
            open(path, 'w', encoding='utf-8', newline='').write(t.replace('\n', nl))
        print(f'wrote lines for {len(rows)} npcs')
    else:
        print('dry run - pass --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
