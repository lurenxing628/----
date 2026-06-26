---
doc_type: feature-ff-note
feature: diagnostic-public-id-boundary-fix
date: 2026-06-26
requirement:
tags: [scheduler, optimizer, public-boundary, diagnostics, operation-logs]
---

## 做了什么

把排产诊断、候选方案、导出和 OperationLogs 的用户可见输出收紧为安全摘要。内部 `op_id`、`node_id`、`candidate_id`、`candidate_key`、`source_table`、`op:...`、`graph_w...`、内部样本和原始 attempts dict 只允许留在 diagnostics/internal，不再进入普通页面、普通 HTML、导出和 OperationLogs public 投影。

## 改了哪些

- `core/services/scheduler/summary/optimizer_public_summary.py` — 将 public algo 摘要改为窄入口，串联 attempts、candidate、graph 和 algo 上下文字段投影。
- `core/services/scheduler/summary/optimizer_public_safety.py`、`optimizer_public_algo_fields.py`、`optimizer_public_attempts.py`、`optimizer_public_candidates.py` — 拆出安全过滤、algo 大字段、attempts 和候选对比投影。
- `core/services/scheduler/summary/graph_public_summary.py`、`core/services/common/excel_audit.py`、`core/services/system/operation_log_public_projection.py` — 收紧图分析、导出 filters 和 OperationLogs 普通用户投影。
- `web/viewmodels/scheduler_analysis_*.py`、`web/routes/system_runtime_logs.py`、`templates/system/logs.html` — 页面上下文改用 public 投影，普通日志页面不直接渲染 raw detail。
- `tests/algorithm/`、`tests/candidate/`、`tests/scheduler_analysis/`、`tests/scheduler_graph/`、`tests/web_pages/` — 增加和收紧 public 边界合同测试。

## 怎么验证的

已跑 221 个相关合同测试、optimizer proof harness 回归、benchmark proof harness 脚本、Python 3.8 语法扫描、ruff、pyright gate/tools、文件大小与复杂度门禁、路线图 YAML 检查。`scripts/run_quality_gate.py --allow-dirty-worktree` 17 步跑完，结果为 `passed_but_unbound`；第二轮定向复审和盲审复审均未发现 blocker。

## 顺手发现

- 当前工作区仍包含上一轮 `optimizer-proof-harness` 的 staged/unstaged 改动和本轮新增改动；因此本轮只能给 dirty/unbound proof，不能包装成 clean-worktree proof。
