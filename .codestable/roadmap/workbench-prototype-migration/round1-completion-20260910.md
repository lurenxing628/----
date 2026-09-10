# 第一轮补漏记录

- 日期：2026-09-10。
- 授权：完成第一轮已知代码与契约补漏，允许新建多 agent 并行；不进入全站验收、容量终验、Win7 发布或旧 UI 下线。
- 状态：第一轮已知补漏与相应联合验证完成，按本轮范围停止；不把中间失败或未运行项目算作通过。
- 工作区原有大量 dirty，所有本轮更改均未 stage/commit；不能据此称 clean-worktree、最终 HEAD 或完整质量门禁通过。

## 本轮修改

| 范围 | 完成内容与证据 |
| --- | --- |
| 分件零工时 | 原单件身份、目标 1、原报工依据进入零工时证据；真实 worker、候选采用、正式读取、试调移动/再采用和 DATE 连接重读贯通。缺证据、正工时、错件或错目标仍拒绝。见 `../../issues/2026-09-10-round1-piece-point/round1-piece-point-fix-note.md` |
| 文件兼容 | XLSX 原十列顺序保留，新下载在尾部预填任务编号、工序范围、单件编号；十列仅唯一匹配，歧义、错身份和过期引用拒绝。CSV 恢复旧“目标数量”列名，原 42 列及尾部 5 个计划字段合同不变。见 `../../issues/2026-09-10-round1-field-piece-files/round1-field-piece-files-fix-note.md` |
| 类型与复杂度 | 按批次、执行、计划、委外、报表、工艺、运行、试调分域收紧真实输入与返回合同、拆分职责；没有新增 ignore、提高门限或新增复杂度豁免。原产品范围 81 errors 降为 0，原 15 warnings 保留 |
| 原 copy/template/protect 红灯 | 批次复制与导入失败统一走既有仓储异常合同；精确保留旧行，逐项核对合法新映射；真实 SQLite 第二行失败验证零半写。见 `../../issues/2026-09-10-round1-batch/round1-batch-fix-note.md` |
| 共享查询与依赖 | 执行台账事实投影归位到 `core/services/execution/`，共享计划读取归位到 `core/services/common/`；旧路径保留同对象转口。备份恢复实现归位到 `core/services/system/backup_restore.py`，宿主负责自己的连接生命周期 |
| 启动与失败可见性 | 配置选择器不反依赖根配置，factory 传入同一配置映射；锁仍先于 app/DB 副作用。保留停止屏障、原回执、异常日志和恢复只读状态，不把不确定结果当成功 |
| 启动台账 | 逐项核查 16 个可观察或清理处理器，对齐 6 个旧位置；旧完整台账、旧 ID 和原异常行为测试保留。仅更新实际行为登记和行号，不改变分类器、复杂度/大小白名单、测试债务或其他风险记录 |
| 额外集成修正 | 明确分件模式标志，禁止只凭非空 piece_id 猜模式；XLSX 计划/快照元数据用字符串单元格，保留以 -/+/@/= 开头的真实引用；维护页浏览器探针等待节点挂载；旧候选断言按真实存储表核验，不强制重复落明细 |
| 测试与扫描登记 | 新增测试逐项登记到实际 owner，新共享模块和 fixture 的影响面进入对应组；浏览器保持 supplemental。动态导入只解析能静态证明的常量与真实源路径，未知仍保留未解析，不改循环依赖基线 |
| 测试夹具接合 | 通用 SQLite 快照函数归入公共支持目录，原路径保持同对象；v19 升级夹具补齐 v30/v31 的精确 35 项结构差集、空事实与映射断言。候选迁移使用历史提交 `196d7e56ecc2f7cfc2ea6b2140227b73cb2e1fed` 的真实 v9 DDL，不以当前残缺结构冒充旧版 |

## 验证口径

- 执行环境：本机 `.venv/bin/python`，Python 3.8.10；私有 SQLite、日志、备份、运行锁和隔离 bytecode 目录。没有操作生产库、重启旧预览或清共享缓存。
- 各域回归有交集，不能简单相加成独立总数。逐域日志、XML、源码 SHA-256 和交接记录汇总于 `output/workbench-migration/verification/round1-20260910/`。
- 已完成的主线定点组：恢复与宿主 82 passed；运行异常/生命周期 41 passed；维护合同及真实浏览器 89 passed；配置装配与锁前置 32 passed。这些集合也有交集。
- B 的真实 Chrome 109 文件工作流覆盖 1920x1080 / 1392x924、深浅色，共 4 组合；真实下载、填报、预检、确认、刷新、导出和重复导入均检查持久化数量及引用。主线复核了导入预览和窄视口刷新截图。
- 额外执行无路径参数的默认 Pyright，包含 tests，最终得到 2011 errors / 16 warnings，所有 errors 都位于 tests；该检查未通过，不和原产品范围的 81 条混为一谈。新增 SGS 测试自身的 3 条类型错误已消除，没有为此改全局配置或豁免类型错误。

## 最终验证

| 检查 | 最终实际结果 | 本轮证据目录内文件 |
| --- | --- | --- |
| 原产品类型范围 | 1161 files，0 errors / 15 warnings，原 81 条 errors 清零 | `pyright-product-frozen.json` |
| 架构及原扫描器合同 | 47 passed，含原架构 21/21；原 4 项架构失败消除 | `architecture-final.xml` |
| 业务联合回归 | 821 passed，0 failed/error/skipped，93.55 秒；包含全部本轮业务测试、实际浏览器、旧复制及升级边界 | `verification-final.xml` |
| 额外旧执行/候选/真实 v9 回归 | 同一 42 项全部通过，不删除原断言 | `R1-I-test-contract/freeze42.xml` |
| 新 SGS 测试类型收口 | 10 passed，定点 Pyright 0 errors / 0 warnings | `sgs-test-contract-final.xml`、`sgs-test-types-final.json` |
| 测试登记 | 最终 582 required / 85 supplemental / 33 groups，无缺失、重复或未知 owner | `final-verification-summary.json` |
| 登记及缓存 | 首批 1323 passed；SGS/L/公共快照增量分别 86、58、35 passed；主线最终完整新登记合同及候选 schema 163 passed。集合不相加，未声称在 582 上重跑原 1323 全套 | `registry-final.xml`、`agents/K/` 及 K 增量交接记录 |
| 生产及含测试导入扫描 | `--fail-on-new-cycle` 均 exit 0；新增圈、圈内边和未解析动态导入均为 0，parse errors 为 0 | `imports-product-after.json`、`imports-with-tests-verified.json` |
| 启动台账 | 结构、实际样本和当前扫描校验通过；原非启动条目和其他治理分区保留 | `ledger-verified.log`、`ledger-preservation-proof.json` |
| 改动检查 | `git diff --check` 通过；主线最终源码/测试 SHA-256 复核一致 | `main-sources-verified.sha256`、`main-last-test-sources.sha256` |

821 项联合运行有两条 pytest `record_property` 与 `xunit2` 输出格式警告，不是测试失败。原工艺文件中的两条 10000 工序夹具回归随同执行，不代表 5000 同资源排产容量终验。

导入检查通过指相较既有冻结基线没有新增债务，不是全仓零循环：原有 1 个目录硬环、8 个文件硬环和 43 条真正动态未解析仍在。没有通过改基线或改扫描范围掩盖这些事实。

汇总机器证据为 `output/workbench-migration/verification/round1-20260910/final-verification-summary.json`。中间失败日志保留：D 新测试变量遮蔽、浏览器探针节点未挂载，以及 v19 夹具漏列新版本结构均在修正后按原集合复跑通过；没有标 xfail 或删除数据保留断言。

## 构建与保留

- 离线完整前端构建成功，目标 `chrome109`，build ID `eaa69eec9bf98dbecac97b6be1baa322ff34c2a5df4ca1264ddd0bd4548bf8bf`。
- 210 个输出文件逐一核对字节数和 SHA-256，302 个构建输入逐一核对当前源哈希；输出在本轮 `offline-build/`，没有发布到 `static/workbench`，没有替换原 53144 预览。
- 原源码归档 SHA-256 仍为 `5cf4ecc190bcafc11fb80bdccb40733e0e93624d86d8c2fc45854a224b900b3b`。
- 唯一原 staged 文件仍是 `tests/gate_meta/test_frozen_bundle_contract.py`，文件 SHA-256 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`；整个 staged patch SHA-256 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`，没有改变。

## 未包含的工作

- 不代表整个移植完成；全站功能矩阵验收、5000 同资源容量终验、完整质量门禁、最终离线包、Win7 真机与旧 UI 下线未做。
- 308 个 required 文件仍未被 Git 跟踪，即原 280 加本轮 28；另有一个原已跟踪候选 schema 测试被正式纳入 required。不通过 git add 或改门禁消除 tracked 阻断。
- 15 条产品类型警告及包含 tests 的默认类型错误尚存；完整门禁须在明确的集成和提交安排后另跑。
- CSV 外部实际解析脚本未找到仓库内证据，因此只确认本仓库格式合同与回归，不声称所有外部消费者兼容。
- 本轮到此停止推进，下一阶段须按用户安排另行开始。
