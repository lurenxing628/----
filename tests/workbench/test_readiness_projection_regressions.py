"""Quantity round trips keep batch, preflight and dashboard readiness consistent."""

from datetime import datetime

import pytest

from core.infrastructure.transaction import TransactionManager
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.batch.projection import BatchProjection
from core.services.workbench.dashboard.facts import DashboardFacts
from core.services.workbench.dashboard.projection import material
from core.services.workbench.run.preflight import PreflightService
from tests.workbench.master_overview_support import overview_client as _overview_client  # noqa: F401
from tests.workbench.master_overview_support import query, stored
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


@pytest.mark.parametrize("required,ready", [(0.1 + 0.2, True), (0.300001, False)])
def test_saved_fractional_arrivals_have_one_readiness_rule(run_case, required, ready):
    case = run_case
    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','千克')")
    case.conn.commit()
    with TransactionManager(case.conn).transaction():
        WorkbenchBatchMaterialService(case.conn).apply(case.ref("batch", "B1"), {"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"),
            "required_quantity": required, "available_quantity": 0,
            "arrivals": [{"arrival_date": "2026-09-09", "quantity": 0.1},
                         {"arrival_date": "2026-09-10", "quantity": 0.2}]}]})

    def read():
        batch_facts = BatchFacts(case.conn).load()
        batch = next(row for row in batch_facts["Batches"] if row["batch_id"] == "B1")
        assert BatchProjection(batch_facts).entity(batch)["display_ready_status"] == ("yes" if ready else "partial")
        data, _ = PreflightService(case.conn).evaluate(case.settings())
        assert data["counts"]["ready_tasks"] == int(ready)
        with TransactionManager(case.conn).transaction():
            facts = DashboardFacts(case.conn, datetime(2026, 9, 25)).load()
            items, _ = material(facts)
        item = items[0]
        assert item["source"]["ready_status"] == ("yes" if ready else "partial")
        assert item["source"]["requirements"][0]["ready_status"] == ("yes" if ready else "no")
        assert item["risk"]["active"] is not ready

    unchanged(case, read)


@pytest.mark.parametrize("required,available,shortage", [(0.3, 0.29999999999999993, False),
    (0.3, 0.2999, True), (9007199254740991, 9007199254740990, True)])
def test_master_overview_only_reports_real_material_shortages(overview_client, required, available, shortage):
    client = overview_client
    client.conn.execute("UPDATE BatchMaterials SET required_qty=?,available_qty=?,ready_status='yes' WHERE batch_id='B000'",
                        (required, available))
    client.conn.commit()
    before = stored(client)
    result = query(client, {"view": "issues", "domain": "material", "column_filters": {"evidence": "B000"}})
    pending = [row for row in result["data"]["rows"] if row["rule"] == "batch_material.pending"]
    assert bool(pending) is shortage
    assert stored(client) == before
