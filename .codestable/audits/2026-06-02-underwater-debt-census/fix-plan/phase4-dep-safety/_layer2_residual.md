# Layer2 收敛结论 + 残留文档瑕疵（喂给 Layer3/4）

> 来源 workflow wl5ginikd（19 agent）。红队 2 轮一致判：**分析层（拓扑/承重/边）PASS**，仅余文档侧瑕疵。

## Layer2 收敛结论（可直接用）

- **42 个原子簇（G01–G42）+ GF1 共享前置门（reject_integer_float，非债，默认 False）= 43 调度单元**。多债强原子 20 / 单债 22 / 承重门 6🔒 / owner_pending 16⏸。
- **验环：无环，DAG 成立（环成员=空）**。跨原子簇真门控硬边仅 **13 条 H 边**；承重根层（GF1/LB01/LB02/LB05/LB07/LB08/LB03/R05-step1/R22-parity）零入边纯 source。
- 边总变化：旧 146 → 删 29（假边 22 + 已修对消 5 + 方向并 2）+ 新 19 + 降 18 ≈ **重建 ~136 边**。
- **承重文件 6 个**（红队补登第 6 个）：见下方路径表。
- 批次草案：**ROOT → Batch-A（零前置死叶子）→ Batch-B（单门控前置）→ Batch-C（身份族收敛）→ Batch-D（facade 最晚）**。
- 三不变式全守：承重前置先落 / B13 facade 晚于 B05·B06·B09 收敛 / parity（R22 24键 exact、R68、LB07 spec_sync、R54 三基数分组、GF1）先于收敛。

## 权威真实路径表（修正红队 D1 的 4 处前缀错；已 ls 确认存在）

| basename | 真实路径 |
|---|---|
| scheduler_navigation_publish.py | `web/routes/domains/scheduler/scheduler_navigation_publish.py` |
| schedule_payload_contract.py | `core/services/scheduler/run/schedule_payload_contract.py` |
| schedule_repo.py | `data/repositories/schedule_repo.py`（**无 core/ 前缀**） |
| part_repo.py / op_type_repo.py / operator_repo.py / batch_operation_repo.py / operator_machine_repo.py / material_repo.py | `data/repositories/`（无 core/ 前缀） |
| operation_execution_scope.py（第 6 承重文件，R09 收口家 + LB01 最终底同住，3499B） | `core/models/operation_execution_scope.py` |
| reports_execution_review_context.py / reports_request_support.py / reports_page_support.py | `web/routes/`（LB06 fail-CLOSED 本体在前两者，非 reports_page_support） |

**6 个承重文件**：operation_execution_feedback_service.py（LB01）、execution_review.py（LB02/LB05）、navigation_context.py（LB06/R56）、schedule_config_runtime_{coercion,read,snapshot,...}.py（LB07）、scheduler_public_errors.py（LB08）、schedule_plan_identity_builder.py（LB03）、**operation_execution_scope.py（R09 收口点 parse_positive_execution_int:9 + validate:36-50 三 raise，新登）**。

## 残留文档瑕疵（Layer4 出可执行批次前统一回写；不撼分析结论）

- **D1**（中）：综合产物 §3 重灾区表 4 处路径前缀错（见上表）；nav_publish 一条与 R2-P4 layer 修订自相矛盾（prose 改了表行未同步）。
- **D2**（低）：collar 真符号 `build_workbench_plan_context`（scheduler_workbench_links.py:187），多数调用方以**别名 `n` import**。**co-change grep 纪律：删 R42 形参须同查 `build_workbench_plan_context` 与 `n(` 两种调用形态**，否则漏改 dashboard/reports/gantt_task_detail/navigation_links 的别名调用点（这些都不传 plan_id，TypeError 风险低但须覆盖）。
- **D3**（低）：R01 `__all__` 锚点 :414-415 已随 2026-06-08 G19 fixed 删除；后续禁按旧块重复施工。
- **LB06 宿主**（低）：fail-CLOSED 强制 adopted+scenario=None 本体在 `reports_execution_review_context.py`（blocked_execution_review_plan_resolution）+ `reports_request_support.py`（require_execution_review_*），**认账注释须落这两者，非 reports_page_support.py**。

## R09 收编面权威口径（红队补强，最高危收口）

- `_positive_int` 同符号 family 实盘 **STRICT 4 处（`-> int`，loud raise，一字不碰）**：scope.py:9 / scheduler_public_errors.py:167 / auto_assign:114 / operation_execution_feedback_support.py:161。
- **Optional 5 处（`-> Optional[int]`，收编面）**：context.py:28（已 wrap 收口点）/ scope_read.py:21（已 wrap）/ resource_dispatch_execution_tokens.py（已 wrap re-raise）/ **resource_dispatch_execution_service.py:24（未收编，def + 调用 :169/:180/:181，放宽点 :180-181 比较）** / **scheduler_resource_dispatch_execution.py viewmodel:33（未收编）** / **schedule_persistence_errors.py:13（第 3 份未收编，`int(value or 0)` 不 wrap，owner 复核）**。
- **收编只动 Optional 副本，STRICT 4 处一字不碰**；收编须分两路 parity：C 路（已收口）对 float/bool 严格 5.9→None/True→None，A/B 旧内联宽松 5.9→5/True→1——直接收口会**静默放宽**，owner 裁两种语义取哪个。
