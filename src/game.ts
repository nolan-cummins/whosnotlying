/**
 * Game logic and state management for "Who's Not Lying?" (One of These People Is Not Lying).
 *
 * - Dedicated guesser(s) assigned at round start who get no clues; one designated voter accuses.
 * - Unique topics per suspect; only truth tellers hold a true statement plus detailed facts.
 * - Roles can be set directly from the admin console without re-randomising.
 * - Phases are untimed; only the voting guesser can accuse.
 * - Players and the used-topic history persist on disk (see accounts.ts).
 */
import { randomBytes, timingSafeEqual } from "node:crypto";
import { writeFileSync } from "node:fs";
import { join as joinPath } from "node:path";
import { fileURLToPath } from "node:url";
import * as accounts from "./accounts.ts";
import type { Settings, UsedStatement } from "./accounts.ts";
import * as match from "./match.ts";
import * as packs from "./packs.ts";
import type { LibraryTopic, Need, Source } from "./packs.ts";
import { choice, randint, shuffle, weightedChoice } from "./rng.ts";

const here = fileURLToPath(new URL(".", import.meta.url));

export const cfg = {
  playersFile: joinPath(here, "..", "players.json"),
};

export function setPlayersFile(path: string): void {
  cfg.playersFile = path;
}

export const NEED_NEW_PASSWORD = "That was a temporary password. Choose a new one (4+ characters).";

export type Phase = "lobby" | "setup" | "questioning" | "voting" | "reveal";
export type Role = "guesser" | "truth_teller" | "liar";
export type RoleMode = "one_liar" | "custom" | "one_truth";
export type LogLevel = "INFO" | "ACTION" | "WARN";

export interface Player {
  id: string;
  name: string;
  score: number;
  role: Role;
  is_voting_guesser?: boolean;
  topic: string | null;
  category: string | null;
  statement: string | null;
  detailed_description: string | null;
  voted_for: string | string[] | null;
  tags?: string[];
  expertise?: string;
  token?: string;
  account_id?: string;
  pw_hash?: string;
  salt?: string;
  debt?: Record<Role, number>;
  last_role?: Role;
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
}

export interface RoleCounts {
  players: number;
  guessers: number;
  truth_tellers: number;
  liars: number;
  min_required_players: number;
}

export interface Standing {
  rank: number;
  id: string;
  name: string;
  score: number;
  role: string;
  pts_gained: number;
}

export interface RoundResults {
  guesser: { id: string; name: string; voted_for: string | string[] | null } | null;
  guessers: { id: string; name: string; is_voting_guesser: boolean; voted_for: string | string[] | null }[];
  truth_teller: TruthTellerResult | null;
  truth_tellers: TruthTellerResult[];
  liars: { id: string; name: string; topic: string | null; false_statement: string | null }[];
  picked_player: PickedResult | null;
  picked_players: PickedResult[];
  is_correct: boolean;
  score_changes: Record<string, number>;
  standings: Standing[];
}

export interface TruthTellerResult {
  id: string;
  name: string;
  topic: string | null;
  true_statement: string | null;
  detailed_description: string | null;
}

export interface PickedResult {
  id: string;
  name: string;
  role: string;
  is_truth_teller: boolean;
  topic: string | null;
}

export interface PlayerView {
  id: string;
  name: string;
  score: number;
  voted_for: string | string[] | null;
  is_guesser: boolean;
  is_voting_guesser: boolean;
  account?: boolean;
  role: string;
  is_truth_teller: boolean | null;
  topic: string | null;
  category: string | null;
  statement: string | null;
  detailed_description: string | null;
  source?: Source | null;
  lie_facts?: string[];
}

export interface MyInfo {
  id: string;
  name: string;
  role: Role;
  is_guesser: boolean;
  is_voting_guesser: boolean;
  voting_guesser_name: string | null;
  fellow_guessers: string[];
  is_truth_teller: boolean;
  topic: string | null;
  category: string | null;
  statement: string | null;
  detailed_description: string | null;
  lie_facts: string[];
  source: Source | { redacted: true } | null;
  match_pct: number | null;
  tag_order: string[];
  permanent: boolean;
  tags: string[];
  expertise: string;
  has_password: boolean;
}

export interface CurrentStatement {
  player_id: string;
  player_name: string;
  topic: string | null;
  category: string | null;
  statement: string | null;
  detailed_description?: string | null;
}

export interface GameState {
  phase: Phase;
  round: number;
  role_requirements: { valid: boolean; error: string | null } & RoleCounts;
  guesser_id: string | null;
  guesser_name: string;
  voting_guesser_id: string | null;
  voting_guesser_name: string;
  guesser_ids: string[];
  target_guesser_count: number;
  target_truth_teller_count: number;
  truth_teller_count: number;
  role_mode: RoleMode;
  ready_ids: string[];
  can_ready: boolean;
  truth_teller_id: string | null;
  truth_teller_name: string;
  truth_teller_ids: string[];
  players: PlayerView[];
  my_info: MyInfo | null;
  standings: Standing[];
  last_results: RoundResults | null;
  used_topics_count: number;
  blocked_topics_count: number;
  settings: Settings;
  all_tags: string[];
  match_status: (match.Status & { profiles: number }) | null;
  accounts: accounts.AccountRow[];
  total_topics_count: number;
  packs: packs.PackSummary[];
  used_true_statements: UsedStatement[];
  used_false_statements: UsedStatement[];
  current_true_statements: CurrentStatement[];
  current_false_statements: CurrentStatement[];
  used_true_count: number;
  used_false_count: number;
  used_truth_count: number;
  used_lies_count: number;
  total_true_count: number;
  total_false_count: number;
  total_truth_count: number;
  total_lies_count: number;
  logs: LogEntry[];
  // set by the server after a join
  joined_player_id?: string;
  joined_player_name?: string;
  token?: string;
  [extra: string]: unknown;
}

export interface JoinResult {
  player: Player | null;
  error: string | null;
}

export function findTopicData(topicName: string | null | undefined): LibraryTopic | null {
  if (!topicName) return null;
  const want = topicName.toLowerCase();
  return packs.library().find((t) => t.topic.toLowerCase() === want) ?? null;
}

const PHASES: Phase[] = ["lobby", "setup", "questioning", "voting", "reveal"];
const ROLES: Role[] = ["guesser", "truth_teller", "liar"];
const DEFAULT_PLAYER_NAMES = new Set(["alice", "bob", "charlie", "diana", "player 1", "player 2", "player 3", "player 4", "player 5", "player 6"]);

const now = (): number => Date.now() / 1000;
const stamp = (): string => new Date().toTimeString().slice(0, 8);
const sameToken = (a: string, b: string): boolean => {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
};
const byName = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0);

export interface GameManagerOptions {
  seedSamples?: boolean;
  playersFile?: string;
}

export class GameManager {
  playersFile: string;
  phase: Phase = "lobby";
  roundNumber = 1;
  players: Player[] = [];
  guesserIds: string[] = [];
  votingGuesserId: string | null = null;
  truthTellerIds: string[] = [];
  targetGuesserCount = 1;
  targetTruthTellerCount = 1;
  roleMode: RoleMode = "custom";
  readyIds = new Set<string>();
  logs: LogEntry[] = [];
  usedTopicIds: string[] = []; // topics dealt this session (until resetGame)
  usedStatements: UsedStatement[];
  gameId: number; // tags archive entries; round numbers restart each game
  lastRoundResults: RoundResults | null = null;
  lastActivity: number; // any player/admin action; an hour of silence ends the game

  constructor(opts: GameManagerOptions = {}) {
    this.playersFile = opts.playersFile ?? cfg.playersFile;
    if (!accounts.hasHistoryFile()) accounts.initHistory(packs.legacyUsedKeys());
    this.usedStatements = accounts.loadArchive();
    this.gameId = Date.now();
    this.lastActivity = now();

    // The default is to start without any player in the lobby; the test bench simulates players joining.
    if (opts.seedSamples) {
      this.seedSamplePlayers();
    } else {
      this.players = [];
      this.guesserIds = [];
      this.votingGuesserId = null;
      this.truthTellerIds = [];
      this.savePlayers();
    }

    this.log("Server initialized. Welcome to 'One of These People Is Not Lying'!", "INFO");
    if (this.players.length) {
      const overlap = this.guesserIds.some((g) => this.truthTellerIds.includes(g));
      if (this.players.length >= 2 && (!this.guesserIds.length || !this.truthTellerIds.length || overlap)) this.assignRoundRoles();
      else if (this.players.length >= 2) this.ensureAllSuspectsHaveContent();
      this.recordUsedStatements();
    }
  }

  get guesserId(): string | null {
    return this.votingGuesserId;
  }

  set guesserId(val: string | null) {
    this.votingGuesserId = val;
    if (val !== null) {
      if (!this.guesserIds.includes(val)) this.guesserIds = [val, ...this.guesserIds.filter((g) => g !== val)];
    } else this.guesserIds = [];
  }

  get truthTellerId(): string | null {
    return this.truthTellerIds[0] ?? null;
  }

  set truthTellerId(val: string | null) {
    if (val !== null) {
      if (!this.truthTellerIds.includes(val)) this.truthTellerIds = [val, ...this.truthTellerIds.filter((t) => t !== val)];
    } else this.truthTellerIds = [];
  }

  get votingGuesserName(): string {
    return this.player(this.votingGuesserId)?.name ?? "None";
  }

  get guesserName(): string {
    return this.votingGuesserName;
  }

  get truthTellerName(): string {
    return this.player(this.truthTellerId)?.name ?? "None";
  }

  player(id: string | null | undefined): Player | null {
    if (id === null || id === undefined) return null;
    return this.players.find((p) => p.id === id) ?? null;
  }

  private accountIds(): string[] {
    return this.players.map((p) => p.account_id).filter((a): a is string => Boolean(a));
  }

  /** Topics not to deal: this session's, plus the global / present accounts' history. */
  blocked(): Set<string> {
    return new Set([...this.usedTopicIds, ...accounts.blockedTopics(this.accountIds())]);
  }

  /** Statements are live (questioning onwards): everyone present has now heard them. */
  private recordHistory(): void {
    const keys: string[] = [];
    for (const p of this.players) {
      const t = findTopicData(p.topic);
      if (t && (p.role === "truth_teller" || p.role === "liar")) keys.push(packs.statementKey(t, p.statement) || t.id + ":?");
    }
    try {
      accounts.record(keys, this.accountIds());
    } catch (e) {
      this.log(`Warning: could not save topic history: ${String(e)}`, "WARN");
    }
  }

  /** Seeds sample players only when explicitly requested (unit test fixtures). */
  private seedSamplePlayers(): boolean {
    const mk = (id: string, name: string, role: Role, voter = false): Player => ({
      id, name, score: 0, role, is_voting_guesser: voter, topic: null, category: null, statement: null, detailed_description: null, voted_for: null,
    });
    this.players = [mk("p1", "Alice", "guesser", true), mk("p2", "Bob", "liar"), mk("p3", "Charlie", "truth_teller"), mk("p4", "Diana", "liar")];
    this.guesserIds = ["p1"];
    this.votingGuesserId = "p1";
    this.truthTellerIds = ["p3"];
    this.targetGuesserCount = 1;
    this.targetTruthTellerCount = 1;
    this.savePlayers();
    return true;
  }

  private savePlayers(): void {
    if (this.playersFile === ":memory:") return;
    try {
      const toSave = this.players.map((p) => ({
        id: p.id,
        name: p.name,
        score: p.score ?? 0,
        role: p.role ?? "liar",
        is_voting_guesser: p.id === this.votingGuesserId,
        topic: p.topic ?? null,
        category: p.category ?? null,
        statement: p.statement ?? null,
        detailed_description: p.detailed_description ?? null,
        voted_for: p.voted_for ?? null,
        tags: p.tags ?? [],
        expertise: p.expertise ?? "",
      }));
      writeFileSync(this.playersFile, JSON.stringify(toSave, null, 2), "utf-8");
    } catch (e) {
      this.log(`Warning: could not save players: ${String(e)}`, "WARN");
    }
  }

  /** A random unplayed topic; need="truth"/"lie" keeps to topics that have that side. */
  private getUnusedTopic(excludeTopics: string[] = [], need: Need = null): LibraryTopic {
    const exclude = new Set(excludeTopics);
    const blocked = this.blocked();
    const library = packs.library();
    const lib = library.filter((t) => packs.hasSide(t, need));
    const pool = lib.length ? lib : library;
    const groups = new Set(library.filter((t) => exclude.has(t.topic) && t.group).map((t) => t.group as string)); // one paper per round
    let available = pool.filter((t) => !blocked.has(t.id) && !exclude.has(t.topic) && !(t.group && groups.has(t.group)));
    if (!available.length) {
      this.log("Topic pool exhausted for this lobby: reusing played topics.", "WARN");
      available = pool.filter((t) => !exclude.has(t.topic));
    }
    if (!available.length) available = pool;
    const chosen = choice(available);
    if (!this.usedTopicIds.includes(chosen.id)) this.usedTopicIds.push(chosen.id);
    return chosen;
  }

  /**
   * Fill a suspect's topic + statement for their role, keeping their current topic if it has that side.
   * Packs may hold truth-only and lie-only items, so every role change goes through here.
   */
  private give(p: Player, role: Role, taken?: Set<string>): void {
    const need: Need = role === "truth_teller" ? "truth" : "lie";
    const used = taken ?? new Set(this.players.filter((x) => x !== p && x.topic).map((x) => x.topic as string));
    let t = findTopicData(p.topic);
    if (!t || !packs.hasSide(t, need) || (p.topic && used.has(p.topic))) t = this.getUnusedTopic([...used], need);
    p.topic = t.topic;
    p.category = t.category;
    if (!this.usedTopicIds.includes(t.id)) this.usedTopicIds.push(t.id);
    if (need === "truth") {
      p.statement = t.true_statement;
      p.detailed_description = t.true_description;
    } else {
      if (!p.statement || !t.false_statements.includes(p.statement)) p.statement = packs.getRandomFalseStatement(t);
      p.detailed_description = null;
    }
  }

  setPacks(packIds: string[]): boolean {
    if (!packs.setSelected(packIds)) return false;
    this.log(`Topic packs enabled: ${packIds.join(", ")}`, "ACTION");
    return true;
  }

  clearTopicHistory(): void {
    this.usedTopicIds = [];
    this.usedStatements = [];
    accounts.saveArchive([]);
    accounts.resetGlobal();
    this.log("Global topic history cleared by Admin. All topics re-enabled!", "ACTION");
  }

  private recordUsedStatements(): void {
    if (this.phase === "questioning" || this.phase === "voting" || this.phase === "reveal") this.recordHistory();
    // Refresh the current round's statements to match the active players
    this.usedStatements = this.usedStatements.filter((s) => !(s.game === this.gameId && s.round === this.roundNumber));
    for (const p of this.players) {
      if (!p.statement || !p.topic) continue;
      if (p.role === "truth_teller") {
        this.usedStatements.push({
          type: "true", game: this.gameId, round: this.roundNumber, player_id: p.id, player_name: p.name,
          topic: p.topic, category: p.category, statement: p.statement, detailed_description: p.detailed_description,
        });
      } else if (p.role === "liar") {
        this.usedStatements.push({
          type: "false", game: this.gameId, round: this.roundNumber, player_id: p.id, player_name: p.name,
          topic: p.topic, category: p.category, statement: p.statement,
        });
      }
    }
    try {
      accounts.saveArchive(this.usedStatements);
    } catch (e) {
      this.log(`Warning: could not save the statements archive: ${String(e)}`, "WARN");
    }
  }

  log(message: string, level: LogLevel = "INFO"): void {
    this.logs.push({ timestamp: stamp(), level, message });
    if (this.logs.length > 250) this.logs.shift();
  }

  clearLogs(): void {
    this.logs.length = 0;
    this.log("Server event log cleared by host.", "INFO");
  }

  addPlayer(name: string, playerId?: string | null): Player {
    let cleanName = name.trim();
    if (!cleanName) cleanName = `Player ${this.players.length + 1}`;

    if (playerId) {
      const existing = this.player(playerId);
      if (existing) {
        existing.name = cleanName;
        this.ensureAllSuspectsHaveContent();
        this.savePlayers();
        this.log(`Player reconnected: ${cleanName} (ID: ${playerId})`, "ACTION");
        return existing;
      }
    }

    const existingByName = this.players.find((p) => p.name.toLowerCase() === cleanName.toLowerCase());
    if (existingByName) {
      if (playerId) existingByName.id = playerId;
      this.ensureAllSuspectsHaveContent();
      this.savePlayers();
      this.log(`Player re-joined: ${cleanName} (ID: ${existingByName.id})`, "ACTION");
      return existingByName;
    }

    const pid = playerId || `p_${Date.now() % 1000000}_${randint(10, 99)}`;
    const newPlayer: Player = { id: pid, name: cleanName, score: 0, role: "liar", topic: null, category: null, statement: null, detailed_description: null, voted_for: null };
    this.players.push(newPlayer);

    // Assign a unique topic for the new suspect
    this.give(newPlayer, "liar");

    if (!this.guesserIds.length || !this.truthTellerIds.length) this.assignRoundRoles();
    else this.ensureAllSuspectsHaveContent();

    this.savePlayers();
    this.log(`Player joined: ${cleanName} (ID: ${pid})`, "ACTION");
    return newPlayer;
  }

  syncPlayer(playerId: string, name: string): Player {
    return this.addPlayer(name, playerId);
  }

  /** After an admin reset the temporary password works once: the player must pick their own. */
  private renewPassword(acct: accounts.Account, password: string, newPassword: string): string | null {
    if (!acct.must_change || !accounts.checkPassword(password, acct.pw_hash, acct.salt)) return null;
    if ((newPassword || "").length < 4) return NEED_NEW_PASSWORD;
    accounts.setPassword(acct.id, newPassword);
    this.log(`Password changed after reset: ${acct.name}`, "ACTION");
    return null;
  }

  /** Player self-service join / re-login. Returns {player} or {error}. */
  join(name: string, password = "", permanent = false, token = "", newPassword = ""): JoinResult {
    name = (name || "").trim().slice(0, 24);
    if (!name) return { player: null, error: "Enter a name." };
    const p = this.players.find((x) => x.name.toLowerCase() === name.toLowerCase());
    if (p) {
      // re-login to an in-game player
      const acct = p.account_id ? accounts.accountById(p.account_id) : null;
      const ok =
        (token && p.token && sameToken(token, p.token)) ||
        (acct && accounts.checkPassword(password, acct.pw_hash, acct.salt)) ||
        (p.pw_hash && accounts.checkPassword(password, p.pw_hash, p.salt)) ||
        (!p.token && !acct && !p.pw_hash); // admin-added, unclaimed
      if (!ok) return { player: null, error: acct || p.pw_hash ? "That name is taken. Enter its password to log back in." : "That name is already in the game." };
      const err = acct ? this.renewPassword(acct, password, newPassword) : null;
      if (err) return { player: null, error: err };
      p.token = p.token || randomBytes(18).toString("base64url");
      this.log(`Player logged back in: ${p.name}`, "ACTION");
      return { player: p, error: null };
    }
    let acct = accounts.getAccount(name);
    if (acct) {
      if (!accounts.checkPassword(password, acct.pw_hash, acct.salt)) return { player: null, error: "A saved account uses that name. Wrong password." };
      const err = this.renewPassword(acct, password, newPassword);
      if (err) return { player: null, error: err };
    } else if (permanent) {
      if ((password || "").length < 4) return { player: null, error: "Permanent accounts need a password (4+ characters)." };
      acct = accounts.createAccount(name, password);
      this.log(`Permanent account created: ${acct.name}`, "ACTION");
    }
    const player = this.addPlayer(acct ? acct.name : name);
    player.token = randomBytes(18).toString("base64url");
    if (acct) {
      player.account_id = acct.id;
      player.tags ??= acct.tags ?? [];
      player.expertise ??= acct.expertise ?? "";
      // Their history now applies: re-deal anything they've already seen.
      const seen = accounts.blockedTopics([acct.id]);
      const t = findTopicData(player.topic);
      if (t && seen.has(t.id) && this.phase === "lobby") {
        player.topic = null;
        this.ensureAllSuspectsHaveContent();
      }
    } else if (password) {
      [player.pw_hash, player.salt] = accounts.hashPassword(password);
    }
    return { player, error: null };
  }

  /** A player's interests: tags from the packs' vocabulary, plus free-text expertise for embeddings. */
  setProfile(playerId: string, tags: unknown[], expertise: string): boolean {
    const p = this.player(playerId);
    if (!p) return false;
    const clean: string[] = []; // pack tags or the player's own; matching is by meaning, so any phrase works
    for (const raw of tags ?? []) {
      const t = String(raw).split(/\s+/).filter(Boolean).join(" ").slice(0, 32);
      if (t && !clean.some((c) => c.toLowerCase() === t.toLowerCase())) clean.push(t);
    }
    p.tags = clean.slice(0, 40);
    p.expertise = String(expertise ?? "").trim().slice(0, 600);
    if (p.account_id) accounts.setProfile(p.account_id, p.tags, p.expertise);
    match.warm([match.queryText(p.expertise), ...p.tags.map(match.tagText)]);
    this.savePlayers();
    return true;
  }

  playerForToken(playerId: string, token: string | null | undefined): Player | null {
    const p = this.player(playerId);
    if (p && token && p.token && sameToken(String(token), p.token)) return p;
    return null;
  }

  removePlayer(playerId: string): boolean {
    const player = this.player(playerId);
    if (!player) return false;
    this.players = this.players.filter((p) => p.id !== playerId);
    this.guesserIds = this.guesserIds.filter((g) => g !== playerId);
    if (this.votingGuesserId === playerId) this.votingGuesserId = this.guesserIds[0] ?? null;
    this.truthTellerIds = this.truthTellerIds.filter((t) => t !== playerId);
    this.readyIds.delete(playerId);

    this.log(`Player removed: ${player.name}`, "ACTION");
    if (this.players.length) {
      if (!this.guesserIds.length || !this.truthTellerIds.length) this.assignRoundRoles();
      else {
        this.ensureAllSuspectsHaveContent();
        this.savePlayers();
      }
    } else {
      this.guesserIds = [];
      this.votingGuesserId = null;
      this.truthTellerIds = [];
      this.savePlayers();
    }
    this.advanceIfAllReady();
    return true;
  }

  /**
   * Randomises roles and unique topics for all players from targetGuesserCount and targetTruthTellerCount:
   * guessers get no clues (one designated voter accuses, the others deliberate), truth tellers get a unique
   * topic with the true statement and facts, everyone else is a liar with a unique topic and a false statement.
   */
  assignRoundRoles({ roles = true, topics = true }: { roles?: boolean; topics?: boolean } = {}): void {
    if (!this.players.length) {
      this.guesserIds = [];
      this.votingGuesserId = null;
      this.truthTellerIds = [];
      return;
    }

    const total = this.players.length;
    let gCount: number;
    let ttCount: number;
    if (total >= 2) {
      gCount = Math.max(1, Math.min(this.targetGuesserCount, total - 1));
      ttCount = Math.max(1, Math.min(this.targetTT(total, gCount), total - gCount));
    } else {
      gCount = 1;
      ttCount = 0;
    }

    if (!roles && this.guesserIds.length && this.truthTellerIds.length) {
      gCount = this.guesserIds.length;
      ttCount = this.truthTellerIds.length;
    } else if (accounts.settings().fair_roles && total >= 3) {
      [this.guesserIds, this.truthTellerIds] = this.fairDeal(gCount, ttCount);
      this.votingGuesserId = choice(this.guesserIds);
    } else {
      const shuffled = shuffle([...this.players]);
      this.guesserIds = shuffled.slice(0, gCount).map((p) => p.id);
      this.votingGuesserId = this.guesserIds[0] ?? null;
      this.truthTellerIds = shuffled.slice(gCount, gCount + ttCount).map((p) => p.id);
    }

    const suspects = this.players.filter((p) => !this.guesserIds.includes(p.id));

    let dealt: Map<string, LibraryTopic> | null = topics ? new Map() : null; // roles only: suspects keep their topic when it has their new side
    const blocked = topics ? this.blocked() : new Set<string>();
    const library = packs.library();
    let unused = library.filter((t) => !blocked.has(t.id));
    if (topics && unused.length < suspects.length) {
      this.log("Topic pool exhausted for this lobby: reusing played topics.", "WARN");
      unused = library.filter((t) => !this.usedTopicIds.includes(t.id));
      if (!unused.length) unused = library;
    }

    // Weighted by each player's tags / expertise when the admin turned matching on; plain random otherwise.
    // Two passes: truth tellers from items with a truth, then liars from items with a lie (packs may hold one-sided items).
    const mode = accounts.settings().match_mode ?? "off";
    const tts = suspects.filter((p) => this.truthTellerIds.includes(p.id));
    for (const p of this.players) {
      // clear last round's topics so they don't block this round's deal
      if (topics || this.guesserIds.includes(p.id)) p.topic = null;
    }
    if (topics) {
      dealt = match.deal(tts, unused.filter((t) => packs.hasSide(t, "truth")), mode);
      const taken = new Set<string>();
      for (const t of dealt.values()) {
        taken.add(t.id);
        if (t.group) taken.add(t.group);
      }
      const liars = suspects.filter((p) => !tts.includes(p));
      for (const [pid, t] of match.deal(liars, unused.filter((t) => packs.hasSide(t, "lie") && !taken.has(t.id) && !(t.group && taken.has(t.group))), mode)) dealt.set(pid, t);
    }

    for (const p of this.players) {
      p.voted_for = null;
      if (this.guesserIds.includes(p.id)) {
        p.role = "guesser";
        p.is_voting_guesser = p.id === this.votingGuesserId;
        p.topic = null;
        p.category = null;
        p.statement = null;
        p.detailed_description = null;
      } else if (this.truthTellerIds.includes(p.id)) {
        p.role = "truth_teller";
        p.is_voting_guesser = false;
        if (dealt !== null) {
          p.topic = dealt.get(p.id)?.topic ?? null;
          p.statement = null;
        }
        this.give(p, "truth_teller");
      } else {
        p.role = "liar";
        p.is_voting_guesser = false;
        if (dealt !== null) {
          p.topic = dealt.get(p.id)?.topic ?? null;
          p.statement = null;
        }
        this.give(p, "liar");
      }
    }

    this.ensureAllSuspectsHaveContent();
    this.savePlayers();

    const voterName = this.player(this.votingGuesserId)?.name ?? "None";
    const ttNames = this.players.filter((p) => this.truthTellerIds.includes(p.id)).map((p) => p.name).join(", ") || "None";
    const gNames = this.players.filter((p) => this.guesserIds.includes(p.id)).map((p) => p.name).join(", ") || "None";
    this.log(
      `Round ${roles ? "roles" : ""}${roles && topics ? " & " : ""}${topics ? "topics" : ""} dealt (${gCount} Guesser(s), ${ttCount} Truth Teller(s)): ` +
        `Guessers = [${gNames}] (Voter: ${voterName}), Truth Teller(s) = [${ttNames}]`,
      "ACTION",
    );
  }

  /** Truth tellers wanted for n players / g guessers under the current role mode. */
  private targetTT(n: number, g: number): number {
    if (this.roleMode === "one_liar") return Math.max(1, n - g - 1);
    if (this.roleMode === "one_truth") return 1;
    return Math.max(1, this.targetTruthTellerCount);
  }

  setRoleMode(mode: string): boolean {
    if (mode !== "one_liar" && mode !== "custom" && mode !== "one_truth") return false;
    this.roleMode = mode;
    this.log(`Role mode: ${mode}`, "ACTION");
    if (this.phase === "lobby") this.assignRoundRoles();
    return true;
  }

  /**
   * Record the roles just played: "debt" grows by each role's fair share and drops by 1 for the
   * role actually played, so a positive debt means the player is owed that role.
   */
  bookRound(): void {
    const n = this.players.length;
    if (!n) return;
    const slots: Record<Role, number> = { guesser: 0, truth_teller: 0, liar: 0 };
    for (const p of this.players) slots[p.role ?? "liar"] += 1;
    for (const p of this.players) {
      const debt = (p.debt ??= { guesser: 0, truth_teller: 0, liar: 0 });
      for (const r of ROLES) debt[r] = (debt[r] ?? 0) + slots[r] / n;
      debt[p.role ?? "liar"] -= 1;
      p.last_role = p.role;
    }
  }

  /**
   * Scarcest role first, weighted by how owed each player is; nobody repeats last round's role
   * unless there aren't enough others. Returns [guesserIds, truthTellerIds].
   */
  private fairDeal(g: number, tt: number): [string[], string[]] {
    const counts: Record<Role, number> = { guesser: g, truth_teller: tt, liar: this.players.length - g - tt };
    const order = [...ROLES].sort((a, b) => counts[a] - counts[b]); // the last (largest) role takes whoever is left
    let best: Map<string, Role> | null = null;
    let bestScore = Infinity;
    // 30 random tries, not an exact matching; finds a zero-repeat deal at party sizes.
    for (let attempt = 0; attempt < 30; attempt++) {
      const pool = [...this.players];
      const deal = new Map<string, Role>();
      for (const role of order.slice(0, -1)) {
        for (let k = 0; k < counts[role]; k++) {
          const fresh = pool.filter((p) => p.last_role !== role);
          const cands = fresh.length ? fresh : pool;
          const w = cands.map((p) => Math.exp(2 * (p.debt?.[role] ?? 0)));
          const pick = weightedChoice(cands, w);
          pool.splice(pool.indexOf(pick), 1);
          deal.set(pick.id, role);
        }
      }
      for (const p of pool) deal.set(p.id, order[order.length - 1] as Role);
      const score = this.players.filter((p) => p.last_role === deal.get(p.id)).length;
      if (best === null || score < bestScore) {
        best = deal;
        bestScore = score;
        if (!score) break;
      }
    }
    const ids = (r: Role) => this.players.filter((p) => best!.get(p.id) === r).map((p) => p.id);
    return [ids("guesser"), ids("truth_teller")];
  }

  canReady(): boolean {
    return this.phase === "reveal" || (this.phase === "lobby" && this.checkRoleRequirements()[0]);
  }

  toggleReady(playerId: string): boolean {
    if (!this.canReady() || !this.players.some((p) => p.id === playerId)) return false;
    if (this.readyIds.has(playerId)) this.readyIds.delete(playerId);
    else this.readyIds.add(playerId);
    this.advanceIfAllReady();
    return true;
  }

  private advanceIfAllReady(): void {
    if (!this.players.length || !this.canReady() || !this.players.every((p) => this.readyIds.has(p.id))) return;
    this.log("Everyone is ready.", "ACTION");
    if (this.phase === "lobby") this.nextPhase();
    else this.nextRound();
  }

  /** New roles; suspects keep their topics where the new role allows it. */
  randomizeRoles(): void {
    this.assignRoundRoles({ topics: false });
  }

  /** New topics for everyone, same roles. recordOld: count the dropped topics as heard. */
  newTopics(recordOld: boolean): void {
    if (recordOld) this.recordHistory();
    this.assignRoundRoles({ roles: false });
  }

  touch(): void {
    this.lastActivity = now();
  }

  /** Book the result (top scorers win, ties included), then start a fresh lobby. */
  endGame(signOutAll = false, reason = "Admin ended the game"): void {
    if (this.players.some((p) => (p.score ?? 0) > 0)) {
      const top = Math.max(...this.players.map((p) => p.score ?? 0));
      const winners = this.players.filter((p) => (p.score ?? 0) === top);
      accounts.recordGame(this.accountIds(), winners.map((p) => p.account_id).filter((a): a is string => Boolean(a)));
      this.log(`${reason}. Winner(s): ${winners.map((p) => p.name).join(", ")} with ${top} pts.`, "ACTION");
    } else {
      this.log(`${reason} (no points scored).`, "ACTION");
    }
    if (signOutAll) {
      this.players = [];
      this.guesserIds = [];
      this.truthTellerIds = [];
      this.votingGuesserId = null;
    }
    this.resetGame();
    this.touch();
  }

  /** Store a 0-10 review of the statement this player holds right now; returns an error message or null. */
  addReview(p: Partial<Player>, score: unknown, text: unknown): string | null {
    if (!p.statement) return "You don't hold a statement right now.";
    if (typeof score !== "number" || !Number.isInteger(score) || score < 0 || score > 10) return "Pick a score from 0 to 10.";
    const clean = String(text ?? "").trim();
    if (clean.length > 1000 || clean.split(/\s+/).filter(Boolean).length > 100) return "Keep the review to 100 words.";
    const t = findTopicData(p.topic);
    const tt = this.truthTellerIds.includes(p.id as string);
    const facts = tt ? (p.detailed_description ?? null) : packs.lieFacts(t, p.statement);
    const acct = p.account_id ? accounts.accountById(p.account_id) : null;
    accounts.addReview({
      ts: Math.floor(now()), game_id: this.gameId, round: this.roundNumber,
      topic_id: t?.id ?? null, pack: t?.pack ?? null, topic: p.topic ?? null, side: tt ? "truth" : "lie",
      statement: p.statement, facts, score, text: clean, player_name: p.name ?? "", account_id: acct?.id ?? null,
    });
    this.log(`${p.name} reviewed '${p.topic}': ${score}/10`, "ACTION");
    return null;
  }

  endIfIdle(limit?: number): void {
    const mins = accounts.settings().idle_minutes ?? 60;
    const lim = limit ?? mins * 60;
    if (now() - this.lastActivity > lim && (this.players.length || this.phase !== "lobby")) {
      this.endGame(true, `Game ended after ${mins} minutes without activity`);
    }
  }

  /**
   * Validates whether the selected role counts can run a game: at least one guesser, one truth
   * teller and one liar. Returns [valid, errorMessage, counts].
   */
  checkRoleRequirements(): [boolean, string | null, RoleCounts] {
    const total = this.players.length;
    const targetG = Math.max(1, this.targetGuesserCount ?? 1);
    const targetTT = this.targetTT(total, targetG);

    // Effective role counts based on target counts or manually assigned roles
    const actualG = this.guesserIds.length;
    const actualTT = this.truthTellerIds.length;
    const effG = actualG > 0 ? Math.max(targetG, actualG) : targetG;
    const effTT = actualTT > 0 ? Math.max(targetTT, actualTT) : targetTT;

    const effLiars = total - effG - effTT;
    const minPlayers = Math.max(3, effG + effTT + 1);

    const counts: RoleCounts = { players: total, guessers: effG, truth_tellers: effTT, liars: Math.max(0, effLiars), min_required_players: minPlayers };

    if (total === 0) {
      return [false, "Cannot start game: No players have joined. At least 1 Guesser, 1 Truth Teller, and 1 Liar are required (minimum 3 players).", counts];
    }
    if (total < 3) {
      return [false, `Cannot start game: At least 1 Guesser, 1 Truth Teller, and 1 Liar are required (minimum 3 players). Only ${total} player(s) joined. Please wait for more players to join or adjust role counts.`, counts];
    }
    if (effG < 1) {
      return [false, `Cannot start game: At least 1 Guesser must be present (currently ${effG}). Please adjust the number of Guessers to at least 1.`, counts];
    }
    if (effTT < 1) {
      return [false, `Cannot start game: At least 1 Truth Teller must be present (currently ${effTT}). Please adjust the number of Truth Tellers to at least 1.`, counts];
    }
    if (effLiars < 1) {
      return [
        false,
        `Cannot start game: At least 1 Liar must be present. Currently selected: ${effG} Guesser(s) and ${effTT} Truth Teller(s), leaving ${Math.max(0, effLiars)} Liar(s) among ${total} players. Please change the number of each role to allow at least 1 Liar (or add more players).`,
        counts,
      ];
    }
    return [true, null, counts];
  }

  setRoleCounts(guesserCount: unknown, truthTellerCount: unknown, applyNow = true): boolean {
    const g = toInt(guesserCount);
    const tt = toInt(truthTellerCount);
    if (g === null || tt === null) return false;
    if (g < 1 || tt < 1) return false;

    this.targetGuesserCount = g;
    this.targetTruthTellerCount = tt;
    this.log(`Role counts configured: ${g} Guesser(s), ${tt} Truth Teller(s)`, "ACTION");

    if (applyNow && this.phase === "lobby") this.assignRoundRoles();
    return true;
  }

  setVotingGuesser(playerId: string): boolean {
    const target = this.player(playerId);
    if (!target) return false;

    if (!this.guesserIds.includes(playerId)) {
      this.setPlayerRole(playerId, "guesser", true);
    } else {
      this.votingGuesserId = playerId;
      for (const p of this.players) p.is_voting_guesser = p.id === this.votingGuesserId;
      this.savePlayers();
    }

    this.log(`Designated Lead Voting Guesser: ${target.name}`, "ACTION");
    return true;
  }

  private clearGuesserContent(p: Player): void {
    p.topic = null;
    p.category = null;
    p.statement = null;
    p.detailed_description = null;
  }

  /**
   * Directly assigns a role to a player without randomising. Guarantees at least one guesser
   * (with a designated voter) and one truth teller; truth tellers always hold their true statement and facts.
   */
  setPlayerRole(playerId: string, newRole: string, isVoter?: boolean | null): boolean {
    const target = this.player(playerId);
    if (!target || (newRole !== "guesser" && newRole !== "truth_teller" && newRole !== "liar")) return false;

    if (newRole === "guesser") {
      if (this.targetGuesserCount === 1 && this.votingGuesserId === playerId && this.guesserIds.length === 1) return true;

      const wasTT = this.truthTellerIds.includes(playerId);
      if (wasTT) this.truthTellerIds = this.truthTellerIds.filter((t) => t !== playerId);

      target.role = "guesser";
      this.clearGuesserContent(target);

      if (this.targetGuesserCount === 1) {
        // In single guesser mode, demote old guesser(s) to liar
        for (const gid of [...this.guesserIds]) {
          if (gid !== playerId) {
            const oldG = this.player(gid);
            if (oldG) {
              oldG.role = "liar";
              oldG.is_voting_guesser = false;
              this.give(oldG, "liar");
            }
          }
        }
        this.guesserIds = [playerId];
        this.votingGuesserId = playerId;
      } else {
        if (!this.guesserIds.includes(playerId)) this.guesserIds.push(playerId);
        if (isVoter === null || isVoter === undefined || isVoter === true || !this.votingGuesserId) this.votingGuesserId = playerId;
      }

      if (wasTT && !this.truthTellerIds.length) {
        const cand = this.players.find((p) => !this.guesserIds.includes(p.id));
        if (cand) {
          this.truthTellerIds.push(cand.id);
          cand.role = "truth_teller";
        }
      }
    } else if (newRole === "truth_teller") {
      if (this.targetTruthTellerCount === 1 && this.truthTellerId === playerId && this.truthTellerIds.length === 1) return true;

      const wasGuesser = this.guesserIds.includes(playerId);
      if (wasGuesser) {
        this.guesserIds = this.guesserIds.filter((g) => g !== playerId);
        if (this.votingGuesserId === playerId) this.votingGuesserId = this.guesserIds[0] ?? null;
      }

      if (this.targetTruthTellerCount === 1) {
        // In single truth teller mode, demote old truth teller(s) to liar
        for (const tid of [...this.truthTellerIds]) {
          if (tid !== playerId) {
            const oldTT = this.player(tid);
            if (oldTT) {
              oldTT.role = "liar";
              this.give(oldTT, "liar");
            }
          }
        }
        this.truthTellerIds = [playerId];
      } else {
        this.truthTellerIds = [playerId, ...this.truthTellerIds.filter((t) => t !== playerId)];
      }

      target.role = "truth_teller";

      if (wasGuesser && !this.guesserIds.length) {
        const cand = this.players.find((p) => !this.truthTellerIds.includes(p.id));
        if (cand) {
          this.guesserIds.push(cand.id);
          this.votingGuesserId = cand.id;
          cand.role = "guesser";
          this.clearGuesserContent(cand);
        }
      }

      this.give(target, "truth_teller");
    } else {
      const wasGuesser = this.guesserIds.includes(playerId);
      const wasTT = this.truthTellerIds.includes(playerId);

      if (wasGuesser) {
        this.guesserIds = this.guesserIds.filter((g) => g !== playerId);
        if (this.votingGuesserId === playerId) this.votingGuesserId = this.guesserIds[0] ?? null;
      }
      if (wasTT) this.truthTellerIds = this.truthTellerIds.filter((t) => t !== playerId);

      target.role = "liar";
      target.detailed_description = null;

      if (!this.guesserIds.length) {
        let candidates = this.players.filter((p) => p.id !== playerId && !this.truthTellerIds.includes(p.id));
        if (!candidates.length) candidates = this.players.filter((p) => p.id !== playerId);
        const cand = candidates[0];
        if (cand) {
          this.truthTellerIds = this.truthTellerIds.filter((t) => t !== cand.id);
          this.guesserIds.push(cand.id);
          this.votingGuesserId = cand.id;
          cand.role = "guesser";
          this.clearGuesserContent(cand);
        }
      }

      if (!this.truthTellerIds.length) {
        const cand = this.players.find((p) => p.id !== playerId && !this.guesserIds.includes(p.id));
        if (cand) {
          this.truthTellerIds.push(cand.id);
          cand.role = "truth_teller";
        }
      }

      target.statement = null; // a fresh lie for the new role
      this.give(target, "liar");
    }

    for (const p of this.players) p.is_voting_guesser = p.id === this.votingGuesserId;

    this.ensureAllSuspectsHaveContent();
    this.targetGuesserCount = this.guesserIds.length;
    this.targetTruthTellerCount = this.truthTellerIds.length;
    this.savePlayers();
    this.log(`Role assigned directly: ${target.name} -> ${newRole.toUpperCase()}`, "ACTION");
    return true;
  }

  private applyRoleLists(): void {
    for (const p of this.players) {
      if (this.guesserIds.includes(p.id)) {
        p.role = "guesser";
        p.is_voting_guesser = p.id === this.votingGuesserId;
        this.clearGuesserContent(p);
      } else if (this.truthTellerIds.includes(p.id)) {
        p.role = "truth_teller";
        p.is_voting_guesser = false;
      } else {
        p.role = "liar";
        p.is_voting_guesser = false;
      }
    }
  }

  private validIds(playerIds: string[] | null | undefined): string[] | null {
    if (!playerIds || !playerIds.length) return null;
    let valid = playerIds.filter((pid) => this.players.some((p) => p.id === pid));
    if (!valid.length) return null;
    if (valid.length >= this.players.length) {
      valid = valid.slice(0, this.players.length - 1);
      if (!valid.length) return null;
    }
    return valid;
  }

  /**
   * Directly sets several players as guessers: at least one suspect remains, voterId (or the first
   * guesser) becomes the designated voter, guessers lose their topics, truth tellers are kept or reassigned.
   */
  setGuessers(playerIds: string[], voterId?: string | null): boolean {
    const valid = this.validIds(playerIds);
    if (!valid) return false;

    this.targetGuesserCount = valid.length;
    this.guesserIds = [...valid];

    if (voterId && this.guesserIds.includes(voterId)) this.votingGuesserId = voterId;
    else if (!this.votingGuesserId || !this.guesserIds.includes(this.votingGuesserId)) this.votingGuesserId = this.guesserIds[0] as string;

    // Any guesser who was a truth teller stops being one
    this.truthTellerIds = this.truthTellerIds.filter((tid) => !this.guesserIds.includes(tid));

    // If no truth tellers remain, pick one suspect
    const suspects = this.players.filter((p) => !this.guesserIds.includes(p.id));
    if (!this.truthTellerIds.length && suspects.length) this.truthTellerIds = [(suspects[0] as Player).id];

    this.applyRoleLists();
    this.ensureAllSuspectsHaveContent();
    this.savePlayers();
    const names = this.players.filter((p) => this.guesserIds.includes(p.id)).map((p) => p.name);
    this.log(`Assigned Guesser team: ${JSON.stringify(names)} (Lead Voter: ${this.votingGuesserName})`, "ACTION");
    return true;
  }

  /**
   * Directly sets several players as truth tellers: at least one guesser remains, each truth teller
   * gets a unique topic with the true statement and facts, every other suspect becomes a liar.
   */
  setTruthTellers(playerIds: string[]): boolean {
    const valid = this.validIds(playerIds);
    if (!valid) return false;

    this.targetTruthTellerCount = valid.length;
    this.truthTellerIds = [...valid];

    this.guesserIds = this.guesserIds.filter((gid) => !this.truthTellerIds.includes(gid));

    if (!this.guesserIds.length) {
      const cand = this.players.find((p) => !this.truthTellerIds.includes(p.id));
      if (cand) {
        this.guesserIds = [cand.id];
        this.votingGuesserId = cand.id;
      }
    } else if (!this.votingGuesserId || !this.guesserIds.includes(this.votingGuesserId)) {
      this.votingGuesserId = this.guesserIds[0] as string;
    }

    this.applyRoleLists();
    this.ensureAllSuspectsHaveContent();
    this.savePlayers();
    const names = this.players.filter((p) => this.truthTellerIds.includes(p.id)).map((p) => p.name);
    this.log(`Assigned Truth Teller(s): ${JSON.stringify(names)}`, "ACTION");
    return true;
  }

  setGuesser(playerIdOrIds: string | string[]): boolean {
    if (Array.isArray(playerIdOrIds)) return this.setGuessers(playerIdOrIds);
    return this.setPlayerRole(playerIdOrIds, "guesser", true);
  }

  setTruthTeller(playerIdOrIds: string | string[]): boolean {
    if (Array.isArray(playerIdOrIds)) return this.setTruthTellers(playerIdOrIds);
    return this.setPlayerRole(playerIdOrIds, "truth_teller");
  }

  setPhase(phase: string, force = false): boolean {
    if (!(PHASES as string[]).includes(phase)) return false;
    const target = phase as Phase;

    // A completed round (reveal) cannot go back to an earlier phase of the same round
    if (!force && this.phase === "reveal" && (target === "setup" || target === "questioning" || target === "voting")) {
      this.log(`Phase change blocked: Round ${this.roundNumber} is completed. Cannot return to previous phase (${target.toUpperCase()}). Please start a new round or terminate game and return to lobby.`, "WARN");
      return false;
    }

    // Starting the game (lobby -> an active phase) needs the minimum roles
    if (!force && this.phase === "lobby" && target !== "lobby") {
      const [valid, err] = this.checkRoleRequirements();
      if (!valid) {
        this.log(`Game start blocked: ${err}`, "WARN");
        return false;
      }
    }

    this.phase = target;
    this.readyIds = new Set();
    this.log(`Game phase changed to: ${target.toUpperCase()}`, "ACTION");
    // Leaving the lobby: guarantee topics and descriptions are assigned
    if (target !== "lobby") this.ensureAllSuspectsHaveContent();
    // Entering reveal without a scored round: reveal and score now
    if (target === "reveal" && this.lastRoundResults === null) this.revealAndScore();
    return true;
  }

  /** Ensures all suspects have unique topics and truth tellers have their detailed descriptions. */
  ensureAllSuspectsHaveContent(): void {
    if (!this.guesserIds.length || !this.votingGuesserId || !this.truthTellerIds.length) {
      if (this.players.length >= 2) {
        this.assignRoundRoles();
        return;
      }
    }

    // Clean overlap
    this.truthTellerIds = this.truthTellerIds.filter((tid) => !this.guesserIds.includes(tid));
    if (!this.truthTellerIds.length) {
      const cand = this.players.find((p) => !this.guesserIds.includes(p.id));
      if (cand) this.truthTellerIds = [cand.id];
    }

    if (this.guesserIds.length && (!this.votingGuesserId || !this.guesserIds.includes(this.votingGuesserId))) this.votingGuesserId = this.guesserIds[0] as string;

    const assigned = new Set<string>();
    for (const p of this.players) {
      p.is_voting_guesser = p.id === this.votingGuesserId;
      if (this.guesserIds.includes(p.id)) {
        p.role = "guesser";
        this.clearGuesserContent(p);
      } else if (this.truthTellerIds.includes(p.id)) {
        p.role = "truth_teller";
        this.give(p, "truth_teller", assigned);
        assigned.add(p.topic as string);
      } else {
        p.role = "liar";
        this.give(p, "liar", assigned);
        assigned.add(p.topic as string);
      }
    }
    this.recordUsedStatements();
    this.savePlayers();
  }

  nextPhase(): Phase {
    // A completed round cannot advance (it would wrap to the lobby); start a new round instead.
    if (this.phase === "reveal") {
      this.log("Advance blocked: Round is completed. Please start a new round or terminate game and return to lobby.", "WARN");
      return this.phase;
    }
    const idx = PHASES.indexOf(this.phase);
    const target = PHASES[(idx + 1) % PHASES.length] as Phase;
    if (this.phase === "lobby" && target === "setup") {
      const [valid, err] = this.checkRoleRequirements();
      if (!valid) {
        this.log(`Game start blocked: ${err}`, "WARN");
        return this.phase;
      }
    }
    this.setPhase(target);
    return this.phase;
  }

  castVote(voterId: string, targetId?: string | string[] | null, targetIds?: string | string[] | null): boolean {
    if (voterId !== this.votingGuesserId) {
      this.log(`Vote blocked: Player ${voterId} is not the designated Voting Guesser. Only the Voting Guesser can vote!`, "WARN");
      return false;
    }
    const voter = this.player(this.votingGuesserId);
    if (!voter) return false;

    const raw = targetIds !== undefined && targetIds !== null ? targetIds : targetId;
    if (raw === undefined || raw === null) return false;

    let targetList: string[];
    if (Array.isArray(raw)) targetList = raw.map((x) => String(x).trim()).filter(Boolean);
    else if (typeof raw === "string") targetList = raw.split(",").map((x) => x.trim()).filter(Boolean);
    else targetList = [String(raw)];
    if (!targetList.length) return false;

    // Only suspects can be accused (guessers cannot be the truth teller)
    const validTargets = this.players.filter((p) => targetList.includes(p.id) && !this.guesserIds.includes(p.id));
    if (!validTargets.length) {
      this.log(`Vote blocked: No valid suspects found in target list ${JSON.stringify(targetList)}!`, "WARN");
      return false;
    }

    voter.voted_for = validTargets.length === 1 ? (validTargets[0] as Player).id : validTargets.map((p) => p.id);

    this.savePlayers();
    const accused = validTargets.map((p) => p.name).join(", ");
    this.log(`Lead Guesser's Accusation: ${voter.name} accuses [${accused}] of telling the TRUTH!`, "ACTION");
    // The result is revealed as soon as the guesser has chosen
    this.revealAndScore();
    return true;
  }

  clearVotes(): void {
    for (const p of this.players) p.voted_for = null;
    this.savePlayers();
  }

  revealAndScore(): RoundResults {
    this.phase = "reveal";
    const results: RoundResults = {
      guesser: null, guessers: [], truth_teller: null, truth_tellers: [], liars: [],
      picked_player: null, picked_players: [], is_correct: false, score_changes: {}, standings: [],
    };
    const votingGuesser = this.player(this.votingGuesserId);
    const guesserPlayers = this.players.filter((p) => this.guesserIds.includes(p.id));
    const truthPlayers = this.players.filter((p) => this.truthTellerIds.includes(p.id));

    if (votingGuesser) results.guesser = { id: votingGuesser.id, name: votingGuesser.name, voted_for: votingGuesser.voted_for ?? null };
    for (const gp of guesserPlayers) results.guessers.push({ id: gp.id, name: gp.name, is_voting_guesser: gp.id === this.votingGuesserId, voted_for: gp.voted_for ?? null });
    for (const tp of truthPlayers) results.truth_tellers.push({ id: tp.id, name: tp.name, topic: tp.topic, true_statement: tp.statement, detailed_description: tp.detailed_description });
    if (truthPlayers.length) results.truth_teller = results.truth_tellers[0] as TruthTellerResult;

    for (const lp of this.players.filter((p) => p.role === "liar")) results.liars.push({ id: lp.id, name: lp.name, topic: lp.topic, false_statement: lp.statement });

    // Extract voted player ids
    const votedRaw = votingGuesser?.voted_for ?? null;
    const votedIds = Array.isArray(votedRaw) ? votedRaw.map(String).filter(Boolean) : typeof votedRaw === "string" && votedRaw ? [votedRaw] : [];

    const pickedPlayers = this.players.filter((p) => votedIds.includes(p.id));
    results.picked_players = pickedPlayers.map((p) => ({ id: p.id, name: p.name, role: p.role ?? "suspect", is_truth_teller: this.truthTellerIds.includes(p.id), topic: p.topic }));
    results.picked_player = results.picked_players[0] ?? null;

    // Rule: with more than one truth teller the guessers must name all of them to score.
    // Everyone accused of being the truth teller scores a point for convincing the guesser, whatever their role.
    const actualTT = new Set(this.truthTellerIds);
    const votedSet = new Set(votedIds);
    const isCorrect = actualTT.size > 0 && votedSet.size === actualTT.size && [...votedSet].every((id) => actualTT.has(id));
    results.is_correct = isCorrect;

    for (const p of this.players) results.score_changes[p.name] = 0;

    // 1. The guesser team scores 1 each when every truth teller was identified
    for (const gp of guesserPlayers) {
      const pts = isCorrect ? 1 : 0;
      gp.score += pts;
      results.score_changes[gp.name] = pts;
    }
    // 2. Everyone accused scores 1 for convincing the guesser, regardless of actual role
    for (const pp of pickedPlayers) {
      pp.score += 1;
      results.score_changes[pp.name] = (results.score_changes[pp.name] ?? 0) + 1;
    }

    const gNames = guesserPlayers.map((p) => p.name).join(", ") || "Guessers";
    const ttNames = truthPlayers.map((p) => p.name).join(", ") || "Truth Teller";
    const pickedNames = pickedPlayers.map((p) => p.name).join(", ") || "Nobody";

    if (isCorrect) {
      if (truthPlayers.length > 1) this.log(`Brilliant deduction! Guesser team (${gNames}) correctly identified all ${truthPlayers.length} Truth Tellers: ${pickedNames} (+1 pt to Guessers, +1 pt to each Truth Teller)!`, "INFO");
      else this.log(`Brilliant deduction! Guesser team (${gNames}) correctly identified Truth Teller ${pickedNames} (+1 pt each)!`, "INFO");
    } else if (pickedPlayers.length) {
      this.log(`Bluff successful! Accused player(s) [${pickedNames}] convinced Guesser team (+1 pt each). The actual Truth Teller(s) were: ${ttNames}!`, "INFO");
    } else {
      this.log("Accusation concluded with no selection.", "WARN");
    }

    for (const p of this.players) if (p.account_id) accounts.addRoundScore(p.account_id, results.score_changes[p.name] ?? 0);
    this.savePlayers();
    this.log(`REVEAL: ${ttNames} told the truth this round!`, "WARN");

    results.standings = this.getStandings(results.score_changes);
    this.lastRoundResults = results;
    return results;
  }

  getStandings(ptsMap?: Record<string, number> | null, revealRoles = false): Standing[] {
    const pts = ptsMap ?? this.lastRoundResults?.score_changes ?? {};
    const sorted = [...this.players].sort((a, b) => (b.score ?? 0) - (a.score ?? 0) || byName(a.name ?? "", b.name ?? ""));
    const isReveal = this.phase === "reveal" || revealRoles;
    return sorted.map((p, i) => ({
      rank: i + 1,
      id: p.id,
      name: p.name,
      score: p.score ?? 0,
      role: isReveal ? p.role ?? "liar" : this.guesserIds.includes(p.id) ? "guesser" : "suspect",
      pts_gained: pts[p.name] ?? 0,
    }));
  }

  guesserAdvance(playerId: string): boolean {
    if (!this.guesserIds.includes(playerId)) {
      this.log(`Advance rejected: Player ${playerId} is not a Guesser.`, "WARN");
      return false;
    }
    if (this.phase === "setup") {
      this.setPhase("questioning");
      this.log("Guesser advanced game to QUESTIONING phase.", "ACTION");
      return true;
    }
    if (this.phase === "questioning") {
      this.setPhase("voting");
      this.log("Guesser confirmed: All statements heard and understood! Advancing to ACCUSATION phase.", "ACTION");
      return true;
    }
    return false;
  }

  nextRound(): boolean {
    const [valid, err] = this.checkRoleRequirements();
    if (!valid) {
      this.log(`Cannot start next round: ${err}`, "WARN");
      return false;
    }
    this.roundNumber += 1;
    this.clearVotes();
    this.lastRoundResults = null;
    this.bookRound();
    this.assignRoundRoles();
    this.setPhase("setup", true);
    this.log(`--- Started Round ${this.roundNumber} ---`, "INFO");
    return true;
  }

  resetGame(): void {
    this.roundNumber = 1;
    this.phase = "lobby";
    this.lastRoundResults = null;
    this.gameId = Date.now(); // new game; the archive keeps earlier games
    this.usedTopicIds = [];
    const temps = new Set(this.players.filter((p) => p.token && !p.account_id).map((p) => p.id));
    this.players = this.players.filter((p) => !temps.has(p.id));
    this.guesserIds = this.guesserIds.filter((i) => !temps.has(i));
    this.truthTellerIds = this.truthTellerIds.filter((i) => !temps.has(i));
    if (this.votingGuesserId && temps.has(this.votingGuesserId)) this.votingGuesserId = this.guesserIds[0] ?? null;
    this.readyIds = new Set();
    for (const p of this.players) {
      p.score = 0;
      p.voted_for = null;
      delete p.debt;
      delete p.last_role;
    }
    this.clearVotes();
    this.assignRoundRoles();
    this.log(`Game reset to initial state (${temps.size} temporary player(s) signed out).`, "INFO");
  }

  adjustScore(playerId: string, delta: number): boolean {
    const p = this.player(playerId);
    if (!p) return false;
    const d = Number(delta) || 0;
    p.score = Math.max(0, p.score + d);
    this.savePlayers();
    this.log(`Adjusted score for ${p.name}: ${p.score} (${d > 0 ? "+" : ""}${d})`, "ACTION");
    return true;
  }

  /** Phone badge: how well this suspect's topic fits their tags / expertise, among topics of the same side. */
  private matchPct(p: Player, settings: Settings): number | null {
    const mode = settings.match_mode ?? "off";
    const t = findTopicData(p.topic);
    if (mode === "off" || !t || (p.role !== "truth_teller" && p.role !== "liar")) return null;
    const need: Need = p.role === "truth_teller" ? "truth" : "lie";
    return match.percent(p, t, packs.library().filter((x) => packs.hasSide(x, need)), mode);
  }

  /** Admin view of matching; in expertise mode it also keeps the embedding cache topped up. */
  private matchStatus(settings: Settings): match.Status & { profiles: number } {
    if (settings.match_mode === "expertise") {
      match.warm([...packs.library().map(match.topicText), ...this.players.map((p) => match.queryText(p.expertise))]);
    } else if (settings.match_mode === "tags") {
      match.warm([...packs.allTags().map(match.tagText), ...this.players.flatMap((p) => (p.tags ?? []).map(match.tagText))]);
    }
    return { ...match.status(), profiles: this.players.filter((p) => (p.tags && p.tags.length) || p.expertise).length };
  }

  getState({ isAdmin = true, playerId = null, token = null }: { isAdmin?: boolean; playerId?: string | null; token?: string | null } = {}): GameState {
    this.endIfIdle();
    // Guarantee all suspects have topics and roles assigned
    const needsContent = this.players.some((p) => !this.guesserIds.includes(p.id) && (!p.topic || !p.statement));
    if (needsContent || !this.guesserIds.length || !this.votingGuesserId || !this.truthTellerIds.length) this.ensureAllSuspectsHaveContent();

    const settings = accounts.settings();
    const guesser = this.player(this.votingGuesserId);
    const truthPlayer = this.players.find((p) => this.truthTellerIds.includes(p.id)) ?? null;
    const revealed = isAdmin || this.phase === "reveal";

    const playersView: PlayerView[] = [];
    for (const p of this.players) {
      const isG = this.guesserIds.includes(p.id);
      const isTT = this.truthTellerIds.includes(p.id);
      const view: PlayerView = {
        id: p.id, name: p.name, score: p.score, voted_for: p.voted_for ?? null, is_guesser: isG, is_voting_guesser: p.id === this.votingGuesserId,
        role: "", is_truth_teller: null, topic: null, category: null, statement: null, detailed_description: null,
      };
      if (isAdmin) view.account = Boolean(p.account_id);
      if (revealed) {
        view.role = isG ? "guesser" : isTT ? "truth_teller" : "liar";
        view.is_truth_teller = isTT;
        view.topic = p.topic ?? null;
        view.category = p.category ?? null;
        view.statement = p.statement ?? null;
        view.detailed_description = p.detailed_description ?? null;
        // Paper source (PhD pack): only ever attached to a truth, so it can't leak a liar.
        view.source = isTT ? (findTopicData(p.topic)?.source ?? null) : null;
        if (isAdmin && view.role === "liar") view.lie_facts = packs.lieFacts(findTopicData(p.topic), p.statement); // the admin dossier shows each liar's background facts
      } else {
        view.role = isG ? "guesser" : "suspect";
        view.is_truth_teller = null;
        view.topic = p.topic ?? null;
        view.category = p.category ?? null;
        view.statement = "[Hidden from other players]";
        view.detailed_description = null;
      }
      playersView.push(view);
    }

    // For a specific player viewing on a phone
    let myInfo: MyInfo | null = null;
    const pid = playerId === null || playerId === undefined ? "" : String(playerId).trim();
    if (pid && !["undefined", "null", "None"].includes(pid)) {
      let me = this.player(pid);
      // Match by name fallback ("name:Alice" or "Alice")
      if (!me) {
        const targetName = (pid.startsWith("name:") ? pid.slice(5).trim() : pid).toLowerCase();
        me = this.players.find((p) => p.name.trim().toLowerCase() === targetName) ?? null;
      }
      // Private info (role, statement) only for the token holder.
      if (me && !isAdmin && !this.playerForToken(me.id, token)) me = null;

      if (me) {
        const isMeG = this.guesserIds.includes(me.id);
        const isMeTT = this.truthTellerIds.includes(me.id);
        const redact = this.phase === "questioning" || this.phase === "voting";

        // Self-healing safeguards: a truth teller always holds topic, statement and facts; a liar a topic and a lie.
        if (isMeTT && (!me.detailed_description || !me.statement || !me.topic)) {
          this.give(me, "truth_teller");
          me.role = "truth_teller";
          this.savePlayers();
        } else if (!isMeG && !isMeTT && (!me.statement || !me.topic)) {
          this.give(me, "liar");
          me.role = "liar";
          this.savePlayers();
        }

        const topic = findTopicData(me.topic);
        const myTags = me.tags ?? [];
        myInfo = {
          id: me.id,
          name: me.name,
          role: isMeG ? "guesser" : isMeTT ? "truth_teller" : "liar",
          is_guesser: isMeG,
          is_voting_guesser: me.id === this.votingGuesserId,
          voting_guesser_name: guesser?.name ?? null,
          fellow_guessers: this.players.filter((p) => this.guesserIds.includes(p.id) && p.id !== me!.id).map((p) => p.name),
          is_truth_teller: isMeTT,
          topic: me.topic ?? null,
          category: me.category ?? null,
          statement: me.statement ?? null,
          // Truth tellers ALWAYS receive their detailed description
          detailed_description: isMeTT ? me.detailed_description ?? null : null,
          lie_facts: me.role === "liar" && settings.lying_facts ? packs.lieFacts(topic, me.statement) : [],
          // Sources are redacted while suspects are being questioned:
          // everyone holds just a statement, so "some university in Germany" is as good as the real thing.
          source: isMeTT && topic?.source ? (redact ? { redacted: true } : topic.source) : null,
          match_pct: this.matchPct(me, settings),
          tag_order: match.rankTags(myTags, [...new Set([...packs.allTags(), ...myTags])].sort(), me.expertise ?? ""),
          permanent: Boolean(me.account_id),
          tags: myTags,
          expertise: me.expertise ?? "",
          has_password: Boolean(me.account_id || me.pw_hash),
        };
      }
    }

    const usedTrue = this.usedStatements.filter((s) => s.type === "true");
    const usedFalse = this.usedStatements.filter((s) => s.type === "false");
    const gkeys = new Set(accounts.globalKeys());
    const lib = packs.library();
    const libKeys = new Set(lib.flatMap(packs.statementKeys));
    const usedKeys = [...gkeys].filter((k) => libKeys.has(k)); // only statements of enabled packs that still exist
    const usedTrueCount = usedKeys.filter((k) => k.endsWith(":t")).length;
    const usedFalseCount = usedKeys.length - usedTrueCount;
    const currentTrue: CurrentStatement[] = this.players
      .filter((p) => p.role === "truth_teller" && p.statement)
      .map((p) => ({ player_id: p.id, player_name: p.name, topic: p.topic, category: p.category, statement: p.statement, detailed_description: p.detailed_description }));
    const currentFalse: CurrentStatement[] = this.players
      .filter((p) => p.role === "liar" && p.statement)
      .map((p) => ({ player_id: p.id, player_name: p.name, topic: p.topic, category: p.category, statement: p.statement }));

    const totalTrue = lib.filter((t) => t.true_statement).length;
    const totalFalse = lib.reduce((n, t) => n + t.false_statements.length, 0);

    const [validRoles, reqErr, req] = this.checkRoleRequirements();

    return {
      phase: this.phase,
      round: this.roundNumber,
      role_requirements: { valid: validRoles, error: reqErr, ...req },
      guesser_id: this.votingGuesserId,
      guesser_name: guesser?.name ?? "None",
      voting_guesser_id: this.votingGuesserId,
      voting_guesser_name: guesser?.name ?? "None",
      guesser_ids: [...this.guesserIds],
      target_guesser_count: this.targetGuesserCount,
      target_truth_teller_count: this.targetTruthTellerCount,
      truth_teller_count: this.truthTellerIds.length,
      role_mode: this.roleMode,
      ready_ids: [...this.readyIds].sort(),
      can_ready: this.canReady(),
      truth_teller_id: revealed ? this.truthTellerId : null,
      truth_teller_name: revealed && truthPlayer ? truthPlayer.name : "???",
      truth_teller_ids: revealed ? [...this.truthTellerIds] : [],
      players: playersView,
      my_info: myInfo,
      standings: this.getStandings(null, isAdmin),
      last_results: this.lastRoundResults,
      used_topics_count: new Set(usedKeys.map(accounts.topicOf)).size,
      blocked_topics_count: isAdmin ? this.blocked().size : 0,
      settings,
      all_tags: packs.allTags(),
      match_status: isAdmin ? this.matchStatus(settings) : null,
      accounts: isAdmin ? accounts.listAccounts() : [],
      total_topics_count: lib.length,
      packs: isAdmin ? packs.packSummaries(gkeys) : [],
      used_true_statements: isAdmin ? usedTrue : [],
      used_false_statements: isAdmin ? usedFalse : [],
      current_true_statements: isAdmin ? currentTrue : [],
      current_false_statements: isAdmin ? currentFalse : [],
      used_true_count: usedTrueCount,
      used_false_count: usedFalseCount,
      used_truth_count: usedTrueCount,
      used_lies_count: usedFalseCount,
      total_true_count: totalTrue,
      total_false_count: totalFalse,
      total_truth_count: totalTrue,
      total_lies_count: totalFalse,
      logs: isAdmin ? this.logs.slice(-100) : [],
    };
  }
}

/** int() as the admin console sends numbers: a number or a numeric string; anything else is rejected. */
function toInt(v: unknown): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? Math.trunc(v) : null;
  if (typeof v === "string" && /^\s*[+-]?\d+\s*$/.test(v)) return parseInt(v, 10);
  return null;
}

export { DEFAULT_PLAYER_NAMES };
