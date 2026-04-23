# APS 静默回退修复 - 三轮深度审查
- Date: 2026-04-02
- Overview: 对 49 个未提交文件的全面深度审查：strict_mode 传播链、observability 增强、引用链一致性
- Status: in_progress

## Review Scope
# APS 静默回退修复 - 三轮深度审查

**日期**：2026-04-02  
**审查范围**：49 个未提交修改文件  
**审查方法**：三轮引用链追踪 + 数据流验证 + 边界条件分析

### 变更概要
本次变更的核心目标是**消除静默回退（silent fallback）**，通过引入 `strict_mode` 参数贯穿整条调用链，使得原本会"静默回退到默认值"的行为，在严格模式下变为显式报错。同时增强了排产结果的可观测性（algo_stats、warning_pipeline、resource_pool_meta 等）。

### 变更分类

| 类别 | 文件数 | 关键变更 |
|------|--------|---------|
| 核心算法层 | 5 | algo_stats 计数、strict_mode 校验、seed 防御 |
| 核心基础设施 | 1 | ValidationError.field 类型注解修正 |
| 服务层-工艺 | 4 | route_parser strict_mode、supplier_map issues 返回、_coerce_external_default_days |
| 服务层-排产 | 11 | strict_mode 传播、schedule_summary 大量 observability、resource_pool_builder 细粒度错误 |
| Web 路由层 | 6 | strict_mode 解析与传递、_strict_mode_enabled 工具函数 |
| 模板层 | 7 | strict_mode checkbox UI、batch_detail 增强 |
| 测试 | 4 | 回归测试更新 |
| 文档/证据 | 8 | 审计文档、evidence 报告更新 |

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: in_progress
- Reviewed modules: tests/, core/services/scheduler/schedule_service.py, core/services/scheduler/config_presets.py, core/services/scheduler/config_snapshot.py
- Current progress: 1 milestones recorded; latest: M1
- Total milestones: 1
- Completed milestones: 1
- Total findings: 4
- Findings by severity: high 1 / medium 3 / low 0
- Latest conclusion: ## 第一轮审查：引用链完整性 + 测试回归 ### 1. `strict_mode` 传播链完整性验证 追踪 strict_mode 从 Web 入口到最底层的完整传播链： ``` Web Route (request.form → _strict_mode_enabled) → scheduler_run.py / scheduler_week_plan.py → ScheduleService.run_schedule(strict_mode=...) → ConfigService.get_snapshot(strict_mode=...) → config_presets.get_snapshot_from_repo(strict_mode=...) → config_snapshot.build_schedule_config_snapshot(strict_mode=...) → _choice(strict=bool(strict_mode)) / _yes_no(strict=bool(strict_mode)) → schedule_optimizer.run_optimization(strict_mode=...) → _run_multi_start(strict_mode=...) → _schedule_with_optional_strict_mode(scheduler, strict_mode=...) → scheduler.schedule(strict_mode=...) → resolve_schedule_params(strict_mode=...) ``` **✅ 验证通过**：排产路径 strict_mode 从 web 到算法层完整贯穿。 ``` Web Route (process_parts.py → PartService.create(strict_mode=...)) → _parse_route_or_raise(strict_mode=...) → route_parser.parse(strict_mode=...) → _build_supplier_map() → 返回 (result, issues) → 工种未识别 → errors.append() [strict] / warnings.append() [non-strict] → 供应商缺失 → errors.append() [strict] / fallback 1.0 天 [non-strict] ``` **✅ 验证通过**：工艺路线解析路径 strict_mode 完整贯穿。 ``` Web Route (scheduler_excel_batches.py → BatchService.import_from_preview(strict_mode=...)) → batch_excel_import(strict_mode=...) → create_batch_from_template_no_tx(strict_mode=...) → _load_template_ops_with_fallback(strict_mode=...) → _invoke_template_resolver(strict_mode=...) → _default_template_resolver(strict_mode=...) → upsert_and_parse_no_tx(strict_mode=...) / reparse_and_save(strict_mode=...) ``` **✅ 验证通过**：批次导入路径 strict_mode 完整贯穿。 ### 2. 测试回归分析 运行全量测试 272 项，发现 **11 项失败**，其中： | 失败测试 | 根因 | 是否本次变更引起 | 严重度 | |---------|------|----------------|--------| | `regression_auto_assign_persist_truthy_variants` | mock `_patched_get_snapshot(self)` 缺少 `strict_mode` 参数 | **是** | P0 | | `test_file_size_limit` | 5 个文件超过 500 行 | **是** | P1 | | `test_no_silent_exception_swallow` | 新增 bare except 模式 | **是** | P1 | | `test_cyclomatic_complexity_threshold` | `_build_supplier_map` CC=19 等 | **是** | P1 | | `test_no_circular_service_dependencies` | `common ↔ scheduler` 循环 | 待确认 | P1 | | `regression_config_manual_markdown` | JS 渲染分支缺失 | **否**（预存在） | - | | `regression_skill_rank_mapping` | 预存在 | **否** | - | | `regression_startup_host_portfile` (×2) | 端口文件竞争 | **否** | - | | `test_team_pages_excel_smoke` | Windows 文件锁 | **否** | - | | `test_excel_normalizers_contract` | 间歇性（重跑通过） | **否** | - | ### 3. P0 问题详解 **`regression_auto_assign_persist_truthy_variants` 失败**： ```python # tests/regression_auto_assign_persist_truthy_variants.py:75 def _patched_get_snapshot(self): # 缺少 strict_mode 参数 snap = orig_get_snapshot(self) setattr(snap, "auto_assign_persist", "1") return snap ``` `schedule_service.py:284` 现在调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`， 但 mock 不接受 `strict_mode` 关键字参数，导致 `TypeError`。 **修复方案**：`def _patched_get_snapshot(self, **kwargs):` 或 `def _patched_get_snapshot(self, *, strict_mode=False):`
- Recommended next action: pending
- Overall decision: pending
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [high] test: mock 签名与实际 API 不兼容导致测试 TypeError
  - ID: F001
  - Description: tests/regression_auto_assign_persist_truthy_variants.py 中 _patched_get_snapshot(self) 未接受 strict_mode 参数，schedule_service.py:284 现在会传 strict_mode=bool(strict_mode)，导致 TypeError。
  - Evidence Files:
    - `tests/regression_auto_assign_persist_truthy_variants.py`
    - `core/services/scheduler/schedule_service.py`
  - Related Milestones: M1
  - Recommendation: 将 mock 签名改为 _patched_get_snapshot(self, **kwargs) 或 _patched_get_snapshot(self, *, strict_mode=False)

- [medium] maintainability: 5 个核心文件超过 500 行限制
  - ID: F002
  - Description: part_service.py(512), batch_service.py(508), schedule_optimizer.py(584), schedule_service.py(532), schedule_summary.py(648) 超过架构适配测试的 500 行限制。
  - Evidence Files:
    - `tests/test_architecture_fitness.py`
  - Related Milestones: M1
  - Recommendation: 添加到 known_oversize 白名单或进一步拆分。schedule_summary.py(648 行) 应优先考虑拆分。

- [medium] maintainability: 新增 bare except 模式未更新白名单
  - ID: F003
  - Description: external_group_service.py(+1), part_service.py(+1), route_parser.py(+1), supplier_service.py(+1), resource_pool_builder.py(+4) 新增了 except Exception: pass/continue 模式。
  - Evidence Files:
    - `tests/test_architecture_fitness.py`
  - Related Milestones: M1
  - Recommendation: 更新 test_architecture_fitness.py 的 known_violations 白名单并注明原因，或改用更精确的异常捕获。

- [medium] maintainability: 新增高圈复杂度函数未加入白名单
  - ID: F004
  - Description: route_parser._build_supplier_map CC=19, schedule_summary._compute_downtime_degradation CC=18, schedule_optimizer._compact_attempts CC=16。
  - Evidence Files:
    - `core/services/process/route_parser.py`
    - `core/services/scheduler/schedule_summary.py`
  - Related Milestones: M1
  - Recommendation: 拆分或加入 known_violations 白名单。_build_supplier_map 的 CC=19 尤其需要考虑拆分。
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### M1 · 第一轮：引用链完整性 + 测试回归
- Status: completed
- Recorded At: 2026-04-02T06:52:15.407Z
- Reviewed Modules: tests/, core/services/scheduler/schedule_service.py, core/services/scheduler/config_presets.py, core/services/scheduler/config_snapshot.py
- Summary:
## 第一轮审查：引用链完整性 + 测试回归

### 1. `strict_mode` 传播链完整性验证

追踪 strict_mode 从 Web 入口到最底层的完整传播链：

```
Web Route (request.form → _strict_mode_enabled)
  → scheduler_run.py / scheduler_week_plan.py → ScheduleService.run_schedule(strict_mode=...)
    → ConfigService.get_snapshot(strict_mode=...)
      → config_presets.get_snapshot_from_repo(strict_mode=...)
        → config_snapshot.build_schedule_config_snapshot(strict_mode=...)
          → _choice(strict=bool(strict_mode)) / _yes_no(strict=bool(strict_mode))
    → schedule_optimizer.run_optimization(strict_mode=...)
      → _run_multi_start(strict_mode=...)
        → _schedule_with_optional_strict_mode(scheduler, strict_mode=...)
          → scheduler.schedule(strict_mode=...)
            → resolve_schedule_params(strict_mode=...)
```

**✅ 验证通过**：排产路径 strict_mode 从 web 到算法层完整贯穿。

```
Web Route (process_parts.py → PartService.create(strict_mode=...))
  → _parse_route_or_raise(strict_mode=...)
    → route_parser.parse(strict_mode=...)
      → _build_supplier_map() → 返回 (result, issues)
      → 工种未识别 → errors.append() [strict] / warnings.append() [non-strict]
      → 供应商缺失 → errors.append() [strict] / fallback 1.0 天 [non-strict]
```

**✅ 验证通过**：工艺路线解析路径 strict_mode 完整贯穿。

```
Web Route (scheduler_excel_batches.py → BatchService.import_from_preview(strict_mode=...))
  → batch_excel_import(strict_mode=...)
    → create_batch_from_template_no_tx(strict_mode=...)
      → _load_template_ops_with_fallback(strict_mode=...)
        → _invoke_template_resolver(strict_mode=...)
          → _default_template_resolver(strict_mode=...)
            → upsert_and_parse_no_tx(strict_mode=...) / reparse_and_save(strict_mode=...)
```

**✅ 验证通过**：批次导入路径 strict_mode 完整贯穿。

### 2. 测试回归分析

运行全量测试 272 项，发现 **11 项失败**，其中：

| 失败测试 | 根因 | 是否本次变更引起 | 严重度 |
|---------|------|----------------|--------|
| `regression_auto_assign_persist_truthy_variants` | mock `_patched_get_snapshot(self)` 缺少 `strict_mode` 参数 | **是** | P0 |
| `test_file_size_limit` | 5 个文件超过 500 行 | **是** | P1 |
| `test_no_silent_exception_swallow` | 新增 bare except 模式 | **是** | P1 |
| `test_cyclomatic_complexity_threshold` | `_build_supplier_map` CC=19 等 | **是** | P1 |
| `test_no_circular_service_dependencies` | `common ↔ scheduler` 循环 | 待确认 | P1 |
| `regression_config_manual_markdown` | JS 渲染分支缺失 | **否**（预存在） | - |
| `regression_skill_rank_mapping` | 预存在 | **否** | - |
| `regression_startup_host_portfile` (×2) | 端口文件竞争 | **否** | - |
| `test_team_pages_excel_smoke` | Windows 文件锁 | **否** | - |
| `test_excel_normalizers_contract` | 间歇性（重跑通过） | **否** | - |

### 3. P0 问题详解

**`regression_auto_assign_persist_truthy_variants` 失败**：

```python
# tests/regression_auto_assign_persist_truthy_variants.py:75
def _patched_get_snapshot(self):  # 缺少 strict_mode 参数
    snap = orig_get_snapshot(self)
    setattr(snap, "auto_assign_persist", "1")
    return snap
```

`schedule_service.py:284` 现在调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`，
但 mock 不接受 `strict_mode` 关键字参数，导致 `TypeError`。

**修复方案**：`def _patched_get_snapshot(self, **kwargs):` 或 `def _patched_get_snapshot(self, *, strict_mode=False):`
- Conclusion: ## 第一轮审查：引用链完整性 + 测试回归 ### 1. `strict_mode` 传播链完整性验证 追踪 strict_mode 从 Web 入口到最底层的完整传播链： ``` Web Route (request.form → _strict_mode_enabled) → scheduler_run.py / scheduler_week_plan.py → ScheduleService.run_schedule(strict_mode=...) → ConfigService.get_snapshot(strict_mode=...) → config_presets.get_snapshot_from_repo(strict_mode=...) → config_snapshot.build_schedule_config_snapshot(strict_mode=...) → _choice(strict=bool(strict_mode)) / _yes_no(strict=bool(strict_mode)) → schedule_optimizer.run_optimization(strict_mode=...) → _run_multi_start(strict_mode=...) → _schedule_with_optional_strict_mode(scheduler, strict_mode=...) → scheduler.schedule(strict_mode=...) → resolve_schedule_params(strict_mode=...) ``` **✅ 验证通过**：排产路径 strict_mode 从 web 到算法层完整贯穿。 ``` Web Route (process_parts.py → PartService.create(strict_mode=...)) → _parse_route_or_raise(strict_mode=...) → route_parser.parse(strict_mode=...) → _build_supplier_map() → 返回 (result, issues) → 工种未识别 → errors.append() [strict] / warnings.append() [non-strict] → 供应商缺失 → errors.append() [strict] / fallback 1.0 天 [non-strict] ``` **✅ 验证通过**：工艺路线解析路径 strict_mode 完整贯穿。 ``` Web Route (scheduler_excel_batches.py → BatchService.import_from_preview(strict_mode=...)) → batch_excel_import(strict_mode=...) → create_batch_from_template_no_tx(strict_mode=...) → _load_template_ops_with_fallback(strict_mode=...) → _invoke_template_resolver(strict_mode=...) → _default_template_resolver(strict_mode=...) → upsert_and_parse_no_tx(strict_mode=...) / reparse_and_save(strict_mode=...) ``` **✅ 验证通过**：批次导入路径 strict_mode 完整贯穿。 ### 2. 测试回归分析 运行全量测试 272 项，发现 **11 项失败**，其中： | 失败测试 | 根因 | 是否本次变更引起 | 严重度 | |---------|------|----------------|--------| | `regression_auto_assign_persist_truthy_variants` | mock `_patched_get_snapshot(self)` 缺少 `strict_mode` 参数 | **是** | P0 | | `test_file_size_limit` | 5 个文件超过 500 行 | **是** | P1 | | `test_no_silent_exception_swallow` | 新增 bare except 模式 | **是** | P1 | | `test_cyclomatic_complexity_threshold` | `_build_supplier_map` CC=19 等 | **是** | P1 | | `test_no_circular_service_dependencies` | `common ↔ scheduler` 循环 | 待确认 | P1 | | `regression_config_manual_markdown` | JS 渲染分支缺失 | **否**（预存在） | - | | `regression_skill_rank_mapping` | 预存在 | **否** | - | | `regression_startup_host_portfile` (×2) | 端口文件竞争 | **否** | - | | `test_team_pages_excel_smoke` | Windows 文件锁 | **否** | - | | `test_excel_normalizers_contract` | 间歇性（重跑通过） | **否** | - | ### 3. P0 问题详解 **`regression_auto_assign_persist_truthy_variants` 失败**： ```python # tests/regression_auto_assign_persist_truthy_variants.py:75 def _patched_get_snapshot(self): # 缺少 strict_mode 参数 snap = orig_get_snapshot(self) setattr(snap, "auto_assign_persist", "1") return snap ``` `schedule_service.py:284` 现在调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`， 但 mock 不接受 `strict_mode` 关键字参数，导致 `TypeError`。 **修复方案**：`def _patched_get_snapshot(self, **kwargs):` 或 `def _patched_get_snapshot(self, *, strict_mode=False):`
- Findings:
  - [high] test: mock 签名与实际 API 不兼容导致测试 TypeError
  - [medium] maintainability: 5 个核心文件超过 500 行限制
  - [medium] maintainability: 新增 bare except 模式未更新白名单
  - [medium] maintainability: 新增高圈复杂度函数未加入白名单
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mnh49jkn-ypw7h6",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "finalizedAt": null,
  "status": "in_progress",
  "overallDecision": null,
  "latestConclusion": "## 第一轮审查：引用链完整性 + 测试回归 ### 1. `strict_mode` 传播链完整性验证 追踪 strict_mode 从 Web 入口到最底层的完整传播链： ``` Web Route (request.form → _strict_mode_enabled) → scheduler_run.py / scheduler_week_plan.py → ScheduleService.run_schedule(strict_mode=...) → ConfigService.get_snapshot(strict_mode=...) → config_presets.get_snapshot_from_repo(strict_mode=...) → config_snapshot.build_schedule_config_snapshot(strict_mode=...) → _choice(strict=bool(strict_mode)) / _yes_no(strict=bool(strict_mode)) → schedule_optimizer.run_optimization(strict_mode=...) → _run_multi_start(strict_mode=...) → _schedule_with_optional_strict_mode(scheduler, strict_mode=...) → scheduler.schedule(strict_mode=...) → resolve_schedule_params(strict_mode=...) ``` **✅ 验证通过**：排产路径 strict_mode 从 web 到算法层完整贯穿。 ``` Web Route (process_parts.py → PartService.create(strict_mode=...)) → _parse_route_or_raise(strict_mode=...) → route_parser.parse(strict_mode=...) → _build_supplier_map() → 返回 (result, issues) → 工种未识别 → errors.append() [strict] / warnings.append() [non-strict] → 供应商缺失 → errors.append() [strict] / fallback 1.0 天 [non-strict] ``` **✅ 验证通过**：工艺路线解析路径 strict_mode 完整贯穿。 ``` Web Route (scheduler_excel_batches.py → BatchService.import_from_preview(strict_mode=...)) → batch_excel_import(strict_mode=...) → create_batch_from_template_no_tx(strict_mode=...) → _load_template_ops_with_fallback(strict_mode=...) → _invoke_template_resolver(strict_mode=...) → _default_template_resolver(strict_mode=...) → upsert_and_parse_no_tx(strict_mode=...) / reparse_and_save(strict_mode=...) ``` **✅ 验证通过**：批次导入路径 strict_mode 完整贯穿。 ### 2. 测试回归分析 运行全量测试 272 项，发现 **11 项失败**，其中： | 失败测试 | 根因 | 是否本次变更引起 | 严重度 | |---------|------|----------------|--------| | `regression_auto_assign_persist_truthy_variants` | mock `_patched_get_snapshot(self)` 缺少 `strict_mode` 参数 | **是** | P0 | | `test_file_size_limit` | 5 个文件超过 500 行 | **是** | P1 | | `test_no_silent_exception_swallow` | 新增 bare except 模式 | **是** | P1 | | `test_cyclomatic_complexity_threshold` | `_build_supplier_map` CC=19 等 | **是** | P1 | | `test_no_circular_service_dependencies` | `common ↔ scheduler` 循环 | 待确认 | P1 | | `regression_config_manual_markdown` | JS 渲染分支缺失 | **否**（预存在） | - | | `regression_skill_rank_mapping` | 预存在 | **否** | - | | `regression_startup_host_portfile` (×2) | 端口文件竞争 | **否** | - | | `test_team_pages_excel_smoke` | Windows 文件锁 | **否** | - | | `test_excel_normalizers_contract` | 间歇性（重跑通过） | **否** | - | ### 3. P0 问题详解 **`regression_auto_assign_persist_truthy_variants` 失败**： ```python # tests/regression_auto_assign_persist_truthy_variants.py:75 def _patched_get_snapshot(self): # 缺少 strict_mode 参数 snap = orig_get_snapshot(self) setattr(snap, \"auto_assign_persist\", \"1\") return snap ``` `schedule_service.py:284` 现在调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`， 但 mock 不接受 `strict_mode` 关键字参数，导致 `TypeError`。 **修复方案**：`def _patched_get_snapshot(self, **kwargs):` 或 `def _patched_get_snapshot(self, *, strict_mode=False):`",
  "recommendedNextAction": null,
  "reviewedModules": [
    "tests/",
    "core/services/scheduler/schedule_service.py",
    "core/services/scheduler/config_presets.py",
    "core/services/scheduler/config_snapshot.py"
  ],
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：引用链完整性 + 测试回归",
      "summary": "## 第一轮审查：引用链完整性 + 测试回归\n\n### 1. `strict_mode` 传播链完整性验证\n\n追踪 strict_mode 从 Web 入口到最底层的完整传播链：\n\n```\nWeb Route (request.form → _strict_mode_enabled)\n  → scheduler_run.py / scheduler_week_plan.py → ScheduleService.run_schedule(strict_mode=...)\n    → ConfigService.get_snapshot(strict_mode=...)\n      → config_presets.get_snapshot_from_repo(strict_mode=...)\n        → config_snapshot.build_schedule_config_snapshot(strict_mode=...)\n          → _choice(strict=bool(strict_mode)) / _yes_no(strict=bool(strict_mode))\n    → schedule_optimizer.run_optimization(strict_mode=...)\n      → _run_multi_start(strict_mode=...)\n        → _schedule_with_optional_strict_mode(scheduler, strict_mode=...)\n          → scheduler.schedule(strict_mode=...)\n            → resolve_schedule_params(strict_mode=...)\n```\n\n**✅ 验证通过**：排产路径 strict_mode 从 web 到算法层完整贯穿。\n\n```\nWeb Route (process_parts.py → PartService.create(strict_mode=...))\n  → _parse_route_or_raise(strict_mode=...)\n    → route_parser.parse(strict_mode=...)\n      → _build_supplier_map() → 返回 (result, issues)\n      → 工种未识别 → errors.append() [strict] / warnings.append() [non-strict]\n      → 供应商缺失 → errors.append() [strict] / fallback 1.0 天 [non-strict]\n```\n\n**✅ 验证通过**：工艺路线解析路径 strict_mode 完整贯穿。\n\n```\nWeb Route (scheduler_excel_batches.py → BatchService.import_from_preview(strict_mode=...))\n  → batch_excel_import(strict_mode=...)\n    → create_batch_from_template_no_tx(strict_mode=...)\n      → _load_template_ops_with_fallback(strict_mode=...)\n        → _invoke_template_resolver(strict_mode=...)\n          → _default_template_resolver(strict_mode=...)\n            → upsert_and_parse_no_tx(strict_mode=...) / reparse_and_save(strict_mode=...)\n```\n\n**✅ 验证通过**：批次导入路径 strict_mode 完整贯穿。\n\n### 2. 测试回归分析\n\n运行全量测试 272 项，发现 **11 项失败**，其中：\n\n| 失败测试 | 根因 | 是否本次变更引起 | 严重度 |\n|---------|------|----------------|--------|\n| `regression_auto_assign_persist_truthy_variants` | mock `_patched_get_snapshot(self)` 缺少 `strict_mode` 参数 | **是** | P0 |\n| `test_file_size_limit` | 5 个文件超过 500 行 | **是** | P1 |\n| `test_no_silent_exception_swallow` | 新增 bare except 模式 | **是** | P1 |\n| `test_cyclomatic_complexity_threshold` | `_build_supplier_map` CC=19 等 | **是** | P1 |\n| `test_no_circular_service_dependencies` | `common ↔ scheduler` 循环 | 待确认 | P1 |\n| `regression_config_manual_markdown` | JS 渲染分支缺失 | **否**（预存在） | - |\n| `regression_skill_rank_mapping` | 预存在 | **否** | - |\n| `regression_startup_host_portfile` (×2) | 端口文件竞争 | **否** | - |\n| `test_team_pages_excel_smoke` | Windows 文件锁 | **否** | - |\n| `test_excel_normalizers_contract` | 间歇性（重跑通过） | **否** | - |\n\n### 3. P0 问题详解\n\n**`regression_auto_assign_persist_truthy_variants` 失败**：\n\n```python\n# tests/regression_auto_assign_persist_truthy_variants.py:75\ndef _patched_get_snapshot(self):  # 缺少 strict_mode 参数\n    snap = orig_get_snapshot(self)\n    setattr(snap, \"auto_assign_persist\", \"1\")\n    return snap\n```\n\n`schedule_service.py:284` 现在调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`，\n但 mock 不接受 `strict_mode` 关键字参数，导致 `TypeError`。\n\n**修复方案**：`def _patched_get_snapshot(self, **kwargs):` 或 `def _patched_get_snapshot(self, *, strict_mode=False):`",
      "status": "completed",
      "conclusion": "## 第一轮审查：引用链完整性 + 测试回归 ### 1. `strict_mode` 传播链完整性验证 追踪 strict_mode 从 Web 入口到最底层的完整传播链： ``` Web Route (request.form → _strict_mode_enabled) → scheduler_run.py / scheduler_week_plan.py → ScheduleService.run_schedule(strict_mode=...) → ConfigService.get_snapshot(strict_mode=...) → config_presets.get_snapshot_from_repo(strict_mode=...) → config_snapshot.build_schedule_config_snapshot(strict_mode=...) → _choice(strict=bool(strict_mode)) / _yes_no(strict=bool(strict_mode)) → schedule_optimizer.run_optimization(strict_mode=...) → _run_multi_start(strict_mode=...) → _schedule_with_optional_strict_mode(scheduler, strict_mode=...) → scheduler.schedule(strict_mode=...) → resolve_schedule_params(strict_mode=...) ``` **✅ 验证通过**：排产路径 strict_mode 从 web 到算法层完整贯穿。 ``` Web Route (process_parts.py → PartService.create(strict_mode=...)) → _parse_route_or_raise(strict_mode=...) → route_parser.parse(strict_mode=...) → _build_supplier_map() → 返回 (result, issues) → 工种未识别 → errors.append() [strict] / warnings.append() [non-strict] → 供应商缺失 → errors.append() [strict] / fallback 1.0 天 [non-strict] ``` **✅ 验证通过**：工艺路线解析路径 strict_mode 完整贯穿。 ``` Web Route (scheduler_excel_batches.py → BatchService.import_from_preview(strict_mode=...)) → batch_excel_import(strict_mode=...) → create_batch_from_template_no_tx(strict_mode=...) → _load_template_ops_with_fallback(strict_mode=...) → _invoke_template_resolver(strict_mode=...) → _default_template_resolver(strict_mode=...) → upsert_and_parse_no_tx(strict_mode=...) / reparse_and_save(strict_mode=...) ``` **✅ 验证通过**：批次导入路径 strict_mode 完整贯穿。 ### 2. 测试回归分析 运行全量测试 272 项，发现 **11 项失败**，其中： | 失败测试 | 根因 | 是否本次变更引起 | 严重度 | |---------|------|----------------|--------| | `regression_auto_assign_persist_truthy_variants` | mock `_patched_get_snapshot(self)` 缺少 `strict_mode` 参数 | **是** | P0 | | `test_file_size_limit` | 5 个文件超过 500 行 | **是** | P1 | | `test_no_silent_exception_swallow` | 新增 bare except 模式 | **是** | P1 | | `test_cyclomatic_complexity_threshold` | `_build_supplier_map` CC=19 等 | **是** | P1 | | `test_no_circular_service_dependencies` | `common ↔ scheduler` 循环 | 待确认 | P1 | | `regression_config_manual_markdown` | JS 渲染分支缺失 | **否**（预存在） | - | | `regression_skill_rank_mapping` | 预存在 | **否** | - | | `regression_startup_host_portfile` (×2) | 端口文件竞争 | **否** | - | | `test_team_pages_excel_smoke` | Windows 文件锁 | **否** | - | | `test_excel_normalizers_contract` | 间歇性（重跑通过） | **否** | - | ### 3. P0 问题详解 **`regression_auto_assign_persist_truthy_variants` 失败**： ```python # tests/regression_auto_assign_persist_truthy_variants.py:75 def _patched_get_snapshot(self): # 缺少 strict_mode 参数 snap = orig_get_snapshot(self) setattr(snap, \"auto_assign_persist\", \"1\") return snap ``` `schedule_service.py:284` 现在调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`， 但 mock 不接受 `strict_mode` 关键字参数，导致 `TypeError`。 **修复方案**：`def _patched_get_snapshot(self, **kwargs):` 或 `def _patched_get_snapshot(self, *, strict_mode=False):`",
      "evidenceFiles": [],
      "reviewedModules": [
        "tests/",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/config_presets.py",
        "core/services/scheduler/config_snapshot.py"
      ],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-02T06:52:15.407Z",
      "findingIds": [
        "F001",
        "F002",
        "F003",
        "F004"
      ]
    }
  ],
  "findings": [
    {
      "id": "F001",
      "severity": "high",
      "category": "test",
      "title": "mock 签名与实际 API 不兼容导致测试 TypeError",
      "description": "tests/regression_auto_assign_persist_truthy_variants.py 中 _patched_get_snapshot(self) 未接受 strict_mode 参数，schedule_service.py:284 现在会传 strict_mode=bool(strict_mode)，导致 TypeError。",
      "evidenceFiles": [
        "tests/regression_auto_assign_persist_truthy_variants.py",
        "core/services/scheduler/schedule_service.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "将 mock 签名改为 _patched_get_snapshot(self, **kwargs) 或 _patched_get_snapshot(self, *, strict_mode=False)"
    },
    {
      "id": "F002",
      "severity": "medium",
      "category": "maintainability",
      "title": "5 个核心文件超过 500 行限制",
      "description": "part_service.py(512), batch_service.py(508), schedule_optimizer.py(584), schedule_service.py(532), schedule_summary.py(648) 超过架构适配测试的 500 行限制。",
      "evidenceFiles": [
        "tests/test_architecture_fitness.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "添加到 known_oversize 白名单或进一步拆分。schedule_summary.py(648 行) 应优先考虑拆分。"
    },
    {
      "id": "F003",
      "severity": "medium",
      "category": "maintainability",
      "title": "新增 bare except 模式未更新白名单",
      "description": "external_group_service.py(+1), part_service.py(+1), route_parser.py(+1), supplier_service.py(+1), resource_pool_builder.py(+4) 新增了 except Exception: pass/continue 模式。",
      "evidenceFiles": [
        "tests/test_architecture_fitness.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "更新 test_architecture_fitness.py 的 known_violations 白名单并注明原因，或改用更精确的异常捕获。"
    },
    {
      "id": "F004",
      "severity": "medium",
      "category": "maintainability",
      "title": "新增高圈复杂度函数未加入白名单",
      "description": "route_parser._build_supplier_map CC=19, schedule_summary._compute_downtime_degradation CC=18, schedule_optimizer._compact_attempts CC=16。",
      "evidenceFiles": [
        "core/services/process/route_parser.py",
        "core/services/scheduler/schedule_summary.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "拆分或加入 known_violations 白名单。_build_supplier_map 的 CC=19 尤其需要考虑拆分。"
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->
