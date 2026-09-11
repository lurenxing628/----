---
doc_type: issue-fix
issue: 2026-09-08-backend-correctness-and-efficiency
status: implemented
fix_date: 2026-09-08
tags: [scheduler, integration, correctness, performance]
---

# 后端正确性与效率集成记录

## 授权与起点

- 用户批准先修业务正确性，再建立可信质量比较并优化候选及 SGS。
- 排除启动锁、安装/离线包、新前端接入、R04 大整数、ATC 数值优化及新的业务评分策略。
- 起点 HEAD 为 `de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`，已有 364 个修改或未跟踪文件。
- 原已暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行保持；本轮没有 commit 或 push。
- 新增必跑测试使用 intent-to-add 纳入 Git 跟踪，不暂存其内容，不能据此宣称已提交。
- 共实际创建 8 个实施 SubAgent、1 个只读复核 SubAgent；主线程负责接线、范围纠正和最终验证。

## 执行状态

- [x] R40：服务和仓储拒绝非有限库存数量；异常读取明确报错，不清洗历史数据。
- [x] A18：真实预期工序、seed 和失败明细参与完成性判断；八个产品调用点贯穿；公开摘要保留安全完成性字段。
- [x] 日历：跨夜班按统计区间相交累计容量；齐套日期保留原始时间下界，由实际资源日历排槽。
- [x] D03：关键链以完整明细内容生成指纹，指纹与计算共享同一批行；覆盖三类方案来源、事务和恢复。
- [x] 候选：严格弱序前置去重、候选族交错、repair 预算预留；没有新增算子策略。
- [x] SGS：单次运行内按完整段快照复用重叠索引，内容变化失效，不缓存整个排程结果。
- [x] 基准工具：正式更新拒绝脏/未知/失败快照；新增真实生产质量矩阵及退化检测。
- [x] 在制占用：仅阻止遗漏在制批次的正式发布，模拟正确避让；不扩大为禁用所有既有重排。服务影响面 453 项通过。
- [x] 主线程全仓测试与冻结后的串行测量。全仓 5937 项通过；项目门禁已实际执行，但仍在第 5 步因既有依赖基线差异阻塞。
- [ ] 最终提交后的 clean 门禁与正式 tracked 基线重建。本轮没有满足这一证据条件。

## 已完成的主线程验证

- 最终全仓回归：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests -q --tb=short -p no:cacheprovider --junitxml=evidence/QualityGate/long_gate/backend-2026-09-08/final-pytest.xml`，**5937 passed in 404.59s**。
- 第一轮全仓为 5935 passed / 2 failed；两项均由原必跑 frozen-bundle 测试遗漏分组引起。仅补齐既有测试的分组登记，没有修改测试内容或安装行为；定点 2 项通过后再全仓重跑得到上述最终结果。
- 算法目录统一回归：1125 passed，使用 Python 3.8，独立 pycache 前缀且禁止写入缓存。
- 基线生命周期、轻基准和 A3 依赖边界：43 passed；拆分复杂度后基线组再次 29 passed。
- A18 公开投影及相邻摘要：17 passed。
- 必跑测试注册及债务注册合同：64 passed。
- 架构适应度检查：21 passed。
- 全仓 Ruff：通过。全仓 Pyright：0 errors、15 个既有动态导出 warnings。
- 独立复核：A18 与 R40 未发现可复现问题；200 组完整方案的四目标评分与原实现完全一致。
- 各专项数量包含重叠用例，不累加成去重总测试数。

## 冻结后的质量和性能

- 质量矩阵按同 seed、10 秒预算、60 候选上限、单 worker 串行执行两次：4 个目标 x tiny/48 工序带班次资源池场景，共 8 个 case，每轮全部通过。
- 每轮 254 次真实 SGS 解码，其中 126 次来自正式生产 repair；不存在测试侧自写 repair 替代生产代码。
- 两轮保存快照比较无质量/耗时退化。比较阈值为 runtime ratio 3、绝对余量 250ms，用于回归拦截，不代表宣称 3 倍以内的退化有业务合理性。
- 证据：`evidence/QualityGate/long_gate/optimizer_quality_matrix/frozen-run-a.json`、`frozen-run-b.json`、`frozen-comparison.json`，均明确为 dirty/unbound。
- SGS 按开关交替、每组 5 次串行实测；288 工序加 36 条 seed 的完整结果逐字段相等，相关源码在测量前后哈希相同。
- 自动派工中位数 2.418640s -> 2.212872s，下降 8.51%；固定资源 0.264760s -> 0.245173s，下降 7.40%。这是本机固定样本，不外推到 Win7 或其他规模。
- 证据：`.codestable/refactors/2026-09-08-sgs-probe-reuse/paired.json`。没有同时运行其他本轮性能任务。

## 项目门禁阻塞

实际命令：`PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-backend-20260908-pycache .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --no-resume --no-long-gate-cache`。

第 1-4 步通过；第 5/19 步 `scan_import_cycles --fail-on-new-cycle` 报告：

- `core.services.process` 父包初始化文件环相对旧基线扩展了 unit_excel helper 成员。
- 既有启动配置增加了 `web.bootstrap.startup_config -> config` 目录圈内边。

上述启动配置及相关 unit_excel 文件逐一与本轮入场内容哈希核对，均未变化。本轮没有放宽依赖基线，没有修改启动链。门禁结果为 failed，不是 passed_but_unbound；全仓 pytest 通过不能替代其剩余步骤。

失败凭证保存在 `evidence/QualityGate/quality_gate_manifest.json` 及关联 receipts/logs；执行前原凭证已备份到 `evidence/QualityGate/long_gate/backend-2026-09-08/previous-manifest-1788855104953.json`。

## 集成时额外纠正

- 不再为了旧测试保留无效的全局日历对齐调用；增加全局长期停工但个人覆盖可工作的真实反例。
- A18 completion 字段贯穿公开 metrics/attempts，不公开批次样本或数值哨兵。
- A3 测试保护真正的算法依赖边界，不固定全仓模块总数。
- 既有 Excel helper 移动导致静默回退登记错位；仅迁移路径和 ID。处理内容指纹及上下文哈希相同，状态仍为 open，没有新增忽略项。
- 旧基准计数改为配置覆盖、实际解码和去重记账，不强制重复解码。
- 为既有必跑 `test_frozen_bundle_contract.py` 补齐分组，消除覆盖校验与缓存凭证验证失败；没有改该测试原有已暂存内容。

## 必须保留的限制

- 当前为 dirty worktree，不是最终 HEAD 的 clean-worktree proof；正式 tracked 基线尚未重建。
- 历史 NaN 若已被 SQLite 转为 NULL，无法从现有值恢复来源，保留原空值合同。
- 不完整方案的同失败数目标比较采用保守持平，不伪造实际拖期或完工日期。
- 关键链命中仍需读取完整明细并计算指纹，消除的是关键链重算，不是明细读取成本。
- 在制工序的跨版本报工连续性属于现有身份合同限制；本轮不伪造事件、不弱化 adopted-only guard。
- 没有操作真实业务数据库；没有 Win7 实机测量。
