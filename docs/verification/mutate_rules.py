"""Mutation sweep over rules/**/*.toml in a throw-away export of HEAD (never the real checkout).

Mutations, one at a time: each numeric string and integer field changes; each `from` / `to` date shifts a day on its own (the
loader must refuse the gap or overlap) and each boundary between two rows of one key moves a day earlier and later (the golden
"both sides of every change" cases must notice). A test must fail every time.
Usage: python docs/verification/mutate_rules.py WORKERS   (about 10 minutes with 6 workers)
Outcome lines: KILLED-FAST (golden, gate or real-rule tests caught it), KILLED-FULL (only another test caught it), SURVIVED.
"""
import concurrent.futures as cf
import datetime as dtm
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # the repository this file is in
WORK = Path(tempfile.gettempdir()) / "rules_mutation"
WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
SKIP_KEYS = {"source", "note", "verified_on", "confidence", "id", "name", "cohort", "segment", "side", "exchange", "bucket", "series",
             "regime", "group", "product", "kind", "instrument_class", "asset_class", "mode", "basis", "order", "applies_to",
             "st_treatment", "lt_treatment", "st_section", "lt_section", "lt_alt_section", "lt_exemption_group", "excluded_sections",
             "cap_sections", "coverage_from", "open_ended", "late_keys", "keys", "lt_alt_indexation", "indexation", "always_short",
             "applies_to_special", "marginal_relief"}
NUM = re.compile(r'"(\d+(?:\.\d+)?)"')
DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def bump(num: str) -> str:
    return num[:-1] + str((int(num[-1]) + 1) % 10)


def date_edit(line: str, delta: int):
    m = DATE.search(line.split("=", 1)[1])
    a = line.index("=") + 1 + m.start()
    return a, a + 10, (dtm.date(*map(int, m.groups())) + dtm.timedelta(days=delta)).isoformat()


def points(text: str):
    """Return a list of (edits, label); edits = [(line_index, start, end, replacement)]."""
    lines = text.split("\n")
    out = []
    blocks, cur = [], None
    for i, line in enumerate(lines):
        if line.strip() == "[[row]]":
            cur = dict(start=i, lines=[])
            blocks.append(cur)
        elif cur is not None:
            cur["lines"].append(i)
    meta_text = "\n".join(lines[: blocks[0]["start"]]) if blocks else "\n".join(lines)
    keys = tomllib.loads(meta_text).get("meta", {}).get("keys", [])
    for b in blocks:
        b["data"] = tomllib.loads("\n".join(lines[j] for j in b["lines"]))
        b["key"] = tuple(str(b["data"].get(k)) for k in keys)
        for j in b["lines"]:
            k = lines[j].split("=", 1)[0].strip()
            if k in ("from", "to"):
                b[k + "_line"] = j
    for b in blocks:
        for j in b["lines"]:
            line = lines[j]
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            key = s.split("=", 1)[0].strip()
            if key in ("from", "to"):
                for delta in (1, -1):
                    a, e, rep = date_edit(line, delta)
                    out.append(([(j, a, e, rep)], f"{key} date alone {delta:+d} day ({b['key']})"))
                continue
            if key in SKIP_KEYS:
                continue
            if re.fullmatch(r"\w+\s*=\s*\d+", s):
                m = re.search(r"\d+$", line)
                out.append(([(j, m.start(), m.end(), str(int(m.group()) + 1))], f"{key} integer +1 ({b['key']})"))
                continue
            for m in NUM.finditer(line):
                out.append(([(j, m.start(1), m.end(1), bump(m.group(1)))], f"{key} number {m.group(1)} ({b['key']})"))
    for b in blocks:
        if "to_line" not in b:
            continue
        to = b["data"]["to"]
        nxt = next((c for c in blocks if c is not b and c["key"] == b["key"] and c["data"]["from"] == to + dtm.timedelta(days=1)), None)
        if nxt is None:
            continue
        for delta in (1, -1):
            a1, e1, r1 = date_edit(lines[b["to_line"]], delta)
            a2, e2, r2 = date_edit(lines[nxt["from_line"]], delta)
            out.append(([(b["to_line"], a1, e1, r1), (nxt["from_line"], a2, e2, r2)],
                        f"boundary {to} -> {to + dtm.timedelta(days=1)} moved {delta:+d} day ({b['key']})"))
    return out


def run(cwd: Path, targets) -> bool:
    args = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", f"--basetemp={cwd / '.tmp'}", "--no-header", *targets]
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True).returncode != 0


def worker(wid: int, jobs):
    cwd = WORK / f"w{wid}"
    out = []
    for rel, edits, label in jobs:
        path = cwd / rel
        orig = path.read_bytes()
        text = orig.decode("utf-8")
        crlf = "\r\n" in text
        lines = text.replace("\r\n", "\n").split("\n")
        for i, a, b, rep in edits:
            lines[i] = lines[i][:a] + rep + lines[i][b:]
        mut = "\n".join(lines)
        try:
            path.write_bytes((mut.replace("\n", "\r\n") if crlf else mut).encode("utf-8"))
            if run(cwd, ["tests/test_golden.py", "tests/test_gates.py", "tests/test_rules_real.py"]):
                out.append(("KILLED-FAST", rel, edits[0][0] + 1, label))
            elif run(cwd, []):
                out.append(("KILLED-FULL", rel, edits[0][0] + 1, label))
            else:
                out.append(("SURVIVED", rel, edits[0][0] + 1, label))
        finally:
            path.write_bytes(orig)
    return out


def main():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    base = WORK / "base"
    base.mkdir(parents=True)
    git = subprocess.Popen(["git", "archive", "HEAD"], cwd=REPO, stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(base)], stdin=git.stdout, check=True)
    git.stdout.close()
    assert git.wait() == 0
    jobs = []
    for path in sorted((base / "rules").rglob("*.toml")):
        rel = path.relative_to(base).as_posix()
        text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
        jobs += [(rel, edits, label) for edits, label in points(text)]
    print(f"{len(jobs)} mutation points, {WORKERS} workers", flush=True)
    for w in range(WORKERS):
        shutil.copytree(base, WORK / f"w{w}")
    shards = [jobs[w::WORKERS] for w in range(WORKERS)]
    results = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for res in ex.map(worker, range(WORKERS), shards):
            results += res
    tally = {}
    for kind, *_ in results:
        tally[kind] = tally.get(kind, 0) + 1
    print("tally", tally, flush=True)
    for kind, rel, line, label in sorted(results):
        if kind != "KILLED-FAST":
            print(kind, rel, "line", line, label, flush=True)
    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
