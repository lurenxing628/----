"""Quantity changes retain legacy demand basis across every current write entry."""

from io import BytesIO

import openpyxl
import pytest
from flask import Blueprint, g

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.batch.service import BatchService
from core.services.workbench.batch.files import WorkbenchBatchFileService
from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.preflight import PreflightService
from tests.workbench.batch_support import detail, post
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import compute
from web.routes.workbench.batches import register_batch_routes


def _client(case):
    blueprint = Blueprint("legacy_material_quantity", __name__)
    register_batch_routes(blueprint)
    case.app.register_blueprint(blueprint)

    @case.app.before_request
    def bind():
        g.db = case.conn

    client = case.app.test_client()
    client.batch_conn = case.conn
    return client


def _change_quantity(case, client, ref, writer):
    if writer == "api":
        response = post(client, "update", {"fields": {"quantity": 10}}, ref=ref,
                        key="legacy-quantity-update-01")
        assert response.status_code == 200, response.get_json()
    elif writer == "file":
        workbook = openpyxl.Workbook()
        workbook.active.append(["批次号", "数量"])
        workbook.active.append(["B1", 10])
        content = BytesIO()
        workbook.save(content)
        workbook.close()
        files = WorkbenchBatchFileService(case.conn)
        document = files.preview(content.getvalue(), "overwrite")
        assert document["can_confirm"]
        with TransactionManager(case.conn).transaction():
            assert files.apply(document).result == "committed"
    else:
        BatchService(case.conn).update("B1", quantity=10, ready_status="yes")


@pytest.mark.parametrize("old_quantity,writer", [(5, "api"), (-1, "api"), (5, "file"), (5, "domain")])
def test_quantity_change_cannot_review_untouched_legacy_demand(candidate_case, old_quantity, writer):
    case = candidate_case
    # v36 retained demand amounts without inventing explicit review records.
    case.conn.execute("UPDATE Batches SET quantity=? WHERE batch_id='B1'", (old_quantity,))
    case.conn.execute("INSERT INTO Materials(material_id,name) VALUES ('OLD','钢材'),('NEW','辅料')")
    cursor = case.conn.execute("""INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status)
        VALUES ('B1','OLD',5,5,'yes')""")
    old_requirement = cursor.lastrowid
    case.conn.commit()
    assert not case.conn.execute("SELECT 1 FROM BatchMaterialReviews").fetchone()
    client, ref = _client(case), case.ref("batch", "B1")
    _change_quantity(case, client, ref, writer)
    basis = old_quantity if old_quantity >= 0 else None
    assert case.conn.execute("SELECT batch_quantity FROM BatchMaterialReviews WHERE requirement_id=?",
                             (old_requirement,)).fetchone()[0] == basis
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{"row_key": None,
        "material_ref": case.ref("material", "NEW"), "required_quantity": 1, "available_quantity": 1}]},
        ref=ref, key="legacy-new-demand-00001")
    assert response.status_code == 200, response.get_json()
    data, _ = PreflightService(case.conn).evaluate(case.settings())
    assert data["counts"]["ready_tasks"] == 0
    assert any(item["code"] == "material_review_required" for item in data["tasks"][0]["issues"])
    with pytest.raises(CandidateRunInputError):
        prepare_candidate_run_input(case.conn, case.settings(), case.projections())
    old = next(row for row in detail(client, ref)["data"]["materials"]["requirements"]
               if row["business_code"] == "OLD")
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{"row_key": old["row_key"],
        "material_ref": old["material_ref"], "required_quantity": 10, "available_quantity": 10}]},
        ref=ref, key="legacy-reviewed-demand-01")
    assert response.status_code == 200, response.get_json()
    _run, candidates = compute(case)
    result = service(case.conn).adopt(candidates[0], preview(case, candidates[0]),
                                      "legacy-reviewed-adopt-01", INTENT)
    assert result["result"] == "committed"
