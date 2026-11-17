"""Request-local reads of original history sources inside one read snapshot."""

from typing import Dict, List, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.candidate_read_source import CandidateReadSource, SavedRun, load_saved_run
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import validate_candidate_tasks
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.trial_scenario_archive import load_verified_scenario
from core.services.workbench.history_entries.conditions import (
    prepare_history_condition_side,
    prepare_history_condition_source,
)
from core.services.workbench.history_entries.packets import (
    HistoryPacket,
    LightRunPacket,
    RunPacket,
    TrialPacket,
    UnavailablePacket,
)
from core.services.workbench.run.decision import decision_history_candidate
from core.services.workbench.run.decision_source import DecisionSource
from data.repositories.workbench_history_catalog_repo import WorkbenchHistoryCatalogRepository


def _condition_key(packet):
    if isinstance(packet, UnavailablePacket):
        if packet.ref is None:
            return ("empty", packet.source_issue["code"], packet.source_issue["message"])
        return ("entry", packet.entry_ref)
    if isinstance(packet, RunPacket):
        return ("run", packet.ref, packet.candidate_ref)
    return ("trial", packet.ref, None)


def _cached(cache, key, load):
    if key not in cache:
        try:
            cache[key] = load()
        except WorkbenchCommandRejected as exc:
            if exc.status != 404:
                raise
            cache[key] = exc.with_traceback(None)
    value = cache[key]
    if isinstance(value, WorkbenchCommandRejected):
        raise value.with_traceback(None)
    return value


class _HistoryCandidateStore(CandidateStore):
    """Request-local CandidateStore sharing 404 lookups and archives across history events."""

    def __init__(self, conn):
        super().__init__(conn)
        self._saved = {}

    def run(self, run_ref):
        return _cached(self._saved, ("run", run_ref), lambda: super(_HistoryCandidateStore, self).run(run_ref))

    def receipt(self, run):
        return _cached(self._saved, ("receipt", run["run_ref"]), lambda: super(_HistoryCandidateStore, self).receipt(run))

    def candidates(self, run_ref):
        return _cached(self._saved, ("candidates", run_ref), lambda: super(_HistoryCandidateStore, self).candidates(run_ref))

    def candidate_run(self, candidate_ref):
        return _cached(
            self._saved,
            ("candidate_run", candidate_ref),
            lambda: super(_HistoryCandidateStore, self).candidate_run(candidate_ref),
        )

    def capture(self, run_ref):
        return _cached(self._saved, ("capture", run_ref), lambda: super(_HistoryCandidateStore, self).capture(run_ref))

    def tasks(self, candidate_ref):
        return _cached(self._saved, ("tasks", candidate_ref), lambda: super(_HistoryCandidateStore, self).tasks(candidate_ref))


def _translate_missing_source(load):
    try:
        return load()
    except WorkbenchCommandRejected as exc:
        if exc.status != 404:
            raise
        raise WorkbenchCommandRejected(
            "history_source_invalid", "历史记录的保存来源缺失，请联系维护人员核对。", 500
        ) from exc


class HistoryReader:
    """Load only requested entries; repeated adoption events share their source."""

    def __init__(self, conn):
        if not conn.in_transaction:
            raise RuntimeError("History sources require the caller's read transaction")
        self.conn = conn
        self.store = _HistoryCandidateStore(conn)
        self.catalog_repo = WorkbenchHistoryCatalogRepository(conn)
        self._runs = {}
        self._run_batches = {}
        self._candidates = {}
        self._run_candidates: Dict[str, List[CandidateReadSource]] = {}
        self._scenarios = {}
        self._entries = {}
        self._metric_packets = {}
        self._sources = {}
        self._decisions = {}
        self._condition_sources = {}
        self._condition_sides = {}
        self.history_metrics_cache = {}
        self.history_range_facts = {}

    def prepared_condition_source(self, packet):
        key = _condition_key(packet)
        if key not in self._condition_sources:
            self._condition_sources[key] = prepare_history_condition_source(packet)
        return self._condition_sources[key]

    def condition_source(self, packet):
        return self.prepared_condition_source(packet)["source"]

    def condition_side(self, packet, window):
        source_key = _condition_key(packet)
        key = (source_key, window["start"], window["end"])
        if key not in self._condition_sides:
            self._condition_sides[key] = prepare_history_condition_side(
                self.prepared_condition_source(packet), window
            )
        return self._condition_sides[key]

    def run_batches(self, run_ref):
        if run_ref not in self._run_batches:
            self._run_batches[run_ref] = self.catalog_repo.run_batch_quantities(run_ref)
        return self._run_batches[run_ref]

    def _run(self, run_ref) -> SavedRun:
        return _cached(
            self._runs,
            run_ref,
            lambda: load_saved_run(self.store, self.store.run(run_ref), self.store.candidates(run_ref)),
        )

    def _loaded_run(self, run_ref) -> Optional[SavedRun]:
        """The run this reader already read, or None; a missing source it found is raised again."""
        return self._run(run_ref) if run_ref in self._runs else None

    def _candidate(self, run_ref, candidate_ref):
        def load():
            saved = self._run(run_ref)
            candidate = next((row for row in self.store.candidates(run_ref) if row["candidate_ref"] == candidate_ref), None)
            if candidate is None:
                if self.store.candidate_run(candidate_ref) != run_ref:
                    raise WorkbenchCommandRejected("history_source_invalid", "历史候选与原排产编号不一致。", 500)
                corrupt()
            source = CandidateReadSource.of(saved, candidate, validate_candidate_tasks(self.store, candidate, saved.facts))
            self._run_candidates.setdefault(run_ref, []).append(source)
            return source

        return _cached(self._candidates, (run_ref, candidate_ref), load)

    def read(self, descriptor):
        entry_ref = descriptor["entry_ref"]
        if entry_ref not in self._entries:
            self._entries[entry_ref] = self._read(descriptor)
        return self._entries[entry_ref]

    def metric_packet(self, descriptor) -> HistoryPacket:
        """Return a lightweight packet for metric projection when full archive deserialization is unnecessary."""
        entry_ref = descriptor["entry_ref"]
        if entry_ref in self._entries:
            return self._entries[entry_ref]
        if entry_ref not in self._metric_packets:
            self._metric_packets[entry_ref] = self._build_metric_packet(descriptor)
        return self._metric_packets[entry_ref]

    def _build_metric_packet(self, descriptor) -> HistoryPacket:
        _source_kind, refs, kind, ref, source_issue = self._descriptor_identity(descriptor)
        if source_issue is not None:
            return UnavailablePacket(kind, ref, descriptor["entry_ref"], source_issue)
        if kind == "trial":
            return self.read(descriptor)
        candidate_ref = refs["candidate_ref"]
        if candidate_ref is None:
            return self.read(descriptor)
        # A run's catalog entry joins its stored input, admitted there (catalog.admitted_run_input).
        run_input = descriptor["run_input"]
        if run_input is None:
            raise WorkbenchCommandRejected("history_source_invalid", "历史记录的保存来源缺失，请联系维护人员核对。", 500)
        return LightRunPacket(ref, descriptor["entry_ref"], run_input, candidate_ref)

    @staticmethod
    def _descriptor_identity(descriptor):
        source_kind, refs = descriptor["source_kind"], descriptor["source"]
        kind = "trial" if source_kind == "trial_adoption" else "run"
        ref = refs["run_ref"] if kind == "run" else refs["scenario_ref"]
        source_issue = None
        if source_kind in ("candidate_adoption", "trial_adoption"):
            gap = next(
                (row for row in descriptor["evidence_gaps"] if row["code"] == "audit_missing"),
                None,
            )
            if gap is not None:
                source_issue = {"code": gap["code"], "message": gap["message"]}
        return source_kind, refs, kind, ref, source_issue

    def _read(self, descriptor) -> HistoryPacket:
        _source_kind, refs, kind, ref, source_issue = self._descriptor_identity(descriptor)
        entry_ref = descriptor["entry_ref"]
        if source_issue is not None:
            return UnavailablePacket(kind, ref, entry_ref, source_issue)
        return _translate_missing_source(
            lambda: self._read_run(ref, entry_ref, refs) if kind == "run" else self._read_trial(ref, entry_ref, refs)
        )

    def _read_run(self, ref, entry_ref, refs) -> RunPacket:
        saved = self._run(refs["run_ref"])
        candidate_ref = refs["candidate_ref"]
        if candidate_ref is None:
            return RunPacket(ref, entry_ref, saved.capture, saved.facts, saved.receipt, None, None)
        source = self._candidate(refs["run_ref"], candidate_ref)
        return RunPacket(ref, entry_ref, saved.capture, saved.facts, saved.receipt, source.candidate, source.raw_tasks)

    def _read_trial(self, ref, entry_ref, refs) -> TrialPacket:
        source = _cached(
            self._scenarios,
            refs["scenario_ref"],
            lambda: load_verified_scenario(self.conn, refs["scenario_ref"]),
        )
        return TrialPacket(ref, entry_ref, source.saved, source.head, source.rows, source.origin)

    def source_state(self, descriptor):
        _source_kind, _refs, kind, ref, source_issue = self._descriptor_identity(descriptor)
        return {
            "kind": kind,
            "ref": ref,
            "entry_ref": descriptor["entry_ref"],
            "source": descriptor["source"],
            "state": descriptor["state"],
            "source_issue": source_issue,
        }

    def run_source(self, run_ref, candidate_ref, *, range_start, range_end):
        key = (run_ref, candidate_ref, range_start, range_end)

        def load():
            source = _translate_missing_source(
                lambda: DecisionSource(
                    self.store,
                    run_ref,
                    selected_candidate_ref=candidate_ref,
                    range_start=range_start,
                    range_end=range_end,
                    resource_view="full_candidate",
                    run=self._loaded_run(run_ref),
                    candidate_sources=tuple(self._run_candidates.get(run_ref, ())),
                )
            )
            if candidate_ref is not None and source.selected is None:
                owner = _translate_missing_source(lambda: self.store.candidate_run(candidate_ref))
                if owner != run_ref:
                    raise WorkbenchCommandRejected("history_source_invalid", "历史候选与原排产编号不一致。", 500)
                corrupt()
            return source

        return _cached(self._sources, key, load)

    def decision(self, run_ref, range_start, range_end, *, candidate_ref, metric_keys=None):
        key = (run_ref, candidate_ref, range_start, range_end, None if metric_keys is None else tuple(metric_keys))
        return _cached(
            self._decisions,
            key,
            lambda: decision_history_candidate(
                self.run_source(run_ref, candidate_ref, range_start=range_start, range_end=range_end),
                metric_keys=metric_keys,
            ),
        )
