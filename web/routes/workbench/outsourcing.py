"""Unregistered DI hook; coordinator owns root blueprint, migration and lifecycle.

POST receipts/preview accepts {input: ReceiptInput}; receipts accepts CommandInput.
Create input: target={kind,batch_ref,supplier_ref,operation_refs}, sent, planned,
returned (null when absent), confirmedState, declared_operator, reason.
Update input: outsourcing_ref, declared_operator, reason, and sparse fact fields.
An omitted date is preserved; explicit null only clears returned with matching state.
Each new intent records a confirmation, including unchanged-value reconfirmations.
"""

import json
from datetime import datetime

from flask import g, jsonify, request

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_outsourcing import bounded, reject
from core.models.workbench_outsourcing_input import factory_time
from core.services.workbench.outsourcing import WorkbenchOutsourcingService
from core.services.workbench.outsourcing_commands import WorkbenchOutsourcingCommandService
from web.public_token_registry import issue_public_token, resolve_public_token

from .api_responses import api_endpoint, query_success
from .write_context import issue_write_context, validate_write_context

_SCOPE = "workbench-outsourcing-read-v1"


def _positive_integer(value: str) -> int:
    if not value.isascii() or not value.isdigit() or len(value) > 6 or int(value) < 1:
        reject("页码和每页数量须为正整数。", status=400)
    return int(value)


def _arguments(kind):
    allowed = {"snapshot_ref", "page", "size"}
    if kind in ("targets", "receipts"):
        allowed.add("batch_ref")
    if kind == "receipts":
        allowed.add("status")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        reject("外协查询含未知或重复参数，未忽略查询条件。", status=400)
    args = request.args.to_dict()
    number = _positive_integer(args.pop("page", "1"))
    size = _positive_integer(args.pop("size", "20"))
    if number > 1 and not args.get("snapshot_ref"):
        reject("翻页必须携带原读取快照。", "snapshot_required", 400)
    return args, number, size


def _snapshot_time(token, scope):
    if token is None:
        return datetime.now().replace(microsecond=0), None
    try:
        saved = json.loads(resolve_public_token(_SCOPE, token, message="外协读取快照已失效。", field="snapshot_ref"))
        if type(saved) is not dict or saved.get("scope") != scope or saved.get("source") != "production":
            raise ValueError("scope changed")
        return factory_time(saved["as_of"]), saved
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "外协读取快照已失效，请明确刷新；未自动换范围。") from exc


def _read(kind, ref=None):
    args, number, size = _arguments(kind)
    token = args.pop("snapshot_ref", None)
    scope = {"kind": kind, "outsourcing_ref": ref, "size": size, **args}
    now, saved = _snapshot_time(token, scope)
    reader = WorkbenchOutsourcingService(g.db)
    with reader.read_snapshot():
        if kind == "targets":
            data = reader.targets(number=number, size=size, **args)
        elif kind == "receipts":
            data = reader.receipts(number=number, size=size, as_of=now, **args)
        elif kind == "history":
            data = reader.history(ref, number=number, size=size, as_of=now)
        else:
            if number != 1:
                reject("单条登记没有翻页。", status=400)
            data = reader.detail(ref, as_of=now)
        fingerprint = data.pop("fingerprint")
        if saved is not None and saved.get("fingerprint") != fingerprint:
            reject("外协来源或登记已变化，请刷新后核对；未静默使用新数据。", "snapshot_stale", 409)
        if token is None:
            token = issue_public_token(_SCOPE, canonical_json({"scope": scope, "source": "production", "fingerprint": fingerprint,
                                       "as_of": now.isoformat(timespec="seconds")}), ttl_seconds=900)
    response = query_success(bounded(data), {"snapshot_ref": token, "as_of": now.isoformat(timespec="seconds")})
    response.headers["Cache-Control"] = "no-store"
    return response


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


def _body(confirm):
    if request.args or not request.is_json:
        reject("外协登记须提交 JSON 请求。", status=400)
    body = request.get_json()
    fields = {"input", "request_key", "write_token"} if confirm else {"input"}
    if type(body) is not dict or set(body) != fields or type(body["input"]) is not dict:
        reject("外协登记请求合同不完整或包含未知字段。", status=400)
    return body


@api_endpoint
def outsourcing_preview():
    body = _body(False)
    service = WorkbenchOutsourcingCommandService(g.db, context_factory=issue_write_context)
    result = service.preview(body["input"])
    response = query_success(result, {"as_of": service.reader.now().isoformat(timespec="seconds"), "snapshot_ref": None})
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def outsourcing_confirm():
    body = _body(True)
    g.workbench_request_key = body["request_key"]
    service = WorkbenchOutsourcingCommandService(g.db)
    result = service.execute(body["input"], request_key=body["request_key"],
        validate_context=lambda subject, action, snapshot: validate_write_context(body["write_token"], subject, action, snapshot))
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_outsourcing_routes(bp):
    root = "/api/workbench/v1/outsourcing"
    for path, view, method in (("/targets", outsourcing_targets, "GET"), ("/receipts", outsourcing_receipts, "GET"),
        ("/receipts/<outsourcing_ref>", outsourcing_detail, "GET"), ("/receipts/<outsourcing_ref>/history", outsourcing_history, "GET"),
        ("/receipts/preview", outsourcing_preview, "POST"), ("/receipts", outsourcing_confirm, "POST")):
        bp.add_url_rule(root + path, view_func=view, methods=[method])
