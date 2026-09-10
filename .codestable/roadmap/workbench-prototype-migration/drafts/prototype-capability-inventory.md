---
doc_type: explore
type: module-overview
status: draft
created: 2026-09-09
scope: prototype-capability-inventory-only
evidence: current-worktree-source
backend_verified: false
browser_verified: false
---

# Workbench 样板能力清单

## 1. 结论与使用方法

- 当前入口确实是 **14 个 index 路由（含无侧栏项的 delay）+ 独立 trial**，不是 README 里的旧页面划分。已按实际挂载链清点，不只列菜单。
- 样板不是一套已连通业务数据库的前端。存在纯界面交互、会话内存写入、仅 DOM 增删、localStorage 方案保存、真实浏览器文件处理、仅提示成功以及明确禁用等不同实现程度。
- **所有可见的业务入口都属于迁移候选，禁用/占位不等于删除或免做。** 下表“后端需要”是待落实的契约需求，不表示已找到对应接口，也不授权实施。
- 关键接入断点：基础资料与批次模板并非同一内存源；值班台、排产检查、方案工作区、现场记录的批次/时间/资源也不统一；“开始排产检查”不运行引擎；归属分拣只提交阶段状态；系统真实备份/恢复/日志/配置未接入。
- “样式/交互完全一致”应锁定当前可达界面的布局、控件、状态与跳转，不能把示例数据、假成功、错误的业务推断当成必须复制的业务合同。需决策的差异单列于第 19 节。

**证据口径**：2026-09-09（本机 Asia/Shanghai）当前脏工作区源码，只读调查。未启动后端、未访问真实数据库、未跑浏览器、未执行原型测试或生成器。源码静态证明“有怎样的实现/分支”，不证明实际点击、布局像素或真实后端已通过。

**路径约定**：下表短路径均相对 `/Users/lurenxing/GitHub/----/前端设计/ui_kits/workbench/`；跨目录证据写仓库相对全路径。`文件:行号` 为当前源码锚点，同行或附近包含字段生成/事件分支。后续源码改动后需刷新行号，不更换能力 ID。

**稳定 ID**：`WBP-域-编号` 表示能力族；同一行逐一列出共享合同的字段/子动作。后续拆分用 `.a/.b` 等后缀，不重排已有编号。本文不按样例行数重复计能力，也不把颜色/图标本身当成单独业务能力。

| 现状码 | 含义 | 不能由此推出什么 |
|---|---|---|
| UI | 原型可交互，改变视图/选择/焦点/筛选 | 不等于业务写入 |
| MEM | 实际读写页面/模块会话内存 | 不等于持久化；刷新或组件重建可能丢失 |
| DOM | 仅当前 DOM 表格增删或标记 | 不等于源数组已更新 |
| LS | 实际读写 localStorage | 不等于正式采用计划或服务端事务 |
| FILE | 实际选择、解析或发起下载文件 | 不等于生产数据导入；发起下载不保证用户已保存 |
| SHOW | 固定样例/派生只读展示 | 不等于来自生产数据的结论 |
| STUB | 纯占位、无业务处理器或只弹提示 | 需落实业务，而不是保留假成功 |
| OFF | 明确禁用/锁定/不提供当前动作 | 按禁用原因落实能力和守卫，不得直接排除 |

下面所有行的“后端需要”均为**待核对/待接入**；“无新增业务写入”只表示该 UI 动作本身不应写业务数据。

## 2. 入口、挂载与数据源

| 入口 | 实际挂载链 | 清单域 | 源码证据 |
|---|---|---|---|
| `index.html?view=dashboard` | DashboardScreen -> APSDashboard.mount | DASH | `app.jsx:87`; `DashboardScreen.jsx:1` |
| `?view=process` | ProcessNative -> APSPlanAInit，非 BaseDataScreen | PROC | `app.jsx:96`; `ProcessNative.jsx:6` |
| `?view=batches` | BatchesScreen -> 列表/详情/弹窗 | BATCH | `app.jsx:95`; `BaseBatches.jsx:148` |
| `?view=run` | GanttScreen(mode=run) -> PreflightCheck | RUN | `app.jsx:89`; `GanttScreen.jsx:2` |
| `?view=analysis` | AnalysisScreen -> PlanShared + APSTrialViews | ANA / PLAN | `app.jsx:90`; `AnalysisScreen.jsx:1` |
| `?view=gantt` | GanttScreen(mode=gantt) -> GanttBoard | GANTT / PLAN | `app.jsx:88`; `GanttScreen.jsx:33` |
| `?view=delay` | DelayScreen，侧栏高亮 analysis | DELAY / PLAN | `app.jsx:83`; `app.jsx:91` |
| `?view=field` | FieldRecordScreen -> APSFieldReports.mount | FIELD | `app.jsx:97`; `FieldRecordScreen.jsx:1` |
| `?view=fieldgantt` | FieldGanttScreen -> Content / Rows / Viewport / Chain | FG | `app.jsx:98`; `FieldGanttScreen.jsx:81` |
| `?view=review` | ExecutionReviewScreen -> ExecutionReviewContent | REVIEW / SCOPE | `app.jsx:92`; `ExecutionReviewScreen.jsx:129` |
| `?view=reports` | ReportsScreen -> ReportCenterContent | REPORT / SCOPE | `app.jsx:93`; `ReportsScreen.jsx:107` |
| `?view=calib` | CalibScreen | CALIB | `app.jsx:94`; `CalibScreen.jsx:7` |
| `?view=basedata` | MasterDataOverview -> native-session 快照 | MD | `app.jsx:99`; `master-data-overview.js:231` |
| `?view=system` | SystemManagementScreen -> 四页签 | SYS | `app.jsx:100`; `SystemManagementScreen.jsx:182` |
| `trial-sample.html` | 独立原生 JS 页面，不挂 React AppShell | TRIAL / PLAN | `AppShell.jsx:33`; `trial-sample.html:20`; `trial-sample-views.js:43` |

入口地址省略的前缀均为 `index.html`。`view` 以查询参数读取；侧栏虽然用 `#id` href，但点击被拦截转为查询路由。不是任意 hash 都可直接深链。无效 `view` 回值班台：`app.jsx:21`, `app.jsx:31`。

| 数据分区 | 实际来源与生命周期 | 生产接入约束 |
|---|---|---|
| 基础资料 | `plana-logic.js:81` session，PART_META/PART_OPS/PART_STAGE；物料/资源列表常仅 DOM 临时增删；重挂载搬回原 subtree（`plana-logic.js:1831`, `plana-logic.js:1897`） | 建立统一实体 ID、阶段与引用关系；DOM 不是数据仓库 |
| 批次与检查 | `BaseShared.jsx:456` PARTS_SEED 与 `_parts`；`BaseBatches.jsx:87` SEED -> APSBatchDraft；`batch-draft-model.js:111` 会话与 revision | 当前 process 用另一套 PART_OPS，不能误称新增工艺已自动同步批次下拉 |
| 方案选择/计划甘特/delay/trial | `aps_trial_sample_v1`；三套预置候选、初始基线 v15、草稿、采用历史（`plan-workbench.js:7`; `trial-sample.js:5`） | 正式 adopted/candidate/draft 身份、基线、版本、采用事务与审计 |
| 值班台 | `dashboard-model.js:41` 独立 September provenance；MEM 处置、回填、外协登记与历史 | 相同批次号也不能跨源认作同一记录；需显式映射 |
| 现场/现场甘特/复盘/报表 | `field-report-model.js:9` 当前报工 MEM；另有 complex/dense 隔离样例（`report-workbench-model.js:3`） | 完整工序、分次报工、修订事件、剩余计划、统计截止时间 |
| 校准 | `CalibScreen.jsx:12` 固定表；`adopted` 仅组件 state | 接真实样本统计与定额写回，不用勾标记代替 |
| 系统 | current 的 logs/backups 为 null；sample 固定 24 备份情境/64 日志；`system-workbench-model.js:48`, `system-workbench-model.js:67` | null=尚未读取，不等于空表或失败；真实文件、结果和配置另接 |

## 3. 共享外壳与标准控件

| ID | 页面 / 控件或动作 | 现状与读写 | 后端需要 / 状态边界 | 证据 |
|---|---|---|---|---|
| WBP-SH-001 | 全站 5 组侧栏、14 index 路由、trial 独立链接，标题/激活态 | UI，history push/pop；trial 整页导航 | 保持完整入口及 delay 情境入口，刷新可恢复真实上下文；无业务写入 | `AppShell.jsx:25`; `app.jsx:19`; `trial-sample-views.js:43` |
| WBP-SH-002 | 跨页携带批次/工序、scope、returnTo；返回滚动位置 | UI/MEM，contexts/positions；分析工作区另存页码/详情/折叠/表滚动 | 明确对象不存在、异源和过期版本；不得自动扩大筛选来冒充定位 | `app.jsx:25`; `AnalysisShared.jsx:3`; `fg-screen-hooks.jsx:19` |
| WBP-SH-003 | 页眉深色开关；system 浅/深；trial 深色 | UI/LS，`aps_kit_theme`；storage/pageshow/focus 同步 | 属本机偏好；读取/保存失败、非法值状态需保留，不写计划；index 与 trial 错误表现不同 | `index.html:8`; `app.jsx:52`; `app.jsx:73`; `trial-sample.js:64` |
| WBP-SH-004 | 页眉计划胶囊：标签、名称、采用/预览、版本、范围；示例页脚 | SHOW，部分取 LS，部分固定；complex/dense 甘特隐藏胶囊 | 必须取当前真正计划身份、版本/范围；不混用正式与示例 | `app.jsx:104`; `AppShell.jsx:90` |
| WBP-SH-005 | 加载中 / 依赖缺失 / 未知数据 / 读写错误提示 | SHOW/OFF，index 轮询 DS.Panel，未设加载超时；各页存在专用 error 分支 | 真加载、空数据、故障、未连接分别展示；补服务端失败/繁忙/校验状态，不能无限假加载 | `app.jsx:123`; `ReportsScreen.jsx:222`; `SystemManagementScreen.jsx:220` |
| WBP-SH-006 | React 表格表头排序、筛选弹层（值搜索/计数/全选/清除）、拖动列宽 | UI/MEM；按列配置决定排序/筛选；最小列宽 56px；批次列表自有表头 | 只改变视图；跨分页筛选范围需一致。reports/review/MD/system 明确禁用内置排序筛选，不补造不存在的按钮 | `workbench-ui.js:49`; `前端设计/components/data/Table.jsx:101`; `前端设计/components/data/Table.jsx:198`; `前端设计/components/data/Table.jsx:402` |
| WBP-SH-007 | process 原生表头三态排序、逐列筛选/搜索值/全选/清除、列宽拖动 | UI/DOM；仅 `.plana table.tbl`，跳过 checkbox/动作列排序；重绘清状态；带 colspan 行不作数据行 | 保留 UI 及筛选空态，改为基于真实数据；不能与未接线的工具栏搜索混为一谈 | `table-enhance.js:91`; `table-enhance.js:148`; `table-enhance.js:160`; `table-enhance.js:313`; `table-enhance.js:336` |
| WBP-SH-008 | 普通日期：手输、日历打开、前后月、月份选择、今天、清除、键盘选择、min/max | UI；APSDatePicker，非所有 date 控件都会被动态增强 | 使用同一日期口径；disabled/readOnly/min/max 必须有效；field 的日期时间是另一套控件 | `datepicker/aps-datepicker.js:41`; `datepicker/aps-datepicker.js:101`; `datepicker/aps-datepicker.js:222`; `BaseShared.jsx:162`; `BaseBatches.jsx:19` |
| WBP-SH-009 | 模态关闭 X/取消/遮罩/Escape、Tab 圈定、触发器焦点恢复、背景锁定 | UI，各模块实现不等同；dashboard/field import/trial 有 inert 与焦点处理，通用 process 窗口仅基本关闭 | 无业务写入；手输与嵌套弹层关闭行为需逐个真浏览器验收，不能假定共享弹窗全有焦点圈定 | `dashboard-workbench.js:11`; `field-reporting.js:11`; `trial-sample.js:92`; `plana-logic.js:1273`; `BaseShared.jsx:220` |

## 4. 值班台 dashboard

**子面覆盖**：6 类关注（交期风险、执行偏差、外协跟踪、停机冲突、齐套缺口、方案选择）各可切 4 页签（处置清单、影响分析、方案对比、处置历史）。不是旧 README 所述的 7 张风险卡。真实数据需要模型重新产出类别条目；关闭条目不消灭计算风险。

| ID | 子页 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-DASH-001 | 顶部 5 指标点击、6 类关注卡、窄屏类别下拉、4 页签 | UI/SHOW，读 stats/entries；写 caseId/tab/selectedItem | 真实交期风险、资源压力、回厂、回填、待排计数与条目来源 | `dashboard-views.js:113`; `dashboard-markup.js:15`; `dashboard-workbench.js:95` |
| WBP-DASH-002 | 处置清单：状态（全部/未关闭/待分析/跟进中/待验证/已关闭）、搜索批次/责任人/动作/备注、清除 | UI/MEM 查询；列异常依据、责任人/期限、动作/备注、状态、操作；空匹配提示 | 稳定异常 item ID、责任期限及逾期判断、同范围计数 | `dashboard-model.js:45`; `dashboard-model.js:70`; `dashboard-views.js:87` |
| WBP-DASH-003 | 处置弹窗：status、owner、deadline、action、remark；保存/取消 | MEM，更新 handling，追加 before/after；保存无变化拒绝，证据备注必填；非待分析需责任人/期限/动作 | 可持久化处置台账、乐观版本/失败不丢草稿、审计来源；不更新风险结果 | `dashboard-workbench.js:28`; `dashboard-model.js:85` |
| WBP-DASH-004 | 关闭凭据：completedAt、evidenceRef、completionEvidence；关闭/查看关闭记录 | MEM/OFF；已关闭整个字段组禁用；关闭需具体结果+凭据，不能只填“已处理”；完成时间须有效且不晚于示例时点 | 真实业务时点、可审计人工声明、状态转换守卫；凭据存在/核验不能由文本自证 | `dashboard-workbench.js:30`; `dashboard-model.js:93` |
| WBP-DASH-005 | 重开弹窗、必填原因、保留旧关闭凭据历史 | MEM；仅已关闭可重开，转跟进中、清空本轮完成字段 | 追加重开事件，保留旧证据，不覆盖历史 | `dashboard-workbench.js:44`; `dashboard-model.js:104` |
| WBP-DASH-006 | 条目历史入口/历史条目下拉/逆序记录/展开变更前后/来源表 | UI/MEM；记录序号、示例时间、动作、备注、字段旧新值；无历史空态 | 持久审计事件、操作者/时间/数据来源和实际业务修改区分 | `dashboard-views.js:101`; `dashboard-model.js:79` |
| WBP-DASH-007 | 交期影响：资源时段条 hover、批次选择高亮、影响批次表、对比调整方案 | UI/SHOW，固定 jobs + 派生交期；不生成排程 | 真实完整批次交期/完工、可核实相关资源时段；共用设备不是延期根因 | `dashboard-views.js:29`; `dashboard-views.js:34`; `dashboard-workbench.js:101` |
| WBP-DASH-008 | 执行偏差：定额/实际/偏差表、计划实际对照、逐条回填 | MEM；start/end/hours；结束须晚于开始，不可未来，工时非负；两时间齐而工时空会按跨度填值 | 需决策是否与真实分次报工合并；不能沿用自动跨度作有效工时。与 FIELD 当前不互写 | `dashboard-views.js:39`; `dashboard-workbench.js:36`; `dashboard-workbench.js:74` |
| WBP-DASH-009 | 外协跟踪：未回厂/超时/已回厂、登记入口、当前跟踪依据 | SHOW+MEM；发出 sent、计划 planned、实际 returned、确认状态 confirmedState | 外协发出/回厂/人工确认事实、供应商、周期与后续重排；不是仅用计划推算 | `dashboard-views.js:51`; `dashboard-workbench.js:39` |
| WBP-DASH-010 | 保存外协登记及错误：缺发出/计划、倒序、未来实际、已回厂与时间不一致 | MEM，写 externalRows 和审计；confirmed 用假时钟递增 | 后端一致校验与保存结果；不能把周期估算当回厂事件 | `dashboard-workbench.js:83`; `dashboard-model.js:111` |
| WBP-DASH-011 | 停机冲突：检修条、原计划任务条、重叠工序表、原因/登记时点 | SHOW/UI，仅样例时段交集；本页无新增/编辑停机弹窗 | 有效停机台账与同版计划交集、最终延期另由排程得出 | `dashboard-model.js:38`; `dashboard-model.js:61`; `dashboard-views.js:59` |
| WBP-DASH-012 | 齐套缺口：批次/数量/交期/齐套状态/日期、排产约束展示 | SHOW，固定 pendingRows；没有本页物料需求编辑 | 批次齐套事实、相关物料缺口查询；状态不能推出缺料数量 | `dashboard-model.js:33`; `dashboard-views.js:64` |
| WBP-DASH-013 | 三候选 radio、收益代价表、逐批变化、摘要弹窗 | UI/SHOW；写独立 state.plan；摘要只有返回比较/取消，无采用动作；输入变化显示候选未重算 | 同一批次范围的正式候选及指标、输入版本失效标记；不能用 PLAN 的候选 ID 偷换 | `dashboard-views.js:68`; `dashboard-workbench.js:49`; `dashboard-workbench.js:120` |
| WBP-DASH-014 | 无独立候选类别提示、转现有候选；关联页面确认弹窗 | UI；显示不同数据源“无法定位”，确认仅打开目标概览，保留 origin；无导航回调会报错 | 明确实体映射后才定点跳转；保留不可定位分支及返回路径 | `dashboard-model.js:115`; `dashboard-workbench.js:46`; `dashboard-workbench.js:62` |

## 5. 基础资料 process

**实际子页**：工艺、物料、自制工种、设备、人员、外协工种、供应商、工作日历。以下 PROC 清单只按 `plana-logic.js` 当前原生界面；旧 React Base* 全功能编辑器不因 script 已加载就自动算入。

| ID | 子页 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-PROC-001 | 顶部产能链各节点点击/键盘进入；下一步批次管理；计数/就绪度 | UI+SHOW；state.node/sub；多数计数固定：12/86/14/23/4/5 等 | 实际各域数量、异常与就绪检查口径，不把装饰统计写成生产结果 | `plana-logic.js:77`; `plana-logic.js:144` |
| WBP-PROC-002 | 工艺列表全部/待导入路线/待分拣/待填工时/已就绪，进度三段、下一步 | UI/MEM 派生 PART_STAGE，点击图号/去分拣/填工时打开详情弹窗 | 阶段模型、可调度条件、阶段人数/计数同源；只读状态也需真实投影 | `plana-logic.js:508`; `plana-logic.js:801`; `plana-logic.js:1132` |
| WBP-PROC-003 | 工艺/物料/各资源列表工具栏搜索输入、分页上一页/下一页 | **STUB**，存在输入/第 1/1 页外观，未找到对应全文搜索或翻页处理器；表头过滤另见 SH-007 | 真列表查询、总数/页数、搜索联动；不要把可手输当搜索已实现 | `plana-logic.js:265`; `plana-logic.js:275`; `plana-logic.js:662`; `plana-logic.js:1123`; `table-enhance.js:401` |
| WBP-PROC-004 | 新增零件弹窗：图号、名称、路线文字；实时拆序；逐序自制/外协、换型/单件工时 | MEM；保存写 PART_META/OPS/STAGE/CODES，未知工种登记待归类；图号/名称/路线必填、重复图号拒绝 | 统一零件库、正式路线解析、归属与工时合同；未知不得默认可排；新零件下拉须联动批次 | `plana-logic.js:1579`; `plana-logic.js:1638`; `plana-logic.js:1686` |
| WBP-PROC-005 | 录入路线菜单：导入 / 手工新建；无路线详情提示 | UI；菜单及手工新建可操作，导入转通用假导入 | 正式路线输入流程、未解析/未生成清晰区分 | `plana-logic.js:628`; `plana-logic.js:1139` |
| WBP-PROC-006 | 手工路线弹窗：整条文本/逐行表格切换，工序号/工种 datalist，增加/删除行，预览和未识别摘要 | UI/MEM；parseRouteText 拆序；至少一道才保存，保存进 PART_OPS/阶段/待建 | 正式序号唯一性/合法性、工种解析诊断、非连续序号/未知工种策略；保留两种录入模式 | `plana-logic.js:452`; `plana-logic.js:1326`; `plana-logic.js:1396`; `plana-logic.js:1450` |
| WBP-PROC-007 | 零件详情三步 stepper、归属/工时锁定、已完成步骤重新打开、就绪汇总 | UI+MEM/OFF；根据 route/attr/hours 控制，重开不代表恢复原数据 | 服务端阶段与必填守卫，路线改动的下游失效/审计；保留锁定原因 | `plana-logic.js:550`; `plana-logic.js:753`; `plana-logic.js:783` |
| WBP-PROC-008 | 工序归属分拣：自制/外协段控、建议/置信/依据、待定/待确认/已选；完成归属 | **DOM+MEM/OFF**；未选完禁用；提交仅 `s.attr='done'`，不写行内选中的 src 或确认人/依据 | 每道实际归属写回、建议来源、人工确认人与时间、重导不覆盖人工确认；不能只解锁下一步 | `plana-logic.js:577`; `plana-logic.js:590`; `plana-logic.js:1185` |
| WBP-PROC-009 | 定额工时：换型/单件输入、空缺黄标、单件 0 红标、保存 | MEM；按 seq 找工序保存原字符串；无统一有限数值校验，单件 0 被视异常 | 正式工时单位/零值/有限性与保存范围；需解决与 MD/BATCH 允许 0 的口径差异 | `plana-logic.js:630`; `plana-logic.js:717`; `plana-logic.js:1159`; `master-data-overview.js:133` |
| WBP-PROC-010 | 工时详情“导入工艺路线”“导入工时定额”“查看未匹配”，工序搜索 | **STUB**：控件可见，wireHours 仅工时输入/保存；未匹配 312/320、8 条为固定文字；详情按钮未见接线 | 真未匹配记录/下载与导入事务；列表同名导入按钮有弹窗，不能据此推定详情也连通 | `plana-logic.js:630`; `plana-logic.js:681`; `plana-logic.js:783`; `plana-logic.js:1159` |
| WBP-PROC-011 | 已就绪：只读逐序资源/归属/工时/外协周期、汇总，编辑重新打开，导出清单 | SHOW/UI；编辑转 attr；导出仅 toast STUB | 读取真实工序快照与可排状态、真实清单下载 | `plana-logic.js:612`; `plana-logic.js:794` |
| WBP-PROC-012 | 待归类工种：来源记录、去工种库、建为自制/建为外协 | MEM；仅写 KNOWN_INT/EXT 并移除 pending，未建 OP_INT/EXT 实体，也未更新引用工序 | 正式工种 ID 建档、归属确认和引用联动；“自动可排产”提示不构成实现 | `plana-logic.js:445`; `plana-logic.js:1073`; `plana-logic.js:1105` |
| WBP-PROC-013 | 物料列表/新增：编号、名称、规格、库存（带单位文本）、状态启用/低库存/停用 | SHOW+DOM；必填编号/名，新增当前表；无真实库存流水 | 物料实体、库存数值/单位、状态口径；低库存阈值由真实数据定义 | `plana-logic.js:833`; `plana-logic.js:1489`; `plana-logic.js:1717` |
| WBP-PROC-014 | 自制工种列表/新增：编号、名称、产能备注；显示可用设备/人员数量 | SHOW+DOM，新增数量 0；归类来源与表格源并不统一 | 工种 CRUD、真实设备/技能关系计数、编号唯一性 | `plana-logic.js:1063`; `plana-logic.js:1495`; `plana-logic.js:1534` |
| WBP-PROC-015 | 设备列表/新增：编号、名称、单一绑定工种、设备组 A/B/C、可用/检修 | SHOW+DOM，单选下拉 | 设备实体、真实工种/组可选项及引用、可用/检修状态来源 | `plana-logic.js:1064`; `plana-logic.js:1499` |
| WBP-PROC-016 | 人员列表/新增：工号、姓名、多选技能、白班/两班倒/夜班、在岗/请假 | SHOW+DOM，多选 chips；未建真实设备操作关系 | 人员/技能/班次/可用性合同；技能不能自动当设备操作授权 | `plana-logic.js:1065`; `plana-logic.js:1505`; `plana-logic.js:1724` |
| WBP-PROC-017 | 外协工种列表/新增：编号、名、分别/合并周期策略、备注 | SHOW+DOM，默认周期策略只为文本 | 工种与周期策略；合并外协组需要显式关联与周期，不从文字猜 | `plana-logic.js:1067`; `plana-logic.js:1511` |
| WBP-PROC-018 | 供应商列表/新增：编号、名、多选外协工种、默认周期文本、启用/待复核/停用 | SHOW+DOM，弹窗只有身份必填 | 供应商实体、工种绑定、正数周期/单位、状态与引用校验 | `plana-logic.js:1068`; `plana-logic.js:1516` |
| WBP-PROC-019 | 上述 6 类列表复选框/全选/取消选择；单行删除/批量删除确认 | UI+DOM；无选择显示“知道了”；确认后移除 tr，**没有执行文案声称的引用保护** | 引用受阻、逐行结果、原子性与审计；不能照搬“确认即成功” | `plana-logic.js:1226`; `plana-logic.js:1273`; `plana-logic.js:1908` |
| WBP-PROC-020 | 6 类列表编号/查看编辑/查看绑定/查看供应商 -> 统一详情 | UI/SHOW；仅 RECORDS 中已登记编号可打开；新 DOM 编号通常无详情 | 真 ID 明细/编辑入口、关联数据，找不到有明确信息；详细动作见 DETAIL | `plana-logic.js:1908`; `detail-drawer.js:138` |
| WBP-PROC-021 | 通用导入：物料、自制工种、设备、人员、外协工种、供应商、工艺路线、工时定额；模板、点选/拖拽区、确认 | **STUB**；模板 toast；点击 drop 变固定“128 行/126 可导/2 更新”；无 file input/拖拽读取/解析/提交；未选也能确认 | 各类正式模板/上传/校验/增量更新、关键字段引用确认、真实结果；2000 行仅文案上限 | `plana-logic.js:1764`; `plana-logic.js:1793`; `plana-logic.js:1809` |
| WBP-PROC-022 | 同上 8 类导出：当前筛选/全部，Excel/CSV，导出确认 | UI+STUB，段控会切，最终只 toast，无文件 | 同筛选全量导出、真实 Excel/CSV；不得把列选择状态当导出范围 | `plana-logic.js:1780`; `plana-logic.js:1801` |
| WBP-PROC-023 | 工作日历月视图、前/后月、今天、日格鼠标/键盘，统计及默认规则 | UI/MEM；初始 2026-06，今天用本机真日期；周一到周五默认 8h/100%，周末休息 | 真实日历默认与覆盖、工作时长/效率/普通急件可排性；日历统计独立于 rail 固定数字 | `plana-logic.js:84`; `plana-logic.js:848`; `plana-logic.js:898` |
| WBP-PROC-024 | 单日弹窗：工作/休息，工时 0..24（步长 .5）、效率 0..200（步长5）、允许普通/急件、备注；保存/清除 | MEM；休息工时区变淡+pointerEvents，非真正 disabled；清除恢复默认；JS Number 或0无完整范围守卫 | 服务端日历合法性/互斥、0值含义、真实结果与审计；两个优先级都关为停排 | `plana-logic.js:919`; `plana-logic.js:960`; `plana-logic.js:971` |
| WBP-PROC-025 | 批量日历弹窗：起止日期、每天/仅工作日/仅周末、工作/休息、工时/效率、普通/急件；应用 | MEM，逐日写 cfg，备注固定批量设置；空/倒序日期拒绝 | 批量范围上限、覆盖预览/确认、日历版本与校验；不能用无界日期循环 | `plana-logic.js:998`; `plana-logic.js:1030` |

## 6. 统一详情 DETAIL（含嵌套关联入口）

本模块自称 drawer，当前实际样式是居中模态面板。记录独立硬编码，不随 PROC DOM 或 BATCH 更新。所有类型均有 X/Escape/遮罩关闭；关联编号可继续换详情；仅“在甘特图中定位此批次”有真实导航回调，其他页脚按钮统一 toast。

| ID | 可达实体 / 字段 / 页脚动作 | 现状与读写 | 后端需要 / 边界 | 证据 |
|---|---|---|---|---|
| WBP-DETAIL-001 | 物料：规格、库存、单位、状态、引用零件；编辑物料/调整库存 | SHOW/UI + 页脚 STUB；零件关联可点 | 按实体读取库存与引用；编辑/调整库存真实提交需落实 | `detail-drawer.js:143`; `detail-drawer.js:368` |
| WBP-DETAIL-002 | 零件：名、标准工时、自制/外协数、解析状态、工艺顺序；打开工艺详情/导出清单 | SHOW/UI+STUB；可从物料关系或校准图号进入 | 真工艺 ID 与阶段导航、清单；当前“打开”按钮不是 PROC 定位 | `detail-drawer.js:161`; `CalibScreen.jsx:45` |
| WBP-DETAIL-003 | 自制工种：设备数/人员数/口径/备注、关联设备/人员；查看绑定/编辑工种 | SHOW/UI+STUB | 真实绑定集合和编辑能力；固定数字不作关联证据 | `detail-drawer.js:194` |
| WBP-DETAIL-004 | 外协工种：周期策略/备注/口径、供应商；查看供应商/编辑工种 | SHOW/UI+STUB | 真实供应商关系、周期策略维护 | `detail-drawer.js:209` |
| WBP-DETAIL-005 | 设备：名/工种/组/状态、可选本周任务/利用率；查看甘特/编辑设备 | SHOW/UI+STUB | 当前窗计划+日历产能、设备编辑与甘特定点导航 | `detail-drawer.js:222` |
| WBP-DETAIL-006 | 人员：名/技能/班次/本周排班/状态；查看排班/编辑人员 | SHOW/UI+STUB | 真实人员可用性/排班与编辑；不能直接凭状态文本扣产能 | `detail-drawer.js:249` |
| WBP-DETAIL-007 | 供应商：外协工种/默认周期/状态；查看承接工种/编辑供应商 | SHOW/UI+STUB | 真实绑定、周期、维护 | `detail-drawer.js:272` |
| WBP-DETAIL-008 | 批次/旧方案/未知编号详情记录与页脚 | SHOW，RECORDS 有数据和通用 fallback，但在本轮 15 入口未找到直接打开这些批次/旧方案的当前业务按钮；不是 BATCH 新详情 | **潜在/未达**，不冒充当前已挂载能力；若后续接入既有跨链应重新核对。批次定位有回调，延期按钮仅 toast | `detail-drawer.js:290`; `detail-drawer.js:316`; `detail-drawer.js:377`; `detail-drawer.js:405`; `app.jsx:64` |

## 7. 批次管理 batches

| ID | 子页 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-BATCH-001 | 列表字段：批次、图号/名、数量、交期、工序进度、优先级、齐套、状态、操作 | SHOW/MEM 读 Draft；状态有待排/已排/加工中/已完成/已取消；无新分页控件 | 真批次与逐序状态/缺项；不按前序完成推断实际已开工 | `BaseBatches.jsx:35`; `BaseBatches.jsx:439` |
| WBP-BATCH-002 | 搜索批次/图号/名；筛选弹层状态+齐套；条件 chips 单清/清全部 | UI/MEM，存 session drafts | 同范围查询；空列表区分无数据/无匹配；保留往返状态 | `BaseBatches.jsx:343`; `BaseBatches.jsx:390`; `batch-draft-model.js:71` |
| WBP-BATCH-003 | 各数据列表头三态排序、值多选/全选/清本列/完成/外点/Escape；列宽 | UI/MEM；批次自有表头与 Draft.query，不借内置筛选 | 服务端全量范围排序筛选与计数；不误导只筛当前页 | `BaseBatches.jsx:316`; `BaseBatches.jsx:485` |
| WBP-BATCH-004 | 勾单行/当前筛选全选/半选/清除选择，跨筛选隐藏选中数量 | UI/MEM selection；批量条只在已选时出现 | 明确操作 ID 集合，防止筛选改变误删隐藏对象 | `BaseBatches.jsx:424`; `BaseBatches.jsx:542`; `batch-draft-model.js:84` |
| WBP-BATCH-005 | 工序概况 details 展开：序号/工种/缺项、已完/总数进度 | SHOW/UI/MEM，expanded 保存 | 真实工序列表/缺项，不把概况当编辑；无路线显示未生成 | `BaseBatches.jsx:439` |
| WBP-BATCH-006 | 新增弹窗：batch_id、part_no、quantity、due_date、priority、ready_status、ready_date、remark | MEM；保存新待排批次、ops=[]；批次/图号/数量必填，正整数、重复、非法日期报错 | 正式批次创建、模板引用、主键唯一、齐套/交期合同；创建不冒充已生成工序 | `BaseBatches.jsx:458`; `BaseBatches.jsx:560`; `batch-draft-model.js:32` |
| WBP-BATCH-007 | 批量修改：优先级/交期/备注可选；预览旧新值；确认/取消 | MEM；留空不覆盖，至少一项变化；预览绑定 revision | 服务端受影响集合与版本校验、原子写回；数据/预览变化拒绝 | `BaseBatches.jsx:304`; `BaseBatches.jsx:607`; `batch-draft-model.js:138` |
| WBP-BATCH-008 | 复制所选：新编号/全部字段与工序预览、确认 | MEM；递增尾数/无尾号加 copy；重生成工序编码、done=false/status=pending | 真实编号分配、复制策略与快照/完成状态重置，碰撞/越界报错 | `BaseBatches.jsx:474`; `batch-draft-model.js:151` |
| WBP-BATCH-009 | 单行删除 X / 删除所选：旧值预览、确认；详情删除二次确认 | MEM；删除会话记录与草稿；列表 preview 版本守卫；详情无真实引用检查 | 引用保护、已排/已执行批次策略、数据保留及删除审计 | `BaseBatches.jsx:449`; `BaseBatches.jsx:690`; `batch-draft-model.js:129`; `batch-draft-model.js:174` |
| WBP-BATCH-010 | 导入弹窗：overwrite/append/replace，真实 .xlsx 文件选择/文件名，确认 | FILE(仅文件名)+STUB；未选禁用；onDone 只警告未导入，**不解析/覆盖/清空** | 正式首工作表解析、逐行诊断、三模式与 replace 保护；不能把选文件当已导入 | `BaseBatches.jsx:191`; `BaseBatches.jsx:197`; `BaseBatches.jsx:255` |
| WBP-BATCH-011 | 批次导入模板下载 | OFF：按钮 title 明说尚无模板 | **必须落实**实际 xlsx 模板（字段说明/示例），不可直接丢弃该能力 | `BaseBatches.jsx:243` |
| WBP-BATCH-012 | 批量导出及已选计数 | STUB；无选择提示先勾选，已选提示未生成文件 | 需要决策“当前筛选”文案与实际“选中”触发范围，真实导出合同 | `BaseBatches.jsx:418`; `BaseBatches.jsx:520` |
| WBP-BATCH-013 | 批次详情四区、返回列表/返回排产、缺项/未齐套定位/清除定位 | UI/MEM；view/openId/location 会话保留 | 真实批次 ID 深链、来源范围与返回；不存在对象明确提示而非换对象 | `BaseBatches.jsx:148`; `BaseBatches.jsx:184`; `BaseBatches.jsx:685` |
| WBP-BATCH-014 | 基础信息保存：数量、交期、优先级、齐套显示/日期、备注；批次号/图号禁用 | MEM/OFF；保存仅 dirty 启用，非法正整数/日期拒绝；有未提交编辑提示 | 正式可变/不可变字段、行版本、失败保留草稿；禁用身份字段仍需展示真值 | `BaseBatches.jsx:634`; `BaseBatches.jsx:704` |
| WBP-BATCH-015 | 同步最新模板：资料不完整停止刷新复选框；覆盖警告；二次确认 | MEM，读 BD.findPart，重建工序清空资源补充/完工标记/草稿；无模板或严格缺项不覆盖 | 真模板版本、已执行数据保护/重建策略、影响预览与结果留痕；不能照搬清完成标记 | `BaseBatches.jsx:657`; `BaseBatches.jsx:726` |
| WBP-BATCH-016 | 自制逐序补充：machine/operator/setup/unit、保存、待补色；设备可用人员提示/不匹配红字 | MEM/OFF；dirty 才保存；资源固定枚举、组合验证、有限非负工时（0允许），无静默换人 | 真设备工种/人员技能/设备操作关系与工时契约；保留不匹配且可纠正态 | `BaseBatches.jsx:759`; `BaseBatches.jsx:807`; `batch-draft-model.js:43` |
| WBP-BATCH-017 | 外协逐序：供应商、ext_days、保存；合并组 group/mode/total 只读提示 | MEM/OFF；dirty 才保存；正数天或有效合并总周期，未选供应商报错 | 正式外协组与单工序周期优先级；**本界面没有分组创建/删除/整组周期编辑入口** | `BaseBatches.jsx:788`; `batch-draft-model.js:51` |

## 8. 执行排产 run

| ID | 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-RUN-001 | 计划窗口 start/end、选择批次展开/收起 | UI/MEM，RUN_SETTINGS 默认 2026-05-23..29 | 真计划窗口、待排范围、有效日期/倒序守卫 | `GanttScreen.jsx:1`; `GanttScreen.jsx:15`; `preflight-model.js:10` |
| WBP-RUN-002 | 单批勾选、全部待排/仅已齐套/清空，显示工序/齐套 | UI/MEM；完成/取消批次不列入；picked=null 为全部 | 真批次筛选合同，空选不可执行 | `GanttScreen.jsx:9`; `GanttScreen.jsx:16`; `preflight-model.js:8` |
| WBP-RUN-003 | 齐套检查 开/关；缺资源 自动分配/暂不排；已完成工序 锁定/可重排 | MEM，影响就绪计数；`lockStarted` 实际仅 done，**无逐序已开工数据** | 真实引擎参数映射必须核对；自动分配、锁定执行事实并非当前已实现 | `GanttScreen.jsx:18`; `preflight-model.js:12` |
| WBP-RUN-004 | 待排/可进入/跳过/需处理四指标，就绪检查、跳过明细展开 | SHOW/MEM 派生 eligible/missing/invalid/noRoute/skipped；日历产能明确未校验 | 引擎前置检查结果、逐序原因码、可用产能；不是排程可行性证明 | `GanttScreen.jsx:17`; `GanttScreen.jsx:23`; `preflight-model.js:7` |
| WBP-RUN-005 | 去补齐/查看未齐套批次/处理缺项 -> batches focus 和 ID 集 | UI/OFF：无对应问题禁用 | 真实定位与往返刷新；批次修改后检查失效并重算 | `GanttScreen.jsx:7`; `GanttScreen.jsx:12`; `GanttScreen.jsx:23` |
| WBP-RUN-006 | 开始排产检查 | MEM+STUB（相对于目标“执行排产”）；只 setRan(true)，明确未生成方案；无有效工序/无选中/日期错/资料缺项禁用 | **必须接实际排产引擎**、任务状态/繁忙/失败/取消策略、结果版本；不能只改成功文案 | `GanttScreen.jsx:28`; `preflight-model.js:31` |
| WBP-RUN-007 | 查看独立方案样例 | UI 跳 analysis，与此检查不共享产出 | 接本次真实候选结果或显示无结果；当前非运行完成跳转 | `GanttScreen.jsx:30` |

## 9. 计划共享 PLAN / 方案选择 analysis

| ID | 页面 / 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-PLAN-001 | analysis/gantt/delay 查看方案下拉：三预置、可选草稿、另存已采用快照 | LS selected；读方案任务/版本，跨页同 key | 正式候选列表、有效状态、输入版本与相同方案判断；不存在不可换默认冒充 | `PlanShared.jsx:16`; `plan-workbench.js:13`; `plan-workbench.js:17` |
| WBP-PLAN-002 | 已采用/预览状态、初始基线 v15、任务 taskId、变更比较 | LS 任务/采用；UI 参数另在 PLAN_UI 内存中 | 真实基线 ID、采用 ID、版本与任务稳定身份；不要固化 v15 | `PlanShared.jsx:1`; `plan-workbench.js:9`; `trial-sample-model.js:159` |
| WBP-PLAN-003 | 采用此方案 -> 确认人(40)/采用说明(300)/确认/取消；返回焦点 | LS；有错误/冲突/已采用禁用；必填 trim；版本+1、历史含旧方案与变更数 | 正式采用事务、预览与正式隔离、版本变化冲突、完整校验、审计；失败不展示采用成功 | `PlanShared.jsx:53`; `plan-workbench.js:44` |
| WBP-PLAN-004 | 恢复本地状态 / 格式错 / storage 失败 | LS/OFF；错误不覆盖原记录，提示去 trial 检查/重置；Plan mutate error 展示 | 生产失败/过期响应不可用初始样例兜底；区分页面偏好恢复与业务状态读取 | `plan-workbench.js:22`; `plan-workbench.js:33`; `PlanShared.jsx:10` |
| WBP-PLAN-005 | 返回方案对比 / 方案试调链接 | UI；gantt/delay 共用条，trial 为独立页面 | 同一真实方案上下文；导航不能丢草稿版本 | `PlanShared.jsx:20`; `trial-sample-views.js:118` |
| WBP-ANA-001 | 指标：预计晚交批数、总拖期h、调整工序、换设备数；摘要/取舍 | SHOW，按预置任务时间计算；冲突显示不可评估；换型为预置 | 真实候选完整结果、失败/不可评估标记、指标口径与当前窗同源 | `AnalysisScreen.jsx:4`; `trial-sample-model.js:159` |
| WBP-ANA-002 | 候选对比表 radio，推荐/基线/候选/草稿/冲突/已采用标记 | UI/LS；仅选择，不采用；全体候选指标计算 | 正式候选比较，选中与 adopted 分离；草稿未评估字段显示未知 | `AnalysisScreen.jsx:16`; `trial-sample-views.js:53` |
| WBP-ANA-003 | 批次交付 / 采用记录页签；逐批截止/基准完工/预览完工/变更；批次按钮定位甘特 | UI/LS taskId；历史读取 LS；无历史/无变更空态；当前 React 宿主仅 click，没有 trial 的专用页签键盘监听 | 真交付结果、采用历史与甘特定点上下文 | `AnalysisScreen.jsx:17`; `trial-sample-views.js:94` |
| WBP-ANA-004 | 查看此方案甘特 / 交付风险 / 采用 | UI/LS，分别转 gantt/delay/共享采用窗 | 必须携带真方案，不把另一个页面的样例当结果 | `AnalysisScreen.jsx:13`; `PlanShared.jsx:53` |
| WBP-ANA-005 | 导出方案对比 CSV | FILE；有约束冲突禁用；导出的是当前候选逐批对基线，不是全部候选矩阵 | 明确导出范围/列和真实基线；下载失败提示 | `AnalysisScreen.jsx:22`; `PlanShared.jsx:66`; `trial-sample-model.js:217` |

## 10. 计划甘特 gantt / 延期说明 delay

| ID | 页面 / 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-GANTT-001 | 设备/人员/批次分组、初始基线复选、仅变更复选、搜索、展开/收起工作区 | UI/MEM PLAN_UI；任务选择 LS；时间轴硬限两个日班并折夜 | 真实可变范围、设备人员批次关系/基线；本页没有拖拽改期或缩放按钮，不能从旧页带入 | `PlanShared.jsx:27`; `trial-sample-views.js:66` |
| WBP-GANTT-002 | 任务条点选/键盘焦点、hover title、冲突叠轨/覆盖区、固定/急件/晚交/选中 | UI/LS；布局按任务区间；无匹配空态，滚动防冻结列遮挡 | 正式任务时段与状态、资源冲突结果；保留 hover/焦点/精确边界 | `trial-sample-views.js:22`; `trial-sample-views.js:75`; `trial-sample-model.js:234` |
| WBP-GANTT-003 | 右侧工序详情：批次/零件/数量/交期、设备人员、起止/固定态、工艺顺序按钮 | SHOW/UI/LS；按 predecessor 排序，不称关键路径 | 真依赖链与资源；点击选工序，不能以时间排序掩盖前序冲突 | `GanttBoard.jsx:19`; `GanttBoard.jsx:28` |
| WBP-GANTT-004 | 指定批次定位、缺失提示；交付风险/调整工序 | UI；找不到保留“未替换其他批次”，调整转 trial | 正式跨页面稳定 ID；详情不是实际报工，不能显示伪执行进度 | `GanttBoard.jsx:6`; `GanttBoard.jsx:35` |
| WBP-DELAY-001 | 预计晚交/总拖期/约束冲突/评估批次四指标 | SHOW，从所选方案共用 report；冲突时不可评估 | 同版正式计划/候选评估状态，范围和可用性 | `DelayScreen.jsx:2`; `DelayScreen.jsx:11` |
| WBP-DELAY-002 | 逐批选择：批次零件数量、截止、预览完工、预计交付、相对基线变化 | UI/MEM selected；可按期/晚h/冲突待处理 | 全批最后工序与交期投影，不能以单道完工作批次交付 | `DelayScreen.jsx:5`; `DelayScreen.jsx:12` |
| WBP-DELAY-003 | 交付依据：最后工序/设备/结束/交期；定位最后工序/对比备选 | UI/LS taskId + 导航 | 精确末工序 ID、计划与实际区分；当前没有根因时间线/建议试算动作 | `DelayScreen.jsx:7`; `DelayScreen.jsx:13` |
| WBP-DELAY-004 | 冲突明细；“不含等待/停机/缺料原因，不能认定根因”状态 | SHOW；列 vm.issues | 必须保留证据不足边界；若接原因链须真实事件/诊断服务，不得借旧 README 虚构现成功能 | `DelayScreen.jsx:13`; `DelayScreen.jsx:14` |

## 11. 独立方案试调 trial

PLAN 的候选、基线、采用概念与本页共享 LS，但本页额外提供工序试调、放弃、重置。分组只有设备/批次，**没有人员切换**（计划甘特宿主传 allowPerson=true 才有）。没有拖拽改期、自动后序移动或调用优化引擎。

| ID | 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-TRIAL-001 | 独立侧栏、brand 回首页、返回原型 analysis、主题，加载失败 | UI/LS；真正 href；编辑中阻止页面链接/beforeunload 提醒 | 独立页面与工作台同源方案/主题/返回上下文；本地加载错误明确显示 | `trial-sample-views.js:43`; `trial-sample.js:121`; `trial-sample.js:247` |
| WBP-TRIAL-002 | 候选 radio/摘要/收益代价/当前 adopted 顶栏、草稿/额外已采用行 | LS，三候选+草稿；当前正式与预览分离 | 正式候选读取、基线/草稿版本，共同遵守 PLAN-001/002 | `trial-sample-views.js:53`; `trial-sample.js:15` |
| WBP-TRIAL-003 | 甘特设备/批次、初始基线、仅变更、搜索、展开/收起/Escape | UI/LS（expanded仅MEM）；定位/hover/滚动同共用 timeline | 正式工序与日历范围；保留两组视图，不擅自增旧页选项 | `trial-sample-views.js:66`; `trial-sample.js:139`; `trial-sample.js:240` |
| WBP-TRIAL-004 | 选任务/选交付批次 -> inspector：工序、资源、起止、前序/完成、交期/固定、资源时段占用 | UI/LS；未解决 editor 时选对象/切方案被拒 | 真任务/前序/工作窗产能，工时占用非全厂利用率 | `trial-sample-views.js:105`; `trial-sample.js:82`; `trial-sample.js:127` |
| WBP-TRIAL-005 | 调整此工序：resource 下拉、start 日期时间；保存试调/取消 | LS 草稿/MEM editor；自动选设备配套人员，保持时长，不移动前后序；固定工序按钮禁用 | **必须落实真实试调预览**及固定/已执行保护、合格资源、日历/前序冲突；不能用样例一对一设备人员硬映射 | `trial-sample-views.js:111`; `trial-sample.js:155`; `trial-sample-model.js:196` |
| WBP-TRIAL-006 | 约束检查与冲突草稿：工艺资源匹配、设备/人员重叠、前后序、日历、固定保护 | MEM/LS；业务冲突可保存继续修，采用/导出禁用；畸形 ID/时间/关联会拒绝 | 服务端校验/诊断结构：kind、message、taskIds；区分不可接受输入与可编辑冲突预览 | `trial-sample-model.js:85`; `trial-sample-model.js:112`; `trial-sample.js:184` |
| WBP-TRIAL-007 | 底部采用此方案 -> 确认窗：人/说明、调整数/预计晚交、确认/取消 | LS，版本+1/历史快照；冲突/已采用/editor 禁用；确认时复核状态 | 正式采用与 audit 事务、版本冲突；当前 LS 写失败可能只内存改变，不能照搬成成功 | `trial-sample-views.js:123`; `trial-sample-views.js:127`; `trial-sample.js:202` |
| WBP-TRIAL-008 | 放弃试调 -> 二次确认 | LS，删除 draft；回已采用对应预置或 adopted；正式快照不变 | 真草稿独立生命周期、已采用不可删、失败不误报 | `trial-sample.js:219`; `trial-sample-views.js:124` |
| WBP-TRIAL-009 | 重置样板 -> 确认 | **示例专用 LS 写**，清草稿/历史回 v15，保留主题 | **待决策，不可映射生产重置**；与 index 共用 key，会影响 index 方案，弹窗“原有原型不受影响”不可照抄 | `trial-sample.js:215`; `trial-sample-views.js:130`; `plan-workbench.js:7` |
| WBP-TRIAL-010 | 批次交付/采用记录页签、键盘左右/Home/End、历史空态/无变更空态 | UI/LS；历史人/说明/时间/前方案/变更数 | 正式历史可审计，禁止用本机伪时序覆盖 | `trial-sample-views.js:94`; `trial-sample.js:240` |
| WBP-TRIAL-011 | 导出对比 CSV、成功/失败提示；浏览器打印前转浅色后恢复 | FILE/UI，导出同当前预览/初始基线；冲突禁用；没有专门打印按钮 | 真导出版本/口径；保留打印样式状态但不凭空新增业务打印功能 | `trial-sample.js:108`; `trial-sample.js:248`; `trial-sample-views.js:120` |
| WBP-TRIAL-012 | LS 恢复/结构校验/损坏提示/保存失败，编辑未保存离开保护 | LS+MEM；editor不持久化；当前只同步跨页主题事件，不主动恢复外部方案写入 | 真服务端版本更新与 stale guard；生产故障不能回初始样例后继续写业务 | `trial-sample.js:28`; `trial-sample.js:49`; `trial-sample.js:163`; `trial-sample.js:247` |

## 12. 现场记录 field

**读模型字段**：工序 `id/batch/name/op/target/machine/person/planStart/planEnd/reports`；报工 `id/reportNo/qty/start/end/hours/machine/person/remark/recorded/revision`。`null` 数量/工时不是 0；一次作业结束不是整道工序完工。整道完工需所有记录完整、累计数量恰等于应做数量。此页没有直接删除报工记录按钮，也没有人工勾“整道完工”的独立开关。

| ID | 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-FIELD-001 | 5 指标：待报/已登记开工/部分/已完/累计实报工时；状态页签+计数 | SHOW/UI/MEM，summary 汇总 tasks；状态枚举 none/started/partial/done | 正式分次报工汇总、完整性与工序完成状态；未知保持未知 | `field-report-model.js:21`; `field-report-views.js:60` |
| WBP-FIELD-002 | 搜索批次/名/工序/计划与实际设备人员/报工号；无匹配/当前条数 | UI/MEM filter/search；全局表格无内置列筛选/排序 | 同范围真实查询/计数/导出；不新增旧页独有工具栏 | `field-report-views.js:10`; `field-reporting.js:117` |
| WBP-FIELD-003 | 工序总览：累计/应做/剩余、计划起止、首实际开工、整道完工、累计工时、状态、待补 | SHOW，分次记录推导；完成可提前/晚/按时；未完显示最近作业而非整道结束 | 真计划基线+真实报工，不能由计划自动补实际 | `field-report-views.js:12`; `field-report-views.js:46` |
| WBP-FIELD-004 | 批次/箭头展开收起记录；逐次数量/实际时间/工时/资源/完整性 | UI/MEM expanded；第N次按实际开工排序 | 稳定报工 ID 与真实记录顺序；展开不改变数据 | `field-report-views.js:24`; `field-reporting.js:108` |
| WBP-FIELD-005 | 备注与录入信息展开：报工号、修改时刻、修订次数、备注 | UI/MEM reportInfo | 实际审计元数据，不用渲染顺序或假时间代替 | `field-report-views.js:34`; `field-reporting.js:106` |
| WBP-FIELD-006 | 顶部新增当前工序报工 / 行内报工 / 未完整记录补齐；原位编辑开关 | MEM editor；优先选中未完工/第一个未完工，存在未完整记录时复用；已完工行无新增入口 | 正式记录创建/补齐语义与目标选择，已完工 guard；找不到待报显示提示 | `field-report-editor.js:9`; `field-report-editor.js:34`; `field-reporting.js:109` |
| WBP-FIELD-007 | 本次数量手输、+1/-1、最小0/最大可报量、上下键；保存后累计预览 | UI/MEM 草稿；max=应做-其他记录，边界按钮禁用 | 后端重新核对剩余，不能只信前端 max；合法 0 与未知空值区分 | `field-report-form.js:6`; `field-report-editor.js:70`; `field-report-editor.js:83` |
| WBP-FIELD-008 | 实际开工/本次结束手输+日期时间弹层；前后月/月份/跨月日格、今天/清除、小时24/分钟60 | UI/MEM，hidden value+React控件；今天固定 2026-09-07，默认时分08:00 | 替换假今天/假业务截止，保留手输、外点/滚动/resize/Escape 和时间列滚动交互 | `field-report-form.js:4`; `FieldReportCalendar.jsx:32`; `FieldReportCalendar.jsx:91`; `FieldReportCalendar.jsx:174` |
| WBP-FIELD-009 | 有效工时输入、作业跨度/工时差额预览；设备/人员/备注折叠区 | MEM 草稿；hours步长.1；实际资源默认计划资源，可改固定枚举 | 正式合格资源集合与实际事实确认，工时不可自动从跨度生成 | `field-report-form.js:12`; `field-report-editor.js:78` |
| WBP-FIELD-010 | 保存报工/补齐：只开工记录、完整作业、自动整道完工 | MEM tasks/reports，报工号分配，clock+1分钟；无数据库写入 | 真创建/补齐、编号、原子累计/自动完成；留存原计划及审计；失败保留草稿 | `field-report-editor.js:95`; `field-report-model.js:22` |
| WBP-FIELD-011 | 剩余全部完工快捷动作 | MEM；先填最大数量，缺实际起止/工时则报错，完整才 save；更正完整记录时不显示此按钮 | 快捷填数不是越过校验；全部报齐且其他记录完整才整道完工 | `field-report-form.js:29`; `field-report-editor.js:112` |
| WBP-FIELD-012 | 补录/更正已有记录：更正原因按需显示且必填、保存更正；修订记录折叠/旧新值 | MEM；完整记录更正必须原因，改变已知事实也必须；revision冲突拒绝；改小数量可重新变未完 | 正式更正链、版本锁、事实不静默覆盖、完成状态重算 | `field-report-editor.js:66`; `field-report-editor.js:99`; `field-report-views.js:41` |
| WBP-FIELD-013 | 草稿暂存/恢复与取消：收起/切对象存草稿；取消丢当前草稿；焦点/编辑行高亮 | MEM state.drafts keyed task+record；切页清理保留草稿 | 决策刷新丢失是否接受，真实编辑 revision 恢复；取消不误删已保存记录 | `field-report-editor.js:21`; `field-report-editor.js:57`; `field-reporting.js:133` |
| WBP-FIELD-014 | 时间对照展开/收起：整道计划+每次实际、未知结束起点标记、hover明细 | UI/SHOW，真实内存区间作图，不画未知结束 | 真时段/未知值，计划实际图例与所有报工层次保留 | `field-report-views.js:17`; `field-report-views.js:44`; `field-reporting.js:105` |
| WBP-FIELD-015 | 批量导入窗/选文件/文件名/下载模板/直接导入/取消/关闭/重导/完成 | FILE+MEM；.xlsx首sheet、8MB、5000行、ZIP签名；忙时选择与提交禁用；有任一错误不写全批 | 真导入事务、重复提交幂等、版本复核及复杂文件边界；模板待填与示例 sheet 分离 | `field-reporting.js:62`; `field-reporting.js:72`; `field-report-import.js:41` |
| WBP-FIELD-016 | 导入结果：新增/补全/重复/空白/自动完工数量；前8错误行+剩余数；下载问题清单 | FILE+MEM；错误导出 xlsx；按报工号/批次工序+开工识别已有；只补空缺不改已有事实 | 物理行号诊断、真实行级结果、保留旧数据证明；冲突走更正流程 | `field-reporting.js:58`; `field-reporting.js:67`; `field-report-import.js:204`; `field-report-import.js:283` |
| WBP-FIELD-017 | 导出筛选内已保存报工.xlsx：报工记录/工序汇总/录入信息3 sheet | FILE；无匹配禁用；包括未报工工序汇总、不含未提交草稿；失败有状态文字 | 真筛选全量与元数据，下载核对文件内容/行数/日期/版本 | `field-reporting.js:35`; `field-report-views.js:66` |
| WBP-FIELD-018 | 行内错误、未知资源、未来/倒序/零跨度、超报、重叠、工时超跨度、有产量但0工时、记录缺项 | 实际 MEM 校验与浏览器 reportValidity；相邻时段可接续，缺结束视为无界占用 | 后端同口径 guard，不根据示例枚举放行；非负、完整性与阶段条件必须有合同测试 | `field-report-model.js:31`; `field-report-editor.js:98` |

**Excel 额外错误面**（归 FIELD-015/016）：缺首表、范围非 A1..J、非指定10列/未知/重复表头、超范围单元格、截断或合并表、无缓存公式/Excel错误/布尔/JS Date、数量非安全整数/非有限工时、1900/1904日期标志、分钟精度/非零秒/非法日历、跨工序报工号、文件内重复冲突、已有完整记录覆盖、导入到已完工工序、已有 ID/批次工序重复。证据：`field-report-import.js:88`, `field-report-import.js:119`, `field-report-import.js:147`, `field-report-import.js:176`, `field-report-import.js:204`, `field-report-import.js:230`, `field-report-import.js:283`。这是真实浏览器内解析逻辑，不是已有后端导入能力的证据。

## 13. 现场实际甘特 fieldgantt

| ID | 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-FG-001 | 当前报工/复杂样例/密集样例来源切换、计划版本/截至时间、回来源 | UI/MEM；current共用FIELD；切源清scope/search/选中/折叠/viewport；样例模块缺失禁用 | 示例切换专用决策见第19节；真实来源/版本/时点，不用样例自动补数据 | `FieldGanttScreen.jsx:85`; `FieldGanttScreen.jsx:219`; `fg-screen-hooks.jsx:1` |
| WBP-FG-002 | 外部 scope 信息、清来源范围、返回来源含滚动/选择/详情 | UI/MEM；错误不退回全量；已选不在范围提示 | 真 ID 和带版本 scope（时间/批次/资源/搜索/焦点）；保留不扩大范围行为 | `FieldGanttScreen.jsx:229`; `FieldGanttScreen.jsx:295`; `fg-screen-model.js:32` |
| WBP-FG-003 | 四指标：整道已完/已报未完/待报/平均整道完工偏差与延后数 | SHOW，平均只取完成且可比较；无样本“—” | 真实数据汇总；不能把未确认完成当未生产 | `FieldGanttScreen.jsx:157` |
| WBP-FG-004 | 设备/人员/批次视图、搜索计划/实际/剩余资源/报工号；资源/工序/报工计数 | UI/MEM；组按原计划、实际报工、剩余分别资源归属 | 真实关联资源/报工/剩余安排，换机换人不能丢子轨或错计工时 | `FieldGanttScreen.jsx:126`; `FieldGanttScreen.jsx:237`; `fg-screen-model.js:44` |
| WBP-FG-005 | 晚期下拉：全部/已完晚/到期未确认完成/剩余安排预计晚，各自计数 | UI/MEM；finishLate与forecastLate >10分钟，unclosed按计划时点已到 | 正式计划完工+实际完成+剩余计划，**不是批次交期**；三种晚不可混算 | `fg-screen-model.js:6`; `fg-screen-model.js:23`; `FieldGanttScreen.jsx:250` |
| WBP-FG-006 | 每个资源组折叠/展开、全部折叠/展开 | UI/MEM，key含source/view/name；空组禁用全折叠 | 只改界面，保留按源/视图记忆和选择定位自动展开 | `FieldGanttScreen.jsx:210`; `FieldGanttScreen.jsx:271`; `FieldGanttRows.jsx:25` |
| WBP-FG-007 | 原计划基线 / 实际报工 / 剩余计划条；实际未知结束、无剩余安排；状态/整道偏差 | SHOW/UI；实际按不同资源/重叠分轨，剩余用 explicit remainingPlan，不从差额推时段 | 真基线/实际/剩余数据、未知标记、叠轨与精确边界 | `FieldGanttScreen.jsx:34`; `FieldGanttScreen.jsx:126`; `FieldGanttRows.jsx:25` |
| WBP-FG-008 | 任务名/条点击或Enter/Space定位，选中强调，只看选中，定位选中 | UI/MEM；选中不在筛选范围时不扩大；无选中禁用相关按钮 | 真任务稳定 ID 和可见范围；返回保持选中及 viewport | `FieldGanttScreen.jsx:193`; `FieldGanttScreen.jsx:276`; `fg-screen-hooks.jsx:35` |
| WBP-FG-009 | 详情复选展开：批次/工序/数量状态、计划资源与起止、剩余计划、实际报工号/起止/资源/数量/工时/修订/备注 | SHOW/UI；hover另有完整tooltip，计划完成竖标单独tooltip；Escape隐藏 | 真详细数据，计划完成参考线不能伪装实际结束；focus与hover一致 | `FieldGanttScreen.jsx:175`; `FieldGanttScreen.jsx:298`; `FieldGanttScreen.jsx:318`; `FieldGanttRows.jsx:98` |
| WBP-FG-010 | 缩小/放大、自动/手动、刻度显示、适应全部、横纵滚动、按选任务聚焦 | UI/MEM；极限/未ready禁用；fit复位，变窗测量；不是重排 | 无业务写入；真实大跨度/大行量下性能与定位准确性需压测 | `FieldGanttScreen.jsx:279`; `FieldGanttViewport.jsx:143`; `fg-screen-hooks.jsx:82` |
| WBP-FG-011 | 关键链开关、全局/hover对象关联链、链节点点选、边理由、实/虚连线开关 | UI/SHOW/OFF；节点在筛选外禁用；无边连线禁用；当前报工链为预生成单节点快照 | **待落实真实关键链服务**与计划版本/内容匹配、不可用/部分结果。样例快照字段写着核心函数名不等于正在调用后端 | `FieldGanttScreen.jsx:110`; `FieldGanttScreen.jsx:267`; `FieldGanttChain.jsx:7`; `field-gantt-current-chains.js:7` |
| WBP-FG-012 | 关键链不可用/版本不符/内容不符/数据无效；无关联链、筛选内节点数提示 | SHOW/OFF，reject mismatch，不借别的链 | 保留真实 fail-closed 语义；complex/dense预设链不作为真实算法结果 | `field-gantt-current-chains.js:8`; `field-gantt-chains.js:95`; `FieldGanttChain.jsx:19` |
| WBP-FG-013 | 导出 CSV：计划身份、逐工序+逐次报工+剩余安排字段，按当前可见筛选 | FILE；无visible行禁用，失败 alert；未报工工序也有一行 | 真全量筛选导出、计划/报工/剩余一致版本；不把一次发起下载当文件验收 | `FieldGanttScreen.jsx:48`; `FieldGanttScreen.jsx:253` |
| WBP-FG-014 | 空结果、无计划、没有匹配晚期、只看选中范围外、数据未加载/范围不可应用 | SHOW；多种空/错误说明明确区分 | 真加载/空/错/局部数据状态与复盘联动，不回退到假样例 | `FieldGanttScreen.jsx:109`; `FieldGanttScreen.jsx:295`; `FieldGanttScreen.jsx:311`; `fg-screen-model.js:34` |

## 14. 分析共享筛选 / 执行复盘 review

**共享范围字段**：`source/dateFrom/dateTo/batch/resourceType/resource/search/focus`。日期按**计划完工日期**选工序；资源按计划或实际关联选工序，保留该工序全部报工。不是按报工日期裁片、不是只汇总被选设备上的记录。复盘/报表/甘特及导出必须锁住这一合同。

| ID | 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-SCOPE-001 | source 当前报工/complex/dense；计划完工起止日、批次、搜索 | UI/MEM，两页面共享 analysisScope；不可用来源禁用，未知源仍可见无效选项 | 真数据来源/计划版本、日期范围、完整批次选项；示例切换改造需决策 | `AnalysisShared.jsx:70`; `AnalysisShared.jsx:94`; `execution-analysis-model.js:15` |
| WBP-SCOPE-002 | 更多条件展开：全部资源/设备/人员、资源对象（含未填写）、分析范围 | UI/MEM；全部资源时对象禁用；focus=全部/到期/到期未确认/晚完>10/未报或待补/实际资源变更 | 正式查询 scope、未知资源组、按状态来源有据计算 | `AnalysisShared.jsx:104`; `execution-analysis-model.js:5` |
| WBP-SCOPE-003 | 条件chips逐清、重置本源全部范围、当前无匹配选项保留 | UI/MEM；无有效源重置禁用，切源重置全部条件 | 保留筛选因果，别把“重置筛选”变成“重置数据” | `AnalysisShared.jsx:79`; `AnalysisShared.jsx:88`; `AnalysisShared.jsx:101` |
| WBP-SCOPE-004 | 日期/范围错误、缺计划完工警告、未知数量/工时、重复工序/报工身份 | SHOW+实际模型验证；无效日期/倒序/类型/源/时间/负数等拒绝整次分析 | 正式稳定身份与字段合同，缺日期不计分母且明确数量；错/空/未知区分 | `execution-analysis-model.js:22`; `execution-analysis-model.js:131`; `report-workbench-model.js:24`; `report-workbench-model.js:43`; `report-workbench-model.js:95` |
| WBP-SCOPE-005 | scope/专题/排序/页码/详情/展开/表格滚动/returnTo 往返恢复 | UI/MEM workspace；变范围清页码/selected/recordPage | 跨页传递真 scope、版本与对象；源变化不可保留错误上下文 | `AnalysisShared.jsx:3`; `ReportsScreen.jsx:140`; `ExecutionReviewScreen.jsx:147` |
| WBP-SCOPE-006 | 共享图表：趋势折线hover title/图表数据展开，分布值/未知/空态 | UI/SHOW；趋势截至后实际=null；资源图可点击，普通分布图不可点击 | 同范围真实统计；图表可核对数据表与导出同源，不能把历史回算称历史快照 | `AnalysisShared.jsx:114`; `AnalysisShared.jsx:150`; `execution-analysis-model.js:90` |
| WBP-REVIEW-001 | 刷新复盘、报表中心/实际甘特、回来源 | UI/MEM，重新读当前内存；无analysis/无行禁用相应跳转 | 真查询刷新、状态失败可见与上下文传递；不是触发重排 | `ExecutionReviewScreen.jsx:129`; `ExecutionReviewScreen.jsx:154` |
| WBP-REVIEW-002 | 到期完成率/按时完成率/超时未确认/已报有效工时，样本数/未知工时 | SHOW；按时≤10分钟、分母0显示“—” | 真数据截至、到期分母与完成确认；不可拿批次交付率替换 | `ExecutionReviewScreen.jsx:13`; `execution-analysis-model.js:57` |
| WBP-REVIEW-003 | 范围内工序表：批次/工序、计划/整道完工、状态/到期、偏差、工时/待补；逐行定位 | UI/SHOW；选中记录MEM，转实际甘特及returnTo | 真工序结果与定位；晚完、到期未确认与无可比数据区别保留 | `ExecutionReviewScreen.jsx:104` |
| WBP-REVIEW-004 | 表排序计划完工/批次/偏差/工时、升降序、每页10/20/50、前后页 | UI/MEM；边界页禁用；排序/每页变化回第一页 | 服务端范围内稳定排序/分页与未知值位置，不能只排当前页 | `ExecutionReviewScreen.jsx:118`; `report-workbench-model.js:148` |
| WBP-REVIEW-005 | 导出汇总 CSV，成功/失败通知 | FILE；无行禁用；输出14项指标及source/version/asof/scope/tolerance，不是逐工序明细 | 正式同scope汇总下载，避免按钮名与输出类型不一致 | `ExecutionReviewScreen.jsx:150`; `execution-analysis-model.js:163` |
| WBP-REVIEW-006 | 趋势、偏差与资源分析折叠：累计完工趋势、整道偏差中位数/P90/分布、到期未确认老化分段 | SHOW/UI；无样本独立提示，P90最近秩 | 完整真实数据、计算口径/图表数据，不能推原因或责任 | `ExecutionReviewScreen.jsx:75`; `ExecutionReviewScreen.jsx:169`; `execution-analysis-model.js:75` |
| WBP-REVIEW-007 | 事实重点列表按钮、晚完明细/未确认明细/工序明细 -> reports 专题+focus | UI/SHOW，insights由当前数据计算，不是自由生成文案 | 真事实依据、目标专题/范围精确传递；保持缺数据不归责 | `ExecutionReviewScreen.jsx:28`; `ExecutionReviewScreen.jsx:79`; `execution-analysis-model.js:112` |
| WBP-REVIEW-008 | 资源工时设备/人员页签、柱/资源名下钻、每6组分页/资源明细 | UI/MEM，按已知工时降序，未报工时不抹成0；前后页禁用 | 实际设备/人员工时与未知记录，不称利用率；保留点击关联工序全部记录语义 | `ExecutionReviewScreen.jsx:40`; `execution-analysis-model.js:104` |
| WBP-REVIEW-009 | 数据范围与计算方法 details、缺字段警告、无工序/依赖缺失错误面 | SHOW/UI | 真实解释与不可用原因、失败重试入口；无数据不能显示0偏差 | `ExecutionReviewScreen.jsx:163`; `ExecutionReviewScreen.jsx:176` |

## 15. 报表中心 reports

**5 专题全覆盖**：工序完成情况、报工记录、设备工时、人员工时、数据完整性。另有“其他报表 · 数据接入状态”4项未来能力，不能忽略。这里只把其中“后台支持”认作界面文字，未用它作后端证据。

| ID | 子页 / 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-REPORT-001 | 5专题页签及左右/Home/End；刷新、执行复盘/实际甘特、回来源 | UI/MEM；换topic重置排序/页码/详情；无数据相应按钮禁用 | 正式同scope不同视图、准确返回；不是旧“执行复盘合并页” | `ReportsScreen.jsx:8`; `ReportsScreen.jsx:50`; `ReportsScreen.jsx:188` |
| WBP-REPORT-002 | 工序完成：到期完成/按时率、未确认、偏差中位/P90；表数量/剩余、计划/实际、偏差、状态/到期 | SHOW，真实内存派生；未完不显示整道结束 | 正式采用计划+事件、到期/确认/比较有效性，不称批次交付 | `ReportsScreen.jsx:64`; `ReportsScreen.jsx:154` |
| WBP-REPORT-003 | 报工记录：记录数/已报工序/工时/待补指标；报工号/批次/工序/数量/起止/工时/资源/完整性表 | SHOW | 正式逐次记录 ID、零值/未知、已保存范围，补录历史不能挤成一条工序行 | `ReportsScreen.jsx:77`; `ReportsScreen.jsx:162` |
| WBP-REPORT-004 | 设备工时：实际设备分组、涉及工序/批次/记录/已知工时/未知工时记录，工时比例条 | SHOW，含未填实际资源；没有逐资源编辑按钮 | 真实实际资源聚合；比例是本表最大值对比，不代表产能利用率 | `ReportsScreen.jsx:81`; `ReportsScreen.jsx:171`; `report-workbench-model.js:128` |
| WBP-REPORT-005 | 人员工时：同设备表结构，按实际人员聚合 | SHOW | 真分次人员工时与未知记录，不推人员效率 | `ReportsScreen.jsx:171`; `report-workbench-model.js:137` |
| WBP-REPORT-006 | 数据完整性：字段待补/未报工/待补记录/计划字段待补指标；计划/实际缺项明细 | SHOW，已知6实际字段/4计划字段；不是质量合格率 | 真数据质量诊断（数量/时间/工时/资源缺项），按可检查字段解释 | `ReportsScreen.jsx:71`; `ReportsScreen.jsx:146`; `report-workbench-model.js:63` |
| WBP-REPORT-007 | 排序下拉（随专题变化）/升降/每页10/20/50/前后页 | UI/MEM；边界禁用，专题完整表行先排序再分页 | 正式范围排序/分页；保持未知值最后与稳定同值排序 | `ReportsScreen.jsx:186`; `ReportsScreen.jsx:203`; `report-workbench-model.js:148` |
| WBP-REPORT-008 | 导出CSV（全筛选所有页）及成功/失败提示 | FILE/OFF，错或空禁用；质量专题目前导出通用 operations列，非完全同列的质量表 | 明确每专题导出列合同；校验source/范围/全部行，保留元数据与公式文本保护 | `ReportsScreen.jsx:125`; `ReportsScreen.jsx:179`; `execution-analysis-model.js:158`; `report-workbench-model.js:177` |
| WBP-REPORT-009 | 工序/报工行详情 -> 内嵌详情区：数量/待报/跨度/工时、异常说明、逐次记录 | UI/MEM；焦点进入/关闭X/Escape/回原按钮；记录每页10 | 真工序及全部报工明细、修订/缺项；跨度非定额，次结束非整道完工 | `ReportsScreen.jsx:15`; `ReportsScreen.jsx:135` |
| WBP-REPORT-010 | 详情记录分页、查看现场记录（仅current）、查看/逐行定位实际甘特 | UI/OFF；complex/dense不显示现场编辑跳转；current写FIELD筛选/选中再导航 | 真实同源记录定位与返回、异源只读守卫；保留“当前记录”可编辑与样例只读边界 | `ReportsScreen.jsx:30`; `ReportsScreen.jsx:44`; `ReportsScreen.jsx:140` |
| WBP-REPORT-011 | 趋势与分布 details：完成趋势/偏差、记录完整性/字段缺项、资源前8已知工时/待补、计划字段缺项 | SHOW/UI，5专题不同图；图表数据可展开 | 与列表/指标同scope的真实统计、前8规则及未知/空态 | `ReportsScreen.jsx:88`; `ReportsScreen.jsx:215`; `AnalysisShared.jsx:114` |
| WBP-REPORT-012 | 数据范围说明、缺计划完工警告、源/模型/字段错误、无匹配空态 | SHOW/UI | 真不可用与缺项不得转空成功；未知来源不可混入数据 | `ReportsScreen.jsx:60`; `ReportsScreen.jsx:208`; `ReportsScreen.jsx:222` |
| WBP-REPORT-013 | 其他报表：超期批次（所需数据/缺口/边界） | **STUB/待落实**，仅接入状态说明，无生成按钮 | 完整批次交期与全部计划工序/排程结果；单道完工不能判断交付 | `ReportsScreen.jsx:218`; `report-workbench-model.js:10` |
| WBP-REPORT-014 | 其他报表：资源负荷/利用率 | **STUB/待落实** | 计划占用+日历可用产能、零产能不可计算；不是实报工时除以随意固定值 | `report-workbench-model.js:11` |
| WBP-REPORT-015 | 其他报表：停机影响 | **STUB/待落实** | 有效停机台账与计划区间交集；报工间空档不是停机事实 | `report-workbench-model.js:12` |
| WBP-REPORT-016 | 其他报表：正式执行复盘/Excel | **STUB/待落实** | 正式采用身份/执行事件/Excel导出；暂停/异常原因/严重程度不可从备注推断 | `report-workbench-model.js:13` |

## 16. 工时定额校准 calib

| ID | 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-CALIB-001 | 在产工序/偏差>20%/可采纳/样本不足四指标；定额单件/实际中位数/样本数/偏差/建议状态 | SHOW，126/14/9/23和5行定额样例固定，未按FIELD计算 | 真样本筛选、暂停异常剔除、近N中位数、零/缺定额/样本不足判定 | `CalibScreen.jsx:12`; `CalibScreen.jsx:27`; `CalibScreen.jsx:38` |
| WBP-CALIB-002 | 搜索图号/工序/工种、仅看绝对偏差>20%、表头排序筛选/列宽 | UI/MEM；仅影响SEED显示，不改变固定四指标 | 真列表筛选及指标范围决策，保留未知偏差不纳阈值筛选 | `CalibScreen.jsx:35`; `CalibScreen.jsx:90`; `workbench-ui.js:49` |
| WBP-CALIB-003 | 点击图号 -> 统一零件详情 | UI/SHOW | 真实工艺实体与校准来源；当前抽屉并不回写 | `CalibScreen.jsx:45`; `detail-drawer.js:161` |
| WBP-CALIB-004 | 采纳建议/补建定额；采纳后标“样例已采纳” | **MEM标记+STUB业务写回**；无确认人/原因窗；正常无需调整、few采纳禁用 | **必须落实**真实定额写回/采用审计/锁定，样本不足保护；不能只把disabled去掉 | `CalibScreen.jsx:63`; `CalibScreen.jsx:105` |
| WBP-CALIB-005 | 导出校准明细 | STUB toast，无文件 | 真筛选数据下载（含定额/中位/样本/来源/建议状态） | `CalibScreen.jsx:96` |
| WBP-CALIB-006 | 采纳与定额维护说明 details：近N、排除暂停异常、采纳人/日期、工艺校准标记、导入不覆盖锁定项 | SHOW/待落实，正文承诺不是实现 | 确认锁定/工艺联动/导入覆盖契约及后端能力；此页不提供N值编辑控件 | `CalibScreen.jsx:105` |

## 17. 主数据总览 basedata

| ID | 控件 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-MD-001 | 刷新主数据、焦点/主数据变更自动重读；4总指标+8域计数/待维护 | SHOW/UI；APSPlanAData.ensureSession/snapshot，统计实际读取条目，不用rail装饰数 | 真主数据聚合快照/版本、可检查范围，不等于排产就绪 | `MasterDataOverview.jsx:25`; `MasterDataOverview.jsx:94`; `master-data-overview.js:231` |
| WBP-MD-002 | 待维护项/实体清单页签；数据域/检查状态/搜索/排序 | UI/MEM；实体状态待维护/已检查/停用；按问题数/编号/名称/关联数 | 真实体与诊断项（规则ID/证据/维护目标），稳定筛选 | `MasterDataOverview.jsx:105`; `master-data-overview.js:192` |
| WBP-MD-003 | 两列表：身份/域、问题/当前记录 或 状态/已填字段/关联数/摘要；每页20/50/100/前后 | UI/MEM；边界禁用；不同空态有清筛选 | 正式分页、计数、字段完整性；已检查不等于生产条件全满足 | `MasterDataOverview.jsx:68`; `MasterDataOverview.jsx:117` |
| WBP-MD-004 | 选实体 -> 侧详情；问题焦点、已填/总检查字段、返回清单焦点 | UI/MEM，默认首行，无业务编辑 | 真实体字段与当前问题证据，选择不静默变更事实 | `MasterDataOverview.jsx:35`; `MasterDataOverview.jsx:129` |
| WBP-MD-005 | 详情3页签：待维护项/相关项/字段；详情每10项分页；相关项跳实体清单 | UI/MEM；空关系/无问题可见，键盘页签；关系按实际匹配形成 | 真引用图、唯一标识、字段来源；人员设备授权/批次物料/正式外协组目前未加载需明确 | `MasterDataOverview.jsx:82`; `MasterDataOverview.jsx:135`; `master-data-overview.js:40` |
| WBP-MD-006 | 行维护、问题动作、定位当前实体、维护基础资料 | UI/MEM，requestNavigation到PROC对应域/图号/阶段/日期；未知目标报错/未找到提示 | 真维护页深链与准确目标；无导航禁用总入口，处理目标变化 | `MasterDataOverview.jsx:57`; `MasterDataOverview.jsx:80`; `master-data-overview.js:239`; `plana-logic.js:1853` |
| WBP-MD-007 | 导出筛选结果CSV：问题/实体各列、所有分页 | FILE；未加载或无结果禁用；失败提示 | 真全筛选/同快照导出，不混合DOM临时记录与正式数据 | `MasterDataOverview.jsx:60`; `master-data-overview.js:210` |
| WBP-MD-008 | 未加载域/未加载会话、读取失败、缺关系边界；实体规则检查 | SHOW+模型校验；重复编号/工种不唯一/无资源技能/检修请假/库存规格/供应商周期/工艺归属工时/日历异常 | 后端可检查字段与不可检查关系分开；零工时合法规则需与PROC统一 | `MasterDataOverview.jsx:14`; `MasterDataOverview.jsx:103`; `master-data-overview.js:45`; `master-data-overview.js:105`; `master-data-overview.js:161` |

## 18. 系统管理 system

**4页签**：概况、备份恢复、运行日志、配置。**2来源**：当前原型（未读取本机）、管理样例（固定情境）。不要把 sample 的 failed/verified 当成本机故障或健康证据。

| ID | 子页 / 字段 / 动作 | 现状与读写 | 后端需要 / 错误及禁用状态 | 证据 |
|---|---|---|---|---|
| WBP-SYS-001 | 两来源radio/4页签/键盘导航；当前检查、数据接入/数据库/备份健康四指标 | UI/MEM+SHOW；真实业务全为未连接/未知，示例来源也不改变真实状态 | 真数据接入状态、数据库/备份健康只用检测结果；保留未知/失败区别 | `SystemManagementScreen.jsx:182`; `SystemManagementScreen.jsx:203` |
| WBP-SYS-002 | 概况3个工作项整行点击：备份与恢复/运行日志/自动维护策略 | UI，进相应tab并聚焦；source不同文案不同 | 真实摘要来自备份/日志/配置结果，路径及内容不可假填 | `SystemManagementScreen.jsx:31`; `SystemManagementScreen.jsx:194` |
| WBP-SYS-003 | 页面环境自检表/重新检查：runtime/localScripts/ui/icons/styles/model/download/theme与时间 | 实际UI检查，不访问服务；有不可用状态，样式只查标记不是像素 | 生产版重写检测对象但保持布局，不能把8项通过当DB健康 | `SystemManagementScreen.jsx:60`; `system-workbench-model.js:123` |
| WBP-SYS-004 | 导出当前诊断JSON | FILE，投影检查时间/协议/检查项；排除路径/日志/storage/凭证/样例；缺download/icon禁用 | 明确“页面诊断”与正式诊断包区别；真实产品适配检测投影 | `SystemManagementScreen.jsx:200`; `system-workbench-model.js:152` |
| WBP-SYS-005 | 备份恢复列表：时间、类型、状态、摘要/文件、大小、详情；current尚未读取空态 | SHOW；sample=24条备份/恢复/清理情境，不都是文件 | 真备份清单+维护执行结果，未生成文件显示不适用，不能用记录数冒充备份数 | `SystemManagementScreen.jsx:105`; `system-workbench-model.js:32`; `system-workbench-model.js:48` |
| WBP-SYS-006 | 备份筛选：全文搜索、类型手动/自动/恢复前/恢复/清理，状态、开始/结束日期、清除 | UI/MEM；current全禁用；非法日期/倒序提示，空结果区别于未读取 | 真查询范围/元信息与完整故障原因搜索；未连接仍需保留控件位置与禁用解释 | `SystemManagementScreen.jsx:66`; `system-workbench-model.js:86` |
| WBP-SYS-007 | 备份分页/每页10/25/50；详情X/Escape、完整body、恢复校验要求 details | UI/MEM；current总数unknown、前后页禁用；sample边界禁用 | 真分页、详情/错误链，恢复成功/校验失败已回滚/回滚也失败要分别呈现 | `SystemManagementScreen.jsx:83`; `SystemManagementScreen.jsx:94` |
| WBP-SYS-008 | 立即备份 | **OFF/必须落实**，无处理器 | 正式备份执行、真实数据库/目录/维护窗口、生成副本及校验结果/失败留痕；需后续授权实施 | `SystemManagementScreen.jsx:128` |
| WBP-SYS-009 | 恢复备份 | **OFF/必须落实**，当前无目标选择/确认窗 | 真实目标文件、维护互斥、恢复前副本、恢复后校验、失败/回滚分态；保持布局，补交互必须方案确认 | `SystemManagementScreen.jsx:128`; `SystemManagementScreen.jsx:102` |
| WBP-SYS-010 | 删除备份 | **OFF/必须落实**，无处理器 | 真文件清单、目标确认、保底留存、执行结果及审计；不可映射 DOM 删除 | `SystemManagementScreen.jsx:128` |
| WBP-SYS-011 | 日志表：运行文件与操作记录分开；时间/类型/状态/级别/摘要/文件/详情 | SHOW，sample=64条；ERROR/WARNING/INFO，完整body含长错误链 | 真日志读取分页，OperationLogs与aps_error.log/aps.log/launcher.log范围区分 | `SystemManagementScreen.jsx:105`; `system-workbench-model.js:56` |
| WBP-SYS-012 | 日志搜索全文详情/文件、类型runtime/operation、状态、级别、记录集、日期/清除/分页/详情 | UI/MEM；current筛选/翻页禁用；显示未读取而非0；日期错误 | 真日志筛选/解析、稳定页码、完整详情/错误上下文；不修改运行日志 | `SystemManagementScreen.jsx:66`; `SystemManagementScreen.jsx:125`; `system-workbench-model.js:96` |
| WBP-SYS-013 | 导出样例日志CSV（所有筛选页） | FILE；current/无下载/错误/空禁用，success只说交浏览器 | 真日志导出与来源/时区/全分页；浏览器失败有明确提示 | `SystemManagementScreen.jsx:126`; `SystemManagementScreen.jsx:190`; `system-workbench-model.js:164` |
| WBP-SYS-014 | 正式诊断包 | **OFF/必须落实**，独立于页面JSON | 本机日志读取与ZIP构包接口、诊断范围与清单；不能以SYS-004完成替代 | `SystemManagementScreen.jsx:127` |
| WBP-SYS-015 | 即时偏好：浅/深radio、每页10/25/50、紧凑行距 | UI/MEM+主题LS；主题缺宿主回调禁用/失败报错，列表偏好仅当前页面 | 保持即时生效；决定是否持久化页面偏好，不属于维护配置业务写入 | `SystemManagementScreen.jsx:139`; `SystemManagementScreen.jsx:154` |
| WBP-SYS-016 | sample自动维护草稿8字段：auto_backup_enabled、auto_backup_interval_minutes、auto_backup_cleanup_enabled、auto_backup_keep_days、auto_backup_cleanup_interval_minutes、auto_log_cleanup_enabled、auto_log_cleanup_keep_days、auto_log_cleanup_interval_minutes | UI/MEM；开关yes/no，间隔1..1440整数min，保留1..365整数day；current无真配置表值 | 读正式配置快照与同字段校验，旧非法值/关闭开关时数字校验策略需映射；不另加样板没有选项 | `system-workbench-model.js:18`; `SystemManagementScreen.jsx:161` |
| WBP-SYS-017 | 检查参数 / 还原样例；字段错误 / 通过预览（未保存） | MEM，validateConfig，清预览/错误；无业务写入 | 正式校验结果/失败保留草稿；“还原样例”不得变生产恢复默认而不确认 | `SystemManagementScreen.jsx:164`; `system-workbench-model.js:73` |
| WBP-SYS-018 | 保存正式配置 | **OFF/必须落实**；始终禁用，未读快照/无保存 | 正式读取、版本保护、保存和结果审计；检查参数通过不能当已保存 | `SystemManagementScreen.jsx:162` |
| WBP-SYS-019 | 生效范围与自动维护规则；恢复/回滚失败、未校验/已跳过/受阻/待执行 | SHOW/UI；访问请求触发/非后台定时、失败跳过清理/保底保留等为样例文字 | 由后端事实核对全部规则；不能把sample待执行条目当任务队列，也不能据文件存在判健康 | `SystemManagementScreen.jsx:178`; `system-workbench-model.js:5`; `system-workbench-model.js:32` |

## 19. 需要先落实的决定

### 19.1 示例专属控件与固定来源

以下是**保持布局、替换真实语义的候选处理方式**，不是已批准改动。禁止直接删去这些控件而称“已完整移植”；也禁止把演示动作直接对准生产库。

| 决策点 | 影响能力 ID | 当前源码事实 | 生产决策要求 |
|---|---|---|---|
| 数据源开关 | FG-001、SCOPE-001、SYS-001 | current/complex/dense 与 current/sample 是隔离样例，非真实计划来源；`report-workbench-model.js:3`; `SystemManagementScreen.jsx:203` | 保留现有区域与控件尺寸，决定是否改为真实计划/快照来源或保留独立演示模式；演示不能写真实库，真实数据空/错不得回退样例 |
| 重置样板、还原样例 | TRIAL-009、SYS-017 | trial重置共享 `aps_trial_sample_v1`（会影响index计划页）；system只还原草稿；`trial-sample.js:215`; `SystemManagementScreen.jsx:174` | 不映射清空生产计划/历史/数据库；分别决定改成重置试调草稿、重读正式配置或仅演示可用。文案、禁用原因、确认窗随真实影响调整 |
| 假当前时间与假审计时刻 | DASH-003..010、FIELD-008..016、FG-001、SYS-005 | dashboard NOW=09-07 11:40；field NOW=09-07 16:30；编辑后分钟递增；complex=09-08 12:00；system fixed sample 09-07；`dashboard-model.js:9`; `field-report-model.js:7`; `field-gantt-example.js:148`; `system-workbench-model.js:45` | 后端提供业务截止与真实事件时间，页面时间格式保持；actual不可未来要用真实时钟。不得沿用“每保存+1分钟” |
| “今天”与起始月份 | SH-008、PROC-023、FIELD-008 | 普通日历今天=本机；process初始2026-06；field日期控件今天固定2026-09-07（`FieldReportCalendar.jsx:99`） | 保持今天/清除按钮布局，统一真日期与默认窗口策略；不能移植固定今天 |
| 三种默认计划窗口 | RUN-001、PLAN-002、FG-001 | 批次/排产检查为5月，计划试调为09-08..09两个日班，现场为09-07..08；`GanttScreen.jsx:1`; `trial-sample-model.js:85`; `field-report-model.js:52` | 必须允许真实范围；scope/页眉/图表/下载统一版本和时间，不可显示固定窗而查另一范围 |
| 独立内存工艺库 | PROC-004/006/009、BATCH-006/015、MD-001 | native PART_OPS 与 BD `_parts` 不是同一源；`plana-logic.js:367`; `BaseShared.jsx:501` | 真实工艺只能有明确事实源；批次下拉、工序同步、主数据检查联动同一实体/版本。不能据BaseBatches注释称已联通 |
| 固定字典与关系 | PROC-014..018、BATCH-016/017、FIELD-009、TRIAL-005 | EQ/P-101系和M/P-021系、中文姓名等混合；设备人员关系不同模型独立硬编码 | 用真实ID/显示名/合格关系，保留原控件类型；相同显示号不能跨源认同一记录 |
| 装饰指标与派生指标 | PROC-001/013..018、CALIB-001、DETAIL全域 | 原生rail/资源数量、校准四指标和详情多为固定值，MD按实际snapshot计数 | 保持卡片/表结构，数字必须真实或标未知；显示“0”不能代替不可计算；不修饰成正式健康状态 |
| 假导入与假导出成功 | PROC-010/011/021/022、BATCH-010..012、CALIB-005、DETAIL页脚 | 有的仅弹toast，有的只选文件，有的真实Blob下载，三者不同 | 每类导入/导出必须落真实模板、文件、校验/事务/结果；不得把toast当接口成功 |
| 归属确认与建工种 | PROC-008/012 | 完成分拣只改阶段；“建为”只改识别词库。界面声称留人/时/依据，实际上未保存 | 实现逐序归属、持久确认与引用绑定，保留当前闸门布局；任何新审计字段的输入位置要在方案中定好 |
| 只做就绪检查的执行入口 | RUN-003/006 | 不调用排产，不生成候选；自动分配只计数；锁定只有done | 要满足“移植所有能力”需要明确真实执行及状态面如何进入当前布局。不能把检查按钮的成功状态改名当排产 |
| 阈值与合法零 | PROC-009、BATCH-016、CALIB-002、SCOPE/REVIEW/FG | PROC单件0红标、MD和BATCH允许0；分析容差10分钟、校准20%；`master-data-overview.js:133`; `execution-analysis-model.js:3` | 数值/单位/阈值与真实后端合同对齐；不直接增加样板没有的设置项。确需改变标签/校验须记录视觉及交互差异 |
| 关键链来源 | FG-011/012 | current加载预生成单节点数据，complex/dense为预设链；`field-gantt-current-chains.js:7`; `field-gantt-chains.js:3` | 真实服务按计划内容/版本产链，保留不可用说明；生成脚本或快照中的backend字段不是在线接口证据 |
| 校准“采纳” | CALIB-004/006 | 单纯组件标记；说明中承诺写回/锁定/导入保护没有实现 | 正式采纳需来源样本、旧/新定额、确认/审计/锁定；既有按钮保留，新确认交互设计需在方案落实 |
| “后台支持”标签 | REPORT-013..016 | `report-workbench-model.js:9` 是四条常量，源码内 evidence 字符串不是调用 | 后端独立评估逐一给真实函数/路由/请求/返回/测试证据。未核实就标“待核对”，不能自动判已覆盖 |

表中简写 ID 均加 `WBP-`；范围号表示上述既有能力族，不新造 ID。

### 19.2 禁用与占位必办台账

| 类别 | 已编号入口 | 接入/验收要求 |
|---|---|---|
| **缺实现而禁用** | BATCH-011；SYS-008/009/010/014/018 | 模板、备份、恢复、删除、正式诊断包、正式配置保存都必须逐项落实或经用户明确列为暂不交付；不能因disabled默认剔除 |
| **业务保护而禁用** | PROC-007/008；PLAN-003；TRIAL-005/006/007；CALIB-004 | 未完成前置、固定工序、冲突方案、已采用、编辑未解决、样本不足的禁用必须保留，并测试解除条件 |
| **无选择/无数据/无变化而禁用** | BATCH-010/014/016/017；RUN-005/006；FIELD-007/017；FG-006/008/010/013；REVIEW/REPORT/MD分页/导出 | 不是功能缺失；真数据条件满足后需启用，变更/空值/范围/分页边界不能漂移 |
| **依赖/来源未接而禁用** | FG-001/011/012；SCOPE-001/002/003；MD-006；SYS-004/006/012/013/015 | 缺模型、无链边、来源未加载、无下载支持、无宿主回调等要解释原因；不能用样例补全后伪装成功 |
| **可点击但只有提示/无处理器** | PROC-003/008/010/011/012/021/022；DETAIL-001..007的页脚；BATCH-010/012；RUN-006；CALIB-004/005 | 必须按真实业务动作接线；“可点击/可输入/显示成功”不足以验收 |
| **文字声明、尚无生成入口** | REPORT-013..016；CALIB-006的持久审计/锁定/工艺标记；SYS-019的维护规则 | 属样板承诺的待落实能力，不当成已实现；生成/确认/失败界面需在后续方案明确，但本轮不扩建原型 |

### 19.3 后端对照的最小交接字段

后端评估应对**每个能力ID**补：真实路由/函数与行号、方法、请求字段及单位、响应字段、计划/实体身份、事务边界、合法/非法/空/繁忙/失效状态、审计事件、验证方法。没有证据应写“未找到证据”，不能以原型测试名称、README 或字符串 `evidence` 代替。

- 查询类：实体/工序/报工/方案稳定ID + snapshot/version + asOf；表格、指标、图表、详情、CSV必须同scope。
- 写入类：明确记录版本/预览版本、确认范围与结果；批量失败不得伪装整批成功；保留原事实/草稿/审计。尤其区分实际记录、更正记录、计划草稿、正式采用。
- 文件类：模板真实字节、格式/列/单位/行限制、逐行问题、幂等和原子性、下载实际文件核对。表格数量、单位和导出范围不能靠文案猜。
- 页面联动类：source + plan/version + batch/op/report ID + scope + returnTo；无映射显示不可定位而非定位同号样例。
- 新高风险动作：正式恢复/删除/重建/采用/定额写回须在方案中明确确认和保护。样板缺确认窗不等于可以省略正式保护，也不是当前授权实施。

## 20. 覆盖、排除与验证边界

### 20.1 覆盖汇总

共 **206 个稳定能力族 ID**：其中 DETAIL-008 明确标为潜在/未达的记录级入口，其余覆盖本次14+1入口的业务面与共享控件。不是206条独立后端API，也不是206条测试通过。

| 能力域 | 数量 | 范围 |
|---|---:|---|
| SH / DETAIL | 9 / 8 | 外壳、日期、表格、弹层、统一实体明细（含1潜在入口） |
| DASH / PROC / BATCH | 14 / 25 / 17 | 6类x4页签、8基础子页及所有表单/阶段/导入导出、批次列表/详情/批量预览 |
| RUN / PLAN / ANA / GANTT / DELAY / TRIAL | 7 / 5 / 5 / 4 / 4 / 12 | 检查、方案共享、候选、计划甘特、交付依据、独立试调 |
| FIELD / FG | 18 / 14 | 分次报工/更正/Excel/校验、三来源现场甘特/关键链/导出 |
| SCOPE / REVIEW / REPORT | 6 / 9 / 16 | 共享筛选及恢复、复盘分析、5报表专题+4待接入报表 |
| CALIB / MD / SYS | 6 / 8 / 19 | 校准、8主数据域/3详情页签、4系统页签/2来源/8配置字段 |

**样式证据边界**：`index.html:16` 到 `index.html:36` 引用全局与分域样式，`index.html:305` 到 `index.html:379` 为本地依赖/组件/增强器加载顺序；独立trial用 `trial-sample.html:14` 到 `trial-sample.html:28`。DS Table实加载实现见 `前端设计/_ds_bundle.js:398`，源码对应 `前端设计/components/data/Table.jsx:101`。本次未重建bundle，也未改变样式/图标/组件。后续生产呈现应以这些当前可达页面为视觉基线，不能沿用旧截图或README里的过期侧栏/密度开关。

### 20.2 已加载但不在当前路由挂载链

| 文件 / 内容 | 本轮结论 | 证据 / 处理 |
|---|---|---|
| `BaseDataScreen.jsx` 结构切换chain/flat、旧tab/subtab与LS位置 | **未挂载**。不可把其中的资源排班/批次物料需求/外协组等算作当前样板可达入口 | `BaseDataScreen.jsx:46`; 当前路由为 `app.jsx:96` -> `ProcessNative.jsx:6` |
| `BaseProcess.jsx`、`BaseMaterial.jsx`、`BaseCalendar.jsx`、`BaseOpTypes.jsx`、`BaseSuppliers.jsx`、`BaseEquipment.jsx`、`BasePersonnel.jsx` | 由旧BaseDataScreen编排，当前只加载定义，不做这些旧编辑器的逐字段迁移承诺 | `index.html:363`; `BaseDataScreen.jsx:151`；生产旧页独有选项要另轨对照，不从这组文件推断 |
| `BasicDataScreen.jsx` | 旧通用module列表，不在14路由switch里 | `BasicDataScreen.jsx:144`; `app.jsx:86` |
| `BaseShared.jsx` | **部分实际使用**：BD字段/日期/确认等及批次PARTS_SEED有效；旧ExcelWizard等没有当前入口 | `BaseBatches.jsx:7`; `BaseBatches.jsx:197`; `BaseShared.jsx:315`; 不把整库exports全算活跃能力 |
| `detail-drawer.js` 旧批次/旧方案记录与 generic fallback | API存在但本轮当前业务入口未达，已用 DETAIL-008 单列，不伪报为已迁移 | `detail-drawer.js:290`; `detail-drawer.js:405` |

### 20.3 目录内其余独立HTML

只读目录枚举发现32个HTML：本次index/trial两个入口 + **30个未纳入当前主导航/实际挂载链的设计备选、比较页或备份**。未逐页评估这些30个HTML内部按钮；这是明确的范围边界，不是遗漏后自行删除的清单。其样式或实现若被当前JS引用，则当前可达能力已在上文清点。

| 分组 | 文件（均在样板根，注明子目录者除外） |
|---|---|
| 旧完整方案/流程 | `PlanAEmbed.html`、`基础资料-方案A.html`、`基础资料-方案对比.html`、`flow-redesign.html`、`flow-redesign-v1-backup.html`、`flow-arrows.html` |
| 甘特备选 | `甘特进度-方案对比.html`、`gantt-aps-board4-compare.html`、`gantt-aps-elements.html`、`gantt-redesign-options.html` |
| 卡片样式备选 | `ready-card-options.html`、`cal-card-options.html`、`rest-card-options.html`、`rest-card-options-C.html`、`risk-card-number-placement.html`、`risk-card-number-placement-v2.html`、`hero-card-number-emphasis.html`、`hero-card-number-emphasis-v2.html`、`hero-card-number-emphasis-v3.html` |
| 表单/工作流备选 | `form-options.html`、`batch-actionbar-options.html`、`严格模式-控件方案.html`、`排产开关方案.html`、`时间窗口方案.html`、`单件工时对齐方案.html`、`工时录入示意.html`、`工艺三步流程示意.html`、`现场记录-计划列方案.html`、`回填工具栏-方案对比.html`、`datepicker/日期选择器-重设计.html` |

实际入口判断证据为 `AppShell.jsx:25`, `app.jsx:86`, `ProcessNative.jsx:6`, `trial-sample-views.js:43`，不是根据文件名想当然。**30文件仍保留，不曾移动、备份、删除或下线。**

### 20.4 辅助测试与未完成事项

- 已只读参考 `tests/workbench-workflow-browser.cjs:58` 附近的14路由循环与跨页检查；它是测试源码，不是本轮已执行结果。其他field/import/关键链/系统/范围联动测试只作查漏线索，不证实生产后端能力。
- 未运行原型测试：一些浏览器脚本会创建临时目录、截图/measurement文件（`tests/batch-workbench-browser.cjs:9`; `tests/system-maintenance-navigation.cjs:112`），超出本轮仅可写指定文档的范围。
- 未运行 `tests/build-field-gantt-current-chain-data.cjs`；该辅助脚本可启动Python计算（`tests/build-field-gantt-current-chain-data.cjs:112`）。读取预生成快照不等于当前页面连通真实数据库/后端，测试中“backend result”不能代替接口映射。
- 未评估旧生产页独有选项。**后续必须另产旧页集合减本清单可达能力集合的差集，并逐项列暂不移植**。不得把未挂载Base*或上述30设计页直接冒充旧生产页差集。
- 未移植/改动/备份/下线任何运行时代码或旧页面；未启动服务、未运行质量门禁、未导入导出真实业务文件、未触碰真实DB。
- 未做真实浏览器手输/点击/逐项目视，未做压力测试或复杂业务测试；这些是用户要求的后续实施验收，不能由本次源码清点代替。
- 后续验收可用能力ID逐项挂证据：真实手输/点击/目视（浅深色、长中文/大数据、列表/子页/弹窗/错误/禁用解除）、接口请求/响应、DB前后差异/数据保留、真实下载文件；压力/复杂测试须用隔离数据集，最后再做旧页备份及下线验证。当前只提出交接要求，不启动该流程。
- 本轮验证仅包括：能力ID唯一性、14路由与trial覆盖、源码路径/行号存在性、原型文件写前/写后指纹对比及指定文档差异检查。不能称 clean-worktree proof；初始工作区已有大量其他改动与暂存内容，保持原样。

### 20.5 本次静态核对结果

| 核对项 | 结果与证明范围 |
|---|---|
| 能力ID | 206行、206个唯一ID；每行5列完整。编号唯一不等于206个行为实测通过 |
| 入口 | 从当前app的case提取14个路由，逐一在入口表找到；独立trial另列 |
| 源码引用 | 625处文件/行号引用均指向存在文件与有效行号。语义判断来自上述源码阅读，不因路径有效就自动成立 |
| 原型内容保留 | 写文档前对样板目录202个文件计算SHA-256，写后逐一对比，无变化、无新增文件；指纹仅留在本轮工具内存，未额外落盘 |
| 文档差异 | `git diff --no-index --check /dev/null <本文件>` 没有空白错误诊断；新文件差异返回1，不作为测试失败。指定文档为未跟踪新增，未暂存/提交 |
| 不做的证明 | 无真实后端接入证明、数据库保留实测、浏览器逐操作目视、压测、质量门禁或clean-worktree proof |

### 20.6 主任务追加的验证信息

- 用户在清单收尾时报告：已用 Chromium 109 实测15入口、60个主题/尺寸状态，无脚本报错、无外网请求，关键工作流247项check通过。此处按**用户提供的主任务验证结果**记录，不冒充本子任务独立复测。
- 本子任务未收到或核对该轮命令、运行环境与证据产物路径；不据此扩大为真实Win7系统、生产后端、完整逐控件人工验收或打包交付已通过。本文 `browser_verified: false` 仅描述本子任务的核验范围，不否定上述主任务报告；后续总方案可关联其实际证据。
