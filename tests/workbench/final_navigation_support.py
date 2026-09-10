"""Small explicit URL cases; no app factory, database fixture or browser."""

import json

from werkzeug.datastructures import MultiDict

REF = "a" * 48
OTHER_REF = "b" * 48
START = "2026-09-10T08:00:00"
END = "2026-09-11T08:00:00"


def nav_args(view, context, **extra):
    payload = {"version": 1, "view": view, "context": context}
    return MultiDict({"view": view, "nav": json.dumps(payload, ensure_ascii=False), **extra})


VALID_CONTEXTS = (
    ("gantt", {"plan_ref": REF}),
    ("analysis", {"plan_ref": REF, "range_start": START, "range_end": END}),
    ("delay", {"plan_ref": REF}),
    ("delay", {"plan_ref": REF, "range_start": START, "range_end": END}),
    ("process", {"source": "production"}),
    ("process", {"source": "production", "kind": "material", "entity_ref": REF}),
    ("process", {"source": "production", "kind": "machine", "entity_ref": REF}),
    ("process", {"source": "production", "kind": "operator", "entity_ref": REF}),
    ("process", {"source": "production", "kind": "supplier", "entity_ref": REF}),
    ("process", {"source": "production", "kind": "op_type", "entity_ref": REF, "category": "internal"}),
    ("process", {"source": "production", "kind": "op_type", "entity_ref": REF, "category": "external"}),
    ("process", {"source": "production", "kind": "part", "entity_ref": REF, "stage": "hours",
                 "template_operation_ref": OTHER_REF, "template_external_group_ref": REF}),
    ("process", {"source": "production", "kind": "calendar", "month": "2024-02", "date": "2024-02-29"}),
    ("process", {"source": "production", "kind": "calendar", "month": "0001-01"}),
    ("batches", {"entity_ref": REF}),
    ("batches", {"focus": "unready", "batchIds": ["批次甲", "B-002"]}),
    ("reports", {"scope": {"plan_ref": REF}, "topic": "records", "catalogOpen": True}),
    ("reports", {"scope": {"source": "production", "kind": "execution_analysis", "plan_ref": REF,
                           "plan_finish_date_from": "2024-02-29", "plan_finish_date_to": "2024-03-01",
                           "batch_ref": OTHER_REF, "resource_type": "machine", "resource_ref": REF,
                           "query": "工序甲", "focus": "unreported"}, "catalogOpen": False}),
    ("review", {"scope": {"plan_ref": REF, "resource_type": "operator", "resource_ref": "unassigned"}}),
    ("run", {"run_ref": REF}),
    ("trial", {"draft_ref": REF}),
    ("trial", {"scenario_ref": REF}),
    ("trial", {"base": {"plan_ref": REF}}),
    ("trial", {"base": {"candidate_ref": REF}, "scope": {"range_start": START, "range_end": END,
               "batch_refs": [OTHER_REF], "resource_type": "machine", "resource_ref": REF, "query": "工序甲"}}),
)

INVALID_CONTEXTS = (
    ("delay", {"plan_ref": REF, "range_start": START}),
    ("delay", {"candidate_ref": REF}), ("delay", {"plan_ref": REF, "query": "B-001"}),
    ("delay", {"plan_ref": REF, "range_start": None, "range_end": None}),
    ("gantt", {"version": 7}), ("gantt", {"plan_ref": None}), ("gantt", {"plan_ref": "latest"}),
    ("gantt", {"plan_ref": REF.upper()}), ("gantt", {"plan_ref": REF, "plan_role": "adopted"}),
    ("gantt", {"plan_ref": REF, "range_start": START}),
    ("gantt", {"plan_ref": REF, "range_start": END, "range_end": START}),
    ("gantt", {"plan_ref": REF, "range_start": START, "range_end": START}),
    ("gantt", {"plan_ref": REF, "range_start": "2026-02-30T08:00:00", "range_end": END}),
    ("gantt", {"plan_ref": REF, "range_start": START + "Z", "range_end": END}),
    ("gantt", {"plan_ref": REF, "snapshot_ref": "s" * 32}),
    ("gantt", {"plan_ref": REF, "range_start": None, "range_end": None}),
    ("gantt", {"plan_ref": REF, "range_start": None}),
    ("analysis", {"candidate_ref": REF}), ("analysis", {"plan_ref": REF, "query": "B-001"}),
    ("process", {"source": "sample"}), ("process", {"kind": "machine", "entity_ref": REF}),
    ("process", {"source": "production", "kind": "machine", "entity_ref": None}),
    ("process", {"source": "production", "kind": "machine", "entity_ref": REF, "machine_id": "M1"}),
    ("process", {"source": "production", "kind": "op_type", "entity_ref": REF}),
    ("process", {"source": "production", "kind": "op_type", "entity_ref": REF, "category": "all"}),
    ("process", {"source": "production", "kind": "calendar", "month": "2026-13"}),
    ("process", {"source": "production", "kind": "calendar", "month": "0000-01"}),
    ("process", {"source": "production", "kind": "calendar", "month": "2026-02", "date": "2026-02-29"}),
    ("process", {"source": "production", "kind": "calendar", "month": "2026-02", "date": "2026-03-01"}),
    ("process", {"source": "production", "kind": "part", "entity_ref": REF, "stage": "guess"}),
    ("process", {"source": "production", "kind": "part", "entity_ref": REF, "template_operation_ref": None}),
    ("batches", {"entity_ref": False}), ("batches", {"batch_ref": REF}),
    ("batches", {"batchIds": [""]}), ("batches", {"focus": "all"}),
    ("batches", {"return_to": "run"}),
    ("reports", {"scope": {}}), ("reports", {"scope": {"plan_ref": None}}),
    ("reports", {"scope": {"plan_ref": REF}, "topic": "overdue"}),
    ("reports", {"scope": {"plan_ref": REF}, "catalogOpen": 1}),
    ("reports", {"scope": {"plan_ref": REF, "date_from": "2026-09-10"}}),
    ("reports", {"scope": {"plan_ref": REF, "source": "sample"}}),
    ("reports", {"scope": {"plan_ref": REF, "kind": "resource"}}),
    ("reports", {"scope": {"plan_ref": REF, "plan_finish_date_from": "2026-09-10"}}),
    ("reports", {"scope": {"plan_ref": REF, "resource_ref": OTHER_REF}}),
    ("reports", {"scope": {"plan_ref": REF, "query": "x" * 201}}),
    ("review", {"scope": {"plan_ref": REF}, "topic": "records"}),
    ("run", {"run_ref": None}), ("run", {"run_ref": REF, "batch_refs": [OTHER_REF]}),
    ("run", {"start_date": "2026-09-10", "end_date": "2026-09-12"}),
    ("trial", {"draft_ref": REF, "scenario_ref": OTHER_REF}),
    ("trial", {"base": {"plan_ref": REF, "candidate_ref": OTHER_REF}}),
    ("trial", {"base": {"plan_ref": REF}, "scope": {"range_start": START}}),
    ("trial", {"base": {"plan_ref": REF}, "scope": {"resource_ref": OTHER_REF}}),
    ("trial", {"base": {"plan_ref": REF}, "scope": {"batch_refs": [None]}}),
    ("trial", {"base": {"plan_ref": REF}, "scope": {"range_start": None, "range_end": None}}),
)
