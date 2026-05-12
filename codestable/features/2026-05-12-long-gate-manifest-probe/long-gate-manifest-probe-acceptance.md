---
doc_type: feature-acceptance
feature: 2026-05-12-long-gate-manifest-probe
status: accepted
summary: 长耗时门禁清单探测工具已完成，未接入真实门禁执行循环
tags: [quality-gate, manifest, receipts]
---

# long-gate-manifest-probe 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-12
> 关联方案 doc：`codestable/features/2026-05-12-long-gate-manifest-probe/long-gate-manifest-probe-design.md`

## 1. 接口契约核对

**接口示例逐项核对**：

- [x] `build_long_gate_manifest(repo_root)`：实际调用 `tools.quality_gate_shared.build_quality_gate_command_plan()`，返回的 entry display 顺序和真实 command plan 一致。
- [x] `classify_quality_gate_command(command)`：能识别 collect-only、full-test-debt、版本探测、ruff、pyright、architecture、debt ledger、quickref 等确定命令。
- [x] `build_manifest_from_quality_gate_plan(command_plan, receipts=None, repo_root=...)`：按 command plan 生成 schema_version、plan hash、entries 和 warnings。

**名词层"现状 → 变化"逐项核对**：

- [x] 新增 `tools/long_gate_manifest.py`，没有改动 `tools/quality_gate_shared.py` 的真实计划生成逻辑。
- [x] 新增 `LONG_GATE_SCHEMA_VERSION = 1`。
- [x] 新增本地 receipt 读取函数，旧 receipt 缺少 `duration_s` 时显示 `duration_unknown`。

**流程图核对**：

- [x] CLI 调用 → 读取真实 command plan → 分类 entry → 可选读取本地 receipts → 打印清单，代码中均有实际落点。

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] 清单来自真实 command plan：`tests/test_long_gate_manifest.py::test_build_long_gate_manifest_uses_real_quality_gate_plan` 已锁住 spy 调用和 display 顺序。
- [x] 输出包含当前主要门禁分类：`tests/test_long_gate_manifest.py::test_manifest_contains_current_quality_gate_long_entries` 已覆盖。
- [x] 本地 receipt 不存在时有清楚提示：定向测试和手工 CLI 均已验证。

**明确不做逐项核对**：

- [x] 在本 feature 的提交边界内未新增 `--long-gate-cache`；后续 PR-3 已接入该 CLI。
- [x] 在本 feature 的提交边界内未修改 `scripts/run_quality_gate.py`；后续 PR-3 已接入 runner。
- [x] 未执行 pytest/ruff/pyright 等质量门禁命令；`tools/long_gate_manifest.py` 只用 `subprocess.run` 调 `git rev-parse HEAD` 读取 HEAD。

**关键决策落地**：

- [x] D1：入口只认 `build_quality_gate_command_plan()`，没有手写 13 步命令清单。
- [x] D2：required/startup 的最终 entry 识别基于真实 command plan，并用 `sync_debt_ledger.py check` 作为位置锚点兜底。
- [x] D3：本地 receipt 只作为探测信息，损坏或未知命令进入 warnings，不删除旧文件。

**挂载点反向核对**：

- [x] 本 feature 边界内唯一用户可见入口是 `python -m tools.long_gate_manifest`；当前工作区后续阶段也支持 `python tools/long_gate_manifest.py` 直接执行。
- [x] `rg -- '--long-gate-cache|long_gate_cache' scripts/run_quality_gate.py tools/long_gate_manifest.py tests/test_long_gate_manifest.py` 未发现 runner 接入。

## 3. 验收场景核对

- [x] **S1**：调用 `build_long_gate_manifest(repo_root)` → 真实调用 `build_quality_gate_command_plan()`。
  - 证据来源：`tests/test_long_gate_manifest.py`。
  - 结果：通过。

- [x] **S2**：当前真实 command plan → manifest entries 包含主要门禁分类。
  - 证据来源：`tests/test_long_gate_manifest.py` 和 CLI 输出。
  - 结果：通过。

- [x] **S3**：pyright tools 命令 → entry 包含 `QUALITY_GATE_TOOL_PATHS`。
  - 证据来源：`tests/test_long_gate_manifest.py`。
  - 结果：通过。

- [x] **S4**：无本地 receipts → 输出固定 no receipts 提示。
  - 证据来源：`tests/test_long_gate_manifest.py` 和 `--repo-root /tmp/aps-long-gate-no-receipts` 手工 CLI。
  - 结果：通过。

- [x] **S5**：未知 local receipt → 输出 warning，不静默丢弃。
  - 证据来源：`tests/test_long_gate_manifest.py`。
  - 结果：通过。

## 4. 术语一致性

- `long_gate_manifest`：只用于新模块和测试，未和现有 `quality_gate_manifest` 混名。
- `receipt`：沿用现有质量门禁证据叫法，新增逻辑只读不改。
- 防冲突：本 feature 边界内未新增 `long_gate_cache` 或 `--long-gate-cache`，避免提前暴露尚未实现的缓存入口；后续 PR-1/PR-3 已分别补上核心库和 runner 开关。

## 5. 架构归并

- [x] 不需要更新 `codestable/architecture/ARCHITECTURE.md`。本 feature 只是新增只读开发工具，不改变 APS 运行架构，也不改变正式质量门禁入口。
- [x] 架构总入口现有“质量门禁入口仍以 scripts/run_quality_gate.py 为准”仍然准确。

## 6. requirement 回写

- [x] 无 requirement 回写。本 feature 是技术工具准备项，不新增用户可见业务能力。

## 7. roadmap 回写

- [x] 已把 `codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `long-gate-manifest-probe` 改为 `done`。
- [x] 已把 roadmap 主文档第 5 节中对应条目同步为 `done`，并补变更日志。
- [x] 已运行 CodeStable YAML 校验。

## 8. AGENTS.md / CLAUDE.md 候选盘点

- [x] 无候选。本 feature 没暴露需要所有后续任务都遵守的新仓库级规则。

## 9. 遗留

- 后续继续按 roadmap 推进 `long-gate-cache-core`：输入指纹和 success cache 读写。
- 当前本地已有旧 QualityGate receipts，但旧 schema 没有 `duration_s`，所以 CLI 只能显示 `duration_unknown`。
