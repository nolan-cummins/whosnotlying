import subprocess
import sys
from unittest.mock import patch, MagicMock
from src.main import main


def test_main_module_help():
    """Verify python3 -m src.main --help executes cleanly without import or name errors."""
    proc = subprocess.run([sys.executable, "-m", "src.main", "--help"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "One of These People Is Not Lying" in proc.stdout


def test_main_entrypoint_initialization():
    """Verify main() initializes GameManager with empty lobby and passes arguments cleanly."""
    with patch("src.main.create_server") as mock_create_server, \
         patch("src.main.open_browser_tabs_delayed") as mock_open_tabs:
        mock_server = MagicMock()
        mock_server.serve_forever.side_effect = KeyboardInterrupt()
        mock_create_server.return_value = (mock_server, 5050, "127.0.0.1")

        # Call main with --no-browser and custom port
        main(["--no-browser", "--port", "5055"])

        assert mock_create_server.called
        args, kwargs = mock_create_server.call_args
        assert kwargs["port"] == 5055
        gm = kwargs["game_manager"]
        assert len(gm.players) == 0
        assert gm.guesser_ids == []
        assert gm.truth_teller_ids == []
        assert not mock_open_tabs.called
