---
doc_type: feature-acceptance
feature: 2026-05-13-full-test-debt-nodeid-cache
roadmap: quality-gate-long-cache
roadmap_item: full-test-debt-nodeid-cache
status: accepted
summary: full-test-debt nodeid 级增量复用验收记录
tags: [quality-gate, cache, full-test-debt, nodeid]
---

# full-test-debt-nodeid-cache 验收记录

## 1. 做成了什么

- 新增 `tools/long_gate_full_test_debt.py`，把 full-test-debt 专项逻辑集中到一个地方：node cache 读写、坏证据拒绝、台账-only、普通测试文件 nodeid 增量、整体回退原因都在这里处理。
- 新增 `evidence/QualityGate/full_test_debt_node_cache.json` 作为运行产物，并加入 `.gitignore` 和本地 hook 拦截；它不会被提交，只用于下一次判断 full-test-debt 能不能安全增量。
- `collect_nodeids.json` 的解析修正为保留整行 nodeid，参数化测试名字里有空格或 `collected` 字样时不会被截断。
- `collect_full_test_debt.py` 新增 `--no-current-payload` 和 `--current-payload-path`，nodeid 子集收集不会覆盖正式 `current_full_test_debt.json`。
- `check_full_test_debt.py` 拆出“从已有 current payload 重新做台账校验并生成 summary”的入口，nodeid 增量和台账-only 都继续复用原判定规则。
- `scripts/run_quality_gate.py` 的顺序保持保守：先看整项 success cache；整项不能复用时，再尝试 ledger-only 或 nodeid 增量；证据不可信就整项执行。
- node cache 绑定 `evidence/QualityGate/long_gate/logs/` 下的持久 success cache 日志，不依赖下一轮会被清理的普通运行日志。

## 2. 安全边界

- 只有普通 `tests/**/*.py` 变化、且不是任何 `conftest.py`、且 `collect_nodeids.json.nodeids_by_file` 能找到 nodeid 时，才会走 nodeid 增量。
- 源码、`conftest.py`、pytest 配置、依赖、collector/checker/runner/schema/cache/fingerprint/manifest/summary/registry 工具、模板、静态资源、Excel 模板、安装脚本、`.limcode` 旧资产、CodeStable 文档变化，都会整体回退。
- 如果变化的测试文件被其它测试文件静态 import、`importlib.import_module()` 动态 import、`__import__()` 动态 import，或遇到无法安全解析的动态导入，都会整体回退。
- 只改 `开发文档/技术债务治理台账.md` 时，不跑 pytest，但必须读取可信旧 current payload，再用当前台账重新校验并重写 summary。
- node cache 缺失、损坏、schema/hash 不匹配、日志缺失、日志 hash 不匹配、旧 success cache 未声明 node cache、非本次改动测试文件 hash 不匹配、current payload 的 nodeid 与 collect nodeid 不一致，都会整体回退。
- 增量 pytest 失败、collector 输出不合法、exitstatus 不一致、合并后台账校验失败，都不会复用旧成功。

## 3. 没有启用什么

- 没有新增新的 long gate entry。
- 当前 enabled long gate entry 仍只有 `pytest_collect_all` 和 `full_test_debt`。
- startup、required、ruff、pyright、architecture、debt ledger、quickref 仍保持 planned。
- NEXT-6 `startup-runtime-regression-cache` 仍保持 planned，`feature: null`。

## 4. 已验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py tests/test_run_quality_gate.py tests/test_long_gate_collect_cache.py tests/test_check_full_test_debt.py tests/test_full_test_debt_registry_contract.py`
  - 结果：318 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
  - 结果：通过；只打印决策，没有写 proof。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright ...`
  - 结果：0 errors。
- `git diff --check`
  - 结果：通过。

## 5. 最终 clean proof

- 提交前状态：待最终提交后执行。
- 最终 HEAD：待最终提交后回填。
- clean-worktree gate：待最终提交后回填。
