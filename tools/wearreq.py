#!/usr/bin/env python3
"""Which equipable items can be worn at level 1 that should not be.

WHY THIS EXISTS. Equip requirements in this content are not data: there is no "requires 40
Defence" field on an obj. They are one [opheld2,<obj>] @levelrequire_<stat>(<n>, last_slot)
trigger per item, hand-written into scripts/levelrequire/scripts/tier<n>.rs2, and anything
without one falls through to the global [opheld2,_] ~equip(last_slot) and goes on at level 1.
So a requirement is missing exactly when somebody forgot to type a line, and nothing complains.
A gold rune defender and every piece of 3rd age went on at 1 Defence for that reason.

HOW IT FINDS THEM. A trimmed, heraldic, gilded or god-blessed piece is the same armour as the
plain one repainted - the configs say so themselves ("A repaint of rune_platebody, so the same
armour: stats copied from it"). So the test is the equipment bonuses: take every unwired
equipable item and look for WIRED items with exactly the same slot and exactly the same
offensive and defensive bonuses. Those are the same armour, and the same armour wants the same
requirement.

Twins can disagree - dagganoth_melee_body has rune platebody's stats behind Viking quest rather
than Dragon Slayer - so the vote is a majority, and a split is reported rather than guessed.

NAME EVIDENCE DECIDES WHETHER TO ACT. Matching stats are not proof on their own: Varrock armour
3 has mithril platebody's stats and is a diary reward you wear at level 1. So the matches are
graded:

  A  the item's name begins with its twin's name - "Rune platebody (h1)" from "Rune platebody".
     A repaint. Safe.
  B  the names end in the same word - "Saradomin kiteshield" / "Rune kiteshield", "Castlewars
     med helm" / "Steel med helm". The same piece of armour under another name. Safe.
  C  neither - "Varrock armour 3" / "Mithril platebody". Reported, never applied: this is where
     the diary and minigame rewards live, and they are meant to be wearable.

Items with no twin at all are listed too, loudest bonus first, because that is where the unique
things are - 3rd age, god d'hide, the composite bows - and they need a wiki, not a rule.

  python3 tools/wearreq.py                 # the report
  python3 tools/wearreq.py --fix           # write the A and B wirings into tier<n>.rs2
  python3 tools/wearreq.py --show C        # just one bucket

NOT EVERYTHING HERE IS A BUG. black_mask and the slayer helmets are deliberately wearable at 1
Defence on this server; their requirement lines are commented out in tier10/tier20 with a note,
and this tool reads .rs2 with comments stripped so it reports them as unwired. They are in
KEEP_AT_ONE below and are never written.
"""
import argparse, collections, glob, os, re, sys

# Deliberately wearable at level 1 on this server; see tier10.rs2 and tier20.rs2.
KEEP_AT_ONE = {'black_mask', 'black_mask_i', 'slayer_helm', 'slayer_helm_i'}
KEEP_PREFIX = ('slayer_helm_', 'black_mask_')

BONUS_WORDS = ('attack', 'defence', 'strength', 'prayer', 'magicdamage')

# Bucket B says "the same armour under another name", and for god armour, gilded rune and the
# infinity recolours it is right. For these it is not: they share a twin's bonuses by coincidence
# (usually because both are zero) or the twin is the wrong model entirely. Reported, never written.
B_HOLD = {
    # A plain coloured cape has no requirement. It matches the lunar cape only because neither of
    # them has a single non-zero bonus.
    'black_cape': 'a plain cape, no requirement',
    'blue_cape': 'a plain cape, no requirement',
    'green_cape': 'a plain cape, no requirement',
    'orange_cape': 'a plain cape, no requirement',
    'purple_cape': 'a plain cape, no requirement',
    'red_cape': 'a plain cape, no requirement',
    'gnome_hat_blue': 'cosmetic gnome kit, not xerician robes',
    'gnome_hat_cream': 'cosmetic gnome kit, not xerician robes',
    'gnome_hat_green': 'cosmetic gnome kit, not xerician robes',
    'gnome_hat_pink': 'cosmetic gnome kit, not xerician robes',
    'gnome_hat_turquoise': 'cosmetic gnome kit, not xerician robes',
    'yellow_cape': 'a plain cape, no requirement',
    'viyeldihat': 'cosmetic, not xerician robes',
    'wolfenhat_crimson': 'cosmetic wolfen kit, not xerician robes',
    'wolfenhat_grey': 'cosmetic wolfen kit, not xerician robes',
    'wolfenhat_ocean': 'cosmetic wolfen kit, not xerician robes',
    'wolfenhat_purple': 'cosmetic wolfen kit, not xerician robes',
    'wolfenhat_tangerine': 'cosmetic wolfen kit, not xerician robes',
    'castlewars_med_helm': 'Castle Wars decorative armour - unconfirmed',
    'castlewars_med_helm_2': 'Castle Wars decorative armour - unconfirmed',
    'castlewars_med_helm_3': 'Castle Wars decorative armour - unconfirmed',
    'cabbage_round_shield': 'novelty shield - unconfirmed',
    'deathdagger': 'unconfirmed',
    'animmag_blessed_axe': 'quest item - unconfirmed',
    'third_age_axe': 'has its own requirement; see tier65.rs2',
    'third_age_pickaxe': 'has its own requirement; see tier65.rs2',
    'tzhaar_cape_obsidian': 'twin is a skillcape, whose requirement is not a plain level call',
}


def noop(call):
    """A requirement of level 1 enforces nothing, so writing one is noise."""
    nums = [int(n) for n in re.findall(r'(\d+)', call)]
    return bool(nums) and max(nums) <= 1


def malformed(call):
    """The trigger regex stops at the first ')', so a call with a nested one comes back cut in
    half. Those are reported, not written."""
    return call.count('(') != call.count(')') or not re.fullmatch(r'@\w+\([^()]*\)', call)


def load_objs(root):
    objs = {}
    for p in sorted(glob.glob(os.path.join(root, 'scripts/**/*.obj'), recursive=True)):
        cur = None
        for line in open(p, encoding='utf-8', errors='replace'):
            s = line.strip()
            if s.startswith('//'):
                continue
            if s.startswith('[') and s.endswith(']'):
                cur = s[1:-1]
                objs[cur] = {'_file': p}
            elif cur and '=' in s:
                k, v = s.split('=', 1)
                if k == 'param' and ',' in v:
                    pk, pv = v.split(',', 1)
                    objs[cur].setdefault('p_' + pk, pv)
                else:
                    objs[cur].setdefault(k, v)
    return objs


def load_calls(root):
    """obj name -> the @levelrequire_... call wired to it, with comments stripped so a
    deliberately disabled requirement reads as absent."""
    calls = {}
    for p in sorted(glob.glob(os.path.join(root, 'scripts/**/*.rs2'), recursive=True)):
        txt = ''.join(l for l in open(p, encoding='utf-8', errors='replace')
                      if not l.lstrip().startswith('//'))
        for m in re.finditer(r'\[opheld2,([^\]]+)\]\s*(@\w+\([^)]*\))?', txt):
            for n in m.group(1).split(','):
                calls[n.strip()] = m.group(2) or ''
    return calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default='.')
    ap.add_argument('--fix', action='store_true')
    ap.add_argument('--show', default='ABCX', help='which buckets to print')
    args = ap.parse_args()

    objs = load_objs(args.content)
    calls = load_calls(args.content)
    bonus_keys = {k for d in objs.values() for k in d
                  if k.startswith('p_') and any(w in k[2:] for w in BONUS_WORDS)}

    def sig(n):
        d = objs[n]
        return (d.get('wearpos'), d.get('wearpos2'), d.get('wearpos3'),
                tuple(sorted((k, d[k]) for k in d if k in bonus_keys)))

    def nm(n):
        return objs[n].get('name', '').lower().strip()

    wear = [n for n, d in objs.items() if 'wearpos' in d]
    wired = [n for n in wear if n in calls and calls[n]]
    bysig = collections.defaultdict(list)
    for n in wired:
        bysig[sig(n)].append(n)

    buckets = {'A': [], 'B': [], 'C': [], 'X': []}
    for n in sorted(wear):
        if n in calls or n in KEEP_AT_ONE or n.startswith(KEEP_PREFIX):
            continue
        s = sig(n)
        if not s[3]:
            continue                                   # no bonuses: a cosmetic, nothing to gate
        twins = bysig.get(s)
        if not twins:
            loud = max((abs(int(v)) for k, v in s[3] if v.lstrip('-').isdigit()), default=0)
            buckets['X'].append((n, objs[n].get('name', '?'), s[0], loud))
            continue
        votes = collections.Counter(calls[t] for t in twins)
        call, count = votes.most_common(1)[0]
        if noop(call) or malformed(call):
            continue
        split = len(votes) > 1
        twin = next(t for t in twins if calls[t] == call)
        if n in B_HOLD:
            buckets['C'].append((n, twin, call + '   // held: ' + B_HOLD[n], split))
            continue
        if nm(twin) and nm(n).startswith(nm(twin)):
            b = 'A'
        elif nm(twin) and nm(n).split()[-1:] == nm(twin).split()[-1:]:
            b = 'B'
        else:
            b = 'C'
        buckets[b].append((n, twin, call, split))

    buckets['X'].sort(key=lambda r: -r[3])

    titles = {
        'A': 'A  a repaint of a wired item (name begins with its twin\'s) - safe to copy',
        'B': 'B  the same armour under another name (same final word) - safe to copy',
        'C': 'C  same stats, unrelated name - diary and minigame rewards live here, NOT applied',
        'X': 'X  no twin at all - unique items, these need a wiki and a human',
    }
    for b in 'ABCX':
        if b not in args.show:
            continue
        print()
        print(f'{titles[b]}   [{len(buckets[b])}]')
        for row in buckets[b]:
            if b == 'X':
                print(f'    {row[3]:>4}  {row[0]:<34} {row[1]:<32} {row[2]}')
            else:
                mark = ' (twins disagree)' if row[3] else ''
                print(f'    {row[0]:<34} <- {row[1]:<28} {row[2]}{mark}')

    print()
    print(f'equipable {len(wear)}, wired {len(wired)}, '
          f'copyable {len(buckets["A"]) + len(buckets["B"])}, '
          f'report-only {len(buckets["C"])}, unique {len(buckets["X"])}')

    if args.fix:
        write_fixes(args.content, buckets['A'] + buckets['B'])
    return 0


def write_fixes(root, rows):
    """Append each wiring to the tier file its level belongs to, which is where every other one
    of these lives."""
    by_tier = collections.defaultdict(list)
    for n, twin, call, _ in rows:
        m = re.search(r'\((\d+)', call)
        if not m:
            print('  ?? no level in', call, 'for', n)
            continue
        by_tier[int(m.group(1))].append((n, twin, call))
    for tier, items in sorted(by_tier.items()):
        p = os.path.join(root, f'scripts/levelrequire/scripts/tier{tier}.rs2')
        if not os.path.exists(p):
            print('  ?? no tier file for', tier, '-', len(items), 'items skipped')
            continue
        src = open(p, encoding='utf-8', newline='').read()
        nl = '\r\n' if '\r\n' in src else '\n'
        body = src.replace('\r\n', '\n').rstrip('\n')
        add = [l for l in (f'[opheld2,{n}] {call};' for n, twin, call in items)
               if l.split(']')[0] + ']' not in body]
        if not add:
            continue
        body += ('\n\n// Repaints and renames of items already in this file, found by '
                 'tools/wearreq.py:\n// same slot, same bonuses, so the same armour and the same '
                 'requirement. They went\n// on at level 1 because nobody had typed a line for '
                 'them.\n' + '\n'.join(sorted(add)) + '\n')
        open(p, 'w', encoding='utf-8', newline='').write(body.replace('\n', nl))
        print(f'  tier{tier}.rs2 += {len(add)}')


if __name__ == '__main__':
    sys.exit(main())
