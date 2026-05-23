---
doc_type: audit-index
slug: aps-market-gap
status: current
created: 2026-05-23
tags:
  - aps
  - market-research
  - gap-analysis
  - exa
  - subagent
scope: "主流 APS 软件能力与当前项目差距对比"
---

# 主流 APS 软件能力与当前项目差距对比

## 1. 本次审计怎么做的

本次审计的目标不是只看广告词，而是把市面上常见 APS 软件的能力拆开，再和当前项目已经落地的能力逐项对比。

执行方式如下：

- 主代理启动 16 个 Sub Agent 并行调研。
- 每个 Sub Agent 都被明确要求使用 Exa MCP 查资料。
- Sub Agent 覆盖 Siemens、DELMIA Ortems、Asprova、PlanetTogether、SAP、Oracle、Kinaxis、Blue Yonder、OMP、o9、IFS、Infor、Epicor、Microsoft Dynamics 365、QAD 以及横向能力框架。
- 主代理再回到当前仓库读取 `.codestable/` 文档、说明书、调度算法、甘特图、排程入口、报表、模拟调整和发布服务代码，做本地能力核对。
- 本报告只新增审计文档，不修改业务代码。

工作区状态说明：

- 开始审计前，仓库里已经有多处未提交修改。
- 本报告只把市场调研和差距分析落在 `.codestable/audits/2026-05-23-aps-market-gap/index.md`。
- 其他已经存在的代码改动没有被本次审计回退或清理。

## 2. 市面上主流 APS 软件通常在做什么

把 16 个 Sub Agent 查到的信息合并后，主流 APS 软件大体分三层。

### 2.1 基础 APS 能力

这类能力决定一个系统是不是“像 APS”，而不只是一个表格工具。

- 工单、批次、订单、工序、工艺路线、设备、人员、班次、日历等基础资料维护。
- 按设备、人员、班次、交期、工序先后顺序做排程。
- 有限产能，也就是同一时间同一台设备或同一个人不能被重复占用。
- 甘特图展示排程结果，让计划员能看到每个任务被排到了哪里。
- 交期延误、设备负荷、人员负荷、瓶颈资源等基本分析。
- Excel、ERP 或 MRP 数据导入导出。
- 排程结果可以生成周计划、派工表、报表或历史版本。

### 2.2 成熟 APS 能力

这类能力决定系统能不能真的支撑日常计划员工作，而不是只能演示。

- 多约束同时考虑，比如设备、人员、模具、刀具、物料、换型、维护停机、外协、冻结窗口等。
- 可替代设备、可替代人员、可替代工艺路线。
- 物料可用性检查，包括库存、采购到货时间、缺料提示、订单和物料之间的追溯关系。
- 拖拽甘特图调整计划，并且调整后能检查冲突、保存草稿、生成方案、正式发布。
- 多方案对比，比如方案 A 交期更好，方案 B 换型更少，方案 C 设备更均衡。
- 瓶颈分析和原因解释，比如告诉计划员“为什么这个批次晚了”“卡在哪台设备/哪个人/哪个物料”。
- 与 ERP、MES、WMS、PLM 或其他系统集成。
- 多人协同、权限、审批、锁定、操作记录。
- 车间执行反馈，比如任务开始、暂停、完成、实际工时回写。

### 2.3 高阶 APS 能力

这类能力一般出现在头部企业套件或行业成熟产品中。

- 供应链层面的 S&OP、主生产计划、库存计划、采购计划、订单承诺。
- 多工厂、多仓库、多供应商的网络计划。
- AI 辅助排程、自动解释、自动生成调整建议。
- 数字孪生、快速仿真、实时重排。
- 设备数据或 IoT 数据接入。
- 能耗、碳排、成本、利润等高级目标。
- 行业专用模板，比如半导体、汽车、制药、食品、重工、流程制造等。

## 3. Sub Agent 调研到的产品能力汇总

评分说明：

- `强`：公开资料里能看到比较明确、成熟的产品能力。
- `中`：能看到能力，但边界、深度或用户体验没有完全展开。
- `弱`：资料里只有少量相关能力，或更偏旁路能力。
- `无明确证据`：本轮没有查到足够证据，不能硬说有。

| 产品 | 核心定位 | 排程约束 | 物料/库存 | 甘特图/手动调整 | What-if/多方案 | 集成/协同 | 本轮结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Siemens Opcenter APS / Preactor | 经典 APS，覆盖计划和详细排程 | 强 | 强 | 强 | 强 | 强 | 头部参照物，能力覆盖很完整 |
| DELMIA Ortems | 制造排程和生产计划 | 强 | 中到强 | 中到强 | 强 | 强 | 在复杂制造、协同和计划层面成熟 |
| Asprova APS | 以高速排程和工厂约束见长 | 强 | 强 | 强 | 强 | 强 | 很适合作为单厂详细排程标杆 |
| PlanetTogether APS | ERP 外挂式 APS，强调拖拽和集成 | 强 | 中到强 | 强 | 强 | 强 | 很重视计划员交互体验 |
| SAP PP/DS + IBP | SAP 体系内计划和详细排程 | 强 | 强 | 强 | 强 | 强 | 企业套件级别，集成能力非常重 |
| Oracle Fusion Cloud Production Scheduling | Oracle 云制造排程 | 强 | 强 | 强 | 强 | 强 | APS 能力集中在 Production Scheduling |
| Kinaxis Maestro / RapidResponse | 供应链计划和响应 | 中到强 | 强 | 中 | 强 | 强 | 更偏供应链快速响应和协同计划 |
| Blue Yonder | 供应链计划和生产排程套件 | 强 | 强 | 强 | 强 | 强 | 套件能力很完整，偏企业级 |
| OMP Unison Planning | 供应链和生产计划平台 | 强 | 强 | 中到强 | 强 | 强 | 流程制造和复杂供应链能力明显 |
| o9 Digital Brain | 企业计划平台 | 中到强 | 强 | 中 | 强 | 强 | 更偏计划平台、仿真和经营协同 |
| IFS Cloud Manufacturing/MSO | ERP 内置制造优化排程 | 中到强 | 中 | 强 | 中 | 中到强 | ERP 内排程能力较完整 |
| Infor SyteLine / CloudSuite APS | ERP 内置 APS | 强 | 中到强 | 强 | 中到强 | 中 | 中小制造 ERP 场景成熟 |
| Epicor Kinetic APS | ERP 内置 APS | 中到强 | 中 | 中 | 中 | 中 | 更像 ERP 生产排程增强模块 |
| Microsoft Dynamics 365 SCM | 供应链和生产计划 | 中 | 中到强 | 中 | 中 | 强 | ERP 计划能力强，专门 APS 深度不如头部 APS |
| QAD Adaptive ERP / Advanced Scheduling | 汽车等制造业 ERP/排程 | 强 | 中到强 | 强 | 强 | 中到强 | 行业制造约束和排程体验较强 |

## 4. 当前项目已经具备的能力

当前项目不是一个空壳。按代码和文档核对，它已经有一套面向 Win7 离线场景的本地 APS 基础能力。

### 4.1 已经比较扎实的部分

- 有明确的本地离线定位：
  - 面向 Win7 x64。
  - 目标机不要求安装 Python。
  - 依赖 Excel、本地页面和本地静态资源。
  - 这和云端企业 APS 的方向不同，是一个有意选择的边界。
- 有较完整的基础资料链：
  - 人员。
  - 设备。
  - 工序类型。
  - 供应商。
  - 零件工艺路线。
  - 批次。
  - 批次工序。
  - 工作日历。
  - 人员日历。
  - 设备和人员的绑定关系。
  - Excel 模板导入导出。
- 有可运行的核心排程：
  - 支持批次工序先后顺序。
  - 支持设备占用。
  - 支持人员占用。
  - 支持内制和外协工序。
  - 支持设备停机。
  - 支持工作日历。
  - 支持冻结窗口。
  - 支持准备状态和准备日期。
  - 支持自动分配设备和人员。
  - 支持优先级、交期、加权、先进先出等策略。
  - 支持 slack、critical ratio、ATC 等派工规则。
- 有一部分优化和候选方案能力：
  - 支持 OR-Tools warm-start。
  - 支持多次尝试和局部搜索。
  - 支持图分析模式。
  - 支持关键链相关分析。
  - 支持 3/5/7 个候选方案比较。
- 有甘特图结果查看：
  - 支持多种缩放粒度。
  - 支持按批次、设备、颜色模式筛选。
  - 支持交期延误、外协、关键任务高亮。
  - 支持关系线展示。
  - 支持场景预览标识。
- 有周计划、资源派工、报表和历史：
  - 支持周计划。
  - 支持资源派工视图。
  - 支持延误报表。
  - 支持利用率报表。
  - 支持停机影响报表。
  - 支持排程历史和版本。
- 有甘特图调整后端雏形：
  - 能创建调整草稿。
  - 能记录时间和资源调整。
  - 能校验设备/人员冲突、工序先后、日历、停机、交期、物料准备。
  - 能保存场景。
  - 能预览场景。
  - 能发布为新的正式排程版本。

### 4.2 现在还偏弱的部分

- 甘特图目前主要还是“看结果”，不是完整“拖拽改计划”：
  - 页面上“模拟调整”按钮仍是禁用状态。
  - 后端草稿、校验、保存、发布已经有了，但用户在页面上还不能完整操作。
- 物料能力还不是成熟 APS 里的“物料计划”：
  - 当前更像准备状态、准备日期和物料提醒。
  - 还没有完整 BOM 展开。
  - 还没有库存扣减和库存预测。
  - 还没有采购订单到货时间和缺料追踪。
  - 还没有订单和物料之间的清晰追溯。
- 多方案对比还不够计划员友好：
  - 算法里有候选方案和优化。
  - 但页面上还缺少一个清楚的“方案 A / B / C 对比看板”。
  - 计划员不容易直接看懂为什么系统选了这个方案。
- 报表已经有基础，但还不够“诊断型”：
  - 有延误、利用率、停机影响。
  - 但还缺少“为什么晚了”“卡在哪里”“怎么改会更好”的解释层。
- 执行闭环还比较弱：
  - 有周计划和资源派工导出。
  - 但没有车间实际开工、完工、暂停、异常反馈。
  - 没有把实际执行结果回写后再重排的闭环。
- 集成能力弱：
  - Excel 链路适合本地离线交付。
  - 但和 ERP、MES、WMS、PLM、设备数据系统相比，集成能力差距明显。
- 协同和权限弱：
  - 当前更像单机或小范围共享使用。
  - 没有完整登录、角色权限、多人锁定、审批流、评论协同。
- 多工厂和供应链计划基本不在当前范围：
  - 当前项目更像单厂本地详细排程。
  - 和 SAP IBP、Kinaxis、Blue Yonder、o9、OMP 这种供应链计划平台不是同一层级。

## 5. 当前项目和主流 APS 的逐项评分

评分口径：

- `0`：基本没有。
- `1`：有雏形，能看到方向，但还不足以支撑稳定日常使用。
- `2`：已经能支撑一个具体场景的日常使用，但还不够成熟。
- `3`：接近成熟商业 APS 的水平。

| 能力项 | 当前评分 | 市场成熟水平 | 差距判断 | 大白话解释 |
| --- | ---: | ---: | --- | --- |
| 基础资料和 Excel 导入导出 | 2.2 | 3.0 | 中等差距 | 当前已经能把人、设备、工艺、批次、日历这些资料串起来，适合本地离线使用；差在企业系统级主数据治理、权限、版本和跨系统同步。 |
| 有限产能排程 | 2.0 | 3.0 | 中等差距 | 已经能避免设备和人员同一时间重复占用，也能考虑日历、停机、外协、工序先后；差在模具、刀具、物料、替代路线、复杂换型矩阵等更多约束。 |
| 排程策略和优化 | 2.0 | 3.0 | 中等差距 | 当前不只是简单排序，已经有多策略、派工规则、OR-Tools、候选方案；差在用户可解释性、稳定的多目标优化和成熟方案对比体验。 |
| 甘特图查看 | 2.0 | 3.0 | 中等差距 | 看结果这块已经比较像样，有缩放、筛选、高亮、关系线；差在成熟产品常见的拖拽、锁定、批量调整、冲突提示和一键发布。 |
| 甘特图手动调整 | 1.3 | 3.0 | 大差距 | 后端草稿、校验、保存、发布已经有骨架，但页面入口还没真正开放，所以计划员还不能像成熟 APS 那样直接拖着改。 |
| 物料、库存、缺料追踪 | 1.1 | 3.0 | 大差距 | 当前更像“准备好没有”的提醒，不是完整物料计划；成熟 APS 会看库存、采购、BOM、到货时间、缺料影响和订单追溯。 |
| What-if 和多方案比较 | 1.6 | 3.0 | 大差距 | 当前有模拟排程、候选方案和场景预览的基础，但还缺少计划员能直接使用的方案比较页面和清楚解释。 |
| 瓶颈和原因解释 | 1.5 | 3.0 | 大差距 | 当前有关键链、图分析、延误和利用率报表，但还没有把“为什么晚”“卡在哪里”“怎么改”讲给用户听。 |
| 报表和 KPI | 1.8 | 3.0 | 中到大差距 | 延误、利用率、停机影响这些基础报表已经有；差在更完整的 KPI 看板、成本、库存、交付承诺、趋势分析和根因分析。 |
| 周计划和资源派工 | 2.0 | 3.0 | 中等差距 | 这块很贴近本项目用户，能导出给现场用；差在现场执行反馈和实际进度回写。 |
| 车间执行反馈 | 0.8 | 3.0 | 大差距 | 当前更多是“计划下发”，还不是“现场执行中实时反馈”。成熟系统会有开工、完工、暂停、异常、实际工时。 |
| ERP/MES/API 集成 | 0.8 | 3.0 | 大差距 | 当前强项是 Excel 和本地离线；和商业 APS 的 ERP/MES 深度集成相比差距大。这个差距有一部分是项目定位决定的。 |
| 多人协同和权限 | 0.7 | 3.0 | 大差距 | 当前有日志和版本意识，但还不是多人协同系统；成熟产品会有角色、审批、锁定、评论、权限和审计。 |
| 多工厂/供应链计划 | 0.4 | 3.0 | 很大差距 | 当前是单厂本地详细排程，不是供应链计划平台；这不是短板优先级最高的地方。 |
| AI、数字孪生、实时重排、碳排 | 0.5 | 3.0 | 很大差距 | 当前有图分析和关键链，算是未来高级能力的种子；但还没有成熟 AI 助手、实时数据、数字孪生和能耗碳排。 |

## 6. 总体差距判断

如果拿当前项目和“头部企业级 APS 套件”比，差距还比较大。

原因不是当前项目没有价值，而是对方覆盖的是企业级完整链路：

- 从销售预测到主生产计划。
- 从采购、库存到物料齐套。
- 从 ERP/MES 集成到车间反馈。
- 从多人协同到多工厂。
- 从拖拽调整到多方案仿真。
- 从瓶颈诊断到 AI 辅助。

如果拿当前项目和“面向单厂、本地离线、Excel 驱动的小型 APS”比，当前项目已经有比较像样的基础版雏形。

当前项目最有价值的地方是：

- 已经不是只做静态表格。
- 已经能排人、排设备、排工序顺序。
- 已经有正式排程、模拟排程、历史版本、周计划、资源派工、报表。
- 已经在做关键链、图分析、候选方案这种偏高级的尝试。
- 已经照顾 Win7 离线交付，这一点和很多现代云 APS 不是同一个战场。

所以更准确的说法是：

- 对“本地离线单厂 APS 基础版”来说，当前大约走到了 `60% - 70%`。
- 对“成熟商业 APS 单厂详细排程产品”来说，当前大约走到了 `40% - 50%`。
- 对“企业级供应链计划平台”来说，当前大约只有 `20% - 30%`。

这些比例不是数学测量，而是按功能覆盖、用户体验成熟度、集成深度和闭环程度做的工程判断。

## 7. 最应该补的差距

下面按“最值得优先补”的顺序排，不按最酷炫排序。

### 7.1 第一优先级：把甘特图调整做成真正可用

原因：

- 市面上成熟 APS 都很重视甘特图上的人工调整。
- 当前项目后端已经有草稿、校验、保存、发布服务。
- 页面上入口还没开放，这意味着已经写了不少地基，但用户还没真正用上。

建议目标：

- 允许计划员在甘特图上拖动任务时间。
- 允许计划员改设备或人员。
- 调整后立即提示冲突。
- 冲突要讲人话，比如“这台设备这个时间已经排了另一个任务”。
- 能保存为方案。
- 能预览方案。
- 能用二次确认发布为正式版本。

这一步做好后，当前项目会从“能看排程结果”明显升级成“能调整排程方案”。

### 7.2 第二优先级：把物料从“准备状态”升级成“缺料闭环”

原因：

- APS 只考虑设备和人员还不够。
- 实际生产里，经常不是设备没人，而是物料没到、半成品没好、外协没回。
- 市面上成熟 APS 基本都会把物料当成关键约束。

建议目标：

- 建立 BOM 或批次用料清单。
- 记录库存数量、已分配数量、预计到货数量。
- 支持采购/外协到货日期。
- 排程时能判断某个工序最早什么时候物料齐套。
- 甘特图或报表里能显示缺料影响。
- 延误原因里能说清楚“不是设备问题，是这个物料没到”。

这一步做好后，排程结果会更接近真实生产。

### 7.3 第三优先级：做计划员能看懂的多方案对比

原因：

- 当前算法层已经有候选方案和优化尝试。
- 但计划员更关心“哪个方案更好，为什么好，代价是什么”。

建议目标：

- 做一个方案对比页。
- 每个方案展示：
  - 总延期小时。
  - 延期批次数。
  - 最大延期批次。
  - 设备平均利用率。
  - 人员平均利用率。
  - 换型次数或换型时间。
  - 缺料影响数量。
  - 被改动的任务数量。
- 支持一键进入某个方案的甘特图预览。
- 支持把某个方案发布成正式版本。

这一步做好后，现有算法能力会更容易被用户理解和信任。

### 7.4 第四优先级：补“为什么晚了”的解释

原因：

- 计划员最怕系统只告诉他结果，不告诉他原因。
- 成熟 APS 会把瓶颈、缺料、资源冲突、交期风险讲清楚。

建议目标：

- 对每个延期批次给出主要原因。
- 原因可以先从简单规则开始：
  - 物料未准备。
  - 前序工序完成太晚。
  - 关键设备负荷过高。
  - 关键人员负荷过高。
  - 外协周期过长。
  - 停机影响。
  - 冻结窗口导致不能调整。
- 在甘特图、报表、周计划中都能看到这些原因。

这一步做好后，系统会从“给结果”变成“能解释结果”。

### 7.5 第五优先级：补车间执行反馈

原因：

- 当前项目能下发周计划和资源派工。
- 但如果现场实际做快了、做慢了、暂停了，系统还不能很好地回收这些变化。

建议目标：

- 增加任务开工、完工、暂停、异常记录。
- 支持实际开始时间、实际结束时间、实际工时。
- 支持现场备注。
- 支持用实际进度重新排剩余任务。
- 报表区分计划工时和实际工时。

这一步做好后，项目会从“排一次计划”走向“计划和现场互相反馈”。

### 7.6 第六优先级：定义集成边界

原因：

- 当前 Win7 离线定位不适合一上来做复杂云集成。
- 但长期看，Excel 之外最好有更稳定的数据接口。

建议目标：

- 先保留 Excel 作为主入口。
- 增加可控的本地导入导出接口。
- 明确哪些数据未来能从 ERP 来：
  - 批次。
  - 工艺路线。
  - 物料。
  - 库存。
  - 采购到货。
  - 完工回报。
- 先把接口格式文档化，不急着接所有系统。

这一步做好后，项目不会被 Excel 永远锁死。

## 8. 不建议现在优先追的方向

这些方向市场上很热门，但不一定适合当前项目马上做。

- 不建议马上做完整供应链计划平台：
  - 当前项目是本地单厂 APS，先把详细排程闭环做好更重要。
- 不建议马上做云端多人协同套件：
  - Win7 离线交付是硬约束，云协同不是当前最优先。
- 不建议马上做 AI 大模型排程：
  - 现在更缺的是数据闭环、调整闭环、物料闭环。
  - 没有这些基础，AI 只能讲漂亮话，很难稳定排出可用计划。
- 不建议马上追碳排、能耗、数字孪生：
  - 这些是高级能力。
  - 当前更应该先补计划员每天会用到的能力。

## 9. 建议的阶段路线

### 阶段一：把本地单厂 APS 做顺

目标是让计划员每天真的能用。

- 打通甘特图拖拽调整。
- 打通草稿、校验、保存、预览、发布。
- 把冲突提示写成人话。
- 增强周计划和资源派工的可用性。
- 增加延期原因解释。
- 把现有候选方案做成清楚的方案对比页。

### 阶段二：把物料和执行闭环补上

目标是让排程更接近真实生产。

- 建立用料、库存、采购到货、缺料影响链路。
- 增加车间开工、完工、异常反馈。
- 用实际进度重新排剩余任务。
- 报表里区分计划和实际。

### 阶段三：把系统从工具变成小型平台

目标是让项目具备继续扩展的基础。

- 增加更稳定的数据接口。
- 补权限、角色、操作审计。
- 做更完整的 KPI 看板。
- 做计划变更影响分析。
- 为未来 ERP/MES 对接留接口。

### 阶段四：再考虑高阶能力

目标是根据真实用户使用情况决定要不要继续升级。

- AI 辅助解释和调整建议。
- 更复杂的多目标优化。
- 多工厂或多车间。
- 设备数据接入。
- 能耗、成本、碳排。

## 10. 本次调研使用的主要公开来源

Sub Agent 使用 Exa MCP 查到并归纳了这些公开来源。这里列主要入口，完整判断以上文能力拆解为准。

- Siemens Opcenter APS / Preactor:
  - https://plm.sw.siemens.com/en-US/opcenter/advanced-planning-scheduling/
  - https://plm.sw.siemens.com/en-US/opcenter/advanced-planning-scheduling/preactor-aps/
  - https://blogs.sw.siemens.com/opcenter/new-capabilities-in-opcenter-aps-2404/
  - https://blogs.sw.siemens.com/opcenter/opcenter-aps-2410-release-sustainable-production-scheduling/
- DELMIA Ortems:
  - https://www.3ds.com/products/delmia/ortems
  - https://www.3ds.com/products/delmia/ortems/production-scheduler
  - https://www.3ds.com/products/delmia/ortems/manufacturing-planner
  - https://www.3ds.com/products/delmia/ortems/synchronized-requirements-planner
- Asprova APS:
  - https://www.asprova.com/en/products/
  - https://www.asprova.com/en/production-scheduler/
  - https://www.asprova.com/en/features/
- PlanetTogether APS:
  - https://www.planettogether.com/advanced-planning-and-scheduling
  - https://www.planettogether.com/features
  - https://www.planettogether.com/integrations
- SAP PP/DS and SAP IBP:
  - https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/
  - https://help.sap.com/docs/SAP_INTEGRATED_BUSINESS_PLANNING
  - https://community.sap.com/topics/pp-ds
- Oracle Fusion Cloud Production Scheduling:
  - https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/
  - https://www.oracle.com/scm/supply-chain-planning/
  - https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/24d/faups/
- Kinaxis Maestro / RapidResponse:
  - https://www.kinaxis.com/en/solutions/supply-chain-planning
  - https://www.kinaxis.com/en/solutions/concurrent-planning
  - https://www.kinaxis.com/en/solutions/production-planning
- Blue Yonder:
  - https://blueyonder.com/solutions/supply-planning
  - https://blueyonder.com/solutions/production-planning
  - https://blueyonder.com/solutions/control-tower
- OMP Unison Planning:
  - https://omp.com/solution/unison-planning
  - https://omp.com/solution/supply-chain-planning
  - https://omp.com/solution/scheduling
- o9 Digital Brain:
  - https://o9solutions.com/platform/
  - https://o9solutions.com/solutions/integrated-business-planning/
  - https://o9solutions.com/solutions/supply-chain-planning/
- IFS Cloud Manufacturing / MSO:
  - https://www.ifs.com/solutions/enterprise-resource-planning/manufacturing
  - https://docs.ifs.com/
- Infor SyteLine / CloudSuite Industrial APS:
  - https://www.infor.com/solutions/erp/cloudsuite-industrial
  - https://docs.infor.com/
- Epicor Kinetic APS:
  - https://www.epicor.com/en-us/erp-systems/kinetic/
  - https://help.epicor.com/
- Microsoft Dynamics 365 Supply Chain Management:
  - https://learn.microsoft.com/en-us/dynamics365/supply-chain/
  - https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/
  - https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/
- QAD Adaptive ERP / Advanced Scheduling:
  - https://www.qad.com/solutions/manufacturing
  - https://www.qad.com/solutions/supply-chain

## 11. 一句话结论

当前项目已经具备“本地离线单厂 APS 基础版”的核心骨架，尤其是资料、排程、甘特图查看、周计划、资源派工、报表和候选方案方面已经有实物；真正拉开差距的是成熟 APS 最重视的五件事：甘特图可编辑、物料缺料闭环、多方案可解释对比、车间执行反馈、ERP/MES/协同集成。
