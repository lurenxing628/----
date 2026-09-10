"""BC independent source compilation and live HTTP browser evidence, not main build."""

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live_environment import create_root, environment
from test_live_browser import runtime_tools


def verify_exports(evidence):
    for export in evidence["downloads"]:
        path = Path(export["file"])
        if export["format"] == "csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
        else:
            workbook = openpyxl.load_workbook(str(path), read_only=True)
            rows = list(workbook["范围全部结果"].values)
            workbook.close()
        assert len(rows) == export["total"] + 1, path
        if "records15" in path.name:
            records = [dict(zip(rows[0], row)) for row in rows[1:]]
            assert sum(row["记录来源"] == "现场事件" for row in records) == 2
            assert sum(row["记录来源"] == "逐次报工" for row in records) == 13
            revised = next(row for row in records if row["备注"] == "BC corrected quantity and hours")
            history = json.loads(revised["完整修订历史"])
            assert [row["action"] for row in history] == ["create", "supplement", "correct"]
            assert history[0]["after"]["completed_quantity"] is None
            assert history[1]["after"]["completed_quantity"] == 0
            assert history[2]["before"]["completed_quantity"] == 0
            assert history[2]["after"]["completed_quantity"] == 2
            assert sum(str(row["本次完成数量"]) == "0" for row in records) == 3
            unknown = next(row for row in records if "OP-03" in row["工序"])
            assert unknown["本次完成数量"] == "未知" and unknown["有效加工工时(h)"] == "未知"


def test_report_ledger_widgets_live():
    node, browser, modules = runtime_tools()
    root = create_root()
    env = environment(root)
    env.update(NODE_PATH=modules, WORKBENCH_BROWSER=browser)
    print("BC_REPORT_LEDGER_ARTIFACTS " + str(root), flush=True)
    with (root / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, "-B", str(HERE / "report_ledger_widgets_server.py"), str(root)],
            cwd=str(root), env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 90
            while not (root / "ready.json").exists():
                assert server.poll() is None, (root / "server.log").read_text(encoding="utf-8")[-10000:]
                assert time.monotonic() < deadline, "Temporary Flask startup timed out: " + str(root)
                time.sleep(.1)
            result = subprocess.run([node, str(HERE / "test_report_ledger_widgets.cjs"), str(root)],
                cwd=str(root), env=env, capture_output=True, text=True, timeout=360)
            assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(root)
        finally:
            server.terminate()
            server.wait(timeout=30)
    final = json.loads((root / "final.json").read_text(encoding="utf-8"))
    assert final["database_unchanged"] and final["stopped"] and final["violations"] == []
    for path in final["sqlite_connections"]:
        if path != ":memory:":
            Path(path).relative_to(root)
    evidence = json.loads((root / "result.json").read_text(encoding="utf-8"))
    assert evidence["global_build"] is False
    assert len(evidence["cases"]) == 4 and evidence["errors"] == [] and evidence["external"] == []
    verify_exports(evidence)
    for source in evidence["sources"]:
        assert hashlib.sha256((HERE.parents[1] / source["path"]).read_bytes()).hexdigest() == source["sha256"], source["path"]
    print("BC_REPORT_LEDGER_VERIFIED " + json.dumps({"cases": len(evidence["cases"]), "screenshots": len(evidence["screenshots"])}), flush=True)


if __name__ == "__main__":
    test_report_ledger_widgets_live()
