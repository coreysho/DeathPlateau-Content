#!/usr/bin/env python3
"""Which synths define a loop region, and which sound_synth calls truncate one by asking for 0 loops.

THE LOOPS ARGUMENT IS NOT A COUNT OF EXTRA PLAYS. jagex2/sound/Wave.method483 builds the wave like
this, with arg0 being the loops field off the wire:

    int var7 = (arg0 - 1) * (var6 - var5) + var4;

var4 is the sound's natural length in samples and var5..var6 is its loop region. So:

    loops = 1   ->  var7 = var4                     the whole sound, once
    loops = 2   ->  var7 = var4 + one loop region   the loop played twice
    loops = 0   ->  var7 = var4 - one loop region   THE SOUND, MINUS ITS LOOP REGION

The declared length is what goes in the WAV header, so loops=0 hands the audio device a file that
stops early. For a synth with no loop region it is harmless - method483 forces arg0 to 0 when
var5 >= var6, and then (0-1)*0 + var4 is just var4 - which is why this has gone unnoticed: 266 of
the 285 synths the combat paths touch have no loop region and sound identical either way.

The ones that do have one are the spells. Every *_cast_and_fire in the standard spellbook loops
1020..1220ms, so asking for 0 loops cuts 200ms off the end of every elemental cast. That is the
"audio bug when casting spells ... if it doesn't kill it cuts the sound short" report.

The loop region is the last four bytes of a .synth file: Wave.method480 reads up to ten tones and
then two g2s, field1476 (loop start, ms) and field1477 (loop end, ms).

  python3 tools/synthloops.py              # what loops, and which call sites ask for 0
  python3 tools/synthloops.py --apply      # rewrite every loops=0 to loops=1
"""
import argparse, glob, os, re, struct, sys


def loop_regions(content):
    """synth name -> (loop start ms, loop end ms) for the ones that define a region."""
    out = {}
    for p in glob.glob(os.path.join(content, 'synth/**/*.synth'), recursive=True):
        b = open(p, 'rb').read()
        if len(b) < 4:
            continue
        start, end = struct.unpack('>HH', b[-4:])
        if start < end:
            out[os.path.basename(p)[:-6]] = (start, end)
    return out


def args_of(src, open_paren):
    """The top-level comma-separated arguments of a call whose '(' is at open_paren."""
    depth, start, parts = 0, open_paren + 1, []
    i = open_paren
    while i < len(src):
        c = src[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                parts.append((start, i))
                return parts, i
        elif c == ',' and depth == 1:
            parts.append((start, i))
            start = i + 1
        i += 1
    return None, None


def call_sites(content):
    """(path, line, loops-arg span, the whole call) for every sound_synth in the scripts."""
    out = []
    for p in sorted(glob.glob(os.path.join(content, 'scripts/**/*.rs2'), recursive=True)):
        src = open(p, encoding='utf-8', newline='').read()
        for m in re.finditer(r'\bsound_synth\(', src):
            parts, close = args_of(src, m.end() - 1)
            if not parts or len(parts) != 3:
                continue
            line = src.count('\n', 0, m.start()) + 1
            out.append((p, line, parts, src[m.start():close + 1]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--content',
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()

    loops = loop_regions(a.content)
    print('%d synths define a loop region. The longest:' % len(loops))
    for n, (s, e) in sorted(loops.items(), key=lambda kv: kv[1][0] - kv[1][1])[:8]:
        print('    %-34s %4d..%-5d  %d ms' % (n, s, e, e - s))

    sites = call_sites(a.content)
    zeros = [s for s in sites if s[3][s[2][1][0] - s[3].find('sound_synth('):
                                     s[2][1][1] - s[3].find('sound_synth(')].strip() == '0']
    # simpler: re-read the arg text from the file
    zeros = []
    for p, line, parts, call in sites:
        src = open(p, encoding='utf-8', newline='').read()
        if src[parts[1][0]:parts[1][1]].strip() == '0':
            zeros.append((p, line, parts, call))

    print('\n%d of %d sound_synth calls ask for 0 loops:' % (len(zeros), len(sites)))
    byfile = {}
    for p, line, parts, call in zeros:
        byfile.setdefault(os.path.relpath(p, a.content).replace('\\', '/'), []).append(line)
    for f, lines in sorted(byfile.items(), key=lambda kv: -len(kv[1])):
        print('    %-66s %d' % (f, len(lines)))

    # which of them name a synth that actually loops, and which are dynamic
    named, dynamic = [], []
    for p, line, parts, call in zeros:
        src = open(p, encoding='utf-8', newline='').read()
        first = src[parts[0][0]:parts[0][1]].strip()
        if re.fullmatch(r'[a-z0-9_]+', first):
            named.append((first, p, line))
        else:
            dynamic.append((first, p, line))
    hurt = [(n, p, l) for n, p, l in named if n in loops]
    print('\n  %d name a synth outright, %d pass one in a variable or a lookup'
          % (len(named), len(dynamic)))
    print('  of the named ones, %d name a synth that loops:' % len(hurt))
    for n, p, l in hurt:
        print('      %s  (%s:%d)' % (n, os.path.relpath(p, a.content).replace('\\', '/'), l))
    print('  every dynamic one can resolve to a looping synth, so all of them are suspect:')
    for n, p, l in dynamic:
        print('      %-54s %s:%d' % (n, os.path.relpath(p, a.content).replace('\\', '/'), l))

    if not a.apply:
        print('\ndry run - pass --apply to rewrite every loops=0 to loops=1')
        return 0

    # rewrite back to front within each file so the spans stay valid
    byfile = {}
    for p, line, parts, call in zeros:
        byfile.setdefault(p, []).append(parts[1])
    for p, spans in byfile.items():
        src = open(p, encoding='utf-8', newline='').read()
        for start, end in sorted(spans, reverse=True):
            src = src[:start] + src[start:end].replace('0', '1', 1) + src[end:]
        open(p, 'w', encoding='utf-8', newline='').write(src)
    print('\nrewrote %d calls across %d files' % (len(zeros), len(byfile)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
