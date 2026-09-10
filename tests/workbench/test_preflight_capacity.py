"""The full permitted selection is returned, never silently truncated."""

from tests.workbench.preflight_support import BASE, create_app, seed, snapshot


def test_five_thousand_permanent_batch_refs(schema_conn):
    seed(schema_conn, count=5000)
    refs = [row[0] for row in schema_conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key LIKE 'PF-%' AND active=1")]
    assert len(refs) == 5000
    before = snapshot(schema_conn)
    changes = schema_conn.total_changes
    response = create_app(schema_conn).test_client().post(BASE, json={"batch_refs": refs, "start_date": "2026-09-09", "end_date": "2026-09-09",
        "ready_check": True, "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals"})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["counts"]["selected_batches"] == 5000 and data["eligible_tasks"] == 5000
    assert len(data["tasks"]) == len(data["included_batches"]) == 5000
    assert set(data["scope"]["batch_refs"]) == set(refs)
    assert snapshot(schema_conn) == before and schema_conn.total_changes == changes
