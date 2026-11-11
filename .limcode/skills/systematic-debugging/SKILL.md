---
name: systematic-debugging
description: 旧排查兼容入口；用于明确调用 systematic-debugging 或回查旧排查任务。新问题调查使用 cs-issue 或 cs-explore。
---

# 根因排查兼容入口

新 bug 使用 [cs-issue](../cs-issue/SKILL.md)，只读定向研究使用 [cs-explore](../cs-explore/SKILL.md)。要求“先查清楚”仅表示只读，不自动触发多轮流程。

从报错、复现条件和近期相关变化建立可证伪假设，核对实际输入输出与正常路径。修复须指向有证据的根因，避免叠加猜测性补丁。调查不自动进入修改阶段；实施已获授权时连续完成修复和必要验证。

按具体问题读取：

- 倒查坏值或跨层调用：[root-cause-tracing.md](root-cause-tracing.md)。
- 不同启动方式、进程或配置来源：[运行证据参考](../deep-investigate/runtime-evidence.md)。
- 需要更早暴露错误：[defense-in-depth.md](defense-in-depth.md)。
- 异步时序问题：[condition-based-waiting.md](condition-based-waiting.md)。
- 检查回归测试有效性：[测试参考](../test-driven-development/testing-anti-patterns.md)。

输出已确认根因、证据和未验证边界；若证据推翻原假设，更新结论，不为满足流程强行找 bug。
