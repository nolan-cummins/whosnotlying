/** Unit tests for the game engine. */
import { strict as assert } from "node:assert";
import { test } from "node:test";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import * as accounts from "../src/accounts.ts";
import { GameManager, type Player } from "../src/game.ts";
import { library } from "../src/packs.ts";
import { isolate, sandbox, tok } from "./helpers.ts";

isolate();

const lib = () => library();
const byId = (gm: GameManager, id: string | null): Player => gm.players.find((p) => p.id === id)!;
const liarsOf = (gm: GameManager) => gm.players.filter((p) => p.id !== gm.guesserId && p.id !== gm.truthTellerId);
const me = (gm: GameManager, id: string) => gm.getState({ isAdmin: false, playerId: id, token: tok(gm, id) }).my_info!;

test("expanded topics: one truth and one lie per topic, all unique", () => {
  const topics = lib();
  const N = topics.length;
  assert.ok(N >= 400);
  const trues = topics.map((t) => t.true_statement);
  const falses = topics.flatMap((t) => t.false_statements);
  assert.equal(trues.length, N);
  assert.equal(falses.length, N);
  assert.equal(new Set(trues).size, N);
  assert.equal(new Set(falses).size, N);
  assert.ok(trues.every((s) => !falses.includes(s)));
  assert.equal(new Set(topics.map((t) => t.id)).size, N, "Duplicate topic IDs found");
  assert.equal(new Set(topics.map((t) => t.topic)).size, N, "Duplicate topics found");
  for (const t of topics) {
    assert.ok(t.id && typeof t.id === "string");
    assert.ok(t.topic && typeof t.topic === "string");
    assert.ok(t.category && typeof t.category === "string");
    assert.ok(t.true_statement && typeof t.true_statement === "string");
    assert.ok(t.true_description && typeof t.true_description === "string");
    assert.ok(Array.isArray(t.false_statements) && t.false_statements.length >= 1);
    for (const fs of t.false_statements) assert.ok(typeof fs === "string" && fs.trim().length > 0);
  }
});

test("empty lobby on boot without samples", () => {
  const gm = new GameManager({ seedSamples: false });
  assert.equal(gm.players.length, 0);
  assert.equal(gm.guesserId, null);
  assert.equal(gm.truthTellerId, null);
  assert.equal(gm.votingGuesserId, null);
  assert.equal(gm.phase, "lobby");
});

test("liars hold statements from the false statements pool", () => {
  const gm = new GameManager({ seedSamples: true });
  const liars = gm.players.filter((p) => p.role === "liar");
  assert.ok(liars.length >= 1);
  for (const liar of liars) {
    assert.ok(liar.topic);
    const t = lib().find((x) => x.topic === liar.topic);
    assert.ok(t);
    assert.ok(t.false_statements.includes(liar.statement as string));
  }
});

test("initial state: guesser and truth teller", () => {
  const gm = new GameManager({ seedSamples: true });
  assert.equal(gm.phase, "lobby");
  assert.ok(gm.players.length >= 3);
  assert.ok(gm.guesserId && gm.truthTellerId && gm.guesserId !== gm.truthTellerId);
  const guesser = byId(gm, gm.guesserId);
  assert.equal(guesser.topic, null);
  assert.equal(guesser.statement, null);
  assert.equal(guesser.detailed_description, null);
  const tt = byId(gm, gm.truthTellerId);
  assert.ok(tt.topic && tt.statement && tt.detailed_description);
});

test("unique topics for suspects", () => {
  const gm = new GameManager({ seedSamples: true });
  const topics = gm.players.filter((p) => p.id !== gm.guesserId).map((p) => p.topic);
  assert.equal(topics.length, new Set(topics).size, "Each suspect must have a unique topic!");
});

test("only the guesser can vote", () => {
  const gm = new GameManager({ seedSamples: true });
  const liar = liarsOf(gm)[0]!;
  assert.equal(gm.castVote(liar.id, gm.truthTellerId), false, "Non-guesser must not be allowed to cast vote!");
  assert.equal(gm.castVote(gm.guesserId!, gm.truthTellerId), true);
  assert.equal(byId(gm, gm.guesserId).voted_for, gm.truthTellerId);
});

test("topic history persistence and clearing", () => {
  const gm = new GameManager({ seedSamples: true });
  gm.clearTopicHistory();
  assert.equal(gm.usedTopicIds.length, 0);
  gm.assignRoundRoles();
  const usedCount = gm.usedTopicIds.length;
  assert.ok(usedCount > 0);
  // Statements are recorded to the global history once they go live
  assert.deepEqual(accounts.globalKeys(), []);
  gm.setPhase("questioning", true);
  assert.equal(new Set(accounts.globalKeys().map(accounts.topicOf)).size, usedCount);
  // Next round should not reuse those same topics
  const old = new Set(gm.usedTopicIds);
  gm.nextRound();
  assert.ok(new Set(gm.usedTopicIds).size > old.size);
  gm.clearTopicHistory();
  assert.equal(gm.usedTopicIds.length, 0);
});

test("player reconnect sync", () => {
  const gm = new GameManager();
  const p = gm.addPlayer("TestUser123");
  const p2 = gm.syncPlayer(p.id, "TestUser123");
  assert.equal(p2.id, p.id);
  assert.equal(gm.players.filter((x) => x.name === "TestUser123").length, 1);
});

test("untimed phases", () => {
  const gm = new GameManager({ seedSamples: true });
  assert.ok(!("timer_seconds" in gm) && !("timer_running" in gm));
  const state = gm.getState();
  assert.ok(!("timer_seconds" in state) && !("timer" in state));
  gm.setPhase("questioning");
  assert.equal(gm.phase, "questioning");
  gm.setPhase("voting");
  assert.equal(gm.phase, "voting");
});

test("direct role assignment", () => {
  const gm = new GameManager({ seedSamples: true });
  const target = liarsOf(gm)[0]!.id;
  assert.equal(gm.setPlayerRole(target, "guesser"), true);
  assert.equal(gm.guesserId, target);
  let p = byId(gm, target);
  assert.equal(p.role, "guesser");
  assert.equal(p.statement, null);
  assert.equal(p.detailed_description, null);

  assert.equal(gm.setPlayerRole(target, "truth_teller"), true);
  assert.equal(gm.truthTellerId, target);
  p = byId(gm, target);
  assert.equal(p.role, "truth_teller");
  assert.ok(p.statement && p.detailed_description);
  assert.ok(gm.guesserId && gm.guesserId !== target); // the guesser moved to someone else
});

test("truth teller phone state and description", () => {
  const gm = new GameManager({ seedSamples: true });
  gm.setPhase("questioning");
  const ttId = gm.truthTellerId!;
  const gId = gm.guesserId!;
  const liar = gm.players.find((p) => p.id !== ttId && p.id !== gId)!;

  const myTT = me(gm, ttId);
  assert.equal(myTT.role, "truth_teller");
  assert.equal(myTT.is_truth_teller, true);
  assert.equal(myTT.is_guesser, false);
  assert.ok(myTT.topic && myTT.statement && myTT.detailed_description);

  const myLiar = me(gm, liar.id);
  assert.equal(myLiar.role, "liar");
  assert.equal(myLiar.is_truth_teller, false);
  assert.ok(myLiar.statement);
  assert.equal(myLiar.detailed_description, null, "Liars must never receive detailed descriptions!");

  const myG = me(gm, gId);
  assert.equal(myG.role, "guesser");
  assert.equal(myG.is_guesser, true);
  assert.equal(myG.topic, null);
  assert.equal(myG.statement, null);
  assert.equal(myG.detailed_description, null);
});

test("scoring: correct guess", () => {
  const gm = new GameManager({ seedSamples: true });
  for (const p of gm.players) p.score = 0;
  const guesser = byId(gm, gm.guesserId);
  const tt = byId(gm, gm.truthTellerId);
  const liar = liarsOf(gm)[0]!;
  assert.equal(gm.castVote(guesser.id, tt.id), true);
  assert.equal(gm.phase, "reveal"); // auto-reveal
  assert.deepEqual([guesser.score, tt.score, liar.score], [1, 1, 0]);
});

test("scoring: incorrect guess", () => {
  const gm = new GameManager({ seedSamples: true });
  for (const p of gm.players) p.score = 0;
  const guesser = byId(gm, gm.guesserId);
  const tt = byId(gm, gm.truthTellerId);
  const liar = liarsOf(gm)[0]!;
  assert.equal(gm.castVote(guesser.id, liar.id), true);
  assert.equal(gm.phase, "reveal");
  assert.deepEqual([guesser.score, liar.score, tt.score], [0, 1, 0]);
});

test("guesser advances the stages", () => {
  const gm = new GameManager({ seedSamples: true });
  gm.setPhase("setup");
  assert.equal(gm.guesserAdvance(gm.truthTellerId!), false);
  assert.equal(gm.phase, "setup");
  assert.equal(gm.guesserAdvance(gm.guesserId!), true);
  assert.equal(gm.phase, "questioning");
  assert.equal(gm.guesserAdvance(gm.guesserId!), true);
  assert.equal(gm.phase, "voting");
});

test("standings structure and order", () => {
  const gm = new GameManager({ seedSamples: true });
  gm.players[0]!.score = 3;
  gm.players[1]!.score = 1;
  gm.players[2]!.score = 5;
  const s = gm.getStandings();
  assert.ok(s[0]!.score >= s[1]!.score && s[1]!.score >= s[2]!.score);
  assert.deepEqual(s.slice(0, 3).map((x) => x.rank), [1, 2, 3]);
});

const bigParty = (from: number, to: number): GameManager => {
  const gm = new GameManager({ seedSamples: true });
  for (let i = from; i < to; i++) gm.addPlayer(`Player_${i}`, `p_${i}`);
  return gm;
};

test("multi guesser and truth teller role counts", () => {
  const gm = bigParty(5, 9);
  assert.ok(gm.players.length >= 8);
  assert.equal(gm.setRoleCounts(2, 2, true), true);
  assert.equal(gm.targetGuesserCount, 2);
  assert.equal(gm.targetTruthTellerCount, 2);
  gm.assignRoundRoles();
  assert.equal(gm.guesserIds.length, 2);
  assert.equal(gm.truthTellerIds.length, 2);
  assert.ok(gm.votingGuesserId && gm.guesserIds.includes(gm.votingGuesserId));
  const voters = gm.players.filter((p) => p.is_voting_guesser);
  assert.equal(voters.length, 1);
  assert.equal(voters[0]!.id, gm.votingGuesserId);
  const others = gm.players.filter((p) => gm.guesserIds.includes(p.id) && p.id !== gm.votingGuesserId);
  assert.equal(others.length, 1);
  assert.equal(others[0]!.is_voting_guesser, false);
  assert.equal(gm.players.filter((p) => p.role === "liar").length, gm.players.length - 4);
});

test("only the designated voter can vote in a multi-guesser game", () => {
  const gm = bigParty(5, 7);
  gm.setRoleCounts(2, 1, true);
  gm.assignRoundRoles();
  const voter = gm.votingGuesserId!;
  const consultant = gm.guesserIds.find((g) => g !== voter)!;
  const tt = gm.truthTellerIds[0]!;
  const liar = gm.players.find((p) => p.role === "liar")!;
  assert.equal(gm.castVote(consultant, tt), false, "Consultant guesser must not be allowed to cast vote!");
  assert.equal(gm.castVote(liar.id, tt), false, "Suspect must not be allowed to cast vote!");
  assert.equal(gm.castVote(voter, tt), true);
  assert.equal(gm.phase, "reveal");
});

test("multi guesser team scoring on correct and incorrect guesses", () => {
  const gm = bigParty(5, 8);
  gm.setRoleCounts(2, 2, true);
  gm.assignRoundRoles();
  const zero = () => gm.players.forEach((p) => (p.score = 0));
  zero();
  const voterId = gm.votingGuesserId!;
  const consultantId = gm.guesserIds.find((g) => g !== voterId)!;
  const [tt1, tt2] = gm.truthTellerIds as [string, string];
  const [liar1, liar2] = gm.players.filter((p) => p.role === "liar") as [Player, Player];
  const voter = byId(gm, voterId);
  const consultant = byId(gm, consultantId);
  const tt1p = byId(gm, tt1);
  const tt2p = byId(gm, tt2);

  // 1: the voter names all truth tellers
  assert.equal(gm.castVote(voterId, null, [tt1, tt2]), true);
  assert.equal(gm.lastRoundResults!.is_correct, true);
  assert.deepEqual([voter.score, consultant.score, tt1p.score, tt2p.score, liar1.score, liar2.score], [1, 1, 1, 1, 0, 0]);

  // 2: one truth teller and one liar
  zero();
  gm.phase = "voting";
  assert.equal(gm.castVote(voterId, null, [tt1, liar1.id]), true);
  assert.equal(gm.lastRoundResults!.is_correct, false);
  assert.deepEqual([voter.score, consultant.score, tt1p.score, liar1.score, tt2p.score, liar2.score], [0, 0, 1, 1, 0, 0]);

  // 3: a single target when two truth tellers exist
  zero();
  gm.phase = "voting";
  assert.equal(gm.castVote(voterId, tt1), true);
  assert.equal(gm.lastRoundResults!.is_correct, false);
  assert.deepEqual([voter.score, consultant.score, tt1p.score, tt2p.score], [0, 0, 1, 0]);

  // 4: two liars
  zero();
  gm.phase = "voting";
  assert.equal(gm.castVote(voterId, null, [liar1.id, liar2.id]), true);
  assert.equal(gm.lastRoundResults!.is_correct, false);
  assert.deepEqual([voter.score, consultant.score, liar1.score, liar2.score, tt1p.score, tt2p.score], [0, 0, 1, 1, 0, 0]);
});

test("multiple truth tellers get unique topics and descriptions", () => {
  const gm = bigParty(5, 8);
  gm.setRoleCounts(1, 3, true);
  gm.assignRoundRoles();
  assert.equal(gm.truthTellerIds.length, 3);
  const tts = gm.players.filter((p) => gm.truthTellerIds.includes(p.id));
  assert.equal(new Set(tts.map((p) => p.topic)).size, 3, "Each truth teller must have a distinct unique topic!");
  for (const p of tts) assert.ok(p.statement && p.detailed_description);
  const suspects = gm.players.filter((p) => !gm.guesserIds.includes(p.id)).map((p) => p.topic);
  assert.equal(suspects.length, new Set(suspects).size);
});

test("phone state for the lead voter and consultant guessers", () => {
  const gm = bigParty(5, 7);
  gm.setRoleCounts(2, 1, true);
  gm.assignRoundRoles();
  const voterId = gm.votingGuesserId!;
  const consultantId = gm.guesserIds.find((g) => g !== voterId)!;
  const v = me(gm, voterId);
  assert.equal(v.is_guesser, true);
  assert.equal(v.is_voting_guesser, true);
  assert.equal(v.voting_guesser_name, v.name);
  assert.equal(v.fellow_guessers.length, 1);
  const c = me(gm, consultantId);
  assert.equal(c.is_guesser, true);
  assert.equal(c.is_voting_guesser, false);
  assert.equal(c.voting_guesser_name, v.name);
  assert.ok(c.fellow_guessers.includes(v.name));
});

test("set guessers (multi assignment)", () => {
  const gm = bigParty(5, 8);
  const ids = gm.players.map((p) => p.id);
  const targets = [ids[0]!, ids[1]!];
  assert.equal(gm.setGuessers(targets, targets[1]), true);
  assert.deepEqual(new Set(gm.guesserIds), new Set(targets));
  assert.equal(gm.votingGuesserId, targets[1]);
  assert.equal(gm.targetGuesserCount, 2);
  for (const p of gm.players) {
    if (targets.includes(p.id)) {
      assert.equal(p.role, "guesser");
      assert.equal(p.topic, null);
      assert.equal(p.is_voting_guesser, p.id === targets[1]);
    } else assert.ok(p.role === "truth_teller" || p.role === "liar");
  }
  assert.ok(gm.truthTellerIds.length >= 1);
  for (const tid of gm.truthTellerIds) assert.ok(!gm.guesserIds.includes(tid));
});

test("set truth tellers (multi assignment)", () => {
  const gm = bigParty(5, 8);
  const ids = gm.players.map((p) => p.id);
  gm.setGuessers([ids[0]!, ids[1]!]);
  const targets = [ids[2]!, ids[3]!];
  assert.equal(gm.setTruthTellers(targets), true);
  assert.deepEqual(new Set(gm.truthTellerIds), new Set(targets));
  assert.equal(gm.targetTruthTellerCount, 2);
  for (const p of gm.players) {
    if (targets.includes(p.id)) {
      assert.equal(p.role, "truth_teller");
      assert.ok(p.statement && p.detailed_description);
    } else if (gm.guesserIds.includes(p.id)) assert.equal(p.role, "guesser");
    else {
      assert.equal(p.role, "liar");
      assert.equal(p.detailed_description, null);
    }
  }
  const topics = gm.players.filter((p) => targets.includes(p.id)).map((p) => p.topic);
  assert.equal(topics.length, new Set(topics).size);
});

test("setGuesser and setTruthTeller accept a list or a single id", () => {
  const gm = bigParty(5, 8);
  const ids = gm.players.map((p) => p.id);
  assert.equal(gm.setGuesser([ids[0]!, ids[1]!]), true);
  assert.equal(gm.guesserIds.length, 2);
  assert.equal(gm.setTruthTeller([ids[2]!, ids[3]!]), true);
  assert.equal(gm.truthTellerIds.length, 2);
  assert.equal(gm.setGuesser(ids[4]!), true);
  assert.equal(gm.guesserId, ids[4]);
});

test("used true and false statements are tracked separately", () => {
  const gm = bigParty(5, 8);
  gm.setRoleCounts(1, 2, true);
  gm.clearTopicHistory(); // counts are cumulative across rounds; start this check from zero
  gm.assignRoundRoles();
  const trues = gm.usedStatements.filter((s) => s.type === "true");
  const falses = gm.usedStatements.filter((s) => s.type === "false");
  assert.equal(trues.length, 2, "There must be 2 true statements used for 2 truth tellers");
  assert.equal(falses.length, gm.players.length - 1 - 2);
  for (const ts of trues) assert.ok(ts.statement && ts.detailed_description && ts.topic);
  for (const fs of falses) assert.ok(fs.statement && fs.topic && !fs.detailed_description);

  gm.setPhase("questioning", true);
  const st = gm.getState({ isAdmin: true });
  assert.equal(st.used_true_statements.length, 2);
  assert.equal(st.used_false_statements.length, falses.length);
  assert.equal(st.used_true_count, 2);
  assert.equal(st.used_false_count, falses.length);
  assert.equal(st.used_truth_count, 2);
  assert.equal(st.used_lies_count, falses.length);
  assert.equal(st.total_truth_count, lib().length);
  assert.equal(st.total_lies_count, lib().length);

  const pid = gm.players[0]!.id;
  const ps = gm.getState({ isAdmin: false, playerId: pid, token: tok(gm, pid) });
  assert.deepEqual(ps.used_true_statements, []);
  assert.deepEqual(ps.used_false_statements, []);

  gm.clearTopicHistory();
  assert.equal(gm.usedStatements.length, 0);
  assert.equal(gm.getState({ isAdmin: true }).used_true_count, 0);
  assert.equal(gm.getState({ isAdmin: true }).used_false_count, 0);

  gm.assignRoundRoles();
  const r1 = gm.usedStatements.length;
  assert.ok(r1 > 0);
  gm.nextRound();
  const r2 = gm.usedStatements.length;
  assert.ok(r2 > r1, "Statements used should accumulate across rounds");
  const rounds = new Set(gm.usedStatements.map((s) => s.round));
  assert.ok(rounds.has(1) && rounds.has(2));
});

test("logs: terminal and server log privacy", () => {
  const gm = new GameManager({ seedSamples: false });
  assert.ok(gm.logs.length >= 1);
  assert.ok(gm.logs[0]!.message.includes("Server initialized"));
  assert.equal(gm.logs[0]!.level, "INFO");
  const p1 = gm.addPlayer("Tester 1");
  gm.addPlayer("Tester 2");
  gm.addPlayer("Tester 3");
  gm.setPhase("setup");
  const msgs = gm.logs.map((l) => l.message);
  assert.ok(msgs.some((m) => m.includes("Tester 1")));
  assert.ok(msgs.some((m) => m.includes("SETUP")));
  const st = gm.getState({ isAdmin: true });
  assert.ok(st.logs.length >= 3);
  assert.ok(st.logs.every((l) => "timestamp" in l && "level" in l && "message" in l));
  assert.deepEqual(gm.getState({ isAdmin: false, playerId: p1.id, token: tok(gm, p1.id) }).logs, []);
  gm.clearLogs();
  assert.equal(gm.logs.length, 1);
  assert.ok(gm.logs[0]!.message.toLowerCase().includes("cleared"));
});

test("game start minimum role requirements", () => {
  const gm = new GameManager({ seedSamples: false });
  let [valid, err, counts] = gm.checkRoleRequirements();
  assert.equal(valid, false);
  assert.ok(err!.includes("No players have joined"));
  assert.equal(gm.setPhase("setup"), false);
  assert.equal(gm.nextPhase(), "lobby");

  gm.addPlayer("Alice");
  [valid, err] = gm.checkRoleRequirements();
  assert.equal(valid, false);
  assert.ok(err!.includes("minimum 3 players"));
  assert.equal(gm.setPhase("setup"), false);

  gm.addPlayer("Bob");
  [valid, err] = gm.checkRoleRequirements();
  assert.equal(valid, false);
  assert.ok(err!.includes("minimum 3 players") || err!.includes("0 Liar"));
  assert.equal(gm.setPhase("setup"), false);
  assert.equal(gm.nextPhase(), "lobby");

  gm.addPlayer("Charlie");
  gm.setRoleCounts(2, 1);
  [valid, err, counts] = gm.checkRoleRequirements();
  assert.equal(valid, false);
  assert.ok(err!.includes("at least 1 Liar"));
  assert.deepEqual([counts.guessers, counts.truth_tellers, counts.liars], [2, 1, 0]);
  assert.equal(gm.setPhase("setup"), false);
  assert.equal(gm.nextPhase(), "lobby");

  gm.setRoleCounts(1, 2);
  [valid, err, counts] = gm.checkRoleRequirements();
  assert.equal(valid, false);
  assert.ok(err!.includes("at least 1 Liar"));
  assert.deepEqual([counts.guessers, counts.truth_tellers, counts.liars], [1, 2, 0]);
  assert.equal(gm.setPhase("setup"), false);

  gm.addPlayer("Dave");
  gm.setRoleCounts(2, 2);
  [valid, err, counts] = gm.checkRoleRequirements();
  assert.equal(valid, false);
  assert.ok(err!.includes("at least 1 Liar"));
  assert.deepEqual([counts.guessers, counts.truth_tellers, counts.liars], [2, 2, 0]);
  assert.equal(gm.setPhase("setup"), false);

  gm.setRoleCounts(1, 1);
  [valid, err, counts] = gm.checkRoleRequirements();
  assert.equal(valid, true);
  assert.equal(err, null);
  assert.deepEqual([counts.guessers, counts.truth_tellers, counts.liars], [1, 1, 2]);
  assert.equal(gm.setPhase("setup"), true);
  assert.equal(gm.phase, "setup");

  const st = gm.getState({ isAdmin: true });
  assert.equal(st.role_requirements.valid, true);
  assert.deepEqual([st.role_requirements.players, st.role_requirements.guessers, st.role_requirements.truth_tellers, st.role_requirements.liars], [4, 1, 1, 2]);
});

test("round end blocks advance and previous phases", () => {
  const gm = new GameManager({ seedSamples: true });
  gm.setPhase("setup");
  gm.setPhase("questioning");
  gm.setPhase("voting");
  gm.setPhase("reveal");
  assert.equal(gm.phase, "reveal");
  assert.equal(gm.nextPhase(), "reveal");
  assert.equal(gm.setPhase("voting"), false);
  assert.equal(gm.setPhase("questioning"), false);
  assert.equal(gm.setPhase("setup"), false);
  assert.equal(gm.phase, "reveal");
  assert.equal(gm.nextRound(), true);
  assert.equal(gm.phase, "setup");
  assert.equal(gm.roundNumber, 2);
  gm.setPhase("voting");
  gm.setPhase("reveal");
  assert.equal(gm.setPhase("lobby"), true);
  assert.equal(gm.phase, "lobby");
});

test("a normal launch starts with an empty lobby and no default players", () => {
  const leftover = join(sandbox.dir, "leftover_players.json");
  writeFileSync(
    leftover,
    JSON.stringify([
      { id: "p1", name: "Player 1", role: "guesser" }, { id: "p2", name: "Player 2", role: "truth_teller" }, { id: "p3", name: "Player 3", role: "liar" },
      { id: "p4", name: "Alice", role: "liar" }, { id: "p5", name: "Bob", role: "liar" },
    ]),
  );
  const gm = new GameManager();
  assert.equal(gm.players.length, 0);
  assert.deepEqual(gm.guesserIds, []);
  assert.equal(gm.votingGuesserId, null);
  assert.deepEqual(gm.truthTellerIds, []);
  assert.equal(gm.phase, "lobby");

  const gm2 = new GameManager({ seedSamples: false, playersFile: leftover });
  assert.equal(gm2.players.length, 0);
  assert.deepEqual(gm2.guesserIds, []);
  assert.deepEqual(gm2.truthTellerIds, []);
  assert.equal(gm2.phase, "lobby");

  for (let i = 1; i <= 6; i++) gm2.syncPlayer(`p_${i}`, `Player ${i}`);
  assert.equal(gm2.players.length, 6);
  assert.deepEqual(gm2.players.map((p) => p.name), [1, 2, 3, 4, 5, 6].map((i) => `Player ${i}`));
});
