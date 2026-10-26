"""Per-decode acceleration state: priority frontier, checkpoint capture and tail reuse."""

from types import FunctionType, MethodType

from . import sgs_dispatch_step
from .sgs_checkpoint import plan_decode_checkpoints
from .sgs_priority_frontier import make_priority_queue

_SCHEDULE_OPERATION = sgs_dispatch_step.schedule_op


def pristine_functions(module):
    """Snapshot a module's plain functions at import time so the certificate can spot replacements later."""
    return {name: value for name, value in vars(module).items() if type(value) is FunctionType}


def dispatch_certificate(scheduler, context, scheduler_guard, context_guard, guarded_module, guarded_functions):
    """The caller names the module whose functions must stay pristine; dispatch never imports its parent package."""
    def current():
        if not scheduler_guard(scheduler) or not context_guard(context):
            return False
        callback = context.internal_callback
        if type(callback) is not MethodType or callback.__self__ is not scheduler:
            return False
        if callback.__func__ is not vars(type(scheduler)).get("_schedule_internal"):
            return False
        if callback.__func__.__globals__.get("schedule_internal_operation") is not guarded_functions["schedule_internal_operation"]:
            return False
        return (sgs_dispatch_step.schedule_op is _SCHEDULE_OPERATION
                and all(vars(guarded_module).get(name) is function for name, function in guarded_functions.items()))

    return current


class DecodeAcceleration:
    def __init__(self, request, graph, pruning, hours, context, *, resume):
        self.plan = plan_decode_checkpoints(request, graph_state=graph, resume=resume)
        self.frontier = make_priority_queue(graph, pruning)
        # A decode without a checkpoint request has no tail to reuse.
        self.tail = request.tail_reuse if request is not None else None
        self.dispatch_guard = context.checkpoint_dispatch_guard
        # Tail reuse compares run state only; the auto-assign demand window is not part of it, so
        # the suffix is only proved for decodes where every operation names its resources.
        self.tail_eligible = (self.tail is not None and pruning is not None and pruning.supported
                              and pruning.fixed_resources and all(value > 0 for value in hours.values()))

    def record(self, op_id, position, *, state, next_idx, graph, native_dispatch):
        if self.frontier is not None:
            self.frontier.after_pick(op_id)
        if self.plan is not None:
            self.plan.record(op_id, position, state=state, next_idx=next_idx, graph_state=graph)
        if self.tail is None:
            return False
        guard = self.dispatch_guard
        if self.tail_eligible and native_dispatch and guard is not None:
            eligible = guard() if position in self.tail.checkpoints else True
        else:
            eligible = False
        return self.tail.try_complete(position, state=state, next_idx=next_idx, graph_state=graph, eligible=eligible)


__all__ = ["DecodeAcceleration", "dispatch_certificate"]
