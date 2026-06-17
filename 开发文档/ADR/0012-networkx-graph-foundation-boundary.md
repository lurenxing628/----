# ADR-0012: NetworkX 工序图基础设施边界

- **状态**: 已决策
- **日期**: 2026-05-17
- **关联文档**: [NetworkX 排产工序图分析引入路线](../../.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-roadmap.md)

## 背景

排产系统最初计划先把 NetworkX 工序依赖图能力作为基础设施引入，再分阶段接入排产主链。到 2026-06-17，当前代码已经不再停留在“只保存配置、不执行图分析”的阶段：`graph_analysis_mode=on` 是默认模式，会在 NetworkX 可用时参与 ready 队列、图评分、候选方案和诊断摘要；`graph_analysis_mode=report` 是旁路报告模式；`graph_analysis_mode=off` 才是明确关闭图增强。

因此，本 ADR 的边界从“只做 Phase 0–4.5 基础设施硬化”更新为“图能力已经进入排产主链，但仍必须守住模块隔离、依赖交付和失败可见性”。

## 决策

1. NetworkX 是可选依赖，只能懒加载。
2. `graph_analysis_mode=off` 时系统不要求安装 NetworkX。
3. `nx.DiGraph` 只能留在 `core/services/scheduler/graph/` 内部，不得泄漏到 Controller、模板、数据库、Excel、summary 或算法公共接口。
4. `graph_analysis_mode=report` 执行旁路图分析，只写入公开摘要和诊断，不改变排产结果。
5. `graph_analysis_mode=on` 执行图增强排产：可用 DAG 会参与 ready 队列、图评分、候选方案和诊断摘要；发现有环且配置为阻止时，必须在分配版本前失败并给出可见错误。
6. 默认 `on` 模式下，Win7 离线交付包必须包含兼容 Python 3.8 的 `networkx==3.1`；缺依赖不能静默当成 `off`，必须在门禁、配置或启动链路里可见。
7. 图节点 ID 必须严格生成，不允许空 ID、二义性 ID 或 bytes/bytearray 静默解码。
8. 图值对象必须是纯 Python、可 JSON 序列化；`OperationGraphNode` 内部候选资源与 `raw` 快照不可变。
9. 图配置默认值由配置规格与 `ConfigService.ensure_defaults()` 管理；`schema.sql` 不直接插入 graph 默认配置行。
10. 旧库升级通过 v9 迁移补默认配置与 preset JSON，迁移必须幂等，坏 preset JSON 必须 fail fast。

## 后果

- UI 必须向用户明确说明：`on` 会启用图增强排产；`report` 只生成旁路诊断；`off` 才是关闭图增强。
- 代码边界仍然不变：NetworkX 对象不能跨出 `core/services/scheduler/graph/`，跨层数据只能用普通 dict、list、str、int、float、bool、None。
- Win7 x64 离线包证明必须覆盖 NetworkX 依赖：打包产物里要能离线启动，并能跑过图分析相关冒烟验证。
- 如果 NetworkX 缺失、图输入坏、图有环或图配置非法，不能静默降级成旧排产；要么按 `report/off` 语义明确绕开，要么按 `on` 语义给出可见失败或可见诊断。
