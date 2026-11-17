"""Current-day material projection; dated arrivals never require a write-on-read."""

from core.services.material.stage_availability import MaterialReadiness


def _public(amount):
    return None if amount is None else float(amount)


def current_material_views(raw, day):
    """Each requirement shows the amounts readiness admitted (None when unknown), never the stored columns."""
    availability = MaterialReadiness.from_tables(raw)
    batches, requirements = [], []
    for batch in raw["Batches"]:
        diagnosis = availability.readiness_diagnostics(batch, day)
        batches.append(dict(batch, ready_status=diagnosis["status"]))
        for row in availability.requirements[batch["batch_id"]]:
            item = diagnosis["requirements"][row["id"]]
            # A reviewed batch's status is None exactly when a problem leaves its readiness unknown.
            status = ((None if diagnosis["status"] is None else "yes" if item["ready"] else "no")
                      if row["id"] in availability.reviews else row["ready_status"])
            requirements.append(dict(row, required_qty=_public(item["required"]), available_qty=_public(item["available"]),
                                     ready_status=status))
    return batches, requirements, availability
