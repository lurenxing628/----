"""Strict part creation and explicit selection contracts for process actions."""

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_query import ProcessPageRequest
from core.models.workbench_process_route import check_route_text
from core.models.workbench_process_table_query import process_table_scope
from core.models.workbench_resource_action import ResourceActionPreview, resource_refs
from core.models.workbench_resource_input import resource_object, resource_text


def normalize_process_part_create(input):
    resource_object(input, {"business_code", "label", "route_raw", "remark"}, "input")
    result = {}
    for field, label in (("business_code", "图号"), ("label", "名称"), ("remark", "备注")):
        result[field] = resource_text(input.get(field), field, nullable=field == "remark")
        _check_text(result[field], label, field)
    route = input.get("route_raw")
    _check_text(route, "路线文字", "route_raw")
    if route is not None:
        check_route_text(route)
    result["route_raw"] = route
    return result


def _check_text(value, label, field):
    if value is None:
        return
    if type(value) is not str:
        raise ValidationError(label + "必须是文字或留空。", field=field)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(label + "包含无法保存的字符，请核对。", field=field) from exc


def process_part_refs(refs):
    # Keep the resource selection contract, including selections beyond one page.
    try:
        return resource_refs(refs)
    except ValidationError as exc:
        raise ValidationError("请选择有效的零件记录，选择列表不能为空或重复。", field="refs") from exc


def process_part_scope(scope):
    if type(scope) is dict and ("column_filters" in scope or type(scope.get("sort")) is list):
        return process_table_scope(scope)
    resource_object(scope, {"query", "stage", "sort", "direction"}, "scope")
    query = ProcessPageRequest(**scope)
    return {key: value for key, value in query.scope().items() if key not in ("kind", "size")}


def check_process_part_preview(original, current):
    if not isinstance(original, ResourceActionPreview) or original.document != current.document:
        raise WorkbenchCommandRejected("stale_write", "零件资料、删除选择或筛选条件已变化，请重新预检。")
    if current.as_dict()["summary"]["rejected"]:
        raise WorkbenchCommandRejected("constraint_conflict", "有零件不能删除，本次未删除任何零件，请先核对预检结果。")
