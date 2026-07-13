---
doc_type: audit-finding
audit: 2026-07-13-unpushed-dependency-governance-review
finding_id: "bug-02"
nature: bug
severity: P2
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 02：调用图把同一 imported-module 调用同时记成确信边和模糊边

## 速答

提交 `9417bde3` 重写并重建的调用图仍会把一个已经按 import alias 精确解析的 `module.function()` 调用，同时再按“同名属性”生成一条模糊边；同一真实调用因此进入两套计数，污染 fan-in/fan-out、总边数和热点排序，也让“工具可信闭环”的数字口径不自洽。

## 关键证据

- `.codestable/checkup/scripts/callgraph_extract.py:200-209` — `_add_imported_module_attr_edges()` 对已知 import alias 生成 `module_import_attr, ambiguous=False` 确信边。
- `.codestable/checkup/scripts/callgraph_extract.py:171-186` — `_add_attr_edges()` 又把所有非 `self` 属性调用按方法名扩成 `attr, ambiguous=True` 候选，没有排除已经精确解析的 callsite。
- `.codestable/checkup/scripts/callgraph_extract.py:231-252` — `_resolve_edges()` 对同一批属性调用先执行 imported-module 精确消解，再无条件执行通用 attr 消解，形成双记。
- `.codestable/checkup/scripts/callgraph_extract.py:256-268` — `_fan_counts()` 按 edge record 逐条累加，确信边和模糊边都会计数，因此不是单纯输出冗余。
- `tests/gate_meta/test_callgraph_receiver_resolution.py:103-109` — 现有测试只断言确信边存在，没有断言同一 source/target 不得再出现模糊边，所以 213 项定向回归和完整门禁都能通过。
- `.codestable/checkup/latest/callgraph/summary.json:1` — 当前正式快照 `total_edges=25798`，但 NetworkX 去重后的 `graph_metrics.edge_count_total=25701`；两种“总边数”相差 97。

使用现有测试同款最小输入：

```python
# helpers.py
def actual():
    return None

# main.py
import helpers as helper_module

def run():
    return helper_module.actual()
```

当前 `_resolve_edges()` 对唯一调用输出两条记录：

```text
main.py::run -> helpers.py::actual  kind=module_import_attr ambiguous=False
main.py::run -> helpers.py::actual  kind=attr               ambiguous=True
```

对正式 `edges.json` 统计，当前至少有 **92 组相同 source/target 同时具备确信和模糊记录**；例如 `BatchService.create -> batch_write_rules.build_create_payload` 就被双记。

## 影响

- 确信边构成的 cycle 图本身不会因这类模糊副本新增确信循环，所以不推翻 A1/A2/A3 的 import-cycle SCC 结论。
- `functions.json` 的 fan-in/fan-out、`high_fan_in.json`、风险排序和人工引用的总边数字会被抬高；它们既不是“唯一函数依赖边数”，也不是“真实调用点数”（同一位置可能双计，多位置又可能被 set 折叠）。
- A1/A2/A3 的“旧边全映射”是用同一套口径前后比较，因此能保持相等，却不能证明该口径本身正确；这属于自洽性证明而非真实性证明。
- 工具拆分本身符合 KISS，但目前精确分支和模糊分支没有互斥，增加了无价值噪音。

## 修复方向

以 callsite 为单位先做精确消解：已被 imported-module 规则命中的 `(receiver, method, line)` 不再进入通用 attr 候选；最终 edge 集也应定义清楚是“唯一依赖边”还是“调用点证据”，不要让 fan 统计混用两种口径。补测试同时断言确信边存在、同端点模糊副本不存在，并在修复后重建调用图、baseline artifact SHA 和引用数字。

## 建议动作

`cs-issue`，因为这是治理工具的可复现计数/置信度错误。它不阻断业务运行，但在继续用调用图数字做架构决策前应修正。

## 修复闭环（2026-07-13）

- 已进入 `.codestable/issues/2026-07-13-callgraph-imported-module-edge-dedup/` 标准 issue。
- `_add_imported_module_attr_edges()` 现在返回已精确解析的 `(receiver, method, line)`；`_add_attr_edges()` 只消费剩余 callsite。最小用例由“确信 + 模糊两条”收敛为唯一 `module_import_attr, ambiguous=false`。
- 对旧正式快照精确核对：删除 111 条 `attr, ambiguous=true` 记录，全部可由同 source/方法名的 imported-module 确信边解释，未出现未解释删除；新增仅 1 条 Finding 01 strict 修复带来的真实确信边。
- 旧快照中 `module_import_attr` 确信边与同 source/target `attr` 模糊边精确重叠 88 组，修复后为 0。新的 25688 edge records 与 25679 唯一端点边相差 9，逐项都是 function-reference 与 import/self/attr 等不同证据类型，不属于本 issue 的同 callsite 双消解。
- 两个独立临时目录的 10 JSON 文件集合及逐文件 SHA 全同；正式快照、`baseline.json` 25 项 artifact SHA 和当前事实文档已重建。完整门禁 19/19 receipts 均通过；当前仍是未提交 dirty proof，manifest=`passed_but_unbound`。
