# Finding 04：required_regressions 的 skipped 白名单没有平台限制

- 优先级：P1 阻塞
- 结论：POSIX 平台上的 skipped 也会被当前 verifier 放过，和注释声明不一致。

## 根因

`REQUIRED_REGRESSION_ALLOWED_SKIPPED_NODEIDS` 的注释说：某个用例因为 Windows 文件名限制可以 skip，但 POSIX 上应该正常运行且必须 passed。实际 verifier 只判断 `outcome == "skipped"` 且 nodeid 在白名单里，没有判断平台。

大白话说：规则本来是“只有 Windows 可以跳过”，代码写成了“谁都可以跳过”。

## 调用链

- `scripts/run_quality_gate.py`
- `tools/verify_required_regressions_from_full_test_debt.py`
- 读取 `evidence/QualityGate/current_full_test_debt.json`
- 遍历 required nodeid 的 reports
- skipped 且在白名单中就直接通过

## 证据

- `tools/quality_gate_shared.py:256-260`：注释声明 POSIX 上必须正常运行并通过。
- `tools/verify_required_regressions_from_full_test_debt.py:215-227`：只检查 nodeid 白名单，不检查平台。
- 主线程只读探针：在本机 POSIX 环境下，白名单 nodeid 的 skipped 会满足当前通过条件。

## 影响

- 如果 Linux/macOS 上这个 required 用例因为错误原因 skipped，门禁也会放过。
- required regression 的“强制回归”含义被削弱。

## 建议

- 白名单改成带平台条件的数据结构，例如 `{nodeid: ["nt"]}`。
- verifier 读取 payload 或当前运行环境中的平台信息，POSIX skipped 必须失败。
- 补一个 POSIX skipped payload 必须失败的测试。
