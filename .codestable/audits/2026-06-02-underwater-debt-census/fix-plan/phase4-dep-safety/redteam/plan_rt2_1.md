# 红队第2轮·第1号 — 复攻1：第1轮采纳修订是否真改对了

> 视角：逐条 rg 回盘第1轮（RT1/RT2/RT3）采纳的 9 项修订，查「改对了吗 / 改出新依赖反序 / 批次撞行号」。只读不改。2026-06-05 实盘。

## 0. 结论速览

第1轮 9 项采纳修订中，**8 项锚点回盘完全成立、无新增依赖反序、无批次撞行号**：GF1 reject_integer_float 全仓零命中 + parse_required_int:81 + 文件 130 行（RT1-P0-1/RT2-2）；ready_queue 双文件 impl `core/algorithms/greedy/dispatch/ready_queue.py:103` + 垫片 `core/services/scheduler/graph/ready_queue.py:9`（11 行）（RT1-P0-2/RT2-3）；collar 宿主 `web/viewmodels/scheduler_workbench_links.py:187` + plan_id 形参 `:191` + collar return 不产三 fail-open 键（RT1-P1-4/RT2-1）；R42 跨文件删点 dashboard `:92 "plan_id"` + `:119 **` 展开 + dashboard 136 行（RT1-P1-3）；R49 dispatch_rules.py `parse_dispatch_rule:28`（RT3-P02）；全仓零 `as n` 别名（RT3 噪音清除）；16 个 RQErr 合同（RT3-P03，本号未独立复盘 test_ready_queue.py，留给他号）；R64 死 helper `_has_navigation_date_range:66` 零调用 + 活近亲 `_has_navigation_context:47` 真用（RT3-P01）。

**发现 1 个真问题**：RT3-P01 补登 R64/R65 时，对 **R65** 的措辞退化——把「死分支」误同质化成「零调用死 helper」，丢掉 R65 专属硬原子要件，照计划执行会 NameError。详见 §2。

## 1. 逐条回盘（实盘命中）

| 修订 | 计划锚点 | rg 回盘 | 判定 |
|---|---|---|---|
| GF1（RT1-P0-1/RT2-2） | reject_integer_float 全仓零命中；真符号 parse_required_int；文件 130 行 | `rg reject_integer_float`=0 命中；`strict_parse.py:81 def parse_required_int`；`wc -l`=130 | ✅ 成立 |
| ready_queue 双文件（RT1-P0-2/RT2-3） | impl :103 / 垫片 :9（11 行） | `greedy/dispatch/ready_queue.py:103 def get_ready_operation_ids`；`graph/ready_queue.py` 11 行，`:9 import`，`:11 __all__` | ✅ 成立 |
| collar 宿主（RT1-P1-4/RT2-1） | `web/viewmodels/scheduler_workbench_links.py:187`，不产三键，`plan_id:191` 形参在 | `:187 def`；`:191 plan_id: Any=None`；三键仅 `:294/295/296/369` context.get 消费（在 collar 体外下游判定函数），collar return（≈:231）不含三键 | ✅ 成立 |
| R42 跨文件删点（RT1-P1-3） | dashboard `:92 "plan_id"` + `:119 **` 展开，dashboard 136 行 | `dashboard:92 "plan_id"`；`:119 build_workbench_plan_context(`；`wc -l`=136 | ✅ 成立 |
| R49 宿主（RT3-P02） | `core/algorithms/dispatch_rules.py:28 parse_dispatch_rule` | `:28 def parse_dispatch_rule` | ✅ 成立（但消费图见 §2 备注） |
| 零 `as n` 别名（RT3 噪音） | 全仓零 `as n`，7 真调用方真名 import | `rg "as n"`=0；真调用方实为 **8** 生产文件（含 web/navigation_context.py） | ✅ 成立（调用方计 7→实 8，下沉非硬伤） |
| R64（RT3-P01） | `_has_navigation_date_range:66` 零调用 | `:66 def`，全仓仅 1 命中（def 自身），活近亲 `_has_navigation_context:47` 被 `:71/114/142/175` 真用 | ✅ 成立 |
| R65（RT3-P01） | 「同文件孪生 `:74-78 def + :160` 化简」「复核确为零调用死码」 | `:74 def _target_url`（**活函数**，`:160` 真引用，文件内出现 2 次），dossier 定性为 P6 **死分支**非死 helper | ⚠ **措辞退化，见 §2** |

## 2. 真问题清单

### 问题 1（Batch-A · R65 失忆债 / 误同质化）— 中危

**问题**：计划 §94/§145/§160 三处把 R65 与 R64 并称「**两份死 helper**」「R64/R65 死 helper（全仓零调用）」「复核 R65 孪生确为**零调用死码**」。但 dossier R65（`dossiers/R65.md` §1/§7/§9）与 `_layer3_explosion.md:84` 明确 R65 真身是 `_target_url` 的 **P6 死分支**——`web/viewmodels/scheduler_navigation_links.py:74-78 def` 体语法可达，被 `:160 _plain_link(label, plain_url or _target_url(...), ...)` 的 `or` 短路恒真遮蔽（9 条 spec 的 plain_url 字面量 9/9 非空，实盘 `:77 TARGET_PAGE_PATHS[target_page]` + `:177 TARGET_PAGE_PATHS[target]` 印证）。**R65 不是「零调用」**：`_target_url` 在 `:160` 有真实引用，只是运行期被短路。

**为什么会炸**：照计划「复核确为零调用死码 → 直删 :74-78 def」，因 `:160` 残留 `or _target_url(...)` 对已删符号的引用 → import-time/lint 即 NameError（`build_scheduler_navigation_links` 走 else 分支），dossier §52 原子性铁律已明警「只删 def 不化简 :160 → NameError」。计划全文对 R65 **未提**三件套硬原子的另两件：① 化简 `:160` 去掉 ` or _target_url(...)` 保留 plain_url；② 删孤儿 import `:4 urlencode`/`:6 query_for_target`（删 def 后变 F401）；也未提 `_layer3_explosion.md:84/85` 列的两条护栏：**保留 `:7 TARGET_PAGE_PATHS`**（`:177 build_report_navigation_links` 真用，误删则报表导航条全挂 NameError）+ 补不变量护栏 `test_all_nav_specs_have_nonempty_plain_url`（化简 :160 行为等价的唯一依据是「9 specs plain_url 恒非空」，无护栏则未来加空串 spec 即静默回退死分支）。

**修正建议**：把 §94/§145/§160 对 R65 的「死 helper / 零调用死码」措辞，改回 dossier 口径「`_target_url` **死分支**三件套硬原子：删 def `:74-78` + 化简 `:160`（去 `or _target_url` 留 plan_url）+ 删孤儿 import `:4/:6`」，并补两条禁区/护栏：**保留 `:7 TARGET_PAGE_PATHS`**、落 `test_all_nav_specs_have_nonempty_plain_url` 不变量护栏。R64（真零调用死 helper）与 R65（死分支）虽同文件同原子提交（防行号二漂，`_interference_rebuilt.md:17 G02` 已对），但**性质不同、改点不同**（R64 改 :66-67；R65 改 :74-78/:160/:4/:6），计划不可继续把二者同质化为「两份死 helper」。

### 备注（非问题，登记备查）
- **R49 消费图**：计划 §189 称 `parse_dispatch_rule` 被「greedy 内 `dispatch/sgs_scoring.py`/`dispatch/sgs.py`/`scheduler.py` 多文件消费」，但实盘 `rg parse_dispatch_rule` 全仓仅 2 命中（`dispatch_rules.py:28` 定义自身 + `tests/resource_dispatch/test_dispatch_rule_case_insensitive.py` 测试），**无任何 greedy 子模块消费**。§189 的「跨批串行炸（G25 先删旁支致 G24 主体孤儿 / G24 先删致悬空 NameError）」前提里的「共享 `parse_dispatch_rule` 调用图被 greedy 多文件消费」是夸大——真正待清的是 dossiers/R49.md 写的 `due_exclusive/parse_date` 别名垫片（evaluation/ortools），与 `parse_dispatch_rule` 是两码事。串行序结论（G25 旁支晚于或并回 G24）本身无害（保守），但「炸点」描述基于幻觉消费图，不影响安全只影响可信度，留作他号交叉。本号判其非硬伤。
- **零 `as n` 别名**：回盘成立（`rg "as n"`=0）。附带订正：collar `build_workbench_plan_context` 真调用方实为 8 个生产文件（计划 §388 记 7），多出 `web/navigation_context.py`；不影响删形参安全性（navigation_context 经 **kwargs 链 plan_id=0，§235 爆点 #12 已覆盖），仅计数下沉。

