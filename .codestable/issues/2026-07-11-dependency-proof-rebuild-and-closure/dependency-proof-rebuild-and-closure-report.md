---
doc_type: issue-report
issue: 2026-07-11-dependency-proof-rebuild-and-closure
status: confirmed
severity: P1
summary: 调用图快照、双循环基线、checkup 哈希和事实文档仍绑定旧工具口径，不能形成可复现终态证明
roadmap: dependency-cycle-governance
roadmap_item: dependency-proof-rebuild-and-closure
tags: [callgraph, import-cycle, baseline, reproducibility, quality-gate]
---

# 依赖治理终态证据漂移问题报告

## 1. 问题现象

第 7、8 项语义修复完成后，仓库中的正式证据仍是旧工具口径：

- `.codestable/checkup/latest/callgraph/` 尚未按“typed 边归零、严格 UTF-8、三元调用点”重新生成。
- 两份 import-cycle v2 基线仍是 alias 重绑定修复前生成物；虽然正式门禁当前没有新增债务，但基线还未收敛到最终工具结果。
- `.codestable/checkup/baseline.json` 记录旧调用图数字和旧 artifact SHA，并仍引用已删除的 `callgraph_type_index.py`。
- checkup README、循环依赖审计、模块架构审计和旧工具 issue 中仍有 7314/25299/11320/1198、749/1442 等旧数字。
- 当前工作区有大量未提交改动，不能把任何本机重跑包装成 clean-worktree proof。

## 2. 复现步骤

1. 用当前冻结的调用图工具输出到独立临时目录。
2. 将临时目录的 10 个 JSON 与 `.codestable/checkup/latest/callgraph/` 逐文件比较，观察快照差异。
3. 对 `.codestable/checkup/baseline.json.artifact_sha256` 逐项复算，观察工具、快照和双基线哈希漂移以及已删除文件引用。
4. 分别运行生产和“生产+测试”循环扫描并生成候选 v2 基线，对比仓库双基线中的 SCC、圈内边和 unresolved 签名。
5. 查看 README、审计和旧工具 issue，观察其数字仍指向前两轮临时口径。

复现频率：稳定。

## 3. 期望 vs 实际

**期望行为**：

- 工具冻结后，调用图连续输出到两个独立临时目录，文件集合和逐文件 SHA256 完全一致。
- 双 scope import 扫描的 SCC、圈内边和 unresolved 差异逐项解释后，才允许受控刷新基线。
- 正式快照、双基线、`baseline.json`、README、审计与 issue 数字一次性同步。
- `artifact_sha256` 每一项都与最终文件匹配，记录数字与重跑结果一致。
- 只有提交后的干净最终 HEAD 完整质量门禁成功，才能声称 clean-worktree proof。

**实际行为**：

- 当前证据分属多个工具阶段，快照、基线、哈希和文档互相漂移。
- 当前只能证明第 7、8 项局部合同通过，尚不能证明最终证据可重复。

## 4. 环境信息

- 分支：`feat/default-light-improve-sgs`
- 起点 HEAD：`cd6cdf43798e3c6321370e4fceb7150bbe4cef3c`
- 起点工作区：45 条 `git status --short` 记录。
- 相关范围：
  - `.codestable/checkup/latest/callgraph/*.json`
  - `.codestable/checkup/import_cycles_*_baseline.json`
  - `.codestable/checkup/baseline.json`
  - `.codestable/checkup/README.md`
  - 依赖治理相关 architecture / audits / issues / roadmap 文档
- 明确不做：本 issue 不修改业务代码、不实施 A1、不刷新 dead-code 基线、不推进历史决定考古水位线。

## 5. 严重程度

**P1**。这是 A1 前置的最终可信度阻塞：证据不闭环时继续结构重构，会让验收建立在漂移快照上。它不是业务运行故障，但必须先于 scheduler A1 处理。

## 备注

用户已接受第 8 项并明确要求进入 roadmap 第 9 项。本报告按既定终态重建合同确认；最终 clean HEAD 门禁仍需要后续明确的提交授权和干净工作区条件。
