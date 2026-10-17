"""Equipment groups and rotating shifts use the shared prepared-change write path."""

from core.errors import ValidationError
from core.models.calendar_periods import shift_pattern_fields
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_input import normalize_resource_input

from .states import ResourceChange, WorkbenchResourceStateService

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
        return self.state.snapshot(identity, kind=self.kind)

    def apply(self, action, payload, identity=None):
        from .queries import WorkbenchResourceQueryService

        payload = self.normalize_input(action, payload)
        preparation = WorkbenchResourceQueryService(self.conn, self.kind).preparation_for(
            action, payload, ref=getattr(identity, "ref", None))
        if action == "create" and identity is not None:
            raise WorkbenchCommandRejected("invalid_input", "新增资源时请使用新增入口。", 400)
        checked = None if action == "create" else preparation.state(self.kind,
            preparation.current(self.kind, identity).entity_key)
        return self.apply_prepared(self.prepare(action, payload, checked, preparation))

    def prepare(self, action, payload, checked, preparation):
        identity = None if action == "create" else preparation.identity(self.kind, checked["identity"]["ref"])
        code = payload["business_code"] if identity is None else identity.entity_key
        if action == "delete":
            if checked["members"]:
                raise WorkbenchCommandRejected("constraint_conflict", "还有资源在用这个" + _KIND_NAMES[self.kind] + "，请先把这些资源改到别处。")
            return ResourceChange(action, code, identity, {}, {})
        if action == "create" and preparation.raw(self.kind, code) is not None:
            raise WorkbenchCommandRejected("constraint_conflict", "这个" + _KIND_NAMES[self.kind] + "编号已经存在，请换一个编号。")
        fields = dict(payload["fields"])
        pattern = fields.pop("pattern", None)
        if "label" in payload:
            fields["name"] = payload["label"]
            owner = preparation.name_owner(self.kind, fields["name"])
            if owner is not None and owner != code:
                raise WorkbenchCommandRejected("constraint_conflict", "这个名称已经被占用，请换一个名称。")
        raw = checked["record"] if checked is not None else {}
        old_pattern = checked.get("pattern", []) if checked is not None else []
        desired = {**raw, **fields}
        if self.kind == "shift_profile" and (pattern is None and action == "create" or
                desired["cycle_days"] != len(pattern if pattern is not None else old_pattern)):
            raise ValidationError("轮换周期与逐日规则条数不一致，请补齐每一天。", field="fields.pattern")
        related = {}
        if pattern is not None and pattern != [shift_pattern_fields(row) for row in old_pattern]:
            related["pattern"] = pattern
        changes = {"status": "active", **fields} if action == "create" else {key: value for key, value in fields.items() if raw[key] != value}
        return ResourceChange(action, code, identity, changes, related)

    def apply_prepared(self, change):
        if not self.conn.in_transaction:
            raise RuntimeError("资源目录写入必须由外层工作台事务负责。")
        code, identity = change.business_code, change.identity
        if change.action == "delete":
            self.repo.delete_catalog(self.kind, code)
        elif change.action == "create":
            self.repo.insert_catalog(self.kind, code, change.fields)
            identity = self.state.identities.find_active(self.kind, code)
            if identity is None:
                raise RuntimeError("新目录记录缺少永久引用。")
        elif change.fields:
            self.repo.update_catalog(self.kind, code, change.fields)
        if "pattern" in change.related:
            self.repo.set_pattern(code, change.related["pattern"])
        changed = change.action != "update" or bool(change.fields or change.related)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"entity_ref": identity.ref, "business_code": code})
