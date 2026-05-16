---
doc_type: feature-acceptance
feature: 2026-05-12-long-gate-cache-core
status: accepted
summary: 长耗时门禁输入指纹和成功缓存核心已完成，尚未接入真实门禁执行
tags: [quality-gate, cache, fingerprint]
---

# long-gate-cache-core 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-12
> 关联方案 doc：`.codestable/features/2026-05-12-long-gate-cache-core/long-gate-cache-core-design.md`

## 1. 接口契约核对

**接口示例逐项核对**：

- [x] `fingerprint_files(paths_or_patterns, repo_root)`：记录路径 hash、内容 hash 和文件列表。
- [x] `fingerprint_entry(entry, repo_root)`：合成 command、files、environment 三类组件。
- [x] `write_success(entry, fingerprint, command_result, output_files, repo_root=...)`：写入 success cache、stdout/stderr log 和 output file hash。
- [x] `decide_reuse(entry, current_fingerprint, repo_root=...)`：返回 `reuse` 或 `run`，并给出原因和失效项。

**名词层"现状 → 变化"逐项核对**：

- [x] 新增 `tools/long_gate_fingerprint.py`。
- [x] 新增 `tools/long_gate_cache.py`。
- [x] `.gitignore` 新增 `evidence/QualityGate/long_gate/`。

**流程图核对**：

- [x] entry → fingerprint_entry → current fingerprint → decide_reuse → success cache 判断，代码中均有实际落点。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 文件集合指纹能响应新增、删除、修改。
- [x] 上次成功且所有 hash 都匹配才允许 reuse。
- [x] 损坏缓存和缺字段只返回 run，不删除缓存。

**明确不做逐项核对**：

- [x] 在本 feature 的提交边界内未修改 `scripts/run_quality_gate.py`；后续 PR-3 已接入 runner。
- [x] 在本 feature 的提交边界内未新增 `--long-gate-cache`；后续 PR-3 已新增 CLI。
- [x] 未实现 collect-only nodeid 输出。
- [x] 未执行真实质量门禁命令。

**关键决策落地**：

- [x] D1：文件指纹只读传入 scope。
- [x] D2：缓存损坏绕过并解释。
- [x] D3：success cache 目录固定在 `evidence/QualityGate/long_gate/`，并已加入 `.gitignore`。
- [x] D4：测试使用 `tmp_path`，不写真实仓库 evidence。

## 3. 验收场景核对

- [x] **S1**：同一 entry、同一文件输入、同一环境 → 指纹 hash 稳定。
  - 证据来源：`tests/test_long_gate_cache.py`。
  - 结果：通过。

- [x] **S2**：新增/删除/修改输入文件 → 文件集合 hash 变化。
  - 证据来源：`tests/test_long_gate_cache.py`。
  - 结果：通过。

- [x] **S3**：上次成功且 command/fingerprint/log/output 全匹配 → `decision=reuse`。
  - 证据来源：`tests/test_long_gate_cache.py`。
  - 结果：通过。

- [x] **S4**：上次失败、timeout、interrupted、partial write → `decision=run`。
  - 证据来源：`tests/test_long_gate_cache.py`。
  - 结果：通过。

- [x] **S5**：cache JSON 损坏或缺字段 → `decision=run`。
  - 证据来源：`tests/test_long_gate_cache.py`。
  - 结果：通过。

- [x] **S6**：stdout/stderr log 或 output file 缺失 → `decision=run`。
  - 证据来源：`tests/test_long_gate_cache.py`。
  - 结果：通过。

- [x] **S7**：command args 或 schema version 变化 → `decision=run`。
  - 证据来源：`tests/test_long_gate_cache.py`。
  - 结果：通过。

## 4. 术语一致性

- `fingerprint`、`success cache`、`CacheDecision` 只在新增 long gate 工具层使用。
- 未改现有 `QualityGate` manifest / receipt 证明字段语义。
- 本 feature 边界内未新增 `long_gate_cache` CLI 开关，避免和后续 runner 接入阶段混淆；当前工作区后续 PR-3 已接入。

## 5. 架构归并

- [x] 不需要更新 `.codestable/architecture/ARCHITECTURE.md`。本 feature 只是质量门禁辅助库，不改变正式质量门禁入口。

## 6. requirement 回写

- [x] 无 requirement 回写。本 feature 是技术工具底座，不新增用户可见业务能力。

## 7. roadmap 回写

- [x] 已把 `.codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `long-gate-cache-core` 改为 `done`。
- [x] 已把 roadmap 主文档第 5 节对应条目同步为 `done`，并补变更日志。
- [x] 已运行 CodeStable YAML 校验。

## 8. AGENTS.md / CLAUDE.md 候选盘点

- [x] 无候选。本 feature 没暴露需要写入仓库级代理规则的新约束。

## 9. 遗留

- 下一步 `collect-only-cache-output` 要真正把 collect-only stdout 解析成 `collect_nodeids.json`，并接入这些核心库。
- 在本 feature 的提交边界内，success cache 核心尚未被 `scripts/run_quality_gate.py` 调用；当前工作区后续 PR-3 已调用 collect-only success cache。
