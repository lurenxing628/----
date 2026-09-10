"""Real transport boundaries are inclusive; accepted batches are not truncated."""

import hashlib
import json

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_process_file import IMPORT_BYTE_LIMIT
from core.services.process.workflow_state import record_confirmation
from core.services.workbench.process_file_codec import decode_process_file
from tests.workbench.process_file_api_support import BASE, file_api_fixture, node_contract
from tests.workbench.process_stage_api_support import rejected, success


@pytest.mark.parametrize("kind", ["route", "hours"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_exactly_two_thousand_rows_previews_and_commits_as_one_receipt(file_api, kind, fmt):
    with file_api.database() as conn:
        if kind == "route":
            conn.executemany("INSERT INTO Parts(part_no,part_name) VALUES (?,?)",
                             [(f"IMPORT-{n:04d}", "Old") for n in range(2000)])
            rows = [{"business_code": f"IMPORT-{n:04d}", "label": "New"} for n in range(2000)]
        else:
            conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('IMPORT-HOURS','Hours')")
            conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) VALUES ('IMPORT-HOURS',?,'PROC-IN','\u8f66\u524a','internal',0,1)",
                             [(n,) for n in range(1, 2001)])
            conn.commit()
            with TransactionManager(conn).transaction(begin_immediate=True):
                record_confirmation(conn, "IMPORT-HOURS", "route")
                record_confirmation(conn, "IMPORT-HOURS", "source")
            rows = [{"business_code": "IMPORT-HOURS", "sequence": n, "unit_hours": 2} for n in range(1, 2001)]
    before = file_api.snapshot()
    preview = file_api.preview_rows(kind, rows, fmt)
    node_contract("preview", preview, kind, fmt=fmt)
    assert preview["data"]["summary"]["update"] == len(preview["data"]["rows"]) == 2000
    assert file_api.snapshot() == before
    body = file_api.file_body(preview)
    receipt = success(file_api.file_post(kind, "confirm", body))
    node_contract("receipt", receipt, kind, body=body, preview=preview)
    assert len(receipt["data"]["rows"]) == 2000
    assert len(file_api.rows("WorkbenchCommandReceipts")) == 1
    if kind == "route":
        assert {row["part_name"] for row in file_api.rows("Parts", "part_no LIKE 'IMPORT-%'")} == {"New"}
    else:
        assert {row["unit_hours"] for row in file_api.rows("PartOperations", "part_no='IMPORT-HOURS'")} == {2}


def test_exact_sixteen_mib_keeps_original_bytes_and_one_more_byte_rejects(file_api):
    header = b"business_code,remark\r\n"
    prefixes = [(f"LIMIT-{n:03d},").encode("ascii") for n in range(200)]
    available = IMPORT_BYTE_LIMIT - len(header) - sum(len(prefix) + 2 for prefix in prefixes)
    width, remainder = divmod(available, len(prefixes))
    content = header + b"".join(prefix + b"x" * (width + (index < remainder)) + b"\r\n"
                                for index, prefix in enumerate(prefixes))
    assert len(content) == IMPORT_BYTE_LIMIT
    before = file_api.snapshot()
    preview = success(file_api.upload("route", content))
    node_contract("preview", preview, "route")
    assert preview["data"]["file_sha256"] == hashlib.sha256(content).hexdigest()
    assert len(preview["data"]["rows"]) == preview["data"]["summary"]["rejected"] == 200
    rejected(file_api.upload("route", content + b"x"), "invalid_input", 413)
    assert file_api.snapshot() == before


@pytest.mark.parametrize("mode", ["include", "exclude"])
def test_actual_column_filter_exports_full_matches_after_node_request_encoding(file_api, mode):
    options = success(file_api.client.get(BASE + "/process-table/facets/business_code"))["data"]["options"]
    codes = {"PROC-001", "PROC-004"}
    keys = [row["key"] for row in options if row["label"] in codes]
    scope = {"sort": [], "column_filters": {"business_code": {"mode": mode, "values": keys}}}
    body, _ = file_api.export_body(scope=scope, selection="filtered", size=1)
    body = node_contract("export-body", None, "route", body=body)
    preview = success(file_api.file_post("route", "export-preview", body))
    node_contract("export", preview, "route", body=body)
    response = file_api.download("route", preview["data"]["export_ref"])
    assert response.status_code == 200, response.get_json()
    exported = {row["values"]["business_code"] for row in decode_process_file("route", response.data, "csv")}
    assert exported == (codes if mode == "include" else {"PROC-002", "PROC-003", "PROC-%_"})
    assert len(exported) > 1
    changed = json.loads(json.dumps(body))
    changed["scope"]["column_filters"]["business_code"]["mode"] = "exclude" if mode == "include" else "include"
    rejected(file_api.file_post("route", "export-preview", changed), "snapshot_stale")
