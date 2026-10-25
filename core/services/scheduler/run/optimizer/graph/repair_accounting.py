"""Account for admitted repair portfolios while profiles keep adding parents and basis variants."""
from __future__ import annotations

from typing import Any, Dict, Iterable


class RepairWorkAccounting:
    def __init__(self) -> None:
        # Account for portfolio progress without retaining their live parent objects.
        self.elites: Dict[int, Dict[str, Any]] = {}

    def observe(self, elites: Iterable[Dict[str, Any]]) -> None:
        for elite in elites:
            self.elites[elite["portfolio_id"]] = {
                "total": elite["neighborhood"].candidate_count,
                "consumed": elite.get("decision_offset", 0),
            }

    def finish(self, pool: Any) -> None:
        if pool.limits.enabled:
            # Newly selected parents that never got a task are pending work, not top-k exclusions.
            self.observe(pool.elites)
        report, pruning = pool.report, pool.report["repair_pruning_report"]
        parents = pool.profile_parent_sizes
        report["eligible_elites"] = len(parents)
        excluded_sizes = [total for portfolio_id, total in parents.items() if portfolio_id not in self.elites]
        counts = [(parents.get(portfolio_id, progress["total"]), progress["consumed"])
                  for portfolio_id, progress in self.elites.items()]
        report["selected_elites"] = len(parents) - len(excluded_sizes)
        report["selected_elites_scope"] = "cumulative_profile_parents_admitted_during_rotation"
        report["repair_registered_portfolios"] = len(counts)
        report["repair_visited_portfolios"] = sum(consumed > 0 for _total, consumed in counts)
        report["skipped_elites_by_top_k"] = len(excluded_sizes)
        report["skipped_neighbors_by_top_k"] = sum(excluded_sizes)
        pruning["candidate_space_total"] = sum(total for total, _consumed in counts)
        pruning["skipped_by_budget"] = (report["skipped_neighbors_by_top_k"]
                                        + sum(total - consumed for total, consumed in counts))


__all__ = ["RepairWorkAccounting"]
