"""Real equipment groups and fully specified fixed/rotating shift catalogs."""

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_input import normalize_resource_input

from .resource_states import WorkbenchResourceStateService

# 提示里按界面上的叫法称呼这类资料，不写内部的“目录”。
_KIND_NAMES = {"machine_group": "设备组", "shift_profile": "班次档"}


class WorkbenchResourceCatalogService:
    def __init__(self, conn, kind, logger=None):
        if kind not in ("machine_group", "shift_profile"):
            raise ValueError("Unsupported resource catalog")
        self.conn, self.kind = conn, kind
        self.state = WorkbenchResourceStateService(conn, logger)
        self.repo = self.state.repo

    def normalize_input(self, action, payload):
        return normalize_resource_input(self.kind, action, payload)

    def snapshot(self, identity):
        self.state.current(identity, self.kind)
        return self.state.snapshot(identity)

    def apply(self, action, normalized_input, identity=None):
        if not self.conn.in_transaction:
            raise RuntimeError("资源目录写入必须由外层工作台事务负责。")
        payload = self.normalize_input(action, normalized_input)
        if action == "create":
            if identity is not None:
                raise WorkbenchCommandRejected("invalid_input", "新增" + _KIND_NAMES[self.kind] + "时不能指定已有记录，没有保存。请重新点「新增」。", 400)
            return self._create(payload)
        current, raw = self.state.current(identity, self.kind)
        code = current.entity_key
        if action == "delete":
            members = self.repo.group_members(code) if self.kind == "machine_group" else self.repo.shift_members(code)
            if members:
                raise WorkbenchCommandRejected("constraint_conflict", "还有资源在用这个" + _KIND_NAMES[self.kind] + "，没有删除。请先把这些资源改到别处。")
            self.repo.delete_catalog(self.kind, code)
            changed = True
        else:
            changed = self._update(code, raw, payload)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"entity_ref": current.ref, "business_code": code})

    def _create(self, payload):
        code = payload["business_code"]
        if self.repo.get_raw(self.kind, code) is not None:
            raise WorkbenchCommandRejected("constraint_conflict", "这个" + _KIND_NAMES[self.kind] + "编号已经存在，没有新增。请换一个编号。")
        fields = {"name": payload["label"], "status": "active", **payload["fields"]}
        self._check_name(code, fields["name"])
        pattern = fields.pop("pattern", None)
        self._check_pattern(fields, pattern)
        self.repo.insert_catalog(self.kind, code, fields)
        if pattern is not None:
            self.repo.set_pattern(code, pattern)
        identity = self.state.identities.find_active(self.kind, code)
        if identity is None:
            raise RuntimeError("新目录记录缺少永久引用。")
        return WorkbenchCommandOutcome("committed", {"entity_ref": identity.ref, "business_code": code})

    def _update(self, code, raw, payload):
        fields = dict(payload["fields"])
        pattern = fields.pop("pattern", None)
        if "label" in payload:
            fields["name"] = payload["label"]
            self._check_name(code, fields["name"])
        old_pattern = self.repo.pattern(code) if self.kind == "shift_profile" else []
        self._check_pattern({**raw, **fields}, pattern if pattern is not None else old_pattern)
        changes = {key: value for key, value in fields.items() if raw[key] != value}
        changed_pattern = pattern is not None and pattern != [{key: row[key] for key in ("day_offset", "is_rest", "shift_start", "shift_end")} for row in old_pattern]
        self.repo.update_catalog(self.kind, code, changes)
        if changed_pattern:
            self.repo.set_pattern(code, pattern)
        return bool(changes or changed_pattern)

    def _check_pattern(self, fields, pattern):
        if self.kind == "shift_profile" and (pattern is None or fields["cycle_days"] != len(pattern)):
            raise ValidationError("轮换周期与逐日规则条数不一致，请补齐每一天。", field="fields.pattern")

    def _check_name(self, code, name):
        existing = self.repo.catalog_by_name(self.kind, name)
        if existing is not None and existing["business_code"] != code:
            raise WorkbenchCommandRejected("constraint_conflict", "这个名称已经被占用，没有保存。请换一个名称。")
