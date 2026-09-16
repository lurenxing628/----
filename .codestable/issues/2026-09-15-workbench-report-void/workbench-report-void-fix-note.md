---
doc_type: issue-fix-note
status: fixed
date: 2026-09-15
title: 单次报工显式撤销及统一有效事实投影
---

## 授权与边界

承接 `workbench-manual-remediation` 的 `wbfix-report-void` / B4 / 合同 5.8。用户授权并行实施，并明确禁止全门禁。本条目只运行报工及受影响读取方的专项测试，未运行 `run_quality_gate.py` 的任何模式，也未运行整仓测试。

用户当前工作区原有大量未提交改动。本条目保留原改动，不提交，不操作正式数据库，不启动正式应用，不自行更新 `static/workbench`。v32 的公共迁移、固定 schema.sql、测试注册和最终构建由主代理及 schema 集成代理统一完成。

## 行为

- 现场每条有效报工新增可见的“撤销”操作，使用 `rotate-ccw`，与真正删除资料的垃圾桶含义区分。
- 用户填写原因后查看撤销影响。页面列出累计完成数量、剩余量和执行状态的前后变化；有后道开工/完工、已采用计划或已采用工时定额依赖时，列出具体工序/采用记录并禁用确认。
- 点击“确认撤销这次报工”追加一次撤销事实。原报工、原单号、所有更正、原数量、原工时和原操作者均保持不变。历史折叠区仍能查看这些内容及撤销原因、经办人、时间和回执。
- 同键重试重放原回执；对已撤销目标重新确认返回 unchanged，不重复扣减。改过原报工后使用旧版本撤销返回 `context_stale`；改原因、改经办人或预览后有新事实必须重新预览。
- 数量 0 仍代表实际发生的零产出。只有显式撤销才从有效报工中排除。撤销一条不影响同工序的其他报工；历史实际开工/完工事件继续有效。
- 已撤销报工不能补齐、更正或用原单号重新导入，以免无意复活旧事实。

## 数据与接口

新增 `core/infrastructure/workbench_execution_void_schema.py`，由显式 v32 迁移调用 `install_execution_voids(conn)`。新增 `WorkbenchProductionReportVoids`，以 `report_ref` 唯一绑定单次报工及原 `original_revision_ref`。原 ledger v25 安装合同未修改。

七个对象包括表、ledger clock 递增、当前版本绑定、已撤销记录禁止新增修订、禁止 UPDATE/DELETE/INSERT OR REPLACE 触发器。若结构缺失或部分丢失，读取失败，不能把撤销记录当作不存在而重新计入原报工。

接口沿用现场普通命令的回执与事务：

- `POST /api/workbench/v1/execution/reports/<report_ref>/void-preview`，`{input: {original_revision_ref, reason, declared_operator}}`；只读，返回 `target_report / before / after / downstream_impacts / can_confirm / write_context`。
- `POST /api/workbench/v1/execution/reports/<report_ref>/void`，普通 `{input, write_token, request_key}`；命令为 `execution.report_void`，结果含 `report_ref / void_fact_ref / state=voided / refresh_required=true`。
- `ExecutionProjection.reports` 始终只含有效报工；新增 `voided_reports=[{report, void_fact}]` 仅供审计展示。唯一的中立 `ExecutionLedgerReader` 完成过滤，因此现场、实际甘特、剩余量、复盘、报表、风险及校准共用同一有效事实集合。
- 受理时归档的候选基线按同一归档内的撤销表重新投影，不读取后来当前库的事实。排产快照 DTO 只对唯一旧形态显式补空 `voided_reports`，其余字段继续严格检查。

关键实现：`production_report_void.py:37` 读取和模拟；`:88` 事务复查和幂等写入；`production_report_void_dependencies.py` 检查已采用定额样本；`execution/ledger_reader.py:61` 统一过滤；`run_candidate_baseline.py` 校验受理时归档；`execution_ledger_adapter.py` 排除只有撤销报工的工序范围约束。

## 界面

新增 `FieldVoidEditor.jsx`，由主代理加入正式 build-order，置于 `FieldDetail.jsx` 之前。`FieldAPI.js` 与 `resource-api.js` 接入撤销预览和普通 pending 回执查询。

现场表格原操作列仅占 11%，新增文字按钮后在 1280 屏会被裁掉。现改为独立 190px 操作列和可换行按钮组，调整相邻字段列宽；专项截图已核对操作文字完整。改动只作用于现场报工表格。

## 专项证据

最终后端专项：

```text
.venv/bin/python -m pytest -q \
  tests/workbench/test_execution_report_void.py \
  tests/workbench/test_field_report_void_api.py \
  tests/workbench/test_report_void_projections.py \
  tests/workbench/test_round1_execution_dependency_contract.py::test_workbench_alone_issues_write_contexts
20 passed
```

覆盖只读预览、原历史逐表保留、零产出、撤销多条之一、实际资源区间、同键重放、不同键不重复撤销、版本及快照过期、后道和正式计划依赖、历史开工、失败回滚、撤销不可变、缺表不能复活事实、真实 HTTP、实际甘特/复盘/风险/校准/候选归档。

浏览器专项：`test_field_report_void_browser.py` 通过；离线 Chrome 109、临时 SQLite、当前源码单独编译，无全局 build。五条真实 UI→HTTP 路径覆盖可见图标、原因与预览、修改原因使预览失效、确认后自动回读原历史、后道阻断。1392×924、1280×720 浅色及深色截图，补充动作按钮不裁字的几何断言。

最终浏览器证据目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-report-void-browser-3z8z_rtp/`。补齐撤销历史的原实际起止、设备/人员和备注显示后，对应 3 项 HTTP + 1 项浏览器专项再次通过。这是自动化专项证据，不能冒充用户要求的全量手动验收。

原报工/约束/现场 HTTP/排产消费回归 58 项通过。候选基线扩大专项 45 项通过、1 项因已有文案预期不一致失败：`test_run_candidate_baseline_queries.py::test_no_original_plan_is_explicit_and_not_a_zero_baseline` 期待旧文案“排产时没有正式的初始计划，算不出相对改善。”，当前产品为“排产时没有正式计划可供对比。”；本条目未修改该产品文案，已报主代理合并验收。

`node tests/workbench/test_field_fastpath.cjs` 的 8 项旧快速录入合同及全部 Field 源码 Chrome 109 编译通过。所改文件的 `git diff --check` 通过。

## 尚由主代理完成

公共 v32 迁移与构建集成、真实项目浏览器的最终手动验收。原未提交内容继续保留。本条目没有 clean-worktree proof，也不声称整项目或全功能已经通过。
