"""Check native Win7 downloads against their hash and captured public readings."""
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tests.workbench.final_execution_artifacts import _actual, _field, _readings


def main():
    root = Path(sys.argv[1]).resolve()
    report = json.loads((root / "final-field-initial.json").read_text(encoding="utf-8"))
    ledger = json.loads((root / "guest-downloads.json").read_text(encoding="utf-8"))
    endpoints = {"template": "/execution/files/template", "saved-records": "/execution/files/export",
                 "actual-visible-scope": "/actual-gantt/export"}
    checked = []
    for download in report["downloads"]:
        source = Path(download["path"]).resolve()
        assert root in source.parents
        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        assert digest == download["sha256"] and len(content) == download["bytes"]
        native = [row for row in ledger if row["sha256"] == digest and row["bytes"] == len(content)]
        assert len(native) == 1 and Path(native[0]["target"]).resolve() == source
        name, query = download["name"], {}
        if name in endpoints:
            requests = [row for row in report["requests"] if row["method"] == "GET"
                        and urlsplit(row["url"]).path.endswith(endpoints[name])]
            assert len(requests) == 1
            query = parse_qs(urlsplit(requests[0]["url"]).query)
        source_reading = None
        if name == "saved-records":
            current = _readings(report, query["snapshot_ref"][0], "tasks")[-1]
            if len(current["data"]["tasks"]) < current["data"]["page"]["total"]:
                prior_path = Path(report["prior_completed"]["report"])
                prior = json.loads(prior_path.read_text(encoding="utf-8"))
                complete = [row["payload"] for row in prior["responses"] if row["status"] == 200
                            and len(row["payload"].get("data", {}).get("tasks", [])) == 33]
                source_reading = complete[-1]
                original = {task["task_ref"]: task for task in source_reading["data"]["tasks"]}
                for task in current["data"]["tasks"]:
                    assert original[task["task_ref"]] == task
                assert source_reading["data"]["summary"] == current["data"]["summary"]
        proof = (_actual(content, query, report) if name == "actual-visible-scope"
                 else _field(content, name, query, report, source_reading=source_reading))
        if source_reading:
            proof["complete_public_reading"] = str(prior_path)
            proof["current_page_and_summary_match_complete_reading"] = True
        checked.append({"name": name, "sha256": digest, "native_download_guid": native[0]["guid"], **proof})
    assert len(checked) == 4
    (root / "download-content-verification.json").write_text(
        json.dumps({"passed": True, "downloads": checked}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "checked_downloads": len(checked)}))


if __name__ == "__main__":
    main()
