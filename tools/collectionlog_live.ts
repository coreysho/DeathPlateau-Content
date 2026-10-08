// Live test of the collection log against the real engine and the real compiled scripts: a
// socketless player, the real world tick (run fast), scripts fired the way the packet handlers fire
// them. Run it through tools/collectionlog_live_battery.py, which puts it inside the engine and takes
// it out again.
//
// What a compile cannot see and this does: a real monster death (the Giant Mole, killed through
// ::~droptest's own path, so its real drop table and the boss kill count both run in npc context)
// writing the log; the "New item" line appearing exactly once per item; a casket's leftovers from
// the one before NOT being counted again; the save format carrying the log across a logout; and the
// window showing the right numbers.
import World from '#/engine/World.js';
import { PlayerLoading } from '#/engine/entity/PlayerLoading.js';
import Packet from '#/io/Packet.js';
import ScriptProvider from '#/engine/script/ScriptProvider.js';
import ScriptRunner from '#/engine/script/ScriptRunner.js';
import ServerTriggerType from '#/engine/script/ServerTriggerType.js';
import ObjType from '#/cache/config/ObjType.js';
import NpcType from '#/cache/config/NpcType.js';
import InvType from '#/cache/config/InvType.js';
import VarPlayerType from '#/cache/config/VarPlayerType.js';
import Component from '#/cache/config/Component.js';
import IfSetText from '#/network/game/server/model/IfSetText.js';
import fs from 'fs';

for (const k of ['loginThread', 'friendThread', 'loggerThread']) (World as any)[k]?.on?.('error', () => {});

const log = (...a: unknown[]) => console.log(`[t${World.currentTick}]`, ...a);
let players: any[] = [];
const waitTicks = (n: number) => new Promise<void>(res => {
    const target = World.currentTick + n;
    const iv = setInterval(() => {
        for (const p of players) { p.lastResponse = World.currentTick; p.lastConnected = World.currentTick; }
        if (World.currentTick >= target) { clearInterval(iv); res(); }
    }, 1);
});
let fails = 0;
const check = (ok: boolean, what: string) => { console.log((ok ? '  ok   ' : '  FAIL ') + what); if (!ok) fails++; };

const SPEC = JSON.parse(fs.readFileSync(`${process.env.BUILD_SRC_DIR}/tools/collectionlogspec.json`, 'utf8'));
const DISTINCT = new Set<string>();
for (const t of SPEC.tabs) for (const e of t.entries) for (const i of e.items) DISTINCT.add(i);
const OWN = (key: string) => 100 + SPEC.own_counters.findIndex((c: any) => c.key === key);

await World.start(false, true);
World.tickRate = 4;

const obj = (n: string) => { const id = ObjType.getId(n); if (id === -1) throw new Error('no obj ' + n); return id; };
const varp = (p: any, n: string) => p.vars[VarPlayerType.getId(n)];
const logCount = (p: any, n: string) => {
    const inv = p.getInventory(InvType.getId('collection_log'))!;
    let c = 0;
    for (let s = 0; s < inv.capacity; s++) { const o = inv.get(s); if (o && o.id === obj(n)) c += o.count; }
    return c;
};
const proc = (p: any, name: string, args: any[] = []) => {
    const script = ScriptProvider.getByName(`[proc,${name}]`);
    if (!script) throw new Error('no proc ' + name);
    p.executeScript(ScriptRunner.init(script, p, null, args), true);
};
const button = (p: any, com: string) => {
    const id = Component.getId(com);
    const script = ScriptProvider.getByTrigger(ServerTriggerType.IF_BUTTON, id, -1);
    if (!script) throw new Error('no if_button for ' + com);
    p.lastCom = id;
    p.executeScript(ScriptRunner.init(script, p), true);
};

function login(name: string, save: Uint8Array) {
    const p: any = PlayerLoading.load(name, new Packet(save), null);
    p.members = true;
    p.staffModLevel = 4; // ::~droptest is a developer debugproc
    p.x = 3222; p.z = 3218; p.level = 0;
    p.msgs = [] as string[];
    p.texts = new Map<number, string>();
    p.messageGame = (m: string) => { p.msgs.push(m); log(name, 'MES', m); };
    const w = p.write.bind(p);
    p.write = (m: any) => {
        if (m instanceof IfSetText) p.texts.set(m.component, m.text);
        return w(m);
    };
    World.newPlayers.add(p);
    players.push(p);
    return p;
}
const newItem = (p: any, name: string) => p.msgs.filter((m: string) => m.startsWith('New item added to your collection log:') && m.endsWith(name)).length;
const text = (p: any, com: string) => p.texts.get(Component.getId(com)) ?? '';

const p = login('collogtest', new Uint8Array(0));
await waitTicks(3);
check(World.getPlayerByUsername('collogtest') !== null, 'player is in the world');

// ---- 1. A real boss kill, three times: the Giant Mole always drops a claw and 1-3 skins, and
// neither is broadcast, so this is the one-line hook in giant_mole.rs2 running in npc context.
const mole = NpcType.getId('mole_giant');
{
    const script = ScriptProvider.getByName('[debugproc,droptest]');
    p.executeScript(ScriptRunner.init(script!, p, null, [mole, 3]), true);
}
await waitTicks(30);
check(varp(p, 'boss_kc_mole') === 3, `three mole kills counted (boss_kc_mole = ${varp(p, 'boss_kc_mole')})`);
check(logCount(p, 'mole_claw') === 3, `mole claw logged three times (${logCount(p, 'mole_claw')})`);
const skins = logCount(p, 'mole_skin');
check(skins >= 3 && skins <= 9, `mole skins logged with their stack sizes (${skins}, 3..9)`);
check(newItem(p, 'Mole claw') === 1, `"New item added" for the claw said exactly once (${newItem(p, 'Mole claw')})`);
check(newItem(p, 'Mole skin') === 1, `"New item added" for the skin said exactly once (${newItem(p, 'Mole skin')})`);
check(p.msgs.filter((m: string) => m.startsWith('Your collection log is open for business')).length === 1,
    'the first-item placeholder reward paid once');
check((varp(p, 'collection_log_rewards') & 1) === 1, 'and marked paid in bit 0');

// ---- 2. The broadcast hook: a rare that ~broadcast_drop announces is logged by it.
proc(p, 'broadcast_drop', [obj('abyssal_whip')]);
proc(p, 'broadcast_drop', [obj('abyssal_whip')]);
check(logCount(p, 'abyssal_whip') === 2 && newItem(p, 'Abyssal whip') === 1, 'broadcast whip: counted twice, announced once');
// ...and a noted drop logs the item
proc(p, 'collection_log_add', [obj('cert_dragon_axe'), 1]);
check(logCount(p, 'dragon_axe') === 1 && logCount(p, 'cert_dragon_axe') === 0, 'a noted dragon axe logs the dragon axe');
// ...and something the log does not list is ignored
const before = p.msgs.length;
proc(p, 'collection_log_add', [obj('coins'), 500]);
check(logCount(p, 'coins') === 0 && p.msgs.length === before, 'coins are not logged and say nothing');

// ---- 3. The Barrows chest pays through ~barrows_reward_add.
proc(p, 'barrows_reward_add', [obj('barrows_dharok_head'), 1]);
check(logCount(p, 'barrows_dharok_head') === 1, 'a Barrows piece paid by the chest is logged');

// ---- 3b. The randoms. Every keepsake a random event pays goes out through
// ~macro_event_give_obj, so that one proc is the hook - the Drill Demon's camo, the Mime's outfit,
// the Gravedigger's zombie outfit and what Thessalia makes from a frog token, all of it, and
// whatever the next event pays as well.
proc(p, 'macro_event_give_obj', [obj('macro_mime_mask'), 1]);
proc(p, 'macro_event_give_obj', [obj('drill_helm'), 1]);
proc(p, 'macro_event_give_obj', [obj('macro_digger_boots'), 1]);
proc(p, 'macro_event_give_obj', [obj('macro_frog_mask'), 1]);
proc(p, 'macro_event_give_obj', [obj('laderhosen_hat'), 1]);
check(logCount(p, 'macro_mime_mask') === 1 && logCount(p, 'drill_helm') === 1 && logCount(p, 'macro_digger_boots') === 1 && logCount(p, 'macro_frog_mask') === 1 && logCount(p, 'laderhosen_hat') === 1,
    'the mime mask, camo helmet, zombie boots, frog mask and lederhosen hat are logged where they are handed over');
check(newItem(p, 'Mime mask') === 1, '"New item added" for the mime mask, once');
// ...and the ordinary things that proc also hands out are not
const beforeKebab = p.msgs.length;
proc(p, 'macro_event_give_obj', [obj('kebab'), 1]);
check(logCount(p, 'kebab') === 0 && p.msgs.length === beforeKebab, "the same proc's kebab is not logged and says nothing");

// ---- 4. A casket with leftovers from the one before. One trimmed platebody is still sitting in
// trail_rewardinv from last time; this casket adds a second and a pair of wizard boots.
const trail = InvType.getId('trail_rewardinv');
const full = p.getInventory(InvType.INV)!;
for (let s = 0; s < full.capacity; s++) p.invSet(InvType.INV, obj('bronze_arrow'), 1, s); // full, so nothing flushes
p.invAdd(trail, obj('black_platebody_trim'), 1);
proc(p, 'collection_log_casket_before');
p.invAdd(trail, obj('black_platebody_trim'), 1);
p.invAdd(trail, obj('boots_wizard'), 1);
proc(p, 'collection_log_casket', [OWN('clue_easy'), 'easy']);
check(logCount(p, 'black_platebody_trim') === 1, `the leftover platebody is not counted again (${logCount(p, 'black_platebody_trim')})`);
check(logCount(p, 'boots_wizard') === 1, 'the new boots are');
check(varp(p, 'collection_log_count_clue_easy') === 1, 'one easy casket counted');
check(p.msgs.includes('You have completed 1 easy Treasure Trails.'), 'and the casket count is said');
for (let s = 0; s < full.capacity; s++) p.invDelSlot(InvType.INV, s);
p.invClear(trail);

// ---- 5. A real casket, end to end: rolls into trail_rewardinv, ~trail_complete, the count.
proc(p, 'trail_clue_hard_reward');
check(varp(p, 'collection_log_count_clue_hard') === 1, 'a real hard casket counts itself');
await waitTicks(2);

// ---- 6. The window. Opened from the quest tab's Character Summary, Bosses tab, then the Giant Mole page.
button(p, 'questtab_summary:collog');
check(p.modalMain === Component.getId('collection_log'), `the Character Summary's button opens the window (modalMain ${p.modalMain})`);
const got = new Set<string>();
const inv = p.getInventory(InvType.getId('collection_log'))!;
for (let s = 0; s < inv.capacity; s++) { const o = inv.get(s); if (o && DISTINCT.has(ObjType.get(o.id).debugname!)) got.add(ObjType.get(o.id).debugname!); }
check(text(p, 'collection_log:title') === `Collection Log - ${got.size}/${DISTINCT.size}`,
    `title "${text(p, 'collection_log:title')}" is ${got.size}/${DISTINCT.size}`);
check(text(p, 'collection_log:r0name').includes('Barrows Chests'), `row 0 is "${text(p, 'collection_log:r0name')}"`);
const moleRow = SPEC.tabs[0].entries.findIndex((e: any) => e.key === 'mole');
button(p, `collection_log:r${moleRow}box`);
check(text(p, 'collection_log:name') === 'Giant Mole', `page name "${text(p, 'collection_log:name')}"`);
check(text(p, 'collection_log:obtained') === 'Obtained: @yel@2/3', `"${text(p, 'collection_log:obtained')}" - claw and skin, no pet`);
check(text(p, 'collection_log:counter0') === 'Giant Mole kills: @whi@3', `"${text(p, 'collection_log:counter0')}"`);
const view = p.getInventory(InvType.getId('collection_log_view'))!;
const cell = (s: number) => { const o = view.get(s); return o ? `${ObjType.get(o.id).debugname}x${o.count}` : 'empty'; };
check(cell(0) === 'bosspet_giant_mole_item' + 'x0', `pet is a placeholder, drawn faded (${cell(0)})`);
check(cell(1) === `mole_skinx${skins}` && cell(2) === 'mole_clawx3', `skin and claw show their counts (${cell(1)}, ${cell(2)})`);
check(cell(3) === 'empty', 'nothing past the page');
button(p, 'collection_log:tab3');
check(text(p, 'collection_log:tab3') === '@whi@Other', 'Other tab is lit');
check(text(p, 'collection_log:name') === SPEC.tabs[3].entries[0].name, `and opens on its first page (${text(p, 'collection_log:name')})`);
check(text(p, 'collection_log:counter0') === '', 'a page with no counter shows none');
const randomRow = SPEC.tabs[3].entries.findIndex((e: any) => e.key === 'random_events');
button(p, `collection_log:r${randomRow}box`);
check(text(p, 'collection_log:name') === 'Random Events', `page name "${text(p, 'collection_log:name')}"`);
check(text(p, 'collection_log:obtained') === 'Obtained: @yel@5/21', `"${text(p, 'collection_log:obtained')}" - the five handed over above`);

// ---- 6b. The Freaky Forester pays the lederhosen a piece at a time, as the Drill Demon pays its
// camo: three right birds, three pieces, and the ordinary gift from the fourth on.
const fp: any = login('foresttest', new Uint8Array(0));
await waitTicks(2);
const invSlots = (q: any) => {
    const i = q.getInventory(InvType.getId('inv'))!;
    let n = 0;
    for (let s2 = 0; s2 < i.capacity; s2++) { if (i.get(s2)) n++; }
    return n;
};
const held = (q: any, name: string) => {
    const i = q.getInventory(InvType.getId('inv'))!;
    let n = 0;
    for (let s2 = 0; s2 < i.capacity; s2++) { const o = i.get(s2); if (o && o.id === obj(name)) n += o.count; }
    return n;
};
proc(fp, 'macro_forester_pay');
check(held(fp, 'laderhosen_hat') === 1, 'the first right bird pays the hat');
proc(fp, 'macro_forester_pay');
proc(fp, 'macro_forester_pay');
check(held(fp, 'laderhosen_top') === 1 && held(fp, 'laderhosen_legs') === 1, 'the second and third pay the top and the shorts');
const slotsBefore = invSlots(fp);
proc(fp, 'macro_forester_pay');
check(held(fp, 'laderhosen_hat') === 1 && held(fp, 'laderhosen_top') === 1 && held(fp, 'laderhosen_legs') === 1,
    'a fourth right bird pays no second piece');
check(invSlots(fp) > slotsBefore, '...and pays the ordinary gift instead');
check(logCount(fp, 'laderhosen_hat') === 1 && logCount(fp, 'laderhosen_top') === 1 && logCount(fp, 'laderhosen_legs') === 1,
    "all three are in that player's collection log");

// ---- 7. Log out and back in: the save carries the log, the counts and the paid reward.
const save = p.save();
const q = login('collogtest', save);
check(logCount(q, 'mole_claw') === 3 && logCount(q, 'abyssal_whip') === 2 && logCount(q, 'boots_wizard') === 1,
    'after a save and load the log is all there');
check(varp(q, 'collection_log_count_clue_easy') === 1 && (varp(q, 'collection_log_rewards') & 1) === 1,
    'and so are the casket count and the paid reward');
proc(q, 'collection_log_add', [obj('mole_claw'), 1]);
check(logCount(q, 'mole_claw') === 4 && newItem(q, 'Mole claw') === 0, 'a claw after reloading counts, and is not "new"');

console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
process.exit(fails ? 1 : 0);
