#!/usr/bin/env python3
"""A quest may not record a step later than it spends the player's things.

THE BUG THIS EXISTS FOR. A player drank three beers for Drunken Ali, Ali sent them to Ali the
Operator, and the Operator's minder turned them away - because the beers were consumed in one
tick and the quest's progress was written three ticks later, after p_delay and a conversation.
p_delay SUSPENDS the script. Anything the player clicks in between drops the rest of it, so the
beer was gone and feud_var never moved; Ali refuses a fourth beer, and there is no other way to
set that value. The quest was over for that character.

THE RULE. Inside one block, a quest progress var - one that some script hands to
~send_quest_progress - may not be written after a suspend that comes after an inv_del or an
npc_del. Spend the thing and record it in the same tick; the theatre can come after, and can be
dropped without costing anybody anything.

Suspends are p_delay, the chat and mesbox procs, p_arrivedelay and the multi helpers: each of
them hands the script back to the engine, and the engine hands it back only if the player has
not started something else meanwhile.

WHAT IS NOT CHECKED. Writes to the quest's working flags: those are usually set with the action
and are cheap to re-derive. And scripts outside scripts/, which have no quests in them.

    python3 tools/questprogress_battery.py
"""
import os
import re
import sys

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')

SUSPEND = re.compile(r'\b(p_delay|~chatnpc|~chatplayer|~mesbox|~objbox|~p_choice\d?|p_arrivedelay|~multi\d)\(')
DESTROY = re.compile(r'\binv_del\(|\bnpc_del\(')
WRITE = re.compile(r'^\s*%(\w+) = ')
BLOCK = re.compile(r'^\[')
PROGRESS = re.compile(r'~send_quest_progress\(questlist:\w+, %(\w+)')

# Reviewed and allowed, with the reason. A line here is a promise that losing the write costs the
# player nothing they cannot get back - not that the shape is fine.
ALLOWED = {
    # (path, var): why
}


def sources():
    for base, _dirs, files in os.walk(SCRIPTS):
        for f in sorted(files):
            if f.endswith('.rs2'):
                yield os.path.join(base, f)


def main():
    progress = set()
    for path in sources():
        progress.update(PROGRESS.findall(open(path, encoding='utf-8', errors='replace').read()))
    if len(progress) < 50:
        print(f'questprogress_battery: only {len(progress)} quest progress vars found - '
              'the scan is reading the wrong tree')
        return 1
    print(f'{len(progress)} quest progress vars, across {len(list(sources()))} scripts')

    bad = allowed = 0
    for path in sources():
        rel = os.path.relpath(path, os.path.dirname(SCRIPTS))
        lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
        block = 'the top of the file'
        destroyed = suspend = None
        written = set()
        for i, line in enumerate(lines, 1):
            if BLOCK.match(line):
                block, destroyed, suspend, written = line.strip(), None, None, set()
                continue
            if DESTROY.search(line):
                destroyed, suspend = i, None
                continue
            write = WRITE.match(line)
            if write:
                var = write.group(1)
                if destroyed and suspend and var in progress and var not in written:
                    if (rel, var) in ALLOWED:
                        allowed += 1
                        print(f'  allowed  {rel}:{i} %{var} - {ALLOWED[(rel, var)]}')
                    else:
                        bad += 1
                        print(f'  FAIL     {rel}:{i} %{var} is written after the suspend at '
                              f'{suspend}, and {rel}:{destroyed} has already spent something')
                        print(f'           in {block}')
                written.add(var)
                continue
            if destroyed and suspend is None and SUSPEND.search(line):
                suspend = i

    if bad:
        print(f'\n{bad} quest progress write(s) a player can lose. Move the write into the tick '
              'that spends the item, or add it to ALLOWED with a reason.')
        return 1
    print(f'\nevery quest records what it spends in the tick it spends it'
          + (f' ({allowed} reviewed exception(s))' if allowed else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
