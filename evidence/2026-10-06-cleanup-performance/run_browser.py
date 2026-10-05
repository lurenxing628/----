"""Keep isolated old/current servers alive for serial browser measurements."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

out = Path(__file__).resolve().parent
info = json.loads((out / "environment.json").read_text())
procs = []
logs = []
try:
    targets = {}
    for variant, key in [("before", "baseline_checkout"), ("after", "current_checkout")]:
        sample = json.loads((out / ("large-6-" + variant + ".json")).read_text())
        folder = Path(info["temporary_root"]) / (variant + "-browser")
        folder.mkdir(exist_ok=True)
        db = folder / "bench.db"
        shutil.copy2(sample["db"], db)
        ready = out / (variant + "-server-ready.json")
        if ready.exists():
            ready.unlink()
        log = (out / (variant + "-browser-server.log")).open("w")
        logs.append(log)
        proc = subprocess.Popen(
            [
                info["python"],
                str(out / "browser_server.py"),
                "--repo",
                info[key],
                "--db",
                str(db),
                "--ready",
                str(ready),
            ],
            stdout=log,
            stderr=log,
        )
        procs.append(proc)
        start = time.monotonic()
        while not ready.exists():
            if proc.poll() is not None:
                raise RuntimeError(variant + " server exited " + str(proc.returncode))
            if time.monotonic() - start > 25:
                raise RuntimeError(variant + " server readiness timeout")
            time.sleep(0.05)
        targets[variant] = {
            **json.loads(ready.read_text()),
            "plan_ref": sample["plan_ref"],
            "run_ref": sample["run_ref"],
            "candidate_ref": sample["candidate_ref"],
        }
    (out / "browser-targets.json").write_text(json.dumps(targets, indent=2) + "\n")
    env = os.environ.copy()
    env.update(
        {
            "WORKBENCH_BROWSER": "/Users/lurenxing/.cache/aps-chromium109-assessment/stage/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
            "NODE_PATH": "/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
        }
    )
    node = "/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    result = subprocess.run([node, str(out / "measure_browser.cjs")], env=env)
    raise SystemExit(result.returncode)
finally:
    for proc in procs:
        if proc.poll() is None:
            proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    for log in logs:
        log.close()
