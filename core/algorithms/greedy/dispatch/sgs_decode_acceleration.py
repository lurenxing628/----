"""Per-decode acceleration state: priority frontier, checkpoint capture and tail reuse."""

from .sgs_checkpoint import plan_decode_checkpoints
from .sgs_priority_frontier import make_priority_queue


class DecodeAcceleration:
    def __init__(self, request, graph, pruning, hours, *, resume):
        self.plan = plan_decode_checkpoints(request, graph_state=graph, resume=resume)
        self.frontier = make_priority_queue(graph, pruning)
        # A decode without a checkpoint request has no tail to reuse.
        self.tail = request.tail_reuse if request is not None else None
        # Tail reuse compares run state only; the auto-assign demand window is not part of it, so
        # the suffix is only proved for decodes where every operation names its resources.
        self.tail_eligible = (self.tail is not None and pruning is not None and pruning.supported
                              and pruning.fixed_resources and all(value > 0 for value in hours.values()))

    def record(self, op_id, position, *, state, next_idx, graph):
        if self.frontier is not None:
            self.frontier.after_pick(op_id)
        if self.plan is not None:
            self.plan.record(op_id, position, state=state, next_idx=next_idx, graph_state=graph)
        if self.tail is None:
            return False
        return self.tail.try_complete(position, state=state, next_idx=next_idx, graph_state=graph,
                                      eligible=self.tail_eligible)


__all__ = ["DecodeAcceleration"]
