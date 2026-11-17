"""Bounded repair-round queues that can incorporate parents arriving from other stages."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.services.scheduler.run.optimizer.candidate_fingerprint import score_strictly_better

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget


def pending_neighbors(elite: Dict[str, Any]) -> int:
    return elite["neighborhood"].candidate_count - elite["decision_offset"]


def fresh_pool_elites(pool: Any, *groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    known = {id(elite) for group in groups for elite in group}
    return [elite for elite in pool.elites if id(elite) not in known and pending_neighbors(elite) > 0]


def with_unvisited_pool_elites(elites: List[Dict[str, Any]], queued: List[Dict[str, Any]],
                               pool: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    admitted = elites + fresh_pool_elites(pool, elites, queued)
    return admitted[:pool.limits.top_k], admitted[pool.limits.top_k:] + queued


def fill_round_slots(elites: List[Dict[str, Any]], queued: List[Dict[str, Any]],
                     deferred: List[Dict[str, Any]], pool: Any) -> None:
    # Appending is intentional: the current round's list iterator will visit these admitted
    # parents. A late arrival consumes an unused slot, never an extra round or active slot.
    fresh = fresh_pool_elites(pool, elites, queued, deferred)
    slots = max(pool.limits.top_k - len(elites), 0)
    elites.extend(fresh[:slots])
    queued.extend(fresh[slots:])


def improvements_over_best(improved: List[Dict[str, Any]], best: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Keep the actual event list intact for reporting. A profile/IG improvement may have
    # superseded an earlier repair gain while this generator was suspended.
    return [elite for elite in improved
            if not score_strictly_better(None if best is None else best["score"], elite["candidate"]["score"])]


def prepare_next_repair_round(
    pool: Any, *, improved_elites: List[Dict[str, Any]], deferred_elites: List[Dict[str, Any]],
    budget: SharedSearchBudget,
) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    next_elites: List[Dict[str, Any]] = []
    next_slots = max(pool.limits.top_k - len(deferred_elites), 1)
    for improved in sorted(improved_elites, key=lambda elite: tuple(elite["candidate"]["score"]))[:next_slots]:
        if budget.clock() >= budget.deadline:
            break
        elite = pool.make_elite(improved["candidate"], improved["profile"])
        for profile in improved["basis_profiles"]:
            if budget.clock() >= budget.deadline:
                break
            pool.add_basis_variant(elite, profile)
        next_elites.append(elite)
    if not next_elites and improved_elites:
        return None
    next_elites.extend(deferred_elites)
    return next_elites[:pool.limits.top_k], next_elites[pool.limits.top_k:]


def retain_pending_tail(elite: Dict[str, Any], deferred_elites: List[Dict[str, Any]]) -> None:
    if pending_neighbors(elite):
        deferred_elites.append(elite)


def defer_to_improved_elites(pool: Any, round_index: int, improved_elites: List[Dict[str, Any]]) -> bool:
    return bool(improved_elites) and round_index + 1 < pool.limits.max_rounds
