"""Large-order checkpoint capture and exact tail-reuse requests."""

from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpointRequest
from core.algorithms.greedy.dispatch.sgs_checkpoint_tail import DecodeTailReuse

from .optimizer_graph_ready_iterated_greedy_checkpoints import CheckpointStore, checkpoint_positions


class TailCheckpointStore(CheckpointStore):
    def request_for(self, size):
        if not self.enabled or size <= 1:
            return None, []
        captured = []
        # The complete reference supplies the unchanged suffix; intermediate
        # snapshots remain bounded by the configured checkpoint count.
        positions = checkpoint_positions(size, self.count) + [size]
        return DecodeCheckpointRequest(positions, captured.append), captured


def trial_request(reference, *, resume, budget):
    if budget is not None:
        budget.last_pick_check = 0
    check = budget.check_pick if budget is not None else None
    tail = DecodeTailReuse(reference.checkpoints, check_budget=check) if resume is not None else None
    positions = [item.position for item in reference.checkpoints] or [len(reference.order)]
    return DecodeCheckpointRequest(positions, lambda checkpoint: None, tail_reuse=tail, check_budget=check)


__all__ = ["TailCheckpointStore", "trial_request"]
