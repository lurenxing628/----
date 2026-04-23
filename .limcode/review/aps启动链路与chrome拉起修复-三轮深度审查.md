# APS启动链路与Chrome拉起修复-三轮深度审查
- 日期: 2026-04-07
- 概述: 对APS启动链路与Chrome拉起修复plan所涉及的全部未提交修改进行三轮深度审查，覆盖启动批处理、Python运行时入口、打包脚本、安装器、测试与文档。
- 状态: 已完成
- 总体结论: 通过

## 评审范围

# APS启动链路与Chrome拉起修复 - 三轮深度审查

- 日期：2026-04-07
- 范围：启动批处理(`assets/启动_排产系统_Chrome.bat`)、Python运行时入口(`web/bootstrap/launcher.py`)、打包脚本(`package_win7.ps1`)、安装器(`aps_win7_chrome.iss`)、测试(`test_win7_launcher_runtime_paths.py`)、文档(`DELIVERY_WIN7.md`、`README_WIN7_INSTALLER.md`)
- 目标：审查本轮未提交修改是否达成plan目标、实现是否优雅简洁、有无过度兜底/静默回退、逻辑是否严谨、是否存在遗留BUG

## 审查口径

本次审查聚焦以下五项plan交付承诺：
1. P0：首次启动不再因延迟展开BUG固定等待45秒
2. P1：收口owner反转义、锁探测、主程序短时存活与profile可写性
3. P2：替换残留wmic并消除浏览器清理静默回退
4. P3：为package_win7.ps1增加浏览器运行时最小冒烟
5. P4：文档与验收清单同步

## 评审摘要

- 当前状态: 已完成
- 已审模块: assets/启动_排产系统_Chrome.bat, web/bootstrap/launcher.py, .limcode/skills/aps-package-win7/scripts/package_win7.ps1, installer/aps_win7_chrome.iss, tests/test_win7_launcher_runtime_paths.py, tests/regression_shared_runtime_state.py, DELIVERY_WIN7.md, installer/README_WIN7_INSTALLER.md, web/bootstrap/entrypoint.py, tests/regression_runtime_contract_launcher.py, tests/regression_runtime_stop_cli.py
- 当前进度: 已记录 5 个里程碑；最新：M5
- 里程碑总数: 5
- 已完成里程碑: 5
- 问题总数: 4
- 问题严重级别分布: 高 0 / 中 0 / 低 4
- 最新结论: 经第五轮引用链复核与回归验证，打包脚本清理语义与安装器 Chrome marker 口径两条接受风险均已完成代码收口；启动、契约、停机与卸载清理主链路回归全部通过。本 review 可按“已接受并完成收口”结束。
- 下一步建议: 当前无需继续跟踪本次两条风险；后续若再改 profile 命名或浏览器清理协议，继续按同一口径同步四处实现。
- 总体结论: 通过

## 评审发现

### 冒烟清理语义依赖调用点容错

- ID: ps1-cleanup-throw-in-finally
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: M2, M4, M5
- 说明:

  复核 `Invoke-ChromeRuntimeSmoke -> Stop-ProcessTreeByIds` 调用链后确认，`Stop-ProcessTreeByIds` 当前只在 `finally` 内的局部 `try/catch` 中调用，现状并不会把 `taskkill` 非零返回泄露为出包失败。原先“会不必要地中断出包”的判断偏重。实际风险仅在于严格 helper 的语义与 best-effort 清理语义分散在调用点，后续维护者若重构时忽略这一层包装，才可能引入行为变化。
- 建议:

  当前无需为此阻断；如后续继续打磨，可在 helper 名称、注释或额外 wrapper 上显式表达“严格停止”和“容错清理”的语义差异。
- 证据:
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:244-255#Stop-ProcessTreeByIds`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:316-325#finally cleanup`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:244-255#Stop-ProcessTreeByIds`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:316-325#Invoke-ChromeRuntimeSmoke finally`
  - `assets/启动_排产系统_Chrome.bat`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `installer/aps_win7_chrome.iss`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/regression_runtime_stop_cli.py`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:244-329#Stop-ProcessTreeByIds 与 Stop-ProcessTreeByIdsBestEffort`
  - `tests/test_win7_launcher_runtime_paths.py:202-215#best-effort wrapper 守卫`

### Chrome 进程枚举策略相似但口径未统一

- ID: cross-lang-chrome-enum-sync
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: M2, M4, M5
- 说明:

  复核 `_list_aps_chrome_pids`、`Get-ChromeIdsByMarker` 与安装器卸载脚本后确认：三处都使用命令行 marker + `Get-CimInstance -> Get-WmiObject` 降级链，但 marker 并不完全一致。Python 与打包脚本按完整 profile 路径匹配；安装器仅按固定子串 `chrome109profile` 匹配。因此原先“完全一致但代码重复”的说法不准确。真实风险是未来如果调整 marker 口径或 profile 命名，三处都要同步考虑，否则可能出现覆盖范围不一致。
- 建议:

  作为接受风险在文档中留痕：三处进程枚举策略必须同步修改。当前阶段不需要强制统一实现。
- 证据:
  - `web/bootstrap/launcher.py`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `installer/aps_win7_chrome.iss`
  - `web/bootstrap/launcher.py:832-856#_list_aps_chrome_pids marker=完整 profile 路径`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:201-241#Get-ChromeIdsByMarker marker=完整 profile 路径`
  - `installer/aps_win7_chrome.iss:58-72#BuildStopChromePowerShellParams marker=chrome109profile`
  - `assets/启动_排产系统_Chrome.bat`
  - `web/bootstrap/entrypoint.py`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/regression_runtime_stop_cli.py`
  - `installer/aps_win7_chrome.iss:56-100#CurrentUserChromeProfilePath 与 BuildStopChromePowerShellParams`
  - `web/bootstrap/launcher.py:514-518#default_chrome_profile_dir`
  - `assets/启动_排产系统_Chrome.bat:57-62#批处理默认 profile 路径`
  - `tests/test_win7_launcher_runtime_paths.py:86-272#profile 路径与 installer marker 守卫`

### `ps1-cleanup-throw-in-finally` 已修复

- ID: F-ps1-cleanup-throw-in-finally-已修复
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M5
- 证据:
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `installer/aps_win7_chrome.iss`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `assets/启动_排产系统_Chrome.bat`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_stop_cli.py`

### `cross-lang-chrome-enum-sync` 已修复

- ID: F-cross-lang-chrome-enum-sync-已修复
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M5
- 证据:
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `installer/aps_win7_chrome.iss`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `assets/启动_排产系统_Chrome.bat`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_stop_cli.py`

## 评审里程碑

### M1 · 第一轮：启动批处理与Python运行时入口审查

- 状态: 已完成
- 记录时间: 2026-04-07T02:15:16.921Z
- 已审模块: assets/启动_排产系统_Chrome.bat, web/bootstrap/launcher.py
- 摘要:

  ## 第一轮审查：启动批处理与Python运行时入口

  ### 1. P0 延迟展开修复 — ✅ 已达成

  **bat就绪循环（第184-204行）**：
  - `set "HOST=!FILE_HOST!"` 和 `set "PORT=!FILE_PORT!"` 已正确使用延迟展开语法
  - `call :log launch_error="!LAUNCH_ERROR!"` 也已使用延迟展开
  - 测试文件第171-173行有对应静态守卫断言

  评价：修复简洁直接，没有过度改造，只改了必须改的三处。

  ### 2. P1.1 owner反转义 — ✅ 已达成，但有一处值得注意

  **`:normalize_contract_owner`子程序（第540-547行）**：
  ```bat
  set "CONTRACT_OWNER=!CONTRACT_OWNER:\\=\!"
  ```
  这行把JSON中的 `\\` 还原为 `\`。逻辑正确——Python侧 `json.dump` 会把 `DOMAIN\user` 写成 `DOMAIN\\user`，而bat侧当前账户值是 `DOMAIN\user`，所以需要反转义。

  **潜在问题**：plan提到"如实现成本可控，再补 `\"` 与 `\/` 的最小兼容"，当前只处理了 `\\`→`\`。考虑到owner值只含域名和用户名，不会出现 `\"` 或 `\/`，这个范围是合理的。

  ### 3. P1.2 锁探测替换wmic — ✅ 已达成

  **`:lock_is_active`子程序（第549-581行）**：
  - 使用 `tasklist /FI "PID eq !LOCK_PID!" /NH /FO CSV` 替代了wmic
  - 输出写到临时文件再逐行解析，避免管道中的延迟展开问题
  - PID格式先做正则校验（`^[0-9][0-9]*$`），非法PID直接走UNKNOWN而不是误判不活跃
  - `tasklist` 命令失败时设 `LOCK_ACTIVE=UNKNOWN` 保持失败闭合

  **潜在问题1**：临时文件命名用 `%RANDOM%_%RANDOM%`，在极端并发场景下仍有碰撞概率。但考虑到APS本身是单活用户设计，这个风险可忽略。

  **潜在问题2**：第575行 `echo !LOCK_QUERY_ROW! | findstr /C:",\"!LOCK_PID!\"," >nul` 对tasklist CSV输出做精确PID匹配。这个模式能区分 PID 123 与 PID 1234，因为CSV格式是 `"imagename","123","..."` 带引号和逗号的。逻辑正确。

  ### 4. P1.3 主程序短时存活探测 — ✅ 已达成

  **第167-181行**：
  - `start "" "%APP_EXE%"` 后立即 `timeout /t 2`
  - 然后检查 `aps_launch_error.txt` 是否生成
  - 如有明确错误文件，直接跳转到 `:APP_START_FAILED` 不再继续等待
  - 无错误才进入就绪循环

  **优点**：不依赖中文镜像名筛选，使用错误文件作为信号——这是最可靠的跨语言方案。

  ### 5. P1.4 profile可写性校验 — ✅ 已达成

  **`:probe_chrome_profile_dir`子程序（第589-605行）**：
  - 先尝试创建目录
  - 再写入探针文件 `aps_write_probe_{RANDOM}_{RANDOM}.tmp`
  - 写入失败则设 `CHROME_PROFILE_READY=` 为空
  - 主流程第146-151行检测到不可写后会 `pause` 并 `exit /b 10`

  **细节**：探针文件内容是 `> "%CHROME_PROFILE_PROBE_FILE%" echo APS`，简洁明了。删除用 `del /f /q` 且不检查结果——这里是合理的，因为探针文件只是临时文件。

  ### 6. P1.5 浏览器短时存活确认 — ✅ 已达成

  **`:probe_chrome_alive`子程序（第607-633行）**：
  - 用 `tasklist /FI "IMAGENAME eq chrome.exe" /NH /FO CSV` 检查是否存在chrome.exe
  - 等待3秒后检查
  - 不存在则设 `CHROME_ALIVE=` 为空
  - 主流程第260-268行检测到未存活后给出明确排障提示和 `pause`

  **注意**：正如plan所述，这个检查无法区分APS专用浏览器和普通Chrome，但能覆盖"Chrome完全没启动仍静默成功"这个核心场景。

  ### 7. Python侧 `_query_process_executable_path` — ✅ 已改为PowerShell

  **第765-795行**：
  - 使用 `Get-Process -Id $pid0` 读取进程路径
  - 返回 `None` 表示查询失败（保持失败闭合），返回空字符串表示进程存在但无路径
  - 不再依赖wmic

  ### 8. Python侧 `_list_aps_chrome_pids` — ✅ 已改为PowerShell，不再静默成功

  **第832-878行**：
  - 使用 `Get-CimInstance` → `Get-WmiObject` 降级链
  - 所有枚举方案都失败时返回 `None`（而非空列表）
  - 调用方 `stop_aps_chrome_processes`（第881-902行）检测到 `None` 时 `return False`
  - `_stop_aps_chrome_if_requested` 把 `False` 传播出去

  ### 逻辑严谨性总评

  - 批处理错误码覆盖：0(成功)、1(exe未找到)、2(Chrome未找到)、3(超时)、4(APS_CHROME_EXE无效)、5(Chrome start失败)、6(app启动失败)、7(日志目录不可写)、8(其他用户占用)、9(不确定归属)、10(profile不可写)、11(Chrome未存活) — 编号没有重叠，语义清晰
  - 没有发现新增的静默回退或过度兜底
  - 所有失败路径都有日志输出和 `pause` 阻止窗口闪退
- 结论:

  ## 第一轮审查：启动批处理与Python运行时入口 ### 1. P0 延迟展开修复 — ✅ 已达成 **bat就绪循环（第184-204行）**： - `set "HOST=!FILE_HOST!"` 和 `set "PORT=!FILE_PORT!"` 已正确使用延迟展开语法 - `call :log launch_error="!LAUNCH_ERROR!"` 也已使用延迟展开 - 测试文件第171-173行有对应静态守卫断言 评价：修复简洁直接，没有过度改造，只改了必须改的三处。 ### 2. P1.1 owner反转义 — ✅ 已达成，但有一处值得注意 **`:normalize_contract_owner`子程序（第540-547行）**： ```bat set "CONTRACT_OWNER=!CONTRACT_OWNER:\\=\!" ``` 这行把JSON中的 `\\` 还原为 `\`。逻辑正确——Python侧 `json.dump` 会把 `DOMAIN\user` 写成 `DOMAIN\\user`，而bat侧当前账户值是 `DOMAIN\user`，所以需要反转义。 **潜在问题**：plan提到"如实现成本可控，再补 `\"` 与 `\/` 的最小兼容"，当前只处理了 `\\`→`\`。考虑到owner值只含域名和用户名，不会出现 `\"` 或 `\/`，这个范围是合理的。 ### 3. P1.2 锁探测替换wmic — ✅ 已达成 **`:lock_is_active`子程序（第549-581行）**： - 使用 `tasklist /FI "PID eq !LOCK_PID!" /NH /FO CSV` 替代了wmic - 输出写到临时文件再逐行解析，避免管道中的延迟展开问题 - PID格式先做正则校验（`^[0-9][0-9]*$`），非法PID直接走UNKNOWN而不是误判不活跃 - `tasklist` 命令失败时设 `LOCK_ACTIVE=UNKNOWN` 保持失败闭合 **潜在问题1**：临时文件命名用 `%RANDOM%_%RANDOM%`，在极端并发场景下仍有碰撞概率。但考虑到APS本身是单活用户设计，这个风险可忽略。 **潜在问题2**：第575行 `echo !LOCK_QUERY_ROW! | findstr /C:",\"!LOCK_PID!\"," >nul` 对tasklist CSV输出做精确PID匹配。这个模式能区分 PID 123 与 PID 1234，因为CSV格式是 `"imagename","123","..."` 带引号和逗号的。逻辑正确。 ### 4. P1.3 主程序短时存活探测 — ✅ 已达成 **第167-181行**： - `start "" "%APP_EXE%"` 后立即 `timeout /t 2` - 然后检查 `aps_launch_error.txt` 是否生成 - 如有明确错误文件，直接跳转到 `:APP_START_FAILED` 不再继续等待 - 无错误才进入就绪循环 **优点**：不依赖中文镜像名筛选，使用错误文件作为信号——这是最可靠的跨语言方案。 ### 5. P1.4 profile可写性校验 — ✅ 已达成 **`:probe_chrome_profile_dir`子程序（第589-605行）**： - 先尝试创建目录 - 再写入探针文件 `aps_write_probe_{RANDOM}_{RANDOM}.tmp` - 写入失败则设 `CHROME_PROFILE_READY=` 为空 - 主流程第146-151行检测到不可写后会 `pause` 并 `exit /b 10` **细节**：探针文件内容是 `> "%CHROME_PROFILE_PROBE_FILE%" echo APS`，简洁明了。删除用 `del /f /q` 且不检查结果——这里是合理的，因为探针文件只是临时文件。 ### 6. P1.5 浏览器短时存活确认 — ✅ 已达成 **`:probe_chrome_alive`子程序（第607-633行）**： - 用 `tasklist /FI "IMAGENAME eq chrome.exe" /NH /FO CSV` 检查是否存在chrome.exe - 等待3秒后检查 - 不存在则设 `CHROME_ALIVE=` 为空 - 主流程第260-268行检测到未存活后给出明确排障提示和 `pause` **注意**：正如plan所述，这个检查无法区分APS专用浏览器和普通Chrome，但能覆盖"Chrome完全没启动仍静默成功"这个核心场景。 ### 7. Python侧 `_query_process_executable_path` — ✅ 已改为PowerShell **第765-795行**： - 使用 `Get-Process -Id $pid0` 读取进程路径 - 返回 `None` 表示查询失败（保持失败闭合），返回空字符串表示进程存在但无路径 - 不再依赖wmic ### 8. Python侧 `_list_aps_chrome_pids` — ✅ 已改为PowerShell，不再静默成功 **第832-878行**： - 使用 `Get-CimInstance` → `Get-WmiObject` 降级链 - 所有枚举方案都失败时返回 `None`（而非空列表） - 调用方 `stop_aps_chrome_processes`（第881-902行）检测到 `None` 时 `return False` - `_stop_aps_chrome_if_requested` 把 `False` 传播出去 ### 逻辑严谨性总评 - 批处理错误码覆盖：0(成功)、1(exe未找到)、2(Chrome未找到)、3(超时)、4(APS_CHROME_EXE无效)、5(Chrome start失败)、6(app启动失败)、7(日志目录不可写)、8(其他用户占用)、9(不确定归属)、10(profile不可写)、11(Chrome未存活) — 编号没有重叠，语义清晰 - 没有发现新增的静默回退或过度兜底 - 所有失败路径都有日志输出和 `pause` 阻止窗口闪退
- 证据:
  - `assets/启动_排产系统_Chrome.bat:184-204#就绪循环延迟展开修复`
  - `assets/启动_排产系统_Chrome.bat:540-547#normalize_contract_owner`
  - `assets/启动_排产系统_Chrome.bat:549-581#lock_is_active`
  - `assets/启动_排产系统_Chrome.bat:589-605#probe_chrome_profile_dir`
  - `assets/启动_排产系统_Chrome.bat:607-633#probe_chrome_alive`
  - `web/bootstrap/launcher.py:765-795#_query_process_executable_path`
  - `web/bootstrap/launcher.py:832-878#_list_aps_chrome_pids`
  - `web/bootstrap/launcher.py:881-902#stop_aps_chrome_processes`

### M2 · 第二轮：打包脚本、安装器与测试审查

- 状态: 已完成
- 记录时间: 2026-04-07T02:16:17.764Z
- 已审模块: .limcode/skills/aps-package-win7/scripts/package_win7.ps1, installer/aps_win7_chrome.iss, tests/test_win7_launcher_runtime_paths.py, tests/regression_shared_runtime_state.py
- 摘要:

  ## 第二轮审查：打包脚本、安装器与测试

  ### 1. package_win7.ps1 浏览器冒烟 — ✅ 已达成plan目标

  **`Invoke-ChromeRuntimeSmoke`函数（第257-339行）**：
  - 临时起一个本地HTTP服务（`python -m http.server`）
  - 用独立临时profile启动chrome.exe
  - 通过命令行marker（profile目录路径）匹配APS专用Chrome进程
  - 等15秒确认进程出现，再等2秒确认仍然存活
  - 清理逻辑在finally块中执行

  **调用点**：
  - `Invoke-ChromeRuntimeBuild`第455行：对裁剪后的runtime payload执行冒烟
  - `Invoke-LegacyPackageBuild`第480行：对legacy路径下的dist Chrome执行冒烟
  - 两处冒烟失败都会中断出包

  **`Get-ChromeIdsByMarker`函数（第196-242行）**：
  - 使用`Get-CimInstance` → `Get-WmiObject`降级链
  - 通过命令行中包含marker字符串来匹配进程
  - 两种枚举方式都失败时`throw`，不静默成功

  **第二轮暂记问题（已在第四轮复核后下调为低等级接受风险）**：`Stop-ProcessTreeByIds`（第244-255行）在taskkill返回非0时直接throw。如果清理阶段Chrome进程已自行退出，taskkill返回非0，throw会从finally块中泄露。当前被外层空catch块吞掉（第324行），但这是隐式依赖。

  ### 2. aps_win7_chrome.iss 安装器修改 — ✅ 已达成

  **`TryStopApsChromeProcesses`函数（第76-100行）**：
  - 使用PowerShell构建一段进程枚举与停止脚本
  - marker固定为`chrome109profile`（小写），与Chrome profile目录名一致
  - 停止后等800ms再检查是否有残留进程
  - 所有PowerShell不可用或执行失败的场景都返回False
  - 不再依赖wmic

  **卸载流程（第102-147行）**：
  - 静默卸载时Chrome停止失败会直接阻止卸载
  - 交互卸载时Chrome停止失败会弹确认框让用户选择是否继续

  ### 3. 测试覆盖 — ✅ 覆盖充分

  **静态守卫（第161-201行）**：
  - bat延迟展开修复存在性检查（第171-173行）
  - owner反转义存在性检查（第174行）
  - tasklist替代wmic检查（第175-177行）
  - 新增日志键存在性检查（第178-181行）
  - Python侧PowerShell进程枚举检查（第184-191行）
  - 打包脚本浏览器冒烟检查（第194-200行）
  - 安装器wmic移除检查（第234-250行）

  **行为测试**：
  - `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable`（第155-158行）：确认进程列表不可用时返回False
  - `test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm`（第132-152行）：确认Chrome清理不确认时整个stop_runtime返回失败

  **`regression_shared_runtime_state.py`**：端到端覆盖运行时锁获取、契约写入、第二用户阻止、释放与重获取。

  ### 4. 实现优雅性评价

  - 打包脚本的冒烟逻辑拆成独立函数，可复用于runtime和legacy两条路径——结构清晰
  - 打包脚本注释说明了"ASCII-only to avoid ParserError when saved as UTF-8 without BOM"，照顾了Win7 PowerShell 5.1的实际约束
  - 安装器代码把PowerShell脚本构造拆成独立函数`BuildStopChromePowerShellParams`，而不是行内堆砌——可读性好
  - 测试用静态文本断言而非运行时模拟来覆盖bat/ps1/iss的结构约束——这是跨语言项目中实用且低成本的守卫方式
- 结论:

  ## 第二轮审查：打包脚本、安装器与测试 ### 1. package_win7.ps1 浏览器冒烟 — ✅ 已达成plan目标 **`Invoke-ChromeRuntimeSmoke`函数（第257-339行）**： - 临时起一个本地HTTP服务（`python -m http.server`） - 用独立临时profile启动chrome.exe - 通过命令行marker（profile目录路径）匹配APS专用Chrome进程 - 等15秒确认进程出现，再等2秒确认仍然存活 - 清理逻辑在finally块中执行 **调用点**： - `Invoke-ChromeRuntimeBuild`第455行：对裁剪后的runtime payload执行冒烟 - `Invoke-LegacyPackageBuild`第480行：对legacy路径下的dist Chrome执行冒烟 - 两处冒烟失败都会中断出包 **`Get-ChromeIdsByMarker`函数（第196-242行）**： - 使用`Get-CimInstance` → `Get-WmiObject`降级链 - 通过命令行中包含marker字符串来匹配进程 - 两种枚举方式都失败时`throw`，不静默成功 **第二轮暂记问题（已在第四轮复核后下调为低等级接受风险）**：`Stop-ProcessTreeByIds`（第244-255行）在taskkill返回非0时直接throw。如果清理阶段Chrome进程已自行退出，taskkill返回非0，throw会从finally块中泄露。当前被外层空catch块吞掉（第324行），但这是隐式依赖。 ### 2. aps_win7_chrome.iss 安装器修改 — ✅ 已达成 **`TryStopApsChromeProcesses`函数（第76-100行）**： - 使用PowerShell构建一段进程枚举与停止脚本 - marker固定为`chrome109profile`（小写），与Chrome profile目录名一致 - 停止后等800ms再检查是否有残留进程 - 所有PowerShell不可用或执行失败的场景都返回False - 不再依赖wmic **卸载流程（第102-147行）**： - 静默卸载时Chrome停止失败会直接阻止卸载 - 交互卸载时Chrome停止失败会弹确认框让用户选择是否继续 ### 3. 测试覆盖 — ✅ 覆盖充分 **静态守卫（第161-201行）**： - bat延迟展开修复存在性检查（第171-173行） - owner反转义存在性检查（第174行） - tasklist替代wmic检查（第175-177行） - 新增日志键存在性检查（第178-181行） - Python侧PowerShell进程枚举检查（第184-191行） - 打包脚本浏览器冒烟检查（第194-200行） - 安装器wmic移除检查（第234-250行） **行为测试**： - `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable`（第155-158行）：确认进程列表不可用时返回False - `test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm`（第132-152行）：确认Chrome清理不确认时整个stop_runtime返回失败 **`regression_shared_runtime_state.py`**：端到端覆盖运行时锁获取、契约写入、第二用户阻止、释放与重获取。 ### 4. 实现优雅性评价 - 打包脚本的冒烟逻辑拆成独立函数，可复用于runtime和legacy两条路径——结构清晰 - 打包脚本注释说明了"ASCII-only to avoid ParserError when saved as UTF-8 without BOM"，照顾了Win7 PowerShell 5.1的实际约束 - 安装器代码把PowerShell脚本构造拆成独立函数`BuildStopChromePowerShellParams`，而不是行内堆砌——可读性好 - 测试用静态文本断言而非运行时模拟来覆盖bat/ps1/iss的结构约束——这是跨语言项目中实用且低成本的守卫方式
- 证据:
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:257-339#Invoke-ChromeRuntimeSmoke`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:449-462#Invoke-ChromeRuntimeBuild`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:464-489#Invoke-LegacyPackageBuild`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:196-242#Get-ChromeIdsByMarker`
  - `installer/aps_win7_chrome.iss:56-100#TryStopApsChromeProcesses`
  - `tests/test_win7_launcher_runtime_paths.py:161-201#静态守卫`
  - `tests/test_win7_launcher_runtime_paths.py:132-158#失败闭合测试`
- 问题:
  - [低] 可维护性: 冒烟清理语义依赖调用点容错
  - [低] 可维护性: Chrome 进程枚举策略相似但口径未统一

### M3 · 第三轮：文档一致性与整体交叉审查

- 状态: 已完成
- 记录时间: 2026-04-07T02:17:05.028Z
- 已审模块: DELIVERY_WIN7.md, installer/README_WIN7_INSTALLER.md
- 摘要:

  ## 第三轮审查：文档一致性与整体交叉审查

  ### 1. DELIVERY_WIN7.md — ✅ 内容与代码一致

  文档更新要点：
  - 第16-21行：明确指出`package_win7.ps1`是完整入口，包含主程序冷启动验收+浏览器运行时最小冒烟，任一失败阻断出包
  - 第35-41行：排障口径与bat新增日志键完全一致（`contract_owner_normalized`、`app_spawn_probe`、`chrome_profile_probe`、`chrome_alive_probe`、`chrome_cmd`）
  - 第93行：明确说明`validate_dist_exe.py`只覆盖后端冷启动与页面可达，与plan定位一致
  - 没有引入多余的验收文案重复

  ### 2. installer/README_WIN7_INSTALLER.md — ✅ 内容与代码一致

  文档更新要点：
  - 第55-57行：明确说明chrome runtime payload冒烟步骤
  - 第88行：明确`build_win7_installer.bat`不是完整双包验收入口
  - 第206-224行：启动排障段落与bat实际输出日志键精确对齐
  - 第255-259行：验收建议第9条明确覆盖`--runtime-stop --stop-aps-chrome`在无wmic场景下不再误报成功
  - 第262行：明确标注`validate_dist_exe.py`不覆盖Chrome链路

  ### 3. plan与实现的对齐核验

  逐项核验plan中`完成标准`8条：

  1. ✅ 首次启动不再因延迟展开固定等待45秒 — bat已用`!FILE_HOST!`/`!FILE_PORT!`/`!LAUNCH_ERROR!`
  2. ✅ Chrome缺件/profile不可写/Chrome瞬退不再静默消失 — 分别有错误码10/11和`pause`
  3. ✅ bat侧不再依赖wmic — `lock_is_active`已改用`tasklist`，静态守卫断言`wmic`不存在
  4. ✅ Python侧残留wmic已收口 — `_query_process_executable_path`改PowerShell，`_list_aps_chrome_pids`改PowerShell+None语义
  5. ✅ bat侧JSON owner反转义已收口 — `normalize_contract_owner`子程序
  6. ✅ 正式出包浏览器冒烟是阻断项 — `package_win7.ps1`中冒烟失败=`throw`
  7. ✅ 共享日志契约/`--runtime-stop`/现有回归保持通过 — `regression_shared_runtime_state.py`未被破坏性修改
  8. ✅ 文档验收清单已同步 — `DELIVERY_WIN7.md`和`README_WIN7_INSTALLER.md`均已更新

  ### 4. 是否存在过度兜底或过度设计

  **没有**。与原始plan对比，实际实现做了正确的减法：
  - 放弃了"PowerShell 主路径 + profile 锁痕迹降级"的双路径方案，改为简单的`tasklist /FI "IMAGENAME eq chrome.exe"`最小检查
  - 放弃了"中文镜像名 tasklist 过滤"作为主程序存活探测，改为"等2秒+检查错误文件"
  - owner反转义只处理`\\`→`\`一种，没有过度扩展到不可能出现的`\"`和`\/`

  ### 5. 是否存在遗留BUG

  经三轮交叉核验，**未发现遗留BUG**。第一轮和第二轮发现的中等问题（`Stop-ProcessTreeByIds`清理阶段throw依赖隐式catch）不会在当前代码中导致功能错误，只是维护性风险。

  ### 6. 整体实现简洁性评分

  **优秀**。具体表现：
  - bat脚本683行，核心新增逻辑拆成独立子程序，主流程可读性未受影响
  - Python侧修改集中在进程枚举相关的3个函数，没有扩散到不相关代码
  - 打包脚本537行，冒烟逻辑自含、可复用，未引入额外依赖
  - 安装器修改只涉及卸载清理一处，没有改动安装流程
  - 测试新增守卫精准对齐修改点，没有"写一个修复补十个测试"的膨胀
- 结论:

  本轮修改整体质量高，plan的5项交付承诺全部达成。代码实现优雅简洁，没有过度兜底或静默回退，错误处理逻辑清晰一致。第三轮阶段性判断曾暂记为“1个中等级别问题+1个低等级维护性问题”，但该口径已在第四轮引用链复核后统一修订为“2个低等级接受风险”。文档与代码保持一致，无遗漏BUG。
- 证据:
  - `DELIVERY_WIN7.md`
  - `installer/README_WIN7_INSTALLER.md`
  - `.limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md`

### M4 · 第四轮：引用链复核与结论修订

- 状态: 已完成
- 记录时间: 2026-04-07T02:25:14.660Z
- 已审模块: assets/启动_排产系统_Chrome.bat, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, .limcode/skills/aps-package-win7/scripts/package_win7.ps1, installer/aps_win7_chrome.iss, tests/test_win7_launcher_runtime_paths.py, tests/regression_shared_runtime_state.py, tests/regression_runtime_contract_launcher.py, tests/regression_runtime_stop_cli.py, DELIVERY_WIN7.md, installer/README_WIN7_INSTALLER.md
- 摘要:

  ## 第四轮复核：引用链、变量与结论修订

  ### 1. 启动链路逐层核实
  - `app.py -> web/bootstrap/entrypoint.py:app_main()` 在正常启动路径中先获取 `runtime_owner`，再进入 `configure_runtime_contract()`。
  - `configure_runtime_contract()` 会把 `owner`、`chrome_profile_dir`、`exe_path`、`host`、`port` 传给 `write_runtime_contract_file()`；`write_runtime_contract_file()` 再调用 `_runtime_contract_payload()` 落盘到 `aps_runtime.json`。
  - `assets/启动_排产系统_Chrome.bat` 中的 `:read_runtime_contract -> :normalize_contract_owner -> :try_reuse_by_contract` 读取同一份契约，并拿 `CONTRACT_OWNER` 与 `CURRENT_OWNER` 比较。`CURRENT_OWNER` 与 `current_runtime_owner()` 都遵循“域/机器名 + 用户名”的同一语义；默认 `CHROME_PROFILE_DIR` 也与 `default_chrome_profile_dir()` 一致。

  ### 2. 停机与浏览器清理链路逐层核实
  - `app_main(--runtime-stop)` 会进入 `stop_runtime_from_dir()`。
  - `stop_runtime_from_dir()` 通过 `_stop_aps_chrome_if_requested()` 统一收口浏览器清理，并把 `stop_aps_chrome_processes()` 的失败闭合结果继续向外返回，不再吞掉失败。
  - `stop_aps_chrome_processes()` 再调用 `_list_aps_chrome_pids()`；当 PowerShell 进程枚举不可用时，`_list_aps_chrome_pids()` 返回 `None`，调用链整体返回失败。
  - 这条失败闭合语义已被 `tests/test_win7_launcher_runtime_paths.py` 中的相关用例覆盖，且实际回归执行通过。

  ### 3. 打包与安装器链路逐层核实
  - `package_win7.ps1` 中的实际调用链是 `Invoke-ChromeRuntimeSmoke -> Get-ChromeIdsByMarker -> Stop-ProcessTreeByIds`。
  - `Stop-ProcessTreeByIds` 虽然是严格 helper，但它当前只在 `Invoke-ChromeRuntimeSmoke` 的 `finally` 局部 `try/catch` 中调用；因此现状并不会把清理失败泄露成出包失败。此前“会中断出包”的判断偏重，应下调为低等级可维护性提示。
  - `installer/aps_win7_chrome.iss` 中的调用链是 `BuildStopChromePowerShellParams -> TryStopApsChromeProcesses -> InitializeUninstall`。这里确实也使用 `Get-CimInstance -> Get-WmiObject` 的降级链，但它的 marker 是固定子串 `chrome109profile`，并不是与 Python / 打包脚本完全一致的“完整 profile 路径 marker”。

  ### 4. 对既有 finding 的修订
  - `ps1-cleanup-throw-in-finally`：修订为“当前不会阻断出包，只是严格 helper 与 best-effort 清理语义分离不够直观”，严重级别由中下调为低，跟踪状态改为接受风险。
  - `cross-lang-chrome-enum-sync`：修订为“策略相似但口径未统一”，保留低等级接受风险。原因是 Python / 打包脚本按完整 profile 路径匹配，安装器按固定子串 `chrome109profile` 匹配；若未来调整 marker 口径，三处仍需同步。

  ### 5. 回归核验结果
  - 已执行 `pytest tests/test_win7_launcher_runtime_paths.py -q`
  - 已执行 `python tests/regression_shared_runtime_state.py`
  - 已执行 `python tests/regression_runtime_contract_launcher.py`
  - 已执行 `python tests/regression_runtime_stop_cli.py`
  - 上述检查均通过，说明启动、契约、停机与浏览器清理主链路当前闭合。

  ### 6. 修订后的总体意见
  - 本轮实现应从“有条件通过”上调为“通过（带低等级接受风险）”。
  - 当前无需因本 review 阻断；若继续收口，优先建议把安装器侧 marker 常量与运行时 profile 命名来源统一，减少 `chrome109profile` 与 `chrome109_profile` 的长期分叉。
- 结论:

  经第四轮引用链复核后，原 review 中两条 finding 都需要降级和改写：一条属于表述过重，一条属于“完全一致”判断不准。综合源码、调用点、变量语义与回归结果，本轮修改应判定为通过，保留 2 条低等级接受风险即可。
- 证据:
  - `web/bootstrap/entrypoint.py:115-137#configure_runtime_contract 调用 write_runtime_contract_file 传递 owner/profile/exe/host/port 字段`
  - `web/bootstrap/launcher.py:544-559#_runtime_contract_payload 写入 owner 与 chrome_profile_dir`
  - `web/bootstrap/launcher.py:586-621#write_runtime_contract_file`
  - `assets/启动_排产系统_Chrome.bat:479-518#read_runtime_contract`
  - `assets/启动_排产系统_Chrome.bat:540-547#normalize_contract_owner`
  - `assets/启动_排产系统_Chrome.bat:392-410#try_reuse_by_contract`
  - `web/bootstrap/launcher.py:832-902#_list_aps_chrome_pids 与 stop_aps_chrome_processes`
  - `web/bootstrap/launcher.py:923-973#stop_runtime_from_dir 调用 _stop_aps_chrome_if_requested`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:244-339#Stop-ProcessTreeByIds 与 Invoke-ChromeRuntimeSmoke finally 清理`
  - `installer/aps_win7_chrome.iss:56-147#BuildStopChromePowerShellParams -> TryStopApsChromeProcesses -> InitializeUninstall`
  - `tests/test_win7_launcher_runtime_paths.py:132-200#停机失败闭合与静态守卫`
  - `tests/regression_shared_runtime_state.py:50-123#共享运行时状态回归`
  - `tests/regression_runtime_contract_launcher.py:51-109#运行时契约读写回归`
  - `tests/regression_runtime_stop_cli.py:140-177#runtime-stop 真实停机回归`
  - `assets/启动_排产系统_Chrome.bat`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `installer/aps_win7_chrome.iss`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/regression_runtime_stop_cli.py`
- 下一步建议:

  当前无需因本 review 阻断；若继续收口，优先统一 installer 侧 marker 常量与运行时 profile 命名来源。
- 问题:
  - [低] 可维护性: 冒烟清理语义依赖调用点容错
  - [低] 可维护性: Chrome 进程枚举策略相似但口径未统一

### M5 · 第五轮：接受风险收口复核

- 状态: 已完成
- 记录时间: 2026-04-07T02:51:18.964Z
- 已审模块: .limcode/skills/aps-package-win7/scripts/package_win7.ps1, installer/aps_win7_chrome.iss, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, assets/启动_排产系统_Chrome.bat, tests/test_win7_launcher_runtime_paths.py, tests/regression_runtime_contract_launcher.py, tests/regression_shared_runtime_state.py, tests/regression_runtime_stop_cli.py
- 摘要:

  ## 第五轮复核：接受风险已收口

  ### 1. 打包脚本清理语义收口
  - 复核 `.limcode/skills/aps-package-win7/scripts/package_win7.ps1` 可见：`Stop-ProcessTreeByIds` 仍保留严格停止语义，`taskkill` 非零即抛错，没有被改成静默成功。
  - 新增 `Stop-ProcessTreeByIdsBestEffort` 仅作为包装层出现，并且当前仅在 `Invoke-ChromeRuntimeSmoke` 的 `finally` 清理分支被调用。
  - `finally` 中已移除原先包住严格 helper 的空 `catch`，清理语义改为“显式容错 helper + 其他步骤各自独立清理”，不再依赖调用点隐式吞异常。

  ### 2. 浏览器进程 marker 口径收口
  - 复核 `installer/aps_win7_chrome.iss` 可见：新增 `CurrentUserChromeProfilePath()`，其返回值与 `web/bootstrap/launcher.py:default_chrome_profile_dir()`、`assets/启动_排产系统_Chrome.bat` 的默认 profile 路径一致，均为 `%LOCALAPPDATA%\\APS\\Chrome109Profile`。
  - `BuildStopChromePowerShellParams` 已改为接收 profile 绝对路径参数，并在写入 PowerShell 前先做单引号转义；卸载脚本不再使用裸字串 `chrome109profile`。
  - `TryStopApsChromeProcesses -> BuildStopChromePowerShellParams(CurrentUserChromeProfilePath)` 调用链已把安装器侧进程枚举口径收口到“当前账户 profile 绝对路径 marker”。

  ### 3. 引用链复核
  - `web/bootstrap/entrypoint.py:configure_runtime_contract()` 仍把 `default_chrome_profile_dir(runtime_dir)` 写入运行时契约。
  - `web/bootstrap/launcher.py:stop_runtime_from_dir()` 在无契约回退路径中仍通过 `default_chrome_profile_dir(runtime_dir_abs)` 计算默认 profile。
  - `assets/启动_排产系统_Chrome.bat` 仍固定使用 `%LOCALAPPDATA%\\APS\\Chrome109Profile`；因此启动、契约、停机、卸载四处 profile 口径现在一致。

  ### 4. 验证结果
  - `python -m pytest tests/test_win7_launcher_runtime_paths.py -q`：21 通过。
  - `python tests/regression_runtime_contract_launcher.py`：输出 `OK`。
  - `python tests/regression_shared_runtime_state.py`：输出 `OK`。
  - `python tests/regression_runtime_stop_cli.py`：输出 `OK`。

  ### 5. 结论
  - `ps1-cleanup-throw-in-finally` 已通过显式 best-effort helper 收口。
  - `cross-lang-chrome-enum-sync` 已通过统一到 profile 绝对路径 marker 收口。
  - 本次修改未引入新的静默回退或过度兜底，现有启动链、契约链、停机链与卸载清理链均保持通过。
- 结论:

  经第五轮引用链复核与回归验证，原 review 中两条低等级接受风险均已完成代码收口并有测试证据支撑，跟踪状态可改为 `fixed`。
- 证据:
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:244-329#严格停止与容错清理 helper 收口`
  - `installer/aps_win7_chrome.iss:56-100#CurrentUserChromeProfilePath 与 stop helper 调用链`
  - `web/bootstrap/entrypoint.py:123-137#configure_runtime_contract 写入 chrome_profile_dir`
  - `web/bootstrap/launcher.py:514-518#default_chrome_profile_dir`
  - `web/bootstrap/launcher.py:939-941#stop_runtime_from_dir 默认 profile 路径`
  - `assets/启动_排产系统_Chrome.bat:57-62#启动批处理默认 profile 路径`
  - `tests/test_win7_launcher_runtime_paths.py:86-272#新增静态守卫与行为守卫`
  - `tests/regression_runtime_contract_launcher.py:51-109#运行时契约回归`
  - `tests/regression_shared_runtime_state.py:50-123#共享状态回归`
  - `tests/regression_runtime_stop_cli.py:140-177#停机回归`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `installer/aps_win7_chrome.iss`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `assets/启动_排产系统_Chrome.bat`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_stop_cli.py`
- 下一步建议:

  当前无需继续跟踪本次两条风险；后续若再改 profile 命名或浏览器清理协议，继续按同一口径同步四处实现。
- 问题:
  - [低] 可维护性: 冒烟清理语义依赖调用点容错
  - [低] 可维护性: Chrome 进程枚举策略相似但口径未统一
  - [低] 其他: `ps1-cleanup-throw-in-finally` 已修复
  - [低] 其他: `cross-lang-chrome-enum-sync` 已修复

## 最终结论

经第五轮引用链复核与回归验证，打包脚本清理语义与安装器 Chrome marker 口径两条接受风险均已完成代码收口；启动、契约、停机与卸载清理主链路回归全部通过。本 review 可按“已接受并完成收口”结束。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnnzkhjr-813t4u",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T02:52:12.239Z",
  "finalizedAt": "2026-04-07T02:52:12.239Z",
  "status": "completed",
  "overallDecision": "accepted",
  "header": {
    "title": "APS启动链路与Chrome拉起修复-三轮深度审查",
    "date": "2026-04-07",
    "overview": "对APS启动链路与Chrome拉起修复plan所涉及的全部未提交修改进行三轮深度审查，覆盖启动批处理、Python运行时入口、打包脚本、安装器、测试与文档。"
  },
  "scope": {
    "markdown": "# APS启动链路与Chrome拉起修复 - 三轮深度审查\n\n- 日期：2026-04-07\n- 范围：启动批处理(`assets/启动_排产系统_Chrome.bat`)、Python运行时入口(`web/bootstrap/launcher.py`)、打包脚本(`package_win7.ps1`)、安装器(`aps_win7_chrome.iss`)、测试(`test_win7_launcher_runtime_paths.py`)、文档(`DELIVERY_WIN7.md`、`README_WIN7_INSTALLER.md`)\n- 目标：审查本轮未提交修改是否达成plan目标、实现是否优雅简洁、有无过度兜底/静默回退、逻辑是否严谨、是否存在遗留BUG\n\n## 审查口径\n\n本次审查聚焦以下五项plan交付承诺：\n1. P0：首次启动不再因延迟展开BUG固定等待45秒\n2. P1：收口owner反转义、锁探测、主程序短时存活与profile可写性\n3. P2：替换残留wmic并消除浏览器清理静默回退\n4. P3：为package_win7.ps1增加浏览器运行时最小冒烟\n5. P4：文档与验收清单同步"
  },
  "summary": {
    "latestConclusion": "经第五轮引用链复核与回归验证，打包脚本清理语义与安装器 Chrome marker 口径两条接受风险均已完成代码收口；启动、契约、停机与卸载清理主链路回归全部通过。本 review 可按“已接受并完成收口”结束。",
    "recommendedNextAction": "当前无需继续跟踪本次两条风险；后续若再改 profile 命名或浏览器清理协议，继续按同一口径同步四处实现。",
    "reviewedModules": [
      "assets/启动_排产系统_Chrome.bat",
      "web/bootstrap/launcher.py",
      ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
      "installer/aps_win7_chrome.iss",
      "tests/test_win7_launcher_runtime_paths.py",
      "tests/regression_shared_runtime_state.py",
      "DELIVERY_WIN7.md",
      "installer/README_WIN7_INSTALLER.md",
      "web/bootstrap/entrypoint.py",
      "tests/regression_runtime_contract_launcher.py",
      "tests/regression_runtime_stop_cli.py"
    ]
  },
  "stats": {
    "totalMilestones": 5,
    "completedMilestones": 5,
    "totalFindings": 4,
    "severity": {
      "high": 0,
      "medium": 0,
      "low": 4
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：启动批处理与Python运行时入口审查",
      "status": "completed",
      "recordedAt": "2026-04-07T02:15:16.921Z",
      "summaryMarkdown": "## 第一轮审查：启动批处理与Python运行时入口\n\n### 1. P0 延迟展开修复 — ✅ 已达成\n\n**bat就绪循环（第184-204行）**：\n- `set \"HOST=!FILE_HOST!\"` 和 `set \"PORT=!FILE_PORT!\"` 已正确使用延迟展开语法\n- `call :log launch_error=\"!LAUNCH_ERROR!\"` 也已使用延迟展开\n- 测试文件第171-173行有对应静态守卫断言\n\n评价：修复简洁直接，没有过度改造，只改了必须改的三处。\n\n### 2. P1.1 owner反转义 — ✅ 已达成，但有一处值得注意\n\n**`:normalize_contract_owner`子程序（第540-547行）**：\n```bat\nset \"CONTRACT_OWNER=!CONTRACT_OWNER:\\\\=\\!\"\n```\n这行把JSON中的 `\\\\` 还原为 `\\`。逻辑正确——Python侧 `json.dump` 会把 `DOMAIN\\user` 写成 `DOMAIN\\\\user`，而bat侧当前账户值是 `DOMAIN\\user`，所以需要反转义。\n\n**潜在问题**：plan提到\"如实现成本可控，再补 `\\\"` 与 `\\/` 的最小兼容\"，当前只处理了 `\\\\`→`\\`。考虑到owner值只含域名和用户名，不会出现 `\\\"` 或 `\\/`，这个范围是合理的。\n\n### 3. P1.2 锁探测替换wmic — ✅ 已达成\n\n**`:lock_is_active`子程序（第549-581行）**：\n- 使用 `tasklist /FI \"PID eq !LOCK_PID!\" /NH /FO CSV` 替代了wmic\n- 输出写到临时文件再逐行解析，避免管道中的延迟展开问题\n- PID格式先做正则校验（`^[0-9][0-9]*$`），非法PID直接走UNKNOWN而不是误判不活跃\n- `tasklist` 命令失败时设 `LOCK_ACTIVE=UNKNOWN` 保持失败闭合\n\n**潜在问题1**：临时文件命名用 `%RANDOM%_%RANDOM%`，在极端并发场景下仍有碰撞概率。但考虑到APS本身是单活用户设计，这个风险可忽略。\n\n**潜在问题2**：第575行 `echo !LOCK_QUERY_ROW! | findstr /C:\",\\\"!LOCK_PID!\\\",\" >nul` 对tasklist CSV输出做精确PID匹配。这个模式能区分 PID 123 与 PID 1234，因为CSV格式是 `\"imagename\",\"123\",\"...\"` 带引号和逗号的。逻辑正确。\n\n### 4. P1.3 主程序短时存活探测 — ✅ 已达成\n\n**第167-181行**：\n- `start \"\" \"%APP_EXE%\"` 后立即 `timeout /t 2`\n- 然后检查 `aps_launch_error.txt` 是否生成\n- 如有明确错误文件，直接跳转到 `:APP_START_FAILED` 不再继续等待\n- 无错误才进入就绪循环\n\n**优点**：不依赖中文镜像名筛选，使用错误文件作为信号——这是最可靠的跨语言方案。\n\n### 5. P1.4 profile可写性校验 — ✅ 已达成\n\n**`:probe_chrome_profile_dir`子程序（第589-605行）**：\n- 先尝试创建目录\n- 再写入探针文件 `aps_write_probe_{RANDOM}_{RANDOM}.tmp`\n- 写入失败则设 `CHROME_PROFILE_READY=` 为空\n- 主流程第146-151行检测到不可写后会 `pause` 并 `exit /b 10`\n\n**细节**：探针文件内容是 `> \"%CHROME_PROFILE_PROBE_FILE%\" echo APS`，简洁明了。删除用 `del /f /q` 且不检查结果——这里是合理的，因为探针文件只是临时文件。\n\n### 6. P1.5 浏览器短时存活确认 — ✅ 已达成\n\n**`:probe_chrome_alive`子程序（第607-633行）**：\n- 用 `tasklist /FI \"IMAGENAME eq chrome.exe\" /NH /FO CSV` 检查是否存在chrome.exe\n- 等待3秒后检查\n- 不存在则设 `CHROME_ALIVE=` 为空\n- 主流程第260-268行检测到未存活后给出明确排障提示和 `pause`\n\n**注意**：正如plan所述，这个检查无法区分APS专用浏览器和普通Chrome，但能覆盖\"Chrome完全没启动仍静默成功\"这个核心场景。\n\n### 7. Python侧 `_query_process_executable_path` — ✅ 已改为PowerShell\n\n**第765-795行**：\n- 使用 `Get-Process -Id $pid0` 读取进程路径\n- 返回 `None` 表示查询失败（保持失败闭合），返回空字符串表示进程存在但无路径\n- 不再依赖wmic\n\n### 8. Python侧 `_list_aps_chrome_pids` — ✅ 已改为PowerShell，不再静默成功\n\n**第832-878行**：\n- 使用 `Get-CimInstance` → `Get-WmiObject` 降级链\n- 所有枚举方案都失败时返回 `None`（而非空列表）\n- 调用方 `stop_aps_chrome_processes`（第881-902行）检测到 `None` 时 `return False`\n- `_stop_aps_chrome_if_requested` 把 `False` 传播出去\n\n### 逻辑严谨性总评\n\n- 批处理错误码覆盖：0(成功)、1(exe未找到)、2(Chrome未找到)、3(超时)、4(APS_CHROME_EXE无效)、5(Chrome start失败)、6(app启动失败)、7(日志目录不可写)、8(其他用户占用)、9(不确定归属)、10(profile不可写)、11(Chrome未存活) — 编号没有重叠，语义清晰\n- 没有发现新增的静默回退或过度兜底\n- 所有失败路径都有日志输出和 `pause` 阻止窗口闪退",
      "conclusionMarkdown": "## 第一轮审查：启动批处理与Python运行时入口 ### 1. P0 延迟展开修复 — ✅ 已达成 **bat就绪循环（第184-204行）**： - `set \"HOST=!FILE_HOST!\"` 和 `set \"PORT=!FILE_PORT!\"` 已正确使用延迟展开语法 - `call :log launch_error=\"!LAUNCH_ERROR!\"` 也已使用延迟展开 - 测试文件第171-173行有对应静态守卫断言 评价：修复简洁直接，没有过度改造，只改了必须改的三处。 ### 2. P1.1 owner反转义 — ✅ 已达成，但有一处值得注意 **`:normalize_contract_owner`子程序（第540-547行）**： ```bat set \"CONTRACT_OWNER=!CONTRACT_OWNER:\\\\=\\!\" ``` 这行把JSON中的 `\\\\` 还原为 `\\`。逻辑正确——Python侧 `json.dump` 会把 `DOMAIN\\user` 写成 `DOMAIN\\\\user`，而bat侧当前账户值是 `DOMAIN\\user`，所以需要反转义。 **潜在问题**：plan提到\"如实现成本可控，再补 `\\\"` 与 `\\/` 的最小兼容\"，当前只处理了 `\\\\`→`\\`。考虑到owner值只含域名和用户名，不会出现 `\\\"` 或 `\\/`，这个范围是合理的。 ### 3. P1.2 锁探测替换wmic — ✅ 已达成 **`:lock_is_active`子程序（第549-581行）**： - 使用 `tasklist /FI \"PID eq !LOCK_PID!\" /NH /FO CSV` 替代了wmic - 输出写到临时文件再逐行解析，避免管道中的延迟展开问题 - PID格式先做正则校验（`^[0-9][0-9]*$`），非法PID直接走UNKNOWN而不是误判不活跃 - `tasklist` 命令失败时设 `LOCK_ACTIVE=UNKNOWN` 保持失败闭合 **潜在问题1**：临时文件命名用 `%RANDOM%_%RANDOM%`，在极端并发场景下仍有碰撞概率。但考虑到APS本身是单活用户设计，这个风险可忽略。 **潜在问题2**：第575行 `echo !LOCK_QUERY_ROW! | findstr /C:\",\\\"!LOCK_PID!\\\",\" >nul` 对tasklist CSV输出做精确PID匹配。这个模式能区分 PID 123 与 PID 1234，因为CSV格式是 `\"imagename\",\"123\",\"...\"` 带引号和逗号的。逻辑正确。 ### 4. P1.3 主程序短时存活探测 — ✅ 已达成 **第167-181行**： - `start \"\" \"%APP_EXE%\"` 后立即 `timeout /t 2` - 然后检查 `aps_launch_error.txt` 是否生成 - 如有明确错误文件，直接跳转到 `:APP_START_FAILED` 不再继续等待 - 无错误才进入就绪循环 **优点**：不依赖中文镜像名筛选，使用错误文件作为信号——这是最可靠的跨语言方案。 ### 5. P1.4 profile可写性校验 — ✅ 已达成 **`:probe_chrome_profile_dir`子程序（第589-605行）**： - 先尝试创建目录 - 再写入探针文件 `aps_write_probe_{RANDOM}_{RANDOM}.tmp` - 写入失败则设 `CHROME_PROFILE_READY=` 为空 - 主流程第146-151行检测到不可写后会 `pause` 并 `exit /b 10` **细节**：探针文件内容是 `> \"%CHROME_PROFILE_PROBE_FILE%\" echo APS`，简洁明了。删除用 `del /f /q` 且不检查结果——这里是合理的，因为探针文件只是临时文件。 ### 6. P1.5 浏览器短时存活确认 — ✅ 已达成 **`:probe_chrome_alive`子程序（第607-633行）**： - 用 `tasklist /FI \"IMAGENAME eq chrome.exe\" /NH /FO CSV` 检查是否存在chrome.exe - 等待3秒后检查 - 不存在则设 `CHROME_ALIVE=` 为空 - 主流程第260-268行检测到未存活后给出明确排障提示和 `pause` **注意**：正如plan所述，这个检查无法区分APS专用浏览器和普通Chrome，但能覆盖\"Chrome完全没启动仍静默成功\"这个核心场景。 ### 7. Python侧 `_query_process_executable_path` — ✅ 已改为PowerShell **第765-795行**： - 使用 `Get-Process -Id $pid0` 读取进程路径 - 返回 `None` 表示查询失败（保持失败闭合），返回空字符串表示进程存在但无路径 - 不再依赖wmic ### 8. Python侧 `_list_aps_chrome_pids` — ✅ 已改为PowerShell，不再静默成功 **第832-878行**： - 使用 `Get-CimInstance` → `Get-WmiObject` 降级链 - 所有枚举方案都失败时返回 `None`（而非空列表） - 调用方 `stop_aps_chrome_processes`（第881-902行）检测到 `None` 时 `return False` - `_stop_aps_chrome_if_requested` 把 `False` 传播出去 ### 逻辑严谨性总评 - 批处理错误码覆盖：0(成功)、1(exe未找到)、2(Chrome未找到)、3(超时)、4(APS_CHROME_EXE无效)、5(Chrome start失败)、6(app启动失败)、7(日志目录不可写)、8(其他用户占用)、9(不确定归属)、10(profile不可写)、11(Chrome未存活) — 编号没有重叠，语义清晰 - 没有发现新增的静默回退或过度兜底 - 所有失败路径都有日志输出和 `pause` 阻止窗口闪退",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 184,
          "lineEnd": 204,
          "symbol": "就绪循环延迟展开修复"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 540,
          "lineEnd": 547,
          "symbol": "normalize_contract_owner"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 549,
          "lineEnd": 581,
          "symbol": "lock_is_active"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 589,
          "lineEnd": 605,
          "symbol": "probe_chrome_profile_dir"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 607,
          "lineEnd": 633,
          "symbol": "probe_chrome_alive"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 765,
          "lineEnd": 795,
          "symbol": "_query_process_executable_path"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 878,
          "symbol": "_list_aps_chrome_pids"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 881,
          "lineEnd": 902,
          "symbol": "stop_aps_chrome_processes"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "web/bootstrap/launcher.py"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    },
    {
      "id": "M2",
      "title": "第二轮：打包脚本、安装器与测试审查",
      "status": "completed",
      "recordedAt": "2026-04-07T02:16:17.764Z",
      "summaryMarkdown": "## 第二轮审查：打包脚本、安装器与测试\n\n### 1. package_win7.ps1 浏览器冒烟 — ✅ 已达成plan目标\n\n**`Invoke-ChromeRuntimeSmoke`函数（第257-339行）**：\n- 临时起一个本地HTTP服务（`python -m http.server`）\n- 用独立临时profile启动chrome.exe\n- 通过命令行marker（profile目录路径）匹配APS专用Chrome进程\n- 等15秒确认进程出现，再等2秒确认仍然存活\n- 清理逻辑在finally块中执行\n\n**调用点**：\n- `Invoke-ChromeRuntimeBuild`第455行：对裁剪后的runtime payload执行冒烟\n- `Invoke-LegacyPackageBuild`第480行：对legacy路径下的dist Chrome执行冒烟\n- 两处冒烟失败都会中断出包\n\n**`Get-ChromeIdsByMarker`函数（第196-242行）**：\n- 使用`Get-CimInstance` → `Get-WmiObject`降级链\n- 通过命令行中包含marker字符串来匹配进程\n- 两种枚举方式都失败时`throw`，不静默成功\n\n**第二轮暂记问题（已在第四轮复核后下调为低等级接受风险）**：`Stop-ProcessTreeByIds`（第244-255行）在taskkill返回非0时直接throw。如果清理阶段Chrome进程已自行退出，taskkill返回非0，throw会从finally块中泄露。当前被外层空catch块吞掉（第324行），但这是隐式依赖。\n\n### 2. aps_win7_chrome.iss 安装器修改 — ✅ 已达成\n\n**`TryStopApsChromeProcesses`函数（第76-100行）**：\n- 使用PowerShell构建一段进程枚举与停止脚本\n- marker固定为`chrome109profile`（小写），与Chrome profile目录名一致\n- 停止后等800ms再检查是否有残留进程\n- 所有PowerShell不可用或执行失败的场景都返回False\n- 不再依赖wmic\n\n**卸载流程（第102-147行）**：\n- 静默卸载时Chrome停止失败会直接阻止卸载\n- 交互卸载时Chrome停止失败会弹确认框让用户选择是否继续\n\n### 3. 测试覆盖 — ✅ 覆盖充分\n\n**静态守卫（第161-201行）**：\n- bat延迟展开修复存在性检查（第171-173行）\n- owner反转义存在性检查（第174行）\n- tasklist替代wmic检查（第175-177行）\n- 新增日志键存在性检查（第178-181行）\n- Python侧PowerShell进程枚举检查（第184-191行）\n- 打包脚本浏览器冒烟检查（第194-200行）\n- 安装器wmic移除检查（第234-250行）\n\n**行为测试**：\n- `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable`（第155-158行）：确认进程列表不可用时返回False\n- `test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm`（第132-152行）：确认Chrome清理不确认时整个stop_runtime返回失败\n\n**`regression_shared_runtime_state.py`**：端到端覆盖运行时锁获取、契约写入、第二用户阻止、释放与重获取。\n\n### 4. 实现优雅性评价\n\n- 打包脚本的冒烟逻辑拆成独立函数，可复用于runtime和legacy两条路径——结构清晰\n- 打包脚本注释说明了\"ASCII-only to avoid ParserError when saved as UTF-8 without BOM\"，照顾了Win7 PowerShell 5.1的实际约束\n- 安装器代码把PowerShell脚本构造拆成独立函数`BuildStopChromePowerShellParams`，而不是行内堆砌——可读性好\n- 测试用静态文本断言而非运行时模拟来覆盖bat/ps1/iss的结构约束——这是跨语言项目中实用且低成本的守卫方式",
      "conclusionMarkdown": "## 第二轮审查：打包脚本、安装器与测试 ### 1. package_win7.ps1 浏览器冒烟 — ✅ 已达成plan目标 **`Invoke-ChromeRuntimeSmoke`函数（第257-339行）**： - 临时起一个本地HTTP服务（`python -m http.server`） - 用独立临时profile启动chrome.exe - 通过命令行marker（profile目录路径）匹配APS专用Chrome进程 - 等15秒确认进程出现，再等2秒确认仍然存活 - 清理逻辑在finally块中执行 **调用点**： - `Invoke-ChromeRuntimeBuild`第455行：对裁剪后的runtime payload执行冒烟 - `Invoke-LegacyPackageBuild`第480行：对legacy路径下的dist Chrome执行冒烟 - 两处冒烟失败都会中断出包 **`Get-ChromeIdsByMarker`函数（第196-242行）**： - 使用`Get-CimInstance` → `Get-WmiObject`降级链 - 通过命令行中包含marker字符串来匹配进程 - 两种枚举方式都失败时`throw`，不静默成功 **第二轮暂记问题（已在第四轮复核后下调为低等级接受风险）**：`Stop-ProcessTreeByIds`（第244-255行）在taskkill返回非0时直接throw。如果清理阶段Chrome进程已自行退出，taskkill返回非0，throw会从finally块中泄露。当前被外层空catch块吞掉（第324行），但这是隐式依赖。 ### 2. aps_win7_chrome.iss 安装器修改 — ✅ 已达成 **`TryStopApsChromeProcesses`函数（第76-100行）**： - 使用PowerShell构建一段进程枚举与停止脚本 - marker固定为`chrome109profile`（小写），与Chrome profile目录名一致 - 停止后等800ms再检查是否有残留进程 - 所有PowerShell不可用或执行失败的场景都返回False - 不再依赖wmic **卸载流程（第102-147行）**： - 静默卸载时Chrome停止失败会直接阻止卸载 - 交互卸载时Chrome停止失败会弹确认框让用户选择是否继续 ### 3. 测试覆盖 — ✅ 覆盖充分 **静态守卫（第161-201行）**： - bat延迟展开修复存在性检查（第171-173行） - owner反转义存在性检查（第174行） - tasklist替代wmic检查（第175-177行） - 新增日志键存在性检查（第178-181行） - Python侧PowerShell进程枚举检查（第184-191行） - 打包脚本浏览器冒烟检查（第194-200行） - 安装器wmic移除检查（第234-250行） **行为测试**： - `test_stop_aps_chrome_processes_fails_closed_when_pid_list_unavailable`（第155-158行）：确认进程列表不可用时返回False - `test_stop_runtime_from_log_dir_fails_closed_when_chrome_cleanup_cannot_confirm`（第132-152行）：确认Chrome清理不确认时整个stop_runtime返回失败 **`regression_shared_runtime_state.py`**：端到端覆盖运行时锁获取、契约写入、第二用户阻止、释放与重获取。 ### 4. 实现优雅性评价 - 打包脚本的冒烟逻辑拆成独立函数，可复用于runtime和legacy两条路径——结构清晰 - 打包脚本注释说明了\"ASCII-only to avoid ParserError when saved as UTF-8 without BOM\"，照顾了Win7 PowerShell 5.1的实际约束 - 安装器代码把PowerShell脚本构造拆成独立函数`BuildStopChromePowerShellParams`，而不是行内堆砌——可读性好 - 测试用静态文本断言而非运行时模拟来覆盖bat/ps1/iss的结构约束——这是跨语言项目中实用且低成本的守卫方式",
      "evidence": [
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 257,
          "lineEnd": 339,
          "symbol": "Invoke-ChromeRuntimeSmoke"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 449,
          "lineEnd": 462,
          "symbol": "Invoke-ChromeRuntimeBuild"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 464,
          "lineEnd": 489,
          "symbol": "Invoke-LegacyPackageBuild"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 196,
          "lineEnd": 242,
          "symbol": "Get-ChromeIdsByMarker"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 56,
          "lineEnd": 100,
          "symbol": "TryStopApsChromeProcesses"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 161,
          "lineEnd": 201,
          "symbol": "静态守卫"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 132,
          "lineEnd": 158,
          "symbol": "失败闭合测试"
        }
      ],
      "reviewedModules": [
        ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
        "installer/aps_win7_chrome.iss",
        "tests/test_win7_launcher_runtime_paths.py",
        "tests/regression_shared_runtime_state.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "ps1-cleanup-throw-in-finally",
        "cross-lang-chrome-enum-sync"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：文档一致性与整体交叉审查",
      "status": "completed",
      "recordedAt": "2026-04-07T02:17:05.028Z",
      "summaryMarkdown": "## 第三轮审查：文档一致性与整体交叉审查\n\n### 1. DELIVERY_WIN7.md — ✅ 内容与代码一致\n\n文档更新要点：\n- 第16-21行：明确指出`package_win7.ps1`是完整入口，包含主程序冷启动验收+浏览器运行时最小冒烟，任一失败阻断出包\n- 第35-41行：排障口径与bat新增日志键完全一致（`contract_owner_normalized`、`app_spawn_probe`、`chrome_profile_probe`、`chrome_alive_probe`、`chrome_cmd`）\n- 第93行：明确说明`validate_dist_exe.py`只覆盖后端冷启动与页面可达，与plan定位一致\n- 没有引入多余的验收文案重复\n\n### 2. installer/README_WIN7_INSTALLER.md — ✅ 内容与代码一致\n\n文档更新要点：\n- 第55-57行：明确说明chrome runtime payload冒烟步骤\n- 第88行：明确`build_win7_installer.bat`不是完整双包验收入口\n- 第206-224行：启动排障段落与bat实际输出日志键精确对齐\n- 第255-259行：验收建议第9条明确覆盖`--runtime-stop --stop-aps-chrome`在无wmic场景下不再误报成功\n- 第262行：明确标注`validate_dist_exe.py`不覆盖Chrome链路\n\n### 3. plan与实现的对齐核验\n\n逐项核验plan中`完成标准`8条：\n\n1. ✅ 首次启动不再因延迟展开固定等待45秒 — bat已用`!FILE_HOST!`/`!FILE_PORT!`/`!LAUNCH_ERROR!`\n2. ✅ Chrome缺件/profile不可写/Chrome瞬退不再静默消失 — 分别有错误码10/11和`pause`\n3. ✅ bat侧不再依赖wmic — `lock_is_active`已改用`tasklist`，静态守卫断言`wmic`不存在\n4. ✅ Python侧残留wmic已收口 — `_query_process_executable_path`改PowerShell，`_list_aps_chrome_pids`改PowerShell+None语义\n5. ✅ bat侧JSON owner反转义已收口 — `normalize_contract_owner`子程序\n6. ✅ 正式出包浏览器冒烟是阻断项 — `package_win7.ps1`中冒烟失败=`throw`\n7. ✅ 共享日志契约/`--runtime-stop`/现有回归保持通过 — `regression_shared_runtime_state.py`未被破坏性修改\n8. ✅ 文档验收清单已同步 — `DELIVERY_WIN7.md`和`README_WIN7_INSTALLER.md`均已更新\n\n### 4. 是否存在过度兜底或过度设计\n\n**没有**。与原始plan对比，实际实现做了正确的减法：\n- 放弃了\"PowerShell 主路径 + profile 锁痕迹降级\"的双路径方案，改为简单的`tasklist /FI \"IMAGENAME eq chrome.exe\"`最小检查\n- 放弃了\"中文镜像名 tasklist 过滤\"作为主程序存活探测，改为\"等2秒+检查错误文件\"\n- owner反转义只处理`\\\\`→`\\`一种，没有过度扩展到不可能出现的`\\\"`和`\\/`\n\n### 5. 是否存在遗留BUG\n\n经三轮交叉核验，**未发现遗留BUG**。第一轮和第二轮发现的中等问题（`Stop-ProcessTreeByIds`清理阶段throw依赖隐式catch）不会在当前代码中导致功能错误，只是维护性风险。\n\n### 6. 整体实现简洁性评分\n\n**优秀**。具体表现：\n- bat脚本683行，核心新增逻辑拆成独立子程序，主流程可读性未受影响\n- Python侧修改集中在进程枚举相关的3个函数，没有扩散到不相关代码\n- 打包脚本537行，冒烟逻辑自含、可复用，未引入额外依赖\n- 安装器修改只涉及卸载清理一处，没有改动安装流程\n- 测试新增守卫精准对齐修改点，没有\"写一个修复补十个测试\"的膨胀",
      "conclusionMarkdown": "本轮修改整体质量高，plan的5项交付承诺全部达成。代码实现优雅简洁，没有过度兜底或静默回退，错误处理逻辑清晰一致。第三轮阶段性判断曾暂记为“1个中等级别问题+1个低等级维护性问题”，但该口径已在第四轮引用链复核后统一修订为“2个低等级接受风险”。文档与代码保持一致，无遗漏BUG。",
      "evidence": [
        {
          "path": "DELIVERY_WIN7.md"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        },
        {
          "path": ".limcode/plans/20260407_APS启动链路与Chrome拉起修复plan.md"
        }
      ],
      "reviewedModules": [
        "DELIVERY_WIN7.md",
        "installer/README_WIN7_INSTALLER.md"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    },
    {
      "id": "M4",
      "title": "第四轮：引用链复核与结论修订",
      "status": "completed",
      "recordedAt": "2026-04-07T02:25:14.660Z",
      "summaryMarkdown": "## 第四轮复核：引用链、变量与结论修订\n\n### 1. 启动链路逐层核实\n- `app.py -> web/bootstrap/entrypoint.py:app_main()` 在正常启动路径中先获取 `runtime_owner`，再进入 `configure_runtime_contract()`。\n- `configure_runtime_contract()` 会把 `owner`、`chrome_profile_dir`、`exe_path`、`host`、`port` 传给 `write_runtime_contract_file()`；`write_runtime_contract_file()` 再调用 `_runtime_contract_payload()` 落盘到 `aps_runtime.json`。\n- `assets/启动_排产系统_Chrome.bat` 中的 `:read_runtime_contract -> :normalize_contract_owner -> :try_reuse_by_contract` 读取同一份契约，并拿 `CONTRACT_OWNER` 与 `CURRENT_OWNER` 比较。`CURRENT_OWNER` 与 `current_runtime_owner()` 都遵循“域/机器名 + 用户名”的同一语义；默认 `CHROME_PROFILE_DIR` 也与 `default_chrome_profile_dir()` 一致。\n\n### 2. 停机与浏览器清理链路逐层核实\n- `app_main(--runtime-stop)` 会进入 `stop_runtime_from_dir()`。\n- `stop_runtime_from_dir()` 通过 `_stop_aps_chrome_if_requested()` 统一收口浏览器清理，并把 `stop_aps_chrome_processes()` 的失败闭合结果继续向外返回，不再吞掉失败。\n- `stop_aps_chrome_processes()` 再调用 `_list_aps_chrome_pids()`；当 PowerShell 进程枚举不可用时，`_list_aps_chrome_pids()` 返回 `None`，调用链整体返回失败。\n- 这条失败闭合语义已被 `tests/test_win7_launcher_runtime_paths.py` 中的相关用例覆盖，且实际回归执行通过。\n\n### 3. 打包与安装器链路逐层核实\n- `package_win7.ps1` 中的实际调用链是 `Invoke-ChromeRuntimeSmoke -> Get-ChromeIdsByMarker -> Stop-ProcessTreeByIds`。\n- `Stop-ProcessTreeByIds` 虽然是严格 helper，但它当前只在 `Invoke-ChromeRuntimeSmoke` 的 `finally` 局部 `try/catch` 中调用；因此现状并不会把清理失败泄露成出包失败。此前“会中断出包”的判断偏重，应下调为低等级可维护性提示。\n- `installer/aps_win7_chrome.iss` 中的调用链是 `BuildStopChromePowerShellParams -> TryStopApsChromeProcesses -> InitializeUninstall`。这里确实也使用 `Get-CimInstance -> Get-WmiObject` 的降级链，但它的 marker 是固定子串 `chrome109profile`，并不是与 Python / 打包脚本完全一致的“完整 profile 路径 marker”。\n\n### 4. 对既有 finding 的修订\n- `ps1-cleanup-throw-in-finally`：修订为“当前不会阻断出包，只是严格 helper 与 best-effort 清理语义分离不够直观”，严重级别由中下调为低，跟踪状态改为接受风险。\n- `cross-lang-chrome-enum-sync`：修订为“策略相似但口径未统一”，保留低等级接受风险。原因是 Python / 打包脚本按完整 profile 路径匹配，安装器按固定子串 `chrome109profile` 匹配；若未来调整 marker 口径，三处仍需同步。\n\n### 5. 回归核验结果\n- 已执行 `pytest tests/test_win7_launcher_runtime_paths.py -q`\n- 已执行 `python tests/regression_shared_runtime_state.py`\n- 已执行 `python tests/regression_runtime_contract_launcher.py`\n- 已执行 `python tests/regression_runtime_stop_cli.py`\n- 上述检查均通过，说明启动、契约、停机与浏览器清理主链路当前闭合。\n\n### 6. 修订后的总体意见\n- 本轮实现应从“有条件通过”上调为“通过（带低等级接受风险）”。\n- 当前无需因本 review 阻断；若继续收口，优先建议把安装器侧 marker 常量与运行时 profile 命名来源统一，减少 `chrome109profile` 与 `chrome109_profile` 的长期分叉。",
      "conclusionMarkdown": "经第四轮引用链复核后，原 review 中两条 finding 都需要降级和改写：一条属于表述过重，一条属于“完全一致”判断不准。综合源码、调用点、变量语义与回归结果，本轮修改应判定为通过，保留 2 条低等级接受风险即可。",
      "evidence": [
        {
          "path": "web/bootstrap/entrypoint.py",
          "lineStart": 115,
          "lineEnd": 137,
          "symbol": "configure_runtime_contract 调用 write_runtime_contract_file 传递 owner/profile/exe/host/port 字段",
          "excerptHash": "sha256:entrypoint-configure-runtime-contract"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 544,
          "lineEnd": 559,
          "symbol": "_runtime_contract_payload 写入 owner 与 chrome_profile_dir",
          "excerptHash": "sha256:launcher-runtime-contract-payload"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 586,
          "lineEnd": 621,
          "symbol": "write_runtime_contract_file",
          "excerptHash": "sha256:launcher-write-runtime-contract"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 479,
          "lineEnd": 518,
          "symbol": "read_runtime_contract",
          "excerptHash": "sha256:bat-read-runtime-contract"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 540,
          "lineEnd": 547,
          "symbol": "normalize_contract_owner",
          "excerptHash": "sha256:bat-normalize-contract-owner"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 392,
          "lineEnd": 410,
          "symbol": "try_reuse_by_contract",
          "excerptHash": "sha256:bat-try-reuse-by-contract"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 902,
          "symbol": "_list_aps_chrome_pids 与 stop_aps_chrome_processes",
          "excerptHash": "sha256:launcher-chrome-pid-chain"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 923,
          "lineEnd": 973,
          "symbol": "stop_runtime_from_dir 调用 _stop_aps_chrome_if_requested",
          "excerptHash": "sha256:launcher-stop-runtime-chain"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 244,
          "lineEnd": 339,
          "symbol": "Stop-ProcessTreeByIds 与 Invoke-ChromeRuntimeSmoke finally 清理",
          "excerptHash": "sha256:ps1-smoke-cleanup-chain"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 56,
          "lineEnd": 147,
          "symbol": "BuildStopChromePowerShellParams -> TryStopApsChromeProcesses -> InitializeUninstall",
          "excerptHash": "sha256:iss-stop-chrome-chain"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 132,
          "lineEnd": 200,
          "symbol": "停机失败闭合与静态守卫",
          "excerptHash": "sha256:test-win7-launcher-runtime-paths"
        },
        {
          "path": "tests/regression_shared_runtime_state.py",
          "lineStart": 50,
          "lineEnd": 123,
          "symbol": "共享运行时状态回归",
          "excerptHash": "sha256:test-shared-runtime-state"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py",
          "lineStart": 51,
          "lineEnd": 109,
          "symbol": "运行时契约读写回归",
          "excerptHash": "sha256:test-runtime-contract-launcher"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 140,
          "lineEnd": 177,
          "symbol": "runtime-stop 真实停机回归",
          "excerptHash": "sha256:test-runtime-stop-cli"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "web/bootstrap/entrypoint.py",
        "web/bootstrap/launcher.py",
        ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
        "installer/aps_win7_chrome.iss",
        "tests/test_win7_launcher_runtime_paths.py",
        "tests/regression_shared_runtime_state.py",
        "tests/regression_runtime_contract_launcher.py",
        "tests/regression_runtime_stop_cli.py",
        "DELIVERY_WIN7.md",
        "installer/README_WIN7_INSTALLER.md"
      ],
      "recommendedNextAction": "当前无需因本 review 阻断；若继续收口，优先统一 installer 侧 marker 常量与运行时 profile 命名来源。",
      "findingIds": [
        "ps1-cleanup-throw-in-finally",
        "cross-lang-chrome-enum-sync"
      ]
    },
    {
      "id": "M5",
      "title": "第五轮：接受风险收口复核",
      "status": "completed",
      "recordedAt": "2026-04-07T02:51:18.964Z",
      "summaryMarkdown": "## 第五轮复核：接受风险已收口\n\n### 1. 打包脚本清理语义收口\n- 复核 `.limcode/skills/aps-package-win7/scripts/package_win7.ps1` 可见：`Stop-ProcessTreeByIds` 仍保留严格停止语义，`taskkill` 非零即抛错，没有被改成静默成功。\n- 新增 `Stop-ProcessTreeByIdsBestEffort` 仅作为包装层出现，并且当前仅在 `Invoke-ChromeRuntimeSmoke` 的 `finally` 清理分支被调用。\n- `finally` 中已移除原先包住严格 helper 的空 `catch`，清理语义改为“显式容错 helper + 其他步骤各自独立清理”，不再依赖调用点隐式吞异常。\n\n### 2. 浏览器进程 marker 口径收口\n- 复核 `installer/aps_win7_chrome.iss` 可见：新增 `CurrentUserChromeProfilePath()`，其返回值与 `web/bootstrap/launcher.py:default_chrome_profile_dir()`、`assets/启动_排产系统_Chrome.bat` 的默认 profile 路径一致，均为 `%LOCALAPPDATA%\\\\APS\\\\Chrome109Profile`。\n- `BuildStopChromePowerShellParams` 已改为接收 profile 绝对路径参数，并在写入 PowerShell 前先做单引号转义；卸载脚本不再使用裸字串 `chrome109profile`。\n- `TryStopApsChromeProcesses -> BuildStopChromePowerShellParams(CurrentUserChromeProfilePath)` 调用链已把安装器侧进程枚举口径收口到“当前账户 profile 绝对路径 marker”。\n\n### 3. 引用链复核\n- `web/bootstrap/entrypoint.py:configure_runtime_contract()` 仍把 `default_chrome_profile_dir(runtime_dir)` 写入运行时契约。\n- `web/bootstrap/launcher.py:stop_runtime_from_dir()` 在无契约回退路径中仍通过 `default_chrome_profile_dir(runtime_dir_abs)` 计算默认 profile。\n- `assets/启动_排产系统_Chrome.bat` 仍固定使用 `%LOCALAPPDATA%\\\\APS\\\\Chrome109Profile`；因此启动、契约、停机、卸载四处 profile 口径现在一致。\n\n### 4. 验证结果\n- `python -m pytest tests/test_win7_launcher_runtime_paths.py -q`：21 通过。\n- `python tests/regression_runtime_contract_launcher.py`：输出 `OK`。\n- `python tests/regression_shared_runtime_state.py`：输出 `OK`。\n- `python tests/regression_runtime_stop_cli.py`：输出 `OK`。\n\n### 5. 结论\n- `ps1-cleanup-throw-in-finally` 已通过显式 best-effort helper 收口。\n- `cross-lang-chrome-enum-sync` 已通过统一到 profile 绝对路径 marker 收口。\n- 本次修改未引入新的静默回退或过度兜底，现有启动链、契约链、停机链与卸载清理链均保持通过。",
      "conclusionMarkdown": "经第五轮引用链复核与回归验证，原 review 中两条低等级接受风险均已完成代码收口并有测试证据支撑，跟踪状态可改为 `fixed`。",
      "evidence": [
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 244,
          "lineEnd": 329,
          "symbol": "严格停止与容错清理 helper 收口"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 56,
          "lineEnd": 100,
          "symbol": "CurrentUserChromeProfilePath 与 stop helper 调用链"
        },
        {
          "path": "web/bootstrap/entrypoint.py",
          "lineStart": 123,
          "lineEnd": 137,
          "symbol": "configure_runtime_contract 写入 chrome_profile_dir"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 514,
          "lineEnd": 518,
          "symbol": "default_chrome_profile_dir"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 939,
          "lineEnd": 941,
          "symbol": "stop_runtime_from_dir 默认 profile 路径"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 57,
          "lineEnd": 62,
          "symbol": "启动批处理默认 profile 路径"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 86,
          "lineEnd": 272,
          "symbol": "新增静态守卫与行为守卫"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py",
          "lineStart": 51,
          "lineEnd": 109,
          "symbol": "运行时契约回归"
        },
        {
          "path": "tests/regression_shared_runtime_state.py",
          "lineStart": 50,
          "lineEnd": 123,
          "symbol": "共享状态回归"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py",
          "lineStart": 140,
          "lineEnd": 177,
          "symbol": "停机回归"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        }
      ],
      "reviewedModules": [
        ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
        "installer/aps_win7_chrome.iss",
        "web/bootstrap/entrypoint.py",
        "web/bootstrap/launcher.py",
        "assets/启动_排产系统_Chrome.bat",
        "tests/test_win7_launcher_runtime_paths.py",
        "tests/regression_runtime_contract_launcher.py",
        "tests/regression_shared_runtime_state.py",
        "tests/regression_runtime_stop_cli.py"
      ],
      "recommendedNextAction": "当前无需继续跟踪本次两条风险；后续若再改 profile 命名或浏览器清理协议，继续按同一口径同步四处实现。",
      "findingIds": [
        "ps1-cleanup-throw-in-finally",
        "cross-lang-chrome-enum-sync",
        "F-ps1-cleanup-throw-in-finally-已修复",
        "F-cross-lang-chrome-enum-sync-已修复"
      ]
    }
  ],
  "findings": [
    {
      "id": "ps1-cleanup-throw-in-finally",
      "severity": "low",
      "category": "maintainability",
      "title": "冒烟清理语义依赖调用点容错",
      "descriptionMarkdown": "复核 `Invoke-ChromeRuntimeSmoke -> Stop-ProcessTreeByIds` 调用链后确认，`Stop-ProcessTreeByIds` 当前只在 `finally` 内的局部 `try/catch` 中调用，现状并不会把 `taskkill` 非零返回泄露为出包失败。原先“会不必要地中断出包”的判断偏重。实际风险仅在于严格 helper 的语义与 best-effort 清理语义分散在调用点，后续维护者若重构时忽略这一层包装，才可能引入行为变化。",
      "recommendationMarkdown": "当前无需为此阻断；如后续继续打磨，可在 helper 名称、注释或额外 wrapper 上显式表达“严格停止”和“容错清理”的语义差异。",
      "evidence": [
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 244,
          "lineEnd": 255,
          "symbol": "Stop-ProcessTreeByIds"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 316,
          "lineEnd": 325,
          "symbol": "finally cleanup"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 244,
          "lineEnd": 255,
          "symbol": "Stop-ProcessTreeByIds",
          "excerptHash": "sha256:ps1-stop-process-tree"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 316,
          "lineEnd": 325,
          "symbol": "Invoke-ChromeRuntimeSmoke finally",
          "excerptHash": "sha256:ps1-invoke-smoke-finally"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 244,
          "lineEnd": 329,
          "symbol": "Stop-ProcessTreeByIds 与 Stop-ProcessTreeByIdsBestEffort"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 202,
          "lineEnd": 215,
          "symbol": "best-effort wrapper 守卫"
        }
      ],
      "relatedMilestoneIds": [
        "M2",
        "M4",
        "M5"
      ],
      "trackingStatus": "accepted_risk"
    },
    {
      "id": "cross-lang-chrome-enum-sync",
      "severity": "low",
      "category": "maintainability",
      "title": "Chrome 进程枚举策略相似但口径未统一",
      "descriptionMarkdown": "复核 `_list_aps_chrome_pids`、`Get-ChromeIdsByMarker` 与安装器卸载脚本后确认：三处都使用命令行 marker + `Get-CimInstance -> Get-WmiObject` 降级链，但 marker 并不完全一致。Python 与打包脚本按完整 profile 路径匹配；安装器仅按固定子串 `chrome109profile` 匹配。因此原先“完全一致但代码重复”的说法不准确。真实风险是未来如果调整 marker 口径或 profile 命名，三处都要同步考虑，否则可能出现覆盖范围不一致。",
      "recommendationMarkdown": "作为接受风险在文档中留痕：三处进程枚举策略必须同步修改。当前阶段不需要强制统一实现。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 856,
          "symbol": "_list_aps_chrome_pids marker=完整 profile 路径",
          "excerptHash": "sha256:launcher-profile-marker"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 201,
          "lineEnd": 241,
          "symbol": "Get-ChromeIdsByMarker marker=完整 profile 路径",
          "excerptHash": "sha256:ps1-profile-marker"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 58,
          "lineEnd": 72,
          "symbol": "BuildStopChromePowerShellParams marker=chrome109profile",
          "excerptHash": "sha256:iss-fixed-marker"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 56,
          "lineEnd": 100,
          "symbol": "CurrentUserChromeProfilePath 与 BuildStopChromePowerShellParams"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 514,
          "lineEnd": 518,
          "symbol": "default_chrome_profile_dir"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 57,
          "lineEnd": 62,
          "symbol": "批处理默认 profile 路径"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 86,
          "lineEnd": 272,
          "symbol": "profile 路径与 installer marker 守卫"
        }
      ],
      "relatedMilestoneIds": [
        "M2",
        "M4",
        "M5"
      ],
      "trackingStatus": "accepted_risk"
    },
    {
      "id": "F-ps1-cleanup-throw-in-finally-已修复",
      "severity": "low",
      "category": "other",
      "title": "`ps1-cleanup-throw-in-finally` 已修复",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        }
      ],
      "relatedMilestoneIds": [
        "M5"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-cross-lang-chrome-enum-sync-已修复",
      "severity": "low",
      "category": "other",
      "title": "`cross-lang-chrome-enum-sync` 已修复",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "web/bootstrap/entrypoint.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_stop_cli.py"
        }
      ],
      "relatedMilestoneIds": [
        "M5"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:72ed53edcbb5a2cdecff8074011a3622735676c8a3abfc61afb4db604734bb9d",
    "generatedAt": "2026-04-07T02:52:12.239Z",
    "locale": "zh-CN"
  }
}
```
