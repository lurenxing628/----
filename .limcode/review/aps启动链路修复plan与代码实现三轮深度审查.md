# APS启动链路修复plan与代码实现三轮深度审查
- 日期: 2026-04-07
- 概述: 对照修复plan逐项审查启动器、打包脚本、运行时入口和测试文件的当前实现状态，验证plan是否被正确落地，定位遗漏与潜在BUG
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# APS启动链路修复plan与代码实现三轮深度审查

- 日期：2026-04-07
- 范围：`assets/启动_排产系统_Chrome.bat`、`web/bootstrap/launcher.py`、`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`、`tests/test_win7_launcher_runtime_paths.py`、`validate_dist_exe.py`、`DELIVERY_WIN7.md`、`installer/README_WIN7_INSTALLER.md`
- 目标：三轮审查——第一轮验证plan识别的问题是否真实存在于代码中；第二轮审查plan的方案完整性与遗漏点；第三轮审查实现是否优雅、是否有过度兜底、静默回退或BUG

## 审查上下文

本次审查基于 `.limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md` 作为待验证蓝图，对照工作区中的实际代码与文档，检查该plan是否已被正确实施、方案本身是否存在盲点。

## 评审摘要

- 当前状态: 已完成
- 已审模块: assets/启动_排产系统_Chrome.bat, web/bootstrap/launcher.py, .limcode/skills/aps-package-win7/scripts/package_win7.ps1, validate_dist_exe.py, tests/test_win7_launcher_runtime_paths.py, .limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md, DELIVERY_WIN7.md, installer/README_WIN7_INSTALLER.md
- 当前进度: 已记录 3 个里程碑；最新：R3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 5
- 问题严重级别分布: 高 2 / 中 3 / 低 0
- 最新结论: ## 三轮深度审查总结 本次审查以 `.limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md` 为蓝图，对照工作区实际代码逐项核实、逆向验证、深度排查。共发现 **5 个问题**（2 高 / 3 中），其中 plan 识别的 5 个分叉点全部实证确认，但同时发现了 plan 完全遗漏的 1 个严重 BUG 和 3 个方案层面的缺陷。 ### plan 尚未实施 **plan 中列出的所有改动项（A1-A6、B1-B2、C1-C3）均未在代码中落地。** 当前工作区中的 `启动_排产系统_Chrome.bat`、`package_win7.ps1`、`test_win7_launcher_runtime_paths.py` 等文件仍处于修改前的状态。plan 只是一份蓝图，不是已完成的实施。 ### 必须在实施前修正的问题 | 优先级 | 问题 | 修复代价 | |--------|------|----------| | **P0** | 就绪循环 `%FILE_HOST%`/`%FILE_PORT%` 应改为 `!FILE_HOST!`/`!FILE_PORT!`（第 178-179 行） | 改 3 行 | | **P1** | plan A3 需扩展范围：Python 侧 `_query_process_executable_path` 和 `_list_aps_chrome_pids` 仍用 wmic | 增加 plan 条目 | | **P1** | plan A6 应简化为单一 tasklist 方案，去掉 PowerShell/profile锁 双路径 | 精简 plan 条目 | | **P2** | plan A4 需补充中文镜像名的具体策略 | 补充 plan 说明 | | **P2** | `_list_aps_chrome_pids` 的 `except: return []` 应改为显式降级 + 返回 False | 改 ~10 行 | ### plan 的正确之处 - 5 个分叉点的识别全部准确，无虚报 - "必须保持不变的兼容面"约束设计合理 - 浏览器 profile 可写性校验（A5）设计简洁正确 - 运行时契约 owner 反转义（A2）方向正确 - 批处理 wmic → tasklist（A3）方向正确，只是范围不够 - 打包链路补浏览器冒烟（B1）方向正确 - 静态守卫（C1）设计合理 ### 建议实施顺序 1. **紧急**：修复就绪循环的 `%` → `!` BUG（3 行改动，可立即合并） 2. 修正 plan：扩展 A3 范围、简化 A6、补充 A4 策略 3. 按修正后的 plan 顺序实施 A1 → A2 → A3（含 Python） → A4 → A5 → A6 → B1 → C1-C3
- 下一步建议: 立即修复 P0（就绪循环变量展开 BUG），然后修正 plan 的 A3/A4/A6 范围，最后按修正后的 plan 依序实施。
- 总体结论: 有条件通过

## 评审发现

### Python 侧仍有两处 wmic 硬依赖被 plan 漏掉

- ID: python-wmic-residual
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  plan 第 A3 节声称"Python 侧已改为 tasklist"，并据此只修改批处理的 `:lock_is_active`。但实际上 `web/bootstrap/launcher.py` 中仍有两个函数直接依赖 `wmic`：

  1. `_query_process_executable_path`（第 751 行）：通过 `wmic process where processid=... get ExecutablePath` 查询进程可执行路径，被 `_pid_matches_contract` → `_is_runtime_lock_active` → `acquire_runtime_lock` 以及 `stop_runtime_from_dir` 调用。当 `wmic` 不可用时返回 `None`，导致 `_pid_matches_contract` 返回 `None`，进而使 `_is_runtime_lock_active` 采用失败闭合策略直接认为锁仍活跃——安全但可能造成误阻。

  2. `_list_aps_chrome_pids`（第 813 行）：通过 `wmic process where Name='chrome.exe' and CommandLine like '%marker%'` 枚举 APS 专用浏览器进程。被 `stop_aps_chrome_processes` → `stop_runtime_from_dir` 和安装器卸载链路调用。当 `wmic` 不可用时返回空列表，浏览器进程不会被清理——**这是静默失败，不是失败闭合**。

  plan 只修批处理不修 Python，会造成"bat 用 tasklist 判断存活、Python 用 wmic 判断可执行路径"的新不一致。
- 建议:

  把 `_query_process_executable_path` 改用 PowerShell `Get-Process -Id ... | Select-Object Path` 或 `tasklist /FI "PID eq ..." /V /FO CSV`（后者在 Win7 上可获取镜像名但不一定能获取完整路径）。`_list_aps_chrome_pids` 改用 PowerShell `Get-WmiObject Win32_Process` 或 `wmic` 降级 + `tasklist` 主路径的组合方案。两者都需要处理 wmic 不可用时的降级，且不能像现在一样静默返回空列表。
- 证据:
  - `web/bootstrap/launcher.py:742-769#_query_process_executable_path`
  - `web/bootstrap/launcher.py:806-839#_list_aps_chrome_pids`
  - `web/bootstrap/launcher.py`

### 主程序短时存活探测的中文镜像名兼容性未考虑

- ID: app-spawn-imagename-cjk
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  plan A4 要求"从 `APP_EXE` 解析镜像名，用 `tasklist` 做一次短时存在性判断"。但批处理中 `APP_EXE` 是通过第 20-24 行 `for %%F in (*.exe)` 遍历得到的完整路径，例如 `C:\Program Files\APS\SchedulerApp\排产系统.exe`。提取镜像名需要 `%%~nxF` 风格的操作，但在 `:OPEN_CHROME` 之后的 subroutine 中不能直接用 `for` 变量语法。

  更大的问题是：`tasklist` 筛选 `IMAGENAME` 时，中文镜像名（`排产系统.exe`）在非 UTF-8 代码页下可能无法匹配。plan A1 提出加 `chcp 65001`，但 `chcp 65001` 在 Win7 上对 `tasklist` 的影响不确定——Win7 的 `tasklist` 可能不支持 UTF-8 镜像名筛选。

  plan 没有说明这个中文镜像名场景下的具体策略，可能导致实施者在此处卡住或做出不可靠的实现。
- 建议:

  考虑不按镜像名筛选，而是在 `start` 后通过 `for /f` 捕获 PID（例如用 `wmic process call create` 或 PowerShell 的 `Start-Process -PassThru`），然后按 PID 做 `tasklist` 精确匹配。或者简化为：`start` 后等待 2 秒，再检查 `aps_launch_error.txt` 是否出现。

### plan A6 浏览器存活探测方案过度设计

- ID: a6-overengineered
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  plan A6 设计了"两段式短时探测"和"PowerShell 主路径 + tasklist 降级路径"的复杂组合方案。但实际场景中：

  1. PowerShell 侧需要 `Win32_Process` + 命令行筛选——本质上仍是 WMI 查询，只是通过 PowerShell 调用而非直接 `wmic`。在 Win7 上可靠，但会增加约 1-2 秒的 PowerShell 启动延迟。
  2. 降级路径的"浏览器镜像存在性 + profile 锁痕迹"组合判断没有给出具体实现口径——什么是"profile 锁痕迹"？是 `CHROME_PROFILE_DIR\\SingletonLock`、`CHROME_PROFILE_DIR\\lockfile` 还是 `Local State` 的修改时间？不同版本的 Chrome/Chromium 使用不同的锁机制。
  3. plan 还要求"不允许继续静默成功，应提示用户查看 launcher.log"，但如果 PowerShell 不可用、tasklist 也无法区分 APS Chrome 和用户 Chrome，就会对每次成功启动都弹出"无法确认"提示——这是过度警告。

  相比之下，一个更简洁的方案是：`start` Chrome 后等 2 秒，用 `tasklist /FI "IMAGENAME eq chrome.exe"` 确认有 `chrome.exe` 进程存在。如果没有，说明 Chrome 完全没启动，应 `pause` 报错。如果有，合理假设 APS Chrome 已启动（因为刚刚调用了 `start`）。这个方案不能区分 APS Chrome 和用户已打开的 Chrome，但"Chrome 完全不存在"的极端场景（用户同时没开任何 Chrome）已能覆盖当前用户反馈的核心问题。
- 建议:

  简化 A6 为单一策略：`start` Chrome 后等 2-3 秒，用 `tasklist` 检查 `chrome.exe` 是否存在。若不存在则 `pause` 报错并输出 `launcher.log` 路径与 `chrome_cmd`。不再设计 PowerShell 主/降级双路径，避免批处理复杂度爆炸。

### 就绪循环变量展开方式错误导致首次启动必定超时

- ID: readiness-loop-percent-vs-bang
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  启动器第 5 行已启用 `EnableDelayedExpansion`，但第 162-189 行的 `for /l` 就绪循环内部的第 178-179 行使用了 `%FILE_HOST%` 和 `%FILE_PORT%`（解析时展开），而不是 `!FILE_HOST!` 和 `!FILE_PORT!`（运行时展开）。

  `FILE_HOST` 和 `FILE_PORT` 是由 `for` 循环体内的 `call :read_host_file` 和 `call :read_port_file` 在运行时设置的。但整个 `for /l` 块在解析时会把 `%FILE_HOST%` 展开为其当前值——在循环开始前，这两个变量未定义，因此展开为空字符串。

  实际后果：
  - `set "HOST=%FILE_HOST%"` → `set "HOST="`（清空 HOST）
  - `set "PORT=%FILE_PORT%"` → `set "PORT="`（清空 PORT）
  - `probe_health` 检查到 PORT 为空后直接返回，HEALTH_OK 始终未设置
  - `is_port_listening` 用空 PORT 拼接 `findstr` 模式，无法匹配任何监听端口
  - 就绪检测永远不会成功，循环必定跑完 45 次迭代后走到超时错误路径

  这意味着：**每次首次启动都会等待 45 秒后显示"App did not become ready in time"并 `pause`**。只有复用已有实例的路径（`try_reuse_existing` → `CAN_REUSE_EXISTING`）能正常跳过此循环。

  同样的问题也影响第 166 行：`call :log launch_error="%LAUNCH_ERROR%"` 会把空值写入日志（尽管第 167 行 `echo [launcher] !LAUNCH_ERROR!` 的控制台输出是正确的）。
- 建议:

  将第 178 行改为 `set "HOST=!FILE_HOST!"`，第 179 行改为 `set "PORT=!FILE_PORT!"`，第 166 行改为 `call :log launch_error="!LAUNCH_ERROR!"`。这是经典的批处理延迟展开问题，且脚本已启用 `EnableDelayedExpansion`，只需把 `%` 换成 `!` 即可。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:162-189#for就绪循环`
  - `assets/启动_排产系统_Chrome.bat:178-179#%FILE_HOST%和%FILE_PORT%`
  - `assets/启动_排产系统_Chrome.bat:166-167#%LAUNCH_ERROR%`
  - `assets/启动_排产系统_Chrome.bat`

### Python 侧浏览器清理在无 wmic 时静默失效

- ID: chrome-cleanup-silent-noop
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  `launcher.py` 第 842-856 行的 `stop_aps_chrome_processes` 调用 `_list_aps_chrome_pids`（第 806-839 行）枚举 APS 专用浏览器进程。当 `wmic` 不可用时，`_list_aps_chrome_pids` 在第 826-827 行 `except Exception: return []` 静默返回空列表，`stop_aps_chrome_processes` 返回 `True`（表示成功）。

  这不是失败闭合，是**静默回退**。调用方（安装器卸载链路、`--runtime-stop --stop-aps-chrome`）会以为浏览器已成功关闭，但实际上 Chrome 进程仍在运行。在无 wmic 的 Win10+ 环境下，卸载后 Chrome 进程会残留。
- 建议:

  在 `_list_aps_chrome_pids` 中增加 wmic 不可用时的降级方案（例如 PowerShell `Get-CimInstance Win32_Process`），并且当所有方案都不可用时，`stop_aps_chrome_processes` 应返回 `False` 并记录警告，而不是静默返回 `True`。
- 证据:
  - `web/bootstrap/launcher.py:842-857#stop_aps_chrome_processes`
  - `web/bootstrap/launcher.py:806-839#_list_aps_chrome_pids`
  - `web/bootstrap/launcher.py`

## 评审里程碑

### R1 · 第一轮：plan所识别问题在代码中的实证核实

- 状态: 已完成
- 记录时间: 2026-04-07T01:13:45.156Z
- 已审模块: assets/启动_排产系统_Chrome.bat, web/bootstrap/launcher.py, .limcode/skills/aps-package-win7/scripts/package_win7.ps1, validate_dist_exe.py
- 摘要:

  逐项对照 plan 中标识的 5 个分叉点，在实际代码中验证其存在性与严重度。

  ### 分叉点 1：运行时契约 owner 反转义缺失 — **已确认**

  `web/bootstrap/launcher.py` 第 602-603 行通过 `json.dump(payload, f, ensure_ascii=False, ...)` 写出 `aps_runtime.json`。当 `owner` 值为 `DOMAIN\user` 时，JSON 规范要求序列化为 `"DOMAIN\\user"`（双反斜杠）。

  批处理 `assets/启动_排产系统_Chrome.bat` 第 451-456 行的 `:read_runtime_contract` 用 `findstr` + 文本替换提取 owner，只去掉了逗号和引号，**没有把 `\\` 还原为 `\`**。因此 `CONTRACT_OWNER` 值为 `DOMAIN\\user`（双反斜杠），而 `CURRENT_OWNER`（第 15-17 行组装）是 `DOMAIN\user`（单反斜杠）。第 366 行的 `if /I "%CONTRACT_OWNER%"=="%CURRENT_OWNER%"` 比较会失败，在契约回退路径下把同账户误判为异账户。

  **plan 识别正确。**

  ### 分叉点 2：锁文件进程探测仍依赖 wmic — **已确认**

  `assets/启动_排产系统_Chrome.bat` 第 502-525 行 `:lock_is_active` 完全使用 `where wmic` + `wmic process where "ProcessId=..."` 判断进程是否存活。而 `web/bootstrap/launcher.py` 第 305-332 行 `_pid_exists` 已经改为 `tasklist /FI "PID eq ..." /NH /FO CSV`。

  在 Win10 22H2+ 上 `wmic` 可能已不存在，此时批处理会将 `LOCK_ACTIVE` 设为 `UNKNOWN`，最终走到 `:BLOCKED_UNCERTAIN`（第 208-213 行），阻止正常启动。

  **plan 识别正确。**

  ### 分叉点 3：浏览器启动后无存活验证 — **已确认**

  `assets/启动_排产系统_Chrome.bat` 第 215-232 行 `:OPEN_CHROME` 在调用 `start` 后只检查 `ERRORLEVEL`，第 232 行直接 `exit /b 0`。脚本自身在第 221-222 行的注释中已承认"不能证明 Chrome 启动后一定稳定运行"。没有任何短时存活探测。

  **plan 识别正确。**

  ### 分叉点 4：浏览器 profile 目录未校验可写性 — **已确认**

  第 137 行只有 `if not exist "%CHROME_PROFILE_DIR%" mkdir "%CHROME_PROFILE_DIR%" >nul 2>&1`，无论 `mkdir` 是否成功都会继续执行。没有临时探针文件写入/删除确认。

  **plan 识别正确。**

  ### 分叉点 5：打包链路不覆盖浏览器运行时冒烟 — **已确认**

  `package_win7.ps1` 第 157-167 行 `Test-DistExeStartup` 只调用 `python validate_dist_exe.py`。`validate_dist_exe.py` 明确在注释中写明"只验证主程序 exe 冷启动与 HTTP 页面，不覆盖快捷方式、批处理脚本、环境变量刷新时序或 Chrome 启动链路"。`New-ChromeRuntimePayload`（第 211-258 行）构建裁剪后的运行时 payload 时仅检查 `chrome.exe` 存在，不执行任何可启动性验证。

  **plan 识别正确。**

  ### 第一轮结论

  plan 标识的 5 个分叉点全部在实际代码中得到了实证确认，无虚报。
- 结论:

  plan 标识的 5 个分叉点全部经代码实证确认存在，问题描述准确，无虚报。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:451-456#read_runtime_contract owner提取`
  - `assets/启动_排产系统_Chrome.bat:502-525#lock_is_active wmic`
  - `assets/启动_排产系统_Chrome.bat:215-232#OPEN_CHROME无存活验证`
  - `assets/启动_排产系统_Chrome.bat:137#CHROME_PROFILE_DIR仅mkdir`
  - `web/bootstrap/launcher.py:305-332#_pid_exists使用tasklist`
  - `web/bootstrap/launcher.py:602-603#json.dump写owner`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:157-167#Test-DistExeStartup仅覆盖后端`
  - `validate_dist_exe.py:1-16#验收范围声明`

### R2 · 第二轮：plan方案完整性与遗漏审查

- 状态: 已完成
- 记录时间: 2026-04-07T01:15:22.378Z
- 已审模块: web/bootstrap/launcher.py, tests/test_win7_launcher_runtime_paths.py, .limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md
- 摘要:

  第二轮审查聚焦 plan 方案本身的完整性，发现 3 个显著问题：

  ### 遗漏 1：Python 侧 wmic 残留未纳入修复范围 — **高风险**

  plan 声称"Python 侧已改为 tasklist"并据此只修改批处理。但实际上 `launcher.py` 中仍有两个函数直接依赖 `wmic`：

  - `_query_process_executable_path`（第 742-769 行）：被锁的活跃性判断和停机链路使用。当 `wmic` 不可用时返回 `None`，导致失败闭合（安全但可能误阻）。
  - `_list_aps_chrome_pids`（第 806-839 行）：被浏览器清理链路使用。当 `wmic` 不可用时返回空列表，**导致浏览器进程静默不清理**——这不是失败闭合，是静默回退。

  plan 只修批处理的 `:lock_is_active`，反而会造成"bat 用 tasklist，Python 用 wmic"的**新不一致**。

  ### 遗漏 2：主程序短时存活探测的中文镜像名兼容性

  plan A4 要求"从 `APP_EXE` 解析镜像名，用 `tasklist` 做短时存在性判断"，但没有考虑 `排产系统.exe` 是中文镜像名。在 Win7 默认代码页下，`tasklist /FI "IMAGENAME eq 排产系统.exe"` 可能无法正确匹配。plan 没有给出中文镜像名场景下的具体策略。

  ### 过度设计：浏览器存活探测的双路径方案

  plan A6 设计了"PowerShell 主路径 + tasklist+profile锁降级路径"的复杂两段式探测。但：
  - PowerShell 路径本质上仍是 WMI 查询，会增加 1-2 秒延迟
  - 降级路径的"profile 锁痕迹"没有具体口径
  - 当 PowerShell 不可用且无法区分 APS Chrome 时，会对每次启动都弹告警——过度警告

  更简洁的方案是：等 2-3 秒后用 `tasklist` 检查 `chrome.exe` 是否存在。不存在则 `pause` 报错。存在则合理假设成功。这能覆盖"Chrome 完全没启动"这一核心用户反馈场景。

  ### 其他观察

  - plan C1 的静态守卫设计是合理的，但现有测试文件 `test_win7_launcher_runtime_paths.py` 已有 `test_launcher_bat_contains_json_health_probe_and_owner_fallback()` 在做类似的文本断言，新增守卫应与之统一风格。
  - plan B2 关于"文档中明确 `validate_dist_exe.py` 只覆盖后端"——`DELIVERY_WIN7.md` 第 91 行和 `installer/README_WIN7_INSTALLER.md` 第 248 行已经有此声明，无需重复补充。
  - plan "必须保持不变的兼容面"部分很好，明确了不改 `contract_version`、不改字段名、不改 profile 目录名，是合理的约束。
- 结论:

  plan 方案整体方向正确，但存在 3 个显著遗漏和 2 个过度设计风险，需要在实施前修正。
- 证据:
  - `web/bootstrap/launcher.py:742-769#_query_process_executable_path 使用wmic`
  - `web/bootstrap/launcher.py:806-839#_list_aps_chrome_pids 使用wmic`
  - `web/bootstrap/launcher.py:362-377#_is_runtime_lock_active pid_match判断`
  - `web/bootstrap/launcher.py:905-918#stop_runtime_from_dir pid_match判断`
  - `tests/test_win7_launcher_runtime_paths.py:132-202#静态守卫现状`
- 下一步建议:

  实施前先修正 plan：1）把 Python 侧 `_query_process_executable_path` 和 `_list_aps_chrome_pids` 的 wmic 迁移纳入 A3 范围；2）简化 A6 为单一 tasklist 方案；3）补充主程序短时存活探测的镜像名提取策略说明。
- 问题:
  - [高] 其他: Python 侧仍有两处 wmic 硬依赖被 plan 漏掉
  - [中] 其他: 主程序短时存活探测的中文镜像名兼容性未考虑
  - [中] 其他: plan A6 浏览器存活探测方案过度设计

### R3 · 第三轮：现有代码BUG与静默回退深度排查

- 状态: 已完成
- 记录时间: 2026-04-07T01:20:53.366Z
- 已审模块: assets/启动_排产系统_Chrome.bat
- 摘要:

  第三轮审查深入逐行检查代码逻辑，发现了 plan 和前两轮 review 都完全未提及的关键 BUG 与静默回退：

  ### 严重 BUG：就绪检测循环的变量展开方式错误

  `assets/启动_排产系统_Chrome.bat` 第 162-189 行的 `for /l` 就绪检测循环中，第 178-179 行：

  ```bat
  set "HOST=%FILE_HOST%"
  set "PORT=%FILE_PORT%"
  ```

  使用了 `%`（解析时展开），而不是 `!`（运行时展开）。脚本第 5 行已启用 `EnableDelayedExpansion`，但此处没有利用。

  `FILE_HOST` 和 `FILE_PORT` 是在循环体内由 `call :read_host_file` 和 `call :read_port_file` 在运行时设置的。但整个 `for /l (...)` 块在解析时就把 `%FILE_HOST%` 展开了——此时这两个变量尚未定义，展开结果为空字符串。

  因此每次循环迭代中：
  1. `set "HOST="` 和 `set "PORT="` 被执行（HOST/PORT 被清空）
  2. `probe_health` 检查到 PORT 为空后直接返回，不执行健康检查
  3. `is_port_listening` 用空 PORT 拼接 `findstr` 模式，无法匹配任何监听端口
  4. 就绪检测永远不会成功
  5. 循环必定跑完 45 次迭代后走到超时路径

  **影响**：每次"首次启动"（不走复用路径的场景）都会等待 45 秒后显示 `"App did not become ready in time"` 并 `pause`。只有通过 `try_reuse_existing` → `CAN_REUSE_EXISTING` 的路径（已有运行实例时）才能正常工作。

  同样的问题影响第 166 行 `call :log launch_error="%LAUNCH_ERROR%"`（日志写入空值，但控制台输出第 167 行用了 `!LAUNCH_ERROR!` 所以正确）。

  ### 中风险：Python 侧浏览器清理在无 wmic 时静默"成功"

  `launcher.py` 的 `stop_aps_chrome_processes`（第 842-856 行）调用 `_list_aps_chrome_pids`（第 806-839 行）。当 `wmic` 不可用时，后者在 `except Exception: return []` 静默返回空列表。前者遍历空列表后直接返回 `True`（表示成功）。调用方——安装器卸载链路和 `--runtime-stop --stop-aps-chrome`——会以为浏览器已关闭，但实际上 Chrome 进程仍在运行。

  ### 该 BUG 与用户反馈的关系

  第 178-179 行的 BUG **不是**导致"CMD 闪一下就关"的直接原因——超时路径会 `pause`，不会闪退。用户反馈的闪退仍然指向 plan 中已识别的问题（Chrome 启动后无存活验证，`start` 成功后 `exit /b 0`）。但此 BUG 意味着"首次启动"场景根本无法正常工作，是一个独立的严重缺陷。
- 结论:

  第三轮审查发现一个**严重 BUG**（就绪检测循环中的变量展开错误导致首次启动必定超时 45 秒）和一个中风险的静默回退（Python 侧浏览器清理在无 wmic 时静默失效），两者均被 plan 完全遗漏。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:162-189#for就绪循环变量展开BUG`
  - `assets/启动_排产系统_Chrome.bat:178-179#%FILE_HOST%和%FILE_PORT%应用!!`
  - `assets/启动_排产系统_Chrome.bat:166-167#%LAUNCH_ERROR%应用!!`
  - `web/bootstrap/launcher.py:842-857#stop_aps_chrome_processes静默失效`
- 下一步建议:

  紧急修复就绪循环的 `%` → `!` 变量展开BUG（影响首次启动体验），然后再按修正后的 plan 实施其他改进。
- 问题:
  - [高] JavaScript: 就绪循环变量展开方式错误导致首次启动必定超时
  - [中] 其他: Python 侧浏览器清理在无 wmic 时静默失效

## 最终结论

## 三轮深度审查总结

本次审查以 `.limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md` 为蓝图，对照工作区实际代码逐项核实、逆向验证、深度排查。共发现 **5 个问题**（2 高 / 3 中），其中 plan 识别的 5 个分叉点全部实证确认，但同时发现了 plan 完全遗漏的 1 个严重 BUG 和 3 个方案层面的缺陷。

### plan 尚未实施

**plan 中列出的所有改动项（A1-A6、B1-B2、C1-C3）均未在代码中落地。** 当前工作区中的 `启动_排产系统_Chrome.bat`、`package_win7.ps1`、`test_win7_launcher_runtime_paths.py` 等文件仍处于修改前的状态。plan 只是一份蓝图，不是已完成的实施。

### 必须在实施前修正的问题

| 优先级 | 问题 | 修复代价 |
|--------|------|----------|
| **P0** | 就绪循环 `%FILE_HOST%`/`%FILE_PORT%` 应改为 `!FILE_HOST!`/`!FILE_PORT!`（第 178-179 行） | 改 3 行 |
| **P1** | plan A3 需扩展范围：Python 侧 `_query_process_executable_path` 和 `_list_aps_chrome_pids` 仍用 wmic | 增加 plan 条目 |
| **P1** | plan A6 应简化为单一 tasklist 方案，去掉 PowerShell/profile锁 双路径 | 精简 plan 条目 |
| **P2** | plan A4 需补充中文镜像名的具体策略 | 补充 plan 说明 |
| **P2** | `_list_aps_chrome_pids` 的 `except: return []` 应改为显式降级 + 返回 False | 改 ~10 行 |

### plan 的正确之处

- 5 个分叉点的识别全部准确，无虚报
- "必须保持不变的兼容面"约束设计合理
- 浏览器 profile 可写性校验（A5）设计简洁正确
- 运行时契约 owner 反转义（A2）方向正确
- 批处理 wmic → tasklist（A3）方向正确，只是范围不够
- 打包链路补浏览器冒烟（B1）方向正确
- 静态守卫（C1）设计合理

### 建议实施顺序

1. **紧急**：修复就绪循环的 `%` → `!` BUG（3 行改动，可立即合并）
2. 修正 plan：扩展 A3 范围、简化 A6、补充 A4 策略
3. 按修正后的 plan 顺序实施 A1 → A2 → A3（含 Python） → A4 → A5 → A6 → B1 → C1-C3

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnnxdmxt-kxqde7",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T01:21:25.929Z",
  "finalizedAt": "2026-04-07T01:21:25.929Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "APS启动链路修复plan与代码实现三轮深度审查",
    "date": "2026-04-07",
    "overview": "对照修复plan逐项审查启动器、打包脚本、运行时入口和测试文件的当前实现状态，验证plan是否被正确落地，定位遗漏与潜在BUG"
  },
  "scope": {
    "markdown": "# APS启动链路修复plan与代码实现三轮深度审查\n\n- 日期：2026-04-07\n- 范围：`assets/启动_排产系统_Chrome.bat`、`web/bootstrap/launcher.py`、`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`、`tests/test_win7_launcher_runtime_paths.py`、`validate_dist_exe.py`、`DELIVERY_WIN7.md`、`installer/README_WIN7_INSTALLER.md`\n- 目标：三轮审查——第一轮验证plan识别的问题是否真实存在于代码中；第二轮审查plan的方案完整性与遗漏点；第三轮审查实现是否优雅、是否有过度兜底、静默回退或BUG\n\n## 审查上下文\n\n本次审查基于 `.limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md` 作为待验证蓝图，对照工作区中的实际代码与文档，检查该plan是否已被正确实施、方案本身是否存在盲点。"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查总结\n\n本次审查以 `.limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md` 为蓝图，对照工作区实际代码逐项核实、逆向验证、深度排查。共发现 **5 个问题**（2 高 / 3 中），其中 plan 识别的 5 个分叉点全部实证确认，但同时发现了 plan 完全遗漏的 1 个严重 BUG 和 3 个方案层面的缺陷。\n\n### plan 尚未实施\n\n**plan 中列出的所有改动项（A1-A6、B1-B2、C1-C3）均未在代码中落地。** 当前工作区中的 `启动_排产系统_Chrome.bat`、`package_win7.ps1`、`test_win7_launcher_runtime_paths.py` 等文件仍处于修改前的状态。plan 只是一份蓝图，不是已完成的实施。\n\n### 必须在实施前修正的问题\n\n| 优先级 | 问题 | 修复代价 |\n|--------|------|----------|\n| **P0** | 就绪循环 `%FILE_HOST%`/`%FILE_PORT%` 应改为 `!FILE_HOST!`/`!FILE_PORT!`（第 178-179 行） | 改 3 行 |\n| **P1** | plan A3 需扩展范围：Python 侧 `_query_process_executable_path` 和 `_list_aps_chrome_pids` 仍用 wmic | 增加 plan 条目 |\n| **P1** | plan A6 应简化为单一 tasklist 方案，去掉 PowerShell/profile锁 双路径 | 精简 plan 条目 |\n| **P2** | plan A4 需补充中文镜像名的具体策略 | 补充 plan 说明 |\n| **P2** | `_list_aps_chrome_pids` 的 `except: return []` 应改为显式降级 + 返回 False | 改 ~10 行 |\n\n### plan 的正确之处\n\n- 5 个分叉点的识别全部准确，无虚报\n- \"必须保持不变的兼容面\"约束设计合理\n- 浏览器 profile 可写性校验（A5）设计简洁正确\n- 运行时契约 owner 反转义（A2）方向正确\n- 批处理 wmic → tasklist（A3）方向正确，只是范围不够\n- 打包链路补浏览器冒烟（B1）方向正确\n- 静态守卫（C1）设计合理\n\n### 建议实施顺序\n\n1. **紧急**：修复就绪循环的 `%` → `!` BUG（3 行改动，可立即合并）\n2. 修正 plan：扩展 A3 范围、简化 A6、补充 A4 策略\n3. 按修正后的 plan 顺序实施 A1 → A2 → A3（含 Python） → A4 → A5 → A6 → B1 → C1-C3",
    "recommendedNextAction": "立即修复 P0（就绪循环变量展开 BUG），然后修正 plan 的 A3/A4/A6 范围，最后按修正后的 plan 依序实施。",
    "reviewedModules": [
      "assets/启动_排产系统_Chrome.bat",
      "web/bootstrap/launcher.py",
      ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
      "validate_dist_exe.py",
      "tests/test_win7_launcher_runtime_paths.py",
      ".limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md",
      "DELIVERY_WIN7.md",
      "installer/README_WIN7_INSTALLER.md"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 5,
    "severity": {
      "high": 2,
      "medium": 3,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "R1",
      "title": "第一轮：plan所识别问题在代码中的实证核实",
      "status": "completed",
      "recordedAt": "2026-04-07T01:13:45.156Z",
      "summaryMarkdown": "逐项对照 plan 中标识的 5 个分叉点，在实际代码中验证其存在性与严重度。\n\n### 分叉点 1：运行时契约 owner 反转义缺失 — **已确认**\n\n`web/bootstrap/launcher.py` 第 602-603 行通过 `json.dump(payload, f, ensure_ascii=False, ...)` 写出 `aps_runtime.json`。当 `owner` 值为 `DOMAIN\\user` 时，JSON 规范要求序列化为 `\"DOMAIN\\\\user\"`（双反斜杠）。\n\n批处理 `assets/启动_排产系统_Chrome.bat` 第 451-456 行的 `:read_runtime_contract` 用 `findstr` + 文本替换提取 owner，只去掉了逗号和引号，**没有把 `\\\\` 还原为 `\\`**。因此 `CONTRACT_OWNER` 值为 `DOMAIN\\\\user`（双反斜杠），而 `CURRENT_OWNER`（第 15-17 行组装）是 `DOMAIN\\user`（单反斜杠）。第 366 行的 `if /I \"%CONTRACT_OWNER%\"==\"%CURRENT_OWNER%\"` 比较会失败，在契约回退路径下把同账户误判为异账户。\n\n**plan 识别正确。**\n\n### 分叉点 2：锁文件进程探测仍依赖 wmic — **已确认**\n\n`assets/启动_排产系统_Chrome.bat` 第 502-525 行 `:lock_is_active` 完全使用 `where wmic` + `wmic process where \"ProcessId=...\"` 判断进程是否存活。而 `web/bootstrap/launcher.py` 第 305-332 行 `_pid_exists` 已经改为 `tasklist /FI \"PID eq ...\" /NH /FO CSV`。\n\n在 Win10 22H2+ 上 `wmic` 可能已不存在，此时批处理会将 `LOCK_ACTIVE` 设为 `UNKNOWN`，最终走到 `:BLOCKED_UNCERTAIN`（第 208-213 行），阻止正常启动。\n\n**plan 识别正确。**\n\n### 分叉点 3：浏览器启动后无存活验证 — **已确认**\n\n`assets/启动_排产系统_Chrome.bat` 第 215-232 行 `:OPEN_CHROME` 在调用 `start` 后只检查 `ERRORLEVEL`，第 232 行直接 `exit /b 0`。脚本自身在第 221-222 行的注释中已承认\"不能证明 Chrome 启动后一定稳定运行\"。没有任何短时存活探测。\n\n**plan 识别正确。**\n\n### 分叉点 4：浏览器 profile 目录未校验可写性 — **已确认**\n\n第 137 行只有 `if not exist \"%CHROME_PROFILE_DIR%\" mkdir \"%CHROME_PROFILE_DIR%\" >nul 2>&1`，无论 `mkdir` 是否成功都会继续执行。没有临时探针文件写入/删除确认。\n\n**plan 识别正确。**\n\n### 分叉点 5：打包链路不覆盖浏览器运行时冒烟 — **已确认**\n\n`package_win7.ps1` 第 157-167 行 `Test-DistExeStartup` 只调用 `python validate_dist_exe.py`。`validate_dist_exe.py` 明确在注释中写明\"只验证主程序 exe 冷启动与 HTTP 页面，不覆盖快捷方式、批处理脚本、环境变量刷新时序或 Chrome 启动链路\"。`New-ChromeRuntimePayload`（第 211-258 行）构建裁剪后的运行时 payload 时仅检查 `chrome.exe` 存在，不执行任何可启动性验证。\n\n**plan 识别正确。**\n\n### 第一轮结论\n\nplan 标识的 5 个分叉点全部在实际代码中得到了实证确认，无虚报。",
      "conclusionMarkdown": "plan 标识的 5 个分叉点全部经代码实证确认存在，问题描述准确，无虚报。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 451,
          "lineEnd": 456,
          "symbol": "read_runtime_contract owner提取"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 502,
          "lineEnd": 525,
          "symbol": "lock_is_active wmic"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 215,
          "lineEnd": 232,
          "symbol": "OPEN_CHROME无存活验证"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 137,
          "lineEnd": 137,
          "symbol": "CHROME_PROFILE_DIR仅mkdir"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 305,
          "lineEnd": 332,
          "symbol": "_pid_exists使用tasklist"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 602,
          "lineEnd": 603,
          "symbol": "json.dump写owner"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 157,
          "lineEnd": 167,
          "symbol": "Test-DistExeStartup仅覆盖后端"
        },
        {
          "path": "validate_dist_exe.py",
          "lineStart": 1,
          "lineEnd": 16,
          "symbol": "验收范围声明"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "web/bootstrap/launcher.py",
        ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
        "validate_dist_exe.py"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    },
    {
      "id": "R2",
      "title": "第二轮：plan方案完整性与遗漏审查",
      "status": "completed",
      "recordedAt": "2026-04-07T01:15:22.378Z",
      "summaryMarkdown": "第二轮审查聚焦 plan 方案本身的完整性，发现 3 个显著问题：\n\n### 遗漏 1：Python 侧 wmic 残留未纳入修复范围 — **高风险**\n\nplan 声称\"Python 侧已改为 tasklist\"并据此只修改批处理。但实际上 `launcher.py` 中仍有两个函数直接依赖 `wmic`：\n\n- `_query_process_executable_path`（第 742-769 行）：被锁的活跃性判断和停机链路使用。当 `wmic` 不可用时返回 `None`，导致失败闭合（安全但可能误阻）。\n- `_list_aps_chrome_pids`（第 806-839 行）：被浏览器清理链路使用。当 `wmic` 不可用时返回空列表，**导致浏览器进程静默不清理**——这不是失败闭合，是静默回退。\n\nplan 只修批处理的 `:lock_is_active`，反而会造成\"bat 用 tasklist，Python 用 wmic\"的**新不一致**。\n\n### 遗漏 2：主程序短时存活探测的中文镜像名兼容性\n\nplan A4 要求\"从 `APP_EXE` 解析镜像名，用 `tasklist` 做短时存在性判断\"，但没有考虑 `排产系统.exe` 是中文镜像名。在 Win7 默认代码页下，`tasklist /FI \"IMAGENAME eq 排产系统.exe\"` 可能无法正确匹配。plan 没有给出中文镜像名场景下的具体策略。\n\n### 过度设计：浏览器存活探测的双路径方案\n\nplan A6 设计了\"PowerShell 主路径 + tasklist+profile锁降级路径\"的复杂两段式探测。但：\n- PowerShell 路径本质上仍是 WMI 查询，会增加 1-2 秒延迟\n- 降级路径的\"profile 锁痕迹\"没有具体口径\n- 当 PowerShell 不可用且无法区分 APS Chrome 时，会对每次启动都弹告警——过度警告\n\n更简洁的方案是：等 2-3 秒后用 `tasklist` 检查 `chrome.exe` 是否存在。不存在则 `pause` 报错。存在则合理假设成功。这能覆盖\"Chrome 完全没启动\"这一核心用户反馈场景。\n\n### 其他观察\n\n- plan C1 的静态守卫设计是合理的，但现有测试文件 `test_win7_launcher_runtime_paths.py` 已有 `test_launcher_bat_contains_json_health_probe_and_owner_fallback()` 在做类似的文本断言，新增守卫应与之统一风格。\n- plan B2 关于\"文档中明确 `validate_dist_exe.py` 只覆盖后端\"——`DELIVERY_WIN7.md` 第 91 行和 `installer/README_WIN7_INSTALLER.md` 第 248 行已经有此声明，无需重复补充。\n- plan \"必须保持不变的兼容面\"部分很好，明确了不改 `contract_version`、不改字段名、不改 profile 目录名，是合理的约束。",
      "conclusionMarkdown": "plan 方案整体方向正确，但存在 3 个显著遗漏和 2 个过度设计风险，需要在实施前修正。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 742,
          "lineEnd": 769,
          "symbol": "_query_process_executable_path 使用wmic"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 806,
          "lineEnd": 839,
          "symbol": "_list_aps_chrome_pids 使用wmic"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 362,
          "lineEnd": 377,
          "symbol": "_is_runtime_lock_active pid_match判断"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 905,
          "lineEnd": 918,
          "symbol": "stop_runtime_from_dir pid_match判断"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 132,
          "lineEnd": 202,
          "symbol": "静态守卫现状"
        }
      ],
      "reviewedModules": [
        "web/bootstrap/launcher.py",
        "tests/test_win7_launcher_runtime_paths.py",
        ".limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md"
      ],
      "recommendedNextAction": "实施前先修正 plan：1）把 Python 侧 `_query_process_executable_path` 和 `_list_aps_chrome_pids` 的 wmic 迁移纳入 A3 范围；2）简化 A6 为单一 tasklist 方案；3）补充主程序短时存活探测的镜像名提取策略说明。",
      "findingIds": [
        "python-wmic-residual",
        "app-spawn-imagename-cjk",
        "a6-overengineered"
      ]
    },
    {
      "id": "R3",
      "title": "第三轮：现有代码BUG与静默回退深度排查",
      "status": "completed",
      "recordedAt": "2026-04-07T01:20:53.366Z",
      "summaryMarkdown": "第三轮审查深入逐行检查代码逻辑，发现了 plan 和前两轮 review 都完全未提及的关键 BUG 与静默回退：\n\n### 严重 BUG：就绪检测循环的变量展开方式错误\n\n`assets/启动_排产系统_Chrome.bat` 第 162-189 行的 `for /l` 就绪检测循环中，第 178-179 行：\n\n```bat\nset \"HOST=%FILE_HOST%\"\nset \"PORT=%FILE_PORT%\"\n```\n\n使用了 `%`（解析时展开），而不是 `!`（运行时展开）。脚本第 5 行已启用 `EnableDelayedExpansion`，但此处没有利用。\n\n`FILE_HOST` 和 `FILE_PORT` 是在循环体内由 `call :read_host_file` 和 `call :read_port_file` 在运行时设置的。但整个 `for /l (...)` 块在解析时就把 `%FILE_HOST%` 展开了——此时这两个变量尚未定义，展开结果为空字符串。\n\n因此每次循环迭代中：\n1. `set \"HOST=\"` 和 `set \"PORT=\"` 被执行（HOST/PORT 被清空）\n2. `probe_health` 检查到 PORT 为空后直接返回，不执行健康检查\n3. `is_port_listening` 用空 PORT 拼接 `findstr` 模式，无法匹配任何监听端口\n4. 就绪检测永远不会成功\n5. 循环必定跑完 45 次迭代后走到超时路径\n\n**影响**：每次\"首次启动\"（不走复用路径的场景）都会等待 45 秒后显示 `\"App did not become ready in time\"` 并 `pause`。只有通过 `try_reuse_existing` → `CAN_REUSE_EXISTING` 的路径（已有运行实例时）才能正常工作。\n\n同样的问题影响第 166 行 `call :log launch_error=\"%LAUNCH_ERROR%\"`（日志写入空值，但控制台输出第 167 行用了 `!LAUNCH_ERROR!` 所以正确）。\n\n### 中风险：Python 侧浏览器清理在无 wmic 时静默\"成功\"\n\n`launcher.py` 的 `stop_aps_chrome_processes`（第 842-856 行）调用 `_list_aps_chrome_pids`（第 806-839 行）。当 `wmic` 不可用时，后者在 `except Exception: return []` 静默返回空列表。前者遍历空列表后直接返回 `True`（表示成功）。调用方——安装器卸载链路和 `--runtime-stop --stop-aps-chrome`——会以为浏览器已关闭，但实际上 Chrome 进程仍在运行。\n\n### 该 BUG 与用户反馈的关系\n\n第 178-179 行的 BUG **不是**导致\"CMD 闪一下就关\"的直接原因——超时路径会 `pause`，不会闪退。用户反馈的闪退仍然指向 plan 中已识别的问题（Chrome 启动后无存活验证，`start` 成功后 `exit /b 0`）。但此 BUG 意味着\"首次启动\"场景根本无法正常工作，是一个独立的严重缺陷。",
      "conclusionMarkdown": "第三轮审查发现一个**严重 BUG**（就绪检测循环中的变量展开错误导致首次启动必定超时 45 秒）和一个中风险的静默回退（Python 侧浏览器清理在无 wmic 时静默失效），两者均被 plan 完全遗漏。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 162,
          "lineEnd": 189,
          "symbol": "for就绪循环变量展开BUG"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 178,
          "lineEnd": 179,
          "symbol": "%FILE_HOST%和%FILE_PORT%应用!!"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 166,
          "lineEnd": 167,
          "symbol": "%LAUNCH_ERROR%应用!!"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 842,
          "lineEnd": 857,
          "symbol": "stop_aps_chrome_processes静默失效"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat"
      ],
      "recommendedNextAction": "紧急修复就绪循环的 `%` → `!` 变量展开BUG（影响首次启动体验），然后再按修正后的 plan 实施其他改进。",
      "findingIds": [
        "readiness-loop-percent-vs-bang",
        "chrome-cleanup-silent-noop"
      ]
    }
  ],
  "findings": [
    {
      "id": "python-wmic-residual",
      "severity": "high",
      "category": "other",
      "title": "Python 侧仍有两处 wmic 硬依赖被 plan 漏掉",
      "descriptionMarkdown": "plan 第 A3 节声称\"Python 侧已改为 tasklist\"，并据此只修改批处理的 `:lock_is_active`。但实际上 `web/bootstrap/launcher.py` 中仍有两个函数直接依赖 `wmic`：\n\n1. `_query_process_executable_path`（第 751 行）：通过 `wmic process where processid=... get ExecutablePath` 查询进程可执行路径，被 `_pid_matches_contract` → `_is_runtime_lock_active` → `acquire_runtime_lock` 以及 `stop_runtime_from_dir` 调用。当 `wmic` 不可用时返回 `None`，导致 `_pid_matches_contract` 返回 `None`，进而使 `_is_runtime_lock_active` 采用失败闭合策略直接认为锁仍活跃——安全但可能造成误阻。\n\n2. `_list_aps_chrome_pids`（第 813 行）：通过 `wmic process where Name='chrome.exe' and CommandLine like '%marker%'` 枚举 APS 专用浏览器进程。被 `stop_aps_chrome_processes` → `stop_runtime_from_dir` 和安装器卸载链路调用。当 `wmic` 不可用时返回空列表，浏览器进程不会被清理——**这是静默失败，不是失败闭合**。\n\nplan 只修批处理不修 Python，会造成\"bat 用 tasklist 判断存活、Python 用 wmic 判断可执行路径\"的新不一致。",
      "recommendationMarkdown": "把 `_query_process_executable_path` 改用 PowerShell `Get-Process -Id ... | Select-Object Path` 或 `tasklist /FI \"PID eq ...\" /V /FO CSV`（后者在 Win7 上可获取镜像名但不一定能获取完整路径）。`_list_aps_chrome_pids` 改用 PowerShell `Get-WmiObject Win32_Process` 或 `wmic` 降级 + `tasklist` 主路径的组合方案。两者都需要处理 wmic 不可用时的降级，且不能像现在一样静默返回空列表。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 742,
          "lineEnd": 769,
          "symbol": "_query_process_executable_path"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 806,
          "lineEnd": 839,
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
      "id": "app-spawn-imagename-cjk",
      "severity": "medium",
      "category": "other",
      "title": "主程序短时存活探测的中文镜像名兼容性未考虑",
      "descriptionMarkdown": "plan A4 要求\"从 `APP_EXE` 解析镜像名，用 `tasklist` 做一次短时存在性判断\"。但批处理中 `APP_EXE` 是通过第 20-24 行 `for %%F in (*.exe)` 遍历得到的完整路径，例如 `C:\\Program Files\\APS\\SchedulerApp\\排产系统.exe`。提取镜像名需要 `%%~nxF` 风格的操作，但在 `:OPEN_CHROME` 之后的 subroutine 中不能直接用 `for` 变量语法。\n\n更大的问题是：`tasklist` 筛选 `IMAGENAME` 时，中文镜像名（`排产系统.exe`）在非 UTF-8 代码页下可能无法匹配。plan A1 提出加 `chcp 65001`，但 `chcp 65001` 在 Win7 上对 `tasklist` 的影响不确定——Win7 的 `tasklist` 可能不支持 UTF-8 镜像名筛选。\n\nplan 没有说明这个中文镜像名场景下的具体策略，可能导致实施者在此处卡住或做出不可靠的实现。",
      "recommendationMarkdown": "考虑不按镜像名筛选，而是在 `start` 后通过 `for /f` 捕获 PID（例如用 `wmic process call create` 或 PowerShell 的 `Start-Process -PassThru`），然后按 PID 做 `tasklist` 精确匹配。或者简化为：`start` 后等待 2 秒，再检查 `aps_launch_error.txt` 是否出现。",
      "evidence": [],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "a6-overengineered",
      "severity": "medium",
      "category": "other",
      "title": "plan A6 浏览器存活探测方案过度设计",
      "descriptionMarkdown": "plan A6 设计了\"两段式短时探测\"和\"PowerShell 主路径 + tasklist 降级路径\"的复杂组合方案。但实际场景中：\n\n1. PowerShell 侧需要 `Win32_Process` + 命令行筛选——本质上仍是 WMI 查询，只是通过 PowerShell 调用而非直接 `wmic`。在 Win7 上可靠，但会增加约 1-2 秒的 PowerShell 启动延迟。\n2. 降级路径的\"浏览器镜像存在性 + profile 锁痕迹\"组合判断没有给出具体实现口径——什么是\"profile 锁痕迹\"？是 `CHROME_PROFILE_DIR\\\\SingletonLock`、`CHROME_PROFILE_DIR\\\\lockfile` 还是 `Local State` 的修改时间？不同版本的 Chrome/Chromium 使用不同的锁机制。\n3. plan 还要求\"不允许继续静默成功，应提示用户查看 launcher.log\"，但如果 PowerShell 不可用、tasklist 也无法区分 APS Chrome 和用户 Chrome，就会对每次成功启动都弹出\"无法确认\"提示——这是过度警告。\n\n相比之下，一个更简洁的方案是：`start` Chrome 后等 2 秒，用 `tasklist /FI \"IMAGENAME eq chrome.exe\"` 确认有 `chrome.exe` 进程存在。如果没有，说明 Chrome 完全没启动，应 `pause` 报错。如果有，合理假设 APS Chrome 已启动（因为刚刚调用了 `start`）。这个方案不能区分 APS Chrome 和用户已打开的 Chrome，但\"Chrome 完全不存在\"的极端场景（用户同时没开任何 Chrome）已能覆盖当前用户反馈的核心问题。",
      "recommendationMarkdown": "简化 A6 为单一策略：`start` Chrome 后等 2-3 秒，用 `tasklist` 检查 `chrome.exe` 是否存在。若不存在则 `pause` 报错并输出 `launcher.log` 路径与 `chrome_cmd`。不再设计 PowerShell 主/降级双路径，避免批处理复杂度爆炸。",
      "evidence": [],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "readiness-loop-percent-vs-bang",
      "severity": "high",
      "category": "javascript",
      "title": "就绪循环变量展开方式错误导致首次启动必定超时",
      "descriptionMarkdown": "启动器第 5 行已启用 `EnableDelayedExpansion`，但第 162-189 行的 `for /l` 就绪循环内部的第 178-179 行使用了 `%FILE_HOST%` 和 `%FILE_PORT%`（解析时展开），而不是 `!FILE_HOST!` 和 `!FILE_PORT!`（运行时展开）。\n\n`FILE_HOST` 和 `FILE_PORT` 是由 `for` 循环体内的 `call :read_host_file` 和 `call :read_port_file` 在运行时设置的。但整个 `for /l` 块在解析时会把 `%FILE_HOST%` 展开为其当前值——在循环开始前，这两个变量未定义，因此展开为空字符串。\n\n实际后果：\n- `set \"HOST=%FILE_HOST%\"` → `set \"HOST=\"`（清空 HOST）\n- `set \"PORT=%FILE_PORT%\"` → `set \"PORT=\"`（清空 PORT）\n- `probe_health` 检查到 PORT 为空后直接返回，HEALTH_OK 始终未设置\n- `is_port_listening` 用空 PORT 拼接 `findstr` 模式，无法匹配任何监听端口\n- 就绪检测永远不会成功，循环必定跑完 45 次迭代后走到超时错误路径\n\n这意味着：**每次首次启动都会等待 45 秒后显示\"App did not become ready in time\"并 `pause`**。只有复用已有实例的路径（`try_reuse_existing` → `CAN_REUSE_EXISTING`）能正常跳过此循环。\n\n同样的问题也影响第 166 行：`call :log launch_error=\"%LAUNCH_ERROR%\"` 会把空值写入日志（尽管第 167 行 `echo [launcher] !LAUNCH_ERROR!` 的控制台输出是正确的）。",
      "recommendationMarkdown": "将第 178 行改为 `set \"HOST=!FILE_HOST!\"`，第 179 行改为 `set \"PORT=!FILE_PORT!\"`，第 166 行改为 `call :log launch_error=\"!LAUNCH_ERROR!\"`。这是经典的批处理延迟展开问题，且脚本已启用 `EnableDelayedExpansion`，只需把 `%` 换成 `!` 即可。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 162,
          "lineEnd": 189,
          "symbol": "for就绪循环"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 178,
          "lineEnd": 179,
          "symbol": "%FILE_HOST%和%FILE_PORT%"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 166,
          "lineEnd": 167,
          "symbol": "%LAUNCH_ERROR%"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "chrome-cleanup-silent-noop",
      "severity": "medium",
      "category": "other",
      "title": "Python 侧浏览器清理在无 wmic 时静默失效",
      "descriptionMarkdown": "`launcher.py` 第 842-856 行的 `stop_aps_chrome_processes` 调用 `_list_aps_chrome_pids`（第 806-839 行）枚举 APS 专用浏览器进程。当 `wmic` 不可用时，`_list_aps_chrome_pids` 在第 826-827 行 `except Exception: return []` 静默返回空列表，`stop_aps_chrome_processes` 返回 `True`（表示成功）。\n\n这不是失败闭合，是**静默回退**。调用方（安装器卸载链路、`--runtime-stop --stop-aps-chrome`）会以为浏览器已成功关闭，但实际上 Chrome 进程仍在运行。在无 wmic 的 Win10+ 环境下，卸载后 Chrome 进程会残留。",
      "recommendationMarkdown": "在 `_list_aps_chrome_pids` 中增加 wmic 不可用时的降级方案（例如 PowerShell `Get-CimInstance Win32_Process`），并且当所有方案都不可用时，`stop_aps_chrome_processes` 应返回 `False` 并记录警告，而不是静默返回 `True`。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 842,
          "lineEnd": 857,
          "symbol": "stop_aps_chrome_processes"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 806,
          "lineEnd": 839,
          "symbol": "_list_aps_chrome_pids"
        },
        {
          "path": "web/bootstrap/launcher.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:4996f5bbe4b350c6f1f33d2223879c24a0cd8f5891e2bdc7f5a062fe78b3ddeb",
    "generatedAt": "2026-04-07T01:21:25.929Z",
    "locale": "zh-CN"
  }
}
```
