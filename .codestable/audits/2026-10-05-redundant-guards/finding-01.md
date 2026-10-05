---
doc_type: audit-finding
audit: 2026-10-05-redundant-guards
finding_id: "1.1"
nature: bug
severity: P2
confidence: high
status: fixed
---

# 看板处置状态使试调误失效

修复前，trial 事实捕获排除 trial/run 账本，却遗漏四个 Dashboard 状态/历史表。处置只改变处理记录，`trial/validation.py` 仍因全 facts_hash 变化标记 `trial_facts_changed`，正式采用预检因此拒绝。

真实链为 `registration.py` 的试调/采用路由 → `WorkbenchTrialService` / adoption validation → `live_context` → `capture_facts` → `WorkbenchTrialQueryRepository.read_whole_table`。内存夹具已确认仅 DashboardStates 更新即可改变 trial 捕获事实，而 run 的 `_production_facts` 比较不变。

实施应统一非输入表定义及比较语义，兼容旧试调已捕获的事实；不能改写旧档案摘要，也不能放过真实计划、执行、资源、日历、停机、资格、冻结和范围外占用变化。


## 实施结果

已完成对应源头修复；历史档案、公开契约及必要边界保留。具体实现、实际回归与日常门禁结果见 [修复记录](../../issues/2026-10-05-redundant-guards/redundant-guards-fix-note.md)。
