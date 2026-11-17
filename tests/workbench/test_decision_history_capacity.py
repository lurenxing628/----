"""历史页不再按目录总量拒绝读取；导出按筛选出的条数设上限，超出时整次不开始下载。"""

import pytest

from core.services.workbench.history import queries as history_queries
from tests.workbench.decision_history_support import BASE, api, copy_case, four_source_case, read
from tests.workbench.run_candidate_support import retained

CAPACITY_MESSAGE = "筛选出的历史超过 2 条，没有开始下载。请缩小日期或状态范围后再导出。"


@pytest.fixture(scope="module")
def history_template(tmp_path_factory):
    with four_source_case(tmp_path_factory.mktemp("decision-history-capacity")) as case:
        yield case


@pytest.fixture
def history_case(history_template, tmp_path):
    case = copy_case(history_template, tmp_path)
    with case.app.app_context():
        yield case
    case.conn.close()


def test_page_reads_past_the_export_cap_and_export_counts_only_the_filtered_rows(history_case, monkeypatch):
    monkeypatch.setattr(history_queries, "MAX_HISTORY_EXPORT_ROWS", 2)
    client, _ = api(history_case)
    with retained(history_case.conn):
        page = read(client, timeline="official")
        assert page["data"]["totals"] == {"run": 1, "official": 3, "filtered": 3} and len(page["data"]["entries"]) == 3

        rejected = client.get(BASE + "/export", query_string={
            "timeline": "official", "snapshot_ref": page["meta"]["snapshot_ref"], "format": "csv", "section": "entries"})
        assert rejected.status_code == 413
        error = rejected.get_json()["error"]
        assert (error["code"], error["message"]) == ("history_capacity_exceeded", CAPACITY_MESSAGE)

        # 目录共 4 条，超过上限；只要筛选出的条数在上限内就照常导出。
        narrow = read(client, timeline="run", state="complete")
        assert narrow["data"]["totals"]["filtered"] == 1
        narrowed = client.get(BASE + "/export", query_string={
            "timeline": "run", "state": "complete", "snapshot_ref": narrow["meta"]["snapshot_ref"], "format": "csv",
            "section": "entries"})
        assert narrowed.status_code == 200, narrowed.get_data(as_text=True)
