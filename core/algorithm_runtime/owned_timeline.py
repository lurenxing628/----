"""Run-owned segment sequences with a complete public mutation protocol."""

from __future__ import annotations

from collections.abc import MutableSequence
from datetime import datetime
from typing import Any, Dict, List, Tuple, cast

Segment = Tuple[datetime, datetime]


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


class OwnedTimeline(Dict[str, List[Segment]]):
    """A native run copies inserted lists into owned segment sequences."""

    def __setitem__(self, key: str, value: Any) -> None:
        # The inherited Dict[str, List[Segment]] annotation keeps timeline callers typed while
        # wrapping inserted sequences into OwnedSegments so mutations advance the owner certificate.
        super().__setitem__(key, cast(Any, OwnedSegments(value)))

    def setdefault(self, key: str, default: Any) -> Any:
        if key not in self:
            self[key] = default
        return self[key]

    def update(self, *args: Any, **kwargs: Any) -> None:
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def clone(self) -> OwnedTimeline:
        """Independent copy with one segment-list allocation per resource and fresh owner identities."""
        cloned = OwnedTimeline()
        for key, values in self.items():
            owned: Any = OwnedSegments(cast(OwnedSegments, values)._values)
            dict.__setitem__(cloned, key, owned)
        return cloned


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
