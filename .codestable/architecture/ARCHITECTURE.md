---
doc_type: architecture
slug: ARCHITECTURE
scope: 项目架构总入口，覆盖 APS 整体结构、核心模块索引、关键架构决定和长期交付边界
summary: APS 在 Win7 x64、Python 3.8、离线交付约束下的系统地图入口
status: current
created: 2026-04-27
last_reviewed: 2026-05-27
tags: [aps, codestable, architecture, win7]
depends_on: []
implements: []
---

# 回转壳体单元智能排产系统（APS）架构总入口

> 状态：CodeStable 接入骨架，待后续按 `cs-arch` 补全
> 创建日期：2026-04-27

## 1. 项目简介

本项目是面向 Win7 x64 离线单机与共享数据场景的本地 APS 智能排产系统。系统目标是在目标机不安装 Python、不依赖外网的前提下，完成基础资料维护、Excel 导入导出、批次排产、结果查看、报表导出、备份恢复和现场交付。

当前开发与打包基线保持在 Python 3.8，并继续服从 Win7 兼容边界。正式交付时，目标机通过安装包和本地浏览器运行时访问 APS 页面。

## 2. 核心概念 / 术语表

- APS：围绕批次、工序、设备、人员、日历、齐套约束和排产策略组织的智能排产系统。
- 经典界面：`templates/` 与 `static/` 下的原有页面体系。
- 现代界面：`web_new_test/templates/` 下的覆盖模板体系，通过界面模式切换逐步接管页面。
- Win7 交付边界：目标机不要求安装 Python，页面和静态资源随应用本地交付，依赖升级必须考虑 Python 3.8 与 Win7。

## 3. 子系统 / 模块索引

- `core/`：核心领域、算法、基础设施、服务与插件运行框架。
- `data/`：数据访问层。
- `web/`：Flask 启动、路由、页面装配、界面模式与 viewmodel。
- `templates/`、`static/`：经典页面模板与本地静态资源。
- `web_new_test/templates/`：现代界面模板覆盖层。
- `templates_excel/`：交付 Excel 模板。
- `plugins/`：自研插件目录，当前插件默认关闭。
- `tests/`：自动化测试。
- `tools/`、`scripts/`：质量门禁、治理台账、辅助检查脚本。
- `开发文档/`、`audit/`、`evidence/`：开发说明、审计记录和验证证据。
- `.codestable/architecture/ui-gantt.md`：甘特图结果查看页面、缩放协议、只读边界、模拟预览身份传递和本地 Frappe 补丁治理现状。
- 车间执行事件基础：`OperationExecutionEvents`、执行事件仓储、执行反馈服务和执行状态读模型记录现场开工、暂停、继续、完工、报异常这些事实。

## 4. 关键架构决定

- CodeStable 从 2026-04-27 起作为新的 AI 协作工作流入口。
- `.limcode/` 暂不删除，保留为旧工作流归档、历史计划、历史审查和 APS 专项技能资料库。
- 新增功能、问题修复、重构、知识沉淀等新工作默认落到 `.codestable/` 下；只有需要引用历史资料或 APS 专项技能时，再回看 `.limcode/`。

## 5. 已知约束 / 硬边界

- 面向用户默认使用简体中文。
- Win7 x64、Python 3.8、离线交付是长期约束。
- 页面、导出、文件名、提示语和帮助文档不能直接展示 `scenario_id`、`plan_role`、`source_table`、`candidate_id` 这类程序内部字段；这些字段可以留在 URL、隐藏字段、请求参数和日志里用于对齐同一套计划，但用户可见位置必须转成中文大白话。
- 质量门禁入口仍以仓库现有 `scripts/run_quality_gate.py` 为准。
- 旧 `.limcode/plans/`、`.limcode/review/` 里有大量历史上下文，迁移初期不得批量删除或搬动。

## 6. 排产工序图分析现状

- `core/services/scheduler/graph/` 是排产工序图的内部分析模块，当前负责把已整理好的待排工序转成图节点、构建同批次前后工序边、校验 DAG / 环、计算拓扑顺序、关键路径和节点指标，并导出普通 dict 摘要。
- `graph_analysis_mode=off` 是默认关闭模式。关闭时排产主链不导入图模块，不要求安装 NetworkX，也不会在 `result_summary` 里写 `graph_analysis`。
- `graph_analysis_mode=report` 已作为旁路报告接入 `core/services/scheduler/run/schedule_orchestrator.py`。接入点在原排产算法已经算完、`validated_schedule_payload` 已经生成之后，图报告判断、错误投影和采样投影收在 `core/services/scheduler/run/schedule_graph_report.py`，只读取 `ScheduleRunInput.cfg`、`algo_ops_to_schedule`、`batches` 和 `resource_pool`。
- report 模式只把公开小摘要写进 `result_summary["algo"]["graph_analysis"]`，把采样诊断写进 `result_summary["diagnostics"]["graph_analysis"]`。OperationLogs 沿用现有 `detail["algo"]` 小摘要路径，因此只能看到 `algo.graph_analysis`，不能看到完整 nodes、edges、node_metrics、topological_order 或 raw 对象。
- `graph_analysis_mode=on` 当前已经接入 PR-5 ready 队列和 PR-6 图评分：可用 DAG 会在 optimizer 前生成 plain `graph_ready_context`，SGS 候选集合只从图 ready 工序里取；当 `graph_critical_weight` 或 `graph_impact_weight` 大于 0 时，图模块会计算 full `node_metrics`，在 service 层预先转成 `graph_priority_key_by_op_id`，算法层只拼普通 tuple，不反向依赖 scheduler service。`on + 有环 + graph_block_on_cycle=yes` 会在 version 分配前阻止排产；`on + 有环 + graph_block_on_cycle=no` 会继续旧 SGS 逻辑，但 public 摘要会写明图增强和图评分未启用。候选方案链路已经接入 3/5/7 档权重试跑、自动选择、候选落库和代表三方案页面切换；第一版只承诺正式采用方案、原算法代表方案和重点工序优先代表方案的查看与对比，不承诺全候选明细大屏、任意两方案自由对比、批次级或资源级差异清单。

## 7. 车间执行事件基础现状

- `OperationExecutionEvents` 是现场事实表，记录工序、批次、正式计划身份、动作、反馈时间、实际设备、实际人员、异常信息、幂等键、服务端指纹、写入前状态版本和反馈人。
- 执行事件只追加。`schedule_id` 和 `op_id` 仍保留外键用于审计对齐，但不使用级联删除，避免删除计划行时把现场事实一起带走。
- `data/repositories/operation_execution_event_repo.py` 负责执行事件的全部 SQL，并按 `op_id` 聚合 `OperationExecutionState`。service 不直接拼写事件表 SQL。
- `core/services/scheduler/operation_execution_feedback_service.py` 负责正式计划身份校验、幂等键优先判断、状态版本校验、合法状态流转和事件写入。
- 状态读模型按事件流聚合：`last_event_*` 表示最后一条现场事件，`latest_exception_*` 表示最近一次报异常；两组字段分开计算。
- 程序动作 `report_exception` 入库为 `event_type=exception`，页面和返回值显示“报异常”；现场状态 `exception` 显示“异常中”，两套中文映射分开维护。
