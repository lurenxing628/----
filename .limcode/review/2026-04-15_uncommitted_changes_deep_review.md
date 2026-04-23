# 未提交改动三轮深审结论

- 时间：2026-04-15
- 范围：当前工作区未提交改动，重点覆盖请求级服务容器、排产配置/输入契约、Excel 预览基线、`result_summary` 可观测性、质量门禁扫描。

## Round 1：需求符合性审查

- 结论：PASS
- 依据：
  - 请求级服务容器与目标路由迁移已按“显式失败、减少静默兜底、统一依赖入口”的方向落地。
  - 排产配置快照、输入收集契约、Excel 预览基线、结果摘要解析与质量门禁都与当前设计目标一致。
  - 未发现明显的范围漂移、顺手扩范围或与用户意图冲突的过度实现。

## Round 2：代码质量审查

- 结论：PASS
- 依据：
  - 主链路未发现可复现的崩溃、静默吞错或明显误判。
  - 已检查请求级容器生命周期、`g.services` 消费链、UI 模式读取、调度契约收紧、Excel stale 检测、`result_summary` 解析、质量门禁扫描。
  - 针对性回归测试通过。

## Round 3：独立对抗审

- 结论：主链路无阻塞性缺陷，但有 1 个“真实存在、尚未证实会转化为当前故障”的清理不对称点。
- 独立审核员确认：
  - 主链路总体满足设计意图，没有发现阻塞合入的功能性缺陷。
  - `backup_restore()` 中只清理 `g.db` / `g.op_logger`，未同步清理 `g.services`，这是真实存在的生命周期不对称。
- 独立审核员不同意的点：
  - 目前没有证据证明该不对称已经在当前请求内转化成实际功能故障，因此不应夸大为“已证实回归”。

## 主代理裁决

### 发现 1

- 严重度：Minor
- 位置：
  - `web/routes/system_backup.py:236-243`
  - `web/bootstrap/factory.py:300-343`
- 事实：
  - 请求级容器新约束是 `g.db` / `g.op_logger` / `g.services` 同生命周期装配。
  - `backup_restore()` 仍只 `g.pop("db")` 和 `g.pop("op_logger")`，没有同步 `g.pop("services")`。
- 判断：
  - 这是一个真实的清理不对称。
  - 现有代码路径在同一请求后续没有继续消费 `g.services`，因此暂未构成已证实的运行时故障。
- 建议：
  - 二选一即可：
    - 补 `g.pop("services", None)`，把恢复流程与新请求级容器约束收口到同一生命周期模型；
    - 或先补专门回归测试，证明关闭 `g.db` 后当前请求不会再访问 `g.services`，再决定是否修补。

## 测试证据

- 主代理执行：
  - `pytest -q tests/regression_request_services_contract.py tests/regression_request_services_failure_propagation.py tests/regression_system_request_services_contract.py tests/test_ui_mode.py tests/regression_schedule_input_collector_contract.py tests/regression_schedule_input_collector_legacy_compat.py tests/regression_schedule_service_strict_snapshot_guard.py tests/regression_schedule_repository_bundle_contract.py tests/regression_supplier_effective_selection_contract.py tests/regression_excel_backend_factory_observability.py tests/regression_scheduler_excel_batches_helper_injection_contract.py tests/regression_scheduler_excel_batches_preview_baseline_precision.py tests/test_schedule_summary_observability.py tests/test_architecture_fitness.py`
  - 结果：`79 passed in 24.52s`
- 独立审核员复跑相关子集：
  - 结果：`61 passed in 21.24s`

## 最终结论

- 当前改动整体达成了“不过度兜底、不静默回退、减少过度防御式兼容、保持功能完整”的设计目标。
- 未发现阻塞合入的功能性缺陷。
- 保留 1 个低严重度生命周期一致性风险，建议在后续小补丁或专项回归里收口。
