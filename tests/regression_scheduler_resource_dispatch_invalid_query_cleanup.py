from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_client(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(str(test_db))
    try:
        conn.execute("INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)", ("TEAM-01", "装配一组", "active"))
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
            ("OP001", "张三", "active", "TEAM-01", ""),
        )
        conn.execute(
            "INSERT INTO Machines (machine_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
            ("MC001", "数控车床1", "active", "TEAM-01", ""),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name, route_raw) VALUES (?, ?, ?)", ("PART-001", "回转壳体", "[]"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B001", "PART-001", "回转壳体", 5, "2026-03-08", "urgent", "yes", "scheduled"),
        )
        cur = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("OP-B001-10", "B001", "P1", 10, "车削", "internal", "MC001", "OP001", "scheduled"),
        )
        op_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id, "MC001", "OP001", "2026-03-02 08:00:00", "2026-03-02 12:00:00", "locked", 1),
        )
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "greedy",
                1,
                1,
                "success",
                json.dumps({"overdue_batches": {"count": 1, "items": [{"batch_id": "B001"}]}}, ensure_ascii=False),
                "test",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    return app.test_client()


def _query_dict(location: str):
    parsed = urlparse(location)
    return parse_qs(parsed.query)


def test_resource_dispatch_invalid_date_redirects_to_clean_url(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP001&period_preset=week&query_date=bad&version=1"
    )

    assert resp.status_code == 302
    params = _query_dict(resp.headers["Location"])
    assert params.get("scope_type") == ["operator"]
    assert params.get("operator_id") == ["OP001"]
    assert params.get("version") == ["1"]
    assert "period_preset" not in params
    assert "query_date" not in params


def test_resource_dispatch_invalid_scope_redirects_to_clean_url(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP404&period_preset=week&query_date=2026-03-02&version=1"
    )

    assert resp.status_code == 302
    params = _query_dict(resp.headers["Location"])
    assert params.get("scope_type") == ["operator"]
    assert params.get("period_preset") == ["week"]
    assert params.get("query_date") == ["2026-03-02"]
    assert params.get("version") == ["1"]
    assert "operator_id" not in params
    assert "scope_id" not in params


def test_resource_dispatch_invalid_version_redirects_to_clean_url(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=bad"
    )

    assert resp.status_code == 302
    params = _query_dict(resp.headers["Location"])
    assert params.get("scope_type") == ["operator"]
    assert params.get("operator_id") == ["OP001"]
    assert params.get("period_preset") == ["week"]
    assert params.get("query_date") == ["2026-03-02"]
    assert "version" not in params


def test_resource_dispatch_mixed_invalid_filters_settle_without_500(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP404&period_preset=week&query_date=bad&version=1",
        follow_redirects=True,
    )

    assert resp.status_code == 200
    html = resp.data.decode("utf-8", errors="ignore")
    assert "资源排班中心" in html
    assert "id=\"rdPage\"" in html
