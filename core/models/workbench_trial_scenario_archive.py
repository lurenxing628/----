"""Compact saved scenario header and permanent task storage without UI tree bloat."""

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from core.models.workbench_trial import MAX_TRIAL_BYTES, reject
from core.models.workbench_trial_codec import encode_trial_text
from core.shared.refs import is_ref

SCENARIO_ROW_FORMAT = "permanent_rows_v1"
OMITTED_SCENARIO_KEYS = frozenset(("tasks", "capacity", "change_history", "resources"))
SCENARIO_RESOURCE_KEYS = frozenset(("machines", "operators", "authorizations", "suppliers", "op_types"))
_HEADER_PREFIX = '{"format":"' + SCENARIO_ROW_FORMAT + '","snapshot":'
_HEADER_ROWS = ',"task_row_refs":'
_INVALID_SCENARIO = "试调方案任务的永久行或原始顺序不完整。请刷新后重试。"
# 一条已保存任务的载荷只存保存时现场才有的事实：当时的执行状态（execution）和当时的保护判定（locked）。
# 其余字段都由绑定回来的来源草稿行（保存后被 wb_trial_closed_rows 锁定）、草稿存档和方案头里保存时的核对结果
# 在读取时重新投影（trial/projection.scenario_tasks），不另存副本；所在永久行的列也不进载荷。
SCENARIO_TASK_FIELDS = frozenset(("execution", "locked"))
# 已保存任务所在永久行的身份列：row_ref 是主键，task_ref 唯一，source_row_ref 外键指向来源草稿行。
_ROW_COLUMNS = ("row_ref", "task_ref", "source_row_ref")


@dataclass(frozen=True)
class EncodedScenario:
    header: str
    tasks: Tuple[str, ...]


def check_scenario_bytes(size: int) -> int:
    if size > MAX_TRIAL_BYTES:
        reject("query_too_large", f"这次试调的数据超过 {MAX_TRIAL_BYTES // (1024 * 1024)} MB 上限，没有读取。请缩小批次范围。", 413)
    return size


def _compact_metadata(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    metadata = {key: value for key, value in snapshot.items() if key not in OMITTED_SCENARIO_KEYS}
    comparison = metadata.get("comparison")
    if type(comparison) is dict and "preparation_common" in comparison:
        metadata["comparison"] = {key: value for key, value in comparison.items() if key != "preparation_common"}
    unplanned = metadata.get("unplanned_operations")
    if type(unplanned) is list:
        metadata["unplanned_operations"] = [
            {key: value for key, value in item.items() if key != "operation_effort"} if type(item) is dict else item
            for item in unplanned
        ]
    return metadata


def _compact_task(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: row[key] for key in SCENARIO_TASK_FIELDS}


def encode_scenario(snapshot: Dict[str, Any], *, resources_bytes: int = 0) -> EncodedScenario:
    """Encode compact scenario header and permanent task rows once under MAX_TRIAL_BYTES."""
    metadata = _compact_metadata(snapshot)
    metadata_text, metadata_encoded = encode_trial_text(metadata)
    refs_text, refs_encoded = encode_trial_text([row["row_ref"] for row in snapshot["tasks"]])
    header = _HEADER_PREFIX + metadata_text + _HEADER_ROWS + refs_text + "}"
    header_bytes = len(_HEADER_PREFIX) + len(metadata_encoded) + len(_HEADER_ROWS) + len(refs_encoded) + 1
    check_scenario_bytes(header_bytes + resources_bytes)
    tasks, bodies = [], 0
    for row in snapshot["tasks"]:
        text, encoded = encode_trial_text(_compact_task(row))
        tasks.append(text)
        bodies += len(encoded)
        check_scenario_bytes(header_bytes + resources_bytes + bodies)
    return EncodedScenario(header, tuple(tasks))


def encode_scenario_resources(resources: Dict[str, Any]) -> Tuple[str, int]:
    validate_scenario_resources(resources)
    text, encoded = encode_trial_text(resources)
    return text, check_scenario_bytes(len(encoded))


def validate_scenario_resources(resources: Any) -> Dict[str, Any]:
    if type(resources) is not dict or set(resources) != SCENARIO_RESOURCE_KEYS or any(
        type(resources[key]) is not list for key in SCENARIO_RESOURCE_KEYS
    ):
        reject("trial_snapshot_invalid", _INVALID_SCENARIO)
    return resources


def scenario_snapshot(archive: Any, stored: Dict[str, Any], columns: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Reconstruct the compact saved scenario from its header metadata and ordered permanent rows.

    ``stored`` holds each row's decoded payload and ``columns`` that row's identity columns, both keyed by
    ``row_ref``. A payload has exactly the stored task keys; each task is its row's identity columns and payload.
    """
    refs = archive.get("task_row_refs") if type(archive) is dict else None
    metadata = archive.get("snapshot") if type(archive) is dict else None
    if (
        type(archive) is not dict
        or set(archive) != {"format", "snapshot", "task_row_refs"}
        or archive["format"] != SCENARIO_ROW_FORMAT
        or type(metadata) is not dict
        or bool(OMITTED_SCENARIO_KEYS & set(metadata))
        or "operation_effort" not in metadata
        or type(refs) is not list
        or any(type(ref) is not str for ref in refs)
        or len(refs) != len(set(refs))
        or set(refs) != set(stored)
        or any(type(stored[ref]) is not dict or stored[ref].keys() != SCENARIO_TASK_FIELDS for ref in refs)
        or not _frozen_refs_valid(metadata.get("frozen_operation_refs"))
    ):
        reject("trial_snapshot_invalid", _INVALID_SCENARIO)
    return dict(metadata, tasks=[{**stored[ref], **{key: columns[ref][key] for key in _ROW_COLUMNS}} for ref in refs])


def _frozen_refs_valid(frozen: Any) -> bool:
    """A saved scenario records the operations it kept for the hold window as distinct stored refs.

    That they are operations of this scenario is checked once its tasks are bound to their source draft rows
    (``facts/trial_scenario_archive.bind_scenario_rows``), against the rows' real identities.
    """
    return (type(frozen) is list and all(is_ref(ref) for ref in frozen)
            and len(frozen) == len(set(frozen)))
