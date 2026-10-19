#!/usr/bin/env python3
"""Every attackable npc's drop table, read out of the drop scripts themselves - for the viewer that
opens when a player examines a monster (scripts/drop_tables/scripts/npc_drops.rs2).

WHY A GENERATOR, AND WHY IT RUNS THE SCRIPTS. A drop table here is not data, it is RuneScript: an
[ai_queue3,<npc>] death trigger that rolls random(128), walks an if/else-if ladder of thresholds,
jumps to a shared @label, calls ~randomherb / ~randomjewel / ~ultrarare_getitem (which call
~megararetable), rolls tertiaries (clues, pets, champion scrolls) and gates members drops on
map_members. A hand-kept copy of all that would be wrong the first time anyone edited a table. So
this reads the same .rs2 the server runs and EXECUTES it - a small RuneScript interpreter over just
the parts a death script uses - with every random() kept symbolic: `random(128)` is a variable whose
possible values are 0..127, each `$roll < 13` test splits the values between the two branches, and
each branch carries the probability of the values it got. A nested table therefore multiplies out
on its own: a rune spear through the rare table is (rare-table slot) x (megararetable slot), exactly
what the server rolls. `calc(random(11) + 2)` as an amount is shown as the range it can produce.

WHAT A RATE MEANS. A row is one (item, amount) and its rate is the expected number of times a kill
drops it: "1/N" is once every N kills on average, "Always" exactly once a kill. For anything a
single roll decides that is simply its chance; where independent rolls can both give it (a
superior rolls its monster's table three times) they add, as the OSRS wiki adds them, and a row
that averages more than once a kill says so ("Always x2", "1.18 per kill"). Counting a drop where
it happens rather than carrying "what has dropped so far" through every branch is also what keeps
this fast: three rolls of a hundred-row table would otherwise be a million combinations.

THE PLAYER IT ASSUMES. A death script also asks about the killer. Those questions get fixed answers
rather than guesses, and they are the ones the viewer is honest about:
  * a members world (map_members is true) - members drops are listed;
  * a killer who carries nothing (inv_total is 0) - no ring of wealth, no clue already in the bag,
    no pet already owned; so clue scrolls and pets are shown at their full rate;
  * the kill is credited (npc_findhero / p_finduid / finduid are true).
Anything ELSE the script asks - a quest varp, a coordinate, a skill level - cannot be answered for
"a player", so the test is taken as false and the npc is REPORTED (the `approx` list below), never
silently guessed. A script that uses something the interpreter does not model at all is reported
as `failed` and its npcs get no table, rather than a wrong one.

WHAT IT WRITES
  scripts/drop_tables/configs/npc_drops.dbrow   one row per distinct table, keyed by every npc that
                                                 shares it (db_find on npc_drops:npc); data=drop is
                                                 what the viewer lists, data=bonus what the game-mode
                                                 drop-rate boost rolls (see BONUS below)
  scripts/drop_tables/configs/npc_drops.enum    the window's list tiers and rows by number
  scripts/drop_tables/configs/npc_drops.inv     the icon column's inv
  scripts/drop_tables/interfaces/npc_drops.if   the window (parchment, list tiers, close button)
and takes interface ids (tools/ifids.py) and the inv id.

    python3 tools/gennpcdrops.py            # write everything, print the report
    python3 tools/gennpcdrops.py --check    # exit 1 if any generated file would change
    python3 tools/gennpcdrops.py --show goblin   # print one npc's table and stop

Re-run it whenever a drop script (or an npc's death_drop / category / Attack op) changes.
"""
import json, os, re, sys, subprocess
from fractions import Fraction

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(C, 'scripts')
SPEC = os.path.join(C, 'tools/npcdropsspec.json')
OUT_DBROW = os.path.join(S, 'drop_tables/configs/npc_drops.dbrow')
OUT_ENUM = os.path.join(S, 'drop_tables/configs/npc_drops.enum')
OUT_INV = os.path.join(S, 'drop_tables/configs/npc_drops.inv')
OUT_IF = os.path.join(S, 'drop_tables/interfaces/npc_drops.if')
INVPACK = os.path.join(C, 'pack/inv.pack')
IFNAME = 'npc_drops'
INVNAME = 'npcdrops'
NPCS_PER_ROW = 200  # see the split in main()


def read(p):
    with open(p, encoding='utf-8', errors='replace', newline='') as f:
        return f.read().replace('\r\n', '\n')


FILES = []


def walk(ext):
    if not FILES:
        for root, dirs, files in os.walk(S):
            dirs.sort()
            FILES.extend(os.path.join(root, f) for f in sorted(files))
    return [p for p in FILES if p.endswith(ext)]


COMMENT = re.compile(r'"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/', re.S)


def strip_comments(src):
    """// and /* */ outside string literals (a block comment keeps its newlines)."""
    def repl(m):
        t = m.group(0)
        if t[0] == '"':
            return t
        return '\n' * t.count('\n')
    return COMMENT.sub(repl, src)


# =========================================================================== configs

def load_constants():
    k = {}
    for p in walk('.constant'):
        for line in strip_comments(read(p)).split('\n'):
            m = re.match(r'^\^(\w+)\s*=\s*(.*?)\s*$', line)
            if m:
                v = m.group(2)
                if re.fullmatch(r'-?\d+', v):
                    v = int(v)
                elif re.fullmatch(r'0x[0-9a-fA-F]+', v):
                    v = int(v, 16)
                elif v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                k[m.group(1)] = v
    return k


def load_configs(ext):
    """{name: {key: value or [values]}} from every file of one config type."""
    out = {}
    for p in walk(ext):
        cur = None
        for line in strip_comments(read(p)).split('\n'):
            line = line.strip()
            m = re.match(r'^\[([^\]]+)\]$', line)
            if m:
                cur = out.setdefault(m.group(1), {'params': {}})
                continue
            if cur is None or '=' not in line:
                continue
            key, val = line.split('=', 1)
            if key == 'param':
                pk, pv = val.split(',', 1)
                cur['params'][pk] = pv
            else:
                cur[key] = val
    return out


# =========================================================================== lexer / parser

TOKEN = re.compile(r'''
    (?P<ws>\s+)
  | (?P<str>"(?:\\.|[^"\\])*")
  | (?P<op><=|>=|[=!<>&|+\-*/(){},;:])
  | (?P<var>[$%^~@][A-Za-z0-9_.]+(?::[A-Za-z0-9_]+)?)
  | (?P<mod>%)
  | (?P<id>[A-Za-z_.][A-Za-z0-9_.]*(?:\+\+?[A-Za-z0-9_.]+)*(?::[A-Za-z0-9_]+)?(?:\+\+?(?![\w$(]))?(?:\*(?=\())?
      | [0-9][A-Za-z0-9_.]*(?::[A-Za-z0-9_]+)?)
''', re.X)
# (the id's tail: obj names like adamant_arrow_p++, and queue*(...) - the strong-queue command)
# A '+' INSIDE a name - potato_chilli+carne, antidote++4 - is part of the name, so the name swallows
# it. Only a name that starts with a letter may: a token that starts with a digit is a number, and
# 5+2 has to stay the arithmetic it looks like.


class ParseError(Exception):
    pass


class Unsupported(Exception):
    pass


def lex(src):
    toks, i = [], 0
    while i < len(src):
        m = TOKEN.match(src, i)
        if not m:
            raise ParseError('cannot read %r' % src[i:i + 20])
        i = m.end()
        kind = m.lastgroup
        if kind == 'ws':
            continue
        t = m.group(kind)
        if kind == 'mod':
            t = '%'
            kind = 'op'
        toks.append((kind, t))
    toks.append(('eof', ''))
    return toks


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self, k=0):
        return self.t[self.i + k]

    def next(self):
        tok = self.t[self.i]; self.i += 1
        return tok

    def accept(self, v):
        if self.t[self.i][1] == v and self.t[self.i][0] in ('op', 'id'):
            self.i += 1
            return True
        return False

    def expect(self, v):
        if not self.accept(v):
            raise ParseError('expected %r, got %r' % (v, self.t[self.i][1]))

    # -- statements
    def block_until_eof(self):
        out = []
        while self.peek()[0] != 'eof':
            out.append(self.stmt())
        return out

    def stmt(self):
        kind, v = self.peek()
        if v == ';' and kind == 'op':
            self.next(); return ('nop',)
        if v == '{' and kind == 'op':
            self.next()
            body = []
            while not (self.peek()[1] == '}' and self.peek()[0] == 'op'):
                if self.peek()[0] == 'eof':
                    raise ParseError('unclosed {')
                body.append(self.stmt())
            self.next()
            return ('block', body)
        if kind == 'id' and v == 'if':
            self.next(); self.expect('(')
            cond = self.expr(); self.expect(')')
            then = self.stmt()
            other = None
            if self.peek() == ('id', 'else'):
                self.next(); other = self.stmt()
            return ('if', cond, then, other)
        if kind == 'id' and v == 'while':
            self.next(); self.expect('(')
            cond = self.expr(); self.expect(')')
            return ('while', cond, self.stmt())
        if kind == 'id' and v.startswith('switch_'):
            self.next(); self.expect('(')
            subj = self.expr(); self.expect(')'); self.expect('{')
            cases = []
            while not self.accept('}'):
                if not self.accept('case'):
                    raise ParseError('expected case, got %r' % self.peek()[1])
                vals = []
                if self.accept('default'):
                    vals = None
                else:
                    vals.append(self.expr())
                    while self.accept(','):
                        vals.append(self.expr())
                self.expect(':')
                body = []
                while not (self.peek() in (('id', 'case'), ('op', '}'))):
                    if self.peek()[0] == 'eof':
                        raise ParseError('unclosed switch')
                    body.append(self.stmt())
                cases.append((vals, body))
            return ('switch', subj, cases)
        if kind == 'id' and v == 'return':
            self.next()
            vals = []
            if self.accept('('):
                if not self.accept(')'):
                    vals.append(self.expr())
                    while self.accept(','):
                        vals.append(self.expr())
                    self.expect(')')
            self.expect(';')
            return ('return', vals)
        if kind == 'id' and v.startswith('def_'):
            self.next()
            name = self.next()[1]
            init = None
            if self.accept('='):
                init = self.expr()
            self.expect(';')
            return ('def', v[4:], name, init)
        if kind == 'var' and v[0] in '$%' and self.peek(1)[1] in ('=', ','):
            targets = [self.next()[1]]
            while self.accept(','):
                targets.append(self.next()[1])
            self.expect('=')
            e = self.expr()
            self.expect(';')
            return ('assign', targets, e)
        if kind == 'var' and v[0] == '@':
            self.next()
            args = self.args() if self.peek()[1] == '(' else []
            self.accept(';')
            return ('jump', v[1:], args)
        e = self.expr()
        self.expect(';')
        return ('expr', e)

    def args(self):
        self.expect('(')
        out = []
        if self.accept(')'):
            return out
        out.append(self.expr())
        while self.accept(','):
            out.append(self.expr())
        self.expect(')')
        return out

    # -- expressions (conditions and calc() share the grammar)
    def expr(self):
        return self.or_()

    def or_(self):
        e = self.and_()
        while self.peek() == ('op', '|'):
            self.next(); e = ('or', e, self.and_())
        return e

    def and_(self):
        e = self.cmp()
        while self.peek() == ('op', '&'):
            self.next(); e = ('and', e, self.cmp())
        return e

    def cmp(self):
        e = self.add()
        if self.peek()[0] == 'op' and self.peek()[1] in ('=', '!', '<', '>', '<=', '>='):
            op = self.next()[1]
            e = ('cmp', op, e, self.add())
        return e

    def add(self):
        e = self.mul()
        while self.peek()[0] == 'op' and self.peek()[1] in '+-' and self.peek()[1]:
            op = self.next()[1]
            e = ('arith', op, e, self.mul())
        return e

    def mul(self):
        e = self.unary()
        while self.peek()[0] == 'op' and self.peek()[1] in ('*', '/', '%'):
            op = self.next()[1]
            e = ('arith', op, e, self.unary())
        return e

    def unary(self):
        if self.peek() == ('op', '-'):
            self.next()
            return ('arith', '-', ('lit', 0), self.unary())
        return self.primary()

    def primary(self):
        kind, v = self.next()
        if kind == 'op' and v == '(':
            e = self.expr(); self.expect(')')
            return e
        if kind == 'str':
            return ('lit', v[1:-1])
        if kind == 'var':
            p, name = v[0], v[1:]
            if p == '$':
                return ('local', name)
            if p == '%':
                return ('varp', name)
            if p == '^':
                return ('const', name)
            if p == '~':
                args = self.args() if self.peek() == ('op', '(') else []
                return ('call', name, args)
            raise ParseError('unexpected %r' % v)
        if kind == 'id':
            if re.fullmatch(r'\d+', v):
                return ('lit', int(v))
            if re.fullmatch(r'0x[0-9a-fA-F]+', v):
                return ('lit', int(v, 16))
            if self.peek() == ('op', '('):
                args = self.args()
                if self.peek() == ('op', '('):
                    self.args()  # queue(name, delay)(args): the queued script's own args
                return ('cmd', v, args)
            return ('name', v)
        raise ParseError('unexpected %r' % v)


HEADER = re.compile(r'^\[(\w+),([^\]]+)\]', re.M)


def load_scripts():
    """{(trigger, name): (path, params, returns, body-src)} - bodies are parsed only when reached."""
    out = {}
    for p in walk('.rs2'):
        src = strip_comments(read(p))
        heads = list(HEADER.finditer(src))
        for k, m in enumerate(heads):
            end = heads[k + 1].start() if k + 1 < len(heads) else len(src)
            rest = src[m.end():end]
            params, returns = [], []
            # [proc,x](type $a, type $b)(rettype, rettype)
            mm = re.match(r'\(([^)]*)\)', rest)
            if mm and (mm.group(1).strip() == '' or '$' in mm.group(1)):
                params = [a.split()[-1][1:] for a in mm.group(1).split(',') if a.strip()]
                rest = rest[mm.end():]
                mm = re.match(r'\(([^)]*)\)', rest)
                if mm:
                    returns = [a.strip() for a in mm.group(1).split(',') if a.strip()]
                    rest = rest[mm.end():]
            out[(m.group(1), m.group(2))] = (p[len(C) + 1:].replace('\\', '/'), params, returns, rest)
    return out


# =========================================================================== the interpreter

class Sym:
    """A value that is `random var` + off; the var's possible values live in the state."""
    __slots__ = ('var', 'off')

    def __init__(self, var, off=0):
        self.var, self.off = var, off

    def key(self):
        return ('sym', self.var, self.off)


class Unknown:
    __slots__ = ('what',)

    def __init__(self, what):
        self.what = what

    def key(self):
        return ('unk', self.what)

    def __repr__(self):
        return self.what


class RareStr(str):
    """An obj name that came out of the shared rare table (RARE_PROCS). Those procs RETURN their
    drop and the monster's own script does the obj_add, so where a drop is made says nothing about
    where it came from - the value itself has to carry it. Equal to the plain name everywhere but
    vkey, so a gem table that can hand back an uncut diamond of its own or one via ~megararetable
    keeps the two apart."""


def rare(v):
    if isinstance(v, tuple):
        return tuple(rare(x) for x in v)
    if isinstance(v, str) and not isinstance(v, RareStr):
        return RareStr(v)
    return v


def vkey(v):
    if isinstance(v, RareStr):
        return ('rare', str(v))
    if isinstance(v, (Sym, Unknown)):
        return v.key()
    if isinstance(v, tuple):
        return tuple(vkey(x) for x in v)
    return v


def dom_size(d):
    return sum(hi - lo + 1 for lo, hi in d)


def dom_cut(d, lo, hi):
    out = []
    for a, b in d:
        a2, b2 = max(a, lo), min(b, hi)
        if a2 <= b2:
            out.append((a2, b2))
    return tuple(out)


def dom_split(d, op, c):
    """(values where `x op c`, the rest)."""
    INF = 1 << 60
    if op == '<':
        t = dom_cut(d, -INF, c - 1)
    elif op == '<=':
        t = dom_cut(d, -INF, c)
    elif op == '>':
        t = dom_cut(d, c + 1, INF)
    elif op == '>=':
        t = dom_cut(d, c, INF)
    elif op in ('=', '!'):
        t = dom_cut(d, c, c)
    else:
        raise Unsupported('op ' + op)
    # the complement of t within d: t is one cut of d, so it is the parts of d either side of it
    if op in ('=', '!'):
        f = dom_cut(d, -INF, c - 1) + dom_cut(d, c + 1, INF)
    elif op in ('<', '<='):
        f = dom_cut(d, c if op == '<' else c + 1, INF)
    else:
        f = dom_cut(d, -INF, c if op == '>' else c - 1)
    if op == '!':
        t, f = f, t
    return t, f


class St:
    __slots__ = ('prob', 'doms', 'locs')

    def __init__(self, prob, doms, locs):
        self.prob, self.doms, self.locs = prob, doms, locs

    def copy(self, **kw):
        s = St(self.prob, self.doms, self.locs)
        for k, v in kw.items():
            setattr(s, k, v)
        return s


def syms_in(v, out):
    if isinstance(v, Sym):
        out.add(v.var)
    elif isinstance(v, tuple):
        for x in v:
            syms_in(x, out)


# Commands with no arguments that a death script reads, and the answer for the assumed killer.
ZERO_ARG = {
    'map_members': 1, 'npc_findhero': 1, 'true': 1, 'false': 0, 'null': None,
}
# Commands whose answer is fixed for the assumed killer (see the docstring).
FIXED = {
    'p_finduid': 1, 'finduid': 1, 'inv_total': 0, 'inv_totalcat': 0, 'inv_freespace': 28,
}
# Statements that do nothing to the loot. Anything not here and not obj_add is ignored as well, but
# these are the ones known to be side effects, so they are not even looked at.


class Npc:
    def __init__(self, name, cfg, params_default):
        self.name, self.cfg = name, cfg
        self.params_default = params_default

    def param(self, p):
        v = self.cfg['params'].get(p, self.params_default.get(p))
        if v is None:
            return None
        if re.fullmatch(r'-?\d+', v):
            return int(v)
        if v in ('null', ''):
            return None
        if v in ('yes', 'true'):
            return 1
        if v in ('no', 'false'):
            return 0
        if v.startswith('^'):
            return CONST.get(v[1:], v)
        return v


class Ctx:
    def __init__(self, npc, scripts):
        self.npc, self.scripts = npc, scripts
        self.approx = set()     # questions answered "false" for want of a player
        self.acc = {}           # (obj, amount, label) -> expected drops per kill
        self.excl = {}          # ...the part of that which comes through the shared rare table
        self.excluding = False  # inside ~ultrarare_getitem / ~megararetable
        self.nextvar = 0
        self.parsed = {}
        self.depth = 0
        self.key = None         # the trigger being run, so npc_queue cannot re-enter it


# [proc,npc_death] is the funnel every death passes through, and what it adds is not the monster's
# table: kill counts, Barrows reward potential, and the game-mode drop-rate boost (extra draws on the
# shared rare table for the killer's mode, gamemodes/scripts/droprate.rs2). That last one is the
# PLAYER'S, not the npc's, so the viewer states it per viewer instead (~npc_drops_open).
SKIP_PROCS = {'npc_death'}
# THE SLAYER FINISHERS, answered true. ~slayer_autofinish asks whether the killer's own unlock
# finished the monster for them - Gargoyle Smasher and its siblings - and the answer decides only
# HOW it dies, not what it drops: with the unlock the death carries straight on into [ai_queue4],
# and without it the player uses the rock hammer, the bag of salt, the ice cooler or the spear and
# the same [ai_queue4] runs from [opnpcu]. Taken as false, which is the default for a question this
# cannot answer, the viewer said the gargoyle, the rockslug, the desert lizard and the two superiors
# drop nothing at all - five tables missing because of a question whose two answers have the same
# drops.
TRUE_PROCS = {'slayer_autofinish'}
# The boss pet roll (npc/scripts/boss_pets.rs2), counted where it is called: see call().
PET_PROCS = {'bosspet_roll'}

# THE SHARED RARE TABLE. What a drop owes to these is counted apart (Ctx.excl), because the game-mode
# drop-rate boost (gamemodes/scripts/droprate.rs2) raises a monster's OWN table and not this one: the
# viewer's rates are the sum, the bonus column is everything else. ~randomjewel (the gem table) is
# the monster's own; only its reach into ~megararetable is excluded.
RARE_PROCS = {'ultrarare_getitem', 'megararetable'}

# Questions the shared tables ask of the killer, and what taking them as false shows.
KNOWN_APPROX = {
    '%legendsquest': "the gem table's mega-rare slot (after Legends' Quest) is left out",
    'coordz()': 'the gem table is rolled above ground: a nature talisman, not a chaos one',
    '%follower_obj': 'a boss pet is shown at its full rate (no pet already following)',
}


def body_of(ctx, key):
    if key in ctx.parsed:
        return ctx.parsed[key]
    if key not in ctx.scripts:
        return None
    path, params, returns, src = ctx.scripts[key]
    try:
        body = Parser(lex(src)).block_until_eof()
    except ParseError as e:
        raise ParseError('%s [%s,%s]: %s' % (path, key[0], key[1], e))
    ctx.parsed[key] = (body, params, returns, path)
    PARSED_CACHE[key] = ctx.parsed[key]
    return ctx.parsed[key]


PARSED_CACHE = {}


def drops_anything(scripts, key, seen=None):
    """Does this script, or anything it calls, put an obj on the ground?"""
    if key in DROPS_MEMO:
        return DROPS_MEMO[key]
    seen = seen or set()
    if key in seen or key not in scripts:
        return False
    seen.add(key)
    src = scripts[key][3]
    hit = 'obj_add' in src
    if not hit:
        for n in set(re.findall(r'~([A-Za-z0-9_.]+)', src)) | set(re.findall(r'gosub\((\w+)\)', src)):
            if drops_anything(scripts, ('proc', n), seen) or drops_anything(scripts, ('label', n), seen):
                hit = True
                break
        if not hit:
            for n in set(re.findall(r'@(\w+)', src)):
                if drops_anything(scripts, ('label', n), seen):
                    hit = True
                    break
    DROPS_MEMO[key] = hit
    return hit


DROPS_MEMO = {}

# Tertiary clue rolls. The proc picks one of the tier's clues out of an enum with a second random();
# which clue it is does not matter to the player reading the table, so the row is the tier.
CLUE_PROCS = {'trail_easycluedrop': ('trail_easy_enum', 'Clue scroll (easy)'),
              'trail_mediumcluedrop': ('trail_medium_enum', 'Clue scroll (medium)'),
              'trail_hardcluedrop': ('trail_hard_enum', 'Clue scroll (hard)')}


def gc(st, pinned):
    live = set(pinned)
    for v in st.locs.values():
        syms_in(v, live)
    if any(k not in live for k in st.doms):
        st = st.copy(doms={k: d for k, d in st.doms.items() if k in live})
    return st


def merge(states):
    """States that no longer differ in anything but probability are one state."""
    if len(states) < 2:
        return states
    acc = {}
    for s in states:
        k = (tuple(sorted((a, vkey(b)) for a, b in s.locs.items())),
             tuple(sorted(s.doms.items())))
        if k in acc:
            acc[k].prob += s.prob
        else:
            acc[k] = s.copy()
    return list(acc.values())


def new_var(ctx, st, lo, hi):
    if hi < lo:
        raise Unsupported('random() of an empty range')
    v = ctx.nextvar
    ctx.nextvar += 1
    doms = dict(st.doms)
    doms[v] = ((lo, hi),)
    return st.copy(doms=doms), Sym(v)


def concretize(ctx, st, v):
    """Split a state into one per value a Sym can take (for arithmetic that is not +/- a constant)."""
    if not isinstance(v, Sym):
        return [(st, v)]
    d = st.doms[v.var]
    n = dom_size(d)
    if n > 4096:
        raise Unsupported('arithmetic on a random() of %d values' % n)
    out = []
    for lo, hi in d:
        for x in range(lo, hi + 1):
            doms = dict(st.doms)
            doms[v.var] = ((x, x),)
            out.append((st.copy(doms=doms, prob=st.prob / n), x + v.off))
    return out


def ev(ctx, e, st, pinned):
    """[(state, value)]"""
    k = e[0]
    if k == 'lit':
        return [(st, e[1])]
    if k == 'const':
        if e[1] not in CONST:
            raise Unsupported('^%s is not a constant' % e[1])
        return [(st, CONST[e[1]])]
    if k == 'local':
        if e[1] not in st.locs:
            raise Unsupported('$%s read before it is set' % e[1])
        return [(st, st.locs[e[1]])]
    if k == 'varp':
        return [(st, Unknown('%' + e[1]))]
    if k == 'name':
        n = e[1]
        if n in ZERO_ARG:
            return [(st, ZERO_ARG[n])]
        if n == 'npc_type':
            return [(st, ctx.npc.name)]
        if n == 'npc_category':
            return [(st, ctx.npc.cfg.get('category'))]
        if n == 'npc_name':
            return [(st, ctx.npc.cfg.get('name', ctx.npc.name))]
        if n in ('npc_coord', 'coord', 'uid', 'npc_uid'):
            return [(st, '<' + n + '>')]
        if n in ('map_clock', 'npc_basestat', 'npc_stat', 'map_production', 'map_playercount'):
            return [(st, Unknown(n))]
        return [(st, n)]  # a symbol: an obj, npc, category, inv or stat name
    if k in ('and', 'or'):
        out = []
        for s, t in cond(ctx, e, st, pinned):
            out.append((s, 1 if t else 0))
        return out
    if k == 'cmp':
        return [(s, 1 if t else 0) for s, t in cond(ctx, e, st, pinned)]
    if k == 'arith':
        out = []
        for s1, a in ev(ctx, e[2], st, pinned):
            for s2, b in ev(ctx, e[3], s1, pinned | symset(a)):
                out.extend(arith(ctx, e[1], a, b, s2))
        return out
    if k == 'cmd':
        return command(ctx, e[1], e[2], st, pinned)
    if k == 'call':
        return call(ctx, e[1], e[2], st, pinned)
    raise Unsupported('expression ' + k)


def symset(v):
    s = set()
    syms_in(v, s)
    return s


def arith(ctx, op, a, b, st):
    if isinstance(a, Unknown) or isinstance(b, Unknown):
        return [(st, Unknown('arithmetic'))]
    if isinstance(a, Sym) and isinstance(b, int) and op in '+-':
        return [(st, Sym(a.var, a.off + (b if op == '+' else -b)))]
    if isinstance(b, Sym) and isinstance(a, int) and op == '+':
        return [(st, Sym(b.var, b.off + a))]
    out = []
    for s1, x in concretize(ctx, st, a):
        for s2, y in concretize(ctx, s1, b):
            if not isinstance(x, int) or not isinstance(y, int):
                raise Unsupported('arithmetic on %r %s %r' % (x, op, y))
            if op == '+':
                r = x + y
            elif op == '-':
                r = x - y
            elif op == '*':
                r = x * y
            elif op == '/':
                r = int(x / y) if y else 0
            elif op == '%':
                r = x % y if y else 0
            else:
                raise Unsupported(op)
            out.append((s2, r))
    return out


def ev_list(ctx, exprs, st, pinned):
    """[(state, [values])], a multi-value proc result spread into the list as the compiler does."""
    res = [(st, [])]
    for e in exprs:
        nxt = []
        for s, vals in res:
            pin = set(pinned)
            for v in vals:
                syms_in(v, pin)
            for s2, v in ev(ctx, e, s, pin):
                nxt.append((s2, vals + (list(v) if isinstance(v, tuple) else [v])))
        res = nxt
    return res


ARITH_CMDS = {'add': '+', 'sub': '-', 'multiply': '*', 'divide': '/', 'modulo': '%'}


def command(ctx, name, args, st, pinned):
    if name == 'calc':
        return ev(ctx, args[0], st, pinned)
    if name in ('random', 'randominc'):
        out = []
        for s, (n,) in ev_list(ctx, args, st, pinned):
            if not isinstance(n, int):
                raise Unsupported('random() of %r' % (n,))
            out.append(new_var(ctx, s, 0, n - 1 if name == 'random' else n))
        return out
    if name in ARITH_CMDS:
        out = []
        for s, (a, b) in ev_list(ctx, args, st, pinned):
            out.extend(arith(ctx, ARITH_CMDS[name], a, b, s))
        return out
    if name in ('min', 'max'):
        out = []
        for s, (a, b) in ev_list(ctx, args, st, pinned):
            for s1, x in concretize(ctx, s, a):
                for s2, y in concretize(ctx, s1, b):
                    out.append((s2, min(x, y) if name == 'min' else max(x, y)))
        return out
    if name in ('nc_vislevel', 'nc_name', 'nc_category'):
        out = []
        for s, (n,) in ev_list(ctx, args, st, pinned):
            cfg = NPCS.get(n) if isinstance(n, str) else None
            if cfg is None:
                raise Unsupported('%s of %r' % (name, n))
            if name == 'nc_vislevel':
                out.append((s, int(cfg.get('vislevel', 0))))
            else:
                out.append((s, cfg.get(name[3:])))
        return out
    if name == 'npc_param':
        if args[0][0] != 'name':
            raise Unsupported('npc_param of an expression')
        return [(st, ctx.npc.param(args[0][1]))]
    if name in FIXED:
        return [(st, FIXED[name])]
    if name == 'compare':
        out = []
        for s, (a, b) in ev_list(ctx, args, st, pinned):
            if isinstance(a, str) and isinstance(b, str):
                out.append((s, 0 if a == b else (1 if a > b else -1)))
            else:
                out.append((s, Unknown('compare')))
        return out
    if name == 'enum':
        out = []
        for s, vals in ev_list(ctx, args, st, pinned):
            _, outtype, enum, k = vals
            if enum not in ENUMS:
                raise Unsupported('enum %s' % enum)
            e = ENUMS[enum]
            for s1, kk in concretize(ctx, s, k):
                v = e['vals'].get(str(kk), e.get('default'))
                out.append((s1, typed(v, outtype)))
        return out
    if name == 'enum_getoutputcount':
        return [(st, len(ENUMS[args[0][1]]['vals']))]
    return [(st, Unknown(name + '()'))]


def typed(v, outtype):
    """A config value as the interpreter holds it."""
    if v is None or v == 'null':
        return 0 if outtype in ('int', 'boolean') else None
    if re.fullmatch(r'-?\d+', v):
        return int(v)
    if v.startswith('^'):
        return CONST.get(v[1:], v)
    if outtype == 'boolean':
        return 1 if v in ('yes', 'true') else 0
    return v


def cond(ctx, e, st, pinned):
    """[(state, bool)] - the state split by the condition."""
    k = e[0]
    if k == 'and':
        out = []
        for s, t in cond(ctx, e[1], st, pinned):
            out.extend(cond(ctx, e[2], s, pinned) if t else [(s, False)])
        return out
    if k == 'or':
        out = []
        for s, t in cond(ctx, e[1], st, pinned):
            out.extend([(s, True)] if t else cond(ctx, e[2], s, pinned))
        return out
    if k != 'cmp':
        out = []
        for s, v in ev(ctx, e, st, pinned):
            out.append((s, truthy(ctx, v)))
        return out
    op = e[1]
    out = []
    for s1, a in ev(ctx, e[2], st, pinned):
        for s2, b in ev(ctx, e[3], s1, pinned | symset(a)):
            out.extend(compare(ctx, op, a, b, s2))
    return out


def truthy(ctx, v):
    if isinstance(v, (Unknown, Sym)):
        raise Unsupported('a bare value as a condition')
    return bool(v)


FLIP = {'<': '>', '>': '<', '<=': '>=', '>=': '<=', '=': '=', '!': '!'}


def compare(ctx, op, a, b, st):
    if isinstance(a, Unknown) or isinstance(b, Unknown):
        u = a if isinstance(a, Unknown) else b
        ctx.approx.add(u.what)
        return [(st, False)]
    if isinstance(b, Sym) and not isinstance(a, Sym):
        a, b, op = b, a, FLIP[op]
    if isinstance(a, Sym):
        if isinstance(b, Sym):
            raise Unsupported('two random() values compared with each other')
        if not isinstance(b, int):
            raise Unsupported('random() compared with %r' % (b,))
        d = st.doms[a.var]
        t, f = dom_split(d, op, b - a.off)
        n = dom_size(d)
        out = []
        for part, truth in ((t, True), (f, False)):
            if part:
                doms = dict(st.doms)
                doms[a.var] = part
                out.append((st.copy(doms=doms, prob=st.prob * Fraction(dom_size(part), n)), truth))
        return out
    if op in ('=', '!'):
        eq = a == b
        return [(st, eq if op == '=' else not eq)]
    if not isinstance(a, int) or not isinstance(b, int):
        if a is None or b is None:
            return [(st, False)]
        raise Unsupported('ordering %r %s %r' % (a, op, b))
    return [(st, {'<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b}[op])]


def default_returns(returns):
    return tuple(None if r not in ('int', 'boolean') else 0 for r in returns)


def call(ctx, name, args, st, pinned):
    """A proc (or a gosub'd label). [(state, value)] where value is a tuple for several returns."""
    if name in CLUE_PROCS:
        enum, label = CLUE_PROCS[name]
        out = []
        for s, vals in ev_list(ctx, args, st, pinned):
            rate = vals[0]
            if not isinstance(rate, int):
                raise Unsupported('clue rate %r' % (rate,))
            if rate > 0:
                emit(ctx, (ENUM_FIRST.get(enum), '1', label), s.prob / rate)
            out.append((s, ()))
        return out
    if name in PET_PROCS:
        # ~bosspet_roll(pet, rate) hands the pet to the killer by a queue (~pet_receive_later) rather
        # than an obj_add, so it is counted here: once in rate kills
        out = []
        for s, vals in ev_list(ctx, args, st, pinned):
            pet, rate = vals[0], vals[1]
            if not isinstance(pet, str) or not isinstance(rate, int):
                raise Unsupported('pet roll %r' % (vals,))
            if rate > 0:
                emit(ctx, (pet, '1', None), s.prob / rate)
            out.append((s, ()))
        return out
    if name in TRUE_PROCS:
        return [(st, 1)]
    if name in SKIP_PROCS:
        return [(st, ())]
    key = ('proc', name) if ('proc', name) in ctx.scripts else ('label', name)
    if key not in ctx.scripts:
        return [(st, Unknown('~' + name))]
    path, params, returns, _ = ctx.scripts[key]
    if not returns and not drops_anything(ctx.scripts, key):
        return [(st, ())]
    out = []
    for s, vals in ev_list(ctx, args, st, pinned):
        if len(vals) != len(params):
            raise Unsupported('~%s given %d args for %d params' % (name, len(vals), len(params)))
        if symset(tuple(vals)):
            was = ctx.excluding
            ctx.excluding = was or name in RARE_PROCS
            try:
                got = run_call(ctx, key, vals, s, pinned)
            finally:
                ctx.excluding = was
            out.extend((s2, rare(rv)) if name in RARE_PROCS else (s2, rv) for s2, rv in got)
            continue
        # A call whose arguments are plain values does the same thing wherever it is made from -
        # ~ultrarare_getitem from a goblin is ~ultrarare_getitem from a dragon - so it is run once
        # from nothing and replayed onto each caller. Only a script that reads the npc itself
        # (npc_param, npc_type...) is run again per npc.
        mk = (key, vkey(tuple(vals)), ctx.npc.name if reads_npc(ctx.scripts, key) else None)
        if mk not in MEMO:
            saved, ctx.approx = ctx.approx, set()
            savedacc, ctx.acc = ctx.acc, {}
            savedexcl, ctx.excl = ctx.excl, {}
            was, ctx.excluding = ctx.excluding, name in RARE_PROCS
            res = []
            try:
                for s2, rv in run_call(ctx, key, vals, St(Fraction(1), {}, {}), set()):
                    live = symset(rv)
                    res.append((s2.prob, rv, {v: s2.doms[v] for v in live}))
                MEMO[mk] = (merge_results(res), ctx.approx, ctx.acc, ctx.excl)
            finally:
                ctx.approx = saved | ctx.approx
                ctx.acc, ctx.excl, ctx.excluding = savedacc, savedexcl, was
        res, approx, emitted, excluded = MEMO[mk]
        ctx.approx |= approx
        # replayed onto this caller: everything counts, and the part the memo counted as the shared
        # rare table's stays excluded - all of it, if this caller is itself inside that table
        for d, p in emitted.items():
            ctx.acc[d] = ctx.acc.get(d, 0) + s.prob * p
            if ctx.excluding:
                ctx.excl[d] = ctx.excl.get(d, 0) + s.prob * p
        if not ctx.excluding:
            for d, p in excluded.items():
                ctx.excl[d] = ctx.excl.get(d, 0) + s.prob * p
        for prob, rv, doms in res:
            nd = dict(s.doms)
            remap = {}
            for v, d in doms.items():
                remap[v] = ctx.nextvar
                nd[ctx.nextvar] = d
                ctx.nextvar += 1
            rv = resym(rv, remap)
            out.append((s.copy(prob=s.prob * prob, doms=nd), rare(rv) if name in RARE_PROCS else rv))
    return out


def merge_results(res):
    acc = {}
    for prob, rv, doms in res:
        k = (vkey(rv), tuple(sorted(doms.items())))
        if k in acc:
            acc[k][0] += prob
        else:
            acc[k] = [prob, rv, doms]
    return [tuple(v) for v in acc.values()]


def resym(v, remap):
    if isinstance(v, Sym):
        return Sym(remap[v.var], v.off)
    if isinstance(v, tuple):
        return tuple(resym(x, remap) for x in v)
    return v


MEMO = {}
READS_NPC = {}
STRINGS = re.compile(r'"(?:\\.|[^"\\])*"')


def reads_npc(scripts, key, seen=None):
    """Does this script (or anything it calls) ask about the npc - so its result differs per npc?"""
    if key in READS_NPC:
        return READS_NPC[key]
    seen = seen if seen is not None else set()
    if key in seen or key not in scripts:
        return False
    seen.add(key)
    src = STRINGS.sub('""', scripts[key][3])
    hit = bool(re.search(r'\b(npc|nc)_\w+', src))
    if not hit:
        for n in set(re.findall(r'~([A-Za-z0-9_.]+)', src)) | set(re.findall(r'gosub\((\w+)\)', src)) | set(re.findall(r'@(\w+)', src)):
            if n in SKIP_PROCS:
                continue
            if reads_npc(scripts, ('proc', n), seen) or reads_npc(scripts, ('label', n), seen):
                hit = True
                break
    READS_NPC[key] = hit
    return hit


def run_call(ctx, key, vals, s, pinned):
    body, params, returns, path = body_of(ctx, key)
    ctx.depth += 1
    if ctx.depth > 40:
        raise Unsupported('recursion')
    out = []
    try:
        caller_locs = s.locs
        pin = set(pinned)
        for v in caller_locs.values():
            syms_in(v, pin)
        s = s.copy(locs=dict(zip(params, vals)))
        for s2, ctl in run_block(ctx, body, [s], pin):
            rv = ctl[1] if ctl and ctl[0] == 'return' else ()
            if returns and not rv:
                rv = default_returns(returns)
            rv = tuple(rv)
            s2 = s2.copy(locs=caller_locs)
            out.append((s2, rv[0] if len(rv) == 1 else rv))
    finally:
        ctx.depth -= 1
    return out


def run_block(ctx, stmts, states, pinned):
    """Run statements over a set of states. [(state, ctl)] where ctl is None or ('return', vals)."""
    done = []
    active = states
    for stmt in stmts:
        nxt = []
        for s in active:
            for s2, ctl in run_stmt(ctx, stmt, s, pinned):
                if ctl:
                    done.append((s2, ctl))
                else:
                    nxt.append(gc(s2, pinned))
        active = merge(nxt)
        if not active:
            break
    return done + [(s, None) for s in active]


def run_stmt(ctx, stmt, st, pinned):
    k = stmt[0]
    if k == 'nop':
        return [(st, None)]
    if k == 'block':
        return run_block(ctx, stmt[1], [st], pinned)
    if k == 'if':
        out = []
        for s, t in cond(ctx, stmt[1], st, pinned):
            if t:
                out.extend(run_stmt(ctx, stmt[2], s, pinned))
            elif stmt[3] is not None:
                out.extend(run_stmt(ctx, stmt[3], s, pinned))
            else:
                out.append((s, None))
        return out
    if k == 'while':
        out, active, n = [], [st], 0
        while active:
            n += 1
            if n > 500:
                raise Unsupported('a while loop that does not end')
            nxt = []
            for s in active:
                for s2, t in cond(ctx, stmt[1], s, pinned):
                    if not t:
                        out.append((s2, None))
                        continue
                    for s3, ctl in run_stmt(ctx, stmt[2], s2, pinned):
                        (out if ctl else nxt).append((s3, ctl) if ctl else s3)
            active = merge(nxt)
        return out
    if k == 'switch':
        out = []
        for s, subj in ev(ctx, stmt[1], st, pinned):
            pin = pinned | symset(subj)
            rest = [s]
            default = None
            for vals, body in stmt[2]:
                if vals is None:
                    default = body
                    continue
                nxt = []
                for r in rest:
                    for r2, t in match_any(ctx, subj, vals, r, pin):
                        if t:
                            out.extend(run_block(ctx, body, [r2], pinned))
                        else:
                            nxt.append(r2)
                rest = nxt
            for r in rest:
                out.extend(run_block(ctx, default, [r], pinned) if default else [(r, None)])
        return out
    if k == 'return':
        out = []
        for s, vals in ev_list(ctx, stmt[1], st, pinned):
            out.append((s, ('return', tuple(vals))))
        return out
    if k == 'def':
        _, typ, name, init = stmt
        name = name[1:]
        if init is None:
            locs = dict(st.locs)
            locs[name] = 0 if typ in ('int', 'boolean') else None
            return [(st.copy(locs=locs), None)]
        return assign(ctx, [('$' + name)], init, st, pinned)
    if k == 'assign':
        return assign(ctx, stmt[1], stmt[2], st, pinned)
    if k == 'jump':
        # @label: the rest of the caller never runs.
        return [(s, ('return', ())) for s, _ in call(ctx, stmt[1], stmt[2], st, pinned)]
    if k == 'expr':
        e = stmt[1]
        if e[0] == 'cmd' and e[1] == 'obj_add':
            return obj_add(ctx, e[2], st, pinned)
        # npc_queue(n, ...) CARRIES THIS NPC'S DEATH ON IN [ai_queue<n>], and five slayer monsters
        # keep their whole drop table there: the gargoyle, the rockslug, the desert lizard and the
        # two superiors all heal to 1 hitpoint in ai_queue3 and wait for the item that finishes
        # them, then drop from ai_queue4. Not following it is why the viewer said those five dropped
        # nothing at all - the one place an [ai_queue3] can hand its own death on to itself.
        if e[0] == 'cmd' and e[1] == 'npc_queue' and e[2] and e[2][0][0] == 'lit':
            nxt = trigger_for(ctx.npc, ctx.scripts, e[2][0][1])
            if nxt is None or nxt == ctx.key:
                return [(st, None)]
            return [(s, None) for s, _ in run_call(ctx, nxt, [], st, pinned)]
        if e[0] == 'cmd' and e[1] == 'gosub':
            if e[2][0][0] != 'name':
                raise Unsupported('gosub of an expression')
            return [(s, None) for s, _ in call(ctx, e[2][0][1], [], st, pinned)]
        if e[0] == 'call':
            return [(s, None) for s, _ in call(ctx, e[1], e[2], st, pinned)]
        return [(st, None)]  # any other command: a side effect, not loot
    raise Unsupported('statement ' + k)


def match_any(ctx, subj, vals, st, pinned):
    """Split a state on `subj` being any of the case values."""
    rest, out = [st], []
    for v in vals:
        nxt = []
        for r in rest:
            for r1, cv in ev(ctx, v, r, pinned):
                for r2, t in compare(ctx, '=', subj, cv, r1):
                    (out.append((r2, True)) if t else nxt.append(r2))
        rest = nxt
    return out + [(r, False) for r in rest]


def assign(ctx, targets, e, st, pinned):
    out = []
    for s, v in ev(ctx, e, st, pinned):
        vals = list(v) if isinstance(v, tuple) else [v]
        if len(targets) == 1 and len(vals) != 1:
            if targets[0].startswith('%'):
                out.append((s, None)); continue
            raise Unsupported('%s given %d values' % (targets[0], len(vals)))
        if len(vals) != len(targets):
            raise Unsupported('%d targets for %d values' % (len(targets), len(vals)))
        locs = dict(s.locs)
        for t, x in zip(targets, vals):
            if t.startswith('$'):
                locs[t[1:]] = x
        out.append((s.copy(locs=locs), None))
    return out


def qty_text(st, v):
    if isinstance(v, int):
        return str(v)
    if isinstance(v, Sym):
        d = st.doms[v.var]
        lo, hi = d[0][0] + v.off, d[-1][1] + v.off
        return str(lo) if lo == hi else '%d-%d' % (lo, hi)
    raise Unsupported('an amount of %r' % (v,))


def obj_add(ctx, args, st, pinned):
    out = []
    for s, vals in ev_list(ctx, args, st, pinned):
        if len(vals) != 4:
            raise Unsupported('obj_add with %d values' % len(vals))
        obj, n = vals[1], vals[2]
        if obj is None or n == 0:
            out.append((s, None)); continue
        if not isinstance(obj, str):
            raise Unsupported('obj_add of %r' % (obj,))
        drop = (str(obj), qty_text(s, n), None)
        emit(ctx, drop, s.prob)
        if isinstance(obj, RareStr) and not ctx.excluding:
            ctx.excl[drop] = ctx.excl.get(drop, 0) + s.prob
        out.append((s, None))
    return out


def emit(ctx, drop, p):
    """A drop is counted where it happens, weighted by the chance of getting there, rather than
    carried along in the state: what a row shows is the expected number of that drop per kill (1/N
    = once every N kills on average), and keeping every combination of what else dropped would
    multiply out - a superior rolls its monster's whole table three times."""
    ctx.acc[drop] = ctx.acc.get(drop, 0) + p
    if ctx.excluding:
        ctx.excl[drop] = ctx.excl.get(drop, 0) + p


# =========================================================================== per npc

def trigger_for(npc, scripts, which=3):
    if ('ai_queue%d' % which, npc.name) in scripts:
        return ('ai_queue%d' % which, npc.name)
    cat = npc.cfg.get('category')
    if cat and ('ai_queue%d' % which, '_' + cat) in scripts:
        return ('ai_queue%d' % which, '_' + cat)
    key = ('ai_queue%d' % which, '_')
    return key if which == 3 or key in scripts else None


def table_for(npc, scripts):
    """([(obj, qty, label, Fraction, Fraction outside the shared rare table)], approx-set)"""
    ctx = Ctx(npc, scripts)
    ctx.parsed = PARSED_CACHE
    key = trigger_for(npc, scripts)
    ctx.key = key
    body, _, _, _ = body_of(ctx, key)
    st = St(Fraction(1), {}, {})
    ends = run_block(ctx, body, [st], set())
    total = sum(s.prob for s, _ in ends)
    if total != 1:
        raise Unsupported('the branches add up to %s, not 1' % total)
    rows = [(o, q, l, p, p - ctx.excl.get((o, q, l), 0)) for (o, q, l), p in ctx.acc.items()]
    return rows, ctx.approx, key


# =========================================================================== formatting

def rate_text(p):
    # A row is the expected number of that drop per kill, so it can pass 1: a drop made by two
    # obj_adds, or one a superior's three rolls of its table make likely more than once.
    if p == 1:
        return 'Always'
    if p > 1:
        return 'Always x%d' % int(p) if p.denominator == 1 else '%s per kill' % ('%.2f' % p).rstrip('0').rstrip('.')
    n = 1 / p
    if n.denominator == 1:
        return '1/%d' % n.numerator
    f = float(n)
    if f < 100:
        s = ('%.2f' % f).rstrip('0').rstrip('.')
        return '1/' + s
    return '1/%d' % round(f)


def qty_sort(q):
    m = re.match(r'(\d+)', q)
    return int(m.group(1)) if m else 0


def obj_name(o):
    cfg = OBJS.get(o)
    if cfg is None:
        return o
    if 'name' in cfg:
        return cfg['name']
    if 'certlink' in cfg:
        return obj_name(cfg['certlink'])
    return o


# Drops whose obj depends on the killer in a way one row can only name. ~rcu_pouch_drop_roll
# (skill_runecraft) gives the smallest essence pouch the killer does not own yet; with nothing owned
# that is the small one, which would read as "this monster drops small pouches".
DISPLAY_NAMES = {'rcu_pouch_small': 'Essence pouch (next)'}


def display(rows):
    out = []
    for o, q, l, p, pb in rows:
        name = l or DISPLAY_NAMES.get(o) or obj_name(o)
        base = OBJS[o]['certlink'] if l is None and o in OBJS and 'certlink' in OBJS[o] else o
        # Every unidentified herb in 377 is called "Herb" and they share a model, so eleven rows of
        # "Herb" would say nothing; which herb it is comes from the obj's own name.
        if name == 'Herb' and base.startswith('unidentified_'):
            name = 'Herb (%s)' % base[len('unidentified_'):].replace('_', ' ').capitalize()
        if base != o:
            name = name + ' (noted)'
        name = name.replace(',', '')  # a dbrow value cannot hold a comma
        out.append((o, name, q, rate_text(p), p, pb))
    out.sort(key=lambda r: (-r[4], r[1].lower(), qty_sort(r[2])))
    return out


# =========================================================================== outputs

# The list comes in a few fixed lengths, because a 377 scroll layer cannot change its length at
# runtime: a table of 3 rows in a 120-row list would scroll through 117 blank rows. Each tier is its
# own layer with its own rows, and ~npc_drops_open shows the smallest that holds the table. 7 rows
# fill the parchment with no scrollbar at all. The tiers are fixed rather than fitted to the data so
# that a re-run after a drop table changes does not renumber the interface.
TIERS = (7, 15, 30, 60, 120)
ROW_H = 32
LIST_X, LIST_Y, LIST_W, LIST_H = 48, 70, 342, 228
# The amount column is the one that fills up ("20005-29995" is 84px in p12), so it takes the few
# pixels the name and rarity columns do not need: their longest are 152 and 65.
NAME_X, QTY_X, QTY_W, RATE_X, RATE_W = 38, 192, 84, 276, 66
TITLE_Y, SUB_Y, HDR_Y = 26, 42, 56
COL_HDR = '0x5F3F1F'


def build_if():
    L = ['// DROP TABLE VIEWER - what an attackable npc drops, opened by examining it',
         '// (scripts/drop_tables/scripts/npc_drops.rs2). GENERATED by tools/gennpcdrops.py - do not',
         '// hand-edit; change the generator and re-run it.',
         '//',
         "// The skill guide's parchment ([backdrop] is the same com_i161 model skill_guide.if uses as its",
         '// paper - see there for why a model is the paper, and why nothing may be wider than ~370) and',
         '// its stone frame with Close Window. Below the title, one list per length in TIERS: a 377 scroll',
         '// layer cannot change length at runtime, so a short table gets a short list rather than a long',
         '// scroll through empty rows. A row is an inv slot for the icon (32px, the row pitch) and three',
         '// text columns: name, amount, rarity. The scrollbar is drawn just outside a layer\'s right edge,',
         '// at x=390, still on the paper.',
         '',
         '[backdrop]', 'type=model', 'x=200', 'y=90', 'width=55', 'height=81', 'model=com_i161',
         'zoom=643', 'xan=512', '',
         '[title]', 'type=text', 'x=%d' % LIST_X, 'y=%d' % TITLE_Y, 'width=%d' % LIST_W, 'height=17',
         'font=q8_full', 'text=Drop table', '',
         '[subtitle]', 'type=text', 'x=%d' % LIST_X, 'y=%d' % SUB_Y, 'width=%d' % LIST_W, 'height=13',
         'font=p11_full', 'colour=%s' % COL_HDR, '']
    for hdr, x, w, c, text in (('hdr_item', LIST_X + NAME_X, QTY_X - NAME_X, 'no', 'Item'),
                               ('hdr_qty', LIST_X + QTY_X, QTY_W, 'yes', 'Quantity'),
                               ('hdr_rate', LIST_X + RATE_X, RATE_W, 'yes', 'Rarity')):
        L += ['[%s]' % hdr, 'type=text', 'x=%d' % x, 'y=%d' % HDR_Y, 'width=%d' % w, 'height=13',
              'font=p11_full', 'center=%s' % c, 'colour=%s' % COL_HDR, 'text=%s' % text, '']
    for t, n in enumerate(TIERS, 1):
        L += ['[list%d]' % t, 'type=layer', 'x=%d' % LIST_X, 'y=%d' % LIST_Y, 'width=%d' % LIST_W,
              'height=%d' % LIST_H]
        if n * ROW_H > LIST_H:
            L.append('scroll=%d' % (n * ROW_H))
        L += ['hide=yes', '']
        L += ['[icons%d]' % t, 'layer=list%d' % t, 'type=inv', 'x=0', 'y=0', 'width=1', 'height=%d' % n, '']
        for r in range(1, n + 1):
            y = (r - 1) * ROW_H + 10
            L += ['[name%d_%d]' % (t, r), 'layer=list%d' % t, 'type=text', 'x=%d' % NAME_X, 'y=%d' % y,
                  'width=%d' % (QTY_X - NAME_X), 'height=14', 'font=p12_full', '']
            L += ['[qty%d_%d]' % (t, r), 'layer=list%d' % t, 'type=text', 'x=%d' % QTY_X, 'y=%d' % y,
                  'width=%d' % QTY_W, 'height=14', 'center=yes', 'font=p12_full', '']
            L += ['[rate%d_%d]' % (t, r), 'layer=list%d' % t, 'type=text', 'x=%d' % RATE_X, 'y=%d' % y,
                  'width=%d' % RATE_W, 'height=14', 'center=yes', 'font=p12_full', '']
    # the stone frame and its Close Window, as skill_guide.if has them, and under Close Window the
    # monster browser's way back (drop_tables/scripts/npc_browser.rs2): a layer, hidden unless the
    # table was opened from the browser, because only a layer can be hidden
    L += FRAME
    return '\n'.join(L).rstrip('\n') + '\n'


FRAME = """[frame]
type=layer
x=423
y=18
width=88
height=180

[frame_tile]
layer=frame
type=graphic
x=0
y=0
width=88
height=60
graphic=tradebacking,0

[frame_tl]
layer=frame
type=graphic
x=0
y=0
width=25
height=30
graphic=steelborder,0

[frame_l]
layer=frame
type=graphic
x=-15
y=18
width=36
height=36
graphic=miscgraphics,2

[frame_t1]
layer=frame
type=graphic
x=25
y=-15
width=36
height=36
graphic=steelborder2,0

[frame_t2]
layer=frame
type=graphic
x=38
y=-15
width=36
height=36
graphic=steelborder2,0

[frame_tr]
layer=frame
type=graphic
x=63
y=0
width=25
height=30
graphic=steelborder,1

[frame_r]
layer=frame
type=graphic
x=67
y=20
width=36
height=36
graphic=steelborder2,1

[frame_b1]
layer=frame
type=graphic
x=25
y=45
width=36
height=36
graphic=miscgraphics,3

[frame_bl]
layer=frame
type=graphic
x=0
y=36
width=25
height=30
graphic=steelborder,2

[frame_b2]
layer=frame
type=graphic
x=35
y=45
width=36
height=36
graphic=miscgraphics,3

[frame_br]
layer=frame
type=graphic
x=63
y=36
width=25
height=30
graphic=steelborder,3

[close]
type=text
x=434
y=28
buttontype=close
width=68
height=11
font=p11_full
shadowed=yes
text=Close Window
colour=0xC00000
overcolour=0xFFFFFF

[back]
type=layer
x=434
y=44
width=68
height=11
hide=yes

[back_button]
layer=back
type=text
x=0
y=0
buttontype=normal
width=68
height=11
font=p11_full
shadowed=yes
text=Back to list
colour=0xFF981F
overcolour=0xFFFFFF
option=Back to the monster list
""".split('\n')


def build_enum():
    L = ['// npc_drops.if by number, for ~npc_drops_open (scripts/drop_tables/scripts/npc_drops.rs2).',
         '// GENERATED by tools/gennpcdrops.py - do not hand-edit.',
         '',
         '// tier -> how many rows its list holds; the tiers are smallest first',
         '[npc_drops_tier_size]', 'inputtype=int', 'outputtype=int']
    L += ['val=%d,%d' % (t, n) for t, n in enumerate(TIERS, 1)]
    # default=null on every component enum here: an enum with no default returns 0 on a miss and
    # NOT null (rs2check rule 17), and component 0 is a real component. These keys are generated
    # from the same TIERS table that bounds the loops reading them, so they cannot miss - but that
    # is a property of today's generator rather than a guarantee, and the default costs one line.
    L += ['', '// tier -> its list layer', '[npc_drops_tier_list]', 'inputtype=int', 'outputtype=component',
          'default=null']
    L += ['val=%d,%s:list%d' % (t, IFNAME, t) for t in range(1, len(TIERS) + 1)]
    L += ['', '// tier -> its icon column', '[npc_drops_tier_icons]', 'inputtype=int', 'outputtype=component',
          'default=null']
    L += ['val=%d,%s:icons%d' % (t, IFNAME, t) for t in range(1, len(TIERS) + 1)]
    for col, what in (('name', 'item name'), ('qty', 'amount'), ('rate', 'rarity')):
        L += ['', '// tier * 1000 + row (from 0) -> that row\'s %s text' % what,
              '[npc_drops_%s]' % col, 'inputtype=int', 'outputtype=component', 'default=null']
        for t, n in enumerate(TIERS, 1):
            L += ['val=%d,%s:%s%d_%d' % (t * 1000 + r - 1, IFNAME, col, t, r) for r in range(1, n + 1)]
    return '\n'.join(L) + '\n'


def build_inv():
    return ('// The icon column of the drop table viewer (npc_drops.if), filled by ~npc_drops_open and\n'
            '// sent with inv_transmit. As long as the longest list tier. GENERATED by tools/gennpcdrops.py.\n'
            '[%s]\nsize=%d\nprotect=no\n' % (INVNAME, TIERS[-1]))


# THE DROP-RATE BOOST'S DATA (gamemodes/scripts/droprate.rs2). A boosted kill rolls each of these on
# its own, at the row's chance times the killer's boost, so every drop on the monster's own table
# comes that much more often - the viewer's rates times 1.25 on realism, say - and the shared rare
# table not at all. The chance is the row's own, less what it owes to that table; a row the monster
# always drops (bones) has nothing to boost, nor does one whose obj is chosen per killer.
#   kind 0  the obj, least..most of it
#   kind 1  a pet: ~bosspet_roll's rules (not if one is owned already), at a chance of 1
#   kind 2+ a clue scroll, easy/medium/hard: the tier's own drop proc at a chance of 1, which picks
#           the clue and keeps the one-clue-at-a-time rule
BONUS_UNITS = 10000000
CLUE_KINDS = {'Clue scroll (easy)': 2, 'Clue scroll (medium)': 3, 'Clue scroll (hard)': 4}


def bonus_of(o, name, q, p, pb):
    """(obj, least, most, chance in BONUS_UNITS, kind) or None."""
    if p >= 1 or pb <= 0 or o in DISPLAY_NAMES:
        return None
    m = re.fullmatch(r'(\d+)(?:-(\d+))?', q)
    if not m:
        return None
    least = int(m.group(1))
    most = int(m.group(2) or m.group(1))
    kind = CLUE_KINDS.get(name, 1 if o.startswith('bosspet_') else 0)
    return (o, least, most, max(1, round(pb * BONUS_UNITS)), kind)


def build_dbrow(groups):
    L = ['// Every attackable npc\'s drops, as its death script rolls them. GENERATED by',
         '// tools/gennpcdrops.py from the [ai_queue3] scripts - do not hand-edit; re-run it when a drop',
         '// table changes. One row per distinct table; data=npc lists every npc that shares it.',
         '// data=drop is obj, name as shown, amount, rarity ("Always" or "1/N", N = 1 / the chance).',
         '// data=bonus is obj, least, most, chance in ten million, kind - for the drop-rate boost.',
         '']
    for rowname, (npcs, rows, key, approx) in groups:
        L.append('[%s]' % rowname)
        L.append('table=npc_drops')
        L.append('// %s' % ('[%s,%s]' % key))
        if approx:
            L.append('// assumed false: %s' % ', '.join(sorted(approx)))
        for n in npcs:
            L.append('data=npc,%s' % n)
        for o, name, q, r, p, pb in rows:
            L.append('data=drop,%s,%s,%s,%s' % (o, name, q, r))
        for o, name, q, r, p, pb in rows:
            b = bonus_of(o, name, q, p, pb)
            if b:
                L.append('data=bonus,%s,%d,%d,%d,%d' % b)
        L.append('')
    return '\n'.join(L).rstrip('\n') + '\n'


def write(path, text, check, changed):
    old = read(path) if os.path.exists(path) else None
    if old == text:
        return
    changed.append(os.path.relpath(path, C))
    if not check:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)


def ensure_inv(check, changed):
    raw = read(INVPACK)
    if re.search(r'^\d+=%s$' % INVNAME, raw, re.M):
        return
    ids = [int(m) for m in re.findall(r'^(\d+)=', raw, re.M)]
    changed.append('pack/inv.pack')
    if not check:
        with open(INVPACK, 'w', encoding='utf-8', newline='\n') as f:
            f.write(raw.rstrip('\n') + '\n%d=%s\n' % (max(ids) + 1, INVNAME))


def main():
    global CONST, OBJS, ENUM_FIRST, ENUMS, NPCS
    check = '--check' in sys.argv
    show = sys.argv[sys.argv.index('--show') + 1] if '--show' in sys.argv else None
    CONST = load_constants()
    OBJS = load_configs('.obj')
    npcs = NPCS = load_configs('.npc')
    params = {k: v.get('default') for k, v in load_configs('.param').items()}
    ENUM_FIRST, ENUMS = {}, {}
    for p in walk('.enum'):
        cur = None
        for line in strip_comments(read(p)).split('\n'):
            line = line.strip()
            m = re.match(r'^\[([^\]]+)\]$', line)
            if m:
                cur = ENUMS.setdefault(m.group(1), {'vals': {}})
                name = m.group(1)
                continue
            if cur is None or '=' not in line:
                continue
            k, v = line.split('=', 1)
            if k == 'val' and ',' in v:
                a, b = v.split(',', 1)
                cur['vals'][a] = b
                ENUM_FIRST.setdefault(name, b)
            else:
                cur[k] = v
    scripts = load_scripts()

    attackable = sorted(n for n, c in npcs.items() if any(k.startswith('op') and v == 'Attack' for k, v in c.items()))
    if show:
        attackable = [show]
    tables, failed, approx_by = {}, {}, {}
    for name in attackable:
        npc = Npc(name, npcs[name], params)
        key = trigger_for(npc, scripts)
        try:
            rows, approx, key = table_for(npc, scripts)
        except (Unsupported, ParseError, RecursionError) as e:
            failed.setdefault((key, str(e)), []).append(name)
            continue
        disp = display(rows)
        if not disp:
            continue
        tables[name] = (disp, key, approx)
        if approx:
            approx_by.setdefault(key, set()).update(approx)
    # THE TABLES THE INTERPRETER CANNOT REACH, out of tools/npcdropsspec.json with the reason for
    # each one written beside it. A drop handed to the killer through queue() leaves no obj_add in
    # the trigger to see, and an obj chosen by a varp is not something this can answer - the hell rat
    # behemoth's spice is both at once. The guard matters more than the rows: if an npc named in the
    # spec turns out to be derivable, that is an error rather than a hand-written table quietly
    # shadowing a real one.
    for hand_name, d in sorted(json.load(open(SPEC, encoding='utf-8'))['hand'].items()):
        if hand_name in tables:
            sys.exit('gennpcdrops: %s is derivable from the scripts now - take it out of %s'
                     % (hand_name, os.path.relpath(SPEC, C)))
        if hand_name not in npcs:
            sys.exit('gennpcdrops: %s in %s is not an npc' % (hand_name, os.path.relpath(SPEC, C)))
        raw = []
        for row in d['drops']:
            rate = row['rate']
            p = Fraction(1) if rate == 'Always' else Fraction(1, int(rate.split('/')[1]))
            raw.append((row['obj'], row['qty'], row.get('name'), p, p))
        tables[hand_name] = (display(raw), (d.get('trigger', 'ai_queue3'), hand_name), set())

    if show:
        if show in tables:
            disp, key, approx = tables[show]
            print('%s  <- [%s,%s]%s' % (show, key[0], key[1], ('   assumed false: ' + ', '.join(sorted(approx))) if approx else ''))
            for o, name, q, r, p, pb in disp:
                print('  %-32s %-14s %-10s %s' % (name, q, r, o))
        else:
            for (key, why), ns in failed.items():
                print('FAILED [%s,%s]: %s' % (key[0], key[1], why))
            if not failed:
                print('%s drops nothing' % show)
        return

    # one dbrow per distinct table
    bytable = {}
    for name, (disp, key, approx) in tables.items():
        sig = tuple((o, n, q, r, bonus_of(o, n, q, p, pb)) for o, n, q, r, p, pb in disp)
        bytable.setdefault(sig, []).append(name)
    groups = []
    used = set()
    for sig, ns in sorted(bytable.items(), key=lambda kv: sorted(kv[1])[0]):
        ns = sorted(ns)
        disp, key, approx = tables[ns[0]]
        # The packer writes a LIST column's length in ONE byte (DbRowConfig.ts, server.p1), so a
        # column of 256+ values wraps and every row after it reads as garbage. The plain "bones and
        # nothing else" table is shared by 400-odd npcs, so a big group is split into several rows.
        for k in range(0, len(ns), NPCS_PER_ROW):
            part = ns[k:k + NPCS_PER_ROW]
            rowname = 'npc_drops_' + part[0]
            assert rowname not in used
            used.add(rowname)
            groups.append((rowname, (part, disp, key, set().union(*(tables[n][2] for n in part)))))
    maxrows = max(len(g[1][1]) for g in groups)
    for rowname, (ns, disp, key, approx) in groups:
        if len(disp) > TIERS[-1]:
            # the least likely rows go; say so rather than let the build or the viewer find out
            print('TRUNCATED %s: %d rows, the longest list holds %d' % (rowname, len(disp), TIERS[-1]))
            del disp[TIERS[-1]:]

    changed = []
    write(OUT_DBROW, build_dbrow(groups), check, changed)
    write(OUT_ENUM, build_enum(), check, changed)
    write(OUT_INV, build_inv(), check, changed)
    write(OUT_IF, build_if(), check, changed)
    ensure_inv(check, changed)
    if not check and any(c.endswith('.if') for c in changed):
        subprocess.check_call([sys.executable, os.path.join(C, 'tools', 'ifids.py'), IFNAME], cwd=C)
    # the monster browser lists what this wrote, so it follows every change to the tables
    if not check:
        subprocess.check_call([sys.executable, os.path.join(C, 'tools', 'gennpcbrowser.py')], cwd=C)

    # the report
    print('gennpcdrops: %d attackable npcs, %d with a table, %d distinct tables, longest %d rows'
          % (len(attackable), len(tables), len(groups), maxrows))
    if failed:
        print('\nFAILED - these npcs get no table (the script uses something this does not model):')
        for (key, why), ns in sorted(failed.items()):
            print('  [%s,%s]  %s\n      %d npc(s): %s' % (key[0], key[1], why, len(ns), ', '.join(ns[:8]) + (' ...' if len(ns) > 8 else '')))
    if approx_by:
        print('\nAPPROXIMATE - a test about the killer taken as false (the table is listed without it).')
        print('Shared by many tables, and what "false" means there:')
        for k, why in KNOWN_APPROX.items():
            n = sum(1 for a in approx_by.values() if k in a)
            if n:
                print('  %-16s %s (%d scripts)' % (k, why, n))
        print('The rest, per script:')
        for key, a in sorted(approx_by.items()):
            rest = sorted(set(a) - set(KNOWN_APPROX))
            if rest:
                print('  [%s,%s]  %s' % (key[0], key[1], ', '.join(rest)))
    if check:
        if changed:
            print('\nout of date: ' + ', '.join(changed))
            sys.exit(1)
        print('\nup to date')
    elif changed:
        print('\nwrote: ' + ', '.join(changed))


if __name__ == '__main__':
    main()
