/** HTTP server tests: every page and API route, through a real server on a random port. */
import { strict as assert } from "node:assert";
import { test } from "node:test";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { GameManager } from "../src/game.ts";
import * as server from "../src/server.ts";
import * as templates from "../src/templates.ts";
import { isolate, startServer, tok, type TestServer } from "./helpers.ts";

isolate();

/** Run a test against a server seeded with the sample players (or the given game). */
async function withServer(gm: GameManager | null, fn: (s: TestServer) => Promise<void>): Promise<void> {
  const s = await startServer(gm ?? new GameManager({ seedSamples: true }));
  try {
    await fn(s);
  } finally {
    await s.close();
  }
}

test("admin dashboard page", () => withServer(null, async (s) => {
  const html = (await s.get("/admin")).text;
  assert.ok(html.includes("Admin Console"));
  assert.ok(html.includes("One of These People Is Not Lying"));
}));

test("qr page", () => withServer(null, async (s) => {
  const html = (await s.get("/qr")).text;
  assert.ok(html.includes("Scan to Join Game"));
  assert.ok(html.includes("Join Lobby - QR Code"));
}));

test("join page", () => withServer(null, async (s) => {
  assert.ok((await s.get("/join")).text.includes("Join The Game"));
}));

test("qr svg api", () => withServer(null, async (s) => {
  const r = await s.get("/api/qr.svg?url=http://192.168.0.100:5050/join");
  assert.equal(r.headers.get("content-type"), "image/svg+xml; charset=utf-8");
  assert.ok(r.text.includes("<svg") && r.text.includes("</svg>"));
}));

test("api state for the admin", () => withServer(null, async (s) => {
  const data = (await s.get("/api/state?role=admin")).json;
  for (const k of ["truth_teller_id", "guesser_id", "used_topics_count", "total_topics_count"]) assert.ok(k in data, k);
}));

test("api action sync_player", () => withServer(null, async (s) => {
  const data = (await s.action({ action: "sync_player", player_id: "test_id_999", name: "SyncedPlayer" })).json;
  const matching = data.players.filter((p: { id: string }) => p.id === "test_id_999");
  assert.equal(matching.length, 1);
  assert.equal(matching[0].name, "SyncedPlayer");
}));

test("api action clear_topic_history", () => withServer(null, async (s) => {
  assert.equal((await s.action({ action: "clear_topic_history" })).json.used_topics_count, 0);
}));

test("api action set_role", () => withServer(null, async (s) => {
  const target = (await s.get("/api/state?role=admin")).json.players[1].id;
  const res = (await s.action({ action: "set_role", player_id: target, role: "truth_teller" })).json;
  assert.equal(res.truth_teller_id, target);
  const tt = res.players.find((p: { id: string }) => p.id === target);
  assert.equal(tt.is_truth_teller, true);
  assert.ok(tt.detailed_description);
  const res2 = (await s.action({ action: "set_role", player_id: target, role: "guesser" })).json;
  assert.equal(res2.guesser_id, target);
  assert.equal(res2.players.find((p: { id: string }) => p.id === target).is_guesser, true);
}));

test("api action set_guesser and set_truth_teller endpoints", () => withServer(null, async (s) => {
  const players = (await s.get("/api/state?role=admin")).json.players;
  const [a, b] = [players[0].id, players[1].id];
  assert.equal((await s.action({ action: "set_guesser", player_id: a })).json.guesser_id, a);
  const res = (await s.action({ action: "set_truth_teller", player_id: b })).json;
  assert.equal(res.truth_teller_id, b);
  const tt = res.players.find((p: { id: string }) => p.id === b);
  assert.equal(tt.is_truth_teller, true);
  assert.ok(tt.topic && tt.statement && tt.detailed_description);
}));

test("api action randomize_roles picks topics for every suspect", () => withServer(null, async (s) => {
  const res = (await s.action({ action: "randomize_roles" })).json;
  for (const p of res.players) if (p.id !== res.guesser_id) assert.ok(p.topic && p.statement);
  assert.ok(res.guesser_id && res.truth_teller_id && res.guesser_id !== res.truth_teller_id);
}));

test("player client topics always present", () => withServer(null, async (s) => {
  const data = (await s.get("/api/state?role=admin")).json;
  const suspects = data.players.filter((p: { id: string }) => p.id !== data.guesser_id);
  assert.ok(suspects.length > 0);
  const sid = suspects[0].id;
  const p = (await s.get(`/api/state?role=player&player_id=${sid}&token=${tok(s.gm, sid)}`, { admin: false })).json;
  assert.ok(p.my_info && p.my_info.topic);
  for (const x of p.players) if (!x.is_guesser) assert.ok(x.topic);
}));

test("setup and questioning phases reveal topics to the right phones", async () => {
  const gm = new GameManager({ seedSamples: true });
  gm.setPhase("lobby");
  gm.setPhase("setup");
  assert.equal(gm.phase, "setup");
  await withServer(gm, async (s) => {
    const ttId = gm.truthTellerId!;
    const dataTT = (await s.get(`/api/state?role=player&player_id=${ttId}&token=${tok(gm, ttId)}`, { admin: false })).json;
    assert.equal(dataTT.phase, "setup");
    assert.equal(dataTT.my_info.role, "truth_teller");
    assert.ok(dataTT.my_info.topic && dataTT.my_info.statement && dataTT.my_info.detailed_description);

    const liar = gm.players.find((p) => p.id !== gm.truthTellerId && p.id !== gm.guesserId)!;
    const dataLiar = (await s.get(`/api/state?role=player&player_id=${liar.id}&token=${tok(gm, liar.id)}`, { admin: false })).json;
    assert.equal(dataLiar.phase, "setup");
    assert.equal(dataLiar.my_info.role, "liar");
    assert.ok(dataLiar.my_info.topic && dataLiar.my_info.statement);
    assert.equal(dataLiar.my_info.detailed_description, null);

    gm.setPhase("questioning");
    const dataTT2 = (await s.get(`/api/state?role=player&player_id=${ttId}&token=${tok(gm, ttId)}`, { admin: false })).json;
    assert.equal(dataTT2.phase, "questioning");
    assert.equal(dataTT2.my_info.topic, dataTT.my_info.topic);
    assert.equal(dataTT2.my_info.detailed_description, dataTT.my_info.detailed_description);
  });
});

test("player name fallback and no-cache headers", async () => {
  const gm = new GameManager({ seedSamples: true });
  const name = gm.players[0]!.name;
  const token = gm.join(name).player!.token; // an unclaimed (admin-added) player can be claimed by name
  await withServer(gm, async (s) => {
    const r = await s.get(`/api/state?role=player&player_id=name:${name}&token=${token}`, { admin: false });
    const cc = r.headers.get("cache-control") ?? "";
    assert.ok(cc.includes("no-cache") && cc.includes("no-store"));
    assert.ok(r.json.my_info);
    assert.equal(r.json.my_info.name.toLowerCase(), name.toLowerCase());
  });
});

test("escapeHtml is present in the join page", () => withServer(null, async (s) => {
  const html = (await s.get("/join")).text;
  assert.ok(html.includes("function escapeHtml") && html.includes("escapeHtml(str)"));
}));

test("api action guesser_advance", async () => {
  const gm = new GameManager({ seedSamples: true });
  gm.setPhase("questioning");
  await withServer(gm, async (s) => {
    assert.equal((await s.action({ action: "guesser_advance", player_id: gm.guesserId })).json.phase, "voting");
    const liar = gm.players.find((p) => p.id !== gm.guesserId)!;
    const r = await s.action({ action: "guesser_advance", player_id: liar.id });
    assert.equal(r.status, 403);
  });
});

test("admin dashboard masks topics by default", () => withServer(null, async (s) => {
  const html = (await s.get("/admin")).text;
  assert.ok(html.includes("toggleTopic") && html.includes("toggleAllTopics") && html.includes("Show Topic"));
  assert.ok(html.includes("Topic &amp; Summary Hidden") || html.includes("Topic & Summary Hidden"));
}));

test("auto reveal via the server vote action", async () => {
  const gm = new GameManager({ seedSamples: true });
  await withServer(gm, async (s) => {
    const data = (await s.action({ action: "cast_vote", voter_id: gm.guesserId, target_id: gm.truthTellerId })).json;
    assert.equal(data.phase, "reveal");
    assert.ok(data.standings.length > 0);
    assert.equal(data.last_results.is_correct, true);
  });
});

test("stage controller page", () => withServer(null, async (s) => {
  const html = (await s.get("/admin/control")).text;
  for (const want of ["Stage Controller", "Blind Host Participation", "Jump to Any Game Stage", "Advance to Next Stage", "ctrl-guesser-count", "ctrl-truth-count", "updateRoleCounts", "Role Quantities"]) assert.ok(html.includes(want), want);
  // Zero spoilers guarantee: no player dossier or secret topics in the template
  for (const bad of ["admin-select-guesser", "admin-select-tt", "Secret Dossier"]) assert.ok(!html.includes(bad), bad);
}));

test("auto reveal on set_phase reveal", async () => {
  const gm = new GameManager({ seedSamples: true });
  assert.equal(gm.lastRoundResults, null);
  await withServer(gm, async (s) => {
    const data = (await s.action({ action: "set_phase", phase: "reveal" })).json;
    assert.equal(data.phase, "reveal");
    assert.ok(data.last_results);
    assert.ok(data.standings.length > 0);
  });
});

test("all clients have standings components", () => {
  const join = templates.getJoinHtml(5050);
  const display = templates.getDisplayHtml(5050);
  const qr = templates.getQrHtml(5050, "192.168.1.5");
  const stage = templates.getStageControlHtml(5050);
  assert.ok(join.includes("join-standings-preview") && join.includes("Current Standings") && join.includes("Round"));
  assert.ok(display.includes("Standings") && display.includes("state.standings"));
  assert.ok(qr.includes("qr-standings-card"));
  assert.ok(stage.includes("Stage Controller") && stage.includes("nextPhase") && stage.includes("nextRound"));
});

/** A throwaway process that listens on a port for 30 s. */
function occupy(port: number) {
  return spawn(process.execPath, ["-e", `require("node:net").createServer().listen(${port}, "0.0.0.0"); setTimeout(() => {}, 30000)`], { stdio: "ignore" });
}
async function waitBusy(port: number): Promise<void> {
  const deadline = Date.now() + 3000;
  while (Date.now() < deadline) {
    if (await server.isPortInUse(port)) return;
    await new Promise((r) => setTimeout(r, 50));
  }
}

test("isPortInUse and killProcessOnPort", async () => {
  const port = 5898;
  assert.ok(!(await server.isPortInUse(port)));
  const proc = occupy(port);
  try {
    await waitBusy(port);
    assert.ok(await server.isPortInUse(port), "test process should be occupying the port");
    server.cfg.logRequests = false;
    assert.equal(await server.killProcessOnPort(port, 2.0), true);
    assert.ok(!(await server.isPortInUse(port)), "port should now be free");
  } finally {
    proc.kill();
  }
});

test("createServer keeps its port and kills the stale session", async () => {
  const port = 5899;
  const proc = occupy(port);
  try {
    await waitBusy(port);
    assert.ok(await server.isPortInUse(port));
    const running = await server.createServer({ host: "0.0.0.0", port });
    try {
      assert.equal(running.port, port);
    } finally {
      await new Promise((r) => running.server.close(r));
    }
  } finally {
    proc.kill();
  }
});

test("api action set_role_counts", async () => {
  const gm = new GameManager({ seedSamples: true });
  for (let i = 5; i < 9; i++) gm.addPlayer(`ServerPlayer_${i}`, `sp_${i}`);
  await withServer(gm, async (s) => {
    const data = (await s.action({ action: "set_role_counts", guesser_count: 2, truth_teller_count: 2, apply_now: true })).json;
    assert.equal(data.target_guesser_count, 2);
    assert.equal(data.target_truth_teller_count, 2);
    assert.equal(data.guesser_ids.length, 2);
    assert.equal(data.truth_teller_ids.length, 2);
  });
});

test("api action set_voting_guesser", async () => {
  const gm = new GameManager({ seedSamples: true });
  for (let i = 5; i < 9; i++) gm.addPlayer(`ServerPlayer_${i}`, `sp_${i}`);
  gm.setRoleCounts(2, 2, true);
  gm.assignRoundRoles();
  const consultant = gm.guesserIds.find((g) => g !== gm.votingGuesserId)!;
  await withServer(gm, async (s) => {
    const data = (await s.action({ action: "set_voting_guesser", player_id: consultant })).json;
    assert.equal(data.voting_guesser_id, consultant);
    assert.equal(data.guesser_id, consultant);
  });
});

test("api action: a non-voting guesser's vote is forbidden", async () => {
  const gm = new GameManager({ seedSamples: true });
  for (let i = 5; i < 8; i++) gm.addPlayer(`ServerPlayer_${i}`, `sp_${i}`);
  gm.setRoleCounts(2, 1, true);
  gm.assignRoundRoles();
  const voter = gm.votingGuesserId!;
  const consultant = gm.guesserIds.find((g) => g !== voter)!;
  const tt = gm.truthTellerIds[0]!;
  await withServer(gm, async (s) => {
    const bad = await s.action({ action: "cast_vote", voter_id: consultant, target_id: tt });
    assert.ok(bad.text.includes("error") && bad.text.toLowerCase().includes("voting guesser"));
    const good = (await s.action({ action: "cast_vote", voter_id: voter, target_id: tt })).json;
    assert.equal(good.phase, "reveal");
    assert.equal(good.last_results.is_correct, true);
  });
});

test("admin dashboard has role count inputs", () => {
  const html = templates.getAdminHtml(5050, "192.168.1.10");
  for (const want of ["admin-guesser-count", "admin-truth-count", "updateRoleCounts", "Lead Guesser (Designated Voter)"]) assert.ok(html.includes(want), want);
});

test("api action set_guessers (multi)", async () => {
  const gm = new GameManager({ seedSamples: true });
  for (let i = 5; i < 9; i++) gm.addPlayer(`ServerPlayer_${i}`, `sp_${i}`);
  const ids = gm.players.map((p) => p.id);
  const targets = [ids[0], ids[1]];
  await withServer(gm, async (s) => {
    const data = (await s.action({ action: "set_guessers", player_ids: targets, voter_id: targets[1] })).json;
    assert.deepEqual(new Set(data.guesser_ids), new Set(targets));
    assert.equal(data.voting_guesser_id, targets[1]);
    assert.equal(data.target_guesser_count, 2);
  });
});

test("api action set_truth_tellers (multi)", async () => {
  const gm = new GameManager({ seedSamples: true });
  for (let i = 5; i < 9; i++) gm.addPlayer(`ServerPlayer_${i}`, `sp_${i}`);
  const ids = gm.players.map((p) => p.id);
  const targets = [ids[2], ids[3]];
  await withServer(gm, async (s) => {
    const data = (await s.action({ action: "set_truth_tellers", player_ids: targets })).json;
    assert.deepEqual(new Set(data.truth_teller_ids), new Set(targets));
    assert.equal(data.target_truth_teller_count, 2);
  });
});

test("admin dashboard has the multi-select role assignment elements", () => {
  const html = templates.getAdminHtml(5050, "192.168.1.10");
  for (const want of ["role-multi-select", "admin-guesser-select-holder", "admin-truth-select-holder", "onGuesserMultiChange", "onTruthTellerMultiChange", "chooseLeadVoter", "attachToggleBehavior", "admin-lead-voter-subcard"]) assert.ok(html.includes(want), want);
});

test("the default game manager boots with zero players", () => {
  const gm = new GameManager();
  assert.equal(gm.players.length, 0);
  assert.deepEqual(gm.guesserIds, []);
  assert.equal(gm.votingGuesserId, null);
  assert.deepEqual(gm.truthTellerIds, []);
});

test("api action: multi truth teller voting", async () => {
  const gm = new GameManager({ seedSamples: true });
  for (let i = 5; i < 8; i++) gm.addPlayer(`ServerPlayer_${i}`, `sp_${i}`);
  gm.setRoleCounts(1, 2, true);
  gm.assignRoundRoles();
  const voter = gm.votingGuesserId!;
  const [tt1, tt2] = gm.truthTellerIds as [string, string];
  const liar = gm.players.find((p) => p.role === "liar")!;
  const name = (id: string) => gm.players.find((p) => p.id === id)!.name;
  await withServer(gm, async (s) => {
    for (const p of gm.players) p.score = 0;
    const d1 = (await s.action({ action: "cast_vote", voter_id: voter, target_ids: [tt1, tt2] })).json;
    assert.equal(d1.phase, "reveal");
    assert.equal(d1.last_results.is_correct, true);
    const sc1 = d1.last_results.score_changes;
    assert.deepEqual([sc1[name(voter)], sc1[name(tt1)], sc1[name(tt2)], sc1[liar.name]], [1, 1, 1, 0]);

    for (const p of gm.players) p.score = 0;
    gm.phase = "voting";
    const d2 = (await s.action({ action: "cast_vote", voter_id: voter, target_ids: [tt1, liar.id] })).json;
    assert.equal(d2.last_results.is_correct, false);
    const sc2 = d2.last_results.score_changes;
    assert.deepEqual([sc2[name(voter)], sc2[name(tt1)], sc2[liar.name], sc2[name(tt2)]], [0, 1, 1, 0]);
  });
});

test("admin dashboard shows truths and lies used separately", () => {
  const html = templates.getAdminHtml(5050, "192.168.1.10");
  assert.ok(!html.includes("statements-used-card") && !html.includes("Statements Used History"));
  for (const want of ["Topic History:", "used-truth-count", "total-truth-count", "used-lies-count", "total-lies-count", "used-topics-count", "total-topics-count", "Truth:", "Lies:", "clearTopicHistory", "toggleTopicHistoryDetails", "topic-history-drawer", "renderTopicHistoryDrawer"]) assert.ok(html.includes(want), want);
});

test("admin dashboard live terminal and server logs card", () => {
  const html = templates.getAdminHtml(5050, "192.168.1.10");
  for (const want of ["Live Terminal & Server Logs", 'id="logs-card"', 'id="logs-list"', 'id="logs-count"', ".logs-console", ".log-entry", ".log-badge", ".log-action", ".log-info", ".log-warn", 'logsContainer = document.getElementById("logs-list")', "state.logs", "logsUserScrolled"]) assert.ok(html.includes(want), want);
});

test("clear_logs action", async () => {
  const gm = new GameManager({ seedSamples: false });
  gm.log("Test log entry 1");
  gm.log("Test log entry 2");
  assert.ok(gm.logs.length >= 3);
  await withServer(gm, async (s) => {
    const out = (await s.action({ action: "clear_logs" })).json;
    assert.equal(out.logs.length, 1);
    assert.ok(out.logs[0].message.toLowerCase().includes("cleared"));
  });
});

test("notable HTTP requests are recorded in the game log", () => {
  const gm = new GameManager({ seedSamples: false });
  server.logRequest(gm, "GET /join HTTP/1.1", "200");
  assert.ok(gm.logs.some((l) => l.message.includes("HTTP: GET /join HTTP/1.1 -> 200")));
  server.logRequest(gm, "GET /api/state?role=admin HTTP/1.1", "200");
  assert.ok(!gm.logs.some((l) => l.message.includes("/api/state")));
});

test("the server enforces the minimum role requirements to start", async () => {
  const gm = new GameManager({ seedSamples: false });
  gm.addPlayer("Player 1");
  gm.addPlayer("Player 2");
  await withServer(gm, async (s) => {
    const r1 = await s.action({ action: "set_phase", phase: "setup" });
    assert.equal(r1.status, 400);
    assert.ok(r1.json.error.toLowerCase().includes("at least 1"));
    assert.equal(gm.phase, "lobby");

    const r2 = await s.action({ action: "next_phase" });
    assert.equal(r2.status, 400);
    assert.ok("error" in r2.json);
    assert.equal(gm.phase, "lobby");

    gm.addPlayer("Player 3");
    gm.setRoleCounts(2, 1);
    const r3 = await s.action({ action: "set_phase", phase: "setup" });
    assert.equal(r3.status, 400);
    assert.ok(r3.json.error.toLowerCase().includes("at least 1 liar"));
    assert.equal(gm.phase, "lobby");

    gm.setRoleCounts(1, 1);
    const r4 = await s.action({ action: "set_phase", phase: "setup" });
    assert.equal(r4.status, 200);
    assert.equal(r4.json.phase, "setup");
    assert.equal(gm.phase, "setup");
  });
});

test("the server blocks advance and previous phases at round end", async () => {
  const gm = new GameManager({ seedSamples: true });
  gm.setPhase("setup");
  gm.setPhase("voting");
  gm.setPhase("reveal");
  await withServer(gm, async (s) => {
    const r1 = await s.action({ action: "next_phase" });
    assert.equal(r1.status, 400);
    assert.ok(/completed|disabled/.test(r1.json.error.toLowerCase()));
    assert.equal(gm.phase, "reveal");

    const r2 = await s.action({ action: "set_phase", phase: "questioning" });
    assert.equal(r2.status, 400);
    assert.equal(gm.phase, "reveal");

    const r3 = await s.action({ action: "next_round" });
    assert.equal(r3.status, 200);
    assert.equal(r3.json.phase, "setup");
    assert.equal(gm.roundNumber, 2);

    gm.setPhase("reveal");
    const r4 = await s.action({ action: "reset_game" });
    assert.equal(r4.status, 200);
    assert.equal(r4.json.phase, "lobby");
    assert.equal(gm.phase, "lobby");
  });
});

test("join page: streamlined phone presentation", () => {
  const html = templates.getJoinHtml(5050);
  for (const want of ["player-bar", "team-banner", "goal-pill", "facts-drawer", "leaderboard-card", "leader-row", "verdict-card", "toggleDrawer", "<details", "<summary", "detailsFoldState", "recordToggle", "tt-facts-drawer", "lie-facts-drawer", "renderedHtml"]) assert.ok(html.includes(want), want);
  for (const bad of ["You have NOT been assigned any topic or statement", "Interrogation & Deliberation in Progress", "You have NO detailed facts description!", "Consensus Deliberation Time"]) assert.ok(!html.includes(bad), bad);
});

test("the archive serves offline copies but nothing outside it", async () => {
  const dir = mkdtempSync(join(tmpdir(), "archive-"));
  writeFileSync(join(dir, "paper.pdf"), "%PDF-1.4 x");
  writeFileSync(join(dir, "secret.key"), "no");
  const old = server.cfg.archiveDir;
  server.cfg.archiveDir = dir;
  try {
    await withServer(null, async (s) => {
      const r = await s.get("/archive/paper.pdf");
      assert.equal(r.status, 200);
      assert.equal(r.text, "%PDF-1.4 x");
      assert.equal(r.headers.get("content-type"), "application/pdf");
      for (const bad of ["/archive/secret.key", "/archive/../src/server.ts", "/archive/%2e%2e/%2e%2e/etc/passwd"]) {
        const b = await s.get(bad);
        assert.equal(b.status, 404, bad);
        assert.notEqual(b.text, "no");
      }
    });
  } finally {
    server.cfg.archiveDir = old;
    rmSync(dir, { recursive: true, force: true });
  }
});

test("request body limits and bad JSON", () => withServer(null, async (s) => {
  assert.equal((await s.post("/api/action", "")).status, 400);
  assert.equal((await s.post("/api/action", "{not json")).status, 400);
  assert.equal((await s.action({ action: "nope" })).status, 400);
  assert.equal((await s.get("/nowhere")).status, 404);
}));
