"""Saved logical documents share one byte measure across physical task storage."""

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from core.models.workbench_trial import MAX_TRIAL_BYTES, reject
from core.models.workbench_trial_codec import encode_trial_text

SCENARIO_ROW_FORMAT = "permanent_rows_v1"
_HEADER_PREFIX = '{"format":"' + SCENARIO_ROW_FORMAT + '","snapshot":'
_HEADER_ROWS = ',"task_row_refs":'


@dataclass(frozen=True)
class EncodedScenario:
    header: str
    tasks: Tuple[str, ...]
    logical_bytes: int


def _bounded(size):
    if size > MAX_TRIAL_BYTES:
        reject("query_too_large", "这次试调的数据超过 64 MB 上限，没有读取。请缩小批次范围。", 413)
    return size


def logical_snapshot_bytes(metadata_bytes, task_bytes, task_count, *, has_metadata):
    """Metadata braces plus one logical tasks field, bodies and JSON separators."""
    return _bounded(metadata_bytes + int(has_metadata) + len('"tasks":[]')
                    + task_bytes + max(0, task_count - 1))


def encode_scenario(snapshot):
    """Encode each persisted fragment once; the physical wrapper has its own cap."""
    metadata = {key: value for key, value in snapshot.items() if key != "tasks"}
    metadata_text, metadata_encoded = encode_trial_text(metadata)
    metadata_len, has_metadata = len(metadata_encoded), bool(metadata)
    logical_bytes = logical_snapshot_bytes(metadata_len, 0, 0, has_metadata=has_metadata)
    tasks, bodies = [], 0
    for row in snapshot["tasks"]:
        text, encoded = encode_trial_text(row)
        tasks.append(text)
        bodies += len(encoded)
        logical_bytes = logical_snapshot_bytes(metadata_len, bodies, len(tasks), has_metadata=has_metadata)
    refs_text, refs_encoded = encode_trial_text([row["row_ref"] for row in snapshot["tasks"]])
    header = _HEADER_PREFIX + metadata_text + _HEADER_ROWS + refs_text + "}"
    _bounded(len(_HEADER_PREFIX) + len(metadata_encoded) + len(_HEADER_ROWS) + len(refs_encoded) + 1)
    return EncodedScenario(header, tuple(tasks), logical_bytes)


def scenario_metadata_bytes(raw, archive, header_bytes):
    """Metadata bytes of the header written by ``encode_scenario``; any other layout is damaged storage."""
    boundary = raw.rfind(_HEADER_ROWS)
    if (type(archive.get("snapshot")) is not dict or not raw.startswith(_HEADER_PREFIX)
            or boundary < len(_HEADER_PREFIX) or not raw.endswith("}")):
        reject("trial_snapshot_invalid", "试调方案任务的永久行或原始顺序不完整。请刷新后重试。")
    refs_bytes = len(raw[boundary + len(_HEADER_ROWS):-1].encode("utf-8"))
    return header_bytes - len(_HEADER_PREFIX) - len(_HEADER_ROWS) - refs_bytes - 1


def scenario_snapshot(archive, stored) -> Dict[str, Any]:
    """Reconstruct the saved document from its header metadata and ordered permanent rows."""
    refs = archive.get("task_row_refs")
    metadata = archive.get("snapshot")
    if (set(archive) != {"format", "snapshot", "task_row_refs"}
            or archive["format"] != SCENARIO_ROW_FORMAT
            or type(metadata) is not dict or "tasks" in metadata
            or type(refs) is not list or any(type(ref) is not str for ref in refs)
            or len(refs) != len(set(refs)) or set(refs) != set(stored)
            or any(type(stored[ref]) is not dict or stored[ref].get("row_ref") != ref for ref in refs)):
        reject("trial_snapshot_invalid", "试调方案任务的永久行或原始顺序不完整。请刷新后重试。")
    return dict(metadata, tasks=[stored[ref] for ref in refs])
