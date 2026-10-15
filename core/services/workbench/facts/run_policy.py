"""Run-journal rulings for schema availability and immutable admission lineage."""

import json

from core.models.workbench_command import WorkbenchCommandRejected


def require_run_schema(repo):
    if repo.schema_issues():
        raise WorkbenchCommandRejected("run_schema_unavailable", "排产记录结构不完整，请联系维护人员。", 503)


def require_admission(repo, row):
    """The run row must be the one its scheduling.run command receipt admitted."""
    receipt = repo.admission_receipt(row["request_key"])
    if (receipt is None or receipt[0] != "scheduling.run" or receipt[1] != row["input_ref"]
            or json.loads(receipt[2])["data"] != {"run_ref": row["run_ref"]}):
        raise WorkbenchCommandRejected("run_result_inconsistent", "这次排产没有一致的接收结果记录，请让维护人员核对排产记录。", 500)
