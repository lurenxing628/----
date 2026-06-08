# 逐簇爆炸对抗 r3 · C-EXEC-REVIEW · 主透镜=灵魂线热路径+收口等价

> skeptic 第3轮 · 只读不改 · 行号 2026-06-05 工作区 rg 实测回盘（execution_review.py git=MM, 476 行）
> 成员债 [LB02, LB05, R62] · 主文件 core/services/report/execution_review.py
> 主透镜 Q4/Q5/Q6 为重，六质问全过。默认怀疑：多数维度存疑即标红。

---

## 0) 回盘基线（本轮 rg 实测，旧行号一律不信）

承重五处硬钉 + 签名（全命中 dossier，零漂移偏差）：
- `:9` `from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE`
- `:58` `effective_plan_role=ROLE_ADOPTED`（scope 构造，工作区新增第 7 钉）
- `:180-181` / `:191-192` `plan_role=ROLE_ADOPTED, scenario_id=None`（between/all 两路）
- `:209` `def execution_review(` 签名——keyword-only 仅 version/date_from/date_to/batch_id/resource_type/resource_id，**实证不收 plan_role/scenario_id**
- `:221` `host._resolve_plan(v, ROLE_ADOPTED, None)`
- `:236` 返回 dict `"plan_role": ROLE_ADOPTED`
- `:121` `_resolve_plan` Protocol；`:99`/`:113` Protocol 形参声明 plan_role: Optional[str]

R62 三档键区（全命中）：
- `_resource_pair_payload`:406，三键恒等 return **:417** `{"display_label": display, "identity_label": display, "export_label": display}`
- exception 三连 :358-359 / :361-362；planned 三连 :373-375；actual 三连 :380-382
- `_actual_resource_identity` 无 feedback 早退块三键 :437-441（内容 :438-440）
- 模板死副行 templates/reports/execution_review.html :138/139/142/143（`!=` 模式实测命中）
- xlsx 死回退 core/services/report/exporters/xlsx.py :410/411/414/415（`or` 回退，未漂）

护栏测试 tests/operation_execution/test_execution_review_identity_guard.py（6186B, 6 个 test）实测存在：
candidate→blocked(:59) / unknown role 不泄漏 raw(:76,:86 `future_role not in body`) / scenario→blocked(:91) / 资源筛选导出只含正式行(:107) / **历史 adopted 可见可导出(:136)** / 导出拒非正式身份返回 **400**(:162-173)。

灾难链物理可达坐实：`report_plan_helpers._resolve_plan`:37 透传 plan_role/scenario_id → `resolve_plan_view`:176 → scenario_key 非空切 `_resolve_scenario_plan`:185 → 换 source_table（SOURCE_ADJUSTMENT_SCENARIO_ROWS import :13）。**加形参=静默换源表无 raise**。

R62 爆炸面闭合：全仓（剔 latest_/counterpart_）无前缀 identity/export 键消费者**仅 execution_review.py + 模板 + xlsx 三处**，无 web 路由/其他服务读取。

---

## 1) 逐成员债判定（六质问 + 主透镜）

### LB02 —— 承重不对称（刻意只复盘 ROLE_ADOPTED，签名禁形参）

**判定：🟢 绿（计划修法=纯注释+回归，安全）；但带一条🔴红色禁区警戒线（见灾难链）**

- Q1 承重误删：计划修法被铁律3锁死为「仅 `#` 注释 + 回归既有测试」，零删/零统一/零透传/零加形参。五处禁区行（:58/:180-181/:191-192/:221/:236）+ 签名 :209 全列 lb_no_touch。**无误删风险。**
- Q2 分层环：纯注释零新增 import，0 AST 违规。import :6-14 全同层/下层（infra/model/同层 service），无 core.models→core.services / core.algorithms→core.services 反向边。**绿。**
- Q3 迁移耦合：注释不碰 schema/迁移，adopted-only 已下沉 v19 CHECK（effective_plan_role=adopted）与本注释无耦合。**绿。**
- Q4 灵魂线热路径：注释**不新增任何兜底/静默回退**；反而 guardrail 测试已验页面 loud 拦截（候选→可见 blocked、导出→400）+ 导出链置空。历史 adopted 热路径（测试 :136）走正常显示非 blocked，注释不触。**绿，合灵魂线。**
- Q5 收口等价：本债不收口（纯护栏注释），无新旧两路 parity 义务。adopted-only 不变量已收敛在已存在单点 `_resolve_plan`:121/:221，无新建收口点。**绿。**
- Q6 测试迁移序：no-op，无需迁测试，只回归 4 组（guardrail / plan_vs_actual / workbench_link_guardrails / navigation+backlink contract）。注释若致任一变色=误改表达式，立即回退。**绿。**

**🔴 红色禁区灾难链（非计划动作，是必须钉死的反例锚点）**：若他人以「统一四张报表签名」给 :209 加 plan_role/scenario_id 形参并透传 → report_plan_helpers:37 → resolve_plan_view:176 → scenario 非空切 _resolve_scenario_plan:185 换 source_table → 预览/对比方案明细拼进「计划 vs 实际」→ export_execution_review_xlsx 导出 → **预览静默冒充正式现场复盘，无 loud failure（违灵魂线）**。当前 guardrail 测试在请求级（页/导出）挡住，但残余风险=绕页面直调透传后的 service 且不更新测试。故 §90 LB-A2 注释**必须钉回 :209 本地**，不可只靠远端测试。**计划已正确把此列为禁区——绿在于不动它，红在于一旦动它即炸。**

### LB05 —— 同点第二 finding（服务层零注释保护，含 :58 第 7 钉）

**判定：🟢 绿（与 LB02 同一次注释动作，安全）**

- 与 LB02 完全同点：同段签名 :209 + 同五处硬钉（LB05 多覆盖 :58 scope 构造第 7 钉）。**一次注释满足两条**，只新增 `#` 行、不动 dict 键序、不位移返回 dict（:225-238）键。
- Q1-Q6 同 LB02 全绿。**唯一额外注意**：dossier 自核 B 节已纠正「文件未 git 修改」失实（实为 MM、HEAD=407 行），但 `git diff HEAD | grep ROLE_ADOPTED` 确认原有硬钉的 plan_role/scenario_id=None 零改动，:58 第 7 钉是新增且方向与不变量一致（非削弱）。**承重不变量未被工作区改动削弱，绿成立。**
- 主透镜 Q4：LB05 §7 给的「未来放开历史正式版本」precondition 要求 service 内非 adopted/非 None **必须 loud raise ValidationError，禁默默回退 adopted**（None vs raise 不可混）——这正是灵魂线口径，**本批不放开，仅注释，不引入此分支**。绿。

### R62 —— 三档身份压扁死分支清理（display/identity/export 恒等）

**判定：🟡 黄（收口等价成立但强原子三处同删 + 行号重盘 + 五处禁区贴身，有条件可做）**

- Q5 收口等价（主透镜核心，逐分支验）：
  - `_resource_pair_payload`:407-416 五分支（machine&op / machine / op / else empty_label）全产**非空 str**，:417 三键由同一 `display` 赋值 → identity 恒非空且恒==label。**无 None vs raise 反例。**
  - **额外验命门**（dossier 未充分展开，本轮补证）：actual 路径 `_state_resource_identity`:430-431 产出的 `ResourceIdentity` 里 display_label(:430) 与 identity_label(:431 `_identity_label or _label`) **可能不同源不同值**——但 :442-443 把它喂给 `_resource_pair_payload`，而 payload **只读 `machine.display_label`/`operator.display_label`（:407-408），完全丢弃 identity_label**。即 actual 真身份信息**在 payload 层已被丢弃**，三键收口面恒等成立。`_state_resource_identity` 仅此一处被调，identity 无旁路消费者。**等价坐实。**
  - 模板 :138-143 `!=` 恒 False（identity==label）text-meta div 永不渲染，删副行后渲染逐字节不变；xlsx :410-415 `or` 永不回退（export==label 非空），删 `or` 后取值相同。**三处删除均零行为差异。**
- Q1 承重误删：R62 lb=false。收口段 :358-444 与护栏区 :58-236 **不同方法、零行重叠**（rg 实测）。但**🔴红色贴身风险**：R62 删键时行号已被 LB02/LB05 注释下推，若照抄旧行号或手滑上探，可能误碰五处 ROLE_ADOPTED 禁区（:58/180-181/191-192/221/236）→ 破坏「只复盘正式采用方案」→ 复盘错读 scenario 草稿。**前置铁律：A1 注释先落（Batch-1），R62 后做（Batch-3），动手前按符号名 `_resource_pair_payload` + `!=` 模式重新 grep，绝不照抄任何档案行号。**
- Q6 测试迁移序（黄的主因）：R62 收口面**零现成测试**（tests/ 对无前缀 `*_identity_label`/`*_export_label` 零断言，rg 验真）。**删前必须先新写 3 套 parity 快照**（dict 键消失+label 值不变 / xlsx 逐格相等 / 模板 HTML 无 text-meta diff）作收口安全网，否则删完无自证。**这是「测试绿但护栏未建」的反面——此处是测试根本不存在，序错=删完无网。**
  - **🔴误删对象灾难链 B**：state 层 `latest_*_identity_label`(operation_execution_state.py:45) + `counterpart_resource_identity_label` 被 7+ 文件 PIN 真身份（resource_dispatch viewmodel contract :68/71、test :239 断言 "MC001 数控车床1"）。若把带 `latest_`/`counterpart_` 前缀的真身份键当 R62 残骸删 → 这批契约测试全红。**前置：删时严格限定无前缀键，键名空间分离已 rg 证（剔除前缀后消费者仅 3 文件）。**
- Q2 分层：纯删键，零新增 import，无新建模块，0 AST 违规。**绿。**
- Q3 迁移耦合：R62 三档键非 schema 字段，不碰 v18/v19 CHECK。**绿。**
- Q4 灵魂线：xlsx `or` 与模板 `!=` 是「展示降级」非「错误吞噬」，删除清 P3 残骸不触灵魂线红线，不新增兜底。**绿。**
- **三处强原子耦合**：payload 键 + 模板副行 + xlsx 回退必须同一 commit。链 A（不原子）：只删 payload 漏删 xlsx → `row.get("X_export_label")` 取 None 仍 `or` 回退 label（不炸但留「键死回退活」新半截残骸）；漏删模板 → `{% if None and ... %}` 仍 False（不炸但残骸留存）。**全静默债务累积，非崩溃，但违 P3 清理初衷。**

---

## 2) 跨簇边复核（主透镜视角）

- **LB02/LB05 → LB06（web 守卫 fail-CLOSED）**：rg 实测 web 守卫符号现以别名 `n` import（reports_execution_review_context.py / reports_request_support.py），本体在 reports_execution_review_context.py + reports_request_support.py（**非 reports_page_support.py**，与 _layer2_residual.md LB06 宿主校正一致）。LB06 已 fixed（结构性 fail-CLOSED，未 fail-open），降为认账协同非阻塞。A1 注释须交叉引用「入口守卫已落（页级 identity_error+blocked），本服务层硬钉为数据层最后一道」，**勿粘 §90 LB-B4 反向 fail-OPEN 文案**（现盘已 fail-CLOSED）。
- 其余 same_symbol=false 弱边（R14/R42/R54/R58/R60/R61/R66）共宿主文件非同符号，按符号名定位即可并行，非阻塞。

---

## 3) 漏项（本轮新发现，没被计划充分覆盖的爆点/缺失前置）

1. **R62 parity 测试是「无中生有」非「迁移」**：计划/dossier §7 称「建议先补 3 套 parity」，但措辞偏软（「建议」）。本轮强调——R62 收口面**当前零断言**，不是「测试绿但护栏破」，而是**根本无网**。若 owner 跳过 parity 直接删，删完**无任何自证手段**证明零行为差异，且未来恢复真三档身份时无法回归。**建议升级为硬前置门（parity 红→绿基线先于删除），非建议项。**

2. **actual 路径 identity_label 真信息丢弃是「既成压扁」非 R62 引入**：`_state_resource_identity`:431 费力构造 `identity_label = _identity_label or _label`（疑似原意要真身份），却在 :442-444 被 `_resource_pair_payload` 只读 display_label 丢弃。R62 删收口面三键是清这层「构造了又丢弃」的半截残骸的**下半截**，但 :431 的 identity_label 构造（上半截）R62 计划**不动**（不在 :358-444 死分支区？实际 :430-431 在 _state_resource_identity 内）。**漏项**：R62 删 payload 三键后，:431 构造的 identity_label 成为更彻底的死值（产出后无人读）——计划未提是否同清 :431 的 identity_label 构造。**不阻塞**（:431 产出的 ResourceIdentity.identity_label 删 payload 后无消费者，留着是无害死值，但 P3 残骸未清干净）。建议 owner 决定 :431 是否一并收。

3. **历史 adopted 热路径（Q4/LB03 latest_executable_official_version）与本簇的隐性耦合**：guardrail 测试 :136-152 验证 version=11 历史 adopted 走正常显示+导出（非 blocked），断言「历史正式方案（已被新版本替代）」标签 + 「正式采用方案」not in。R62 删返回 dict 三档键**不碰** :235 `plan_label`/:236 `plan_role`，故不影响此热路径——但若 R62 重盘行号时把 :235-236 的 plan_label/plan_role 误纳入「标签压扁」清理范围（二者都叫 `_label`/`plan_*`），会破坏历史 adopted 标签区分。**前置警戒**：R62 收口面是 resource 三档键（exception/planned/actual_resource_*），**与 :235 plan_label / :236 plan_role 是完全不同的键族**，重盘时按 `_resource_` / `_machine_` / `_operator_` 前缀锁定，勿扩进 plan_* 标签。

4. **签名禁区 :209 的远端测试覆盖盲区仍在**：guardrail 全是请求级（页/导出 HTTP），无「直接 import 调 `execution_review(version, plan_role=非adopted)`」的单元级断言——但因签名根本不收 plan_role 形参，该调用类型层不可达，盲区影响有限。**LB02 注释钉回 :209 本地正是补这个「绕页面直调」残余口的唯一手段**，计划已覆盖，无新增缺失。
