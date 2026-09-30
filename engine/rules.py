"""Dated rule tables loaded from rules/**/*.toml. Nothing else in the engine knows a rate."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from engine.money import D
from engine.trace import RuleRef

CONFIDENCE = {"primary", "secondary", "assumed"}
RESERVED = {"from", "to", "source", "verified_on", "confidence", "note"}
ONE_DAY = timedelta(days=1)


class RuleTableError(ValueError):
    """A rules file is malformed. Raised while loading, never at lookup time."""


class RuleNotFound(LookupError):
    """No row covers this date and key. The engine never guesses a default."""


def rule_id(table: str, key: tuple[tuple[str, str], ...]) -> str:
    return f"{table}[{','.join(f'{k}={v}' for k, v in key)}]"


@dataclass(frozen=True)
class Row:
    table: str
    key: tuple[tuple[str, str], ...]
    valid_from: date
    valid_to: date | None
    data: dict
    ref: RuleRef

    def dec(self, field: str) -> Decimal:
        return D(self.data[field])

    @property
    def value(self) -> Decimal:
        return self.dec("value")

    def covers(self, on: date) -> bool:
        return self.valid_from <= on and (self.valid_to is None or on <= self.valid_to)


class Table:
    def __init__(self, name: str, raw: dict, path: Path):
        meta = raw.get("meta")
        if not isinstance(meta, dict) or "keys" not in meta or type(meta.get("coverage_from")) is not date:
            raise RuleTableError(f"{path}: [meta] needs keys=[...] and coverage_from=<date>")
        self.name, self.path = name, path
        self.keys: list[str] = list(meta["keys"])
        self.open_ended: bool = meta.get("open_ended", True)
        # "day": looked up by the date of a transaction, rows may change on any day. "financial_year": looked up by the year, so
        # every row must start on 1 April and end on 31 March (a change in mid-year would be answered for the whole year).
        self.granularity: str = meta.get("granularity", "day")
        if self.granularity not in ("day", "financial_year"):
            raise RuleTableError(f"{path}: granularity must be 'day' or 'financial_year', not {self.granularity!r}")
        late = [({k: str(v) for k, v in e.items() if k != "from"}, e["from"])
                for e in meta.get("late_keys", [])]
        if self.granularity == "financial_year":
            for _, f in late:
                self._check_year_edge(f, "starts", path)
        self.groups: dict[tuple, list[Row]] = {}
        for i, r in enumerate(raw.get("row", [])):
            row = self._row(r, i)
            self.groups.setdefault(row.key, []).append(row)
        if not self.groups:
            raise RuleTableError(f"{path}: table has no [[row]] entries")
        for key, rows in self.groups.items():
            rows.sort(key=lambda r: r.valid_from)
            start = next((f for d, f in late if d == dict(key)), meta["coverage_from"])
            if rows[0].valid_from != start:  # earlier would answer for dates the rules were never checked for
                raise RuleTableError(f"{path} {dict(key)}: first row starts {rows[0].valid_from}, "
                                     f"must start exactly on {start}")
            for a, b in zip(rows, rows[1:]):
                if a.valid_to is None or b.valid_from != a.valid_to + ONE_DAY:
                    raise RuleTableError(f"{path} {dict(key)}: gap or overlap between "
                                         f"{a.valid_from}..{a.valid_to} and {b.valid_from}")
            if self.open_ended and rows[-1].valid_to is not None:
                raise RuleTableError(f"{path} {dict(key)}: last row must be open-ended (no `to`)")

    def _row(self, r: dict, i: int) -> Row:
        at = f"{self.path} row {i}"
        for f in ("from", "source", "verified_on", "confidence"):
            if f not in r:
                raise RuleTableError(f"{at}: missing `{f}`")
        for f in ("from", "verified_on", *(("to",) if "to" in r else ())):
            if type(r[f]) is not date:
                raise RuleTableError(f"{at}: `{f}` must be a TOML date")
        if r["confidence"] not in CONFIDENCE:
            raise RuleTableError(f"{at}: confidence must be one of {sorted(CONFIDENCE)}")
        if not str(r["source"]).strip():
            raise RuleTableError(f"{at}: `source` is empty")
        if r["confidence"] == "assumed" and not str(r.get("note", "")).strip():
            raise RuleTableError(f"{at}: assumed rows need a `note` saying why")
        if "to" in r and r["to"] < r["from"]:
            raise RuleTableError(f"{at}: `to` is before `from`")
        if r["verified_on"] > date.today():
            raise RuleTableError(f"{at}: `verified_on` is in the future")
        missing = [k for k in self.keys if k not in r]
        if missing:
            raise RuleTableError(f"{at}: missing key field(s) {missing}")
        key = tuple((k, str(r[k])) for k in self.keys)
        data = {k: v for k, v in r.items() if k not in RESERVED and k not in self.keys}
        ref = RuleRef(rule_id(self.name, key), r["from"], r.get("to"), r["source"],
                      r["verified_on"], r["confidence"], str(r.get("note", "")).strip())
        if self.granularity == "financial_year":
            self._check_year_edge(r["from"], "starts", at)
            if "to" in r:
                self._check_year_edge(r["to"], "ends", at)
        return Row(self.name, key, r["from"], r.get("to"), data, ref)

    @staticmethod
    def _check_year_edge(d: date, what: str, at) -> None:
        good = (d.month, d.day) == ((4, 1) if what == "starts" else (3, 31))
        if not good:
            raise RuleTableError(f"{at}: a financial-year table row {what} on {d}, "
                                 f"but must {'start on 1 April' if what == 'starts' else 'end on 31 March'}")

    def _key(self, key: dict) -> tuple[tuple[str, str], ...]:
        if set(key) != set(self.keys):
            raise TypeError(f"{self.name} needs key fields {self.keys}, got {sorted(key)}")
        return tuple((k, str(key[k])) for k in self.keys)

    def has(self, on: date, **key) -> bool:
        return any(r.covers(on) for r in self.groups.get(self._key(key), ()))

    def at(self, on: date, **key) -> Row:
        k = self._key(key)
        for row in self.groups.get(k, ()):
            if row.covers(on):
                return row
        raise RuleNotFound(f"{self.name} {dict(k)} on {on}: no rule covers this date")

    def _fy_only(self) -> None:
        if self.granularity != "financial_year":
            raise RuleTableError(f"{self.name} is looked up by date, not by financial year")

    def at_fy(self, fy: int, **key) -> Row:
        """The row in force for the financial year that starts on 1 April `fy` (tables that are looked up by year only)."""
        self._fy_only()
        return self.at(date(fy, 4, 1), **key)

    def has_fy(self, fy: int, **key) -> bool:
        self._fy_only()
        return self.has(date(fy, 4, 1), **key)

    def all_rows(self) -> Iterator[Row]:
        for rows in self.groups.values():
            yield from rows


class Rules:
    def __init__(self, tables: dict[str, Table]):
        self.tables = tables

    @classmethod
    def load(cls, root: Path) -> "Rules":
        root = Path(root)
        tables = {}
        for p in sorted(root.rglob("*.toml")):
            name = ".".join(p.relative_to(root).with_suffix("").parts)
            try:
                raw = tomllib.loads(p.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError as e:
                raise RuleTableError(f"{p}: {e}") from e
            tables[name] = Table(name, raw, p)
        return cls(tables)

    def _t(self, table: str) -> Table:
        if table not in self.tables:
            raise RuleNotFound(f"no rule table named {table!r}")
        return self.tables[table]

    def at(self, table: str, on: date, **key) -> Row:
        return self._t(table).at(on, **key)

    def has(self, table: str, on: date, **key) -> bool:
        return self._t(table).has(on, **key)

    def at_fy(self, table: str, fy: int, **key) -> Row:
        return self._t(table).at_fy(fy, **key)

    def has_fy(self, table: str, fy: int, **key) -> bool:
        return self._t(table).has_fy(fy, **key)

    def all_rows(self) -> Iterator[Row]:
        for t in self.tables.values():
            yield from t.all_rows()
