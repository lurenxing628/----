---
doc_type: issue-fix
issue: 2026-05-23-review-report-dedupe-fix-plan
path: standard
fix_date: 2026-05-23
status: pending_clean_proof
clean_proof_status: not_available_dirty_worktree
tags: [review, scheduler, gantt, resource-dispatch, quality-gate, database, codestable]
---

# Review 报告剩余问题修复记录

## 1. 当前状态

本轮已经把 `.codestable/audits/2026-05-23-review-report-dedupe/index.md` 去重后留下的主要问题推进到当前工作区：

- P1 的 F-01 到 F-07 已经有对应代码、文案和回归测试改动。
- P2-1、P2-2、P2-3 已经实际纳入本轮实现。
- P2-4 已同步本轮实际改到的架构文档、页面帮助和用户手册。

但现在还不能写成“可合并”：

- 当前工作区仍有未提交修改。
- 因为工作区不干净，不能声称已经通过 `--require-clean-worktree` 的最终质量门禁。
- 最终 clean proof 应在提交整理后，再跑 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。

## 2. 已修内容

### Batch 0：质量门禁缺口

- 把新增高风险回归纳入 `tools/test_registry.py`。
- 同步 `tests/test_run_quality_gate.py`，让质量门禁自测能发现注册表漏项。
- 新增/补强的必跑回归覆盖数据库高版本、Gantt 前端错误边界、资源排班公开输出。

### Batch 1：数据库高版本 fail-fast

- 在数据库启动、迁移预检、直接迁移和带备份迁移入口都先检查高版本数据库。
- 高版本数据库会直接抛 `MigrationContractError`，不会继续补表、不会跑迁移、不会先创建 `before_migrate` 备份。
- 回归测试增加“完整未来库”和“只有 SchemaVersion、缺业务表的未来库”两类场景，防止顺序被改错。

### Batch 2：分析页坏数字和未知值

- 分析指标 viewmodel 统一区分“字段不存在”和“字段存在但值不能安全展示”。
- `None`、空字符串、`NaN`、`Infinity`、非数字、`True/False` 不再被静默显示成 `0`、`1` 或正常百分比。
- 页面最终显示 `无法安全展示`，让用户知道这项数据不能信。

### Batch 3：报表和周计划边界

- 报表单边日期、坏日期格式和默认版本口径已有回归覆盖。
- 周计划模拟方案提示去掉重复普通提示，避免用户看到互相打架的说明。

### Batch 4：资源排班公开输出

- 增加 `core/models/resource_dispatch_public_labels.py`，统一把来源和锁定状态转换成用户能看懂的中文；服务层和 viewmodel 都依赖这个更底层的纯标签 helper，避免 viewmodel 反向依赖 `core.services`。
- 页面、Excel 明细和说明文档都使用 `自制`、`外协`、`已锁定`、`未锁定`、`来源未识别`、`锁定状态未识别`。
- Excel 汇总里的坏时间计数改成 `开始或结束时间写法不对，已过滤的记录数`。
- 资源排班导出文件名说明补上“会清理不能放进文件名的符号”。

### Batch 5：Gantt 前端错误边界

- `gantt_boot.js` 对数据请求失败、返回结构错误、脚本缺失、渲染准备异常、适配层异常都有页面可见错误。
- 用户页面只显示中文通用错误，不展示 `render`、`contract.renderHelpList`、`Gantt DOM mismatch` 这类内部名字。
- 具体缺哪个脚本仍交给 `reportClientError`，方便开发排查，但不暴露给普通用户。

### P2-1 / P2-2 / P2-3 / P2-4

- 关键链不可用原因继续保留公开原因码，不把真实原因折成 `unknown`。
- Week / Month 视图下假期背景只占一天宽度，已补真实 DOM 回归。
- `gantt_render.js` 已按职责拆出弹窗、图例、假期、装饰和帮助脚本；拆分后生产 JS 文件都低于 500 行。
- 两份 Gantt 模板、独立预览生成器和 tracked 证据 HTML 都补了新的 `gantt_help.js` 加载顺序。
- `.codestable/architecture/ui-gantt.md`、两份用户手册和说明蓝本已同步当前事实。

## 3. 对抗性审核后补的阻塞修复

本轮实现后又开了 7 个只读子代理做对抗性审核，发现并修掉了这些阻塞点：

- 分析指标底层数字解析必须拒绝 `True/False`，否则坏值会被 Python 当成 `1/0`。
- 用户手册里“模拟调整”的开放条件说法过期，已改成页面入口接好并放行后再开放。
- Gantt 缺脚本错误不能把内部脚本名显示给用户，已改成通用中文错误。
- 独立 Gantt 预览页少加载 `gantt_help.js`，已同步生成器和 tracked 证据 HTML。
- 数据库 preflight 测试的拦截要放在调用前，才能证明 fail-fast 之前不会补表或迁移。
- 分析文档里 P2-3 的计划说法已过期，已改成承认本轮实际纳入实现。

## 4. 验证结果

已通过：

- `git diff --check`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_database_high_version_failfast.py tests/test_database_migration_runner_delegation.py tests/regression_scheduler_analysis_viewmodel_split.py tests/regression_scheduler_analysis_diagnostic_contract.py tests/test_history_summary_parser.py tests/regression_gantt_frontend_error_boundary.py tests/regression_gantt_critical_outline_sync.py tests/regression_gantt_adapter_contract.py tests/regression_gantt_readonly_mode_contract.py tests/regression_gantt_zoom_decoration_sync.py tests/regression_gantt_zoom_range_guard.py tests/regression_resource_dispatch_public_output_contract.py tests/regression_resource_dispatch_export_surfaces_degraded.py tests/regression_frontend_ui_language_polish.py tests/regression_frontend_manual_blueprint_contract.py tests/regression_reports_page_version_default_latest.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_scheduler_candidate_week_plan_contract.py tests/test_run_quality_gate.py`：252 passed
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：通过
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`：13 步跑完，通过；结果标记为 `passed_but_unbound`，不能当成干净工作区最终 proof

没有声称完成：

- 还没有 clean-worktree final proof。
- 本轮收口已决定把 CodeStable 审计/issue 文档、输入 review 报告和排产全流程图文档一起纳入本次交付边界。
- 仍需在本地提交后，再用干净工作区跑最终门禁，把 proof 绑定到提交后的 HEAD。

## 5. 后续收口建议

- 提交前确认 `git status --porcelain=v1 -uall` 里没有 `AM`、没有意外 `??`、没有本应提交却仍未暂存的 ` M` 文件。
- 本轮已决定把 `.codestable/audits/2026-05-23-review-report-dedupe/`、`review-244fbb7-to-d37df6d.md`、`docs/scheduler-full-flow-mermaid.md/html` 一起纳入本轮提交。
- 提交后跑干净工作区质量门禁，把最终 proof 绑定到提交后的 HEAD。
