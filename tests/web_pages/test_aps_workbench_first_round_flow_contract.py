"""回归测试：首版排产（v12）后首页值班台工作台流程的上下文透传——首页展示今日待处理/超期/方案确认/资源负荷等卡片，分析/甘特/派工/复盘/超期/资源负荷各入口链接逐项带上版本与 adopted 方案身份及日期范围，点进目标页能正常打开且保留计划工作台与首页值班台导航，全程不向用户外显 plan_role/scenario_id/op_id 等内部术语。"""

from __future__ import annotations

import html
import importlib
import json
import os
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from core.infrastructure.database import ensure_schema, get_connection
from tests._support.excel_templates import point_env_at_shared
from tests._support.gantt_retirement import _business_state
from tests._support.paths import REPO_ROOT
from tests._support.workbench_browser_contract import browser_contract
from tests._support.workbench_web_contract import canonical_boot, retired_response

SCHEMA_PATH = REPO_ROOT / "schema.sql"

INTERNAL_VISIBLE_TOKENS = (
    "plan_role",
    "scenario_id",
    "source_table",
    "candidate_id",
    "op_id",
    "schedule_id",
)


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_href = ""
        self._current_text: List[str] = []
        self.links: List[Dict[str, str]] = []
        self.visible_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        self._current_href = str(attrs_dict.get("href") or "")
        self._current_text = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if not text:
            return
        self.visible_parts.append(text)
        if self._current_href:
            self._current_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._current_href:
            return
        self.links.append({"href": html.unescape(self._current_href), "text": " ".join(self._current_text)})
        self._current_href = ""
        self._current_text = []


def _prepare_env(tmpdir: str, monkeypatch) -> str:
    db_path = str(Path(tmpdir) / "aps_test.db")
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", db_path)
    monkeypatch.setenv("APS_LOG_DIR", str(Path(tmpdir) / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(Path(tmpdir) / "backups"))
    point_env_at_shared(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "aps-workbench-first-round")
    Path(os.environ["APS_LOG_DIR"]).mkdir(exist_ok=True)
    Path(os.environ["APS_BACKUP_DIR"]).mkdir(exist_ok=True)
    Path(os.environ["APS_EXCEL_TEMPLATE_DIR"]).mkdir(exist_ok=True)
    return db_path


def _load_app(monkeypatch):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            monkeypatch.delitem(sys.modules, name, raising=False)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _insert_first_round_data(db_path: str) -> int:
    now = datetime.now().replace(microsecond=0)
    start = now - timedelta(hours=1)
    end = now + timedelta(hours=2)
    summary = {
        "overdue_batches": {"count": 2, "items": [{"batch_id": "B-WORK"}]},
        "algo": {
            "metrics": {"machine_util_avg": 0.88},
            "candidate_comparison": {
                "planned_candidate_count": 3,
                "completed_candidate_count": 2,
                "adopted_candidate_key": "graph_w1_of_3",
                "candidates": [{"candidate_key": "graph_w1_of_3"}],
            },
        },
    }
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Parts (part_no, part_name) VALUES (?, ?)", ("P-WORK", "工作台零件"))
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("B-WORK", "P-WORK", "工作台零件", 1, (now + timedelta(days=1)).strftime("%Y-%m-%d"), "normal", "scheduled"),
        )
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("B-PENDING", "P-WORK", "工作台零件", 1, (now + timedelta(days=2)).strftime("%Y-%m-%d"), "normal", "pending"),
        )
        cur = conn.execute(
            """
            INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name, source, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("OP-WORK", "B-WORK", 1, "加工", "internal", "pending"),
        )
        op_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (op_id, None, None, start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"), "unlocked", 12),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (12, "priority_first", 1, 1, "success", json.dumps(summary, ensure_ascii=False), "pytest"),
        )
        conn.commit()
    finally:
        conn.close()
    return 12


def _collector_for_home(monkeypatch):
    """Finish fixture configuration before measuring the real read-only flow."""
    from core.services.system.system_config_service import SystemConfigService

    tmpdir = tempfile.mkdtemp(prefix="aps_workbench_first_round_")
    db_path = _prepare_env(tmpdir, monkeypatch)
    ensure_schema(db_path, logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    version = _insert_first_round_data(db_path)
    app = _load_app(monkeypatch)
    # The process-wide maintenance throttle may skip the initial legacy GET.
    # Complete this fixture's configuration explicitly, before taking the baseline.
    with closing(get_connection(db_path)) as conn:
        SystemConfigService(conn).ensure_defaults(backup_keep_days_default=app.config["BACKUP_KEEP_DAYS"])
    client = app.test_client()
    canonical_boot(client, "/", "dashboard", {})
    before = _business_state(client)
    response = client.get("/api/workbench/v1/dashboard")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True and payload["meta"]["source"] == "production"
    assert payload["data"]["plan"]["version"] == version
    return client, payload["data"], before


def test_first_round_workbench_flow_preserves_context_from_homepage_links(monkeypatch) -> None:
    client, data, before = _collector_for_home(monkeypatch)
    plan = data["plan"]
    assert plan["version"] == 12 and plan["kind"] == "official" and plan["is_current_official"]
    assert set(data["categories"]) == {"delivery", "actual", "downtime", "material", "candidate", "external"}
    assert data["categories"]["delivery"]["known_risk_count"] == 0
    assert data["items"]
    for item in data["items"]:
        for link in item["navigation"]:
            if "plan_ref" in link["context"]:
                assert link["context"]["plan_ref"] == plan["plan_ref"]
            assert link["enabled"] is True or link["reason"]
    text = browser_contract("""
for(let i=0;i<150 && !document.querySelector('[data-dashboard-workspace][data-ready=true]');i++) await new Promise(resolve=>setTimeout(resolve,20));
const workspace = document.querySelector('[data-dashboard-workspace][data-ready=true]'); expect(workspace);
const caption = document.querySelector('.wb-current-plan');
expect(caption && caption.dataset.planRef === data.reference && caption.textContent.includes('正式 v12'));
return document.body.innerText;
""", app=client.application, data={"reference": plan["plan_ref"]})
    assert "计划员值班台" in text and "值班台" in text
    assert "必须补录" not in text
    for token in INTERNAL_VISIBLE_TOKENS:
        assert token not in text

    day = datetime.now().strftime("%Y-%m-%d")
    dates = "date_from=" + day + "&date_to=" + day
    identity = "version=12&plan_role=adopted"
    # Old date/resource meanings cannot be silently changed into new report cohorts.
    for path in (
        "/scheduler/analysis?" + identity + "&" + dates,
        "/scheduler/gantt?" + identity + "&view=machine&start_date=" + day + "&end_date=" + day,
        "/scheduler/resource-dispatch?" + identity + "&" + dates + "&scope_type=operator",
        "/reports/overdue?" + identity,
        "/reports/utilization?" + identity + "&start_date=" + day + "&end_date=" + day,
        "/reports/execution-review?" + identity + "&" + dates,
    ):
        response = client.get(path)
        if path.startswith("/scheduler/resource-dispatch?"):
            assert response.status_code == 400
            assert "未改选对象或扩大范围" in response.get_data(as_text=True)
            assert "Location" not in response.headers
            continue
        body = retired_response(response)
        assert "<dt>排产版本</dt><dd>12</dd>" in body
        assert "正式采用方案" in body
        if path.startswith("/reports/"):
            assert "按原条件下载旧报表" in body and "version=12" in body
    for path, view in (("/scheduler/analysis?", "analysis"), ("/scheduler/gantt?", "gantt")):
        canonical_boot(client, path + identity, view, {"plan_ref": plan["plan_ref"]})
    for path in ("/scheduler/analysis?version=0", "/scheduler/gantt?version=12&start_date=bad&end_date=" + day):
        response = client.get(path)
        assert response.status_code == 400 and "Location" not in response.headers

    conn = get_connection(client.application.config["DATABASE_PATH"])
    try:
        summary = json.loads(conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=12").fetchone()[0])
        assert summary["overdue_batches"]["count"] == 2
        assert summary["algo"]["metrics"]["machine_util_avg"] == 0.88
        assert summary["algo"]["candidate_comparison"]["planned_candidate_count"] == 3
        assert summary["algo"]["candidate_comparison"]["completed_candidate_count"] == 2
    finally:
        conn.close()
    assert _business_state(client) == before


def test_first_round_fixture_initializes_system_config_even_when_maintenance_is_throttled(monkeypatch) -> None:
    from core.services.system.maintenance.throttle import MaintenanceThrottle

    # Another app in this process may have used the shared maintenance window.
    monkeypatch.setattr(MaintenanceThrottle, "allow_run", classmethod(lambda cls, seconds: False))
    client, _data, before = _collector_for_home(monkeypatch)
    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        defaults = dict(conn.execute("SELECT config_key, config_value FROM SystemConfig"))
    assert defaults == {
        "auto_backup_enabled": "no",
        "auto_backup_interval_minutes": "60",
        "auto_backup_cleanup_enabled": "no",
        "auto_backup_keep_days": str(client.application.config["BACKUP_KEEP_DAYS"]),
        "auto_backup_cleanup_interval_minutes": "1440",
        "auto_log_cleanup_enabled": "no",
        "auto_log_cleanup_keep_days": "30",
        "auto_log_cleanup_interval_minutes": "60",
    }

    # Once the window expires, this existing legacy GET still runs maintenance.
    monkeypatch.setattr(MaintenanceThrottle, "allow_run", classmethod(lambda cls, seconds: True))
    response = client.get("/scheduler/analysis?version=12&plan_role=adopted")
    assert response.status_code == 302
    assert _business_state(client) == before
