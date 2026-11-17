"""Run-journal rulings for immutable admission lineage."""

from core.models.content import read_stored_json
from core.models.workbench_command import WorkbenchCommandRejected


def require_admission(repo, row):
    """The run row must be the one its scheduling.run command receipt admitted."""
    receipt = repo.admission_receipt(row["request_key"])
    if (receipt is None or receipt[0] != "scheduling.run" or receipt[1] != row["input_ref"]
            or read_stored_json(receipt[2], dict)["data"] != {"run_ref": row["run_ref"]}):
        raise WorkbenchCommandRejected("run_result_inconsistent", "这次排产没有一致的接收结果记录，请让维护人员核对排产记录。", 500)
