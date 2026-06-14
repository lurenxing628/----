---
doc_type: feature-acceptance
feature: 2026-06-13-fusion-dashboard-cockpit
status: accepted
summary: 首页驾驶舱四段（上下文带/hero 指令卡/6 格体检表/去盒清单）验收闭环——逐节对照 design 核对接口契约、行为决策、验收场景、术语一致性，无未处理偏差；实现期经 9 轮 Codex + 3 轮 UltraCode 对抗硬化（双引擎在最终状态一致 0 blocker）；架构 doc 已归并、roadmap 已回写（#19 done + 删按钮墙移交 #10）。
tags: [frontend, dashboard, cockpit, acceptance, module-w]
---

# fusion-dashboard-cockpit 验收报告

> 实现 + 多轮对抗硬化已闭环。本报告逐节对照 `fusion-dashboard-cockpit-design.md`（第 0/1/2/3/4 节）核对，所有 check 经真实代码 grep + 单测 + 复现验证，非凭印象。daily gate 全绿（222 serial + 1730 impact + 5 focused）。

## 1. 接口契约核对（对照 design 2.1）

| 接口 | design 约定 | 实现核实 | 结论 |
|---|---|---|---|
| `workbench_summary.hero` | 派生键 `{mode,severity,title,impact_text,evidence_text,primary_action,secondary_action}`，失败态 hero-only 合成物 | `dashboard_cockpit_hero.build_cockpit_hero` 返回 `{"hero":{...},"rest_todos":[...]}`，`_hero()` 字段齐 | ✅ |
| `workbench_summary.rest_todos` | 风险态=todo_items[1:]、失败态=全量、平静态=[] | `build_cockpit_hero` 三态切分与 design 一致；`todo_items` 原样不变→`set(todos)` 不破（test_dashboard_workbench_contract 绿） | ✅ |
| `build_dashboard_risk_cards` 扩签名 | +`latest_summary` 算 candidate、+`data_gap` 纯值，cards 禁 import core/禁扫 rows | 签名 `(*, context, pending_count, overdue_count, candidate_count, data_gap_reason, resource_load_ratio, site_gap_count)`；纯值在 `build_dashboard_workbench_summary` 先算（`_candidate_count`/`dashboard_data_gap_reason`）再传；cards 无 import core | ✅ |
| 6 格 kinds | 超期/待排/方案待确认/现场待确认/资源压力/基础数据 | 实际 kinds=overdue_batches/pending_batches/candidate_review/site_record_gap/resource_overload/data_gap（test_dashboard_six_cell_health_table_composition 锁顺序 6 格） | ✅ |
| WorkbenchLink `'batches'` | context-free `/scheduler/`，3 强制 + `_CONTEXT_FREE_TARGETS` 硬化 | TARGET_PAGE_PATHS/_TARGET_QUERY_SPECS(全 none)/TARGET_DEFAULT_LABELS/_CONTEXT_FREE_TARGETS 四处齐；TARGET 数 14（13+batches）；extra_params 注入被拒（含内部身份 4 字段） | ✅ |
| route 读 `result_status` | route 读 `workbench_history.result_status` 喂 summary（IO 在 route） | dashboard.py:379 `getattr(workbench_history,"result_status",None)`；viewmodel 不碰 ORM | ✅ |
| hero 模板渲染 action | 必须渲染 primary/secondary 的 label+url（决策 9） | dashboard.html:32-52 渲染 primary/secondary action label+url+context_summary（None 守卫） | ✅ |

接口示例（design 2.1 给的 v8 adopted 风险态）经 test_dashboard_workbench_summary_covers_required_todo_types_and_links + test_dashboard_cockpit_hero 复核：hero.mode=risk、title 原样、impact 含「N 个批次会晚于交期 · 逾期最久 {批次} 晚 {X}」、primary→/reports/overdue 带 version/plan_role/date。**无接口偏差**。

## 2. 行为与决策核对（对照 design 第 1 节 + 2.2 + 2.3 挂载点）

**关键决策逐条核实：**
- **决策 1 hero 三态独立门控**：`_failed_run_applies_to_current_view`(dashboard.py:241) 独立布尔 = `_is_adopted_role_context` + `_is_plain_plan_context` + `requested_history_error==""` + `workbench_version==最新`；**不复用** summary_matches_identity（test_dashboard_cockpit_failed_hero.py 含 executable-independence 用例验证 failed 时 is_current_executable_official_version 恒 False 仍可达）。✅
- **决策 1 归一单源**：`resolve_result_status(result_status) == "failed"`（dashboard_cockpit_hero.py:239），**非裸比较**；'fail'/大小写别名经归一仍判失败（test 覆盖）。grep 确认生产代码无裸 `=='failed'`（仅注释 + 归一后比较）。✅
- **决策 2 Path C 保留按钮墙**：`build_dashboard_quick_links` 仍在；test_manual_entry_scope/context_propagation 未动。✅
- **决策 3 recent_metrics 退役**：`_recent_schedule_metrics`/`_summary_metrics`/`_metric_number` 已从 dashboard_workbench.py 全删（grep 确认；其它模块同名 `_metric_number` 是独立命名空间无关）。✅
- **决策 5 正文唯一性**：版本仅现 `.aps-plan-capsule-version`（test_plan_context_capsule body 无第二处版本断言绿）。✅
- **决策 6 死字段**：scheduled_count 整链清除（grep 0）；overdue_count/latest_summary/latest_history/latest_history_time_display render kwarg 删；`_summary_overdue_count` 调用保留喂 count_error（无 NameError）。✅
- **决策 7 severity**：无 `.severity-unknown`/`_SEVERITY_ORDER['unknown']`（grep 0）。✅
- **决策 8 'batches' 目标**：4 处齐 + 不进 VERSION_REQUIRED/DATE_RANGE_REQUIRED。✅

**挂载点 grep + 拔除沙盘推演（design 2.3 六条，逐条「删了它 feature 是否消失」）：**
1. `templates/dashboard.html` 四段 → 删则驾驶舱消失 ✅ 存在
2. `web/routes/dashboard.py:index()` 读 result_status + 删死 kwarg → 删则 hero 失败态无源 ✅
3. `web/viewmodels/dashboard_cockpit_hero.py`（新建）→ 删则 hero 三态无装配 ✅
4. `web/viewmodels/dashboard_workbench_cards.py` 重组 6 格 ✅
5. `web/viewmodels/scheduler_workbench_link_query.py` 'batches' 目标 → 删则待排格 raise ✅
6. `web/viewmodels/page_manuals_system.py` + `static/docs/scheduler_manual.md` 首页说明改写 ✅

**明确不做反向核对（design 第 1 节末 + 第 3 节末）**：grep 全仓 — 无「工段」措辞 ✅；无 op_type_name 聚类 ✅；无 `.severity-unknown` ✅；按钮墙/顶栏/侧栏未动 ✅；body 无第二处版本 ✅；result_status 无裸比较 ✅；`build_dashboard_quick_links` 仍在 ✅；6 格恰 6 ✅。**无未处理偏差**。

## 3. 验收场景核对（对照 design 第 3 节，逐条证据）

| 场景 | 证据 | 结论 |
|---|---|---|
| 四段结构 | test_dashboard_workbench_contract（render 路由 + 扫 hero/卡/清单）；模板 26 行起 `.aps-dashboard-hero` 四段 | ✅ |
| hero 失败态（独立门控+归一） | test_dashboard_cockpit_failed_hero.py 5 场景 + executable-independence | ✅ |
| hero 失败态隐去（历史/预览/对比） | 同上（gate_false→calm/risk） | ✅ |
| hero 失败态 vs 坏版本请求 | `?version=abc/999`→requested_history_error≠""→隐失败 hero（test_scheduler_plan_identity_summary_guard 覆盖） | ✅ |
| 失败态归一（'fail' 别名/大小写） | test_failed_hero_normalizes_legacy_alias_and_case | ✅ |
| hero 风险态+精简线索+action 链接 | test_overdue_clue_complete_picks_worst_with_due_exclusive_boundary + action 路径断言 | ✅ |
| 精简线索多态降级 | 完整/缺失/裁剪/count-None/全不可解析/边界 delta==0/legacy-list/全在交期内 八态用例全绿 | ✅ |
| hero 平静态 | test_calm_hero_when_no_todos | ✅ |
| 6 格体检表（恰 6/可点跳/灰显） | test_dashboard_six_cell_health_table_composition（顺序+query 空） | ✅ |
| ③④并存 | candidate_review/data_gap 同现 6 格与 todo（契约测试覆盖） | ✅ |
| 待排格点跳不 raise | pending→/scheduler/（query 空）；'batches' 不 raise | ✅ |
| 正文唯一性 | test_plan_context_capsule body 无第二处版本 | ✅ |
| 线索日期宽松解析 | due_date='2026/06/12' 斜杠正常算出（test 覆盖）；整串匹配拒坏后缀 | ✅ |
| 'batches' context-free 拒注入 | test_context_free_targets_reject_extra_params_escape 扩 batches + 内部身份 4 字段 | ✅ |
| 迁移测试（overdue 锚/plan_identity 4 函数/time_display/手册/observability） | 全绿（daily gate impact set 含） | ✅ |
| 词表单源（模板不内联中文） | test_label_single_source_contract 绿 | ✅ |
| 既有锚点不破（三锚+realtime_note+备份四态） | EXPECTED_PAGE_SIGNALS/first_round 绿 | ✅ |
| 零写入 | viewmodel 纯只读、无排产数据写入、无新增首屏计划行扫描 | ✅ |

**前端浏览器视觉验证说明（诚实标注）**：四段结构 / hero 三态 / 6 格 / 去盒清单 / 正文唯一性均经 **HTML 契约测试**（实跑路由 + 解析渲染 HTML 断言可见文本与结构）覆盖；`.aps-dashboard-hero` 四档 severity 的**像素级视觉呈现**（CSS 外观）本会话 CLI 环境无法浏览器实测，列入第 9 节遗留由人工补一次目检。

## 4. 术语一致性（对照 design 第 0 节）

新写符号去第 0 节对照：`build_cockpit_hero`/`_failed_run_applies_to_current_view`/`_overdue_hero_impact`/`candidate_review`/`data_gap`/`_valid_date_arg`/`_has_parseable_range`/`scheduler_workbench_link_specs` 均为 design 既定概念或其自然实现细节，无 doc 外新概念。「精简主导线索」「驾驶舱四段」「context-free 'batches'」措辞与 design 一致。**未引入「工段」**（design 0 节警示的伪概念）。术语一致，无遗漏。

## 5. 架构归并（对照 design 第 4 节，已实际写入）

- **新增模块**：`web/viewmodels/dashboard_cockpit_hero.py`（hero 三态 + 精简线索 + result_status 归一消费）+ 拆分产物 `web/viewmodels/scheduler_workbench_link_specs.py`（WorkbenchLink 目标 query 规格 + 禁注入键表，从 link_query 只搬不改外移）→ **已写入 ARCHITECTURE.md 第 3 节**（首页值班台条目改写为驾驶舱四段 + 新模块；link_query 条目补 specs 拆分 + 'batches' 第 14 目标）。
- **契约遵守**：4.2（正文唯一性阶段二）/4.4（栅格认知）/4.6（severity 不引入 unknown）/4.7（adopted 聚合护栏 + 失败 hero 独立门控）/4.9（删 stat-grid 前迁正则锚 + 三锚不破）逐条核实满足。
- **契约扩展**：WorkbenchLink 'batches'→'/scheduler/' 受控新增（第 11 条合同一处），test_scheduler_workbench_links_contract `set(TARGET_PAGE_PATHS)` 已加 'batches'。

## 6. requirement 回写

design frontmatter `requirement:` 为空——本 feature 是 roadmap 驱动的前端构图重排，无独立愿景能力 req（属界面信息架构调整，非新业务能力）。**结论：跳过**（纯 UI 重排/技术债性质，无 req 可升级或 backfill）。

## 7. roadmap 回写（frontmatter 有 roadmap/roadmap_item，必须回写）

- **items.yaml**：`fusion-dashboard-cockpit` `status: in-progress → done`（feature 字段已填 `2026-06-13-fusion-dashboard-cockpit`）。**已写入**，validate-yaml 校验通过。
- **删按钮墙移交 #10**：design Path C 裁决「删常用工作区按钮墙 + 首页带上下文跳转承接」移交 `fusion-nav-specs-unify`（#10，侧栏做事路线就位再删）。**已在 items.yaml #10 notes 与 roadmap 主文档 #19/#10 条目标注移交**，避免 #10 以「按钮墙已删」错误前提推进。
- 6 格为 item#30 预留挂点，本 feature 未预占（design 已述）。

## 8. attention.md 候选盘点

实现期发现的、对下个 feature 的 AI 有复用价值的硬约束/陷阱候选：
1. **「禁外显内部身份」= 禁渲染可见文本，非禁 URL query**：version/plan_role/scenario_id 是 WorkbenchLink 计划身份 query 三元组（`_append_plan_query`）by-design 入 query；校验工具只扫可见文本忽略 href。（已写入 auto-memory `forbidden-internal-identity-means-visible-text`，是否也加 attention.md 待用户定）
2. **失败 hero 门控不可复用 summary_matches_identity**：result_status=failed→is_current_executable_official_version 恒 False→若复用则 hero 永不可达（design 决策 1 已详载，可不重复入 attention）。
3. **Codex codex-rescue 子代理派发后偶发 mid-flight 死**：改主线程单进程可突破（本次 round-7/8/9 实证）。

（具体是否入 attention.md 由退出后逐条问用户，走 cs-note，不在此手写。）

## 9. 遗留

1. **前端像素级视觉**：`.aps-dashboard-hero` 四档 severity 的浏览器外观本会话未实测（CLI 无浏览器），HTML 结构/文本已契约覆盖——建议人工补一次亮/暗双主题目检（首页三态：失败/风险/平静）。
2. **按钮墙删除**：Path C 保留，移交 #10。
3. **`scheduler_workbench_link_query.py` 已拆至 367 行**（余量充足）；其内 R54「逐键四态拦放 parity oracle」相关测试 `test_scheduler_workbench_links_contract.py` 仍 1016 行（pre-existing、非门禁强制于测试、R54 钉死禁拆）——非本 feature 引入，不处理。
4. 6 格临期第 7 格留给 item#30，本 feature 不预占。

---

**实现期对抗硬化记录**（供后人追溯）：9 轮 Codex（codex-rescue，每轮 --fresh 自包含）+ 3 轮 UltraCode（Workflow 多维 find→双 skeptic 默认反驳验证→合成）。逐条对真实代码核实（驳回过整簇「禁外显」误读假阳），按类彻底收口反射回显 / 坏数据伪装正常 / bool·NaN·unicode 数字·截断 类型混入三大类隐患。双引擎在最终 shipped 状态一致确认 **0 blocker**（Codex round-9「No blocker. Feature is clear for merge.」/ UltraCode 最终轮 confirmed=0 blocker=0）。
