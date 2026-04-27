from __future__ import annotations

import copy
import os
import textwrap
from typing import Any, Dict, List, Set, Tuple, cast

from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    ENTRY_COMMON_FIELDS,
    ENTRY_STATUS_VALUES,
    FALLBACK_KIND_VALUES,
    FILE_SIZE_LIMIT,
    LEDGER_BEGIN,
    LEDGER_END,
    LEDGER_IDENTITY_STRATEGY,
    LEDGER_PATH,
    LEDGER_SCHEMA_VERSION,
    SP02_FACT_BEGIN,
    SP02_FACT_END,
    STAGE_RECORD_PATH,
    STARTUP_SCOPE_PATTERNS,
    TEST_DEBT_MODE_VALUES,
    UI_MODE_SCOPE_TAG_VALUES,
    QualityGateError,
    extract_json_code_block,
    now_shanghai_iso,
    read_text_file,
    render_marked_json_block,
    write_text_file,
)


def default_ledger() -> Dict[str, Any]:
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "identity_strategy": LEDGER_IDENTITY_STRATEGY,
        "updated_at": now_shanghai_iso(),
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {"scope": list(STARTUP_SCOPE_PATTERNS), "entries": []},
        "test_debt": {"ratchet": {"max_registered_xfail": 0}, "entries": []},
        "accepted_risks": [],
    }


def load_ledger(required: bool = True) -> Dict[str, Any]:
    if not os.path.exists(LEDGER_PATH):
        if required:
            raise QualityGateError("治理台账不存在：开发文档/技术债务治理台账.md")
        return default_ledger()
    text = read_text_file("开发文档/技术债务治理台账.md")
    ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")
    validate_ledger(ledger)
    return sort_ledger(copy.deepcopy(ledger))


def _validate_legacy_ledger_for_test_debt_import(ledger: Dict[str, Any]) -> None:
    if not isinstance(ledger, dict):
        raise QualityGateError("治理台账顶层必须是对象")
    if ledger.get("schema_version") != 1:
        raise QualityGateError("旧治理台账 schema_version 必须是 1")
    if ledger.get("identity_strategy") != LEDGER_IDENTITY_STRATEGY:
        raise QualityGateError("旧治理台账 identity_strategy 与约定不一致")
    _require_string(ledger.get("updated_at"), "updated_at")
    if not isinstance(ledger.get("oversize_allowlist"), list):
        raise QualityGateError("旧治理台账 oversize_allowlist 必须是数组")
    if not isinstance(ledger.get("complexity_allowlist"), list):
        raise QualityGateError("旧治理台账 complexity_allowlist 必须是数组")
    silent_fallback = ledger.get("silent_fallback")
    if not isinstance(silent_fallback, dict):
        raise QualityGateError("旧治理台账 silent_fallback 必须是对象")
    if silent_fallback.get("scope") != list(STARTUP_SCOPE_PATTERNS):
        raise QualityGateError("旧治理台账 silent_fallback.scope 与约定不一致")
    if not isinstance(silent_fallback.get("entries"), list):
        raise QualityGateError("旧治理台账 silent_fallback.entries 必须是数组")
    if not isinstance(ledger.get("accepted_risks"), list):
        raise QualityGateError("旧治理台账 accepted_risks 必须是数组")


def load_ledger_for_test_debt_import() -> Dict[str, Any]:
    if not os.path.exists(LEDGER_PATH):
        raise QualityGateError("治理台账不存在：开发文档/技术债务治理台账.md")
    text = read_text_file("开发文档/技术债务治理台账.md")
    ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")
    schema_version = ledger.get("schema_version")
    if schema_version == LEDGER_SCHEMA_VERSION:
        validate_ledger(ledger)
        if cast(Dict[str, Any], ledger.get("test_debt") or {}).get("entries"):
            raise QualityGateError("治理台账已存在 test_debt.entries，导入命令不得覆盖已有测试债务登记")
        return sort_ledger(copy.deepcopy(ledger))
    if schema_version == 1:
        _validate_legacy_ledger_for_test_debt_import(ledger)
        return copy.deepcopy(ledger)
    raise QualityGateError(f"治理台账 schema_version 不支持测试债务导入：{schema_version}")


def render_ledger_markdown(ledger: Dict[str, Any]) -> str:
    oversize_count = len(ledger.get("oversize_allowlist") or [])
    complexity_count = len(ledger.get("complexity_allowlist") or [])
    fallback_entries = cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []
    test_debt_entries = cast(Dict[str, Any], ledger.get("test_debt") or {}).get("entries") or []
    risk_count = len(ledger.get("accepted_risks") or [])
    payload_block = render_marked_json_block(LEDGER_BEGIN, LEDGER_END, ledger)
    body = textwrap.dedent(
        """
        # 技术债务治理台账

        本文档承担两类职责：
        1. 为统一质量门禁提供唯一机器可读事实源；
        2. 为后续批次记录责任人、批次归属、退出条件与接受风险。

        ## 更新规则

        - 质量门禁只读本台账，不直接改写结构块。
        - 受控结构块只能通过 `python scripts/sync_debt_ledger.py` 更新。
        - `set-entry-fields` 仅可修改主条目的人工治理字段。
        - `set-entry-fields --status` 当前只接受 `open`、`in_progress`、`blocked`、`fixed` 四个治理状态。
        - `upsert-risk` / `delete-risk` 仅负责维护 `accepted_risks`。
        - 结构块解析失败、重复标记、缺字段、非法分类或悬空引用都会直接失败。

        ## 分类说明

        - `silent_swallow`：静默吞异常。
        - `silent_default_fallback`：无可观测证据地回退默认值。
        - `observable_degrade`：先留可观测证据，再降级继续。
        - `cleanup_best_effort`：关闭、删除、清理、收尾类尽力而为逻辑。

        ## 当前静默回退门禁边界

        - 启动链范围（`web/bootstrap/**/*.py`、`web/ui_mode.py`）按四类分类全量冻结。
        - 非启动链范围当前只续管历史 `silent_swallow` 遗留项，不据此把 `silent_default_fallback` / `observable_degrade` 扩展为全仓新增门禁。

        ## 当前快照

        - 超长文件登记：__OVERSIZE_COUNT__
        - 高复杂度登记：__COMPLEXITY_COUNT__
        - 静默回退登记：__FALLBACK_COUNT__
        - 测试债务登记：__TEST_DEBT_COUNT__
        - 接受风险：__RISK_COUNT__

        ## SP04 人工补充记录

        - 已核实 `web/routes/domains/scheduler/scheduler_batches.py`、`web/routes/domains/scheduler/scheduler_analysis.py`、`web/routes/system_history.py` 当前已统一改为通过 `g.services` 取查询服务，不再保留 SP04 初期的直接装配形态。
        - `web/ui_mode.py:_read_ui_mode_from_db()` 当前已收口到 `g.services.system_config_service.get_value_with_presence(...)` 单接口读取；请求上下文若出现 `g.db` 已挂但 `g.services` 缺失，会显式抛错，不再把容器损坏伪装成“配置缺失”。
        - `web/routes/domains/scheduler/scheduler_excel_batches.py` 中两处 `get_batch_row_validate_and_normalize(...)` 已完成去 `g.db` 首参改造；对应 helper 特批白名单已清空，不再作为阶段性残余保留。
        - `scheduler_batch_detail.py` 的 `OperatorMachineQueryService` 与 `scheduler_excel_batches.py` 的 `ExcelService` 在切容器后会从 `logger=None` 变为 `g.app_logger`；结合当前实现，这应仅增加可观测性，不得改变查询结果、分页、预览结果或导入结果。
        - `RequestServices` 已明确采用 `functools.cached_property` 做惰性构造与单请求缓存；构造成功才缓存，构造异常不写缓存属性，后续访问允许重试。
        - 每个目标文件内的所有路由函数必须在所属批次内一次切换完成，禁止同一文件同时存在容器取用与直接装配两套方式。
        - `system_backup.py`、`system_ui_mode.py`、`system_plugins.py`、`system_logs.py`、`system_utils.py` 中 5 处 `SystemConfigService` 直接装配不在 SP04 两批目标内，但阶段 5 必须列账。
        - `tests/regression_request_services_lazy_construction.py`、`tests/regression_request_services_failure_propagation.py` 属于 SP04 本批新建回归，执行验证命令时需与已有守卫区分。
        - 本节是人工治理说明，不改变当前静默回退门禁分类口径。

        ## 受控结构块
        """
    ).strip()
    body = body.replace("__OVERSIZE_COUNT__", str(oversize_count))
    body = body.replace("__COMPLEXITY_COUNT__", str(complexity_count))
    body = body.replace("__FALLBACK_COUNT__", str(len(fallback_entries)))
    body = body.replace("__TEST_DEBT_COUNT__", str(len(test_debt_entries)))
    body = body.replace("__RISK_COUNT__", str(risk_count))
    return body + "\n\n" + payload_block + "\n"


def save_ledger(ledger: Dict[str, Any]) -> None:
    sorted_ledger = sort_ledger(copy.deepcopy(ledger))
    validate_ledger(sorted_ledger)
    write_text_file("开发文档/技术债务治理台账.md", render_ledger_markdown(sorted_ledger))


def load_sp02_facts_snapshot() -> Dict[str, Any]:
    if not os.path.exists(STAGE_RECORD_PATH):
        raise QualityGateError("阶段留痕文件不存在：开发文档/阶段留痕与验收记录.md")
    text = read_text_file("开发文档/阶段留痕与验收记录.md")
    payload = extract_json_code_block(text, SP02_FACT_BEGIN, SP02_FACT_END, "SP02 事实冻结块")
    if not isinstance(payload.get("legacy_inline_facts"), dict):
        raise QualityGateError("SP02 事实冻结块缺少 legacy_inline_facts")
    return payload


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityGateError(f"字段 {field_name} 必须是非空字符串")
    return value


def _require_entry_status(value: Any, field_name: str) -> str:
    status = _require_string(value, field_name)
    if status not in ENTRY_STATUS_VALUES:
        raise QualityGateError(f"字段 {field_name} 必须是合法治理状态：{sorted(ENTRY_STATUS_VALUES)}")
    return status


def _require_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise QualityGateError(f"字段 {field_name} 必须是整数")
    return int(value)


def _validate_common_entry(entry: Dict[str, Any], field_prefix: str) -> None:
    for field_name in ENTRY_COMMON_FIELDS:
        if field_name not in entry:
            raise QualityGateError(f"{field_prefix} 缺少字段 {field_name}")
    _require_string(entry.get("id"), f"{field_prefix}.id")
    _require_string(entry.get("path"), f"{field_prefix}.path")
    if entry.get("symbol") is not None and not isinstance(entry.get("symbol"), str):
        raise QualityGateError(f"{field_prefix}.symbol 必须是字符串或 null")
    _require_entry_status(entry.get("status"), f"{field_prefix}.status")
    _require_string(entry.get("owner"), f"{field_prefix}.owner")
    _require_string(entry.get("batch"), f"{field_prefix}.batch")
    _require_string(entry.get("exit_condition"), f"{field_prefix}.exit_condition")
    _require_string(entry.get("last_verified_at"), f"{field_prefix}.last_verified_at")
    if entry.get("notes") is not None and not isinstance(entry.get("notes"), str):
        raise QualityGateError(f"{field_prefix}.notes 必须是字符串或 null")


def _require_no_untriaged(value: str, field_name: str) -> None:
    if value.strip().lower() == "untriaged":
        raise QualityGateError(f"{field_name} 不允许写 untriaged 占位")


def _validate_test_debt_entry(entry: Dict[str, Any], field_prefix: str) -> Tuple[str, str, str]:
    for field_name in [
        "debt_id",
        "nodeid",
        "mode",
        "reason",
        "domain",
        "style",
        "root",
        "owner",
        "exit_condition",
        "last_verified_at",
        "debt_family",
    ]:
        if field_name not in entry:
            raise QualityGateError(f"{field_prefix} 缺少字段 {field_name}")
    debt_id = _require_string(entry.get("debt_id"), f"{field_prefix}.debt_id")
    nodeid = _require_string(entry.get("nodeid"), f"{field_prefix}.nodeid")
    mode = _require_string(entry.get("mode"), f"{field_prefix}.mode")
    if mode not in TEST_DEBT_MODE_VALUES:
        raise QualityGateError(f"{field_prefix}.mode 非法：{mode}")
    for field_name in ["reason", "domain", "style", "owner", "exit_condition", "last_verified_at", "debt_family"]:
        value = _require_string(entry.get(field_name), f"{field_prefix}.{field_name}")
        _require_no_untriaged(value, f"{field_prefix}.{field_name}")
    root = entry.get("root")
    if not isinstance(root, dict):
        raise QualityGateError(f"{field_prefix}.root 必须是对象")
    root_module = _require_string(root.get("module"), f"{field_prefix}.root.module")
    root_function = _require_string(root.get("function"), f"{field_prefix}.root.function")
    _require_no_untriaged(root_module, f"{field_prefix}.root.module")
    _require_no_untriaged(root_function, f"{field_prefix}.root.function")
    if entry.get("notes") is not None and not isinstance(entry.get("notes"), str):
        raise QualityGateError(f"{field_prefix}.notes 必须是字符串或 null")
    return debt_id, nodeid, mode


def _validate_ledger_sections(
    ledger: Dict[str, Any],
) -> Tuple[List[Any], List[Any], List[Any], int, List[Any], List[Any]]:
    if not isinstance(ledger, dict):
        raise QualityGateError("治理台账顶层必须是对象")
    if ledger.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise QualityGateError(f"schema_version 必须是 {LEDGER_SCHEMA_VERSION}")
    identity_strategy = ledger.get("identity_strategy")
    if identity_strategy != LEDGER_IDENTITY_STRATEGY:
        raise QualityGateError("identity_strategy 与约定不一致")
    _require_string(ledger.get("updated_at"), "updated_at")

    oversize_entries = ledger.get("oversize_allowlist")
    complexity_entries = ledger.get("complexity_allowlist")
    silent_fallback = ledger.get("silent_fallback")
    test_debt = ledger.get("test_debt")
    accepted_risks = ledger.get("accepted_risks")

    if not isinstance(oversize_entries, list):
        raise QualityGateError("oversize_allowlist 必须是数组")
    if not isinstance(complexity_entries, list):
        raise QualityGateError("complexity_allowlist 必须是数组")
    if not isinstance(silent_fallback, dict):
        raise QualityGateError("silent_fallback 必须是对象")
    if not isinstance(test_debt, dict):
        raise QualityGateError("test_debt 必须是对象")
    if not isinstance(accepted_risks, list):
        raise QualityGateError("accepted_risks 必须是数组")

    scope = silent_fallback.get("scope")
    entries = silent_fallback.get("entries")
    if scope != list(STARTUP_SCOPE_PATTERNS):
        raise QualityGateError("silent_fallback.scope 与约定不一致")
    if not isinstance(entries, list):
        raise QualityGateError("silent_fallback.entries 必须是数组")

    test_debt_ratchet = test_debt.get("ratchet")
    test_debt_entries = test_debt.get("entries")
    if not isinstance(test_debt_ratchet, dict):
        raise QualityGateError("test_debt.ratchet 必须是对象")
    max_registered_xfail = _require_int(
        test_debt_ratchet.get("max_registered_xfail"),
        "test_debt.ratchet.max_registered_xfail",
    )
    if max_registered_xfail < 0:
        raise QualityGateError("test_debt.ratchet.max_registered_xfail 必须大于等于 0")
    if not isinstance(test_debt_entries, list):
        raise QualityGateError("test_debt.entries 必须是数组")

    return oversize_entries, complexity_entries, entries, max_registered_xfail, test_debt_entries, accepted_risks


def _register_main_entry_id(all_main_ids: Set[str], entry_id: str) -> None:
    if entry_id in all_main_ids:
        raise QualityGateError(f"主条目 id 重复：{entry_id}")
    all_main_ids.add(entry_id)


def _validate_oversize_entries(oversize_entries: List[Any], all_main_ids: Set[str]) -> None:
    for index, entry in enumerate(oversize_entries):
        if not isinstance(entry, dict):
            raise QualityGateError(f"oversize_allowlist[{index}] 必须是对象")
        _validate_common_entry(entry, f"oversize_allowlist[{index}]")
        _require_int(entry.get("current_value"), f"oversize_allowlist[{index}].current_value")
        _require_int(entry.get("limit"), f"oversize_allowlist[{index}].limit")
        _register_main_entry_id(all_main_ids, str(entry.get("id")))


def _validate_complexity_entries(complexity_entries: List[Any], all_main_ids: Set[str]) -> None:
    for index, entry in enumerate(complexity_entries):
        if not isinstance(entry, dict):
            raise QualityGateError(f"complexity_allowlist[{index}] 必须是对象")
        _validate_common_entry(entry, f"complexity_allowlist[{index}]")
        _require_int(entry.get("current_value"), f"complexity_allowlist[{index}].current_value")
        _require_int(entry.get("threshold"), f"complexity_allowlist[{index}].threshold")
        _register_main_entry_id(all_main_ids, str(entry.get("id")))


def _validate_ui_mode_scope(entry: Dict[str, Any]) -> None:
    path = str(entry.get("path"))
    scope_tag = entry.get("scope_tag")
    if path == "web/ui_mode.py":
        if scope_tag not in UI_MODE_SCOPE_TAG_VALUES:
            raise QualityGateError("web/ui_mode.py 条目必须带合法 scope_tag：{}".format(entry.get("id")))
        if scope_tag == "render_bridge" and str(entry.get("batch")) == "SP03":
            raise QualityGateError("render_bridge 条目不得归属 SP03：{}".format(entry.get("id")))
    elif scope_tag is not None and not isinstance(scope_tag, str):
        raise QualityGateError("scope_tag 必须是字符串或 null：{}".format(entry.get("id")))


def _validate_silent_fallback_entries(silent_entries: List[Any], all_main_ids: Set[str]) -> None:
    fallback_unique_keys = set()

    for index, entry in enumerate(silent_entries):
        if not isinstance(entry, dict):
            raise QualityGateError(f"silent_fallback.entries[{index}] 必须是对象")
        _validate_common_entry(entry, f"silent_fallback.entries[{index}]")
        _require_string(entry.get("handler_fingerprint"), f"silent_fallback.entries[{index}].handler_fingerprint")
        _require_int(entry.get("except_ordinal"), f"silent_fallback.entries[{index}].except_ordinal")
        _require_int(entry.get("line_start"), f"silent_fallback.entries[{index}].line_start")
        _require_int(entry.get("line_end"), f"silent_fallback.entries[{index}].line_end")
        _require_string(entry.get("fallback_kind"), f"silent_fallback.entries[{index}].fallback_kind")
        _require_string(entry.get("source"), f"silent_fallback.entries[{index}].source")
        if str(entry.get("fallback_kind")) not in FALLBACK_KIND_VALUES:
            raise QualityGateError("silent_fallback.entries[{}].fallback_kind 非法：{}".format(index, entry.get("fallback_kind")))
        _validate_ui_mode_scope(entry)
        _register_main_entry_id(all_main_ids, str(entry.get("id")))
        except_ordinal = _require_int(entry.get("except_ordinal"), f"silent_fallback.entries[{index}].except_ordinal")
        unique_key = (
            str(entry.get("path")),
            str(entry.get("symbol") or ""),
            str(entry.get("handler_fingerprint")),
            except_ordinal,
        )
        if unique_key in fallback_unique_keys:
            raise QualityGateError(f"silent_fallback.entries 存在重复登记：{unique_key}")
        fallback_unique_keys.add(unique_key)


def _validate_test_debt_entries(test_debt_entries: List[Any], max_registered_xfail: int) -> None:
    test_debt_ids: Set[str] = set()
    test_debt_nodeids: Set[str] = set()
    active_xfail_count = 0
    for index, entry in enumerate(test_debt_entries):
        if not isinstance(entry, dict):
            raise QualityGateError(f"test_debt.entries[{index}] 必须是对象")
        debt_id, nodeid, mode = _validate_test_debt_entry(entry, f"test_debt.entries[{index}]")
        if debt_id in test_debt_ids:
            raise QualityGateError(f"test_debt.entries debt_id 重复：{debt_id}")
        if nodeid in test_debt_nodeids:
            raise QualityGateError(f"test_debt.entries nodeid 重复：{nodeid}")
        test_debt_ids.add(debt_id)
        test_debt_nodeids.add(nodeid)
        if mode == "xfail":
            active_xfail_count += 1
    if active_xfail_count > max_registered_xfail:
        raise QualityGateError("test_debt.ratchet.max_registered_xfail 小于当前 xfail 登记数量")


def _validate_accepted_risks(accepted_risks: List[Any], all_main_ids: Set[str]) -> None:
    risk_ids = set()
    for index, risk in enumerate(accepted_risks):
        if not isinstance(risk, dict):
            raise QualityGateError(f"accepted_risks[{index}] 必须是对象")
        for field_name in ["id", "entry_ids", "owner", "reason", "review_after", "exit_condition"]:
            if field_name not in risk:
                raise QualityGateError(f"accepted_risks[{index}] 缺少字段 {field_name}")
        risk_id = _require_string(risk.get("id"), f"accepted_risks[{index}].id")
        if risk_id in risk_ids:
            raise QualityGateError(f"accepted_risks id 重复：{risk_id}")
        risk_ids.add(risk_id)
        entry_ids = risk.get("entry_ids")
        if not isinstance(entry_ids, list) or not entry_ids:
            raise QualityGateError(f"accepted_risks[{index}].entry_ids 必须是非空数组")
        for entry_id in entry_ids:
            if not isinstance(entry_id, str) or not entry_id:
                raise QualityGateError(f"accepted_risks[{index}].entry_ids 含非法值")
            if entry_id not in all_main_ids:
                raise QualityGateError(f"accepted_risks[{index}] 引用了不存在的主条目：{entry_id}")
        _require_string(risk.get("owner"), f"accepted_risks[{index}].owner")
        _require_string(risk.get("reason"), f"accepted_risks[{index}].reason")
        _require_string(risk.get("review_after"), f"accepted_risks[{index}].review_after")
        _require_string(risk.get("exit_condition"), f"accepted_risks[{index}].exit_condition")
        if risk.get("notes") is not None and not isinstance(risk.get("notes"), str):
            raise QualityGateError(f"accepted_risks[{index}].notes 必须是字符串或 null")


def validate_ledger(ledger: Dict[str, Any]) -> None:
    (
        oversize_entries,
        complexity_entries,
        silent_entries,
        max_registered_xfail,
        test_debt_entries,
        accepted_risks,
    ) = _validate_ledger_sections(ledger)
    all_main_ids: Set[str] = set()
    _validate_oversize_entries(oversize_entries, all_main_ids)
    _validate_complexity_entries(complexity_entries, all_main_ids)
    _validate_silent_fallback_entries(silent_entries, all_main_ids)
    _validate_test_debt_entries(test_debt_entries, max_registered_xfail)
    _validate_accepted_risks(accepted_risks, all_main_ids)


def entry_sort_key(entry: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        str(entry.get("path") or ""),
        str(entry.get("symbol") or ""),
        str(entry.get("handler_fingerprint") or ""),
        int(entry.get("except_ordinal") or 0),
        str(entry.get("id") or ""),
    )


def _ordered_common_fields(entry: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "id": entry.get("id"),
        "path": entry.get("path"),
        "symbol": entry.get("symbol"),
        "status": entry.get("status"),
        "owner": entry.get("owner"),
        "batch": entry.get("batch"),
        "exit_condition": entry.get("exit_condition"),
        "last_verified_at": entry.get("last_verified_at"),
    }
    if "notes" in entry:
        data["notes"] = entry.get("notes")
    return data


def _ordered_test_debt_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "debt_id": entry.get("debt_id"),
        "nodeid": entry.get("nodeid"),
        "mode": entry.get("mode"),
        "reason": entry.get("reason"),
        "domain": entry.get("domain"),
        "style": entry.get("style"),
        "root": {
            "module": cast(Dict[str, Any], entry.get("root") or {}).get("module"),
            "function": cast(Dict[str, Any], entry.get("root") or {}).get("function"),
        },
        "owner": entry.get("owner"),
        "exit_condition": entry.get("exit_condition"),
        "last_verified_at": entry.get("last_verified_at"),
        "debt_family": entry.get("debt_family"),
    }
    if "notes" in entry:
        data["notes"] = entry.get("notes")
    return data


def _ordered_oversize_entries(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    ordered = []
    for entry in sorted(
        cast(List[Dict[str, Any]], ledger.get("oversize_allowlist") or []),
        key=lambda item: (str(item.get("path") or ""), str(item.get("id") or "")),
    ):
        data = _ordered_common_fields(entry)
        data["current_value"] = int(entry.get("current_value") or 0)
        data["limit"] = int(entry.get("limit") or FILE_SIZE_LIMIT)
        ordered.append(data)
    return ordered


def _ordered_complexity_entries(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    ordered = []
    for entry in sorted(
        cast(List[Dict[str, Any]], ledger.get("complexity_allowlist") or []),
        key=lambda item: (str(item.get("path") or ""), str(item.get("symbol") or ""), str(item.get("id") or "")),
    ):
        data = _ordered_common_fields(entry)
        data["current_value"] = int(entry.get("current_value") or 0)
        data["threshold"] = int(entry.get("threshold") or COMPLEXITY_THRESHOLD)
        ordered.append(data)
    return ordered


def _ordered_silent_entries(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    ordered = []
    for entry in sorted(
        cast(List[Dict[str, Any]], cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []),
        key=entry_sort_key,
    ):
        data = _ordered_common_fields(entry)
        data["handler_fingerprint"] = entry.get("handler_fingerprint")
        data["except_ordinal"] = int(entry.get("except_ordinal") or 0)
        data["line_start"] = int(entry.get("line_start") or 0)
        data["line_end"] = int(entry.get("line_end") or 0)
        data["fallback_kind"] = entry.get("fallback_kind")
        if entry.get("scope_tag") is not None:
            data["scope_tag"] = entry.get("scope_tag")
        data["source"] = entry.get("source")
        data.setdefault("notes", entry.get("notes"))
        ordered.append(data)
    return ordered


def _ordered_test_debt_section(test_debt: Dict[str, Any]) -> Dict[str, Any]:
    ratchet = cast(Dict[str, Any], test_debt.get("ratchet") or {})
    entries = [
        _ordered_test_debt_entry(entry)
        for entry in sorted(
            cast(List[Dict[str, Any]], test_debt.get("entries") or []),
            key=lambda item: (str(item.get("nodeid") or ""), str(item.get("debt_id") or "")),
        )
    ]
    return {
        "ratchet": {"max_registered_xfail": int(ratchet.get("max_registered_xfail", 0) or 0)},
        "entries": entries,
    }


def _ordered_accepted_risks(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    ordered = []
    for risk in sorted(cast(List[Dict[str, Any]], ledger.get("accepted_risks") or []), key=lambda item: str(item.get("id") or "")):
        data = {
            "id": risk.get("id"),
            "entry_ids": sorted([str(item) for item in cast(List[Any], risk.get("entry_ids") or [])]),
            "owner": risk.get("owner"),
            "reason": risk.get("reason"),
            "review_after": risk.get("review_after"),
            "exit_condition": risk.get("exit_condition"),
        }
        if "notes" in risk:
            data["notes"] = risk.get("notes")
        ordered.append(data)
    return ordered


def sort_ledger(ledger: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(ledger.get("test_debt"), dict):
        raise QualityGateError("test_debt 必须是对象")
    test_debt = cast(Dict[str, Any], ledger.get("test_debt") or {})
    if not isinstance(test_debt.get("ratchet"), dict):
        raise QualityGateError("test_debt.ratchet 必须是对象")
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "identity_strategy": LEDGER_IDENTITY_STRATEGY,
        "updated_at": ledger.get("updated_at") or now_shanghai_iso(),
        "oversize_allowlist": _ordered_oversize_entries(ledger),
        "complexity_allowlist": _ordered_complexity_entries(ledger),
        "silent_fallback": {"scope": list(STARTUP_SCOPE_PATTERNS), "entries": _ordered_silent_entries(ledger)},
        "test_debt": _ordered_test_debt_section(test_debt),
        "accepted_risks": _ordered_accepted_risks(ledger),
    }


def collect_main_entry_ids(ledger: Dict[str, Any]) -> Set[str]:
    ids = set()
    for section_name in ["oversize_allowlist", "complexity_allowlist"]:
        for entry in cast(List[Dict[str, Any]], ledger.get(section_name) or []):
            ids.add(str(entry.get("id")))
    for entry in cast(Dict[str, Any], ledger.get("silent_fallback") or {}).get("entries") or []:
        ids.add(str(entry.get("id")))
    return ids


def _ledger_semantics_equal(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_copy = copy.deepcopy(left)
    right_copy = copy.deepcopy(right)
    left_copy["updated_at"] = "_"
    right_copy["updated_at"] = "_"
    return left_copy == right_copy


def finalize_ledger_update(ledger: Dict[str, Any]) -> Dict[str, Any]:
    current = load_ledger(required=False)
    next_ledger = sort_ledger(copy.deepcopy(ledger))
    current_sorted = sort_ledger(copy.deepcopy(current))
    if _ledger_semantics_equal(current_sorted, next_ledger):
        next_ledger["updated_at"] = current_sorted.get("updated_at") or next_ledger.get("updated_at")
    else:
        next_ledger["updated_at"] = now_shanghai_iso()
    validate_ledger(next_ledger)
    return next_ledger


__all__ = [
    "collect_main_entry_ids",
    "default_ledger",
    "finalize_ledger_update",
    "load_ledger",
    "load_ledger_for_test_debt_import",
    "load_sp02_facts_snapshot",
    "render_ledger_markdown",
    "save_ledger",
    "sort_ledger",
    "validate_ledger",
    "entry_sort_key",
]
