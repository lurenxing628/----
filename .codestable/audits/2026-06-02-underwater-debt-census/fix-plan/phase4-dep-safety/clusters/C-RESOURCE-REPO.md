# 原子簇 C-RESOURCE-REPO — 干扰图重建（只读不改）

> 成员债 R05 / R67 / R34 / R35 / R36 / R37 / R38 / R39
> 主文件 resource_dispatch_service.py / schedule_plan_query_repo.py / schedule_repo.py / batch_operation_repo.py / operator_machine_repo.py / op_type_repo.py / part_repo.py / request_resource_context.py
> 回盘 2026-06-05；行号均 rg 现盘命中，不信旧值。本簇横跨原 codemap 大簇 C01（R05/R67/R34/R35/R37）+ C02（R38/R39），R36=ISOLATED。
> 2026-06-08 B 执行进度补登：R36 / R37 / R38 / R39 已在本分支登记 fixed；下方旧行号保留作执行前证据，不再表示待执行锚点。后续执行以 `_registry.json` 与各 dossier 顶部终态补登为准，勿重复执行 G31/G32/G35/G36。

## 0) 现盘行号回盘（rg 命中，全部坐实）

| 债 | 符号 | 现盘 file:line | 收口/孪生点 | 备注 |
|---|---|---|---|---|
| R05 | `_normalize_scope_type` 服务私写 | resource_dispatch_service.py:59-63 | 收口点 `schedule_resource_filter.py` | collar :8 `SUPPORTED_SCHEDULE_RESOURCE_TYPES={machine,operator}`（**无 team**）；:19 `column_name`；:43/:59 `normalize_*` |
| R05 | repo 内联 `list_dispatch_rows` | schedule_plan_query_repo.py:430（team 双 join :462） | 活孪生本身 | 禁区行 :454-455/:459-460 空 id 全量 + :461-463 team 双 join |
| R34 | `get_version_time_span` | **已删除**（旧锚 schedule_repo.py:36-59） | 活孪生 `schedule_plan_query_repo.get_plan_time_span`:257 | 2026-06-08 fixed；benchmark 已改指 repo 层活孪生 |
| R34 | `list_overlapping_with_details` | **已删除**（旧锚 schedule_repo.py:114-126） | — | 死孪生已退场 |
| R34 | `list_dispatch_rows_with_resource_context` | **已删除**（旧锚 schedule_repo.py:128-158） | — | 与 R05 的 list_dispatch_rows 不同符号不同文件；未迁 detail_queries |
| R35 | `list_between` | **已删除**（旧锚 schedule_repo.py:61-69） | 无孪生（纯死） | 已随 R34 同原子 diff 删除 |
| R36 | `get_by_op_code` / `list_by_status` | **已删除**（旧锚 batch_operation_repo.py:25-35 / 50-61） | 无 | ISOLATED，2026-06-08 fixed |
| R37 | `list_links_with_machine_names` | **已删除**（旧锚 operator_machine_repo.py:82-90） | 无 | 活近亲 `list_links_with_operator_info` 保留并上移到 :82 |
| R38 | `list_as_dicts`×3 | **已删除**（旧锚 op_type_repo.py:73 / operator_repo.py:85 / part_repo.py:71） | 无 | 结构同形 SQL 各异，已按三笔独立删闭合，禁抽 helper |
| R39 | `list_unparsed` | **已删除**（旧锚 part_repo.py:32，体:33 转调活方法 list:20） | 无 | 已与 R38 part 份同提交，行号漂移风险已关闭 |
| R67 | 6 键别名清单 4 处手抄 | request_resource_context.py:22-27 / reports_request_support.py:56-61 / reports_export_support.py:23-28(`_EXPORT_CONTEXT_KEYS`:13) / scheduler_navigation_links.py:22-27(`_REPORT_CONTEXT_FIELD_NAMES`:11/190) | 常量 home=`report_context_filters.py`（收口点 `normalize_report_resource_filter`:119 同模块）；`REPORT_RESOURCE_FILTER_ARG_KEYS` 全仓 **NOT FOUND** | 第 4 处不在 registry all_files，漏它=半截去重 |

## A) 原子子簇（必须同批 / 可独立）

本簇 9 债拆成 **4 个原子子簇 + 2 个独立单点**。

### 子簇 AC-1 = {R34, R35}（schedule_repo.py，硬同批，唯一行号坐标耦合；2026-06-08 已落地）
- **原子原因（同物理文件改一处顶掉另一处行号）**：R34 删 :36-59 / :114-126 / :128-158 三段，R35 删 :61-69，R35 段正夹在 R34 第一段(止:59)与第二段(起:114)之间。任一先单独提交都让对方行号二次漂移（删 R34 第一段→R35 上移 ~24 行；删 R35→R34 第二/三段上移 9 行），且 facade_delegation 活方法断言位置随之漂移、易误定位。
- **执行结果**：已按符号名同原子删除四个死方法；`test_schedule_service_facade_delegation.py` 仅保留活方法断言；`test_schedule_repository_detail_queries.py` 仅保留 `list_by_version_with_details` 活用例；`gantt_critical_chain_unavailable.py` 删除无效 monkeypatch；`benchmark_fjsp.py` 改指 `SchedulePlanQueryRepository.get_plan_time_span`。活近亲现为 `schedule_repo.py:36` / `:79`。
- **历史顺序说明**：原计划要求同提交内按符号名自下而上删，原因是旧 R35 段夹在 R34 旧删段之间；现在旧删点已不存在，后续不得再按旧行号施工。

### 子簇 AC-2 = {R38(part 份), R39}（part_repo.py，硬同批，行号坐标耦合；2026-06-08 已落地）
- **原子原因**：R39 `list_unparsed`:32 在上，R38 `list_as_dicts`:71 在下；删 R39 致下方行号上移 2 行（R38→~:69）。R39 先落而 R38 patch 基于旧行号 :71 即打偏。
- **内部顺序**：无功能先后（两方法无相互调用，callgraph 无边）。同 commit，按符号名定位；若分 hunk 应用则“先 R39 再以新行号定位 R38”。两者 owner_pending=false，给终态直删。
- **注意**：R38 是“三处 list_as_dicts 死簇”，但仅 **part 份**与 R39 同文件强绑；op_type_repo.py:73 / operator_repo.py:85 两份**无同文件兄弟、随 R38 簇自由排**（见 AC-2′）。三份 SQL 列集不同（op_type_id,name,category / operator_id,name,status,remark,team_id / part_no,part_name,route_raw），**禁抽 helper（会造零消费活死代码）、记三笔独立删**。

### 子簇 AC-2′ = R38 的 op_type / operator 两份（可独立，仅随 R38 同 PR；2026-06-08 已落地）
- op_type_repo.py 旧 :73-74、operator_repo.py 旧 :85-86 各自零引用零碰撞，已随 R38 一并删除，无同文件兄弟。与 part 份同属 R38 一笔账但物理隔离。

### 子簇 AC-3 = {R05}（收口点扩容 + 三原子小步，自身不可拆但 owner_pending）
- **原子原因（收口前置·步内不可换序）**：步1 扩 collar team 双 join 表达力 + 放开“类型有/id 空=全量” → 步2 补负向回归（team-only / operator-空-全量 / machine-空-全量 / team-空-未定义裁断 / bad-raise 5 条 parity）→ 步3 才收敛 repo 字面量 + `_normalize_scope_type`。反序=班组谓词静默丢失 / 全量视图整页 500。
- owner_pending=true：F-决策① collar 加 team 谓词的接口形态；F-决策② `(team,"")` 语义=全量 or loud raise。**暂不分批、不给终态**。
- 毗邻勿伤：`_normalize_team_axis`(resource_dispatch_service.py:65-69，65870e47 新增第四套本地校验苗头) 管展示轴，**不在 R05 收口范围**。

### 子簇 AC-4 = {R67}（抽单一常量，自身不可拆但 owner_pending）
- **原子原因**：4 处手抄须**全收或全不收①②、③④酌情**——半截去重（只换 1~2 处）反造“看似统一实则分裂”假象，比现状更危险。①② 纯 6 键（喂收口点，零新增依赖）必收；③④ 是 superset 元组（资源键尾块），收编要元组拼接 `(...前缀, *KEYS)`，且 ④ 跨层边待 AST 门。
- owner_pending=true：F-决策 是否收编第 4 处 superset + tuple 可读性。常量须 **tuple 保序**（③④依赖 URL/字段遍历序）。**禁动**收口点签名/6 关键字参顺序、**禁改** superset 非资源键成员（R42 + navigation 地盘）、**禁统一 4 处读取逻辑**。

### 独立单点
- **R36**（batch_operation_repo.py 旧 :25-35 / :50-61，ISOLATED，2026-06-08 已落地）：零碰撞零跨边，两个死方法已从后往前直删，owner_pending=false。后续勿重复执行 G35/R36。
- **R37**（operator_machine_repo.py 旧 :82-90，2026-06-08 已 fixed）：死方法 `list_links_with_machine_names` 已删除；活近亲 `list_links_with_operator_info` 保留并上移到 :82。后续勿重复执行 G36。

## B) 跨簇边（指向其他 codemap 簇）

> 关键背景：本任务簇 C-RESOURCE-REPO 是按“资源/repo 战场”聚的，**横跨 codemap 两个原始簇**——R05/R67/R34/R35/R37 属 C01（67 债大簇），R38/R39 属 C02，R36=ISOLATED。故大量 interference_edge 其实是 **C01 簇内边**，不是跨簇。

1. **R34 ↔ {R10,R11,R12,R21,R55,R63}**（gantt_service.py 同文件旧误边）+ **R34↔R23**（schedule_plan_query_service.py 同文件旧误边）：经 rg 确认这 7 个邻居**全在 C01**，且 R34 本体动 schedule_repo.py，**不碰 gantt_service.py/schedule_plan_query_service.py 的方法体**；仅 benchmark repoint 若选服务层会读 `get_plan_time_span_for_resolution`（旧锚 schedule_plan_query_service.py:210；R23 后现盘 :206，执行按符号重 rg，不改其体）。这些旧边只在本段文字留痕说明，权威 `_registry.json` 不再保留对应 `interference_edges`；对 AC-1 排序无硬约束。
2. **R34 软关联 R05**（活孪生 schedule_plan_query_repo.list_dispatch_rows 是 R05 战场）：**簇内**（同属本任务簇）。**降级为软约束**——仅当 R34 的 detail_queries 用例选“迁到活孪生”时才为硬前置（迁移落点是 R05 team-join 改后的方法，须排 R05 之后；选“整删用例”则完全解耦）。
3. **R67 ↔ R42**（reports_export_support.py 的 `_EXPORT_CONTEXT_KEYS` 元组 + 经 verify 补强：**scheduler_navigation_links.py 亦共享**）：R42 在 C01，**簇内**但 R42 不在本任务簇成员内 → 对本簇是**外指边**。关系=**同文件同改（diff hunk 互撞）非语义冲突**：R67 改元组资源键尾块、R42 删 plan_id 首/中段，改不同键、零语义冲突，`fix_invalidation_risk=none`；建议**串行编辑这两个元组文件**避 hunk 互撞（范围覆盖 reports_export_support.py + scheduler_navigation_links.py 两处）。
4. **R37 ↔ R41**（equipment_pages.py 同文件）：R41 在 C01。**伪干扰边**——R37 已直删 operator_machine_repo.py 旧 :82-90，**根本不碰 equipment_pages.py**，零改动行。对 R37 无排序约束，应删此边（见 C 节）。
5. **R38/R39 ↔ C01**：无。C02 与本任务簇 C01 部分之间**无 repo 文件交叉**（part_repo/op_type_repo/operator_repo vs schedule_repo/collar 物理隔离）。AC-2 完全独立于 AC-1/AC-3。
6. **R05/R67 同桶 B07**：co_change 仅彼此，**不同收口点、零冲突、可完全并行**，无前后约束（registry 明示）。

**真·跨簇硬边 = 0**（AC-1/AC-2 各自闭合于自身物理文件；AC-3/AC-4 收口点独立）。唯一需跨边协调的是 **R67↔R42 的 diff-hunk 串行**（软，非语义）。

## C) 相对旧 146 边的变化（删 / 新 / 降）

### 删除（误标 / 伪干扰 / 文件不交叉）
- **删 R37↔R41**：corrections 未列，但 dossier+本轮 rg 实证为伪干扰——R37 不碰 equipment_pages.py，same_file 边对 R37 零约束。删边。
- **删 R34↔{R10,R11,R12,R21,R55,R63,R23}**（作为“跨簇硬边”理解时）：这些旧边对 R34 是误导性排序边，R34 本体不动 gantt_service.py/schedule_plan_query_service.py，**不构成排序边**；权威 `_registry.json` 已删除对应 `interference_edges`，本文件仅保留文字背景，避免后续执行者把它当门控批次。
- **R02↔R25 / R45↔{LB07,R33,R51} / R20↔{R08,R09,R12} / R32↔R15 / LB04↔{LB07,R33} / R26↔R43 / config_snapshot R26↔R71**：corrections B 节假边清单——**均不涉本簇成员**，本簇无对应边可删（登记备查，本簇侧零删除）。

### 新增
- **新 R67↔R42 第二条共享文件边**：verify 补强——R42 的 all_files 同时含 `scheduler_navigation_links.py`（不止 reports_export_support.py），故 R67↔R42 的 diff-hunk 串行范围**新增覆盖 scheduler_navigation_links.py**。属外指软边（diff 层，非语义）。
- 簇内无新增硬边。

### 降级
- **R05→R34 硬依赖 → 条件软边**（corrections 明列）：旧叙事假设“R34 收敛到 column_name / 收敛到活孪生”，本轮回盘证 R34=**纯删死方法**，其 `schedule_repo.list_dispatch_rows_with_resource_context` 与 R05 改的 `schedule_plan_query_repo.list_dispatch_rows` 是**不同符号、不同文件**，无硬数据依赖。O10 已裁 R34 纯删后，当前 R34 与 R05 解耦；仅未来改裁为“迁用例到活孪生”时才回升为 R05 后置硬前置。
- **R13↔R18 解耦**：不涉本簇（登记备查）。

### 本簇 fixed 进度与簇外 fixed 列表（corrections E）
- 2026-06-08 B 执行后，本簇内 **R36/R37/R38/R39 已 fixed**，无残留补注释或补测试动作；后续执行不要重复处理 G31/G32/G35/G36。
- LB06/R56/R57/R07/R16/LB03 已 fixed——**均非本簇成员**，对本簇无前置门控。

## D) 承重前置（LB/N/R03/R58 注释+parity 门控的禁区行）

本簇成员 registry `load_bearing` 字段全 false，但 **R05 verdict=load_bearing（refuted=False）**——是本簇唯一承重点，门控 AC-3 全部结构动作。

### R05 承重前置（门控 AC-3 步3 收敛）
- **禁区行（lb_no_touch，绝不删/合并/裸透传，只能先扩收口点搬过去并保语义）**：
  - `schedule_plan_query_repo.py:461-463`——team 双 join `((o.team_id=?) OR (m.team_id=?))` + `params.extend([scope_id, scope_id])`。column_name 单列**表达不了**的承重第三轴，塌缩=班组静默失效。
  - `schedule_plan_query_repo.py:454-455 / :459-460`——空 id 全量分支 `TRIM(COALESCE(s.operator_id,''))<>''` / machine 同款。塌缩=团队·全量视图整页 500。
- **承重前置门**：步1 扩 collar（加 team 谓词接口 + 放开“id 空=全量”，且在收口点写明“id 空→全量视图（故意，派工全部人员/设备入口）”中文注释，**不得 except 吞错/默认空串静默放行**）+ 步2 落 5 条 parity **必须先落**，才门控开放步3 把 :461-463/:454-460 搬进收口点。**parity 先于收敛**是硬序。
- **灵魂线红线**：步1“放开空 id=全量”是显式扩语义非兜底；team 收敛时 scope_id 缺失须显式走全量分支或 loud raise，禁静默返全量坏数据。
- **分层红线**：collar 在 core.models，只产 SQL fragment 文本+参数序列，**禁让 core.models 反向 import data.repositories 的 SQL builder**（否则 model→data 越层+导入环）。0 AST 违规要求。

### 其余成员承重=无禁区
- R34/R35/R36/R37/R38/R39 全 load_bearing=false、lb_no_touch=null、文件非承重，**纯直删无承重禁区**。G30 fixed 后 R34/R35 唯一剩余“禁区”是相邻**活方法保护**（非承重）：`list_version_rows_by_op_ids_start_range` 当前 `schedule_repo.py:36` + `list_by_version_with_details` 当前 `schedule_repo.py:79` + 其 facade 活断言当前 `test_schedule_service_facade_delegation.py:29-33` 必须保留。R37 已 fixed 后同理保当前 `list_links_with_operator_info:82`。
- R67 禁区是**契约/越界**（非承重）：收口点签名 report_context_filters.py:119-127 禁动；superset 非资源键成员禁改。

### corrections C 节新承重 N1/N2（不在本簇成员，但毗邻提示）
- **N1/N2 不在本簇 8 成员内**，不门控本簇任何动作。仅记知情：N1=scheduler_resource_dispatch_execution_context.py:129-130、N2=operation_execution_event.py:156-163，各自补“我是故意的”注释+绑契约，与本簇 repo/collar 战场不交叉。

## E) fixed 成员残留动作

- **本簇已 fixed 成员：R36/R37/R38/R39。** 这四条均为纯删除死代码，当前无“fixed 前置已完成、补认账注释”的残留动作；执行者勿重复处理。
- LB03/LB06/R07/R16/R56/R57 已 fixed 均在簇外。
- 唯一与 fixed 相关的间接事实：corrections E 把 **R29 由 fixed 误标纠回 planned(owner-pending)**——R29 不在本簇，无影响。

## 返回摘要

簇 C-RESOURCE-REPO | 原子子簇 4+2 独立：AC-1{R34,R35} schedule_repo.py 硬同批、AC-2{R38-part,R39} 已 fixed、AC-2′{R38 op_type/operator 份}已 fixed、AC-3{R05}收口三步、AC-4{R67}抽常量；独立单点 R36 已 fixed / R37 已 fixed | 关键内部顺序：AC-1 无功能先后但按符号名自下而上同 commit；R05 步1扩 collar→步2 parity→步3 收敛不可换；R67 全收或①②必收③④酌情忌半截 | 跨簇硬边 0：AC-2↔C02 已闭合，R67↔R42(C01)diff-hunk 串行软边（覆盖 reports_export_support.py+scheduler_navigation_links.py），R05→R34 软约束 | 边变化：删 R37↔R41 伪干扰、删/降权 R34↔gantt 簇内 7 弱边；新 R67↔R42 第二共享文件边；降 R05→R34 硬→软、R13↔R18 解耦 | 承重前置：仅 R05 verdict=LB，禁区 schedule_plan_query_repo.py:461-463 team 双 join + :454-460 空 id 全量，步1 扩 collar+步2 parity 先落才开步3 收敛；余皆纯删无承重禁区
