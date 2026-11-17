"""Explicit history catalog schema and contract validation."""

from core.models.enums import nullable_time_us_check

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql

HISTORY_TABLES = ("WorkbenchHistoryEntries",)


def workbench_history_objects():
    return {
        "WorkbenchHistoryEntries": f"""CREATE TABLE WorkbenchHistoryEntries (
            entry_ref TEXT NOT NULL PRIMARY KEY,
            timeline TEXT NOT NULL CHECK(timeline IN ('run','official')),
            source_kind TEXT NOT NULL CHECK(source_kind IN ('run','candidate_adoption','trial_adoption')),
            state TEXT NOT NULL,
            occurred_at TEXT,
            occurred_day TEXT,
            occurred_us INTEGER {nullable_time_us_check('occurred_us')},
            time_basis TEXT,
            static_label TEXT,
            run_ref TEXT,
            candidate_ref TEXT,
            scenario_ref TEXT,
            draft_ref TEXT,
            plan_ref TEXT,
            plan_version INTEGER,
            receipt_ref TEXT,
            request_key TEXT NOT NULL UNIQUE,
            baseline_plan_ref TEXT,
            baseline_version INTEGER,
            selected_candidate_ref TEXT,
            selection_json TEXT NOT NULL,
            times_json TEXT NOT NULL,
            evidence_gaps_json TEXT NOT NULL,
            objective_json TEXT NOT NULL,
            static_condition_digest TEXT,
            default_7d_calendar_digest TEXT
        )""",
        "idx_wb_history_timeline_order": (
            "CREATE INDEX idx_wb_history_timeline_order "
            "ON WorkbenchHistoryEntries(timeline, state, occurred_day, occurred_us, entry_ref)"
        ),
        "idx_wb_history_run_ref": "CREATE INDEX idx_wb_history_run_ref ON WorkbenchHistoryEntries(run_ref)",
        "wb_history_entry_bind_adoption_receipt": """CREATE TRIGGER wb_history_entry_bind_adoption_receipt
            AFTER INSERT ON WorkbenchCommandReceipts
            WHEN NEW.action IN ('scheduling.candidate.adopt', 'trial.scenario.adopt')
             AND json_extract(NEW.outcome_json, '$.result') = 'committed'
            BEGIN
                UPDATE WorkbenchHistoryEntries
                SET entry_ref = 'adoption:' || NEW.receipt_ref,
                    receipt_ref = NEW.receipt_ref,
                    occurred_at = COALESCE(occurred_at, NEW.committed_at_utc),
                    occurred_day = COALESCE(occurred_day, substr(NEW.committed_at_utc, 1, 10)),
                    times_json = json_set(times_json, '$.committed_at_utc', NEW.committed_at_utc)
                WHERE request_key = NEW.request_key
                  AND source_kind IN ('candidate_adoption', 'trial_adoption');
            END""",
    }


def workbench_history_contract_issues(structure: SchemaStructure):
    actual = structure.sql
    return [
        ("missing_history_schema:" if name not in actual else "invalid_history_schema:") + name
        for name, sql in workbench_history_objects().items()
        if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)
    ]
