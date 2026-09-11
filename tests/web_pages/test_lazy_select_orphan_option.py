"""Missing legacy resource values remain unchanged and explicit in current batch reads.

Legacy lazy-select markup is retired. Unknown source values are not normalized
by GET; edits must fail closed instead of clearing or replacing missing resources.
"""

import sqlite3

from tests._support.gantt_retirement import _business_state
from tests._support.workbench_browser_contract import browser_contract
from tests._support.workbench_web_contract import canonical_boot, retired_response


def test_lazy_select_orphan_option(app_client, repo_root) -> None:
    database = app_client.application.config["DATABASE_PATH"]
    # A legacy damaged row cannot be created through the current guarded write API.
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','零件')")
        conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B_TEST','P1',1)")
        conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('MC1','Machine1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP1','Operator1')")
        conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,machine_id,operator_id) "
                     "VALUES ('OP1','B_TEST',1,'OT','INTERNAL','MISSING_MC','MISSING_OP')")
        reference = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='B_TEST' AND active=1").fetchone()[0]
    canonical_boot(app_client, "/", "dashboard", {})
    for source, expected_status in (("INTERNAL", 409), ("internal", 409)):
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE BatchOperations SET source=? WHERE op_code='OP1'", (source,))
        before = _business_state(app_client)
        retired_response(app_client.get("/scheduler/batches/B_TEST?lazy_select=1"))
        canonical_boot(app_client, "/scheduler/batches/B_TEST", "batches", {"entity_ref": reference})
        response = app_client.get("/api/workbench/v1/entities/batch/" + reference)
        assert response.status_code == 200
        entity = response.get_json()["data"]
        operation = entity["operations"][0]
        assert operation["source"] == source and operation["ref"] == operation["operation_ref"]
        assert operation["machine_ref"] is None and operation["operator_ref"] is None
        choices = app_client.get("/api/workbench/v1/entities/batch/choices").get_json()["data"]
        assert [row["business_code"] for row in choices["machines"]] == ["MC1"]
        assert [row["business_code"] for row in choices["operators"]] == ["OP1"]
        messages = " ".join(item["message"] for item in operation["issues"])
        if source == "INTERNAL":
            assert operation["editable"] is False and "工序归属未明确" in messages
            assert entity["write_context"]["capabilities"]["batch.operation_update"] is False
        else:
            assert "设备未补齐或不可用" in messages and "人员未补齐或不在岗" in messages
        location = app_client.get("/scheduler/batches/B_TEST").headers["Location"]
        text = browser_contract("""
for (let i=0;i<150 && !document.querySelector('table[aria-label="批次工序"]');i++) await new Promise(resolve=>setTimeout(resolve,20));
const table = document.querySelector('table[aria-label="批次工序"]'); expect(table);
const row = table.tBodies[0].rows[0], button = Array.from(row.querySelectorAll('button')).find(node=>node.textContent==='补充资料');
expect(row.textContent.includes(data.source === 'INTERNAL' ? '工序归属未明确' : '设备未补齐或不可用'));
expect(!row.textContent.includes('Machine1') && !row.textContent.includes('Operator1'), 'Missing resource silently replaced');
if(data.source === 'INTERNAL') expect(button.disabled);
return row.textContent;
""", app=app_client.application, path=location, data={"source": source})
        assert "未归类" in text if source == "INTERNAL" else "自制" in text
        rejected = app_client.post("/api/workbench/v1/entities/batch/" + reference + "/operation_update", json={
            "request_key": "orphan-resource-" + source, "write_token": entity["write_context"]["write_token"],
            "input": {"operation_ref": operation["ref"], "fields": {"setup_hours": 1}},
        })
        assert rejected.status_code == expected_status, rejected.get_json()
        assert rejected.get_json()["error"]["code"] == ("stale_write" if source == "INTERNAL" else "constraint_conflict")
        assert rejected.get_json()["committed"] is False
        assert _business_state(app_client) == before
        with sqlite3.connect(database) as conn:
            assert conn.execute("SELECT source,machine_id,operator_id,setup_hours FROM BatchOperations WHERE op_code='OP1'").fetchone() == (source, "MISSING_MC", "MISSING_OP", 0)
    assert not (repo_root / "templates/scheduler/batch_detail.html").exists()
