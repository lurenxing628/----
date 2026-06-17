# Finding 06：拆分后的 test registry 文件没有进工具门禁源码清单

- 优先级：P2
- 结论：required registry 的拆分实现没有完全进入 `QUALITY_GATE_SOURCE_FILES` 和 `pyrightconfig.tools.json`，门禁自身证明范围不完整。

## 根因

`tools/test_registry.py` 已经拆成 facade，实际数据在三个新文件里。但 `QUALITY_GATE_TOOL_PATHS` 和 `pyrightconfig.tools.json` 仍只列 `tools/test_registry.py`，没有列三个被导入的实现文件。

## 证据

- `tools/test_registry.py:9-19`：导入：
  - `tools.test_registry_data`
  - `tools.test_registry_groups_misc`
  - `tools.test_registry_groups_scheduler`
- `tools/quality_gate_shared.py:110-143`：`QUALITY_GATE_TOOL_PATHS` 没有这三个文件。
- `tools/quality_gate_shared.py:153-167`：`QUALITY_GATE_SOURCE_FILES` 从 `QUALITY_GATE_TOOL_PATHS` 展开。
- `pyrightconfig.tools.json:2-43`：tools pyright include 没有这三个文件。
- 主线程只读检查输出：三个文件在 `QUALITY_GATE_TOOL_PATHS / QUALITY_GATE_SOURCE_FILES / pyrightconfig.tools.json include` 中全部为 `False`。

## 影响

- 修改 registry 数据文件时，门禁证明链不一定把这类变动当成工具源码变动。
- tools pyright 也不会直接覆盖这些被拆出的实现文件。

## 建议

- 把三个文件加入 `QUALITY_GATE_TOOL_PATHS` 和 `pyrightconfig.tools.json`。
- 补一个测试，断言 `tools/test_registry.py` 的直接实现依赖必须全部进工具门禁清单。

## 复核说明

此前有子代理把 `tools/full_test_debt_shards.py` 也归为同类漏项。主线程复核后更正：它已经在 `QUALITY_GATE_TOOL_PATHS` 和 `pyrightconfig.tools.json` 中；它的问题只在 full_test_debt 这个长门禁缓存 entry 的输入范围，不能混为一谈。
