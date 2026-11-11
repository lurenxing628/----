# CodeStable 体系总览

本页用于介绍体系、选择流程和维护技能家族。明确任务直接读取相关技能，不先加载整套总览。授权、平台、完成与验证遵守项目 AGENTS.md；项目技能优先使用项目现行版本。

## 按任务选择

| 任务 | 入口 | 结果 |
|---|---|---|
| 了解体系或选流程 | cs | 解释并选相关入口 |
| 明确初始化/迁移体系 | cs-onboard | 保留定制的项目骨架 |
| 新能力 | cs-feat | 局部实现或完整 design/implement/acceptance |
| 故障 | cs-issue | 只读分析或已授权修复 |
| 审查隐患 | cs-audit | 有证据的只读发现 |
| 行为不变的重构 | cs-refactor | 局部或完整 scan/design/apply |
| 研究现有代码 | cs-explore | 当前事实；仅要求保存时落档 |
| 需求尚未明确 | cs-brainstorm | 必要澄清与范围收敛 |
| 跨模块规划 | cs-roadmap | 依赖与验收清楚的子任务 |
| 当前架构 | cs-arch | 当前结构和决定，不把目标态写成现状 |
| 能力愿景与现状 | cs-req | draft/current/outdated 需求 |
| 经验、方法、长期决定 | cs-learn / cs-trick / cs-decide | 不同 doc_type 的可追溯记录 |
| 短项目注意事项 | cs-note | attention 中必要短约束 |
| 用户/开发指南、公开 API | cs-guide / cs-libdoc | 面向相应读者的文档 |

## 范围与记录

- 只读调查直接回答，发现问题不自动修复或落档。
- 已授权的小功能、修复、重构可走局部路径；在已有 CodeStable 项目留下相应轻量记录，不先补齐整套设计或初始化缺失目录。
- 跨模块、高风险或明确完整流程时保留必要设计、依赖、契约与验收；常规实现选择不重复审批。
- 已批准任务连续完成，遇到实质新取舍才问。阶段名称是导航，不是要求用户重新说一次“继续”。

## 资料职责

- requirements：用户能力愿景与当前状态。
- architecture：当前实现结构及长期决定。
- roadmap：目标态、依赖和计划，不冒充当前架构。
- feature / issue / refactor：一次工作范围、实现及证据。
- audits：审查发现；发现、修复状态与实际验证分开。
- compound：learning（经验）、trick（方法）、decision（决定）、explore（调查），保留取代关系。
- 项目开发文档：开发、接口、操作与验证参考；按变化同步受影响内容，不与上述产物整份互相复制。

路径、元数据和状态协议按需读 `.codestable/reference/shared-conventions.md`；检索与校验读 `.codestable/reference/tools.md`；续作和维护读 `.codestable/reference/maintainer-notes.md`。已有项目共享文件是现行约定，onboard 模板只是新项目起点。
