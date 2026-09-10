"""Stable action denominator; the planning capability manifest stays untouched."""

FAMILIES = {
    "WBP-DASH-001": "metric-delivery metric-pressure metric-external metric-actual metric-pending card-delivery card-actual card-external card-downtime card-material card-candidate category-select tab-items tab-analysis tab-compare tab-records keyboard-tabs",
    "WBP-DASH-002": "status-all status-open status-new status-following status-verification status-closed search-batch search-owner search-action search-remark clear",
    "WBP-DASH-003": "edit-status edit-owner edit-deadline edit-action edit-remark submit cancel reject-invalid retain-failed-draft",
    "WBP-DASH-004": "edit-completed-at edit-evidence-ref edit-completion-result close view-closed reject-incomplete retain-risk-facts",
    "WBP-DASH-005": "open-reopen require-reason confirm-reopen cancel-reopen preserve-closed-history",
    "WBP-DASH-006": "open-history select-history reverse-order expand-before-after source-records history-page",
    "WBP-DASH-007": "hover-resource select-batch affected-batches compare-navigation",
    "WBP-DASH-008": "deviation-table actual-comparison-navigation field-report-navigation",
    "WBP-DASH-009": "filter-awaiting filter-overdue filter-returned open-registration tracking-basis",
    "WBP-DASH-010": "reject-missing-sent reject-missing-planned reject-reverse reject-future-sent reject-future-return reject-state-time preview save correct cancel original-receipt",
    "WBP-DASH-011": "downtime-bar plan-task-bar overlap-table reason-recorded-at",
    "WBP-DASH-012": "batch quantity due-date ready-status ready-date constraints",
    "WBP-DASH-013": "candidate-radio benefits-costs per-batch-change summary-dialog",
    "WBP-DASH-014": "no-independent-candidate existing-candidates navigation-confirm unlocatable return-context",
    "WBP-SYS-001": "source-current source-sample tab-overview tab-backups tab-logs tab-config keyboard-tabs metric-page metric-source metric-database metric-backup",
    "WBP-SYS-002": "row-backups row-logs row-config",
    "WBP-SYS-003": "check-runtime check-scripts check-ui check-icons check-styles check-model check-download check-theme rerun timestamp",
    "WBP-SYS-004": "download-json verify-json-payload",
    "WBP-SYS-005": "time type status filename size detail unread-state",
    "WBP-SYS-006": "search type-manual type-auto type-before-restore type-restore type-cleanup status start-date end-date clear",
    "WBP-SYS-007": "previous next size-10 size-25 size-50 close-x close-escape full-body validation-details",
    "WBP-SYS-008": "create receipt database-payload failure",
    "WBP-SYS-009": "select confirm cancel drain protection-backup verify restored-readonly rollback rollback-failure restart preserve-new-data",
    "WBP-SYS-010": "select confirm cancel filesystem-removal receipt",
    "WBP-SYS-011": "runtime-source operation-source columns detail",
    "WBP-SYS-012": "search-detail search-file type-runtime type-operation status level record-set start-date end-date clear page detail",
    "WBP-SYS-013": "export all-filtered-pages verify-rows",
    "WBP-SYS-014": "build-zip download-zip verify-manifest",
    "WBP-SYS-015": "light dark size-10 size-25 size-50 compact",
    "WBP-SYS-016": "auto_backup_enabled auto_backup_interval_minutes auto_backup_cleanup_enabled auto_backup_keep_days auto_backup_cleanup_interval_minutes auto_log_cleanup_enabled auto_log_cleanup_keep_days auto_log_cleanup_interval_minutes read-snapshot unknown-values",
    "WBP-SYS-017": "validate invalid-fields unsaved-preview discard-confirm discard-cancel",
    "WBP-SYS-018": "save original-receipt unknown-result lookup reload restart",
    "WBP-SYS-019": "scope request-trigger skipped blocked pending unverified failure rollback-failure",
}

# The latest explicit request adds a file download, absent from the old title.
EXTRA_ACTIONS = {"WBP-SYS-008": "download-backup verify-downloaded-database"}


def actions():
    rows = []
    for family, suffixes in FAMILIES.items():
        for suffix in (suffixes + " " + EXTRA_ACTIONS.get(family, "")).split():
            rows.append({"action_id": family + "." + suffix, "family_id": family})
    return rows
