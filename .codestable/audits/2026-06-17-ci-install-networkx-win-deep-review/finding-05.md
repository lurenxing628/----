# Finding 05：required_regressions 缓存没有钉住本轮 full-test-debt payload

- 优先级：P1 阻塞
- 结论：长门禁缓存命中时，可能复用旧的 required_regressions 成功证明，而没有重新核验本轮 full-test-debt 输出。

## 根因

`verify_required_regressions_from_full_test_debt.py` 实际读取 `evidence/QualityGate/current_full_test_debt.json`。但是 `long_gate_manifest.py` 里 required_regressions 的指纹输入来自 required 目标、公共 scope 和 group scope，没有把 `current_full_test_debt.json` 的内容作为输入。

大白话说：这个步骤真正要看的“本轮测试结果文件”没进入缓存指纹。缓存说“以前核过”，不等于“这次这个结果也核过”。

## 调用链

- `scripts/run_quality_gate.py --long-gate-cache`
- full_test_debt 生成 `evidence/QualityGate/current_full_test_debt.json`
- required_regressions 调用 `tools/verify_required_regressions_from_full_test_debt.py`
- verifier 默认读取 `CURRENT_FULL_TEST_DEBT_REL`
- long-gate 按 required_regressions 指纹决定是否跳过

## 证据

- `tools/verify_required_regressions_from_full_test_debt.py:258`：默认 payload 是 `CURRENT_FULL_TEST_DEBT_REL`。
- `tools/verify_required_regressions_from_full_test_debt.py:265-268`：实际加载该 payload 后校验。
- `tools/long_gate_manifest.py:428-446`：required_regressions 的输入来自 required targets 和 registry scopes。
- `tools/long_gate_manifest.py:446`：输出文件只记录 `required_regressions` 自己的 proof。
- `tools/long_gate_manifest.py:800`：`current_full_test_debt.json` 只在 full_test_debt entry 的 output_files 中出现，不是 required_regressions 的 input。

## 影响

- 如果 full-test-debt payload 变了，而 required_regressions 缓存命中，required 核销可能没有针对本轮 payload 重新执行。
- 这会削弱“required 用例在本轮 full-test-debt 中都 passed”的证明力。

## 建议

- 把 `evidence/QualityGate/current_full_test_debt.json` 的内容 hash 纳入 required_regressions 的指纹输入。
- 或者规定 full_test_debt 本轮执行后，required_regressions 必须强制执行。
- 补测试：payload 内容变了时 required_regressions 不能复用旧成功缓存。
