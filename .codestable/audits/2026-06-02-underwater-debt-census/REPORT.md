# APS 排产系统 · 全项目水下语义债普查报告

> 细颗粒度完整版 · 供后续治理与决策使用

---

## 报告元信息

| 项 | 值 |
|---|---|
| 报告主题 | 全项目"水下语义债"(失忆债)普查 |
| 普查方法 | 两遍法:Pass-1 分区 agent 自由取证 + 对抗验证;Pass-2 函数级调用图机械列嫌疑 + 人核验;**增量普查:对 b08162cd 提交版本(`git show`)做同颗粒度 delta 普查(见 §13)**;**第三方复核:drift-analyzer 2.51.1 独立结构腐蚀扫描 + B−A 透镜(见 §14)** |
| 普查覆盖 | 全 12 分区 / 657 模块 / 12.6 万行 / 5874 函数级调用图 + b08162cd 增量 54 生产文件 |
| **证据基准 commit** | **`65870e47`**(Implement resource dispatch execution lane)——基准普查取证 HEAD |
| **现状对账 commit** | **`b08162cd`**(完成报表工作台回跳验收)——增量普查已覆盖,全文对齐至此 |
| 报告日期 | 2026-06-02(增量普查同日追加) |
| 取证性质 | 只读普查,未改任何生产代码;增量普查读 `git show b08162cd:` 提交版本(避工作区 in-flight 污染) |

### ⚠️ 时间基准说明(使用本报告前必读)

**本报告已升级为"现状版":基准普查取证在 HEAD=`65870e47`,随后对其后唯一提交 `b08162cd`("完成报表工作台回跳验收",工作台收口)做了同颗粒度的增量普查(见 §13),使全文对齐到当前 HEAD `b08162cd` 的真实状态。**

`b08162cd` 大改了多个核心文件:`execution_review.py`(149 行)、`report_context_filters.py`(+293)、`reports_page_support.py`(+456 新建)、`navigation_context.py`(+138)、`reports.py`(-465 拆分)等。本报告中所有 `file:line` 已逐条回代码复核,标注三态:
- ✅ **证据仍准** — 行号与定性在当前代码上仍成立
- ⚠️ **行号已变/在途** — 债仍在但位置漂移(给出新行号),或属本分支 roadmap 在途
- 🔧 **疑似已修复** — 该债在 `b08162cd` 后已被消除(给出依据)

**两条核心条目的当前状态(已用版本史考古复核)**:

1. ⚠️ **【更正】所谓"P1 写死常量出血"是一条幻觉证据,版本史无此 P1。** 基准普查曾报告 execution_review 用写死常量 `ADOPTED_PLAN_RESOLUTION`(reports_page_support.py:36)假冒方案身份。**增量普查的版本史考古证明此条不成立**:(a) `git cat-file` 显示 `reports_page_support.py` 在基准 `65870e47` **根本不存在**(是 `b08162cd` 拆分 reports.py 时才新建);(b) `git log --all -S "ADOPTED_PLAN_RESOLUTION"` 全 ref pickaxe **只命中 stash `725cca79`**,且仅出现在审计报告自己的散文里,无任何 `.py` 含它;(c) execution_review 自基线起即走真解析 `host._resolve_plan(v, ROLE_ADOPTED, None).to_dict()`,`ValueError` 时 `raise ValidationError`(不静默兜底)。**结论:当初是把一次工作区 in-flight 中间态误当成基准事实——这正是"活工作区污染"陷阱。本报告诚实更正此条(宁可暴露错误也不自欺,正是本项目灵魂线),原"唯一已知 P1 出血"应读作"普查快照污染,全项目 P1 真实计数 = 0 且从未有过此例"。**

2. ✅ **承重护栏注释仍缺失(这条是铁证,不受上条影响)**:`execution_review.py` 当前 :112/:123/:153/:166-167 仍硬钉 `ROLE_ADOPTED`/`scenario_id=None`,对 4 个承载护栏的文件逐一 grep `#` 注释 + `故意/刻意/不对称/forbidden`——**零解释性注释**(命中的全是 UI 文案、错误消息、变量名 `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS`)。`b08162cd` 编辑了 :116-118/:125-127 相邻行(插入 resource 参数)却没补护栏注释,反而 :70 新增一行功能性注释 `# 计划和现场实际复盘`(说"做什么"而非"为何故意")——**护栏意图的失忆风险不降反升**,是失忆债的活样本。

---

## 执行摘要

**一句话**:全项目 61 条水下语义债,**P1(写死假冒计算值)零活例**(唯一出血已治),债的形状是"整理到一半的房间"(P3 半截迁移 + P6 死代码占 65%),不是"垃圾场"。真正的存量高危不是债多,而是 **8 处"看着像债、实为救命护栏"的承重不对称**——它们零本地注释,是未来 LLM 以"统一"名义最易误删的引爆点。项目离屎山很远,且是结构性远(0 分层违规 + 全可测绘 = 爆炸半径可预测)。

### 三个核心担忧的答复

| 你的担忧 | 普查结论 | 证据 |
|---|---|---|
| "会不会立马成屎山?" | **不会,结构性不会** | 0 分层违规 + 每条债可 grep 到 file:line + git 考古到引入提交 = 爆炸半径可预测(屎山的反面) |
| "agent 注意力偏差漏一大片?" | **没有兑现** | 调用图机械扫 5874 函数,B−A 的 25 个"图标 agent 没碰"文件逐一核实几乎全是图假阳性,无 agent 漏掉的新出血("狗没有叫"式证据) |
| "LLM 自做的微决定是最大隐患?" | **判断对,但隐患是 8 处"别动我"** | 4 处承重护栏都守同一道墙(execution_review 只复盘正式采用方案),零本地注释,理由散在远处 |

### 病理分布(基准 12 分区 61 条 + b08162cd 增量 14 条 = 75 条)

| 病理 | 基准 | +增量 | 合计 | 性质 | 治理基调 |
|---|---:|---:|---:|---|---|
| **P1** 写死假冒计算值 | **0** | 0(+1 呈现失真气味) | **0** | **真实计数 0,且原报告所谓 P1 实证经版本史考古证伪(见封面更正)** | — |
| **P2** 承重不对称无注释 | 4 | +2(N3导航护栏/N5护栏削弱) | 6 | 全 load_bearing | **补"别动我"注释(最高杠杆)** |
| **P3** 半截迁移残渣 | 17 | +3(N4双路径/N9标签压扁/N14清单三抄) | 20 | 新路径胜出、旧路径未清 | 删空壳 / 收口到已存在统一点 |
| **P4** 静默兜底死角 | 6 | +0(3 处反被修复) | 6 | 多为不可达防御 | 改 raise / 补可观测 |
| **P5** 第 N 套私有实现 | 11 | +3(N1护栏字段3抄/N6数值/N10关键链副本) | 14 | 部分已语义漂移 | 收口到已存在统一点 |
| **P6** 死代码 / 死面包屑 | 23 | +5(N7plan_id/N8/N11/N12/N13) | 28 | 纯死代码 / 死字段 / 死参数 | grep 实证后直删 |
| **N2 呈现失真** | — | +1(关键链子集冒充整版) | 1 | P1 气味,但非写死假冒 | 补 scope=filtered 标记 |
| **合计** | **61** | **+14** | **75** | | |

> 注:**§14 第三方 drift 复核为独立交叉验证,不并入上表 75 条计数**——它确认审计无漏出血,并在审计盲区补出 17 组 MDS 微重复(其中 3 组 14.D1–D3 值得记进真债清理册,详见 §14)。
>
> 注:基准对抗验证确认 8 处 load_bearing 承重护栏(Pass-1 的 6 + Pass-2 新增 2);b08162cd 增量新增 2 处承重相关(N1 护栏字段散 3 抄、N3 导航护栏靠字面量+零注释),并**新增 1 道正向反自欺护栏**(is_superseded 标签,§13)。**净效果:b08162cd 减债 > 增债**——堵掉 web 私有数值解析、3 处 P4 静默兜底、硬编码 URL,代价是 2 笔承重语义债 + 一批低危残渣。

### 各分区健康速览(12/12)

| # | 分区 | 健康 | 主病 |
|---|---|---|---|
| 1 | 排产主链 scheduler/run/ | 偏干净 | P6 拆分残渣 |
| 2 | 资源派工 resource_dispatch | 轻残渣 | P5 派工 scope 双轨(team 轴承重) |
| 3 | 甘特调整闭环 gantt | 偏干净 | P6 死方法 + 在途重复 |
| 4 | 执行事实与诊断 exec-diag | 地基扎实 | P2 写侧 adopted 护栏无注释 |
| 5 | 方案身份解析核心 plan-identity | 非重灾 | P5 私实现无 parity 测试 |
| 6 | 配置/汇总/图 config-summary-graph | 非重灾 | P3 SP05 半截包拆分尾巴 |
| 7 | 领域模型 core-models | 健康 | **P3 双配置栈锁步同步(潜伏分叉)** |
| 8 | 排产算法 core-algorithms | 健康偏好 | P3/P6 三次重构"新胜旧未清"尾巴 |
| 9 | 基础设施与共享脊梁 infra-shared | 基本干净 | P5 boolean_normalize 双实现(分层承重) |
| 10 | 业务域服务与报表 svc-domain | 基本干净 | P2 execution_review 护栏无注释 |
| 11 | 数据仓储 data-repos | 结构干净 | P6 死读方法群(迁移残渣) |
| 12 | Web 层 web-all | 非重灾 | P2 路由层 adopted 护栏 + P6 plan_id 死面包屑 |
| **13** | **增量 · b08162cd 工作台收口** | **净减债** | **N1 护栏字段散 3 抄(承重)+ N2 关键链子集冒充整版 + plan_id 死面包屑坐实** |
| **14** | **第三方 drift 复核(三信源)** | **核心结论站得住** | **drift 未证伪审计;补 17 组盲区微重复,3 组值得记(14.D1 降级语义逐字两份最该收)** |

---

## 报告导读

- **第一部分 · 分区详查**(§1–§12):每个分区逐条债,含病理/位置/引用链/为何算债/爆炸半径/处置/当前复核状态。颗粒度最细,按 file:line 可直接行动。
- **§13 · 增量债(b08162cd 工作台收口)**:对基准后唯一提交的同颗粒度 delta 普查——已修复的旧债(改 🔧)、新引入的债(N1–N14)、净效果裁定、含一条对原报告幻觉 P1 的版本史更正。
- **§14 · 第三方 drift 复核(三信源对账)**:在两遍法之外引入独立的 drift-analyzer 做结构腐蚀全扫,用 B−A 透镜回答"第三方能否指出审计漏掉的出血"。裁定:不能(核心结论站得住),但补出 17 组审计盲区微重复 + drift 工具口径校准(AVS≠分层违规)。
- **第二部分 · 横切专题**:
  - §90 **承重护栏清单**(防屎山核心资产)——基准 8 处 + 增量 2 处"别动我",含该补的注释逐字文案。
  - §91 **真债清理册**(按收口难度六档)——53 条可安全收的债,标收口到哪个已存在统一点。
  - §92 **方法论与调用图交叉检验**——两遍法设计、A∩B/B−A 检验、图核验洞见、局限与置信度。
- **附录**:产物清单、病理定义、未决裁断项、置信度标注。

> ⚠️ 产物安全提示:本报告生成期间遭遇并发进程(另一 Claude 工作流共享同一 git 工作区)清理 untracked 文件,导致中间产物两次丢失并从 agent 日志恢复。建议本报告一经生成立即 `git add` 转为 tracked,避免再被 `git clean`/`git checkout` 波及。调用图产物(`.codestable/checkup/latest/callgraph/`)在该事件中丢失,如需可由 `callgraph_extract.py` 复跑重建。

---

## 分区 01 · scheduler-run（排产主链 `core/services/scheduler/run/`）

**分区健康一句话**：这是经「静默回退治理」(e2e4bf7c) 与 `p1-scheduler-debt-cleanup` 整条 roadmap（PR-1~PR-8 全 done）双重打磨过的成熟主链——输入收集层全程 fail-fast、冻结窗口/落库护栏在每个数据缺口处 `raise` 或经 `DegradationCollector` 显式上报、`strict_mode` 一律抛错，灵魂原则（坏数据不静默兜底）落实得很彻底，**未发现活的 P1/P3/P4**；残渣集中在 3 条 P6 死面包屑 + 1 条边界 P5，无重灾区。

> 复核方法：本分区 4 条 finding 已逐条回到**当前代码**（含本批 git modified/added 文件）用 grep + Read 复核。结论：**4 条全部「证据仍准」**，cited file:line 与当前代码逐字对齐；仅 F4 的"全仓 dup 计数"因 6/01 后新增「资源派工执行车道」(commit 65870e47) 由 6 处涨到 7 处，但**本分区内的 2 处定位与全部承重论证不受影响**。

---

### F1 · `count_actionable_schedule_rows` / `has_actionable_schedule_rows` 是拆分重构后遗留的死函数，靠两层 re-export + 拓扑测试续命

- **病理标签**：P6（死代码 / 死面包屑）｜**严重度**：medium｜**load_bearing**：false（纯死代码，删除不移除任何不变量）
- **复核结论**：✅ **证据仍准**。`count_actionable_schedule_rows` 现仍在 `schedule_payload_contract.py:90`、`has_actionable_schedule_rows` 在 `:94`（内部调 `:95`），与原证据逐字一致。

**位置**
- 定义：`core/services/scheduler/run/schedule_payload_contract.py:90`（`count_actionable_schedule_rows`）、`:94`（`has_actionable_schedule_rows`，函数体 `:95` 调前者）
- 唯一私有依赖：`_iter_actionable_results`（`schedule_payload_contract.py:67`，静默跳过无 `op_id`/坏时间的结果行，只计数不报错）

**引用链（当前实测）**
- `run/schedule_persistence.py:16-17` 把两符号 import 进来（位于 `:12-18` 的 `from .schedule_payload_contract import (...)` 块，与 `build_validated_schedule_payload` 并列）。
- `scheduler/schedule_persistence.py:3` 二次 import 并 `:5` 列入 `__all__ = ["count_actionable_schedule_rows", "has_actionable_schedule_rows", "persist_schedule"]`。
- `schedule_payload_contract.py:414-415` 自身 `__all__` 也导出二者。
- **全仓 grep 实证**：除 `has()` 内部调用 `count()`（`:95`）外，`core/`、`web/`、`data/` 无任何 `has_actionable_schedule_rows(` / `count_actionable_schedule_rows(` 调用点；唯一外部引用是 `tests/test_sp05_path_topology_contract.py:54-55`，断言二者作为 `core.services.scheduler.schedule_persistence` 的公开符号存在（该断言块当前在 `:53-58`，含 `persist_schedule`）。
- **git 考古（pass1 已验，本次不复跑）**：`git -S` 证明历史生产调用点 `has_actionable_schedule_rows_fn=...` 在 `78879ec1`（schedule_service 600 行拆为输入收集 + 编排 + 薄门面）时被删除，函数本体留下未清。

**为何算债**
本应判断"是否有可落库排程行"的计数/布尔函数，在 schedule_service 拆分后，生产侧已改走 `build_validated_schedule_payload` → `_validate_persist_inputs`（`run/schedule_persistence.py:201`：`if not validated_schedule_payload.schedule_rows: raise_no_actionable_schedule_error(...)`）做严格落库闸门——这套老 count/has 函数因此**失去所有生产消费方**。两层 re-export 链 + 两处 `__all__` + 拓扑契约测试共同营造"仍在用"的假象，`_iter_actionable_results` 的静默跳过逻辑也随之沦为零生产价值的孤儿。

**爆炸半径**
纯死代码。删除清单：`count_actionable_schedule_rows` + `has_actionable_schedule_rows` + `_iter_actionable_results` + `run/schedule_persistence.py:16-17` 与 `scheduler/schedule_persistence.py:3,5` 两处 re-export/`__all__` + `payload_contract.py:414-415` 两条 `__all__`，并**必须同步删** `tests/test_sp05_path_topology_contract.py:54-55` 的断言（否则该拓扑契约测试会红——这正是它当前在做的事）。无生产路径受影响，误判风险极低（已 grep 实证 + git 考古双确认）。

**处置建议 + 收口点**
直接收（medium）。收口到生产唯一在用的落库闸门 `run/schedule_persistence.py:201` 的 `_validate_persist_inputs`——"有无可落库行"的判断已由它独占，老 count/has 无须保留为公开 seam。删除时一并把拓扑契约测试 `test_sp05_path_topology_contract.py` 中 `schedule_persistence` 的导出清单收缩为只剩 `persist_schedule`。

---

### F2 · `schedule_graph_dispatch_context.build_first_wave_ready_nodes` 是 test-only re-export 包装器（兄弟包装器是活的，唯独它没有生产调用方）

- **病理标签**：P6（冗余转发层 / 死面包屑）｜**严重度**：low｜**load_bearing**：false
- **对抗验证结论**：`_adv_verdict = real_debt`，`_adv_refuted = true`（怀疑者已裁断为真债，可删，但**带前置条件**）
- **复核结论**：✅ **证据仍准**。包装器现仍在 `schedule_graph_dispatch_context.py:461-475`，函数体 `:468` 懒 import 真 impl；真 impl 在 `resource_matching_context.py:48`、本地调用方 `:115`、`__all__` home `:131-134`，全部与原证据逐字对齐。

**位置**
- 包装器：`core/services/scheduler/run/schedule_graph_dispatch_context.py:461-475`（函数体 `:468` `from .schedule_graph_resource_matching_context import build_first_wave_ready_nodes as _impl`，`:470-475` 纯 `return _impl(...)` 转发）
- 真实现：`core/services/scheduler/run/schedule_graph_resource_matching_context.py:48`

**引用链（当前实测）**
- 真 impl 的**唯一生产调用方**在 `resource_matching_context.py:115`（裸名 `build_first_wave_ready_nodes(...)`，绑定到本模块 `:48` 的 local def，**完全不经过** dispatch_context 包装器）。
- 生产消费 dispatch_context 的只有兄弟包装器：`schedule_graph_report.py:19` `import build_graph_resource_matching_projection as _build_graph_resource_matching_projection`，`:180` 调用（确活跃）。
- **全仓 grep `build_first_wave_ready_nodes`**：除上述 2 个模块 + 包装器自身外，唯一外部导入方是 `tests/scheduler_graph/test_graph_dispatch_context.py:11`（import 块 `:10-14`，`:55`/`:66` 调用）。无任何 `core/web/data` 生产代码从 dispatch_context 导入它。
- `dispatch_context` 全文**无 `__all__`**（已 grep 确认），包装器不属于任何已声明门面契约；`run/__init__.py` 为空（1 行），无包级转出。

**为何算债**
同文件两个并排的 re-export 包装器（`build_first_wave_ready_nodes` 与 `build_graph_resource_matching_projection`）给人"对称公开 seam"的印象，但**只有后者有生产调用方**（`report.py:180`），前者纯粹被测试导入，造成"在用"假象。真逻辑在 `resource_matching_context`，该包装器是冗余转发层；其懒 import（`:468`）仅为规避 `matching→dispatch` 的模块级环，删它只会移除 `dispatch→matching` 这条边，改善而非破坏 import 图。

**爆炸半径**
极小。删除需同步改 `tests/scheduler_graph/test_graph_dispatch_context.py:11` 的 import（改为直接从 `schedule_graph_resource_matching_context` 导入，`:55`/`:66` 调用不变）。生产路径（`resource_matching_context:115` 本地调用 + `report.py:180` 走兄弟包装器）不受影响。`regression_scheduler_candidate_py38_contract.py` 仅做 banned-import/py38 语法检查、未 pin 公开导出面，删包装器不破契约测试。

**处置建议 + 收口点**
按对抗裁决的**前置条件顺序**收（low）：先把 `tests/scheduler_graph/test_graph_dispatch_context.py:11` 的 import 从 `schedule_graph_dispatch_context` 改为从 `schedule_graph_resource_matching_context`（其真实 `__all__` home，`:131-134`）导入 `build_first_wave_ready_nodes`，再删 `dispatch_context.py:461-475` 转发包装器；删后跑 `scheduler_graph` 测试套件 + `regression_scheduler_candidate_py38_contract` 自证。收口点 = `resource_matching_context.py` 的 `__all__`（`:131-134`，本就是真 home）。

> ⚠️ **承重旁注（不可顺手删）**：兄弟包装器 `build_graph_resource_matching_projection`（`dispatch_context.py:478`）是**真承重**——`report.py:180` 经 dispatch_context 消费它，删除会断生产路径。本条只动 `build_first_wave_ready_nodes` 一个，两包装器互不耦合（`report.py` 从不 import 前者）。

---

### F3 · 候选"失败"态全套机制（`CANDIDATE_STATUS_FAILED` / `_failed_plan` / `failed_candidate_count` / `baseline_missing_or_failed`）在生产中不可达，一路铺到死 UI 分支

- **病理标签**：P6（为不可达状态铺设的下游死管道）｜**严重度**：low｜**load_bearing**：false（**但内含一处承重窄 except，见下方醒目护栏区**）
- **needs_adversarial**：true（待怀疑者裁断：是"为持久化 schema 枚举保留的防御性契约面"还是"不可达状态的死脚手架"）
- **复核结论**：✅ **证据仍准**。唯一 catch 点仍在 `schedule_candidate_runner.py:216`，`_failed_plan` 在 `:470`（产出 `status=CANDIDATE_STATUS_FAILED` `:476`），`failed_count`/`baseline_missing_or_failed` 计算在 `:241`/`:247`，下游 viewmodel 分支全部命中——逐条对齐。

**位置**
- 失败态触发链：`CandidateTrialFailure` 类（`schedule_candidate_runner.py:28`，`class CandidateTrialFailure(RuntimeError)`）→ **唯一 catch 点** `:216`（`except CandidateTrialFailure as exc: return _failed_plan(...)`）→ `_failed_plan`（`:470-483`，产出 `status=CANDIDATE_STATUS_FAILED`，常量定义 `:24`）

**引用链（当前实测）**
- **生产侧零 raise**：`grep raise CandidateTrialFailure` 全仓只命中 `tests/regression_scheduler_candidate_runner_contract.py:470,576`，生产代码无任何 `raise CandidateTrialFailure`。
- **不可达推理（当前代码逐行验证）**：
  - baseline spec 在 `schedule_candidate_specs.py:61-63` 恒为 `sequence=0` / `candidate_key="baseline"` / `kind=CANDIDATE_KIND_BASELINE` 的首跑；
  - `runner.py:172` 的时间预算闸 `if now() >= deadline:` 在**首个 spec** 时（`deadline = started + budget`，`budget > 0`）不成立，故 baseline **永不被 skip**；
  - 加上 `CANDIDATE_STATUS_FAILED` 不可达 → `_baseline_missing_or_failed`（`:263-267`，baseline 必 `COMPLETED` 时返 False）生产**恒 False**、`failed_count`（`:241` `_count_candidates(..., CANDIDATE_STATUS_FAILED)`）生产**恒 0**。
- **死下游管道**：`failed_count`/`baseline_missing_or_failed` 流入 `schedule_candidate_summary.py:135,140`（公开摘要字段）→ 多个 viewmodel 的展示分支：
  - `web/viewmodels/dashboard_workbench.py:207`：`if comparison.get("baseline_missing_or_failed"):` → 追加"原算法代表方案没有完整结果"（生产永不触发）
  - `web/viewmodels/scheduler_analysis_candidate_helpers.py:324`（`failed_count = int(comparison.get("failed_candidate_count") or 0)`）、`:329`（`if bool(comparison.get("baseline_missing_or_failed")):`）→ 两条 `_warning_message` 分支（生产永不触发）
  - `web/viewmodels/scheduler_analysis_candidates.py:194,206,230,242,260,265` 透传同名字段
- **附带死枚举**：`ScheduleCandidate.status` 持久化枚举里的 `'not_run'`（`core/infrastructure/migrations/v10.py:14` 的 `CHECK(status IN ('completed','failed','skipped','not_run'))`）在整个 `run/` 零产出点（生产只产 completed/skipped，failed 仅测试可造，not_run 无人写）。

**为何算债**
这是一组"为不可达状态铺设的下游管道"：生产中候选要么 `completed`、要么 `skipped`（时间预算，可达）、要么真异常直接 propagate（`b81f8b3f` 收窄 except 后的正确行为）；`FAILED` 这一态**只有测试能造**。`failed_candidate_count` / `baseline_missing_or_failed` 一路传到 viewmodel 的 `if` 分支，这些 UI 分支生产永不触发，构成跨 service→viewmodel→template 的死脚手架。

**爆炸半径**
中等。若清理下游计数 + UI 分支，将牵动**已落库的 `ScheduleCandidate.status` 枚举契约**（`v10.py:14` 的 `completed/failed/skipped/not_run`）+ 两个 viewmodel（`dashboard_workbench`、`scheduler_analysis_candidate_helpers`）+ 候选公开摘要字段（`schedule_candidate_summary.py`），并涉及一批 contract 测试（`regression_scheduler_candidate_runner_contract` / `_summary_contract` / `_display_contract` / `_analysis_links_contract` / `dashboard_workbench_contract` 均断言这些字段）。

**处置建议 + 收口点**
**标 needs_adversarial，倾向低优先登记、暂不动**。这套字段是否该保留取决于一个判断：`failed`/`not_run` 是不是"为持久化 schema 防御性保留的契约面"——若 DB 已落 `v10` migration 的 4 值 CHECK 约束，贸然删 service 侧产出会让 schema 与代码失配。建议处置：(1) 维持枚举与字段不动；(2) 在 `_failed_plan`（`:470`）与 `_baseline_missing_or_failed`（`:263`）上各补一行"我是故意的"注释，标注"生产不可达、为持久化 schema 枚举 + 测试可造态保留"，把"看起来在用其实是契约面"的真相显式化；(3) 待 schema 决策明确后再统一收口到 `schedule_candidate_summary` 的公开摘要契约。

> 🛑🛑 **承重护栏（绝对不可动）—— 本条内嵌的真护栏：`schedule_candidate_runner.py:216` 的窄 except**
>
> 相邻的 `except CandidateTrialFailure as exc:`（`:216`）是 `b81f8b3f`「移除未知异常转 failed candidate 的宽泛捕获，只保留明确的 `CandidateTrialFailure`」**刻意收窄**的成果，是防止已被治理掉的"静默吞错"复活的承重护栏。**绝不能以"统一/简化"名义改回 `except Exception`**——那等于重新引入违背灵魂暗线（坏数据不静默兜底）的高危回归。测试 `regression_scheduler_candidate_runner_contract.py:473` 注释已明确："只有显式 `CandidateTrialFailure` 是候选级失败；`ValidationError`/`RuntimeError`/`TypeError` 必须继续向上抛。"
>
> **该补的"我是故意的"注释文案（建议加在 `:216` 上方）**：
> ```python
> # [承重·勿改宽] 仅捕获显式 CandidateTrialFailure，是 b81f8b3f 对"未知异常吞成 failed candidate"
> # 静默兜底的定点治理。ValidationError/RuntimeError/TypeError 必须继续向上 propagate——
> # 改成 except Exception 会复活已被删除的静默吞错，违背"坏数据宁可暴露错误也不自欺"。
> # 契约由 regression_scheduler_candidate_runner_contract.py:473 守护。
> ```

---

### F4 · 三套私有正整数强制器与统一收口点 `parse_finite_int` 并存（契约各异：raise / →0 / →None）

- **病理标签**：P5（第 N 套私有实现）｜**严重度**：low
- **load_bearing 字段**：false → **但对抗裁决推翻为 `_adv_verdict = load_bearing`（`_adv_refuted = false`）**：三套契约是按上下文刻意分化的，**不可裸合并**。本条因此**以承重论处**。
- **复核结论**：✅ **证据仍准**。三个强制器现仍在 `payload_contract.py:50` / `auto_assign_resource_errors.py:114` / `schedule_persistence_errors.py:13`，6 个 `_strict_positive_int` 调用点的 `except (TypeError, ValueError)` 全部对齐；收口点 `parse_finite_int` 仍在 `number_utils.py:39` 且仍无 `min_value` 形参。唯一漂移:`_positive_int` 全仓计数因新增资源派工车道由 6→7(live grep 实证,见下)，**本分区内 2 处不受影响**。

**位置（三套并存）**
1. `core/services/scheduler/run/schedule_payload_contract.py:50` —— `_strict_positive_int`：`None`/`bool`/`float`/`<=0` **全 raise `ValueError`**，是 `_iter_actionable_results` 与 `_build_validated_schedule_row` 的 `op_id` 落库闸门。
2. `core/services/scheduler/run/auto_assign_resource_errors.py:114` —— `_positive_int`：`except → 0`（错误消息解析路径上的 fall-through sentinel，配合 `:85-86` 的 `if batch_id and seq > 0`）。
3. `core/services/scheduler/run/schedule_persistence_errors.py:13` —— `_positive_int`：`except → None`（装配 `raise_no_actionable_schedule_error` 时的 id-dropping sentinel）。

**统一收口点**：`core/shared/number_utils.py:39` `parse_finite_int(value, *, field, allow_none)`——`allow_none` 重载恰好覆盖"返回 None"（`:41` 转 `parse_optional_int`）与"raise"（`:42` 转 `parse_required_int`）两种语义。同分区的 `optimizer_config.py:75,83` 则**正确**走 `core.shared.strict_parse`（`parse_required_float`/`parse_required_int`）。

**引用链 / 为何算债**
已有覆盖"可空/必需"两态的 `parse_finite_int` 收口点，本分区仍各处私造正整数强制器，三者语义已**漂移**（异常 vs 0 vs None），且 `_strict_positive_int` 抛**裸 `ValueError`** 而非 field 化的 `ValidationError`，属同一概念（正整数强制）的第 N 套私有实现，绕过收口点。
- `_positive_int` 当前**全仓 7 处**(本轮 `grep -rn 'def _positive_int' core/ web/` live 实证,排除 2 个 `_positive_int_set`;原 finding 写"6 处",65870e47 新增 `resource_dispatch_execution_service.py:23` 与 `scheduler_resource_dispatch_execution.py:32` 两处导致 +1。注:此前引的 `2026-06-01-foundation-maturity/codemap/dup_symbols.json` 出处文件在本仓不存在,已改为 live grep 证据)；**本分区内仍恰为 2 处**：`auto_assign_resource_errors.py:114` 与 `schedule_persistence_errors.py:13`，与原定位一致。

> 🛑 **承重裁决（对抗已确权为 load_bearing，绝对不可裸合并）**
>
> 怀疑者复核后**未能推翻**这三套的分化是刻意的，反而坐实了它——三者契约按上下文（**落库闸门 / 解析不可信错误文本 / 装配错误响应**）刻意分化，裸合并会破坏不变量：
>
> 1. **收口点表达力不足**：`parse_finite_int`（`number_utils.py:39`）**没有 `min_value` 形参**，根本表达不出 `op_id` 的契约（`>0` 且**非 float**）。底层 `strict_parse._parse_finite_int`（`strict_parse.py:46-58`）**接受整值 float**（`3.0→3`，`abs(parsed-int)<=1e-9`，`:56`），且 `parse_required_int` 默认 `min_value=None`——**严格弱于** `_strict_positive_int`（后者 `isinstance(value,float)` 一律 raise、`<=0` 一律 raise）。
> 2. **异常类型不兼容会击穿 6 个 except**：`core/infrastructure/errors.py:63,97` —— `class ValidationError(AppError)`、`class AppError(Exception)`，`ValidationError` **不是** `ValueError`/`TypeError` 子类。`_strict_positive_int` 的 6 个调用点全部 `except (TypeError, ValueError)`（`payload_contract.py:73,150,199,309,325,373`）——若换成抛 `ValidationError` 的收口点，异常会**逃逸所有 6 个本地 except**，把 `count`/`has_actionable_schedule_rows` 从"容错跳过脏行"变成"崩溃"。该 raise 是**内部 sentinel 而非真 abort**。
> 3. **数据腐蚀风险**：`payload_contract.py:33-47` `to_repo_rows` 对 DB write 做 `int(row.op_id)`（op_id 是 linkage / lock_status 键），下游无 bool/float 再守卫；Python 中 `isinstance(True,int)` 与 `3.0 in {3}` 均为 True，故 `True→1` / `3.0→3` 会**静默腐蚀 op↔row 映射**。`_strict_positive_int` 对 bool/float 的拒绝是这道腐蚀的唯一闸门。
> 4. **错误路径上的容错 sentinel 不可改抛错**：`auto_assign_resource_errors.py:85-86,114-119` 的 `→0` 与 `schedule_persistence_errors.py:13-18` 的 `→None` 都在**错误处理/错误消息解析**路径上——让它们抛错会**用二次异常掩盖真正的诊断**，违背暗线"坏数据不准静默兜底**但也不自欺**"。

**爆炸半径**
统一到 `parse_finite_int` 的 naive 替换会把"容错点"变成"抛错点"、把"落库闸门"放水接受 float——高危。属边界 P5，承重不对称已被对抗确权。

**处置建议 + 收口点（带前置条件，缺一不可）**
**不可裸合并；按债登记、低优先**。若日后确要收口到 `parse_finite_int`，必须满足全部前置条件：
1. **先扩展收口点**：给 `parse_finite_int`（`number_utils.py:39`）增加 `min_value` 形参，并加"拒绝任何 float（含整值 3.0）"的严格模式——否则收口点表达不出 `op_id` 的 `>0 且非 float` 契约。
2. **保契约迁移每个调用点**：`_strict_positive_int` 的 raise 必须仍能被原地 except 捕获（要么把 6 处 `except` 改成捕获 `ValidationError`，要么保留 `ValueError` 语义），否则 `count`/`has_actionable_schedule_rows` 会从"跳过脏行"变成"抛错"。
3. **不得把 `auto_assign(→0)` 与 `schedule_persistence_errors(→None)` 改成抛错**——它们在错误处理路径上，抛错会用二次异常掩盖真正诊断。

**该补的"我是故意的"注释文案**（分别加在三个强制器上方，把刻意分化显式化）：
- `payload_contract.py:50`（`_strict_positive_int`）：
  ```python
  # [承重·勿合并到 parse_finite_int] op_id 落库闸门：拒 bool/float/<=0。
  # 抛裸 ValueError 是"内部 sentinel"——6 个调用点(:73/:150/:199/:309/:325/:373)
  # 用 except (TypeError, ValueError) 接住转"跳过脏行"。收口点 parse_finite_int 抛的是
  # ValidationError(非 ValueError 子类)且无 min_value/拒 float 能力,裸替换会击穿这些 except
  # 并放水让 True->1 / 3.0->3 腐蚀 op<->row 映射(见 to_repo_rows int(op_id))。
  ```
- `auto_assign_resource_errors.py:114`（`_positive_int → 0`）：
  ```python
  # [承重·勿改抛错] 错误消息解析路径上的 fall-through sentinel(配合 :86 if batch_id and seq>0)。
  # 这是"解析不可信错误文本"语境,容错归 0 是刻意的;改成抛错会用二次异常掩盖真正诊断。
  ```
- `schedule_persistence_errors.py:13`（`_positive_int → None`）：
  ```python
  # [承重·勿改抛错] 装配 raise_no_actionable_schedule_error 时的 id-dropping sentinel。
  # 在"组装错误响应"路径上让坏 id 安静消失,改成抛错会用二次异常掩盖主错误(违背暗线)。
  ```

---

### 本分区债务索引（速查）

| 编号 | 病理 | 严重度 | load_bearing | 复核 | 一句话处置 |
|------|------|--------|--------------|------|-----------|
| F1 | P6 死函数 | medium | false | ✅ 证据仍准 | 直接收，连带删 `test_sp05` 断言，收口到 `_validate_persist_inputs(:201)` |
| F2 | P6 冗余转发 | low | false（对抗判 real_debt 可删） | ✅ 证据仍准 | 先改测试 import 再删包装器，收口到 `resource_matching_context.__all__` |
| F3 | P6 不可达下游脚手架 | low | false（内嵌承重窄 except :216） | ✅ 证据仍准 | needs_adversarial，倾向留 + 补注释；**窄 except 绝不可改宽** |
| F4 | P5 第 N 套正整数强制器 | low | **对抗推翻为 load_bearing** | ✅ 证据仍准（全仓计数 6→7） | 不可裸合并，按债登记 + 补三条注释；收口需先给 `parse_finite_int` 加 `min_value`/拒 float |

---

## 02 · 分区【scheduler-dispatch】资源派工（resource_dispatch_*）水下语义债

**分区健康一句话**：本分区主体是 5 月底刚落地的"资源派工执行车道"（roadmap 全 done，commit `65870e47`），降级处理（超期标记 degraded/partial 上抛 + 日志）忠实贯彻"坏数据不准静默兜底"灵魂线，绝大多数 `except` 是 anti-P4（重抛或记 degradation），**无两套并行生产实现、无 plan_id 式死透传**；水下债集中在边角——一处承重的资源 scope 列映射双轨漂移（派工绕开收口点，且其中 team 轴是收口点表达不了的真实承重逻辑）、一个误建的空包、一处写后卡片对 schedule 缺失的静默兜底、一个生产不可达的休眠开关 + 死面包屑、一组三处逐字节复制的可空正整数助手。共 **5 条**。

> 本节复核基准：2026-06-02 当前代码（分区内多文件处于 git modified/added，刚随 `65870e47` 落地）。每条结论标注 ✅证据仍准 / ⚠️行号已变 / 🔧疑似已修复。

---

### 02-1 · 派工 scope_type 归一与 operator/machine→列映射绕开 ScheduleResourceFilter 收口点（双轨漂移）

- **病理标签**：P5（第 N 套私有实现）
- **严重度**：medium
- **load_bearing**：⚠️ **承重（关键）**。条目原始字段 `load_bearing=false`，但对抗验证把它**升级为 `load_bearing`**（`_adv_verdict: "load_bearing"`，`_adv_refuted: false`）。原因：operator/machine 那部分列映射确属可复用却没复用的债，但 **team（班组）轴的双 join 是收口点根本表达不了的真实第三轴，是承重逻辑**，不能随"统一"一起塌缩。本条因此是"可约简的 P5 外壳 + 不可约简的承重内核"复合体，需特别醒目对待。

**位置**
- `core/services/scheduler/resource_dispatch_service.py:63`（`_normalize_scope_type`，自校验 `{operator,machine,team}`）
- `data/repositories/schedule_plan_query_repo.py:447-463`（`list_dispatch_rows`，内联列映射；team 双 join 在 461-463）

**引用链（当前代码逐段复核）**
1. `resource_dispatch_service._normalize_scope_type:63-67` 自校验 `{operator,machine,team}` 并自报 `ValidationError("视角类型不正确…")`，**不调用** 收口点 `core/models/schedule_resource_filter.normalize_schedule_resource_filter`（该收口点仅认 `{machine,operator}`）。
2. `get_dispatch_payload`（def 现位于 `resource_dispatch_service.py:350`）在 `:368` 调 `_normalize_scope_type`，于 `:424-433` 调 `plan_query_service.list_plan_dispatch_rows_for_resolution(...)`，其中 `scope_type=normalized_scope_type` 在 `:431`、`scope_id=selected_scope_id` 在 `:432`。
3. `schedule_plan_query_service.list_plan_dispatch_rows_for_resolution:387` → `:399` 转调 `repo.list_dispatch_rows`。
4. `schedule_plan_query_repo.list_dispatch_rows:430` 内联展开 scope（当前精确行）：
   - `:451-453` `operator` + 有 id → `TRIM(COALESCE(s.operator_id,''))=?`
   - `:454-455` `operator` 空 id → `TRIM(COALESCE(s.operator_id,'')) <> ''`（全部人员视图）
   - `:456-458` `machine` + 有 id → `s.machine_id`
   - `:459-460` `machine` 空 id → `<> ''`（全部设备视图）
   - `:461-463` `team` + 有 id → `((o.team_id = ?) OR (m.team_id = ?))`，`params.extend([scope_id_text, scope_id_text])`
5. **另一轨（超期/明细读取）走收口点**：同一 repo 文件 `list_overdue_base_rows`（`:391` `overdue_resource_filter(...)` → `:396` `resource_scope.column_name`）以及 `data/repositories/schedule_resource_sql_filters.py:18-19`（`overdue_resource_filter`）+ `:36`（`append_detail_filters` 用 `s.{resource_filter.column_name}`）。
6. 收口点本体 `core/models/schedule_resource_filter.py`：`:8` `SUPPORTED_SCHEDULE_RESOURCE_TYPES={machine,operator}`；`:19-24` `column_name` 对 team 返回 `''`；`:59-70` 对不支持类型 raise、对缺 id raise。
7. **canonical normalizer 在派工链路零引用**：grep `normalize_schedule_resource_filter` / `column_name` 于 `resource_dispatch_service.py` 与 `schedule_plan_query_service.py` 均 0 命中。

**为何算债**
资源类型→列名这件事项目已有统一收口点（`column_name` 属性 + `normalize_schedule_resource_filter`），但派工读取链路私自实现第 N 套：service 层自校验类型 + repo 层内联列字面量（`s.operator_id` / `s.machine_id`）。后果是 operator/machine 列名规则散在派工与超期两处，改一处忘另一处会让"派工筛选"和"超期筛选"对同一资源口径漂移。**但**：team 班组轴（双 `team_id` join）是收口点 `{machine,operator}` 单列属性结构上表达不了的真实第三轴——这是派工链路不能整体塌缩到现状收口点的合理原因。因此真正可约简的只有 operator/machine 列字面量，team 分支是承重特例。

**对抗验证结论（已证陷阱）**
- `column_name('team') == ''` 而 `has_filter('team') == True`：把 team 路由进收口点，要么 raise（吵闹）、要么静默丢掉 WHERE 子句返回**全部班组数据**（坏数据静默兜底，直接违反灵魂线）。
- 收口点 `:59-70` 对缺 id **强制 raise**（实测 `normalize_schedule_resource_filter('operator','')` → `资源筛选缺少资源编号`），会打断派工的"全部人员/全部设备"（空 id）视图。
- `_normalize_scope_type` 是收口点的**超集校验器**（含 team + 空 id 语义），不是它的重复实现，**不能直接换**。
- `tests/test_scheduler_resource_dispatch_smoke.py:177`（`scope_type=team&team_id=TEAM-OP&team_axis=operator…`）、`:182`（断言"班组轴"）、`:162`（"跨班组"）是活的、被测的生产行为，naive 替换是真实回归而非理论。

**爆炸半径**
- 若有人"统一"把 `_normalize_scope_type` 直接换成 `normalize_schedule_resource_filter`：丢掉 team 轴 → 班组视角整页 500。
- 若强行让 `repo.list_dispatch_rows` 复用 `column_name` 而漏处理 team 分支：team 筛选静默失效返回全量坏数据。
- 任何改动必须**同时保留 team 特例与空 id 全量语义**。

**处置建议 + 收口到哪个统一点**
方向是"先扩容收口点，再谈统一"，**严禁反向把派工塞进现状收口点**。顺序：
1. 给 `ScheduleResourceFilter` / `normalize_schedule_resource_filter` 增加 **team 轴表达能力**——`column_name` 单列属性不够，需新增一个能产出 `((o.team_id=?) OR (m.team_id=?))` 双 join 谓词的接口；并放开"类型有、id 空 = 全量"语义（当前收口点强制非空 id，会打断派工全部人员/全部设备视图）。
2. **先补回归断言**：`scope_type=team` 只返回该 team 的行而非全量（钉死"静默丢谓词"反例），以及"全部人员/全部设备"空 id 视图仍可查。
3. **仅在收口点同时覆盖 team 双轴 join + 空 id 全量语义后**，才可把 repo 的 `s.operator_id` / `s.machine_id` 列字面量和 `_normalize_scope_type` 收敛进去。在此之前两轨必须并存；`test_scheduler_resource_dispatch_smoke.py` 的 team 用例须全程保持绿。

**"我是故意的"注释文案**（建议补在 `schedule_plan_query_repo.py:461` team 分支上方，钉死承重意图）：
```python
# 【承重·勿统一】team（班组）轴是双 join 谓词 ((o.team_id=?) OR (m.team_id=?))，
# core.models.ScheduleResourceFilter.column_name 只能产单列、且 SUPPORTED 只含
# {machine,operator}，结构上表达不了班组轴。此处必须独立内联，不能塌缩进收口点。
# 同理 operator/machine 的空 id 分支（全部人员/全部设备视图）依赖"类型有、id 空=全量"
# 语义，收口点当前对缺 id 强制 raise，也不能直接替换。
# 收敛前置条件见审计 02-1：先给收口点补 team 双 join + 空 id 全量语义。
```
并建议在 `resource_dispatch_service.py:63` `_normalize_scope_type` 上方注明"本校验器是收口点的超集（多 team），不可被 normalize_schedule_resource_filter 替换"。

**复核结论**：✅ 证据仍准。`_normalize_scope_type:63`、repo `list_dispatch_rows:447-463`（team 双 join 精确落在 461-463）、service 调用点 `:424-433`（`scope_type` kwarg 仍在 `:431`）、收口点 `schedule_resource_filter.py:8/19-24/59-70`、超期轨 `schedule_resource_sql_filters.py:18-19/36`、smoke 测试 `:177/182/162` 全部逐行对上。仅 `get_dispatch_payload` 的 def 行随车道落地略有位移（现 `:350`），但条目原始引用的是其内部调用点 `:431`，该行仍精确。

---

### 02-2 · 空包 `core/services/scheduler/dispatch/` 为无关提交误建、零引用残渣

- **病理标签**：P3（半截迁移/脚手架残渣）
- **严重度**：low
- **load_bearing**：false

**位置**：`core/services/scheduler/dispatch/__init__.py`

**引用链（当前代码逐段复核）**
- `ls -la core/services/scheduler/dispatch/` → 目录仅含 `__init__.py`，**0 字节**（`wc -c` = 0），无任何兄弟模块。
- `git log --oneline -- core/services/scheduler/dispatch/` → 唯一提交 `24f4c93e "Implement SP05 path topology guardrails"`（SP05 是图拓扑护栏，与资源派工域**无关**）。
- grep `scheduler\.dispatch` / `scheduler/dispatch`（排除 `resource_dispatch`、`greedy`、`schedule_graph_dispatch`）全仓：**仅** `.codestable/audits/*` 与 `.codestable/checkup/latest/codemap/modules.json` 等审计/codemap 文档命中，**零生产代码引用**（无 `.py` / `.html` / 业务 `.json` 动态 import）。

**为何算债**
迁移/脚手架残渣：一个无关 feature（SP05 图拓扑）顺手建的空 package，命名恰好撞上"dispatch"域，既无内容也无引用，制造"派工还有个 dispatch 子包"的假象，误导后来者去找根本不存在的模块（实际派工代码全在 `core/services/scheduler/` 外层平铺为 `resource_dispatch_*`）。

**爆炸半径**：删除无任何运行时影响（零 import）。唯一风险是若未来有人误以为它是命名空间锚点，但当前无证据。

**处置建议 + 收口到哪个统一点**：直接删除空目录 `core/services/scheduler/dispatch/`（删前再确认无 `importlib` 字符串动态引用，本次 grep 已确认无）。与第一轮地基体检（`.codestable/audits/2026-06-01-foundation-maturity/`）记录的"清空占位目录"一并处理——同源残渣应收到同一次清理 PR。无需新建任何收口点。

**复核结论**：✅ 证据仍准。0 字节、唯一提交 `24f4c93e`、零生产引用三项全部当前复现。

---

### 02-3 · 写后任务卡对 schedule 行缺失静默兜底为"正式采用方案/可写"卡片

- **病理标签**：P4（静默兜底死角）
- **严重度**：low
- **load_bearing**：false（对抗验证 `_adv_verdict: "real_debt"`，`_adv_refuted: true`——"这是防御性回显"的辩护被驳回，确认是真该暴露的缺口）

**位置**：`core/services/scheduler/resource_dispatch_execution_service.py:131-141`

**引用链（当前代码逐段复核）**
- `task_card_for_feedback_context`（def `:124`）在 `:131` `schedule = self.schedule_repo.get(int(context.schedule_id))`。
- `:132 if schedule is None:` → `:133-141` 直接返回 `plan_identity={}`、`plan_identity_label="正式采用方案"`、`can_write_feedback=True`、`feedback_write_enabled=feedback_write_enabled` 的**正常卡片**，不抛错也不降级。
- 对照正常分支 `:142-167`：schedule 存在时才用 `list_plan_dispatch_rows_for_resolution` + `_matching_row` 装配真实"实际/计划对比卡"。
- `context.schedule_id` 来源：routes `_feedback_context` 取自 payload，且写入门禁已在别处校验 op_id+schedule_id+batch_id 在当前计划查询行内——即"计划行内有、`schedule_repo.get` 返 None"是真数据缺口/真不一致。

**为何算债**
项目灵魂线是"坏数据不准静默兜底、宁可暴露错误"。这里 schedule 行查不到（真缺口/真不一致）时，不抛错也不降级提示，直接返回 `can_write=True` 的"正式采用方案"卡，把缺口吞掉。虽是写入成功后的展示路径（写门禁在别处独立强校验，**不构成越权写**），但用户看到的"实际/计划对比卡"建立在已不存在的 schedule 行上，属于自欺式兜底。

**对抗验证结论（分支当前不可达，但兜底写法本身仍是债）**
该 None 分支在生产**不可达**——每条写路径在装卡前已 raise NOT_FOUND：
- legacy 写路径 `operation_execution_feedback_service._load_current_official_schedule`（`:347`）在写事务内 `schedule_repo.get` 为 None 时 raise `AppError(NOT_FOUND)`（`:365`/`:368`），装卡时行已证存在于同一连接。
- 实际记录写路径 `resource_dispatch_actual_record_service._task_ref_from_feedback_context:214` 在 `schedule_repo.get` 为 None 时 raise NOT_FOUND（`:218`）。
- `card.can_write_feedback` 仅 UI 提示——后续每次写都服务端重推 plan identity 并重跑 official/existence 门禁，撒谎的卡片授权不了任何坏写。

**爆炸半径**：仅影响单条写入成功后的回显卡片正确性；不影响写入门禁（门禁独立强校验）。若改为抛错需确认不会把正常写后回显误判失败（happy path 本就不走该分支，故无影响）。

**处置建议 + 收口到哪个统一点**
**不要裸删 `:131-141`**——直接删会让控制落到 `:142`/`:147-148` 的 `schedule.start_time`，在写入已提交后抛 `AttributeError` → 500，谎报写失败。正确做法：把该 None 分支改成**显式 `raise AppError(ErrorCode.NOT_FOUND, …)`**，与灵魂线及同模块既有写门禁口径一致（收口到 `operation_execution_feedback_service:365/368`、`resource_dispatch_actual_record_service:218` 已用的 NOT_FOUND 文案族）；并先确认/锁定两个调用语义：装卡始终发生在写门禁通过之后。补一条"该分支转 raise"的回归测试。改完不影响 happy path（分支本就不可达），不削弱任何写门禁。

**复核结论**：✅ 证据仍准（主位置精确）。`:131` `schedule_repo.get`、`:132-141` 兜底 return 当前逐行对上；不可达性所依赖的 NOT_FOUND raise 仍在（`operation_execution_feedback_service:365/368`、`resource_dispatch_actual_record_service:218`）。⚠️ 附注：条目对抗证据里引用的 routes 调用点行号（`264-265/278-279/200-201`）随车道 `65870e47` 落地已位移——`task_card_for_feedback_context` 的生产调用点现为 `scheduler_resource_dispatch_execution_routes.py:184 / :192 / :201`（三处恒传 `feedback_write_enabled=True`，且卡片严格在写步骤成功返回后构建）。核心结论与处置不变。

---

### 02-4 · `feedback_write_enabled` 休眠开关 + 生产不可达的"保护未开启"提示

- **病理标签**：P6（死代码/死面包屑）
- **严重度**：low
- **load_bearing**：false（对抗验证 `_adv_verdict: "real_debt"`，`_adv_refuted: true`——"它是已接线的未来 toggle"的辩护被驳回）

**位置**：`web/viewmodels/scheduler_resource_dispatch_execution.py:24, 226-227, 361-362`

**引用链（当前代码逐段复核）**
- 唯一数据路径生产者 `resource_dispatch_execution_service.get_execution_context` 把两者设为**同一来源**：`:117` `"can_write_feedback": bool(plan_role_fields.get("can_write_feedback"))`，`:120` `"feedback_write_enabled": bool(plan_role_fields.get("can_write_feedback"))`——同源恒等。`:204` `_empty_context` 两者皆 `False`。主路径只产 `(True,True)`/`(False,False)`，`(True,False)` 不可达。
- viewmodel 常量 `:24` `_FEEDBACK_DISABLED_REASON = "现场记录保护还没开启，暂不能填写现场记录。"`
- `_fill_actual_disabled_reason`（def `:223`）`:224 if not can_write: return _NOT_CURRENT_OFFICIAL_REASON`；`:226-227 if not feedback_write_enabled: return _FEEDBACK_DISABLED_REASON`——仅 `(can_write=True, feedback_write_enabled=False)` 才到。
- `build_execution_payload`（def `:331`）`:359-360 if not can_write` → `_NOT_CURRENT_OFFICIAL_REASON`；`:361-362 elif not feedback_write_enabled` → `_FEEDBACK_DISABLED_REASON`——同样仅该不可达组合才返回。
- `task_card_for_feedback_context`（service `:124`，默认参 `:129 feedback_write_enabled=True`）路径 `can_write_feedback` 恒为 `True`；三处路由调用方 `scheduler_resource_dispatch_execution_routes.py:184/192/201` 恒传 `feedback_write_enabled=True`，故只产 `(True,True)`，同样不可达 `(True,False)`。
- 全仓 grep `feedback_write_enabled`：无任何 `config`/`settings`/特性开关读取它（唯一旁系命中是 `scheduler_workbench_links.py` 的 `can_emit_feedback_write_urls`，是 URL 发射的另一关注点）。

**为何算债**
参数本身被消费（非纯死参），但它守护的状态组合 `(True,False)` 在生产**永不出现**，"现场记录保护还没开启"这句用户可见文案真实用户永远看不到。文案口吻（"还没开启"）像是为未来"反馈保护总开关"预埋的 toggle，却从未接到任何配置/特性开关，成了散布在 viewmodel 多处的死面包屑，制造"有个保护开关在用"的假象。

**对抗验证结论**
- service `:117/120` 同源恒等、`:204` 双 False，证实 `(True,False)` 主路径不可达。
- 真正写入护栏在 `operation_execution_feedback_service:361`（`raise … if not plan_identity.can_write_feedback`）与 `resource_dispatch_actual_record_service:137-149`（`_ensure_context_can_write` 基于 `can_write_feedback`/plan_role/source_table/scenario），**全程不消费 `feedback_write_enabled`**——删该展示分支不削弱任何写入不变量。
- `tests/regression_resource_dispatch_workbench_lane_contract.py:164-174` 传 `(can_write_feedback=False, feedback_write_enabled=False)`，因 `can_write=False` 在 `build_available_actions:234` 与 `_fill_actual_disabled_reason:224` 双重短路，`feedback_write_enabled` 分支根本未被执行；grep 确认全仓无任何对 `现场记录保护`/`FEEDBACK_DISABLED`/`disabled_reason` 的断言。

**爆炸半径**：删除该分支与文案不影响任何生产行为（状态不可达），且不破任何测试（已 grep 确认无人断言该字符串）。

**处置建议 + 收口到哪个统一点**（二选一，均需先向 owner 确认）
- **(A) 只删死分支 + 死文案**：删 viewmodel `:226-227` 与 `:361-362` 的 `feedback_write_enabled` 分支及 `:24` 的 `_FEEDBACK_DISABLED_REASON` 常量，保留参数即可，无测试会断。
- **(B) 彻底收口**：把 `feedback_write_enabled` 参数整体并入 `can_write_feedback`——须同步改 4 处签名：service `:129` 默认参、routes `:184/:192/:201` 三处 kwarg、test 的 `build_task_card` 调用，去掉 kwarg 后再删 viewmodel 分支。
- **前置闸门**：两种做法前都应向刚落地的"resource dispatch execution lane" roadmap（commit `65870e47`）owner 确认：近期不计划在此接缝上线真正的"现场记录保护总开关"配置。若确无该规划，按默认立场收为普通债（推荐 A，改动面最小）。

**复核结论**：✅ 证据仍准。`:24`/`:226-227`/`:361-362` 三处 viewmodel 锚点、service 同源 `:117/120`、`_empty_context:204`、test `:164-174` 全部逐行对上（`_fill_actual_disabled_reason` def 现 `:223`，分支体仍 `:226-227`）。

---

### 02-5 · `_positive_int` 可空正整数助手在执行车道三处逐字节复制

- **病理标签**：P5（第 N 套私有实现）
- **严重度**：low
- **load_bearing**：false（对抗验证 `_adv_verdict: "real_debt"`，`_adv_refuted: true`——"是允许的层内小助手"辩护被驳回，确认是真 P5；但有"换错收口点会更糟"的强约束）

**位置**（三处函数体逐字节相同）
- `core/services/scheduler/resource_dispatch_execution_service.py:23`
- `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:37`
- `web/viewmodels/scheduler_resource_dispatch_execution.py:32`

**引用链（当前代码逐段复核）**
三处 `def _positive_int(value: Any) -> Optional[int]:` 函数体完全相同（已逐行核对）：
```python
def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
```
契约 = "垃圾 → None、非正 → None"（可空跳过，用于遍历可信 DB 行/已校验整数时跳过无 op_id 的行）。调用点全是显示与归属判定：service `_op_ids`/`_matching_row`、viewmodel `build_task_card`/任务列表（`:347` 等）、routes `_row_matches_feedback_target` 比对可信行。

**全仓散布（grep `def _positive_int` / `def _required_positive_int`，当前 10 文件）**：
- 本簇 3 处可空变体（上列）
- **STRICT（raise）变体，契约不同，不在本簇收口范围**：`operation_execution_feedback_support.py:162`（`_positive_int(value, field)` raise）、`data/repositories/operation_execution_event_repo.py:96`（`_required_positive_int` raise）、`core/models/scheduler_public_errors.py`、以及 `graph/input_adapter.py`、`summary/schedule_summary_assembly.py`、`run/auto_assign_resource_errors.py`、`run/schedule_persistence_errors.py` 等。

**为何算债**
同一个"解析正整数"诉求在一个 feature 内复制三份（且全仓十余份），项目本有 `core/shared/number_utils.parse_finite_int` 统一解析收口。但 `_positive_int` 的契约（垃圾静默成 None、过滤非正、用于遍历行时跳过坏行）与 `parse_finite_int`（垃圾抛错）确有差异，故严格说不是直接绕开同一职责，介于 P5（第 N 套私有解析）与可接受的层内小助手之间——对抗验证裁定为真 P5：可空契约本身值得有一个 canonical 收口，三处逐字节复制是不必要的重复。

**对抗验证结论（严禁套错收口点）**
- 收口点 `parse_finite_int` 契约不同：`core/shared/number_utils.py:39` `allow_none=True` 仅短路空白，垃圾仍 raise（`core/shared/strict_parse.py:36/40` 对非数字 `raise ValidationError("…必须是数字")`）。套用会把"跳过坏行"退化为"抛错中断整页"。
- 真正的安全不变量由别处 RAISE 守住，非本助手的静默 None：反冒充归属校验无匹配行时抛 `SCHEDULE_CONFLICT`（routes）；用户输入 `schedule_id` 为 None 时抛 `ValidationError`（routes，fail-closed）；写入边界用 STRICT 变体重新校验并抛错（`operation_execution_feedback_support.py:162`、`operation_execution_event_repo.py:96`，写路径在 `operation_execution_feedback_service:222-224` 调用）。`op_id` 经 Flask `<int:op_id>` 路由转换器已是合法整数。

**爆炸半径**：若强行换成 `parse_finite_int` / `parse_optional_int(allow_none=True)`，遍历行收集 op_id 处会从"跳过坏行"变成"抛错中断整页"，并改变 routes 用户输入 `schedule_id` 的拒绝路径。需新增一个 canonical 的"可空正整数"收口，而非套用 `parse_finite_int`。

**处置建议 + 收口到哪个统一点**
1. 先在 `core/shared`（与 `number_utils.parse_finite_int` 同处）新增一个 canonical 的**可空正整数**收口，契约必须保持「垃圾→None、非正→None」——即 `parse_finite_int` 的兄弟，建议命名 `parse_optional_positive_int`。
2. 把本簇 3 处（及全仓其余 nullable 同体）迁移过去。
3. **严禁**改用 `parse_finite_int` / `parse_optional_int(allow_none=True)`（它们对垃圾值 raise）。
4. **不要动 STRICT 变体**（`operation_execution_feedback_support.py:162`、`operation_execution_event_repo.py:96`、`scheduler_public_errors.py`）——它们契约是 raise，是真正的写入闸门，不在本簇收口范围。

**复核结论**：✅ 证据仍准。三处 `_positive_int` def 当前位于 `service:23 / routes:37 / viewmodel:32`，函数体逐字节相同已核对；收口点 `number_utils.parse_finite_int:39` 与其 raise 链 `strict_parse.py:36/40` 仍在；STRICT 变体 `operation_execution_feedback_support.py:162`、`operation_execution_event_repo.py:96` 仍在。全仓散布现为 10 文件（与条目"5+ 处"一致，更多）。

---

### 本分区复核汇总

| # | 病理 | 严重度 | load_bearing | 复核 |
|---|------|--------|--------------|------|
| 02-1 | P5（含承重内核） | medium | ⚠️ 承重（adv 升级） | ✅ 证据仍准 |
| 02-2 | P3 | low | false | ✅ 证据仍准 |
| 02-3 | P4 | low | false | ✅ 主位置准；附注 routes 调用点行号已移至 184/192/201 |
| 02-4 | P6 | low | false | ✅ 证据仍准 |
| 02-5 | P5 | low | false | ✅ 证据仍准 |

合计 5 条：5 条主位置证据仍准，其中 02-3 的**对抗证据**层 routes 调用点行号随车道 `65870e47` 落地位移（已给新行号 184/192/201），主位置 `resource_dispatch_execution_service.py:131-141` 不变；0 条疑似已修复。承重重点是 02-1 的 team 双 join 轴，必须先扩容收口点、补回归断言，才能收敛 operator/machine 那部分可约简的 P5 外壳。

---

## 03 分区:scheduler-gantt(甘特调整闭环 `gantt_*`)

**分区健康一句话:** 有残渣但整体偏干净——调整闭环(publish/draft/scenario/validation/projection)是全分区最成熟的一块(严格 `strict_parse`、`ValidationError` 主动暴露、快照 revision/异常工序多重承重护栏、`DegradationCollector` 统一透出降级,完全贴合"坏数据不准静默兜底"的灵魂暗线);水下残渣仅三处且均**非承重**(`load_bearing=false`):1 个已提交的零消费死方法(名字还撒谎)、1 个被复制成第二份的私有归一函数、1 个只读关键链覆盖层的轻度静默丢行盲点。无 P1/P2/P3。

> 复核口径:本次普查所有 file:line 已回到【当前】分支 `codex/aps-three-gap-directions` 代码逐条 grep/Read 复核。三条债的**主证据位置全部仍精确**;两处**非位置性的状态变化**已在对应条目的"复核结论"中如实标注(债 2 的文件已从未提交转为已提交;债 3 的一处兄弟范式交叉引用行号 +4)。

---

### 债 1 ── `get_latest_version_or_1` 零生产消费的死方法,且名字与实现自相矛盾

- **病理标签:** `P6`(死代码/死面包屑) · **严重度:** low · **load_bearing:** false
- **位置:** `core/services/scheduler/gantt_service.py:60-62`

```
60	    def get_latest_version_or_1(self) -> int:
61	        v = int(self.history_repo.get_latest_version() or 0)
62	        return v if v > 0 else 0
```

- **引用链:**
  - 定义点 `gantt_service.py:60` `def get_latest_version_or_1`。
  - 全仓 `grep 'get_latest_version_or_1('` 仅两处命中:① 定义点本身 `gantt_service.py:60`;② `tests/regression_scheduler_week_plan_summary_observability.py:59` 的 `_GanttServiceStub.get_latest_version_or_1`——那是 stub **定义**(当前实现 `return 3`,见该文件 :55-60)而非对真实方法的调用,通读该测试该 stub 方法从不被 invoke。
  - 真实周计划路由 `web/routes/domains/scheduler/scheduler_week_plan.py:278/284/377` 只调用 `svc.resolve_week_range`(:278)与 `svc.get_week_plan_rows`(:284、:377),从不碰此方法(已 grep 确认该路由文件内无 `get_latest_version_or_1` 命中)。
  - 函数体语义:`v = int(history_repo.get_latest_version() or 0); return v if v > 0 else 0`——名字承诺 `or_1`,实际无历史时返回 **0**,而非 1。

- **为何算债:** 定义后零真实 caller(Flask 路由/registry 已逐一排除,确为静态非盲区),纯死代码。更坏的是测试 stub 镜像了它,制造出"`GanttService` 对外 API 仍在用此方法"的假象(P6 典型的"散布多处造成看起来在用")。名字 `or_1` 与返回 `0` 的矛盾会误导未来读者,以为空态有 `version=1` 的兜底。注意同类正确实现就在隔壁 `resolve_version`(:64-70)——它走 `resolve_version_or_latest` 统一解析,根本不需要这个裸方法。

- **爆炸半径:** 删方法(`gantt_service.py:60-62`)+ 删测试 stub 的该方法(`regression_scheduler_week_plan_summary_observability.py:59-60`),**无生产影响(零 caller)**。唯一风险是若未来有人凭名字以为它返回 1 来写新代码——删掉反而消除误导。

- **处置建议 + 收口点:** 直接删除死方法及其测试 stub 镜像。版本解析的**统一收口点已存在**——`gantt_service.py:64 resolve_version` → `core/services/scheduler/version_resolution.py` 的 `resolve_version_or_latest` / `require_selected_version`。任何"取最新版本"的需求都应走这条已成熟的解析链,不再保留这个名实不符的裸 getter。

- **复核结论:** ✅ 证据仍准。`gantt_service.py:60-62` 行号与函数体逐字一致;测试 stub 仍在 `:59`(stub body 现为 `return 3`,不影响"从不被调用"的结论)。周计划路由仍只调用 `resolve_week_range`/`get_week_plan_rows`,死方法定性不变。

---

### 债 2 ── 关键链结果归一函数 `_normalize_critical_chain_result` 被复制成第二份私有实现

- **病理标签:** `P5`(第 N 套私有实现) · **严重度:** low · **load_bearing:** false · **对抗验证:** `real_debt`(已被反驳/确权为真债)
- **位置:** `core/services/scheduler/gantt_service_support.py:32-51`(第二份);对照原版 `core/services/scheduler/gantt_critical_chain_provider.py:104-128`

```
# support 版 gantt_service_support.py:32-51
32	def _normalize_critical_chain_result(raw: Any) -> Dict[str, Any]:
...
48	        "available": bool(is_available),
50	        "reason_code": reason_code or ("unknown" if not is_available else ""),

# provider 版 gantt_critical_chain_provider.py:104-128(@staticmethod，3be4757f/2a6534ab 期已提交)
104	    def _normalize_critical_chain_result(raw: Any) -> Dict[str, Any]:
...
125	            "available": is_available,
127	            "reason_code": reason_code or ("unknown" if not is_available else ""),
```

- **引用链:**
  - 两份同名函数经 diff 语义逐字相同:`available` 布尔判定(support `is_available = available if isinstance(available, bool) else True` / provider 等价 `if isinstance(...): is_available = available else: is_available = True`)、`available` 时清空 `reason`/`reason_code`、`edge_type_stats` 默认四键 `{"process":0,"machine":0,"operator":0,"unknown":0}`、`edge_count` 的 `int(... or 0)` 兜底、`reason_code or 'unknown'` 兜底——完全一致。support 的 `_text(x)=str(value or "").strip()`(:10-11)即 provider 内联的 `str(x or "").strip()`,无差异。唯一字面差异:support 输出 `bool(is_available)`、provider 输出裸 `is_available`——但 `is_available` 必为 bool(要么通过 `isinstance(bool)` 校验、要么硬编码 `True`),`bool()` 是 no-op,**输出无差**。
  - 两份都活,汇入同一出口:`gantt_service.py:375` `critical_chain = critical_chain_for_plan_detail_filter(rows, detail_filters)`(support 路径,有 `detail_filters` 时)→ 内部 `gantt_service_support.py:58` 调 support 版归一;`gantt_service.py:377` `self._get_critical_chain_provider().get_critical_chain(...)`(provider 路径,无 filter 时)→ 内部调 provider 版归一。二者都流入 `gantt_service.py:389` `build_gantt_contract(...)` → `gantt_contract.py:19 _public_critical_chain` 再统一按 `:16 _ALLOWED_CRITICAL_REASON_CODES` 白名单复核 `reason_code`(:33)并映射中文标签——下游对两路产物一视同仁。
  - 两文件都已 `from .gantt_critical_chain import ...`(support.py:7、provider.py:10),存在**天然的公共 helper 落点**。

- **为何算债:** 同一概念(关键链结果归一)的第 2 套私有实现,两份逐字同义但物理分离,已具备语义漂移温床:任何一处改 `reason_code` 兜底规则或新增字段,另一处不会同步,前端契约会在 filtered/unfiltered 两条路径下不一致。属 P5"绕过已有实现重写"。重复本身**不护任何不变量**——归一调用对 support 路径确实承重(裸 `compute_critical_chain_from_rows` 缺 `available`/`edge_type_stats` 默认,`collect_gantt_degradation_events` 与 `_public_critical_chain` 依赖这些键),但**一份共享实现即可满足**,第二份物理副本不提供任何额外保证。

- **爆炸半径:** 若改:把 support 路径改为复用 provider 的归一(或抽到 `gantt_critical_chain` 公共函数),让两路共用单份。风险低但需同时覆盖 filtered/unfiltered 两条路径的快照测试。

- **处置建议 + 收口点(对抗验证给出的唯一安全做法):**
  - **收口到单份共享实现:** 把 `_normalize_critical_chain_result` 抽到两文件共享的 `core/services/scheduler/gantt_critical_chain.py`(两文件均已 import 该模块,落点天然),让 support 与 provider 两路都改调它(或 support `import` provider 的版本)。**保留归一调用本身**。
  - **绝不可** 把 `critical_chain_for_plan_detail_filter`(`gantt_service_support.py:54-58`)简化为直接 `return compute_critical_chain_from_rows` 的 raw——那会丢掉 `available` 默认 / `edge_type_stats` 四键 / `reason_code` 兜底,使坏数据/空结果以缺字段形态流入 `_public_critical_chain`(违反灵魂暗线"坏数据不准静默兜底",且可能让 `collect_gantt_degradation_events`(`gantt_service_support.py:61-80`,依赖 `available is False`)漏报降级)。
  - **统一后必跑:** `tests/regression_gantt_contract_snapshot.py`、`tests/regression_gantt_critical_chain_unavailable.py`、`tests/regression_gantt_critical_chain_provider.py`,验证 filtered/unfiltered 两路契约逐字不变。

- **复核结论:** ✅ 证据位置仍精确(support `:32-51`、provider `:104-128`、call sites `gantt_service.py:375/377/389` 全部逐字一致;两份归一语义复核仍逐字段相同)。**⚠️ 一处状态变化已落实:** 普查时 `gantt_service_support.py` 为新增**未提交**(git status `A`),对抗验证曾据此保留"疑为在途中间态,落手前先与在途作者确认"的前置。当前该文件已在提交 `b08162cd 完成报表工作台回跳验收` 中**提交入库**,工作区干净。**结论:在途疑虑消除,这是已固化进提交历史的 P5 真债,可按上述收口方案推进(无需再等在途作者),反而更应尽快统一以免两份在后续 feature 中各自漂移。**

---

### 债 3 ── 关键链 `_build_nodes` 静默丢弃坏时间行却仍报 `available:True`,无 partial/缺口信号

- **病理标签:** `P4`(静默兜底死角) · **严重度:** low · **load_bearing:** false(但内含一处**事实上承重的过滤行**,见下方醒目提示) · **对抗验证:** `real_debt`(已被反驳/确权为真债)
- **位置:** `core/services/scheduler/gantt_critical_chain.py:84`

```
79	def _build_nodes(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
80	    nodes: Dict[str, Dict[str, Any]] = {}
81	    for r in rows:
82	        st = _parse_dt(r.get("start_time"))
83	        et = _parse_dt(r.get("end_time"))
84	        if not st or not et or not (st < et):
85	            continue          # ← 静默跳过坏时间行,无任何 collector/counter/flag
```

- **引用链:**
  - `_build_nodes`(`gantt_critical_chain.py:79`)对 `if not st or not et or not (st < et): continue`(:84-85)**静默**跳过坏时间行。
  - 链路:`provider.get_critical_chain` → `compute_critical_chain`(`gantt_critical_chain.py:344`)→ `_load_rows`(:67-68 `schedule_repo.list_by_version_with_details(version)`,取**全版本不按周截断**)→ `_compute_critical_chain_from_loaded_rows`(:312)→ 内部调 `_build_nodes`(:313)丢行后,在 :328-334 仍返回带 `edge_type_stats`/`edge_count` 的**正常结果**(无 partial/dropped 字段),经归一包成 `available:True`。
  - 全文件 `grep -niE 'partial|dropped|skipped|degraded'`:**零命中**——丢了多少行无任何记录。
  - **对照同分区已有的"丢行但留痕"范式:**
    - `gantt_service.py:402-404`:overdue 标记有 `overdue_markers_degraded`/`overdue_markers_partial`/`overdue_markers_message` 三个透出字段。
    - `gantt_tasks.py:195-196`:`build_tasks` 对同款坏时间行(`if not st or not et or not (st < et):`)走 `_record_bad_time_row(collector, scope="gantt.tasks", row=...)` 入 `DegradationCollector`;并在 `:355` 当 `bad_time_row_skipped > 0` 时给出 `empty_reason`。这是**已确立的"丢行 + 留痕"政策**。
    - 本模块边级 `_eligible_process_edge`(:144,raise 在 :151)/`_eligible_resource_edge`(:155,raise 在 :160)对缺时间字段直接 `raise ValueError("...时间字段缺失。")`,且回归测试 `tests/regression_gantt_critical_chain_unavailable.py:215-248`(`test_critical_chain_edge_time_errors_do_not_drop_edges_silently`)断言"关键链边时间异常不应静默当成没有前驱边"(:248)。**证明节点级 `:84` 的静默是已立政策下的缺口,而非被接受的设计。**

- **为何算债:** 项目灵魂是"坏数据不准静默兜底、宁可暴露"。关键链已有 `available:False + reason` 的异常级降级通道,却对"部分行坏时间被剔除"这种**数据缺口零信号**:用户看到一条 `available:True` 的关键链,以为它是完整的,实际真正的瓶颈工序可能因时间损坏被悄悄排除,链路结论被污染而无人知。这是吞掉了本应让用户看见的数据缺口——同分区的 overdue 标记和 tasks 构建都已经留痕,唯独关键链丢行无声。

- **爆炸半径:** 若改:`_build_nodes` 计丢弃行数,经 reason / 新增 `partial`+`dropped_count` 字段透到契约。`Schedule` 表时间由持久化层上游 `NOT NULL` 校验(见下),正常态几乎不触发,改动主要是补防御性可观测;但 candidate/scenario 明细路径数据来源更松。属只读解释性覆盖层上的轻度盲点,非高危。

- **处置建议 + 收口点(对抗验证确权:是真债,可安全收口为兄弟范式,但不是裸删):**
  1. **必须保留 `:84` 的过滤条件本身**(见下方醒目提示)。正确做法是"丢行 + 留痕":照搬 `gantt_tasks` 的 `_record_bad_time_row` / `DegradationCollector`(收口到 `core/services/common/degradation`,与 tasks/calendar 共用同一 collector 出口),并新增 `critical_chain_partial` + `dropped_count`。
  2. **任何新增信号键必须同时穿过三道 whitelist 归一化**,否则在归一层被静默剥离 =换个地方自欺:① `gantt_service_support.py:32-51 _normalize_critical_chain_result`;② `gantt_critical_chain_provider.py:104-128 _normalize_critical_chain_result`;③ `gantt_contract.py:19-40 _public_critical_chain`。(注意:这三道里前两道正是债 2 的重复体——先收口债 2 成单份,再加 partial 键,可少改一处。)
  3. **优先级评估(先堵源头再补读侧):** 采纳/候选源为引擎写入且 `NOT NULL`(`schema.sql:240-241` Schedule、`:338-339` ScheduleCandidateRows、`:538-539` ScheduleAdjustmentScenarioRow 均 `start_time/end_time DATETIME NOT NULL`),`st < et` 几乎恒成立,丢行分支接近死代码;真正能产坏时间的是**人工 scenario 调整**路径——更应在 scenario 调整的**写入校验源头**堵 `st < et`,而非只在只读关键链读侧补 partial 标志。先确认写入源头是否已校验,再决定读侧补防御的投入。

> **🔧 醒目提示——`:84` 过滤行是事实上的承重护栏,需补"我是故意的"注释:**
> 虽然本 finding 的 `load_bearing=false`(缺的是 partial 信号),但**过滤行 `:84` 本身承重、绝不可裸删**:删掉它会让 `start/end=None` 流入 `_build_process_prev` 排序(`:114 items.sort(key=lambda x: (..., x.get("start"), ...))`)与 `_sink_id` 的 `max` 比较(`:262 max(nodes.values(), key=lambda x: (x.get("end"), ...))`)→ Py3.8 下 `None` 与 `datetime` 比较抛 `TypeError` → 被 `:340`/`:358` 的 `try/except` 接住 → 整条关键链因一行坏数据降为 `available:False`(过度激进、功能回归)。这一行是"丢一行坏数据仍出有用链"的刻意韧性。建议落注释:
> ```python
> # 我是故意的(承重):此过滤刻意"丢坏时间行仍出链",不可裸删。
> # 删除会让 None 流入 :114 排序与 :262 max 比较→Py3.8 TypeError→被 :340/:358 接住→
> # 整链降为 available:False(一行坏数据毁全链,功能回归)。
> # 已知缺口:丢行未留痕,违反"坏数据不准静默兜底"——收口方向是 +DegradationCollector
> # 与 critical_chain_partial/dropped_count,而非删此行。详见普查报告 03 分区债 3。
> ```

- **复核结论:** ✅ 主证据仍精确。`gantt_critical_chain.py:84` 过滤行逐字一致;全文件仍无 `partial/dropped/skipped/degraded`;`_compute_critical_chain_from_loaded_rows`(:312-334)丢行后返回正常结果不变;承重的排序/max 点 `:114`/`:262` 逐字一致;`gantt_contract.py:19/33` 白名单复核、`gantt_service.py:402-404` overdue 兄弟范式、`schema.sql:240-241/338-339/538-539` NOT NULL、`tests/regression_gantt_critical_chain_unavailable.py:215-248` 断言全部精确命中。**⚠️ 唯一行号偏移:** 兄弟范式交叉引用的 `gantt_tasks.py` 已较普查时 +4 行——`_record_bad_time_row` 守卫由原 `:192` 移至 **`:195-196`**、`bad_time_row_skipped` 判定由原 `:351` 移至 **`:355`**(模式与定性不变,仅行号位移)。该偏移仅影响"对照范式"的指针,不影响本债主证据 `:84`,定性维持 P4 真债。

---

## 04 · 分区【scheduler-exec-diag】执行事实与诊断

> 覆盖 `operation_execution_*` / `execution_fact_provider` / `execution_snapshot` / `schedule_delay_diagnosis_*` / `operation_execution_feedback_service`(9 文件)。

> **分区健康一句话**:**地基扎实,残渣集中在边角**。承重骨架很硬——`OperationExecutionEvents` 有 schema 级 CHECK + NOT NULL + 唯一索引契约(`migration_operation_execution_contract` 还带坏值探针)、写入幂等 + 乐观锁(state_revision)、dashboard 读现场事实失败会把错误抛到页面(符合"不自欺"灵魂)。问题集中在两类:(1) 一层"被 DB 不变量架空的死防御"(reported_status 兜底表、死键),都因 schema 约束永不触发;(2) 一组 specced-but-prod-unwired 的公开 API(延期诊断三件套)只剩契约测试 + roadmap 续命。**唯一危险的是写侧 adopted-only 护栏(P2)缺注释**(详见 §90 LB-A3)。无 P1 假冒计算值,无活跃 P4 静默吞错。

> 本分区 9 条:1 条承重护栏(P2,已在 §90 详述)、2 条 P3 半截迁移、2 条 P5 私有实现、4 条 P6 死面包屑。

---

### 4.1 【P2 · high · load_bearing=TRUE】⚠️承重护栏:现场反馈写侧 adopted-only 硬拒 + 写死消毒,无注释保护

**位置**:`core/services/scheduler/operation_execution_feedback_service.py:347-356`(硬拒)+ `:451-453`(写死消毒)

> **本条是承重护栏,完整论述见 §90 LB-A3**(execution_review「只复盘正式采用方案」纵深防御 4 处之一——写侧那一处)。此处只记要点。

- **守的不变量**:现场反馈只能写在当前正式采用方案上,禁止预览/scenario 冒充正式现场记录。
- **不对称实锤**:对照延期诊断**读**服务 `_resolve_strict_plan`(`schedule_delay_diagnosis_service.py:137-138`)是 `resolve_plan_view` 接受 scenario_key 的——**读可带 scenario,写禁带 scenario**,这是刻意的读写不对称。三重护栏:路由 `_identity_allows_query_membership_check` + 此处校验 + schema CHECK(`source_table='schedule'`/`effective_plan_role='adopted'`/`scenario_id is null`)。
- **删了会炸什么**:把 `_build_event_payload` 三个写死常量改成透传 context、或删 `:347-356` 拒绝分支,现场反馈可被写到候选方案/scenario 预览上,污染"正式采用方案"的现场执行事实;下游重排护栏(`schedule_execution_guardrails` 读 `ExecutionFact`)会把预览态当真实现场,坏数据进排产决策。
- **复核结论**:✅ 证据仍准(`:347-356,451-453` 当前 HEAD `b08162cd` 已复核,行号一致;grep 注释仍零命中)。
- **🔧 该补注释**:见 §90 LB-A3 逐字文案。

---

### 4.2 【P6 · medium】ExecutionFact 两死字段,拖着一次每调必跑的无用 DB 查询

**位置**:`core/services/scheduler/execution_fact_provider.py:20-21`(字段定义)`,42-43`(赋值)`,96`(死查询)

**引用链**
- 字段 `last_event_schedule_version`/`last_event_schedule_id` 定义 `:20-21`、赋值 `:42-43`(来自 `latest.schedule_version/schedule_id`)。
- grep 全仓(core/web/data/tests)除定义/赋值外**零命中**——连测试都不读。
- 赋值来源链:`list_by_op_ids:96` 调 `event_repo.list_latest_events_by_op_ids(ids)`;而 `_fact_from_state` 里 `latest` 参数**仅**用于这两个死字段(`:42-43`),`ExecutionFact` 其余字段全部来自 `state`(`aggregate_states_by_op_ids`)。
- `list_latest_events_by_op_ids`(repo:254)的生产唯一调用方就是 `:96`。
- 真实消费方(schedule_execution_guardrails/persistence_guard/gantt_tasks/dashboard_workbench/gantt_adjustment_publish_service)只读 actual_status/actual_start_time/actual_end_time/actual_machine_id/actual_operator_id/op_id/state_revision。

**为何算债**:两字段被算出来后永无人读;唯一存在意义是触发 `list_latest_events_by_op_ids` 这次额外全事件查询(每次 `list_by_op_ids` 都跑)。死面包屑 + 被它吊住的死查询。

**爆炸半径**:删两字段 + 不再调 `list_latest_events_by_op_ids`(其本身也仅 `:96` 调用,连带死),零生产消费方受影响。误判风险低——已 grep 实证连测试都不读。

**处置**:删字段 + 连带删 `list_latest_events_by_op_ids`。属真债清理册第二档(#14)。

**复核结论**:⚠️ 涉及 report/gantt 上游消费方,b08162cd 改过 gantt_tasks,动手前重新 grep 两字段确认仍零读取。

---

### 4.3 【P3 · medium】延期诊断公开 API 三件套 prod-unwired

**位置**:`core/services/scheduler/schedule_delay_diagnosis_service.py:42-54,114-139`(`diagnose_plan_overdue`/`diagnose_batch`/`_resolve_strict_plan`)

**引用链**
- 生产入口 `report_engine.py:200,213` 都只调 `diagnose_resolved_plan_overdue`(传入已解析好的 resolution)。
- grep 全 web/core/data:`diagnose_plan_overdue` 生产零调用(仅本文件 `:122` 被 `diagnose_batch` 调),`diagnose_batch` 生产零调用,`_resolve_strict_plan`(`:134`)唯一调用方是 `diagnose_plan_overdue`(`:49`)。
- 即:三者构成一个**生产不可达的自洽子图**。
- 续命来源:`tests/regression_scheduler_delay_diagnosis_contract.py:262/332/349/362/382` + **roadmap `aps-three-gap-directions`(当前分支)`roadmap.md:492`** 把 `diagnose_batch` 列为公开 API 签名、`items.yaml:83` exit_checks 引用两者。
- git:二者生于 `f5f2f1ea`(第2阶段诊断核心服务),`diagnose_resolved_plan_overdue` 后在 `a0cfa3e7` 加入并成为实际生产门。

**为何算债**:specced-and-built 的公开 API,但 UI/report 层改走 `diagnose_resolved_plan_overdue`(自解析 resolution),把带 plan_role/scenario 自解析的 `diagnose_plan_overdue`/`diagnose_batch` 晾在一边。是迁移到 resolved 入口后没收尾的旧入口,**还是有意保留供未来/外部调用的契约 API——需裁决**。

**爆炸半径**:若当残渣删,会破坏 contract 测试多个用例,并与 `aps-three-gap-directions` roadmap 文档化的公开 API 契约冲突。**删前必须先确认 roadmap 是否仍把它当对外契约**——属真债清理册第六档(需先协调)。

**复核结论**:⚠️ **当前分支就是 `aps-three-gap-directions`**——这组 API 是本分支 roadmap 的在途契约,**现阶段不应删**,标"在途"而非"残渣"。

---

### 4.4 【P5 · medium】datetime 解析私造 3 份,绕过 strict_parse 收口点且语义漂移

**位置**:`execution_fact_provider.py:66` / `operation_execution_feedback_support.py:226` / `data/repositories/operation_execution_state_builder.py:42`

**引用链**
- 已知收口点 `core/shared/strict_parse` 提供 `parse_required_datetime(:113)`/`parse_optional_datetime(:127)`,内部正是 `str.strip().replace('/','-').replace('T',' ').replace('：',':')` + 对 `('%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M','%Y-%m-%d')` 循环 strptime。
- 分区内三处各自重写同一套:`_parse_execution_time`(provider:66-76,失败 **return None**)、`_parse_feedback_datetime`(support:226-233,失败 **raise** `_invalid_field_value`)、`_parse_time`(state_builder:42-55,先 fromisoformat 再循环,失败 **return None**)。
- grep 实证三者均未 import strict_parse。

**为何算债**:同一"解析现场时间字符串"职责有统一收口点,却私造三遍**并已语义漂移**:写校验链(`_parse_feedback_datetime`)对坏时间抛错(符合不自欺),而 provider/state_builder 两份对坏时间静默返回 None。同一概念三套口径,其中两套的静默 None 与灵魂原则相左(虽因上游约束当前不易触发)。

**爆炸半径**:改为统一调 strict_parse 需逐处对齐错误语义——provider/state_builder 当前靠 None 表达"无时间"是合法语义,不能简单换成抛错版;收口时若不分清 required vs optional 会把"正常缺时间"误判成错误。中等改造面。属真债清理册第四档(#33,语义需逐处对齐)。

**复核结论**:✅ 证据仍准(provider/support/state_builder 未被 b08162cd 改动)。

---

### 4.5 【P5 · low】positive-op-id 过滤:provider/repo 各私造一份且漂移(公开排序/私有不排序)

**位置**:`execution_snapshot.py:27`(public)vs `execution_fact_provider.py:51` vs `operation_execution_event_repo.py:63`

**引用链**
- `snapshot.positive_op_ids`(`:27`)是 public 且进 `__all__`(`:70`),逻辑 = int 化 + 去重 + **`return sorted(out)`**。
- `provider._positive_op_ids`(`:51`)同逻辑但 **`return out`(不排序)**;`repo._positive_ids`(`:63`)同逻辑也不排序。
- grep 实证 provider/repo 未 import `snapshot.positive_op_ids`,各用私有版。

**为何算债**:已有导出的公共 `positive_op_ids`,另两处不复用而私造,且**语义漂移**(是否排序)。漂移可能引入隐蔽 bug:依赖顺序的下游(如 `execution_snapshot` 的 sha256 指纹按 ids 顺序拼接)必须用排序版,而 provider/repo 的不排序版若被误用于指纹会得到不同 digest。

**爆炸半径**:收口为单一实现时必须保留"排序"语义给 snapshot(指纹稳定性依赖它);provider/list_by_op_ids 当前按入参顺序产 facts——强行换排序版会改变 facts 返回顺序,需确认无下游依赖原顺序。低-中。属真债清理册第四档(#34)。

**复核结论**:✅ 证据仍准。

---

### 4.6 【P6 · low】reported_status 兜底映射表 + or 右支,被 schema 不变量架空永不触发

**位置**:`data/repositories/operation_execution_state_builder.py:33-39`(表)`,76-79`(or 右支)

**引用链**
- `_current_status:77` = `last_event.reported_status or _REPORTED_STATUS_BY_EVENT_TYPE.get(last_event.event_type, EXECUTION_STATUS_NOT_STARTED)`。
- 追 `reported_status` 来源:`OperationExecutionEvent.from_row`(`operation_execution_event.py:95`)`reported_status=str(get(row,'reported_status') or '')`,行来自 DB。
- `migration_operation_execution_contract.py` 把 reported_status 列入 `_OPERATION_EXECUTION_REQUIRED_NOT_NULL_COLUMNS`(`:172`)且 CHECK `reported_status in ('processing','paused','exception','completed')`(`:140`),坏值探针 `:264` 实证拒绝 'finished'。
- 故每条持久化事件 reported_status 恒为四非空合法值之一 → `or` 右支**永不求值** → 整张 `_REPORTED_STATUS_BY_EVENT_TYPE` 死。

**为何算债**:一张看着在用、实则被 DB CHECK + NOT NULL 完全架空的兜底映射 + 一条不可达 or 分支。死面包屑——制造"状态映射有两处真值来源"的假象(真值来源只有写入侧 `_REPORTED_STATUS_BY_ACTION`)。

**爆炸半径**:删表 + `:77` 简化为直接用 reported_status,仅当未来有人绕过 repo 直接构造无 reported_status 的事件才会暴露(但那条路径同样被 schema 拒)。极低。属真债清理册第二档(#21)。

**复核结论**:✅ 证据仍准。

---

### 4.7 【P6 · low】`_REPORTED_STATUS_BY_ACTION` 的 EXCEPTION 死键 + 死导入

**位置**:`operation_execution_feedback_support.py:64` + `operation_execution_feedback_service.py:12,455`

**引用链**
- `_REPORTED_STATUS_BY_ACTION`(support:59-66)同含 `EXECUTION_EVENT_EXCEPTION('exception')` 与 `EXECUTION_ACTION_REPORT_EXCEPTION('report_exception')` 两键。
- 但 `_normalize_action`(service:247-248)= `event_type_to_action(action_to_event_type(text))`,经验证(`labels.py:91-102`)无论输入 'exception' 还是 'report_exception' 恒归一为 'report_exception';`:249` 成员校验与 `:455` 索引用的都是归一后 action,故 'exception' 键**永不被命中**。
- `EXECUTION_EVENT_EXCEPTION` 导入 `service.py:12`,grep body 内零使用(`:278` 用的是 PAUSE+REPORT_EXCEPTION)。

**为何算债**:写后永不读的字典键 + 导入后永不用的符号。死面包屑,让映射表看起来比实际多覆盖一个分支。

**爆炸半径**:删 'exception' 键 + 死导入,零行为影响(已证不可达)。极低。属真债清理册第二档(#22)。

**复核结论**:✅ 证据仍准。

---

### 4.8 【P6 · low】`list_latest_exception_events_by_op_ids` 生产零调用,仅测试续命

**位置**:`data/repositories/operation_execution_event_repo.py:260-265`

**引用链**:方法定义 `:260`。grep 全 web/core/data 除定义外**零命中**;唯一引用 `tests/regression_operation_execution_event_foundation.py:173`。最新异常态的真实生产来源是 `state_builder._latest_exception`(`:91`) + `OperationExecutionState.latest_exception_*` 字段,不经此方法。

**为何算债**:公开 repo 方法被造出但生产无人调,仅靠基础回归测试续命。死代码(已 grep 实证)。

**爆炸半径**:删除需同步删 `regression_operation_execution_event_foundation.py:173` 一行断言。低。属真债清理册第二档(#15)。

**复核结论**:✅ 证据仍准。

---

### 4.9 【P3 · low】service 层 `operation_execution_labels.py` 是 model 同名模块的纯转出垫片

**位置**:`core/services/scheduler/operation_execution_labels.py:1-36`

**引用链**
- 全文件 35 行:从 `core.models.operation_execution_labels` import 15 个符号,`__all__` 再原样导出同 15 个,**无任何新定义/封装/适配**。
- 导入方:`feedback_service.py:48`、`feedback_support.py:26`、`routes:16`、两个测试。
- 对照同分区 `gantt_tasks.py`、`state_builder.py`、`scheduler_resource_dispatch_execution.py` 全部**直接** `from core.models.operation_execution_labels import ...`——绕过此垫片。
- git:生于 `5e1617ec`(第8项执行事件基础)。

**为何算债**:一层不做任何事的 re-export 垫片;且"是否走垫片"在分区内不一致(一半直连 model、一半经垫片),说明它不是被贯彻的服务边界门面,而是半截留下的转发层。

**爆炸半径**:删垫片改 5 个导入方直连 model,行为零影响;但若团队有意以"service 不直接 import model 标签"为约定则会破坏该约定(然而现状已大量直连,约定并未贯彻)。需裁决是收编为统一门面还是删除。低。属真债清理册第三档(#27)。

**复核结论**:✅ 证据仍准。

---

### 本分区小结

| 条 | 病理 | 位置 | 性质 | 复核 |
|---|---|---|---|---|
| 4.1 | P2(LB) | feedback_service.py:347-356,451-453 | 承重护栏(见§90) | ✅ 注释仍缺 |
| 4.2 | P6 | execution_fact_provider.py:20-21,96 | 死字段+死查询 | ⚠️ 重 grep |
| 4.3 | P3 | schedule_delay_diagnosis_service.py:42-54 | **本分支 roadmap 在途契约,勿删** | ⚠️ 在途 |
| 4.4 | P5 | provider/support/state_builder datetime ×3 | 私造+语义漂移 | ✅ |
| 4.5 | P5 | positive_op_ids ×3 | 私造+排序漂移 | ✅ |
| 4.6 | P6 | state_builder.py:33-39,76-79 | schema 架空的死防御 | ✅ |
| 4.7 | P6 | feedback_support.py:64 + service.py:12 | 死键+死导入 | ✅ |
| 4.8 | P6 | event_repo.py:260-265 | 测试续命死方法 | ✅ |
| 4.9 | P3 | operation_execution_labels.py:1-36 | 纯转出垫片 | ✅ |

**要点**:本分区地基由 schema CHECK + 乐观锁 + 启动期 contract probe 三重锁死,大量"死防御"恰恰是因为 DB 不变量太硬而被架空——这是健康的过度防御,不是坏味道。唯一需要人工动作的是 4.1 补注释(§90)和 4.3 确认在途状态。

---

## 05 · 分区【scheduler-plan-identity】方案身份解析核心(version_resolution / plan_query)

> **分区健康一句话**：有残渣、非重灾。任务预设的两大重灾点已被治理(被点名的 P1 `ADOPTED_PLAN_RESOLUTION` 常量假冒已彻底删除、`execution_review` 改走真解析;canonical P2 `execution_review` 只复盘 adopted 的承重不对称已被 UI 文案 + disabled 原因 + 导航强制 + 合同测试四层护住)。核心解析链(`schedule_plan_query_service` / `schedule_plan_identity_builder` / `schedule_plan_query_repo`)本身干净:`plan_id` 全链零真实消费,坏数据多处主动抛错(`build_plan_identity` 空 source 即抛、repo `_require_candidate_id` / `_require_scenario_id` 抛、`normalize_plan_role` 非法 role 抛)。真正水下的剩余债共 5 条:1 条承重护栏缺改动点本地注释(P2,load_bearing)、1 条死兼容 shim(P3)、1 条手搓双 dict 私实现无 parity 测试(P5)、1 条身份计算里静默吞坏 JSON(P4,load_bearing 但低危)、1 条 `_normalize_role` 字节级副本(P5 小)。

**复核口径说明**：本分区 5 条全部回到当前 `codex/aps-three-gap-directions` 分支代码逐条 grep/Read 复核。多数文件未被修复 agent 改动,行号仍准;个别条目原证据里写的是裸文件名(未带目录)或键数有 ±1 偏差,已在各条"复核结论"里如实订正。**审计期间未改动任何代码文件。**

---

### 5.1 【P3 · medium · load_bearing=false】gantt_plan_query 收口迁移后遗留的死兼容 shim

**位置**
- `core/services/scheduler/gantt_plan_query.py:32` `default_plan_resolution_dict`(透传到 `_default_plan_resolution_dict`,外加遗留错误文案包装)
- `core/services/scheduler/gantt_plan_query.py:42` `resolve_plan`(纯透传 `_resolve_plan`)
- `core/services/scheduler/gantt_plan_query.py:46` `selected_plan_role`(纯透传 `_selected_plan_role`)
- `core/services/scheduler/gantt_plan_query.py:59` `_has_explicit_gantt_range`(纯透传 `_has_explicit_display_range`)

**引用链(迁移已完成、wrapper 已死的实证)**
- 历史:`git 4428c75a` 时 `resolve_plan` / `selected_plan_role` 原定义在 `gantt_plan_query`;`git 35b3c138` 提交说明明写"把…解析规则收口到 `schedule_result_view_context`。保留 `gantt_plan_query` 的兼容 wrapper,老调用方不用一次性迁移"。
- 这 4 个符号自此变成对 `schedule_result_view_context` 的纯透传(见 `gantt_plan_query.py:11-19` 的 `as _xxx` 别名导入)。
- 全仓实证迁移已完成、wrapper 已死:
  - `gantt_plan_query.resolve_plan`、`gantt_plan_query.selected_plan_role`:全仓(含 tests)0 个走 `gantt_plan_query.` 模块路径的引用。真正存活的 `selected_plan_role` 调用方(`gantt_critical_chain_provider.py:12,152`、`gantt_service.py:34,325,345`、`scheduler_gantt.py:29,298`、`scheduler_week_plan.py:37,337`)**全部直接 import 自 `schedule_result_view_context`,绕过本 shim**。
  - `default_plan_resolution_dict` 的 `gantt_plan_query` 模块路径:仅 `tests/regression_schedule_result_view_context.py:295,298` 一条测试续命(`gantt_plan_query.default_plan_resolution_dict("bad")`)。其余 5 处生产调用(`gantt_critical_chain_provider.py:141`、`gantt_service.py:167`、`scheduler_navigation_publish.py:69`、`scheduler_week_plan.py:74`、`report_plan_preview.py:37`)均直引 `schedule_result_view_context`。
  - `_has_explicit_gantt_range`:全仓 0 caller(仅 `gantt_plan_query.py:59` 的 `def` 本身)。
- 关键对照:`gantt_service.py:12-17` 从 `gantt_plan_query` import 的是**另外 4 个 range 辅助函数**(`attach_gantt_range_metadata` / `build_empty_week_plan_payload` / `get_version_time_span_dates` / `resolve_gantt_range_for_version`),它们仍是 `gantt_service` 真用的活函数;而 `default_plan_resolution_dict` / `selected_plan_role` 它在 `gantt_service.py:29-35` 是从 `schedule_result_view_context` 直引的,**没走 shim**。

**为何算债**
迁移做了一半:"收口到 view_context" + "迁移老调用方直引 view_context"两步都完成了,但收口后留下的空壳 shim 没删,留下 4 个零生产消费的"假在用"符号(其中 `default_plan_resolution_dict` 还靠 1 条测试人工续命),制造 `gantt_plan_query` 仍是解析入口的假象。属 P3 半截迁移残渣。

**爆炸半径**
删除这 4 个死符号(及 `regression_schedule_result_view_context.py:294-298` 那条仅测 wrapper 透传/遗留文案行为的测试)安全;但 **`gantt_plan_query.py` 文件整体不可删**——它还有 4 个被 `gantt_service` 真用的 range 辅助函数(`get_version_time_span_dates` / `resolve_gantt_range_for_version` / `attach_gantt_range_metadata` / `build_empty_week_plan_payload`)。若误判"整模块死"而删文件,会直接打断甘特周计划范围解析。

**处置建议**
删除 `gantt_plan_query.py:32-47` 的 `default_plan_resolution_dict` / `resolve_plan` / `selected_plan_role` 三个透传 wrapper,以及 `:59-71` 的 `_has_explicit_gantt_range`;同步删 `:11-19,23-25` 对应的 `as _xxx` 别名导入。收口到的统一点已存在:`schedule_result_view_context`(`default_plan_resolution_dict`@73、`resolve_plan`@~190、`selected_plan_role`@201)与 `schedule_result_view_range.has_explicit_display_range`。**⚠️ 删 `default_plan_resolution_dict` wrapper 前须先迁移它身上那段"遗留错误文案包装"**(`gantt_plan_query.py:35-38`,把 `ValidationError` 的 `plan_role` 报错重写成历史文案"未知的排产方案角色:{role}")——若有调用方依赖这条特定中文文案,需把它移到 `normalize_plan_role` 或上游;否则删 wrapper 会改变错误文案。F5 的处置说明也明确要求"务必保留 `gantt_plan_query.py:32-38` 的遗留错误文案包装"。

**复核结论**：✅ 证据仍准。`gantt_plan_query.py` 当前未被改动,4 个死符号行号与原证据 `42,46,32,59` 完全一致。grep 复证:`selected_plan_role` 全仓调用方均直引 `schedule_result_view_context`、`_has_explicit_gantt_range` 0 caller、`default_plan_resolution_dict` 走 `gantt_plan_query` 路径的唯一引用仍是 `regression_schedule_result_view_context.py:298`。

---

### 5.2 【P2 · medium · load_bearing=TRUE】⚠️承重护栏:execution_review 服务方法写死 ROLE_ADOPTED/scenario_id=None 的不对称,改动点本体无注释保护

**位置**
- `core/services/report/execution_review.py:141-150` `execution_review(version, *, date_from, date_to, batch_id, resource_type, resource_id)` —— **形参刻意不收 `plan_role` / `scenario_id`**
- `core/services/report/execution_review.py:153` 方法体内恒 `resolution = host._resolve_plan(v, ROLE_ADOPTED, None)`
- `core/services/report/execution_review.py:112,114` `_execution_review_plan_rows` 走 between 分支恒 `plan_role=ROLE_ADOPTED, scenario_id=None`
- `core/services/report/execution_review.py:123,125` 走 all 分支同样恒 `plan_role=ROLE_ADOPTED, scenario_id=None`
- `core/services/report/execution_review.py:166-167` 返回 dict 恒 `plan_label=plan_role_label(ROLE_ADOPTED), plan_role=ROLE_ADOPTED`

**引用链(不对称的实锤 + 护栏分布在四层远处)**
- **不对称对照**:同属 `ReportEngine` 的 sibling 报表方法全部签名带 `plan_role` + `scenario_id` 并透传:`report_engine.py:157` `overdue_batches(self, version, plan_role=None, scenario_id=None, ...)`、`:267` `utilization(...)`、`:371` `downtime_impact(...)`。已逐个读证:`overdue_batches` 在 `:168` `self._resolve_plan(v, plan_role, scenario_id)`、`:169-176` 把 `plan_role/scenario_id` 透传进 `_fetch_overdue_base_rows_for_plan`。**唯独 `execution_review`(:141) 拒带这两个形参。**
- **取数源真会随 role/scenario 改变(护栏不是装饰)**:`schedule_plan_query_service.py` 的 `resolve_plan_view` 中 `scenario_id` 非空即转 `_resolve_scenario_plan` → 返回 `source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS`、`is_scenario_preview=True`;非 adopted role 选不同 `candidate_id` / `source_table`。`report_plan_helpers.py:56` `_list_plan_rows_between` / `:83` `_list_plan_rows_all` 把 `plan_role/scenario_id` 透传进 detail 取数,FROM 解析出的 `source_table/candidate_id` 决定取哪张表的行——所以 `execution_review` 写死 adopted 是数据层最后一道把关。
- **护栏的"理由"分布在四层远处(都不在改动点本地)**:
  1. 导航强制:`web/navigation_context.py:80-82` —— `is_execution_review` 为真时 `plan_role = ROLE_ADOPTED`、`scenario_id = ""`,把执行复盘请求的 role/scenario 强制清成 adopted。
  2. 入口禁用:`web/viewmodels/scheduler_workbench_links.py:271` `_is_formal_adopted_context`、`:310-311` `if target_page == "execution_review" and not _is_formal_adopted_context(context): return "计划和现场实际只复盘正式采用方案,请切换到正式采用方案后查看。"`;`:267` context_summary 追加"只复盘正式采用方案"。
  3. 用户文案:`web/viewmodels/scheduler_reports_workbench.py:210` "只复盘正式采用方案,不复盘模拟预览和对比参考方案。"
  4. 合同测试钉死:`tests/regression_reports_workbench_backlink_contract.py:266` `test_execution_review_stays_formal_and_links_to_site_record_entry`、`:347` `test_non_adopted_report_nav_disables_execution_review_link`;另有 `regression_reports_workbench_navigation_contract.py:274,450`、`regression_scheduler_workbench_link_guardrails.py:105,128`、`regression_scheduler_workbench_links_contract.py:300`、`regression_plan_vs_actual_review.py:356`、`regression_workbench_nav_entry_contract.py:172` 多处断言"只复盘正式采用方案"。

**为何算债**
这是任务点名的 canonical P2:`execution_review` 刻意拒带 `plan_role`/`scenario_id`,以防模拟预览 / 对比参考方案冒充正式现场复盘——**承重**(删了会让模拟预览数据混入正式现场复盘并可导出)。护栏在 UI / 导航 / 用户文案 / 测试四层都有,但 `execution_review.py:141` 这个**发生不对称的服务方法本体没有任何 inline 注释**说明"我故意和 overdue/utilization/downtime 不一样"。未来 LLM 以"与同类报表方法保持一致"名义给 `execution_review` 补 `plan_role` 形参时,在改动点本地看不到任何阻止信号——这正是承重护栏无注释的典型隐患。

**爆炸半径**
若给 `execution_review` 补 `plan_role`/`scenario_id` 透传:模拟预览 / 对比参考方案的计划时间会和正式现场反馈拼成"计划 vs 实际"复盘并可经 `export_execution_review_xlsx`(`execution_review.py:178-219`)导出,污染唯一可信的正式复盘口径。返回 dict(`:164-176`)既不携带也不拦截 `is_scenario_preview`,预览行会**静默**拼进结果,违背灵魂暗线"坏数据/预览不可静默冒充正式"。链接生成 / 导航类合同测试会拦住一部分入口,但**服务层契约本身已被破坏**——当前全仓无任何测试 `GET /reports/execution-review?plan_role=<非adopted>&scenario_id=X` 并断言服务端回退 adopted,这是最大缺口。

**处置建议(收口到哪个统一点 + 该补的"我是故意的"注释)**
本条**首选不动逻辑、只补防御**。统一点就是 `execution_review` 自身写死 adopted 这一行为,需要做的是把分散在四层的"理由"钉回改动点本地:

1. **(最小、强烈建议立即做)在 `execution_review.py:141` 签名处补 inline 注释**,文案建议:
   > ```python
   > def execution_review(
   >     self,
   >     version: int,
   >     *,
   >     date_from: Any = None,
   >     date_to: Any = None,
   >     batch_id: Any = None,
   >     resource_type: Any = None,
   >     resource_id: Any = None,
   > ) -> Dict[str, Any]:
   >     # 【故意】本方法只复盘 ROLE_ADOPTED(正式采用方案),刻意不收/不透传 plan_role、
   >     # scenario_id —— 与 sibling overdue_batches/utilization/downtime_impact 的不对称是
   >     # 设计而非疏漏。原因:计划-现场实际复盘只对"正式采用方案"成立,若放开 role/scenario,
   >     # 模拟预览(SOURCE_ADJUSTMENT_SCENARIO_ROWS, is_scenario_preview=True)与对比参考方案
   >     # 的计划时间会被拼进"计划 vs 实际"并导出,冒充正式现场复盘、污染唯一可信口径。
   >     # 护栏分布:navigation_context.py:80-82 强制 adopted、scheduler_workbench_links.py:310-311
   >     # 禁用非 adopted 入口、reports_workbench.py:210 用户文案、backlink/navigation 合同测试。
   >     # 若确需放开,改动前必须先满足下方"放开前置条件"三件套(见审计报告 5.2)。
   > ```
   并在 `:112,114,123,125` 写死 `plan_role=ROLE_ADOPTED, scenario_id=None` 处补一行短注释 `# 故意写死 adopted,见 execution_review() 顶部说明`。

2. **(若未来真要放开,对抗验证给出的硬前置条件,缺一不可)**
   - (a) 在取数边界保留强制 adopted:要么继续写死,要么加 service 层断言——`execution_review` 收到非 adopted role 或任何 `scenario_id` 时 `raise ValidationError`(loud,**不得静默回退**),并在返回前校验 `resolution.is_scenario_preview is False`。
   - (b) **新增请求级合同测试(当前最大缺口)**:`client.get('/reports/execution-review?version=..&plan_role=baseline_best&scenario_id=..')` 断言返回 rows 与 `plan_role` 仍为正式采用方案、导出 xlsx 不含预览/对比数据。当前全仓只有 `backlink:355` 一条负向 `assert(... not in html_text)`,无任何服务端回退断言。
   - (c) 同时把 `web/routes/reports_page_support.py`(执行复盘路由自身亦写死 adopted、从不读 request 的 plan_role/scenario_id)与 export 路由接上请求值——注意 sibling 路由 `reports_page_support.py` 用 `request_plan_role()`,证明"与同类对齐"的统一压力真实存在。

**复核结论**：✅ 证据仍准(行号精确)。`execution_review.py` 当前已是 git modified,但复核确认写死点仍在原行:`:153` `host._resolve_plan(v, ROLE_ADOPTED, None)`、`:112/114` 与 `:123/125` 的 `plan_role=ROLE_ADOPTED, scenario_id=None`、`:166-167` 返回值;形参(`:141-150`)仍不收 `plan_role`/`scenario_id`,本体仍无任何 inline 注释。sibling 不对称已复证:`report_engine.py:157 overdue_batches` 形参带 `plan_role/scenario_id` 且 `:168` 透传。两条 backlink 合同测试名仍在(`:266` / `:347`)。唯一需订正的引用细节:原证据写"`navigation_context.py:80-82`"为**裸文件名**,实际路径是 **`web/navigation_context.py:80-82`**(内容一致)。

---

### 5.3 【P5 · medium · load_bearing=false】default_plan_resolution_dict 手搓 plan_identity + resolution 双私有实现,绕过 build_plan_identity / SchedulePlanResolution.to_dict,且无 parity 测试

**位置**
- `core/services/scheduler/schedule_result_view_context.py:77-100` 手搓 `plan_identity` dict(22 键)
- `core/services/scheduler/schedule_result_view_context.py:101-147` 外层 resolution dict
- 调用点:`schedule_result_view_context.py:440`(`no_history` 路径)与 `:448`(`missing_history` 路径)各 `plan_resolution=default_plan_resolution_dict(raw_plan_role)`

**引用链**
- canonical 身份产出口:`build_plan_identity`(`schedule_plan_identity_builder.py:123`)→ `PlanIdentity.to_dict`(`core/models/schedule_plan_identity.py:44`)。
- canonical 外层 resolution 产出:`SchedulePlanResolution.to_dict`(`core/models/schedule_plan_resolution.py:64`)。
- `default_plan_resolution_dict` 在 `no_history`/`missing_history` 两条路径手工拼出同形状的两个 dict,而不委托上述 canonical。
- **"无法委托"理由(对抗验证已推翻)**:`schedule_plan_identity_builder.py:145-146` 对空 `source_table` 主动抛"计划身份缺少有效的数据来源";但该抛错只在 `source ∉ {schedule, candidate_rows, adjustment_scenario_rows}` 时触发。而本占位手搓 dict 的 `source_table` **写死为 `SOURCE_SCHEDULE="schedule"`**(`view_context.py:82` 内层、`:107` 外层),并非空来源 → 走 `build_plan_identity(version=None, source_table='schedule', ...)` 可通过,**今日委托即零差异**。
- **键集核验**:`PlanIdentity.to_dict`(`schedule_plan_identity.py:44-67`)与手搓 `plan_identity`(`view_context.py:77-100`)逐键对齐(今日 0 漂移)。但 grep 实证 `tests/regression_schedule_result_view_context.py` 中 **`build_plan_identity` 出现 0 次**(已 `git grep -c` 复证),即**无任何断言两者键集/取值一致的 parity 测试**。
- **手搓外层反而是 canonical 的子集**:`schedule_plan_resolution.py:64-103` 的 canonical 外层 `to_dict` 是手搓外层的超集——手搓侧缺 `schedule_result_status` / `schedule_lock_status` / `detail_saved` 三键(这三键下游均 `.get()` 读取,无害)。它已非忠实的第二实现,靠"缺键"先一步偏离。

**为何算债**
同一"计划身份 / 解析结果"概念的第二套私有构造,与统一收口点(`build_plan_identity` + `SchedulePlanResolution.to_dict`)并存。今日键集恰好对齐属侥幸——一旦 `PlanIdentity` 增删字段,canonical 侧自动跟随、手搓侧不会,且无测试报警。下游 `plan_role_filter_fields` 的 `_identity_bool`(`view_context.py:271-274`)对缺失键 `.get()` 静默取 `False`,会在"无历史"页面悄悄给出错误的 `is_official` / `can_dispatch` 等。属 P5 第二套私有实现 + 漂移隐患。

**爆炸半径**
误删 / 改坏这个手搓 dict,会让 `no_history`/`missing_history` 页面的资源派工与报表页 `plan_role` 过滤字段崩塌(`KeyError` 或全 `False` 误判);反之放任不管,则承担未来字段漂移时的**静默错值**风险。

**对抗验证裁定(real_debt,但安全方向无虞)**
对抗验证确认这是"第二套该收口的实现"而非"无数据合法占位"。决定性安全证据:**写 / 派工变更不信任该视图 dict**——`operation_execution_feedback_service.py:361` 重新 `resolve_plan_view(...)` 读真 `plan_identity.can_write_feedback`;`resource_dispatch_actual_record_service.py:137` 同样以 `can_write_feedback` 为闸。手搓 dict 仅供**只读的无历史页**。且占位中 `can_dispatch`/`can_write_feedback`/`is_current_executable_official_version` 全硬编码 `False`(`view_context.py:93-94,98`),`_identity_bool` 用 `.get()` 未来缺键 → `False` = 拒绝 = 安全方向,符合灵魂暗线。

**处置建议(收口到统一点)**
1. **先补 parity 测试(对抗验证指出的缺口)**:对 `VALID_PLAN_ROLES` 全集,断言 `default_plan_resolution_dict(role)['plan_identity']` 的键集 + 取值 `== build_plan_identity(无历史输入, source_table='schedule', ...).to_dict()`,并断言外层 dict ⊆ `SchedulePlanResolution.to_dict`。
2. **再把占位委托给 canonical**:`default_plan_resolution_dict` 内部改为调 `build_plan_identity(version=None, source_table=SOURCE_SCHEDULE, ...)` + `SchedulePlanResolution.to_dict`。无历史时多出的 `schedule_result_status` / `schedule_lock_status` / `detail_saved` 三键下游均 `.get()` 读取,无害。
3. **注意外层 `view_context.py:142` `is_official` 用方括号取值**(`plan_identity["is_official"]`,非 `.get()`),收口后改走 `.get()` 反而更稳。
4. **务必保留 `gantt_plan_query.py:32-38` 的遗留错误文案包装**(与 5.1 同一处)。
5. 最后跑 `tests/regression_schedule_result_view_context.py` 与派工 / 反馈契约测试自证行为不变。

**复核结论**：✅ 证据仍准,2 处行号需微订正。`schedule_result_view_context.py` 当前未被改动,手搓 `plan_identity` 仍在 `:77-100`、外层 dict 仍在 `:101-147`。调用点原证据写"`view_context.py:437-449`",复核实际为 **`:440`(no_history)与 `:448`(missing_history)** —— 在原区间内、表述更精确。`_identity_bool` 原证据 `:271-274` 仍准。`tests/regression_schedule_result_view_context.py` 仍 `build_plan_identity` 0 次(parity 测试仍缺)。**🔧 键数订正**:原证据称手搓 `plan_identity`/canonical `to_dict` 为"23 键",**实际复核两侧均为 22 键**(canonical `to_dict` 见 `schedule_plan_identity.py:46-67`,共 22 个键值对;手搓 dict `view_context.py:78-99` 亦 22)——结论"今日键集 0 漂移"不变,仅键计数 -1。

---

### 5.4 【P4 · low · load_bearing=TRUE】⚠️承重(低危):_bool_from_summary 静默吞掉损坏的 result_summary JSON,影响 is_official / 可执行版本 / 可派工判定

**位置**
- `core/services/scheduler/schedule_plan_identity_builder.py:24-29` `_bool_from_summary` 内 `except (TypeError, ValueError): return False`

**引用链**
- `_bool_from_summary` 被 `_history_is_executable`(`:36`)与 `build_plan_identity`(`:150`)调用判 `is_simulation`。
- `is_simulation` 喂入 `_is_official_plan`(`:87-95`,`not is_simulation`)与 `latest_executable_official_version`(`:41-45` 经 `_history_is_executable`)。
- 进而决定 `is_current_executable_official_version`、`can_dispatch`、`can_write_feedback`(`build_plan_identity` 返回的 `PlanIdentity` 字段,`:199,202-203`)。
- `latest_executable_official_version` 的实际消费点:`schedule_plan_query_service.py:99` `latest_official_version=latest_executable_official_version(self.repo.list_history_identity_rows())`。
- 写入侧:`result_summary` 恒由 `schedule_orchestrator` 链的 `build_result_summary_fn` 产 `json.dumps`(`summary/schedule_summary.py:216` `result_summary = json.dumps(result_summary_obj)`,从不手写);`schema.sql` `result_summary TEXT`(可空)。
- 读回:repo `schedule_plan_query_repo.py:80-81`(`list_history_identity_rows`)与 `:104-105`(`get_history_identity_row`)同时 SELECT `h.result_status` 与 `h.result_summary`。

**为何算债**
项目灵魂线是"坏数据不准静默兜底、宁可暴露错误"。此处对损坏 JSON 直接 `except → return False`,把"这条历史的 summary 解析失败"当成"不是模拟"的安全默认,使一条 summary 损坏的记录可能通过 `_history_is_executable` 被选为 `latest_executable_official_version`、并被判 `is_official`。错误被吞,不会让用户 / 运维看见数据缺口。属 P4 静默兜底死角。

**爆炸半径**
改成抛错可能让历史含 NULL / legacy 非 JSON summary 的老库在版本身份解析处直接报错(影响面 = 身份解析全链);保持吞错则牺牲"坏数据可见性"。**低危**,因 `result_summary` 正常恒为机器写 JSON、损坏罕见。

**对抗验证裁定(real_debt,但"承重"含义被精确化、且不可原地改 raise)**
- 对抗验证**推翻了"这处 summary 解析是安全护栏"的说法**:真正承重的是 `result_status='simulated'`(由同一 `ctx.simulate` 原子同写),而非这处 summary 判定。
  - Gate 顺序证据:`schedule_plan_identity_builder.py:33-35` 先查 `result_status in _BLOCKED_RESULT_STATUSES {failed, simulated}`,**早于**(且独立于)`:36` 的 summary gate;每个真模拟先被 Gate1 拦下。
  - `summary/schedule_summary_freeze.py:82-86` `_compute_result_status`:`if simulate: return SIMULATED.value` → 每次模拟跑都被强制 `result_status='simulated'`。
  - `summary/schedule_summary_assembly.py:437` `"is_simulation": bool(ctx.simulate)` 与 `result_status` 同源(冗余副本)。
  - 写入原子性:`run/schedule_persistence.py:309-318` + `data/repositories/schedule_history_repo.py:133-150` 在一条 INSERT 里同写 `result_status` 与 `result_summary`,正常路径下不会分叉。
  - 危险动作闸独立由 `result_status` 兜底:`:161-163` `result_ok = result_status not in _BLOCKED_RESULT_STATUSES`;`is_current_official = is_official and is_current and result_ok`。实际危险派工 / 反馈写入(`resource_dispatch_actual_record_service.py:137`)gate 在 `can_write_feedback`(要求 `is_current_official ⇒ result_ok`),从不单靠 summary `is_simulation`。
  - 所以:删 / 统一这处 summary 判定**不会**让模拟冒充正式或可派工。该处之所以仍标 `load_bearing=true` 并不是因为它独自挡住模拟,而是因为它处在 `is_official` 链路上、且**绝不可原地改成 raise**(见下)。

**处置建议(关键:不可原地 raise)**
- **(硬约束)绝不可把 `:28` 改成 `raise`**——`latest_executable_official_version`(`:41-45`)全量扫历史行,任何一条 legacy/NULL 邻接的损坏 summary 都会让当前方案的 `is_current_executable_official_version` / `can_dispatch` / `can_write_feedback` 整链抛错,这是可用性放大事故而非安全收益。
- **若要落实灵魂线"坏数据可见"**:在读边界加一条**非致命**的完整性日志 / 计数,标记出无法解析的 `result_summary`(例如 `_bool_from_summary` 解析失败时打 warning 日志 + 计数器),而不是让版本身份解析崩溃。这是"暴露而不自欺"与"可用性"的折中收口点。
- **若要移除这处冗余的 summary-based `is_simulation` 判定**(因 `result_status='simulated'` 已是同源权威):先确认没有任何写入方会在不同写 `result_status` 的情况下单独写 `result_summary.is_simulation`(当前 INSERT 是原子同写,成立),然后可删 `:36` 与 `:150` 的 summary 判定,统一信任 `result_status`。

**复核结论**：✅ 证据仍准(基线 `b08162cd`)。⚠️ **工作树超前治理**:该 P4 债在当前 staged 未提交工作树中已被治理(`_bool_from_summary` → `_parsed_summary_flag_is_true(fail_closed=True)` + 新增 `result_summary_parse_failed/_reason` 可见标记),详见 §13.5。以下复核针对 `b08162cd`:`_bool_from_summary` 的 `except (TypeError, ValueError): return False` 仍在 `:24-29`;Gate 顺序(`:33-35` 先于 `:36`)、`build_plan_identity` 的 `:150` 调用、`latest_executable_official_version` 的 `:41-45` 全量扫描均与原证据一致。消费点 `schedule_plan_query_service.py:99` 复证存在;repo 双 SELECT(`:80-81` / `:104-105`)复证。危险动作闸 `can_write_feedback` 在 `resource_dispatch_actual_record_service.py:137` / `operation_execution_feedback_service.py:361` 复证。

---

### 5.5 【P5 · low · load_bearing=false】_normalize_role 在 schedule_plan_role 与 schedule_plan_query_service 字节级重复,且无 plan_role 归一收口点

**位置**
- `core/models/schedule_plan_role.py:21-23` `def _normalize_role(role)`
- `core/services/scheduler/schedule_plan_query_service.py:28-30` `def _normalize_role(role)`

**引用链**
- 两处函数体逐字符相同:`text = str(role or "").strip(); return text or ROLE_ADOPTED`(已逐字复核,完全一致)。
- `dup_symbols.json` 未单列(均为模块私有 `_` 前缀符号)。
- `schedule_result_view_context.py:65` 另有 `normalize_plan_role` 是**带校验**的第三变体(非法 role 抛 `ValidationError`),职责更重,不在本条合并范围。
- 已知收口点核验:grep 实证仓内**无 `enum_normalizers` / `normalization_matrix` 文件**,也无任何 `plan_role` 归一逻辑(即该收口点不存在)。
- `query_service._normalize_role` 完全可 `import` 自 `schedule_plan_role`——`schedule_plan_query_service.py:9-20` 已从 `core.models.schedule_plan_role` import 了 `ROLE_ADOPTED` 等一批符号,加 `_normalize_role` 零成本。

**为何算债**
同一"role 归一(空 → adopted)"职责的两份完全相同私有副本;`schedule_plan_role`(model 层)已是天然归口,`query_service`(service 层)重复造一遍而非复用。属轻度 P5,改一处易漏另一处。

**爆炸半径**
极小:让 `query_service` 复用 `schedule_plan_role._normalize_role` 即可;两者今日行为一致,合并无语义风险。

**处置建议(收口到统一点)**
删 `schedule_plan_query_service.py:28-30` 的本地 `_normalize_role` 定义,改从 `core.models.schedule_plan_role` import(把它加进 `:9-20` 已有的 import 块)。统一点就是 model 层的 `schedule_plan_role._normalize_role`。注意此符号是 `_` 私有,若顾虑跨层引私有名,可在 `schedule_plan_role` 中把它提升为公开 `normalize_role`(无校验版,区别于 `view_context.normalize_plan_role` 带校验版)再 import。

**复核结论**：✅ 证据仍准(行号精确)。两处 `def _normalize_role` 当前仍在 `schedule_plan_role.py:21` 与 `schedule_plan_query_service.py:28`,函数体逐字符相同。grep 复证仓内无 `enum_normalizers`/`normalization_matrix` 含 `plan_role` 的收口点。`view_context.py:65` 的带校验第三变体 `normalize_plan_role` 复证存在。

---

## 06. 分区【scheduler-config-summary-graph】配置/汇总/图分析

**分区健康一句话**：有残渣但非重灾区——`config/` 与 `summary/` 两个子系统是"坏数据不准静默兜底"灵魂原则的范本（except 一律 re-raise `ValidationError`、解析失败一律 append warning + 记 degradation event + 打 `summary_count_parse_failed` 标记）；全部 5 条债集中在三处迁移/抽象残渣上：① SP05 半截包拆分留下的 5 个顶层 shim + 4 个空 delayed 包，② 排产分析诊断块的 core 合同被 web 本地副本架空，③ 图 ready 队列旧抽象被 `sgs_graph.py` 取代后只剩测试续命。**无 P1 写死假冒计算值，无未注释的 P2 隐藏护栏，本分区 5 条债 `load_bearing` 全部为 false**——这点很关键：所有"看起来像护栏"的 shim/兼容面，对抗验证一致裁定其删除后果只是"响亮的 ImportError"，不破任何安全不变量，系统在有无它们时都是 fail-loud 的。

> **承重护栏说明**：本分区没有 `load_bearing=true` 的安全护栏条目，因此没有"我是故意的（安全不变量）"注释需要补。但下文 F3/F4 涉及的 **SP05 冻结兼容面是有意的治理决定**（不是安全护栏，是迁移协调护栏）——它们缺的不是安全注释，而是"我是被 SP05 有意冻结的、删除需走三步迁移"的治理注释。文案见各条处置建议。

---

### F1 · 排产分析诊断块的 core 合同 `schedule_diagnostic_contract.py` 是 web 侧 LIVE 构造器的零生产消费孪生副本

- **病理标签**：P3（半截迁移残渣 / 第 N 套私有实现） · **严重度**：medium · **load_bearing**：false
- **位置**：`core/services/scheduler/analysis/schedule_diagnostic_contract.py`（整文件，约 1-82 行）
  - 三个构造器当前行号：`build_diagnostic_link`→**第 12 行**、`build_diagnostic_item`→**第 25 行**、`build_diagnostic_section`→**第 46 行**（普查证据记的是 :13/:24/:45，已轻微下移）
- **引用链**：
  - **定义点**：`schedule_diagnostic_contract.py:12/25/46` 三个 builder，产出 dict 键 `key/label/value/level/message/details/links`（item）与 `key/title/status/status_label/summary/items/links/degraded/degradation_events/empty_reason`（section）。
  - **唯一引用**：`tests/regression_scheduler_analysis_diagnostic_contract.py:10` `from core.services.scheduler.analysis.schedule_diagnostic_contract import …`。**生产 importer = 0**（全仓 grep `schedule_diagnostic_contract` 仅此一条 test 命中；grep `scheduler.analysis` 另两条命中是 `page_manuals_registry.py:40` / `regression_page_manual_registry.py:505` 的字符串 key `"scheduler.analysis_page"`，与本模块无关）。
  - **LIVE 孪生（实际渲染路径）**：`web/viewmodels/scheduler_analysis_diagnostic_helpers.py:41 build_item` / `:62 build_section`，逐键同形状；被 `web/viewmodels/scheduler_analysis_diagnostics.py:13-37` import 后在 `:54 build_section()` / `:68 build_item()` / `:98 build_section()` 实际拼装，再经 `scheduler_analysis_vm.py`→`analysis.html` 渲染。`_delay_impact.py` / `_health.py` 也同走该 web helper。
  - **git 错位证据**：core 合同单提交 `45c222a0`（"refactor: 增加排产分析诊断块合同"，2026-05-21），此后从未改动；web helper 晚 2 天落地（`ed695e79`，2026-05-23）且获追加修复（`184121ff`）。页面落地时没 import core 合同，而是在 web 层另写了一份本地副本，把 core 合同晾了 12 天。
- **为何算债**：同一职责（诊断 section/item 构造契约）存在两套实现——core 版语义完整但零生产消费，web 版是实际渲染用的活路径。core 合同被绕过，沦为只靠 1 个测试续命的悬空副本。更关键的反证：**真正的灵魂暗线护栏全在 web 侧，core 版一条都没有**——`NonFiniteDiagnosticNumber`（`helpers.py:101`）、`safe_int`（`:127`）、`safe_float`（`:142`）拒非有限数、status 缺失返回 `unknown` 不猜 `ok`，core 合同只有 `str(x or "")` 强转，无任何安全逻辑。所以 core 不是"规范源"，是被架空的废稿。
- **爆炸半径**：误删 core 合同→只破 `regression_scheduler_analysis_diagnostic_contract` 1 个测试（其 :21-82 三个 core-only 用例自证空转），**零生产页面、零安全不变量受影响**（web twin 原封不动）。反向风险：若有人误判方向去删 web twin，会摧毁活渲染路径 + 非有限数护栏——**绝不能删 web 侧**。
- **处置建议 + 收口点**：收口到 **web 侧 `scheduler_analysis_diagnostic_helpers.py`（活路径）**，而非 core。动手前先调和过时的 PR-9 roadmap，不要盲删：
  1. 在 `networkx-scheduler-graph-introduction-items.yaml` 的 `scheduler-graph-analysis-diagnostic-sections` 项里，把 `schedule_diagnostic_contract.py` 从 `primary_paths`（约 :435）及 ruff/pyright `exit_checks`（约 :480-481）移除，标注"该收口已被 web 路径取代"；
  2. 删 core 文件，并清理 `tests/regression_scheduler_analysis_diagnostic_contract.py:10-14` 的 core import 与 :21-82 三个 core-only 用例（web 键集断言 :229-240 是硬编码字面量、与 core 解耦，保留不动）；
  3. 若团队仍坚持让 core 成为规范收口点（走 PR-9 本意），则必须**整体重构**：把 web helper 的 `build_item/build_section` 改指向 core，并把灵魂暗线护栏（`NonFiniteDiagnosticNumber`/`safe_int`/`safe_float`/status 不猜）一并下沉到 core，再连同测试一次性迁移——绝不能单点删改任一侧。
- **复核结论**：⚠️ **行号已变（builder 定义 :13/:24/:45 → :12/:25/:46，下移约 1 行）**，其余证据全部仍准：唯一 test importer、生产 0 引用、web twin 形状/护栏分布、git 时间错位均与普查一致。对抗裁决 `real_debt`（已被精炼，附前置条件）维持。

---

### F2 · `graph/ready_queue.py` 兼容导出 + 底层 `get_ready_operation_ids` 是被 `sgs_graph.py` 取代的未接线并行实现

- **病理标签**：P3（半截迁移残渣 / 死代码） · **严重度**：medium · **load_bearing**：false
- **位置**：`core/services/scheduler/graph/ready_queue.py:1-12`（整文件，**当前精确 1-12 行**）
- **引用链**：
  - **shim 本体**：`ready_queue.py:9` `from core.algorithms.greedy.dispatch.ready_queue import ReadyQueueContractError, get_ready_operation_ids`，文件 docstring 自述意图"so SGS does not import the scheduler service layer"（当 SGS 的 ready 桥）。
  - **底层实现**：`core/algorithms/greedy/dispatch/ready_queue.py:103 def get_ready_operation_ids`。
  - **`get_ready_operation_ids(` 全仓调用点**：仅 `tests/scheduler_graph/test_ready_queue.py` 的 **6 处**（:31/:80/:193/:210/:221/:239，import 在 :16），**生产 0 调用**。
  - **shim 被谁 import**：仅 `tests/regression_scheduler_graph_lazy_runtime_contract.py:27` 与 `tests/scheduler_graph/test_metrics_topology.py:140`——二者只把模块名字符串放进枚举数组断言"若存在则必须保持懒加载/不反向 import"，**并不调用其函数**（注意：上面 grep 里大量 `effective_mode == "graph_ready_queue"` / `"sgs_without_graph_ready_queue"` 是结果摘要里的字符串枚举值，与本 shim 模块无关，勿混淆）。
  - **LIVE 的 SGS ready 排序实际路径**：`core/algorithms/greedy/dispatch/sgs.py:16 from .sgs_graph import (… :23 _prepare_graph_ready_state …)`，在 `sgs.py:201` 调用；定义在 `sgs_graph.py:33 def _prepare_graph_ready_state`。`run/schedule_graph_dispatch_context.py` 只 import `graph.input_adapter/scoring`，从不碰 `ready_queue` shim。全程不经 `get_ready_operation_ids`。
- **为何算债**：PR-5（roadmap 标 done"让 ready 队列参与 SGS 候选"）留下的早期抽象——`get_ready_operation_ids` 这套带完整契约校验的纯函数 + `graph/ready_queue.py` 桥，最终被 PR-6 下沉到 `sgs_graph.py:33 _prepare_graph_ready_state` 取代，自己沦为只有测试调用的死路径。lazy-runtime 合同只是顺带枚举它（"若存在则必须懒"），并不证明它活。
- **爆炸半径**：误删 `graph/ready_queue.py`→破 `regression_scheduler_graph_lazy_runtime_contract`、`test_metrics_topology` 两个 test 的模块枚举断言 + `test_ready_queue.py` 整组（其 import 会失败），**不影响任何排产产出**（SGS 不调它）。安全语义不退化：`sgs_graph.py:22-66` 的 `ValidationError(field="graph_ready_context")` 校验套件（缺集合/非 op_id 集合/误传图对象/重复 op_id/与待排工序不一致）已等价或更严于死函数抛的 `ReadyQueueContractError`，灵魂暗线"坏数据不静默兜底"不退化。
- **处置建议 + 收口点**：收口到 **`sgs_graph.py` 的 `_prepare_graph_ready_state`（活校验）**。同一改动内三处测试耦合必须一起处理，否则破测试模块枚举/导入：
  1. 删 `tests/scheduler_graph/test_ready_queue.py`（否则其 import 失败）；
  2. 从 `regression_scheduler_graph_lazy_runtime_contract.py:27` 与 `test_metrics_topology.py:140` 的模块名数组里摘掉 `"core.services.scheduler.graph.ready_queue"`；
  3. 在 PR-5 决定/roadmap 备忘里补一句"ready_queue helper 已被 `sgs_graph._prepare_graph_ready_state` 取代、连同 service 层兼容 shim 一并下线"，避免历史失忆。
  - 删前确认 `sgs_graph.py:20-160` 校验已覆盖原 helper 的合同点（坏 op_id / 前后置 / 排序 key / 图对象误传）——**经本次核对已等价或更严，无需迁移逻辑**。
- **复核结论**：✅ **证据仍准**。文件 1-12 行精确不变；`get_ready_operation_ids` 唯一调用方仍是 `test_ready_queue.py`（6 处）；两个 lazy/topology 合同的枚举断言行号（:27 / :140）精确不变；`sgs.py:16/:23/:201` 活路径与 `sgs_graph.py:33` 定义、`ValidationError(field="graph_ready_context")` 全部对上。对抗裁决 `real_debt`（附前置条件）维持。

---

### F3 · 顶层 5 个 config/summary shim：生产已迁走、被 SP05 钉死为冻结兼容面

- **病理标签**：P3（半截迁移残渣，地基体检"主病=半截迁移"的尾巴） · **严重度**：low · **load_bearing**：false（**但属 SP05 有意冻结的治理面**）
- **位置**：`core/services/scheduler/config_service.py:1-5`（+ `config_snapshot.py` / `config_validator.py` / `schedule_summary.py:1-29` / `schedule_summary_types.py:1-25`）
- **引用链**：
  - **shim 本体**：5 个文件各 5-29 行，纯 `from .config.X` / `.summary.X` 转出 + `__all__`，**0 逻辑行**（本次逐字确认：无 fallback / 无校验 / 无版本闸）。
  - **生产 importer（排除 tests）= 但发现 2 个 LIVE 非测试消费者**（普查 pass1 误记为"0 生产"，对抗已修正）：
    - `tools/capture_networkx_phase0_baseline.py:17` `from core.services.scheduler.config_service import ConfigService`（也是 `rev_deps.json` 里 config_service shim 的唯一 rev_dep）；
    - `audit/2026-03/20260316_schedule_audit_probes.py:87` `from core.services.scheduler.schedule_summary import build_overdue_items`。
    - 二者均为 SP05 扫描根（core/web）**之外**的离线运维/诊断脚本——正是"离线脚本踩旧路径"的承重顾虑所在。
  - **真正的生产代码全部走深路径**：`web/error_boundary.py:104` / `scheduler_config_display_state.py:5`→`.config`；`scheduler_config.py:11` / `personnel_calendar_pages.py:7`→经 `scheduler/__init__.py __getattr__` 映射 `ConfigService`→`.config.config_service`；`schedule_service.py:259`→`.config.config_service`。**无生产代码走顶层 shim**。
  - **测试 importer = 71 处**（普查 pass1 记的是 53，现已增长到 71，方向不变：仍是"只有测试 + 2 个离线工具在用旧路径"）。
  - **钉死点（SP05 治理合同）**：`tests/test_sp05_path_topology_contract.py:20-31 SERVICE_BEHAVIOR_COMPAT_SYMBOLS` 把这 5 个列为"behavior-compat 别名"（:21 config_service→config.config_service，:29/:30 schedule_summary(_types)→summary.X）；`:328-340` 断言旧模块 `__all__ == expected` 且 `getattr(old,sym) is getattr(new,sym)`（共享身份→无双类 isinstance 隐患）；`:438 assert old_module is not new_module`（"behavior-compatible, not a patch alias"）；`PRODUCTION_LEGACY_IMPORT_SCAN_ROOTS`（:135）禁止 core/web 生产代码 import 它们；`:648/:655` 期望 `config_service.py` 被文档标注为"兼容薄门面"。
- **为何算债**：`config→config/`、`summary→summary/` 包拆分留下的兼容尾巴——生产已全量迁到深路径，旧顶层路径只作冻结兼容面保留。属典型迁移残渣，只是被 SP05 锁住不会悄悄烂。**注意纠偏**：它不是"纯自指测试续命"，确有 2 个离线工具仍踩旧路径，所以直接 `rm` 会破真实工具。
- **爆炸半径**：误删任一 shim→破 `test_sp05_path_topology_contract` + 71 个测试 import + 上述 2 个离线工具。**但失败模式是响亮的 ImportError，不破任何安全不变量**（无预览冒充正式/旧版本冒充现行/坏数据静默吞没/跨层违规）→ **确认非承重安全护栏**。
- **处置建议 + 收口点**：收口到 **深路径 `.config.config_service` / `.summary.schedule_summary`（迁移终点）**。这是一次需协调的迁移、不是自由删除：
  1. 先把 2 个非测试消费者迁到深路径——`tools/capture_networkx_phase0_baseline.py:17` 与 `audit/2026-03/20260316_schedule_audit_probes.py:87` 改为 `.config.config_service` / `.summary.schedule_summary`；
  2. 重指 71 处测试 import 到深路径；
  3. 从 `test_sp05_path_topology_contract.py` 的 `SERVICE_BEHAVIOR_COMPAT_SYMBOLS`/`PUBLIC_SYMBOLS`（:20-82）删这 5 条，并改文档树断言（:648-658 期望"兼容薄门面"标注）；三步做完再删 shim。
  - **该补的"我是有意冻结的"治理注释文案**（贴在每个 shim 顶部，替代裸 import）：
    > `# [SP05 冻结兼容面] 本模块是 config/→config.config_service 包拆分迁移留下的薄门面，由 tests/test_sp05_path_topology_contract.py 钉死。生产代码一律走深路径 .config.config_service；保留此别名仅为兼容尚未迁移的离线脚本（tools/、audit/）与 71 处历史测试。删除前必须先迁这两类消费者并改 SP05 合同——不是自由删除。`
- **复核结论**：⚠️ **行号/计数已变**：测试 importer **53 → 71**（增长，但结论方向不变）；SP05 文档断言行 642-658 → **648/655**（轻微下移）。其余证据全部仍准：5 个 shim 逐字确认纯转出 0 逻辑；2 个离线消费者 `tools/…:17` 与 `audit/…:87` 行号精确不变；SP05 `SERVICE_BEHAVIOR_COMPAT_SYMBOLS` 在 :20-31、`PRODUCTION_LEGACY_IMPORT_SCAN_ROOTS` 在 :135 精确对上。对抗裁决 `depends`（可收但证据需纠偏，附三步前置）维持。

---

### F4 · 空 delayed 包 `calendar/` 与 `batch/`（及 `dispatch/`、`gantt/`）：SP05 强制存在却始终未填充

- **病理标签**：P3（搁置的迁移脚手架） · **严重度**：low · **load_bearing**：false（**属 SP05 有意冻结的空占位**）
- **位置**：`core/services/scheduler/calendar/__init__.py`（**0 字节**）+ `core/services/scheduler/batch/__init__.py`（**0 字节**，普查记为 1 字节，现为 0——更空了）；连带 `dispatch/__init__.py`、`gantt/__init__.py` 同为 0 字节空壳。四目录内**除空 `__init__.py` 外无任何模块**。
- **引用链**：
  - grep 全树：`scheduler.(calendar|batch|dispatch|gantt)` 作为包的生产引用 = 0；`from . import calendar/batch` = 0；importlib 动态字符串引用 = 0——**零运行时消费者**。
  - 干扰项排除：`core/models/__init__.py:11/14 from .batch/.calendar` 是 `core.models` 同名包，非本包；`resource_dispatch_range.py:3 import calendar` 经运行时确认解析到 Python 标准库 `calendar.py`，非本空包，且无 `from .` 相对导入遮蔽标准库的陷阱；`tests/test_greedy_refactor_contracts.py:81 assert "scheduler.calendar" not in text` 是反向断言（禁止 dispatch 算法耦合它），不是依赖。
  - **钉死点**：`tests/test_sp05_path_topology_contract.py:310` 七包存在性元组 `for package_name in ("config", "run", "summary", "batch", "dispatch", "gantt", "calendar")`（断言目录 + `__init__.py` 存在），`:315-316` `for delayed_package in ("batch", "dispatch", "gantt", "calendar")` 循环调 `_assert_init_has_no_imports`（四个 delayed 包 `__init__` 必须无 import）。普查记为 :311-316，实际存在性元组在 :310、无 import 循环在 :315-316，相差约 1 行。
  - **对照**：`config/run/summary` 已填满迁移完成；`batch/calendar/dispatch/gantt` 只搭了空壳。真实日历/批次逻辑仍在顶层 `calendar_engine.py` / `batch_service.py` 等（18+ 活跃 importer，如 `regression_calendar_invalid_shift_window_contract.py:10`、`regression_batch_template_autobuild_same_tx.py:26`）。
- **为何算债**：包拆分计划只完成 `config/run/summary` 三块，`batch/calendar/dispatch/gantt` 预建空包目录就停下，顶层文件从未下沉。SP05 把空壳钉死保证它不被误删也不被误填，但空包本身是搁置的迁移脚手架——且 SP05 对这四包的 pin 是自指的（包只为过测试而存在，测试只为护包而存在），真正护迁移正确性的 strong-alias/behavior-compat 断言只覆盖 `config/run/summary`（:321-340），从不涉及这四个空包。
- **爆炸半径**：误删空包目录→只破 SP05 `:310` 存在断言 + `:315-316` 无 import 循环。**纯目录拓扑，不触碰任何安全不变量**（无预览冒充正式/旧版本冒充现行/坏数据静默吞没/跨层违规）。
- **处置建议 + 收口点**：收口到 **SP05 合同本身**（删空壳 + 同步删断言）。同一提交里两件事一起做、缺一不可：
  1. 删 4 个空占位目录 `core/services/scheduler/{batch,calendar,dispatch,gantt}/`；
  2. 同步改 `tests/test_sp05_path_topology_contract.py`——把 `batch/dispatch/gantt/calendar` 从 :310 存在性元组和 :315 delayed-package 无导入循环里移除，否则该测试失败。
  - 已实证无需额外动作：无 importlib 动态引用、无 `from . import calendar/batch` 相对导入遮蔽标准库、`.limcode/plans/…/05_后续结构债治理与文档同步.plan.md:226,230-233` 明确把批次逻辑保留为顶层文件、**无 active roadmap 把它们当待下沉预留位**。若日后真要分包，届时重建包目录即可，不必现在留空壳。
  - **若选择保留**，该补的治理注释（写进空 `__init__.py`）：
    > `# [SP05 空占位] 此包为 config/run/summary 包拆分的预留位，至今未下沉任何模块。真实 batch/calendar 逻辑仍在顶层 batch_service.py / calendar_engine.py。由 test_sp05_path_topology_contract.py:310/315 钉死"存在且无 import"。删除须同步删该测试断言；无 active roadmap 计划填充本包。`
- **复核结论**：✅ **证据仍准**（一处更"利好"：`batch/__init__.py` 普查记 1 字节、现为 0 字节，更空）。四目录均空、零运行时引用、标准库 `calendar` 非本包均确认；SP05 存在性元组在 :310、无 import 循环在 :315-316（普查 :311-316 范围内，存在性元组实际 :310，偏 1 行）。对抗裁决 `real_debt`（附"删空壳 + 删断言"双动作前置）维持。

---

### F5 · `batch_service._safe_float` 重造浮点解析并静默吞错，绕过 `parse_finite_float`

- **病理标签**：P4（静默兜底死角）+ P5（第 N 套私有浮点解析） · **严重度**：low · **load_bearing**：false
- **位置**：`core/services/scheduler/batch_service.py:56-65`（`@staticmethod` 在 :55，`def _safe_float` 在 :56，函数体 :57-65，**当前精确对上**）
- **引用链**：
  - **本体**：`_safe_float(value)`——`value` 为 `None`/空串 `return None`，否则 `try: float(value) except Exception: return None`——**坏值悄悄变 `None`，不抛不记**。
  - **绕过的收口点**：`core/shared/number_utils.py:23 parse_finite_float`（会 `raise ValidationError` 并校验有限性）。
  - **消费点**：`batch_template_ops.py:172 "ext_days": svc._safe_float(tmpl.ext_days)`、`batch_copy.py:72 "ext_days": svc._safe_float(op.ext_days)`（均精确对上）。
  - **上游已严格校验**：`core/models/batch_operation.py:92 ext_days=parse_optional_float(ext_days, field="ext_days")`、`core/models/part_operation.py:75` 同理——即模型加载时 `ext_days` 已是合法 `float`/`None`，`_safe_float` 看到的几乎不可能是坏值。
  - **已被显式承认**：`tests/test_architecture_fitness.py:77 "core/services/scheduler/batch_service.py:_safe_float"` 在 `LOCAL_PARSE_HELPER_ALLOWLIST`（:75）中（且 :64 也列了 `_safe_float` 名）。
- **为何算债**：同一概念（浮点解析）的私有第 N 套实现 + 静默兜底死角——理论上若 `ext_days` 是坏值会被悄悄吞成 `None` 而非暴露，违背"宁可暴露错误也不自欺"原则。但因上游模型已严格 `parse_optional_float`，实际是冗余防御；且已被 fitness 注册表显式 allowlist 承认，不是失控的私有实现。这是本分区唯一一条 P4，严重度最低。
- **爆炸半径**：极小。替换为 `parse_finite_float` 仅在 `ext_days` 真为坏值时改变行为（从静默 `None` → 抛 `ValidationError`，反而更符合灵魂原则）；但因上游已校验，几乎触发不到。
- **处置建议 + 收口点**：收口到 **`core/shared/number_utils.py:parse_finite_float`（项目统一有限性浮点解析）**。但需先核对模板/复制路径是否真要拒绝坏 `ext_days`（确认语义后再动），改完同步移除 `tests/test_architecture_fitness.py:77` 的 allowlist 条目，否则 fitness 测试会报 stale entry（:254 `stale_entries` 检查）。低优先级，可与其它 P5 私有解析收口一起批量处理。
- **复核结论**：✅ **证据仍准**。`_safe_float` 体 :56-65、两处消费点（`batch_template_ops.py:172` / `batch_copy.py:72`）、两处上游严格解析（`batch_operation.py:92` / `part_operation.py:75`）、收口点 `number_utils.py:23`、allowlist `test_architecture_fitness.py:77` 全部精确对上。该条普查未要求对抗验证（`needs_adversarial=false`），无对抗裁决。

---

### 本分区复核小结

| 编号 | 病理 | 严重度 | load_bearing | 复核结论 |
|---|---|---|---|---|
| F1 | P3 诊断合同孪生副本 | medium | false | ⚠️ 行号已变（builder :13/:24/:45→:12/:25/:46） |
| F2 | P3 ready_queue 旧抽象 | medium | false | ✅ 证据仍准（1-12 行精确） |
| F3 | P3 5 个顶层 shim | low | false | ⚠️ 计数/行号已变（测试 53→71，SP05 :642-658→:648/655） |
| F4 | P3 4 个空 delayed 包 | low | false | ✅ 证据仍准（batch 1→0 字节，更空） |
| F5 | P4 `_safe_float` 静默吞错 | low | false | ✅ 证据仍准（:56-65 精确） |

**一句话总评**：5 条债全部复核为真且 `load_bearing` 全为 false——config/summary 子系统本体干净（fail-loud 范本），债集中在 SP05 半截包拆分的兼容尾巴（5 shim + 4 空包）、诊断合同被 web 副本架空、ready 队列旧抽象被 sgs_graph 取代三处迁移/抽象残渣；所有"看起来像护栏"的 shim 经核实删除后果只是响亮 ImportError，无一是安全护栏，但 SP05 冻结是有意治理决定，处置须走"先迁消费者→再改合同→后删壳"的协调路径而非自由删除。

---

## 07 · core-models（领域模型 `core/models/`）

**分区健康一句话**：地基总体健康、收口点本身干净自律——两条真护栏（`EvidenceLink.validate()` 严格校验可信来源 + `coercion` 引擎 strict_mode 抛错/否则记可见 degradation 事件）恰是灵魂暗线"不自欺"的正面实现，全分区主病只有一处分量级 P3（配置快照整栈双实现，靠人工锁步同步、当前未漂移属潜伏）、一处活的 legacy 错误串往返桥（P3），外加三处 grep 实证的死代码/死参数（P6）。

> 复核范围：本分区 5 条 finding 涉及的 5 个主文件（`schedule_config_runtime_snapshot.py` / `schedule_config_runtime_coercion.py` / `scheduler_public_errors.py` / `greedy/config_adapter.py` / 服务侧孪生 `config/config_snapshot.py`）经 `git status --porcelain` 核对**均不在本次 modified/added 集合内**（最近改动分别停在 `ef244b9e`/`ed695e79`/`fd520b09`/`8ec5b40b`/`ed695e79`，均为 5 月及更早），修复 agent 未触碰。所有引用行号已逐条回到当前代码 grep 复核，**5 条证据全部仍准**。

---

### 07-1 · 【P3 · medium · ⚠️load_bearing=true】ScheduleConfigSnapshot 配置快照/校正引擎整栈双实现，锁步手工同步

> ⚠️ **承重护栏条目**：这套双实现不是可以一删了之的残渣，它当前真正承重（算法层在跑），删任一侧都会断链。它缺的是"我是故意的"注释——见文末补丁文案。

**位置**（整组 5 文件 + 服务侧孪生整组）：
- 模型栈：`core/models/schedule_config_runtime_snapshot.py`、`schedule_config_runtime_coercion.py`、`schedule_config_runtime_fields.py`、`schedule_config_runtime_read.py`、`schedule_config_runtime_weights.py`
- 服务栈孪生：`core/services/scheduler/config/config_snapshot.py`、`config_field_spec.py`、`config_weight_policy.py`

**引用链（已逐条复核到当前代码）**：
- 数据类逐字节相同：`core/models/schedule_config_runtime_snapshot.py:8` `class ScheduleConfigSnapshot`（字段 `:9-38`）**==** `core/services/scheduler/config/config_snapshot.py:24` `class ScheduleConfigSnapshot`（字段 `:24-55`）。本次用 `diff` 抽两边字段名集合，结果 **IDENTICAL FIELD SETS**：各 30 个 dataclass 字段（27 个进 `to_dict` 的配置字段 + `graph_downstream_weight` 派生字段 + `degradation_events`/`degradation_counters` 两个簿记字段），零漂移。
- 校正引擎孪生：`core/models/schedule_config_runtime_coercion.py:409` `def ensure_schedule_config_snapshot`（文件 499 行）**≈** `core/services/scheduler/config/config_snapshot.py:336` `def ensure_schedule_config_snapshot`（整文件 461 行）。
- 权重归一孪生：`core/models/schedule_config_runtime_weights.py:48` `def normalize_weight_triplet` **==** `core/services/scheduler/config/config_weight_policy.py:57` `def normalize_weight_triplet`（仅形参默认名差异）。
- 字段表孪生:模型侧校正逻辑在 `schedule_config_runtime_coercion.py`(对外经门面 `schedule_config_runtime.py` 导出为 `coerce_runtime_config_field`,内部私有 `_coerce_config_field`)vs 服务 `core/services/scheduler/config/config_field_spec.py:468` `def coerce_config_field`。注:模型侧**无**公开符号名 `coerce_config_field`(按此名 grep 会落空),孪生概念成立但命名不对称。
- 消费侧分流（证明两栈都活）：算法栈 → `core/algorithms/greedy/config_adapter.py:6` `from core.models.schedule_config_runtime import ensure_schedule_config_snapshot`、`core/algorithms/greedy/schedule_params.py:98`（`_build_runtime_snapshot` 内 `from core.models.schedule_config_runtime import ensure_schedule_config_snapshot`）；服务栈（config/summary/run 页）走 `core/services/scheduler/config/config_snapshot.py`。
- 门面再导出：`core/models/schedule_config_runtime.py:5` 再导出 `ensure_schedule_config_snapshot`、`:16` 再导出 `normalize_weight_triplet`。

**为何算债**：同一概念（运行期配置快照 + 严格/降级校正 + 权重归一）两套近乎逐字节相同的实现并存，各约 500 行。表面理由成立——算法层不能 import 服务层（分层红线禁止 `core.algorithms → core.services`），需要一个"中性投影"放在 `core/models`；**但 `core.services → core.models` 是合法边**，服务栈完全可以反过来复用 model 栈，而不是另起炉灶。两份靠人工锁步维护（git 实证：`b82c9a4d` / `ef244b9e` 两个 commit 同时改两份字段表）。当前字段集合 `diff` 为空、无漂移，故是**潜伏债**：任何人给配置页（服务栈）加一个字段而忘了同步 model 栈，算法看到的就是旧默认值，而用户在配置页校验/保存的是新值——两边对"同一份配置"各执一词，且算法侧回落是**静默的**（踩中灵魂暗线：坏/缺数据静默兜成默认）。codemap 自身已把 `coercion.py:409 ensure_schedule_config_snapshot` 标记为 `hardcoded->render/resolve（P1 假冒嫌疑）`。

> 顺带实证（强化本条的"静默默认"风险，非新增债）：`coercion.py:470` 处 `graph_downstream_weight = 0 if 临界=0 且 impact=0 else int(ScheduleConfigSnapshot.graph_downstream_weight)`——该字段根本不从配置读取，而是写死取 dataclass 默认值（1）。这正是"快照里有字段但实际不接配置"的微缩样本，恰好说明双栈+静默默认叠加时债务如何潜伏。

**爆炸半径**：排产正确性。算法实际使用的配置可能与配置页校验/保存的不一致；任一栈新增字段未同步即静默分叉，算法侧吃旧默认值且不报错。当前未漂移，影响为**潜伏**——一旦有人改单侧即引爆。

**处置建议 + 收口到哪个已存在统一点**：
1. 收敛方向是**让服务栈复用 model 栈**（合法边方向），把 `core/services/scheduler/config/config_snapshot.py` 的 `ScheduleConfigSnapshot` / `ensure_schedule_config_snapshot` / `normalize_weight_triplet` / `coerce_config_field`(对应模型侧 `coerce_runtime_config_field`)改为从 `core.models.schedule_config_runtime` 再导出或薄委托，删掉服务侧的字段/校正/权重副本。统一收口点 = **`core/models/schedule_config_runtime.py` 门面**（已存在、已被算法栈消费）。
2. 收敛落地前（潜伏期过渡），**至少加一道锁步守护测试**：断言两份 `ScheduleConfigSnapshot` 字段集合 + 默认值逐字段相等（现有 `tests/regression_sp06_no_duplicate_defs.py` 是路径查重，未做字段集合等价断言），让"单侧加字段忘同步"从静默分叉变成红灯。
3. 在两个 dataclass 头部各补"我是故意的"互指注释（见下）。

> **该补的"我是故意的"注释文案**（贴在两份 `class ScheduleConfigSnapshot` 上方各一份，互相指向）：
> ```python
> # [有意的双实现 / 待收敛] 本快照与 core/models/schedule_config_runtime_snapshot.py
> # 是同一份运行期配置的两套实现：算法层禁止 import 服务层（分层红线），故 model 侧
> # 保留一个中性投影供 greedy/* 消费。两栈字段表/默认值【必须逐字段保持一致】——
> # 任一侧新增/改默认值而不同步另一侧，算法会静默吃到旧默认值（违背"坏数据不静默兜底"）。
> # 长期方向：服务栈反向复用 model 栈（services→models 是合法边），届时删除本副本。
> # 改动前请先看 tests/ 里的字段集合锁步断言。
> ```

**复核结论**：✅ 证据仍准。`schedule_config_runtime_snapshot.py:8`、`coercion.py:409`、`weights.py:48`、`config_adapter.py:6`、`schedule_params.py:98`、服务侧 `config_snapshot.py:24/336`、`config_weight_policy.py:57`、`config_field_spec.py:468` 全部行号精确命中；字段集合 `diff` 为空确认零漂移；两侧文件均未被修复 agent 改动。唯一口径修正：原 finding "27 字段"指的是进 `to_dict` 的 27 个配置字段，dataclass 实际 30 个字段（含 1 派生 + 2 簿记），不影响"逐字节相同"结论。

---

### 07-2 · 【P3 · medium · ⚠️load_bearing=true · needs_adversarial】legacy 错误串正则重解析：把已渲染中文串反解回 code，两代错误体制并存

> ⚠️ **承重护栏条目**：这是一座**活着的** legacy 桥（消费方在排产主路径和 viewmodel 里都在跑），不是死代码。对抗验证结论：live legacy，确为真债。

**位置**：`core/models/scheduler_public_errors.py:62-103`、`218-290`

**引用链（已逐条复核到当前代码）**：
- 正则表 `LEGACY_PUBLIC_PATTERNS`：`:62`（`Tuple[Pattern[str], ...] = (`，模板正则延伸到 `:88`）。
- 前缀映射 `_LEGACY_CODE_PREFIXES`：`:94`（8 条中文前缀 → code 的硬映射，到 `:103`）。
- 反解入口 `legacy_public_error_message`：`:218`（`def`，体内 `:229` 遍历 `LEGACY_PUBLIC_PATTERNS` 做 `fullmatch`）。
- 反解入口 `infer_legacy_public_code`：`:284`（`def`，体内 `:287` 走 `_code_from_suffixes`、`:290` 走 `_LEGACY_CODE_PREFIXES`）。
- 另一代（结构化）：同文件 `make_public_error`：`:175`（产 `schema_version`+`code`+`message` 的结构化 dict）。
- **活消费方（对抗验证用）**：
  - `core/services/scheduler/run/auto_assign_resource_errors.py:6` `from core.models.scheduler_public_errors import infer_legacy_public_code, legacy_public_error_message`；`:42` `public_message = legacy_public_error_message(text)`；`:157` `return infer_legacy_public_code(text) in SGS_AUTO_ASSIGN_RESOURCE_ERROR_CODES`。
  - `web/viewmodels/scheduler_summary_display.py:13` import、`:63` `public_message = legacy_public_error_message(item)`。

**为何算债**：老排产路径发出**渲染好的中文错误串**，下游再用一组正则（`infer_legacy_public_code` / `legacy_public_error_message`）把串反解回结构化 code——从"渲染输出"倒推"结构化身份"，绕过了本应端到端携带 code 的结构化错误收口（`make_public_error`）。两代错误体制（结构化 dict vs 串重解析）在同一文件并存，`legacy_` / `LEGACY_` 命名本身就是过渡桥的自供。正则与一长串中文模板字面强耦合（`:63-88` 内嵌"自制工序未补全设备或人员，无法排产：工序…""排产窗口截止到…超出窗口"等整句模板），**任一文案改一个字就断**。

**对抗验证结论（needs_adversarial=true 已结）**：消费方 `auto_assign_resource_errors.py`（排产 run 子包，主链）与 `scheduler_summary_display.py`（summary viewmodel，用户可见摘要）均为**生产活路径**，非测试续命、非死壳。故这是一座**活着的 legacy 桥**，真债成立、不可直接删。

**爆炸半径**：用户可见错误信息的脱敏与归类。改任一中文错误文案，会**静默**使 legacy 正则失配 → 错误被降级为通用文案 `GENERIC_PUBLIC_ERROR_MESSAGE`（"排产执行遇到问题，请联系管理员查看日志。"），用户丢失具体原因，且无任何编译期/运行期告警（再次踩中"宁可暴露错误也不自欺"的反面）。

**处置建议 + 收口到哪个已存在统一点**：
1. 长期：让老排产路径在**发出错误的源头**就携带结构化 code（直接产 `make_public_error` 的 dict），下游不再串重解析；收口统一点 = 同文件 `make_public_error`（`:175`，已是结构化收口）。逐步淘汰 `LEGACY_PUBLIC_PATTERNS` / `_LEGACY_CODE_PREFIXES` / `infer_legacy_public_code`。
2. 过渡期（删不掉时）：补一个"文案↔正则"的锁步守护测试——对每条 `_LEGACY_CODE_PREFIXES` 用真实模板串跑一遍 `infer_legacy_public_code`，断言能解回预期 code，让"改文案断正则"从静默失配变红灯。
3. 在 `LEGACY_PUBLIC_PATTERNS`（`:62`）上方补"我是故意的"注释（见下）。

> **该补的"我是故意的"注释文案**（贴在 `:62 LEGACY_PUBLIC_PATTERNS` 上方）：
> ```python
> # [有意保留的过渡桥 / 待淘汰] 老排产路径发出的是"已渲染中文错误串"，本组正则负责把串
> # 反解回结构化 code（与 make_public_error 的结构化体制并存）。此为兼容桥，非新代码范式。
> # 风险：这些正则与下方中文模板【逐字耦合】，改任一句错误文案都会让正则静默失配、
> # 错误降级为 GENERIC_PUBLIC_ERROR_MESSAGE（用户丢失具体原因）。改文案必同步改这里，
> # 并跑文案↔code 锁步断言。长期方向：让错误在源头就携带 code，删除本桥。
> ```

**复核结论**：✅ 证据仍准。`:62`/`:94`/`:175`/`:218`/`:284` 五个锚点行号精确命中；消费方 `auto_assign_resource_errors.py:6/42/157`、`scheduler_summary_display.py:13/63` 全部命中且仍是活路径；文件停在 `fd520b09`（5 月，"细化排产资源失败提示"），未被修复 agent 改动。对抗验证落定：live legacy。

---

### 07-3 · 【P6 · low · load_bearing=false】死壳 config_adapter：包在本分区收口点外、零功能调用方

**位置**：`core/algorithms/greedy/config_adapter.py:10-27`（相邻文件，经本分区 facade 追出）

**引用链（已复核）**：
- `:9 @dataclass` / `:10 class CriticalConfigReadResult`（`value`/`missing`/`error` 三字段）
- `:16 def read_schedule_config_value`（体内 `:17` 调 `ensure_schedule_config_snapshot`、`:18` `hasattr` 判 missing、`:20-23 try/except` 把异常吞进 `error` 字段）
- `:26 def read_critical_schedule_config`（仅转发 `read_schedule_config_value`）
- 全仓 grep 三个符号（`read_schedule_config_value` / `read_critical_schedule_config` / `CriticalConfigReadResult`）**排除 def 站点后命中为空**——零功能调用方；唯一引用是 `tests/regression_sp06_no_duplicate_defs.py:15` 把该文件**路径**列进查重清单（不调用其函数）。

**为何算债**：这是包在本分区收口点 `ensure_schedule_config_snapshot` 外面的一层薄封装（读快照 + `getattr` + 吞异常成 `error` 字段），没有任何生产或测试代码真正调用它的函数；唯一引用是一个查重守护测试把它的"路径"列进清单。该 facade 本身（`schedule_config_runtime`）仍活（`schedule_params.py:98` 在用），故死的只是这层 adapter 壳。属本分区收口点对外暴露面上的**死消费者**。

**爆炸半径**：无运行期影响；仅是死代码，徒增"本分区收口点有此用法"的假象（误导后人以为有"读单个配置值并吞异常"的标准用法）。

**处置建议 + 收口到哪个已存在统一点**：直接删除整个 `core/algorithms/greedy/config_adapter.py`，并从 `tests/regression_sp06_no_duplicate_defs.py:15` 的路径清单移除该条。真正的配置读取统一点是 `core/models/schedule_config_runtime.py` 门面的 `ensure_schedule_config_snapshot`（消费方应直接读快照属性，无需经此壳）。

**复核结论**：✅ 证据仍准。`:10`/`:16`/`:26` 行号精确；本次 `grep -rn --include="*.py"` 排除 def 站点后**确认零功能调用方**；`sp06` 测试 `:15` 确为路径清单引用；文件停在 `8ec5b40b`（4 月），未被修复 agent 改动。

---

### 07-4 · 【P6 · low · load_bearing=false】死别名 `_safe_identifier`：注释自称内部用，实则零调用

**位置**：`core/models/scheduler_public_errors.py:163-164`

**引用链（已复核）**：
- `:162` 注释 `# Backward-compatible private alias for callers inside this module.`
- `:163 def _safe_identifier(value, *, max_chars=80)`，`:164` 仅 `return public_safe_identifier(value, max_chars=max_chars)`
- 词边界 grep 全仓 `\b_safe_identifier\b`（排除 `public_safe_identifier`、排除另一模块 `core/infrastructure/migrations/v4_sanitizers.py:37/121/122` 自己的同名函数）→ **仅命中本文件 def 自身**，无任何调用方。
- 不在 `__all__`（`:340-351` 只导出 `public_safe_identifier` 于 `:349`）。
- 模块内 `:197` / `:200`（`make_public_error` 内）以及 `:144`/`:149`（`public_safe_identifier` 自身内）一律直接用 `public_safe_identifier`。

**为何算债**：上方注释写"Backward-compatible private alias for callers inside this module"，但 grep 实证模块内外均无任何调用方，模块内部也一律直接用 `public_safe_identifier`。是 `8efa88d5` 收口改名后遗留的**死面包屑**，注释还在误导"有内部调用方"。

**爆炸半径**：无；纯死函数 + 误导性注释。

**处置建议 + 收口到哪个已存在统一点**：删除 `:162-164`（注释 + `_safe_identifier` 别名）。统一收口点 = 同文件 `public_safe_identifier`（`:142`，已是唯一在用的脱敏入口、已进 `__all__`）。

**复核结论**：✅ 证据仍准。`:163-164` 行号精确；本次词边界 grep **确认仅 def 站点命中**（`v4_sanitizers.py` 的同名是另一模块私有函数、不相关）；不在 `__all__` 已核；文件停在 `fd520b09`，未被修复 agent 改动。

---

### 07-5 · 【P6 · trivial · load_bearing=false】死参数 `raw_value`：`_record_blank_choice_degradation` 收了不用

**位置**：`core/models/schedule_config_runtime_coercion.py:83-98`

**引用链（已复核）**：
- `:83 def _record_blank_choice_degradation(collector, *, scope, field_name, raw_value, fallback)`，其中 `:88 raw_value: Any,`
- 函数体 `:91-98`：`:91 label = display_field_label(field_name...)`，`:92-98 collector.add(...)` 的 `message` 只拼 `label`/`fallback`（`"…没有填写，本次先按默认值 {fallback} 处理。"`），**从不引用 `raw_value`**。
- 两个调用点仍传 `raw_value=raw_value`：`_choice_with_degradation` 内 `:155` 起的调用（`raw_value=raw_value` 在 `:159`）；`_yes_no_with_degradation` 内 `:210` 起的调用（`raw_value=raw_value` 在 `:214`）。
- 服务侧孪生函数甚至没有这个参数（佐证其为冗余）。

**为何算债**：形参 `raw_value` 被声明并由两处调用方传入，但函数体内从未被读取（空白值降级消息里只报 `fallback`）。是签名上的**死参数**，徒增调用噪音；与"孪生函数无此参"对照更显其多余。

**爆炸半径**：无；仅签名冗余。

**处置建议 + 收口到哪个已存在统一点**：从 `:88` 删 `raw_value` 形参，并删两个调用点 `:159`/`:214` 的 `raw_value=raw_value` 实参（三处一起改，保持签名/调用一致）。无外部收口点需对接——纯局部清理。注意与 `_record_invalid_choice_degradation`（`:101`，**确实**用到 `raw_value` 拼"当前值"消息）区分，勿误删后者的同名参数。

**复核结论**：✅ 证据仍准。`def` 在 `:83`、`raw_value` 形参在 `:88`、函数体 `:91-98` 不引用 `raw_value`、两调用点起于 `:155`/`:210`（`raw_value=raw_value` 落在 `:159`/`:214`）——全部精确命中；文件停在 `ed695e79`（5 月），未被修复 agent 改动。

---

## 08 · core-algorithms（排产算法核心 `core/algorithms/`）

**分区健康一句话**：这是全项目水下语义债最干净的分区之一——在最危险的 P1（写死常量假冒计算值）、P2（无注释承重不对称）、P4（静默兜底死角）、P5（第 N 套私有身份构造）四类上**零命中**；实际债务全部集中在 P6/P3 一层"新路径胜出、旧路径未清"的迁移尾巴，来自三次算法层重构（`c8a5a49c` 日期解析收敛、`e02cb914` 配置读取内联、`84812566` 图就绪队列增量化），共 6 条，**无一条 load_bearing、无一条违背灵魂暗线**，清理风险低且 blast 主要落在同步测试文件而非生产。

> **复核总结（回到 2026-06-02 当前代码逐条 grep/Read 实证）**：6 条全部 ✅ 证据仍准，主位置 `file:line` 全部精确命中，0 条行号已变、0 条疑似已修复。下文每条末尾给出复核细节。

---

### 为什么本分区没有 P1/P2/P4/P5（审计留痕，便于后续 owner 复核）

这几类是本次普查最在意的承重类病理，本分区**确认无命中**，但相关"看着像债其实有注释自证"的点值得显式登记，避免后续 agent 重复误报：

- **P2 候选（承重护栏）已自带注释，故不计债**：
  - `core/algorithms/dispatch_rules.py:71-72` — `build_dispatch_key` 内 `_safe_positive` 的 `proc_hours<=0` 不兜底极小值，注释明写"否则 ATC 会出现极端值（错误地把不可估算候选排到最前）"+"过滤非有限值（NaN/Inf）避免 -0.0/inf 传播"。这是**有意的承重护栏且已写明意图**，符合标准，不补注释。
  - `core/algorithms/dispatch_rules.py:83-85` — `p<=0` 回退 `avg_proc_hours` 再回退 `1.0`，是显式分级降级而非假身份。
- **P1 候选**：分区内 `1.0` / `2.0`（ATC 的 `k`）/ 排序哨兵均为带语义的算法常量或被 `ctx.increment(...fallback_count)` 计数的可见降级，非"写死假冒计算结果"。
- **P4**：分区内 17 处 `except` 全部 strict 即抛 / 追加可见 `errors` / best-effort 遥测，无一静默吞错。`ready_queue.py:99-100` 的 `except (TypeError, ValueError)` 直接 `raise ReadyQueueContractError(...) from exc`，是灵魂暗线"宁可暴露错误"的正面样本。
- **P5**：string→enum 已统一收口到 `_require_choice + Enum()` 严格路径（见债 4），无第 N 套私有身份构造。

---

### 债 1 · P3 — `config_adapter.py` 整模块迁移残渣：配置读取门面已被内联取代，生产零引用

- **病理标签 / 严重度 / 承重**：P3 半截迁移残渣 · **low** · load_bearing = **false**
- **位置**：`core/algorithms/greedy/config_adapter.py` 全文件 28 行
  - `:10` `CriticalConfigReadResult`（frozen dataclass，含 `value/missing/error` 三字段）
  - `:16` `read_schedule_config_value(config, key)`
  - `:26` `read_critical_schedule_config(config, key)`（仅转调 `:16`）
- **引用链**：
  - `config_adapter.py:16,26` 定义 → 全仓 `grep "read_critical_schedule_config\|read_schedule_config_value"` 生产 **0 引用**（命中仅为 `config_adapter.py` 自身 `:16/:26/:27` 三行）。
  - 唯一外部提及：`tests/regression_sp06_no_duplicate_defs.py:15` 在"禁止重复定义"扫描的路径白名单里列了该文件名（不是调用，是把它纳入静态检查范围）。
  - `git log -S 'read_critical_schedule_config('`：最后调用点在 `e02cb914` 被删除（diff 删 `from .config_adapter import ...` + `read_result = read_critical_schedule_config(config, key, default)`），改由 `core/algorithms/greedy/schedule_params.py` 的 `_snapshot_attr` 内联读取并直接抛 `ValidationError`。
- **为何算债**：排产配置校验链路重构（`fd4b6a9c` 引入 → `e02cb914` 拆除）留下的半截迁移。新路径（直接 `getattr` 快照 + 缺字段即抛）已**全面取代**旧的 `CriticalConfigReadResult`（把异常包进 `.error` 字段返回）。旧门面整模块悬空，且其"把错误塞进结果对象"的风格与新路径"缺字段即抛"**语义相反**——若被误用会绕过快照校验，等于在配置入口重新引入一处可被忽略的错误通道。
- **爆炸半径**：删除整模块仅需同步 `tests/regression_sp06_no_duplicate_defs.py:15` 的路径白名单；无生产调用点，无运行期影响。
- **处置建议 + 收口点**：整文件删除，收口到**已胜出的统一点** `core/algorithms/greedy/schedule_params.py` 的 `_snapshot_attr`（缺字段即抛 `ValidationError`）。同步从 `tests/regression_sp06_no_duplicate_defs.py:15` 白名单移除该路径。
- **复核结论**：✅ 证据仍准。文件仍为 28 行，三个定义在 `:10/:16/:26` 精确命中；生产 grep 仍 0 引用；测试白名单引用仍在 `:15`。

---

### 债 2 · P6 — 5 处死模块别名 `_due_exclusive` / `_parse_due_date` 散落 3 文件，定义后从不被读

- **病理标签 / 严重度 / 承重**：P6 死面包屑 · **low** · load_bearing = **false**
- **位置（5 行）**：
  - `core/algorithms/dispatch_rules.py:25` — `_due_exclusive = due_exclusive`
  - `core/algorithms/evaluation.py:40` — `_parse_due_date = parse_date`
  - `core/algorithms/evaluation.py:41` — `_due_exclusive = due_exclusive`
  - `core/algorithms/ortools_bottleneck.py:24` — `_parse_due_date = parse_date`
  - `core/algorithms/ortools_bottleneck.py:25` — `_due_exclusive = due_exclusive`
- **引用链（逐文件实证别名 0 读取、调用点全走裸名）**：
  - `dispatch_rules.py`：别名 `_due_exclusive`（`:25`）同文件 grep 仅 1 次（定义行）；真正调用在 `:67` 用裸名 `due_exclusive(inp.due_date)`，源自 `:9` `from .greedy.date_parsers import due_exclusive`。
  - `evaluation.py`：别名 `_parse_due_date`/`_due_exclusive`（`:40-41`）0 读取；真正调用 `:36` 裸 `parse_date(s)`、`:257` 裸 `due_exclusive(due_date_value)`，源自 `:9` 共享导入。⚠️注意区分：`:26` 的 `_parse_due_date_state(...)`（`:230` 被调用）是**另一个函数**，不是本条的别名。
  - `ortools_bottleneck.py`：别名（`:24-25`）0 读取；真正调用 `:138` 裸 `parse_date(...)`、`:140` 裸 `due_exclusive(due_d)`，源自 `:19` 共享导入。
  - `git blame`：5 行全部来自 `c8a5a49c`（2026-04-09「日期解析收敛」）。
- **为何算债**：日期解析收口重构时，模块从本地实现切到共享 `core/algorithms/greedy/date_parsers`，留下一层私有别名做"兼容垫片"；但**同一次提交里**调用点已直接改用裸名导入，垫片**从出生就没人用**。三文件同病，是同一次机械改造的残渣。
- **爆炸半径**：5 行纯删除，无任何引用，零运行期影响。
- **处置建议 + 收口点**：5 行直接删除。共享日期解析的唯一收口点已是 `core/algorithms/greedy/date_parsers`（`due_exclusive`/`parse_date`），三文件均已 import 裸名，无需任何替换。
- **复核结论**：✅ 证据仍准。5 行别名定义在 `:25 / :40 / :41 / :24 / :25` 精确命中；各文件裸名调用点（`dispatch_rules:67`、`evaluation:36/257`、`ortools_bottleneck:138/140`）全部仍在，别名读取数仍为 0。

---

### 债 3 · P6 — `mean_positive` 死函数：生产用内联均值，该助手仅靠测试续命

- **病理标签 / 严重度 / 承重**：P6 死代码（第二套实现胜出、第一套悬空）· **low** · load_bearing = **false**
- **位置**：`core/algorithms/dispatch_rules.py:112` `mean_positive(values: Dict[str, float]) -> float`
- **引用链**：
  - `dispatch_rules.py:112` 定义 → 全仓 `grep mean_positive` 生产 **0 引用**；唯一消费者是 `tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py:20/62`（import + 断言"忽略 Inf/非正值"）。
  - 本应消费它的真实生产路径（SGS 算 `avg_proc_hours`）在 `core/algorithms/greedy/dispatch/sgs.py:150` `_average_proc_hours` 内**自己内联**了等价逻辑：`:168-169` `if samples: return sum(samples) / float(len(samples))`，`:170` `ctx.increment("dispatch_key_avg_proc_hours_fallback_count")` 计数降级——从不调 `mean_positive`。
  - `git log -S`：自 `38719ab1` 引入后再无生产调用。
- **为何算债**：为"仅统计严格正值的均值"写的公共助手，但真正算 `avg_proc_hours` 的生产路径自己内联了等价逻辑，**绕过了这个本应是收口点的助手**。属"第二套实现胜出、第一套悬空"的死残渣，仅靠一个回归测试维持存在。
- **爆炸半径**：删除需同步删 `tests/regression_dispatch_rules_nonfinite_proc_hours_safe.py` 中针对 `mean_positive` 的 import 与断言（`:20/:61-63`）；无生产影响。
- **处置建议 + 收口点**：二选一并由 owner 拍板——
  1. （推荐）删除 `mean_positive` + 同步删测试断言；"正值均值"的事实收口点保持在 `sgs.py:150 _average_proc_hours`。
  2. 若想保留一个公共"正值均值"助手，则反向收口：让 `_average_proc_hours` **改调** `mean_positive`，消除两份等价逻辑——但这会改动生产热路径，需谨慎。
- **复核结论**：✅ 证据仍准。主位置 `dispatch_rules.py:112` 精确命中；生产 grep 仍 0 引用，仅测试消费。内联实现确认在 `sgs.py`（全路径 `core/algorithms/greedy/dispatch/sgs.py`）`:150` 定义、`:168-169` 取均值、`:170` 计降级——与证据一致（证据写 `:168`，实际 `if samples:` 在 `:168`、`return` 在 `:169`，同一块，无实质偏差）。

---

### 债 4 · P3 — `parse_dispatch_rule` / `parse_strategy`：被严格收口取代的宽容解析器，生产零引用且语义与灵魂相悖

> **本分区最需要注意的一条（severity = medium）。** 危险面不在"它存在"，而在"它被复活"——一旦有人误把它当规范解析器复用，等于把已铲除的 P4 静默兜底重新引回派工/排序参数入口。

- **病理标签 / 严重度 / 承重**：P3 半截迁移残渣（宽容解析器对抗灵魂暗线）· **medium** · load_bearing = **false**
- **位置**：
  - `core/algorithms/dispatch_rules.py:28` `parse_dispatch_rule(value, default=DispatchRule.SLACK)`，非法分支 `:34-35` `except ValueError: return default`
  - `core/algorithms/sort_strategies.py:161` `parse_strategy(value, default=SortStrategy.PRIORITY_FIRST)`，空值分支 `:169-170` `return default`、非法分支 `:172-173` `except Exception: return default`
- **引用链**：
  - 两函数定义 → 全仓 `grep` 生产（`core/` 非测试、`web/`、`data/`）**0 引用**；且 `core/algorithms/__init__.py:17` 的 `__all__` 也**不导出**它们（实测 `__all__` 仅 `SortStrategy/StrategyFactory/BatchForSort/GreedyScheduler/ScheduleResult/ScheduleSummary`）。
  - 消费者仅为测试：`tests/regression_dispatch_rule_case_insensitive.py:18-25`、`tests/regression_sort_strategy_case_insensitive.py:18-25`。
  - 生产 string→enum 走**严格路径**：
    - `core/algorithms/greedy/schedule_params.py:277` `return SortStrategy(strategy_key)`、`:346` `return DispatchRule(rule_key)`，二者前置 `_require_choice(...)`（`:71` 定义：空值/非法值即抛 `ValidationError`，调用点在 `:272/:341`）。
    - `core/services/scheduler/run/optimizer_config.py:166` `strategy_enum = SortStrategy(require_choice(snapshot.sort_strategy, field="sort_strategy", valid_values=valid_strategies))`。
- **为何算债**：这是 choice 字段校验收口的迁移残渣——早期宽容解析器（非法→静默回退默认枚举）被严格收口（`_require_choice + Enum()` 非法即抛）**全面取代**，但宽容版未清除，仅测试续命。隐患在于其"坏值静默兜底成默认值"的策略**正是灵魂暗线『坏数据不准静默兜底』明令禁止的**；一旦有人误以为它是规范解析器而复用，等于把已铲除的 P4 静默兜底重新引回派工/排序参数入口。
- **爆炸半径**：代码本身生产零 blast；清除需同步处理约 5-9 个 import 它们的测试文件（直接命中 2 个 `*_case_insensitive` 回归，连带其他引用枚举的测试需扫一遍）。**真正危险面在"复活"而非"存在"。**
- **处置建议 + 收口点**：删除两函数，统一收口到严格路径——string→enum 一律走 `schedule_params._require_choice + Enum()`（`:272/277`、`:341/346`）与 `optimizer_config.require_choice + SortStrategy(...)`（`:166`）。若团队确需保留"大小写/空白容错"，应把容错**前移到 `_require_choice` 内部**（先 `.strip().lower()` 再校验合法集合、非法仍抛），而非保留一个独立的"非法→默认"宽容函数。同步删除 `tests/regression_dispatch_rule_case_insensitive.py` 与 `tests/regression_sort_strategy_case_insensitive.py`（或将其大小写容错断言迁移到严格路径上）。
- **复核结论**：✅ 证据仍准。`parse_dispatch_rule` 在 `dispatch_rules.py:28`、`except ValueError` 在 `:34`；`parse_strategy` 在 `sort_strategies.py:161`、`except Exception: return default` 在 `:172-173`——精确命中。`__all__` 不导出实测确认。严格路径锚点 `schedule_params.py:71/272/277/341/346`、`optimizer_config.py:166` 全部精确命中。

---

### 债 5 · P3 — `ready_queue.get_ready_operation_ids` 全量扫描版：生产已换增量前沿，经 service 再导出垫片仅供测试

> **本分区唯一 `needs_adversarial = true` 的条目——需 owner 拍板：是有意保留的差分测试 oracle，还是遗忘的迁移残渣。**

- **病理标签 / 严重度 / 承重**：P3 半截迁移残渣（含一层 service 垫片）· **medium** · load_bearing = **false**
- **位置**：
  - 全量实现：`core/algorithms/greedy/dispatch/ready_queue.py:103` `get_ready_operation_ids(*, schedulable_op_ids, completed_or_fixed_op_ids, blocked_op_ids, predecessor_op_ids_by_op_id, sort_key_by_op_id)`（`:128-135` 全量遍历 schedulable 集合判前驱子集）
  - 再导出垫片：`core/services/scheduler/graph/ready_queue.py`（纯 re-export，文件头注释自陈 *"Compatibility export for graph ready queue helpers."*，`:9` 从算法包 import、`:11` `__all__` 转出）
- **引用链**：
  - `ready_queue.py:103` 定义 → 生产 **0 直接调用**；唯一入口是 `core/services/scheduler/graph/ready_queue.py` 垫片。
  - 垫片消费者仅测试：`tests/scheduler_graph/test_ready_queue.py:16` import + `:31/:80/:193/:210/:221/:239` 调用；`tests/scheduler_graph/test_metrics_topology.py:140` 以字符串 `"core.services.scheduler.graph.ready_queue"` 引用（monkeypatch/mock 目标）。
  - `git show 84812566`（2026-05-19「优化图调度 ready 队列」）diff：删 `from .ready_queue import get_ready_operation_ids` + `ready_op_ids = get_ready_operation_ids(...)`，改为 `core/algorithms/greedy/dispatch/sgs_graph.py` 内联 `_initialize_graph_ready_frontier`（`:226`，在 `:85` 被调用）+ `_mark_graph_operation_completed`（`:305`，`sgs.py:386` 调用）增量维护（Kahn 入度递减）。生产 SGS 走 `sgs_graph._collect_candidates`（`:244`，`sgs.py:203` 调用），不再触及全量版。
  - 差分 oracle 用途确凿：`tests/scheduler_graph/test_ready_queue.py:79` `_full_scan_ready_ids(graph_state)` 直接调 `get_ready_operation_ids`，`:68` `_incremental_ready_ids(...)` 为增量版，`:270` `test_incremental_ready_queue_matches_full_scan_for_branch_join` 等多条断言 `_incremental_ready_ids(...) == _full_scan_ready_ids(...)`——**全量版被当作增量版的差分基准**。
- **为何算债**：同一"就绪集合计算"概念现存**两套实现**：生产用 `sgs_graph` 增量前沿（Kahn 入度递减），全量扫描版 `get_ready_operation_ids` 退居 `core/services/scheduler/graph/ready_queue.py` 再导出垫片后**只被测试引用**。它被 `test_ready_queue.py:270` 系列当作差分测试 oracle——所以**不是纯死残渣**，但"生产包里维护一份仅供测试当基准的旧实现 + 一层仅供测试的 service 垫片"是否值得保留，需 owner 判定（意图保留的差分 oracle vs 遗忘的迁移残渣）。
- **爆炸半径**：删除会移除 incremental-vs-fullscan 差分测试覆盖 + 一层 service 垫片；若保留则应**显式标注其 oracle 用途**。生产路径不受影响。
- **处置建议 + owner 决策（二选一，需拍板）**：
  1. **判定为"有意的差分 oracle"** → 保留，但在 `ready_queue.py:103` 函数 docstring 补一行用途声明（见下方文案），并把 `core/services/scheduler/graph/ready_queue.py` 垫片的"compatibility export"注释改写为"test-only differential oracle export"，消除"看起来像生产兼容层"的误导。这样未来 agent 不会再把它当残渣重报，也不会误当生产入口复用。
  2. **判定为"遗忘的残渣"** → 删除全量版 + service 垫片，把差分断言改为"增量版对已知拓扑的固定期望值"（测试里已有 `== [1]`、`== [2,3]` 等硬编码期望，可独立成立，不必依赖全量版当 oracle）。
  - 无论哪条，收口方向都是：**生产唯一就绪集合实现 = `sgs_graph` 增量前沿**（`:226/:244/:305`），全量版要么显式降格为 test oracle、要么删除，不得再以"compatibility export"的模糊身份停留在 `core/services` 层。
- **复核结论**：✅ 证据仍准。`ready_queue.py:103` 定义、`:138 __all__` 精确命中；service 垫片注释 *"Compatibility export..."* 实测确认；生产 0 直接调用、消费者为 `test_ready_queue.py` + `test_metrics_topology.py:140`（字符串 mock）实测确认；增量前沿 `sgs_graph.py:226/244/305` 与差分 oracle `test_ready_queue.py:79/270` 全部精确命中。

---

### 债 6 · P6 — `batch_order.dispatch_batch_order` 内 `_ = scheduled_count` 死空操作面包屑

- **病理标签 / 严重度 / 承重**：P6 误导性死代码 · **low** · load_bearing = **false**
- **位置**：`core/algorithms/greedy/dispatch/batch_order.py:74` `_ = scheduled_count`
- **引用链**：
  - 形参 `scheduled_count: int = 0` 在 `:39` → 已在 `:58` 传入 `_coerce_state(... scheduled_count=scheduled_count ...)` 用于构造 `ScheduleRunState`。
  - `core/algorithms/greedy/run_state.py:55` `initial_scheduled_count = max(int(scheduled_count or 0) - len(results or []), 0)`、`:75` `return int(self.initial_scheduled_count or 0) + len(self.results)`（`scheduled_count` property）。
  - `:74` `_ = scheduled_count` 把参数赋给丢弃名再"消费"一次；`:75` `return run_state.scheduled_count, run_state.failed_count` 用的是 `run_state` 的 property，与 `:74` 那行无关。
- **为何算债**：重构成 `ScheduleRunState` 后，`scheduled_count` 的真正消费已移入 `_coerce_state`（`:58`），`:74` 这行 `_ = scheduled_count` 是为压制"未使用参数"告警留下的空操作面包屑——但实际参数**早已在 `:58` 被用**，该行属误导性死代码（读者会误以为参数尚未被消费）。
- **爆炸半径**：1 行删除，无行为影响。
- **处置建议 + 收口点**：删除 `:74` 该行。参数 `scheduled_count` 的唯一消费收口点已是 `:58 _coerce_state → run_state.py:55`，无需任何替换；删除后不会触发"未使用参数"告警（参数在 `:58` 已被引用）。
- **复核结论**：✅ 证据仍准。`:74 _ = scheduled_count` 精确命中；`:39` 形参、`:58` 传入 `_coerce_state`、`:75` 用 property 返回均确认；`run_state.py:55` `initial_scheduled_count` 计算精确命中。

---

### 本分区处置优先级速览

| # | 病理 | 位置（主） | 严重度 | 承重 | 对抗 | 处置 | 收口点 |
|---|------|-----------|--------|------|------|------|--------|
| 1 | P3 | `greedy/config_adapter.py`（整模块 28 行） | low | 否 | 否 | 删模块 + 同步测试白名单 | `schedule_params._snapshot_attr` |
| 2 | P6 | `dispatch_rules.py:25` / `evaluation.py:40-41` / `ortools_bottleneck.py:24-25` | low | 否 | 否 | 删 5 行别名 | `greedy/date_parsers` 裸名 |
| 3 | P6 | `dispatch_rules.py:112 mean_positive` | low | 否 | 否 | 删函数 + 同步测试 | `sgs.py:150 _average_proc_hours` |
| 4 | P3 | `dispatch_rules.py:28` / `sort_strategies.py:161` | **medium** | 否 | 否 | 删宽容解析器，容错前移进严格路径 | `_require_choice + Enum()` |
| 5 | P3 | `greedy/dispatch/ready_queue.py:103` + service 垫片 | **medium** | 否 | **是** | owner 拍板：标注 oracle 用途 **或** 删除 | `sgs_graph` 增量前沿 `:226/:244/:305` |
| 6 | P6 | `greedy/dispatch/batch_order.py:74` | low | 否 | 否 | 删 1 行 | `_coerce_state → run_state.py:55` |

**一句话总评**：核心算法层地基干净——6 条债全是三次重构的"旧路径未清"尾巴，无承重、无灵魂违背；只有债 4（宽容解析器复活风险）和债 5（全量就绪队列的 oracle vs 残渣定性）需 owner 一次拍板，其余 4 条可直接清扫。

---

## 09 · core-infra-shared(基础设施与共享脊梁 infrastructure/shared)

**分区健康一句话:** 整条地基(连接/事务 poison/迁移回滚/备份维护窗/日志安全降级/errors)做工扎实、灵魂对齐——except 要么向上抛、要么只降级到 stderr 不丢数据、要么被契约测试钉死;`core/shared` 解析脊梁(strict_parse/field_parse/compat_parse/value_policies/degradation)是真正且唯一的最深层收口点,compat 回退刻意发 `DegradationEvent` 留痕而非静默兜底;**无 P1 写死假冒计算值,无承重不对称护栏被埋**;残渣仅 5 条,集中在双实现漂移面(1 条承重)、半截薄壳化遗漏、两块预建未连线脚手架、以及 1 条被对抗验证"翻案"坐实的备份兜底死角。

> 本次普查共复核 5 条。**5/5 主锚点 `file:line` 在当前代码逐一仍准(✅)**;F5 引用链内有 2 处子引用需就地校正(已在该条标注),不影响其结论。无一条疑似已被修复。

---

### 09-1 · `normalize_yes_no_wide` 在 shared 与归一化矩阵各有一套语义全等实现,无任何测试绑定二者(可静默漂移)

- **病理:** P5(第 N 套私有实现) · **严重度: medium** · **🔩 load_bearing = TRUE(承重护栏,删错即塌)** · 对抗结论 = load_bearing(未被推翻)
- **位置:** `core/shared/boolean_normalize.py:33` `normalize_yes_no_wide` ✅ 主锚点仍准(函数定义在第 33 行)
- **引用链(逐条复核):**
  - shared 侧实现 `core/shared/boolean_normalize.py:33`,宽松别名集硬编码于 `:7-8`(`('y','yes','true','1','on')` / `('n','no','false','0','off','')`) ✅
  - 矩阵侧孪生实现 `core/services/common/normalization_matrix.py:168` `normalize_yes_no_wide_value` ✅(第 168 行),其宽松集由 `:40-41` 的 `NARROW+('on')` / `NARROW+('off','')` 拼出,与 shared 侧逐行同集 ✅
  - 矩阵在 `:5` `from core.models.enums import ... YesNo`——即矩阵自身依赖 `core.models`,故 shared 若改指矩阵会立刻形成 `core.models <-> core.services` 导入环 ✅
  - 活的 `core.models` 消费方:`core/models/schedule_config_runtime_coercion.py:6` `from core.shared.boolean_normalize import normalize_yes_no_wide`,在 `:192 / :201 / :230` 三处调用 ✅
  - **⚠️ 原始证据自带一处更正(本次复核确认其更正正确):** 原 finding 文字称"boolean_normalize 被 core/algorithms/greedy 经 number_utils.to_yes_no 引用"——**此说为假**。`grep core/algorithms/` 对 `boolean_normalize`/`to_yes_no`/`number_utils` 全为空(本次实测 `NONE in core/algorithms`)。真实 `to_yes_no` 消费方全部落在 `core.services.scheduler`:`resource_pool_builder.py:89/280/340`、`config/config_field_coercion.py:25/189/198/227`、`run/schedule_input_collector.py:130/132`、`run/optimizer_config.py:146`、`run/freeze_window.py:84`,且 `to_yes_no` 本身定义在 `core/services/scheduler/number_utils.py:9`,内部 `:5` 转调 `core.shared.boolean_normalize` ✅
  - **关键缺口实测:** `grep normalize_yes_no_wide tests/` = 空,`grep boolean_normalize tests/` = 空——**全仓没有任何测试同时 import 两套实现并断言等价** ✅(漂移风险为真)
- **为何算债:** 同一"宽松是否归一"概念两套独立实现,逻辑当前逐行同义却无任何契约绑定。`YesNo` 枚举值或任一别名集若单边改动(例如有人只改矩阵的 `('on')` 或只改 shared 的 `'on'`),两套会静默漂移、行为分叉而无人察觉。这正是 P5 的漂移风险面。
- **爆炸半径:** `boolean_normalize` 被 `core.models`(下层)直接依赖。若有人以"统一到矩阵"之名删除它、把 coercion 改指 `core.services.common`,会**立刻撞 AST 分层红线(下层 import 上层)**,并制造 `core.models <-> core.services` 导入环,击穿当前 0 违规结构。故该模块的存在本身是分层承重的——它是 `core.shared` 层级及以下唯一的宽松 yes/no 归一器,`core.models`/`core.algorithms` 无替代可调。
- **处置建议(收口方向已锁定,严禁反向):**
  1. **不要删除 shared 模块**。唯一合法的消重方向是:让**上层** `normalization_matrix.normalize_yes_no_wide_value` **反向 delegate** 到**下层** `boolean_normalize.normalize_yes_no_wide`(`services -> shared` 是合法下行边),保留 shared 为唯一事实源、删掉 matrix 内的重复分支。
  2. **优先补一条等价契约测试**(当前真正缺的收口点):断言两函数在「全宽松别名集 × 是/否 × `default`/`passthrough`/`raise`/`no` 全部 `unknown_policy` 分支」上逐一同值,任一单边改动即红灯。这是把"逐行同义"从巧合变成被钉死的不变量。
- **🔩 该补的"我是故意的"承重注释文案(建议加在 `core/shared/boolean_normalize.py:33` `normalize_yes_no_wide` 上方):**
  ```python
  # 【承重·故意双实现,勿合并】本函数是 core.shared 层(及以下)唯一的"宽松是/否"归一器,
  # 被下层 core.models(schedule_config_runtime_coercion:6/192/201/230)、core.algorithms
  # 经 core.services.scheduler.number_utils.to_yes_no 间接依赖。它与上层
  # core.services.common.normalization_matrix.normalize_yes_no_wide_value 语义全等,但【不能】
  # 删除本函数改指矩阵:core.shared 禁止 import core.models(YesNo 枚举在 core.models,故此处
  # 只能硬编码 'yes'/'no' 字面量),下层 import 上层会撞 AST 0 分层违规 + 造 models<->services
  # 导入环。若要消重,唯一合法方向是让上层矩阵反向 delegate 到本函数。两套等价由
  # tests/<待补>_yes_no_wide_equivalence 契约钉死,改任一侧别名集前必跑该测试。
  ```
- **复核结论:** ✅ 证据仍准(主锚点 `:33`、消费链、缺测试均与当前代码一致;原 finding 自带的 core/algorithms 误述已被其对抗证据更正,本次再次实测坐实更正正确)。

---

### 09-2 · `common/number_utils.py` 是 `core/shared/number_utils.py` 的全量函数体拷贝,而同目录 4 个兄弟模块都已是薄 re-export 壳(半截收口)

- **病理:** P3(半截迁移残渣) · **严重度: medium** · load_bearing = false · **对抗结论 = depends(普查员"可安全单边收口"的前提被证伪)**
- **位置:** `core/services/common/number_utils.py:23`(`parse_finite_float`),`:40`(`parse_finite_int`) ✅ 两锚点仍准
- **引用链(逐条复核):**
  - canonical 唯一收口点 `core/shared/number_utils.py:23`(float)、`:39`(int) ✅,内部 `:5-10` 转调 `core.shared.strict_parse` ✅
  - 镜像 `core/services/common/number_utils.py` 保留**全量函数体**(实测 `def-count=6`:2 个 `parse_finite_*` + 4 个 `@overload`),与 canonical 逐行相同,仅多一行中文 docstring(`:24 / :41`) ✅
  - 对照同目录 4 兄弟全为纯 re-export 薄壳(实测 `def-count=0`):`common/compat_parse.py`、`common/value_policies.py`、`common/degradation.py`、`common/field_parse.py` ✅
  - canonical 的活消费方:`core/models/schedule_config_runtime_weights.py:7`、`core/services/scheduler/number_utils.py:6` ✅
  - 镜像的活消费方:`core/services/common/excel_validators.py:26`(在 `:123/:160/:207/:229` 用)、`web/routes/domains/scheduler/scheduler_excel_calendar_rows.py:8`(在 `:79/:94` 用),二者都只 import `parse_finite_*` ✅
  - 钉死测试 `tests/regression_number_utils_facade_delegates_strict_parse.py` 存在(实测在档) ✅,L3 裁定 `.codestable/refactors/2026-06-01-test-gate-cleanup/L3_verdicts.csv:174` = **`KEEP,high`**,2026-06-01 刚复核保留 ✅
- **为何算债:** `core/services/common` 显然在做"统一回落到 `core.shared`"的薄壳化迁移(4/5 兄弟已完成),唯独 `number_utils` 没改成 re-export、留了重复函数体,与 4 个已收口兄弟形成**不对称**。两份体拷当前逐行相同,但重复体可随时单边漂移,是迁移没做完的残渣外观。
- **⚠️ 对抗验证的关键反转(必须写进处置约束):** 普查员设想的"对齐 4 兄弟、单边改成 re-export 薄壳"会**击穿一个活跃 `KEEP/high` 门禁**——
  - `tests/regression_number_utils_facade_delegates_strict_parse.py:19/23-26/45-48/62` 当前 `monkeypatch` 的是 `common.number_utils` **模块级** `parse_required/optional_*(int/float)` 名,并断言 `parse_finite_*` 转调它们。这些名只因 `common` 版**把函数体定义在本模块**、其 `__globals__` 指向 `common.number_utils.__dict__` 才存在且可被 patch。
  - 一旦改成薄壳(`from core.shared.number_utils import *`),`parse_finite_*` 的 `__globals__` 变成 `shared.number_utils`、模块级被 patch 的名不再存在 → `:23` 立即 `AttributeError`、`:62` 断言失败(patch 变空操作)。
  - 该测试 `:69-84` 还钉住灵魂不变量:空白 + `allow_none` → `None`,否则抛 `ValidationError(field 正确)`。
  - 4 兄弟走的是另一种契约:`tests/regression_config_service_component_contract.py:375-411` 的 `*_reexports_shared_identity` **is-同一性**测试(透明壳)。`number_utils` 故意走 delegation-facade 测试,是**两种不同的设计契约**,不对称是有意而非漏改。
- **爆炸半径:** 该重复文件物理上属相邻 `core-svc-domain` 分区,重复源头是本分区 canonical。生产消费方都只用 `parse_finite_*`,两种形态行为字节级一致,运行期灵魂不变量(strict_parse 不静默吞坏数据)不受影响。**风险点不在运行期,而在"误以为可安全单边收口"**:单边改壳会绿灯变红灯。
- **处置建议(收口到 `core/shared/number_utils.py` 这个 canonical,但必须协调式):** 若确要统一为薄壳,**不能单边改**,必须同一笔提交内:(1) 把 facade 测试改写成与 4 兄弟一致的 `*_reexports_shared_identity` 同一性测试;(2) 有意识推翻 `L3_verdicts.csv:174` 的 `KEEP/high` 裁定并记录决定。若不做这套协调,则维持现状、把"故意保留 delegation-facade"写成注释即可——**不建议为消重而消重**。
- **复核结论:** ✅ 证据仍准(锚点 `:23/:40`、4 兄弟 def-count=0、镜像 def-count=6、L3:174=KEEP/high、消费方均与当前代码一致)。但 finding 的 `why_debt` 措辞("可随时单边漂移、可安全收口")需被 `_adv_verdict=depends` 修正:**不对称是有意设计,单边收口非安全债**。

---

### 09-3 · compat 解析的整条"日期"分支(parse_compat_date + 3 个日期策略 + VALUE_DATETIME/READ_FILTER_ONLY)生产零消费,只靠测试续命

- **病理:** P6(死代码/死面包屑) · **严重度: low** · load_bearing = false · 无需对抗
- **位置:** `core/shared/compat_parse.py:198` `parse_compat_date` ✅ 主锚点仍准(定义在第 198 行)
- **引用链(逐条复核):**
  - `parse_compat_date(` 调用点(call 形态)实测全仓 = **仅 2 处**:定义自身 `core/shared/compat_parse.py:198` + 唯一测试 `tests/regression_compat_parse_emits_degradation.py:39`;`core/web/data` 生产侧 = 0 ✅
  - re-export `core/services/common/compat_parse.py:4`,并列入 `:10` `__all__` ✅
  - 上游日期策略项 `core/shared/value_policies.py:180`(`due_date`,VALUE_DATE)、`:190`(`start_time`,VALUE_DATETIME/READ_FILTER_ONLY)、`:200`(`end_time`,同) ✅(三处 `field=` 行号精确)
  - `get_field_policy` 的**唯一生产调用方**是 `core/shared/compat_parse.py:32` `_resolve_compat_policy`,其余调用全在测试(`regression_value_policies_matrix_contract.py:52..93`、`regression_config_service_component_contract.py:399`)✅;而 `_resolve_compat_policy` 的 VALUE_DATE 出口 `parse_compat_date` 已死
  - 生产里真实坏时间留痕走 `core/services/scheduler/_sched_display_utils.py:84` `record_bad_time_row`,内部 `:92` 手搓 `collector.add(code="bad_time_row_skipped")`,**完全绕开** value_policies 的 `start_time`/`end_time` 策略 ✅
  - 对照活分支:`parse_compat_float`/`parse_compat_int` 经 `core/shared/field_parse.py:85`/`:137` 活跃消费 ✅,仅 date 分支死
- **为何算债:** compat 读取子系统按 float/int/date 全矩阵搭建,但 date 能力(`parse_compat_date` + 3 个日期策略项 + `VALUE_DATETIME` 常量 + `READ_FILTER_ONLY` 常量)从未接到任何生产读链——预建却没连线的脚手架。矩阵契约 `tests/regression_value_policies_matrix_contract.py:92-95` 仍在 pin `start_time`/`end_time`(`get_field_policy("start_time"/"end_time")` 在 `:92/:93`,`READ_FILTER_ONLY` 断言在 `:94/:95`),属"测试活、生产死"。
- **爆炸半径:** 纯增生的未消费切片,小。删除只需同步退掉 `regression_compat_parse_emits_degradation.py:39` 的 date 用例与矩阵契约 `:44-45/:92-95` 的 `start_time`/`end_time` 断言。不删则长期作为"看着像在用"的设计噪音,误导后人以为历史日期导入走这条路。
- **处置建议:** 二选一并记决定——(A) 删除整条 date 切片(parse_compat_date + 3 策略项 + 仅 date 用到的常量),同步退测试;(B) 若属"预留待接"的有意脚手架,在 `parse_compat_date:198` 与三策略项 notes 上标注"预建未接线,待 X 功能落地启用",把死面包屑显式化。收口到现有统一点:坏时间留痕已统一在 `record_bad_time_row` + `degradation` 事件,date 策略本就是冗余路径。
- **复核结论:** ✅ 证据仍准(`parse_compat_date:198`、唯一测试调用 `:39`、value_policies `:180/190/200`、矩阵契约断言 `:94-95`、`record_bad_time_row:84/92` 全部与当前代码一致)。

---

### 09-4 · `WRITE_INTERNAL_ONLY` 写模式常量定义 + re-export + `__all__` 白名单齐全,但无任何 FieldPolicy 使用、无任何消费方分支判断

- **病理:** P6(死代码/死面包屑) · **严重度: low** · load_bearing = false · 无需对抗
- **位置:** `core/shared/value_policies.py:9` `WRITE_INTERNAL_ONLY = "write_internal_only"` ✅ 主锚点仍准(第 9 行)
- **引用链(逐条复核 —— 全仓仅 3 处,无一处真正消费):**
  - 定义 `core/shared/value_policies.py:9` ✅
  - re-export `core/services/common/value_policies.py:11`(import)、`:29`(`__all__`)✅
  - **零消费实测:** 全仓唯一读取 `policy.write_mode` 的地方是 `core/shared/compat_parse.py:165 / :188 / :208`,三处一律 `== WRITE_OPTIONAL else ...`,**从不与 `WRITE_INTERNAL_ONLY` 比较** ✅
  - `value_policies.py` 内 16 个 `FieldPolicy` 的 `write_mode=` 赋值实测分布:`WRITE_REQUIRED ×13` / `WRITE_OPTIONAL ×1` / `WRITE_NOT_APPLICABLE ×2`,**无一用 `WRITE_INTERNAL_ONLY`** ✅
- **为何算债:** 定义后无人消费的死常量,却散布在定义点 + re-export + `__all__` 三处制造"在用"假象——符合 P6 死面包屑。它是设计时预留但从未落地的写模式词槽。
- **爆炸半径:** 极小。删除仅触及 `value_policies.py:9` 与 `common/value_policies.py:11,29` 两文件三行,无运行期消费方。
- **处置建议:** 删除三处该常量;若属有意预留,在 `:9` 加一行 notes 注明"预留写模式,尚无字段使用"。无需新建收口点。
- **复核结论:** ✅ 证据仍准(定义 `:9`、re-export `:11/:29`、`write_mode` 读取点 `:165/188/208` 全 `==WRITE_OPTIONAL`、FieldPolicy 赋值分布均与当前代码一致)。

---

### 09-5 · 备份完整性校验(PRAGMA integrity_check)**执行本身**失败时只 warning 不阻断,仍把未通过校验的 `.db` 提升为正式备份

- **病理:** P4(静默兜底死角) · **严重度: low(但影响面是"救命快照可信度",建议升档关注)** · load_bearing = false · **🚩 对抗结论 = real_debt,且 `_adv_refuted = TRUE`:原"护栏"辩护被推翻、坐实为真债**
- **位置:** `core/infrastructure/backup.py:333`(内层 `try:`)✅ 主锚点仍准。精确控制流(本次逐行重映射):
  - `:334` `rows = dest.execute("PRAGMA integrity_check").fetchall() or []`
  - `:335` `except Exception as e:` → `:336` 注释"校验执行失败:不阻断备份" → `:337` `fallback_log(..., "warning", "...执行失败(已忽略)...")`
  - `:338` `else:` → `:339` `msg0=...` → `:340` `if msg0 != "ok":` → `:341` error log → `:342` `raise RuntimeError(...)`
  - `:343` `os.replace(tmp_path, backup_path)` → `:344` info "数据库已备份"
- **引用链(逐条复核):**
  - **核心倒挂(bug 本体):** `:335` except(PRAGMA 执行抛异常 = `database disk image is malformed` 一类**更严重**的损坏迹象)只 warning 后**放行**,控制流落到 `:343` 把未校验的 `.tmp` 升为正式备份、`:344` 报 info "已备份";而 `:340` else 分支(PRAGMA 成功返回但首行 != `ok`,**较轻**)反而 `:342` raise 阻断。**严重度被倒挂** ✅
  - 下游信任这些备份当救命快照:`restore() :415` `self.backup(suffix="before_restore")` 造快照 → `_auto_rollback :387` 经 `_copy_db_file(:354-372)` 用 `source.backup(dest)` 把快照盖回活库,**全程无 integrity 复检** ✅
  - 迁移回滚 `core/infrastructure/migration_backup.py` `restore_db_file_from_backup`(def 在 `:38`,`shutil.copy2` 在 `:55`)裸文件拷贝盖活库,**零完整性校验**,完全信任备份文件可信 ✅(⚠️ 原证据写"migration_backup.py:52-58",`copy2` 实在 `:55`、函数 def 在 `:38`——锚点在区间内但更精确应记 `:38/:55`)
  - 迁移前备份走同一 `backup()`:`core/infrastructure/migration_runner.py:188` `manager.backup(...)`,`:61` 文档契约明写"必须取得可用备份否则阻断迁移";若改 raise,则按 `:191` 重抛阻断——更正确(无法运行 integrity_check 的库不算"可用备份") ✅
  - 消费方均能优雅承接 `backup()` 抛错:`core/services/system/maintenance/backup_task.py:149` `except Exception`(记错不崩)✅;`web/bootstrap/factory.py` 退出备份 `:137` `bm.backup(suffix="exit")` 外包 `except MaintenanceWindowError` + `except Exception`(`:143` 附近,记错不崩)✅(⚠️ 原证据写"factory.py:142",**正确路径是 `web/bootstrap/factory.py`,非 `core/infrastructure/factory.py`(后者不存在)**,行号 `:137-143`);手动路由 `web/routes/system_backup.py:108` `mgr.backup(suffix="manual")` 仅捕 `MaintenanceWindowError`(`:109`),`RuntimeError -> 500` 这条路径**今天已因 else 分支存在**,统一只是多一个触发器经既有路径 ✅
  - finally `:346-352` 的 `.tmp` 清理仍在 ✅(抛错不残留半成品)
  - **无任何测试钉死这条宽松吞咽:** `grep integrity_check tests/` = 空 ✅;`tests/regression_restore_success_condition.py` 全程 `mock.patch`(`:109/136/160/181/207`)BackupManager,根本不触达本校验块 ✅
- **为何算债:** 项目灵魂是"坏数据不准静默兜底、宁可暴露错误"。这里把"这份备份是否可信"这一**本应暴露的缺口**吞成 warning:一个无法被验证完整性的备份仍被当成可信备份落地并报成功(`:344` "数据库已备份"),后续 restore 自动回滚 / 迁移回滚会拿它当救命快照盲拷。`:336` 那句"不阻断备份"注释,正是被对抗验证推翻的**伪"我是故意的"**——"有个备份好过没有"的辩护在"救命快照场景 + 严重度倒挂(更严重的 except 反而放行)"面前不成立。
- **爆炸半径:** 影响备份/恢复可信度。极端场景:用一个未验证(可能已损坏)的备份做自动回滚 / 迁移回滚,**放大数据损坏**。半径覆盖 `restore` 自动回滚、`migrate_with_backup` 回滚两条救命路径。
- **处置建议(收口到"完整性不可验证 = 不可信备份 = 不落地"这一条统一立场):**
  1. **主修:** 把 `:335` except 分支改为与 `:340` else 一致 —— 校验**执行失败**即视为不可信、`raise` 不落地(与"返回非 ok 即 raise"对齐,消除严重度倒挂)。
  2. 顺手收尾(非阻塞):`web/routes/system_backup.py:108-113` 手动路由补一个通用 `except` 把备份失败 `flash` 成清晰错误,而非裸 500(该 500 路径今天已存在,只是多一个触发器)。
  3. 独立加固(可后续):在回滚消费方 `_copy_db_file(:354-372)` 与 `restore_db_file_from_backup(migration_backup.py:38/55)` 各补一次 integrity 复检,封堵"旧版遗留的未校验备份文件被当救命快照盲拷"的残口。
  4. 已核验 `finally :346-352` 仍在、且无任何业务流依赖 `backup()` 在校验失败时仍返回路径,故 `raise` 不丢任何安全不变量。
- **复核结论:** ✅ 证据仍准(主锚点 `:333`、严重度倒挂 except/else、`:343` 落地、下游回滚链、消费方 except、无测试钉死,均与当前代码一致)。**2 处子引用需就地校正(已并入上文,不改变结论):** ① 回滚拷贝在 `migration_backup.py:38(def)/:55(copy2)` 而非泛指 `:52-58`;② 退出备份消费方正确路径是 `web/bootstrap/factory.py:137-143`,而非 `core/infrastructure/factory.py:142`。对抗裁定 `real_debt` 成立、原"护栏"定性已被推翻。

---

## 分区【core-svc-domain】业务域服务与报表（services/{report,process,...}）

**分区健康一句话**：本分区基本干净、与"宁可暴露错误也不自欺"的灵魂高度一致——report 子域所有错误路径都抛 `ValidationError`/`BusinessError` 暴露给用户，六个业务域子包的 `except`/兜底逐条核验均为"暴露非吞"，codemap 在本分区的 orphan 标记几乎全是假阳性（漏算了 web/routes/plugin/scripts 等消费方）；真正的水下债只有两处：**一处承重护栏散在服务层却零注释（P2，高危，必须保护并补注释）**，一处零生产消费、仅靠契约测试反向续命的 re-export facade 残渣（P3，低危，可安全收口）。

本次复核结论（2026-06-02 回到当前 git modified/added 代码逐条 grep+Read）：**两条债的 file:line 全部仍然精确，无行号漂移，无疑似已修复**。详见每条末尾的"复核结论"。

---

### 债 1 ｜ execution_review 固定"正式采用方案"的承重不对称——服务层文件内零注释保护

- **病理标签**：P2 承重不对称（故意护栏但无注释）
- **严重度**：🟥 **high**
- **load_bearing**：✅ **true（承重护栏，默认不可删、不可"统一签名"）** — 本条是本分区最需要警惕的一条，对抗验证裁定 `load_bearing`、未被反驳。

#### 位置
- `core/services/report/execution_review.py:141` — `ExecutionReviewMixin.execution_review(self, version, *, date_from, date_to, batch_id, resource_type, resource_id)` 刻意**不收** `plan_role`/`scenario_id`。
- `core/services/report/execution_review.py:178` — `export_execution_review_xlsx(...)` 同样刻意不收 `plan_role`/`scenario_id`。
- 服务层内部 **5 处硬钉** `ROLE_ADOPTED` / `scenario_id=None`：
  - `:112` `_list_plan_rows_between(..., plan_role=ROLE_ADOPTED, scenario_id=None, ...)`
  - `:123` `_list_plan_rows_all(..., plan_role=ROLE_ADOPTED, scenario_id=None, ...)`
  - `:153` `host._resolve_plan(v, ROLE_ADOPTED, None)`
  - `:166-167` 输出固定 `"plan_label": plan_role_label(ROLE_ADOPTED)` / `"plan_role": ROLE_ADOPTED`
- **全文件零注释**说明"为何独缺 plan_role/scenario_id"。唯一一行人话注释是 `:70` 的 `# 计划和现场实际复盘`，并不解释这个不对称是故意的。

#### 引用链（护栏的保护证据全散在别处，服务层本体不设防）
1. **对照兄弟报表全部透传**：`core/services/report/report_engine.py:157` `overdue_batches(...)`、`:267` `utilization(...)`、`:371` `downtime_impact(...)` 三个签名全部接收并透传 `plan_role`/`scenario_id`——只有 `execution_review` 一处是钉死的。
2. **host 层完全不设防**：`core/services/report/report_plan_helpers.py:29` `_resolve_plan`、`:56` `_list_plan_rows_between`、`:83` `_list_plan_rows_all` 完整透传并尊重**任意** `plan_role`/`scenario_id`（`:37` `host.plan_query_service.resolve_plan_view(int(version), plan_role, scenario_id)`）。证明 `execution_review.py` 的 5 处硬钉是**唯一的钉死点**，宿主方法不会替它兜底。
3. **统一压力真实存在、范式已落地**：`web/routes/reports_page_support.py:57-58` 从请求读 `raw_plan_role = request_plan_role()` / `scenario_id = request_scenario_id()`，并在 `:404-409` 透传给 `engine.downtime_impact(..., plan_role=request_ctx["raw_plan_role"], scenario_id=request_ctx["scenario_id"])`；overdue/utilization 同构（`:146-147`/`:176-177`/`:233-234`/`:253-254`）。"路由读请求方案再透传"的范式已遍布同文件，**统一四报表签名只差 execution_review 这一处**——这正是未来重构的诱因。
4. **下游 join 无法自卫**：`data/repositories/operation_execution_event_repo.py:267` `aggregate_states_by_op_ids(self, op_ids)` 仅按 `op_id` 聚合现场反馈，**无 role/scenario 过滤**——喂进任何 `op_id` 它都照配。
5. **现场反馈只对正式采用方案存在**：`core/services/scheduler/operation_execution_feedback_service.py:347` `_load_current_official_schedule`：当 `plan_role != ROLE_ADOPTED`、或 `source_table != SOURCE_SCHEDULE`、或 `scenario_id` 非空时，`:354`/`:362` 一律 `raise _conflict("not_current_official_plan")`。即拿非采用/模拟方案的行去配 `op_id` 反馈 = 拿真实施工事实去给一个从未执行的假设方案贴"实际开始/偏差"列。
6. **护栏只活在 web 链接生成层 + 文档**：`web/viewmodels/scheduler_workbench_link_query.py:5` `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS = {...}` 与 `:266` `if target_page == "execution_review" and _text(key) in _EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS:` 拦截；`tests/regression_plan_vs_actual_review.py:350-359` 锁合同；设计文档 `.codestable/features/2026-06-01-reports-workbench-backlink/reports-workbench-backlink-design.md:28`「计划和现场实际只复盘正式采用方案」、`:71`「`ExecutionReviewMixin.execution_review()` 固定使用正式采用方案」、`:234`「非正式上下文不能变成可复盘链接」、`:253`「不把模拟预览和对比参考方案纳入计划和现场实际复盘口径」明文确认这是设计决定。**但这些守卫全在链接/导航/文档层，不在服务、也不在路由入参路径上**——服务签名一旦被"统一"，入站请求路径没有任何 `plan_role` 拒绝逻辑。

#### 为何算债
这是**故意的承重不对称**：计划和现场实际复盘 = 拿正式采用方案对账现场事实。若放开 `plan_role`/`scenario_id`，模拟方案预览（`is_scenario_preview`）或历史非采用方案会冒充"现场实际复盘"展示给车间，把"从未发生的预览/假设"当成既成事实呈现。承重点（对 `ROLE_ADOPTED` 的钉死）散在服务层 5 行里却**无一行注释说明"这是故意的、不要为了统一四个报表签名而加 plan_role"**——护栏只活在 web 层守卫和 roadmap 文档里。未来 LLM 或人以"统一四个报表入参"之名重构服务层时，会**无声抹掉**这个不变量，而服务层本身不会报错。

#### 爆炸半径
- 若被"统一报表签名"重构加回 `plan_role`/`scenario_id`：模拟方案预览 / 历史方案的明细会以"计划和现场实际"（正式复盘）身份呈现给现场——**数据完整性事故**，直接踩中灵魂红线"宁可暴露错误也不自欺"的反面。
- 同时 web 层 `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS` 守卫会与"放开后的服务层"产生**认知错位**：web 层还在禁，服务层已经接受，护栏破洞且无人察觉。
- 下游 `aggregate_states_by_op_ids` 不自卫，等于把真实施工反馈贴到从未执行的假设方案上。

#### 处置建议（默认不动；要动必须先补不变量的执行点）
**默认动作 = 不删、不统一、立即补注释。** 把散在别处的不变量可见化到服务层执行现场。最低成本即时动作——在 `:112`/`:123`/`:153` 三处硬钉旁各补一行"我是故意的"中文注释，建议文案：

```python
# 承重不对称(故意):计划和现场实际复盘只对账"正式采用方案"(ROLE_ADOPTED)。
# 现场反馈只对正式采用方案存在(见 operation_execution_feedback_service._load_current_official_schedule),
# 放开 plan_role/scenario_id 会让模拟预览/历史方案冒充"现场实际",把没发生的预览当既成事实。
# 禁止为"统一四个报表签名"而给本方法加 plan_role/scenario_id。要放开须先在本服务对
# 非 ROLE_ADOPTED/非 None scenario_id 显式 raise ValidationError,并给 aggregate_states_by_op_ids 加 role/scenario 过滤。
```

**收口到哪个已存在统一点**：不变量的"真理执行点"应落在 `execution_review` 服务自身（与 `operation_execution_feedback_service._load_current_official_schedule:347` 的硬拒同构——后者已是"现场反馈只认正式采用方案"的权威闸门，可在注释中引为依据）；护栏合同收口到既有的 `tests/regression_plan_vs_actual_review.py:350-359` 与 `tests/regression_reports_workbench_navigation_contract.py`。**若未来确有"允许复盘历史正式版本"的真实需求**，按对抗验证给出的顺序：(1) 在 `execution_review` 服务内对任何非 `ROLE_ADOPTED` 角色 / 非 `None` `scenario_id` 显式 `raise ValidationError`（硬拒、绝不默默回退 adopted），把不变量执行点留在服务层；(2) 给 `aggregate_states_by_op_ids` 增加 role/scenario 作用域过滤让 join 能自卫；(3) 在路由入站层加 `plan_role/scenario_id` 闸门并保留/扩展 web 层 forbidden-params 守卫，消除两层认知错位；(4) 用上述两个 regression 测试锁死。

#### 复核结论
✅ **证据仍准**。`:141`/`:178`/`:112`/`:123`/`:153`/`:166-167` 六处行号在当前代码中**完全精确匹配**，5 处硬钉与签名缺 `plan_role`/`scenario_id` 一字不差；服务层文件本体**仍然零注释**（唯一 `:70` 注释只标题不解释）。引用链全部复核命中：`report_engine.py:157/267/371`、`report_plan_helpers.py:29/37/56/83`、`reports_page_support.py:57-58/404-409`、`operation_execution_event_repo.py:267`、`operation_execution_feedback_service.py:347/354/362`、`scheduler_workbench_link_query.py:5/266` 全部准确。**唯一一处文档行号偏移**：原证据 reference_chain 写「design.md:28/71/164」，实测决定句在 **28/71/234/253**（line 164 与本决定无关，应以 234/253 为准）——不影响结论，证据成立。本条未被修复，仍是高危承重债。

---

### 债 2 ｜ 三个零生产消费的 re-export facade 残渣（compat_parse / field_parse / value_policies），仅测试续命

- **病理标签**：P3 半截迁移残渣
- **严重度**：🟩 **low**
- **load_bearing**：❌ false（删除安全，但需按序保护"坏数据必经降级暴露"的测试覆盖，不能连测一起删光）。对抗验证裁定 `real_debt`、原"可能是有意分层约定"的疑虑已被反驳（`_adv_refuted=true`）。

#### 位置
- `core/services/common/compat_parse.py:1-13` — 纯 re-export，仅 `from core.shared.compat_parse import parse_compat_date/float/int` 再经 `__all__` 转发，无任何逻辑。
- `core/services/common/field_parse.py:1-5` — 纯 re-export，仅转发 `core.shared.field_parse` 的 `parse_field_float`/`parse_field_int`。
- `core/services/common/value_policies.py:1-39` — 纯 re-export，仅转发 `core.shared.value_policies` 的 13 个符号。

#### 引用链（生产侧已大面积绕过该 facade，直连 core.shared）
1. **三者生产引用全部 = 0**：grep `core/ web/ data/ scripts/`（排除三文件自身、排除 tests）对 `services.common.{compat_parse,field_parse,value_policies}` 命中数**均为 0**（本次 2026-06-02 实测复现）。
2. **生产实际走 `core.shared.*` 直连**：例如 `core.shared.field_parse` 被 `core/algorithms/greedy/external_groups.py`、`core/algorithms/greedy/schedule_params.py`、`core/models/schedule_config_runtime_coercion.py`、`core/services/scheduler/run/schedule_input_builder.py` 等直接 import，**绕过 facade**。
3. **唯一续命者是测试**（全仓对这三个 `services.common` 别名的引用仅来自 tests/ 与 codemap 快照 json）：
   - `tests/regression_config_service_component_contract.py:14/16/19` — 三者作为条目写在 `_SERVICE_COMMON_NEUTRAL_HELPERS` 元组（`:13` 起）内；
   - 同文件 `:393-399` `test_services_common_value_policies_reexports_shared_identity`（`:394` `from core.services.common import value_policies as service_value_policies`，断言 `service_value_policies.X is shared_value_policies.X`）；
   - 同文件 `:402-411` `test_services_common_parse_core_reexports_shared_identity`（`:403` `from core.services.common import compat_parse as service_compat_parse`，断言 `is shared_compat_parse.X`）——纯自循环"转发身份正确"断言，正是反向续命这三个空壳的唯一来源；
   - 两个行为测试 `tests/regression_compat_parse_emits_degradation.py:18`（`from core.services.common.compat_parse import parse_compat_date, parse_compat_float`）与 `tests/regression_value_policies_matrix_contract.py:18`（`from core.services.common.value_policies import (...)`）虽经 facade 导入，但其断言的是 `core.shared` 底层的**降级发射 / 策略矩阵行为**，非 facade 特有行为，可平移到 `core.shared`。
4. **包级无再导出、无动态引用**：`core/services/common/__init__.py` 为 **1 字节空文件**，无包级再导出；无 `importlib`/`__import__` 动态引用；codemap `rev_deps.json` 中三者均**不是 key**（零生产被引用）。
5. **对照同目录"真兄弟"facade（被采纳的约定）**——本次实测生产消费数：
   - `services.common.strict_parse` = **4 处**生产消费（`core/services/scheduler/operation_edit_service.py`、`core/services/process/supplier_excel_import_service.py`、`core/services/process/supplier_service.py`、`web/routes/process_excel_suppliers.py`）；
   - `services.common.degradation` = **14 处**生产消费；
   - `services.common.number_utils` = **2 处**生产消费（`core/services/common/excel_validators.py`、`web/routes/domains/scheduler/scheduler_excel_calendar_rows.py`）。
   它们是被采纳的 services 层 re-export 约定；而 compat_parse/field_parse/value_policies 三者是**同一约定下零采纳的空壳**。
6. **不存在"必须经 facade"的强制约定，反而对热路径强制反向**：`tests/regression_config_service_component_contract.py:350` `test_scheduler_run_uses_shared_parse_and_degradation_helpers` 把 `_SERVICE_COMMON_NEUTRAL_HELPERS`（含这三者）列为 run 层的 **FORBIDDEN imports**（`:355` `if imported == "core.services" or imported.startswith(_SERVICE_COMMON_NEUTRAL_HELPERS)`），断言主排产链**必须直连 core.shared**。即体系明确禁止热路径经 services.common facade——这三个空壳没有任何"分层 API 表面"价值。

#### 为何算债
"通用服务底座模块"迁移（commit `5ab57494`）后，生产侧对这三个概念要么直连 `core.shared`、要么根本没用 `services.common` 入口，留下三个**无人（生产）消费的 facade**，只靠一个"断言 facade 转发身份正确"的契约测试反向续命——典型的**迁移收尾未清 + 测试自我循环**。删掉这三个 `.py` 及对应测试断言即可，生产零影响。

#### 爆炸半径
- **保留的运行期爆炸半径 = 0**（无人调用），但会持续误导后人误以为存在"services 层必须经 facade"的强制约定。
- **删除的爆炸半径 = 仅需同步删/改 3 处测试**（见处置）。无任何生产文件受影响。

#### 处置建议（删除安全，但按序保护灵魂暗线"坏数据必经降级暴露、不静默兜底"）
**不能连测一起删光**——两个行为测试是承重的（承重点在 `core.shared`，不在 facade）。按序：
1. 先把两个行为测试的 import 从 `core.services.common.*` **改指 `core.shared.*`**：`regression_compat_parse_emits_degradation.py:18` → `from core.shared.compat_parse import ...`；`regression_value_policies_matrix_contract.py:18` → `from core.shared.value_policies import ...`。保住降级发射与策略矩阵覆盖。
2. 从 `tests/regression_config_service_component_contract.py` 删除三处身份断言：元组内 `:14`/`:16`/`:19` 三个条目、`:393` 起 `test_services_common_value_policies_reexports_shared_identity`、`:402` 起 `test_services_common_parse_core_reexports_shared_identity`。**从 `_SERVICE_COMMON_NEUTRAL_HELPERS` 删条目是安全的**——该元组用于 run 层"禁止导入"白名单，把一个即将不存在的模块从禁止清单移除只会放松对不存在模块的检查，且无任何生产文件导入它。
3. 最后删三个 `.py`。完成后生产运行期零影响、灵魂暗线覆盖无损失。

**收口到哪个已存在统一点**：三个概念的唯一真理已统一在 `core.shared.{compat_parse,field_parse,value_policies}`（生产已直连、`strict_parse`/`degradation`/`number_utils` 为同约定的活样板）；行为测试覆盖收口到 `core.shared` 底层。无需新建统一点，删壳即归一。

#### 复核结论
✅ **证据仍准**。三个 `.py` 当前内容与原证据一字不差（compat_parse `:1-13`、field_parse `:1-5`、value_policies `:1-39` 纯 re-export）；2026-06-02 重跑 grep，三者在 `core/ web/ data/ scripts/`（排除 tests）的生产引用**仍全部 = 0**；续命测试行号全部精确命中（`:14`/`:16`/`:19`/`:393-399`/`:402-411`，行为测试 `:18`/`:18`）；`__init__.py` **仍为 1 字节空文件**；真兄弟 facade 消费数实测 strict_parse=4 / degradation=14 / number_utils=2，与原证据一致。本条未被修复，仍是低危可收口残渣。

---

## 11. 分区:data-repos(数据仓储 `data/repositories/`)

**分区健康一句话**:结构干净、承重链条全对,唯一的真债是 PR7a「plan-role 查询迁移」留下的一束版本-only 死读方法(P3,被孪生 `schedule_plan_query_repo` 完整取代、仅靠类型契约测试续命),外加 6 处零引用死方法/死簇(P6)和 1 处不可达的库存静默兜底死角(P4);无 P1(执行事件常量是 schema CHECK 三重锁定的领域真值)、无 P2、无 P5(资源筛选统一走 `normalize_schedule_resource_filter`,明细 JOIN 统一走 `build_schedule_detail_sql`)。

**关于承重护栏(load_bearing)**:本分区 7 条债 **全部 `load_bearing=false`** —— 没有任何一条是「故意的护栏但缺注释」。需要特别说明的是:本分区真正承重的语义护栏(防候选/情景方案冒充 adopted 的 `source_table`+`candidate_id`+`scenario_id` 校验、`_require_candidate_id`/`_require_scenario_id`/未知 source `raise ValueError`)全部活在 **孪生 `schedule_plan_query_repo`** 里,而非活在被本次普查标记为债的那束旧方法里。换言之,F1 要删的旧方法恰恰是「更不安全、plan-role 盲」的版本,删除它不削弱任何不变量。因此本分区无需补任何「我是故意的」注释。

**复核范围**:逐条回到当前代码(多个文件处于 git modified/added 状态),用 grep 全仓(排除 `__pycache__`)+ Read 复核每个 `file:line` 与每条引用链。结论:**7 条全部 ✅ 证据仍准,0 条行号已变,0 条疑似已修复**。

---

### 11.1 【P3 · medium · load_bearing=false】schedule_repo 版本-only 查询方法群:plan-role 迁移残渣,仅类型契约测试续命

**位置**(`data/repositories/schedule_repo.py`):
- `get_version_time_span` — **:36** ✅
- `list_overlapping_with_details` — **:114** ✅
- `list_dispatch_rows_with_resource_context` — **:128**(`scope_type` 过滤体 :137-158)✅

**引用链(已逐条复核)**:

1. **迁移来源**:PR7a(commit `a8ee4934`「给候选方案补上保存位置和统一查询入口」)新建 `data/repositories/schedule_plan_query_repo.py`,其三个孪生方法仍在原位:
   - `get_plan_time_span` — **:257** ✅
   - `list_detail_rows_between` — **:311** ✅
   - `list_dispatch_rows` — **:430**(`scope_type` 过滤体 :447-463)✅
   孪生带 `source_table`+`candidate_id`+`scenario_id` 的 plan-role 感知;`schedule_plan_query_repo.py:447-463` 的 operator/machine/team `scope_type` 分支与 `schedule_repo.py:137-158` **逐行相同**(已对照确认,仅 where_clauses 初值因孪生多了 source 维度而不同)。

2. **生产链全部走孪生,不碰旧方法**:
   - `core/services/scheduler/schedule_plan_query_service.py:399` → `self.repo.list_dispatch_rows(...)`(孪生);其对外方法 `list_plan_dispatch_rows_for_resolution`(:387)被三个活消费者调用:`resource_dispatch_service.py:424`、`resource_dispatch_execution_service.py:95` 与 `:142`(最新提交 `65870e47` 正在扩建此 dispatch lane)。✅
   - `core/services/scheduler/gantt_critical_chain.py:68` → `schedule_repo.list_by_version_with_details(...)`(**另一个活方法**,不是被标记的 `list_overlapping_with_details`)。✅
   - 时间跨度查询活路径走 `gantt_plan_query`→孪生 `get_plan_time_span`,不碰 `schedule_repo.get_version_time_span`。✅

3. **三个旧方法的全仓引用 = 零生产 + 仅测试/契约续命**(grep 实证):
   - `list_overlapping_with_details`:仅 `tests/test_schedule_repository_detail_queries.py:168` + `tests/regression_schedule_service_facade_delegation.py:36`(类型断言) + `tests/regression_gantt_critical_chain_unavailable.py:59`(monkeypatch 桩)。**生产零调用**。
   - `list_dispatch_rows_with_resource_context`:仅 `tests/test_schedule_repository_detail_queries.py:198/218/225/240/247/254/268/274/288` + `tests/regression_schedule_service_facade_delegation.py:39`(类型断言)。**生产零调用**。
   - `get_version_time_span`(裸名,排除 `_dates`):仅 `tests/benchmark_fjsp.py:503` + `tests/regression_schedule_service_facade_delegation.py:31`(类型断言)。**生产零调用**。

4. **「续命」机制本体已复核**:`tests/regression_schedule_service_facade_delegation.py:30-41` 是一个 `get_type_hints(...)["return"] == ...` 的**纯返回类型契约**测试,从不执行 SQL/行为。它在同一个 assert 块里同时覆盖 **2 个仍活的方法**:`:33` `list_version_rows_by_op_ids_start_range`(→ `freeze_window` 活路径)、`:37` `list_by_version_with_details`(→ `gantt_critical_chain.py:68` 活路径)。这证明该测试是「dict 行命名返回类型」契约,**不是**「保留这 3 个 API」的设计意图。

5. **无效脚手架反证**:`tests/regression_gantt_critical_chain_unavailable.py:59` 把 `list_overlapping_with_details` monkeypatch 成 `[]`,但 **:60** 才是把生产真正调用的 `list_by_version_with_details` 设为 `_repo_raise`(:56-57 定义 `raise RuntimeError("repo boom")`)。:59 桩的方法生产根本不调,是无效残留脚手架。✅

**为何算债**:同一职责存在两套实现 —— plan-role 感知版(活)与版本-only 版(死)。迁移把生产切到孪生后,旧三方法没删,仅靠一个断言返回类型的契约测试制造「还在用」假象。roadmap(`aps-frontend-workbench` / `aps-three-gap` / `gantt-result`)均无重新接线计划;`.codestable/checkup/latest/codemap/dynamic_refs.json` 三名皆无;`core/web/data` 无按字符串 `getattr/setattr` 动态派发。属典型 P3 半截迁移残渣。

**爆炸半径**:删除三个旧方法需同步改动 4 处(对抗验证已确权的删除前置条件):
1. `tests/regression_schedule_service_facade_delegation.py` 删 **:31 / :36 / :38-41** 三条类型断言,**保留 :33 / :37**(两个仍活方法的断言)。
2. `tests/test_schedule_repository_detail_queries.py` 删 `list_overlapping_with_details`(~:168)与 `list_dispatch_rows_with_resource_context`(:198-288)用例,**保留 `list_by_version_with_details`(~:188)**。
3. `tests/regression_gantt_critical_chain_unavailable.py:59` 删那行无效 monkeypatch,**保留 :60**(生产真实路径)。
4. `tests/benchmark_fjsp.py:503` 改调孪生 `SchedulePlanQueryService.get_plan_time_span_for_resolution(version, ROLE_ADOPTED)`(benchmark 为非生产 harness,低风险但须改以免基准脚本报错)。
> 误判风险已对抗排除:契约测试**暗示**可能存在「保留非 plan-role 通用读 API」的隐性意图,但因其同时覆盖 2 个真活方法,证明它是返回类型契约而非保留意图;且安全方向相反(删旧方法是去掉更不安全的 plan-role 盲路径)。对抗结论:`real_debt`,可删。

**处置建议 + 收口点**:删除 `schedule_repo.py` 的 `get_version_time_span`(:36)/`list_overlapping_with_details`(:114)/`list_dispatch_rows_with_resource_context`(:128)三方法,按上述 4 步同步测试与 benchmark。**统一收口点 = `schedule_plan_query_repo`(孪生)+ `SchedulePlanQueryService`**(已是生产唯一入口)。注意 `list_by_version`(:29)/`list_version_rows_by_op_ids_start_range`(:71)/`list_by_version_with_details`(:160)是同文件仍被生产调用的活方法,**不在删除范围**。

**复核结论**:✅ 证据仍准。三个 `def` 行号(36/114/128)与孪生行号(257/311/430)、契约测试行号(31/33/36/37/38-41)、monkeypatch 行号(59 vs 60)、生产消费者(399 / 424 / 95 / 142 / 68)全部与 JSON 逐字吻合,无漂移。

---

### 11.2 【P6 · low · load_bearing=false】schedule_repo.list_between 纯死方法:全仓零引用(含测试)

**位置**:`data/repositories/schedule_repo.py:61` ✅

**引用链(已复核)**:grep `list_between` 全仓 `.py`(排除 `__pycache__`)= **仅 :61 的 `def` 一行**,无任何调用,连测试都没有。与 11.1 的 P3 群不同,它甚至不是被孪生取代 —— 是个从未被任何上层接线过的通用区间查询(`SELECT ... FROM Schedule WHERE start_time >= ? AND end_time <= ?`,可选 version)。

**为何算债**:定义后零消费的死代码,占 `schedule_repo` 一个公开方法位。

**爆炸半径**:零。无任何引用点需同步。

**处置建议 + 收口点**:可直接删除 `schedule_repo.py:61-69` 整个方法。无收口对象(若将来真需要区间查询,应走孪生 `list_detail_rows_between`,带 plan-role 维度)。

**复核结论**:✅ 证据仍准,行号 :61 不变。

---

### 11.3 【P6 · low · load_bearing=false】batch_operation_repo 两个死查询方法:get_by_op_code + list_by_status

**位置**(`data/repositories/batch_operation_repo.py`):
- `get_by_op_code` — **:25** ✅
- `list_by_status` — **:50** ✅

**引用链(已复核)**:`BatchOperationRepository` 经 `repository_bundle.op_repo` / `batch_service.batch_op_repo` / `resource_dispatch_actual_record_service.batch_operation_repo` 实例化。grep `get_by_op_code` 与 `list_by_status` 全仓 `.py` = **各自仅 :25 / :50 的 `def` 一行**,0 调用(含测试、模板、动态 getattr)。同文件实际被调的活方法是 `get`(:13)/`list_by_batch`(:37)/`create`(:63)/`update`(:92)/`delete`(:148)/`delete_by_batch`(:151)。

**为何算债**:两个定义后零消费的死方法。`op_code` 在 schema 里是 UNIQUE 业务键,曾打算按 `op_code` 取行但从未接线;`list_by_status` 同理无人按状态批量取批次工序。

**爆炸半径**:零。

**处置建议 + 收口点**:可直接删除 `batch_operation_repo.py:25-35`(get_by_op_code)与 `:50-61`(list_by_status)。无收口对象。

**复核结论**:✅ 证据仍准,行号 :25 / :50 不变。

---

### 11.4 【P6 · low · load_bearing=false】operator_machine_repo.list_links_with_machine_names 死方法:连 facade 都没暴露它

**位置**:`data/repositories/operator_machine_repo.py:82` ✅

**引用链(已复核)**:该 repo 的查询 facade `core/services/personnel/operator_machine_query_service.py` 逐一代理了 `list_simple_rows`/`list_with_names_by_machine`/`list_with_names_by_operator`/`list_links_with_operator_info`/`list_simple_rows_for_machine_operator_sets` —— **唯独漏了 `list_links_with_machine_names`**。grep 全仓 = **仅 :82 的 `def` 一行**,0 调用。
> 对照其活的近亲 `list_links_with_operator_info`(`operator_machine_repo.py:92`):该方法活路径完整 —— facade `operator_machine_query_service.py:105` 代理它,生产 `web/routes/equipment_pages.py:142` 调用,测试 `tests/test_query_services.py:194/222` 覆盖。命名对称(`machine_names` vs `operator_info`)正是 `list_links_with_machine_names` 最易被误认为「在用」的原因,故特别标注。

**为何算债**:一个被 facade 兄弟方法淹没、看似在用实则零消费的死查询。

**爆炸半径**:零。

**处置建议 + 收口点**:可直接删除 `operator_machine_repo.py:82-90`。无收口对象(若将来需要带 machine 名的关联,应在 facade `operator_machine_query_service` 增代理后再启用)。

**复核结论**:✅ 证据仍准,行号 :82 不变;近亲活方法 `list_links_with_operator_info` 的活路径(facade :105 / equipment_pages :142)也已确认。

---

### 11.5 【P6 · low · load_bearing=false】list_as_dicts 三连复制死簇(op_type / operator / part)

**位置**:
- `data/repositories/op_type_repo.py:73` ✅
- `data/repositories/operator_repo.py:85` ✅
- `data/repositories/part_repo.py:71` ✅

**引用链(已复核)**:codemap `dup_bodies` 簇 `0bd22fccb1ac5d3b` 标记三处同体。grep `list_as_dicts` 全仓 `.py`(含 templates/web 字符串引用)= **仅这三条 `def` 行**,0 调用。三个都是 `self.fetchall(...)` 一行的轻量字典列表查询(各取本表少量列),疑似早期给某页面/算法联动用,后被 `list() -> model` 路径取代。

**为何算债**:复制三份的死方法,`dup_bodies` 已识别为同体簇,且全簇零消费。

**爆炸半径**:零。三处可一并删。

**处置建议 + 收口点**:一并删除 `op_type_repo.py:73-74`、`operator_repo.py:85-86`、`part_repo.py:71-72`。无收口对象(各表已有返回 model 的 `list()` 活方法作为唯一查询路径)。

**复核结论**:✅ 证据仍准,三处行号 73 / 85 / 71 均不变。

---

### 11.6 【P6 · low · load_bearing=false】part_repo.list_unparsed 死方法

**位置**:`data/repositories/part_repo.py:32` ✅

**引用链(已复核)**:grep `list_unparsed` 全仓 `.py` = **仅 :32 的 `def` 一行**,0 调用(含测试)。内部转调 `self.list(route_parsed='no')`(:33),曾用于「未解析工艺路线」筛选,现无人调。

**为何算债**:定义后零消费的死方法。

**爆炸半径**:零。

**处置建议 + 收口点**:可直接删除 `part_repo.py:32-33`。无收口对象(其底座 `list(route_parsed=...)` 是活方法,任何调用方可直接传参)。

**复核结论**:✅ 证据仍准,行号 :32 不变。

---

### 11.7 【P4 · low · load_bearing=false】material_repo.update 库存数量 except 静默保留原值(不可达防御死角)

**位置**:`data/repositories/material_repo.py:68-72` ✅(`try` :68 → `float(val)` :69 → `except Exception:` :70 → 注释「留给服务层校验;这里保持原值」:71 → `val = updates.get("stock_qty")` :72)

**引用链(已复核)**:`stock_qty` 不可转 `float` 时,except 捕获后把**原始坏值**重新赋回 `val` 继续 `set_parts.append`/写库(:74-75)。唯一生产调用方 `core/services/material/material_service.py` 的 `update`(:85)在传入前已于 **:100** `updates["stock_qty"] = self._norm_float(stock_qty, field="库存数量", min_v=0.0)` 强校验(`_norm_float` 定义于同文件 :32);`create` 路径同样在 :65 经 `_norm_float` 校验。坏 `stock_qty` 在 service 层就被 `ValidationError` 拦下,**repo 的 except 分支在当前生产路径不可达**。

**为何算债**:形式上违反灵魂暗线「坏数据不静默兜底」—— 若有旁路绕过 service 直调 repo,坏 `stock_qty` 会被悄悄写进 `Materials.stock_qty`(REAL 列)而非报错。但当前唯一生产入口已上游校验,属**不可达防御死角**,危害极低(当前无任何实际错误被吞)。

**爆炸半径**:极小。改成抛错风险极小(service 已挡上游);保留则是无害死代码。

**处置建议 + 收口点**:两个方向皆可,**推荐方向一**以贴合灵魂暗线 ——
- **方向一(贴合灵魂)**:把 :70-72 的 `except` 改为不吞坏值、直接 `raise`(例如 `raise ValueError(f"库存数量无法解析为数值: {val!r}")`),让 repo 层与 service 层共同守「坏数据不静默」。收口到现有错误语义:与 `material_service._norm_float` 抛 `ValidationError` 的上游护栏对齐,形成「双保险」而非「下游兜底」。
- **方向二(若坚持单点校验)**:删除 :64-72 的整段 `stock_qty` 转换 try/except,在注释里写明「`stock_qty` 数值化是 service 层 `_norm_float` 单一职责,repo 只接收已净化值」,把校验收口点明确钉在 `material_service.py:100`。
> 注意:无论哪个方向,**不要保留现状的「except 后塞回原始坏值」**,这是唯一与灵魂暗线相悖的形态。

**复核结论**:✅ 证据仍准。`material_repo.py:68-72` 的 except-保留原值结构不变;上游护栏 `material_service.py:100`(`_norm_float`, `field="库存数量"`)与 JSON 描述逐字吻合(JSON 原写 `material_service.update:100`,当前文件路径为 `core/services/material/material_service.py`,行号 :100 精确命中)。

---

### 本分区复核汇总

| 编号 | 病理 | 严重度 | load_bearing | 位置 | 复核 |
|---|---|---|---|---|---|
| 11.1 | P3 | medium | false | schedule_repo.py:36/114/128 | ✅ 证据仍准 |
| 11.2 | P6 | low | false | schedule_repo.py:61 | ✅ 证据仍准 |
| 11.3 | P6 | low | false | batch_operation_repo.py:25/50 | ✅ 证据仍准 |
| 11.4 | P6 | low | false | operator_machine_repo.py:82 | ✅ 证据仍准 |
| 11.5 | P6 | low | false | op_type_repo.py:73 / operator_repo.py:85 / part_repo.py:71 | ✅ 证据仍准 |
| 11.6 | P6 | low | false | part_repo.py:32 | ✅ 证据仍准 |
| 11.7 | P4 | low | false | material_repo.py:68-72 | ✅ 证据仍准 |

**7 条全部 ✅ 证据仍准 / 0 条行号已变 / 0 条疑似已修复。** 本分区无 `load_bearing=true` 条目,无需补「我是故意的」注释;真正承重的 plan-role 护栏全在活孪生 `schedule_plan_query_repo` 里,F1 删的是更不安全的旧路径。建议优先收口 11.1(P3 残渣,medium),其余 6 条均为可直接删/低风险定点修(P6 死代码 + P4 不可达死角)。

---

## 12. 分区【web-all】(Web 层 routes / viewmodels / bootstrap) 水下语义债

> **分区健康一句话**：地基整体健康——P1 写死假值 exemplar(ADOPTED_PLAN_RESOLUTION) 已修、资源/版本/数值收口点基本被尊重、P4 静默兜底被 `regression_web_silent_fallback_contract` 钉死、路由 `except` 全部 log+flash 可见。水下债集中在三处真债（一处真 P5 枚举中文标签两套实现且语义漂移、一处真 P6 `plan_id` 死面包屑被在途 roadmap 制度化供养、一处**承重 P2** execution-review 护栏写死且零注释）+ 一组 roadmap 明示有意延期的 P3 顶层 wrapper + 一条轻量 P5 getter 副本。

> **本节复核口径**：所有 file:line 已回到【当前 git 工作区代码】逐条复核（多个文件处于 modified/added 状态）。每条债末尾给出复核结论标记：✅证据仍准 / ⚠️行号(或路径)已变 / 🔧疑似已被修复。

**复核汇总**：5 条债全部仍然成立（无一条被修复）。其中 1 条行号完全未变（P3 wrapper），4 条因上游文件被改动导致 file:line 漂移（最大一处是整文件从顶层迁入 `domains/`）。无误报、无已修复。

---

### 12.1 【P5｜medium｜load_bearing=false】enum_display.py + process_bp 中文枚举标签是 enum_normalizers 收口点的第二套私有实现，且语义已漂移

**位置**
- `web/routes/enum_display.py:13-79`——6 个裸标签函数：`machine_status_zh:13` / `operator_status_zh:24` / `day_type_zh:33` / `batch_status_zh:47` / `priority_zh:62` / `ready_zh:73`
- `web/routes/process_bp.py:16-25`——`_merge_mode_zh:16` / `_source_zh:22`

**引用链（已逐条复核）**
- 真正的收口点 `core/services/common/enum_normalizers.py` 已齐备且每个函数都先 `normalize_*`（归一别名）再贴标签：`operator_status_label:82` / `machine_status_label:124` / `source_type_label:159` / `batch_priority_label:209` / `ready_status_label:220` / `calendar_day_type_label:231`。
- 两套同时活在生产，且**同一概念在不同页面用不同函数**：
  - **齐套状态**：排产侧 `web/routes/domains/scheduler/scheduler_bp.py:9` `from ...enum_display import ... ready_zh` → 包装为 `_ready_zh:28-29` → `scheduler_batches.py:150 "ready_status_label": _ready_zh(b.ready_status)` 渲染排产批次页，另 `scheduler_batch_detail.py:251 ready_status_zh=_ready_zh(b.ready_status)`；而物料侧 `web/routes/material.py:9 from core.services.common.enum_normalizers import ready_status_label` → `material.py:124 row["ready_status_zh"]=ready_status_label(row.get("ready_status"))`（另 `:131`）。同一个批次齐套状态，两套标签函数。
  - **设备/人员状态**：`web/routes/equipment_bp.py:9` 与 `personnel_bp.py:9` `from .enum_display import machine_status_zh, operator_status_zh` → `equipment_pages.py:111 / :230 / :276`、`personnel_pages.py:68 / :136` 渲染；而 Excel 导入/导出侧 `equipment_excel_machines.py:12,161` 用收口点 `machine_status_label`、`personnel_excel_operators.py:12,71` 用收口点 `operator_status_label`。
- `process_bp._source_zh:22-25` 不调 `normalize_op_type_category`（收口点该归一器在 `enum_normalizers.py:135`，能吃 `外协/外/外包/外部` 等中文别名），裸 `== SourceType.EXTERNAL.value` 比较后 `else` 直接返回「自制」。

**为何算债**
同一概念（枚举→中文）绕开已存在的收口点又实现一遍，且两者**语义已实证漂移**：
1. **operator 停用文案不一致**：`enum_display.operator_status_zh:29` 对 INACTIVE 返回「停用/休假」，收口点 `operator_status_label:87` 返回「停用」——同一台账状态在设备页/人员页(走 enum_display) 与 Excel 导入预览(走收口点) 显示不同。
2. **ready 坏值被静默贴成确定状态**：`enum_display.ready_zh:73-79` 对未知/None 一律落到 `return "未齐套"`（被 `tests/test_enum_display_consistency.py:59-61` 钉死：`ready_zh("weird")==ready_zh("")==ready_zh(None)=="未齐套"`）；收口点 `ready_status_label:228` 则是 passthrough `return v or "未知"`，坏值原样暴露。前者把一个无法识别的齐套值伪装成「未齐套」这一确定结论，**直接违背灵魂暗线「坏数据不准静默兜底」**。
3. **source 别名误判**：`_source_zh` 不归一，任何未归一中文别名（如导入残留的「外协」「外」）走 `==` 比较都不等于 `SourceType.EXTERNAL.value`，落到 `else` 被误标「自制」——外协工序当成自制。

**爆炸半径**
若把 enum_display 这套删掉统一到收口点：scheduler 批次页/批次详情页、设备页、人员页、日历页的状态列文案会改变（「停用/休假」→「停用」），且齐套坏值从「未齐套」变为「未知/原值暴露」；必须同步改 `tests/test_enum_display_consistency.py:18,25,43,51,55-61` 的钉死断言。反向风险更隐蔽：若 LLM 以为两套等价而只改其一，会造成同一状态在不同页面显示不一致（现场看排产批次页和物料批次页对不上）。

**处置建议（收口到哪个已存在统一点）**
收口到 `core/services/common/enum_normalizers.py` 的 6 个 `*_label` 函数（已是项目认定的统一点）。具体：把 `enum_display.py` 6 个函数与 `process_bp._merge_mode_zh/_source_zh` 改为薄转发（`return machine_status_label(status)` 等），删除裸 `==` 比较体；`_source_zh` 必须经 `source_type_label`（内含 `normalize_op_type_category`）。同步：(1) 改 `test_enum_display_consistency.py` 的钉死断言，把「ready 坏值=未齐套」改成与收口点一致的 passthrough 语义，让这条测试不再为「坏数据静默兜底」续命；(2) 确认 operator 停用文案以收口点「停用」为准（或反向在收口点补「停用/休假」，二选一全局统一）。

**复核结论**：⚠️**路径已变（核心债仍准）**。`location` 字段两处（`enum_display.py:13-79`、`process_bp.py:16-25`）行号完全准确，债仍成立。但引用链里的排产消费方路径已迁移：旧证据 `web/routes/scheduler_bp.py:9` 对应的**顶层文件已不存在**，现位于 `web/routes/domains/scheduler/scheduler_bp.py:9`（import）+ `web/routes/domains/scheduler/scheduler_batches.py:150`（渲染，行号仍是 150）+ 新增消费点 `scheduler_batch_detail.py:251`。收口点 6 函数行号、operator 漂移(:29 vs :87)、ready passthrough(:228)、source 归一器(:135) 均复核为准。

---

### 12.2 【P6｜medium｜load_bearing=false】plan_id 是死面包屑：从 request 读入、存进工作台上下文、回吐进所有导航/导出 URL，却从不进任何 resolver/query，且被在途 roadmap 制度化保留

**位置**
- 读入：`web/navigation_context.py:86` + `web/routes/reports_page_support.py:98,135`
- 存：`web/viewmodels/scheduler_workbench_links.py:229`
- 回吐 URL：`web/viewmodels/scheduler_workbench_link_query.py:118,154`

**引用链（已逐条复核）**
- **request 读入**：`navigation_context.py:86 plan_id=_request_arg("plan_id")`；`reports_page_support.py:98 plan_id=_request_text("plan_id")`（在 `_publish_report_context`），`:135 build_report_context(plan_id=_request_text("plan_id"), ...)`（在 `reports_index_context`）。
- **流入收口点**：`build_workbench_plan_context`（`scheduler_workbench_links.py:187` 形参 `plan_id`，`:229 "plan_id": _text(plan_id) or None` 仅写进 context dict）。
- **去向只有回吐 URL**：`scheduler_workbench_link_query.py:118 _append_param(query,"plan_id",context.get("plan_id"))`（通用计划查询）、`:154`（execution_review 专用计划查询）。并在透传白名单里旅行：`scheduler_navigation_links.py:5`（`_REPORT_CONTEXT_FIELD_NAMES` 首项）+ `:12`（`_has_navigation_context` 探测项）、`reports_export_support.py:14`（导出参数白名单）。
- **零 resolver 消费——关键反证**：`grep -rn` 整个 `core/` 与 `data/` 找「以 request 参数 plan_id 为键的读取」结果为**空**（仅命中无关的 `plan_identity` 数据类、`schedule_plan_identity.py` 等，以及 `core/services/scheduler/resource_dispatch_actual_record_service.py:397,405` 的 `_plan_idempotency_keys`——那是 import_token 幂等键，与 request 的 plan_id 完全无关）。即 request 来的 plan_id 没有任何 query/resolver/计算读它。
- **对比同行 back_to（真承重）**：`scheduler_resource_dispatch.py:184 back_to=_current_back_to()` → `_workbench_context(..., back_to=back_to)` → 多处 `redirect(_page_url(...))`，back_to 确实驱动跳转，证明 plan_id 的「在用」是假象。

**为何算债**
典型死面包屑：定义后散布在 16+ 处透传白名单/URL 拼装里制造「在用」假象，实际没有任何查询/解析/计算读它。更隐蔽的是它被**在途 feature 制度化**成了验收项：`aps-frontend-workbench-items.yaml:289` 的 exit_check、`reports-workbench-backlink-acceptance.md:52`、`reports-workbench-backlink-checklist.yaml:82` 都把 `plan_id` 与**真正承重的 `back_to` 并列**写成「必须保留的返回上下文」。未来 LLM 读 roadmap 会以为 plan_id 承重而**永久供养**一个零消费参数。

**爆炸半径**
删除 plan_id 传递链需同时修改 3 处验收项（`aps-frontend-workbench-items.yaml:289`、`reports-workbench-backlink-acceptance.md:52`、`reports-workbench-backlink-checklist.yaml:82`）+ `tests/regression_reports_workbench_navigation_contract.py` 的相关断言。误删的**功能风险低**（无任何 resolver 依赖），但会触碰 in-progress feature 的契约测试与 roadmap 验收项。

**处置建议（收口到哪个已存在统一点）**
这条不是「收口到某统一点」，而是「确认死后整链删除 + 同步勘误 roadmap」：(1) 先与 `2026-06-01-reports-workbench-backlink` feature 负责人对齐——把 acceptance/checklist/items 三处的「保留 plan_id 与 back_to」修订为只保留 `back_to`，明确记录 plan_id 为「零消费、已移除」，**杜绝它被当成承重契约再供养**；(2) 删 `build_workbench_plan_context` 的 plan_id 形参与 `:229` 写入、两处 `_append_param(..., "plan_id", ...)`、两处白名单条目、两处 request 读入；(3) 改 `regression_reports_workbench_navigation_contract` 去掉 plan_id 断言。动手前必须先和 roadmap 对齐，不能直接删契约项。

**复核结论**：⚠️**行号已变（+1）**。`reports_page_support.py` 两处读入由旧证据 `:97,134` 漂移到当前 `:98,135`（上游文件有改动）。其余位置全部复核为准：`navigation_context.py:86`、`scheduler_workbench_links.py:229`、`scheduler_workbench_link_query.py:118,154`、白名单 `scheduler_navigation_links.py:5,12` / `reports_export_support.py:14`、roadmap 三处 `:289/:52/:82`、`resource_dispatch_actual_record_service.py:397,405`、back_to 对照 `scheduler_resource_dispatch.py:184` 均准确。core/data 零消费 grep 复跑仍为空，债成立。

---

### 12.3 【P2｜high｜load_bearing=true】★承重护栏★ execution-review 报表页写死 plan_role='adopted'/scenario_id=None，代码处零保护注释

> **⚠️ 这是本分区唯一一条承重护栏（load_bearing=true，对抗验证裁定 load_bearing、未被推翻）。下面给出该补的「我是故意的」注释文案。任何「统一参数方言」的重构在动它之前必须先读本节。**

**位置**
- `web/routes/reports_page_support.py:367,369`（两处写死 `"adopted", None`）
- `web/navigation_context.py:80-82`（execution-review 端点的强制分支）
- 结构性写死的根：`core/services/report/execution_review.py:141`（签名）+ `:153`

**引用链（已逐条复核）**
- `reports_page_support.py:367 plan_resolution=page_plan_resolution(services.schedule_plan_query_service, version, "adopted", None)`；`:369 page_date_range_or_version_span(engine, int(version or 0), "adopted", None, raw_date_from, raw_date_to)`。
- **刻意和同类不一致**：同文件所有兄弟报表页都从 request 读 plan_role/scenario_id——`_standard_request_context:57 raw_plan_role=request_plan_role()`、`:58 scenario_id=request_scenario_id()`（overdue/utilization/downtime 全经此函数）。**就 execution-review 这一页写死 adopted/None**。
- **导航上下文侧的第二道强制**：`navigation_context.py:42-47 _is_execution_review_request()` 专门识别该端点（`endpoint=="reports.execution_review_page"` 或 path 命中 `/reports/execution-review`）；`:80-82` 当 `is_execution_review` 时强制 `plan_role=ROLE_ADOPTED`、`scenario_id=""`。
- **底层结构性写死（最硬的证据）**：`core/services/report/execution_review.py:141 def execution_review(self, version, *, date_from, date_to, batch_id, resource_type, resource_id)`——签名**根本不接受 plan_role/scenario_id 入参**；`:153 resolution=host._resolve_plan(v, ROLE_ADOPTED, None)`，行数据按 adopted-only 结构性写死取出。
- **用户文案印证意图**：`core/services/scheduler/scheduler_reports_workbench.py:210 "只复盘正式采用方案，不复盘模拟预览和对比参考方案。"`（另 `:248 "它不复盘模拟预览，也不在这里写现场记录。"`）。
- **模板静态承诺**：`templates/reports/execution_review.html:61` 渲染 `{{ report_plan_status.source_text }} 这张表只复盘正式排产结果；模拟预览和对比参考方案不在这里写入或复盘现场事实。`

**为何算债（P2 承重不对称 + 缺注释）**
刻意和同类不一致（别处都从 request 读 plan_role/scenario_id，就它写死 adopted/None），这个不一致是**承重的**——但在三个写死/强制点（`reports_page_support.py:367`、`:369`、`navigation_context.py:80-82`）都**没有任何 `#` 注释说明「这里故意忽略 request 的 plan_role 是护栏」**。保护意图只散落在 viewmodel 用户文案和 core 签名里，对修改者不可见。

**对抗验证结论（裁定 load_bearing，但精化了「危害边界」）**
对抗验证**确认承重，未推翻**，但纠正了原始 finding「会污染复盘行数据」的措辞——危害边界更精确：
- **行数据本身是安全的**：core 的 `execution_review()` 签名不收 plan_role/scenario_id（`:141`），`reports_page_support.py:327-334` 调用也不传，所以即使 `:367/:369` 被统一成 `request_plan_role()`，**预览/对比方案的「行」也进不了复盘**——行级护栏在 core，结构性安全。
- **真正承重的是「标签身份」与「导航上下文泄漏」两条路径**：
  1. `reports_page_support.py:367 page_plan_resolution(...)` 是**显示用计划身份的唯一来源** → `report_plan_template_fields(:388)` → `report_plan_status.label/source_text` 渲染到 `templates/reports/execution_review.html:56,61`。统一成 request 读会让表头显示「模拟方案甲/preview」盖在 adopted 行数据上——**表头≠表体的自欺式误标**，模板那句「这张表只复盘正式排产结果」当场变成谎言，**违背灵魂暗线「宁可暴露错误也不自欺」**。
  2. `reports_page_support.py:373 _publish_report_context` → `set_current_workbench_navigation_context`。而 `navigation_context.py:77-79` **先读这个已发布的 override**，绕过 `:80-82` 的 is_execution_review 强制。所以若 `:367` 携带了 preview resolution，会经 `build_report_navigation_links` 把 plan_role/scenario_id **泄漏进后续所有导航链接**。`:80-82` 只守「未发布 context 的回退路径」——`:367` 与 `:80-82` 是守**两条不同代码路径**的两道承重闸，不是冗余。
  3. `reports_page_support.py:369 page_date_range_or_version_span(...,"adopted",None,...)` → `version_date_range(plan_role, scenario_id)`，默认日期窗口取自被解析方案的 span；统一后会用 preview 方案的 span 算默认筛选窗口。
- **测试盲区（恰好对应「无害清理」陷阱）**：`grep` tests/ 下**没有**任何用例带 `?plan_role=/scenario_id=` 显式参数 GET `/reports/execution-review`——只有无参或被取代版次场景（`regression_reports_workbench_navigation_contract.py:84,130`）。护栏类测试（`regression_scheduler_workbench_link_guardrails.py:131,149`；`regression_scheduler_workbench_links_contract.py:281`）只钉**viewmodel 链接构造器**，不钉页面 route 的 `:367/:369`。**一个 naive 的统一改动会 CI 全绿通过，却悄悄打破标签/导航不变量。**

**爆炸半径**
未来 LLM 以「消除参数方言、统一所有报表页都从 request 读 plan_role」之名，把 `:367/:369` 的 `"adopted", None` 改成 `request_plan_role()/request_scenario_id()`——护栏即被抹掉：预览/对比方案的身份标签与导航上下文冒充正式采用方案，**表头自欺、导航污染、默认日期窗错位**，且因测试盲区 **CI 不报红**。改动看起来是无害的一致性清理，实为安全回退。

**处置建议（收口 + 必补注释，不是改成从 request 读）**
对抗验证给出的安全前置条件：
1. **绝不**给 core 的 `execution_review()` 加 plan_role/scenario_id 入参——行级承重护栏在 core，原样保留。
2. **先补一条缺失的页面级回归**（堵测试盲区）：`GET /reports/execution-review?plan_role=baseline_best&scenario_id=xxx`，断言渲染出的「排产方案」标签仍为正式采用方案、`source_text` 不出现预览/对比文案、且发布的 nav context `plan_role=adopted` / 无 scenario_id。
3. **若目的是消除魔法字面量方言**：抽一个具名收口 `execution_review_plan_context()`（内部强制 adopted/None）替换 `:367/:369` 两处字面量——而不是改成从 request 读；并在该收口处补上「此处故意忽略 request 的 plan_role 是护栏」注释。
4. **保留** `navigation_context.py:80-82` 的 is_execution_review 强制分支（守未发布 context 回退路径）。

**该补的「我是故意的」注释文案**（直接落到三处）：
- `reports_page_support.py:367` 上方：
  ```python
  # 护栏(load_bearing)：本页【故意】写死 "adopted", None，绝不从 request 读 plan_role/scenario_id。
  # 它是「显示用计划身份」与「发布给后续导航的 context」的唯一来源——若改成 request_plan_role()/
  # request_scenario_id()，模拟预览/对比方案的身份标签会盖在 adopted 行数据上(表头≠表体的自欺)，
  # 并经 _publish_report_context(:373) 泄漏进 navigation_context.py:77-79 的已发布 override，绕过
  # :80-82 的强制分支。行级数据本身安全(core execution_review() 不收这两个参数)，但标签/导航不变量
  # 在此守。改动前必须先补 GET /reports/execution-review?plan_role=...&scenario_id=... 的页面级回归。
  ```
- `reports_page_support.py:369` 上方：
  ```python
  # 护栏(load_bearing)：同上，默认日期窗口必须按正式采用方案的 span 计算，故写死 "adopted", None。
  ```
- `navigation_context.py:80-82` 上方：
  ```python
  # 护栏(load_bearing)：execution-review 端点【故意】无视 request 的 plan_role/scenario_id，强制 adopted。
  # 这是「未发布 context 回退路径」的护栏；已发布 context 的护栏在 reports_page_support.py:367。两道分守不同路径，非冗余。
  ```

**复核结论**：⚠️**行号已变（+1），承重性与全部引用链复核为准**。两处写死由旧证据 `:366,368` 漂移到当前 `:367,369`（上游 +1；对抗验证的 `_adv_precondition` 已按 :367/:369 表述，与当前一致）。`navigation_context.py:80-82` 行号准确；`_is_execution_review_request:42-47`、core 签名 `execution_review.py:141`+`:153 _resolve_plan(v, ROLE_ADOPTED, None)`、viewmodel 文案 `scheduler_reports_workbench.py:210`、模板承诺 `execution_review.html:61` 全部复核为准。

---

### 12.4 【P3｜low｜load_bearing=false】顶层 9 个 scheduler_*.py wrapper 是迁移到 domains/scheduler 后的别名残渣，仅测试续命，roadmap 有意延期清理

**位置**
- `web/routes/scheduler_run.py:7-8`（sys.modules 别名样板）+ 同型 8 个：`scheduler_analysis.py` / `scheduler_batch_detail.py` / `scheduler_batches.py` / `scheduler_config.py` / `scheduler_excel_calendar.py` / `scheduler_ops.py` / `scheduler_week_plan.py`，以及逐符号 re-export 变体 `scheduler_excel_batches.py`
- `web/routes/_scheduler_compat.py`

**引用链（已逐条复核）**
- `scheduler_run.py:7 _impl=load_scheduler_route_module(".domains.scheduler.scheduler_run")`；`:8 sys.modules[__name__]=_impl`——整模块被替换为 domains 实现的强别名（`web.routes.scheduler_run is web.routes.domains.scheduler.scheduler_run` 为 True，且 import 它不会拉起 registrar，无副作用）。`scheduler_excel_batches.py` 是逐符号 re-export 变体。
- **生产引用**：`grep web/ core/ data/`（含 .py/.html/config/json）对顶层 wrapper 路径**零非测试命中**；`web/routes/__init__.py` 为空（无 re-export）。生产入口是 `web/bootstrap/factory.py:449 importlib.import_module("web.routes.scheduler")`（根入口，非这些 wrapper）；路由注册实际由 `web/routes/domains/scheduler/scheduler_route_registrar.py` 的 `_ROUTE_MODULES`（列 14 个 domains 叶子）`:30 importlib.import_module(f".{module_name}", __package__)` 直接 import domains 真身完成。
- **唯一引用方是 tests/**：`tests/regression_scheduler_wrapper_import_order_contract.py:12 LEGACY_SCHEDULER_WRAPPERS`（列出全部 9 个，并断言 wrapper 自身 import 旁路无副作用）+ `test_sp05_path_topology_contract.py` 的 `ROUTE_COMPAT_MODULES/ROUTE_BEHAVIOR_COMPAT_SYMBOLS` + ~20 个 route-contract 回归。
- **roadmap 明示延期**：`.codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-roadmap.md:522 "先保留旧 wrapper，避免一次改动冲击启动链。"`
- `_scheduler_compat.load_scheduler_route_module` 对缺失目标 `raise ModuleNotFoundError`（无静默兜底，灵魂不变量完好）。

**为何算债**
同一职责两套路径（顶层 wrapper 别名 vs domains 真身），迁移做了一半：真身已搬到 `domains/scheduler/` 并由 registrar 注册，顶层只剩 `sys.modules` 别名，生产代码已不走它们，靠测试续命。属 P3 迁移残渣——但 roadmap 明确记录为**有意延期（降低启动链风险）**，非失忆搁置。

**对抗验证结论（real_debt，原始判定被精化为「确属可收债，但现在删是抢跑」）**
对抗验证裁定删除**安全**（无任何生产安全不变量失守：无预览冒充/无旧版冒充——wrapper 就是现行 leaf 本身/无坏数据吞噬/无跨层违规；启动链 passivity 由 `test_sp05_path_topology_contract.py:484-571` 在**真生产路径**独立守护，删 wrapper 不解除该守卫）。但动手前必须满足三前置：(1) 先认账或修订 roadmap `:522` 的「先保留」延期决定——现在删属**抢跑该决定**，不是安全问题；(2) 把 22 个 test-only 消费者的 `import web.routes.scheduler_xxx` 迁到 domains leaf 路径；(3) 同步删/改两处 wrapper 专属契约：`regression_scheduler_wrapper_import_order_contract.py` 整文件 + `test_sp05_path_topology_contract.py` 的 `ROUTE_COMPAT_MODULES/ROUTE_BEHAVIOR_COMPAT_SYMBOLS` 区块与 `SCHEDULER_REAL_ROUTE_FILES` 清单。

**爆炸半径**
删除这 9 个 wrapper + `_scheduler_compat` 需同步删/改 `regression_scheduler_wrapper_import_order_contract.py`、`test_sp05_path_topology_contract.py` 及十余个 `import web.routes.scheduler_xxx` 的测试。误删会让仍按旧路径 import 的测试断裂。因 roadmap 标注「先保留」，现在动属抢跑。

**处置建议（收口到哪个已存在统一点）**
统一到 `web/routes/domains/scheduler/` 真身 + `scheduler_route_registrar` 注册路径（已是生产唯一路径）。但**此条不建议现在清理**——尊重 roadmap `p1-scheduler-debt-cleanup-roadmap.md:522` 的有意延期，挂到该 roadmap 的 wrapper 清理 PR 里，按上述三前置一次性收口。在那之前保持现状即可，不属于「该立即还的债」。

**复核结论**：✅**证据仍准（行号完全未变）**。9 个 wrapper 文件全部在位，`scheduler_run.py:7-8` 别名样板、`_scheduler_compat.py` 存在且 `raise ModuleNotFoundError`、`factory.py:449` 生产入口、registrar `_ROUTE_MODULES`(14 叶子)、roadmap `:522` 延期句、`LEGACY_SCHEDULER_WRAPPERS:12`(列全 9 个) 均逐条复核为准。

---

### 12.5 【P5｜low｜load_bearing=false】scheduler_navigation_publish.selected_plan_role 是 core schedule_result_view_context.selected_plan_role 的副本

**位置**
- `web/routes/domains/scheduler/scheduler_navigation_publish.py` `selected_plan_role:31-32`（另 `requested_plan_role:27-28` 同理）

**引用链（已逐条复核）**
- web 版 `selected_plan_role:31-32 return str(plan_resolution.get("selected_role") or ROLE_ADOPTED)`。
- 收口点 `core/services/scheduler/schedule_result_view_context.py:201-202 def selected_plan_role(...): return str((plan_resolution or {}).get("selected_role") or ROLE_ADOPTED)`——已存在的统一点。
- `core/services/scheduler/gantt_plan_query.py:46-47` 已做过一次 re-export 包装（`:18 selected_plan_role as _selected_plan_role`，`:46 def selected_plan_role(...)` → `:47 return _selected_plan_role(...)`），是「正好做这种统一」的现成先例。
- web 版被真实调用（非死代码）：`scheduler_week_plan.py:37`(import)、`:337 effective_plan_role=selected_plan_role(plan_resolution)`；`scheduler_gantt.py:29`(import)、`:298 effective_plan_role=selected_plan_role(plan_resolution)`。两处都只作为模板**显示**用 kwarg `effective_plan_role=`，不进任何闸门。

**为何算债**
已有收口点（core `selected_plan_role`）的取值职责在 web 层又私实现一遍，绕过了已存在的统一点。属轻量 P5——3 行 getter，是同概念第三处落地（core 原版 `:201` + `gantt_plan_query` re-export `:46` + 这里 `:28`）。

**对抗验证结论（real_debt，且推翻了原始 finding 的一处事实陈述）**
对抗验证确认是可收的真债，**但推翻了原始 finding「只是 web 版多加 or ROLE_ADOPTED 兜底」这句**——事实正相反：两版都有 `or ROLE_ADOPTED`，且 **core 版更稳健**（`:202` 的 `(plan_resolution or {})` 额外处理了 None）。因此原始 finding 担心的「统一会改变缺 selected_role 时的角色」是**不成立的**——两者对缺失 selected_role 都返回 'adopted'，统一只会保持或增强行为。另外：web 与 core 都 import 同一个 `ROLE_ADOPTED`(`core/models/schedule_plan_role.py:5 ='adopted'`)，无取值漂移；真正的安全闸门(can_dispatch/can_write_feedback/is_scenario_preview/is_superseded_by_newer_version 等)走**独立的** `_PLAN_GUARD_FIELD_NAMES`/`_plan_guard_fields` 路径(`scheduler_navigation_publish.py:12-21,75-86`)，`selected_plan_role` **不是**预览/版本/派工闸门。

**爆炸半径**
改动小且安全：让 web 版直接 re-export core（照搬 `gantt_plan_query.py:46` 写法）即可。等价性已实证，week_plan/gantt 行为不变（仅显示 kwarg）。唯一注意：`requested_plan_role:27-28`（core 无同名函数，等价逻辑内联在 `schedule_result_view_context.py:74-79` 区域）若一并收口需另抽 helper，属清洁度优化、非安全必需。

**处置建议（收口到哪个已存在统一点）**
收口到 `core/services/scheduler/schedule_result_view_context.py:201 selected_plan_role`。把 web 版改为 `from core.services.scheduler.schedule_result_view_context import selected_plan_role`（或照 `gantt_plan_query.py:46` 做一层 re-export）。改后跑 `tests/regression_reports_workbench_navigation_contract.py` 及 week_plan/gantt 回归即可。`requested_plan_role` 可选地一并提一个 core 共享 helper 承载（清洁度优化）。

**复核结论**：⚠️**行号已变（一处消费方 +5）**。web 版 getter `:28-29`、`requested_plan_role:24-25`、core `:201-202`、`gantt_plan_query.py:46-47`、`scheduler_week_plan.py:337` 均复核为准。唯一漂移：消费方 `scheduler_gantt.py` 由旧证据 `:293` 移到当前 `:298`（import 在 `:29`）。core 版更稳健(`:202` 处理 None)这一对抗结论复核为准，原始 finding 的「web 多加兜底」措辞确属事实倒置。

---

## 13 · 增量债 · b08162cd 工作台收口(基准 → 现状)

> 对基准 `65870e47` 之后唯一提交 `b08162cd`("完成报表工作台回跳验收")的同颗粒度 delta 普查。该提交动了 54 个生产文件,把 11 个报表/调度页收口到统一参数合同(reports.py -465 拆成多个新文件,新增 report_context_filters/reports_page_support/scheduler_reports_workbench 等)。
>
> **取证口径**:全部读 `git show b08162cd:<path>`(提交版本),不读工作区——工作区有 in-flight 改动会污染(本提交改的 38 个生产 py 里,有 7 个当前又被未提交工作区二次修改)。
>
> **方法**:4 分区并行 delta 普查 + 1 交叉核验官版本史考古,双信源互证 + 人工亲核关键条目。

### 分区总评:净减债,但增 2 笔承重语义债

`b08162cd` 这次收口**整体方向是减债**:堵掉 web 层私有数值解析、3 处 P4 静默兜底、硬编码 URL,资源归一真收口到单一 collar。代价是新增 2 笔承重/呈现级语义债(N1 护栏字段散 3 抄、N2 关键链子集冒充整版)+ 一批低危死代码残渣。**这正是健康项目演进的典型样态:大重构在堵旧出血的同时,会在新代码的接缝处长出新的失忆债——关键是接缝处的"立约"(注释/收口)有没有跟上。这次没完全跟上。**

---

## 13.0 【更正】原报告"P1 写死常量出血"是幻觉证据(版本史考古)

> 这不是增量债,是对基准报告一条核心结论的**诚实更正**。放在 §13 开头,因为它是用 b08162cd 增量普查的版本史工具才查清的。

**基准报告曾把"execution_review 用写死常量 `ADOPTED_PLAN_RESOLUTION`(reports_page_support.py:36)假冒方案身份"作为头号 P1 实证**,在执行摘要/封面/§90/§12 反复引用,称其为"失忆债最危险形态的实证、唯一已知出血"。

**增量普查证伪了它**:
- `git cat-file -e 65870e47:web/routes/reports_page_support.py` → `fatal: path ... exists on disk, but not in '65870e47'`。**该文件在基准根本不存在**,是 b08162cd 拆分 reports.py 时才新建——所以"基准 reports_page_support:36 有写死常量"在版本史上无法成立。
- `git log --all -S "ADOPTED_PLAN_RESOLUTION"` 全 ref pickaxe → **只命中 stash `725cca79`**("untracked files on codex/...: b08162cd"),且该字符串**只出现在审计自己的 `REPORT.md`/`_consolidated.json` 散文里**,没有任何 `.py` 文件含它。
- execution_review 在 b08162cd:153 调 `host._resolve_plan(v, ROLE_ADOPTED, None)`,真身 `report_plan_helpers._resolve_plan` → `plan_query_service.resolve_plan_view(...)`,`ValueError` 时 `raise ValidationError`——**自基线起即真解析,不存在写死常量假冒**。

**根因**:基准普查取证时读到的"reports_page_support.py:36"是一次工作区 in-flight 中间态(很可能是某个 agent 正在重构 reports.py 时的临时文件),被误当成了"基准事实"。**这是"活工作区污染"陷阱**——也是本报告生成全程反复踩的同一个坑的最深一层。

**处置**:全文凡引用"P1 出血/ADOPTED_PLAN_RESOLUTION 出血"处,应读作"普查快照污染,全项目 P1 真实计数 = 0 且版本史从无此例"。**核心论点不受影响**:承重护栏(execution_review 只复盘 adopted)无注释这条是铁证,独立于这条幻觉 P1 成立。诚实更正自己的错误,正是本项目灵魂线"宁可暴露错误也不自欺"的应用。

---

## 第一部分 · 已修复 / 消除的旧债(基准报告相关条目改标 🔧)

> 这次收口**真的修掉了**基准报告标记的若干债,对应条目的复核状态应更新为 🔧。

### 13.F1 🔧 web 层私有数值解析(疑似第 N 套)已整组删除

- **旧债**:基准 `reports.py:85-101`(65870e47)有 `_report_number`/`_report_nonnegative_int`,基于 `math.isfinite` 私有解析,与 core 解析并存。
- **已修复**:`git grep _report_number b08162cd -- web/` 为空;`reports_export_support.py:44-45` 改为薄封装 core 的 `parse_report_nonnegative_int`。
- **证据**:`git show 65870e47:web/routes/reports.py:85-101` vs b08162cd web 层零命中。

### 13.F2 🔧 报表行计算从 web 路由内联下沉到 viewmodel/exporter

- **旧债**:`reports.py:129-148,416-419`(65870e47)内联利用率换算/汇总求和。
- **已修复**:下沉到 `scheduler_reports_workbench.py:324,343` 与 `exporters/xlsx.py:60`;`reports.py` 收缩为 42 行纯路由。

### 13.F3 🔧 首页超期统计补齐方案/资源/批次全过滤

- **旧债**:`reports.py:150-160`(65870e47)取超期数时只 `engine.overdue_batches(latest_ver)`,丢弃 resource/batch/方案上下文。
- **已修复**:`reports_page_support.py:144-151` 补齐 plan_role/scenario_id/resource_type/resource_id/batch_id 全过滤。

### 13.F4 🔧 三处 P4 静默兜底改 loud(灵魂线落实)

- **旧债**:基准三处坏数据静默兜底——`_pause_duration_label`(`try: float(value or 0.0) except: 0.0`)、`_utilization_percent`(导出 `except: return value` 原样泄漏)、`_delay_text`(裸 `float()`)。
- **已修复**:全改走 `parse_report_float`/`parse_optional_report_float`,空值才给 0、非空非法直接 `raise ValidationError`。
- **证据**:`execution_review.py:377-384`、`exporters/xlsx.py:60-67`、`delay_diagnosis_presentation.py:78-83`。

### 13.F5 🔧 dispatch 现场记录入口 硬编码 URL → 计算值

- **旧债**:resource_dispatch 现场记录入口曾是硬编码字面量 `"/scheduler/resource-dispatch/execution/__OP_ID__/actual"`(不带 query 上下文)。
- **已修复**:改为 `_actual_record_url_template(filters)` 计算值,新实现 `scheduler_resource_dispatch_query.py:125-129`。

### 13.F6 🔧 甘特工作台链接死面包屑被接上消费端

- **旧债**:基准 gantt spec 发出 `resource_type/resource_id/batch_id`,但 gantt 路由(65870e47)根本不读这些键,链接参数全程被丢弃(基准报告 web-all P6 同源)。
- **已修复**:`link_query.py:31-38` 改 `gantt_filter`+`gantt_batch`,`scheduler_gantt.py:214,223,343-349` 新增对 `gantt_resource/gantt_batch` 的读取,面包屑被接上消费端。

### 13.F7 🔧 资源归一真收口(证实基准报告"第 N 套私有资源实现"已解决)

- **已收口**:`report_context_filters.normalize_report_resource_filter`(:119)做完报表特有别名合并(scope_*/machine_id/operator_id)后,在 **:148 委派给规范收口点 `normalize_schedule_resource_filter`**,不重复校验。报表全部入口经此一点:report_engine `:146/167/279/383`、web `request_resource_context.py:39`、`reports_request_support.py:54`;SQL 侧 `schedule_resource_sql_filters` 也 delegate 到同一 collar。
- **派工 team 轴非 P5**:resource_dispatch 不走此 collar 是因为有 team(班组)第三轴——collar 的 `SUPPORTED={machine,operator}` 表达不了,靠 SQL `(o.team_id=? OR m.team_id=?)` 双 join(基准报告 §90 LB-B 同源的承重不对称,b08162cd 未触碰)。刻意两轨并存,不是绕收口点。

---

## 第二部分 · 新引入的债(N1–N14)

### 承重级(高优先)

### 13.N1 【P5 · high · load_bearing=TRUE】⚠️execution_review 放行护栏依赖的 plan-guard 字段投影被切成 3 套手维 key 列表(本轮新增 2 份)

**位置**
- `git show b08162cd:web/viewmodels/scheduler_reports_workbench.py:40-53`(新增)
- `git show b08162cd:web/routes/domains/scheduler/scheduler_navigation_publish.py:12-21,72-85`(新增)
- 对照既有 `git show b08162cd:web/routes/domains/scheduler/scheduler_resource_dispatch.py:63-73`(基准已存在)

**引用链**
- 唯一应有收口点是 `schedule_result_view_context.py:277 plan_role_filter_fields`(一次性产出 requested_plan_role/effective_plan_role/plan_role_status/is_comparison/is_scenario_preview/is_superseded_by_newer_version/can_dispatch/can_write_feedback 全集)。
- 但 `build_workbench_plan_context`(`scheduler_workbench_links.py:183`)的入参**根本不承载这些 guard 字段**,只接受 plan_role/is_preview/can_write_feedback。
- 于是三处各自在 builder 输出后手工"补挂":reports_workbench 从 resolution 命名 `requested_role`/`selected_role` 映射(:42-48);navigation_publish 走 `plan_role_filter_fields` 取 8 键(:13-21);resource_dispatch 从 filter 命名 `requested_plan_role` 直拷 6 键(:64-72)。
- 下游 `_is_formal_adopted_context`(`scheduler_workbench_links.py:271-287`)正是读这些补挂字段(requested_plan_role/effective_plan_role/is_comparison/is_superseded_by_newer_version/scenario_id)来判 execution_review 是否放行。

**为何算债**:收口点 `build_workbench_plan_context` 不承载 guard 字段,导致"把方案护栏字段投进工作台上下文"有 **3 份私有实现**,且源键命名两套(`requested_role` vs `requested_plan_role`)、键集合三样(reports/resource 各 6 键无 plan_role_status,navigation 8 键)。**execution_review「只复盘正式采用方案」这条灵魂护栏的正确性被拆散到 3 张手维列表里**——任何一处漏拷 `is_superseded_by_newer_version`/`is_comparison`,旧正式版本就会被 `_is_formal_adopted_context` 判成 True 而放行写链接,正是 commit message 自己强调要防的"旧正式版本冒充现行正式采用方案"。本轮把这个脆弱模式从 1 处扩散到 3 处。

**爆炸半径**:报表中心/超期/利用率/停机/计划现场实际全部入口卡 + 行级动作,加甘特/周计划/分析/资源派工导航上下文,全依赖手拷字段的完整性;漏一键即 execution_review 写侧护栏静默失效。

**处置建议**:把 guard 字段投影收口进 `build_workbench_plan_context`(让收口点承载这些字段,从 `plan_role_filter_fields` 单一来源产出),删除三处手维拷贝。这是把"护栏正确性"从 3 张易漂移的手维列表收回单一权威点。**这是本提交最该回收的承重语义债。**

**复核结论**:✅ 证据仍准(已亲核三处 def 在 b08162cd 并存:`reports_workbench.py:40`/`navigation_publish.py:72`/`resource_dispatch.py:63`)。

### 13.N2 【呈现失真 · medium · P1 气味】筛选后的关键链把"周窗口子集"喂进"要求整版输入"的算法,以整版 makespan 对外且无 scope 标记

**位置**:`git show b08162cd:core/services/scheduler/gantt_service.py:335,340,375-377` + `gantt_service_support.py:57`

**引用链**
- `scheduler_gantt.py:347-349` `gantt_resource` 存在时 `resource_type=view; resource_id=gantt_resource`(含 :346 batch_id)→ `get_gantt_tasks` → `gantt_service.py:335` plan_detail_filter_kwargs → :340 `list_plan_detail_rows_between_for_resolution(**detail_filters, start_time=wr.start_str, end_time=wr.end_exclusive_str)`(**既按周窗口又按资源/批次过滤的 rows**)→ :375 `critical_chain_for_plan_detail_filter(rows, detail_filters)` → `gantt_service_support.py:57 compute_critical_chain_from_rows(rows)`。
- 无 filter 时(:376 None)才回落 provider,对全版 `list_by_version_with_details(version)` 计算。
- `compute_critical_chain` 文档不变量明示"输入:某一 version 的**全量排程(不按周截断)**"(`gantt_critical_chain.py:347`)。

**为何算债**:新路径喂的是窗口+过滤子集,算出的 ids/edges/makespan_end/edge_type_stats 只描述该子集,却经同一 contract 以 `available:True`、相同 `makespan_end`/关键链 UI 键对外,**无任何 scope=filtered 标记**区分。用户筛到单台设备/单批次时看到的"关键链"和"makespan"其实是子集内部链,被当成整版计划呈现。基准报告(`_load_bearing.json` 的甘特条目)只论两路归一一致、未察觉窗口/整版输入分叉,**此为漏网**。

**爆炸半径**:只读显示正确性——只要 gantt 带任一 resource/batch 过滤,关键链/makespan 数值即偏离整版计划真值且无提示;不损坏数据。

**处置建议**:在 contract 输出加 `scope: "filtered" | "full"` 标记,filtered 时 UI 明示"当前为筛选范围内的局部关键链"。或确认这是渲染刻意设计(若是,补注释说明为何 filtered 也叫 available)。

**复核结论**:⚠️ 中等置信(可能为渲染刻意设计但缺 scope 标记使其失真),建议 owner 确认设计意图。

### 13.N3 【P2 · medium · load_bearing=TRUE】⚠️navigation_context 的 execution_review 护栏靠 endpoint/path 字面量匹配且零注释(整文件新增)

**位置**:`git show b08162cd:web/navigation_context.py:42-47`(`_is_execution_review_request`)+ `:80-82`(`plan_role = ROLE_ADOPTED if is_execution_review else ...` / `scenario_id = "" if is_execution_review`)

**引用链**:`render_bridge.init_ui_mode` 把 `build_*_navigation_links` 注入 Jinja globals(`render_bridge.py:73-91`)→ 每页渲染调 `navigation_context.current_workbench_navigation_context()` → 命中 execution_review 分支强制 adopted/清空 scenario_id。判定靠 `endpoint == "reports.execution_review_page"` 或 `path == "/reports/execution-review"` 字面量匹配。

**为何算债**:这是 commit 自述的灵魂护栏("旧正式版本不能再被显示成现行正式采用方案"),属承重逻辑;但落地方式是路由名/路径**字面量匹配**,且全程无一行注释说明"为何复盘页必须剥离 plan_role/scenario_id"。`navigation_context.py` 整个文件是 b08162cd 新增——**这是本提交新引入的最脆弱承重点**:一旦未来有人重命名该路由或"顺手"删掉这个 if 特例,护栏静默失效、scenario_id 重新渗入复盘页导航,本地无任何阻止信号。

**爆炸半径**:全站导航 chrome;复盘页一旦泄漏 scenario_id,正式方案复盘会被模拟方案身份污染,直接违背本次收口目标。

**🔧 该补注释**(贴在 `navigation_context.py:80` 上方):
```python
# 故意:复盘页(execution_review)强制 plan_role=adopted、scenario_id="",剥离 request 的方案身份。
# 这是护栏——计划和现场实际只复盘正式采用方案,放开会让模拟预览/旧正式版本冒充现行正式复盘。
# 勿删此 if 特例,勿因重命名路由而让 _is_execution_review_request 失配(它靠 endpoint/path 字面量)。
```

**复核结论**:✅ 证据仍准(navigation_context.py:42-47,80-82 已核,整文件 grep `#` 护栏注释零命中)。

### 13.N5 【P2 · low · 护栏削弱】navigation_publish 把 builder 已 gate 的 can_write_feedback 覆盖回未门控值

**位置**:`git show b08162cd:web/routes/domains/scheduler/scheduler_navigation_publish.py:79-84`

**引用链**:`_publish_context` 先以 `can_write_feedback=guard_fields.get("can_write_feedback")` 调 `build_workbench_plan_context`——builder 内 `_feedback_guard_context`(`scheduler_workbench_links.py:145-157`)把它 gate 成 `can_write and formal_adopted`;随后 :83 `context.update(guard_fields)` 又用未 gate 的原始值(来自 `plan_role_filter_fields`,恒为 bool 故必被纳入)覆盖回去,**撤销了 builder 的门控**。

**为何算债**:写侧护栏(只有 formal_adopted 才可写现场记录)在 builder 里建好,又被发布层无注释地拆掉一半。当前低危——写链接放行实际走 resource_dispatch 的 `can_emit_feedback_write_urls`(读 filters,非此 nav context),故该覆盖暂未被消费;但 nav context 的 can_write_feedback 已是"非门控真值",一旦未来有人据此渲染写按钮即破。

**爆炸半径**:当前零(未被消费);潜伏——未来据 nav context 渲染写按钮会绕过门控。

**处置建议**:`:83 context.update(guard_fields)` 前剔除 `can_write_feedback`,或改用 builder gate 后的值。属潜伏护栏债,优先级中。

**复核结论**:✅ 证据仍准。

### 低危残渣(N4 / N6–N14)

### 13.N4 【P3 · medium】导航上下文双构建路径:fallback 直接信任未经 PlanIdentity 解析的 raw plan_role/scenario_id

**位置**:`git show b08162cd:web/navigation_context.py:76-98`(override 路径 :77-78 用真实 plan_resolution;fallback 路径 :80-98 用 `_request_arg("plan_role")`/`_request_arg("scenario_id")`,:87 `plan_role or ROLE_ADOPTED`)

**为何算债**:页面 context 已发布时走 override(经真实 PlanIdentity);未发布(报错页/其它 scheduler 页)走 fallback,只把 `request.args` 的 plan_role/scenario_id 原样塞进导航链接,**不向 schedule_plan_query_service 求证**。除 execution-review 外的页面若带 `?plan_role=adopted&version=<已被取代的旧版>`,fallback 生成的导航链接仍按 adopted 透传——这正是 commit 想消灭的"显示层自欺",只在 publish 路径和 exec-review 特例堵住,**generic fallback 仍是漏的**。两套路径对"当前方案身份"各执一词。

**爆炸半径**:非复盘页的跨页回跳链接 query 参数;下游页面会按透传的 plan_role 重新取数,可能在旧版本上误标 adopted。

**处置建议**:fallback 路径也经 `resolve_plan_view` 求证,或明示 fallback 链接不带未验证的 plan_role。属半截收口,中优先。

**复核结论**:✅ 证据仍准。

### 13.N6 【P5 · low】parse_report_nonnegative_int 手搓正则绕过 strict_parse 收口点(刚收口就开后门)

**位置**:`git show b08162cd:core/services/report/report_number_parsing.py:9,54-70,73-90`

**引用链**:`report_engine._export_nonnegative_int`(:71)→ `parse_report_nonnegative_int` → `_parse_plain_report_int`(自带 `_INT_TEXT_PATTERN=re.compile(r"^[+-]?\d+$")`,自行判 bool/int/str);web `reports_export_support.py:45` 也用它。**对照同文件 3 个兄弟函数**:`parse_report_int`(:48 委派 `parse_required_int`)、`parse_report_float`/`parse_optional_report_float`(委派 `parse_required_float`)——**唯独它例外**。

**为何算债**:已知收口点是 `parse_finite_int`/`parse_required_int`(`core/shared/strict_parse.py:46,81`)。`_parse_plain_report_int` 是第二套私有整数解析,且**语义漂移**——收口点走 `float(value)` 接受 `"2000.0"` 这类浮点文本,私有版正则只认纯整数会拒掉。本可用 `parse_required_int(value, min_value=0)` 表达"非负"。无注释说明为何不复用,也无 parity 测试钉死差异。同文件已亲核 :25/:49 兄弟都委派,唯它手搓。

**爆炸半径**:导出行数档位决策(direct/stream/reject)与 web 导出表单整数参数;收口点语义若调整,此副本不跟随。

**处置建议**:改用 `parse_required_int(value, min_value=0)`,删除 `_INT_TEXT_PATTERN` 与 `_parse_plain_report_int`。属真债清理册第四档(语义需对齐:确认是否真要拒 `"2000.0"`)。

**复核结论**:✅ 已亲核(report_number_parsing.py:9 有 `_INT_TEXT_PATTERN`,:25/:49 兄弟委派 `parse_required_*`)。

### 13.N7 【P6 · low】plan_id 死面包屑被合同字段表正式承认却全链零消费(坐实基准 web-all P6)

**位置**:`git show b08162cd:web/viewmodels/scheduler_workbench_link_query.py:118,154`(`_append_param(query,"plan_id",...)`);注入点 `scheduler_reports_workbench.py:73`、`navigation_context.py:86`、`reports_page_support.py:98,135`;合同字段表 `scheduler_navigation_links.py:12 _REPORT_CONTEXT_FIELD_NAMES`、`reports_export_support.py:14`

**引用链**:`build_report_context(plan_id=)` → `build_workbench_plan_context(plan_id=)`(`scheduler_workbench_links.py:229 "plan_id":_text(plan_id) or None`)→ `query_for_target` → 拼进所有目标页 URL(含 execution_review,`link_query.py:154`)。**反向核查**:`git grep plan_id b08162cd -- core/ data/` 仅命中无关的 `_plan_idempotency_keys`;web 层无 `args.get("plan_id")` 作为解析键——版本身份解析全程用 version+plan_role+scenario_id(`resolve_plan_view`),plan_id 从不参与取数。

**为何算债**:收口收的是"统一参数合同",plan_id 被**正式写进合同字段表**并落进每条链接 query,但没有任何页面用它定位方案——是一个"被合同正式承认却永不消费"的承重感面包屑,读者会误以为 plan_id 是身份主键。这坐实了基准报告 web-all 的 plan_id P6,且这次收口**把它制度化了**(进了字段表)。

**爆炸半径**:所有工作台/报表链接 URL 都多挂一个无效 plan_id 参数;误导后续维护者按 plan_id 做方案解析。

**处置建议**:从 `_REPORT_CONTEXT_FIELD_NAMES` 与 link_query 移除 plan_id,或明确文档化它是"保留字段未启用"。注意:基准报告记过 `back_to`(回跳头牌参数)也 threaded 但零渲染,但 design doc:225 写明 back_to/plan_id 是"保留为返回上下文未必渲染"——**back_to 是有意延期(在途,非债),plan_id 是真死面包屑**(无任何消费者且非延期渲染目标)。

**复核结论**:✅ 证据仍准(双信源互证:本轮 + 上轮失败 workflow 的深度调查均独立得出)。

### 13.N8 【P6 · low】filter_plan_rows_for_report_context 出生即死(实际过滤在 SQL 层)

**位置**:`git show b08162cd:core/services/report/report_context_filters.py:160-187`(含 helper `_plan_row_matches_batch`:160、`_plan_row_matches_resource`:164)

**引用链**:全仓 grep `filter_plan_rows_for_report_context` 仅命中定义 + `tests/regression_report_context_filters_contract.py`(:66/75/81)。孪生函数 `filter_downtime_rows_for_report_context`(:274)被 `report_engine.py:406` 真用;但计划行的 resource/batch 过滤**实际由 repo SQL 完成**(`schedule_resource_sql_filters.append_detail_filters` → `report_engine._list_plan_rows_between` 传 resource_type/resource_id/batch_id 下钻),Python 侧这套行匹配无人调用。

**为何算债**:新文件里一段 40 行完整实现 + helper,只有合同测试供养(给"存活"假信号),无任何生产路径触达。维护者会误以为报表计划行在此处 Python 过滤,实际走 SQL,误导理解。

**爆炸半径**:运行期为零(死);维护成本 + 测试覆盖率虚高 + 对"过滤发生在哪层"的误导。

**处置建议**:删除该函数 + helper + 退对应合同测试断言。属真债清理册第二档。

**复核结论**:✅ 证据仍准。

### 13.N9 【P3 · low】execution_review 三档标签(display/identity/export)被压扁成同值,旧键+模板分支+导出回退沦为死分支未清

**位置**:`git show b08162cd:core/services/report/execution_review.py:337-348`(`_resource_pair_payload` 现 `return {"display_label": display, "identity_label": display, "export_label": display}` 三键恒等)、:287-292、:304-305、:311-312

**引用链**:模板 `templates/reports/execution_review.html:131,132,135,136` 的 `{% if ..._identity_label and ..._identity_label != ..._label %}` 守卫现恒为 False → `text-meta` 副行永不渲染;导出 `exporters/xlsx.py:410-415` 的 `row.get("..._export_label") or row.get("..._label")` 中 `or` 永不回退,且 `_export_label` 名实不符。

**为何算债**:半截简化——三档身份系统被掏空成单值,但键名、模板 `!=` 分支、导出 `or` 回退三处消费方全部留存为 no-op,API 仍对外宣称有 identity/export 变体却零信息差。后续若要恢复真实身份渲染,无法区分这是有意压扁还是 bug。

**爆炸半径**:模板一段死分支 + 导出一段死回退 + 每资源 3 个重复键;阅读/演进误导,低运行期风险。

**处置建议**:若确定不再需要三档,删除 identity/export 键 + 模板 `!=` 分支 + 导出 `or` 回退,只留单 `_label`;若要保留三档能力,恢复真实拼装。属真债清理册第二档。

**复核结论**:✅ 证据仍准。

### 13.N10 【P5 · medium】_normalize_critical_chain_result 被逐字复制成第二份(support vs provider)

**位置**:`git show b08162cd:core/services/scheduler/gantt_service_support.py:32-50` vs `gantt_critical_chain_provider.py:104-128`(基准即存在,UNCHANGED)

**引用链**:`gantt_service.py:21` import `critical_chain_for_plan_detail_filter` → :375 有 detail_filters 时走 support 路径 → `gantt_service_support.py:54-58` → :32 `_normalize_critical_chain_result`;另一份在 provider 走无 filter 路径(`gantt_service.py:377`)。两路汇入同一 `build_gantt_contract` → `gantt_contract.py:19 _public_critical_chain` 白名单复核。两文件都已 `from .gantt_critical_chain import ...`,存在天然公共落点。

**为何算债**:b08162cd 抽 support 模块时,本可 import provider 已有的同名 staticmethod 或抽公共 helper,却又写了一份逐字段语义相同的副本(provider 版与 support 版 diff 后无差异)。**这正是基准报告 §91 第三档记过的 `_normalize_critical_chain_result` 重复(当时标 git status `A` 未提交、需问在途作者)——现在 b08162cd 把它提交了,坐实为 P5**。归一调用本身承重(raw `compute_critical_chain_from_rows` 缺 available/edge_type_stats 默认),但第二份物理副本不提供额外保证。

**爆炸半径**:任何人给关键链 reason_code/edge_type_stats schema 加键,只改一处 → filtered(support)与 unfiltered(provider)两路 payload 字段不一致,且需第三处 `gantt_contract.py:19` 白名单同步。

**处置建议**:抽公共 helper 或让 support 复用 provider 的 staticmethod(两文件都已 import gantt_critical_chain)。属真债清理册第三档。

**复核结论**:✅ 证据仍准(与基准 §91 第三档闭环:那条"未提交待问作者"的债已落地为已提交 P5)。

### 13.N11–N14 死代码/半截残渣(简列)

| 编号 | 病理 | 位置(git show b08162cd:) | 一句话 |
|---|---|---|---|
| **N11** | P6/low | `web/viewmodels/scheduler_navigation_links.py:66` | `_has_navigation_date_range` 新建即死,全仓零引用 |
| **N12** | P6/low | `web/viewmodels/scheduler_navigation_links.py:74-78,160` | `_target_url` 死分支:9 条 spec 第 3 字段全非空字面量,`plain_url or _target_url(...)` 中 plain_url 恒真 |
| **N13** | P6/low | `web/viewmodels/scheduler_reports_workbench.py:141-154` | `_context_summary` 死函数(私有副本,真实现在 `scheduler_workbench_links.py:254`) |
| **N14** | P3/low | `web/request_resource_context.py:20-28` + `reports_request_support.py:53-61` + `reports_export_support.py:13-29` | 资源 6 参数名清单三处各抄一遍(收口点没绕,维护性半截) |

> N11–N13 属真债清理册第一/二档(grep 实证零引用,可直删);N14 属第三档(把 6 别名清单收口到单一常量供三处 import)。

---

## 第三部分 · 承重护栏新状态(更新 §90)

### 13.G1 execution_review「只复盘正式采用方案」纵深三层 —— 保留,四文件零注释

交叉核验官对 4 个承载文件逐一 grep `#` 注释 + `故意/刻意/不对称/不收/forbidden`——**四处全部零解释性注释**(命中的全是 UI 文案、错误消息、变量名 `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS`)。当前硬钉 ROLE_ADOPTED 行(execution_review 服务层):`:112,123`(取数分支)、`:153`(`_resolve_plan`)、`:166-167`(返回 dict);签名 `execution_review(version, *, date_from, date_to, batch_id, resource_type, resource_id)` 结构性无 plan_role/scenario_id 形参。落点另两层:路由 `reports_page_support.py:367,388`、导航 `navigation_context.py:80-82`。

→ **这是基准 §90 LB-A 族的现状确认 + 扩展**:基准记了 web 路由/service 签名/写侧反馈三层,现增加 **navigation_context 这第四个承载点**(b08162cd 新增,见 13.N3),且它靠路由名字面量匹配,最脆弱。§90 应补 navigation_context 这一处 + 13.N3 的注释文案。

### 13.G2 新 collar schedule_resource_filter 只支持 machine/operator,对 team/empty-id 一律 raise(loud)—— 新增无注释

**证据**:`git show b08162cd:core/models/schedule_resource_filter.py:8 SUPPORTED={machine,operator}`、:19-24 column_name 对 team 返 `''`、:54/60/66 三处 `raise ValidationError`。基准报告 §90 LB-B 同源(`column_name('team')==''` 而 `has_filter('team')==True` 的陷阱),precondition 要求"先扩 collar 再统一"。**文件零注释说明 team 排除与 empty-id 拒绝是刻意的、不可裸扩。** dispatch 的 team 双 join(`schedule_plan_query_repo.py:452-462`)在 b08162cd 中 0 改动,仍是 collar 表达不了、必须两轨并存的承重逻辑。

### 13.G3 ✅【正向】is_superseded → "历史正式方案(已被新版本替代)"标签 —— b08162cd 新增的反自欺护栏

**证据**:`git show b08162cd:core/services/scheduler/schedule_plan_identity_builder.py:76-77`(`_is_superseded_version`:version<latest)、:61-62(label 分支)、:166(`build_plan_identity` 接线);基准 65870e47 的 `_identity_user_label` 无此分支。

→ **这是本提交针对"显示层自欺"的灵魂线正向补强**:旧正式版本现在会被明确标成"历史正式方案(已被新版本替代)",而非冒充"现行正式采用方案"。**值得记一笔正面**——b08162cd 不只是减债,还主动加固了一道反自欺护栏。建议补注释说明它守的不变量(防旧正式冒充现行),让未来 LLM 知道这个标签是护栏不是装饰。

---

## §13 小结

| 维度 | 结论 |
|---|---|
| 净效果 | **减债 > 增债**:堵掉 web 私有数值解析、3 处 P4 静默兜底、硬编码 URL;代价是 2 笔承重语义债 + 一批低危残渣 |
| 最该回收 | **N1**(护栏字段散 3 抄,收口进 build_workbench_plan_context)+ **N2**(关键链子集冒充整版,补 scope 标记) |
| 最高杠杆免疫 | **N3** navigation_context 护栏补注释(13.N3 文案)+ §90 execution_review 族补注释(基准已给文案) |
| 正向亮点 | **G3** 新增 is_superseded 反自欺护栏(灵魂线正向补强) |
| 元更正 | **13.0** 原报告幻觉 P1 经版本史考古证伪,已诚实更正 |
| 未修复存量 | `gantt_critical_chain.py:84` 静默丢坏时间行(基准甘特 P4)b08162cd 未碰 |

---

## 13.5 · 工作树 in-flight 漂移说明(复核基线钉死 + 超前治理记录)

> 本节由全面核查(19 节级 subagent + 全局对账)新增,解决一个被抓出的**基线漂移**问题:报告各节"证据仍准/未改动"的复核结论,基线是提交 `b08162cd`;但当前工作树有 **staged 未提交**的 in-flight 改动,使部分被引文件已偏离 `b08162cd`。

### 复核基线声明

**本报告全部 `file:line` 与"复核为准/证据仍准"结论,基线 = 提交 `b08162cd`(当前 HEAD)。** 工作树另有 13 个生产文件处于 staged-未提交状态(见下),不属"现状提交"范畴,但其中一条改动**直接命中并超前治理了本报告记录的一笔债**,如实记录于此,避免读者拿"未改动"的复核结论去指导一个已在治理中的债。

### 工作树相对 `b08162cd` 漂移的 13 个生产文件(git diff 实证)

| 文件 | 改动量 | 性质 |
|---|---|---|
| `core/services/scheduler/schedule_plan_identity_builder.py` | +13/-20 | **治理 5.4 P4 债**(见下) |
| `core/models/schedule_plan_identity.py` | +4 | 新增 `result_summary_parse_failed/_reason` 两键(坏数据可见标记) |
| `core/models/schedule_plan_resolution.py` | +2 | 透传上述两键 |
| `web/routes/reports_plan_template_fields.py` | +2 | 消费 `result_summary_parse_failed` |
| `web/routes/dashboard.py` | +134/-35 | 独立重构(值班台取数下沉,与本报告债无直接关系) |
| `web/viewmodels/dashboard_workbench.py` | +49/-19 | guard 字段集扩展(is_scenario_preview/is_comparison/is_superseded_by_newer_version) |
| 其余 7 文件(navigation_publish/resource_dispatch/workbench_links/dashboard_workbench_cards 等) | 各 +2~8 | guard 字段投影/透传微调 |

### ⚠️ 超前治理:5.4 / LB-B4 的 P4 静默兜底债,工作树中**已被治理**

- **基准 `b08162cd` 状态(本报告 5.4 与 §90 LB-B4 记录的)**:`schedule_plan_identity_builder.py:24-29` 的 `_bool_from_summary` 用 `except (TypeError, ValueError): return False` 静默吞坏 `result_summary` JSON。
- **工作树现状(git diff 实证)**:`_bool_from_summary` 已删,替换为 `_parsed_summary_flag_is_true(parsed, key, *, fail_closed=False)`(基于 `parse_result_summary_payload`),在 `:141` 以 `fail_closed=True` 调用(坏 JSON 在 is_simulation 闸上 fail-closed = 判为模拟 = 安全方向);并在 `to_dict` 新增 `result_summary_parse_failed/result_summary_parse_reason` 两键,把"summary 解析失败"沿 identity→resolution→template_fields 全链路**显式暴露**。
- **裁定**:这**正是 5.4 处置建议"坏数据可见的非致命标记"所要求的**,方向与灵魂线"坏数据不准静默兜底、宁可暴露错误"一致。**5.4 / LB-B4 的"✅证据仍准(对 b08162cd)"成立,但读者应知该债在工作树中已进入治理(待提交后可改标 🔧)。**
- 注:5.4 的其余安全论证(`_BLOCKED_RESULT_STATUSES` Gate1 先于 summary gate、危险动作闸 can_write_feedback)在工作树中仍全部成立,不受影响。

---

## 14 · 第三方 drift 复核(三信源对账)

> 在两遍法(Pass-1 Agent 自由取证 A + Pass-2 NetworkX 调用图机械列嫌疑 B)之外,引入**第三个完全独立、不懂本项目架构的探测器** drift-analyzer 2.51.1(C),对全项目做结构腐蚀扫描,回答一个问题:**一个外来的、只懂"AI 通病"的工具,能不能指出本审计两遍法都漏掉的真出血?**
>
> **取证口径**:drift 扫当前 HEAD `b08162cd` 工作区,产物 `evidence/SemanticDebt/drift/drift-baseline.json`(1606 findings / grade C / 669 文件 / 5918 函数)。本节所有"审计盲区"判定 = drift 标记的组 ∩ (该组涉及文件**不在**审计 findings 引用的 352 个 .py 内),即 **B−A 透镜**的第三方版本。明细见 `evidence/SemanticDebt/agent/drift-mds-blindspot.json` 与 `drift-agent-brief.md`。

### 14.0 总裁定:审计核心结论**站得住**,drift 补了一层"微重复"盲区地图

`drift` 没有推翻本审计任何结论,也**没有指出任何审计漏掉的真出血**(P1/承重护栏/灵魂线层面)。它的增量贡献是:在审计**注意力盲区**(salience-biased,盯承重墙/灵魂线/收口点等"大件",自然忽略 4 行小工具函数的重复)里,补出一批 MDS 细粒度重复。

**权威计数(以 `drift-mds-blindspot.json` 的 `_meta` 为唯一真相源,脚本机械去重得出,见 14.0b 口径说明)**:drift 的 MDS 信号共 **28 组**去重重复;按盲区透镜划分——**文件级盲区 15 组**(审计 findings 从未引用该组涉及的任何文件)、**符号级盲区 25 组**(审计从未单独点名该重复符号,是更严的盲区定义)。其中 **5 组**(14.D1–D5)落在承重/灵魂线敏感区或关联已知承重债,值得记进真债清理册;其余为低危 P5 微重复。**全部 28 组已逐行亲核两侧源码。**

这与 §92 方法论自陈的局限闭环:两遍法对"大件"召回强,对"散落微重复"召回弱;第三方机械全扫正好补这一格。

### 14.0b 【方法修正】盲区透镜:文件级 → 符号级(附计数订正)

本节数字几经修订一度自相矛盾(曾出现 17/24 等),已统一锚定到确定性脚本对干净审计基线(剔除 §14 自身文本,避免自污染)的重算结果。两种盲区粒度并存,定义如下:

- **文件级盲区(15 组)**:该重复组涉及的所有文件都不在审计 findings 引用的文件集内——审计连文件都没碰。
- **符号级盲区(25 组)**:审计从未单独点名该重复**符号**(可能碰过文件但没提这个函数)——更严的盲区定义,故数更大。
- 两者非互斥,文件级盲区 ⊂ 符号级盲区。MDS 去重组总数 **28**。

⚠️ 此前版本误用"17 组/24 组/补 7 组"等数字,且 evidence JSON 的 `_meta` 一度被本节文本自污染成 4/2,均为错误,以本段 **28/15/25** 为准。全部 28 组已逐行读两侧源码,无一例藏有比"重复"更重的病(无新静默兜底、无降级分叉)。其中关联已知承重债的见 14.D4(LB-B2 配料表)、关联 N1 家族的见 14.D5。


### 14.1 三信源对账表

| 类别 | 去重组数 | 裁定 |
|---|---:|---|
| drift 真分叉信号(MDS+PFS) | 91 | — |
| 审计已覆盖(A∩B∩C 三方都碰) | 48 | 互证,无新发现 |
| PFS 目录级"错误处理 N 种写法"统计 | 26 | **噪音**:目录级聚合指标,非具体债,丢弃 |
| **MDS 去重组总数** | **28** | 全部已逐行亲核 |
| **├ 文件级盲区**(审计没碰文件) | **15** | B−A 透镜·文件级 |
| **└ 符号级盲区**(审计没点名符号) | **25** | B−A 透镜·符号级(更严) |

> ⚠️ **工具口径校准(已写入 `drift-agent-brief.md` 与 semantics/README)**:
> - drift 的 **AVS「Architecture Violation」≠ 本审计的「分层违规」**。drift AVS=154 实为 Martin 不稳定度耦合指标(`A.py -> B.py 不稳定依赖`),**非有向越层**;本项目 AST 全量分层违规仍是 **0**。勿把 154 条 AVS 当 154 处越层。
> - drift 的 **MDS「Exact duplicates」里有真护栏**:它独立命中 `normalization_matrix._merge_aliases ↔ boolean_normalize`(=审计 §90 **LB-B1 承重双实现**)并建议"删重复"——而删它会撞分层红线。**这坐实:drift 结果必须过 Agent 语义法医,不能直接采信"删重复"建议。**

### 14.2 值得记进真债清理册的 5 组(14.D1–D5,已亲核两侧代码)

#### 14.D1 【P5 · medium · 灵魂线敏感】`_meta_bool_state` 降级判定逻辑逐字两份

- **位置**:
  - `core/services/scheduler/summary/schedule_summary_degradation.py:123`
  - `core/services/scheduler/summary/schedule_summary_downtime_degradation.py:30`
- **亲核**:约 20 行逐字相同——`meta[key]` 的 bool/int(0,1)/str 多态解析 + `(value, used_default)` 二元返回。两文件 diff 后该函数无差异。
- **为何算债**:这是**降级语义的判定核心**(某 meta 字段是否触发降级、是否回落默认)。两份手维拷贝,改一份漏一份 → 同一份 meta 在普通降级路径与停机降级路径上**判定分叉**,正中灵魂线"降级语义不一致、坏数据静默走不同分支"。性质同 §90 LB-B1,但审计两遍法未扫到此对(两个 summary degradation 文件都不在审计 findings 引用集内)。
- **爆炸半径**:降级摘要正确性——两条降级路径对同一 meta 给出不同 used_default,影响 result_summary 对外的降级标记。
- **处置**:抽公共 `_meta_bool_state` 到两文件共同上游(summary 包内),或收到 `core/shared`;收敛前补 parity 测试钉死两份等价。属真债清理册第三档。

#### 14.D2 【P4 气味 · low · 护栏文件】`_op_seq` 两份 + 均静默兜底,其一在护栏文件内

- **位置**:
  - `core/services/scheduler/run/schedule_execution_persistence_guard.py:48`(**护栏文件**)
  - `core/services/scheduler/run/schedule_input_runtime_support.py:19`
- **亲核**:逐字两份 `int(getattr(op,"seq",0) or 0)` + `except (TypeError, ValueError): return 0`。
- **为何算债**:重复本身低危,但(a)其一落在 execution persistence **护栏文件**内,概念应单一来源;(b)两份都 `except: return 0` 静默吞坏 seq——若 op.seq 是脏字符串会被静默当 0 参与排序,属 P4 静默兜底死角(同 §90 LB-B4 家族的容忍性兜底,但此处无"老库行"理由背书)。
- **爆炸半径**:工序排序键;坏 seq 静默归 0 可能扰乱 persistence guard 的 revision 校验顺序。
- **处置**:收口到单一 `_op_seq`;评估 `except` 是否应改为对脏值 loud(护栏文件内更应暴露)。属真债清理册第三档 + P4 复评。

#### 14.D3 【P5 · low · 主链】`_raise_schedule_empty_result` 逐字两份

- **位置**:
  - `core/services/scheduler/schedule_service.py:46`
  - `core/services/scheduler/run/schedule_input_collector.py:79`
- **亲核**:逐字两份——构造 `ValidationError(message, field="排产")`、塞 `details["reason"]`、raise。
- **为何算债**:主链"空结果报错"的同一段异常装配两份。改其一(如加字段)漏其二 → 两条空结果路径报错结构分叉。低危(都是 loud raise,不踩灵魂线),纯收口卫生。
- **爆炸半径**:排产空结果的错误体结构一致性。
- **处置**:收口到单一 helper(主链共同上游)。属真债清理册第二档。

#### 14.D4 【P3 · medium · 承重关联 LB-B2】config 双栈(model↔service)逐字复制函数群——LB-B2 的"配料表"

- **位置**(model 栈 ↔ service 栈,逐字两份):
  - `_float_matches_choice`:`core/models/schedule_config_runtime_coercion.py:31` ↔ `core/services/scheduler/config/config_field_coercion.py:45`
  - `_normalize_valid_texts`:`schedule_config_runtime_coercion.py:49` ↔ `config_field_coercion.py`
  - `_coerce_degradation_event`:`core/models/schedule_config_runtime_read.py:68` ↔ `core/services/scheduler/config/config_snapshot.py`
  - 近似:`ensure_schedule_config_snapshot ↔ _build_schedule_config_snapshot_from_runtime_cfg`(84%,跨同两栈)
- **为何重要**:§90 **LB-B2「双 ScheduleConfigSnapshot 栈锁步同步」**只说"两栈靠人工锁步、加字段须两栈同改",但**未列出具体被复制的函数**。drift 把它们逐个揪出——这是 LB-B2 承重债的**下层实证/配料表**:不仅 snapshot dataclass 双份,连 coercion/校验的私有 helper 也整组双份。任一份单边改 → 算法栈与配置页栈对"同一份配置"的强制/降级判定分叉(踩 LB-B2 描述的静默分叉)。
- **爆炸半径**:同 LB-B2——配置默认值/降级判定在算法侧与配置页侧分叉,静默污染排产正确性。
- **处置**:并入 LB-B2 收敛(service 栈反向复用 model 栈);收敛前的 parity 测试应**同时覆盖这组 helper**,不只 snapshot 字段。
- **复核**:✅ 已读两侧源码,逐字相同确认。

#### 14.D5 【P5 · low · N1 家族】`_get_plan_role_arg` 在 gantt 与 week_plan 路由各一份

- **位置**:`web/routes/domains/scheduler/scheduler_gantt.py:135` ↔ `scheduler_week_plan.py:60`(逐字:`request.args.get("plan_role")`→strip→`or None`)。
- **为何记**:与 §13 **N1(plan-guard 字段散 3 抄)同族**——plan_role 的读取/投影逻辑在多个 scheduler 路由各自手写。单看低危(纯读 query),但它佐证 N1 的判断:**plan_role 处理在 web 路由层缺单一收口**。审计 N1 盯的是 guard 字段投影,这条是更上游的"取参"也散落。
- **爆炸半径**:低(只读取);维护性——plan_role 取参口径散落多处。
- **处置**:与 N1 一并收口(取参 helper 提到 scheduler 路由公共模块)。属真债清理册第三档。
- **复核**:✅ 已读两侧源码。

### 14.3 低危微重复(14 组,简列 · 真债清理册最低档)

> 全部为 drift MDS 标记、审计盲区、低危 P5 微重复:跨子系统的同名小工具函数逐字/近似重复,删不删不影响正确性。grep 实证后可逐组收口到就近公共点或 `core/shared`。

| 重复符号 | 代表位置(首处) | 备注 |
|---|---|---|
| `_norm_text` (2×) | core/services/material/{material,batch_material}_service.py:25/24 | material 双 service 同款空串归一 |
| `_optional_text` (2×) | core/services/scheduler/graph/input_adapter.py:167 ↔ summary/schedule_summary_degradation.py:172 | 跨 graph/summary 子系统 |
| `_required_text` (2×) | gantt_adjustment_{publish,scenario}_service.py | gantt 调整双 service |
| `_normalize_cell_value` (2×) | core/services/common/{openpyxl,pandas}_backend.py:19 | 两 Excel 后端 |
| `_load_preset_payload` (2×) | core/infrastructure/migrations/v8.py:57 ↔ v9.py | 迁移脚本惯性复制 |
| `_unpack_due_info` (2×) | core/services/system/maintenance/{backup,cleanup}_task.py:51 | 维护任务双份 |
| `_operator_machine_reference_snapshot` (2×) | web/routes/{equipment,personnel}_excel_links.py:65 | 两 Excel 链接路由 |
| `validate_row` (2×) | web/routes/personnel_excel_operators.py:148 | 同文件/同族校验 |
| `_normalize_db_path` (2×) | validate_dist_exe.py:56 ↔ web/bootstrap/runtime_probe.py | 启动探针 vs 打包校验 |
| `_normalize_env_overlay` (2×) | tools/long_gate_fingerprint.py:275 ↔ tools/quality_gate_shared.py | 门禁工具(非生产) |
| `_sha256_file` (3×) | tools/long_gate_*.py + quality_gate_shared.py:59 | 门禁工具(非生产) |
| `_load_payload` (2×) | .codex/hooks/*.py:24 | hook 脚本(非生产) |
| `evaluate_reuse ↔ evaluate_failure_reuse` (82%) | tools/long_gate_cache.py:494 | 近似重复(门禁工具) |
| `maybe_run_auto_backup_cleanup ↔ ..._log_cleanup` (83%) | core/services/system/maintenance/cleanup_task.py:161 | 近似重复(维护) |

> 其中 5 组(`_normalize_env_overlay`/`_sha256_file`/`_load_payload`/`evaluate_*`/门禁工具类)落在 `tools/`、`.codex/`——**非交付生产代码**,收口优先级最低。

### 14.4 本节小结

| 维度 | 结论 |
|---|---|
| 第三方能否证伪审计? | **不能**——drift 未指出任何审计漏掉的真出血,核心结论(P1 真实计数 0、承重护栏清单、灵魂线判定)全部站得住 |
| 三信源最强互证 | drift 独立命中 §90 **LB-B1**(承重双实现)——但建议"删重复"恰是引爆动作,反证"drift 须过 Agent 法医" |
| 增量真发现 | **28 组 MDS 重复(文件级盲区15/符号级盲区25),全逐行亲核**;**5 组值得记**:14.D1 `_meta_bool_state`(降级语义逐字两份,最该收)、14.D2 `_op_seq`(护栏文件+静默兜底)、14.D3、**14.D4 config 双栈复制函数群(=LB-B2 配料表)**、14.D5 `_get_plan_role_arg`(N1 家族) |
| 工具口径校准 | drift AVS≠分层违规(本项目仍 0);drift MDS"删重复"含承重墙,不可盲采 |
| 方法论闭环 | 印证 §92:两遍法对"大件"召回强、对"散落微重复"召回弱,第三方机械全扫补此格;**且暴露本审计自身 B−A 透镜的文件级粒度缺陷,已修正为符号级(14.0b)** |

---

## 90 · 承重护栏清单【防屎山核心资产 · 别动我】

> 本节是整份报告**防屎山价值最高**的一节。基准对抗验证确认 **8 处** `load_bearing=true` 承重不对称(LB-A1/A2/A3 + LB-B1/B2/B3/B4 + N1 收口前身);b08162cd 增量再添 **LB-A4/A5/B5** 与正向护栏 **LB-G+**(见下方增量小节),故小结表共列 10 行。行号已在当前 HEAD `b08162cd` 上复核。

### 为什么"承重不对称"是看着像债、实为救命护栏的东西

普通的债(死代码、半截迁移)删错了顶多功能缺失、报错暴露。**承重不对称删错了不报错——它静默地拆掉一道安全不变量,系统继续绿着跑,直到错误数据流到不该去的地方。**

它的共性,也是它危险的根源:

1. **刻意和兄弟不一致** —— execution_review 比 overdue/utilization/downtime 三个兄弟报表少收两个参数;派工不走资源归一收口点;boolean 有两份实现。每一处单看都像"没对齐、该清理的坏味道"。
2. **理由全散在远处** —— "为什么故意"的根据在 schema CHECK、分层规则、UI 文案、导航强制、合同测试里,**唯独发生不一致的那行代码本地零注释**。
3. **改它的动作伪装成无害清理** —— "统一四张报表的参数签名"、"消除魔法字面量方言"、"合并重复实现",在 diff 层面都像正向重构。

**这意味着:未来任何一个 LLM(或人)看到它们,第一反应都是"这是不一致,该统一"——而统一动作本身就是引爆动作。** 这是"失忆债"最危险的形态:不是债本身危险,是**还债的人如果也失忆,还债就是闯祸**。

**本节对每一处的核心交付物 = 一行该补的"我是故意的"注释**。把散在远处的护栏意图,钉回发生不对称的改动点本地——这是对无记忆的 LLM 协作者**唯一有效的本地阻止信号**,也是性价比最高的防屎山动作。

---

### A 族 · execution_review「只复盘正式采用方案」(纵深防御 4 处,守同一条不变量)

> **不变量**:"计划和现场实际"复盘 = 拿**正式采用方案**对账车间现场事实。若放开 `plan_role`/`scenario_id`,模拟方案预览或历史非采用方案会冒充"现场实际复盘"展示给车间,把**没发生的预览当成既成事实**——直接踩中灵魂红线"宁可暴露错误也不自欺"的反面。
>
> 这道墙在 4 个层次设防(web 路由 → 服务签名 → 取数源表 → 写侧反馈),**任何单层都不是冗余,而是纵深防御**:上层守卫可能被某次重构绕过,下层仍需独立挡住。报告把它们合并讲,但强调**不可"合并简化"为一点**。

#### LB-A1 【P2 · high】web 路由层:写死 `adopted`/`None`(reports_page_support + navigation_context)

- **位置(当前 HEAD `b08162cd` 已复核)**:
  - `web/routes/reports_page_support.py:367` — `page_plan_resolution(services.schedule_plan_query_service, version, "adopted", None)`
  - `web/routes/reports_page_support.py:369` — `page_date_range_or_version_span(engine, ..., "adopted", None, ...)`
  - 二者在 `execution_review_page_context()`(`:364`)内
  - `web/navigation_context.py:80-82` — `is_execution_review` 为真时 `plan_role = ROLE_ADOPTED`、`scenario_id = ""`,强制清掉 request 的 role/scenario
  - ⚠️ **行号已变**:普查时为 `:366,:368`,b08162cd 工作台收口(reports_page_support.py +456 行)后微移到 `:367,:369`。债仍在。
- **不对称实锤**:同文件所有兄弟页(overdue/utilization/downtime 经 `_standard_request_context`)全部 `raw_plan_role=request_plan_role()` / `scenario_id=request_scenario_id()` 从 request 读;**唯独 execution_review 写死**。
- **删了会炸什么**:把 `:367/:369` 的 `"adopted", None` 改成 `request_plan_role()/request_scenario_id()`,预览/对比方案即可通过 `?plan_role=&scenario_id=` 冒充正式复盘,污染复盘结论。改动看起来是"消除参数方言"的一致性清理,实为安全回退。
- **动它的前置条件**:(1) 绝不给 core 的 `execution_review()` 加 plan_role/scenario_id 入参——行数据护栏在 core 必须原样保留;(2) 先补缺失的页面级回归 `GET /reports/execution-review?plan_role=baseline_best&scenario_id=xxx`,断言「排产方案」标签仍为正式采用方案、不出现预览/对比文案、发布的 nav context plan_role=adopted 且无 scenario_id;(3) 若只为消除魔法字面量,应抽具名收口(如 `execution_review_plan_context()` 内部强制 adopted/None)替换字面量,而非改成从 request 读;(4) 保留 navigation_context.py:80-82 的 is_execution_review 强制分支(它守未发布 context 的回退路径)。
- **🔧 该补的"我是故意的"注释**(贴在 `:367` 上方):
  ```python
  # 故意写死 adopted/None,不从 request 读 plan_role/scenario_id:这是护栏,不是漏掉的方言。
  # 计划和现场实际只复盘正式采用方案;放开会让模拟预览/对比方案冒充正式复盘展示给车间。
  # 勿为"统一所有报表页从 request 读参数"而改成 request_plan_role()/request_scenario_id()。
  ```

#### LB-A2 【P2 · high/medium】服务签名层:`execution_review()` 形参拒收 plan_role/scenario_id

> 注:本条由 scheduler-plan-identity(LB2)与 core-svc-domain(LB5)两个分区**独立命中同一处**,互证其重要性。合并陈述。

- **位置(当前 HEAD `b08162cd` 已复核)**:
  - `core/services/report/execution_review.py:141` — `execution_review(self, version, *, date_from, date_to, batch_id, resource_type, resource_id)` 形参**刻意不含** plan_role/scenario_id;`export_execution_review_xlsx`(`:178` 附近)同样
  - `:112,123` — `_execution_review_plan_rows` 两分支恒 `plan_role=ROLE_ADOPTED, scenario_id=None`
  - `:153` — 方法体恒 `resolution = host._resolve_plan(v, ROLE_ADOPTED, None)`
  - `:166-167` — 返回 dict 恒 `plan_label=plan_role_label(ROLE_ADOPTED), plan_role=ROLE_ADOPTED`
  - ✅ **证据仍准**:b08162cd 改了本文件(149 行变更,删除了 P1 出血源),但这 5 处硬钉 ROLE_ADOPTED 仍在;grep"故意/刻意/不对称"**仍零命中**——即使刚做完工作台收口,这道护栏的注释依然没人补(失忆债的活样本)。
- **不对称实锤**:`report_engine.py:157 overdue_batches(self, version, plan_role=None, scenario_id=None, ...)`、`:267 utilization(...)`、`:371 downtime_impact(...)` 全部签名带 plan_role+scenario_id 并透传;`overdue_batches` 在 `:168 self._resolve_plan(v, plan_role, scenario_id)` 透传。**唯独 execution_review 拒带。**
- **取数源真随 role/scenario 改变(护栏不是装饰)**:`schedule_plan_query_service.resolve_plan_view` 中 `scenario_id` 非空即转 `_resolve_scenario_plan` → `source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS`、`is_scenario_preview=True`;非 adopted role 选不同 candidate_id/source_table。所以写死 adopted 是**数据层最后一道把关**。
- **删了会炸什么**:给 execution_review 补 plan_role/scenario_id 透传,模拟预览/对比方案的计划时间会和正式现场反馈拼成"计划 vs 实际"复盘并可导出,污染唯一可信的正式复盘口径;合同测试拦得住一部分,但服务层契约已被破坏。
- **动它的前置条件**:(1) 取数边界保留强制 adopted——继续写死,或加 service 层断言:收到非 adopted role / 任何 scenario_id 时 `raise ValidationError`(loud,不静默回退),返回前校验 `resolution.is_scenario_preview is False`;(2) 给下游 `aggregate_states_by_op_ids` 增加 role/scenario 作用域过滤,让 join 能自卫;(3) 路由入站层加闸门并保留 web 层 forbidden-params 守卫;(4) 用 `regression_plan_vs_actual_review`/`regression_reports_workbench_navigation_contract` 锁死。
- **🔧 该补的"我是故意的"注释**(贴在 `execution_review.py:141` 签名上方):
  ```python
  # 本方法故意只复盘 ROLE_ADOPTED,不收/不透传 plan_role/scenario_id——
  # 与 overdue/utilization/downtime 三兄弟的签名不对称是刻意的护栏,不是遗漏。
  # 勿为"统一四张报表方法签名"而加 plan_role/scenario_id 形参:
  # 会让模拟预览/对比参考方案的明细以"正式现场复盘"身份呈现给车间并可导出。
  ```

#### LB-A3 【P2 · high】写侧反馈层:`operation_execution_feedback_service` 硬拒 + 写死消毒

- **位置(当前 HEAD `b08162cd` 已复核)**:
  - `core/services/scheduler/operation_execution_feedback_service.py:347-356` — `_load_current_official_schedule` 刻意硬拒:`requested_plan_role != ROLE_ADOPTED or effective_plan_role != ROLE_ADOPTED or source_table != SOURCE_SCHEDULE or scenario_id is not None` 即拒
  - `:451-453` — `_build_event_payload` 写死 `"source_table": SOURCE_SCHEDULE, "effective_plan_role": ROLE_ADOPTED, "scenario_id": None`
  - ✅ **证据仍准**:行号与普查一致。
- **守的不变量**:现场反馈只能写在**当前正式采用方案**上,禁止预览/scenario 冒充正式现场记录。`_build_event_payload` 写死常量是 **defense-in-depth 的消毒层**:即便上游校验被绕过,持久化层也绝不落下一条带 candidate/scenario 身份的现场事件。
- **删了会炸什么**:把三个写死常量改成透传 context、或删 `:347-356` 的拒绝分支,现场反馈可被写到候选方案/scenario 预览上,**污染"正式采用方案"的现场执行事实**;下游重排护栏(`schedule_execution_guardrails` 读 `ExecutionFact`)会基于被污染的事实做决策。
- **动它的前置条件**:唯一安全动作是补保护性注释。严禁把 451-453 改成透传 context。若仍要改逻辑必须同时:(a) 保留 348-354 硬拒或等价 can_write_feedback 硬门;(b) `schema.sql:256-258` 三条 CHECK 与 `migration_operation_execution_contract` 启动探针保持不变(最终承重底);(c) 新增 record_event 端到端(非仅 repo 级)回归,证明 scenario/candidate 上下文在任何持久化前被拒。
- **🔧 该补的"我是故意的"注释**(贴在 `:451` 上方):
  ```python
  # 故意写死、故意忽略 context 的同名字段:这是消毒层(defense-in-depth)。
  # 即便上游校验被绕过,持久化也绝不落 candidate/scenario 身份的现场事件——
  # 现场执行事实只能挂在正式采用方案上,否则会污染下游重排护栏的决策依据。
  # 勿改成透传 context.source_table/effective_plan_role/scenario_id。
  ```

---

### B 族 · 各自独立的承重不对称

#### LB-B1 【P5 · medium】`boolean_normalize` 双实现是**分层承重**,不是冗余副本

- **位置**:`core/shared/boolean_normalize.py:33` `normalize_yes_no_wide` vs `core/services/common/normalization_matrix.py:168` `normalize_yes_no_wide_value`(逐行同义)。
- **为什么不能删**:`boolean_normalize` 被 `core.models`/`core.algorithms` 等**下层**模块引用。若以"统一到矩阵"名义删掉它、改指 `core.services.common`,会立刻产生 `core.models → core.services` **越层** + 导入环,**击穿当前 AST 0 违规结构**。所以它的存在是分层承重的。
- **真正该补的**:不是删任一方,是**一条绑定两套等价的契约测试**——断言两者在全 wide 别名集 × 是/否 × default/passthrough/raise/no 全部 unknown_policy 分支上逐一同值(任一单边改动即触发红灯)。
- **若确要消重的唯一合法方向**:让**上层** `normalization_matrix.normalize_yes_no_wide_value` 反过来 delegate 到**下层** `boolean_normalize`(services→shared 是合法下行边),保留 shared 为唯一事实源,删 matrix 内重复逻辑——而非相反。
- **🔧 该补的注释**(贴在 `boolean_normalize.py:33` 上方):
  ```python
  # 这不是 normalization_matrix.normalize_yes_no_wide_value 的冗余副本:
  # core.models/core.algorithms 在下层只能调本函数,删它改指 core.services 会撞分层红线。
  # 两套必须保持语义等价——靠 regression 契约测试绑定,勿单边修改别名集/枚举值。
  ```

#### LB-B2 【P3 · medium】双 `ScheduleConfigSnapshot` 栈:潜伏的静默分叉(Pass-1 漏报、Pass-2 补出)

- **位置**:`core/models/schedule_config_runtime_*.py`(5 文件,snapshot 27 字段)≈ `core/services/scheduler/config/config_snapshot.py`(逐字节相同,ensure_schedule_config_snapshot ~499 行)。
- **为什么是承重/潜伏债**:算法层不能 import 服务层(layer_edges 证实 `core.algorithms → core.services` 不存在),所以需要一个 model 层"中性投影"供算法用。但反过来 `core.services → core.models` 是合法边(42 条),服务栈**本可复用 model 栈而非另起一套**。两份靠人工锁步同步(git 实证 `b82c9a4d`/`ef244b9e` 同时改两份字段表)。
- **删了/疏忽会炸什么**:当前 27 字段在册无漂移,故是**潜伏债**——任何人给配置页(service 栈)加一个字段而忘了同步 model 栈,**算法看到的就是旧默认值,而用户在配置页校验/保存的是新值**,两边对"同一份配置"各执一词,且算法侧回落是静默的(踩灵魂线)。
- **收敛方向(需先补 parity 测试)**:让 service 栈反向复用 model 栈;收敛前必须先补一条 parity 测试断言两栈字段集与默认值逐一相等。
- **🔧 该补的注释**(贴在两栈 snapshot 定义处):
  ```python
  # ⚠️ 本 dataclass 与 core/services/scheduler/config/config_snapshot.py 的 ScheduleConfigSnapshot 必须逐字段同步。
  # 这是分层(算法层不能 import 服务层)被迫的双实现,非随意复制。
  # 加/改字段必须两栈同改,否则算法用旧默认值、配置页存新值,静默分叉污染排产正确性。
  # 收敛前先补 parity 契约测试。
  ```

#### LB-B3 【P3 · medium】legacy 错误串往返桥:两代错误体制并存

- **位置**:`core/models/scheduler_public_errors.py:62-103,218-290`(`LEGACY_PUBLIC_PATTERNS`/`_LEGACY_CODE_PREFIXES`/`legacy_public_error_message`/`infer_legacy_public_code`)。活消费方:`auto_assign_resource_errors.py:42,157` + `scheduler_summary_display.py:63`。
- **为什么算债(needs_adversarial)**:老路径发渲染好的中文错误串,下游用正则把串**反解回结构化 code**——从"渲染输出"倒推"结构化身份",绕过本应端到端携带 code 的 `make_public_error`。正则与一长串中文模板字面强耦合,**任一文案改字就静默失配**,错误降级为通用文案。
- **处置**:这是过渡桥,`legacy_/LEGACY_` 命名是自供。收敛=让老路径也走结构化 `make_public_error` 端到端带 code,届时可删整组正则。**但收敛前改任何相关中文文案都要同步检查正则**——这是它当前的承重点(改文案的人未必知道有正则在依赖文案)。
- **🔧 该补的注释**(贴在 `LEGACY_PUBLIC_PATTERNS:62` 上方):
  ```python
  # ⚠️ 这组正则把已渲染的中文错误串反解回 code,与下方 make_public_error(结构化体制)并存。
  # 它强耦合具体中文模板字面:改任何被 auto_assign_resource_errors 发出的错误文案,
  # 都必须同步更新这里的 pattern,否则错误会静默降级为通用文案。
  # 终态:让老路径也走 make_public_error 端到端带 code,然后删除本组正则。
  ```

#### LB-B4 【P4 · low】`_bool_from_summary` 静默吞坏 JSON(对抗验证**推翻**了其安全危害)

- **位置**:`core/services/scheduler/schedule_plan_identity_builder.py:24-29`(`except (TypeError, ValueError): return False`)。
- **对抗验证的关键纠正**:普查初判它"影响 is_official/可派工"是**被推翻的**。真正的承重护栏是 `result_status='simulated'`(由同一 `ctx.simulate` 原子同写,且在两个消费者里都先于/独立于 summary 被检),所以删/统一**不会**让模拟冒充正式或可派工。
- **但仍不可改 raise**:`latest_executable_official_version` 全量扫历史行,任何一条 legacy/NULL 邻接的损坏 summary 都会让当前方案身份整链抛错——这是**可用性放大事故**而非安全收益。
- **处置**:不改 raise;只补一条非致命的完整性日志(让损坏 summary 可见但不阻断)。属低优先。
- **🔧 该补的注释**(贴在 `:24` 上方):
  ```python
  # 对坏 summary 返回 False 是有意的容忍(legacy/NULL 老库行)——不可改 raise:
  # latest_executable_official_version 全量扫历史,一条坏行会让当前方案身份整链崩。
  # 安全不变量由 result_status='simulated'(原子同写)独立保证,不依赖这处 summary 判定。
  ```

---

### 增量 · b08162cd 工作台收口对承重护栏的影响(详见 §13 第三部分)

> 现状对账:b08162cd 给本清单**新增 1 处承重点、扩展 1 处、并新加 1 道正向护栏**。

| 编号 | 位置(b08162cd) | 守的不变量 | 状态 |
|---|---|---|---|
| **LB-A4**(新增) | `navigation_context.py:42-47,80-82` | execution_review 导航层剥离 plan_role/scenario_id(第 4 个承载点) | ⚠️ b08162cd 新增,靠路由名/路径**字面量匹配**+零注释,**最脆弱**。见 13.N3 注释文案 |
| **LB-A5**(削弱) | `scheduler_navigation_publish.py:79-84` | 写侧 can_write_feedback 仅 formal_adopted 可写 | ⚠️ :83 `context.update` 把 builder 已 gate 的值覆盖回未门控值(当前未被消费,潜伏)。见 13.N5 |
| **LB-B5**(新增承重) | `schedule_resource_filter.py:8,19-24,54/60/66` | 新 collar 只支持 machine/operator,team/empty-id 一律 raise | ⚠️ b08162cd 新增,零注释说明 team 排除是刻意的(collar 表达不了 team 轴,靠 SQL 双 join 两轨并存)。见 13.G2 |
| **LB-G+**(✅正向) | `schedule_plan_identity_builder.py:76-77,61-62,166` | is_superseded → "历史正式方案(已被新版本替代)"标签,防旧正式冒充现行 | ✅ **b08162cd 新加的反自欺护栏**(灵魂线正向补强)。建议补注释说明它是护栏不是装饰 |

> ⚠️ **N1 不是单点护栏,是护栏的"承重字段"被散成 3 抄**:execution_review 放行判定 `_is_formal_adopted_context` 依赖的 plan-guard 字段,被 `reports_workbench.py:40`/`navigation_publish.py:72`/`resource_dispatch.py:63` 三处手维拷贝(键集三样、命名两套),漏拷一键即护栏静默失效。这是比"单处无注释"更危险的承重债——治法是把 guard 字段收口进 `build_workbench_plan_context`(详见 13.N1)。

### 本节小结

| 编号 | 位置(当前 HEAD `b08162cd`) | 守的不变量 | 复核 |
|---|---|---|---|
| LB-A1 | reports_page_support.py:367,369 + navigation_context.py:80-82 | execution_review 只复盘 adopted(web 层) | ⚠️ 行号微移 +1 |
| LB-A2 | execution_review.py:141,112,123,153,166-167 | 同上(服务签名层) | ✅ 仍准,注释仍缺 |
| LB-A3 | operation_execution_feedback_service.py:347-356,451-453 | 现场反馈只挂正式方案(写侧消毒) | ✅ 仍准 |
| **LB-A4** | navigation_context.py:42-47,80-82 | execution_review 导航层剥离方案身份 | ⚠️ b08162cd 新增,最脆弱 |
| LB-B1 | boolean_normalize.py:33 | 分层 0 违规(下层不 import 上层) | ✅ 仍准 |
| LB-B2 | schedule_config_runtime_*.py(5)↔config_snapshot.py | 双配置栈不静默分叉 | ✅ 潜伏 |
| LB-B3 | scheduler_public_errors.py:62-103,218-290 | 改文案不静默失配正则 | ✅ 仍准 |
| LB-B4 | schedule_plan_identity_builder.py:24-29 | (危害已被对抗验证下调)不改 raise | ✅ 仍准(基线b08162cd);⚠️工作树已超前治理为 fail_closed+可见标记,见§13.5 |
| **LB-B5** | schedule_resource_filter.py:8,54/60/66 | 新 collar team/empty-id 一律 raise | ⚠️ b08162cd 新增,零注释 |
| **N1** | reports_workbench:40 / navigation_publish:72 / resource_dispatch:63 | 护栏字段单一来源(现散 3 抄) | ⚠️ 承重字段散落,收口进 builder |

**最高杠杆动作**:把上述注释逐字补进改动点本地(A 族 + LB-A4 navigation_context 是重中之重)。**b08162cd 后新增的 LB-A4(字面量匹配护栏)和 N1(护栏字段散 3 抄)是当前最脆弱的两处**——它们是"刚长出来、还没立约"的接缝。这是把"散在远处的护栏意图"钉回执行现场,对无记忆的 LLM 协作者唯一有效的本地阻止信号——也是本次普查认定的**唯一通向屎山的路(以统一名义抹掉承重不对称)的免疫疫苗**。

---

## 91 · 真债清理册【按收口难度排序】

> 53 条 `load_bearing=false` 的可安全收的债,按收口难度分六档。**核心原则:收口到已存在的统一点,绝不新发明**(新发明 = 再失忆一次)。每条给 file:line + 动作 + 收口目标。
>
> ⚠️ 时间基准:位置取自普查 HEAD `65870e47`。`b08162cd` 工作台收口主要动了 report/gantt 相关文件,本清单多数条目(data-repos / core-algorithms / core-models / infra-shared)未受影响,行号仍准;涉及 report/gantt/web 的条目动手前请重新 grep 定位。

---

### 第一档 · grep 实证零引用,可直删(零爆炸半径)

> 这些是纯死代码,全仓(含测试)零引用。删除无生产路径受影响。

| # | 位置 | 动作 |
|---|---|---|
| 1 | `data/repositories/schedule_repo.py:61` `list_between` | 直接删,零同步 |
| 2 | `data/repositories/batch_operation_repo.py:25,50` `get_by_op_code`+`list_by_status` | 直接删两个方法 |
| 3 | `data/repositories/operator_machine_repo.py:82` `list_links_with_machine_names` | 直接删(连 facade 都没暴露) |
| 4 | `data/repositories/op_type_repo.py:73` + `operator_repo.py:85` + `part_repo.py:71` `list_as_dicts` 三连复制 | 三处一并删 |
| 5 | `data/repositories/part_repo.py:32` `list_unparsed` | 直接删 |
| 6 | `core/shared/value_policies.py:9` `WRITE_INTERNAL_ONLY`(+common:11,29 re-export+__all__) | 删 3 处(定义+re-export+白名单) |
| 7 | `core/models/scheduler_public_errors.py:163-164` `_safe_identifier` 死别名 | 删函数+删误导性注释 |
| 8 | `core/models/schedule_config_runtime_coercion.py:83-98` `_record_blank_choice_degradation` 死参数 `raw_value` | 删形参+改两调用点(:155,:210) |
| 9 | `core/algorithms/dispatch_rules.py:25` + `evaluation.py:40-41` + `ortools_bottleneck.py:24-25` 5 处死模块别名 | 删 5 处别名 |
| 10 | `core/algorithms/dispatch_rules.py:112` `mean_positive` 死函数 | 删(生产用内联均值) |
| 11 | `core/algorithms/greedy/dispatch/batch_order.py:74` `_ = scheduled_count` 死空操作 | 删 1 行 |
| 12 | `core/services/scheduler/dispatch/__init__.py` 空包(无关提交误建) | 删目录 |

### 第二档 · 删 + 同步退 1-2 处测试/桩

> 死代码,但有测试在续命,删时需同步退测试断言。

| # | 位置 | 动作 |
|---|---|---|
| 13 | `core/services/scheduler/gantt_service.py:60-62` `get_latest_version_or_1`(死且名字撒谎) | 删方法 + 删测试 stub |
| 14 | `core/services/scheduler/execution_fact_provider.py:20-21,42-43,96` ExecutionFact 两死字段 `last_event_schedule_version/id` | 删字段 + 不再调 `list_latest_events_by_op_ids`(其本身也仅此一调用,连带死) |
| 15 | `data/repositories/operation_execution_event_repo.py:260-265` `list_latest_exception_events_by_op_ids` | 删 + 退 1 行测试断言 |
| 16 | `core/services/scheduler/run/schedule_graph_dispatch_context.py:461-475` `build_first_wave_ready_nodes` test-only 包装器 | 先把测试 import 改指真 impl(`resource_matching_context`),再删 |
| 17 | `core/shared/compat_parse.py:198` compat 整条 date 分支(`parse_compat_date`+3 日期策略+`VALUE_D...`) | 删 + 退 2 处测试断言 |
| 18 | `core/services/scheduler/run/schedule_payload_contract.py:90-95` `count/has_actionable_schedule_rows`+`_iter_actionable_results` | 删函数+两处 re-export+__all__,同步删 SP05 拓扑断言 |
| 19 | `core/services/scheduler/run/schedule_candidate_runner.py:216` candidate FAILED 态下游计数/UI 脚手架 | **窄 except:216 必须留(承重)**,只收下游不可达计数+viewmodel 死分支 |
| 20 | `web/viewmodels/scheduler_resource_dispatch_execution.py:24,226-227,361-362` `feedback_write_enabled` 休眠开关 + 生产不可达"保护未开启"提示 | 删开关+死提示分支 |
| 21 | `data/repositories/operation_execution_state_builder.py:33-39,76-79` `_REPORTED_STATUS_BY_EVENT_TYPE` 兜底表(被 schema CHECK 架空) | 删表,:77 简化为直用 reported_status |
| 22 | `core/services/scheduler/operation_execution_feedback_support.py:64` + `feedback_service.py:12,455` `_REPORTED_STATUS_BY_ACTION` 的 `EXECUTION_EVENT_EXCEPTION` 死键 | 删键+删死导入 |

### 第三档 · 收口到已存在统一点(改 import/re-export,语义已实证等价)

> 这些有现成的收口点,只需把私有副本/死 shim 指过去。**不新发明。**

| # | 死/重复项 | **收口到(已存在)** | 注意 |
|---|---|---|---|
| 23 | `schedule_plan_role._normalize_role` 与 `schedule_plan_query_service:28-30` 双字节副本 | `core/models/schedule_plan_role._normalize_role` | query_service 直接 import,今日行为一致 |
| 24 | `scheduler_navigation_publish.py:28-29` `selected_plan_role` | `core/services/scheduler/schedule_result_view_context.selected_plan_role` | 照搬 `gantt_plan_query.py:46` 已有 re-export;core 版对 None 更稳 |
| 25 | `gantt_service_support.py:32-51` `_normalize_critical_chain_result` 第二份 | `gantt_critical_chain`(两文件都已 import 它) | ⚠️ git status 标 `A`(未提交),**落手前问在途作者** |
| 26 | `gantt_plan_query.py:42,46,32,59` 死兼容 shim(resolve_plan/selected_plan_role/default_plan_resolution_dict/_has_explicit_gantt_range) | `schedule_result_view_context`(已是真身) | 删 4 符号+1 测试;**文件整体不可删**(还有 4 个活的 range 辅助);删 default_plan_resolution_dict 前先迁移其遗留错误文案包装 |
| 27 | `core/services/scheduler/operation_execution_labels.py:1-36` 纯转出垫片 | `core.models.operation_execution_labels` | 重指 5 个导入方 + 清 doc-gate KEY_PYTHON_FILES |
| 28 | `core/services/common/{compat_parse,field_parse,value_policies}.py` 三个零消费 facade 残渣 | `core.shared.*` 直连 | 先把 2 个行为测试 import 改指 core.shared,再删身份断言+删文件 |
| 29 | `core/services/scheduler/analysis/schedule_diagnostic_contract.py:13-79` 孪生副本 | web 侧 LIVE helper 已是活路径 | **删 core 这份(零消费),绝不能反删 web twin**;先调和 PR-9 roadmap |
| 30 | `core/services/scheduler/graph/ready_queue.py:1-12`+`get_ready_operation_ids` | `sgs_graph._prepare_graph_ready_state`(已取代) | 删测试文件+2 处枚举断言+roadmap 备忘 |
| 31 | `core/algorithms/greedy/config_adapter.py`(整模块 28 行) | 本分区收口点 `ensure_schedule_config_snapshot`(已内联取代) | 整模块删(仅查重测试列了路径) |
| 32 | `data/repositories/schedule_repo.py:114,128,36` 版本-only 查询方法群 | `schedule_plan_query_repo` 的 plan-role 感知孪生方法 | plan-role 迁移残渣,仅测试/类型契约续命 |

### 第四档 · 语义需逐处对齐(收口但不能裸替换)

> 有收口点,但私有副本与收口点**语义有细微差异**,替换前需逐处对齐,否则会改变行为。

| # | 死/重复项 | 收口到 | 对齐要点 |
|---|---|---|---|
| 33 | `execution_fact_provider.py:66` / `feedback_support.py:226` / `operation_execution_*` datetime 解析 3 份 | `core/shared/strict_parse.parse_required/optional_datetime` | provider/state_builder 的 None 是合法"无时间"语义,要分清 required vs optional,别把缺时间误判成错误 |
| 34 | `execution_fact_provider.py:51` / `event_repo.py:63` positive-op-id 过滤 | `execution_snapshot.positive_op_ids`(public 已排序) | 指纹依赖排序版;换前确认无下游依赖原入参顺序 |
| 35 | `batch_service.py:56-65` `_safe_float` 静默吞错 | `core/shared/number_utils.parse_finite_float` | 上游模型已 `parse_optional_float` 校验,替换后更合灵魂线;须同步移除 fitness allowlist 条目 |
| 36 | `enum_display.py:13-79` + `process_bp.py` 中文枚举标签第二套(**已语义漂移**) | `enum_normalizers` 收口点 | operator 停用→"停用/休假" vs "停用";ready 未知值静默贴"未齐套"——对齐前先定哪个语义对 |
| 37 | `parse_dispatch_rule`(dispatch_rules.py:28) / `parse_strategy`(sort_strategies.py:161) 宽容解析器 | 已被 `_require_choice+Enum()` 严格收口取代 | 生产零引用且语义与灵魂相悖(宽容回落 vs 严格抛错),删前确认无测试依赖宽容行为 |

### 第五档 · P4 软兜底(改 raise / 补可观测,不裸删)

> 静默兜底死角。多数不可裸删(删了会 500 谎报),正确动作是改成 loud 暴露或补降级信号。

| # | 位置 | 动作 |
|---|---|---|
| 38 | `core/infrastructure/backup.py:333` integrity_check 失败只 warning 不阻断 | **改 raise**(对齐 :340 else 分支)——真吞缺口,未校验库不该升正式备份;收尾收 `system_backup.py:107` 裸 500 |
| 39 | `core/services/scheduler/resource_dispatch_execution_service.py:131-141` schedule 缺失静默兜成"正式采用方案/可写"卡 | **改 `raise AppError(NOT_FOUND)`**;**不可裸删**(否则 142 行 AttributeError→500 谎报写失败) |
| 40 | `core/services/scheduler/gantt_critical_chain.py:84` 静默丢坏时间行仍报 available:True | 保留过滤 + **补 `dropped_count`/`partial`** 穿三道白名单(support/provider/contract);不可裸删 |
| 41 | `data/repositories/material_repo.py:68-72` `update` 库存 except 静默保留原值 | 不可达防御,当前无错被吞,低优先;补注释或改 loud |

### 第六档 · 需先协调(depends / roadmap 明示延期)

> 这些**现在不该动**——要么 owner 未裁断,要么 roadmap 明示延期,动了属抢跑。

| # | 项 | 状态 | 待办 |
|---|---|---|---|
| 42 | 5 个 config/summary shim(`config_service.py` 等) | depends | **先迁 2 个在用离线脚本**(tools/capture_networkx_phase0_baseline、audit probes)+ 53 测试到深路径 + 改 SP05,再删 |
| 43 | 空 delayed 包 `calendar/`+`batch/` | SP05 强制存在 | 删目录+改 SP05:310-315 元组(机械简单但需同提交) |
| 44 | `core/services/common/number_utils.py:23` 全量拷贝 | depends | 是有意 delegation-facade(2026-06-01 KEEP/high 裁定);薄壳化须**先重写 monkeypatch 测试**为身份断言 → 收口 `core.shared.number_utils` |
| 45 | 顶层 9 个 `scheduler_*.py` wrapper | roadmap 明示延期 | `p1-scheduler-debt-cleanup:522`"先保留避免冲击启动链"——**现在动属抢跑** |
| 46 | `_positive_int` 可空簇(`resource_dispatch_execution_service.py:23` 等 3 处逐字节复制) | ⚠️ **唯一"该收却无现成统一点"的债** | parse_finite_int 对垃圾 raise、契约不符;需**新建 canonical** `parse_optional_positive_int`(垃圾→None)——这是本报告唯一需要新增收口点的债,需 owner 裁断是否值得 |

---

### ⚠️ 唯一需要"新发明"的债(其余全部收口到已存在点)

第六档 #46 的 `_positive_int` 可空簇是个特例:它在执行车道三处逐字节复制(`resource_dispatch_execution_service.py:23` 等),逻辑是"垃圾值→None"。但已有的收口点 `parse_finite_int` 对垃圾值是 **raise**,契约不匹配——所以不能直接收口过去。

这是本次普查 53 条真债里**唯一一条"该收却无现成统一点"的债**。处置需 owner 裁断:是新建一个 canonical `parse_optional_positive_int`(垃圾→None),还是让这三处改用 `parse_finite_int` 的 raise 语义并在调用方补 try。报告不替你决定——但标出来,免得未来有人随手把它"统一"到契约不符的 `parse_finite_int` 上,把"宽容跳过"悄悄变成"抛错中断"。

### 收口难度总览

| 档 | 条数 | 性质 | 风险 |
|---|---:|---|---|
| 一档 直删 | 12 | 零引用死代码 | 零 |
| 二档 删+退测试 | 10 | 测试续命死代码 | 低 |
| 三档 收口到已存在点 | 10 | 私有副本/死 shim | 低(语义已等价) |
| 四档 语义对齐后收口 | 5 | 语义微差 | 中(需逐处对齐) |
| 五档 改 raise/补可观测 | 4 | P4 软兜底 | 中(不可裸删) |
| 六档 需先协调 | 6 | depends/延期 | 暂不动 |
| **合计** | **47** | | |

> 注:53 条真债中,6 条已并入上述"族"(如 enum 标签、datetime 三份各算多处),按可执行动作去重后约 47 个清理项。

---

# 92 · 方法论与调用图交叉检验

> 本章是横切方法论章，不列具体债，而是交代「这份水下语义债普查凭什么可信」：用了什么取证设计、两条独立证据链如何互相校准、哪些是机械工具天然分不清必须靠人核验的盲区、已知的噪声源在哪、以及哪里置信度不足必须打折。
>
> 灵魂暗线同样作用于审计本身：**坏数据不准静默兜底，宁可暴露错误**——下文凡是证据未落盘、agent 掉线、量级取自任务简报而非独立重算的地方，一律明写出来打折，绝不假装满证。

---

## 1）两遍法设计：自由取证 × 机械列举 × 人核验语义

普查没有用单一手段，而是三段式：**Pass1 agent 自由取证 → Pass2 调用图机械列嫌疑 → 人逐条核验语义**。三段各自有致命短板，组合起来才互相兜底。

### Pass1 · agent 自由取证（高精度、未知召回）

让分区 agent 沿引用链自由读码取证（任务 #36–#41 的分区深钻）。优点是语义在场——agent 能看懂「这个返回值是假冒计算结果」这种纯语义债。**短板是显著性偏差（salience bias）**：

- agent 天然被「故事性强、触目惊心、读得深的那一段」吸引，越平淡、越埋得深、越是 agent 只扫过没细读的分区，越容易漏。
- 因此 Pass1 是「**对它找到的东西高精度，但召回率未知**」——你不知道它漏了多少，漏的那部分长什么样。

### Pass2 · 调用图机械列嫌疑（零偏差、语义盲）

任务 #38 建的函数级调用图 + 数据流追踪提取器（NetworkX 底座，基线采集见 `tools/capture_networkx_phase0_baseline.py`✅ 在树、8.4KB），对**全图每个节点**机械扫一遍结构嫌疑：

- 量级（按当前树实测代理：`core/`+`data/`+`web/` 共 **612** 个 py 文件、**5340** 个 `def`/`class` 节点；图规模 `summary.json` 本次未落盘，此处取实测代理数量级，见 §5）。
- 典型嫌疑模式：core-models 层里函数名命中 `preview`/`render`（模型层不该渲染，是分层气味）；以及数据流污点 `sensitive→write`、`hardcoded→render`。
- **优点正是 Pass1 的短板的反面**：穷举、机械、零显著性偏差——再平淡的节点只要命中模式照列不误。**短板是语义全盲**：它分不清「真债」和「假阳性」。

### 人核验语义（图提名，人定罪）

把 Pass1∪Pass2 的嫌疑取并集，逐条回到真实代码读码定性，杀假阳性、给真债补 file:line 证据。**调用图只负责提名，定罪权在人。**

### 为什么必须三段叠加

| | 精度 | 召回 | 单用的后果 |
|---|---|---|---|
| Pass1 单用 | 高（对找到的） | 未知 | 显著性偏差 → 不知道有多大盲区 |
| Pass2 单用 | 极低 | 高（穷举） | 语义盲 → 假阳性洪水 |
| 三段叠加 | Pass2 穷举给 Pass1 召回兜底；人核验给 Pass2 精度兜底 | | 两条链都不被单独信任 |

设计的硬约束：**没有任何一遍的结论被单独采信。** Pass2 列出而 Pass1 漏掉的，是 Pass1 盲区的探针；Pass1 找到而 Pass2 漏掉的，是图模式照不到的语义债（如 P1 写死假冒值）；交集才是双链互证的高置信区。

---

## 2）交叉检验结果：A∩B 互证、B−A 证伪盲区、掉线由图补

记 A = Pass1 agent 取证命中的文件集，B = Pass2 调用图列出的嫌疑文件集。

### A∩B = 12 文件：双重命中互证（最高置信）

自由取证 **和** 机械调用图**各自独立**命中的同 12 个文件。两条互不依赖的方法收敛到同一文件，是「这是真债」的强信号——这 12 个构成普查的高置信骨架。

### B−A = 25 文件：几乎全是图假阳性，**证伪了「大片盲区」假说**

图列了、agent 没碰的 25 个文件。关键追问：这是 **Pass1 漏掉的真债**，还是 **图的假阳性**？人核验裁定：**几乎全是图假阳性**（`_graph_verdicts.json` 对 core-models `preview→render` 那批嫌疑核验后整批标「全假阳性」）。

这是本次交叉检验**最重要的认识论结果**：

- 如果 B−A 里塞满真债 → 说明自由取证法系统性地整类整类地漏 → Pass1 召回崩了。
- **实际 B−A 近乎全假阳性** → 说明：穷举的机械安全网撒下去，捞上来的几乎全是噪声，里头零星的真东西也都很小 → **Pass1 的召回其实是好的，它「漏」的那些大多压根不是债**。

换句话说，这条交叉检验**证伪了「agent 自由取证留下大片盲区」的担忧**，给整份普查的完整度托了底：我们确实跑了机械兜底网，而它几乎没捞到 agent 漏掉的真鱼。

> A−B（agent 找到、图没列）是预期内的：纯值级债（P1 写死假冒计算值）在调用图结构里没有签名，本就照不到，落在 A−B 合理。

### 两分区 Pass1 掉线，由 Pass2 补上

恰有两个分区的 Pass1 agent **掉线**（StructuredOutput 未返回 / agent 404 式失败，见 §5 与 `workflow-explore-agent-haiku-trap` 记忆）。这两个分区的 A 残缺，A∩B 互证逻辑无法施展。**此处 Pass2 的机械穷举顶上了**——因为调用图不依赖 agent 存活，一个掉线的 agent 不会制造**静默的覆盖窟窿**，图照样把该分区每个嫌疑节点列出来交人核验。这正是冗余设计的回报：掉线不等于该分区没被看过。

> 但补得不彻底：图只覆盖有调用图签名的债，掉线分区里的值级 P1 仍可能漏计——见 §5 置信度打折。

---

## 3）关键洞见：出血与护栏在数据流上同形，纯语法工具分不清

本次交叉检验挖出的最深一条：**「出血」（坏/假数据流向用户的 P1）和「护栏」（拦住坏数据的 P2）在数据流形状上是同构的**，纯语法/调用图工具**无法**区分，这正是「图必须靠人核验」的根本原因。

拿两个本次实测的真实端点对照：

**出血样本** — `core/services/report/execution_review.py`✅（在树、17.8KB，HEAD 仍在改）：执行复盘把记录算一算渲染给用户，若中途吞了坏数据就是出血。

**护栏样本** — `EvidenceLink.validate`，`core/models/schedule_plan_identity.py:102`✅（已回当前树核验、行号准）：

```
:107  raise ValueError("行级证据必须带来源表和来源行。")
:111  raise ValueError("汇总证据必须带汇总口径和参与数量。")
:125  raise ValueError("缺数据证据必须写清缺什么、查过哪里、影响谁和检查时间。")
:127  raise ValueError("证据范围必须是 row、aggregate 或 missing_data。")
:131  raise ValueError("证据来源表不可信，不能作为诊断依据。")   ← _validate_source_table ✅ 行号准
```

这是灵魂暗线「宁可暴露错误」的正面教材：坏数据到这里**抛异常炸出来**，绝不静默兜底放行。

**两者在污点工具眼里完全同形**：

| 维度 | 出血 execution_review | 护栏 EvidenceLink.validate |
|---|---|---|
| 输入 | 不可信/敏感记录 | 不可信的证据 payload |
| 中段 | 按数据形状分支 | 按 `evidence_scope` 分支 |
| 终点 | `return 渲染值`（坏数据逃逸=**坏**） | `raise ValueError`（坏数据被拦=**好**） |

调用图看到的只是「函数吃了 sensitive 污点输入 → 分支 → 到达终点 sink」。它**根本分不清**终点是 `raise`（护栏，好 sink）还是 `return 渲染的假值`（出血，坏 sink）——两者点亮的是同一条污点路径。

**而出血 vs 护栏，恰是本次普查 P1/P2 分类里最要命的那条分界线**，它在语法层完全隐形。所以图只能提名候选，**唯有读码看清终点是 `raise` 还是 `return 假值`，才能定性**。

这条洞见还顺手解释了 §2 的 B−A 假阳性洪水：B−A 里很多嫌疑其实是「抛错拦坏数据」的护栏，被图的污点模式当成「敏感数据到达 sink」点亮了，人核验一看是**好的那种 sink**（raise），不是出血。**图分不清护栏和漏洞，它只看见数据到了端点。**

---

## 4）数据流追踪的已知噪声源：两类系统性假阳性

把污点追踪器**两个系统性假阳性发生器**刻画清楚，供后续跑批预过滤：

### (a) repo / persistence / migration 层：`sensitive→write` 假阳性

追踪器把某些输入标「敏感」（plan 版本、scenario id、原始 payload），凡敏感数据流向 write/persist sink 就报警。但——

- 持久化层（`data/repositories`，**34** 个 py，其中 **17** 个带 `persist/save/write/insert/update` 动词）和迁移层（`core/infrastructure/migration_runner.py`、`migration_backup.py`、根 `schema.sql`✅ 实测在树）**把敏感数据写进存储就是它们的全部本职工作**。
- 每个 repo `.save()`、每次 migration upgrade 都点亮这条模式 → 系统性噪声。

**裁定：持久化/迁移层的 `sensitive→write` 是白名单噪声**，不是泄漏。

### (b) config 层：`hardcoded→render` 假阳性

追踪器把流向 render/output sink 的硬编码字面量当 P1（写死假冒计算值）嫌疑。但——

- 配置层（`core/services/scheduler/config`，**35** 个 py 实测）持有的硬编码常量**本职就是被读出来渲染**（预设名、阈值、默认标签、枚举显示串）。
- P1 病理特指**硬编码值伪装成计算结果**；配置常量光明正大地当常量，不构成 P1。

**裁定：源头在 config 层的 `hardcoded→render` 是白名单噪声**；只有源头在计算/服务路径、值在**假装是算出来的**那种 `hardcoded→render` 才是真 P1 嫌疑。

### 两类噪声同根

追踪器按**数据流形状**（源种类→汇种类）匹配，而病理关乎**意图/语义**（这值是否在伪装成它本不是的东西），且**依赖所在层**。同一形状，源头层不同则裁定相反——与 §3 同一个教训：**语法层定不了性，必须人核验 + 看清所在层。**

---

## 5）局限与置信度（按灵魂暗线明写打折，不静默兜底）

### StructuredOutput 掉线 → 掉线分区召回打折

部分 Pass1 agent 未经 StructuredOutput 返回（既有失败模式，见 `workflow-explore-agent-haiku-trap` 记忆：404/掉线的 agent 不吐发现）。**本次运行内即有实证**：任务 #42/#43/#44/#45/#35 仍挂 `in_progress`，指示在途/未完成的 agent 返回。掉线分区的 A 残缺，§2 已说由 Pass2 部分补上，**但 Pass2 只覆盖有调用图签名的债**，掉线分区的值级 P1（图照不到）可能被低计。**掉线分区召回置信度：中，非高。**

### 树外脚本无法 grep → 显式出界，非「已验干净」

普查的 grep/AST 扫覆盖四层主树（`core/services→data/repositories→core/models`、`web/routes`）。**树外脚本**——`tools/` 一次性工具（包括 `capture_networkx_phase0_baseline.py` 自身）、`.venv`、临时脚本——不在调用图抽取范围。树外工具里的债**按构造出界**。**置信度：这些路径是显式不在范围，不是「已验证干净」。**

### 未提交 / 未落盘证据 → 数字取自简报，代码声明经盘验（置信度分层）

写本章时，原始交叉检验产物 **`_graph_verdicts.json` 与 `CROSS-CHECK.md` 无法从磁盘读出**——运行目录 `2026-06-02-underwater-debt-census/findings/` 当时不存在于盘上（已用全盘 `find /` + `git ls-files` + 精确 glob 三路确认，clean 返回，排除了 macOS TCC 授权闪断的可能）。它们活在编排器运行缓冲 / 兄弟 agent 尚未刷盘的输出里。**按灵魂暗线「宁可暴露错误」，此处如实记录、绝不假装满证**：

- §2 的交叉检验计数（A∩B=12、B−A=25、两个掉线分区）**取自编排器任务简报，非由我独立从 JSON 重算** → 数字置信度：**简报级**。
- 承重代码锚点（`EvidenceLink.validate` @ `schedule_plan_identity.py:102`/`:130`、`execution_review.py` 在树）**已回当前 HEAD 树逐条盘验、确认行号准**✅ → 代码声明置信度：**盘验级**。

**置信度据此分层：数字是简报源，代码声明是盘验源。**

### 工作树未提交 → file:line 仅对本快照有效

普查跑在未提交的工作树上（`git status` 在分支 `codex/aps-three-gap-directions` 上有大量 M/A 暂存未提交文件）。**任何发现的 file:line 仅对此工作树快照有效，非某个已提交 ref**；后续 commit/rebase 会移行。**合并后须对合并提交重核行号。**

---

---

# 附录

## 附录 A · 六类病理定义(本次普查的统一尺子)

> 全 12 分区用同一把尺子,只报符合定义的真债,不报代码风格/命名美观/缺类型注解这类非债。

| 病理 | 名称 | 定义 | 典型反例 |
|---|---|---|---|
| **P1** | 写死常量假冒计算值 | 本应由解析/查询/计算得出的值,被写死的常量/字典/默认值替代,下游拿到假身份/假状态而非真实值 | execution_review 曾用 `ADOPTED_PLAN_RESOLUTION` 常量冒充真实 plan_resolution(已治) |
| **P2** | 承重的不对称(无注释保护) | 某处刻意和同类不一致(别处都传 X 就它禁传、别处都算它写死),这个不一致是故意的、承重的——删了/统一了会出安全事故,但代码里没有任何注释说明"我是故意的" | execution_review 禁带 plan_role/scenario_id 以拦截预览冒充正式复盘 |
| **P3** | 没做完的双实现/迁移残渣 | 同一职责两套实现(新旧并存)、shim 垫片、空目录、被绕过的旧路径,迁移做了一半停下 | 顶层 wrapper、gantt_plan_query 死 shim、双 ScheduleConfigSnapshot 栈 |
| **P4** | 躲过"不自欺"运动的静默兜底死角 | 项目有"坏数据不准静默兜底、宁可暴露错误"的灵魂原则,但仍有死角在 `except: pass` / `return 默认值` / `or 0` 把错误吞掉不暴露 | backup integrity_check 失败只 warning 不阻断 |
| **P5** | 同一概念的第 N 套私有实现 | 某个已有统一收口点的职责,在别处又被私自实现一遍(绕过收口点) | resource_dispatch 的第三套 scope 归一、boolean_normalize 双实现 |
| **P6** | 死参数/死面包屑/死代码 | 参数/函数/常量定义后无人真正消费(只在透传白名单里旅行、或零 caller),却散布多处造成"看起来在用"的假象 | plan_id 死面包屑、死读方法群、死参数 raw_value |

### 关于"失忆债"这个统称

本次普查的 6 类病理,本质是同一种债的不同表现形态:**代码在语法和结构上都正确,但某个概念的"真实含义"在不同地方悄悄分了岔,而没有任何单一权威来裁定哪个含义是对的。** 它不是架构债(结构 0 违规)、不是安全债(非攻击面),其载体不是代码缺陷,而是"丢失的共识"——LLM 当执行者、每个 session 无记忆这一生产方式的必然产物。还它的方式不是重构,是"立约":把丢的共识写回一个权威点,并给承重不对称贴上"别动"。

## 附录 B · 普查产物清单

| 产物 | 路径 | 内容 |
|---|---|---|
| 本报告(细颗粒度) | `.codestable/audits/2026-06-02-underwater-debt-census/REPORT.md` | 全部章节拼装 |
| 报告章节(可重拼) | `…/report-sections/*.md` | 各分区/横切独立 Markdown |
| 分区证据(机读) | `…/findings/_load_bearing.json` `_real_debt.json` | 承重护栏 + 真债结构化数据 |
| 调用图提取器 | `.codestable/checkup/scripts/callgraph_extract.py` | 可复跑(只读,Py3.8)重建调用图 |
| 工作台参数方言测绘 | `.codestable/audits/2026-06-02-workbench-param-dialect/README.md` | 起因:11 页参数方言 |

> ⚠️ 注:`DASHBOARD.md`/`CROSS-CHECK.md`/调用图产物目录(`.codestable/checkup/latest/callgraph/`)在生成期间被并发进程清理丢失,核心结论已并入本报告 §90/§91/§92;调用图可由 `callgraph_extract.py` 复跑重建。

### 调用图规模(基准 65870e47,复跑可重现)

| 指标 | 值 |
|---|---:|
| 函数节点 | 5874 |
| 调用边(总) | 22787 |
| 确信边 / 模糊边 | 7973 / 14814 |
| 动态未消解点 | 576 |
| 环 | 13 |
| 孤岛(零入零出) | 615 |
| 桥接点(articulation) | 772 |
| 高风险数据流路径 | 66 |
| 高扇入咽喉(fan_in≥5) | 60 |

- **§14 第三方复核产物**:`evidence/SemanticDebt/drift/drift-baseline.{json,md}`(drift 全扫 1606 findings)、`evidence/SemanticDebt/agent/drift-agent-brief.md`(triage 简报+A∩B 交叉核验+工具口径校准)、`evidence/SemanticDebt/agent/drift-mds-blindspot.json`(17 组审计盲区 MDS 明细)

## 附录 C · 未决裁断项(需 owner 拍板)

| # | 条目 | 分歧 | 待决 |
|---|---|---|---|
| 1 | `_positive_int` 可空簇该收到哪 | parse_finite_int 对垃圾 raise,契约不符;需新建 `parse_optional_positive_int`(垃圾→None) | **唯一"该收却无现成统一点"的债**——是否值得新增收口点 |
| 2 | `default_plan_resolution_dict` 键集 | 对抗验证称"今日侥幸对齐"但无 parity 测试 | 收口前必须先补 parity 测试坐实 |
| 3 | 双 ScheduleConfigSnapshot 栈 | "27 字段未漂移"依赖手工比对 | 收敛(service 栈复用 model 栈)前先补 parity 测试 |
| 4 | config/summary shim(5 个) | 已证 2 个非测试离线脚本在用 | Win7 离线只能证树内;删除前需确认无树外脚本消费 |
| 5 | `_normalize_critical_chain_result` | git status 标 `A`(未提交),可能是作者合并途中 | 落手前必须问在途作者 |
| 6 | common/number_utils.py | 是有意 delegation-facade(2026-06-01 KEEP/high 裁定)还是半截迁移 | 薄壳化须先重写 monkeypatch 测试 |
| 7 | ready_queue 全量版 | 差分测试基准 vs 遗忘残渣 | needs_adversarial 仍开放 |
| 8 | 延期诊断三件套 | 本分支 `aps-three-gap-directions` roadmap 在途契约 | 现阶段勿删,标在途 |
| 9 | 9 个 scheduler_*.py wrapper | roadmap 明示延期 | 现在动属抢跑,非债 |
| 10 | legacy 错误串往返桥 | P3 真债 vs 仍需兼容的过渡桥 | 改文案会静默失配,收敛前同步检查正则 |

## 附录 D · 置信度标注

**证据充分(可直接行动)**:P1=0、第一档死代码 grep 实证、8 处承重护栏代码实证、图×agent 12 文件双重命中互证。

**需补证(行动前坐实)**:default_plan_resolution_dict 键集"0 漂移"、双配置栈"27 字段未漂移"(均无 parity 测试)、config/summary shim 树外消费、`_normalize_critical_chain_result` 定性(未提交)。

**方法局限**:
- Pass-1 有 2–3 路 agent 因未调用 StructuredOutput 掉线(含关键的 core-models),已由 Pass-2 补扫闭环。
- 调用图调用消解保守:确信边只占 35%,动态调用(getattr/import_module)单列不画假边,故图的扇入扇出是下界。
- 数据流追踪已知噪声:repo/persistence/migration 层 `sensitive-identity→write` 系统性假阳性;config/预设/降级层 `hardcoded→render` 假阳性。
- 树外脚本(Win7 离线运维脚本)无法 grep,死代码判定仅限仓库树内。
- 报告生成期间遭遇并发进程清理 untracked 文件,中间产物经 agent 日志恢复,内容完整但调用图产物目录需复跑重建。
