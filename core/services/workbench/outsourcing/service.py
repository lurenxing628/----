"""SELECT-only outsourcing catalog and original-instance history.

Judgement over WorkbenchOutsourcingRepository facts (missing schema, unknown
receipt, row caps) lives here; the repository only reads.
"""

from contextlib import contextmanager
from typing import Any, Dict, Literal, Optional, Tuple, TypedDict, cast

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_outsourcing import (
    MAX_ROWS,
    page_meta,
    pagination,
    reference,
    reject,
)
from core.services.workbench.facts.source_revisions import (
    OUTSOURCING_SOURCE_KEYS,
    read_source_revisions,
)
from data.repositories.workbench_outsourcing_repo import WorkbenchOutsourcingRepository

from .projection import fact, receipt
from .source import AdmittedReceiptSource, WorkbenchOutsourcingSourceService


class CapturedReceiptFacts(TypedDict):
    header: Dict[str, Any]
    latest: Dict[str, Any]


class WorkbenchOutsourcingService:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchOutsourcingRepository(conn)
        self.sources = WorkbenchOutsourcingSourceService(conn)

    # ---- judgement over repository facts ----

    def admitted_receipt(self, ref) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        raw = self.repo.receipt_facts([ref])[ref]
        header = self.header_from_row(raw["header"])
        return header, cast(Dict[str, Any], raw["latest"])

    @staticmethod
    def header_from_row(header: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Admit a receipt header without reading its members again."""
        if header is None:
            reject("外协原登记不存在，未改读其他对象。", "entity_not_found", 404)
        return header

    # ---- snapshots and projections ----

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            yield

    def _bind_revisions(self, bind_snapshot, **extra):
        content = {
            "revisions": read_source_revisions(self.conn, OUTSOURCING_SOURCE_KEYS),
            "clock": self.sources.repo.plan_identity_revision(),
            **extra,
        }
        bind_snapshot(content)
        return content

    def capture_receipts(self) -> Dict[str, CapturedReceiptFacts]:
        count, captured = self.repo.all_receipt_facts(MAX_ROWS)
        if count > MAX_ROWS:
            reject(f"外协登记超过{MAX_ROWS}项，请限定批次。", "query_too_large", 413)
        return cast(Dict[str, CapturedReceiptFacts], captured)

    def entry_from_facts(
        self, header, latest, now, *, sources, projection: Literal["identity", "deferred_scoped"]
    ):
        """Resolve a receipt from header/latest already admitted in the caller's snapshot."""
        source, issues, state = None, [], "current"
        try:
            loaded = sources.load(header["target"], projection=projection)
            source_identity = (
                loaded.identity
                if isinstance(loaded, AdmittedReceiptSource)
                else loaded["identity"]
            )
            if source_identity != header["identity"]:
                state = "identity_drift"
                issues = [
                    {
                        "code": "identity_drift",
                        "message": "原登记的工序或所属批次已变化，请重新核对。",
                    }
                ]
            source = loaded
        except WorkbenchCommandRejected as exc:
            if exc.code not in (
                "identity_missing",
                "identity_drift",
                "entity_not_found",
                "constraint_conflict",
            ):
                raise
            state = "source_unavailable"
            issues = [{"code": exc.code, "message": str(exc)}]
        result = receipt(header, latest, now, source_state=state, issues=issues)
        result["can_preview"] = state == "current"
        if projection == "identity":
            return result, None
        return result, (source if state == "current" else None)

    def detail(self, ref, *, as_of, bind_snapshot):
        reference(ref)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing detail requires a caller-owned snapshot")
        revision = self._bind_revisions(bind_snapshot)["clock"]
        header, latest = self.admitted_receipt(ref)
        item = self.entry_from_facts(
            header,
            latest,
            as_of,
            sources=self.sources.capture([header["target"]], revision=revision),
            projection="identity",
        )[0]
        return {"item": item}

    def history(self, ref, *, number=1, size=20, as_of, bind_snapshot):
        pagination(number, size)
        result = self.detail(ref, as_of=as_of, bind_snapshot=bind_snapshot)
        rows, paging = self.repo.history(ref, number, size)
        result["history"] = {"items": [fact(row) for row in rows], "page": paging}
        return result

    def receipts(
        self, *, batch_ref=None, status="all", number=1, size=20, as_of, bind_snapshot
    ):
        if batch_ref is not None:
            reference(batch_ref)
        if status not in ("all", "awaiting", "overdue", "returned"):
            reject("外协筛选状态无效。", status=400)
        pagination(number, size)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing list requires a caller-owned snapshot")
        as_of_text = as_of.isoformat(timespec="seconds")
        content = self._bind_revisions(bind_snapshot)
        raw_items, total = self.repo.receipt_page(
            batch_ref=batch_ref,
            status=status,
            as_of_text=as_of_text,
            number=number,
            size=size,
        )
        if raw_items:
            sources = self.sources.capture(
                [header["target"] for header, _ in raw_items], revision=content["clock"]
            )
            rows = [
                self.entry_from_facts(
                    header, latest, as_of, sources=sources, projection="identity"
                )[0]
                for header, latest in raw_items
            ]
        else:
            rows = []
        return {
            "items": rows,
            "page": page_meta(number, size, total),
            "as_of": as_of_text,
            "tracking_basis": "manual_receipt_facts",
        }

    def targets(self, *, batch_ref=None, query="", number=1, size=20, bind_snapshot):
        if batch_ref is not None:
            reference(batch_ref)
        if type(query) is not str or len(query) > 200 or "\x00" in query:
            reject("查找内容须为不超过 200 字的文字。", status=400)
        query = query.strip()
        pagination(number, size)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing targets require a caller-owned snapshot")
        content = self._bind_revisions(bind_snapshot, query=query)
        page_rows, total, entities = self.sources.target_page(
            batch_ref, query, number=number, size=size
        )
        if page_rows:
            sources = self.sources.capture(
                [self.sources.target_from_row(row) for row in page_rows],
                entities=entities,
                revision=content["clock"],
            )
            rows = sources.load_target_rows(page_rows)
        else:
            rows = []
        return {
            "items": rows,
            "page": page_meta(number, size, total),
            "grouping_basis": "explicit_receipt_membership",
            "dates_inferred": False,
        }
