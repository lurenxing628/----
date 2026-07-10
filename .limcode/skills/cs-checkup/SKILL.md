---
name: cs-checkup
description: APS 项目专属地基体检——重建机器基线、复查 14 个结构分区、增量考古决定、对比历史健康度。触发：用户说“做个体检”“cs-checkup”“刷新全景图”“项目现在啥状况”“重新验基线”“复查地基”。仅用于本 APS 项目。
---

# cs-checkup（APS 项目专属体检）

## 目标

把 APS 的“代码投影、历史决定、健康判断”分开维护，避免一个过期 watermark 同时冒充三种真相：

- **代码投影**：codemap、callgraph、循环依赖、dead-code 基线；对某个已提交 commit 负责。
- **历史决定**：只对已经逐提交考古到的 decision watermark 负责。
- **健康判断**：每轮重算，并和上一轮历史样本对比。

项目机器基线入口：

- `.codestable/checkup/README.md`
- `.codestable/checkup/baseline.json`
- `.codestable/checkup/latest/`

本技能只用于当前 APS 仓库，不要搬去别的项目照跑固定分区。

## 启动必读

开始任何判断或动作前依次读取：

1. `.codestable/attention.md`
2. `.codestable/checkup/README.md`
3. `.codestable/checkup/baseline.json`
4. `.codestable/architecture/ARCHITECTURE.md`
5. `.codestable/audits/` 下最近一次 `*-checkup*/index.md`（若存在）

缺少 `baseline.json` 时先走“基线模式”，不要回退到已经失效的 `.codestable/audits/2026-06-01-foundation-maturity/` 路径。

## 两条水位线不可混

`baseline.json` 中有两条独立水位线：

1. `code_baseline.commit`：机器扫描对应的 clean commit。
2. `history_baseline.decision_watermark_commit`：决定考古真正覆盖到的 commit。

守护规则：

- 重跑代码扫描只能推进代码基线。
- 只有逐个完成待审提交的分量分级和必要 diff 考古，才能推进决定水位线。
- 不准为了“看起来是最新”把 decision watermark 直接改成 HEAD。

## 模式

- `/cs-checkup`：完整体检，执行 Phase 0-6。
- `/cs-checkup 快检`：只做 Phase 0，报告基线后有多少提交、哪些分区变化、机器门禁是否可直接复跑。
- `/cs-checkup 基线`：重验 clean HEAD 的机器基线；不自动补 332 个历史提交的决定考古。
- `/cs-checkup 结构`：执行 Phase 1-3，刷新代码投影并复查变更分区。
- `/cs-checkup 决定`：执行 Phase 4，增量补决定考古。
- `/cs-checkup 全量`：从指定历史起点重做结构与决定；必须先让用户确认成本和起点。

## Phase 0：钉范围与工作树边界

1. 运行 `git status --short`，记录未提交改动。
2. 读取 `code_baseline.commit` 与 `decision_watermark_commit`。
3. 计算：
   - `git rev-list --count {code_baseline}..HEAD`
   - `git diff --name-only {code_baseline}..HEAD`
   - `git rev-list --count {decision_watermark}..HEAD`
4. 明确本轮是：
   - 扫已提交 HEAD；或
   - 连未提交改动一起做在途快照。

正式基线默认只认 clean commit。工作树脏时，用 `git archive HEAD` 解到临时目录扫描；不能把在途改动混进基线后声称 clean-worktree proof。

## Phase 1：重跑机器投影

完整命令和判定口径见同目录 `reference.md`。

1. codemap：
   - `.codestable/checkup/scripts/codemap_extract.py`
   - `.codestable/checkup/scripts/dynamic_refs.py`
2. callgraph：
   - `.codestable/checkup/scripts/callgraph_extract.py`
3. import cycles：
   - `python3 -m tools.scan_import_cycles --json --fail-on-new-cycle`
4. dead-code quick：
   - `python3 tools/scan_dead_code_islands.py --mode quick`

先把输出写到临时目录，比较后再更新 `.codestable/checkup/latest/`。

最高优先级红线：

- codemap `layering.json` 非空：标红并定位，不自动改代码。
- import cycle 出现基线外新增硬环：标红。
- 脚本 parse error：基线失败，不能继续包装成“已体检”。
- dead-code 出现新增项：先用调用、运行时或测试证据核验；不准直接删，也不准无脑刷新。

## Phase 2：核对机器结果可信边界

- `orphan_candidates` / `orphan_refined` 只是候选，不是死代码裁定。
- 模块 import 图不等于函数调用图；两者要交叉看。
- `dup_bodies` 可能是协议样板，不等于应该合并。
- callgraph 的 ambiguous 边和动态未消解点不能当精确调用事实。
- dead-code quick 对 dataclass 回调、属性读取、鸭子接口和重导出会误报。

对任何准备进入体检结论的候选，都要补真实 `file:line` 证据。

## Phase 3：按 14 分区深钻

分区定义见 `reference.md`。只深钻代码基线之后发生变化的分区；没变的分区可以引用上一轮结论，但必须注明上一轮 commit。

可以使用用户允许的 **LimCode 原生 SubAgent / Sub2API** 做只读切片，遵循：

- `.limcode/skills/_shared/subagent-compat.md`
- 每个子代理只领一个清楚分区或风险面。
- 输出必须带文件路径、行号和“证据不足”。
- 不自动启动 Claude Code bridge；用户另行明确要求时再单独处理。
- 子代理失败不能包装成已完成，主代理决定重派或降级执行。

## Phase 4：增量决定考古

从 `history_baseline.decision_watermark_commit` 到目标 commit：

1. 给每个提交计算分量：churn、文件数、是否触及核心目录。
2. message 详细且改动小的可直读。
3. 触及核心目录、churn ≥ 150、或 message 简单但 churn ≥ 80 的提交必须看 diff。
4. 记录新决定、推翻关系和长期约束。
5. 全部待审提交处理完后，才推进 decision watermark。

若只做了部分，记录已覆盖区间和剩余数量，状态保持 `pending_incremental_archaeology`。

## Phase 5：重算健康度与趋势

- 对 14 分区重新给 1-5 分，并给证据。
- 与 `.codestable/checkup/legacy/2026-06-01-foundation-maturity/module_findings/` 的旧评分对比。
- 旧样本是历史证据，不是当前真相；路径、规模和断言要回当前代码核验。
- 区分在途 roadmap 与长期搁置，不把正在实施的迁移误判成应立即清理的债。

## Phase 6：归档与可视化

1. 按共享审计格式写 `.codestable/audits/{YYYY-MM-DD}-checkup/index.md`；每条未关闭发现单独写 `finding-NN.md`。
2. 机器扫描通过并已落正式快照时，更新 `baseline.json` 的代码基线、统计与哈希。
3. 决定考古完整时才更新 decision watermark。
4. 全景 HTML 当前是 gitignored 本机产物；生成器和输入未正式入库时，只能标 `local-only`，不能声称新克隆可重生。

## 守护规则

- **代码基线与决定水位线分离。**
- **脏工作树不冒充 clean HEAD。**
- **分层违规和新增硬环是最高优先级。**
- **dead-code 先验证，后删除或受控刷新。**
- **历史样本只做对比，不冒充现状。**
- **体检只出发现和文档，不顺手改业务代码。**
- **不自动调用 Claude Code。**

## 退出条件

- [ ] 已说明扫描的是 clean commit 还是在途工作树
- [ ] codemap / callgraph / import cycles / dead-code 均有实际结果
- [ ] 分层违规、解析错误、新增硬环和 dead-code 新项均明确报告
- [ ] 变更分区有证据化复查，未覆盖范围已写明
- [ ] 决定 watermark 只在完整考古后推进
- [ ] 体检报告已写入 `.codestable/audits/`
- [ ] `baseline.json` 与实际产物一致
- [ ] 可视化不可重放时明确标记，没有包装成完成
