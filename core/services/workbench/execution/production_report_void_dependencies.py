"""Previously adopted quota samples remain explicit dependencies of a report."""

from typing import NoReturn

from core.models.content import StoredJsonCorrupt, read_stored_json
from core.models.workbench_execution_input import MAX_REPORT_BYTES, reject
from data.repositories.workbench_report_validation_repo import WorkbenchReportValidationRepository


def _corrupt_evidence() -> NoReturn:
    reject("关联的工时定额采用依据损坏，未执行撤销。", "storage_failure", 500)


def adopted_quota_impacts(conn, report_ref, operation_ref):
    rows = WorkbenchReportValidationRepository(conn).calibration_adoptions_mentioning(report_ref)
    if len(rows) > 10000:
        reject("关联的定额采用记录超过读取上限，未执行撤销。", "query_too_large", 413)
    total, impacts = 0, []
    for row in rows:
        text = row["evidence_json"]
        # 先累计字节再解码，超限的不解码；量之前要是文本，不是文本就是存储损坏，与解码失败同一种错误。
        if type(text) is not str:
            raise StoredJsonCorrupt()
        total += len(text.encode("utf-8"))
        if total > MAX_REPORT_BYTES:
            reject("关联的定额依据超过读取上限，未执行撤销。", "query_too_large", 413)
        evidence = read_stored_json(text, dict)
        samples = evidence.get("samples")
        if not isinstance(samples, list) or any(not isinstance(sample, dict) or not isinstance(sample.get("report_refs"), list) for sample in samples):
            _corrupt_evidence()
        if any(report_ref in sample["report_refs"] for sample in samples):
            impacts.append({"code": "adopted_quota_report_required", "operation_ref": operation_ref,
                            "adoption_ref": row["adoption_ref"], "template_operation_ref": row["template_operation_ref"],
                            "operation_label": "已采用的工时定额", "message": "这次报工已用于采用并锁定的工时定额，需先处理该定额的采用记录"})
    return impacts
