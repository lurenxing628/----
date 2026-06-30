---
doc_type: audit-finding
audit: 2026-06-30-test-suite-redundancy
finding_id: "maintainability-02"
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 02:完全重复(AST 一字不差)4 组核实——无一可直接删

## 速答

扫描器报出 4 组"函数体 AST 完全相同"的测试(用户最关心的"完全重复")。逐组实读后:**3 组是被测对象 / parametrize 契约确实不同的"误导性重复",删任何一个都会丢覆盖;1 组可并入参数化(已收进 finding-01 M18)。没有一组够格直接删除。** 这条记录的价值在于纠正"AST 相同 = 可删"的直觉。

## 关键证据(4 组)

- `tests/algorithm/test_optimizer_compare_algorithms_contract.py:332` ↔ `tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py:336` — 函数体一字不差,但各自 import 的 `_proof_check` 来自**不同脚本**(通用算法对比 vs SMTWT 对比,见两文件第 9 / 11 行 import)。**被测对象不同 → KEEP**。⚠ 前者本轮工作区有未提交改动。
- `tests/app_runtime/test_startup_host_portfile.py:273` ↔ `tests/app_runtime/test_startup_host_portfile_new_ui.py:265` — 辅助函数几乎逐行相同,但分别拉起 `app.py`(断言 `ui_mode=="default"`)与 `app_new_ui.py`(断言 `ui_mode=="new_ui"`),两个入口**真实并存**。**端到端契约不同 → KEEP**(详见 finding-04 的"瘦身正解")。
- `tests/scheduler_graph/test_graph_types.py:82` ↔ `:102` — 函数体相同(`with pytest.raises(ValueError, match=field_name): _make_node(**kwargs)`),但**两者的 `@pytest.mark.parametrize` 装饰器不同**:`:82` 喂空字符串标识符,`:102` 喂非整数运行时字段。扫描器没比对装饰器才误判 EXACT。**两条契约都要留 → KEEP**。
- `tests/schedule/route_view/test_scheduler_batches_page_viewmodel.py:516` ↔ `:556` — 两者都已是 parametrize、函数体逐字相同,仅 parametrize 数据不同(unknown 值 vs incomplete 值)。**可合并 → 见 finding-01 M18**(拼接两组数据表)。

## 影响

无产品影响。意义在于:若有人拿"完全重复"清单盲删,会误删 `scheduler_graph` 的非整数字段校验、`app_runtime` 的 new_ui 入口回归等真实覆盖。

## 修复方向

仅 M18 一组并入参数化(已在 finding-01);其余 3 组维持现状,不动。

## 建议动作

`cs-refactor`(仅针对 M18);其余 3 组无需动作,本条主要作为"完全重复 ≠ 可删"的核实存档。
