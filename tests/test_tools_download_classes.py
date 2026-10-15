"""tools/download_classes.py: only missing or changed zips are fetched, only the classes asked for, and a corrupt download never lands."""
import hashlib

import pytest

from tools import classes as C
from tools import download_classes as D


def _release(tmp_path, files):
    """A fake release: the files, their SHA256SUMS written by tools.classes, and a fetch that copies from it."""
    release = tmp_path / "release"
    release.mkdir()
    for name, data in files.items():
        (release / name).write_bytes(data)
    C.write_sums(release)
    out = tmp_path / "classes"
    out.mkdir()
    (out / "SHA256SUMS").write_bytes((release / "SHA256SUMS").read_bytes())
    calls = []

    def fetch(url, dst):
        calls.append(url.rsplit("/", 1)[1])
        dst.write_bytes((release / url.rsplit("/", 1)[1]).read_bytes())

    return out, fetch, calls


def test_missing_zips_are_fetched_and_a_matching_one_is_kept(tmp_path):
    out, fetch, calls = _release(tmp_path, {"1_share_prices_part1.zip": b"a", "2_etf_prices.zip": b"b"})
    (out / "2_etf_prices.zip").write_bytes(b"b")
    assert D.download(out=out, base="https://x/", fetch=fetch) == ["1_share_prices_part1.zip"]
    assert calls == ["1_share_prices_part1.zip"] and (out / "1_share_prices_part1.zip").read_bytes() == b"a"
    assert D.download(out=out, base="https://x/", fetch=fetch) == []


def test_only_the_classes_asked_for_are_fetched(tmp_path):
    out, fetch, calls = _release(tmp_path, {"1_share_prices_part1.zip": b"a", "9_tax_and_charge_rules.zip": b"z"})
    D.download({"9"}, out=out, base="https://x/", fetch=fetch)
    assert calls == ["9_tax_and_charge_rules.zip"] and not (out / "1_share_prices_part1.zip").exists()


def test_a_download_that_does_not_match_its_checksum_is_refused(tmp_path):
    out, _, _ = _release(tmp_path, {"2_etf_prices.zip": b"b"})
    with pytest.raises(SystemExit, match="does not match"):
        D.download(out=out, base="https://x/", fetch=lambda url, dst: dst.write_bytes(b"tampered"))
    assert not any(out.glob("2_etf_prices.zip*"))


def test_the_published_sums_name_every_class():
    got = D.sums()
    assert {n.split("_", 1)[0] for n in got} == {str(k) for k in range(1, 10)}
    assert all(len(d) == len(hashlib.sha256().hexdigest()) for d in got.values())
