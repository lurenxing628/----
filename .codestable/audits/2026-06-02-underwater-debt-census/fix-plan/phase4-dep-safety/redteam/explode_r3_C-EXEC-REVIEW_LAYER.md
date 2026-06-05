# 逐簇爆炸对抗 r3 · 簇 C-EXEC-REVIEW · 主透镜【分层导入环 + 迁移耦合】

> 只读不改 · 默认怀疑 · 行号全部 2026-06-05 工作区 rg 实测回盘（不信旧值）
> 成员债 [LB02, LB05, R62] · 主文件 core/services/report/execution_review.py（476 行 · git=MM）
> 主攻 Q2（分层导入环）/ Q3（迁移耦合），六质问点全过
> skeptic：找不到爆点才算绿；多维存疑即标红，不放过「测试绿但护栏已破」的静默失效

---

## 0) 本轮独立回盘命中（推翻/坐实）

| 锚点 | 计划值 | r3 rg 实测 | 判定 |
|---|---|---|---|
| 签名 `def execution_review(` 仅 version + 6 个 keyword-only（无 plan_role/scenario_id） | :209 | **:209-218 命中**，kw-only=date_from/date_to/batch_id/resource_type/resource_id | ✅一致 |
| scope 构造硬钉 `source_table=SOURCE_SCHEDULE` + `effective_plan_role=ROLE_ADOPTED` | :57/:58 | **:57 source_table=SOURCE_SCHEDULE / :58 effective_plan_role=ROLE_ADOPTED**（同一 from_values） | ✅一致（**第 7 处硬钉实为「两键同钉」，比计划描述更强**） |
| between/all 路硬钉 | :180-181 / :191-192 | **全命中** plan_role=ROLE_ADOPTED, scenario_id=None | ✅一致 |
| 入口 `_resolve_plan(v, ROLE_ADOPTED, None)` | :221 | **:221 命中** | ✅一致 |
| 返回 dict `"plan_role": ROLE_ADOPTED` | :236 | **:236 命中** | ✅一致 |
| R62 三档键（无前缀）exception/planned/actual | :358-359 / :361-362 / :373-375 / :380-382 | **全命中**（:358/359/361/362 + :373-375 + :380-382） | ✅一致 |
| `_resource_pair_payload` 三键恒等 display | :417 | **:417 `{"display_label": display, "identity_label": display, "export_label": display}`** | ✅一致 |
| `_actual_resource_identity` 无 feedback 早退三键 | :437-441 | **:438-440 内容 / :441 闭合**（块整体 437-441） | ✅一致（边界微差不影响） |
| 模板 `!=` 死副行 | :138/139/142/143 | **全命中** `{% if r.X_identity_label and r.X_identity_label != r.X_label %}` | ✅一致 |
| xlsx `or` 死回退 | :410/411/414/415 | **全命中** `row.get("X_export_label") or row.get("X_label")` | ✅一致 |

**结论：三 dossier 行号全部经 r3 独立 rg 复核命中，无漂移误导。**

---

## 主透镜 r3 新坐实的两条硬证据（计划未充分点名）

### ★ Q3 迁移耦合——adopted-only 是「服务硬钉 + v19 DB CHECK」双层冗余护栏（坐实，强化禁区神圣性）

r3 rg `core/infrastructure/migrations/v19.py` 实测：
```
:15  source_table        TEXT NOT NULL CHECK(source_table = 'schedule')
:19  effective_plan_role TEXT NOT NULL CHECK(effective_plan_role = 'adopted')
:23  UNIQUE(... batch_id, source_table, effective_plan_role, previous_state_revision)
```
而 execution_review.py :57-58 `OperationExecutionScope.from_values(source_table=SOURCE_SCHEDULE, effective_plan_role=ROLE_ADOPTED)` → :206 `get_execution_state_for_scopes(scopes)` 读 events。

**这是迁移耦合的核心证据**：adopted-only 不变量被**钉两次**——服务层 :57/:58 硬钉（fail-fast，DB 之前）+ v19 DB CHECK（最后防线，落库之时）。
- 含义 1（强化禁区）：:57/:58 不是「可有可无的冗余」，是「DB CHECK 的前哨」。删/参数化 :57-58 →scope 携非 adopted/非 schedule 值 → 命到 events 写读路径会触 **v19 CHECK IntegrityError**（loud 但是 DB 层崩，不是业务 loud）；或经 `_resolve_scenario_plan` 改 source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS 走**不在 CHECK 保护下的另一张表** → 预览静默冒充。两条出口都是事故。
- 含义 2（计划盲点）：三 dossier 把 :58 仅当「第 7 处硬钉、方向一致」，**没点明它与 v19 CHECK 的 source_table/effective_plan_role 双列 1:1 对应**。A1 注释**必须交叉引用 v19 CHECK**（「此处硬钉是 v19 `CHECK(effective_plan_role='adopted')`+`CHECK(source_table='schedule')` 的服务层前哨，改码不改迁移 = 启动探针/写库炸」），否则失忆债残留：后人只看到服务硬钉以为可松，不知 DB 层还钉着。

### ★ Q2 分层导入环——本簇 0 违规（坐实绿）

r3 rg 实测三文件 import：
- execution_review.py :6-14：`core.infrastructure.errors` / `core.models.*`（scope/resource_identity/schedule_plan_role）/ `core.services.scheduler.schedule_plan_query_service`（同层）/ 本包相对 `.calculations .exporters .report_number_parsing`。**无 core.models→core.services、无 repo→service 反向边。**
- xlsx.py :12-13：`core.services.common.excel_templates` / `core.services.report.report_number_parsing`（同层内）。
- 反向探针 `rg "^from core.services" core/models/` → **空，0 命中**（core.models 不依赖 core.services，无环）。
- R62 修法=删键/删模板副行/删 xlsx `or`，**新增 import = 0** → 不可能引新跨层边或环。
- A1/LB05 修法=纯注释，**新增符号 = 0** → 零分层风险。

**Q2 本簇判定：0 违规，baseline 与 fix 后均绿。** 本簇不是 LB04/R19 那类越层债的现场，主透镜在此簇的「分层导入环」维度天然安全——危险全部集中在 Q3 迁移耦合 + Q1 承重误删（见下）。

---

## 逐成员债判定

### 🟢 LB02 —— 承重不对称（刻意只复盘 ROLE_ADOPTED）· 纯注释
- 判定 **🟢 绿（修法=仅注释 + 回归既有契约，零删/零透传/零加形参）**。
- 证据（r3 实测）：签名 :209 确不收 plan_role/scenario_id；五处硬钉 :58/:180-181/:191-192/:221/:236 全在；契约 `tests/regression_execution_review_identity_guardrail.py` 存在（173 行，6 test fn，service+页+导出三层负向）。parity 盲区已闭合，**无需新建测试**。
- 绿的前提（禁区，不可越）：A1 注释**仅**在 :209 上方 + 五处硬钉旁补 `#`，不动任何表达式、不位移返回 dict（:233-244）键序。落注释后回归四组反例零变色；任一变色=误改表达式，立即回退。
- 主透镜补强：A1 注释须**显式钉回 v19 CHECK 双列**（见上 ★Q3），非仅写「兄弟报表签名不对称」。

### 🟢 LB05 —— 同一不对称第二 finding（服务层零注释）· 与 LB02 同点合并
- 判定 **🟢 绿（与 LB02 一次注释动作合并，落一段满足两条）**。
- 证据：五处硬钉与 LB02 完全同点；:58 两键同钉（source_table+effective_plan_role）经 r3 坐实，方向与不变量一致非削弱。LB05 dossier §B 已自纠「git 未修改」表述失实（实 MM/HEAD 407 行），但**承重不变量未被工作区改动削弱**（diff 仅新增点、原 6 处硬钉值零改）——r3 复核此结论成立。
- 绿的前提：同 LB02；A1 注释交叉引用 web 入口守卫 `require_execution_review_adopted_plan`（LB06 已 fixed=fail-CLOSED，**勿粘 §90 LB-B4 反向 fail-OPEN 文案**）+ v19 DB CHECK，形成「web 入口 / 服务硬钉 / DB CHECK」三层纵深认账。

### 🟢 R62 —— 三档身份压扁死分支清理（删 no-op）· Batch-3 后做
- 判定 **🟢 绿（删 no-op，行为逐字节不变，爆炸面闭合，承重区零重叠）**——但绿是**有铁前置条件**的，条件不满足即翻红，见下。
- 证据（r3 逐项坐实等价性根）：
  - `_resource_pair_payload` :407-417 **只读 `machine.display_label`/`operator.display_label`**，:417 三键全赋 `display`；即使 `_state_resource_identity` :431 给 ResourceIdentity 建了**不同的** `identity_label`（state.{prefix}_identity_label or _label），该值在 pair 层被**丢弃**——故无前缀 identity/export 键恒==display，删除等价成立。
  - 爆炸面闭合：r3 全仓 `rg --type py --type html` 无前缀键（planned/actual/exception 的 _identity_label/_export_label）**消费者仅 execution_review.py / 模板 / xlsx 三处**，web/路由及其它服务零读。grep 返回空，坐实 dossier §8。
  - 消歧坐实：带 `latest_`/`counterpart_` 前缀的 state 层 `*_identity_label`（operation_execution_state.py:45）是**真身份**、被 7+ 文件 PIN，**键名空间与 R62 无前缀键完全分离**。删 R62 绝不触真身份字段。
- **绿→红 的翻转条件（任一触发即 🔴）**：
  1. **三处不原子**（链 A）：只删 payload 三键、漏删 xlsx :410-415 `or` → `row.get("X_export_label")` 取 None、`or` 仍回退 → 留「键死回退活」新半截残骸；漏删模板 :138-143 `!=` → `r.X_identity_label` 取 None、`{% if None %}` 不炸但残骸留。**必须 dict 键 + 模板副行 + xlsx 回退 + 早退块（:438-440）同一 commit。**
  2. **删错对象**（链 B）：误把 state 层 `latest_*`/`counterpart_*` 真身份当 R62 残骸删 → resource_dispatch viewmodel 契约（regression_resource_dispatch_viewmodel_public_output_contract.py:68/71、test_resource_dispatch_viewmodel.py:239）全红。
  3. **碰护栏**（链 C）：手滑动 :57/:58/:180-181/:191-192/:221/:236 任一行 → 破 adopted-only + 触 v19 CHECK 耦合。
- 铁前置：A1 先落（Batch-1）→ R62 后做（Batch-3）；R62 动手前**按符号名 `_resource_pair_payload` + `!=`/`or` 模式重新 grep**，:357-444 区被 A1 注释下推、又被自身删键回缩，**绝不照抄任何档案行号**。
- 测试序：R62 收口面**零现成断言**，需先写三套 parity 快照（dict / xlsx / 模板）红→绿基线，再删；删后断言无前缀键消失且 _label 值逐格不变（Q6 测试迁移序：R62 是「先补 parity 网、再删」，非「先删后补」）。

---

## 六质问点逐条裁决（本簇）

- **Q1 承重误删**：🟢 三成员修法均无「以统一/DRY 名义抹承重」。禁区行 r3 全部按符号回盘列出（:57/:58/:180-181/:191-192/:221/:236/:209 签名）。**唯一红线**：R62 链 C（碰护栏）+ 任何人「顺手统一四张报表签名」给 :209 加形参——这是计划反复警告的灾难链，r3 坐实其物理路径（见 Q3）。
- **Q2 分层导入环**：🟢 **0 违规**。三文件 import 全同层/下层，core.models 不依赖 core.services（反向探针空），R62 删除/注释零新增 import。本簇非越层债现场。
- **Q3 迁移耦合**：🟡→认账强化。adopted-only = 服务硬钉(:57/:58) **+ v19 DB CHECK(source_table='schedule' / effective_plan_role='adopted') 双层冗余**。**不改码不改迁移本身安全**（A1/LB05 注释、R62 删 no-op 均不触 scope 构造、不改 schema）；但 A1 注释**必须新增对 v19 CHECK 的交叉引用**，否则失忆债残留（后人不知 DB 层也钉着）。改码不改迁移=启动探针/写库炸的风险**仅在违反禁区时触发**，本簇合法修法不触发。
- **Q4 灵魂线热路径**：🟢 本簇无 P4 raise 改造、无新增兜底/静默回退。A1 注释验证既有页面 loud 拦截 + 导出链置空（fail-CLOSED）；R62 删的 `or`/`!=` 是「展示降级」非「错误吞噬」，删除清 P3 残骸不触灵魂线。LB03 latest_executable_official_version 不在本簇面。
- **Q5 收口行为等价**：🟢 LB02/LB05 不收口（纯注释，无新旧两路）。R62 收口到**已存在**的 `_resource_pair_payload`(:417)，逐分支等价（identity/export 恒==display，五分支全产非空 str，无 None/raise 反例，早退块三键恒="暂无现场反馈"）。无 R09/R15 式「严格 vs 宽松」反例。
- **Q6 测试迁移序**：🟢 LB02/LB05 无测试迁移（注释 no-op，回归既有四组）。R62 收口面零断言→需**先新写**三套 parity 快照再删（先补网后删，序正确）；不可误迁 state 层 latest_*/counterpart_* 测试（属链 B 禁区）。

---

## 灾难链全图（仅在违反禁区时触发，本簇合法修法不触发——但必须钉死防后人误碰）

**违禁链（给 :209 加 plan_role/scenario_id 形参并透传）：**
```
:209 加形参 → report_plan_helpers.py:56-106 按 role/scenario 取明细（host 完全透传，不设防）
  → schedule_plan_query_service.resolve_plan_view:176 → scenario 非空切 _resolve_scenario_plan
    → source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS（:13 import）
      ├─[出口1 静默] 走 scenario rows 表（不在 v19 CHECK 保护下）→ 预览/对比方案明细拼进「计划vs实际」
      │              → export_execution_review_xlsx(:257) 导出 → 预览静默冒充正式现场复盘（违灵魂线，无 loud）
      └─[出口2 崩] 若 scope.effective_plan_role/source_table 携非 adopted/非 schedule 落 events
                   → v19 CHECK(effective_plan_role='adopted')/CHECK(source_table='schedule') → IntegrityError（DB 层崩）
当前缓解：regression_execution_review_identity_guardrail.py 四组反例在 CI/页/导出层挡住；
残余风险：绕页面直调透传后的 execution_review 且不更新该测试 → 漏 → 故 §90 LB-A2 注释必须钉回 :209 本地 + 交叉引用 v19 CHECK。
```

---

## 漏项 / 本轮新发现（计划未覆盖的爆点或缺失前置）

1. **【主透镜核心·中】A1 注释计划文案缺「v19 DB CHECK 交叉引用」**：三 dossier 把 :58 仅当「第 7 处硬钉、方向一致」，未点明 :57/:58 与 v19 `CHECK(source_table='schedule')`+`CHECK(effective_plan_role='adopted')` 双列 1:1 对应。A1 注释须补「此服务硬钉是 v19 DB CHECK 的前哨；改码不改迁移 = 写库触 IntegrityError 或经 scenario 表静默冒充」，否则失忆债残留。**非阻塞但必须并入 A1 文案。**
2. **【低】R62 早退块行号 dossier 标 :437-440，实测内容 :438-440 / 闭合 :441**——指代同一块，不影响「随 payload 收单键」修法；仅提醒按符号定位。
3. **【低·已被计划覆盖但再钉】R62 必须连 :438-440 早退块的三键一并收**（dossier §4 已列），漏收=第四处半截残骸。
4. **无新增跨簇爆点**：本簇唯一硬跨簇约束 LB06 已 fixed（fail-CLOSED，优于计划）→ 退化为认账协同；其余 same_symbol=false 弱边按符号并行即可，r3 未发现新阻塞边。
