"""Battery for Teleother - the three spells, the panel, and the Accept aid setting they read.

Three different things get checked here, and they are separate on purpose.

THE NUMBERS. The nine rune counts and three levels in magic_spell_table were not typed from a
wiki: every one of them is derivable from the CACHE's own button in magic.if, which has been
greying these three spells correctly since the unpack. So this battery re-derives all twelve from
the button scripts and compares. The two sides came from different places and neither was copied
from the other, which is the only kind of agreement worth checking.

THE PANEL. scripts/skill_magic/interfaces/teleother.if is inter_251.if renamed in place - Jagex's
own "Teleport Option" screen. Four component blocks were renamed and NOTHING ELSE was touched, so
the checks here are that the cache's own strings are all still in it, that the ids in
interface.pack were kept rather than re-taken, and that no component was lost on the way.

THE FLOW. Ordering, mostly, because the bugs available here are all silent ones: a cost paid
before a check that can still refuse, a close handler that wipes the offer out from under the
accept still reading it, a p_ op in an if_button that has no p_active_player.

    python3 tools/teleother_battery.py
"""
import json
import os
import re

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')


fails = 0


def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1


def nocomment(txt):
    """Strip // comments. Four rounds have now shipped a check that read its own comment and
    called it the code, so this is not optional here."""
    return '\n'.join(re.sub(r'//.*$', '', l) for l in txt.split('\n'))


def block(txt, name):
    key = '[' + name + ']'
    if key not in txt:
        return ''
    return txt.split(key, 1)[1].split('\n[', 1)[0]


def trigger(txt, head):
    """The body of a [trigger,name] block, comments stripped."""
    key = '[' + head + ']'
    if key not in txt:
        return ''
    return nocomment(txt.split(key, 1)[1].split('\n[', 1)[0])


def before(txt, a, b):
    return a in txt and b in txt and txt.index(a) < txt.index(b)


DBROW = read('scripts/skill_magic/configs/magic_spells.dbrow')
CONST = read('scripts/skill_combat/configs/magic/spells.constant')
TOCONST = read('scripts/skill_magic/configs/teleother.constant')
AIDCONST = read('scripts/interface_options/configs/game_options.constant')
RS2 = read('scripts/skill_magic/scripts/spells/teleother.rs2')
CODE = nocomment(RS2)
MAGICIF = read('scripts/skill_magic/interfaces/magic.if')
PANEL = read('scripts/skill_magic/interfaces/teleother.if')
VARP = read('scripts/skill_magic/configs/teleother.varp')
OPTIF = read('scripts/interface_options/interfaces/options.if')
OPTLDIF = read('scripts/interface_options/interfaces/options_ld.if')
OPTRS = nocomment(read('scripts/interface_options/scripts/game_options.rs2'))
OPTLDRS = nocomment(read('scripts/interface_options/scripts/game_options_ld.rs2'))
IFPACK = read('pack/interface.pack')
IFORDER = read('pack/interface.order')
VARPPACK = read('pack/varp.pack')
SEQPACK = read('pack/seq.pack')
SPOTPACK = read('pack/spotanim.pack')
RS2CHECK = read('tools/rs2check.py')
SPEC = json.loads(read('tools/unwiredspells.json'))

# town -> (spell constant, dbrow name, spellbook component, the plain teleport's row)
SPELLS = [
    ('Lumbridge', 'teleother_lumbridge', 'magic_spell_teleother_lumbridge',
     'magic_spell_teleport_lumbridge'),
    ('Falador', 'teleother_falador', 'magic_spell_teleother_falador',
     'magic_spell_teleport_falador'),
    ('Camelot', 'teleother_camelot', 'magic_spell_teleother_camelot',
     'magic_spell_teleport_camelot'),
]


def button_requires(btn):
    """Re-derive (level, {rune: count}) from a spellbook button's own client scripts.

    A button carries scriptNopM=inv_count,inventory:inv,<rune> lines and one scriptN=gt,K per
    group. inv_count on the inventory is the rune; stat_level,magic is the level. gt,K means
    "more than K", so the requirement is K+1. The rune-pouch mirror and the staff substitutes are
    alternative SOURCES of the same rune, so only the inventory line names it."""
    level, runes = None, {}
    for n in range(1, 9):
        cmp_ = re.search(r'^script%d=(\w+),(\d+)$' % n, btn, re.M)
        if not cmp_:
            continue
        op, val = cmp_.group(1), int(cmp_.group(2))
        if re.search(r'^script%dop1=stat_level,magic$' % n, btn, re.M):
            assert op == 'gt', op
            level = val + 1
            continue
        rune = re.search(r'^script%dop1=inv_count,inventory:inv,(\w+)$' % n, btn, re.M)
        if rune:
            assert op == 'gt', op
            runes[rune.group(1)] = val + 1
    return level, runes


def row_runes(row):
    m = re.search(r'^data=runesrequired,(.+)$', row, re.M)
    if not m:
        return {}
    p = [x.strip() for x in m.group(1).split(',')]
    out = {}
    for i in range(0, len(p) - 1, 2):
        if p[i] != 'null':
            out[p[i]] = int(p[i + 1])
    return out


# ============================================================================ 1
print("1. every level and every rune count is the cache's own button, re-derived")
for town, spell, rowname, _plain in SPELLS:
    row, btn = block(DBROW, rowname), block(MAGICIF, spell)
    check(row != '' and btn != '', '%s: the row and the button both exist' % town)
    lvl, runes = button_requires(btn)
    want = re.search(r'^data=levelrequired,(\d+)$', row, re.M)
    # CONSTANT WORDING, offenders appended. mutate_labels reads a CLEAN run, so a message that
    # only exists once something is broken matches no label at all - the ancient book round had to
    # rewrite two checks for this and it is worth not learning twice.
    lvlsame = want is not None and lvl is not None and int(want.group(1)) == lvl
    check(lvlsame, "%s: the row's level requirement is the button's own threshold plus one%s"
          % (town, '' if lvlsame else ' - row %s, button lights above %s'
             % (want.group(1) if want else '?', (lvl - 1) if lvl else '?')))
    same = row_runes(row) == runes and runes != {}
    check(same, '%s: the row costs exactly the runes the button counts%s'
          % (town, '' if same else ' - row %s, button %s'
             % (sorted(row_runes(row).items()), sorted(runes.items()))))

# ============================================================================ 2
print('2. the destination is the ordinary town, and the panel names it from the same place')
for town, spell, rowname, plain in SPELLS:
    mine = re.search(r'^data=tele_coord,(\S+)$', block(DBROW, rowname), re.M)
    theirs = re.search(r'^data=tele_coord,(\S+)$', block(DBROW, plain), re.M)
    check(mine is not None and theirs is not None and mine.group(1) == theirs.group(1),
          '%s: Teleother lands exactly where the plain teleport to that town lands' % town)
    # The string the panel shows is anchored on Jagex's own action text, not written twice.
    act = re.search(r'^action=(.+)$', block(MAGICIF, spell), re.M)
    check(act is not None and act.group(1).strip().endswith(town),
          "%s: the panel's word is the tail of the button's own action text" % town)
    # COUNTED, NOT SEARCHED. Every spell has TWO triggers - opplayert and applayert - and a
    # blanket `in CODE` stays true when one of them is changed, on the strength of the other.
    # That is the Barrows chest's surviving mutation exactly, found the same week; a check that
    # names one call site has to say how many there are.
    check(CODE.count('@teleother_cast(^%s, "%s");' % (spell, town)) == 2,
          '%s: and BOTH of its triggers pass that literal' % town)
# Experience is the one number no button carries, so it is labelled rather than derived.
for town, _spell, rowname, _plain in SPELLS:
    check(re.search(r'^data=experience,\d+$', block(DBROW, rowname), re.M) is not None,
          '%s: the row carries an experience value' % town)
check('OSRS' in DBROW.split('Teleother (Corey')[1].split('[magic_spell_teleother_lumbridge]')[0],
      '...and the comment says the xp came from OSRS rather than from the cache')

# ============================================================================ 3
print("3. the panel is Jagex's own screen, with four blocks renamed and nothing else")
for s in ('text=Teleport Option', 'text=...wants to teleport you to...', 'text=Do you accept?',
          'option=Accept', 'option=Decline',
          'model=spot_teleport_other_impact'):
    check(s in PANEL, "the cache's own %r survived the rename" % s)
for old in ('com_89', 'com_91', 'com_97', 'com_99'):
    check('[%s]' % old not in PANEL, '%s was renamed, not left beside its new name' % old)
for new, was in (('caster', '%1'), ('destination', '%2'), ('accept', 'Accept'),
                 ('decline', 'Decline')):
    b = block(PANEL, new)
    check(b != '' and was in b, '[%s] is the block that used to hold %r' % (new, was))
check(block(PANEL, 'accept').strip().startswith('layer=com_95')
      and block(PANEL, 'decline').strip().startswith('layer=com_96'),
      'both buttons still sit in the layers the cache put them in')
# genadopt MOVES the file rather than copying it, which is what genancientbook.py does not do -
# inter_267.if is still in the tree because ancient_magic.if already existed and had to be
# generated beside it. Nothing existed here, so the panel IS the cache file, renamed, and
# re-running the tool reads its own output back. That is why inter_251.if is gone and must be.
check(not os.path.exists(os.path.join(C, 'scripts/interfaces/inter_251.if'))
      and 'GENERATED by tools/genadopt.py' in PANEL
      and 'from scripts/interfaces/inter_251.if' in PANEL,
      'the panel is genadopt output and says what it was - the adoption is a rerunnable tool, '
      'not a hand rename, and the cache file moved rather than being copied')
spec = {p['iface']: p for p in json.loads(read('tools/adoptspec.json'))['panels']}
tele = spec.get('teleother', {})
check(tele.get('src') == 'scripts/interfaces/inter_251.if'
      and tele.get('dst') == 'scripts/skill_magic/interfaces/teleother.if',
      'and tools/adoptspec.json is where the rename lives, beside the six panels the windows '
      'round adopted - one tool, not two ways of doing this')
check([r['name'] for r in tele.get('rules', [])] == ['accept', 'decline', 'caster', 'destination']
      and all(r['expect'] == 1 for r in tele.get('rules', [])),
      'four rules, one match each, so a panel that is not this one fails the count rather than '
      'renaming the wrong components')
check(all(r['field'] in ('option', 'text') for r in tele.get('rules', [])),
      "...and every rule joins on the panel's OWN text rather than a com_<n> somebody typed")

# ============================================================================ 4
print('4. the panel is packed once, whole, and keeps the id if_openmain puts on the wire')
pack = {}
for l in IFPACK.split('\n'):
    if l:
        i, nm = l.split('=', 1)
        pack[nm] = int(i)
own = pack.get('teleother')
comps = sorted(n for n in pack if n.startswith('teleother:'))
blks = re.findall(r'^\[(\w+)\]$', PANEL, re.M)
check(own is not None, 'the interface itself has an id')
check(own < max(pack.values()),
      'and it is the id inter_251 already had, not a fresh one off the end - genadopt re-takes '
      'the COMPONENT rows and leaves the interface where it is, because an interface id is what '
      'if_openmain puts on the wire')
check(len(comps) == len(blks) and {n.split(':', 1)[1] for n in comps} == set(blks),
      'every component in the .if has a pack id and nothing else does')
check(len(set(pack.values())) == len(pack), 'no duplicate id anywhere in interface.pack')
check(len(set(pack)) == len([l for l in IFPACK.split('\n') if l]),
      'and no duplicate name either - git merges this file line by line and does not know an id '
      'has to be unique, which is a thing to check when two rounds take ids out of order')
order = [int(x) for x in IFORDER.split('\n') if x.strip()]
check(len(order) == len(set(order)) and set(order) == set(pack.values()),
      'interface.order and interface.pack list exactly the same ids, once each')
for spell in ('teleother_lumbridge', 'teleother_falador', 'teleother_camelot'):
    check('magic:%s' % spell in pack, 'magic:%s took the id its com_5NN name had' % spell)
    check('[%s]' % spell in MAGICIF, '...and magic.if carries the name')
# THE POSITIONAL JOIN, checked rather than trusted. %1 and %2 say nothing about what they hold;
# what fixes them is that the caster's slot is ABOVE the "...wants to teleport you to..." line and
# the destination's is below it. adoptspec.json says so in its rule; this asserts it.
def ypos(name):
    m = re.search(r'^y=(\d+)$', block(PANEL, name), re.M)
    return int(m.group(1)) if m else None
mid = next((n for n in blks if 'wants to teleport you to' in block(PANEL, n)), None)
check(mid is not None and ypos('caster') is not None
      and ypos('caster') < ypos(mid) < ypos('destination'),
      'the caster slot really is above the "...wants to teleport you to..." line and the '
      'destination below it, which is the only thing that tells %1 from %2')

# ============================================================================ 5
print('5. no dead clicks: every op the three buttons offer is answered')
for town, spell, _rowname, _plain in SPELLS:
    btn = block(MAGICIF, spell)
    check('buttontype=target' in btn and 'actiontarget=npc,player' in btn,
          '%s: the button is a target button aimed at npcs AND players' % town)
    for t in ('opplayert', 'applayert'):
        check('[%s,magic:%s]' % (t, spell) in CODE, '%s: [%s] is handled' % (town, t))
    for t in ('opnpct', 'apnpct'):
        check('[%s,magic:%s]' % (t, spell) in CODE,
              '%s: [%s] is handled too - the button offers "Cast on" over every npc in the game'
              % (town, t))
check('You can only cast this spell on other players.' in RS2,
      '...and casting one at an npc says so rather than doing nothing')

# ============================================================================ 6
print('6. the cast: everything that can refuse comes before anything that costs')
cast = trigger(CODE, 'label,teleother_cast')
CONSTUSES = CODE.count('^teleother_offer_ticks')
check(cast != '', 'there is a [label,teleother_cast]')
for what, marker in (('the spell requirements', '~check_spell_requirements'),
                     ('Accept aid', '.%option_aid = ^aid_no'),
                     ('the target being busy', '.busy = true'),
                     ('an offer already standing', '.%teleother_expires > map_clock'),
                     ('the wilderness', '~wilderness_level')):
    check(before(cast, marker, '~delete_spell_runes'),
          '%s is checked before the runes are taken' % what)
check(before(cast, '~delete_spell_runes', '.if_openmain(teleother)')
      and before(cast, '~give_spell_xp', '.if_openmain(teleother)'),
      'and the cost is paid before the panel opens - Corey\'s call: on cast, win or lose')
check('.uid = uid' in cast, 'you cannot cast it on yourself')
check('~wilderness_level(.coord)' in cast and '~wilderness_level(coord)' in cast,
      "the wilderness rule is asked of the TARGET's coord and the caster's, not just one of them")
check('.%teleother_caster = uid;' in cast and '.%teleother_spell' in cast
      and '.%teleother_expires = add(map_clock, ^teleother_offer_ticks);' in cast,
      'the offer is stamped on the target, expiry included')
check('.softtimer(teleother_expire, ^teleother_offer_ticks);' in cast
      and before(cast, '.clearsofttimer(teleother_expire)', '.softtimer(teleother_expire'),
      'and the timer is cleared before it is armed, so a second offer cannot leave two running')
# ANCHORED TO END OF LINE. '= 17' is a prefix of '= 170', so a plain substring search calls a
# ten-times-too-long timeout correct - which is what the mutation run found.
check(re.search(r'^\^teleother_offer_ticks = 17$', TOCONST, re.M) is not None
      and CONSTUSES == 2,
      'the timeout is 17 ticks - 10.2 seconds - and lives in one constant, not in two places')

# ============================================================================ 7
print('7. the answer: the order that stops the close handler eating the accept')
acc = trigger(CODE, 'if_button,teleother:accept')
clos = trigger(CODE, 'if_close,teleother')
dec = trigger(CODE, 'if_button,teleother:decline')
tim = trigger(CODE, 'softtimer,teleother_expire')
check(acc != '' and clos != '' and dec != '' and tim != '',
      'accept, decline, close and the timer all exist')
# Scoped to the part AFTER the expiry early-return, because that branch closes and returns
# without reading anything and its if_close is not the one this is about.
body = acc.split('def_coord $dest', 1)[-1]
check('def_coord $dest' in acc and before(body, '~teleother_clear', 'if_close;')
      and before(acc, 'map_findsquare', '~teleother_clear'),
      'ACCEPT reads the offer, then clears it, then closes - in that order, or [if_close] wipes '
      'the offer out from under the accept still reading it')
check(before(acc, '~teleother_answer_caster', '~teleother_clear'),
      '...and the caster is told before the uid it is read from is nulled')
check('%teleother_expires <= map_clock' in acc,
      '...and it checks expiry itself rather than trusting the timer to have fired')
check(before(acc, 'p_finduid(uid)', 'p_delay')
      and before(acc, 'p_finduid(uid)', '~p_telejump_safe')
      and before(acc, 'p_finduid(uid)', '~pre_tele_checks'),
      'and it re-acquires p_active_player before any protected op - an if_button is not handed '
      'one, which the XP lock round paid two deploys to learn')
check('~pre_tele_checks(coord)' in acc and '~wilderness_level(coord) > 20' in acc,
      'the destination checks are re-run at accept, ten seconds after the cast')
check(dec.strip() == 'if_close;',
      'DECLINE is nothing but a close, so the X, the Decline button and being attacked are one '
      'path rather than three')
check('~teleother_answer_caster' in clos and '%teleother_expires <= map_clock' in clos,
      'CLOSE is the decline, and it says nothing when the offer has already been answered')
check('~teleother_flush' not in CODE and 'queue(' not in clos,
      '...and it queues nothing: an [if_close] has no protected access (the Barrows chest round)')
check('%teleother_expires > map_clock' in tim and 'return;' in tim,
      'the TIMER refuses to fire on an offer that has been re-armed underneath it')
clear = trigger(CODE, 'proc,teleother_clear')
check('%teleother_caster = null;' in clear and '%teleother_expires = 0;' in clear
      and 'clearsofttimer(teleother_expire);' in clear,
      'one clear, and it clears the timer as well as the three varps')
check(CODE.count('[proc,teleother_clear]') == 1
      and len(re.findall(r'%teleother_expires = 0;', CODE)) == 1,
      '...and it is the only place that clears them')

# ============================================================================ 8
print('8. the varps: temp, unprotected, and appended')
for n in ('teleother_caster', 'teleother_spell', 'teleother_expires'):
    b = block(VARP, n)
    check(b != '', '%s is declared' % n)
    check('protect=no' in b, '%s is protect=no - the caster writes it through the secondary '
                             'pointer from inside [opplayert]' % n)
    check('scope=perm' not in b, '%s is temp, so a pending offer cannot survive a logout' % n)
    check(re.search(r'^\d+=%s$' % n, VARPPACK, re.M) is not None, '%s is in varp.pack' % n)
check(block(VARP, 'teleother_caster').count('type=player_uid') == 1,
      'the caster is a player_uid, not an int, so ~finduid can get back to them')
vids = {l.split('=', 1)[1]: int(l.split('=', 1)[0]) for l in VARPPACK.split('\n') if l.strip()}
check(len(vids) == len([l for l in VARPPACK.split('\n') if l.strip()]),
      'no duplicate name in varp.pack')
# PINNED, NOT "HIGHEST". These three were appended past every id that existed when they went in,
# and that was the whole of what this check could say at the time - it went red the first time
# anything else was appended after them, which is the normal way a varp is added and not a fault.
# What a save file actually depends on is that an id NEVER MOVES: a character's varps are stored by
# id, so 1190 has to go on meaning teleother_caster for as long as there are saves. So the three
# are pinned to the numbers they were given, they stay contiguous and in order, and nothing else
# in varp.pack may use those ids.
PINNED = {'teleother_caster': 1190, 'teleother_spell': 1191, 'teleother_expires': 1192}
mine = [vids[n] for n in ('teleother_caster', 'teleother_spell', 'teleother_expires')]
_moved = {n: vids.get(n) for n, i in PINNED.items() if vids.get(n) != i}
check(not _moved and mine == sorted(mine) and mine == list(range(mine[0], mine[0] + 3)),
      'and all three still hold the ids they were given, contiguous and in order - a varp id is '
      'part of what a save '
      'file means, so one can never move: %s'
      % (_moved or ', '.join('%s=%d' % (n, i) for n, i in sorted(PINNED.items(), key=lambda x: x[1]))))

# ============================================================================ 9
print('9. Accept aid: the setting this spell reads, and the two handlers that were wrong')
check('^aid_unset = 0' in AIDCONST and '^aid_yes = 1' in AIDCONST and '^aid_no = 2' in AIDCONST,
      'the tri-state is 0 unset / 1 yes / 2 no')
check('%option_aid = ^aid_yes;' in OPTRS and '%option_aid = ^aid_no;' in OPTRS,
      "options:accept_aid sets %option_aid both ways - the 377 tab's Yes/No pair once set %option_pm, "
      'which belongs to Split Private-chat, so Accept Aid silently moved your private chat setting')
check(OPTRS.count('%option_pm = 1;') == 1 and OPTRS.count('%option_pm = 0;') == 1,
      '...and exactly one handler still sets %option_pm, which is Split Private-chat')
check('%option_aid = ^aid_yes;' in OPTLDRS and '%option_aid = ^aid_no;' in OPTLDRS,
      'the low-detail tab - which had it right all along - uses the same constants')
# 474's Options tab has ONE Accept Aid toggle, lit while aid is on; the low-detail tab keeps 377's pair.
ba = block(OPTIF, 'accept_aid')
check('pushvar,option_aid' in ba and 'buttontype=toggle' in ba,
      'options: accept_aid really is the Accept Aid toggle')
check('script1=lt,2' in ba,
      'options: Yes lights below 2, so an account that has never opened this tab shows Yes - '
      'a varp has no default and 0 is what every existing save holds')
by, bn = block(OPTLDIF, 'com_33'), block(OPTLDIF, 'com_34')
check('pushvar,option_aid' in by and 'pushvar,option_aid' in bn,
      'options_ld: both buttons really are the Accept Aid pair')
check('script1=lt,2' in by,
      'options_ld: Yes lights below 2, so an account that has never opened this tab shows Yes - '
      'a varp has no default and 0 is what every existing save holds')
check('script1=eq,2' in bn, 'options_ld: No lights on 2')
check('.%option_aid = ^aid_no' in CODE,
      'and Teleother is the first thing in the build that reads the setting at all')

# ============================================================================ 10
print('10. the rule that found these three, and the art they use')
check('magic:com_511' not in json.dumps(SPEC) and 'magic:com_521' not in json.dumps(SPEC)
      and 'magic:com_541' not in json.dumps(SPEC),
      'all three are out of tools/unwiredspells.json - rule 23 goes red on a spec entry for a '
      'button that IS wired, so leaving them would have been a lie in both directions')
check('magic:com_531' in SPEC, 'Tele Block stays: it needs a mechanism, not a panel')
check('unwiredspells' in RS2CHECK, 'rule 23 still reads the spec')
for seq in ('human_teleport_other_casting', 'human_teleport_other_impact'):
    check(re.search(r'^\d+=%s$' % seq, SEQPACK, re.M) is not None
          and seq in CODE, '%s is in seq.pack and the script uses it' % seq)
for sa in ('teleport_other_casting', 'teleport_other_impact'):
    check(re.search(r'^\d+=%s$' % sa, SPOTPACK, re.M) is not None
          and 'spotanim_pl(%s,' % sa in CODE, '%s is in spotanim.pack and the script uses it' % sa)

# ============================================================================ 11
print('11. no unproven idiom')
bad = []
if 'def_string' in CODE:
    bad.append('def_string')
if 'while (true)' in CODE:
    bad.append('while (true)')
if re.search(r'\)\(string\)', CODE):
    bad.append('a proc returning a string')
if re.search(r'<\$\w+>', RS2):
    bad.append('interpolating a string variable')
check(not bad, 'none of the four idioms with no precedent in this repo%s'
      % ('' if not bad else ': %s' % bad))
check(len(re.findall(r'^\[', CODE, re.M)) == len(set(re.findall(r'^\[[^\]]+\]', CODE, re.M))),
      'and no trigger is declared twice, which is a hard build error rather than a warning')

print()
print('%d FAILED' % fails if fails else 'ALL PASS')
raise SystemExit(1 if fails else 0)
