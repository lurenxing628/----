"""SELECT-only outsourcing catalog and original-instance history."""

from contextlib import contextmanager
from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_outsourcing import bounded, page, pagination, reference, reject
from data.repositories.workbench_outsourcing_repo import WorkbenchOutsourcingRepository
from data.repositories.workbench_outsourcing_source_repo import WorkbenchOutsourcingSourceRepository

from .outsourcing_projection import fact, receipt


class WorkbenchOutsourcingService:
    def __init__(self, conn, *, clock=None):
        self.conn, self.clock = conn, clock or datetime.now
        self.repo = WorkbenchOutsourcingRepository(conn)
        self.sources = WorkbenchOutsourcingSourceRepository(conn)

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            yield

    def now(self):
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("Outsourcing time must be factory local")
        return now.replace(microsecond=0)

    def _entry(self, ref, now):
        header, latest = self.repo.header(ref), self.repo.latest(ref)
        source, issues, state = None, [], "current"
        try:
            source = self.sources.load(header["target"])
            if source["identity"] != header["identity"]:
                state = "identity_drift"
                issues = [{"code": "identity_drift", "message": "原成员或所属对象已变化；历史保留，不重绑同号对象。"}]
        except WorkbenchCommandRejected as exc:
            if exc.code not in ("identity_missing", "identity_drift", "entity_not_found", "constraint_conflict"):
                raise
            state = "source_unavailable"
            issues = [{"code": exc.code, "message": str(exc)}]
        result = receipt(header, latest, now, source_state=state, issues=issues)
        result["can_preview"] = state == "current"
        snapshot = {"header": header, "latest_fact_ref": latest["fact_ref"], "source": source, "issues": issues}
        return bounded(result), snapshot

    def detail(self, ref, *, as_of=None):
        reference(ref)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing detail requires a caller-owned snapshot")
        item, snapshot = self._entry(ref, as_of or self.now())
        return {"item": item, "fingerprint": input_fingerprint(snapshot)}

    def history(self, ref, *, number=1, size=20, as_of=None):
        pagination(number, size)
        result = self.detail(ref, as_of=as_of)
        rows, paging = self.repo.history(ref, number, size)
        result["history"] = {"items": [fact(row) for row in rows], "page": paging}
        return bounded(result)

    def receipts(self, *, batch_ref=None, status="all", number=1, size=20, as_of=None):
        if batch_ref is not None:
            reference(batch_ref)
        if status not in ("all", "awaiting", "overdue", "returned"):
            reject("外协筛选状态无效。", status=400)
        pagination(number, size)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing list requires a caller-owned snapshot")
        now = as_of or self.now()
        rows, snapshots = [], []
        for ref in self.repo.refs(batch_ref):
            item, snapshot = self._entry(ref, now)
            snapshots.append(snapshot)
            matches = {"all": True, "awaiting": item["awaiting_return"], "overdue": item["overdue"], "returned": not item["awaiting_return"]}
            if matches[status]:
                rows.append(item)
        return bounded({**page(rows, number, size), "fingerprint": input_fingerprint(bounded(snapshots)),
                        "as_of": now.isoformat(timespec="seconds"), "tracking_basis": "manual_receipt_facts"})

    def targets(self, *, batch_ref=None, number=1, size=20):
        if batch_ref is not None:
            reference(batch_ref)
        pagination(number, size)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing targets require a caller-owned snapshot")
        rows = self.sources.targets(batch_ref)
        clock = self.conn.execute("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1").fetchone()[0]
        return bounded({**page(rows, number, size), "fingerprint": input_fingerprint({"rows": rows, "clock": clock}),
                        "grouping_basis": "explicit_receipt_membership", "dates_inferred": False})
