# ADR-0011: efficiency 因子在 int64 整数时间轴中的表达

- **状态**: 待决策（占位）
- **日期**: 2026-03-12
- **关联文档**: [排产优化_数据模型与实例构建.md](../V1.2/排产优化_数据模型与实例构建.md#efficiency-在整数时间轴中的表达待设计)

## 背景

v1.x 日历系统支持 `efficiency` 因子（如 0.8 表示 1 小时需 1.25 小时完成）。v2.0 将时间轴改为 `int64` 分钟并用 Numba 加速，需要明确 efficiency 如何映射到整数时间轴。

## 候选方案

- **方案 A**：`InstanceBuilder` 预乘效率系数 `proc_time_scaled = ceil(proc_time / eff)`
- **方案 B**：构建"逻辑分钟 → 实际分钟"映射表
- **方案 C**：v2.0 初期统一 `efficiency=1.0`，后续增强

## 约束

- 必须兼容 Numba nopython 模式
- v2.0 与 v1.x 在 efficiency != 1.0 场景下排产结果不可比时，需明确回退口径

## 预计决策时间

Phase 0（技术验证阶段）完成前必须决策。
