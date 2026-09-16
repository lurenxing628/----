---
doc_type: roadmap
slug: workbench-manual-remediation
status: active
review_status: approved
created: 2026-09-15
last_reviewed: 2026-09-16
tags: [workbench, manual-validation, process, scheduling, usability]
related_requirements: [workbench-production-workflows]
related_architecture: [workbench-shell]
---

# 工作台手动验证整改总方案

## 1. 结论与范围

本方案统一处理用户的 20 条浏览器批注和本轮手动测试发现的问题。先修复排产结果查询卡死，再统一控件、重排工艺和批次页面，同时补齐人员设备授权、旧工序外协登记、报工撤销和报表统计口径，最后重新做逐动作手动验收。

2026-09-15 用户已批准并行实施，并追加：所有页面的删除图标统一垃圾桶。实施状态以 items 清单为准，现有未提交改动保留；执行前差异与源码哈希已存入 execution-20260915/baseline.json 及 existing-worktree.diff。

本方案覆盖正常操作、错误提示、保存与刷新、重启和数据库恢复后的状态，以及可导出的真实文件。既包括纯视觉修复，也包括下文明确列出的业务合同变化。业务变化不能夹在 CSS 修改里交付。

范围边界：保持 Win7 x64、Python 3.8、Chrome 109、单机离线交付；不升级运行时，不引入在线图标或前端库。本方案不改变候选算法、正式采用的覆盖校验和已有计划/报工的保护规则，不把测试数据写回正式数据。Win7 真机打包和最终发布不在本次手动验收范围。

现有 [workbench-ui-refinement](../workbench-ui-refinement/workbench-ui-refinement-roadmap.md) 已完成其原有条目，而且明确排除了领域规则改动。本次作为新的整改路线图承接，不重写旧条目的完成记录，也不把旧验收当作本次通过证据。

## 2. 用户 20 条批注：逐项答案和处理

| 编号 | 核查结论 | 确定的方案 | 归属条目 |
|---|---|---|---|
| 1 | “收起范围”使用了图标库中没有的 chevron-up，所以出现空图标。 | 在现有本地图标库补齐展开/收起图标；图标和文字一起显示，状态与 aria-expanded 一致。 | wbfix-shared-controls |
| 2 | 齐套筛选的 label 和 select 没有内部对齐与间距规则。 | 搜索、齐套筛选、刷新组成统一工具栏；标签和输入框等高对齐，窄屏整组换行。 | wbfix-shared-controls |
| 3 | “历史遗留模板……”表示缺少新流程的确认记录，不代表已有路线、归属或工时必然无效。 | 删除列表中的常驻黄色说明，只显示当前需要做的事和具体缺项；旧确认记录放详情记录区。 | wbfix-process-flow |
| 4 | linkbtn 没有接入共用按钮的图标文字对齐规则。 | 操作列统一宽度，按钮使用 inline-flex；“确认路线”的图标、文字和同排按钮对齐。 | wbfix-shared-controls |
| 5 | 路线操作、工时文件操作、原始文本、解析状态和表格混在一个纵向区域。 | 工艺详情按“路线 → 归属 → 工时”分步展示；当前步骤只放相关操作，原始导入文本等移入详情折叠区，主体留给工序表。 | wbfix-process-flow |
| 6 | 搜索框 CSS 预留了图标位置，组件却没有渲染图标。 | 共用工序搜索组件补上搜索图标，修正输入内边距。 | wbfix-shared-controls |
| 7 | 可勾选的“已核对”和历史确认状态挤在同一格。 | 随第 8 条一起取消重复勾选；确认记录作为只读信息，与可编辑字段分开。 | wbfix-process-flow |
| 8 | 它实际是“勾选当前筛选页的全部有效工序”，不是第二人审批。保存却要求全部有效工序已勾选；工时页的逐行勾选还只是前端门槛。 | 去掉逐行核对、本页全选和全部核对。用户点“保存归属并继续”或“保存工时”就确认本次提交内容，服务端仍校验整份有效工序。搜索和翻页不改变保存范围。 | wbfix-process-flow |
| 9 | 与第 3 条相同，是重复的来源说明。 | 删除弹窗顶部常驻说明；只有实际阻止下一步的缺项才就地提示。 | wbfix-process-flow |
| 10 | “不反写”实际指：改工艺模板，不会自动改已经生成的批次工序。 | 改为“此工艺已用于 8 个批次。修改后，已有批次工序不会自动更新。”提供批次入口；能否更新由该批次的真实状态决定。数字按实际关联数显示。 | wbfix-process-flow |
| 11 | 自制工时、单道外协周期、合并外协组周期放在同一张错列的表内，还缺少列分隔。 | 分成“自制工时”和“外协周期”两区，保留工序号和路线顺序参照。各区用有竖向分隔的编辑表格；整组周期在组行填写一次，成员行清楚标注使用哪个组的周期。 | wbfix-process-flow |
| 12 | 0 有业务含义：加工时间按“换型工时 + 单件工时 × 数量”计算，单件为 0 就不会随数量增加时长。但当前复核框无条件常驻，且多次编辑会反复清除确认。 | 去掉常驻复核框。仅新填、改为或尚未确认的 0，在保存时列出对应工序和计算影响；“按 0 保存”直接完成本次保存。已有确认且内容没变的 0 不重复询问；空值不能当 0。 | wbfix-process-flow |
| 13 | 删除按钮用了 minus 图标，缺少可见文字。 | 所有可达页面的单行、批量、详情和确认弹窗删除统一为垃圾桶图标加“删除”文字，保留已有引用约束和删除影响确认。 | wbfix-shared-controls |
| 14 | 模板区的标题、开关、说明和按钮没有清楚的布局层次。 | 改为“从工艺模板更新工序”卡片：来源工艺、当前能否更新、具体缺项/限制、更新按钮分别成行。 | wbfix-batch-template |
| 15 | 基础信息用连续 span 拼接，备注和短字段互相挤占。 | 使用两至三列标签/值网格，备注独占一行；编辑按钮固定在标题行。 | wbfix-batch-template |
| 16 | 标题、返回、删除、长禁用原因塞进同一工具栏。 | 标题与操作分区；长原因移到独立状态行。示例：“已有排产或报工记录，暂不能删除或替换工序。”具体关联记录在详情展开。 | wbfix-batch-template |
| 17 | “存量模板”只是旧模板的内部分类，而且当前代码并未一概禁止使用这种模板。 | 展示“来源工艺：图号 · 名称”和真实完整程度；需要查看历史时再显示“暂无确认记录”。不把旧模板一律改称“不可用”。 | wbfix-batch-template |
| 18 | “资料不完整时停止刷新”确实是行为开关，默认不勾选时会允许复制不完整资料；更新还会重建工序并清掉原设备、人员指定。 | 删除开关，更新前统一检查必要资料，列出增删改和清除资源指定的影响，确认后整批更新。缺项直接指出工序及字段；有计划/报工的批次继续禁止替换。此项是业务规则调整。 | wbfix-batch-template |
| 19 | 开始按钮、长说明、刷新按钮、状态和技术编号混排，未查询时也可能显示查询文案。 | 按“状态 → 当前可做的操作 → 本次范围/进度 → 结果”重排。显示有文字的“查询结果”；技术编号默认折叠；不重复显示同一个原因。 | wbfix-run-panel |
| 20 | 不是仍在计算。该操作在测试备份中已经 complete；恢复测试前数据库后，当前库没有这条记录，浏览器却保留旧操作编号，前端反复查不到又无限重试。 | 增加数据库恢复后的旧请求识别；有证据确认来自恢复前的数据时结束旧查询并允许重新检查排产。无记录、查询失败、正在计算各用真实状态。不能用清空浏览器缓存或超时后自动重提来掩盖。 | wbfix-run-recovery |

第 20 条是上一轮恢复后漏验的状态联动。本方案将“恢复完成后回到原标签页继续操作”列为必验项，不能只核对数据库数量和启动成功。

## 3. 一并处理的其他发现

| 编号 | 事实与边界 | 方案 |
|---|---|---|
| B1 | 人员技能可编辑，但工作台“可操作设备”只读；旧入口又重定向到新页面。具备工种技能不等于获准操作所有设备。 | 在人员详情补齐“可操作设备”的增删改，复用现有 OperatorMachineService 和资格校验。保存后能用于排产资源选择。 |
| B2 | 当前 10 道外协工序都有现存批次关系，但旧工序的出生来源记录中 batch_ref 为空；登记入口据此全部禁用。 | 普通外协登记预览展示当前批次、图号、供应商和成员；一次“确认登记”同时记录本次核实的关系和外协事实。不给用户再加“确认旧数据”的独立步骤，不回填虚假的历史出生记录。 |
| B3 | 旧报表按任务起止的自然时长累计，并使用不同的容量分母；工作台按可工作区间计算，两者确实存在公式差异。不同窗口的 120% 与 115.8% 不能直接用来证明精确差额。 | 同一版本、时间窗口和资源统一计算口径。资源占用率按有效可工作区间中的占用并集/实际可用时长计算；重叠负荷和非工作时间安排另列，不能硬截成 100%。网页、CSV、XLSX 使用同一结果。 |
| B4 | 报工改为 0、清掉时间后仍存在报工事实。0 代表零产出，不代表这次报工从未发生；先前把“没有回待开工”直接归为缺陷不准确。 | 新增明确的“撤销这次报工”，追加撤销记录、保留原报工及原因，重新汇总有效事实。只有没有其他有效报工或历史开工事实时，才可能回到待开工。 |
| B5 | 浏览器点击过导出，但未核实下载事件和实际落盘文件；这不足以认定导出程序有 bug，也不足以认定成功。 | 做真实文件交付核验：响应、文件名、浏览器下载、实际路径、CSV 内容/XLSX 可打开及行数。查明是产品、浏览器宿主还是保存位置问题后定点修复。 |
| B6 | 空范围可进入预览，后端 no_eligible_tasks 在前端缺少对应消息，可能错误显示“结果不确定”，而预览根本没有执行排产。 | 空范围直接提示“请选择至少一个可排产批次”；无合格工序显示具体原因。预览失败与提交后结果未确认分开处理。 |

## 4. 模块职责与界面组织

| 模块 | 职责 | 实施入口 |
|---|---|---|
| 共用控件 | 统一图标、按钮、搜索、标签与表格容器，修复当前 DOM 和样式约定不一致。 | ResourceControls.jsx、ProcessStageEditor.jsx、styles/20-controls.css、styles/21-table-frame.css |
| 工艺编辑 | 三步编辑、保存即确认、条件性零值提示、自制和外协分别填写。 | ProcessDetail.jsx、ProcessSourceEditor.jsx、ProcessHoursEditor.jsx、process 工作流服务 |
| 批次详情 | 将基本信息、更新来源和真实限制分区，按统一完整性检查更新模板。 | BatchDetail.jsx、batch_operations.py、batch_template_validation.py |
| 排产状态 | 区分预览、受理、计算、查询与恢复后的旧请求，管理同一请求的生命周期。 | RunJobAPI.js、RunJobPanel.jsx、RunJobControls.jsx、run_jobs.py、system restore/journal |
| 人员设备关系 | 在工作台维护现有人员设备资格关系。 | ResourceForms.jsx、resource commands、OperatorMachineService |
| 外协来源 | 把当前关系核实纳入正常登记事务，保留历史来源原义。 | outsourcing_commands.py、workbench_outsourcing_source_repo.py、workbench_outsourcing_repo.py |
| 统计口径 | 报表与工作台共用同一资源可用/占用计算结果。 | report 服务、dashboard_resource_metrics.py、report_catalog.py |
| 报工事实 | 显式撤销单条报工，统一更新现场、复盘、报表和校准读取。 | execution 服务、报工输入协议、FieldDetail.jsx |
| 文件与验收 | 证明真实文件交付，逐动作验证整个业务闭环及恢复后继续使用。 | ReportAPI.js、文件导入导出服务、浏览器人工操作 |

### 工艺详情的目标布局

    工艺 · 图号 / 名称                             关闭
    [路线] → [归属] → [工时]
    当前步骤标题                         该步骤的导入 / 导出
    [搜索工序或工种]                  共 N 道有效工序
    主编辑表格（表头固定，操作列对齐，编辑列有竖向分隔）
    原始导入资料 / 确认记录（需要时展开）
    影响说明                                取消   保存并继续

工时步骤内分“自制工时”和“外协周期”两区，仍在同一个保存事务内。自制区只填换型/单件工时；外协区只填单道或整组周期。整组成员按组周期计算，不能伪装成每行都可编辑。发生校验错误时定位实际字段和所属分页，不能只在页脚报错。

### 批次详情与排产区的目标布局

    批次号 / 图号                          返回列表   删除批次
    数量 / 当前状态
    存在限制时：具体原因及查看记录入口
    基础信息                               编辑基础信息
    交期 / 优先级 / 齐套状态 / 齐套日期（字段网格）
    备注（整行）
    从工艺模板更新工序
    来源工艺 / 资料缺项或更新影响                 查看更新内容

    候选排产                               当前真实状态
    本次范围、时间窗口、可参与工序数
    当前可做的操作：检查并开始 / 查询结果 / 查看候选
    有任务时显示阶段、耗时和进度；无任务时显示具体原因
    排产结果列表
    详细记录（操作编号等，默认折叠）

## 5. 跨模块合同

以下是本轮批准的目标合同。2026-09-15已完成实现及相关专项，手动验收最后补齐独立试调方案的正向正式采用；具体实现、与方案的差异及覆盖边界以各修复记录和[执行盘点](execution-20260915/implementation-and-coverage.md)为准，不以目标合同本身代替实际证据。复用现有写入上下文、短引用、请求键和 SQLite 原子事务，不增加另一套命令系统。

### 5.1 控件与表格

纯视觉修复不改领域 API。共用 Button 使用图标加文字的固定间距和居中布局；linkbtn、mini 必须遵守同一规则。破坏性操作使用 trash 图标及可见“删除”文字。

共用表格采用现有样式能实际命中的结构：wb-table-frame 直接包含 table.wb-table，按需标记 sticky header/actions，去掉额外的嵌套滚动壳。编辑表加列分隔；只读总表不统一加重边框。工具栏标签不依赖全局裸 label 样式。图标来自本地注册表，测试必须检查实际 SVG 内容，而不只是存在一个 svg 节点。

保留键盘焦点、aria-label、aria-expanded、disabled 和错误关联；长禁用原因单独展示，不挤进按钮所在行。长表在一个明确区域内滚动，弹窗页脚始终可达。

### 5.2 保存与工艺确认

继续使用 process.source_confirm / process.hours_confirm，提交当前快照中的全部有效工序；服务端核对完整集合、归属、外协组和字段合法性。筛选只是显示，不能把未显示的行漏掉或偷偷覆盖其草稿。

source_confirm 现有每行 confirmed 字段若继续保留，由明确的整份保存动作提交 true，记录本次保存时的内容与确认时间；不能在仅打开页面、导入或迁移时生成确认记录。hours_confirm 不新增逐行已读字段。删除前端逐行/全选核对门槛，保留内容变化导致确认失效的现有校验。

零工时规则：

    unit_hours == null / 空字符串：缺项，不转换成 0
    unit_hours < 0 或非法数字：字段错误
    unit_hours == 0 且该内容未确认：保存前提示本工序的计算影响
    unit_hours == 0 且服务端确认记录与当前内容一致：不重复提示
    external_days / 组 total_days：按现有业务规则必须大于 0

现有 confirm_zero_unit_hours 继续表达本次明确按 0 保存；不把未确认的 0 自动带成 true。后端根据确认记录及内容匹配识别未改变的已确认零值；需要确认时返回 zero_unit_hours_confirmation_required 及受影响 operation_refs，由同一保存流程提供“按 0 保存”。适用范围必须包含工艺页面、工时导入和其他 stage 命令调用者，不能只改弹窗。

提示例：“工序 5 的单件工时为 0，排产只计算换型工时，数量增加不会增加加工时长。”用户点“按 0 保存”就是最终保存动作，不再追加勾选或第二个确认框。

### 5.3 批次从模板更新

保留现有 batch.sync_preview → batch.sync_confirm 的预览/确认流程。兼容保留 payload.strict_mode 字段时只接受 true；旧 false 请求明确返回 template_validation_required，不静默采用宽松行为。预览返回完整 before/after、字段缺项和资源指定变化，确认重新核对同一批次/模板快照并原子更新。

模板完整性检查统一覆盖：有效工序、有效工种与归属、供应商、自制换型/单件工时、外协单序或合并组周期。旧模板没有新确认记录不单独构成拒绝理由；新流程中的未完成步骤继续按工艺合同处理。使用同一标准生成列表状态、详情缺项和服务器拒绝原因，不能前端说可更新而后端只给笼统错误。

已有计划/报工的引用限制继续生效。预览必须明确更新会替换哪些工序、删除哪些旧工序、清除哪些设备/人员指定。校验失败不删原工序；预览后模板或批次变化则拒绝旧确认并要求重新查看变化。

### 5.4 排产查询与数据库恢复

增加服务器生成的不透明 data_context_ref，表示当前受控数据库数据代次。普通服务重启不改变它；受控恢复完成后改变它，由现有数据库外 system journal 持久保存并在重新开放写入前生效。恢复中断后的启动恢复必须保持相同判定，不能把恢复了一半当作完成。

跨前后端数据：

    PendingRunV2 = {schema_version: 2, input_ref, request_key, run_ref: null | ref, data_context_ref}
    RunPreview / RunAdmission / RunLookup：均返回 data_context_ref
    RunLookup.resolution = found | context_replaced | unresolved
    context_replaced：服务器已经证明请求属于恢复前的数据，当前库没有对应任务/回执

写入上下文绑定 data_context_ref，恢复前的预览令牌不能在恢复后受理。pending 不保存生产输入或 write_token。服务器先核对当前数据库中的原 request_key 和回执；找到了就展示当前真实结果，不能仅凭代次不同扔掉记录。

现有没有 data_context_ref 的旧 pending 必须有迁移路径：通过已完成的恢复 journal 及其登记的恢复前保护备份，对原 request_key 做限定范围的只读核对。本次已经通过备份证明的旧请求应得到 context_replaced；不接受浏览器自报备份路径，不扫描任意目录。没有可靠证据时返回 unresolved，不能猜测完成或允许自动重提。

UI 状态与动作：

| 状态 | 显示 | 允许的后续动作 |
|---|---|---|
| 尚未提交 / 预览被阻止 | 尚未开始，或具体缺项 | 修改范围、重新检查 |
| 正在请求查询接口 | 正在查询结果 | 显示实际请求状态 |
| 已受理 / 排队 / 计算中 | 真实阶段与进度 | 查询原请求、查看已有信息 |
| complete / partial / failed / interrupted | 对应终态 | 查看结果或原因；重新检查下一次排产 |
| unresolved | 暂未查到这次排产记录 | 查询原请求、查看排产记录；不自动重提 |
| 查询接口失败 | 查询失败及重试入口 | 重试同一请求 |
| context_replaced | 数据库已恢复，上次排产结果不在当前数据中 | 收起旧记录，重新检查排产 |

无记录/查询失败持续 60 秒后暂停自动重试，保留原编号并提供手动查询；已确认正在排队/计算的任务继续正常查询，不能套用 60 秒终止规则。只有接口请求真正进行时显示“正在查询”。计时耗尽从不证明“没有执行”，也不自动生成新请求。

正常终态或已证明 context_replaced 后，只解除对应的 pending；最近记录仍可查看。不能 localStorage.clear()，不能影响其他页面的待确认操作。恢复后核对其他共用待确认状态的适用性，但不顺手改写无关命令协议。

空范围和 no_eligible_tasks 有专用预览提示，预览失败不会进入“提交结果不确定”。保留多标签页防重复提交、请求幂等、受理后断网/刷新和后台暂停查询等既有合同。

### 5.5 人员可操作设备

人员详情 DTO 增加可编辑 machine_permissions，字段为 machine_ref、skill_level、is_primary，引用和枚举映射沿用现有服务。新增逻辑命令 operator.machine_permissions：输入该人员的目标关系集合，使用现有预览/确认上下文，展示新增、移除、等级和主操设备变化。

确认时复用 OperatorMachineService 的 add_link / update_link_fields / remove_link，在同一事务核对人员、设备与已有关系。技能列表与设备关系独立保存；编辑姓名或技能不能清空关系，新增技能不能自动授权所有同工种设备。排产资格读取现有 OperatorQualificationService，不新增旁路名单。

### 5.6 旧工序外协登记

保留现有外协 target 的 kind、batch_ref、supplier_ref、operation_refs 四字段；新增只读投影：

    source_resolution = {basis: birth_record | current_relation | registration_confirmation,
                         confirmation_ref: null | fact_ref}
    part = {ref, business_code, label}

优先验证已有出生来源；没有出生来源时验证先前的登记确认；两者都没有时，只有当前工序与批次、零件、供应商的关系完整、唯一且未登记，才允许正常预览。用户“确认登记”在同一个现有命令事务内复验关系、写入外协登记和成员、追加事实，并写入本次核实的来源绑定。

拟新增追加表 WorkbenchOutsourcingSourceConfirmations：operation_ref 唯一、batch_ref、fact_ref（关联首次外协事实）。时间、操作者、原因和完整快照复用该事实，不编造旧 created 事件，不修改旧 WorkbenchOutsourcingOperationOrigins 的空值。

批次与成员身份使用稳定引用。source_resolution.basis 是核实方式，不能放入会随首次登记改变的 source.identity；否则刚登记完就会误报 identity_drift。合并组所有成员一并校验和写入；预览后换批次/供应商、成员变化或重复登记都整单拒绝。普通新工序不增加额外点击。

### 5.7 资源统计统一口径

由共享统计服务提供以下结果，工作台和报表适配同一结果：

    ResourceUtilizationQuery = {plan_ref, source: planned | actual, window_start, window_end,
                                resource_kind, resource_refs}
    ResourceUtilizationRow = {resource_ref, available_hours, occupied_hours,
                              utilization_ratio: number | null, summed_load_hours,
                              overlap_hours, outside_calendar_hours, metric_version}

时间窗口统一使用工厂本地时间的左闭右开区间。available_hours 是该资源实际日历减去停机/不可用区间后的时长；occupied_hours 是选定来源的任务区间与可用区间相交后取并集的时长。utilization_ratio = occupied_hours / available_hours；可用时长为 0 时返回 null 和具体说明。

summed_load_hours 保留相交后的逐任务累计时长；overlap_hours 表达累计与并集的差；outside_calendar_hours 按窗口内任务区间并集减去可用区间后的时长计算，避免重叠任务重复计数。非工作时间安排单列，不靠截断比例掩盖。效率影响的标准/有效加工小时不能冒充时间轴占用小时。实际数据缺失不从计划补齐。

日报峰值与整窗占用率是不同指标，标题明确区分。导出固定同一 plan_ref、来源、窗口和筛选条件并输出 metric_version；报表内使用共同分母和数值格式，不能再由旧 ReportEngine 私下重算另一口径。

### 5.8 报工撤销

新增逻辑动作 execution.report_void，继续使用原报工的预览/确认事务与幂等请求键：

    Input = {report_ref, original_revision_ref, reason, declared_operator}
    Preview = {target_report, before, after, downstream_impacts, write_context}
    Receipt = {report_ref, void_fact_ref, state: voided, refresh_required: true}

追加撤销事实，保留原报工、各次更正、原因与操作者；不物理删除，不将数量统一改成 0。对同一已撤销目标再次提交不重复扣减；待撤销版本变化返回 context_stale。已有下游开工/完工或其他事实依赖时，预览说明具体关联并按执行约束拒绝，不能仅改列表显示。

统一的有效事实投影供现场进度、实际甘特、剩余计划量、复盘、报表、风险和工时校准消费。撤销一条不撤销同工序的其他报工；零产出但实际做过的报工仍有效。仅当全部有效事实都支持“未开始”时才显示待开工；已有历史实际开工不能被抹掉。

### 5.9 导出交付

复用现有导出请求和文件格式合同。一次导出的过滤条件、数据版本、列和行数必须一致。页面可在真实创建下载请求后显示“已交给浏览器下载：文件名”，不能在没有文件证据时称“已保存到本机”。失败时显示可操作的具体原因。

文件验收记录：请求范围、响应状态、Content-Type、文件名、字节数、浏览器下载结果、实际文件路径、CSV 解析/XLSX 打开结果以及数据行数。下载被宿主拦截与服务端生成失败分别报告；前者不能通过伪造下载成功提示处理。

## 6. 子任务与推进顺序

机器清单见 [workbench-manual-remediation-items.yaml](workbench-manual-remediation-items.yaml)。用户已授权下列条目并行推进，实时状态见机器清单；未通过验收不得标记完成。

| 条目 | 交付内容 | 依赖及原因 |
|---|---|---|
| wbfix-run-recovery | 修复恢复后的排产旧请求、无记录无限查询和空范围提示；最小闭环。 | 无；可单独演示恢复后旧标签页继续正常使用。 |
| wbfix-shared-controls | 共用图标、按钮、搜索、筛选、表格容器与竖向分隔规则。 | 无。 |
| wbfix-process-flow | 工艺三步重排、保存即确认、条件性零工时提示。 | shared-controls 提供统一编辑表和操作控件。 |
| wbfix-batch-template | 批次布局与从模板更新的固定完整性校验。 | shared-controls 提供布局控件；process-flow 提供一致的完整性和确认语义。 |
| wbfix-run-panel | 排产区布局、状态呈现和结果操作。 | run-recovery 提供真实状态；shared-controls 提供统一控件。 |
| wbfix-operator-machine | 人员可操作设备增删改及排产资格闭环。 | shared-controls 提供关系编辑控件。 |
| wbfix-outsourcing-existing-source | 旧工序在正常登记时核实当前来源。 | 无；复用现有外协登记事务。 |
| wbfix-utilization | 统一工作台与报表资源统计公式及导出数值。 | 无。 |
| wbfix-report-void | 显式撤销单次报工并更新各事实读取方。 | 无。 |
| wbfix-export-delivery | 定位并修复实际下载交付障碍，完成文件证据。 | 无；最终数值一致性在最终验收与 utilization 合并核对。 |
| wbfix-manual-acceptance | 全部动作、20 个批注、高压排产、保存/刷新/恢复、文件完整验收。 | 依赖上述全部条目，验证组合后的最终版本。 |

建议顺序：先 run-recovery 消除当前阻塞；随后 shared-controls，再工艺、批次、排产三个重点页面；其余业务缺口按表中依赖实施，最后统一验收。这是技术与风险驱动的建议顺序，不是已承诺的工期，也不表示独立条目之间存在硬依赖。

最小闭环：同一浏览器完成排产 → 恢复测试前备份 → 重启服务 → 原标签页明确显示旧结果已不在当前数据 → 能重新检查并开始一次新排产。过程中旧任务不能被自动再次提交。

## 7. 验收标准

### 7.1 有针对性的程序验证

- 排产：扩展 run_job_widgets_probe.cjs、final_planning_run_actions.cjs 及对应服务测试，覆盖有/无任务回执、受理响应丢失、正常重启、受控恢复、旧 pending 迁移、两个标签页、查询 404/断网、空范围、长时间真实计算；验证没有自动重复受理。
- 工艺：覆盖筛选/分页后保存全部工序、未变已确认 0、新 0、空值、负数、外协合并组、过期快照、导入后保存；确认只是减少点击，没有跳过字段和完整集合校验。延伸现有 test_process_stage_commands.py、test_process_stage_api.py 和 widgets/browser 用例。
- 批次：更新 test_batch_actions.py 中宽松复制旧模板的旧预期；覆盖必要字段缺失、有计划/报工、资源指定清除预览、过期确认、原子失败不删数据。
- 人员设备：新增人员→工种技能→设备授权→排产资格；移除授权影响后续新指定但不篡改原计划，编辑其他字段不丢关系。
- 外协：10 道现存旧工序、普通新工序、单序和合并组、预览后关系变化、同键重试、失败无半写入；旧来源空值和旧事件保持不变。
- 报表：跨夜、周末、个人日历、停机、不同效率、重叠任务、零容量、窗口端点，同版本同窗口网页/CSV/XLSX 数值一致。替换与新口径冲突的旧测试预期，并记录其合同变化。
- 报工：撤销一条/多条之一、重复撤销、原版本变化、下游依赖、真实零产出、旧实际开始，以及现场/复盘/风险/校准等全部投影一致。

纯 CSS 小改不编造重复实现的测试；使用实际截图和必要的几何断言验证。影响业务合同的修改必须有行为测试。

### 7.2 手动逐动作与视觉验收

最终验收的业务操作全部通过浏览器点击、填写、选择、导入和下载进行，不用 API 或脚本造出“手动通过”结果。自动测试只作补充。现有 [逐动作清单](../workbench-prototype-migration/acceptance-master/actions.json) 用作起始覆盖表，按当前实际可见功能补齐新增动作和调整后的路径；历史能力族数量不代表原子动作数量。

必须走完现有 12 个入口及其页签、弹窗和动作：值班台、基础资料、资料总览、批次管理、执行排产、选择排产方案、试调排产方案、现场记录、现场实际甘特、报表中心、工时定额校准、系统管理。计划甘特/交付风险/执行复盘虽已合并入口，仍分别核对其功能。

每个动作记录：入口、前置条件、输入、预期、实际结果、证据、通过/失败/被阻断/未验证。保存类动作回读并刷新验证；删除类先查看引用约束；取消、关闭、重新进入和草稿保留也要覆盖。不能用页面可打开代替功能通过，不能用另一条动作通过覆盖本动作失败。

视觉基准：用户的 1392×924，以及 1366×768、1280×720；浅/深主题各验。检查 20 个对应位置，长编号、长备注、自制/外协混合、合并外协组、50 道以上工序的分页与滚动。按钮不裁字、不用空 SVG；标签与输入对齐；编辑表格列分隔清楚；底部保存始终能到达；禁用原因能读懂且不挤坏操作列。

高压业务场景：保留紧交期、资源满负荷、1000 件大批量、自制/外协衔接、齐套不足、停机/休息日、资源资格不匹配。分别验证紧窗口产生部分结果和放宽窗口完成；候选比较、试调、正式采用（在隔离测试副本中）、报工、外协、风险和导出走完。时间记录使用实际数据规模、硬件和结果，不沿用上轮 1–2 秒作为性能承诺。UI 高压业务验证不等于大规模算法性能压测。

工时校准准备满足页面样本规则的真实手工测试记录，验证“样本不足”和“有有效建议”两条路径。导入验证有效文件、旧表头/错误值提示和失败整批回滚。备份验证实际文件、恢复、重启以及原标签页的排产/编辑/待确认状态。

### 7.3 数据保留和最终证据

高压和撤销/删除验证优先使用完整复制的隔离测试库与独立实例，不对用户现有正式批次做破坏性验证。现有备份和未提交改动保留。需要核查恢复行为时只恢复测试实例，并检查所有仍开着的相关标签页。

记录测试前后业务数量、正式版本、计划任务、报工与外协事实和资源关系；保留测试结果快照及关联请求号。数据清理不能用物理删除事实或清浏览器全部状态来制造“干净”。

完成实现后从 frontend/workbench/app 修改并运行 scripts/workbench/build.py 更新生成资源；static/workbench 不是手工修复源。按用户最新明确要求，严禁运行全门禁；仅执行受影响的专项测试、构建检查与手动浏览器验证，不启动 run_quality_gate 的任何模式，也不启动整仓测试。现有工作区含大量未提交改动，测试结论只绑定实际运行快照；只有最终 HEAD 的干净检出完整门禁满足时，才可声称 clean-worktree proof。

手动验收结果逐项记录。各实施条目已闭环，手动总验收最后补齐独立试调方案的正向正式采用，成功通知前不标完成。没有穷尽所有文件格式、参数、跨页和跨恢复组合，不把组件专项冒充逐项手动，不声称新版本全门禁通过。

## 8. 证据与现状冲突

### 8.1 排产查询卡死的实证

用户截图中的 request_key：run-86a45790db230dc6e7bf182e88df2830e20f9b3ad4795de1。

2026-09-15 使用 SQLite mode=ro，按相同 request_key 查 WorkbenchRunJobs 与 scheduling.run 的 WorkbenchCommandReceipts：

| 文件 | 匹配任务 | 匹配受理回执 | 全库排产任务数 |
|---|---|---|---|
| db/aps.db | 无 | 0 | 0 |
| backups/aps_backup_20260915_183234_manual_5aec6fc5e1a9.db | 无 | 0 | 0 |
| backups/aps_backup_20260915_190832_manual_d3db108700fc.db | complete / finished | 1 | 3 |

备份中的 run_ref 为 eac2da8e97c8e738627f2dad99cea26710f7100ccad5de2f。此证据证明该次排产已完成且不在恢复后的当前库中，不代表其他未知请求也可直接清除。

源码对应：RunJobPanel.jsx:46 在 found=false 后只显示待查询并 return；finally 继续安排查询；RunJobAPI.js:226 限制重试间隔而不限制无记录重试；RunJobControls.jsx:90 的无 run 呈现没有区分上述原因。run_jobs.py:125 的 lookup 在任务和回执都不存在时返回空结果。

### 8.2 可复查源码位置

以下均为本轮读取的工作区源码位置，行号会随实施变化；frontend 相对路径均位于 frontend/workbench/app/。

| 证据 | 文件与行号 |
|---|---|
| 收起图标请求与图标缺项 | PreflightWorkspace.jsx:80；ResourceControls.jsx:5；frontend/workbench/prototype/ui_kits/workbench/AppShell.jsx:4 |
| 筛选与 linkbtn/删除控件 | PreflightBatchPicker.jsx:53；ProcessWorkspace.jsx:58；styles/20-controls.css:31 |
| 搜索缺图标、表格容器规则 | ProcessStageEditor.jsx:55；styles/20-controls.css:175；styles/21-table-frame.css:9 |
| 路线弹窗结构 | ProcessDetail.jsx:26；styles/32-process-trial.css:13 |
| 归属核对/工时核对与零值框 | ProcessSourceEditor.jsx:105；ProcessHoursEditor.jsx:35、55、93；core/models/workbench_process_commands.py:56、72 |
| 旧模板提示、就绪例外和变化失效 | core/services/workbench/process_projection.py:36；core/services/process/workflow_state.py:151、224、341 |
| 工时计算含数量的公式 | core/algorithm_runtime/internal_slot.py:68 |
| 批次宽松开关与重建工序 | BatchDetail.jsx:9、24；core/services/workbench/batch_operations.py:38、58；tests/workbench/test_batch_actions.py:83 |
| 模板变更不改已有批次的合同 | tests/workbench/test_process_stage_api.py:125 |
| 排产无记录与预览消息映射 | RunJobPanel.jsx:46、77；RunJobAPI.js:123；core/services/workbench/preflight_result.py:27 |
| 数据库外恢复 journal | web/bootstrap/workbench_system_restore_recovery.py:14；web/bootstrap/workbench_system_restore.py:201 |
| 人员设备关系缺入口/已有服务 | ResourceForms.jsx:23；core/services/workbench/resource_projection.py:75；web/routes/personnel_pages.py:263 |
| 外协旧来源缺失与现有原子写入 | core/infrastructure/workbench_outsourcing_schema.py:112；data/repositories/workbench_outsourcing_source_repo.py:38；core/services/workbench/outsourcing_commands.py:21；data/repositories/workbench_outsourcing_repo.py:60 |
| 报表自然时长与工作台占用口径 | core/services/report/utilization.py:44；core/services/report/report_engine.py:386；core/services/workbench/dashboard_resource_metrics.py:49 |
| 报工仍存在即有执行事实、没有撤销输入 | core/services/execution/projection.py:29；core/models/workbench_execution_input.py:90；FieldDetail.jsx:72 |
| 导出触发不等于实际落盘证明 | ReportAPI.js:81；tests/workbench/test_report_export.py:13 |

### 8.3 需要随着实现更新的现状合同

- 工艺：现状资料写“三步确认”，本方案保留步骤与内容确认，删除额外逐行勾选，需同步用户指南和相关测试。
- 批次：旧测试允许 strict_mode=false 复制缺项模板，本方案改为更新必查完整性；这是明确的行为变化，需在该条设计/验收中记录，不用纯文案变更带过。
- 报表：旧日历容量测试含忽略个人日历的预期，须随统一公式调整。旧数值不再是新口径验收基线。
- 外协与报工：增加新的当前确认事实/撤销事实，须提供 schema 兼容、事务失败回滚和数据保留证据；不重写旧事件含义。
- requirements/architecture 已于执行阶段同步有源码和专项证据的合同；手动未验证内容仍明确保留。旧路线图完成记录保持原样，不重写历史验收为本轮通过。

## 9. 方案自查

- 20 条用户批注逐项给出答案与实施归属，B1–B6 覆盖其他已发现问题；导出保留证据不足边界，报工 0 的判断已纠正。
- 模块职责、跨模块字段、行为变化、数据保留、最小闭环和最终手动验证均已列出。
- items 使用独立条目及明确前置原因，不把建议排序伪装成技术依赖；只有一条最小闭环。
- 初始方案校验通过：主文档 frontmatter 必填项、items YAML、11 条唯一任务、无环依赖、唯一最小闭环、20 条批注完整覆盖、文件内本地链接存在、无同名 feature 冲突；当时所有条目为 planned。这些是历史方案校验，不能代替产品测试；执行状态以当前 items 和执行盘点为准。

## 10. 执行更新

- 2026-09-15：用户批准并行推进，删除图标扩大到全站可达页面；关闭、取消、减少数量和解除关联保留各自语义，不当作删除。
- 初次下载复核：浏览器手动点击 CSV 和 XLSX，响应 200，实际文件均已在 Downloads；XLSX ZIP CRC 通过，18行/11个业务列与CSV逐格一致，元数据一致；发现CSV全局说明与行级缺口同名，已更名并增加回归测试。证据见 execution-20260915/download-initial.json；最终组合版本仍需复验。

- 2026-09-15 执行中用户追加硬约束：严禁跑全门禁。此前仅查看过 --help，未启动全门禁；后续仅本轮专项、构建、手动浏览器验证。此约束覆盖旧文档中的门禁收口建议。
- 22:44收口：10个实施条目已按源码、定向专项和对应真实手动证据标completed；总手动验收继续in-progress，等待其余资源/批次原文件回导轨完成。已完成74道正式采用v15、5条完工样本校准0.05→0.09并锁定模板v2（旧5工序仍0.05）、单道/两道合并外协、报工更正撤销/实际甘特、真实试调时间调整、恢复后原标签新排产、路线/工时XLSX往返和物料原文件回导、工作日历及设备组/两日跨夜班次CRUD。新发现的候选三根因、参考列、现场任务定位及资源父上下文均已修并有相应定向和手动记录。[执行盘点](execution-20260915/implementation-and-coverage.md)继续区分实际覆盖与未穷举范围。
- 最终构建`270587be0986ef9c91d207907ef4f05e6045b23240d1c44103c33e417deb68c7`的355输入hash一致，导航92/92通过；5000最终后端/前端激活及旧数据保留有独立记录。未跑全门禁是已履行的用户约束，不是待整改项，未提交工作区不声称clean-worktree proof。
- 最终收口：五类资源11条及23批次原XLSX回导完成，批次九列业务内容一致、66道工序hash不变，updated_at正常变化；追加51道工艺在第2页完成三阶段整份保存，862窄窗口滚动/页脚可达；1392/1024正式页面浅深色回看和处置跟进→关闭→独立重开→刷新三条历史已落盘。11条items均completed；未穷举组合保留为覆盖边界，不将已完成动作留作待办。最终工作区增量见execution-20260915/final-worktree-incremental.json，HEAD未变、代码未提交。
- 完成状态更正：独立试调方案的正向正式采用此前没有手动成功记录，不能以候选采用v15代替。主代理已安排在5005从完整当前正式v15创建并保存试调，再正向采用；`wbfix-manual-acceptance`回到in-progress，其他10个已完成实施项保持。前一条“11条完成”为当时提前收口记录，本更正优先，待实际成功后更新。
- 12入口覆盖更正：原actions.json实际只展开基础资料/批次58族599动作，不是全部功能分母。仅核对当前live入口和本轮记录后，额外缺正向证据归并为[7个功能组](execution-20260915/remaining-manual-functional-groups.md)，不将库存调整、现场导入、批量维护、系统配置及独立结果交付冒充已经测过。总验收依这些组合动作收口，已完成主线不重跑，不扩成参数/格式穷举。
- 2026-09-16接续：G3库存、G4批次批改/直接工序维护/删除、G5资源与工艺批删、G7总览下钻及独立结果导出已全部实际闭环，G1临时草稿放弃也已刷新核对。G2有效报工文件导入及G6系统配置/日志交付已收到成功回报，等代理详细归档；5002备份`aps_backup_20260915_231723_manual_d6ade12f3efb.db`按用户明确要求保留，删除未执行、不再算阻塞或再次询问。
- 补验实际发现的试调响应级别、真实执行固定、日志自写快照、物料本地时间、总览指引、三处负荷分子及矮屏报工弹窗问题均有独立修复记录/定向证据。`270587be…`和23:01环境收口是历史阶段，后续页面已加载`b71675b…`；总验收继续等5005试调正向采用及最新5000激活/数据保留证明，不提前关闭。
