import re
import shutil
import subprocess
import pytest
from src import templates

PAGES = {
    "admin": lambda: templates.get_admin_html(5050, "127.0.0.1"),
    "qr": lambda: templates.get_qr_html(5050, "127.0.0.1"),
    "join": lambda: templates.get_join_html(5050),
    "display": lambda: templates.get_display_html(5050),
    "control": lambda: templates.get_stage_control_html(5050),
    "login": templates.get_admin_login_html,
}


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
@pytest.mark.parametrize("page", PAGES)
def test_inline_scripts_parse(page, tmp_path):
    """Python string escaping inside the templates can silently break the JS; parse every inline script."""
    for i, js in enumerate(re.findall(r"<script>(.*?)</script>", PAGES[page](), re.S)):
        f = tmp_path / f"{page}{i}.js"
        f.write_text(js)
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
