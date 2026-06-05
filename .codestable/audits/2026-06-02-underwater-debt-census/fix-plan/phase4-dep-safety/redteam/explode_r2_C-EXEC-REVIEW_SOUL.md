# 逐簇爆炸对抗 R2 · C-EXEC-REVIEW · 主透镜 SOUL（灵魂线热路径 + 收口等价）

> skeptic 第 2 轮 · 只读不改 · 行号 2026-06-05 rg 回盘（execution_review.py 476 行 git=MM）
> 成员债 [LB02, LB05, R62] · 主文件 core/services/report/execution_review.py
> 默认怀疑：多数维度存疑即标红，不放过「测试绿但护栏已破」的静默失效。

---

## 0) 回盘真值表（rg 实测，本轮以此为唯一基准，旧值一律不信）

| 锚点 | 真实行 | 命中 |
|---|---|---|
| `import ROLE_ADOPTED, SOURCE_SCHEDULE` | :9 | ✅ |
| `effective_plan_role=ROLE_ADOPTED`（scope 构造，第 7 处硬钉） | :58 | ✅ |
| `_plan_identity_label` 兜底 `plan_role_label(ROLE_ADOPTED)` | :65 | ✅ |
| `_filename_part` 兜底 | :69 | ✅ |
| `_resolve_plan` Protocol 声明 | :121 | ✅ |
| `_list_plan_rows_between(plan_role=ROLE_ADOPTED, scenario_id=None)` | :180-181 | ✅ |
| `_list_plan_rows_all(plan_role=ROLE_ADOPTED, scenario_id=None)` | :191-192 | ✅ |
| `def execution_review(` 签名（刻意不收 plan_role/scenario_id） | :209 | ✅ |
| `host._resolve_plan(v, ROLE_ADOPTED, None)` | :221 | ✅ |
| 返回 dict `"plan_role": ROLE_ADOPTED` | :236 | ✅ |
| R62 exception 三连 `*_identity_label`/`*_export_label` | :358-362 | ✅ |
| R62 planned 三连 | :373-375 | ✅ |
| R62 actual 三连 | :380-382 | ✅ |
| R62 `_resource_pair_payload` 三键恒等 return | :417 | ✅ |
| R62 `_actual_resource_identity` 无 feedback 早退三键 | :438-440（块 :437-441） | ✅ |
| 模板 `!=` 死副行 | templates/reports/execution_review.html :138/139/142/143 | ✅ |
| xlsx `or` 死回退 | core/services/report/exporters/xlsx.py :410/411/414/415 | ✅ |

**漂移结论**：承重五处硬钉 + 签名 + R62 三档键全部命中档案 §1，无新漂移。registry 旧行号（HEAD=407 行那套 :112/:123/:153/:166-167）确已被工作区 +69~70 行未提交改动推漂，本轮以盘上 476 行为准。

---

## 1) 主透镜逐质问（Q4 灵魂线热路径 / Q5 收口等价）

### Q4 灵魂线热路径（P4 改 raise 落热路径？新增兜底/静默回退/吞错？）
- **本簇无 P4 raise 改写动作**。LB02/LB05 = 纯注释（零逻辑），R62 = 删 no-op 死分支（行为不变）。三成员均不在 LB03 `latest_executable_official_version` 扫历史热路径上，不新增任何 raise，不放大可用性。
- **灵魂线唯一真实风险来自「违规修法」而非「计划修法」**：若有人借 A1 之机给 :209 加形参透传 → 落 `report_plan_helpers` 透传热路径 → 静默切源表（见 Q5-灾难链），这恰是 A1 注释要钉死的。计划本身不触灵魂线。
- **R62 删的 `or`/`!=` 是「展示降级」非「错误吞噬」**：identity/export 是展示名变体（用于 hover title / 导出别名），删除不吞任何错误、不触灵魂线红线，反而清 P3 残骸。✅

### Q5 收口行为等价（逐分支 None vs raise 反例搜索）
- **LB02/LB05 不收口**（纯护栏注释，无新旧两路），无 parity 等价义务。
- **R62 收口源 `_resource_pair_payload`(:406-417) 逐分支等价已坐实**（读 :405-444）：
  - 五分支 display 全产**非空 str**（:410 `machine/operator`、:412 `machine/未安排人员`、:414 `未安排设备/operator`、:416 `empty_label`），三键 `{display,identity,export}` 全赋同一 display → identity 恒==label 恒==export，**无 None 边界**。
  - `_actual_resource_identity` 无 feedback 早退（:438-440）三键全="暂无现场反馈"，恒等。
  - `_exception_value_label`(:456-462) `return text or empty_text` 恒产非空 str，exception 三连(:358-362)同源同值。
  - 模板 `!=` 恒 False（identity==label），text-meta div 永不渲染；删副行后 HTML 逐字节不变。
  - xlsx `or` 永不回退（export==label 非空）；删 `or` 后 `row.get("X_label")` 取值完全相同。
  - **结论：无 None/raise 反例，新旧逐分支等价。R62 Q5 PASS。**
- **对照 R09/R15 收口陷阱**：本簇 R62 与那类「C 路严格→None vs A/B 宽松→5」的收口语义分叉**无关**——R62 三键同源恒等，不存在两路语义差。本簇不碰 R09/R15 收口面。

---

## 2) 逐成员债判定

### LB02 — 承重不对称（刻意只复盘 ROLE_ADOPTED，签名 :209 不收形参）
**判定：🟢 绿（安全）**，但带**一条必须随注释钉死的最危爆点**（见 §3）。

- **证据（盘上 rg）**：签名 :209 keyword-only 仅 version/date_from/date_to/batch_id/resource_type/resource_id，确证不收 plan_role/scenario_id；五处硬钉 :58/:180-181/:191-192/:221/:236 全命中。
- **Q1 承重误删**：修法=补 `#` 注释 + 回归既有 `regression_execution_review_identity_guardrail.py`(173 行,6 个 test_)，零删除/零统一/零透传/零加形参。禁区行明列。**无误删风险。**
- **Q2 分层环**：纯注释零新增 import，0 AST 违规。imports(:6-14)全同层/下层。✅
- **Q3 迁移耦合**：与 v18/v19 DB CHECK 无耦合（注释不碰 schema）。✅
- **Q4 灵魂线**：注释不新增兜底；既有测试已验页面 loud 拦截 + 导出链置空(`_export_links==[]`)。✅
- **Q5 等价**：不收口，无 parity 义务。✅
- **Q6 测试迁移序**：no-op，无需迁测试，仅回归。落注释后 4 组反例应零变化全绿。✅

### LB05 — 同一承重不对称第二 finding（同点合并）
**判定：🟢 绿（安全）**，与 LB02 **一次注释同时满足**，不可拆。

- **证据**：与 LB02 同钉 :58/:180-181/:191-192/:221/:236，外加类顶注释块 :136 附近。`require_execution_review_adopted_plan() -> Tuple[str, None]`(reports_request_support.py:75-79) 入口守卫返回 `ROLE_ADOPTED, None` 强制 scenario=None，**fail-CLOSED 已落**（与 _layer2_residual.md「本体在 reports_request_support + reports_execution_review_context，非 reports_page_support」口径一致）。
- **Q1-Q6 同 LB02**：纯注释，全绿。
- **协同令**：LB02/LB05/LB06 注释**须同批落齐**（纵深防御：服务层硬钉=数据层最后一道，web 守卫=入口拦截，任一层单独「统一」即打穿）。因 LB06 已 fail-CLOSED（结构性消除、优于计划），此协同退化为**认账注释**，非阻塞。A1 注释须交叉引用 web `require_execution_review_adopted_plan`。

### R62 — 三档身份压扁死分支清理
**判定：🟡 黄（有条件可做）**，条件 = ①A1 先落 ②动手前重 grep 回盘 ③三处原子同删 ④禁碰禁区行。

- **证据**：三档键 :358-382 + payload :417 + 早退 :438-440 + 模板 :138-143 + xlsx :410-415 全命中。无前缀键消费者**仅 execution_review.py / 模板 / xlsx 三处**（全仓 rg 剔 latest_/counterpart_ 后闭合）。
- **Q1 承重误删**：R62 收口段 :357-444 与护栏区 :58-236 **零行重叠、不同方法**。禁区行（:58/:65/:69/:121/:180-181/:191-192/:209/:221/:236）明令禁碰。条件守住即无误删。🟡
- **Q2 分层环**：纯删键/删模板副行/删 xlsx 回退，零新增 import，无新建模块，0 AST 违规。✅
- **Q3 迁移耦合**：不碰 schema/迁移。✅
- **Q4 灵魂线**：删「展示降级」非「错误吞噬」，不触灵魂线。✅
- **Q5 等价**：逐分支等价已坐实（见 §1-Q5），无 None/raise 反例。✅
- **Q6 测试迁移序**：R62 收口面 tests/ **零断言**（rg 验真：无前缀 `*_identity_label`/`*_export_label`/`_resource_pair_payload` 全 0 命中）→ **无现成测试可迁，须新写 3 套 parity 快照**（dict/xlsx/模板）作收口安全网。**消歧关键**：state 层 `latest_*`(:45/:50)/`actual_*`(:22/:27)/`counterpart_*` 真身份被 5 个测试 PIN，键名空间与 R62 无前缀键完全分离——**删 R62 绝不触及真身份字段**。🟡

---

## 3) 🔴 最危爆点完整灾难链（计划已覆盖，但必须钉死本地注释）

**爆点：A1（LB02/LB05）落地时「顺手统一四张报表签名」给 :209 加 plan_role/scenario_id 形参。**

完整灾难链（物理路径已逐跳 rg 坐实）：
```
给 execution_review(:209) 加形参 plan_role/scenario_id 并透传
  → report_plan_helpers._list_plan_rows_between/_all 完整透传（:60-114, plan_role→role :72, scenario_id→:73）
  → resolve_plan_view(schedule_plan_query_service.py:176)
  → scenario_key = str(scenario_id or "").strip() 非空(:182)
  → _resolve_scenario_plan(version, role, scenario_key)(:185 → def :460)
  → source_table = SOURCE_ADJUSTMENT_SCENARIO_ROWS（import :13）静默切取数源表，无 raise
  → 预览/对比方案明细拼进「计划 vs 实际」复盘
  → export_execution_review_xlsx(:257) 可导出
  → 返回 dict(:225-238) 不携带也不拦截 is_scenario_preview
  ⇒ 预览静默冒充正式现场复盘，导给车间且可导出，无 loud failure（违灵魂线）
```
**当前缓解**：`regression_execution_review_identity_guardrail.py` 6 组反例在 CI 层挡住请求级路径（页 + 导出）。**残余风险**：若有人绕页面、直接在新服务里调透传后的 execution_review 且不更新测试，仍可漏 → **§90 LB-A2 注释必须钉回 :209 本地**，把「不可加形参」写在改动点，而非只靠远端测试。**这是 A1 注释的核心价值，不是可选项。**

---

## 4) 🟡 条件清单（黄债前置/顺序/禁区）

- **R62 黄债四前置**（缺一即可能炸）：
  1. **A1 注释先落（Batch-1），R62 后做（Batch-3）**——承重神圣，给 R62「禁区已标注」参照。
  2. **动手前按符号名 `_resource_pair_payload` + `!=` 模式重新 grep**，A1 注释插入 :58-236 区会把 R62 的 :357-444 整体下推，绝不照抄行号。
  3. **三处消费方原子同删一个 commit**：删 payload 三键 + 模板 `!=` 副行（title 改回 `X_label`）+ xlsx `or` 回退。任一不同步 = 留新半截残骸（链 A：xlsx 取 None 回退仍在 / 模板 `{% if None %}` 仍 False）。
  4. **新写 3 套 parity 快照先红→绿基线**（dict/xlsx/模板逐字节），收口面零现成断言。
- **禁区行（R62 绝不可碰，盘上实证）**：:58 / :65 / :69 / :121 / :180-181 / :191-192 / :209 签名 / :221 / :236。
- **灾难链 B（误删对象）**：误把 state 层 `latest_*_identity_label`(:45/:50) 当 R62 残骸删 → resource_dispatch viewmodel 契约 + operation_execution 系列断言全红（真炸）。消歧：R62 收无前缀键，真身份带 latest_/actual_/counterpart_ 前缀。

---

## 5) 漏项（本轮新发现，没被计划充分覆盖的爆点/缺失前置）

1. **`_state_resource_identity`(:431) 真身份在 :407 被二次丢弃**（新发现，非债边但揭示压扁机理）：:431 `identity_label=getattr(state, identity_label) or getattr(state, label)` 把 state 真身份构造进 ResourceIdentity，但 `_resource_pair_payload`(:407-408) **只读 `.display_label`、丢弃 `.identity_label`** → 这是「三档压扁」的物理根因。**对 R62 的提示**：若 Phase2 owner 反向要恢复真三档身份，不止改 :417 三键，还须改 :407-408 让 payload 读 `machine.identity_label`——**当前 R62 计划（收成单键）默认压扁方向，若 owner 裁反向则 :407-408 也是改点**，计划文档未点名这一行，建议补登为 R62 反向分支的隐藏改点。owner_pending 仅标不给终态。

2. **xlsx 删 `or` 后的 KeyError vs None 语义需确认**（低危但计划未明示）：xlsx :410-415 用 `row.get("X_export_label") or row.get("X_label")`，删 export_label 键后改为 `row.get("X_label")`。若误改成 `row["X_label"]`（下标）则在缺键行 KeyError。计划文案写「→ `row.get("X_label")`」正确，但须**显式禁止改成下标访问**——建议 R62 执行注记补一句「保持 `.get` 形态」。

3. **模板 :138-143 的 `title=` 属性也读 identity_label**（计划已提但易漏执行）：删 identity_label 键后，:138 `<td title="{{ r.exception_affected_machine_identity_label }}">` 与 :142/:143 同——**title 须同步改回 `X_label`**，否则 title 渲染空字符串（Jinja undefined→空），是静默展示退化非崩溃，但属「三处原子」里模板那处的**两改点**（`!=` 副行 + title），计划 §4(b) 已述「title 改回 X_label」，执行时勿只删 `!=` 块漏 title。

4. **LB06 认账注释宿主双文件别落错**（流程前置，_layer2_residual.md D4 已标）：fail-CLOSED 本体在 `reports_request_support.py`(:65/:75 require_/error) + `reports_execution_review_context.py`(:8 blocked_)，**非 reports_page_support.py**（后者仅 :396/:408 调用方）。A1 交叉引用注释须指向前两者，且**勿粘 §90 LB-B4 反向文案**（LB-B4 描述治理前 fail-OPEN，现盘已 fail-CLOSED）。owner 须认账此偏离入账。
