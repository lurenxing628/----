"""Host-only checks for complete long-gate content snapshots and cache reuse."""

from __future__ import annotations

import base64
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import long_gate_cache as cache
from tools import long_gate_fingerprint as fingerprint
from tools.long_gate_collect import COLLECT_NODEIDS_REL, build_collect_nodeids_payload, write_collect_nodeids
from tools.long_gate_manifest import build_manifest_from_quality_gate_plan
from tools.long_gate_schema import canonical_content, content_equal, read_file_content
from tools.quality_gate_shared import normalize_quality_gate_command
from tools.verify_required_regressions_from_full_test_debt import (
    RequiredRegressionProofError,
    verify_required_regressions_from_payload,
)


class LongGateContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.source = self.root / "source.py"
        self.source.write_bytes(b"value=1\n\x00\xff")
        self.output = self.root / "result.bin"
        self.output.write_bytes(b"\x00result\xff")
        self.command = normalize_quality_gate_command(
            {"display": "host check", "args": ["python", "check.py"], "capture_output": True}
        )
        self.entry = {
            **self.command,
            "command": self.command,
            "entry_id": "host_content",
            "reuse_allowed": True,
            "input_file_scopes": ["source.py"],
            "env_keys": ["APS_ENV", "SECRET_KEY"],
            "output_result_files": ["result.bin"],
        }
        self.result = {"returncode": 0, "duration_s": 0.25, "stdout": "中文\r\nall passed\n", "stderr": ""}
        self.paths = patch.object(fingerprint, "_git_path_sources", return_value=({"source.py"}, set(), "available"))
        self.paths.start()
        self.addCleanup(self.paths.stop)

    def current(self, entry=None):
        return fingerprint.fingerprint_entry(entry or self.entry, str(self.root), strict=True)

    def saved(self, kind="success"):
        path = self.root / "evidence" / "QualityGate" / "long_gate" / "results" / f"host_content.v2.{kind}.json"
        return path, json.loads(path.read_text())

    def test_source_command_and_public_environment_use_original_content(self):
        self.assertEqual(base64.b64decode(read_file_content(str(self.source))), self.source.read_bytes())
        self.assertEqual(canonical_content({"b": 2, "a": 1}), '{"a":1,"b":2}')
        self.assertFalse(content_equal(1, 1.0))
        self.assertFalse(content_equal(False, 0))
        with patch.dict(os.environ, {"SECRET_KEY": "private-only-in-memory", "APS_ENV": "host"}, clear=True):
            before = self.current()
            self.assertEqual(before["schema_version"], 2)
            self.assertEqual(before["components"]["command"], self.command)
            self.assertEqual(before["components"]["environment"]["values"]["SECRET_KEY"], {"present": True})
            self.assertNotIn("private-only-in-memory", canonical_content(before))
            self.assertEqual(before["components"]["environment"]["non_reusable_env_keys"], ["SECRET_KEY"])
            unavailable = cache.decide_reuse(self.entry, before, repo_root=str(self.root))
            self.assertEqual(unavailable["decision"], "run")
            self.assertTrue(unavailable["cache_unavailable"])
            self.assertEqual(unavailable["non_reusable_env_keys"], ["SECRET_KEY"])
            self.assertTrue(
                cache.decide_failure_reuse(self.entry, before, repo_root=str(self.root))["cache_unavailable"]
            )
            with self.assertRaises(ValueError):
                cache.write_success(self.entry, before, self.result, ["result.bin"], repo_root=str(self.root))
            with self.assertRaises(ValueError):
                cache.write_failure(self.entry, before, {**self.result, "returncode": 1}, repo_root=str(self.root))
            self.source.write_bytes(b"value=2\n\x00\xff")
            after = self.current()
            self.assertTrue(fingerprint.diff_fingerprints(before, after)["changed"])
            self.assertEqual(fingerprint.diff_fingerprints(before, before)["changed"], False)
            self.assertEqual(
                fingerprint._runtime_probe_cache_key("node", "/node", {"PATH": "/bin", "SECRET_KEY": "a"}),
                ("node", "/node", (("PATH", "/bin"), ("SECRET_KEY", "a"))),
            )
            with self.assertRaises(fingerprint.LongGateFingerprintError):
                fingerprint.fingerprint_environment(["API_TOKEN"], environment={"API_TOKEN": "private"})
        credential_source = self.root / "config.env"
        credential_source.write_bytes(b"value=private-only-in-memory")
        with patch.dict(os.environ, {"SECRET_KEY": "private-only-in-memory"}, clear=True):
            with self.assertRaises(ValueError) as rejected:
                read_file_content(str(credential_source))
            self.assertNotIn("private-only-in-memory", str(rejected.exception))
        runtime_file = self.root / "aps_runtime.json"
        runtime_file.write_bytes(b'{"shutdown_token":"fixture-value"}')
        with self.assertRaises(ValueError):
            read_file_content(str(runtime_file))
        manifest = build_manifest_from_quality_gate_plan([self.command], repo_root=str(self.root))
        self.assertEqual(manifest["quality_gate_plan"], [self.command])
        self.assertEqual(manifest["entries"][0]["command"], self.command)
        self.assertNotIn("command_hash", manifest["entries"][0])

    def test_success_reuse_binds_source_command_logs_outputs_and_status(self):
        current = self.current()
        with patch.dict(os.environ, {"SECRET_KEY": "redact-this-value"}):
            result = {**self.result, "stdout": "redact-this-value\r\nall passed\n"}
            cache.write_success(self.entry, current, result, ["result.bin"], repo_root=str(self.root))
        path, saved = self.saved()
        self.assertEqual(saved["stdout_content"], "[REDACTED]\r\nall passed\n")
        self.assertEqual(base64.b64decode(saved["output_files"][0]["content_base64"]), self.output.read_bytes())
        reused = cache.evaluate_reuse(self.entry, current, repo_root=str(self.root))
        self.assertEqual(reused["decision"]["decision"], "reuse")
        self.assertEqual(reused["stdout"], saved["stdout_content"])
        self.output.write_bytes(b"\x00RESULT\xff")
        self.assertIn("output files", cache.decide_reuse(self.entry, current, repo_root=str(self.root))["reason"])
        self.output.write_bytes(b"\x00result\xff")
        log = self.root / saved["stdout_log_path"]
        log.write_bytes(b"changed\r\n")
        self.assertIn("logs", cache.decide_reuse(self.entry, current, repo_root=str(self.root))["reason"])
        log.write_bytes(saved["stdout_content"].encode("utf-8"))
        changed_entry = {**self.entry, "command": {**self.command, "args": ["python", "other.py"]}}
        self.assertIn("command", cache.decide_reuse(changed_entry, current, repo_root=str(self.root))["reason"])
        self.source.write_bytes(b"value=2\n\x00\xff")
        self.assertIn("fingerprint", cache.decide_reuse(self.entry, self.current(), repo_root=str(self.root))["reason"])
        saved["timed_out"] = True
        path.write_text(json.dumps(saved))
        self.assertIn("timed out", cache.decide_reuse(self.entry, current, repo_root=str(self.root))["reason"])
        saved["timed_out"] = False
        saved["stdout_log_path"] = "../outside.log"
        path.write_text(json.dumps(saved))
        self.assertIn("escapes repo root", cache.decide_reuse(self.entry, current, repo_root=str(self.root))["reason"])

    def test_failure_reuse_retains_nonzero_returncode_and_original_logs(self):
        entry = {**self.entry, "output_result_files": []}
        current = self.current(entry)
        failed = {
            **self.result,
            "returncode": 3,
            "stderr": "failed check\n",
            "receipt_path": "receipts/original.json",
            "run_id": "original-run",
            "command_index": 4,
        }
        cache.write_failure(entry, current, failed, repo_root=str(self.root))
        path, saved = self.saved("failure")
        self.assertEqual(
            cache.decide_failure_reuse(entry, current, repo_root=str(self.root))["decision"], "cached_failure"
        )
        self.assertEqual(saved["returncode"], 3)
        self.assertEqual(saved["run_id"], "original-run")
        self.assertNotIn("result_hash", saved)
        saved["returncode"] = 0
        path.write_text(json.dumps(saved))
        self.assertIn(
            "returncode was zero", cache.decide_failure_reuse(entry, current, repo_root=str(self.root))["reason"]
        )
        saved["returncode"] = 3
        saved["interrupted"] = True
        path.write_text(json.dumps(saved))
        self.assertIn("interrupted", cache.decide_failure_reuse(entry, current, repo_root=str(self.root))["reason"])
        with self.assertRaises(ValueError):
            cache.write_failure(entry, current, {**failed, "timed_out": True}, repo_root=str(self.root))
        saved["interrupted"] = False
        path.write_text(json.dumps(saved))
        (self.root / saved["stderr_log_path"]).write_bytes(b"other error!\n")
        self.assertIn("logs", cache.decide_failure_reuse(entry, current, repo_root=str(self.root))["reason"])

    def test_legacy_digest_only_records_remain_readable_and_miss(self):
        legacy = self.root / "evidence" / "QualityGate" / "long_gate" / "results" / "host_content.success.json"
        legacy.parent.mkdir(parents=True)
        original = b'{"schema_version":1,"fingerprint_hash":"sha256:historical","completed_at":"historical"}\n'
        legacy.write_bytes(original)
        old_log = legacy.parent.parent / "logs" / "host_content.stdout.log"
        old_log.parent.mkdir()
        old_log.write_bytes(b"historical output\n")
        current = self.current()
        decision = cache.decide_reuse(self.entry, current, repo_root=str(self.root))
        self.assertEqual(decision["decision"], "run")
        self.assertEqual(decision["previous_result_path"], str(legacy.relative_to(self.root)))
        self.assertIn("legacy", decision["reason"])
        cache.write_success(self.entry, current, self.result, ["result.bin"], repo_root=str(self.root))
        self.assertEqual(legacy.read_bytes(), original)
        self.assertEqual(old_log.read_bytes(), b"historical output\n")
        self.assertEqual(json.loads(legacy.read_text())["completed_at"], "historical")

    def test_collect_and_required_use_full_nodeids_and_actual_reports(self):
        stdout = "tests/example.py::test_one\ntests/example.py::test_two[param]\n\n2 tests collected in 0.1s\n"
        payload = build_collect_nodeids_payload(stdout, pytest_version="8.3.5")
        self.assertEqual(payload["collect_stdout_content"], stdout)
        write_collect_nodeids(payload, repo_root=str(self.root))
        collect = fingerprint._collect_nodeids_component(str(self.root))
        self.assertTrue(collect["validated"])
        self.assertEqual(collect["nodeids"], payload["nodeids"])
        tampered = {
            **payload,
            "nodeids": ["tests/example.py::test_other"],
            "nodeid_count": 1,
            "nodeids_by_file": {"tests/example.py": ["tests/example.py::test_other"]},
        }
        (self.root / COLLECT_NODEIDS_REL).write_text(json.dumps(tampered))
        self.assertFalse(fingerprint._collect_nodeids_component(str(self.root))["validated"])
        full_payload = {
            "exitstatus": 0,
            "collection_error_count": 0,
            "classifications": {
                "required_or_quality_gate_self_failure": [],
                "main_style_isolation_candidate": [],
                "candidate_test_debt": [],
            },
            "collected_nodeids": payload["nodeids"],
            "reports": [{"nodeid": nodeid, "when": "call", "outcome": "passed"} for nodeid in payload["nodeids"]],
        }
        verified = verify_required_regressions_from_payload(full_payload, required_tests=["tests/example.py"])
        self.assertEqual(verified["required_target_paths"], ["tests/example.py"])
        self.assertEqual(verified["required_nodeids"], payload["nodeids"])
        self.assertEqual(verified["required_reports"][payload["nodeids"][0]], [full_payload["reports"][0]])
        self.assertNotIn("required_target_hash", verified)
        bad = copy.deepcopy(full_payload)
        bad["reports"][0]["xfail_marker_present"] = True
        with self.assertRaises(RequiredRegressionProofError):
            verify_required_regressions_from_payload(bad, required_tests=["tests/example.py"])
        with self.assertRaises(RequiredRegressionProofError):
            verify_required_regressions_from_payload(full_payload, required_tests=["tests/missing.py"])


if __name__ == "__main__":
    unittest.main()
