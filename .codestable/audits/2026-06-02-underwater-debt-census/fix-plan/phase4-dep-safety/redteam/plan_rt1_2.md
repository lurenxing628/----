# 红队第1轮第2号 · 依赖反序猎手回盘

> 视角：批间依赖反序 / 缺前置。把 PHASE4-SAFE-BATCH-PLAN.md 当明日执行指令逐批跑，专攻 13 条 H 硬边对照批次序、facade 删序、parity 先于收敛、承重注释先于同文件改动。只读不改，行号 rg 回盘，权威路径以 _layer2_residual.md 为准。

## 0. 结论速览

13 条 H 硬边（E01/E02/E03/E05/E06/E07/E08/E09/E12/E13/E16部分/E26注释面/GF1两门）**逐条对照批次序后，批次拓扑方向全部正确，无依赖反序硬伤**：facade 三桶（R29/R33/R52）确在 Batch-C/B，R26 确在 Batch-D 最晚；parity（R22/R54/GF1）确在 ROOT 先于 Batch-C 收敛；承重注释（LB01/LB03/G07a/G33a/G15a/G40a）确在 ROOT 先于同文件删改批。**但发现 4 个会致执行期踩空/混淆的问题**（1 个中、3 个低），均为「锚点/措辞」层面而非「批次序」层面——批次顺序本身是对的，是执行者照着找文件/找符号时会踩空。

## 1. 逐条发现

### 问题1（中）· collar 真实路径全文写错宿主目录 —— 不是反序，是 E03/爆点#1 执行时找不到文件
- **批次/债**：ROOT collar 扩产前置 + Batch-C/G04（R54）+ G01（R42），E03 硬边的 co-change 主体。
- **为什么会踩空**：计划权威路径表、§3.2、爆点#1、爆点#21、E03 全文反复把 collar `build_workbench_plan_context` 标在 `web/routes/domains/scheduler/scheduler_workbench_links.py`。实盘只存在于 **`web/viewmodels/scheduler_workbench_links.py:187`**（`routes/domains/scheduler/` 下只有 `scheduler_analysis_links.py`，无 workbench_links）。`dashboard_workbench_context.py` 同理在 `web/viewmodels/` 而非 routes。明天照路径表去 routes/domains 扩 collar 会找不到文件，或误以为另有一份。
- **不是反序**：E03「R54 先扩产→R42 后 rebase」方向正确；爆点#1「collar 当前不产 3 键」已实盘证实（grep `is_comparison|is_superseded|is_current_executable|plan_resolution` 在该文件**零命中**，`plan_id:191` 形参在）。问题只在宿主目录写错。
- **修正建议**：在 _layer2_residual.md 权威路径表补一行 `scheduler_workbench_links.py → web/viewmodels/`（与已订正的 4 处前缀错同级），并把计划内所有 `routes/domains/scheduler/scheduler_workbench_links` 引用纠到 `viewmodels/`。这是 D1 同类「prose 改了表没同步」残瑕的第 5 处。

### 问题2（低）· GF1 是「新增参数」不是「改默认值」，措辞自相矛盾且 E01/E02 source 性质需澄清
- **批次/债**：ROOT/GF1（reject_integer_float），E01→G19(R04) / E02→G20(R59) 两条 H 边的共同 source。
- **为什么会混淆**：`reject_integer_float` 全仓（core/web/tests）**零命中**——它当前不存在。strict_parse.py 只有 `parse_required_int:81`，无此参数、无 `:46` 锚点。计划写「加在 `strict_parse:46` 经 `:81` 透传」「必默认 False」，但 :46 无对应符号，且「默认 False」暗示参数已存在只是定默认值。实为「ROOT 须先新增该 kwarg 并默认 False」。这与「ROOT 纯增量零结构」自洽（加参数+默认 False=纯增量），但执行者可能去找一个不存在的现有参数改默认值而卡住。
- **不是反序**：E01/E02 方向（GF1 先绿→R04/R59 后收口）正确，GF1 作为零入边纯 source 也对。
- **修正建议**：把 GF1 措辞改为「ROOT 在 strict_parse 新增 `reject_integer_float: bool = False` kwarg（按符号 rg 定 `parse_required_int` 真实行，弃 :46 锚点）+ 自带 parity」，明确是新增非改默认。

### 问题3（低）· R52 R25 垫片删序锚点 —— 「:9 import」实盘坐实，但须确认是 graph/ 那份
- **批次/债**：Batch-B/G39（R52+R25），E09→R26 facade 删晚于此收敛。
- **为什么提**：仓内有两份 ready_queue.py（`core/algorithms/greedy/dispatch/`=impl，`core/services/scheduler/graph/`=R25 垫片）。R52 计划说「裸删 impl→R25 垫片 :9 import ImportError」——实盘 impl 是 `algorithms/.../ready_queue.py:103 get_ready_operation_ids`，垫片是 `graph/ready_queue.py:9 from ...import get_ready_operation_ids`，**锚点完全坐实**，test_ready_queue.py 实测 **31 用例**（dossier「~23」失真，计划已纠正，正确）。仅提示执行者别把两份 ready_queue 搞混（同名异文件）。
- **不是反序**：E09 方向（R52 收敛先→R26 删 facade 后）正确。
- **修正建议**：无硬伤，建议 G39 前置安全网点名「impl=algorithms/greedy/dispatch、垫片=services/scheduler/graph」两份全路径防混。

### 问题4（低）· R26 「顶层 5 shim」与 number_utils 薄壳 —— 三桶前置方向对，shim 清单未在本计划展开
- **批次/债**：Batch-D/G18（R26）←E07(R29)/E08(R33)/E09(R52) 三桶收敛。
- **为什么提**：E07/E08/E09 三条 facade-晚于-收敛 H 边方向全部正确（R29 在 Batch-D/G26、R33 在 Batch-C/G23、R52 在 Batch-B/G39，R26 在 Batch-D/G18 最晚），number_utils 三份（common/scheduler/shared）实盘在场印证 R29 半截迁移。但 R26「顶层 5 shim」具体哪 5 个 shim 文件本计划未列（只在 G18 说「2 离线消费者 tools:17/audit:87」）。执行 G18 时须先有 5 shim 清单才能验「三桶已收敛覆盖这 5 shim 的下游」。
- **不是反序**：三桶→R26 顺序正确，E07/E08/E09 坐实。
- **修正建议**：无硬伤，G18 落地前从 _interference_rebuilt B14 桶补全 5 shim 清单，逐个对账其下游是否落在 R29/R33/R52 三桶内。

## 2. 未发现反序的硬边（逐条已验过，登记备查）
- E01/E02：GF1→R04/R59，ROOT 先于 Batch-B，方向对。
- E03：R54→R42/R60 同符号 co-change，G04 先于 G01（E03 硬同批 rebase），方向对（除问题1 路径）。
- E05/E06/A14：R33 先删壳 import→R31/R30 后删源，壳 `core/services/common/value_policies.py:3-11` 确 import 源 `core/shared/value_policies.py:9 WRITE_INTERNAL_ONLY`，依赖方向=壳 import 源，A14 已纠 R31→R33 自相矛盾为 R33→{R30,R31}，正确。
- E07/E08/E09：R26 晚于 R29/R33/R52 三桶，Batch-D 最晚，方向对。
- E12：LB03（B01 承重）先于 G27 身份族 + R22 24 键 parity 先于收敛，ROOT 先于 Batch-C，`to_dict:46` 在位，方向对。
- E13：R14 删 `_resolve_strict_plan:134` 撞 LB01 同符号，LB01 承重让位先行，G41(Batch-D) 晚于 G07a(ROOT)，`:134 def _resolve_strict_plan` 在 `schedule_delay_diagnosis_service.py` 在位，方向对。
- E16：R19↔R01/R46 __all__ 串行对账，S→部分H，按最终导出表串行化无回边。
- E26：N1 注释先于 R08 删死分支，ROOT 先于 Batch-C/G22，注释面 H，方向对。
- R22 view_context:74：`normalize_plan_role` def 在 `schedule_result_view_context.py:65`、被调 `:74`，R21 wrapper 上游「绝不删 :74」止血点在位，方向对。
- R05 collar 双轨 raise + R56 navigation_context:79 fail-CLOSED（实盘 `plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`）：§3.2 方向硬门描述与现盘一致，正确。

## 3. 攻击视角自评
依赖反序专项未抓到「facade 删早 / parity 没先落就收敛 / 承重注释没先落就动同文件 / R26 未等三桶」任一硬伤——这些正是本计划脊梁第 1/4 步与三不变式重点设防处，设防到位。4 个发现全是锚点/措辞层「执行时找不到东西」类，最重的问题1（collar 路径写错宿主目录）须并入 D1 残瑕回写，否则明天扩 collar 第一步就踩空。
