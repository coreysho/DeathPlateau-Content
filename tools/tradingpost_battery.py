"""Battery for the Trading Post - the windows, the script that drives them, and the post itself.

The market's own rules - escrow, refunds, nothing created or destroyed - are checked in the engine,
by engine/tools/tradingpostcheck.ts, against the real TradingPost class and a real SQLite. What is
left for this side is the part only content can get wrong, and every bug available here is a
silent one:

  THE BARTER INV HOLDS REAL ITEMS. It must be handed back whatever closes its window, and the
  only place that can happen is [if_close,tradingpost_offer].
  EVERY tp_ ACTION ANSWERS. Each returns '' or a line to show; a call whose answer is thrown away
  is a trade that failed while the player was told nothing.
  THREE CLICKS CANNOT BE UNDONE. Buy now, Accept and Take down each arm %tp_confirm on the first
  click and act on the second - and nothing else may call the action they guard.
  EVERY BUTTON IS WIRED, and every component the script names exists in a window.
  THE POST IS WHERE IT SAYS: the loc, its pack id, its model, and Edgeville's map line agree.

    python3 tools/tradingpost_battery.py
"""
import os
import sys
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
    return '\n'.join(re.sub(r'//.*$', '', l) for l in txt.split('\n'))


def block(txt, header):
    """The body of one script, from its [header] to the next [ at column 0."""
    i = txt.find(header)
    if i < 0:
        return ''
    j = txt.find('\n[', i + len(header))
    return txt[i:] if j < 0 else txt[i:j]


RS2 = nocomment(read('scripts/tradingpost/scripts/tradingpost.rs2'))
IFS = {n: read('scripts/tradingpost/interfaces/%s.if' % n)
       for n in ('tradingpost', 'tradingpost_listing', 'tradingpost_offer', 'tradingpost_side')}

print('the barter inv goes back')
close = block(RS2, '[if_close,tradingpost_offer]')
check('~moveallinv(tp_barter, inv)' in close, '[if_close,tradingpost_offer] empties tp_barter into the inventory')
check(close.count('\n') < 6, 'and does little else - it runs unprotected, whatever closed the window')
refresh = block(RS2, '[proc,tp_offer_refresh]')
check('if_openmain' not in refresh, 'refreshing the offer window does not reopen it (reopening would close it, and hand the items back)')
inv = read('scripts/tradingpost/configs/tradingpost.inv')
barter = inv[inv.find('[tp_barter]'):]
check('protect=no' in barter.split('\n\n')[0], 'tp_barter is protect=no, so the unprotected close can empty it')
check('scope=perm' not in inv, 'every trading post inv is temp - the market is in the engine, not in a save')
add = block(RS2, '[proc,tp_barter_add]')
check('inv_itemspace2(tp_barter' in add and add.find('inv_itemspace2') < add.find('inv_moveitem'),
      'an offer is only given what fits in it - inv_moveitem drops the rest on the floor')

print('every action answers')
for cmd in ('tp_list', 'tp_buynow', 'tp_makeoffer', 'tp_accept', 'tp_decline', 'tp_withdraw', 'tp_cancel', 'tp_collect'):
    lines = [l.strip() for l in RS2.split('\n') if re.search(r'(?<![~\w])%s\(' % cmd, l) and not l.startswith('[')]
    kept = [l for l in lines if re.match(r'^(def_string )?\$err = %s\(' % cmd, l)]
    check(len(lines) > 0 and kept == lines, '%s: every call keeps its answer (%d of %d)' % (cmd, len(kept), len(lines)))
check(RS2.count('string_length($err) > 0') >= 10, 'and every answer is looked at')

print('the three that cannot be undone')
for button, confirm, cmd in (('tradingpost_listing:buynow', 'buynow', 'tp_buynow('),
                             ('tradingpost_listing:accept', 'accept', 'tp_accept('),
                             ('tradingpost_listing:cancel', 'cancel', 'tp_cancel(')):
    b = block(RS2, '[if_button,%s]' % button)
    arm = b.find('%%tp_confirm ! ^tp_confirm_%s' % confirm)
    act = b.find(cmd)
    check(arm >= 0 and act > arm and 'return;' in b[arm:act], '%s arms on the first click and acts on the second' % button)
    elsewhere = RS2.replace(b, '')
    check(cmd not in elsewhere, '%s is called from nowhere else' % cmd.rstrip('('))
for nav in ('[proc,tp_inspect]', '[proc,tp_lists]', '[proc,tp_pick]'):
    check('%tp_confirm = ^tp_confirm_none' in block(RS2, nav), '%s disarms, so a confirm cannot carry over to something else' % nav)

print('every button is wired')
for name, txt in IFS.items():
    buttons = re.findall(r'^\[(\w+)\]\n((?:[^\n]+\n)*?)(?=\n|\Z)', txt, re.M)
    for com, body in buttons:
        if 'buttontype=normal' in body:
            check('[if_button,%s:%s]' % (name, com) in RS2, '%s:%s has an [if_button]' % (name, com))
named = set(re.findall(r'\b(tradingpost(?:_listing|_offer|_side)?):(\w+)', RS2))
for iface, com in sorted(named):
    check(re.search(r'^\[%s\]$' % re.escape(com), IFS[iface], re.M) is not None, '%s:%s exists' % (iface, com))

print('everything hidden is a layer')
# The 377 client honours hide only on a layer (Client.drawInterface): a hidden text or inv is drawn
# anyway. The first build hid the buttons themselves, and they all drew on top of each other.
for iface, com in sorted(set(re.findall(r'if_sethide\((tradingpost(?:_listing|_offer|_side)?):(\w+),', RS2))):
    body = re.search(r'^\[%s\]\n((?:[^\n]+\n)*)' % re.escape(com), IFS[iface] + '\n', re.M)
    check(body is not None and 'type=layer' in body.group(1), '%s:%s is a layer' % (iface, com))
check('if_sethide($box,' in block(RS2, '[proc,tp_row]') and 'if_sethide($row,' not in RS2,
      "an offer row is hidden by its layer, not by the row")

print('the post')
loc = read('scripts/tradingpost/configs/tradingpost.loc')
check('model=trading_post' in loc and 'width=2' in loc and 'forceapproach=south' in loc, 'the loc is the two-tile board, used from its front')
check(os.path.exists(os.path.join(C, 'models/loc/trading_post_8.ob2')), 'its model is in models/loc')
check(re.search(r'^\d+=trading_post_8$', read('pack/model.pack'), re.M) is not None, 'and has a model.pack id')
locid = re.search(r'^(\d+)=trading_post$', read('pack/loc.pack'), re.M)
check(locid is not None, 'the loc has a loc.pack id')
if locid:
    check(re.search(r'^0 12 36: %s 10 3$' % locid.group(1), read('maps/m48_54.jm2'), re.M) is not None,
          "Edgeville's post stands at 12,36 of m48_54, a centrepiece facing east to the bank")
for op, trig in (('op1=Browse', '[oploc1,trading_post]'), ('op2=Sell', '[oploc2,trading_post]'), ('op3=Collect', '[oploc3,trading_post]')):
    check(op in loc and trig in RS2, '%s has its trigger' % op)
check('[oplocu,trading_post]' in RS2, 'an item used on the post searches for it')
check('~tp_login;' in nocomment(read('scripts/login_logout/scripts/login.rs2')), 'login reads out what happened while the player was away')
print('the prices fit the lines they are drawn in')
# Seen in game (Corey, 2026-09-27): "Click again: buy 5 x Armadyl ac" running off the end of its
# button. Every line that can hold a price is measured here at the widest it can really be, in the
# font the window draws it in. A lot's price is each x count, so the biggest "each" that can appear
# beside a total is the one from a lot of two.
sys.path.insert(0, os.path.join(C, 'tools'))
import ifrender

LISTING_COM = {}
for _name, _body in re.findall(r'(?m)^\[(\w+)\]\n((?:(?!\[)[^\n]*\n)*)',
                               read('scripts/tradingpost/interfaces/tradingpost_listing.if')):
    LISTING_COM[_name] = dict(re.findall(r'(?m)^(\w+)=(.*)$', _body))

_MAX = '2,147,483,647'
_HALF = '1,073,741,823'
WIDEST = [
    ('info2', 'Buy now: %s (%s ea)' % (_MAX, _HALF)),
    ('info2', 'Buy now: %s coins' % _MAX),
    ('info0', '%s x Armadyl godsword' % _MAX),
    ('info3', 'Offers waiting: %s' % _MAX),
    ('buynow', 'Click again to confirm'),
    ('buynow', 'Buy now'),
    ('cancel', 'Click again to take it down'),
    ('hint', 'Click Buy now again to pay %s coins for %s.' % (_MAX, _MAX)),
    ('hint', 'Click again to take it down - every offer goes back to its buyer.')
]
_over = []
for _n, _text in WIDEST:
    _com = LISTING_COM.get(_n)
    if _com is None:
        _over.append('%s: no such component' % _n)
        continue
    _w = ifrender.font(_com.get('font', 'p12_full')).width(_text)
    if _w > int(_com['width']):
        _over.append('%s: %dpx of %spx - "%s"' % (_n, _w, _com['width'], _text))
check(not _over, 'every price line fits at its widest%s' % ('' if not _over else ': ' + '; '.join(_over)))

print(fails == 0 and '\nALL PASS' or '\n%d FAILED' % fails)
raise SystemExit(1 if fails else 0)
