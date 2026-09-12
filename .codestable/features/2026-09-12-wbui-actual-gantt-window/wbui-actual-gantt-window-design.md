---
doc_type: feature-design
feature: 2026-09-12-wbui-actual-gantt-window
status: approved
summary: 实际甘特默认显示窗口、缩放锚点与最小命中区域
tags:
- workbench
- ui
- actual-gantt
roadmap: workbench-ui-refinement
roadmap_item: wbui-actual-gantt-window
created: '2026-09-12'
---

## 0. 术语约定

axis_span 是后端计划、实报、剩余安排、as_of 并集；显示窗口仅决定 zoom 与 scrollLeft。点是零时长，命中区不代表持续时间。

## 1. 决策与约束

遵循用户已授权实施及 implementation-20260912.md。保留 DTO、as_of、筛选与导出，不改 Python 领域逻辑。恢复的 actual_view 优先于默认窗口；默认优先计划区间，无计划区间才用实报范围。适应全部始终回到完整 axis_span（加原点标记留白）。

## 2. 名词与编排

ActualGanttWindow 为纯显示计算：根据数据跨度得默认缩放与中心；缩放以明确选中报工/工序中点或计划数据中心为锚。实际条形真实宽度保留在内层着色面，外层透明命中区域至少4px；canvas同一命中几何，点工序继续24px菱形。

## 3. 验收契约

- 相隔数月的 as_of 不让当天计划压成不可读默认范围，适应全部仍显示完整并集。
- 已恢复视窗保持原位置；选中报工优先缩放锚，其他为计划中心。
- 1秒时段绘制长度不扩大，但DOM和canvas可在4px命中区选择；零时长、未填结束仍为点。
- 跨DST按工厂本地坐标不变；所有模型计算不修改源DTO。
- 定向模型、编译、Chrome109真实API读取及最终主线程构建验收分别记录。

## 4. 与项目级文档的关系

显示状态内部变化，API和领域架构不变；主线程统一回写 UI 文档与路线图。
