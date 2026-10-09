"""Exercise the real selector with controlled process entry points on the host.

These checks protect folder selection and original data; they are not Win7 VM
acceptance of the launcher, executable or business sample injection.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SELECTOR = REPO / "packaging/win7/Start.ps1"
HARNESS = Path(__file__).with_name("switch_harness.ps1")
POWERSHELL = shutil.which("pwsh.exe") or shutil.which("pwsh")

pytestmark = pytest.mark.skipif(not POWERSHELL, reason="Host PowerShell 7 is unavailable")


@pytest.fixture
def application(tmp_path):
    root = tmp_path / "APS 中文 空格 !" / "Application"
    formal = root / "APS_Portable"
    formal.mkdir(parents=True)
    files = {
        "APS.exe": b"controlled test executable; never run",
        "aps-portable.txt": b"portable\r\n",
        "assets/local.txt": b"offline asset",
        "aps-launcher.ps1": (REPO / "assets/aps-launcher.ps1").read_bytes(),
    }
    for name, content in files.items():
        target = formal / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    data = formal / "user-data/db/aps.db"
    data.parent.mkdir(parents=True)
    data.write_bytes(b"original business data must survive every selector case")
    (formal / "user-data/private-export.xlsx").write_bytes(b"original private export")
    write_manifest(root, files)
    return root, formal, files


def write_manifest(root, files):
    with (root / "files.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["Path", "Bytes"])
        writer.writeheader()
        writer.writerows({"Path": name, "Bytes": len(content)} for name, content in files.items())


def run_case(application, scenario):
    root, formal, _ = application
    before = {str(path.relative_to(formal)): path.read_bytes()
              for path in formal.rglob("*") if path.is_file()}
    completed = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(HARNESS),
         "-Launcher", str(SELECTOR), "-Root", str(root), "-Scenario", scenario],
        capture_output=True, text=True, encoding="utf-8", timeout=45,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    after = {str(path.relative_to(formal)): path.read_bytes()
             for path in formal.rglob("*") if path.is_file()}
    assert after == before, "Switching must never alter the original program or user data"
    return result


def actions(result):
    return [event.split("|", 1)[0] for event in result["events"]]


def test_default_start_uses_original_context_without_creating_sample(application):
    root, formal, _ = application
    result = run_case(application, "default")
    assert result["codes"] == [0]
    assert result["events"] == ["start|" + str(formal)]
    assert result["enabled"] is False
    assert not (root / "sample-context").exists()


def test_enable_reopen_disable_preserves_data_and_reuses_completed_sample(application):
    root, formal, files = application
    result = run_case(application, "enable-reopen-disable")
    sample = root / "sample-context/APS_Portable"
    assert result["codes"] == [0, 0, 0]
    assert actions(result) == ["stop", "start", "inject", "start", "stop", "start"]
    assert result["events"][0] == "stop|" + str(formal)
    assert result["events"][1] == "start|" + str(sample)
    assert result["events"][2] == "inject|" + str(sample) + "|--sample-inject"
    assert result["events"][-2:] == ["stop|" + str(sample), "start|" + str(formal)]
    assert result["enabled"] is False
    assert (sample / "aps-complex-sample.txt").is_file()
    assert json.loads((sample / "user-data/sample-acceptance.json").read_text(encoding="utf-8-sig"))["state"] == "complete"
    assert not (sample / "user-data/db/aps.db").exists()
    assert not (sample / "user-data/private-export.xlsx").exists()
    for name, content in files.items():
        assert (sample / name).read_bytes() == content


def test_enabling_completed_sample_again_does_not_reinject(application):
    result = run_case(application, "enable-twice")
    assert result["codes"] == [0, 0]
    assert actions(result) == ["stop", "start", "inject", "start"]
    assert result["enabled"] is True


def test_disabling_when_already_off_only_reopens_original_context(application):
    root, formal, _ = application
    result = run_case(application, "disable-when-off")
    assert result["codes"] == [0]
    assert result["events"] == ["start|" + str(formal)]
    assert not (root / "sample-context").exists()


def test_enabling_pending_sample_does_not_stop_reinject_or_copy_again(application):
    root, _, _ = application
    result = run_case(application, "pending-on")
    assert result["codes"] == [1]
    assert result["events"] == []
    assert result["enabled"] is True
    assert not (root / "sample-context/APS_Portable/assets/local.txt").exists()


def test_stop_failure_keeps_original_context_selected(application):
    root, _, _ = application
    result = run_case(application, "stop-failed-on")
    assert result["codes"] == [1]
    assert actions(result) == ["stop"]
    assert result["enabled"] is False
    assert not (root / "sample-context").exists()


def test_stop_failure_keeps_sample_selected_without_starting_original(application):
    result = run_case(application, "stop-failed-off")
    assert result["codes"] == [0, 1]
    assert actions(result) == ["stop", "start", "inject", "stop"]
    assert result["enabled"] is True


def test_partial_injection_is_preserved_not_replayed_and_can_be_disabled(application):
    root, formal, _ = application
    result = run_case(application, "inject-failed-restore")
    assert result["codes"] == [1, 1, 1, 0]
    assert actions(result) == ["stop", "start", "inject", "stop", "start"]
    assert result["events"][-1] == "start|" + str(formal)
    assert result["enabled"] is False
    report = root / "sample-context/APS_Portable/user-data/sample-acceptance.json"
    assert json.loads(report.read_text(encoding="utf-8-sig")) == {"state": "failed", "committed": True}


def test_zero_exit_without_completion_report_is_not_accepted(application):
    result = run_case(application, "inject-no-result-restore")
    assert result["codes"] == [1, 0]
    assert result["enabled"] is False


def test_existing_report_without_state_is_not_automatically_reinjected(application):
    result = run_case(application, "invalid-result")
    assert result["codes"] == [1]
    assert result["events"] == []
    assert result["enabled"] is True


def test_original_launcher_failure_prevents_injection(application):
    result = run_case(application, "start-failed")
    assert result["codes"] == [9]
    assert actions(result) == ["stop", "start"]


@pytest.mark.parametrize("relative", ["user-data/db/aps.db", "USER-DATA/private-export.xlsx",
                                      "./user-data/db/aps.db", "../APS_Portable/user-data/db/aps.db"])
def test_program_manifest_cannot_copy_original_user_data(application, relative):
    root, _, files = application
    files[relative] = b"must not be copied"
    write_manifest(root, files)
    result = run_case(application, "invalid-manifest")
    assert result["codes"] == [1]
    assert result["enabled"] is False
    sample = root / "sample-context/APS_Portable"
    assert not (sample / "user-data").exists()
