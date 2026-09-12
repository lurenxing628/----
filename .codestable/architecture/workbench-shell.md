---
doc_type: architecture
slug: workbench-shell
scope: 工作台离线外壳、领域服务、受管运行及恢复边界
summary: 真实业务工作区已挂载，逐项终验与旧入口退役仍在收口
status: current
created: 2026-09-09
last_reviewed: 2026-09-13
tags: [workbench, flask, offline, win7]
depends_on: [ARCHITECTURE]
implements: [workbench-foundation-read-loop, workbench-production-workflows]
---

# 工作台迁移宿主

## 当前边界

`/workbench` 和 `/workbench/trial` 支持15个视图，侧栏12项；计划甘特/交付风险及报表/复盘通过页内页签组织，旧URL和精确上下文仍保留。主数据、工艺、批次、候选生成和采用、正式计划、试调、执行台账、实际甘特、复盘报表、工时校准、值班台和系统维护均通过真实领域服务接线。本文件描述当前源码，不替代逐动作验收。旧入口退役与Win7打包、真机和最终发布由迁移路线图管理，本次界面质量整改不替其签发通过结论。

## 职责

- `web/bootstrap/factory.py` 注册 `web.routes.workbench`。工作台Blueprint及`/api/workbench/`请求跳过访问触发的自动维护，避免列表/回执查询额外写库或备份；维护窗口检测、请求连接、关闭连接和旧请求行为保留。
- `web/routes/workbench/assets.py` 校验本地 manifest 和引用文件；资源不完整时宿主明确503。`pages.py` 提供启动信息和只读 JSON 协议，不执行 SQL。
- `core/services/system/workbench_overview.py` 使用已提供的连接及路径进行只读投影；不补配置、不读日志正文、不校验备份、不生成备份。失败、未知和0分开。
- `frontend/workbench/app/` 负责呈现、正式主题键 `aps_theme`、请求时限/取消、响应校验及样例隔离；不计算或保存正式业务事实。
- `frontend/workbench/prototype/` 是原型依赖的可追溯副本，不是开发时依赖的忽略目录。原始 `前端设计/` 不被构建改写。
- `scripts/workbench/build.py` 在开发机将固定 React18、原有共享控件和 live 源预编译，发布到 `static/workbench/`。目标Chrome109不需要 Node、Babel现场编译或外网。

## 请求与恢复

HTML -> 提前应用主题 -> manifest本地脚本/样式 -> React宿主 -> 同源领域API -> 校验实际消费字段 -> 展示数据。读请求有时限，卸载或切换工作区取消旧读取。错误显示重试，不静默读取样例。主题偏好与业务状态分开。

系统概况的`snapshot_ref`只标识本次只读响应。新增物料列表/详情的快照则绑定筛选、排序、当前资料修订和读取时点；分页复用原引用时若数据或范围变化，明确返回`snapshot_stale`，不自动刷新。它仍不是永久实体身份。

## 界面共享层

- 应用样式集中在`frontend/workbench/app/styles/`，由`build-order.json`显式登记，按基础令牌、布局、共享控件和工作区域顺序进入资产清单。原型依赖先加载，应用层负责当前界面；静态样式不再由工作区组件反复插入。视口预算、表内双向滚动、吸顶表头与固定关键/操作列共同保证长表可用。`WorkbenchScrollShadows`在壳层挂载一次，按实际遮挡给表格框打`data-overflow-left/right`，固定列只在遮住其他列时显示滚动阴影；表头`word-break: keep-all`不在中文词内折行。顶栏是唯一可见页面标题，工作区重复的`h2`以`wb-page-title`视觉隐藏、副标题以`wb-page-context`作上下文行；工作区根统一`padding: 0`，灰底加白卡，KPI 条统一四格，甘特滚动框按行数自适应到上限。间距字面量按`--space-1..6`接线，行高有`--wb-line-*`三档，圆角统一`--wb-radius-control`。
- `WorkbenchFormat`区分工厂本地日期文本与带时区的实际时刻；空值和非法值分开处理，显示层不另加业务取值范围。`number/percent/hours`接受`{ digits, trim }`：trim 保留录入精度（最多 digits 位），录入类工时、报工累计与候选对比指标用它而不是 1 位摘要；-0 归零显示。报工时间经`FieldContract.date`保留秒。`WorkbenchTerms`统一界面术语，`WorkbenchReferences`把完整引用与诊断收纳到可展开区域，保留原始内容；值班台来源只折叠诊断码、`*_ref/*_key`与完整十六进制引用，`business_code`、`kind`等业务字段保持可见。
- `ResourceControls`和`WorkbenchControls/WorkbenchListControls`提供字段错误、空态、分页、弹窗与详情。`Button`的禁用原因分`inline`与`tooltip`两种呈现，表格操作列和工具栏用 tooltip（title 加视觉隐藏说明），表单与页面级主动作保持 inline；`Issues`把相同消息合并为一行并标注条数。分页档位由领域消费者明确给出，游标模式不虚构总数。详情按业务条目更换内容并管理焦点；只读自动预览可显式保持原焦点。密度由`WorkbenchDensity`共享订阅和保存，切换行距时保持字号和数据不变，保存失败明确显示。
- `WorkbenchGuards`按owner和作用域登记未保存输入及待核实命令；`WorkbenchGuardHost`通过共享Modal呈现确认，避免核心守卫反向依赖UI。导航、同文档前进后退和编辑器关闭都查询同一守卫，拒绝时保留URL、页面和输入；确认框不再次拦截自己，待核实业务请求不被当成可放弃草稿。`locked`只来自待核实命令，目录弹窗或重读资料等UI忙碌态不得传入；确认等待期间受保护条目全部保存或卸载时，守卫自动放行并关闭空确认框。
- `PlanSelectionModel`只在没有明确或恢复上下文时选取唯一可读的当前正式计划。选中计划或候选后目录可收起并重新展开；从候选目录切换对象后归还展开入口焦点，外部进入不抢焦点。`ActualGanttWindow`仅计算显示窗口和命中区域，按时间中心与可见时长恢复刷新/跨宽度视窗，保留原`axis_span/as_of`、点工序和真实持续时长。
- `FieldDraftModel/FieldEditorFields`仅为新建报工生成可清除的建议，并限制“上一条”的来源与复制字段。保存继续必须经过成功回执、重新读取和新的可写上下文；补齐、更正、保留草稿和未知结果继续沿原事务恢复链。任务详情位于列表滚动框之外，避免编辑器被表格高度预算裁切。

界面验收通过独立的`ui_refinement_capture.cjs`采集当前构建、源码、模板和探针哈希，覆盖15视图、双尺寸、双主题及关键交互。`ui_refinement_gate.py`拒绝缺项、陈旧证据和最终豁免；daily gate以`--workbench-ui-evidence`显式接入，不改变原有浏览器测试的默认执行政策。局部组件、完整页面和最终HEAD门禁证据分别记录。

## 已接后端

- v20增加`WorkbenchEntityRefs`、`WorkbenchCommandReceipts`及资源生命周期触发器。引用跨进程稳定；更新保留、删除重建或REPLACE产生新实例。复合内部键采用百分号/分隔符转义，覆盖NUL及UTF-8/UTF-16，不改业务字段。物料批次引用查找有独立索引。
- `WorkbenchCommandService`拥有最外层SQLite事务，先查询已提交回执，再校验短期编辑上下文、执行领域动作和落不可变回执。回执不保存短期token；不确定结果可按`request_key`查证。此服务不用于文件恢复或异步排产受理。
- `web/routes/workbench/materials.py`开放真实物料列表/详情、新增/修改/删除和命令回执API。领域动作复用`MaterialService`，保留省略字段及`BatchMaterials`事实；NULL库存不显示成零，未配置阈值不声称低库存。
- v21显式资源表不替代旧授权/班组，也不回填猜测值。资源领域服务复用旧增删改保护，`resources.py`暴露有限类型的公开实体/永久引用和短期上下文；统计过滤发生在分页前。坏资料仅影响相应指标并明确问题，真实存储故障仍拒绝读取。
- `OperatorQualificationService`同时供资源统计、可选资源池与固定人员校验使用；`operator_shift_calendar.py`由CalendarService调用，个人日期覆盖优先，全局休息与许可仍约束班次。旧完成/冻结事实不参与新资格校验而被误改写。
- 物料`material_actions*`负责服务器预览登记、短引用与真实文件下载，确认仍使用原子SQLite命令。文件导出只读；批删及增量导入整批回滚。只把2000行限制用于导入。
- `calendars.py`月读和单日/范围维护只修改全局WorkCalendar。公开投影区分编辑字段、原存储字段和实际生效工作窗，不泄露内部revision/history；原始预览留服务器。DATE在仓储统一ISO字符串，不截断datetime或做UTC转换。
- `ResourceLive`挂载真实adapter与各独立向导。`resource-api.js`验证同源、协议与提交状态；`resource-session.js`在会话存储保留待核实请求键，不持久化生产输入/短期令牌。未确认提交时不自动换请求重试。
- 非物料`resource_actions/resource_file_exports`按白名单类型开放预检、三字段确认、CSV/XLSX模板和下载。服务器保留完整原预览/字节，公开令牌仅短引用；导入限2000行，完整导出与显式批删不沿用该行数限制。scope固定自制/外协类别，未展示旧字段只读回传，不开放新写入口。
- `WorkbenchResourceFileRepository`为冲突核对保留全部引用字段，将真实SQLite DATE对象规范为ISO日期，但不截断datetime；个人日历/旧授权既阻止删除，也参与预检后的过时保护。导出不是只读取当前页或新建资源。
- `ResourceRail`消费真实资源统计与本周日历只读投影。标准工时未配置不填样例值，显式/服务默认/无许可/坏资料分开。工种文件待核实状态独立保留category，跨资源命名空间不混用。
- 计划查询已通过`core/services/workbench/`的公开领域层与`web/routes/workbench/`接到目录、分析和甘特UI。内部计划目录/页仍只负责内部数据，不直接序列化内部行号；公开计划和任务引用跨进程稳定，快照与范围另外核对。

## 当前业务与宿主

- 资源、工艺三步确认、批次三种文件导入、复制及批量操作已接领域服务。预览与原子命令保留旧授权、隐藏字段及已有业务事实，不因新UI未展示而清空。
- 排产由`web/bootstrap/workbench_run_runtime.py`及`workbench_run_lifecycle.py`管理实际worker、持久受理、候选、运行锁与停止等待。候选选择只读，正式采用必须明确确认并核对执行快照和版本。
- 试调持久草稿与正式采用分离；共享与分件工序保留原引用、单件前置关系、计划应做量和整批量。合法零时长是计划点，不占资源，也不自动成为实际完工。
- 分次报工与更正走追加台账，旧事件保留原义，未知数量和工时不补零。实际甘特、复盘、报表及工时校准消费同一已核实事实，交付风险不把缺工序或局部完工当作完整批次完成。
- 值班处理状态与业务风险分开。系统备份下载只解析已登记公开引用，文件存在不等于可恢复；`workbench_system_restore*.py`与`workbench_request_lifecycle*.py`负责排空连接、停止worker、恢复状态及冷启动核对，恢复不走普通行命令。

## 页面状态与故障

- `templates/workbench/index.html`先给可读启动状态，并由独立watchdog显示资源错误或启动超时，不依赖末尾主脚本自己报告缺失。
- `WorkbenchBoundary.jsx`隔离工作区渲染错误，保留侧栏和同对象重试。启动信息或核心资源损坏时提供重新加载入口，不渲染虚假业务页面。
- `WorkbenchNavigation.js`维护精确页面context、辅助历史状态及滚动位置；显式规范URL不被另一对象的旧history覆盖，无效定位不静默扩大为全部范围。
- `WorkbenchPageContext.jsx`让各领域显式登记已验证的只读选择和筛选，不保存写表单、不重放请求；待核实写入仍由原命令恢复协议负责。各域接入与实际回返验收仍在收口。
- `WorkbenchCaption.jsx`只消费领域DTO的真实方案身份、版本和范围。页面切换或卸载清除旧信息，无所选方案不显示样例。主题焦点返回同步不改业务状态。

## 统一交互控件

- `templates/workbench/index.html`以`body.aps-workbench`限定工作台样式和事件范围，不影响旧入口。`main.jsx`常驻挂载公共样式、下拉/日期浮层及数字微调器，后续工作区复用同一套控件。
- `WorkbenchControlStyles.jsx`沿用原主题变量和本地Lucide图标，统一按钮、输入、单选、勾选、滑块、文件选择、分页、展开状态和键盘焦点。工具区32px，编辑字段36px，控件4px圆角；导航、日历格和甘特条保留各自语义与尺寸。
- `WorkbenchControls.jsx`和`WorkbenchSelectMenu.jsx`替代原生下拉菜单、日期/月份/时间弹层；浮层限制在视口内，长选项换行并内部滚动。弹窗内使用局部portal，Esc只关当前浮层，随后恢复原控件焦点；日期支持鼠标、方向键及手输。
- `WorkbenchControlBridge.js`通过原生属性setter及input/change事件更新原React控件，不替换输入节点，不改变保存命令。`WorkbenchNumberControls.jsx`用受控portal添加微调按钮，保留min/max/step、空值和无效输入，处理卸载、重绘与禁用。
- `WorkbenchDatePickerModel.js`使用工厂本地日期字符串和浏览器原生约束校验，不以UTC转换日期，不猜测未填的时间。保留原value attribute作为step基点；时间增减按钮与其他数字微调器一致。
- 所有资源本地交付，不新增目标运行时或依赖。编译使用Chrome109支持的对象展开，避免多个独立脚本生成同名Babel全局辅助函数。系统的文件打开/保存窗口继续由操作系统负责，页面内触发按钮及状态提示使用工作台样式。

## 验证边界

2026-09-12界面质量层补充：

- `navigation_metadata.py`提供导航分组/视图别名，`pages.py`下发`nav_groups/view_aliases/help_url`。菜单显示集合与15视图可达集合分别验证；帮助复用现有只读手册路由，壳层通过`WorkbenchNavigation.helpUrl`附加`src=当前视图URL`，手册页据此渲染返回链接。计划中心页签条由`WorkbenchNavigation.historyView`判定，在排产历史上下文中隐藏；报表/复盘页签切换（`preferSaved`）整体恢复目标页签自己保存的上下文（范围、主题、分页、选中、滚动），只有首次进入才沿用当前范围与返回来源；两个页签各自保留范围是验收锁定的既有设计。
- `app/styles/`按令牌、外壳、控件与领域样式显式排序发布。原型导入快照仍核对哈希，应用CSS同样登记来源/输入/发布字节。JSX不再通过runtime style块改变层叠顺序。
- `WorkbenchGuards`管理按owner登记的未保存内容和命令锁定；`WorkbenchGuardHost`单独负责共享Modal呈现，避免classic-script依赖环。导航、历史前进后退、编辑器关闭与外部离开遵守同一退出决定，拒绝时保留URL/页面/草稿。
- `WorkbenchListControls`区分页码与游标分页，档位由既有领域API决定；`WorkbenchDetailPanel`统一用户主动打开后的焦点与返回，自动预览不夺走首屏。共享Field负责字段说明与首错聚焦，错误编号保留在可展开的诊断区域。
- `WorkbenchFormat`区分工厂本地文本和带时区时刻，超大整数字符串单独无损分组；`WorkbenchTerms`统一同义业务术语。格式层不新增领域取值约束，不把未知补零。
- `WorkbenchDensity`只保存本机显示偏好。计划默认选择不覆盖明确来源，实际甘特显示窗口与服务器数据范围分离；报工继续操作只在原回执确认并取得新写入上下文后启动。
- 独立工作台截图/几何/交互工具通过daily gate显式参数运行；默认旧浏览器manual/CI政策保留。每份证据绑定实际源码与build_id，不借用旧截图为新版本作证。

前期专项测试及双尺寸双主题浏览器证据继续保留，当前最终全站逐动作验收仍在进行，不能将旧局部通过重记为最终快照通过。5000同资源工序、四个完整候选的正式隔离测量已通过，受理到终态122.728285375秒低于原180秒目标，重启后引用及结果相同；该证据只绑定当时冻结快照，不自动覆盖最终HEAD。

完整门禁仍为`scripts/run_quality_gate.py`。分批本地归档、最终干净检出完整门禁和旧UI退役由本轮继续完成，Win7打包、真机与最终发布排除。代码归档不是业务数据库备份；代码回退与新数据保全分别核对，不用旧库覆盖新增事实。最新状态见`../roadmap/workbench-prototype-migration/round2-progress-20260910.md`，退役矩阵在同目录`legacy-retirement/`，未应用的决定不作为已实现能力。
