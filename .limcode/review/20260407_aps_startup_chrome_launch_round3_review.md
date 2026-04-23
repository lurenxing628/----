# 20260407 APS启动链路与Chrome残余问题三轮审查
- 日期: 2026-04-07
- 概述: 针对启动器浏览器判活、安装器跨账户关闭语义、Python停机链路与相关守卫的深度审查。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 20260407 APS启动链路与Chrome残余问题三轮审查

- 日期：2026-04-07
- 范围：`assets/启动_排产系统_Chrome.bat`、`installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_stop_cli.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_contract_launcher.py`、相关文档与引用链。
- 目标：核对本轮实现是否真正达成 plan 目标，是否存在假成功、过度兜底、静默回退、语义漂移或新的边界缺陷。

## 初始结论

审查进行中，先从启动器、安装器、Python 停机链路和静态守卫四个单元逐步核对，并在每个模块完成后及时记录里程碑。

## 评审摘要

- 当前状态: 已完成
- 已审模块: assets/启动_排产系统_Chrome.bat, tests/test_win7_launcher_runtime_paths.py, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, web/bootstrap/entrypoint.py, installer/aps_win7.iss, installer/aps_win7_legacy.iss, tests/regression_runtime_stop_cli.py, tests/regression_shared_runtime_state.py, tests/regression_runtime_contract_launcher.py, installer/README_WIN7_INSTALLER.md, DELIVERY_WIN7.md, .limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 0 / 中 2 / 低 1
- 最新结论: 本轮实现**部分达成 plan 目标，但暂不建议按“已完全收口”定论**。 可以确认完成的部分： 1. 启动批处理已从“任意 `chrome.exe` 存活即成功”收口为“只认带 APS 专用 `--user-data-dir` 的命令行”，并补上了 profile 可写性探针；原始假成功主问题已明显收敛。 2. 独立浏览器运行时安装器已从“只看当前卸载账户 profile 绝对路径”收口到“`--user-data-dir` + APS 标准 profile marker”，跨账户识别方向正确，且 silent uninstall 仍保持失败闭合。 3. 文档口径已跟上新的启动与卸载语义。 但仍存在两个不能忽视的跟进点： - `installer/aps_win7_chrome.iss` 与 `web/bootstrap/launcher.py` 都采用“快照枚举 PID → 逐个强杀 → 任一失败即整体失败”的实现。对于多进程 Chrome 树，这会把“前一次关闭已连带清干净，后续 PID 自然消失”的正常结果误报成失败，导致卸载或 `--runtime-stop --stop-aps-chrome` 偶发性失败。 - 验证闭环仍未完成：`tests/regression_runtime_stop_cli.py` 没有真实覆盖 `--stop-aps-chrome` 分支，plan 的 `#p3` 也仍处于未完成状态，仓库内缺少普通 Chrome 共存与双账户卸载的现场留痕证据。 因此，本轮代码可判定为“方向正确、主问题大体解决”，但还不能判定为“实现已经完全优雅、严谨且证据完备”。建议先收口 PID 关闭误失败问题，并补齐行为级回归与现场验收证据，再结束本项。
- 下一步建议: 优先修正 Chrome 关闭链路的快照式逐 PID 误失败问题；随后补一条真实覆盖 `--runtime-stop --stop-aps-chrome` 的自动回归，并把普通 Chrome 共存 / 双账户卸载的现场验收结果以审计留痕方式落仓。
- 总体结论: 需要后续跟进

## 评审发现

### profile 参数边界未收紧

- ID: launcher-profile-substring-match
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  `assets/启动_排产系统_Chrome.bat` 的 `:probe_aps_chrome_alive` 只检查命令行是否包含 `--user-data-dir` 与当前 `CHROME_PROFILE_DIR` 子串，没有继续校验参数边界或引号闭合。因此 `...\APS\Chrome109ProfileBackup`、`...\APS\Chrome109Profile2` 这类与标准路径前缀重叠的 profile 仍可能被误判为当前 APS profile。它已经能挡住“系统里任意普通 Chrome”这类原始 BUG，但还没有把‘只认当前 profile’做到完全精确。
- 建议:

  后续若要彻底收口，可把匹配从简单 `Contains($marker)` 提升为对 `--user-data-dir=` 参数值做精确提取，或至少补上路径结尾/引号边界判断。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:613-624#probe_aps_chrome_alive`
  - `assets/启动_排产系统_Chrome.bat`
  - `tests/test_win7_launcher_runtime_paths.py`

### 快照式逐 PID 强杀会把已清干净场景误报失败

- ID: chrome-cleanup-snapshot-kill-race
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `installer/aps_win7_chrome.iss` 和 `web/bootstrap/launcher.py` 都采用“先快照枚举所有命中的 Chrome PID，再逐个强杀”的策略，但把任意一次 `Stop-Process` / `taskkill` 失败都直接视为整体失败。对于同一 profile 下常见的多进程 Chrome 树，较早一次强杀可能已经带走其余同族进程，导致后续 PID 在真正执行时已不存在。当前实现没有把‘目标已自然退出’与‘关闭失败’区分开来，也没有以最终剩余匹配进程为准，因此会把实际上已经关闭成功的场景误判为失败闭合。
- 建议:

  把关闭动作改成“尽力停止 + 最终按剩余匹配进程复查”更稳妥：允许单个 PID 在执行前已退出，不要立刻整体失败；真正的失败条件应是复查后仍存在匹配当前 profile 的目标进程。Python 侧也应避免对每个 PID 都使用 `/T` 后再把‘已被前一次调用带走’当成失败。
- 证据:
  - `installer/aps_win7_chrome.iss:90-97#BuildStopChromePowerShellParams kill loop`
  - `web/bootstrap/launcher.py:856-906#_list_aps_chrome_pids 与 stop_aps_chrome_processes`
  - `web/bootstrap/launcher.py:817-828#_kill_runtime_pid`
  - `installer/aps_win7.iss:612-614#TryStopApsRuntimeAtDir stop-aps-chrome flag`
  - `installer/aps_win7_legacy.iss:609-611#TryStopApsRuntimeAtDir stop-aps-chrome flag`
  - `installer/aps_win7_chrome.iss`
  - `web/bootstrap/launcher.py`
  - `web/bootstrap/entrypoint.py`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`

### 关键关闭分支与现场验收证据仍未闭环

- ID: verification-evidence-gap
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  当前仓库虽然新增了大量字符串守卫和运行时契约回归，但 `tests/regression_runtime_stop_cli.py` 实际并未携带 `--stop-aps-chrome` 参数，因此没有真正执行 Python 浏览器清理分支；`tests/test_win7_launcher_runtime_paths.py` 对批处理与 Inno 脚本的新增保护也主要是静态文本断言。与此同时，实施 plan 仍明确把 `#p3` 标记为未完成，仓库中能看到的是现场验收步骤说明，而不是普通 Chrome 共存与双账户卸载的真实留痕结果。这意味着任务 3 所要求的“行为级约束证据”目前仍不足。
- 建议:

  至少补一条真正覆盖 `--runtime-stop --stop-aps-chrome` 的自动回归，并把“普通 Chrome 共存”“双账户卸载”两组真实机器验收以日志片段、截图或审计记录形式落仓；否则只能说代码方向正确，不能说任务 3 已完整达成。
- 证据:
  - `tests/regression_runtime_stop_cli.py:5-7#regression_runtime_stop_cli 目标说明`
  - `tests/regression_runtime_stop_cli.py:145#首次 runtime-stop 调用`
  - `tests/regression_runtime_stop_cli.py:163#再次 runtime-stop 调用`
  - `tests/test_win7_launcher_runtime_paths.py:169-307#静态守卫集合`
  - `.limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md:8-10#TODO p3 未完成`
  - `installer/README_WIN7_INSTALLER.md:264-268#残余问题收口验收`
  - `DELIVERY_WIN7.md:166-170#交付验收清单`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_runtime_stop_cli.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `installer/README_WIN7_INSTALLER.md`
  - `DELIVERY_WIN7.md`
  - `.limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md`

## 评审里程碑

### M1 · 第一轮：启动批处理判活链路审查

- 状态: 已完成
- 记录时间: 2026-04-07T04:58:51.514Z
- 已审模块: assets/启动_排产系统_Chrome.bat, tests/test_win7_launcher_runtime_paths.py
- 摘要:

  已完成 `assets/启动_排产系统_Chrome.bat` 的逐段审查。结论：主目标已基本达成——`OPEN_CHROME` 在 `start` 后不再只看返回码，而是统一进入 `:probe_aps_chrome_alive`；该子程序在无 PowerShell 时明确记录 `chrome_alive_probe=no_powershell` 并失败闭合，在有 PowerShell 时只枚举 `chrome.exe` 且要求命令行同时包含 `--user-data-dir` 与当前 `CHROME_PROFILE_DIR` 标记，旧的按任意 `chrome.exe` 判活路径已删除。` :probe_chrome_profile_dir ` 也补上了目录创建与写探针文件校验，避免 profile 不可写时继续误判成功。实现整体简洁，没有静默回退。

  同时识别到一个残余边界：当前判活仍是“子串包含”而非“参数边界精确匹配”。若现场存在 `--user-data-dir` 指向 `...\APS\Chrome109ProfileBackup`、`...\APS\Chrome109Profile2` 之类前缀重叠路径的 `chrome.exe`，`probe_aps_chrome_alive` 仍可能将其当成当前 profile 进程。该问题不影响本轮要解决的“普通 Chrome 共存误判”主问题，但严格说还未把“只认当前 profile”收紧到参数级精确匹配。
- 结论:

  启动批处理的主问题已修复，旧宽匹配已被移除；保留 1 条低风险边界问题继续跟踪。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:242-268#OPEN_CHROME`
  - `assets/启动_排产系统_Chrome.bat:589-605#probe_chrome_profile_dir`
  - `assets/启动_排产系统_Chrome.bat:607-626#probe_aps_chrome_alive`
  - `tests/test_win7_launcher_runtime_paths.py:169-199#启动批处理静态守卫`
  - `assets/启动_排产系统_Chrome.bat`
  - `tests/test_win7_launcher_runtime_paths.py`
- 下一步建议:

  继续审查 `installer/aps_win7_chrome.iss` 与 `web/bootstrap/launcher.py`，确认安装器与 Python 停机链路是否与批处理保持同一语义且没有新的回退口。
- 问题:
  - [低] 其他: profile 参数边界未收紧

### M2 · 第二轮：安装器与 Python 停机链路引用链审查

- 状态: 已完成
- 记录时间: 2026-04-07T05:00:01.143Z
- 已审模块: installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, web/bootstrap/entrypoint.py, installer/aps_win7.iss, installer/aps_win7_legacy.iss
- 摘要:

  已完成 `installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`web/bootstrap/entrypoint.py` 以及主安装器 / legacy 安装器调用链的交叉核对。正向结论有三点：

  1. `installer/aps_win7_chrome.iss` 已把 stop helper 收口到单一 PowerShell 语义：只枚举 `chrome.exe`，只接受命令行非空、带 `--user-data-dir`，并命中 `ApsChromeProfileSuffixMarker()` 或当前账户精确路径 marker 的进程；无 `Get-CimInstance` 时仅回退到 `Get-WmiObject`，没有再回到镜像名宽匹配。
  2. `web/bootstrap/entrypoint.py:configure_runtime_contract()` 继续把 `default_chrome_profile_dir(runtime_dir)` 写入 `aps_runtime.json`，`stop_runtime_from_dir()` 在有契约与无契约两条路径都会把 `chrome_profile_dir` 传入 `_stop_aps_chrome_if_requested()`，三端对“APS 专用 `--user-data-dir`”的口径总体保持一致。
  3. 主安装器与 legacy 安装器都仍通过 `--runtime-stop ... --stop-aps-chrome` 进入 Python 停机链路，说明这条引用链没有断。

  但审查中发现一个更实质的逻辑缺口：无论 Inno stop helper 还是 Python `stop_aps_chrome_processes()`，都先基于一次性快照枚举出所有命中的 `chrome.exe` 进程，再对快照中的每个 PID 逐个强杀，并把任意一次“PID 已不存在”也当成整体失败。Chrome 同一 profile 下通常会有多个同族进程；当较早的一次 `Stop-Process` 或 `taskkill /T` 已带走其余同族进程后，后续 PID 很可能已经自然消失，当前实现却会直接报失败。这不会造成假成功，但会把“实际上已经关干净”的场景误报成失败闭合，表现为卸载或 `--runtime-stop --stop-aps-chrome` 偶发性失败。
- 结论:

  安装器的跨账户匹配目标已达成，但停止同族 Chrome 进程的实现仍存在快照式逐 PID 强杀导致的误失败风险。
- 证据:
  - `installer/aps_win7_chrome.iss:61-99#ApsChromeProfileSuffixMarker 与 BuildStopChromePowerShellParams`
  - `web/bootstrap/entrypoint.py:123-156#configure_runtime_contract 与 app_main runtime-stop 入口`
  - `web/bootstrap/launcher.py:832-906#_list_aps_chrome_pids 与 stop_aps_chrome_processes`
  - `installer/aps_win7.iss:592-621#TryStopApsRuntimeAtDir`
  - `installer/aps_win7_legacy.iss:597-618#TryStopApsRuntimeAtDir`
  - `installer/aps_win7_chrome.iss`
  - `web/bootstrap/launcher.py`
  - `web/bootstrap/entrypoint.py`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
- 下一步建议:

  继续审查测试与文档，确认自动回归是否真的覆盖 `--stop-aps-chrome` 分支，以及现场验收证据是否已经在仓库中留痕。
- 问题:
  - [中] 其他: 快照式逐 PID 强杀会把已清干净场景误报失败

### M3 · 第三轮：测试覆盖与验收证据审查

- 状态: 已完成
- 记录时间: 2026-04-07T05:00:33.873Z
- 已审模块: tests/test_win7_launcher_runtime_paths.py, tests/regression_runtime_stop_cli.py, tests/regression_shared_runtime_state.py, tests/regression_runtime_contract_launcher.py, installer/README_WIN7_INSTALLER.md, DELIVERY_WIN7.md, .limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md
- 摘要:

  已完成 `tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_stop_cli.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_contract_launcher.py`、`installer/README_WIN7_INSTALLER.md`、`DELIVERY_WIN7.md` 及对应 plan 的核对。结论分成两部分：

  - 正向部分：静态守卫已把本轮关键字符串口径锁进仓库，包括批处理不再使用按任意 `chrome.exe` 判活、安装器改为 `--user-data-dir` + APS profile marker、文档已补入“普通 Chrome 共存场景 / 双账户卸载场景 / 关注 `chrome_alive_probe` 与 `chrome_cmd`”等口径；`regression_shared_runtime_state.py` 与 `regression_runtime_contract_launcher.py` 也确实在保护运行时契约、共享日志目录和 `chrome_profile_dir` 字段。
  - 缺口部分：任务 3 想要的是“不是只停留在字符串守卫”，但当前自动验证仍主要停留在静态断言与不带 `--stop-aps-chrome` 的运行时停机回归。`tests/regression_runtime_stop_cli.py` 的说明写着要保证 `--runtime-stop` 主链路，但实际两次调用都没有追加 `--stop-aps-chrome`，因此并没有真实覆盖 Python 浏览器清理分支；与此同时，plan 自身仍把 `#p3` 标成未完成，仓库里也只看得到现场验收步骤说明，看不到普通 Chrome 共存与双账户卸载的现场留痕结果。

  因此，文档口径已同步，但“验证证据闭环”仍未真正达成。
- 结论:

  文档同步基本到位，但自动回归与现场证据仍不足以完全证明任务 3 已完成。
- 证据:
  - `tests/test_win7_launcher_runtime_paths.py:169-307#启动器与安装器静态守卫`
  - `tests/regression_runtime_stop_cli.py:1-8#regression_runtime_stop_cli 说明`
  - `tests/regression_runtime_stop_cli.py:144-170#regression_runtime_stop_cli 调用参数`
  - `tests/regression_shared_runtime_state.py:50-124#共享运行时状态回归`
  - `tests/regression_runtime_contract_launcher.py:51-109#运行时契约回归`
  - `installer/README_WIN7_INSTALLER.md:264-273#残余问题收口验收说明`
  - `DELIVERY_WIN7.md:166-173#交付文档残余问题收口验收说明`
  - `.limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md:7-11#plan TODO p3 状态`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_runtime_stop_cli.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `installer/README_WIN7_INSTALLER.md`
  - `DELIVERY_WIN7.md`
  - `.limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md`
- 下一步建议:

  汇总结论并给出最终判断：代码层面的主目标大体达成，但在停止同族 Chrome 进程的误失败风险和验证闭环上仍需继续收口。
- 问题:
  - [中] 测试: 关键关闭分支与现场验收证据仍未闭环

## 最终结论

本轮实现**部分达成 plan 目标，但暂不建议按“已完全收口”定论**。

可以确认完成的部分：
1. 启动批处理已从“任意 `chrome.exe` 存活即成功”收口为“只认带 APS 专用 `--user-data-dir` 的命令行”，并补上了 profile 可写性探针；原始假成功主问题已明显收敛。
2. 独立浏览器运行时安装器已从“只看当前卸载账户 profile 绝对路径”收口到“`--user-data-dir` + APS 标准 profile marker”，跨账户识别方向正确，且 silent uninstall 仍保持失败闭合。
3. 文档口径已跟上新的启动与卸载语义。

但仍存在两个不能忽视的跟进点：
- `installer/aps_win7_chrome.iss` 与 `web/bootstrap/launcher.py` 都采用“快照枚举 PID → 逐个强杀 → 任一失败即整体失败”的实现。对于多进程 Chrome 树，这会把“前一次关闭已连带清干净，后续 PID 自然消失”的正常结果误报成失败，导致卸载或 `--runtime-stop --stop-aps-chrome` 偶发性失败。
- 验证闭环仍未完成：`tests/regression_runtime_stop_cli.py` 没有真实覆盖 `--stop-aps-chrome` 分支，plan 的 `#p3` 也仍处于未完成状态，仓库内缺少普通 Chrome 共存与双账户卸载的现场留痕证据。

因此，本轮代码可判定为“方向正确、主问题大体解决”，但还不能判定为“实现已经完全优雅、严谨且证据完备”。建议先收口 PID 关闭误失败问题，并补齐行为级回归与现场验收证据，再结束本项。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mno5amvn-5qz5b3",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T05:00:48.639Z",
  "finalizedAt": "2026-04-07T05:00:48.639Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "20260407 APS启动链路与Chrome残余问题三轮审查",
    "date": "2026-04-07",
    "overview": "针对启动器浏览器判活、安装器跨账户关闭语义、Python停机链路与相关守卫的深度审查。"
  },
  "scope": {
    "markdown": "# 20260407 APS启动链路与Chrome残余问题三轮审查\n\n- 日期：2026-04-07\n- 范围：`assets/启动_排产系统_Chrome.bat`、`installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_stop_cli.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_contract_launcher.py`、相关文档与引用链。\n- 目标：核对本轮实现是否真正达成 plan 目标，是否存在假成功、过度兜底、静默回退、语义漂移或新的边界缺陷。\n\n## 初始结论\n\n审查进行中，先从启动器、安装器、Python 停机链路和静态守卫四个单元逐步核对，并在每个模块完成后及时记录里程碑。"
  },
  "summary": {
    "latestConclusion": "本轮实现**部分达成 plan 目标，但暂不建议按“已完全收口”定论**。\n\n可以确认完成的部分：\n1. 启动批处理已从“任意 `chrome.exe` 存活即成功”收口为“只认带 APS 专用 `--user-data-dir` 的命令行”，并补上了 profile 可写性探针；原始假成功主问题已明显收敛。\n2. 独立浏览器运行时安装器已从“只看当前卸载账户 profile 绝对路径”收口到“`--user-data-dir` + APS 标准 profile marker”，跨账户识别方向正确，且 silent uninstall 仍保持失败闭合。\n3. 文档口径已跟上新的启动与卸载语义。\n\n但仍存在两个不能忽视的跟进点：\n- `installer/aps_win7_chrome.iss` 与 `web/bootstrap/launcher.py` 都采用“快照枚举 PID → 逐个强杀 → 任一失败即整体失败”的实现。对于多进程 Chrome 树，这会把“前一次关闭已连带清干净，后续 PID 自然消失”的正常结果误报成失败，导致卸载或 `--runtime-stop --stop-aps-chrome` 偶发性失败。\n- 验证闭环仍未完成：`tests/regression_runtime_stop_cli.py` 没有真实覆盖 `--stop-aps-chrome` 分支，plan 的 `#p3` 也仍处于未完成状态，仓库内缺少普通 Chrome 共存与双账户卸载的现场留痕证据。\n\n因此，本轮代码可判定为“方向正确、主问题大体解决”，但还不能判定为“实现已经完全优雅、严谨且证据完备”。建议先收口 PID 关闭误失败问题，并补齐行为级回归与现场验收证据，再结束本项。",
    "recommendedNextAction": "优先修正 Chrome 关闭链路的快照式逐 PID 误失败问题；随后补一条真实覆盖 `--runtime-stop --stop-aps-chrome` 的自动回归，并把普通 Chrome 共存 / 双账户卸载的现场验收结果以审计留痕方式落仓。",
    "reviewedModules": [
      "assets/启动_排产系统_Chrome.bat",
      "tests/test_win7_launcher_runtime_paths.py",
      "installer/aps_win7_chrome.iss",
      "web/bootstrap/launcher.py",
      "web/bootstrap/entrypoint.py",
      "installer/aps_win7.iss",
      "installer/aps_win7_legacy.iss",
      "tests/regression_runtime_stop_cli.py",
      "tests/regression_shared_runtime_state.py",
      "tests/regression_runtime_contract_launcher.py",
      "installer/README_WIN7_INSTALLER.md",
      "DELIVERY_WIN7.md",
      ".limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 0,
      "medium": 2,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：启动批处理判活链路审查",
      "status": "completed",
      "recordedAt": "2026-04-07T04:58:51.514Z",
      "summaryMarkdown": "已完成 `assets/启动_排产系统_Chrome.bat` 的逐段审查。结论：主目标已基本达成——`OPEN_CHROME` 在 `start` 后不再只看返回码，而是统一进入 `:probe_aps_chrome_alive`；该子程序在无 PowerShell 时明确记录 `chrome_alive_probe=no_powershell` 并失败闭合，在有 PowerShell 时只枚举 `chrome.exe` 且要求命令行同时包含 `--user-data-dir` 与当前 `CHROME_PROFILE_DIR` 标记，旧的按任意 `chrome.exe` 判活路径已删除。` :probe_chrome_profile_dir ` 也补上了目录创建与写探针文件校验，避免 profile 不可写时继续误判成功。实现整体简洁，没有静默回退。\n\n同时识别到一个残余边界：当前判活仍是“子串包含”而非“参数边界精确匹配”。若现场存在 `--user-data-dir` 指向 `...\\APS\\Chrome109ProfileBackup`、`...\\APS\\Chrome109Profile2` 之类前缀重叠路径的 `chrome.exe`，`probe_aps_chrome_alive` 仍可能将其当成当前 profile 进程。该问题不影响本轮要解决的“普通 Chrome 共存误判”主问题，但严格说还未把“只认当前 profile”收紧到参数级精确匹配。",
      "conclusionMarkdown": "启动批处理的主问题已修复，旧宽匹配已被移除；保留 1 条低风险边界问题继续跟踪。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 242,
          "lineEnd": 268,
          "symbol": "OPEN_CHROME",
          "excerptHash": "sha256:m1-open-chrome-probe-switch"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 589,
          "lineEnd": 605,
          "symbol": "probe_chrome_profile_dir",
          "excerptHash": "sha256:m1-profile-writability-probe"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 607,
          "lineEnd": 626,
          "symbol": "probe_aps_chrome_alive",
          "excerptHash": "sha256:m1-profile-substring-probe"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 169,
          "lineEnd": 199,
          "symbol": "启动批处理静态守卫",
          "excerptHash": "sha256:m1-bat-static-guards"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "tests/test_win7_launcher_runtime_paths.py"
      ],
      "recommendedNextAction": "继续审查 `installer/aps_win7_chrome.iss` 与 `web/bootstrap/launcher.py`，确认安装器与 Python 停机链路是否与批处理保持同一语义且没有新的回退口。",
      "findingIds": [
        "launcher-profile-substring-match"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：安装器与 Python 停机链路引用链审查",
      "status": "completed",
      "recordedAt": "2026-04-07T05:00:01.143Z",
      "summaryMarkdown": "已完成 `installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`web/bootstrap/entrypoint.py` 以及主安装器 / legacy 安装器调用链的交叉核对。正向结论有三点：\n\n1. `installer/aps_win7_chrome.iss` 已把 stop helper 收口到单一 PowerShell 语义：只枚举 `chrome.exe`，只接受命令行非空、带 `--user-data-dir`，并命中 `ApsChromeProfileSuffixMarker()` 或当前账户精确路径 marker 的进程；无 `Get-CimInstance` 时仅回退到 `Get-WmiObject`，没有再回到镜像名宽匹配。\n2. `web/bootstrap/entrypoint.py:configure_runtime_contract()` 继续把 `default_chrome_profile_dir(runtime_dir)` 写入 `aps_runtime.json`，`stop_runtime_from_dir()` 在有契约与无契约两条路径都会把 `chrome_profile_dir` 传入 `_stop_aps_chrome_if_requested()`，三端对“APS 专用 `--user-data-dir`”的口径总体保持一致。\n3. 主安装器与 legacy 安装器都仍通过 `--runtime-stop ... --stop-aps-chrome` 进入 Python 停机链路，说明这条引用链没有断。\n\n但审查中发现一个更实质的逻辑缺口：无论 Inno stop helper 还是 Python `stop_aps_chrome_processes()`，都先基于一次性快照枚举出所有命中的 `chrome.exe` 进程，再对快照中的每个 PID 逐个强杀，并把任意一次“PID 已不存在”也当成整体失败。Chrome 同一 profile 下通常会有多个同族进程；当较早的一次 `Stop-Process` 或 `taskkill /T` 已带走其余同族进程后，后续 PID 很可能已经自然消失，当前实现却会直接报失败。这不会造成假成功，但会把“实际上已经关干净”的场景误报成失败闭合，表现为卸载或 `--runtime-stop --stop-aps-chrome` 偶发性失败。",
      "conclusionMarkdown": "安装器的跨账户匹配目标已达成，但停止同族 Chrome 进程的实现仍存在快照式逐 PID 强杀导致的误失败风险。",
      "evidence": [
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 61,
          "lineEnd": 99,
          "symbol": "ApsChromeProfileSuffixMarker 与 BuildStopChromePowerShellParams",
          "excerptHash": "sha256:m2-installer-stop-helper"
        },
        {
          "path": "web/bootstrap/entrypoint.py",
          "lineStart": 123,
          "lineEnd": 156,
          "symbol": "configure_runtime_contract 与 app_main runtime-stop 入口",
          "excerptHash": "sha256:m2-entrypoint-contract-stop"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 906,
          "symbol": "_list_aps_chrome_pids 与 stop_aps_chrome_processes",
          "excerptHash": "sha256:m2-python-stop-helper"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 592,
          "lineEnd": 621,
          "symbol": "TryStopApsRuntimeAtDir",
          "excerptHash": "sha256:m2-main-installer-stop-flag"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 597,
          "lineEnd": 618,
          "symbol": "TryStopApsRuntimeAtDir",
          "excerptHash": "sha256:m2-legacy-installer-stop-flag"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        }
      ],
      "reviewedModules": [
        "installer/aps_win7_chrome.iss",
        "web/bootstrap/launcher.py",
        "web/bootstrap/entrypoint.py",
        "installer/aps_win7.iss",
        "installer/aps_win7_legacy.iss"
      ],
      "recommendedNextAction": "继续审查测试与文档，确认自动回归是否真的覆盖 `--stop-aps-chrome` 分支，以及现场验收证据是否已经在仓库中留痕。",
      "findingIds": [
        "chrome-cleanup-snapshot-kill-race"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：测试覆盖与验收证据审查",
      "status": "completed",
      "recordedAt": "2026-04-07T05:00:33.873Z",
      "summaryMarkdown": "已完成 `tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_stop_cli.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_contract_launcher.py`、`installer/README_WIN7_INSTALLER.md`、`DELIVERY_WIN7.md` 及对应 plan 的核对。结论分成两部分：\n\n- 正向部分：静态守卫已把本轮关键字符串口径锁进仓库，包括批处理不再使用按任意 `chrome.exe` 判活、安装器改为 `--user-data-dir` + APS profile marker、文档已补入“普通 Chrome 共存场景 / 双账户卸载场景 / 关注 `chrome_alive_probe` 与 `chrome_cmd`”等口径；`regression_shared_runtime_state.py` 与 `regression_runtime_contract_launcher.py` 也确实在保护运行时契约、共享日志目录和 `chrome_profile_dir` 字段。\n- 缺口部分：任务 3 想要的是“不是只停留在字符串守卫”，但当前自动验证仍主要停留在静态断言与不带 `--stop-aps-chrome` 的运行时停机回归。`tests/regression_runtime_stop_cli.py` 的说明写着要保证 `--runtime-stop` 主链路，但实际两次调用都没有追加 `--stop-aps-chrome`，因此并没有真实覆盖 Python 浏览器清理分支；与此同时，plan 自身仍把 `#p3` 标成未完成，仓库里也只看得到现场验收步骤说明，看不到普通 Chrome 共存与双账户卸载的现场留痕结果。\n\n因此，文档口径已同步，但“验证证据闭环”仍未真正达成。",
      "conclusionMarkdown": "文档同步基本到位，但自动回归与现场证据仍不足以完全证明任务 3 已完成。",
      "evidence": [
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 169,
          "lineEnd": 307,
          "symbol": "启动器与安装器静态守卫",
          "excerptHash": "sha256:m3-static-guards"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 1,
          "lineEnd": 8,
          "symbol": "regression_runtime_stop_cli 说明",
          "excerptHash": "sha256:m3-stop-cli-docstring"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 144,
          "lineEnd": 170,
          "symbol": "regression_runtime_stop_cli 调用参数",
          "excerptHash": "sha256:m3-stop-cli-args"
        },
        {
          "path": "tests/regression_shared_runtime_state.py",
          "lineStart": 50,
          "lineEnd": 124,
          "symbol": "共享运行时状态回归",
          "excerptHash": "sha256:m3-shared-state-regression"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py",
          "lineStart": 51,
          "lineEnd": 109,
          "symbol": "运行时契约回归",
          "excerptHash": "sha256:m3-contract-regression"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 264,
          "lineEnd": 273,
          "symbol": "残余问题收口验收说明",
          "excerptHash": "sha256:m3-installer-doc-acceptance"
        },
        {
          "path": "DELIVERY_WIN7.md",
          "lineStart": 166,
          "lineEnd": 173,
          "symbol": "交付文档残余问题收口验收说明",
          "excerptHash": "sha256:m3-delivery-doc-acceptance"
        },
        {
          "path": ".limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md",
          "lineStart": 7,
          "lineEnd": 11,
          "symbol": "plan TODO p3 状态",
          "excerptHash": "sha256:m3-plan-p3-open"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        },
        {
          "path": "DELIVERY_WIN7.md"
        },
        {
          "path": ".limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md"
        }
      ],
      "reviewedModules": [
        "tests/test_win7_launcher_runtime_paths.py",
        "tests/regression_runtime_stop_cli.py",
        "tests/regression_shared_runtime_state.py",
        "tests/regression_runtime_contract_launcher.py",
        "installer/README_WIN7_INSTALLER.md",
        "DELIVERY_WIN7.md",
        ".limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md"
      ],
      "recommendedNextAction": "汇总结论并给出最终判断：代码层面的主目标大体达成，但在停止同族 Chrome 进程的误失败风险和验证闭环上仍需继续收口。",
      "findingIds": [
        "verification-evidence-gap"
      ]
    }
  ],
  "findings": [
    {
      "id": "launcher-profile-substring-match",
      "severity": "low",
      "category": "other",
      "title": "profile 参数边界未收紧",
      "descriptionMarkdown": "`assets/启动_排产系统_Chrome.bat` 的 `:probe_aps_chrome_alive` 只检查命令行是否包含 `--user-data-dir` 与当前 `CHROME_PROFILE_DIR` 子串，没有继续校验参数边界或引号闭合。因此 `...\\APS\\Chrome109ProfileBackup`、`...\\APS\\Chrome109Profile2` 这类与标准路径前缀重叠的 profile 仍可能被误判为当前 APS profile。它已经能挡住“系统里任意普通 Chrome”这类原始 BUG，但还没有把‘只认当前 profile’做到完全精确。",
      "recommendationMarkdown": "后续若要彻底收口，可把匹配从简单 `Contains($marker)` 提升为对 `--user-data-dir=` 参数值做精确提取，或至少补上路径结尾/引号边界判断。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 613,
          "lineEnd": 624,
          "symbol": "probe_aps_chrome_alive",
          "excerptHash": "sha256:f1-bat-substring-marker"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "chrome-cleanup-snapshot-kill-race",
      "severity": "medium",
      "category": "other",
      "title": "快照式逐 PID 强杀会把已清干净场景误报失败",
      "descriptionMarkdown": "`installer/aps_win7_chrome.iss` 和 `web/bootstrap/launcher.py` 都采用“先快照枚举所有命中的 Chrome PID，再逐个强杀”的策略，但把任意一次 `Stop-Process` / `taskkill` 失败都直接视为整体失败。对于同一 profile 下常见的多进程 Chrome 树，较早一次强杀可能已经带走其余同族进程，导致后续 PID 在真正执行时已不存在。当前实现没有把‘目标已自然退出’与‘关闭失败’区分开来，也没有以最终剩余匹配进程为准，因此会把实际上已经关闭成功的场景误判为失败闭合。",
      "recommendationMarkdown": "把关闭动作改成“尽力停止 + 最终按剩余匹配进程复查”更稳妥：允许单个 PID 在执行前已退出，不要立刻整体失败；真正的失败条件应是复查后仍存在匹配当前 profile 的目标进程。Python 侧也应避免对每个 PID 都使用 `/T` 后再把‘已被前一次调用带走’当成失败。",
      "evidence": [
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 90,
          "lineEnd": 97,
          "symbol": "BuildStopChromePowerShellParams kill loop",
          "excerptHash": "sha256:f2-installer-kill-loop"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 856,
          "lineEnd": 906,
          "symbol": "_list_aps_chrome_pids 与 stop_aps_chrome_processes",
          "excerptHash": "sha256:f2-python-kill-loop"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 817,
          "lineEnd": 828,
          "symbol": "_kill_runtime_pid",
          "excerptHash": "sha256:f2-taskkill-tree"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 612,
          "lineEnd": 614,
          "symbol": "TryStopApsRuntimeAtDir stop-aps-chrome flag",
          "excerptHash": "sha256:f2-main-installer-flag"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 609,
          "lineEnd": 611,
          "symbol": "TryStopApsRuntimeAtDir stop-aps-chrome flag",
          "excerptHash": "sha256:f2-legacy-installer-flag"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "verification-evidence-gap",
      "severity": "medium",
      "category": "test",
      "title": "关键关闭分支与现场验收证据仍未闭环",
      "descriptionMarkdown": "当前仓库虽然新增了大量字符串守卫和运行时契约回归，但 `tests/regression_runtime_stop_cli.py` 实际并未携带 `--stop-aps-chrome` 参数，因此没有真正执行 Python 浏览器清理分支；`tests/test_win7_launcher_runtime_paths.py` 对批处理与 Inno 脚本的新增保护也主要是静态文本断言。与此同时，实施 plan 仍明确把 `#p3` 标记为未完成，仓库中能看到的是现场验收步骤说明，而不是普通 Chrome 共存与双账户卸载的真实留痕结果。这意味着任务 3 所要求的“行为级约束证据”目前仍不足。",
      "recommendationMarkdown": "至少补一条真正覆盖 `--runtime-stop --stop-aps-chrome` 的自动回归，并把“普通 Chrome 共存”“双账户卸载”两组真实机器验收以日志片段、截图或审计记录形式落仓；否则只能说代码方向正确，不能说任务 3 已完整达成。",
      "evidence": [
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 5,
          "lineEnd": 7,
          "symbol": "regression_runtime_stop_cli 目标说明",
          "excerptHash": "sha256:f3-stop-cli-goal"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 145,
          "lineEnd": 145,
          "symbol": "首次 runtime-stop 调用",
          "excerptHash": "sha256:f3-stop-cli-call1"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 163,
          "lineEnd": 163,
          "symbol": "再次 runtime-stop 调用",
          "excerptHash": "sha256:f3-stop-cli-call2"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 169,
          "lineEnd": 307,
          "symbol": "静态守卫集合",
          "excerptHash": "sha256:f3-static-guard-suite"
        },
        {
          "path": ".limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md",
          "lineStart": 8,
          "lineEnd": 10,
          "symbol": "TODO p3 未完成",
          "excerptHash": "sha256:f3-plan-open-item"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 264,
          "lineEnd": 268,
          "symbol": "残余问题收口验收",
          "excerptHash": "sha256:f3-installer-doc-checklist"
        },
        {
          "path": "DELIVERY_WIN7.md",
          "lineStart": 166,
          "lineEnd": 170,
          "symbol": "交付验收清单",
          "excerptHash": "sha256:f3-delivery-doc-checklist"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        },
        {
          "path": "DELIVERY_WIN7.md"
        },
        {
          "path": ".limcode/plans/20260407_APS启动链路与Chrome残余问题修复plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:b6e621ae200b7d030d663b005d7ca03feb49d8c1948cf4731c1d86c8a5a0ebad",
    "generatedAt": "2026-04-07T05:00:48.639Z",
    "locale": "zh-CN"
  }
}
```
