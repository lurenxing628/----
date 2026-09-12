---
doc_type: roadmap
slug: workbench-ui-refinement
status: completed
completion_scope: completed-with-validation-limit
full_gate_status: failed
review_status: approved
created: 2026-09-12
last_reviewed: 2026-09-13
tags: [aps, workbench, frontend, ui, ux, design-system, win7]
related_requirements: [workbench-production-workflows, scheduler-daily-workbench, gantt-readonly-result-view, shop-floor-execution-feedback]
related_architecture: [workbench-shell, ARCHITECTURE]
related_roadmaps: [workbench-prototype-migration]
---

# 新工作台界面质量整改路线图

## 1. 背景

2026-09-12 对已接通后端的新工作台（`frontend/workbench/app/` + `frontend/workbench/prototype/`）做了一轮界面审查：用 v14 备份副本起隔离服务器，Chrome 通过 CDP 在 1366×768 / 1280×720 / 1920×1080 三种尺寸、浅色和深色下截取 15 个工作区和 20 多个交互步骤，共 69 张截图；另由四路子代理分别审样式系统、两组工作区交互和跨页一致性。证据与逐条 `文件:行号` 收在本目录 `drafts/2026-09-12-ui-review-findings.md`。

结论是底子好、三类问题拖后腿：

1. 目标分辨率下的首屏与溢出。1366×768 下批次表的操作列整列在横向滚动区外，选完计划后甘特图本体仍在首屏外，侧栏最后一项被截掉；1280 宽下多页错位。
2. 信息架构。侧栏 14 项只对应 11 个组件，同一功能多入口，落地页值班台放在最后一组，"先选目录再看内容"的两步式让最常用路径多一次点击。
3. 一致性与文案。48 位内部哈希多处直接显示，同一后端字段有 4 个中文名，表格、药丸、空态、分页各自手写十几套，样式散在 38 个 JSX 内嵌 `<style>` 里，令牌大半没接线。

这些问题横跨外壳、样式基座、共享控件和十几个工作区，单个 feature 装不下，也不能各页各修一遍再重新发明轮子，所以先在这里把模块边界和共享合同定下来，再拆成子 feature 逐条走 `cs-feat`。

本路线图与 `workbench-prototype-migration` 的关系：那份负责"接通真实后端、逐动作验收、退役旧界面、Win7 发布"，本份只管界面质量，不改领域 API 与业务规则。两份并行时，本份每条子 feature 都要重跑受影响的既有工作台合同测试，不能让迁移验收的证据失效。

2026-09-12 用户已批准按审查意见修订并并行实施。执行协调、源码与历史截图基线、文件所有权见 `implementation-20260912.md`。旧迁移验收证据仍只代表其冻结源码与 build_id；每项记录影响的动作/工作区和需要重跑的浏览器证据，最终在统一 UI 构建冻结后重新验收，不把局部合同通过当成旧截图已覆盖新版本。

当前21项实现已完成。最终e696构建的60页面、8交互、4密度矩阵及每日门禁均通过；完整门禁的实际结果保留为16491 passed、1 failed、11 skipped，唯一失败的KB旧测试预期已修正并通过完整受影响模块。用户明确要求不再为此重跑完整门禁，因此本路线图按`completed-with-validation-limit`收尾，不宣称全量全绿或clean-worktree proof。详细结果见[统一验收记录](acceptance-20260912.md)。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 外壳：侧栏分组与尺寸、顶栏全局控件、视图别名与页内页签。
- 样式基座：应用自有 CSS 层、令牌接线（字号、z-index、语义色）、交互态、视口预算、原型死样式清理。
- 共享控件：表格框（吸顶表头、固定操作列）、详情面板、空态与加载态、分页器、字段级校验、脏草稿守卫、格式化模块、术语表、内部标识收纳。
- 工作区首屏与高频路径：计划中心三页、执行排产、现场实际甘特、现场报工、值班台详情、批次表单、报表与复盘的"未知"呈现、系统管理诊断折叠。
- 验证协议：双尺寸双主题截图基线、几何断言进门禁、主按钮唯一性检查。

### 明确不做

- 基础资料首屏的产能链图重排。用户明确指定不动。本路线图只在 `wbui-viewport-budget` 里修它在 1280 宽下卡片互相重叠的错位，不改首屏结构；若用户也不要修，去掉该条即可。
- Win7 打包、真机验收、最终发布、旧入口退役。归 `workbench-prototype-migration`。
- 领域 API 与业务规则改动：导入"只导正确行"（现行整批原子是业务边界，要改先走 `cs-req`）、排产任务取消（需要运行时支持）、外协登记接入、全局搜索。UI 侧只消费已有 DTO。启动信息新增 `nav_groups`、`view_aliases`、`help_url` 三个只读字段，帮助复用现有手册 URL；维护恢复模板只调整呈现，不新增领域 API。
- 1920 宽下限制内容宽度。数据密集型工具全宽更合适，不做。
- 试调从 `/workbench/trial` 改为 `?view=trial`。会破坏已验收的入口合同与用户收藏，记观察项不做。
- 新运行时、新依赖、新构建工具。继续 React 18.3.1 + Babel 7.29 预编译，目标 Chrome 109，全部资源本地交付。

## 3. 模块拆分（概设）

```
新工作台界面质量整改
├── M1 外壳与导航：侧栏分组、顶栏全局控件、视图别名与页内页签
├── M2 样式基座：应用自有 CSS 层、令牌接线、交互态、视口预算、死样式清理
├── M3 共享控件层：表格框、详情面板、空态/加载态、分页器、字段校验、脏草稿守卫、格式化与术语
├── M4 工作区改造：各页首屏、主操作层级、高频路径，只消费 M2/M3 的合同
└── M5 验证协议：截图基线、几何断言、主按钮唯一性、合同测试更新
```

### M1 · 外壳与导航

- **职责**：`main.jsx` 外壳、侧栏渲染、顶栏、视图到组件的映射；导航分组从后端启动信息读取而不再由原型 `AppShell.jsx` 常量决定。
- **承载的子 feature**：`wbui-nav-boot-groups`、`wbui-header-controls`、`wbui-view-tabs-merge`。
- **触碰的现有代码**：`frontend/workbench/app/main.jsx`、`web/routes/workbench/pages.py`、`tests/web_pages/test_workbench_nav_entry_contract.py`；原型 `AppShell.jsx` 里的 `NAV_GROUPS` 停止被生产壳消费。

### M2 · 样式基座

- **职责**：提供受版本控制的应用 CSS 层并接进构建与清单，定义令牌、层叠顺序、交互态和视口预算规则；不含任何业务页面的专用样式。
- **承载的子 feature**：`wbui-css-layer-table-frame`（同时是 M3 表格框的首个落地）、`wbui-tokens-states`、`wbui-viewport-budget`、`wbui-prototype-css-cleanup`。
- **触碰的现有代码**：`scripts/workbench/build.py`、`scripts/workbench/build-order.json`、`static/workbench/asset-manifest.json`、`frontend/workbench/app/WorkbenchControlStyles.jsx` 及各 `*Styles.jsx`、`frontend/workbench/prototype/ui_kits/workbench/*.css`（只读参照，清理时才动）。

### M3 · 共享控件层

- **职责**：在 `window.ResourceControls` / `window.WorkbenchControls` 上补齐所有工作区共用的控件与规则，替代各页手写版本；控件只做呈现与焦点管理，不发请求、不保存业务事实。
- **承载的子 feature**：`wbui-detail-panel`、`wbui-empty-loading-pager`、`wbui-field-validation`、`wbui-dirty-guard`、`wbui-format-module`、`wbui-terms-and-ids`。
- **触碰的现有代码**：`frontend/workbench/app/ResourceControls.jsx`、`WorkbenchControls.jsx`、`WorkbenchPageContext.jsx`、`main.jsx` 的 `navigate`，以及新增文件 `WorkbenchFormat.js`、`WorkbenchTerms.js`、`WorkbenchDetailPanel.jsx`、`WorkbenchGuards.js`。

### M4 · 工作区改造

- **职责**：各工作区按第 4 节合同接入共享控件，修首屏、主操作层级和高频路径；每条只动本页的 JSX 与本页专用样式。
- **承载的子 feature**：`wbui-plan-center-first-screen`、`wbui-run-stepper`、`wbui-actual-gantt-window`、`wbui-field-report-fastpath`、`wbui-table-density-noise`、`wbui-a11y-sweep`、`wbui-system-page-polish`。
- **触碰的现有代码**：`Plan*.jsx`、`Preflight*.jsx`、`Run*.jsx`、`ActualGantt*.jsx`、`Field*.jsx`、`Dashboard*.jsx`、`Batch*.jsx`、`Report*.jsx`、`Review*.jsx`、`System*.jsx`。

### M5 · 验证协议

- **职责**：把"看得见的回归"变成可重跑的证据：双尺寸双主题截图基线、几何断言、主按钮唯一性检查，以及合同测试的同步更新规则。
- **承载的子 feature**：`wbui-ui-baseline-gate`。
- **触碰的现有代码**：`tests/ui_baseline_capture.mjs`、`tests/ui_geometry_probe_scenarios.mjs`、`tests/app_runtime/test_ui_browser_geometry_smoke.py`、`tests/workbench-*.cjs`。

## 4. 模块间接口契约 / 共享协议（架构层详设）

以下合同是每条子 feature 的硬约束。feature-design 发现不合理，先回本文件 update，不在 feature 里绕开。

### 4.1 样式分层与构建协议

**方向**：M2 定义，M1/M3/M4 消费，M5 校验。
**形式**：文件目录约定 + 构建脚本 + 资源清单。

```
frontend/workbench/app/styles/            应用自有 CSS 层（受版本控制）
  00-tokens.css       只放 --wb-* 令牌补充与暗色重映射；不放选择器规则
  10-shell.css        外壳：侧栏、顶栏、消息条
  20-controls.css     共享控件：按钮态、表格框、详情面板、空态、分页器、字段校验
  30-workspaces.css   工作区通用布局；专用规则拆为 31-*.css 等职责文件

scripts/workbench/build-order.json 新增键：
  "styles": ["00-tokens.css", "10-shell.css", "20-controls.css", "30-workspaces.css", ...显式登记的职责文件]

scripts/workbench/build.py：
  发布到 static/workbench/app/styles/<name>.css
  manifest.styles = [原型 styles 原顺序...] + ["workbench/app/styles/<name>.css" ...]
  asset_records 中 origins = ["frontend/workbench/app/styles/<name>.css"]，inputs 同步登记
```

**规则**：

- 层叠顺序固定为：原型 tokens → 原型 ui_kits CSS → index.inline.css → 应用 CSS 层 → 各脚本。应用 CSS 层靠顺序赢同特异度，禁止为此加 `!important`。
- 新代码不得在 JSX 里新增 `<style>`；现有 38 个 `*Styles.jsx` / 内嵌 `<style>` 在各自子 feature 接手时迁入对应 CSS 文件，迁完删除。
- 颜色只允许 `var(--ui-*)`、`var(--wb-*)`；应用 CSS 层内出现裸 hex / rgb 视为违规，由 M5 的样式测试拦截。
- 字号只允许 `var(--font-size-1..5)`、`var(--font-size-kpi)`（`frontend/workbench/prototype/tokens/typography.css` 已定义 12/13/14/17/22/28），禁止半像素值。
- `!important` 仅允许出现在 `20-controls.css` 且每处前一行必须有 `/* override: <被压制的选择器与原因> */`。
- 原型层文件是 `前端设计/` 的导入快照，构建校验哈希；本路线图除 `wbui-prototype-css-cleanup` 外不修改原型层。确需改原型层时流程固定为：改 `前端设计/`，`python scripts/workbench/import_prototype.py --update`，再 `python scripts/workbench/build.py`。
- 每次改动样式或 JSX 后必须 `python scripts/workbench/build.py` 并把 `static/workbench/` 一并提交；`tests/workbench/test_entry.py`、`tests/app_runtime/test_validate_dist_static_payload.py`、`tests/web_pages/test_ui_contract_component_tokens.py` 三处清单合同随首条 feature 更新为"允许 `workbench/app/styles/` 前缀"。

### 4.2 令牌补充

**形式**：`frontend/workbench/app/styles/00-tokens.css`，`:root` 声明，暗色在同文件 `html[data-theme="dark"]` 重映射。

```css
:root {
  /* z 阶梯：所有 z-index 只能取这五个 */
  --wb-z-sticky: 10;      /* 吸顶表头、固定列、甘特轴 */
  --wb-z-dropdown: 1000;  /* 下拉、列筛选浮层、tooltip */
  --wb-z-modal: 10000;    /* 弹窗遮罩与弹窗（与现有 FieldControls 一致） */
  --wb-z-popup: 12000;    /* 弹窗之上的日期/选择浮层（与现有 wb-control-popup 一致） */
  --wb-z-toast: 13000;    /* 全局提示 */
  /* 布局 */
  --wb-sticky-top: var(--header-height);   /* 外壳保证顶栏实际高度等于该值 */
  --wb-sidebar-item-h: 32px;
  --wb-sidebar-group-h: 22px;
  --wb-detail-w: 320px;
  --wb-line-tight: 1.3; --wb-line-body: 1.5; --wb-line-relaxed: 1.7;   /* 行高阶梯（2026-09-13 第二轮） */
  --wb-scroll-shadow: var(--ui-info-muted);  /* 固定列滚动阴影，深色为 var(--ui-bg) */
  /* 严重度别名，供消息条、徽标、图例统一取色 */
  --wb-sev-ok: var(--ui-success);
  --wb-sev-notice: var(--ui-primary);
  --wb-sev-warning: var(--ui-warning);
  --wb-sev-danger: var(--ui-danger);
}
```

**约束**：圆角沿用 `workbench-ui.css` 已定的 `--wb-radius-surface: 0px / --wb-radius-control: 4px / --wb-radius-overlay: 8px`，不新增第四套名字；`--wb-gantt-radius-control` 与 `--wb-control-radius` 在 `wbui-tokens-states` 中改为引用上述三个。

### 4.3 表格框合同 `wb-table-frame`

**方向**：M2 定义样式，M4 各列表页消费。
**形式**：DOM 结构 + class 名 + CSS 变量。

```html
<div class="wb-table-frame" data-sticky-head data-sticky-actions style="--wb-table-min: 1100px">
  <table class="wb-table" aria-label="批次列表">
    <caption class="wb-visually-hidden">批次列表</caption>
    <thead><tr>
      <th scope="col" class="wb-col-key">批次号</th>
      ...
      <th scope="col" class="wb-col-actions">操作</th>
    </tr></thead>
    <tbody>...</tbody>
  </table>
</div>
```

**规则**：

- 框：`overflow: auto; max-height: var(--wb-table-max-height, calc(100vh - 280px))`，表 `min-width: var(--wb-table-min)`；表格在框内双向滚动，工作区按首屏工具条高度调整预算。页面级不得因表格横向溢出，且局部关键列须可见、可点击。
- `[data-sticky-head] thead th { position: sticky; top: 0; z-index: var(--wb-z-sticky); background: var(--ui-table-head-bg) }`，吸顶相对表内滚动框，不使用顶栏高度作为偏移。表头/固定列交叉处须高于普通固定单元格。
- `.wb-col-actions { position: sticky; right: 0; z-index: var(--wb-z-sticky); background: var(--ui-card-bg); box-shadow: -1px 0 0 var(--ui-border) }`；`.wb-col-key` 同理固定在左。
- 滚动阴影（2026-09-13 第二轮）：`WorkbenchScrollShadows.attach(container)` 给每个 `.wb-table-frame` 按实际遮挡打 `data-overflow-left/right`，CSS 只在有标记时给固定列叠加 `var(--wb-scroll-shadow)` 阴影；放得下的表格无阴影，滚到底阴影消失。报表 `.rw-fixed-*` 与校准明细固定列复用同一标记。
- 表头 `word-break: keep-all`：中文列名只在空格或斜线处换行，列宽预算须放得下自己的列名；表头内的排序/筛选按钮继承表头颜色。
- 表头排序/筛选图标默认 `opacity: 0`，`th:hover, th:focus-within, th[aria-sort], th[data-filtered]` 时显示；表头文字用 `--ui-text` 而非链接蓝。
- 每张表必须有 `<caption>`（可视觉隐藏）与 `th[scope]`。
- 现有 `.bd-op-table table { min-width: 1320px }`、`.batch-list-table table { min-width: 1100px }` 等硬底改走 `--wb-table-min`，并满足 4.6 视口预算。

### 4.4 导航启动信息协议

**方向**：`web/routes/workbench/pages.py` → `main.jsx`。
**形式**：`boot` JSON 新增字段，`schema_version` 保持 1（只增不改）。

```
boot.nav_groups: [
  { "title": str,                       # 组标题，不带序号字符
    "items": [ { "id": view_id, "label": str, "icon": icon_name } ] }
]
boot.view_aliases: { "delay": "analysis" }   # 无侧栏入口的视图高亮到哪一项
boot.help_url: str                            # 现有只读手册路由，相对路径；壳层点击帮助时附加 src=当前视图 URL，手册页据此渲染“返回”
约束：
  - 所有 items[].id ∈ VIEW_TITLES 且 ∈ enabled_views；label 必须等于 VIEW_TITLES[id]
  - icon_name ∈ 本地图标集（AppShell 现有 P 表：box database play home gantt chart users clipboard file grid settings scale，可追加，不得重复用于同组两项）
  - main.jsx 只渲染 boot.nav_groups，不再引用原型 NAV_GROUPS；href 规则不变：trial → boot.trial_url，其余 → entry_url?view=id
  - 只从 boot.nav_groups 派生菜单顺序与渲染一致性；独立断言15个支持视图、核心可达入口及旧URL/context。不得从可见菜单推导 enabled_views。
```

**已批准默认分组**：

```
值班台                                  dashboard
数据准备      基础资料 process · 主数据总览 basedata · 批次管理 batches
执行排产      执行排产 run · 选择排产方案 analysis · 方案试调 trial · 设备/人员/批次甘特 gantt
现场          现场记录 field · 现场实际甘特 fieldgantt
统计分析      执行复盘 review · 报表中心 reports · 工时定额校准 calib
系统          系统管理 system
```

`wbui-view-tabs-merge` 落地后 gantt 与 review 从侧栏移除，成为页内页签，`?view=gantt`、`?view=review`、`?view=delay` 继续作为入口别名有效。

### 4.5 共享控件合同

**方向**：M3 定义，M4 消费。全部挂在 `window` 全局，遵循现有无模块打包方式。

```
ResourceControls.Button 新增 prop
  reasonDisplay?: 'inline' | 'tooltip'   默认 'inline'；tooltip 用于表格操作列与工具栏：原因进 title 与视觉隐藏的 aria-describedby 说明节点，其他取值抛错（2026-09-13 第二轮）
  <span class="wb-reason" role="status">{reason}</span>，键盘与触屏可见

window.WorkbenchDetailPanel({ title, subtitle?, actions?, onClose, children })
  渲染 <aside class="wb-detail" role="region" aria-label={title}>
  ≥1280 宽：右侧固定列，宽 var(--wb-detail-w)；<1280：内容下方整宽并 scrollIntoView
  挂载时焦点移到标题（tabIndex=-1）；Esc 调 onClose 并把焦点还给触发元素；不锁滚动
  消费方：值班台条目详情、报表/复盘工序详情；主数据总览现有侧栏改为同一组件

WorkbenchControls.EmptyState({ kind: 'empty' | 'filtered' | 'error' | 'loading', title?, hint?, action? })
  empty    默认 "暂无记录"
  filtered 默认 "当前筛选没有匹配项" 且必须给 action 清除筛选
  loading  role="status" aria-busy="true" 默认 "正在读取…"
  error    内部复用 ErrorBox，必须给 action 重试
  class="wb-empty"，列表页三态只能通过它渲染

WorkbenchListControls.Pager({ page, pages, total, size, sizes, unit = '项', onPage, onSize, mode = 'page', hasMore?, onNext?, onPrevious? })
  页码模式文案 "共 {total} {unit} · 第 {page} / {pages} 页"；sizes由消费方按现有领域合同显式传入
  游标模式仅显示已读取段及上一段/下一段，不虚构total/pages；同时挂载到WorkbenchControls作兼容入口
  替代现有 8 处独立 Pager

ResourceControls.Field({ label, path, error, required, full, hint?, children })
  从 ResourceForms.jsx 抽出，保持现有 aria-invalid / aria-describedby / aria-required 行为
  表单提交失败时由表单容器调用 focusFirstInvalid(formElement)，滚动并聚焦首个 [aria-invalid="true"]
  同一条错误只允许渲染一次：字段级错误进 Field，非字段级进 ErrorBox；Issues 不重复字段级消息，相同 message 合并为一行并标注条数

window.WorkbenchGuards
  useDirtyGuard({ owner?, dirty: bool, message: str, locked?: bool }) -> owner
  register({ owner, dirty, message, locked? }) -> unsubscribe
  hasDirty({ owner?, excludeOwners? } = {}) -> boolean
  confirmLeave({ owner?, excludeOwners? } = {}) -> Promise<boolean>
  等待确认期间受保护条目全部保存或卸载时自动 resolve(true) 并关闭确认框；locked 只来自待核实命令，目录弹窗、重读资料等 UI 忙碌态不得传 locked
  GuardHost在工作区view:key外挂载，用guardBypass的ResourceControls.Modal确认，不递归守卫自身
  navigate、同文档前进/后退、Modal的Esc/关闭/遮罩、编辑器取消必须覆盖；外部离开由beforeunload保护
  拒绝离开必须保持URL/视图/草稿一致；locked沿用pending命令的不可放弃边界

window.WorkbenchFormat
  dateTime(value, { seconds = false } = {}) -> 'YYYY-MM-DD HH:mm' | 'YYYY-MM-DD HH:mm:ss'
  date(value) -> 'YYYY-MM-DD'
  instant(value, { seconds = false } = {}) -> 本机本地日期时间（输入必须为明确带Z或时区偏移的时刻）
  integerText(value) -> canonical非负整数字符串精确千分位，不能转Number丢精度
  number(value, { digits = 1, trim = false } = {}) -> zh-CN 千分位；digits 为小数位，trim=true 去掉末尾 0（"最多 digits 位"）；-0 与四舍五入到 0 的值显示为 0
  percent(ratio, digits | { digits, trim }) -> '87.3%'（输入为有限比值；业务取值范围由既有DTO合同校验，显示层不新增0..1限制）
  hours(value, digits | { digits, trim }) -> '3.3 h'；录入类工时（工序定额、报工累计与跨度、候选对比指标）必须用 trim 保留录入精度，不得用 1 位摘要
  空值（null / undefined / ''）一律返回 '未知'；格式非法抛 TypeError，由 WorkbenchBoundary 显示，不静默兜底
  dateTime/date按工厂本地文本直出，不做时区换算；instant转换明确时刻，系统自检checkedAt使用instant

window.WorkbenchTerms（frontend/workbench/app/WorkbenchTerms.js）
  { overdue_count: '预计超期批次', delay_hours: '超期时长', total_tardiness_hours: '总拖期',
    utilization: '利用率', candidate: '候选方案', official_plan: '正式计划', trial: '试调',
    actions: { add: '新增', save: '保存', confirm: '确认', cancel: '取消', clear: '清除', import: '导入', export: '导出', download: '下载' } }
  采用上述已批准默认值，按真实业务含义替换，不能把同名但含义不同的字段误合并；M5检查消费和残余清单
```

### 4.6 视口与主操作合同

- 支持范围：宽 1280 到 1920，高 ≥ 720；1366×768 与 1280×720 是 M5 的基线尺寸。
- 内容预算：1280 宽下 991px，1366 宽下 1077px。任何固定最小宽超过预算的表格必须走 4.3 表格框并固定关键列与操作列。
- 侧栏：14 项 + 6 组标题总高 ≤ 620px（`--wb-sidebar-item-h` 32px、`--wb-sidebar-group-h` 22px）；最后一项在 720 高度下必须完整可见。
- 每个视图的首屏（不含打开的弹窗）最多一个 `.btn.primary`，且它必须是当前步骤的下一步动作；破坏性动作用 `btn danger`（`--wb-sev-danger`），不与 primary 同时出现在同一工具条。
- 首屏定义：1366×768 下不滚动可见的区域。计划中心三页选中计划后甘特画布首行必须在首屏内。

### 4.7 内部标识与文案协议

- 40 位以上十六进制引用、`request_key`、`*_ref`、规则码（如 `qualification.empty`）不得出现在可见文本中；确需给维护人员留查证入口的，统一放进 `<details class="wb-ref"><summary>编号</summary>…</details>`。M5 用 DOM 断言拦截 `details.wb-ref` 之外的 `/[0-9a-f]{32,}/`。
- 用户可见的错误文案不出现错误码、HTTP 状态码、JSON、异常类名；`request_failed` 一类代码进 `details.wb-ref`。
- 严重度一律四级 ok / notice / warning / danger，取色只用 4.2 的 `--wb-sev-*`，并且同时给徽标文字或圆点，不只靠边框色。

### 4.8 验证协议

```
基线截图（人工评审证据，不入门禁）
  工具：tests/ui_baseline_capture.mjs 适配工作台（等待 #root[data-workbench-boot="ready"]，
        外壳检查改为 .top-header + .sidebar-nav + .hdr-pill）
  矩阵：15 个视图 × {1366×768, 1280×720} × {light, dark}，外加 8 个交互态
        （批次表滚到底、新增批次校验失败、计划中心选中 v14、执行排产选批次、现场展开报工、
          值班台详情、试调新建弹窗、工时校准详情）
  存放：evidence/workbench-ui/<日期>/，PNG 不进仓库门禁，对比结论写进对应 feature 的 acceptance

几何断言（进 daily gate，扩展 tests/ui_geometry_probe_scenarios.mjs）
  G1 批次表 .wb-col-actions 在 1366 首屏可见且 thead 吸顶
  G2 侧栏最后一个 .nav-item 在 720 高度下 bottom <= innerHeight
  G3 计划中心选中当前正式后第一任务行的标签与条形完整位于真实外壳首屏内，且未被遮挡；只露出几像素不通过
  G4 document.documentElement.scrollWidth <= clientWidth（15 视图 × 2 尺寸）
  G5 每视图首屏 .btn.primary 数量 <= 1
  G6 可见文本无 32 位以上十六进制（details.wb-ref 内除外）
  局部检查：重点卡片不相交、标签和关键操作在裁剪容器内可见、固定操作可点击，不能以G4替代
  启用：先采现状；已知失败逐条记录owner/对应条目/移除条件，修复后启用阻断，最终验收无豁免
  接线：新增独立工作台工具并由daily gate显式opt-in运行；旧页面browser smoke继续遵守manual/CI政策

样式测试（进 daily gate，新增 tests/workbench-app-styles.cjs）
  应用 CSS 层无裸 hex/rgb、无半像素 font-size、z-index 只取 --wb-z-*、
  !important 前一行必须有 override 注释

合同测试同步
  改导航：菜单渲染期望从boot.nav_groups派生，但保留独立支持视图/核心入口/旧URL/context断言
  改清单：tests/workbench/test_entry.py、tests/app_runtime/test_validate_dist_static_payload.py、
          tests/web_pages/test_ui_contract_component_tokens.py 允许 workbench/app/styles/ 前缀
  每条 feature 收尾至少跑：受影响 pytest 模块 + 相关 tests/workbench-*.cjs + python scripts/run_daily_quality_gate.py
```

### 4.9 页面标题与上下文行（2026-09-13 第二轮）

- 顶栏 `.top-title` 是页面唯一可见标题。工作区页内与顶栏重复的 `h2` 加 `wb-page-title`（视觉隐藏，保留在 DOM 供结构、region 名称与测试使用），紧随的副标题加 `wb-page-context`（13px 次级色）作为可见上下文行，右侧放页面动作。工艺节点标题、候选子态标题等不与顶栏重复的标题保持可见。
- 工作区根 `.plana` 一律 `padding: 0`，内容左边缘统一为 264px；页面为灰底，表格框、KPI 条、详情面板为白卡。KPI 条统一为“label 上、数值下”的四格条，值班台 KPI 用 flex 换行并伸展避免空洞。
- 甘特滚动框 `height: auto` + `max-height`，处置清单无最小高度；只有一两行时不留空白。

## 5. 子 feature 清单

按依赖与建议推进顺序排列，与 `workbench-ui-refinement-items.yaml` 一一对应。

1. **wbui-css-layer-table-frame** — 建立应用自有 CSS 层并接进构建与清单，以批次表吸顶表头加固定操作列作为首个消费者。
   - 所属模块：M2 + M3（表格框）
   - 依赖：无
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-css-layer-table-frame
   - 备注：验收信号是 1366×768 打开批次管理不横滚即可见"查看/编辑"和删除，滚动时表头不消失；三处清单合同测试同步放开前缀。

2. **wbui-ui-baseline-gate** — 落地 4.8 验证协议：基线截图工具适配工作台、几何断言 G1–G6 进 daily gate、应用 CSS 层样式测试。
   - 所属模块：M5
   - 依赖：无（当前版本基线先于第 1 条采集，门禁按对应修复逐项启用）
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-ui-baseline-gate
   - 备注：G1–G6及局部断言的已知失败都必须绑定修复条目；最终验收不允许预期失败或跳过。

3. **wbui-tokens-states** — 补 z 阶梯与严重度别名令牌、字号整数化（清 121 处半像素）、消息条语义色走令牌并补徽标、未选中单选钮空心样式、`:active` 与表格行 focus 态、三套圆角令牌名收一。
   - 所属模块：M2
   - 依赖：wbui-css-layer-table-frame（规则落在应用 CSS 层）
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-tokens-states
   - 备注：`main.jsx:59-61` 三个硬编码色、`WorkbenchControlStyles.jsx:267-269` 单选、`plana.css` / `basedata.css` / `index.inline.css` 的半像素字号是主要工作量。

4. **wbui-viewport-budget** — 落地 4.6 视口合同：侧栏项高与组标题尺寸、去掉组标题序号字符、1280 断点、主数据总览筛选行裁切与实体卡溢出、值班台 1280 下指标卡与表格溢出、基础资料产能链图 1280 卡片重叠（仅修重叠）。
   - 所属模块：M2 + M4
   - 依赖：wbui-css-layer-table-frame
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-viewport-budget
   - 备注：验收信号是 G2 与 G4 在两种尺寸全部通过。

5. **wbui-nav-boot-groups** — 导航分组由 `pages.py` 下发 `nav_groups` / `view_aliases`，值班台置顶、主数据总览并入数据准备、图标去重；`main.jsx` 改读启动信息；导航合同测试改为派生。
   - 所属模块：M1
   - 依赖：无
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-nav-boot-groups
   - 备注：分组顺序按4.4已批准默认值；视图合并由对应条目负责。

6. **wbui-header-controls** — 顶栏：主题切换改为动作语义（图标加"切换深色/浅色"），补帮助入口（`help_url` 指向接进工作台壳的手册页），显示实例标签，页头标题随子页内容变化（如排产历史）。
   - 所属模块：M1
   - 依赖：无
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-header-controls
   - 备注：复用scheduler_config.py已提供的只读手册URL，保留下载和返回合同，不再新增重复手册路由。

7. **wbui-plan-center-first-screen** — 计划中心三页：进页自动选中当前正式计划，目录默认收起为顶部下拉，甘特首行进首屏；图例补齐绿色、虚线、菱形；条形第一行改批次号；加今日线。
   - 所属模块：M4
   - 依赖：无
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-plan-center-first-screen
   - 备注：G3通过；无当前正式时保留目录展开态。显式计划/恢复上下文优先，读取失败不得改选当前正式。

8. **wbui-detail-panel** — 实现 `WorkbenchDetailPanel` 并接入值班台条目详情、报表与复盘工序详情，主数据总览侧栏改用同一组件；点"详情"后面板在视口内且焦点移入。
   - 所属模块：M3 + M4
   - 依赖：wbui-css-layer-table-frame
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-detail-panel
   - 备注：值班台详情里的"完整来源依据" JSON 转为结构化字段表，随本条一起去掉。

9. **wbui-run-stepper** — 执行排产页改为"选批次与窗口、检查、计算"三步条，主按钮跟随当前步骤；候选页只保留"采用方案"为实心；排产阶段用 `data-run-stage` 翻成中文阶段加已耗时；预检参数变更后提示重检；批次选择器补交期与优先级列。
   - 所属模块：M4
   - 依赖：无
   - 状态：done
   - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
   - 对应 feature：2026-09-12-wbui-run-stepper
   - 备注：不做排产取消（需要运行时支持，见明确不做）。

10. **wbui-actual-gantt-window** — 现场实际甘特默认窗口对齐计划区间或最近报工区间，条形最小宽 4px，放大以选中项或数据中心为锚，"适应全部"覆盖计划基线。
    - 所属模块：M4
    - 依赖：无
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-actual-gantt-window
    - 备注：服务端axis_span覆盖计划/实报/剩余安排/as_of，保持该语义，仅调整前端显示窗口与命中区域，点工序不变持续条。

11. **wbui-field-validation** — 抽出 `ResourceControls.Field`，批次、外协、日历、报工表单统一字段级校验，提交失败聚焦首个错误字段，去掉 ErrorBox 与 Issues 的重复渲染；新增批次三必填全部即时标记。
    - 所属模块：M3 + M4
    - 依赖：无
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-field-validation
    - 备注：`ResourceControls.jsx:32,36` 重复消息、`BatchForms.jsx` 与 `BatchControls.jsx:10-13` 弱化版 Field 是起点。

12. **wbui-field-report-fastpath** — 报工新建编辑器提供可清除的时间建议（同任务同工序上一有效报工结束或当前时间）、加"保存并继续"和"复制上一条"；补齐/更正/保留草稿不覆盖。
    - 所属模块：M4
    - 依赖：wbui-field-validation、wbui-dirty-guard
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-field-report-fastpath
    - 备注：建议值明确提示且可清除，不猜实际事实；仅确认原回执成功且重读新write_context后可继续，新草稿不复用引用/版本/请求键。

13. **wbui-empty-loading-pager** — 实现 `EmptyState` 与 `Pager`，接入全部列表页，区分无数据与筛选无结果，统一每页档位与量词。
    - 所属模块：M3 + M4
    - 依赖：wbui-css-layer-table-frame
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-empty-loading-pager
    - 备注：替换 8 处独立 Pager 与 14 个 `*-empty` 类。

14. **wbui-format-module** — 实现 `WorkbenchFormat`，替换 50 处内联 `replace('T',' ')`、8 份千分位定义与 2 处裸浮点，修 `ProcessStageEditor.jsx:8-14` 的时区偏移与 `SystemLive.jsx:103` 的斜杠日期。
    - 所属模块：M3
    - 依赖：无
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-format-module
    - 备注：利用率统一为百分数。

15. **wbui-terms-and-ids** — 落地 `WorkbenchTerms` 术语表并替换全部字面量；内部引用、请求键、规则码收进 `details.wb-ref`；契约词（身份条目、段、持久候选、协议、快照、原 key）改为计划员能行动的说法。
    - 所属模块：M3 + M4
    - 依赖：wbui-format-module
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-terms-and-ids
    - 备注：按已批准默认术语表实施；验收信号是G6通过且不同业务含义未被误合并。

16. **wbui-table-density-noise** — 表头筛选/排序图标按 4.3 规则收敛，表头文字改中性色，加全局紧凑密度偏好（`localStorage` 键 `aps_density`，值 `comfortable | compact`），报表与复盘在无现场数据时用一条横幅代替逐格"未知"，现场记录去掉与筛选片重复的统计条。
    - 所属模块：M4
    - 依赖：wbui-css-layer-table-frame
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-table-density-noise
    - 备注：密度只改行高与内边距，不改字号。

17. **wbui-dirty-guard** — 实现 `WorkbenchGuards`，`main.jsx` 的 `navigate` 与共享 `Modal` 的 Esc/遮罩在有未保存草稿时二次确认；接入试调编辑器、批次表单、工艺编辑器、报工编辑器。
    - 所属模块：M3 + M4
    - 依赖：无
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-dirty-guard
    - 备注：确认框复用共享 Modal，不用原生 confirm。

18. **wbui-a11y-sweep** — 表格补 caption 与 scope，`Button` 加 `reasonDisplay: 'inline'` 并在禁用按钮处启用，候选甘特虚拟列表表头去掉 `aria-hidden`，`aria-label` 里的哈希换业务描述，Canvas 键盘可遍历全部色块。
    - 所属模块：M3 + M4
    - 依赖：无
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-a11y-sweep
    - 备注：与第 15 条有交集，先做哪条都行，后做的只补差。

19. **wbui-system-page-polish** — 系统管理"页面环境自检"收进折叠区，"导出当前诊断 JSON"改为"导出诊断文件"，维护恢复页去掉裸错误码、补回工作台入口，读取状态失败时文案改为"无法读取维护状态"而非"系统已暂停"。
    - 所属模块：M4
    - 依赖：无
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-system-page-polish
    - 备注：不改恢复流程的保守语义，只改呈现。

20. **wbui-view-tabs-merge** — 报表中心与执行复盘、选择排产方案与甘特/交付风险各合并为一个入口加页内页签；旧 `?view=` 值保持有效并映射到对应页签；侧栏减到 12 项。
    - 所属模块：M1 + M4
    - 依赖：wbui-nav-boot-groups
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-view-tabs-merge
    - 备注：用户已批准该方向；菜单12项与15视图可达性分开验证，报表页签复用本域go()保留范围与返回上下文。

21. **wbui-prototype-css-cleanup** — 先量再删：用真实渲染统计原型 CSS 选择器命中率，删除不再渲染的原型样式与相应 `!important`，断点归一为 1280 / 1366 / 1600，剩余 `*Styles.jsx` 全部迁入应用 CSS 层。
    - 所属模块：M2
    - 依赖：wbui-tokens-states、wbui-viewport-budget
    - 状态：done
    - 最终证据：见 acceptance-20260912.md 第 3 节与 evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json：e696 构建 60 页面 / 8 交互 / 4 密度矩阵与 daily gate 通过；完整门禁 16491 passed / 1 failed，唯一失败为 KB 显示旧预期，已修正并单模块复测通过；用户决定不再重跑完整门禁，此项不构成全仓全绿证明
    - 对应 feature：2026-09-12-wbui-prototype-css-cleanup
    - 备注：涉及 `前端设计/` 导入快照，按 4.1 的原型层修改流程走；建议最后做。

**最小闭环**：第 1 条 `wbui-css-layer-table-frame` 做完后，1366×768 打开批次管理即可不横滚看到并点击操作列，表头随滚动吸顶；同时应用 CSS 层已接进构建与清单，后续条目有了落样式的地方。

## 6. 排期思路

按"先固定基线与共同合同，再按文件所有权并行开发，最后统一构建验收"执行；依赖约束集成和验收，不阻止基于已批准合同并行开发：

- 第一波（1–4 条）：CSS 层、基线与几何断言、令牌与交互态、视口预算。它们改的是所有页面共用的地基，做完后每条页面改动都有落点、有回归证据。
- 第二波（5–12 条）：导航与顶栏、计划中心首屏、详情面板、执行排产步骤条、现场甘特窗口、字段校验、报工快路径。这是计划员每天最常走的路径，收益最直接。
- 第三波（13–21 条）：空态与分页、格式化与术语、密度与降噪、脏草稿守卫、无障碍、系统页、视图合并、原型清理。多为一致性收口，其中第 20 条视图合并和第 15 条术语表已获用户批准。

卡点：第1条改构建与清单，第2条新增显式几何验收接线，第5条改启动信息与导航合同，第21条依赖导入快照流程。草稿守卫应在报工快捷流程集成前就位；原型清理在工作区改造完成后执行。迁移历史证据保留原绑定，本次UI冻结后重新生成受影响浏览器证据，不以等待旧验收来替代新版本验证。

## 7. 观察项

- `aps-frontend-fusion`（13 条 planned）和 `aps-frontend-workbench`（4 条 planned）两份 roadmap 针对的是已退役的旧界面，建议另行 update 标 paused 或 dropped。
- 13 个根目录 `tests/*.cjs` 样式测试 require 的是被 git 忽略的 `前端设计/ui_kits/workbench/tests/*.cjs`，原型层源头也是忽略目录；换机器或他人协作时这些测试跑不起来。建议走 `cs-decide` 决定是否把这些测试助手收进 `tests/_support/`。
- `前端设计/readme.md` 写的圆角规范是 4/6/8 默认 6，代码是 2026-09-07 直角化决定后的 0/4/8。建议改文档不改代码。
- 开发库 `db/aps.db`（6 月）迁到 v31 时被 `OperationExecutionEvents` 约束前置检查挡住，与界面无关，建议单独起 issue。
- 顶栏实测高 64px，令牌 `--header-height` 是 60px；第 3 或第 4 条落地时需二者对齐，否则吸顶偏移错 4px。
- 样式审查子代理估算原型 CSS 约八成已不渲染，方向可信、数字未复核；第 21 条先量再删。
- 导入"只导正确行"、排产取消、外协登记入口、全局搜索都是能力边界问题，需要先走 `cs-req`，本路线图不承接。
- 基础资料与主数据总览两个入口指向同一批数据，本路线图只把它们放进同一组，是否合并属产品决定。

## 8. 变更日志

- 2026-09-12：new 模式创建，基于同日界面审查；`review_status: draft`，待用户 review 后转 approved。
- 2026-09-12：用户批准按审查意见并行实施；修订分页、时间、草稿退出、表格滚动、几何门禁、导航独立断言和迁移证据绑定合同，review_status转approved；执行记录见implementation-20260912.md。
- 2026-09-12：21项实现与文档收尾；e696最终矩阵、每日门禁及唯一失败的定向复测通过。按用户明确要求停止完整门禁重跑，保留原全量1项失败和后续测试修正证据，status转completed、completion_scope记completed-with-validation-limit；未提交、未发布。
- 2026-09-13：五路对抗复审后修复 7 项（格式精度退化与报工丢秒、守卫 locked 混入 UI 忙碌态、报表/复盘页签切换丢范围、帮助入口丢上下文、报工保存提示常驻、值班台业务字段被折叠、排产历史下页签条自相矛盾），同步修订 4.4 help_url 与 4.5 number/hours/percent、WorkbenchGuards 合同文本；记录见 `../../issues/2026-09-13-wbui-review-fixes/wbui-review-fixes-fix-note.md`。
- 2026-09-13：整体样式复审后第二轮整改（固定列滚动阴影、表头 keep-all、单一页面标题与上下文行、容器与 KPI 统一、甘特自适应高度、原因文字 tooltip、Issues 合并、链接蓝收敛、间距/行高/圆角令牌接线），新增 4.9 并修订 4.2/4.3/4.5 合同文本；items 追加 5 条 wbui-r2-*（1 条 dropped）；记录见 `../../features/2026-09-13-wbui-style-round2/wbui-style-round2-implementation.md`。
- 2026-09-13：`tests/workbench` 全目录长跑（8376 passed / 9 failed）并在干净 HEAD worktree 复跑 8 例做基线归因：回退复审修复第 3 项（页签切换叠加当前范围，实为既有整体恢复设计）；3 处未提交测试期望改回 HEAD 语义（工时 trim、时间带秒）；现场甘特滚动步骤加"页面能滚才滚"守卫；维护存储故障断言改为维护屏稳定态；共享控件探针旧 `title` 模式改为 `tooltip`。记录见 round2 实施记录"补记"。
