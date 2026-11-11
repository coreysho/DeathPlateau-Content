#!/usr/bin/env python3
"""The quest-complete scroll says how many quest points once.

THE BUG THIS EXISTS FOR. ~send_quest_complete writes "N Quest Point(s)" on the scroll's own line
(inter_238:com_9) out of the number it is handed. 43 of the 111 quests wrote that same line at the
front of their reward text as well, so their scrolls showed it twice. Holy Grail's was reported.

THE FIX IS IN THE PROC, not in 43 files: it drops a first reward line that is EXACTLY the line
com_9 is about to print. Exactly, and not "contains the words Quest Point", because a line read
loosely can be read wrongly - "2 Quest Points and a hat" would lose the hat, which is a worse bug
than the one being fixed and a silent one.

THE RULE THIS KEEPS. The narrow match only covers every quest while every quest's hand-written
line really is byte-identical to the proc's, down to the singular for a one-point quest. All 43
are today. This asserts they stay so, and that a new quest written with the line in some other
shape is noticed here rather than on a player's scroll:

  - a first reward line mentioning quest points must equal pluralise(<the quest's own points>)
  - no LATER line may mention them at all: the proc only ever looks at the first

WHAT IS NOT CHECKED. Whether the scroll looks right, which needs the engine - tools/sim/
questscroll.ts in the engine repo fires ten real completion queues and counts the lines. This is
the breadth behind that depth: every quest, from the source, with no cache to build.

    python3 tools/questscroll_battery.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts')

CALL = re.compile(r'~send_quest_complete\(')
STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
CONSTANT = re.compile(r'^\^?([A-Za-z0-9_]+)\s*=\s*(-?\d+)\s*$')
MENTIONS_POINTS = re.compile(r'quest\s*points?', re.IGNORECASE)


def sources(ext):
    for base, _dirs, files in os.walk(SCRIPTS):
        for f in sorted(files):
            if f.endswith(ext):
                yield os.path.join(base, f)


def constants():
    """Every ^name = number in the content, so ^grail_questpoints can be read as 2."""
    out = {}
    for path in list(sources('.constant')) + list(sources('.const')):
        for line in open(path, encoding='utf-8', errors='replace'):
            m = CONSTANT.match(line.strip())
            if m and m.group(1) not in out:
                out[m.group(1)] = int(m.group(2))
    return out


def arguments(call):
    """The call's arguments, split on the commas that are not inside a string or a nested call."""
    blanked = STRING.sub('""', call)
    args, cur, depth = [], '', 0
    for ch in blanked:
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth == 0:
                break
            depth -= 1
        if ch == ',' and depth == 0:
            args.append(cur.strip())
            cur = ''
        else:
            cur += ch
    args.append(cur.strip())
    return args


def pluralise(amount):
    """~pluralise in scripts/general/scripts/misc/string_procs.rs2, which com_9 is printed through."""
    return '1 Quest Point' if amount == 1 else f'{amount} Quest Points'


def main():
    consts = constants()
    calls = []
    for path in sources('.rs2'):
        rel = os.path.relpath(path, ROOT)
        for i, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
            if not CALL.search(line) or line.lstrip().startswith('//'):
                continue
            at = line.index('~send_quest_complete(')
            quoted = STRING.findall(line[at:])
            if len(quoted) < 2:
                print(f'  FAIL     {rel}:{i} the call has fewer than two strings - this parser '
                      'cannot read it, so fix the parser rather than skip the quest')
                return 1
            calls.append((rel, i, arguments(line[at + len('~send_quest_complete('):]), quoted[-1]))

    # A battery that parses nothing passes everything. These two say the reading worked at all.
    if len(calls) < 100:
        print(f'  FAIL     only {len(calls)} completion calls found, expected 111 or so - the '
              'parser is broken, not the content')
        return 1
    handwritten = [c for c in calls if MENTIONS_POINTS.search(c[3].split('|')[0])]
    if len(handwritten) < 40:
        print(f'  FAIL     only {len(handwritten)} hand-written quest-point lines found, expected '
              '43 or so - the parser is broken, not the content')
        return 1

    bad = 0
    for rel, i, args, reward in calls:
        lines = reward.split('|')
        for n, line in enumerate(lines[1:], 2):
            if MENTIONS_POINTS.search(line):
                bad += 1
                print(f'  FAIL     {rel}:{i} line {n} of the reward text mentions quest points '
                      f'({line!r}) - the proc only drops the FIRST line, so this one shows twice')
        if not MENTIONS_POINTS.search(lines[0]):
            continue
        if len(args) < 4:
            bad += 1
            print(f'  FAIL     {rel}:{i} could not find the questpoints argument')
            continue
        name = args[3].lstrip('^')
        if name not in consts:
            bad += 1
            print(f'  FAIL     {rel}:{i} the points argument {args[3]} is not a constant this '
                  'battery can resolve, so its line cannot be compared')
            continue
        want = pluralise(consts[name])
        if lines[0] != want:
            bad += 1
            print(f'  FAIL     {rel}:{i} the reward text opens {lines[0]!r} but com_9 prints '
                  f'{want!r} - the proc drops only an exact match, so this scroll shows the '
                  'points twice. Write the line exactly, or drop it and let the scroll say it.')

    if bad:
        print(f'\n{bad} quest scroll(s) would show their quest points twice.')
        return 1
    print(f'{len(calls)} quest completions, {len(handwritten)} of them writing the points line by '
          f'hand, every one exactly as com_9 prints it')
    return 0


if __name__ == '__main__':
    sys.exit(main())
