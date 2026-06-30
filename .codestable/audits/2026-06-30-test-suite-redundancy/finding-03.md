---
doc_type: audit-finding
audit: 2026-06-30-test-suite-redundancy
finding_id: "maintainability-03"
nature: maintainability
severity: P2
confidence: medium
suggested_action: cs-refactor
status: open
---

# Finding 03:3 个无显式断言测试均为 by-design 契约,可选增强

## 速答

全套 3837 个测试里,只有 **3** 个测试函数没有任何显式断言(无 `assert`、无 `pytest.raises`、无 `raise`、无委托断言)。逐一核实:全部是 by-design 的"调用目标、只要不抛异常就算通过"契约测试,**不是无意义的空转,不建议删**。如果要拔高,可加一条显式断言把意图写明,但优先级最低。

## 关键证据(3 个)

- `tests/algorithm/test_greedy_algo_stats_contract.py` — `test_missing_stats_sink_is_allowed_for_direct_compat_calls`:函数体是 `increment_counter(None, "x_count")`。意图就是"stats sink 为 None 时直接兼容调用**不报错**"(名字 `..._is_allowed`)。属合法冒烟契约。
- `tests/gate_meta/test_architecture_fitness.py:332` — `test_startup_silent_fallback_samples`:函数体是 `architecture_validate_startup_samples()`。断言其实**在该 helper 内部**(它来自被测模块,内部会 `raise`),只是扫描器的文件内闭包跨不到 import 来的函数,所以显示为"无断言"。严格说不算低价值,定位时知道即可。
- `tests/models_domain/test_normalize_text.py` — `test_append_unique_text_messages_accepts_none_buffer`:函数体是 `append_unique_text_messages(None, ["告警", "", None])`。意图是"buffer 为 None 时**不抛异常**"(名字 `..._accepts_none_buffer`)。属合法冒烟契约。

## 影响

无。这 3 个不是"假绿"测试——它们各自守着一个"特定输入下不崩溃"的契约,被测代码真退化(开始抛异常)时它们会失败。

## 修复方向

可选:给前两个"不抛即过"型各补一条显式断言(如断言返回值 / 计数器未被污染 / buffer 仍为期望形态),把"我在验什么"写明。不补也可接受。第二个(architecture_fitness)无需改。

## 建议动作

`cs-refactor`(可选、最低优先);若不增强则本条仅作"全套无意义测试 ≈ 0"的结论存档。
