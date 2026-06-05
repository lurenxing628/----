# 逐簇爆炸对抗 r1 · C-LEAF-DUP-P4 · 主透镜【承重误删】

> skeptic 第1轮，只读未改。行号全部 rg 回盘（2026-06-05），不信簇文件旧值。
> 结论：**本簇分析层承重逻辑 PASS，但锚点层重伤**——R70/R43 的删除位点彻底锚错（会删到承重正式函数/删到空气），R03 web 消费禁区行被别名遮蔽失踪。计划不可按现有 file:line 执行。

---

## 判定总表

| 债 | 判定 | 一句话 |
|---|---|---|
| R70 | 🔴 红 | 死副本锚点 `schedule_service.py:46-50` **不存在**，:46 实为承重正式函数 `_raise_schedule_empty_result`；`_op_seq` 在该文件零命中 |
| R43 | 🔴 红 | 主文件锚点全错：`scheduler_run.py` 仅 8 行薄壳、`_scheduler_compat.py` 仅 9 行，9 wrapper + `:522` 延期行全仓搜不到 |
| R69 | 🔴 红 | 坏 seq 静默 `return 0` 实在 `persistence_guard.py:49-53` + `runtime_support.py:19-23`（非簇称 :149）；runtime_support 还多 2 处 `:178/:193` return 0 未登 |
| R03 | 🟡 黄 | 承重段(A) :28/:216/:217 锚点全对可落；但 (B) 禁区 `dashboard_workbench.py:156` 消费点被别名 `comparison["n"]` 遮蔽、rg 零命中，禁区行失踪 |
| LB04 | 🟡 黄 | 函数体+行号对（:33/matrix:168/shim:172），但 matrix/shim **路径前缀全错**（簇写 scheduler/+web/routes/，实在 common/） |
| R41 | 🟢 绿 | 收口点 6 个 `*_label` 行号全对（82/124/159/209/220/231），但在 `common/enum_normalizers.py` 非簇写的 web/routes/enum_display |
| R68 | 🟢 绿 | 二元组 `(bool,parse_failed)` :123-140 + downtime:30-47 全对，收口家 summary_count_parse 存在 |
| R32 | 🟢 绿 | integrity :334 / except :335 / os.replace :343 三行号全对，灾难链成立可落 |
| R40 | 🟢 绿 | float :69 / except :70 / 静默 :72 全对，只删 :70-72 保 :69 |
| R53 | 🟢 绿 | 死面包屑 `_ = scheduled_count:74` + 禁区 :39/:58/:75 全对 |
| R61 | 🟢 绿 | 死簇 172-187/160/164 + live 孪生 274/156/119 全对 |

---

## 🔴 红 · 完整灾难链

### R70 — 删除位点+live锚点+twin框架三重失真（最危）
- **回盘**: `core/services/scheduler/schedule_service.py:44-52` 实为 `_raise_schedule_empty_result`（排产空结果**正式抛错**承重函数，:47 `ValidationError(...,field="排产")` + :217 复用 ValidationError）。`def _op_seq` 在该文件 **rg 零命中**。
- **簇称「live 唯一在 input_collector.py:79」亦错**：`def _op_seq` 真实只在 `run/schedule_execution_persistence_guard.py:49` + `run/schedule_input_runtime_support.py:19`，input_collector 零命中。
- **灾难链**: 按簇计划「纯删 schedule_service.py:46-50 死副本」→ 删到 `_raise_schedule_empty_result` 函数体 → 排产返回空结果时不再 loud raise「排产空」→ 静默吞 → 空排产计划被当正常版本落库 → 下游甘特/周计划空白无告警。**Q1 承重误删命中**。
- **修正**: 删除前必须 owner 重新定位「R70 死副本」真身（疑似已在历史中消失或锚点漂到其它 run/ 文件）；twin 框架推倒重建；`schedule_service.py:7` ValidationError import + :44-52 函数体列为绝对禁区。

### R43 — wrapper 群+522 延期行锚点失踪
- **回盘**: `web/routes/scheduler_run.py` 仅 **8 行**（`from ._scheduler_compat import load_scheduler_route_module` 薄壳）；`_scheduler_compat.py` 仅 **9 行**。两者都无 9 wrapper、无 `:522`。全仓 >400 行 scheduler route 文件、「先保留旧 wrapper」文案均 **零命中**。
- **灾难链**: 按簇/corrections「以 522 为准」去 `scheduler_run.py:522` 删 wrapper → 行不存在 → 迁移面 22 文件锚点全部以失锚行计算偏移 → 19 plain import-rewrite 漂改 → route 注册契约误删 → 路由注册表击穿（500 全线）。**Q1+Q6 命中**。
- **修正**: owner 先定位真实 wrapper 群所在文件（疑似 `domains/scheduler/` 深层或已被前序重构搬迁），522 延期行重新 rg 回盘后才能排批；本轮**禁锚定 scheduler_run.py**。

### R69 — 坏 seq 静默归 0 锚点 +63 漂移且漏登 2 处
- **回盘**: 簇称坏 seq `:149`。实盘 `persistence_guard.py:49-53` `def _op_seq … except (TypeError,ValueError): return 0`；消费者 :206/:212 对（簇已纠）。`runtime_support.py:19-23` 同款 return 0，**另有 :178/:193 两处 except→return 0 未登**。
- **灾难链**: 坏 op seq → 静默归 0 → :207 `completed_seq<=0` 误判已完成工序为「未开始」→ :212 revision 过滤把后继工序排到已完工序前 → 工序倒挂坏排程。P4 改 loud 时**若只改 :49/:19 漏改 :178/:193 → 仍有静默归 0 残口 fail-open**。
- **修正**: 改 loud 范围须含 runtime_support :19/:178/:193 全 3 处 + persistence_guard :49，缺一即护栏破口；owner 裁 loud raise vs 可观测降级标记。

---

## 🟡 黄 · 条件

### R03 — (A)可落 / (B)禁区行被别名遮蔽
- (A) 承重锚点全对：`runner.py:28` class CandidateTrialFailure / :216 except CandidateTrialFailure / :217 return _failed_plan / missing 态 `_baseline_missing_or_failed:267 return True` **确认存在**（missing 态生产可达铁律成立）。(A) 注释段可随 Batch-1 落。
- **条件/缺失前置**: (B) 禁区 `dashboard_workbench.py:156` 的 baseline 消费 **rg 零命中**——真键 `baseline_missing_or_failed`（summary:140）在 web 层走**别名 `comparison.get("n")`**（dashboard_workbench/analysis_candidates/helpers 多处）。**禁区行 :156 已漂失**。(B) 段四态 parity 前必须按真符号 `baseline_missing_or_failed` + 别名 `n` 两形态 grep 全消费点（同 D2 别名陷阱），否则裸删告警点定位失准、漏改别名读取方。

### LB04 — 逻辑对 / 路径前缀全错
- 函数体确认：`boolean_normalize.py:33 def normalize_yes_no_wide`（policy passthrough/raise/default 分支完整）。对照实现 `normalize_yes_no_wide_value` 在 **`core/services/common/normalization_matrix.py:168`**（簇写 scheduler/ 错）；shim **`core/services/common/enum_normalizers.py:172`**（簇写 web/routes/ 错）。
- **条件**: 注释+parity 唯一合法动作不变，但「上层 matrix 反向 delegate 下层」的合法下行方向须按真路径 services/common→shared 复核（不是 scheduler→shared）。禁删 shared 改指 services 铁律仍成立。路径写错不改判定，但批次执行时按错路径找文件会落空。

---

## 漏项（本轮新发现，计划未覆盖）

1. **R70 死副本根本不在簇锚点** — 计划「纯删 schedule_service.py:46-50」会删承重正式函数 `_raise_schedule_empty_result`；R70 整条需 owner 重定位真身后才可排，本轮应冻结。
2. **R43 9 wrapper + :522 延期行全仓失踪** — 主文件 `scheduler_run.py`/`_scheduler_compat.py` 均薄壳；22 文件迁移面锚点链全部建立在失锚行上，禁排批。
3. **R69 漏登 runtime_support.py:178/:193 两处 return 0** — P4 改 loud 若只改 def 处会留两处静默归 0 残口，仍 fail-open。
4. **R03 (B) 禁区 dashboard_workbench:156 消费点被别名 `n` 遮蔽** — 四态 parity 须按 `baseline_missing_or_failed`+`n` 双形态全仓 grep，计划只列 :156 单点不足。
5. **LB04/R41 路径前缀系统性错位**（matrix/shim/收口点实在 core/services/common/，非簇写的 scheduler/+web/routes/）— 不改判定但执行时找不到文件，需统一回写真路径。
