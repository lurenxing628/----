"""DU: real Chrome 109 controls, original receipts and own-process lifecycle only."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from core.services.workbench.system_journal import file_fingerprint
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_system_restore_entrypoint_support import KEY, ProcessHost, marker, seed_database

HERE = Path(__file__).resolve().parent
VARIANTS = [(1920, 1080, "light"), (1920, 1080, "dark"), (1392, 924, "light"), (1392, 924, "dark")]


def probe(host, mode, viewport, theme, **extra):
    output = Path(tempfile.mkdtemp(prefix="aps-du-restore-" + mode + "-"))
    node, browser, modules = runtime_tools()
    options = dict(port=host.port, output=str(output), mode=mode, viewport=viewport, theme=theme,
                   database=str(host.path), backups=str(host.backups), journal=str(host.journal_dir), **extra)
    print("DU_RESTORE_UI_ARTIFACTS " + str(output), flush=True)
    result = subprocess.run([node, str(HERE / "du_system_restore_browser.cjs")], cwd=str(HERE.parents[1]),
                            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            input=json.dumps(options), capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    return json.loads((output / "browser-report.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("width,height,theme", VARIANTS)
def test_du_warm_true_restore_controls_original_receipt_and_no_repeat(tmp_path, width, height, theme):
    host = ProcessHost(tmp_path)
    source = seed_database(host)
    source_hash = file_fingerprint(str(source))
    try:
        host.start()
        report = probe(host, "warm", {"width": width, "height": height}, theme, drop=width == 1392 and theme == "dark")
        assert report["operation"]["state"] == "succeeded"
        assert report["operation"]["target_sha256"] == source_hash
        row = host.journal().lookup(report["pending"]["request_key"])
        assert row is not None
        assert row["job_ref"] == report["operation"]["job_ref"]
        assert len(list(host.backups.glob("*before_restore.db"))) == 1
        before = host.hashes()
        host.locked()
        host.stop()
        assert host.hashes() == before and marker(host.path) == "selected"
    finally:
        host.close()


@pytest.mark.parametrize("width,height,theme", VARIANTS)
@pytest.mark.parametrize("corrupt", [False, True])
def test_du_cold_pending_or_corrupt_browser_has_no_database_access(tmp_path, width, height, theme, corrupt):
    host = ProcessHost(tmp_path, "no-database")
    source = seed_database(host)
    row, _ = host.journal().begin(KEY, "restore", {})
    host.journal().record(row, "verifying", target={"filename": source.name, "sha256": file_fingerprint(str(source))})
    if corrupt:
        next(host.journal_dir.glob("*.json")).write_text("{", encoding="utf-8")
    before = host.hashes()
    try:
        host.start()
        probe(host, "cold", {"width": width, "height": height}, theme, reference=KEY, corrupt=corrupt)
        assert host.hashes() == before
        host.locked()
        host.stop()
        assert host.hashes() == before
    finally:
        host.close()


@pytest.mark.parametrize("mode,state,origin", [("verify-failure", "rolled_back", "protection_backup"),
                                              ("rollback-failure", "rollback_failed", "unconfirmed")])
def test_du_warm_real_rollback_and_unknown_remain_readonly(tmp_path, mode, state, origin):
    host = ProcessHost(tmp_path, mode)
    seed_database(host)
    try:
        host.start()
        report = probe(host, "warm", {"width": 1392, "height": 924}, "dark", expected=state)
        assert report["operation"]["database_origin"] == origin
        before = host.hashes()
        host.stop()
        assert host.hashes() == before
    finally:
        host.close()


def test_du_current_built_payload_runs_true_restore_without_source_overlay(tmp_path):
    host = ProcessHost(tmp_path)
    seed_database(host)
    try:
        host.start()
        report = probe(host, "warm", {"width": 1392, "height": 924}, "light", overlay=False)
        assert report["asset_overlay"] is False
        assert report["operation"]["state"] == "succeeded"
        before = host.hashes()
        host.stop()
        assert host.hashes() == before
    finally:
        host.close()
