---
doc_type: issue-fix
issue: 2026-05-03-phase6-contract-cleanup
status: completed
clean_proof_status: passed
path: fast-track
fix_date: 2026-05-03
tags: [contract, regression, scheduler, reports, plugins, python38]
---

# techdebt phase6 合同口径收敛修复记录

## 1. 问题描述

当前分支有一组回归测试已经把公开合同写清楚，但生产代码还停在另一套说法上。表现为页面提示、错误文案、Excel sheet 名、插件状态标签、配置字段标签和复杂度门禁不一致。

这些问题不是排产算法主体坏了，而是对用户和测试暴露的“话术、标签、错误边界”没有收口。

## 2. 根因

本轮根因集中在四类：

- 展示层仍保留旧文案，比如 OR-Tools 预热失败、恢复成功、插件加载失败、资源排班入口。
- 导出层 sheet 名用了中文展示名，但回归合同要求稳定英文 key。
- source 合同有的入口说“自制/归属”，有的测试要求“内部/来源”。
- 复杂度门禁发现 `_build_link_dirty_summary` 同时做筛行、收字段、收原因和组装结果，函数复杂度刚好超过阈值。

## 3. 修复方案

按当前失败测试作为合同源，定点改生产代码：

- 排产摘要、说明书、自动分配、兼容读取、外协组日志统一到测试要求的公开口径。
- 工序 source、报表导出、恢复成功、批量删除、插件状态、配置字段和首页入口按回归合同收敛。
- `route_parser_errors.py` 恢复严格校验提示片段，同时只调整中文治理测试里对该已批准合同词的禁止项，继续禁止 `strict_mode`、raw debug 和英文内部字段泄漏。
- 拆分 `web/routes/personnel_detail_context.py::_build_link_dirty_summary`，不新增复杂度白名单。

## 4. 改动范围

- 排产与摘要：`core/algorithms/greedy/internal_operation.py`、`core/shared/compat_parse.py`、`core/services/scheduler/summary/*`、`web/viewmodels/scheduler_degradation_presenter.py`、`web/routes/domains/scheduler/scheduler_config.py`
- 工艺与外协：`core/services/process/*`、`web/routes/process_excel_part_operation_hours.py`
- 报表与系统：`core/services/report/*`、`web/routes/system_backup_actions.py`、`web/routes/process_parts.py`
- 插件和配置页面：`web/bootstrap/plugins.py`、`templates/system/backup.html`、`templates/scheduler/config.html`、`web_new_test/templates/scheduler/config.html`
- 首页入口和复杂度：`templates/dashboard.html`、`web_new_test/templates/dashboard.html`、`web/routes/personnel_detail_context.py`
- 合同测试同步：`tests/regression_frontend_ui_language_polish.py`

## 5. 验证结果

- 目标合同集合：`48 passed`。
- 防串味集合：`52 passed`。
- `git diff --check`：通过。
- 触达文件 `ruff check`：通过。

目标合同集合包含本轮列出的排产摘要、SP05 说明书路径、自动分配、兼容读取、外协日志、工时导入、报表导出、恢复、路线解析、warmstart、批量删除、source 合同、插件状态、配置跟进、资源排班 smoke，以及复杂度门禁。

防串味集合覆盖插件配置失败可见性、外协组 strict/route warning、配置字段合同、资源排班 viewmodel/boundary、资源排班导出降级，以及中文治理中和本次合同相关的检查。

## 6. 收口说明

本轮已按课题组拆成本地提交。提交后首次运行总门禁时，先发现仓库里有陈旧 APS 运行痕迹；确认对应本地进程没有健康服务后已停止并清理运行痕迹。

随后总门禁继续发现 10 个旧合同差异，集中在历史摘要日志、系统历史告警数量、说明书缺配置文案、已有排产记录错误、甘特图关键链图例。已补充修复并验证：

- 门禁点名的 10 条失败测试：`10 passed`。

补充修复提交后，已在干净工作区运行最终总门禁：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

结果：`质量门禁通过`。

最终总门禁过程中还发现技术债台账里 2 条已登记复杂度旧债的扫描值过期：`excel_routes_confirm` 当前扫描值为 27，`_sanitize_batch_dates` 当前扫描值为 20。已只同步台账里的当前扫描值和验证时间，没有新增白名单，也没有登记临时债。
