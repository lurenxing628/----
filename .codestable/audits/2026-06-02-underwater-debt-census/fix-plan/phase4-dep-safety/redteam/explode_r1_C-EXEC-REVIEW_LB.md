# 逐簇爆炸对抗 r1 · C-EXEC-REVIEW · 主透镜【承重误删】

> skeptic 第1轮 · 只读不改 · 默认怀疑 · 2026-06-05 工作区 rg 回盘
> 成员债 [LB02, LB05, R62] · 主文件 core/services/report/execution_review.py(476行, git=MM)
> 主透镜 Q1 承重误删为重，六质问点全过。行号均经独立 rg 回盘，不信旧值。

## 判定速览

| 债 | 判定 | 一句话 |
|---|---|---|
| LB02 | 🟢绿 | 纯护栏注释，零删/零透传/零加形参；最大盲区(请求级回归)已闭合 |
| LB05 | 🟢绿 | 与 LB02 同点同动作，一次注释满足两条；纯增量 |
| R62 | 🟡黄 | 删 no-op 死分支行为等价，但消费方原子面须扩到「四处」(含模板 title)，且必须等 A1 注释落定后重新 grep |
## 回盘附证（2026-06-05 rg 实测，逐符号命中 dossier，不信旧值）

- 承重五处硬钉 + 签名：`:9`(import ROLE_ADOPTED,SOURCE_SCHEDULE) / `:58`(effective_plan_role=ROLE_ADOPTED, scope 构造) / `:121`(Protocol `_resolve_plan`) / `:180-181`(between 路硬钉) / `:191-192`(all 路硬钉) / `:209`(签名) / `:221`(host._resolve_plan(v, ROLE_ADOPTED, None)) / `:236`(返回 dict "plan_role": ROLE_ADOPTED) —— **全命中 dossier §1**。
- 签名 `:209-218` keyword-only 实测仅 `version/date_from/date_to/batch_id/resource_type/resource_id`，**确证不收 plan_role/scenario_id**。承重不对称坐实。
- R62 三档键：payload 收口源 `:406` / 三键恒等 `:417 {"display_label":display,"identity_label":display,"export_label":display}`(:409-416 全 5 分支 display 恒非空 str，三键恒等)；dict 装配 `:358-359/:361-362/:374-375/:381-382`；actual 无 feedback 早退 `:438-440`(块 :437-441)。
- R62 模板 `!=` 死副行 + **title 属性**：`templates/reports/execution_review.html :138/:139/:142/:143`，每行 `title="{{ r.X_identity_label }}"` + `{% if X_identity_label and X_identity_label != X_label %}<div class=text-meta>`。
- R62 xlsx `or` 死回退：`core/services/report/exporters/xlsx.py :410/:411/:414/:415`，未漂。
- 灾难链下游坐实：`report_plan_helpers.py` `_resolve_plan`(:29-37)/`_list_plan_rows_between`(:56-73)/`_list_plan_rows_all`(:83-100) **完整透传** plan_role/scenario_id → `schedule_plan_query_service.resolve_plan_view`(:176-185) → scenario_key 非空切 `_resolve_scenario_plan`(:185)换 `source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS`(import :13)，**无 raise，静默换源表**。
- 护栏测试存在：`tests/operation_execution/test_execution_review_identity_guard.py`(6186B, 6 测试函数)，三组负向反例(baseline_best :63 / future_role :78 / scenario SCENARIO-RPT :95) + `_export_links()==[]`(:72/:88/:103) + 历史 adopted 可见 :136 + 参数化导出拒非正式身份 :162。**fail-CLOSED 坐实，parity 盲区已闭合。**
- 消歧坐实：R62 无前缀键(planned_resource_identity_label / actual_resource_identity_label / *_export_label)全仓消费者**仅 3 文件**(execution_review.py / 模板 / xlsx.py)；state 层真身份 `latest_*_identity_label`(operation_execution_state.py:45/:50) + `counterpart_resource_identity_label` 是**另一键空间**，R62 不触及。

---

## 逐债判定 + 证据 + 灾难链/修正

### LB02 — 🟢绿（承重护栏注释，安全）

**判定 🟢**：修法 = 仅在 `:209` 签名上方 + 五处硬钉旁补「我是故意的」`#` 注释 + 回归既有 6 组护栏测试。零删除/零统一/零透传/零加形参。Q1 主透镜逐项过：
- **Q1 承重误删**：五处禁区行(:58/:180-181/:191-192/:221/:236/:209签名)仅补注释，不动表达式 → 无 fail-open。**绿**。
- **Q2 分层环**：纯注释零新增 import；现有 import(:6-14)全同层/下层(core.infrastructure/core.models/同层 core.services.scheduler + 本包相对)，无 core.models→core.services / core.algorithms→core.services 越层 → 0 违规。**绿**。
- **Q3 迁移耦合**：注释不碰 schema/v18/v19 CHECK，无启动探针风险。**绿**。
- **Q4 灵魂线热路径**：不新增兜底/静默回退；既有测试已验页面 loud 拦截 + 导出链置空，符合 P4。**绿**。
- **Q5 收口等价**：本债不收口(adopted-only 不变量已收敛在已存在单点 `_resolve_plan` :121/:221)，无新旧两路。**绿**。
- **Q6 测试迁移序**：不删 facade/不改签名/不删 impl，无需迁测试，只回归。注释为 no-op，6 组测试应零变化全绿；若任一变色=误改表达式立即回退。**绿**。

**潜在灾难链(被注释阻止的，非本债引入)**：若他人以「统一四张报表签名」给 :209 加 plan_role/scenario_id 形参 → helpers 透传 → resolve_plan_view scenario 非空切 _resolve_scenario_plan 换 source_table → 预览/对比方案明细以「正式现场复盘」身份拼进结果并经 export_execution_review_xlsx 导出 → **静默冒充，违灵魂线**。当前由 guardrail 测试在 CI 挡住；残余风险=绕页面直调新服务，故 §90 LB-A2 注释必须钉回 :209 本地。**这正是 LB02 注释的目的——绿，且是防爆的护栏本身。**

### LB05 — 🟢绿（与 LB02 同点，一次注释合并）

**判定 🟢**：LB05≡LB02 是同一承重不对称的第二 finding，钉同一段(签名 :209 + 五处硬钉 :58/:180-181/:191-192/:221/:236)。同一次注释动作 + 同一组回归即满足两条，只新增 `#` 行、不动 dict 键序、不位移返回 dict(:225-238)键。六质问点裁决同 LB02 全绿(纯注释、零结构改、零分层风险、不触灵魂线、不收口、不迁测试)。

### R62 — 🟡黄（删 no-op 行为等价，但有条件：原子面须扩到四处 + 行号重 grep 门 + 禁区零重叠须自证）

**判定 🟡（非红）**：三键当前恒等(payload :417 全分支 identity==export==display==label)，删 no-op 死分支对所有边界值逐分支等价，无 None/raise 反例(early-return :438-440 三键恒="暂无现场反馈"、exception 簇 :358-359 同源 affected_machine_label)。运行期零风险，非承重(lb=false)。**但三个条件必须满足，否则降红：**

**条件 1（爆点·簇文覆盖缺口）——模板原子面是「四处」不是「三处」**：簇 C-EXEC-REVIEW.md §A2 与多数描述把模板侧只列为「:138/139/142/143 `!=` 死副行」，**漏点同一行的 `title="{{ r.X_identity_label }}"` 属性也读 identity_label 键**。删 identity_label 键后若只删 `!=` 副行、漏改 title：Jinja2 `{{ r.X_identity_label }}` 取 undefined → 渲染空串 → `title=""`，title 从「有内容」变「空」= **可观测 HTML 属性变化(hover 提示/可访问性丢失)，非逐字节等价**。
  - 灾难链：删 payload+dict 键 → 漏改模板 title → title 空串 → 模板渲染 parity 测试若只断 text-meta div 不断 title 属性则**测试绿但 title 已退化**(静默 UI 降级)。
  - 修正：R62 原子面 = payload(:417) + dict 装配(:358-382) + **模板「`!=`副行**且**title 属性」两处同改**(title 改回 `{{ r.X_label }}`，因恒等故值不变) + xlsx(:410-415)。dossier R62 §4(b) 已写「title 改回 X_label」是对的，但**簇文 A2 须补这一点**，执行者勿只照簇文删 `!=`。parity 测试须同时断 title 属性，不止 text-meta div。

**条件 2（行号重 grep 门）**：A1 注释先落(Batch-1)会把 R62 的 :358-441 整体下推，R62 删键又回缩。R62 动手前**必须按符号名 `_resource_pair_payload` + `!=` 模式重新 grep**，绝不照抄 dossier/簇文行号(本档行号是「A1 注释未插」态)。

**条件 3（禁区零重叠须自证）**：R62 收口段(:358-441)与护栏禁区(:58-236)不同方法、零行重叠(rg 实测)——但删键时**绝不可顺手碰** :58/:180-181/:191-192/:221/:236/:209，更**禁顺手「统一四张报表签名」加形参**(灾难链同 LB02)。:431 `_state_resource_identity` 读 `state.{prefix}_identity_label` 是 **state 层真身份**(带 actual_machine 前缀)，与 R62 无前缀键不同空间，R62 删键不碰它。

**消歧灾难链 B（防误删，被消歧阻止）**：若误把 state 层 `latest_*/counterpart_*_identity_label`(真身份)当 R62 残骸删 → resource_dispatch viewmodel 契约 + operation_execution 系列断言全红(真炸)。R62 只删 execution_review 报表无前缀键，消歧成立，B 链不会触发——前提是执行者认清两键空间。

---

## 漏项（本轮新发现，未被计划/dossier 充分覆盖的爆点或缺失前置）

1. **【簇文覆盖缺口·中】R62 模板原子面少算一处**：C-EXEC-REVIEW.md §A2 描述模板侧仅「`!=` 死副行」，**未点出同行 `title="{{ X_identity_label }}"` 属性也消费 identity_label 键**。删键漏改 title → `title=""` 可观测 UI 降级。dossier R62 §4(b) 覆盖了(title 改回 X_label)，但簇文层执行者若照簇文操作会漏。**前置建议：R62 的 parity 测试(dossier §7 三套)须显式断言 title 属性前后相等，不止 text-meta div 零 diff。**

2. **【dossier 锚点漂移·低】LB02/LB05 注释交叉引用的 web 守卫宿主指向消费点而非定义点**：LB02 dossier §8 把 web 守卫写在 `reports_export_routes.py:100` + `reports_page_support.py:396`，但 `_layer2_residual` 已校正——`require_execution_review_adopted_plan` **定义在 reports_request_support.py:75**，`blocked_execution_review_plan_resolution` **定义在 reports_execution_review_context.py:8**；reports_page_support/reports_export_routes 只是 import 转用。A1 注释若按 LB02 dossier 交叉引用会指向消费点。**前置建议：A1 注释的「web 层另有入口守卫」交叉引用应指向真定义宿主 reports_request_support.py / reports_execution_review_context.py(与 _layer2_residual + LB06 认账注释口径一致)，避免锚点漂移。**

3. **【演进信号·低，非爆点】R62 收口固化「设计了真值通道但实现没接」**：`_state_resource_identity`(:431)用 `state.{prefix}_identity_label` 真身份构造 ResourceIdentity 的 identity_label 形参，但 `_resource_pair_payload`(:417)随即把 identity_label 压成 display **丢弃了这个真值**。R62 删键 = 固化「压扁」决定，运行期安全(现状就是压扁)，但这是 owner 该认账的演进信号(三档身份本有真值来源但实现没接)。dossier §4 反向兜底已提「若 owner 要恢复真三档身份则反向补齐」，**但未点明真值通道(:431→ResourceIdentity.identity_label)已存在却被 payload 丢弃**——若未来恢复，收口点是接通 payload :417 而非重建通道。非本轮阻塞，记为 owner 认账项。

4. **无环、无分层违规、无迁移耦合**(Q2/Q3 全簇过)：三成员均零新增 import，注释/删键不引入越层或导入环；不碰 schema/v18/v19 CHECK，无启动探针风险。
