# fusion-handrolled-links-adoption 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-handrolled-links-adoption-design.md（approved，Codex 设计两轮 BLOCK→PASS-WITH-SUGGESTIONS + 实现三轮 BLOCK→BLOCK→PASS，建议全采纳）

## 1. 接口契约核对

- [x] TARGET_PAGE_PATHS/TARGET_DEFAULT_LABELS 13 键（+history「查看排产历史」/+batch_detail「查看批次详情」）；_TARGET_QUERY_SPECS +2（plan_style version_only/none、date_style none、batch_position none、resource_style none、batch_in_path）。
- [x] 路径参数型目标新机制：`{batch_id}` 占位 quote(safe="") 替换；缺 batch_id raise 不随 disabled 摇摆（query 装配阶段 fail-loud）。
- [x] `build_history_version_links(version, *, span, span_error)` 纯数据变换（第一版带 IO 被架构适应度门禁拦下后重构——span IO 归路由层 `_load_history_span_dates`）；`build_version_picker_gantt_links(services, version, *, plan_role, scenario_id, back_to)`。
- [x] 实现期偏差 1 处已拍板回写 design：history 行 analysis 链带 adopted 上下文（与其余 4 链一致），旧稿「仅 version」是保守笔误。

## 2. 行为与决策核对

- [x] 决策 1 收编范围 7 条：history 宏 5 链（:65/:286 两调用点）+ _version_picker 2 甘特链；「去补充」/分页/form action 零 diff。
- [x] 决策 2 日期范围：先分页后装配（span 查询 ≤per_page+1，同版本缓存去重）；span None → 日期必填链接禁用给原因（有意行为变化）；span 异常宽 catch 只包获取调用，单行坏历史不炸整页。
- [x] 决策 3 公共枚举：none/version_only 显式分发未知 raise；period 在 date_style=none 短路；extra_params 禁键集（execution_review 身份键 ∪ version/view/batch/日期/period/资源 维度键）守护两新目标 query 合同（实现三审追加堵死逃逸）。
- [x] 决策 4 身份缺陷修复：选择器链 resolve_navigation_plan_context 全量身份 + FULL_PLAN_GUARD_FIELDS；场景预览保留 scenario_id（单测正向钉死）；裸 preview 由 `_preview_without_public_identity_reason` 禁用明示。
- [x] 决策 5 装配归属：system_history_links.py 新文件；analysis 链进 scheduler_analysis_links.py。行数落账：link_query 479/links 449（均 <500，余量收窄——后续 feature 进这两文件先看行数）。
- [x] 挂载点 grep 反向核对：模板 `{% macro history_version_links` 零残留；_version_picker 无裸 `url_for('scheduler.gantt_page'`；workbench_links/selected_workbench_links/version_picker_gantt_links 消费链路闭合。拔除沙盘：删 2 新文件+回退 8 文件改动即完全退出（新枚举键随 link_query 回退消失）。

## 3. 验收场景核对

- [x] S1 正常版本 5 链接 URL 形态逐目标钉死（gantt view+start/end_date、week_plan week_start、dispatch period_preset=custom、analysis adopted+日期）。
- [x] S2 无计划行版本：4 条日期必填禁用+原因，analysis 仍可点，页面 200（v8 failed 行真渲染断言）。
- [x] S3 span 异常行禁用「读取失败」原因，其余行正常（_load_history_span_dates 数据态 ValueError 钉死）。
- [x] S4 场景预览 scenario_id=S1 保留（桩贴 resolve_plan_view 合同）；plan_role 合法值口径修正（scenario_preview 是状态值非请求值）。
- [x] S5 batch_detail：`B 1/2` → `/scheduler/batches/B%201%2F2`；query 仅 back_to；缺参 raise（含 disabled=True）；中文 batch_id UTF-8 百分号编码（Codex 实测）。
- [x] S6 枚举守卫 13 键 + labels 钉死；extra_params 逃逸 11 组 case 全 raise + page=2 完整 query 对照放行。
- [x] S7 grep 反向核对全过（见第 2 节）。
- [x] S8 回归：route_view 287 + web_pages 380（系列合计 912 passed）；既有 history route contract 桩补 schedule_plan_query_service（桩贴真实合同）；daily gate passed（并行 WIP stash 隔离）。
- [x] 浏览器目检：/tmp/links_adoption_shots/ history 页（亮/暗）与 analysis?version=7（两甘特按钮可见）核过。

## 4. 术语一致性

- 「手拼链接/WorkbenchLink 合同/路径参数型目标/轻量 context」design、代码注释、测试 docstring 同口径；「上下文维度键」禁键集命名与文案一致（三审后文案改准）。

## 5. 架构归并

- [x] ARCHITECTURE.md「报表工作台回跳」段补收编结论 + 13 目标 + 路径参数型机制 + extra_params 禁键守护。

## 6. requirement 回写

design frontmatter `requirement` 为空；工程收敛（模块 C 链接合同统一）+ 缺陷修复，非新增用户能力。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-handrolled-links-adoption `status: done` + feature 回填。
- [x] 主文档第 11 条标 ✅ done。
- [x] 解锁：fusion-batch-detail-schedule-card（第 18 条）就绪。

## 8. attention.md 候选盘点

候选 1：「viewmodel 层禁 IO/禁 core.services import 是 LIVE 架构适应度门禁（test_architecture_fitness）——新 viewmodel 动笔前先想清 IO 归路由层还是 service 层，别等门禁红了再重构」。
（仅登记，落不落由用户定。）

## 9. 遗留

- batch_detail 目标的第一个生产消费方归第 18 条（本 feature 只立合同+契约测试）。
- scheduler_workbench_link_query.py 479 行——下次进这文件的 feature 需评估拆分。
- history 行级刻意轻量 context（无 plan_resolution）——若未来历史页要展示候选方案行再升级全量身份。
