---
doc_type: refactor-apply-notes
refactor: 2026-07-12-algorithms-a3-dependency-decoupling
status: apply-completed-commit-proof-pending
base_head: 582a588c8adda314584052b870ace00628a722c7
---

# algorithms A3 dependency decoupling apply notes

## 授权与边界

- 2026-07-13：用户明确回复“执行吧”，授权按 approved design/checklist 进入 apply。
- 本次授权不包含 `git commit`、clean-HEAD proof、push 或 PR。
- apply 起点 HEAD 仍为 `582a588c8adda314584052b870ace00628a722c7`；进入 apply 前只有本 refactor 的 scan、approved design、approved checklist 为未跟踪内容。
- `core/algorithms/__init__.py` 起点 SHA256：`bca5f1d3515eb3f8ab694e0003e7dcce01fa4abe88584da906fabd2814e3594b`。

## 步骤 1：锁定 A3 公开边界与模块状态

- 开始时间：2026-07-13T10:40:53+0800
- 改动文件：`tests/algorithm/test_algorithms_a3_dependency_boundary.py`
- 完成时间：2026-07-13T10:43:00+0800
- 验证结果：运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/algorithm/test_algorithms_a3_dependency_boundary.py`，得到 `2 passed, 5 failed`。根 `GreedyScheduler`/根 `__all__`/签名/继承合同与旧 `greedy.algo_stats.deepcopy` 真实 patch 合同均通过；5 个失败分别只来自新 leaf 尚不存在、独立进程尚不能导入 canonical 路径，以及 production 模块数仍为 763/A3 尚未移除，符合红灯预期。
- 行为等价自检：本步只新增测试与执行记录，未改生产代码，不可能改变外部运行行为。
- 偏离：无。

## 步骤 2：建立纯 `core.algorithm_contracts` 叶子

- 完成时间：2026-07-13T10:54:07+0800
- 改动文件：新增 `core/algorithm_contracts/{__init__,date_parsers,dispatch_rules,ordering,priority_constants,sort_strategies,types,value_domains}.py`；将 `core.algorithms` 六个合同模块与 `greedy.date_parsers` 改为显式同对象 re-export；切换 approved checklist 列出的 greedy/dispatch 与 7 个重点生产调用方。
- 验证结果：8 个步骤专项文件 `50 passed`；`ruff check core/algorithm_contracts core/algorithms` 通过；旧/新纯合同 `__all__` 逐对象 identity 校验通过；新 leaf 无 `core.algorithms`/`core.services`/`core.algorithm_runtime` 反向 import；根 `core/algorithms/__init__.py` SHA256 仍为起点值。
- 结构结果：临时 production scan 为 `771 modules / 4 hard directory SCC / unresolved 6`；A3 已从 3 成员 / 42 边收缩为 `greedy ⇄ dispatch` 2 成员 / 11 边，其余 3 个 production SCC 成员与边数不变，无新 SCC。
- 调整：原型 wrapper/import 形式触发 10 个 Ruff `I001`；仅用 Ruff 自动整理 import 顺序后复跑专项和 lint，未改函数体、值、文案或 API。
- 行为等价自检：本步只搬移原实现、同对象 re-export 和切换 import；50 项专项、identity、签名与根字节合同均证明未改变外部行为。
- 偏离：无设计偏离；Ruff 仅做格式化排序。

## 步骤 3：建立 `core.algorithm_runtime` 共享运行时叶子

- 完成时间：2026-07-13T10:56:41+0800
- 改动文件：新增 `core/algorithm_runtime/{__init__,algo_stats,auto_assign_contract,downtime,internal_slot,run_state,runtime_state}.py`；按 checklist 更新 greedy runtime 兼容层、生产调用方和 scheduler run 调用方。`dispatch_context.py` 明确保留到步骤 4。
- 验证结果：6 个步骤专项文件 `29 passed`；Ruff 通过；runtime leaf AST 核对无 `core.algorithms`/`core.services` 反向 import；downtime/internal-slot/run-state/runtime-state 旧新路径逐对象 identity 通过；algo-stats 只下沉批准 helper，旧 `snapshot_algo_stats`/`merge_algo_stats`/模块全局 `deepcopy` 保留且 patch 探针命中真实执行。
- 边界进度：总边界测试变为 `6 passed, 1 failed`，唯一失败是步骤 4 尚未新增 `dispatch_context`，故模块数仍为 778 且 A3 尚未消失；不存在其它合同失败。
- 结构结果：临时 production scan 为 `778 modules / 4 hard directory SCC / unresolved 6`；剩余 A3 严格为 `greedy ⇄ dispatch` 2 成员 / 9 边，其余 SCC 不变，无新 SCC。
- 调整：终态原型 import 形式触发 14 个 Ruff `I001`，仅自动排序并在专项、Ruff、identity 和边界测试中复证。
- 行为等价自检：29 项 runtime 专项与 6 项总边界合同通过；没有算法函数体重写、值/错误文本变化或 patch 路径迁移。
- 偏离：无设计偏离；Ruff 仅做格式化排序。

## 步骤 4：把 dispatch 切到最小上下文边界

- 完成时间：2026-07-13T11:00:49+0800
- 改动文件：新增 `core/algorithm_runtime/dispatch_context.py`；更新 `dispatch/batch_order.py`、`dispatch/sgs.py`、`dispatch/sgs_scoring.py`、`resource_validation.py` 及上下文调用方。`ScheduleRunContext` 仍定义在 `greedy.run_context`，dispatch 三个主模块仍保留自身函数定义和真实 globals。
- 验证结果：批准的 15 文件专项 `120 passed`；A3 边界测试最终 `7 passed`；Ruff 通过；AST 证明 `dispatch_batch_order`、`dispatch_sgs`、`_score_internal_candidate` 仍在原 canonical 模块定义。
- 结构结果：production `779 modules / 3 hard directory SCC / unresolved 6`，production-and-tests `1475 modules / 4 SCC / unresolved 44`；A3 目录 SCC 消失；A4/A5/A6/tests 成员与圈内边数分别保持 41/2/3/11；hard file SCC 9、显式 hard 0、runtime file SCC 13、显式 runtime 4；A3 父包感知文件 SCC 精确为 8 成员 / 24 边；新 leaves 不进入目录 SCC。
- 调整：边界测试初版使用两个 `importlib.import_module(variable)`，使 include-tests unresolved 暂时从 44 增至 46。差异精确定位到该测试两行后改为静态 import，复扫恢复 44；没有修改生产实现、隐藏 import 或刷新基线。另有 6 个生产 import 和 1 个测试 import 的 Ruff `I001`，仅自动排序后复证。
- 行为等价自检：120 项 dispatch/SGS/graph 专项、7 项根/identity/import-order/module-state/SCC 边界全部通过，现有 monkeypatch 路径仍控制真实执行。
- 偏离：终态无偏离；测试动态 import 导致的临时 unresolved 已在本步骤内按硬约束消除。

## 步骤 5：完成兼容与调用图闭环

- 完成时间：2026-07-13T11:21:59+0800
- 测试结果：checklist 原命令把边界文件和其父目录同时交给 pytest，pytest 去重后只执行边界 7 项 + graph-on 39 项，结果 `46 passed`；随后单独运行 `tests/algorithm`，完整收集并通过 `557 passed in 14.02s`（起点 550 + 新边界 7）。graph-on 39 项已在前一命令通过。
- 双 scope：候选 `/tmp/a3-apply-production.json` 与 `/tmp/a3-apply-with-tests.json` 按正式 v2 口径逐 SCC 成员和圈内边比较通过；只移除 A3 目录块；其余目录 SCC、8 个非 A3 hard file SCC、unresolved 记录逐项相同；A3 文件圈严格从 21/94 缩为 8/24。
- 调用图确定性：`/tmp/a3-callgraph-run-1` 与 `run-2` 均含 10 个 JSON；文件集合相同且逐文件 SHA256 全部相同。
- 调用图总量：`7337 callable / 25798 total edges / 10171 confident / 15627 ambiguous / typed 0 / 685 dynamic unresolved / 8 cycles / 193 islands`，与 approved design 完全一致。
- callable 映射：起点 7329 个 callable 全部一一映射且目标不重复；4 个 auto-assign lambda 因 import 行数变化按“同作用域 + 同列号”稳定键映射；旧 callable 丢失 0。新增 8 个 callable 恰为 `_LegacyDispatchContext` 七个方法与 `ensure_dispatch_context`。
- 边映射：全量 Counter 比较得到旧差异 6、新记录 18；其中 4 条 algo-stats 相同端点 `local → import`，2 条 `dispatch_batch_order/dispatch_sgs → ensure_run_context` 被 `→ ensure_dispatch_context` 替代；剩余 12 条加两条替代新端点合计 14 条均连接 adapter callable，无其它漂移。
- dynamic unresolved：旧 680 条按 callable 新路径/新行号映射后全部保留；新增恰好 5 条且都来自 `dispatch_context.py` 的显式 `getattr` callback 点。
- 行为等价自检：完整算法、graph-on、双 scope、两次调用图及全 callable/边/dynamic 映射全部闭合；不存在“测试绿但静态边丢失”。
- 偏离：无。

## 步骤 6：收紧正式证据并同步当前事实

- 完成时间：2026-07-13T12:13:43+0800
- 双正式基线：受控执行 production / production-and-tests `--update-baseline`；随后另写 `/tmp/a3-formal-*-candidate.json`，两份均与正式文件逐字节相同。production 基线 518→384 行，with-tests 578→444 行；刷新后双 `--fail-on-new-cycle --quiet-when-clean` 均通过。
- 正式调用图：以步骤 5 的 run-1 覆盖正式 10 JSON；正式文件集合/内容与确定性候选逐文件相同。`baseline.json` 记录 7337/25798/10171/15627/685 等当前事实，25 项 artifact SHA256 全部复算匹配。
- dead-code：只迁移 `WeightedStrategy.__init__` 与 `ScheduleSummary.__post_init__` 两个身份。quick 仍报告 193 candidates / 86 explained / 107 suspect，以及 A2 起点已有的 32 个新增候选；过滤核对后没有任何 `algorithm_contracts`、`algorithm_runtime` 或 `core/algorithms` A3 新候选，故不全量 refresh。该命令因 32 个既有候选按设计返回 1，未伪报为门禁全绿。
- 事实同步：更新 checkup README/baseline、架构总入口、scheduler 架构、两份 audit 与 dependency roadmap/items。R3 只从 planned 改为 in-progress；A3 当前注明 apply 机械证据完成但 commit/clean proof 待授权，A4/A5/A6/tests 未启动，未误标 completed。
- 结构数字：production 779/3/6639/unresolved 6，with-tests 1475/4/13296/unresolved 44；hard file 9/0、runtime file 13/4，A3 文件圈 8/24。双 YAML 校验、JSON parse、`git diff --check`、49 个批准生产 Python 文件精确范围和根 init SHA 全部通过。
- 证明边界：`baseline.json.worktree_tooling_refresh.clean_worktree_proof=false`、manifest status=`pending`；正式证据是当前未提交工作区事实，不借用 A1/A2 clean proof。
- 行为等价自检：正式证据只在步骤 5 全测试、双 scope 和全调用图映射闭合后刷新；没有用 baseline 覆盖解释不了的漂移。
- 偏离：无。dead-code quick 的非零退出来自已记录的 32 个既有候选，A3 新增为 0。

## 步骤 7：提交前与 clean-HEAD 证明

- 完成时间：2026-07-13T12:45:54+0800（提交前部分完成；clean-HEAD 部分待单独授权）。
- 最终专项：在最终源码上运行 A3/完整 algorithm/ready-queue/graph/calendar 组合，`643 passed in 13.75s`；Ruff 全绿。
- 类型检查：首次 gate Pyright 发现新 adapter 的动态 logger 被推断为 Optional，修正为 `self.logger: Any` 后 `0 errors, 15 warnings`；15 条均为既有 scheduler 惰性 `__all__` 警告。tools Pyright 为 `0 errors, 0 warnings`。
- Python 3.8：首次 A3 起点范围扫描暴露 `schedule_params.py` 起点已有的 `set[str]`（本轮因 import 改动进入扫描范围）；按 Win7/Python 3.8 硬约束改为 `typing.Set[str]`，复扫 33 文件为 0 findings。完整门禁正式扫描 1203 文件、读取失败 0、findings 0。
- 修正后证据复封：两次最终调用图与正式 10 JSON 逐文件仍完全相同；从固定起点 HEAD 重新提取旧调用图后，全 7329 callable/全边/dynamic 映射再次 `CALLGRAPH_MAPPING_OK`。双 scope 正式循环门禁再次通过，正式 artifact SHA 无变化。
- 完整门禁：执行 `scripts/run_quality_gate.py --allow-dirty-worktree --no-long-gate-cache --no-resume`；19 份 receipt 的 `returncode` 全为 0，4731 collected、collection error 0、unexpected failure 0、required 253 targets / 2467 nodeids。manifest=`passed_but_unbound`、`is_dirty_before=true`、`is_dirty_after=true`、`tracked_drift_detected=false`。
- 进程退出说明：wrapper 退出码为 2，且明确提示 dirty proof 未绑定；这是 `--allow-dirty-worktree` 防止被冒充 clean proof 的预期策略，不是 19 个子步骤失败。当前只声明 dirty-worktree diagnostic 完成。
- 行为等价自检：最终代码、专项、全算法、完整质量门禁、双 scope 和调用图证据全部闭合；唯一源码验证修正是动态属性类型标注和私有注解的 Python 3.8 兼容写法，不改变运行逻辑。
- 授权边界：尚未执行 `git commit`，未运行 `--require-clean-worktree`，未 push/PR。下一步必须先取得单独 commit 授权；提交后才能在固定最终 HEAD 上补 clean proof。
- 偏离：原 checklist 的 Python 3.8 检查暴露一条起点存量注解；按项目硬约束在已触碰文件内最小修正，并在源码变化后完整重封调用图/循环证据。无其它偏离。
