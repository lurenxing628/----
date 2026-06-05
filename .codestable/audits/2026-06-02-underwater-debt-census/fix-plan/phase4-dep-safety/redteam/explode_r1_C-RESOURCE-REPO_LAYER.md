# 逐簇爆炸对抗 · C-RESOURCE-REPO · 主透镜【分层导入环+迁移耦合】· r1

> skeptic 第1轮，只读不改。回盘 2026-06-05，行号 rg 现盘命中。
> 主攻 Q2(分层导入环) / Q3(迁移耦合)，全过六质问。默认怀疑：多维度存疑即标红。
> 成员债：R05 / R67 / R34 / R35 / R36 / R37 / R38 / R39

---

## 0) 现盘回盘修订（与 dossier/cluster 行号有漂移，执行须按符号/分支定位）

| 项 | dossier/cluster 旧值 | 现盘真值（rg/awk 回盘） | 影响 |
|---|---|---|---|
| R05 collar 无 team | :8 SUPPORTED={machine,operator} | ✅ `schedule_resource_filter.py:8`={"machine","operator"} 无 team | 一致 |
| R05 collar 空 id raise | :65-70 | ✅ `:65-66` `if resource_type_text and not resource_id_text: raise` | 一致 |
| R05 collar imports | core.models 不 import data | ✅ 仅 `:6 from core.infrastructure.errors`，**零 data import** | 分层基线干净 |
| R05 禁区行 空 id 全量 | :454-455 / :459-460 | **现盘 operator 全量在 :455、machine 全量在 :460**（:454/:459 是 `elif` 分支头非 SQL） | **漂移 ~2-3 行**，按分支定位 |
| R05 禁区行 team 双 join | :461-463 | ✅ `:462-463` `((o.team_id=?) OR (m.team_id=?))` + `params.extend` | 一致 |
| R05 team 谓词依赖 | dossier 只说"双 join"未点 builder 耦合 | **`o`/`m` 别名来自 `:466 build_schedule_detail_sql(...include_team_context=True)`**；join 体在 `schedule_detail_query.py:64-65/72-74`，由 `:80-87 include_team_context` 闸控 | **新爆点，见漏项①** |
| R34 repoint 目标 | dossier 正文误判"不存在" | ✅ `schedule_plan_query_service.py:210 get_plan_time_span_for_resolution` 存在 | 利好，纯删安全 |
| R34 死/活方法 | — | ✅ 死 :36/:114/:128，活近亲 :71/:160，list_between(R35):61 | 一致 |
| R34 facade 断言 | :31/:36/:39-41 | ✅ 死断言 :31/:36/:39-40；**活近亲护栏 :33(by_op_ids)/:37(by_version)** 必保 | 一致 |
| R37 活近亲 | :92 | ✅ `operator_machine_repo.py:92 list_links_with_operator_info` | 一致 |
| v18/v19 DB CHECK | adopted-only 下沉 v19 | ✅ `v19.py:18-19 CHECK(effective_plan_role='adopted')` + `:14-15 CHECK(source_table='schedule')`；探针 `:70-73 _reject_invalid_event_sequences` **loud raise** | 见 Q3 |

---

## Q3 迁移耦合（本透镜重点之一）— **全簇绿**

- v19 是 **建表 + `_copy_events` 复制 + `_reject_invalid_event_sequences`(:70-73) loud raise 探针**，作用对象 **OperationExecutionEvents**，与本簇 Schedule/dispatch/repo 战场 **物理不交叉**。本簇 8 债无一向该探针喂数据。
- v19 的 `CHECK(effective_plan_role='adopted')` / `CHECK(source_table='schedule')` 钉的是事件表列；本簇所有删除动的是**读取 Schedule 表的 version-only / dispatch 查询方法**，**不改任何迁移、不改任何 schema 列**。改码不改迁移 ⇒ 启动探针不炸。
- R34 删的 `get_version_time_span` 是 adopted/version-only 盲路径，其活孪生 `get_plan_time_span_for_resolution(:210)` 才与 source_table 维度耦合——但 R34 是**纯删死孪生**，不碰活孪生体、不碰 CHECK。
- **结论：Q3 对 R05/R34/R35/R36/R37/R38/R39/R67 全部不构成迁移耦合爆点。** 启动探针炸=不会发生。

## Q2 分层导入环（本透镜核心）— 基线 0 违规，唯一风险点在 R05 step1

- `core.models/schedule_resource_filter.py` 现盘仅 import `core.infrastructure.errors`（合法下行），**零 data import**。
- `data/repositories/schedule_plan_query_repo.py` **零 `core.services`/`core.algorithms` import**。
- 全仓 `core/models/ → data.repositories` import = **NOT FOUND**（无 model→data 既有环）。
- R34/R35/R36/R37/R38/R39 = 纯删，**只减边不加边**，分层 0 风险，导入环不可能新生。R67 ①②③ 走已存在 `web→core.services` 下行（先例 `scheduler_resource_dispatch_execution.py`），④ 须过 viewmodels→core.services AST 门——本透镜下均不构成环。
- **唯一分层爆点 = R05 step1 扩 collar**：见红区 R05。

---

## 逐债判定

### 🔴 R05 —— load_bearing 承重，本簇唯一红，三维度叠加存疑

**判定 🔴红=会炸（前提：不先扩 collar / step3 漏带 builder 耦合 / 反序）。** 证据均现盘命中。

**灾难链 A（承重第三轴塌缩·主透镜外但最危）**：
改 `_normalize_scope_type`(resource_dispatch_service.py:59-63) 收敛到只有 `column_name` 单列的现状 collar → team 分支 `((o.team_id=?) OR (m.team_id=?))`(repo:462-463) **无处安放** → 班组视角静默返全量坏数据（无报错，整页数据范围错，最难发现）。或：现状 collar :65-66 对"类型有/id 空"强制 raise → 派工"全部人员/全部设备"全量视图(repo:455/:460 空 id 全量分支)整页 500。

**灾难链 B（分层·主透镜·dossier 未点的新爆点）**：
team 谓词 `o.team_id`/`m.team_id` 的别名 **不是 list_dispatch_rows 自带**，而来自 `:466 build_schedule_detail_sql(include_team_context=True)` → join 体在 `data/repositories/schedule_detail_query.py:64-65/72-74`，由 `:80-87 include_team_context` 闸控。**step3 收敛若把谓词字符串搬进 collar 却丢掉 `include_team_context=True` 这一 builder 信号** → `o`/`m` 别名在 SQL 不存在 → `OperationalError: no such column: o.team_id`（loud）；**更坏**：若 collar 为产 team 谓词而反向 import `schedule_detail_query` 的 join builder → **core.models→data.repositories 越层 + 潜在导入环**（现盘 0 违规被击穿）。

**修正建议（前置/顺序/禁区）**：
- **禁区行（lb_no_touch，只先扩 collar 搬过去并保语义，绝不裸删/裸合并）**：repo `:462-463` team 双 join+extend、`:455` operator 空 id 全量、`:460` machine 空 id 全量。
- **硬序不可换**：step1 扩 collar（team 谓词接口 + 放开"id 空=全量"，且收口点写明"id 空→全量（故意，派工全部人员/设备入口）"中文注释，**禁 except 吞错/默认空串静默放行**）→ step2 落 5 条 parity（team-only/operator-空-全量/machine-空-全量/team-空-未定义裁断/bad-raise）→ step3 才收敛 repo 字面量+`_normalize_scope_type`。**parity 先于收敛是硬序**。
- **分层红线（本透镜）**：collar 只产 SQL fragment 文本+参数序列，**禁 core.models 反向 import data 的 SQL builder**；team 谓词的 collar 接口**必须同时表达"需要 team join 上下文"这一布尔**（等价 include_team_context），让 repo 侧拼 join，否则 step3 收敛即炸（灾难链 B）。
- **owner_pending=true**：F-决策① collar team 谓词接口形态（须含 include_team_context 信号）；F-决策② `(team,"")` 语义=全量 or loud raise。**暂不给终态、暂不分批**。
- **毗邻勿伤**：`_normalize_team_axis`(resource_dispatch_service.py:65-69) 管展示轴，不在 R05 收口范围，收敛勿误并。

### 🟡 R67 —— 条件可做（半截去重 + 第4处跨层门）

**判定 🟡黄。** 本透镜下两条件：
1. **半截去重风险**：4 处手抄（request_resource_context.py:22-27 / reports_request_support.py:56-61 / reports_export_support.py:23-28 / scheduler_navigation_links.py:22-27 第4处不在 all_files）。①②必收③④酌情，**忌只收 1-2 处**造"看似统一实则分裂"。漏第4处=半截。
2. **第4处分层门(Q2)**：收编 ④ 新增 `web.viewmodels→core.services.report` 边——有同向先例（`scheduler_resource_dispatch_execution.py:23`），过 AST 门概率高，但**owner 未拍前第4处保持现状/仅注释最稳**。①②③ 零新增依赖/零环。
- 禁区：收口点签名 `report_context_filters.py:119-127` 禁动；superset 非资源键成员（R42+navigation 地盘）禁改；常量须 tuple 保序（③④依赖遍历序）。
- 软边：与 R42 共享 `reports_export_support.py` + `scheduler_navigation_links.py` 两元组，串行编辑避 diff-hunk 互撞（非语义冲突）。

### 🟢 R34 —— 安全（纯删，repoint 目标已坐实存在）

**判定 🟢绿。** repoint 目标 `get_plan_time_span_for_resolution` 现盘 `schedule_plan_query_service.py:210` **存在**（dossier 正文"不存在"已被 verify+本轮回盘双纠）。死孪生 :36/:114/:128 与活孪生 SOURCE_SCHEDULE 分支逐分支等价（活孪生严格超集+未知 source raise）。删错全是**响亮 AttributeError 无静默炸点**。Q2/Q3 双绿（纯删只减边、不碰迁移）。
- 禁区（非承重，活方法保护）：**禁误删活近亲 `list_version_rows_by_op_ids_start_range:71`(freeze_window) + `list_by_version_with_details:160`(gantt_critical_chain)**，其 facade 断言 :33/:37 必保留。死断言 :31/:36/:39-40 + import :12/:14 同提交退。
- owner_pending=true：detail_queries 整删 vs 迁活孪生（迁则排 R05 之后）；benchmark:503 repoint 层级。**不给终态**。

### 🟢 R35 —— 安全（纯死直删，零引用）

**判定 🟢绿。** list_between `schedule_repo.py:61` 全仓零引用零测试零 callgraph 入边。Q2/Q3 双绿。唯一约束=与 R34 **同 commit**（:61-69 夹在 R34 删段 :59↘:114 之间，按符号名自下而上删防行号二次漂移）。owner_pending=false 给终态直删。

### 🟢 R36 —— 安全（ISOLATED 纯死直删）

**判定 🟢绿。** get_by_op_code `:25-35` + list_by_status `:50-61`，零碰撞零跨边零引用。Q2/Q3 双绿。从后往前删。本桶最早可落之一。

### 🟢 R37 —— 安全（纯死直删，唯一纪律=锁行+护活近亲）

**判定 🟢绿。** 死方法 `operator_machine_repo.py:82-90` 零引用；活近亲 `list_links_with_operator_info:92`（一字之差 machine_names↔operator_info，被 equipment_pages.py:142+facade+2 测试用活）现盘坐实在 :92。Q2/Q3 双绿。R37↔R41 伪干扰边（R37 不碰 equipment_pages.py）。**唯一纪律：diff 锁 :82-90，删后立即 grep `list_links_with_operator_info:92` 仍在**（误删=静默炸设备页人机联动分组）。owner_pending=false。

### 🟢 R38 —— 安全（三份 list_as_dicts 结构同形非同体，记三笔独立删）

**判定 🟢绿。** op_type_repo.py:73 / operator_repo.py:85 / part_repo.py:71，三处 SQL 列集各异（op_type_id,name,category / operator_id,name,status,remark,team_id / part_no,part_name,route_raw），零引用零 callgraph 入边。Q2/Q3 双绿。**禁抽 helper**（会造零消费活死代码）。part 份与 R39 同 part_repo.py **硬同批**。

### 🟢 R39 —— 安全（纯死直删，被包活方法独立存活）

**判定 🟢绿。** list_unparsed `part_repo.py:32-33`(体转调活方法 `list:20`)，零引用。删壳不孤立 list（多活调用者）。Q2/Q3 双绿。与 R38(part 份)同 commit：删 R39 致下方上移 2 行，R38 patch 须同基线。owner_pending=false。

---

## 漏项（本轮新发现，计划未充分覆盖）

**① [中危·主透镜] R05 step3 收敛的 builder 耦合被 dossier 漏点。** team 谓词 `o.team_id`/`m.team_id` 别名**不是 list_dispatch_rows 自带**，依赖 `:466 build_schedule_detail_sql(include_team_context=True)`（join 体 `schedule_detail_query.py:64-65/72-74`，闸 `:80-87`）。dossier R05 §4 只讲"扩 collar 加 team 双 join 表达力"，**未要求 collar 接口同时承载 `include_team_context` 信号**。若 step3 只搬谓词字符串、漏带该布尔 → `no such column: o.team_id`（loud）；若为产 team 谓词让 collar 反向 import builder → core.models→data 越层+导入环（击穿 0 违规）。**前置补强**：F-决策① 的 collar 接口签名必须含"是否需要 team join 上下文"的返回项，由 repo 侧拼 join，collar 绝不 import data builder。

**② [低危·行号漂移] R05 禁区行行号在 dossier/cluster 已漂 2-3 行。** "空 id 全量"现盘在 operator `:455`/machine `:460`（dossier 写 :454-455/:459-460，其 :454/:459 实为 elif 分支头非 SQL）。执行**必须按分支语义定位**，照搬旧行号会删错或漏删全量分支。

**③ [提示·非本簇] v19 探针 `_reject_invalid_event_sequences:70-73` 是 loud raise（合规），但它与本簇零交叉**——记知情：任何后续把本簇 repo 删除误连带改到 OperationExecutionEvents 读写链才会触雷，本簇 8 债不触。
