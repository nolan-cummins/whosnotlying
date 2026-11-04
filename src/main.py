"""
Main entry point for 'One of These People Is Not Lying'.
Starts the HTTP server, spawns browser tabs (Admin Console + Lobby QR tab), and streams live logs.
"""

import argparse
import os
import sys
import threading
import time
import webbrowser
from typing import Optional

from src.game import GameManager
from src.server import create_server, COLOR_BOLD, COLOR_CYAN, COLOR_GREEN, COLOR_RESET, COLOR_YELLOW, COLOR_MAGENTA


def open_browser_tabs_delayed(control_url: str, qr_url: str, delay: float = 0.6):
    """Wait briefly for server to bind then launch both Stage Controller and Lobby QR in separate tabs."""
    def _worker():
        time.sleep(delay)
        try:
            # Tab 1: Stage Controller (Spoiler-free stage controller for Admin participation)
            sys.stdout.write(f"{COLOR_CYAN}[BROWSER]{COLOR_RESET} Opening Stage Controller (zero spoilers) in default browser tab...\n")
            sys.stdout.flush()
            webbrowser.open(control_url)

            # Tab 2: Lobby QR Code in a separate browser tab
            time.sleep(0.5)
            sys.stdout.write(f"{COLOR_CYAN}[BROWSER]{COLOR_RESET} Opening Lobby QR code in a separate browser tab...\n")
            sys.stdout.flush()
            webbrowser.open(qr_url)
        except Exception as e:
            sys.stderr.write(f"Could not open browser automatically: {e}\n")
            sys.stderr.flush()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


def main(argv: Optional[list] = None):
    parser = argparse.ArgumentParser(description="One of These People Is Not Lying - Game Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5050, help="Initial port to bind (default: 5050)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open default browser")
    parser.add_argument("--test-bench", action="store_true", help="Launch in test bench mode")
    parser.add_argument("--players-file", default=None, help="Custom players file")
    args = parser.parse_args(argv)

    is_test_bench = args.test_bench or (os.environ.get("TEST_BENCH") == "1")
    # When launched normally (not via the testbench), start with an empty lobby
    game_manager = GameManager(seed_samples=False, players_file=args.players_file, empty_lobby=not is_test_bench)
    server, active_port, lan_ip = create_server(host=args.host, port=args.port, game_manager=game_manager)

    local_base = f"http://127.0.0.1:{active_port}"
    control_url = f"{local_base}/control"
    admin_url = f"{local_base}/admin"
    qr_url = f"{local_base}/qr"
    join_url = f"http://{lan_ip}:{active_port}/join"
    display_url = f"{local_base}/display"

    # Terminal monitoring banner
    print("")
    print(f"{COLOR_BOLD}{'=' * 74}{COLOR_RESET}")
    print(f"{COLOR_BOLD}   ONE OF THESE PEOPLE IS NOT LYING{COLOR_RESET}")
    print(f"  Game Server & Host Stage Monitor")
    print(f"{'=' * 74}")
    print(f"  • {COLOR_BOLD}Stage Controller (Host):{COLOR_RESET} {COLOR_GREEN}{control_url}{COLOR_RESET}  (Zero Spoilers)")
    print(f"  • {COLOR_BOLD}Lobby QR Code (Tab):{COLOR_RESET}     {COLOR_MAGENTA}{qr_url}{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Phone Join Link:{COLOR_RESET}         {COLOR_CYAN}{join_url}{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Public TV/Display:{COLOR_RESET}       {COLOR_GREEN}{display_url}{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Full Admin Dossier:{COLOR_RESET}         {COLOR_YELLOW}{admin_url}{COLOR_RESET}  (Contains Spoilers)")
    print(f"  • {COLOR_BOLD}Status:{COLOR_RESET}                  {COLOR_GREEN}ONLINE & MONITORING{COLOR_RESET}")
    print(f"  • {COLOR_BOLD}Stop Server:{COLOR_RESET}             Press {COLOR_YELLOW}Ctrl+C{COLOR_RESET} at any time")
    print(f"{'=' * 74}")
    print("")

    if not args.no_browser:
        open_browser_tabs_delayed(control_url, qr_url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}[SERVER] Shutting down gracefully...{COLOR_RESET}")
    finally:
        server.server_close()
        print(f"{COLOR_GREEN}[SERVER] Server stopped. Goodbye!{COLOR_RESET}")


if __name__ == "__main__":
    main()
