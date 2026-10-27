"""Request-local reads of original history sources inside one read snapshot."""

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import candidate_summary, dispositions, validate_manifest
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.decision_baseline_source import candidate_evidence, trial_evidence
from core.services.workbench.facts.decision_metrics import admission_operation_refs
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario
from core.services.workbench.run.decision import decision_history_candidate
from core.services.workbench.run.decision_source import DecisionSource

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
            cache[key] = exc.with_traceback(None)
    value = cache[key]
    if isinstance(value, WorkbenchCommandRejected):
        raise value.with_traceback(None)
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
        self._sources = {}
        self._decisions = {}
        self._condition_sources = {}
        self._condition_sides = {}
        self.history_metrics_cache = {}
        self.history_range_facts = {}

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
            if schema_contract_memo(self.conn).get_schema(workbench_run_contract_issues):
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
            facts = GenerationFacts(capture)
            disposition = dispositions(receipt, expected_refs=admission_operation_refs(facts, capture["input"]))
            return {**prepared, "run": run, "receipt": receipt, "rows": rows, "capture": capture,
                    "facts": facts, "disposition": disposition, "candidate_sources": {}}

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
            source = read_candidate_source(self.store, candidate_ref, prepared={**saved, "candidate": candidate})
            candidate_summary(candidate, saved["disposition"], scheduled_op_ids=source.scheduled_op_ids)
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
        kind = "trial" if source_kind == "trial_adoption" else "run"
        ref = refs["run_ref"] if kind == "run" else refs["scenario_ref"]
        packet = _packet(kind, ref, descriptor["entry_ref"])
        if source_kind in ("candidate_adoption", "trial_adoption") and descriptor["record"]["audit"] is None:
            gap = next((row for row in descriptor["evidence_gaps"] if row["code"] in ("audit_missing", "audit_unproven")), None)
            packet["source_issue"] = {"code": gap["code"], "message": gap["message"]} if gap else {
                "code": "audit_missing", "message": "原采用审计缺失，结果来源无法确认。"}
            return packet
        # Runs, candidates, drafts and scenarios are permanent; a missing source is damaged storage.
        try:
            if kind == "run":
                self._read_run(packet, refs, descriptor)
            else:
                self._read_trial(packet, refs, descriptor)
        except WorkbenchCommandRejected as exc:
            if exc.status != 404:
                raise
            raise WorkbenchCommandRejected("history_source_invalid", "历史记录的保存来源缺失，请联系维护人员核对。", 500) from exc
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
            candidate_evidence(source, audit)
            if len(source.raw_tasks) != audit["row_count"]:
                raise WorkbenchCommandRejected("history_source_invalid", "采用记录与原候选安排条数不一致。", 500)
        packet.update(candidate=source.candidate, raw_tasks=source.raw_tasks)

    def _read_trial(self, packet, refs, descriptor):
        source = _cached(self._scenarios, refs["scenario_ref"], lambda: load_saved_scenario(self.conn, refs["scenario_ref"]))
        saved, head, rows = source
        audit = descriptor["record"]["audit"]
        trial_evidence(source, audit)
        if len(rows) != audit["row_count"]:
            raise WorkbenchCommandRejected("history_source_invalid", "采用记录与原试调安排条数不一致。", 500)
        packet.update(saved=saved, head=head, rows=rows)

    def source_state(self, descriptor):
        """Saved sources bind their permanent references, state and known gaps."""
        packet = self.read(descriptor)
        return {"kind": packet["kind"], "ref": packet["ref"], "entry_ref": descriptor["entry_ref"],
                "source": descriptor["source"], "state": descriptor["state"],
                "source_issue": packet.get("source_issue")}

    def run_source(self, run_ref, candidate_ref, *, range_start, range_end):
        """Reuse the existing decision source for the actual candidate and window."""
        self._require_run_schema()
        key = (run_ref, candidate_ref, range_start, range_end)
        return _cached(self._sources, key, lambda: DecisionSource(self.store, run_ref,
            selected_candidate_ref=candidate_ref, range_start=range_start, range_end=range_end,
            resource_view="full_candidate", prepared=self._runs.get(run_ref, self._run_prepared.get(run_ref))))

    def decision(self, run_ref, range_start, range_end, *, candidate_ref):
        """Read this event's metrics under the workspace's common resource cohort."""
        key = (run_ref, candidate_ref, range_start, range_end)
        return _cached(self._decisions, key, lambda: decision_history_candidate(self.run_source(run_ref, candidate_ref,
            range_start=range_start, range_end=range_end)))
