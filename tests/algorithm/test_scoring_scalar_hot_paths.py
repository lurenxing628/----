"""Scalar fast paths preserve legacy parsing and per-score input reads."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, cast

import pytest

from core.algorithm_contracts.dispatch_rules import DispatchRule
from core.algorithm_runtime.piece_input import operation_batch
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms.greedy.dispatch import sgs_scoring
from core.errors import ValidationError
from core.shared import strict_parse

LIMIT = 1 << 53


def _blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _validation(field, suffix):
    return ValidationError(f"\u201c{field}\u201d{suffix}", field=field)


# Frozen pre-fast-path logic, independent of all product parsing helpers.
def _legacy_int(value, *, field, min_value=None, reject_integer_float=False):
    if _blank(value):
        raise _validation(field, "\u4e0d\u80fd\u4e3a\u7a7a")
    reject = bool(reject_integer_float)
    if isinstance(value, bool):
        raise _validation(field, "\u5fc5\u987b\u662f\u6574\u6570")
    try:
        parsed = float(value)
    except Exception as exc:
        raise _validation(field, "\u5fc5\u987b\u662f\u6574\u6570") from exc
    if not math.isfinite(parsed):
        raise _validation(field, "\u5fc5\u987b\u662f\u6709\u9650\u6574\u6570")
    result = int(parsed)
    if abs(parsed - float(result)) > 1e-9:
        raise _validation(field, "\u5fc5\u987b\u662f\u6574\u6570")
    if reject:
        looks_float = isinstance(value, float)
        if isinstance(value, str):
            text = value.strip()
            looks_float = "." in text or "e" in text.lower()
        if looks_float:
            raise _validation(field, "\u5fc5\u987b\u662f\u6574\u6570")
    if min_value is not None and result < int(min_value):
        raise _validation(field, f"\u5fc5\u987b\u5927\u4e8e\u7b49\u4e8e {min_value}")
    return int(result)


def _legacy_required_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if _blank(value):
        raise _validation("due_date", "\u4e0d\u80fd\u4e3a\u7a7a")
    text = str(value).strip().replace("/", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception as exc:
        suffix = "\u683c\u5f0f\u4e0d\u5408\u6cd5\uff08\u671f\u671b\uff1aYYYY-MM-DD\uff09"
        raise _validation("due_date", suffix) from exc


def _legacy_due(value, *, strict_mode=False):
    if strict_mode:
        return None if _blank(value) else _legacy_required_date(value)
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("/", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _outcome(parser, value, **options):
    try:
        result = parser(value, **options)
    except Exception as exc:
        cause = exc.__cause__
        return ("error", type(exc), str(exc), getattr(exc, "field", None),
                None if cause is None else (type(cause), str(cause)))
    return ("value", type(result), result)


class _CustomInt(int):
    def __float__(self):
        return 9.0


class _BrokenInt(int):
    def __float__(self):
        raise ValueError("custom float failed")


class _DateSubclass(date):
    pass


class _DatetimeSubclass(datetime):
    def date(self):
        return date(2001, 2, 3)


class _DateText(str):
    def __str__(self):
        return "2026/09/12"


@pytest.mark.parametrize("value", [
    -10 ** 400, -LIMIT - 2, -LIMIT - 1, -LIMIT, -LIMIT + 1, -1, 0, 1,
    LIMIT - 1, LIMIT, LIMIT + 1, LIMIT + 2, 10 ** 400,
    True, False, None, "", " ", "12", "12.0", "12e0", "12.5", "bad",
    12.0, 12.5, 12.0000000001, float("nan"), float("inf"), float("-inf"),
    _CustomInt(3), _BrokenInt(3),
])
@pytest.mark.parametrize("options", [
    {}, {"min_value": 0}, {"min_value": "7"}, {"reject_integer_float": True},
    {"reject_integer_float": None}, {"reject_integer_float": 0},
    {"min_value": -1, "reject_integer_float": True},
])
def test_int_matches_independent_legacy_oracle(value, options):
    assert _outcome(strict_parse.parse_required_int, value, field="seq", **options) == (
        _outcome(_legacy_int, value, field="seq", **options)
    )


@pytest.mark.parametrize("value,expected", [
    (-LIMIT, -LIMIT), (LIMIT, LIMIT), (LIMIT + 1, LIMIT),
    (-LIMIT - 1, -LIMIT), (LIMIT + 2, LIMIT + 2), (_CustomInt(3), 9),
])
def test_int_known_rounding_and_subclass_results(value, expected):
    assert strict_parse.parse_required_int(value, field="id") == expected
    assert _legacy_int(value, field="id") == expected


@pytest.mark.parametrize("value", [-LIMIT, -LIMIT + 1, -1, 0, 1, LIMIT - 1, LIMIT])
def test_only_safe_default_ints_bypass_legacy(monkeypatch, value):
    def forbidden(_value):
        pytest.fail("safe default integer entered the legacy parser")
    monkeypatch.setattr(strict_parse, "is_blank_input", forbidden)
    assert strict_parse.parse_required_int(value, field="id") == value


@pytest.mark.parametrize("value,options", [
    (True, {}), (False, {}), (_CustomInt(3), {}), (_BrokenInt(3), {}),
    (LIMIT + 1, {}), (-LIMIT - 1, {}), (10 ** 400, {}), (3.0, {}), ("3", {}),
    (None, {}), (" ", {}), (3, {"min_value": 0}), (3, {"min_value": False}),
    (3, {"reject_integer_float": True}), (3, {"reject_integer_float": None}),
    (3, {"reject_integer_float": 0}),
])
def test_other_int_inputs_and_options_keep_legacy_path(monkeypatch, value, options):
    calls = []
    original = strict_parse.is_blank_input
    def record(raw):
        calls.append(raw)
        return original(raw)
    monkeypatch.setattr(strict_parse, "is_blank_input", record)
    assert _outcome(strict_parse.parse_required_int, value, field="id", **options) == (
        _outcome(_legacy_int, value, field="id", **options)
    )
    assert len(calls) == 1 and calls[0] is value


def test_int_custom_option_conversion_order():
    for raw_parser in (_legacy_int, strict_parse.parse_required_int):
        # Noncanonical option objects deliberately exercise runtime conversions.
        parser = cast(Any, raw_parser)
        events = []
        class Flag:
            def __bool__(self):
                events.append("reject")
                return False
        class Value(int):
            def __float__(self):
                events.append("float")
                return 4.0
        class Minimum:
            def __int__(self):
                events.append("minimum")
                return 0
        assert parser(Value(2), field="seq", min_value=Minimum(), reject_integer_float=Flag()) == 4
        assert events == ["reject", "float", "minimum"]
        events.clear()
        assert parser(2, field="seq", reject_integer_float=Flag()) == 2
        assert events == ["reject"]
        events.clear()
        with pytest.raises(ValidationError):
            parser(None, field="seq", reject_integer_float=Flag())
        assert events == []


@pytest.mark.parametrize("strict_mode", [False, True])
@pytest.mark.parametrize("value", [
    None, date(2026, 9, 11), date.min, date.max, datetime(2026, 9, 11, 8),
    _DateSubclass(2026, 9, 11), _DatetimeSubclass(2026, 9, 11, 8), _DateText("unused"),
    "", " ", "2026/09/11", "2026-09-11", "2026-09-11 08:00", "2026-02-30", "bad", True, 1,
])
def test_due_matches_independent_legacy_oracle_and_routing(monkeypatch, strict_mode, value):
    calls = []
    original_strict = sgs_scoring.parse_optional_date
    original_legacy = sgs_scoring.parse_date
    def strict(raw, *, field):
        calls.append("strict")
        return original_strict(raw, field=field)
    def legacy(raw):
        calls.append("legacy")
        return original_legacy(raw)
    monkeypatch.setattr(sgs_scoring, "parse_optional_date", strict)
    monkeypatch.setattr(sgs_scoring, "parse_date", legacy)
    assert _outcome(sgs_scoring._parse_due_date, value, strict_mode=strict_mode) == (
        _outcome(_legacy_due, value, strict_mode=strict_mode)
    )
    fast = strict_mode and (value is None or type(value) is date)
    assert calls == ([] if fast else ["strict" if strict_mode else "legacy"])


@pytest.mark.parametrize("value", [None, date(2026, 9, 11), "2026/09/11"])
@pytest.mark.parametrize("enabled", [False, True, None])
def test_due_checks_mode_once_before_value(value, enabled):
    for raw_parser in (_legacy_due, sgs_scoring._parse_due_date):
        parser = cast(Any, raw_parser)
        events = []
        class Mode:
            def __bool__(self):
                events.append("mode")
                if enabled is None:
                    raise RuntimeError("mode failed")
                return enabled
        if enabled is None:
            with pytest.raises(RuntimeError, match="mode failed"):
                parser(value, strict_mode=Mode())
        else:
            assert parser(value, strict_mode=Mode()) == (None if value is None else date(2026, 9, 11))
        assert events == ["mode"]


def _score(op, batch, state, **overrides):
    kwargs: Dict[str, Any] = dict(
        ctx=SimpleNamespace(calendar=None), op=op, batch=batch, state=state, batch_id="B1",
        batch_order={"B1": 0}, dispatch_rule=DispatchRule.SLACK, end_dt_exclusive=None,
        machine_downtimes=None, auto_assign_enabled=False, resource_pool=None,
        avg_proc_hours=1.0, strict_mode=True,
    )
    kwargs.update(overrides)
    return sgs_scoring._score_internal_candidate(**kwargs)


def test_score_first_error_and_getter_order_survive_same_length_mutation(monkeypatch):
    events = []
    class Fields:
        def __init__(self, label, values):
            self.label, self.values = label, values
        def __getattr__(self, name):
            events.append(self.label + "." + name)
            return self.values[name]
    def prev_end(_batch_id):
        events.append("prev_end")
        return datetime(2026, 9, 11, 8)
    def hours(*args, **kwargs):
        events.append("hours")
        raise ValidationError("invalid hours", field="setup_hours")
    monkeypatch.setattr(sgs_scoring, "_scoring_total_hours", hours)
    batch = Fields("batch", {"priority": "normal", "due_date": "bad"})
    op = Fields("op", {"seq": "bad", "id": "bad"})
    state = SimpleNamespace(prev_end=prev_end)
    expected = ["batch.priority", "batch.due_date"]
    for field, fix in [("due_date", date(2026, 9, 11)), ("seq", 1), ("id", 2), ("setup_hours", None)]:
        events.clear()
        with pytest.raises(ValidationError) as caught:
            _score(op, batch, state)
        assert caught.value.field == field
        assert events == expected
        if field == "due_date":
            batch.values[field] = fix
            expected += ["op.seq"]
        elif field in ("seq", "id"):
            op.values[field] = fix
            expected += ["op.id"] if field == "seq" else ["prev_end", "hours"]
    batch.values["due_date"] = "bad"
    events.clear()
    with pytest.raises(ValidationError) as caught:
        _score(op, batch, state)
    assert caught.value.field == "due_date"
    assert events == ["batch.priority", "batch.due_date"]
    assert len(batch.values) == len(op.values) == 2


@pytest.mark.parametrize("piece", [None, "p1"])
@pytest.mark.parametrize("strict_mode", [False, True])
def test_score_reads_current_fields_piece_quantity_and_prev_end(piece, strict_mode):
    base = datetime(2026, 9, 11, 8)
    op = SimpleNamespace(id=1, seq=1, batch_id="B1", piece_id=piece, setup_hours=0, unit_hours=1,
                         machine_id="M1", operator_id="O1")
    batch = SimpleNamespace(priority="normal", due_date=date(2026, 9, 12), quantity=7)
    state = ScheduleRunState(base_time=base, batch_progress={"B1": base}, machine_timeline={},
                             initial_scheduled_count=4, failed_count=2)
    stats = {"auto_assign_invalid_total_hours_count": 3}
    ctx = SimpleNamespace(calendar=None, algo_stats=stats)
    order, estimates, inputs = {"B1": 0}, [], []
    sizes = (len(vars(op)), len(vars(batch)), len(order), len(state.batch_progress))
    def estimate(**kwargs):
        estimates.append((kwargs["batch"].quantity, kwargs["prev_end"]))
        start = max(kwargs["prev_end"], kwargs["base_time"])
        hours = kwargs["total_hours_base"]
        return SimpleNamespace(start_time=start, end_time=start + timedelta(hours=hours),
                               total_hours=hours, changeover_penalty=0, blocked_by_window=False, abort_after_hit=False)
    def key(inp):
        inputs.append(inp)
        return (inp.proc_hours, inp.est_start.hour, inp.seq, inp.op_id, inp.batch_order, inp.due_date.day)
    first_hours = 7 if piece is None else 1
    first = _score(op, operation_batch(op, batch), state, ctx=ctx, batch_order=order,
                   estimate_slot=estimate, dispatch_key_builder=key, strict_mode=strict_mode)
    assert first == (0.0, first_hours, 8, 1, 1, 0, 12)
    batch.priority, batch.due_date, batch.quantity = "urgent", date(2026, 9, 13), 3
    op.seq, op.id = 2, 2
    order["B1"] = 5
    state.batch_progress["B1"] = base + timedelta(hours=3)
    second_hours = 3 if piece is None else 1
    second = _score(op, operation_batch(op, batch), state, ctx=ctx, batch_order=order,
                    estimate_slot=estimate, dispatch_key_builder=key, strict_mode=strict_mode)
    assert second == (0.0, second_hours, 11, 2, 2, 5, 13)
    assert estimates == [(first_hours, base), (second_hours, base + timedelta(hours=3))]
    assert [inp.priority for inp in inputs] == ["normal", "urgent"]
    assert sizes == (len(vars(op)), len(vars(batch)), len(order), len(state.batch_progress))
    assert batch.quantity == 3
    assert stats == {"auto_assign_invalid_total_hours_count": 3}
    assert (state.scheduled_count, state.failed_count, state.results, state.errors) == (4, 2, [], [])
