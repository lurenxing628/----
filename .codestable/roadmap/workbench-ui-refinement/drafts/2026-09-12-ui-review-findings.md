# 2026-09-12 新工作台界面审查：发现清单与证据

本文件是 `workbench-ui-refinement` 路线图的素材，只记录审查当天核实的现象与出处，不是修复记录。

## 审查方式

- 数据：`backups/aps_backup_20260527_082854_before_migrate_v14_to_v15.db` 拷贝到 `/tmp` 后由当前代码迁移到 v31（22 批次、168 排程行、3 设备、3 人员）。6 月的 `db/aps.db` 副本被 `OperationExecutionEvents` 约束前置检查挡住，未使用。
- 服务器：`web.bootstrap.entrypoint.create_app_with_mode("new_ui")` 隔离实例，日志与备份目录均指向 `/tmp`；系统管理页另用 `tests/workbench/run_live_server.py --profile mixed` 起带完整运行时的实例核对。
- 浏览器：本机 Chrome 152 headless，通过 CDP（复用 `tests/ui_geometry_cdp_client.mjs`）截图并抓 DOM 事实；15 个视图 × 1366×768，另有 1280×720、1920×1080 与深色样本，20 余个交互步骤，共 69 张 PNG，当时存放在 `/tmp/aps-ui-review/shots*/`（临时目录，不入库）。
- 字体：mac 上回退为苹方，目标机为微软雅黑，字形观感不同但 px 尺寸一致。
- 子代理：样式系统、A 组工作区（排产与分析链）、B 组工作区（主数据、批次、现场、系统）、跨页一致性各一路。

## 已核实的现象（按模块）

### 外壳与导航

- 侧栏 14 项实际对应 11 个组件：analysis / gantt / delay 共用 `PlanCenterWorkspace`（`main.jsx:144`），reports / review 共用 `ReportWorkspace`。`delay` 有标题有 URL 无侧栏入口，高亮被拽回 analysis（`main.jsx:39`）。
- 导航常量在原型 `frontend/workbench/prototype/ui_kits/workbench/AppShell.jsx:25`，打进 `static/workbench/assets/foundation-*.js`；`VIEW_TITLES`（`pages.py:43`）、`enabled_views`（`pages.py:77`）、测试 `DESTINATIONS`（`tests/web_pages/test_workbench_nav_entry_contract.py:25`）共四份清单。
- 侧栏在 768 高度下导航内容 739px、可视 708px，"系统管理"底边 783px 被截；720 高度下"主数据总览""系统管理"不可见。项高 36px、组标题 11px 见 `plana.css:42-44`。
- 顶栏 `main.jsx:55` 的"深色：关"是状态文案，点击后开启深色；无帮助入口，`templates/workbench/manual.html` 只由 `web/routes/domains/scheduler/scheduler_config.py:272` 渲染；`instance_label` 只被 `SystemLive.jsx` 消费。
- 点"排产记录"后页头标题为"选择排产方案"，内容是"排产历史"。

### 视口与溢出

- 批次表：容器 1078px、表 1289px，操作列（查看/编辑、删除）整列在滚动区外，横向滚动条位于 1383px 高的表底；`thead` 为 static。`batch-workbench.css:55` min-width 1100px，`:122` 工序表 1320px。
- 1280 宽：基础资料产能链图卡片互相重叠；主数据总览筛选行"数据域"被裁成"据域"、8 个实体卡溢出、表格 898px 超出 660px 容器；值班台指标卡与表格被裁（`dy-scroll` 720 > 664）。
- 主数据总览在 1366 宽同样裁切（`wb-table-shell` 898 > 746）。

### 计划中心与甘特

- analysis / gantt / delay 进页先显示"历史版本"目录与四个指标，已有"当前正式 v14"却需手选；选中后甘特首行仍在首屏外（目录约 250px、工具条 45px、页头 60px）。目录收起按钮已存在（`PlanCatalogUI.jsx:29`）。
- 目录单选未选中态被画成实心蓝，与选中态一样：`WorkbenchControlStyles.jsx:267-269` 只定义 checked 的白底内点；试调"从原来源创建"弹窗同样，且下方写"尚未选择"。
- 甘特条第一行为"共同工序"（`PlanGanttModel.js:9`），批次号在第二行被截；图例只有蓝红两项，实际出现绿色条；无今日线。
- 现场实际甘特默认刻度 30 天，1.7 小时工序条宽 0.45px；"适应全部"不改刻度，放大 6 次后窗口落在 7 月而数据在 5 月；轴范围来自 `ActualGanttModel.js:111` 的 `axis_span`。

### 详情与反馈

- 值班台点"详情"，`dy-detail`（`DashboardPanels.jsx:82`）追加在 2313px 处，视口外，焦点留在 body；执行复盘详情同样落在 714px 处且不滚动。
- 值班台详情直接显示 48 位"正式计划引用 / 批次引用"（`DashboardPanels.jsx:75`），"完整来源依据"为 JSON dump（`:80`），计划完成显示原始 ISO `2026-05-18T12:42:00`。
- 工时校准的工艺详情表格显示 48 位哈希（`ProcessDetail.jsx:19`）；主数据总览显示规则码 `qualification.empty`（`MasterOverviewDetail.jsx:22-23`）。
- 执行排产页"开始排产检查"是幽灵按钮且在首屏外，"核对并开始排产"是实心但禁用；候选页一排 7 个同重量按钮，"采用方案"不是 primary（`RunCandidateWorkspace.jsx:109-116`）。
- 新增批次空表单提交只报"数量必须是正整数"且重复两遍（`ResourceControls.jsx:32,36` 两个组件渲染同一消息），批次号与图号为空不报；8 个字段无 required / aria-invalid。
- 排产计算无进度与已耗时，只有"正在计算"；成功提示均为页内 status，顶部消息条只接服务端消息。
- 脏草稿无跨页保护：`TrialWorkspace.jsx:76` 的 guard 只挡页内按钮，`main.jsx:114` 的 navigate 与关窗不挡；`ProcessDetail.jsx:66` 有 beforeunload 可复制。
- 报工编辑器 `FieldEditor.jsx:57` 两个 datetime-local 初值为空（`FieldContract.js:55-57`），无"保存并继续"与"复制上一条"，保存后需手点重读（`FieldControls.jsx:28`）。

### 样式系统

- 应用层 38 个 JSX 含 `<style>`，全在 body 内，同特异度必胜静态 CSS；实例：`field-gantt.css:52` 的图标按钮 hover 被 `ActualGanttControls.jsx:24` 盖掉。`@keyframes apsdp-pop` 在 `aps-datepicker.css:82` 与 `field-reporting.css:151` 重复定义。
- 令牌之外裸 hex：`gantt-theme.css` 60、`plana.css` 24、`basedata.css` 16、`datepicker/aps-datepicker.css` 10；`main.jsx:59-61` 消息条用 `#dc3545 / #b77900 / #15803d`，且严重度只靠左边框单通道。
- 半像素字号 121 处（12.5 / 13.5 / 11.5 / 10.5），集中在 `plana.css` 51、`basedata.css` 35、`index.inline.css` 24。低于 12px：组标题 11px、值班台指标副文案 10.83px、现场甘特刻度 10px。
- `!important` 397 处，`workbench-ui.css` 132 + `WorkbenchControlStyles.jsx` 81；≤640px 的 44px 触摸目标规则被 8 条页面级 32/36px 规则压掉。
- 断点 23 个不同值，无 1366 处理，1280 仅 2 处；z-index 0 到 12000 无阶梯，值班台 tooltip 1800 低于 10000 弹窗。
- 设计令牌 `--space-*`、`--font-size-*`、`--radius-*` 等消费者为 0；应用自建 `--wb-*`；`--wb-radius-surface: 0px` 与 `前端设计/readme.md` 的默认 6px 冲突（代码为 2026-09-07 直角化决定）。
- 深色：6 个 `*Styles.jsx` 纯令牌无硬编码；缺口在原型静态表，其中 `basedata.css:429-430` 的未定义令牌 fallback 属死样式（`.bd-matrix` 在应用层零引用）。
- 被推翻的一条：原型 `apsdp` 日期弹层 z 4000 低于 10000 弹窗，但 React 工作台用的是 `WorkbenchDatePicker`（浮层 12000，`WorkbenchControlStyles.jsx:328`），不受影响。

### 一致性与文案

- `overdue_count` 四个中文名（超期批次 / 预计晚交批数 / 已核实预计超期 / 预计晚交批次），`delay_hours` 五个，含 CSV 表头 `TrialExport.js:7`。"候选"五种叫法；"排程"3 处对"排产"95 处；"清除 / 清空"、"新增 / 创建 / 新建"混用。
- 日期无共享格式化：50 处 `replace('T',' ')`，`ProcessStageEditor.jsx:8-14` 经 `new Date()` 叠加时区，`SystemLive.jsx:103` 用 `toLocaleString` 斜杠格式；千分位 8 份定义；利用率 `RunCandidateModel.js:10` 显示 0.873 而 `DashboardPanels.jsx:104` 显示 87.3%。
- 表格 15 个家族、状态药丸 14 个家族、分页器 8 份、`useRead` 重定义 8 次；`wb-page-panel` 页壳仅 `main.jsx:154` 占位符使用。
- 契约词上界面："身份条目""段""持久候选""协议""快照""原 key"；`ResourceForms.jsx:10` "服务器已确认提交"与单机定位冲突。
- 表格 0 caption、0 scope；`RunCandidateGantt.jsx:64` 表头 aria-hidden；`aria-label` 含 48 位 ref（`RunHistoryControls.jsx:57,62`）；禁用原因只在 title（`ResourceControls.jsx:21-27`）。

### 做得好的（保持）

- 圆角全站 4px 一致，主字号 13px，焦点环 2px 蓝色清晰，深色主要页面正常，Chrome 109 不支持的语法零命中。
- 零原生 `confirm / alert`，共享 `Modal` 有焦点陷阱、Esc、还原与滚动锁；下拉与日期选择器键盘完整；`navigator.locks` 防重复提交；读取失败明确不替换旧数据。
- `tabular-nums` 137 处，数字等宽原则基本落实；`gantt-theme.css`、`plana.css` 的 `--kit-*` 浅暗成对无遗漏。

## 用户已裁定

- 基础资料首屏产能链图重排：不做（2026-09-12）。
