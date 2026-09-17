---
doc_type: decision
category: convention
date: 2026-09-17
slug: test-suite-slimming-and-browser-lane
status: active
area: quality-gate
tags: [tests, quality-gate, browser-lane, perf-marker, registry, python38]
---

## 背景与授权

用户反映全量门禁要跑一个多小时，怀疑绝大多数测试是垃圾。按 2026-09-14 那次全量运行留下的逐用例耗时记录核算：11303 个已执行用例累计 145 分钟，其中 235 个工作台浏览器用例占 60 分钟，9 个按"宽度 × 主题"跑 4 遍的验收文件占 30 分钟，gate_meta 元测试占 11 分钟；62% 的用例每个不到 0.1 秒。抽样实读 95 个测试文件后判断：真实行为回归占绝大多数，可零覆盖损失删除的是注册表顺序/数量契约和重复变体，时间要靠"移出车道"而不是"删测试"。用户裁决：按以上意见执行，旧路由层那 119 个测试文件另行裁决。

## 决定

1. 删除 5 个 gate_meta 注册表顺序/数量契约文件（`test_workbench_registry_contract`、`test_workbench_round1_registry_contract`、`test_workbench_cache_environment`、`test_quality_gate_registry_split_scope_contract`、`test_full_test_debt_registry_contract`，共 1297 个用例），并同步清理 `tools/test_registry_*.py` 里的登记；`tests/gate_meta/test_long_gate_manifest.py` 里冻结的必跑总数改为结构性计数。以后不再新增"某测试在注册表第几位 / 清单恰好 N 条"这类断言。
2. 9 个 `tests/workbench/test_final_*` 验收文件的 `width,theme` 四变体改成单变体，按文件轮换分配 1920/1392 与 light/dark，持久化断言只跑一遍；宽度和主题的视觉覆盖由样式探针负责。
3. 新增 `tools/browser_lane_files.py`：需要真 Chromium 109 / Node 运行时且未登记为 required 的 129 个测试文件构成浏览器验收车道，`tools.full_test_debt_shards.is_perf_nodeid` 把它们视为 `perf`。`FORMAL_FULL_TEST_PYTEST_ARGS` 与 `scripts/sync_debt_ledger.py` 一律加 `-m "not perf"`，正式全量门禁不再执行浏览器验收与性能守卫；`scripts/run_browser_test_lane.py` 单独实跑这条车道，`python -m tools.browser_lane_files --check` 检查清单漂移。
4. `core/services/scheduler/run/optimizer_multi_start_dedup.py` 的原生类证书排除 CPython 记账属性 `__slotnames__`：copy/pickle 第一次碰到某类实例就会往类 `__dict__` 写它，之前会让多起点去重缓存在一次真实排产后于整个进程内静默失效。回归测试见 `tests/algorithm/test_optimizer_multi_start_decision_dedup.py::test_copy_and_pickle_bookkeeping_on_native_classes_keeps_certification`。

5. 旧路由测试按“方案 B”处理（2026-09-18，用户裁决“先按 B”）：旧路由产品代码暂留，只删“只测旧页面本身”的测试。119 个候选文件由三个子代理逐文件判定后执行：DELETE 81、KEEP 22、SPLIT 16；另有 8 个不在候选清单、但只 import 已删文件并只测旧视图模型（`web/viewmodels/scheduler_analysis_*`、`scheduler_resource_dispatch`，活层零引用）的文件级联删除。SPLIT 文件用 AST 裁剪只保留直接打核心服务、工作台 API、迁移或前端源码的用例（213 例→103 例），其中 `test_safe_next_url_hardening`、`test_web_silent_fallback_contract`、`test_plan_vs_actual_review` 三处在函数体内剥离旧路由/旧视图模型断言。删除文件合计 526 例、约 2.3 万行、上次全量实测 9.3 分钟；全套收集数 16574→15856。同步：`tools/test_registry_*.py` 与 gate_meta 元测试去掉对应登记，`scripts/run_daily_quality_gate.py` 的 focused 冒烟不再引用旧批次页视图模型用例，`docs/dev/aps_three_gap_quality_gate.md` 把已删文件挪到附录（roadmap YAML 的历史 `test_commands` 仍引用它们，仅作记录）。判定依据：所测模块从 `core/services/workbench`、`web/routes/workbench`、`web/bootstrap` 是否可达；子代理标注拿不准的 5 个文件主代理逐一复核后维持原判。

## 未做与待裁决

- 重构期特征化家族、防回潮结构锁未动。旧路由测试已按下文第 5 条处理；旧路由层产品代码（约 3.1 万行 web/routes 旧页面与 web/viewmodels）本轮保留休眠，删不删留到下一轮单独裁决（方案 A）。
- `final_*` 逐任务验收未合并，移出正式门禁后只在浏览器车道跑。
- 三个基准基建自测（`test_optimizer_benchmark_loaders` 等）实读后判定守的是基准证据完整性，保留。

## 验证

第 5 条（2026-09-18）：38 个 SPLIT/KEEP 文件 380 passed（含浏览器运行时）；`tests/gate_meta` 1230 passed（4 处元测试样例数据引用已删文件，改指向仍存在的已登记测试后通过）；受影响 11 个目录 `-m "not perf"` 2155 passed 1 skipped；必跑注册表 605 条全在盘；ruff、pyright tools 0 errors、`tools.scan_import_cycles --include-tests` 退出 0（残留环均为既有）；`python -m tools.browser_lane_files --check` 通过；日常门禁结果见会话汇报。9 个 `tests/workbench/*_support|*_server|*_probe` 与 2 个 gate_meta 脚本在本轮前就已无人引用，未动。


- `tests/algorithm` 整目录 2600 passed（修复前整目录 15 红、单文件绿）。
- `tests/gate_meta` 剩余 1236 个用例全绿；`tests/gate_meta/test_long_gate_manifest.py` 与 `test_run_quality_gate.py` 单独复跑 248 passed。
- ruff、`pyright -p pyrightconfig.tools.json`（0 errors）、`tools.scan_import_cycles --include-tests` 通过；全套 collect-only 16574 个用例。
- 日常门禁 `scripts/run_daily_quality_gate.py` 结果见本轮会话汇报；未跑正式全量门禁，浏览器车道本机缺 Chromium 109 未实跑。
