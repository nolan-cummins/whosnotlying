import glob
import os
from scripts.lint_packs import lint

PACKS = glob.glob(os.path.join(os.path.dirname(__file__), "..", "packs", "*.json"))


def test_shipped_packs_have_no_lint_errors():
    errors, _ = lint(PACKS)
    assert errors == []
