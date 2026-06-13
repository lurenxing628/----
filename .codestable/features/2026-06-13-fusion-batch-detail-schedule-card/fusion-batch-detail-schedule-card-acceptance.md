---
doc_type: feature-acceptance
feature: 2026-06-13-fusion-batch-detail-schedule-card
status: accepted
summary: 批次详情「排程去向卡」验收——9 节核对全过、checks c1-c8 全 passed、架构 doc 与 roadmap 已归并回写。
tags: [frontend, scheduler, batch-detail, module-w, execution-fact]
---

# fusion-batch-detail-schedule-card 验收报告

对照 `fusion-batch-detail-schedule-card-design.md`（status: approved）逐节核对。实现已落地（git status 见新增/修改文件），daily gate 全绿（1713 并行 + 221 串行 + 5 focused + 静态检查），Phase 2 实现审核 Codex + UltraCode 双零阻塞收口。

## 1. 接口契约核对（design 2.1）

| 契约项 | 设计 | 实现 | 结论 |
|---|---|---|---|
| `schedule_placement` 字典形状 | state/message/version_label/generated_at_label/strategy_label/op_count/span_label/gantt_link/op_rows | `web/viewmodels/scheduler_batch_schedule_placement.py::build_schedule_placement` 返回该 9 键 | ✓ 一致 |
| op_rows 公开字段（8 键） | op_label/plan_machine_label/plan_operator_label/execution_status_label/actual_*_time_label/actual_summary_label/has_execution_record | `_placement_op_row` 装配，`_PLACEMENT_OP_LABEL_KEYS` 锁 5 个现场键 + 3 个计划 label；单测 `test_op_row_*` 精确断言键集 == 8 | ✓ 一致，无裸 actual_start_time/actual_end_time 下传 |
| 4.10 唯一入口 | `facts_by_op_id_for_plan_rows(rows, plan_fields)` 不传 include_op_ids | route `_resolve_schedule_placement:304` 调用；ok 态路由测试 `_FakeProvider` 断言 `"include_op_ids" not in kw` + plan_fields 键集 == {version,source_table,effective_plan_role,scenario_id} + effective_plan_role=="adopted" + rows 带 schedule_id/version/batch_id | ✓ 完整身份契约钉死 |
| 单次解析 | resolve_plan 一次 → list_plan_detail_rows_all_for_resolution（全 kwarg、复用 resolution） | route:279-286 解析一次，rows 与版本级 span 共用同一 resolution | ✓ 无二次 resolve |
| build_workbench_plan_context / build_workbench_link | viewmodel 经胶囊取 *_label + gantt 链接 | viewmodel 相对 import `.scheduler_workbench_links`，ctx 注入 version+date_from/date_to+batch_id | ✓ 一致 |

无接口偏差。

## 2. 行为与决策核对（design 1 / 2.2 / 2.4 / 2.5）

| 决策 | 实现验证 | 结论 |
|---|---|---|
| 数据范围 adopted@get_latest_version() | route 取 `get_latest_version()`、角色硬钉 `ROLE_ADOPTED`；URL 无 version/plan_role 维度 | ✓ |
| 整段 try/except + current_app.logger.exception + 诚实 error 态 | `_resolve_schedule_placement` 整段（含 get_latest_version 与 g.db/provider 构造）在 try 内，`except Exception: current_app.logger.exception(...)` + error 态，不冒泡不静默吞 | ✓ 不 500、不静默 |
| 诚实五态 | get_latest_version≤0→no_official_plan；本批次 rows 空 + 版本级 span 区分 plan_empty/not_placed；正常 ok；异常 error | ✓ viewmodel 5 态测试 + route 测试覆盖 |
| span 日期解析在路由层、跳坏值各自独立 min/max | `_placement_span` parse_dt 跳坏值，starts/ends 独立 min/max，全坏→(None,None,"时间记录异常")；单测 all-valid/mixed/all-bad/empty 四态 | ✓ |
| hist None 优雅降级 | `history_present=hist is not None`，None 时不喂 generated_at/strategy（走「-」非 error） | ✓ |
| int 强转防类型漂移 | `_placement_op_row` 用 `facts.get(int(row.get("op_id") or 0))` 对齐 gantt 抽取源惯例；单测 `test_op_row_string_op_id_still_hits_via_int_coercion` 覆盖字符串路径命中 | ✓ 非阻塞建议已采纳 |
| 微重构（拆文件）只搬不改 | `execution_detail_meta` 全仓单一定义点（`execution_fact_presentation.py:40`），gantt_tasks 改 import 公开名（:42 import、:217 调用），gantt 回归全绿 | ✓ 行为零变 |
| viewmodel 禁 import core.services / 不碰 rows/fact | viewmodel 仅相对 import 同层 links；fact→label 与 span 解析均在路由层 | ✓ 架构适应度门禁 39 passed |

**挂载点反向核对（grep + 沙盘推演）**：design 2.3 列 3 个挂载点——① 模板 L28-78 `{% if schedule_placement %}` 卡；② route `_resolve_schedule_placement` + render_template `schedule_placement=` 实参；③ 新 viewmodel 文件。沙盘：删任一项 → 卡消失/无数据/无装配，feature 即不存在。结构归并项 execution_fact_presentation 不在挂载点（gantt 也消费，删它是破坏单源非卸载本 feature）。✓ 边界清晰可卸载。

无行为偏差。

## 3. 验收场景核对（design 3）

实测以测试 + grep 锁定（浏览器目检五态已在 checklist s5 完成；模板渲染由 render 测试 test_batch_detail_linkage 锁）：

| check | 场景 | 验证 | 结论 |
|---|---|---|---|
| c1 | 正常态卡 + 定位按钮带日期窗口 | route ok 态测试断言 op_label/plan_*_label/gantt_link.disabled=False/gantt_batch=B001；workbench_links 合同测试钉死 gantt URL 带 plan_role=adopted/start_date/end_date/gantt_batch | passed |
| c2 | 现场混合 + 外协 | `_placement_op_row` 单测 facts 命中（has_record=True+ISO 时间）/未命中（暂未记录现场实际）/外协（外协 供应商X / 外协/未分配）；presentation 单测 ISO 标签 | passed |
| c3 | 三类空态区分 | route 契约测试**显式断言**覆盖 ok 与 no_official_plan（test_..._uses_request_services 补 `assert schedule_placement["state"]=="no_official_plan"`）两态；plan_empty/not_placed/error 三态由 viewmodel 单测（直接喂 state）覆盖，其 route 分支（本批次 rows 空 → `version_span is None` 区分）由 viewmodel 单测 + 服务 Optional 返回契约共同保证，无独立 route e2e（route 分支足够简单） | passed |
| c4 | 取数失败 logger.exception + 坏时间 disabled | error 态 logger.exception 留栈；`_placement_span` all-bad→"时间记录异常"+无日期→gantt_link disabled→模板三重守卫不渲染按钮 | passed |
| c5 | 身份护栏反向（限新卡） | grep 模板 L28-78 零 op_id/schedule_id/scenario_id/source_table/candidate_id；op_rows 键集 == 8 公开键；`op_id=0`@301/`data-op-id`@128 在既有可编辑卡（明确排除）；gantt_link.url 合同参数豁免 | passed |
| c6 | 明确不做反向 | grep：无 publish_workbench_navigation_context、无新卡 batch.status 门控（b.status@366 是既有基础卡状态显示）、无 url_for 直拼 gantt、batch_detail 未进 EXPECTED_PAGE_SIGNALS、无写排产调用 | passed |
| c7 | 既有锚点不破 | test_batch_detail_linkage（靠 `{% if %}` 守卫）+ test_scheduler_batch_detail_route_contract（既有 + 新增 ok 态）全绿 | passed |
| c8 | gantt 单源不变 | gantt 任务测试全绿、execution_detail_meta 全仓单一定义点、viewmodel 无 core.services import | passed |

## 4. 术语一致性（design 0）

- 「排程去向卡 / schedule_placement / placement_op_row」全仓零生产冲突（design 0 节已 grep）；与既有「批次工序（可编辑补充）」卡 section-title 显式区分（「最新方案排程去向」vs 既有卡）。
- 「最新方案」= adopted@get_latest_version()，与甘特默认同口径，代码用 ROLE_ADOPTED + get_latest_version()，未用 list_recent(limit=1)。
- 现场公开标签术语（execution_status_label/actual_*_label/has_execution_record）与 4.10 / gantt 详情面板一致，单源 execution_detail_meta 产出。
无术语漂移。

## 5. 架构归并（design 4）— 已实际写入

1. **ARCHITECTURE.md 第 3 节模块索引**：新增两条 bullet——①「现场事实公开标签单源（契约 4.10）」记录 `execution_fact_presentation.execution_detail_meta` 为 ExecutionFact→公开标签全站唯一实现（gantt 与批次卡共消费）；②「批次详情排程去向卡」记录路由取数编排/五态/viewmodel 边界/门禁。`last_reviewed` 更新 2026-06-13。
2. **roadmap 4.10 契约 file:line 漂移**：原 `gantt_tasks.py _execution_detail_meta:152-177` 改为 `execution_fact_presentation.execution_detail_meta` 单源表述（含「新消费方禁内联/重复实现」措辞，顺带覆盖 gantt_week_plan 那类窄实现）。
3. **gantt_week_plan.py:91 注释**：已在 checklist s1 指向 `execution_fact_presentation.execution_detail_meta`（本次核对确认）。
4. **契约遵守复核**：模块 W（只消费既有服务/公开 *_label）+ 4.10（唯一入口/公开标签/禁透传/非 adopted 无事实）+ 4.7（硬钉 adopted、URL 无 plan_role 维度天然满足）+ 4.2（*_label 经 build_workbench_plan_context 单点）+ 第 11 条 WorkbenchLink 合同（gantt 目标）。facts_by_op_id_for_plan_rows 生产消费方落地后共 6 处（design 开工时既有 5 处 + 本卡）：gantt_adjustment_publish_service.py:361 / gantt_service.py:243 / execution_snapshot.py:115 / run/schedule_execution_guardrails.py:213 / web/routes/dashboard.py:145 / 本卡 scheduler_batch_detail.py:304（定义点 execution_fact_provider.py:131）。

## 6. requirement 回写

**结论：跳过。** design frontmatter `requirement:` 为空，与全部同类 fusion 接线 feature（dual-track-retirement / runtime-log-viewer / backup-health-hint / handrolled-links-adoption 等）一致——W 模块接线类 feature 不自带 req。本卡把既有后端能力接到前端（adopted 计划行 ← `gantt-readonly-result-view`；现场事实 ← `shop-floor-execution-feedback`），非新能力，无需 backfill 或升级。

## 7. roadmap 回写 — 已实际写入

design frontmatter 有 `roadmap: aps-frontend-fusion` / `roadmap_item: fusion-batch-detail-schedule-card`，必须回写：

- **items.yaml**：item 18 `status: in-progress → done`，notes 追加收口说明（list_plan_detail_rows_all_for_resolution 单次解析 + facts 不传 include_op_ids + 抽 execution_fact_presentation 单源）。`validate-yaml.py` 通过。
- **主文档**：第 18 条加 `✅ done（2026-06-13，feature 2026-06-13-fusion-batch-detail-schedule-card，Codex+UltraCode 实现审核零阻塞收口）` + 落地摘要（对齐第 11 条 done 格式）。
- 两份一致（items.yaml status=done ↔ 主文档 ✅ done）。

## 8. attention.md 候选盘点

- 无新的命令/路径/环境陷阱产生（纯应用层 Flask 路由 + viewmodel + 模板，沿用既有 .venv/pytest/gate 流程）。
- 可沉淀的是 design 2.5「建议沉淀的 convention」：『ExecutionFact→前端公开标签只走 execution_fact_presentation.execution_detail_meta 单源；现场 status label 统一走 execution_status_label，新消费方禁内联状态文案/重复实现 4.10 标签映射』——属长期 convention，宜走 `cs-decide` 归档而非 attention.md。
- 无 attention.md 候选条目。

## 9. 遗留

- **超出范围的观察（design 2.5，不阻塞）**：批次详情页「可编辑工序表」（工艺模板视图）与本卡「已排方案工序表」（已排结果视图）是两套工序视图，长期可统一页面信息架构，属页面 IA 重构，后续走 `cs-refactor`，非本卡范围。
- **convention 归档建议**：上述 4.10 单源 convention 建议 `cs-decide` 归档（design 2.5 已识别为稳定模式）。
- 无未处理偏差，无未通过 check。
