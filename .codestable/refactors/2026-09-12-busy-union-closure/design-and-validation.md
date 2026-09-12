---
doc_type: refactor-design
refactor: 2026-09-12-busy-union-closure
status: approved
scope: Certified native slot occupancy across machine, operator and downtime groups
summary: Extend continuous occupied coverage across resources without re-estimating at every alternating boundary.
---

# 跨资源连续忙段闭包

- 授权：用户在当前算法研究之后明确要求“全部都做，多并发 agent 全力全速推进”。
- 基线：`afc0551ed15ac0d8aceca63f1d950ebe8f9b0e8b`；源树已冻结于仓库外临时目录。
- 根因：每一资源组已合并连续占用，但三组之间交替覆盖仍反复回到时隙估算器。
- 实现：先保留原有每组一次查询。仅当纯原生索引、时间值及恒定日历窗口已经认证时，继续查找跨资源连续覆盖的最远边界；遇到任意真实空隙、工作窗末尾即停止。
- 索引证书：只接受普通 list/tuple 中的普通二元 tuple 和 naive datetime；使用索引现有“查询期间不得修改输入”的合同。SGS 复用索引持有内容快照，同长修改仍通过已有内容比较建立新索引。追加派生必须先通过既有原生前缀证明。
- 一般路径：自定义索引、替换 covered_end 方法、日期子类、序列子类、abort、非原生日历继续原先单组查询。没有更改真实完工时间、截止解释、日历效率和首个异常时序。
- 局部验证：`tests/algorithm/test_busy_union_closure.py`、`tests/algorithm/test_busy_block_native_equivalence.py`、`tests/algorithm/test_busy_block_boundaries.py` 共 **112 passed，7.61 秒**。交错连续忙段的真实估算次数由 73 次降为 2 次，排程起止时间完全一致；微秒空隙、跨日效率、非原生输入与被覆盖方法均有边界测试。
- 独立复核：对 120 组三资源随机案例及乱序、零长、反向、touching 边界做纯内存旧新差分，结果一致。随后将 `advance_busy_block` 中认证窗口与可延伸条件按职责拆出，官方局部复杂度和体量扫描通过。
- 验收边界：以上为未提交修改上的局部回归与有限差分，不是完整门禁、独占性能或 Win7 实机证明；统一整合、容量与来源回执见本批次主验收记录。
