---
doc_type: feature-acceptance
feature: 2026-05-12-collect-only-cache-output
status: accepted
summary: collect-only nodeid 输出协议和输入失效合同已完成，尚未接入真实门禁 runner
tags: [quality-gate, collect-only, cache]
---

# collect-only-cache-output 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-12
> 关联方案 doc：`codestable/features/2026-05-12-collect-only-cache-output/collect-only-cache-output-design.md`

## 1. 接口契约核对

**接口示例逐项核对**：

- [x] `build_collect_nodeids_payload(stdout, pytest_version=..., collect_stdout_log_path=...)`：从 stdout 生成 nodeids、count、hash、by_file 和 stdout hash。
- [x] `write_collect_nodeids(payload, repo_root=...)`：写入 `evidence/QualityGate/collect_nodeids.json`。
- [x] `load_collect_nodeids(repo_root=...)`：读取 collect nodeids JSON 对象。

**名词层"现状 → 变化"逐项核对**：

- [x] 新增 `tools/long_gate_collect.py`。
- [x] `pytest_collect_all` entry 已声明 collect 输入范围、环境 key 和输出文件。
- [x] 复用判定继续使用 PR-1 的 `decide_reuse()`，本 feature 不新增 runner 分支。

**流程图核对**：

- [x] collect stdout → parse nodeids → by_file → nodeid_hash → collect_nodeids payload → success cache output_files hash，代码和测试都有实际落点。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] collect stdout 可生成稳定 nodeid 输出。
- [x] `collect_nodeids.json` 被 success cache 当成输出文件校验。
- [x] 新增/删除测试文件、修改 conftest 会让指纹变化并失效。

**明确不做逐项核对**：

- [x] 在本 feature 的提交边界内未修改 `scripts/run_quality_gate.py`；后续 PR-3 已把 collect-only cache 接入 runner。
- [x] 未执行 pytest collect。
- [x] 在本 feature 的提交边界内未新增 CLI 参数；后续 PR-3 已新增 `--long-gate-cache` 系列参数。

**关键决策落地**：

- [x] 输出 hash 来自 collect stdout。
- [x] 输入范围由 manifest entry 声明。
- [x] 当前阶段只做 helper 和测试，不做 runner 集成。

## 3. 验收场景核对

- [x] **S1**：collect stdout 含多个 nodeid → 输出 nodeids、count、hash、by_file 正确。
  - 证据来源：`tests/test_long_gate_collect_cache.py`。
  - 结果：通过。

- [x] **S2**：输入没变，success cache 中的 `collect_nodeids.json` hash 匹配 → `decision=reuse`。
  - 证据来源：`tests/test_long_gate_collect_cache.py`。
  - 结果：通过。

- [x] **S3**：新增测试文件 → `decision=run`，invalidated_by 包含新增文件。
  - 证据来源：`tests/test_long_gate_collect_cache.py`。
  - 结果：通过。

- [x] **S4**：删除测试文件 → `decision=run`，invalidated_by 包含删除文件。
  - 证据来源：`tests/test_long_gate_collect_cache.py`。
  - 结果：通过。

- [x] **S5**：修改 `tests/conftest.py` → `decision=run`，invalidated_by 包含 conftest。
  - 证据来源：`tests/test_long_gate_collect_cache.py`。
  - 结果：通过。

## 4. 术语一致性

- `collect-only`、`collect_nodeids`、`pytest_collect_all` 和 roadmap 术语一致。
- 未引入新的 runner 开关名称。

## 5. 架构归并

- [x] 不需要更新 `codestable/architecture/ARCHITECTURE.md`。本 feature 只补质量门禁辅助输出协议。

## 6. requirement 回写

- [x] 无 requirement 回写。本 feature 是技术工具输出协议，不新增用户可见业务能力。

## 7. roadmap 回写

- [x] 已把 `codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `collect-only-cache-output` 改为 `done`。
- [x] 已把 roadmap 主文档第 5 节对应条目同步为 `done`，并补变更日志。
- [x] 已运行 CodeStable YAML 校验。

## 8. AGENTS.md / CLAUDE.md 候选盘点

- [x] 无候选。本 feature 没暴露需要写入仓库级代理规则的新约束。

## 9. 遗留

- 下一步 `quality-gate-runner-collect-cache` 才会把 collect-only success cache 接入 `scripts/run_quality_gate.py`。
- 当前 helper 不主动执行 pytest collect，调用方必须传入已完成命令的 stdout。
