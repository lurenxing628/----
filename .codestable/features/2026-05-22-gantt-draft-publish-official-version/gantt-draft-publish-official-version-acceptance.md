# 甘特图 Scenario 正式采用验收

## 已完成

- `POST /scheduler/gantt/adjustments/publish-scenario` 已接入。
- 发布必须传 `confirm_text=正式采用` 和非空原因。
- 发布前重新校验来源 Draft，且只接受 `saved_scenario`。
- 发布时确认基准版本仍是最新正式版本。
- 发布成功后生成新的正式 `Schedule` 版本和 `ScheduleHistory`。
- 被采用的 Scenario 和 Draft 会标记为 `published`。
- 操作日志记录发布人、原因、基准版本、新版本、Scenario 和 Draft。
- 同一个 Scenario 只能正式采用一次；重复采用会被拒绝。
- 操作日志写入失败时，正式版本写入会一起回滚。

## 验收测试

- `tests/regression_gantt_scenario_publish.py`
- `tests/regression_request_services_contract.py`
- `tests/test_run_quality_gate.py::test_required_suite_comes_from_shared_registry_and_covers_high_risk_regressions`

## 边界

- 页面仍不显示正式采用按钮；只读甘特图不会触发发布。
- 不新增假权限。
- 接口不接受客户端自报发布人；没有真实登录体系时记为 `system`。
- 不修改旧正式版本，不写候选方案表。
