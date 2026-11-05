/**
 * Entry point for a laptop at a party: starts the server, opens the host's browser tabs
 * (stage controller + lobby QR) and streams the live log.
 */
import { spawn } from "node:child_process";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";
import { GameManager } from "./game.ts";
import { COLOR_BOLD, COLOR_CYAN, COLOR_GREEN, COLOR_MAGENTA, COLOR_RESET, COLOR_YELLOW, createServer as realCreateServer, type Running } from "./server.ts";

const TITLE = "One of These People Is Not Lying";

export function openUrl(url: string): void {
  const [cmd, args] = process.platform === "darwin" ? ["open", [url]] : process.platform === "win32" ? ["cmd", ["/c", "start", "", url]] : ["xdg-open", [url]];
  const child = spawn(cmd, args, { detached: true, stdio: "ignore" });
  child.on("error", (e) => process.stderr.write(`Could not open browser automatically: ${e.message}\n`));
  child.unref();
}

/** Wait briefly for the server to bind, then open the stage controller and the lobby QR in two tabs. */
export function openBrowserTabsDelayed(controlUrl: string, qrUrl: string, delayMs = 600): void {
  setTimeout(() => {
    process.stdout.write(`${COLOR_CYAN}[BROWSER]${COLOR_RESET} Opening Stage Controller (zero spoilers) in default browser tab...\n`);
    openUrl(controlUrl);
    setTimeout(() => {
      process.stdout.write(`${COLOR_CYAN}[BROWSER]${COLOR_RESET} Opening Lobby QR code in a separate browser tab...\n`);
      openUrl(qrUrl);
    }, 500).unref();
  }, delayMs).unref();
}

export interface MainDeps {
  createServer: typeof realCreateServer;
  openBrowserTabsDelayed: typeof openBrowserTabsDelayed;
}

export interface MainOptions {
  host: string;
  port: number;
  noBrowser: boolean;
  testBench: boolean;
  playersFile?: string;
}

export function parseCli(argv: string[]): MainOptions | null {
  const { values } = parseArgs({
    args: argv,
    options: {
      host: { type: "string", default: "0.0.0.0" },
      port: { type: "string", default: "5050" },
      "no-browser": { type: "boolean", default: false },
      "test-bench": { type: "boolean", default: false },
      "players-file": { type: "string" },
      help: { type: "boolean", short: "h", default: false },
    },
  });
  if (values.help) {
    process.stdout.write(
      `usage: node src/main.ts [--host HOST] [--port PORT] [--no-browser] [--test-bench] [--players-file FILE]\n\n${TITLE} - Game Server\n\n` +
        "  --host HOST           Host address to bind (default: 0.0.0.0)\n" +
        "  --port PORT           Port to bind (default: 5050)\n" +
        "  --no-browser          Do not automatically open the default browser\n" +
        "  --test-bench          Launch in test bench mode\n" +
        "  --players-file FILE   Custom players file\n",
    );
    return null;
  }
  const port = parseInt(values.port as string, 10);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error(`invalid --port: ${values.port}`);
  return { host: values.host as string, port, noBrowser: values["no-browser"] as boolean, testBench: values["test-bench"] as boolean, playersFile: values["players-file"] as string | undefined };
}

export async function main(argv: string[] = process.argv.slice(2), deps: Partial<MainDeps> = {}): Promise<Running | null> {
  const opts = parseCli(argv);
  if (!opts) return null;
  const createServer = deps.createServer ?? realCreateServer;
  const openTabs = deps.openBrowserTabsDelayed ?? openBrowserTabsDelayed;

  // When launched normally (not via the test bench), start with an empty lobby
  const gameManager = new GameManager({ seedSamples: false, playersFile: opts.playersFile });
  const running = await createServer({ host: opts.host, port: opts.port, gameManager });
  const { server, port: activePort, lanIp } = running;

  const localBase = `http://127.0.0.1:${activePort}`;
  const controlUrl = `${localBase}/control`;
  const adminUrl = `${localBase}/admin`;
  const qrUrl = `${localBase}/qr`;
  const joinUrl = `http://${lanIp}:${activePort}/join`;
  const displayUrl = `${localBase}/display`;

  const bar = "=".repeat(74);
  const out = (s = "") => process.stdout.write(s + "\n");
  out();
  out(`${COLOR_BOLD}${bar}${COLOR_RESET}`);
  out(`${COLOR_BOLD}   ${TITLE.toUpperCase()}${COLOR_RESET}`);
  out("  Game Server & Host Stage Monitor");
  out(bar);
  out(`  • ${COLOR_BOLD}Stage Controller (Host):${COLOR_RESET} ${COLOR_GREEN}${controlUrl}${COLOR_RESET}  (Zero Spoilers)`);
  out(`  • ${COLOR_BOLD}Lobby QR Code (Tab):${COLOR_RESET}     ${COLOR_MAGENTA}${qrUrl}${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Phone Join Link:${COLOR_RESET}         ${COLOR_CYAN}${joinUrl}${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Public TV/Display:${COLOR_RESET}       ${COLOR_GREEN}${displayUrl}${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Full Admin Dossier:${COLOR_RESET}         ${COLOR_YELLOW}${adminUrl}${COLOR_RESET}  (Contains Spoilers)`);
  out(`  • ${COLOR_BOLD}Status:${COLOR_RESET}                  ${COLOR_GREEN}ONLINE & MONITORING${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Stop Server:${COLOR_RESET}             Press ${COLOR_YELLOW}Ctrl+C${COLOR_RESET} at any time`);
  out(bar);
  out();

  if (!opts.noBrowser) openTabs(controlUrl, qrUrl);

  const shutdown = () => {
    out(`\n${COLOR_YELLOW}[SERVER] Shutting down gracefully...${COLOR_RESET}`);
    server.close(() => {
      out(`${COLOR_GREEN}[SERVER] Server stopped. Goodbye!${COLOR_RESET}`);
      process.exit(0);
    });
    setTimeout(() => process.exit(0), 1500).unref();
  };
  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
  return running;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((e) => {
    process.stderr.write(`${e instanceof Error ? e.message : String(e)}\n`);
    process.exit(1);
  });
}
