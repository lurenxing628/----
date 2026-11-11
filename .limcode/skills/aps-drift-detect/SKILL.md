---
name: aps-drift-detect
description: 对 APS 做明确要求的综合漂移体检，组合架构、一致性对标、静态检查和文档新鲜度证据。局部一致性问题、服务存活检查或泛泛“检查一下”不触发全项目体检。
---

# APS 综合漂移体检

## 范围与入口

遵循根目录 `AGENTS.md`。只读分析先看已有相关证据；用户要求运行综合体检时，才执行综合脚本。产品代码、正式数据库和基线不因体检结果被自动修改。

使用项目 `.venv` Python；以下 `python` 为已激活环境后的简写：

```bash
python .limcode/skills/aps-drift-detect/scripts/drift_detect.py
```

可用 `--timeout 180 --timeout-ruff 300` 调整子步骤超时。脚本包含架构审计、一致性对标、核心目录 Ruff、文档时间差及复杂度汇总。它会调用 `aps-arch-audit` 的脚本，已执行时不要再重复运行同一架构扫描。

综合脚本不包含以下两项，按本次体检要求补齐：

- 架构适应度：`python -m pytest tests/gate_meta/test_architecture_fitness.py -v`。测试清单与数量读取当前测试文件及实际执行结果。
- 变更调用链：按 [.codestable/reference/symbol-locator.md](../../../.codestable/reference/symbol-locator.md) 使用 `python3 -m tools.symbol_locator` 核对本次指定变更范围内涉及定义的 `whereis`、`callers`、`callees`；比较范围严格按用户指定文件或提交基线确定，不默认把 `HEAD~1` 当作任务范围。

若用户明确要求完整综合体检，应完成适用的覆盖项，或说明未完成原因。局部问题不套用完整组合。静态调用关系只提供定位证据，不能代替源码合同核对。

## 证据与限制

- 综合报告：`evidence/DriftDetect/drift_report.md`。
- 子报告：`evidence/ArchAudit/arch_audit_report.md`、`evidence/Conformance/conformance_report.md`；调用链核对直接引用 `tools.symbol_locator` 查询结果与源码位置，不再产出独立文件。
- 一致性对标会启动 Flask app，必须保持临时目录/测试数据库隔离；不能改用正式数据库来绕过失败。
- 文档修改时间差只能说明可能过期，是否不一致要核对具体内容；适应度失败要区分新增违反、基线或环境问题。
- 统一门禁与最终证明口径见 [开发文档/README.md](../../../开发文档/README.md)。综合体检报告不代替 full gate 或 clean-worktree proof。

## 汇报与完成

说明完成的维度、失败/跳过项、证据、确认的问题和建议；不因发现问题自动修复、刷新基线或重跑整套体检。

默认对话汇报。用户要求保存报告或已授权流程要求落档时，写到 `.codestable/audits/` 或该流程的证据位置。失败和警告本身不触发额外审计文档，原始脚本产物继续保留在 `evidence/`。
