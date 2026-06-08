# 逐簇爆炸对抗 r1 · C-LEAF-DUP-P4 · 主透镜 SOUL（灵魂线热路径 + 收口等价）

> skeptic 第 1 轮，只读不改。默认怀疑：多维存疑即标红，不放过「测试绿但护栏已破」的静默失效。
> 行号均 2026-06-05 rg 回盘，不信旧 blast。主攻 Q4/Q5/Q6。

## 判定总表

| 债 | 判定 | 一句话 |
|---|---|---|
| R69 | 🔴 | 坏 seq 改 loud 落 `_completed_downstream_rows` 热路径，但收口家落点+loud 方向 owner 未裁，且 :207 短路语义被 loud 改写后行为分叉 |
| R03 | 🔴 | (B) 段四态 parity 未建即清理 → 静默吞 baseline-missing 真告警；missing 态 :267 生产可达推翻全死叙事 |
| R41 | 🔴 | ready_zh 实测三态(齐套/部分齐套/未齐套)，dossier 只列两态；空串反转(未齐套↔齐套)owner 未裁即收口=静默误导调度员放行未齐套批 |
| R68 | 🟡 | 收口须保 `(bool,parse_failed)` 二元组 loud；downtime `:27 return 0,True` 是 `_meta_int_state` 异形邻居，混收即炸 |
| R32 | 🟡 | except→raise 方向对，但 system_backup.py:108 仅 catch MaintenanceWindowError → RuntimeError 落裸 500；owner 未裁硬raise/降级 |
| R40 | 🟡 | 只删 :70-72 保 :69 float；误连删则坏值落 REAL 列退化；owner 未裁错误分类 |
| R43 | 🟡 | 删 wrapper 须同清 domains/scheduler_config.py:95 软 fallback；roadmap 延期行 owner 未认账=抢跑 |
| R70 | 🟢 | 纯删 schedule_service.py:46-50 死副本，live 在 run/ 子目录，保 :7 import |
| R53 | 🟢 | 纯删 batch_order.py:74 一行，:58 仍真用无 unused-arg 复发 |
| R61 | 🟢 | 直删死簇:160/164/172-187 + 重定向负向测试到 normalize_report_resource_filter |
| LB04 | 🟢 | 纯增量注释+parity；boolean_normalize 真叶子(零 core import)，禁删 shared 改指 services |

---

## 🔴 红区（会炸，灾难链 + 前置）

### R69 — 坏 seq 改 loud 落热路径，收口/loud 方向 owner 未裁 + 短路语义分叉
回盘坐实(persistence_guard.py)：`def _op_seq :49` / 消费 `:206 completed_seq=_op_seq(completed_op)` / `:212 _op_seq(op)<=completed_seq`；runtime_support `:19 def` / `:216 seq=_op_seq(op)`。blast :143/:149 已过期 +63，必用 :206/:212。
**灾难链（改错=静默炸）**：
1. 现状坏 seq → `except (TypeError,ValueError): return 0`。回盘 `:207 if not completed_batch_id or completed_seq <= 0: return out` —— 若 **completed_op 自己**坏 seq 归 0 → `:207` 短路 return 放空整个 downstream 集合 → 后继工序漏判需重算 revision；runtime_support `:217 seq>completed_seq` 恒假 → 算法侧漏排工序。这是当前静默病。
2. **改 loud 的反向爆点（本轮新揪）**：`:207` 把 `completed_seq<=0` 当作「无效完成态、正常放空」的 legit 短路分支。若 P4 把 `_op_seq` 内部坏 seq 直接 `raise`，则 **completed_op.seq 为 0/None 的合法场景**（BatchOperation.seq 默认 0）会从「:207 静默放空」变成「整个护栏扫描 raise」——`_completed_downstream_rows` 是 execution persistence 护栏热路径，可用性放大。loud 必须只对**非数/坏类型**(TypeError/ValueError 域)raise，**不得**把 `seq=0`（合法）也卷进 raise，否则 :207 短路语义被击穿。dossier 未区分「坏 seq raise」vs「seq=0 合法短路」二者在 loud 化后的分叉。
**前置**：① owner 先裁 loud raise vs 可观测降级；② parity 测试必须分别钉 `seq=0`(走 :207 短路，**不 raise**) 与 `seq="abc"`(loud raise) 两反例，证明 loud 化没污染合法 0 短路；③ 收口家 schedule_input_contracts.py 已存在、无回指(已核 NONE)，guard→contracts 新边无环成立。

### R03 — (B) 段四态 parity 未建即清理 = 静默吞 baseline-missing 告警
回盘坐实：`except CandidateTrialFailure :216` / `_failed_plan :217` / `class :28` 三承重禁区零漂移；生产侧 `raise CandidateTrialFailure` 仅 tests:470/576，**生产零 raise** → failed 半支不可达成立。**但 `_baseline_missing_or_failed :267 return True`**（无 baseline 候选时）→ `dashboard_workbench.py:156 if comparison.get("baseline_missing_or_failed")` **missing 路径生产可达，非纯死分支**。
**灾难链**：若 (B) 段把 dashboard_workbench:156 / helpers:390 当纯死分支裸删 → 静默吞「无基准方案」真实用户告警（用户看不到 baseline 缺失提示，无报错）。
**前置**：(A) 注释段可随 Batch-1 落（仅 :216 上方补三行，零逻辑）；(B) **owner 裁 ScheduleCandidate.status 枚举契约前禁动**，清理须先建 None/missing/failed/completed 四态 parity，missing 态保留+补不可达注释。**绝不裸删 dashboard_workbench:156**。R03 列入红区是因 (B) 段在四态 parity 未就位时极易被「P6 全死」叙事误导成裸删。

### R41 — ready_zh 三态(dossier 漏中间态) + 空串反转 owner 未裁即收口
回盘坐实：`ready_zh def :73` → **`:76 return "齐套" / :78 return "部分齐套" / :79 return "未齐套"`**。dossier 字段1/字段7 只列 ":79 未齐套" 末行，**漏报 :78 "部分齐套" 中间态**。收口到 ready_status_label 时 parity 矩阵必须覆盖映射到「部分齐套」的输入，否则中间态静默丢失或错并入二值。
空串反转坐实：`normalization_matrix _enum_alias_lookup :100 if text=="": :101 return str(default)`，ready default=YES → `ready_status_label("")=="齐套"`；旧 `ready_zh("")=="未齐套"`。
**灾难链**：直接收口未审空串 → 排产批次页 ready 列对空 ready 字段从「未齐套」翻「齐套」→ **调度员把未齐套批当齐套放行**，纯展示无报错无测试拦=静默。
**前置**：owner 三裁断门（ready 空串/未知目标文案、operator "/休假"、day_type/priority/operator 空串"-"→label 默认）；测试 `test_enum_display_consistency.py:59/60/61` 改 loud 暴露**禁删了重钉静默**；须排 Batch-1(LB04 安全网)之后。

---

## 🟡 黄区（有条件可做）

- **R68**：收口前提=先建 parity(Batch-1) 后收敛(Batch-15)。回盘 degradation `:132/139/140 return bool(default),True` + downtime `:39/46/47` 二元组 loud 对齐。**爆点**：downtime `:27 return 0, True` 是 `_meta_int_state`（int 首位）异形邻居，与 `_meta_bool_state`(bool 首位) 同二元组形态——收口时若把两个文件的 `_meta_*` 误并/压扁，会把 int/bool 首位混淆且丢 parse_failed 位。条件：只提升 `_meta_bool_state` 单符号到 summary_count_parse.py(已存在，仅 parse_summary_count)，禁碰 `_meta_int_state`，禁压扁二元组。

- **R32**：except→raise 方向对，回盘坐实 `:335 except Exception as e:` 只 warning(:337) → 无条件落 `:343 os.replace` 升正式（重症放行、轻症 :340-342 else raise=倒挂）。条件：① owner 裁硬raise vs 可观测降级；② precondition system_backup.py:108 仅 catch MaintenanceWindowError，R32 的 RuntimeError 落裸 500，须同改或后补 except RuntimeError；③ 禁区 :340-342 else raise 不改弱、:343 os.replace 不加二次兜底、:346-352 finally 保留。

- **R40**：回盘坐实 `:69 val=float(val)` / `:70 except Exception:` / `:72 val=updates.get("stock_qty")` 静默回退坏值。条件：方向 A 只删 :70-72 让 :69 自然抛 ValueError(零 import 零越层)，**必保 :69 float**(误连删→坏值落 REAL 列退化)；方向 B 引 core.ValidationError 造 data→core.infrastructure 错误耦合(不推荐)；owner 裁错误分类。生产路径不可达(service _norm_float 已拦)，改 raise 零行为影响。

- **R43**：直删 wrapper 多为 loud(删错即 ModuleNotFoundError 红，非静默)。**唯一静默点**=domains/scheduler_config.py 回盘 `:95 sys.modules.get("web.routes.scheduler_config")` + `:97 compat_resolver()` 调用，删 wrapper 后永 None→走 :99 默认单路，须主动清 :95-98 软 fallback。条件：owner 认账 roadmap 延期行（**回盘实测在 :522「先保留旧 wrapper」，:521 是空行——R43 dossier 4 处写 521 是反向污染，以 522 为准**，与 L1§F/cluster E节一致）；迁 22 文件(19 plain+3 契约，registry 15 低估)；删 wrapper_import_order_contract 整文件。

---

## 🟢 绿区（安全）

- **R70**：纯删 schedule_service.py:46-50 死副本(回盘 :46 def/:47 ValidationError)，live 唯一在 run/schedule_input_collector.py:79（顶层壳无此符号），保 :7 import(:217 仍用 ValidationError)。零承重零收口零测试迁移。
- **R53**：纯删 batch_order.py:74 `_ = scheduled_count`，:58 仍真用故无 unused-arg 复发；禁区 :39/:58/:75。sgs.py:127 同形态行非本债。
- **R61**：2026-06-08 已 fixed；旧 :160/:164/:172-187 死簇已删除，:64-84 负向测试已重定向到 normalize_report_resource_filter(零覆盖损失)；后续仍禁删 _row_text:156 / normalize_report_resource_filter:119 / filter_downtime_*:244 live 孪生。
- **LB04**：纯增量。回盘 boolean_normalize.py 仅 import `__future__`+`typing`=真叶子；matrix `:5 from core.models.enums`、coercion `:6 from core.shared.boolean_normalize`=models→shared 合法下行；algorithms 零消费(rg ZERO)。禁删 shared 改指 services(造 models↔services 环+越层)，注释里 algorithms 标「前瞻」。

---

## 漏项（本轮新发现，计划未覆盖的爆点 / 缺失前置）

1. **【R41 漏报中间态】ready_zh 实测三态(:76 齐套/:78 部分齐套/:79 未齐套)**，dossier 字段1/7 只列「:79 未齐套」末行，漏 :78「部分齐套」。收口 parity 矩阵必须显式覆盖「部分齐套」映射，否则中间态被静默并入二值——这是计划 parity「{合法值,空串,None,未知串}四类」未列的第五类（多枚举态）。
2. **【R69 loud 化反向爆点】**计划只讲「坏 seq 静默归 0→改 loud」，未识别 `:207 completed_seq<=0` 是合法短路分支。`BatchOperation.seq` 默认 0，loud 化若把 `seq=0`(合法) 与 `seq="abc"`(坏) 同等 raise，会把 :207 正常放空路径改成护栏热路径 raise=可用性放大。前置缺失：parity 必须分别钉 seq=0(不raise) 与坏类型(raise) 两反例。
3. **【R68 异形邻居】downtime :27 `return 0, True` 是 `_meta_int_state`(int 首位)**，与 `_meta_bool_state`(bool 首位) 同 `(_, parse_failed)` 二元组形态、相邻同文件。计划「严禁动 _meta_int_state」成立，但未点出二者二元组同形=误并/误压扁时 int/bool 首位混淆的具体撞点。收口排程须显式隔离两符号。
4. **【R43 roadmap 行号污染回灌风险】**R43 dossier 在 4 处(字段1/2/12/索引)把真相源 522 反向改成 521，本轮回盘实测延期文案在 :522、:521 为空行。Layer4 出批次若照抄 R43 dossier 的 521 会回灌错误锚点——已在黄区显式纠为 522(与 L1§F/cluster 一致)。
5. **【R32 倒挂未列为独立校验项】**「校验跑不起来(重症)放行、校验跑通但≠ok(轻症)raise」的倒挂，计划修法只对齐 except→else，但未把「确认 :340-342 else 在修后仍 raise、未被连带改弱」列为强制回归断言项(parity 用例 4)。Layer4 须把 else 分支未改弱纳入 R32 验收门。
