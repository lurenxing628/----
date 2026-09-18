---
doc_type: refactor-apply-notes
refactor: 2026-09-19-sgs-decode-pruning-and-memo
status: completed
summary: 第一步（剪枝开放自动派工）已实施并通过等价收据、定向合同与真实时钟基准；第二步按画像判定收益不足，本轮不做。
---

# 实施与证据

## 第一步：图优先剪枝开放给自动派工

- 改动：`sgs_priority_pruning.py`（认证拆分、`fixed_resources`、`for_cache` 走缓存认证）、`sgs_decode_acceleration.py`（尾段复用门槛）、`sgs_priority_frontier.py`（docstring）、`tests/algorithm/test_sgs_priority_pruning.py`（31 条）。
- 等价收据 `measure-before.json` / `measure-after-step1.json`（同一脏工作区，`--repeats 3`）：

| 工况 | 工序 | payload 逐位相同 | 评分次数 | 估算次数 | 解码中位耗时 |
|---|---|---|---|---|---|
| slot_auto_graph_unique | 144 | 是 | 1498→144 | 2040→1152 | 0.190→0.066 s |
| slot_auto_graph_tied | 144 | 是 | 2444→946 | 2990→2302 | 0.272→0.152 s |
| slot_auto_graph_window | 144 | 是 | 1283→458 | 1537→1148 | 0.147→0.083 s |
| slot_fixed_graph_unique（对照） | 144 | 是 | 144→144 | 144→144 | 0.025→0.026 s |
| scaled192_bounded_graph | 192 | 是 | 3256→192 | 3285→1152 | 0.348→0.080 s |
| scaled192_bounded_baseline（score_enabled=False 对照） | 192 | 是 | 4308→4308 | 2609→2609 | 0.382→0.378 s |
| scaled192_wide_graph | 192 | 是 | 4704→192 | 14000→4608 | 0.998→0.180 s |
| scaled480_bounded_graph | 480 | 是 | 20180→480 | 7938→2880 | 1.649→0.207 s |

- 静态检查：ruff 通过；`scan_complexity_entries`/`scan_oversize_entries` 为空（`_prepare` 曾 17，拆出 `_certify_operations` 后回到阈内）；`tools.scan_import_cycles` 本改动 0 新增环（基线外唯一新增项是他人未提交的 `web/routes/workbench/legacy_blueprints.py:112` 动态导入）。
- 定向测试：见下方补记。
- 定向测试（`env -u FORCE_COLOR .venv/bin/python -m pytest`）：SGS 缓存/共享槽/日历备忘/原生复用/朴素时间轴/估算一致性/greedy 重构合同/检查点/尾段/门禁元测试共 20 个文件 488 passed，唯一失败是 `test_sgs_priority_frontier.py` 里"自动派工保持全量扫描"的旧断言，按新决定改为"认证后走唯一堆（扫描减半以上）+ 并列键仍全量扫描"，改后剪枝 31 条 + 优先堆 9 条 40 passed。
- pyright（3.8）：产品文件 0 错误；`test_sgs_priority_pruning.py:75` 的 9 条 `OpForScheduleAlgo(**dict)` 报错为 HEAD 既有写法，本轮新增用例已用 `Dict[str, Any]` 标注规避。
- 工作区仍为脏（含他人未提交改动），以上为局部验证，不是 clean-worktree proof；未跑全量门禁。

## 真实时钟基准（改前快照 vs 改后，单机、脏工作区）

- 质量矩阵 8 例（10 s）：8 例 baseline 排程逐位相同；tiny 4 例改进分相同；medium_shift_pool：min_overdue 1128→1121（更好）、min_tardiness 850.5→849（更好）、min_weighted_tardiness 1128→1132.5（差 0.4%，两次重跑稳定，是搜索轨迹差异）、min_changeover 8/11 与 9/10 两次重跑各出现一次（噪声）。`compare` 因两例"improved objective regressed"报 failed，属真实时钟轨迹差异，非解码错误。
- 端到端 20 例：20 例 baseline 逐位相同；4 个自动派工例（shift_pool）解码数 102–110→207–216，四个目标全部更好；其余 16 例相同；`compare` passed。收据 `/tmp/aps-budget-20260919/{qm_step1,qm_step1b,e2e_step1}.json`（会被清理）。

## 第二步裁决

剪枝后 192 道工序单次图模式解码 0.08 s，其中约 0.10 s（含 profiler）在最小组那一个候选的 6 个机人对估算，每步只评 1 个候选，见证/机人对备忘没有复用对象；基线解码（score_enabled=False）每次 improve 只跑 1 次。台账/机人对分数备忘/派工键跳过预估只对基线解码给 1.5–2 倍，对整轮预算的贡献不到 20%，本轮不实施；记录于设计文档第二步。


## 推送与正式基线合同（2026-09-19 晚）

- 三笔提交：98fe552b（19 项修复）、642ec804（剪枝开放自动派工）、034e4d86（干净 HEAD 92ef3524 第 5 次运行、噪声下限那次晋升为正式基线夹具）。
- 直连推送触发 pre-push 日常门禁：并行车道通过，串行车道 942 passed + 2 failed（`test_real_matrix_does_not_regress_against_formal_historical_baseline`：`medium_shift_pool/min_changeover: improved objective regressed`；`test_quality_uses_lexicographic_target_order_not_componentwise_non_degradation`：构造不出权衡候选）。根因是全向量字典序非回归对真实时钟搜索结果不成立，任何一次夹具都挡不住尾部分量更差的运行；处理见 `.codestable/compound/2026-09-19-decision-quality-matrix-improved-primary-floor.md`：baseline 仍逐位，improved 只比罚分与主目标并保留 3/4 历史改进量。
