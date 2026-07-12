---
doc_type: issue-analysis
issue: 2026-07-11-dependency-proof-rebuild-and-closure
status: confirmed
root_cause_type: stale-generated-evidence
related: [dependency-proof-rebuild-and-closure-report.md]
roadmap: dependency-cycle-governance
roadmap_item: dependency-proof-rebuild-and-closure
tags: [callgraph, import-cycle, baseline, hashes, reproducibility]
---

# 依赖治理终态证据漂移根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `.codestable/checkup/latest/callgraph/*.json` | 生成于第 7、8 项最终工具冻结前，不能代表当前 KISS 确信边口径。 |
| `.codestable/checkup/import_cycles_production_baseline.json` | 生产 scope v2 基线需按 alias 重绑定修复后的最终扫描结果收敛。 |
| `.codestable/checkup/import_cycles_with_tests_baseline.json` | 含测试 scope v2 基线需独立核对，不能与生产基线互换。 |
| `.codestable/checkup/baseline.json` | 旧数字、旧哈希和已删除 type-index 路径混在同一总入口。 |
| `.codestable/checkup/README.md`、依赖治理 architecture/audits/issues | 人工事实文本仍引用多个历史中间口径。 |

## 2. 失败路径还原

**正常路径**：冻结工具 → 调用图临时双跑一致 → 双 scope import 扫描并人工解释差异 → 生成候选快照/基线 → 一次性写入正式证据 → 最后复算 baseline 数字与 artifact SHA → 文档同步 → 提交后干净 HEAD 完整门禁。

**当前失败路径**：首次工具接线后先写入快照/基线/数字 → 后续审查发现 alias 假环、typed 假确信和静默 UTF-8 → 第 7、8 项继续修改工具，但按合同没有提前刷新证据 → 正式文件因此保留旧口径，哈希与当前工具自然漂移。

**分叉点**：生成型证据与工具版本没有在最终冻结后统一重建。前两项选择“不提前刷新”是正确保护，但必须由本项完成最终收口。

## 3. 根因

**根因类型**：生成证据陈旧，不是新的业务逻辑缺陷。

**根因描述**：调用图快照、循环基线、总哈希和事实文档是同一工具版本的派生物；第 7、8 项有意只修语义、不更新派生物，因此当前证据链缺少一次原子式重建。若只改其中一层，下一层仍会保留旧数字或旧哈希。

**是否有多个根因**：单一主因，但表现为四层漂移：机器快照、门禁基线、总哈希、人工事实文档。

## 4. 影响面

- **影响范围**：依赖治理证据的可复现性、正式门禁输入哈希、审计事实和 A1 起点边集。
- **潜在受害者**：scheduler A1-A6、后续架构审查、任何引用 checkup 数字的报告。
- **数据完整性风险**：无业务数据风险；风险是错误的治理结论。
- **提交风险**：当前 45 条工作区记录均属于同一未提交治理批次或既有改动，未取得提交授权前只能做 dirty-worktree 局部证明。
- **严重程度复核**：维持 P1。

## 5. 修复方案

### 方案 A：直接覆盖快照和基线

- **做什么**：运行生成命令后立即写正式路径，再让测试变绿。
- **优点**：快。
- **缺点 / 风险**：无法证明差异来自已知语义修复，可能把新误报或漏报一起基线化。
- **结论**：拒绝。

### 方案 B：临时双跑、人工核差异、原子式重建（选定）

- **做什么**：
  1. 冻结第 7、8 项工具代码。
  2. 调用图写两个独立临时目录并逐文件 SHA 比对。
  3. 生产/含测试扫描分别输出 JSON 和候选 v2 基线；逐项比较 SCC、圈内边、unresolved。
  4. 差异全部解释后，才覆盖正式调用图快照与双基线。
  5. 工具和证据不再变化后重建 `baseline.json` 数字及 artifact SHA。
  6. 同步 README、architecture、audits、旧工具 issue 和本 issue。
  7. 跑定向回归、正式双 scope、哈希自检和可执行质量门禁。
  8. 只有用户授权提交并在提交后干净 HEAD 完整门禁成功，才标记 clean-worktree proof 和 roadmap completed。
- **优点**：每层证据来源可追溯，不靠刷新掩盖未知差异。
- **缺点 / 风险**：文件多、需要严格保持生成顺序；任一工具或证据再变都要从双跑重来。

### 方案 C：保留旧证据，只在文档写“已过期”

- **做什么**：不刷新机器文件，A1 继续使用临时输出。
- **优点**：不改生成物。
- **缺点 / 风险**：正式门禁、哈希和人工事实长期分裂，无法满足 roadmap 最小闭环。
- **结论**：拒绝。

### 确认

采用方案 B。用户明确要求进入 `dependency-proof-rebuild-and-closure`，即授权执行提交前的受控证据重建；`git commit`、推送和 clean HEAD 最终证明仍需单独明确授权。
