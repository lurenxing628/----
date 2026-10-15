"""Request-local reads of original history sources inside one read snapshot."""

from copy import deepcopy

from core.infrastructure.read_evidence import read_evidence_scope
from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import candidate_summary, dispositions, validate_manifest
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.decision_baseline_source import _candidate_evidence, _trial_evidence
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.trial_policy import load_scenario_record
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario
from core.services.workbench.run.decision import decision_overview
from core.services.workbench.run.decision_source import DecisionSource
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .conditions import prepare_history_condition_side, prepare_history_condition_source


def _condition_key(packet):
    issue = packet.get("source_issue")
    if packet["ref"] is None:
        return ("empty", issue["code"], issue["message"])
    if issue is not None:
        return ("entry", packet["entry_ref"])
    candidate = packet.get("candidate")
    return (packet["kind"], packet["ref"], candidate["candidate_ref"] if candidate is not None else None)


def _cached(cache, key, load):
    if key not in cache:
        try:
            cache[key] = load()
        except WorkbenchCommandRejected as exc:
            if exc.status != 404:
                raise
            cache[key] = exc
    value = cache[key]
    if isinstance(value, WorkbenchCommandRejected):
        raise value
    return value


class _HistoryCandidateStore(CandidateStore):
    """Keep CandidateStore's checks while sharing archived bytes across events."""

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
        return _cached(self._saved, ("candidate_run", candidate_ref), lambda: super(_HistoryCandidateStore, self).candidate_run(candidate_ref))

    def capture(self, run_ref):
        return _cached(self._saved, ("capture", run_ref), lambda: super(_HistoryCandidateStore, self).capture(run_ref))

    def tasks(self, candidate_ref):
        return _cached(self._saved, ("tasks", candidate_ref), lambda: super(_HistoryCandidateStore, self).tasks(candidate_ref))


def _packet(kind, ref, entry_ref):
    data = {"kind": kind, "ref": ref, "entry_ref": entry_ref}
    if kind == "run":
        data.update(capture=None, facts=None, candidate=None, receipt=None, raw_tasks=None)
    elif kind == "trial":
        data.update(saved=None, head=None, rows=[])
    elif kind == "legacy":
        data["parsed_summary"] = None
    else:
        raise ValueError("Unknown saved history source")
    return data


class HistoryReader:
    """Load only requested entries; repeated adoption events share their source.

    The caller owns the read transaction and evidence scope. Source packets retain
    event identity separately from the original candidate or saved scenario.
    """

    def __init__(self, conn, *, catalog=()):
        if not conn.in_transaction:
            raise RuntimeError("History sources require the caller's read transaction")
        self.conn = conn
        self.store = _HistoryCandidateStore(conn)
        self._run_schema_checked = False
        self._run_prepared = {descriptor["source"]["run_ref"]: {
            "head": descriptor["record"]["job"], "admission": descriptor["record"]["admission"],
            "header": descriptor["record"]["run_header"]} for descriptor in catalog
            if descriptor["source_kind"] == "run" and "admission" in descriptor["record"]}
        self._runs = {}
        self._candidates = {}
        self._scenarios = {}
        self._entries = {}
        self._source_states = {}
        self._sources = {}
        self._decisions = {}
        self._condition_sources = {}
        self._condition_sides = {}
        self.history_metrics_cache = {}

    def condition_source(self, packet):
        """Share a verified saved source while keeping missing-event evidence separate."""
        key = _condition_key(packet)
        if key not in self._condition_sources:
            self._condition_sources[key] = prepare_history_condition_source(packet)
        return self._condition_sources[key]["source"]

    def condition_side(self, packet, window):
        """Reuse production by source and window, retaining window-free settings."""
        source_key = _condition_key(packet)
        key = (source_key, window["start"], window["end"])
        if key not in self._condition_sides:
            self.condition_source(packet)
            self._condition_sides[key] = prepare_history_condition_side(self._condition_sources[source_key], window)
        return self._condition_sides[key]

    def _require_run_schema(self):
        if not self._run_schema_checked:
            if workbench_run_contract_issues(self.conn):
                raise WorkbenchCommandRejected("candidate_schema_unavailable", "排产记录结构不完整，请联系维护人员。", 503)
            self._run_schema_checked = True

    def _run(self, run_ref):
        self._require_run_schema()

        def load():
            prepared = self._run_prepared.get(run_ref, {})
            head = prepared.get("head")
            run = ({key: head[key] for key in ("run_ref", "state", "accepted_at", "finished_at")}
                   if head is not None else self.store.run(run_ref))
            if head is not None:
                self.store._saved[("run", run_ref)] = run
            receipt = self.store.receipt(run)
            rows = self.store.candidates(run_ref)
            validate_manifest(run, rows, receipt)
            capture = self.store.capture(run_ref)
            return {**prepared, "run": run, "receipt": receipt, "rows": rows, "capture": capture,
                    "facts": GenerationFacts(capture), "disposition": dispositions(receipt), "candidate_sources": {}}

        return _cached(self._runs, run_ref, load)

    def _candidate(self, run_ref, candidate_ref):
        def load():
            saved = self._run(run_ref)
            candidate = next((row for row in saved["rows"] if row["candidate_ref"] == candidate_ref), None)
            if candidate is None:
                # A missing source is distinct from a reference to another run.
                if self.store.candidate_run(candidate_ref) != run_ref:
                    raise WorkbenchCommandRejected("history_source_invalid", "历史候选与原排产编号不一致。", 500)
                corrupt()
            candidate_summary(candidate, saved["disposition"])
            source = read_candidate_source(self.store, candidate_ref, prepared={**saved, "candidate": candidate})
            saved["candidate_sources"][candidate_ref] = source
            return source

        return _cached(self._candidates, (run_ref, candidate_ref), load)

    def read(self, descriptor):
        """Return the frozen private source packet for one catalog descriptor."""
        entry_ref = descriptor["entry_ref"]
        if entry_ref not in self._entries:
            self._entries[entry_ref] = self._read(descriptor)
        return self._entries[entry_ref]

    def _read(self, descriptor):
        source_kind, refs = descriptor["source_kind"], descriptor["source"]
        kinds = {"run": "run", "candidate_adoption": "run", "trial_adoption": "trial", "legacy_official": "legacy"}
        kind = kinds[source_kind]
        ref = refs["run_ref"] if kind == "run" else refs["scenario_ref"] if kind == "trial" else str(refs["history_id"])
        packet = _packet(kind, ref, descriptor["entry_ref"])
        if source_kind in ("candidate_adoption", "trial_adoption") and descriptor["record"]["audit"] is None:
            gap = next((row for row in descriptor["evidence_gaps"] if row["code"] in ("audit_missing", "audit_unproven")), None)
            packet["source_issue"] = {"code": gap["code"], "message": gap["message"]} if gap else {
                "code": "audit_missing", "message": "原采用审计缺失，结果来源无法确认。"}
            return packet
        try:
            if kind == "run":
                self._read_run(packet, refs, descriptor)
            elif kind == "trial":
                self._read_trial(packet, refs, descriptor)
            else:
                packet["parsed_summary"] = descriptor["record"]["summary"]
        except WorkbenchCommandRejected as exc:
            if exc.status != 404:
                raise
            packet["source_issue"] = {"code": "source_missing", "message": "原候选、排产、试调场景或草稿已不存在。"}
        return packet

    def _read_run(self, packet, refs, descriptor):
        record = descriptor["record"]
        if descriptor["source_kind"] == "run" and "admission" in record:
            self._run_prepared[refs["run_ref"]] = {
                "head": record["job"], "admission": record["admission"], "header": record["run_header"]}
        saved = self._run(refs["run_ref"])
        packet.update(capture=saved["capture"], facts=saved["facts"], receipt=saved["receipt"])
        candidate_ref = refs["candidate_ref"]
        if candidate_ref is None:
            return
        source = self._candidate(refs["run_ref"], candidate_ref)
        if descriptor["source_kind"] == "candidate_adoption":
            audit = descriptor["record"]["audit"]
            _candidate_evidence(source, audit)
            if len(source.raw_tasks) != audit["row_count"]:
                raise WorkbenchCommandRejected("history_source_invalid", "采用记录与原候选安排条数不一致。", 500)
        packet.update(candidate=source.candidate, raw_tasks=source.raw_tasks)

    def _read_trial(self, packet, refs, descriptor):
        source = _cached(self._scenarios, refs["scenario_ref"], lambda: self._trial(refs["scenario_ref"]))
        saved, head, rows = source
        audit = descriptor["record"]["audit"]
        if head is None:
            if (saved["scenario_ref"] != refs["scenario_ref"] or saved["draft_ref"] != refs["draft_ref"]
                    or saved["baseline"] != {"plan_ref": audit["baseline_ref"], "version": audit["baseline_version"]}
                    or saved["task_count"] != audit["row_count"]):
                raise WorkbenchCommandRejected("history_source_invalid", "采用记录与原保存试调场景不一致。", 500)
            packet.update(saved=saved, head=None, rows=[], source_issue={"code": "source_missing",
                "message": "原试调草稿已不存在；保留原保存场景和原口径指标。"})
            return
        _trial_evidence(source, audit)
        if len(rows) != audit["row_count"]:
            raise WorkbenchCommandRejected("history_source_invalid", "采用记录与原试调安排条数不一致。", 500)
        packet.update(saved=saved, head=head, rows=rows)

    def _trial(self, scenario_ref):
        try:
            return load_saved_scenario(self.conn, scenario_ref)
        except WorkbenchCommandRejected as exc:
            if exc.status != 404:
                raise
            # A saved scene can outlive its draft. Keep only its verified saved
            # values; current projection still requires the missing admission.
            _header, saved = load_scenario_record(WorkbenchTrialRepository(self.conn), scenario_ref)
            return saved, None, []

    def source_state(self, descriptor):
        """Original JSON contents for selected/reference snapshot anchors only."""
        entry_ref = descriptor["entry_ref"]
        if entry_ref not in self._source_states:
            packet = self.read(descriptor)
            keys = {"run": ("capture", "candidate", "receipt", "raw_tasks"),
                    "trial": ("saved", "head", "rows"), "legacy": ("parsed_summary",)}[packet["kind"]]
            state = {"kind": packet["kind"], "ref": packet["ref"], "entry_ref": entry_ref,
                     **{key: packet[key] for key in keys}}
            if "source_issue" in packet:
                state["source_issue"] = packet["source_issue"]
            self._source_states[entry_ref] = deepcopy(state)
        return self._source_states[entry_ref]

    def run_source(self, run_ref, candidate_ref=None, *, range_start=None, range_end=None):
        """Reuse the existing decision source for the actual candidate and window."""
        self._require_run_schema()
        key = (run_ref, candidate_ref, range_start, range_end)
        return _cached(self._sources, key, lambda: DecisionSource(self.store, run_ref,
            selected_candidate_ref=candidate_ref, range_start=range_start, range_end=range_end,
            resource_view="full_candidate", prepared=self._runs.get(run_ref, self._run_prepared.get(run_ref))))

    def decision(self, run_ref, range_start=None, range_end=None, *, candidate_ref=None):
        """Return the same overview used by the run workspace, once per window."""
        key = (run_ref, candidate_ref, range_start, range_end)
        return _cached(self._decisions, key, lambda: decision_overview(self.run_source(run_ref, candidate_ref,
            range_start=range_start, range_end=range_end)))


def read_history_source(conn, descriptor):
    """One-off saved-source read; grouped history requests share HistoryReader."""
    with candidate_read_snapshot(conn), read_evidence_scope(conn):
        return HistoryReader(conn).read(descriptor)
