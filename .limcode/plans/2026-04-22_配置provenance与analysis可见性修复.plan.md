# 配置 provenance 与 analysis 可见性修复 plan

> **执行方式**：优先使用 `subagent-driven-development`；如果当前环境不适合子代理或用户要求当前会话直接执行，则使用 `executing-plans`。

**目标**：修复配置 provenance completeness blocker，补齐 analysis 页 warning 可见性，并把对应回归接入 quality gate。

**总体做法**：先把当前缺失的交叉测试补成会失败的合同，再最小改动收敛 config completeness 判定；随后补 analysis 真模板 warning 展示，并把真模板回归纳入 guard suite，最后跑受影响定向回归和门禁自检。

**涉及技术 / 模块**：core/services/scheduler/config、web/routes/domains/scheduler、templates/scheduler、web/viewmodels、tools/quality_gate_shared.py、scripts/run_quality_gate.py、tests。

---

### 任务 1：锁住 provenance 半残缺交叉场景

**目标**
- 把当前最危险的半残缺 provenance 场景先锁成失败用例，避免后续“修了读链、漏了写链”。

**文件**
- 修改：core/services/scheduler/config/config_service.py
- 测试：tests/regression_config_service_active_preset_custom_sync.py
- 测试：tests/regression_config_service_relaxed_missing_visibility.py
- 测试：tests/regression_scheduler_config_route_contract.py

- [ ] **步骤 1：写失败用例，锁住 active_preset 存在但 reason 缺失的 hidden repair 场景**

在 tests/regression_config_service_active_preset_custom_sync.py 新增一条交叉回归：

```python
def test_config_service_page_save_hidden_repair_with_missing_reason_stays_blocked() -> None:
    ...
```

用例要求：
- restore_default 之后只删除 ACTIVE_PRESET_REASON_KEY，保留 ACTIVE_PRESET_KEY；
- 再把 auto_assign_persist 写成退化值；
- 调用 save_page_config；
- 断言 hidden_repaired_fields 为空、blocked_hidden_repairs 包含 auto_assign_persist；
- 断言 active_preset 不被重新 materialize 成 hidden_repair 确定态；
- 断言 get_preset_display_state(readonly=True) 仍然是 provenance_missing。

- [ ] **步骤 2：补 rejected path 的 completeness 合同用例**

在 tests/regression_config_service_active_preset_custom_sync.py 再补 1 条 apply_preset 或 save_preset 的 rejected-path 用例，场景同样是 active_preset 还在但 reason 缺失。目标不是落库，而是锁定返回给前端的 effective_active_preset / reason 不得假装完整来源。

- [ ] **步骤 3：运行定向用例，确认当前实现按预期失败**

运行：python -m pytest tests/regression_config_service_active_preset_custom_sync.py -q

预期：
- 新增半残缺 provenance 用例失败；
- 失败原因落在 hidden repair gate 或 rejected path 口径，而不是测试拼写错误。

---

### 任务 2：统一 config completeness 判定

**目标**
- 用一个共享判定收敛读链、bootstrap、save_page_config、rejected path 的 provenance completeness 语义。

**文件**
- 修改：core/services/scheduler/config/config_service.py
- 修改：core/services/scheduler/config/config_presets.py
- 测试：tests/regression_config_service_active_preset_custom_sync.py
- 测试：tests/regression_config_service_relaxed_missing_visibility.py
- 测试：tests/regression_scheduler_config_route_contract.py

- [ ] **步骤 1：在 config_service 中抽共享 completeness 解析**

在 core/services/scheduler/config/config_service.py 增加一个只负责 provenance 解析的共享 helper。最低要求是输出：
- active_preset
- active_preset_reason
- active_preset_meta
- active_preset_missing
- active_preset_reason_missing
- provenance_missing
- can_preserve_baseline

要求：
- 与 current_config_state 的只读判定保持一致；
- 不能把 reason 为 None 的正常 exact 场景一律打成缺失；
- 继续保留“完整命名方案 + hidden repair 仍可 exact，但带 hidden notice”的现有合同。

- [ ] **步骤 2：让 save_page_config 使用同一 completeness 结果**

修改 core/services/scheduler/config/config_service.py 中 _config_page_current_provenance_state 和 _config_page_build_write_plan，使 hidden repair 的放行条件从“current_active_preset 是否有值”改为“can_preserve_baseline 是否为真”。

要求：
- active_preset 存在但 reason 行缺失时，必须走 blocked_hidden_write_plan；
- 完整命名方案 + hidden degradation 的现有通过路径保持不变；
- route 层 flash 合同仍沿用现有 blocked_hidden / hidden notice 结构。

- [ ] **步骤 3：让 bootstrap 与 rejected path 也消费同一 completeness 语义**

修改 core/services/scheduler/config/config_presets.py：
- bootstrap_active_provenance_if_pristine 的短路条件不能只看 ACTIVE_PRESET_KEY；
- save_preset / apply_preset 的 rejected payload 不能再把半残缺 provenance 当作完整 effective identity 回显。

要求：
- 不在 rejected path 偷偷补写 provenance 行；
- 继续保持“不物化 provenance 行”的现有回归合同。

- [ ] **步骤 4：运行 config 焦点回归**

运行：
- python -m pytest tests/regression_config_service_active_preset_custom_sync.py -q
- python -m pytest tests/regression_config_service_relaxed_missing_visibility.py -q
- python -m pytest tests/regression_scheduler_config_route_contract.py -q
- python -m pytest tests/regression_apply_preset_adjusted_marks_custom.py -q

预期：全部通过。

---

### 任务 3：补 analysis 页 warning 真模板回归

**目标**
- 先让 analysis warning 漏显变成可执行、可失败的真模板合同，再动模板。

**文件**
- 测试：tests/regression_scheduler_analysis_observability.py
- 测试：tests/regression_scheduler_analysis_route_contract.py
- 修改：web/routes/domains/scheduler/scheduler_analysis.py
- 修改：web/viewmodels/scheduler_summary_display.py

- [ ] **步骤 1：在真模板回归里构造 warning-only 场景**

在 tests/regression_scheduler_analysis_observability.py 增加一个 summary：
- warnings 非空
- warning_total > 0
- errors 为空
- primary_degradation 可以为空或保持次级事件

并增加 HTML 断言，至少锁：
- “告警：N 条”
- warnings_preview 中的一条具体文本
- warning_hidden_count 的“另有 N 条告警”文案

- [ ] **步骤 2：在 route contract 中补 payload 层断言**

在 tests/regression_scheduler_analysis_route_contract.py 增加 1 条轻量断言，确认 selected_summary_display 在 route payload 中确实带有 warning_total 和 warnings_preview。这个测试不替代真模板回归，只用于锁 route 没把字段丢掉。

- [ ] **步骤 3：运行 analysis 焦点回归，确认模板层当前失败**

运行：
- python -m pytest tests/regression_scheduler_analysis_observability.py -q
- python -m pytest tests/regression_scheduler_analysis_route_contract.py -q

预期：
- 真模板回归因 analysis.html 未渲染 warning 而失败；
- route contract 通过或按预期暴露 payload 缺口。

---

### 任务 4：把 analysis 真模板回归接入 quality gate

**目标**
- 在修模板前先把 analysis 真模板合同接入 guard suite，避免同类问题再次绕过门禁。

**文件**
- 修改：tools/quality_gate_shared.py
- 修改：tests/test_run_quality_gate.py
- 修改：scripts/run_quality_gate.py
- 测试：tests/regression_scheduler_analysis_observability.py

- [ ] **步骤 1：把 analysis observability 真模板回归加入 guard suite**

修改 tools/quality_gate_shared.py，把 tests/regression_scheduler_analysis_observability.py 加入 QUALITY_GATE_GUARD_TESTS。

要求：
- 不删除现有 analysis route contract；
- route contract 继续守 payload，observability 守真模板显示。

- [ ] **步骤 2：补 gate 自检**

修改 tests/test_run_quality_gate.py，新增断言确保：
- regression_scheduler_analysis_observability.py 在 guard 清单中；
- run_quality_gate 生成的 pytest 命令会实际执行到它。

- [ ] **步骤 3：运行 gate 相关测试**

运行：
- python -m pytest tests/test_run_quality_gate.py tests/regression_quality_gate_scan_contract.py -q

预期：全部通过。

---

### 任务 5：补 analysis 模板 warning 展示

**目标**
- 让 analysis 页与 week_plan、history 共用同一套 warning 显示行为。

**文件**
- 修改：templates/scheduler/analysis.html
- 测试：tests/regression_scheduler_analysis_observability.py
- 联动：templates/scheduler/week_plan.html
- 联动：templates/system/history.html

- [ ] **步骤 1：按现有页面口径补 warning 区块**

修改 templates/scheduler/analysis.html，在 parse_failed / primary_degradation / error_total 之间补 warning_total 区块，直接消费：
- selected_summary_display.warning_total
- selected_summary_display.warnings_preview
- selected_summary_display.warning_hidden_count

要求：
- 文案和 week_plan、history 保持一致；
- 只在 warning_total > 0 时渲染；
- 不新增 analysis 专属字段。

- [ ] **步骤 2：重新运行 analysis 定向回归**

运行：
- python -m pytest tests/regression_scheduler_analysis_observability.py -q
- python -m pytest tests/regression_scheduler_analysis_route_contract.py -q
- python -m pytest tests/regression_scheduler_week_plan_summary_observability.py tests/regression_system_history_route_contract.py -q

预期：全部通过，且 week_plan / history 不受影响。

---

### 任务 6：收尾验证与文档同步

**目标**
- 用最小但足够的验证确认三条主线都闭环，并补齐必要留痕。

**文件**
- 联动：.limcode/review/2026-04-22_未提交修改深挖对抗审查.md
- 联动：audit/2026-04/20260422_配置provenance与analysis可见性取舍.md
- 联动：开发文档/技术债务治理台账.md

- [ ] **步骤 1：运行最终定向回归集**

运行：
- python -m pytest tests/regression_config_service_active_preset_custom_sync.py tests/regression_config_service_relaxed_missing_visibility.py tests/regression_scheduler_config_route_contract.py -q
- python -m pytest tests/regression_scheduler_analysis_observability.py tests/regression_scheduler_analysis_route_contract.py tests/regression_scheduler_week_plan_summary_observability.py tests/regression_system_history_route_contract.py -q
- python -m pytest tests/test_run_quality_gate.py tests/regression_quality_gate_scan_contract.py -q

预期：全部通过。

- [ ] **步骤 2：运行一次实际 quality gate**

运行：python scripts/run_quality_gate.py

预期：
- guard suite 中包含 analysis observability 真模板回归；
- 整体门禁通过。

- [ ] **步骤 3：如修复过程中调整了合同语义，补技术债或阶段留痕**

若 config completeness 或 analysis observability 的合同有文字口径变化，同步更新 开发文档/技术债务治理台账.md 或 阶段留痕文档；不要新增泛泛说明，只记录：
- 修复了什么裂缝
- 新增了哪条回归
- 门禁如何接住它

---

plan 已完成并保存。接下来有两个执行方式：

1. `subagent-driven-development`（推荐）—— 每个任务由独立子代理执行，并在任务间做两阶段 review
2. `executing-plans` —— 在当前会话按 plan 逐项执行