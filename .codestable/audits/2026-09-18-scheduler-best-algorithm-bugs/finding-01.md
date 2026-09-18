---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: bug-01
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 01：IG 采纳新现任失败后留下过期 reference，下一轮续排签名不一致崩掉整次排产

## 速答

`adopt_incumbent` 先切换父（batch_order / inherited / profile），再对新父解码；解码返回 None 时既不回滚父也不更新 `reference`。下一轮用旧 reference 的检查点在新父签名下续排，`run_state_setup` 抛 `decode_checkpoint_signature_mismatch`，`_decode` 对 `decode_checkpoint` 类错误一律 re-raise，整个优化器与候选对比崩溃，而不是"保留已验证方案"。

## 关键证据

- `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy.py:171-186` —— `_set_parent` 后 `entry = self._decode_entry(parent.order)`，`entry is None` 时无回滚。
- 同文件 `:229-251` 与 `optimizer_graph_ready_iterated_greedy_diversify.py:58-63` —— 重启路径失败时 `_activate_entry(reference)` 回滚，只有 adopt 没有。
- 同文件 `:401-403` —— `exc.field == "decode_checkpoint"` 一律 raise；`core/algorithms/greedy/run_state_setup.py:116-118` 抛签名不一致。
- 复现：`/tmp/aps-audit-20260918/S2/probe_adopt_stale_reference.py`（4 工序真实 SGS，非 strict，`before_evaluate` 让新父首次正式解码被拒 1 次）→ `ValidationError: 断点续排的解码输入与断点不一致 {'reason': 'decode_checkpoint_signature_mismatch'}`。strict 下新父按 rank 键重解码出现 `failed_ops>0`（如排到 end_date 窗口外）时 `_decode_entry` 返回 None，效果相同。

## 影响

触发条件：修补阶段产出换了批序或资源覆盖的新现任（context switch），且它的 IG 重解码不可行或被拒。生产可达性中，一旦触发是整次排产失败而非降级。

## 修复方向

`entry is None` 时回滚到原 reference 的父（`_activate_entry(self.reference)`）或把 reference 置为需重解码状态；合同测试锁住"换父失败不得留下跨父 reference"。

## 处理结果

2026-09-18 同日落地：采纳逻辑抽到 `core/services/scheduler/run/optimizer_graph_ready_iterated_greedy_reference.py`，`adopt_incumbent` 捕获失败（预算或拒绝）时回滚原父与原 reference，计 `incumbent_adoption_rollbacks`，现任本身仍被采纳；合同测试 `tests/algorithm/test_graph_ready_ig_reference_contract.py`（两种回滚场景，换父失败后下一轮不得出现签名不一致）。决定见 `.codestable/compound/2026-09-18-decision-ig-parent-identity-and-checkpoint-degradation.md`。
