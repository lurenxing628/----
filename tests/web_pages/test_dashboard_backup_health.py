"""备份健康提示契约（fusion-backup-health-hint）：viewmodel 四态 + 首页渲染。

钉死点：max(mtime) 口径（非文件名序）；aps_backup_*.db 双过滤；恰好 7 天不提示
第 8 天提示（> 语义）；仅 listdir 的 FileNotFoundError 归「从未备份」，其余
OSError 穿透（读取失败不得洗成从未备份）；目录不存在时首页访问不创建目录。
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests._support.workbench_web_contract import canonical_boot
from web.viewmodels.dashboard_backup_health import (
    BACKUP_STALE_DAYS,
    build_backup_health_hint,
    read_latest_backup_time,
)

NOW = datetime(2026, 6, 12, 10, 0, 0)


def _skip_without_symlink(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("平台不支持软链接")
    target = tmp_path / "_symlink_target"
    link = tmp_path / "_symlink_probe"
    target.write_bytes(b"x")
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"平台不允许创建软链接：{exc}")


def _skip_without_hardlink(tmp_path: Path) -> None:
    target = tmp_path / "_hardlink_target"
    link = tmp_path / "_hardlink_probe"
    target.write_bytes(b"x")
    try:
        os.link(str(target), str(link))
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"平台不允许创建硬链接：{exc}")


def _seed(directory, name, *, days_ago, base=NOW):
    path = Path(directory) / name
    path.write_bytes(b"x")
    mtime = (base - timedelta(days=days_ago)).timestamp()
    os.utime(path, (mtime, mtime))
    return path


# ---------- read_latest_backup_time（IO 读取层） ----------


def test_read_latest_returns_max_mtime_not_filename_order(tmp_path):
    # 文件名时间戳较新但 mtime 8 天前；文件名较旧但 mtime 今天 → 取 mtime 最大者
    _seed(tmp_path, "aps_backup_20260612_090000.db", days_ago=8)
    _seed(tmp_path, "aps_backup_20260601_090000.db", days_ago=0)
    latest = read_latest_backup_time(str(tmp_path))
    assert latest is not None
    assert latest.date() == NOW.date()


def test_read_latest_filters_prefix_and_db_suffix(tmp_path):
    _seed(tmp_path, "aps_backup_20260604_090000.db", days_ago=8)
    _seed(tmp_path, "aps_backup_fake.txt", days_ago=0)
    _seed(tmp_path, "other_20260612.db", days_ago=0)
    (tmp_path / "aps_backup_dir.db").mkdir()  # 误放的同名目录不算备份
    latest = read_latest_backup_time(str(tmp_path))
    assert latest is not None
    # 今天的 .txt / 非前缀 .db / 同名目录都不算备份，不得把 8 天态洗成健康
    assert (NOW.date() - latest.date()).days == 8


def test_read_latest_missing_dir_returns_none_without_creating(tmp_path):
    missing = tmp_path / "backups_not_exist"
    assert read_latest_backup_time(str(missing)) is None
    assert not missing.exists()  # 只读实证：访问不创建目录


def test_read_latest_empty_dir_returns_none(tmp_path):
    assert read_latest_backup_time(str(tmp_path)) is None


def test_read_latest_not_a_directory_propagates(tmp_path):
    blocker = tmp_path / "backups"
    blocker.write_bytes(b"x")  # 路径被文件挡住=配置错误，不得归「从未备份」
    with pytest.raises(NotADirectoryError):
        read_latest_backup_time(str(blocker))


def test_read_latest_broken_symlink_dir_is_read_error_not_never_backed_up(tmp_path):
    _skip_without_symlink(tmp_path)
    link = tmp_path / "backups"
    os.symlink(str(tmp_path / "missing_target"), str(link))

    with pytest.raises(OSError, match="备份目录不是安全目录"):
        read_latest_backup_time(str(link))


def test_read_latest_symlink_dir_is_read_error_not_followed(tmp_path):
    _skip_without_symlink(tmp_path)
    target_dir = tmp_path / "real_backups"
    target_dir.mkdir()
    _seed(target_dir, "aps_backup_20260612_090000.db", days_ago=0)
    link = tmp_path / "backups"
    os.symlink(str(target_dir), str(link))

    with pytest.raises(OSError, match="备份目录不是安全目录"):
        read_latest_backup_time(str(link))


def test_read_latest_stat_failure_propagates(tmp_path, monkeypatch):
    _seed(tmp_path, "aps_backup_20260612_090000.db", days_ago=0)

    def _boom(path):
        raise PermissionError(f"mock denied: {path}")

    monkeypatch.setattr("web.viewmodels.dashboard_backup_health.os.lstat", _boom)
    with pytest.raises(PermissionError):
        read_latest_backup_time(str(tmp_path))


def test_read_latest_symlink_backup_is_read_error_not_never_backed_up(tmp_path):
    _skip_without_symlink(tmp_path)
    victim = tmp_path / "victim.db"
    victim.write_bytes(b"outside")
    os.symlink(str(victim), str(tmp_path / "aps_backup_20260612_090000.db"))

    with pytest.raises(OSError, match="不是安全的普通文件"):
        read_latest_backup_time(str(tmp_path))


def test_read_latest_hardlink_backup_is_read_error_not_never_backed_up(tmp_path):
    _skip_without_hardlink(tmp_path)
    source = tmp_path / "source.db"
    source.write_bytes(b"db")
    os.link(str(source), str(tmp_path / "aps_backup_20260612_090000.db"))

    with pytest.raises(OSError, match="不是安全的普通文件"):
        read_latest_backup_time(str(tmp_path))


# ---------- build_backup_health_hint（纯决策层） ----------


def test_hint_healthy_returns_none_at_exact_threshold():
    latest = NOW - timedelta(days=BACKUP_STALE_DAYS)
    assert build_backup_health_hint(latest=latest, read_error=None, now=NOW) is None


def test_hint_stale_day_count_and_guide():
    latest = NOW - timedelta(days=8)
    hint = build_backup_health_hint(latest=latest, read_error=None, now=NOW)
    assert hint is not None
    assert hint["title"] == "已 8 天未备份"
    assert hint["tone"] == "warning"
    assert "数据备份" in hint["body"]


def test_hint_calendar_day_diff_not_seconds():
    # 昨天 23:00 备份，今天 10:00 看 → 日历日差 1 天（≤7 健康），非 0 天
    latest = datetime(2026, 6, 11, 23, 0, 0)
    assert build_backup_health_hint(latest=latest, read_error=None, now=NOW) is None


def test_hint_never_backed_up():
    hint = build_backup_health_hint(latest=None, read_error=None, now=NOW)
    assert hint is not None
    assert hint["title"] == "尚未发现任何备份"
    assert hint["tone"] == "warning"


def test_hint_read_error_is_explicit():
    hint = build_backup_health_hint(latest=None, read_error="Permission denied", now=NOW)
    assert hint is not None
    assert hint["title"] == "备份状态读取失败"
    assert "Permission denied" in hint["body"]


# ---------- 首页渲染契约 ----------


def _current_backup_state(client):
    """Retired homepage hints now use explicit, unverified system metadata."""
    canonical_boot(client, "/", "dashboard", {})
    response = client.get("/api/workbench/v1/system/overview")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True and payload["meta"]["source"] == "production"
    state = payload["data"]["backups"]
    assert state["verification_status"] == "not_checked"
    assert "尚未校验备份内容" in state["message"]
    return state


def test_dashboard_shows_stale_hint(app_client):
    # 路由用真实 datetime.now()，播种 mtime 以真实时间为基准
    backup_dir = os.environ["APS_BACKUP_DIR"]
    seeded = _seed(backup_dir, "aps_backup_20260604_090000.db", days_ago=8, base=datetime.now())
    state = _current_backup_state(app_client)
    assert state["state"] == "available" and state["count"] == 1
    latest = datetime.fromisoformat(state["latest"]["modified_at"])
    assert state["latest"]["filename"] == seeded.name
    assert (datetime.now().date() - latest.date()).days == 8
    hint = build_backup_health_hint(latest=latest, read_error=None, now=datetime.now())
    assert "天未备份" in hint["title"]
    assert seeded.read_bytes() == b"x"


def test_dashboard_shows_never_backed_up_hint(app_client):
    # db_env 建了空 backups 目录 → 「尚未备份」态
    state = _current_backup_state(app_client)
    assert state["state"] == "empty" and state["count"] == 0
    assert state["files"] == [] and state["latest"] is None
    assert build_backup_health_hint(latest=None, read_error=None, now=NOW)["title"] == "尚未发现任何备份"


def test_dashboard_healthy_renders_no_hint(app_client):
    backup_dir = os.environ["APS_BACKUP_DIR"]
    _seed(backup_dir, "aps_backup_20260612_090000.db", days_ago=0, base=datetime.now())
    state = _current_backup_state(app_client)
    assert state["state"] == "available" and state["count"] == 1
    latest = datetime.fromisoformat(state["latest"]["modified_at"])
    assert build_backup_health_hint(latest=latest, read_error=None, now=datetime.now()) is None
    assert not state["issues"] and state["error"] is None


def test_dashboard_read_failure_explicit_and_page_alive(app_client, monkeypatch, caplog):
    import logging

    def _boom(*args, **kwargs):
        raise PermissionError("mock denied")

    monkeypatch.setattr("core.services.system.workbench_overview.build_system_overview", _boom)
    canonical_boot(app_client, "/", "dashboard", {})
    with caplog.at_level(logging.ERROR):
        resp = app_client.get("/api/workbench/v1/system/overview")
    assert resp.status_code == 500
    payload = resp.get_json()
    assert payload["ok"] is False and "data" not in payload
    assert payload["error"]["code"] == "system_read_failed"
    assert payload["error"]["request_ref"] and payload["error"]["retryable"] is True
    assert "mock denied" not in resp.get_data(as_text=True)
    assert any("工作台系统概况读取失败" in r.getMessage() for r in caplog.records)
    assert app_client.get("/workbench?view=system").status_code == 200
