---
description: APS 架构合规审计：分层、越层导入、循环依赖、复杂度、死代码与架构适应度函数
---
当用户提到“架构审计 / 架构检查 / 分层检查 / 合规检查 / 架构体检 / 复杂度检查 / 适应度函数”时，使用本 workflow。

- 本地 skill 说明：`.windsurf/skills/aps-arch-audit/SKILL.md`

1. 运行两类自动化检查。
   - 审计脚本：`python .windsurf/skills/aps-arch-audit/scripts/arch_audit.py`
   - 架构适应度函数：`python -m pytest tests/test_architecture_fitness.py -v`

2. 读取关键证据。
   - 审计报告：`evidence/ArchAudit/arch_audit_report.md`
   - pytest 输出：直接读取终端结果

3. 解读时按三层优先级排序。
   - 架构级：分层违反、循环依赖、Route 越层导入。
   - 质量级：高复杂度、死代码、缺类型注解、裸字符串枚举。
   - 信息级：future annotations、命名问题、较轻复杂度告警。

4. 对脚本无法解释的重点问题，补做人工深审。
   - 发现循环依赖：分析能否通过抽离公共模块解耦。
   - 发现 Route 直接导入 Repository：判断是否应该补一层 Service。
   - 发现死代码：确认是否真无调用方，还是动态调用/反射场景。
   - 发现文件超 500 行或复杂度 D+：给出具体拆分建议。

5. 向用户输出固定结论。
   - 总结：PASS/FAIL。
   - 审计报告路径。
   - 适应度函数通过情况。
   - 复杂度健康度：A-C 与 D-F 数量。
   - 架构级问题清单。
   - 质量级问题清单。
   - 建议下一步：是否转 `aps-deep-review` 深挖影响面。

6. 若结果为 FAIL 或用户要求留痕，再补审阅报告。
   - 只基于 evidence 和 pytest 结果做判断。
   - 明确区分必须改、建议改、可暂缓，并给出成本与风险。

7. 约束。
   - 本 workflow 只做检查与建议，不直接修改代码。
