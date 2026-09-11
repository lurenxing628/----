---
doc_type: issue-fix-note
status: fixed
created: 2026-09-08
updated: 2026-09-08
tags: [U03, U04, dispatch, callback, contract]
---

# U03 + U04 派工 callback 合同修复记录

## 结论与范围

- 实施完成，专项与相关行为回归通过；共享门禁、基线集成和统一提交仍由主代理处理。本记录不是 clean-worktree proof。
- 本机验证日期为 2026-09-08（Asia/Shanghai）；Python 为仓库 `.venv/bin/python` 的 **3.8.10**，没有升级依赖、语法或运行时。
- 开始时 `run_context.py`、实际 legacy 路径 `core/algorithm_runtime/dispatch_context.py` 没有既有改动；其他大量 dirty、暂存及未跟踪内容全部保留。没有运行 `git add/commit/push`。
- 只修改两个适配实现、新增一个类型叶子模块、三个专项测试，以及本计划目录的状态和本记录。没有修改 scheduler/seed、batch_order/SGS 的 except、evaluation、optimizer、公共台账、基线、registry 或共享调用图。

## 根因与实施

- 旧的适配层直接调用 callback；参数绑定失败的普通 `TypeError` 进入派工循环的广义业务异常处理，从而被记为 `dispatch_operation_exception`。strict 模式缺少 `op`/`batch` 时还会先抛裸 `KeyError`。
- `core/algorithm_runtime/dispatch_context.py:61` 新增 `check_dispatch_callback_binding`：先 `Signature.bind(*args, **kwargs)`，只把绑定错误转为既有 `DispatchContextContractError`。callback 正文不在转换用的 try/except 内，正文 `TypeError` 和坏结果转换的原有分类不变。
- `core/algorithm_runtime/dispatch_context.py:33` 将 `inspect.signature(..., follow_wrapped=False)` 的标准不可内省错误转为合同错误。按本轮明确授权 **fail closed**，不采用旧草案的跳过方案；decorator 按真实 wrapper 签名校验，不强加 `__wrapped__` 的形参。
- 错误文案带实际槽名；原始内省/bind 异常保留在 `__cause__`，不丢失 traceback。主错误不拼接原始错误文本，避免上游 unknown-signature wrapper 用 `unexpected keyword argument` 文本错误重试；未改上游异常处理。
- `core/algorithm_runtime/dispatch_context.py:24` 的缓存仅缓存 Python 函数及绑定方法；同一底层函数跨实例共享，bound/unbound 分开，不持有绑定实例。缓存检测 `__code__`、位置默认参数数量、keyword 默认键集合、显式 `__signature__` 的变化；callback 替换也自然失效。
- 已验证调用形态的缓存键包含位置参数数量和关键字集合，不缓存实参值；签名缓存最多 256 项，每签名形态最多 128 项。callable 实例、partial、builtin 每次重新内省，避免自定义 hash/相等或可变 partial 造成错误缓存；不可哈希并不等于跳过校验。
- `core/algorithm_runtime/dispatch_context.py:77` 共享 strict 输入检查，把缺 `op`/`batch` 改为明确合同错误。非 strict 的部分 kwargs 仍允许由 callback 自身签名决定；不在构造期要求全部能力。
- `core/algorithms/greedy/run_context.py:53` 起为四个槽及 canonical fallback 接线；fallback 校验增补后的最终实参，包括 external facade 的位置参数。`schedule_internal` 仍 pop `strict_mode` 再调用 legacy callback，fallback 回填该值；external 仍原样透传。
- `core/algorithm_runtime/dispatch_context.py:104` 起接线 legacy 三个真正 callback 调用方法；legacy tuple auto-assign 门面仍经 attempt 分支校验，不复制算法或合并双轨。
- `core/algorithm_runtime/dispatch_callback_types.py:10` 起定义四个 Protocol，`run_context.py:26` 起替换原 `Callable[..., Any]` 槽注解。attempt 的返回声明保留既有 `AutoAssignAttempt`/tuple/list/None 适配语义，不新增运行时返回值规则。

## 测试与命令

- 红灯验证：只加首批测试、尚未改产品代码时，`test_dispatch_callback_binding_contract.py` 为 **14 failed / 8 passed**；实测复现两轨、batch_order/SGS、internal/external 签名漂移，以及 strict 缺输入、不可内省仍执行。
- 新增三份测试最终共 **91 项通过**：`test_dispatch_callback_binding_contract.py`、`test_dispatch_callback_signature_cache.py`、`test_dispatch_callback_types_contract.py`。
- `test_dispatch_callback_binding_contract.py:55` 验证签名错误中止、不落业务失败；`:71` 验证正文 TypeError 仍落原分类；`:137` 验证 fallback 缺参及完整合法键集合再额外加参均失败；`:207` 验证已知/未知 schedule 签名上游不重试。
- `test_dispatch_callback_signature_cache.py:62` 验证跨实例只内省一次、形态只 bind 一次、clear 后重查、实例不被持有；`:143` 验证原函数签名元数据漂移重新检查；其余覆盖位置/关键字冲突、positional-only、partial、不可哈希、wrapper 和缓存大小上限。
- `test_dispatch_callback_types_contract.py:59` 起冻结 Protocol 字段、dispatch 的实际 AST keyword 集合、GreedyScheduler 四方法和 canonical fallback 三方关系；`:106` 起验证 SGS probe 13 键、commit 12 键与 auto-assign 两种 callback。
- 最终相关回归命令：

```bash
.venv/bin/python -m pytest -q \
  tests/algorithm/test_dispatch_callback_binding_contract.py \
  tests/algorithm/test_dispatch_callback_signature_cache.py \
  tests/algorithm/test_dispatch_callback_types_contract.py \
  tests/algorithm/test_greedy_refactor_contract.py \
  tests/algorithm/test_batch_order_bid_unboundlocal.py \
  tests/algorithm/test_internal_slot_estimator_consistency.py \
  tests/algorithm/test_dispatch_blocking_consistency.py \
  tests/algorithm/test_schedule_optimizer_strict_mode_signature_cache.py \
  tests/algorithm/test_algorithms_a3_dependency_boundary.py \
  -k 'not test_a3_is_removed_without_changing_other_directory_cycles'
```

- 结果：**154 passed / 1 deselected**。被排除的是下面已实际运行并失败的模块计数断言，不是把失败改为成功。
- 扩大回归 `.venv/bin/python -m pytest -q tests/algorithm tests/schedule/route_view tests/gate_meta/test_callgraph_receiver_resolution.py`：**1089 passed / 1 failed**（45.04s）。唯一失败在 `test_algorithms_a3_dependency_boundary.py:399`，期待生产模块数 786、扫描时实际 799。共享工作区仍有其他 agent 增加模块，数量不是固定终值。
- 对两个适配文件、新类型文件及三份新测试执行 `.venv/bin/ruff check`：通过；执行 `.venv/bin/python -m pyright <上述六个文件>`：**0 errors / 0 warnings**。
- `.venv/bin/python -m pyright -p pyrightconfig.gate.json`：**3 errors / 15 warnings**，错误位于本写集外 `downtime.py:62/64`、`optimizer_graph_ready_repair.py:159`；没有擅自修改。
- 全仓 `pyrightconfig.json` 包含测试的探测没有通过（两次共享现场采样为 708/711 errors，16 warnings）。其中一个本轮类型化暴露的故意坏值 fixture 见下方集成点；不能把所有错误都称为既有或与本轮无关。
- 环境启动器问题：`.venv/bin/pyright` 的 shebang 指向已经不存在的旧 `Documents/GitHub` 路径；改用 `.venv/bin/python -m pyright` 成功运行。未修改环境或安装新工具。

## 结构与性能边界

- 已先用 `python3 -m tools.symbol_locator` 查 `ScheduleRunContext`；该工具按函数索引不识别类名，继而查 `from_legacy_scheduler`、`schedule_internal` 的 callers/callees，读取实际定义完成定位。共享快照标签为 2026-07-20，未刷新公共产物。
- 使用项目现有 AST 提取器，对本轮相关八个源文件做 **内存内局部提取**：绑定 helper 有 **7 个 confident caller**（主轨四个、legacy 三个），`GreedyScheduler._schedule_internal` 仍为 **0 个 confident caller**。类型注解不会恢复现有提取器的 callback 槽 confident 边；未声称 SCIP 或 Jedi 改善已获证明。
- 两种 scope 的 `.venv/bin/python -m tools.scan_import_cycles [--include-tests] --fail-on-new-cycle --quiet-when-clean` 都因共享基线差异返回 1：两组文件环签名、`web.bootstrap.startup_config -> config` 的圈内边；含测试还报告 `test_frozen_bundle_contract.py:198` 的未解析导入。
- 为区分本轮影响，固定读取一次共享源码快照，在内存中仅将本轮两份原本干净的适配文件替换为其 HEAD 内容，并移除本轮新增的一个生产/三个测试模块，与实施后比较；不写文件、不回退现场、不刷新基线。
- 该对照结果：production **799 -> 800**，with-tests **1543 -> 1547**；两个 scope 的 **硬环成员和圈内边完全相同、运行时环成员相同、未解析动态导入相同、解析错误为 0**。这是本轮增量结构证据，不是共享基线门禁通过。
- Python 3.8.10、真实 bound internal callback、14 kwargs 的微基准：暖缓存校验 100000 次最低 **0.056318s / 0.563us 每次**；无缓存 signature+bind 10000 次最低 **0.189898s / 18.990us 每次**。仅为本机 helper 微基准，不能推导优化器端到端耗时回归百分比。

## 主代理集成点与剩余限制

1. 本轮新增生产模块 **+1**、含测试总模块 **+4**。由主代理汇总所有 agent 的最终模块集后统一处理 A3 计数、registry 和调用图/导入环基线；不要直接把本记录某次并发采样值抄成最终 pin。
2. `tests/algorithm/test_greedy_refactor_contract.py:931` 故意把返回 `("M1",)` 的 `bad_probe` 注入 `auto_assign_callback`。运行时坏结果哨兵仍通过，但新增 Protocol 正确拒绝其静态返回类型；主代理可用 `cast(Any, bad_probe)` 显式标识该测试的故意非法注入，不能放宽生产 Protocol 为单元素 tuple。本任务没有该现有测试文件的写权限，未修改。
3. 四槽签名合同不等于所有 callback 正文的正确性证明；自定义 `__signature__` 应准确描述调用合同，内部再次调用其他函数产生的 TypeError 仍按既有正文异常处理。对不可内省 callback，本轮明确拒绝执行，调用方需提供可内省的适配函数。
4. 不执行 `scripts/run_quality_gate.py` 的完整共享证明流程：当前多 agent 持续写入、工作区 dirty，入口会清理/写入共享质量门禁产物，不在本任务独占写集内；同时已实测到共享计数/静态门禁失败。最终由主代理统一集成后跑门禁；此处只有 dirty worktree 的局部与扩大回归证据。
5. 本轮八个文件均留在工作区，未暂存、未提交、未推送；所有禁止写集和他人已有改动均未由本任务编辑。
