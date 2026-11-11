---
name: writing-plans
description: 旧计划编写兼容入口；用于明确调用 writing-plans 或维护旧 .limcode plan。新功能计划随 cs-feat-design 管理。
---

# 旧计划编写

新功能计划跟随 [cs-feat-design](../cs-feat-design/SKILL.md)，较大需求使用 [cs-roadmap](../cs-roadmap/SKILL.md)。

维护旧 plan 时保留原路径和已确认决定。任务按可交付行为、依赖和可验证边界拆分，写明目标、准确文件、影响范围、验证方式和已知前提。未知事项如实标注，不编造路径、命令或解决方案。

覆盖接口、Schema、枚举、配置、模板和文案的实际联动；不为凑步骤重复列同一验证。新增合同与 bug 修复需有有效测试，方法见 [测试参考](../test-driven-development/testing-anti-patterns.md)。

计划编写不自动授权实施；若实施已获授权，选择适合当前依赖关系的执行方式继续，不重新询问同一决定。独立任务可按当前授权委派，耦合任务由当前代理完成。
