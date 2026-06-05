# 逐簇爆炸对抗 r2 — 簇 C-NAV-GUARD（主透镜：承重误删 LB）

> skeptic 第2轮 / 只读不改 / 默认怀疑。成员债 R54·R44·R58。主攻 Q1 承重误删 + 5 套 guard fail-open。
> 全部行号当前工作区 rg 回盘（不信 dossier/clusters 旧值）。本轮以「找爆点」为成功，找不到才绿。

## 0) 回盘锚点订正（本轮新盘，权威覆盖 clusters.md / dossier）

| 锚点 | clusters/dossier 写的 | 本轮实盘 rg | 判定 |
|---|---|---|---|
| R54 L5 gantt_task_detail 路径 | `web/routes/domains/scheduler/scheduler_gantt_task_detail.py:9-15` | **`web/viewmodels/scheduler_gantt_task_detail.py:8` `_PLAN_GUARD_FIELD_ALIASES`** | ⚠️**目录前缀错**：routes/domains→viewmodels。文件在 routes 下**不存在**（rg IO error）。clusters.md:16 与 R54 dossier 字段1 L5 行均错。 |
| R54 L1 reports `_copy_plan_guard_fields` def/call | :36 / :77（clusters）/ :98（dossier） | def **:36** / call **:98** | def 对；clusters「call 77」错，dossier「98」对 |
| R54 L2 nav 元组/ret/update | :12 / :82 / :91 | :12 / :82 / :91 | ✅ |
| R54 L3 resource def/call×2 | :64 / :95 / :199 | def **:64** / call **:109** / **:199** | clusters「call 95」错（实 :109），:199 对 |
| R54 L4 dashboard 元组/apply | :8 / :130 | :8 / :130 | ✅ |
| R54 收口点 build_workbench_plan_context | :187，dict :229-258 | def **:187**，dict :229-258，**当前零 guard 字段**（仅 is_preview:248/can_write_feedback:248） | ✅ 收口确未发生 |
| fail-open 判定 _is_current_official_identity | :292-304 | **:292-296**：`not is_comparison and not is_superseded_by_newer_version and is_current_executable_official_version is True` | ✅ 方向坐实：前两键 `not<truthy>`=fail-OPEN，第三键 `is True`=fail-CLOSED |
| R44 web 副本 / import / core 收口 | :36-37 / :6 / view_context:201 | def **:36-37**，import ROLE_ADOPTED **:6 = schedule_plan_query_service**，core **:201** | ✅ corrections A 坐实 |
| R58 病灶 context.update | :91 | :91（唯一命中） | ✅ |
| N1 邻接 execution_context | :129-130 + 蕴含链 `_can_write_feedback:89`/`_is_official_plan:70-84` | :129-130=裸 `return bool(identity.get("can_write_feedback"))`；**:89/:70-84 这两符号在该文件不存在**（:70-110 全是 request_kwargs/row_matching） | ⚠️**corrections C 节 N1 蕴含链=幻觉锚点** |

## 逐成员判定

### 🟡 R54（high / load_bearing=true）— 有条件可做，5 个前置全绑才放行
**判定黄不红**：当前 5 套**全各含** is_comparison/is_superseded_by_newer_version/is_current_executable_official_version（rg -c 实证 L1-L4 各 1、L5 各 1+，L5 另有 :98 `is_comparison = OR(is_comparison, is_comparison_plan)` 合并）→ 当前未坏，债是 split 结构。收口到已存在点 build_workbench_plan_context(:187) 方向合规、分层合法(web→core 单向无环)。
**放行硬条件（缺一即红）**：
1. **L5 必须纳入收口**且**按 viewmodels 真路径**（非 clusters 的 routes 路径，否则改空文件 = 漏第五面 = dashboard/gantt 入口仍旧手拷，债残留 fail-open 入口未堵）。
2. **L5 别名 OR 合并语义不得抹平**：`:98 is_comparison = bool(get(is_comparison) or data.get("is_comparison_plan"))` + `_PLAN_GUARD_FIELD_ALIASES` 多别名(`is_comparison_plan`/`is_official`/`is_preview`/`selected_role`...) 是 L5 独有的源键宽容。收口若强行喂统一收口点的单键全集，会丢 `is_comparison_plan` 这条 OR 支路 → 旧入口的 comparison plan 漏判 is_comparison=falsy → `not falsy`=True → fail-OPEN。**禁统一键名/禁抹 OR**。
3. **静默丢键路径禁保留**：5 套各带丢键逻辑（nav:82 `if fields.get(key) is not None` / L5:96 `if value is not _MISSING` / dashboard:130 循环 / reports:53 / resource:80）。漏键正是 fail-open 入口，收口后必须走 default_plan_resolution_dict(view_context:94-95/145-146) 的 is_superseded=False/is_current_executable_official_version=False 确定默认，不得静默不写。
4. **禁区行**：workbench_links.py:292-296 判定方向（严禁为「统一」把 `is_current_executable_official_version is True` 翻成 truthy → fail-closed→fail-open）；view_context default fail-closed 默认值方向。
5. **与 R42 同函数互锁**：R42 删 plan_id 形参(:191)/dict 行(:233)，R54 加 guard 字段，同改 build_workbench_plan_context 签名+dict → **必须同批次**（batch_hint 把 R42 列 Batch-3 与 deps「同批」冲突，owner 裁）。
**灾难链（若条件 2 破）**：收口统一键名抹掉 L5 `is_comparison_plan` OR 支路 → gantt/dashboard 入口的 comparison plan 上下文 is_comparison 取不到 → falsy → `_is_current_official_identity`(:294)误判现行官方 → execution_review 闸(:394 `not _is_formal_adopted_context`)放行 → 旧/比较方案冒充现行采用方案，写侧脏写。测试侧 L5 parity 若不补「comparison_plan-only 喂值」反例，删 OR 后仍可能绿（当前用例可能两键都给）→ 静默失护栏。

### 🟢 R58（low / load_bearing=true）— 本轮仅注释，安全
病灶 :91 `context.update(guard_fields)` 用未门控 raw 覆盖 builder 已 gate 的 can_write_feedback(:248) 坐实。但**零生产消费**：真写链接放行走 can_emit_feedback_write_urls(:469-473，独立读 filters/row_context)；scheduler_navigation_links.py grep can_write_feedback **零命中**（nav 链接不传播脏值）。本轮修法=:91 上方插「我是故意的」注释（钉 4 点）+ 绑现有 keep_plan_guard_fields 契约，纯增量零逻辑变更 → 安全。**红线**：禁删整行(连带丢 can_dispatch→superseded 派工护栏失效+测试转红)、禁剔 can_write_feedback 单键(Phase2 须补 preview-adopted/非adopted 两反例 parity，现契约盲——superseded 用例 builder-gated≡raw≡True 仍绿)。

### 🟢 R44（low / load_bearing=false）— 收口安全，仅排序约束
web 副本 :36-37 vs core :201 逐字近似，core 多 `(pr or {})` None 防御=**更防御**（原报告「web 多兜底」方向已 refute）。只喂 effective_plan_role 模板显示 kwarg(week_plan:352/gantt:299)，不碰任何闸门；生产入参恒 dict，None 反例不可达。收口=照搬 gantt_plan_query re-export 范式到已存在 core 点，分层合法无环。**约束**：排 SEQ-NAV 末位（R58→R54→R44，同文件行号），动手前重新 rg 回盘 :6-7/:36-37；仅允许动 :6-7(import)+:36-37(删 def)，禁顺手统一 :32-33 requested_plan_role / :12-31 闸门元组。

## 漏项（本轮新发现，计划未覆盖）

1. **🔴幻觉锚点·N1（execution_context.py）**：corrections C 节 + clusters D 节给 N1 修法「补注释钉 can_write_feedback⇒adopted-only 来源链，禁区 `_can_write_feedback:89-110`/`_is_official_plan:70-84`」——但实盘**该文件 :70-110 无此二符号**，:129-130 是裸 `return bool(identity.get("can_write_feedback"))`，:70-110 全是 _json_payload/_required_request_kwargs/_row_matches。执行者照计划去守不存在的禁区行 = 守空气，且「严格蕴含 adopted+schedule+无 scenario」无代码支撑。**真实缓解在别处**：N1 漏放最坏只跳过 `_ensure_feedback_target_in_query`(query-membership 校验)；真写门 server-side 独立 fail-closed raise 在 **operation_execution_feedback_service.py:369-374**（requested/effective != ROLE_ADOPTED → raise）+ **:381-382**（plan_identity.can_write_feedback False → raise）。故 N1=失忆债(注释缺失)非 fail-open。**修正建议**：N1 注释锚点改 :129-130 本符号，蕴含链改钉「真闸在 feedback_service:369-382 双 raise，本字段仅 query 优化短路」，删 dossier 幻觉的 :89/:70-84 禁区行。
2. **🟡L5 第五面键数/机制**：clusters「L5 别名元组 9-15」实为 **:8-25 共 16 别名对**，机制是 `_lookup_identity_field` 多别名回退 + :98 OR 合并，与 L1/L3 的 `_copy_plan_guard_fields`、L2/L4 的 `_PLAN_GUARD_FIELD_NAMES` **三种不同符号**。R54 dossier「恰 4 套」按两符号名 scope 漏 L5。收口面计数与 parity 用例须按 5 面、L5 单列 OR 反例。
3. **🟡reports 第二注入路径坐实**：plan_identity_error/blocking_error/blocking_scope 经 reports_execution_review_context.py + dashboard.py 另一路注入（实盘命中），reports L1 `_copy_plan_guard_fields` 不含这三阻断态键 → **禁把 reports 两注入路径并一条**（丢阻断态）。计划已标，本轮 rg 坐实。
4. **批次张力未裁**：R54↔R42 必须同批 vs R42 batch_hint=Batch-3、R54=Batch-2，owner 未裁，Layer4 须显式定。
