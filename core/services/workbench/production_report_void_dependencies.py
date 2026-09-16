"""Previously adopted quota samples remain explicit dependencies of a report."""

import json

from core.models.workbench_execution_input import MAX_REPORT_BYTES, reject


def adopted_quota_impacts(conn, report_ref, operation_ref):
    # Pre-adoption isolated ledgers have no quota adoption capability. Production
    # startup separately requires the complete current migration contract.
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='WorkbenchCalibrationAdoptions'").fetchone():
        return []
    rows = conn.execute("""SELECT adoption_ref, template_operation_ref, evidence_json
        FROM WorkbenchCalibrationAdoptions WHERE instr(evidence_json,?)>0 ORDER BY adoption_ref LIMIT 10001""", (report_ref,)).fetchall()
    if len(rows) > 10000:
        reject("关联的定额采用记录超过读取上限，未执行撤销。", "query_too_large", 413)
    total, impacts = 0, []
    for row in rows:
        text = row["evidence_json"]
        if not isinstance(text, str):
            reject("关联的工时定额采用依据损坏，未执行撤销。", "storage_failure", 500)
        total += len(text.encode("utf-8"))
        if total > MAX_REPORT_BYTES:
            reject("关联的定额依据超过读取上限，未执行撤销。", "query_too_large", 413)
        try:
            evidence = json.loads(text)
            samples = evidence["samples"]
            if not isinstance(samples, list) or any(not isinstance(sample, dict) or not isinstance(sample.get("report_refs"), list) for sample in samples):
                raise ValueError("Invalid adopted sample list")
        except (ValueError, TypeError, KeyError):
            reject("关联的工时定额采用依据损坏，未执行撤销。", "storage_failure", 500)
        if any(report_ref in sample["report_refs"] for sample in samples):
            impacts.append({"code": "adopted_quota_report_required", "operation_ref": operation_ref,
                            "adoption_ref": row["adoption_ref"], "template_operation_ref": row["template_operation_ref"],
                            "operation_label": "已采用的工时定额", "message": "这次报工已用于采用并锁定的工时定额，需先处理该定额的采用记录"})
    return impacts
