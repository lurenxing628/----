"""Compare browser downloads with emitted HTTP bytes, API facts and original SQL."""

import csv
import io
import json
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import openpyxl
from live_environment import sha256, write_json


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def url_key(url):
    value = urlsplit(url)
    return value.path, parse_qs(value.query)


def normalized(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return format(value, "g")
    return str(value)


def rows_from_download(download):
    path = Path(download["path"])
    if path.suffix == ".csv":
        rows = list(csv.reader(io.StringIO(path.read_bytes().decode("utf-8-sig"))))
        return {"范围全部结果": rows}, {"数据版本编号": rows[1][-4]}
    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=False)
    try:
        sheets = {sheet.title: list(sheet.iter_rows(values_only=True)) for sheet in workbook}
    finally:
        workbook.close()
    info = sheets.get("范围与计算方式", sheets.get("查询摘要", []))
    return sheets, {row[0]: row[1] for row in info if len(row) == 2}


def verify_snapshot(download, sheets, meta):
    token = parse_qs(urlsplit(download["url"]).query)["snapshot_ref"][0]
    assert download["headers"]["x-workbench-snapshot"] == token
    is_csv = Path(download["path"]).suffix == ".csv"
    # Compare the exact protected CSV representation, never strip arbitrary apostrophes.
    expected = "'" + token if is_csv and token.startswith(("=", "+", "-", "@")) else token
    assert meta["数据版本编号"] == expected, (download["path"], meta["数据版本编号"], expected)
    if is_csv:
        rows = sheets["范围全部结果"]
        assert rows[0][-4] == "数据版本编号"
        assert all(row[-4] == expected for row in rows[1:])


def verify_records(rows, reports, revisions):
    values = [dict(zip(rows[0], row)) for row in rows[1:]]
    production = {row["报工编号"]: row for row in values if row["记录来源"] == "逐次报工"}
    assert set(production) == set(reports)
    assert len(values) - len(production) == 6
    known_hours, unknown = 0, 0
    for ref, source in reports.items():
        row = production[ref]
        history = revisions[ref]
        latest = json.loads(history[-1]["values_json"])
        assert row["报工单号"] == source["report_no"]
        assert row["原报工任务编号"] == source["recorded_against_task_ref"]
        assert row["原报工计划编号"] == source["recorded_against_plan_ref"]
        for label, key in (("本次完成数量", "completed_quantity"), ("有效加工工时（小时）", "effective_processing_hours"),
                           ("实际开工", "actual_start"), ("本次实际结束", "actual_end"), ("备注", "remark")):
            original = latest[key]
            expected = "未知" if original is None else ("'" + original if key == "remark" and original.startswith("=") else original)
            assert normalized(row[label]) == normalized(expected), (ref, key, row[label], expected)
        assert [item["after"] for item in json.loads(row["完整更正记录"])] == [json.loads(item["values_json"]) for item in history]
        hours = latest["effective_processing_hours"]
        if hours is None:
            unknown += 1
        else:
            known_hours += hours
    assert known_hours == 7.5 and unknown == 1
    assert sum(row["备注"] == "'=1+1" for row in production.values()) == 1
    return {"production_rows": len(production), "legacy_rows": 6, "known_hours": known_hours,
            "unknown_production_hours": unknown, "revision_rows": sum(map(len, revisions.values()))}


def verify(root):
    root = Path(root)
    browser = json.loads((root / "ei-browser.json").read_text(encoding="utf-8"))
    before = json.loads((root / "business-before.json").read_text(encoding="utf-8"))
    after = json.loads((root / "business-after.json").read_text(encoding="utf-8"))
    assert before == after
    http = read_jsonl(root / "ei-http.jsonl")
    streams = read_jsonl(root / "ei-streams.jsonl")
    assert all(row["method"] == "GET" and row["status"] == 200 for row in http)
    assert all(row["method"] == "GET" for row in browser["requests"])
    source_queries = {
        "reports": "SELECT * FROM WorkbenchProductionReports ORDER BY report_ref",
        "revisions": "SELECT * FROM WorkbenchProductionReportRevisions ORDER BY report_ref, sequence",
        "operations": "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1",
        "load": "SELECT COUNT(*) AS tasks, SUM((julianday(end_time)-julianday(start_time))*24) AS hours FROM Schedule WHERE version=1",
        "downtime": "SELECT COUNT(*) AS events, SUM((julianday(end_time)-julianday(start_time))*24) AS hours FROM MachineDowntimes WHERE status='active'",
    }
    connection = sqlite3.connect(str(root / "db/aps-live.db"))
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        sql = {key: [dict(row) for row in connection.execute(query)] for key, query in source_queries.items()}
    finally:
        connection.close()
    reports = {row["report_ref"]: row for row in sql["reports"]}
    revisions = {ref: [row for row in sql["revisions"] if row["report_ref"] == ref] for ref in reports}
    operations = {row["ref"] for row in sql["operations"]}
    assert len(operations) == 66 and len(reports) == 27
    assert sql["load"][0]["tasks"] == 66 and abs(sql["load"][0]["hours"] - 132) < .00001
    assert sql["downtime"][0]["events"] == 1 and abs(sql["downtime"][0]["hours"] - .5) < .00001
    for observed in browser["responses"]:
        assert any(url_key(row["url"]) == url_key(observed["url"]) and row.get("payload") == observed["payload"] for row in http)
    evidence = {"source_queries": source_queries, "sql_counts": {key: len(rows) for key, rows in sql.items()},
                "sql_load": sql["load"], "sql_downtime": sql["downtime"], "json_payloads": len(browser["responses"]), "downloads": []}
    for download in browser["downloads"]:
        bytes_value = Path(download["path"]).read_bytes()
        assert sha256(bytes_value) == download["sha256"]
        matches = [row for row in streams if url_key(row["url"]) == url_key(download["url"])]
        assert len(matches) == 1, "Download evidence must bind to one original response, not a refetch"
        wire = matches[0]
        assert wire["sha256"] == download["sha256"] and Path(wire["path"]).read_bytes() == bytes_value
        sheets, meta = rows_from_download(download)
        query = parse_qs(urlsplit(download["url"]).query)
        verify_snapshot(download, sheets, meta)
        count = int(download["headers"]["x-workbench-row-count"])
        result = {"path": download["path"], "wire_sha256": wire["sha256"], "rows": count, "sheets": list(sheets)}
        if "范围全部结果" in sheets:
            rows = sheets["范围全部结果"]
            assert len(rows) == count + 1
            topic = query["topic"][0]
            values = [dict(zip(rows[0], row)) for row in rows[1:]]
            if topic in ("delivery", "quality"):
                assert {row["工序编号"] for row in values} == operations
                assert sum(int(row["逐次报工数"]) for row in values) == 27
                assert sum(int(row["旧现场事件数"]) for row in values) == 6
            elif topic == "records":
                result["source_verified"] = verify_records(rows, reports, revisions)
            else:
                assert count == 2
                assert sum(int(row["逐次报工数"]) for row in values) == 27
                assert sum(int(row["全部记录数"]) for row in values) == 33
                assert sum(float(row["已知加工工时小计（小时）"]) for row in values if row["已知加工工时小计（小时）"] != "未知") == 7.5
        elif "计划和现场实际" in sheets:
            rows = sheets["计划和现场实际"]
            assert len(rows) == 67 and count == 66
            assert Counter(row[-1] for row in rows[1:])["已完工"] == 15
        elif "停机影响" in sheets:
            assert sheets["停机影响"][1][2:] == (.5, 1, 33, 66)
        elif "设备负荷" in sheets:
            # available_occupancy_v1：66 条任务叠放在同一 2 小时里。设备扣掉 0.5 小时登记停机后可用 7.5 小时，
            # 班表内占用 1.5、落在停机里的 0.5 单列为班表外；累计负荷按每条任务班表内小时逐条相加，
            # 重叠负荷 = 累计负荷 - 班表内占用。人员没有停机，可用 8 小时、班表内占用 2 小时。
            assert sheets["设备负荷"][1][2:] == (1.5, 66, 7.5, 20, 99, 97.5, 0.5, "available_occupancy_v1", None)
            assert sheets["人员负荷"][1][2:] == (2, 66, 8, 25, 132, 130, 0, "available_occupancy_v1", None)
        elif "超期清单" in sheets:
            assert sheets["超期清单"][1][1] == "B1" and sheets["超期清单"][1][-1] == 10
        else:
            raise AssertionError("Unexpected export sheets: " + str(list(sheets)))
        evidence["downloads"].append(result)
    assert len(evidence["downloads"]) == 56
    evidence.update(download_count=56, database_unchanged=True, wire_bytes_identical=True,
                    production_reports=27, original_revisions=28, original_events=6)
    write_json(root / "ei-payload-sql-proof.json", evidence)
    return evidence
