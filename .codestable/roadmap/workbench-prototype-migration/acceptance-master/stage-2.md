# Task C 第二阶段证据

更新时间：2026-09-11 01:45 +0800。继续补本域缺项；下方保留 20:40 时的失败历史，本页不是最终全域验收结论。

## 当前状态

- 共享控件原 `jb7nijn7` 的 28/28 和 44 个工艺列宽合同没有重跑。原 41 个明确共享动作加上资源嵌套详情返回、工艺焦点/下层关闭、日历真实禁用、主数据自有行内表头，现为 46/50 个动作 B/K `reused`，P 为未提交视图不适用；剩余 4 个按实际挂载范围等 Main 决定，详见 `shared-scope-decisions.md`。
- 领域 58 族 / 599 个动作保留固定分母：B 240 reused / 359 pending；K 279 reused / 320 pending；P 98 reused / 140 not_applicable / 361 pending。599 领域与 50 共享的 V 全部仍 pending_main_review，不把有限代表图或家庭级场景自动升级为全部原子动作通过。所有 649 个 ID 的状态和精确证据见 `coverage-current.json`、`coverage-current.md`。
- Main 的 8 张列宽图和 DETAIL 范围决定只引用 `../round2-main-decisions.md`，C 不改该文件，也不扩大其 V 范围。较晚的原型新增表单编号串用证据另见 `detail008-reachability.md`，已交 Main 定边界，不继续重跑该项。
- **修复后的 context_restore 新完整源码验证：20/20 passed**，24 screenshots、314 steps。真实检查设备、工艺、批次、日历、主数据的 F5、侧栏往返、后退、选中身份和详情恢复；不是仅检查 history 内容。
- 该新运行根 `/private/tmp/aps-workbench-live-7iwt2eg8`；build `2ab72cffda0497d97b4576fec291da318c7d5b8cb110bbeab8c23da7012dcfdb`，223 files / 315 inputs；manifest SHA `46b8f2f589306a09275adeee3398a2dcc635746804f7fc64332e3c9e3d0f4607`。浏览器和重启读原记录探针均 exit 0；read_database_unchanged=true、restart_preservation=true、source_changes=[]，unexpected errors/external 均为空。23 条明确取消的只读请求保留为 expected，实际页面结果另有断言。
- 源为 `/private/tmp/aps-final-master-C-domain.GpjDC1/source-registered` 的完整 3934 文件副本；执行源 G 指纹 `503980c286dfc50e31b8459ef54537bc9c3511474c2c45b85cced7666f46134a`，整数 mode 模块清单 `source-executed-bound.json` aggregate `0fab53c0f4c460e1068dbd406dba3301311ba5b4dd3338d4b1dff2c30e716acc`。相对捕获源仅补 1 个 C 测试断言，详见清单 allowed_test_overlays。两次宿主实际导入 1111/1056 个仓库模块，全在该副本且 SHA/mode 匹配，violations=[]；结束后 3934 文件复核通过。
- context 结果 SHA `ca1a72b40a9853b069d62e94d0fcfbb74a4fbc61b7a49a9bd3dd2206e4e8d866`；整轮结果 SHA `1f1bbdaeb253667bdac92240cd4ecaf859e01d46a641a0d6a57d2ca3bf34b3a9`；运行前源 SHA `a74ca131122eca12f899e7266918751ab5383c1475d0f60fd175486e0b5c2b56`。自有宿主 35228/35393 正常退出。
- 同一完整源下的日历调用栈补证根 `/private/tmp/aps-workbench-live-vhn54uok`：8 个日历场景通过，40 条命令、28 图；旧保留断言仍因 ScheduleConfig 0→34 使整轮 exit 1，此失败未覆盖。增强观察器证实 34 次 INSERT 均属于一个真实成功 200、committed 的 calendar/upsert 请求，提交状态与最终 34 行哈希一致；不是错误请求偷偷提交，也不是每次刷新重复补配置。原首次栈和按 PID 完整观察文件均保留。
- 新的精确保留断言核对 27 个注册默认字段、4 个内置模板、3 个启用来源字段的完整键、值、说明、身份、时间、成功命令及回执；对应负向测试拒绝旧配置覆盖、缺行、错值、错误请求、错误栈和无回执。真实资源终态已经补齐，见下一节，不把单测代替实际重启。
- 工艺/批次旧根 `pss3e6vz` 的 67 cases / 14 failed 保留；新的 `su4resfc` 真实浏览器动作已全部完成，独立快照重验 67/67，原始 8 项测试 oracle 失败及两次重验失败日志均保留，见下文。没有改旧报告的 passed 字段。
- 捕获源的两次并发漂移，以及完整副本第一次构建缺少 PlanProcessOrder.js 登记的失败均保留。构建失败根 `dcf2dk5y` 未连接 SQLite；994 个导入模块仍全部来自该副本，违规为 0，31408 已退出。共享清单登记后才完成上述新 2ab72 构建。

## 当前补齐的业务证据

- 所有以下真实运行仍明确绑定构建 `2ab72cffda0497d97b4576fec291da318c7d5b8cb110bbeab8c23da7012dcfdb`、manifest `46b8f2f589306a09275adeee3398a2dcc635746804f7fc64332e3c9e3d0f4607`。副本之间只增加声明过的 C 测试 overlay；不是对 Main 后续 G05 或移动原树作整仓通过声明。
- 资源 `/private/tmp/aps-workbench-live-5ddb9gm0`：原完整 224/224，1260 条命令，464 图，errors/external 和 unexpected HTTP/console/request failures 均为空；浏览器源为 `source-resources`。旧 Python 后置断言错误地把文件导入的供应商索引当成 5，实际为 4；原失败 `final-master-result.json` SHA `88574e3479c499c74ab80f2cbd6bb847b902cb3f1a34bc81be2d283994565617` 和浏览器报告 `8def68cc194b5fab89c23e7c6eb56a23659a69f88b1a209b53c8c05d5e3116b6` 没有改写。
- 仅补资源后置保留与重启：`final-master-resource-resume-result.json` SHA `68bb48d5eeef3df6c9f6268b96ae9b18a3fc3109917e06754a8b7404053b59fa`，passed=true，原 224 项没有重跑。所有业务表原样；旧 identity 的实际 revision 增量由 72 条具体场景贡献精确解释，不按“只增不减”放行。34 条 ScheduleConfig 由一个真实 calendar/upsert、回执 `f186e08b6261463fa048db1f76e60d88` 初始化；初始 trace SHA `c8619652e74e8c6d071f5df22dc44513cab5e7862dc0aa1ad2ab48774200dbab`。重启后 34 行完整一致、写入次数 0，重启 trace SHA `e9d062e21852a7e4697a0998173082297d9d0976841c652803e234ca66db988a`。
- 资源宿主 45291/49908 正常退出，导入模块 1063/1057 均在各自声明副本，无违规。补验源 `source-resume`：3939 文件 G `964172e6c8221a17dec76554a03c6c00bbd9b94057487d2a1d25c2312ac3e2b0`，F 清单 `2364f02f9cee1d905177d62f5a323d12f06142eb8f678137dff568dbec02f9fe`，运行后全文件复核通过。
- 工艺/批次 `/private/tmp/aps-workbench-live-su4resfc`：67 场景，1354 steps、179 图、72 downloads。实际 UI 动作无 error/runtime_error；8 项在后置来源校验失败，原因是 JavaScript JSON 把 SQLite REAL 0.0 变成整数 0，以及旧 sequence 名单未包含新来源事件表。真实数据库 24 条来源全部通过产品 `validate_origin`；16 条出生事件可复现浮点类型丢失，不是修改或忽略产品的严格来源验证。
- `final_master_metadata_guard_support.py` 先逐行核对不可变 SQLite 事件和值，再读取其原始存储类型；C wrapper 精确核对新事件连续编号、sequence 增量和最大 event_id。新增 7 个类型证据测试、原 16 个元数据守卫，共 23 pytest 通过；另 9 个精确 sequence JS 断言通过。
- 工艺的 `final-master-process-revalidation.json` 单独记录 67/67，8 个旧 oracle 纠正，browser_rerun=false；SHA `fd291e9f75828910a7f1899813f5544f3de50b308dc29d7a18acf21395fec360`。重验驱动结果 SHA `1addaa7ce9f8a391974586ea3bda5bb0a20a3a8ab4e1eda21fc58172f1ecb4e3`。旧整轮结果 SHA `abdb08b93d47051759159a35e11e2dbc6908c3886311590657c004801d6d1ee1`、旧浏览器结果 SHA `a26c968cfa31b6484b3bfff776f33e683e1ccada3da85b124272419f275b30e0` 均保持不变。业务保留与真实重启在原运行已通过；重验没有写库。
- 工艺宿主 51334/52458 正常退出，1117/1056 个导入模块全部来自 `source-resume`。离线重验源 `source-lineage2`：3943 文件 G `828ab9f8d10b92865045d18fabaa4d565fbec343090dd289b57ed5219cc963aa`，F 清单 `58b1a6bd5d7d0b75beb3b312d1494d86f2db4914acedfc7b6e85d00fab27f083`；CLI 导入证据逐 PID 保留，违规为空。一次原 sequence 断言失败和一次 30 秒子进程超时的日志没有删除，重试只读快照最终通过。
- 主数据总览 `/private/tmp/aps-workbench-live-uio1t7lq`：新完整 40/40、44 图、206 steps，read_database_unchanged=true、restart_preservation=true、两次浏览器 exit 0、source_changes=[]、unexpected/external=[]。源码为 `source-lineage2`，宿主 55555/55841 正常关闭，1110/1056 导入模块无违规。浏览器报告 SHA `f418656aa80a0d6ee362c362f853a285dc815f0368b171cd629094d6ba0ab106`；整轮结果 `7efc24f78fd579f92458026b6fb00d461975c3c3342279b1cc7dc1ab445cf586`；运行前源码表 `2254d1a92d509b18d489e91cf256a00070fcd24d6df9aec459c9cb34b5d59fcb`。这替代旧 e091 的运行身份，不自动把所有 MD 原子动作绑定通过。
- 旧 batch_widgets 定点修复已按 Main 最新要求完成：只补真实 `WorkbenchPageContext.jsx` 依赖，原 32 场景/40 图通过，详见 `old-batch-widgets-fix-note.md`。不修 Main G05 缺 planning/actions fixture 的问题，不停完整执行。
- 缺失共享动作根 `7kvfmq7f` 完成工艺 focus/Tab 恢复、下层路线 Escape、原日历预览 loading 下日期禁用，以及 4 项范围观察；原主数据“弹窗”选择器假设错误的 4 个失败保留。仅该项另根 `rp8dshb6` 按实际 `.mo-filter-band` 行内筛选重跑 4/4，8 图、18 steps。两根 read_database_unchanged/restart_preservation=true，source_changes=[]，宿主 59936/60393 和 63302/63378 全正常退出。`rp8dshb6` 结果 SHA `a6d3ea9e29cfcddc078efe2fce466c440660d60f9b99282713d83111407887b3`，共享探针报告 `70813e371776a1c317a2d1dc0ddf08bbb699d3b868d7dd182cb4f997313dff67`。
- 新领域只读缺项根 `/private/tmp/aps-workbench-live-pyixrdav`：20/20、14 原子动作、40 图、182 steps，补齐四指标/八域逐项对 SQLite、前置工艺锁定、逐行增加删除、非连续序号、重复序号拒绝、未知工种摘要、无匹配搜索和上一页。源码 `source-domain-gaps` 为 3945 文件，G `2a9f071d8036b6ca9e09752937dfd7c483054e7bd2df0915455dddbc9cc432e2`，F `8e5a6c200cb22d65f24fd1ae69306da137931bafd20d432bcde02cae45959fc2`，运行后全文件复核通过。真实浏览器/重启均 exit 0、read_database_unchanged=true、restart_preservation=true、source_changes=[]，宿主 68148/68324 正常关闭。报告 SHA `56da8ac4789d08a5cad80b68fdca6af98a6b1c8e8702d35d6455dc439a5f7409`，整轮结果 `fbfdec8980cc11cff7f837ee05adb569aa1b4e5d651bbb29f31a90e207020f82`。
- Main V 最小代表集为 `main-v-minimum-index.json` / `.md`：8 组 / 32 张原始视口图，逐图记录路径、尺寸、bytes、SHA、build/source/report；资源录入、设备导入预检、日历范围预览、工艺就绪、批次刷新预览与详情、主数据字段、下层路线各四组合。只供 Main 按可见范围审图，不代表其已批准。
- 新文件与已有 C 工具更新的机械清单在 `new-files-handoff.json`，状态为 registration_requested_not_claimed_done；全局注册与 Main/H 的固定 G05 源由他们处理，C 没有修改统一 registry。

## 历史记录（20:40）

以下内容记录当时的状态，不覆盖上面的新终态，尤其不能再将工艺/主数据第 2 页修复写成尚未验证。

## 稳定窗口

- Main 冻结构建：`69ab1c53713a21acffe9810a3311ddf79538d4adeb1f86955ef272c0463372d8`，215 files / 307 inputs，Chrome 109。
- C 末次产品写入：`frontend/workbench/app/ProcessReadView.js`，文件时间 `20:23:08 +0800`；ResourceWorkspace/ProcessWorkspace 为 `20:22:18 +0800`。
- 之后仅改 `tests/workbench/final_master*`、`test_final_master*` 和本证据目录。没有 Git 写操作，没有停止其他域的服务，没有碰 53144 旧预览。
- C 私有当前完整构建的 build_id、输入和 payload 都经过 fixture 校验，与 Main 构建相同；不是复用旧 e091 构建。

## 已证实的产品阻断

### 工艺第 2 页刷新

- 真实动作：工艺搜索 `FC-P-`，图号升序，第 2 页勾选 `FC-P-021`，F5。
- 结果：history 中页码、排序、选中引用仍在；实际请求被后端拒绝，显示“继续翻页需要原列表快照，请先刷新。”四种视口/主题均复现。
- 根因边界：`frontend/workbench/app/ProcessWorkspace.jsx:76` 直接使用无 `snapshot_ref` 的恢复范围请求第 2 页；`web/routes/workbench/process_reads.py:58` 明确要求后续页携带原列表快照。
- 建议的最小修法：保持只读恢复记录不存旧 token；先用相同筛选读取第 1 页取得新快照，再读取原页并核对原引用。不得静默返回第一页或换选对象。产品修复等待 Main 解冻，不在本窗口实施。

### 主数据第 2 页刷新

- 真实动作：实体清单，零件域，搜索 `FC-P-`，编号升序，第 2 页选择 `FC-P-024`，字段页签，F5。
- 结果：实际列表显示“此操作需要原主数据列表快照，请先刷新。”四种视口/主题均复现。
- 根因边界：`frontend/workbench/app/MasterOverviewWorkspace.jsx:62` 直接以恢复页码和空 token 调用列表；`web/routes/workbench/master_overview.py:25` 拒绝无快照请求。
- 修复建议同上；选中实体和字段页签必须在新快照实际读取成功后核对，不能仅断言 history 内容即判恢复成功。

## 实际执行

### `context_restore` 第一轮

- 私有根：`/private/tmp/aps-workbench-live-kwfron_m`。
- `final-master-context_restore.json`：20 cases，4 passed / 16 failed，24 screenshots，214 steps。没有将辅助恢复场景冒充 599 个原子动作。
- 设备恢复四种组合通过：筛选、升序、第 2 页、勾选永久引用、F5、侧栏往返、浏览器后退、只读详情 F5、未保存新增表单不重放。
- 8 个失败属于上述工艺/主数据产品阻断。另 8 个是批次详情数据未就绪就断言、日历入口选择器错误；只修测试后补跑，旧失败证据保留。
- `final-master-result.json`：`read_database_unchanged=true`，`restart_preservation.passed=true`，原业务行完全一致；重启仅增加一条成功的禁用插件启动审计及对应 sequence。
- 初次和重启 `isolation_violations=[]`，所有自有服务正常退出。重启主数据原记录探针 8 cases / 0 failed。
- 执行过程中 source_changes 只有两个自有测试文件；没有产品构建输入变化。
- 四种组合：1920x1080 light/dark，1392x924 light/dark。V 均待 Main 看图，不自动判通过。

### 工艺与批次完整业务第一轮

- 私有根：`/private/tmp/aps-workbench-live-s255lk75`，同一 69ab 构建。
- 原探针实际完成 6 cases、207 steps、23 screenshots、8 downloads；场景内 0 failed，但之后初始化等待超时，所以整轮失败。
- 已完成：工艺表格读取、多页文件下载、新增零件、路线/归属/工时三阶段保存、旧分组隐藏保留、未知工种创建绑定。
- 超时原因：旧测试将同 URL `goto` 当成无状态新入口；新恢复合同实际恢复了 `AN-UNKNOWN` 工艺范围，再点当前工艺节点不触发它预期的第二个列表请求。没有 pageerror。
- 自有 wrapper 现在将独立场景入口显式经过 `about:blank`，保留原业务断言和 SQLite oracle；保存改写前后精确片段、原探针指纹及实际执行脚本哈希。原测试源不改，F5 恢复另由恢复探针覆盖。
- 重启原记录读取、业务保留和锁释放已经执行通过；不以此掩盖浏览器整轮失败。第二轮根为 `/private/tmp/aps-workbench-live-spwb5_r8`，本页此时尚未读取终态。

## 仍待完成

- 修正测试后的批次/日历恢复、共享控件、工艺/批次完整业务、资源完整业务与 `ScheduleConfig` 34 条新增的调用栈判定。
- 旧 e091 构建上的总览 40 cases 和资源 224 cases 是历史执行证据，不自动覆盖本轮已改的恢复产品代码。
- `actions.json` 仍为 41 主数据族 + 17 批次族，共 599 原子动作；`shared-actions.json` 另有 50 动作。未逐项绑定有效证据的项目继续 pending，不降低分母。
- Main 负责共享注册、正式全门禁、最终 HEAD 与 V。当前工作区不干净，不是 clean-worktree proof。

## 可重跑命令

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-final-master-c-pycache CHECKUP_CALLGRAPH=/tmp/aps-final-master-c-callgraph .venv/bin/python -B -m tests.workbench.test_final_master_acceptance --phase context_restore
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-final-master-c-pycache CHECKUP_CALLGRAPH=/tmp/aps-final-master-c-callgraph .venv/bin/python -B -m tests.workbench.test_final_master_acceptance --phase process_batches
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-final-master-c-pycache CHECKUP_CALLGRAPH=/tmp/aps-final-master-c-callgraph .venv/bin/python -B -m tests.workbench.test_final_master_acceptance --phase controls
```
