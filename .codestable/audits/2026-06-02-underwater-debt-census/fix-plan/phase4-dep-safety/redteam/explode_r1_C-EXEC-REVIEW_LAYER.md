# 逐簇爆炸对抗 r1 · C-EXEC-REVIEW（主透镜：分层导入环+迁移耦合）

> skeptic 第1轮，只读不改。默认怀疑——这一簇按计划改下去会不会连环炸？
> 主文件 core/services/report/execution_review.py（476 行，git=MM，工作区相对 HEAD +69~70 行）
> 成员债 [LB02, LB05, R62] · 2026-06-05 rg/Read 实证回盘
> 回盘命中：硬钉 :58/:180-181/:191-192/:221/:236 · 签名 :209-218（确不收 plan_role/scenario_id）· import ROLE_ADOPTED :9 · Protocol _resolve_plan :121 —— 与三份 dossier §1 盘上表逐行一致，无漂移分歧。

---

## 0) 本轮回盘新证据（dossier 之外 / 加固或纠偏）

1. **灾难链物理路径全程坐实**（Q4/Q1 关键）：
   - `report_plan_helpers._resolve_plan`(:37) → `resolve_plan_view(version, plan_role, scenario_id)` **完整透传**（实证 helpers.py:37/:72-73/:95/:100）。
   - `schedule_plan_query_service.resolve_plan_view`(:176) → scenario_key 非空即 :185 `_resolve_scenario_plan` → `source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS`（import :13，:160/:168/:171 整组 scenario 分支）。
   - 即「给 execution_review 加形参并透传 → 静默切 scenario 取数源 → 预览/对比方案以正式复盘身份导出」是**真实可达的物理路径**，非臆测。LB02/LB05 五处硬钉是读路径**唯一最后一道**。
2. **Q3 迁移耦合——关键纠偏（dossier 未展开）**：v19 有 DB 级硬 CHECK `CHECK(source_table='schedule')` + `CHECK(effective_plan_role='adopted')`（v19.py:14-19）。但**这是 OperationExecutionEvents 写路径的 CHECK，不挡读/报表路径**。execution_review 是读侧，:58 用 `effective_plan_role=ROLE_ADOPTED` 构造 scope 去查——DB CHECK 不会在读侧拦截透传后的 scenario 查询。
   - **双向含义**：(a) 改码不改迁移**不会**炸启动探针（CHECK 针对写表，读侧无 DDL 依赖）——Q3「改码不改迁移=启动炸」在本簇**不成立**，安全；(b) 但反过来 DB CHECK 也**救不了**读侧透传灾难——读侧护栏 100% 压在 LB02/LB05 应用层硬钉 + 请求级测试上。**这放大了 LB02/LB05 注释欠补的严重度**。
3. **R62 等价性根坐实**：`_resource_pair_payload`(:407-408) 只读 `.display_label`，**从不读 `.identity_label`**；exception 路 :321 显式只取 `affected_machine.display_label`；planned/actual :373-382 三键全 = `["display_label"]`。:431 读进的真 identity_label 在报表路**确为死值**。三键恒等成立，删除逐字节等价（Q5 通过）。
4. **R62 模板耦合放大**（dossier 已述但本轮加固）：模板 :138/:139/:142/:143 不仅 `!=` 死副行用 `*_identity_label`，**`title="{{ r.*_identity_label }}"` 也用它**。R62 删 identity 键必须**同步把 title 改回 `*_label`**，否则 title 取 Jinja undefined（渲染空 title）——非崩溃但留半截残骸。

---

## 1) 逐成员债判定

### LB02 + LB05（A1 同点合并，承重 P2，load_bearing=true）→ 🟡 黄（有条件可做）

**判定理由**：修法是「纯注释 + 回归既有测试」，本身零删除/零透传/零加形参，技术上安全。但标 🟡 而非 🟢，因为**护栏当前处于「测试已立、本地注释欠补」的半截 in_progress 态**，且 Q3 纠偏揭示读侧 DB CHECK 不兜底——这条注释不是「锦上添花」，是**读路径唯一本地护栏的最后拼图**。条件不满足就放行会留下静默失效窗口。

**承重误删核（Q1）**：✅ 五处禁区行 :58/:180-181/:191-192/:221/:236 + 签名 :209 全程不得碰。dossier 修法已锁死为仅注释。无 DRY/统一/对齐签名名义抹护栏的动作。**通过**。

**分层导入环（Q2）**：✅ 纯注释零新增 import。现状 import（:6-14）全合规：core.services.report → core.models/infra/同层 services，无 core.models→core.services、无 repo→service 越层。0 违规。**通过**。

**灵魂线（Q4）**：✅ 注释不新增兜底/静默回退。现有 guardrail 测试已验页面 loud 拦截 + 导出链置空（:68-72/:84-88/:100-103）。**通过**。

**完整灾难链（若违规放行 = 给 :209 加形参）**：
```
统一四张报表签名 → execution_review(:209) 加 plan_role/scenario_id 形参并透传
→ report_plan_helpers._resolve_plan(:37) 透传 → resolve_plan_view(:176)
→ scenario 非空切 _resolve_scenario_plan(:185) → source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS
→ 预览/对比方案明细拼进「计划 vs 实际」→ export_execution_review_xlsx 导出
→ 返回 dict(:233-) 不携带 is_scenario_preview、无 loud raise
→ 预览静默冒充正式现场复盘给车间（违灵魂线 + 数据完整性事故）
```
**当前缓解**：guardrail 测试四组反例在**请求级**（GET 页/导出）挡住。**残余风险**（坐实）：测试全是 request-level（:63/:78/:95/:107），**绕页面在新服务里直调透传后的 execution_review 不被任何测试覆盖**；而本地注释又未补 → 此刻护栏依赖「远端请求级测试 + reviewer 警惕」，无改动点本地警示。

**🟡 放行条件（必须同批落齐）**：
- (前置) F-门-1 基线四组 regression 全绿（identity_guardrail / plan_vs_actual_review / workbench_link_guardrails / workbench_navigation+backlink_contract）。
- (动作) §90 LB-A2 注释钉回 :209 签名上方 + 五处硬钉旁短注（含新发现第 7 处 :58）；注释须交叉引用 web 层 `require_execution_review_adopted_plan`（reports_request_support.py / reports_execution_review_context.py，非 reports_page_support.py——见 _layer2_residual D 节）。
- (协同) 与 LB06 认账注释同批；LB06 已 fixed 为 fail-CLOSED，**勿粘 §90 LB-B4 反向 fail-OPEN 文案**。
- (自证) F-门-3 重跑四组全绿 + `git diff` 仅注释行变化、零逻辑行改动。
- (禁区) 绝不顺手「统一四张报表签名」加形参——此即灾难链入口。

---

### R62（三档身份压扁死分支清理，P3，承重 false）→ 🟡 黄（有条件可做）

**判定理由**：等价性 Q5 实证通过（三键恒等、删除逐字节等价），运行期零风险。但标 🟡 而非 🟢，因为：(1) **三处消费方强原子耦合**（dict 键 / 模板 title+`!=` / xlsx `or`），任一不同步即 KeyError/取 None/留半截残骸；(2) **承重高危同居**——R62 收口段 :357-444 与 LB02/LB05 禁区段 :58-236 同文件，手滑碰禁区即破护栏；(3) **R62 收口面零现成测试**，删前须新写 parity 安全网，否则「等价」无机器自证。

**承重误删核（Q1）**：✅ R62 收口段（payload :406-417 / dict 三连 :357-382 / actual 早退 :437-441）与护栏段 :58-236 **不同方法、零行重叠**（实证）。但**强提醒禁区**：R62 删键时 :58-236 任何 ROLE_ADOPTED 行 + :209 签名为绝对禁区。

**误删对象核（链 B，关键防误删）**：✅ 必须区分 R62 收口面（**无前缀** `exception_affected_machine_identity_label` 等，恒=display 压扁值）vs state 层真身份（**带 `latest_`/`counterpart_` 前缀** `latest_exception_affected_machine_identity_label`，定义 operation_execution_state.py，被 7+ 文件 PIN 真值断言）。删 R62 无前缀键**绝不可触** state 层真身份字段，否则 resource_dispatch viewmodel 契约测试全红（真炸）。

**分层导入环（Q2）**：✅ 纯删键 + 删模板副行 + 删 xlsx 回退，零新增 import，无新建模块，无跨层。三处文件 execution_review.py(core.services.report)/xlsx.py(.exporters)/html(templates) 同层或模板层。0 违规。**通过**。

**灵魂线（Q4）**：✅ 模板 `!=` 与 xlsx `or` 是「展示降级」非「错误吞噬」，删除清 P3 残骸不触灵魂线。**通过**。

**收口等价（Q5）**：✅ 逐分支搜反例落空——payload :407-417 五分支全产非空 str，identity 恒==label，无 None vs raise 反例；actual 早退三键恒="暂无现场反馈"；exception 三键同源 affected_*_label。**等价成立**。

**完整灾难链（若三处不原子 / 删错对象）**：
- **链 A（不原子）**：只删 payload/dict 三键、漏删 xlsx `or` → `row.get("*_export_label")` 取 None，`or row.get("*_label")` 仍回退（不炸但留半截）；漏删模板 → `r.*_identity_label` 取 Jinja undefined，`title` 渲染空、`{% if undefined %}` 仍 False（不炸但残骸+title 退化）。**静默债务累积**。
- **链 B（删错对象）**：误把 state 层 `latest_*_identity_label` 真身份当残骸删 → resource_dispatch viewmodel 契约测试（regression_resource_dispatch_viewmodel_public_output_contract.py / test_resource_dispatch_viewmodel.py 断 `counterpart_resource_identity_label`="MC001 数控车床1"）+ operation_execution 系列全红。**真炸**。
- **链 C（碰护栏）**：手滑动 :58-236 → 破 LB02/LB05 adopted-only 语义，复盘错读 scenario 草稿。**绝对禁区**。

**🟡 放行条件**：
- (前置) **A1 注释先落（Batch-1）**，R62 后做（Batch-3）——承重神圣，禁区先钉注释给 R62 一个「禁区已标注」参照。
- (行号门) A1 注释插 :58-236 区会把 R62 :357-444 整体下推；R62 动手前**必须按符号名 `_resource_pair_payload` + `!=` 模式 + `export_label or` 模式重新 grep**，绝不照抄任何档案/本文行号。
- (原子门) 三处消费方**同 commit** 删齐：execution_review dict 三连+payload+actual 早退 / 模板 :138-143（删 `!=` 副行 + title 改回 `*_label`）/ xlsx :410-415（删 `or` 回退）。
- (安全网) 删前新写 §7 三套 parity 快照（dict / xlsx / 模板），红→绿基线自证零行为差异（R62 收口面当前零现成测试）。
- (禁区) state 层 `latest_*`/`counterpart_*` 真身份字段绝不触；:58-236 护栏段绝不触。

---

## 2) 跨簇硬约束复核

- **LB06**：已 fixed（结构性消除为页级 identity_error+blocked，fail-CLOSED，未 fail-open，契约 regression_execution_review_identity_guardrail 钉死）→ 与 A1 的「同护栏纵深同批」退化为**认账协同**，非阻塞。**注**：认账注释宿主应落 `reports_request_support.py` + `reports_execution_review_context.py`（_layer2_residual D 节纠正，**非** reports_page_support.py）；勿粘 LB-B4 反向 fail-OPEN 文案。
- 其余 same_symbol=false 边（R14/R61/R42/R54/R56/R57/R58/R60/R66）均共宿主文件弱碰撞，按符号名定位并行，非阻塞。

---

## 3) Q3 迁移耦合专项结论

- adopted-only 不变量已下沉 v19 DB CHECK（`source_table='schedule'` + `effective_plan_role='adopted'`），但**仅在写表（OperationExecutionEvents）维度**。
- 本簇三债**均不动 DDL/迁移**——「改码不改迁移=启动探针炸」在本簇**不成立**（读侧无迁移依赖）。
- 但 DB CHECK 不护读侧：读路径透传灾难（LB02/LB05 灾难链）DB 层不兜底 → 读侧护栏全压应用层硬钉 + 请求级测试，**故 A1 注释欠补的严重度被这一事实放大**，是 LB02/LB05 标 🟡 不标 🟢 的核心依据。

---

## 4) 本轮新发现漏项（计划未覆盖 / 缺失前置）

1. **【中】读侧 vs 写侧护栏断层（计划未点明）**：v19 DB CHECK 只护写路径，execution_review 读路径透传灾难**无任何 DB 兜底**。三份 dossier 把「adopted-only 已下沉 DB」当普适护栏，未区分读/写——读侧 100% 依赖应用层 LB02/LB05 + 请求级测试。**前置补强建议**：A1 注释文案须明确写「读侧无 DB CHECK 兜底，此硬钉是读路径唯一最后一道」，避免后人误以为 DB 会兜。
2. **【中】请求级测试覆盖盲区未闭合（dossier 已点但无前置动作）**：guardrail 四组反例全 request-level，**直调 service `execution_review(version, plan_role=非adopted)` 无单元级断言**。当前签名不收形参故类型层不可达，但这正是「靠签名形状当护栏」——一旦有人加形参，类型护栏即失效且无单元测试接住。**前置补强建议**：可选在 A1 批补一条「签名形状契约」单元断言（assert `execution_review` 形参集恰为 {version,date_from,date_to,batch_id,resource_type,resource_id}），把「不可加形参」机器化，而非只靠注释 + reviewer。
3. **【低】R62 模板 title 退化未在原子门显式列为失败项**：dossier §4 提了 title 改回，但「漏改 title → 空 title」未列入链 A 残骸清单。本文已补入 R62 原子门。
4. **【低】LB06 认账注释宿主在 dossier 仍写 reports_page_support.py**：与 _layer2_residual D 节（本体在 reports_request_support.py + reports_execution_review_context.py）矛盾。A1 协同认账须按 _layer2 权威宿主落，否则注释贴错文件。

---

## 5) 总判定

| 债 | 判定 | 一句话 |
|---|---|---|
| LB02+LB05 | 🟡 | 纯注释本安全，但读侧 DB CHECK 不兜底、本地注释欠补、请求级测试有直调盲区——须同批落齐注释+交叉引用+签名形状自证才放行 |
| R62 | 🟡 | 等价性实证通过，但三处强原子耦合（含模板 title）+ 承重高危同居 + 收口面零现成测试——须 A1 先落、重 grep、同 commit、新写 parity 网才放行 |

**本簇无 🟢**（两条均有未满足前置条件，非「拿来即改」）。**本簇无 🔴**（找不到「按计划改即必炸」的爆点——计划的禁区/顺序/parity 约束若全守则不炸；风险全在「条件不满足时放行」的静默失效，故为 🟡）。
