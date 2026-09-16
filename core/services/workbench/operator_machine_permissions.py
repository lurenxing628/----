"""Preview and atomically replace one operator's explicit machine permissions."""

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_action import ResourceActionPreview, check_resource_preview, resource_refs
from core.services.personnel.operator_machine_service import OperatorMachineService

from .resource_states import WorkbenchResourceStateService

OPERATION = "operator.machine_permissions"


def permission_rows(state):
    machines = {item["record"]["machine_id"]: item for item in state["authorized_machines"]}
    return [{"machine_ref": machines[row["machine_id"]]["identity"]["ref"],
             "business_code": row["machine_id"], "label": machines[row["machine_id"]]["record"]["name"],
             "skill_level": row["skill_level"], "is_primary": row["is_primary"]}
            for row in state["machine_authorizations"]]


def _row_result(old, target):
    return "new" if old is None else "delete" if target is None else "unchanged" if old == target else "update"


def _field_changes(old, target):
    return {key: [old.get(key) if old else None, target.get(key) if target else None]
            for key in ("skill_level", "is_primary")
            if (old or {}).get(key) != (target or {}).get(key)}


def _permission_row(number, ref, machine, previous, target):
    old = {key: previous[key] for key in ("machine_ref", "skill_level", "is_primary")} if previous else None
    return {"row": number, "entity_ref": ref, "business_code": machine["record"]["machine_id"],
            "label": machine["record"]["name"], "result": _row_result(old, target), "before": old, "after": target,
            "changes": _field_changes(old, target), "errors": []}


class WorkbenchOperatorMachinePermissions:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.state = WorkbenchResourceStateService(conn, logger)
        self.domain = OperatorMachineService(conn, logger=logger)
        self.tx = TransactionManager(conn)

    def preview(self, operator_ref, permissions):
        with self.tx.transaction():
            identity, raw = self.state.by_ref("operator", operator_ref)
            if raw["operator_id"] != raw["operator_id"].strip():
                raise WorkbenchCommandRejected("constraint_conflict", "工号前后含空格，请先修正工号。")
            before = self.state.snapshot(identity)
            old_rows = {row["machine_ref"]: row for row in permission_rows(before)}
            requested = self._normalize(permissions, old_rows)
            requested_by_ref = {row["machine_ref"]: row for row in requested}
            machines = self._machine_snapshots(sorted(set(old_rows) | set(requested_by_ref)))
            rows = [_permission_row(number, ref, machines[ref], old_rows.get(ref), requested_by_ref.get(ref))
                    for number, ref in enumerate(sorted(machines), 1)]
            # The full operator and machine facts fence rename/recreation, skill changes and hidden links.
            request = {"operator_ref": operator_ref, "machine_permissions": requested,
                       "expected_operator": before, "expected_machines": machines}
            return ResourceActionPreview.build(OPERATION, request, rows)

    def _machine_snapshots(self, refs):
        machines = {}
        for ref in refs:
            machine, _ = self.state.by_ref("machine", ref)
            if machine.entity_key != machine.entity_key.strip():
                raise WorkbenchCommandRejected("constraint_conflict", "设备编号前后含空格，请先修正设备编号。")
            machines[ref] = self.state.snapshot(machine)
        return machines

    def _normalize(self, permissions, old):
        if type(permissions) is not list:
            raise ValidationError("可操作设备必须是完整的关联列表。", field="machine_permissions")
        if any(type(row) is not dict or set(row) != {"machine_ref", "skill_level", "is_primary"} for row in permissions):
            raise ValidationError("每台设备需包含设备编号、技能等级和主操标记。", field="machine_permissions")
        resource_refs([row["machine_ref"] for row in permissions], allow_empty=True)
        result = []
        for row in permissions:
            previous = old.get(row["machine_ref"], {})
            for key, values in (("skill_level", ("beginner", "normal", "expert")), ("is_primary", ("yes", "no"))):
                if row[key] not in values and (key not in previous or row[key] != previous[key]):
                    raise ValidationError("请选择有效的技能等级和主操标记。", field="machine_permissions")
            result.append(dict(row))
        if sum(self.domain._normalize_yes_no_stored(row["is_primary"]) == "yes" for row in result) > 1:
            raise ValidationError("同一人员只能设置一台主操设备。", field="machine_permissions")
        return sorted(result, key=lambda row: row["machine_ref"])

    def confirm(self, preview):
        if not self.conn.in_transaction:
            raise RuntimeError("设备授权保存必须由工作台命令事务负责。")
        request = preview.as_dict()["request"]
        try:
            current = self.preview(request["operator_ref"], request["machine_permissions"])
        except (ValidationError, WorkbenchCommandRejected) as exc:
            raise WorkbenchCommandRejected("stale_write", "人员、设备或关联已变化，请重新预检。") from exc
        check_resource_preview(preview, current)
        body = current.as_dict()
        code = body["request"]["expected_operator"]["record"]["operator_id"]
        rows = body["rows"]
        for row in rows:
            if row["result"] == "delete":
                self.domain.remove_link(code, row["business_code"])
        # Remove the old primary first; the final set has at most one primary.
        changed = [row for row in rows if row["result"] in ("new", "update")]
        changed.sort(key=lambda row: self.domain._normalize_yes_no_stored(row["after"]["is_primary"]) == "yes")
        for row in changed:
            target = row["after"]
            values = {key: target[key] for key in ("skill_level", "is_primary")}
            if row["result"] == "new":
                self.domain.add_link(code, row["business_code"], **values, preserve_unchanged=True)
            else:
                self.domain.update_link_fields(code, row["business_code"], **values, preserve_unchanged=True)
        count = sum(row["result"] != "unchanged" for row in rows)
        return WorkbenchCommandOutcome("committed" if count else "unchanged",
                                       {"entity_ref": request["operator_ref"], "business_code": code,
                                        "permission_count": len(request["machine_permissions"]), "changed_count": count})
