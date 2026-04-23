# 2026-04-13 请求级容器与仓储束深度review
- 日期: 2026-04-13
- 概述: 针对当前未提交代码变更，完成三轮深度review、引用链检查、门禁验证与风险结论归档。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 深度review

## 范围
- 请求级服务容器：`web/bootstrap/request_services.py`
- 启动挂载与请求生命周期：`web/bootstrap/factory.py`
- UI 模式读取链：`web/ui_mode.py`
- 排产仓储束：`core/services/scheduler/repository_bundle.py`、`core/services/scheduler/schedule_service.py`
- 已切换路由：`web/routes/scheduler_*`、`web/routes/dashboard.py`、`web/routes/material.py`、`web/routes/system_history.py`
- 批次 Excel 基线辅助：`web/routes/scheduler_excel_batches.py`、`web/routes/scheduler_excel_batches_baseline.py`
- 门禁与架构适应度：`tools/quality_gate_*`、`tests/test_architecture_fitness.py`

## 证据
- `evidence/DeepReview/reference_trace.md`
- `audit/2026-04/_tmp_review/sp04_code.diff`
- `audit/2026-04/_tmp_review/sp04_tests.diff`
- `audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md`
- 运行验证：相关回归集合、`tests/test_architecture_fitness.py`、`scripts/run_quality_gate.py`

## 三轮审查摘要
1. 第一轮：核对目标、挂载时序、容器公开面、仓储束边界、已切换路由的服务取用方式。
2. 第二轮：沿 `factory._open_db -> g.services -> route -> service/query service` 与 `ScheduleService -> repository_bundle` 两条主链做参数/返回值/异常路径检查。
3. 第三轮：检查边界条件、失败路径、质量门禁、测试覆盖、静默回退与过度兜底。

## 结论
- 目标基本达成：请求级服务入口、排产仓储束、目标路由切换、门禁与回归整体闭环成立。
- 未发现会阻断合并的高风险逻辑 BUG。
- 发现 1 项需要尽快处理的问题：`core/services/scheduler/config_snapshot.py` 仍存在静态类型报错。
- 另有 2 项低风险关注点：一个是 `excel_backend_factory.get_excel_backend()` 对非法 `prefer` 值仍静默回落到 `OpenpyxlBackend`；另一个是 `scheduler_excel_batches_baseline.py` 仍通过 `part_svc.op_type_repo` / `supplier_repo` 读取数据，依赖了服务内部实现细节。

## 评审摘要

- 当前状态: 已完成
- 已审模块: web/bootstrap/request_services.py, web/bootstrap/factory.py, core/services/scheduler/repository_bundle.py, core/services/scheduler/schedule_service.py, web/ui_mode.py, web/routes/scheduler_analysis.py, web/routes/system_history.py, web/viewmodels/scheduler_analysis_vm.py, web/routes/scheduler_batches.py, web/routes/scheduler_batch_detail.py, web/routes/scheduler_run.py, web/routes/scheduler_week_plan.py, tests/test_architecture_fitness.py, core/services/scheduler/config_snapshot.py, core/services/common/excel_backend_factory.py, web/routes/scheduler_excel_batches_baseline.py
- 当前进度: 已记录 3 个里程碑；最新：round3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 0 / 中 1 / 低 2
- 最新结论: 三轮深度review完成。当前未提交改动总体上能够达成目标，请求级容器、仓储束、目标路由切换、质量门禁与回归验证均成立；未发现阻断合并的高风险 BUG。建议在后续小批次尽快处理 `config_snapshot` 的静态类型报错，并继续收紧 `get_excel_backend()` 的非法参数兜底与批次 Excel 基线辅助对 `PartService` 内部仓储的耦合。
- 下一步建议: 优先清理 `config_snapshot` 的类型报错；随后收紧 `get_excel_backend()` 的非法参数行为，并评估是否把批次 Excel 基线辅助改成稳定查询 façade。
- 总体结论: 有条件通过

## 评审发现

### config_snapshot 静态类型报错

- ID: cfg-snapshot-type-error
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  `core/services/scheduler/config_snapshot.py` 的 `_read_repo_raw_value()` 通过 `hasattr(record, "config_value")` 再读取 `record.config_value`。运行期逻辑没有明显问题，但当前工作区诊断已报出“无法访问类 object 的属性 config_value”。这会让类型检查持续失败，也会降低后续重构时的可维护性与可靠性。建议改成显式协议/类型收窄，或在读取处做明确 `cast`。
- 建议:

  用协议类型、`cast` 或明确的模型类型收窄替代 `hasattr + 动态属性访问`，把当前诊断清零。
- 证据:
  - `tests/test_architecture_fitness.py`
  - `scripts/run_quality_gate.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/common/excel_backend_factory.py`
  - `web/routes/scheduler_excel_batches_baseline.py`

### 非法 prefer 值仍静默回落

- ID: excel-backend-invalid-prefer-fallback
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  `core/services/common/excel_backend_factory.py:get_excel_backend()` 对 `prefer` 仅在 `openpyxl/auto/pandas` 三种值上做分支；若传入其他文本，会直接回落到 `OpenpyxlBackend()`，没有告警、没有异常。虽然当前调用点基本不传非法值，但这与本批“减少过度兜底”的方向不完全一致，一旦后续调用方传错参数，会被悄悄吃掉。
- 建议:

  对非法 `prefer` 值显式抛错，或至少记录 warning，并补一条对应回归。
- 证据:
  - `tests/test_architecture_fitness.py`
  - `scripts/run_quality_gate.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/common/excel_backend_factory.py`
  - `web/routes/scheduler_excel_batches_baseline.py`
  - `tests/regression_excel_backend_factory_observability.py`

### 基线辅助仍依赖服务内部仓储

- ID: baseline-helper-couples-partservice-internals
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  `web/routes/scheduler_excel_batches_baseline.py` 通过 `part_svc.op_type_repo` 与 `part_svc.supplier_repo` 读取快照。这样虽然没有直接跨到数据层导入，但仍把路由辅助逻辑绑定到了 `PartService` 的内部实现细节，而不是稳定的查询 façade。当前测试能守住现状，但未来若 `PartService` 收口内部仓储字段，这里会先脆断。
- 建议:

  后续可补一个只读查询 façade，避免在路由辅助模块里透传服务内部仓储对象。
- 证据:
  - `tests/test_architecture_fitness.py`
  - `scripts/run_quality_gate.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/common/excel_backend_factory.py`
  - `web/routes/scheduler_excel_batches_baseline.py`
  - `core/services/process/part_service.py`
  - `tests/regression_scheduler_excel_batches_helper_injection_contract.py`

## 评审里程碑

### round1 · 第一轮：结构与目标审查

- 状态: 已完成
- 记录时间: 2026-04-13T12:12:02.824Z
- 已审模块: web/bootstrap/request_services.py, web/bootstrap/factory.py, core/services/scheduler/repository_bundle.py, core/services/scheduler/schedule_service.py
- 摘要:

  核对了请求级容器、仓储束、挂载时序与目标路由切换范围。`factory._open_db()` 的时序为：白名单/维护短路 → 建立连接与操作日志 → 维护任务 → 挂载 `g.services`。`ScheduleService` 的公开构造签名未变化，仓储实例化被收口到 `build_schedule_repository_bundle(...)`，外部消费面仍保持 `svc.<repo>` 代理属性。
- 结论:

  整体目标达成，装配入口与仓储边界均已收口，没有发现目标偏离。
- 证据:
  - `web/bootstrap/request_services.py`
  - `web/bootstrap/factory.py`
  - `core/services/scheduler/repository_bundle.py`
  - `core/services/scheduler/schedule_service.py`
  - `audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md`
- 下一步建议:

  继续沿引用链检查路由取用、异常传播与门禁闭环。

### round2 · 第二轮：引用链与边界审查

- 状态: 已完成
- 记录时间: 2026-04-13T12:12:15.563Z
- 已审模块: web/ui_mode.py, web/routes/scheduler_analysis.py, web/routes/system_history.py, web/viewmodels/scheduler_analysis_vm.py, web/routes/scheduler_batches.py, web/routes/scheduler_batch_detail.py, web/routes/scheduler_run.py, web/routes/scheduler_week_plan.py
- 摘要:

  沿 `factory._open_db -> RequestServices -> g.services -> route` 与 `ScheduleService.__init__ -> build_schedule_repository_bundle(...) -> svc.<repo>` 两条主链核对了参数传递、返回值消费、异常传播与生命周期。目标路由当前均通过 `g.services` 取服务；`web/ui_mode.py` 不再自行构造 `SystemConfigService`，而是复用 `g.services.system_config_service` 并对请求上下文损坏显式抛错。`scheduler_analysis` 与 `system_history` 先解析 `result_summary`，再交给视图模型/模板消费，`scheduler_analysis_vm._safe_load_json()` 也已补上对字典入参的兼容。
- 结论:

  主引用链完整，关键边界一致，未发现参数漂移、返回值错用或事务边界破坏。
- 证据:
  - `evidence/DeepReview/reference_trace.md`
  - `web/ui_mode.py`
  - `web/routes/scheduler_analysis.py`
  - `web/routes/system_history.py`
  - `web/viewmodels/scheduler_analysis_vm.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_batch_detail.py`
  - `web/routes/scheduler_run.py`
  - `web/routes/scheduler_week_plan.py`
- 下一步建议:

  继续做边界条件、门禁、静态诊断与残余兜底行为检查。

### round3 · 第三轮：边界、门禁与回归审查

- 状态: 已完成
- 记录时间: 2026-04-13T12:12:43.534Z
- 已审模块: tests/test_architecture_fitness.py, core/services/scheduler/config_snapshot.py, core/services/common/excel_backend_factory.py, web/routes/scheduler_excel_batches_baseline.py
- 摘要:

  完成了边界条件、门禁与回归核验：执行了 98 条相关回归用例，随后执行 `scripts/run_quality_gate.py`，结果全部通过。请求级直接装配门禁与 `_repos` 漂移门禁当前均为 0，说明本批改动没有重新引入越层直连。但在静态诊断与长期维护层面，仍发现 1 项中风险和 2 项低风险问题。
- 结论:

  功能目标、质量门禁与主要回归均已达成；当前可以合并，但建议在后续小批次尽快清理类型报错并继续收紧残余兜底与内部耦合。
- 证据:
  - `tests/test_architecture_fitness.py`
  - `scripts/run_quality_gate.py`
  - `core/services/scheduler/config_snapshot.py`
  - `core/services/common/excel_backend_factory.py`
  - `web/routes/scheduler_excel_batches_baseline.py`
- 下一步建议:

  优先清理 `config_snapshot` 的类型报错；随后收紧 `get_excel_backend()` 的非法参数行为，并评估是否把批次 Excel 基线辅助改成稳定查询 façade。
- 问题:
  - [中] 可维护性: config_snapshot 静态类型报错
  - [低] 可维护性: 非法 prefer 值仍静默回落
  - [低] 可维护性: 基线辅助仍依赖服务内部仓储

## 最终结论

三轮深度review完成。当前未提交改动总体上能够达成目标，请求级容器、仓储束、目标路由切换、质量门禁与回归验证均成立；未发现阻断合并的高风险 BUG。建议在后续小批次尽快处理 `config_snapshot` 的静态类型报错，并继续收紧 `get_excel_backend()` 的非法参数兜底与批次 Excel 基线辅助对 `PartService` 内部仓储的耦合。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnx5jk33-18d68m",
  "createdAt": "2026-04-13T00:00:00.000Z",
  "updatedAt": "2026-04-13T12:13:01.483Z",
  "finalizedAt": "2026-04-13T12:13:01.483Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "2026-04-13 请求级容器与仓储束深度review",
    "date": "2026-04-13",
    "overview": "针对当前未提交代码变更，完成三轮深度review、引用链检查、门禁验证与风险结论归档。"
  },
  "scope": {
    "markdown": "# 深度review\n\n## 范围\n- 请求级服务容器：`web/bootstrap/request_services.py`\n- 启动挂载与请求生命周期：`web/bootstrap/factory.py`\n- UI 模式读取链：`web/ui_mode.py`\n- 排产仓储束：`core/services/scheduler/repository_bundle.py`、`core/services/scheduler/schedule_service.py`\n- 已切换路由：`web/routes/scheduler_*`、`web/routes/dashboard.py`、`web/routes/material.py`、`web/routes/system_history.py`\n- 批次 Excel 基线辅助：`web/routes/scheduler_excel_batches.py`、`web/routes/scheduler_excel_batches_baseline.py`\n- 门禁与架构适应度：`tools/quality_gate_*`、`tests/test_architecture_fitness.py`\n\n## 证据\n- `evidence/DeepReview/reference_trace.md`\n- `audit/2026-04/_tmp_review/sp04_code.diff`\n- `audit/2026-04/_tmp_review/sp04_tests.diff`\n- `audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md`\n- 运行验证：相关回归集合、`tests/test_architecture_fitness.py`、`scripts/run_quality_gate.py`\n\n## 三轮审查摘要\n1. 第一轮：核对目标、挂载时序、容器公开面、仓储束边界、已切换路由的服务取用方式。\n2. 第二轮：沿 `factory._open_db -> g.services -> route -> service/query service` 与 `ScheduleService -> repository_bundle` 两条主链做参数/返回值/异常路径检查。\n3. 第三轮：检查边界条件、失败路径、质量门禁、测试覆盖、静默回退与过度兜底。\n\n## 结论\n- 目标基本达成：请求级服务入口、排产仓储束、目标路由切换、门禁与回归整体闭环成立。\n- 未发现会阻断合并的高风险逻辑 BUG。\n- 发现 1 项需要尽快处理的问题：`core/services/scheduler/config_snapshot.py` 仍存在静态类型报错。\n- 另有 2 项低风险关注点：一个是 `excel_backend_factory.get_excel_backend()` 对非法 `prefer` 值仍静默回落到 `OpenpyxlBackend`；另一个是 `scheduler_excel_batches_baseline.py` 仍通过 `part_svc.op_type_repo` / `supplier_repo` 读取数据，依赖了服务内部实现细节。"
  },
  "summary": {
    "latestConclusion": "三轮深度review完成。当前未提交改动总体上能够达成目标，请求级容器、仓储束、目标路由切换、质量门禁与回归验证均成立；未发现阻断合并的高风险 BUG。建议在后续小批次尽快处理 `config_snapshot` 的静态类型报错，并继续收紧 `get_excel_backend()` 的非法参数兜底与批次 Excel 基线辅助对 `PartService` 内部仓储的耦合。",
    "recommendedNextAction": "优先清理 `config_snapshot` 的类型报错；随后收紧 `get_excel_backend()` 的非法参数行为，并评估是否把批次 Excel 基线辅助改成稳定查询 façade。",
    "reviewedModules": [
      "web/bootstrap/request_services.py",
      "web/bootstrap/factory.py",
      "core/services/scheduler/repository_bundle.py",
      "core/services/scheduler/schedule_service.py",
      "web/ui_mode.py",
      "web/routes/scheduler_analysis.py",
      "web/routes/system_history.py",
      "web/viewmodels/scheduler_analysis_vm.py",
      "web/routes/scheduler_batches.py",
      "web/routes/scheduler_batch_detail.py",
      "web/routes/scheduler_run.py",
      "web/routes/scheduler_week_plan.py",
      "tests/test_architecture_fitness.py",
      "core/services/scheduler/config_snapshot.py",
      "core/services/common/excel_backend_factory.py",
      "web/routes/scheduler_excel_batches_baseline.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 2
    }
  },
  "milestones": [
    {
      "id": "round1",
      "title": "第一轮：结构与目标审查",
      "status": "completed",
      "recordedAt": "2026-04-13T12:12:02.824Z",
      "summaryMarkdown": "核对了请求级容器、仓储束、挂载时序与目标路由切换范围。`factory._open_db()` 的时序为：白名单/维护短路 → 建立连接与操作日志 → 维护任务 → 挂载 `g.services`。`ScheduleService` 的公开构造签名未变化，仓储实例化被收口到 `build_schedule_repository_bundle(...)`，外部消费面仍保持 `svc.<repo>` 代理属性。",
      "conclusionMarkdown": "整体目标达成，装配入口与仓储边界均已收口，没有发现目标偏离。",
      "evidence": [
        {
          "path": "web/bootstrap/request_services.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "core/services/scheduler/repository_bundle.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md"
        }
      ],
      "reviewedModules": [
        "web/bootstrap/request_services.py",
        "web/bootstrap/factory.py",
        "core/services/scheduler/repository_bundle.py",
        "core/services/scheduler/schedule_service.py"
      ],
      "recommendedNextAction": "继续沿引用链检查路由取用、异常传播与门禁闭环。",
      "findingIds": []
    },
    {
      "id": "round2",
      "title": "第二轮：引用链与边界审查",
      "status": "completed",
      "recordedAt": "2026-04-13T12:12:15.563Z",
      "summaryMarkdown": "沿 `factory._open_db -> RequestServices -> g.services -> route` 与 `ScheduleService.__init__ -> build_schedule_repository_bundle(...) -> svc.<repo>` 两条主链核对了参数传递、返回值消费、异常传播与生命周期。目标路由当前均通过 `g.services` 取服务；`web/ui_mode.py` 不再自行构造 `SystemConfigService`，而是复用 `g.services.system_config_service` 并对请求上下文损坏显式抛错。`scheduler_analysis` 与 `system_history` 先解析 `result_summary`，再交给视图模型/模板消费，`scheduler_analysis_vm._safe_load_json()` 也已补上对字典入参的兼容。",
      "conclusionMarkdown": "主引用链完整，关键边界一致，未发现参数漂移、返回值错用或事务边界破坏。",
      "evidence": [
        {
          "path": "evidence/DeepReview/reference_trace.md"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "web/routes/scheduler_analysis.py"
        },
        {
          "path": "web/routes/system_history.py"
        },
        {
          "path": "web/viewmodels/scheduler_analysis_vm.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/scheduler_batch_detail.py"
        },
        {
          "path": "web/routes/scheduler_run.py"
        },
        {
          "path": "web/routes/scheduler_week_plan.py"
        }
      ],
      "reviewedModules": [
        "web/ui_mode.py",
        "web/routes/scheduler_analysis.py",
        "web/routes/system_history.py",
        "web/viewmodels/scheduler_analysis_vm.py",
        "web/routes/scheduler_batches.py",
        "web/routes/scheduler_batch_detail.py",
        "web/routes/scheduler_run.py",
        "web/routes/scheduler_week_plan.py"
      ],
      "recommendedNextAction": "继续做边界条件、门禁、静态诊断与残余兜底行为检查。",
      "findingIds": []
    },
    {
      "id": "round3",
      "title": "第三轮：边界、门禁与回归审查",
      "status": "completed",
      "recordedAt": "2026-04-13T12:12:43.534Z",
      "summaryMarkdown": "完成了边界条件、门禁与回归核验：执行了 98 条相关回归用例，随后执行 `scripts/run_quality_gate.py`，结果全部通过。请求级直接装配门禁与 `_repos` 漂移门禁当前均为 0，说明本批改动没有重新引入越层直连。但在静态诊断与长期维护层面，仍发现 1 项中风险和 2 项低风险问题。",
      "conclusionMarkdown": "功能目标、质量门禁与主要回归均已达成；当前可以合并，但建议在后续小批次尽快清理类型报错并继续收紧残余兜底与内部耦合。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "scripts/run_quality_gate.py"
        },
        {
          "path": "core/services/scheduler/config_snapshot.py"
        },
        {
          "path": "core/services/common/excel_backend_factory.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches_baseline.py"
        }
      ],
      "reviewedModules": [
        "tests/test_architecture_fitness.py",
        "core/services/scheduler/config_snapshot.py",
        "core/services/common/excel_backend_factory.py",
        "web/routes/scheduler_excel_batches_baseline.py"
      ],
      "recommendedNextAction": "优先清理 `config_snapshot` 的类型报错；随后收紧 `get_excel_backend()` 的非法参数行为，并评估是否把批次 Excel 基线辅助改成稳定查询 façade。",
      "findingIds": [
        "cfg-snapshot-type-error",
        "excel-backend-invalid-prefer-fallback",
        "baseline-helper-couples-partservice-internals"
      ]
    }
  ],
  "findings": [
    {
      "id": "cfg-snapshot-type-error",
      "severity": "medium",
      "category": "maintainability",
      "title": "config_snapshot 静态类型报错",
      "descriptionMarkdown": "`core/services/scheduler/config_snapshot.py` 的 `_read_repo_raw_value()` 通过 `hasattr(record, \"config_value\")` 再读取 `record.config_value`。运行期逻辑没有明显问题，但当前工作区诊断已报出“无法访问类 object 的属性 config_value”。这会让类型检查持续失败，也会降低后续重构时的可维护性与可靠性。建议改成显式协议/类型收窄，或在读取处做明确 `cast`。",
      "recommendationMarkdown": "用协议类型、`cast` 或明确的模型类型收窄替代 `hasattr + 动态属性访问`，把当前诊断清零。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "scripts/run_quality_gate.py"
        },
        {
          "path": "core/services/scheduler/config_snapshot.py"
        },
        {
          "path": "core/services/common/excel_backend_factory.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches_baseline.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "excel-backend-invalid-prefer-fallback",
      "severity": "low",
      "category": "maintainability",
      "title": "非法 prefer 值仍静默回落",
      "descriptionMarkdown": "`core/services/common/excel_backend_factory.py:get_excel_backend()` 对 `prefer` 仅在 `openpyxl/auto/pandas` 三种值上做分支；若传入其他文本，会直接回落到 `OpenpyxlBackend()`，没有告警、没有异常。虽然当前调用点基本不传非法值，但这与本批“减少过度兜底”的方向不完全一致，一旦后续调用方传错参数，会被悄悄吃掉。",
      "recommendationMarkdown": "对非法 `prefer` 值显式抛错，或至少记录 warning，并补一条对应回归。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "scripts/run_quality_gate.py"
        },
        {
          "path": "core/services/scheduler/config_snapshot.py"
        },
        {
          "path": "core/services/common/excel_backend_factory.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches_baseline.py"
        },
        {
          "path": "tests/regression_excel_backend_factory_observability.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "baseline-helper-couples-partservice-internals",
      "severity": "low",
      "category": "maintainability",
      "title": "基线辅助仍依赖服务内部仓储",
      "descriptionMarkdown": "`web/routes/scheduler_excel_batches_baseline.py` 通过 `part_svc.op_type_repo` 与 `part_svc.supplier_repo` 读取快照。这样虽然没有直接跨到数据层导入，但仍把路由辅助逻辑绑定到了 `PartService` 的内部实现细节，而不是稳定的查询 façade。当前测试能守住现状，但未来若 `PartService` 收口内部仓储字段，这里会先脆断。",
      "recommendationMarkdown": "后续可补一个只读查询 façade，避免在路由辅助模块里透传服务内部仓储对象。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "scripts/run_quality_gate.py"
        },
        {
          "path": "core/services/scheduler/config_snapshot.py"
        },
        {
          "path": "core/services/common/excel_backend_factory.py"
        },
        {
          "path": "web/routes/scheduler_excel_batches_baseline.py"
        },
        {
          "path": "core/services/process/part_service.py"
        },
        {
          "path": "tests/regression_scheduler_excel_batches_helper_injection_contract.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:df1a6725e141ba37ddf02b815423247f490c0ce22f2ee46f4775ea42d915085e",
    "generatedAt": "2026-04-13T12:13:01.483Z",
    "locale": "zh-CN"
  }
}
```
