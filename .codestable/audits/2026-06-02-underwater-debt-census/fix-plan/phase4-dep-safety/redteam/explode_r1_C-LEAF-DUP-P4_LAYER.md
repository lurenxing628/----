# 逐簇爆炸对抗 r1 — C-LEAF-DUP-P4 · 主透镜【分层导入环 + 迁移耦合】

> skeptic 第1轮，只读不改。默认怀疑：找不到爆点才算绿。
> 主透镜：Q2 分层导入环（LB04 删 shared 改指 services）/ Q3 迁移耦合（v18·v19 DB CHECK）/ repo→service 越层。
> 行号全部 rg/sed 当前工作区回盘（2026-06-05），不信 dossier 旧值。六质问点全过。

---

## 0) 回盘事实基线（本轮独立复核，与 dossier 对账）

| 债 | 回盘真实 file:line | 与 dossier 一致? |
|---|---|---|
| LB04 | `core/shared/boolean_normalize.py:33`(真叶子,仅 import typing) / matrix:168 / shim enum_normalizers:172 | ✅ 一致 |
| LB04 越层证据 | `core/models/schedule_config_runtime_coercion.py:6/192/201/230` 下行调 shared；matrix:5 反向 `from core.models.enums import YesNo` | ✅ 环论据坐实 |
| LB04 algorithms | `core/algorithms/` 零消费(ALGO-ZERO) | ✅ 前瞻成立 |
| R03 | runner.py:216 except / :217 _failed_plan / :28 class / `_baseline_missing_or_failed:263-267 return True` / dashboard_workbench.py:156 | ✅ missing 可达实证;:216 上方零注释 |
| R03 生产 raise | `raise .*CandidateTrialFailure` 生产侧零命中(PROD-RAISE-ZERO) | ✅ P6 成立 |
| R69 | guard:49 def / :206 / :212；runtime_support:19 def / :216；contracts.py 存在且无回指 | ✅ 消费者行号 :206/:212(非旧:143/:149) |
| R68 | degradation:123 def / loud 二元组 :132/:139/:140；收口家 summary_count_parse.py 存在未迁 | ✅ |
| R70 | 死副本 schedule_service.py:46；live run/collector.py:79/173/228/251/356；顶层壳 collector.py=185B 无符号 | ✅ 双文件+import:7/:217 |
| R53 | batch_order.py:39 形参 / :58 真消费 / :74 `_ = scheduled_count` / :75 return | ✅ unused-arg 不复发 |
| R61 | plan 死簇:160/164/172；live 孪生 _row_text:156 / normalize:119 / downtime:274(report_engine:406 调) | ✅ plan 死函数生产零调用 |
| R41 | enum_display *_zh:13/24/33/47/62/73；6 收口点 enum_normalizers 全存在;batch_status_label ABSENT | ✅ |
| R32 | backup.py integrity_check:334 / `except Exception as e:335` / `raise RuntimeError:342` / `os.replace:343` | ⚠️ **dossier 病灶语义偏差,见下** |
| R40 | material_repo.py:69 float / `except Exception:70` / `val=updates.get:72`;service _norm_float 真拦 | ✅ |
| **R43** | **scheduler_run.py 真实仅 8 行(sys.modules 重定向壳),roadmap:522 在 .codestable roadmap.md 非任何 .py** | 🔴 **dossier file:line 类目错误,见漏项** |
| v18/v19 | v18 建 OEE 基表(UNIQUE previous_state_revision:14);v19 加 `source_table='schedule'`/`effective_plan_role='adopted'` CHECK(:14-19) | ✅ adopted-only 下沉 v19 坐实 |

---

## 1) 🔴 红（会炸 — 一句灾难链）

**LB04 — 唯一真红区，但仅在"被错误执行成删 shared 改指 services"时引爆（计划本身=绿，执行纪律=红）**
- 灾难链：若以"统一到 matrix/DRY"名义删 `boolean_normalize.py` 让 `core/models/schedule_config_runtime_coercion.py:6` 改指 `core.services.common.normalization_matrix` → matrix:5 `from core.models.enums import YesNo` → 立刻形成 **`core.models → core.services.common → core.models.enums` 导入环 + core.models→core.services 越层**，击穿 AST 0 违规 + R29 分层前提 → 启动期 import 即炸（非静默，但全模块加载失败）。
- 第二条静默链：若单边改 matrix 别名集/枚举值（不删 shared），personnel `is_primary`/plugin enabled/system_config 三处（走 matrix 链）与调度开关侧（走 boolean_normalize 链）对同一原始串给出相反 yes/no，**无任何测试报警**（tests/ 零 parity）。
- 前置/禁区：唯一合法=`:33` def 上方补"我是故意的"注释（algorithms 论据标"前瞻"）+ 新建 `tests/regression_boolean_normalize_wide_parity_contract.py` 全矩阵 parity；**绝对禁删 shared 改指 services**；唯一合法消重方向=matrix 反向 delegate 到 shared（services→shared 下行），本批不执行。判定红是因主透镜核心爆点就在此，且 LB04 是 Batch-1 所有 yes/no 收敛动作的安全网前置——网未铺前任何收敛=裸奔。

---

## 2) 🟡 黄（有条件可做 — 条件/前置/裁断）

**R03(A) 承重注释段 🟡→实为绿**：仅 :216 上方补三行注释,逻辑零改,契约 runner_contract:473/486/488 已钉死意图。条件：禁碰 :28/:216/:217 三禁区行(禁改回 except Exception/禁透传/禁改基类)。可随 Batch-1 落。
**R03(B) 下游脚手架 🟡**：owner_pending=true,**待裁不给终态**。条件硬门：`_baseline_missing_or_failed:267 return True` 使 **missing 态生产可达**,dashboard_workbench.py:156 + helpers:390 **非纯死分支**;裸删=静默吞"无基准方案"真实告警。前置=None/missing/failed/completed 四态 parity + owner 裁 ScheduleCandidate.status 枚举契约(已落库 completed/failed/skipped/not_run,裸删破持久化兼容)。本轮不分配批次。
**R69 🟡**：收口 `_op_seq`→contracts.py(已存在,无回指,新增 guard→contracts 边无环)。条件：① 坏 seq **禁保留 `except (TypeError,ValueError): return 0`**(护栏文件内静默归 0→:207 `completed_seq<=0` 短路放空 / :212 比较污染→漏判后继工序需重算;runtime_support:217 `seq>completed_seq` 恒假→漏排工序)——P4 改 loud raise 或补可观测降级,owner 裁 loud 方向;② 先建坏-seq loud 护栏测试 + 单点 import 契约测试。**Q3 澄清:R69 改的是 revision 读侧过滤,不写 v19 CHECK 列(source_table/effective_plan_role 写在 guard:66/67 另一函数),与 v18·v19 DB CHECK 无耦合——主透镜迁移耦合维度对 R69 不成立(假关联)。**
**R68 🟡**：收口 `_meta_bool_state`→summary_count_parse.py(已存在未迁)。条件：① parity 测试 Batch-1 先于收敛 Batch-15;② **严禁压扁 `(bool,parse_failed)` 二元组为单 bool**(:132/:139/:140 loud 标记位),压扁=坏 meta 静默当 default 接受,前端丢"降级因 meta 异常"提示。
**R32 🟡**：owner_pending=true。条件：**dossier 病灶语义有偏**——回盘 integrity **不通过**时 :342 已 `raise RuntimeError`(loud);真正 fail-open 窄路只剩「PRAGMA **执行本身**抛异常」的 `:335 except Exception as e`→warning→:343 os.replace 仍升正式(跑不起 integrity 的库被当可信备份)。修法面比 dossier 描述小:P4 把 :335-337 改 loud raise。禁区 :338-342 else raise 不改弱、:343 os.replace 不加二次兜底、:346-352 finally 保留。owner 裁硬 raise vs 可观测降级。
**R40 🟡**：owner_pending=true。条件：只删 material_repo.py:70-72,**必保 :69 float 转换**(误连删=坏值落 REAL 列退化);生产路径不可达(service `_norm_float` 已拦,batch_material_service:31/material_service:32),改 raise 零行为影响。方向 A(删 except 让 :69 自然抛)零越层;方向 B 引 core.ValidationError 造 data→core 错误耦合,不推荐。owner 裁错误分类。
**R41 🟡**：owner_pending=true,owner 须先裁 4 语义(硬门控)。条件：6 收口点(enum_normalizers machine_status_label:124 等)全存在,`batch_status_label` ABSENT→**batch_status_zh 保留不收口,禁建新 label(=新 P5)**;ready 未知值现状贴回确定态(`ready_zh("weird")→"未齐套"`,test_enum_display_consistency.py:59 钉死),改 passthrough 暴露则此断言必同改;收口包装禁 try/except 吞错/禁贴回确定态。Batch-1(LB04 安全网)之后。
**R43 🔴→实为 🟡 但 file:line 全错（见漏项）**：删 9 wrapper + compat + 清 scheduler_config.py:91/95 双 sys.modules.get 软 fallback(删后永 None,退化单路,顶层壳 web/routes/scheduler_config.py=213B 仍在故 :95 当前可命中)。条件：删 wrapper 必与迁/删测试同 PR(中间态 CI 红);迁移面 22 文件(wrapper_import_order_contract 实 pin scheduler_batches+scheduler_run 两壳被动导入)。owner 须先认账 roadmap 延期决定。**E1 强串行:R43↔R26 共碰 scheduler_config.py+SP05,R26 先或合批。**

---

## 3) 🟢 绿（安全）

**R70**：纯删死副本 schedule_service.py:46-50,live(run/collector.py:79)不碰,保 :7 import(:217 仍用 ValidationError),零前置/零承重/零测试迁移/ISOLATED。两 collector 文件已确认(顶层 185B 壳无符号/run 真身),删错文件方向已钉死。
**R53**：纯删 batch_order.py:74 `_ = scheduled_count` 一行,:39 形参/:58 真消费(`_build(scheduled_count=scheduled_count)`)/:75 return 均真用,无 unused-arg 复发,契约 test_greedy_refactor_contracts:250 响亮拦截。
**R61**：删 plan 死簇(:160/164/172,生产零调用),严保 live 孪生 _row_text:156/normalize:119/downtime:274(report_engine:406 live);删函数+改测试(两负向测试重定向到 normalize)同 PR 原子,零覆盖损失。本删除不触 report_engine 一字,无跨债行号约束。

---

## 4) 漏项（本轮新发现，计划未覆盖的爆点/缺失前置）

1. 🔴 **R43 file:line 类目错误(高危漏项)**：cluster/dossier 称「主文件 scheduler_run.py」「roadmap 延期行 :522」「顶层 9 wrapper」——回盘 `scheduler_run.py` **真实仅 8 行**(`sys.modules[__name__]=_impl` 重定向壳),:518-525/:522 全空。延期文案 :522 实在 `.codestable/roadmap/p1-scheduler-debt-cleanup/...-roadmap.md`(markdown 行),**不在任何 .py**。Layer1 corrections §F 纠的「521→522」是 markdown 行号之争,但真正问题是**这行被当成 py 代码行号挂在 R43 头上**。执行时按「scheduler_run.py:522」找会扑空;wrapper 真身分散在 domains/scheduler/ + scheduler_batches.py 等,22 文件迁移面的锚点需在执行前整体重定位,否则 R43 整批落点失准。**前置缺失:R43 需先做一次 wrapper 真身 file:line 重盘,不可照 dossier 行号动手。**

2. 🟡 **R32 灾难链描述偏大**：dossier/cluster 暗示 integrity 失败也会升正式备份,实则 :342 已 raise 拦住「不通过」份,仅「PRAGMA 执行异常」窄路 fail-open。修法面小但方向对;红队/owner 评估 severity 时勿被放大的灾难链误导。

3. 🟢 **R69↔v19 DB CHECK = 假迁移耦合(澄清,非爆点)**：主透镜 Q3 担心 R69 改码触 v18·v19 CHECK 探针炸,回盘证实 `_op_seq` 是 revision 读侧过滤,不写 source_table/effective_plan_role 两 CHECK 列(写在 guard:66/67 别的函数)。本簇**无任何成员的修法触碰 v18/v19 DB CHECK**——迁移耦合维度对 C-LEAF-DUP-P4 整簇空转,可从本簇主透镜降权(adopted-only 下沉是他簇 LB01/R09 族的耦合面)。

4. 🟡 **R41 ready/source 语义反转测试是隐藏红绿灯**：`test_enum_display_consistency.py:59 ready_zh("weird")→"未齐套"` 把未知值贴回"未齐套"(齐套反义)——R41 改 passthrough 暴露未知值时,此断言+空串/None 多条(:60/:61)必须同 PR 改 loud,否则测试红或复活静默贴回。owner 裁 4 语义时这条是 ready 反转的具体落点,cluster 已提及但未点出测试行的确切断言值。
