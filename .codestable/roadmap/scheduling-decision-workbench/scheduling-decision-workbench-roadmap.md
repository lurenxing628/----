---
doc_type: roadmap
slug: scheduling-decision-workbench
status: completed
planning_state: reviewed
implementation_authorized: true
authorized_items: [decision-comparison-loop, decision-delivery-impact, decision-resource-impact, decision-preparation-events, decision-recommendation, decision-optimization-process, decision-history-trends, decision-integration-acceptance]
current_stage: decision-integration-acceptance
current_stage_state: passed
stage_dispatch: parent_controlled
created: 2026-10-13
last_reviewed: 2026-10-14
source_revision: 0df8fc48
summary: 完整建设排产方案决策工作台，统一多候选比较、推荐取舍、交付影响、资源负荷、准备工时、优化过程和历史趋势
tags: [aps, candidate-comparison, recommendation, capacity, history, workbench, win7]
related_requirements: [candidate-comparison-business-view, gantt-readonly-result-view]
related_architecture: [service-scheduler, workbench-shell, ui-gantt]
related_roadmaps: [workbench-prototype-migration, aps-three-gap-directions, trial-scenario-planning, demand-hours-integration]
---

# 排产方案决策工作台整体方案

本方案把“排完产后选择哪套方案、为什么选、付出什么代价、影响谁”作为完整产品能力建设。所有阶段共同完成下述目标；第一阶段是可运行的起点，最终验收覆盖全部阶段。

2026-10-13 用户要求形成整体方案、作出明确决策并由独立 subAgent 审查，后续实施以审定稿为依据。本轮交付主方案、依赖清单和审查处理记录；实施状态由条目逐项维护。

**方案状态：A第0—8阶段的非延期范围已通过主对话验收，并已提交推送origin/main（efe047d3）。B独立review/debug的B1—B15及同类界面修复已通过主对话非延期范围验收，82路径提交7b2697a5已推送origin/main并核对；C独立对话U0—U2已通过主验收，U3共同复用与预算正在实施。** B验收时同库正常实例为59615／PID50528（现已退出，原库保全），原库、Python3.8.10、Schema40保持；主对话已核对身份、真实页面与CSV。Gate04前16步通过，762收集／726通过／36跳过／0失败；第17步仅原15条Windows required setup-skipped导致failed。全部Windows验证由用户在大改后统一测试，保留失败/跳过及核销规则。用户决定性能留C收口：每候选20,000安排的4／6／8候选summary仍为3.6246／4.6823／5.2835秒，2秒目标与完整旧候选/资源窗口保持。C对话01a13a5e-ebf4-7bb2-abd6-ca06b29491c4/local按主对话施工稿U3.1—U3.7执行共同解码复用与预算，后续U4—U6逐段设计并验收。当前B证据覆盖dirty工作区，当前状态依据[主验收表](stage-acceptance.md)，B原件在`evidence/decision-workbench-review/2026-10-14/`，性能移交在`evidence/decision-stage-acceptance/stage-08/performance-c-handoff.json`。下列历次交付和返修段落保留过程事实。

> 2026-10-13 用户追加推荐卡排版返修：原主因固定320px窄列、短清单大空白及行距过密；当前重排为全宽主因、下方收益／代价两栏，并增加正文行距和指标间隔。上一轮数学、事实、事务、原始文件与功能证据保持有效；本次结构构建及受影响页面验收进行中。第7已正式派发，先交此处更新预览再继续历史趋势。

> 此前暂停记录（2026-10-13）：用户要求先讨论整页信息架构并对标成熟APS／项目管理系统，推荐区／结果页局部施工与第7开发已暂缓，当前改动原样保留。推荐卡两份源码及既有CJS已更新，22:19:15 Chrome109构建完成／资产3 passed，实际54526返回main.js1791901155；本增量1392／1920／窄屏视觉验收尚未执行。结果页及第7产品代码尚未修改，当前仅完成只读来源核对。

> 2026-10-14 第二版整页接入及母验收6项返修实施验收passed，最终53871/PID44499/main1791922970；主对话独立验收passed，第7已恢复先前派发、连续实施，第8等待前置完成。四份不同安排由真实求解保存，产品读取共同归档服务。

## 1. 结论与产品决策

**当前最有价值的投入是补齐方案选择能力。** 引擎与候选持久化已具备大部分事实，主要工作是统一比较口径、补充成本证据，并把分散信息组织成一条决策流程。

| 编号 | 本方案采用的决定 | 价值与理由 |
| --- | --- | --- |
| D01 | 建设一个完整“方案对比”主页面，包含总览、批次影响、资源影响、准备与换型、优化过程、历史趋势 | 计划员在一个入口完成判断，再进入甘特核查和采用。 |
| D02 | 同次排产的全部候选进入横向表，支持任选一个候选作基准；排产前正式计划是另一个明确的比较模式 | 同次择优与重排影响各有清楚答案。原算法候选、原正式计划分别显示身份。 |
| D03 | 推荐沿用该次排产保存的选择规则与选择结果，解释其实际收益、代价和完成性 | 用户看到的推荐与算法实际选择一致；正式采用继续由用户明确操作。 |
| D04 | 业务资源指标统一采用可用班表口径，所有候选共用时间窗和资源集合 | 消除候选因工期长短、已用资源数量不同而产生的分母偏差。 |
| D05 | 同时展示“工序准备工时”和“工种切换次数”，时间来自调度实际计入的准备需求 | 两项均有实际证据，能够解释真实成本。准备工时相同的候选直接显示相同。 |
| D06 | 批次交付、资源压力、工序变化、推荐与导出共用一个比较服务 | 一次修正规则能同步到主页面、值班台、试调和导出。 |
| D07 | 完成性放在比较表最前；部分结果显示已完成子集、未完成集合和剩余需求 | 交期改善与任务漏排同时可见，选择依据完整。 |
| D08 | 恢复优化过程和历史趋势，并明确记录范围、采样和可比性 | 过程解释“这次怎样改善”，历史解释“历次发生了什么变化”。 |
| D09 | 复用现有 React/JavaScript、Python 3.8、SQLite、日历与采用机制 | 适配 Win7 x64、离线单机和现有交付包。 |
| D10 | 本方案的完整交付包含真实数据贯通、浏览器操作、导出和相关回归 | 交付结果以业务场景验收，页面形似只完成其中一部分。 |

### 1.1 与已有规划的关系

- 2026-05-24 原型的推荐、批次影响和资源影响，是本方案恢复的业务目标。示例数值由真实计算替换。
- 旧 `candidate-comparison-business-view` 的“代表三方案、无任选候选比较”扩展为“同次全部候选、明确基准”。实施第一阶段同步其能力目标与当前实现描述。
- 9 月工作台迁移的页面、身份、离线资产和采用成果继续使用。本方案承接迁移后缩减的分析能力，以现行工作台组件实现。
- `trial-scenario-planning` 继续按其留存备用状态管理；本方案为现有试调提供共同指标与比较入口。联动重排、虚拟资源和条件求解仍由该规划负责。
- `demand-hours-integration` 中的批次工时与执行计量规则作为成本事实来源；本方案在排产结果中展示这些事实。
- 引擎当前的优化目标、规则池与选择策略保持现有业务含义。展示层准确解释这些规则，新的顺序相关换型求解由独立算法需求承接。

## 2. 实施前事实与建设差距

以下是方案审查时的起点快照；第 0、1 阶段的现行交付见第 12 节及对应 feature 验收，后续条目按清单推进。

| 当前事实 | 实际证据 | 建设动作 |
| --- | --- | --- |
| 主候选表并排展示 3 项指标，其余 12 项摘要藏在生成资料中 | `frontend/workbench/app/RunCandidateControls.jsx:41,56`；`RunCandidateAPI.js:31` | 业务指标全部回到比较区，生成资料只保留来源与技术记录。 |
| 候选完整分析返回四项指标，推荐字段为空 | `core/services/workbench/run/candidate_analysis.py:27-36` | 新增同次比较读模型，提供推荐与结构化差值。 |
| 每个候选完整 artifact 和整个选择结果已保存 | `data/repositories/workbench_run_result_repo.py:23-66` | 直接投影现有事实，统一候选身份映射。 |
| 排产受理时保存完整业务资料 | `core/services/workbench/run/jobs_facts.py:14-26` | 所有回看依据同一归档，复用既有归档标识。 |
| 值班台已有候选与受理时正式计划的批次/设备差值 | `core/services/workbench/run/candidate_comparison.py:110-135` | 提取共同比较职责，扩展人员与同次候选。 |
| 班表容量共同核算已经存在 | `core/services/capacity/resource_utilization_metrics.py:63-103` | 资源明细、日峰值与总览统一消费。 |
| 当前换型次数按设备上相邻工种变化计算；准备工时按每道工序计入 | `core/algorithms/evaluation.py:295-313`；`core/algorithm_runtime/internal_slot.py:69-84` | 分别建立切换事件与实际准备需求账。 |
| 新候选采用的历史摘要记录采用审计，算法指标在源候选 | `core/services/workbench/plan/official_persistence.py:38-47` | 历史读模型沿采用来源回连候选。 |
| 完整正式安排覆盖是采用前提 | `core/services/workbench/run/candidate_adoption_validation.py:93-105` | 页面分别展示排产完整性、正式安排覆盖和采用预检状态。 |

当前仓库 `db/aps.db` 中新工作台候选表为空；历史原型、当前代码及交付脚本已经核对。实施验收使用隔离实例创建完整候选，现场案例按实际实例导出已有资料后复现。

## 3. 用户操作与页面结构

### 3.1 从排产到采用

1. 排产结束后进入本次“方案对比”，页首显示运行时间、批次/工序数量、计划时间窗、完整/部分结果数量。
2. 推荐区说明推荐哪套、依据哪条选择规则、相对基准改善了什么、增加了什么成本。
3. 横向表按方案分行、指标分组；默认突出推荐候选与原算法候选，全部候选保持可访问。
4. 点击方案切换关注对象，点击“设为比较基准”改变所有差值的基准。共同范围和基准始终显示在页面顶部。
5. 进入批次、资源、准备与换型页签核对局部代价；点击对应行进入同方案甘特并定位对象，返回后保留比较上下文。
6. 点击“采用”进入已有采用预检，显示拟采用版本、范围和当前依据变化；采用成功后保留原比较并提供正式计划入口。

### 3.2 页面布局

```text
方案与范围：本次排产 / 对比模式 / 基准 / 资源时间窗 / 导出
推荐结论：推荐方案 + 完成性 + 主要收益 + 主要代价 + 采用入口
候选横向表：完整性 → 交付 → 时间/准备 → 设备/人员 → 变更成本
详情页签：批次影响 | 资源影响 | 准备与换型 | 优化过程
历史趋势入口：所选运行/正式计划的历史来源、趋势和范围变化
```

主表提供“常用指标”和“全部指标”两种视图。常用视图至少包含未排工序、超期批次、总拖期、完工跨度、准备工时、工种切换次数、设备/人员高压力数量、调整工序数；全部指标增加加权拖期、内制跨度、占用/需求负荷、班表外安排、重叠、资源数量与计算用时。指标列分组、固定方案列，资源明细分页和按需读取。

推荐区和横向表位于甘特之前。完整甘特沿用现有独立页；选择方案与看时间轴各有清楚入口。

### 3.3 比较模式

| 模式 | 比较对象 | 默认基准 | 适用动作 |
| --- | --- | --- | --- |
| 本次候选 | 同一 `run_ref` 的候选全集 | 本次原算法候选；其计算失败时要求选择一个已产出候选 | 选择本次最佳方案。 |
| 重排影响 | 选中候选与该运行受理时正式安排快照 | 固定为该次 `admission_official` | 判断相对原计划的交期、资源和稳定性变化。 |
| 试调影响 | 已保存试调与其来源完整方案 | 保存的来源计划或候选 | 解释人工调整产生的变化，复用共同指标。 |
| 历史趋势 | 多次运行或正式版本 | 时间轴，无默认因果基准 | 查看走势；证据等价的运行支持成对差值。 |

同次候选切换时，批次集合、资源集合、时间窗保持固定。筛选批次仅影响对应明细；页首推荐与整份结果摘要保持完整排产范围，并明确标注“整次排产”。

## 4. 一套共同指标与比较规则

### 4.1 共同范围

- **业务范围**：运行受理时选定的全部批次及其永久工序身份，包含未安排、跳过、已执行和冻结项。交付按每批完整工艺完成性计算。
- **资源默认时间窗**：排产起日 00:00 至截止日次日 00:00，工厂本地时间，左闭右开。用户修改后一次应用于全部比较对象。
- **完整计划跨度**：各方案全部安排首尾之差，单列为结果指标；资源占用率使用上述共同窗口。
- **资源集合**：同次所有候选与比较基准实际涉及的设备/人员并集，在该次会话中固定；每个方案未使用的资源在容量有效时记占用 0。新打开其他候选沿用同一集合。
- **身份匹配**：使用永久 `operation_ref`，分件按现有永久分件工序身份处理，任务行引用用于甘特定位。
- **数值差值**：统一 `所选方案 − 基准`。指标目录定义单位、显示精度、改善方向和适用范围；先按原始数值计算差值，再格式化。

### 4.2 指标目录

| 组 | 指标 | 口径与用途 |
| --- | --- | --- |
| 完整性 | 预期/已排/未排工序、完成/未完成批次、已知失败、跳过原因 | 决策第一组；分别呈现任务缺口和结果状态。 |
| 交付 | 超期批次、总拖期、加权拖期、准交批次、未知交付批次、最晚完工 | 采用完整批次终点和现有交期边界。未完成批次进入未知/未完成集合。 |
| 时间 | 全部安排跨度、内制安排跨度 | 解释整体工期和内制资源占用跨度。 |
| 准备 | 待执行准备标准工时、已排准备标准工时、未排准备标准工时、加工标准工时 | 来源为引擎采用的工序需求账；按目标量、执行状态和分件规则计算。 |
| 切换 | 工种切换次数、切换设备数、逐次切换事件 | 按当前工种切换语义；展示前后工序与切换发生的顺序。 |
| 资源容量 | 可用工时、班表内占用、需求负荷、班表外占用、重复占用、已用资源数 | 设备、人员分别计算。 |
| 资源压力 | 容量加权占用率、日峰值、高压力资源数、零容量有任务数、冲突资源数 | 高压力阈值沿用 90%；零容量和冲突单独列出。 |
| 均衡 | 固定资源集合的日占用率离散程度、Top 压力资源 | 比较工作分布；占用率采用中性展示，压力风险清楚提示。 |
| 稳定性 | 新增/移除/移动工序、换设备/换人员工序、起止变化 | 同一工序只计一次变更，分类可重叠并明确显示。 |
| 计算 | 用时、候选来源、实际搜索规则、停止原因 | 解释方案来源与计算投入。 |

总指标始终返回覆盖情况：`complete/partial/unavailable/not_applicable`、已知小计、未知数量、总数量和具体缺项。全量未知时显示缺少的事实；已知小计与完整总值使用不同字段。比率指标返回分子、分母及其覆盖情况，已知部分按已知分子/分母计算，并标注已知范围。

完整性采用三个维度：搜索覆盖（各候选是否算完）、可排工序覆盖（应排工序是否齐全）、业务交付覆盖（全链完成或按待料策略暂缓）。运行 `partial` 可由兄弟候选超时造成；合法 `material_strategy=stage` 的本次可排工序齐全时，显示“本次可排范围完成”，整批完工仍显示待后道安排。各维度来自既有 dispositions、完成性证据与采用规则。

**交期共同合同：**`due_state=specified/unspecified/invalid`。`9999-12-31` 表示 `unspecified`，批次显示“未指定交期”；实际缺失或非法值归 `invalid`，保留具体原因。工艺完成性独立显示。有明确交期的批次进入交付评价集合；未指定交期的批次另计 `excluded_due_count`，其拖期为 `null`，交期评价为 `not_applicable`。总拖期、超期数和准交率同时返回 `due_eligible_count`、已知/未知数量；全范围均未指定交期时，交期指标 `value=null/state=not_applicable`。有明确交期但未排完整或资料异常时，汇总按未知覆盖处理。

算法保存的分数继续保留原值；决策展示使用上述共同业务口径。实施第二阶段将候选、正式计划、值班台、试调和导出的交付投影接到共同入口，并同步其前端状态枚举。

### 4.3 资源计算

共同核算采用 `ResourceUtilizationMetrics`：

- 占用率 = 可用班表内任务区间并集时长 ÷ 可用时长。
- 需求负荷率 = 可用班表内各独立工序需求时长之和 ÷ 可用时长；重叠需求可超过 100%。
- 重复占用 = 需求工时 − 并集占用；同时返回实际重叠时段便于定位。
- 班表外占用 = 全部占用并集 − 班表内占用。
- 总览占用率 = 各资源班表内占用之和 ÷ 各资源可用容量之和，设备与人员分别统计。
- 高压力资源：共同窗口内至少一个已知自然日占用率 ≥90%；每个资源计一次。另返未知日资源数、零容量有任务资源数、冲突资源数。
- 均衡指标使用容量加权的占用率变异系数：`u_i=occupied_i/capacity_i`，`mu=Σoccupied_i/Σcapacity_i`，`sigma=sqrt(Σcapacity_i×(u_i−mu)²/Σcapacity_i)`，`CV=sigma/mu`。固定集合中正容量资源参与计算，未用资源取占用 0；零容量资源另列。`mu=0` 时为 `not_applicable` 并显示“该范围无安排”；容量缺项时显示覆盖不足。设备、人员分别计算，日明细与整窗分别使用相应窗口的分子/分母。

资源页同时提供设备、人员两种视角，包含对比明细表、逐日热力图、增幅最大的资源、压力最高的资源和冲突定位。默认 Top 10 支持展开全部。

正式基准按受理时“每道工序最后正式安排”解析。默认资源页展示“本次选批贡献”；切换“完整候选压力”时显示候选完整安排，并展示正式安排覆盖数。覆盖完整的候选可说明整份采用结果压力；覆盖不足时同时展示缺失的正式安排和未排需求，用户据此补齐排产范围。页面与采用预检共用覆盖判断。

归档日历适配统一支持全局日历、设备停机、个人日历、人员轮班和归档时适用的日历版本；在 `candidate_metrics.py`、`trial/calendar.py`、`plan/calendar.py` 的现有能力基础上提取共同归档适配器。

### 4.4 准备工时和切换事件

当前算法按 `setup_hours + unit_hours × 有效目标量` 形成工序需求。为准确覆盖已执行、冻结和分件工序，在**共同工序需求构造处**生成 `OperationEffort`，调度和指标共同消费：

```text
operation_ref, source, quantity_basis, target_quantity, remaining_quantity
execution_target_quantity, execution_quantity_basis
setup_standard_hours, processing_standard_hours, required_standard_hours
setup_state = pending | retained_in_execution | already_completed | external | unknown
effort_basis = runtime_requirement_v1
```

`required_standard_hours` 等于该次运行实际交给排槽的标准需求。执行中的剩余需求、冻结安排、分件准备计取均沿用共同执行/工时规则，由该规则输出计量分解。新排标准准备工时只汇总该候选实际新排的自制工序，每个永久工序计一次；分件自身工序分别计取，共同工序计一次。原样保留、已开工/已完成种子单列安排及其需求依据。已发生准备是否完成由保存的执行事实决定，缺少分解时给出缺项。外协以外协周期单列。日历效率换算后的占用小时由资源指标承担。

第4阶段数量口径：`target_quantity / quantity_basis` 绑定该份保存需求原目标，`execution_target_quantity / execution_quantity_basis / remaining_quantity` 绑定本次受理AJ执行事实，两侧分别对照原需求。原保存10件／7h、本次目标20件时，原需求仍10件／7h，执行目标另列20件；旧需求原目标缺失保持null／unknown，本次已知执行目标仍展示。

准备页展示每道工序的准备、加工、剩余量、状态与设备，提供候选汇总和差值。全部候选完整覆盖同一需求时，准备总量通常相同；其变化能直接追到未排工序、目标量和执行处理。

切换事件统一从设备排序后的内制非零工时安排生成：`machine_ref, previous_operation_ref, next_operation_ref, previous_type, next_type, next_start`。计数函数和事件清单共用这条生成规则。同工种连续安排计 0，设备第一道安排计 0；重叠安排标注冲突，相关切换统计附完整性状态。时间筛选先按完整序列确定相邻关系，再按后一道的开始时间纳入窗口，保留窗口前驱。

产品标签采用“工序准备工时”和“工种切换次数”。当前调度规则下的准备成本和切换顺序分别准确呈现。顺序相关的真实换型时间需要换型族、前后转换定额和相应排槽规则，属于后续独立算法能力。

## 5. 推荐与收益、代价

### 5.1 推荐事实来源

运行保存的 `selection.selected_candidate_key` 映射到对应 `candidate_ref`；`reason_code`、选择策略、实际目标、容差和 `health` 转成结构化解释。推荐标记固定反映该次计算的结果；用户切换基准只改变收益/代价差值。

选择证据保存两个固定基准：`raw_score_best_candidate_ref` 用于解释 balanced 交期容差，`health_reference_candidate_ref` 指向算法原始 baseline，用于解释关键链健康改善。两者分别带当时的指标、差值和采用的容差。`DecisionScope.reference` 是用户查看基准。推荐区分为“当时的选择依据”和“相对当前基准的收益与代价”，前者消费冻结的 `selection_basis`，后者消费当前比较差值。

页面把三类状态分开显示：算法推荐、方案排产完整性、当前采用预检。采用预检沿用现有事务前检查与失败处理，现场更新由预检明确显示。

### 5.2 解释生成

采用确定性规则模板，模板参数来自已核实的指标和选择证据：

1. 先说明完成性和选择主因，例如“全部工序已安排；按本次保交期目标优先”。
2. 依次给最多 3 条主要收益、3 条主要代价，例如减少超期、缩短拖期、增加准备需求、设备压力上升、工序变动增加。
3. 展开可查看全部差值及支撑批次/资源/工序；每条解释包含相应钻取目标。
4. balanced 策略选择了关键链改善方案时，明确说明实际改善和接受的交期差额及本次容差。
5. 候选指标并列时显示“目标指标并列”，解释当前平分裁决规则；等价复用标明来源候选并允许展开策略记录。

推荐标题按三轴完成性区分：完整业务结果为“推荐方案”；合法待料暂缓且本次应排工序齐全为“本次可排范围推荐”；其他部分产出显示“算法选中的部分结果”与具体缺口，正式采用状态取现有预检。运行中的兄弟候选失败或超时只影响搜索覆盖，已完成候选按自身事实展示。

已完成子集不同的部分候选单独分组，逐项显示未完成批次集合和剩余工作。成对交付收益使用两边共同完成批次；全部选批的未知结果列出，准备工时的减少与漏排关联时显示“少安排的准备需求”，方向为中性。

## 6. 批次影响、工序影响与跨页定位

批次表：批次/零件/优先级/目标量、交期、基准与所选方案完成状态和完工、拖期差、提前/延后、新增超期/解除超期、未排工序。支持按恶化优先、改善优先、拖期量排序及筛选变化项。

工序变化表：基准/所选开始与结束、设备/人员、变更类型、工时需求、已执行/冻结状态和已知约束事实。变化原因引用保存的算法/约束证据，未保存的因果关系显示具体已知变化及可核对约束。

导航上下文统一包含 `run_ref、selected_candidate_ref、comparison_mode、reference、range、batch_ref/resource_ref/operation_ref、return_context`。甘特、交付风险、采用后正式计划、试调、值班台和报表沿用同一身份链。计划版本入口回溯对应候选时保留正式版本与原始候选两种身份。

## 7. 优化过程与历史趋势

### 7.1 优化过程

外层展示每个候选的来源、实际派工规则、耗时、状态、停止原因和最终指标；展开候选查看搜索进步曲线与代表尝试。

曲线记录有效改进事件，采用“累计求解耗时 → 当前最好业务目标”，完整性变化和比较阶段变化采用事件标记。目标不同的过程分别显示主目标和单位。搜索尝试表按保存事实展示来源、结果、变化、接受情况和耗时。

现有保存尝试和轨迹存在条数上限。新增紧凑过程投影保存总尝试数、保留条数、改进数、首尾事件、停止原因及采样策略。每个候选最多保存 200 个曲线点，固定保留首次有效结果、首次全部应排完成结果、最终结果；其余槽位按累计求解耗时等宽分桶保留桶末的最好解，重合点合并。搜索阶段起止、评估/改善/拒绝计数另作阶段汇总。页面注明事件总数与显示数。本方案选用“代表尝试排名＋完整计数＋覆盖首尾的进步轨迹”，服务于判断改善来源与计算效果；每次求解的完整底层事件日志保留在诊断工具职责中。

过程采集复用优化器已有记录点，由每个候选完成时随 artifact 保存；查询页面读取保存结果。旧记录按原保存条数展示“已保存的代表尝试”，轨迹缺少起点或最终点时呈现离散事件。

### 7.2 历史趋势

统一历史条目沿以下来源读取：

- 新运行 → 运行回执 → 推荐/所选候选 artifact。
- 候选正式采用 → 正式计划采用审计 → `run_ref/candidate_ref` → 原始指标。
- 试调采用 → 来源试调快照及采用记录 → 共同指标计算。
- 旧正式版本 → `ScheduleHistory` 保存的旧摘要适配。

历史页先展示运行和正式采用两条可切换时间线，避免同一次计算多次采用造成优化次数重复。支持超期、拖期、加权拖期、跨度、准备、切换、设备/人员压力及计算时间趋势。

跨运行分两种阅读方式：

- **业务走势**：每次运行的实际范围、数量、需求工时、日历和指标一起展示；范围变化处显示标记。
- **同条件对照**：比较选批/工序、数量/交期/优先级、工艺需求、物料/外协事实、日历与停机、资源资格、执行/正式基线和冻结事实。算法配置变化作为显式实验维度；相同目标与指标版本下比较优化效果。服务逐项比较归档事实，返回一致项与变化项；生产条件相同才输出“同条件改善”结论。复用已有归档身份，比较内容按实际字段完成。

旧指标按其原口径显示；有完整归档的历史数据可按当前规则重新投影，并同时标注指标版本和来源。资源趋势按同一固定窗口长度或用户指定的共同窗口展示容量与需求量，分母随范围变化时显示范围标记。

## 8. 模块职责与接口

### 8.1 目标结构

```text
排产/试调保存的事实与工时需求
  → 共同结果评价与资源容量计算
  → 决策服务：运行全集、基准、差值、推荐、批次/资源/过程/历史
  → 工作台路由和导出
  → 方案对比主页面 / 值班台 / 试调 / 历史入口
```

| 模块 | 职责 | 主要落点 |
| --- | --- | --- |
| 工序需求与计量 | 调度与准备/加工需求共享来源 | `core/algorithm_runtime/`、`core/algorithm_contracts/`、`core/services/workbench/run/input.py`、`trial` 的共同需求入口 |
| 归档资料适配 | 一次读取归档并解析设备、人员、日历、正式安排和永久身份 | `core/services/workbench/facts/`，复用 `candidate_facts/candidate_metrics` 与归档日历能力 |
| 共同比较服务 | 统一指标、差值、范围、完成性和结构化解释 | `core/services/workbench/run/` 下的决策查询服务与同层纯投影 |
| 持久化 | 保存新增需求分解、过程元信息，批量读候选与历史来源 | `data/repositories/workbench_run_result_repo.py`、相关 run/plan/trial repositories |
| Web 协议 | 校验引用与筛选、调用服务、返回已有工作台 envelope、生成下载响应 | `web/routes/workbench/` |
| 前端 | 展示、筛选、选择、导航、可访问交互和图形 | `frontend/workbench/app/`；重组 `RunCandidateWorkspace/Controls/Analysis` 与 Dashboard 比较组件 |

先在当前包内明确职责，随着实现把语义相同的公式和归档读取迁入共同入口。现有值班台与候选单项接口改为调用共同服务，重复的差值/换型/日历计算随迁移清理。正式采用继续走现有服务。

### 8.2 共享数据结构

```text
DecisionScope {
  run_ref, comparison_mode: candidates | admission_official,
  selected_candidate_ref?, reference: {kind: candidate, candidate_ref} | {kind: admission_official},
  range_start, range_end, snapshot_ref?
}

MetricValue {
  value: number | null, state: complete | partial | unavailable | not_applicable,
  known_subtotal: number | null, known_count, unknown_count, total_count,
  numerator: number | null, denominator: number | null,
  metric_version, scope: full_admission | common_completed_batches | resource_window,
  reason: {code, message} | null
}

MetricDelta {
  value: number | null, state: comparable | different_coverage | unavailable,
  direction: better | worse | equal | neutral,
  reference_value, selected_value, compared_batch_refs?, evidence_refs[]
}

DecisionOverview {
  run, scope, catalog_complete, metric_definitions[],
  candidates[{candidate_ref, kind, label, status, completeness, coverage,
              metrics, deltas, equivalent_source_ref?, selection_role}],
  recommendation{candidate_ref?, state, reason_code, headline,
                 benefits[], costs[], supporting_refs[], selection_basis},
  baseline, resource_cohort, snapshot_ref
}

SelectionBasis {
  selected_candidate_ref, raw_score_best_candidate_ref,
  health_reference_candidate_ref, selection_policy, selection_policy_version,
  objective_name, objective_field_order[], selected_score[],
  raw_score_comparison, health_comparison,
  overdue_tolerance_count, tardiness_tolerance_ratio,
  evidence_state: complete | partial | unavailable
}
```

`metric_definitions` 是单位、方向、格式与适用范围的唯一目录，页面与 Excel 共用。指标版本采用明确版本名。候选状态和当前已有 DTO 保持一致；新字段表示新增分析语义。

### 8.3 查询与导出协议

以下为新增目标接口，注册在现有工作台蓝图中：

| 接口 | 核心参数 | 返回 |
| --- | --- | --- |
| `GET /api/workbench/v1/scheduling/runs/<run_ref>/decision` | 比较模式、基准、选中候选、资源窗口 | 同次所有候选的紧凑汇总、推荐、指标定义、范围和快照。 |
| `GET .../decision/batches` | 同一 scope、分页、变化类型、排序 | 批次差值与工序钻取引用。 |
| `GET .../decision/operations` | 同一 scope、batch/resource 筛选、分页 | 工序变化、准备需求和定位引用。 |
| `GET .../decision/resources` | 同一 scope、machine/operator、贡献/完整候选视角、分页、排序 | 资源汇总、差值、覆盖情况。 |
| `GET .../decision/resource-days` | 同一 scope、资源引用、日期范围 | 该资源逐日负荷、占用、容量、冲突与任务引用。 |
| `GET .../decision/changeovers` | 同一 scope、设备、分页 | 准备需求摘要和切换事件。 |
| `GET .../decision/process` | candidate_ref、分页 | 候选计算元数据、进步轨迹与保存尝试。 |
| `GET .../decision/export` | 同一 scope、xlsx/csv、导出分区 | 与屏幕同身份、范围、指标版本的比较结果。 |
| `GET /api/workbench/v1/scheduling/decision-history` | run/official、指标、日期、分页 | 来源可追溯的趋势点、范围与可比性说明。 |

各接口使用当前 `ok/schema_version/data/meta/warnings` envelope 和现有请求/快照协议。无效范围 422、引用不存在 404、快照已变化 409、记录损坏使用已有明确错误；合法但资料不足的指标返回缺项状态。结束运行的候选集合稳定；运行中的目录带 `catalog_complete=false`，新增候选时刷新整个比较快照。

共同 query 字段固定为 `comparison_mode=candidates|admission_official`、`reference_candidate_ref`、`selected_candidate_ref`、`range_start`、`range_end`、`resource_view=selected_batches|full_candidate`、`snapshot_ref`。候选模式缺省基准取该次原算法候选；缺原算法结果时返回 `reference_state=selection_required` 并显示可选候选。正式基准模式由受理归档定位；受理时无正式计划返回 `reference_state=absent`，所选候选仍可查看。明细请求必须指定所选候选；两端引用均校验属于该运行。起止参数成对传入，缺省沿用第 4.1 节；候选范围和资源集合由服务返回并固定。

明细分页使用 `page`、`size=20|50`，排序为该分区明确指标键加 `order=asc|desc`，空值排末、同值按永久引用稳定排序。批次筛选使用 `batch_ref/change_kind`，工序使用 `batch_ref/resource_ref/change_kind`，资源使用 `resource_kind=machine|operator`、`resource_view=selected_batches|full_candidate`，逐日明细指定单个 `resource_ref`。

导出参数为 `format=xlsx|csv` 和 `section=all|overview|batches|operations|resources|resource-days|changeovers|process`。XLSX 支持 `all`，CSV 选择一个分区；整表导出按相同筛选读取全部页，页码只影响屏幕。历史接口使用 `timeline=run|official`、`date_from/date_to`、`metric_keys`、`comparison=observed|same_conditions`、`reference_run_ref`、`page/size`；同条件模式的基准运行显式传入。

批次/资源/工序明细默认 20 行，沿用现有分页控件。概览只返回聚合值与引用，单次回复沿用既有体积限制；资源逐日明细按资源和窗口按需查询。

试调和正式计划由各自现有路由加载对应 `AnalysisSource`，交给相同评价/差值服务；其快照及来源身份继续使用既有协议。

### 8.4 保存与兼容

运行收据增加共同 `operation_effort` 需求账、本次指标/选择规则版本及必要配置；候选现有 artifact 增加 `analysis_contract_version、process_evidence`，候选对需求账的已排/未排归属使用永久工序身份匹配。共同需求每次运行保存一份，候选保留自己的安排与计算事实。所有字段在运行完成事务中与候选一起保存。

优先沿用现有 JSON 字段承载新增事实。实施时确认需要索引的历史查询字段后，再按项目 schema 协议增加最少必要字段/索引；相应 schema、迁移和数据字典一起更新。

旧 artifact 由版本适配器读取：保存证据充分的指标按原值或归档重算；缺少运行时需求分解的准备指标返回相应缺项。历史事实保持原样，查询生成分析投影。

## 9. 导出、性能与可访问性

XLSX 提供方案总览、指标口径、批次影响、资源影响、准备/切换、优化过程、数据缺项工作表；CSV 导出当前选择的分区，并附同一范围和身份字段。数值列保留数值类型和单位，差值与界面一致；用户筛选显示与完整导出范围在下载前说明。

首屏一次读取归档与候选聚合，详情按页签加载。请求内复用解析后的归档、日历索引和每个候选的资源区间索引；结果查询复用保存事实。采用单机可取消读取和现有读取状态管理。

性能验证覆盖典型 4/6/8 候选，以及现有 20,000 安排/候选的边界；资源日明细按现有 40,000 resource-days 预算分块计算、分页返回，整窗汇总覆盖完整窗口。用户主动缩小窗口后统一刷新全部比较。验证记录首屏、单资源钻取、导出耗时与峰值内存；相同实例和数据上，新增概览读取以 2 秒以内为目标，重明细加载展示进度并可取消。Win7 目标机实际结果用于最终达标判定。

图形采用本地 SVG/Canvas 与既有 React，随包预编译；表格提供图形的数值等价视图。覆盖浅深主题、1920×1080/1392×924、100%/125%/150% DPI、键盘选择/排序/页签和屏幕缩放。

## 10. 分阶段实施与退出条件

| 顺序 | 条目 | 依赖 | 可交付结果与退出条件 |
| --- | --- | --- | --- |
| 1 | `decision-comparison-loop` | 无 | 共同归档/指标目录、同次全部候选横向表、明确基准和差值、保存选择标记、甘特回跳；真实隔离运行到查看并采用走通。 |
| 2 | `decision-delivery-impact` | 1 | 完成性、逐批交付和工序变化表；完整/部分候选的范围与差值正确。 |
| 3 | `decision-resource-impact` | 1 | 设备与人员共同班表口径、明细/热力图/高压力/冲突、贡献与完整候选视角；两种资源均有贯通证据。 |
| 4 | `decision-preparation-events` | 1 | 共同运行需求分解、准备工时、切换事件，覆盖执行/冻结/分件；成本能逐项追到排槽需求。 |
| 5 | `decision-recommendation` | 2,3,4 | 完整推荐理由、收益与代价、部分结果说明、并列/复用解释；文字逐项对应真实差值。 |
| 6 | `decision-optimization-process` | 1 | 候选来源/停止原因、紧凑过程证据、进步曲线、保存尝试，旧数据明确呈现覆盖。 |
| 7 | `decision-history-trends` | 2,3,4,6 | 运行/采用来源回溯、历史趋势和同条件判断，新候选/试调采用/旧记录贯通。 |
| 8 | `decision-integration-acceptance` | 5,7 | 主页面、值班台、试调、正式计划、导出统一接入；重复实现清理，完整业务验收和开发文档同步。 |

**最小闭环是第 1 项。完整交付以第 8 项通过为终点。** 第 2/3/4/6 项可以在共同契约落定后分工并行，文件所有权明确。每项交付包含自身相关导出和验证，最后一项验证跨入口整体一致性。

## 11. 验收场景与验证选择

| 编号 | 场景 | 期望结果 |
| --- | --- | --- |
| A01 | 同次 4/6/8 候选 | 全部候选可访问，基准选择与排序稳定，推荐源与保存结果一致。 |
| A02 | 候选 A 保交期但资源压力和切换增加 | 首屏明确收益与代价，资源/事件明细与文字对应。 |
| A03 | 候选未排最晚批次，已完成子集拖期下降 | 未排集合优先显示；成对收益以共同完成集合计算。 |
| A04 | 全部部分结果、单候选、失败/预算跳过、等价复用、按工序待料暂缓、未指定交期 | 三轴完成性、原因、候选来源、推荐类别和采用预检符合保存事实；交期适用集合独立计算。 |
| A05 | 设备/人员班次不同、停机、零容量、容量缺失 | 分母来自共同归档日历，覆盖和容量状态正确。 |
| A06 | 多工序重叠、跨天、窗口前驱切换、零工时工序 | 占用/需求负荷/重叠分别正确，窗口事件计数稳定。 |
| A07 | 选批范围小于已有正式安排 | 本次贡献、候选完整安排和正式覆盖缺口清楚显示；采用按现行覆盖规则处理。 |
| A08 | 准备 2h + 单件 0.5h × 10件，另含已执行/冻结/分件 | 需求账与实际排槽一致；时间显示能追到准备/加工分解及执行规则。 |
| A09 | 切换候选、基准、资源窗口并钻取/返回 | 身份、范围、选择和差值始终一致。 |
| A10 | 计算后修改资料/报工/正式计划，再回看和采用 | 历史比较保持原依据；采用预检报告当前变化。 |
| A11 | 目标并列、balanced 容差选择、部分完成集合不同、切到第三候选查看基准 | 两条算法基准和当时的选择依据固定，查看差值随用户基准变化；文字与各自证据一致。 |
| A12 | 过程事件超过显示预算、最终结果在后半段改善 | 首尾、完成性变化、最终最佳值和显示覆盖准确。 |
| A13 | 新候选采用、试调采用、旧版本和范围变化的历史 | 来源正确、采用与运行不重复计数、同条件结论有字段依据。 |
| A14 | 页面、XLSX、CSV、试调对照，混合有交期/未指定/非法交期 | 同范围数值、单位、差值、交期适用范围、未知项和身份一致。 |
| A15 | 典型与边界数据、Win7 离线环境 | 性能、取消、交互、布局和本地资产符合第 9 节。 |

复用当前候选 API、采用事务、部分采用、日历容量、执行/分件、历史和前端契约测试。新增用例集中覆盖上述新增行为，重点锁定共同范围、人员日历、准备需求、推荐与历史来源。实现阶段按 `开发文档/README.md` 的日常与完整门禁入口执行；本轮文档验证采用 YAML、引用、依赖和独立方案审查。

## 12. 文档同步与实施状态

实施第一阶段更新 `candidate-comparison-business-view` 的目标范围；各阶段按实际实现同步相应接口和用户说明。共同职责迁移完成后更新 `architecture/service-scheduler.md` 与 `workbench-shell.md`。旧迁移记录保留历史，通过本方案链接说明新增建设。

状态清单见 [scheduling-decision-workbench-items.yaml](scheduling-decision-workbench-items.yaml)。审查处理记录见 [review.md](review.md)。本稿的目标结构与接口是后续实施输入，当前产品事实以第 2 节及源码为准。

### 2026-10-13 第 0、1 阶段实际交付

第 0 阶段将共同指标、归档身份、用户查看基准与计算时固定选择依据收敛为一个入口，移除重复归档 SHA256 核验，快照按实际字段匹配。第 1 阶段交付同次全部候选、18 项指标与覆盖、任选查看基准、保存推荐/评分最优/健康基准、甘特钻取及回跳、CSV/XLSX 总览与现有正式采用。

隔离真实运行为 6 批、15 工序、4 候选；浏览器采用重点工序优先方案 1/3 后得到正式 v1，15 道工序的身份、数量、时间和资源与候选一致。CSV/XLSX 72 行与屏幕同一结果逐字段核对通过。日常门禁 361 passed / 20 平台跳过，最后选择策略与文档变更完成相关增量验证。

第 1 阶段资源指标清楚标注算法保存口径；当时共同班表指标、准备需求分解、完整批次/资源影响、过程和历史能力沿后续条目推进。详细证据与边界见 [第 1 阶段验收](../../features/2026-10-13-decision-comparison-loop/decision-comparison-loop-acceptance.md)。

### 2026-10-13 第 2 阶段实际交付

`decision-delivery-impact` 已完整实现共同交期/三轴完成性、实际交付调用者迁移、受理时正式归档模式、逐批交付/工序变化、变化筛选与20/50稳定分页、双方甘特定位与完整上下文返回、CSV/XLSX明细及五表比较。正式基准按受理前每道工序最后安排归并，绑定不可变来源；当前候选分析/值班台使用共同范围，显式历史版本入口保留原范围。工序标准需求与执行/保护/保存锁定标记分别表达，实际准备分解沿第4阶段建设。

实施验收通过：最终日常 **400 passed / 20 skipped**、Ruff全通过、Chrome109构建；三个真实边界运行、五次真实浏览器往返、浅深桌面与11场景18份原始导出通过。正式详情的真实布尔字段渲染问题已在共同入口修正并锁定实际响应回归。当前隔离实例为 `http://127.0.0.1:60154` / PID37323，原4/6/8候选和正式v1保留。

第2阶段 `implementation_acceptance=passed` 与 `parent_acceptance=passed`，两项P3已关闭；第3阶段已派发，第4—8阶段仍为planned，待主对话逐阶段派发。准确范围、当前入口和原始证据见 [第 2 阶段交接](../../features/2026-10-13-decision-delivery-impact/decision-delivery-impact-handoff.md) 与 [实施验收](../../features/2026-10-13-decision-delivery-impact/decision-delivery-impact-acceptance.md)。母任务独立验收记录继续由主对话维护。

### 2026-10-13 第3阶段实际交付

`decision-resource-impact` 已完整接入共同归档日历、永久资源区间和固定集合容量加权汇总，交付设备／人员资源表、逐日热力图、压力／冲突、本次贡献／完整候选视角、正式覆盖、双方甘特过滤定位及完整返回。旧候选分析、值班台和试调同义资源读取已迁移，原算法统计仍保留实际来源。

资源／逐日CSV与XLSX沿同一scope；覆盖及冲突计数为原生数字，逐条“覆盖工序”“资源冲突”保留完整身份。最终日常437 passed／20 skipped，122必跑目标，Ruff通过；真实3次资源往返、浅深布局、100／125／150%原生缩放、热图键盘及四条交付入口通过。最终5个受影响案例的7文件、894业务行、16,239格、7,105数字格回读通过；当前56030/PID56365同库7运行34候选、正式v1和15行保持。

Python3.8.10核心20k任务／对象、4／6／8候选加基准，40,200资源日／对象跨块完整汇总通过；索引加整窗汇总1.745／2.451／3.179s，典型真实总览17.6／24.8／27.7ms。宿主、单次HTTP和Win7实际性能的范围分别记录；Win7及最终HEAD完整门禁沿第8阶段验收。

第3阶段为 `done / implementation_acceptance=passed / parent_acceptance=passed`，完整材料见 [第3阶段交接](../../features/2026-10-13-decision-resource-impact/decision-resource-impact-handoff.md) 与 [实施验收](../../features/2026-10-13-decision-resource-impact/decision-resource-impact-acceptance.md)。主对话独立复审通过且无新增返修，独立证据在 `evidence/decision-stage-acceptance/stage-03/`；第4阶段已派发，第5—8阶段维持planned。

### 2026-10-13 第4阶段实际交付

`decision-preparation-events` 完整实现实际排槽与运行需求账共用的准备／加工分解，保存永久工序证据，区分原需求目标及本次AJ执行目标／余量，并接入候选、正式最后来源、试调及旧同义消费者。新排、执行、完成、冻结、分件、共同工序、外协、普通未排与合法暂缓各按实际事实表达，旧分解／原标准缺项保持未知。

工种评价、原生插入惩罚与切换事件共用真实ID规则；完整非零内制设备序列建立前驱后按后序开始裁共同窗，点事件及同ID为0，未知身份是屏障。目录52项／`decision-preparation-v4`，准备及事件两页签、20／50稳定筛选分页、两侧甘特往返和CSV／XLSX完整9表／单资源逐日11表同scope；原算法保存统计独立。

实施验收通过：Python3.8.10日常461 passed／20 skipped、127目标与Ruff全通过；其后紧凑布局增量2项Node契约及10文件Chrome109构建通过。真实4次工序／事件往返、1392／1920深浅两页8张最终图、原生依据键盘及准备表125／150%缩放滚动通过，浏览器155加载本地资产。5案例7文件899行、42,897格／11,347数字及202个JSON安排原始回读通过。

最初2次受理分别因件别完整性、正式覆盖失败，原记录保留；静态核全部正式及件别覆盖后，最终31工序真实运行成功，4候选各30安排／31项账，新排准备14.5h、加工45.55h及实际切换3次。原7运行／34候选、正式v1／15行及参数保存，当前同库10运行／38候选。最终预览50306／PID62818，后续核对只读。

第4阶段为 `done / implementation_acceptance=passed / parent_acceptance=passed`，主对话独立验收通过且无新增返修，独立证据`evidence/decision-stage-acceptance/stage-04/`；第5阶段已派发，第6—8阶段保持planned。准确文件范围、直接入口、验收与原始证据见[第4阶段交接](../../features/2026-10-13-decision-preparation-events/decision-preparation-events-handoff.md)及[实施验收](../../features/2026-10-13-decision-preparation-events/decision-preparation-events-acceptance.md)。母独立验收记录由主对话维护，最终HEAD、clean-worktree、Win7实机及整体性能沿第8阶段。


### 2026-10-13 第5阶段实际交付

`decision-recommendation` 完整实现源头保存的精确选择／健康证据、三类推荐、搜索／可排／业务交付三轴、共同完成批次的交付取舍、3+3主要收益代价及全部52差值；旧值班台和试调消费者复用相同事实。原生展开并列、策略复用和真实剩余需求；五类支撑沿真实安排钻取甘特，聚合明细与甘特两层返回保持原第三候选／基准／筛选分页。推荐CSV96列、三表39／36／59列，完整比较12表／逐日14表合同同scope。

真实balanced运行保存4候选，各31安排、合法暂缓1道；主目标4个并列、完整评分1个最优，实际secondary_score裁决。健康3分覆盖raw最优，算法切换3对3，超期2→3、拖期284.61→301.85h（+17.24h／约6.0574%），四容差均实际通过。既有6／8候选的16策略字段、4永久引用展开核对一致。浅深1392／1920、原生125／150%、键盘、五类支撑与两条完整嵌套返回通过；7原始CSV／XLSX、2315业务行／137525格回读通过。采用只预检，恢复原生成目标后source_context_changed／409禁用确认，正式v1／15行保持。

用户追加全仓无用SHA和编号清理已完成：读快照与大DTO、缓存、预览、当前事实、断点输入／日历、物料行与临时展示键、构建清单及ZIP sidecar分别收敛到原范围、实际来源、原文或业务序号；真实持久回放、外部／维护文件核对和长期排程内容缓存保留原职责。初轮2个过时测试夹具已修，清理完成时Python3.8.10日常484 passed／20 skipped、133目标、77.52s、Ruff通过；10 payload Chrome109构建通过。

清理后的只读服务58804／PID77096已在返修时正常退出；当时4案例及正式辅助入口冷读、同scope快照复用／跨scope拒绝、新业务键实际筛选通过，9张业务表和34参数逐行相等。清理阶段新增排产、业务样例、采用与重复导出为0，原业务矩阵／7导出复用。累计47批／91工序／11运行／42候选／737任务；本P5只新增1批／1工序、1次真实运行。

第5阶段第一轮主对话独立验收要求P2-05-01、P2-05-02、P3-05-03返修，当前`done / implementation_acceptance=passed / parent_acceptance=passed`。已恢复默认真实主因和可视当前基准关系，13px／3+3在双宽／双主题及三项代价场景八组合均四完整候选；完成组各成员以独立anchor取完整批次，普通部分推荐仅DD-P-A一道未排，21批20+1／50 API及页面分页相等，remaining与基准甘特往返完整保存原第三查看和集合条件；交接graph2／graph3映射已修正。返修日常487 passed／20 skipped、134目标、77.06s、Ruff通过，随后局部UI的Node／Chrome109构建及两项离线资产增量通过；当前同库65050／PID41829，Chrome原生125／150%及恢复100%通过，9表完整行集、34参数和正式v1／15行与修复前相等，读取total_changes=0。返修新增排产、业务样例、采用和重复导出均为0，原失败记录保留。

完整材料见[交接](../../features/2026-10-13-decision-recommendation/decision-recommendation-handoff.md)、[实施验收](../../features/2026-10-13-decision-recommendation/decision-recommendation-acceptance.md)与[返修记录](../../features/2026-10-13-decision-recommendation/decision-recommendation-repair-01-fix-note.md)，原清理记录见`evidence/sha256-cleanup/summary.json`。母独立验收记录由主对话维护，第6阶段已派发、第7—8阶段保持planned；最终HEAD、clean-worktree、Win7实机与整体边界性能沿第8阶段。

主对话第5阶段返修独立复验passed，原证据保留。第6阶段首次采集／采样／永久来源／曲线／导出证据继续位于`evidence/decision-recommendation/phase-06/`，495 passed／20 skipped日常按未变范围复用。本轮返修当前done／implementation_acceptance=passed／parent_acceptance=passed；主对话已在最终54526／PID27118／main.js1791898902实测全部最后页面返修passed。44条新尝试事实、264差值、过程原件7083格与root6589业务格通过；计算与业务范围、工具栏与资源返回、基准与显式详情、整行过程比较、原生控件以及共同文案均有实际证据。balanced主因按保存贡献恢复总时长／等待各45.905小时改善，切当前基准逐字相同，1392四行完整且13px。最新Chrome109构建21:41:42／built10及资产3 passed／0.60s；本轮新增测试文件／函数0。一次必要新run只新增130行，1119旧行／7201字段、34参数及正式v1／15行保持。当前材料在`evidence/decision-recommendation/phase-06/repair-01/`，独立页面证据在`evidence/decision-stage-acceptance/stage-06-repair-01/`，见[交接](../../features/2026-10-13-decision-optimization-process/decision-optimization-process-handoff.md)、[实施验收](../../features/2026-10-13-decision-optimization-process/decision-optimization-process-acceptance.md)与[返修记录](../../features/2026-10-13-decision-optimization-process/decision-optimization-process-repair-01-fix-note.md)。母stage-acceptance已记第6阶段passed，第7正式派发；第8保持planned，最终HEAD、clean-worktree、Win7实机与整体性能沿第8阶段。

### 2026-10-14 第6阶段第二版原型正式接入

2026-10-14 用户已明确恢复实施，按第二版原型正式接入APS。当前第6阶段整页返修进行中，实施验收尚未完成、主对话验收changes_requested；第7在本阶段主验收后继续、第8等待派发。原型采用真实记录作交互依据，产品继续读取共同归档服务。 共同资源四粒度与夜休语义、完整事件阶梯和真实采样、交期／差异分工及全宽明细、归档Job范围和微秒时间源按已批准目标接入。新增公共字段见[设计补充](../../features/2026-10-13-decision-optimization-process/decision-optimization-process-design.md#5-2026-10-14-已批准的整页接入补充)，本轮证据入口`evidence/prototype-integration/2026-10-14/`。当前采用原54526隔离库，代码稳定后正常cold载入实际Python改动，保全原行和34配置；新排产／采用仅使用相关临时测试fixture，现场业务记录保持。

## 此前2026-10-14 整页接入首次实施交付

第6阶段第二版原型正式接入、P2-06-09候选卡和窄屏媒体布局已完成实施验收；主对话正独立验收，第7沿本阶段主验收依赖继续，第8等待前置阶段。用户追加的四份实际不同结果由DQ4-的12批48工序真实求解保存，六对安排均有变化，切候选/固定对照/推荐、当前风险、工序差异、资源四粒度和真实过程保持共同来源。当前实例49394/PID8243/main1791917435/CSS1791920118，产品已冻结。

日常136目标498 passed/20 skipped/Ruff有效；后续纯媒体CSS与帮助文案由最后构建、3资产、360真实界面和正常cold帮助入口补充。原九表1249行7869字段、34配置170字段、正式v1/15行保全；clock增加48与新工序身份原触发器相符。新增Python测试函数3分别承担四粒度、班内权威冲突、小时显示窗/导出关键契约，纯排版新增0。详见[本轮feature交接](../../features/2026-10-13-decision-optimization-process/decision-optimization-process-handoff.md)及 `evidence/prototype-integration/2026-10-14/integration-summary.json`；实施与主验收各有状态，A/B Git及后续C按用户顺序由主对话统筹。


## 2026-10-14 母验收六项返修实施交付

第6实施及母验收passed，第7已恢复先前派发。最终53871/PID44499/session96013/main1791922970/CSS1791920118，Python3.8.10；累计4次正常cold，返修新增运行/样例/采用/试调0。资源同侧警报与未知依据、精确区间小计、98/95唯一原生表头及键盘关闭返回，过程无改善全程、真实成员变化和旧可信全集规范化均已实际验证。4/4完整实线、6/7采样虚线、30/251ms两点平线及90%阈值下85.2%固定对照格通过；最后格高68，原null依据保持。

日常136目标498 passed/20 skipped/83.70s及全Ruff；最后兼容/主格密度由既有节点1passed、两Node、Chrome109 built10、资产3passed及4项真实回验补充，六组UIpassed。返修8原件含资源128业务行及过程36业务行/4836格，Root直接打开确认；原九表1249行7869字段/types及34参数、正式v1/15行在最后cold保持，clock158未再变化。原四份不同安排、23项页面、两档原生及其他未变证据继续复用。阶段依赖、最终HEAD/clean proof和A/B Git/C顺序保持，以[第6最新交接](../../features/2026-10-13-decision-optimization-process/decision-optimization-process-handoff.md)和`evidence/prototype-integration/2026-10-14/integration-summary.json`为准；母stage-acceptance由主对话维护。

## 2026-10-14 第7阶段最终交付与第8派发

第7实施与母验收passed，源头四项、三项界面及最后连续键盘焦点已闭环。当前52705／PID82711／main1791934561／CSS1791933089，Python3.8.10，3次正常cold；四来源历史、八类条件、保存目标与共同窗口、原生数量15列、同秒运行序号、空筛选和完整返回通过。最终CSV30×90、XLSX主业务619行／六表，2700条目格直接对实际API。原85表2633行／20444字段值及类型保留，日志表只追加3条对应启动审计，当前2636行；业务增量0。日常501 passed／20 skipped／2初次cold失败及原cold2／API4补验、H01—03与H04／最后CJS和实际UI分别记录，复用有效结果。详见[第7实施验收](../../features/2026-10-14-decision-history-trends/decision-history-trends-acceptance.md)及[交接](../../features/2026-10-14-decision-history-trends/decision-history-trends-handoff.md)。

第8已派发；本地方案沿原批准范围收口，当前先统一原内容比较与旧Schema／来源兼容，随后完成A01—A15、实际性能／取消／内存和整体完整门禁。过去第5的SHA清理成果是当时范围记录，仍存回执、存档、事实、搜索、维护与门禁的实际摘要计算；本阶段按现行授权完成这些剩余职责，保旧原文与永久引用。第8 feature与清单见[集成验收设计](../../features/2026-10-14-decision-integration-acceptance/decision-integration-acceptance-design.md)。


## 2026-10-14 操作者体验返修过程记录

按用户使用舒服、结果前置、原因按需、下一步清楚的要求，统一候选／资源／过程／历史及关联正式、试调和值班台入口。资源状态恢复低饱和度淡蓝／琥珀／红／灰，过程和采用绑定共同当前方案，历史差异缺项前置，并修复返回、范围分页和试调详情联动。四组按文件owner连续实施，原数学、事务、导出及迁移保全证据复用；后台性能独立推进，UI就绪后统一完整dirty门禁。[实施设计](../../features/2026-10-14-decision-integration-acceptance/decision-integration-acceptance-design.md#5-2026-10-14-已批准的操作者界面返修)。当前implementation_in_progress，母体验验收changes_requested，A／B Git与C顺序由主对话统一执行。

## 2026-10-14 最新第6／7通过与第8性能收口

主对话已在最终正常实例58240／PID3143亲自核对八候选、四候选对受理正式v1、返回运行记录→历史图及实际帮助；15条历史、5个原值点2／2／2／0／12和3／7缺项正常，console为空，公开健康身份与运行合同一致。第6／7实施、操作者UI和主对话验收均passed，主stage表已回写；上述过程记录保留旧changes_requested与历次返修事实。实施材料见[第6交接](../../features/2026-10-13-decision-optimization-process/decision-optimization-process-handoff.md)、[第7交接](../../features/2026-10-14-decision-history-trends/decision-history-trends-handoff.md)及[最终同库主验收](../../../evidence/decision-stage-acceptance/stage-08/final-cold-runtime/parent-review.json)。

2026-10-14用户最新决定后，第8及A非延期范围为done／implementation_acceptance=passed／parent_acceptance=passed。共同源、类型、台账、UI、迁移及原件保持，Gate09前16步及全量722 passed／36 skipped／0 failed复用；第17步15条启动器检查按用户决定在大改后统一测试，原failed manifest与核销门槛保持。4／6／8候选20k summary为3.6246／4.6823／5.2835秒，2秒目标未达，已交C按原范围收口。A源码与测试冻结，实施方仅整理文档及逐文件提交归属。材料见[第8交接](../../features/2026-10-14-decision-integration-acceptance/implementation-handoff.md)；A提交推送、B独立review/debug再提交推送、C算法U0—U6由主对话继续。
