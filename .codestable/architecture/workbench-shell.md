---
doc_type: architecture
slug: workbench-shell
scope: 工作台离线外壳、领域服务、受管运行及恢复边界
summary: 真实业务工作区已挂载，逐项终验与旧入口退役仍在收口
status: current
created: 2026-09-09
last_reviewed: 2026-09-10
tags: [workbench, flask, offline, win7]
depends_on: [ARCHITECTURE]
implements: [workbench-foundation-read-loop, workbench-production-workflows]
---

# 工作台迁移宿主

## 当前边界

`/workbench` 和 `/workbench/trial` 已挂载 14 个侧栏工作区及上下文内的交付风险视图。主数据、工艺、批次、候选生成和采用、正式计划、试调、执行台账、实际甘特、复盘报表、工时校准、值班台和系统维护均通过真实领域服务接线，不再是仅系统只读的初始阶段。本文件描述当前源码，不替代逐动作验收。旧默认入口和旧资产尚未退役；全站与容量终验通过后才执行退役。Win7 打包、真机和最终发布被本轮明确排除，不记为通过。

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

前期专项测试及双尺寸双主题浏览器证据继续保留，当前最终全站逐动作验收仍在进行，不能将旧局部通过重记为最终快照通过。5000同资源工序、四个完整候选的正式隔离测量已通过，受理到终态122.728285375秒低于原180秒目标，重启后引用及结果相同；该证据只绑定当时冻结快照，不自动覆盖最终HEAD。

完整门禁仍为`scripts/run_quality_gate.py`。分批本地归档、最终干净检出完整门禁和旧UI退役由本轮继续完成，Win7打包、真机与最终发布排除。代码归档不是业务数据库备份；代码回退与新数据保全分别核对，不用旧库覆盖新增事实。最新状态见`../roadmap/workbench-prototype-migration/round2-progress-20260910.md`，退役矩阵在同目录`legacy-retirement/`，未应用的决定不作为已实现能力。
