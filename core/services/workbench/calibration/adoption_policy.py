"""Service-side rulings over calibration adoption storage facts; the repository only reads and writes."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.template_hours import ProcessTemplateHours

from .facts import to_calibration_template


def require_template(repo, template_operation_ref):
    row = repo.template(template_operation_ref)
    if row is None:
        raise WorkbenchCommandRejected("entity_not_found", "模板永久引用已失效或不存在，不能按图号和序号重新绑定。", 404)
    template = {key: value for key, value in row.items() if key != "part_name"}
    cal_template = to_calibration_template(
        {
            **row,
            "operation_ref": row["template_operation_ref"],
            "revision": row["template_revision"],
        }
    )
    return template, cal_template


def adopt_checked_quota(repo, template, value):
    """Use the shared current-template hours writer in the adoption transaction."""
    changed = template["unit_hours"] != value
    current = {**template, "ref": template["template_operation_ref"], "revision": template["template_revision"]}
    ProcessTemplateHours(repo.conn).revise_current(current, {"unit_hours": value})
    revision = template["template_revision"] + int(changed)
    return {
        **template,
        "unit_hours": value,
        "template_revision": revision,
        "hours_confirmed_at": None if changed else template["hours_confirmed_at"],
    }
