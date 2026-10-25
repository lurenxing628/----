"""Service-side rulings over calibration adoption storage facts; the repository only reads and writes."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.template_hours import ProcessTemplateHours


def require_template(repo, template_operation_ref):
    row = repo.template(template_operation_ref)
    if row is None:
        raise WorkbenchCommandRejected("entity_not_found", "模板永久引用已失效或不存在，不能按图号和序号重新绑定。", 404)
    if row["part_ref"] is None:
        raise WorkbenchCommandRejected("calibration_source_unavailable", "模板所属零件的永久身份缺失，未按图号补配。")
    return row


def adopt_checked_quota(repo, template, value):
    """Use the shared current-template hours writer in the adoption transaction."""
    current = {**template, "ref": template["template_operation_ref"], "revision": template["template_revision"]}
    ProcessTemplateHours(repo.conn).revise_current(current, {"unit_hours": value},
                                                  expected_revision=template["template_revision"])
    revision = template["template_revision"] + int(template["unit_hours"] != value)
    return {**template, "unit_hours": value, "template_revision": revision}
