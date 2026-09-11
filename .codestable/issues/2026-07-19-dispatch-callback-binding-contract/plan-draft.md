# U03 + U04 实施计划草案：dispatch 透传层签名漂移响亮失败 + callback 槽静态可见性恢复

> 状态：implemented / pending-integration（2026-09-08 已按用户授权实施，专项验证通过；共享门禁与统一提交待主代理）。来源：2026-07-19 debt-recheck-ultra 审计（.codestable/audits/2026-07-19-debt-recheck-ultra/，条目 U03/U04，误杀翻案对）；原草案由 Plan subagent 探索产出、主代理落盘。
> 已批准组合：方案 B（使用点 bind 校验与缓存）+ 方案 C（Protocol 类型化）+ 三方签名合同测试。实际结果与验证限制见同目录 `dispatch-callback-binding-contract-fix-note.md`。

## 2026-09-08 实施覆盖说明

- 下文保留原草案作为历史依据；本节和 fix-note 的实际结果覆盖草案中的未实施状态及不同取舍。
- 按本轮明确要求：无法内省的 callable 在使用点抛 `DispatchContextContractError`，不采用草案的静默跳过。
- 双轨适配及 canonical fallback 都先绑定再执行；只转化内省/绑定错误，不包 callback 正文；`strict_mode` pop 与原有业务异常分类保持不变。
- 签名错误的原始异常保留在 `__cause__`；主错误文案不拼接原始 bind 文本，避免上游旧 wrapper 的关键字消息匹配误触发重试。
- 签名缓存区分 bound/unbound、位置参数数量、关键字集合和 Python 函数绑定元数据；普通 callable 实例、partial、builtin 每次内省，不缓存可变或自定义相等语义。
- 类型声明单独落在获准新增的 `core/algorithm_runtime/dispatch_callback_types.py`；新增 3 个专项测试模块。公共模块计数 pin、基线、registry、台账和共享调用图不在写集内，未修改。
- U04 仅确认新增 7 个 helper confident 调用来源；原 callback 槽仍是静态盲区，不能声称 typed 让 AST confident 边恢复。未做 SCIP 改善或 clean-worktree proof 的承诺。

## 0. 范围与结论先行

- **U03（运行时吞错）**：在 `ScheduleRunContext` 与 `_LegacyDispatchContext` 两条适配轨的 callback 转发点，调用前做 `inspect.signature(...).bind(...)` 校验（带缓存），签名失配 raise `DispatchContextContractError` —— 该异常已被 batch_order/SGS 主循环显式 re-raise（已核实），从而把"代码回归伪装成全工序业务失败"变成响亮失败。**不动 batch_order.py:146-148 的 except 结构，不统一双轨适配层。**
- **U04（静态盲区）**：四个 callback 槽用 `typing.Protocol`（Python 3.8 原生支持）类型化 + 三方签名一致性契约测试。**诚实结论**：`symbol_locator` 的 confident 边由 AST 提取器产生，属性调用（`ctx.schedule_internal(...)`）在现有提取器下**永远是 ambiguous 边**（证据见 §1.6），因此"`ctx.schedule_internal → GreedyScheduler._schedule_internal` 的 confident 边"在不违反 A3 双轨裁决的前提下**不可恢复**；本方案能恢复的是：合同校验链的新增 confident 边（每个转发方法 → 共享 bind 校验 helper）、Pyright/jedi/SCIP 层面的类型可见性、以及测试时的签名漂移锁。

## 1. 调用链现状（全部证据 file:line，基于 2026-07-19 工作区）

### 1.1 主路径

```
GreedyScheduler.schedule
  → scheduler.py:124  ctx = ScheduleRunContext.from_legacy_scheduler(self)
  → scheduler.py:128/431/444  _run_dispatch → dispatch_batch_order / dispatch_sgs
  → batch_order.py:40 / sgs.py:80  ctx = ensure_dispatch_context(context)
  → batch_order.py:130（_dispatch_one 内）或 sgs.py:369（_dispatch_selected 内）→ _schedule_op
  → batch_order.py:186  ctx.schedule_internal(...)   # 15 个 kwargs，全部关键字传参
  → run_context.py:53-58  pop strict_mode → 调 internal_callback
  → scheduler.py:181  GreedyScheduler._schedule_internal（经 run_context.py:33 getattr 接线）
  → scheduler.py:200  schedule_internal_operation(...)
```

- SGS 不直接调 `ctx.schedule_internal`：sgs.py:15 从 batch_order 导入 `_schedule_op`，在 sgs.py:369 调用，与 batch_order 共用同一转发面。
- `ensure_dispatch_context`（dispatch_context.py:64-68）：candidate 具备 5 项能力（`schedule_external / schedule_internal / auto_assign_internal_resources_attempt / increment / log_exception`，dispatch_context.py:65）时**原样返回**；否则包 `_LegacyDispatchContext`。`ScheduleRunContext` 具备全部 5 项（run_context.py:38、41、47、53、76），故主路径直接用它；legacy 轨仅服务于直接调 dispatch 的 scheduler-like 对象（仓内仅测试使用；core/web/data/plugins/desktop/scripts 全仓 sweep 无其他调用方——但**仓外脚本证据不足**，离线交付环境无法证伪）。

### 1.2 真实 kwargs 集合（逐槽）

| 槽 | 生产调用点 | kwargs 集合 |
|---|---|---|
| `schedule_internal` | batch_order.py:186-202（唯一） | 15 个：`op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes, auto_assign_enabled, resource_pool, last_op_type_by_machine, machine_busy_hours, operator_busy_hours, strict_mode`；无位置参数 |
| `schedule_external` | batch_order.py:176-185（唯一） | 8 个：`op, batch, batch_progress, external_group_cache, base_time, errors, end_dt_exclusive, strict_mode` |
| `auto_assign_internal_resources_attempt` | sgs_scoring.py:330-347（13 个，含 `probe_only=True`）；internal_operation.py:122-135（12 个，无 probe_only，经 run_context.py:61 / scheduler.py:203 接线） | `op, batch, batch_progress, machine_timeline, operator_timeline, base_time, end_dt_exclusive, machine_downtimes, resource_pool, last_op_type_by_machine, machine_busy_hours, operator_busy_hours[, probe_only]` |
| `auto_assign_internal_resources` | sgs_scoring.py:348（attempt 槽缺失时的回退） | 同上 13 个 |

### 1.3 适配层转发行为（必须保持的合同）

- **strict_mode pop 不对称**：`ScheduleRunContext.schedule_internal` 在 run_context.py:55 pop `strict_mode`，**不转发**给 internal_callback（契约测试 tests/algorithm/test_greedy_refactor_contract.py:686-744 锁定"无 strict_mode 参数的 legacy callback 必须能被 strict_mode=True 调通"）；strict 校验由适配层的 `_validate_strict_internal_input`（run_context.py:93-96）承担。`_LegacyDispatchContext.schedule_internal` 同形（dispatch_context.py:42-46）。**external 槽相反**：strict_mode 原样透传（run_context.py:47-51，`GreedyScheduler._schedule_external` 接受它，scheduler.py:158-168）。
- **fallback 分支**：无 callback 时，internal 槽 setdefault `calendar/algo_stats/auto_assign_resources` 并回填 strict_mode 后调 canonical `schedule_internal_operation`（run_context.py:59-66；目标签名 internal_operation.py:20-40，keyword-only 无 `**kwargs`）；external fallback 走 `_ScheduleFacade`（run_context.py:51、99-102）；auto-assign fallback 见 run_context.py:81-84。
- **legacy 轨缺 callback 已响亮**：dispatch_context.py:35、41、55 抛 `DispatchContextContractError(TypeError)`（dispatch_context.py:10）。

### 1.4 吞错通道（U03 病灶复现路径）

- batch_order.py:126-149：`_dispatch_one` 的 try 包住 `_schedule_op`；:146-147 `except (ValidationError, DispatchContextContractError): raise`（**核实无误**）；:148 `except Exception` 折算为 `_record_dispatch_exception`（:205-208）继续跑。
- sgs.py:406-408：`_dispatch_selected` 同构——:406-407 re-raise 同两类异常，:408 `except Exception` 折算。
- 因此：run_context.py:58 处 callback 签名失配抛的**普通 TypeError** 落在 try 内 → 被 :148 吞成单工序失败 → 每道工序重复失败 → summary 呈现"全工序业务失败"，无人知道是代码回归。附带同类隐患：strict_mode=True 且 kwargs 缺 `op`/`batch` 时，run_context.py:96 / dispatch_context.py:45 的 `call_kwargs["op"]` 抛 KeyError，同样被吞。
- SGS **评分**路径不在 try 内（sgs.py:217-234 的 `_score_candidates` 直接执行），评分期异常本来就响亮——受影响的只是正式派工转发面。

### 1.5 上游异常处理（波及面关键点）

- 服务层进入 `scheduler.schedule` 全部经 `schedule_with_optional_strict_mode`（schedule_signature_support.py:151-174；调用方 schedule_optimizer.py:61/67/72/149/370/399、schedule_optimizer_steps.py:103/334；另有 optimizer_proof_oracle.py:92 直调）。该 wrapper 在签名探测不可用（返回 None）时用 `except TypeError` 包住 schedule 调用（:164-174）并按消息匹配重试。对 canonical `GreedyScheduler`，`schedule_supports_strict_mode` 返回 True → 走 :159-160 **无 try/except 直调**，`DispatchContextContractError` 干净上抛。残余风险与消息碰撞分析见 §7.3，需一条穿透回归测试。

### 1.6 U04 基线（直接读 `.codestable/checkup/latest/callgraph/edges.json` 实测）

- `GreedyScheduler._schedule_internal`：confident **caller 边 0 条**（仅 1 条 confident callee 边 → `schedule_internal_operation`）；`from_legacy_scheduler` 的 getattr 接线记录在 dynamic_unresolved.json（run_context.py:26 条目）。
- `ScheduleRunContext.schedule_internal`：caller 侧仅 `_schedule_op → …` 的 **AMB attr** 边（同时指向 `_LegacyDispatchContext.schedule_internal` 的孪生 AMB 边）；confident callee 边 2 条（→ schedule_internal_operation [import]、→ _validate_strict_internal_input [local]）；run_context.py:58 的 `self.internal_callback(...)` **零边**（槽是 dataclass 字段非函数定义）。
- **结构性原因**：提取器 `_add_attr_edges`（callgraph_extract.py:171-186）对非 `self` 接收者的属性调用**一律标 ambiguous**（:183-186）；confident 边只产自 bare import 调用（:150-155）、唯一 local（:157-159）、全局唯一裸名（:164-166）、`self.方法`（:181-182）、`导入模块.attr`（:200-212）。提取器不消费类型注解（A3 design §2.7:165 "typed 0"）。**故任何 typing 手段都不能把 attr 调用边变 confident**——这是评估三个方案 U04 恢复程度的判决性事实。

## 2. 必须尊重的裁决（已亲读原文）

1. **双轨 by-design**：A3 design（algorithms-a3-dependency-decoupling-refactor-design.md:137-138）——`ScheduleRunContext` 留在 greedy.run_context 不移动；`ensure_dispatch_context` 只为旧式直接 dispatch 构造 `_LegacyDispatchContext`，不得复制 SGS/时隙估算/自动派工算法。issue（legacy-dispatch-adapter-contract-analysis.md:63-72）方案 C（fallback 下沉统一）被显式否决、方案 B 经用户拍板（"按照你的意见修吧"）。→ 本计划**不合并两个类**，只共享叶子级校验 helper——先例：`validate_internal_hours_for_mode` 已被双轨共享（run_context.py:8、dispatch_context.py:7）。
2. **except 结构不许动**：2026-06-24 深审 F-10 + 上述 issue（audit index.md:41 注记"修法在透传层加签名校验响亮失败，不动 except 本身"）。→ 本计划对 batch_order.py / sgs.py 的生产代码**零改动**。
3. **先例扩展**：A3 apply-notes 复审后修正（apply-notes.md:97-104）已把"缺 callback 的 TypeError 被主循环折算"判为缺陷并造 `DispatchContextContractError` 在能力使用点响亮抛（fix-note.md:17-23 "能力按需 fail-loud"，构造期全量校验曾致 7 个回归被撤回）。本次是把该先例从"缺 callback"扩展到"签名漂移"，异常类型复用同一个（这也是唯一能穿过 :146-147 re-raise 白名单的类型——白名单本身不许扩）。
4. **冻结项**：`GreedyScheduler` 构造/schedule/覆写语义不变（design §2.4:126；覆写合同由 test_greedy_refactor_contract.py:40-90 锁定 getattr 接线）；`ensure_run_context`（run_context.py:87-90）零调用是验收终态不许删（audit index.md:35 条目 3）；monkeypatch 合同（design §2.5:134-139）；根 `__init__` SHA 与模块数 pin（test_algorithms_a3_dependency_boundary.py:19、390-391）。

## 3. 设计方案

### 方案 A：`schedule_internal` 改显式签名（枚举 15 个真实参数）

做法：两轨适配方法都改成显式 keyword-only 签名，逐名转发（internal 槽显式不转 strict_mode）。

- **U03 修复度：不达标**。两个失配面都救不了：(i) dispatch→适配层失配的 TypeError 在 `ctx.schedule_internal(...)` 调用点抛出，而该调用点**词法上在 `_dispatch_one` 的 try 内**（batch_order.py:126-141）——"失配发生在 except 之外"在不动 except 结构的裁决下无法成立；(ii) 适配层→callback 失配仍在适配器体内抛普通 TypeError，同样被吞。若用 `except TypeError → ContractError` 包裹 callback 调用来补救，会把 **callback 体内**的真 TypeError（业务/数据缺陷，现按工序折算——test_batch_order_bid_unboundlocal.py:150-189 锁定体内异常折算合同）误转成全局中止，反向误杀。
- **行为兼容风险**：显式签名带默认值会**合成调用方从未传入的 kwargs**——loose callback（`**kwargs`）今天只收到实际传入的键，改后收到全量 14 键（值为默认 None），"键缺席 vs 值为 None"语义漂移；不带默认值则杀伤走部分 kwargs 的奇异直调（仓内无此调用方，仓外证据不足）。
- **U04 恢复度**：confident 边恢复 **0**（§1.6 判决性事实）；仅可读性与 IDE 提示提升。
- **结论：不推荐单独采用**；其"防调用点漂移"价值改由契约测试承接（见方案组合）。

### 方案 B：透传保留 + 调用前签名 bind 校验（推荐主干）

做法：新增共享 helper（放 `core/algorithm_runtime/dispatch_context.py`，与 `DispatchContextContractError` 同居；**不新增模块**，避开 test_algorithms_a3_dependency_boundary.py:390-391 的 779/1475 模块数 pin）：

```python
def check_dispatch_callback_binding(callback, kwargs, *, slot: str) -> None:
    # 缓存键：getattr(callback, "__func__", callback)（绑定方法解包到底层函数，
    # 跨实例/跨排产轮次命中；不可哈希 → 不缓存），仿 schedule_signature_support.py:13-19 先例
    # 已验证 (func, frozenset(kwargs)) 直接返回
    # inspect.signature 抛 (TypeError, ValueError) → 跳过校验（行为与今天完全一致,不误杀 C 可调用/奇异对象）
    # sig.bind(**kwargs) 抛 TypeError → raise DispatchContextContractError(f"dispatch callback 签名失配（{slot}）：{exc}")
```

接线点（每个真实调用的前一行）：
- `ScheduleRunContext`：schedule_internal 的 callback 分支（run_context.py:58 前，用 pop 后的 call_kwargs）与 fallback 分支（run_context.py:63 前，用 setdefault 增补后的最终 kwargs 对 `schedule_internal_operation` 校验）；schedule_external 两分支（:49、:51）；两个 auto-assign 槽（:70、:78、:80、:84）。
- `_LegacyDispatchContext`：schedule_external（dispatch_context.py:36 前）、schedule_internal（:46 前）、auto_assign（:51、:54 前）。
- 微加固：strict_mode=True 且 call_kwargs 缺 `op`/`batch` 时 raise ContractError（替换 run_context.py:96 / dispatch_context.py:45 的裸 KeyError 隐患）。

评估：
- **U03 修复度：完整且零误杀**（by construction）：bind 成功 ⟺ 实际调用能绑定，故所有今天能跑通的合法调用（含 `*args/**kwargs` loose callback、缺 strict_mode 的 keyword-only callback、子类覆写 `**kwargs`）绝不被拦；所有今天会抛绑定 TypeError 被吞的调用改为响亮 ContractError；**callback 体内异常完全不经过本机制**（bind 不执行函数体），F-10 折算合同原样保留。
- **A3 兼容性：好**。双轨各自保留自己的方法体，只共享叶子 helper（同 `validate_internal_hours_for_mode` 先例）；`run_context → dispatch_context` 新增 import 边方向为 greedy→algorithm_runtime（合法方向，dispatch_context.py:5-7 无反向依赖，不成环）。
- **调用方波及：零**——batch_order.py / sgs.py 生产代码一行不改。
- **U04 恢复度：部分**。新增 confident 边：`ScheduleRunContext.{4 个转发方法} → check_dispatch_callback_binding`（import 类 confident）+ `_LegacyDispatchContext.{3 个转发方法} → 同 helper`（同文件 local 类 confident），合同校验链成为 symbol_locator 可查的静态锚点（`callers check_dispatch_callback_binding` 确信列出全部转发点）；槽位本身仍盲。dynamic_unresolved 不增（提取器只把 `getattr/__import__/import_module` 记动态，callgraph_call_sites.py:87-88；`inspect.signature` 非首方目标不产边不产噪）。

### 方案 C：callback 槽 typing.Protocol 类型化（推荐配套）

做法：在 dispatch_context.py 定义 4 个 Protocol（仓内已有 Protocol 使用先例：core/services/scheduler/run/schedule_optimizer_steps.py:37 等；pyrightconfig.json:38-39 `pythonVersion 3.8 / basic` 且 include 覆盖 tests）：

- `InternalScheduleCallback.__call__`：**不含 strict_mode**（pop 合同，§1.3）——14 个 keyword-only 参数，返回 `Tuple[Optional[ScheduleResult], bool]`；
- `ExternalScheduleCallback.__call__`：8 参数**含 strict_mode**；
- `AutoAssignAttemptCallback` / `AutoAssignCallback`：13 参数含 `probe_only: bool = False`。

run_context.py:20-23 四个槽从 `Optional[Callable[..., Any]]` 改为 `Optional[<对应 Protocol>]`。可选加码：定义 `DispatchContextLike` Protocol（5 能力 + calendar + auto_assign_internal_resources，覆盖 sgs_scoring.py:345-348、:365 的实际使用面），注解 `ensure_dispatch_context` 返回值；`batch_order/sgs` 的 `ctx: Any` 参数注解替换列为**独立可回退子步**（它会触碰 batch_order.py——只改注解不改逻辑、不碰 :146-148，若 Pyright basic 产生摩擦则回退 `Any`）。

评估：
- **U03**：无运行时效果，单独不修。
- **U04 恢复度**：symbol_locator confident 边恢复 **0**（提取器不读注解，§1.6）；实际收益在 (i) Pyright 门禁——测试直构 `ScheduleRunContext(internal_callback=...)` 处的 Protocol 一致性检查（getattr 接线处为 Any，不受检，如实声明）；(ii) jedi（`whereis --at`）与 SCIP `--deep` 深查询预期改善——**证据不足**：issue analysis（legacy-dispatch-adapter-contract-analysis.md:22）记录过 SCIP 对 A3 新符号 callers/callees 未解析，改善幅度以实测为准，不写包票。
- **风险**：dead-code 门禁 quick 模式对鸭子接口/Protocol stub 已知误报（attention.md"命令与脚本陷阱"明文警告）——若 Protocol `__call__` stub 被报"新增疑似死代码"，按 attention.md 用 `--mode quick --refresh` 刷基线，勿删。

### 推荐：B（主干）+ C（配套）+ A 的价值由契约测试承接

- 方案 A 的"防三方漂移"用测试实现：AST 解析 batch_order.py 中 `_schedule_op` 两个调用的 keyword 名集合（boundary 测试文件已 import ast，:4，有同类手法先例），断言 = 冻结清单 = Protocol 参数名 = `inspect.signature().bind` 能绑定到 `GreedyScheduler` 四个 callback 方法与 canonical fallback（`schedule_internal_operation` / `external_groups.schedule_external` / `auto_assign_internal_resources_attempt`）。任何一方漂移 → 测试红灯，而非运行时静默。
- 覆盖范围决策：bind 校验四个槽全上（internal/external/auto-assign×2、双轨、含 fallback 分支）——同一 helper、边际代码极小；auto-assign 槽在 SGS 评分热路径上的成本由缓存摊平（§7.1）。

## 4. 分步实施（每步先红后绿，绿灯后进下一步）

**S1 helper 落地（dispatch_context.py）**
新增 `check_dispatch_callback_binding` + 两级缓存 + `clear_dispatch_callback_binding_cache_for_tests()`（镜像 schedule_signature_support.py:22-24 惯例）。
测试：helper 单元——loose/keyword-only/positional-or-keyword 可调对象绑定通过；缺参/多参 raise ContractError 且消息含槽名与原始 bind 错误文本；不可内省对象跳过；同一 `__func__` 只 `inspect.signature` 一次（mock 计数，仿 test_schedule_optimizer_strict_mode_signature_cache.py 手法）；clear 后重查。
验证：新测试 + `pytest tests/algorithm/test_algorithms_a3_dependency_boundary.py`。

**S2 legacy 轨接线（dispatch_context.py 三个转发方法 + strict 缺 op/batch 守卫）**
测试（先红）：legacy candidate `_schedule_internal` 签名漂移（keyword-only 缺一参且无 `**kwargs`）经 `dispatch_batch_order` → ContractError 而非折算；strict + 缺 op kwarg → ContractError 非 KeyError；既有 :300/:333/:357 三条合同保持绿。
验证：`pytest tests/algorithm/test_algorithms_a3_dependency_boundary.py tests/algorithm/test_greedy_refactor_contract.py`。

**S3 主轨接线（run_context.py 四个槽、callback 与 fallback 双分支）**
测试（先红）：
- T1/T2：内部槽漂移 callback 经 `dispatch_batch_order` 与 `dispatch_sgs` 均 ContractError 上抛（验证 sgs.py:406-407 透传）；
- T4：外部槽漂移同形（外部槽真实收紧：合法 callback 都含 strict_mode，scheduler.py:158-168，只有已坏调用受影响）；
- T5：无 callback 的 fallback 分支多传/缺传 kwarg → ContractError（今天是被吞的 TypeError）；
- T7（防过度转化）：callback **体内** raise TypeError("boom") → 仍按工序折算继续跑（扩展 test_batch_order_bid_unboundlocal.py:144-189 的 RuntimeError 用例到 TypeError）；
- T12：auto-assign attempt 槽 12/13 kwargs 两形态 + scoring 路径（probe_only=True，不在 try 内）行为核对；
- 全量既有合同回归：test_greedy_refactor_contract.py:633（strict 先于 callback 抛 ValidationError）、:686（strict pop 兼容）、:40（子类覆写）、test_internal_slot_estimator_consistency.py:100/275（**位置传参直调** `scheduler._schedule_internal`——本计划不改 scheduler.py，必须保持绿）、test_dispatch_blocking_consistency.py、tests/schedule/route_view/test_scheduler_missing_resource_message.py。

**S4 上游穿透回归**
测试 T9：在 `schedule()` 体内抛 ContractError，断言穿过 `schedule_with_optional_strict_mode` 原样上抛且**不触发重试**——两个形态：可内省 scheduler（走 :159-160 无 except 路径）与不可内省 scheduler（走 :164-174 except TypeError 路径，验证消息不撞 `is_unexpected_strict_mode_type_error`/readiness/graph 匹配，见 §7.3）。

**S5 Protocol 类型化（U04）**
dispatch_context.py 加 4 个 Protocol（+可选 `DispatchContextLike`）；run_context.py:20-23 槽改型；契约测试 T11（三方签名一致，AST + bind + Protocol 参数名比对）。可选子步：`ensure_dispatch_context` 返回注解与 `ctx` 参数注解（摩擦即回退）。
验证：Pyright 全仓 0 errors（既有 15 条 scheduler `__all__` warning 为基线，apply-notes.md:86）；Ruff；Python 3.8 语法扫描（apply-notes.md:87 曾抓 `set[str]`——用 `typing.Dict/FrozenSet` 等 3.8 写法）；dead-code quick 若报 Protocol stub 按 attention.md 刷基线。

**S6 结构门禁与全量回归**
- `tools.scan_import_cycles --fail-on-new-cycle` 双 scope（run_context→dispatch_context 新边不成环，A3 SCC 不回潮——design §2.6 硬约束）；
- 完整 `pytest tests/algorithm` + route_view + gate_meta/test_callgraph_receiver_resolution.py；
- 模块数 pin 协调：本计划生产侧**零新模块**（全部进既有文件）；新测试若开独立文件会 +1 with-tests 计数——与本轮已落地的新测试文件一起，pin（test_algorithms_a3_dependency_boundary.py:390-391 的 779/1475）需一次改对；若想少动 pin，可把新测试并入既有 test_algorithms_a3_dependency_boundary.py / test_greedy_refactor_contract.py。

**S7 事实与证据收尾**
- 按 A3 apply-notes 纪律刷 `.codestable/checkup/latest/callgraph`（需一并解释全部边差异：预期新增 = 转发方法 → helper 的 confident 边 + helper 自身 callable；预期不变 = dynamic_unresolved 中 run_context/dispatch_context 条目数）；
- **symbol_locator 终验**（`python3 -m tools.symbol_locator`）：
  - `callers check_dispatch_callback_binding` → 确信列出 7-9 个转发方法（新增静态锚点，PASS 判据）；
  - `callees schedule_internal` → 既有 confident 边保留 + 新增 → helper；
  - `callers _schedule_internal` → **预期仍 0 confident**——终验记录明写"by-design 残留：attr 边 ambiguous 是提取器结构性行为（callgraph_extract.py:183-186），getattr 接线是 A3/覆写合同冻结项"；提取器注解感知增强另立 tooling 项（本次不做）；
  - `--deep`（SCIP，先 `build-index`）实测 Protocol 后的解析改善，如实记录（可能仍不解析，有先例）。
- 完整质量门禁 `scripts/run_quality_gate.py`（dirty 诊断 → 用户授权提交后 clean proof）。

## 5. 测试策略汇总

**误杀哨兵（既有测试必须保持绿）**：
- tests/algorithm/test_internal_slot_estimator_consistency.py:100、275（位置传参直调 `_schedule_internal`）
- tests/algorithm/test_greedy_refactor_contract.py:40-90（子类覆写）、:583-630（legacy loop）、:633-683（strict 先于 callback）、:686-744（strict pop 兼容）、:747+（无 callback fallback）、:924-945（auto_assign bad probe）
- tests/algorithm/test_algorithms_a3_dependency_boundary.py:282-383（legacy strict + 缺 callback fail-loud——本次先例的锚测试）
- tests/algorithm/test_batch_order_bid_unboundlocal.py:105-189（体内异常折算合同）
- tests/algorithm/test_dispatch_blocking_consistency.py、test_sgs_pre_sort_strict_nonfinite_rejected.py、test_sgs_penalize_nonfinite_proc_hours.py、test_sgs_atc_penalize_missing_resources.py（评分期响亮合同）
- tests/schedule/route_view/test_scheduler_missing_resource_message.py:113-170（fallback auto-assign）
- tests/algorithm/test_schedule_optimizer_strict_mode_signature_cache.py（上游 wrapper 合同，T9 宿主区）

**新增契约测试（T1-T12 核心断言口径）**：签名漂移必须响亮（ContractError + 不产生 dispatch_operation_exception failure_detail + run 中止）；ContractError 透传不被吞（batch_order.py:146-147 与 sgs.py:406-407 各一条）；体内 TypeError 仍折算（反向护栏）；三方签名一致契约（T11）；上游 wrapper 穿透（T9）；缓存单次 inspect（T10）。

## 6. U04 恢复程度总评

| 维度 | 方案A | 方案B | 方案C | 推荐组合 |
|---|---|---|---|---|
| symbol_locator confident 边 | 0 恢复 | 新增合同锚点边 7-9 条；槽边仍盲 | 0 恢复（提取器不读注解） | 同 B；槽边不可恢复为**结构性事实**，终验留档 |
| Pyright/jedi/SCIP | 小幅 | 无 | 主要收益（SCIP 幅度证据不足，实测） | C 承担 |
| 运行时签名漂移 | 仍被吞 | 响亮（零误杀） | 无 | B 承担 |
| A3 双轨裁决 | 兼容但改签名有奇异调用风险 | 兼容（叶子共享先例） | 兼容（合同层） | 兼容 |
| batch_order/sgs 波及 | 无 | **零改动** | 仅可选注解子步 | 近零 |

## 7. 风险与缓解

### 7.1 性能（派工主循环每工序一次）
- 成本模型：暖缓存后每次转发 = `frozenset(kwargs)` 构造 + 一次 set 查询（亚微秒级）；冷路径每 `(底层函数, 键集)` 一次 `inspect.signature`（数十微秒，进程级缓存，跨排产轮次/跨实例命中——`__func__` 解包使所有 `GreedyScheduler` 实例共享条目，对优化器多候选反复 `schedule()` 尤其重要，schedule_optimizer.py:149 等）。10 万工序量级预计总开销 <0.1s。
- 热点：SGS 评分期 auto-assign attempt 槽为 O(候选×迭代) 调用（sgs_scoring.py:330-348）——同缓存覆盖；若实测超预算（判据：optimizer benchmark light ratchet 或 tests/algorithm 总时长回归 >2%），降级方案已备：auto-assign 槽退化为"每 context 每槽首调校验一次"，internal/external 槽保持全量校验。
- 明确不用每次调用裸 `inspect.signature`（太贵），缓存是方案组成部分而非可选项。

### 7.2 行为兼容（误杀零容忍）
- bind 校验的数学性质：bind 通过 ⟺ 真实调用可绑定——所有现网合法调用形态（§5 哨兵清单 + loose/keyword-only/子类覆写/位置直调）不可能被误杀；唯一新增拒绝是"strict 且缺 op/batch"（今天是被吞的 KeyError，无合法调用方触发：batch_order.py:187-188 恒传两者）。
- 不可内省可调用对象跳过校验 → 行为与今天逐字节一致（代价是这类对象的漂移仍走旧通道，测试 T8 锁定）。
- 外部槽收紧点（缺 strict_mode 的 legacy external callback 从"静默折算"变响亮）：仓内无此形态调用方；仓外证据不足，在 fix-note 中作为边界声明留档。

### 7.3 ContractError 是 TypeError 子类的上游碰撞
- 已排查唯一 `except TypeError` 拦截点：schedule_signature_support.py:164-174（仅签名不可内省的 scheduler 走到）。误吞条件需消息同时含 `"unexpected keyword argument"` 与 `strict_mode/readiness_gate_enabled/graph_ready_context` 之一且后两者在 schedule 层 kwargs 中（:100、:110 守卫）——internal 槽 bind 前已 pop strict_mode，绑定错误消息不可能提及它；readiness/graph 两键不流入 dispatch 层。碰撞实际不可达，但用 T9 两形态回归测试锁死，不靠推理。
- 其余 `except (TypeError, ValueError)` 均在无关数据解析路径，不在本调用链上。

### 7.4 结构与工具链
- import 环：run_context→dispatch_context 单向新边，`--fail-on-new-cycle` 双 scope 把关；A3 SCC 数字不许回潮（design §2.6:150-157）。
- 模块数/根 SHA pin 与本轮其他改动的并行落地冲突（§4 S6 协调项）。
- 调用图事实刷新必须逐边解释（apply-notes.md:97-104 复审纪律）。
- dead-code quick 对 Protocol stub 误报 → attention.md 处方处理。

## 8. 证据不足清单（如实声明）

1. 仓外/离线交付现场是否存在直调 `dispatch_batch_order/dispatch_sgs` 或适配器方法的脚本——仓内全 sweep 为空，仓外不可证。
2. Protocol 化后 SCIP `--deep` 的解析改善幅度——有"曾不解析 A3 新符号"的反向先例（analysis.md:22），只能实测。
3. 性能预算的量化上限——无现成派工路径微基准，估算为分析值，以 ratchet/全量测试时长回归实测裁决。
4. 典型现场工序规模——按 10 万工序量级保守估算。

## 关键文件

- core/algorithm_runtime/dispatch_context.py（bind 校验 helper + 4 个 Protocol + legacy 轨接线落点）
- core/algorithms/greedy/run_context.py（主轨四槽接线 + 槽类型化，U03/U04 病灶本体）
- core/algorithms/greedy/dispatch/batch_order.py（唯一转发调用点与不许动的 except 结构，`_schedule_op` 是 kwargs 合同的单一真相源）
- tests/algorithm/test_algorithms_a3_dependency_boundary.py（先例锚测试 + 模块数 pin，新契约测试首选宿主）
- tests/algorithm/test_greedy_refactor_contract.py（strict pop / 覆写 / fallback 行为合同，误杀哨兵）
