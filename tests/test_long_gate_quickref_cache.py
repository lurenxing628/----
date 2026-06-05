"""测试：long-gate 缓存中 quickref_vs_routes 条目的指纹与复用判定——该条目启用且声明输出 evidence/QualityGate/quickref_vs_routes.md；指纹随速查表/app.py/路由/viewmodel/模板/静态资源/config/schema/依赖/check 脚本及 APS_DB_PATH 环境边界变化而变；decide_reuse 仅当输出报告文件存在且 hash 匹配才 reuse，文件缺失或内容改动则改判为 run。"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import quality_gate_shared
from tools.long_gate_cache import decide_reuse, write_success
from tools.long_gate_fingerprint import fingerprint_entry
from tools.long_gate_manifest import build_manifest_from_quality_gate_plan


def _entry_by_id(manifest, entry_id):
    for entry in list(manifest["entries"]):
        if entry["entry_id"] == entry_id:
            return entry
    raise AssertionError("missing entry_id: " + str(entry_id))


def _quickref_entry(repo_root: Path):
    manifest = build_manifest_from_quality_gate_plan(
        quality_gate_shared.build_quality_gate_command_plan(),
        repo_root=str(repo_root),
    )
    return _entry_by_id(manifest, "quickref_vs_routes")


def _write(repo_root: Path, rel_path: str, text: str = "MARKER = 1\n") -> Path:
    path = repo_root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_quickref_report(repo_root: Path, text: str = "# quickref\n\nOK\n") -> Path:
    return _write(repo_root, "evidence/QualityGate/quickref_vs_routes.md", text)


def test_quickref_vs_routes_is_enabled_and_declares_output_file(tmp_path):
    entry = _quickref_entry(tmp_path)

    assert entry["cache_status"] == "enabled"
    assert entry["reuse_allowed"] is True
    assert entry["output_result_files"] == ["evidence/QualityGate/quickref_vs_routes.md"]


@pytest.mark.parametrize(
    "changed_path",
    [
        "开发文档/系统速查表.md",
        "app.py",
        "web/routes/example.py",
        "web/bootstrap/factory.py",
        "web/viewmodels/example.py",
        "web/error_handlers.py",
        "web/ui_mode.py",
        "templates/dashboard.html",
        "web_new_test/templates/dashboard.html",
        "static/app.css",
        "web_new_test/static/app.css",
        "config.py",
        "schema.sql",
        "requirements.txt",
        "tests/check_quickref_vs_routes.py",
    ],
)
def test_quickref_fingerprint_tracks_doc_routes_app_resources_config_and_dependencies(tmp_path, changed_path):
    entry = _quickref_entry(tmp_path)

    before = fingerprint_entry(entry, str(tmp_path))
    _write(tmp_path, changed_path)
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]


def test_quickref_fingerprint_tracks_environment_boundary(tmp_path, monkeypatch):
    entry = _quickref_entry(tmp_path)
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "one.db"))

    before = fingerprint_entry(entry, str(tmp_path))
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "two.db"))
    after = fingerprint_entry(entry, str(tmp_path))

    assert after["hash"] != before["hash"]


def test_quickref_reuse_requires_report_file_to_exist_and_match_hash(tmp_path):
    entry = _quickref_entry(tmp_path)
    report = _write_quickref_report(tmp_path, "# quickref\n\nOK\n")
    fingerprint = fingerprint_entry(entry, str(tmp_path))
    write_success(
        entry,
        fingerprint,
        {
            "stdout": "evidence/QualityGate/quickref_vs_routes.md\nOK\n",
            "stderr": "",
            "returncode": 0,
            "duration_s": 1.0,
        },
        [str(report)],
        repo_root=str(tmp_path),
    )

    assert decide_reuse(entry, fingerprint, repo_root=str(tmp_path))["decision"] == "reuse"

    report.unlink()
    missing = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))
    assert missing["decision"] == "run"
    assert missing["reason"] == "previous output files missing or hash mismatch"

    _write_quickref_report(tmp_path, "# quickref\n\nchanged\n")
    changed = decide_reuse(entry, fingerprint, repo_root=str(tmp_path))
    assert changed["decision"] == "run"
    assert changed["reason"] == "previous output files missing or hash mismatch"
