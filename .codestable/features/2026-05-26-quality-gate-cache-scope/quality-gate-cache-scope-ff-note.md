---
doc_type: feature-ff-note
feature: quality-gate-cache-scope
date: 2026-05-26
requirement:
tags: [quality-gate, cache, pre-push, long-gate]
---

## 做了什么
优化质量门禁本地缓存：pre-push 现在按本次 push 的真实 from/to 范围算影响面，long gate 新增只读影响解释入口，避免无关指纹变化把所有长门禁都拖去重跑。

追加实现了 `full_test_debt` 的更细缓存边界：能证明“只改了某个测试函数里很普通的本地赋值”时，只重跑对应 selected nodeid；证明不了就退回原来的文件级增量。还加了严格失败缓存：只缓存真实完整命令失败，不把 nodeid 增量失败或 ledger-only 失败冒充成完整失败缓存。

## 改了哪些
- `tools/git_hook_checks.py` / `scripts/run_daily_quality_gate.py` - 接入 pre-commit pre-push 环境变量和显式 diff 范围，删除分支跳过，本地 dirty 时仍不读写成功缓存。
- `tools/git_hook_cache.py` - daily cache key 绑定 changed paths、impact pytest 目标和 ruff 目标，不再用 commit sha 阻断 message-only amend 复用。
- `tools/long_gate_manifest.py` / `scripts/run_quality_gate.py` - 拆掉 long entry 默认全量工具 scope，保留全局 runner/tooling 保护，并增加 `--long-gate-impact-explain` JSON 诊断。
- `tools/long_gate_test_body_diff.py` - 新增函数体级 diff 选择器；只允许非常保守的本地名字赋值和简单 assert 进入 nodeid 级复用，函数调用、属性/下标读写、比较表达式、控制流、import、global/nonlocal、删除、增强赋值都会退回文件级。
- `tools/long_gate_full_test_debt.py` - 接入函数体级选择、旧源码 git head 校验、selected nodeid 合并、collector payload 强校验和未知 merge policy 拒绝。
- `tools/long_gate_cache.py` / `scripts/run_quality_gate.py` - 增加 full_test_debt 失败缓存；dirty worktree、force rerun、增量失败、ledger-only 失败都不会读写这个失败缓存。
- `tools/long_gate_summary.py` - 长 nodeid 列表在 summary/diagnostic 里改成数量、hash 和样例，避免诊断输出爆长。

## 怎么验证的
- `pytest -q tests/test_long_gate_cache.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_summary_output.py -p no:cacheprovider`
- `pytest -q tests/test_run_quality_gate.py tests/test_long_gate_manifest.py tests/test_long_gate_cli_controls.py -p no:cacheprovider`
- `pytest -q tests/test_long_gate_required_regression_cache.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_cache.py -p no:cacheprovider`
- `python -m ruff check scripts/run_quality_gate.py tools/long_gate_cache.py tools/long_gate_full_test_debt.py tools/long_gate_test_body_diff.py tools/long_gate_summary.py tools/quality_gate_shared.py tests/test_long_gate_cache.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py`
- `pyright -p pyrightconfig.tools.json`
- `python -m pyright -p pyrightconfig.tools.json` 未跑通：当前 shell 的 Python 没有安装 `pyright` 模块；系统 `pyright` 命令已通过。

## 顺手发现
- pre-commit 的 pre-push hook 会先消费 stdin，再通过环境变量给 hook 传 from/to；所以实现不能只依赖 stdin。
- selected-nodeid 要非常保守。函数体里只要出现调用、属性/下标读写、比较、控制流等无法证明不影响后续测试的行为，就不能只跑一个 nodeid，必须退回文件级增量。
- 失败缓存不能混用语义。只有真实完整 `full_test_debt` 命令失败可以写失败缓存，nodeid 增量失败和 ledger-only 失败只作为本次快速反馈失败，不能给后续 run 复用。
- pre-push 多 ref 里只要有一个 ref 算不清范围，cache key 和实际执行命令都必须显式进入 unknown-range 全量保护，不能让命令裸跑回当前分支 diff。
