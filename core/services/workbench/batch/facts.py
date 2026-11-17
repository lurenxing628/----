"""Raw, SELECT-only facts used by batch projections and transaction guards."""

from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Tuple

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.template_lineage import instance_lineage_facts
from core.services.scheduler.template_lineage_query import TemplateLineageQuery
from core.services.workbench.facts.source_revisions import BATCH_SOURCE_KEYS, read_source_revisions
from data.repositories.workbench_batch_facts_repo import BATCH_FACT_TABLES, WorkbenchBatchFactsRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .execution import load_execution, project_execution_snapshot, protects_execution
from .scope import BatchFactScope


@contextmanager
def read_transaction(conn):
    if conn.in_transaction:
        yield
        return
    with TransactionManager(conn).transaction():
        yield


class BatchFacts:
    def __init__(self, conn, logger=None, *, material_day: str):
        """``material_day`` is the factory-local day this reader counts arrivals up to; every snapshot and
        command scope it opens shares it."""
        self.conn = conn
        self.material_day = material_day
        self.repo = WorkbenchBatchFactsRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.plan_refs = WorkbenchPlanIdentityRepository(conn, logger=logger)

    def read_revisions(self) -> Dict[str, Any]:
        with read_transaction(self.conn):
            return read_source_revisions(self.conn, BATCH_SOURCE_KEYS)

    def load_choices(self):
        with read_transaction(self.conn):
            return self.repo.choice_tables()

    def _populate_bounded_operation_facts(
        self, tables: Dict[str, Any]
    ) -> Tuple[Dict[int, str], Dict[str, Any]]:
        op_ids = [row["id"] for row in tables["BatchOperations"]]
        tables["plan_reference_counts"] = self.repo.plan_reference_counts(op_ids)
        operation_refs = self.plan_refs.get_operation_refs(op_ids)
        execution = load_execution(self.conn, operation_refs.values()) if op_ids else {"facts": {"operations": {}}}
        return operation_refs, execution

    def capture_closure(self, target_refs: Tuple[str, ...], *, revisions: Dict[str, Any]) -> Dict[str, Any]:
        """Capture stage-2 bounded closure for <=100 page refs inside the caller's read transaction."""
        if not target_refs:
            return {
                "tables": {
                    **{table: [] for table in BATCH_FACT_TABLES},
                    "plan_reference_counts": {},
                },
                "operation_refs": {},
                "execution": {"facts": {"operations": {}}},
                "revisions": revisions,
            }
        tables = self.repo.closure_batch_tables(target_refs)
        operation_refs, execution = self._populate_bounded_operation_facts(tables)
        return {
            "tables": tables,
            "operation_refs": operation_refs,
            "execution": execution,
            "revisions": revisions,
        }

    def _capture_in_transaction(
        self,
        scope: BatchFactScope,
        *,
        revisions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if revisions is None:
            revisions = read_source_revisions(self.conn, BATCH_SOURCE_KEYS)
        mode = scope.mode
        if mode in ("single_template", "single_instance", "single_split", "single_choices"):
            if scope.target_ref is None:
                raise ValueError(f"Single-batch mode {mode!r} requires target_ref")
            batch_row = scope.batch(scope.target_ref)
            tables: Dict[str, Any] = self.repo.single_batch_tables(
                batch_row,
                scope.target_ref,
                include_template=(mode == "single_template"),
                include_batch_codes=(mode == "single_split"),
                all_parts=(mode == "single_choices"),
                include_instance_relations=(mode != "single_choices"),
            )
            op_ids = [row["id"] for row in tables["BatchOperations"]]
            tables["plan_reference_counts"] = (
                {} if mode == "single_choices" else self.repo.plan_reference_counts(op_ids)
            )
            operation_refs = self.plan_refs.get_operation_refs(op_ids)
            if mode == "single_split":
                tables["template_lineage_capture"] = TemplateLineageQuery.capture_partial_facts(
                    self.conn,
                    list(operation_refs.values()),
                    current_by_ref=instance_lineage_facts(tables, operation_refs),
                )
            execution = None if mode == "single_choices" else load_execution(self.conn, operation_refs.values())
        elif mode == "import_preview":
            if scope.query_filter is None:
                raise ValueError("Mode 'import_preview' requires query_filter")
            tables = self.repo.import_preview_tables(
                scope.query_filter["batch_codes"],
                scope.query_filter["part_nos"],
            )
            operation_refs, execution = self._populate_bounded_operation_facts(tables)
        elif mode == "batch_refs":
            if scope.target_refs is None:
                raise ValueError("Mode 'batch_refs' requires target_refs")
            tables = {
                **{table: [] for table in BATCH_FACT_TABLES},
                **self.repo.scoped_entity_tables(scope.target_refs),
                "plan_reference_counts": {},
            }
            operation_refs = {}
            execution = None
        elif scope.target_refs is not None:
            tables = self.repo.closure_batch_tables(
                scope.target_refs, include_batch_codes=(mode == "batch_copy")
            )
            operation_refs, execution = self._populate_bounded_operation_facts(tables)
        else:
            tables = self.repo.whole_tables()
            tables["plan_reference_counts"] = self.repo.plan_reference_counts()
            operation_refs = self.plan_refs.get_operation_refs(row["id"] for row in tables["BatchOperations"])
            execution = load_execution(self.conn, operation_refs.values())
        return {
            "tables": tables,
            "operation_refs": operation_refs,
            "execution": execution,
            "revisions": revisions,
        }

    @staticmethod
    def project_captured(raw: Dict[str, Any], *, material_day: str) -> Dict[str, Any]:
        facts: Dict[str, Any] = {
            **raw["tables"],
            "operation_refs": raw["operation_refs"],
            "revisions": raw["revisions"],
            "material_day": material_day,
        }
        if raw["execution"] is not None:
            facts["execution"] = project_execution_snapshot(raw["execution"])
        return facts

    def load_for_scope(self, scope: BatchFactScope) -> Dict[str, Any]:
        with read_transaction(self.conn):
            revisions = (
                scope.revisions
                if scope.revisions is not None
                and scope.command
                and scope.stamp is not None
                and self.conn.in_transaction
                and self.conn.total_changes == scope.stamp
                else None
            )
            raw = self._capture_in_transaction(scope, revisions=revisions)
        facts = self.project_captured(raw, material_day=scope.material_day)
        scope.facts = facts
        scope.revisions = facts["revisions"]
        if scope.command and self.conn.in_transaction:
            scope.stamp = self.conn.total_changes
        return facts

    @contextmanager
    def detached_read_snapshot(
        self,
        *,
        bind: Optional[Callable[[str], Any]] = None,
        mode: str = "collection",
        target_ref: Optional[str] = None,
        target_refs: Optional[Tuple[str, ...]] = None,
        query_filter: Optional[Mapping[str, Any]] = None,
    ) -> Iterator[BatchFactScope]:
        """Keep one materialized snapshot while projection runs without a DB lock.

        An existing caller transaction is never committed or released here.
        """
        day = self.material_day
        with read_transaction(self.conn):
            revisions = read_source_revisions(self.conn, BATCH_SOURCE_KEYS)
            fingerprint = content_text(["batch-facts-v3", revisions, day])
            if bind is not None:
                bind(fingerprint)
            scope = BatchFactScope(
                self,
                revisions=revisions,
                mode=mode,
                target_ref=target_ref,
                target_refs=target_refs,
                query_filter=query_filter,
            )
            raw = self._capture_in_transaction(scope, revisions=revisions)
        scope.facts = self.project_captured(raw, material_day=day)
        try:
            yield scope
        finally:
            scope.clear()

    @contextmanager
    def command_snapshot(
        self,
        *,
        mode: str = "collection",
        target_ref: Optional[str] = None,
        target_refs: Optional[Tuple[str, ...]] = None,
    ) -> Iterator[BatchFactScope]:
        """Let one write command reuse the facts its guard loaded instead of reloading them."""
        scope = BatchFactScope(self, command=True, mode=mode, target_ref=target_ref, target_refs=target_refs)
        try:
            yield scope
        finally:
            scope.clear()


_UNREFERENCED_MESSAGES = {
    "outsourcing": "这个批次已有外协发出或回厂登记，不能删除、重建工序、改数量或更换工序供应商，以免原登记无法继续核对回厂。",
    "protected": "这个批次已经进了计划、试调或现场报工，不能删除、重建工序或改数量。",
}
_DELETE_MESSAGES = {
    **_UNREFERENCED_MESSAGES,
    "quantity_splits": "这个批次有数量拆分记录，需保留原批与子批以核对数量，不能删除。",
    "materials": "这个批次还挂着物料需求，不能直接删除。",
}


def unreferenced_blocker(*, has_outsourcing: bool, is_protected: bool) -> Optional[str]:
    if has_outsourcing:
        return "outsourcing"
    if is_protected:
        return "protected"
    return None


def delete_blocker(
    *,
    has_outsourcing: bool,
    is_protected: bool,
    has_quantity_splits: bool,
    has_materials: bool,
) -> Optional[str]:
    blocker = unreferenced_blocker(has_outsourcing=has_outsourcing, is_protected=is_protected)
    if blocker is not None:
        return blocker
    if has_quantity_splits:
        return "quantity_splits"
    if has_materials:
        return "materials"
    return None


def require_unreferenced(relations):
    """relations 是调用方已按同一份 facts 算好的这一批关联；逐批循环时先 index_relations 一次再传进来。"""
    blocker = unreferenced_blocker(
        has_outsourcing=bool(relations["outsourcing_receipts"]),
        is_protected=relations["protected"],
    )
    if blocker is not None:
        raise WorkbenchCommandRejected("constraint_conflict", _UNREFERENCED_MESSAGES[blocker])


def group_protected(group, batch):
    return bool(group["plan_reference_count"] or group["execution_protected"] or group["outsourcing_receipts"]
                or batch["status"] in ("scheduled", "processing", "completed")
                or any(row["status"] != "pending" for row in group["operations"]))


def require_deletable(relations):
    blocker = delete_blocker(
        has_outsourcing=bool(relations["outsourcing_receipts"]),
        is_protected=relations["protected"],
        has_quantity_splits=bool(relations["quantity_splits"]),
        has_materials=bool(relations["materials"]),
    )
    if blocker is not None:
        raise WorkbenchCommandRejected("constraint_conflict", _DELETE_MESSAGES[blocker])


def _index_outsourcing_receipts(facts, result):
    batch_refs = {row["ref"]: row["entity_key"] for row in facts["WorkbenchEntityRefs"] if row["kind"] == "batch" and row["active"]}
    for receipt in facts["WorkbenchOutsourcingReceipts"]:
        owner = batch_refs.get(receipt["batch_ref"])
        if owner in result:
            result[owner]["outsourcing_receipts"].append(receipt)


def index_relations(facts):
    result = {row["batch_id"]: {"operations": [], "plan_reference_count": 0, "reports": [], "materials": [],
                              "outsourcing_receipts": [], "quantity_splits": [], "execution_protected": False} for row in facts["Batches"]}
    _index_outsourcing_receipts(facts, result)
    for row in facts["BatchQuantitySplits"]:
        for owner in {row["source_batch_id"], row["child_batch_id"]}:
            if owner in result:
                result[owner]["quantity_splits"].append(row)
    projections = facts["execution"]["projections"]
    for row in facts["BatchOperations"]:
        group = result[row["batch_id"]]
        group["operations"].append(row)
        group["plan_reference_count"] += facts["plan_reference_counts"].get(row["id"], 0)
        projected = projections[facts["operation_refs"][row["id"]]]
        group["reports"].extend(projected.reports)
        group["execution_protected"] |= protects_execution(projected)
    for row in facts["BatchMaterials"]:
        if row["batch_id"] in result:
            result[row["batch_id"]]["materials"].append(row)
    for batch in facts["Batches"]:
        group = result[batch["batch_id"]]
        group["protected"] = group_protected(group, batch)
    return result
