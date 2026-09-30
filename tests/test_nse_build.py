import csv
import io
import zipfile
from datetime import date

from data import nse_archive as na
from data import nse_build as nb

CASH_HEAD = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,"
FO_HEAD = "INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP,"
IDX_HEAD = "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield"


def zipped(lines):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("f.csv", "\n".join(lines) + "\n")
    return buf.getvalue()


def put(root, kind, d, raw):
    """Write a raw file and list it, the way the downloader does."""
    p = na.raw_path(root, kind, d)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    import hashlib
    na.append_days([dict(kind=kind, date=d.isoformat(), status="ok", bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), url="u", retrieved="2026-09-30")], root)


def make_root(tmp_path):
    d1, d2 = date(2016, 6, 1), date(2016, 6, 2)
    put(tmp_path, "cash", d1, zipped([CASH_HEAD, "NIFTYBEES,EQ,827,831.75,826,828.85,829.05,826.68,32150,26661845.83,01-JUN-2016,1158,INF732E01011,",
                                     "GOLDBEES,EQ,2500,2510,2490,2505,2505,2495,1000,2500000,01-JUN-2016,50,INF204KB16I7,"]))
    put(tmp_path, "cash", d2, zipped([CASH_HEAD, "NIFTYBEES,EQ,829,835,828,834.5,834,828.85,40000,33000000,02-JUN-2016,1200,INF732E01011,"]))
    put(tmp_path, "fo", d1, zipped([FO_HEAD, "FUTIDX,NIFTY,30-Jun-2016,0,XX,8200,8224.9,8178.3,8194.55,8194.55,125472,771709.04,21499350,-130800,01-JUN-2016,"]))
    put(tmp_path, "index", d1, ("\n".join([IDX_HEAD, "Nifty 50,01-06-2016,8200,8224.9,8178.3,8194.55,1,0.1,1,1,21.5,3.1,1.3"]) + "\n").encode())
    # an absent day and a holiday: nothing to read
    na.append_days([dict(kind="cash", date="2016-06-03", status="absent", bytes=0, sha256="", url="u", retrieved="2026-09-30")], tmp_path)
    return tmp_path


def read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def test_build_writes_one_sorted_csv_per_kind_from_the_raw_files_that_are_listed(tmp_path):
    root = make_root(tmp_path)
    counts = nb.build(root, etfs={"NIFTYBEES", "GOLDBEES"}, futures={"NIFTY"}, indices={"Nifty 50"})
    assert counts == {"cash": 3, "fo": 1, "index": 1}
    etf = read(root / "processed" / "nse_etf_daily.csv")
    assert [(r["date"], r["symbol"], r["close"]) for r in etf] == [("2016-06-01", "GOLDBEES", "2505"), ("2016-06-01", "NIFTYBEES", "828.85"),
                                                                    ("2016-06-02", "NIFTYBEES", "834.5")]
    assert read(root / "processed" / "nse_index_futures_daily.csv")[0]["expiry"] == "2016-06-30"
    assert read(root / "processed" / "nse_index_daily.csv")[0]["pe"] == "21.5"


def test_build_is_repeatable_byte_for_byte_and_writes_lf_line_ends(tmp_path):
    root = make_root(tmp_path)
    nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})
    first = {p.name: p.read_bytes() for p in (root / "processed").iterdir()}
    nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})
    assert {p.name: p.read_bytes() for p in (root / "processed").iterdir()} == first
    assert all(b"\r" not in v for v in first.values())


def test_build_refuses_a_raw_file_whose_hash_is_not_the_listed_one(tmp_path):
    import pytest
    root = make_root(tmp_path)
    na.raw_path(root, "cash", date(2016, 6, 1)).write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})


def test_build_names_a_listed_day_whose_raw_file_is_missing_instead_of_skipping_it(tmp_path):
    import pytest
    root = make_root(tmp_path)
    na.raw_path(root, "fo", date(2016, 6, 1)).unlink()
    with pytest.raises(ValueError, match="missing"):
        nb.build(root, {"NIFTYBEES"}, {"NIFTY"}, {"Nifty 50"})
