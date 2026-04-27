---
doc_type: issue-fix
issue: 2026-04-27-review-contract-hardening
status: completed
clean_proof_status: pending_after_current_diff_commit
path: fast-track
fix_date: 2026-04-27
tags: [quality-gate, full-test-debt, codestable, python38]
---

# 当前分支 review 机器合同返修记录

## 1. 问题描述

当前分支 deep review 发现 9 个问题，核心都是机器合同不够硬：新增 active xfail 可以靠抬高数字绕过，未登记 xfail 可以混进 proof，baseline 可以缺少可追溯提交号，CodeStable 搜索工具会吞坏 YAML，Python 3.8 下两个 CodeStable 工具也不能保证启动。

## 2. 根因

这些问题不是业务算法本身坏了，而是边界检查只看了“数量像不像对”，没有把“哪些 nodeid 被允许”“报告里有没有未登记 xfail”“baseline 来自哪个提交”“坏 YAML 能不能继续搜索”这些机器事实一起锁住。

## 3. 修复方案

把检查改成显式失败合同：台账 active xfail 只允许当前 5 条历史 P0 nodeid；proof 中任何 xfail 痕迹都必须匹配台账 active 登记；导入 baseline 必须有 40 位 Git SHA 且候选不能为空；CodeStable 工具在 Python 3.8 下可启动，并在坏 YAML 时直接失败；regression 文件读取失败改成 pytest 收集错误。

## 4. 改动文件清单

- `tools/quality_gate_shared.py`
- `tools/quality_gate_ledger.py`
- `tools/check_full_test_debt.py`
- `tools/test_debt_registry.py`
- `tools/collect_full_test_debt.py`
- `codestable/tools/search-yaml.py`
- `codestable/tools/validate-yaml.py`
- `tests/conftest.py`
- `tests/test_check_full_test_debt.py`
- `tests/test_full_test_debt_registry_contract.py`
- `tests/test_sync_debt_ledger.py`
- `tests/test_regression_main_isolation_contract.py`
- `tests/test_codestable_tools_contract.py`
- `audit/2026-04/20260427_full_pytest_p0_debt_baseline.md`
- `.limcode/plans/2026-04-27_full_pytest_p0_test_debt_governance.plan.md`
- `codestable/architecture/ARCHITECTURE.md`
- `codestable/compound/2026-04-27-decision-codestable-default-workflow.md`

## 5. 验证结果

- `.venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py tests/test_check_full_test_debt.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py tests/test_regression_main_isolation_contract.py --tb=short -p no:cacheprovider`：159 passed。
- `.venv/bin/python -m pytest -q tests/test_codestable_tools_contract.py --tb=short -p no:cacheprovider`：15 passed。
- `python3.8 codestable/tools/search-yaml.py --help`：通过。
- `python3.8 codestable/tools/validate-yaml.py --help`：通过。
- `.venv/bin/python tools/check_full_test_debt.py`：status=passed，active_xfail_count=5，fixed_count=0，max_registered_xfail=5，collected_count=700，collection_error_count=0。
- `.venv/bin/python scripts/sync_debt_ledger.py check`：通过。
- `git diff --check`：通过。
- 临时 clean worktree 将当前 dirty diff 做成临时提交后运行 `.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`：质量门禁通过。

## 6. 收口说明

`audit/2026-04/20260427_full_pytest_p0_debt_baseline.md` 已在干净提交 `197663a9a4e5573f0e85a1a090fa2158baa33856` 上重新生成。机器块记录 `git_status_short_before=[]`、`worktree_clean_before=true`、`collected_count=690`、`candidate_test_debt=0`，不再使用旧提交的 `631` 条采集结果冒充当前证明。

本记录和新 baseline 提交后，需要在干净工作区重跑 `scripts/run_quality_gate.py --require-clean-worktree` 作为最终 clean proof。

## 7. 二次 deep review 返修

后续 deep review 又确认了 4 个必须补硬的点：full pytest 债务 proof 不能只看 call 阶段，CodeStable YAML fallback 必须能读常见多行列表，目录校验不能把 markdown frontmatter 要求套到 checklist.yaml 上，旧 baseline 不能继续冒充当前证明。

本次补充的合同是：未登记 `xfail(run=False)` 必须失败，已登记的 setup 阶段 xfail 必须通过，fixed 债务只要还在 setup 阶段 xfail 就不能被当成修好；采集报告新增 `xfail_marker_run`；CodeStable 工具在无 PyYAML 时也能搜索 block list，遇到坏 block list 和非独立 `---` 分隔符会直接失败。

## 8. 三次 deep review 返修

后续 Review 继续发现 CodeStable YAML 工具对“无 PyYAML”路径的承诺过宽：内置解析器既会误杀合法 checklist，也会放过未闭合引号的坏 frontmatter。README 入口也没有把 `codestable/` 作为当前默认事实源露出来。

本次补充的合同是：纯 `.yaml/.yml` 文件必须依赖 PyYAML 校验，缺失时直接失败并提示安装开发依赖；内置 frontmatter 解析器只保留极简用途，并拒绝未闭合单双引号；根 README 与开发文档 README 补上 CodeStable 入口；`codestable/reference/tools.md` 的 guide/libdoc 示例路径改为 `docs/dev`、`docs/user`、`docs/api`。

## 9. 四次 deep review 返修

后续 Review 又确认了 5 个收口问题：strict XPASS 候选仍可能被采集器写成可导入债务种子；门禁 source proof 没覆盖实际执行的规则脚本；dirty worktree 下的 `passed_but_unbound` 仍返回成功信号；`search-yaml.py --help` 示例路径仍指向旧目录；本记录里的 CodeStable 工具测试数量过期。

本次补充的合同是：带 xfail 信号的候选不能成为 importable baseline；台账导入层也拒绝这类 baseline；门禁 source proof 覆盖实际命令计划中的 `.py` 目标、required tests、startup regressions、pyright gate 配置与 quickref 检查；`--allow-dirty-worktree` 只产出未绑定排查证明，返回码不再是 0，终端文字也不再写“质量门禁通过”；`search-yaml.py --help` 示例改为 `docs/api`。

本次 clean proof 已在临时 worktree 完成：先把当前未提交 diff 做成临时提交，再挂载同一份 `.venv`，最后以干净工作区运行 `scripts/run_quality_gate.py --require-clean-worktree`，结果为“质量门禁通过”。

## 10. 五次 deep review 返修

后续 Review 又确认了 5 个收口问题：导入阶段只挡 candidate 里的 xfail 信号，按预期失败的未登记 xfail 会以 skipped 形态绕过导入边界；坏 baseline report 缺机器字段时会冒 `KeyError`；`search-yaml.py --filter status~=` 会把空 contains 当成宽泛匹配；`audit/2026-04/20260427_full_pytest_p0_debt_baseline.md` 的机器块绑定旧提交，不能代表当前 dirty 工作区；`requirements-dev.txt` 新增 PyYAML 越过了原计划“不新增外部依赖 / 不改 requirements-dev.txt”的边界。

本次补充的合同是：只要 baseline reports 中出现任何 xfail 信号，导入阶段就拒绝，不再只看 candidate 失败集合；baseline reports 缺 `strict_xpass`、`xfail_marker_present`、`xfail_marker_reason`、`wasxfail_reason` 等机器字段时必须抛 `QualityGateError`；`search-yaml.py` 拒绝空 key / 空 value 的 filter，普通 Markdown 没有 frontmatter 时会被跳过，不再作为结构化命中；`audit` baseline 顶部明确写清绑定旧提交 `197663a9a4e5573f0e85a1a090fa2158baa33856`。

PyYAML 仍只作为 `requirements-dev.txt` 的开发期依赖，用于 CodeStable YAML 工具校验 Markdown frontmatter 和纯 YAML 文件；它不进入 APS 运行时依赖，也不进入 Win7 离线目标机交付。因为这越过了原 P0 plan 的“不新增外部依赖 / 不改 requirements-dev.txt”边界，本记录把它作为已审查边界例外单独写明。

本次补充后已复跑：`tests/test_run_quality_gate.py tests/test_run_full_selftest_report_metadata.py tests/test_check_full_test_debt.py tests/test_full_test_debt_registry_contract.py tests/test_sync_debt_ledger.py tests/test_regression_main_isolation_contract.py` 为 `159 passed`；`tests/test_codestable_tools_contract.py` 为 `15 passed`；覆盖本次计划五个测试文件的合并命令为 `169 passed`；`tools/check_full_test_debt.py` 为 `status=passed`、`collected_count=700`、`unexpected_failure_count=0`；`scripts/sync_debt_ledger.py check` 和 `git diff --check` 均通过。

当前主工作区仍有未提交 diff，`clean_proof_status` 保持 `pending_after_current_diff_commit`。临时 worktree clean gate 可以作为排查证据；最终分支 clean proof 仍需在本 diff 提交后，用干净工作区重新运行 `scripts/run_quality_gate.py --require-clean-worktree`。
