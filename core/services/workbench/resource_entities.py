"""Legacy domain CRUD with explicit workbench resource relationships."""

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_input import normalize_resource_input
from core.services.equipment.machine_service import MachineService
from core.services.personnel.operator_service import OperatorService
from core.services.process.op_type_service import OpTypeService

from .resource_states import WorkbenchResourceStateService


class WorkbenchResourceService:
    def __init__(self, conn, kind, logger=None):
        if kind not in ("op_type", "machine", "operator"):
            raise ValueError("Unsupported resource entity")
        self.conn, self.kind = conn, kind
        self.state = WorkbenchResourceStateService(conn, logger)
        self.repo = self.state.repo
        service = {"op_type": OpTypeService, "machine": MachineService, "operator": OperatorService}[kind]
        self.domain = service(conn, logger=logger)

    def normalize_input(self, action, payload):
        return normalize_resource_input(self.kind, action, payload)

    def snapshot(self, identity):
        self.state.current(identity, self.kind)
        return self.state.snapshot(identity)

    def apply(self, action, normalized_input, identity=None):
        if not self.conn.in_transaction:
            raise RuntimeError("资源保存必须由工作台最外层事务负责。")
        payload = self.normalize_input(action, normalized_input)
        if action == "create":
            if identity is not None:
                raise WorkbenchCommandRejected("invalid_input", "新增资源不能指定已有对象。", 400)
            code, raw = payload["business_code"], {}
        else:
            identity, raw = self.state.current(identity, self.kind)
            code = identity.entity_key
            if code != code.strip():
                raise WorkbenchCommandRejected("constraint_conflict", "旧编号含首尾空白，不能由当前领域规则误写另一对象。")
        if action == "delete":
            if self.kind == "op_type" and any(self.repo.op_type_dependencies(code).values()):
                raise WorkbenchCommandRejected("constraint_conflict", "工种仍被资源、技能或工序引用，不能删除。")
            self.domain.delete(code)
            changed = True
        else:
            changed = self._save(action, code, raw, payload)
        if identity is None:
            identity = self.state.identities.find_active(self.kind, code)
            if identity is None:
                raise RuntimeError("新增资源没有永久引用，不能确认保存。")
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"entity_ref": identity.ref, "business_code": code})

    def _save(self, action, code, raw, payload):
        fields = dict(payload["fields"])
        if "label" in payload:
            fields["name"] = payload["label"]
        if self.kind == "op_type":
            return self._save_op_type(action, code, raw, fields)
        if self.kind == "machine":
            return self._save_machine(action, code, raw, fields, payload["relationships"])
        return self._save_operator(action, code, raw, fields, payload["relationships"])

    def _domain_save(self, action, code, raw, fields):
        if action == "create":
            self.domain.create(code, **fields)
            return True
        changes = {key: value for key, value in fields.items() if raw[key] != value}
        if changes:
            self.domain.update(code, **{key: "" if value is None else value for key, value in changes.items()})
        return bool(changes)

    def _save_op_type(self, action, code, raw, fields):
        marker = "default_merge_mode" in fields
        mode = fields.pop("default_merge_mode", None)
        category = fields.get("category", raw.get("category", "internal"))
        if marker and mode is not None and category != "external":
            raise WorkbenchCommandRejected("constraint_conflict", "自制工种不能设置外协周期策略。")
        if action != "create" and category != raw["category"] and any(self.repo.op_type_dependencies(code).values()):
            raise WorkbenchCommandRejected("constraint_conflict", "工种仍有资源或工序引用，不能直接切换自制/外协归属。")
        profile = self.repo.get_profile("op_type", code)
        old_mode = profile["default_merge_mode"] if profile else None
        changed = self._domain_save(action, code, raw, fields)
        if marker and mode != old_mode:
            self.repo.set_op_type_policy(code, mode)
            changed = True
        return changed

    def _save_machine(self, action, code, raw, fields, relations):
        profile = self.repo.get_profile("machine", code)
        old_group = profile["group_id"] if profile else None
        group = self.state.selected("machine_group", relations["group_ref"]) if "group_ref" in relations else old_group
        if "op_type_ref" in relations:
            fields["op_type_id"] = self.state.selected("op_type", relations["op_type_ref"], category="internal")
        changed = self._domain_save(action, code, raw, fields)
        if group != old_group:
            self.repo.set_machine_group(code, group)
            changed = True
        return changed

    def _save_operator(self, action, code, raw, fields, relations):
        original, profile, old_profile = self._operator_settings(code, fields, relations)
        codes = None
        if "skill_refs" in relations:
            codes = [self.state.selected("op_type", ref, category="internal") for ref in relations["skill_refs"]]
            profile["skills_declared"] = 1
        changed = self._domain_save(action, code, raw, fields)
        if codes is not None and sorted(codes) != sorted(row["op_type_id"] for row in self.repo.skills(code)):
            self.repo.set_skills(code, codes)
            changed = True
        # A legacy status write clears a known reason; restore this explicitly saved reason in the same transaction.
        current = self.repo.get_profile("operator", code)
        current_values = {key: current[key] for key in profile} if current else old_profile
        if profile != current_values or (original is None and profile != old_profile):
            self.repo.set_operator_profile(code, **profile)
            changed = True
        return changed

    def _operator_settings(self, code, fields, relations):
        original = self.repo.get_profile("operator", code)
        profile = {"shift_profile_id": None, "skills_declared": 0, "inactive_reason": None}
        if original:
            profile.update({key: original[key] for key in profile})
        old_profile = dict(profile)
        if "status" in fields:
            requested = fields["status"]
            fields["status"] = "inactive" if requested == "leave" else requested
            profile["inactive_reason"] = {"active": None, "leave": "leave", "inactive": "disabled"}[requested]
        if "shift_profile_ref" in relations:
            profile["shift_profile_id"] = self.state.selected("shift_profile", relations["shift_profile_ref"])
        return original, profile, old_profile
