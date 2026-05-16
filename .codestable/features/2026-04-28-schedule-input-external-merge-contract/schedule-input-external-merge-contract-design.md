---
doc_type: feature-design
feature: 2026-04-28-schedule-input-external-merge-contract
status: approved
summary: 固定排产输入和外协组合并合同，补齐窄测试，并把两个复杂度登记压回阈值内。
tags: [scheduler, input-contract, external-merge, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: schedule-input-external-merge-contract
---

# 排产输入与外协组合并合同设计

## 0. 术语约定

- 排产输入：`build_algo_operations(..., return_outcome=True)` 产出的算法工序列表和 `BuildOutcome` 事件。
- 外协组合并：模板工序指向外部组，外部组为 `merged` 时，整组外协使用组总周期。
- 可见退化：非 strict 模式可以继续跑，但必须带结构化事件说明原因；strict 模式必须直接失败。
- full-test-debt：当前 active xfail 登记，不包含本次 scheduler M1。

## 1. 决策与约束

- 本次只处理 P1-8/9/10 的当前事实源：`_build_algo_operations_outcome` 复杂度、`lookup_template_group_context_for_op` 复杂度、外协组合并合同测试缺口。
- 明确不做：不改页面、不改落库、不改冻结窗口、不改停机区间、不碰 runtime/plugin、不修改质量门禁工具、不把本次说成 full-test-debt 减少。
- `schedule_input_contracts.py` 只读参照；如果 collector 合同测试证明必须改该文件，立即停线重新定范围。
- 不新增静默兜底；只允许搬移现有可见退化逻辑，事件 code、field 和 strict 抛错字段保持稳定。

## 2. 名词与编排

### 2.1 名词层

- `OpForScheduleAlgo` 字段保持不变：`ext_days`、`ext_group_id`、`ext_merge_mode`、`ext_group_total_days`、`merge_context_degraded`、`merge_context_events` 继续作为下游算法和 summary 的稳定输入。
- `BuildOutcome` 合同保持不变：`return_outcome=True` 必须返回 `BuildOutcome[List[OpForScheduleAlgo]]`。
- `TemplateGroupLookupOutcome` 合同保持不变：模板缺失、外部组缺失在非 strict 下返回 degraded outcome；strict 下抛 `ValidationError`。

### 2.2 编排层

```text
BatchOperation
-> build_algo_operations()
-> lookup_template_group_context_for_op()
-> OpForScheduleAlgo + BuildOutcome events
-> collector / service / summary / greedy
```

- 内部工序不查模板和外部组，组合并字段为空。
- 外协无组或 `separate` 组走单道 `ext_days`。
- 外协 `merged` 组使用 `ext_group_total_days`，不使用成员 `ext_days`。
- 模板缺失、外部组缺失、非法 `total_days` 的非 strict 路径保留结构化事件；strict 路径直接失败。

### 2.3 挂载点

- 主入口：`core/services/scheduler/run/schedule_input_builder.py`。
- 模板/外部组查找：`core/services/scheduler/run/schedule_template_lookup.py`。
- 下游证明：collector、ScheduleService、summary、greedy/SGS 只作为验证面，不主动改。

## 3. 验收契约

- S1：内部工序不访问模板仓库或外部组仓库，组合并字段为空。
- S2：外协模板无 `ext_group_id` 时，使用单道 `ext_days`，没有退化事件。
- S3：外协 `separate` 组不被误当成 merged，仍使用单道 `ext_days`。
- S4：外协 `merged` 组使用 `ext_group_total_days`，`ext_days` 为空。
- S5：模板缺失、外部组缺失、非法 `total_days` 在非 strict 下有事件并退回单道 `ext_days`。
- S6：模板缺失、外部组缺失、非法 `total_days` 在 strict 下 fail fast。
- S7：服务汇总层保留 `merge_context_degraded` 通道，不把组合并退化混成普通 `input_fallback`。
- 反向核对：不新增 legacy private lookup fallback；不改页面、落库、冻结、停机、runtime/plugin、门禁工具。

## 4. 与项目级架构文档的关系

本次是排产输入合同和技术债收口，不新增用户可见能力，不需要改 requirements。若实现后合同成为长期规则，则在验收报告中确认是否需要补 architecture；默认只回填 roadmap。
