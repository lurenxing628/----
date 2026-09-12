"""Every ordinary segment mutation invalidates; legacy list aliases stay untouched."""

from datetime import datetime, timedelta, timezone

import pytest

from core.algorithm_runtime.owned_timeline import OwnedSegments, OwnedTimeline

BASE = datetime(2026, 9, 7, 8)


def _segment(index):
    return BASE + timedelta(hours=index), BASE + timedelta(hours=index + 1)


@pytest.mark.parametrize("mutation", [
    "append", "insert", "extend", "setitem", "slice", "delitem", "delslice", "pop", "remove", "clear",
    "reverse", "sort", "iadd", "imul",
])
def test_all_public_mutations_change_native_certificate(mutation):
    values = OwnedSegments([_segment(0), _segment(1)])
    original = values.certificate()
    if mutation == "append":
        values.append(_segment(2))
    elif mutation == "insert":
        values.insert(1, _segment(2))
    elif mutation == "extend":
        values.extend([_segment(2), _segment(3)])
    elif mutation == "setitem":
        values[0] = _segment(2)
    elif mutation == "slice":
        values[:] = [_segment(2), _segment(3)]
    elif mutation == "delitem":
        del values[0]
    elif mutation == "delslice":
        del values[:1]
    elif mutation == "pop":
        values.pop()
    elif mutation == "remove":
        values.remove(_segment(0))
    elif mutation == "clear":
        values.clear()
    elif mutation == "reverse":
        values.reverse()
    elif mutation == "sort":
        values.sort(reverse=True)
    elif mutation == "iadd":
        values += [_segment(2)]
    else:
        values *= 2
    assert values.certificate() is not None
    assert values.certificate() != original


@pytest.mark.parametrize("value", [
    [BASE, BASE + timedelta(hours=1)], (BASE,), (BASE, "invalid"),
    (BASE.replace(tzinfo=timezone.utc), BASE.replace(tzinfo=timezone.utc)),
])
def test_uncertifiable_segments_never_get_a_version_only_certificate(value):
    values = OwnedSegments([_segment(0)])
    assert values.certificate() is not None
    values[0] = value
    assert values.certificate() is None
    values[:] = [_segment(0)]
    assert values.certificate() is not None


def test_normal_list_copy_is_owned_and_c_level_mutation_cannot_bypass_protocol():
    original = [_segment(0)]
    timeline = OwnedTimeline()
    timeline["M"] = original
    original[0] = _segment(1)
    assert timeline["M"] == [_segment(0)]
    assert timeline["M"].copy() == [_segment(0)]
    with pytest.raises(TypeError):
        list.__setitem__(timeline["M"], 0, _segment(2))
    # A deliberately borrowed plain list still gets content-based certificates.
    dict.__setitem__(timeline, "borrowed", original)
    assert timeline["borrowed"] is original


def test_inherited_mutator_override_invalidates_the_native_run(monkeypatch):
    from collections.abc import MutableSequence

    from core.algorithms.greedy.dispatch.sgs_reuse import _SEGMENTS_GUARD
    values = OwnedSegments([_segment(0)])
    assert _SEGMENTS_GUARD(values)
    monkeypatch.setattr(MutableSequence, "append", lambda self, value: None)
    assert not _SEGMENTS_GUARD(values)


def test_machine_type_versions_keep_tuple_api_and_refuse_overridden_certificates():
    from core.algorithm_runtime.resource_quality import MachineTypeState

    state = MachineTypeState()
    state.record("M", BASE, BASE + timedelta(hours=1), 1, "TURN")
    original = state.score_certificate("M")
    assert original is not None
    values = state._entries["M"]
    values[0] = (BASE, BASE + timedelta(hours=1), 1, "MILL")
    assert state.score_certificate("M") != original
    assert state.certificate("M") == ((BASE, BASE + timedelta(hours=1), 1, "MILL"),)
    setattr(values, "certificate", lambda: original)
    assert state.score_certificate("M") is None
