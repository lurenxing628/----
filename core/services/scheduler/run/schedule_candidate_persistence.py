from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.infrastructure.errors import ValidationError
from core.models.enums import LockStatus
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.models.schedule_plan_role import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE

from .schedule_candidate_persistence_models import build_candidate_model
from .schedule_candidate_summary import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    candidate_roles_by_key,
)


def _candidate_by_key(candidate_comparison: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for candidate in list(getattr(candidate_comparison, "candidates", None) or []):
        key = str(getattr(candidate, "candidate_key", "") or "").strip()
        if key:
            out[key] = candidate
    return out


def _require_result_row(candidate: Any, result: Any, *, allowed_op_ids: Set[int]) -> Dict[str, Any]:
    key = str(getattr(candidate, "candidate_key", "") or "")
    try:
        op_id = int(getattr(result, "op_id", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"试算方案 {key} 的工序编号不合法，已拒绝保存明细。", field="candidate_rows") from exc
    if op_id <= 0:
        raise ValidationError(f"试算方案 {key} 的工序编号必须大于 0，已拒绝保存明细。", field="candidate_rows")
    if op_id not in allowed_op_ids:
        raise ValidationError(
            f"试算方案 {key} 包含超出本次可重排范围的工序 {op_id}，已拒绝保存明细。",
            field="candidate_rows",
        )
    start_time = getattr(result, "start_time", None)
    end_time = getattr(result, "end_time", None)
    if start_time is None or end_time is None:
        raise ValidationError(f"试算方案 {key} 缺少开始或结束时间，已拒绝保存明细。", field="candidate_rows")
    try:
        valid_range = start_time < end_time
    except TypeError as exc:
        raise ValidationError(f"试算方案 {key} 的开始/结束时间不可比较，已拒绝保存明细。", field="candidate_rows") from exc
    if not valid_range:
        raise ValidationError(f"试算方案 {key} 的开始时间必须早于结束时间，已拒绝保存明细。", field="candidate_rows")
    return {
        "op_id": int(op_id),
        "machine_id": getattr(result, "machine_id", None),
        "operator_id": getattr(result, "operator_id", None),
        "start_time": start_time,
        "end_time": end_time,
    }


def _candidate_rows(
    svc: Any,
    candidate: Any,
    *,
    version: int,
    candidate_id: int,
    frozen_op_ids: Set[int],
    allowed_op_ids: Set[int],
) -> List[ScheduleCandidateRows]:
    rows: List[ScheduleCandidateRows] = []
    for result in list(getattr(candidate, "results", None) or []):
        row = _require_result_row(candidate, result, allowed_op_ids=allowed_op_ids)
        op_id = int(row["op_id"])
        rows.append(
            ScheduleCandidateRows(
                id=None,
                version=int(version),
                candidate_id=int(candidate_id),
                op_id=op_id,
                machine_id=row["machine_id"],
                operator_id=row["operator_id"],
                start_time=svc._format_dt(row["start_time"]),
                end_time=svc._format_dt(row["end_time"]),
                lock_status=LockStatus.LOCKED.value if op_id in frozen_op_ids else LockStatus.UNLOCKED.value,
            )
        )
    if not rows:
        raise ValidationError("代表试算方案没有可保存的明细行，已拒绝保存。", field="candidate_rows")
    return rows


def _role_key(candidate_comparison: Any, role: str) -> Optional[str]:
    selection = getattr(candidate_comparison, "selection", None)
    if role == ROLE_ADOPTED:
        value = getattr(selection, "selected_candidate_key", None)
    elif role == ROLE_BASELINE_BEST:
        value = getattr(selection, "baseline_best_key", None)
    elif role == ROLE_CRITICAL_BEST:
        value = getattr(selection, "critical_best_key", None)
    else:
        value = None
    text = str(value or "").strip()
    return text or None


def _selection_source(*, role_key: str, adopted_key: str) -> str:
    return SOURCE_SCHEDULE if role_key == adopted_key else SOURCE_CANDIDATE_ROWS


def _require_adopted_key(selection: Any) -> str:
    adopted_key = str(getattr(selection, "selected_candidate_key", "") or "").strip()
    if not adopted_key:
        raise ValidationError("方案对比缺少最终采用结果，已拒绝保存。", field="candidate_selection")
    return adopted_key


def _require_candidate_key_available(
    *,
    role: str,
    key: str,
    by_key: Dict[str, Any],
    candidate_ids: Dict[str, int],
) -> None:
    if key not in by_key or key not in candidate_ids:
        raise ValidationError(
            f"方案对比角色 {role} 指向不存在的方案编号：{key}",
            field="candidate_selection",
        )


def _comparison_weight_count(candidate_comparison: Any) -> int:
    return max(0, int(getattr(candidate_comparison, "planned_count", 0) or 0) - 1)


def _candidate_models(
    candidate_comparison: Any,
    *,
    version: int,
    roles_by_key: Dict[str, List[str]],
    adopted_key: str,
    selection: Any,
    weight_count: int,
) -> List[ScheduleCandidate]:
    models: List[ScheduleCandidate] = []
    for candidate in list(getattr(candidate_comparison, "candidates", None) or []):
        key = str(getattr(candidate, "candidate_key", "") or "").strip()
        selection_reason = str(getattr(selection, "reason_code", "") or "") if key == adopted_key else None
        models.append(
            build_candidate_model(
                candidate,
                version=int(version),
                roles=roles_by_key.get(key, []),
                selection_reason=selection_reason,
                weight_count=weight_count,
            )
        )
    return models


def _detail_keys(candidate_comparison: Any, *, adopted_key: str) -> List[str]:
    detail_keys: List[str] = []
    for role in (ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST):
        key = _role_key(candidate_comparison, role)
        if key and key != adopted_key and key not in detail_keys:
            detail_keys.append(key)
    return detail_keys


def _persist_candidate_detail_rows(
    svc: Any,
    *,
    version: int,
    candidate_ids: Dict[str, int],
    by_key: Dict[str, Any],
    detail_keys: List[str],
    frozen_op_ids: Set[int],
    allowed_op_ids: Set[int],
) -> None:
    repo = svc.candidate_repo
    for key in detail_keys:
        _require_candidate_key_available(
            role="detail_rows",
            key=key,
            by_key=by_key,
            candidate_ids=candidate_ids,
        )
        candidate = by_key[key]
        repo.bulk_create_candidate_rows(
            _candidate_rows(
                svc,
                candidate,
                version=int(version),
                candidate_id=int(candidate_ids[key]),
                frozen_op_ids=frozen_op_ids,
                allowed_op_ids=allowed_op_ids,
            )
        )


def _persist_candidate_selections(
    svc: Any,
    *,
    version: int,
    candidate_comparison: Any,
    candidate_ids: Dict[str, int],
    by_key: Dict[str, Any],
    adopted_key: str,
) -> None:
    repo = svc.candidate_repo
    for role in (ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST):
        key = _role_key(candidate_comparison, role)
        if not key:
            continue
        _require_candidate_key_available(
            role=role,
            key=key,
            by_key=by_key,
            candidate_ids=candidate_ids,
        )
        repo.create_selection(
            ScheduleCandidateSelection(
                id=None,
                version=int(version),
                role=role,
                candidate_id=int(candidate_ids[key]),
                source_table=_selection_source(role_key=key, adopted_key=adopted_key),
            )
        )


def persist_candidate_comparison(
    svc: Any,
    *,
    version: int,
    candidate_comparison: Any,
    frozen_op_ids: Set[int],
    allowed_op_ids: Set[int],
) -> None:
    repo = svc.candidate_repo
    roles_by_key = candidate_roles_by_key(candidate_comparison)
    selection = getattr(candidate_comparison, "selection", None)
    adopted_key = _require_adopted_key(selection)
    weight_count = _comparison_weight_count(candidate_comparison)
    candidates = _candidate_models(
        candidate_comparison,
        version=int(version),
        roles_by_key=roles_by_key,
        adopted_key=adopted_key,
        selection=selection,
        weight_count=weight_count,
    )
    candidate_ids = repo.create_candidates(candidates)
    by_key = _candidate_by_key(candidate_comparison)

    _persist_candidate_detail_rows(
        svc,
        version=int(version),
        candidate_ids=candidate_ids,
        by_key=by_key,
        detail_keys=_detail_keys(candidate_comparison, adopted_key=adopted_key),
        frozen_op_ids=frozen_op_ids,
        allowed_op_ids=allowed_op_ids,
    )
    _persist_candidate_selections(
        svc,
        version=int(version),
        candidate_comparison=candidate_comparison,
        candidate_ids=candidate_ids,
        by_key=by_key,
        adopted_key=adopted_key,
    )


__all__ = [
    "SOURCE_CANDIDATE_ROWS",
    "SOURCE_SCHEDULE",
    "persist_candidate_comparison",
]
