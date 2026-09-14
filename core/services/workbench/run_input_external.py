"""Populate the existing algorithm builder's cache from validated raw templates."""

from dataclasses import fields

from core.models.external_group import ExternalGroup
from core.models.part_operation import PartOperation
from core.services.workbench.preflight_checks import number

from .run_input_rows import fail


def _template_model(row, op) -> PartOperation:
    if row is None or row["status"] != "active" or row["source"] != "external":
        fail("external_template_missing", "这道外协工序在工艺资料里找不到对应的模板工序，这次排产没有开始。请先到工艺资料补上。", op_id=op.id)
    if row["op_type_id"] != op.op_type_id:
        fail("external_template_mismatch", "这道外协工序的工种和模板里的不一样，这次排产没有开始。请到工艺资料核对工种。", op_id=op.id)
    for field in ("setup_hours", "unit_hours"):
        if not number(row[field]):
            fail("external_template_invalid", "模板工序的工时读不出来，这次排产没有开始，系统不会替你按默认值算。请到工艺资料补上工时。", op_id=op.id, field=field)
    return PartOperation(**{field.name: row[field.name] for field in fields(PartOperation)})


def _group_model(group, part_no, op):
    if group is None or group["part_no"] != part_no or group["merge_mode"] not in ("separate", "merged"):
        fail("external_group_invalid", "这道外协工序的合并送出分组资料不完整，这次排产没有开始。请到工艺资料核对分组。", op_id=op.id)
    if (not number(group["start_seq"], integer=True, positive=True)
            or not number(group["end_seq"], integer=True, positive=True)
            or not group["start_seq"] <= op.seq <= group["end_seq"]):
        fail("external_group_range_invalid", "这个外协合并分组的工序范围填得不对，这次排产没有开始。请到工艺资料核对起止工序号。", op_id=op.id)
    if group["merge_mode"] == "merged" and not number(group["total_days"], positive=True):
        fail("external_group_days_invalid", "这个外协合并分组的周期天数读不出来或填得不对，这次排产没有开始。请到工艺资料补上周期。", op_id=op.id)
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
