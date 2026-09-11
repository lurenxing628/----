"""Sparse action mappings reviewed against the executed probe bodies, not family names."""


def ids(family, numbers):
    return ["WBP-" + family + "-A" + str(number).zfill(2) for number in numbers]


def entry(case, family, numbers, gates="BKP", persistence="view"):
    return {"case": case, "actions": ids(family, numbers), "gates": gates, "persistence": persistence}


def resource_mappings():
    rows = []
    for index, (family, fields, save) in enumerate([
        ("PROC-013", [2, 3, 4, 5, 6, 7], 10), ("PROC-014", [2, 3, 4], 5),
        ("PROC-015", [2, 3, 4, 5, 7], 8), ("PROC-016", [2, 3, 4, 5, 7], 8),
        ("PROC-017", [2, 3, 5, 6], 7), ("PROC-018", [2, 3, 4, 5, 7], 9),
    ]):
        create, edit = "create-" + str(index), "cancel-update-delete-" + str(index)
        rows.extend([entry(create, "PROC-001", [index + 1]), entry(create, family, fields, "K"),
                     entry(create, family, [save], "BKP", "command"),
                     entry(edit, "PROC-019", [index * 8 + 4, index * 8 + 5], "BKP", "command")])
        rows.append(entry(create, "PROC-003", [5 if index == 0 else 8 + (index - 1) * 3]))
        rows.append(entry("table-controls-" + str(index), family, [1]))
    rows.extend([
        entry("initial-and-pagination", "PROC-003", [6]),
        entry("initial-and-pagination", "PROC-019", [1, 2, 3]),
        entry("stock-quick-action-validation-save-and-backdrop-cancel", "PROC-013", [11], "BKP", "rejected"),
        entry("stock-quick-action-validation-save-and-backdrop-cancel", "DETAIL-001", [4, 5], "BKP", "command"),
        entry("cancel-update-delete-0", "DETAIL-001", [3, 5], "BKP", "command"),
        entry("cancel-update-delete-1", "DETAIL-003", [5], "BKP", "command"),
        entry("cancel-update-delete-2", "DETAIL-005", [5], "BKP", "command"),
        entry("cancel-update-delete-3", "DETAIL-006", [6], "BKP", "command"),
        entry("cancel-update-delete-4", "DETAIL-004", [4], "BKP", "command"),
        entry("cancel-update-delete-5", "DETAIL-007", [5], "BKP", "command"),
        entry("real-internal-bindings-nested-back", "DETAIL-003", [2, 3, 4]),
        entry("real-external-supplier-details", "DETAIL-004", [2, 3]),
        entry("real-external-supplier-details", "DETAIL-007", [2, 4]),
        entry("calendar-month-and-day", "PROC-001", [8]),
        entry("calendar-month-and-day", "PROC-023", [1, 2, 3, 5, 8]),
        entry("calendar-month-and-day", "PROC-024", [2, 3, 4, 8, 9, 12], "BKP", "command"),
        entry("calendar-range-preview-confirm-clear", "PROC-025", [1, 2, 3, 4, 12, 13], "BKP", "command"),
        entry("material-import-preview-and-confirm", "PROC-021", [2, 4], "BK"),
        entry("material-import-preview-and-confirm", "PROC-021", [6], "BKP", "command"),
        entry("material-export-and-bulk-delete", "PROC-019", [6, 7], "BKP", "command"),
    ])
    # File fixtures and create fixtures have different orders. Supplier is file 4, create 5.
    for file_index, resource_index, next_action in [(0, 1, 9), (1, 4, 18), (2, 2, 12), (3, 3, 15), (4, 5, 21)]:
        offset, export_offset = resource_index * 8, resource_index * 5
        suffix = str(file_index)
        rows.extend([
            entry("resource-files-import-" + suffix, "PROC-021", [offset + 1, offset + 2, offset + 4]),
            entry("resource-files-import-" + suffix, "PROC-021", [offset + 6], "BKP", "command"),
            entry("resource-files-cross-page-export-" + suffix, "PROC-003", [next_action]),
            entry("resource-files-filtered-export-" + suffix, "PROC-022", [export_offset + 2, export_offset + 4]),
            entry("resource-files-cross-page-export-" + suffix, "PROC-019", [offset + 1]),
            entry("resource-files-bulk-delete-" + suffix, "PROC-019", [offset + 2, offset + 6, offset + 7], "BKP", "command"),
        ])
    return rows


def process_mappings():
    return [
        entry("process-read-table", "PROC-001", [7]),
        entry("process-read-table", "PROC-003", [1]),
        entry("process-crosspage-downloads", "PROC-003", [3]),
        entry("create-process", "PROC-004", [1, 2, 3], "K"),
        entry("create-process", "PROC-004", [9], "BKP", "command"),
        entry("stages-input-confirm", "PROC-006", [1, 7]),
        entry("stages-input-confirm", "PROC-007", [1, 8], "BKP", "command"),
        entry("stages-input-confirm", "PROC-008", [1], "K"),
        entry("stages-input-confirm", "PROC-008", [7], "BKP", "command"),
        entry("stages-input-confirm", "PROC-009", [1, 2, 3, 4, 6, 7], "BKP", "command"),
        entry("route-import-cancel", "PROC-021", [50, 52, 56], "BKP", "rejected"),
        entry("route-import-confirm", "PROC-021", [54], "BKP", "command"),
        entry("hours-import-cancel", "PROC-021", [58, 60, 64], "BKP", "rejected"),
        entry("hours-import-confirm", "PROC-021", [62], "BKP", "command"),
        entry("hours-import-negative", "PROC-021", [63], "BKP", "rejected"),
        entry("hours-import-negative", "PROC-010", [6], "BKP", "rejected"),
        entry("nonempty-hours-crosspage-downloads", "PROC-022", [31, 32, 36, 37]),
        entry("batch-create-date-dropdown", "BATCH-006", [1, 2, 3, 4, 5, 6, 9], "K"),
        entry("batch-create-date-dropdown", "BATCH-006", [10], "BKP", "command"),
        entry("batch-base-sync-operation", "BATCH-014", [3, 9], "BKP", "command"),
        entry("batch-base-sync-operation", "BATCH-015", [1, 4, 7], "BKP", "command"),
        entry("batch-base-sync-operation", "BATCH-016", [4, 5], "BKP", "command"),
        entry("batch-base-sync-operation", "BATCH-013", [3]),
        entry("batch-replace-protected", "BATCH-010", [5, 9], "BKP", "rejected"),
        entry("batch-crosspage-copy-delete-persist", "BATCH-004", [1, 4, 5, 6]),
        entry("batch-crosspage-copy-delete-persist", "BATCH-008", [1, 2, 4], "BKP", "command"),
        entry("batch-crosspage-copy-delete-persist", "BATCH-009", [3, 4, 8], "BKP", "command"),
        entry("batch-crosspage-copy-delete-persist", "BATCH-012", [1, 2, 3, 4]),
    ]
