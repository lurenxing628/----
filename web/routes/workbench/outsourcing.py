"""Unregistered DI hook; coordinator owns root blueprint, migration and lifecycle.

POST receipts/preview accepts {input: ReceiptInput}; receipts accepts CommandInput.
Create input: target={kind,batch_ref,supplier_ref,operation_refs}, sent, planned,
returned (null when absent), confirmedState, declared_operator, reason.
Update input: outsourcing_ref, declared_operator, reason, and sparse fact fields.
An omitted date is preserved; explicit null only clears returned with matching state.
Each new intent records a confirmation, including unchanged-value reconfirmations.
"""

from flask import current_app, g

from core.models.workbench_outsourcing import MAX_BYTES, reject
from core.services.workbench.outsourcing.commands import WorkbenchOutsourcingCommandService
from core.services.workbench.outsourcing.service import WorkbenchOutsourcingService
from core.shared.key_sets import keys_conform
from web.api_responses import json_response, query_success
from web.runtime_host import wall_clock

from .api_responses import api_endpoint, read_endpoint
from .read_context import bind_read_snapshot, current_snapshot_time, page_integer, read_snapshot_time, unbound_snapshot
from .request_json import BodyTexts, command_body, read_json_body, rejecter, single_value_arguments
from .write_context import issue_write_context, validate_write_context


def _arguments(kind):
    allowed = {"snapshot_ref", "page", "size"}
    if kind in ("targets", "receipts"):
        allowed.add("batch_ref")
    if kind == "targets":
        allowed.add("query")
    if kind == "receipts":
        allowed.add("status")
    args = single_value_arguments(allowed, message="外协的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。")
    number = page_integer(args.pop("page", "1"))
    size = page_integer(args.pop("size", "20"))
    if number > 1 and not args.get("snapshot_ref"):
        reject("翻页位置已失效，请回到第 1 页重新查询。", "snapshot_required", 400)
    return args, number, size


def _read(kind, ref=None):
    args, number, size = _arguments(kind)
    token = args.pop("snapshot_ref", None)
    scope = {"kind": kind, "outsourcing_ref": ref, "size": size, **args}
    now, binding = read_snapshot_time(token)
    stale_message = "外协来源或登记内容有变化，还没有保存；系统没有偷偷用新数据。请点「刷新」后重新核对。"
    snapshot = None

    def bind(content):
        nonlocal snapshot
        snapshot = bind_read_snapshot(
            scope, content, token, as_of=now, binding=binding, stale_message=stale_message,
        )

    reader = WorkbenchOutsourcingService(g.db)
    with reader.read_snapshot():
        if kind == "targets":
            data = reader.targets(number=number, size=size, bind_snapshot=bind, **args)
        elif kind == "receipts":
            data = reader.receipts(number=number, size=size, as_of=now, bind_snapshot=bind, **args)
        elif kind == "history":
            data = reader.history(ref, number=number, size=size, as_of=now, bind_snapshot=bind)
        else:
            if number != 1:
                reject("单条外协登记没有分页。请直接查看这一条。", status=400)
            data = reader.detail(ref, as_of=now, bind_snapshot=bind)
    return query_success(data, snapshot, byte_limit=MAX_BYTES)


@api_endpoint
def outsourcing_targets():
    return _read("targets")


@api_endpoint
def outsourcing_receipts():
    return _read("receipts")


@api_endpoint
def outsourcing_detail(outsourcing_ref):
    return _read("detail", outsourcing_ref)


@api_endpoint
def outsourcing_history(outsourcing_ref):
    return _read("history", outsourcing_ref)


_UNREADABLE = "提交的内容格式不正确，外协登记还没有保存。请刷新页面后重新填写。"
_BODY = BodyTexts(transport=_UNREADABLE, malformed=_UNREADABLE,
                  incomplete="提交的内容不完整或有多余项，外协登记还没有保存。请刷新页面后重新填写。")


@read_endpoint
def outsourcing_preview():
    body = read_json_body(_BODY)
    if not keys_conform(body, ("input",)) or type(body["input"]) is not dict:
        rejecter(_BODY.incomplete)()
    now = current_snapshot_time()
    service = WorkbenchOutsourcingCommandService(g.db, clock=wall_clock(current_app), context_factory=issue_write_context)
    result = service.preview(body["input"], now=now)
    return query_success(result, unbound_snapshot(now), byte_limit=MAX_BYTES)


@api_endpoint
def outsourcing_confirm():
    body = command_body(_BODY, stale="本页数据已过期，外协登记还没有保存。请刷新页面后重新填写。")
    if type(body["input"]) is not dict:
        rejecter(_BODY.incomplete)()
    service = WorkbenchOutsourcingCommandService(g.db, clock=wall_clock(current_app), context_factory=issue_write_context)
    result = service.execute(body["input"], request_key=body["request_key"],
        validate_context=lambda subject, action, snapshot: validate_write_context(body["write_token"], subject, action, snapshot))
    return json_response(result)


def register_outsourcing_routes(bp):
    root = "/api/workbench/v1/outsourcing"
    for path, view, method in (("/targets", outsourcing_targets, "GET"), ("/receipts", outsourcing_receipts, "GET"),
        ("/receipts/<outsourcing_ref>", outsourcing_detail, "GET"), ("/receipts/<outsourcing_ref>/history", outsourcing_history, "GET"),
        ("/receipts/preview", outsourcing_preview, "POST"), ("/receipts", outsourcing_confirm, "POST")):
        bp.add_url_rule(root + path, view_func=view, methods=[method])
