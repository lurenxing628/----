from __future__ import annotations

"""质量门禁辅助模块稳定外观。

`tools/quality_gate_support.py` 继续作为对外唯一导入入口，避免脚本、测试与文档中
既有导入路径失效。具体实现已按职责拆分到若干同级模块：
- `quality_gate_shared.py`：常量、路径与结构块通用工具
- `quality_gate_ledger.py`：治理台账读写、排序与校验
- `quality_gate_scan.py`：静默回退 / 复杂度 / 超长文件扫描
- `quality_gate_entries.py`：三类主条目构造与自动字段刷新
- `quality_gate_operations.py`：迁移、基线刷新、门禁对齐与架构适应度接口
"""

from .quality_gate_entries import (
    build_complexity_entry,
    build_oversize_entry,
    build_silent_entry,
)
from .quality_gate_ledger import (
    collect_main_entry_ids,
    default_ledger,
    finalize_ledger_update,
    load_ledger,
    load_sp02_facts_snapshot,
    render_ledger_markdown,
    save_ledger,
    sort_ledger,
    validate_ledger,
)
from .quality_gate_operations import (
    architecture_complexity_allowlist_map,
    architecture_complexity_scan_map,
    architecture_oversize_allowlist_map,
    architecture_oversize_scan_map,
    architecture_repository_bundle_drift_entries,
    architecture_request_service_direct_assembly_entries,
    architecture_silent_allowlist_map,
    architecture_silent_scan_entries,
    delete_risk,
    refresh_auto_fields,
    refresh_migrate_inline_facts,
    refresh_scan_startup_baseline,
    set_entry_fields,
    upsert_risk,
    validate_ledger_against_current_scan,
)
from .quality_gate_scan import (
    classify_silent_fallback,
    scan_complexity_entries,
    scan_oversize_entries,
    scan_repository_bundle_drift_entries,
    scan_request_service_direct_assembly_entries,
    scan_silent_fallback_entries,
    ui_mode_scope_tag,
    validate_startup_samples,
)
from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    CORE_DIRS,
    ENTRY_COMMON_FIELDS,
    ENTRY_MANUAL_FIELDS,
    ENTRY_STATUS_VALUES,
    FALLBACK_KIND_VALUES,
    FILE_SIZE_LIMIT,
    LEDGER_BEGIN,
    LEDGER_END,
    LEDGER_IDENTITY_STRATEGY,
    LEDGER_PATH,
    LEDGER_SCHEMA_VERSION,
    REPO_ROOT,
    REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS,
    REQUEST_SERVICE_SCAN_SCOPE_PATTERNS,
    REQUEST_SERVICE_TARGET_FILES,
    SP02_FACT_BEGIN,
    SP02_FACT_END,
    STAGE_RECORD_PATH,
    STARTUP_SAMPLE_EXPECTATIONS,
    STARTUP_SCOPE_PATTERNS,
    TEST_ARCH_FITNESS_PATH,
    UI_MODE_SCOPE_TAG_VALUES,
    UI_MODE_STARTUP_GUARD_SYMBOLS,
    QualityGateError,
    SilentFallbackSample,
    collect_globbed_files,
    collect_py_files,
    collect_quality_rule_files,
    collect_startup_scope_files,
    ensure_single_marker,
    extract_json_code_block,
    extract_marked_block,
    is_startup_scope_path,
    now_shanghai_iso,
    read_text_file,
    render_marked_json_block,
    repo_abs,
    repo_rel,
    slugify,
    write_text_file,
)
