---
doc_type: roadmap
slug: scheduler-global-optimizer
status: implemented-validated
created: 2026-09-12
last_reviewed: 2026-09-13
tags: [optimizer, quality, performance, python38, win7]
---

# 当前算法能力与效率实施批次

## 授权、基线和范围

用户在本轮全面只读研究后要求“全部都做，多并发 agent 全力全速推进”。本文件管理已报告项目的连续实施，不重新要求相同开始授权。原工作区干净，HEAD 为 `afc0551ed15ac0d8aceca63f1d950ebe8f9b0e8b`；原完整源码已通过 `git archive` 冻结至 `/private/tmp/aps-algorithm-implementation-20260912/base-source`。

所有业务数据实验使用独立临时样例，不连接或写入原业务数据库。保持 Python 3.8、Win7 x64、离线交付、当前硬约束、严格错误与公开摘要边界。依赖升级、设备班次新模型、跨日效率语义升级、安装发布不属于本次已报告清单。用户没有要求 Git 提交，主工作区不自动提交。

## 模块拆分与逐项清单

| 编号 | 项目 | 实现归属 | 验收要求 | 状态 |
| --- | --- | --- | --- | --- |
| A | 外层统一预算、阶段份额、多起点安全去重 | optimizer/run | 真实入口覆盖与受控时钟；已启动SGS可完成，超时/跳过如实记录 | 已实现并定向验证 |
| B | 插入位置增量换型、稀缺机人分配 | algorithm_runtime/greedy | 4次换型降到2次的回归；稀缺资源反例；fixed/seed/piece保持 | 已实现并定向验证 |
| C | SGS增量评分、已选时隙证书、纯字符串日期复用 | greedy dispatch | 原生路径评分数下降；动态输入/回调/同长变更保留原路径；真实工作台启用 | 已实现并定向验证 |
| D | 有界多轮精英修补、工序/关键块/资源邻域 | graph-ready repair | 全部新候选由真实SGS生成时间；DAG/资格/冻结与总预算不被绕过 | 已实现并定向验证 |
| E | 四目标候选生成、工序级剩余负担与ready偏移 | graph-ready features | 保留基线候选；piece/合并外协不重复计量；毛产能口径不擅改 | 已实现并定向验证 |
| F | 旧比较真实总耗时、正式repair、矩阵分片 | benchmark/tools | 同预算真实时钟；旧不可比基线显式拒绝；矩阵不拆成两轮fixture | 已实现并定向验证 |
| G | 完整入口矩阵、独立tiny oracle、基线生命周期 | tests support/CLI | 四目标完整向量与可行性；完整搜索耗时；独立oracle限定证明范围 | 已实现并定向验证 |
| H | 同一只读快照消除重复指纹 | workbench run | 组合路径私有连续调用；独立prepared调用仍检查stale；无写库 | 已实现并定向验证 |
| I | 线性图影响计数、权重无关投影、评分合法化复用 | graph preparation | 链和菱形独立计数；候选容器隔离；非法字段仍显式失败 | 已实现并定向验证 |
| J | 跨设备、人员、停机连续忙段闭包 | busy-block runtime | 微小空隙/工作窗/效率/异常不变；交错占用显著减少estimate次数 | 已实现并定向验证 |
| K | 公共预算摘要、测试注册、集成质量及性能对照 | Main | 安全聚合字段、显式注册、冻结与定向验收完成；整仓门禁未完成 | 已定向验收；按用户要求停止追加门禁 |

选中结果二次基础payload校验属于H的次要检查项；若证书成本大于其开销，可保留原校验并记录实测否定理由，不用复杂缓存替代廉价可靠校验。所有项目都需有实现、测试或明确的实验处置，不能无声漏掉。

## 跨模块接口合同

1. **预算**：`SearchBudget(clock, started_at, deadline, outer_deadline, assigned_seconds)` 是单次候选冻结值；外层按同一monotonic时钟分配剩余份额，`optimize_schedule(..., search_budget=None)` 接受可选合同。图候选继续消费同一clock/deadline。配置秒数与实际分配的 `assigned_time_budget_ms` 分开报告；跳过不等于完成，首次可行解不靠构造假结果兜底。
2. **资源质量状态**：保持尾工种映射兼容，并增加真实时间邻接数据；`initialize_resource_quality(state, sorted_ops, resource_pool)` 在run内初始化，所有seed/排入/失败更新由状态写入方统一完成。`certificate(machine_id)` 为评分缓存提供完整内容，而非id/长度。稀缺度只能在合法资源组合中择优，不可改变资格数据。
3. **增量评分**：只有认证原生日历/输入和完整相关状态内容一致才复用成功评分。`CalendarService.certified_sgs_policy_snapshot(operator_id)` 可返回纯内容证书，不能认证时返回None并继续一般路径。选择后仍通过正式dispatch，输入或资源变化使证书失效。只缓存成功的exact-str日期解析，不缓存错误或任意对象转换。
4. **图搜索决策**：`repair_decision` 只包含工序/批次优先序与合格资源override，不含新排程时间。`evaluate_graph_ready_candidate(..., repair_decision=None)` 用生产SGS真实解码；固定工序/资源/种子不能改。总候选、轮数、无改善与deadline必须共同终止搜索，同输出不能计为改进。
5. **目标特征**：profile/features显式接收 `objective_name` 与可选 `graph_ready_context`。后继工作量沿真实DAG唯一计量，前置偏移按最长路径；piece与合并外协沿现有身份/计量规则。缺少必要piece图不猜线性依赖。
6. **只读快照**：生产组合路径在同一私有连续函数内prepare后立刻计算，中间不暴露prepared对象。公开独立prepared接口仍全量校验。沿用已有SQLite只读事务，不新增防伪token或全局缓存，不移除执行态/额外payload保护。
7. **图准备**：缓存只覆盖同一comparison内权重无关的合法输入，返回可变容器独立拷贝。链专用O(N+E)指标必须先证明链结构，一般DAG继续精确去重。一次规范化同时生成key与bonus，保留非法输入错误。
8. **忙段闭包**：原生连续占用可跨三资源组延伸，不能跨任何真实空隙或日历证书边界。自定义方法/序列/日期或abort保持旧查询路径；索引现有内容快照、追加证明和错误时机继续有效。

## 验证及执行依赖

- 本任务的正式测量按序执行并记录机器背景负载；用户明确不要求整机100%零其他负载。driver的contended仅作环境限定，不能仅凭单次背景进程样本否决实际产品/180秒容量通过，也不因此放宽真实质量或容量阈值。
- A提供统一预算，D/E使用既有deadline并行开发；B提供资源状态内容，C负责评分与派工接线。F/G独立开发量尺，K统一注册，防止共享注册冲突。
- G的端到端量尺先在冻结旧源和新源分别运行，再在相同机器/输入/预算下比较；计时范围或schema改变不能拼接成提速比例。
- J/C/I/H属于性能路径，要求适用输入的完整结果等价；B/D/E属于质量路径，保留可行解并比较完整目标向量，任何退化必须定位后处理。
- 各模块、整合定向测试和静态结构检查已执行。最终主仓 `scripts/run_quality_gate.py` 仅guard预检退出，长测试未启动；8个已知untracked测试已intent-to-add纳入且字节不变。按用户最新要求停止扩大验证，不重跑整仓门禁，保留未完成状态。
- 主工作区有本轮未提交修改时，全门禁只能记录dirty/unbound结果，不能声称最终HEAD clean-worktree proof。基线生成同样不得伪造clean来源或把更新基线当作消除退化的方法。
- 原5000工序、四方案容量要求的180秒端到端阈值保持；新算法质量与性能证据分开报告。一次实验的耗时不作最坏情况保证，也不代表Win7实机结果。

## 起始实测

- 旧核心矩阵：8/8通过，254次真实解码，总计量17.142856秒，来源clean且HEAD绑定；快照 `/private/tmp/aps-algorithm-research-20260912-matrix.json`。
- 旧1000工序/4方案profile：20.206061秒（cProfile），285150次评分、289150次时隙估算；四方案各1000行，临时数据不变。
- 旧工作台1000工序、5秒预算：8.865507秒，计划4、完成2、跳过2。它不是严格超时违约证明，说明预算份额和搜索机会存在空间。
- 插空微例：自动M1为4次换型，固定M2为2次换型，时间相同、失败工序均0。

## 2026-09-13 收尾结果

稳定回执见[最终README](../../../evidence/algorithm-capability-efficiency/2026-09-13-final/README.md)和[summary.json](../../../evidence/algorithm-capability-efficiency/2026-09-13-final/summary.json)；41份原始回执与哈希清单一并归档。

- 实施和定向验证完成，最终证据以resume2/resume2b为准：完整入口20例、核心8例完整比较及native20通过；历史质量失败全部保留，不修改基线。
- 普通1000工序四方案六次完整payload一致，中位10.815770459→10.744741417秒，约-0.66%，只表述基本持平；两次5000工序四方案容量89.381380042/89.475103292秒，均20000任务持久化、72非运行表和重启数据保留通过，原180秒阈值保持。
- H选中payload缓存经测量后拒绝，原校验保留；A最终按不同parent计top_k，同parent basis变体共享8项邻域额度；E基础/增强特征明确并存；C保持首次导入/动态getter/自定义metaclass边界。
- 最终整仓门禁未完成，按用户要求不再追加长跑；不得称clean/full proof，不升级历史ALNS项目。完整来源与限制见[统一验收](../../features/2026-09-12-algorithm-capability-efficiency/algorithm-capability-efficiency-acceptance.md)。
