# 执行重构新引入债扫描 — 承重/护栏/方案身份/guard 字段不对称

- 基线: `b08162cd`
- 当前分支: `codex/aps-three-gap-directions`
- 范围: `git diff b08162cd -- core web data`（生产 .py，只读）
- 聚焦: 承重护栏 / 方案身份(plan_role/scenario) / guard 字段相关的**新引入不对称 + 灵魂线违背**
- 行号回盘: 全部按符号名 rg 当前工作区落地，已记漂移
- 性质标注: 区分「真新债」「旧债搬家」「护栏升级(非债)」

> 结论先行: **未发现新的静默兜底 / fail-open / except 吞错**。已知线索里担心的两点(membership-check 弱化、navigation_context R56/R57 重定位)经回盘**都不是 fail-open**——一个是合法收敛、一个是把"静默强制"升级成"显式 loud 阻断"。2026-06-09 台账唯一真相源登记两条新债：(N1) execution-scope 读路径 membership-check 收敛后丢了自文档；(N2) `_event_id_for_revision` 末位 `return 0` 哨兵缺契约保护。两条均为 `planned / owner_pending=false`，本轮只登记，不执行修复；后续修法只能补保护性注释 + 绑契约测试，**绝不能合并/统一/透传**(会踩承重)。

---

## N1【真新债·承重不对称·缺注释】execution-scope 读路径 membership-check 收敛后丢了 adopted 自文档

**位置(已回盘)**
- `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py:129-130` `_identity_allows_query_membership_check`

**新代码片段**
```python
def _identity_allows_query_membership_check(identity: Mapping[str, Any]) -> bool:
    return bool(identity.get("can_write_feedback"))
```

**基线代码(被删)** — 同名函数原在 `scheduler_resource_dispatch_execution_routes.py`，refactor 把整块 guard helper 下沉到新 `_execution_context.py`，并把判定从五连合取收敛成单字段：
```python
return (
    _text(identity.get("requested_plan_role")) == "adopted"
    and _text(identity.get("effective_plan_role")) == "adopted"
    and _text(identity.get("source_table")) == "schedule"
    and not _text(identity.get("scenario_id"))
    and bool(identity.get("can_write_feedback"))
)
```

**定性: 收敛在行为上安全，但承重契约从"显式自证"退化成"隐式依赖"，无注释。**

**为何行为安全(已逐链回盘，反证 fail-open)**
- `can_write_feedback` 唯一权威产出点 = `core/services/scheduler/schedule_plan_identity_builder.py:89 _can_write_feedback`。它返回 True 必须同时满足 `is_current_official`(经 `_is_current_official_plan:136`→`is_official`)、非 superseded、非 candidate-rows、非 comparison、status 可执行。
- `is_official` 经 `_is_official_plan:70-84`：**强制** `source_table==SOURCE_SCHEDULE and requested_role==ROLE_ADOPTED and effective_role==ROLE_ADOPTED and status=="resolved_adopted" and not is_preview`。
- 即 `can_write_feedback==True` **严格蕴含** adopted+schedule+无 scenario-preview。旧代码那四个合取项是 `can_write_feedback` 的**真子集**，收敛后判定结果**等价**。不是 fail-open。

**为何仍算债(承重不对称 P2 类)**
旧写法是「写死 adopted/schedule/no-scenario」的**护栏自证**——读代码的人一眼看到"这里只放正式采用方案过 membership 检查"。收敛成 `can_write_feedback` 后，这条承重不变量被**藏进了 identity builder 的远端推导链**，本地零线索。未来 LLM 若改 `_can_write_feedback` 的语义(例如放开某 preview 也能 write_feedback)，**这个读路径 membership 闸会跟着无声放开，且本地看不出关联**。承重点丢了自文档 = 失忆债。

**承重等级**: load_bearing 倾向=true（这是「现场记录读取必须命中当前查询行」的 schedule_mismatch 闸，配合 `_ensure_feedback_target_in_query:106` 的 SCHEDULE_CONFLICT raise）。

**修法(承重神圣，仅补注释+绑 parity，禁改逻辑)**
- 在 `:129` 上方补「我是故意的」注释，钉死 `can_write_feedback` ⇒ adopted-only 的契约来源：
  ```python
  # 护栏(承重)：此处【故意】只看 can_write_feedback。它由 schedule_plan_identity_builder._can_write_feedback
  # 产出，True 严格蕴含 source_table=schedule + requested/effective_role=adopted + 非 preview/scenario
  # (见 _is_official_plan)。旧版在此重复写死那四个合取项，收敛后等价；改 _can_write_feedback 语义即等于
  # 改本闸语义，二者不可分别维护。绝不可在此放宽成 or / 加 preview 旁路。
  ```
- 绑契约测试: 断言「`can_write_feedback==True` 的 identity 必为 adopted+schedule+无 scenario」+「非 adopted/带 scenario 的 identity 不进 `_ensure_feedback_target_in_query`」。
- **禁区行**: `_can_write_feedback:89-110`、`_is_official_plan:70-84`、`_identity_allows_query_membership_check:129-130` —— 禁删合取项、禁把本闸改成读 request 原始 plan_role、禁加任何 preview/scenario 旁路。
- **owner_pending=false**: N1 已按“仅补注释 + 绑契约测试”的方向收进 registry；不得还原/改写函数体，也不得把 `can_write_feedback` 放宽成 OR/preview 旁路。

---

## N2【真新债·承重不对称·缺契约】`_event_id_for_revision` 末位 `return 0` 哨兵缺保护

**位置(已回盘)**
- `core/models/operation_execution_event.py:156-164` `_event_id_for_revision`

**当前代码片段**
```python
def _event_id_for_revision(event: Any, *, index: int, total: int) -> int:
    raw = _event_field(event, "id")
    value = parse_int(raw, default=None)
    if value is not None and value > 0:
        return value
    if index < total:
        raise ValueError(f"id is required before following event at {_event_identity(event)}")
    return 0
```

**定性: 末位 `return 0` 是 revision 链哨兵，不是任意默认值。**
非末位事件缺 id 已 loud raise；只有最后一个新事件允许 id=0，因为它没有后继事件需要引用它作为 `previous_event_id`。风险是后续维护者为“统一所有 id 解析”删掉 0 哨兵，或把非末位 raise 改软，导致 revision 拼接语义漂移。

**承重等级**: load_bearing 倾向=true（现场执行事件 revision 链的 previous_event_id 语义）。

**修法(后续执行，不在本轮做)**
- 在 `_event_id_for_revision` 的末位 `return 0` 附近补保护性注释，说明末位无后继、其 id 不参与下游拼接，故允许 0 哨兵。
- 补契约测试：非末位缺 id 必须 raise；末位缺 id 允许返回 0。
- **禁区行**: `if index < total: raise ...` 与末位 `return 0`。不得删除非末位 raise，不得把坏数据改成静默兜底，也不得顺手统一同文件其他 `return 0`。
- **owner_pending=false**: 已登记清楚，后续仅按注释 + 契约测试执行，不需要再等裁断。

---

## 已澄清为「非债」的两条已知线索（防止误判，逐条给反证）

### C1【护栏升级·非债】navigation_context.py R56/R57：移除 execution-review 强制分支，**不是 fail-open**
**位置(回盘)**: `web/navigation_context.py`（删 `_is_execution_review_request()`；`current_workbench_navigation_context` 内 `plan_role`/`scenario_id` 改为直读 request）。

**变更**: 旧代码对 execution-review 端点**静默强制** `plan_role=adopted`/`scenario_id=""`(用户实际请求的 preview 被悄悄改写成 adopted)。新代码删掉这个静默改写。

**为何是升级不是放开(已查接管路径)**: 强制逻辑没消失，而是**升级到页面 route 层并改成 loud 阻断**——
- `web/routes/reports_request_support.py:65 execution_review_plan_identity_error`：请求带 scenario 或非 adopted role → 返回**可见中文报错串**。
- 同文件 `:74 require_execution_review_adopted_plan`：直接 `raise ValidationError(..., reason="unsupported_execution_review_plan_identity")`。
- `web/routes/reports_page_support.py:execution_review_page_context`：identity_error 时走 `_blocked_execution_review_report`(空行 + `empty_reason="unsupported_plan_identity"` + `execution_review_identity_error`)，并用 `reports_execution_review_context.py:8 blocked_execution_review_plan_resolution` 把 `can_write_feedback=False/can_dispatch=False/is_preview=True` **如实标注**，**不做 adopted 自欺贴标**。
- 行级护栏仍在 core：page_plan_resolution/page_date_range 仍写死 `"adopted", None`。

**定性**: 把"静默强制 adopted"(违背"宁可暴露错误也不自欺"的软兜底)替换成"显式 loud 阻断 + 如实标 preview" = **灵魂线方向的改善**。非债。

**残留小点(非新债)**: `navigation_context.py` 通用 fallback 路径的 `plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`——把未知/垃圾 plan_role 静默归一为 adopted。但基线该处本就是 `plan_role or ROLE_ADOPTED`(无校验默认 adopted)，本次只是**收紧成枚举校验**，不是新引入的兜底，且这是非执行页的导航回退路径。不计新债。

### C2【护栏升级·非债】adopted-only 不变量下沉 v19 DB CHECK + 集中 raise，新文件无承重不对称
- `core/models/operation_execution_scope.py:36 validate_current_official_execution_scope`：source≠schedule / role≠adopted / scenario 非空 **逐个 loud raise ValueError**，无兜底、无 return None。✅ 集中校验是收口升级。
- v19 迁移 `core/infrastructure/migrations/v19.py`：把 `effective_plan_role/source_table` 的 DEFAULT 去掉、保留 `CHECK(=‘adopted’)/CHECK(=‘schedule’)`，UNIQUE 补 batch_id+source_table+effective_plan_role；`_reject_invalid_event_sequences` 发现脏序列**直接 RuntimeError 拒绝静默迁移**。✅ loud。
- 写路径 3 个 raise 校验点全部到位且 loud：`data/repositories/operation_execution_event_repo.py:241`、`core/models/operation_execution_event.py:297`、`data/repositories/operation_execution_state_builder.py:73`。
- 读路径 `operation_execution_scope_read.py:56 scope_from_plan_row`：op_id/schedule_id/version/batch_id 缺失 **loud `ValueError`(:68)**；source_table/effective_plan_role/scenario 从 plan_fields 取(default=""/None)交由 `OperationExecutionScope.from_values`→`_required_text` 兜空再 raise。**读路径不重复 adopted 断言是设计**(写已被 DB+app 双闸挡死，非 adopted 行不可能有 event)。`_scope_for_event_list:288` 的 `except ValueError → raise AppError(DB_INTEGRITY_ERROR, reason="missing_plan_identity") from exc` 是**带 cause 的 loud 转译**，非吞错。✅ 非债。

---

## 灵魂线专项核验：4 处生产新增 except + 静默兜底，逐条排雷

> `git diff b08162cd -- core web data` 生产路径仅 **4 处** `except Exception` + **2 处** `except AppError`（其余 grep 命中全在 docs dossier markdown，非生产代码）。逐条核：

| 位置(回盘) | 形态 | 定性 |
|---|---|---|
| `core/services/scheduler/gantt_range.py:33 _normalize_offset_weeks` | `try int(...) except Exception as e: raise ValidationError(... ) from e` | **loud 转译**，宽 except 但立即 re-raise 成带 field 的 ValidationError。✅非吞错。可选收窄成 `(TypeError,ValueError)` 但非债。 |
| `core/services/scheduler/resource_dispatch_overdue.py:36 _load_result_summary_payload` | `except Exception as exc: _mark_overdue_degraded(reason=..., message=...); return None` | **可观测降级**：写 `degraded=True`+`reason`+用户可见 message，非静默。符合灵魂线 P4「可观测降级标记」。✅非债。 |
| `scheduler_resource_dispatch_execution_routes.py`（events route，旧 diff line ~7097） | `except AppError → _execution_error_response; except Exception: current_app.logger.exception(...); return 500` | **loud**：logger.exception 打全栈 + 500。与基线同文件 `resource_dispatch_execution_actual` 既有 route 同款模式(旧债同构搬家)。✅非新债。 |
| 同文件 `resource_dispatch_execution_actual_by_task`（旧 diff line ~7138） | 同上 | 同上，新 task_key 路由复制既有 500 兜底模式。✅非新债(模式搬家)。 |

**新拷贝私有 helper 核验**: `_text`/`_positive_int`/`_execution_svc`/`_feedback_svc`/`_execution_error_response`/`_json_payload` 等从 `_execution_routes.py` **整块搬到** `_execution_context.py`(routes 文件对应块同步删除)——是**搬家不是复制**(原处已删)，且 `_positive_int` 还顺手收口到了 `parse_positive_execution_int`(:30)。唯一**语义收敛**的是 `_identity_allows_query_membership_check`(见 N1)。其余逐字等价。不计新拷贝债。

---

## 分层红线核验
- 新文件 import 方向抽查：`operation_execution_scope_read.py`(core.services)→`core.models.operation_execution_scope` ✅下游；`scheduler_resource_dispatch_execution_context.py`(web)→core.models/core.services ✅；`reports_execution_review_context.py`(web)→`core.models.schedule_plan_role` ✅。未见 `core.algorithms→core.services` 或 `core.models→core.services` 反向 import。AST 违规=0（抽查范围内）。

## owner_pending 汇总
- N1、N2 均已收进 registry 唯一真相源，状态为 **planned / owner_pending=false**。本轮只做台账登记，不执行这两条后续债；未来只能按保护性注释 + 契约测试推进。
