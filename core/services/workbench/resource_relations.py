"""Op-type relation inspection, never a scheduling candidate or write-context API."""

import re
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_resource_relation_repo import WorkbenchResourceRelationRepository

from .resource_relations_projection import RELATION_BASIS, RELATION_KINDS, relation_entity


def _valid_ref(ref):
    return type(ref) is str and re.fullmatch(r"[0-9a-f]{48}", ref) is not None


def _invalid_facts(message):
    raise WorkbenchCommandRejected("storage_failure", message + "；未自动修补资料。", 500)


@dataclass(frozen=True)
class ResourceRelationRequest:
    relation: str
    query: str = ""
    number: int = 1
    size: int = 20

    def __post_init__(self):
        if type(self.relation) is not str or self.relation not in RELATION_KINDS:
            raise WorkbenchCommandRejected("invalid_input", "关联类型不正确，请明确选择设备、人员或供应商。", 400)
        ResourcePageRequest(RELATION_KINDS[self.relation], query=self.query, number=self.number, size=self.size)

    def scope(self, parent_ref):
        return {"kind": "op_type_relations", "parent_ref": parent_ref, "relation": self.relation,
                "query": self.query, "size": self.size, "sort": "business_code", "direction": "asc"}


class WorkbenchResourceRelationService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.repo = WorkbenchResourceRelationRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)

    def _parent(self, kind, ref, relation):
        if kind != "op_type" or not _valid_ref(ref):
            raise WorkbenchCommandRejected("entity_not_found", "工种引用或入口不正确，请从工种列表重新选择。", 404)
        identity = self.identities.get(ref)
        if identity is None or identity.kind != kind or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "工种已不存在；旧引用不会指向同编号的新记录。", 404)
        parent = self.repo.parent(identity.entity_key)
        if parent is None:
            raise WorkbenchCommandRejected("entity_not_found", "工种记录已不存在。", 404)
        if parent["category"] not in ("internal", "external"):
            _invalid_facts("工种的自制或外协归属无效")
        allowed = ("machines", "operators") if parent["category"] == "internal" else ("suppliers",)
        if relation not in allowed:
            raise WorkbenchCommandRejected("invalid_input", "此工种归属不支持所选关联类型，未自动切换查询范围。", 400)
        return identity, parent

    @contextmanager
    def read_snapshot(self, kind, ref, query):
        with TransactionManager(self.conn).transaction():
            identity, parent = self._parent(kind, ref, query.relation)
            rows = self.repo.rows(identity.entity_key, query.relation)
            records = self._records(rows)
            facts = self.repo.facts(query.relation, sorted(records))
            self._validate_facts(query.relation, rows, facts)
            qualifications = self._qualifications(query.relation, sorted(records))
            fingerprint = input_fingerprint({"parent_identity": asdict(identity), "parent": parent,
                                             "rows": rows, "facts": facts})
            yield fingerprint, self._page(identity, query, records, qualifications, facts)

    def _records(self, rows):
        records = {}
        for row in rows:
            code = row["business_code"]
            if not isinstance(code, str) or not code or code != code.strip() or "\x00" in code or code in records:
                _invalid_facts("关联资源编号无效或重复")
            if row["name"] is None:
                _invalid_facts("关联指向不存在的资源")
            if not _valid_ref(row["ref"]):
                _invalid_facts("关联资源永久引用缺失或无效")
            records[code] = row
        return records

    def _validate_facts(self, relation, rows, facts):
        if relation == "suppliers":
            for row in rows:
                if row["legacy_type"] is not None and row["legacy_category"] != "external":
                    _invalid_facts("供应商旧单工种不存在或不是外协工种")
            if any(row["category"] != "external" for row in facts["capabilities"]):
                _invalid_facts("供应商显式能力工种不存在或不是外协工种")
        elif relation == "operators":
            seen = set()
            for row in facts["authorizations"]:
                key = (row["operator_id"], row["machine_id"])
                if key in seen or row["machine_name"] is None:
                    _invalid_facts("设备授权重复或指向不存在的设备")
                seen.add(key)
                if row["op_type_id"] is not None and row["work_type_category"] != "internal":
                    _invalid_facts("授权设备的工种不存在或不是自制工种")

    def _qualifications(self, relation, codes):
        if relation != "operators":
            return {}
        try:
            return OperatorQualificationService(self.conn, logger=self.logger).load(codes)
        except OperatorQualificationError as exc:
            raise WorkbenchCommandRejected("storage_failure", "人员资格资料无效或无法读取；未退回旧授权或空集合。", 500) from exc

    def _page(self, parent, query, records, qualifications, facts):
        codes, total = self.repo.page(parent.entity_key, query.relation, query)
        pages = max(1, (total + query.size - 1) // query.size)
        if query.number > pages:
            raise WorkbenchCommandRejected("snapshot_stale", "关联页码已超出当前范围，请明确刷新后重新选择。")
        authorizations = defaultdict(list)
        for row in facts.get("authorizations", []):
            authorizations[row["operator_id"]].append(row)
        entities = []
        for code in codes:
            row = records[code]
            identity = WorkbenchEntityIdentity(row["ref"], RELATION_KINDS[query.relation], code, row["revision"], True)
            entities.append(relation_entity(identity, row, query.relation, parent.entity_key, qualifications, authorizations[code]))
        return {"parent_ref": parent.ref, "parent_kind": "op_type", "relation": query.relation,
                "basis": dict(RELATION_BASIS[query.relation]), "entities": entities,
                "page": {"number": query.number, "size": query.size, "total": total, "pages": pages,
                         "sort": [{"field": "business_code", "direction": "asc"}]}}
