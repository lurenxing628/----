# 逐簇爆炸对抗 r2 · C-LEAF-DUP-P4 · 主透镜 SOUL（灵魂线热路径 + 收口等价）

> skeptic 第 2 轮，只读不改。默认怀疑：多维存疑即标红，不放过「测试绿但护栏已破」的静默失效。
> 行号均 2026-06-05 rg/sed 回盘当前代码，不信旧 blast。主攻 Q4/Q5/Q6。r1 三红（R69/R03/R41）全部代码复核坐实，本轮再挖深 + 揪 r1 漏的更宽爆面。

## 判定总表

| 债 | 判定 | 一句话 |
|---|---|---|
| R69 | 🔴 | `_op_seq` 坏 seq 改 loud 落 `_completed_downstream_rows`+`_downstream_operations` **双消费者**热路径；`seq=0/None`(合法,`or 0`)与坏类型同 raise→击穿 `:207/:262` 合法短路=可用性放大 |
| R03 | 🔴 | (B) 段四态 parity 未建即清理→静默吞 baseline-missing 真告警；missing 态 `:267 return True` 生产可达，下游 6 处消费(非 1 处)裸删任一即吞告警 |
| R41 | 🔴 | 收口对**全 6 枚举族**改语义非仅 ready：空串`"-"`→default-label、unknown 原值透传→`"未知"`、operator `停用/休假`→`停用`、ready 空串 `未齐套`→`齐套`；owner 未裁即收口=调度员误读，且测试 `:18/:19/:26` 钉旧态,绿化=接受静默改写 |
| R68 | 🟡 | `_meta_bool_state` 两份(degradation:123 / downtime:30)收口；downtime `:30` 紧贴 `_meta_int_state:23`(仅隔 7 行)→范围删/抽取易连带,且二元组同形 int/bool 首位混淆 |
| R32 | 🟡 | integrity `except:335` warning 吞→落 `:343 os.replace` 升正式;倒挂(重症放行/轻症 `:341 raise`)坐实;owner 未裁 raise/降级,system_backup:181 只 catch MaintenanceWindowError→RuntimeError 裸 500 |
| R40 | 🟡 | 只删 `:70-72`(except+`val=updates.get`)保 `:69 float`;误连删→坏值落 REAL 退化;生产 service `_norm_float` 已拦故行为零影响;owner 裁错误分类 |
| R43 | 🟡 | 删 wrapper 须同清 scheduler_config.py:95 软 fallback;roadmap 延期行 :522(非 521,dossier 4 处污染);迁 22 文件 |
| R70 | 🟢 | 纯删 schedule_service.py:46-50 死副本,live 在 run/input_collector.py:79,保 :7 import |
| R53 | 🟢 | 纯删 batch_order.py:74 `_ = scheduled_count`,:58 仍真用 |
| R61 | 🟢 | 2026-06-08 已 fixed；旧死簇:160/164/172-187 已删 + 负向测试已重定向,后续仍禁删 _row_text:156/normalize_report_resource_filter:119/filter_downtime_*:244 |
| LB04 | 🟢 | 纯增量注释+parity;boolean_normalize.py 仅 import __future__+typing=真叶子,algorithms 零消费(rg ZERO);禁删 shared 改指 services |

---

## 🔴 红区（会炸，灾难链 + 前置）

### R69 — 坏 seq 改 loud 落双消费者热路径，seq=0 合法短路被 loud 化击穿
回盘坐实(persistence_guard.py)：`def _op_seq:49`,函数体 `:51 return int(getattr(op,"seq",0) or 0)` / `:52 except (TypeError,ValueError):` / `:53 return 0`；消费 `:206 completed_seq=_op_seq(completed_op)` / `:207 if not completed_batch_id or completed_seq<=0: return out` / `:212 _op_seq(op)<=completed_seq`。**runtime_support.py 平行第二份**：`def _op_seq:19`(同体)，消费链 `:262 if not completed_batch_id or completed_seq<=0: continue` + `:216 seq=_op_seq(op)`(内层循环)。blast :143/:149 已过期,必用上述。
**灾难链（loud 化反向爆点，r1 已点本轮坐实+加深）**：
1. 现状静默病:坏 seq→`return 0`,若 completed_op 坏 seq→`:207`/`:262` 短路放空整 downstream→后继工序漏判重算 revision、`:216 seq>completed_seq` 恒假漏排——确为 P4 残留。
2. **反向爆点(关键)**:`_op_seq` 体是 `int(getattr(op,"seq",0) or 0)`——`seq=None`/`seq=0`/`seq=""` 全走 `or 0` 正常返回 0,**不进 except**;`:207/:262 completed_seq<=0` 把这当**合法「无有效完成态」短路**(放空,不报错)。若 P4 粗暴把 `_op_seq` 内坏值直接 raise,且 loud 范围误含 `seq=0/None`(合法默认),则两个热路径 `_completed_downstream_rows`+`_downstream_operations` 从「静默放空」翻成「扫描 raise」=**execution persistence 护栏热路径可用性放大**。loud 必须**只对非数/坏类型(TypeError/ValueError 域)raise**,`or 0` 兜的 None/0/空串合法路径不得卷入。
**前置**:① owner 裁 loud raise vs 可观测降级;② parity **必须在两份(guard+runtime)同时**钉 `seq=0/None`(走短路,不 raise)与 `seq="abc"`(loud raise)两反例;③ 收口家 schedule_input_contracts.py 已存在(4693B)、imports 无回指 guard/runtime(已核 `:7 from core.services.common.build_outcome`),guard→contracts 新边无环成立;④ 收口须两份同改,否则一份 loud 一份静默=parity 裂。

### R03 — (B) 段四态 parity 未建即清理 = 静默吞 baseline-missing 告警；下游消费 6 处(非 1 处)
承重三禁区零漂移坐实:`class CandidateTrialFailure(RuntimeError):28` / `except CandidateTrialFailure:216` / `:217 return _failed_plan`。生产侧 `raise CandidateTrialFailure` 仅 tests(470/576),failed 半支不可达成立。**但 `_baseline_missing_or_failed:263` 体 `:267 return True`**(候选列表无 baseline 类目时)→missing 态生产可达,非纯死分支。
**下游消费面比 r1 更宽(本轮揪)**:`baseline_missing_or_failed` 被消费于 `dashboard_workbench.py:156`、`scheduler_analysis_candidates.py:225/262/288`、`scheduler_analysis_candidate_helpers.py:390`、`schedule_candidate_summary.py:140/166`——**6 处下游**。
**灾难链**:(B) 段若把这些当「P6 全死」裸删任一→静默吞「无基准方案」真实用户告警(用户看不到 baseline 缺失提示,无报错)。
**前置**:(A) 注释段随 Batch-1 落(仅 :216 上方补三行,零逻辑);(B) owner 裁 ScheduleCandidate.status 枚举契约前禁动,清理须先建 None/missing/failed/completed 四态 parity,missing 态保留+补不可达注释。**绝不裸删 dashboard_workbench:156 及上列 6 消费点任一**。

### R41 — 收口对全 6 枚举族改语义(非仅 ready),空串/未知/operator 三类静默翻面 + 测试钉旧态
**r1 只盯 ready,本轮逐 def 对照坐实改面远更宽**。旧 zh(enum_display.py)vs 收口 label(enum_normalizers.py)三类系统性差异:
1. **空串翻面**:旧全族 `return v or "-"`(machine:21/operator:29 末行/day_type/priority/ready)。收口 ready_status_label:221 `default=ReadyStatus.YES`→`""→"齐套"`(旧 `ready_zh("")→未齐套:79`);machine/operator/day_type label 末行 `return v or "未知"`→`""→"未知"`(旧 `"-"`)。**「-」与「齐套/未知」对调**。
2. **unknown 透传翻面**:旧 `return v or "-"` 对未知值原样透传(测试 `:18 machine_status_zh("weird")=="weird"`、`:25 operator..("weird")=="weird"`)。收口 label `unknown_policy="passthrough"` 后末行 `v or "未知"`,但若 normalize 不透传未知→`"未知"`,**原值→「未知」**,展示信息丢失。
3. **operator 标签语义窄化**:旧 `operator_status_zh INACTIVE→"停用/休假":29`,收口 `operator_status_label:87 return "停用"`——**「停用/休假」缩成「停用」,丢"休假"语义**。
4. **ready 中间态 r1 已揪**:`ready_zh:73` 三态(`:76 齐套/:78 部分齐套/:79 未齐套`),dossier 漏 `:78` 中间态,parity 须覆盖。
**灾难链**:排产/资源/日历页直接收口未审→空 ready 字段 `未齐套`翻`齐套`→**调度员把未齐套批当齐套放行**(纯展示无报错无测试拦);operator 列「休假」隐去看成「停用」。
**测试复活风险(Q6)**:`test_enum_display_consistency.py:18/19/25/26` 钉死旧态(`weird→weird`、`""→"-"`)。收口/改 loud 后这些测试**必红**;若改测试断言去贴合收口输出(`"-"→"未知"`/`weird→未知`)=**接受静默改写、绿化即复活**。`:59/60/61` 钉静默的断言改 loud 暴露**禁删**。
**前置**:owner 多裁断硬门(ready 空串/未知文案、operator 停用/休假→停用、machine/day_type/priority 空串「-」→label 默认、unknown 透传去留);全 6 族 × {合法/空串/None/未知/多枚举态} parity 钉死逐格差异;排 Batch-1(LB04 安全网)之后。

---

## 🟡 黄区（有条件可做）

- **R68**:回盘 degradation `_meta_bool_state:123`(体 `:125/128/131 ...,False`+`:132/139/140 return bool(default),True` loud 二元组)。**downtime 文件回盘纠偏(cluster/r1 行号偏)**:downtime 同时有 `_meta_int_state:23`(`:27 return 0,True`)**和自己一份 `_meta_bool_state:30`**(`:39/46/47 return bool(default),True`,与 degradation 逐字同)——被收口的是 downtime:30 这份。**爆点加深**:`_meta_int_state:23` 与待删 `_meta_bool_state:30` **同文件仅隔 7 行紧邻**,范围删/抽取-method 极易连带;且二者 `(_,parse_failed)` 二元组同形,int 首位 vs bool 首位混淆。条件:只提升 degradation:123 单符号到 summary_count_parse.py(已存在),删 downtime:30,**逐符号删禁碰 downtime:23 `_meta_int_state`、禁压扁二元组保 parse_failed 位**。

- **R32**:回盘坐实 `:335 except Exception as e:` warning(`:337 ...执行失败(已忽略)`)→`:339 else` 仅 `:341 raise RuntimeError`(校验跑通≠ok)→无条件落 `:343 os.replace` 升正式。**倒挂坐实**:重症(integrity 跑不起)`:335` 静默放行、轻症(跑通≠ok)`:341` raise。条件:① owner 裁硬 raise vs 可观测降级;② precondition `system_backup.py:181` 只 catch MaintenanceWindowError(非 R32 的 RuntimeError),R32 RuntimeError 落裸 500,须同改/后补;③ 禁区 `:339 else` 分支 raise 不改弱、`:343 os.replace` 不加二次兜底、`:347-352 finally` 清理保留。**强制回归项**:`else` 未被连带改弱(r1 漏项 5)。

- **R40**:回盘坐实 `:69 val=float(val)`(在 try 内)/`:70 except Exception:`/`:72 val=updates.get("stock_qty")` 静默回退坏值。条件:方向 A 只删 `:70-72` 让 `:69 float` 自然抛 ValueError(零 import 零越层),**必保 :69**(误连删→坏值落 REAL 列退化);方向 B 引 core.ValidationError 造 data→core.infrastructure 错误耦合(不推荐);owner 裁错误分类。生产 service `_norm_float` 已拦,改 raise 零行为影响。

- **R43**:删 wrapper 多 loud(删错 ModuleNotFoundError 红,非静默)。唯一静默点=`domains/scheduler/scheduler_config.py:95 sys.modules.get` 软 fallback,删 wrapper 后永 None→退化单路,须主动清。条件:owner 认账 roadmap 延期行 **:522**(非 521,dossier 4 处反向污染,以 522 为准);迁 22 文件(19 plain+3 契约);删 wrapper_import_order_contract 整文件。

---

## 🟢 绿区（安全）

- **R70**:纯删 schedule_service.py:46-50 死副本,live 唯一 run/schedule_input_collector.py:79(顶层壳无此符号),保 `:7 ValidationError` import(`:217` 仍用)。零承重零收口。
- **R53**:纯删 batch_order.py:74,`:58` 仍真用 scheduled_count 无 unused-arg 复发;禁区 :39/:58/:75。
- **R61**:2026-06-08 已 fixed；旧死簇 :160/:164/:172-187 已删除, :64-84 负向测试已重定向到 normalize_report_resource_filter(零覆盖损失);后续仍禁删 _row_text:156/normalize_report_resource_filter:119/filter_downtime_*:244 live。
- **LB04**:回盘坐实 boolean_normalize.py 仅 `from __future__`+`from typing`=真叶子;`enum_normalizers.py:21/172/173` 为 shim re-export;**algorithms 零消费(rg `core/algorithms/` ZERO)**。纯增量注释+parity。**禁删 shared 改指 services**(造 models↔services 环+越层);唯一合法消重=上层 matrix 反向 delegate 到 boolean_normalize(本批不执行)。

---

## 漏项（本轮新发现，计划未覆盖的爆点 / 缺失前置）

1. **【R41 改面远超 ready,r1/dossier 严重低估】**逐 def 对照:空串(全族 `"-"`→`default-label/未知/齐套`)、unknown(透传原值→`未知`)、operator(`停用/休假`→`停用`)三类系统性翻面,非仅 ready 一处。parity 必须全 6 族 × 5 类逐格,owner 裁断门从 4 处扩到 ≥6 处(加 machine/operator unknown 透传去留)。**遗漏将批量静默改写排产/资源/日历/操作员四类页面展示**。
2. **【R41 测试复活硬门,Q6】**`test_enum_display_consistency.py:18/19/25/26` 当前钉旧态(weird→weird、""→"-")。收口后必红;改断言贴合收口=接受静默改写的复活。Layer4 须把「这些断言是改 loud 暴露差异、禁贴回收口输出」列为 R41 验收硬门,否则测试绿=护栏破。
3. **【R69 双消费者 parity 裂】**`_op_seq` 有两份(guard:49 + runtime_support:19),消费短路两处(guard:207 + runtime:262)。收口/改 loud **必须两份原子同改**,否则一份 loud 一份静默归 0=parity 裂、行为分叉。r1 只描 guard 一侧,runtime:262 镜像短路 + :216 内层 `_op_seq` 调用同受影响,须显式纳入。
4. **【R69 seq=0 合法路径双兜底】**`_op_seq` 体 `int(getattr(op,"seq",0) or 0)` 两层兜 None/0/空串(getattr 默认 0 + `or 0`),与 except 域(TypeError/ValueError)正交。loud 化只能动 except 域,`or 0` 兜的合法 0 路径(走 :207/:262 短路)不得卷入 raise,否则护栏热路径可用性放大。parity 须钉 seq=None/0(不 raise)。
5. **【R68 行号回盘纠偏 + 紧邻爆点】**cluster/r1 把 downtime 异形邻居记为 `:27 return 0,True` 单点,实盘 downtime **同时有 `_meta_int_state:23` 与待删 `_meta_bool_state:30`,仅隔 7 行紧邻**——待删的 bool 份就贴在 int 份正下方,范围删/抽取-method 连带 int 份的物理风险被低估,须逐符号(非逐行范围)删。
6. **【R03 下游消费面 6 处,r1 记 1 处】**baseline_missing_or_failed 消费于 dashboard_workbench:156 + analysis_candidates:225/262/288 + helpers:390 + candidate_summary:140/166,共 6 点。(B) 段清理「死分支」判断须覆盖全 6,裸删任一即吞 missing 告警。
