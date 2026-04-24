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
    QualityGateError,
    collect_globbed_files,
    collect_quality_rule_files,
    collect_startup_scope_files,
    is_startup_scope_path,
    read_text_file,
    slugify,
)


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
        new_complexity_entries.append(
            build_complexity_entry(item["path"], item["symbol"], int(item["current_value"]), existing=existing)
        )

    silent_scan_paths = sorted({str(key).split(":", 1)[0] for key in silent_counter})
    silent_scan_entries = scan_silent_fallback_entries(silent_scan_paths)
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
        entry = build_oversize_entry(str(item["path"]), int(item["current_value"]), existing=existing)
        entry.setdefault("notes", "启动链基线冻结，后续治理批次再处理")
        startup_oversize.append(entry)

    startup_complexity = []
    for item in scan_complexity_entries(startup_files):
        existing = find_existing_by_id(
            complexity_existing,
            "complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),
        )
        entry = build_complexity_entry(str(item["path"]), str(item["symbol"]), int(item["current_value"]), existing=existing)
        entry.setdefault("notes", "启动链基线冻结，后续治理批次再处理")
        startup_complexity.append(entry)

    startup_silent = []
    for item in scan_silent_fallback_entries(startup_files):
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
        return matched

    fallback_candidates = [
        dict(candidate)
        for scan_key, candidate in silent_scan.items()
        if scan_key[:3] == key[:3]
    ]
    if len(fallback_candidates) == 1:
        return fallback_candidates[0]

    raise QualityGateError("静默回退条目已无法通过当前扫描对齐：{}".format(entry.get("id")))


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
        refreshed_complexity.append(
            build_complexity_entry(str(item["path"]), str(item["symbol"]), int(item["current_value"]), existing=entry)
        )

    silent_paths = sorted({str(entry.get("path")) for entry in silent_entries})
    silent_scan = _silent_scan_index(scan_silent_fallback_entries(silent_paths))
    refreshed_silent = []
    for entry in silent_entries:
        matched_entry = _resolve_silent_refresh_entry(entry, silent_scan)
        refreshed_silent.append(
            build_silent_entry(matched_entry, source=str(entry.get("source") or "baseline_scan"), existing=entry)
        )

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
            if current_value != int(entry.get("current_value") or 0):
                raise QualityGateError("oversize 条目 current_value 与当前扫描不一致：{}".format(entry.get("id")))
    if complexity_paths:
        complexity_scan = complexity_scan_map(complexity_paths)
        for entry in cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or []):
            key = "{}:{}".format(entry.get("path"), entry.get("symbol"))
            if key not in complexity_scan:
                raise QualityGateError("复杂度条目无法通过当前扫描定位：{}".format(entry.get("id")))
            if int(complexity_scan[key]["current_value"]) != int(entry.get("current_value") or 0):
                raise QualityGateError("复杂度条目 current_value 与当前扫描不一致：{}".format(entry.get("id")))
    if silent_paths:
        silent_scan = _silent_scan_index(scan_silent_fallback_entries(silent_paths))
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
