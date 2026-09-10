"""Capture isolated, read-only static triage evidence; never run the full gate."""

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def stamp():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=str(ROOT))


def snapshot():
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")
    hashes = {}
    extra = {"AGENTS.md", ".codestable/attention.md", "pyproject.toml", "schema.sql",
             "pyrightconfig.gate.json", "pyrightconfig.tools.json", "pyrightconfig.json",
             ".codestable/checkup/import_cycles_production_baseline.json",
             ".codestable/checkup/import_cycles_with_tests_baseline.json",
             "开发文档/技术债务治理台账.md"}
    for raw in files:
        rel = os.fsdecode(raw)
        if not rel or "previews" in Path(rel).parts:
            continue
        scope = rel.endswith(".py") and ("/" not in rel or rel.split("/", 1)[0] in
                {"core", "web", "data", "tools", "scripts", "tests", "desktop", "plugins"})
        if not scope and rel not in extra:
            continue
        path = ROOT / rel
        if path.is_file():
            hashes[rel] = digest(path.read_bytes())
    return {"captured_at": stamp(), "head": git("rev-parse", "HEAD").decode().strip(),
            "staged_diff_sha256": digest(git("diff", "--cached", "--binary", "--no-ext-diff")),
            "files": hashes}


def main():
    name, *command = sys.argv[1:]
    if not command or not re.fullmatch(r"[a-z0-9-]+", name):
        raise SystemExit("usage: capture_check.py label command ...")
    target = OUT / "runs" / (datetime.datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + name)
    target.mkdir(parents=True, exist_ok=False)
    processes = subprocess.check_output(["ps", "-axo", "pid,ppid,%cpu,etime,command"]).decode()
    rows = [row for row in processes.splitlines() if re.search(
        r"pyright|run_quality_gate|scan_import_cycles|architecture_fitness|pytest|long_gate", row)]
    (target / "processes-before.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    # The caller checks for competing jobs before dispatch; keep this evidence auditable.
    before = snapshot()
    write_json(target / "before.json", before)
    (target / "git-status-before.txt").write_bytes(git("status", "--short"))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               PYTHONPYCACHEPREFIX=str(target / "unused-pycache"))
    started = stamp()
    tick = time.monotonic()
    print("START", name, started, str(target), flush=True)
    with (target / "stdout.log").open("wb") as stdout, (target / "stderr.log").open("wb") as stderr:
        result = subprocess.run(["nice", "-n", "10", *command], cwd=str(ROOT), env=env,
                                stdout=stdout, stderr=stderr, check=False)
    elapsed = time.monotonic() - tick
    after = snapshot()
    write_json(target / "after.json", after)
    (target / "git-status-after.txt").write_bytes(git("status", "--short"))
    changed = sorted(path for path in set(before["files"]) | set(after["files"])
                     if before["files"].get(path) != after["files"].get(path))
    receipt = {"name": name, "cwd": str(ROOT), "command": command,
               "execution_prefix": ["nice", "-n", "10"], "environment_overlay": {
                   key: env[key] for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONUTF8", "PYTHONIOENCODING", "PYTHONPYCACHEPREFIX")},
               "started_at": started, "finished_at": stamp(), "duration_seconds": elapsed,
               "returncode": result.returncode, "source_changes_during_run": changed,
               "staged_diff_unchanged": before["staged_diff_sha256"] == after["staged_diff_sha256"],
               "does_not_claim": ["full_gate", "clean_worktree_proof", "atomic_snapshot"],
               "stdout_sha256": digest((target / "stdout.log").read_bytes()),
               "stderr_sha256": digest((target / "stderr.log").read_bytes())}
    write_json(target / "receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
