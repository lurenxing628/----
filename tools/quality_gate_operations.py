from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, cast

from .architecture_scan_cache import aggregate_architecture_scan, scan_files_with_cache
from .quality_gate_entries import (
    build_complexity_entry,
    build_default_note,
    build_oversize_entry,
    build_silent_entry,
    find_existing_by_id,
    remove_entries_by_predicate,
)
from .quality_gate_ledger import (
    collect_main_entry_ids,
    entry_sort_key,
    finalize_ledger_update,
    load_ledger,
    load_sp02_facts_snapshot,
    silent_entry_content_equal,
    silent_entry_has_content,
    silent_entry_key,
    validate_ledger,
)
from .quality_gate_scan import (
    validate_startup_samples as _direct_validate_startup_samples,
)
from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    FILE_SIZE_LIMIT,
    REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS,
    STARTUP_SCOPE_PATTERNS,
    UI_MODE_STARTUP_SCOPE_PATHS,
    WEB_HELPER_SCAN_SCOPE_PATTERNS,
    QualityGateError,
    collect_globbed_files,
    collect_quality_rule_files,
    collect_startup_scope_files,
    is_startup_scope_path,
    slugify,
)

SILENT_REFRESH_SYMBOL_ALIASES = {
    ("web/bootstrap/launcher_processes.py", "_pid_exists"): "_pid_state",
    ("web/bootstrap/launcher_processes.py", "_parse_pid"): "_pid_state",
    ("web/bootstrap/launcher_processes.py", "_posix_pid_state"): "_pid_state",
    ("web/bootstrap/launcher_processes.py", "_windows_pid_state"): "_pid_state",
}
SILENT_REFRESH_GROUP_ALIASES: dict = {}
ALLOWED_SILENT_REALIGN_KIND_TRANSITIONS = {
    ("silent_swallow", "observable_degrade"),
    ("silent_default_fallback", "observable_degrade"),
    ("cleanup_best_effort", "cleanup_best_effort"),
    ("observable_degrade", "observable_degrade"),
}


def refresh_migrate_inline_facts(ledger: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if ledger is None:
        ledger = load_ledger(required=False)
    snapshot = load_sp02_facts_snapshot()
    legacy_inline = cast(Dict[str, Any], snapshot.get("legacy_inline_facts") or {})
    oversize_paths = cast(List[str], legacy_inline.get("oversize_allowlist") or [])
    complexity_keys = cast(List[str], legacy_inline.get("complexity_allowlist") or [])
    silent_counter = cast(Dict[str, int], legacy_inline.get("silent_fallback_counter") or {})

    oversize_existing = cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])
    complexity_existing = cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    silent_existing = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []

    line_counts = _cached_file_line_counts(sorted(set(str(item) for item in oversize_paths)))
    new_oversize_entries = []
    for path in sorted(set([str(item) for item in oversize_paths])):
        current_value = line_counts[path]
        existing = find_existing_by_id(oversize_existing, f"oversize:{slugify(path)}")
        if existing is not None:
            _reject_fixed_oversize_entry_if_current(existing, current_value)
        new_oversize_entries.append(build_oversize_entry(path, current_value, existing=existing))

    complexity_scan = _cached_complexity_scan_map(
        sorted({str(item).split(":", 1)[0] for item in complexity_keys}),
        include_all=True,
    )
    new_complexity_entries = []
    for key in sorted(set([str(item) for item in complexity_keys])):
        if key not in complexity_scan:
            raise QualityGateError(f"复杂度白名单迁移失败，当前已无法定位：{key}")
        item = complexity_scan[key]
        if int(item["current_value"]) <= COMPLEXITY_THRESHOLD:
            continue
        existing = find_existing_by_id(
            complexity_existing,
            "complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),
        )
        if existing is not None:
            _reject_fixed_complexity_entry_if_current(existing, int(item["current_value"]))
        new_complexity_entries.append(
            build_complexity_entry(item["path"], item["symbol"], int(item["current_value"]), existing=existing)
        )

    silent_scan_paths = sorted({str(key).split(":", 1)[0] for key in silent_counter})
    silent_scan_entries = _cached_silent_scan_entries(silent_scan_paths)
    _reject_fixed_silent_entries_still_in_scan(silent_existing, silent_scan_entries)
    new_silent_entries = []
    for key, expected_count in sorted(silent_counter.items()):
        path, symbol = key.split(":", 1)
        matched = [
            entry
            for entry in silent_scan_entries
            if str(entry.get("path")) == path
            and str(entry.get("symbol")) == symbol
            and bool(entry.get("legacy_swallow_hit"))
        ]
        if len(matched) != int(expected_count):
            raise QualityGateError(
                f"静默回退迁移数量不一致：{key} 期望 {expected_count}，实测 {len(matched)}"
            )
        for matched_entry in matched:
            existing = _find_existing_silent_entry(silent_existing, matched_entry)
            new_silent_entries.append(
                build_silent_entry(matched_entry, source="migrated_from_architecture_fitness_counter", existing=existing)
            )

    ledger["oversize_allowlist"] = new_oversize_entries + [
        dict(entry)
        for entry in oversize_existing
        if str(entry.get("path")) not in set(oversize_paths)
    ]
    ledger["complexity_allowlist"] = new_complexity_entries + [
        dict(entry)
        for entry in complexity_existing
        if "{}:{}".format(entry.get("path"), entry.get("symbol")) not in set(complexity_keys)
    ]
    ledger["silent_fallback"] = {
        "scope": list(STARTUP_SCOPE_PATTERNS),
        "entries": new_silent_entries + [
            dict(entry)
            for entry in silent_existing
            if str(entry.get("source") or "") != "migrated_from_architecture_fitness_counter"
        ],
    }
    return finalize_ledger_update(ledger)


def refresh_scan_startup_baseline(ledger: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if ledger is None:
        ledger = load_ledger(required=False)
    startup_files = collect_startup_scope_files()
    oversize_existing = cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])
    complexity_existing = cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    silent_existing = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []

    startup_path_set = set(startup_files)
    startup_silent_scan_entries = _cached_silent_scan_entries(startup_files)
    _validate_startup_samples_from_entries(startup_silent_scan_entries)

    startup_oversize = []
    for item in _cached_oversize_entries(startup_files):
        existing = find_existing_by_id(oversize_existing, "oversize:{}".format(slugify(item["path"])))
        if existing is not None:
            _reject_fixed_oversize_entry_if_current(existing, int(item["current_value"]))
        entry = build_oversize_entry(str(item["path"]), int(item["current_value"]), existing=existing)
        entry.setdefault("notes", "启动链基线冻结，后续治理批次再处理")
        startup_oversize.append(entry)

    startup_complexity = []
    for item in _cached_complexity_entries(startup_files):
        existing = find_existing_by_id(
            complexity_existing,
            "complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),
        )
        if existing is not None:
            _reject_fixed_complexity_entry_if_current(existing, int(item["current_value"]))
        entry = build_complexity_entry(str(item["path"]), str(item["symbol"]), int(item["current_value"]), existing=existing)
        entry.setdefault("notes", "启动链基线冻结，后续治理批次再处理")
        startup_complexity.append(entry)

    _reject_fixed_silent_entries_still_in_scan(silent_existing, startup_silent_scan_entries)
    startup_silent = []
    for item in startup_silent_scan_entries:
        existing = _find_existing_silent_entry(silent_existing, item)
        entry = build_silent_entry(item, source="baseline_scan", existing=existing)
        startup_silent.append(entry)

    ledger["oversize_allowlist"] = remove_entries_by_predicate(oversize_existing, lambda entry: str(entry.get("path")) in startup_path_set) + startup_oversize
    ledger["complexity_allowlist"] = remove_entries_by_predicate(complexity_existing, lambda entry: str(entry.get("path")) in startup_path_set) + startup_complexity
    ledger["silent_fallback"] = {
        "scope": list(STARTUP_SCOPE_PATTERNS),
        "entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup_scope_path(str(entry.get("path")))) + startup_silent,
    }
    main_ids = collect_main_entry_ids(ledger)
    for risk in cast(List[Dict[str, Any]], ledger.get("accepted_risks") or []):
        for entry_id in list(risk.get("entry_ids") or []):
            if str(entry_id) not in main_ids:
                raise QualityGateError("accepted_risks 引用的条目已退出扫描，请先显式复核风险：{} {}".format(risk.get("id"), entry_id))
    return finalize_ledger_update(ledger)


def _find_existing_silent_entry(entries: Sequence[Dict[str, Any]], current: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    matches = [entry for entry in entries if silent_entry_key(entry) == silent_entry_key(current)]
    if len(matches) > 1:
        raise QualityGateError(f"静默回退业务位置存在多条旧登记，请先复核：{silent_entry_key(current)}")
    return dict(matches[0]) if matches else None


def _require_silent_content(entry: Dict[str, Any]) -> None:
    if not silent_entry_has_content(entry):
        raise QualityGateError(
            "静默回退条目缺少 handler_signature / handler_context 原文：{}；请显式复核并重取内容基线，保留旧 id 与 accepted_risks 引用".format(entry.get("id"))
        )


def _silent_scan_index(entries: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, int], Dict[str, Any]]:
    index = {}
    for entry in entries:
        index[silent_entry_key(entry)] = dict(entry)
    return index


def _is_allowed_silent_realign(old_entry: Dict[str, Any], new_entry: Dict[str, Any]) -> Tuple[bool, str]:
    old_kind = str(old_entry.get("fallback_kind") or "")
    new_kind = str(new_entry.get("fallback_kind") or "")
    old_scope = str(old_entry.get("scope_tag") or "")
    new_scope = str(new_entry.get("scope_tag") or "")
    if old_scope != new_scope:
        return False, f"scope_tag changed {old_scope}->{new_scope}"

    if _silent_refresh_group_key(old_entry) != _silent_refresh_group_key(new_entry):
        return False, "path/symbol alias group changed"

    if not silent_entry_has_content(old_entry):
        return False, "old handler_signature / handler_context missing; explicit content baseline review required"
    if not silent_entry_has_content(new_entry):
        return False, "new handler_signature / handler_context missing"
    if int(old_entry.get("except_ordinal") or 0) != int(new_entry.get("except_ordinal") or 0):
        return False, "except ordinal changed"
    if not silent_entry_content_equal(old_entry, new_entry):
        return False, "handler_signature / handler_context changed"

    if old_kind == new_kind:
        return True, f"same path/symbol alias and except ordinal; kind {old_kind}->{new_kind}; scope_tag unchanged; handler content matched"
    # 旧 architecture_fitness 计数器曾把非启动链清理动作记成 silent_swallow。
    # 这里仅允许这批历史非启动链条目回到 cleanup_best_effort，不用于启动链或 accepted risk 换绑放宽。
    if (
        str(old_entry.get("source") or "") == "migrated_from_architecture_fitness_counter"
        and not is_startup_scope_path(str(old_entry.get("path") or ""))
        and old_kind == "silent_swallow"
        and new_kind == "cleanup_best_effort"
    ):
        return True, "legacy architecture silent entry reclassified as cleanup_best_effort; scope_tag unchanged; handler content matched"
    if (old_kind, new_kind) not in ALLOWED_SILENT_REALIGN_KIND_TRANSITIONS:
        return False, f"fallback kind transition {old_kind}->{new_kind} is not allowed"
    return True, f"same path/symbol alias and except ordinal; kind {old_kind}->{new_kind}; scope_tag unchanged; handler content matched"


def _resolve_silent_refresh_entry(
    entry: Dict[str, Any],
    silent_scan: Dict[Tuple[str, str, int], Dict[str, Any]],
) -> Dict[str, Any]:
    key = silent_entry_key(entry)
    matched = silent_scan.get(key)
    if matched is not None:
        allowed, reason = _is_allowed_silent_realign(entry, matched)
        if not allowed:
            raise QualityGateError("静默回退条目自动对齐被拒绝：{} {}".format(entry.get("id"), reason))
        return matched

    same_handler_candidates = [
        dict(candidate)
        for candidate in silent_scan.values()
        if _silent_refresh_group_key(candidate) == _silent_refresh_group_key(entry)
        and int(candidate.get("except_ordinal") or 0) == key[2]
    ]
    if len(same_handler_candidates) == 1:
        allowed, reason = _is_allowed_silent_realign(entry, same_handler_candidates[0])
        if not allowed:
            raise QualityGateError("静默回退条目自动对齐被拒绝：{} {}".format(entry.get("id"), reason))
        return same_handler_candidates[0]

    raise QualityGateError("静默回退条目已无法通过当前扫描对齐：{}".format(entry.get("id")))


def _silent_group_alignment(
    silent_entries: Sequence[Dict[str, Any]],
    scan_entries: Sequence[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    old_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    new_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for entry in silent_entries:
        key = _silent_refresh_group_key(entry)
        old_groups.setdefault(key, []).append(dict(entry))
    for entry in scan_entries:
        key = _silent_refresh_group_key(entry)
        new_groups.setdefault(key, []).append(dict(entry))

    aligned: Dict[str, Dict[str, Any]] = {}
    for key, old_items in old_groups.items():
        new_items = new_groups.get(key) or []
        if len(old_items) != len(new_items):
            continue
        old_ordered = sorted(old_items, key=lambda item: (int(item.get("except_ordinal") or 0), int(item.get("line_start") or 0)))
        new_ordered = sorted(new_items, key=lambda item: (int(item.get("except_ordinal") or 0), int(item.get("line_start") or 0)))
        for old_item, new_item in zip(old_ordered, new_ordered):
            old_id = str(old_item.get("id") or "")
            allowed, _reason = _is_allowed_silent_realign(old_item, new_item)
            if old_id and allowed:
                aligned[old_id] = dict(new_item)
    return aligned


def _silent_refresh_group_key(entry: Dict[str, Any]) -> Tuple[str, str]:
    path = str(entry.get("path") or "")
    symbol = str(entry.get("symbol") or "")
    group_alias = SILENT_REFRESH_GROUP_ALIASES.get((path, symbol))
    if group_alias is not None:
        return group_alias
    return path, SILENT_REFRESH_SYMBOL_ALIASES.get((path, symbol), symbol)


def _silent_scan_has_group(entry: Dict[str, Any], scan_entries: Sequence[Dict[str, Any]]) -> bool:
    key = _silent_refresh_group_key(entry)
    return any(_silent_refresh_group_key(scan_entry) == key for scan_entry in scan_entries)


def _reject_fixed_silent_entries_still_in_scan(
    silent_entries: Sequence[Dict[str, Any]],
    scan_entries: Sequence[Dict[str, Any]],
) -> None:
    for entry in silent_entries:
        if str(entry.get("status") or "open") != "fixed":
            continue
        if _silent_scan_has_group(entry, scan_entries):
            raise QualityGateError(
                "silent_fallback 条目仍被当前扫描命中，不能标记为 fixed：{}".format(entry.get("id"))
            )


def _reject_fixed_oversize_entry_if_current(entry: Dict[str, Any], current_value: int) -> None:
    if str(entry.get("status") or "open") == "fixed" and int(current_value) > FILE_SIZE_LIMIT:
        raise QualityGateError("超长文件条目仍超过限制，不能标记为 fixed：{}".format(entry.get("id")))


def _reject_fixed_complexity_entry_if_current(entry: Dict[str, Any], current_value: int) -> None:
    if str(entry.get("status") or "open") == "fixed" and int(current_value) > COMPLEXITY_THRESHOLD:
        raise QualityGateError("复杂度条目仍超过限制，不能标记为 fixed：{}".format(entry.get("id")))


def _reject_fixed_tracked_entries_still_current(ledger: Dict[str, Any]) -> None:
    fixed_oversize_entries = [
        entry
        for entry in cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])
        if str(entry.get("status") or "open") == "fixed"
    ]
    line_counts = _cached_file_line_counts([str(entry.get("path")) for entry in fixed_oversize_entries])
    for entry in fixed_oversize_entries:
        if str(entry.get("status") or "open") != "fixed":
            continue
        current_value = line_counts[str(entry.get("path"))]
        _reject_fixed_oversize_entry_if_current(entry, current_value)
    complexity_entries = cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    if complexity_entries:
        complexity_scan = _cached_complexity_scan_map(sorted({str(entry.get("path")) for entry in complexity_entries}))
        for entry in complexity_entries:
            if str(entry.get("status") or "open") != "fixed":
                continue
            key = "{}:{}".format(entry.get("path"), entry.get("symbol"))
            item = complexity_scan.get(key)
            if item is not None:
                _reject_fixed_complexity_entry_if_current(entry, int(item.get("current_value") or 0))
    silent_entries = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []
    fixed_silent_paths = sorted(
        {str(entry.get("path")) for entry in silent_entries if str(entry.get("status") or "open") == "fixed"}
    )
    if fixed_silent_paths:
        _reject_fixed_silent_entries_still_in_scan(
            cast(List[Dict[str, Any]], silent_entries),
            _cached_silent_scan_entries(fixed_silent_paths),
        )


def refresh_auto_fields(ledger: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if ledger is None:
        ledger = load_ledger(required=True)
    oversize_entries = cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])
    complexity_entries = cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    silent_entries = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []
    for entry in silent_entries:
        _require_silent_content(entry)
    accepted_entry_ids = {
        str(entry_id)
        for risk in cast(List[Dict[str, Any]], ledger.get("accepted_risks") or [])
        for entry_id in list(risk.get("entry_ids") or [])
    }

    line_counts = _cached_file_line_counts([str(entry.get("path")) for entry in oversize_entries])
    refreshed_oversize = []
    for entry in oversize_entries:
        path = str(entry.get("path"))
        current_value = line_counts[path]
        _reject_fixed_oversize_entry_if_current(entry, current_value)
        if current_value <= FILE_SIZE_LIMIT:
            if str(entry.get("id")) in accepted_entry_ids:
                raise QualityGateError(f"超长文件条目已达成退出条件但仍被 accepted_risks 引用：{entry.get('id')}")
            continue
        refreshed_oversize.append(build_oversize_entry(path, current_value, existing=entry))

    complexity_paths = sorted({str(entry.get("path")) for entry in complexity_entries})
    complexity_scan_all = _cached_complexity_scan_map(complexity_paths, include_all=True)
    complexity_scan = {key: item for key, item in complexity_scan_all.items()
                       if int(item.get("current_value") or 0) > COMPLEXITY_THRESHOLD}
    refreshed_complexity = []
    for entry in complexity_entries:
        key = "{}:{}".format(entry.get("path"), entry.get("symbol"))
        if key not in complexity_scan:
            resolved_item = complexity_scan_all.get(key)
            if resolved_item is not None and int(resolved_item.get("current_value") or 0) <= COMPLEXITY_THRESHOLD:
                if str(entry.get("id")) in accepted_entry_ids:
                    raise QualityGateError(f"复杂度条目已达成退出条件但仍被 accepted_risks 引用：{entry.get('id')}")
                continue
            raise QualityGateError(f"复杂度条目已无法通过当前扫描对齐：{key}")
        item = complexity_scan[key]
        _reject_fixed_complexity_entry_if_current(entry, int(item["current_value"]))
        refreshed_complexity.append(
            build_complexity_entry(str(item["path"]), str(item["symbol"]), int(item["current_value"]), existing=entry)
        )

    silent_paths = sorted({str(entry.get("path")) for entry in silent_entries} | set(UI_MODE_STARTUP_SCOPE_PATHS))
    silent_scan_entries = _cached_silent_scan_entries(silent_paths)
    silent_scan = _silent_scan_index(silent_scan_entries)
    silent_group_alignment = _silent_group_alignment(silent_entries, silent_scan_entries)
    _reject_fixed_silent_entries_still_in_scan(silent_entries, silent_scan_entries)
    refreshed_silent = []
    removed_silent_ids: Set[str] = set()
    for entry in silent_entries:
        if str(entry.get("status") or "open") == "fixed" and not is_startup_scope_path(str(entry.get("path") or "")):
            removed_silent_ids.add(str(entry.get("id") or ""))
            continue
        matched_entry = silent_group_alignment.get(str(entry.get("id") or ""))
        if matched_entry is None:
            try:
                matched_entry = _resolve_silent_refresh_entry(entry, silent_scan)
            except QualityGateError:
                if _silent_scan_has_group(entry, silent_scan_entries):
                    raise
                removed_silent_ids.add(str(entry.get("id") or ""))
                continue
        refreshed_entry = build_silent_entry(matched_entry, source=str(entry.get("source") or "baseline_scan"), existing=entry)
        refreshed_silent.append(refreshed_entry)

    removed_accepted_ids = removed_silent_ids & accepted_entry_ids
    if removed_accepted_ids:
        raise QualityGateError(f"静默回退条目已达成退出条件但仍被 accepted_risks 引用，请先显式复核风险：{sorted(removed_accepted_ids)}")

    ledger["oversize_allowlist"] = refreshed_oversize
    ledger["complexity_allowlist"] = refreshed_complexity
    ledger["silent_fallback"] = {"scope": list(STARTUP_SCOPE_PATTERNS), "entries": refreshed_silent}
    return finalize_ledger_update(ledger)


def set_entry_fields(ledger: Dict[str, Any], entry_id: str, updates: Dict[str, Optional[str]]) -> Dict[str, Any]:
    applied = False
    for section_name in ["oversize_allowlist", "complexity_allowlist"]:
        for entry in cast(List[Dict[str, Any]], ledger.get(section_name) or []):
            if str(entry.get("id")) != entry_id:
                continue
            for field_name, value in updates.items():
                if value is None:
                    continue
                entry[field_name] = value
            applied = True
    silent_entries = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []
    for entry in silent_entries:
        if str(entry.get("id")) != entry_id:
            continue
        for field_name, value in updates.items():
            if value is None:
                continue
            entry[field_name] = value
        applied = True
    if not applied:
        raise QualityGateError(f"未找到主条目：{entry_id}")
    if updates.get("status") == "fixed":
        _reject_fixed_tracked_entries_still_current(ledger)
    return finalize_ledger_update(ledger)


def upsert_risk(
    ledger: Dict[str, Any],
    risk_id: str,
    entry_ids: Sequence[str],
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
    risk = {
        "id": risk_id,
        "entry_ids": list(entry_ids),
        "owner": owner,
        "reason": reason,
        "review_after": review_after,
        "exit_condition": exit_condition,
    }
    if notes is not None:
        risk["notes"] = notes
    accepted_risks = []
    replaced = False
    for current in cast(List[Dict[str, Any]], ledger.get("accepted_risks") or []):
        if str(current.get("id")) == risk_id:
            accepted_risks.append(risk)
            replaced = True
        else:
            accepted_risks.append(dict(current))
    if not replaced:
        accepted_risks.append(risk)
    ledger["accepted_risks"] = accepted_risks
    return finalize_ledger_update(ledger)


def delete_risk(ledger: Dict[str, Any], risk_id: str) -> Dict[str, Any]:
    accepted_risks = cast(List[Dict[str, Any]], ledger.get("accepted_risks") or [])
    new_risks = [dict(risk) for risk in accepted_risks if str(risk.get("id")) != risk_id]
    if len(new_risks) == len(accepted_risks):
        raise QualityGateError(f"未找到 accepted_risks 条目：{risk_id}")
    ledger["accepted_risks"] = new_risks
    return finalize_ledger_update(ledger)


def validate_ledger_against_current_scan(ledger: Dict[str, Any]) -> Dict[str, Any]:
    validate_ledger(ledger)
    for entry in cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []:
        _require_silent_content(entry)
    sample_summary = architecture_validate_startup_samples()

    oversize_paths = [str(entry.get("path")) for entry in cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])]
    complexity_paths = [str(entry.get("path")) for entry in cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])]
    silent_paths = [str(entry.get("path")) for entry in cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []]

    if oversize_paths:
        line_counts = _cached_file_line_counts(oversize_paths)
        for entry in cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or []):
            current_value = line_counts[str(entry.get("path"))]
            _reject_fixed_oversize_entry_if_current(entry, current_value)
            if current_value != int(entry.get("current_value") or 0):
                raise QualityGateError("oversize 条目 current_value 与当前扫描不一致：{}".format(entry.get("id")))
    if complexity_paths:
        complexity_scan = _cached_complexity_scan_map(complexity_paths)
        for entry in cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or []):
            key = "{}:{}".format(entry.get("path"), entry.get("symbol"))
            if key not in complexity_scan:
                raise QualityGateError("复杂度条目无法通过当前扫描定位：{}".format(entry.get("id")))
            _reject_fixed_complexity_entry_if_current(entry, int(complexity_scan[key]["current_value"]))
            if int(complexity_scan[key]["current_value"]) != int(entry.get("current_value") or 0):
                raise QualityGateError("复杂度条目 current_value 与当前扫描不一致：{}".format(entry.get("id")))
    if silent_paths:
        silent_scan_entries = _cached_silent_scan_entries(silent_paths)
        _reject_fixed_silent_entries_still_in_scan(
            cast(List[Dict[str, Any]], cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []),
            silent_scan_entries,
        )
        silent_scan = _silent_scan_index(silent_scan_entries)
        for entry in cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []:
            key = silent_entry_key(entry)
            if key not in silent_scan:
                raise QualityGateError("静默回退条目无法通过当前扫描定位：{}".format(entry.get("id")))
            current_entry = silent_scan[key]
            if not silent_entry_content_equal(entry, current_entry):
                raise QualityGateError("静默回退条目 handler_signature / handler_context 与当前扫描不一致：{}".format(entry.get("id")))
            for field_name in ("line_start", "line_end"):
                if int(current_entry.get(field_name) or 0) != int(entry.get(field_name) or 0):
                    raise QualityGateError(
                        "静默回退条目 {} 与当前扫描不一致：{}".format(field_name, entry.get("id"))
                    )
    return {"samples": sample_summary}


def architecture_oversize_allowlist_map(ledger: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(entry.get("path")): dict(entry) for entry in cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])}


def architecture_complexity_allowlist_map(ledger: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        "{}:{}".format(entry.get("path"), entry.get("symbol")): dict(entry)
        for entry in cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    }


def architecture_silent_allowlist_map(ledger: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(entry.get("id")): dict(entry)
        for entry in cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []
    }


def _cached_architecture_aggregate(
    paths: Sequence[str],
    fact_kinds: Sequence[str],
    include_all_complexity: bool = False,
) -> Dict[str, Any]:
    scan_paths = _unique_scan_paths(paths)
    if not scan_paths:
        return aggregate_architecture_scan([], include_all_complexity=include_all_complexity)
    return aggregate_architecture_scan(
        scan_files_with_cache(scan_paths, fact_kinds=fact_kinds),
        include_all_complexity=include_all_complexity,
    )


def _cached_file_line_counts(paths: Sequence[str]) -> Dict[str, int]:
    scan_paths = _unique_scan_paths(paths)
    if not scan_paths:
        return {}
    return {
        str(fact.get("path")): int(fact.get("line_count") or 0)
        for fact in scan_files_with_cache(scan_paths, fact_kinds=())
    }


def _cached_oversize_entries(paths: Sequence[str]) -> List[Dict[str, Any]]:
    scan_paths = _unique_scan_paths(paths)
    if not scan_paths:
        return []
    aggregate = _cached_architecture_aggregate(scan_paths, ())
    return cast(List[Dict[str, Any]], aggregate.get("oversize_entries") or [])


def _cached_complexity_scan_map(paths: Sequence[str], include_all: bool = False) -> Dict[str, Dict[str, Any]]:
    scan_paths = _unique_scan_paths(paths)
    if not scan_paths:
        return {}
    aggregate = _cached_architecture_aggregate(
        scan_paths,
        ("complexity",),
        include_all_complexity=include_all,
    )
    return {str(key): dict(entry) for key, entry in dict(aggregate.get("complexity_map") or {}).items()}


def _cached_complexity_entries(paths: Sequence[str]) -> List[Dict[str, Any]]:
    scan_paths = _unique_scan_paths(paths)
    if not scan_paths:
        return []
    aggregate = _cached_architecture_aggregate(scan_paths, ("complexity",))
    return cast(List[Dict[str, Any]], aggregate.get("complexity_entries") or [])


def _cached_silent_scan_entries(paths: Sequence[str]) -> List[Dict[str, Any]]:
    scan_paths = _unique_scan_paths(paths)
    if not scan_paths:
        return []
    aggregate = _cached_architecture_aggregate(scan_paths, ("silent",))
    return cast(List[Dict[str, Any]], aggregate.get("silent_fallback_entries") or [])


def _validate_startup_samples_from_entries(entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return _direct_validate_startup_samples(entries)


def _unique_scan_paths(paths: Sequence[str]) -> List[str]:
    return sorted(set(str(path) for path in paths))


def architecture_silent_scan_entries() -> List[Dict[str, Any]]:
    """返回当前架构门禁真正比较的静默回退条目。

    边界说明：启动链范围保留四类分类的全量扫描结果；非启动链范围当前只续管
    旧 `tests/gate_meta/test_architecture_fitness.py` 计数器迁移而来的遗留静默吞异常命中，
    不据此把 `silent_default_fallback` / `observable_degrade` 扩展为全仓新增门禁。
    """
    entries = []
    aggregate = _cached_architecture_aggregate(collect_quality_rule_files(), ("silent",))
    for entry in list(aggregate.get("silent_fallback_entries") or []):
        if is_startup_scope_path(str(entry.get("path"))):
            entries.append(entry)
            continue
        if bool(entry.get("legacy_swallow_hit")):
            normalized = dict(entry)
            normalized["fallback_kind"] = "silent_swallow"
            normalized.pop("scope_tag", None)
            entries.append(normalized)
    return sorted(entries, key=entry_sort_key)


def architecture_validate_startup_samples() -> Dict[str, Any]:
    return _validate_startup_samples_from_entries(_cached_silent_scan_entries(collect_startup_scope_files()))


def architecture_oversize_scan_map() -> Dict[str, Dict[str, Any]]:
    aggregate = _cached_architecture_aggregate(collect_quality_rule_files(), ())
    return {str(path): dict(entry) for path, entry in dict(aggregate.get("oversize_map") or {}).items()}


def architecture_complexity_scan_map() -> Dict[str, Dict[str, Any]]:
    aggregate = _cached_architecture_aggregate(collect_quality_rule_files(), ("complexity",))
    return {str(key): dict(entry) for key, entry in dict(aggregate.get("complexity_map") or {}).items()}


def architecture_web_helper_direct_assembly_entries() -> List[Dict[str, Any]]:
    """web/*.py 顶层辅助模块里的直接装配（Service/Repository(g.db|conn)）。"""
    aggregate = _cached_architecture_aggregate(collect_globbed_files(WEB_HELPER_SCAN_SCOPE_PATTERNS), ("assembly",))
    return cast(List[Dict[str, Any]], aggregate.get("direct_assembly_entries") or [])


def architecture_repository_bundle_drift_entries() -> List[Dict[str, Any]]:
    aggregate = _cached_architecture_aggregate(collect_globbed_files(REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS), ("repository",))
    return cast(List[Dict[str, Any]], aggregate.get("repository_bundle_drift_entries") or [])
