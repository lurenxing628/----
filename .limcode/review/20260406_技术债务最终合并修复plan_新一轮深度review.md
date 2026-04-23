# 20260406_技术债务最终合并修复plan_新一轮深度review
- 日期: 2026-04-06
- 概述: 对技术债务最终合并修复plan进行新一轮深度审查，重点核对目标达成性、步骤严谨性、收口完整性与潜在BUG。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 20260406_技术债务最终合并修复plan 新一轮深度review

- 日期：2026-04-06
- 对象：`.limcode/plans/20260405_技术债务最终合并修复plan.md`
- 范围：执行边界、任务拆分、前后依赖、验证闭环、静默回退治理、潜在BUG与实现复杂度风险
- 方法：按批次与任务逐段核对，发现一个有意义的模块级问题后立即记录里程碑

## 初始判断

当前 plan 已明显吸收了大量前序 review 结论，结构化程度较高，覆盖面也较完整。但是否能够“直接指导实施且稳定达成目标”，仍需继续核对以下方面：

1. 任务之间的前后依赖是否彻底闭合。
2. 验证命令、完成判定与实施步骤之间是否一一对应。
3. 是否仍存在隐藏的双事实源、重复收口、路径漂移或执行时序断裂。
4. 是否有会诱发过度改造、重复迁移或中间态失稳的步骤。
5. 是否还残留对 BUG、静默回退、兼容桥、目录迁移的模糊描述。

## 评审摘要

- 当前状态: 已完成
- 已审模块: 任务1 工程基线与质量门禁, 任务2 请求级服务装配与仓储束, 任务3 目录骨架与路由领域子包, 任务4 调度配置单一事实源, 任务5 排产主链上下文与兼容桥, 任务6 算法主流程与类型约束, 任务7 数据基础设施与 Gantt 热点, 任务8 页面组装、Excel 页面流程、模板树与前端协议, 任务9 测试目录重整与覆盖率口径, 任务10 文档、证据与审计轨道
- 当前进度: 已记录 3 个里程碑；最新：m3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 4
- 问题严重级别分布: 高 1 / 中 3 / 低 0
- 最新结论: 三轮深度核对后，这份 `20260405_技术债务最终合并修复plan.md` 已经比前序版本明显更成熟：大部分已知路径漂移、静默回退、兼容桥、测试迁移和文档入口链问题都被吸收进了任务边界，整体方向正确，结构也比旧版更克制、更接近可实施状态。 但它**还不能直接作为最终唯一权威 plan 投入实施**。当前仍有 4 个会影响目标达成度与执行无歧义性的缺口： 1. task1 对启动链改造缺少足够明确的定向回归护栏； 2. task3 对非 scheduler 域根层门面的切换时序与“只建空包、不迁文件”的批次边界互相冲突； 3. task4 的“配置单一事实源”尚未覆盖配置页面与模板层，前后端仍可能保留双事实源； 4. task8 声称转向 `page_boot.js/data-page` 的 DOM 协议，但缺少直接可验证的退出条件，容易停留在口号层。 因此，当前最合理的判断是：**这是一份高质量、接近可执行的修订版草案，但仍需再做一次小规模定向修订后，才能成为真正的唯一权威实施 plan。**
- 下一步建议: 先按本轮 4 个发现修订 plan，再进入实施：补 task1 启动链专项回归，修 task3 非 scheduler 域门面时序，扩 task4 到配置页面元数据，补 task8 的 DOM 协议门禁与完成判定。
- 总体结论: 需要后续跟进

## 评审发现

### 启动链改造缺少定向回归护栏

- ID: task1-bootstrap-regression-gap
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  plan 在 task1 中把 `web/bootstrap/` 多个启动链文件纳入静默回退治理，但验证命令只固定到 `tests/test_architecture_fitness.py` 与统一门禁入口，未把现有的运行时探测、启动契约、停机链路、插件装配可观测性回归显式绑定到 task1。证据见 plan 第283-295、316-320、365-389 行，而仓库已存在 `tests/regression_runtime_probe_resolution.py`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_startup_host_portfile.py`、`tests/regression_plugin_bootstrap_config_failure_visible.py`、`tests/regression_runtime_stop_cli.py`。若执行者仅按 plan 自带验证收口，启动链行为回归存在被漏检的风险。
- 建议:

  在 task1 的“验证命令”或“重点回归集合”中，至少显式纳入运行时探测、启动契约、插件装配和停机链路四类现成回归，避免统一门禁入口成为过宽占位。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/regression_runtime_probe_resolution.py`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_startup_host_portfile.py`
  - `tests/regression_plugin_bootstrap_config_failure_visible.py`
  - `tests/regression_runtime_stop_cli.py`
  - `web/routes/process.py`
  - `web/routes/system.py`
  - `web/routes/personnel.py`
  - `web/routes/equipment.py`

### 非 scheduler 域门面改造时序冲突

- ID: task3-domain-facade-ordering-conflict
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  task3 的批次边界第683-687 行明确规定 `process/personnel/equipment/system` 四个域在批次1只建子包与空 `__init__.py`，实际文件迁移延后到 task8；但步骤7 第723-726 行又要求 `process.py`、`personnel.py`、`equipment.py`、`system.py` 统一改成 `from .domains.<领域> import ...` 的包内导入。当前这些根层门面仍直接导入同目录下的真实模块，如 `web/routes/process.py:18-30`、`web/routes/system.py:16-26`。如果按现有文字执行，批次1将出现“目标子包为空，但根层门面已改向新子包”的中间态断裂。
- 建议:

  把 task3 步骤7 明确拆成两段：批次1仅改 `scheduler.py`；其余四个根层门面要么保持旧导入直到 task8 完成物理迁移，要么在 task3 同步创建域内转发模块后再切换，禁止留给执行者自行猜测。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/regression_runtime_probe_resolution.py`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_startup_host_portfile.py`
  - `tests/regression_plugin_bootstrap_config_failure_visible.py`
  - `tests/regression_runtime_stop_cli.py`
  - `web/routes/process.py`
  - `web/routes/system.py`
  - `web/routes/personnel.py`
  - `web/routes/equipment.py`

### 配置页面仍保留第二套字段事实源

- ID: task4-config-ui-second-source
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  task4 在 plan 中把目标定义为“调度配置字段只有一处登记”，但文件职责与步骤只覆盖 `config_field_spec.py`、`config_snapshot.py`、`config_validator.py`、`config_service.py`、`config_presets.py`、算法入口和 `schedule_summary_freeze.py`，未覆盖 `web/routes/scheduler_config.py` 与 `templates/scheduler/config.html`。当前这两个文件仍硬编码 `algo_mode`、`objective`、`dispatch_mode`、`dispatch_rule`、`freeze_window_*` 的选项、标签与提示语，而 `ConfigService` 目前只有 `get_available_strategies()` 这一个页面可消费元数据出口。结果是：即使 task4 完成，页面层仍然需要手工同步第二套字段枚举与文案，无法真正达到“新增配置字段只需一处登记”的目标。
- 建议:

  把 `web/routes/domains/scheduler/scheduler_config.py`（任务3后路径）与 `templates/scheduler/config.html` 的字段选项、标签、提示语纳入 task4 范围：至少要求页面渲染从字段注册表或统一字段门面生成可选项与展示文案，避免前后端双事实源并存。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/routes/scheduler_config.py`
  - `templates/scheduler/config.html`
  - `core/services/scheduler/config_service.py`

### DOM 协议迁移缺少直接门禁

- ID: task8-dom-protocol-exit-gap
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: m3
- 说明:

  plan 在关键结构决策和 task8 中把 `static/js/page_boot.js`、`data-page`、`data-*` 设为前端初始化的新协议，但完成判定与验证命令没有直接检查这些约束是否真正落地。当前 `templates/base.html` 仍没有 `data-page`，`static/js/common.js` 与 `static/js/gantt.js` 仍以 `window.__APS_COMMON__`、`window.__APS_GANTT__` 为核心入口，而 `tests/regression_frontend_common_interactions.py` 只验证旧全局命名空间与脚本顺序，不验证 `page_boot.js` 或 `data-page`。这样会导致 task8 即使全部自带验证通过，也可能只是“新增了新协议文件，但旧协议仍是主入口”，无法证明前端初始化已经真正完成收口。
- 建议:

  给 task8 增加一条明确门禁：至少校验 `static/js/page_boot.js` 被 `templates/base.html` 或等价公共模板接入、目标页面根节点产出 `data-page`、且新接入页面不再以扩张 `window.__APS_COMMON__`/`window.__APS_GANTT__` 作为新增初始化入口。若短期必须保留旧全局入口，也应把“哪些页面已切到 DOM 协议、哪些页面仍在旧协议”写进完成判定。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `templates/base.html`
  - `static/js/common.js`
  - `static/js/gantt.js`
  - `tests/regression_frontend_common_interactions.py`
  - `tests/check_quickref_vs_routes.py`

## 评审里程碑

### m1 · 第一轮：批次0-1与任务1-3的可执行性核对

- 状态: 已完成
- 记录时间: 2026-04-06T11:22:42.905Z
- 已审模块: 任务1 工程基线与质量门禁, 任务2 请求级服务装配与仓储束, 任务3 目录骨架与路由领域子包
- 摘要:

  已完成对任务1、任务2、任务3的第一轮核对。整体上，工程基线、请求级装配、调度目录骨架与路由分域的大方向是成立的，plan 对静默回退、直接装配、路径漂移和同名目录冲突的约束也明显比前序版本更严谨。

  但仍发现两个会影响“可直接执行”的问题：

  1. **任务1验证闭环偏弱**：task1 明确要改 `web/bootstrap/plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py`、`factory.py`、`paths.py` 等启动链关键点，但验证命令只有 `tests/test_architecture_fitness.py` 与 `python scripts/run_quality_gate.py`。当前仓库其实已存在覆盖运行时探测、启动契约、停机链路、插件装配可观测性的现成回归；如果 plan 不把这些测试至少列成 task1 的定向护栏，执行者完全可能“按计划完成且通过自带验证”，但真实启动链行为仍被改坏。

  2. **任务3内部存在时序冲突**：task3 一方面明确规定 `process/personnel/equipment/system` 四个域在批次1只创建子包与空 `__init__.py`，实际文件迁移延后到 task8；另一方面又在步骤7要求 `process.py`、`personnel.py`、`equipment.py`、`system.py` 统一改成从 `.domains.<领域>` 导入。若没有同步创建对应转发模块，这一要求会与“只建空包、不迁文件”的批次边界直接冲突，执行者要么提前搬域、要么制造中间态断裂，违背了 plan 自己强调的最小变更原则。
- 结论:

  批次0-1方向正确，但 task1 需要补足启动链定向回归，task3 需要修正非 scheduler 域门面改造时序，否则 plan 还不能算可无歧义落地。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:283-295`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:316-320`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:365-389`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:683-687`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:717-726`
  - `web/routes/process.py:18-30`
  - `web/routes/system.py:16-26`
  - `tests/regression_runtime_probe_resolution.py:1-9`
  - `tests/test_win7_launcher_runtime_paths.py:31-76`
  - `tests/regression_plugin_bootstrap_config_failure_visible.py:25-70`
  - `tests/regression_runtime_stop_cli.py:1-8`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `tests/regression_runtime_probe_resolution.py`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_startup_host_portfile.py`
  - `tests/regression_plugin_bootstrap_config_failure_visible.py`
  - `tests/regression_runtime_stop_cli.py`
  - `web/routes/process.py`
  - `web/routes/system.py`
  - `web/routes/personnel.py`
  - `web/routes/equipment.py`
- 下一步建议:

  继续第二轮，核对任务4-7是否还存在会破坏单一事实源、路径口径或验证闭环的遗漏。
- 问题:
  - [中] 测试: 启动链改造缺少定向回归护栏
  - [高] 可维护性: 非 scheduler 域门面改造时序冲突

### m2 · 第二轮：任务4-7的单一事实源与主链治理核对

- 状态: 已完成
- 记录时间: 2026-04-06T11:24:22.060Z
- 已审模块: 任务4 调度配置单一事实源, 任务5 排产主链上下文与兼容桥, 任务6 算法主流程与类型约束, 任务7 数据基础设施与 Gantt 热点
- 摘要:

  已完成对任务4、任务5、任务6、任务7的第二轮核对。总体判断是：plan 对配置读取闭包、主链兼容桥、`persist_schedule()` 参数爆炸、`if best is None` 归属、`gantt_critical_chain.py` / `gantt_service.py` 静默回退清理、以及 `database.py` / `backup.py` / `schedule_repo.py` 热点拆分的命中度都比较高；相较前序版本，主链与数据层的收口已经明显更严谨。

  本轮新增确认的关键问题主要集中在 task4：

  1. **调度配置的“单一事实源”仍未覆盖配置页面与页面展示元数据**。task4 目前只覆盖后端配置服务、快照、校验器、算法入口与摘要侧读取点，但当前 `web/routes/scheduler_config.py` 与 `templates/scheduler/config.html` 仍直接硬编码 `algo_mode`、`objective`、`dispatch_mode`、`dispatch_rule`、`freeze_window_*` 的选项、标签与提示语；`ConfigService` 目前也只提供 `get_available_strategies()`，没有为其余字段提供统一可消费的字段元数据出口。这意味着即使 task4 完成，执行层和页面层之间仍会保留第二套字段枚举与展示语义，plan 声称的“新增配置字段只需一处登记”并不能真正成立。

  2. 作为次要观察，task5 对 `CalendarService/ConfigService` 的延迟导入收口方向是对的，但描述里仍残留少量 task3 之后不应继续出现的旧根路径措辞；这属于文案一致性问题，建议修订时顺手清掉，以保持 plan 自己设定的“后续步骤只引用迁移后路径”规则完整。
- 结论:

  任务4-7的大方向已基本能支撑“少兼容桥、少静默回退”的目标，但 task4 还需要把配置页面元数据纳入同一字段注册表或统一读取门面，否则配置领域仍会保留前后端双事实源。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:783-850`
  - `web/routes/scheduler_config.py:274-304`
  - `web/routes/scheduler_config.py:367-388`
  - `templates/scheduler/config.html:269-365`
  - `core/services/scheduler/config_service.py:359-360`
  - `core/services/scheduler/config_service.py:397-423`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:667-673`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:954-959`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/routes/scheduler_config.py`
  - `templates/scheduler/config.html`
  - `core/services/scheduler/config_service.py`
- 下一步建议:

  进入第三轮，重点核对任务8-10的前端协议、测试迁移和文档校验是否已经具备可验证的退出条件。
- 问题:
  - [中] 可维护性: 配置页面仍保留第二套字段事实源

### m3 · 第三轮：任务8-10的前端协议、测试迁移与文档轨道核对

- 状态: 已完成
- 记录时间: 2026-04-06T11:25:27.951Z
- 已审模块: 任务8 页面组装、Excel 页面流程、模板树与前端协议, 任务9 测试目录重整与覆盖率口径, 任务10 文档、证据与审计轨道
- 摘要:

  已完成对任务8、任务9、任务10的第三轮核对。总体看，plan 已经吸收了此前最明显的三个缺口：试点页专项回归被写回 task8，`regression_frontend_common_interactions.py` 与 `test_ui_mode.py` 已纳入 task9 首批迁移范围，task10 也明确要求 `check_quickref_vs_routes.py` 追加关键路径存在性校验。这说明界面层、测试层、文档层的闭环设计比前几版更成熟。

  不过，第三轮仍确认一个会影响“是否真正完成前端协议收口”的问题：

  1. **task8 缺少对 DOM 协议落地程度的直接退出条件**。plan 在关键结构决策和 task8 步骤5中明确提出要转向 `static/js/page_boot.js + data-page + data-*`，并要求不再扩张 `window.__APS_COMMON__`、`window.__APS_GANTT__`。但 task8 的完成判定与验证命令并没有任何一条直接检查 `page_boot.js` 是否被接入、目标页面是否真的产出 `data-page`、或现有全局命名空间是否停止继续承担新增初始化职责。当前仓库里 `templates/base.html` 仍没有 `data-page`，`static/js/common.js` 与 `static/js/gantt.js` 仍以全局命名空间为核心入口，而 `tests/regression_frontend_common_interactions.py` 还在显式断言 `window.__APS_COMMON__` 必须存在。这意味着执行者完全可能“新增了 page_boot.js、保留了旧全局入口、现有测试照样通过”，但并没有真正完成 plan 自己宣称的协议迁移。

  2. task9、task10 的方向目前没有再发现新的主阻塞点：测试分层、共享仓库根辅助、速查表双重校验、文档入口链的设计都已比旧版严谨，可在修正 task8 的退出条件后继续使用。
- 结论:

  任务8-10整体已接近可执行，但 task8 还需要补一个面向 `page_boot.js/data-page` 的明确门禁或完成判定，否则“前端初始化已转向 DOM 协议”仍可能停留在口号层。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:235-241`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1292-1296`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1329-1359`
  - `templates/base.html:50-135`
  - `static/js/common.js:270-305`
  - `static/js/gantt.js:1-6`
  - `tests/regression_frontend_common_interactions.py:40-119`
  - `tests/check_quickref_vs_routes.py:16-23`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `templates/base.html`
  - `static/js/common.js`
  - `static/js/gantt.js`
  - `tests/regression_frontend_common_interactions.py`
  - `tests/check_quickref_vs_routes.py`
- 下一步建议:

  基于三轮结果做一次小规模修订：补 task1 启动链定向回归、修 task3 非 scheduler 域门面时序、扩 task4 到配置页面元数据、补 task8 的 DOM 协议门禁；完成后再把该 plan 作为唯一权威实施计划。
- 问题:
  - [中] JavaScript: DOM 协议迁移缺少直接门禁

## 最终结论

三轮深度核对后，这份 `20260405_技术债务最终合并修复plan.md` 已经比前序版本明显更成熟：大部分已知路径漂移、静默回退、兼容桥、测试迁移和文档入口链问题都被吸收进了任务边界，整体方向正确，结构也比旧版更克制、更接近可实施状态。

但它**还不能直接作为最终唯一权威 plan 投入实施**。当前仍有 4 个会影响目标达成度与执行无歧义性的缺口：

1. task1 对启动链改造缺少足够明确的定向回归护栏；
2. task3 对非 scheduler 域根层门面的切换时序与“只建空包、不迁文件”的批次边界互相冲突；
3. task4 的“配置单一事实源”尚未覆盖配置页面与模板层，前后端仍可能保留双事实源；
4. task8 声称转向 `page_boot.js/data-page` 的 DOM 协议，但缺少直接可验证的退出条件，容易停留在口号层。

因此，当前最合理的判断是：**这是一份高质量、接近可执行的修订版草案，但仍需再做一次小规模定向修订后，才能成为真正的唯一权威实施 plan。**

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnn3i3j6-a18fpn",
  "createdAt": "2026-04-06T00:00:00.000Z",
  "updatedAt": "2026-04-06T11:25:41.706Z",
  "finalizedAt": "2026-04-06T11:25:41.706Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "20260406_技术债务最终合并修复plan_新一轮深度review",
    "date": "2026-04-06",
    "overview": "对技术债务最终合并修复plan进行新一轮深度审查，重点核对目标达成性、步骤严谨性、收口完整性与潜在BUG。"
  },
  "scope": {
    "markdown": "# 20260406_技术债务最终合并修复plan 新一轮深度review\n\n- 日期：2026-04-06\n- 对象：`.limcode/plans/20260405_技术债务最终合并修复plan.md`\n- 范围：执行边界、任务拆分、前后依赖、验证闭环、静默回退治理、潜在BUG与实现复杂度风险\n- 方法：按批次与任务逐段核对，发现一个有意义的模块级问题后立即记录里程碑\n\n## 初始判断\n\n当前 plan 已明显吸收了大量前序 review 结论，结构化程度较高，覆盖面也较完整。但是否能够“直接指导实施且稳定达成目标”，仍需继续核对以下方面：\n\n1. 任务之间的前后依赖是否彻底闭合。\n2. 验证命令、完成判定与实施步骤之间是否一一对应。\n3. 是否仍存在隐藏的双事实源、重复收口、路径漂移或执行时序断裂。\n4. 是否有会诱发过度改造、重复迁移或中间态失稳的步骤。\n5. 是否还残留对 BUG、静默回退、兼容桥、目录迁移的模糊描述。"
  },
  "summary": {
    "latestConclusion": "三轮深度核对后，这份 `20260405_技术债务最终合并修复plan.md` 已经比前序版本明显更成熟：大部分已知路径漂移、静默回退、兼容桥、测试迁移和文档入口链问题都被吸收进了任务边界，整体方向正确，结构也比旧版更克制、更接近可实施状态。\n\n但它**还不能直接作为最终唯一权威 plan 投入实施**。当前仍有 4 个会影响目标达成度与执行无歧义性的缺口：\n\n1. task1 对启动链改造缺少足够明确的定向回归护栏；\n2. task3 对非 scheduler 域根层门面的切换时序与“只建空包、不迁文件”的批次边界互相冲突；\n3. task4 的“配置单一事实源”尚未覆盖配置页面与模板层，前后端仍可能保留双事实源；\n4. task8 声称转向 `page_boot.js/data-page` 的 DOM 协议，但缺少直接可验证的退出条件，容易停留在口号层。\n\n因此，当前最合理的判断是：**这是一份高质量、接近可执行的修订版草案，但仍需再做一次小规模定向修订后，才能成为真正的唯一权威实施 plan。**",
    "recommendedNextAction": "先按本轮 4 个发现修订 plan，再进入实施：补 task1 启动链专项回归，修 task3 非 scheduler 域门面时序，扩 task4 到配置页面元数据，补 task8 的 DOM 协议门禁与完成判定。",
    "reviewedModules": [
      "任务1 工程基线与质量门禁",
      "任务2 请求级服务装配与仓储束",
      "任务3 目录骨架与路由领域子包",
      "任务4 调度配置单一事实源",
      "任务5 排产主链上下文与兼容桥",
      "任务6 算法主流程与类型约束",
      "任务7 数据基础设施与 Gantt 热点",
      "任务8 页面组装、Excel 页面流程、模板树与前端协议",
      "任务9 测试目录重整与覆盖率口径",
      "任务10 文档、证据与审计轨道"
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
      "title": "第一轮：批次0-1与任务1-3的可执行性核对",
      "status": "completed",
      "recordedAt": "2026-04-06T11:22:42.905Z",
      "summaryMarkdown": "已完成对任务1、任务2、任务3的第一轮核对。整体上，工程基线、请求级装配、调度目录骨架与路由分域的大方向是成立的，plan 对静默回退、直接装配、路径漂移和同名目录冲突的约束也明显比前序版本更严谨。\n\n但仍发现两个会影响“可直接执行”的问题：\n\n1. **任务1验证闭环偏弱**：task1 明确要改 `web/bootstrap/plugins.py`、`launcher.py`、`entrypoint.py`、`security.py`、`runtime_probe.py`、`factory.py`、`paths.py` 等启动链关键点，但验证命令只有 `tests/test_architecture_fitness.py` 与 `python scripts/run_quality_gate.py`。当前仓库其实已存在覆盖运行时探测、启动契约、停机链路、插件装配可观测性的现成回归；如果 plan 不把这些测试至少列成 task1 的定向护栏，执行者完全可能“按计划完成且通过自带验证”，但真实启动链行为仍被改坏。\n\n2. **任务3内部存在时序冲突**：task3 一方面明确规定 `process/personnel/equipment/system` 四个域在批次1只创建子包与空 `__init__.py`，实际文件迁移延后到 task8；另一方面又在步骤7要求 `process.py`、`personnel.py`、`equipment.py`、`system.py` 统一改成从 `.domains.<领域>` 导入。若没有同步创建对应转发模块，这一要求会与“只建空包、不迁文件”的批次边界直接冲突，执行者要么提前搬域、要么制造中间态断裂，违背了 plan 自己强调的最小变更原则。",
      "conclusionMarkdown": "批次0-1方向正确，但 task1 需要补足启动链定向回归，task3 需要修正非 scheduler 域门面改造时序，否则 plan 还不能算可无歧义落地。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 283,
          "lineEnd": 295,
          "excerptHash": "sha256:m1a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 316,
          "lineEnd": 320,
          "excerptHash": "sha256:m1b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 365,
          "lineEnd": 389,
          "excerptHash": "sha256:m1c"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 683,
          "lineEnd": 687,
          "excerptHash": "sha256:m1d"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 717,
          "lineEnd": 726,
          "excerptHash": "sha256:m1e"
        },
        {
          "path": "web/routes/process.py",
          "lineStart": 18,
          "lineEnd": 30,
          "excerptHash": "sha256:m1f"
        },
        {
          "path": "web/routes/system.py",
          "lineStart": 16,
          "lineEnd": 26,
          "excerptHash": "sha256:m1g"
        },
        {
          "path": "tests/regression_runtime_probe_resolution.py",
          "lineStart": 1,
          "lineEnd": 9,
          "excerptHash": "sha256:m1h"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 31,
          "lineEnd": 76,
          "excerptHash": "sha256:m1i"
        },
        {
          "path": "tests/regression_plugin_bootstrap_config_failure_visible.py",
          "lineStart": 25,
          "lineEnd": 70,
          "excerptHash": "sha256:m1j"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 1,
          "lineEnd": 8,
          "excerptHash": "sha256:m1k"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/regression_runtime_probe_resolution.py"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_startup_host_portfile.py"
        },
        {
          "path": "tests/regression_plugin_bootstrap_config_failure_visible.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        },
        {
          "path": "web/routes/process.py"
        },
        {
          "path": "web/routes/system.py"
        },
        {
          "path": "web/routes/personnel.py"
        },
        {
          "path": "web/routes/equipment.py"
        }
      ],
      "reviewedModules": [
        "任务1 工程基线与质量门禁",
        "任务2 请求级服务装配与仓储束",
        "任务3 目录骨架与路由领域子包"
      ],
      "recommendedNextAction": "继续第二轮，核对任务4-7是否还存在会破坏单一事实源、路径口径或验证闭环的遗漏。",
      "findingIds": [
        "task1-bootstrap-regression-gap",
        "task3-domain-facade-ordering-conflict"
      ]
    },
    {
      "id": "m2",
      "title": "第二轮：任务4-7的单一事实源与主链治理核对",
      "status": "completed",
      "recordedAt": "2026-04-06T11:24:22.060Z",
      "summaryMarkdown": "已完成对任务4、任务5、任务6、任务7的第二轮核对。总体判断是：plan 对配置读取闭包、主链兼容桥、`persist_schedule()` 参数爆炸、`if best is None` 归属、`gantt_critical_chain.py` / `gantt_service.py` 静默回退清理、以及 `database.py` / `backup.py` / `schedule_repo.py` 热点拆分的命中度都比较高；相较前序版本，主链与数据层的收口已经明显更严谨。\n\n本轮新增确认的关键问题主要集中在 task4：\n\n1. **调度配置的“单一事实源”仍未覆盖配置页面与页面展示元数据**。task4 目前只覆盖后端配置服务、快照、校验器、算法入口与摘要侧读取点，但当前 `web/routes/scheduler_config.py` 与 `templates/scheduler/config.html` 仍直接硬编码 `algo_mode`、`objective`、`dispatch_mode`、`dispatch_rule`、`freeze_window_*` 的选项、标签与提示语；`ConfigService` 目前也只提供 `get_available_strategies()`，没有为其余字段提供统一可消费的字段元数据出口。这意味着即使 task4 完成，执行层和页面层之间仍会保留第二套字段枚举与展示语义，plan 声称的“新增配置字段只需一处登记”并不能真正成立。\n\n2. 作为次要观察，task5 对 `CalendarService/ConfigService` 的延迟导入收口方向是对的，但描述里仍残留少量 task3 之后不应继续出现的旧根路径措辞；这属于文案一致性问题，建议修订时顺手清掉，以保持 plan 自己设定的“后续步骤只引用迁移后路径”规则完整。",
      "conclusionMarkdown": "任务4-7的大方向已基本能支撑“少兼容桥、少静默回退”的目标，但 task4 还需要把配置页面元数据纳入同一字段注册表或统一读取门面，否则配置领域仍会保留前后端双事实源。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 783,
          "lineEnd": 850,
          "excerptHash": "sha256:m2a"
        },
        {
          "path": "web/routes/scheduler_config.py",
          "lineStart": 274,
          "lineEnd": 304,
          "excerptHash": "sha256:m2b"
        },
        {
          "path": "web/routes/scheduler_config.py",
          "lineStart": 367,
          "lineEnd": 388,
          "excerptHash": "sha256:m2c"
        },
        {
          "path": "templates/scheduler/config.html",
          "lineStart": 269,
          "lineEnd": 365,
          "excerptHash": "sha256:m2d"
        },
        {
          "path": "core/services/scheduler/config_service.py",
          "lineStart": 359,
          "lineEnd": 360,
          "excerptHash": "sha256:m2e"
        },
        {
          "path": "core/services/scheduler/config_service.py",
          "lineStart": 397,
          "lineEnd": 423,
          "excerptHash": "sha256:m2f"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 667,
          "lineEnd": 673,
          "excerptHash": "sha256:m2g"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 954,
          "lineEnd": 959,
          "excerptHash": "sha256:m2h"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "templates/scheduler/config.html"
        },
        {
          "path": "core/services/scheduler/config_service.py"
        }
      ],
      "reviewedModules": [
        "任务4 调度配置单一事实源",
        "任务5 排产主链上下文与兼容桥",
        "任务6 算法主流程与类型约束",
        "任务7 数据基础设施与 Gantt 热点"
      ],
      "recommendedNextAction": "进入第三轮，重点核对任务8-10的前端协议、测试迁移和文档校验是否已经具备可验证的退出条件。",
      "findingIds": [
        "task4-config-ui-second-source"
      ]
    },
    {
      "id": "m3",
      "title": "第三轮：任务8-10的前端协议、测试迁移与文档轨道核对",
      "status": "completed",
      "recordedAt": "2026-04-06T11:25:27.951Z",
      "summaryMarkdown": "已完成对任务8、任务9、任务10的第三轮核对。总体看，plan 已经吸收了此前最明显的三个缺口：试点页专项回归被写回 task8，`regression_frontend_common_interactions.py` 与 `test_ui_mode.py` 已纳入 task9 首批迁移范围，task10 也明确要求 `check_quickref_vs_routes.py` 追加关键路径存在性校验。这说明界面层、测试层、文档层的闭环设计比前几版更成熟。\n\n不过，第三轮仍确认一个会影响“是否真正完成前端协议收口”的问题：\n\n1. **task8 缺少对 DOM 协议落地程度的直接退出条件**。plan 在关键结构决策和 task8 步骤5中明确提出要转向 `static/js/page_boot.js + data-page + data-*`，并要求不再扩张 `window.__APS_COMMON__`、`window.__APS_GANTT__`。但 task8 的完成判定与验证命令并没有任何一条直接检查 `page_boot.js` 是否被接入、目标页面是否真的产出 `data-page`、或现有全局命名空间是否停止继续承担新增初始化职责。当前仓库里 `templates/base.html` 仍没有 `data-page`，`static/js/common.js` 与 `static/js/gantt.js` 仍以全局命名空间为核心入口，而 `tests/regression_frontend_common_interactions.py` 还在显式断言 `window.__APS_COMMON__` 必须存在。这意味着执行者完全可能“新增了 page_boot.js、保留了旧全局入口、现有测试照样通过”，但并没有真正完成 plan 自己宣称的协议迁移。\n\n2. task9、task10 的方向目前没有再发现新的主阻塞点：测试分层、共享仓库根辅助、速查表双重校验、文档入口链的设计都已比旧版严谨，可在修正 task8 的退出条件后继续使用。",
      "conclusionMarkdown": "任务8-10整体已接近可执行，但 task8 还需要补一个面向 `page_boot.js/data-page` 的明确门禁或完成判定，否则“前端初始化已转向 DOM 协议”仍可能停留在口号层。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 235,
          "lineEnd": 241,
          "excerptHash": "sha256:m3a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1292,
          "lineEnd": 1296,
          "excerptHash": "sha256:m3b"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1329,
          "lineEnd": 1359,
          "excerptHash": "sha256:m3c"
        },
        {
          "path": "templates/base.html",
          "lineStart": 50,
          "lineEnd": 135,
          "excerptHash": "sha256:m3d"
        },
        {
          "path": "static/js/common.js",
          "lineStart": 270,
          "lineEnd": 305,
          "excerptHash": "sha256:m3e"
        },
        {
          "path": "static/js/gantt.js",
          "lineStart": 1,
          "lineEnd": 6,
          "excerptHash": "sha256:m3f"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py",
          "lineStart": 40,
          "lineEnd": 119,
          "excerptHash": "sha256:m3g"
        },
        {
          "path": "tests/check_quickref_vs_routes.py",
          "lineStart": 16,
          "lineEnd": 23,
          "excerptHash": "sha256:m3h"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "templates/base.html"
        },
        {
          "path": "static/js/common.js"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        }
      ],
      "reviewedModules": [
        "任务8 页面组装、Excel 页面流程、模板树与前端协议",
        "任务9 测试目录重整与覆盖率口径",
        "任务10 文档、证据与审计轨道"
      ],
      "recommendedNextAction": "基于三轮结果做一次小规模修订：补 task1 启动链定向回归、修 task3 非 scheduler 域门面时序、扩 task4 到配置页面元数据、补 task8 的 DOM 协议门禁；完成后再把该 plan 作为唯一权威实施计划。",
      "findingIds": [
        "task8-dom-protocol-exit-gap"
      ]
    }
  ],
  "findings": [
    {
      "id": "task1-bootstrap-regression-gap",
      "severity": "medium",
      "category": "test",
      "title": "启动链改造缺少定向回归护栏",
      "descriptionMarkdown": "plan 在 task1 中把 `web/bootstrap/` 多个启动链文件纳入静默回退治理，但验证命令只固定到 `tests/test_architecture_fitness.py` 与统一门禁入口，未把现有的运行时探测、启动契约、停机链路、插件装配可观测性回归显式绑定到 task1。证据见 plan 第283-295、316-320、365-389 行，而仓库已存在 `tests/regression_runtime_probe_resolution.py`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_startup_host_portfile.py`、`tests/regression_plugin_bootstrap_config_failure_visible.py`、`tests/regression_runtime_stop_cli.py`。若执行者仅按 plan 自带验证收口，启动链行为回归存在被漏检的风险。",
      "recommendationMarkdown": "在 task1 的“验证命令”或“重点回归集合”中，至少显式纳入运行时探测、启动契约、插件装配和停机链路四类现成回归，避免统一门禁入口成为过宽占位。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/regression_runtime_probe_resolution.py"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_startup_host_portfile.py"
        },
        {
          "path": "tests/regression_plugin_bootstrap_config_failure_visible.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        },
        {
          "path": "web/routes/process.py"
        },
        {
          "path": "web/routes/system.py"
        },
        {
          "path": "web/routes/personnel.py"
        },
        {
          "path": "web/routes/equipment.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task3-domain-facade-ordering-conflict",
      "severity": "high",
      "category": "maintainability",
      "title": "非 scheduler 域门面改造时序冲突",
      "descriptionMarkdown": "task3 的批次边界第683-687 行明确规定 `process/personnel/equipment/system` 四个域在批次1只建子包与空 `__init__.py`，实际文件迁移延后到 task8；但步骤7 第723-726 行又要求 `process.py`、`personnel.py`、`equipment.py`、`system.py` 统一改成 `from .domains.<领域> import ...` 的包内导入。当前这些根层门面仍直接导入同目录下的真实模块，如 `web/routes/process.py:18-30`、`web/routes/system.py:16-26`。如果按现有文字执行，批次1将出现“目标子包为空，但根层门面已改向新子包”的中间态断裂。",
      "recommendationMarkdown": "把 task3 步骤7 明确拆成两段：批次1仅改 `scheduler.py`；其余四个根层门面要么保持旧导入直到 task8 完成物理迁移，要么在 task3 同步创建域内转发模块后再切换，禁止留给执行者自行猜测。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "tests/regression_runtime_probe_resolution.py"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_startup_host_portfile.py"
        },
        {
          "path": "tests/regression_plugin_bootstrap_config_failure_visible.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        },
        {
          "path": "web/routes/process.py"
        },
        {
          "path": "web/routes/system.py"
        },
        {
          "path": "web/routes/personnel.py"
        },
        {
          "path": "web/routes/equipment.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task4-config-ui-second-source",
      "severity": "medium",
      "category": "maintainability",
      "title": "配置页面仍保留第二套字段事实源",
      "descriptionMarkdown": "task4 在 plan 中把目标定义为“调度配置字段只有一处登记”，但文件职责与步骤只覆盖 `config_field_spec.py`、`config_snapshot.py`、`config_validator.py`、`config_service.py`、`config_presets.py`、算法入口和 `schedule_summary_freeze.py`，未覆盖 `web/routes/scheduler_config.py` 与 `templates/scheduler/config.html`。当前这两个文件仍硬编码 `algo_mode`、`objective`、`dispatch_mode`、`dispatch_rule`、`freeze_window_*` 的选项、标签与提示语，而 `ConfigService` 目前只有 `get_available_strategies()` 这一个页面可消费元数据出口。结果是：即使 task4 完成，页面层仍然需要手工同步第二套字段枚举与文案，无法真正达到“新增配置字段只需一处登记”的目标。",
      "recommendationMarkdown": "把 `web/routes/domains/scheduler/scheduler_config.py`（任务3后路径）与 `templates/scheduler/config.html` 的字段选项、标签、提示语纳入 task4 范围：至少要求页面渲染从字段注册表或统一字段门面生成可选项与展示文案，避免前后端双事实源并存。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "templates/scheduler/config.html"
        },
        {
          "path": "core/services/scheduler/config_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "task8-dom-protocol-exit-gap",
      "severity": "medium",
      "category": "javascript",
      "title": "DOM 协议迁移缺少直接门禁",
      "descriptionMarkdown": "plan 在关键结构决策和 task8 中把 `static/js/page_boot.js`、`data-page`、`data-*` 设为前端初始化的新协议，但完成判定与验证命令没有直接检查这些约束是否真正落地。当前 `templates/base.html` 仍没有 `data-page`，`static/js/common.js` 与 `static/js/gantt.js` 仍以 `window.__APS_COMMON__`、`window.__APS_GANTT__` 为核心入口，而 `tests/regression_frontend_common_interactions.py` 只验证旧全局命名空间与脚本顺序，不验证 `page_boot.js` 或 `data-page`。这样会导致 task8 即使全部自带验证通过，也可能只是“新增了新协议文件，但旧协议仍是主入口”，无法证明前端初始化已经真正完成收口。",
      "recommendationMarkdown": "给 task8 增加一条明确门禁：至少校验 `static/js/page_boot.js` 被 `templates/base.html` 或等价公共模板接入、目标页面根节点产出 `data-page`、且新接入页面不再以扩张 `window.__APS_COMMON__`/`window.__APS_GANTT__` 作为新增初始化入口。若短期必须保留旧全局入口，也应把“哪些页面已切到 DOM 协议、哪些页面仍在旧协议”写进完成判定。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "templates/base.html"
        },
        {
          "path": "static/js/common.js"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "tests/regression_frontend_common_interactions.py"
        },
        {
          "path": "tests/check_quickref_vs_routes.py"
        }
      ],
      "relatedMilestoneIds": [
        "m3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:40dbbe048c1ea492dd1ea51c983ef2fa51205ba2bd89c577fa394204ec195d6c",
    "generatedAt": "2026-04-06T11:25:41.706Z",
    "locale": "zh-CN"
  }
}
```
