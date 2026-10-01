"""Push a kernel to Kaggle, wait for it, pull what it wrote and verify it, with the `kaggle` command line already logged in on this machine.

Only datasets and kernels named india-algo-* are ever created or changed, so the old deeptrend-* and btc-* ones cannot be touched by a typo. The credential is the CLI's own:
nothing here reads, passes or prints it. Kernels are private, run on a T4 GPU and have no internet.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from research.kaggle.snapshot import sha256

SLUG = re.compile(r"^india-algo-[a-z0-9]+(-[a-z0-9]+)*$")
FAILED = ("ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED")


def check_slug(slug: str) -> str:
    if not SLUG.match(slug):
        raise ValueError(f"the slug {slug!r} must be india-algo-... in lower case letters, digits and hyphens")
    return slug


def dataset_metadata(owner: str, slug: str, title: str) -> dict:
    return {"title": title, "id": f"{owner}/{check_slug(slug)}", "licenses": [{"name": "other"}]}


def kernel_metadata(owner: str, slug: str, title: str, code_file: str, datasets: list[str], gpu: bool = True) -> dict:
    for ds in datasets:
        check_slug(ds.split("/")[-1])
    return {"id": f"{owner}/{check_slug(slug)}", "title": title, "code_file": code_file, "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": gpu,
            "enable_tpu": False, "enable_internet": False, "keywords": ["gpu"] if gpu else [], "dataset_sources": list(datasets), "kernel_sources": [], "competition_sources": [],
            "model_sources": [], "machine_shape": "NvidiaTeslaT4" if gpu else None}


def cli(args: list[str], runner=subprocess.run) -> str:
    r = runner(["kaggle", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout


def status(ref: str, runner=subprocess.run) -> str:
    out = cli(["kernels", "status", ref], runner)
    m = re.search(r'has status "KernelWorkerStatus\.(\w+)"', out)
    if not m:
        raise RuntimeError(f"could not read a status from: {out.strip()}")
    return m.group(1)


def wait(ref: str, runner=subprocess.run, sleep=time.sleep, timeout_s: int = 3 * 3600, interval_s: int = 30) -> str:
    waited = 0
    while True:
        s = status(ref, runner)
        if s == "COMPLETE":
            return s
        if s in FAILED:
            raise RuntimeError(f"the kernel {ref} ended with status {s}")
        if waited >= timeout_s:
            raise TimeoutError(f"the kernel {ref} was still {s} after {waited} seconds")
        sleep(interval_s)
        waited += interval_s


def verify_output(out, expected: list[str]) -> None:
    """The kernel's outputs.json lists the hash of every file it wrote; every expected file must be there, listed and unchanged."""
    out = Path(out)
    if not (out / "outputs.json").exists():
        raise ValueError("the output has no outputs.json: the kernel did not finish writing")
    listed = json.loads((out / "outputs.json").read_text(encoding="utf-8"))["files"]
    gone = [f for f in expected if f not in listed or not (out / f).exists()]
    if gone:
        raise ValueError(f"missing output files: {gone}")
    for f in expected:
        if sha256(out / f) != listed[f]:
            raise ValueError(f"changed output file: {f}")


def upload_dataset(snap, owner: str, slug: str, title: str, message: str, runner=subprocess.run, sleep=time.sleep, timeout_s: int = 900) -> None:
    """Create the private dataset from the snapshot folder, or add a version to it, and wait until it is ready."""
    snap = Path(snap)
    (snap / "dataset-metadata.json").write_bytes((json.dumps(dataset_metadata(owner, slug, title), indent=1) + "\n").encode("utf-8"))
    ref = f"{owner}/{slug}"
    try:
        cli(["datasets", "status", ref], runner)
        cli(["datasets", "version", "-p", str(snap), "-m", message], runner)
    except RuntimeError:
        cli(["datasets", "create", "-p", str(snap)], runner)
    waited = 0
    while "ready" not in cli(["datasets", "status", ref], runner).lower():
        if waited >= timeout_s:
            raise TimeoutError(f"the dataset {ref} was not ready after {waited} seconds")
        sleep(10)
        waited += 10


def run_kernel(workdir, owner: str, slug: str, title: str, code: Path, datasets: list[str], expected: list[str], out, runner=subprocess.run, sleep=time.sleep,
               timeout_s: int = 3 * 3600) -> None:
    """Push the script as a private GPU kernel, wait for it, pull its output into `out` and verify it."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / code.name).write_bytes(code.read_bytes())
    (workdir / "kernel-metadata.json").write_bytes((json.dumps(kernel_metadata(owner, slug, title, code.name, datasets), indent=1) + "\n").encode("utf-8"))
    cli(["kernels", "push", "-p", str(workdir)], runner)
    wait(f"{owner}/{slug}", runner, sleep, timeout_s)
    Path(out).mkdir(parents=True, exist_ok=True)
    cli(["kernels", "output", f"{owner}/{slug}", "-p", str(out)], runner)
    verify_output(out, expected)
