#!/usr/bin/env python3
"""Mutation test for tools/slayer_battery.py.

Each entry breaks one thing the battery claims to catch - in a throwaway copy, never in place - and
the battery has to go red. Same runner as poh_mutate.py and maxcape_mutate.py, copied a third time;
that is now three, so the next one should lift it into a module instead.

    python3 tools/slayer_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'slayer_mutate_work')

MUTS = [
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  '[tab4]\ntype=text', '[tab4]\ntype=rect',
  '2 re-running it changes nothing'),
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  'text=Cosmetics', 'text=Cosmetic',
  '2 tab 4 is Cosmetics'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_tab_buy = 2', '^slayer_tab_buy = 5',
  '2 ^slayer_tab_buy is 2, the column it is drawn in'),
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  '[row10]\ntype=layer', '[row10]\ntype=rect',
  '3 every row is a layer, which is the only thing if_sethide works on'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_task_rows = 6', '^slayer_task_rows = 12',
  '3 the window has a row for every entry the longest tab needs'),
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  '[r5name]\nlayer=row5\ntype=text\nx=6\ny=1\nwidth=328',
  '[r5name]\nlayer=row5\ntype=text\nx=6\ny=1\nwidth=328\noption=Select',
  '3 exactly 11 components carry an option - one per row'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,On task, a monster with a superior form has a 1 in 200 chance',
  'val=0,On task, a monster with a superior form has a 1 in 200 chance of summoning it when it dies, which is a long way of saying it is worth having.',
  '4 every description line is inside the 448px panel'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=1,of summoning it when it dies.\nval=3,',
  'val=1,of summoning it when it dies.\nval=2,and that is a third line.\nval=3,',
  '4 slayer_unlock_desc is exactly two lines per entry, as ^slayer_desc_lines says'),
 # the two recolour unlocks upstream added, which the Cosmetics tab now holds
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,Unholy Helmet', 'val=0,Unholy Helm',
  '4 ^slayer_tab_cosmetics is 4, the column it is drawn in'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  '[slayer_cosmetic_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,5',
  '[slayer_cosmetic_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,7',
  '4 and Bigger and Badder is still bit 4, which is what superiors.rs2 reads'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,1000\nval=1,1000', 'val=0,500\nval=1,1000',
  '4 and it checks the points before it reaches any of them'),
 # The Buy tab, after the imbue left it: contiguous rows, and no service row growing back.
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=2,looting_bag\nval=3,rune_pouch', 'val=2,looting_bag\nval=4,rune_pouch',
  '9 the Buy tab is keyed 0..3 with no gap and every row has both an obj and a price'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  '[slayer_buy_obj]', '[slayer_buy_name]\ninputtype=int\noutputtype=string\ndefault=null\nval=3,Imbue a mask\n\n[slayer_buy_obj]',
  '9 and no row is a service: the name table, the row constant and the special case'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_ui_row_off = 0x4A3F31', '^slayer_ui_row_off = 0x4A3F32',
  '5 ^slayer_ui_row_off is the colour the .if paints r0box with'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_ui_row_on = 0x8C7F63', '^slayer_ui_row_on = 0x4A3F31',
  '5 a selected row is a different brown'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_ui_clicks = 128', '^slayer_ui_clicks = 400',
  '6 and their product is inside the 500,000 opcodes a script gets'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'while ($clicks < ^slayer_ui_clicks) {', 'while ($clicks < 400) {',
  '6 the loop is bounded by that constant'),
 ('scripts/skill_slayer/scripts/slayer_master.rs2',
  '~slayer_rewards_window;', '~slayer_taskname;',
  '7 a master\'s "spend my Slayer points" opens the window'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'mes("Select something first.");', '~chatnpc("Select something first.");',
  '7 and says nothing as the npc (~chatnpc)'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'if (%slayer_points < $cost) {', 'if (%slayer_points < 0) {',
  '8 and Confirm compares the points against the cost at all'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'if (~slayer_ui_owned($tab, $sel) = true) {\n    mes("You already have that.");',
  'if (~slayer_ui_owned($tab, $sel) = false) {\n    mes("You already have that.");',
  '8 and refuses what you already own'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  '[slayer_unlock_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,4',
  '[slayer_unlock_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,0',
  '8 the 9 unlocks own 9 distinct bits, none reused'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=1,120', 'val=1,100',
  "9 the 9 unlock prices are the wiki's, bar the one that is ours"),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,slayer_ring_8', 'val=0,slayer_ring_9',
  '9 and so are the four things you can buy'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_cancel_cost = 30', '^slayer_cancel_cost = 45',
  '9 cancelling is 30 points and blocking 100, as they were before the window'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=1000,1,000', 'val=1000,1000',
  '9 and each one is that number with its thousands separator'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=750,750\n', '',
  '9 every price the window can show has a slayer_cost_text row'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'return("<enum(int, string, slayer_cost_text, $cost)> points");',
  'return("<tostring($cost)> points");',
  '9 and ~slayer_ui_cost_text reaches for the table, not tostring'),
 ('tools/genslayerui.py',
  "    for c in ('slayer_cancel_cost', 'slayer_block_cost'):",
  "    for c in ('slayer_block_cost',):",
  '9 re-running it changes nothing'),
 ('tools/genslayerui.py',
  "ROWS, ROW_Y, ROW_STEP, ROW_H = 11, 90, 15, 14",
  "ROWS, ROW_Y, ROW_STEP, ROW_H = 10, 90, 15, 14",
  '10 re-running it changes nothing'),
 ('tools/genslayerui.py',
  "body = nl.join(src).replace('\\r\\n', '\\n').rstrip('\\n')",
  "body = nl.join(src).rstrip('\\r\\n')",
  '10 the writer normalises before it converts, which is what keeps that true'),
]

def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    fails = 0
    loose = 0
    for path, find, repl, why in MUTS:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-40s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'slayer_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        # WHICH check went red matters. A mutation that trips some OTHER check still exits
        # non-zero, so counting exit codes alone proves only that something noticed - not that the
        # check this mutation was written for is doing anything. This harness had no attribution
        # at all until tools/mutate_labels.py went looking: it printed red or GREEN from the exit
        # code and stopped, which is the weaker thing the other harnesses exist to avoid. Its
        # labels were then rewritten from the checks that actually fire, measured rather than
        # guessed - and one mutation turned out to be caught by a TRACEBACK rather than a check.
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in f for f in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'
            fails += 1
        elif onpoint:
            # More than one check firing means the mutation is broader than the check it names.
            # Not a failure, but worth saying: a mutation that trips four checks proves less about
            # any one of them than a mutation that trips one.
            note = 'caught by its own check'
            if len(fired) > 1:
                note += ' (and %d other%s)' % (len(fired) - 1, '' if len(fired) == 2 else 's')
            state = 'red'
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:60] if fired else 'a non-zero exit with no check named, which is a '
                                            'crash and not a catch')
            loose += 1
        print('  %-5s %-62s %s' % (state, why, note))
        if not ok:
            fails += 1
    print()
    if loose:
        print('%d caught by a check other than the one named - see the note beside each' % loose)
    print('%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
