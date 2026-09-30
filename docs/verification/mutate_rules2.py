"""Second mutation sweep over rules/**/*.toml: the NON-numeric fields (booleans, modes, orders, treatments, buckets, cohorts, section
labels, list items, inline `basis`, the grandfathering date). Reuses the machinery of mutate_rules.py. Usage: python docs/verification/mutate_rules2.py WORKERS"""
import importlib.util
import re
import sys
import tomllib
from pathlib import Path

spec = importlib.util.spec_from_file_location("mr", Path(__file__).with_name("mutate_rules.py"))
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)

SWAP = {
    "mode": {"zero": "pct", "pct": "zero", "min_flat_pct": "pct", "exempt": "slab", "slab": "exempt", "above_threshold": "slab"},
    "order": {"lowest_rate_first": "highest_rate_first", "highest_rate_first": "lowest_rate_first"},
    "st_treatment": {"special": "slab", "slab": "special", "exempt": "special"},
    "lt_treatment": {"special": "exempt", "exempt": "special", "slab": "special"},
    "basis": {"per_sale": "per_isin_per_day", "per_isin_per_day": "per_sale"},
    "bucket": {"equity": "gold", "gold": "equity", "debt_pre_apr2023": "gold", "gold_post_apr2023": "debt_post_apr2023",
               "debt_post_apr2023": "gold_post_apr2023"},
    "cohort": {"legacy": "standard", "standard": "free", "free": "legacy"},
}
LABEL_FIELDS = {"st_section", "lt_section", "lt_alt_section", "lt_exemption_group"}
RESERVED = {"from", "to", "source", "verified_on", "confidence", "note"}
BOOLS = {"true": "false", "false": "true"}
STRING = re.compile(r'=\s*"([^"]*)"\s*$')


def points2(text: str):
    lines = text.split("\n")
    first = next((i for i, l in enumerate(lines) if l.strip() == "[[row]]"), None)
    if first is None:
        return []
    keys = tomllib.loads("\n".join(lines[:first])).get("meta", {}).get("keys", [])
    out = []
    for i in range(first, len(lines)):
        line = lines[i]
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("["):
            continue
        field = s.split("=", 1)[0].strip()
        if field in keys or field in RESERVED:
            continue
        val = line.split("=", 1)[1].strip()
        base = line.index("=") + 1
        if field == "grandfather_acq_upto":
            for delta in (1, -1):
                a, e, rep = mr.date_edit(line, delta)
                out.append(([(i, a, e, rep)], f"{field} date {delta:+d} day"))
        elif val in BOOLS:
            a = line.index(val, base)
            out.append(([(i, a, a + len(val), BOOLS[val])], f"{field} flipped to {BOOLS[val]}"))
        elif val.startswith("["):
            for label in sorted(set(re.findall(r'test_excludes = \[([^\]]*)\]', line) and
                                    re.findall(r'"([^"]+)"', " ".join(re.findall(r'test_excludes = \[([^\]]*)\]', line))))):
                cut = re.sub(r'"' + re.escape(label) + r'",? ?', "", line)
                cut = cut.replace(", ]", "]")
                out.append(([(i, 0, len(line), cut)], f"test_excludes without {label!r}"))
            if 'basis = "excluding_special"' in line:
                a = line.index('basis = "excluding_special"')
                out.append(([(i, a, a + len('basis = "excluding_special"'), 'basis = "including"')], "tier basis removed"))
            items = re.findall(r'"([^"]*)"', val)
            if field in ("applies_to", "excluded_sections", "cap_sections") and items:
                a = line.index("[", base)
                e = line.rindex("]") + 1
                for k, item in enumerate(items):
                    rest = [x for j, x in enumerate(items) if j != k]
                    rep = "[" + ", ".join(f'"{x}"' for x in rest) + "]"
                    out.append(([(i, a, e, rep)], f"{field} without {item!r}"))
        else:
            m = STRING.search(line)
            if not m or re.fullmatch(r"\d+(\.\d+)?", m.group(1)):
                continue
            v = m.group(1)
            if field in SWAP and v in SWAP[field]:
                out.append(([(i, m.start(1), m.end(1), SWAP[field][v])], f"{field} {v} -> {SWAP[field][v]}"))
            elif field in LABEL_FIELDS:
                out.append(([(i, m.end(1), m.end(1), "X")], f"{field} label {v!r} + X"))
    return out


if __name__ == "__main__":
    mr.points = points2
    mr.main()
