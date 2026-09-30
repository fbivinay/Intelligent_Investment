import json
from datetime import date

from data.fetch_yahoo import save
from engine.report import main, render_html
from engine.scenario import Result
from engine.trace import const, sub
from tests.helpers import make_rules
from tests.synth_charges import CHARGES
from tests.synth_tax import TAX


def fake_result():
    a, b = const("<b>Cost</b>", "100.123456789"), const("Fee", "0.5")
    net = sub("Net", a, b)
    w = {k: net for k in ("initial", "gross_profit", "gross_end", "buy_charges", "sale_charges", "amc",
                          "account_opening", "charges", "tax", "net")}
    return Result(net, w, 10, date(2020, 1, 1), date(2021, 1, 1), True)


def test_report_shows_exact_values_behind_an_info_button_and_escapes_text():
    html = render_html("T & <script>", [("Sold", fake_result())], ["a note <i>"])
    assert "ⓘ" in html and "99.623456789" in html          # exact, unrounded value is in the trace
    assert "&lt;b&gt;Cost&lt;/b&gt;" in html and "<script>" not in html and "&lt;i&gt;" in html
    assert "None used." in html                             # no non-primary rules involved


def test_report_has_a_row_for_the_account_opening_fee():
    assert "Account opening fee" in render_html("T", [("Sold", fake_result())], [])


def test_command_line_writes_a_report_with_both_views(tmp_path):
    ts = [1517357100 + 86400 * i for i in range(0, 900) if (i % 7) < 5]     # weekdays from 2018-01-31
    price = [100 + i * 0.05 for i in range(len(ts))]
    raw = json.dumps({"chart": {"result": [{"meta": {"gmtoffset": 19800}, "timestamp": ts,
                      "indicators": {"quote": [{"high": price, "close": price}]}}]}}).encode()
    save("ETF.NS", raw, date(2026, 9, 29), root=tmp_path)
    make_rules(tmp_path / "rules", {**CHARGES, **TAX})
    out = main(["--symbol", "ETF", "--amount", "100000", "--start", "2018-02-01", "--end", "2020-06-01",
                "--rules", str(tmp_path / "rules"), "--data", str(tmp_path / "processed"),
                "--out", str(tmp_path / "out" / "r.html")])
    html = out.read_text(encoding="utf-8")
    assert "If sold on the end date" in html and "If still holding" in html and "ⓘ" in html
    assert "Dividends in the source: 0" in html
