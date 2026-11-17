"""Evidence-only material and delivery risks. Unknown fields are not alarms."""

from collections import defaultdict

from core.models.enums import DueState
from core.models.workbench_dashboard import MAX_ROWS, bounded
from core.services.workbench.facts.preflight_checks import PreflightChecks
from core.shared.local_datetime import us_to_iso
from core.shared.stored_dates import stored_date
from core.shared.strict_parse import is_stored_number

from .material_views import current_material_views


def category(state="loaded", *, issues=None, assessed=0, unknown=0):
    return {
        "state": state,
        "assessed_count": assessed,
        "unknown_count": unknown,
        "risk_count": None,
        "known_risk_count": 0,
        "issues": issues or [],
    }


def observation(category_name, source_ref, subject, source, active, code, message, source_revision):
    return {
        "category": category_name,
        "anchor_ref": source_ref,
        "subject": subject,
        "source": source,
        "risk": {"active": active, "code": code, "message": message},
        "_guard": {"source_revision": source_revision},
    }


def _delivery_revisions(facts):
    """Per-batch lightweight source revision without cloning full schedule/operation trees."""
    tasks_by_batch = defaultdict(list)
    for row in facts.raw["Schedule"]:
        tasks_by_batch[row["batch_id"]].append(
            [row["task_ref"], us_to_iso(row["start_us"]), us_to_iso(row["end_us"])]
        )
    batches = {row["batch_id"]: row for row in facts.raw["Batches"]}
    result = {}
    for row in facts.delivery_items:
        key = row["batch_id"]
        batch = batches[key]
        result[key] = {
            "batch": [
                batch["part_no"],
                batch["part_name"],
                batch["quantity"],
                batch["due_date"],
                batch["ready_date"],
                batch["ready_status"],
                batch["status"],
                batch["priority"],
            ],
            "tasks": tasks_by_batch[key],
        }
    return result


def delivery(facts):
    items = []
    if facts.delivery_items:
        revisions = _delivery_revisions(facts)
        for row in facts.delivery_items:
            active = row["is_overdue"]
            unspecified = row["due_state"] == DueState.UNSPECIFIED.value
            source = {
                "kind": "planned_delivery",
                "batch_ref": row["batch_ref"],
                "plan_ref": facts.item_plan_ref,
                "evaluation": row,
                "time_basis": "factory_local",
                "due_boundary": "next_day_exclusive",
            }
            items.append(
                observation(
                    "delivery",
                    row["batch_ref"],
                    row["batch_id"] + " · " + (row["part_label"] or "未填写名称"),
                    source,
                    active,
                    (
                        "due_not_applicable"
                        if unspecified
                        else "planned_overdue"
                        if active
                        else "delivery_unknown"
                        if active is None
                        else "on_time"
                    ),
                    (
                        "未指定交期，交期评价不适用。"
                        if unspecified
                        else "正式计划预计超期。"
                        if active
                        else "交期或排产数据不够，还判断不了。"
                        if active is None
                        else "正式计划预计按期完成。"
                    ),
                    revisions[row["batch_id"]],
                )
            )
    if facts.plan_state != "loaded":
        return items, category(facts.plan_state, issues=facts.plan_issues)
    summary = facts.delivery["summary"]
    state = "not_applicable" if items and summary["state"] == "not_applicable" else "loaded" if items else "no_data"
    result = category(state, assessed=summary["known_due_count"], unknown=summary["unknown_due_count"])
    for key in ("due_eligible_count", "excluded_due_count", "invalid_due_count", "due_evaluation_count"):
        result[key] = summary[key]
    return items, result


class _MaterialChecks(PreflightChecks):
    """Reuse the exact readiness rule without loading unrelated resource catalogs."""

    def __init__(self, availability, requirements, stored_batches):
        self.availability = availability
        self.requirements = defaultdict(list)
        for row in requirements:
            self.requirements[row["batch_id"]].append(row)
        self.stored_batches = {row["batch_id"]: row for row in stored_batches}
        self._batch_reviewed = {}
        self._unreviewed_readiness = {}

    def readiness(self, batch, day):
        return super().readiness(self.stored_batches[batch["batch_id"]], day)


def _material_requirement(row, value, material_refs):
    required, available, status = row["required_qty"], row["available_qty"], row["ready_status"]
    labels = {key: value[key] if value and type(value[key]) is str else None for key in ("name", "unit")}
    return {
        "material_ref": material_refs[row["material_id"]].ref if value else None,
        "business_code": row["material_id"],
        "label": labels["name"],
        "unit": labels["unit"],
        "required_quantity": required,
        "available_quantity": available,
        "ready_status": status,
    }, (value is None or required is None or available is None or status is None)


def _material_batch(batch, checks, day, refs, by_material, material_refs):
    batch_id = batch["batch_id"]
    reasons = checks.readiness(batch, day)
    rows = checks.requirements[batch_id]
    projected = [_material_requirement(row, by_material.get(row["material_id"]), material_refs) for row in rows]
    status = batch["ready_status"]
    unknown = status is None or any(bad for _, bad in projected)
    active = None if unknown else bool(reasons)
    batch_identity = refs[batch_id]
    ref = batch_identity.ref
    source = {
        "kind": "batch_readiness",
        "batch_ref": ref,
        "batch_id": batch_id,
        "stored_status": batch["status"],
        "ready_status": status,
        "ready_date": stored_date(batch["ready_date"]),
        "due_date": stored_date(batch["due_date"]),
        "quantity": batch["quantity"] if is_stored_number(batch["quantity"], integer=True) else None,
        "requirements": [row for row, _ in projected],
        "readiness_issues": reasons,
        "basis": "batch_material_requirements_not_stock",
    }
    code, message = {
        None: ("readiness_unknown", "齐套数据读不完整，算不出缺多少，也不能当作齐套。"),
        True: ("not_ready", "批次或已登记物料需求尚未确认齐套。"),
        False: ("ready", "当前齐套检查无缺口。"),
    }[active]
    label = batch["part_name"] if type(batch["part_name"]) is str else "未填写名称"
    stored_batch = checks.stored_batches[batch_id]
    availability = checks.availability
    source_revision = {
        "batch_revision": batch_identity.revision,
        "batch": [
            stored_batch["part_no"],
            stored_batch["part_name"],
            stored_batch["quantity"],
            stored_batch["due_date"],
            stored_batch["ready_date"],
            stored_batch["ready_status"],
            stored_batch["status"],
            stored_batch["priority"],
        ],
        "requirements": [
            [
                req["id"],
                req["material_id"],
                req["required_qty"],
                req["available_qty"],
                req["ready_status"],
                availability.reviews.get(req["id"]),
                [[arr["id"], arr["arrival_date"], arr["quantity"]] for arr in availability.arrivals.get(req["id"], ())],
                material_refs[req["material_id"]].revision if req["material_id"] in by_material else None,
            ]
            for req in availability.requirements[batch_id]
        ],
    }
    return observation("material", ref, batch_id + " · " + label, source, active, code, message, source_revision)


def safe_material(facts):
    materials = facts.raw["Materials"]
    day = facts.now.date().isoformat()
    batches, requirements, availability = current_material_views(facts.raw, day)
    bounded(batches, MAX_ROWS)
    refs, batch_issue = facts.valid_entity_refs("batch", [row["batch_id"] for row in batches])
    material_refs, material_issue = facts.valid_entity_refs("material", [row["material_id"] for row in materials])
    by_material = {row["material_id"]: row for row in materials}
    checks = _MaterialChecks(availability, requirements, facts.raw["Batches"])
    items = [
        _material_batch(batch, checks, day, refs, by_material, material_refs)
        for batch in batches
        if batch["batch_id"] in refs
        and all(
            req["material_id"] not in by_material or req["material_id"] in material_refs
            for req in checks.requirements[batch["batch_id"]]
        )
    ]
    issue = batch_issue or material_issue
    if issue is not None:
        return items, category("unavailable", issues=[issue])
    unknown = sum(row["risk"]["active"] is None for row in items)
    return items, category("loaded" if items else "no_data", assessed=len(items) - unknown, unknown=unknown)
