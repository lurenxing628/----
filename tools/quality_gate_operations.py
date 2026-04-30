from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, cast

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
    validate_ledger,
)
from .quality_gate_scan import (
    complexity_scan_map,
    scan_complexity_entries,
    scan_oversize_entries,
    scan_repository_bundle_drift_entries,
    scan_request_service_direct_assembly_entries,
    scan_silent_fallback_entries,
    validate_startup_samples,
)
from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    FILE_SIZE_LIMIT,
    REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS,
    REQUEST_SERVICE_SCAN_SCOPE_PATTERNS,
    REQUEST_SERVICE_TARGET_FILES,
    REQUEST_SERVICE_TARGET_SYMBOLS,
    STARTUP_SCOPE_PATTERNS,
    UI_MODE_STARTUP_SCOPE_PATHS,
    QualityGateError,
    collect_globbed_files,
    collect_quality_rule_files,
    collect_startup_scope_files,
    is_startup_scope_path,
    now_shanghai_iso,
    read_text_file,
    slugify,
)

SILENT_REFRESH_SYMBOL_ALIASES = {
    ("web/bootstrap/launcher_processes.py", "_pid_exists"): "_pid_state",
    ("web/bootstrap/launcher_processes.py", "_parse_pid"): "_pid_state",
    ("web/bootstrap/launcher_processes.py", "_posix_pid_state"): "_pid_state",
    ("web/bootstrap/launcher_processes.py", "_windows_pid_state"): "_pid_state",
}
SILENT_REFRESH_GROUP_ALIASES = {
    ("web/ui_mode.py", "_describe_template_name"): ("web/render_bridge.py", "_describe_template_name"),
    ("web/ui_mode.py", "_normalize_relative_manual_src"): ("web/manual_src_security.py", "_normalize_relative_manual_src"),
    ("web/ui_mode.py", "_read_ui_mode_from_db"): ("web/ui_mode_store.py", "_read_ui_mode_from_db"),
    ("web/ui_mode.py", "_resolve_manual_endpoint"): ("web/manual_src_security.py", "_resolve_manual_endpoint"),
    ("web/ui_mode.py", "_resolve_manual_src"): ("web/manual_src_security.py", "_resolve_manual_src"),
    ("web/ui_mode.py", "_resolve_template_source"): ("web/render_bridge.py", "_resolve_template_source"),
    ("web/ui_mode.py", "_resolve_template_url_for"): ("web/render_bridge.py", "_resolve_template_url_for"),
    ("web/ui_mode.py", "_same_origin_absolute_manual_src"): ("web/manual_src_security.py", "_same_origin_absolute_manual_src"),
    ("web/ui_mode.py", "_warn_v2_render_fallback_once"): ("web/render_bridge.py", "_warn_v2_render_fallback_once"),
    ("web/ui_mode.py", "get_ui_mode"): ("web/ui_mode_request.py", "get_ui_mode"),
    ("web/ui_mode.py", "init_ui_mode"): ("web/render_bridge.py", "init_ui_mode"),
    ("web/ui_mode.py", "render_ui_template"): ("web/render_bridge.py", "render_ui_template"),
    ("web/ui_mode.py", "safe_url_for"): ("web/manual_src_security.py", "safe_url_for"),
}
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

    new_oversize_entries = []
    for path in sorted(set([str(item) for item in oversize_paths])):
        current_value = len(read_text_file(path).splitlines())
        existing = find_existing_by_id(oversize_existing, f"oversize:{slugify(path)}")
        if existing is not None:
            _reject_fixed_oversize_entry_if_current(existing, current_value)
        new_oversize_entries.append(build_oversize_entry(path, current_value, existing=existing))

    complexity_scan = complexity_scan_map(sorted({str(item).split(":", 1)[0] for item in complexity_keys}), include_all=True)
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
    silent_scan_entries = scan_silent_fallback_entries(silent_scan_paths)
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
            existing = find_existing_by_id(silent_existing, str(matched_entry.get("id")))
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
    validate_startup_samples()
    startup_files = collect_startup_scope_files()
    oversize_existing = cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])
    complexity_existing = cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    silent_existing = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []

    startup_path_set = set(startup_files)
    startup_oversize = []
    for item in scan_oversize_entries(startup_files):
        existing = find_existing_by_id(oversize_existing, "oversize:{}".format(slugify(item["path"])))
        if existing is not None:
            _reject_fixed_oversize_entry_if_current(existing, int(item["current_value"]))
        entry = build_oversize_entry(str(item["path"]), int(item["current_value"]), existing=existing)
        entry.setdefault("notes", "启动链基线冻结，后续治理批次再处理")
        startup_oversize.append(entry)

    startup_complexity = []
    for item in scan_complexity_entries(startup_files):
        existing = find_existing_by_id(
            complexity_existing,
            "complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),
        )
        if existing is not None:
            _reject_fixed_complexity_entry_if_current(existing, int(item["current_value"]))
        entry = build_complexity_entry(str(item["path"]), str(item["symbol"]), int(item["current_value"]), existing=existing)
        entry.setdefault("notes", "启动链基线冻结，后续治理批次再处理")
        startup_complexity.append(entry)

    startup_silent_scan_entries = scan_silent_fallback_entries(startup_files)
    _reject_fixed_silent_entries_still_in_scan(silent_existing, startup_silent_scan_entries)
    startup_silent = []
    for item in startup_silent_scan_entries:
        existing = find_existing_by_id(silent_existing, str(item.get("id")))
        entry = build_silent_entry(item, source="baseline_scan", existing=existing)
        if entry.get("path") == "web/ui_mode.py" and entry.get("scope_tag") == "render_bridge":
            entry["owner"] = existing.get("owner") if existing else "SP09"
            entry["batch"] = existing.get("batch") if existing else "SP09"
            if not existing:
                entry["notes"] = build_default_note("baseline_scan", fallback_kind=str(item.get("fallback_kind")), scope_tag="render_bridge")
        startup_silent.append(entry)

    ledger["oversize_allowlist"] = remove_entries_by_predicate(oversize_existing, lambda entry: str(entry.get("path")) in startup_path_set) + startup_oversize
    ledger["complexity_allowlist"] = remove_entries_by_predicate(complexity_existing, lambda entry: str(entry.get("path")) in startup_path_set) + startup_complexity
    ledger["silent_fallback"] = {
        "scope": list(STARTUP_SCOPE_PATTERNS),
        "entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup_scope_path(str(entry.get("path")))) + startup_silent,
    }
    replacements = _silent_group_alignment(
        [dict(entry) for entry in silent_existing if is_startup_scope_path(str(entry.get("path")))],
        startup_silent,
    )
    id_replacements = {
        old_id: str(new_entry.get("id") or "")
        for old_id, new_entry in replacements.items()
        if old_id and str(new_entry.get("id") or "")
    }
    main_ids = collect_main_entry_ids(ledger)
    refreshed_risks = []
    for risk in cast(List[Dict[str, Any]], ledger.get("accepted_risks") or []):
        next_entry_ids = []
        for entry_id in list(risk.get("entry_ids") or []):
            next_id = id_replacements.get(str(entry_id), str(entry_id))
            if next_id not in main_ids:
                continue
            if next_id not in next_entry_ids:
                next_entry_ids.append(next_id)
        if not next_entry_ids:
            raise QualityGateError(
                "accepted_risks 将被自动清空，请先显式 delete-risk：{}".format(risk.get("id"))
            )
        risk["entry_ids"] = next_entry_ids
        refreshed_risks.append(risk)
    ledger["accepted_risks"] = refreshed_risks
    return finalize_ledger_update(ledger)


def _silent_scan_index(entries: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str, str, int], Dict[str, Any]]:
    index = {}
    for entry in entries:
        key = (
            str(entry.get("path") or ""),
            str(entry.get("symbol") or ""),
            str(entry.get("handler_fingerprint") or ""),
            int(entry.get("except_ordinal") or 0),
        )
        index[key] = dict(entry)
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

    new_hash = str(new_entry.get("handler_context_hash") or "")
    if not new_hash.startswith("sha1:"):
        return False, "new handler_context_hash missing"

    old_hash = str(old_entry.get("handler_context_hash") or "")
    old_fingerprint = str(old_entry.get("handler_fingerprint") or "")
    new_fingerprint = str(new_entry.get("handler_fingerprint") or "")
    if int(old_entry.get("except_ordinal") or 0) != int(new_entry.get("except_ordinal") or 0) and old_hash:
        return False, "except ordinal changed"
    if not old_hash:
        hash_reason = "handler_context_hash initialized"
        hash_matched = True
    else:
        if not old_hash.startswith("sha1:"):
            return False, "old handler_context_hash invalid"
        if old_hash != new_hash:
            return False, "handler_context_hash changed"
        hash_reason = "handler_context_hash matched"
        hash_matched = True

    if str(old_entry.get("id") or "") and str(old_entry.get("id") or "") == str(new_entry.get("id") or "") and old_kind == new_kind:
        return True, f"same id; kind {old_kind}->{new_kind}; scope_tag unchanged; {hash_reason}"

    if old_kind == new_kind and old_fingerprint == new_fingerprint:
        return True, f"same path/symbol alias and except ordinal; kind {old_kind}->{new_kind}; scope_tag unchanged; {hash_reason}"
    # 旧 architecture_fitness 计数器曾把非启动链清理动作记成 silent_swallow。
    # 这里仅允许这批历史非启动链条目回到 cleanup_best_effort，不用于启动链或 accepted risk 换绑放宽。
    if (
        str(old_entry.get("source") or "") == "migrated_from_architecture_fitness_counter"
        and not is_startup_scope_path(str(old_entry.get("path") or ""))
        and old_kind == "silent_swallow"
        and new_kind == "cleanup_best_effort"
    ):
        return True, f"legacy architecture silent entry reclassified as cleanup_best_effort; scope_tag unchanged; {hash_reason}"
    if (old_kind, new_kind) not in ALLOWED_SILENT_REALIGN_KIND_TRANSITIONS:
        return False, f"fallback kind transition {old_kind}->{new_kind} is not allowed"
    if not hash_matched:
        return False, "handler_context_hash changed"
    return True, f"same path/symbol alias and except ordinal; kind {old_kind}->{new_kind}; scope_tag unchanged; handler_context_hash matched"


def _apply_silent_realign_metadata(old_entry: Dict[str, Any], new_entry: Dict[str, Any], reason: str) -> None:
    new_entry["realigned_from"] = str(old_entry.get("id") or "")
    new_entry["realigned_at"] = now_shanghai_iso().split("T", 1)[0]
    new_entry["realignment_reason"] = reason


def _resolve_silent_refresh_entry(
    entry: Dict[str, Any],
    silent_scan: Dict[Tuple[str, str, str, int], Dict[str, Any]],
) -> Dict[str, Any]:
    key = (
        str(entry.get("path") or ""),
        str(entry.get("symbol") or ""),
        str(entry.get("handler_fingerprint") or ""),
        int(entry.get("except_ordinal") or 0),
    )
    matched = silent_scan.get(key)
    if matched is not None:
        allowed, reason = _is_allowed_silent_realign(entry, matched)
        if not allowed:
            raise QualityGateError("静默回退条目自动对齐被拒绝：{} {}".format(entry.get("id"), reason))
        return matched

    fallback_candidates = [
        dict(candidate)
        for scan_key, candidate in silent_scan.items()
        if scan_key[:3] == key[:3]
    ]
    if len(fallback_candidates) == 1:
        allowed, reason = _is_allowed_silent_realign(entry, fallback_candidates[0])
        if not allowed:
            raise QualityGateError("静默回退条目自动对齐被拒绝：{} {}".format(entry.get("id"), reason))
        return fallback_candidates[0]

    same_handler_candidates = [
        dict(candidate)
        for scan_key, candidate in silent_scan.items()
        if scan_key[0] == key[0] and scan_key[1] == key[1] and scan_key[3] == key[3]
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
    for entry in cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or []):
        if str(entry.get("status") or "open") != "fixed":
            continue
        current_value = len(read_text_file(str(entry.get("path"))).splitlines())
        _reject_fixed_oversize_entry_if_current(entry, current_value)
    complexity_entries = cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    if complexity_entries:
        complexity_scan = complexity_scan_map(sorted({str(entry.get("path")) for entry in complexity_entries}))
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
            scan_silent_fallback_entries(fixed_silent_paths),
        )


def refresh_auto_fields(ledger: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if ledger is None:
        ledger = load_ledger(required=True)
    oversize_entries = cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])
    complexity_entries = cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])
    silent_entries = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []
    accepted_entry_ids = {
        str(entry_id)
        for risk in cast(List[Dict[str, Any]], ledger.get("accepted_risks") or [])
        for entry_id in list(risk.get("entry_ids") or [])
    }

    refreshed_oversize = []
    for entry in oversize_entries:
        path = str(entry.get("path"))
        current_value = len(read_text_file(path).splitlines())
        _reject_fixed_oversize_entry_if_current(entry, current_value)
        if current_value <= FILE_SIZE_LIMIT:
            if str(entry.get("id")) in accepted_entry_ids:
                raise QualityGateError(f"超长文件条目已达成退出条件但仍被 accepted_risks 引用：{entry.get('id')}")
            continue
        refreshed_oversize.append(build_oversize_entry(path, current_value, existing=entry))

    complexity_paths = sorted({str(entry.get("path")) for entry in complexity_entries})
    complexity_scan = complexity_scan_map(complexity_paths)
    complexity_scan_all = complexity_scan_map(complexity_paths, include_all=True)
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
    silent_scan_entries = scan_silent_fallback_entries(silent_paths)
    silent_scan = _silent_scan_index(silent_scan_entries)
    silent_group_alignment = _silent_group_alignment(silent_entries, silent_scan_entries)
    _reject_fixed_silent_entries_still_in_scan(silent_entries, silent_scan_entries)
    refreshed_silent = []
    silent_id_replacements: Dict[str, str] = {}
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
        allowed, realign_reason = _is_allowed_silent_realign(entry, matched_entry)
        if not allowed:
            raise QualityGateError("静默回退条目自动对齐被拒绝：{} {}".format(entry.get("id"), realign_reason))
        old_id = str(entry.get("id") or "")
        new_id = str(refreshed_entry.get("id") or "")
        if old_id and new_id and old_id != new_id:
            if old_id in accepted_entry_ids and not str(entry.get("handler_context_hash") or "").startswith("sha1:"):
                refreshed_entry["id"] = old_id
                new_id = old_id
            else:
                _apply_silent_realign_metadata(entry, refreshed_entry, realign_reason)
                silent_id_replacements[old_id] = new_id
        refreshed_silent.append(refreshed_entry)

    if silent_id_replacements or removed_silent_ids:
        refreshed_risks = []
        for risk in cast(List[Dict[str, Any]], ledger.get("accepted_risks") or []):
            next_entry_ids = []
            for entry_id in list(risk.get("entry_ids") or []):
                if str(entry_id) in removed_silent_ids:
                    continue
                next_id = silent_id_replacements.get(str(entry_id), str(entry_id))
                if next_id not in next_entry_ids:
                    next_entry_ids.append(next_id)
            if not next_entry_ids:
                raise QualityGateError(
                    "accepted_risks 将被自动清空，请先显式 delete-risk：{}".format(risk.get("id"))
                )
            risk["entry_ids"] = next_entry_ids
            refreshed_risks.append(risk)
        ledger["accepted_risks"] = refreshed_risks

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
    sample_summary = validate_startup_samples()

    oversize_paths = [str(entry.get("path")) for entry in cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or [])]
    complexity_paths = [str(entry.get("path")) for entry in cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or [])]
    silent_paths = [str(entry.get("path")) for entry in cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []]

    if oversize_paths:
        for entry in cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or []):
            current_value = len(read_text_file(str(entry.get("path"))).splitlines())
            _reject_fixed_oversize_entry_if_current(entry, current_value)
            if current_value != int(entry.get("current_value") or 0):
                raise QualityGateError("oversize 条目 current_value 与当前扫描不一致：{}".format(entry.get("id")))
    if complexity_paths:
        complexity_scan = complexity_scan_map(complexity_paths)
        for entry in cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or []):
            key = "{}:{}".format(entry.get("path"), entry.get("symbol"))
            if key not in complexity_scan:
                raise QualityGateError("复杂度条目无法通过当前扫描定位：{}".format(entry.get("id")))
            _reject_fixed_complexity_entry_if_current(entry, int(complexity_scan[key]["current_value"]))
            if int(complexity_scan[key]["current_value"]) != int(entry.get("current_value") or 0):
                raise QualityGateError("复杂度条目 current_value 与当前扫描不一致：{}".format(entry.get("id")))
    if silent_paths:
        silent_scan_entries = scan_silent_fallback_entries(silent_paths)
        _reject_fixed_silent_entries_still_in_scan(
            cast(List[Dict[str, Any]], cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []),
            silent_scan_entries,
        )
        silent_scan = _silent_scan_index(silent_scan_entries)
        for entry in cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []:
            key = (
                str(entry.get("path") or ""),
                str(entry.get("symbol") or ""),
                str(entry.get("handler_fingerprint") or ""),
                int(entry.get("except_ordinal") or 0),
            )
            if key not in silent_scan:
                raise QualityGateError("静默回退条目无法通过当前扫描定位：{}".format(entry.get("id")))
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


def architecture_silent_scan_entries() -> List[Dict[str, Any]]:
    """返回当前架构门禁真正比较的静默回退条目。

    边界说明：启动链范围保留四类分类的全量扫描结果；非启动链范围当前只续管
    旧 `tests/test_architecture_fitness.py` 计数器迁移而来的遗留静默吞异常命中，
    不据此把 `silent_default_fallback` / `observable_degrade` 扩展为全仓新增门禁。
    """
    entries = []
    for entry in scan_silent_fallback_entries(collect_quality_rule_files()):
        if is_startup_scope_path(str(entry.get("path"))):
            entries.append(entry)
            continue
        if bool(entry.get("legacy_swallow_hit")):
            normalized = dict(entry)
            normalized["fallback_kind"] = "silent_swallow"
            normalized.pop("scope_tag", None)
            entries.append(normalized)
    return sorted(entries, key=entry_sort_key)


def architecture_oversize_scan_map() -> Dict[str, Dict[str, Any]]:
    return {str(entry.get("path")): entry for entry in scan_oversize_entries(collect_quality_rule_files())}


def architecture_complexity_scan_map() -> Dict[str, Dict[str, Any]]:
    return complexity_scan_map(collect_quality_rule_files())


def architecture_request_service_direct_assembly_entries() -> List[Dict[str, Any]]:
    target_files = set(REQUEST_SERVICE_TARGET_FILES)
    target_symbols = {
        str(path): set(str(symbol) for symbol in symbols)
        for path, symbols in REQUEST_SERVICE_TARGET_SYMBOLS.items()
    }
    entries = scan_request_service_direct_assembly_entries(collect_globbed_files(REQUEST_SERVICE_SCAN_SCOPE_PATTERNS))
    return [
        entry
        for entry in entries
        if (
            str(entry.get("path")) in target_files
            or str(entry.get("symbol")) in target_symbols.get(str(entry.get("path")), set())
        )
        and not (
            str(entry.get("path")) in target_symbols
            and str(entry.get("symbol")) not in target_symbols.get(str(entry.get("path")), set())
        )
    ]


def architecture_repository_bundle_drift_entries() -> List[Dict[str, Any]]:
    return scan_repository_bundle_drift_entries(collect_globbed_files(REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS))
