# SP04 请求级容器与仓储束 深度review
- 日期: 2026-04-11
- 概述: 针对当前未提交改动做三轮深度审查，覆盖请求级容器、仓储束、调度相关路由、界面模式读取链与质量门禁。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# SP04 请求级容器与仓储束 深度review

## 审查范围
- 请求级容器：`web/bootstrap/request_services.py`
- 启动挂载：`web/bootstrap/factory.py`
- 界面模式读取链：`web/ui_mode.py`、`core/services/system/system_config_service.py`
- 调度仓储束：`core/services/scheduler/repository_bundle.py`、`core/services/scheduler/schedule_service.py`
- 已切换路由与两处自定义测试工厂
- 质量门禁与架构适应度：`tools/quality_gate_*`、`tests/test_architecture_fitness.py`

## 审查方法
1. 读取未提交差异与交接说明，确认改动目标。
2. 追踪关键调用链：Route → `g.services` → Service → Repository / 配置仓储。
3. 跑针对性回归与质量门禁，校验实现与门禁一致性。

## 当前结论
- 主目标基本达成：目标路由已统一改为请求级容器取服务，`ScheduleService` 的仓储创建已收口到仓储束，`web/ui_mode.py` 不再直接构造系统配置服务。
- 重点回归已通过：相关回归、架构适应度、治理台账校验、质量门禁均通过。
- 仍发现少量需要关注的实现细节，见后续 milestone。

## 评审摘要

- 当前状态: 已完成
- 已审模块: web/bootstrap/request_services.py, web/bootstrap/factory.py, web/ui_mode.py, core/services/scheduler/repository_bundle.py, core/services/scheduler/schedule_service.py, web/routes/scheduler_excel_batches.py, core/services/system/system_config_service.py, tools/quality_gate_shared.py, tools/quality_gate_operations.py, tests/run_real_db_replay_e2e.py, tests/run_complex_excel_cases_e2e.py, tests/regression_factory_request_lifecycle_observability.py, tests/test_architecture_fitness.py, web/routes/dashboard.py, web/routes/material.py, web/routes/scheduler_batches.py, web/routes/scheduler_batch_detail.py, web/routes/scheduler_config.py, web/routes/scheduler_gantt.py, web/routes/scheduler_ops.py, web/routes/scheduler_run.py, web/routes/scheduler_week_plan.py, tools/quality_gate_scan.py, tests/test_ui_mode.py
- 当前进度: 已记录 3 个里程碑；最新：round3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 2
- 问题严重级别分布: 高 0 / 中 1 / 低 1
- 最新结论: 三轮审查后，当前未提交改动已经基本达成“请求级容器收口 + 调度仓储束收口 + 目标路由切换 + 界面模式读取链去直构造”的目的，主调用链清晰、公开签名稳定、实现总体简洁，没有发现会直接阻断当前目标达成的高风险 BUG。与此同时，仍有两处值得尽快处理的细节：其一，质量门禁对保留 helper 的放行粒度过粗，会削弱后续新增直接装配点的识别能力；其二，两处自定义测试工厂尚未完全继承正式工厂的容器不变量守卫，测试环境约束略松于正式环境。整体判断为可继续推进，但建议在后续提交前顺手收紧这两处，以避免规则漂移。
- 下一步建议: 优先收紧 helper 放行规则，其次补齐两处测试工厂的不变量守卫；完成后重跑当前已通过的定向回归、治理台账校验与质量门禁。
- 总体结论: 有条件通过

## 评审发现

### helper 放行粒度过粗

- ID: helper-allowlist-too-broad
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  当前对 `scheduler_excel_batches.py` 中保留 helper 的门禁豁免，仅按 `(path, target)` 做匹配，没有约束具体符号、行号或出现次数。现状虽然只豁免两处 `get_batch_row_validate_and_normalize(g.db, ...)`，但同文件未来若再新增同名调用，会被同一条放行规则直接吞掉，门禁无法第一时间暴露新增直接装配点。这会削弱本批“目标文件不再直接装配”的核心约束。
- 建议:

  把放行规则收紧到“路径 + 符号 + 行号/次数”至少三元之一，或在门禁中显式断言当前仅允许 2 处命中，避免未来新增调用被同名豁免一并放过。
- 证据:
  - `web/routes/scheduler_excel_batches.py:197#excel_batches_preview`
  - `web/routes/scheduler_excel_batches.py:286#excel_batches_confirm`
  - `tools/quality_gate_shared.py:59-64#REQUEST_SERVICE_TARGET_ALLOWED_HELPERS`
  - `tools/quality_gate_operations.py:392-407#architecture_request_service_direct_assembly_entries`
  - `core/services/common/excel_validators.py:87-93#get_batch_row_validate_and_normalize`
  - `web/routes/scheduler_excel_batches.py`
  - `tools/quality_gate_shared.py`
  - `tools/quality_gate_operations.py`
  - `core/services/common/excel_validators.py`

### 自定义测试工厂缺少容器不变量守卫

- ID: test-factory-missing-invariant-guard
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  正式工厂与 `web/ui_mode.py` 已明确建立“请求上下文存在 `g.db` 时，必须同步存在 `g.services`”这一不变量；但两处自定义测试工厂的 `_open_db` 仍只在 `db` 缺失时补挂容器，没有对“已有 `g.db` 但缺少 `g.services`”做 fail-fast。这样会让测试环境比正式环境更宽松，后续若脚本或夹具错误预置了 `g.db`，测试未必能第一时间暴露上下文不一致。
- 建议:

  把两处自定义测试工厂的 `_open_db` 与正式工厂对齐，至少补上“已有 `g.db` 但缺少 `g.services` 就抛错”的守卫；更理想的做法是抽出可复用的测试工厂辅助函数，避免再次漂移。
- 证据:
  - `web/bootstrap/factory.py:297-321#_open_db`
  - `web/ui_mode.py:220-228#_read_ui_mode_from_db`
  - `tests/run_real_db_replay_e2e.py:223-239#_open_db`
  - `tests/run_complex_excel_cases_e2e.py:279-295#_open_db`
  - `tests/regression_factory_request_lifecycle_observability.py:324-339#test_open_db_raises_when_db_preseeded_but_services_missing`
  - `tests/regression_request_services_contract.py`
  - `tests/regression_request_services_failure_propagation.py`
  - `tests/regression_request_services_lazy_construction.py`
  - `tests/test_ui_mode.py`
  - `tests/regression_factory_request_lifecycle_observability.py`
  - `tests/test_architecture_fitness.py`
  - `tests/run_real_db_replay_e2e.py`
  - `tests/run_complex_excel_cases_e2e.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`

## 评审里程碑

### round1 · 第一轮：变更目标与装配边界核对

- 状态: 已完成
- 记录时间: 2026-04-11T16:21:25.893Z
- 已审模块: web/bootstrap/request_services.py, web/bootstrap/factory.py, web/ui_mode.py, core/services/scheduler/repository_bundle.py, core/services/scheduler/schedule_service.py
- 摘要:

  - 结合未提交差异、交接说明与当前实现，确认本批目标是把指定调度路由与 `web/ui_mode.py` 收口到请求级容器 `g.services`，并把 `ScheduleService` 的仓储创建收口到 `repository_bundle`。
  - 实际代码已完成主路径收口：`web/bootstrap/factory.py` 负责挂载 `RequestServices`；目标路由改为通过 `g.services` 取服务；`web/ui_mode.py` 改为经 `g.services.system_config_service` 读取配置；`ScheduleService.__init__` 改为通过 `build_schedule_repository_bundle(...)` 初始化仓储。
  - 结论：主目标达成，结构方向正确，公开签名保持稳定，没有把 `_repos` 暴露为新的公开消费口。
- 结论:

  第一轮确认改动目标与落点一致，主设计方向成立。
- 证据:
  - `audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md:11-24`
  - `web/bootstrap/request_services.py:17-33#REQUEST_SERVICES_PUBLIC_ATTRS`
  - `web/bootstrap/factory.py:297-321#_open_db`
  - `web/ui_mode.py:220-244#_read_ui_mode_from_db`
  - `core/services/scheduler/repository_bundle.py:20-46#ScheduleRepositoryBundle`
  - `core/services/scheduler/schedule_service.py:67-83#ScheduleService.__init__`
  - `audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md`
  - `web/bootstrap/request_services.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
  - `core/services/scheduler/repository_bundle.py`
  - `core/services/scheduler/schedule_service.py`
- 下一步建议:

  继续第二轮，逐条检查引用链与门禁实现是否存在漏口。

### round2 · 第二轮：引用链与门禁实现深挖

- 状态: 已完成
- 记录时间: 2026-04-11T16:21:48.924Z
- 已审模块: web/routes/scheduler_excel_batches.py, web/ui_mode.py, core/services/system/system_config_service.py, tools/quality_gate_shared.py, tools/quality_gate_operations.py
- 摘要:

  - 已逐条核对关键引用链：
    - `scheduler_* / dashboard / material` 目标路由 → `g.services.<service>` → 对应服务构造；
    - `web/ui_mode.py:get_ui_mode()` → `_read_ui_mode_from_db()` → `g.services.system_config_service.get_value()/has_key()` → `SystemConfigRepository.get_value()/get()`；
    - `ScheduleService.__init__` → `build_schedule_repository_bundle()` → 各仓储实例。
  - 运行结果说明主链路没有签名漂移，服务构造参数与既有公开签名保持一致，仓储束也没有扩散新的 `_repos` 消费面。
  - 但在质量门禁里发现一个真实漏口：针对 `scheduler_excel_batches.py` 的 helper 放行采用“路径 + 目标名”粗粒度匹配，未来只要同文件再新增同名 helper 调用，哪怕位置和语义已变化，也会被继续静默放行，削弱“禁止直接装配”的门禁目标。
- 结论:

  第二轮确认主调用链一致，但质量门禁放行粒度过粗，属于需要尽快收紧的中风险问题。
- 证据:
  - `web/routes/scheduler_excel_batches.py:197#excel_batches_preview`
  - `web/routes/scheduler_excel_batches.py:286#excel_batches_confirm`
  - `tools/quality_gate_shared.py:59-64#REQUEST_SERVICE_TARGET_ALLOWED_HELPERS`
  - `tools/quality_gate_operations.py:392-407#architecture_request_service_direct_assembly_entries`
  - `core/services/common/excel_validators.py:87-93#get_batch_row_validate_and_normalize`
  - `web/routes/scheduler_excel_batches.py`
  - `tools/quality_gate_shared.py`
  - `tools/quality_gate_operations.py`
  - `core/services/common/excel_validators.py`
- 下一步建议:

  进入第三轮，结合真实执行结果与测试工厂实现，检查边界一致性与回归覆盖是否还有漏口。
- 问题:
  - [中] 测试: helper 放行粒度过粗

### round3 · 第三轮：执行验证与边界一致性复核

- 状态: 已完成
- 记录时间: 2026-04-11T16:22:33.165Z
- 已审模块: tests/run_real_db_replay_e2e.py, tests/run_complex_excel_cases_e2e.py, tests/regression_factory_request_lifecycle_observability.py, tests/test_architecture_fitness.py
- 摘要:

  - 已执行聚焦回归：请求级容器契约、懒构造、失败传播、界面模式读取、相关路由契约、质量门禁扫描契约、架构适应度，共 65 项全部通过。
  - 已执行 `python scripts/sync_debt_ledger.py check` 与 `python scripts/run_quality_gate.py`，治理台账、架构门禁与质量门禁均通过。
  - 继续对比主工厂与两处自定义测试工厂后，发现还有一个低风险一致性缺口：正式工厂在 `g.db` 已存在但 `g.services` 缺失时会立即 fail-fast，`web/ui_mode.py` 也依赖这个不变量；但两处自定义测试工厂仅在 `db` 不存在时挂载容器，没有同步这条守卫，导致测试环境的请求上下文约束比正式环境更松。
- 结论:

  第三轮确认当前改动可达成目标且整体实现较为干净，但仍建议补齐测试工厂不变量守卫，并尽快收紧 helper 放行规则。
- 证据:
  - `web/bootstrap/factory.py:297-321#_open_db`
  - `web/ui_mode.py:220-228#_read_ui_mode_from_db`
  - `tests/run_real_db_replay_e2e.py:223-239#_open_db`
  - `tests/run_complex_excel_cases_e2e.py:279-295#_open_db`
  - `tests/regression_factory_request_lifecycle_observability.py:324-339#test_open_db_raises_when_db_preseeded_but_services_missing`
  - `tests/test_architecture_fitness.py:442-465#test_request_service_target_files_no_direct_assembly`
  - `tests/regression_request_services_contract.py`
  - `tests/regression_request_services_failure_propagation.py`
  - `tests/regression_request_services_lazy_construction.py`
  - `tests/test_ui_mode.py`
  - `tests/regression_factory_request_lifecycle_observability.py`
  - `tests/test_architecture_fitness.py`
  - `tests/run_real_db_replay_e2e.py`
  - `tests/run_complex_excel_cases_e2e.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
- 下一步建议:

  按优先级先修复 helper 放行粒度，再补齐两处测试工厂守卫；修复后重跑当前已通过的定向回归与质量门禁。
- 问题:
  - [低] 测试: 自定义测试工厂缺少容器不变量守卫

## 最终结论

三轮审查后，当前未提交改动已经基本达成“请求级容器收口 + 调度仓储束收口 + 目标路由切换 + 界面模式读取链去直构造”的目的，主调用链清晰、公开签名稳定、实现总体简洁，没有发现会直接阻断当前目标达成的高风险 BUG。与此同时，仍有两处值得尽快处理的细节：其一，质量门禁对保留 helper 的放行粒度过粗，会削弱后续新增直接装配点的识别能力；其二，两处自定义测试工厂尚未完全继承正式工厂的容器不变量守卫，测试环境约束略松于正式环境。整体判断为可继续推进，但建议在后续提交前顺手收紧这两处，以避免规则漂移。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnujklxy-41auvg",
  "createdAt": "2026-04-11T00:00:00.000Z",
  "updatedAt": "2026-04-11T16:22:47.183Z",
  "finalizedAt": "2026-04-11T16:22:47.183Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "SP04 请求级容器与仓储束 深度review",
    "date": "2026-04-11",
    "overview": "针对当前未提交改动做三轮深度审查，覆盖请求级容器、仓储束、调度相关路由、界面模式读取链与质量门禁。"
  },
  "scope": {
    "markdown": "# SP04 请求级容器与仓储束 深度review\n\n## 审查范围\n- 请求级容器：`web/bootstrap/request_services.py`\n- 启动挂载：`web/bootstrap/factory.py`\n- 界面模式读取链：`web/ui_mode.py`、`core/services/system/system_config_service.py`\n- 调度仓储束：`core/services/scheduler/repository_bundle.py`、`core/services/scheduler/schedule_service.py`\n- 已切换路由与两处自定义测试工厂\n- 质量门禁与架构适应度：`tools/quality_gate_*`、`tests/test_architecture_fitness.py`\n\n## 审查方法\n1. 读取未提交差异与交接说明，确认改动目标。\n2. 追踪关键调用链：Route → `g.services` → Service → Repository / 配置仓储。\n3. 跑针对性回归与质量门禁，校验实现与门禁一致性。\n\n## 当前结论\n- 主目标基本达成：目标路由已统一改为请求级容器取服务，`ScheduleService` 的仓储创建已收口到仓储束，`web/ui_mode.py` 不再直接构造系统配置服务。\n- 重点回归已通过：相关回归、架构适应度、治理台账校验、质量门禁均通过。\n- 仍发现少量需要关注的实现细节，见后续 milestone。"
  },
  "summary": {
    "latestConclusion": "三轮审查后，当前未提交改动已经基本达成“请求级容器收口 + 调度仓储束收口 + 目标路由切换 + 界面模式读取链去直构造”的目的，主调用链清晰、公开签名稳定、实现总体简洁，没有发现会直接阻断当前目标达成的高风险 BUG。与此同时，仍有两处值得尽快处理的细节：其一，质量门禁对保留 helper 的放行粒度过粗，会削弱后续新增直接装配点的识别能力；其二，两处自定义测试工厂尚未完全继承正式工厂的容器不变量守卫，测试环境约束略松于正式环境。整体判断为可继续推进，但建议在后续提交前顺手收紧这两处，以避免规则漂移。",
    "recommendedNextAction": "优先收紧 helper 放行规则，其次补齐两处测试工厂的不变量守卫；完成后重跑当前已通过的定向回归、治理台账校验与质量门禁。",
    "reviewedModules": [
      "web/bootstrap/request_services.py",
      "web/bootstrap/factory.py",
      "web/ui_mode.py",
      "core/services/scheduler/repository_bundle.py",
      "core/services/scheduler/schedule_service.py",
      "web/routes/scheduler_excel_batches.py",
      "core/services/system/system_config_service.py",
      "tools/quality_gate_shared.py",
      "tools/quality_gate_operations.py",
      "tests/run_real_db_replay_e2e.py",
      "tests/run_complex_excel_cases_e2e.py",
      "tests/regression_factory_request_lifecycle_observability.py",
      "tests/test_architecture_fitness.py",
      "web/routes/dashboard.py",
      "web/routes/material.py",
      "web/routes/scheduler_batches.py",
      "web/routes/scheduler_batch_detail.py",
      "web/routes/scheduler_config.py",
      "web/routes/scheduler_gantt.py",
      "web/routes/scheduler_ops.py",
      "web/routes/scheduler_run.py",
      "web/routes/scheduler_week_plan.py",
      "tools/quality_gate_scan.py",
      "tests/test_ui_mode.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 2,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "round1",
      "title": "第一轮：变更目标与装配边界核对",
      "status": "completed",
      "recordedAt": "2026-04-11T16:21:25.893Z",
      "summaryMarkdown": "- 结合未提交差异、交接说明与当前实现，确认本批目标是把指定调度路由与 `web/ui_mode.py` 收口到请求级容器 `g.services`，并把 `ScheduleService` 的仓储创建收口到 `repository_bundle`。\n- 实际代码已完成主路径收口：`web/bootstrap/factory.py` 负责挂载 `RequestServices`；目标路由改为通过 `g.services` 取服务；`web/ui_mode.py` 改为经 `g.services.system_config_service` 读取配置；`ScheduleService.__init__` 改为通过 `build_schedule_repository_bundle(...)` 初始化仓储。\n- 结论：主目标达成，结构方向正确，公开签名保持稳定，没有把 `_repos` 暴露为新的公开消费口。",
      "conclusionMarkdown": "第一轮确认改动目标与落点一致，主设计方向成立。",
      "evidence": [
        {
          "path": "audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md",
          "lineStart": 11,
          "lineEnd": 24
        },
        {
          "path": "web/bootstrap/request_services.py",
          "lineStart": 17,
          "lineEnd": 33,
          "symbol": "REQUEST_SERVICES_PUBLIC_ATTRS"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 297,
          "lineEnd": 321,
          "symbol": "_open_db"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 220,
          "lineEnd": 244,
          "symbol": "_read_ui_mode_from_db"
        },
        {
          "path": "core/services/scheduler/repository_bundle.py",
          "lineStart": 20,
          "lineEnd": 46,
          "symbol": "ScheduleRepositoryBundle"
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 67,
          "lineEnd": 83,
          "symbol": "ScheduleService.__init__"
        },
        {
          "path": "audit/2026-04/20260411_sp04_请求级容器与仓储束交接说明.md"
        },
        {
          "path": "web/bootstrap/request_services.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "core/services/scheduler/repository_bundle.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "reviewedModules": [
        "web/bootstrap/request_services.py",
        "web/bootstrap/factory.py",
        "web/ui_mode.py",
        "core/services/scheduler/repository_bundle.py",
        "core/services/scheduler/schedule_service.py"
      ],
      "recommendedNextAction": "继续第二轮，逐条检查引用链与门禁实现是否存在漏口。",
      "findingIds": []
    },
    {
      "id": "round2",
      "title": "第二轮：引用链与门禁实现深挖",
      "status": "completed",
      "recordedAt": "2026-04-11T16:21:48.924Z",
      "summaryMarkdown": "- 已逐条核对关键引用链：\n  - `scheduler_* / dashboard / material` 目标路由 → `g.services.<service>` → 对应服务构造；\n  - `web/ui_mode.py:get_ui_mode()` → `_read_ui_mode_from_db()` → `g.services.system_config_service.get_value()/has_key()` → `SystemConfigRepository.get_value()/get()`；\n  - `ScheduleService.__init__` → `build_schedule_repository_bundle()` → 各仓储实例。\n- 运行结果说明主链路没有签名漂移，服务构造参数与既有公开签名保持一致，仓储束也没有扩散新的 `_repos` 消费面。\n- 但在质量门禁里发现一个真实漏口：针对 `scheduler_excel_batches.py` 的 helper 放行采用“路径 + 目标名”粗粒度匹配，未来只要同文件再新增同名 helper 调用，哪怕位置和语义已变化，也会被继续静默放行，削弱“禁止直接装配”的门禁目标。",
      "conclusionMarkdown": "第二轮确认主调用链一致，但质量门禁放行粒度过粗，属于需要尽快收紧的中风险问题。",
      "evidence": [
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 197,
          "lineEnd": 197,
          "symbol": "excel_batches_preview"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 286,
          "lineEnd": 286,
          "symbol": "excel_batches_confirm"
        },
        {
          "path": "tools/quality_gate_shared.py",
          "lineStart": 59,
          "lineEnd": 64,
          "symbol": "REQUEST_SERVICE_TARGET_ALLOWED_HELPERS"
        },
        {
          "path": "tools/quality_gate_operations.py",
          "lineStart": 392,
          "lineEnd": 407,
          "symbol": "architecture_request_service_direct_assembly_entries"
        },
        {
          "path": "core/services/common/excel_validators.py",
          "lineStart": 87,
          "lineEnd": 93,
          "symbol": "get_batch_row_validate_and_normalize"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "tools/quality_gate_shared.py"
        },
        {
          "path": "tools/quality_gate_operations.py"
        },
        {
          "path": "core/services/common/excel_validators.py"
        }
      ],
      "reviewedModules": [
        "web/routes/scheduler_excel_batches.py",
        "web/ui_mode.py",
        "core/services/system/system_config_service.py",
        "tools/quality_gate_shared.py",
        "tools/quality_gate_operations.py"
      ],
      "recommendedNextAction": "进入第三轮，结合真实执行结果与测试工厂实现，检查边界一致性与回归覆盖是否还有漏口。",
      "findingIds": [
        "helper-allowlist-too-broad"
      ]
    },
    {
      "id": "round3",
      "title": "第三轮：执行验证与边界一致性复核",
      "status": "completed",
      "recordedAt": "2026-04-11T16:22:33.165Z",
      "summaryMarkdown": "- 已执行聚焦回归：请求级容器契约、懒构造、失败传播、界面模式读取、相关路由契约、质量门禁扫描契约、架构适应度，共 65 项全部通过。\n- 已执行 `python scripts/sync_debt_ledger.py check` 与 `python scripts/run_quality_gate.py`，治理台账、架构门禁与质量门禁均通过。\n- 继续对比主工厂与两处自定义测试工厂后，发现还有一个低风险一致性缺口：正式工厂在 `g.db` 已存在但 `g.services` 缺失时会立即 fail-fast，`web/ui_mode.py` 也依赖这个不变量；但两处自定义测试工厂仅在 `db` 不存在时挂载容器，没有同步这条守卫，导致测试环境的请求上下文约束比正式环境更松。",
      "conclusionMarkdown": "第三轮确认当前改动可达成目标且整体实现较为干净，但仍建议补齐测试工厂不变量守卫，并尽快收紧 helper 放行规则。",
      "evidence": [
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 297,
          "lineEnd": 321,
          "symbol": "_open_db"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 220,
          "lineEnd": 228,
          "symbol": "_read_ui_mode_from_db"
        },
        {
          "path": "tests/run_real_db_replay_e2e.py",
          "lineStart": 223,
          "lineEnd": 239,
          "symbol": "_open_db"
        },
        {
          "path": "tests/run_complex_excel_cases_e2e.py",
          "lineStart": 279,
          "lineEnd": 295,
          "symbol": "_open_db"
        },
        {
          "path": "tests/regression_factory_request_lifecycle_observability.py",
          "lineStart": 324,
          "lineEnd": 339,
          "symbol": "test_open_db_raises_when_db_preseeded_but_services_missing"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 442,
          "lineEnd": 465,
          "symbol": "test_request_service_target_files_no_direct_assembly"
        },
        {
          "path": "tests/regression_request_services_contract.py"
        },
        {
          "path": "tests/regression_request_services_failure_propagation.py"
        },
        {
          "path": "tests/regression_request_services_lazy_construction.py"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/regression_factory_request_lifecycle_observability.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/run_real_db_replay_e2e.py"
        },
        {
          "path": "tests/run_complex_excel_cases_e2e.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        }
      ],
      "reviewedModules": [
        "tests/run_real_db_replay_e2e.py",
        "tests/run_complex_excel_cases_e2e.py",
        "tests/regression_factory_request_lifecycle_observability.py",
        "tests/test_architecture_fitness.py"
      ],
      "recommendedNextAction": "按优先级先修复 helper 放行粒度，再补齐两处测试工厂守卫；修复后重跑当前已通过的定向回归与质量门禁。",
      "findingIds": [
        "test-factory-missing-invariant-guard"
      ]
    }
  ],
  "findings": [
    {
      "id": "helper-allowlist-too-broad",
      "severity": "medium",
      "category": "test",
      "title": "helper 放行粒度过粗",
      "descriptionMarkdown": "当前对 `scheduler_excel_batches.py` 中保留 helper 的门禁豁免，仅按 `(path, target)` 做匹配，没有约束具体符号、行号或出现次数。现状虽然只豁免两处 `get_batch_row_validate_and_normalize(g.db, ...)`，但同文件未来若再新增同名调用，会被同一条放行规则直接吞掉，门禁无法第一时间暴露新增直接装配点。这会削弱本批“目标文件不再直接装配”的核心约束。",
      "recommendationMarkdown": "把放行规则收紧到“路径 + 符号 + 行号/次数”至少三元之一，或在门禁中显式断言当前仅允许 2 处命中，避免未来新增调用被同名豁免一并放过。",
      "evidence": [
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 197,
          "lineEnd": 197,
          "symbol": "excel_batches_preview"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py",
          "lineStart": 286,
          "lineEnd": 286,
          "symbol": "excel_batches_confirm"
        },
        {
          "path": "tools/quality_gate_shared.py",
          "lineStart": 59,
          "lineEnd": 64,
          "symbol": "REQUEST_SERVICE_TARGET_ALLOWED_HELPERS"
        },
        {
          "path": "tools/quality_gate_operations.py",
          "lineStart": 392,
          "lineEnd": 407,
          "symbol": "architecture_request_service_direct_assembly_entries"
        },
        {
          "path": "core/services/common/excel_validators.py",
          "lineStart": 87,
          "lineEnd": 93,
          "symbol": "get_batch_row_validate_and_normalize"
        },
        {
          "path": "web/routes/scheduler_excel_batches.py"
        },
        {
          "path": "tools/quality_gate_shared.py"
        },
        {
          "path": "tools/quality_gate_operations.py"
        },
        {
          "path": "core/services/common/excel_validators.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "test-factory-missing-invariant-guard",
      "severity": "low",
      "category": "test",
      "title": "自定义测试工厂缺少容器不变量守卫",
      "descriptionMarkdown": "正式工厂与 `web/ui_mode.py` 已明确建立“请求上下文存在 `g.db` 时，必须同步存在 `g.services`”这一不变量；但两处自定义测试工厂的 `_open_db` 仍只在 `db` 缺失时补挂容器，没有对“已有 `g.db` 但缺少 `g.services`”做 fail-fast。这样会让测试环境比正式环境更宽松，后续若脚本或夹具错误预置了 `g.db`，测试未必能第一时间暴露上下文不一致。",
      "recommendationMarkdown": "把两处自定义测试工厂的 `_open_db` 与正式工厂对齐，至少补上“已有 `g.db` 但缺少 `g.services` 就抛错”的守卫；更理想的做法是抽出可复用的测试工厂辅助函数，避免再次漂移。",
      "evidence": [
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 297,
          "lineEnd": 321,
          "symbol": "_open_db"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 220,
          "lineEnd": 228,
          "symbol": "_read_ui_mode_from_db"
        },
        {
          "path": "tests/run_real_db_replay_e2e.py",
          "lineStart": 223,
          "lineEnd": 239,
          "symbol": "_open_db"
        },
        {
          "path": "tests/run_complex_excel_cases_e2e.py",
          "lineStart": 279,
          "lineEnd": 295,
          "symbol": "_open_db"
        },
        {
          "path": "tests/regression_factory_request_lifecycle_observability.py",
          "lineStart": 324,
          "lineEnd": 339,
          "symbol": "test_open_db_raises_when_db_preseeded_but_services_missing"
        },
        {
          "path": "tests/regression_request_services_contract.py"
        },
        {
          "path": "tests/regression_request_services_failure_propagation.py"
        },
        {
          "path": "tests/regression_request_services_lazy_construction.py"
        },
        {
          "path": "tests/test_ui_mode.py"
        },
        {
          "path": "tests/regression_factory_request_lifecycle_observability.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "tests/run_real_db_replay_e2e.py"
        },
        {
          "path": "tests/run_complex_excel_cases_e2e.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
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
    "bodyHash": "sha256:c1e75bb0cd44b9242881b3617875009fdadbb72b0352a59027607d7c90f54845",
    "generatedAt": "2026-04-11T16:22:47.183Z",
    "locale": "zh-CN"
  }
}
```
