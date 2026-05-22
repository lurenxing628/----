---
doc_type: feature-acceptance
feature: 2026-05-22-gantt-readonly-docs-and-qa
roadmap: gantt-result-view-and-manual-adjustment
roadmap_item: gantt-readonly-docs-and-qa
status: accepted
accepted_at: 2026-05-22
---

# 只读甘特图第一版验收记录

## 1. 完成范围

- 路线图已收口为“只读甘特图结果查看 + 时间缩放”优先完成，模拟调整、草稿、方案、正式发布保留为后续路线。
- 页面默认查看模式，显示“当前为查看模式”，任务条不能拖动、拉伸或改进度。
- 时间粒度支持月、周、日、12小时、6小时、小时、15分钟、5分钟、1分钟。
- `gantt_zoom` 和筛选/配色/关系线参数可从 URL 恢复，并可写回 URL。
- 加载表单、设备视图/人员视图链接会延续当前缩放。
- 短工序按真实时长显示，透明点击区只负责好点，不放大真实工序时长。
- 分钟级范围过大、列数过多或节点估算过高时会阻止渲染并提示。
- 显式 `00:00:00` 结束不再把短工序误扩成整天；分钟视图里次日 `00:00:00` 会按自然日边界处理，避免单日 1 分钟视图被误拦。
- 说明书、页面帮助、浏览器压测手册、vendor 补丁说明和回归测试已同步。

## 2. 明确未做

- 没有做拖动保存。
- 没有新增草稿保存接口。
- 没有新增正式采用接口。
- 没有写 `Schedule`。
- 没有写 `ScheduleHistory`。
- 没有改变正式版本指针。
- 没有把模拟调整按钮做成可保存入口。
- 没有引入 CDN 或必须联网的前端资源。
- 没有做秒级、0.1 秒或虚拟滚动。

## 3. 浏览器验收

本机实际打开 `http://127.0.0.1:5000` 验证，当前主库最新排产版本为 `14`，甘特图数据接口返回 `18` 条任务。

- `/system/health` 返回 `app=aps`、`status=ok`。
- `/scheduler/gantt?view=machine&gantt_zoom=day` 页面可打开，能看到查看模式提示、9 个缩放选项、`data-gantt-mode="view"`。
- 完整版本范围下，月、周、日、12小时、6小时可渲染；小时、15分钟、5分钟、1分钟因范围太宽会提示缩小范围。
- 单日范围下，小时、15分钟、5分钟可渲染。
- 单日 + 批次筛选下，1分钟视图能显示并点击 `BROWSER-0511-HOT-01_30` 这条 36 分钟工序。
- 点击 36 分钟工序能打开弹窗，弹窗显示批次、工序、设备、人员和开始结束时间。
- 尝试拖动该任务条后，`x` 和 `width` 保持不变，页面没有拖动手柄。
- 打开非法 `?gantt_zoom=bad-value` 会回到日视图，并保留“链接里的时间粒度无法识别，已切回日视图。”提示。
- 打开 `gantt_zoom=five-minute` 后，加载表单隐藏字段和设备/人员视图链接都会带上 `gantt_zoom=five-minute`。

## 4. 自动化验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_frappe_gantt_short_task_contract.py tests/regression_gantt_zoom_contract.py tests/regression_gantt_readonly_mode_contract.py tests/regression_gantt_zoom_decoration_sync.py tests/regression_gantt_zoom_range_guard.py tests/regression_gantt_critical_outline_sync.py tests/regression_gantt_default_version_span.py tests/regression_gantt_url_persistence.py tests/regression_frontend_ui_language_polish.py`：61 passed。
- `node --check static/js/gantt_zoom.js`：通过。
- `node --check static/js/gantt_ui.js`：通过。
- `node --check static/js/gantt_render.js`：通过。
- `node --check static/js/frappe-gantt.min.js`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check --no-cache -- web/routes/domains/scheduler/scheduler_gantt.py tests/regression_gantt_url_persistence.py tests/regression_gantt_zoom_range_guard.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`：13 个步骤实际执行完成，`failed=0`，但命令退出码为 2，因为当前工作区未提交，门禁标记为 `passed_but_unbound`。这不能当作 clean-worktree final proof。

## 5. 对抗审查

- 验收前实际启动了 4 个子代理，分别检查 CodeStable 收口、浏览器验收路径、质量门禁/运行时停止路径、代码质量风险。
- 子代理发现的阻塞问题“非法 `gantt_zoom` 提示会被渲染清掉”已修复，并补回归。
- 子代理指出的“加载表单和设备/人员视图链接会丢缩放”已修复，并补浏览器证明。
- 主线程在浏览器验收中补抓到“次日 `00:00:00` 会让 1分钟单日误判两天”的边界，已修复并补测试。

## 6. Roadmap 回写

- `gantt-result-view-and-manual-adjustment-items.yaml` 前 6 个只读阶段已回写为 `done`。
- roadmap 主文档“子 feature 清单”前 6 项已同步为 `done`，对应 feature 为 `2026-05-22-gantt-readonly-docs-and-qa`。
- 后续模拟调整相关 item 仍保持 `planned`，并依赖 `gantt-readonly-docs-and-qa`。

## 7. 剩余边界

- 当前没有 Win7 Chrome 109 真机 500/1000/2000 任务手工压测结果；手册已经给出复跑矩阵。当前浏览器验收只证明本机真实页面和当前库 18 条任务场景。
- 当前没有 clean-worktree final proof。原因是仓库仍有一批未提交改动，门禁只能给出 dirty-worktree unbound 证明。提交或清理工作区后，需要再跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
