"""Account for admitted repair portfolios while profiles keep adding parents and basis variants."""
from __future__ import annotations

from typing import Any, Dict, Iterable


class RepairWorkAccounting:
    def __init__(self) -> None:
        # Hold objects, not only ids: their neighborhood may gain a basis variant between tasks.
        self.elites: Dict[int, Dict[str, Any]] = {}

    def observe(self, elites: Iterable[Dict[str, Any]]) -> None:
        for elite in elites:
            self.elites[id(elite)] = elite

    def finish(self, pool: Any) -> None:
        if pool.limits.enabled:
            # Newly selected parents that never got a task are pending work, not top-k exclusions.
            self.observe(pool.elites)
        report, pruning = pool.report, pool.report["repair_pruning_report"]
        parents = list(pool.parents_by_fingerprint.values())
        excluded = [elite for elite in parents if id(elite) not in self.elites]
        counts = [(elite["neighborhood"].candidate_count, elite.get("decision_offset", 0)) for elite in self.elites.values()]
        if any(consumed < 0 or consumed > total for total, consumed in counts):
            raise ValueError("repair portfolio consumed count is outside its materialized candidate space")
        if sum(consumed for _total, consumed in counts) != pruning["generated_candidates"]:
            raise ValueError("repair generated count disagrees with admitted portfolio offsets")
        report["selected_elites"] = len(parents) - len(excluded)
        report["selected_elites_scope"] = "cumulative_profile_parents_admitted_during_rotation"
        report["repair_registered_portfolios"] = len(counts)
        report["repair_visited_portfolios"] = sum(consumed > 0 for _total, consumed in counts)
        report["skipped_elites_by_top_k"] = len(excluded)
        report["skipped_neighbors_by_top_k"] = sum(elite["neighborhood"].candidate_count for elite in excluded)
        pruning["candidate_space_total"] = sum(total for total, _consumed in counts)
        pruning["skipped_by_budget"] = (report["skipped_neighbors_by_top_k"]
                                        + sum(total - consumed for total, consumed in counts))


__all__ = ["RepairWorkAccounting"]
