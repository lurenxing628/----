"""Bounded repair-round queues that can incorporate parents arriving from other stages."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .optimizer_candidate_fingerprint import score_strictly_better
from .optimizer_graph_ready_repair_accounting import RepairWorkAccounting


def _pending_neighbors(elite: Dict[str, Any]) -> int:
    return elite["neighborhood"].candidate_count - elite.get("decision_offset", 0)


def _fresh_pool_elites(elites: List[Dict[str, Any]], pool: Any) -> List[Dict[str, Any]]:
    known = {id(elite) for elite in elites}
    return [elite for elite in pool.elites if id(elite) not in known and _pending_neighbors(elite) > 0]


def _with_unvisited_pool_elites(elites: List[Dict[str, Any]], queued: List[Dict[str, Any]],
                                pool: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    admitted = elites + _fresh_pool_elites(elites + queued, pool)
    return admitted[:pool.limits.top_k], admitted[pool.limits.top_k:] + queued


def _fill_round_slots(elites: List[Dict[str, Any]], queued: List[Dict[str, Any]],
                      deferred: List[Dict[str, Any]], pool: Any) -> None:
    # Appending is intentional: the current round's list iterator will visit these admitted
    # parents. A late arrival consumes an unused slot, never an extra round or active slot.
    fresh = _fresh_pool_elites(elites + queued + deferred, pool)
    slots = max(pool.limits.top_k - len(elites), 0)
    elites.extend(fresh[:slots])
    queued.extend(fresh[slots:])


def _current_improvements(improved: List[Dict[str, Any]], best: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Keep the actual event list intact for reporting. A profile/IG improvement may have
    # superseded an earlier repair gain while this generator was suspended.
    return [elite for elite in improved
            if not score_strictly_better((best or {}).get("score"), elite["candidate"]["score"])]


def _prepare_next_repair_round(
    pool: Any, *, improved_elites: List[Dict[str, Any]], deferred_elites: List[Dict[str, Any]],
    repair_deadline: float, clock: Callable[[], float], accounting: RepairWorkAccounting,
) -> Optional[Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
    next_elites: List[Dict[str, Any]] = []
    next_slots = max(pool.limits.top_k - len(deferred_elites), 1)
    for improved in sorted(improved_elites, key=lambda elite: tuple(elite["candidate"]["score"]))[:next_slots]:
        if clock() >= repair_deadline:
            break
        elite = pool.make_elite(improved["candidate"], improved["profile"])
        for profile in improved.get("basis_profiles", ()):
            if clock() >= repair_deadline:
                break
            pool.add_basis_variant(elite, profile)
        next_elites.append(elite)
    if not next_elites and improved_elites:
        return None
    accounting.observe(next_elites)
    next_elites.extend(deferred_elites)
    return next_elites[:pool.limits.top_k], next_elites[pool.limits.top_k:]


def _retain_pending_tail(elite: Dict[str, Any], deferred_elites: List[Dict[str, Any]]) -> None:
    if _pending_neighbors(elite):
        elite["pending_tail"] = True
        deferred_elites.append(elite)


def _defer_to_improved_elites(pool: Any, elites: List[Dict[str, Any]], elite_index: int,
                             round_index: int, improved_elites: List[Dict[str, Any]]) -> bool:
    if not improved_elites or round_index + 1 >= pool.limits.max_rounds:
        return False
    pool.report["repair_deferred_by_improvement"] += sum(
        _pending_neighbors(elite) for elite in elites[elite_index:])
    return True
