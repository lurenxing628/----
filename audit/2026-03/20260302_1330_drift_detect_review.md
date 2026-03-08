# 漂移检测（综合体检）审阅报告（LLM）

- 时间：2026-03-02 13:30
- 证据：
  - evidence/DriftDetect/drift_report.md
  - evidence/ArchAudit/arch_audit_report.md
  - evidence/Conformance/conformance_report.md
  - evidence/DeepReview/reference_trace.md
  - pytest tests/test_architecture_fitness.py（11/11 PASSED）

## 事实摘要（来自证据）

- **总体结论：需要关注**（架构分层完美无违反，问题集中在圈复杂度）
- **架构合规**：FAIL（45 个检出项；0 架构级违反，问题全部为质量级/信息级）
  - 分层违反：0 | 文件超限：0 | 禁止模式：0 | 循环依赖：0 | 越层导入：0
  - 命名问题：1 | 裸字符串枚举：5 | 潜在死代码：3 | 圈复杂度超标（>15）：36
  - Vulture 死代码：0
- **适应度函数**：11/11 PASSED（无新增架构违反）
- **一致性对标**：13/13 通过（0 BLOCKER，0 MAJOR）
- **Ruff Lint**：All checks passed（核心目录 0 问题）
- **文档新鲜度**：所有文档均在代码变更 1 天内更新过
- **引用链追踪**（HEAD~1）：0 跨层边界风险

### 复杂度分布

| 等级 | 范围 | 函数数 | 占比 |
|------|------|--------|------|
| A 简单 | 1-5 | 940 | 71.6% |
| B 低 | 6-10 | 261 | 19.9% |
| C 中 | 11-20 | 93 | 7.1% |
| D 高 | 21-30 | 16 | 1.2% |
| E 很高 | 31-40 | 1 | 0.08% |
| F 极高 | 41+ | 2 | 0.15% |

- A-C（健康）：1294 函数（98.6%）
- D-F（需关注）：19 函数（1.4%）

### F 级函数（最高风险）

| 文件 | 函数 | 复杂度 |
|------|------|--------|
| core/services/scheduler/schedule_optimizer.py:187 | optimize_schedule | 50 |
| core/services/scheduler/schedule_service.py:198 | _run_schedule_impl | 51 |

### E 级函数

| 文件 | 函数 | 复杂度 |
|------|------|--------|
| core/infrastructure/migrations/v4.py:34 | _sanitize_field | 39 |

### 裸字符串枚举（5 处）

| 文件 | 行号 | 内容 |
|------|------|------|
| web/routes/scheduler_excel_calendar.py | 126, 138, 245, 257 | `== "workday"` |
| core/services/common/enum_normalizers.py | 202 | `== "normal"` |

### 潜在死代码（3 处）

| 文件 | 行号 | 方法 |
|------|------|------|
| core/services/process/unit_excel_converter.py | 26 | convert() |
| core/services/scheduler/gantt_range.py | 38 | start_str() |
| core/services/scheduler/gantt_range.py | 42 | end_exclusive_str() |

### 命名问题（1 处）

| 文件 | 说明 |
|------|------|
| core/services/scheduler/_sched_utils.py | 前缀下划线不符合 snake_case 规范 |

## 结论与取舍（LLM）

### 必须改（P0/P1：架构级）

- 无。分层合规、循环依赖、越层导入均为 0 违反，架构层面健康。

### 建议改（P2）

- [ ] **F 级函数拆分**：`optimize_schedule`(50) 和 `_run_schedule_impl`(51) 是排产核心函数，复杂度已达极高。建议提取子策略函数、将分支逻辑抽为独立方法。已在 pytest 白名单内不阻塞 CI，但长期应逐步降低。成本：M，风险：中（核心排产逻辑变更需充分回归测试）。
- [ ] **裸字符串枚举清理**：5 处 `"workday"`/`"normal"` 比较应改为 enums.py 枚举引用。成本：S，风险：低。
- [ ] **潜在死代码确认与清理**：3 个公开方法无外部调用者，需确认是否仍有运行时动态调用或未来预留。若确认无用则删除。成本：S，风险：低。

### 不建议改 / 暂缓

- [x] **命名问题 `_sched_utils.py`**：前缀下划线表示内部模块的惯例，语义明确且已在 pytest 白名单。改名涉及所有 import 联动修改，ROI 低。暂缓。
- [x] **21 处枚举集合比较（INFO 级）**：多为 Route 层输入校验（`in ['yes', 'no']`），属于合理的输入合法性检查而非业务逻辑枚举比较。暂不处理。
- [x] **D 级函数（16 处）**：均在 15-30 区间，部分为 `from_row()`/migration 等难以进一步简化的场景。暂不强制拆分。
- [x] **E 级函数 `_sanitize_field`(39)**：位于 migration v4（历史迁移脚本），不会再被新代码触发，无需改造。

## 成本与风险评估

- **预估总成本**：S（仅 P2 项；P0/P1 为 0）
- **回归风险**：低（P2 的裸字符串和死代码清理影响面小；F 级函数拆分需中等回归测试）
- **整体健康度**：良好。架构分层、一致性、代码规范均处于优秀状态，主要技术债集中在排产核心函数的圈复杂度。
