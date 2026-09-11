"""Append derivation contracts; constructor-built indexes are the unchanged oracle."""

from datetime import datetime, timedelta, timezone, tzinfo
from itertools import product
from typing import Any, List, Tuple

import pytest

from core.algorithm_runtime.downtime import SegmentOverlapIndex
from core.algorithm_runtime.slot_overlap_reuse import SlotOverlapReuse

BASE = datetime(2026, 1, 1)
ARRAY_FIELDS = ("_segments", "_starts", "_prefix_max_ends", "_covered_starts", "_covered_ends")


def dt(microseconds):
    return BASE + timedelta(microseconds=microseconds)


def segment(start, end):
    return dt(start), dt(end)


def segments(*pairs):
    return tuple(segment(start, end) for start, end in pairs)


def saved_state(index):
    references = tuple(getattr(index, name) for name in ARRAY_FIELDS)
    values = tuple(None if value is None else
                   tuple(list(item) if type(item) is list else item for item in value)
                   for value in references)
    return references, values, index._scanned_once


def assert_unchanged(index, saved):
    references, values, scanned_once = saved
    for name, reference, value in zip(ARRAY_FIELDS, references, values):
        current = getattr(index, name)
        assert current is reference, name
        assert (None if current is None else tuple(current)) == value, name
    assert index._scanned_once is scanned_once


def assert_queries(index, snapshot, points, covered=True, materialize=None):
    oracle = SegmentOverlapIndex(snapshot)
    if materialize is None:
        oracle._materialize()
    else:
        # Exclude the independent oracle from cache-path instrumentation.
        materialize(oracle)
    assert len(index) == len(oracle) == len(snapshot)
    for start, end in product(points, repeat=2):
        assert index.shift_end(start, end) == oracle.shift_end(start, end), (start, end, snapshot)
    assert index._starts is not None and oracle._starts is not None
    assert tuple(index._starts) == tuple(oracle._starts)
    assert tuple(index._prefix_max_ends) == tuple(oracle._prefix_max_ends)
    if covered:
        for instant in points:
            assert index.covered_end(instant) == oracle.covered_end(instant), (instant, snapshot)
        assert index._covered_starts is not None and oracle._covered_starts is not None
        assert tuple(index._covered_starts) == tuple(oracle._covered_starts)
        assert tuple(index._covered_ends) == tuple(oracle._covered_ends)


def query_trace(index):
    intervals = [(-2, -1), (1, 2), (9, 9), (11, 9), (13, 16)]
    calls: List[Tuple[Any, Tuple[datetime, ...]]] = [
        (index.shift_end, (dt(start), dt(end))) for start, end in intervals
    ]
    calls.extend((index.covered_end, (dt(instant),)) for instant in (-1, 0, 4, 8, 12, 15))
    aware_interval = dt(0).replace(tzinfo=timezone.utc), dt(16).replace(tzinfo=timezone.utc)
    calls.append((index.shift_end, aware_interval))
    trace = []
    for function, args in calls:
        try:
            trace.append(("value", function(*args)))
        except Exception as exc:
            trace.append(("error", type(exc), str(exc)))
    return trace


@pytest.mark.parametrize("covered", [False, True])
@pytest.mark.parametrize("before, appended", [
    pytest.param((), segment(0, 4), id="empty-parent"),
    pytest.param(segments((9, 9), (5, 4)), segment(0, 4), id="all-invalid-parent"),
    pytest.param(segments((0, 4), (8, 12)), segment(20, 25), id="separate-block"),
    pytest.param(segments((0, 10), (8, 12)), segment(9, 20), id="overlap"),
    pytest.param(segments((0, 10), (8, 12)), segment(8, 9), id="equal-start-shorter-end"),
    pytest.param(segments((0, 40), (8, 12)), segment(10, 20), id="nested-under-prefix-max"),
    pytest.param(segments((0, 4), (8, 12)), segment(12, 20), id="touching-tail"),
    pytest.param(segments((0, 4), (8, 12)), segment(13, 20), id="one-microsecond-gap"),
    pytest.param(segments((0, 5), (50, 49)), segment(5, 6), id="ignore-invalid-tail-start"),
    pytest.param(segments((0, 4), (8, 12)), segment(-10, -10), id="zero-before-last-start"),
    pytest.param(segments((0, 4), (8, 12)), segment(-10, -11), id="reverse-before-last-start"),
    pytest.param(segments((0, 4), (8, 12)), segment(100, 99), id="invalid-future-tail"),
    pytest.param(segments((9, 9)), segment(2, 1), id="still-all-invalid"),
])
def test_derived_queries_and_old_snapshots_are_exact(before, appended, covered):
    parent = SegmentOverlapIndex(before)
    parent._materialize()
    if covered:
        parent.covered_end(BASE)
    saved = saved_state(parent)
    # Equal prefix values need not be the same tuple or datetime objects.
    snapshot = tuple((start.replace(), end.replace()) for start, end in before) + (appended,)
    child = parent.with_appended_segment(snapshot)
    assert child is not None and child is not parent
    assert child._starts is not None
    assert len(child) == len(parent) + 1
    if covered:
        assert child._covered_starts is not None
    else:
        assert child._covered_starts is None
        assert child._covered_ends == ()
    if appended[1] <= appended[0]:
        assert child._starts == parent._starts
        assert child._prefix_max_ends == parent._prefix_max_ends
        assert child._covered_starts == parent._covered_starts
        assert child._covered_ends == parent._covered_ends
    points = {dt(-20), dt(110)}
    for start, end in snapshot:
        for boundary in (start, end):
            points.update(boundary + timedelta(microseconds=offset) for offset in (-1, 0, 1))
    assert_queries(child, snapshot, sorted(points))
    assert_unchanged(parent, saved)
    oracle = SegmentOverlapIndex(before)
    oracle._materialize()
    assert parent.shift_end(dt(1), dt(30)) == oracle.shift_end(dt(1), dt(30))


class DatetimeSubclass(datetime):
    pass


class TupleSubclass(tuple):
    pass


class EqualityBomb(datetime):
    def __eq__(self, other):
        raise RuntimeError("prefix equality must stay outside the fast path")

    def __ne__(self, other):
        raise RuntimeError("prefix inequality must stay outside the fast path")


class OffsetBomb(tzinfo):
    def utcoffset(self, value):
        raise RuntimeError("timezone offset unavailable")


OLD = segments((0, 4), (8, 12))
NEXT = segment(13, 16)
AWARE = tuple((start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)) for start, end in OLD)
SUBCLASS = DatetimeSubclass(2026, 1, 1, 0, 0, 0, 13)


@pytest.mark.parametrize("before, snapshot, warm", [
    pytest.param(OLD, OLD + (NEXT,), False, id="cold-parent"),
    pytest.param(OLD, OLD, True, id="unchanged-length"),
    pytest.param(OLD, segments((0, 4), (8, 13)), True, id="same-length-edit"),
    pytest.param(OLD, segments((0, 5), (8, 12), (13, 16)), True, id="changed-prefix"),
    pytest.param(OLD, segments((0, 4), (5, 6), (8, 12)), True, id="gap-insert"),
    pytest.param(OLD, (segment(-2, -1),) + OLD, True, id="prepend"),
    pytest.param(OLD, OLD + (NEXT, segment(17, 20)), True, id="bulk-append"),
    pytest.param(OLD, OLD[:-1], True, id="delete"),
    pytest.param(OLD, (), True, id="clear"),
    pytest.param(OLD, OLD + (segment(5, 6),), True, id="unsorted-append"),
    pytest.param(OLD[::-1], OLD[::-1] + (NEXT,), False, id="unsorted-parent"),
    pytest.param(list(OLD), OLD + (NEXT,), True, id="mutable-list-parent"),
    pytest.param((list(OLD[0]), OLD[1]), (list(OLD[0]), OLD[1], NEXT), True, id="list-row-parent"),
    pytest.param(OLD, OLD + (list(NEXT),), True, id="list-row-append"),
    pytest.param((TupleSubclass(OLD[0]), OLD[1]),
                 (TupleSubclass(OLD[0]), OLD[1], NEXT), True, id="tuple-subclass-parent-row"),
    pytest.param(OLD, OLD + (TupleSubclass(NEXT),), True, id="tuple-subclass-append-row"),
    pytest.param(OLD, (TupleSubclass(OLD[0]), OLD[1], NEXT), True,
                 id="equal-prefix-with-tuple-subclass"),
    pytest.param(OLD, ((DatetimeSubclass(2026, 1, 1), dt(4)), OLD[1], NEXT), True,
                 id="equal-prefix-with-datetime-subclass"),
    pytest.param(((SUBCLASS, dt(15)),), ((SUBCLASS, dt(15)), segment(16, 18)), True,
                 id="datetime-subclass-parent-start"),
    pytest.param(((dt(0), SUBCLASS),), ((dt(0), SUBCLASS), NEXT), True,
                 id="datetime-subclass-parent-end"),
    pytest.param(OLD, OLD + ((SUBCLASS, dt(16)),), True, id="datetime-subclass-append-start"),
    pytest.param(OLD, OLD + ((dt(13), SUBCLASS),), True, id="datetime-subclass-invalid-append-end"),
    pytest.param(((SUBCLASS, SUBCLASS),), ((SUBCLASS, SUBCLASS), NEXT), True,
                 id="datetime-subclass-invalid-parent"),
    pytest.param(AWARE, AWARE + ((dt(13).replace(tzinfo=timezone.utc),
                                dt(16).replace(tzinfo=timezone.utc)),), True, id="aware-parent"),
    pytest.param(((AWARE[0][0], AWARE[0][0]),), ((AWARE[0][0], AWARE[0][0]), NEXT), True,
                 id="aware-invalid-parent"),
    pytest.param(OLD, OLD + ((dt(13).replace(tzinfo=timezone.utc), dt(16)),), True,
                 id="aware-append-start"),
    pytest.param(OLD, OLD + ((dt(13), dt(16).replace(tzinfo=timezone.utc)),), True,
                 id="aware-append-end"),
    pytest.param(OLD, OLD + ((dt(13),),), True, id="short-row"),
    pytest.param(OLD, OLD + ((dt(13), dt(16), dt(17)),), True, id="long-row"),
    pytest.param(OLD, OLD + (None,), True, id="non-row"),
    pytest.param(OLD, OLD + (("bad", dt(16)),), True, id="non-datetime-start"),
    pytest.param(OLD, OLD + ((dt(13), "bad"),), True, id="non-datetime-end"),
    pytest.param(((0, 0),), ((0, 0), NEXT), True, id="non-datetime-invalid-parent"),
    pytest.param(OLD, ((EqualityBomb(2026, 1, 1), dt(4)), OLD[1], NEXT), True,
                 id="prefix-comparison-exception"),
    pytest.param(OLD, OLD + ((dt(13).replace(tzinfo=OffsetBomb()), dt(16)),), True,
                 id="timezone-exception"),
])
def test_ineligible_derivation_returns_none_without_mutating_parent(before, snapshot, warm):
    parent = SegmentOverlapIndex(before)
    if warm:
        parent._materialize()
    saved = saved_state(parent)
    assert parent.with_appended_segment(snapshot) is None
    assert_unchanged(parent, saved)


@pytest.mark.parametrize("snapshot", [
    segments((0, 4), (8, 13)), segments((0, 5), (8, 12), (13, 16)),
    segments((0, 4), (5, 6), (8, 12)), OLD + (NEXT, segment(17, 20)),
    OLD[:-1], (), OLD + (segment(5, 6),), OLD + (list(NEXT),),
    OLD + ((SUBCLASS, dt(16)),), OLD + ((dt(13).replace(tzinfo=timezone.utc), dt(16)),),
    OLD + ((dt(13),),), OLD + (None,),
    OLD + ((dt(13).replace(tzinfo=OffsetBomb()), dt(16)),),
])
def test_reuse_fallback_preserves_constructor_query_and_exception_trace(snapshot):
    reuse = SlotOverlapReuse()
    parent = reuse.index("machine", "M", list(OLD))
    parent._materialize()
    parent.covered_end(BASE)
    saved = saved_state(parent)
    actual = reuse.index("machine", "M", snapshot)
    assert actual is not parent
    assert actual._starts is None
    assert actual._covered_starts is None
    assert actual._scanned_once is False
    assert query_trace(actual) == query_trace(SegmentOverlapIndex(snapshot))
    assert_unchanged(parent, saved)


@pytest.mark.parametrize("kind", ["machine", "operator", "downtime"])
def test_equal_replacement_prefix_appends_and_only_changes_its_resource(kind):
    reuse = SlotOverlapReuse()
    source = list(OLD)
    parent = reuse.index(kind, "R", source)
    parent._materialize()
    others = {(domain, resource): reuse.index(domain, resource, source)
              for domain in ("machine", "operator", "downtime") for resource in ("R", "OTHER")
              if (domain, resource) != (kind, "R")}
    replacement = [(start.replace(), end.replace()) for start, end in source]
    assert replacement is not source and replacement[0] is not source[0]
    assert reuse.index(kind, "R", replacement) is parent
    saved = saved_state(parent)
    replacement.append(NEXT)
    child = reuse.index(kind, "R", replacement)
    assert child is not parent and child._starts is not None
    assert_queries(child, tuple(replacement), [dt(n) for n in (-1, 0, 4, 8, 12, 13, 16, 17)])
    assert_unchanged(parent, saved)
    assert source == list(OLD)
    for key, untouched in others.items():
        assert reuse.index(key[0], key[1], source) is untouched
    list.__setitem__(replacement, 0, segment(0, 5))
    changed = reuse.index(kind, "R", replacement)
    assert changed is not child and changed._starts is None
    assert query_trace(changed) == query_trace(SegmentOverlapIndex(tuple(replacement)))


@pytest.mark.parametrize("scanned_once", [False, True])
def test_lazy_parent_never_becomes_materialized_by_append(scanned_once):
    reuse = SlotOverlapReuse()
    parent = reuse.index("machine", "M", OLD)
    if scanned_once:
        assert parent.shift_end(dt(-2), dt(-1)) is None
    saved = saved_state(parent)
    assert parent.with_appended_segment(OLD + (NEXT,)) is None
    child = reuse.index("machine", "M", OLD + (NEXT,))
    assert child._starts is None and child._scanned_once is False
    assert query_trace(child) == query_trace(SegmentOverlapIndex(OLD + (NEXT,)))
    assert_unchanged(parent, saved)


def test_unsorted_zero_hop_and_first_second_query_error_order():
    reuse = SlotOverlapReuse()
    source = list(OLD)
    parent = reuse.index("machine", "M", source)
    parent._materialize()
    source.append(segment(5, 6))
    for _ in range(3):
        current = reuse.index("machine", "M", source)
        assert current._starts is None and current._scanned_once is False
        assert current.shift_end(dt(-2), dt(-1)) is None
        assert current._starts is None
    current = reuse.index("machine", "M", source)
    oracle = SegmentOverlapIndex(tuple(source))
    assert current.shift_end(dt(1), dt(2)) == oracle.shift_end(dt(1), dt(2)) == dt(4)
    with pytest.raises(ValueError) as expected:
        oracle.shift_end(dt(4), dt(5))
    with pytest.raises(ValueError) as actual:
        current.shift_end(dt(4), dt(5))
    assert str(actual.value) == str(expected.value)
    assert current._starts is None
    restarted = reuse.index("machine", "M", source)
    assert restarted is current and restarted.shift_end(dt(-2), dt(-1)) is None
    with pytest.raises(ValueError):
        restarted.covered_end(dt(5))


@pytest.mark.parametrize("covered", [False, True])
def test_500_single_appends_do_not_rematerialize_and_match_oracle(monkeypatch, covered):
    materializations = []
    original = SegmentOverlapIndex._materialize

    def counted(index):
        materializations.append(index)
        return original(index)

    monkeypatch.setattr(SegmentOverlapIndex, "_materialize", counted)
    reuse = SlotOverlapReuse()
    source = [segment(0, 2)]
    current = reuse.index("machine", "M", source)
    current._materialize()
    if covered:
        current.covered_end(BASE)
    for step in range(1, 501):
        parent, saved = current, saved_state(current)
        start = 2 * step
        width = (0, -1, 1, 2, 7)[step % 5]
        source.append(segment(start, start + width))
        current = reuse.index("machine", "M", source)
        assert current is not parent and current._starts is not None
        assert (current._covered_starts is not None) is covered
        points = [dt(n) for n in (-1, 0, start - 1, start, start + 1, start + 7, start + 8)]
        assert_queries(current, tuple(source), points, covered=covered, materialize=original)
        assert_unchanged(parent, saved)
        assert len(current) == step + 1
        assert len(materializations) == 1
    assert_queries(current, tuple(source), points, materialize=original)
    assert len(materializations) == 1
