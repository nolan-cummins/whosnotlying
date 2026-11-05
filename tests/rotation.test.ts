import { strict as assert } from "node:assert";
import { test } from "node:test";
import * as accounts from "../src/accounts.ts";
import { GameManager, type Role } from "../src/game.ts";
import * as rng from "../src/rng.ts";
import { isolate } from "./helpers.ts";

isolate();

function game(n: number, g = 1, tt = 1, fair = true): GameManager {
  accounts.setSetting("fair_roles", fair);
  const gm = new GameManager();
  for (let i = 0; i < n; i++) gm.addPlayer(`P${i}`);
  gm.setRoleCounts(g, tt);
  return gm;
}

const roles = (gm: GameManager): Record<string, Role> => Object.fromEntries(gm.players.map((p) => [p.id, p.role]));
const count = (gm: GameManager) => {
  const c = { guesser: 0, truth_teller: 0, liar: 0 };
  for (const p of gm.players) c[p.role]++;
  return c;
};

test("fair rotation with ten players", () => {
  rng.seed(7); // the long-wait bound is a tail check; keep it deterministic
  const gm = game(10, 1, 8); // 1 guesser, 8 truth tellers, 1 liar
  const seen = new Map<string, number>();
  const since = new Map<string, number>();
  let last = roles(gm);
  for (let rnd = 0; rnd < 300; rnd++) {
    gm.bookRound();
    gm.assignRoundRoles();
    const now = roles(gm);
    for (const [pid, role] of Object.entries(now)) {
      if (role === "guesser" || role === "liar") {
        assert.notEqual(last[pid], role, `round ${rnd}: ${pid} repeated ${role}`);
        seen.set(`${pid}|${role}`, (seen.get(`${pid}|${role}`) ?? 0) + 1);
        since.set(`${pid}|${role}`, rnd);
      } else if (rnd - (since.get(`${pid}|guesser`) ?? 0) > 30 || rnd - (since.get(`${pid}|liar`) ?? 0) > 30) {
        assert.fail(`${pid} waited over 30 rounds for a role`);
      }
    }
    last = now;
  }
  for (const p of gm.players) {
    for (const role of ["guesser", "liar"]) {
      const n = seen.get(`${p.id}|${role}`) ?? 0;
      assert.ok(n >= 18 && n <= 42, `${p.name} ${role} ${n}`);
    }
  }
});

test("a small game never repeats a scarce role", () => {
  const gm = game(4, 1, 1); // 1 guesser, 1 truth teller, 2 liars
  let last = roles(gm);
  for (let i = 0; i < 100; i++) {
    gm.bookRound();
    gm.assignRoundRoles();
    const now = roles(gm);
    assert.ok(!Object.keys(now).some((p) => now[p] === last[p] && now[p] !== "liar"));
    last = now;
  }
});

test("role modes", () => {
  const gm = game(6, 1, 1, false);
  gm.setRoleMode("one_liar");
  let c = count(gm);
  assert.deepEqual([c.guesser, c.truth_teller, c.liar], [1, 4, 1]);
  assert.ok(gm.checkRoleRequirements()[0]);
  gm.setRoleMode("one_truth");
  c = count(gm);
  assert.deepEqual([c.guesser, c.truth_teller, c.liar], [1, 1, 4]);
  assert.ok(!gm.setRoleMode("bogus"));
});

test("ready up", () => {
  const gm = game(2);
  assert.ok(!gm.toggleReady(gm.players[0]!.id)); // under 3 players: nothing to ready for
  gm.addPlayer("P2");
  const ids = gm.players.map((p) => p.id);
  for (const pid of ids) gm.toggleReady(pid);
  assert.equal(gm.phase, "setup");
  assert.equal(gm.readyIds.size, 0);

  gm.setPhase("reveal", true);
  gm.toggleReady(ids[0]!);
  gm.toggleReady(ids[0]!); // tap again: un-ready
  assert.equal(gm.readyIds.size, 0);
  gm.addPlayer("P3");
  for (const pid of ids) gm.toggleReady(pid);
  assert.equal(gm.roundNumber, 1); // P3 isn't ready yet
  gm.removePlayer(gm.players[gm.players.length - 1]!.id); // kicking the last holdout starts the round
  assert.equal(gm.roundNumber, 2);
  assert.equal(gm.phase, "setup");
});
