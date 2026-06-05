# 逐簇爆炸对抗 r1 — C-NAV-GUARD / 主透镜【分层导入环+迁移耦合】

> skeptic 第1轮，只读不改，默认怀疑。成员 R54 / R44 / R58。本轮全部 file:line 当前工作区 rg 回盘（b08162cd 后 nav_publish=M +8 行 / workbench_links=MM +146 行，行号高度漂移）。

## 0) 本轮 rg 自证（当前工作区，不信旧值）

| 锚点 | 回盘 file:line | 结论 |
|---|---|---|
| R58 病灶 `context.update(guard_fields)` | scheduler_navigation_publish.py:91（唯一命中） | 坐实，registry :86 / old :79-84 全错 |
| R58 链路 :88 喂 raw → builder gate → :91 覆盖回 raw | nav_publish:88/91 + workbench_links:158/248 | 覆盖回脏值坐实 |
| R54 fail-open 判定 `_is_current_official_identity` | workbench_links.py:292-298 | `not is_comparison and not is_superseded_by_newer_version`(fail-OPEN) + `is_current_executable_official_version is True`(fail-CLOSED) **坐实** |
| R54 builder gate `_feedback_guard_context` | workbench_links.py:149-162（:157 formal_adopted / :158 can_write） | 坐实，禁区本体 |
| R54 真放行收口 `can_emit_feedback_write_urls` | workbench_links.py:469-473 | 坐实 |
| R54 三关键键 ×5 套齐全 | reports/nav/resource/dashboard 各 1×3；gantt_task_detail 别名元组 :8-19 全含 | **当前未坏**，债=split 结构 |
| R54 第5套别名元组（异机制） | scheduler_gantt_task_detail.py:8 `_PLAN_GUARD_FIELD_ALIASES`（非 `_PLAN_GUARD_FIELD_NAMES`） | 坐实，5 面成立 |
| R54 静默丢键路径 | reports:53 `if value is not None` / resource:82 `if key in identity` / dashboard:131 `if key in filters` | 坐实，fail-open 入口 |
| R44 web 副本 selected_plan_role | nav_publish:36-37 | 坐实 |
| R44 import ROLE_ADOPTED 真来源 | nav_publish:6 = schedule_plan_query_service（**非 view_context**） | corrections A 坐实 |
| reports 第二注入路径三阻断态 | reports_execution_review_context.py:39-45 `execution_review_context_overrides`（plan_identity_blocking_error:43/error:44/blocking_scope:45） | **双分叉坐实，禁并一条** |
| N1 单字段收敛 | scheduler_resource_dispatch_execution_context.py:129-130 `return bool(identity.get("can_write_feedback"))` | 坐实，隐式化失忆 |

## 1) 六质问点逐债判定

### R58 — context.update 覆盖回未门控 can_write_feedback（P2 / 承重 / 本轮纯注释）
- **Q1 承重误删**：本轮只在 :91 上方插「我是故意的」注释，零逻辑变更。绿。**但若 owner Phase2「只剔 can_write_feedback 一键」**→ Q5 反例:preview-adopted / 非adopted 角色路径语义从 raw 静默翻 gated(True→False),而现有 `keep_plan_guard_fields` 用例构造 adopted+非preview → builder-gated≡raw≡True,**测试仍绿但护栏语义已变** = 典型「测试绿但护栏破」静默失效。
- **Q2 分层**：本轮纯注释零 import。绿。Phase2 收敛仍 web 内 publish→build 单向，须复核不引入 nav_publish↔workbench_links 双向环。
- **Q4 灵魂线**：本轮不动逻辑。**禁区:误删整行 `context.update(guard_fields)` 会连带丢 can_dispatch → superseded 派工护栏失效(测试转红,有响声但违规)**。
- **Q6 测试序**：本轮无需迁测试,跑 `regression_reports_workbench_navigation_contract.py:406` 保绿即承重契约。Phase2 须先补 preview-adopted/非adopted 两反例 parity 再改码,序不可倒。
- **判定🟡**：本轮注释安全；Phase2 剔键是黄(条件=先补两反例 parity + 排 R54 之后 + owner 拍板,否则静默翻转 gate)。

### R54 — plan-guard 投影散成 5 套手维列表（P5 收口 / 承重 / owner_pending）
- **Q1 承重误删（核心爆点）**：5 套看似 DRY 重复,实为护栏冗余。**任一套被「统一/简化」时漏拷 `is_comparison` 或 `is_superseded_by_newer_version` → 下游 :293-294 `not context.get(...)` = `not None` = True = 不拦 → 旧正式版/比较版冒充现行采用方案 → execution_review 闸(workbench_links execution_review 分支)+ can_emit_feedback_write_urls:469 放行写侧护栏 → 向历史/比较方案写现场事实(脏写、不可逆)**。这是 high+load_bearing 核心。
- **Q3 迁移耦合**:adopted-only 已下沉 v19 CHECK,本债收口 web 投影不改迁移,无启动探针炸。绿(此维)。
- **Q5 收口行为等价(关键反例)**:旧路手映射缺键走静默丢键(:53/:82/:131)不写→下游读 None;新路收口点 `default_plan_resolution_dict` 给 is_superseded=False/is_current_executable_official_version=False。须逐键验证三关键键在 {缺失/None/False/True}×拦放矩阵收口前后完全一致。**禁保留 `if value is not None`/`if key in` 丢键路径——漏键正是 fail-open 入口**。源键改名分叉(L1/L3 手映射 requested_role→requested_plan_role vs L2/L4/L5 取已命名键)须 parity「双键并存」口径。
- **Q6 测试序**:删任一手维列表**前**先改对应契约测试读收口点输出,同 commit,禁护栏裸奔窗口。
- **判定🟡**:条件=① owner 先裁(owner_pending=true);② R42 同批次(同改 build_workbench_plan_context 签名/dict);③ 收口含第5套 gantt_task_detail 别名元组(漏迁=债残留);④ parity 逐键四态矩阵钉死三关键键;⑤ 删丢键路径走收口点确定 fail-closed 默认。任一缺失即转🔴(静默 fail-open 脏写)。

### R44 — web selected_plan_role 是 core 收口点副本（P5 / 非承重 / owner_pending）
- **Q1 承重误删**:非承重,只喂模板显示 kwarg,不碰闸门。绿。
- **Q2 分层**:web→core 合法(import 真来源 schedule_plan_query_service:6),view_context 不反向 import web,无环。绿。
- **Q5 收口等价**:唯一差异 None→AttributeError(web) vs "adopted"(core),core 更防御,生产无 None 调用方(week_plan:352/gantt:299 入参恒 dict),反例不可达。
- **Q6 测试序**:唯一契约测试不钉 selected_plan_role getter,收口不变红;parity 测试同 PR 补即可。
- **判定🟢**:安全。条件极弱=排 SEQ-NAV 末位(R58→R54→R44)+ 动手前重盘 :6-7/:36-37 行号 + owner 裁 None 边界是否接受。

## 2) 漏项（本轮新发现没被计划覆盖的爆点/缺失前置）

1. **【数字打架·需订正】R54 dossier 字段1 键数与对抗核验自相矛盾**:dossier 表写 L1=13/L4=12,其对抗核验段又自纠 L1=12/L4=16,corrections F 又记 L1=12/L4=16。本轮 rg 仅核「三关键键齐全」未逐字数全键,**建议 Layer4 以 L1=12/L4=16/L2=16 订正字段1表**(不撼 split 结论,但 file:line 数字漂移须收口)。
2. **【N1 隐式化失忆=未被本簇修法终态覆盖】**:N1 `_identity_allows_query_membership_check:129-130` 收敛成单字段 `can_write_feedback`,与 R54/R58 同护栏概念但 owner_pending 只标不给终态。**爆点**:R54 收口若改 plan_role_filter_fields 全集语义,N1 隐式依赖 can_write_feedback⇒adopted-only 来源链(经 _can_write_feedback:89+_is_official_plan:70-84)无注释绑定 → 远端语义漂移时 N1 无守卫感知。前置缺失=N1 注释+绑 parity 须与 R54 同期(Batch-2)否则 R54 改真相源时 N1 失忆放大。
3. **【reports 第二注入路径=R54 收口的隐藏分叉】**:reports 缺三阻断态字段,经 reports_execution_review_context.py:39 `execution_review_context_overrides` 另一路注入。**R54 收口若把 reports 两条注入路径并一条 → 丢 plan_identity_blocking_error/error/blocking_scope 阻断态 → execution_review 阻断闸失效**。计划已警示但未列为 R54 收口的硬前置 parity 项,建议升为 R54 acceptance 必测。
4. **【批次张力未裁=R54↔R42 同批 vs batch_hint Batch-3】**:R54 deps 要求与 R42 同批次,batch_hint 把 R42 列 Batch-3、R54 列 Batch-2,内部冲突待 owner 裁(R42 提前 or R54 延后)。未裁即动 = 后落者 rebase 漂移后的 build_workbench_plan_context:187-258 整块,dict 键位移误删风险。
