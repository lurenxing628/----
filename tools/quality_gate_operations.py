from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from .architecture_scan_cache import aggregate_architecture_scan, scan_files_with_cache
from .quality_gate_entries import (
    build_complexity_entry,
    build_oversize_entry,
    build_silent_entry,
    remove_entries_by_predicate,
)
from .quality_gate_ledger import (
    collect_main_entry_ids,
    complexity_entry_key,
    finalize_ledger_update,
    oversize_entry_key,
    silent_entry_content_equal,
    silent_entry_has_content,
    silent_entry_key,
)
from .quality_gate_scan_primitives import validate_startup_samples
from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    FILE_SIZE_LIMIT,
    STARTUP_SCOPE_PATTERNS,
    QualityGateError,
    collect_startup_scope_files,
    is_startup_scope_path,
)


def refresh_scan_startup_baseline(repo_root: str, ledger: Dict[str, Any]) -> Dict[str, Any]:
    startup_files = collect_startup_scope_files(repo_root)
    oversize_existing = ledger["oversize_allowlist"]
    complexity_existing = ledger["complexity_allowlist"]
    silent_existing = ledger["silent_fallback"]["entries"]

    startup_path_set = set(startup_files)
    # 启动链三类事实共用一次扫描快照。
    startup_scan = _cached_architecture_aggregate(repo_root, startup_files, ("silent", "complexity"))
    startup_silent_scan_entries = startup_scan["silent_fallback_entries"]
    validate_startup_samples(startup_silent_scan_entries)

    startup_oversize = []
    for item in startup_scan["oversize_entries"]:
        existing = _find_existing_entry(oversize_existing, oversize_entry_key, item["path"], "超长文件")
        if existing is not None:
            _reject_fixed_entry(existing, "超长文件")
        entry = build_oversize_entry(item["path"], item["current_value"], existing=existing)
        startup_oversize.append(entry)

    startup_complexity = []
    for key, item in startup_scan["complexity_map"].items():
        existing = _find_existing_entry(complexity_existing, complexity_entry_key, key, "复杂度")
        if existing is not None:
            _reject_fixed_entry(existing, "复杂度")
        entry = build_complexity_entry(item["path"], item["symbol"], item["current_value"], existing=existing)
        startup_complexity.append(entry)

    _reject_fixed_silent_entries_still_in_scan(silent_existing, startup_silent_scan_entries)
    startup_silent = []
    for item in startup_silent_scan_entries:
        existing = _find_existing_entry(silent_existing, silent_entry_key, silent_entry_key(item), "静默回退")
        if existing is None and item["fallback_kind"] == "broad_io_boundary":
            raise QualityGateError(
                f"新处理器用宽泛 except 包住外部 I/O，不登记台账，请收窄为实际会抛出的异常类型：{item['id']}"
            )
        entry = build_silent_entry(item, source="baseline_scan", existing=existing)
        startup_silent.append(entry)

    next_ledger = {
        **ledger,
        "oversize_allowlist": remove_entries_by_predicate(
            oversize_existing, lambda entry: entry["path"] in startup_path_set
        )
        + startup_oversize,
        "complexity_allowlist": remove_entries_by_predicate(
            complexity_existing, lambda entry: entry["path"] in startup_path_set
        )
        + startup_complexity,
        "silent_fallback": {
            "scope": list(STARTUP_SCOPE_PATTERNS),
            "entries": remove_entries_by_predicate(
                silent_existing, lambda entry: is_startup_scope_path(entry["path"])
            )
            + startup_silent,
        },
    }
    main_ids = collect_main_entry_ids(next_ledger)
    for risk in next_ledger["accepted_risks"]:
        for entry_id in risk["entry_ids"]:
            if entry_id not in main_ids:
                raise QualityGateError(
                    f"accepted_risks 引用的条目已退出扫描，请先显式复核风险：{risk['id']} {entry_id}"
                )
    return finalize_ledger_update(next_ledger, current=ledger)


def _find_existing_entry(
    entries: Sequence[Dict[str, Any]],
    entry_key: Callable[[Dict[str, Any]], Any],
    key: Any,
    label: str,
) -> Optional[Dict[str, Any]]:
    """按业务身份键查找旧登记（保留永久 ID 与人工字段）；同一身份多条旧登记时 fail-loud。"""
    matches = [entry for entry in entries if entry_key(entry) == key]
    if len(matches) > 1:
        raise QualityGateError(f"{label}业务位置存在多条旧登记，请先复核：{key}")
    return matches[0] if matches else None


def _silent_scan_index(entries: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, int], Dict[str, Any]]:
    return {silent_entry_key(entry): entry for entry in entries}


def _silent_realign_rejection(
    old_entry: Dict[str, Any], new_entry: Dict[str, Any], *, allow_ordinal_shift: bool = False,
) -> Optional[str]:
    """自动对齐的拒绝原因；处理器内容与分类都没变、可以对齐时返回 None。

    调用方只拿同一 path + symbol 组（`_silent_refresh_group_key`）里的新旧条目来比。
    分类变化（含分类器口径调整）不自动对齐，一律经 `refresh --mode scan-startup-baseline` 显式重建。
    """
    if not silent_entry_has_content(old_entry):
        return "old handler_signature / handler_context missing; explicit content baseline review required"
    if not allow_ordinal_shift and old_entry["except_ordinal"] != new_entry["except_ordinal"]:
        return "except ordinal changed"
    if not silent_entry_content_equal(old_entry, new_entry):
        return "handler_signature / handler_context changed"
    if old_entry["fallback_kind"] != new_entry["fallback_kind"]:
        return (
            f"fallback_kind changed {old_entry['fallback_kind']}->{new_entry['fallback_kind']}; "
            "rebuild with refresh --mode scan-startup-baseline"
        )
    return None


def _resolve_silent_refresh_entry(
    entry: Dict[str, Any],
    silent_scan: Dict[Tuple[str, str, int], Dict[str, Any]],
) -> Dict[str, Any]:
    key = silent_entry_key(entry)
    matched = silent_scan.get(key)
    if matched is not None:
        rejection = _silent_realign_rejection(entry, matched)
        if rejection is not None:
            raise QualityGateError(f"静默回退条目自动对齐被拒绝：{entry['id']} {rejection}")
        return matched

    same_handler_candidates = [
        candidate
        for candidate in silent_scan.values()
        if _silent_refresh_group_key(candidate) == _silent_refresh_group_key(entry)
        and candidate["except_ordinal"] == key[2]
    ]
    if len(same_handler_candidates) == 1:
        rejection = _silent_realign_rejection(entry, same_handler_candidates[0])
        if rejection is not None:
            raise QualityGateError(f"静默回退条目自动对齐被拒绝：{entry['id']} {rejection}")
        return same_handler_candidates[0]

    raise QualityGateError(f"静默回退条目已无法通过当前扫描对齐：{entry['id']}")


def _silent_deletion_alignment(
    old_ordered: Sequence[Dict[str, Any]],
    new_ordered: Sequence[Dict[str, Any]],
) -> Optional[Tuple[Dict[str, Dict[str, Any]], Set[str]]]:
    """Deletion-only refresh: survivors keep content and order, so later ordinals may shift down.

    Identical handler content inside the group would make the survivor identity ambiguous;
    such groups are left to explicit review.
    """
    for index, item in enumerate(old_ordered):
        if any(silent_entry_content_equal(item, other) for other in old_ordered[index + 1:]):
            return None
    aligned: Dict[str, Dict[str, Any]] = {}
    retired: Set[str] = set()
    position = 0
    for old_item in old_ordered:
        old_id = old_item["id"]
        if position < len(new_ordered) and _silent_realign_rejection(
            old_item, new_ordered[position], allow_ordinal_shift=True,
        ) is None:
            aligned[old_id] = new_ordered[position]
            position += 1
        else:
            retired.add(old_id)
    if position != len(new_ordered):
        return None
    return aligned, retired


def _silent_group_alignment(
    silent_entries: Sequence[Dict[str, Any]],
    scan_entries: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Set[str]]:
    old_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    new_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for entry in silent_entries:
        key = _silent_refresh_group_key(entry)
        old_groups.setdefault(key, []).append(entry)
    for entry in scan_entries:
        key = _silent_refresh_group_key(entry)
        new_groups.setdefault(key, []).append(entry)

    aligned: Dict[str, Dict[str, Any]] = {}
    retired: Set[str] = set()
    for key, old_items in old_groups.items():
        new_items = new_groups.get(key) or []
        old_ordered = sorted(old_items, key=lambda item: (item["except_ordinal"], item.get("line_start", 0)))
        new_ordered = sorted(new_items, key=lambda item: (item["except_ordinal"], item["line_start"]))
        if 0 < len(new_items) < len(old_items):
            deletion = _silent_deletion_alignment(old_ordered, new_ordered)
            if deletion is not None:
                aligned.update(deletion[0])
                retired.update(deletion[1])
            continue
        if len(old_items) != len(new_items):
            continue
        for old_item, new_item in zip(old_ordered, new_ordered):
            if _silent_realign_rejection(old_item, new_item) is None:
                aligned[old_item["id"]] = new_item
    return aligned, retired


def _silent_refresh_group_key(entry: Dict[str, Any]) -> Tuple[str, str]:
    return entry["path"], entry["symbol"]


def _silent_scan_has_group(entry: Dict[str, Any], scan_entries: Sequence[Dict[str, Any]]) -> bool:
    key = _silent_refresh_group_key(entry)
    return any(_silent_refresh_group_key(scan_entry) == key for scan_entry in scan_entries)


def _reject_fixed_silent_entries_still_in_scan(
    silent_entries: Sequence[Dict[str, Any]],
    scan_entries: Sequence[Dict[str, Any]],
) -> None:
    for entry in silent_entries:
        if entry["status"] != "fixed":
            continue
        if _silent_scan_has_group(entry, scan_entries):
            raise QualityGateError(
                f"silent_fallback 条目仍被当前扫描命中，不能标记为 fixed：{entry['id']}"
            )


def _reject_fixed_entry(entry: Dict[str, Any], label: str) -> None:
    """前置条件：调用方已确认该条目当前仍超限。"""
    if entry["status"] == "fixed":
        raise QualityGateError(f"{label}条目仍超过限制，不能标记为 fixed：{entry['id']}")


def _reject_fixed_tracked_entries_still_current(repo_root: str, ledger: Dict[str, Any]) -> None:
    fixed_oversize_entries = [
        entry for entry in ledger["oversize_allowlist"] if entry["status"] == "fixed"
    ]
    line_counts = _cached_file_line_counts(repo_root, [entry["path"] for entry in fixed_oversize_entries])
    for entry in fixed_oversize_entries:
        if line_counts[entry["path"]] > FILE_SIZE_LIMIT:
            _reject_fixed_entry(entry, "超长文件")
    complexity_entries = ledger["complexity_allowlist"]
    if complexity_entries:
        complexity_scan = _cached_complexity_scan_map(repo_root, sorted({entry["path"] for entry in complexity_entries}))
        for entry in complexity_entries:
            if complexity_entry_key(entry) in complexity_scan:
                _reject_fixed_entry(entry, "复杂度")
    silent_entries = ledger["silent_fallback"]["entries"]
    fixed_silent_paths = sorted(
        {entry["path"] for entry in silent_entries if entry["status"] == "fixed"}
    )
    if fixed_silent_paths:
        _reject_fixed_silent_entries_still_in_scan(
            silent_entries,
            architecture_silent_scan_entries(repo_root, fixed_silent_paths),
        )


def refresh_auto_fields(repo_root: str, ledger: Dict[str, Any]) -> Dict[str, Any]:
    oversize_entries = ledger["oversize_allowlist"]
    complexity_entries = ledger["complexity_allowlist"]
    silent_entries = ledger["silent_fallback"]["entries"]
    accepted_entry_ids = {
        entry_id
        for risk in ledger["accepted_risks"]
        for entry_id in risk["entry_ids"]
    }

    line_counts = _cached_file_line_counts(repo_root, [entry["path"] for entry in oversize_entries])
    refreshed_oversize = []
    for entry in oversize_entries:
        path = entry["path"]
        current_value = line_counts[path]
        if current_value <= FILE_SIZE_LIMIT:
            if entry["id"] in accepted_entry_ids:
                raise QualityGateError(f"超长文件条目已达成退出条件但仍被 accepted_risks 引用：{entry['id']}")
            continue
        _reject_fixed_entry(entry, "超长文件")
        refreshed_oversize.append(build_oversize_entry(path, current_value, existing=entry))

    complexity_paths = sorted({entry["path"] for entry in complexity_entries})
    complexity_scan = _cached_complexity_scan_map(repo_root, complexity_paths, include_all=True)
    refreshed_complexity = []
    for entry in complexity_entries:
        key = complexity_entry_key(entry)
        if key not in complexity_scan:
            raise QualityGateError(f"复杂度条目已无法通过当前扫描对齐：{key}")
        item = complexity_scan[key]
        if item["current_value"] <= COMPLEXITY_THRESHOLD:
            if entry["id"] in accepted_entry_ids:
                raise QualityGateError(f"复杂度条目已达成退出条件但仍被 accepted_risks 引用：{entry['id']}")
            continue
        _reject_fixed_entry(entry, "复杂度")
        refreshed_complexity.append(
            build_complexity_entry(item["path"], item["symbol"], item["current_value"], existing=entry)
        )

    silent_paths = sorted({entry["path"] for entry in silent_entries})
    silent_scan_entries = architecture_silent_scan_entries(repo_root, silent_paths)
    silent_scan = _silent_scan_index(silent_scan_entries)
    silent_group_alignment, retired_silent_ids = _silent_group_alignment(silent_entries, silent_scan_entries)
    _reject_fixed_silent_entries_still_in_scan(silent_entries, silent_scan_entries)
    refreshed_silent = []
    removed_silent_ids: Set[str] = set()
    for entry in silent_entries:
        entry_id = entry["id"]
        if entry["status"] == "fixed" and not is_startup_scope_path(entry["path"]):
            removed_silent_ids.add(entry_id)
            continue
        if entry_id in retired_silent_ids:
            removed_silent_ids.add(entry_id)
            continue
        matched_entry = silent_group_alignment.get(entry_id)
        if matched_entry is None:
            try:
                matched_entry = _resolve_silent_refresh_entry(entry, silent_scan)
            except QualityGateError:
                if _silent_scan_has_group(entry, silent_scan_entries):
                    raise
                removed_silent_ids.add(entry_id)
                continue
        refreshed_entry = build_silent_entry(matched_entry, source=entry["source"], existing=entry)
        refreshed_silent.append(refreshed_entry)

    removed_accepted_ids = removed_silent_ids & accepted_entry_ids
    if removed_accepted_ids:
        raise QualityGateError(
            f"静默回退条目已达成退出条件但仍被 accepted_risks 引用，请先显式复核风险：{sorted(removed_accepted_ids)}"
        )

    next_ledger = {
        **ledger,
        "oversize_allowlist": refreshed_oversize,
        "complexity_allowlist": refreshed_complexity,
        "silent_fallback": {"scope": list(STARTUP_SCOPE_PATTERNS), "entries": refreshed_silent},
    }
    return finalize_ledger_update(next_ledger, current=ledger)


def set_entry_fields(
    repo_root: str, ledger: Dict[str, Any], entry_id: str, updates: Dict[str, Optional[str]]
) -> Dict[str, Any]:
    non_null_updates = {key: value for key, value in updates.items() if value is not None}
    applied = False
    next_sections: Dict[str, List[Dict[str, Any]]] = {}
    for section_name in ("oversize_allowlist", "complexity_allowlist"):
        updated_section = []
        for entry in ledger[section_name]:
            if entry["id"] == entry_id:
                updated_section.append({**entry, **non_null_updates})
                applied = True
            else:
                updated_section.append(entry)
        next_sections[section_name] = updated_section
    updated_silent = []
    for entry in ledger["silent_fallback"]["entries"]:
        if entry["id"] == entry_id:
            updated_silent.append({**entry, **non_null_updates})
            applied = True
        else:
            updated_silent.append(entry)
    if not applied:
        raise QualityGateError(f"未找到主条目：{entry_id}")
    next_ledger = {
        **ledger,
        **next_sections,
        "silent_fallback": {**ledger["silent_fallback"], "entries": updated_silent},
    }
    if updates.get("status") == "fixed":
        _reject_fixed_tracked_entries_still_current(repo_root, next_ledger)
    return finalize_ledger_update(next_ledger, current=ledger)


def upsert_risk(
    ledger: Dict[str, Any],
    risk_id: str,
    entry_ids: List[str],
    owner: str,
    reason: str,
    review_after: str,
    exit_condition: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    main_ids = collect_main_entry_ids(ledger)
    for entry_id in entry_ids:
        if entry_id not in main_ids:
            raise QualityGateError(f"accepted_risks 引用了不存在的主条目：{entry_id}")
    risk: Dict[str, Any] = {
        "id": risk_id,
        "entry_ids": entry_ids,
        "owner": owner,
        "reason": reason,
        "review_after": review_after,
        "exit_condition": exit_condition,
    }
    if notes is not None:
        risk["notes"] = notes
    accepted_risks = []
    replaced = False
    for current in ledger["accepted_risks"]:
        if current["id"] == risk_id:
            accepted_risks.append(risk)
            replaced = True
        else:
            accepted_risks.append(current)
    if not replaced:
        accepted_risks.append(risk)
    next_ledger = {**ledger, "accepted_risks": accepted_risks}
    return finalize_ledger_update(next_ledger, current=ledger)


def delete_risk(ledger: Dict[str, Any], risk_id: str) -> Dict[str, Any]:
    accepted_risks = ledger["accepted_risks"]
    new_risks = [risk for risk in accepted_risks if risk["id"] != risk_id]
    if len(new_risks) == len(accepted_risks):
        raise QualityGateError(f"未找到 accepted_risks 条目：{risk_id}")
    next_ledger = {**ledger, "accepted_risks": new_risks}
    return finalize_ledger_update(next_ledger, current=ledger)


def validate_ledger_against_current_scan(repo_root: str, ledger: Dict[str, Any]) -> Dict[str, Any]:
    """把已准入台账与当前扫描逐条对账。

    ledger 必须来自 load_ledger（已经过 validate_ledger 准入）；唯一生产调用者是
    scripts/sync_debt_ledger.py 的 check 子命令。
    """
    silent_entries = ledger["silent_fallback"]["entries"]
    silent_paths = {entry["path"] for entry in silent_entries}
    # 启动样本校验与台账静默回退核对共用这一次扫描，各自只取自己负责的文件。
    shared_silent_scan = architecture_silent_scan_entries(
        repo_root, collect_startup_scope_files(repo_root) + sorted(silent_paths)
    )
    startup_scan_entries = [entry for entry in shared_silent_scan if is_startup_scope_path(entry["path"])]
    sample_summary = validate_startup_samples(startup_scan_entries)

    oversize_entries = ledger["oversize_allowlist"]
    if oversize_entries:
        line_counts = _cached_file_line_counts(repo_root, [entry["path"] for entry in oversize_entries])
        for entry in oversize_entries:
            current_value = line_counts[entry["path"]]
            if current_value > FILE_SIZE_LIMIT:
                _reject_fixed_entry(entry, "超长文件")
            if current_value != entry["current_value"]:
                raise QualityGateError(f"oversize 条目 current_value 与当前扫描不一致：{entry['id']}")
    complexity_entries = ledger["complexity_allowlist"]
    if complexity_entries:
        complexity_scan = _cached_complexity_scan_map(repo_root, [entry["path"] for entry in complexity_entries])
        for entry in complexity_entries:
            key = complexity_entry_key(entry)
            if key not in complexity_scan:
                raise QualityGateError(f"复杂度条目无法通过当前扫描定位：{entry['id']}")
            current_value = complexity_scan[key]["current_value"]
            _reject_fixed_entry(entry, "复杂度")
            if current_value != entry["current_value"]:
                raise QualityGateError(f"复杂度条目 current_value 与当前扫描不一致：{entry['id']}")
    _reject_fixed_silent_entries_still_in_scan(silent_entries, shared_silent_scan)
    active_silent_entries = [entry for entry in silent_entries if entry["status"] != "fixed"]
    active_by_key = {silent_entry_key(entry): entry for entry in active_silent_entries}
    for scan_entry in startup_scan_entries:
        if silent_entry_key(scan_entry) not in active_by_key:
            raise QualityGateError(f"启动链静默回退未在治理台账登记：{scan_entry['id']}")
    silent_scan_entries = [entry for entry in shared_silent_scan if entry["path"] in silent_paths]
    silent_scan = _silent_scan_index(silent_scan_entries)
    for entry in active_silent_entries:
        key = silent_entry_key(entry)
        if key not in silent_scan:
            raise QualityGateError(f"静默回退条目无法通过当前扫描定位：{entry['id']}")
        current_entry = silent_scan[key]
        if not silent_entry_content_equal(entry, current_entry):
            raise QualityGateError(f"静默回退条目 handler_signature / handler_context 与当前扫描不一致：{entry['id']}")
        for field_name in ("fallback_kind", "line_start", "line_end"):
            if current_entry[field_name] != entry[field_name]:
                raise QualityGateError(
                    f"静默回退条目 {field_name} 与当前扫描不一致：{entry['id']}"
                )
    return {"samples": sample_summary}


def _cached_architecture_aggregate(
    repo_root: str,
    paths: Sequence[str],
    fact_kinds: Sequence[str],
    include_all_complexity: bool = False,
) -> Dict[str, Any]:
    return aggregate_architecture_scan(
        scan_files_with_cache(repo_root, paths, fact_kinds=fact_kinds),
        include_all_complexity=include_all_complexity,
    )


def _cached_file_line_counts(repo_root: str, paths: Sequence[str]) -> Dict[str, int]:
    return {fact["path"]: fact["line_count"] for fact in scan_files_with_cache(repo_root, paths, fact_kinds=())}


def _cached_complexity_scan_map(
    repo_root: str, paths: Sequence[str], include_all: bool = False
) -> Dict[str, Dict[str, Any]]:
    return _cached_architecture_aggregate(repo_root, paths, ("complexity",), include_all_complexity=include_all)[
        "complexity_map"
    ]


def architecture_silent_scan_entries(repo_root: str, paths: Sequence[str]) -> List[Dict[str, Any]]:
    """静默回退门禁的唯一范围视图：台账 check、refresh-auto-fields 与 `quality_gate_scan --strict`
    都拿它与台账比较，各自只决定扫描哪些文件。

    启动链范围保留全部分类的扫描结果；非启动链范围当前只续管旧
    `tests/gate_meta/test_architecture_fitness.py` 计数器迁移而来的遗留静默吞异常命中，一律按
    `silent_swallow` 计，不据此把 `silent_default_fallback` / `observable_degrade` 扩展为全仓新增门禁。
    """
    entries = []
    for entry in _cached_architecture_aggregate(repo_root, paths, ("silent",))["silent_fallback_entries"]:
        if is_startup_scope_path(entry["path"]):
            entries.append(entry)
        elif entry["legacy_swallow_hit"]:
            entries.append({**entry, "fallback_kind": "silent_swallow"})
    return entries
