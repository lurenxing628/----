"""Old report probes with current SQLite DTOs; Chrome109, no shared build."""

import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.workbench.report_browser_fixture import capture
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent


def run_probe(name, fixture, output=None):
    node, browser, modules = runtime_tools()
    return subprocess.run([node, str(HERE / name)] + ([str(output)] if output else []),
                          input=json.dumps(fixture, ensure_ascii=False), text=True, capture_output=True,
                          env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser), timeout=300)


def test_report_api():
    result = run_probe("report_api_probe.cjs", capture())
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["topics"] == 5 and report["catalogs"] == 4
    assert report["ledger_rejections"] == 7 and report["unknown_hours_preserved"]
    assert report["writes"] == 0


def test_report_widgets(output=None):
    artifacts = Path(output or tempfile.mkdtemp(prefix="aps-report-ui-"))
    artifacts.mkdir(parents=True, exist_ok=True)
    assert ROOT not in artifacts.resolve().parents and artifacts.resolve() != ROOT
    fixture = capture()
    assert fixture["evidence"] == {"temporary_sqlite": True, "database_unchanged": True, "write_statements": []}
    encoded = json.dumps(fixture, ensure_ascii=False)
    (artifacts / "fixture.json").write_text(encoded, encoding="utf-8")
    print("REPORT_UI_ARTIFACTS " + str(artifacts), flush=True)
    result = run_probe("report_widgets_probe.cjs", fixture, artifacts)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(artifacts)
    report = json.loads((artifacts / "report-ui-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["compile_global_build"] is False
    assert report["fixture_sha256"] == hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    assert len(report["cases"]) == 4 and len(report["screenshots"]) == 24
    assert len(report["downloads"]) == 8 and report["errors"] == report["external"] == []
    assert {(row["viewport"]["width"], row["theme"]) for row in report["cases"]} == {
        (1920, "light"), (1920, "dark"), (int(os.environ.get("WORKBENCH_UI_NARROW_WIDTH", "1392")), "light"),
        (int(os.environ.get("WORKBENCH_UI_NARROW_WIDTH", "1392")), "dark")}
    for row in report["sources"]:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    assert hashlib.sha256((HERE / "report_widgets_probe.cjs").read_bytes()).hexdigest() == report["probe_sha256"]
    for filename in report["screenshots"]:
        assert Path(filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    for download in report["downloads"]:
        content = Path(download["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == download["sha256"]
        assert content == base64.b64decode(fixture["downloads"][download["topic"] + "." + download["format"]])
        if download["format"] == "csv":
            rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        else:
            book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            try:
                rows = list(book["范围全部结果"].iter_rows(values_only=True))
            finally:
                book.close()
        assert len(rows) == 24, "Downloads must retain all 23 rows while viewing page 2 of size 10"
    for response in report["responses"]:
        query, payload = response["query"], response["payload"]
        if "/reports/" in response["path"]:
            assert payload == fixture["catalogs"][response["path"].split("/")[-1]]
            continue
        captured = fixture["filters"]["search"] if query.get("query") else (
            fixture["filters"]["finish_late"] if query.get("focus") == "finish_late" else fixture["topics"][query.get("topic", "delivery")])
        assert payload["data"]["summary"] == captured["data"]["summary"]
        assert payload["meta"] == captured["meta"] and payload["data"]["scope"] == captured["data"]["scope"]
        assert payload["data"]["page"]["total"] == len(captured["data"]["rows"])
        assert all(row in captured["data"]["rows"] for row in payload["data"]["rows"])
    print("REPORT_UI_VERIFIED " + json.dumps({"browser": report["browser"], "cases": 4, "screenshots": 24,
          "downloads": 8, "json_responses": len(report["responses"])}), flush=True)


if __name__ == "__main__":
    test_report_api()
    test_report_widgets(sys.argv[1] if len(sys.argv) > 1 else None)
