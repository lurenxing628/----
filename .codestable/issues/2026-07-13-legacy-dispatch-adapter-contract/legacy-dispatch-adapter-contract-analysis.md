---
doc_type: issue-analysis
issue: 2026-07-13-legacy-dispatch-adapter-contract
status: confirmed
root_cause_type: logic
related: [legacy-dispatch-adapter-contract-report.md]
tags: [algorithm, dispatch, strict-mode, compatibility]
---

# Legacy dispatch adapter 合同回归根因分析

## 1. 问题定位

| 关键位置 | 说明 |
|---|---|
| `core/algorithm_runtime/dispatch_context.py:33-39` | 新 adapter 删除 `strict_mode` 后直接调用 legacy callback，没有复用旧校验。 |
| `core/algorithm_runtime/dispatch_context.py:27-48` | callback 缺失只在能力被调用时抛普通 `TypeError`，随后会落入逐工序广泛异常折算。 |
| `core/algorithms/greedy/run_context.py:47-84` | A3 前的适配路径包含 strict 校验和 canonical fallback；新旧两份逻辑发生漂移。 |
| `core/algorithms/greedy/dispatch/batch_order.py:40,124-149` | context 在入口适配，但方法异常在 `_dispatch_one` 的广泛异常处理里执行，可被记成普通失败。 |
| `tests/algorithm/test_algorithms_a3_dependency_boundary.py` | 只锁 identity/import/SCC，没有锁 legacy adapter 的运行行为。 |

`symbol_locator` 能定位 `ensure_dispatch_context` 定义，但当前 SCIP 索引对 A3 新符号 callers/callees 未解析；调用方已用源码和 `git grep` 复核为 `dispatch/batch_order.py` 与 `dispatch/sgs.py`。

## 2. 失败路径还原

**正常路径**：`dispatch_batch_order` → 得到完整 `ScheduleRunContext` 或 legacy adapter → strict 工时校验 → 校验通过后调用 scheduling callback；当前执行路径缺少所需 callback 时，专用合同错误穿透逐工序异常折算并 fail-loud。

**失败路径**：`dispatch_batch_order` → `ensure_dispatch_context` 无条件构造 `_LegacyDispatchContext` → `schedule_internal` 删除 `strict_mode` → 非法工时进入 callback → callback 返回空结果后只记录 dispatch failure；若 callback 缺失，则方法内 `TypeError` 被 `_dispatch_one` 的 `except Exception` 折算。

**分叉点**：`core/algorithm_runtime/dispatch_context.py:33-39` - 新 adapter 复制了 callback 转发，却没有复制 strict 校验；同时没有在 adapter 构造阶段验证 legacy 协议。

## 3. 根因

**根因类型**：逻辑错误。

**根因描述**：A3 为消除 `dispatch → greedy.run_context` 反向依赖新增第二套 context 适配逻辑，但只搬了 callback 访问和统计能力，没有完整定义“legacy context 最小协议”和 strict 行为。两套近似实现因此漂移：旧路径负责校验和宽泛 canonical fallback，新路径既丢校验，又把协议错误留到逐工序 try/except 内。

**是否有多个根因**：是。主因是 strict 校验遗漏；次因是 legacy callback 协议没有入口级 fail-loud。原 canonical fallback 依赖 greedy 具体实现，若完整搬入 `algorithm_runtime` 会扩大 A3 范围并混淆 runtime leaf 职责。

## 4. 影响面

- **影响范围**：direct `dispatch_batch_order` / `dispatch_sgs` 传 legacy scheduler-like 对象的路径；主 `GreedyScheduler.schedule()` 传完整 `ScheduleRunContext`，目前不受影响。
- **潜在受害模块**：算法专项测试、仓外或脚本级 direct dispatch 调用、strict-mode 数据校验与错误展示。
- **数据完整性风险**：当前直接复现为排产失败和错误原因丢失；若 legacy callback 自身宽容，存在接受非法工时并生成错误排程的风险。
- **严重程度复核**：维持 P1。生产主门面有绕过，但 fail-loud 合同被破坏且属于未推送回归。

## 5. 修复方案

### 方案 A：只补 strict 校验

- **做什么**：在 `_LegacyDispatchContext.schedule_internal` 调 callback 前恢复 strict 工时校验。
- **优点**：改动最小，直接修复已复现输入。
- **缺点 / 风险**：缺 callback 仍在逐工序 try/except 内退化成普通失败，问题只修一半。
- **影响面**：`dispatch_context.py` + A3 边界测试。

### 方案 B：strict 校验 + 能力按需 fail-loud（选定）

- **做什么**：恢复 strict 校验；callback 缺失时抛专用 `DispatchContextContractError(TypeError)`，并让 batch-order/SGS 在广泛异常折算前原样抛出。只在执行路径真正使用某项能力时校验，不提前要求无关 callback。
- **优点**：根因直接、KISS、没有反向 import，不复制 scheduling 算法；保留“缺批次等无需调度 callback”的既有 direct dispatch 行为，也不再静默折算真实协议错误。
- **缺点 / 风险**：把 A3 前“缺 callback 时借 canonical 实现”的偶然宽泛能力正式收窄为明确错误；需用测试和 fix-note 固化边界。
- **影响面**：`core/algorithm_runtime/dispatch_context.py`、`core/algorithms/greedy/dispatch/batch_order.py`、`core/algorithms/greedy/dispatch/sgs.py`、`tests/algorithm/test_algorithms_a3_dependency_boundary.py`，以及生成调用图/事实数字。

### 方案 C：把 canonical fallback 实现一并下沉

- **做什么**：把 external/internal/auto-assign 具体实现迁入 `algorithm_runtime`，让 adapter 完整复刻旧 fallback。
- **优点**：最大程度保留旧泛化行为。
- **缺点 / 风险**：把算法执行实现塞进 shared runtime leaf，扩大为跨多个大文件的结构重构，违背本 issue 最小修复和 A3 包职责。
- **影响面**：多个算法实现、wrapper、patch 合同、调用图和完整算法测试。

### 推荐方案

**推荐并选定方案 B**。它恢复真正需要的 strict 合同，同时把 callback 缺失从静默折算改成能力使用点 fail-loud；不提前拒绝当前路径不需要的 callback，也不为没有实际调用证据的偶然 fallback 扩大 A3 架构。用户在审计结论后明确回复“按照你的意见修吧”，已确认按推荐方案实施。实现阶段扩大回归发现若在构造时要求全部 callback 会破坏现有 missing-batch / auto-assign-disabled direct dispatch 合同，因此按本方案的“能力按需”口径收敛。
