"""Actual report date HTTP boundaries and retained print/manual payloads."""

import argparse
import json
import traceback
from pathlib import Path

from factory_runtime import FactoryCase


def report_dates(case):
    ranges = (("slash", "2026/09/09", "2026/09/10", True),
              ("maximum", "2026-08-01", "2026-10-01", True),
              ("missing-end", "2026-01-01", "", False),
              ("invalid", "2026-02-30", "2026-03-01", False),
              ("reversed", "2026-01-02", "2026-01-01", False),
              ("too-long", "2026-01-01", "2026-03-04", False))
    rows = []
    for page in ("utilization", "downtime"):
        for name, first, end, valid in ranges:
            for export in (False, True):
                path = "/reports/" + page + ("/export" if export else "")
                response = case.client.get(path, query_string={"version": "3", "start_date": first, "end_date": end})
                row = case.save_response("report-" + page + "-" + name + ("-export" if export else "-page"), response)
                expected = (410 if case.candidate and not export else 200) if valid else 400
                assert response.status_code == expected, (path, name, expected, response.status_code)
                row.update(path=path, range_case=name, export=export, expected_status=expected)
                rows.append(row)
                response.close()
    if case.candidate:
        for primary, alias in (("date_from", "start_date"), ("date_to", "end_date")):
            response = case.client.get("/reports/utilization", query_string={"version": "3", primary: "2026-09-09", alias: "2026-09-10"})
            assert response.status_code == 400
            assert "冲突的日期别名" in response.get_data(as_text=True)
            rows.append(case.save_response("report-conflict-" + primary, response))
            response.close()
    return rows


def presentation(case):
    for role in ("adopted", "baseline_best"):
        response = case.client.get("/scheduler/week-plan/print", query_string={
            "version": "3", "week_start": "2026-09-07", "group_by": "machine",
            "day": "2026-09-09", "batch_id": "CAT-B", "plan_role": role})
        case.save_response("print-" + role, response)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        for value in ("v3", "CAT-B", "2026-09-09", "window.print()", "备注", "仅含筛选范围"):
            assert value in html, (role, value)
        if role == "baseline_best":
            assert "不得下发执行" in html
        if case.candidate:
            assert "/static/css/" not in html and "/static/js/" not in html
        response.close()
    response = case.client.get("/scheduler/config/manual")
    case.save_response("manual", response)
    assert response.status_code == 200
    if case.candidate:
        html = response.get_data(as_text=True)
        assert "说明书正文" in html and "说明书目录" in html
        assert "config_manual.js" not in html
    response.close()
    response = case.client.get("/scheduler/config/manual/download")
    receipt = case.save_response("manual-download", response)
    assert response.status_code == 200
    assert "attachment" in response.headers.get("Content-Disposition", "")
    assert response.get_data() == (case.source / "static/docs/scheduler_manual.md").read_bytes()
    response.close()
    return {"print_cases": 2, "identity_warning": True, "manual_source_bytes_equal": True,
            "manual_download_sha256": receipt["sha256"], "browser_rendering_verified": False}


def run(case):
    from tests.workbench.plan_read_support import seed_plans

    with case.db() as conn:
        seed_plans(conn)
        conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_code,reason_detail,status) "
                     "VALUES ('PRIVATE-M1','2026-09-09 23:00:00','2026-09-10 01:00:00','maintenance','report fixture','active')")
        conn.commit()
    before = case.business_state()
    rows = report_dates(case)
    retained = presentation(case)
    assert case.business_state() == before
    return {"passed": True, "report_date_requests": rows, "presentation": retained,
            "business_state_unchanged": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    case = FactoryCase(args.source, args.runtime, candidate=args.candidate)
    try:
        result = run(case)
    except Exception as exc:
        result = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
    case.write_result(result)
    print(json.dumps({"passed": result["passed"], "error": result.get("error")}, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
