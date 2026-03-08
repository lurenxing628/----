---
description: APS 深度代码审查：引用链追踪、影响面评估、数据流分析、边界条件与回归风险检查
---
当用户提到“深度 review / 深度审查 / 引用链检查 / 影响面分析 / 帮我仔细看看 / 这个改动安全吗 / 合并前检查 / 排查一下”时，使用本 workflow。

- 本地 skill 说明：`.windsurf/skills/aps-deep-review/SKILL.md`

1. 先运行引用链追踪脚本，拿到自动化线索。
   - 默认：`python .windsurf/skills/aps-deep-review/scripts/reference_tracer.py`
   - 以某个提交为基线：`python .windsurf/skills/aps-deep-review/scripts/reference_tracer.py --commit HEAD~1`
   - 只分析指定文件：`python .windsurf/skills/aps-deep-review/scripts/reference_tracer.py --file core/services/scheduler/batch_service.py`

2. 阅读 `evidence/DeepReview/reference_trace.md`，先画出影响图谱。
   - 每个变更函数的调用者数量。
   - 是否存在跨层边界风险。
   - 是否有无外部调用者的公开方法。
   - 必要时再补查模板引用与测试引用。

3. 按五阶段做深审。
   - Phase 1：变更影响图谱。
   - Phase 2：逐条引用链深审，检查参数、返回值、异常传播、事务边界。
   - Phase 3：数据流追踪，沿着“用户输入 → Route → Service → Repository → DB”核对类型、字段、SQL 与 schema。
   - Phase 4：边界条件与回归风险，重点看空值、类型错配、并发、测试覆盖。
   - Phase 5：汇总结论与行动项。

4. 输出结论时至少包含。
   - 变更概要：改动文件数、变更函数数、影响调用者数。
   - 引用链完整性：参数、返回值、异常、事务是否一致。
   - 跨层边界一致性：是否引入越层依赖或职责漂移。
   - 边界条件：空值、弱类型、并发、重复提交、特殊输入。
   - 回归风险：现有测试覆盖是否足够，需要补哪些测试。
   - 行动项：必须改、建议改、可暂缓。

5. 使用本 workflow 时的判断标准。
   - 只把脚本输出当作线索，不把文本匹配当成完整调用图。
   - 对高风险结论必须回到源码核对。
   - 涉及 Service 公开方法签名、Schema、跨模块改动时，优先使用本 workflow 而不是浅检查。
