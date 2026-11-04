"""
Production Web Server Entrypoint for 'One of These People Is Not Lying'.
Optimized for cloud platforms (Render, Railway, Fly.io, Heroku, AWS, DigitalOcean) and Docker.

Features:
- Dynamically respects $PORT environment variable assigned by cloud hosts.
- Binds to 0.0.0.0 by default for global/external internet access.
- Headless (no automatic desktop browser popping).
- Handles SIGTERM and SIGINT for zero-downtime container shutdown.
- Supports $PUBLIC_URL for custom domain or reverse-proxy QR code resolution.
"""

import argparse
import os
import signal
import sys
import time

# Ensure imports work whether run from repo root or inside deployment/ container
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
for p in (current_dir, parent_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.game import GameManager
from src.server import create_server, COLOR_BOLD, COLOR_CYAN, COLOR_GREEN, COLOR_RESET, COLOR_YELLOW, COLOR_MAGENTA


def main():
    parser = argparse.ArgumentParser(description="One of These People Is Not Lying - Production Web Server")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host IP to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5050")), help="Port to bind (default: $PORT or 5050)")
    parser.add_argument("--public-url", default=os.environ.get("PUBLIC_URL", ""), help="Publicly accessible base URL (e.g., https://game.example.com)")
    args = parser.parse_args()

    if args.public_url:
        os.environ["PUBLIC_URL"] = args.public_url.rstrip("/")

    game_manager = GameManager()
    server, active_port, lan_ip = create_server(host=args.host, port=args.port, game_manager=game_manager)

    public_base = os.environ.get("PUBLIC_URL") or f"http://{lan_ip}:{active_port}"

    print("")
    print(f"{COLOR_BOLD}{'=' * 74}{COLOR_RESET}")
    print(f"{COLOR_BOLD}   ONE OF THESE PEOPLE IS NOT LYING (PRODUCTION WEB SERVER){COLOR_RESET}")
    print(f"  Cloud / Internet Web Deployment Active")
    print(f"{'=' * 74}")
    print(f"  • {COLOR_BOLD}Public Base URL:{COLOR_RESET}         {COLOR_GREEN}{public_base}{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Player Join Link:{COLOR_RESET}        {COLOR_CYAN}{public_base}/join{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Lobby QR Code Screen:{COLOR_RESET}    {COLOR_MAGENTA}{public_base}/qr{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Stage Controller (Host):{COLOR_RESET}{COLOR_GREEN}{public_base}/control{COLOR_RESET} (Zero Spoilers)")
    print(f"  • {COLOR_BOLD}Public TV / Display:{COLOR_RESET}     {COLOR_GREEN}{public_base}/display{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Admin Console:{COLOR_RESET}     {COLOR_YELLOW}{public_base}/admin{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Health Check Endpoint:{COLOR_RESET}   {public_base}/health")
    print(f"  • {COLOR_BOLD}Bound Address:{COLOR_RESET}           {args.host}:{active_port}")
    print(f"{'=' * 74}")
    print("")

    # Graceful shutdown handler for container SIGTERM / SIGINT
    def handle_shutdown(signum, frame):
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        sys.stdout.write(f"\n{COLOR_YELLOW}[SERVER] Received {sig_name}. Shutting down web server gracefully...{COLOR_RESET}\n")
        sys.stdout.flush()
        server.shutdown()
        server.server_close()
        sys.stdout.write(f"{COLOR_GREEN}[SERVER] Clean shutdown complete.{COLOR_RESET}\n")
        sys.stdout.flush()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
