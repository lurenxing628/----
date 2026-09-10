"""Read-only legacy identity facts; no HTTP imports, raw query parsing or repair."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from core.infrastructure.transaction import TransactionManager
from core.models.schedule_plan_role import VALID_PLAN_ROLES
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.services.common.plan_query import SchedulePlanQueryService
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

_ENTITIES = {"machine": ("Machines", "machine_id"), "operator": ("Operators", "operator_id"),
             "op_type": ("OpTypes", "op_type_id"), "part": ("Parts", "part_no"),
             "supplier": ("Suppliers", "supplier_id"), "batch": ("Batches", "batch_id")}


class LegacyNavigationSourceMissing(LookupError):
    """The explicitly selected source record does not exist."""


@dataclass(frozen=True)
class LegacyEntityReference:
    entity_ref: Optional[str]
    category: Optional[str] = None


@dataclass(frozen=True)
class LegacyPlanBinding:
    locator: WorkbenchPlanLocator
    plan_ref: str
    fallback: bool


class LegacyNavigationQueries:
    def __init__(self, conn):
        self.conn = conn
        self.history = ScheduleHistoryRepository(conn)
        self.plans = SchedulePlanQueryService(conn)
        self.references = WorkbenchPlanIdentityRepository(conn)
        self.entities = WorkbenchIdentityRepository(conn)

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            yield self

    def _require_snapshot(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Legacy identity queries require a caller-owned read snapshot.")

    @staticmethod
    def _version(version):
        if type(version) is not int or version <= 0:
            raise ValueError("Legacy plan version must be an explicit positive integer.")

    def latest_version(self):
        self._require_snapshot()
        return self.history.get_latest_version()

    def version_exists(self, version):
        self._require_snapshot()
        self._version(version)
        return self.history.get_by_version(version) is not None

    def bind_plan(self, version: int, role: str, scenario_id: Optional[str]):
        self._require_snapshot()
        self._version(version)
        if type(role) is not str or role not in VALID_PLAN_ROLES:
            raise ValueError("Legacy role must be a parsed plan role.")
        if scenario_id is not None and (type(scenario_id) is not str or not scenario_id or "\x00" in scenario_id):
            raise ValueError("Legacy scenario must be a parsed nonempty identifier.")
        if not self.version_exists(version):
            raise LegacyNavigationSourceMissing("Selected plan history no longer exists.")
        resolution = self.plans.resolve_plan_view(version, role, scenario_id)
        locator = WorkbenchPlanLocator(version, resolution.requested_role, scenario_id)
        if resolution.requested_role != resolution.selected_role:
            return LegacyPlanBinding(locator, "", True)
        ref = self.references.get_plan_ref(locator)
        if self.references.resolve_plan(ref) != locator:
            raise WorkbenchPlanReferenceError("plan_binding_invalid", "永久计划身份绑定不一致。")
        return LegacyPlanBinding(locator, ref, False)

    def entity(self, kind: str, business_key: str):
        self._require_snapshot()
        if type(kind) is not str or kind not in _ENTITIES:
            raise ValueError("Unsupported legacy entity kind.")
        if type(business_key) is not str or not business_key or "\x00" in business_key:
            raise ValueError("Legacy detail requires its exact business key.")
        table, key = _ENTITIES[kind]
        row = self.conn.execute("SELECT * FROM " + table + " WHERE " + key + " = ?", (business_key,)).fetchone()
        if row is None:
            raise LegacyNavigationSourceMissing("Selected detail record no longer exists.")
        identity = self.entities.find_active(kind, business_key)
        if identity is not None and self.entities.get(identity.ref) != identity:
            raise WorkbenchPlanReferenceError("identity_missing", "原对象永久身份反查不一致。")
        return LegacyEntityReference(identity.ref if identity else None, row["category"] if kind == "op_type" else None)

    def get_plan_time_span(self, version: int, plan_role: Optional[str] = None):
        self._require_snapshot()
        self._version(version)
        return self.plans.get_plan_time_span(version, plan_role)

    def get_plan_time_span_for_view(self, version: int, plan_role: Optional[str], scenario_id: str):
        self._require_snapshot()
        self._version(version)
        return self.plans.get_plan_time_span_for_view(version, plan_role, scenario_id)
