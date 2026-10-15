"""Battery for the server-wide announcements - rare drops, pets, capes and ::yell.

    python3 tools/broadcast_battery.py

What it holds in place, and why each is a thing that has already gone wrong once:

  ONE PLACE BUILDS A BROADCAST. There were fourteen hand-written copies of the rare-drop line in
  fourteen files; restyling them meant finding every one, and a copy that was missed would have
  gone on printing plain black text. broadcast_mes is called from general/scripts/broadcast.rs2
  and nowhere else.
  EVERY PET ANNOUNCES. Only the Jad pet did; boss pets, skill pets and the Kraken's did not.
  THE ICON SHEET HAS ALL EIGHT ICONS, keyed on magenta. The packer takes 0xff00ff as transparent and
  ignores alpha, so an icon drawn with alpha-transparent corners ships with black ones.
  THE CROWN RULE IS THE ENGINE'S. ~broadcast_name must give the crown engine ChatCrown gives the
  same player's chat lines - 1 silver, 2 and 3 gold, 4 purple, 5 red, 6 and up blue and gold - or a moderator's yell and
  their chat show different ranks, which is exactly what ::yell used to do.
"""
import os
import re
import sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(cond, what):
    global fails
    print(('  ok   ' if cond else '  FAIL ') + what)
    if not cond:
        fails += 1


def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')


def nocomment(s):
    return '\n'.join(l.split('//', 1)[0] for l in s.split('\n'))


SCRIPTS = []
for root, _, files in os.walk(os.path.join(C, 'scripts')):
    for f in files:
        if f.endswith('.rs2'):
            p = os.path.relpath(os.path.join(root, f), C).replace(os.sep, '/')
            SCRIPTS.append((p, nocomment(read(p))))
BC = nocomment(read('scripts/general/scripts/broadcast.rs2'))

print('one place builds a broadcast')
outside = [p for p, s in SCRIPTS if 'broadcast_mes(' in s and p not in ('scripts/engine.rs2', 'scripts/general/scripts/broadcast.rs2')]
check(not outside, 'broadcast_mes is called only from broadcast.rs2%s' % (': also ' + ', '.join(outside) if outside else ''))
for proc in ('broadcast_name', 'broadcast_news', 'broadcast_drop', 'broadcast_pet', 'broadcast_staff', 'yell'):
    check('[proc,%s]' % proc in BC, '[proc,%s] exists' % proc)
drops = sum(s.count('~broadcast_drop(') for p, s in SCRIPTS)
check(drops >= 12, 'the rare-drop tables call ~broadcast_drop (%d calls)' % drops)

print('every pet announces, because one proc hands every pet over')
# THIS USED TO BE FIVE FILES AND THE STRING EACH HAD TO CONTAIN, and all five went red when pet
# granting was funnelled into ~pet_receive (npc/scripts/follower.rs2), whose own header says it:
# "Every pet the game hands out comes through here - boss drops, skilling, the Fight Cave, the
# drop-rate boost". None of the five announces for itself any more and kraken_drops.rs2 does not
# hand the pet over at all - it rolls, and ~bosspet_roll queues the funnel. Checking the funnel is
# a stronger statement than checking five copies: a sixth route cannot forget to announce, because
# announcing is not something a route does.
FOLLOWER = nocomment(read('scripts/npc/scripts/follower.rs2'))
_callers = sorted(p for p, s in SCRIPTS if '~broadcast_pet(' in s)
check(_callers == ['scripts/npc/scripts/follower.rs2'],
      '~broadcast_pet is called from one file and no other: %s' % ', '.join(_callers) or 'nowhere')
_recv = FOLLOWER.split('[proc,pet_receive]', 1)[1].split('\n[', 1)[0] if '[proc,pet_receive]' in FOLLOWER else ''
check('~broadcast_pet($pet)' in _recv,
      '...and the call is inside ~pet_receive, which is the one proc that hands a pet over')
# All three of its endings announce, because the call is after them and none of them returns: it
# follows you, it goes in the pack, or it waits at Probita's. Only the already-owned path returns
# early, and that one must NOT announce - the player has the pet already.
check(_recv.count('return;') == 1 and _recv.index('return;') < _recv.index('~broadcast_pet($pet)'),
      '...after all three of follow, pack and Probita\'s, with the one early return before it')
check(_recv.count('would have been followed') == 1
      and _recv.index('would have been followed') < _recv.index('return;'),
      'the one path that does not announce is the one where the player owns it already, and its '
      '"...would have been followed..." sits in front of that return')
# and every route the header names reaches it
for _p, _want in (('scripts/npc/scripts/boss_pets.rs2', '~pet_receive_later($pet, 0)'),
                  ('scripts/npc/scripts/skill_pets.rs2', '~pet_receive($pet)'),
                  ('scripts/areas/area_kraken_cove/scripts/kraken_drops.rs2', '~bosspet_roll(bosspet_kraken_item'),
                  ('scripts/minigames/game_fightcave/scripts/fightcave_reward.rs2', '~pet_receive_later(bosspet_tzrek_jad_item'),
                  ('scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2', '~pet_receive(bosspet_tzrek_jad_item)'),
                  ('scripts/gamemodes/scripts/droprate.rs2', '~pet_receive_later($obj, 0)')):
    check(_want in nocomment(read(_p)),
          '%s hands its pet to the funnel rather than granting one itself' % _p.split('/')[-1])

print('the icon sheet')
try:
    from PIL import Image
    im = Image.open(os.path.join(C, 'sprites/mod_icons.png')).convert('RGBA')
    opt = read('sprites/meta/mod_icons.opt').split('\n')[0].strip()
    tw, th = (int(n) for n in opt.split('x'))
    check((tw, th) == (13, 13), 'tiles are 13x13 (%s)' % opt)
    check(im.size == (8 * tw, th), 'eight tiles - two crowns, three XP-mode badges, the developer crown and both owner crowns (%dx%d)' % im.size)
    alpha = sum(1 for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3] < 255)
    check(alpha == 0, 'transparency is magenta, not alpha - the packer ignores alpha (%d alpha pixels)' % alpha)
    for t in range(im.width // tw):
        corner = im.getpixel((t * tw, 0))[:3]
        check(corner == (255, 0, 255), '...tile %d has a transparent corner' % t)
except ImportError:
    print('  skip the icon sheet needs Pillow (pip install pillow)')

print('the crown rule')
m = re.search(r'\[proc,broadcast_name\]\(\)\(string\)(.*?)\n\[', BC + '\n[', re.S)
body = m.group(1) if m else ''
rule = re.findall(r'staffmodlevel >= (\d)\) \{\s*\$icons = "(@cr\d@)"', body)
check(rule == [('6', '@cr8@'), ('5', '@cr7@'), ('4', '@cr6@'), ('2', '@cr2@'), ('1', '@cr1@')],
      '6+ blue and gold, 5 red, 4 purple, 2+ gold, 1+ silver - engine ChatCrown\'s rule (%s)' % rule)
badges = dict(re.findall(r'case (\^xprate_\w+|default) : \$icons = append\(\$icons, "(@cr\d@)"\)', body))
check(badges.get('^xprate_10x') == '@cr5@' and badges.get('^xprate_5x') == '@cr4@' and badges.get('default') == '@cr3@',
      '10x, 5x, and Realism for everything else, unset included (%s)' % badges)
check('~xprate_current' in body and '%xp_rate' not in body and 'displayname' in body,
      '...read through ~xprate_current, never %xp_rate itself, around the player\'s own display name')

print(fails == 0 and '\nALL PASS' or '\n%d FAILED' % fails)
raise SystemExit(1 if fails else 0)
