import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).parent / "js" / "nse_web_collect_test.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_collector_behaves_against_a_fake_site():
    """data/nse_web_collect.js runs in the owner's browser; here it runs under node against a fake NSE (row cap, refusals, holiday-moved expiries)."""
    r = subprocess.run(["node", str(JS)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    assert "collector tests passed" in r.stdout
