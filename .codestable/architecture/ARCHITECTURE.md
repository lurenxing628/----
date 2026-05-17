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

## 4. 关键架构决定

- CodeStable 从 2026-04-27 起作为新的 AI 协作工作流入口。
- `.limcode/` 暂不删除，保留为旧工作流归档、历史计划、历史审查和 APS 专项技能资料库。
- 新增功能、问题修复、重构、知识沉淀等新工作默认落到 `.codestable/` 下；只有需要引用历史资料或 APS 专项技能时，再回看 `.limcode/`。

## 5. 已知约束 / 硬边界

- 面向用户默认使用简体中文。
- Win7 x64、Python 3.8、离线交付是长期约束。
- 质量门禁入口仍以仓库现有 `scripts/run_quality_gate.py` 为准。
- 旧 `.limcode/plans/`、`.limcode/review/` 里有大量历史上下文，迁移初期不得批量删除或搬动。

## 6. 排产工序图分析现状

- `core/services/scheduler/graph/` 是排产工序图的内部分析模块，当前负责把已整理好的待排工序转成图节点、构建同批次前后工序边、校验 DAG / 环、计算拓扑顺序、关键路径和节点指标，并导出普通 dict 摘要。
- `graph_analysis_mode=off` 是默认关闭模式。关闭时排产主链不导入图模块，不要求安装 NetworkX，也不会在 `result_summary` 里写 `graph_analysis`。
- `graph_analysis_mode=report` 已作为旁路报告接入 `core/services/scheduler/run/schedule_orchestrator.py`。接入点在原排产算法已经算完、`validated_schedule_payload` 已经生成之后，图报告判断、错误投影和采样投影收在 `core/services/scheduler/run/schedule_graph_report.py`，只读取 `ScheduleRunInput.cfg`、`algo_ops_to_schedule`、`batches` 和 `resource_pool`。
- report 模式只把公开小摘要写进 `result_summary["algo"]["graph_analysis"]`，把采样诊断写进 `result_summary["diagnostics"]["graph_analysis"]`。OperationLogs 沿用现有 `detail["algo"]` 小摘要路径，因此只能看到 `algo.graph_analysis`，不能看到完整 nodes、edges、node_metrics、topological_order 或 raw 对象。
- `graph_analysis_mode=on` 在当前阶段仍按 report-only 处理，并在摘要里写 `effective_mode="report_only"`。它还没有接 ready 队列、SGS 候选集合、评分、冻结窗口或落库行；真正改变排产行为要等后续图 ready 队列和评分阶段。
