"""Current-day material projection; dated arrivals never require a write-on-read."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.material.stage_availability import MaterialAvailability, quantity


def current_material_views(raw, day):
    names = ("BatchMaterialReviews", "BatchMaterialArrivals")
    version = raw.get("SchemaVersion") or []
    if not version or (version[0]["version"] >= 36 and any(raw.get(name) is None for name in names)):
        return None
    availability = MaterialAvailability({"BatchMaterials": raw["BatchMaterials"],
        **{name: raw.get(name) or [] for name in names}})
    batches, requirements = [], []
    for batch in raw["Batches"]:
        status, problems = availability.readiness_state(batch, day)
        batches.append(dict(batch, ready_status=status))
        for row in availability.requirements[batch["batch_id"]]:
            view = dict(row)
            if row["id"] in availability.reviews:
                try:
                    amount = availability.available(row, day)
                    view.update(available_qty=float(amount), ready_status="yes" if amount >= quantity(row["required_qty"], positive=True) else "no")
                except WorkbenchCommandRejected:
                    # The public row retains an explicit unknown quantity; it is never a ready fact.
                    view.update(available_qty=None, ready_status=None)
                if problems:
                    view["ready_status"] = None
            requirements.append(view)
    return batches, requirements
