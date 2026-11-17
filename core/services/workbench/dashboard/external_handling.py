"""External disposition handling on the unified dashboard ledger."""

from core.models.workbench_dashboard import bounded
from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository

from .external_sources import subject
from .policy import read_receipt_mappings


def _source(header):
    return {
        **header["origin"],
        "kind": "outsourcing_receipt",
        "target_kind": header["target_kind"],
        "outsourcing_ref": header["outsourcing_ref"],
        "time_basis": "factory_local",
        "tracking_basis": "manual_receipt_facts",
    }


def _navigation(ref, current):
    return [
        {
            "view": "outsourcing",
            "context": {"outsourcing_ref": ref} if current else {},
            "enabled": current,
            "reason": None if current else "外协来源暂时无法核对，请刷新重试。",
        }
    ]


def _observation(ref, captured, gap):
    header = captured["header"]
    source = _source(header)
    if gap:
        risk = {"active": None, "code": gap["code"], "message": gap["message"]}
        source_revision = {
            "latest_fact_ref": captured["latest"]["fact_ref"],
            "target": header["target"],
            "gap_code": gap["code"],
        }
        current = False
    else:
        receipt = captured["receipt"]
        current = True
        active = receipt["overdue"] or receipt["confirmedState"] == "awaiting_confirmation"
        risk = {
            "active": active,
            "code": (
                "outsourcing_overdue"
                if receipt["overdue"]
                else "outsourcing_awaiting_confirmation"
                if active
                else "outsourcing_tracked"
            ),
            "message": (
                "外协超过真实登记的计划回厂时点。"
                if receipt["overdue"]
                else "外协仍待人工确认。"
                if active
                else "当前登记未发现超时或待确认风险。"
            ),
        }
        source["receipt"] = receipt
        # Source identities and revisions already express this receipt's dependencies;
        # the global plan clock must not expire it when another source changes.
        scoped = captured["admitted_source"].to_scoped_source()
        source_revision = {
            "latest_fact_ref": captured["latest"]["fact_ref"],
            **scoped,
        }
    label = subject(header["origin"]["batch"]["business_code"], "外协原登记")
    operations = " / ".join(subject(row["business_code"], "外协工序") for row in header["origin"]["operations"])
    return {
        "category": "external",
        "anchor_ref": ref,
        "subject": label + " · " + operations,
        "source": source,
        "risk": risk,
        "_guard": {"source_revision": source_revision},
        "navigation": _navigation(ref, current),
        "source_state": "current" if current else "not_currently_evaluated",
    }


def handling_counts(rows):
    """One category's handling counts over its stored dashboard items."""
    return {"handling_count": len(rows), "closed_count": sum(row["handling"]["status"] == "closed" for row in rows)}


def project_external_item(item_ref, outsourcing_ref, entry, gap_row, saved):
    awaiting = not gap_row and entry["receipt"]["source_state"] == "current" and entry["receipt"]["awaiting_return"]
    if not (awaiting or saved):
        return None
    return dict(_observation(outsourcing_ref, entry, gap_row), item_ref=item_ref)


class DashboardExternalHandling:
    def __init__(self, conn):
        self.repo = WorkbenchDashboardRepository(conn)

    def read(self, summary, receipts, stored):
        """The receipts' handled observations and the external category's handling counts."""
        refs = list(receipts)
        mappings = read_receipt_mappings(self.repo, refs)
        gaps = {row["source_ref"]: row for row in summary["evaluation_gaps"]}
        observations = []
        for ref in refs:
            mapped = mappings[ref]
            saved = stored.get(mapped["item_ref"])
            projected = project_external_item(mapped["item_ref"], ref, receipts[ref], gaps.get(ref), saved)
            if projected is not None:
                observations.append((projected, saved, mapped))
        handling = handling_counts([row for row in stored.values() if row["category"] == "external"])
        return bounded(observations), handling
