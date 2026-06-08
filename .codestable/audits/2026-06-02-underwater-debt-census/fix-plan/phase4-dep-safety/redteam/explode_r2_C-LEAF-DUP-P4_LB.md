# 逐簇爆炸对抗 r2 · C-LEAF-DUP-P4 · 主透镜【承重误删】

> skeptic 第2轮,只读未改。行号全部 rg 回盘(2026-06-05),不信簇文件/dossier/r1 旧值。
> **核心反转**:r1 把 R70/R43/R69 判红,本轮逐符号 rg 回盘证明 r1 那三条红**全是 r1 自己的回盘误判**(把薄壳别名当"失踪"、把同名函数当"承重正式函数"、把无关 `return 0` 当 R69 漏登)。簇文件 + dossier 的锚点经我独立 rg 全部坐实。本簇承重逻辑 PASS,锚点 PASS。

---

## 判定总表

| 债 | r1 判定 | **r2 判定** | 一句话(r2 rg 回盘) |
|---|---|---|---|
| R70 | 🔴 | 🟢 | `_raise_schedule_empty_result` **死副本确在 schedule_service.py:46**(本文件零调用),live 在 `run/schedule_input_collector.py:79`。r1「:46 是承重正式函数」=把函数名当承重,实为该死副本本身。 |
| R43 | 🔴 | 🟡 | 9 wrapper 实存,`scheduler_run.py:8` `sys.modules[__name__]=_impl` 薄壳**就是债本体**(薄=债,非失踪);roadmap 延期行 rg 实测 **:522**(dossier 体内 :521 自污染,簇/corrections 已纠为 522,采 522)。owner_pending=true → 黄。 |
| R69 | 🔴 | 🟢 | `_op_seq` 仅 guard:49+runtime_support:19 两份,消费 :206/:212/:216。r1「runtime_support :178/:193 漏登 return 0」=**误把 `_seed_op_id`/`_seed_seq` 两个无关函数的 return 0 当 R69 漏口**,不在 `_op_seq` 收口范围。 |
| R03 | 🟡 | 🟡 | (A) :28/:216/:217/:267 承重锚点全对可落;(B) owner_pending。r1「:156 被别名 n 遮蔽 rg 零命中」=**误判**,实测 dashboard_workbench:156 + helpers:390 均按真键 `baseline_missing_or_failed` 命中,禁区行在场不失踪。 |
| LB04 | 🟡 | 🟢 | boolean_normalize.py:33 真叶子(零 core import);matrix:168/shim:172 路径 `core/services/common/`(r1 已纠簇文件前缀错)。注释+parity 纯增量。 |
| R68 | 🟢 | 🟢 | degradation:123+downtime:30 二元组 `(bool,parse_failed)`,loud `return bool(default),True`@:132/:139/:140 在场;collar summary_count_parse.py 存在无该符号。 |
| R32 | 🟢 | 🟢 | backup.py:335 except warning→:343 os.replace;else raise :338-342。改 raise 只动 :335-337。 |
| R40 | 🟢 | 🟢 | material_repo.py:69 float / :70-72 静默回退坏值。只删 :70-72 保 :69。 |
| R53 | 🟢 | 🟢 | batch_order.py:74 死 `_ = scheduled_count`;:58 真消费在场,删后无 unused-arg 复发。 |
| R61 | 🟢 | 🟢 | 2026-06-08 已 fixed；旧死簇 :160/:164/:172 已删；live 孪生 `filter_downtime_*:244`、`_row_text:156`、`normalize_report_resource_filter:119` 在场禁删。 |

**净结论:8🟢 + 2🟡(R43/R03 均 owner_pending,非技术红),0🔴。** r1 的 3 红被本轮 rg 逐一推翻。

---

## 主透镜 Q1【承重误删】逐债扫(本轮重点)

### LB04 — 本簇最危爆点,但计划只补注释 = 安全(🟢)
- **rg 实证**:`boolean_normalize.py` `rg "^from core|from core\."` = **ZERO**,真叶子坐实。被 `core/models/schedule_config_runtime_coercion.py:6`(models 下行,合法)+ `core/services/scheduler/number_utils.py:5` 双链消费。matrix:5 `from core.models.enums import YesNo`(反向 import 论据成立)。
- **承重不对称真实存在**:下层 shared 是唯一真叶子事实源,上层 matrix:168 是语义全等对照实现,**无任何测试钉死二者等价**(`rg normalize_yes_no_wide tests/` 零)。任一侧单边改别名集 → personnel/plugin/system_config 链 vs 调度开关链对同串给相反 yes/no,**静默无报警**。
- **唯一会炸的动作(计划已禁)**:以「统一到矩阵/DRY」名义删 shared、令 models 改指 `core.services.common` → `core.models → core.services` 越层 + `core.models→core.services.common→core.models.enums` 导入环,击穿 AST 0 违规 + R29 分层前提。**计划只做 :33 上方注释 + 新建 parity 网,零删除零改指 → Q1 不触发。** 唯一合法消重=matrix 反向 delegate 到 shared(services→shared 下行),本批不执行。

### R03 — (A) 承重锚点全对,r1「禁区行失踪」证伪(🟡=owner_pending)
- **rg 实证**:runner.py:28 `class CandidateTrialFailure(RuntimeError)` / :216 `except CandidateTrialFailure as exc:` / :217 `return _failed_plan(...)` / :263-267 `_baseline_missing_or_failed` 末行 `:267 return True` 全部在场零漂移。missing 态生产可达铁律成立(无 baseline 候选 → True)。
- **证伪 r1**:r1 称「dashboard_workbench:156 被别名 `comparison.get("n")` 遮蔽、rg 零命中」。本轮实测 `dashboard_workbench.py:156` = `if comparison.get("baseline_missing_or_failed"):`(**真键直命中,无别名遮蔽**),且 `helpers.py:390` = `if bool(comparison.get("baseline_missing_or_failed")):` 同样真键命中。**禁区消费点未失踪,四态 parity 门可按真键 grep 全覆盖**(D2 别名 `n` 陷阱是 R42/build_workbench_plan_context 的,不波及 baseline 键)。
- (B) 下游 FAILED 脚手架仍 owner_pending(ScheduleCandidate.status 枚举契约),禁裸删 :156(会静默吞 baseline 缺失告警)。(A) 注释可随 Batch-1 落,黄因 (B) 待裁。

### 其余承重/正确性禁区(逐符号 rg 确认在场,删时勿碰)
- R70 禁区:`schedule_service.py:7` ValidationError import(:217 仍用,删则 NameError)+ :44-52 死副本本体只删不连带。
- R40 禁区:`material_repo.py:69` float 转换(只删 :70-72,误连删则坏值落 REAL 列退化)。
- R53 禁区:batch_order.py:39/:58/:75(:58 真消费在场,故删 :74 无 unused-arg 复发)。
- R61 禁区:`_row_text:156`/`normalize_report_resource_filter:119`/`filter_downtime_*:244`(live 孪生一字不动)。
- R32 禁区:backup.py:338-342 else raise 不改弱/:343 os.replace 不加二次兜底。

---

## Q2 分层导入环 · Q3 迁移耦合 · Q4 灵魂线热路径 · Q5 收口等价 · Q6 测试序

- **Q2(分层/环)**:LB04 删 shared 改指 services 的环已在主透镜列(计划禁,不触发)。R69 新增 `persistence_guard→schedule_input_contracts` 边:rg 实测 contracts.py 只 import `core.services.common.build_outcome`,**无 guard/runtime 回指 → 无环**。R41 `web→core.services.common.enum_normalizers`:enum_normalizers/matrix **无 reverse `import web` → 无环**。R68 收口同包 summary/ 水平 import 无环。**全簇 0 越层 0 环。**
- **Q3(迁移耦合)**:本簇无一与 v18/v19 DB CHECK 或 schema CHECK 耦合(R03 牵动的 `ScheduleCandidate.status` 是已落库枚举但属 (B) owner 裁断,非启动探针)。**无改码不改迁移=启动炸的成员。**
- **Q4(灵魂线热路径)**:R69 坏 seq→loud(guard:49 单点,改 loud 范围=guard:49+runtime_support:19 两份 `_op_seq`,**不含** r1 误指的 _seed_*:178/193)、R32 integrity except→raise、R40 float except→raise、R41 未知值 passthrough 暴露、R43 清 scheduler_config.py:95 软 fallback——均禁新增兜底/静默回退,P4 改 loud。无落扫历史/legacy 热路径放大(R32 severity=备份可信度面,非主排程热路径)。
- **Q5(收口等价)**:R68 收口前两份 diff IDENTICAL,parity 须钉 `(bool,parse_failed)` 完整二元组**禁压扁单 bool**(否则坏 meta 静默当 default,前端降级提示丢);R41 收口**非等价**(ready 空串"未齐套"↔"齐套"反转、_source 误判修复、day_type/priority/operator 空串文案变),全须 owner 裁 4 语义 + parity 钉死,禁贴回确定态。R70/R69 正常路径等价,差异仅在 except 分支(R69 改 loud)。
- **Q6(测试序)**:R68 parity 先于收敛(Batch-1→Batch-15 强序,倒序失网);R61 删函数+重定向两负向测试到 `normalize_report_resource_filter` **同 PR 原子**(中间态 CI 红);R43 先迁 19 plain → 删 wrapper → 删/改 3 契约(wrapper_import_order 整删/route_registration:88/sp05 三表);R41 先改 test_enum_display_consistency.py:59-61 为 loud 暴露**禁删了重钉静默**。

---

## 漏项(本轮新发现 / 对 r1 的纠正)

1. **r1 三红全系 r1 回盘误判,须从计划红区移除**:① R70「:46 是承重正式函数」——:46 就是死副本本体(本文件零调用),非承重,纯删安全;② R43「wrapper 群+522 失踪」——9 wrapper 实存、:8 薄壳即债、roadmap rg 实测 :522 在场;③ R69「runtime_support :178/:193 漏登」——那是 `_seed_op_id`/`_seed_seq` 无关函数,**不在 `_op_seq` 收口范围**(若把它们也"顺手统一"反而是 Q1 越界误删)。
2. **R69 的真实邻接陷阱(r1 误报但底层有真坑)**:runtime_support 内 `_op_seq`(:19)、`_seed_op_id`(:178)、`_seed_seq`(:193)三个函数都有 `except (TypeError,ValueError): return 0`,**长得一样但语义不同**。改 R69 时若 DRY 冲动把三者一起收口/改 loud = 把 seed 解析(允许缺省 0)误判成坏 seq → Q1 承重不对称误删。**前置禁区:R69 只动 `_op_seq` 两份,`_seed_*` 一字不碰。**
3. **R43 dossier 体内 :521 自污染**(corrections §F 已点名):dossier 字段1/2/12/索引 4 处写 521,真相源 522。执行前须以簇文件/本报告 :522 为准,勿被 dossier 体内污染值带偏。
4. **R03 (B) 四态 parity 按真键可全覆盖**:r1 担心的别名 `n` 遮蔽不成立,missing 态消费点(workbench:156 + helpers:390)均真键命中,但 (B) 仍须 owner 裁 failed 半支后才动,本轮冻结。
5. **LB04 注释须标 algorithms「前瞻」**:rg `core/algorithms/` 零消费 boolean_normalize,注释里 algorithms 论据是分层前瞻非现状,防日后被当幻觉误删。
