"""Process actions inside the caller's BEGIN IMMEDIATE and receipt transaction."""

from __future__ import annotations

from dataclasses import dataclass

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_process_commands import normalize_process_input
from data.repositories.external_group_repo import ExternalGroupRepository

from .group_apply import apply_groups, group_changes, prepare_groups
from .group_defaults import apply_default_groups
from .part_actions_facts import checked_process_facts
from .route_apply import affected_group_rows, apply_route, discard_groups, prepare_route, require_group_ack
from .stage_apply import (
    apply_prepared_hours,
    apply_source,
    prepare_hours,
    prepare_source,
    source_catalog,
    source_group_changes,
)


@dataclass
class PreparedProcessChange:
    action: str
    payload: dict
    checked: tuple
    changes: object
    affected: list
    auxiliary: object
    identities: object


class WorkbenchProcessMutationService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger

    @staticmethod
    def normalize(action, input):
        return normalize_process_input(action, input)

    checked_facts = staticmethod(checked_process_facts)

    def _apply_source_changes(self, part_no, prepared, operations, supplier_updates):
        apply_source(self.conn, prepared, operations)
        for group_id, supplier_id in supplier_updates:
            ExternalGroupRepository(self.conn).update(group_id, {"supplier_id": supplier_id})
        by_id = {row["id"]: row for row in operations}
        new_external = {by_id[change[3]]["seq"] for change in prepared if change[0] == "external"
            and (by_id[change[3]]["source"] != "external" or by_id[change[3]]["op_type_id"] != change[1]
                 or by_id[change[3]]["supplier_id"] is None)
            and by_id[change[3]]["ext_group_id"] is None}
        grouped = apply_default_groups(self.conn, part_no, new_external)
        return bool(prepared or supplier_updates or grouped)

    def apply(self, action, input, identity):
        if not self.conn.in_transaction:
            raise RuntimeError("工艺动作必须在外层BEGIN IMMEDIATE命令事务内执行。")
        if not isinstance(identity, WorkbenchEntityIdentity) or identity.kind != "part":
            raise WorkbenchCommandRejected("invalid_input", "请先选定零件再操作。", 400)
        payload = self.normalize(action, input)
        from .queries import WorkbenchProcessQueryService

        reader = WorkbenchProcessQueryService(self.conn, self.logger)
        with reader.read_snapshot():
            current = reader.resolve(identity.ref)
            if current != identity:
                raise WorkbenchCommandRejected("stale_write", "零件资料已经变了。请刷新后重新核对。")
            facts = reader.facts()
            checked = self.checked_facts(current, facts)
            prepared = self.prepare_checked(action, payload, checked, facts=facts)
        return self.apply_prepared(prepared)

    def _identities(self, facts):
        return {row["ref"]: WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"],
                row["revision"], bool(row["active"])) for row in facts["identities"]}

    def prepare_checked(self, action, payload, checked, *, facts):
        """Own the actual change prepared from this command's current facts."""
        prepared = self.prepare_review(action, payload, checked, facts=facts)
        if action in ("route_confirm", "source_confirm"):
            require_group_ack(payload, prepared.affected)
        return prepared

    def prepare_review(self, action, payload, checked, *, facts):
        """The review projects the same domain change applied on confirmation."""
        _, part, operations, groups, workflow = checked
        identities = self._identities(facts)
        stage = action[:-len("_confirm")]
        if stage != "route":
            previous = "route" if stage in ("source", "groups") else "source"
            if workflow[previous]["state"] != "confirmed":
                raise WorkbenchCommandRejected("stage_not_ready", "前置阶段尚未确认或已变化，请先重新核对。")
        if stage == "groups":
            catalog = source_catalog(self.conn, self.logger, facts)
            changes, affected = prepare_groups(payload, operations, groups, identities, catalog=catalog)
            names = {key: row["name"] for key, row in catalog[1].items()}
            auxiliary = group_changes(changes, affected, operations, names=names)
        elif stage == "hours":
            confirmations = {code: state["operations"] for code, state in facts["workflow"].items()}
            changes = prepare_hours(self.conn, payload, operations, groups, confirmations=confirmations)
            affected, auxiliary = [], None
        elif stage == "route":
            changes, sequences = prepare_route(self.conn, self.logger, payload, operations, facts=facts)
            affected, auxiliary = affected_group_rows(groups, operations, sequences), None
        else:
            changes, _ = prepare_source(payload, operations, identities,
                                        catalog=source_catalog(self.conn, self.logger, facts))
            affected, auxiliary = source_group_changes(changes, operations, groups)
        return PreparedProcessChange(action, payload, checked, changes, affected, auxiliary, identities)

    def apply_prepared(self, prepared):
        """Apply the held change directly inside the command's write lock."""
        if not self.conn.in_transaction:
            raise RuntimeError("工艺动作必须在外层BEGIN IMMEDIATE命令事务内执行。")
        from core.services.process.workflow_state import record_confirmation

        identity, part, operations, groups, workflow = prepared.checked
        stage = prepared.action[:-len("_confirm")]
        if stage == "groups":
            changed = apply_groups(self.conn, part["part_no"], prepared.changes, prepared.affected, operations,
                                   changes=prepared.auxiliary)
            if changed and workflow["source"]["state"] == "confirmed":
                record_confirmation(self.conn, part["part_no"], "source")
            return WorkbenchCommandOutcome("committed" if changed else "unchanged", {
                "entity_ref": identity.ref, "business_code": part["part_no"], "stage": "groups"})
        if stage == "hours":
            changed = apply_prepared_hours(self.conn, prepared.changes)
        else:
            discard_groups(self.conn, part["part_no"], prepared.affected)
            if stage == "route":
                changed = apply_route(self.conn, part, operations, prepared.changes, prepared.identities) or bool(prepared.affected)
            else:
                changed = self._apply_source_changes(part["part_no"], prepared.changes, operations, prepared.auxiliary) or bool(prepared.affected)
        result = "unchanged" if not changed and workflow[stage]["state"] == "confirmed" else "committed"
        # Route confirmation also retires records for removed operations.
        if result != "unchanged" or stage == "route":
            record_confirmation(self.conn, part["part_no"], stage)
        return WorkbenchCommandOutcome(result, {"entity_ref": identity.ref,
                                                "business_code": part["part_no"], "stage": stage})
