---
name: aps-drift-detect
description: 漂移检测与一致性体检：架构审计（含复杂度/Vulture）、适应度函数、conformance report、ruff 全量检查、引用链追踪，生成综合健康报告。适用于用户提到"漂移检测/体检/一致性检查/健康检查/定期检查/milestone检查/全面检查"等场景。
---

# APS 漂移检测（综合体检）

## Quick start

```bash
# Step 1: 综合检测脚本
python .limcode/skills/aps-drift-detect/scripts/drift_detect.py

# 可选：调整各子步骤 timeout（秒）
# python .limcode/skills/aps-drift-detect/scripts/drift_detect.py --timeout 180 --timeout-ruff 300

# Step 2: 架构适应度函数（新增）
python -m pytest tests/test_architecture_fitness.py -v

# Step 3: 引用链追踪（对近期变更）
python .limcode/skills/aps-deep-review/scripts/reference_tracer.py --commit HEAD~1
```

- 综合报告：`evidence/DriftDetect/drift_report.md`

## 适用场景（触发词）

- 用户提到：**漂移检测 / 体检 / 一致性检查 / 健康检查 / 定期检查 / milestone 检查 / 全面检查 / 全面体检**
- 建议：每周或每个大功能完成后运行一次

## 检查覆盖范围（7 大维度）

> 说明：`drift_detect.py` 脚本本身覆盖其中的 **1/3/4/5/7**；维度 **2/6** 需要按 Quick start 手工补跑。

1. **架构合规审计** — 调用 `aps-arch-audit`（`drift_detect.py` 自动运行）
2. **架构适应度函数** — `pytest tests/test_architecture_fitness.py`（手工运行；9 条 PASS/FAIL）
3. **一致性对标报告** — `tests/generate_conformance_report.py`（`drift_detect.py` 自动运行）
4. **Ruff 全量 Lint** — 核心目录全量检查（`drift_detect.py` 自动运行）
5. **文档新鲜度** — 开发文档 vs 代码的最后修改时间差（`drift_detect.py` 自动运行）
6. **引用链追踪** — `reference_tracer.py`（手工运行；近期变更的跨层边界风险）
7. **复杂度健康度** — 架构审计报告中的 A-F 分布图趋势（由维度 1 产出）

## 工作流（给 Agent 的执行指引）

### 1) 运行综合检测脚本

```bash
python .limcode/skills/aps-drift-detect/scripts/drift_detect.py
```

### 2) 运行架构适应度函数

```bash
python -m pytest tests/test_architecture_fitness.py -v
```

如有 FAILED 用例，说明有**新增的架构违反**（非历史遗留），优先处理。

### 3) 运行引用链追踪（对近期变更）

```bash
python .limcode/skills/aps-deep-review/scripts/reference_tracer.py --commit HEAD~1
```

引用链报告输出到 `evidence/DeepReview/reference_trace.md`。重点关注跨层边界风险和无调用者的公开方法。

### 4) 阅读综合报告

- 架构审计报告：`evidence/ArchAudit/arch_audit_report.md`
- 漂移检测报告：`evidence/DriftDetect/drift_report.md`
- 引用链追踪报告：`evidence/DeepReview/reference_trace.md`

### 5) 向用户输出结论

```markdown
## 漂移检测（综合体检）结论

- 总结：健康 / 需要关注 / 需要立即修复
- 综合报告：evidence/DriftDetect/drift_report.md

### 架构适应度函数
- 结论：9/9 PASSED / N 条 FAILED

### 架构合规
- 结论：PASS/FAIL（N 个违反项）
- 复杂度健康度：A-C 占 N%，D-F 占 N%

### 一致性对标
- 结论：PASS/FAIL（N 个 BLOCKER，N 个 MAJOR）

### Ruff Lint
- 核心目录问题数：N

### 文档新鲜度
- ⚠ 以下文档可能需要更新：...

### 建议下一步
1. ...
2. ...
```

## 约束

- 只做检查，不做任何修改。
- 一致性对标报告会启动 Flask app（在临时目录），注意不要污染正式数据库。

## 审阅报告归档（audit/，LLM）

当综合体检结果为 **需要关注/需要修复**，或用户要求“审计留痕/后续改造决策”时，Agent 需要基于综合报告与关联 evidence 生成一份“取舍型审阅报告”，并归档到仓库根目录一级目录 `audit/`，用于后续审计与排期。

- **目录**：`audit/YYYY-MM/`
- **文件命名**：`YYYYMMDD_HHMM_drift_detect_review.md`
- **建议证据清单**：
  - `evidence/DriftDetect/drift_report.md`
  - `evidence/ArchAudit/arch_audit_report.md`
  - `evidence/Conformance/conformance_report.md`
  - （如有）`evidence/DeepReview/reference_trace.md`

**强制规则（防止幻觉/跑偏）**：

- 只基于 evidence 做判断；每条结论必须能定位到证据文件与片段。
- 报告必须回答：哪些要改（P0/P1）、哪些不改（为什么）、成本/风险/收益大概是多少。
- 不自动修改代码（除非用户明确要求）。

**审阅报告模板（建议）**：

```markdown
# 漂移检测（综合体检）审阅报告（LLM）

- 时间：YYYY-MM-DD HH:MM
- 证据：
  - evidence/DriftDetect/drift_report.md
  - evidence/ArchAudit/arch_audit_report.md
  - evidence/Conformance/conformance_report.md

## 事实摘要（来自证据）
- 总体结论：...
- 架构合规：...
- 对标差异：...
- Ruff：...

## 结论与取舍（LLM）

### 必须改（P0/P1）
- [ ] ...

### 建议改（P2）
- [ ] ...

### 不建议改 / 暂缓
- [x] ...

## 成本与风险评估
- 预估总成本：S/M/L
- 回归风险：低/中/高
```
