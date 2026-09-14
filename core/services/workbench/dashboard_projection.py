"""Evidence-only material and delivery risks. Unknown fields are not alarms."""

from collections import defaultdict

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_ROWS, bounded
from core.services.workbench.dashboard_facts import source_issue, typed
from core.services.workbench.preflight_checks import PreflightChecks, number, stored_date


def category(state="loaded", *, issues=None, assessed=0, unknown=0):
    return {"state": state, "assessed_count": assessed, "unknown_count": unknown,
            "risk_count": None, "known_risk_count": 0, "issues": issues or []}


def observation(category_name, source_ref, subject, source, active, code, message, facts):
    return {"category": category_name, "anchor_ref": source_ref, "subject": subject,
            "source": source, "risk": {"active": active, "code": code, "message": message}, "_facts": typed(facts)}


def delivery(facts):
    if facts.plan_state != "loaded":
        return [], category(facts.plan_state, issues=facts.plan_issues)
    items = []
    by_batch = defaultdict(list)
    for row in facts.delivery_facts["tasks"]:
        by_batch[row["batch_id"]].append(row)
    batches = {row["batch_id"]: row for row in facts.raw["Batches"] or []}
    for row in facts.delivery["items"]:
        active = row["is_overdue"]
        source = {"kind": "planned_delivery", "batch_ref": row["batch_ref"], "plan_ref": facts.plan["plan_ref"],
                  "evaluation": row, "time_basis": "factory_local", "due_boundary": "next_day_exclusive"}
        items.append(observation("delivery", row["batch_ref"], row["batch_id"] + " · " + (row["part_label"] or "未填写名称"),
                                 source, active, "planned_overdue" if active else "delivery_unknown" if active is None else "on_time",
                                 "正式计划预计超期。" if active else "交期或排产数据不够，还判断不了。" if active is None else "正式计划预计按期完成。",
                                 {"batch": batches.get(row["batch_id"]), "tasks": by_batch[row["batch_id"]],
                                  "completion_record": facts.delivery_facts["completion_record"]}))
    unknown = sum(row["risk"]["active"] is None for row in items)
    return items, category("loaded" if items else "no_data", assessed=len(items) - unknown, unknown=unknown)


class _MaterialChecks(PreflightChecks):
    """Reuse the exact readiness rule without loading unrelated resource catalogs."""

    def __init__(self, requirements):
        self.materials = defaultdict(list)
        for row in requirements:
            self.materials[row["batch_id"]].append(row)


def _material_requirement(row, value, material_refs):
    required = row["required_qty"] if number(row["required_qty"], positive=True) else None
    available = row["available_qty"] if number(row["available_qty"]) else None
    status = row["ready_status"] if row["ready_status"] in ("yes", "no", "partial") else None
    labels = {key: value[key] if value and type(value[key]) is str else None for key in ("name", "unit")}
    return {"material_ref": material_refs[row["material_id"]]["ref"] if value else None,
            "business_code": row["material_id"], "label": labels["name"], "unit": labels["unit"],
            "required_quantity": required, "available_quantity": available, "ready_status": status}, (
                value is None or required is None or available is None or status is None)


def _material_batch(batch, checks, refs, by_material, material_refs):
    reasons = checks.readiness(batch, True)
    rows = checks.materials[batch["batch_id"]]
    projected = [_material_requirement(row, by_material.get(row["material_id"]), material_refs) for row in rows]
    status = batch["ready_status"] if batch["ready_status"] in ("yes", "no", "partial") else None
    unknown = status is None or batch["status"] not in ("pending", "scheduled", "processing", "completed") or any(bad for _, bad in projected)
    active = None if unknown else bool(reasons)
    ref = refs[batch["batch_id"]]["ref"]
    source = {"kind": "batch_readiness", "batch_ref": ref, "batch_id": batch["batch_id"],
              "stored_status": batch["status"] if type(batch["status"]) is str else None, "ready_status": status,
              "ready_date": stored_date(batch["ready_date"]), "due_date": stored_date(batch["due_date"]),
              "quantity": batch["quantity"] if number(batch["quantity"], integer=True) else None,
              "requirements": [row for row, _ in projected], "readiness_issues": reasons, "basis": "batch_material_requirements_not_stock"}
    code, message = {None: ("readiness_unknown", "齐套数据读不完整，算不出缺多少，也不能认定已齐套。"),
                     True: ("not_ready", "批次或已登记物料需求尚未确认齐套。"),
                     False: ("ready", "当前齐套检查无缺口（不等于排产就绪）。")}[active]
    label = batch["part_name"] if type(batch["part_name"]) is str else "未填写名称"
    return observation("material", ref, batch["batch_id"] + " · " + label, source, active, code, message,
                       {"batch": batch, "requirements": rows, "identity": refs[batch["batch_id"]],
                        "materials": [by_material.get(row["material_id"]) for row in rows]})


def material(facts):
    batches, requirements, materials = (facts.raw[key] for key in ("Batches", "BatchMaterials", "Materials"))
    if any(value is None for value in (batches, requirements, materials)):
        return [], category("unavailable", issues=[source_issue("source_not_read", "批次或物料需求来源尚未读取，齐套风险未知。")])
    bounded(batches, MAX_ROWS)
    refs = facts.repo.entity_refs("batch", [row["batch_id"] for row in batches])
    facts.raw["material_batch_refs"] = refs
    material_refs = facts.repo.entity_refs("material", [row["material_id"] for row in materials])
    facts.raw["material_refs"] = material_refs
    by_material = {row["material_id"]: row for row in materials}
    checks = _MaterialChecks(requirements)
    items = [_material_batch(batch, checks, refs, by_material, material_refs) for batch in batches]
    unknown = sum(row["risk"]["active"] is None for row in items)
    return items, category("loaded" if items else "no_data", assessed=len(items) - unknown, unknown=unknown)


def safe_material(facts):
    try:
        return material(facts)
    except WorkbenchCommandRejected as exc:
        if exc.code != "identity_missing":
            raise
        return [], category("unavailable", issues=[source_issue(exc.code, str(exc))])
