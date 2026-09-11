# F 当前进展与历史证据

## 当前视觉补充交接（2026-09-11）

- 文档映射和最小补图已完成，**不是 Main V 全通过**。Main 已签精确 54 张（原 28 + delta 26）；delta 记录 SHA-256 `64dfe3e2d1c8cdc5f1e529ebf2117d85d68a647b768e30b1f37edcdfa4468a93` 已核对。旧 209 图、原 55 delta 的顺序、228 action 分母和原 B/K/P 不改。
- [新增 20 图小索引](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/visual-supplement-index.md)逐项列出真实 path/SHA/视口/动作/可见范围；[完整状态清单](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/main-v-state-map.md)列出待看代表 **57 张 = 32 旧独立状态 + 5 delta + 20 补图**。原 28 和新签 26 不重复要求 Main 看。
- delta 只需补看原数组零基 index `2,5,8,11,23`：前四张是原清单第二页/选中详情，不是已签的历史页；`23` 才是 1392/light 普通可操作备份详情，已签 `20` 是 pending 配置下操作禁用的状态。其他未看的 24 张明确列为同 source18 的 before/inactive 备用，不擅自标已看。
- [机器索引](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/main-v-state-map.json) SHA-256 `3b6f98243a714f6cd4f9846149d3ab21c8d337de3c97f086c87aae3fa7299120`：229 张真实图逐图绑定 source/build/hash，228 项反向映射，0 action 自动通过。209 张旧 PNG 的 SHA 全不同，代表关系不是字节去重；可共用组件和字段变化、不共用的错误/回执/冷暖维护分支均有说明。
- [补图运行证据](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/visual-supplement-evidence.json) SHA-256 `f386a3b43f0031ca1ad4dde85af1d23903ee544368b3dece0ef2f64becd84364`：固定 source18/build16 的 **4 个独立 runner 用例 PASS / 20 图**，不是 pytest/JUnit 的 21 delta 重跑。四组合均有真实补图，已由 F 逐图确认目标可见，Main 尚未签。
- 本轮只写 F 文档、新独立 harness 和 evidence，不改产品、旧 source/build 或旧证据文件。source18 的 3672 文件和 build16 的 223 资产逐 SHA/大小核验不变；进程 `57831/57872/59144/62149` 的加载模块绑定分别为 `1113/1114/1114/1113`，0 违规，均已正常结束。必要正向输入仅发生在独立测试库：处置前置历史、一次外协物流登记和一个新测试备份；未删除或恢复备份，未改报工/正式计划表。
- 独立 harness 首次等错现场接口路径的失败保留在 `F-visual-supplement-run1`，不计入通过。4 个通过用例的源码、请求、SQL保留、备份和进程证据均单列。本轮没有 Git 写入、没有再抓 fullsnapshot、没有 B252 或全量门禁、没有 clean-worktree proof；后续仅由 Main 实際看图签署适用 V。

## 当前结论（2026-09-11 新 delta 已验证）

- 33 族 / 228 动作已收齐。`action-evidence.json` 当前为 K 228 通过、B 222 通过 + 6 项纯页面偏好不适用、P 227 通过 + 紧凑行距 1 项不适用。13 项补全与后批准的 R14 两项分别记账，没有用 N/A 消除产品缺口；B/P 按对应真实流程和共用状态持有者核对，不声称 228 项各自独立重启。
- 原 13 项完整主入口矩阵为 `F13-copy-matrix4-results.xml` 14 PASS / 180.02s，含四组正常、八组恢复及两项边界；真实在途请求/worker 排空和恢复后新数据保留为 `F13-inflight1-results.xml` 1 PASS / 15.74s。旧 106 项后台/接口回归绑定 source8，不冒充最终 HEAD。
- 新 delta 为 `F13-final-delta1-results.xml` **21 PASS / 156.94s**：19 个真实完整主入口用例 + 2 个源码边界测试。包含 R14 四组合、Dashboard 原浏览器第二页跨新 PID 四组合、System 备份/日志各四组合、同名替换/缺稳定 key/原待核实配置三项边界。源码核验 3672 文件零变化、38 个进程 violations 均为空；其中 15 个用例原 page/context、原端口保活跨 PID。
- Dashboard 恢复不再持久化进程内快照；第一页仅用于同筛选新快照绑定，随后显示原第二页，保留原条目和历史第二页。R14 取消/X/遮罩/Esc 不导航不写；确认只进入已知空概览，返回仍为原条目，未知目标或缺回调明确报错。
- System 恢复保留原筛选/页码/稳定记录 key，不把 snapshot_ref 或 backup_ref 当永久身份；新清单唯一匹配同 key 后使用新 backup_ref。同名替换和缺 key 明确提示、不选第一项；旧读、下载、删除和恢复令牌均实测 409。未核实配置在新 PID 只 GET 原 receipt，不重发 POST。
- 新 delta 仅改 `DashboardWorkspace.jsx`、`DashboardPanels.jsx`、`SystemMaintenanceAPI.js`、`SystemMaintenanceRecords.jsx` 及 F 测试；没有修改 SystemLive、系统后端、恢复协议、共享导航或 build-order。原树定向回归 `F13-delta-regression1-results.xml` 23 PASS / 29.35s（含组件补充测试，非独立完整入口）；新增 Python 文件 Ruff 与 Pyright 0 errors / 0 warnings。
- 最新可只读复制的完整源为 `/private/tmp/aps-final-operations-F.TQejHX/F13-source18`，源清单 `F13-source18-manifest.json`；聚合 SHA-256 `e5d57c7785aed192c1cb15cc11277150621fb9eb5ff6159078aeb171cca6fee7`。完整构建 `/private/tmp/aps-final-operations-F.TQejHX/F13-copy-build16`，build_id `5b4327b9c68a2f7e69c0df01f34df2c2087fd0c9968418e93a7d11150866c480`，asset-manifest SHA-256 `ac0e08e56a509627ddd6f220ee29e81895de6aa5ea90004a822fc2f9f521a325`。详见 `b-shared-source.json`；66 个 F 范围产品/测试/保留依赖文件与当前原树逐 SHA 相同。
- B 可复制上述源到自己的私有根；F 不执行 B 的 252 矩阵。Source9 与 `/private/tmp/aps-r2-system-frozen-CIRVeT` 归档完全未动，不再用 source9 冒充本次修复。Dashboard 构建块早已交还 Main，交回时整文件 SHA 为 `91f107475d30bca828500ed7e79c4450b50bcc6311a8423a5260d38e9332ea34`，此后 F 未再修改 build-order。
- Main 已独立签 28 张旧图及 26 张 delta 的可见布局，记录在 `../round2-main-v-F-matrix4.json`、`../round2-main-v-F-delta.json`；不是全 228 动作 V。`runtime-evidence.json` 保留原 209 张图和 55 delta 次序不动，本轮追加 20 张独立图另记 `visual-supplement-evidence.json`。待看代表和动作映射以本页顶部为准，没有代签 Main V。
- 根因、失败样本、精确文件行号与复现命令见 `navigation-recovery-fix.md`；机器可读证据见 `navigation-recovery-evidence.json`。所有既往失败保留，不改称通过。整套证据来自多个明确绑定的完整源码副本及注明的原树局部验证，不是单一最终 HEAD、clean-worktree proof、容量证明或 Win7 实机证明。
- F 自启构建、pytest、补图 runner、宿主与浏览器均已结束；产品和仓库测试不再改动，本轮仅按后续授权新增独立 harness/截图。仓库仍有多方未提交内容，F 未提交 Git、未改旧预览/生产库。Main 继续统一源码门禁、B252 和剩余 V；这不是把 F 的控件操作交给 Main 手跑。

## 上一进展快照（保留，不作为当前状态）

- 以下“历史阶段记录”全部保留，但其待 Main 接线、13 项待定和停止执行等描述已经过期。F 继续负责 33 族 / 228 动作，不交由 Main 手跑。
- Main 已批准的 13 项最小补全已全部接入产品。值班台使用真实同范围日峰值、待排池、任务与检修轴、同 run 实际候选和受理时基线；系统集合明确区分文件/恢复事件/清理事件。
- 四组正常主入口已在固定完整源码副本上通过：`F13-copy-matrix2-results.xml` 的正常 4 项通过；同命令另有一项用于定位的恢复跨重启字节断言失败，不能把整命令称为全通过。包含真实三候选切换、八项配置重启读回、同 request URL 对应原 receipt_ref、三条处置历史与三条外协事实、真实下载及正常退出备份。
- 恢复字节差异已定位并留三个数据库样本：重启仅新增一条 `plugins/load` 审计和其自增序号，其他全部表及旧日志均未变；事件读取前后 bytes 完全相同。新测试严格核对这唯一启动增量，不修改产品启动逻辑。正在完整重跑四正常、八恢复、一个维护只读用例。
- 最新完整联验源：`/tmp/aps-final-operations-F.TQejHX/F13-source8`，3610 以上完整源/测试/配置/本地 vendor 文件。精确清单 `F13-source8-manifest.json` 的 3628 项，聚合 SHA-256 `0f4218160842bbd4f4643ccebbebea188ab3627b9b2259a5e047cc8b5308137a`；完整构建 `F13-copy-build6`，build_id `1fd18034068406933d7197adfae2a1c75273d8008c575779def5c7c4da3a0c14`。这是当前 dirty 工作内容的固定副本，不是最终 HEAD。
- 原树后续 delta 不使该固定副本结果失效；所有 repo-owned 实际 loaded-module 路径必须位于该副本并匹配 SHA/bytes/mode。原 venv 仅供 Python 3.8 解释器与第三方依赖；业务库、备份、journal、下载全部使用各例私有根。
- H 的三个复杂度阻塞已拆到真实职责，原函数为 12/6/6，新叶不超过 15；18 个定向文件 Pyright 0 errors，后续新增五文件也为 0 errors，Ruff 通过。37 项叶回归通过；后续新增 journal 未配置回归与旧 widgets 合计 10 项通过。未升级依赖、未提高门禁。
- 旧回归命中的产品问题已经修复：未配置 journal 时备份文件仍可读，恢复事件来源缺口明确列出，写操作禁用；坏 journal 继续报错。旧指标测试由固定下标改为按指标名定位，未改业务断言。
- Dashboard 构建连续块已登记七个新叶并于本次进展交还 Main，F 不再写 `build-order.json`。交回时整文件 SHA-256 `91f107475d30bca828500ed7e79c4450b50bcc6311a8423a5260d38e9332ea34`，实际块为第 53 至 56 行。
- **待 Main 决定的额外两动作**：`WBP-DASH-014.navigation-confirm` / `unlocatable`。实际 `DashboardPanels.jsx` 仅禁用不可定位链接，`DashboardWorkspace.jsx` 对 enabled=false 直接返回；没有原型 `dashboard-workbench.js:46` 所要求的“说明无法定位后明确确认打开概览”分支。已请求仅在这两个已属 F 的现有文件补齐；不得认作已批准的 13 项之一，不标 N/A，不自动扩大产品写集。其余验证照常继续。
- 操作偏差：22:21 首次定位误用了 `CHECKUP_CALLGRAPH_DIR`，刷新共享调用图产物；已确认时间戳并告知 Main。其后使用正确的 `CHECKUP_CALLGRAPH=/tmp/aps-final-operations-F.TQejHX/callgraph`。没有回滚原本已有并发修改的产物，没有 Git 写操作。
- `action-evidence.json` / `control-mappings.json` 尚待最新完整运行结束后统一更新；不能把其中历史待实施状态当作当前产品事实。Main V、全仓门禁和最终 clean-worktree proof 不由 F 宣称。

## 历史阶段记录

## 结论

- 33 个能力族、228 个动作全部保留，见 `action-evidence.json`。备份只读下载已实施并有真实 SQLite 验证；caption/只读 page-context 已按 Main 最新合同接入。
- **不是任务最终完成**：当前全构建受其他域加载顺序阻断，System 主入口还缺 `initialContext` prop。最终四组正常主入口、八组恢复页面、Main V 和所有动作 BKVP 尚未完成。
- 13 个原型控件映射待 Main 核对等价实现/处置记录；没有直接认定为产品 bug，也没有删掉分母。未逐项审核前不乱标 `not_applicable`。

## 修改范围

- `web/routes/workbench/system_backup_export.py:43`、`system_routes.py:19`：opaque backup_ref + 原读取 snapshot 的下载；禁止直接用客户端路径/文件名读文件；前后签名、大小、SQLite 头验证，错误明确返回 JSON。
- `frontend/workbench/app/SystemMaintenanceAPI.js`、`SystemMaintenanceRecords.jsx`：实际下载及响应校验；只读筛选/页码/选中引用恢复，不存 DTO、写 token、确认态或配置草稿。
- `frontend/workbench/app/DashboardWorkspace.jsx`：顶层无条件 `WorkbenchCaption.useCaption` / `WorkbenchPageContext.useSnapshot`，只使用真实当前正式计划与只读页面上下文。
- `frontend/workbench/app/SystemLive.jsx`、`SystemMaintenanceWorkspace.jsx`：校验并接收 `initialContext`，从记录子视图回传只读状态；恢复 pending 完全沿原维护协议。
- 新增 `tests/workbench/*final_operations*` 及本目录；四个旧域 CJS 仅加 caption/page-context 加载。完整 27 文件 hash 见 `source-hashes.json`。
- 没有修改 shared factory/restore/transaction、schema/DTO、共享 build-order、旧 HTML 下载、生产库、旧预览或任何源码归档。F 没有 Git 写操作，也没有编辑原 staged 文件。收尾 `git diff --cached --name-status` 输出为空，与开工时唯一 staged 的状态不同，需由 Main 核对其 Git 活动，不能声称当前索引仍原样。

## 本轮结果

| 证据 | 结果 | 边界 |
| --- | --- | --- |
| `host2-results.xml` | 2 passed / 3.42s | 真实主入口、worker 四候选、私有停止；旧于 caption/page-context |
| `download1-results.xml` | 16 passed / 6.93s | 下载正常/负测；已被后面的重跑覆盖，不重复累加 |
| `download-config2-results.xml` | 22 passed / 42.86s | 当前下载、配置回执/草稿及控件补充；真实 SQLite 原 bytes/中文名/大小/行验证 |
| `operations-regression1.xml` | 68 passed / 66.25s | 本轮新跑既有强故障：真实 worker/HTTP/连接 drain、ACK 丢失、保护、回滚、冷恢复 |
| `restore-widgets2-results.xml` | 7 passed / 8 failed | 7 项旧域组件补充通过；8 项新恢复页面因 v6 未产出 manifest 在 host 启动前失败，未运行恢复 |
| `browser5-results.xml` | 1 passed / 1 failed | 恢复 1392 浅色整例通过；正常链测试失败。旧于 page-context，不当最终通过 |
| 全部 11 个新 Python 产品/测试文件 pyright | 0 errors / 0 warnings | 修正 test host 的 Jinja loader 类型后重跑；未升级依赖 |
| 同 11 文件 Ruff | All checks passed | 首次 9 个新测试格式问题已修，不改断言 |
| `git diff --check` | exit 0 | 工作区仍 dirty，不是 clean proof |

所有运行证据均在 `/tmp/aps-final-operations-F.TQejHX`。正常 browser3..6 的失败、请求、截图、DB 都保留；最长正常链实到 141 条操作记录后因测试定位器停止，不把这些记录升级为完整用例通过。

## 实际命令

所有命令在仓库根运行，统一带 `PYTHONDONTWRITEBYTECODE=1` 和 `PYTHONPYCACHEPREFIX=/tmp/aps-final-operations-F.TQejHX/pycache`，pytest 带 `-p no:cacheprovider` 和专属 `--basetemp` / `--junitxml`。

```text
.venv/bin/python -m pytest tests/workbench/test_final_operations_download.py tests/workbench/test_final_operations_download_contract.py tests/workbench/test_system_config_saved.py tests/workbench/test_system_maintenance_widgets.py -q -p no:cacheprovider --basetemp=/tmp/aps-final-operations-F.TQejHX/download-config2-pytest --junitxml=/tmp/aps-final-operations-F.TQejHX/download-config2-results.xml
.venv/bin/python -m pytest tests/workbench/test_system_maintenance_api.py tests/workbench/test_system_maintenance_failures.py tests/workbench/test_system_restore_host_drain.py tests/workbench/test_system_restore_host_recovery.py tests/workbench/test_system_restore_entrypoint_recovery.py tests/workbench/test_system_restore_entrypoint_fail_closed.py -q -p no:cacheprovider --basetemp=/tmp/aps-final-operations-F.TQejHX/operations-regression1-pytest --junitxml=/tmp/aps-final-operations-F.TQejHX/operations-regression1.xml
.venv/bin/python scripts/workbench/build.py --output-dir /tmp/aps-final-operations-F.TQejHX/build-v6 --node /Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
```

`whereis/callers/callees resolve_context/system_log_export` 已先跑在 `CHECKUP_CALLGRAPH=/tmp/aps-final-operations-F.TQejHX/callgraph`。JS workspace 的 locator 不支持，已保留未找到输出并用实际定义/主入口/域 probe 引用定位，没有写共享调用图。

## Main 下一步

1. `main.jsx` 的 `SystemLive` 调用传 `initialContext={initialContext}`，再解决当前 `ResourceWorkspace.js → ProcessWorkspace.js` 依赖顺序；主线不要覆盖本域文件。
2. 统一 freeze 后先成功 fullbuild，再启动新测试，避免像本轮 v6 构建失败后误启动的 8 个前置失败。测试默认读取当前 `static/workbench`；私有包通过 `FINAL_OPERATIONS_BUILD=/绝对路径/完整构建目录` 明确指定，不自动找旧包或跳过源 hash。
3. 跑 `test_final_operations_browser.py` 四组、`test_final_operations_restore.py` 八组和 `test_final_operations_host.py` 两组；它们都用完整 `/workbench`，没有独立组件伪装主入口或脚本 overlay。
4. 核对 System F5 / 后退的日志筛选页码和选中引用、Dashboard 历史页与条目、caption 显示/清除；再由 Main 审视截图，回写 228 动作矩阵。原型缺控件映射须有明确等价证据或批准处置。
5. Main 登记新 test/support 范围并统一门禁、源码归档及旧 UI 退役。F 不发布、打包或声明 Win7 真机通过。

截至本记录时 F 自启测试/构建/host/browser 均已结束，无后台遗留。Main 随后明确 F 继续负责四组正常、八组恢复及完整 228 动作：F 不停止或移交责任，等 Main 构建通畅通知立即继续。13 项详细原控件/当前证据/缺口见 `control-mappings.json` 的 `.mappings[]`；它们不是 13 个已确诊产品 bug。Main 已补 `SystemLive initialContext`，对应前置已解除；其他域依赖环正在由其责任人拆分。
