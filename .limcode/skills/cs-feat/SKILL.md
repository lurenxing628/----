---
name: cs-feat
description: 用户明确要求增加功能时选择适当开发流程。需求明确且范围小直接走快速实现；复杂需求或明确要求完整流程时先设计。只问方案时不修改代码。
---

# 功能开发入口

## 启动

启动、授权与续作遵守根目录 `AGENTS.md`；读取或复用 `.codestable/attention.md`。路径、状态与收尾按需查 `.codestable/reference/shared-conventions.md`，缺辅助材料不阻断只读调查或已授权局部工作。

按需查看已有相关方案与进度，不凭用户一句“写完了”就认定已验证；也不为小任务强制创建全套材料。

## 选择路径

1. 只讨论或想法模糊：cs-brainstorm；只输出方案时不进入实现。
2. 需求明确、局部改动、不涉及数据迁移或跨模块约定：直接 cs-feat-ff，无需用户先说“快速模式”。
3. 复杂能力、重大风险或明确要求完整流程：cs-feat-design -> cs-feat-impl -> cs-feat-accept。方案明确且批准后连续完成已授权阶段；用户只批准设计时不自动实施。
4. 已有批准方案并要求实施：读相关 design 和 checklist，使用 cs-feat-impl；已有实现且要求验收则 cs-feat-accept。
5. 大需求分多个独立能力：cs-roadmap；从现有条目启动时核对其前置依赖与当前接口约定。
6. 用户明确要自己写 intent 草稿：cs-feat-design 的初始化入口，不替用户写实质决定。

## 材料与记录

- 已采用 CodeStable 时沿用 `.codestable/features/YYYY-MM-DD-{slug}/` 与现有文档命名；不重新命名或覆盖在途材料。
- 快速实现仅保留简短 `{slug}-ff-note.md`；未采用该体系的小任务在最终结果中记录即可。
- 完整流程的 design、checklist 和 acceptance 按相应技能生成，不为凑文档添加无关步骤。
- 进入本技能并不授权提交、发布、安装或迁移数据；按当前任务范围处理。
- 故障修复进入 cs-issue，行为不变的结构调整进入 cs-refactor，避免互相套流程。
