---
doc_type: audit-finding
audit: 2026-10-05-redundant-guards
finding_id: "2.1-2.8"
nature: performance
severity: P2
confidence: high
status: fixed
---

# 排产档案嵌套及同快照重复取得事实

修复前，`WorkbenchRunFactsRepository.admission_facts` 仅跳过 RUN_TABLES；候选试调 `prepare_base` 把旧 capture 嵌入 admission，后续 run 又复制 trial 表。无新 SHA 的内存夹具已证明嵌套结构增长，当前生产容量与是否达到 64 MiB 尚未测量。

同快照还存在未消费的组合计算指纹、resolver/preflight 双扫描、comparison 5 次 GenerationFacts/3 次 AdmissionBaseline、同归档连续完整性核验、试调双编码、各候选重复固定分件事实。各项应共享一次可信原事实，再做各自结果投影；正式采用/最终写事务的跨时间重核保留。

实施不能静默修改历史档案、去掉类型规范、返回旧 head revision，或将候选特有可行性判断缓存为永久结果。旧 prepared API 的新鲜度合同和真实不可变档案完整性仍有效。


## 实施结果

已完成对应源头修复；历史档案、公开契约及必要边界保留。具体实现、实际回归与日常门禁结果见 [修复记录](../../issues/2026-10-05-redundant-guards/redundant-guards-fix-note.md)。
