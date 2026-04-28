---
doc_type: feature-acceptance
feature: 2026-04-28-plugin-enabled-source-contract
status: accepted
roadmap: p1-scheduler-debt-cleanup
roadmap_item: plugin-enabled-source-contract
accepted_at: 2026-04-28
---

# plugin enabled source contract 验收

## 1. 验收结论

M7-B 已完成。插件开关来源整理已经从一个复杂函数拆成来源判定、状态行公开化和整体来源汇总三个小函数；真实可选插件默认关闭合同已由测试锁住。

系统页现在能展示插件留痕状态和冲突能力信息，方便现场判断插件为什么没有按预期加载。

## 2. 改动范围

- `web/bootstrap/plugins.py`：拆 `_apply_enabled_sources`，保持原默认开关语义。
- `templates/system/backup.html`：展示 `telemetry_persisted` 和 `conflicted_capabilities`。
- `tests/test_plugin_enabled_source_contract.py`：新增真实插件默认关闭、来源汇总、错误脱敏和系统页模板守护测试。

## 3. 债务口径

- P1-23：`complexity:web-bootstrap-plugins-_apply_enabled_sources` 已关闭。
- P1-24：复核后没有作为 open bug 修复；当前 plugin fallback 仍按台账 fixed/baseline 状态管理。
- P1-25：证据不足，未处理。
- 本轮不声明 full-test-debt 减少。

## 4. 已运行验证

- `tests/test_plugin_enabled_source_contract.py`：4 passed。
- `tests/regression_plugin_bootstrap_config_failure_visible.py tests/regression_plugin_bootstrap_injects_config_reader.py tests/regression_plugin_bootstrap_telemetry_failure_visible.py tests/regression_plugin_capability_conflict_visible.py`：7 passed。
- `tests/test_architecture_fitness.py` 启动链相关 5 项：5 passed。
- `scripts/sync_debt_ledger.py check`：通过，`complexity_count=32`。

## 5. 复审结果

- 插件合同审查未发现阻断问题，确认默认关闭、不注册能力、不抢默认 Excel 路径、来源汇总、错误脱敏、冲突和留痕入口都被覆盖。
- P1-24 在 roadmap 和 source-map 里保持“只复核”，没有被包装成新的 open bug 或已修 bug。
- 本轮没有改 `PluginManager` 默认语义，没有新增 plugin fallback。
