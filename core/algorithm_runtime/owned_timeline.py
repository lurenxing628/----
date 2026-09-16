"""Run-owned segment sequences with a complete public mutation protocol."""

from collections.abc import MutableSequence
from datetime import datetime
from typing import Any

from .native_snapshot import make_class_guard
from .slot_overlap_reuse import SlotReuseTimeline


class OwnedSegments(MutableSequence):
    """No list inheritance: list.__setitem__ cannot bypass the revision counter."""

    def __init__(self, values=()):
        self._values = list(values)
        self._identity = object()
        self._revision = 0
        self._checked_revision = -1
        self._native = False

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
        native_before = self._checked_revision == self._revision and self._native
        try:
            self._values.insert(index, value)
        finally:
            self._revision += 1
        if native_before:
            self._native = self._native_item(value)
            self._checked_revision = self._revision

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
        if self._checked_revision != self._revision:
            self._native = all(self._native_item(value) for value in self._values)
            self._checked_revision = self._revision
        return (self._identity, self._revision) if self._native else None

    @staticmethod
    def _native_item(value):
        return _native_segment(value)


class OwnedTypeEntries(OwnedSegments):
    """The same mutation protocol for actual (start, end, op_id, type) rows."""

    @staticmethod
    def _native_item(value):
        return (type(value) is tuple and len(value) == 4 and type(value[2]) is int and type(value[3]) is str
                and all(type(item) is datetime and item.tzinfo is None for item in value[:2]))


def _native_segment(value):
    return (type(value) is tuple and len(value) == 2
            and all(type(item) is datetime and item.tzinfo is None for item in value))


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


_SEGMENTS_GUARD = make_class_guard(OwnedSegments)
_TYPE_ENTRIES_GUARD = make_class_guard(OwnedTypeEntries)
_SEGMENT_PROTOCOL_NAMES = frozenset(
    key for base in OwnedSegments.__mro__ for key, value in vars(base).items()
    if callable(value) or isinstance(value, (property, staticmethod, classmethod))
    or key in ("__getattribute__", "__getattr__", "__dict__"))
_NATIVE_SEGMENT_CERTIFICATE = OwnedSegments.certificate


def owned_segment_certificate(values):
    """Only unchanged native owners may replace a content comparison by a revision."""
    if type(values) is not OwnedSegments or not _SEGMENTS_GUARD(values):
        return None
    return values.certificate()


def owned_segment_round_reader(values):
    """Certify the protocol once for a closed native SGS scoring round.

    The owner must discard this reader at the next round. Every public data mutation
    still changes its revision, and new instance-level method overrides invalidate it.
    """
    if type(values) is not OwnedSegments or not _SEGMENTS_GUARD(values):
        return None

    def read():
        if type(values) is not OwnedSegments or not vars(values).keys().isdisjoint(_SEGMENT_PROTOCOL_NAMES):
            return None
        return _NATIVE_SEGMENT_CERTIFICATE(values)

    return read


def owned_type_certificate(values):
    if type(values) is not OwnedTypeEntries or not _TYPE_ENTRIES_GUARD(values):
        return None
    return values.certificate()


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
