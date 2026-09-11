---
doc_type: refactor-apply-notes
refactor: 2026-07-19-summary-build-context-typing
---

# U01 执行记录

## 前置刻画

- 环境：`.venv/bin/python --version` 为 Python 3.8.10；pyright 与 ruff 使用本地已安装工具，不升级依赖。
- `symbol_locator whereis/callers SummaryBuildContext` 均报告未找到函数；类构造按 `rg` 核对。`callers/callees build_result_summary` 已运行，索引快照为 2026-07-20，存在 ambiguous 边，不能冒充当前全量精确图。
- 前置文件副本与命令日志：`/tmp/aps-u01-20260908-HMWgLK/`。副本保留两个消费者已有的 A18 未完成批次风险业务修改。
- 相关 pytest 基线：183 passed，1 failed。失败为 `test_algorithms_a3_dependency_boundary.py::test_a3_is_removed_without_changing_other_directory_cycles` 的测试模块数量 1525 != 1522，不是新增依赖圈。
- 生产 pyright 基线：713 files，2 errors，15 warnings；错误在 `core/algorithm_runtime/downtime.py:62,64`。默认含测试配置：1452 files，719 errors，16 warnings。
- 不运行会写共享 manifest 的完整 `scripts/run_quality_gate.py`；共享 dirty 与并发修改不具备绑定 HEAD 的证明条件，主代理统一执行。

## 类型实施

- `schedule_summary_types.py:15` 新增只要求 `to_dict` 的 `SummaryMetrics` Protocol；`:34-55` 收紧 8 个字段。没有新增生产模块，也没有反向引入 algorithms/config/run/summary。
- `schedule_summary_assembly.py:59,77,228,299,385` 对结果列表、summary 和结束日期回调补齐类型；`summary_runtime_state.py:175,221` 对 runtime/warning 构建参数补齐类型。两个消费者所有函数体保持不变。
- 与前置副本做去注解 AST 比较：三个生产文件均通过。对比只忽略模块 import 和新声明的 Protocol，保留其他语句、常量、函数签名默认值及 dataclass 字段声明顺序。
- 新测试 `tests/schedule/summary/test_summary_build_context_typing.py` 锁定 39 个字段原始注解/顺序、前 20 个必填项及其余默认值，验证 frozen/replace、domain/日期对象原样保留、轻量 metrics 可缺省诊断属性、干净子进程导入和静态正反样例。
- 新测试单跑：9 passed。pyright 正样例包含真实 ScheduleMetrics 和最小结构实现；8 个错误字段样例均产生对应 `reportArgumentType`，没有 cast/ignore 逃过检查。
- `cfg`、异构元数据、trace、warning_merge_status 和 BuildOutcome 的列表元素仍保留 Any；Metrics 的可缺省诊断字段仍通过现有 getattr 读取。上游归一对象和 kwargs 通道的 Any 仍可绕开静态类型，这不是运行时数据校验项目。

## 验证结果（dirty / unbound）

- scoped pyright：三个生产文件及新测试为 0 errors / 0 warnings；tools 配置 0 errors / 0 warnings。
- 相关 pytest：192 passed、1 failed。仍为 A3 全仓快照测试，当前首个断言变成生产模块数 800 != 786；这是并行现场变化，本轮只新增一个测试模块，不修改其快照。
- Python 3.8.10 scoped 语法扫描与四文件 ruff 均通过。草案的无路径全仓语法扫描会扫入 `.venv-semantic` 宿主依赖，出现 16825 条发现；不能把那个结果当成产品范围结论，最终使用显式写集并加 `--fail-on-hit`。
- 生产全配置最终记录：727 files、3 errors、15 warnings。两个基线错误仍在 `core/algorithm_runtime/downtime.py:62,64`；并行新增错误在 `core/services/scheduler/run/optimizer_graph_ready_repair.py:152`（空字符串传给 SortStrategy）。不越界修复，也不宣称全配置通过。
- 默认含测试配置最终记录：1474 files、708 errors、16 warnings。前后整体数字受其他代理增删修改影响，不能据 719 -> 708 声称 U01 消除了 11 个错误。U01 可归因增量为 23 条旧假对象诊断：dict cfg 合同 2、due exclusive 3、optimizer public projection 8、summary v11 2、result summary 合同 4、graph summary 合同 4；都因 SimpleNamespace 不满足 domain 类，没有修改这些测试或压制诊断。
- 导入扫描生产 800 modules / 含测试 1547 modules，parse_errors 均为空；基于 JSON 单独断言 A1/A3 及 contracts、algorithm_contracts、algorithm_runtime 不在 hard directory SCC 中，两份均通过。A3 原测试卡在数量断言，不能将整个 A3 套件称为通过。
- 三个生产文件及新测试行数为 151 / 493 / 344 / 298；未超过 500 行。`git diff --check` 通过。

### 实际执行命令

以下命令均在仓库根执行；pytest 基线未包含后来创建的专属测试，最终目录运行自动纳入它。

```bash
.venv/bin/python -m pytest -q tests/schedule/service/test_scheduler_a1_dependency_boundary.py tests/algorithm/test_algorithms_a3_dependency_boundary.py tests/schedule/service/test_schedule_orchestrator_contract.py tests/schedule/summary/ tests/algorithm/test_dict_cfg_contract.py tests/algorithm/test_due_exclusive_consistency.py tests/algorithm/test_optimizer_public_summary_projection_contract.py tests/scheduler_graph/test_scheduler_graph_summary_contract.py
.venv/bin/python -m pytest -q tests/schedule/summary/test_summary_build_context_typing.py
.venv/bin/python -m pyright -p pyrightconfig.gate.json --outputjson
.venv/bin/python -m pyright -p pyrightconfig.json --outputjson
.venv/bin/python -m pyright -p pyrightconfig.tools.json --outputjson
.venv/bin/python -m pyright -p pyrightconfig.gate.json core/services/scheduler/contracts/schedule_summary_types.py core/services/scheduler/summary/schedule_summary_assembly.py core/services/scheduler/summary/summary_runtime_state.py tests/schedule/summary/test_summary_build_context_typing.py
.venv/bin/python -m ruff check core/services/scheduler/contracts/schedule_summary_types.py core/services/scheduler/summary/schedule_summary_assembly.py core/services/scheduler/summary/summary_runtime_state.py tests/schedule/summary/test_summary_build_context_typing.py
.venv/bin/python -m tools.scan_py38plus_syntax --fail-on-hit core/services/scheduler/contracts/schedule_summary_types.py core/services/scheduler/summary/schedule_summary_assembly.py core/services/scheduler/summary/summary_runtime_state.py tests/schedule/summary/test_summary_build_context_typing.py
.venv/bin/python -m tools.scan_import_cycles --json
.venv/bin/python -m tools.scan_import_cycles --json --include-tests
```

### 已验证文件指纹

用于标识共享 dirty 现场，不是 HEAD/clean proof；日志位于前述临时目录。

| 文件 | SHA-256 |
|---|---|
| contracts/schedule_summary_types.py | bc16686cdec03c2668a0e46ced6f6a98639b7a8e796e1eaacbd7607998637204 |
| summary/schedule_summary_assembly.py | ce3c35ab44dd5ff5491f0622346957efeab212846a609e87982a0692369151d4 |
| summary/summary_runtime_state.py | f204a0984a8c884608441d17778e2da2d0049addf24d7de76806923ba3d64dc1 |
| tests/schedule/summary/test_summary_build_context_typing.py | 719f9cd28d4c7b1d1e62b2a0f799661f76ef767d633f3f4679401d3811cefe35 |

## 收尾边界

- 本轮只有三个生产文件、一个专属测试、三份本目录记录；草案保留原文，正式实施以批准设计和本记录为准。
- 不改公共 registry/基线/roadmap；保留既有 dirty 和其他代理写入，不执行 git add/commit/push。
- 完整门禁与统一提交交主代理；本清单的 passed 仅指明确列出的局部检查，不表示整个仓库验收通过。
