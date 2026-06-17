# 逐簇爆炸对抗 r1 · C-EXEC-REVIEW · 主透镜 SOUL（灵魂线热路径+收口等价）

> skeptic 只读不改 · 2026-06-05 工作区 rg 回盘 · 默认怀疑
> 成员债 [LB02, LB05, R62] · 主文件 core/services/report/execution_review.py（476 行, git=MM）
> 本轮重攻 Q4(灵魂线热路径)/Q5(收口等价)/Q6(测试迁移序)；全六点过一遍。

## 0) 行号回盘自核（不信旧值，全部 rg 实测命中）

| 锚点 | dossier 值 | rg 实测 | 一致 |
|---|---|---|---|
| import ROLE_ADOPTED | :9 | :9 | ✅ |
| effective_plan_role=ROLE_ADOPTED (scope) | :58 | :58 | ✅ |
| _resolve_plan Protocol | :121 | :121 | ✅ |
| _list_plan_rows_between 硬钉 | :180-181 | :180-181 | ✅ |
| _list_plan_rows_all 硬钉 | :191-192 | :191-192 | ✅ |
| def execution_review 签名 | :209 | :209 | ✅ |
| host._resolve_plan(v, ROLE_ADOPTED, None) | :221 | :221 | ✅ |
| 返回 dict "plan_role": ROLE_ADOPTED | :236 | :236 | ✅ |
| _resource_pair_payload 定义 | :406 | :406 | ✅ |
| payload 三键恒等 return | :417 | :417 | ✅ |
| exception 三连 | :357-362 | :358/359/361/362 | ✅ |
| planned 三连 | :373-375 | :373-375 | ✅ |
| actual 三连 | :380-382 | :380-382 | ✅ |
| actual 早退三键 | :437-441 | :438-440 内容/441 闭合 | ✅ |
| 模板 != 死副行 | :138-143 | :138/139/142/143 | ✅ |
| xlsx or 死回退 | :410-415 | :410/411/414/415 | ✅ |

全部命中。dossier 行号可信。

---

## 1) LB02 — 🟢绿（安全，但带一条放大警告）

**判定 🟢绿**：计划修法=纯 `#` 注释 + 回归既有 173 行 guardrail 测试，零删除/零透传/零加形参。承重铁律 3 守住。

**逐质问点**：
- Q1 承重误删：无。修法只在 :209 签名上方 + 五处硬钉(:58/:180-181/:191-192/:221/:236)旁补注释，不动表达式、不动 dict 键序。
- Q2 分层导入环：0。imports(:1-14)全在 core.infrastructure/core.models/同层 core.services + 本包相对，注释零新增符号，不可能造越层或环。
- Q3 迁移耦合：无。注释不碰 schema/v18/v19 CHECK。
- Q4 灵魂线热路径：**不新增兜底**。反而既有 guardrail 测试已验页面 loud 拦截 + 导出链置空(`_export_links==[]`)，符合 P4。注释把"不可加形参"钉回改动点本地，强化灵魂线。
- Q5 收口等价：不涉收口（纯护栏注释，adopted-only 不变量本就收敛在已存在单点 `_resolve_plan` :121/:221）。
- Q6 测试迁移序：无需迁移，只回归。

**灾难链（仅当违规改 :209 才触发，已被测试挡）**：物理坐实——helpers `_resolve_plan`(:37)完整透传 → `resolve_plan_view`(:176) scenario_key 非空(:182) → `_resolve_scenario_plan`(:185) **静默切 source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS，无 raise** → 预览/对比方案冒充正式复盘并导出。残余风险=绕页面直调新服务，故 §90 LB-A2 注释必须钉回 :209。当前 guardrail 6 测试在 CI 层挡住。

**前置/禁区**：禁加 plan_role/scenario_id 形参到 :209；禁把五处硬钉改透传。

## 2) LB05 — 🟢绿（与 LB02 同点，一次注释合并）

**判定 🟢绿**：同 LB02，是同一承重不对称的第二 finding，钉同一段。一次注释动作同时满足两条，不位移返回 dict 键。owner_pending=false，被铁律 3 锁死为仅注释+回归。

**逐质问点同 LB02**。补两点本轮实证：
- 第 7 处硬钉 :58 `effective_plan_role=ROLE_ADOPTED` 实测命中（工作区新增 scope 构造，registry 未列），方向与 adopted-only 不变量**一致非削弱**，A1 注释覆盖面 +1 行。
- Q5 放开时的 parity 反例（非本批）：service 对非 adopted role/非 None scenario **必须 loud raise ValidationError，绝不默默回退 adopted**（None vs raise 不可混）。本批不放开，仅守住既有 GET 级负向断言不破。

## 3) R62 — 🟡黄（有条件可做：删 no-op，但等价性有一条裂缝 + 强原子三处必须同 commit）

**判定 🟡黄**（dossier 报 low/安全，本轮压到黄——非否定方向，而是 dossier §7「逐字节不变」论证有一处裂缝须前置补测）。

**逐质问点**：
- Q1 承重误删：R62 收口段 :357-417 与护栏区 :58-236 **不同方法、零行重叠**（实测）。前提是动手前按符号名 `_resource_pair_payload`+`!=` 模式重 grep（A1 注释会下推行号），绝不照抄行号、绝不顺手碰 :209 签名。
- Q2 分层：0，纯删键，无新 import。
- Q3 迁移耦合：无。
- Q4 灵魂线：R62 删的 `or`/`!=` 是「展示降级」非「错误吞噬」，删除清 P3 残骸不触灵魂线。**但注意区分**：删的是 execution_review 报表**无前缀**键，与 state 层 `latest_*_identity_label`/`counterpart_*`（真身份，被 7+ 文件 PIN，operation_execution_state.py:45/50）键名空间完全分离——删 R62 绝不触真身份字段（灾难链 B 防护，实测爆炸面闭合：无前缀键消费者仅 3 文件）。
- **Q5 收口等价（裂缝在此）**：dossier §7 称"模板渲染逐字节不变"——**部分失真**。模板 :138-143 每行 `<td title="{{ r.X_identity_label }}">`，identity 键删除后 Jinja2 把 undefined 渲染为空串 → **title 属性从有值（=display）变空 `title=""`**。这是**可见 HTML diff，非 no-op**。dossier §4(b) 已开修法（"title 改回 `_label`"），但必须把"改 title"列为与删键**同 commit 的强原子第四处**，否则只删键不改 title = title 静默清空（hover 提示丢失）。`!=` 副 div 恒 False 确实零 diff；xlsx `or` 删后 `row.get` 返 None、`None or label`≡`label` 确实等价。**裂缝仅在 title。**
- Q6 测试迁移序：**R62 收口面零断言**（tests/ 实测零命中无前缀键）——无现成测试接住 title 变化。dossier §7 要求**动手前先补 3 套 parity 快照（dict/xlsx/模板）**，本轮升级为**硬前置门**：没有模板 parity 快照，title 清空这条裂缝无人接住（测试绿但展示已变）。

**强原子三处（漏一即新半截残骸）**：(a) execution_review.py 删 :358/359/361/362/374/375/381/382 八键 + payload :417 收单键 + actual 早退 :438-440 收单键；(b) 模板 :138-143 删 `!=` 副行 **且 title 改回 `_label`**；(c) xlsx :410/411/414/415 删 `or`。只删 a 漏 b/c = `row.get` 取 None 残骸 / 模板 title 空。

**前置/顺序**：LB02/LB05 注释先落(Batch-1) → R62 重 grep 回盘(行号已下推) → 补 3 套 parity → 三处同 commit(Batch-3)。

---

## 4) 跨簇边复核（本轮实证）

- LB06 fixed 属实：`require_execution_review_adopted_plan`(reports_request_support.py:75)+ `execution_review_plan_identity_error`(:65)+ 页级 `blocked_execution_review_plan_resolution`(reports_execution_review_context.py:8) + reports_page_support.py:397 强制 page_plan_resolution(..., "adopted", None)=**fail-CLOSED**。LB06↔A1 退化为认账协同，非阻塞。认账注释须落 reports_request_support.py + reports_execution_review_context.py（**非 reports_page_support.py**，与 _layer2_residual LB06 宿主口径一致）。
- 其余 same_symbol=false 弱边非阻塞。

## 5) 漏项（本轮新发现，计划未充分覆盖）

1. **【中】R62 模板 title 清空裂缝**：dossier §7「模板逐字节不变」对 title 属性失真——删 identity 键后 :138-143 的 `title=""` 是可见 diff。修法 §4(b) 虽提"title 改回 _label"，但未把它标成与删键**同 commit 强原子**且**无测试接住**（R62 收口面零断言）。前置：模板 parity 快照升为硬门，断言 title 收口前后相等（应=display 值，非空）。
2. **【低】R62 actual 早退块边界**：dossier §1/§6 标 :437-440，实测内容 :438-440、闭合 :441。指代同块不影响修法，但 R62 重 grep 时按符号定位勿照抄。
3. **【低】payload 丢弃真 identity 的隐性事实**：`_resource_pair_payload`(:407-408)只读 machine/operator 的 `display_label`，**完全不读 `_state_resource_identity`(:431)构造的真 identity_label** → 三键恒等的根因是 payload 层就丢了 identity，而非偶然相等。这反向坐实删键安全（下游本就拿不到真 identity），但也说明"恢复真三档身份"远不止删/留键，须改 payload 读 identity_label——owner 若要反向恢复，工作量被 dossier 低估。
