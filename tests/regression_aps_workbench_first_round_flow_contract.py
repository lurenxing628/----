from __future__ import annotations

import html
import importlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from core.infrastructure.database import ensure_schema, get_connection
from tests._support.paths import REPO_ROOT

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
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(Path(tmpdir) / "templates_excel"))
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
    tmpdir = tempfile.mkdtemp(prefix="aps_workbench_first_round_")
    db_path = _prepare_env(tmpdir, monkeypatch)
    ensure_schema(db_path, logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    version = _insert_first_round_data(db_path)
    app = _load_app(monkeypatch)
    client = app.test_client()
    try:
        client.set_cookie("aps_ui_mode", "v1", domain="localhost")
    except TypeError:
        client.set_cookie("localhost", "aps_ui_mode", "v1")
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert f"v{version}" in body
    parser = _LinkCollector()
    parser.feed(body)
    return client, parser


def _visible_text(body: str) -> str:
    parser = _LinkCollector()
    parser.feed(body)
    return "\n".join(parser.visible_parts)


def _href_for_label(parser: _LinkCollector, label: str) -> str:
    for item in parser.links:
        if label in item["text"] and "version=12" in item["href"]:
            return item["href"]
    raise AssertionError(f"未找到带版本上下文的首页入口：{label}，links={parser.links!r}")


def _query(href: str) -> Dict[str, List[str]]:
    return parse_qs(urlparse(href).query)


def test_first_round_workbench_flow_preserves_context_from_homepage_links(monkeypatch) -> None:
    client, parser = _collector_for_home(monkeypatch)
    visible_text = "\n".join(parser.visible_parts)

    assert "计划工作台" in visible_text
    assert "首页值班台" in visible_text
    assert "今日待处理" in visible_text
    assert "超期批次需要先看" in visible_text
    assert "方案需要确认" in visible_text
    assert "资源负荷偏高" in visible_text
    assert "现场情况待确认" in visible_text
    assert "待处理项根据当前数据实时生成，暂不保存已处理状态。" in visible_text
    assert "必须补录" not in visible_text
    for token in INTERNAL_VISIBLE_TOKENS:
        assert token not in visible_text

    analysis = _query(_href_for_label(parser, "排产分析"))
    assert analysis["version"] == ["12"]
    assert analysis["plan_role"] == ["adopted"]
    assert analysis["date_from"]
    assert analysis["date_to"]

    gantt = _query(_href_for_label(parser, "设备甘特图"))
    assert gantt["version"] == ["12"]
    assert gantt["plan_role"] == ["adopted"]
    assert gantt["view"] == ["machine"]
    assert gantt["start_date"]
    assert gantt["end_date"]

    dispatch = _query(_href_for_label(parser, "资源派工"))
    assert dispatch["version"] == ["12"]
    assert dispatch["plan_role"] == ["adopted"]
    assert dispatch["date_from"]
    assert dispatch["date_to"]
    assert dispatch["scope_type"] == ["operator"]

    execution = _query(_href_for_label(parser, "计划和现场实际"))
    assert execution["version"] == ["12"]
    assert execution["plan_role"] == ["adopted"]
    assert execution["date_from"]
    assert execution["date_to"]

    overdue = _query(_href_for_label(parser, "查看超期清单"))
    assert overdue["version"] == ["12"]
    assert overdue["plan_role"] == ["adopted"]
    assert overdue["date_from"]
    assert overdue["date_to"]

    utilization = _query(_href_for_label(parser, "查看资源负荷"))
    assert utilization["version"] == ["12"]
    assert utilization["plan_role"] == ["adopted"]
    assert utilization["start_date"]
    assert utilization["end_date"]

    target_pages = (
        ("排产分析", "排产分析"),
        ("设备甘特图", "甘特图"),
        ("资源派工", "资源排班"),
        ("查看超期清单", "超期"),
        ("查看资源负荷", "资源负荷"),
        ("计划和现场实际", "计划和现场实际"),
    )
    for label, expected_text in target_pages:
        href = _href_for_label(parser, label)
        resp = client.get(href)
        assert resp.status_code == 200, f"{label} -> {href} 返回 {resp.status_code}"
        target_visible_text = _visible_text(resp.get_data(as_text=True))
        assert "计划工作台" in target_visible_text
        assert "首页值班台" in target_visible_text
        assert expected_text in target_visible_text
        for token in INTERNAL_VISIBLE_TOKENS:
            assert token not in target_visible_text
