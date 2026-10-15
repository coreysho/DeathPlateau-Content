#!/usr/bin/env python3
"""Read the PACKED interface archive the client actually loads, and check the rune pouch ops.

WHY THIS AND NOT THE .if FILES. The .if is source; this is the artefact. tools/genpouchruneops.py
rewrites the source and tools/pouch_battery.py checks the source is in step - but neither can say
the packer wrote what the source meant, and the packer is where the interesting limits live
(PackShared.ts reads ops 1..20 and stops, so an op past the cap is dropped in silence). It also
walks EVERY component in the archive rather than the files somebody remembered, which is how
staff_spells.if was found: the autocast panel greys its spells exactly like the spellbook, and a
hand-written file list had missed it.

Decodes the archive the way javaclient/src/main/java/jagex2/config/Component.decode does, field
for field, because the only way to walk to a component's scripts is to walk past everything else.

Needs a build to have run: it reads ../engine/data/pack/client/interface.

    python3 tools/pouchpacked.py                        # default path
    python3 tools/pouchpacked.py <path to interface>
"""

import bz2, io, sys, os

def jagfile(path):
    d=open(path,'rb').read()
    ulen=int.from_bytes(d[0:3],'big'); clen=int.from_bytes(d[3:6],'big')
    body=d[6:6+clen]
    if ulen!=clen: body=bz2.decompress(b'BZh1'+body)
    return body
def hashname(s):
    h=0
    for ch in s.upper(): h=(h*61+ord(ch)-32)&0xFFFFFFFF
    return h
def entries(buf):
    n=int.from_bytes(buf[0:2],'big'); o=2; meta=[]
    for _ in range(n):
        h=int.from_bytes(buf[o:o+4],'big'); o+=4
        ul=int.from_bytes(buf[o:o+3],'big'); o+=3
        cl=int.from_bytes(buf[o:o+3],'big'); o+=3
        meta.append((h,ul,cl))
    out={}
    for h,ul,cl in meta:
        d=buf[o:o+cl]; o+=cl
        if ul!=cl: d=bz2.decompress(b'BZh1'+d)
        out[h]=d
    return out

class P:
    def __init__(s,d): s.d=d; s.p=0
    def g1(s): v=s.d[s.p]; s.p+=1; return v
    def g2(s): v=int.from_bytes(s.d[s.p:s.p+2],'big'); s.p+=2; return v
    def g2b(s): v=s.g2(); return v-65536 if v>32767 else v
    def g4(s): v=int.from_bytes(s.d[s.p:s.p+4],'big'); s.p+=4; return v
    def gjstr(s):
        i=s.d.index(10,s.p); v=s.d[s.p:i].decode('latin-1'); s.p=i+1; return v

def decode(buf, id):
    c={'id':id}
    c['type']=buf.g1(); bt=buf.g1(); buf.g2(); c['w']=buf.g2(); c['h']=buf.g2(); buf.g1()
    ov=buf.g1()
    if ov!=0: buf.g1()
    n=buf.g1(); c['cmp']=[]
    for _ in range(n): c['cmp'].append((buf.g1(), buf.g2()))
    n=buf.g1(); c['scripts']=[]
    for _ in range(n):
        m=buf.g2(); c['scripts'].append([buf.g2() for _ in range(m)])
    t=c['type']
    if t==0:
        buf.g2(); buf.g1(); n=buf.g2()
        for _ in range(n): buf.g2(); buf.g2b(); buf.g2b()
    if t==1: buf.g2(); buf.g1()
    if t==2:
        buf.g1(); buf.g1(); buf.g1(); buf.g1(); buf.g1(); buf.g1()
        for _ in range(20):
            if buf.g1()==1:
                buf.g2b(); buf.g2b(); buf.gjstr()
        c['iop']=[buf.gjstr() for _ in range(5)]
    if t==3: buf.g1()
    if t in (4,1): buf.g1(); buf.g1(); buf.g1()
    if t==4: c['text']=buf.gjstr(); buf.gjstr()
    if t in (1,3,4): buf.g4()
    if t in (3,4): buf.g4(); buf.g4(); buf.g4()
    if t==5:
        buf.gjstr(); buf.gjstr()
    if t==6:
        for _ in range(4):
            if buf.g1()!=0: buf.g1()
        buf.g2(); buf.g2(); buf.g2()
    if t==7:
        buf.g1(); buf.g1(); buf.g1(); buf.g4(); buf.g2b(); buf.g2b(); buf.g1()
        c['iop']=[buf.gjstr() for _ in range(5)]
    if t==8: buf.gjstr()
    if bt==2 or t==2:
        buf.gjstr(); buf.gjstr(); buf.g2()
    if bt in (1,4,5,6): buf.gjstr()
    return c

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# WHERE THE ENGINE IS. In order: an explicit path argument, then $LOSTCITY_ENGINE, then a sibling
# clone under either name it goes by - "engine" in CI and in the cloud, "Engine-TS" on the laptop.
# The environment variable is what tools/poh_mutate.py sets: it copies the CONTENT tree to a
# scratch directory, so a sibling lookup from there finds nothing, and a check that cannot look is
# a check that fails for every mutation and drowns out the one under test.
_roots = ([os.environ['LOSTCITY_ENGINE']] if os.environ.get('LOSTCITY_ENGINE') else []) \
    + [os.path.join(C, '..', e) for e in ('engine', 'Engine-TS')]
DEFAULTS = [os.path.join(r, 'data', 'pack', 'client', 'interface') for r in _roots]
path = sys.argv[1] if len(sys.argv) > 1 else next(
    (d for d in DEFAULTS if os.path.exists(d)), DEFAULTS[0])
if not os.path.exists(path):
    print('no packed interface archive at %s - run the build first' % path)
    sys.exit(2)
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
arc=entries(jagfile(path))
buf=P(arc[hashname('data')])
total=buf.g2()
coms={}
layer=-1
while buf.p < len(buf.d):
    i=buf.g2()
    if i==65535:
        layer=buf.g2(); i=buf.g2()
    coms[i]=decode(buf,i)
print('decoded %d components out of an id space of %d' % (len(coms), total))

names={}
for l in open('pack/interface.pack'):
    if '=' in l:
        a,b=l.strip().split('=',1); names[b]=int(a)
objs={}
for l in open('pack/obj.pack'):
    if '=' in l:
        a,b=l.strip().split('=',1); objs[b]=int(a)

mirror=names['rune_pouch_mirror:runes']
invcom=names['inventory:inv']
print('mirror com', mirror, 'inventory:inv com', invcom)
m=coms[mirror]
print('mirror type', m['type'], 'slots', m['w'], 'x', m['h'])
assert m['type']==2, 'the mirror must be an inv component or the client will not keep it'

ws=coms[names['magic:wind_strike']]
print('wind_strike scripts', ws['scripts'])
# THE STAVES COME OUT OF THE TABLE, not out of a list here. This assertion named three -
# staff_of_air, air_battlestaff, mystic_air_staff - and went red the day the combination staves
# landed, because smoke, mist and dust all supply air and so all six of them belong on the
# button's worn-highlight list too. magic_staff.dbrow's magic_staff_air row is where the game
# decides which staff supplies air; reading it means a tenth staff added to that row cannot make
# this check wrong, only make it check more.
staves=[]
row=None
for l in open('scripts/skill_magic/configs/magic_staff.dbrow'):
    l=l.split('//')[0].strip()
    if l.startswith('['):
        row=l[1:-1]
    elif row=='magic_staff_air' and l.startswith('data=staff,'):
        staves.append(l.split(',',1)[1])
assert len(staves)>=3, ('no staves read out of magic_staff_air', staves)
want=[4,invcom,objs['airrune'], 4,mirror,objs['airrune'],
      4,invcom,objs['smokerune'], 4,mirror,objs['smokerune'],
      4,invcom,objs['mistrune'], 4,mirror,objs['mistrune'],
      4,invcom,objs['dustrune'], 4,mirror,objs['dustrune']]
for s in staves:
    want += [10,names['wornitems:worn'],objs[s]]
want += [0]
assert ws['scripts'][0]==want, (ws['scripts'][0], want)
print('wind_strike script1 is exactly pack+pouch for all four runes, then the %d staves '
      'magic_staff_air lists: OK' % len(staves))

# every spell/label script that counts a rune in the inventory counts it in the mirror too
bad=0; checked=0
for cid,c in coms.items():
    for sc in c.get('scripts',[]):
        i=0; pairs=[]
        while i < len(sc) and sc[i]!=0:
            op=sc[i]
            if op in (4,10):
                if i+2 >= len(sc): break
                pairs.append((op,sc[i+1],sc[i+2])); i+=3
            elif op in (1,2,3,5,6,13,14,20): i+=2
            else: i+=1
        inv=[p for p in pairs if p[0]==4 and p[1]==invcom]
        mir=[p for p in pairs if p[0]==4 and p[1]==mirror]
        if inv:
            checked+=1
            if sorted(p[2] for p in inv) != sorted(p[2] for p in mir):
                bad+=1
runes=set()
for l in open('scripts/storage_items/configs/rune_pouch.enum'):
    if l.startswith('val='):
        runes.add(objs[l.strip().split(',',1)[1]])
byname={v:k for k,v in names.items()}
gaps={}
for cid,c in coms.items():
    for si,sc in enumerate(c.get('scripts',[])):
        i=0; pairs=[]
        while i < len(sc) and sc[i]!=0:
            op=sc[i]
            if op in (4,10):
                if i+2>=len(sc): break
                pairs.append((op,sc[i+1],sc[i+2])); i+=3
            elif op in (1,2,3,5,6,13,14,20): i+=2
            else: i+=1
        inv=[p[2] for p in pairs if p[0]==4 and p[1]==invcom]
        mir=[p[2] for p in pairs if p[0]==4 and p[1]==mirror]
        missing=[o for o in inv if o in runes and o not in mir]
        if missing:
            gaps.setdefault(byname.get(cid, cid), []).append((si+1, missing))
print('%d packed scripts count the inventory' % checked)
print('scripts that count a POUCH RUNE in the pack but not in the pouch: %d' % len(gaps))
for k,v in list(gaps.items())[:20]: print('   ', k, v)
sys.exit(1 if gaps else 0)
