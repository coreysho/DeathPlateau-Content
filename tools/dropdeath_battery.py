#!/usr/bin/env python3
"""Does every npc whose config NAMES a death drop actually drop it?

DeathPlateau-Bugs#109. icefiend.rs2 had no `obj_add(npc_coord, npc_param(death_drop), ...)` line, and
the icefiend's config says `param=death_drop,ashes`, so every icefiend in the game left no ashes -
twelve kills, none. `~npc_death` does not drop the 100% row; every table calls obj_add for itself, so
a table that forgets that line is a monster that leaves nothing behind, and it looks completely
normal. It was the fifth time that exact omission had turned up: four God Wars bodyguard tables
had it too, found by a 540-kill run.

WHAT IT CHECKS, AND WHAT IT DELIBERATELY DOES NOT. It flags an `[ai_queue3,<npc>]` table when the
npc's config EXPLICITLY sets `param=death_drop` to something other than null and the table - followed
through every label and proc it calls - neither reads `npc_param(death_drop)` nor drops that item by
name. An explicit setting is proof of intent, which is the only thing that separates a bug from a
creature that is meant to leave nothing.

It does NOT flag an npc whose death_drop is only the DEFAULT (bones). `param=death_drop` defaults to
bones for every npc that does not say, and Old School gives a great many creatures no bones at all -
crawling hands, cockatrices, kalphites, banshees - so a table that omits the line may be exactly
right. Those are counted and printed below as information. There are 25 of them today; whether each is
intended is a question about the game and not something a check can answer.

TWO BLIND SPOTS THE FIRST VERSION HAD, both of which reported tables that drop correctly:
  - a label called with arguments - `@elemental_wizard_drops(airrune, air_talisman);` - because it
    only matched a bare `@name;`. Four elemental wizards were reported that way.
  - a [proc,...], because it only indexed [label,...]. The abyssal demon drops from one.
Both are exercised by the real content, so they are covered without a fixture.

    python3 tools/dropdeath_battery.py
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
FAILED = []


def ok(msg, extra=''):
    print('  ok   %s%s' % (msg, (': ' + str(extra)) if extra != '' else ''))


def bad(msg, extra=''):
    print('  FAIL %s%s' % (msg, (': ' + str(extra)) if extra != '' else ''))
    FAILED.append(msg)


def check(cond, msg, extra=''):
    (ok if cond else bad)(msg, extra)


def strip(t):
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    return re.sub(r'//[^\n]*', '', t)


# ---- every npc's death_drop, and whether it was SET or merely defaulted ----
death_drop = {}
explicit = set()
for f in glob.glob('scripts/**/*.npc', recursive=True):
    cur = None
    for line in open(f, errors='replace'):
        line = line.rstrip('\r\n')
        m = re.match(r'^\[([^\]]+)\]', line)
        if m:
            cur = m.group(1)
            death_drop.setdefault(cur, 'bones')
            continue
        m = re.match(r'^param=death_drop,(\S+)', line)
        if m and cur:
            death_drop[cur] = m.group(1)
            explicit.add(cur)

# ---- the tables, and every label and proc anything could jump to ----
handlers, callable_ = {}, {}
for f in glob.glob('scripts/drop_tables/scripts/*.rs2'):
    text = strip(open(f, errors='replace').read())
    for part in re.split(r'(?m)^(?=\[)', text):
        m = re.match(r'\[([a-z_0-9]+),([^\]]+)\](.*)', part, re.S)
        if not m:
            continue
        kind, name, body = m.groups()
        if kind == 'ai_queue3':
            handlers[(name, os.path.basename(f))] = body
        elif kind in ('label', 'proc'):
            callable_[name] = body


def reach(body, seen=None):
    """The body plus the body of everything it calls, so a drop in a helper still counts."""
    seen = seen if seen is not None else set()
    out = body
    for name in re.findall(r'@([a-z_0-9]+)\s*[;(]', body) + re.findall(r'~([a-z_0-9]+)\b', body):
        if name in callable_ and name not in seen:
            seen.add(name)
            out += reach(callable_[name], seen)
    return out


missing_explicit, missing_default, checked = [], [], 0
for (npc, fname), body in sorted(handlers.items()):
    want = death_drop.get(npc)
    if npc == '_' or want is None or want == 'null':
        continue
    checked += 1
    full = reach(body)
    named = re.search(r'obj_add\(\s*npc_coord\s*,\s*' + re.escape(want) + r'\b', full)
    if 'death_drop' in full or named:
        continue
    (missing_explicit if npc in explicit else missing_default).append((npc, want, fname))

print('1. no table forgets a death_drop its npc asks for')
check(checked > 300, 'the sweep actually looked at the tables (%d with a death_drop to drop)' % checked)
check(not missing_explicit,
      'every explicit death_drop is dropped by its table',
      ', '.join('%s (%s, in %s)' % m for m in missing_explicit) if missing_explicit else len(handlers))

print('2. and the ones it does not judge are at least counted')
print('       %d tables omit a death_drop their npc only DEFAULTS to (bones) - may be intended,' % len(missing_default))
print('       because Old School gives many of these creatures no bones. Not a failure.')

print()
print('ALL PASS' if not FAILED else '%d FAILED' % len(FAILED))
sys.exit(1 if FAILED else 0)
