"""Three saved sources, with original event identities and no metric calculation."""

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import NoReturn

from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_history import (
    MAX_DIRECTORY_BYTES,
    MAX_DIRECTORY_ROWS,
    MAX_DOCUMENT_BYTES,
    local_datetime,
)
from core.services.workbench.facts.decision_read_models import public_run_head, read_model_json
from data.repositories.workbench_history_catalog_repo import WorkbenchHistoryCatalogRepository

_REF_FIELDS = ("run_ref", "candidate_ref", "scenario_ref", "draft_ref", "plan_ref", "version", "history_id", "receipt_ref", "request_key")
_TIME_FIELDS = ("accepted_at", "started_at", "finished_at", "adopted_at", "committed_at_utc", "schedule_time")
_ADOPTION_SOURCES = {"scheduling.candidate.adopt": "candidate_adoption", "trial.scenario.adopt": "trial_adoption"}
_AUDIT_SOURCES = {"candidate_adoption": "workbench_candidate_adoption", "trial_adoption": "workbench_trial_adoption"}


def _gap(field, code="not_recorded"):
    return {"field": field, "code": code, "message": "原记录未保存此项。" if code == "not_recorded" else "原记录的此项无法确认。"}


def _invalid() -> NoReturn:
    raise WorkbenchCommandRejected("history_source_invalid", "历史记录的来源或提交结果不一致，请联系维护人员核对。", 500)


def _object(raw):
    parsed = parse_result_summary_payload(raw)
    if parsed.parse_failed or parsed.payload is None:
        _invalid()
    return parsed.payload


def _reference(value, length=48):
    if type(value) is not str or re.fullmatch("[0-9a-f]{" + str(length) + "}", value) is None:
        _invalid()
    return value


def _local_time(value, field, gaps):
    if value is None:
        gaps.append(_gap(field))
        return None
    try:
        local_datetime(value)
        return value
    except (ValueError, TypeError):
        gaps.append(_gap(field, "invalid_stored_time"))
        return None


def _utc_to_factory(value, field, gaps):
    if value is None:
        gaps.append(_gap(field))
        return None
    try:
        if type(value) is not str or not value.endswith("Z"):
            raise ValueError("Expected recorded UTC time")
        stamp = value[:-1]
        point = local_datetime(stamp).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        # Keep the saved precision after timezone conversion.
        digits = len(stamp.split(".", 1)[1]) if "." in stamp else 0
        return point.isoformat(timespec="seconds") + (("." + format(point.microsecond, "06d")[:digits]) if digits else "")
    except (ValueError, TypeError, OverflowError):
        gaps.append(_gap(field, "invalid_stored_time"))
        return None


def _descriptor(ref, kind, state, source, times, record, gaps):
    return {"entry_ref": ref, "timeline": "run" if kind == "run" else "official", "source_kind": kind,
            "state": state, "source": {key: source.get(key) for key in _REF_FIELDS},
            "times": {key: times.get(key) for key in _TIME_FIELDS}, "record": record,
            "baseline": {"plan_ref": None, "version": None}, "selected_candidate_ref": None,
            "selection": {}, "occurred_at": None, "time_basis": None, "evidence_gaps": gaps}


def _run(row):
    run_ref = _reference(row["run_ref"])
    admission = read_model_json(row, "scope_json")
    result = (read_model_json(row, "header_json")
              if row["header_version"] is not None or row["header_json"] is not None else None)
    public_run_head(row, admission, result)
    candidate_refs = {candidate["candidate_ref"] for candidate in (result or {}).get("candidates", [])}
    selection = (result or {}).get("selection") or {}
    if type(selection) is not dict:
        _invalid()
    gaps = []
    selected = selection.get("selected_candidate_ref")
    if selected is not None:
        _reference(selected)
        if selected not in candidate_refs:
            gaps.append(_gap("selected_candidate_ref", "selection_candidate_unavailable"))
    elif row["state"] in ("complete", "partial"):
        gaps.append(_gap("selected_candidate_ref"))
    source = {"run_ref": run_ref, "candidate_ref": selected, "receipt_ref": row["receipt_ref"], "request_key": row["request_key"]}
    entry = _descriptor("run:" + run_ref, "run", row["state"], source, row,
                        {"job": row, "admission": admission, "run_header": result}, gaps)
    occurred = _local_time(row["accepted_at"], "accepted_at", gaps)
    entry.update(selected_candidate_ref=selected, selection=selection,
                 occurred_at=occurred, time_basis="accepted_at_factory_local" if occurred is not None else None)
    return entry


def _audit(row, history, kind, data, plan, gaps):
    if history is None:
        gaps.append(_gap("adoption", "audit_missing"))
        return None
    parsed = parse_result_summary_payload(history["result_summary"])
    audit = parsed.payload
    refs = ("candidate_ref", "run_ref") if kind == "candidate_adoption" else ("scenario_ref", "draft_ref")
    required = {"request_key", "baseline_ref", "baseline_version", "version", "proof", "row_count",
                "validation", "is_simulation", "reason", "declared_operator"}
    if (audit is None or not required <= set(audit) or history["result_status"] != "success"
            or audit.get("source") != _AUDIT_SOURCES[kind]
            or audit["request_key"] != row["request_key"] or audit["version"] != plan["version"]
            or audit["baseline_ref"] != plan.get("baseline_ref") or audit["row_count"] != data["row_count"]
            or audit["validation"] != "valid" or audit["is_simulation"] is not False
            or type(audit["proof"]) is not dict or any(audit.get(key) != data[key] for key in refs)
            or any(audit["proof"].get(key) != data[key] for key in refs)):
        gaps.append(_gap("adoption", "audit_unproven"))
        return None
    return audit


def _adoption(row, histories, bindings):
    outcome = _object(row["outcome_json"])
    if outcome.get("result") != "committed":
        return None
    try:
        kind = _ADOPTION_SOURCES[row["action"]]
        data, plan = outcome["data"], outcome["data"]["official_plan"]
        if type(data) is not dict or type(plan) is not dict:
            _invalid()
        plan_ref, receipt_ref = _reference(plan["plan_ref"]), _reference(row["receipt_ref"], 32)
        if type(plan["version"]) is not int or plan["version"] < 1 or plan["kind"] != "official":
            _invalid()
        fields = ("candidate_ref", "run_ref") if kind == "candidate_adoption" else ("scenario_ref", "draft_ref")
        for key in fields:
            _reference(data[key])
        provenance = ("run_ref",) if kind == "candidate_adoption" else fields
        if (row["context_ref"] != data[fields[0]] or any(plan["source_" + key] != data[key] for key in provenance)
                or type(data["row_count"]) is not int or data["row_count"] < 0):
            _invalid()
        if kind == "trial_adoption" and any(key in data or key in plan for key in ("candidate_ref", "run_ref", "source_run_ref")):
            _invalid()
    except (KeyError, TypeError):
        _invalid()
    gaps = []
    rows = histories.get(plan["version"], [])
    history = rows[0] if len(rows) == 1 else None
    audit = _audit(row, history, kind, data, plan, gaps)
    binding = bindings.get(plan["version"])
    if binding is None or binding["ref"] != plan_ref:
        gaps.append(_gap("official_plan", "official_identity_unavailable"))
    source = {**{key: data[key] for key in fields}, "plan_ref": plan_ref, "version": plan["version"],
              "receipt_ref": receipt_ref, "request_key": row["request_key"], "history_id": history["id"] if history else None}
    times = {"adopted_at": audit.get("adopted_at") if audit else None, "committed_at_utc": row["committed_at_utc"],
             "schedule_time": history["schedule_time"] if history else None}
    entry = _descriptor("adoption:" + receipt_ref, kind, "committed", source, times,
                        {"receipt": row, "outcome": outcome, "history": history, "audit": audit}, gaps)
    entry["baseline"] = {"plan_ref": plan.get("baseline_ref"), "version": audit["baseline_version"] if audit else None}
    entry["occurred_at"] = _local_time(times["adopted_at"], "adopted_at", gaps)
    entry["time_basis"] = "adopted_at_factory_local"
    if entry["occurred_at"] is None:
        entry["occurred_at"] = _utc_to_factory(times["committed_at_utc"], "committed_at_utc", gaps)
        entry["time_basis"] = "committed_at_utc_to_factory_local" if entry["occurred_at"] is not None else None
    return entry


def _labels(entries):
    """Display order comes from the whole run directory, before any query filtering."""
    runs = sorted((entry for entry in entries if entry["source_kind"] == "run"),
                  key=lambda entry: (entry["occurred_at"] is None,
                      local_datetime(entry["occurred_at"]) if entry["occurred_at"] is not None else datetime.min,
                      entry["source"]["run_ref"]))
    for number, entry in enumerate(runs, 1):
        entry["label"] = "第" + str(number) + "次运行"
    names = {"candidate_adoption": "候选正式采用", "trial_adoption": "试调正式采用"}
    for entry in entries:
        if entry["source_kind"] != "run":
            entry["label"] = names[entry["source_kind"]] + " · 正式计划 v" + str(entry["source"]["version"])


def read_history_catalog(conn):
    """Read once inside the caller's transaction; filtering and paging belong to queries."""
    if not conn.in_transaction:
        raise RuntimeError("History catalog requires the caller's read transaction")
    repo = WorkbenchHistoryCatalogRepository(conn)
    byte_count = 0

    def _collect(rows, fields):
        nonlocal byte_count
        collected = []
        for count, row in enumerate(rows, 1):
            if count > MAX_DIRECTORY_ROWS:
                raise WorkbenchCommandRejected("history_capacity_exceeded", "历史目录超过读取上限，请联系维护人员处理。", 413)
            for field in fields:
                raw = row[field]
                if raw is not None:
                    if type(raw) is not str:
                        _invalid()
                    size = len(raw.encode("utf-8"))
                    byte_count += size
                    if size > MAX_DOCUMENT_BYTES or byte_count > MAX_DIRECTORY_BYTES:
                        raise WorkbenchCommandRejected("history_capacity_exceeded", "历史目录超过读取上限，请联系维护人员处理。", 413)
            collected.append(row)
        return collected

    jobs = _collect(repo.runs(), ("scope_json", "header_json"))
    receipts = _collect(repo.adoption_receipts(), ("outcome_json",))
    receipts.sort(
        key=lambda row: (
            (0, row["committed_at_utc"], row["request_key"])
            if type(row["committed_at_utc"]) is str
            else (1, f"{type(row['committed_at_utc']).__name__}:{row['committed_at_utc']!r}", row["request_key"])
        )
    )
    histories = _collect(repo.histories(), ("result_summary",))
    bindings = _collect(repo.official_bindings(), ("ref",))
    by_version, official = defaultdict(list), {}
    for row in histories:
        by_version[row["version"]].append(row)
    for row in bindings:
        if row["active"] == 1 and row["source_key"] == str(row["version"]) and row["plan_role"] == "adopted" and row["source_table"] == "schedule":
            official[row["version"]] = row
    entries = [_run(row) for row in jobs]
    adopted = [entry for entry in (_adoption(row, by_version, official) for row in receipts) if entry is not None]
    # 每个正式版本都由采用事务连同回执一起写下；没有回执的版本说明历史来源不一致。
    if set(by_version) - {entry["source"]["version"] for entry in adopted}:
        _invalid()
    entries.extend(adopted)
    _labels(entries)
    # Permanent source/receipt identities and the existing clock own freshness.
    state = {"entries": [{key: entry[key] for key in
                          ("entry_ref", "source_kind", "state", "source", "times", "evidence_gaps")}
                         for entry in entries],
             "runs": [{key: row[key] for key in ("run_ref", "state", "stage", "receipt_ref", "receipt_state", "recorded_at")}
                      for row in jobs], "identity_clock": repo.identity_clock()}
    return entries, state
