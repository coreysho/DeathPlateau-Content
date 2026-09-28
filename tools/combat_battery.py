"""Battery for the three things play reported on 2026-09-21, and the two it turned up.

All five were the same shape: CONTENT THAT EXISTS AND CANNOT BE REACHED WITHOUT ENDING THE SESSION.
A weapon with no attack sound, and five finished spells with no row in the table. rs2check rules
19, 21 and 22 are where the general cases live and the selftest proves those go red; what is here
is the part a linter cannot know - the numbers, which came off the wiki on 2026-09-21, and the
autocast arming, which is a three-way agreement between a script, a varbit and an interface.

    python3 tools/combat_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

AUTO = read('scripts/skill_combat/scripts/player/auto_cast.rs2')
STYLES = read('scripts/skill_combat/scripts/player/player_attackstyles.rs2')
STAFFIF = read('scripts/skill_combat/interfaces/magic/combat_staff_2.if')
VARBIT = read('scripts/_unpack/377/all.varbit')
ROWS = read('scripts/skill_combat/configs/magic/magic_combat_spells.dbrow')
MAGIC = read('scripts/skill_combat/scripts/player/player_magic.rs2')
IBANPVM = read('scripts/skill_combat/scripts/player/spells/scripts/ibans_blast.rs2')
IBANPVP = read('scripts/skill_combat/scripts/pvp/spells/scripts/ibans_blast.rs2')
UPASS = read('scripts/quests/quest_upass/scripts/quest_upass.rs2')

def block(txt, name):
    return txt.split('[' + name + ']', 1)[1].split('\n[', 1)[0] if '[' + name + ']' in txt else ''

def row(name):
    out = {}
    for line in block(ROWS, name).split('\n'):
        t = line.split('//')[0].strip()
        if t.startswith('data='):
            k, v = t[5:].split(',', 1)
            out[k] = v.strip()
    return out


print('1. choosing an autocast spell arms it')

# THE BUG: @open_autocast_interface writes %autocast_set = 0 before the picker opens, and choosing
# a spell used to leave it there - so the spell name appeared, the toggle stayed grey, and the next
# click on an npc was a melee swing. Reported as "ibans staff autocasting fire wave" followed by a
# melee script error.
_set = block(AUTO, 'label,set_autocast_spell')
check('%autocast_spell = $spell;' in _set, 'the chosen spell is remembered')
check('%autocast_set = 1;' in _set, '...and autocast is turned ON by choosing, the way OSRS does it')
check(_set.index('%autocast_set = 1;') > _set.index('if (~check_spell_requirements($spell_data) = false) {'),
      '...after the requirement check, so a spell you cannot cast does not arm it')

# and the three places that bit lives all have to mean the same bit
_vb = block(VARBIT, 'autocast_set')
check('basevar=lastcastspell' in _vb and 'startbit=0' in _vb and 'endbit=0' in _vb,
      'autocast_set is one bit of lastcastspell')
# UPDATED 2026-09-28: the staff tab's single on/off toggle is gone. It is two Spell boxes now, one
# for a plain cast and one for a defensive one, and they are combat styles like Bash and Pound - so
# the lamp follows %com_mode (3 and 4, the two rows added to weapon_staff_table) rather than the
# autocast bit, and autocast is turned off by picking a style that is not a spell.
check('option=Spell' in block(STAFFIF, 'auto_cast') and 'script1=eq,3' in block(STAFFIF, 'auto_cast'),
      '...the plain Spell box lights up on com_mode 3')
check('option=Spell' in block(STAFFIF, 'auto_defensive') and 'script1=eq,4' in block(STAFFIF, 'auto_defensive'),
      '...the defensive Spell box on com_mode 4')
check('if (%damagetype ! ^magic_style) {' in block(STYLES, 'proc,set_attackstyle')
      and '%autocast_set = 0;' in block(STYLES, 'proc,set_attackstyle'),
      '...and picking a style that is not a spell clears that same bit, as OSRS turns autocast off')
check('testbit(%autocast_set, 0) = ^true & %autocast_spell > 0' in AUTO,
      'and combat still needs BOTH the bit and a spell before it casts')

print()
print('2. the five spells that had no row')

# EVERY NUMBER HERE IS THE WIKI'S, read 2026-09-21. Experience is stored in tenths, which is what
# stat_advance takes and what every other row in that file is (it said x100 until 2026-09-23, and
# paid ten times the wiki's figure). This is the check that cannot come from the code, because the
# code is what it is checking - so the figures are written out once, here, with what they mean.
WIKI = {
    # row name                       level xp/10 maxhit  runes                              worn
    'magic_combat_iban_blast':       (50, 300, 25,  'firerune,5,deathrune,1,null,null',     'ibanstaff'),
    'magic_combat_crumble_undead':   (39, 245, 15,  'airrune,2,earthrune,2,chaosrune,1',    None),
    'magic_combat_saradomin_strike': (60, 350, 20,  'airrune,4,firerune,2,bloodrune,2',     'saradomin_staff'),
    'magic_combat_claws_of_guthix':  (60, 350, 20,  'airrune,4,firerune,1,bloodrune,2',     'guthix_staff'),
    'magic_combat_flames_of_zamorak':(60, 350, 20,  'airrune,1,firerune,4,bloodrune,2',     'zamorak_staff'),
}
for name, (lvl, xp, maxhit, runes, worn) in sorted(WIKI.items()):
    d = row(name)
    short = name[len('magic_combat_'):]
    # BY THE SPELL ID, NOT THE BLOCK NAME. The block name is a label nothing reads; ~get_spell_data
    # finds a row by db_find(magic_spell_table:spell, ...), so a row whose spell field says
    # something else is exactly as absent as no row at all - and a mutation that renamed the id
    # walked straight past the first version of this check, which only asked whether the block
    # existed.
    check(d.get('spell') == '^' + short,
          '%s has a row under its own spell id - this is the whole bug' % short)
    check(d.get('levelrequired') == str(lvl) and d.get('experience') == str(xp)
          and d.get('maxhit') == str(maxhit),
          '...%s: level %d, %s xp, max %d' % (short, lvl, xp / 10.0, maxhit))
    check(d.get('runesrequired') == runes, '...and costs %s' % runes.replace(',null,null', ''))
    if worn:
        check(d.get('wornrequired') == worn and 'reqmessage' in ' '.join(d),
              '...and needs %s wielded, with a message saying so' % worn)
    else:
        check('wornrequired' not in d, '...and needs nothing wielded, which is right for it')

# the two fields player_magic.rs2 reads with no guard at all
for name in sorted(WIKI):
    d = row(name)
    check('anim' in d and 'spotanim_target' in d,
          '%s carries the two fields that are read unguarded' % name[len('magic_combat_'):])

# the god spells land rather than fly, and their charged max is the wiki's 30
GODS = ['magic_combat_saradomin_strike', 'magic_combat_claws_of_guthix',
        'magic_combat_flames_of_zamorak']
check(all('spotanim_proj' not in row(n) for n in GODS),
      'no god spell carries a projectile - in OSRS they land on the target')
check(all(row(n).get('continue_by_autocast') == 'no' for n in GODS),
      '...and none of them autocasts: the only god staves here are the plain ones, which cannot')
check(len({row(n)['spotanim_target'] for n in GODS}) == 3,
      '...and each has its own impact effect, not one shared between them')
_scaled = [int(row(n)['maxhit']) * 3 // 2 for n in GODS]
check(_scaled == [30, 30, 30],
      'the scale(3, 2, $maxhit) in their scripts turns 20 into the wiki\'s charged 30')
check(row('magic_combat_crumble_undead').get('continue_by_autocast') == 'yes',
      'crumble undead DOES continue an autocast, which player_magic.rs2 says is OSRS behaviour')

print()
print('3. Iban\'s staff charges')

check('%iban_staff_charges < 1' in IBANPVM and '%iban_staff_charges = sub(%iban_staff_charges, 1);' in IBANPVM,
      'a cast at an npc costs one charge and is refused at zero')
check('%iban_staff_charges < 2' in IBANPVP and '%iban_staff_charges = sub(%iban_staff_charges, 2);' in IBANPVP,
      'a cast at a player costs two, which is what OSRS charges')
check('%iban_staff_charges = 120;' in UPASS,
      'and Underground Pass is still what fills it, at 120')

print()
print('4. a prayer pressed while you are busy')

# Player.busy() is delayed || containsModalInterface, and p_finduid fails whenever canAccess()
# does - so a prayer pressed during a spec, a teleport or a skilling swing used to fall through to
# a resync and the orb flicked back off. The queue gets protected access and only runs once
# canAccess() is true again, so the press survives the delay instead of being thrown away.
import glob as _glob
_PRAY = sorted(_glob.glob(os.path.join(C, 'scripts/skill_prayer/scripts/prayers/*.rs2')))
# 26 since 474's tab (2026-09-23): 377's 18 and Sharp Eye, Mystic Will, Hawk Eye, Mystic Lore, Eagle
# Eye, Mystic Might, Chivalry and Piety - every one of them held to the same rules below
check(len(_PRAY) == 26, 'all %d prayers are here' % len(_PRAY))
_bad, _noclear, _stale = [], [], []
for _f in _PRAY:
    _t = open(_f, newline='').read().replace('\r\n', '\n')
    _name = os.path.basename(_f)
    _btn = re.search(r'\[if_button,prayer:(\w+)\]', _t)
    _lbl = re.search(r'\[label,(activate_\w+)\]', _t)
    if not _btn or not _lbl:
        _bad.append((_name, 'no button or no activate label')); continue
    _b, _l = _btn.group(1), _lbl.group(1)
    if 'queue(retry_%s, 0, 0);' % _b not in _t:
        _bad.append((_name, 'does not queue a retry'))
    if '[queue,retry_%s]\n@%s;' % (_b, _l) not in _t:
        _bad.append((_name, 'the retry does not run the same activate label'))
    # the success path must RETURN, or a prayer that worked would queue a second toggle and
    # turn itself straight back off
    if 'if (p_finduid(uid) = true) {\n    @%s;\n    return;\n}' % _l not in _t:
        _bad.append((_name, 'the direct path does not return, so it would toggle twice'))
    if re.search(r'^%\w+ = %\w+;', _t, re.M):
        _stale.append(_name)
    # AND IT MUST NOT COME BACK. p_clearpendingaction nulls Player.target, so a prayer toggle
    # dropped whatever you were attacking. Upstream cites three period videos for it and Corey
    # chose Old School feel over 2006 authenticity on 2026-09-21; the citation is kept in
    # clarity.rs2 beside the decision. An EXECUTABLE line is what counts - every one of these
    # files now says the words in a comment.
    if [l for l in _t.split('\n') if l.split('//')[0].strip().startswith('p_clearpendingaction')]:
        _noclear.append(_name)
check(not _bad, 'every prayer queues its own retry and returns on the direct path: %s'
      % (_bad[:3] or 'all 18'))
check(not _stale, 'and none of them still falls through to a bare varp resync: %s'
      % (_stale[:3] or 'none'))
check(not _noclear, 'and none of them clears your pending action any more, so praying does not '
      'drop what you were attacking: %s' % (_noclear[:3] or 'all 18 clean'))
_clarity = open(os.path.join(C, 'scripts/skill_prayer/scripts/prayers/clarity.rs2'), newline='').read()
check(_clarity.count('youtu') >= 3,
      '...with the three videos upstream cited kept beside the decision, not deleted with the line')

print()
print('5. the obsidian staff stands like a person')

# thzaar_staff_ready and thzaar_staff_walk are the animations a TZHAAR wielding a staff uses.
# They were on the player's base anims for the Toktz-mej-tal, on a human skeleton - reported from
# play 2026-09-21 as "broken animation and stance". The evidence that it was wrong is the other
# 32 staves, not an opinion: every one of them uses human_staffready, and NOT ONE overrides the
# walk, because a one-handed staff walks the way the player walks.
_ALLOBJ = read('scripts/_unpack/377/all.obj')
def _params(txt, name):
    b = txt.split('[%s]\n' % name, 1)[1].split('\n[', 1)[0] if '[%s]\n' % name in txt else ''
    return {l[6:].split(',')[0]: l[6:].split(',', 1)[1]
            for l in b.split('\n') if l.startswith('param=')}
_obby = _params(_ALLOBJ, 'tzhaar_staff')
check(_obby.get('ready_baseanim') == 'human_staffready',
      'the obsidian staff is held the way the other 32 staves are held')
# It is TWO-handed (wearpos2=lefthand), unlike the one-handed staves above, so the plain player
# walk swung the off hand through it. It walks, runs and turns the way the halberds do.
_halberd = _params(_ALLOBJ, 'rune_halberd')
_walks = ('walk_f_baseanim', 'walk_b_baseanim', 'walk_l_baseanim', 'walk_r_baseanim',
          'running_baseanim', 'turnonspot_baseanim')
check(all(_obby.get(k) and _obby.get(k) == _halberd.get(k) for k in _walks),
      'and, being two-handed, walks, runs and turns the way the halberds do: %s'
      % ([_obby.get(k) for k in _walks]))
check(not [k for k, v in _obby.items() if v.startswith('thzaar')],
      '...and carries no TzHaar animation at all - those are npc animations: %s'
      % ([k for k, v in _obby.items() if v.startswith('thzaar')] or 'none'))
check(_obby.get('crushattack_anim') == 'human_stafforb_pummel'
      and _obby.get('defend_anim') == 'human_stafforb_block',
      'its attack and defend are the human_stafforb pair 23 other staves use, untouched')

# and the invariant the outlier was found against, so the next staff cannot repeat it: a one-handed
# staff walks as the player walks, and a two-handed one (wearpos2=lefthand) may walk only as the
# halberds do - never with an npc's animation, as the Toktz-mej-tal once did.
_staves, _overrides = 0, []
_cur, _cat, _p, _two = None, None, {}, False
for _line in _ALLOBJ.split('\n') + ['[end]']:
    _t = _line.split('//')[0].strip()
    if _t.startswith('[') and _t.endswith(']'):
        if _cat == 'weapon_staff':
            _staves += 1
            _bad = [k for k in _p if (k.startswith('walk_') or k.startswith('running'))
                    and not (_two and _p[k].startswith('human_halberd'))]
            if _bad:
                _overrides.append((_cur, _bad))
        _cur, _cat, _p, _two = _t[1:-1], None, {}, False
    elif _t == 'wearpos2=lefthand':
        _two = True
    elif _t.startswith('category='):
        _cat = _t.split('=', 1)[1]
    elif _t.startswith('param='):
        _p[_t[6:].split(',')[0]] = _t[6:].split(',', 1)[1]
check(_staves > 20 and not _overrides,
      'and no weapon_staff walks other than as the player (one-handed) or a halberd (two-handed): %d checked, %s'
      % (_staves, _overrides[:2] or 'none do'))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
