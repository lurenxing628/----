"""Service-side rulings over calibration adoption storage facts; the repository only reads and writes."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import public_ref
from core.models.workbench_template_lineage import snapshot
from core.services.process.template_hours import ProcessTemplateHours


def require_template(repo, template_operation_ref):
    public_ref(template_operation_ref)
    row = repo.template(template_operation_ref)
    if row is None:
        raise WorkbenchCommandRejected("entity_not_found", "模板永久引用已失效或不存在，不能按图号和序号重新绑定。", 404)
    if row["part_ref"] is None:
        raise WorkbenchCommandRejected("calibration_source_unavailable", "模板所属零件的永久身份缺失，未按图号补配。")
    return row


def adopt_checked_quota(repo, template, value):
    """Use the shared current-template hours writer in the adoption transaction."""
    if not repo.conn.in_transaction:
        raise RuntimeError("Quota adoption requires the caller write transaction.")
    ProcessTemplateHours(repo.conn).revise(template["template_operation_ref"], {"unit_hours": value},
                                          expected_revision=template["template_revision"])
    after = require_template(repo, template["template_operation_ref"])
    expected = {**template, "unit_hours": after["unit_hours"], "template_revision": after["template_revision"]}
    revision = template["template_revision"] + int(template["unit_hours"] != value)
    if snapshot(after) != snapshot(expected) or after["unit_hours"] != value or after["template_revision"] != revision:
        raise RuntimeError("Template adoption changed unexpected facts or failed to advance identity revision.")
    return after
