"""Static enabled-resource counts, not calendar capacity or scheduled utilization."""

from collections import Counter, defaultdict
from typing import Any, Dict

from core.models.resource_capabilities import machine_type_index, supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_status import public_resource_status
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.workbench_resource_metrics_repo import WorkbenchResourceMetricsRepository

AVAILABILITY_BASIS = "enabled_authorized_matching"
RESOURCE_KEYS = {"op_type": "op_type_id", "machine": "machine_id", "operator": "operator_id",
         "supplier": "supplier_id", "machine_group": "group_id", "shift_profile": "profile_id"}
_INTERNAL = {"op_type", "machine_capabilities", "machine", "operator", "operator_profiles", "skills", "authorizations"}
_EXTERNAL = {"op_type", "supplier", "supplier_profiles", "capabilities", "policies"}
READ_FACTS = {
    "machine": {"machine", "machine_capabilities", "op_type", "groups", "machine_group"},
    "operator": {"operator", "operator_profiles", "skills", "authorizations", "op_type", "machine", "shift_profile", "shift_pattern"},
    "supplier": _EXTERNAL,
    "machine_group": {"machine_group", "groups", "machine"},
    "shift_profile": {"shift_profile", "shift_pattern", "operator_profiles", "operator"},
}
READ_FACTS["op_type"] = set().union(_INTERNAL, _EXTERNAL, *READ_FACTS.values())
_BASIS = {
    "machines": "启用并绑定了对应自制工种的设备；没算班表和当前占用。",
    "operators": "启用、对匹配设备有授权、并符合技能资格规则的人数，同一人只算一次；没算班表和当前占用。",
    "linked_machines": "绑定所选自制工种的全部设备，含停机和停用的设备。",
    "without_machines": "所选自制工种里一台设备都没绑的工种数，不是说设备都占满了。",
    "available_suppliers": "启用并且能做所选外协工种的供应商数，同一家只算一次。",
    "skills": "已登记的人员与自制工种关系条数；旧的设备授权不算技能登记。",
    "groups": "筛选范围内设备实际绑定的不同设备组数。",
    "status": "按资料中的启用状态统计。",
}


class ResourceMetricFactsError(WorkbenchCommandRejected):
    """Invalid domain relationships, distinct from SQLite/schema/IO failures."""


def _invalid(message):
    raise ResourceMetricFactsError("storage_failure", message + "，这一项没有统计出来，资料没有被改动。请到资料总览核对后重试。", 500)


def index_resource_rows(rows, key):
    result = {}
    for row in rows:
        value = row[key]
        if not isinstance(value, str) or not value or value in result:
            _invalid("有资源没有编号或者编号重复")
        result[value] = row
    return result


def _relation(value, records, label):
    if value not in records:
        _invalid(label + "指向的记录已经不存在")


class WorkbenchResourceMetricsService:
    def __init__(self, conn, logger=None, *, facts=None):
        """``facts`` supplies a command's captured resource closure; otherwise facts load from SQLite on first use."""
        self.conn, self.logger = conn, logger
        self.repo = WorkbenchResourceMetricsRepository(conn, logger=logger)
        self.facts = facts if facts is not None else {}
        self.records, self.profiles, self.statuses = {}, {}, {}
        self.policies = {}
        self._computed = set()
        self._failed = {}
        self.linked_machines = defaultdict(set)
        self.active_machines = defaultdict(set)
        self.available_operators = defaultdict(set)
        self.available_suppliers = defaultdict(set)

    def load_facts(self, names):
        missing = sorted(set(names) - set(self.facts))
        if missing:
            self.facts.update(self.repo.facts(missing))

    @staticmethod
    def identity_kinds(kind):
        return sorted(READ_FACTS[kind] & set(RESOURCE_KEYS))

    def kind_records(self, kind):
        if kind not in self.records:
            self.load_facts([kind])
            self.records[kind] = index_resource_rows(self.facts[kind], RESOURCE_KEYS[kind])
        return self.records[kind]

    def kind_statuses(self, kind):
        if kind not in self.statuses:
            if kind in ("operator", "supplier"):
                self.load_facts([kind + "_profiles"])
                self.profiles[kind] = index_resource_rows(self.facts[kind + "_profiles"], kind + "_id")
            self.statuses[kind] = {code: public_resource_status(kind, row["status"], self.profiles.get(kind, {}).get(code))
                                   for code, row in self.kind_records(kind).items()}
        return self.statuses[kind]

    def _validate_internal(self):
        for row in self.facts["machine_capabilities"]:
            _relation(row["machine_id"], self.records["machine"], "设备加工能力")
            self._work_type(row["op_type_id"], "internal")
        for row in self.facts["authorizations"]:
            _relation(row["operator_id"], self.records["operator"], "设备操作授权")
            _relation(row["machine_id"], self.records["machine"], "设备操作授权")
        for row in self.facts["skills"]:
            _relation(row["operator_id"], self.records["operator"], "人员技能")
        for row in self.facts["operator_profiles"]:
            _relation(row["operator_id"], self.records["operator"], "人员资格登记")

    def _work_type(self, code, category):
        _relation(code, self.records["op_type"], "资源工种关联")
        if not supports_source(self.records["op_type"][code]["category"], category):
            _invalid("资源关联的工种，自制或外协归属对不上")

    def _validate_suppliers(self):
        for row in self.facts["capabilities"]:
            _relation(row["supplier_id"], self.records["supplier"], "供应商能力")
            self._work_type(row["op_type_id"], "external")

    def _active_qualifications(self):
        active = {code for code, status in self.kind_statuses("operator").items() if status == "active"}
        profiles = [{"operator_id": code, "profile_operator_id": code if code in self.profiles["operator"] else None,
                     "skills_declared": self.profiles["operator"].get(code, {}).get("skills_declared")}
                    for code in self.records["operator"]]
        stored_skills = [dict(row, category=self.records["op_type"].get(row["op_type_id"], {}).get("category"))
                         for row in self.facts["skills"]]
        # The planning service interprets the already captured qualification facts once.
        all_skills = OperatorQualificationService.project_facts(sorted(self.records["operator"]), profiles, stored_skills)
        return {code: all_skills[code] for code in active}

    def _internal_capacity(self):
        if "internal" in self._computed:
            return
        self.load_facts(_INTERNAL)
        for kind in ("op_type", "machine", "operator"):
            self.kind_records(kind)
        self._validate_internal()
        capabilities = machine_type_index(self.records["machine"].values(), self.facts["machine_capabilities"])
        active = {}
        for code, row in self.records["machine"].items():
            for work_type in capabilities[code]:
                self.linked_machines[work_type].add(code)
                if row["status"] == "active":
                    self.active_machines[work_type].add(code)
            if row["status"] == "active":
                active[code] = capabilities[code]
        skills = self._active_qualifications()
        links = OperatorQualificationService.eligible_links(self.facts["authorizations"], active, qualifications=skills)
        for link in links:
            for work_type in capabilities[link["machine_id"]]:
                if skills[link["operator_id"]] is None or work_type in skills[link["operator_id"]]:
                    self.available_operators[work_type].add(link["operator_id"])
        self._computed.add("internal")

    def _external_capacity(self):
        if "external" in self._computed:
            return
        self.load_facts(_EXTERNAL)
        self.kind_records("op_type")
        self.kind_records("supplier")
        self.kind_statuses("supplier")
        self._validate_suppliers()
        for row in self.facts["capabilities"]:
            if self.statuses["supplier"][row["supplier_id"]] == "active":
                self.available_suppliers[row["op_type_id"]].add(row["supplier_id"])
        self._computed.add("external")

    def op_type_records(self):
        self.load_facts(["op_type", "policies"])
        if "policies" not in self._computed:
            self.policies = index_resource_rows(self.facts["policies"], "op_type_id")
            self._computed.add("policies")
        return self.kind_records("op_type")

    def availability(self, code):
        if not supports_source(self.kind_records("op_type")[code]["category"], "internal"):
            return None
        if not self._ensure_capacity("internal"):
            return None
        return {"machines": len(self.active_machines[code]), "operators": len(self.available_operators[code]),
                "basis": AVAILABILITY_BASIS}

    def availability_issues(self, code):
        if not supports_source(self.kind_records("op_type")[code]["category"], "internal") or self._ensure_capacity("internal"):
            return []
        return [{"code": "resource_availability_unavailable", "message": self._failed["internal"]}]

    def _ensure_capacity(self, category):
        if category in self._failed:
            return False
        try:
            {"internal": self._internal_capacity, "external": self._external_capacity}[category]()
        except (ResourceMetricFactsError, OperatorQualificationError) as exc:
            if isinstance(exc, OperatorQualificationError) and exc.__cause__ is not None:
                raise
            # A failed metric stays explicit, while its editable source records remain reachable.
            self._failed[category] = str(exc)
            return False
        return True

    def status_metrics(self, counts: Dict[str, int], *, scope: str = "filtered") -> Dict[str, Any]:
        """SQL 按对外状态数出的 ``counts``（``status_counts``）配上统计口径。"""
        return {"scope": scope, "counts": counts, "basis": dict(_BASIS), "issues": []}

    def op_type_metrics(self, codes, *, scope="filtered"):
        """工种的能力计数要按资格规则在内存里算，不走 SQL 状态计数。"""
        counts = self._work_type_counts(set(codes))
        issues = []
        unavailable = {"internal": ["linked_machines", "available_operators", "without_machines"],
                       "external": ["available_suppliers"]}
        for category in ("internal", "external"):
            if category in self._failed and any(
                supports_source(self.records["op_type"][code]["category"], category) for code in codes
            ):
                issues.append({"code": "resource_availability_unavailable", "message": self._failed[category],
                               "unavailable_fields": unavailable[category]})
        return {"scope": scope, "counts": counts, "basis": dict(_BASIS), "issues": issues}

    def _work_type_counts(self, codes):
        self.op_type_records()
        internal = {code for code in codes if supports_source(self.records["op_type"][code]["category"], "internal")}
        external = {code for code in codes if supports_source(self.records["op_type"][code]["category"], "external")}
        counts = {"total": len(codes), "internal": len(internal), "external": len(external)}
        if not internal or self._ensure_capacity("internal"):
            counts.update(self._internal_counts(internal))
        if not external or self._ensure_capacity("external"):
            counts["available_suppliers"] = len(set().union(*(self.available_suppliers[code] for code in external)))
        counts.update(self._policy_counts(external))
        return counts

    def _internal_counts(self, codes):
        return {"linked_machines": len(set().union(*(self.linked_machines[code] for code in codes))),
                "available_operators": len(set().union(*(self.available_operators[code] for code in codes))),
                "without_machines": sum(not self.linked_machines[code] for code in codes)}

    def _policy_counts(self, external):
        modes = Counter(self.policies[code]["default_merge_mode"] if code in self.policies else "unset" for code in external)
        return {"merged": modes["merged"], "separate": modes["separate"], "merge_mode_unset": modes["unset"]}

    def summary_metrics(self, status_counts):
        """``status_counts``：各类资料整库按对外状态的 SQL 计数；工种按自制、外协各算一组能力计数。"""
        groups = {kind: self.status_metrics(counts, scope="all") for kind, counts in status_counts.items()}
        for category in ("internal", "external"):
            groups[category + "_op_type"] = self._op_type_summary(category)
        return {"scope": "all", "groups": groups}

    def _op_type_summary(self, category):
        try:
            codes = [code for code, row in self.kind_records("op_type").items() if supports_source(row["category"], category)]
            return self.op_type_metrics(codes, scope="all")
        except ResourceMetricFactsError as exc:
            return {"scope": "all", "counts": {}, "basis": dict(_BASIS),
                    "issues": [{"code": "resource_metrics_unavailable", "message": str(exc)}]}
