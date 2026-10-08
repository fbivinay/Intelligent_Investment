"""tools/classes.py: each kind of file is measured from its contents, and the class list names every dataset once."""
import numpy as np

from tools import classes as C


def test_each_kind_of_file_is_measured(tmp_path):
    (tmp_path / "a.csv").write_text("date,x\n2020-01-02,1\n2021-05-06,2\n2019-12-31,3\n", encoding="utf-8")
    (tmp_path / "m.csv").write_text("date,close\n2015-01-09 09:15:00,1\n2015-01-09 09:16:00,2\n2026-05-15 15:29:00,3\n", encoding="utf-8")
    days = tmp_path / "days"
    days.mkdir()
    for d in ("2016-01-04", "2016-01-01"):
        (days / f"{d}.zip").write_bytes(b"x")
    np.savez(tmp_path / "d.npz", days=np.array(["2016-01-01", "2016-01-04"], dtype="datetime64[D]"))
    np.save(tmp_path / "p.npy", np.zeros((5, 2)))
    got = {k: C.measure(str(tmp_path / p), k) for k, p in (("csv", "a.csv"), ("minute", "m.csv"), ("zipdir", "days"), ("npz", "d.npz"), ("npy", "p.npy"))}
    assert {k: (v["rows"], v["files"], v["first"], v["last"]) for k, v in got.items()} == {
        "csv": (3, 1, "2019-12-31", "2021-05-06"), "minute": (3, 1, "2015-01-09", "2026-05-15"), "zipdir": ("", 2, "2016-01-01", "2016-01-04"),
        "npz": (2, 1, "2016-01-01", "2016-01-04"), "npy": (5, 1, "", "")}


def test_every_dataset_is_listed_once_and_git_is_matched_by_folder():
    paths = [p for *_, sets in C.CLASSES for _, p, _ in sets]
    assert len(C.CLASSES) == 9 and len(paths) == len(set(paths)) and all(sets for *_, sets in C.CLASSES)
    assert C.in_git("rules", {"rules/tax/slabs.toml"}) and not C.in_git("data/raw/nse", {"data/raw/nse_web/a.json"})


def test_the_website_gets_rows_only_where_a_file_has_them():
    inv = [{"class": 1, "name": "n", "what": "w", "source": "s", "used_by": "u", "from": "2016-01-01", "to": "2026-09-30",
            "datasets": [{"dataset": "a", "rows": "", "files": 3, "first": "", "last": ""}, {"dataset": "b", "rows": 7, "files": 1, "first": "2016-01-01", "last": "2026-09-30"}]}]
    assert [(d["rows"], d["files"]) for d in C.summary(inv)[0]["datasets"]] == [(None, 3), (7, 1)]
