# Finding 07：full_test_debt 缓存没有覆盖分片规则实现文件

- 优先级：P2
- 结论：只改 `tools/full_test_debt_shards.py` 时，full_test_debt 的长门禁缓存可能不会因为分片规则变化而失效。

## 根因

`full_test_debt` entry 的 input/config scopes 覆盖了测试、业务代码、`collect_full_test_debt.py`、`check_full_test_debt.py` 等，但没有直接包含 `tools/full_test_debt_shards.py`。这个文件决定哪些用例 serial、哪些用例 parallel，属于 full-test-debt 执行语义的一部分。

## 证据

- `tools/full_test_debt_shards.py`：定义 serial/parallel 分类规则。
- `tools/long_gate_manifest.py:703-748`：full_test_debt 的 input scopes。
- `tools/long_gate_manifest.py:750-764`：full_test_debt 的 config scopes，其中没有 `tools/full_test_debt_shards.py`。
- `tools/quality_gate_shared.py:120` 和 `pyrightconfig.tools.json:12`：该文件已经进入全局工具清单，但这不等于进入 full_test_debt entry 的缓存输入。

## 影响

- 分片规则变化可能没有触发 full_test_debt 缓存失效。
- 分片隔离规则本身如果改坏，旧成功缓存可能掩盖问题。

## 建议

- 把 `tools/full_test_debt_shards.py` 加进 full_test_debt entry 的 config/tool scope。
- 补测试：改分片 helper 必须改变 full_test_debt fingerprint。
