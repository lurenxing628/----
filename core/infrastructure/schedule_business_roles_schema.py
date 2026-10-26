"""Exact native candidate declarations before and after the v42 role extension."""

from .schema_structure import schema_objects
from .workbench_metadata_schema import canonical_sql

REBUILD_TABLES = ("ScheduleCandidate", "ScheduleCandidateRows", "ScheduleCandidateSelection")
_LEGACY_TABLES = {
    "ScheduleCandidate": """CREATE TABLE ScheduleCandidate (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    version               INTEGER NOT NULL,
    candidate_key         TEXT NOT NULL,
    candidate_label       TEXT NOT NULL,
    candidate_kind        TEXT NOT NULL CHECK(candidate_kind IN ('baseline', 'critical_chain')),
    status                TEXT NOT NULL CHECK(status IN ('completed', 'failed', 'skipped', 'not_run')),
    graph_enabled         TEXT NOT NULL DEFAULT 'no' CHECK(graph_enabled IN ('yes', 'no')),
    weight_level          INTEGER,
    weight_count          INTEGER,
    critical_weight       INTEGER,
    impact_weight         INTEGER,
    downstream_weight     INTEGER,
    sort_strategy         TEXT,
    dispatch_mode         TEXT,
    dispatch_rule         TEXT,
    objective             TEXT,
    score_json            TEXT,
    metrics_json          TEXT,
    health_json           TEXT,
    summary_json          TEXT,
    selection_reason      TEXT,
    failure_reason        TEXT,
    detail_saved          TEXT NOT NULL DEFAULT 'no' CHECK(detail_saved IN ('yes', 'no')),
    elapsed_ms            INTEGER,
    started_at            DATETIME,
    finished_at           DATETIME,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(version, candidate_key),
    UNIQUE(id, version)
)
""",
    "ScheduleCandidateSelection": """CREATE TABLE ScheduleCandidateSelection (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version         INTEGER NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('adopted', 'baseline_best', 'critical_best')),
    candidate_id    INTEGER NOT NULL,
    source_table    TEXT NOT NULL CHECK(source_table IN ('schedule', 'candidate_rows')),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(candidate_id, version) REFERENCES ScheduleCandidate(id, version) ON DELETE CASCADE,
    UNIQUE(version, role)
)
""",
}


def objects(*, legacy=False):
    """Own only the two CHECK changes; every other declared field stays exact."""
    definitions = dict(_LEGACY_TABLES)
    if not legacy:
        definitions["ScheduleCandidate"] = definitions["ScheduleCandidate"].replace(
            "CHECK(candidate_kind IN ('baseline', 'critical_chain'))",
            "CHECK(candidate_kind IN ('baseline', 'critical_chain', 'business_objective'))")
        definitions["ScheduleCandidateSelection"] = definitions["ScheduleCandidateSelection"].replace(
            "CHECK(role IN ('adopted', 'baseline_best', 'critical_best'))",
            "CHECK(role IN ('adopted', 'baseline_best', 'critical_best', 'min_overdue', 'min_tardiness', "
            "'min_changeover', 'min_weighted_tardiness'))")
    return definitions


def contract_issues(conn, *, structure=None, allow_legacy=False):
    """Recognize the declared CHECKs, including a version-tag-only false upgrade."""
    actual, current, legacy = schema_objects(conn, structure=structure), objects(), objects(legacy=True)
    issues = []
    for name, sql in current.items():
        if name not in actual:
            issues.append("missing_schedule_business_roles:" + name)
            continue
        accepted = (canonical_sql(sql), canonical_sql(legacy[name])) if allow_legacy else (canonical_sql(sql),)
        if canonical_sql(actual[name]) not in accepted:
            issues.append("invalid_schedule_business_roles:" + name)
    return issues
