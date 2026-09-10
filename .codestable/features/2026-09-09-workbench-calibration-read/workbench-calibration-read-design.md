---
doc_type: feature-design
feature: workbench-calibration-read
status: approved
summary: 按已批准迁移契约D05实现校准只读后端，未知模板实例来源不猜关联。
tags: [workbench, calibration, read-only]
roadmap: workbench-prototype-migration
roadmap_item: wb-calibration
---

# 0. 依据与术语

本轮用户授权只读建议、详情、CSV/XLSX及专属测试，不授权公用schema、路由注册、历史事实修改。
业务依据为 `workbench-contracts.md` §8.2/D05 和本轮已批准实施要求，不重新扩大审批范围。
`suggestion_ref` 直接使用永久模板工序引用，具体建议内容由 `snapshot_ref` 绑定。
`sample_ref` 是执行工序永久引用，不是报工次数；报工更正引用另外完整保留。

# 1. 决策与现状

近20个有效整道完工实例、至少5个；每样本=逐次有效加工小时合计/权威累计完成数量，中位数。
严格 `abs((suggested-old)/old) > 0.2`，旧值0或未知时偏差率未知，不生成无穷值。
执行事实只调用 `ExecutionLedgerService.load/project_loaded`。不从原型SEED或事件起止跨度补数据。
现有 `BatchOperations` 以及 `batch_operations.insert_operation`、`batch_template_ops._build_batch_op_payload`
没有持久化来源模板永久引用和复制时修订。即使 part_no/seq/工种/工时全相同，也不能作为关联证据。
当前生产入口只输出“数据不足”，详情展示同零件待核对实例并明确它们不是已关联模板样本。
没有假定新schema存在，也不接受HTTP传入lineage。内部算法类型单独允许测试已证实来源的合同。
采纳及锁定恒为false，不调用普通模板工时update。未来来源关系与采纳事务由公用层另行接入。

# 2. 编排与职责

Flask参数校验 -> 读取同一SQLite事务 -> 原模板/永久身份 -> 唯一执行投影 -> 排除证据 -> 建议统计 -> 快照 -> 分页/详情/导出。
DTO、只读repository、样本核验、统计、事实读取、查询编排、导出和独占路由分文件，避免万能服务。
模板上限10000、实例上限10000、执行修订沿用共享50000上限；拒绝超限，不截断。
范围含搜索、零件、来源、状态、偏差、排序和页大小；跨页、详情、导出必须带snapshot_ref。
快照绑定范围、源内容及as_of；变更后显式snapshot_stale；不创建持久化快照表。

# 3. 验收契约

- 不足5/恰好5/近20/严格大于20%/0与未知/异常/暂停/修订不一致/来源缺失。
- 真实SQLite和共享执行投影；来源不可证实则生产列表没有伪造可用样本。
- 真实Flask分页、搜索、详情、快照失效、CSV/XLSX及公式注入保护。
- 读取PRAGMA query_only，所有历史业务表和schema前后一致。
- 大容量无N乘M实例投影，超限和损坏明确失败，Python3.8兼容性验证。

# 4. 集成边界

仅新增用户独占写域；路由注册、测试registry、最终构建和架构/roadmap总入口由主代理负责。
不能把本子任务只读交付标为整个wb-calibration采纳闭环已完成。
