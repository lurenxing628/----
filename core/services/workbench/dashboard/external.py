"""Real shipment summary, independent of generic Dashboard handling and plans.

The separate list/detail/history contract is WorkbenchOutsourcingService's DTO.
No external Dashboard item, mapping DDL, handling command or history is invented.
Risk counts current receipts that are overdue OR awaiting confirmation, once each.
All retained receipts count toward receipt_count; stale sources only produce gaps.
An unregistered operation is unknown, not a dispatched shipment or zero risk.
"""

from core.infrastructure.schema_probe import object_sql_map
from core.infrastructure.workbench_outsourcing_schema import objects
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_dashboard import bounded, payload_size
from core.models.workbench_outsourcing import STATES
from core.models.workbench_outsourcing import bounded as receipt_bounded
from core.models.workbench_outsourcing_input import next_values
from core.services.workbench.outsourcing.projection import values
from core.services.workbench.outsourcing.service import WorkbenchOutsourcingService

from .external_sources import gap, latest_fact, source_gaps, subject
from .facts import source_issue, typed
from .projection import category

COUNTS = ("receipt_count", "current_receipt_count", "awaiting_return_count", "overdue_count",
          "returned_count", "awaiting_confirmation_count", "unregistered_count", "source_gap_count")


def summary(state, issues=None):
    connected = state in ("loaded", "no_data")
    return {**category(state, issues=issues), **dict.fromkeys(COUNTS, 0 if connected else None),
            "kind": "outsourcing_receipts", "tracking_basis": "manual_receipt_facts",
            "handling_supported": False, "handling_count": 0, "closed_count": 0, "evaluation_gaps": [],
            "entry": {"view": "outsourcing", "target": "/api/workbench/v1/outsourcing/receipts", "enabled": connected}}


def _receipts(reader, now, result):
    snapshots, captured = [], {}
    for ref in reader.refs():
        latest = latest_fact(reader, ref)
        captured[ref] = {"latest": latest}
        try:
            if latest["confirmed_state"] not in STATES:
                raise WorkbenchCommandRejected("invalid_input", "外协确认状态无效。")
            next_values(None, values(latest), now)
        except WorkbenchCommandRejected as exc:
            if exc.code != "invalid_input":
                raise
            issues = [source_issue("outsourcing_fact_invalid", "外协登记的时间或状态无效，请核对物流登记。")]
            result["evaluation_gaps"].append(gap(ref, "外协原登记", issues))
            snapshots.append({"latest": latest, "issues": issues})
            continue
        header = reader.header(ref)
        item, snapshot = reader.entry_from_facts(header, receipt_bounded(latest), now)
        captured[ref].update(header=header, receipt=item, snapshot=snapshot)
        snapshots.append({"source": snapshot, "receipt": item})
        if item["source_state"] != "current":
            title = subject(item["target"]["batch"]["business_code"], "外协原登记")
            result["evaluation_gaps"].append(gap(ref, title, item["issues"]))
            continue
        result["current_receipt_count"] += 1
        result["awaiting_return_count"] += int(item["awaiting_return"])
        result["overdue_count"] += int(item["overdue"])
        result["returned_count"] += int(not item["awaiting_return"])
        pending = item["confirmedState"] == "awaiting_confirmation"
        result["awaiting_confirmation_count"] += int(pending)
        result["known_risk_count"] += int(item["overdue"] or pending)
    result["receipt_count"] = len(snapshots)
    return snapshots, captured


def _targets(reader, result):
    entries = reader.sources.load_targets()
    targets = [item for item, source in entries]
    snapshots = []
    for item, source in entries:
        if item["outsourcing_ref"] is not None:
            continue  # Registered membership is evaluated once, at the receipt.
        result["unregistered_count"] += 1
        issues = item["issues"]
        snapshots.append({"target": item, "source": source, "issues": issues})
        if not issues:
            issues = [source_issue("outsourcing_unregistered", "尚未登记外协发出或回厂信息，请补充物流登记。")]
        title = subject(item["label"], "外协工序")
        code = subject(item["business_code"], "")
        if code:
            title += "（" + code + "）"
        detail = gap(item["operation_ref"], title, issues)
        detail["operation"] = {"code": item["business_code"], "name": item["label"]}
        result["evaluation_gaps"].append(detail)
    source_rows = source_gaps(reader.conn)
    for item in source_rows:
        if item["outsourcing_ref"] is None:
            legacy_external = item["source_kind"] == "external"
            if legacy_external:
                issue = source_issue("external_source_noncanonical", "已识别为历史外协工序，但归属未按标准保存，物流登记尚未评估。请到基础资料核对。")
            else:
                issue = source_issue("external_source_unknown", "工序归属未填写或无效，请确认自制或外协。")
            title = subject(item["business_code"], "历史外协工序" if legacy_external else "来源未知工序")
            result["evaluation_gaps"].append(gap(item["operation_ref"], title, [issue]))
    return {"targets": targets, "unregistered_sources": snapshots, "source_gaps": source_rows}


def external(conn, now):
    result, fingerprint, receipts = load_external(conn, now)
    return result, fingerprint


def load_external(conn, now):
    """Capture receipt facts once for the dashboard summary and handling projection."""
    if not conn.in_transaction:
        raise RuntimeError("External dashboard reads require a caller-owned snapshot")
    definitions = objects()
    schema = object_sql_map(conn, definitions)
    reader = WorkbenchOutsourcingService(conn, clock=lambda: now)
    try:
        reader.require_schema()
    except WorkbenchCommandRejected as exc:
        if exc.code != "outsourcing_unavailable":
            raise
        recorded = reader.repo.has_confirm_receipts()
        state = "unavailable" if schema or recorded else "not_connected"
        result = summary(state, [source_issue(exc.code, str(exc))])
        return result, input_fingerprint({"schema": schema, "recorded": recorded, "summary": result}), {}
    result = summary("loaded")
    receipts, captured = _receipts(reader, now, result)
    targets = _targets(reader, result)
    gaps = bounded(result["evaluation_gaps"])
    result["unknown_count"] = len(gaps)
    result["source_gap_count"] = sum(item["code"] != "outsourcing_unregistered" for item in gaps)
    result["assessed_count"] = result["current_receipt_count"]
    result["risk_count"] = None if gaps else result["known_risk_count"]
    if not result["receipt_count"] and not gaps:
        result["state"] = "no_data"
    fingerprint = input_fingerprint(payload_size(typed({"schema": schema, "receipts": receipts,
                                                        "targets": targets, "summary": result})))
    return result, fingerprint, captured
