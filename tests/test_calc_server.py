import gzip
import io
import json
import urllib.parse
import subprocess
import sys
from pathlib import Path

import pytest

from calc import api, server as SV

ROOT = Path(__file__).resolve().parents[1]
PARAMS = {"amount": 200000, "start": "2018-06-01", "end": "2019-06-03", "level": "Conservative", "compare": ["GOLDBEES"], "horizon": 1}


def test_a_calc_request_answers_the_same_json_as_calculate_and_a_bad_one_is_a_400():
    status, headers, body = SV.respond("/api/calc", json.dumps(PARAMS).encode(), accept_gzip=False)
    assert status == 200 and headers["content-type"] == "application/json" and json.loads(body) == api.calculate(PARAMS)
    status, _, body = SV.respond("/api/calc", json.dumps({**PARAMS, "end": "2010-01-01"}).encode(), accept_gzip=False)
    assert status == 400 and "error" in json.loads(body)


def test_answers_are_gzipped_when_the_client_accepts_it_and_unknown_paths_are_404():
    status, headers, body = SV.respond("/api/calc", json.dumps(PARAMS).encode(), accept_gzip=True)
    assert headers["content-encoding"] == "gzip" and json.loads(gzip.decompress(body)) == api.calculate(PARAMS)
    assert SV.respond("/api/nothing", b"{}", accept_gzip=False)[0] == 404
    assert SV.respond("/api/calc", b"not json", accept_gzip=False)[0] == 400


def test_the_preview_route_serves_the_fyers_preview():
    status, _, body = SV.respond("/api/preview", json.dumps({k: v for k, v in PARAMS.items() if k != "compare"}).encode(), accept_gzip=False)
    out = json.loads(body)
    assert status == 200 and out["order_days"] and "preview" in out


def test_the_bundle_holds_the_code_rules_data_and_artifact_and_runs_without_numba(tmp_path):
    from tools import bundle_site as BS
    lib = BS.bundle(tmp_path / "_lib")
    for rel in ("calc/api.py", "engine/tax.py", "research/sim.py", "rules/tax/slabs.toml", "data/processed/etf_daily_adjusted.csv", "research/out/signal/manifest.json",
                "numba/__init__.py"):
        assert (lib / rel).exists(), rel
    assert not (lib / "research" / "dl").exists() and not (lib / "data" / "raw").exists()
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import numba; assert getattr(numba, 'STAND_IN', False); from calc import api; "
            "print(json.dumps(api.calculate(json.loads(sys.argv[2]))['results'][0]['net']['exact']))")
    out = subprocess.run([sys.executable, "-c", code, str(lib), json.dumps(PARAMS)], capture_output=True, text=True, cwd=tmp_path, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    assert json.loads(out.stdout.strip()) == api.calculate(PARAMS)["results"][0]["net"]["exact"]


def _load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"vercel_{name}", ROOT / "site" / "api" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.handler


@pytest.mark.parametrize("name,params,check", [
    ("calc", PARAMS, lambda out: out == api.calculate(PARAMS)),
    ("preview", {k: v for k, v in PARAMS.items() if k != "compare"}, lambda out: "order_days" in out),
])
def test_the_vercel_functions_answer_over_http_like_the_local_server(name, params, check):
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _load(name))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/api/{name}", data=json.dumps(params).encode(), headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            assert resp.status == 200 and check(json.loads(resp.read()))
        q = urllib.parse.quote(json.dumps(params))
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_port}/api/{name}?q={q}", timeout=600) as resp:
            assert check(json.loads(resp.read()))
    finally:
        srv.shutdown()
