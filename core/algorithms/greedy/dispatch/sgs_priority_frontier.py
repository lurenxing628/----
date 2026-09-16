"""Maintain unique graph priorities across picks instead of sorting the whole ready set.

Only certified, fixed-resource large decodes use this path. The head still receives
the ordinary dynamic score. If it is penalized, score the full ready set, preserving
the feasibility-first contract. Small, tied and callback-bearing inputs are unchanged.
"""

import heapq


class PriorityReadyQueue:
    def __init__(self, graph, pruning):
        self.graph, self.pruning = graph, pruning
        self.keys = graph["graph_priority_key_by_op_id"]
        self.queued = set(graph["ready_op_ids"])
        self.heap = [(self.keys[op_id], op_id) for op_id in self.queued]
        heapq.heapify(self.heap)

    def head(self, blocked_batches):
        for kind, record in self.pruning.examples.items():
            if not self.pruning.guards[kind](record):
                return None
        while self.heap:
            _key, op_id = self.heap[0]
            batch_id, op = self.graph["op_by_id"][op_id]
            if op_id in self.graph["ready_op_ids"] and batch_id not in blocked_batches:
                return [(batch_id, op)]
            heapq.heappop(self.heap)
        return []

    def after_pick(self, op_id):
        for successor in self.graph["successor_op_ids_by_op_id"].get(op_id, ()):
            if successor in self.graph["ready_op_ids"] and successor not in self.queued:
                self.queued.add(successor)
                heapq.heappush(self.heap, (self.keys[successor], successor))


def make_priority_queue(graph, pruning):
    if graph is None or pruning is None or not pruning.supported or len(graph["op_by_id"]) < 128:
        return None
    keys = graph["graph_priority_key_by_op_id"]
    if len(set(keys.values())) != len(keys):
        return None
    return PriorityReadyQueue(graph, pruning)


def score_next_ready(queue, *, collect, score, native, blocked_batches, cache):
    candidates = queue.head(blocked_batches) if queue is not None and native() else None
    narrowed = candidates is not None
    if candidates is None:
        candidates = collect()
    if not candidates:
        return []
    scored = score(candidates)
    if narrowed:
        if not any(row[0][0] == 0.0 for row in scored):
            return score(collect())
        cache.graph_candidates_pruned += max(len(queue.graph["ready_op_ids"]) - len(candidates), 0)
    return scored


__all__ = ["make_priority_queue", "score_next_ready"]
