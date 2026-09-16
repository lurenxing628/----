"""Native revision reuse avoids copies without weakening mutable-input invalidation."""

from collections.abc import MutableSequence
from datetime import timedelta

import pytest

from core.algorithm_runtime import slot_overlap_reuse as module
from core.algorithm_runtime.owned_timeline import OwnedSegments
from tests.algorithm.test_sgs_slot_reuse_contract import dt


def _long_values():
    start = dt(0) + timedelta(days=1)
    return OwnedSegments([(dt(0), dt(1))] + [
        (start + timedelta(hours=i * 2), start + timedelta(hours=i * 2 + 1)) for i in range(150)])


def test_unchanged_owned_timeline_is_copied_once_and_old_index_keeps_its_snapshot(monkeypatch):
    copies = []
    original = module._segment_snapshot

    def snapshot(values):
        copies.append(values)
        return original(values)

    monkeypatch.setattr(module, "_segment_snapshot", snapshot)
    values = _long_values()
    cache = module.SlotOverlapReuse()
    old = cache.index("machine", "M", values)
    for _ in range(30):
        assert cache.index("machine", "M", values) is old
        assert old.shift_end(dt(0), dt(0.5)) == dt(1)
    assert len(copies) == 1
    values[0] = (dt(0), dt(3))
    new = cache.index("machine", "M", values)
    assert len(copies) == 2
    assert new.shift_end(dt(0), dt(0.5)) == dt(3)
    assert old.shift_end(dt(0), dt(0.5)) == dt(1)


@pytest.mark.parametrize("mutation", ["append", "insert", "same_length", "slice", "delete", "clear", "replace"])
@pytest.mark.parametrize("long_timeline", [False, True])
def test_owned_changes_match_fresh_overlap_index(mutation, long_timeline):
    values = _long_values() if long_timeline else OwnedSegments([(dt(0), dt(1)), (dt(2), dt(3))])
    cache = module.SlotOverlapReuse()
    cache.index("machine", "M", values)
    if mutation == "append":
        values.append((dt(3), dt(4)))
    elif mutation == "insert":
        values.insert(1, (dt(1), dt(2)))
    elif mutation == "same_length":
        values[1] = (dt(2), dt(4))
    elif mutation == "slice":
        values[:] = [(dt(0), dt(4))]
    elif mutation == "delete":
        del values[0]
    elif mutation == "clear":
        values.clear()
    else:
        values = OwnedSegments([(dt(0), dt(4))])
    actual = cache.index("machine", "M", values)
    fresh = module.SlotOverlapReuse().index("machine", "M", values)
    for start in (dt(0), dt(1.5), dt(2), dt(3.5)):
        actual.begin_estimate()
        fresh.begin_estimate()
        assert actual.shift_end(start, dt(4)) == fresh.shift_end(start, dt(4))


def test_overridden_owner_mutation_uses_content_instead_of_stale_revision(monkeypatch):
    values = _long_values()
    cache = module.SlotOverlapReuse()
    cache.index("machine", "M", values)
    certificate = values.certificate()

    def untracked_append(owner, value):
        owner._values[0] = value

    monkeypatch.setattr(MutableSequence, "append", untracked_append)
    values.append((dt(0), dt(5)))
    assert values.certificate() == certificate
    assert cache.index("machine", "M", values).shift_end(dt(0), dt(0.5)) == dt(5)


def test_shadowed_certificate_and_borrowed_same_length_edit_do_not_reuse_stale_index():
    values = _long_values()
    cache = module.SlotOverlapReuse()
    cache.index("machine", "M", values)
    certificate = values.certificate()
    values.certificate = lambda: certificate
    values[0] = (dt(0), dt(4))
    assert cache.index("machine", "M", values).shift_end(dt(0), dt(0.5)) == dt(4)
    borrowed = [(dt(0), dt(2))]
    cache.index("machine", "M", borrowed)
    borrowed[0] = (dt(0), dt(6))
    assert cache.index("machine", "M", borrowed).shift_end(dt(0), dt(0.5)) == dt(6)


def test_short_timelines_use_exact_content_without_paying_for_owner_protocol_guards(monkeypatch):
    cache = module.SlotOverlapReuse()

    def unexpected_guard(_values):
        raise AssertionError("short snapshots must not certify the owner")

    monkeypatch.setattr(cache, "_owned_certificate", unexpected_guard)
    values = OwnedSegments([(dt(0), dt(1))])
    cache.index("machine", "M", values)
    values[0] = (dt(0), dt(3))
    assert cache.index("machine", "M", values).shift_end(dt(0), dt(0.5)) == dt(3)


def test_small_decode_selects_original_snapshot_path_once_and_preserves_mutation(monkeypatch):
    from core.algorithm_runtime.owned_timeline import OwnedTimeline

    timeline = OwnedTimeline()
    timeline["M"] = [(dt(0), dt(1))]
    with module.sgs_overlap_reuse(timeline, expected_operations=40):
        cache = module.overlap_reuse_for(timeline)
        monkeypatch.setattr(cache, "_owned_certificate", lambda _values: pytest.fail("small decode must use content"))
        before = cache.index("machine", "M", timeline["M"])
        timeline["M"][0] = (dt(0), dt(3))
        assert cache.index("machine", "M", timeline["M"]).shift_end(dt(0), dt(0.5)) == dt(3)
        assert before.shift_end(dt(0), dt(0.5)) == dt(1)
