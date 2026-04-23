# 2026-04-06 技术债务最终合并修复plan 深度review（本轮）
- 日期: 2026-04-06
- 概述: 审查 .limcode/plans/20260405_技术债务最终合并修复plan.md 的可达成性、结构严谨性、静默回退治理充分性与潜在BUG/断层风险。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 2026-04-06 技术债务最终合并修复plan 深度review（本轮）

- 日期：2026-04-06
- 目标文件：`.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 审查范围：plan 与当前仓库结构、关键实现入口、门禁/测试/调度主链事实的一致性
- 审查关注点：
  1. 是否能达成既定治理目的
  2. 方案是否优雅、简洁，是否存在过度抽象或过度兜底
  3. 是否仍有静默回退、执行断层、路径漂移、验证口径失配
  4. 是否存在潜在BUG、循环依赖、验证不可执行或完成判定失真风险

> 按审查序列逐步记录 milestone，不等待全量读完后一次性下结论。

## 评审摘要

- 当前状态: 已完成
- 已审模块: 任务1 工程基线与门禁, 任务2 请求级装配与仓储束, 任务3 目录骨架与路由门面, 任务4 配置单一事实源, 任务5 主链上下文与兼容桥, 任务6 算法边界与 BUG 收口, 任务7 数据基础设施拆分, 任务8 页面/模板/静态资源协议, 任务9 测试分层与覆盖率, 任务10 文档/证据/审计轨道, 全局执行顺序与退出条件
- 当前进度: 已记录 3 个里程碑；最新：m3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 4
- 问题严重级别分布: 高 1 / 中 3 / 低 0
- 最新结论: 该 plan 已具备较高可执行度，任务顺序、批次边界、静默回退治理意识、目录迁移节奏、主链兼容桥收口与前端协议收口方向总体正确，也基本避免了新的过度抽象；但在直接开工前，仍需先补齐 4 个关键断层：1）任务 2 必须明确 `ScheduleService` 构造器与 `svc.<repo>` 平铺属性的稳定迁移策略；2）任务 1 必须把 `factory.py` 的 `_open_db/_close_db/_perf_headers` 从“样本点”升级为明确清零或接受风险对象；3）任务 4 必须显式清理 `schedule_optimizer.py:_cfg_choices()` 与 `ConfigService.VALID_*` 直读链，避免配置第二事实源残留；4）任务 7/8 必须补入与物理迁移同步的架构白名单路径更新动作。补齐后，本 plan 可以作为唯一权威 plan 执行；未补齐前，不建议无条件开工。
- 下一步建议: 先将 4 个 open finding 回写到 plan，并优先修补任务 2 的构造器/仓储属性策略与任务 1 的 factory 样本点归属；随后再按批次 0 → 1 → 2 顺序实施。
- 总体结论: 有条件通过

## 评审发现

### 任务2低估 ScheduleService 收口爆炸半径

- ID: task2-schedule-service-blast-radius
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  plan 要求 `ScheduleService` 从内部平铺创建 10 个仓储实例改为接收 `RepositoryBundle`，并把内部使用从 `self.xxx_repo` 切到 `self.repos.xxx_repo`。但当前代码与测试/脚本并不只依赖构造器 `(conn, logger=None, op_logger=None)`，还在大量位置直接读取或覆写 `svc.batch_repo`、`svc.op_repo`、`svc.history_repo` 等属性。仅代表性证据就包括：`tests/regression_schedule_service_passes_algo_stats_to_summary.py` 直接访问 `svc.batch_repo/op_repo`，`tests/regression_schedule_service_reschedulable_contract.py` 直接覆写 `svc.op_repo`，`tests/regression_schedule_input_collector_contract.py` 直接调用 `collect_schedule_run_input(...)` 并传入现有注入签名，而 `core/services/scheduler/operation_edit_service.py`、`schedule_input_collector.py` 等内部 helper 也广泛依赖 `svc.<repo>` 形态。若按 plan 字面执行而不保留稳定公开构造签名与仓储访问策略，批次 1 会同时打断路由、内部 helper、回归测试与脚本入口；若临时加兼容桥，又会和 plan 的“禁止新增临时兼容桥”原则冲突。
- 建议:

  任务 2 应显式补一条稳定策略：要么保留 `ScheduleService(conn, logger=None, op_logger=None)` 作为正式公开构造边界，并把 `RepositoryBundle` 作为内部可选注入；要么在 plan 中列出必须同步迁改的全部调用点与 `svc.<repo>` 访问位点，并说明这些属性是保留为正式代理属性还是一次性全面替换。两者必须二选一，不能留给执行者临场判断。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/test_architecture_fitness.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/operation_edit_service.py`
  - `tests/regression_schedule_service_passes_algo_stats_to_summary.py`
  - `tests/regression_schedule_service_reschedulable_contract.py`
  - `tests/regression_schedule_input_collector_contract.py`

### 任务1对 factory 样本点仍偏门禁化

- ID: task1-factory-sample-points-not-cleared
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  plan 已要求把 `_open_db/_close_db/_perf_headers` 作为 `web/bootstrap/` 样本点登记并做扫描命中验证，但真正的代码治理步骤 6.5 只明确优先收口 `plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py`、`_maintenance_gate_response` 与 `runtime_base_dir()`。当前 `web/bootstrap/factory.py` 仍保留多处关键静默回退：`_open_db` 中 `g._aps_req_started` 失败后回退为 `None`、请求路径解析失败后 `pass`；`_close_db` 中 `db.close()` 异常吞没；`_perf_headers` 中 `_is_prefetch_req()` 失败直接 `return False`、外层异常直接 `pass`。如果任务 1 只做到“建台账 + 扩门禁 + 样本验证”，而没有把这些样本点明确归类为本任务就地清零、可观测接受风险或后续具体批次，就会出现批次 0 已宣称完成、但启动/请求装配主路径仍保留静默回退热点的假收口。
- 建议:

  任务 1 应把 `_open_db`、`_close_db`、`_perf_headers` 从“样本点”提升为明确执行对象：逐项声明是任务 1 本批清零、接受风险保留（含日志/事件要求），还是绑定到后续唯一批次；并把该归属写进步骤 6.5 或完成判定，而不是仅依赖台账自由填写。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/test_architecture_fitness.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/operation_edit_service.py`
  - `tests/regression_schedule_service_passes_algo_stats_to_summary.py`
  - `tests/regression_schedule_service_reschedulable_contract.py`

### 任务4仍遗漏算法侧 VALID_* 第二事实源

- ID: task4-cfg-choices-second-source
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  任务 4 已明确要求清理 `schedule_optimizer.py` 里的 `_cfg_value()`、`_norm_text()`，并让快照/校验/预设/页面元数据统一走注册表；但当前优化器里还有一条独立的合法值来源：`_cfg_choices()` 会直接从 `cfg_svc.VALID_STRATEGIES / VALID_DISPATCH_MODES / VALID_DISPATCH_RULES` 读取合法集合，并在缺值时回退到本地元组。`ConfigService` 侧这些 `VALID_*` 常量与 `get_available_strategies()` 也仍是独立定义。这意味着即使 `_cfg_value/_norm_text` 被删掉，只要 `_cfg_choices()` 保留，优化器仍可能和注册表/页面元数据/校验器维持两套合法值来源，任务 4 的“单一事实源”目标就无法完全落地。
- 建议:

  任务 4 需要显式补一条步骤与完成判定：`schedule_optimizer.py:_cfg_choices()`、`cfg_svc.VALID_*` 直读、以及与之等价的本地回退元组必须同步退出；允许保留 `ConfigService` 对外常量/方法作为注册表投影，但其值必须由注册表生成，不能继续手写维护。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/config_service.py`
  - `web/bootstrap/static_versioning.py`
  - `tests/test_architecture_fitness.py`

### 任务7/8缺少后续物理迁移的白名单路径同步步骤

- ID: task7-8-arch-whitelist-path-drift
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  当前 `tests/test_architecture_fitness.py` 仍硬编码了大量路径敏感条目，包括 `core/infrastructure/backup.py`、`core/infrastructure/database.py` 的静默回退白名单，以及 `web/routes/system_backup.py` 等旧路由文件路径。任务 3 已为 scheduler 域迁移补了路径敏感测试修正步骤，但任务 7 还会继续拆 `backup.py/database.py`，任务 8 还会继续把 `system/process/personnel/equipment` 物理迁入 `web/routes/domains/**`；这两个后续迁移批次却没有像任务 3 那样显式要求同步更新 `tests/test_architecture_fitness.py` 中的超长文件白名单、静默回退白名单、复杂度白名单和同类路径清单。由于任务 7/8 验证命令都仍要求跑架构门禁，这会在执行时形成明显的路径漂移断层。
- 建议:

  把任务 3 的“路径敏感白名单同步修正”抽成一个横向固定动作，并复制到任务 7、任务 8：凡发生物理迁移或热点拆分的批次，都必须同批更新/移除 `tests/test_architecture_fitness.py`（任务 9 后对应 `tests/architecture/test_architecture_fitness.py`）中的相关路径白名单与门禁断言。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/config_service.py`
  - `web/bootstrap/static_versioning.py`
  - `tests/test_architecture_fitness.py`

## 评审里程碑

### m1 · 完成任务 1-3 与现状代码入口的一致性审查

- 状态: 已完成
- 记录时间: 2026-04-06T13:14:00.124Z
- 已审模块: 任务1 工程基线与门禁, 任务2 请求级装配与仓储束, 任务3 目录骨架与路由门面
- 摘要:

  已核对工程基线、门禁、请求级装配与目录骨架相关 plan 段落，并对照当前 `tests/test_architecture_fitness.py`、`web/bootstrap/factory.py`、`web/ui_mode.py`、`core/services/scheduler/schedule_service.py`、`web/routes/scheduler.py` 等关键入口验证事实。

  结论：本 plan 在任务顺序、禁止项、路径冲突规避、`web/bootstrap/` 治理意识和路由迁移节奏上明显比前序版本更成熟，整体方向正确；但任务 1 与任务 2 仍各有一个会影响落地质量的关键断层：
  1. 任务 2 低估了 `ScheduleService` 构造器与平铺仓储属性的真实爆炸半径；
  2. 任务 1 对 `factory.py` 样本点更多停留在“记账+门禁验证”，对 `_open_db/_close_db/_perf_headers` 的实际清零动作还不够落地。

  这两个问题如果不先补强，执行者很容易在批次 0/1 形成“门禁已升级、核心热点仍保留静默回退”或“仓储束已引入、但测试/脚本/内部 helper 大面积断裂”的中间态。
- 结论:

  任务 1-3 的总体治理方向成立，但批次 0/1 仍需先补两处执行级断层：一是 `factory.py` 样本点的清零归属，二是 `ScheduleService` 构造器与仓储属性的兼容/迁移策略。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/test_architecture_fitness.py`
  - `web/bootstrap/factory.py`
  - `web/ui_mode.py`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`
  - `core/services/scheduler/operation_edit_service.py`
  - `tests/regression_schedule_service_passes_algo_stats_to_summary.py`
  - `tests/regression_schedule_service_reschedulable_contract.py`
- 下一步建议:

  继续审查任务 4-8，重点核对配置单一事实源、主链兼容桥收口、算法边界与静态资源/双模板治理是否仍存在未被 plan 明确覆盖的第二事实源或契约松散点。
- 问题:
  - [高] 可维护性: 任务2低估 ScheduleService 收口爆炸半径
  - [中] 可维护性: 任务1对 factory 样本点仍偏门禁化

### m2 · 完成任务 4-8 的主链/配置/迁移策略审查

- 状态: 已完成
- 记录时间: 2026-04-06T13:15:56.781Z
- 已审模块: 任务4 配置单一事实源, 任务5 主链上下文与兼容桥, 任务6 算法边界与 BUG 收口, 任务7 数据基础设施拆分, 任务8 页面/模板/静态资源协议
- 摘要:

  已核对任务 4-8 的 plan 段落，并对照当前 `schedule_optimizer.py`、`config_service.py`、`schedule_optimizer_steps.py`、`schedule_input_collector.py`、`web/bootstrap/static_versioning.py` 与 `tests/test_architecture_fitness.py` 的现状实现检查“单一事实源”“去兼容桥”“后续迁移门禁”是否闭环。

  结论：
  1. 任务 5 与任务 6 的顺序、`best is None` 归属、`_parse_date()` BUG 定性、`RunCommand/RunContext` 单向映射要求，整体上比此前版本严谨得多；
  2. 任务 8 对 `page_boot.js/data-page`、双模板运行时桥接层与静态资源版本化的约束较完整，整体没有出现明显过度抽象；
  3. 但任务 4 仍漏掉一条真实存在的配置第二事实源：`schedule_optimizer.py:_cfg_choices()` 仍直接消费 `cfg_svc.VALID_*`；
  4. 此外，任务 7/8 的后续物理迁移缺少与架构门禁白名单同步更新的明确步骤，容易在执行时制造“代码已迁、白名单仍指旧路径”的假失败或陈旧白名单。
- 结论:

  任务 4-8 的治理框架总体成立，但要真正达成“配置单一事实源 + 后续迁移平滑过门禁”，还需补齐算法侧 `VALID_*` 读取链清理，以及任务 7/8 的白名单路径同步规则。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `core/services/scheduler/config_service.py`
  - `web/bootstrap/static_versioning.py`
  - `tests/test_architecture_fitness.py`
- 下一步建议:

  完成最终总评，汇总哪些任务已足够可执行、哪些任务还需补文字约束后才能避免中间态断层。
- 问题:
  - [中] 可维护性: 任务4仍遗漏算法侧 VALID_* 第二事实源
  - [中] 测试: 任务7/8缺少后续物理迁移的白名单路径同步步骤

### m3 · 完成任务 9-10 与整体可执行性总评

- 状态: 已完成
- 记录时间: 2026-04-06T13:16:28.177Z
- 已审模块: 任务9 测试分层与覆盖率, 任务10 文档/证据/审计轨道, 全局执行顺序与退出条件
- 摘要:

  已核对测试分层与文档轨道相关 plan 段落，并对照 `pyproject.toml`、`requirements-dev.txt`、`.pre-commit-config.yaml`、`tests/conftest.py` 与仓库根现状检查后半段任务是否与前置批次衔接。

  结论：
  1. 任务 9、任务 10 与前置批次的衔接总体成立，尤其是“先补 `tests/regression/` 最小落点，再做完整测试分层”和“先建开发文档/审计入口，再在任务 10 做总收口”的时序是合理的；
  2. 当前仓库确实存在 `requirements-dev.txt` 过薄、`.pre-commit-config.yaml` 直接依赖系统 `ruff`、`pyproject.toml` 仍为 `tests/*` 非递归放宽、根 `README.md` 缺失等事实，说明任务 1、任务 9、任务 10 的问题定义是准确的；
  3. 结合前三个阶段审查，本 plan 已具备作为唯一执行底稿的主体质量，但前述 4 个断层如果不补，执行中仍会出现高概率中间态断裂。

  因此，本轮总评不建议直接判定“可无条件执行”，而应视为“补齐少量文字约束后即可执行”的 conditionally_accepted 状态。
- 结论:

  本 plan 已达到高可执行度，但仍需先补 4 个关键断层后再开工；补齐后可作为唯一权威 plan 使用。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `pyproject.toml`
  - `requirements-dev.txt`
  - `.pre-commit-config.yaml`
  - `tests/conftest.py`
- 下一步建议:

  将 4 个 open finding 回写到 plan 后，再按批次 0 → 1 → 2 顺序实施；其中任务 2 的构造器/仓储属性策略必须最先补齐，否则后续主链与测试改造会反复返工。

## 最终结论

该 plan 已具备较高可执行度，任务顺序、批次边界、静默回退治理意识、目录迁移节奏、主链兼容桥收口与前端协议收口方向总体正确，也基本避免了新的过度抽象；但在直接开工前，仍需先补齐 4 个关键断层：1）任务 2 必须明确 `ScheduleService` 构造器与 `svc.<repo>` 平铺属性的稳定迁移策略；2）任务 1 必须把 `factory.py` 的 `_open_db/_close_db/_perf_headers` 从“样本点”升级为明确清零或接受风险对象；3）任务 4 必须显式清理 `schedule_optimizer.py:_cfg_choices()` 与 `ConfigService.VALID_*` 直读链，避免配置第二事实源残留；4）任务 7/8 必须补入与物理迁移同步的架构白名单路径更新动作。补齐后，本 plan 可以作为唯一权威 plan 执行；未补齐前，不建议无条件开工。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnn7dgru-bmu4za",
  "createdAt": "2026-04-06T00:00:00.000Z",
  "updatedAt": "2026-04-06T13:16:43.547Z",
  "finalizedAt": "2026-04-06T13:16:43.547Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "2026-04-06 技术债务最终合并修复plan 深度review（本轮）",
    "date": "2026-04-06",
    "overview": "审查 .limcode/plans/20260405_技术债务最终合并修复plan.md 的可达成性、结构严谨性、静默回退治理充分性与潜在BUG/断层风险。"
  },
  "scope": {
    "markdown": "# 2026-04-06 技术债务最终合并修复plan 深度review（本轮）\n\n- 日期：2026-04-06\n- 目标文件：`.limcode/plans/20260405_技术债务最终合并修复plan.md`\n- 审查范围：plan 与当前仓库结构、关键实现入口、门禁/测试/调度主链事实的一致性\n- 审查关注点：\n  1. 是否能达成既定治理目的\n  2. 方案是否优雅、简洁，是否存在过度抽象或过度兜底\n  3. 是否仍有静默回退、执行断层、路径漂移、验证口径失配\n  4. 是否存在潜在BUG、循环依赖、验证不可执行或完成判定失真风险\n\n> 按审查序列逐步记录 milestone，不等待全量读完后一次性下结论。"
  },
  "summary": {
    "latestConclusion": "该 plan 已具备较高可执行度，任务顺序、批次边界、静默回退治理意识、目录迁移节奏、主链兼容桥收口与前端协议收口方向总体正确，也基本避免了新的过度抽象；但在直接开工前，仍需先补齐 4 个关键断层：1）任务 2 必须明确 `ScheduleService` 构造器与 `svc.<repo>` 平铺属性的稳定迁移策略；2）任务 1 必须把 `factory.py` 的 `_open_db/_close_db/_perf_headers` 从“样本点”升级为明确清零或接受风险对象；3）任务 4 必须显式清理 `schedule_optimizer.py:_cfg_choices()` 与 `ConfigService.VALID_*` 直读链，避免配置第二事实源残留；4）任务 7/8 必须补入与物理迁移同步的架构白名单路径更新动作。补齐后，本 plan 可以作为唯一权威 plan 执行；未补齐前，不建议无条件开工。",
    "recommendedNextAction": "先将 4 个 open finding 回写到 plan，并优先修补任务 2 的构造器/仓储属性策略与任务 1 的 factory 样本点归属；随后再按批次 0 → 1 → 2 顺序实施。",
    "reviewedModules": [
      "任务1 工程基线与门禁",
      "任务2 请求级装配与仓储束",
      "任务3 目录骨架与路由门面",
      "任务4 配置单一事实源",
      "任务5 主链上下文与兼容桥",
      "任务6 算法边界与 BUG 收口",
      "任务7 数据基础设施拆分",
      "任务8 页面/模板/静态资源协议",
      "任务9 测试分层与覆盖率",
      "任务10 文档/证据/审计轨道",
      "全局执行顺序与退出条件"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 4,
    "severity": {
      "high": 1,
      "medium": 3,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "m1",
      "title": "完成任务 1-3 与现状代码入口的一致性审查",
      "status": "completed",
      "recordedAt": "2026-04-06T13:14:00.124Z",
      "summaryMarkdown": "已核对工程基线、门禁、请求级装配与目录骨架相关 plan 段落，并对照当前 `tests/test_architecture_fitness.py`、`web/bootstrap/factory.py`、`web/ui_mode.py`、`core/services/scheduler/schedule_service.py`、`web/routes/scheduler.py` 等关键入口验证事实。\n\n结论：本 plan 在任务顺序、禁止项、路径冲突规避、`web/bootstrap/` 治理意识和路由迁移节奏上明显比前序版本更成熟，整体方向正确；但任务 1 与任务 2 仍各有一个会影响落地质量的关键断层：\n1. 任务 2 低估了 `ScheduleService` 构造器与平铺仓储属性的真实爆炸半径；\n2. 任务 1 对 `factory.py` 样本点更多停留在“记账+门禁验证”，对 `_open_db/_close_db/_perf_headers` 的实际清零动作还不够落地。\n\n这两个问题如果不先补强，执行者很容易在批次 0/1 形成“门禁已升级、核心热点仍保留静默回退”或“仓储束已引入、但测试/脚本/内部 helper 大面积断裂”的中间态。",
      "conclusionMarkdown": "任务 1-3 的总体治理方向成立，但批次 0/1 仍需先补两处执行级断层：一是 `factory.py` 样本点的清零归属，二是 `ScheduleService` 构造器与仓储属性的兼容/迁移策略。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/operation_edit_service.py"
        },
        {
          "path": "tests/regression_schedule_service_passes_algo_stats_to_summary.py"
        },
        {
          "path": "tests/regression_schedule_service_reschedulable_contract.py"
        }
      ],
      "reviewedModules": [
        "任务1 工程基线与门禁",
        "任务2 请求级装配与仓储束",
        "任务3 目录骨架与路由门面"
      ],
      "recommendedNextAction": "继续审查任务 4-8，重点核对配置单一事实源、主链兼容桥收口、算法边界与静态资源/双模板治理是否仍存在未被 plan 明确覆盖的第二事实源或契约松散点。",
      "findingIds": [
        "task2-schedule-service-blast-radius",
        "task1-factory-sample-points-not-cleared"
      ]
    },
    {
      "id": "m2",
      "title": "完成任务 4-8 的主链/配置/迁移策略审查",
      "status": "completed",
      "recordedAt": "2026-04-06T13:15:56.781Z",
      "summaryMarkdown": "已核对任务 4-8 的 plan 段落，并对照当前 `schedule_optimizer.py`、`config_service.py`、`schedule_optimizer_steps.py`、`schedule_input_collector.py`、`web/bootstrap/static_versioning.py` 与 `tests/test_architecture_fitness.py` 的现状实现检查“单一事实源”“去兼容桥”“后续迁移门禁”是否闭环。\n\n结论：\n1. 任务 5 与任务 6 的顺序、`best is None` 归属、`_parse_date()` BUG 定性、`RunCommand/RunContext` 单向映射要求，整体上比此前版本严谨得多；\n2. 任务 8 对 `page_boot.js/data-page`、双模板运行时桥接层与静态资源版本化的约束较完整，整体没有出现明显过度抽象；\n3. 但任务 4 仍漏掉一条真实存在的配置第二事实源：`schedule_optimizer.py:_cfg_choices()` 仍直接消费 `cfg_svc.VALID_*`；\n4. 此外，任务 7/8 的后续物理迁移缺少与架构门禁白名单同步更新的明确步骤，容易在执行时制造“代码已迁、白名单仍指旧路径”的假失败或陈旧白名单。",
      "conclusionMarkdown": "任务 4-8 的治理框架总体成立，但要真正达成“配置单一事实源 + 后续迁移平滑过门禁”，还需补齐算法侧 `VALID_*` 读取链清理，以及任务 7/8 的白名单路径同步规则。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/config_service.py"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "reviewedModules": [
        "任务4 配置单一事实源",
        "任务5 主链上下文与兼容桥",
        "任务6 算法边界与 BUG 收口",
        "任务7 数据基础设施拆分",
        "任务8 页面/模板/静态资源协议"
      ],
      "recommendedNextAction": "完成最终总评，汇总哪些任务已足够可执行、哪些任务还需补文字约束后才能避免中间态断层。",
      "findingIds": [
        "task4-cfg-choices-second-source",
        "task7-8-arch-whitelist-path-drift"
      ]
    },
    {
      "id": "m3",
      "title": "完成任务 9-10 与整体可执行性总评",
      "status": "completed",
      "recordedAt": "2026-04-06T13:16:28.177Z",
      "summaryMarkdown": "已核对测试分层与文档轨道相关 plan 段落，并对照 `pyproject.toml`、`requirements-dev.txt`、`.pre-commit-config.yaml`、`tests/conftest.py` 与仓库根现状检查后半段任务是否与前置批次衔接。\n\n结论：\n1. 任务 9、任务 10 与前置批次的衔接总体成立，尤其是“先补 `tests/regression/` 最小落点，再做完整测试分层”和“先建开发文档/审计入口，再在任务 10 做总收口”的时序是合理的；\n2. 当前仓库确实存在 `requirements-dev.txt` 过薄、`.pre-commit-config.yaml` 直接依赖系统 `ruff`、`pyproject.toml` 仍为 `tests/*` 非递归放宽、根 `README.md` 缺失等事实，说明任务 1、任务 9、任务 10 的问题定义是准确的；\n3. 结合前三个阶段审查，本 plan 已具备作为唯一执行底稿的主体质量，但前述 4 个断层如果不补，执行中仍会出现高概率中间态断裂。\n\n因此，本轮总评不建议直接判定“可无条件执行”，而应视为“补齐少量文字约束后即可执行”的 conditionally_accepted 状态。",
      "conclusionMarkdown": "本 plan 已达到高可执行度，但仍需先补 4 个关键断层后再开工；补齐后可作为唯一权威 plan 使用。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "pyproject.toml"
        },
        {
          "path": "requirements-dev.txt"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": "tests/conftest.py"
        }
      ],
      "reviewedModules": [
        "任务9 测试分层与覆盖率",
        "任务10 文档/证据/审计轨道",
        "全局执行顺序与退出条件"
      ],
      "recommendedNextAction": "将 4 个 open finding 回写到 plan 后，再按批次 0 → 1 → 2 顺序实施；其中任务 2 的构造器/仓储属性策略必须最先补齐，否则后续主链与测试改造会反复返工。",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "task2-schedule-service-blast-radius",
      "severity": "high",
      "category": "maintainability",
      "title": "任务2低估 ScheduleService 收口爆炸半径",
      "descriptionMarkdown": "plan 要求 `ScheduleService` 从内部平铺创建 10 个仓储实例改为接收 `RepositoryBundle`，并把内部使用从 `self.xxx_repo` 切到 `self.repos.xxx_repo`。但当前代码与测试/脚本并不只依赖构造器 `(conn, logger=None, op_logger=None)`，还在大量位置直接读取或覆写 `svc.batch_repo`、`svc.op_repo`、`svc.history_repo` 等属性。仅代表性证据就包括：`tests/regression_schedule_service_passes_algo_stats_to_summary.py` 直接访问 `svc.batch_repo/op_repo`，`tests/regression_schedule_service_reschedulable_contract.py` 直接覆写 `svc.op_repo`，`tests/regression_schedule_input_collector_contract.py` 直接调用 `collect_schedule_run_input(...)` 并传入现有注入签名，而 `core/services/scheduler/operation_edit_service.py`、`schedule_input_collector.py` 等内部 helper 也广泛依赖 `svc.<repo>` 形态。若按 plan 字面执行而不保留稳定公开构造签名与仓储访问策略，批次 1 会同时打断路由、内部 helper、回归测试与脚本入口；若临时加兼容桥，又会和 plan 的“禁止新增临时兼容桥”原则冲突。",
      "recommendationMarkdown": "任务 2 应显式补一条稳定策略：要么保留 `ScheduleService(conn, logger=None, op_logger=None)` 作为正式公开构造边界，并把 `RepositoryBundle` 作为内部可选注入；要么在 plan 中列出必须同步迁改的全部调用点与 `svc.<repo>` 访问位点，并说明这些属性是保留为正式代理属性还是一次性全面替换。两者必须二选一，不能留给执行者临场判断。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/operation_edit_service.py"
        },
        {
          "path": "tests/regression_schedule_service_passes_algo_stats_to_summary.py"
        },
        {
          "path": "tests/regression_schedule_service_reschedulable_contract.py"
        },
        {
          "path": "tests/regression_schedule_input_collector_contract.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task1-factory-sample-points-not-cleared",
      "severity": "medium",
      "category": "maintainability",
      "title": "任务1对 factory 样本点仍偏门禁化",
      "descriptionMarkdown": "plan 已要求把 `_open_db/_close_db/_perf_headers` 作为 `web/bootstrap/` 样本点登记并做扫描命中验证，但真正的代码治理步骤 6.5 只明确优先收口 `plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py`、`_maintenance_gate_response` 与 `runtime_base_dir()`。当前 `web/bootstrap/factory.py` 仍保留多处关键静默回退：`_open_db` 中 `g._aps_req_started` 失败后回退为 `None`、请求路径解析失败后 `pass`；`_close_db` 中 `db.close()` 异常吞没；`_perf_headers` 中 `_is_prefetch_req()` 失败直接 `return False`、外层异常直接 `pass`。如果任务 1 只做到“建台账 + 扩门禁 + 样本验证”，而没有把这些样本点明确归类为本任务就地清零、可观测接受风险或后续具体批次，就会出现批次 0 已宣称完成、但启动/请求装配主路径仍保留静默回退热点的假收口。",
      "recommendationMarkdown": "任务 1 应把 `_open_db`、`_close_db`、`_perf_headers` 从“样本点”提升为明确执行对象：逐项声明是任务 1 本批清零、接受风险保留（含日志/事件要求），还是绑定到后续唯一批次；并把该归属写进步骤 6.5 或完成判定，而不是仅依赖台账自由填写。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        },
        {
          "path": "core/services/scheduler/operation_edit_service.py"
        },
        {
          "path": "tests/regression_schedule_service_passes_algo_stats_to_summary.py"
        },
        {
          "path": "tests/regression_schedule_service_reschedulable_contract.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task4-cfg-choices-second-source",
      "severity": "medium",
      "category": "maintainability",
      "title": "任务4仍遗漏算法侧 VALID_* 第二事实源",
      "descriptionMarkdown": "任务 4 已明确要求清理 `schedule_optimizer.py` 里的 `_cfg_value()`、`_norm_text()`，并让快照/校验/预设/页面元数据统一走注册表；但当前优化器里还有一条独立的合法值来源：`_cfg_choices()` 会直接从 `cfg_svc.VALID_STRATEGIES / VALID_DISPATCH_MODES / VALID_DISPATCH_RULES` 读取合法集合，并在缺值时回退到本地元组。`ConfigService` 侧这些 `VALID_*` 常量与 `get_available_strategies()` 也仍是独立定义。这意味着即使 `_cfg_value/_norm_text` 被删掉，只要 `_cfg_choices()` 保留，优化器仍可能和注册表/页面元数据/校验器维持两套合法值来源，任务 4 的“单一事实源”目标就无法完全落地。",
      "recommendationMarkdown": "任务 4 需要显式补一条步骤与完成判定：`schedule_optimizer.py:_cfg_choices()`、`cfg_svc.VALID_*` 直读、以及与之等价的本地回退元组必须同步退出；允许保留 `ConfigService` 对外常量/方法作为注册表投影，但其值必须由注册表生成，不能继续手写维护。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/config_service.py"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task7-8-arch-whitelist-path-drift",
      "severity": "medium",
      "category": "test",
      "title": "任务7/8缺少后续物理迁移的白名单路径同步步骤",
      "descriptionMarkdown": "当前 `tests/test_architecture_fitness.py` 仍硬编码了大量路径敏感条目，包括 `core/infrastructure/backup.py`、`core/infrastructure/database.py` 的静默回退白名单，以及 `web/routes/system_backup.py` 等旧路由文件路径。任务 3 已为 scheduler 域迁移补了路径敏感测试修正步骤，但任务 7 还会继续拆 `backup.py/database.py`，任务 8 还会继续把 `system/process/personnel/equipment` 物理迁入 `web/routes/domains/**`；这两个后续迁移批次却没有像任务 3 那样显式要求同步更新 `tests/test_architecture_fitness.py` 中的超长文件白名单、静默回退白名单、复杂度白名单和同类路径清单。由于任务 7/8 验证命令都仍要求跑架构门禁，这会在执行时形成明显的路径漂移断层。",
      "recommendationMarkdown": "把任务 3 的“路径敏感白名单同步修正”抽成一个横向固定动作，并复制到任务 7、任务 8：凡发生物理迁移或热点拆分的批次，都必须同批更新/移除 `tests/test_architecture_fitness.py`（任务 9 后对应 `tests/architecture/test_architecture_fitness.py`）中的相关路径白名单与门禁断言。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "core/services/scheduler/config_service.py"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:b5d2c6bf8c452c943e3bbbdfdb1797d5cc865537534ffe42263f82c10ad84529",
    "generatedAt": "2026-04-06T13:16:43.547Z",
    "locale": "zh-CN"
  }
}
```
