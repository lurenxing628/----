"""Run-owned segment sequences with a complete public mutation protocol."""

from collections.abc import MutableSequence
from typing import Any

from .slot_reuse_timeline import SlotReuseTimeline


class OwnedSegments(MutableSequence):
    """No list inheritance: list.__setitem__ cannot bypass the revision counter."""

    def __init__(self, values=()):
        self._values = list(values)
        self._identity = object()
        self._revision = 0

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def __iter__(self):
        return iter(self._values)

    def __setitem__(self, index, value):
        try:
            self._values[index] = value
        finally:
            self._revision += 1

    def __delitem__(self, index):
        try:
            del self._values[index]
        finally:
            self._revision += 1

    def insert(self, index, value):
        try:
            self._values.insert(index, value)
        finally:
            self._revision += 1

    def sort(self, *, key=None, reverse=False):
        try:
            self._values.sort(key=key, reverse=reverse)
        finally:
            self._revision += 1

    def reverse(self):
        self._values.reverse()
        self._revision += 1

    def __imul__(self, count):
        try:
            self._values *= count
        finally:
            self._revision += 1
        return self

    def copy(self):
        return self._values.copy()

    def __eq__(self, other):
        if isinstance(other, OwnedSegments):
            return self._values == other._values
        return self._values == other

    def __repr__(self):
        return repr(self._values)

    def certificate(self):
        return self._identity, self._revision


class OwnedTypeEntries(OwnedSegments):
    """The same mutation protocol for actual (start, end, op_id, type) rows."""


class OwnedTimeline(SlotReuseTimeline):
    """A native run copies inserted lists; borrowed legacy maps are never wrapped."""

    def __setitem__(self, key, value):
        # The inherited legacy annotation says List; this private owner accepts
        # the same mutable-sequence operations without exposing borrowed aliases.
        owned: Any = OwnedSegments(value) if type(value) is list else value
        super().__setitem__(key, owned)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value


def owned_segment_certificate(values):
    """Only native owners may replace a content comparison by a revision."""
    if not isinstance(values, OwnedSegments):
        return None
    return values.certificate()


def owned_segment_round_reader(values):
    """Return a revision reader for a closed SGS scoring round."""
    if not isinstance(values, OwnedSegments):
        return None
    return values.certificate


def clone_timeline(mapping):
    """Independent copy of a resource timeline with the same container type.

    Segment rows are immutable tuples and are shared; every list is copied, so
    later occupations on either side never leak across. Owned containers re-wrap
    their lists through ``__setitem__`` and therefore start with fresh identities.
    """
    if type(mapping) is dict:
        return {key: list(values) for key, values in mapping.items()}
    if not isinstance(mapping, SlotReuseTimeline):
        raise TypeError("clone_timeline only accepts dict, SlotReuseTimeline or OwnedTimeline")
    clone = type(mapping)()
    for key, values in mapping.items():
        clone[key] = list(values)
    return clone
