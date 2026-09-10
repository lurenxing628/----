"""Populate the existing algorithm builder's cache from validated raw templates."""

from dataclasses import fields

from core.models.external_group import ExternalGroup
from core.models.part_operation import PartOperation
from core.services.workbench.preflight_checks import number

from .run_input_rows import fail


def _template_model(row, op) -> PartOperation:
    if row is None or row["status"] != "active" or row["source"] != "external":
        fail("external_template_missing", "External operation has no active matching template.", op_id=op.id)
    if row["op_type_id"] != op.op_type_id:
        fail("external_template_mismatch", "External work type differs from its template.", op_id=op.id)
    for field in ("setup_hours", "unit_hours"):
        if not number(row[field]):
            fail("external_template_invalid", "Unknown template hours cannot be defaulted.", op_id=op.id, field=field)
    return PartOperation(**{field.name: row[field.name] for field in fields(PartOperation)})


def _group_model(group, part_no, op):
    if group is None or group["part_no"] != part_no or group["merge_mode"] not in ("separate", "merged"):
        fail("external_group_invalid", "External group is missing or inconsistent.", op_id=op.id)
    if (not number(group["start_seq"], integer=True, positive=True)
            or not number(group["end_seq"], integer=True, positive=True)
            or not group["start_seq"] <= op.seq <= group["end_seq"]):
        fail("external_group_range_invalid", "External group sequence range is invalid.", op_id=op.id)
    if group["merge_mode"] == "merged" and not number(group["total_days"], positive=True):
        fail("external_group_days_invalid", "Merged external lead time is unknown or invalid.", op_id=op.id)
    return ExternalGroup(**{field.name: group[field.name] for field in fields(ExternalGroup)})


def prime_template_cache(svc, tables, batches, operations):
    templates = {(row["part_no"], row["seq"]): row for row in tables["PartOperations"]}
    groups = {row["group_id"]: row for row in tables["ExternalGroups"]}
    cache = {"batch": dict(batches), "tmpl": {}, "grp": {}}
    for op in operations:
        if op.source != "external":
            continue
        key = (batches[op.batch_id].part_no, op.seq)
        row = templates.get(key)
        template = _template_model(row, op)
        cache["tmpl"][key] = template
        group_id = template.ext_group_id
        if group_id is None:
            continue
        group = groups.get(group_id)
        cache["grp"][group_id] = _group_model(group, key[0], op)
    svc._aps_schedule_input_cache = cache
