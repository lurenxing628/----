"""Shared private resource facts and identity checks, without public token handling."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from core.models.resource_capabilities import supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_resource_state_repo import WorkbenchResourceStateRepository

from .state_projection import machine_write_state, operator_write_state
from .table_states import resource_table_states


@dataclass
class ResourceChange:
    action: str
    business_code: str
    identity: Optional[WorkbenchEntityIdentity]
    fields: dict
    related: dict


class ResourceChangePreparation:
    """One operation's captured resource rows, identities and complete current states."""

    def __init__(self, facts, *, name_reader=None, names=None):
        self.facts = facts
        self._identities = {row["ref"]: row for row in facts.identities.values()}
        self._states = {}
        self._names = names or {}
        self._name_reader = name_reader
        self._references = {}

    def identity(self, kind, ref):
        identity = self.find_by_ref(kind, ref)
        if identity is None:
            raise WorkbenchCommandRejected("entity_not_found", "这条资源已经删除了，请刷新后重新选择。", 404)
        return identity

    def find_by_ref(self, kind, ref):
        if kind not in self.facts.identity_kinds:
            self.facts.load_identity_kinds([kind])
            self._identities = {row["ref"]: row for row in self.facts.identities.values()}
        row = self._identities.get(ref)
        if row is None or row["kind"] != kind:
            return None
        return self.facts.identity(kind, row["entity_key"])

    def identity_by_code(self, kind, code):
        return self.facts.identity(kind, code)

    def current(self, kind, identity):
        if not isinstance(identity, WorkbenchEntityIdentity) or identity.kind != kind or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "这条资源记录已失效，请重新选择。", 404)
        current = self.identity(kind, identity.ref)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "资源或相关资料已经变了，请刷新后重新核对。")
        return current

    def find_identity(self, kind, code):
        if kind not in self.facts.identity_kinds:
            self.facts.load_identity_kinds([kind])
        return self.identity_by_code(kind, code) if (kind, code) in self.facts.identities else None

    def raw(self, kind, code):
        from .metrics import _KEYS

        return self.facts.raw_lookup(kind, _KEYS[kind]).get(code)

    def states(self, kind, codes):
        current = self._states.setdefault(kind, {})
        pending = sorted(set(codes) - set(current))
        for offset in range(0, len(pending), 200):
            chunk = pending[offset:offset + 200]
            references = self._references.get(kind)
            if kind == "op_type":
                if references is None:
                    dependencies = self.facts.metrics.repo.op_type_dependencies(chunk)
                else:
                    from .table_facts import _OP_TYPE_DEPENDENCIES

                    dependencies = {code: {name: len(references[code][source])
                        for name, source in _OP_TYPE_DEPENDENCIES.items()} for code in chunk}
                profiles = self.facts.raw_lookup("policies", "op_type_id")
                current.update({code: {"identity": asdict(self.identity_by_code(kind, code)),
                    "record": self.facts.raw_record(kind, code), "profile": profiles.get(code),
                    "dependencies": dependencies[code]} for code in chunk})
            else:
                counts, supplier_refs = None, None
                if references is not None:
                    if kind == "supplier":
                        supplier_refs = {name: {code: references[code][table] for code in chunk}
                            for name, table in (("part_operations", "PartOperations.supplier_id"),
                                                ("batch_operations", "BatchOperations.supplier_id"),
                                                ("external_groups", "ExternalGroups.supplier_id"))}
                    else:
                        aliases = {"BatchOperations": "batch_operations", "Schedule": "schedule"}
                        counts = {code: {aliases.get(table.split(".")[0], table): len(rows)
                            for table, rows in references[code].items()} for code in chunk}
                current.update(resource_table_states(self.facts, kind, chunk, dependencies=counts,
                                                     supplier_references=supplier_refs))
        return {code: current[code] for code in codes}

    def capture_references(self, repo, kind, codes):
        self._references[kind] = repo.references_many(kind, sorted(set(codes)))
        return self._references[kind]

    def state(self, kind, code):
        return self.states(kind, [code])[code]

    def selected_record(self, kind, identity, *, category=None):
        current = self.identity(kind, identity.ref)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "资源或相关资料已经变了，请刷新后重新核对。")
        raw = self.facts.raw_record(kind, current.entity_key)
        WorkbenchResourceStateService._require_selected(current, raw, category)
        return current, raw

    def selected(self, kind, ref, *, category=None):
        if ref is None:
            return None
        identity = self.identity(kind, ref)
        self.selected_record(kind, identity, category=category)
        return identity.entity_key

    def name_owner(self, kind, name):
        if self._name_reader is not None:
            owners = self._names.setdefault(kind, {})
            if name not in owners:
                owners.update(self._name_reader(kind, [name]))
            return owners[name]
        if kind not in self._names:
            self._names[kind] = {row["name"]: code for code, row in self.facts.raw_lookup(kind,
                {"op_type": "op_type_id", "machine_group": "group_id", "shift_profile": "profile_id"}[kind]).items()}
        return self._names[kind].get(name)

    def authorizations(self, kind, code):
        key = "machine_id" if kind == "machine" else "operator_id"
        return self.facts.grouped("authorizations", key)[code]

    def export_state(self, kind, code):
        from .file_projection import resource_export_state

        return resource_export_state(self.facts, kind, code)

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
        return current, self._raw_from_current(current)

    def _raw_from_current(self, current):
        raw = self.repo.get_raw(current.kind, current.entity_key)
        if raw is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的编号和实际记录对不上，操作没有执行。请联系维护人员核对数据。", 500)
        return raw

    def related(self, kind, code):
        if code is None:
            return None
        identity = self.identities.find_active(kind, code)
        if identity is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的关联记录在资料里查不到编号，操作没有执行，资料也没有被改动。请到资料总览核对后重试。", 500)
        raw = self._raw_from_current(identity)
        return {"identity": asdict(identity), "record": raw}

    def snapshot(self, identity, *, kind=None):
        current, raw = self.current(identity, identity.kind if kind is None else kind)
        return self._snapshot_from_current(current, raw)

    def snapshot_current(self, identity):
        return self._snapshot_from_current(identity, self._raw_from_current(identity))

    def _snapshot_from_current(self, current, raw):
        """Project current identity/raw facts without querying them again."""
        kind, code = current.kind, current.entity_key
        result: Dict[str, Any] = {"identity": asdict(current), "record": raw}
        if kind in ("op_type", "machine", "operator"):
            result["profile"] = self.repo.get_profile(kind, code)
        if kind == "op_type":
            result["dependencies"] = self.repo.op_type_dependencies(code)
        elif kind == "machine":
            types = set(self.repo.machine_capabilities(code)) | ({raw["op_type_id"]} if raw["op_type_id"] is not None else set())
            profile = result["profile"]
            return machine_write_state(current, raw, profile, self.repo.assigned_dependencies(kind, code),
                                       [self.related("op_type", item) for item in sorted(types)],
                                       self.related("machine_group", profile["group_id"]) if profile else None)
        elif kind == "operator":
            profile, skills, authorizations = result["profile"], self.repo.skills(code), self.repo.authorizations(code)
            profile_id = profile["shift_profile_id"] if profile else None
            return operator_write_state(current, raw, profile, self.repo.assigned_dependencies(kind, code), skills,
                                        [self.related("op_type", row["op_type_id"]) for row in skills], authorizations,
                                        [self.related("machine", row["machine_id"]) for row in authorizations],
                                        self.related("shift_profile", profile_id), self.repo.pattern(profile_id) if profile_id else [])
        elif kind == "machine_group":
            result["members"] = self.repo.group_members(code)
        elif kind == "shift_profile":
            result["pattern"] = self.repo.pattern(code)
            result["members"] = self.repo.shift_members(code)
        return result

    @staticmethod
    def _require_selected(identity, raw, category):
        if raw.get("status", "active") != "active":
            raise WorkbenchCommandRejected("constraint_conflict", "选中的关联资源已经停用，没有保存。请重新选择一个在用的。")
        if category is not None and not supports_source(raw.get("category"), category):
            raise WorkbenchCommandRejected("constraint_conflict", "选中工种的自制或外协归属和当前资源不匹配，没有保存。请换一个工种。")
        if identity.entity_key != identity.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "关联编号前后带空格，没有保存，以免写错到别的记录上。请去掉前后的空格。")
