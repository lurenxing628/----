"""Bind retained requirements to their last official saved calculation source."""

from core.services.scheduler.run.operation_effort import build_operation_efforts


def _missing(message):
    return {
        "data_gaps": [
            {
                "field": "saved_runtime_requirement",
                "code": "runtime_requirement_source_missing",
                "message": message,
            }
        ]
    }


def saved_seed_efforts(facts, seed_results, execution_facts):
    """Read original run/trial work once per actual official version, without math."""
    if not seed_results:
        return {}
    result, sources = {}, {}
    for seed in seed_results:
        op_id = seed["op_id"]
        fact = execution_facts.get(op_id)
        version = fact.schedule_version if fact is not None else None
        if version not in sources:
            if type(version) is not int:
                sources[version] = None
            else:
                context = facts.official_source(version)
                sources[version] = context["documents"].operation_effort if context is not None else None
        source = sources[version]
        ref = facts.operation_refs.get(op_id)
        item = source.get(ref) if source is not None else None
        if item is not None:
            result[op_id] = item
        else:
            result[op_id] = _missing("原样保留安排的实际需求账缺失；保留原安排，准备和加工分解列为缺项。")
    return result


def prepare_operation_efforts(*, facts, operations, batches, algo_ops, seeds, execution_facts, projections):
    return build_operation_efforts(
        operations=operations,
        batches=batches,
        algo_operations=algo_ops,
        operations_to_schedule=seeds.to_schedule,
        seed_results=seeds.seed_results,
        execution_facts=execution_facts,
        execution_projections={op.id: projections[facts.operation_refs[op.id]] for op in operations},
        saved_efforts=saved_seed_efforts(facts, seeds.seed_results, execution_facts),
    )
