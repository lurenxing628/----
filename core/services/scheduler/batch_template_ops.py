from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.models.enums import BatchOperationStatus, BatchPriority, BatchStatus, ReadyStatus, SourceType
from core.services.common.normalize import append_unique_text_messages


def default_template_resolver_factory(svc) -> Callable[..., Any]:
    def _resolver(part_no: str, part_name: str, route_raw: str, no_tx: bool, *, strict_mode: bool = False):
        from core.services.process.part_service import PartService

        part_service = PartService(svc.conn, logger=svc.logger, op_logger=svc.op_logger)
        if no_tx:
            return part_service.upsert_and_parse_no_tx(
                part_no=part_no,
                part_name=part_name,
                route_raw=route_raw,
                strict_mode=strict_mode,
            )
        return part_service.reparse_and_save(part_no=part_no, route_raw=route_raw, strict_mode=strict_mode)

    return _resolver


def invoke_template_resolver(svc, part_no: str, part_name: str, route_raw: str, no_tx: bool, *, strict_mode: bool):
    resolver = svc._template_resolver
    try:
        signature = inspect.signature(resolver)
    except (TypeError, ValueError) as exc:
        if strict_mode:
            raise BusinessError(
                ErrorCode.ROUTE_PARSE_ERROR,
                "当前模板解析器版本过旧，不支持 strict_mode，请升级解析器后重试。",
                details={"reason": "strict_mode_unsupported"},
                cause=exc,
            ) from exc
        return resolver(part_no, part_name, route_raw, no_tx)

    supports_strict_mode = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD or parameter.name == "strict_mode"
        for parameter in signature.parameters.values()
    )
    if supports_strict_mode:
        return resolver(part_no, part_name, route_raw, no_tx, strict_mode=strict_mode)
    if strict_mode:
        raise BusinessError(
            ErrorCode.ROUTE_PARSE_ERROR,
            "当前模板解析器版本过旧，不支持 strict_mode，请升级解析器后重试。",
            details={"reason": "strict_mode_unsupported"},
        )
    return resolver(part_no, part_name, route_raw, no_tx)


def _normalize_source(value: Any) -> str:
    source = ("" if value is None else str(value)).strip().lower()
    if not source:
        return SourceType.INTERNAL.value
    if source in (SourceType.INTERNAL.value, SourceType.EXTERNAL.value):
        return source
    return SourceType.INTERNAL.value


def probe_template_ops_readonly(svc, part_no: str, part) -> Dict[str, Any]:
    template_ops = svc.part_op_repo.list_by_part(part_no, include_deleted=False)
    route_raw = (part.route_raw or "").strip() if getattr(part, "route_raw", None) is not None else ""
    return {
        "has_template_ops": bool(template_ops),
        "route_raw": route_raw,
        "part_name": getattr(part, "part_name", None) or part_no,
    }


def ensure_template_ops_in_tx(
    svc,
    part_no: str,
    part,
    *,
    strict_mode: bool = False,
    probe: Optional[Dict[str, Any]] = None,
):
    template_ops = svc.part_op_repo.list_by_part(part_no, include_deleted=False)
    if template_ops:
        return template_ops

    probe_data = dict(probe or {})
    route_raw = str(probe_data.get("route_raw") or "").strip()
    if not route_raw:
        route_raw = (part.route_raw or "").strip() if getattr(part, "route_raw", None) is not None else ""
    if route_raw:
        try:
            parse_result = invoke_template_resolver(
                svc,
                part_no,
                str(probe_data.get("part_name") or getattr(part, "part_name", None) or part_no),
                route_raw,
                True,
                strict_mode=bool(strict_mode),
            )
        except BusinessError as exc:
            if ((getattr(exc, "details", None) or {}).get("reason")) == "strict_mode_unsupported":
                raise
            raise BusinessError(
                ErrorCode.ROUTE_PARSE_ERROR,
                "该零件尚未生成工序模板，且自动解析失败。请到【工艺管理-工序模板】中检查工艺路线并重新解析。",
                cause=exc,
            ) from exc
        append_unique_text_messages(svc._user_visible_warnings, getattr(parse_result, "warnings", None))
        template_ops = svc.part_op_repo.list_by_part(part_no, include_deleted=False)

    if not template_ops:
        raise BusinessError(
            ErrorCode.ROUTE_PARSE_ERROR,
            "该零件尚未生成工序模板，无法创建批次工序。请先在【工艺管理-工序模板】中解析工艺路线并保存模板。",
        )
    return template_ops


def _ensure_batch_exists_for_template_ops(
    svc,
    *,
    batch_id: str,
    part_no: str,
    part_name: Optional[str],
    quantity: int,
    due_date: Optional[str],
    priority: str,
    ready_status: str,
    ready_date: Optional[str],
    remark: Optional[str],
    rebuild_ops: bool,
) -> None:
    if svc.batch_repo.get(batch_id):
        if rebuild_ops:
            svc.batch_op_repo.delete_by_batch(batch_id)
            return
        raise BusinessError(ErrorCode.BATCH_ALREADY_EXISTS, f"批次号“{batch_id}”已存在，不能重复添加。")

    svc.batch_repo.create(
        {
            "batch_id": batch_id,
            "part_no": part_no,
            "part_name": part_name,
            "quantity": int(quantity),
            "due_date": due_date,
            "priority": priority,
            "ready_status": ready_status,
            "ready_date": svc._normalize_date(ready_date),
            "status": BatchStatus.PENDING.value,
            "remark": remark,
        }
    )


def _build_batch_op_payload(svc, *, batch_id: str, seq: int, tmpl: Any, source: str) -> Dict[str, Any]:
    supplier_id = tmpl.supplier_id if source == SourceType.EXTERNAL.value else None
    return {
        "op_code": f"{batch_id}_{int(seq):02d}",
        "batch_id": batch_id,
        "piece_id": None,
        "seq": int(seq),
        "op_type_id": tmpl.op_type_id,
        "op_type_name": tmpl.op_type_name,
        "source": source,
        "machine_id": None,
        "operator_id": None,
        "supplier_id": supplier_id,
        "setup_hours": float(tmpl.setup_hours or 0.0),
        "unit_hours": float(tmpl.unit_hours or 0.0),
        "ext_days": svc._safe_float(tmpl.ext_days),
        "status": BatchOperationStatus.PENDING.value,
    }


def create_batch_from_template_no_tx(
    svc,
    *,
    batch_id: str,
    part_no: str,
    quantity: int,
    due_date: Optional[str],
    priority: str,
    ready_status: str,
    ready_date: Optional[str],
    remark: Optional[str],
    rebuild_ops: bool = False,
    strict_mode: bool = False,
    template_probe: Optional[Dict[str, Any]] = None,
) -> None:
    bid = svc._normalize_text(batch_id)
    part_no_text = svc._normalize_text(part_no)
    if not bid:
        raise ValidationError("“批次号”不能为空", field="批次号")
    if not part_no_text:
        raise ValidationError("“图号”不能为空", field="图号")
    if quantity is None or int(quantity) <= 0:
        raise ValidationError("“数量”必须大于 0", field="数量")

    priority_text = svc._normalize_text(priority) or BatchPriority.NORMAL.value
    ready_status_text = svc._normalize_text(ready_status) or ReadyStatus.YES.value
    svc._validate_enum(priority_text, (BatchPriority.NORMAL.value, BatchPriority.URGENT.value, BatchPriority.CRITICAL.value), "优先级")
    svc._validate_enum(ready_status_text, (ReadyStatus.YES.value, ReadyStatus.NO.value, ReadyStatus.PARTIAL.value), "齐套")

    part = svc.part_repo.get(part_no_text)
    if not part:
        raise BusinessError(ErrorCode.NOT_FOUND, f"图号“{part_no_text}”不存在，请先在工艺管理中维护零件。")

    template_ops = ensure_template_ops_in_tx(svc, part_no_text, part, strict_mode=bool(strict_mode), probe=template_probe)
    _ensure_batch_exists_for_template_ops(
        svc,
        batch_id=bid,
        part_no=part_no_text,
        part_name=getattr(part, "part_name", None),
        quantity=int(quantity),
        due_date=due_date,
        priority=priority_text,
        ready_status=ready_status_text,
        ready_date=ready_date,
        remark=remark,
        rebuild_ops=bool(rebuild_ops),
    )

    for template in template_ops:
        seq = int(template.seq)
        source = _normalize_source(getattr(template, "source", None))
        svc.batch_op_repo.create(_build_batch_op_payload(svc, batch_id=bid, seq=seq, tmpl=template, source=source))
