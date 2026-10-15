"""Saved projections retain exact permanent memberships and archive failures."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.decision_read_models import Memberships, analysis_arrangements, decode_model


def test_delivery_projections_share_one_static_batch_group_and_reverse_identity_index():
    from core.services.workbench.facts.candidate_delivery import project_legacy_delivery_detail
    from core.services.workbench.facts.decision_delivery import project_decision_delivery

    scans = []

    class OperationRows(dict):
        def values(self):
            scans.append("operations")
            return super().values()

    class EntityRefs(dict):
        def items(self):
            scans.append("identities")
            return super().items()

    facts = GenerationFacts.__new__(GenerationFacts)
    facts.operations = {"op-a": 1, "op-b": 2}
    facts.entity_refs = EntityRefs({("batch", key): ref for key, ref in
                                   (("B1", "batch-a"), ("B2", "batch-b"), ("B3", "batch-c"))})
    facts.tables = {
        "BatchOperations": OperationRows({1: {"id": 1, "batch_id": "B1"}, 2: {"id": 2, "batch_id": "B2"}}),
        "Batches": {key: {"batch_id": key, "part_no": "P1", "part_name": "零件", "due_date": "2026-10-15"}
                    for key in ("B1", "B2", "B3")}}
    tasks = [{"row_ref": "row-a", "operation_ref": "op-a", "sequence": 0, "piece_id": None,
              "process_label": "车削", "start": "2026-10-15T08:00:00", "end": "2026-10-15T09:00:00",
              "machine": None, "operator": None}]
    batch_refs = ["batch-a", "batch-b", "batch-c"]
    candidate = {"artifact": {"metrics": {}}}
    settings = {"batch_refs": batch_refs}
    before = canonical_json(facts.tables)
    delivery = project_decision_delivery(facts, tasks, batch_refs, deferred_ids={2})
    detail = project_legacy_delivery_detail(candidate, facts, tasks, {}, settings, deferred_ids={2})
    assert [{key: value for key, value in row.items() if key != "last_operations"} for row in detail] == delivery
    assert [row["completion_state"] for row in delivery] == ["complete", "deferred", "unknown"]
    assert detail[0]["last_operations"] == tasks and detail[1]["last_operations"] == []
    assert scans == ["operations", "identities"]
    assert canonical_json(facts.tables) == before


def test_known_memberships_restore_scoring_metrics_and_preparation_roles_once():
    operations = ["a" * 48, "b" * 48, "c" * 48]
    batches = ["d" * 48, "e" * 48]
    decoder = Memberships({"operation_refs": operations, "batch_refs": batches,
        "operation_sets": [[2, 0], [], [1]], "batch_sets": [[1, 0], []]})
    members = lambda kind, index: {"membership_kind": kind, "membership_index": index}
    saved = {"scoring_scope": {"scheduled_operation_refs": members("operation", 0),
                             "complete_batch_refs": members("batch", 0), "components_known": False},
        "metrics": {"required": {"covered_operation_refs": members("operation", 0), "unknown_count": 2},
                    "due": {"covered_batch_refs": members("batch", 1)}},
        "preparation": {"coverage": {"new_schedule": members("operation", 0), "unknown": members("operation", 2)}}}
    original = canonical_json(saved)
    restored = decoder.expand(saved)
    assert restored["scoring_scope"] == {"scheduled_operation_refs": [operations[2], operations[0]],
        "complete_batch_refs": [batches[1], batches[0]], "components_known": False}
    assert restored["metrics"]["required"] == {"covered_operation_refs": [operations[2], operations[0]], "unknown_count": 2}
    assert restored["metrics"]["due"]["covered_batch_refs"] == []
    assert restored["preparation"]["coverage"] == {"new_schedule": [operations[2], operations[0]], "unknown": [operations[1]]}
    assert decoder.refs(members("operation", 0), "operation") is decoder.refs(members("operation", 0), "operation")
    assert canonical_json(saved) == original
    restored["scoring_scope"]["scheduled_operation_refs"].clear()
    assert decoder.refs(members("operation", 0), "operation") == [operations[2], operations[0]]


def test_projection_reads_reject_missing_rows_unknown_versions_and_duplicate_json_keys():
    from types import SimpleNamespace

    from core.services.workbench.run.decision_source import DecisionSource

    for row in (None, {"projection_version": "future-version", "summary_json": "{}"},
                {"projection_version": "decision-read-v1", "summary_json": None},
                {"projection_version": "decision-read-v1", "summary_json": '{"label":"a","label":"b"}'}):
        with pytest.raises(WorkbenchCommandRejected) as failure:
            decode_model(row, ("summary",))
        assert failure.value.code == "candidate_artifact_invalid"
    result = decode_model({"projection_version": "decision-read-v1", "delivery_detail_json": "[]", "process_json": None},
                          ("delivery_detail", "process"))
    assert result == {"delivery_detail": [], "process": None}

    candidate_ref, run_ref = "a" * 48, "b" * 48
    source = DecisionSource.__new__(DecisionSource)
    source.run = {"run_ref": run_ref}
    source.comparison_mode, source.reference_ref = "candidates", candidate_ref
    source._candidate_models = {candidate_ref: {}}
    source.memberships = Memberships({"operation_refs": [], "batch_refs": [], "operation_sets": [], "batch_sets": []})
    wrong_run = {"run_ref": "c" * 48, "projection_version": "decision-read-v1", "delivery_detail_json": "[]"}
    for row in (None, wrong_run, {**wrong_run, "run_ref": run_ref, "projection_version": "future-version"},
                {**wrong_run, "run_ref": run_ref, "delivery_detail_json": '[{"label":"a","label":"b"}]'}):
        source.repo = SimpleNamespace(candidate_read_model=lambda _key, _fields: row)
        for read in (source._saved_projection, source.saved_projection):
            with pytest.raises(WorkbenchCommandRejected) as failure:
                read("reference", "delivery_detail")
            assert failure.value.code == "candidate_artifact_invalid"
        assert source._candidate_models[candidate_ref] == {}


def test_core_and_catalog_expand_only_their_consumed_saved_fields():
    from core.services.workbench.run.decision import _core_candidates
    from core.services.workbench.run.decision_source import DecisionSource

    class TrackedMemberships(Memberships):
        def __init__(self, value):
            super().__init__(value)
            self.expanded = 0

        def refs(self, value, kind):
            refs = super().refs(value, kind)
            self.expanded += len(refs)
            return refs

    candidate_ref = "c" * 48
    source = DecisionSource.__new__(DecisionSource)
    source.rows = [{"candidate_ref": candidate_ref}]
    source.memberships = TrackedMemberships({"operation_refs": ["a" * 48], "batch_refs": [],
        "operation_sets": [[0]], "batch_sets": []})
    source._candidate_models = {candidate_ref: {"summary": {"candidate_ref": candidate_ref, "metrics": {},
        "catalog": {"candidate_ref": candidate_ref, "label": "saved"}, "run_ref": "b" * 48,
        "scheduled_operation_refs": {"membership_kind": "operation", "membership_index": 0}, "resource_views": {}}}}
    assert _core_candidates(source) == [{"candidate_ref": candidate_ref, "metrics": {}}]
    assert source.saved_candidate_catalog(candidate_ref) == {"candidate_ref": candidate_ref, "label": "saved"}
    assert source.memberships.expanded == 0
    source._candidate_models[candidate_ref]["summary"]["catalog"]["evaluations"] = {
        "due": {"scoring_scope": {"scheduled_operation_refs": {"membership_kind": "operation", "membership_index": 0}}}}
    assert source.saved_candidate_catalog(candidate_ref, fields=("candidate_ref", "label")) == {
        "candidate_ref": candidate_ref, "label": "saved"}
    assert source.memberships.expanded == 0
    assert source.scheduled_refs(candidate_ref) == {"a" * 48}
    assert source.memberships.expanded == 1


def test_analysis_arrangements_keep_unknown_identity_and_each_sources_resource_label():
    from types import SimpleNamespace

    from core.services.workbench.facts.decision_read_model import _arrangements
    from core.services.workbench.run.decision_source import DecisionSource

    supplier_ref = "d" * 48
    base = {"row_ref": "a" * 48, "operation_ref": "b" * 48, "batch_ref": "c" * 48,
        "batch_label": "B1", "process_label": "委外", "process_type_ref": None, "process_type_label": None,
        "start": "2026-10-15T08:00:00", "end": "2026-10-15T09:00:00", "source": "external",
        "locked": False, "interval_comparable": True, "data_gaps": [{"field": "machine.ref", "code": "not_recorded"}],
        "machine": {"ref": None, "label": "已知设备"}, "operator": None,
        "supplier": {"ref": supplier_ref, "label": "来源一名称"}}
    second = {**base, "row_ref": "e" * 48, "supplier": {"ref": supplier_ref, "label": "来源二名称"}}
    point = {**base, "row_ref": "f" * 48, "machine": None, "supplier": None,
        "end": base["start"], "event_kind": "point", "occupies_resources": False}
    original = [base, second, point]
    saved = _arrangements(original)
    assert analysis_arrangements(saved) == original
    assert saved["resource_values"] == [
        {"kind": "machine", "ref": None, "label": "已知设备"},
        {"kind": "supplier", "ref": supplier_ref, "label": "来源一名称"},
        {"kind": "supplier", "ref": supplier_ref, "label": "来源二名称"}]

    expansion_calls, loaded_fields = [], []

    class TrackedMemberships(Memberships):
        def expand(self, value, **kwargs):
            expansion_calls.append(value)
            return super().expand(value, **kwargs)

    candidate_ref, run_ref = "1" * 48, "2" * 48
    source = DecisionSource.__new__(DecisionSource)
    source.run = {"run_ref": run_ref}
    source.comparison_mode, source.reference_ref = "candidates", candidate_ref
    source._candidate_models, source._analysis = {candidate_ref: {}}, {}
    source.memberships = TrackedMemberships({"operation_refs": [base["operation_ref"]], "batch_refs": [base["batch_ref"]],
                                            "operation_sets": [[0]], "batch_sets": [[0]]})

    def read_model(key, fields):
        loaded_fields.append((key, fields))
        return {"run_ref": run_ref, "projection_version": "decision-read-v1", "arrangements_json": canonical_json(saved)}

    source.repo = SimpleNamespace(candidate_read_model=read_model)
    tasks = source.analysis_tasks("reference")
    assert tasks == original and source.analysis_tasks(candidate_ref) is tasks
    assert expansion_calls == [] and loaded_fields == [(candidate_ref, ("arrangements",))]
    raw = source._saved_projection(candidate_ref, "arrangements")
    assert raw is source._candidate_models[candidate_ref]["arrangements"]
    assert tasks[0] is not raw["rows"][0]
    assert tasks[0]["data_gaps"] is raw["rows"][0][-1]
    public = source.saved_projection("reference", "arrangements")
    assert public == saved and public is not raw and expansion_calls[0] is raw
    assert public["rows"][0][-1] is not tasks[0]["data_gaps"]
    assert loaded_fields == [(candidate_ref, ("arrangements",))] and canonical_json(raw) == canonical_json(saved)
    source._candidate_models[candidate_ref]["preparation"] = {"coverage": {
        "new_schedule": {"membership_kind": "operation", "membership_index": 0}}}
    assert source.saved_projection("reference", "preparation") == {"coverage": {"new_schedule": [base["operation_ref"]]}}
