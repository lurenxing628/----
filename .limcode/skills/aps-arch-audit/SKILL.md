---
name: aps-arch-audit
description: 全项目架构合规审计：分层违反、文件超限、命名规范、禁止模式、圈复杂度门禁（Radon）、死代码检测（Vulture）、pytest 架构适应度函数。适用于用户提到"架构审计/架构检查/分层检查/合规检查/架构体检/复杂度检查/适应度函数"等场景。
---

# APS 架构合规审计

## Quick start

```bash
# 方式 1：独立脚本（生成 Markdown 报告）
python .limcode/skills/aps-arch-audit/scripts/arch_audit.py

# 方式 2：pytest 架构适应度函数（11 条规则，PASS/FAIL 粒度）
python -m pytest tests/test_architecture_fitness.py -v
```

- 脚本报告：`evidence/ArchAudit/arch_audit_report.md`

## 适用场景（触发词）

- 用户提到：**架构审计 / 架构检查 / 分层检查 / 合规检查 / 架构体检 / 分层合规 / 复杂度检查 / 适应度函数 / fitness**
- 建议：每周或每个 milestone 前运行一次

## 检查项（12 项自动化 + Agent 深审）

### 自动化检查（脚本执行）

1. **分层调用方向**：route 不直接操作 DB，service 不导入 Flask request
2. **文件大小**：核心目录 Python 文件不超过 500 行
3. **命名规范**：文件命名是否为 snake_case
4. **禁止模式**：`import *`、`except Exception: pass` / `except Exception as e: pass`、`except: pass`
5. **裸字符串枚举**：业务代码中是否使用裸字符串比较/集合校验（`== "pending"`、`status in (...)` 等）；其中 `in/not in` 默认作为 INFO（可能是输入校验）
6. **future annotations**：核心目录 Python 文件是否有 `from __future__ import annotations`
7. **公开方法类型注解**：Service/Repository 的公开方法是否有返回类型注解
8. **Service 循环依赖**：Service 包之间是否存在 A↔B 互相导入
9. **Route 越层导入**：Route 文件是否直接 import 了 Repository 类（应通过 Service 中转）
10. **死代码公开方法**：Service 层是否有公开方法无任何外部调用者
11. **圈复杂度门禁（Radon）**：单函数圈复杂度 **>15** 即标记（项目门禁；比 Radon 的 C 上限 20 更严格），报告含 A-F 分布图
12. **Vulture 死代码检测**：默认 `--min-confidence 80`（低噪音）；主要覆盖高置信度项（如 unused import / unreachable）。注意：不会覆盖 60% 置信度的 unused function/class/variable，除非降低阈值并配合白名单/ignore_decorators。

### pytest 架构适应度函数（11 条）

运行 `pytest tests/test_architecture_fitness.py -v`，包含：

1. `test_routes_do_not_execute_sql_directly` — 分层：Route 禁止直接 SQL
2. `test_services_do_not_import_flask_request` — 分层：Service 禁止 flask.request
3. `test_routes_do_not_import_repository` — 越层：Route 禁止直接导入 Repository
4. `test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes` — 分层：ViewModel 禁止越层/依赖 Flask
5. `test_no_circular_service_dependencies` — 循环依赖检测
6. `test_no_wildcard_imports` — 禁止 import *
7. `test_services_do_not_use_assert_for_runtime_guards` — Service 禁止用 `assert` 充当运行时校验
8. `test_no_silent_exception_swallow` — 禁止静默吞异常
9. `test_file_size_limit` — 文件大小限制
10. `test_cyclomatic_complexity_threshold` — 圈复杂度 ≤15（白名单机制）
11. `test_file_naming_snake_case` — 命名规范

历史遗留违反通过 `known_violations` / `known_imports` 白名单豁免，只捕获**新增违反**。

## 工作流（给 Agent 的执行指引）

### 1) 运行审计脚本 + 适应度函数

```bash
# 审计脚本（全量报告，含复杂度分布图）
python .limcode/skills/aps-arch-audit/scripts/arch_audit.py

# 适应度函数（PASS/FAIL 粒度，只捕获新增违反）
python -m pytest tests/test_architecture_fitness.py -v
```

### 2) 阅读报告

- 审计报告：`evidence/ArchAudit/arch_audit_report.md`
- pytest 输出：控制台直接查看

### 3) Agent 引用链深审（脚本之后的人工智能补充）

脚本只能发现模式级问题。对于以下场景，Agent 应主动做更深分析：

- **循环依赖被发现时**：读取涉及的两个 Service 包，分析是否可以通过提取公共模块解耦。
- **Route 越层导入被发现时**：评估是否真的需要直接调用 Repository（只读场景可能合理），还是应该包一层 Service。
- **死代码被发现时**：确认方法是否真的没用（可能通过反射/动态调用），还是确实应该删除。
- **文件超 500 行时**：建议具体的拆分方案，参考已有拆分先例（`scheduler.py` 的拆分模式）。
- **复杂度 D+ 函数被发现时**：建议拆分策略（提取子函数、策略模式、查表替代 if-else 等）。

如果问题数较多，Agent 应按严重程度排序：
1. **架构级**（必须修复）：分层违反、循环依赖
2. **质量级**（建议修复）：复杂度 E/F、死代码、缺类型注解
3. **信息级**（可延后）：复杂度 D、缺 future annotations、命名问题

### 4) 向用户输出结论

```markdown
## 架构合规审计结论

- 总结：PASS / FAIL
- 审计报告：evidence/ArchAudit/arch_audit_report.md
- 适应度函数：11/11 PASSED（或 N 条 FAILED）

### 复杂度健康度
- A-C（健康）：N 个函数
- D-F（需关注）：N 个函数

### 架构级问题（必须修复）
- [ ] 分层违反 / 循环依赖 / 越层导入

### 质量级问题（建议修复）
- [ ] 死代码 / 缺类型注解 / 裸字符串枚举 / 高复杂度函数

### 建议下一步
- 对架构级问题运行 `深度 review` 做引用链追踪
- ...
```

## 约束

- 只做检查，不做任何修改。

## 审阅报告归档（audit/，LLM）

当审计结果为 **FAIL**、或问题较多需要“决定哪些值得改/哪些不改”、或用户要求“审计留痕”时，Agent 需要基于本次审计产物生成一份“取舍型审阅报告”，并归档到仓库根目录一级目录 `audit/`，用于后续审计与排期。

- **目录**：`audit/YYYY-MM/`
- **文件命名**：`YYYYMMDD_HHMM_arch_audit_review.md`
- **建议证据清单**：
  - `evidence/ArchAudit/arch_audit_report.md`
  - `pytest tests/test_architecture_fitness.py -v` 的失败用例摘要（如有）

**强制规则（防止幻觉/跑偏）**：

- 只基于 evidence 做判断；每条结论必须能定位到证据文件与片段。
- 明确区分：**架构级（必须改）** / **质量级（建议改）** / **信息级（可延后）**，并给出成本（S/M/L）与风险。
- 不自动修改代码（除非用户明确要求）。

**审阅报告模板（建议）**：

```markdown
# 架构合规审计审阅报告（LLM）

- 时间：YYYY-MM-DD HH:MM
- 证据：
  - evidence/ArchAudit/arch_audit_report.md
  - （如有）pytest 失败摘要

## 事实摘要（来自证据）
- 总问题数：...
- 架构级问题：...
- 质量级问题：...

## 结论与取舍（LLM）

### 必须改（P0/P1：分层违反/循环依赖/越层导入等）
- [ ] ...

### 建议改（P2：复杂度/类型注解/死代码等）
- [ ] ...

### 不建议改 / 暂缓
- [x] ...（原因：历史债/误报/ROI 低/需更大重构）

## 成本与风险评估
- 预估总成本：S/M/L
- 回归风险：低/中/高
```
