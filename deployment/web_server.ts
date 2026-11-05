/**
 * Production entry point (Docker, a VPS, a cloud host): binds 0.0.0.0, honours $PORT and $PUBLIC_URL,
 * never opens a browser, and shuts down cleanly on SIGTERM / SIGINT.
 */
import { parseArgs } from "node:util";
import { GameManager } from "../src/game.ts";
import { COLOR_BOLD, COLOR_CYAN, COLOR_GREEN, COLOR_MAGENTA, COLOR_RESET, COLOR_YELLOW, createServer } from "../src/server.ts";

async function main(): Promise<void> {
  const { values } = parseArgs({
    options: {
      host: { type: "string", default: process.env.HOST || "0.0.0.0" },
      port: { type: "string", default: process.env.PORT || "5050" },
      "public-url": { type: "string", default: process.env.PUBLIC_URL || "" },
    },
  });
  const port = parseInt(values.port as string, 10);
  if (!Number.isInteger(port)) throw new Error(`invalid port: ${values.port}`);
  if (values["public-url"]) process.env.PUBLIC_URL = (values["public-url"] as string).replace(/\/+$/, "");

  const { server, port: activePort, lanIp } = await createServer({ host: values.host as string, port, gameManager: new GameManager() });
  const publicBase = process.env.PUBLIC_URL || `http://${lanIp}:${activePort}`;

  const bar = "=".repeat(74);
  const out = (s = "") => process.stdout.write(s + "\n");
  out();
  out(`${COLOR_BOLD}${bar}${COLOR_RESET}`);
  out(`${COLOR_BOLD}   ONE OF THESE PEOPLE IS NOT LYING (PRODUCTION WEB SERVER)${COLOR_RESET}`);
  out("  Cloud / Internet Web Deployment Active");
  out(bar);
  out(`  • ${COLOR_BOLD}Public Base URL:${COLOR_RESET}         ${COLOR_GREEN}${publicBase}${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Player Join Link:${COLOR_RESET}        ${COLOR_CYAN}${publicBase}/join${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Lobby QR Code Screen:${COLOR_RESET}    ${COLOR_MAGENTA}${publicBase}/qr${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Stage Controller (Host):${COLOR_RESET} ${COLOR_GREEN}${publicBase}/control${COLOR_RESET} (Zero Spoilers)`);
  out(`  • ${COLOR_BOLD}Public TV / Display:${COLOR_RESET}     ${COLOR_GREEN}${publicBase}/display${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Admin Console:${COLOR_RESET}           ${COLOR_YELLOW}${publicBase}/admin${COLOR_RESET}`);
  out(`  • ${COLOR_BOLD}Health Check Endpoint:${COLOR_RESET}   ${publicBase}/health`);
  out(`  • ${COLOR_BOLD}Bound Address:${COLOR_RESET}           ${values.host}:${activePort}`);
  out(bar);
  out();

  const shutdown = (sig: string) => {
    out(`\n${COLOR_YELLOW}[SERVER] Received ${sig}. Shutting down web server gracefully...${COLOR_RESET}`);
    server.close(() => {
      out(`${COLOR_GREEN}[SERVER] Clean shutdown complete.${COLOR_RESET}`);
      process.exit(0);
    });
    setTimeout(() => process.exit(0), 2000).unref();
  };
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT", () => shutdown("SIGINT"));
}

main().catch((e) => {
  process.stderr.write(`${e instanceof Error ? e.message : String(e)}\n`);
  process.exit(1);
});
