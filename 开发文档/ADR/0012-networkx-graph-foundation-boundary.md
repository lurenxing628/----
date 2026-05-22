# ADR-0012: NetworkX 工序图基础设施边界

- **状态**: 已决策
- **日期**: 2026-05-17
- **关联文档**: [NetworkX 排产工序图分析引入路线](../../.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-roadmap.md)

## 背景

排产系统计划引入 NetworkX 做工序依赖图分析，但当前阶段只允许完成 Phase 0–4.5 基础设施硬化，不能提前改变排产结果。

## 决策

1. NetworkX 是可选依赖，只能懒加载。
2. `graph_analysis_mode=off` 时系统不要求安装 NetworkX。
3. `nx.DiGraph` 只能留在 `core/services/scheduler/graph/` 内部，不得泄漏到 Controller、模板、数据库、Excel、summary 或算法公共接口。
4. 当前 `report/on` 只保存配置，不执行图分析，不改变排产结果。
5. 图节点 ID 必须严格生成，不允许空 ID、二义性 ID 或 bytes/bytearray 静默解码。
6. 图值对象必须是纯 Python、可 JSON 序列化；`OperationGraphNode` 内部候选资源与 `raw` 快照不可变。
7. 图配置默认值由配置规格与 `ConfigService.ensure_defaults()` 管理；`schema.sql` 不直接插入 graph 默认配置行。
8. 旧库升级通过 v9 迁移补默认配置与 preset JSON，迁移必须幂等，坏 preset JSON 必须 fail fast。

## 后果

- Phase 4.5 可以安全验证图基础设施，不引入调度行为变化。
- 后续 Phase 5+ 若要接入图构建、校验、指标或排产评分，必须另起设计/实施，不得借 Phase 4.5 顺手实现。
- UI 必须向用户明确说明：当前 `report/on` 不会执行图分析，也不会改变排产结果。
