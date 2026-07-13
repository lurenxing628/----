---
doc_type: issue-fix
issue: 2026-07-13-legacy-dispatch-adapter-contract
path: standard
fix_date: 2026-07-13
status: fixed
severity: P1
root_cause_type: logic
related: [legacy-dispatch-adapter-contract-analysis.md]
tags: [algorithm, dispatch, strict-mode, compatibility]
---

# Legacy dispatch adapter 合同回归修复记录

## 1. 实际采用方案

采用 analysis 选定的方案 B，并在扩大回归后收敛为“strict 校验 + 能力按需 fail-loud”：

1. `_LegacyDispatchContext.schedule_internal()` 不再丢弃 `strict_mode` 后直接调用 callback；strict 模式下先调用 `validate_internal_hours_for_mode(...)`，失败时保持原 `ValidationError` 字段合同。
2. 新增 `DispatchContextContractError(TypeError)`。legacy 对象缺少当前执行路径真正调用的 external/internal/auto-assign callback 时，adapter 抛出专用合同错误。
3. batch-order 与 SGS 的逐工序广泛异常处理显式透传 `DispatchContextContractError`，不会再把它折算成普通 dispatch failure。
4. 不在 adapter 构造时要求全部 callback。一次中间实现这样做后，完整算法回归出现 7 个失败：missing-batch 路径和 auto-assign-disabled 路径并不需要所有 callback。最终按能力使用点检查，既 fail-loud，又不扩大兼容收窄。
5. 不把 canonical external/internal/auto-assign 具体算法复制或迁入 `algorithm_runtime`。这会把定点修复扩大为结构重构，也会破坏 runtime leaf 的职责边界。

## 2. 改动文件清单

### 生产代码

- `core/algorithm_runtime/dispatch_context.py`
  - 恢复 legacy strict 工时校验。
  - 新增专用 context 合同异常并用于三个 callback 缺失分支。
- `core/algorithms/greedy/dispatch/batch_order.py`
  - 透传 `ValidationError` 与 `DispatchContextContractError`。
- `core/algorithms/greedy/dispatch/sgs.py`
  - 同样透传专用合同异常。

### 测试

- `tests/algorithm/test_algorithms_a3_dependency_boundary.py`
  - strict 非法工时必须在 callback 前抛错。
  - batch-order 缺 external callback 必须 fail-loud。
  - SGS 缺 external callback 也必须 fail-loud。

### 联动证据与事实文档

- `.codestable/checkup/latest/callgraph/`、`.codestable/checkup/baseline.json`、`.codestable/checkup/README.md`
- A3 apply notes、两份依赖/模块审计、本轮未推送提交 audit
- 本 issue 的 report / analysis / fix-note

调用图和事实文档同时包含 sibling issue `callgraph-imported-module-edge-dedup` 的原子式证据重建，未夹带无关业务重构。

## 3. 验证结果

### 3.1 测试先行与修法校正

- 最初两条合同测试在旧实现上稳定红灯：strict 用例“未抛 `ValidationError`”，不完整 legacy context 用例“未 fail-loud”。
- 恢复 strict 校验后两条转绿。
- 构造阶段强制完整 callback 的中间方案在 `tests/algorithm` 暴露 7 个兼容回归；没有修改旧测试迁就实现，而是撤回过度前置校验，改为能力使用点专用异常。
- 最终 batch-order / SGS 三条新合同均通过，callback 前拒绝用例确认 `field="setup_hours"` 且 callback 调用数为 0。

### 3.2 扩大回归与结构门禁

- 完整 `tests/algorithm` + receiver-resolution：574 passed。
- 生产与含测试两条 `tools.scan_import_cycles --fail-on-new-cycle` 正式命令均返回 0；新增 runtime sibling import 没有让 A3 SCC 回潮。
- Ruff 全仓检查通过。
- Pyright gate：0 errors、15 条既有 scheduler `__all__` warning；Pyright tools：0 errors / 0 warnings。
- Python 3.8.10 全范围扫描：1220 文件、0 发现。

### 3.3 完整质量门禁

执行：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py \
  --allow-dirty-worktree --no-long-gate-cache --no-resume
```

结果：

- 19/19 receipts 的 returncode 都是 0；
- collected 4734，collection error 0，unexpected failure 0；
- required 253 targets / 2467 nodeids；
- manifest=`passed_but_unbound`；
- `is_dirty_before=true`、`is_dirty_after=true`、`tracked_drift_detected=false`；
- wrapper 退出码 2 是 dirty proof 不得冒充 clean proof 的预期合同。

## 4. 遗留事项

- 修复尚未 commit、未 push。
- 当前只能声明 dirty-worktree diagnostic，`clean_worktree_proof=false`。
- 若用户授权 scoped commit，应在固定干净 HEAD 重新执行 `--require-clean-worktree --no-long-gate-cache --no-resume`；只有那次成功才能建议 push。
- 没有遗留的代码 blocker，也没有顺手发现需要另开 issue。
