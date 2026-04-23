# APS启动链路与Chrome接受风险收口 followup review
- 日期: 2026-04-07
- 概述: 对两条接受风险完成实现后的引用链、路径口径与回归结果做独立收口复核。
- 状态: 已完成
- 总体结论: 通过

## 评审范围

# APS启动链路与Chrome接受风险收口 followup review

- 日期：2026-04-07
- 范围：`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`、`installer/aps_win7_chrome.iss`、`web/bootstrap/entrypoint.py`、`web/bootstrap/launcher.py`、`assets/启动_排产系统_Chrome.bat`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_contract_launcher.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_stop_cli.py`
- 目标：确认打包脚本清理语义与安装器 Chrome marker 口径两条接受风险是否已完成代码收口，并验证主链路未回退。

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/skills/aps-package-win7/scripts/package_win7.ps1, installer/aps_win7_chrome.iss, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, assets/启动_排产系统_Chrome.bat, tests/test_win7_launcher_runtime_paths.py, tests/regression_runtime_contract_launcher.py, tests/regression_shared_runtime_state.py, tests/regression_runtime_stop_cli.py
- 当前进度: 已记录 1 个里程碑；最新：M1
- 里程碑总数: 1
- 已完成里程碑: 1
- 问题总数: 2
- 问题严重级别分布: 高 0 / 中 0 / 低 2
- 最新结论: 两条接受风险均已通过最小实现完成收口，且启动、契约、停机与卸载清理主链路回归全部通过，可按 `fixed` 关闭。
- 下一步建议: 当前无需继续跟踪本次两条风险。
- 总体结论: 通过

## 评审发现

### 冒烟清理语义依赖调用点容错

- ID: ps1-cleanup-throw-in-finally
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 已修复
- 相关里程碑: M1
- 说明:

  打包脚本已新增 `Stop-ProcessTreeByIdsBestEffort`，并把 `Invoke-ChromeRuntimeSmoke` 的 `finally` 清理改为显式调用该包装层。严格停止与容错清理语义已完成收口。
- 建议:

  后续若再次调整出包冒烟清理，只继续沿用“严格停止 + 容错清理包装层”的分层方式。
- 证据:
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1:244-329#Stop-ProcessTreeByIds 与 Stop-ProcessTreeByIdsBestEffort`
  - `tests/test_win7_launcher_runtime_paths.py:202-215#best-effort wrapper 守卫`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `installer/aps_win7_chrome.iss`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `assets/启动_排产系统_Chrome.bat`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_stop_cli.py`

### Chrome 进程枚举策略相似但口径未统一

- ID: cross-lang-chrome-enum-sync
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 已修复
- 相关里程碑: M1
- 说明:

  安装器 stop helper 已改为使用 `CurrentUserChromeProfilePath()` 提供的 profile 绝对路径 marker，并与 `default_chrome_profile_dir()` 和批处理默认 profile 路径保持一致。原口径分叉已完成收口。
- 建议:

  后续若调整 profile 命名或清理协议，继续同步 Python、批处理、安装器与打包脚本四处实现。
- 证据:
  - `installer/aps_win7_chrome.iss:56-100#CurrentUserChromeProfilePath 与 BuildStopChromePowerShellParams`
  - `web/bootstrap/launcher.py:514-518#default_chrome_profile_dir`
  - `assets/启动_排产系统_Chrome.bat:57-62#批处理默认 profile 路径`
  - `tests/test_win7_launcher_runtime_paths.py:86-272#profile 路径与 installer marker 守卫`
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

### M1 · 收口实现与回归复核

- 状态: 已完成
- 记录时间: 2026-04-07T02:53:47.388Z
- 已审模块: .limcode/skills/aps-package-win7/scripts/package_win7.ps1, installer/aps_win7_chrome.iss, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, assets/启动_排产系统_Chrome.bat, tests/test_win7_launcher_runtime_paths.py, tests/regression_runtime_contract_launcher.py, tests/regression_shared_runtime_state.py, tests/regression_runtime_stop_cli.py
- 摘要:

  ## 收口实现与回归复核

  ### 1. 打包脚本清理语义
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1` 中保留 `Stop-ProcessTreeByIds` 的严格停止语义。
  - 新增 `Stop-ProcessTreeByIdsBestEffort`，并仅在 `Invoke-ChromeRuntimeSmoke` 的 `finally` 清理分支使用。
  - 清理路径不再依赖外层空 `catch` 吞异常，语义已显式分层。

  ### 2. 安装器 marker 口径
  - `installer/aps_win7_chrome.iss` 新增 `CurrentUserChromeProfilePath()`，返回 `%LOCALAPPDATA%\\APS\\Chrome109Profile`。
  - `BuildStopChromePowerShellParams` 改为接收 profile 绝对路径参数，并先做单引号转义。
  - 安装器 stop helper 已移除裸字串 `chrome109profile`，与 Python 与批处理侧路径口径一致。

  ### 3. 引用链核对
  - `web/bootstrap/entrypoint.py:configure_runtime_contract()` 继续把 `default_chrome_profile_dir(runtime_dir)` 写入运行时契约。
  - `web/bootstrap/launcher.py:stop_runtime_from_dir()` 在无契约回退路径继续使用 `default_chrome_profile_dir(runtime_dir_abs)`。
  - `assets/启动_排产系统_Chrome.bat` 仍固定使用 `%LOCALAPPDATA%\\APS\\Chrome109Profile`。
  - 因此启动、契约、停机、卸载四处 profile 口径一致。

  ### 4. 回归结果
  - `python -m pytest tests/test_win7_launcher_runtime_paths.py -q`：21 通过。
  - `python tests/regression_runtime_contract_launcher.py`：`OK`。
  - `python tests/regression_shared_runtime_state.py`：`OK`。
  - `python tests/regression_runtime_stop_cli.py`：`OK`。
- 结论:

  两条接受风险均已通过最小实现完成收口，且主链路回归全部通过，可按 `fixed` 关闭。
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

  当前无需继续跟踪本次两条风险。
- 问题:
  - [低] 可维护性: 冒烟清理语义依赖调用点容错
  - [低] 可维护性: Chrome 进程枚举策略相似但口径未统一

## 最终结论

两条接受风险均已通过最小实现完成收口，且启动、契约、停机与卸载清理主链路回归全部通过，可按 `fixed` 关闭。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mno0yc3i-ym4hx4",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T02:53:55.399Z",
  "finalizedAt": "2026-04-07T02:53:55.399Z",
  "status": "completed",
  "overallDecision": "accepted",
  "header": {
    "title": "APS启动链路与Chrome接受风险收口 followup review",
    "date": "2026-04-07",
    "overview": "对两条接受风险完成实现后的引用链、路径口径与回归结果做独立收口复核。"
  },
  "scope": {
    "markdown": "# APS启动链路与Chrome接受风险收口 followup review\n\n- 日期：2026-04-07\n- 范围：`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`、`installer/aps_win7_chrome.iss`、`web/bootstrap/entrypoint.py`、`web/bootstrap/launcher.py`、`assets/启动_排产系统_Chrome.bat`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_contract_launcher.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_stop_cli.py`\n- 目标：确认打包脚本清理语义与安装器 Chrome marker 口径两条接受风险是否已完成代码收口，并验证主链路未回退。"
  },
  "summary": {
    "latestConclusion": "两条接受风险均已通过最小实现完成收口，且启动、契约、停机与卸载清理主链路回归全部通过，可按 `fixed` 关闭。",
    "recommendedNextAction": "当前无需继续跟踪本次两条风险。",
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
    ]
  },
  "stats": {
    "totalMilestones": 1,
    "completedMilestones": 1,
    "totalFindings": 2,
    "severity": {
      "high": 0,
      "medium": 0,
      "low": 2
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "收口实现与回归复核",
      "status": "completed",
      "recordedAt": "2026-04-07T02:53:47.388Z",
      "summaryMarkdown": "## 收口实现与回归复核\n\n### 1. 打包脚本清理语义\n- `.limcode/skills/aps-package-win7/scripts/package_win7.ps1` 中保留 `Stop-ProcessTreeByIds` 的严格停止语义。\n- 新增 `Stop-ProcessTreeByIdsBestEffort`，并仅在 `Invoke-ChromeRuntimeSmoke` 的 `finally` 清理分支使用。\n- 清理路径不再依赖外层空 `catch` 吞异常，语义已显式分层。\n\n### 2. 安装器 marker 口径\n- `installer/aps_win7_chrome.iss` 新增 `CurrentUserChromeProfilePath()`，返回 `%LOCALAPPDATA%\\\\APS\\\\Chrome109Profile`。\n- `BuildStopChromePowerShellParams` 改为接收 profile 绝对路径参数，并先做单引号转义。\n- 安装器 stop helper 已移除裸字串 `chrome109profile`，与 Python 与批处理侧路径口径一致。\n\n### 3. 引用链核对\n- `web/bootstrap/entrypoint.py:configure_runtime_contract()` 继续把 `default_chrome_profile_dir(runtime_dir)` 写入运行时契约。\n- `web/bootstrap/launcher.py:stop_runtime_from_dir()` 在无契约回退路径继续使用 `default_chrome_profile_dir(runtime_dir_abs)`。\n- `assets/启动_排产系统_Chrome.bat` 仍固定使用 `%LOCALAPPDATA%\\\\APS\\\\Chrome109Profile`。\n- 因此启动、契约、停机、卸载四处 profile 口径一致。\n\n### 4. 回归结果\n- `python -m pytest tests/test_win7_launcher_runtime_paths.py -q`：21 通过。\n- `python tests/regression_runtime_contract_launcher.py`：`OK`。\n- `python tests/regression_shared_runtime_state.py`：`OK`。\n- `python tests/regression_runtime_stop_cli.py`：`OK`。",
      "conclusionMarkdown": "两条接受风险均已通过最小实现完成收口，且主链路回归全部通过，可按 `fixed` 关闭。",
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
      "recommendedNextAction": "当前无需继续跟踪本次两条风险。",
      "findingIds": [
        "ps1-cleanup-throw-in-finally",
        "cross-lang-chrome-enum-sync"
      ]
    }
  ],
  "findings": [
    {
      "id": "ps1-cleanup-throw-in-finally",
      "severity": "low",
      "category": "maintainability",
      "title": "冒烟清理语义依赖调用点容错",
      "descriptionMarkdown": "打包脚本已新增 `Stop-ProcessTreeByIdsBestEffort`，并把 `Invoke-ChromeRuntimeSmoke` 的 `finally` 清理改为显式调用该包装层。严格停止与容错清理语义已完成收口。",
      "recommendationMarkdown": "后续若再次调整出包冒烟清理，只继续沿用“严格停止 + 容错清理包装层”的分层方式。",
      "evidence": [
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
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "fixed"
    },
    {
      "id": "cross-lang-chrome-enum-sync",
      "severity": "low",
      "category": "maintainability",
      "title": "Chrome 进程枚举策略相似但口径未统一",
      "descriptionMarkdown": "安装器 stop helper 已改为使用 `CurrentUserChromeProfilePath()` 提供的 profile 绝对路径 marker，并与 `default_chrome_profile_dir()` 和批处理默认 profile 路径保持一致。原口径分叉已完成收口。",
      "recommendationMarkdown": "后续若调整 profile 命名或清理协议，继续同步 Python、批处理、安装器与打包脚本四处实现。",
      "evidence": [
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
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "fixed"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:78d0305cd995c7e3ca04d89f58f4ecdea5eb9915492e3d5cb257b3f22eddc6ac",
    "generatedAt": "2026-04-07T02:53:55.399Z",
    "locale": "zh-CN"
  }
}
```
