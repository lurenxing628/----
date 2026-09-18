---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: bug-02
nature: bug
severity: P2
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 02：检查点"输入不支持"不降级而是让整次候选对比失败

## 速答

`_decode` 只对 `decode_checkpoint_unsupported_calendar` 关掉检查点并重跑全量；`decode_checkpoint_unsupported_input`、`calendar_unavailable`、`calendar_changed_during_read` 等捕获期失败直接上抛。IG 的首个参考解一定带检查点请求，`sgs_checkpoint_inputs.py` 的报错文案写着"请使用全量解码"，但没有任何调用方这么做。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy.py:395-403`。
- `core/algorithms/greedy/dispatch/sgs_checkpoint_inputs.py:59-61`；`optimizer_graph_ready_iterated_greedy_start.py:28` 起点必带检查点。
- 复现：`/tmp/aps-audit-20260918/S2/probe_unsupported_input.py` 给批次挂 `imported_at = datetime(..., tzinfo=utc)` → `run_candidate_comparison` 整体失败 `decode_checkpoint_unsupported_input`，不是单候选 failed。

## 影响

当前 `Batch` / `OpForScheduleAlgo` 字段均为标量或标量字典列表，生产可达性低；但任何未来新增的非标量、带时区或 NaN 字段会让所有图候选与整次排产失败，而不是退回全量解码。

## 修复方向

捕获期失败原因与 `unsupported_calendar` 同样处理（禁用检查点、重跑全量、报告原因与计数）；只有真正的续排签名不一致保持 fail-loud。

## 处理结果

2026-09-18 同日落地：`optimizer_graph_ready_iterated_greedy.py` 的 `_decode` 在未续排时对所有 `decode_checkpoint` 捕获期失败一律降级——关检查点、重跑完整解码、计 `checkpoint_capture_rejections` 与 `disabled_reason`，逻辑解码只计一次；续排签名不一致仍 fail-loud；判定规则收在新模块 `optimizer_graph_ready_decode_capture.py`（`is_capture_failure` / `capture_failure_reason`）。同日曾让候选评估层的取序捕获走同一降级，后因取序基座整体撤回（finding-07）而删除，候选评估层不再发起任何检查点请求。合同测试见 `tests/algorithm/test_graph_ready_ig_incumbent_context_contract.py`（`test_unsupported_calendar_capture_reports_reason_and_continues_with_real_full_decodes`、`test_capture_refusal_degrades_to_full_decodes_with_reason_and_count`、`test_resume_mismatches_stay_fail_loud`）。
