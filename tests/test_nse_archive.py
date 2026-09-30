import csv
import hashlib
import io
import zipfile
from datetime import date

import pytest

from data import nse_archive as na


def zipped(name: str, text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, text)
    return buf.getvalue()


def fake(routes: dict[str, tuple[int, bytes]], script: dict[str, list] | None = None, blocked: set | None = None):
    """A stand-in for the network: {url: (status, body)}, 404 for any other address. `script` gives an address a list of answers used one by
    one first. Hosts in `blocked` refuse everything with 403, the way the exchange's firewall does; the two canary files exist otherwise."""
    calls: list[str] = []
    script = {k: list(v) for k, v in (script or {}).items()}
    blocked = blocked if blocked is not None else set()

    def opener(url):
        calls.append(url)
        if url.split("/")[2] in blocked:
            return 403, b""
        if script.get(url):
            return script[url].pop(0)
        if url in na.CANARY.values():
            return 200, b"canary"
        return routes.get(url, (404, b""))

    opener.calls = calls
    opener.blocked = blocked
    return opener


NO_SLEEP = lambda s: None  # noqa: E731
OLD, NEW = "archives.nseindia.com", "nsearchives.nseindia.com"


def test_urls_use_the_old_layout_before_the_switch_and_the_new_one_after_and_try_both_only_around_it():
    before, after = date(2024, 7, 5), date(2024, 7, 8)
    assert na.urls("cash", before) == ["https://archives.nseindia.com/content/historical/EQUITIES/2024/JUL/cm05JUL2024bhav.csv.zip",
                                       "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20240705_F_0000.csv.zip"]
    assert na.urls("cash", after)[0] == "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip"
    assert len(na.urls("cash", after)) == 2
    assert na.urls("fo", date(2016, 6, 1)) == ["https://archives.nseindia.com/content/historical/DERIVATIVES/2016/JUN/fo01JUN2016bhav.csv.zip"]
    assert na.urls("fo", date(2025, 1, 2)) == ["https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_20250102_F_0000.csv.zip"]
    assert na.urls("index", date(2018, 1, 31)) == ["https://archives.nseindia.com/content/indices/ind_close_all_31012018.csv"]
    assert na.urls("index", date(2025, 1, 2)) == ["https://nsearchives.nseindia.com/content/indices/ind_close_all_02012025.csv"]
    assert len(na.urls("index", date(2023, 11, 17))) == 2
    with pytest.raises(ValueError):
        na.urls("options", after)


def test_every_calendar_day_is_tried_because_special_sessions_fall_on_weekends():
    # Diwali Muhurat trading (2019-10-27, 2023-11-12) and budget-day or special Saturdays are real trading days with real files
    assert [d.isoformat() for d in na.days(date(2024, 8, 1), date(2024, 8, 5))] == ["2024-08-01", "2024-08-02", "2024-08-03", "2024-08-04", "2024-08-05"]


def test_fetch_day_takes_the_first_url_that_answers():
    d = date(2016, 6, 1)
    first = na.urls("cash", d)[0]
    op = fake({first: (200, b"zipbytes")})
    assert na.fetch_day("cash", d, op, NO_SLEEP) == ("ok", b"zipbytes", first)
    assert op.calls == [first]


def test_fetch_day_falls_back_to_the_other_layout_and_says_absent_only_when_every_layout_says_404():
    d = date(2024, 7, 8)
    old, new = na.urls("cash", d)[1], na.urls("cash", d)[0]
    assert na.fetch_day("cash", d, fake({old: (200, b"x")}), NO_SLEEP)[0:2] == ("ok", b"x")
    status, body, _ = na.fetch_day("cash", d, fake({}), NO_SLEEP)
    assert (status, body) == ("absent", None)


def test_fetch_day_does_not_retry_404_but_retries_server_trouble():
    d = date(2019, 12, 19)
    url = na.urls("cash", d)[0]
    op = fake({url: (200, b"ok")}, script={url: [(503, b""), (0, b""), (429, b"")]})
    assert na.fetch_day("cash", d, op, NO_SLEEP)[0] == "ok" and op.calls.count(url) == 4
    op = fake({}, script={url: [(404, b"")]})
    assert na.fetch_day("cash", d, op, NO_SLEEP)[0] == "absent" and op.calls.count(url) == 1


def test_fetch_day_gives_up_with_error_and_never_calls_a_bad_day_absent():
    d = date(2019, 12, 19)
    url = na.urls("cash", d)[0]
    op = fake({url: (503, b"")})
    status, body, _ = na.fetch_day("cash", d, op, NO_SLEEP, tries=3)
    assert (status, body) == ("error", None) and op.calls.count(url) == 3


def test_a_403_while_the_exchange_refuses_everything_is_a_block_and_never_an_absent_day():
    d = date(2019, 12, 19)
    with pytest.raises(na.Blocked):
        na.fetch_day("cash", d, fake({}, blocked={OLD}), NO_SLEEP)


def test_a_403_while_the_exchange_serves_other_files_is_a_denied_day_not_a_block():
    d = date(2012, 5, 2)
    url = na.urls("cash", d)[0]
    op = fake({url: (403, b"")})
    status, body, got = na.fetch_day("cash", d, op, NO_SLEEP)
    assert (status, body, got) == ("denied", None, url) and na.CANARY[OLD] in op.calls


def test_paced_keeps_every_request_at_least_the_gap_after_the_one_before():
    now = [0.0]
    starts = []

    def base(url):
        starts.append(now[0])
        return 200, b""

    def sleep(s):
        now[0] += s

    op = na.paced(base, 0.5, clock=lambda: now[0], sleep=sleep)
    for _ in range(4):
        op("u")
    assert all(b - a >= 0.5 - 1e-9 for a, b in zip(starts, starts[1:]))


def cash_url(d):
    return na.urls("cash", d)[0]


def test_sync_saves_the_raw_file_lists_it_and_does_not_fetch_a_listed_day_again(tmp_path):
    good = zipped("cm01JUN2016bhav.csv", "SYMBOL,SERIES\nNIFTYBEES,EQ\n")
    d = date(2016, 6, 1)
    op = fake({cash_url(d): (200, good)})
    res = na.sync(["cash"], d, date(2016, 6, 2), root=tmp_path, opener=op, sleep=NO_SLEEP, workers=1, retrieved=date(2026, 9, 30))
    assert res == {"ok": 1, "absent": 1, "denied": 0, "error": 0}                       # 2016-06-02 is not in the fake network: a real 404
    assert (tmp_path / "raw" / "nse" / "cash" / "2016-06-01.zip").read_bytes() == good
    rows = list(csv.DictReader((tmp_path / "nse_days.csv").open(newline="")))
    assert [(r["kind"], r["date"], r["status"]) for r in rows] == [("cash", "2016-06-01", "ok"), ("cash", "2016-06-02", "absent")]
    assert rows[0]["sha256"] == hashlib.sha256(good).hexdigest() and rows[0]["bytes"] == str(len(good)) and rows[1]["sha256"] == ""
    calls = len(op.calls)
    assert na.sync(["cash"], d, date(2016, 6, 2), root=tmp_path, opener=op, sleep=NO_SLEEP, workers=1) == {"ok": 0, "absent": 0, "denied": 0, "error": 0}
    assert len(op.calls) == calls                                                     # nothing fetched twice


def test_sync_asks_for_the_other_files_only_on_days_the_cash_file_exists(tmp_path):
    d1, d2 = date(2016, 6, 1), date(2016, 6, 2)
    body = zipped("a.csv", "x\n")
    op = fake({na.urls(k, d1)[0]: (200, body) for k in ("cash", "fo", "index")})
    res = na.sync(["cash", "fo", "index"], d1, d2, root=tmp_path, opener=op, sleep=NO_SLEEP, workers=1, retrieved=date(2026, 9, 30))
    assert res == {"ok": 3, "absent": 3, "denied": 0, "error": 0}
    asked_on_d2 = [u for u in op.calls if any(s in u for s in ("02JUN2016", "20160602", "02062016"))]
    assert asked_on_d2 == [na.urls("cash", d2)[0]]                                      # only the cash file: the market was closed
    rows = {(r["kind"], r["date"]): r for r in csv.DictReader((tmp_path / "nse_days.csv").open(newline=""))}
    assert rows[("fo", "2016-06-02")]["status"] == "absent" and rows[("fo", "2016-06-02")]["url"] == ""
    assert rows[("fo", "2016-06-01")]["status"] == "ok"


def test_sync_keeps_no_row_for_a_day_that_failed_so_it_is_tried_again(tmp_path):
    d = date(2016, 6, 1)
    url = cash_url(d)
    res = na.sync(["cash"], d, d, root=tmp_path, opener=fake({url: (503, b"")}), sleep=NO_SLEEP, workers=1)
    assert res == {"ok": 0, "absent": 0, "denied": 0, "error": 1} and not (tmp_path / "nse_days.csv").exists()
    good = zipped("a.csv", "x\n")
    assert na.sync(["cash"], d, d, root=tmp_path, opener=fake({url: (200, good)}), sleep=NO_SLEEP, workers=1)["ok"] == 1


def test_sync_waits_when_the_exchange_blocks_and_carries_on_when_it_stops(tmp_path):
    d = date(2016, 6, 1)
    good = zipped("a.csv", "x\n")
    op = fake({cash_url(d): (200, good)}, blocked={OLD})
    waits = []

    def sleep(s):
        waits.append(s)
        if len(waits) == 2:
            op.blocked.clear()                                                        # the block ends during the second wait

    res = na.sync(["cash"], d, d, root=tmp_path, opener=op, sleep=sleep, workers=1, retrieved=date(2026, 9, 30))
    assert res["ok"] == 1 and len(waits) == 2 and waits[1] > waits[0]                  # it waited longer the second time
    assert [r["status"] for r in csv.DictReader((tmp_path / "nse_days.csv").open(newline=""))] == ["ok"]


def test_sync_stops_with_blocked_after_too_many_waits_and_lists_nothing_wrong(tmp_path):
    d = date(2016, 6, 1)
    with pytest.raises(na.Blocked):
        na.sync(["cash"], d, d, root=tmp_path, opener=fake({}, blocked={OLD}), sleep=NO_SLEEP, workers=1, max_waits=2)
    assert not (tmp_path / "nse_days.csv").exists()


def test_sync_lists_a_denied_day_as_denied_with_no_hash(tmp_path):
    d = date(2012, 5, 2)
    res = na.sync(["cash"], d, d, root=tmp_path, opener=fake({cash_url(d): (403, b"")}), sleep=NO_SLEEP, workers=1, retrieved=date(2026, 9, 30))
    assert res["denied"] == 1
    (row,) = list(csv.DictReader((tmp_path / "nse_days.csv").open(newline="")))
    assert (row["status"], row["sha256"]) == ("denied", "") and na.verify_days(tmp_path) == []


def test_verify_days_passes_a_clean_folder_and_finds_a_changed_or_unlisted_or_malformed_entry(tmp_path):
    d = date(2016, 6, 1)
    good = zipped("a.csv", "x\n")
    na.sync(["cash"], d, d, root=tmp_path, opener=fake({cash_url(d): (200, good)}), sleep=NO_SLEEP, workers=1)
    assert na.verify_days(tmp_path) == []
    raw = tmp_path / "raw" / "nse" / "cash" / "2016-06-01.zip"
    raw.write_bytes(good + b"!")
    assert any("2016-06-01" in p and "hash" in p for p in na.verify_days(tmp_path))
    raw.unlink()
    assert na.verify_days(tmp_path) == []                                              # a clone has no raw files: hashes are the record
    assert any("missing" in p for p in na.verify_days(tmp_path, need_raw=True))
    with (tmp_path / "nse_days.csv").open("a", newline="") as f:
        f.write("cash,2016-06-01,ok,5,abc,u,2026-09-30\n")                              # the same day twice, with a short hash
    problems = na.verify_days(tmp_path)
    assert any("twice" in p for p in problems) and any("sha256" in p for p in problems)


def test_verify_days_finds_a_hash_on_an_absent_day_and_an_unknown_status(tmp_path):
    with (tmp_path / "nse_days.csv").open("w", newline="") as f:
        f.write("kind,date,status,bytes,sha256,url,retrieved\n")
        f.write("cash,2016-06-04,absent,0," + "a" * 64 + ",u,2026-09-30\n")
        f.write("cash,2016-06-05,forbidden,0,,u,2026-09-30\n")
    problems = na.verify_days(tmp_path)
    assert any("2016-06-04" in p and "has a hash" in p for p in problems)
    assert any("2016-06-05" in p and "not ok, absent or denied" in p for p in problems)
