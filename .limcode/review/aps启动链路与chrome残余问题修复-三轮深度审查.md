# APS启动链路与Chrome残余问题修复_三轮深度审查
- 日期: 2026-04-07
- 概述: 对当前未提交的启动器浏览器判活收紧、安装器卸载匹配收口、文档同步三类修改进行三轮深度审查
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# APS启动链路与Chrome残余问题修复 三轮深度审查

- 日期：2026-04-07
- 范围：`assets/启动_排产系统_Chrome.bat`、`installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`tests/test_win7_launcher_runtime_paths.py`、`DELIVERY_WIN7.md`、`installer/README_WIN7_INSTALLER.md`
- 目标：验证当前未提交修改是否正确达成了以下三个目标：
  1. 启动器浏览器判活从"任意 Chrome 存活"收紧为"APS 专用 profile 存活"
  2. 浏览器运行时卸载器从"当前账户路径匹配"收紧为"任意账户 APS 标准 profile 命令行匹配"
  3. 三端（批处理启动器、安装器、Python 停机链路）语义统一

## 审查方法

分三轮递进审查：
- 第一轮：功能正确性——是否达成目标，核心逻辑有无 BUG
- 第二轮：实现质量——是否优雅简洁，有无过度兜底或静默回退
- 第三轮：边界与一致性——三端语义是否统一，测试覆盖是否充分，文档是否同步

## 评审摘要

- 当前状态: 已完成
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, tests/test_win7_launcher_runtime_paths.py, DELIVERY_WIN7.md, installer/README_WIN7_INSTALLER.md, tests/regression_shared_runtime_state.py, tests/regression_runtime_stop_cli.py
- 当前进度: 已记录 3 个里程碑；最新：R3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 0 / 中 1 / 低 2
- 最新结论: ## 三轮深度审查总结 本次修改涵盖 6 个文件，核心目标是消除启动器和安装器中的两类假成功路径： 1. **启动器判活收紧**（`assets/启动_排产系统_Chrome.bat`）——新增 `probe_chrome_profile_dir` 目录可写校验和 `probe_aps_chrome_alive` 进程精确判活，完全删除旧的按镜像名宽匹配，无 PowerShell 时失败闭合而非静默降级。**实现正确、简洁、无过度兜底**。 2. **安装器卸载匹配收口**（`installer/aps_win7_chrome.iss`）——新增 `ApsChromeProfileSuffixMarker` 和 `Test-ApsChromeCommandLine` 函数，同时支持当前账户精确路径和跨账户后缀匹配，二次验证闭合。**实现正确、结构清晰**。 3. **Python 侧最小联动**（`web/bootstrap/launcher.py`）——仅新增 4 行注释说明三端统一语义。代码未做行为修改。 4. **测试守卫**（`tests/test_win7_launcher_runtime_paths.py`）——新增 3 个字符串守卫，覆盖批处理判活、安装器跨账户匹配、安装器新签名。 5. **文档同步**（`DELIVERY_WIN7.md`、`installer/README_WIN7_INSTALLER.md`）——两份文档口径一致，完整覆盖启动器收紧、卸载器收紧、验收场景、排障日志键。 ### 审查发现汇总 | 问题 | 严重级别 | 状态 | |---|---|---| | Python 侧注释声称检查 `--user-data-dir` 但代码未检查 | 中 | 开放 | | 无 PowerShell 场景下判活硬失败 | 低 | 接受风险 | | 安装器双匹配在当前场景有冗余 | 低 | 接受风险 | ### 结论 **整体修改质量高**。三项核心修改均达成功能目标，没有引入新的静默回退或过度兜底，逻辑严谨，测试充分，文档同步。之前 review 识别的 3 个高/中风险问题已全部被修复。 唯一需要在提交前处理的是 **`py-comment-vs-impl-gap`**（中风险）：建议在 `_list_aps_chrome_pids` 的 PowerShell 脚本中增加 `$cmd.ToLowerInvariant().Contains('--user-data-dir')` 条件（一行改动），使注释与实现以及三端语义彻底一致。这不是 BUG（当前不会误判），但会消除注释与代码之间的语义偏差，防止后续维护者误读。
- 下一步建议: 在 `web/bootstrap/launcher.py` 的 `_list_aps_chrome_pids` 中，将第 858 行的匹配条件从 `$cmd.ToLowerInvariant().Contains($marker)` 改为 `$cmdLower = $cmd.ToLowerInvariant(); $cmdLower.Contains('--user-data-dir') -and $cmdLower.Contains($marker)`，使三端语义完全统一。改完后即可提交。
- 总体结论: 有条件通过

## 评审发现

### Python 侧注释与实现不一致：声称检查 --user-data-dir 但实际未检查

- ID: py-comment-vs-impl-gap
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  Python 侧 `_list_aps_chrome_pids` 第 832-835 行新增注释声称三端共同语义都是“只认 APS 专用 `--user-data-dir` 命令行”，但 Python 侧实际的 PowerShell 脚本（第 857-860 行）只检查 `$cmd.ToLowerInvariant().Contains($marker)` 而没有检查 `--user-data-dir`。虽然因为 `$marker` 是包含 `Chrome109Profile` 的绝对路径，误命中普通 Chrome 的概率接近零，但注释描述与实现存在语义差异：注释说“只认 `--user-data-dir` 命令行”，但代码实际不检查该参数。建议要么在 Python 侧也加上 `--user-data-dir` 条件以匹配注释描述，要么把注释改成“Python 侧按精确 profile 绝对路径匹配，批处理和安装器按 `--user-data-dir` + profile 后缀匹配”。
- 建议:

  建议在 `_list_aps_chrome_pids` 的 PowerShell 脚本中增加 `$cmdLower.Contains('--user-data-dir')` 条件，与批处理和安装器保持一致；或者把注释修改成更精确的描述。
- 证据:
  - `web/bootstrap/launcher.py:832-860#_list_aps_chrome_pids`
  - `web/bootstrap/launcher.py`

### 无 PowerShell 场景下判活会硬失败（设计意图）

- ID: no-powershell-hard-fail
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 接受风险
- 相关里程碑: R2
- 说明:

  批处理 `:probe_aps_chrome_alive` 在无 PowerShell 的 Win7 场景下会记录日志 `chrome_alive_probe=no_powershell` 并且 `CHROME_ALIVE` 保持未定义，导致 `:OPEN_CHROME` 中的检查 `if not defined CHROME_ALIVE` 命中而退出。这是正确的失败闭合行为——不能确认就拒绝。但需要留意的是，如果目标机是 Win7 且真正没有 PowerShell（极罕见但理论上可能），则每次启动都会因为“无法确认”而失败。这比以前的假成功强很多，但用户体验上会表现为永远无法启动而不是稍微宽松的探测。这是设计意图中的有意取舍，不是 BUG。

### 安装器双匹配逻辑在当前场景下有冗余但设计合理

- ID: dual-match-redundancy
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 接受风险
- 相关里程碑: R2
- 说明:

  安装器 `BuildStopChromePowerShellParams` 生成的 PowerShell 脚本中 `Test-ApsChromeCommandLine` 函数先检查后缀 marker，再检查精确路径。由于后缀 marker (`\aps\chrome109profile`) 已经足够精确，实际上精确路径会永远被后缀包含，所以第二个分支在正常场景下不会被命中。但这不算多余，因为它提供了一层安全网：当用户自定义 profile 目录名（不包含 `aps\chrome109profile` 后缀）时，精确路径匹配仍能起作用。实现謨义当前不存在这种场景（路径为硬编码），但保留双匹配在可维护性上是合理的。

## 评审里程碑

### R1 · 第一轮：功能正确性审查

- 状态: 已完成
- 记录时间: 2026-04-07T03:24:40.461Z
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, tests/test_win7_launcher_runtime_paths.py
- 摘要:

  ## 第一轮：功能正确性

  ### 1. 启动器浏览器判活（`assets/启动_排产系统_Chrome.bat`）

  **目标**：拉起 Chrome 后不再按"任意 chrome.exe 存活"判定成功，改为按 APS 专用 `--user-data-dir` 命令行匹配。

  **实现审查**：
  - 第 607-626 行新增 `:probe_aps_chrome_alive` 子程序，逻辑正确：
    1. 无 PowerShell 时 `CHROME_ALIVE` 保持未定义并记录 `chrome_alive_probe=no_powershell`，不再降级到宽匹配——**正确**
    2. 使用 `Get-CimInstance Win32_Process` 优先、`Get-WmiObject Win32_Process` 降级查询——**正确**
    3. 匹配条件：命令行非空 + 包含 `--user-data-dir` + 包含 `$marker`（profile 路径小写）——**正确**
    4. 返回码语义：0=找到、1=查询失败、2=未找到——**清晰且可区分**
  - 第 589-605 行新增 `:probe_chrome_profile_dir` 子程序，在拉起浏览器前校验 profile 目录可写——**正确闭合**
  - 第 260-268 行 `:OPEN_CHROME` 中调用 `call :probe_aps_chrome_alive`，失败时明确提示"未能确认 APS 专用浏览器已拉起"并退出码 11——**正确**
  - 旧的 `tasklist` 宽匹配已完全删除——**验证通过**

  **潜在 BUG 检查**：
  - 第 613 行 `CHROME_PROFILE_MARKER` 转义：`%CHROME_PROFILE_DIR:'=''%` 是为了处理 profile 路径中的单引号（传入 PowerShell 字符串需要转义）。`CHROME_PROFILE_DIR` 默认值 `%LOCALAPPDATA%\APS\Chrome109Profile` 不太可能包含单引号，但这个防御是合理的。
  - PowerShell 脚本中 `$marker` 使用 `.ToLowerInvariant()` 归一化后与命令行 `.ToLowerInvariant()` 比较——大小写无关匹配**正确**。

  **结论**：功能正确，目标达成。

  ### 2. 安装器卸载匹配（`installer/aps_win7_chrome.iss`）

  **目标**：卸载时不再只按当前账户 profile 绝对路径匹配，改为按 APS 标准 profile 后缀匹配，覆盖跨账户场景。

  **实现审查**：
  - 第 61-64 行新增 `ApsChromeProfileSuffixMarker()`，返回 `\aps\chrome109profile`——**正确**
  - 第 66-99 行 `BuildStopChromePowerShellParams` 现在接收两个参数：精确路径 + 后缀 marker
  - 生成的 PowerShell 内嵌函数 `Test-ApsChromeCommandLine` 匹配逻辑：
    1. 命令行非空——**正确**
    2. 包含 `--user-data-dir`——**正确**
    3. 后缀 marker 非空时匹配后缀——**跨账户核心逻辑**
    4. 精确路径非空时匹配精确路径——**当前账户兼容**
    5. 两条之一命中即算 APS Chrome——**正确**
  - 第 115 行调用：`BuildStopChromePowerShellParams(CurrentUserChromeProfilePath(), ApsChromeProfileSuffixMarker())`——**参数传递正确**
  - 停止后二次验证仍用同一套条件——**闭合**

  **潜在 BUG 检查**：
  - 后缀 marker `\aps\chrome109profile` 会被小写化后与命令行小写化比较；Windows `%LOCALAPPDATA%` 实际路径类似 `C:\Users\xxx\AppData\Local\APS\Chrome109Profile`，小写后确实包含 `\aps\chrome109profile`——**匹配正确**
  - `$exactMarker` 和 `$suffixMarker` 的单引号转义逻辑一致——**正确**

  **结论**：功能正确，目标达成。

  ### 3. Python 侧（`web/bootstrap/launcher.py`）

  - 第 832-835 行仅新增注释说明三端统一语义——**最小侵入，符合目标**
  - `_list_aps_chrome_pids` 现有逻辑已使用精确 profile 绝对路径匹配（`$marker` = profile 绝对路径小写），但**没有检查 `--user-data-dir`**——这是一个值得注意的差异，但因为 Python 侧使用精确绝对路径（包含 `Chrome109Profile`），误命中普通 Chrome 的概率接近零，目前可接受。

  ### 4. 测试（`tests/test_win7_launcher_runtime_paths.py`）

  - 第 169-175 行新增 `test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process()`：
    - 验证 `--user-data-dir` 出现在批处理中——**正确**
    - 验证 `CHROME_PROFILE_DIR` 出现——**正确**
    - 验证使用 `Get-CimInstance`/`Get-WmiObject`——**正确**
    - 验证旧 `tasklist` 宽匹配不存在——**正确的负断言**
  - 第 277-281 行新增 `test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only()`——**正确**
  - 第 284-290 行更新 `test_chrome_installer_stop_helper_uses_current_user_profile_path_marker()`，验证 `ApsChromeProfileSuffixMarker` 和新调用签名——**正确**
- 结论:

  第一轮审查通过：三项核心修改均达成功能目标，未发现功能性 BUG。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:607-626#probe_aps_chrome_alive`
  - `assets/启动_排产系统_Chrome.bat:589-605#probe_chrome_profile_dir`
  - `assets/启动_排产系统_Chrome.bat:260-268`
  - `installer/aps_win7_chrome.iss:61-99`
  - `web/bootstrap/launcher.py:832-835`
  - `tests/test_win7_launcher_runtime_paths.py:169-175`
  - `tests/test_win7_launcher_runtime_paths.py:277-290`

### R2 · 第二轮：实现质量审查

- 状态: 已完成
- 记录时间: 2026-04-07T03:25:14.117Z
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py
- 摘要:

  ## 第二轮：实现质量

  ### 1. 是否有过度兜底或静默回退

  **批处理 `:probe_aps_chrome_alive`**：
  - 无 PowerShell → 记录日志 + 不定义 `CHROME_ALIVE` → 调用方当失败处理并退出 11——**失败闭合，不是静默回退**
  - 查询失败（rc=1）→ 记录日志 + 不定义 `CHROME_ALIVE` → 同样失败闭合——**正确**
  - 查到进程但不匹配（rc=2）→ 记录 `chrome_alive_probe=missing`——**正确的可观测失败**
  - **不存在任何静默降级到旧宽匹配的路径**——审查通过

  **批处理 `:probe_chrome_profile_dir`**：
  - 创建目录失败 → 记录日志 + 不定义 `CHROME_PROFILE_READY` → 调用方退出 10——**失败闭合**
  - 写探针文件失败 → 同上——**失败闭合**
  - 成功后清理探针临时文件——**无副作用残留**
  - **不存在"创建失败后跳过继续"的静默回退**——审查通过

  **安装器 `BuildStopChromePowerShellParams`**：
  - `Get-CimInstance` 失败 → 回退到 `Get-WmiObject`——**合理降级（Win7 兼容）**
  - `Get-WmiObject` 也失败 → `exit 1` → 调用方 `TryStopApsChromeProcesses` 返回 `False`——**失败闭合**
  - `Stop-Process` 失败 → `exit 1` → 同上——**失败闭合**
  - 停止后二次检查发现残留 → `exit 1` → 同上——**失败闭合**
  - **不存在"关闭失败但声称成功"的路径**——审查通过

  **Python 侧**：
  - 仅新增注释，无代码修改——**无新的兜底路径引入**

  ### 2. 实现是否简洁优雅

  **批处理判活**：
  - PowerShell 内嵌脚本是单行紧凑写法，在批处理中这是唯一实用的做法（多行 PowerShell 嵌入批处理很难处理引号和换行）。虽然长达一行但逻辑清晰：准备 marker → 查询 → 遍历匹配 → 返回结果。**没有更好的替代方案**。

  **安装器 PowerShell**：
  - 把匹配逻辑抽成内部函数 `Test-ApsChromeCommandLine`，查询、停止、二次验证复用同一函数——**结构清晰**
  - `BuildStopChromePowerShellParams` 接收两个 marker 参数而不是硬编码——**可测试性好**

  **Python 注释**：
  - 4 行注释清楚解释了三端差异和共同目标——**简洁有效**

  ### 3. 逻辑严谨性逐行审查

  **批处理第 613 行**：`set "CHROME_PROFILE_MARKER=%CHROME_PROFILE_DIR:'=''%"`
  - 这是标准的批处理字符串替换语法，把单引号替换为两个单引号——**正确**

  **批处理第 614 行内嵌 PowerShell**：
  - `$marker='...'`.ToLowerInvariant()` 实际发生在 PowerShell 运行时内部——**正确**
  - 注意：marker 直接拼进 PowerShell 字符串，理论上如果 `CHROME_PROFILE_DIR` 包含 PowerShell 特殊字符（如 `$`）可能导致注入。但 Windows 路径不会包含 `$` 或其他 PowerShell 可执行字符，且 `LOCALAPPDATA` 路径是由系统控制的——**风险可忽略**

  **安装器第 73-74 行**：`StringChangeEx(ExactMarker, '''', '''''', True)` 和 `StringChangeEx(SuffixMarker, '''', '''''', True)`
  - Inno Setup 的 Pascal 字符串中 `''''` 是转义的单引号 `'`，`''''''` 是两个单引号 `''`——**正确转义**

  **安装器第 80-86 行** `Test-ApsChromeCommandLine` 内部：
  - 先检查空命令行 → 检查 `--user-data-dir` → 检查后缀 → 检查精确路径——**顺序合理**
  - 注意：后缀检查优先于精确路径检查，这意味着当两者都匹配时以后缀为准命中——**语义正确，因为同一进程两者必然都命中**
- 结论:

  第二轮审查通过：实现简洁、没有过度兜底或静默回退。发现两个低风险待观察点和一个中风险注释不一致问题。
- 问题:
  - [中] 其他: Python 侧注释与实现不一致：声称检查 --user-data-dir 但实际未检查
  - [低] 其他: 无 PowerShell 场景下判活会硬失败（设计意图）
  - [低] 其他: 安装器双匹配逻辑在当前场景下有冗余但设计合理

### R3 · 第三轮：边界与一致性审查

- 状态: 已完成
- 记录时间: 2026-04-07T03:25:31.801Z
- 已审模块: DELIVERY_WIN7.md, installer/README_WIN7_INSTALLER.md, tests/test_win7_launcher_runtime_paths.py, tests/regression_shared_runtime_state.py, tests/regression_runtime_stop_cli.py
- 摘要:

  ## 第三轮：边界与一致性

  ### 1. 三端语义统一审查

  | 维度 | 批处理（启动器） | 安装器（卸载） | Python（停机） |
  |---|---|---|---|
  | 查询方式 | `Get-CimInstance` / `Get-WmiObject` | 同左 | 同左 |
  | 命令行检查 `--user-data-dir` | ✅ 是 | ✅ 是 | ❌ 否（仅按 profile 路径匹配） |
  | profile 路径匹配 | 精确路径（当前账户） | 精确路径 + 后缀 marker | 精确路径（当前账户） |
  | 大小写归一化 | `.ToLowerInvariant()` | `.ToLowerInvariant()` | `.lower()` |
  | 查询失败行为 | 失败闭合（退出 11） | 失败闭合（返回 False） | 失败闭合（返回 None） |
  | `Get-CimInstance` → `Get-WmiObject` 降级 | ✅ | ✅ | ✅ |

  **结论**：三端在核心语义上高度一致。唯一偏差是 Python 侧不检查 `--user-data-dir`（已在 R2 记录为 `py-comment-vs-impl-gap`）。该偏差在实际运行中不会造成误判，因为 Python 使用的 marker 是绝对路径，足以唯一标识 APS Chrome。

  ### 2. 测试覆盖审查

  **已有守卫**：
  - `test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process` — 覆盖批处理判活字符串守卫
  - `test_launcher_bat_contains_json_health_probe_and_owner_fallback` — 覆盖批处理总体结构
  - `test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only` — 覆盖安装器跨账户匹配
  - `test_chrome_installer_stop_helper_uses_current_user_profile_path_marker` — 覆盖安装器新签名
  - `test_installers_fail_closed_on_silent_uninstall_and_retry_delete` — 覆盖安装器失败闭合
  - `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable` — 覆盖 Python 停机失败闭合
  - `test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup` — 覆盖 Python 停机实现

  **覆盖缺口**：
  - 所有测试都是**字符串守卫**（验证文件中包含特定字符串），而非行为守卫（实际运行 PowerShell 判活流程）——这是合理的，因为批处理/安装器不能在单测中真正执行
  - Python 侧 `_list_aps_chrome_pids` 的行为覆盖通过 `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable` 间接覆盖——**合理**
  - `regression_shared_runtime_state.py` 和 `regression_runtime_stop_cli.py` 覆盖了共享状态和停机链路——**不受本次修改影响**

  **覆盖结论**：测试覆盖在字符串守卫层面是充分的，覆盖了批处理/安装器/Python 三端的关键匹配条件、失败闭合语义和旧路径消除。

  ### 3. 文档同步审查

  **`DELIVERY_WIN7.md`**：
  - 第 40 行正确描述启动器只把 APS 专用 `--user-data-dir` 进程视为成功
  - 第 44 行正确描述卸载器会尝试关闭任意账户下使用 APS 标准 profile 的 APS Chrome
  - 第 166-173 行"残余问题收口验收"节完整覆盖普通 Chrome 共存和双账户卸载两个场景
  - 需要检查的日志键 `chrome_alive_probe`、`chrome_cmd` 已写明

  **`installer/README_WIN7_INSTALLER.md`**：
  - 第 222-224 行启动排障已同步描述新的判活语义
  - 第 245-247 行卸载说明已同步描述跨账户匹配和失败闭合
  - 第 264-273 行"残余问题收口验收"与 `DELIVERY_WIN7.md` 口径一致

  **文档结论**：两份文档的口径完全一致，内容覆盖了启动器收紧、卸载器收紧、验收场景、排障日志键四个方面。

  ### 4. 原始 review 问题闭合检查

  对照之前 review（`.limcode/review/20260407_aps_startup_chrome_launch_review.md`）的三个发现：

  1. **`launcher-silent-chrome-failure`（高）**：浏览器启动结果判定过于乐观 → **已修复**。现在有 `probe_chrome_profile_dir`（目录可写校验）和 `probe_aps_chrome_alive`（进程存活确认），不再依赖 `start` 返回码。
  2. **`packaging-misses-browser-smoke`（高）**：双包打包链缺少浏览器最小冒烟 → **已修复**（在本次修改范围外，`package_win7.ps1` 已有 `Invoke-ChromeRuntimeSmoke`）。
  3. **`bat-contract-owner-unescape`（中）**：批处理契约解析未反转义 owner → **已修复**。第 545 行 `set "CONTRACT_OWNER=!CONTRACT_OWNER:\\=\\!"` 已做归一化处理。
- 结论:

  第三轮审查通过：三端语义基本统一，测试覆盖充分，文档同步到位。唯一需要关注的是 Python 侧注释与代码的语义偏差（已在第二轮记录）。整体修改质量高，达成既定目标。
- 下一步建议:

  唯一建议：在 `_list_aps_chrome_pids` 的 PowerShell 脚本中增加 `--user-data-dir` 条件（一行改动），使三端匹配语义彻底统一。其余修改可直接提交。

## 最终结论

## 三轮深度审查总结

本次修改涵盖 6 个文件，核心目标是消除启动器和安装器中的两类假成功路径：

1. **启动器判活收紧**（`assets/启动_排产系统_Chrome.bat`）——新增 `probe_chrome_profile_dir` 目录可写校验和 `probe_aps_chrome_alive` 进程精确判活，完全删除旧的按镜像名宽匹配，无 PowerShell 时失败闭合而非静默降级。**实现正确、简洁、无过度兜底**。

2. **安装器卸载匹配收口**（`installer/aps_win7_chrome.iss`）——新增 `ApsChromeProfileSuffixMarker` 和 `Test-ApsChromeCommandLine` 函数，同时支持当前账户精确路径和跨账户后缀匹配，二次验证闭合。**实现正确、结构清晰**。

3. **Python 侧最小联动**（`web/bootstrap/launcher.py`）——仅新增 4 行注释说明三端统一语义。代码未做行为修改。

4. **测试守卫**（`tests/test_win7_launcher_runtime_paths.py`）——新增 3 个字符串守卫，覆盖批处理判活、安装器跨账户匹配、安装器新签名。

5. **文档同步**（`DELIVERY_WIN7.md`、`installer/README_WIN7_INSTALLER.md`）——两份文档口径一致，完整覆盖启动器收紧、卸载器收紧、验收场景、排障日志键。

### 审查发现汇总

| 问题 | 严重级别 | 状态 |
|---|---|---|
| Python 侧注释声称检查 `--user-data-dir` 但代码未检查 | 中 | 开放 |
| 无 PowerShell 场景下判活硬失败 | 低 | 接受风险 |
| 安装器双匹配在当前场景有冗余 | 低 | 接受风险 |

### 结论

**整体修改质量高**。三项核心修改均达成功能目标，没有引入新的静默回退或过度兜底，逻辑严谨，测试充分，文档同步。之前 review 识别的 3 个高/中风险问题已全部被修复。

唯一需要在提交前处理的是 **`py-comment-vs-impl-gap`**（中风险）：建议在 `_list_aps_chrome_pids` 的 PowerShell 脚本中增加 `$cmd.ToLowerInvariant().Contains('--user-data-dir')` 条件（一行改动），使注释与实现以及三端语义彻底一致。这不是 BUG（当前不会误判），但会消除注释与代码之间的语义偏差，防止后续维护者误读。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mno22f65-rq8uq8",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T03:25:44.394Z",
  "finalizedAt": "2026-04-07T03:25:44.394Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "APS启动链路与Chrome残余问题修复_三轮深度审查",
    "date": "2026-04-07",
    "overview": "对当前未提交的启动器浏览器判活收紧、安装器卸载匹配收口、文档同步三类修改进行三轮深度审查"
  },
  "scope": {
    "markdown": "# APS启动链路与Chrome残余问题修复 三轮深度审查\n\n- 日期：2026-04-07\n- 范围：`assets/启动_排产系统_Chrome.bat`、`installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`tests/test_win7_launcher_runtime_paths.py`、`DELIVERY_WIN7.md`、`installer/README_WIN7_INSTALLER.md`\n- 目标：验证当前未提交修改是否正确达成了以下三个目标：\n  1. 启动器浏览器判活从\"任意 Chrome 存活\"收紧为\"APS 专用 profile 存活\"\n  2. 浏览器运行时卸载器从\"当前账户路径匹配\"收紧为\"任意账户 APS 标准 profile 命令行匹配\"\n  3. 三端（批处理启动器、安装器、Python 停机链路）语义统一\n\n## 审查方法\n\n分三轮递进审查：\n- 第一轮：功能正确性——是否达成目标，核心逻辑有无 BUG\n- 第二轮：实现质量——是否优雅简洁，有无过度兜底或静默回退\n- 第三轮：边界与一致性——三端语义是否统一，测试覆盖是否充分，文档是否同步"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查总结\n\n本次修改涵盖 6 个文件，核心目标是消除启动器和安装器中的两类假成功路径：\n\n1. **启动器判活收紧**（`assets/启动_排产系统_Chrome.bat`）——新增 `probe_chrome_profile_dir` 目录可写校验和 `probe_aps_chrome_alive` 进程精确判活，完全删除旧的按镜像名宽匹配，无 PowerShell 时失败闭合而非静默降级。**实现正确、简洁、无过度兜底**。\n\n2. **安装器卸载匹配收口**（`installer/aps_win7_chrome.iss`）——新增 `ApsChromeProfileSuffixMarker` 和 `Test-ApsChromeCommandLine` 函数，同时支持当前账户精确路径和跨账户后缀匹配，二次验证闭合。**实现正确、结构清晰**。\n\n3. **Python 侧最小联动**（`web/bootstrap/launcher.py`）——仅新增 4 行注释说明三端统一语义。代码未做行为修改。\n\n4. **测试守卫**（`tests/test_win7_launcher_runtime_paths.py`）——新增 3 个字符串守卫，覆盖批处理判活、安装器跨账户匹配、安装器新签名。\n\n5. **文档同步**（`DELIVERY_WIN7.md`、`installer/README_WIN7_INSTALLER.md`）——两份文档口径一致，完整覆盖启动器收紧、卸载器收紧、验收场景、排障日志键。\n\n### 审查发现汇总\n\n| 问题 | 严重级别 | 状态 |\n|---|---|---|\n| Python 侧注释声称检查 `--user-data-dir` 但代码未检查 | 中 | 开放 |\n| 无 PowerShell 场景下判活硬失败 | 低 | 接受风险 |\n| 安装器双匹配在当前场景有冗余 | 低 | 接受风险 |\n\n### 结论\n\n**整体修改质量高**。三项核心修改均达成功能目标，没有引入新的静默回退或过度兜底，逻辑严谨，测试充分，文档同步。之前 review 识别的 3 个高/中风险问题已全部被修复。\n\n唯一需要在提交前处理的是 **`py-comment-vs-impl-gap`**（中风险）：建议在 `_list_aps_chrome_pids` 的 PowerShell 脚本中增加 `$cmd.ToLowerInvariant().Contains('--user-data-dir')` 条件（一行改动），使注释与实现以及三端语义彻底一致。这不是 BUG（当前不会误判），但会消除注释与代码之间的语义偏差，防止后续维护者误读。",
    "recommendedNextAction": "在 `web/bootstrap/launcher.py` 的 `_list_aps_chrome_pids` 中，将第 858 行的匹配条件从 `$cmd.ToLowerInvariant().Contains($marker)` 改为 `$cmdLower = $cmd.ToLowerInvariant(); $cmdLower.Contains('--user-data-dir') -and $cmdLower.Contains($marker)`，使三端语义完全统一。改完后即可提交。",
    "reviewedModules": [
      "assets/启动_排产系统_Chrome.bat",
      "installer/aps_win7_chrome.iss",
      "web/bootstrap/launcher.py",
      "tests/test_win7_launcher_runtime_paths.py",
      "DELIVERY_WIN7.md",
      "installer/README_WIN7_INSTALLER.md",
      "tests/regression_shared_runtime_state.py",
      "tests/regression_runtime_stop_cli.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 2
    }
  },
  "milestones": [
    {
      "id": "R1",
      "title": "第一轮：功能正确性审查",
      "status": "completed",
      "recordedAt": "2026-04-07T03:24:40.461Z",
      "summaryMarkdown": "## 第一轮：功能正确性\n\n### 1. 启动器浏览器判活（`assets/启动_排产系统_Chrome.bat`）\n\n**目标**：拉起 Chrome 后不再按\"任意 chrome.exe 存活\"判定成功，改为按 APS 专用 `--user-data-dir` 命令行匹配。\n\n**实现审查**：\n- 第 607-626 行新增 `:probe_aps_chrome_alive` 子程序，逻辑正确：\n  1. 无 PowerShell 时 `CHROME_ALIVE` 保持未定义并记录 `chrome_alive_probe=no_powershell`，不再降级到宽匹配——**正确**\n  2. 使用 `Get-CimInstance Win32_Process` 优先、`Get-WmiObject Win32_Process` 降级查询——**正确**\n  3. 匹配条件：命令行非空 + 包含 `--user-data-dir` + 包含 `$marker`（profile 路径小写）——**正确**\n  4. 返回码语义：0=找到、1=查询失败、2=未找到——**清晰且可区分**\n- 第 589-605 行新增 `:probe_chrome_profile_dir` 子程序，在拉起浏览器前校验 profile 目录可写——**正确闭合**\n- 第 260-268 行 `:OPEN_CHROME` 中调用 `call :probe_aps_chrome_alive`，失败时明确提示\"未能确认 APS 专用浏览器已拉起\"并退出码 11——**正确**\n- 旧的 `tasklist` 宽匹配已完全删除——**验证通过**\n\n**潜在 BUG 检查**：\n- 第 613 行 `CHROME_PROFILE_MARKER` 转义：`%CHROME_PROFILE_DIR:'=''%` 是为了处理 profile 路径中的单引号（传入 PowerShell 字符串需要转义）。`CHROME_PROFILE_DIR` 默认值 `%LOCALAPPDATA%\\APS\\Chrome109Profile` 不太可能包含单引号，但这个防御是合理的。\n- PowerShell 脚本中 `$marker` 使用 `.ToLowerInvariant()` 归一化后与命令行 `.ToLowerInvariant()` 比较——大小写无关匹配**正确**。\n\n**结论**：功能正确，目标达成。\n\n### 2. 安装器卸载匹配（`installer/aps_win7_chrome.iss`）\n\n**目标**：卸载时不再只按当前账户 profile 绝对路径匹配，改为按 APS 标准 profile 后缀匹配，覆盖跨账户场景。\n\n**实现审查**：\n- 第 61-64 行新增 `ApsChromeProfileSuffixMarker()`，返回 `\\aps\\chrome109profile`——**正确**\n- 第 66-99 行 `BuildStopChromePowerShellParams` 现在接收两个参数：精确路径 + 后缀 marker\n- 生成的 PowerShell 内嵌函数 `Test-ApsChromeCommandLine` 匹配逻辑：\n  1. 命令行非空——**正确**\n  2. 包含 `--user-data-dir`——**正确**\n  3. 后缀 marker 非空时匹配后缀——**跨账户核心逻辑**\n  4. 精确路径非空时匹配精确路径——**当前账户兼容**\n  5. 两条之一命中即算 APS Chrome——**正确**\n- 第 115 行调用：`BuildStopChromePowerShellParams(CurrentUserChromeProfilePath(), ApsChromeProfileSuffixMarker())`——**参数传递正确**\n- 停止后二次验证仍用同一套条件——**闭合**\n\n**潜在 BUG 检查**：\n- 后缀 marker `\\aps\\chrome109profile` 会被小写化后与命令行小写化比较；Windows `%LOCALAPPDATA%` 实际路径类似 `C:\\Users\\xxx\\AppData\\Local\\APS\\Chrome109Profile`，小写后确实包含 `\\aps\\chrome109profile`——**匹配正确**\n- `$exactMarker` 和 `$suffixMarker` 的单引号转义逻辑一致——**正确**\n\n**结论**：功能正确，目标达成。\n\n### 3. Python 侧（`web/bootstrap/launcher.py`）\n\n- 第 832-835 行仅新增注释说明三端统一语义——**最小侵入，符合目标**\n- `_list_aps_chrome_pids` 现有逻辑已使用精确 profile 绝对路径匹配（`$marker` = profile 绝对路径小写），但**没有检查 `--user-data-dir`**——这是一个值得注意的差异，但因为 Python 侧使用精确绝对路径（包含 `Chrome109Profile`），误命中普通 Chrome 的概率接近零，目前可接受。\n\n### 4. 测试（`tests/test_win7_launcher_runtime_paths.py`）\n\n- 第 169-175 行新增 `test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process()`：\n  - 验证 `--user-data-dir` 出现在批处理中——**正确**\n  - 验证 `CHROME_PROFILE_DIR` 出现——**正确**\n  - 验证使用 `Get-CimInstance`/`Get-WmiObject`——**正确**\n  - 验证旧 `tasklist` 宽匹配不存在——**正确的负断言**\n- 第 277-281 行新增 `test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only()`——**正确**\n- 第 284-290 行更新 `test_chrome_installer_stop_helper_uses_current_user_profile_path_marker()`，验证 `ApsChromeProfileSuffixMarker` 和新调用签名——**正确**",
      "conclusionMarkdown": "第一轮审查通过：三项核心修改均达成功能目标，未发现功能性 BUG。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 607,
          "lineEnd": 626,
          "symbol": "probe_aps_chrome_alive"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 589,
          "lineEnd": 605,
          "symbol": "probe_chrome_profile_dir"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 260,
          "lineEnd": 268
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 61,
          "lineEnd": 99
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 835
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 169,
          "lineEnd": 175
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 277,
          "lineEnd": 290
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "installer/aps_win7_chrome.iss",
        "web/bootstrap/launcher.py",
        "tests/test_win7_launcher_runtime_paths.py"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    },
    {
      "id": "R2",
      "title": "第二轮：实现质量审查",
      "status": "completed",
      "recordedAt": "2026-04-07T03:25:14.117Z",
      "summaryMarkdown": "## 第二轮：实现质量\n\n### 1. 是否有过度兜底或静默回退\n\n**批处理 `:probe_aps_chrome_alive`**：\n- 无 PowerShell → 记录日志 + 不定义 `CHROME_ALIVE` → 调用方当失败处理并退出 11——**失败闭合，不是静默回退**\n- 查询失败（rc=1）→ 记录日志 + 不定义 `CHROME_ALIVE` → 同样失败闭合——**正确**\n- 查到进程但不匹配（rc=2）→ 记录 `chrome_alive_probe=missing`——**正确的可观测失败**\n- **不存在任何静默降级到旧宽匹配的路径**——审查通过\n\n**批处理 `:probe_chrome_profile_dir`**：\n- 创建目录失败 → 记录日志 + 不定义 `CHROME_PROFILE_READY` → 调用方退出 10——**失败闭合**\n- 写探针文件失败 → 同上——**失败闭合**\n- 成功后清理探针临时文件——**无副作用残留**\n- **不存在\"创建失败后跳过继续\"的静默回退**——审查通过\n\n**安装器 `BuildStopChromePowerShellParams`**：\n- `Get-CimInstance` 失败 → 回退到 `Get-WmiObject`——**合理降级（Win7 兼容）**\n- `Get-WmiObject` 也失败 → `exit 1` → 调用方 `TryStopApsChromeProcesses` 返回 `False`——**失败闭合**\n- `Stop-Process` 失败 → `exit 1` → 同上——**失败闭合**\n- 停止后二次检查发现残留 → `exit 1` → 同上——**失败闭合**\n- **不存在\"关闭失败但声称成功\"的路径**——审查通过\n\n**Python 侧**：\n- 仅新增注释，无代码修改——**无新的兜底路径引入**\n\n### 2. 实现是否简洁优雅\n\n**批处理判活**：\n- PowerShell 内嵌脚本是单行紧凑写法，在批处理中这是唯一实用的做法（多行 PowerShell 嵌入批处理很难处理引号和换行）。虽然长达一行但逻辑清晰：准备 marker → 查询 → 遍历匹配 → 返回结果。**没有更好的替代方案**。\n\n**安装器 PowerShell**：\n- 把匹配逻辑抽成内部函数 `Test-ApsChromeCommandLine`，查询、停止、二次验证复用同一函数——**结构清晰**\n- `BuildStopChromePowerShellParams` 接收两个 marker 参数而不是硬编码——**可测试性好**\n\n**Python 注释**：\n- 4 行注释清楚解释了三端差异和共同目标——**简洁有效**\n\n### 3. 逻辑严谨性逐行审查\n\n**批处理第 613 行**：`set \"CHROME_PROFILE_MARKER=%CHROME_PROFILE_DIR:'=''%\"`\n- 这是标准的批处理字符串替换语法，把单引号替换为两个单引号——**正确**\n\n**批处理第 614 行内嵌 PowerShell**：\n- `$marker='...'`.ToLowerInvariant()` 实际发生在 PowerShell 运行时内部——**正确**\n- 注意：marker 直接拼进 PowerShell 字符串，理论上如果 `CHROME_PROFILE_DIR` 包含 PowerShell 特殊字符（如 `$`）可能导致注入。但 Windows 路径不会包含 `$` 或其他 PowerShell 可执行字符，且 `LOCALAPPDATA` 路径是由系统控制的——**风险可忽略**\n\n**安装器第 73-74 行**：`StringChangeEx(ExactMarker, '''', '''''', True)` 和 `StringChangeEx(SuffixMarker, '''', '''''', True)`\n- Inno Setup 的 Pascal 字符串中 `''''` 是转义的单引号 `'`，`''''''` 是两个单引号 `''`——**正确转义**\n\n**安装器第 80-86 行** `Test-ApsChromeCommandLine` 内部：\n- 先检查空命令行 → 检查 `--user-data-dir` → 检查后缀 → 检查精确路径——**顺序合理**\n- 注意：后缀检查优先于精确路径检查，这意味着当两者都匹配时以后缀为准命中——**语义正确，因为同一进程两者必然都命中**",
      "conclusionMarkdown": "第二轮审查通过：实现简洁、没有过度兜底或静默回退。发现两个低风险待观察点和一个中风险注释不一致问题。",
      "evidence": [],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "installer/aps_win7_chrome.iss",
        "web/bootstrap/launcher.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "py-comment-vs-impl-gap",
        "no-powershell-hard-fail",
        "dual-match-redundancy"
      ]
    },
    {
      "id": "R3",
      "title": "第三轮：边界与一致性审查",
      "status": "completed",
      "recordedAt": "2026-04-07T03:25:31.801Z",
      "summaryMarkdown": "## 第三轮：边界与一致性\n\n### 1. 三端语义统一审查\n\n| 维度 | 批处理（启动器） | 安装器（卸载） | Python（停机） |\n|---|---|---|---|\n| 查询方式 | `Get-CimInstance` / `Get-WmiObject` | 同左 | 同左 |\n| 命令行检查 `--user-data-dir` | ✅ 是 | ✅ 是 | ❌ 否（仅按 profile 路径匹配） |\n| profile 路径匹配 | 精确路径（当前账户） | 精确路径 + 后缀 marker | 精确路径（当前账户） |\n| 大小写归一化 | `.ToLowerInvariant()` | `.ToLowerInvariant()` | `.lower()` |\n| 查询失败行为 | 失败闭合（退出 11） | 失败闭合（返回 False） | 失败闭合（返回 None） |\n| `Get-CimInstance` → `Get-WmiObject` 降级 | ✅ | ✅ | ✅ |\n\n**结论**：三端在核心语义上高度一致。唯一偏差是 Python 侧不检查 `--user-data-dir`（已在 R2 记录为 `py-comment-vs-impl-gap`）。该偏差在实际运行中不会造成误判，因为 Python 使用的 marker 是绝对路径，足以唯一标识 APS Chrome。\n\n### 2. 测试覆盖审查\n\n**已有守卫**：\n- `test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process` — 覆盖批处理判活字符串守卫\n- `test_launcher_bat_contains_json_health_probe_and_owner_fallback` — 覆盖批处理总体结构\n- `test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only` — 覆盖安装器跨账户匹配\n- `test_chrome_installer_stop_helper_uses_current_user_profile_path_marker` — 覆盖安装器新签名\n- `test_installers_fail_closed_on_silent_uninstall_and_retry_delete` — 覆盖安装器失败闭合\n- `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable` — 覆盖 Python 停机失败闭合\n- `test_launcher_python_runtime_stop_uses_powershell_and_fail_closed_cleanup` — 覆盖 Python 停机实现\n\n**覆盖缺口**：\n- 所有测试都是**字符串守卫**（验证文件中包含特定字符串），而非行为守卫（实际运行 PowerShell 判活流程）——这是合理的，因为批处理/安装器不能在单测中真正执行\n- Python 侧 `_list_aps_chrome_pids` 的行为覆盖通过 `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable` 间接覆盖——**合理**\n- `regression_shared_runtime_state.py` 和 `regression_runtime_stop_cli.py` 覆盖了共享状态和停机链路——**不受本次修改影响**\n\n**覆盖结论**：测试覆盖在字符串守卫层面是充分的，覆盖了批处理/安装器/Python 三端的关键匹配条件、失败闭合语义和旧路径消除。\n\n### 3. 文档同步审查\n\n**`DELIVERY_WIN7.md`**：\n- 第 40 行正确描述启动器只把 APS 专用 `--user-data-dir` 进程视为成功\n- 第 44 行正确描述卸载器会尝试关闭任意账户下使用 APS 标准 profile 的 APS Chrome\n- 第 166-173 行\"残余问题收口验收\"节完整覆盖普通 Chrome 共存和双账户卸载两个场景\n- 需要检查的日志键 `chrome_alive_probe`、`chrome_cmd` 已写明\n\n**`installer/README_WIN7_INSTALLER.md`**：\n- 第 222-224 行启动排障已同步描述新的判活语义\n- 第 245-247 行卸载说明已同步描述跨账户匹配和失败闭合\n- 第 264-273 行\"残余问题收口验收\"与 `DELIVERY_WIN7.md` 口径一致\n\n**文档结论**：两份文档的口径完全一致，内容覆盖了启动器收紧、卸载器收紧、验收场景、排障日志键四个方面。\n\n### 4. 原始 review 问题闭合检查\n\n对照之前 review（`.limcode/review/20260407_aps_startup_chrome_launch_review.md`）的三个发现：\n\n1. **`launcher-silent-chrome-failure`（高）**：浏览器启动结果判定过于乐观 → **已修复**。现在有 `probe_chrome_profile_dir`（目录可写校验）和 `probe_aps_chrome_alive`（进程存活确认），不再依赖 `start` 返回码。\n2. **`packaging-misses-browser-smoke`（高）**：双包打包链缺少浏览器最小冒烟 → **已修复**（在本次修改范围外，`package_win7.ps1` 已有 `Invoke-ChromeRuntimeSmoke`）。\n3. **`bat-contract-owner-unescape`（中）**：批处理契约解析未反转义 owner → **已修复**。第 545 行 `set \"CONTRACT_OWNER=!CONTRACT_OWNER:\\\\=\\\\!\"` 已做归一化处理。",
      "conclusionMarkdown": "第三轮审查通过：三端语义基本统一，测试覆盖充分，文档同步到位。唯一需要关注的是 Python 侧注释与代码的语义偏差（已在第二轮记录）。整体修改质量高，达成既定目标。",
      "evidence": [],
      "reviewedModules": [
        "DELIVERY_WIN7.md",
        "installer/README_WIN7_INSTALLER.md",
        "tests/test_win7_launcher_runtime_paths.py",
        "tests/regression_shared_runtime_state.py",
        "tests/regression_runtime_stop_cli.py"
      ],
      "recommendedNextAction": "唯一建议：在 `_list_aps_chrome_pids` 的 PowerShell 脚本中增加 `--user-data-dir` 条件（一行改动），使三端匹配语义彻底统一。其余修改可直接提交。",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "py-comment-vs-impl-gap",
      "severity": "medium",
      "category": "other",
      "title": "Python 侧注释与实现不一致：声称检查 --user-data-dir 但实际未检查",
      "descriptionMarkdown": "Python 侧 `_list_aps_chrome_pids` 第 832-835 行新增注释声称三端共同语义都是“只认 APS 专用 `--user-data-dir` 命令行”，但 Python 侧实际的 PowerShell 脚本（第 857-860 行）只检查 `$cmd.ToLowerInvariant().Contains($marker)` 而没有检查 `--user-data-dir`。虽然因为 `$marker` 是包含 `Chrome109Profile` 的绝对路径，误命中普通 Chrome 的概率接近零，但注释描述与实现存在语义差异：注释说“只认 `--user-data-dir` 命令行”，但代码实际不检查该参数。建议要么在 Python 侧也加上 `--user-data-dir` 条件以匹配注释描述，要么把注释改成“Python 侧按精确 profile 绝对路径匹配，批处理和安装器按 `--user-data-dir` + profile 后缀匹配”。",
      "recommendationMarkdown": "建议在 `_list_aps_chrome_pids` 的 PowerShell 脚本中增加 `$cmdLower.Contains('--user-data-dir')` 条件，与批处理和安装器保持一致；或者把注释修改成更精确的描述。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 860,
          "symbol": "_list_aps_chrome_pids"
        },
        {
          "path": "web/bootstrap/launcher.py"
        }
      ],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "no-powershell-hard-fail",
      "severity": "low",
      "category": "other",
      "title": "无 PowerShell 场景下判活会硬失败（设计意图）",
      "descriptionMarkdown": "批处理 `:probe_aps_chrome_alive` 在无 PowerShell 的 Win7 场景下会记录日志 `chrome_alive_probe=no_powershell` 并且 `CHROME_ALIVE` 保持未定义，导致 `:OPEN_CHROME` 中的检查 `if not defined CHROME_ALIVE` 命中而退出。这是正确的失败闭合行为——不能确认就拒绝。但需要留意的是，如果目标机是 Win7 且真正没有 PowerShell（极罕见但理论上可能），则每次启动都会因为“无法确认”而失败。这比以前的假成功强很多，但用户体验上会表现为永远无法启动而不是稍微宽松的探测。这是设计意图中的有意取舍，不是 BUG。",
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "accepted_risk"
    },
    {
      "id": "dual-match-redundancy",
      "severity": "low",
      "category": "other",
      "title": "安装器双匹配逻辑在当前场景下有冗余但设计合理",
      "descriptionMarkdown": "安装器 `BuildStopChromePowerShellParams` 生成的 PowerShell 脚本中 `Test-ApsChromeCommandLine` 函数先检查后缀 marker，再检查精确路径。由于后缀 marker (`\\aps\\chrome109profile`) 已经足够精确，实际上精确路径会永远被后缀包含，所以第二个分支在正常场景下不会被命中。但这不算多余，因为它提供了一层安全网：当用户自定义 profile 目录名（不包含 `aps\\chrome109profile` 后缀）时，精确路径匹配仍能起作用。实现謨义当前不存在这种场景（路径为硬编码），但保留双匹配在可维护性上是合理的。",
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "accepted_risk"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:cbb4676b7bdb068eff5d3c7a7f4ad391d27eece03ee4da50ca5aa2a8bdd71e5e",
    "generatedAt": "2026-04-07T03:25:44.394Z",
    "locale": "zh-CN"
  }
}
```
