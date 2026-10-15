// Scroll boxes and one trail per tier, live: the real engine and the real compiled scripts, with a
// socketless player. Run it through tools/clue_live_battery.py, which copies it into the engine's
// tools/sim (for './harness.js' and the '#/' imports) and takes it out again. Build first.
//
// What the static checks in clue_battery.py cannot see and this does: a second clue of a tier
// arriving as a scroll box, boxes stacking with no cap set, the bank counting toward "do you
// already have one of these", tiers held side by side with their own progress, a box refusing to
// open while its tier has a clue and opening once the trail is done, the spade picking the right
// clue out of three, and the one-time move of the old %trail_status step bits at login.
//
// THE CAP IS OFF, which is what this file had not been told. ^trail_easy_stackcap and its two
// siblings are ^trail_stackcap_none (-1) - "no limit, as the owner asked", which clue_battery.py
// asserts - and ~trail_cluedrop and ~trail_take_refused both test for that sentinel and skip the
// comparison. This file still asserted the old limit of 2 and so reported twelve failures the first
// time anybody ran it: it is not in CI, it needs a built pack and an engine beside content, and the
// cap came off after it was written.
import World from '#/engine/World.js';
import * as H from './harness.js';
import ObjType from '#/cache/config/ObjType.js';
import InvType from '#/cache/config/InvType.js';
import CategoryType from '#/cache/config/CategoryType.js';
import ScriptProvider from '#/engine/script/ScriptProvider.js';
import ScriptRunner from '#/engine/script/ScriptRunner.js';
import ServerTriggerType from '#/engine/script/ServerTriggerType.js';
import { CoordGrid } from '#/engine/CoordGrid.js';
import Player from '#/engine/entity/Player.js';
import ParamType from '#/cache/config/ParamType.js';
import ScriptPointer from '#/engine/script/ScriptPointer.js';

const EASY = 0, MEDIUM = 1, HARD = 2;
const X = 3222, Z = 3218; // Lumbridge courtyard

await H.boot();
H.loginOrder();

let fails = 0;
function check(ok: boolean, what: string) {
    console.log((ok ? '  ok   ' : '  FAIL ') + what);
    if (!ok) fails++;
}

function catOf(id: number) {
    const c = ObjType.get(id).category;
    return c === -1 ? '' : (CategoryType.get(c)?.debugname ?? '');
}
function invItems(p: Player) {
    const inv = p.getInventory(InvType.INV)!;
    const out: { id: number; count: number; name: string; cat: string }[] = [];
    for (let i = 0; i < inv.capacity; i++) {
        const s = inv.get(i);
        if (s) out.push({ id: s.id, count: s.count, name: ObjType.get(s.id).debugname!, cat: catOf(s.id) });
    }
    return out;
}
function groundAt(x: number, z: number) {
    const zone = World.gameMap.getZone(x, z, 0);
    return [...zone.getAllObjsSafe()].filter(o => o.x === x && o.z === z);
}
function clearGround(x: number, z: number) {
    for (const o of groundAt(x, z)) World.removeObj(o, 0);
}
function drop(p: Player, tier: number) {
    // rarity 1: random(1) is always 0, so the roll always succeeds
    run(p, '[proc,trail_cluedrop]', [tier, 1, CoordGrid.packCoord(0, X, Z)]);
}
// What the client's "Take" does once the player is on the tile: the opobj3 trigger with the obj active.
function take(p: Player, objId: number) {
    const o = groundAt(X, Z).find(g => g.type === objId);
    if (!o) throw new Error('nothing to take: ' + ObjType.get(objId).debugname);
    const t = ObjType.get(objId);
    const script = ScriptProvider.getByTrigger(ServerTriggerType.OPOBJ3, t.id, t.category);
    if (!script) throw new Error('no opobj3 for ' + t.debugname);
    const state = ScriptRunner.init(script, p, o);
    ScriptRunner.execute(state);
}
// H.runProc without protected access, which every varp write needs; a real trigger (opheld, login,
// an npc drop's p_finduid) has it.
function run(p: Player, name: string, args: any[] = []): number[] {
    const script = ScriptProvider.getByName(name);
    if (!script) throw new Error('no such script: ' + name);
    const state = ScriptRunner.init(script, p, null, args);
    state.pointerAdd(ScriptPointer.ProtectedActivePlayer);
    ScriptRunner.execute(state);
    return (state as any).intStack.slice(0, (state as any).isp);
}
function count(p: Player, name: string) {
    return H.invCount(p, name);
}

const p = H.makePlayer('clueman', X, Z, 11);
H.tick(1);
H.maxOut(p);
H.clearInv(p);
H.clearLogs();

console.log('1. names');
const tierName = ['easy', 'medium', 'hard'];
let badNames: string[] = [];
for (const [name, id] of ObjType.configNames) {
    const cat = catOf(id);
    const m = /^trail_(clue|casket)_(easy|medium|hard)$/.exec(cat);
    if (!m) continue;
    const want = (m[1] === 'clue' ? 'Clue scroll' : 'Casket') + ` (${m[2]})`;
    if (ObjType.get(id).name !== want) badNames.push(`${name}=${ObjType.get(id).name}`);
}
check(badNames.length === 0, `every clue and casket is named by tier: ${badNames.slice(0, 3).join(', ') || 'all'}`);
for (const t of tierName) {
    const id = ObjType.getId('trail_scrollbox_' + t);
    check(id !== -1 && ObjType.get(id).name === `Scroll box (${t})` && ObjType.get(id).stackable, `Scroll box (${t}) exists and stacks`);
}

console.log('2. the first easy drop is a clue; the second is a scroll box');
clearGround(X, Z);
drop(p, EASY);
let g = groundAt(X, Z);
check(g.length === 1 && catOf(g[0].type) === 'trail_clue_easy', `first drop: ${g.map(o => ObjType.get(o.type).debugname).join(',')}`);
take(p, g[0].type);
check(invItems(p).some(i => i.cat === 'trail_clue_easy'), 'picked up the easy clue');
const easyClue = invItems(p).find(i => i.cat === 'trail_clue_easy')!;
drop(p, EASY);
g = groundAt(X, Z);
check(g.length === 1 && ObjType.get(g[0].type).debugname === 'trail_scrollbox_easy', `second drop: ${g.map(o => ObjType.get(o.type).debugname).join(',')}`);
take(p, g[0].type);
check(count(p, 'trail_scrollbox_easy') === 1, 'picked up the easy scroll box');

console.log('3. no cap is set, so every further clue of the tier is another scroll box');
H.clearLogs();
drop(p, EASY);
g = groundAt(X, Z);
check(g.length === 1 && ObjType.get(g[0].type).debugname === 'trail_scrollbox_easy', `third drop: ${g.map(o => ObjType.get(o.type).debugname).join(',') || 'nothing'}`);
take(p, g[0].type);
check(count(p, 'trail_scrollbox_easy') === 2, `two easy boxes held: ${count(p, 'trail_scrollbox_easy')}`);
check(!H.mesgs.some(m => m.text.includes('sneaking suspicion')), `and nothing stands in for a drop that happened: ${H.mesgs.map(m => m.text).join(' | ')}`);
// nor is a box on the floor refused for a limit that is not set
H.clearLogs();
const ref = run(p, '[proc,trail_take_refused]', [ObjType.getId('trail_scrollbox_easy'), 1]);
check(ref[0] === 0, `another easy box off the floor is allowed: ${H.mesgs.map(m => m.text).join(' | ')}`);

console.log('4. tiers are independent: a medium drop is a medium clue while holding an easy clue and box');
drop(p, MEDIUM);
g = groundAt(X, Z);
check(g.length === 1 && catOf(g[0].type) === 'trail_clue_medium', `medium drop: ${g.map(o => ObjType.get(o.type).debugname).join(',')}`);
take(p, g[0].type);
check(invItems(p).some(i => i.cat === 'trail_clue_medium'), 'picked up the medium clue beside the easy one');
drop(p, MEDIUM);
g = groundAt(X, Z);
check(g.length === 1 && ObjType.get(g[0].type).debugname === 'trail_scrollbox_medium', `second medium drop is a medium box: ${g.map(o => ObjType.get(o.type).debugname).join(',')}`);
clearGround(X, Z);

console.log('5. a box will not open while its tier has a clue');
H.clearLogs();
H.opheld(p, 'trail_scrollbox_easy', 1);
check(count(p, 'trail_scrollbox_easy') === 2, `both boxes still there: ${count(p, 'trail_scrollbox_easy')}`);
check(H.mesgs.some(m => m.text === 'The clue box refuses to open - you already have a clue.'), `and says why: ${H.mesgs.map(m => m.text).join(' | ')}`);

console.log('6. progress is per tier');
H.setVar(p, 'trail_progress', 0);
run(p, '[proc,trail_clue_progress]', [EASY]);
run(p, '[proc,trail_clue_progress]', [EASY]);
run(p, '[proc,trail_clue_progress]', [HARD]);
const pe = run(p, '[proc,get_trail_progress]', [EASY])[0];
const pm = run(p, '[proc,get_trail_progress]', [MEDIUM])[0];
const ph = run(p, '[proc,get_trail_progress]', [HARD])[0];
check(pe === 2 && pm === 0 && ph === 1, `easy=${pe} medium=${pm} hard=${ph} (want 2,0,1)`);
run(p, '[proc,clear_trail_progress]', [EASY]);
check(run(p, '[proc,get_trail_progress]', [EASY])[0] === 0 && run(p, '[proc,get_trail_progress]', [HARD])[0] === 1, 'clearing easy leaves hard alone');

console.log('7. finishing the easy trail, then opening the box for the next clue');
// Force the next step to complete the trail: progress at max.
H.setVar(p, 'trail_progress', 4); // easy bits = 4 = ^trail_easy_maxsteps
H.clearLogs();
run(p, '[proc,progress_clue_easy]', [easyClue.id, 'x']);
check(!invItems(p).some(i => i.cat === 'trail_clue_easy'), 'the easy clue is gone');
check(H.mesgs.some(m => m.text.includes('completed the Treasure Trail')), `trail completed: ${H.mesgs.map(m => m.text).join(' | ')}`);
check(run(p, '[proc,get_trail_progress]', [EASY])[0] === 0, 'easy progress cleared at completion');
p.closeModal();
run(p, '[proc,trail_flush_rewards]');
H.opheld(p, 'trail_scrollbox_easy', 1);
check(count(p, 'trail_scrollbox_easy') === 1, `one box used, one left: ${count(p, 'trail_scrollbox_easy')}`);
check(invItems(p).some(i => i.cat === 'trail_clue_easy'), `a new easy clue: ${invItems(p).filter(i => i.cat.startsWith('trail')).map(i => i.name).join(',')}`);
check(invItems(p).some(i => i.cat === 'trail_clue_medium'), 'the medium clue is untouched');

console.log('8. boxes with no clue: they stack, and a clue off the floor is still allowed');
H.clearInv(p);
drop(p, HARD); // no hard held: a clue
g = groundAt(X, Z);
const hardClue = g[0].type;
clearGround(X, Z);
H.give(p, 'trail_scrollbox_hard', 2);
check(invItems(p).filter(i => i.name === 'trail_scrollbox_hard').length === 1 && count(p, 'trail_scrollbox_hard') === 2, 'two hard boxes in one slot');
drop(p, HARD);
g = groundAt(X, Z);
check(g.length === 1 && ObjType.get(g[0].type).debugname === 'trail_scrollbox_hard', `a third hard drop is another box: ${g.map(o => ObjType.get(o.type).debugname).join(',') || 'nothing'}`);
clearGround(X, Z);
H.clearLogs();
// ~trail_take_refused only turns a clue away when the tier already has a CLUE; boxes held are not
// a clue, and with no cap there is nothing for the count to be over.
check(run(p, '[proc,trail_take_refused]', [hardClue, 1])[0] === 0, `a hard clue off the floor is allowed while two boxes are held: ${H.mesgs.map(m => m.text).join(' | ')}`);
H.opheld(p, 'trail_scrollbox_hard', 1);
check(count(p, 'trail_scrollbox_hard') === 1 && invItems(p).some(i => i.cat === 'trail_clue_hard'), 'opening one gives a hard clue and leaves one box');

console.log('9. the bank counts: a box banked still makes the next drop a box, not a fresh clue');
H.clearInv(p);
const bank = InvType.getId('bank');
p.invAdd(bank, ObjType.getId('trail_scrollbox_medium'), 2);
drop(p, MEDIUM);
g = groundAt(X, Z);
check(g.length === 1 && ObjType.get(g[0].type).debugname === 'trail_scrollbox_medium', `two medium boxes in the bank: the drop is a box: ${g.map(o => ObjType.get(o.type).debugname).join(',') || 'nothing'}`);
clearGround(X, Z);
p.invDel(bank, ObjType.getId('trail_scrollbox_medium'), 2);

console.log('10. legacy progress moves to the held tier at login');
H.clearInv(p);
H.setVar(p, 'trail_progress', 0);
H.give(p, 'trail_clue_hard_riddle001', 1);
H.setVar(p, 'trail_status', (3 | (1 << 4)) | (2 << 5)); // 3 steps, guardian beaten, chart progress 2
run(p, '[proc,trail_login]');
check(run(p, '[proc,get_trail_progress]', [HARD])[0] === 3, 'hard progress is 3');
check(run(p, '[proc,trail_guardian_defeated]', [HARD])[0] === 1, 'hard guardian carried over');
check(H.getVar(p, 'trail_status') === 2 << 5, `chart bits kept, old bits cleared: ${H.getVar(p, 'trail_status')}`);

console.log('11. the spade finds the clue for this spot among several tiers');
H.clearInv(p);
H.give(p, 'spade', 1);
H.give(p, 'trail_clue_easy_simple001', 1); // first in the inventory, and not a dig clue
H.give(p, 'trail_clue_hard_riddle001', 1);
H.give(p, 'trail_clue_medium_map001', 1);
const coordParam = ParamType.getId('trail_coord');
const at = CoordGrid.unpackCoord(ObjType.get(ObjType.getId('trail_clue_medium_map001')).params!.get(coordParam) as number);
p.teleport(at.x, at.z, at.level);
H.tick(2);
H.clearLogs();
H.opheld(p, 'spade', 1);
H.tick(3);
const trailNow = invItems(p).filter(i => i.cat.startsWith('trail')).map(i => i.name);
check(invItems(p).some(i => i.cat === 'trail_casket_medium') && count(p, 'trail_clue_medium_map001') === 0,
    `dug up the medium casket at ${at.x},${at.z}: ${trailNow.join(',')}`);
check(count(p, 'trail_clue_easy_simple001') === 1 && count(p, 'trail_clue_hard_riddle001') === 1, 'the easy and hard clues are untouched');
const casket = invItems(p).find(i => i.cat === 'trail_casket_medium');
check(!!casket && ObjType.get(casket.id).name === 'Casket (medium)', `and it reads ${casket ? ObjType.get(casket.id).name : '-'}`);

console.log();
console.log(fails === 0 ? 'ALL PASS' : `${fails} FAILED`);
process.exit(fails ? 1 : 0);
