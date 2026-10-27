"""Process actions inside the caller's BEGIN IMMEDIATE and receipt transaction."""

from __future__ import annotations

from dataclasses import dataclass

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_process_commands import normalize_process_input
from data.repositories.external_group_repo import ExternalGroupRepository

from .group_apply import apply_groups, group_changes, prepare_groups
from .group_defaults import apply_default_groups, default_suppliers
from .part_actions_facts import checked_process_facts
from .route_apply import affected_group_rows, apply_route, discard_groups, prepare_route, require_group_ack
from .route_facts import ProcessRouteFacts
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
    checked: tuple
    changes: object
    affected: list
    auxiliary: object
    identities: object
    references: dict


class WorkbenchProcessMutationService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self._route_preview = None

    def normalize(self, action, input):
        route_out = [] if action == "route_confirm" else None
        normalized = normalize_process_input(action, input, route_out=route_out)
        self._route_preview = (normalized["route"], route_out[0]) if route_out else None
        return normalized

    checked_facts = staticmethod(checked_process_facts)

    def _apply_source_changes(self, part_no, prepared, operations, supplier_updates, *, default_catalog_reader):
        apply_source(self.conn, prepared, operations)
        for group_id, supplier_id in supplier_updates:
            ExternalGroupRepository(self.conn).update(group_id, {"supplier_id": supplier_id})
        by_id = {row["id"]: row for row in operations}
        new_external = {by_id[change[3]]["seq"] for change in prepared if change[0] == "external"
            and (by_id[change[3]]["source"] != "external" or by_id[change[3]]["op_type_id"] != change[1]
                 or by_id[change[3]]["supplier_id"] is None)
            and by_id[change[3]]["ext_group_id"] is None}
        grouped = apply_default_groups(self.conn, part_no, new_external, catalog_reader=default_catalog_reader)
        return bool(prepared or supplier_updates or grouped)

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
        stage = action[:-len("_confirm")]
        if stage == "route":
            route_facts = ProcessRouteFacts(facts)
            identities = route_facts.identities
        else:
            previous = "route" if stage in ("source", "groups") else "source"
            if workflow[previous]["state"] != "confirmed":
                raise WorkbenchCommandRejected("stage_not_ready", "前置阶段尚未确认或已变化，请先重新核对。")
            identities = None if stage == "hours" else self._identities(facts)
        if stage == "groups":
            catalog = source_catalog(facts["references"])
            changes, affected = prepare_groups(payload, operations, groups, identities, catalog=catalog)
            names = {key: row["name"] for key, row in catalog[1].items()}
            auxiliary = group_changes(changes, affected, operations, names=names)
        elif stage == "hours":
            confirmations = {code: state["operations"] for code, state in facts["workflow"].items()}
            changes = prepare_hours(payload, operations, groups, confirmations=confirmations)
            affected, auxiliary = [], None
        elif stage == "route":
            route_normalized = (self._route_preview[1]
                                if self._route_preview is not None and self._route_preview[0] is payload["route"]
                                else None)
            changes, sequences = prepare_route(self.conn, self.logger, payload, operations,
                                               facts=route_facts, normalized=route_normalized)
            affected, auxiliary = affected_group_rows(groups, operations, sequences), None
        else:
            changes = prepare_source(payload, operations, identities,
                                     catalog=source_catalog(facts["references"]))
            affected, auxiliary = source_group_changes(changes, operations, groups)
        return PreparedProcessChange(action, checked, changes, affected, auxiliary, identities, facts["references"])

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
            def default_catalog():
                return default_suppliers(prepared.references)

            discard_groups(self.conn, part["part_no"], prepared.affected)
            if stage == "route":
                changed = apply_route(self.conn, part, operations, prepared.changes, prepared.identities,
                                      default_catalog_reader=default_catalog) or bool(prepared.affected)
            else:
                changed = self._apply_source_changes(part["part_no"], prepared.changes, operations, prepared.auxiliary,
                                                     default_catalog_reader=default_catalog) or bool(prepared.affected)
        result = "unchanged" if not changed and workflow[stage]["state"] == "confirmed" else "committed"
        # Route confirmation also retires records for removed operations.
        if result != "unchanged" or stage == "route":
            record_confirmation(self.conn, part["part_no"], stage)
        return WorkbenchCommandOutcome(result, {"entity_ref": identity.ref,
                                                "business_code": part["part_no"], "stage": stage})
