---
doc_type: refactor-scan
refactor: 2026-04-30-techdebt-phase5-startup-fallbacks
status: approved
scope: 启动链 fallback、launcher 运行时能力和 web/ui_mode.py 拆分
tags: [techdebt, startup, fallback, win7]
---

# techdebt phase5 startup fallbacks scan

## 顶部总览

阶段 5 从阶段 4 clean gate 通过后的提交 `ae4c421` 继续。扫描范围是质量门禁定义的启动链范围，重点包括 `web/bootstrap/**/*.py`、`web/ui_mode.py`，以及阶段 5 计划拆出的 `web/ui_mode_request.py`、`web/ui_mode_store.py`、`web/render_bridge.py`、`web/manual_src_security.py`。

当前审计文件：`audit/2026-05/phase5_startup_fallback_baseline.json`。

当前 raw scanner 基线：

- fallback_count: 109
- cleanup_best_effort: 17
- observable_degrade: 35
- silent_default_fallback: 39
- silent_swallow: 18
- scope_tag 为空: 86
- scope_tag=render_bridge: 18
- scope_tag=startup_guard: 5
- accepted_risk_count: 5

台账当前口径仍以 `scripts/sync_debt_ledger.py check` 为准：阶段 4 收口后 `silent_fallback_count=153`。raw scanner 数量和台账数量不是同一个展示口径；阶段 5 收口时以台账 check 和 clean gate 双重结果为准。

## 选中条目

### P5-1 启动链 baseline 和新文件扫描范围

- 风险等级：中
- 当前问题：拆 `web/ui_mode.py` 前如果不先扩扫描范围，后续新文件可能漏扫，导致门禁看起来变好但真实风险被搬家。
- 处理策略：先补扫描范围/合同测试，再拆文件。
- 验证：`tests/test_architecture_fitness.py::test_no_silent_exception_swallow`、`tests/test_architecture_fitness.py::test_startup_silent_fallback_samples`、`tests/regression_quality_gate_scan_contract.py`。

### P5-2 runtime capability 结果模型

- 风险等级：低
- 当前问题：启动链里有一些“失败后默认继续”的路径，后续需要统一表达“可用 / 降级 / 不可用”和原因。
- 处理策略：新增 `web/bootstrap/runtime_capabilities.py`，先提供小模型和测试，再逐步接入 launcher。
- 验证：`tests/test_runtime_capabilities.py`。

### P5-3 launcher fallback 收敛

- 风险等级：高
- 当前问题：launcher paths/contracts/processes/stop/network/probe 中仍有能力不可用、清理 best effort、进程识别失败等路径，必须避免把“无法确认”当成“成功”。
- 处理策略：按 paths/contracts -> processes -> stop -> network -> runtime_probe 顺序收敛，保守处理 Chrome profile、PowerShell、WMI/CIM、runtime stop。
- 验证：Win7 launcher/runtime 相关定向回归。

### P5-4 web/ui_mode.py 拆分

- 风险等级：高
- 当前问题：`web/ui_mode.py` 同时承担请求读取、DB 读取、模板桥接、manual src 安全和 fallback 记录，既超长又容易混淆 startup_guard 与 render_bridge。
- 处理策略：保留 `web/ui_mode.py` facade，不改同名包；拆出 request/store/render/security 四类职责，public API 不变。
- 验证：`tests/test_ui_mode.py`、manual src、render bridge、fallback scanner 相关回归。

### P5-5 accepted risk 和 Win7 复核

- 风险等级：中
- 当前问题：一部分风险只有 Win7 真机或虚拟机才能最终证明。
- 处理策略：已消除且扫描不再命中的 risk 删除；必须现场复测的风险保留 owner、reason、review_after、exit_condition，并写审计记录。
- 验证：Win7 复核记录和 clean quality gate。
