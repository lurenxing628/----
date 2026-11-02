"""Strict part creation and explicit selection contracts for process actions."""

from dataclasses import dataclass

from core.errors import ValidationError
from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import is_entity_ref
from core.models.workbench_process_route import MAX_ROUTE_TEXT_BYTES
from core.models.workbench_resource_input import resource_object, resource_text


def normalize_process_part_create(input):
    resource_object(input, {"business_code", "label", "route_raw", "remark"}, "input")
    result = {}
    for field, label in (("business_code", "图号"), ("label", "名称"), ("remark", "备注")):
        result[field] = resource_text(input.get(field), field, nullable=field == "remark")
        _check_text(result[field], label, field)
    route = input.get("route_raw")
    encoded = _check_text(route, "路线文字", "route_raw")
    if encoded is not None and len(encoded) > MAX_ROUTE_TEXT_BYTES:
        raise WorkbenchCommandRejected("route_too_large", "路线文字不能超过256 KiB（UTF-8），未截断。", 413)
    result["route_raw"] = route
    return result


def _check_text(value, label, field):
    if value is None:
        return
    if type(value) is not str:
        raise ValidationError(label + "必须是文字或留空。", field=field)
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(label + "包含无法保存的字符，请核对。", field=field) from exc


def process_part_refs(refs, *, allow_empty=False):
    if type(refs) is not list or (not refs and not allow_empty):
        raise ValidationError("请选择有效的零件记录，选择列表不能为空或重复。", field="refs")
    if any(not is_entity_ref(ref) for ref in refs) or len(set(refs)) != len(refs):
        raise ValidationError("请选择有效的零件记录，选择列表不能为空或重复。", field="refs")
    return refs


@dataclass(frozen=True)
class PartDeletePreview(AtomicActionPreview):
    stale_message = "零件资料、删除选择或筛选条件已变化，请重新预检。"
    rejected_message = "有零件不能删除，本次未删除任何零件，请先核对预检结果。"
