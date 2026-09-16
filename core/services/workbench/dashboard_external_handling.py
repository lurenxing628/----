"""Migrate prototype external disposition without changing DO's risk summary."""

from core.models.workbench_dashboard import bounded
from data.repositories.workbench_dashboard_external_repo import WorkbenchDashboardExternalRepository

from .dashboard_external_sources import latest_fact, subject
from .outsourcing import WorkbenchOutsourcingService


def _source(header):
    return {**header["origin"], "kind": "outsourcing_receipt", "target_kind": header["target_kind"],
            "outsourcing_ref": header["outsourcing_ref"], "time_basis": "factory_local", "tracking_basis": "manual_receipt_facts"}


def _navigation(ref, current):
    return [{"view": "outsourcing", "context": {"outsourcing_ref": ref}, "enabled": current,
             "query_target": "/api/workbench/v1/outsourcing/receipts/" + ref,
             "reason": None if current else "外协来源暂时无法核对，请刷新重试。"}]


def _observation(reader, ref, now, gap):
    header = reader.repo.header(ref)
    source = _source(header)
    if gap:
        risk = {"active": None, "code": gap["code"], "message": gap["message"]}
        facts = {"header": header, "latest": latest_fact(reader, ref), "gap": gap}
        current, awaiting = False, False
    else:
        receipt, snapshot = reader._entry(ref, now)
        current, awaiting = receipt["source_state"] == "current", receipt["awaiting_return"]
        active = receipt["overdue"] or receipt["confirmedState"] == "awaiting_confirmation"
        risk = {"active": active if current else None,
                "code": "outsourcing_overdue" if receipt["overdue"] else "outsourcing_awaiting_confirmation" if active else "outsourcing_tracked",
                "message": "外协超过真实登记的计划回厂时点。" if receipt["overdue"] else "外协仍待人工确认。" if active else "当前登记未发现超时或待确认风险。"}
        source["receipt"] = receipt
        facts = {"receipt": receipt, "snapshot": snapshot, "latest": latest_fact(reader, ref)}
    label = subject(header["origin"]["batch"]["business_code"], "外协原登记")
    operations = " / ".join(subject(row["business_code"], "外协工序") for row in header["origin"]["operations"])
    item = {"category": "external", "anchor_ref": ref, "subject": label + " · " + operations,
            "source": source, "risk": risk, "_facts": facts, "navigation": _navigation(ref, current),
            "source_state": "current" if current else "not_currently_evaluated"}
    return item, current and awaiting


class DashboardExternalHandling:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchDashboardExternalRepository(conn)

    def read(self, summary, now):
        state = self.repo.schema_state()
        if state == "not_connected":
            return [], {}, {}  # v30 remains explicitly unsupported until v31 installs the extension.
        if state != "loaded" or summary["state"] not in ("loaded", "no_data"):
            summary.update(handling_supported=False, handling_count=None, closed_count=None,
                           handling_state="unavailable", handling_issues=[{"code": "dashboard_external_unavailable",
                           "message": "外协处置记录不完整，请核对登记来源和处置历史。"}])
            return [], {}, {"state": "unavailable"}
        reader = WorkbenchOutsourcingService(self.conn, clock=lambda: now)
        refs = reader.repo.refs()
        mappings, stored = self.repo.receipt_mappings(refs), self.repo.stored()
        gaps = {row["source_ref"]: row for row in summary["evaluation_gaps"]}
        observations = []
        for ref in refs:
            identity = mappings[ref]
            item, awaiting = _observation(reader, ref, now, gaps.get(ref))
            saved = stored.get(identity["item_ref"])
            if awaiting or saved:
                observations.append((dict(item, item_ref=identity["item_ref"]), saved, identity))
        summary.update(handling_supported=True, handling_count=len(stored),
                       closed_count=sum(row["handling"]["status"] == "closed" for row in stored.values()))
        return bounded(observations), stored, {"mappings": mappings, "state": state}
