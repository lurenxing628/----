---
doc_type: issue-fix
slug: quality-gate-output-normalization
status: fixed
created: 2026-09-12
summary: 完整门禁收集输出中的超长数字测试名称触发收据规范化正则的平方级回溯。
tags: [quality-gate, performance, receipt]
---

# 收据输出规范化性能修复

## 根因与现场

隔离门禁 `python -B scripts/run_quality_gate.py --allow-dirty-worktree` 第 7/19 步已经成功收集 17073 个测试，却持续占用单核。2026-09-12 的 1 秒进程采样中，850/850 样本位于 Python `re.sub` → `sre_search`。原始收集日志约 2.53 MB；`test_process_route_preview.py::test_structured_row_name_is_preserved_without_text_reparsing[...]` 的参数名含 262143 位连续数字。

`tools/quality_gate_shared.py` 的耗时规范化使用 `[0-9]+(?:\.[0-9]+)? seconds`。超长数字后没有 ` seconds` 时，搜索从数字串每个后缀重新尝试，工作量随长度平方增长。相同 Python 3.8 环境，1000/2000/4000 位输入耗时 0.00984/0.03888/0.15534 秒，外推现场单次约 667 秒。门禁在收据生成前已记录子命令耗时，因此步骤日志不计这段额外等待。

此正则和超长参数测试均为既有代码；不是本次工作台领域功能导致。根任务已明确授权仅修规范化性能、对应测试和本记录，不变更门禁标准、测试参数、产品或其他调度工作。

## 已选择的最小修复

在 ASCII 数字串起点增加 `(?<![0-9])`，只阻止从同一连续数字串内部重复搜索。某一数字串的完整起点若不能匹配原后缀，内部任何起点也不能匹配；小数点仍允许作为下一候选数字串的边界，例如 `1.2.3 seconds` 保持原结果 `1.<seconds> seconds`。其余规范化规则与 exact 策略不变。

验证将覆盖明确示例、旧新结果的确定性小样本比较、完整收据哈希，以及独立子进程内的 262143 位数字测试名称超时回归。不使用运行时降级或改变历史收据匹配语义。

## 验证

- `.venv/bin/python -m pytest -q --tb=short tests/gate_meta/test_quality_gate_output_normalization.py tests/gate_meta/test_long_gate_collect_cache.py`：**25 passed / 1.19s**。包含 13 个明确例子、9331 个确定性小串旧新等价比较，以及 262143 位数字 nodeid 的完整收据哈希子进程测试（10 秒超时）。输入只在子进程中生成，新增测试本身不再制造超长 pytest 参数名。
- `.venv/bin/python -m pytest -q --tb=short tests/gate_meta/test_run_quality_gate.py -k 'receipt or output or collect'`：**21 passed, 79 deselected / 8.14s**。
- 对现场 **2,534,963 字节**收集日志直接执行新规范化：**0.094675 秒**；262143 位数字完整保留。规范化输出 SHA-256 为 `7aafc0245b36ebc97daf4479d20b21659a81f96bd4118acfbce55aa84ad8a8f8`。
- `.venv/bin/python -m ruff check tools/quality_gate_shared.py tests/gate_meta/test_quality_gate_output_normalization.py` 与范围内 `git diff --check` 通过。

改动仅为一处正则和解释性注释、新增独立测试及本记录。`tools/quality_gate_shared.py` 原有 UI 注册路径改动予以保留。完整隔离门禁由根任务重新同步和执行；以上属于 dirty 工作区局部验证，不是 clean-worktree proof。本分支未停止或重启门禁进程，未暂存或提交。
