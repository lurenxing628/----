"""Current strict DTO, cross-page identities and pinned CSV/XLSX exports."""

from copy import deepcopy

import pytest

from core.services.workbench.facts import adoption_baseline_values as values
from tests.workbench.plan_adoption_baseline_support import trial_case as trial_case  # noqa: F401
from tests.workbench.plan_adoption_baseline_support import two_versions
from tests.workbench.plan_read_support import make_api
from tests.workbench.plan_transport_support import catalog_fixture, run_probe, workspace_fixture
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import service as candidate_adopter
from tests.workbench.run_candidate_support import compute
from tests.workbench.trial_adoption_support import service as trial_adopter
from tests.workbench.trial_support import change, create
from tests.workbench.trial_support import service as trial_service


@pytest.mark.parametrize("source", ["trial"])
def test_cross_page_catalog_workspace_and_strict_dto(trial_case, tmp_path, source):
    first, second = two_versions(trial_case, source)
    api = make_api(trial_case.path)
    latest = catalog_fixture(api, "new official", size=1)
    page = latest["payload"]
    original = catalog_fixture(api, "original official", size=1, cursor=page["data"]["page"]["next_cursor"],
                               snapshot_ref=page["meta"]["snapshot_ref"])
    assert latest["payload"]["data"]["plans"][0]["plan_ref"] == second["plan_ref"]
    assert original["payload"]["data"]["plans"][0]["plan_ref"] == first["plan_ref"]
    selected = workspace_fixture(api, source + " adopted", second["plan_ref"])
    baseline = selected["payload"]["data"]["projections"]["baseline"]
    assert baseline["state"] == "available" and baseline["baseline_plan"]["plan_ref"] == first["plan_ref"]
    provenance = selected["payload"]["data"]["provenance"]
    assert provenance["state"] == "available" and provenance["source_kind"] == "trial_adoption"
    assert provenance["algorithm"] is None and provenance["run_ref"] is None
    assert provenance["source_label"] and provenance["adopted_at"] and provenance["finished_at"]
    assert provenance["baseline"]["kind"] == "trial_creation_official"
    assert provenance["baseline"]["baseline_ref"] == first["plan_ref"]
    assert provenance["baseline"]["captured_at"] == provenance["accepted_at"]
    initial = workspace_fixture(api, "first adoption", first["plan_ref"])
    assert initial["payload"]["data"]["provenance"]["state"] == "available"
    assert initial["payload"]["data"]["provenance"]["baseline"]["baseline_ref"] is None
    fixtures = [latest, original, selected, initial]
    for field, value in (("basis", "scenario_base"), ("basis", "invented"), ("compared_fields", ["supplier_ref"])):
        bad = deepcopy(selected)
        bad.update(name="reject " + field + str(value), contract_error=True)
        bad["payload"]["data"]["projections"]["baseline"][field] = value
        fixtures.append(bad)
    bad = deepcopy(selected)
    bad.update(name="reject current-official baseline", contract_error=True)
    bad["payload"]["data"]["projections"]["baseline"]["baseline_plan"]["is_current_official"] = True
    fixtures.append(bad)
    for code in values.REASONS:
        unavailable = deepcopy(initial)
        unavailable["name"] = code
        unavailable["payload"]["data"]["projections"]["baseline"]["reason_code"] = code
        fixtures.append(unavailable)
    assert run_probe(tmp_path, fixtures)["checks"] == len(fixtures)


def test_formal_supplier_identity_and_baseline_resource_names_follow_their_adoptions(trial_case, tmp_path):
    case = trial_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT','Heat treatment','external')")
    case.conn.executemany("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES (?,?,'XT',2)",
                         (("XS1", "First supplier"), ("XS2", "Second supplier"), ("XS3", "Current replacement")))
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                      "VALUES ('P1',2,'XT','Heat treatment','external','XS1',2)")
    external = case.operation(seq=2, op_type_id="XT", op_type_name="Heat treatment", source="external",
                              supplier_id="XS1", ext_days=2, machine_id=None, operator_id=None)
    case.conn.commit()
    _, refs = compute(case)
    adopter = candidate_adopter(case.conn)
    preview = adopter.preview(refs[0])
    first = adopter.adopt(refs[0], preview["write_context"]["write_token"], "formal-source-v1-adoption", INTENT)["data"]["official_plan"]
    case.conn.execute("UPDATE BatchOperations SET supplier_id='XS2' WHERE id=?", (external,))
    case.conn.commit()
    draft = create(case, {"base": {"plan_ref": first["plan_ref"]}}, key="formal-source-trial-create")
    draft = change(case, draft, start="2026-09-09T08:00:00", machine="M2", operator="O2", key="formal-source-trial-change")["data"]
    saved = trial_service(case.conn).save(draft["draft_ref"], {"name": "Changed resources"},
        draft["write_context"]["write_token"], "formal-source-trial-save")["data"]
    adopter = trial_adopter(case.conn)
    preview = adopter.preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    second = adopter.adopt(saved["scenario_ref"], preview["write_context"]["write_token"],
                            "formal-source-v2-adoption", INTENT)["data"]["official_plan"]
    case.conn.execute("UPDATE BatchOperations SET supplier_id='XS3' WHERE id=?", (external,))
    case.conn.execute("UPDATE Suppliers SET name='Renamed current supplier' WHERE supplier_id IN ('XS1','XS2')")
    case.conn.execute("UPDATE Machines SET name='Renamed current M1' WHERE machine_id='M1'")
    case.conn.execute("UPDATE Operators SET name='Renamed current O1' WHERE operator_id='O1'")
    case.conn.commit()
    api = make_api(case.path)
    old = workspace_fixture(api, "original adopted supplier", first["plan_ref"])
    current = workspace_fixture(api, "trial adopted resources and suppliers", second["plan_ref"])
    original, data = old["payload"]["data"], current["payload"]["data"]
    assert next(row for row in original["tasks"] if row["sequence"] == 2)["supplier_ref"] == case.ref("supplier", "XS1")
    assert next(row for row in data["tasks"] if row["sequence"] == 2)["supplier_ref"] == case.ref("supplier", "XS2")
    baseline = data["projections"]["baseline"]
    assert baseline["state"] == "available", baseline
    assert baseline["compared_fields"] == ["start", "end", "machine_ref", "operator_ref"]
    before_external = next(row["before"] for row in baseline["items"] if row["before"]["sequence"] == 2)
    assert before_external["supplier_ref"] == case.ref("supplier", "XS1")
    directory = {row["ref"]: row for row in data["resources"]}
    assert directory[case.ref("machine", "M1")]["label"] == "Lathe 1"
    assert directory[case.ref("operator", "O1")]["label"] == "Operator 1"
    assert directory[case.ref("supplier", "XS1")]["label"] == "First supplier"
    assert directory[case.ref("supplier", "XS2")]["label"] == "Second supplier"
    assert case.ref("supplier", "XS3") not in directory
    assert run_probe(tmp_path, [old, current])["checks"] == 2
