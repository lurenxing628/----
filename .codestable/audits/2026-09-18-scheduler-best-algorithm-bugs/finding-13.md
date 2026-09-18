---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: performance-13
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
status: fixed
---

# Finding 13：图档多起点对 3 条规则各解一次，无并列时必同输出

## 速答

派工键序是 `(penalty, *graph_key, *dispatch_key)`，图键无并列时规则键永远不参与比较，三次解码必同输出；决策键含规则令牌，多起点去重不剪。

## 关键证据

- `core/algorithms/greedy/dispatch/sgs_scoring.py:115-116`；`optimizer_multi_start.py:33-34`；`optimizer_multi_start_dedup.py:211-212`。
- 实测（S4）：frozen_ready_external 5 档图键 15 组 / 0 并列，4 条规则解码哈希全同，步进时钟每档 multi_start n=3、distinct=1（占该档 6–8 次解码的 2 次）；shift_pool 每档 3/2（slack==cr）。

## 影响

每档 22–33% 解码白烧，直接挤掉图阶段。

## 修复方向

与 finding-08 一并：无并列只解配置规则，有并列展开规则池。

## 处理结果

2026-09-18 同日与 finding-08 一并落地：图键无并列时多起点只解配置规则（`configured_only`）；实测 frozen_ready_external 图档多起点 3 次 → 1 次解码。
