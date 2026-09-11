# 现场与校准重启修复、完整源码封存

状态：四文件恢复修复定向验收已完成，最终固定快照 **9 passed / 110.82s**。产品文件及交给 B 的 source/manifest/build/assetroot 已停止写入；精确复制地址、哈希与原结果见 `08-b252-handoff.json`。这不是 B252、69 族全部动作或最终 HEAD 通过。

## 根因与边界

- Main/B 原静态疑点不直接算失败。E 用同一个 Chromium 109 页面和 browser context 保活，在原端口停服、启动新 PID，再执行 F5，才确认 Field 与 Calibration 都把 history 中的进程内 snapshot_ref 回传，收到真实 `snapshot_stale` 409。
- Field 使用查询 B1、size 10、page 2、原正式计划、原任务/执行工序以及真实报工；重启前输入一段未保存备注，重启后没有 POST。Calibration 使用 query P1、source internal、sample_count 升序、size 10、page 3、原模板和原有效样本。
- 永久引用均来自本轮真实 fixture DB；测试没有以新对象替换旧对象，没有用样例 HTTP/adapter 冒充完整入口。
- 新进入/F5/明确刷新只启动新读取。先用相同永久筛选读取 page 1，再以该响应的 token 读取原 page N。详情和文件使用合法新列表的 token。活动页面的旧 token 仍原样发出、真实 409，不自动重试或换新 token。
- 没有修改 public token registry、TTL、持久化令牌、服务端 409、数据库 schema、写命令、System/Dashboard、共享 build-order 或测试登记。

## 产品范围

| 文件 | SHA-256 |
|---|---|
| frontend/workbench/app/FieldAPI.js | a320d072036113ed505381b9c4e91396ec2608a492236d476719fd4bf7bc6403 |
| frontend/workbench/app/FieldWorkspace.jsx | da53e462bbcb47922fc7c508158c7fc2ed51c86ffba35961716e61f2067f42a5 |
| frontend/workbench/app/CalibrationAPI.js | b50d402150bc5974dd2f62afc47e3f345c4493e86f2fbf754b7ea572f80d4a97 |
| frontend/workbench/app/CalibrationWorkspace.jsx | 500efa73b75c9d0b7ad347c10ae4048177fbbfa230f09401c7c8519f26c1b6a6 |
| frontend/workbench/app/ReportAPI.js | 4acaeea96cb63f84f2501f43005d934a493975e1c2924a1d9b9445b2f8e511fc |
| frontend/workbench/app/ReportWorkspace.jsx | 1908d9d2c06ef3f37cf212f2f4fef79967e63f2dff8979a3508ee48caf863b4e |

Report/Review 的两文件及原修复见 06。本次没有新增前端叶文件，既有加载顺序不变。

Field 历史排除顶层、scope、table 的旧 token，保留永久条件与任务；显式保存的原页不允许被 backend 的任务定位改为另一页。没有显式页码的新外部导航仍可定位原任务所在页。明确刷新绑定已实际读取的永久计划，不因原上下文省略 plan_ref 就换为新的正式计划。

Calibration 将持久读取参数的校验与活动分页校验分开：底层 `input` 仍拒绝 page > 1 没有 token；只有显式新读取入口负责合法 page 1 引导。原 template/sample refs 和列宽不变，表头 facet 查询使用新的有效 bound scope。

## Sealed Source

Main 本轮明确要求以后在 E 自有完整 sealed source 上构建和运行。新增 `tests/workbench/final_execution_source_binding.py`，复用 G 的 `source_inventory.py`、`source_binding.py capture/check`、`FrozenSourceGuard`，不改 G 文件。

- G 静态发现全部现行仓库 Python roots，并纳入本地 assets、templates、frontend、vendor、tests/fixtures 等原清单。
- 加入全部非 Python 的 `.codestable` 事实资料、根 Markdown、docs、开发文档、策划方案、前端设计、.github、.limcode，以及实际复用的三个 G 检查模块。未应用的 `.codestable/legacy-retirement/draft-payload/*.py` 不是现行可执行模块；没有把其尚未存在的目标 import 当作现行代码，也没有忽略缺失模块检查。
- 捕获 SHA、bytes、mode；复制后分别核对原 preimage 与副本。副本以独立清单固定，不在测试结束时要求已经继续工作的原树仍与之相同。
- 所有 repo imports 限定到 sealed source；原 venv 只提供解释器及第三方包。G guard 在 pytest 主进程和每次服务器 PID 上记录实际模块路径，并拒绝原树回读；退出时再次核对全部清单内容和权限。
- 完整构建的每个 input 与文件 hash 仍逐项校验。没有更改 skip、删掉断言或忽略 expected hash。旧资产与旧失败证据不覆盖。

## 实际记录

| 快照 / 运行 | 结果与范围 |
|---|---|
| sealed-read-before-20260911-01 | capture 拒绝尚未应用退役草稿中的缺失模块；没有运行测试。 |
| sealed-read-before-20260911-02 | 首个副本缺少 tests/conftest 需要的开发文档台账；collection internal error，没有产品复现。补全事实源后新建副本。 |
| sealed-read-before-20260911-03/before-01 | 2 failed / 33.24s。Calibration 为真实新 PID 409；Field 是测试备注控件定位失败，不能算产品失败。pytest source guard 核对 992 个加载模块通过。 |
| sealed-read-before-20260911-04/before-01 | **2 failed / 20.58s，均为真实旧 token 409**。Field root 925ovb37、Calibration root f45p_25w；原页/原对象/history/截图/重启 PID 留存。 |
| sealed-read-after-20260911-01/after-01 | **6 passed / 1 failed / 89.25s**。Field 全部重启步骤、Report/Review 两视图重启、两项拒绝/未知命令测试、旧 Calibration 组件通过。Calibration 已完成新 PID 原页原样本恢复、同 PID 往返/F5及真实文件下载；最后显式刷新时测试过早读取异步事件数组。真实 wire 已有 page 1 -> page 2 及原详情 200。仅修改测试为等待目标页的明确响应，保留该失败。 |
| sealed-read-after-20260911-02/all-final-01 | **49 passed / 4 failed / 314.14s**。两项旧测试要求返回来源 token 不变、校准重新进入必须 409，已按新合同修正并保留活动态 409；报表 probe 将恢复 page 2 的引导 page 1 当作最终渲染行，已改为明确等待原目标页并核对它绑定引导响应 token；校准 probe 过早 full reload 使未收完的详情 response body 消失，已加导航前网络完成和原始响应体 drain，采集错误仍明确失败。 |
| sealed-read-after-20260911-03/all-final-01 | **51 passed / 2 failed / 414.16s**。完整 56 次下载与字节/SQL/元数据核对、采用与锁定及原回执重启等已通过。剩余复盘跨现场返回仍有两处旧 token 相等断言；校准负例写入 history 时新详情尚未完成，后来正常视图发布覆盖了测试输入，未实际请求未知 ref。未将其冒称产品替换未知对象。 |
| sealed-read-after-20260911-06/reentry-final-01 | **9 passed / 110.82s**。两域完整重启/旧形态 history/原页原对象/下载/活动 409/未知 ref 失败，Report 与 Review 两视图同 PID/F5/新 PID，两个纯策略单元，两个拒绝与未知命令用例，以及完整复盘导航均通过。 |

上述目录均在 `/tmp/aps-final-e-` 前缀下，各运行的 `pytest.xml` 为原结果。pre-fix 04 的完整 source SHA 为 `0d47824c29103e087937b9aefdc758934d7878f6e4a852a22a55eabadb65037d`，6516 files / 318750624 bytes。

当前 after 02 完整 source 在 `/private/tmp/aps-final-e-sealed-read-after-20260911-02/source`，`source-manifest.json` aggregate SHA 为 `3a3a25a4a1c7a823d0bf9ef992e787843f6c26318c7c894a084e87676ffcc24c`，6522 files / 319163039 bytes。测试使用原 `.venv/bin/python` 执行该副本内的入口，不从原 repo 载入代码。

该整组退出时 `sealed-pytest-source.json` 核对 1141 个仓库加载模块、内容和 mode 通过，read violations 为零。该副本上定向 Ruff 全部通过、Pyright 0 errors / 0 warnings；Pyright 另提示副本未复制 `.venv`，本次已明确 `--pythonpath` 指向原第三方解释器，并没有在副本建立回原仓库的代码链接或升级工具。

### 最终固定底本

- 按 Main 最后指示，03 后没有为 B 再追 moving 原树。06 由已固定 03 完整机械复制，复制前后都通过 G check；只覆盖两份明确 E probe，再由 G capture/check 固定新清单并逐文件证明差异集合恰为这两个测试文件，见 `source-delta.json`。全部产品文件、模板、静态源、build inputs 与 03 不变。
- 派生尝试 04/05 没有运行测试：原 manifest 的 extra_paths 含已被 G 自身规则排除的 .DS_Store/历史 .db，不能据此重建复制清单。06 直接把原 manifest 的全部 6532 条 files 作为 extra 集合，保留静态发现并严格比较全文件差异，没有忽略应有源文件或期望哈希。
- 最终 source 为 `/private/tmp/aps-final-e-sealed-read-after-20260911-06/source`，6532 files / 319481080 bytes，聚合 SHA `2d6c6f12a3b2496d791cd9eb6f846b4dd26260facc334d568a68166561cff1d5`。最终 pytest 核对 998 个已加载仓库模块，source 内容和权限未变，原树回读零次；每个真实服务 PID 均另有 sealed-process 文件并正常退出。
- Field 原目录 ob8_k949：端口 61398，PID 51421 -> 51472 -> 51519。Calibration 原目录 ds0d4zps：端口 61804，PID 51548 -> 51591 -> 51623。两域各五项完整步骤均通过；数据库永久行不变，重启仅精确增加 plugins/load 审计与相应序列。
- E 已目视两张新 PID 原页恢复的 1920 light 截图；1392/1920 深浅截图均留存。此处不是 Main V 批准。
- H 已由 Main 独立确认三项旧复杂度收口，E 不再重复修复。四个原产品文件当前 SHA 与最终 source 清单一致，停止写入；B 可读取复制 source、相邻 manifest、build_root 与 assetroot，剩余统计文档不作为 B 的等待条件。

## 证据含义

- `test_final_execution_read_reentry.py` 是两个真实完整入口用例；`test_final_execution_read_contract.py` 是显式 synthetic adapter 的纯策略单元测试，不可当作 K 或真实 B 证据。
- 对比 Field 事实时只将新签发 write_token/expiry 与不可变事实分开；保留其权限和拒绝原因比较。Calibration 的 snapshot/as_of/generated_at 逐行必须绑定新 meta，其他模板/样本/报工/修订字段完整对比。
- 用户操作测量期的所有业务表相等；每次重启只允许一条原 plugins/load 日志与其精确序列增量。此规则不将 fixture 准备的写入冒称只读。
- 本记录不是 final HEAD 或 clean-worktree proof。Main V、全域同源合并验证、最终登记和 Git 归档仍待 Main；69 WBP 内部原子项矩阵仍需单独核账，不能用本次几个复现用例把整个分组判通过。
