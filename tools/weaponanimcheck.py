#!/usr/bin/env python3
"""Every weapon's animations, against Old School's own ids.

    python3 tools/weaponanimcheck.py            # from content/
    python3 tools/weaponanimcheck.py -v         # list the ones that agree too

WHY THIS EXISTS. Four separate rounds of "the animation is wrong" were reported from play in one
week - the dragon warhammer's special twice, then the abyssal bludgeon and the hill giant club
"swinging like a gmaul", then the staves' swipe. Every one of them was an animation id sitting in
an obj param that nothing ever read back. A param can name any animation in the build: the obj
compiles, rs2check is clean, every sim passes, the weapon swings something, and it is the wrong
thing. The abyssal bludgeon carried the granite maul's entire set while its own five animations
had been in all.seq the whole time.

THE SOURCE is rune-server thread 697435, a RuneLite developer-tools dump taken off the OSRS beta
world: stance, walk, run, each attack style, defence and each special, for about seventy weapons.
It is the same source the bludgeon's special attack ids came from, and those were right.

WHAT IT CANNOT DO. It compares ids. Whether an animation LOOKS right is a different question and
needs the client - javaclient/tools/clienttests/run_weaponanim.py photographs a weapon's poses
frame by frame. Use both: this one is cheap and catches a weapon wearing another's animations,
that one catches an id that is right on paper.

DISAGREEING ON PURPOSE is fine and is recorded in KEEP below, with the reason. An entry there is a
decision, not an exception to be cleared.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.dirname(HERE)

# ---------------------------------------------------------------------------------------------
# The dump, as ids. One entry per weapon, keyed by this build's obj debugname.
#   ready / walk / run    the stance set (baseanim params)
#   stab / slash / crush  the attack styles
#   defend                the block
#   spec / specgfx        the special attack and the graphic it throws
# A key that is absent is simply not stated by the dump and is not checked.
DUMP = {
    'dragon_warhammer':   {'crush': 401, 'defend': 403, 'spec': 1378, 'specgfx': 1292},
    'granite_hammer':     {'spec': 1378, 'specgfx': 1450},
    'abyssal_bludgeon':   {'ready': 1652, 'crush': 3298, 'defend': 1666,
                           'spec': 3299, 'specgfx': 1284},
    'dragon_sword':       {'stab': 386, 'slash': 390, 'defend': 4177,
                           'spec': 7515, 'specgfx': 1369},
    'bone_dagger':        {'stab': 376, 'slash': 377, 'defend': 4177,
                           'spec': 4198, 'specgfx': 704},
    'dragon_pickaxe':     {'stab': 401, 'crush': 400, 'defend': 397, 'spec': 7138},
    'dragon_axe':         {'spec': 2876, 'specgfx': 479},
    'barrelchest_anchor': {'ready': 5869, 'walk': 5867, 'run': 5868,
                           'stab': 5865, 'crush': 5865, 'spec': 5870, 'specgfx': 1027},
    'dragon_scimitar':    {'stab': 386, 'slash': 390, 'defend': 4177, 'spec': 1872, 'specgfx': 347},
    'dragon_longsword':   {'stab': 386, 'slash': 390, 'defend': 4177, 'spec': 1058, 'specgfx': 248},
    'dragon_dagger':      {'stab': 376, 'slash': 377, 'defend': 4177, 'spec': 1062, 'specgfx': 252},
    'dragon_mace':        {'stab': 400, 'crush': 401, 'defend': 403, 'spec': 1060, 'specgfx': 251},
    'dragon_2h_sword':    {'slash': 407, 'crush': 406, 'defend': 410, 'spec': 3157, 'specgfx': 559},
    'dragon_spear':       {'stab': 381, 'slash': 380, 'crush': 382, 'defend': 383,
                           'spec': 1064, 'specgfx': 253},
    'abyssal_whip':       {'walk': 1660, 'run': 1661, 'slash': 1658, 'defend': 1659,
                           'spec': 1658, 'specgfx': 341},
    'abyssal_tentacle':   {'slash': 1658, 'defend': 1659, 'spec': 1658, 'specgfx': 1283},
    'staff_of_the_dead':  {'ready': 813, 'stab': 428, 'slash': 440, 'crush': 419, 'defend': 420,
                           'spec': 7083, 'specgfx': 1228},
    'toxic_staff_of_the_dead': {'ready': 813, 'stab': 428, 'slash': 440, 'crush': 419,
                                'defend': 420, 'spec': 7083, 'specgfx': 1228},
    'toxic_staff_uncharged':   {'ready': 813, 'stab': 428, 'slash': 440, 'crush': 419,
                                'defend': 420, 'spec': 7083, 'specgfx': 1228},
    'staff_of_light':     {'ready': 813, 'stab': 428, 'slash': 440, 'crush': 419, 'defend': 420,
                           'spec': 7967, 'specgfx': 1516},
    'saradomin_sword':    {'ready': 7053, 'slash': 7045, 'crush': 7054, 'defend': 7056,
                           'spec': 1133, 'specgfx': 1213},
    'armadyl_godsword':   {'ready': 7053, 'walk': 7052, 'run': 7043, 'slash': 7045,
                           'crush': 7054, 'defend': 7056, 'spec': 7644, 'specgfx': 1211},
    'bandos_godsword':    {'ready': 7053, 'walk': 7052, 'run': 7043, 'slash': 7045,
                           'crush': 7054, 'defend': 7056, 'spec': 7642, 'specgfx': 1212},
    'saradomin_godsword': {'ready': 7053, 'walk': 7052, 'run': 7043, 'slash': 7045,
                           'crush': 7054, 'defend': 7056, 'spec': 7640, 'specgfx': 1209},
    'zamorak_godsword':   {'ready': 7053, 'walk': 7052, 'run': 7043, 'slash': 7045,
                           'crush': 7054, 'defend': 7056, 'spec': 7638, 'specgfx': 1210},
    'granite_maul':       {'ready': 1662, 'walk': 1663, 'run': 1664, 'crush': 1665,
                           'defend': 1666, 'spec': 1667, 'specgfx': 340},
    'toxic_blowpipe':     {'defend': 430, 'spec': 5061, 'specgfx': 1043},
    'dragon_claws':       {'stab': 1067, 'slash': 393, 'defend': 424, 'spec': 7514, 'specgfx': 1171},
    'dark_bow':           {'spec': 426, 'specgfx': 1111},
    'dragon_halberd':     {'stab': 428, 'slash': 440, 'defend': 430, 'spec': 1203},
    'elder_maul':         {'ready': 7518, 'walk': 7520, 'run': 7519, 'crush': 7516, 'defend': 7517},
}

# Disagreements that are decisions. weapon -> {field: why}
KEEP = {
    'dragon_sword':     {'defend': "4177 is Old School's LATER block for every sword - it gives it "
                                   "to the 2006 dragon longsword, scimitar and dagger too - so it "
                                   "is a rework, not something particular to this weapon. 388 is "
                                   "what 2006 blocks with and what every other sword here uses."},
    'dragon_longsword': {'defend': 'as the dragon sword: 4177 is the later rework.'},
    'dragon_scimitar':  {'defend': 'as the dragon sword: 4177 is the later rework.'},
    'dragon_dagger':    {'defend': 'as the dragon sword: 4177 is the later rework.'},
    'bone_dagger':      {'defend': 'as the dragon sword: 4177 is the later rework.'},
    'saradomin_sword':  {'spec': 'OSRS 1132 and 1133 are THE SAME ANIMATION - 28 frames, the '
                                 'same frame ids, the same delays - differing only in '
                                 'replaceheldleft/right, which name an OSRS item to force into '
                                 'the hand and which animconvosrs drops because an OSRS item id '
                                 'means nothing here. Frame for frame this IS 1133.'},
    'barrelchest_anchor': {'spec': 'Rejuvenate is not built - the obj says specwep is deliberately '
                                   'absent until the effect exists. osrs_anchor_spec is imported '
                                   'and waiting.',
                           'specgfx': 'with the special above.'},
}

PARAM = {'ready': 'ready_baseanim', 'walk': 'walk_f_baseanim', 'run': 'running_baseanim',
         'stab': 'stabattack_anim', 'slash': 'slashattack_anim', 'crush': 'crushattack_anim',
         'defend': 'defend_anim'}


def packfile(name):
    out = {}
    with open(os.path.join(CONTENT, 'pack', name), newline='') as f:
        for line in f:
            if '=' in line:
                i, n = line.strip().split('=', 1)
                out[n] = int(i)
    return out


def osrsids(ext, word):
    """name -> the OSRS id it was imported from, out of the configs' own provenance comments.

    AN IMPORTED ANIMATION IS NOT PACKED AT ITS OSRS ID. osrs_dwh_spec is OSRS 1378 and sits at 5724
    in this build, so comparing packed numbers against the dump calls every correctly imported
    animation wrong - sixty-one of them, the first time this ran. The importers write
    "// OSRS seq N" (and "// OSRS spotanim N") under each entry, and that is the number to compare.
    """
    out = {}
    for root, _dirs, files in os.walk(os.path.join(CONTENT, 'scripts')):
        for fn in files:
            if not fn.endswith(ext):
                continue
            text = open(os.path.join(root, fn), encoding='utf-8', newline='').read()
            for m in re.finditer(r'\[(\w+)\]\s*\n//\s*OSRS %s (\d+)' % word, text):
                out[m.group(1)] = int(m.group(2))
    return out


def objblocks():
    """debugname -> the text of its block, for every .obj under scripts/."""
    blocks = {}
    for root, _dirs, files in os.walk(os.path.join(CONTENT, 'scripts')):
        for fn in files:
            if not fn.endswith('.obj'):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding='utf-8', newline='').read().replace('\r\n', '\n')
            for part in re.split(r'\n(?=\[)', text):
                m = re.match(r'\[(\w+)\]', part)
                if m:
                    blocks.setdefault(m.group(1), (os.path.relpath(path, CONTENT), part))
    return blocks


def specof(weapon, scripts):
    """(seq name, spotanim name) the weapon's special plays, read out of the spec scripts.

    Found by the label the dispatch jumps to, so a renamed script is still followed."""
    label = scripts.get(weapon)
    if label is None:
        return None, None
    seq = re.search(r'^anim\((\w+),', label, re.M)
    spot = re.search(r'^\s*\.?spotanim_(?:pl|npc)\((\w+),', label, re.M)
    return (seq.group(1) if seq else None), (spot.group(1) if spot else None)


def speclabels():
    """weapon -> the text of the [label,pvm_<x>_sa] its dispatch entry names."""
    disp = os.path.join(CONTENT, 'scripts/skill_combat/scripts/player/player_special_attack.rs2')
    if not os.path.exists(disp):
        return {}
    text = open(disp, encoding='utf-8', newline='').read()
    want = {}
    for m in re.finditer(r'case ([\w, ]+?)\s*:\s*@(\w+);', text):
        for w in m.group(1).split(','):
            want[w.strip()] = m.group(2)
    bodies = {}
    for root, _dirs, files in os.walk(os.path.join(CONTENT, 'scripts/skill_combat/scripts')):
        for fn in files:
            if not fn.endswith('.rs2'):
                continue
            src = open(os.path.join(root, fn), encoding='utf-8', newline='').read().replace('\r\n', '\n')
            for part in re.split(r'\n(?=\[)', src):
                m = re.match(r'\[label,(\w+)\]', part)
                if m:
                    bodies[m.group(1)] = part
    return {w: bodies[lab] for w, lab in want.items() if lab in bodies}


def main():
    verbose = '-v' in sys.argv
    # Packed ids for what 377 already had - all.seq was unpacked from that cache, so there the
    # packed id IS the cache id - overlaid with the real OSRS id of everything imported.
    seqs = packfile('seq.pack')
    seqs.update(osrsids('.seq', 'seq'))
    spots = packfile('spotanim.pack')
    spots.update(osrsids('.spotanim', 'spotanim'))
    blocks = objblocks()
    labels = speclabels()

    bad = kept = ok = 0
    for weapon in sorted(DUMP):
        want = DUMP[weapon]
        if weapon not in blocks:
            continue                       # not in this build; nothing to say about it
        _rel, block = blocks[weapon]
        keep = KEEP.get(weapon, {})
        lines = []
        for field, wanted in sorted(want.items()):
            if field in ('spec', 'specgfx'):
                seqname, spotname = specof(weapon, labels)
                have_name = seqname if field == 'spec' else spotname
                table = seqs if field == 'spec' else spots
            else:
                m = re.search(r'^param=%s,(\S+)' % PARAM[field], block, re.M)
                have_name = m.group(1) if m else None
                table = seqs
            if have_name is None:
                # A style the weapon does not use is not a fault; a MISSING defend is.
                if field == 'defend':
                    lines.append(('MISSING', field, '-', wanted, keep.get(field)))
                continue
            have = table.get(have_name)
            if have == wanted:
                ok += 1
                if verbose:
                    lines.append(('ok', field, '%s (%s)' % (have_name, have), wanted, None))
            else:
                lines.append(('WRONG', field, '%s (%s)' % (have_name, have), wanted,
                              keep.get(field)))
        shown = [l for l in lines if l[0] != 'ok' or verbose]
        if not shown:
            continue
        print('\n%s' % weapon)
        for state, field, have, wanted, why in shown:
            if state == 'ok':
                print('   ok     %-8s %s' % (field, have))
            elif why:
                kept += 1
                print('   kept   %-8s %-34s osrs %-5s  %s' % (field, have, wanted, why))
            else:
                bad += 1
                print('   %-6s %-8s %-34s osrs %s' % (state, field, have, wanted))

    print('\n%d agree, %d differ on purpose, %d WRONG' % (ok, kept, bad))
    # Weapons the dump does not cover at all, said out loud: an unchecked weapon is not a passing
    # one, and the hill giant club is exactly the case that matters.
    missing = [w for w, (_r, b) in sorted(blocks.items())
               if w not in DUMP and 'param=crushattack_anim,' in b and 'wearpos=righthand' in b
               and ('granite_maul' in b or 'osrs_' in b)]
    if missing:
        print('not in the dump, so not checked: ' + ', '.join(missing))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
