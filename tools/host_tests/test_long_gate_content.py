"""Host-only checks for complete long-gate content snapshots and cache reuse."""

from __future__ import annotations

import base64
import copy
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tools import long_gate_cache as cache
from tools import long_gate_fingerprint as fingerprint
from tools import long_gate_schema as schema
from tools.long_gate_collect import build_collect_nodeids_payload, write_collect_nodeids
from tools.long_gate_manifest import group_local_receipts, load_local_quality_gate_receipts
from tools.long_gate_paths import LONG_GATE_CACHE_DIR_REL, resolve_repo_root
from tools.long_gate_records import (
    CacheDecision,
    CommandResult,
    DecisionCause,
    GateJsonError,
    RuntimeEntry,
    StepOutcome,
    build_receipt,
    gate_entries,
    load_gate_json,
)
from tools.long_gate_schema import (
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
    PRIVATE_ENVIRONMENT_KEYS,
    PUBLIC_ENVIRONMENT_KEYS,
    SensitiveSourceError,
    canonical_content,
    content_equal,
    long_gate_cache_metadata,
    read_file_content,
)
from tools.long_gate_summary import build_long_gate_summary, summary_entry, write_long_gate_summary
from tools.quality_gate_shared import (
    FORMAL_FULL_TEST_PYTEST_ARGS,
    QUALITY_GATE_COLLECT_NODEIDS_REL,
    GateCheckSpec,
    QualityGateError,
    build_quality_gate_check_specs,
    normalize_quality_gate_command,
)
from tools.test_debt_registry import BASELINE_SCHEMA_VERSION
from tools.verify_required_regressions_from_full_test_debt import (
    RequiredRegressionProofError,
    verify_required_regressions_from_payload,
)

REPO_ROOT = Path(resolve_repo_root())
CACHE_DIR = LONG_GATE_CACHE_DIR_REL
RECEIPT_PATH = "evidence/QualityGate/v4/receipts/01_host-check.json"


def _result(**overrides):
    base = CommandResult(
        stdout="中文\r\nall passed\n",
        stderr="",
        returncode=0,
        stdout_log_path="evidence/QualityGate/v4/logs/01_host-check.stdout.log",
        stderr_log_path="evidence/QualityGate/v4/logs/01_host-check.stderr.log",
        execution_mode="executed",
        reused_from={},
        started_at="2026-11-16T00:00:00",
        ended_at="2026-11-16T00:00:01",
        duration_s=0.25,
        duration_kind="executed",
        original_duration_s=None,
    )
    return replace(base, **overrides)


class LongGateContentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.source = self.root / "source.py"
        self.source.write_bytes(b"value=1\n\x00\xff")
        self.output = self.root / "result.bin"
        self.output.write_bytes(b"\x00result\xff")
        self.spec = GateCheckSpec(
            check_id="host_content",
            entry_type="long_gate_probe",
            display="host check",
            args=("python", "check.py"),
            capture_output=True,
            output_policy="exact",
            input_file_scopes=("source.py",),
            env_keys=("APS_ENV", "SECRET_KEY"),
            output_result_files=("result.bin",),
            reuse_policy="success_or_failure",
        )
        self.entry = gate_entries([self.spec])[0]
        self.result = _result()
        self.paths = patch.object(fingerprint, "_git_path_sources", return_value=({"source.py"}, set(), "available"))
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.identity = patch.object(
            schema,
            "repo_identity",
            side_effect=lambda repo_root: {
                "checkout_root_realpath": os.path.realpath(str(repo_root)),
                "git_common_dir_realpath": os.path.realpath(os.path.join(str(repo_root), ".git")),
            },
        )
        self.identity.start()
        self.addCleanup(self.identity.stop)
        self.metadata = long_gate_cache_metadata(str(self.root), cache_dir=CACHE_DIR)

    def entry_for(self, **spec_overrides):
        return gate_entries([replace(self.spec, **spec_overrides)])[0]

    def current(self, entry=None):
        return fingerprint.fingerprint_entry(entry or self.entry, str(self.root), strict=True)

    def evaluate(self, entry=None, *, current=None, kind="success"):
        entry = entry or self.entry
        return cache.evaluate_cache(
            entry,
            self.current(entry) if current is None else current,
            kind=kind,
            metadata=self.metadata,
            repo_root=str(self.root),
            cache_dir=CACHE_DIR,
        )

    def write_success(self, entry=None, result=None, *, current=None):
        entry = entry or self.entry
        prepared = cache.prepare_success_write(
            entry,
            self.current(entry) if current is None else current,
            result or self.result,
            entry.spec.output_result_files,
            receipt_path=RECEIPT_PATH,
            run_id="host-run",
            metadata=self.metadata,
            repo_root=str(self.root),
            cache_dir=CACHE_DIR,
        )
        cache.commit_prepared_success_write(str(self.root), prepared)

    def write_failure(self, entry, result):
        cache.write_failure(
            entry,
            self.current(entry),
            result,
            receipt_path=RECEIPT_PATH,
            run_id="original-run",
            metadata=self.metadata,
            repo_root=str(self.root),
            cache_dir=CACHE_DIR,
        )

    def saved(self, kind="success"):
        path = self.root / "evidence" / "QualityGate" / "long_gate" / "results" / f"host_content.v2.{kind}.json"
        return path, json.loads(path.read_text())

    def test_existence_scopes_record_current_paths_without_reading_content(self):
        entry = self.entry_for(existence_file_scopes=("docs/**/*.md",))
        doc = self.root / "docs" / "guide.md"
        doc.parent.mkdir()
        doc.write_text("first\n", encoding="utf-8")
        before = self.current(entry)
        self.assertEqual(before["components"]["existence"], {"paths": ["docs/guide.md"]})
        doc.write_text("edited\n", encoding="utf-8")
        self.assertTrue(content_equal(before, self.current(entry)))
        doc.unlink()
        after = self.current(entry)
        self.assertEqual(after["components"]["existence"], {"paths": []})
        self.assertEqual(
            fingerprint.diff_fingerprints(before, after)["reasons"], ["fingerprint component changed: existence"]
        )

    def test_source_command_and_public_environment_use_original_content(self):
        self.assertEqual(base64.b64decode(read_file_content(str(self.source))), self.source.read_bytes())
        self.assertEqual(canonical_content({"b": 2, "a": 1}), '{"a":1,"b":2}')
        self.assertFalse(content_equal(1, 1.0))
        self.assertFalse(content_equal(False, 0))
        with patch.dict(os.environ, {"SECRET_KEY": "private-only-in-memory", "APS_ENV": "host"}, clear=True):
            before = self.current()
            self.assertEqual(before["schema_version"], LONG_GATE_FINGERPRINT_SCHEMA_VERSION)
            self.assertEqual(before["components"]["command"], self.entry.command)
            self.assertEqual(before["components"]["environment"]["values"]["SECRET_KEY"], {"present": True})
            self.assertNotIn("private-only-in-memory", canonical_content(before))
            self.assertEqual(before["components"]["environment"]["non_reusable_env_keys"], ["SECRET_KEY"])
            for kind in ("success", "failure"):
                decision = self.evaluate(current=before, kind=kind).decision
                self.assertEqual((decision.kind, decision.cause), ("run", DecisionCause.CACHE_UNAVAILABLE))
                self.assertTrue(decision.cache_unavailable)
                self.assertEqual(decision.non_reusable_env_keys, ("SECRET_KEY",))
            self.source.write_bytes(b"value=2\n\x00\xff")
            after = self.current()
            self.assertTrue(fingerprint.diff_fingerprints(before, after)["changed"])
            self.assertEqual(fingerprint.diff_fingerprints(before, before)["changed"], False)
            self.assertEqual(
                fingerprint._runtime_probe_cache_key("node", "/node", {"PATH": "/bin", "SECRET_KEY": "a"}),
                ("node", "/node", (("PATH", "/bin"), ("SECRET_KEY", "a"))),
            )
            self.assertEqual(
                fingerprint._powershell_version(environment={"PATH": "", "APS_TEST_POWERSHELL": "missing-pwsh"}),
                "__missing_powershell__:missing-pwsh",
            )
            self.assertEqual(
                fingerprint.fingerprint_environment(
                    ["node_executable_realpath", "node_version"],
                    environment={"PATH": "", "WORKBENCH_NODE": "missing-node"},
                    repo_root=str(self.root),
                )["values"],
                {
                    "node_executable_realpath": "__missing_node__:missing-node",
                    "node_version": "__missing_node__:missing-node",
                },
            )
            with self.assertRaises(fingerprint.LongGateFingerprintError):
                fingerprint.fingerprint_environment(
                    ["API_TOKEN"], environment={"API_TOKEN": "private"}, repo_root=str(self.root)
                )
        credential_source = self.root / "config.env"
        credential_source.write_bytes(b"value=private-only-in-memory")
        for raw_secret in ("private-only-in-memory", "  private-only-in-memory  \n"):
            with patch.dict(os.environ, {"SECRET_KEY": raw_secret}, clear=True):
                with self.assertRaises(ValueError) as rejected:
                    read_file_content(str(credential_source))
                self.assertNotIn("private-only-in-memory", str(rejected.exception))
        with patch.dict(os.environ, {"SECRET_KEY": "   \t\n  ", "APS_ENV": "host"}, clear=True):
            blank_fp = self.current()
            self.assertEqual(blank_fp["components"]["environment"]["values"]["SECRET_KEY"], {"present": False})
            self.assertEqual(blank_fp["components"]["environment"]["non_reusable_env_keys"], [])
            self.assertFalse(self.evaluate(current=blank_fp).decision.cache_unavailable)
        if os.name != "nt":
            backslash_rel = "tools/name\\part.py"
            backslash_file = self.root / "tools" / "name\\part.py"
            backslash_file.parent.mkdir(parents=True, exist_ok=True)
            backslash_file.write_bytes(b"x = 1\n")
            backslash_entry = self.entry_for(
                input_file_scopes=("tools/**/*.py",), env_keys=("APS_ENV",), output_result_files=()
            )
            with patch.object(
                fingerprint, "_git_path_sources", return_value=({backslash_rel}, set(), "available")
            ), patch.dict(os.environ, {"APS_ENV": "host"}, clear=True):
                bs_before = self.current(backslash_entry)
                bs_files = bs_before["components"]["files"]["files"]
                self.assertEqual([row["path"] for row in bs_files], [backslash_rel])
                self.assertEqual(bs_files[0]["kind"], "file")
                self.assertEqual(bs_files[0]["source"], "tracked")
                backslash_file.write_bytes(b"x = 2\n")
                bs_after = self.current(backslash_entry)
                self.assertTrue(fingerprint.diff_fingerprints(bs_before, bs_after)["changed"])
            backslash_file.unlink()
        repo_pyproject = REPO_ROOT / "pyproject.toml"
        token_cfg = self.root / "pyproject.toml"
        token_cfg.write_bytes(repo_pyproject.read_bytes() + b'\ncustom_token = "false"\n')
        runner_script = self.root / "scripts" / "run_quality_gate.py"
        runner_script.parent.mkdir(parents=True, exist_ok=True)
        runner_script.write_bytes(b"RUNNER_FLAG = 'false'\n")
        with patch.dict(
            os.environ,
            {"TOKENIZERS_PARALLELISM": "false", "CUSTOM_TOKEN": "false"},
            clear=True,
        ):
            self.assertEqual(base64.b64decode(read_file_content(str(token_cfg))), token_cfg.read_bytes())
            meta = long_gate_cache_metadata(str(self.root), cache_dir=CACHE_DIR)
            self.assertEqual(meta["runner_version_content"][0]["path"], "scripts/run_quality_gate.py")
        runner_script.write_bytes(b"LEAKED = 'private-only-in-memory'\n")
        with patch.dict(os.environ, {"SECRET_KEY": "private-only-in-memory"}, clear=True):
            with self.assertRaises(SensitiveSourceError) as leaked:
                long_gate_cache_metadata(str(self.root), cache_dir=CACHE_DIR)
            self.assertNotIn("private-only-in-memory", str(leaked.exception))
        runner_script.unlink()
        self.assertEqual(PRIVATE_ENVIRONMENT_KEYS, frozenset({"SECRET_KEY"}))
        self.assertIn("PYTHONHASHSEED", PUBLIC_ENVIRONMENT_KEYS)
        runtime_file = self.root / "aps_runtime.json"
        runtime_file.write_bytes(b'{"shutdown_token":"fixture-value"}')
        with self.assertRaises(ValueError):
            read_file_content(str(runtime_file))
        probe_spec = GateCheckSpec(
            check_id="host_content",
            entry_type="version_or_env_probe",
            display="host check",
            args=("python", "check.py"),
            capture_output=True,
            output_policy="exact",
            reuse_policy="none",
        )
        probe = gate_entries([probe_spec])[0]
        self.assertEqual(probe.index, 1)
        self.assertEqual(probe.command, normalize_quality_gate_command(probe_spec.to_command_dict()))
        self.assertEqual(
            probe.command,
            {
                "display": "host check",
                "args": ["python", "check.py"],
                "capture_output": True,
                "output_policy": "exact",
                "env_overlay": {},
                "check_id": "host_content",
                "entry_type": "version_or_env_probe",
                "proof_kind": None,
                "reuse_policy": "none",
                "runner_handler": "default",
            },
        )
        self.assertFalse(probe.spec.reuse_allowed)

    def test_gate_json_load_rejects_non_finite_numbers_and_non_objects(self):
        path = self.root / "gate.json"
        for text in ('{"x": NaN}', '{"x": Infinity}', '{"x": -Infinity}', '{"x": 1e999}', '{"x": [1, -1e999]}'):
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(GateJsonError) as rejected:
                load_gate_json(str(path))
            self.assertFalse(rejected.exception.missing)
            self.assertIn("non-finite", str(rejected.exception))
        path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(GateJsonError, "top-level value is not an object"):
            load_gate_json(str(path))
        path.write_bytes(b'{"x": "\xe4\xb8')
        with self.assertRaises(GateJsonError) as truncated:
            load_gate_json(str(path))
        self.assertFalse(truncated.exception.missing)
        path.write_text('{"x": 1.5, "y": 1e300, "z": -0.0}', encoding="utf-8")
        self.assertEqual(load_gate_json(str(path)), {"x": 1.5, "y": 1e300, "z": -0.0})
        path.unlink()
        with self.assertRaises(GateJsonError) as missing:
            load_gate_json(str(path))
        self.assertTrue(missing.exception.missing)

    def test_success_reuse_binds_source_command_logs_outputs_and_status(self):
        current = self.current()
        with patch.dict(os.environ, {"SECRET_KEY": "redact-this-value"}):
            self.write_success(result=replace(self.result, stdout="redact-this-value\r\nall passed\n"), current=current)
        path, saved = self.saved()
        self.assertEqual(saved["schema_version"], 3)
        self.assertEqual(saved["stdout_content"], "[REDACTED]\r\nall passed\n")
        self.assertEqual((saved["receipt_path"], saved["run_id"], saved["command_index"]), (RECEIPT_PATH, "host-run", 1))
        self.assertEqual(base64.b64decode(saved["output_files"][0]["content_base64"]), self.output.read_bytes())
        reused = self.evaluate(current=current)
        self.assertEqual((reused.decision.kind, reused.decision.cause), ("reuse", DecisionCause.MATCHED))
        self.assertEqual(reused.record.stdout_content, saved["stdout_content"])
        self.output.write_bytes(b"\x00RESULT\xff")
        self.assertIn("output files", self.evaluate(current=current).decision.reason)
        self.output.write_bytes(b"\x00result\xff")
        log = self.root / saved["stdout_log_path"]
        log.write_bytes(b"changed\r\n")
        self.assertIn("logs", self.evaluate(current=current).decision.reason)
        log.write_bytes(saved["stdout_content"].encode("utf-8"))
        changed_command = self.entry_for(args=("python", "other.py"))
        changed = self.evaluate(changed_command).decision
        self.assertEqual((changed.cause, changed.reason), (DecisionCause.REJECTED, "input fingerprint changed"))
        self.assertIn("command", [row["component"] for row in changed.fingerprint_diff])
        self.source.write_bytes(b"value=2\n\x00\xff")
        self.assertEqual(self.evaluate().decision.reason, "input fingerprint changed")
        original_log_path = saved["stdout_log_path"]
        saved["stdout_log_path"] = "../outside.log"
        path.write_text(json.dumps(saved))
        self.assertEqual(self.evaluate(current=current).decision.reason, "previous logs path changed: ../outside.log")
        saved["stdout_log_path"] = original_log_path
        path.write_text(json.dumps(saved).replace('"duration_s": 0.25', '"duration_s": NaN'))
        nan_decision = self.evaluate(current=current).decision
        self.assertEqual(nan_decision.cause, DecisionCause.REJECTED)
        self.assertTrue(nan_decision.reason.startswith("cache unreadable/corrupt: non-finite"))

    def test_failure_reuse_retains_nonzero_returncode_and_original_logs(self):
        entry = self.entry_for(output_result_files=())
        current = self.current(entry)
        self.write_failure(entry, replace(self.result, returncode=3, stderr="failed check\n"))
        path, saved = self.saved("failure")
        cached = self.evaluate(entry, current=current, kind="failure")
        self.assertEqual((cached.decision.kind, cached.decision.cause), ("cached_failure", DecisionCause.MATCHED))
        self.assertEqual((cached.record.returncode, cached.record.stderr_content), (3, "failed check\n"))
        self.assertEqual((saved["returncode"], saved["run_id"], saved["receipt_path"]), (3, "original-run", RECEIPT_PATH))
        self.assertNotIn("result_hash", saved)
        saved["returncode"] = 0
        path.write_text(json.dumps(saved))
        self.assertEqual(
            self.evaluate(entry, current=current, kind="failure").decision.reason, "previous failure returncode was zero"
        )
        saved["returncode"] = 3
        path.write_text(json.dumps(saved))
        (self.root / saved["stderr_log_path"]).write_bytes(b"other error!\n")
        self.assertIn("logs", self.evaluate(entry, current=current, kind="failure").decision.reason)

    def test_missing_unreadable_or_mistyped_cache_reruns_with_original_reason(self):
        failure_entry = self.entry_for(output_result_files=())
        self.write_success()
        self.write_failure(failure_entry, replace(self.result, returncode=2))
        for kind, entry in (("success", self.entry), ("failure", failure_entry)):
            path, saved = self.saved(kind)
            current = self.current(entry)
            for field, value in (("returncode", True), ("schema_version", "3"), ("duration_s", "0.25")):
                path.write_text(json.dumps({**saved, field: value}))
                decision = self.evaluate(entry, current=current, kind=kind).decision
                self.assertEqual(
                    (decision.kind, decision.reason),
                    ("run", "cache unreadable/corrupt: numeric field has invalid type"),
                )
            path.write_text(json.dumps({**saved, "schema_version": 2}))
            self.assertEqual(self.evaluate(entry, current=current, kind=kind).decision.reason, "cache schema changed")
            path.write_text(json.dumps(saved).replace('"duration_s": 0.25', '"duration_s": 1e999'))
            self.assertIn("non-finite", self.evaluate(entry, current=current, kind=kind).decision.reason)
            path.write_text("[]")
            self.assertEqual(
                self.evaluate(entry, current=current, kind=kind).decision.reason,
                "cache unreadable/corrupt: top-level value is not an object",
            )
            path.unlink()
            missing = self.evaluate(entry, current=current, kind=kind).decision
            self.assertEqual((missing.cause, missing.reason), (DecisionCause.MISSING, f"no previous {kind} cache"))

    def test_summary_references_owned_content_and_preserves_actual_results(self):
        current = self.current()
        cached = "evidence/QualityGate/long_gate/results/host_content.v2.success.json"
        result = replace(
            self.result,
            execution_mode="reused_success_cache",
            duration_kind="reuse_overhead",
            original_duration_s=3.0,
        )
        decision = CacheDecision(
            "reuse",
            DecisionCause.MATCHED,
            "fingerprint matched previous successful result",
            fingerprint_diff=(
                {
                    "component": "files",
                    "reason": "modified input file",
                    "path": "source.py",
                    "previous": {"content_base64": "previous-source-bytes"},
                    "current": current,
                },
            ),
            previous_result_path=cached,
        )
        rt = RuntimeEntry(
            self.entry, decision, current, None, StepOutcome(result, RECEIPT_PATH, ("result.bin",), False)
        )
        summary = build_long_gate_summary(
            run_id="host-run",
            repo_root=str(self.root),
            head_sha="host-head",
            worktree_clean=True,
            cache_enabled=True,
            entries=[summary_entry(rt)],
            failure=None,
            cache_dir=CACHE_DIR,
        )
        paths = write_long_gate_summary(summary, str(self.root))
        stored = json.loads((self.root / paths["summary_json"]).read_text())
        self.assertEqual(stored["schema_version"], 3)
        row = stored["entries"][0]
        self.assertEqual(row["input_snapshot"], {"schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION, "path_count": 1})
        self.assertEqual(row["fingerprint_diff"], [
            {"component": "files", "reason": "modified input file", "path": "source.py"},
        ])
        self.assertEqual(row["output_files"], [{"path": "result.bin"}])
        self.assertEqual((row["previous_result_path"], row["receipt_path"]), (cached, RECEIPT_PATH))
        self.assertEqual((row["returncode"], row["duration_s"], row["original_duration_s"]), (0, 0.25, 3.0))
        self.assertEqual(stored["counts"], {"executed": 0, "reused": 1, "failed": 0, "disabled": 0})
        self.assertNotIn("current_fingerprint", row)
        self.assertNotIn("content_base64", canonical_content(stored))
        self.assertEqual(base64.b64decode(current["components"]["files"]["files"][0]["content_base64"]),
                         self.source.read_bytes())

    def test_real_gate_entries_track_execution_inputs_and_ignore_bytecode(self):
        execution_sources = {
            **{
                relative: (REPO_ROOT / relative).read_bytes()
                for relative in (
                    "tests/workbench/decision_comparison_contract.cjs",
                    "frontend/workbench/app/RunDecisionProcessChart.jsx",
                    "tests/workbench/fixtures/decision_candidate_baseline.json",
                    "scripts/workbench/compile.cjs",
                    "scripts/workbench/esbuild-manifest.json",
                    "vendor/node_modules/esbuild/package.json",
                    "tools/generate_schema_sql.py",
                    "tools/resolve_iscc.ps1",
                    "tools/wufenchang_demo/blueprint.py",
                    "packaging/win7/offline-manifest.json",
                )
            },
            ".codex/hooks/guard_pre_tool_use.py": b"print('hook')\n",
            "vendor/node_modules/@esbuild/win32-x64/esbuild.exe": b"MZ\x00win32-esbuild\n",
            "vendor/wheels/networkx-3.1-py3-none-any.whl": b"PK\x03\x04wheel\n",
        }
        collect_sources = {
            relative: (REPO_ROOT / relative).read_bytes()
            for relative in ("开发文档/技术债务治理台账.md", "tools/quality_gate_ledger.py")
        }
        for relative, original in {**execution_sources, **collect_sources}.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)
        entries = {entry.spec.check_id: entry for entry in gate_entries(build_quality_gate_check_specs(str(REPO_ROOT)))}
        full, collect = entries["full_test_debt"], entries["pytest_collect_all"]
        nodeid = "tests/workbench/test_ui_refinement_node_contracts.py::test_shared_ui_node_contract[workbench/decision_comparison_contract.cjs]"
        collect_stdout = nodeid + "\n\n1 test collected\n"
        collect_log = "evidence/QualityGate/v4/logs/12_collect.stdout.log"
        (self.root / collect_log).parent.mkdir(parents=True, exist_ok=True)
        (self.root / collect_log).write_bytes(collect_stdout.encode("utf-8"))
        payload = build_collect_nodeids_payload(
            collect_stdout, pytest_version="8.3.5", collect_stdout_log_path=collect_log
        )
        self.assertEqual(write_collect_nodeids(payload, repo_root=str(self.root)), QUALITY_GATE_COLLECT_NODEIDS_REL)
        full_payload = {
            "exitstatus": 0,
            "collection_error_count": 0,
            "classifications": {
                "required_or_quality_gate_self_failure": [],
                "main_style_isolation_candidate": [],
                "candidate_test_debt": [],
            },
            "collected_nodeids": [nodeid],
            "reports": [{"nodeid": nodeid, "when": "call", "outcome": "passed"}],
        }
        for relative in full.spec.output_result_files:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(full_payload), encoding="utf-8")
        # Hold host probes fixed while exercising real file scopes and cache comparisons.
        with patch.dict(os.environ, {}, clear=True), patch.object(
            fingerprint, "fingerprint_environment", return_value={"values": {}, "non_reusable_env_keys": []}
        ):
            for entry in (full, collect):
                stdout = payload["collect_stdout_content"] if entry is collect else "1 passed\n"
                self.write_success(entry, replace(self.result, stdout=stdout))
                self.assertEqual(self.evaluate(entry).decision.kind, "reuse")
            for entry, sources in ((full, execution_sources), (collect, collect_sources)):
                for relative, original in sources.items():
                    with self.subTest(path=relative):
                        path = self.root / relative
                        try:
                            path.write_bytes(original + b"\nchanged\n")
                            decision = self.evaluate(entry).decision
                            self.assertEqual((decision.kind, decision.reason), ("run", "input fingerprint changed"))
                        finally:
                            path.write_bytes(original)
                        self.assertEqual(self.evaluate(entry).decision.kind, "reuse")
            for relative in ("tests/workbench/__pycache__/contract.pyc", "scripts/workbench/__pycache__/compile.pyc"):
                path = self.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"new bytecode")
                self.assertEqual(self.evaluate(full).decision.kind, "reuse")
                path.write_bytes(b"modified bytecode")
                self.assertEqual(self.evaluate(full).decision.kind, "reuse")
            (self.root / collect_log).write_bytes(b"tampered collect log\n")
            invalid = self.evaluate(full).decision
            self.assertEqual(
                (invalid.cause, invalid.reason), (DecisionCause.COLLECT_NODEIDS_INVALID, "collect nodeids proof is invalid")
            )

    def test_collect_and_required_use_full_nodeids_and_actual_reports(self):
        stdout = "tests/example.py::test_one\ntests/example.py::test_two[param]\n\n2 tests collected in 0.1s\n"
        log_rel = "evidence/QualityGate/v4/logs/12_collect.stdout.log"
        (self.root / log_rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / log_rel).write_bytes(stdout.encode("utf-8"))
        payload = build_collect_nodeids_payload(stdout, pytest_version="8.3.5", collect_stdout_log_path=log_rel)
        self.assertEqual(payload["collect_stdout_content"], stdout)
        write_collect_nodeids(payload, repo_root=str(self.root))
        collect = fingerprint._collect_nodeids_component(str(self.root))
        self.assertEqual(collect["error"], "")
        self.assertEqual(collect["nodeids"], payload["nodeids"])
        tampered = {**payload, "nodeids": ["tests/example.py::test_other"]}
        (self.root / QUALITY_GATE_COLLECT_NODEIDS_REL).write_text(json.dumps(tampered))
        self.assertEqual(
            fingerprint._collect_nodeids_component(str(self.root))["error"],
            "collect_nodeids payload is invalid: stdout does not match nodeids",
        )
        classification_keys = (
            "required_or_quality_gate_self_failure",
            "main_style_isolation_candidate",
            "candidate_test_debt",
        )
        full_payload = {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "baseline_kind": "after_main_style_isolation",
            "exitstatus": 0,
            "pytest_args": list(FORMAL_FULL_TEST_PYTEST_ARGS),
            "collection_errors": [],
            "os_name": os.name,
            "classifications": {key: [] for key in classification_keys},
            "collected_nodeids": payload["nodeids"],
            "reports": [
                {
                    "nodeid": nodeid,
                    "when": "call",
                    "outcome": "passed",
                    "xfail_marker_present": False,
                    "xfail_marker_reason": "",
                    "xfail_marker_strict": False,
                    "xfail_marker_run": False,
                    "wasxfail_reason": "",
                    "strict_xpass": False,
                }
                for nodeid in payload["nodeids"]
            ],
            "summary": {
                "collected_count": len(payload["nodeids"]),
                "failed_nodeid_count": 0,
                "collection_error_count": 0,
                "outcome_counts": {"call:passed": len(payload["nodeids"])},
                "classification_counts": {key: 0 for key in classification_keys},
            },
        }
        required_tests = ["tests/example.py"]
        required_groups = [
            {
                "group_id": "example",
                "label": "Example required regressions",
                "target_paths": required_tests,
                "input_file_scopes": [
                    "app.py",
                    "schema.sql",
                    "core/**/*.py",
                    "data/**/*.py",
                    "web/**/*.py",
                    "desktop/**/*.py",
                    "frontend/workbench/app/**/*",
                    "scripts/workbench/**/*",
                    "templates/**/*.html",
                    "static/workbench/**/*",
                    "static/**/*",
                ],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
                "env_keys": [],
            }
        ]
        verified = verify_required_regressions_from_payload(
            full_payload,
            repo_root=str(REPO_ROOT),
            required_tests=required_tests,
            required_groups=required_groups,
        )
        self.assertEqual(verified["required_target_paths"], required_tests)
        self.assertEqual(verified["required_nodeids"], payload["nodeids"])
        self.assertEqual(verified["required_reports"][payload["nodeids"][0]], [full_payload["reports"][0]])
        self.assertNotIn("required_target_hash", verified)
        bad = copy.deepcopy(full_payload)
        bad["reports"][0]["xfail_marker_present"] = True
        with self.assertRaises(RequiredRegressionProofError):
            verify_required_regressions_from_payload(
                bad,
                repo_root=str(REPO_ROOT),
                required_tests=required_tests,
                required_groups=required_groups,
            )
        with self.assertRaises(RequiredRegressionProofError):
            verify_required_regressions_from_payload(
                full_payload,
                repo_root=str(REPO_ROOT),
                required_tests=["tests/missing.py"],
                required_groups=required_groups,
            )
        setup_only = copy.deepcopy(full_payload)
        setup_only["reports"][0]["when"] = "setup"
        with self.assertRaisesRegex(QualityGateError, "终态报告"):
            verify_required_regressions_from_payload(
                setup_only,
                repo_root=str(REPO_ROOT),
                required_tests=required_tests,
                required_groups=required_groups,
            )

    def test_node_resolution_and_fingerprint_skip_broken_path_node_and_bind_working_fallback(self):
        from tests._support.node_runtime_support import resolve_node_binary

        bad_dir = self.root / "bad_bin"
        good_dir = self.root / "good_bin"
        bad_dir.mkdir(parents=True, exist_ok=True)
        good_dir.mkdir(parents=True, exist_ok=True)
        bad_log = self.root / "bad_node_calls.log"
        bad_node = bad_dir / "node"
        good_node = good_dir / "node"
        bad_node.write_text(f"#!/bin/sh\necho x >> {bad_log}\nexit 1\n", encoding="utf-8")
        good_node.write_text("#!/bin/sh\necho v20.11.1\n", encoding="utf-8")
        bad_node.chmod(0o755)
        good_node.chmod(0o755)

        env = {"PATH": f"{bad_dir}{os.pathsep}{good_dir}"}
        resolved_test_node = resolve_node_binary(env)
        env_fp = fingerprint.fingerprint_environment(
            ["node_executable_realpath", "node_version"], environment=env, repo_root=str(self.root)
        )

        expected_path = os.path.realpath(str(good_node))
        self.assertEqual(os.path.realpath(resolved_test_node), expected_path)
        self.assertEqual(
            env_fp["values"],
            {"node_executable_realpath": expected_path, "node_version": "v20.11.1"},
        )
        self.assertEqual(len(bad_log.read_text(encoding="utf-8").splitlines()), 1)

        bad_only_env = {"PATH": str(bad_dir)}
        fallback_test_node = resolve_node_binary(bad_only_env)
        fallback_fp = fingerprint.fingerprint_environment(
            ["node_executable_realpath", "node_version"],
            environment=bad_only_env,
            repo_root=str(self.root),
        )["values"]
        self.assertNotEqual(os.path.realpath(fallback_test_node), os.path.realpath(str(bad_node)))
        self.assertEqual(os.path.realpath(fallback_test_node), fallback_fp["node_executable_realpath"])
        self.assertTrue(fallback_fp["node_version"].startswith("v"))

    def test_content_equal_preserves_type_signed_zero_and_nan_validation(self):
        self.assertFalse(content_equal(True, 1))
        self.assertFalse(content_equal(False, 0))
        self.assertFalse(content_equal(1, 1.0))
        self.assertFalse(content_equal(0, 0.0))
        self.assertFalse(content_equal({"nested": [1, False, 0.0]}, {"nested": [1.0, False, 0.0]}))
        self.assertFalse(content_equal(0.0, -0.0))
        self.assertFalse(content_equal({"z": 0.0}, {"z": -0.0}))
        self.assertTrue(content_equal(-0.0, -0.0))
        self.assertTrue(content_equal([1, "a", (True, None)], (1, "a", [True, None])))
        self.assertTrue(content_equal({"b": 2, "a": 1}, {"a": 1, "b": 2}))
        self.assertTrue(content_equal({1: "x"}, {"1": "x"}))
        self.assertTrue(content_equal({1: "x", 2: "y"}, {"1": "x", "2": "y"}))
        self.assertFalse(content_equal({2: "x", 10: "y"}, {"2": "x", "10": "y"}))
        self.assertNotEqual(canonical_content({2: "x", 10: "y"}), canonical_content({"2": "x", "10": "y"}))
        self.assertTrue(content_equal({None: 1}, {"null": 1}))
        self.assertTrue(content_equal({False: 2, True: 3}, {"false": 2, "true": 3}))
        with self.assertRaises(TypeError):
            content_equal({None: 1, False: 2}, {"null": 1, "false": 2})

        for bad_left, bad_right in (
            ([1, float("nan")], [2, 3]),
            ([1, 2], [2, float("inf")]),
            ({"a": 1, "b": float("-inf")}, {"a": 2, "b": 0.0}),
            ({float("nan"): 1}, {"x": 1}),
        ):
            with self.assertRaises(ValueError):
                content_equal(bad_left, bad_right)

        with self.assertRaises(TypeError):
            content_equal({"a": {1, 2}}, {"a": [1, 2]})

    def test_diff_fingerprint_components_covers_missing_keys_files_metadata_and_order(self):
        base = self.current()
        self.assertEqual(
            fingerprint.diff_fingerprint_components(base, copy.deepcopy(base)),
            {"changed": False, "components": []},
        )
        self.assertEqual(
            fingerprint.diff_fingerprints(base, copy.deepcopy(base)),
            {"changed": False, "reasons": [], "components": []},
        )

        # Missing key vs explicit None at component level and top level
        with_none_comp = copy.deepcopy(base)
        with_none_comp["components"]["extra_comp"] = None
        comp_diff = fingerprint.diff_fingerprints(base, with_none_comp)
        self.assertTrue(comp_diff["changed"])
        self.assertTrue(any(row["component"] == "extra_comp" for row in comp_diff["components"]))

        with_none_top = copy.deepcopy(base)
        with_none_top["extra"] = None
        top_diff = fingerprint.diff_fingerprints(base, with_none_top)
        self.assertTrue(top_diff["changed"])
        self.assertTrue(any(row["component"] == "extra" for row in top_diff["components"]))

        # Files metadata change (git_source_status / paths) without file row change
        meta_changed = copy.deepcopy(base)
        meta_changed["components"]["files"]["git_source_status"] = "unavailable"
        meta_diff = fingerprint.diff_fingerprints(base, meta_changed)
        self.assertTrue(meta_diff["changed"])
        self.assertTrue(
            any(
                row["component"] == "files" and row.get("field") == "git_source_status"
                for row in meta_diff["components"]
            )
        )

        # Files list order change with identical file set
        two_files_fp_a = copy.deepcopy(base)
        file_a = {"path": "a.py", "exists": True, "kind": "file", "source": "git", "content_base64": "YQ=="}
        file_b = {"path": "b.py", "exists": True, "kind": "file", "source": "git", "content_base64": "Yg=="}
        two_files_fp_a["components"]["files"]["files"] = [file_a, file_b]
        two_files_fp_b = copy.deepcopy(two_files_fp_a)
        two_files_fp_b["components"]["files"]["files"] = [file_b, file_a]
        order_diff = fingerprint.diff_fingerprints(two_files_fp_a, two_files_fp_b)
        self.assertTrue(order_diff["changed"])
        self.assertTrue(
            any(
                row["component"] == "files" and row["reason"] == "file list order or structure changed"
                for row in order_diff["components"]
            )
        )

    def test_fingerprint_translates_sensitive_sources_to_domain_error(self):
        secret = "fingerprint-secret-do-not-persist"
        self.source.write_text(f'LEAK = "{secret}"\n', encoding="utf-8")
        with patch.dict(os.environ, {"SECRET_KEY": secret, "APS_ENV": "host"}, clear=True):
            with self.assertRaises(fingerprint.LongGateFingerprintError) as file_err:
                self.current()
            self.assertEqual(file_err.exception.details, {"failure_kind": "source_content_unavailable"})
            self.assertIsInstance(file_err.exception.__cause__, SensitiveSourceError)
            self.assertIn("SECRET_KEY", str(file_err.exception))
            self.assertNotIn(secret, str(file_err.exception))

            if os.name != "nt":
                link_path = self.root / "linked_source.py"
                link_path.symlink_to(self.source)
                with patch.object(
                    fingerprint, "_git_path_sources", return_value=({"linked_source.py"}, set(), "available")
                ):
                    with self.assertRaises(fingerprint.LongGateFingerprintError) as link_err:
                        fingerprint.fingerprint_files(["linked_source.py"], str(self.root), strict=True)
                self.assertEqual(link_err.exception.details, {"failure_kind": "source_content_unavailable"})
                self.assertIsInstance(link_err.exception.__cause__, SensitiveSourceError)
                self.assertNotIn(secret, str(link_err.exception))

            scanner_file = self.root / "tools" / "architecture_scan_cache.py"
            scanner_file.parent.mkdir(parents=True, exist_ok=True)
            scanner_file.write_text(f'LEAK = "{secret}"\n', encoding="utf-8")
            with self.assertRaises(fingerprint.LongGateFingerprintError) as env_err:
                fingerprint.fingerprint_environment(
                    ["architecture_scan_cache_metadata"],
                    strict=True,
                    repo_root=str(self.root),
                )
            self.assertEqual(env_err.exception.details, {"failure_kind": "source_content_unavailable"})
            self.assertIsInstance(env_err.exception.__cause__, SensitiveSourceError)
            self.assertNotIn(secret, str(env_err.exception))

    def test_local_receipts_go_through_the_single_receipt_admission(self):
        probe_spec = GateCheckSpec(
            check_id="host_content",
            entry_type="version_or_env_probe",
            display="host check",
            args=("python", "check.py"),
            capture_output=True,
            output_policy="exact",
            reuse_policy="none",
        )
        entries = gate_entries([probe_spec])
        environment = {"keys": [], "values": {}, "non_reusable_env_keys": []}
        valid = build_receipt(
            entries[0].command, run_id="host-run", command_index=1, result=replace(self.result, duration_s=1.25),
            environment=environment,
        )
        retired = build_receipt(
            {**entries[0].command, "check_id": "retired_check"}, run_id="host-run", command_index=2,
            result=self.result, environment=environment,
        )
        receipts_dir = self.root / "evidence" / "QualityGate" / "v4" / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        (receipts_dir / "01_matched.json").write_text(json.dumps(valid), encoding="utf-8")
        missing_id = {key: value for key, value in valid.items() if key != "check_id"}
        (receipts_dir / "02_missing_id.json").write_text(json.dumps(missing_id), encoding="utf-8")
        (receipts_dir / "03_unknown_id.json").write_text(json.dumps(retired), encoding="utf-8")
        (receipts_dir / "04_truncated_utf8.json").write_bytes(b'{"check_id":"host_content","display":"\xe4\xb8')
        (receipts_dir / "05_nan.json").write_text(
            json.dumps(valid).replace('"duration_s": 1.25', '"duration_s": NaN'), encoding="utf-8"
        )
        rows = load_local_quality_gate_receipts(str(self.root))
        prefix = "evidence/QualityGate/v4/receipts/"
        self.assertEqual(
            [path for path, _admitted in rows],
            [prefix + name for name in ("01_matched.json", "02_missing_id.json", "03_unknown_id.json",
                                        "04_truncated_utf8.json", "05_nan.json")],
        )
        by_entry, warnings = group_local_receipts(entries, rows)
        self.assertEqual([receipt.path for receipt in by_entry["host_content"]], [prefix + "01_matched.json"])
        self.assertEqual(by_entry["host_content"][0].duration_s, 1.25)
        self.assertEqual(
            warnings,
            [
                f"receipt rejected: {prefix}02_missing_id.json: UNBOUND: quality gate command receipt check_id invalid",
                "local receipt check_id is not in current plan: retired_check",
                f"receipt rejected: {prefix}04_truncated_utf8.json: UNBOUND: quality gate command receipt unreadable",
                f"receipt rejected: {prefix}05_nan.json: UNBOUND: quality gate command receipt unreadable",
            ],
        )


if __name__ == "__main__":
    unittest.main()
