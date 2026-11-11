---
name: cs
description: 用户想了解 CodeStable 或不确定该用哪个流程时提供简短导航。明确的任务直接进入相应技能，不要求用户重复触发，不初始化项目。
---

# CodeStable 导航

启动与任务范围遵守根目录 `AGENTS.md`，项目注意事项见 `.codestable/attention.md`。本技能只用于介绍和分流，不自动生成产物。

## 根据当前诉求选择

| 诉求 | 入口 |
|---|---|
| 新功能 | `cs-feat` |
| 故障分析或修复 | `cs-issue` |
| 行为不变的结构调整 | `cs-refactor` |
| 只读审计 / 定向代码研究 | `cs-audit` / `cs-explore` |
| 模糊想法 / 大需求拆解 | `cs-brainstorm` / `cs-roadmap` |
| 需求 / 架构文档 | `cs-req` / `cs-arch` |
| 已定决定 / 经验 / 用法 / 常驻提示 | `cs-decide` / `cs-learn` / `cs-trick` / `cs-note` |
| 用户或开发指南 / API 参考 | `cs-guide` / `cs-libdoc` |
| APS 基线体检 / 概念语义检查 | `cs-checkup` / `cs-semantic-radar` |
| 明确要求接入或维护 CodeStable 骨架 | `cs-onboard` |

具体任务已清楚时，说明采用哪条路径并继续完成已授权范围，不以“现在切换吗”结束。用户只想了解时，简述体系后回答问题即可。信息缺失会影响目标或风险时才澄清；可以从上下文判断的内部分类不交给用户反复选择。

## 按需补充材料

- 只有介绍体系或选择完整流程时才读 `.codestable/reference/system-overview.md`。
- 续作只查当前相关记录及实际代码；不为分流遍历全部历史产物。
- 缺 `.codestable/` 不自动初始化，也不阻断调查或局部修改；用户选择完整流程时只补实际需要的材料。
- 技能的阶段名称用于定位操作方法，不能覆盖根规则的只读、局部实施和完整流程授权边界。
