# fusion-plan-context-capsule 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-plan-context-capsule-design.md（approved，Codex 设计三轮 BLOCK→BLOCK→PASS——含 6 发布点/单点化两阶段/sentinel 三次拍板 + 实现两轮 PASS-WITH-SUGGESTIONS→PASS，建议全采纳并逐轮收回确认）

## 1. 接口契约核对

- [x] 与 design 2.1 一致：`build_workbench_plan_context` 新增 `generated_at=_UNSET, strategy=_UNSET`（模块级私有 sentinel）+ `generated_at_label/strategy_label` 两公开输出；label 转换只在合同内一处。
- [x] `plan_context_capsule.py` 新文件：`build_plan_context_capsule(context)`（无 version None）+ `history_row_capsule_fields(rows, version)`（查不到空 dict）。
- [x] 模板全局 `workbench_plan_capsule` 经 navigation_context → template_globals 注入（第 9 个全局，注释同步）。
- [x] 实现期零偏差（设计三轮已把 sentinel 两态/6 发布点/取数来源提前钉死）。

## 2. 行为与决策核对

- [x] 决策 1 sentinel 四类边界：_UNSET→「-」；喂 None/空串→时间「-」/策略「旧历史未记录」（词表缺失态，与未喂参刻意区分）；正常值/坏值走 format_public_datetime 与 strategy_display_label 单源（未知「历史记录异常」，不造第三套文案——roadmap 4.2 已设计期修订）。
- [x] 决策 2 import 方向无环（history_summary 不反向依赖 links）；links 文件 461/500。
- [x] 决策 3 builder 落新文件（不往 449 行 links 加码——实际只加合同 12 行）。
- [x] 决策 4 挂载 base.html h2 与 workbench nav 之间；CSS 纯 token 零新 hex（冻结守卫绿）。
- [x] 决策 5 六发布点喂参：dashboard 落第二次发布的 latest_plan_context 构造处（后写覆盖坑避开）；gantt 改 `_selected_version_summary_context` 单查询两用（不退化 limit-30 列表）；analysis/week_plan 用现成 selected 行；reports 公共 `_publish_report_context` 加 capsule_rows（5 入口传 versions）；resource_dispatch `_workbench_context` 加 capsule_rows。`_capsule_kwargs` 钉死「空 dict 不传→_UNSET」与「查到缺失值传 None→词表缺失态」链路一致。
- [x] 决策 6 单点化阶段一：dashboard.html muted 行去重（保留「今日待处理生成时间」+语义注释）；analysis 概览卡/体检表零 diff（阶段二 #28/#19）。
- [x] 挂载点 grep 反向核对：aps-plan-capsule 全仓仅宏/CSS/测试三处；workbench_plan_capsule 仅 navigation_context/template_globals/base.html；拔除沙盘：删 2 新文件+回退 12 文件改动即完全退出。

## 3. 验收场景核对

- [x] S1 合同四类边界单测 3 条全绿（含词表单源未知态直锁）。
- [x] S2 带版本页胶囊渲染（gantt?version=7 → v7·正式采用方案·生成时间·策略·日期范围）——页面断言+浏览器截图（亮/暗）。
- [x] S3 基础数据页（/material/materials）胶囊零渲染——断言+截图核过。
- [x] S4 首页胶囊字段非「-」（第二次发布喂参落点实证）+ muted 行去重断言。
- [x] S5 六发布点各 1 条页面断言（断在「2026年6月1日 08:00」喂参才有的值上）；reports 抽超期页+公共取数单测覆盖。
- [x] S7 history_row_capsule_fields 查不到→空 dict→「-」诚实降级单测钉死（防误修成查库）。
- [x] S8 URL fallback（/system/history?version=7 无发布点页）：胶囊渲染 v7 基础字段、生成时间不出现（不查库补）。
- [x] S9 CSS 零新 hex（test_css_token_source_contract 绿）。
- [x] 回归：web_pages+schedule 928 passed、app_runtime 162 passed、daily gate passed（并行 WIP stash 隔离）。

## 4. 术语一致性

- 「胶囊/生成时间（排产 schedule_time ≠ 今日待处理实时戳）/单点化两阶段/_UNSET 未喂参」design、合同注释、宏注释、测试 docstring 同口径；roadmap 4.2 修订后契约与实现零打架（Codex 逐轮收回确认）。

## 5. 架构归并

- [x] ARCHITECTURE.md「APS 工作台上下文链接合同」段补胶囊条目（sentinel/6 发布点/零渲染/URL 直入不查库）。

## 6. requirement 回写

design frontmatter `requirement` 为空；上下文常驻属工程收敛（模块 C），非新增用户能力。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-plan-context-capsule `status: done` + feature 回填。
- [x] 主文档第 9 条标 ✅ done；4.2 三处修订已于设计期落账（变更日志 2026-06-12 条目）。
- [x] 解锁：fusion-nav-specs-unify（#10）、fusion-quick-locate（#22）、fusion-analysis-action-refresh（#28）就绪。

## 8. attention.md 候选盘点

候选 1：「合同 kwargs 需要区分『调用方没传』与『传了空值』时，None 不能身兼两态——历史数据字段本身可能是 None/空串，用模块级私有 sentinel（_UNSET = object()）；透传层用 'key' in fields 判断而非 truthiness」。
（仅登记，落不落由用户定。）

## 9. 遗留

- reports_page_support.py 498/500 余量极窄——下次进此文件先拆（design 2.5 已落账）。
- 版本号单点化阶段二（analysis 概览卡接胶囊/dashboard 体检表）归 #28/#19，两条验收时执行正文唯一性断言。
- 胶囊无跳转动作（纯展示）；若未来要点击回到来源页，归 #10 导航 specs 统一。
