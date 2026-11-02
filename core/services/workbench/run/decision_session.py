"""One decision read session: the archived source under one read snapshot and its binding scope."""

from contextlib import contextmanager
from typing import Iterator

from core.infrastructure.read_evidence import read_evidence_scope
from core.services.workbench.facts.candidate_store import CandidateStore

from .decision_source import DecisionSource


@contextmanager
def decision_read(conn, run_ref, **query) -> Iterator[DecisionSource]:
    """One read snapshot's decision source.

    Every decision read prepares this source and binds its snapshot token before projecting from it.
    """
    store = CandidateStore(conn)
    with store.snapshot(), read_evidence_scope(conn):
        yield DecisionSource(store, run_ref, **query)


def decision_snapshot_scope(source, **view):
    """The read binding of one decision view: its comparison scope plus the view's own filters."""
    return {"kind": "run-decision", **source.scope, **view}
