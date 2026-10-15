"""Puts the complete data of each class back in classes/: the zips live in the data-v1 GitHub release, not in git, so a clone stays small.
Every file is checked against classes/SHA256SUMS; one already there and matching is kept.

    python -m tools.download_classes          # all nine classes; python -m tools.download_classes 2 9 fetches classes 2 and 9
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "classes"
RELEASE = "https://github.com/fbivinay/Intelligent_Investment/releases/download/data-v1/"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sums(out: Path = OUT) -> dict[str, str]:
    """classes/SHA256SUMS as {zip name: digest}."""
    return {name: digest for digest, name in (line.split(maxsplit=1) for line in (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if line)}


def download(only: set[str] | None = None, out: Path = OUT, base: str = RELEASE, fetch=urllib.request.urlretrieve) -> list[str]:
    """Fetches the zips of the classes in only (all when None) that are missing or differ, and returns their names. A file whose checksum does
    not match is deleted and stops the run, so classes/ never holds a corrupt zip."""
    got = []
    for name, digest in sums(out).items():
        if only and name.split("_", 1)[0] not in only:
            continue
        target = out / name
        if target.exists() and sha256(target) == digest:
            continue
        part = target.with_name(name + ".part")
        fetch(base + name, part)
        if sha256(part) != digest:
            part.unlink()
            raise SystemExit(f"{name}: the download does not match classes/SHA256SUMS")
        part.replace(target)
        got.append(name)
        print(f"{name}: {target.stat().st_size / 1e6:,.1f} MB", flush=True)
    return got


if __name__ == "__main__":
    got = download(set(sys.argv[1:]) or None)
    print(f"{len(got)} downloaded, the rest already here" if got else "every class already here")
