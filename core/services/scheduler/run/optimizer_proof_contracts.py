from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Tuple

from core.algorithms.objective_specs import normalize_objective_name, objective_metric_keys
from core.infrastructure.errors import ValidationError

REFERENCE_SCHEMA_VERSION = 1

REFERENCE_PROVEN_OPTIMUM = "proven_optimum"
REFERENCE_LOWER_BOUND = "lower_bound"
REFERENCE_FOLDED_NOT_COMPARABLE = "folded_not_comparable"

BOUND_SCOPE_SAME_MODEL = "same_model"
BOUND_SCOPE_FOLDED_FJSP = "folded_fjsp"

FORBIDDEN_PUBLIC_TOKENS = (
    "op:",
    "op_id",
    "node_id",
    "candidate_id",
    "source_table",
)


def assert_benchmark_reference_contract(reference: Dict[str, Any]) -> None:
    _assert_required_fields(reference)
    objective_name = _assert_objective_metric_keys(reference)
    _assert_oracle_fields(reference)
    _assert_reference_scope(reference)
    _assert_makespan_scope(reference, objective_name=objective_name)
    _assert_bound_values_consistent(reference, objective_name=objective_name)
    _assert_best_known_gap_consistent(reference, objective_name=objective_name)
    _assert_public_fields_match_reference(reference)
    assert_public_payload_safe(reference.get("public") or {})


def assert_public_payload_safe(payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    for token in FORBIDDEN_PUBLIC_TOKENS:
        if token in lowered:
            raise ValidationError(
                "Public benchmark payload contains internal scheduler identifiers.",
                field="public",
                details={"token": token},
            )


def render_optimizer_proof_report(payload: Dict[str, Any], *, generated_at: Optional[datetime] = None) -> str:
    generated = generated_at or datetime.now()
    public = payload.get("public") or {}
    lines = [
        "# Optimizer Proof Harness Report",
        "",
        f"- generated_at: {generated.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- status: {public.get('status') or payload.get('status')}",
        f"- case_count: {public.get('case_count')}",
        "",
        "## Cases",
        "",
    ]
    for item in public.get("cases") or []:
        lines.extend(
            [
                f"- {item.get('case_slug')}: {item.get('reference_type')}",
                f"  - objective: {item.get('objective_name')}",
                f"  - bound_metric: {item.get('bound_metric')}",
                f"  - oracle_status: {item.get('oracle_status')}",
                f"  - gap_to_oracle_pct: {_format_optional_float(item.get('gap_to_oracle_pct'))}",
                f"  - counts: {json.dumps(item.get('aggregate_counts') or {}, ensure_ascii=False, sort_keys=True)}",
            ]
        )
    text = "\n".join(lines) + "\n"
    assert_public_payload_safe(text)
    return text


def require_known_objective(objective_name: Any) -> str:
    text = str(objective_name or "").strip().lower()
    normalized = normalize_objective_name(text)
    if not text or normalized != text:
        raise ValidationError("Unknown benchmark objective.", field="objective_name")
    return normalized


def score_equal(left: Sequence[float], right: Sequence[float]) -> bool:
    return len(left) == len(right) and all(abs(float(a) - float(b)) <= 1e-9 for a, b in zip(left, right))


def best_known_score(actual_score: Sequence[float], oracle_score: Optional[Sequence[float]]) -> Tuple[float, ...]:
    best = tuple(float(item) for item in actual_score)
    if oracle_score is None:
        return best
    candidate = tuple(float(item) for item in oracle_score)
    if candidate and candidate < best:
        return candidate
    return best


def gap_to_score(
    actual_score: Sequence[float],
    reference_score: Sequence[float],
    objective_name: str,
) -> Tuple[Optional[float], Optional[str]]:
    if score_equal(actual_score, reference_score):
        return 0.0, "objective_score"
    metric_keys = ["failed_ops"] + list(objective_metric_keys(objective_name))
    for idx, (actual, reference) in enumerate(zip(actual_score, reference_score)):
        if abs(float(actual) - float(reference)) <= 1e-9:
            continue
        metric_key = metric_keys[idx] if idx < len(metric_keys) else "objective_score"
        return gap_pct(float(actual), float(reference)), metric_key
    return None, None


def gap_pct(actual: float, reference: float) -> Optional[float]:
    if reference is None:
        return None
    value = float(actual)
    if not math.isfinite(value):
        return None
    ref = float(reference)
    if not math.isfinite(ref) or abs(ref) <= 1e-12:
        return None
    return float(round((value - ref) / ref * 100.0, 6))


def _assert_required_fields(reference: Dict[str, Any]) -> None:
    required = (
        "reference_type",
        "objective_name",
        "objective_metric_keys",
        "bound_metric",
        "bound_scope",
        "bound_is_objective_comparable",
        "oracle_status",
        "public",
        "diagnostics_ref",
    )
    missing = [key for key in required if key not in reference]
    if missing:
        raise ValidationError(
            "BenchmarkReference is missing required fields.",
            field="BenchmarkReference",
            details={"missing": missing},
        )


def _assert_objective_metric_keys(reference: Dict[str, Any]) -> str:
    objective_name = require_known_objective(reference.get("objective_name"))
    expected_metric_keys = list(objective_metric_keys(objective_name))
    if list(reference.get("objective_metric_keys") or []) != expected_metric_keys:
        raise ValidationError(
            "BenchmarkReference objective metric keys do not match the objective registry.",
            field="objective_metric_keys",
        )
    return objective_name


def _assert_oracle_fields(reference: Dict[str, Any]) -> None:
    if reference.get("oracle_status") != "proven_optimal" and reference.get("reference_type") == REFERENCE_PROVEN_OPTIMUM:
        raise ValidationError(
            "Only a proven oracle may produce a proven_optimum reference.",
            field="reference_type",
        )
    if reference.get("oracle_status") != "proven_optimal":
        if reference.get("oracle_optimum") is not None or reference.get("oracle_objective_score"):
            raise ValidationError(
                "An unproven oracle cannot publish oracle optimum fields.",
                field="oracle_optimum",
            )
        if reference.get("gap_to_oracle_pct") is not None:
            raise ValidationError(
                "An unproven oracle cannot publish an oracle gap.",
                field="gap_to_oracle_pct",
            )


def _assert_makespan_scope(reference: Dict[str, Any], *, objective_name: str) -> None:
    if reference.get("bound_metric") == "makespan_hours" and objective_name != "min_makespan":
        if reference.get("reference_type") != REFERENCE_PROVEN_OPTIMUM and reference.get("bound_is_objective_comparable"):
            raise ValidationError(
                "A makespan lower bound cannot prove this objective.",
                field="bound_is_objective_comparable",
            )


def _assert_public_fields_match_reference(reference: Dict[str, Any]) -> None:
    public = reference.get("public") or {}
    for field_name in (
        "reference_type",
        "objective_name",
        "bound_metric",
        "oracle_status",
        "bound_is_objective_comparable",
        "objective_score_matched",
        "gap_to_oracle_pct",
    ):
        if field_name in public and public.get(field_name) != reference.get(field_name):
            raise ValidationError(
                "BenchmarkReference public field does not match the reference payload.",
                field="public",
                details={"public_field": field_name},
            )
    expected_status = "reference" if reference.get("reference_type") == REFERENCE_PROVEN_OPTIMUM else "not_comparable"
    if public.get("status") is not None and public.get("status") != expected_status:
        raise ValidationError(
            "BenchmarkReference public status does not match the reference type.",
            field="public",
            details={"public_field": "status", "expected": expected_status},
        )


def _assert_reference_scope(reference: Dict[str, Any]) -> None:
    reference_type = reference.get("reference_type")
    if reference_type == REFERENCE_PROVEN_OPTIMUM:
        if reference.get("bound_scope") != BOUND_SCOPE_SAME_MODEL:
            raise ValidationError(
                "A proven tiny oracle must use the same APS scheduling model scope.",
                field="bound_scope",
            )
        if reference.get("bound_metric") != "objective_score":
            raise ValidationError(
                "A proven tiny oracle must bind the comparable objective score, not a single side metric.",
                field="bound_metric",
            )
        if not reference.get("bound_is_objective_comparable"):
            raise ValidationError(
                "A proven tiny oracle must mark the objective score as comparable.",
                field="bound_is_objective_comparable",
            )
        return
    if reference_type == REFERENCE_LOWER_BOUND:
        if reference.get("bound_scope") != BOUND_SCOPE_SAME_MODEL:
            raise ValidationError(
                "A same-model lower-bound reference must use the same APS scheduling model scope.",
                field="bound_scope",
            )
        return
    if reference_type == REFERENCE_FOLDED_NOT_COMPARABLE:
        if reference.get("bound_scope") != BOUND_SCOPE_FOLDED_FJSP:
            raise ValidationError(
                "A folded FJSP reference must keep the folded scope explicit.",
                field="bound_scope",
            )
        if reference.get("bound_is_objective_comparable"):
            raise ValidationError(
                "A folded FJSP reference cannot be marked as objective comparable.",
                field="bound_is_objective_comparable",
            )
        return
    raise ValidationError(
        "BenchmarkReference has an unknown reference type.",
        field="reference_type",
    )


def _assert_bound_values_consistent(reference: Dict[str, Any], *, objective_name: str) -> None:
    lower_bound_value = reference.get("lower_bound_value")
    if lower_bound_value is None:
        if reference.get("gap_to_bound_pct") is not None:
            raise ValidationError(
                "BenchmarkReference cannot publish a bound gap without a lower bound.",
                field="gap_to_bound_pct",
            )
        if reference.get("gap_to_bound_metric_key") is not None:
            raise ValidationError(
                "BenchmarkReference cannot publish a bound gap metric key without a lower bound.",
                field="gap_to_bound_metric_key",
            )
        return

    actual = _finite_number_or_none(reference.get("actual_metric_value"))
    lower = _finite_number_or_none(lower_bound_value)
    if actual is not None and lower is not None:
        if actual + 1e-9 < lower:
            raise ValidationError(
                "BenchmarkReference lower bound is above the actual metric value.",
                field="lower_bound_value",
                details={"actual_metric_value": actual, "lower_bound_value": lower},
            )
        expected_gap = gap_pct(actual, lower)
        _assert_optional_gap_matches(
            reference.get("gap_to_bound_pct"),
            expected_gap,
            field="gap_to_bound_pct",
            allow_negative=False,
        )
        _assert_gap_metric_key(
            reference.get("gap_to_bound_metric_key"),
            expected_metric_key=str(reference.get("bound_metric") or ""),
            field="gap_to_bound_metric_key",
        )
        return

    if reference.get("bound_metric") == "objective_score":
        actual_score = _coerce_score(reference.get("actual_metric_value"), field="actual_metric_value")
        lower_score = _coerce_score(lower_bound_value, field="lower_bound_value")
        if len(actual_score) != len(lower_score):
            raise ValidationError(
                "BenchmarkReference objective score bound length does not match the actual score length.",
                field="lower_bound_value",
            )
        if tuple(actual_score) < tuple(lower_score):
            raise ValidationError(
                "BenchmarkReference objective lower bound is worse than the actual objective score.",
                field="lower_bound_value",
            )
        if reference.get("gap_to_bound_pct") is not None and reference.get("reference_type") == REFERENCE_PROVEN_OPTIMUM:
            expected_gap, expected_metric_key = gap_to_score(actual_score, lower_score, objective_name)
            _assert_optional_gap_matches(
                reference.get("gap_to_bound_pct"),
                expected_gap,
                field="gap_to_bound_pct",
                allow_negative=False,
            )
            _assert_gap_metric_key(
                reference.get("gap_to_bound_metric_key"),
                expected_metric_key=expected_metric_key,
                field="gap_to_bound_metric_key",
            )


def _assert_best_known_gap_consistent(reference: Dict[str, Any], *, objective_name: str) -> None:
    actual_score_value = reference.get("actual_objective_score")
    best_known_value = reference.get("best_known_upper_bound")
    if not isinstance(actual_score_value, list) or not isinstance(best_known_value, list):
        actual_metric = _finite_number_or_none(reference.get("actual_metric_value"))
        best_known = _finite_number_or_none(best_known_value)
        if best_known is not None and actual_metric is None:
            raise ValidationError(
                "BenchmarkReference actual metric value must be a finite number.",
                field="actual_metric_value",
            )
        if actual_metric is not None and best_known is not None:
            if reference.get("bound_metric") == "makespan_hours" and actual_metric <= 0:
                raise ValidationError(
                    "BenchmarkReference actual makespan must be positive.",
                    field="actual_metric_value",
                )
            expected_gap = gap_pct(actual_metric, best_known)
            _assert_optional_gap_matches(
                reference.get("gap_to_best_known_pct"),
                expected_gap,
                field="gap_to_best_known_pct",
                allow_negative=True,
            )
            expected_metric_key = str(reference.get("bound_metric") or "")
            _assert_gap_metric_key(
                reference.get("gap_to_best_known_metric_key"),
                expected_metric_key=expected_metric_key,
                field="gap_to_best_known_metric_key",
            )
        return

    actual_score = _coerce_score(actual_score_value, field="actual_objective_score")
    best_score = _coerce_score(best_known_value, field="best_known_upper_bound")
    if len(actual_score) != len(best_score):
        raise ValidationError(
            "BenchmarkReference best-known score length does not match the actual score length.",
            field="best_known_upper_bound",
        )
    expected_gap, expected_metric_key = gap_to_score(actual_score, best_score, objective_name)
    _assert_optional_gap_matches(
        reference.get("gap_to_best_known_pct"),
        expected_gap,
        field="gap_to_best_known_pct",
        allow_negative=True,
    )
    _assert_gap_metric_key(
        reference.get("gap_to_best_known_metric_key"),
        expected_metric_key=expected_metric_key,
        field="gap_to_best_known_metric_key",
    )


def _assert_gap_metric_key(actual: Any, *, expected_metric_key: Optional[str], field: str) -> None:
    if actual is not None and actual != expected_metric_key:
        raise ValidationError(
            "BenchmarkReference gap metric key does not match the metric values.",
            field=field,
            details={"actual": actual, "expected": expected_metric_key},
        )


def _assert_optional_gap_matches(
    actual: Any,
    expected: Optional[float],
    *,
    field: str,
    allow_negative: bool,
) -> None:
    if actual is None and expected is None:
        return
    if actual is None or expected is None:
        raise ValidationError(
            "BenchmarkReference gap value does not match its metric values.",
            field=field,
            details={"actual": actual, "expected": expected},
        )
    if abs(float(actual) - float(expected)) > 1e-6:
        raise ValidationError(
            "BenchmarkReference gap value does not match its metric values.",
            field=field,
            details={"actual": float(actual), "expected": float(expected)},
        )
    if not allow_negative and float(actual) < -1e-9:
        raise ValidationError(
            "BenchmarkReference lower-bound gap cannot be negative.",
            field=field,
            details={"actual": float(actual)},
        )


def _finite_number_or_none(value: Any) -> Optional[float]:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _coerce_score(value: Any, *, field: str) -> Tuple[float, ...]:
    if not isinstance(value, list):
        raise ValidationError("BenchmarkReference objective score must be a list.", field=field)
    try:
        score = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("BenchmarkReference objective score contains a non-numeric value.", field=field) from exc
    if not all(math.isfinite(item) for item in score):
        raise ValidationError("BenchmarkReference objective score contains a non-finite value.", field=field)
    return score


def _format_optional_float(value: Any) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.6f}"
