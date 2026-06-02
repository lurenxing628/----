---
doc_type: audit
slug: foundation-maturity-round2-ABCG
scope: 第二轮函数级深钻 · 已完成的四个专题（A shim退役 / B 死代码确权 / C helper去重 / G 甘特标签一致性）
summary: 在 codemap 静态底座 + 第一轮体检基础上，对四个最具体可执行的专题做函数级深钻，产出可直接动手的整改方案
status: current
created: 2026-06-02
last_reviewed: 2026-06-02
tags: [aps, audit, refactor-seed, shim, dead-code, dedup, gantt]
depends_on: [foundation-maturity]
implements: []
---

# 第二轮深钻 · 已完成专题 A/B/C/G

> 这四个专题在 Workflow 全模块深钻之前已用独立 Agent 完成，证据扎实、可直接执行。
> 另有 D（命名）/E（分层归属）/F（门禁减负）+ 14 个模块深钻由 `aps-foundation-deepdive` workflow 承接。

---

## 专题 A：shim 退役全景图

### 最关键发现：shim 删不掉的真因是"反向锁死的契约测试"
不是普通测试旧导入路径，而是 `tests/test_sp05_path_topology_contract.py` **主动断言"每个 shim 必须存在、`old is new`、`__all__` 逐字段相等"**（第 15-121 行的 `SERVICE_STRONG_COMPAT_MODULES`/`SERVICE_BEHAVIOR_COMPAT_SYMBOLS`/`ROUTE_COMPAT_MODULES`）。配套 `tests/regression_scheduler_wrapper_import_order_contract.py` 参数化覆盖全部 9 个 web 路由 shim。两者都登记进 `tools/test_registry_groups_scheduler.py:28-31` 的 `QUALITY_GATE_GUARD_TESTS`（必跑、不可静默 DROP）。

**退役顺序铁律**：必须先反转/退役这两个守卫测试，否则删任何 shim 都会让门禁红，且无法靠 xfail 绕过（台账 `max_registered_xfail: 0`）。

### 第二关键发现：第一轮"生产全 0 引用"对 config_service 不成立
`tools/capture_networkx_phase0_baseline.py:17` 真实引用 `core.services.scheduler.config_service`。它逃过 sp05 扫描因为 `PRODUCTION_LEGACY_IMPORT_SCAN_ROOTS=("core","web")` 不含 tools/。建议把 "tools" 加进该扫描根防回潮。

### shim 清单（退役动作）
**A 组 scheduler 服务层顶层 shim（13个，生产引用除 config_service=1 外全 0）**：
schedule_optimizer / schedule_optimizer_steps（sys.modules 强别名）、schedule_input_builder / schedule_input_collector / schedule_persistence / schedule_summary / schedule_summary_types / config_service / config_snapshot / config_validator / freeze_window（逐符号 re-export）、schedule_orchestrator（__getattr__ 惰性）→ 改测试+守卫后删。

**B 组 web 路由 shim（9+1个，生产引用全 0）**：
scheduler_analysis/batch_detail/batches/config/excel_calendar/ops/run/week_plan（sys.modules 强别名）、scheduler_excel_batches（逐符号 re-export，额外暴露私有 helper 给测试 patch）、_scheduler_compat.py（被9个shim调用，最后删）。

**必须保留（非死 shim）**：
- `core/services/scheduler/degradation_messages.py` —— 7+ 生产消费者的活跃门面。
- `web/ui_mode.py` —— render_ui_template(37处)/init_ui_mode 是全站渲染入口；仅第 58-76 行 19 个私有 re-export 无人用可选删，文件必须留。

**最干净的第一刀**：`core/services/scheduler/history_summary_parser.py` 生产+测试 import 全 0，唯一阻碍是 `tests/test_phase6_no_result_summary_route_parser.py:24` 用 read_text 读它源码做断言，改那一行即可直接删。

### 执行顺序
1. 删 history_summary_parser（改 1 处源码字符串断言）
2. 反转两个守卫契约测试 → 改 config_service 的 tools/ 生产引用 → 批量改 93 个测试文件旧导入 old→new → 删 21 个 shim + _scheduler_compat
3. 与在途前端 roadmap **零冲突**（roadmap 引用的全是 domains/ 转发目标真身，不是顶层 shim）

---

## 专题 B：死代码确权

### 组1：ScheduleRepository 明细查询确已死（可删 8 方法）
`data/repositories/schedule_repo.py` 生产实际只用 5 个方法（get/bulk_create/list_by_version/list_by_version_with_details/list_version_rows_by_op_ids_start_range）。
**可删（生产 0 调用）**：`list_between`(61,全仓零引用最干净)、`list_overlapping_with_details`(114)、`list_dispatch_rows_with_resource_context`(128)、`list_by_machine`(170)、`create`(183)、`delete`(217)、`delete_by_version`(220)、`delete_by_op`(223)。`get_version_time_span`(36) 仅 benchmark 用，视取舍。
新路对应：→ SchedulePlanQueryRepository 的 list_detail_rows_between / list_dispatch_rows / get_plan_time_span（支持 adopted/候选/场景三源）。
**配套删测试**：`tests/test_schedule_repository_detail_queries.py` 的 7 个 test（保留测存活方法的 :185）、`regression_schedule_service_facade_delegation.py` 对应类型断言行、`regression_gantt_critical_chain_unavailable.py:57` 的失效 monkeypatch。
**附带**：`core/services/report/report_engine.py:66-67` 有两处死实例化字段（self.schedule_repo/self.history_repo 从不调用），顺带清掉。

### 组2：独立 persist_schedule 生产零调用（可降级合并）
`run/schedule_persistence.py:322` 独立 persist_schedule 生产 0 调用。生产实走 `persist_schedule_run_with_candidates`（schedule_service.py:23 误导性别名 `as persist_schedule`）。
唯一行为差：独立版不调 `delete_without_schedule_history()`（候选清理）。可表达为 candidates 版 candidate_comparison=None（迁 4 个测试需给 svc 桩补 candidate_repo）。
先改两处结构契约（test_sp05:53-57 的 __all__、generate_conformance_report.py:292）再删。**建议单独 PR，风险高于组1**。

### 组3：backup vs migration_backup —— 纠正第一轮定性，不是死代码
逐方法看，两者是迁移闭环的**互补两半**：backup.py 在线 backup API（用户手动恢复流 system_backup_actions.py:27），migration_backup.py 文件 replace+winerror 重试+sidecar 清理（迁移自动回滚 migration_runner.py:257）。机制差异刻意、调用方完全分流。**保留两套不合并**——强合并会丢各自的锁重试/sidecar 正确性。本组不产出删除项。

### 命名债建议
即使暂不删独立 persist_schedule，也应去掉 schedule_service.py:23 的 `as persist_schedule` 别名、直接用全名，消除"两个 persist_schedule"歧义。

---

## 专题 C：helper 去重与公共 util（codemap 精确计数）
codemap dup_bodies 实测 15 簇 94 处。重点：
- **`_text`(23处) + `_normalize_text`(13处) = 36 处字符串清洗同义函数**，横跨 models/services/web。最大单一重复。
- 跨层成组复制：`_parse_mode`/`_ensure_unique_ids`/`_read_uploaded_xlsx` 在 4 个 Excel 路由 `*_bp.py`（说明从同一模板拷出）。
- `_positive_int`(3)、`_text_or_none`(3)、`_has_value`(4)。
- 门禁内部：`_sha256_text`(5)/`_sha256_file`(4) 在 tools/ 复制。
**惯用样板不该合并**：to_dict(8)/delete_all(8)/from_row/_columns_sql(3)/list_as_dicts(3) 是 dataclass/repo 模式。
**落点建议**：core/shared/ 下建文本清洗/整数解析 util。**合并前必须逐字比对函数体差异**（LLM 复制常引入细微不一致，如是否 strip、None 处理），有差异处标人工确认。Python 3.8 约束：util 不能用 3.9+ 语法。
> 详细逐处差异对照由 workflow 的 crosscut:dedup 专题产出。

---

## 专题 G：甘特双路径标签一致性（P0，可独立先做）

### 问题
`gantt_tasks.py:171/179/193` 与 `gantt_critical_chain.py:34/42/48` 同名标签函数（_detail_part_label/_detail_operation_label/_public_task_label）行为漂移：
- _detail_part_label：tasks 版有 piece_id 兜底 + 空值返 "-"；critical_chain 版无兜底 + 空值返 ""。
- 后果：对 op_code/seq/op_type/part 皆空但 piece_id="piece-a" 的工序行，甘特任务条显示 "piece-a"，关键链 tooltip 显示 "B1 工序"——**同一工序两处不同名，改一处不报错**。

### 数据源确认
两条路径都经 `data/repositories/schedule_detail_query.py:92` 的 `build_schedule_detail_sql`，行字段形状完全一致；分叉纯在标签函数。adopted 关键链取全版本行、甘特条取本周行，落在当前周又在关键链上的工序会被两套各标一次（同屏可见分叉）。

### 方案
以 **gantt_tasks 版为正确基线**（信息更全、含 piece_id 兜底、详情区刚 done 零风险），关键链向它对齐。
- piece_id 是已公开业务件号（详情区 gantt_popup.js:109 已兜底），保留不违反"不露 op_id"红线。
- 落点：扩充既有 `core/services/scheduler/_sched_display_utils.py`，新增 3 个公开函数 = gantt_tasks 现实现逐字搬运。两文件改为 import 别名，调用点不动。
- 唯一用户可见变化：关键链边对 piece_id-only 工序从 "{batch}工序" 变为显示 piece_id（需签字确认接受）。
- 附带：gantt_critical_chain.py:9-27 自带的 _parse_dt/_fmt_dt 与共享版逐行等价，可顺带折叠（或留给 dedup 专题）。

### 受影响测试
`tests/regression_gantt_task_detail_panel_contract.py`（现有断言走 op_code 分支不变，**需新增 1 条一致性回归**：构造 piece_id-only 行断言 build_tasks 的 task_label 与 critical_chain 边的 from_label/to_label 逐字相等）。与在途 gantt-task-detail-panel(已done) 零冲突。
