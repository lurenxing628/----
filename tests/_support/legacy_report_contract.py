"""Read-only old-page assertions; callers supply the client, DB and exact scope.

No app factory, fixture, collected test or implicit environment lookup is used.
Business tables are compared in full; diagnostic logs are outside this snapshot.
"""

import json
import sqlite3
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

BUSINESS_TABLES = (
    "Schedule", "ScheduleHistory", "ScheduleCandidate", "ScheduleCandidateRows",
    "ScheduleCandidateSelection", "ScheduleAdjustmentDraft", "ScheduleAdjustmentChange",
    "ScheduleAdjustmentScenario", "ScheduleAdjustmentScenarioRow", "OperationExecutionEvents",
    "WorkbenchPlanSourceRefs", "WorkbenchPlanIdentityClock", "Batches", "BatchOperations",
)
INVALID_CONTEXT = "地址里的计划编号、日期或筛选不对，页面没有打开；系统没有替你换记录或放宽范围。请从侧栏重新进入。"
RETIRED_SCOPE = "旧页面的统计范围、日期和设备人员条件，新报表装不下，页面没有打开；系统没有改用新报表的默认范围。请从侧栏进入「报表中心」重新筛选。"
MISSING_ROLE = "要对比的方案没有保存过，页面没有打开；系统没有改成已采用的正式计划。请从侧栏进入「选择排产方案」重新选择。"
IDENTITY_UNAVAILABLE = "这份计划还没有正式编号，或编号已经失效，页面没有打开；系统不会替你补编号，也不会换查别的计划。请从侧栏进入「选择排产方案」重新选择。"
UNSUPPORTED_SCOPE = "新页面装不下这组旧条件，没有跳转，也没有丢掉任何条件。原来的数据和下载都还在，请从侧栏进入对应页面重新筛选。"
ANALYSIS_SCOPE = "旧分析页的日期和设备人员条件只用来跳转，新分析页装不下，页面没有打开；原来的条件没有被改动。请从侧栏进入「选择排产方案」重新筛选。"


class PageContract(HTMLParser):
    """Extract visible words, links and controls without interpreting scripts."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.controls = []
        self.words = []
        self.hidden_depth = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ("script", "style"):
            self.hidden_depth += 1
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        if tag in ("form", "input", "select", "button"):
            self.controls.append((tag, values))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth and data.strip():
            self.words.append(data.strip())

    @property
    def text(self):
        return "\n".join(self.words)


def business_rows(db_path, tables=BUSINESS_TABLES):
    """Capture declared tables from an existing DB without migrations or writes."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        return {table: conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid').fetchall()
                for table in tables}


def get_unchanged(client, path, db_path):
    before = business_rows(db_path)
    response = client.get(path, follow_redirects=False)
    assert business_rows(db_path) == before, path
    return response


def xlsx_text(data):
    """Read all cells from supplied download bytes, including public metadata."""
    from io import BytesIO

    import openpyxl

    workbook = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
    try:
        return "\n".join(str(cell) for sheet in workbook.worksheets
                         for row in sheet.iter_rows(values_only=True) for cell in row if cell is not None)
    finally:
        workbook.close()


def saved_summary_display(db_path, version):
    """Read the original selected history and its retained public viewmodel."""
    from web.viewmodels.scheduler_history_summary import parse_history_summary_state
    from web.viewmodels.scheduler_summary_display import build_summary_display_state

    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        row = conn.execute("SELECT result_status, result_summary FROM ScheduleHistory WHERE version=?", (version,)).fetchone()
    assert row is not None
    parsed = parse_history_summary_state(row[1])
    return row, build_summary_display_state(parsed.get("payload"), result_status=row[0], parse_state=parsed)


def assert_retired(response, *, public=(), downloads=(), message=RETIRED_SCOPE):
    assert response.status_code == 410
    assert "Location" not in response.headers
    assert response.headers["Cache-Control"] == "no-store"
    page = PageContract(response.get_data(as_text=True))
    assert "旧入口已退役" in page.text
    assert message in page.text
    assert "原业务数据、保存的配置和历史记录仍保留" in page.text
    assert not page.controls
    assert page.links == ["/workbench"] + list(downloads)
    for word in public:
        assert str(word) in page.words
    for term in ("candidate_id", "candidate_key", "source_table", "scenario_id", "baseline_best", "critical_best"):
        assert term not in page.text
    return page


def assert_rejected(response, *, status=400, message=INVALID_CONTEXT, forbidden=()):
    assert response.status_code == status
    assert "Location" not in response.headers
    page = PageContract(response.get_data(as_text=True))
    assert message in page.text
    assert not page.controls
    assert not [link for link in page.links if link != "/workbench"]
    for term in forbidden:
        assert term not in response.get_data(as_text=True)
    return page


def assert_typed_navigation(response, view):
    assert response.status_code == 302
    parts = urlsplit(response.headers["Location"])
    assert not parts.netloc and not parts.fragment
    assert parts.path == "/workbench"
    query = parse_qs(parts.query, keep_blank_values=True)
    assert set(query) == {"view", "nav"} and query["view"] == [view]
    assert len(query["nav"]) == 1
    value = json.loads(query["nav"][0])
    assert set(value) == {"version", "view", "context"}
    assert value["version"] == 1 and value["view"] == view
    return value["context"]


def assert_plan_navigation(response, db_path, *, version, role="adopted", scenario=None, view="analysis"):
    """Reverse-resolve the emitted ref, not a newly generated expected ref."""
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

    context = assert_typed_navigation(response, view)
    assert set(context) == {"plan_ref"}
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        locator = WorkbenchPlanIdentityRepository(conn).resolve_plan(context["plan_ref"])
        assert (locator.version, locator.plan_role, locator.scenario_id) == (version, role, scenario)
    return context


def analysis_read_context(app, db_path, raw_version):
    """Keep original history/trend/diagnostic facts independently of retired HTML."""
    from core.services.scheduler.schedule_history_query_service import ScheduleHistoryQueryService
    from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
    from web.routes.domains.scheduler.scheduler_analysis_read import build_analysis_read_context

    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        services = SimpleNamespace(schedule_history_query_service=ScheduleHistoryQueryService(conn),
                                   schedule_plan_query_service=SchedulePlanQueryService(conn))
        with app.app_context():
            return build_analysis_read_context(services, raw_version)


def report_read_context(app, db_path, path):
    """Read retained business viewmodels, not an HTTP page or a template render.

    Inputs are the explicit app, existing DB and old report query. Factory GET
    retirement must be asserted separately; this never mounts or calls a route.
    """
    from flask import g

    from core.services.report import ReportEngine
    from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
    from web.navigation_context import build_report_navigation_links, current_workbench_navigation_context
    from web.routes.reports_execution_review_page import execution_review_page_context
    from web.routes.reports_page_support import (
        downtime_page_context,
        overdue_page_context,
        reports_index_context,
        utilization_page_context,
    )

    builders = {
        "/reports/": reports_index_context, "/reports/overdue": overdue_page_context,
        "/reports/utilization": utilization_page_context, "/reports/downtime": downtime_page_context,
        "/reports/execution-review": execution_review_page_context,
    }
    before = business_rows(db_path)
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        with app.test_request_context(path):
            g.db = conn
            g.services = SimpleNamespace(schedule_plan_query_service=SchedulePlanQueryService(conn))
            g.app_logger = app.logger
            value = builders[urlsplit(path).path](ReportEngine(conn), g.services)
            value["navigation_context"] = current_workbench_navigation_context()
            value["report_navigation_links"] = build_report_navigation_links()
    assert business_rows(db_path) == before
    return value
