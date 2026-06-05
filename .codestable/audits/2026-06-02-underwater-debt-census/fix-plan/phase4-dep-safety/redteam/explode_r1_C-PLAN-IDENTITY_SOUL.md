# 逐簇爆炸对抗 r1 · C-PLAN-IDENTITY · 主透镜【灵魂线热路径+收口等价】

> skeptic 第 1 轮 · 只读不改 · 默认怀疑 · 行号均 2026-06-05 rg/Read 实盘回盘(不信旧值)
> 成员 R21 / R22 / R23 / R72 · 桶 B02 身份族 · 簇 C01
> 判定图例:🔴红=会炸 / 🟡黄=有条件可做 / 🟢绿=安全

---

## 回盘真相源(本轮实测,推翻/确认旧值)

| 锚点 | 实测 file:line | 状态 |
|---|---|---|
| R21 dpr_dict wrapper(KEEP) | `gantt_plan_query.py:32-39`(loud raise @38) | ✅准,零漂 |
| R21 wrapper 依赖的 import 别名 | `gantt_plan_query.py:11-13`(`default_plan_resolution_dict as _default_plan_resolution_dict`) | ✅ 这条 import 是 wrapper 命脉,不可连带删 |
| R21 三死 shim | resolve_plan:42-43 / selected_plan_role:46-47 / _has_explicit_gantt_range:59-71 | ✅准 |
| R21 三待清 import | _resolve_plan:14-16 / _selected_plan_role:17-19 / _has_explicit_display_range:23-25 | ✅准 |
| R22 手搓内层 dict | `schedule_result_view_context.py:77-100`(**实测 22 键**) | ✅ |
| R22 canonical 收口 | `PlanIdentity.to_dict:46`(**24 键**,parse 键 @58/59) + `build_plan_identity:158` | ✅ |
| R22 调用点 | fallback:152 / no_history:449 / missing_history:457 | ✅(phase1_blast 标 440/448 已 +9 失真) |
| R22 缺键静默 False 链 | `_identity_bool:271-274`(缺键回退 data.get) + `plan_role_filter_fields:329-330`(两路皆缺→恒 False) | ✅ 链成立 |
| R22 parity 前置门 | **未落**:无 `build_plan_identity().to_dict()` 断言;evidence_contract 仍 `set(identity) >= {...}`@194(22 键 superset) | 🔴 收口硬 precondition 缺口 |
| R23 两份 _normalize_role | model:21-23 ↔ service:28-30(**字节级相同**,实测) | ✅ |
| R23 resolve_plan 双段 | `query_service.py:106 _normalize_role`(静默归一)→`:107-108 raise ValueError`(loud) | ✅ |
| R23 误并陷阱 view_context | `normalize_plan_role:65-72`(带 VALID 校验,抛 **ValidationError** 异类异文案) | ✅ 误并=行为变更 |
| R72 两份 _get_plan_role_arg | gantt:136 ↔ week_plan:67(字节级相同) | ✅ |
| R72 收口落点现状 | `scheduler_utils.py` 仅 `from flask import g`(**无 request**),核无 plan_role getter 孪生 | ✅ 分层铁律成立 |
| R34 联动锚(R23 行号联动) | `get_plan_time_span_for_resolution:210` 存在 | ✅(印证 layer1 纠正) |

---

## R23 — 🟢绿(条件:守住 §4 禁区不误并第三变体)

**判定:🟢绿,簇内最安全,可先落热身。** 两份 `_normalize_role` 字节级相同(model:21-23 ↔ service:28-30 实测逐字符一致),收口 service→model 合法层向(model 仅 import typing,零环),触发面 2 处自调用,tests 零钉死。逐分支等价无反例。

**但有一条静默炸点必须钉死(降级而非升级到红的唯一理由是它已被 §4/§7 双重拦截):**
- 灾难链:dedup 时若误把 service:28 收口到 view_context `normalize_plan_role:65`(带校验) → `resolve_plan("bogus")` 的抛错从 `ValueError`(:108)变 `ValidationError`(:69) + 抛错点前移 + 文案变 → 上游 `except ValueError` 的调用方**静默漏接** → 错误角色被当合法值放行(身份族最怕的静默错身份)。
- 拦截:R23 收口范围**仅** model:21 + service:28 两份字节重复体,**绝不并入** view_context:65。resolve_plan 双段(:105-108)只换 :106 符号来源、不动语义。
- 前置/顺序:与同文件 R34 行号联动——R23 删 :28-30 三行致其后上移 3 行,**R23 先落**让 R34 基于删后行号定位(软序,非硬)。

## R72 — 🟡黄(条件:owner 裁断 + 必补 `from flask import request` + 实时重盘 week_plan 行号)

**判定:🟡黄,owner_pending=true,叶子级低危但有三个条件门。** 两份字节相同(gantt:136 ↔ week_plan:67),纯 dedup 无行为差。

**条件门(全满足才可落):**
1. **分层硬约束(灾难链 A)**:getter 读 `flask.request`,**绝不能下沉 core/services 或 core/shared** → 否则 `core→flask` 跨层 import,击穿 AST 0 违规红线。实测核无 plan_role getter 孪生,R72(web 请求层)与 R44(core resolve 层)落点天然分离,必须各落各点,**不硬塞同一 helper、也不各建各的**(owner 须与 R44 共识)。
2. **必补 import(灾难链 B,本债最易踩坑)**:`scheduler_utils.py` 实测**仅 `from flask import g`,无 request**。收口提 `get_plan_role_arg` 到 utils 却忘 `from flask import request` → 运行期 `NameError: request`,只在该路由命中时炸(latent 但 loud)。
3. **静默改语义禁区(灾难链 C,灵魂线)**:收口**不得**顺手把"空串→None"改成"空串→默认角色/兜底",否则下游静默选错 plan_role(low 债升级为正确性 bug)。空串→None 是当前真实语义,原样保留。
4. **行号联动(返工风险)**:week_plan.py 是当天高频漂移热点(def 已 +7、call 已 +15,实测 def@67/call@288/375),与 R21/R55/R44 同文件 → 落地前必须实时 rg 重盘,blast/registry 静态行号一律不信。

## R22 — 🟡黄(条件:parity 前置门必先落 + 保留 R21 wrapper + B01/LB03 先行 + owner 裁取值语义)

**判定:🟡黄(owner_pending=true)。** 病理 drift 已现形非潜在:手搓内层实测 22 键、canonical 24 键,差集恰 `{result_summary_parse_failed, result_summary_parse_reason}`。收口本身合规(委托 build_plan_identity/SchedulePlanResolution.to_dict,包内同层,零跨层零环;消除"缺键静默 False"回退,灵魂线方向正确)。**之所以黄不绿,是四道前置门缺一即炸:**

**灾难链(主透镜:收口缺键静默 False 落热路径)**:
- 手搓 dict 缺 `result_summary_parse_failed` → `_identity_bool:271-274` 缺键回退 `data.get` → `plan_role_filter_fields:329-330` 两路皆缺 ⇒ **恒 False**。一条 result_summary 损坏的方案:走 canonical → parse_failed=True(报表/派工会拦);走 no_history 手搓 dict → 静默 False(误判正常)。
- **但触发面窄**:手搓 dict 调用点实测仅 fallback:152 / no_history:449 / missing_history:457(只读无历史页,此时本无 summary),且写/派工真闸门另走 identity re-resolve(`feedback_service:355-362` 等) → 不静默放行写操作 ⇒ severity 钉 medium 而非 high。这是黄不是红的根据。

**四道前置门(缺一即炸)**:
1. **parity 门未落(🔴 实测确认)**:tests 无 `build_plan_identity().to_dict()` exact 断言,evidence_contract 仍 `>=` 22 键 superset(@194)——这正是 drift 0→2 而 CI 全绿的根因。收口前必须先补 **24 键 exact `==`** parity(Batch-1 纯增量网),不可照抄 22 键 superset,否则收口取值漂移无网兜底。
2. **保留 R21 wrapper(硬 precondition)**:R22"保留遗留文案包装"依赖 `gantt_plan_query.py:32-39` wrapper 续命,契约测试 `regression_schedule_result_view_context.py:294-300` 钉死「未知的排产方案角色：bad」。R21 绝不可先删 wrapper。
3. **B01/LB03 先行**:收口符号 `build_plan_identity` 所在 builder 是承重(LB03),R22 只 CALL 不改 builder:158 / PlanIdentity.to_dict:46-71(禁区行)。LB03 承重注释+guard 收口须先于 B02 身份族动工。
4. **owner 裁取值语义**:LB03 改两 parse 键取值(静默吞→loud)不改键集,parity 用"键集+取值"exact 即覆盖;但取哪种语义待 owner 拍板(owner_pending,只标不给终态)。

## R21 — 🟡黄(条件:R22 在前锁定 wrapper 保留 + 整文件保留 4 LIVE 函数 + 不删 :11-13 import 别名)

**判定:🟡黄(非承重可动手,但与 R22 硬序耦合,误删即连环炸)。** 三死 shim 纯透传 re-export,零生产消费者(`gantt_service.py:12` 只导 4 LIVE,不含任一 shim)、零测试引用,删之无 parity 需求、无测试变红。

**两条致命误删链(本簇最危爆点,必须前置拦截):**
1. **误删 dpr_dict wrapper(:32-39)→ R22 连环炸**:wrapper 是 loud raise(:38 抛 ValidationError 改文案),是 R22"保留遗留文案"的 precondition。若 R21 把它当死空壳删 → R22 约束失效 + 契约测试 :300 变红 + 「未知的排产方案角色：bad」文案静默退化为收口点原始文案。**连带陷阱**:wrapper 依赖 `:11-13` 的 import 别名 `default_plan_resolution_dict as _default_plan_resolution_dict`,删 3 shim 清 import 时**这条 import 必须保留**(实测 :12,易被一并误清)。前置:R22 先锁定"wrapper 保留"约束,R21 紧随同提交、严守保留 :32-39 + :11-13。
2. **误删整模块 → 甘特周计划范围静默断裂**:见 3 shim 全死就判整模块死、连带删 4 个 LIVE range 函数(get_version_time_span_dates:50 / resolve_gantt_range_for_version:74 / attach_gantt_range_metadata:113 / build_empty_week_plan_payload:135)→ 打断 gantt_service 真调用 → version_span/week_range/empty_message 整条静默断裂。前置:明列"整文件保留,只删 :42/:46/:59 三段 + :14-16/:17-19/:23-25 三 import"。

**禁区行(R21 绝不碰)**:`gantt_plan_query.py:32-39`(wrapper)+ `:11-13`(其 import 别名)+ `:50-156`(4 LIVE 函数)。行号联动:删 import 区致 wrapper 上移约 9 行,R22 锚 wrapper 用符号名 `default_plan_resolution_dict` 不用行号。

---

## 漏项(本轮新发现,计划未充分覆盖的爆点/缺失前置)

1. **【R21 import 别名 :11-13 易误清,簇报告 D 节禁区只列 :32-39 未显式护 :11-13】**:dpr_dict wrapper 的命脉 import `default_plan_resolution_dict as _default_plan_resolution_dict`(实测 :12)。R21 删 3 shim 时同步清 3 个待清 import(:14-25),极易把相邻的 :11-13 这条 wrapper 依赖 import 一并误清 → wrapper 内 `_default_plan_resolution_dict` NameError。簇报告禁区行汇总写"`:32-39` + :11-13 其 import"已含,但 dossier R21 字段 4 删除清单与 §禁区 A 须在执行步骤里**显式标红:清 import 时跳过 :11-13**,否则 loud 但仍是 R21 的可用性回归。建议补一条单测 `import gantt_plan_query` + 调 `default_plan_resolution_dict("bad")` 作删后自证(R21 字段 11 已建议,提升为前置必跑)。

2. **【parity 门"升级 22→24 exact"与"新增 view_context parity"是两件事,易被合并漏一】**:R22 字段 7/11 要求(a)新增 `default_plan_resolution_dict` vs `build_plan_identity().to_dict()` 的 exact 断言 +(b)升级 `evidence_contract:194` 的 `>=` superset 为 24 键 exact。两者治不同症:(a)钉手搓侧 drift,(b)堵 CI 全绿放行的根因网。若只做(a)漏(b),evidence_contract 仍可放过未来 canonical 再加键的二次 drift。建议两条 parity 同 Batch-1 落,缺一不可。

3. **【R72 灾难链 C 与 R23/R72 共性:plan_role 空值语义"空串→None"vs"空→adopted"在簇内不一致,易被"统一"冲动误抹】**:R72(web)空串→`None`;R23(`_normalize_role`)空→`ROLE_ADOPTED`;view_context `normalize_plan_role`(:65)空→`ROLE_ADOPTED`+校验 raise。三者对"空"的归宿不同(None / adopted / adopted+校验),是**故意的分层差异**(web 取参层允许 None 交下游决策,core 归一层兜 adopted)。簇报告已分别拦截,但**漏一条横向守卫提示**:任何收口/dedup 都不得以"统一空值处理"名义把 web 的 None 改成 adopted 或反之——这会静默改 plan_role 默认选择。建议 owner 裁断时把"三处空值语义差异是契约非 bug"写进概念身份证,防后续 LLM 失忆再统一。

4. **【week_plan.py 当天高频漂移=行号炸弹,任何静态行号计划落地前都已过期】**:实测 week_plan def 已 +7、call 已 +15,文件 mtime 06-05 与 R55/resource_dispatch 邻边同动。这不止影响 R72——簇内凡引 week_plan/scheduler_gantt 行号的步骤(R21/R55/R44 联动)都须落地前实时 rg。建议 Layer4 出执行批次时,对 scheduler_gantt.py + scheduler_week_plan.py 同文件多债**强制同批或显式串行 + 每步前重盘**,列为批次硬纪律而非软建议。
