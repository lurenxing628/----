"""Saved scenario metadata keeps task order; permanent rows own the task bodies."""

from core.models.workbench_trial import reject

SCENARIO_ROW_FORMAT = "permanent_rows_v1"


def scenario_archive(snapshot):
    return {"format": SCENARIO_ROW_FORMAT,
            "snapshot": {key: value for key, value in snapshot.items() if key != "tasks"},
            "task_row_refs": [row["row_ref"] for row in snapshot["tasks"]]}


def scenario_snapshot(archive, stored):
    """Reconstruct new archives and preserve the original full-snapshot format."""
    if "tasks" in archive:
        return archive
    refs = archive.get("task_row_refs")
    metadata = archive.get("snapshot")
    if (set(archive) != {"format", "snapshot", "task_row_refs"}
            or archive["format"] != SCENARIO_ROW_FORMAT
            or type(metadata) is not dict or "tasks" in metadata
            or type(refs) is not list or any(type(ref) is not str for ref in refs)
            or len(refs) != len(set(refs)) or set(refs) != set(stored)):
        reject("trial_snapshot_invalid", "试调方案任务的永久行或原始顺序不完整。请刷新后重试。")
    return dict(metadata, tasks=[stored[ref] for ref in refs])
