# 20260406_技术债务最终合并修复plan_深度review
- 日期: 2026-04-06
- 概述: 针对 .limcode/plans/20260405_技术债务最终合并修复plan.md 的三轮深度审查，重点核对目标可达性、结构边界、静默回退治理与潜在遗漏。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 20260406 技术债务最终合并修复plan 深度review

- 日期：2026-04-06
- 审查对象：`.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 审查范围：plan 目标可达性、任务拆分严谨性、与当前仓库事实一致性、静默回退/兼容桥治理是否充分、是否仍存在遗漏或执行断层。

> 本 review 采用增量留痕方式，按模块完成审查后逐步记录 milestone。

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_orchestrator.py, web/bootstrap/plugins.py, web/bootstrap/launcher.py, web/bootstrap/entrypoint.py, web/bootstrap/security.py, web/bootstrap/runtime_probe.py, .pre-commit-config.yaml, tests/test_architecture_fitness.py, web/routes/scheduler_batches.py, web/routes/process_parts.py, web/routes/personnel_pages.py, web/routes/equipment_pages.py, web/routes/system_logs.py
- 当前进度: 已记录 4 个里程碑；最新：m4-execution-granularity
- 里程碑总数: 4
- 已完成里程碑: 4
- 问题总数: 4
- 问题严重级别分布: 高 1 / 中 3 / 低 0
- 最新结论: 该 plan 已明显优于早期版本，主事实、路径和关键兼容桥识别基本准确，整体方向可达成大部分治理目标；但它还不足以直接作为“唯一权威执行 plan”无修订开工。当前至少还有四个需要先补齐的断口：一是 `web/bootstrap/` 其余启动链文件的静默回退治理范围仍明显缺失；二是 `ruff` 本地钩子仍可能脱离统一版本区间；三是治理台账尚无机器可读结构，难以真正成为门禁单一事实源；四是批次 1 前置的全量目录迁移偏重，不够简洁稳妥。结论上，建议先修订任务 1 与任务 3 的边界和退出条件，再启动实施。
- 下一步建议: 先补充 bootstrap 全面静默回退清单与接受风险边界；把本地 `ruff` 钩子并入统一门禁入口；为治理台账增加稳定结构块；将任务 3 改为热点先迁、其余延后，再把修订后的版本作为唯一执行 plan。
- 总体结论: 需要后续跟进

## 评审发现

### bootstrap 静默回退治理范围不完整

- ID: bootstrap-silent-fallback-scope-gap
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2-bootstrap-fallback-coverage
- 说明:

  plan 在任务 1 与任务 8 中把静默回退治理集中到 `factory.py`、`static_versioning.py` 与 `web/ui_mode.py`，但当前 `web/bootstrap/` 其余关键启动链文件仍保留大量异常吞没、默认值回退与空值返回路径。由于这些文件既未被纳入明确台账，也未进入批次退出条件，最终即使严格按 plan 执行，仓库仍可能保留一大片未治理的启动期/探测期静默回退面，和 plan 的总目标口径不一致。
- 建议:

  把 `web/bootstrap/` 再拆成“请求装配层”“启动入口层”“运行时探测层”“插件装载层”四类清单，至少把 `plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py` 明确纳入台账；若本轮不治理，必须在固定边界中单列接受风险并从“全部可修复问题已覆盖”的口径里剔除。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:305-316`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1211-1227`
  - `web/bootstrap/plugins.py:106-144#_build_plugin_config_reader`
  - `web/bootstrap/plugins.py:191-202#bootstrap_plugins`
  - `web/bootstrap/launcher.py:284-332#_read_key_value_file/_pid_exists`
  - `web/bootstrap/entrypoint.py:162-202#main`
  - `web/bootstrap/runtime_probe.py:48-90#read_runtime_host_port/read_runtime_db_path/delete_stale_runtime_files/probe_health`
  - `web/bootstrap/plugins.py`
  - `web/bootstrap/launcher.py`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/security.py`
  - `web/bootstrap/runtime_probe.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### ruff 本地钩子版本仍可漂移

- ID: ruff-hook-version-drift
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m3-quality-gate-closure
- 说明:

  plan 希望通过 `requirements-dev.txt` 锁定 `ruff>=0.15,<0.16` 来统一质量门禁，但当前本地提交钩子依然直接调用系统安装的 `ruff`。在这种形态下，开发者即使安装了要求区间内的开发依赖，也可能因为系统 PATH 中的另一个 `ruff` 版本而得到不同结果，和“本地与托管环境共享同一门禁入口”的目标不完全一致。
- 建议:

  把本地钩子改为调用同一门禁脚本或 `python -m ruff`，并在 `scripts/run_quality_gate.py` 中显式检查 `ruff --version` 是否落在计划区间，避免靠人工确认维持一致性。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:268-273`
  - `.pre-commit-config.yaml:3-10`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### 治理台账缺少机器可读结构定义

- ID: governance-ledger-schema-gap
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: m3-quality-gate-closure
- 说明:

  plan 要求架构门禁读取 `开发文档/技术债务治理台账.md` 来驱动白名单与退出条件，但没有规定该台账必须采用什么稳定结构。当前 `tests/test_architecture_fitness.py` 仍是硬编码白名单；如果后续直接从自由格式 markdown 抽取规则，极易产生脆弱的文本解析、文档与门禁双写，反而削弱“台账单一事实源”的目标。
- 建议:

  在台账 markdown 中预留稳定的机器可读块，例如表头固定的表格、前置元数据或受控代码块，然后让门禁只解析该结构块；否则应把白名单数据单独放到受版本控制的数据文件中，再由文档引用它。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:300-318`
  - `tests/test_architecture_fitness.py:44-70#_known_oversize_files/LOCAL_PARSE_HELPER_ALLOWLIST`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

### 批次 1 结构改造前置过重

- ID: batch1-structure-churn-too-heavy
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m4-execution-granularity
- 说明:

  plan 一方面要求遵守“最小实现、不要把目录迁移和行为改造混在同一小批次”，另一方面又在批次 1 同时推进请求级装配收口和调度/路由全量物理迁移。考虑到当前直接装配仍广泛散落在多个业务域，先做全量目录迁移会让后续每个行为任务都建立在新路径和大量导入修复之上，增加回归面和审查噪音，优雅性不足。
- 建议:

  把任务 3 改成两段：先只建子包和少量薄门面，优先迁主链热点与 scheduler 域；其余 process/personnel/equipment/system 的物理迁移延后到各自行为任务或任务 9 之后，避免在行为未收口前引入大规模路径 churn。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:122-135`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:420-434`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:452-705`
  - `web/routes/scheduler_batches.py:30-32#batches_page`
  - `web/routes/process_parts.py:92-95#create_part`
  - `web/routes/personnel_pages.py:21-23#list_page`
  - `web/routes/equipment_pages.py:120-122#list_page`
  - `web/routes/system_logs.py:27-29#logs_page`
  - `web/routes/scheduler_batches.py`
  - `web/routes/process_parts.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/system_logs.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`

## 评审里程碑

### m1-baseline-fact-check · 基线事实核对：plan 与当前仓库主事实基本对齐

- 状态: 已完成
- 记录时间: 2026-04-06T03:26:50.890Z
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_orchestrator.py
- 摘要:

  已核对 plan 中最关键的事实基线：`core/services/scheduler/` 当前确为 45 个平铺文件，`web/routes/` 当前确为 59 个平铺文件；`ScheduleService.__init__` 当前仍是 `(conn, logger=None, op_logger=None)` 并在内部平铺创建 10 个仓储实例；主链兼容桥 `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_schedule_with_optional_strict_mode`、`_scheduler_accepts_strict_mode`、`_normalize_optimizer_outcome`、`_merge_summary_warnings` 也都仍然存在。说明该 plan 在路径、数量、函数归属和关键断层识别上，已经比早期版本严谨很多，具备可执行基础。
- 结论:

  基线层面，plan 已基本建立在当前仓库真实状态之上，不存在明显的路径幻觉或主事实错位。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:458-461`
  - `core/services/scheduler/schedule_service.py:78-96#ScheduleService.__init__`
  - `core/services/scheduler/schedule_input_collector.py:184-255#_build_algo_operations_with_optional_outcome/_build_freeze_window_seed_with_optional_meta`
  - `core/services/scheduler/schedule_optimizer_steps.py:85-115#_scheduler_accepts_strict_mode/_schedule_with_optional_strict_mode`
  - `core/services/scheduler/schedule_orchestrator.py:53-100#_normalize_optimizer_outcome/_merge_summary_warnings`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/schedule_orchestrator.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  继续核对 plan 对静默回退与质量门禁的覆盖是否足够闭环。

### m2-bootstrap-fallback-coverage · 静默回退覆盖复核：bootstrap 面仍有未纳入 plan 的大面积回退路径

- 状态: 已完成
- 记录时间: 2026-04-06T03:27:15.850Z
- 已审模块: web/bootstrap/plugins.py, web/bootstrap/launcher.py, web/bootstrap/entrypoint.py, web/bootstrap/security.py, web/bootstrap/runtime_probe.py, .limcode/plans/20260405_技术债务最终合并修复plan.md
- 摘要:

  对 `web/bootstrap/` 进行抽样核对后发现，plan 虽然把 `factory.py:_open_db`、`factory.py:_perf_headers`、`static_versioning.py` 与 `web/ui_mode.py` 纳入治理，但当前仓库中仍有多个同层启动/探测/插件模块保留大量异常吞没或空值回退：`plugins.py` 继续在配置读取失败、插件加载失败后按默认开关或旧状态继续运行；`launcher.py` 在运行时文件读取、进程探测失败时直接回空字典/False；`entrypoint.py` 在清理启动错误、写入启动错误与环境变量设置等路径继续 `pass`；`security.py`、`runtime_probe.py` 也保留多处 `return None` / `pass` 式降级。当前 plan 的任务 1 和任务 8 没有把这些文件纳入明确的台账、专项门禁或批次退出条件。
- 结论:

  如果不补充 bootstrap 其余热点文件的治理范围，当前 plan 只能局部收口静默回退，无法支撑“全部可修复问题均有主任务归属”“没有过度兜底、静默回退”的最终口径。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:305-316`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1211-1227`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1591-1593`
  - `web/bootstrap/plugins.py:106-144#_build_plugin_config_reader`
  - `web/bootstrap/plugins.py:191-202#bootstrap_plugins`
  - `web/bootstrap/launcher.py:284-332#_read_key_value_file/_pid_exists`
  - `web/bootstrap/entrypoint.py:162-202#main`
  - `web/bootstrap/security.py:30-60#ensure_secret_key`
  - `web/bootstrap/runtime_probe.py:48-90#read_runtime_host_port/read_runtime_db_path/delete_stale_runtime_files/probe_health`
  - `web/bootstrap/plugins.py`
  - `web/bootstrap/launcher.py`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/security.py`
  - `web/bootstrap/runtime_probe.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  继续检查门禁与执行路径是否还有无法闭环之处，尤其是版本一致性和大规模目录迁移的风险。
- 问题:
  - [高] 可维护性: bootstrap 静默回退治理范围不完整

### m3-quality-gate-closure · 质量门禁闭环复核：版本一致性与台账单一事实源仍有设计缺口

- 状态: 已完成
- 记录时间: 2026-04-06T03:27:41.701Z
- 已审模块: .pre-commit-config.yaml, tests/test_architecture_fitness.py, .limcode/plans/20260405_技术债务最终合并修复plan.md
- 摘要:

  继续审看任务 1 后，发现 plan 对“统一质量门禁”的方向是对的，但还有两处闭环不足。其一，当前 `.pre-commit-config.yaml` 使用本机 `system` 方式直接执行 `ruff`，而 plan 仅在 `requirements-dev.txt` 锁版本并要求人工确认；若不补充统一调用入口或版本断言，本地提交钩子与门禁脚本仍可能跑出不同结果。其二，plan 要求 `tests/test_architecture_fitness.py` 读取治理台账并随批次收紧白名单，但没有规定 `开发文档/技术债务治理台账.md` 的机器可读结构；当前架构门禁仍是硬编码集合，若直接改为解析自由格式 markdown，很容易形成脆弱解析器或二次复制。
- 结论:

  任务 1 的治理方向正确，但要真正做到“统一质量门禁”和“台账为单一事实源”，还需要补一个可执行的结构约束层。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:268-273`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:300-318`
  - `.pre-commit-config.yaml:3-10`
  - `tests/test_architecture_fitness.py:44-70#_known_oversize_files/LOCAL_PARSE_HELPER_ALLOWLIST`
  - `.pre-commit-config.yaml`
  - `tests/test_architecture_fitness.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  最后再评估任务 2 与任务 3 的执行粒度是否过重，是否会抵消“最小实现”的目标。
- 问题:
  - [中] 测试: ruff 本地钩子版本仍可漂移
  - [中] 文档: 治理台账缺少机器可读结构定义

### m4-execution-granularity · 执行粒度复核：批次 1 的结构改造偏重，优雅性与最小实现不足

- 状态: 已完成
- 记录时间: 2026-04-06T03:28:32.157Z
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, web/routes/scheduler_batches.py, web/routes/process_parts.py, web/routes/personnel_pages.py, web/routes/equipment_pages.py, web/routes/system_logs.py
- 摘要:

  最后从实施顺序看，plan 的批次 1 同时要求完成请求级服务容器、调度仓储束、路由/service 大规模目录迁移、导入策略重写、路径敏感门禁修复和 `ruff` 例外迁移。问题在于，任务 2 仍允许大量历史 `Service(g.db, ...)` 装配只做登记，而任务 3 却前置了整个 `core/services/scheduler/` 与 `web/routes/` 的物理重组。这意味着在现有 45 个调度文件、59 个路由文件、且直接装配分布于 scheduler/process/personnel/equipment/system 多域的情况下，会先承受很大的拓扑 churn，再进入真正的行为收口。这样做不是不能落地，但和 plan 自己强调的“最小实现、不混批次”相比，显得偏重，也不够优雅。
- 结论:

  当前 plan 大方向可行，但若追求更简洁稳妥的落地路径，应把任务 3 从“全量迁移”改成“热点先迁 + 其余按行为任务顺带归位”，避免目录 churn 先于行为治理。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:122-135`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:351-354`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:420-434`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:452-705`
  - `web/routes/scheduler_batches.py:30-32#batches_page`
  - `web/routes/process_parts.py:92-95#create_part`
  - `web/routes/personnel_pages.py:21-23#list_page`
  - `web/routes/equipment_pages.py:120-122#list_page`
  - `web/routes/system_logs.py:27-29#logs_page`
  - `web/routes/scheduler_batches.py`
  - `web/routes/process_parts.py`
  - `web/routes/personnel_pages.py`
  - `web/routes/equipment_pages.py`
  - `web/routes/system_logs.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 下一步建议:

  汇总结论并给出是否建议执行前先修订 plan 的最终判断。
- 问题:
  - [中] 可维护性: 批次 1 结构改造前置过重

## 最终结论

该 plan 已明显优于早期版本，主事实、路径和关键兼容桥识别基本准确，整体方向可达成大部分治理目标；但它还不足以直接作为“唯一权威执行 plan”无修订开工。当前至少还有四个需要先补齐的断口：一是 `web/bootstrap/` 其余启动链文件的静默回退治理范围仍明显缺失；二是 `ruff` 本地钩子仍可能脱离统一版本区间；三是治理台账尚无机器可读结构，难以真正成为门禁单一事实源；四是批次 1 前置的全量目录迁移偏重，不够简洁稳妥。结论上，建议先修订任务 1 与任务 3 的边界和退出条件，再启动实施。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnmmkh9f-bchquu",
  "createdAt": "2026-04-06T00:00:00.000Z",
  "updatedAt": "2026-04-06T03:28:46.027Z",
  "finalizedAt": "2026-04-06T03:28:46.027Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "20260406_技术债务最终合并修复plan_深度review",
    "date": "2026-04-06",
    "overview": "针对 .limcode/plans/20260405_技术债务最终合并修复plan.md 的三轮深度审查，重点核对目标可达性、结构边界、静默回退治理与潜在遗漏。"
  },
  "scope": {
    "markdown": "# 20260406 技术债务最终合并修复plan 深度review\n\n- 日期：2026-04-06\n- 审查对象：`.limcode/plans/20260405_技术债务最终合并修复plan.md`\n- 审查范围：plan 目标可达性、任务拆分严谨性、与当前仓库事实一致性、静默回退/兼容桥治理是否充分、是否仍存在遗漏或执行断层。\n\n> 本 review 采用增量留痕方式，按模块完成审查后逐步记录 milestone。"
  },
  "summary": {
    "latestConclusion": "该 plan 已明显优于早期版本，主事实、路径和关键兼容桥识别基本准确，整体方向可达成大部分治理目标；但它还不足以直接作为“唯一权威执行 plan”无修订开工。当前至少还有四个需要先补齐的断口：一是 `web/bootstrap/` 其余启动链文件的静默回退治理范围仍明显缺失；二是 `ruff` 本地钩子仍可能脱离统一版本区间；三是治理台账尚无机器可读结构，难以真正成为门禁单一事实源；四是批次 1 前置的全量目录迁移偏重，不够简洁稳妥。结论上，建议先修订任务 1 与任务 3 的边界和退出条件，再启动实施。",
    "recommendedNextAction": "先补充 bootstrap 全面静默回退清单与接受风险边界；把本地 `ruff` 钩子并入统一门禁入口；为治理台账增加稳定结构块；将任务 3 改为热点先迁、其余延后，再把修订后的版本作为唯一执行 plan。",
    "reviewedModules": [
      ".limcode/plans/20260405_技术债务最终合并修复plan.md",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "web/bootstrap/plugins.py",
      "web/bootstrap/launcher.py",
      "web/bootstrap/entrypoint.py",
      "web/bootstrap/security.py",
      "web/bootstrap/runtime_probe.py",
      ".pre-commit-config.yaml",
      "tests/test_architecture_fitness.py",
      "web/routes/scheduler_batches.py",
      "web/routes/process_parts.py",
      "web/routes/personnel_pages.py",
      "web/routes/equipment_pages.py",
      "web/routes/system_logs.py"
    ]
  },
  "stats": {
    "totalMilestones": 4,
    "completedMilestones": 4,
    "totalFindings": 4,
    "severity": {
      "high": 1,
      "medium": 3,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "m1-baseline-fact-check",
      "title": "基线事实核对：plan 与当前仓库主事实基本对齐",
      "status": "completed",
      "recordedAt": "2026-04-06T03:26:50.890Z",
      "summaryMarkdown": "已核对 plan 中最关键的事实基线：`core/services/scheduler/` 当前确为 45 个平铺文件，`web/routes/` 当前确为 59 个平铺文件；`ScheduleService.__init__` 当前仍是 `(conn, logger=None, op_logger=None)` 并在内部平铺创建 10 个仓储实例；主链兼容桥 `_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta`、`_schedule_with_optional_strict_mode`、`_scheduler_accepts_strict_mode`、`_normalize_optimizer_outcome`、`_merge_summary_warnings` 也都仍然存在。说明该 plan 在路径、数量、函数归属和关键断层识别上，已经比早期版本严谨很多，具备可执行基础。",
      "conclusionMarkdown": "基线层面，plan 已基本建立在当前仓库真实状态之上，不存在明显的路径幻觉或主事实错位。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 458,
          "lineEnd": 461
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 78,
          "lineEnd": 96,
          "symbol": "ScheduleService.__init__"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 184,
          "lineEnd": 255,
          "symbol": "_build_algo_operations_with_optional_outcome/_build_freeze_window_seed_with_optional_meta"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 85,
          "lineEnd": 115,
          "symbol": "_scheduler_accepts_strict_mode/_schedule_with_optional_strict_mode"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 53,
          "lineEnd": 100,
          "symbol": "_normalize_optimizer_outcome/_merge_summary_warnings"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务最终合并修复plan.md",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_orchestrator.py"
      ],
      "recommendedNextAction": "继续核对 plan 对静默回退与质量门禁的覆盖是否足够闭环。",
      "findingIds": []
    },
    {
      "id": "m2-bootstrap-fallback-coverage",
      "title": "静默回退覆盖复核：bootstrap 面仍有未纳入 plan 的大面积回退路径",
      "status": "completed",
      "recordedAt": "2026-04-06T03:27:15.850Z",
      "summaryMarkdown": "对 `web/bootstrap/` 进行抽样核对后发现，plan 虽然把 `factory.py:_open_db`、`factory.py:_perf_headers`、`static_versioning.py` 与 `web/ui_mode.py` 纳入治理，但当前仓库中仍有多个同层启动/探测/插件模块保留大量异常吞没或空值回退：`plugins.py` 继续在配置读取失败、插件加载失败后按默认开关或旧状态继续运行；`launcher.py` 在运行时文件读取、进程探测失败时直接回空字典/False；`entrypoint.py` 在清理启动错误、写入启动错误与环境变量设置等路径继续 `pass`；`security.py`、`runtime_probe.py` 也保留多处 `return None` / `pass` 式降级。当前 plan 的任务 1 和任务 8 没有把这些文件纳入明确的台账、专项门禁或批次退出条件。",
      "conclusionMarkdown": "如果不补充 bootstrap 其余热点文件的治理范围，当前 plan 只能局部收口静默回退，无法支撑“全部可修复问题均有主任务归属”“没有过度兜底、静默回退”的最终口径。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 305,
          "lineEnd": 316
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1211,
          "lineEnd": 1227
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1591,
          "lineEnd": 1593
        },
        {
          "path": "web/bootstrap/plugins.py",
          "lineStart": 106,
          "lineEnd": 144,
          "symbol": "_build_plugin_config_reader"
        },
        {
          "path": "web/bootstrap/plugins.py",
          "lineStart": 191,
          "lineEnd": 202,
          "symbol": "bootstrap_plugins"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 284,
          "lineEnd": 332,
          "symbol": "_read_key_value_file/_pid_exists"
        },
        {
          "path": "web/bootstrap/entrypoint.py",
          "lineStart": 162,
          "lineEnd": 202,
          "symbol": "main"
        },
        {
          "path": "web/bootstrap/security.py",
          "lineStart": 30,
          "lineEnd": 60,
          "symbol": "ensure_secret_key"
        },
        {
          "path": "web/bootstrap/runtime_probe.py",
          "lineStart": 48,
          "lineEnd": 90,
          "symbol": "read_runtime_host_port/read_runtime_db_path/delete_stale_runtime_files/probe_health"
        },
        {
          "path": "web/bootstrap/plugins.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "web/bootstrap/security.py"
        },
        {
          "path": "web/bootstrap/runtime_probe.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        "web/bootstrap/plugins.py",
        "web/bootstrap/launcher.py",
        "web/bootstrap/entrypoint.py",
        "web/bootstrap/security.py",
        "web/bootstrap/runtime_probe.py",
        ".limcode/plans/20260405_技术债务最终合并修复plan.md"
      ],
      "recommendedNextAction": "继续检查门禁与执行路径是否还有无法闭环之处，尤其是版本一致性和大规模目录迁移的风险。",
      "findingIds": [
        "bootstrap-silent-fallback-scope-gap"
      ]
    },
    {
      "id": "m3-quality-gate-closure",
      "title": "质量门禁闭环复核：版本一致性与台账单一事实源仍有设计缺口",
      "status": "completed",
      "recordedAt": "2026-04-06T03:27:41.701Z",
      "summaryMarkdown": "继续审看任务 1 后，发现 plan 对“统一质量门禁”的方向是对的，但还有两处闭环不足。其一，当前 `.pre-commit-config.yaml` 使用本机 `system` 方式直接执行 `ruff`，而 plan 仅在 `requirements-dev.txt` 锁版本并要求人工确认；若不补充统一调用入口或版本断言，本地提交钩子与门禁脚本仍可能跑出不同结果。其二，plan 要求 `tests/test_architecture_fitness.py` 读取治理台账并随批次收紧白名单，但没有规定 `开发文档/技术债务治理台账.md` 的机器可读结构；当前架构门禁仍是硬编码集合，若直接改为解析自由格式 markdown，很容易形成脆弱解析器或二次复制。",
      "conclusionMarkdown": "任务 1 的治理方向正确，但要真正做到“统一质量门禁”和“台账为单一事实源”，还需要补一个可执行的结构约束层。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 268,
          "lineEnd": 273
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 300,
          "lineEnd": 318
        },
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 3,
          "lineEnd": 10
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 44,
          "lineEnd": 70,
          "symbol": "_known_oversize_files/LOCAL_PARSE_HELPER_ALLOWLIST"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        ".pre-commit-config.yaml",
        "tests/test_architecture_fitness.py",
        ".limcode/plans/20260405_技术债务最终合并修复plan.md"
      ],
      "recommendedNextAction": "最后再评估任务 2 与任务 3 的执行粒度是否过重，是否会抵消“最小实现”的目标。",
      "findingIds": [
        "ruff-hook-version-drift",
        "governance-ledger-schema-gap"
      ]
    },
    {
      "id": "m4-execution-granularity",
      "title": "执行粒度复核：批次 1 的结构改造偏重，优雅性与最小实现不足",
      "status": "completed",
      "recordedAt": "2026-04-06T03:28:32.157Z",
      "summaryMarkdown": "最后从实施顺序看，plan 的批次 1 同时要求完成请求级服务容器、调度仓储束、路由/service 大规模目录迁移、导入策略重写、路径敏感门禁修复和 `ruff` 例外迁移。问题在于，任务 2 仍允许大量历史 `Service(g.db, ...)` 装配只做登记，而任务 3 却前置了整个 `core/services/scheduler/` 与 `web/routes/` 的物理重组。这意味着在现有 45 个调度文件、59 个路由文件、且直接装配分布于 scheduler/process/personnel/equipment/system 多域的情况下，会先承受很大的拓扑 churn，再进入真正的行为收口。这样做不是不能落地，但和 plan 自己强调的“最小实现、不混批次”相比，显得偏重，也不够优雅。",
      "conclusionMarkdown": "当前 plan 大方向可行，但若追求更简洁稳妥的落地路径，应把任务 3 从“全量迁移”改成“热点先迁 + 其余按行为任务顺带归位”，避免目录 churn 先于行为治理。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 122,
          "lineEnd": 135
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 351,
          "lineEnd": 354
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 420,
          "lineEnd": 434
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 452,
          "lineEnd": 705
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 30,
          "lineEnd": 32,
          "symbol": "batches_page"
        },
        {
          "path": "web/routes/process_parts.py",
          "lineStart": 92,
          "lineEnd": 95,
          "symbol": "create_part"
        },
        {
          "path": "web/routes/personnel_pages.py",
          "lineStart": 21,
          "lineEnd": 23,
          "symbol": "list_page"
        },
        {
          "path": "web/routes/equipment_pages.py",
          "lineStart": 120,
          "lineEnd": 122,
          "symbol": "list_page"
        },
        {
          "path": "web/routes/system_logs.py",
          "lineStart": 27,
          "lineEnd": 29,
          "symbol": "logs_page"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务最终合并修复plan.md",
        "web/routes/scheduler_batches.py",
        "web/routes/process_parts.py",
        "web/routes/personnel_pages.py",
        "web/routes/equipment_pages.py",
        "web/routes/system_logs.py"
      ],
      "recommendedNextAction": "汇总结论并给出是否建议执行前先修订 plan 的最终判断。",
      "findingIds": [
        "batch1-structure-churn-too-heavy"
      ]
    }
  ],
  "findings": [
    {
      "id": "bootstrap-silent-fallback-scope-gap",
      "severity": "high",
      "category": "maintainability",
      "title": "bootstrap 静默回退治理范围不完整",
      "descriptionMarkdown": "plan 在任务 1 与任务 8 中把静默回退治理集中到 `factory.py`、`static_versioning.py` 与 `web/ui_mode.py`，但当前 `web/bootstrap/` 其余关键启动链文件仍保留大量异常吞没、默认值回退与空值返回路径。由于这些文件既未被纳入明确台账，也未进入批次退出条件，最终即使严格按 plan 执行，仓库仍可能保留一大片未治理的启动期/探测期静默回退面，和 plan 的总目标口径不一致。",
      "recommendationMarkdown": "把 `web/bootstrap/` 再拆成“请求装配层”“启动入口层”“运行时探测层”“插件装载层”四类清单，至少把 `plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py` 明确纳入台账；若本轮不治理，必须在固定边界中单列接受风险并从“全部可修复问题已覆盖”的口径里剔除。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 305,
          "lineEnd": 316
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1211,
          "lineEnd": 1227
        },
        {
          "path": "web/bootstrap/plugins.py",
          "lineStart": 106,
          "lineEnd": 144,
          "symbol": "_build_plugin_config_reader"
        },
        {
          "path": "web/bootstrap/plugins.py",
          "lineStart": 191,
          "lineEnd": 202,
          "symbol": "bootstrap_plugins"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 284,
          "lineEnd": 332,
          "symbol": "_read_key_value_file/_pid_exists"
        },
        {
          "path": "web/bootstrap/entrypoint.py",
          "lineStart": 162,
          "lineEnd": 202,
          "symbol": "main"
        },
        {
          "path": "web/bootstrap/runtime_probe.py",
          "lineStart": 48,
          "lineEnd": 90,
          "symbol": "read_runtime_host_port/read_runtime_db_path/delete_stale_runtime_files/probe_health"
        },
        {
          "path": "web/bootstrap/plugins.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "web/bootstrap/security.py"
        },
        {
          "path": "web/bootstrap/runtime_probe.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m2-bootstrap-fallback-coverage"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "ruff-hook-version-drift",
      "severity": "medium",
      "category": "test",
      "title": "ruff 本地钩子版本仍可漂移",
      "descriptionMarkdown": "plan 希望通过 `requirements-dev.txt` 锁定 `ruff>=0.15,<0.16` 来统一质量门禁，但当前本地提交钩子依然直接调用系统安装的 `ruff`。在这种形态下，开发者即使安装了要求区间内的开发依赖，也可能因为系统 PATH 中的另一个 `ruff` 版本而得到不同结果，和“本地与托管环境共享同一门禁入口”的目标不完全一致。",
      "recommendationMarkdown": "把本地钩子改为调用同一门禁脚本或 `python -m ruff`，并在 `scripts/run_quality_gate.py` 中显式检查 `ruff --version` 是否落在计划区间，避免靠人工确认维持一致性。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 268,
          "lineEnd": 273
        },
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 3,
          "lineEnd": 10
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m3-quality-gate-closure"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "governance-ledger-schema-gap",
      "severity": "medium",
      "category": "docs",
      "title": "治理台账缺少机器可读结构定义",
      "descriptionMarkdown": "plan 要求架构门禁读取 `开发文档/技术债务治理台账.md` 来驱动白名单与退出条件，但没有规定该台账必须采用什么稳定结构。当前 `tests/test_architecture_fitness.py` 仍是硬编码白名单；如果后续直接从自由格式 markdown 抽取规则，极易产生脆弱的文本解析、文档与门禁双写，反而削弱“台账单一事实源”的目标。",
      "recommendationMarkdown": "在台账 markdown 中预留稳定的机器可读块，例如表头固定的表格、前置元数据或受控代码块，然后让门禁只解析该结构块；否则应把白名单数据单独放到受版本控制的数据文件中，再由文档引用它。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 300,
          "lineEnd": 318
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 44,
          "lineEnd": 70,
          "symbol": "_known_oversize_files/LOCAL_PARSE_HELPER_ALLOWLIST"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m3-quality-gate-closure"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "batch1-structure-churn-too-heavy",
      "severity": "medium",
      "category": "maintainability",
      "title": "批次 1 结构改造前置过重",
      "descriptionMarkdown": "plan 一方面要求遵守“最小实现、不要把目录迁移和行为改造混在同一小批次”，另一方面又在批次 1 同时推进请求级装配收口和调度/路由全量物理迁移。考虑到当前直接装配仍广泛散落在多个业务域，先做全量目录迁移会让后续每个行为任务都建立在新路径和大量导入修复之上，增加回归面和审查噪音，优雅性不足。",
      "recommendationMarkdown": "把任务 3 改成两段：先只建子包和少量薄门面，优先迁主链热点与 scheduler 域；其余 process/personnel/equipment/system 的物理迁移延后到各自行为任务或任务 9 之后，避免在行为未收口前引入大规模路径 churn。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 122,
          "lineEnd": 135
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 420,
          "lineEnd": 434
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 452,
          "lineEnd": 705
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 30,
          "lineEnd": 32,
          "symbol": "batches_page"
        },
        {
          "path": "web/routes/process_parts.py",
          "lineStart": 92,
          "lineEnd": 95,
          "symbol": "create_part"
        },
        {
          "path": "web/routes/personnel_pages.py",
          "lineStart": 21,
          "lineEnd": 23,
          "symbol": "list_page"
        },
        {
          "path": "web/routes/equipment_pages.py",
          "lineStart": 120,
          "lineEnd": 122,
          "symbol": "list_page"
        },
        {
          "path": "web/routes/system_logs.py",
          "lineStart": 27,
          "lineEnd": 29,
          "symbol": "logs_page"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/process_parts.py"
        },
        {
          "path": "web/routes/personnel_pages.py"
        },
        {
          "path": "web/routes/equipment_pages.py"
        },
        {
          "path": "web/routes/system_logs.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "m4-execution-granularity"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:ad5ce321bda60f4a37c16a464cd4500b42f20660ec51c3a0dff8fd8d10359eaa",
    "generatedAt": "2026-04-06T03:28:46.027Z",
    "locale": "zh-CN"
  }
}
```
