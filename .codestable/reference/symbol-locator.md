# 产品函数定位与影响面

用于产品函数定位、调用链与实现影响分析；维护技能说明无需扫描产品调用链。命令从项目根目录运行。

## symbol-locator 函数定位工具

常用命令：

```bash
python3 -m tools.symbol_locator whereis compute_candidate_run
python3 -m tools.symbol_locator callers compute_candidate_run
python3 -m tools.symbol_locator callers compute_candidate_run --deep
python3 -m tools.symbol_locator callees compute_candidate_run
python3 -m tools.symbol_locator whereis normalize_objective_name --at core/services/scheduler/run/optimizer/shared_archive.py:105
```

`--at` 用于 `whereis` 的同名消歧，位置必须来自当前源码中的实际定义或调用点；文件行号随修改重新定位。上面的候选计算和目标名称规范化均为当前保留符号。

选择规则：

| 用户话术 | 应运行 |
|---|---|
| `X 在哪` / `X 定义在哪` / `找下函数 X` | `python3 -m tools.symbol_locator whereis X` |
| `谁调用 X` / `X 被谁用` / `改 X 影响谁` / `动 X 前看波及` | `python3 -m tools.symbol_locator callers X` |
| `X 调了啥` / `X 依赖谁` | `python3 -m tools.symbol_locator callees X` |
| `X 的调用链` / `上下游` | `python3 -m tools.symbol_locator callers X` + `python3 -m tools.symbol_locator callees X` |
| `彻底` / `全量` / `精确` / `含 tests` | 在 `callers` 或 `callees` 后加 `--deep` |
| 句首 `定位:` / `用定位工具` / `上 sl` | 必须按语境选择上面的命令 |

## 指定变更范围的调用链核对与索引边界

针对指定变更文件、提交或函数集合核对调用链时，统一使用 `python3 -m tools.symbol_locator`：

1. **范围边界**：核对范围严格来自当前用户授权（指定文件、指定提交比较基线、staged-only 或显式函数集合）。不默认把 `HEAD~1` 当作比较基线，也不把变更文件里的全部未改动定义都当作变更符号逐一全扫。
2. **定位与双向关系**：先确认本次实际变更的函数/方法定义，再对其运行 `whereis`、`callers`、`callees`（同名符号按 `rel::qual` 区分，必要时用 `--at FILE:LINE` 消歧；需覆盖测试或更深引用时加 `--deep`）。批量核对可在同一次读取中复用 `tools.symbol_locator.static_index` 筛选目标定义键，避免逐符号重复全仓扫描。
3. **证据等级与源码复核**：保留 `confident`、`ambiguous`、`dynamic` 的证据差异；`--deep` 使用现有 SCIP 索引能力，仍不承诺动态 Python 的完整调用图。跨层边界、签名兼容、`Optional` 返回值与空值/事务合同必须回到真实源码上下文核对，不能凭搜索命中或附近几行出现 `if`/`None` 下结论。
4. **索引新鲜度（`refresh`）与只读边界**：CLI 执行 `whereis` / `callers` / `callees` 时默认检查静态图快照（`.codestable/checkup/latest/callgraph/`）新鲜度，源码变更后或显式传 `--rebuild` 会自动重建静态图；`--deep` 依赖 SCIP 索引（按需运行 `python3 -m tools.symbol_locator build-index` 刷新）。在明确禁止刷新索引或严格无副作用的只读核对场景下，直接读取现有静态索引快照结合源码核对，不借查询之名触发索引重建，也不自动落盘固定调用链报告文件。
