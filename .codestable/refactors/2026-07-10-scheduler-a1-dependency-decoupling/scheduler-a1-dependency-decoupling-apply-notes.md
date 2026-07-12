---
doc_type: refactor-apply-notes
refactor: 2026-07-10-scheduler-a1-dependency-decoupling
status: implemented-awaiting-clean-proof
---

# scheduler A1 dependency decoupling apply notes

## 步骤 1：刻画兼容与导入合同

- 完成时间：2026-07-12
- 改动文件：`tests/schedule/service/test_scheduler_a1_dependency_boundary.py`
- 验证结果：先运行单测得到预期红灯，pytest 在收集阶段因 `core.services.scheduler.contracts` 尚不存在退出 2；测试已锁定旧/新路径对象 identity、7 个关键签名、正逆序新解释器导入和 A1 四目录 SCC 消失条件。
- 行为等价自检：只新增刻画测试，未改生产行为。
- 偏离：无

## 步骤 2：根目录叶子能力归位

- 完成时间：2026-07-12
- 改动文件：`core/shared/boolean_normalize.py`、`core/services/scheduler/number_utils.py`、config/run/summary 下 9 个直接调用模块。
- 验证结果：`tests/config`、`tests/schedule/summary` 与 yes/no 单源合同共 336 passed；目标文件 Ruff 通过；旧根路径与 shared/model 叶子逐项 `is` identity 通过。正式扫描中 config 已退出 A1，残余圈由四目录 49 条缩为 root/run/summary 三目录 30 条，hard 目录 SCC 总数仍为 6，未新增 SCC。
- 行为等价自检：`to_yes_no` 原实现原样归位到 shared，有限数字函数和降级文案只改 import 方向；默认值、解析与文案均由既有测试锁住。
- 偏离：无

## 步骤 3：execution 族下沉

- 完成时间：2026-07-12
- 改动文件：新增 `core/services/scheduler/execution/` 五个文件；四个旧根模块改为显式 re-export；run、scheduler 根业务模块和 web 的生产调用方均直连新叶子。
- 验证结果：operation execution 与甘特发布快照专项共 155 passed；目标 Ruff、旧新对象 `is` identity、正逆序新解释器导入均通过；execution 子包无函数内 scheduler import，未进入任何 hard SCC。正式扫描的 A1 残余已缩为 run/summary 两目录 8 条边，hard 目录 SCC 总数仍为 6。
- 行为等价自检：四个实现原样移动；`positive_op_ids` 归到 fact provider 供 snapshot 单向复用，删除了旧 snapshot→provider 函数内 import，hash 拼接、排序、仓储读取和异常文本均未改。
- 偏离：为真正降低模块复杂度，消除了 execution 内原有 provider⇄snapshot 隐式环，而不是把旧函数内 import 原样搬入新叶子；公开对象和签名保持 identity/等价。

## 步骤 4：summary contracts 下沉

- 完成时间：2026-07-12
- 改动文件：新增 `core/services/scheduler/contracts/` 六个文件；五个旧 summary 模块改为显式 re-export；run、summary 和 web 的生产调用方均直连 contracts。
- 验证结果：最初红灯的 A1 边界测试已转绿（4 passed）；orchestrator、summary、optimizer 投影、graph 与 candidate 合同共 321 passed；目标 Ruff 和结构 grep 通过。正式生产扫描为 761 模块、5 个 hard 目录 SCC，A1 四目录均未进入任何 SCC，contracts 也未进入 SCC。
- 行为等价自检：五个实现原样移动，dataclass 字段/默认值、公开白名单、脱敏规则和 count 错误文本未改；旧 summary 路径与新 contracts 对象由 `is` 合同锁定。
- 偏离：无

## 步骤 5：A1 静态与动态验收

- 本地实施完成时间：2026-07-12
- 改动文件：双 scope import-cycle v2 基线、10 份正式调用图快照、checkup 总入口/README、scheduler 架构、循环审计、roadmap 与调用图路径合同测试。
- 循环证据：production 761 模块 / 5 hard 目录 SCC，production-and-tests 1455 模块 / 6 SCC；A1 四目录均不在任何 SCC，其他 SCC 成员和圈内边逐项不变，unresolved 仍为 6 / 44。双基线各只删除 A1 一个 59 行块，刷新前后正式门禁都通过。
- 调用图证据：两个独立临时目录的 10 份 JSON 逐文件 SHA 相同；7329 callable、25786 输出边、10166 confident、15620 ambiguous、typed 0、8 个受限简单循环、193 islands。旧函数按移动路径映射后零增删，旧调用边零丢失，生产直连新叶子后新增 14 条原先被 wrapper 遮挡的确信边。
- 动态验证：A1 广覆盖专项 1543 passed；完整门禁 19/19 命令通过，4716 collected、collection error 0、unexpected failure 0、required 253 targets / 2467 nodeids。Ruff、Pyright gate/tools、1153 文件 Python 3.8 扫描均通过。
- 证明边界：完整门禁使用 `--allow-dirty-worktree --no-long-gate-cache --no-resume`，manifest=`passed_but_unbound`，运行器按合同退出 2；当前未获提交授权，不能声称 clean-worktree proof。
- dead-code 说明：仅把 2 个 `ExecutionFactProvider` 基线身份迁到新路径；archived 起点 HEAD 自身也报告 32 个无关新增 quick 候选，因此没有借 A1 全量 refresh 接受既有漂移。
- 行为等价自检：排产算法、数据库、事务、路由、公开字段、错误码/文案和公开签名均未改；旧路径 identity 与正逆序独立进程 import 通过。
- 偏离：为避免兼容 wrapper 遮掉静态调用边，除设计要求的 run 调用方外，其余生产调用方也直连新叶子；旧路径仍完整保留给兼容消费。该调整让调用图多看见 14 条真实边，没有新增抽象或兜底。
- 阻塞项：需用户明确授权提交后，在最终 clean HEAD 上无缓存、无续跑再跑完整门禁；完成后才能把 refactor/roadmap 标为 completed。
