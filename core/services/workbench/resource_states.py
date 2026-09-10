"""Shared private resource facts and identity checks, without public token handling."""

from dataclasses import asdict
from typing import Any, Dict, Optional, overload

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_resource_state_repo import WorkbenchResourceStateRepository


class WorkbenchResourceStateService:
    def __init__(self, conn, logger=None):
        self.repo = WorkbenchResourceStateRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)

    def current(self, identity, kind):
        if not isinstance(identity, WorkbenchEntityIdentity) or identity.kind != kind or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "资源引用已失效或不属于当前类型。", 404)
        current = self.identities.get(identity.ref)
        if current is None or not current.active or current.kind != kind:
            raise WorkbenchCommandRejected("entity_not_found", "原资源已经删除，旧引用不会指向同编号的新记录。", 404)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "资源或相关资料已变化，请重新读取后核对。")
        raw = self.repo.get_raw(kind, current.entity_key)
        if raw is None:
            raise WorkbenchCommandRejected("storage_failure", "资源永久引用与实际记录不一致，请检查数据库。", 500)
        return current, raw

    def by_ref(self, kind, ref):
        identity = self.identities.get(ref)
        return self.current(identity, kind)

    def related(self, kind, code):
        if code is None:
            return None
        identity = self.identities.find_active(kind, code)
        if identity is None:
            raise WorkbenchCommandRejected("storage_failure", "资源关联的永久引用缺失，未自动修补资料。", 500)
        current, raw = self.current(identity, kind)
        return {"identity": asdict(current), "record": raw}

    def snapshot(self, identity):
        current, raw = self.current(identity, identity.kind)
        kind, code = current.kind, current.entity_key
        result: Dict[str, Any] = {"identity": asdict(current), "record": raw}
        if kind in ("op_type", "machine", "operator"):
            result["profile"] = self.repo.get_profile(kind, code)
        if kind == "op_type":
            result["dependencies"] = self.repo.op_type_dependencies(code)
        elif kind == "machine":
            result["dependencies"] = self.repo.assigned_dependencies(kind, code)
            result["op_type"] = self.related("op_type", raw["op_type_id"])
            result["group"] = self.related("machine_group", result["profile"]["group_id"]) if result["profile"] else None
        elif kind == "operator":
            result["dependencies"] = self.repo.assigned_dependencies(kind, code)
            result["skills"] = self.repo.skills(code)
            result["skill_types"] = [self.related("op_type", row["op_type_id"]) for row in result["skills"]]
            result["machine_authorizations"] = self.repo.authorizations(code)
            profile_id = result["profile"]["shift_profile_id"] if result["profile"] else None
            result["shift"] = self.related("shift_profile", profile_id)
            result["shift_pattern"] = self.repo.pattern(profile_id) if profile_id else []
        elif kind == "machine_group":
            result["members"] = self.repo.group_members(code)
        elif kind == "shift_profile":
            result["pattern"] = self.repo.pattern(code)
            result["members"] = self.repo.shift_members(code)
        return result

    @overload
    def selected(self, kind, ref: str, *, category=None) -> str: ...

    @overload
    def selected(self, kind, ref: None, *, category=None) -> None: ...

    def selected(self, kind, ref: Optional[str], *, category=None) -> Optional[str]:
        if ref is None:
            return None
        identity, raw = self.by_ref(kind, ref)
        if raw.get("status", "active") != "active":
            raise WorkbenchCommandRejected("constraint_conflict", "所选关联资源已停用，请重新选择。")
        if category is not None and raw.get("category") != category:
            raise WorkbenchCommandRejected("constraint_conflict", "所选工种的自制/外协归属不适用于当前资源。")
        if identity.entity_key != identity.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "关联业务编号含首尾空白，不能按当前领域规则安全写入。")
        return identity.entity_key
