---
doc_type: roadmap
slug: aps-frontend-fusion
status: active
created: 2026-06-11
last_reviewed: 2026-06-11
tags: [aps, frontend, fusion, design-system, v2-shell, workbench, win7]
related_requirements:
  - scheduler-daily-workbench
  - gantt-readonly-result-view
  - shop-floor-execution-feedback
  - resource-dispatch-calendar-readable-output
related_architecture: [ARCHITECTURE, ui-gantt]
related_roadmaps: [aps-frontend-workbench, gantt-result-view-and-manual-adjustment, networkx-scheduler-graph-introduction]
---

# APS 前端设计收口与已有能力融合路线图

## 1. 背景

2026-06-10 的全面前端设计评审（23 agent 编排 + 3 评委对抗 + 8 域能力挖掘 130 条核证）得出三个结构性结论：

1. **双轨 UI 半截迁移**：`DEFAULT_UI_MODE="v2"`，用户日常看到的是 `web_new_test/` 的 V2 侧栏壳（仅 7 个模板），其余 ~60 页是 V1 页面体塞 V2 壳；6 个镜像模板靠人肉双写、守卫测试已被 DROP；旗舰的「计划工作台」入口只挂在 V1 壳（`templates/base.html:56`），默认界面看不见。
2. **设计地基三代叠层**：token 三层链、语义色三个真值（success `#16a34a`/`#10b981`/`#0f9d58`）、383 处硬编码 hex、`ui_contract.css` 6277 行单文件、183 条暗色手工覆盖。
3. **大量后端能力已建好但前端没接**：甘特条 progress 硬编码 0（完工事实就在同函数里）、Excel 导入两段式 preview/confirm 端点零前端消费、报表中心入口卡是死文案而 KPI 聚合函数现成、批次详情页零排程字段而按批查询 API 现成。

本 roadmap 解决两件事：**把双轨与设计地基收口成一套**（评委一致裁定的「方向 B 设计系统中改」，承载壳为已转正 4.5 个月的 V2 侧栏），以及**把已有后端能力接到前端**（全部接线点经对抗核证、有 file:line 背书）。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- V2 壳转正为唯一壳，删双轨渲染机器与镜像树。
- 设计令牌单源化、hex 机械迁移、CSS 分层拆库、前端门禁三件套。
- 全局计划上下文胶囊、导航 specs 数据驱动化、词表单一字源。
- 已有能力融合接线：甘特现场事实可视化、沿链巡检、负荷条带、报表 KPI 答案卡、批次详情排程去向、周计划增强、Excel 两段式导入、首页失败 hero 卡与驾驶舱减法、派工拆页、长尾页收敛。
- 守卫与基线：镜像守卫、锚点爆点清单、亮/暗/打印基线、500 行门禁扩面、性能预算。

### 明确不做

- 不重复立项老 roadmap `aps-frontend-workbench` 的 9/10/12/13 项（用户指南、延期接现场事实、停机任务级明细、批次牵连影响面）——它们留在老 roadmap 推进，本文观察项给出按本次挖掘结论的修订建议。
- 不引入外部框架/CDN/外链字体/构建工具；不做 SPA；保持 Flask+Jinja2 服务端渲染。
- 不开放甘特拖拽写库；现场记录只写正式采用方案；不重写排程算法。
- 不做移动端、大屏看板、多人账号权限；不做机器级日历容量细分（无数据来源，属新数据链路需求，见观察项）。
- 不放宽「候选/模拟方案无现场事实」的 DB 级 CHECK 口径（这是契约不是缺陷）。
- 不升级破坏 Python 3.8 / Win7 x64 / Chrome 109 的语法或依赖；CSS 禁用 color-mix/oklch/原生嵌套/subgrid/popover。

## 3. 模块拆分（概设）

```text
aps-frontend-fusion
├── 模块 S · 壳层收口：V2 侧栏转正为唯一壳，删双轨机器与镜像树，旗舰入口归位
├── 模块 T · 令牌与样式工程：token 单源、hex 迁移、CSS 分层拆库
├── 模块 C · 上下文与导航：计划上下文胶囊、导航 specs 化、词表与链接收编
├── 模块 W · 能力融合接线：把已建好的后端能力接到页面（甘特/报表/批次/周计划/派工/首页）
├── 模块 N · 闭环补全：用户拍板的小型新功能（临期预警/派工单打印/备份提示/版本差异）
└── 模块 G · 守卫与门禁：锚点基线、前端门禁扩面、性能预算
```

### 模块 S · 壳层收口
- **职责**：让全站只有一棵模板树、一个壳。先急救默认界面的存量缺陷（入口不可见、孤儿 CSS 裸奔），再裁决并删除双轨机器。
- **承载的子 feature**：fusion-v2-quickwin-pack、fusion-mirror-sync-guard、fusion-dual-track-retirement
- **触碰的现有代码**：web/render_bridge.py、web/ui_mode*.py、web_new_test/、templates/base.html、34 个路由的 import、build_win7_onedir.bat、tools 门禁源。

### 模块 T · 令牌与样式工程
- **职责**：建立 token 唯一真相源并把全仓样式迁移上去；拆掉 6277 行单文件；暗色退化为纯 token 换肤。不动页面信息架构。
- **承载的子 feature**：fusion-tokens-single-source、fusion-hex-migration、fusion-css-layer-split、fusion-debox-table-wave
- **触碰的现有代码**：static/css/*（拆分重组）、static/js/gantt_color.js 等 JS 色源。

### 模块 C · 上下文与导航
- **职责**：版本/方案/时间上下文全站常驻且只出现一处；导航全部由 Python specs 数据驱动；中文词表单一字源；手拼链接收编进 WorkbenchLink 合同。
- **承载的子 feature**：fusion-label-single-source、fusion-plan-context-capsule、fusion-nav-specs-unify、fusion-handrolled-links-adoption
- **触碰的现有代码**：web/viewmodels/scheduler_workbench_links.py（扩合同）、scheduler_navigation_links.py、templates/components/、base.html。

### 模块 W · 能力融合接线
- **职责**：每条接线只消费已存在的服务/字段，不新增算法。凡涉及计划身份的展示一律走既有 *_label 公开字段。
- **承载的子 feature**：fusion-gantt-execution-visuals、fusion-chain-walk-navigation、fusion-gantt-fix-pack、fusion-gantt-controls-rework、fusion-gantt-load-strip、fusion-week-plan-enrich、fusion-reports-index-kpi、fusion-batch-detail-schedule-card、fusion-dashboard-cockpit、fusion-dispatch-import-two-phase（已 dropped）、fusion-dispatch-split-pages、fusion-longtail-unify、fusion-todo-ack-state、fusion-quick-locate、fusion-analysis-action-refresh
- **触碰的现有代码**：core/services/scheduler/gantt_tasks.py、gantt_week_plan.py、web/viewmodels/dashboard_workbench*.py、scheduler_reports_workbench.py、static/js/gantt_*.js、resource_execution_import.js 等。

### 模块 N · 闭环补全（小型新功能）
- **职责**：补日常闭环的"最后一米"缺口——只做用户拍板的小件（2026-06-11 拍板四件）；允许新增只读查询/纯函数算法，**禁止写排产数据**；每条必须有诚实空态与失败态。与模块 W 的分界：W 只消费已存在的服务/字段，N 允许新增只读算法。
- **承载的子 feature**：fusion-due-soon-alert、fusion-dispatch-print-sheet、fusion-backup-health-hint、fusion-plan-version-diff、fusion-runtime-log-viewer
- **触碰的现有代码**：web/viewmodels/dashboard_workbench*.py（临期待办类别）、web/routes/system_backup.py 读侧、资源排班页模板与 static/css/print.css、core/services/scheduler/ 新增 plan_version_diff.py（新文件，不碰 495/500 行的 gantt_service.py）、web/error_handlers.py 与 web/error_boundary.py 的文案出口、core/infrastructure/logging.py 只读消费。

### 模块 G · 守卫与门禁
- **职责**：改版不打无准备之仗——先有爆点清单和截图基线，后动手；门禁守住不回潮；改完守住不变慢。
- **承载的子 feature**：fusion-anchor-baseline-prep、fusion-frontend-gates、fusion-performance-budget
- **触碰的现有代码**：tools/quality_gate_shared.py、tests/app_runtime/ui_geometry_contract_data.py、新增 tools/check_css_compat.py。

## 4. 模块间接口契约 / 共享协议（架构层详设）

### 4.1 模板全局注入接口（S → 全部模块）

**方向**：S 模块产出，所有后续模板类 feature 依赖。
**形式**：函数调用（应用启动期）。

```
# 新建 web/bootstrap/template_globals.py
def install_template_globals(app) -> None
# 函数体迁自 render_bridge.py:68-80 的 jinja_env.globals 注入
# （safe_url_for/get_help_card/get_manual_url/get_full_manual_section_url/
#   build_workbench_navigation_links/build_report_navigation_links/
#   build_scheduler_navigation_links/preserved_report_context_fields）
```

**约束**：双轨删除后 `from web.ui_mode import render_ui_template as render_template` 的 34 处 import 统一切回 `from flask import render_template`，一次性切换不留兼容垫片；`web/bootstrap/static_versioning.py:22` 的 endpoints 集合删除 `ui_v2_static.static`。

### 4.2 计划上下文胶囊数据契约（C → 全站模板）

**方向**：viewmodel → base.html 壳层宏。
**形式**：扩展既有合同 + Jinja 宏。

```
# 扩展 web/viewmodels/scheduler_workbench_links.py
def build_workbench_plan_context(*, version=None, ..., back_to=None,
                                 generated_at=_UNSET, strategy=_UNSET) -> Dict[str, Any]
# _UNSET 是模块级私有 sentinel（2026-06-12 修订）：None 不能身兼「未喂参」「喂了空值」两态——
# 未喂参（URL fallback 路径）显示"-"；喂了 None/空串的旧历史行走词表缺失态"旧历史未记录"
# 输出新增字段：generated_at_label: str（走 format_public_datetime，坏值显示"时间记录异常"）
#               strategy_label: str（走 #8 词表单源 strategy_display_label——未知值"历史记录异常"、
#               缺失"旧历史未记录"；2026-06-12 修订：原文"未识别的策略"先于 #8 完成而写，不另造第三套文案）
# 发布点同步喂参共 6 处（注意 dashboard 有两次发布、后写覆盖前写）：
#   web/routes/dashboard.py 双发布——第二次的 latest_plan 产自 dashboard_workbench_context.py，
#     喂参点必须落在其 build_workbench_plan_context 调用处，否则首页胶囊被二次发布覆盖成 "-"
#   web/routes/domains/scheduler/scheduler_navigation_publish.py 的 publish_gantt/publish_analysis/publish_week_plan
#   web/routes/reports_page_support.py:91 _publish_report_context
#   web/routes/domains/scheduler/scheduler_resource_dispatch.py _workbench_context（2026-06-12 修订补列，原文漏）

# 新建 templates/components/_plan_context_capsule.html
{% macro plan_context_capsule(context) %}
# 渲染：版本 · 方案身份 · 生成时间 · 策略 · 数据范围；无上下文页面渲染空串
```

**约束**：版本号单点化分两阶段（2026-06-12 修订）——阶段一（第 9 条）：胶囊上线 + 壳层 chrome 单点（dashboard muted 行去重）；阶段二（第 28 条 analysis 概览卡接胶囊 / 第 19 条 dashboard 体检表）：页面正文版本号清理至胶囊一处，两条验收时执行正文唯一性断言；数据行（历史表每行 vN）与版本选择器选项永久豁免（数据不是 chrome）。胶囊只消费 `*_label` 公开字段；缺字段显示"-"，不显示 raw 值；不显示 plan_role/scenario_id 原值；scheduler_workbench_links.py 已 449/500 行，胶囊 builder 落新文件，禁止顺手加码。

### 4.3 导航 specs 契约（C → 壳层与各域子导航）

**形式**：Python 数据结构 → 统一渲染宏。

```
NavItemSpec（dict）: { key: str, label: str, url: str, active: bool,
  disabled: bool, disabled_reason: str, icon_id: Optional[str] }
NavGroupSpec（dict）: { key: str, label: str, items: List[NavItemSpec] }

def build_sidebar_nav_groups(...) -> List[NavGroupSpec]   # 五段做事路线 + 基础数据 + 系统
{% macro module_subnav(specs) %}                          # 替换 material/process/personnel/equipment/system 五个手写宏
```

**约束**：active 按 request.endpoint 前缀判定并输出 `aria-current="page"`；disabled 必带中文原因；与既有 `build_scheduler_navigation_links`（web/viewmodels/scheduler_navigation_links.py:123-151）同构扩展，不另起平行体系。侧栏视觉 2026-06-11 定版**浅色**：#f8fafc 底 + 1px 右描边，active 项 = primary-soft 底 + 左 3px 主色条 + 主色深字，图标 16px/2px 描边线性风格——理由是把全页最强对比度让位给内容区的风险信息，常驻菜单不抢注意力。

### 4.4 设计令牌契约（T → 全部样式）

**形式**：CSS 文件 + 门禁脚本。

```
# 新建 static/css/00-tokens.css —— 全仓唯一允许出现裸 hex 的文件
命名空间：--ui-*（语义层唯一真相源）；--aps-*/--primary-color 降为别名块（迁移期保留，期满删除）
语义色定版（三套分叉值合一，沿用 slate 族内推导）：
  success #16a34a / danger #dc2626 / warning #d97706 / primary #2563eb（沿用）
字号阶：12/13/14/17/22px 五级 + KPI 28px；间距阶 --space-1..7 = 4/8/12/16/24/32/40px
圆角：4/6/8px 三档；阴影两档低透明多层叠；焦点环 --ui-focus-ring 全局 :focus-visible 上岗
阈值常量唯一真相源：负荷 warning>=0.75 / danger>=0.90
  （收编 dashboard_workbench.py:14-15 与 dashboard_workbench_cards.py:7-8 的双份定义，Python 侧单点定义、CSS 侧仅消费类名）
版面栅格（2026-06-11 定版，全站构图契约）：内容区 12 列栅格、列槽 24px、内容上限宽约 1128px；
  页面上任何卡片/分栏的竖边必须落在栅格线上，禁止元素私有宽度（320px 固定侧卡之类一律改列跨度）
认知五原则（全站构图契约）：①对比度最强处 = 信息最重处（风险横幅 > 正文 > 导航）；
  ②一屏只许一个主按钮（填充蓝），其余降为描边/文字按钮；③同一语义全站只有一种长相
  （底色+徽标+圆点三通道一致，色盲可辨）；④同类信息固定位置，养成位置记忆；
  ⑤数字一律 tabular-nums 等宽对齐
```

**约束**：00-tokens.css 之外新增裸 hex 由门禁拒绝（白名单机制）；暗色 `html[data-theme=dark]` 只允许 token 重赋值 + ≤10 条特例。

### 4.5 CSS 分层契约（T → 全部页面）

```
@layer reset, tokens, base, components, patterns, pages;   # Chrome 99+，109 可用
文件：00-tokens / 05-reset / 10-base / 20-components-*(btn/form/table/badge/nav/card)
     / 30-patterns-*(hero/summary/notice/empty/import) / 40-page-*
每文件 < 500 行；页面私有样式（#batchOpsTable 等）迁入 40-page-* 经 extra_head 挂载
```

**约束**：拆分批次执行，每批用截图 A/B + computed-style diff 验证零视觉回归（"只搬不改"对页面私有规则不成立——级联顺序会变，必须 diff 验证）。

### 4.6 容量与负荷口径共享协议（W：第 15/16/17 条及后续一切容量类展示共同遵守）

```
容量分母公式单源：CalendarEngine 的 shift_hours × efficiency 同一公式；
  采样时刻统一取正午定口径并加测试钉死；
  禁止直接调用 calculations.capacity_hours——其 midnight 采样（calculations.py:56-67 硬编码、无采样时刻参数）
  在跨午夜班次会把当日容量归属前一日窗口
阈值唯一真相源：负荷 warning>=0.75 / danger>=0.90（收编 dashboard_workbench.py:14-15 与
  dashboard_workbench_cards.py:7-8 的双份定义，Python 侧单点定义）
severity 枚举：负荷类新增 'unknown' 档与首页既有 'notice' 档并存，feature-design 必须显式裁决映射，不得同义混用
```

**约束**：容量来源必须明示"按全局工作日历估算，未按单台设备/单人细分"；算不出显示"利用率暂时算不了"；输出行可含点击联动所需的 resource_id（machine_id/operator_id），此外禁含内部字段；负荷条带的函数签名、输出 schema、像素对齐实现与降级止损线属第 15 条 feature-design 范畴（gantt_service.py 已 495/500 行，新逻辑必须落新文件），证据与建议实现见 drafts/capability-mining.md 的 utilization-capacity 域。

### 4.7 adopted 聚合注入非身份页面的共享护栏（W：第 17 条报表答案卡、第 19 条首页线索摘要等共同遵守）

```
凡把 adopted-only 聚合（如 execution_review，execution_review.py:207-208 钉死口径）
  注入报表中心 / 首页这类会随 request 身份切换的页面：
  request 身份非 adopted 时该 KPI 必须按既有 plan_identity_error 口径隐去，
  不得拿 adopted 数字冒充当前查看方案
聚合报错走 _checked_report_value 既有模式（reports_page_support.py:131-135）明示，不静默吞
首屏聚合次数增加（如报表 index 1→4 次计划行扫描）必须 Win7 实测，并预置门槛/懒加载降级预案
```

**约束**："偏差 Top"无数值聚合（仅 *_deviation_label 字符串），第一版用可复盘记录数顶替并在文案明示；KPI 取数表达式与 build_reports_index_workbench 形参扩展属第 17 条 feature-design 范畴，接线证据见 drafts/capability-mining.md 的 page-fusion 域。

### 4.8 词表唯一字源契约（C → 全部模板/JS）

```
strategy/status 中文标签：唯一字源定为 web/viewmodels/ 层标签函数
 （候选三套：build_analysis_labels、scheduler_history_summary 的 _VERSION_OPTION_STATUS_LABELS、
   scheduler_summary_display.py:395 的 build_summary_display_state——后者是 display_label 真源；
   归并到哪一套属 cs-decide 级拍板，先于本模块各 feature 落地）
全量收编点：11 处模板内联字典（dashboard.html:126-135、scheduler/gantt.html:11-19、
 scheduler/resource_dispatch.html:11-19 及 web_new_test 镜像、_version_picker 等）
JS 侧不维护平行词表；甘特 execution-<status> 类名只用公开语义词（processing/paused/completed/exception）
```

**约束**：status 现存三套口径（含 'ok2' 遗留键），收编时逐键对账并删除死键；未知值统一"未识别的××"，不透传英文枚举。

### 4.9 守卫契约（G → 全部改版 feature）

```
镜像守卫（双轨删除前的临时保险）：逐字节断言 6 个镜像模板与 V1 相同，挂 LIVE 门禁
锚点单一真相源：页面标题/栏目文案变更只改 tests/app_runtime/ui_geometry_contract_data.py
 的 EXPECTED_PAGE_SIGNALS（20 条 URL，HTML 档与浏览器档共享）
500 行门禁扩面：不动 CORE_DIRS（collect_py_files 只收 .py 且同清单喂 radon，.html 会爆）；
 在 tools/quality_gate_shared.py 新增 FRONTEND_SIZE_DIRS 常量接 architecture_oversize_scan_map
Chrome109 黑名单：新建 tools/check_css_compat.py，正则拒绝
 color-mix(|oklch(|lab(|lch(|&（原生嵌套）|subgrid|popover=|text-wrap:balance|toSorted|toSpliced
 （正则需上下文限定并支持白名单豁免——& 会命中 CSS url() 查询串与 HTML 实体、popover= 会命中普通文本，
  豁免机制款式同 4.4 的 hex 白名单）
```

**约束**：每个动模板的 feature 开工前先跑锚点测试集圈爆点；动 dashboard 删 stat-grid 前必须先迁移 tests/web_pages/test_dashboard_overdue_count_tolerance.py:15 的正则锚（LIVE required）。

### 4.10 现场事实展示契约（W：所有接事实的 feature 共同遵守）

```
读取唯一入口：ExecutionFactProvider.facts_by_op_id_for_plan_rows(rows, plan_fields, *, include_op_ids=())
 （op_id-only 入口被故意毒化会 raise——这是契约；必须带完整计划身份）
展示只消费公开标签：actual_summary_label / actual_start_time_label / actual_end_time_label /
 execution_status_label（gantt_tasks.py _execution_detail_meta:152-177 的抽取模式）
禁止把 ExecutionFact 整体透传给模板/JS（含 schedule_id/source_table/effective_plan_role/scenario_id）
非 adopted 身份永远无事实（schema CHECK 钉死）：候选/模拟下诚实显示"暂未记录现场实际"，禁止放宽
甘特 progress 只允许 completed→100，禁止用 quantity_done 估算部分进度伪装精度
```

### 4.11 闭环补全类新功能共享约束（N → 第 30-33 条共同遵守）

```
只读不写：N 模块一切功能只读排产/备份数据，禁止写入或修改排产结果
常量单点：时间窗/阈值（临期窗口默认 3 天、备份提醒阈值 7 天）Python 侧单点定义，模板只消费结论
身份口径：涉计划身份的展示遵 4.7（adopted 聚合护栏）与 4.10（现场事实展示契约）
诚实态：备份状态读取失败明示"备份状态读取失败"；版本 diff 算不出明示"无法对比"并给原因；
  空态给下一步指引（空班次/无差异/无临期都要有一句话），禁止静默隐藏
```

**约束**：派工单第一版只含计划任务、不含现场事实（要含必须走 4.10 唯一入口，不另开旁路）；临期判定与超期判定共用同一交期字段、同一方案身份与同一比较口径，禁止两套算法各算各的。

## 5. 子 feature 清单

> 状态均 planned、feature 均未启动，仅列依赖与一句话落点（详细接线证据见 drafts/capability-mining.md）。

**模块 S**
1. **fusion-v2-quickwin-pack** ✅ done（2026-06-11，feature 2026-06-11-fusion-v2-quickwin-pack，提交 cd0c2c3e）— 默认界面急救包：V2 壳挂 workbench_nav_menu + 门禁断言扩 V2；base.css 孤儿 CSS 11 类并入 style.css（flash-warning 等 19 模板今天裸奔）；dashboard.html:137 raw 时间改 format_public_datetime（双树）。依赖：无。**最小闭环**。（镜像守卫已按拍板单拎为第 26 条。）
2. **fusion-dual-track-retirement** ✅ done（2026-06-11，feature 2026-06-11-fusion-dual-track-retirement，提交 dab79ed2..91eb10cc 共 10 个）— 双轨裁决 ADR（cs-decide，2026-06-11 用户已拍板留侧栏壳）+ 六工作包落地：删 render_bridge 等 5 文件、35 路由 import 切回 flask、V2 base 转正搬家（顺手修 title 常量化缺陷）、system_ui_mode 下线、打包 bat 与 tools 门禁源同步、测试面整删 2 文件改 16 文件、quality_gate_ledger 台账同步。依赖：26（镜像守卫是双轨拆除的真前置）；建议排在 1 之后执行（挂载即被转正继承）。

**模块 G**
3. **fusion-anchor-baseline-prep** ✅ done（2026-06-12，feature 2026-06-12-fusion-anchor-baseline-prep，Codex 设计两轮+实现两轮审核零阻塞收口）— 改版基线三件套：LIVE 文案/结构锚点爆点清单落档；亮/暗双主题截图基线（复用既有截图管线）；打印介质回归清单。依赖：无。
4. **fusion-frontend-gates** — 前端门禁三件套：500 行扩面（FRONTEND_SIZE_DIRS 接 architecture_oversize_scan_map）、check_css_compat.py 黑名单、token 漂移守卫（00-tokens.css 外禁裸 hex）。依赖：5（token 文件先存在才有守卫对象）。

**模块 T**
5. **fusion-tokens-single-source** ✅ done（2026-06-12，feature 2026-06-12-fusion-tokens-single-source，Codex 设计两轮+实现两轮审核收口；语义色三值合一为有意视觉变化已 A/B 留痕）— 00-tokens.css 唯一真相源 + 语义色三值合一定版 + 旧名降别名 + 负荷阈值常量收编单点。依赖：2（单壳单 CSS 链）、3（基线先行）。
6. **fusion-hex-migration** — 383 处裸 hex 机械替换（映射表逐处人工标注后进脚本，分批 + 逐批截图 A/B）+ 暗色 183 条覆盖收敛为 token 换肤 + JS 色源（gantt_color/gantt_legend）改 getComputedStyle 读 token。依赖：5。
7. **fusion-css-layer-split** — @layer 分层拆库六层多文件各<500 行 + 页面私有样式迁 40-page-* + computed-style diff 验证。依赖：6（先收口 hex 再拆层，避免拆层引起的级联变化污染 383 处替换的 A/B 截图基线）。

**模块 C**
8. **fusion-label-single-source** ✅ done（2026-06-12，feature 2026-06-12-fusion-label-single-source，Codex 设计两轮+实现一轮审核收口；ok2 死键全删走 unknown 诚实降级）— 词表收编：11 处内联 strategy/status 字典收编唯一字源 + 三套 status 口径拍板 + 'ok2' 死键清理 + cs-semantic-radar 概念身份证。依赖：2（删镜像后只剩单树，工作量减半）。
9. **fusion-plan-context-capsule** ✅ done（2026-06-12，feature 2026-06-12-fusion-plan-context-capsule，Codex 设计三轮+实现两轮审核零阻塞收口；4.2 契约三处修订于设计期落账）— 计划上下文胶囊：扩 build_workbench_plan_context 合同（_UNSET sentinel 区分未喂参/喂了缺失值）+ 6 发布点喂参（含 resource_dispatch）+ 胶囊宏挂壳层 top-header（无 version 零渲染，URL 直入「-」不查库补）+ 版本号单点化阶段一（dashboard muted 行去重；正文清理归 #28/#19 阶段二）。依赖：8（词表先单源）。→ 解锁第 10/22/28 条。
10. **fusion-nav-specs-unify** — 导航 specs 化：侧栏五段「做事路线」分组 + module_subnav 统一五个手写宏 + aria-current 全站 + 焦点环上岗。依赖：2、9（胶囊与侧栏同壳层，先胶囊后重排）。
11. **fusion-handrolled-links-adoption** ✅ done（2026-06-12，feature 2026-06-12-fusion-handrolled-links-adoption，Codex 设计两轮+实现三轮审核零阻塞收口）— 手拼链接收编：history.html 5 链接、analysis _version_picker 2 链接入 WorkbenchLink（修「模拟预览点过去掉回正式视角」缺陷——选择器链带全量身份保留 scenario_id）；TARGET_PAGE_PATHS 扩 history/batch_detail 13 目标（batch_detail 是首个路径参数型目标：{batch_id} 占位 quote 替换、缺参 fail-loud 不随 disabled 摇摆；两新目标 query 合同由 extra_params 禁键集守护）。history 行级 span 先分页后装配、单行坏历史禁用明示。依赖：无。→ 解锁第 18 条。

**模块 W**
12. **fusion-gantt-execution-visuals** ✅ done（2026-06-13，feature 2026-06-12-fusion-gantt-execution-visuals，Codex 设计两轮（2 阻塞：罩层 hover/active 三态闪回紫、overdue 优先级靠顺序不稳+dark 覆盖）+实现两轮（零阻塞，3 建议全采纳）审核收口；CDP 双主题目检 computed style 实测）— 甘特现场事实可视化：progress 完工置 100（gantt_tasks.py:245）+ execution-<status> 条形着色（css 列表 :220-223 追加）+ 侧栏详情补优先级/加工方式/时长、popup 补现场摘要一行（meta 字段双向互缺，gantt_popup.js:107-116/:162-176）。依赖：2（甘特模板双写税消除）。
13. **fusion-chain-walk-navigation** — 沿链巡检：详情面板上一道/下一道（前端 dependencies 反查建 Map，零后端改动）+ 关键链 ←/→（normalizeCriticalChain ids 正序）。依赖：12（软依赖：同在详情面板区施工避免冲突，非产物依赖）。
14. **fusion-gantt-fix-pack** — 甘特小修包（纯 bugfix/守卫，跑测试即可验收）：select 精确匹配（修 B1 带出 B12）+ 暗色 cc-outline 补丁 + 删"模拟调整"死按钮 + ZOOM_SPECS 与 min.js 双份真相 boot 断言。依赖：12（软依赖：同在甘特 JS 施工避免冲突，非产物依赖）。（UX 重排部分已按拍板拆为第 27 条。）
15. **fusion-gantt-load-strip** — 资源负荷热力条带（契约 4.6）：新建 gantt_resource_load.py 按资源×日桶聚合 + decorateStaticAfterRender 挂层像素对齐 + 容量来源明示 + 点击色带格弹出该资源当天任务清单与去派工/报表跳转（按 2026-06-11 拍板 B 案吸收老 item 11 验收点）。依赖：12（同在甘特装饰层钩子区施工，且条带格挂详情联动）、5（阈值与状态色 token 须先单源）。
16. **fusion-week-plan-enrich** ✅ done（2026-06-12，feature 2026-06-12-fusion-week-plan-enrich，Codex 设计两轮+实现两轮审核收口——实现首轮阻塞「空周跳转读错键 plan_resolution 误当 adopted」已修并复审逐条闭环；4.6 容量口径首个落地实例）— 周计划增强：现场状态列（_split_by_day 拆分前注入，逻辑全落 gantt_week_plan.py——gantt_service.py 仅余 5 行余量）+ Excel 导出同列 + 空周提示升级（get_plan_time_span_for_view 告知计划所在周并给跳转）+ 每日合计工时/容量行（容量分母按 4.6 协议：shift_hours×efficiency 同一公式、正午采样，禁直调 capacity_hours）。依赖：无。
17. **fusion-reports-index-kpi** — 报表中心答案卡（契约 4.7）：三张死文案卡注入最忙资源/停机小时/可复盘记录数 + 身份护栏 + Win7 性能实测与懒加载降级预案。依赖：无。
18. **fusion-batch-detail-schedule-card** — 批次详情排程去向卡：「最新正式方案中 N 道工序、跨度 X」摘要 +「在甘特中定位本批次」（gantt_batch 参数链路现成）+ 工序表现场实际列（须先查 adopted 计划行拿全身份，禁 op_id-only）。依赖：11（batch_detail 目标入白名单）。
19. **fusion-dashboard-cockpit** — 首页驾驶舱（构图 2026-06-11 定稿，样张 drafts/dashboard-restyle-proto.html）：单栏四段 = 上下文胶囊 → hero 指令卡（待办队列第 1 条置顶展示，下方明细清单**不重复**它；排产失败时 _failed_run_todo 顶格，result_status 已在手）→ 6 格体检表（超期/待排/方案待确认/现场待确认/资源压力/基础数据，每格即入口可点跳，正常项灰显——替代旧 stat-grid，"待排数"承接被裁的"最近一次排产"卡唯一增量信息）→ 其余待处理清单（3px 左语义条，不嵌灰盒）。删 stat-grid（先迁正则锚）+ 删按钮墙 + 删"下一步"链接卡（侧栏做事路线承接）+ 风险卡 severity 按 result_status 分级 + 死字段裁决（overdue_count/latest_summary 零消费且每请求白算一遍）+ 超期 todo 直挂主导线索摘要（性能门槛：仅 overdue_count 小时启用）+ 全健康空态定义（hero 转绿色平静卡"当前没有必须马上处理的风险"）。依赖：2、3（爆点清单先行）。
20. **fusion-dispatch-import-two-phase**（**已 dropped**）— 原拟接通 Excel 导入两段式预览/确认。2026-06-11 用户拍板不做：导入失败本就有报错与错误明细，预览徒增操作步数。后端两段式端点与契约测试保留不删。
21. **fusion-dispatch-split-pages** — 派工拆两页：「资源排班（查看）」与「现场记录（代录）」+ 琥珀模式横幅"正在向正式采用方案 vN 写入现场事实" + #rdGantt 补只读保护 + 旧 URL 302 过渡。依赖：10（侧栏分组承载新页入口）。
22. **fusion-longtail-unify** — 长尾收敛：excel_import_page 宏收编 11 个导入页 + 17 处旧 page-subtitle 页头迁 aps_page_hero（宏不在锚点清单，安全）+「护眼模式→深色模式」改名（4 文件零锚点+手册双写）。依赖：7（新样式体系定稿后做，避免二次返工）。
23. **fusion-todo-ack-state** — 待办处理留痕：单计划员"已确认/今天不再提醒"本地留痕（SQLite 小表，无账号无工作流），治"清单永远不变短"。依赖：19（留痕交互挂在 19 重排后的 hero 待办卡上）。注意：与 req `scheduler-daily-workbench` 的"不保存已处理状态"边界正面冲突，见观察项。
24. **fusion-quick-locate** — 全局快速定位：壳层输入批次/设备/人员，带当前计划上下文跳甘特定位/资源排班/超期清单（复用 WorkbenchLink + item 8 已锁的目标页高亮）。依赖：9。
**模块 G**
25. **fusion-performance-budget** — 性能预算守卫：首页/甘特/报表 index 基线数据集首屏预算 + 计时探针 + 超预算显式说明；报表 KPI 的 1→4 次计划行扫描实测定去留。依赖：17、15、19（在真实改造后定预算）。

**追加条目（2026-06-11 用户拍板拆分，编号顺延）**
26. **fusion-mirror-sync-guard**（模块 S）✅ done（2026-06-11，快速通道直落；**已随第 2 条完成按计划退役删除**）— 镜像逐字节同步守卫测试：tests/gate_meta/test_v1_v2_mirror_sync_guard.py，6 个镜像模板 + scheduler_manual.md 双份共 7 对参数化全等断言（核证修正：style.css 只存在于 V2 树不是镜像对），登记 QUALITY_GATE_GUARD_TESTS 挂 required 门禁 + ui_layout_presenters_system impact 组；红绿反证自证有效。第 2 条完成后随镜像树一并退役。依赖：无。
27. **fusion-gantt-controls-rework**（模块 W）— 甘特控件重排（UX，需截图基线评审验收）：解码条取代折叠图例（色样 chips 点击即筛选）+ 控件三层化（上下文面包屑/zoom 步进/筛选收纳）+ 宽屏禁浮层弹窗单一点击反应。依赖：12（软依赖：同区施工）。

**追加条目（2026-06-11 视觉定稿后补充）**
28. **fusion-analysis-action-refresh**（模块 W）— 排产分析页收口（需截图基线评审验收）：按定稿设计语言重排方案对比区（对比表去框化、采用/对比等行动按钮层级收口为一屏一个主按钮）+ 候选/正式身份徽标统一走 4.8 词表 + 页头接 4.2 胶囊不再自拼版本文案 + 空态（无候选方案）明示下一步去执行排产。依赖：9（胶囊先行）、5（token 先单源）。
29. **fusion-debox-table-wave**（模块 T）— 全站去框化与表格现代化波次（需截图基线评审验收）：嵌套灰盒清除（统一改 3px 左语义条 + 留白分层）+ 表格现代化（表头浅灰底、行 hover、数字列右对齐 tabular-nums、状态列徽标化）+ severity 三通道一致性扫尾（底色+徽标+圆点同步出现，按 4.4 认知原则③）+ 图标库扩容 13→约 30 枚（16px/2px 描边同风格；其中侧栏导航所需约 12 枚随第 10 条先行，遵同一规范）。依赖：22（长尾页结构先统一成宏再做全站视觉扫尾，避免对旧结构刷两遍）。

**追加条目（2026-06-11 用户拍板新功能，模块 N，契约 4.11 共同约束）**
30. **fusion-due-soon-alert**（模块 N）— 临期预警："3 天内到期且未完工"新待办类别 + 体检表格位（7 格排布还是与超期合并一格，feature-design 裁决）+ 临期窗口常量单点定义；数据 = 既有批次交期 vs 正式方案排程结束时间，与超期判定共用同一口径（4.11），零新数据链路。依赖：19（驾驶舱构图先落定，类别与格位才有挂点）。
31. **fusion-dispatch-print-sheet** ✅ done（2026-06-12，feature 2026-06-12-fusion-dispatch-print-sheet，Codex 设计两轮（3 阻塞：registrar 登记/警示判定 is_current_executable_official_version 三态/重名供应商错并组归兜底段）+实现两轮（1 阻塞：段内时间序补排）审核收口；CDP printToPDF 三态目检过 anchor-baseline 第三节）—（模块 N）周派工单打印（2026-06-11 按现场实践重定：车间按周打印计划）：按设备/按人员两个视图（同一份周计划 7 字段行重分组，gantt_week_plan.py:50-53 设备/人员格现成；每行带另一维度做交接参照）+ 窗口周为主、附单日切换（加急重排后补打当天）+ 一资源一页 page-break 整叠打印、本周无任务资源不出纸 + 人员视图含"外协/未分配"兜底段（沿 gantt_tasks.py:130 既有分组语义，没派人的工序不许从纸上静默消失）+ 每页页眉印方案版本与生成时间（防车间贴旧纸误用）+ 行尾空白备注列（手写用，不设签字栏，用户拍板）；打印入口挂周计划页，资源排班页落地后补导航链接（非依赖）；第一版只含计划任务不含现场事实（4.11 约束）。依赖：16（同文件 gantt_week_plan.py 施工，周选择器与空周提示先就位）。
32. **fusion-backup-health-hint** ✅ done（2026-06-12，feature 2026-06-12-fusion-backup-health-hint，Codex 设计三轮+实现一轮审核零阻塞收口）—（模块 N）备份健康提示：首页顶部纯只读扫描备份目录（不实例化 BackupManager——其 __init__ 有建目录副作用，违反 4.11 只读）取 aps_backup_*.db 最大 mtime，超 7 天琥珀提示"已 N 天未备份"（BACKUP_STALE_DAYS 常量单点）+ 备份目录读取失败时明示不静默（4.11）；仅 listdir 的 FileNotFoundError 归「从未备份」，其余 OSError 穿透。依赖：2（单树后挂壳层一次到位，免付镜像双写税）。
33. **fusion-plan-version-diff**（模块 N）— 新旧方案差异清单：工序级 diff（按批次+工序身份配对，报告换设备/挪时间/新增/移除四类变化）落新文件 core/services/scheduler/plan_version_diff.py + 分析页方案对比区展示 + "无差异/无法对比"诚实文案（4.11）。依赖：28（分析页收口后同区施工，避免对旧结构施工两遍）。
34. **fusion-runtime-log-viewer** ✅ done（2026-06-12，feature 2026-06-11-fusion-runtime-log-viewer，提交 ad6cfff9..b3415f9f 共 3 个，full gate 17 步全净通过）（模块 N）— 运行日志页与诊断包导出（2026-06-11 用户提出：现场报错要进文件夹翻 log，计划员无法自助反馈）：① 系统管理新增"运行日志"页，与既有"操作日志"页（system_logs.py，业务审计存库）并列命名区分；默认倒序展示 aps_error.log 最近条目（按时间戳行边界把多行 traceback 分组成条，块式倒读不整文件加载），可切 aps.log / launcher.log（启动失败死因在此），按级别/关键词筛选；② 一键"导出诊断包"——logs/ 下 *.log（含轮转分卷）+ 版本与环境信息 + 最近若干条操作日志（对照报错前的用户动作）打 zip 下载，**安全硬约束：白名单制——`*.log` + 轮转分卷 `*.log.[0-9]+` + 显式列名的 aps_launch_error.txt（启动失败关键证据，2026-06-11 设计审核拍板的唯一 .txt 例外），严禁把同目录 aps_secret_key.txt 打进包**；③ 报错出口接门：errorhandler(500)/error_boundary 的"请查看日志"文案升级为"发生时刻 + 打开运行日志链接"（error_handlers.py:100-110、error_boundary.py:316/344）；只读不写、不提供删除/清空（轮转管大小，报错证据不许销毁，较操作日志页的删除功能刻意收窄）。依赖：无；建议排最早批次——后续条目逐条上线时现场排障全靠它。

**最小闭环**：第 1 条 `fusion-v2-quickwin-pack` 做完后，默认界面第一次能看到「计划工作台」入口、警示框恢复样式、首页时间口径正确——端到端可演示且全部是用户当天可感知的修复。

## 6. 排期思路

按"先止血 → 先裁决 → 先地基 → 再融合 → 后收尾"排：1 与 26（急救 + 镜像守卫，均半天级）→ 2（裁决+删双轨，一切模板工作的前置，否则每条都付双写税）→ 3 与 16/17/11（无依赖件并行：基线准备 + 纯后端/JS 融合速赢）→ 5→6→7 与 4（令牌轨道）→ 8→9→10（上下文轨道）→ 12→13/14/27/15（甘特轨道）→ 18/19 → 28（分析页收口，胶囊与 token 就位后）→ 21 → 22 → 29（全站视觉扫尾，长尾结构统一后）→ 23/24 → 25。（20 已按用户拍板 dropped。）模块 N 五件穿插其间：**34 运行日志页无依赖，排进最早批次（与 1/26/3 同批）——它是后续所有条目现场测试排障的眼睛，先有眼睛再动手术**；32 备份提示在 2 之后随时可做（半天级）；30 临期预警紧跟 19；31 周派工单紧跟 16（周计划轨道——16 无前置链，故派工单比挂资源排班页的原案早交付得多）；33 版本差异紧跟 28——其余都是小件，跟着宿主页面的收口走，不单独占轨道。两条轨道（令牌 vs 融合）文件不相交可双线并行；甘特轨道内部串行避免同文件冲突。第 1 条选最小闭环是因为它把评审发现的"已完成功能在默认界面不可见"这一最不对称的价值/成本比先兑现。

## 7. 观察项

- **老 roadmap `aps-frontend-workbench` 的 9/10/12/13 需要一次 update**（本 roadmap 不代改；2026-06-11 用户已确认：动老计划任何一条之前先做该对账修订）：① 五条的 primary_paths/test_commands 全部指向 P6 重组前的扁平路径，item 9 的测试文件已物理删除；② item 10 的接入点应改为 execution_fact_provider.py（145 行现成 API），原列的写侧服务已 499/500 行，且实现须三层同改（服务/展示白名单/模板）并收口"没有现场执行反馈"双写文案（schedule_delay_diagnosis_service.py:96,141 与 delay_diagnosis_presentation.py:87）；③ item 12 的实现路径=downtime_impact.py 索引结构改 Dict 保留 batch/op 身份；④ item 13 不能用 networkx 图层（批内线性边，无跨批次边），最短路径是新建 schedule_downstream_impact.py 复用 gantt_critical_chain 的节点表（:116）与两张前驱表（:142/:163，均需公开导出），且 schema 无订单实体须改窄为批次级口径。
- **老 item 11（gantt-resource-load-summary）与本 roadmap 第 15 条目标重叠**：2026-06-11 用户已拍板 B 案——由第 15 条替代并吸收老 11 验收点（Top-N 以色带排序承接、任务数与跳转入口经点击弹层承接）；老 roadmap update 时将老 11 标 dropped 指向本条。
- **第 20 条已按用户拍板 dropped**（2026-06-11）：导入失败本就有报错与错误明细渲染，预览徒增操作步数。老 roadmap"短期不做预览"口径与 req `shop-floor-execution-feedback` 维持不变、无需回写；后端两段式端点与契约测试保留不删。
- requirement `scheduler-daily-workbench` 的"停机影响第一版只做设备级"边界将随老 item 12 演进，验收时回写 req（本 roadmap 不动）。
- 甘特 payload 顶层暴露 schedule_id（gantt_tasks.py:240 与 meta :252）属既有内部字段外泄面，治本涉 gantt_contract.js 契约版本，建议单独立 issue。
- quality_gate_ledger 对 web/ui_mode*.py 启动链分类全量冻结——第 2 条删文件会触发台账失配，执行前先跑 gate scan 看红量并同步台账数据。
- 利用率"同名两口径"（algo makespan vs 报表日历容量）建议用 cs-semantic-radar 立概念身份证；第 17 条文案已要求口径标注。
- 'btn-' 类族与表格密度三档零测试锚定——若后续重做按钮体系，先补锚再动。
- docs/aps_frontend_workbench_mockup.html 建议加定位声明头："信息架构基准，非视觉验收基准；26px 圆角/玻璃拟态/Inter 不作为还债项"。
- 机器级日历容量细分无数据来源（CalendarEngine 收 machine_id 但实现只用 operator_id，无 MachineCalendarRepository）——属新数据链路需求，若要做请走 cs-req 先立愿景。
- 浏览器几何冒烟单进程 90s 硬超时（已耗 ~19s）——改版大量加页/加重 CSS 时最先爆 node_probe_timeout，排障形态特殊，留意。
- **第 23 条 fusion-todo-ack-state 与 requirement `scheduler-daily-workbench` 的边界正面冲突**（req 明文"不保存'已处理/已忽略/指派给谁'的状态，提醒实时生成"，用户故事还专门写了"不要让我以为它记住了处理进度"）——2026-06-11 用户已确认推翻该边界，验收时回写 req。
- 存量报表链 capacity_hours 的 midnight 采样在跨午夜班次**已有**双计/错计风险（非本 roadmap 引入）——建议按 4.6 正午口径给存量报表侧补测试，可并入第 16 条验收或单独小修。
- networkx 老 roadmap 的 PR-9（scheduler-graph-analysis-diagnostic-sections）台账滞后：实现已落地并被 analysis.html:30 消费，items 仍标 planned——建议 update 对齐，防后续重复立项。
- 人员停机维度无数据来源（MachineDowntimes 仅设备维度；OperatorCalendar 是排班可用性语义非停机事件）——要做"人员缺勤影响"属新数据链路，先走 cs-req。
- 颗粒度拆分已按用户拍板执行（2026-06-11）：原第 14 条一分为二（14 甘特小修包 + 27 甘特控件重排，验收方式不同）；镜像守卫从第 1 条单拎为第 26 条，第 2 条改为只依赖守卫。
- test_frontend_ui_language_polish.py 自身是门禁长缓存的指纹源——文案类变更建议攒批合入，每改一次该文件长缓存全量失效。
- 设计样张存档 drafts/dashboard-restyle-proto.html（2026-06-11 定稿：浅色侧栏 + 12 列栅格 + 单栏四段构图）——定位是**构图与层级基准**，非像素级验收基准；逐页落地以截图基线评审为准。
- "现场最新动态流"**已裁决不做**（2026-06-11 用户拍板）：未接 MES/自动采集时，现场记录全部是计划员自己代录的，动态流本质是给自己看自己刚输入的内容，信息价值不成立。若未来接入 MES 再走 cs-req 立愿景；在那之前不要再提案。

## 8. 变更日志

- 2026-06-11：新建 roadmap。承接 2026-06-10 全面设计评审（三评委一致裁定方向 B + V2 侧栏转正合成裁决）与 8 域能力挖掘 130 条对抗核证结论；25 条子 feature 全部带 file:line 级接线证据，证据全文见 drafts/capability-mining.md。
- 2026-06-11：三视角对抗复审修订（5 阻塞收口）。接口契约变化：4.6 由"负荷条带单 feature 契约"改写为跨 feature 容量口径共享协议（修正"复用 capacity_hours"自相矛盾——该函数 midnight 采样无时刻参数，改为"同公式正午采样、禁直调"）；4.7 由"报表答案卡单 feature 契约"改写为 adopted 聚合注入共享护栏；4.2 修正 dashboard 双发布点（:275/:338 后写覆盖）与 publish 模块真实路径、补报表发布点 file:line、补 442/500 行余量约束；4.8 补第三候选字源并标注 cs-decide 级；4.9 黑名单补白名单豁免。其余：todo-ack 与 req 冲突、跨午夜容量存量风险、networkx PR-9 台账滞后等 7 条补入观察项；依赖理由补全（7→6、13/14→12 软依赖标注、23→19）。受影响的已启动 feature：无（全部 planned）。
- 2026-06-11：用户拍板落账（六件）。① V2 侧栏壳转正与 token 标准表确认；② 第 23 条确认推翻 req"不保存处理状态"边界，验收时回写；③ 第 20 条 dropped——不做导入预览（已有报错机制，预览徒增步数），后端端点保留；④ 第 15 条采 B 案，吸收老 item 11 的 Top-N/任务数/跳转验收点（点击色带格弹层承接）；⑤ 拆分落地：原第 14 条一分为二（14 小修包 + 27 控件重排）、镜像守卫单拎为 26、第 2 条依赖改指 26，条目数 25→27；⑥ 确认动老计划前先做对账修订。接口契约无变化；受影响的已启动 feature：无。
- 2026-06-11：视觉定稿落账（全面调整方案经三轮样张迭代后用户委托裁定）。① 侧栏定版浅色（用户拍板），写入 4.3 约束；② 12 列版面栅格 + 认知五原则写入 4.4，升为全站构图契约；③ 第 19 条按定稿构图改写——单栏四段（胶囊 / hero 置顶队列首条 / 6 格体检表 / 其余清单），裁掉"最近一次排产"卡（与胶囊重复，唯一增量"待排数"并入体检表）与"下一步"链接卡（与侧栏重复），治同屏三处信息重复；④ 新增第 28 条分析页收口（模块 W）、第 29 条全站去框化与表格现代化波次（模块 T），条目数 27→29；⑤ 样张存档 drafts/dashboard-restyle-proto.html。接口契约变化：4.3/4.4 增补构图级约束，对未启动 feature 即时生效；受影响的已启动 feature：无（全部 planned）。
- 2026-06-11：新功能拍板落账（四件做 + 一件裁决不做）。新增**模块 N · 闭环补全**（与 W 分界：W 只消费已有字段，N 允许新增只读算法、禁止写排产数据）承载用户拍板四件：30 临期预警、31 今日派工单打印、32 备份健康提示、33 新旧方案差异清单，条目数 29→33；新增契约 4.11（N 模块共享约束：只读不写/常量单点/身份遵 4.7-4.10/空态失败态诚实）。"现场动态流"裁决不做——未接 MES 时现场数据全为计划员代录，动态流信息价值不成立，观察项已固化该裁决。提案前已逐项验证非重复（临期/派工单/备份提醒/工序级 diff 四概念全仓不存在，print.css 基建已有）。受影响的已启动 feature：无（全部 planned）。
- 2026-06-11：第 31 条按现场实践重定（用户提供现场真相：车间按周打印计划，原"今日派工单"假设作废）。改为周派工单：周为主 + 单日切换补打（用户拍板）、按设备/按人员双视图（周计划行设备/人员格现成，零新数据链路）、一资源一页整叠打印、人员视图"外协/未分配"兜底、页眉印版本与生成时间防旧纸误用、行尾备注列不设签字栏（用户拍板）；挂载点从资源排班页改周计划页，依赖 21→16（同文件施工；副作用 = 交付大幅提前，16 无前置依赖链）。受影响的已启动 feature：无。
- 2026-06-12：4.2 契约三处修订（fusion-plan-context-capsule design 审核两阻塞拍板）：① strategy_label 未知值文案从"未识别的策略"改遵 #8 词表单源（"历史记录异常"/"旧历史未记录"——原文先于 #8 完成而写，不造第三套文案）；② 发布点清单补 resource_dispatch（_workbench_context 直接 build+set_current 是真实发布点，原文漏列），5→6 处；③ "版本号在页面正文只允许出现在胶囊一处"改两阶段口径（阶段一第 9 条壳层 chrome 单点；阶段二第 28/19 条正文清理+正文唯一性断言；数据行与选择器选项永久豁免）。受影响的已启动 feature：无（第 9 条 design 即本修订发起方）。
- 2026-06-11：第 34 条红线表述修订（design 审核发现"只收 *.log 通配"会把启动失败证据 aps_launch_error.txt 排除在外）：改白名单制，*.log+分卷+显式列名的 launch_error 例外，secret 排除红线不变。
- 2026-06-11：新增第 34 条运行日志页与诊断包导出（模块 N，用户提出：现场报错要进文件夹翻 log、计划员无法自助反馈维护者）。落账前验证既有底子：logging.py 双文件轮转（aps.log/aps_error.log 带文件名:行号）+ errorhandler(500) 已记完整 traceback，但页面文案"请查看日志"没给入口；与既有"操作日志"页（业务审计存库）是两类日志，并列不合并。安全硬约束写入条目：诊断包只收 \*.log 通配（**该表述已被上一条 2026-06-11 修订取代：白名单制**），严禁打入同目录 aps_secret_key.txt；刻意不提供删除/清空（报错证据不许销毁）。排期进最早批次（无依赖，是后续条目现场排障的眼睛）。条目数 33→34。受影响的已启动 feature：无。
