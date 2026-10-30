#!/usr/bin/env python3
"""Every inv_transmit must name a component that can hold an inventory.

WHAT GOES WRONG IF ONE DOES NOT, and it is not a quiet thing. The client allocates a component's
invSlotObjId only for the two inventory types - Component.decode fills it under `type == 2` and
`type == 7` and nowhere else - and the UPDATE_INV_FULL handler writes straight into that array
with no null check. So transmitting an inv to a model or a layer is a NullPointerException inside
readPacket, which is caught by the `catch (Exception)` at the bottom of it, and that calls
logout(). The player is not shown an empty window: they are thrown out of the game.

It found exactly one, and it had been there as long as the puzzle box had:

    inv_transmit(trail_puzzleinv, trail_puzzle:com_3)

com_3 is the Hint button, a model. The 5x5 grid the player slides pieces around is com_2. Opening
a puzzle box logged you out.

READ OFF THE SOURCE, not the packed archive, because this is an authoring mistake and the .if is
where it is made - and because a check that needs a build cannot run in the seconds after a typo.
tools/pouchpacked.py is the other half of the pair: it reads what the packer actually wrote.

    python3 tools/invtransmit.py
"""
import os
import re
import sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The two component types the client gives an inventory array to, by the names the .if uses for
# them. Everything else - layer, model, text, rect, graphic, overlay - has none.
HOLDS_INV = ('inv', 'invtext')

TRANSMIT = re.compile(
    r'\b\.?(?:inv_transmit|invother_transmit)\('
    r'[^()]*?([A-Za-z_][A-Za-z0-9_]*):([A-Za-z_][A-Za-z0-9_]*)\s*\)')


def interfaces():
    """{interface name: {component name: its type}} over every .if in the tree."""
    out = {}
    for root, _dirs, files in os.walk(os.path.join(C, 'scripts')):
        for name in files:
            if not name.endswith('.if'):
                continue
            coms = {}
            com = None
            for line in open(os.path.join(root, name), encoding='utf-8', errors='replace'):
                line = line.split('//')[0].strip()
                if line.startswith('[') and line.endswith(']'):
                    com = line[1:-1]
                    coms[com] = ''
                elif com and line.startswith('type='):
                    coms[com] = line[5:]
            out[name[:-3]] = coms
    return out


def main():
    coms = interfaces()
    checked = 0
    bad = []
    unknown = []
    for root, _dirs, files in os.walk(os.path.join(C, 'scripts')):
        if '_unpack' in root:
            continue
        for name in files:
            if not name.endswith('.rs2'):
                continue
            path = os.path.join(root, name)
            for n, line in enumerate(open(path, encoding='utf-8', errors='replace'), 1):
                for iface, com in TRANSMIT.findall(line.split('//')[0]):
                    where = '%s:%d  %s:%s' % (os.path.relpath(path, C), n, iface, com)
                    if iface not in coms:
                        unknown.append(where + '  (no interface of that name)')
                    elif com not in coms[iface]:
                        unknown.append(where + '  (that interface has no such component)')
                    elif coms[iface][com] not in HOLDS_INV:
                        bad.append(where + '  (type=%s, which the client gives no inventory to)'
                                   % (coms[iface][com] or 'unset'))
                    else:
                        checked += 1

    print('%d inv_transmit targets, all of them an inv component' % checked
          if not bad and not unknown else
          '%d inv_transmit targets check out' % checked)
    for line in bad:
        print('  TRANSMITS TO A COMPONENT WITH NO INVENTORY: ' + line)
    for line in unknown:
        print('  CANNOT BE CHECKED: ' + line)
    if not checked:
        print('invtransmit: found no transmits at all - the pattern has gone stale')
        return 1
    if bad or unknown:
        print('%d would log the player out, %d could not be checked' % (len(bad), len(unknown)))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
