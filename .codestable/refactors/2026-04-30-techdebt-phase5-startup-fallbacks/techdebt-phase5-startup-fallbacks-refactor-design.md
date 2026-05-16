---
doc_type: refactor-design
refactor: 2026-04-30-techdebt-phase5-startup-fallbacks
status: approved
scope: 启动链 fallback、launcher 运行时能力和 web/ui_mode.py 拆分
summary: 把启动链和 UI mode 的无声回退改成显式失败、可观测降级或可复核 best effort
tags: [techdebt, startup, fallback, win7]
---

# techdebt phase5 startup fallbacks refactor design

## 1. 本次范围

- 记录阶段 5 启动链 fallback baseline。
- 先让扫描器覆盖 `web/ui_mode.py` 拆分后的新文件，避免把风险搬出扫描范围。
- 新增 runtime capability 结果模型。
- 收敛 launcher paths/contracts/processes/stop/network/runtime_probe 的静默回退。
- 拆 `web/ui_mode.py`，保留 facade 和旧 public API。
- 收口 accepted risk 和 Win7 复核记录。

明确不做：

- 不改 Win7 / Python 3.8 兼容边界。
- 不误杀普通 Chrome；无法确认身份时失败闭合。
- 不把端口自动换路删除，但必须可观测。
- 不把 `safe_url_for()` 缺 endpoint 改成粗暴 500，但必须 warning。
- 不修改阶段 4 已归档内容，除非阶段 5 审查发现必须补充的交接说明。

## 2. 前置依赖

- 阶段 4 clean quality gate 已在提交 `ae4c421` 后通过。
- 当前阶段 5 分支：`codex/techdebt-phase5-startup-fallbacks`。
- 固定解释器：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`。

## 3. 执行顺序

### 步骤 1：记录阶段 5 baseline

- 操作：生成 `audit/2026-05/phase5_startup_fallback_baseline.json`，记录 fallback kind、path、symbol、line、scope_tag、accepted risk。
- 退出信号：基线提交只包含 audit 和 CodeStable 记录，不改业务代码。
- 验证责任：AI。

### 步骤 2：更新扫描范围和合同测试

- 操作：确保 `web/ui_mode_request.py`、`web/ui_mode_store.py`、`web/render_bridge.py`、`web/manual_src_security.py` 进入启动链 fallback 扫描范围，并且 `startup_guard` 与 `render_bridge` 的 scope_tag 不混账。
- 退出信号：架构适应度和扫描合同测试通过。
- 验证责任：AI。

### 步骤 3：新增 runtime capability 结果模型

- 操作：新增 `web/bootstrap/runtime_capabilities.py` 和测试，表达 available / degraded / unavailable。
- 退出信号：降级和不可用有 reason，允许继续运行的降级有日志。
- 验证责任：AI。

### 步骤 4：收敛 launcher fallback

- 操作：按 paths/contracts -> processes -> stop -> network -> runtime_probe 顺序处理。
- 退出信号：能力不可用不伪装成成功；Chrome profile 和 runtime stop 无法确认时失败闭合；相关 Win7 launcher 回归通过。
- 验证责任：AI。

### 步骤 5：拆分 web/ui_mode.py

- 操作：保留 `web/ui_mode.py` facade，拆出 request/store/render/security 模块。
- 退出信号：public API 不变；现代模板缺失可回退，真实渲染异常不伪装；manual src 外站丢弃；scanner 覆盖新文件。
- 验证责任：AI。

### 步骤 6：accepted risk 和 Win7 复核

- 操作：刷新台账；删除已消除风险，保留必须 Win7 真机/虚拟机证明的风险；写 `phase5_win7_startup_review.md`。
- 退出信号：保留 risk 都有 owner、reason、review_after、exit_condition；Win7 未执行真机复测则明确写明。
- 验证责任：AI + HUMAN（如有 Win7 环境）。

### 步骤 7：阶段 5 对抗审查和 clean gate

- 操作：新开至少 4 个 subagent 审查 Chrome/profile、scanner 漏扫、accepted risk、ui_mode facade/API。
- 退出信号：无阻断问题；`scripts/run_quality_gate.py --require-clean-worktree` 通过。
- 验证责任：AI。

## 4. 风险与看点

- Chrome 进程识别必须保守；没有精确 `--user-data-dir=` 证据就不能清理。
- PowerShell/WMI/CIM 不可用不能被当成“没有进程”。
- cleanup best effort 可以保留，但必须有日志、结果或 accepted risk。
- `web/ui_mode.py` 拆分后不能让 scanner 漏扫，也不能让 `render_bridge` 和 `startup_guard` 混成一个账。
- accepted risk 不能变成“还没修”的遮羞布；只有 Win7 现场才能证明的才保留。
