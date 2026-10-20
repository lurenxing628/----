"""Resource changes prepared once from current rows and explicit relationships."""

from core.errors import BusinessError, ErrorCode
from core.models import Machine, Operator, OpType
from core.models.resource_capabilities import supports_source
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_input import normalize_resource_input
from data.repositories import MachineRepository, OperatorRepository, OpTypeRepository

from .states import ResourceChange, WorkbenchResourceStateService


class WorkbenchResourceService:
    def __init__(self, conn, kind, logger=None):
        if kind not in ("op_type", "machine", "operator"):
            raise ValueError("Unsupported resource entity")
        self.conn, self.kind = conn, kind
        self.state = WorkbenchResourceStateService(conn, logger)
        self.repo = self.state.repo
        self.rows = {"op_type": OpTypeRepository, "machine": MachineRepository, "operator": OperatorRepository}[kind](conn, logger=logger)

    def normalize_input(self, action, payload):
        return normalize_resource_input(self.kind, action, payload)

    def snapshot(self, identity):
        return self.state.snapshot(identity, kind=self.kind)

    def snapshot_current(self, identity):
        return self.state.snapshot_current(identity)

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
        if code != code.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "这条旧记录的编号前后带空格，请先修正编号。")
        raw = {} if checked is None else checked["record"]
        if action == "delete":
            if any(checked["dependencies"].values()):
                raise WorkbenchCommandRejected("constraint_conflict", "这个资源还被工序、授权、班表或历史报工使用，请先解除这些关联。")
            return ResourceChange(action, code, identity, {}, {})
        if action == "create" and preparation.raw(self.kind, code) is not None:
            raise BusinessError(ErrorCode.DUPLICATE_ENTRY, "资源编号“" + code + "”已存在，请改用其他编号。")
        fields = dict(payload["fields"])
        if "label" in payload:
            fields["name"] = payload["label"]
        related = {}
        if self.kind == "op_type":
            self._prepare_op_type(action, code, raw, fields, checked, preparation, related)
        elif self.kind == "machine":
            self._prepare_machine(code, raw, fields, payload["relationships"], checked, preparation, related)
        else:
            self._prepare_operator(raw, fields, payload["relationships"], checked, preparation, related)
        changes = fields if action == "create" else {key: value for key, value in fields.items() if raw[key] != value}
        return ResourceChange(action, code, identity, changes, related)

    def _prepare_op_type(self, action, code, raw, fields, checked, preparation, related):
        if "name" in fields:
            owner = preparation.name_owner("op_type", fields["name"])
            if owner is not None and owner != code:
                raise BusinessError(ErrorCode.DUPLICATE_ENTRY, "工种名称“" + fields["name"] + "”已存在，请改用其他名称。")
        category = fields.get("category", raw.get("category", "internal"))
        if "default_merge_mode" in fields:
            mode = fields.pop("default_merge_mode")
            if mode is not None and not supports_source(category, "external"):
                raise WorkbenchCommandRejected("constraint_conflict", "自制工种不能设置外协周期规则，请核对工种归属。")
            profile = checked["profile"] if checked is not None else None
            if mode != (profile["default_merge_mode"] if profile else None):
                related["policy"] = mode
        if action != "create" and category != raw["category"] and category != "both" and any(checked["dependencies"].values()):
            raise WorkbenchCommandRejected("constraint_conflict", "还有设备人员或工序在用这个工种，请先解除关联后再修改归属。")

    @staticmethod
    def _prepare_machine(code, raw, fields, relations, checked, preparation, related):
        profile = checked["profile"] if checked is not None else None
        old_group = profile["group_id"] if profile else None
        if "group_ref" in relations:
            group = preparation.selected("machine_group", relations["group_ref"])
            if group != old_group:
                related["group"] = group
        if "op_type_ref" in relations:
            fields["op_type_id"] = preparation.selected("op_type", relations["op_type_ref"], category="internal")
        if "op_type_refs" in relations:
            codes = [preparation.selected("op_type", ref, category="internal") for ref in relations["op_type_refs"]]
            primary = raw.get("op_type_id") if raw.get("op_type_id") in codes else (codes[0] if codes else None)
            fields["op_type_id"] = primary
            existing = {row["op_type_id"] for row in preparation.facts.grouped("machine_capabilities", "machine_id")[code]}
            desired = set(codes) - {primary}
            if existing != desired:
                related["capabilities"] = existing, desired

    @staticmethod
    def _prepare_operator(raw, fields, relations, checked, preparation, related):
        original = checked["profile"] if checked is not None else None
        default = {"shift_profile_id": None, "skills_declared": 0, "inactive_reason": None}
        profile = {key: original[key] for key in default} if original else dict(default)
        previous = dict(profile)
        if "status" in fields:
            requested = fields["status"]
            fields["status"] = "inactive" if requested == "leave" else requested
            profile["inactive_reason"] = {"active": None, "leave": "leave", "inactive": "disabled"}[requested]
            if fields["status"] != raw.get("status"):
                previous["inactive_reason"] = None
        if "shift_profile_ref" in relations:
            profile["shift_profile_id"] = preparation.selected("shift_profile", relations["shift_profile_ref"])
        if "skill_refs" in relations:
            desired = {preparation.selected("op_type", ref, category="internal") for ref in relations["skill_refs"]}
            existing = {row["op_type_id"] for row in checked["skills"]} if checked is not None else set()
            if existing != desired:
                related["skills"] = existing, desired
            profile["skills_declared"] = 1
        if profile != previous or original is None and profile != default:
            related["profile"] = profile

    def apply_prepared(self, change):
        if not self.conn.in_transaction:
            raise RuntimeError("资源保存必须由工作台最外层事务负责。")
        code, identity = change.business_code, change.identity
        if change.action == "delete":
            self.rows.delete(code)
        elif change.action == "create":
            model, key = {"op_type": (OpType, "op_type_id"), "machine": (Machine, "machine_id"), "operator": (Operator, "operator_id")}[self.kind]
            self.rows.create(model(**{key: code, **change.fields}))
            identity = self.state.identities.find_active(self.kind, code)
            if identity is None:
                raise RuntimeError("新增资源没有永久引用。")
        elif change.fields:
            self.rows.update(code, change.fields)
        related = change.related
        if "policy" in related:
            self.repo.set_op_type_policy(code, related["policy"])
        if "group" in related:
            self.repo.set_machine_group(code, related["group"])
        if "capabilities" in related:
            self.repo.replace_machine_capabilities(code, *related["capabilities"])
        if "skills" in related:
            self.repo.replace_skills(code, *related["skills"])
        if "profile" in related:
            self.repo.set_operator_profile(code, **related["profile"])
        changed = change.action != "update" or bool(change.fields or related)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"entity_ref": identity.ref, "business_code": code})
