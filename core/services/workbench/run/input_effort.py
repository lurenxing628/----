"""Bind retained requirements to their last official saved calculation source."""

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts
from core.services.workbench.facts.run_input_rows import fail


def _missing(message):
    return {"data_gaps": [{"field": "saved_runtime_requirement", "code": "runtime_requirement_source_missing", "message": message}]}


def saved_seed_efforts(svc, facts, seed_results, execution_facts):
    """Read original run/trial work once per actual official version, without math."""
    if not seed_results:
        return {}
    result, sources = {}, {}
    with read_evidence_scope(svc.conn):
        for seed in seed_results:
            op_id = seed["op_id"]
            fact = execution_facts.get(op_id)
            version = fact.schedule_version if fact is not None else None
            if version not in sources:
                if type(version) is not int:
                    sources[version] = None
                else:
                    try:
                        context = facts.official_source(version)
                    except WorkbenchCommandRejected as exc:
                        if exc.code not in ("adoption_snapshot_invalid", "adoption_source_archived", "entity_not_found"):
                            raise
                        context = {"operation_effort": None}
                    sources[version] = saved_operation_efforts(context.get("operation_effort")) if context is not None else None
            source = sources[version]
            ref = facts.operation_refs.get(op_id)
            item = source.get(ref) if source is not None else None
            if item is not None and item["op_id"] != op_id:
                fail("runtime_effort_identity_mismatch", "原保存需求与工序永久身份不一致，这次排产没有开始。", op_id=op_id)
            if item is not None:
                result[op_id] = item
            else:
                result[op_id] = _missing("原样保留安排的实际需求账缺失；保留原安排，准备和加工分解列为缺项。")
    return result
