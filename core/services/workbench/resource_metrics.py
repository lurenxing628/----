"""Static enabled-resource counts, not calendar capacity or scheduled utilization."""

from collections import Counter, defaultdict
from types import SimpleNamespace
from typing import Dict

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.workbench_resource_metrics_repo import WorkbenchResourceMetricsRepository

AVAILABILITY_BASIS = "enabled_authorized_matching"
_KEYS = {"op_type": "op_type_id", "machine": "machine_id", "operator": "operator_id",
         "supplier": "supplier_id", "machine_group": "group_id", "shift_profile": "profile_id"}
_INTERNAL = {"op_type", "machine", "operator", "operator_profiles", "skills", "authorizations"}
_EXTERNAL = {"op_type", "supplier", "supplier_profiles", "capabilities", "policies"}
_READ_FACTS = {
    "machine": {"machine", "op_type", "groups", "machine_group"},
    "operator": {"operator", "operator_profiles", "skills", "authorizations", "op_type", "shift_profile"},
    "supplier": _EXTERNAL,
    "machine_group": {"machine_group", "groups", "machine"},
    "shift_profile": {"shift_profile", "operator_profiles", "operator"},
}
_READ_FACTS["op_type"] = set().union(_INTERNAL, _EXTERNAL, *_READ_FACTS.values())
_BASIS = {
    "machines": "启用且绑定匹配自制工种的设备；不含日历与当前占用。",
    "operators": "启用、对匹配的启用设备有现授权且通过现有技能资格规则的去重人数；不含日历与当前占用。",
    "linked_machines": "绑定所选自制工种的全部设备，含检修与停用设备。",
    "without_machines": "所选自制工种中完全没有绑定设备的工种数，并非没有空闲设备。",
    "available_suppliers": "启用且有匹配外协工种能力的去重供应商数。",
    "skills": "已登记的人员与自制工种关系条数，不将旧设备授权推算为技能登记或认证。",
    "groups": "筛选范围内设备实际绑定的不同设备组数。",
    "status": "active仅表示资料启用，不代表今日出勤；未知旧状态单列，不推断原因。",
}


class ResourceMetricFactsError(WorkbenchCommandRejected):
    """Invalid domain relationships, distinct from SQLite/schema/IO failures."""


def _invalid(message):
    raise ResourceMetricFactsError("storage_failure", message + "；未修补或推算资源资料。", 500)


def _index(rows, key):
    result = {}
    for row in rows:
        value = row[key]
        if not isinstance(value, str) or not value or value in result:
            _invalid("资源编号缺失或重复")
        result[value] = row
    return result


def _relation(value, records, label, *, nullable=False):
    if value is None and nullable:
        return
    if value not in records:
        _invalid(label + "指向不存在的记录")


def _status(kind, raw, profile=None):
    value = raw["status"]
    if kind not in ("operator", "supplier"):
        allowed = ("active", "inactive", "maintain") if kind == "machine" else ("active", "inactive")
        return value if value in allowed else "unknown"
    if value == "active":
        return "active"
    reason = profile["inactive_reason"] if profile else None
    special = "leave" if kind == "operator" else "pending_review"
    if value == "inactive":
        return special if reason == special else "inactive" if reason == "disabled" else "unknown"
    return "unknown"


class WorkbenchResourceMetricsService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.repo = WorkbenchResourceMetricsRepository(conn, logger=logger)
        self.facts, self.records, self.profiles, self.statuses = {}, {}, {}, {}
        self.policies, self.groups = {}, {}
        self._computed = set()
        self._failed = {}
        self.linked_machines = defaultdict(set)
        self.active_machines = defaultdict(set)
        self.available_operators = defaultdict(set)
        self.available_suppliers = defaultdict(set)

    def _load(self, names):
        self.facts.update(self.repo.facts(sorted(set(names) - set(self.facts))))

    def fingerprint_facts(self, kind):
        # Fingerprinting raw facts must not make another domain's validation a read gate.
        names = _READ_FACTS[kind]
        self._load(names)
        return {name: self.facts[name] for name in sorted(names)}

    def _records(self, kind):
        if kind not in self.records:
            self._load([kind])
            self.records[kind] = _index(self.facts[kind], _KEYS[kind])
        return self.records[kind]

    def _statuses(self, kind):
        if kind not in self.statuses:
            if kind in ("operator", "supplier"):
                self._load([kind + "_profiles"])
                self.profiles[kind] = _index(self.facts[kind + "_profiles"], kind + "_id")
            self.statuses[kind] = {code: _status(kind, row, self.profiles.get(kind, {}).get(code))
                                   for code, row in self._records(kind).items()}
        return self.statuses[kind]

    def _validate_internal(self):
        for row in self.records["machine"].values():
            self._work_type(row["op_type_id"], "internal", nullable=True)
        for row in self.facts["authorizations"]:
            _relation(row["operator_id"], self.records["operator"], "设备操作授权")
            _relation(row["machine_id"], self.records["machine"], "设备操作授权")
        for row in self.facts["skills"]:
            _relation(row["operator_id"], self.records["operator"], "人员技能")
        for row in self.facts["operator_profiles"]:
            _relation(row["operator_id"], self.records["operator"], "人员资格登记")

    def _work_type(self, code, category, *, nullable=False):
        _relation(code, self.records["op_type"], "资源工种关联", nullable=nullable)
        if code is not None and self.records["op_type"][code]["category"] != category:
            _invalid("资源关联工种的自制或外协归属不匹配")

    def _validate_suppliers(self):
        for row in self.records["supplier"].values():
            self._work_type(row["op_type_id"], "external", nullable=True)
        for row in self.facts["capabilities"]:
            _relation(row["supplier_id"], self.records["supplier"], "供应商能力")
            self._work_type(row["op_type_id"], "external")

    def _internal_capacity(self):
        if "internal" in self._computed:
            return
        self._load(_INTERNAL)
        for kind in ("op_type", "machine", "operator"):
            self._records(kind)
        self._validate_internal()
        machines = []
        for code, row in self.records["machine"].items():
            work_type = row["op_type_id"]
            if work_type is not None:
                self.linked_machines[work_type].add(code)
                if row["status"] == "active":
                    self.active_machines[work_type].add(code)
                    machines.append(SimpleNamespace(machine_id=code, op_type_id=work_type))
        qualification = OperatorQualificationService(self.conn, logger=self.logger)
        active = {code for code, status in self._statuses("operator").items() if status == "active"}
        others = sorted(set(self.records["operator"]) - active)
        if others:
            qualification.load(others)
        # The planning service remains the sole interpreter of explicit/legacy skills.
        links = qualification.eligible_links(self.facts["authorizations"], machines, active, [])
        for link in links:
            work_type = self.records["machine"][link["machine_id"]]["op_type_id"]
            self.available_operators[work_type].add(link["operator_id"])
        self._computed.add("internal")

    def _external_capacity(self):
        if "external" in self._computed:
            return
        self._load(_EXTERNAL)
        self._records("op_type")
        self._records("supplier")
        self._statuses("supplier")
        self._validate_suppliers()
        for row in list(self.records["supplier"].values()) + self.facts["capabilities"]:
            if row["op_type_id"] is not None and self.statuses["supplier"][row["supplier_id"]] == "active":
                self.available_suppliers[row["op_type_id"]].add(row["supplier_id"])
        self._computed.add("external")

    def op_type_records(self):
        self._load(["op_type", "policies"])
        self.policies = _index(self.facts["policies"], "op_type_id")
        return self._records("op_type")

    def availability(self, code):
        if self._records("op_type")[code]["category"] != "internal":
            return None
        if not self._ensure_capacity("internal"):
            return None
        return {"machines": len(self.active_machines[code]), "operators": len(self.available_operators[code]),
                "basis": AVAILABILITY_BASIS}

    def availability_issues(self, code):
        if self._records("op_type")[code]["category"] != "internal" or self._ensure_capacity("internal"):
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

    def metrics(self, kind, codes, *, scope="filtered"):
        selected = set(codes)
        if not selected.issubset(self._records(kind)):
            _invalid("资源统计范围与实际记录不一致")
        if kind == "op_type":
            counts = self._work_type_counts(selected)
        else:
            counts = self._status_counts(kind, selected)
        issues = []
        if counts.get("unknown", 0):
            issues.append({"code": "resource_status_unknown", "count": counts["unknown"],
                           "message": "存在状态或停用原因未知的旧资源，未计作启用或已明确停用。"})
        if kind == "op_type":
            categories = {self.records[kind][code]["category"] for code in selected}
            unavailable = {"internal": ["linked_machines", "available_operators", "without_machines"],
                           "external": ["available_suppliers"]}
            for category in sorted(categories & set(self._failed)):
                issues.append({"code": "resource_availability_unavailable", "message": self._failed[category],
                               "unavailable_fields": unavailable[category]})
        return {"scope": scope, "counts": counts, "basis": dict(_BASIS), "issues": issues}

    def _status_counts(self, kind, codes):
        states = ("active", "inactive", "unknown")
        if kind == "machine":
            states += ("maintain",)
        elif kind in ("operator", "supplier"):
            states += ("leave" if kind == "operator" else "pending_review",)
        counts: Dict[str, int] = dict.fromkeys(states, 0)
        statuses = self._statuses(kind)
        counts.update(Counter(statuses[code] for code in codes))
        counts["total"] = len(codes)
        if kind == "machine":
            self._load(["groups", "machine_group"])
            self.groups = _index(self.facts["groups"], "machine_id")
            groups = self._records("machine_group")
            for code in codes:
                if code in self.groups:
                    _relation(self.groups[code]["group_id"], groups, "设备分组")
            counts["groups"] = len({self.groups[code]["group_id"] for code in codes if code in self.groups})
        elif kind == "operator":
            self._load(["skills"])
            counts["skills"] = sum(row["operator_id"] in codes for row in self.facts["skills"])
        return counts

    def _work_type_counts(self, codes):
        self.op_type_records()
        if any(self.records["op_type"][code]["category"] not in ("internal", "external") for code in codes):
            _invalid("工种的自制或外协归属无效")
        internal = {code for code in codes if self.records["op_type"][code]["category"] == "internal"}
        external = codes - internal
        counts = {"total": len(codes), "internal": len(internal), "external": len(external)}
        if not internal or self._ensure_capacity("internal"):
            counts.update(self._internal_counts(internal))
        if not external or self._ensure_capacity("external"):
            counts["available_suppliers"] = len(set().union(*(self.available_suppliers[code] for code in external)))
        counts.update(self._policy_counts(external))
        return counts

    def _internal_counts(self, codes):
        return {"linked_machines": sum(len(self.linked_machines[code]) for code in codes),
                "available_operators": len(set().union(*(self.available_operators[code] for code in codes))),
                "without_machines": sum(not self.linked_machines[code] for code in codes)}

    def _policy_counts(self, external):
        if any(code in self.policies and self.policies[code]["default_merge_mode"] not in ("merged", "separate") for code in external):
            _invalid("工种周期策略无效")
        modes = Counter(self.policies[code]["default_merge_mode"] if code in self.policies else "unset" for code in external)
        return {"merged": modes["merged"], "separate": modes["separate"], "merge_mode_unset": modes["unset"]}

    def summary_metrics(self):
        groups = {kind: self._summary_group(kind) for kind in _KEYS if kind != "op_type"}
        for category in ("internal", "external"):
            groups[category + "_op_type"] = self._summary_group("op_type", category)
        return {"scope": "all", "groups": groups}

    def _summary_group(self, kind, category=None):
        try:
            records = self._records(kind)
            codes = records if category is None else [code for code, row in records.items() if row["category"] == category]
            return self.metrics(kind, codes, scope="all")
        except ResourceMetricFactsError as exc:
            return {"scope": "all", "counts": {}, "basis": dict(_BASIS),
                    "issues": [{"code": "resource_metrics_unavailable", "message": str(exc)}]}
