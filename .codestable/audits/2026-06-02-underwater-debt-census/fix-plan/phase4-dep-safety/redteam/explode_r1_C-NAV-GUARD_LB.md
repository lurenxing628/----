# 爆炸对抗 r1 · 簇 C-NAV-GUARD · 透镜 LB(承重误删)

> skeptic 第1轮，只读不改，默认怀疑。全部承重禁区行已独立 rg 回盘（不信旧值）。
> 成员债 R54 / R44 / R58。主透镜【承重误删】主攻 Q1。

## 回盘锚点订正（本轮新发现的路径/行号漂移）

| 项 | cluster/dossier 旧值 | 实盘回盘 | 影响 |
|---|---|---|---|
| **L5 文件路径** | `web/routes/domains/scheduler/scheduler_gantt_task_detail.py`（cluster:3、dossier 字段1） | **`web/viewmodels/scheduler_gantt_task_detail.py`** | 路径前缀错（routes/domains/scheduler→viewmodels），动手前必纠，否则改错文件 |
| L5 别名元组 | :9-15 | `_PLAN_GUARD_FIELD_ALIASES`:8-25（16 条），写回循环 :94-97，is_comparison 独立兜底 :98 | dossier「:9-15」只覆盖前 7 条，实为 16 条 |
| build_workbench_plan_context 返回 dict guard 键 | cluster/dossier 称收口点「当前只有 is_preview/can_write_feedback」 | **坐实**：:230-255 返回 dict **完全不含** is_comparison/is_superseded/is_current_executable/is_official_plan，仅 is_preview:247 + can_write_feedback:248 | 收口方案核心假设成立 |

## 逐债判定

### R58 — 🟢绿（本轮注释动作安全）
- `:91 context.update(guard_fields)` 实盘唯一命中（非 registry :86），上方零注释，坐实 planned。
- 机理坐实：`:88 can_write_feedback=guard_fields.get(...)` 喂 raw 给 builder→builder `_feedback_guard_context:157-158` 算 gate 写 :248→`:91` 用 raw guard_fields 覆盖回门控值。
- 零生产消费坐实：`scheduler_navigation_links.py` grep can_write_feedback=0 命中；真写链接走 `can_emit_feedback_write_urls:469`（消费者 resource_dispatch:202 / reports_workbench:361，读 filters/row_context 非 nav context）。纯增量注释零行为变更=绿。
- **漏项(次)**：cluster A-1#1 只钉 :91 上方 4 点注释，**漏 :88 raw 双重入口**——注释须同时说明「:88 喂 raw 是故意的（builder 内 gate）、:91 覆盖回 raw 是故意的（零消费）」，否则读者困惑「builder 已 gate 为何被覆盖」。

### R44 — 🟢绿（收口到已存在 core 点，非承重，core 更防御）
- import 真来源坐实 `:6 from ...schedule_plan_query_service import ROLE_ADOPTED`（非 view_context）。
- core 收口点 `schedule_result_view_context.py:201 selected_plan_role` 多 `(plan_resolution or {})` None 防御；web `:36` 无。收口=保持/增强防御，不新增兜底/不翻 fail-open。
- 只喂 effective_plan_role= 模板显示 kwarg，不碰任何闸门。唯一行为差异 None→AttributeError vs "adopted"（生产不可达）。owner 裁 None 边界即可。绿。

### R54 — 🟡黄（收口方向安全，但有两个计划漏项 + 一条 A 族禁区诱惑，必须前置钉死才转绿）
- **当前未坏坐实**：5 套（L1 reports:36 / L2 nav:12 / L3 resource_dispatch:64 / L4 dashboard:8 / L5 gantt viewmodels:8）各含三关键键 is_comparison/is_superseded/is_current_executable 各 1。
- **fail-closed 真支柱坐实**：`_is_current_official_identity:292-296` = `not is_comparison AND not is_superseded AND is_current_executable_official_version is True`。前两键 truthy（缺→falsy→不拦，fail-OPEN 方向），**唯一拦截支柱是第三键 `is True`**（缺→None→`None is True`=False=拦=fail-CLOSED）。
- **5 套丢键语义坐实统一为「缺键→不写→builder dict 不含→.get()=None→第三键兜底拦」**：L1 :53 `if value is not None`、L2 :82 `is not None`、L3 :82 `if key in identity`、L4 :131 `if key in filters`、L5 :96 `if value is not _MISSING`。→ **漏写 ≠ fail-open**（漏写只会 fail-closed）。真 fail-OPEN 入口只有「写错值」或「收口把 is_current 默认成 True」。
- **收口安全性坐实**：真相源 `plan_role_filter_fields:341/346` 用 `_identity_bool`（:271-274 缺键既不在 plan_identity 也不在 data→`bool(None)`=**False**）+ `default_plan_resolution_dict:94-95` is_current/is_superseded=**False**。→ 收口走真相源全集对三键全部 fail-closed 收敛，安全。

**🟡条件（三条必须作前置/禁区，否则转🔴）**：
1. **A 族禁区诱惑（最危）**：cluster 字段4/dossier 字段4 候选写「给 build_workbench_plan_context **增加承载 guard 字段的入参**（或接收 guard dict）」。**这条若被实现为「加 guard 形参由 5 套各自传入」=路径乙=A 族禁区「给 builder 加形参透传」**——builder 仍只透传，5 套「缺键不写」语义原样搬进 builder，收口=假收口，且签名形参化给未来调用方留「传半套 guard」的预览冒充正式入口。**owner 裁断点必须钉死：只许路径甲（builder 内部 delegate plan_role_filter_fields 产全集），禁路径乙（加 guard 形参/dict 透传）。**
2. **5 面 parity 语义分叉（A-2 漏项）**：cluster A-2 把 5 面当「无顺序敏感的同质 delegate」，但实盘 L1(:53 过滤 None) vs L3/L4/L5(过滤缺键，key 在但值=None 时**会写 None**) 语义不对称。parity 测试必须分两组（None-filter 组 vs key-presence 组）覆盖「key 在但值=None」态，验证收口前(None) 与收口后(bool False) 下游拦放一致，否则收口悄改边界。
3. **R54↔R42 同批次 vs batch_hint Batch-3 张力**（dossier 字段12 已标）：plan_id 形参 :191 / dict :233 实盘坐实，R42 删此与 R54 加 guard 同改 :187-255 整块，MUST 同批，owner 须裁 R42 提前或 R54 延后。禁区行 :292-296 判定方向、view_context :94-95 fail-closed 默认值，收口绝不触碰。

## 六质问点小结
- **Q1 承重误删**：5 套看似该 DRY，但任一「统一/删」若落在「翻第三键 `is True`→truthy」或「把 is_current 默认成 True」=fail-OPEN。当前未坏，债为 split 结构风险。已标 R54 黄+禁区。
- **Q2 分层环**：L5 在 web/viewmodels import 同层 .scheduler_workbench_links（web→web），nav/reports 收口新增 web→core.services 合法，view_context/query_service 不反向 import web。0 违规，无环。🟢
- **Q3 迁移耦合**：本簇三债不碰 schema/v18/v19 CHECK，无迁移耦合。🟢
- **Q4 灵魂线热路径**：R58/R54 收口禁引入兜底；L5 :92 `can_write if not _MISSING else None`、5 套丢键路径收口后须走真相源确定 bool，禁保留「缺了不写」静默路径（漏键=fail-open 入口）。已标禁区。
- **Q5 收口行为等价**：见 R54 条件2，5 面 parity 须分两组覆盖 {缺失/None/False/True}×拦放，尤其「key 在值=None」分叉态。
- **Q6 测试迁移序**：删任一手维列表前先令其契约测试改读 build_workbench_plan_context(含 guard) 输出，删列表与改测试同 commit；硬序 R58→R54→R44，R44 动手前重新回盘 :6/:36-37。
