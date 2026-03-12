# ADR-0010: 外协工序 ext_group_id 快照策略

- **状态**: 待决策（占位）
- **日期**: 2026-03-12
- **关联文档**: [排产优化_技术架构.md](../V1.2/排产优化_技术架构.md#4-5-5-外协工序-ext_group_id-快照策略待设计)

## 背景

`BatchOperations` 不存储 `ext_group_id`，排产时动态回查 `PartOperations` 模板。若创建批次后模板被修改，历史批次的外协分组关系可能漂移。

## 待决策点

- 是否在 `BatchOperations` 创建时固化 `ext_group_id`（快照策略）
- 若固化，模板修改时是否级联更新已有批次
- 若继续回查，是否在排产结果中记录映射快照

## 约束

- 涉及 Schema 变更（`BatchOperations` 新增字段），需同步 migration
- 必须兼容已有历史数据

## 预计决策时间

Phase 1 数据转换层实现时一并决策。
