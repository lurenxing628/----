# 2026-05-21 前端 UI 布局风险核对记录

## 核对结论总览

- 本次只做核对，不改源码。
- 已按用户要求调用 8 个 Sub Agent 分组读代码；主代理负责在可见浏览器里打开页面、观察真实布局。
- 核对对象是用户提供的“前端 UI 布局审计的问题/风险清单中文版”。
- 浏览器和临时服务均保持运行，未关闭。

## 环境

- 仓库：`/Users/lurenxing/Documents/GitHub/----`
- 当前页面基准：`http://127.0.0.1:61661/process/`
- 临时压测环境：`/tmp/aps-networkx-full-browser-stress.h88s1vh4`
- 当前浏览器宽度约：`1160px`
- 截图证据：
  - `/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/ui-layout-materials-1160.png`
  - `/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/ui-layout-resource-dispatch-1160.png`
  - `/tmp/aps-networkx-full-browser-stress.h88s1vh4/browser-artifacts/screenshots/ui-layout-gantt-controls-1160.png`

## Sub Agent 分工

- Excel 演示页、Excel 操作卡片、Excel 上传字段。
- 全局固定布局表格、表格拖宽持久化、截断工具类。
- 物料主数据、批次物料、最小宽度工具类。
- 排产操作面板、批次管理批量操作、空状态排产面板。
- 资源派工详情、班组任务表、资源派工甘特容器。
- 甘特图区间查询、筛选勾选项、顶部控制行。
- 浮动说明书按钮、主导航、Flash 消息、日历、系统日志、遗留工具类。
- 测试环境、pytest / jinja2 / 布局契约脚本。

## 状态说明

- `属实`：代码证据能直接确认，或当前浏览器已经看到对应现象。
- `部分属实`：代码里确实有这个风险点，但被其他规则抵消、当前页面没有复现，或只能说明“可能发生”。
- `不属实`：本轮用当前代码和命令没有复现，和清单描述不一致。
- `仍需验证`：需要更窄视口、Chrome 109、长文案、长数据或特殊状态才能判断最终视觉效果。

## 问题清单核对

| 优先级 | 页面/组件 | 核对状态 | 结论 |
|---|---|---|---|
| P1 | Excel 演示页当前人员表格 | 属实 | `templates/excel/demo.html:10` 直接使用普通 `<table>`，没有 `.aps-table-scroll`，没有 `table-layout-fixed`，也没有 `data-col-resize="1"`。当前 1160px 浏览器下没有立刻撑出卡片，但长姓名、长备注仍有真实风险。 |
| P1 | 全局固定布局表格 | 部分属实 | `.aps-table--fixed` / `.table-layout-fixed` 的隐藏、省略、单行机制属实，见 `static/css/ui_contract.css:1623`、`:1628`。但 `.aps-table--multiline` 会改回可换行，不能说所有固定表格都会隐藏重要文本。 |
| P1 | 物料主数据可编辑表格 | 属实 | `templates/material/materials.html:71` 使用固定布局宽表，内部有 `w-160`、`w-140`、`w-120`、`w-220` 输入框。浏览器确认表格宽约 1321px、容器约 806px，依赖横向滚动。 |
| P1 | 资源派工详情/班组任务表 | 属实 | 多张表使用 `aps-table-xwide`，`current_resource` 和 `resource` 为 220px。浏览器确认 `#rdDetailTable` 宽约 1681px、容器约 798px，横向滚动明确存在。 |
| P1 | 表格列宽拖拽持久化 | 属实 | `static/js/table_resize.js` 使用 `aps_table_colwidth:v1:` 保存列宽，并按列宽总和写入表格 `min-width`。多次拖宽后可能让表格在宽屏下也出现额外横向滚动，但是否出现取决于用户保存的列宽总和。 |
| P2 | Excel 操作卡片按钮区 | 属实 | `.aps-excel-card-actions` 是固定两列，按钮 `white-space: nowrap`。当前 `/process/` 页面 1160px 下没有溢出，但窄卡片或更长按钮文案时风险成立。 |
| P2 | 排产操作面板选中数量状态 | 属实 | `_run_panel.html:7` 使用 `.aps-run-panel-status`，CSS 有 `margin-left: auto` 和 `white-space: nowrap`。当前 1160px 页面没挤压，窄宽度仍需看。 |
| P2 | 批次管理批量操作状态 | 部分属实 | 三个批量按钮和“已选 N 个批次”确实在同一操作区，但外层 `.aps-action-card-actions` 允许换行，所以只能确认有拥挤风险，不能确认一定会溢出。 |
| P2 | 无待排批次时的排产操作面板 | 属实 | `templates/scheduler/batches.html:175-187` 空状态仍显示状态文本和多个按钮式控件，状态文本不换行。实际视觉是否失衡需要空数据状态再看。 |
| P2 | 响应式表单中的最小宽度工具类 | 部分属实 | `.min-w-320/.min-w-360/.min-w-420` 确实存在，但在 `.aps-query-form-grid` 内会被更具体的 `.form-field { min-width: 0; }` 抵消。不能直接判定当前页面必然溢出。 |
| P2 | 批次物料选择字段 | 部分属实 | 模板里外层 `min-w-320`、内部 `w-280` 属实；浏览器当前看到 computed `min-width` 被表单网格压成 0，select 能按容器伸缩。 |
| P2 | Excel 上传文件字段 | 部分属实 | `excel_import.html:72` 的文件字段有 `min-w-320` 属实；但它位于查询表单网格里，当前代码会把字段最小宽度压回 0。Chrome 109 窄屏仍需验证。 |
| P2 | 遗留 `.aps-filter-bar` | 部分属实 | CSS 里仍有 `.aps-filter-bar`，但当前重点模板没有活跃使用，测试还在阻止继续使用它。所以这是后续复用风险，不是当前页面已发生问题。 |
| P2 | 工具栏 nowrap 类 | 部分属实 | `.toolbar-actions-inline`、`.toolbar-actions-nowrap` 存在，但全仓未发现活跃模板/JS 使用。属于后续误用风险。 |
| P2 | 甘特图区间查询表单 | 属实 | `aps_gantt.css:223` 桌面端是四列字段加自动按钮列，980px 和 560px 有断点。当前 1160px 下列宽约 161.5px、按钮 88px，没有溢出；临界宽度仍需看。 |
| P2 | 甘特图筛选勾选项 | 属实 | `aps_gantt.css:540-543` 在 900px 以上给 `.aps-gantt-filter-checks` 设置 `min-width: 320px`。当前页面实际宽度为 320px。 |
| P2 | 甘特图顶部控制行 | 属实 | `.aps-gantt-control-row` 基础规则确实是 `width: fit-content; max-width: 100%`。当前 1160px 下控制行宽约 431px，靠左成组但未溢出。 |
| P2 | 资源派工甘特图容器内联样式 | 属实 | `templates/scheduler/resource_dispatch.html:265-267` 的 `#rdGantt` 写了内联 `style="min-height: 360px;"`。当前浏览器状态下该容器隐藏，空状态和加载后状态还需要再看。 |
| P2 | “浮动”说明书按钮 | 属实 | `base.html:102` 在 `.container` 之后渲染 `floating_manual_button()`，wrapper 是 `position: relative`，不是 fixed。浏览器里它参与正常文档流。 |
| P2 | 主导航换行 | 属实 | `base.css` 里 `nav` 允许换行，`nav a` 不换行。当前布局使用侧边导航，当前 1160px 没看到顶部导航挤压；旧顶栏或窄屏仍需看。 |
| P2 | Flash 消息关闭按钮垂直居中 | 部分属实 | `.flash-close` 绝对定位 `top: 50%` 属实。是否在多行消息里显得不齐，需要制造长 Flash 消息验证。 |
| P3 | 日历日期选择器最小宽度 | 属实 | `.aps-calendar-date-field` 有 `min-width: 260px`，内部日期输入区域使用 `minmax(180px, 1fr) auto`。桌面一般可接受，紧凑表单仍有压迫风险。 |
| P3 | 系统日志清理按钮 | 部分属实 | `.aps-settings-cleanup-actions .btn` 确实不换行；当前按钮文案短，浏览器下没有溢出。后续文案变长才更容易出问题。 |
| P3 | 截断工具类 | 部分属实 | `.truncate-cell`、`.truncate-cell-150` 定义属实，但当前未发现模板/JS 活跃使用。风险存在，但不是当前页面已确认问题。 |
| P3 | 全局 nowrap 模式累积风险 | 部分属实 | 多个通用类确实在叠加不换行行为；当前只能确认这是系统性风险，需要具体页面和真实数据确认是否已经影响使用。 |

## 测试环境风险核对

| 优先级 | 范围 | 核对状态 | 结论 |
|---|---|---|---|
| P1 | 浏览器几何布局验证缺 pytest | 部分属实 | 默认 `python -m pytest --version` 确实报 `No module named pytest`，但直接 `pytest --version` 可用，指向 Python 3.8 的 pytest 8.3.5。问题更像“默认 python 指错环境”，不是机器完全没有 pytest。 |
| P1 | Jinja 渲染检查缺 jinja2 | 部分属实 | 默认 `python` 直接跑脚本会报 `No module named 'jinja2'`；但 `.venv/bin/python` 和 `/usr/local/bin/python3.8` 都能导入 `jinja2 3.1.6`。用 pytest 跑对应测试通过。 |
| P2 | 排产入口布局契约测试漂移 | 不属实 | 本轮没有复现 `ValueError: substring not found`。默认 python、`.venv/bin/python`、pytest 跑 `tests/regression_scheduler_run_entry_layout_contract.py` 均通过。 |
| P2 | 静态布局契约检查 | 部分属实 | 多个静态布局脚本存在，抽样运行通过；但没有本轮全量跑完所有脚本，也没有把 `regression_ui_browser_geometry_smoke.py` 真正跑成通过，只做了收集。 |

## 主浏览器抽查记录

- `/excel-demo/`
  - 看到 1 张裸 `<table>`，没有 `.aps-table-scroll`。
  - 当前数据和 1160px 宽度下没有马上撑出卡片。
- `/process/`
  - Excel 操作卡片为两列按钮布局，按钮不换行。
  - 当前宽度下未看到按钮文字溢出。
- `/material/materials`
  - 物料表横向滚动存在，输入框固定宽度存在。
  - 没有整页横向溢出，因为滚动被表格容器接住。
- `/material/batches`
  - `min-w-320` 在表单网格内被计算为 0。
  - 当前宽度下选择框未撑破容器。
- `/scheduler/`
  - 排产面板状态文本不换行属实。
  - 当前宽度下未挤压标题。
- `/scheduler/batches`
  - 批量操作状态和按钮同区属实。
  - 当前宽度下没有立刻溢出。
- `/scheduler/resource-dispatch?version=15&scope_type=machine&period_preset=custom&start_date=2026-05-04&end_date=2026-05-11`
  - 资源派工详情表宽约 1681px，容器约 798px，横向滚动明显。
- `/scheduler/gantt?view=machine&version=15`
  - 区间查询表单列宽、筛选列 320px、顶部控制行靠左成组都和清单描述一致。
  - 当前宽度下未出现控件重叠。
- `/system/logs`
  - 日志表宽约 1515px，容器约 798px，横向滚动存在。
  - 当前短按钮文案未溢出。

## 暂不应夸大的点

- 不应把所有 `.table-layout-fixed` 表格都直接说成“必然隐藏重要信息”，因为 `.aps-table--multiline` 有明确换行例外。
- 不应把所有 `min-w-320` 都说成“必然撑破窄屏”，因为查询表单网格会把 `.form-field` 的最小宽度压回 0。
- 不应把 `pytest/jinja2` 描述成“项目环境缺依赖”，更准确说法是默认 `python` 指向的解释器不对；项目可用解释器和 pytest 命令本身能跑。
- 不应把 `regression_scheduler_run_entry_layout_contract.py` 的 `ValueError` 继续当成当前事实，本轮没有复现。

## 后续仍需真实验证的场景

- 320px、375px、768px、900px、980px、1024px 这些关键宽度。
- Chrome 109 / Win7 目标环境里的 file input、日期选择器、甘特图和横向滚动。
- 真实长姓名、长备注、长供应商名、长工艺路线、长错误信息、长日志消息。
- 用户拖宽表格列之后刷新页面，确认 localStorage 里的列宽是否让宽屏也出现额外横向滚动。
- 多行 Flash 消息，确认关闭按钮是否影响阅读。

