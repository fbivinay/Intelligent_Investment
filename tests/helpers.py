"""Test-only helpers: write throwaway rule tables so engine logic is tested without real rates."""
from pathlib import Path

from engine.rules import Rules

STAMP = 'source = "test fixture"\nverified_on = 2026-01-01\nconfidence = "primary"\n'


def table(keys: list[str], rows: list[str], coverage: str = "2010-04-01", extra_meta: str = "") -> str:
    """rows: `field = value` lines. A row that sets its own `confidence` also sets source and verified_on."""
    head = f"[meta]\nkeys = {keys!r}\ncoverage_from = {coverage}\n{extra_meta}\n".replace("'", '"')
    body = "".join(f"[[row]]\n{r.strip()}\n{'' if 'confidence' in r else STAMP}\n" for r in rows)
    return head + body


def make_rules(tmp_path: Path, files: dict[str, str]) -> Rules:
    for name, text in files.items():
        p = tmp_path / (name.replace(".", "/") + ".toml")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return Rules.load(tmp_path)
