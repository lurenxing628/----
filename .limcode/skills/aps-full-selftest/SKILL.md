---
name: aps-full-selftest
description: 运行 APS 仓库的全量自测（smoke、web smoke、FullE2E、regression、复杂 Excel 用例），并生成汇总报告。适用于用户提到全量自测、冒烟测试、E2E、回归测试、复杂 Excel 用例，或要求“通读项目并跑全量自测”且不需要打包的场景。
---

# APS 全量自测（不打包）

## Quick start

- 运行：`python .limcode/skills/aps-full-selftest/scripts/run_full_selftest.py`
- 可选：`python .limcode/skills/aps-full-selftest/scripts/run_full_selftest.py --fail-fast --step-timeout 900`（每步超时秒数；<=0 表示不设超时）
- 汇总报告：`evidence/FullSelfTest/full_selftest_report.md`

## 适用场景（触发词）

- 用户提到：**全量自测/冒烟测试/smoke/E2E/回归测试/regression/复杂 Excel 用例**
- 用户要求：**通读项目** + **跑一遍全量自测**（且不打包）

## 默认覆盖范围

- smoke：`tests/smoke_phase0_phase1.py` ~ `tests/smoke_phase10_sgs_auto_assign.py`
- web smoke：`tests/smoke_web_phase0_5.py`、`tests/smoke_web_phase0_6.py`
- FullE2E：`tests/smoke_e2e_excel_to_schedule.py`
- regression：自动枚举 `tests/regression_*.py`
- 显式 guard：`tests/test_sp05_path_topology_contract.py`、`tests/test_schedule_input_builder_strict_hours_and_ext_days.py`
- complex excel cases：`tests/run_complex_excel_cases_e2e.py --out evidence/ComplexExcelCases --repeat 1`

## 约束

- **不要执行打包/出包**：不要运行 PyInstaller、`dist/`、`validate_dist_exe.py` 等。

## 工作流（给 Agent 的执行指引）

### 1) 轻量通读/扫描项目（尽量覆盖“全局”但不浪费 token）

- 结构扫描：快速浏览仓库顶层与关键目录（`core/`、`data/`、`web/`、`tests/`、`templates/`、`static/`、`schema.sql`、`requirements.txt`）。
- 变更扫描（若是 git 仓库）：读取 `git status` 与 `git diff`，把改动按模块归类，并指出高风险点（数据库/排产/Excel 导入/路由/模板）。
- 只在必要时再深入阅读：优先读“本次改动文件”与“改动影响的入口/服务”。

### 2) 运行全量自测（不打包）

- 推荐：直接运行 runner：
  - `python .limcode/skills/aps-full-selftest/scripts/run_full_selftest.py`
- 若运行环境缺依赖：按仓库约定安装 `requirements.txt`（仅提示，不擅自改动项目依赖）。

### 3) 输出结论（统一格式）

输出至少包含：

- 总结：PASS/FAIL
- 耗时：总耗时 + 每个脚本耗时
- 定位：失败脚本名、退出码、以及对应 `evidence/...` 报告路径（如存在）
- 下一步：给出最短修复路径（优先从第一个失败开始）

## 输出模板（建议）

```markdown
## 全量自测结论

- 总结：PASS/FAIL
- 汇总报告：evidence/FullSelfTest/full_selftest_report.md

## 失败项（若有）

- [ ] <script>（exit=<code>）：<关键错误摘要>
  - 证据：<evidence path>

## 备注

- 未执行打包/出包（按约束）
```

## 额外说明

- 详细脚本清单、报告路径与常见问题见：[reference.md](reference.md)

## 审阅报告归档（audit/，LLM）

当全量自测结果为 **FAIL**，或用户要求“审计留痕/评估要不要改、先改哪些更值”时，Agent 需要基于自测汇总报告与关键失败日志生成一份“取舍型审阅报告”，并归档到仓库根目录一级目录 `audit/`，用于后续审计与修复排期。

- **目录**：`audit/YYYY-MM/`
- **文件命名**：`YYYYMMDD_HHMM_full_selftest_review.md`
- **建议证据清单**：
  - `evidence/FullSelfTest/full_selftest_report.md`
  - `evidence/FullSelfTest/logs/*.log.txt`（仅引用失败项/首个失败项）
  - 相关 `evidence/...` 报告（Phase 报告、FullE2E 报告、ComplexExcelCases 报告等）

**强制规则（防止幻觉/跑偏）**：

- 只基于证据做判断；每条结论必须能定位到报告/日志的路径与片段。
- 重点回答：哪些失败值得立刻改（阻断链路/高风险）、哪些可暂缓（低 ROI/环境问题/偶发），并给出成本（S/M/L）。
- 不自动修改代码（除非用户明确要求）。

**审阅报告模板（建议）**：

```markdown
# 全量自测审阅报告（LLM）

- 时间：YYYY-MM-DD HH:MM
- 证据：
  - evidence/FullSelfTest/full_selftest_report.md
  - evidence/FullSelfTest/logs/xx.log.txt

## 事实摘要（来自证据）
- 总体结论：PASS/FAIL
- 首个失败：...
- 影响范围：...

## 结论与取舍（LLM）

### 必须改（P0/P1：阻断交付/高回归风险）
- [ ] ...

### 建议改（P2：稳定性/易用性）
- [ ] ...

### 不建议改 / 暂缓
- [x] ...（原因：环境/偶发/ROI 低）

## 成本与风险评估
- 预估总成本：S/M/L
- 回归风险：低/中/高
```
