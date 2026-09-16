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
            raise WorkbenchCommandRejected("entity_not_found", "这条资源记录已失效，或者不属于当前这一类资料，操作没有执行。请从列表重新选择。", 404)
        current = self.identities.get(identity.ref)
        if current is None or not current.active or current.kind != kind:
            raise WorkbenchCommandRejected("entity_not_found", "这条资源已经删除了，操作未执行。请从列表重新选择。", 404)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "资源或相关资料已经变了，操作没有执行。请刷新后重新核对。")
        raw = self.repo.get_raw(kind, current.entity_key)
        if raw is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的编号和实际记录对不上，操作没有执行。请联系维护人员核对数据。", 500)
        return current, raw

    def by_ref(self, kind, ref):
        identity = self.identities.get(ref)
        return self.current(identity, kind)

    def related(self, kind, code):
        if code is None:
            return None
        identity = self.identities.find_active(kind, code)
        if identity is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的关联记录在资料里查不到编号，操作没有执行，资料也没有被改动。请到资料总览核对后重试。", 500)
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
            result["authorized_machines"] = [self.related("machine", row["machine_id"])
                                             for row in result["machine_authorizations"]]
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
            raise WorkbenchCommandRejected("constraint_conflict", "选中的关联资源已经停用，没有保存。请重新选择一个在用的。")
        if category is not None and raw.get("category") != category:
            raise WorkbenchCommandRejected("constraint_conflict", "选中工种的自制或外协归属和当前资源不匹配，没有保存。请换一个工种。")
        if identity.entity_key != identity.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "关联编号前后带空格，没有保存，以免写错到别的记录上。请去掉前后的空格。")
        return identity.entity_key
