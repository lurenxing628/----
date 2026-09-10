"""Capture real temporary SQLite DTOs for clearly labelled mock UI tests."""

import base64
import json
import sys
import tempfile
from pathlib import Path

from tests.workbench.report_api_support import report_api


def capture():
    with tempfile.TemporaryDirectory(prefix="report-ui-sqlite-") as temporary:
        api = report_api.__wrapped__(Path(temporary))
        before = api.state()
        topics, details, downloads, catalogs = {}, {}, {}, {}
        token = None
        for topic in ("delivery", "records", "machines", "people", "quality"):
            result = api.read(topic=topic, size=50, **({"snapshot_ref": token} if token else {}))
            token = result["meta"]["snapshot_ref"]
            topics[topic] = result
            for format_name in ("csv", "xlsx"):
                response = api.get("/export", topic=topic, size=50, snapshot_ref=result["meta"]["snapshot_ref"], format=format_name)
                assert response.status_code == 200
                downloads[topic + "." + format_name] = base64.b64encode(response.data).decode("ascii")
        token = topics["delivery"]["meta"]["snapshot_ref"]
        for row in topics["delivery"]["data"]["rows"]:
            details[row["operation_ref"]] = api.read("/operations/" + row["operation_ref"], snapshot_ref=token)["data"]["detail"]
        for kind in ("overdue", "utilization", "downtime", "official-review"):
            response = api.client.get("/api/workbench/v1/reports/" + kind)
            assert response.status_code == 200
            catalogs[kind] = response.get_json()
        filters = {"search": api.read(size=50, query="OP-02"),
                   "finish_late": api.read(size=50, resource_type="machine", focus="finish_late")}
        assert api.state() == before, "Capturing browser fixtures must not change the temporary database"
        writes = [sql for sql in api.statements if sql.lstrip().split()[0].upper() in
                  ("UPDATE", "INSERT", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER")]
        assert not writes, writes
        return {"scope": "captured-real-sqlite-dto-used-by-mock-ui", "topics": topics, "details": details,
                "downloads": downloads, "catalogs": catalogs, "filters": filters,
                "evidence": {"temporary_sqlite": True, "database_unchanged": True, "write_statements": writes}}


if __name__ == "__main__":
    json.dump(capture(), sys.stdout, ensure_ascii=False)
