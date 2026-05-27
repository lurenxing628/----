---
doc_type: feature-acceptance
feature: 2026-05-27-aps-three-gap-docs-quality-gate
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: aps-three-gap-docs-quality-gate
accepted_at: 2026-05-27
---

# APS 三个差距方向文档和质量门禁收口验收

## 1. 验收结论

第 14 项已完成。本条主目标是把第 1-13 项做成可交接的说明和测试收口；复审过程中发现的页面说明、路由清单和现场反馈前端输入不一致问题已同步修正，但没有改排程算法、延期诊断结论规则或 scenario 发布业务逻辑。

- 用户说明用中文大白话说明方案对比、延期解释、现场反馈、计划和现场实际、重排保护。
- 开发测试说明标注“仅给开发和测试使用，不给用户看”，并集中说明内部协议、测试清单、关键 Python 文件、Win7 离线验收和质量门禁命令。
- 文档质量测试会检查用户说明不泄漏内部字段，开发说明保留内部协议，items.yaml 里的测试文件都能在开发说明里找到。
- 离线静态资源测试继续覆盖 `docs/aps_frontend_workbench_mockup.html`，阻止外链脚本、外链样式、外链字体、CDN 和用户可见旧草稿词。

## 2. 主要产物

- `static/docs/aps_three_gap_user_guide.md`
- `docs/dev/aps_three_gap_quality_gate.md`
- `tests/regression_aps_three_gap_docs_quality_gate.py`
- `tools/scan_aps_three_gap_py38_scope.py`
- `static/docs/scheduler_manual.md`
- `web_new_test/static/docs/scheduler_manual.md`
- `docs/aps_frontend_workbench_mockup.html`
- `tests/regression_frontend_offline_static_assets.py`
- `tools/quality_gate_shared.py`

## 3. 用户可见说明验收

- 用户说明只写业务能看懂的话，不显示 `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`event_type`、`ReasonCode`、`score tuple`、`state_revision` 等内部名字。
- 手册页和示例页清理了“第一版”“当前阶段”“后续开放”“静态 HTML 原型”“设计讨论材料”等旧口吻。
- `static/docs/scheduler_manual.md` 和 `web_new_test/static/docs/scheduler_manual.md` 已保持一致。
- 页面级说明新增“计划和现场实际”入口后，同步更新了 registry 测试，避免手册入口数量和真实入口脱节。

## 4. 开发测试说明验收

- `docs/dev/aps_three_gap_quality_gate.md` 已在文件开头和 Win7 验收小节标明“仅给开发和测试使用，不给用户看”。
- 开发说明列出 PlanIdentity、EvidenceLink、OperationExecutionEvents、OperationExecutionState、state_revision、execution_snapshot_revision、execution_snapshot_op_ids 等内部协议。
- 开发说明明确旧 explore 后半段路线草案已被本 roadmap 覆盖，后续以 roadmap 主文档和 items.yaml 为准。
- 第 1-13 项 feature、精准测试、回归测试清单和关键 Python 文件已集中列出。

## 5. 对抗性审查记录

第 14 项已进行了 7 轮、28 个只读 SubAgent 审查，均已关闭。前 3 轮在本条文档、测试和门禁产物成型过程中完成；第 4 轮到第 7 轮按同颗粒度整阶段复审，阻塞项修复后继续复审，直到最后一轮阻塞项为 0。

- 第一轮 4 个：用户说明、开发说明、测试门禁、Win7 离线四个切片均发现文档和测试收口不完整。修复：新增用户说明、开发测试说明、文档质量测试、Python 3.8 动态扫描工具，并接入质量门禁计划。
- 第二轮 4 个：发现用户可见旧草稿词、items.yaml 未列新增 docs 测试、Python 3.8 扫描范围说明不完整。修复：清理旧词，补 item14 test_commands，补动态扫描工具和固定扫描命令。
- 第三轮 4 个：
  - `019e6a97-de07-7603-962d-faafa11508cc`：发现手册 registry 数量未同步、用户可见内部英文名、旧草稿话术。已修复，并用手册测试组验证。
  - `019e6a98-0982-7892-94a5-f08cfa555543`：发现第 14 项验收未收口、第 5 项 items.yaml 测试命令与 acceptance 不一致、clean proof 尚未运行。已补第 5 项测试命令并写入本 acceptance；clean proof 留到提交后工作区干净时运行。
  - `019e6a98-4239-7880-bdb7-b5024c8c58eb`：未发现代码/测试阻塞，指出 clean-worktree 长门禁尚未验证。留到提交后验证。
  - `019e6a99-193a-7bb2-b9a2-b7ed413ba07e`：指出当前 dirty worktree 无法作为 clean proof、CodeStable 状态未完成。已完成 CodeStable 回写；clean proof 留到提交后验证。
- 第四轮 4 个：
  - `019e6aeb-a456-7b93-a853-0fa1fa7a56ae`：发现 acceptance 仍有“待最终复跑记录”，roadmap / checklist 状态早于最终验证。已补真实复跑记录，并把提交前与提交后 clean proof 口径分开。
  - `019e6aeb-cb6d-7dd2-8825-1eed3fee57fb`：未发现测试和质量门禁阻塞，建议保留 pyright tools 覆盖证明。已补 `pyrightconfig.tools.json` 覆盖验证记录。
  - `019e6aec-10c4-7dc3-96ec-9f7b62cb6597`：未发现前端、用户可见中文和离线资源阻塞。
  - `019e6aeb-ef04-70e1-92ba-80bcadd150c0`：发现服务层仍有报表/排程直写 SQL、延期诊断链接路径不准确，并指出甘特架构说明里 scenario 导出口径过期。已把 SQL 下沉到 repository，修正 `/material/batches` 和 `/reports/downtime` 跳转，更新架构说明并补测试断言。
- 第五轮 4 个：
  - `019e6b19-7fca-70c1-9c9c-18e8153202be`：发现第 13 项 acceptance 缺 YAML 头。已补 `feature-acceptance / accepted` frontmatter，并用 CodeStable YAML 工具验证。
  - `019e6b19-8049-74d0-95d5-edba0cfe0557`：实现链复审 OK。
  - `019e6b19-80c1-74d0-85b1-668618d1d96d`：测试和门禁链未发现阻塞，提醒 clean proof 需提交后运行。
  - `019e6b19-813b-7362-a110-649751ce6c30`：发现开工实际资源说明和页面操作不一致、报表模拟预览导出说明冲突。已让开工动作要求确认实际设备并填写实际人员，修正模拟预览导出口径，并补测试断言。
- 第六轮 4 个：
  - `019e6b26-66a9-7101-a3c2-3b42cc8e4ea0`：CodeStable 产物无阻塞，仅提醒提交后 clean proof。
  - `019e6b26-6757-7eb0-b28c-332af39795f5`：实现链复审 OK。
  - `019e6b26-67ce-73d1-a1f1-6362c69d0c43`：门禁链复审未发现阻塞，已跑第 10-14 项相关检查。
  - `019e6b26-6863-7252-87e6-cc85d41749b4`：发现资源排班手册仍写三种视图和旧 11 列、模拟预览导出手册口径冲突、开工弹窗有“第一版”话术。已更新手册和页面帮助为四种视图 / 14 列，修正模拟导出说明，去掉旧话术，并补回归断言。
- 第七轮 4 个：
  - `019e6b31-520d-76e3-89d6-ed4475c1be0f`：CodeStable 产物复审 OK，阻塞项 0。
  - `019e6b31-52d0-7401-811b-af0d820b7418`：实现链复审 OK，阻塞项 0。
  - `019e6b31-5338-7721-8335-9945d5b24043`：测试和门禁链复审 OK，阻塞项 0。
  - `019e6b31-53e4-7c42-b282-44438cc60978`：用户可见页面、手册、导出说明和离线资源复审 OK，阻塞项 0。

## 6. 已修复的阻塞项

- 手册入口数量从 45 变 46 后，`tests/regression_page_manual_registry.py` 没同步：已加入 `reports.execution_review_page`。
- 用户可见说明里的 `primary / success / danger / info`、`dirty_fields`、`input / select`：已改成中文说明。
- 甘特图手册和页面说明里的“后续开放”：已改成当前真实行为说明。
- 示例页里的“原型 / 设计讨论材料 / 资源派工”：已改成“示例 / 页面参考 / 资源排班”。
- 第 5 项 `candidate-summary-delta-cards` 的 items.yaml 测试命令漏掉 summary 和 graph 测试：已补齐并同步开发说明。
- 第 14 项精准测试命令没有覆盖手册 registry：已加入 `tests/regression_config_manual_markdown.py`、`tests/regression_page_manual_registry.py`、`tests/regression_reports_layout_contract.py`。
- 质量门禁发现 `开发文档/系统速查表.md` 漏了 9 个新路由：已补计划和现场实际报表、资源排班现场反馈数据、事件、开工、完工、暂停、继续生产、报异常接口，并用 `tests/check_quickref_vs_routes.py` 验证。
- 文档测试清单漏了本轮收口中实际修改的工具和测试文件：已补 `.codestable/tools/validate-yaml.py`、`tools/scan_py38plus_syntax.py`、`tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py` 等清单项。
- `core/services/report/queries.py` 已删除，报表查询回到 repository；开发文档中和当前实现强绑定的引用已避免继续把它当作现行分层依据。
- 第 13 项 `reschedule-respects-execution-facts` acceptance 缺 CodeStable YAML 头：已补 frontmatter，并用 `validate-yaml.py --require doc_type --require status` 验证。
- 资源排班开工动作原先没有让用户填写实际人员，说明却写“实际资源”：已让开工动作确认实际设备、填写实际人员和反馈人，后端仍校验设备必须是当前正式排程设备。
- 报表模拟预览导出口径在页面、手册、页面帮助里不一致：已统一为“导出的 Excel 也会按这个模拟方案生成，正式计划未改变”。
- 资源排班手册和页面帮助仍写三种视图 / 11 列：已更新为任务明细、日历矩阵、甘特图、现场反馈四种视图，以及包含现场状态、最近异常、影响资源的 14 列。
- 开工弹窗出现“第一版”交付前话术：已改成用户能直接理解的中文提示，并用测试锁住不再出现。

## 7. 验证记录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_reports_layout_contract.py`：13 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_frontend_offline_static_assets.py tests/regression_frontend_ui_language_polish.py tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_reports_layout_contract.py tests/regression_gantt_simulation_entry_shell.py tests/test_codestable_tools_contract.py tests/test_scan_py38plus_syntax.py tests/regression_aps_three_gap_docs_quality_gate.py tests/test_run_quality_gate.py`：180 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py tests/regression_operation_execution_exception_feedback.py tests/regression_plan_vs_actual_review.py tests/regression_scheduler_reschedule_execution_facts.py tests/regression_scheduler_reschedule_execution_minimum_guardrails.py tests/regression_gantt_adjustment_publish_execution_revision.py`：48 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_operation_execution_feedback_routes.py tests/regression_config_manual_markdown.py tests/regression_frontend_offline_static_assets.py tests/regression_frontend_ui_language_polish.py tests/regression_page_manual_registry.py tests/regression_reports_layout_contract.py`：55 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-27-reschedule-respects-execution-facts/reschedule-respects-execution-facts-acceptance.md --require doc_type --require status`：1 passed, 0 failed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider ... tests/test_architecture_fitness.py::test_services_do_not_use_assert_for_runtime_guards`：18 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items`：1 passed, 0 failed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_aps_three_gap_py38_scope.py --base-ref d4589d77`：扫描 114 个 Python 文件，0 个发现。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit scripts/run_quality_gate.py tools/quality_gate_shared.py tools/scan_aps_three_gap_py38_scope.py tests/regression_frontend_offline_static_assets.py tests/regression_frontend_ui_language_polish.py tests/regression_config_manual_markdown.py tests/regression_page_manual_registry.py tests/regression_gantt_simulation_entry_shell.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/regression_aps_three_gap_docs_quality_gate.py tests/test_run_quality_gate.py`：扫描 11 个 Python 文件，0 个发现。
- `.venv/bin/python -m ruff check --force-exclude -- tools/quality_gate_shared.py tools/scan_aps_three_gap_py38_scope.py tests/regression_frontend_offline_static_assets.py tests/regression_page_manual_registry.py tests/regression_aps_three_gap_docs_quality_gate.py web/viewmodels/page_manuals_reports.py web/viewmodels/page_manuals_system.py web/viewmodels/page_manuals_scheduler_outputs.py`：All checks passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors, 14 warnings。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json --outputjson`：40 files analyzed, 0 errors, 0 warnings。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：治理台账校验通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_quickref_vs_routes.py`：OK。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`：16 步均通过；因为当前工作区未提交，manifest 标记 `passed_but_unbound`，只能作为本地反馈，不能作为 clean-worktree proof。
- `git diff --check`：通过。

## 8. 仍需在提交后证明的事项

clean-worktree 长门禁必须在本条改动提交后、工作区干净时运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

如果工作区还有无关 dirty，只能用 allow-dirty 作为本地反馈，不能宣称 clean proof。
