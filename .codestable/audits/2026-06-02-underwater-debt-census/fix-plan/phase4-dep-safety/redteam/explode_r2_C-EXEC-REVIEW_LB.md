# 逐簇爆炸对抗 r2 · C-EXEC-REVIEW · 主透镜【承重误删】

> skeptic 第2轮 · 只读不改 · 默认怀疑 · 2026-06-05 工作区 rg 独立回盘(不信旧值)
> 成员债 [LB02, LB05, R62] · 主文件 core/services/report/execution_review.py(476行, git=MM)
> 主透镜 Q1 承重误删为重，复核 r1 结论是否经得起第二轮捶打，并主攻本簇危爆点：给 execution_review 加形参/透传 → 预览冒充正式复盘。

## 判定速览（与 r1 一致，独立重盘后维持）

| 债 | 判定 | 一句话 |
|---|---|---|
| LB02 | 🟢绿 | 纯护栏注释，五处禁区行只补 `#` 不动表达式；最大盲区(请求级回归)已闭合，签名实测不收 plan_role/scenario_id |
| LB05 | 🟢绿 | 与 LB02 同点同动作，一次注释满足两条；纯增量、零结构改 |
| R62 | 🟡黄 | 删 no-op 三档死分支行为等价，但**原子面四处(含模板 title 属性)** + **行号重 grep 门** + **禁区零重叠须自证**，三条件全满足才安全 |

## 独立回盘附证（2026-06-05 rg 实测，逐符号命中，不信 dossier 旧值）

- **承重五处硬钉 + 签名全命中**：`:9`(import ROLE_ADOPTED,SOURCE_SCHEDULE) / `:58`(effective_plan_role=ROLE_ADOPTED scope 构造) / `:121`(Protocol `_resolve_plan(version, plan_role, scenario_id=None)`) / `:180-181`(between 路 plan_role=ROLE_ADOPTED,scenario_id=None) / `:191-192`(all 路) / `:209`(签名) / `:221`(host._resolve_plan(v, ROLE_ADOPTED, None)) / `:236`("plan_role": ROLE_ADOPTED)。
- **签名 :209-217 keyword-only 实测仅** version/date_from/date_to/batch_id/resource_type/resource_id —— **确证不收 plan_role/scenario_id，承重不对称坐实**。
- **危爆点物理路径坐实(主透镜)**：`report_plan_helpers.py` `_resolve_plan`(:29-37)/`_list_plan_rows_between`(:56-73)/`_list_plan_rows_all`(:83-100) **完整透传** plan_role/scenario_id → `resolve_plan_view` → scenario 非空切 `_resolve_scenario_plan` 换 source_table，**无 raise、静默换源表**。故 execution_review 五处硬钉是数据层最后一道。**纵深第二道实测在场**：`reports_request_support.py:75 require_execution_review_adopted_plan() -> Tuple[str, None]`(web 入口也钉死 scenario=None)+ `reports_execution_review_context.py:8 blocked_execution_review_plan_resolution`(页级 fail-CLOSED)。
- **`core/services/report/` 全仓无第二份 adopted-only 解析副本**(rg `ROLE_ADOPTED, None` 仅命中 execution_review.py:221)——**无「5套guard漏拷一键」式 fail-open 风险**，硬钉唯一不可被「DRY 合并」。
- **R62 三档键恒等坐实**：`_resource_pair_payload`(:406) 五分支 display 恒非空 str，:417 `{"display_label":display,"identity_label":display,"export_label":display}` 三键恒等；dict 装配 :358-359/:361-362/:374-375/:381-382；actual 早退 :438-440(块 :437-441) 三键恒="暂无现场反馈"。
- **R62 爆炸面闭合(独立全仓 rg)**：无前缀键(planned/actual_resource_identity_label、*_export_label、exception_affected_*_identity_label)消费者**仅 3 文件**(execution_review.py 自产 / 模板 :138-143 / xlsx.py :410-415)，**无 web/路由或其它服务读取**。state 层真身份 `latest_*_identity_label`(operation_execution_state.py:45) + `counterpart_*` 是另一键空间，R62 不触。
- **模板四处坐实**：每行 `title="{{ r.X_identity_label }}"` + `{% if X_identity_label and X_identity_label != X_label %}<div text-meta>`，:138/139/142/143。**title 属性同读 identity_label 键**。

## 逐债判定 + 灾难链/修正

### LB02 — 🟢绿（承重护栏注释，安全）
六质问点逐过：Q1 五处禁区行仅补注释零改表达式→无 fail-open；Q2 纯注释零新增 import(:6-14 全同层/下层)→0 越层/0 环；Q3 不碰 schema/v18·v19 CHECK→无探针炸；Q4 不新增兜底，既有测试验页面 loud 拦截+导出链置空→不触灵魂线；Q5 不收口(adopted-only 已收敛在已存在单点 :121/:221)→无新旧两路；Q6 不删 facade/不改签名→只回归 6 组护栏测试，no-op 应零变色。**主透镜被注释阻止的灾难链(非本债引入)**：他人「统一四张报表签名」给 :209 加形参→helpers 透传→resolve_plan_view scenario 非空切 _resolve_scenario_plan 换 source_table→预览/对比方案以「正式现场复盘」身份导出→静默冒充违灵魂线。当前 guardrail 测试 CI 挡住，残余=绕页面直调新服务，故注释必须钉回 :209 本地——**LB02 注释正是防爆护栏本身**。

### LB05 — 🟢绿（与 LB02 同点，一次注释合并）
LB05≡LB02 第二 finding，钉同一段(签名 :209 + 五处硬钉)。同一次注释 + 同组回归满足两条，只新增 `#` 行、不动 dict 键序、不位移返回 dict(:225-238)。六质问点裁决同 LB02 全绿。

### R62 — 🟡黄（删 no-op 等价，但三条件必满足，否则降红）
三键恒等→删 no-op 对所有边界值逐分支等价，无 None/raise 反例(早退 :438-440 恒="暂无现场反馈"、exception 簇 :358-359 同源 affected_machine_label)。运行期零风险、lb=false。**三条件**：
- **条件1(爆点·簇文 §A2 覆盖缺口)——模板原子面是「四处」**：簇文只列 :138/139/142/143 `!=` 死副行，**漏同行 `title="{{ X_identity_label }}"` 也读 identity_label 键**。删键后只删 `!=` 副行、漏改 title → Jinja2 取 undefined → `title=""` → **可观测 HTML 属性退化(hover 提示/可访问性丢失)，非逐字节等价**。修正：R62 原子面 = payload(:417) + dict(:358-382) + **模板「`!=`副行 + title 属性」两处同改**(title 改回 `{{ X_label }}`，恒等值不变) + xlsx(:410-415)。dossier §4(b) 已写对，**簇文 A2 须补**，执行者勿只照簇文删 `!=`；parity 测试须同断 title 属性，不止 text-meta div。
- **条件2(行号重 grep 门)**：A1 注释先落把 R62 :358-441 下推、删键又回缩。R62 动手前**必须按符号名 `_resource_pair_payload` + `!=` 模式重 grep**，绝不照抄 dossier/簇文行号。
- **条件3(禁区零重叠须自证)**：R62 收口段(:358-441)与护栏禁区(:58-236)不同方法零行重叠——但删键时**绝不顺手碰** :58/:180-181/:191-192/:221/:236/:209，**禁顺手「统一四张报表签名」加形参**(灾难链同 LB02)。`:431 _state_resource_identity` 读 `state.{prefix}_identity_label` 是 state 层真身份(actual_machine 前缀)，与 R62 无前缀键不同空间。**消歧灾难链 B**：误把 state 层 `latest_*/counterpart_*_identity_label` 当 R62 残骸删→resource_dispatch viewmodel 契约+operation_execution 系列全红(真炸)；R62 只删 execution_review 无前缀键，前提是执行者认清两键空间。

## 漏项（本轮新发现 / r1 已发现须固化）

1. **【簇文覆盖缺口·中·复核坐实】R62 模板原子面少算一处 title 属性**(r1 已发现，r2 独立重盘确认):簇文 §A2 仅列 `!=` 死副行，漏 `title="{{ X_identity_label }}"`。删键漏改 title → `title=""` 可观测降级。**前置：R62 parity 测试须显式断 title 属性前后相等。**
2. **【认账口径·低·r2 确认修正】A1 注释 web 守卫交叉引用须指真定义宿主**:LB02 dossier §8 把 web 守卫写 `reports_export_routes.py:100`+`reports_page_support.py:396`(消费点)；r2 实测**定义点**=`reports_request_support.py:75 require_execution_review_adopted_plan() -> Tuple[str,None]` + `reports_execution_review_context.py:8 blocked_execution_review_plan_resolution`(与 _layer2_residual / LB06 认账口径一致)。A1 注释交叉引用应指定义宿主，避免锚点漂移。
3. **【主透镜·绿强化】无「5套guard漏拷一键」fail-open**:`core/services/report/` 全仓仅 execution_review.py:221 一份 `ROLE_ADOPTED, None` 解析，无第二副本可被 DRY 合并;web 入口 `require_execution_review_adopted_plan` 返回类型 `Tuple[str, None]` 在类型层钉死 scenario=None=纵深第二道。硬钉唯一性坐实，承重不可统一。
4. **【演进信号·低·非阻塞】R62 固化「真值通道已存在但被丢弃」**:`_state_resource_identity`(:431)用 `state.{prefix}_identity_label` 真身份构 ResourceIdentity.identity_label，但 `_resource_pair_payload`(:417)随即压成 display 丢弃。R62 删键=固化压扁(现状安全)，但真值来源在场。若未来恢复三档身份，收口点是接通 :417 而非重建——owner 认账项。
5. **无环、无分层违规、无迁移耦合(Q2/Q3 全簇过)**:三成员零新增 import,不碰 schema/v18·v19 CHECK,无启动探针风险。
