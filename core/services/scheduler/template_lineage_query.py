"""Shared template lineage evaluation over 6-column origins and active operation identities."""

from core.models.workbench_calibration import issue
from data.repositories.workbench_template_lineage_repo import WorkbenchTemplateLineageRepository


def lineage_problems(*, source_eligible, operation_active, instance_modified):
    reasons = []
    if not source_eligible:
        reasons.append(
            issue(
                "template_copy_source_unqualified",
                "复制来源那道工序的模板来源已失效或已撤回，复制过来的这道工序也不能当作可用的完工记录。",
            )
        )
    if not operation_active:
        reasons.append(
            issue(
                "template_instance_retired",
                "原来那道工序已删除或被替换，不会改指同号的新工序，不再用于校准。",
            )
        )
    if instance_modified:
        reasons.append(
            issue(
                "template_instance_modified",
                "这道工序的工艺资料或所属批次改过，即使改回原值也不能当作可用的完工记录。",
            )
        )
    return reasons


def _read_origins(repo, refs):
    return {row["operation_ref"]: row for row in repo.origin_rows(refs)}


def _evaluate(origins):
    problems = {
        ref: lineage_problems(
            source_eligible=bool(origin["source_eligible"]),
            operation_active=bool(origin["operation_active"]),
            instance_modified=bool(origin["instance_modified"]),
        )
        for ref, origin in origins.items()
    }
    return {
        "origins": origins,
        "problems": problems,
    }


class TemplateLineageQuery:
    def __init__(self, conn, repo=None):
        self.repo = repo if repo is not None else WorkbenchTemplateLineageRepository(conn)

    @classmethod
    def capture_partial_facts(cls, conn, operation_refs, *, current_by_ref):
        origins = _read_origins(cls(conn).repo, operation_refs)
        return {
            "origins": origins,
            "source_instances": current_by_ref,
        }

    def read(self, operation_refs):
        origins = _read_origins(self.repo, operation_refs)
        return _evaluate(origins)

    def read_captured(self, captured):
        return _evaluate(captured["origins"])
