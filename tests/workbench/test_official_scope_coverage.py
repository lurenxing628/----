"""Archived pressure and adoption use the same complete official operation set."""

import json

import pytest

from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.services.workbench.facts.official_scope_coverage import official_scope_coverage
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.run.candidate_adoption_validation import _require_official_scope
from tests.workbench.run_candidate_adoption_support import INTENT, candidate, preview, service, snapshot
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401


def test_saved_permanent_coverage_agrees_with_real_adoption_guard(candidate_case):
    case = candidate_case
    case.batch("B2")
    second = case.operation("B2")
    case.conn.commit()
    ref = candidate(case, case.settings("B1", "B2"))
    service(case.conn).adopt(ref, preview(case, ref), "coverage-full-official", INTENT)
    refs = {json.loads(row[1])["op_id"]: row[0] for row in case.conn.execute(
        "SELECT operation_ref,payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))}
    coverage = official_scope_coverage(refs.values(), [refs[case.op_id]])
    assert coverage == {"covers_official_scope": False, "official_operation_count": 2,
                        "covered_official_operation_count": 1, "missing_official_operations": [refs[second]]}
    before = snapshot(case.conn)
    with pytest.raises(CandidateAdoptionBlocked) as exc:
        _require_official_scope(ProductionFactsCapture(case.conn).latest_plan_rows(1), {case.op_id})
    assert exc.value.code == "official_scope_not_covered"
    _require_official_scope(ProductionFactsCapture(case.conn).latest_plan_rows(1), {case.op_id, second})
    assert snapshot(case.conn) == before
