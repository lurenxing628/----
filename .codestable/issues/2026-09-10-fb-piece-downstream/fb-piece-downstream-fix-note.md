---
doc_type: issue-fix-note
status: completed
owner: FB
date: 2026-09-10
---

# FB 现场记录 / 实际甘特单件信息贯通

## 范围与根因

- 用户已授权局部直接实施。保留起步已有的大量 dirty；不 stage/commit，不修改 registry、build-order、ES 数量证据、Plan/Run/Trial/Point 或公共 controls。
- FieldWorkspaceService.cohort 原 DTO 丢失正式计划的 piece_id / quantity / batch_quantity / quantity_basis / quantity_reason。
- Field 列表/详情、实际甘特行标题/详情/悬浮和搜索隐藏 piece_id；旧界面把当前执行目标当成所选计划应做量。
- 实际甘特后端已原样保留计划 task，不重复查询或推导数量。执行台账对真实分件仍输出目标 1，没有发现把它算成批次 3 的证据。

## 已实施 Handoff

- Field 仅透传上游原数量证据，现场列表/详情显示原单件编号、计划应做、计划批次量。
- Field 和实际甘特搜索包括原 piece_id。实际甘特行标题、鼠标/键盘标题、详情、CSV 包括单件身份。
- 旧计划/缺回执数量保持 null，UI 显示未知与原缺失原因；不以当前主数据或执行目标补造原计划量。
- 原 CSV 执行目标明确标为“执行目标数量”，另附“计划应做数量 / 计划批次数量 / 计划数量依据 / 计划数量缺失原因”。
- Field 和 actual contract 拒绝缺字段/非法数量证据；Point arrangement 校验保留。
- 未改执行 arithmetic、报工写入、自动完成、Canvas renderMark 单向依赖或零时长 contract。

## 最终验证

- `.venv/bin/python` 为 Python 3.8.10。
- 最终针对性回归 **69 passed**：`test_piece_downstream_api.py`、`test_field_workspace_api.py`、`test_actual_gantt_api.py`、`test_point_downstream_api.py`、`test_actual_gantt_ui.py::test_actual_gantt_model`、`test_field_files_api.py`、`test_field_files_codec.py`。
- 最后一处日期比较类型窄化后，重新运行单件下游和 invalid_scope：**11 passed, 14 deselected**。
- 新增 API 链路覆盖真实 worker/adopt/formal -> Field list/detail -> actual，含当前批量改 99、旧 plan/缺回执未知、零数量报工不完成其他单件、完整任务集合、报工字段和原始引用/表保留。
- `test_piece_downstream_browser.py` 最终 **4 passed**：真实 factory、managed worker、main.jsx 私有编译，Chromium **109.0.5414.46**，1920/1392 x light/dark。每组 10 张截图，逐件 Field -> 实际甘特 -> CSV，旧计划未知，错误数量 DTO 拒绝，0 页面/console/外部请求/采集错误。
- 浏览器脚本首次暴露的 3 类问题均在脚本内修正：不能比较 Field 可写上下文与甘特只读上下文；必须等待搜索结果/重读后的报工行渲染；异步排产受理的既有 `202 / ok=true` 不是错误。仅精确允许 `/scheduling/runs` 的 202，其他异常响应仍失败。
- `test_point_downstream_browser.py` **2 passed**（每个用例均覆盖四组合，16 张截图），无报工点与真实报工两种路径，保留 24px point 命中、键盘选择、零时长合同、Canvas renderMark。非透明 Canvas 像素分别 **126 / 1760**，数据与范围未补造。
- 所有浏览器服务均使用专属临时目录、SQLite guard、随机空闲端口，退出回收；未访问或重启 53144。

## FE 类型问题收口

- 对应 `.codestable/issues/2026-09-10-fe-static-integration/diagnostic-index.md` 保留给 FB 的 **25 条**：actual_gantt_scope 6、field_report_files 2、codec 15、xml 2。
- 六个可空查询字段改为 `Optional[str]`；batch_ids 明确为 `Tuple[str, ...]`；日期比较显式确认 end 非空。
- XLSX 汇总与录入元数据使用真实 `str/int/float/None` 混合单元格列表；没有转字符串或丢失 null/0。
- 拒绝函数使用 `NoReturn`，让真实异常路径参与窄化；新工作簿无活动表明确抛 RuntimeError，不造替代表。
- 使用现行 `.venv` Pyright **1.1.406**、不改全局配置，以下限定范围结果 **0 errors, 0 warnings, 0 informations**：

```text
.venv/bin/python -m pyright -p pyrightconfig.gate.json
  core/services/workbench/actual_gantt.py
  core/services/workbench/actual_gantt_scope.py
  core/services/workbench/actual_gantt_export.py
  core/services/workbench/field_workspace.py
  core/services/workbench/field_workspace_scope.py
  core/services/workbench/field_report_files.py
  core/services/workbench/field_report_files_codec.py
  core/services/workbench/field_report_files_xml.py
```

- 命令为一行运行，以上按参数换行展示。`actual_gantt.py` 仅检查，未编辑。未加入 ignore/cast，也未更新 Pyright。

## 合并清单

- `core/services/workbench/field_workspace.py:70`：5 字段原样透传。
- `core/services/workbench/field_workspace_scope.py:102`、`actual_gantt_scope.py:118`：piece 搜索；后者 `:18/:32/:45` 同时收口类型。
- `core/services/workbench/actual_gantt_export.py:10/:47`：明确执行目标，追加原单件/计划数量证据列。
- `core/services/workbench/field_report_files.py:142`：混合单元格列表；`field_report_files_codec.py:26/:159/:186`、`field_report_files_xml.py:16`：异常窄化与活动表约束。
- `frontend/workbench/app/FieldContract.js:9`、`FieldTable.jsx:6`、`FieldDetail.jsx:53`：合同、列表、详情。
- `frontend/workbench/app/ActualGanttContract.js:14`、`ActualGanttModel.js:9/:144`、`ActualGanttRows.jsx:54`：合同、标识/详情、标签。
- 新增 `tests/workbench/test_piece_downstream_api.py`、`test_piece_downstream_browser.py`、`piece_downstream_contract.cjs`、`piece_downstream_browser.cjs`、`piece_downstream_browser_support.cjs`。
- 本修复记录。以上 **13 个产品文件 + 5 个测试/辅助文件 + 1 份记录**；均保持未提交，未 stage。

## 浏览器与原始数据证据

以下均为独立临时 fixture，服务已退出，文件保留：

| 组合 | 证据根目录 |
| --- | --- |
| 1920 light | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-h7jax7ef` |
| 1920 dark | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-hu787ix4` |
| 1392 light | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-k2pydw1c` |
| 1392 dark | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-9vl2jsw1` |

- 每目录 `piece_downstream_browser.json` 保留 formal tasks、原 operation/task/plan refs、HTTP 响应、新报工 refs、合同拒绝结果；移除 write_context 后落盘。
- `run-seed.json` 保留原始 operation_id/piece_id 对应；`business-before.json` / `business-after.json` 保留数据库逐表原值。
- `fb-retention.json` 核实 Batches、BatchOperations、OperationExecutionEvents、ScheduleCandidateRows、ScheduleAdjustmentScenarioRow 全表不变；Schedule、WorkbenchTaskRefs、WorkbenchPlanSourceRefs、WorkbenchEntityRefs、原报工与修订、原回执逐行保留。正式采用仅追加计划数据，每组只在私库明确新增 1 条数量 0 报工。
- `server-final.json` 核实 stopped、assets_unchanged、isolation_violations=[]，所有 SQLite 路径均在对应根目录。
- `piece_main_build.json` 保留 chrome109 编译来源及散列；`screenshots/` 和 `downloads/` 分别保留实际截图与逐件 CSV。
- Point 浏览器证据：`/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/pytest-of-lurenxing/pytest-1291/test_real_main_point_downstrea0/ek-point-downstream-browser` 与同级 `test_real_main_point_downstrea1/ek-point-downstream-browser`。

## 剩余边界与停止点

- 只提供 dirty-worktree 局部验证，不宣称 clean-worktree proof。
- 不跑全局 build 或全仓门禁，不改测试 registry。新增测试由主线程统一注册。
- 浏览器覆盖的是本轮短 ASCII fixture piece_id；中文原始编号另由真实 API/模型测试覆盖，未声称超长编号全视口浏览器验收。
- 既有十列 XLSX 的分件同名导入仍明确拒绝、不猜关联（`field_report_files.py:63`）；XLSX 汇总仍为执行目标口径（`:147`），本轮只完成其类型收口，未将该格式扩成原计划数量证据格式。作为后续待办保留，不继续扩展。
- 原 CSV 的“目标数量”改名“执行目标数量”，按旧中文表头读取 CSV 的外部脚本需要对应调整；其原数据位置与数值保留，原计划证据列附于尾部。
- 四组合 UI / point 浏览器通过后，仅追加 Python 类型注解、显式非空判断/工作簿异常边界；后续 69 项既有回归与最后 11 项定点复跑覆盖这些变化。
- 用户要求本阶段完成后停止：本写集功能与类型闭环完成，没有继续派发任务或全站检查。全仓 FE 其他诊断未在本轮处理。
