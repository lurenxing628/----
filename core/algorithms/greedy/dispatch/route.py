"""Dispatch-mode routing with the scheduler's current callback bindings."""

from core.errors import ValidationError

from .batch_order import dispatch_batch_order
from .sgs import dispatch_sgs


def dispatch_run(ctx, *, state, sorted_ops, batches, batch_order, params, machine_downtimes,
                 resource_pool, graph_ready_context,
                 decode_resume=None, decode_checkpoints=None) -> None:
    if graph_ready_context is not None and params.dispatch_mode_key != "sgs":
        raise ValidationError("图 ready 队列只能在 SGS 派工模式下启用。", field="graph_ready_context")
    if (decode_resume is not None or decode_checkpoints is not None) and (
            params.dispatch_mode_key != "sgs" or graph_ready_context is None):
        raise ValidationError("解码断点只支持图模式下的 SGS 派工。", field="decode_checkpoint",
                              details={"reason": "decode_checkpoint_requires_graph_mode"})
    common = dict(
        sorted_ops=sorted_ops,
        batches=batches,
        end_dt_exclusive=params.end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        state=state,
        auto_assign_enabled=params.auto_assign_enabled,
        resource_pool=resource_pool,
    )
    if params.dispatch_mode_key != "sgs":
        dispatch_batch_order(ctx, **common, base_time=params.base_time)
        return
    dispatch_sgs(ctx, **common, batch_order=batch_order, dispatch_rule=params.dispatch_rule_spec,
                 graph_ready_context=graph_ready_context,
                 decode_resume=decode_resume, decode_checkpoints=decode_checkpoints)
