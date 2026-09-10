"""Real loopback admission, polling, four full workspaces, process stop and restart."""

import hashlib
import json
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tests.workbench.final_capacity_binding import binding_evidence, install_capacity_binding
from tests.workbench.final_capacity_sources import ProductSourceFreeze
from tests.workbench.final_capacity_support import digest, retain_business, retain_restart, verify_database
from tests.workbench.live_environment import REPO, create_root, environment, write_json

BASE = "/api/workbench/v1/scheduling"
OTHER_REQUEST = "/api/workbench/v1/resources/summary"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require_current_build(ready, *, formal):
    if formal:
        assert ready["assets"]["source_differences"] == [], "Main must finish the current full build before formal timing"


class Host:
    def __init__(self, root, *, reuse=False, profile=False):
        self.root = root
        prefix = "restart" if reuse else "initial"
        self.streams = [(root / (prefix + suffix)).open("w", encoding="utf-8") for suffix in (".stdout.log", ".stderr.log")]
        command = [sys.executable, "-B", str(REPO / "tests/workbench/final_capacity_server.py"), "--root", str(root)]
        if reuse:
            command.append("--reuse")
        if profile:
            command.append("--profile")
        env = environment(root)
        env["PYTHONPYCACHEPREFIX"] = str(root / "tmp/pycache")
        self.process = subprocess.Popen(command, cwd=str(REPO), env=env, stdout=self.streams[0], stderr=self.streams[1])
        self.requests = []
        self.started = time.monotonic()
        self.ready = None

    def wait_ready(self):
        path = self.root / "server-ready.json"
        while time.monotonic() - self.started < 60:
            if self.process.poll() is not None:
                raise RuntimeError("Capacity server exited before ready: " + str(self.process.returncode))
            if path.is_file():
                try:
                    ready = read_json(path)
                except json.JSONDecodeError:
                    time.sleep(0.02)
                    continue
                if ready["pid"] == self.process.pid:
                    self.ready = ready
                    return ready
            time.sleep(0.05)
        raise TimeoutError("Capacity server did not become ready")

    def request(self, path, *, body=None, status=200):
        assert self.ready is not None
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(self.ready["url"] + path, data=data, headers={"Content-Type": "application/json"})
        started = time.monotonic()
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            raw, code = response.read(), response.status
        parsed = json.loads(raw)
        row = {"path": path, "method": request.get_method(), "status": code,
               "started_seconds": started - self.started, "elapsed_seconds": time.monotonic() - started,
               "response_bytes": len(raw), "body_sha256": digest(parsed)}
        self.requests.append(row)
        directory = self.root / "sessions" / self.ready["session"]
        (directory / f"http-{len(self.requests):04d}.json").write_bytes(raw)
        write_json(directory / "client-requests.json", self.requests)
        assert code == status, {"request": path, "expected": status, "actual": code, "response": parsed}
        return parsed

    def close(self):
        started = time.monotonic()
        try:
            if self.process.poll() is None:
                self.process.send_signal(signal.SIGTERM)
            try:
                code = self.process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                write_json(self.root / "forced-stop.json", {"pid": self.process.pid, "reason": "graceful shutdown exceeded 180 seconds"})
                raise
        finally:
            for stream in self.streams:
                stream.close()
        assert code == 0, "Capacity child failed: " + str(code)
        assert self.ready is not None
        directory = self.root / "sessions" / self.ready["session"]
        final = read_json(directory / "server-final.json")
        assert final["stopped"] and final["runtime"]["closed"] and not final["runtime"]["pending"]
        assert not final["isolation_violations"] and final["assets_unchanged"]
        assert not final["python_sources"]["changed"], "Loaded source changed during run"
        assert not Path(self.ready["runtime_lock"]["path"]).exists()
        assert not Path(self.ready["db_lock"]).exists()
        result = {"pid": self.process.pid, "returncode": code, "elapsed_seconds": time.monotonic() - started,
                  "final": final, "process": read_json(directory / "capacity-process.json")}
        binding = install_capacity_binding()
        if binding is not None:
            result["source_binding"] = binding.host_evidence(directory, expected_pid=self.process.pid)
        return result


def accept_and_poll(host, *, deadline):
    assert host.ready is not None
    settings = host.ready["expected"]["settings"]
    preflight = host.request(BASE + "/preflight", body=settings)["data"]
    preview = host.request(BASE + "/runs/preview", body={"input_ref": preflight["input_ref"]})["data"]
    key = "capacity-" + uuid.uuid4().hex
    intent = {"input_ref": preflight["input_ref"], "write_token": preview["write_context"]["write_token"], "request_key": key}
    started = time.monotonic()
    accepted = host.request(BASE + "/runs", body=intent, status=202)
    run_ref, running_reads = accepted["run_ref"], []
    acceptance_seconds = time.monotonic() - started
    while time.monotonic() - started < deadline:
        state = host.request(BASE + "/runs/" + run_ref)["data"]
        if state["state"] in ("complete", "partial", "failed", "interrupted"):
            assert state["state"] == "complete" and state["result_persisted"], state
            assert len(state["candidates"]) == 4
            assert time.monotonic() - started < deadline, "Observed terminal response exceeded the capacity deadline"
            return {"run_ref": run_ref, "request_key": key, "state": state,
                    "acceptance_seconds": acceptance_seconds, "accepted_to_terminal_seconds": time.monotonic() - started,
                    "running_reads": running_reads, "intent": intent}
        assert state["state"] in ("queued", "running"), state
        lookup = host.request(BASE + "/requests/" + key)["data"]
        assert lookup["found"] and lookup["run"]["run_ref"] == run_ref
        host.request(OTHER_REQUEST)
        if state["state"] == "running":
            running_reads.append({"state": state["state"], "lookup_state": lookup["run"]["state"],
                                  "other_request_seconds": host.requests[-1]["elapsed_seconds"]})
        time.sleep(0.1)
    raise TimeoutError("Capacity run did not complete before the unchanged 180 second target")


def read_all_candidates(host, run_ref, expected_count):
    catalog = host.request(BASE + "/runs/" + run_ref + "/candidates")["data"]
    assert catalog["candidate_count"] == 4 and catalog["catalog_complete"]
    workspaces = {}
    for candidate in catalog["candidates"]:
        ref = candidate["candidate_ref"]
        data = host.request(BASE + "/candidates/" + ref)["data"]
        assert data["tasks_complete"] is True
        assert data["task_count"] == data["candidate_task_count"] == len(data["tasks"]) == expected_count
        workspaces[ref] = digest(data)
    assert len(workspaces) == 4
    return workspaces


def run_managed(output, *, batches=100, operations=2, exclusive_window=None, profile=False, asset_root=None):
    if operations * batches > 1000 and not exclusive_window:
        raise ValueError("Main must arrange an exclusive window before a 5000 run")
    if exclusive_window and (batches != 100 or operations != 50 or profile):
        raise ValueError("Formal capacity is exactly 100 x 50 and has cProfile disabled")
    if exclusive_window and asset_root is None:
        raise ValueError("Formal capacity requires Main's explicit current --asset-root")
    binding = install_capacity_binding(required=bool(exclusive_window))
    output = Path(output).resolve()
    if output == REPO or REPO in output.parents:
        raise ValueError("Capacity output must be a fresh private root outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    root = create_root(output)
    spec = {"kind": "final-capacity-B-v1", "root": str(root), "batches": batches, "operations": operations,
            "exclusive_window": exclusive_window, "cprofile": profile,
            "timing_scope": "Main-declared exclusive window" if exclusive_window else "exploratory; parallel host activity uncontrolled"}
    if asset_root is not None:
        asset_root = Path(asset_root).resolve()
        spec.update(asset_root=str(asset_root), manifest_sha256=hashlib.sha256((asset_root / "asset-manifest.json").read_bytes()).hexdigest())
    write_json(root / "final-capacity.json", spec)
    result = {"spec": spec, "complete": False, "formal_capacity_passed": False, "root": str(root),
              "source_binding": {"before": binding_evidence(binding)}}
    write_json(output / "result.json", result)
    freeze = ProductSourceFreeze(output)
    freeze.start()
    try:
        _verify_managed(root, output, result, batches=batches, operations=operations,
                        exclusive_window=exclusive_window, profile=profile)
    finally:
        result["product_input_freeze"] = freeze.finish()
        write_json(output / "result.json", result)
        result["source_binding"]["after"] = binding_evidence(binding)
        write_json(output / "result.json", result)
    assert result["product_input_freeze"]["unchanged"], result["product_input_freeze"]
    result.update(complete=True, formal_capacity_passed=bool(exclusive_window), restart_business_unchanged=True)
    write_json(output / "result.json", result)
    return result


def _verify_managed(root, output, result, *, batches, operations, exclusive_window, profile):
    host = Host(root, profile=profile)
    try:
        ready = host.wait_ready()
        require_current_build(ready, formal=bool(exclusive_window))
        admitted = accept_and_poll(host, deadline=180)
        assert admitted["running_reads"], "No real concurrent request was observed while computing"
        workspaces = read_all_candidates(host, admitted["run_ref"], batches * operations)
        replay = host.request(BASE + "/runs", body=admitted["intent"], status=202)
        assert replay["run_ref"] == admitted["run_ref"] and replay["replayed"]
        result.update(admission={key: value for key, value in admitted.items() if key != "intent"}, workspaces=workspaces)
    finally:
        result["shutdown"] = host.close()
        write_json(output / "result.json", result)
    directory = root / "sessions" / ready["session"]
    before, after = read_json(directory / "business-before.json"), read_json(directory / "business-after.json")
    result["business_retention"] = retain_business(before, after)
    proof = verify_database(root / "db/aps-live.db", admitted["run_ref"], batches * operations,
                            expected_batches=batches, expected_operations=operations)
    write_json(output / "candidate-payloads.json", proof.pop("payloads"))
    result["persistence"] = proof
    result["stages"] = [json.loads(line) for line in (directory / "worker-stages.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["stage"] for row in result["stages"]} == {"prepare", "engine", "serialization", "snapshot_compute_serialize", "persistence", "worker_total"}
    assert all(row["completed"] for row in result["stages"])
    assert next(row["elapsed_seconds"] for row in result["stages"] if row["stage"] == "engine") < 180
    restarted = Host(root, reuse=True)
    try:
        second = restarted.wait_ready()
        state = restarted.request(BASE + "/runs/" + admitted["run_ref"])["data"]
        assert state == admitted["state"], "Durable run identity/result changed after restart"
        lookup = restarted.request(BASE + "/requests/" + admitted["request_key"])["data"]
        assert lookup["found"] and lookup["run"] == state
        result["restart_workspaces"] = read_all_candidates(restarted, admitted["run_ref"], batches * operations)
        assert result["restart_workspaces"] == workspaces
    finally:
        result["restart_shutdown"] = restarted.close()
        write_json(output / "result.json", result)
    second_dir = root / "sessions" / second["session"]
    result["restart_retention"] = retain_restart(after, read_json(second_dir / "business-before.json"),
                                                 read_json(second_dir / "business-after.json"))
    after_restart = verify_database(root / "db/aps-live.db", admitted["run_ref"], batches * operations,
                                    expected_batches=batches, expected_operations=operations)
    after_restart.pop("payloads")
    assert proof == after_restart
    assert not (second_dir / "worker-stages.jsonl").exists(), "Restart unexpectedly recomputed the completed run"
    assert ready["assets"]["build_id"] == second["assets"]["build_id"]
    first_sources = result["shutdown"]["final"]["python_sources"]["after"]
    second_sources = result["restart_shutdown"]["final"]["python_sources"]["after"]
    for path, expected in first_sources.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, "Source changed across restart: " + path
        assert path not in second_sources or second_sources[path] == expected
    result["loaded_source_hashes_unchanged_across_restart"] = True
