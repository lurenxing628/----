# 2026-04-16 SP05 路径拓扑与当前工作区深审结论

本结论基于 3 轮只读审查。Round 1/2 使用调查子代理并行取证与反证，Round 3 使用独立审核子代理做对抗复核；主代理只做源码复读、测试复跑与裁决。审查对象为提交 `24f4c93e9660cf920fb7b71426ade459d32a6006` 加当前工作区未提交修改。

## Findings

1. `[高] legacy wrapper 已被反向升级为真实入口，直接破坏 SP05 路径拓扑契约。`

`core/services/scheduler/config_snapshot.py:3-5` 重新导出 `ensure_schedule_config_snapshot`，把原本只用于兼容旧 import 的 wrapper 扩口；随后 `core/services/scheduler/run/schedule_optimizer.py:16,315` 与 `core/services/scheduler/run/schedule_optimizer_steps.py:14,29,41,104,316` 又从这个旧 wrapper 导入并调用该函数。根因链很直接：真实入口已经在 `core/services/scheduler/config/config_snapshot.py`，但新生产代码没有依赖真实模块，反而让 wrapper 承担运行时契约入口。这不是“暂时桥接”，而是设计倒退，违反了“新生产代码只能依赖真实入口、legacy wrapper 只能做兼容”的 SP05 约束，也违背了“不过度兜底”的设计初衷。验证上，`python -m pytest -q tests/test_sp05_path_topology_contract.py` 当前稳定失败 2 项，其中 2 项都正中这一问题：`core.services.scheduler.config_snapshot.__all__` 扩口，以及 `schedule_optimizer*` 反向导入旧 wrapper。

2. `[高] summary 子模块存在同名 helper 后定义覆盖前定义，且已经带来可复现回归。`

`core/services/scheduler/summary/schedule_summary_freeze.py:10-18` 先定义了基于 `cfg_get` 的 `_cfg_freeze_window_state`，但 `95-101` 又用 `getattr` 重新定义同名函数；`core/services/scheduler/summary/schedule_summary_degradation.py:14-17` 先定义了基于 `cfg_get` 的 `_cfg_yes_no_flag`，但 `324-325` 再次以 `getattr` 重定义。`core/services/scheduler/summary/schedule_summary.py:30-43` 直接从这些模块导入 helper，运行时绑定到的是后定义版本，于是前面面向 snapshot/config-adapter 的契约被旁路。结果已经稳定复现为两个额外失败：`python tests/regression_schedule_summary_freeze_state_contract.py` 失败，表现为 `freeze_state=active` 未透传；`python tests/regression_schedule_summary_algo_warnings_union.py` 失败，表现为 `resource_pool.degraded` 标记缺失。这说明当前实现不是“优雅收口”，而是半迁移状态下的覆盖式回退，已经引入新 bug。

3. `[中] holiday_default_efficiency 的兼容解释重新膨胀回路由层，而且服务侧仍保留双读口径。`

`web/routes/domains/scheduler/scheduler_calendar_pages.py:12-31` 与 `web/routes/personnel_calendar_pages.py:13-32` 复制了几乎相同的 `_resolve_page_holiday_default_efficiency()`：都调用 `cfg_svc.get_snapshot(strict_mode=False)`，都自己扫描 `snapshot.degradation_events`，都在路由层拼 warning 文案。与此同时，`core/services/scheduler/calendar_admin.py:40-51` 的 `_get_holiday_default_efficiency()` 仍保留“异常即回默认值”的口径，`56-70` 的 `_legacy_get_holiday_default_efficiency()` 又保留 relaxed snapshot 兼容口径。根因不是单点实现失误，而是“fallback 被下沉后换个地方继续存在”：本应被统一封装的退化解释重新散落到 route/service 两层，既不简洁，也偏离了“路由只做页面装配和显示决策”的目标。

4. `[中] config_field_spec 收口方向正确，但模板和错误展示链路仍是半迁移状态。`

`core/services/scheduler/config/config_service.py:314-318` 已经提供 `get_field_label()` / `get_choice_labels()` 这类统一元数据入口，`web/routes/domains/scheduler/scheduler_config.py:285-294` 也开始通过 `get_page_metadata()` 注入页面元数据；但这条链目前只覆盖 6 个字段。模板仍然保留硬编码字段展示，例如 `templates/scheduler/config.html:241` 仍直接写 `holiday_default_efficiency` 输入块；错误处理链也没有完全经由 `ConfigService`，`web/error_handlers.py:10,29` 仍直接依赖 `field_label_for()`。因此，“默认值/标签/choice/page metadata 收拢到单一事实源”这一方向是对的，但还没有落实到“模板/路由不再硬编码”的程度，暂时不能宣称该目标已经完成。

## Open questions / disputed points

1. `core/services/scheduler/summary/schedule_summary_assembly.py` 的前后两组 helper 代码块明显有遗留重复，但本轮没有拿到足够运行时证据证明它像 `freeze` / `degradation` 一样发生了同名覆盖并导致当前错误。现阶段更稳妥的裁决是“半收口遗留，需单独最小化验证”，不应直接上升为已确认缺陷。

## Change summary

`navigation_utils._safe_next_url_core()` 改成只做校验和记录、把默认回跳交给调用点显式决定，这个方向是对的，符合“不静默回退”的设计目标；当前生产调用点也已经收缩到少数几个，相关回归当前通过。`config_field_spec` 把默认值、字段标签、choice 文案和页面元数据收拢成单一事实源，这个方向也对。

当前主要问题不在方向，而在落法。SP05 试图把真实入口和兼容门面分开，但 `config_snapshot` wrapper 扩口加上 `schedule_optimizer*` 反向导入，直接抵消了这次收口；summary 层的 duplicate helper 更是把新契约打回旧行为，并且已经造成回归；路由/UI 层则仍在手写兼容解释和硬编码展示，说明职责边界还没有完全收干净。

当前验证现状如下：

- `python -m pytest -q tests/test_sp05_path_topology_contract.py`：`2 failed, 5 passed`
- `python -m pytest -q tests/regression_config_field_spec_contract.py tests/regression_schedule_optimizer_cfg_snapshot_contract.py tests/regression_error_field_label_source.py tests/regression_safe_next_url_hardening.py tests/regression_safe_next_url_observability.py`：`16 passed`
- `python -m pytest -q tests/regression_config_snapshot_strict_numeric.py tests/regression_config_validator_preset_degradation.py tests/regression_schedule_input_builder_safe_float_parse.py tests/regression_schedule_optimizer_cfg_float_strict_blank.py tests/regression_scheduler_strict_mode_dispatch_flags.py tests/regression_schedule_service_passes_algo_stats_to_summary.py tests/regression_schedule_service_reject_no_actionable_schedule_rows.py tests/regression_schedule_service_reschedulable_contract.py tests/regression_objective_case_normalization.py`：`15 passed`
- 额外复核：`python tests/regression_schedule_summary_freeze_state_contract.py` 失败；`python tests/regression_schedule_summary_algo_warnings_union.py` 失败；`python tests/regression_schedule_summary_v11_contract.py` 通过

本次任务是只读审查；未对业务代码做任何修改。
