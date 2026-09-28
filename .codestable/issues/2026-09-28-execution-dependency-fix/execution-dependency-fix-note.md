---
doc_type: issue-fix-note
status: verified-related-scope
date: 2026-09-28
issue: execution-dependency-fix
summary: 修复报工前后序时间和共同分件撤销保护，解决旧报工用例缺少设备能力表的24项失败，并记录独立复查发现
---

# 报工依赖保护修复

用户授权主代理修复两处已复现问题及 24 个失败用例，同时调用一个 sub agent 沿原高风险路径只读复查。唯一子代理 `high_risk_execution_rescan` 未改仓库、未派生其他代理。未运行日常或完整门禁，未提交、推送、发布或操作生产数据库。

## 已修复

1. **更正能写入倒置的前后序实际时间。** 原校验只查后序，没有检查前序。本次新增、补齐、更正共同核对已有实际前后序：09:45 完工的前序不能接 09:30 开工的后序，拒绝时事实、修订、回执和时钟均不变。合法更正后再次排产能够正常完成。
2. **共同工序和分件工序之间漏掉撤销保护。** 原查询只按同一 `piece_id` 查后序。`ReportDependencies` 现在对混合路线复用 `build_piece_adoption_scope` 的共同/分件关系，沿全部传递依赖查找上下游；原有纯分件路线仍逐件连接。分流和汇合两种结构，后序有正式安排或实际报工时均明确拒绝撤销。互不依赖的分件保持独立。
3. **同根因入口与批量一致性。** 子代理另行复现新增报工也能制造相同时间矛盾，已一并覆盖。批量处理按全部修改后的最终投影校验，不按旧数据库投影或输入行序判断；合法的成套时间修正允许保存，最终仍冲突时整批拒绝。
4. **24 项旧回归失败。** 旧 `ledger_case` 为隔离报工迁移保留 v24 基底，但报工资源校验已依赖设备多工种表。测试建库时显式安装现行 `MachineOpTypes` 合同，不改变产品缺表保护或历史迁移测试的版本基底。两个原测试另有不合法场景：后序早于已完成前序，以及共同工序/分件使用同一顺序号；改为合法的先后时间和完整的 10 件分件路线，原撤销保护与单件数量断言保留。

新增报工只核对已经发生的实际时间，不用尚未开工的旧计划阻拦真实晚完工；更正和撤销继续保留原正式计划保护。合并外协按保存的批次外协事实识别同一周期，允许同组成员的实际时间重叠。依赖读取不签发额外编辑令牌。没有修改前端组件和样式。

## 验证与复查

证据目录：[evidence/execution-dependency-fix-20260928](../../../evidence/execution-dependency-fix-20260928/)。本轮起点文件哈希保存在 `/tmp/aps-execution-dependency-before-20260928.json`，相关原文件备份为同名 `.tar.gz`。

| 范围 | 结果与边界 |
|---|---|
| 报工台账、文件及 HTTP、逐件执行、候选及试排、齐套及实际保护、仓储读接口 | 相关组共 198 个测试节点：`related-tests.log` 为 197 passed / 1 failed；唯一失败是上述旧分件夹具，修正后该节点通过。 |
| 原 24 项失败所在三份测试及旧分件夹具复验 | `original-failures-final.log`：29 passed，其中原三份文件合计 28 项全部通过。与上一行重叠，不相加计数。 |
| 新增回归 | 14 个场景：新增双向录入、更正拒绝后续排、分流/汇合且已排/已报四种撤销、无关分件、合法/非法批量修正且两种行序、晚完工以及合并外协。包含在 198 个节点内。 |
| 子代理独立 HTTP 与业务命令复验 | 更正、双向新增、批量最终状态均拒绝矛盾输入；汇合撤销准确列出共同后序，业务命令返回 `constraint_conflict`，两道工序保持 complete；更正拒绝后下一次排产正常产出 4 个候选。见 `subagent-*-recheck.json`。 |
| 子代理恢复、覆盖导入和数量守恒相关测试 | `subagent-highrisk-tests.log`：50 passed。采用的执行快照、数量目标、旧正式范围及种子保护另做静态核对。 |
| 静态检查 | 修改文件 Ruff、产品文件局部 Pyright（0 errors / 0 warnings）通过；Python 3.8 语法、定向差异检查及本轮文件范围最终核对见 `repair-scope.json`。 |

上述为相关验证，不是全仓验证或 clean-worktree proof；工作区保留历史改动。没有新增浏览器操作验证，HTTP 均使用完整临时数据库，未打开生产数据库。

## 独立发现：外协完工后续排产 P1（后续已修复）

本节保留发现时的证据。用户随后明确授权修复，当前处理结果见 [外协执行事实适配修复](../2026-09-28-external-completion/external-completion-fix-note.md)。以下“未修改”描述对应本轮依赖修复的原始范围。

**外协完工报工会阻断后续其他批次排产。** 子代理使用完整库真实 compute → adopt → HTTP 报工复现，主代理原样复核：外协不填本厂设备/人员时，报工返回 200 committed、执行状态与资料完整性均为 complete；随后即使只选择新增自制 B2，worker 仍被原正式计划中外协 B1 的事实挡住，报 `execution_ledger_actual_resource_missing_or_multiple`。

- `core/services/execution/totals.py:24` 明确外协报工不要求本厂设备和人员。
- `core/services/scheduler/execution/execution_ledger_guard.py:85` 及 `core/services/scheduler/run/schedule_execution_guardrails.py:49` 却无条件要求这些资源。
- `core/services/workbench/run/input_execution.py:48` 校验原正式计划的全部执行事实，因此仅排其他批次也会失败。
- 本项属于额外的外协执行事实适配与种子语义问题，不是本轮依赖修复引入；未在本轮修改。修复不能编造本厂设备人员，也不能放宽自制工序保护。
- 复核摘要：`external-completion-open-finding.json`；复现脚本：`/tmp/aps-subagent-external-completion-20260928.py`。

## 文件范围

产品变更为 `production_report_dependencies.py`、`production_report_validation.py`、`production_report_prepare.py`、`production_report_void.py`、`workbench_report_validation_repo.py`、`batch_external_context_repo.py`；配套更新 4 个测试/夹具文件、测试注册表、使用手册、系统速查表和本记录。精确路径及哈希见 `repair-scope.json`。
