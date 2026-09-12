"""Dispatch-mode routing with the scheduler's current callback bindings."""

from core.infrastructure.errors import ValidationError


def dispatch_run(ctx, *, state, sorted_ops, batches, batch_order, params, machine_downtimes,
                 resource_pool, graph_ready_context, strict_mode, batch_dispatch, sgs_dispatch):
    if graph_ready_context is not None and params.dispatch_mode_key != "sgs":
        raise ValidationError("图 ready 队列只能在 SGS 派工模式下启用。", field="graph_ready_context")
    common = dict(
        sorted_ops=sorted_ops,
        batches=batches,
        base_time=params.base_time,
        end_dt_exclusive=params.end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        state=state,
        auto_assign_enabled=params.auto_assign_enabled,
        resource_pool=resource_pool,
        strict_mode=strict_mode,
    )
    if params.dispatch_mode_key != "sgs":
        return batch_dispatch(ctx, **common)
    return sgs_dispatch(ctx, **common, batch_order=batch_order, dispatch_rule=params.dispatch_rule_enum,
                        graph_ready_context=graph_ready_context)
