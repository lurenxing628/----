# 红队第1轮第1号 — 脑内执行者视角(只读不改)

> 视角:把 PHASE4-SAFE-BATCH-PLAN.md 当明天的执行指令,从 ROOT 逐批跑到 Batch-D。每批问:前批改过谁、行号漂没漂、前置安全网真绿了吗、哪批做到一半发现缺前置。
> 纪律:行号一律 rg 回盘,权威路径以 _layer2_residual.md 为准。下列均为已回盘的真问题。

## 摘要

发现 7 个问题(2 硬伤 P0 级影响可执行性,3 中,2 低)。核心硬伤:GF1 这个被全计划当"现有前置门"的 `reject_integer_float` 参数在代码里根本不存在,ROOT 这批从第一步就缺前置;R52 的 impl 文件路径在计划里丢了 package 前缀,执行者会删错文件。

---

## P0-1 [ROOT/GF1, Batch-B/G19·G20] GF1 是"待新建参数"被当成"现有前置门",ROOT 第一步即缺前置

**问题**:计划全程把 GF1(`reject_integer_float`,§1.0/§1.1/§0.2 称"非债前置门,默认 False,加在 strict_parse:46 经 :81 透传")当作**已存在、只需确认默认值**的承重门,门控 G19(R04)/G20(R59)。

**为什么会炸**:全仓 rg 零命中——
- `rg -ni reject_integer_float` 全仓(含非 py)0 行;
- 真符号 `core/shared/strict_parse.py:81 def parse_required_int(value, *, field, min_value)` 签名里**无任何 float 拒绝参数**,也无 `:46`(该文件 `parse_required_int` 在 `:81`,计划锚点 `:46/:81` 都漂);
- `core/services/common/strict_parse.py` 同样无该参数。

GF1 实际是**要新建的一个参数 + 透传链 + parity**,不是"确认默认值"。这撞计划自己的铁律 3「P5 收口到已存在点、绝不新建模块」的精神;更要命的是 ROOT 是"纯增量零结构"批,新增一个改变 `parse_required_int` 行为的参数**不是纯增量**,而 G19(R04)/G20(R59) 都硬依赖 GF1 先绿。脑内执行 ROOT 第一步 `GF1 必默认 False + 自带 parity` 时就会发现:没有这个参数可改,parity 无锚点。

**修正建议**:GF1 须从"承重门确认"重新定性为"新建受控参数"独立单元,显式登记 ①新建 `parse_required_int(..., reject_integer_float=False)` 落点(`core/shared/strict_parse.py:81`)+ ②`core/services/common/strict_parse.py` 是否同步 + ③8 处 algorithms 调用方(sgs_graph 等)的 `parse_required_int` 调用确认默认 False 不回归。锚点 `strict_parse:46` 全部纠为实盘 `:81`。在 owner 表补一条"GF1 新建参数是否违铁律 3"。

## P0-2 [Batch-B/G39·§2 R52] ready_queue impl 文件路径丢 package 前缀,会删错壳/impl

**问题**:§2 R52 写「裸删 impl `ready_queue.py:103`→R25 垫片 `:9 import` ImportError」,§1.0/RK18 同样只写裸 `ready_queue.py`,无 package 前缀。

**为什么会炸**:仓里有**两个** ready_queue.py:
- impl(真删点):`core/algorithms/greedy/dispatch/ready_queue.py:103 def get_ready_operation_ids`,`__all__:138`;
- 壳(R25 垫片,4 行 re-export):`core/services/scheduler/graph/ready_queue.py:9 from core.algorithms.greedy.dispatch.ready_queue import ...`。

测试 `tests/scheduler_graph/test_ready_queue.py:7` import 的却是 `core.algorithms.greedy.dispatch.sgs_graph`,`:16` import `core.algorithms.greedy.dispatch.ready_queue`(直连 impl,不走壳)。执行者照裸 `ready_queue.py:103` 删,可能删到 services 壳(只有 11 行,`:103` 越界)或在错文件上找 `:103`,Edit old_string 必失配;删对 impl 后 services 壳的 `:9 import` 才 ImportError(RK18 描述的方向对,但锚点指错文件)。

**修正建议**:§2/§1.0/RK18 的 R52 impl 锚点全部补全为 `core/algorithms/greedy/dispatch/ready_queue.py:103`,R25 垫片明确为 `core/services/scheduler/graph/ready_queue.py:9`。「同提交退 lazy_runtime:27+metrics_topology:140」前先确认这两处真引壳路径。

---

## P1-3 [Batch-C/G01·§2 R42] :92(dashboard)与 :191(collar)两个不同文件的行号挤在一句,执行者易混

**问题**:R42 安全路径反复写「删点清单 MUST 补 `dashboard_workbench_context.py:92` 与 `:191` 形参同提交」,把 `:92` 和 `:191` 并列在一句里,像同一文件两行。

**为什么会炸**:实盘 `web/viewmodels/dashboard_workbench_context.py` **只有 136 行**,`:92` 是 `"plan_id": _filter_or_none(...)`(在 `_context_kwargs:84` 字典里,经 `:119-120 build_workbench_plan_context(**_context_kwargs(...))` 的 `**` 展开流入——爆点 #21 这部分**核对准确**)。但 `:191` 是 **collar `web/viewmodels/scheduler_workbench_links.py:191`** 的 `plan_id` 形参,跨文件。两者并列叙述,执行者按 `:191` 去 dashboard 文件删会越界失配。爆点本身真实,叙述锚点跨文件未点名是隐患。

**修正建议**:R42 删点清单显式分两行:`scheduler_workbench_links.py:191`(collar 形参删)+ `dashboard_workbench_context.py:92`(`**kwargs` 真流入键,删形参后此处会 TypeError)。两者是"删形参/被展开命中"的因果对,不是同文件两行。

## P1-4 [全局·§0.3/§2/§3] collar 真符号路径与计划自述不一致(D2 已埋但正文多处仍按旧)

**问题**:§2 R42/R54 与 §0.3 称 collar 为 `scheduler_workbench_links.py:187`,但未在多数引用处带 `web/viewmodels/` 前缀;_layer2_residual D2 已注明真符号在 viewmodels 且多以别名 `n` import。

**为什么会炸**:实盘 `web/viewmodels/scheduler_workbench_links.py:187 def build_workbench_plan_context`。计划正文裸写 `scheduler_workbench_links.py` 时,与 `scheduler_navigation_publish.py`(在 `web/routes/domains/scheduler/`)等同名易混的 web 文件并列,co-change grep 若不带 viewmodels 前缀 + 不查别名 `n(`,会漏 reports_workbench/gantt_task_detail/navigation_links 的别名调用点(D2 风险)。这是低概率但 D2 已点名的真隐患。

**修正建议**:正文所有 collar 引用统一带 `web/viewmodels/scheduler_workbench_links.py` 前缀;R42/R54 的 co-change 纪律(查 `build_workbench_plan_context` + 别名 `n(`)从 D2 脚注提升到 G01/G04 前置安全网正文。

## P1-5 [ROOT→Batch-B/C 串行] R01 先删致 R04/R19 收口面行号系统性下移,但"删后重 rg"只在个别处点名

**问题**:计划多处声明「R01 先删 `_iter:67-87` 缩 R04 收口面 6→5」「R20 改 :52 与 R17 串行(R17 删 :12 后 :52 上移重 rg)」,但 G19/G08/G39 这些同文件多债簇,只在部分锚点写了"重 rg",未给统一的"每删一处即对全部下游锚点重 rg"硬纪律。

**为什么会炸**:脑内执行到 Batch-B 时,ROOT 已对若干承重文件**插入了注释行**(LB01 两处/LB02 五硬钉/LB07 两栈),这些插入使**所有**后续删点行号下移,而非只有同簇删点。例如 G07a 在 LB01 锚符号上方插注释后,R17 删 `service:12`/`support:81` 的 `:81` 必下移;R20 的 `:52` 受 R17 + ROOT 注释双重位移。计划虽有全文纪律 1(按符号 rg),但批次正文里"删 :81 非 :80 活键"这类**裸行号断言**仍在,执行者一旦信旧值即误删相邻活键。

**修正建议**:把"ROOT 注释插入会令同文件所有删点下移"显式写进 Batch-B/C 前置;所有"删 :NN 非 :MM"的活/死键区分改为"按 `<符号名/键名>` rg 定位",删除裸行号断言(尤其 R17 `:81 vs :80`、R09 收编面、R47 死活参 8 处逐字相同处)。

---

## P2-6 [Batch-C/G22·§2 R09] STRICT-4 误删风险已坐实但 family 对照表未在正文给全 9+ 锚点

**问题**:计划反复警告"全仓 9+ 同名异义 `_positive_int` 极易误删 STRICT 当重复",但正文只点名 STRICT-4(scope:9/feedback_support:161/public_errors:167/auto_assign:114)与 Optional-5,未在 G22 正文给完整 grep 锚点清单。

**为什么会炸(已回盘)**:`rg "def _positive_int"` 实盘命中——Optional `-> Optional[int]`:`scheduler_resource_dispatch_execution_context.py:28`、`scheduler_resource_dispatch_execution.py(viewmodel):33`、`operation_execution_scope_read.py:21`、`resource_dispatch_execution_service.py:24`、`schedule_persistence_errors.py:13`;STRICT `-> int`:`scheduler_public_errors.py:167`、`auto_assign_resource_errors.py:114`、`scope.py:9`(+`feedback_support:161`)。另有 `_positive_int_set` ×3、`_positive_int_text` ×1、data_contract `_positive_int(value, field_name)` 同名异签。**12 处同前缀**,RK03 真实。计划口径正确,只是正文未把这 12 处一次列清,执行者临场 grep 易漏判返回类型。

**修正建议**:G22 正文嵌入 family 对照实盘表(12 处 file:line + 返回类型 + STRICT/Optional/Set/Text 分类),收编动作前先逐行核 `-> Optional[int]` 才动,杜绝按裸 `_positive_int` 全局替换。

## P2-7 [Batch-B/G30·§2 R34] repoint 目标存在(C1 校正成立),无硬伤,登记为已核

**问题/核对**:R34 纯删依赖 repoint 目标 `get_plan_time_span_for_resolution:210` 存在。实盘 `core/services/scheduler/schedule_plan_query_service.py:210 def get_plan_time_span_for_resolution` ✅。C1 校正(目标存在、降纯删)成立,此处**无问题**,仅登记已核,供对账。

---

## 总结(脑内逐批结论)

- **ROOT 这批做到第一步就缺前置**:GF1 参数不存在(P0-1),整批"纯增量零结构"前提对 GF1 不成立。
- **Batch-B 的 R52 会删错文件**(P0-2 路径丢前缀)、同文件串行删点的裸行号断言会让人误删活键(P1-5)。
- **Batch-C 身份族**爆点核对总体准确(#21 的 dashboard:92 经 `**kwargs` 流入已实盘验证),问题在叙述把跨文件行号挤一句(P1-3)+ collar 前缀不统一(P1-4)。
- STRICT-4 误删风险(P2-6)真实且口径正确,补全 family 表即可闭合。
- R34/R09 收口点/Optional 副本/ready_queue 双文件等结构性判断均与代码对得上。

主病不是分析错,是**几个被当"现状"的前置(GF1)其实是待建动作**,加上**路径/行号在正文裸写**,执行者照搬会在 ROOT 第一步和 Batch-B 删点上撞墙。
