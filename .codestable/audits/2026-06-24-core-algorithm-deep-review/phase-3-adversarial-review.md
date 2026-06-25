---
doc_type: audit-stage
audit: 2026-06-24-core-algorithm-deep-review
stage: phase-3-adversarial-review
status: completed
created: 2026-06-24
---

# Phase 3：对抗复审

本阶段目标是防止主线程把误报写进总报告，或漏掉比当前发现更严重的问题。

## 对抗批次

| round_id | agent_id | 任务 | 状态 |
|---|---|---|---|
| adv-1A | 019ef9df-60b1-7900-80ca-5ddb9764b2c2 | 按主线程 F-01 到 F-11 逐条找反证、查严重度是否过高/过低 | completed |
| adv-1B | 019ef9df-611a-7b93-94f7-5ea91f3898c1 | 不依赖主线程结论，重新沿主链盲审 | completed |

## 当前主线程给对抗批次的验收标准

- 必须只读源码，不改文件。
- 必须给真实 `file:line` 证据。
- 有反证就指出，不要顺着主线程结论。
- 证据不足就明确写证据不足。
- 重点挑战：
  - 是否把“可见降级”误写成“静默吞错”。
  - 是否把架构允许的行为误写成缺陷。
  - 是否漏掉会导致正式排产错误、运行时崩溃、数据写错的问题。

## adv-1A 反证结果

### 要求主线程修正

- 坏工时不能写成“必然落库成正式零时长排程”。
  - 反证：`core/services/scheduler/run/schedule_payload_contract.py:169-176` 持久化前要求 `start_time < end_time`。
  - 主线程处理：已改成“坏工时进入算法层，可能产生零时长算法结果或后段校验失败；不能证明零时长正式落库”。
- `graph on + cycle + block=no` 不能报 P1。
  - 反证：`core/services/scheduler/run/schedule_graph_dispatch_context.py:96-103` 有明确 public 降级字段。
  - 主线程处理：保留为 P2 展示弱化，不报 blocker。
- 当前服务入口 `simulate=True` 不能说会落库。
  - 反证：`core/services/scheduler/schedule_service.py:327-330` 不传持久化函数。
  - 主线程处理：拆成“服务入口安全”和“底层持久化层同名参数会写模拟版本”。
- attempts 截断不建议作为正式缺陷。
  - 主线程处理：移到“降级或不报的线索”。

### 支持保留

- 停机加载/扩展失败继续排产：保留 P1。
- 候选对比强制 greedy 绕开 improve：保留 P1。
- balanced 可能偏离用户目标：保留 P1/P2，主线程按默认策略影响正式采用，保留 P1。
- 摘要计数单源破裂：保留 P1。
- 同批次后续跳过缺错误明细：保留 P2。
- OR-Tools/异常根因不进摘要：保留 P2，并合并为“异常根因泛化”。
- `enforce_ready` 未知字符串变 no：补入 P2 服务层合同风险。

## adv-1B 盲审结果

### 新增或强化

- 部分失败会生成可打开正式版本。
  - 证据链：派工失败计数不一定中断整次排产；`partial` 有合法 payload；非模拟会写 `Schedule`/`ScheduleHistory`；路由把 `partial` 跳到甘特图。
  - 主线程处理：新增 F-01 P1，并说明这是当前测试锁定的产品合同风险，不是隐藏行为。
- 候选对比强制 greedy 绕开 improve。
  - 主线程处理：保留 F-04 P1。
- balanced 候选选择可能覆盖用户优化目标。
  - 主线程处理：保留 F-05 P1。
- 异常根因被压成泛化文案。
  - 主线程处理：把 OR-Tools 根因不足扩展为 F-10 P2，覆盖 dispatch 泛化异常和历史/操作日志不可追溯。

### 反例确认

- 输入收集多处不是静默兜底：空批次、非法时间、无可重排工序等会直接抛错。
- 图分析 `on` 模式不是完全吞错：不可用或构图错误会被策略拦住。
- 图 ready queue 不是无条件忽略：非 SGS 和坏 graph context 有合同校验。
- 候选方案不是所有异常都吞掉：普通异常不会被当作成功候选。
- OR-Tools 失败是可选加速路径，不作为“主排程失败被静默成功”上报。
- 服务层模拟运行不落库。

## 最终修订结果

- 正式发现：12 条。
- P1：6 条。
- P2：6 条。
- 移出正式发现：attempts 截断缺标记，仅保留为观察项。
- 关键表述收窄：坏工时不再声称必然落库；simulate 不再混淆服务入口和底层持久化；图有环降级不再当作违反架构。
