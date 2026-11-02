"""Host-only source and receipt contracts; these tests do not enter the product gate."""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools import benchmark_full_test_debt_shards as shard_tool
from tools import quality_gate_shared as shared
from tools import report_full_test_debt_durations as report_tool
from tools.long_gate_schema import canonical_content


def _command(policy="exact"):
    return {
        "display": "python receipt-content-contract",
        "args": [sys.executable, "-c", "print('real output')"],
        "capture_output": True,
        "output_policy": policy,
        "env_overlay": {},
    }


def _receipt_files(root, command, stdout="real output\n", *, run_id="run-content"):
    logs = shared.QUALITY_GATE_LOGS_DIR_REL.replace("\\", "/")
    stdout_path, stderr_path = logs + "/01.stdout.log", logs + "/01.stderr.log"
    (root / logs).mkdir(parents=True, exist_ok=True)
    with (root / stdout_path).open("w", encoding="utf-8", newline="") as stream:
        stream.write(shared.sanitize_quality_gate_output(stdout))
    with (root / stderr_path).open("w", encoding="utf-8", newline="") as stream:
        stream.write("")
    receipt = shared.build_quality_gate_command_receipt(
        command, run_id=run_id, command_index=1, returncode=0, stdout=stdout,
        stdout_log_path=stdout_path, stderr_log_path=stderr_path,
    )
    path = shared.build_quality_gate_receipt_rel_path(1, command["display"])
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(canonical_content(receipt), encoding="utf-8")
    return receipt, {"path": path, "content": receipt}


def test_schema4_binds_original_source_and_receipt_content(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "QUALITY_GATE_SOURCE_FILES", ["source.py"])
    original = b"source\x00\xff\n"
    (tmp_path / "source.py").write_bytes(original)
    sources = shared.build_quality_gate_source_proof(tmp_path)
    assert sources == [{"path": "source.py", "exists": True, "content_base64": base64.b64encode(original).decode("ascii")}]
    assert shared._verify_manifest_gate_sources(tmp_path, {"gate_sources": sources}) is None
    assert shared._verify_manifest_gate_sources(tmp_path, {"gate_sources": [{**sources[0], "exists": 1}]}).endswith("gate sources mismatch")

    command = _command()
    receipt, entry = _receipt_files(tmp_path, command)
    manifest = shared.apply_quality_gate_manifest_proof_fields(
        {"commands": [command], "command_receipts": [entry], "gate_sources": sources}, repo_root=tmp_path,
    )
    assert manifest["schema_version"] == 4
    assert shared._load_verified_quality_gate_receipt(tmp_path, entry, command, index=1) == (receipt, None)
    assert "evidence/QualityGate/v4/receipts/01_" in entry["path"]

    changed = {**receipt, "returncode": False}
    (tmp_path / entry["path"]).write_text(canonical_content(changed), encoding="utf-8")
    assert shared._load_verified_quality_gate_receipt(tmp_path, entry, command, index=1)[1].endswith("content mismatch")
    (tmp_path / "source.py").write_bytes(b"other\x00\xff\n")
    assert shared._verify_manifest_gate_sources(tmp_path, manifest).endswith("gate sources mismatch")


def test_receipt_output_policy_sanitizes_and_checks_actual_logs(tmp_path, monkeypatch):
    secret = "private-runtime-value-for-contract"
    monkeypatch.setenv("SECRET_KEY", secret)
    command = _command("normalized")
    stdout = "1 passed in 1.20s\r\n" + secret + "\r\n"
    receipt, entry = _receipt_files(tmp_path, command, stdout)
    assert receipt["stdout_content"] == "1 passed in <seconds>s\n[REDACTED]\n"
    assert secret not in canonical_content(entry)
    assert secret not in (tmp_path / receipt["stdout_log_path"]).read_text(encoding="utf-8")
    with pytest.raises(shared.QualityGateError) as error:
        shared.normalize_quality_gate_command({**command, "env_overlay": {"SECRET_KEY": secret}})
    assert "SECRET_KEY" in str(error.value) and secret not in str(error.value)

    result = {1: {"returncode": 0, "stdout": "1 passed in 7.90s\n" + secret + "\n", "stderr": ""}}
    assert shared.replay_quality_gate_command_plan(
        tmp_path, [command], receipt_entries=[entry], run_id="run-content", reusable_results=result,
    ) is None
    (tmp_path / receipt["stdout_log_path"]).write_text("different result\n", encoding="utf-8")
    assert "stdout log mismatch" in shared.replay_quality_gate_command_plan(
        tmp_path, [command], receipt_entries=[entry], run_id="run-content", reusable_results=result,
    )


def test_legacy_hash_only_evidence_is_readable_without_new_verification(tmp_path, monkeypatch):
    identity = {"checkout_root_realpath": str(tmp_path), "git_common_dir_realpath": str(tmp_path / ".git")}
    monkeypatch.setattr(shared, "repo_identity", lambda _root: identity)
    monkeypatch.setattr(shared, "collect_current_pytest_nodeids", lambda _root: pytest.fail("legacy proof must not collect"))
    command = _command()
    legacy_directory = tmp_path / shared.QUALITY_GATE_LEGACY_ROOT_REL / "receipts"
    legacy_directory.mkdir(parents=True)
    for version in (2, 3):
        legacy = {"schema_version": version, "stdout_sha256": "saved-stdout-proof", "stderr_sha256": "saved-stderr-proof"}
        path = shared.QUALITY_GATE_LEGACY_ROOT_REL.replace("\\", "/") + f"/receipts/original-v{version}.json"
        (tmp_path / path).write_text(json.dumps(legacy), encoding="utf-8")
        payload, error = shared._load_verified_quality_gate_receipt(
            tmp_path, {"path": path, "sha256": "saved-receipt-proof"}, command, index=1,
        )
        assert payload == legacy and "legacy" in error and "content unavailable" in error
        normalized = shared._normalize_command_receipt_payload(legacy)
        assert normalized["stdout_sha256"] == legacy["stdout_sha256"] and "stdout_content" not in normalized
        bound, note = shared.verify_quality_gate_manifest(
            repo_root=tmp_path, manifest={**identity, "schema_version": version, "status": "passed", "run_id": "old-run"},
            head_sha="saved-head", git_status_lines=[],
        )
        assert bound is False and "legacy" in note
    with pytest.raises(shared.QualityGateError, match="source content is unavailable"):
        shared.apply_quality_gate_manifest_proof_fields(
            {"gate_sources": [{"path": "source.py", "exists": True, "sha256": "saved-source-proof"}]}, repo_root=tmp_path,
        )


def test_replay_checks_run_index_path_and_preserves_execution_failures(tmp_path):
    command = _command()
    receipt, entry = _receipt_files(tmp_path, command)
    assert shared.replay_quality_gate_command_plan(
        tmp_path, [command], receipt_entries=[entry], run_id="run-content",
    ) is None
    assert "run_id mismatch" in shared.replay_quality_gate_command_plan(
        tmp_path, [command], receipt_entries=[entry], run_id="another-run",
    )
    assert "command_index mismatch" in shared._verify_receipt_header(receipt, index=2, run_id="run-content")
    assert "path mismatch" in shared._load_verified_quality_gate_receipt(
        tmp_path, {**entry, "path": entry["path"].replace("01_", "02_")}, command, index=1,
    )[1]
    failure = {1: {"returncode": 7, "stdout": "", "stderr": "command failed"}}
    assert "command replay failed" in shared.replay_quality_gate_command_plan(
        tmp_path, [command], receipt_entries=[entry], run_id="run-content", reusable_results=failure,
    )
    assert "incomplete execution" in shared._verify_receipt_execution_fields({**receipt, "interrupted": True})
    raw_receipt, raw_entry = _receipt_files(tmp_path, command, "real output\r\n")
    assert shared.read_text_file(str(tmp_path / raw_receipt["stdout_log_path"])) == "real output\r\n"
    raw_result = {1: {"returncode": 0, "stdout": "real output\r\n", "stderr": ""}}
    assert shared.replay_quality_gate_command_plan(
        tmp_path, [command], receipt_entries=[raw_entry], run_id="run-content", reusable_results=raw_result,
    ) is None
    assert "stdout replay mismatch" in shared.replay_quality_gate_command_plan(
        tmp_path, [command], receipt_entries=[raw_entry], run_id="run-content",
        reusable_results={1: {"returncode": 0, "stdout": "real output\n", "stderr": ""}},
    )


FRESH_NODEID = "tests/new/test_fresh.py::test_fresh"
RETIRED_NODEID = "tests/old/test_retired.py::test_retired"


def _write_debt_payload(path, nodeid, duration):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "collected_nodeids": [nodeid],
        "reports": [{"nodeid": nodeid, "when": "call", "outcome": "passed", "duration": duration}],
        "summary": {"collected_count": 1},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def analysis_repo(tmp_path, monkeypatch):
    """以 tmp_path 作仓库根：v4 current 是新数据，旧根 current 是迁移前的历史数据；cwd 是空目录。"""
    current = _write_debt_payload(tmp_path / shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL, FRESH_NODEID, 1.0)
    legacy = _write_debt_payload(
        tmp_path / shared.QUALITY_GATE_LEGACY_ROOT_REL / "current_full_test_debt.json", RETIRED_NODEID, 9.0
    )
    (tmp_path / "cwd").mkdir()
    monkeypatch.setattr(report_tool, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(shard_tool, "REPO_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path / "cwd")
    return current, legacy


def test_duration_report_defaults_to_shared_current_and_keeps_explicit_history(analysis_repo, capsys):
    current, legacy = analysis_repo
    assert report_tool.main([]) == 0
    output = capsys.readouterr().out
    assert FRESH_NODEID in output and "tests/old/" not in output

    assert report_tool.main([str(legacy)]) == 0
    assert RETIRED_NODEID in capsys.readouterr().out

    current.unlink()
    with pytest.raises(FileNotFoundError):
        report_tool.main([])


def test_shard_estimate_defaults_to_shared_current_and_keeps_explicit_history(analysis_repo, capsys):
    current, legacy = analysis_repo
    assert shard_tool.main(["--counts", "2"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["total_count"] == 1
    assert result["distributions"][0]["estimated_report_s"] == 1.0
    assert result["source_payload"] == shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL

    assert shard_tool.main(["--counts", "2", "--payload", str(legacy)]) == 0
    assert json.loads(capsys.readouterr().out)["distributions"][0]["estimated_report_s"] == 9.0

    current.unlink()
    with pytest.raises(FileNotFoundError):
        shard_tool.main(["--counts", "2"])


def test_direct_script_entries_bootstrap_outside_repo_root(analysis_repo, tmp_path):
    current, _legacy = analysis_repo
    tools_dir = Path(report_tool.__file__).resolve().parent
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    commands = {
        FRESH_NODEID: [sys.executable, str(tools_dir / "report_full_test_debt_durations.py"), str(current)],
        '"estimated_report_s": 1.0': [
            sys.executable, str(tools_dir / "benchmark_full_test_debt_shards.py"),
            "--payload", str(current), "--counts", "2",
        ],
    }
    for expected, command in commands.items():
        completed = subprocess.run(command, cwd=str(tmp_path), env=env, capture_output=True, text=True, check=False)
        assert completed.returncode == 0, completed.stderr
        assert expected in completed.stdout
