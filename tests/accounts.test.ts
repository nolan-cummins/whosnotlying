import { strict as assert } from "node:assert";
import { test } from "node:test";
import * as accounts from "../src/accounts.ts";
import { GameManager, findTopicData } from "../src/game.ts";
import { isolate, startServer } from "./helpers.ts";

isolate();

test("admin pages and actions need login", async () => {
  const s = await startServer(new GameManager());
  try {
    let r = await s.get("/", { admin: false });
    assert.equal(r.headers.get("location"), "/join");
    r = await s.get("/admin", { admin: false });
    assert.ok(r.headers.get("location")!.startsWith("/admin/login"));
    assert.ok((await s.get("/admin")).text.includes("Admin Console"));
    assert.equal((await s.get("/api/state?role=admin", { admin: false })).status, 401);
    assert.equal((await s.action({ action: "reset_game" }, { admin: false })).status, 401);
    assert.equal((await s.action({ action: "add_player", name: "X" }, { admin: false })).status, 401);
  } finally {
    await s.close();
  }
});

test("admin login sets a cookie and rejects a bad password", async () => {
  const s = await startServer(new GameManager());
  try {
    for (const [pw, ok] of [["wrong", false], ["notthepassword", true]] as const) {
      const r = await s.post("/api/admin/login", `username=admin&password=${pw}`, { admin: false, form: true });
      assert.equal(r.headers.has("set-cookie"), ok);
      assert.equal(r.headers.get("location"), ok ? "/admin" : "/admin/login?error=1&next=/admin");
    }
  } finally {
    await s.close();
  }
});

test("player token gates private state and votes", async () => {
  const gm = new GameManager();
  const s = await startServer(gm);
  try {
    const toks: Record<string, string> = {};
    for (const n of ["Ann", "Ben", "Cy", "Dee"]) {
      const r = await s.action({ action: "join", name: n }, { admin: false });
      assert.equal(r.status, 200);
      assert.ok(r.json.token);
      toks[r.json.joined_player_id] = r.json.token;
      assert.ok(!("logs" in r.json) || r.json.logs.length === 0); // players never get the admin view
    }
    const pid = Object.keys(toks)[0]!;
    assert.equal(gm.getState({ isAdmin: false, playerId: pid }).my_info, null);
    assert.equal(gm.getState({ isAdmin: false, playerId: pid, token: toks[pid] }).my_info!.id, pid);
    // Someone else can't take the name, or vote as the guesser
    assert.equal((await s.action({ action: "join", name: "ann" }, { admin: false })).status, 403);
    gm.setPhase("voting", true);
    const voter = gm.votingGuesserId!;
    assert.equal((await s.action({ action: "cast_vote", voter_id: voter, target_id: gm.truthTellerIds[0] }, { admin: false })).status, 403);
    assert.equal((await s.action({ action: "cast_vote", voter_id: voter, target_id: gm.truthTellerIds[0], token: toks[voter] }, { admin: false })).status, 200);
  } finally {
    await s.close();
  }
});

test("temporary password re-login; reset signs out temporary players", () => {
  const gm = new GameManager();
  const { player: p } = gm.join("Temp", "pw12");
  assert.deepEqual(gm.join("Temp", "nope"), { player: null, error: "That name is taken. Enter its password to log back in." });
  assert.equal(gm.join("Temp", "pw12").player, p);
  gm.join("Keeper", "secret", true);
  gm.resetGame();
  assert.deepEqual(gm.players.map((x) => x.name), ["Keeper"]);
});

test("a permanent account's history blocks topics; toggles", () => {
  const gm = new GameManager();
  for (const n of ["A", "B", "C"]) gm.join(n);
  const { player: perm } = gm.join("Vet", "secret", true);
  assert.deepEqual(gm.join("Vet2", "ab", true), { player: null, error: "Permanent accounts need a password (4+ characters)." });
  gm.setPhase("questioning", true);
  const acct = perm!.account_id!;
  const seen = accounts.blockedTopics([acct]);
  assert.equal(seen.size, 3); // three suspects' statements were heard

  // A new game later, global history off: only Vet's own history blocks topics
  accounts.setSetting("use_global", false);
  const gm2 = new GameManager();
  for (const n of ["X", "Y", "Z"]) gm2.join(n);
  assert.equal(gm2.join("Vet", "wrong").error, "A saved account uses that name. Wrong password.");
  gm2.join("Vet", "secret");
  for (let i = 0; i < 20; i++) {
    gm2.assignRoundRoles();
    const dealt = new Set(gm2.players.filter((p) => p.topic).map((p) => findTopicData(p.topic)!.id));
    assert.ok([...dealt].every((d) => !seen.has(d)));
  }
  accounts.setSetting("use_user", false);
  assert.deepEqual(gm2.blocked(), new Set(gm2.usedTopicIds));
});

test("lying facts toggle reaches only liars", () => {
  const gm = new GameManager();
  const toks: Record<string, string> = {};
  for (const n of ["A", "B", "C", "D"]) {
    const { player: p } = gm.join(n);
    toks[p!.id] = p!.token!;
  }
  const liar = gm.players.find((p) => p.role === "liar")!;
  const t = findTopicData(liar.topic)!;
  const lie = t.lies.find((l) => l.text === liar.statement)!;
  lie.facts = ["grounding fact"]; // library() copies are shallow: this edits the cached pack
  const me = () => gm.getState({ isAdmin: false, playerId: liar.id, token: toks[liar.id] }).my_info!;
  assert.deepEqual(me().lie_facts, []);
  accounts.setSetting("lying_facts", true);
  assert.deepEqual(me().lie_facts, ["grounding fact"]);
  assert.ok(gm.getState({ isAdmin: false }).players.every((p) => !("lie_facts" in p)));
});

test("the View Used archive survives a restart and a reset", () => {
  const gm = new GameManager();
  for (const n of ["A", "B", "C"]) gm.join(n);
  gm.setPhase("questioning", true);
  const n = gm.usedStatements.length;
  assert.equal(n, 2); // two suspects' statements this round
  gm.resetGame();
  assert.equal(new GameManager().usedStatements.length, n); // a restarted server still has them
  gm.clearTopicHistory();
  assert.deepEqual(new GameManager().usedStatements, []);
});

test("forgot password reset flow", async () => {
  const gm = new GameManager();
  const s = await startServer(gm);
  try {
    assert.equal((await s.action({ action: "join", name: "Ann", password: "old1", permanent: true }, { admin: false })).status, 200);
    gm.players = []; // Ann's phone lost the session and the lobby moved on
    assert.deepEqual((await s.action({ action: "request_reset", name: "ann" }, { admin: false })).json, { ok: true });
    assert.deepEqual((await s.action({ action: "request_reset", name: "nobody" }, { admin: false })).json, { ok: true }); // no account enumeration
    const acct = accounts.listAccounts().find((a) => a.name === "Ann")!;
    assert.ok(acct.reset_requested);
    assert.equal((await s.action({ action: "reset_password", account_id: acct.id }, { admin: false })).status, 401);
    const temp = (await s.action({ action: "reset_password", account_id: acct.id })).json.temp_password as string;
    assert.equal((await s.action({ action: "join", name: "Ann", password: "old1" }, { admin: false })).status, 403);
    const r = await s.action({ action: "join", name: "Ann", password: temp }, { admin: false });
    assert.equal(r.status, 403);
    assert.ok(r.json.need_new_password);
    assert.equal((await s.action({ action: "join", name: "Ann", password: temp, new_password: "new1" }, { admin: false })).status, 200);
    gm.players = [];
    assert.equal((await s.action({ action: "join", name: "Ann", password: "new1" }, { admin: false })).status, 200);
    assert.ok(!accounts.listAccounts().find((a) => a.name === "Ann")!.reset_requested);
  } finally {
    await s.close();
  }
});

test("end game books the winner; idle timeout signs everyone out", async () => {
  const gm = new GameManager();
  const s = await startServer(gm);
  try {
    for (const n of ["Ann", "Bob", "Cy"]) await s.action({ action: "join", name: n, password: "pw12", permanent: true }, { admin: false });
    gm.players[0]!.score = 5;
    gm.players[1]!.score = 2;
    await s.action({ action: "end_game" });
    const board = Object.fromEntries(((await s.get("/api/leaderboard", { admin: false })).json.leaderboard as { name: string; wins: number; games: number }[]).map((r) => [r.name, r]));
    assert.deepEqual([board["Ann"]!.wins, board["Ann"]!.games, board["Bob"]!.wins, board["Bob"]!.games], [1, 1, 0, 1]);
    assert.ok(gm.players.length === 3 && gm.players.every((p) => p.score === 0)); // admin end keeps who's in the room
    gm.players[2]!.score = 1;
    gm.lastActivity -= 3601;
    gm.getState({ isAdmin: false });
    assert.deepEqual(gm.players, []); // an hour of silence: everyone is signed out, /join starts a new lobby
    assert.deepEqual(Object.fromEntries(accounts.leaderboard().map((r) => [r.name, [r.wins, r.games]])), { Ann: [1, 2], Bob: [0, 2], Cy: [1, 2] });
  } finally {
    await s.close();
  }
});

test("roles and topics are separate buttons", () => {
  const gm = new GameManager();
  for (const n of "ABCDE") gm.addPlayer(n);
  gm.assignRoundRoles();
  const roles = Object.fromEntries(gm.players.map((p) => [p.id, p.role]));
  let topics = Object.fromEntries(gm.players.map((p) => [p.id, p.topic]));
  gm.newTopics(true);
  assert.deepEqual(Object.fromEntries(gm.players.map((p) => [p.id, p.role])), roles);
  assert.ok(gm.players.filter((p) => p.role !== "guesser").every((p) => p.topic !== topics[p.id]));
  assert.equal(accounts.globalKeys().length, 4); // the 4 dropped statements count as heard
  topics = Object.fromEntries(gm.players.map((p) => [p.id, p.topic]));
  for (let i = 0; i < 5; i++) {
    gm.randomizeRoles();
    const kept = gm.players.filter((p) => p.role !== "guesser" && topics[p.id]);
    assert.ok(kept.every((p) => p.topic === topics[p.id])); // trivia topics have both sides: kept
    topics = Object.fromEntries(gm.players.map((p) => [p.id, p.topic]));
  }
});

test("sources are redacted during questioning", () => {
  const gm = new GameManager();
  assert.ok(gm.setPacks(["phd-mode"]));
  for (const n of "ABCDE") gm.addPlayer(n);
  gm.assignRoundRoles();
  const tt = gm.players.find((p) => p.role === "truth_teller")!;
  const liar = gm.players.find((p) => p.role === "liar")!;
  const me = (p: { id: string; token?: string }) => gm.getState({ isAdmin: false, playerId: p.id, token: (p.token ??= "t" + p.id) }).my_info!;
  assert.ok((me(tt).source as { institution?: string }).institution);
  gm.setPhase("questioning", true);
  assert.deepEqual(me(tt).source, { redacted: true });
  assert.ok(!("venue" in (me(liar) as object)));
});

test("reviews are saved, tagged and validated", async () => {
  const gm = new GameManager();
  assert.ok(gm.setPacks(["phd-mode"]));
  const s = await startServer(gm);
  try {
    assert.equal((await s.action({ action: "join", name: "Rae", password: "pw123456", permanent: true }, { admin: false })).status, 200);
    for (const n of "BCDE") gm.addPlayer(n);
    gm.assignRoundRoles();
    const rae = gm.players.find((p) => p.name === "Rae")!;
    const base = { action: "review", player_id: rae.id, token: rae.token };
    for (let i = 0; i < 50; i++) {
      // make sure Rae is a suspect holding a statement (guessers hold none)
      if (rae.role !== "guesser") break;
      assert.equal((await s.action({ ...base, score: 5 }, { admin: false })).status, 400);
      gm.randomizeRoles();
    }
    assert.ok(rae.statement);
    assert.equal((await s.action({ ...base, score: 11, text: "x" }, { admin: false })).status, 400);
    assert.equal((await s.action({ ...base, score: 7, text: "word ".repeat(101) }, { admin: false })).status, 400);
    assert.equal((await s.action({ ...base, score: 7, text: "Clear, but fact 2 is vague." }, { admin: false })).status, 200);
    assert.equal((await s.action({ ...base, score: 3 }, { admin: false })).status, 200); // several reviews allowed
    assert.equal((await s.action({ action: "review", player_id: rae.id, token: "wrong", score: 5 }, { admin: false })).status, 403);
    const rows = accounts.reviews();
    assert.deepEqual(rows.map((x) => x.score), [3, 7]);
    assert.ok(rows[1]!.account_id && rows[1]!.player_name === "Rae" && rows[1]!.statement === rae.statement);
    assert.ok(rows[1]!.topic_id!.startsWith("phd-mode:") && rows[1]!.facts);
    assert.equal((await s.get("/api/reviews", { admin: false })).status, 403);
    assert.equal((await s.get("/api/reviews")).json.reviews[0].score, 3);
  } finally {
    await s.close();
  }
});
