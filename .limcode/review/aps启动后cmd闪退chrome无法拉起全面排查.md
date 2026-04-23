# APS启动后CMD闪退Chrome无法拉起全面排查
- 日期: 2026-04-07
- 概述: 对"安装完成后点击快捷方式CMD闪一下就关闭、Chrome未启动"的问题进行全链路排查
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# APS 启动后 CMD 闪退、Chrome 无法拉起 — 全面排查

**日期**: 2026-04-06

## 审查范围

- 桌面快捷方式定义（Inno Setup `.iss` 文件）
- 启动器脚本 `assets/启动_排产系统_Chrome.bat`
- 应用入口 `app.py` → `web/bootstrap/entrypoint.py` → `factory.py` → `launcher.py`
- PyInstaller 打包配置 `build_win7_onedir.bat`
- 运行时路径解析 `web/bootstrap/paths.py`
- 配置文件 `config.py`
- 健康检测接口 `web/routes/system_health.py`
- 安装器与交付文档

## 核心启动链路

```
用户点击快捷方式
  → cmd.exe /c "启动_排产系统_Chrome.bat"
    → 查找 APP_EXE（排产系统.exe）
    → 查找 Chrome 运行时
    → 检查是否已有运行实例（锁/契约/健康检测）
    → start "" "排产系统.exe"  （后台启动应用服务）
    → 轮询等待就绪（最多45秒）
    → start "" /D "chrome目录" "chrome.exe" --app="http://..." 
    → exit /b 0  （CMD 窗口关闭）
```

## 评审摘要

- 当前状态: 已完成
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7.iss, build_win7_onedir.bat, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, web/bootstrap/factory.py, web/bootstrap/paths.py, config.py, app.py, installer/aps_win7_chrome.iss, installer/aps_win7_legacy.iss, build_win7_installer.bat, stage_chrome109_to_dist.bat, web/routes/system_health.py, DELIVERY_WIN7.md, installer/README_WIN7_INSTALLER.md
- 当前进度: 已记录 1 个里程碑；最新：M1
- 里程碑总数: 1
- 已完成里程碑: 1
- 问题总数: 5
- 问题严重级别分布: 高 1 / 中 2 / 低 2
- 最新结论: ## 全面排查结论 ### 现象解释 **CMD"闪一下就关"说明启动器脚本正常走到了 `exit /b 0`（成功退出路径）**。启动器中所有错误路径（应用未找到、Chrome 未找到、被锁、超时、健康检测失败等）都包含 `pause`（等待用户按键），不会产生"闪退"现象。因此可以确认：**启动器认为一切正常**——它找到了 Chrome、启动了应用（或复用了已有实例）、调用了 Chrome 的 `start` 命令，然后正常退出。 ### 根本原因 **核心问题是 Chrome 启动后无存活验证。** Windows `start` 命令的返回码只反映"能否发起进程创建"，不反映"目标进程是否正常运行"。即使 Chrome 因为 DLL 缺失、沙箱异常、GPU 驱动不兼容、配置文件损坏等原因立即崩溃，`start` 仍然返回 0。脚本在 `start` Chrome 之后直接 `exit /b 0`，完全不验证 Chrome 是否真的在运行。 ### 确定问题的排障步骤 1. **查看 `launcher.log`**：路径为 `C:\ProgramData\APS\shared-data\logs\launcher.log`，确认 `chrome_source`、`chrome_exe`、`chrome_cmd` 的值 2. **手动执行 `chrome_cmd`**：将日志中记录的完整 Chrome 启动命令复制到 CMD 中执行，观察 Chrome 是否能正常启动。这一步可以确定是"启动器问题"还是"Chrome 本体问题" 3. **检查 Chrome 运行时是否正确安装**：确认 `C:\Program Files\APS\Chrome109\chrome.exe` 存在且完整 4. **检查残留锁文件**：确认 `C:\ProgramData\APS\shared-data\logs\aps_runtime.lock` 是否存在。如存在，手动删除后重试 ### 应修复的代码问题（共5个） | 编号 | 严重程度 | 问题 | 修复建议 | |------|----------|------|----------| | F1 | 严重 | Chrome 启动后无存活验证 | 在 `start` Chrome 后延迟 2-3 秒，用 `tasklist` 检查 Chrome 进程是否存活。若不存活则 `pause` 并显示 `launcher.log` 路径 | | F2 | 中 | `--windowed` 导致应用崩溃不可见 | 在 `start` 应用后增加1-2秒进程存活检测 | | F3 | 中 | `wmic` 在新版 Win10 上已弃用 | 将进程检测改为 `tasklist /FI "PID eq ..." /NH /FO CSV`，与 Python 端一致 | | F4 | 低 | 生产启动器缺少 `chcp` 编码设置 | 在启动器开头添加 `chcp 65001 >nul 2>&1` | | F5 | 低 | `cmd /c` 使诊断输出不可见 | 与 F1 联动解决——Chrome 不存活时 `pause` |
- 下一步建议: 先到目标机检查 launcher.log 确认 Chrome 失败的具体原因，然后修复 F1（Chrome 存活验证）和 F3（wmic 替换为 tasklist），这两个修复可以从根本上解决"闪退无反馈"问题。
- 总体结论: 需要后续跟进

## 评审发现

### start 命令返回码不可靠，Chrome 崩溃无法检测

- ID: F1
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  启动器第223行使用 start chrome.exe 启动 Chrome，然后第224行通过 ERRORLEVEL 检查返回码。但 Windows 的 start 命令只反映能否发起进程创建，而不反映目标进程是否正常运行。即使 Chrome 因 DLL 缺失、沙箱异常、GPU 驱动崩溃等原因立即退出，start 仍返回 0。脚本在第232行直接 exit /b 0 退出，没有后续验证。这是最可能导致 CMD闪一下Chrome不出现 的直接原因。
- 建议:

  在 start Chrome 之后加入 2-3 秒延迟检测：用 tasklist 或检查 Chrome profile 目录中的锁文件验证 Chrome 是否真正存活。若未存活则显示诊断信息并 pause。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:223-232`
  - `assets/启动_排产系统_Chrome.bat`

### 应用无窗口打包导致崩溃不可见

- ID: F2
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  PyInstaller 使用 --windowed 标志打包，应用进程没有控制台窗口。如果崩溃发生在 Python 运行时初始化之前（如缺少 DLL、解包失败），则无任何可见反馈。启动器的45秒超时可以兜底，但用户可能在此之前放弃操作。
- 建议:

  在启动器中增加应用进程存活检测：start 之后等1-2秒用 tasklist 检查应用进程是否还在。若已退出立即提示并显示日志路径。
- 证据:
  - `build_win7_onedir.bat:41`
  - `build_win7_onedir.bat`

### wmic 弃用导致残留锁阻塞启动

- ID: F3
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  启动器使用 where wmic 检测可用性然后用 wmic process 检查进程。在 Win10 22H2+ 上 wmic 已弃用。如果 wmic 不可用且存在残留 aps_runtime.lock 文件，LOCK_ACTIVE 被设为 UNKNOWN，最终走到 BLOCKED_UNCERTAIN 路径。虽然有 pause 但会阻止正常启动。Python 端的 _pid_exists 正确使用了 tasklist，但批处理端未跟进。
- 建议:

  将批处理中的 wmic 进程检测改为 tasklist /FI PID eq ... /NH /FO CSV 方案，与 Python 端保持一致。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:506-525`
  - `assets/启动_排产系统_Chrome.bat`

### 生产启动器缺少字符编码设置

- ID: F4
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  开发用 start.bat 设置了 chcp 65001，但生产用的启动器没有任何 chcp 设置。应用可执行文件名为中文，在混合语言环境或区域设置异常的机器上可能导致路径解析失败。
- 建议:

  考虑在启动器开头添加 chcp 65001，或确保脚本内所有字符串操作都兼容系统默认 ANSI 编码。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:1-5`
  - `assets/启动_排产系统_Chrome.bat`

### 快捷方式 cmd /c 使正常路径诊断信息不可见

- ID: F5
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  Inno Setup 快捷方式使用 cmd.exe /c 执行启动器脚本。脚本中所有 echo 输出在正常退出路径中都会瞬间消失。只有 pause 路径对用户可见。当 Chrome 静默失败时用户看不到任何有用信息。
- 建议:

  在 OPEN_CHROME 路径的 Chrome 启动后如果检测到 Chrome 未存活应该 pause 并显示 launcher.log 路径。
- 证据:
  - `installer/aps_win7.iss:58-59`
  - `installer/aps_win7.iss`

## 评审里程碑

### M1 · 启动链路全链路分析与根因定位

- 状态: 已完成
- 记录时间: 2026-04-07T00:36:56.939Z
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7.iss, build_win7_onedir.bat, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, web/bootstrap/factory.py, web/bootstrap/paths.py, config.py, app.py
- 摘要:

  ## 分析方法

  完整阅读了从 Inno Setup 快捷方式到启动器脚本到应用入口到运行时路径到健康检测的完整链路代码，逐条排查所有可能导致CMD闪退Chrome不出现的路径。

  ## 现象还原

  用户报告的行为：安装完成后点击快捷方式，CMD窗口闪一下就关闭，Chrome浏览器未出现。

  ## 关键推理

  **CMD闪一下就关说明脚本正常走到了 exit /b 0。** 启动器脚本中所有错误路径（应用找不到、Chrome找不到、被锁、超时等）都有 pause，不会闪退。唯一没有 pause 的路径是**成功路径**：到达 OPEN_CHROME 标签 → 调用 start 启动 Chrome → exit /b 0。

  **这意味着启动器认为一切正常**——它找到了Chrome、启动了应用或复用了现有实例、调用了Chrome的start命令然后正常退出。但Chrome实际上并没有出现。

  ## 定位到的5个根因/风险点

  1. **start命令返回码不可靠**（严重）：start即使Chrome无法启动也返回0
  2. **Chrome启动后无存活验证**（严重）：脚本start之后立即exit
  3. **--windowed导致应用崩溃无反馈**（中）：PyInstaller无窗口模式
  4. **wmic弃用导致残留锁阻塞**（中）：新版Win10可能无wmic
  5. **cmd /c使诊断输出消失**（低）：正常路径echo瞬间消失
- 结论:

  CMD闪退+Chrome不出现的最可能原因是：启动器正确到达了Chrome启动步骤，但Chrome启动后立即崩溃，而脚本缺乏Chrome存活验证机制。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:215-232#OPEN_CHROME`
  - `assets/启动_排产系统_Chrome.bat:506-525#lock_is_active (wmic)`
  - `build_win7_onedir.bat:41#--windowed`
  - `installer/aps_win7.iss:58-59#快捷方式定义 cmd /c`
- 下一步建议:

  查看目标机 C:\ProgramData\APS\shared-data\logs\launcher.log 中的 chrome_cmd 行，手动在 CMD 中执行以定位 Chrome 具体失败原因。
- 问题:
  - [高] 其他: start 命令返回码不可靠，Chrome 崩溃无法检测
  - [中] 其他: 应用无窗口打包导致崩溃不可见
  - [中] 其他: wmic 弃用导致残留锁阻塞启动
  - [低] 其他: 生产启动器缺少字符编码设置
  - [低] 其他: 快捷方式 cmd /c 使正常路径诊断信息不可见

## 最终结论

## 全面排查结论

### 现象解释

**CMD"闪一下就关"说明启动器脚本正常走到了 `exit /b 0`（成功退出路径）**。启动器中所有错误路径（应用未找到、Chrome 未找到、被锁、超时、健康检测失败等）都包含 `pause`（等待用户按键），不会产生"闪退"现象。因此可以确认：**启动器认为一切正常**——它找到了 Chrome、启动了应用（或复用了已有实例）、调用了 Chrome 的 `start` 命令，然后正常退出。

### 根本原因

**核心问题是 Chrome 启动后无存活验证。** Windows `start` 命令的返回码只反映"能否发起进程创建"，不反映"目标进程是否正常运行"。即使 Chrome 因为 DLL 缺失、沙箱异常、GPU 驱动不兼容、配置文件损坏等原因立即崩溃，`start` 仍然返回 0。脚本在 `start` Chrome 之后直接 `exit /b 0`，完全不验证 Chrome 是否真的在运行。

### 确定问题的排障步骤

1. **查看 `launcher.log`**：路径为 `C:\ProgramData\APS\shared-data\logs\launcher.log`，确认 `chrome_source`、`chrome_exe`、`chrome_cmd` 的值
2. **手动执行 `chrome_cmd`**：将日志中记录的完整 Chrome 启动命令复制到 CMD 中执行，观察 Chrome 是否能正常启动。这一步可以确定是"启动器问题"还是"Chrome 本体问题"
3. **检查 Chrome 运行时是否正确安装**：确认 `C:\Program Files\APS\Chrome109\chrome.exe` 存在且完整
4. **检查残留锁文件**：确认 `C:\ProgramData\APS\shared-data\logs\aps_runtime.lock` 是否存在。如存在，手动删除后重试

### 应修复的代码问题（共5个）

| 编号 | 严重程度 | 问题 | 修复建议 |
|------|----------|------|----------|
| F1 | 严重 | Chrome 启动后无存活验证 | 在 `start` Chrome 后延迟 2-3 秒，用 `tasklist` 检查 Chrome 进程是否存活。若不存活则 `pause` 并显示 `launcher.log` 路径 |
| F2 | 中 | `--windowed` 导致应用崩溃不可见 | 在 `start` 应用后增加1-2秒进程存活检测 |
| F3 | 中 | `wmic` 在新版 Win10 上已弃用 | 将进程检测改为 `tasklist /FI "PID eq ..." /NH /FO CSV`，与 Python 端一致 |
| F4 | 低 | 生产启动器缺少 `chcp` 编码设置 | 在启动器开头添加 `chcp 65001 >nul 2>&1` |
| F5 | 低 | `cmd /c` 使诊断输出不可见 | 与 F1 联动解决——Chrome 不存活时 `pause` |

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnnw0rlx-rh275n",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T00:37:26.780Z",
  "finalizedAt": "2026-04-07T00:37:26.780Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "APS启动后CMD闪退Chrome无法拉起全面排查",
    "date": "2026-04-07",
    "overview": "对\"安装完成后点击快捷方式CMD闪一下就关闭、Chrome未启动\"的问题进行全链路排查"
  },
  "scope": {
    "markdown": "# APS 启动后 CMD 闪退、Chrome 无法拉起 — 全面排查\n\n**日期**: 2026-04-06\n\n## 审查范围\n\n- 桌面快捷方式定义（Inno Setup `.iss` 文件）\n- 启动器脚本 `assets/启动_排产系统_Chrome.bat`\n- 应用入口 `app.py` → `web/bootstrap/entrypoint.py` → `factory.py` → `launcher.py`\n- PyInstaller 打包配置 `build_win7_onedir.bat`\n- 运行时路径解析 `web/bootstrap/paths.py`\n- 配置文件 `config.py`\n- 健康检测接口 `web/routes/system_health.py`\n- 安装器与交付文档\n\n## 核心启动链路\n\n```\n用户点击快捷方式\n  → cmd.exe /c \"启动_排产系统_Chrome.bat\"\n    → 查找 APP_EXE（排产系统.exe）\n    → 查找 Chrome 运行时\n    → 检查是否已有运行实例（锁/契约/健康检测）\n    → start \"\" \"排产系统.exe\"  （后台启动应用服务）\n    → 轮询等待就绪（最多45秒）\n    → start \"\" /D \"chrome目录\" \"chrome.exe\" --app=\"http://...\" \n    → exit /b 0  （CMD 窗口关闭）\n```"
  },
  "summary": {
    "latestConclusion": "## 全面排查结论\n\n### 现象解释\n\n**CMD\"闪一下就关\"说明启动器脚本正常走到了 `exit /b 0`（成功退出路径）**。启动器中所有错误路径（应用未找到、Chrome 未找到、被锁、超时、健康检测失败等）都包含 `pause`（等待用户按键），不会产生\"闪退\"现象。因此可以确认：**启动器认为一切正常**——它找到了 Chrome、启动了应用（或复用了已有实例）、调用了 Chrome 的 `start` 命令，然后正常退出。\n\n### 根本原因\n\n**核心问题是 Chrome 启动后无存活验证。** Windows `start` 命令的返回码只反映\"能否发起进程创建\"，不反映\"目标进程是否正常运行\"。即使 Chrome 因为 DLL 缺失、沙箱异常、GPU 驱动不兼容、配置文件损坏等原因立即崩溃，`start` 仍然返回 0。脚本在 `start` Chrome 之后直接 `exit /b 0`，完全不验证 Chrome 是否真的在运行。\n\n### 确定问题的排障步骤\n\n1. **查看 `launcher.log`**：路径为 `C:\\ProgramData\\APS\\shared-data\\logs\\launcher.log`，确认 `chrome_source`、`chrome_exe`、`chrome_cmd` 的值\n2. **手动执行 `chrome_cmd`**：将日志中记录的完整 Chrome 启动命令复制到 CMD 中执行，观察 Chrome 是否能正常启动。这一步可以确定是\"启动器问题\"还是\"Chrome 本体问题\"\n3. **检查 Chrome 运行时是否正确安装**：确认 `C:\\Program Files\\APS\\Chrome109\\chrome.exe` 存在且完整\n4. **检查残留锁文件**：确认 `C:\\ProgramData\\APS\\shared-data\\logs\\aps_runtime.lock` 是否存在。如存在，手动删除后重试\n\n### 应修复的代码问题（共5个）\n\n| 编号 | 严重程度 | 问题 | 修复建议 |\n|------|----------|------|----------|\n| F1 | 严重 | Chrome 启动后无存活验证 | 在 `start` Chrome 后延迟 2-3 秒，用 `tasklist` 检查 Chrome 进程是否存活。若不存活则 `pause` 并显示 `launcher.log` 路径 |\n| F2 | 中 | `--windowed` 导致应用崩溃不可见 | 在 `start` 应用后增加1-2秒进程存活检测 |\n| F3 | 中 | `wmic` 在新版 Win10 上已弃用 | 将进程检测改为 `tasklist /FI \"PID eq ...\" /NH /FO CSV`，与 Python 端一致 |\n| F4 | 低 | 生产启动器缺少 `chcp` 编码设置 | 在启动器开头添加 `chcp 65001 >nul 2>&1` |\n| F5 | 低 | `cmd /c` 使诊断输出不可见 | 与 F1 联动解决——Chrome 不存活时 `pause` |",
    "recommendedNextAction": "先到目标机检查 launcher.log 确认 Chrome 失败的具体原因，然后修复 F1（Chrome 存活验证）和 F3（wmic 替换为 tasklist），这两个修复可以从根本上解决\"闪退无反馈\"问题。",
    "reviewedModules": [
      "assets/启动_排产系统_Chrome.bat",
      "installer/aps_win7.iss",
      "build_win7_onedir.bat",
      "web/bootstrap/entrypoint.py",
      "web/bootstrap/launcher.py",
      "web/bootstrap/factory.py",
      "web/bootstrap/paths.py",
      "config.py",
      "app.py",
      "installer/aps_win7_chrome.iss",
      "installer/aps_win7_legacy.iss",
      "build_win7_installer.bat",
      "stage_chrome109_to_dist.bat",
      "web/routes/system_health.py",
      "DELIVERY_WIN7.md",
      "installer/README_WIN7_INSTALLER.md"
    ]
  },
  "stats": {
    "totalMilestones": 1,
    "completedMilestones": 1,
    "totalFindings": 5,
    "severity": {
      "high": 1,
      "medium": 2,
      "low": 2
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "启动链路全链路分析与根因定位",
      "status": "completed",
      "recordedAt": "2026-04-07T00:36:56.939Z",
      "summaryMarkdown": "## 分析方法\n\n完整阅读了从 Inno Setup 快捷方式到启动器脚本到应用入口到运行时路径到健康检测的完整链路代码，逐条排查所有可能导致CMD闪退Chrome不出现的路径。\n\n## 现象还原\n\n用户报告的行为：安装完成后点击快捷方式，CMD窗口闪一下就关闭，Chrome浏览器未出现。\n\n## 关键推理\n\n**CMD闪一下就关说明脚本正常走到了 exit /b 0。** 启动器脚本中所有错误路径（应用找不到、Chrome找不到、被锁、超时等）都有 pause，不会闪退。唯一没有 pause 的路径是**成功路径**：到达 OPEN_CHROME 标签 → 调用 start 启动 Chrome → exit /b 0。\n\n**这意味着启动器认为一切正常**——它找到了Chrome、启动了应用或复用了现有实例、调用了Chrome的start命令然后正常退出。但Chrome实际上并没有出现。\n\n## 定位到的5个根因/风险点\n\n1. **start命令返回码不可靠**（严重）：start即使Chrome无法启动也返回0\n2. **Chrome启动后无存活验证**（严重）：脚本start之后立即exit\n3. **--windowed导致应用崩溃无反馈**（中）：PyInstaller无窗口模式\n4. **wmic弃用导致残留锁阻塞**（中）：新版Win10可能无wmic\n5. **cmd /c使诊断输出消失**（低）：正常路径echo瞬间消失",
      "conclusionMarkdown": "CMD闪退+Chrome不出现的最可能原因是：启动器正确到达了Chrome启动步骤，但Chrome启动后立即崩溃，而脚本缺乏Chrome存活验证机制。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 215,
          "lineEnd": 232,
          "symbol": "OPEN_CHROME"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 506,
          "lineEnd": 525,
          "symbol": "lock_is_active (wmic)"
        },
        {
          "path": "build_win7_onedir.bat",
          "lineStart": 41,
          "lineEnd": 41,
          "symbol": "--windowed"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 58,
          "lineEnd": 59,
          "symbol": "快捷方式定义 cmd /c"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "installer/aps_win7.iss",
        "build_win7_onedir.bat",
        "web/bootstrap/entrypoint.py",
        "web/bootstrap/launcher.py",
        "web/bootstrap/factory.py",
        "web/bootstrap/paths.py",
        "config.py",
        "app.py"
      ],
      "recommendedNextAction": "查看目标机 C:\\ProgramData\\APS\\shared-data\\logs\\launcher.log 中的 chrome_cmd 行，手动在 CMD 中执行以定位 Chrome 具体失败原因。",
      "findingIds": [
        "F1",
        "F2",
        "F3",
        "F4",
        "F5"
      ]
    }
  ],
  "findings": [
    {
      "id": "F1",
      "severity": "high",
      "category": "other",
      "title": "start 命令返回码不可靠，Chrome 崩溃无法检测",
      "descriptionMarkdown": "启动器第223行使用 start chrome.exe 启动 Chrome，然后第224行通过 ERRORLEVEL 检查返回码。但 Windows 的 start 命令只反映能否发起进程创建，而不反映目标进程是否正常运行。即使 Chrome 因 DLL 缺失、沙箱异常、GPU 驱动崩溃等原因立即退出，start 仍返回 0。脚本在第232行直接 exit /b 0 退出，没有后续验证。这是最可能导致 CMD闪一下Chrome不出现 的直接原因。",
      "recommendationMarkdown": "在 start Chrome 之后加入 2-3 秒延迟检测：用 tasklist 或检查 Chrome profile 目录中的锁文件验证 Chrome 是否真正存活。若未存活则显示诊断信息并 pause。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 223,
          "lineEnd": 232
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F2",
      "severity": "medium",
      "category": "other",
      "title": "应用无窗口打包导致崩溃不可见",
      "descriptionMarkdown": "PyInstaller 使用 --windowed 标志打包，应用进程没有控制台窗口。如果崩溃发生在 Python 运行时初始化之前（如缺少 DLL、解包失败），则无任何可见反馈。启动器的45秒超时可以兜底，但用户可能在此之前放弃操作。",
      "recommendationMarkdown": "在启动器中增加应用进程存活检测：start 之后等1-2秒用 tasklist 检查应用进程是否还在。若已退出立即提示并显示日志路径。",
      "evidence": [
        {
          "path": "build_win7_onedir.bat",
          "lineStart": 41,
          "lineEnd": 41
        },
        {
          "path": "build_win7_onedir.bat"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F3",
      "severity": "medium",
      "category": "other",
      "title": "wmic 弃用导致残留锁阻塞启动",
      "descriptionMarkdown": "启动器使用 where wmic 检测可用性然后用 wmic process 检查进程。在 Win10 22H2+ 上 wmic 已弃用。如果 wmic 不可用且存在残留 aps_runtime.lock 文件，LOCK_ACTIVE 被设为 UNKNOWN，最终走到 BLOCKED_UNCERTAIN 路径。虽然有 pause 但会阻止正常启动。Python 端的 _pid_exists 正确使用了 tasklist，但批处理端未跟进。",
      "recommendationMarkdown": "将批处理中的 wmic 进程检测改为 tasklist /FI PID eq ... /NH /FO CSV 方案，与 Python 端保持一致。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 506,
          "lineEnd": 525
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F4",
      "severity": "low",
      "category": "other",
      "title": "生产启动器缺少字符编码设置",
      "descriptionMarkdown": "开发用 start.bat 设置了 chcp 65001，但生产用的启动器没有任何 chcp 设置。应用可执行文件名为中文，在混合语言环境或区域设置异常的机器上可能导致路径解析失败。",
      "recommendationMarkdown": "考虑在启动器开头添加 chcp 65001，或确保脚本内所有字符串操作都兼容系统默认 ANSI 编码。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 1,
          "lineEnd": 5
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F5",
      "severity": "low",
      "category": "other",
      "title": "快捷方式 cmd /c 使正常路径诊断信息不可见",
      "descriptionMarkdown": "Inno Setup 快捷方式使用 cmd.exe /c 执行启动器脚本。脚本中所有 echo 输出在正常退出路径中都会瞬间消失。只有 pause 路径对用户可见。当 Chrome 静默失败时用户看不到任何有用信息。",
      "recommendationMarkdown": "在 OPEN_CHROME 路径的 Chrome 启动后如果检测到 Chrome 未存活应该 pause 并显示 launcher.log 路径。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 58,
          "lineEnd": 59
        },
        {
          "path": "installer/aps_win7.iss"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:0b495f303ffde3cbb5f1d6878254681c0bfac2f2e0a33f1b0ef442e360b4fa6d",
    "generatedAt": "2026-04-07T00:37:26.780Z",
    "locale": "zh-CN"
  }
}
```
