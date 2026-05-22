---
doc_type: feature-acceptance
feature: 2026-05-22-gantt-simulation-entry-shell
status: accepted
roadmap: gantt-result-view-and-manual-adjustment
roadmap_item: gantt-simulation-entry-shell
accepted_at: 2026-05-22
tags: [scheduler, gantt, simulation, frontend]
---

# gantt-simulation-entry-shell 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-22
> 关联方案 doc：`.codestable/features/2026-05-22-gantt-simulation-entry-shell/gantt-simulation-entry-shell-design.md`

## 1. 接口契约核对

- `ganttSimulationEntryShell` 已落在主模板和镜像模板，带 `data-simulation-state="disabled"`。
- `ganttSimulationEntry` 是 disabled 按钮，文案为 `模拟调整（后续开放）`。
- `#gantt` 仍保持 `data-gantt-mode="view"`，模板里没有 `data-gantt-mode="simulate"`。

## 2. 行为与决策核对

- 默认仍是查看模式：只读合同测试继续通过。
- 本阶段没有新增 JS 状态机、保存接口、后端路由、草稿表或正式发布入口。
- 模板和运行时 Gantt JS 不包含 `save-draft`、`adjustments/save-draft`、`ScheduleHistory` 或 POST 保存请求。
- 没有“保存成功”“正式采用”“提交调整”这类会误导用户的页面入口。

## 3. 验收场景核对

- 模拟调整入口可见但禁用：`tests/regression_gantt_simulation_entry_shell.py` 覆盖。
- 两份模板同步：同一测试覆盖 `templates/scheduler/gantt.html` 和 `web_new_test/templates/scheduler/gantt.html`。
- 入口壳样式独立在 `static/css/aps_gantt_simulation.css`，不继续增加主甘特图样式文件职责。
- 说明书和页面帮助说清不能点击、不会产生草稿或正式新版本：同一测试覆盖。
- 查看模式不退化：`tests/regression_gantt_readonly_mode_contract.py` 继续通过。

## 4. 术语一致性

- 本阶段只新增“模拟调整入口壳 / 占位入口 / 后续开放”这些方案内术语。
- 没有把 `Draft`、`Scenario`、`Official Version` 伪装成已上线能力。

## 5. 架构归并

- 已更新 `.codestable/architecture/ui-gantt.md`：说明当前页面上的模拟调整入口只是 disabled 占位，不进入 `simulate`，不保存、不写正式数据。

## 6. requirement 回写

- 本阶段不新增完整用户能力，只是为后续模拟调整放占位入口；既有只读甘特图 requirement 不需要升级。

## 7. roadmap 回写

- 已把 `gantt-simulation-entry-shell` 从 `in-progress` 回写为 `done`。
- 主 roadmap 子 feature 清单和变更日志已同步。
- 下一阶段仍是 `gantt-adjustment-draft-model`。

## 8. attention.md 候选盘点

- 无新的通用启动注意事项。

## 9. 验证记录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_simulation_entry_shell.py tests/regression_gantt_adapter_contract.py tests/regression_gantt_readonly_mode_contract.py tests/regression_scheduler_candidate_py38_contract.py tests/test_run_quality_gate.py`：104 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tests/regression_gantt_simulation_entry_shell.py tests/regression_scheduler_candidate_py38_contract.py tools/test_registry.py web/viewmodels/page_manuals_scheduler_outputs.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/gantt-result-view-and-manual-adjustment/gantt-result-view-and-manual-adjustment-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-22-gantt-simulation-entry-shell`：通过。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：通过。
