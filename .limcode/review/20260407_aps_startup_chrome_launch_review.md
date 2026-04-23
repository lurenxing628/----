# APS安装后启动Chrome未拉起综合审查
- 日期: 2026-04-07
- 概述: 排查安装后APS启动时命令行一闪而过且未能拉起Chrome的问题，聚焦启动脚本、运行时入口、浏览器探测与安装器集成链路。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# APS安装后启动Chrome未拉起综合审查

- 日期：2026-04-07
- 范围：安装器、启动脚本、运行时入口、浏览器探测、端口文件与启动契约
- 目标：定位安装后“CMD闪一下，Chrome未拉起”的根因与风险扩散点，并给出可落地整改建议

## 初始判断

用户现象说明问题大概率发生在“启动脚本 → Python入口 → 运行时探测/写端口文件 → 浏览器拉起”链路中的前半段或浏览器探测分支。优先审查批处理脚本、桌面/安装器生成入口、运行时浏览器选择与失败降级路径。

## 评审摘要

- 当前状态: 已完成
- 已审模块: assets/启动_排产系统_Chrome.bat, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, installer/aps_win7.iss, installer/aps_win7_chrome.iss, .limcode/skills/aps-package-win7/scripts/package_win7.ps1, validate_dist_exe.py, tests/test_win7_launcher_runtime_paths.py
- 当前进度: 已记录 1 个里程碑；最新：M1
- 里程碑总数: 1
- 已完成里程碑: 1
- 问题总数: 3
- 问题严重级别分布: 高 2 / 中 1 / 低 0
- 最新结论: 已完成对安装后启动链路的端到端审查。当前“CMD闪一下但未拉起 Chrome”并非单点问题，而是两个高风险缺口叠加造成：其一，启动器把 `start` 返回码当作浏览器启动成功，未验证 APS 专用浏览器是否真正拉起并稳定存活，也未对 `Chrome109Profile` 目录创建失败做失败即停处理；其二，双包打包链只验证主程序后端冷启动，不验证裁剪后的浏览器运行时与安装后快捷方式链路，因此浏览器运行时损坏、缺件、目录不可写等问题都可能直接流入现场。另有一处中风险问题：批处理对运行时契约中的 `owner` 字段未做 JSON 反转义，在契约回退路径下可能误判同一账户为其他账户占用。结论：该问题需要继续跟进并落地修复，优先级应放在浏览器拉起失败即停、打包期浏览器最小冒烟、契约回退解析归一化三项。
- 下一步建议: 立即按三步收口：1）启动器在拉起浏览器前后增加目录可写性校验与 APS 专用浏览器存活确认；2）打包脚本增加裁剪后 `chrome.exe --app` 最小冒烟与安装后快捷方式验收；3）修正批处理对运行时契约 owner 的反转义并补回归。
- 总体结论: 需要后续跟进

## 评审发现

### 浏览器启动结果判定过于乐观

- ID: launcher-silent-chrome-failure
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  启动器在打开浏览器时仅根据 `start` 命令返回码判断成功，而批处理自身也已在注释中承认这无法证明浏览器稳定运行。当前链路不会校验 APS 专用浏览器进程是否真正拉起、是否仍然存活，也不会在浏览器瞬时崩溃后回写明确错误。再加上 `CHROME_PROFILE_DIR` 仅尝试 `mkdir` 而不校验创建结果或可写性，运行时缺件、目录不可写、用户数据损坏等情况都可能表现为“命令行一闪而过、浏览器没打开”。这与用户反馈现象直接吻合。
- 建议:

  在打开浏览器前先校验用户数据目录可创建且可写；打开后按 `Chrome109Profile` 标识轮询确认 APS 专用浏览器进程已出现并短时存活，否则明确写入 `launcher.log` 与控制台错误并失败退出，而不是仅依赖 `start` 返回码。
- 证据:
  - `assets/启动_排产系统_Chrome.bat`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_chrome.iss`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `validate_dist_exe.py`

### 双包打包链缺少浏览器最小冒烟

- ID: packaging-misses-browser-smoke
- 严重级别: 高
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  当前打包流程会构建裁剪后的浏览器运行时并生成安装包，但实际自动验收只覆盖主程序 `validate_dist_exe.py`，并不执行 `chrome.exe --app` 最小可用性验证，也不覆盖安装后快捷方式/启动器链路。这样即使浏览器运行时 payload 被裁剪坏、目录结构与来源包不兼容，或安装后快捷方式链路失效，构建仍会被判定通过，问题只能在目标机暴露。
- 建议:

  在打包阶段增加裁剪后运行时的最小冒烟验证，至少覆盖 `chrome.exe --app=http://127.0.0.1:{port}/` 可拉起；在交付验收中增加安装后通过快捷方式启动的自动或半自动验证，并将其纳入出包阻断条件。
- 证据:
  - `assets/启动_排产系统_Chrome.bat`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_chrome.iss`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `validate_dist_exe.py`
  - `installer/README_WIN7_INSTALLER.md`

### 批处理契约解析未反转义 owner

- ID: bat-contract-owner-unescape
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  启动器从 `aps_runtime.json` 读取 `owner` 时，采用 `findstr` 与简单文本替换提取字段，但没有把 JSON 中的转义反斜杠 `\\` 还原为 `\`。Python 侧写入的 owner 形如 `DOMAIN\\user`，而批处理当前账户值是 `DOMAIN\user`。在运行时锁缺失、查询失败或仅能依赖契约回退判定归属时，同一账户可能被误判为“其他账户正在使用”，造成错误阻止。
- 建议:

  避免在批处理中手写 JSON 解析；至少在 owner 提取后增加反转义归一化，把 `\\` 还原为 `\`，并补充针对契约回退场景的自动化回归。
- 证据:
  - `assets/启动_排产系统_Chrome.bat`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_chrome.iss`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `validate_dist_exe.py`

## 评审里程碑

### M1 · 启动器与安装链路首轮审查

- 状态: 已完成
- 记录时间: 2026-04-07T00:34:47.610Z
- 已审模块: assets/启动_排产系统_Chrome.bat, web/bootstrap/entrypoint.py, web/bootstrap/launcher.py, installer/aps_win7.iss, installer/aps_win7_chrome.iss, .limcode/skills/aps-package-win7/scripts/package_win7.ps1, validate_dist_exe.py, tests/test_win7_launcher_runtime_paths.py
- 摘要:

  已完成对启动批处理、运行时入口、共享日志契约、主安装器与浏览器运行时打包脚本的联动审查。当前最贴近用户现象的风险点不在后端端口拉起，而在“浏览器启动成功判定”过于乐观：启动器只检查 `start` 命令返回码，未验证 APS 专用浏览器是否真正存活，也未对用户数据目录创建失败做失败即停处理；一旦浏览器因运行时缺件、目录不可写或配置损坏而瞬间退出，用户侧就只会看到命令行闪一下。与此同时，双包打包流程只验证主程序 `exe` 冷启动，不验证裁剪后的浏览器运行时 `chrome.exe --app` 最小可用性，也不覆盖安装后快捷方式链路，导致该类问题很容易漏到现场。另发现批处理对运行时契约中的 `owner` 字段采用文本截取但未做 JSON 反转义，命中契约回退路径时可能把同一账户误判为“其他账户占用”。
- 结论:

  安装后“CMD闪一下但未拉起 Chrome”的主要风险集中在浏览器启动判定与打包验收缺口，两者叠加后会把运行时崩溃表现成无提示的静默失败。
- 证据:
  - `assets/启动_排产系统_Chrome.bat`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher.py`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_chrome.iss`
  - `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `validate_dist_exe.py`
- 下一步建议:

  基于上述三处问题，优先收口浏览器拉起的失败即停机制与打包期浏览器冒烟验收，然后再补齐契约回退场景的批处理解析回归。
- 问题:
  - [高] 其他: 浏览器启动结果判定过于乐观
  - [高] 测试: 双包打包链缺少浏览器最小冒烟
  - [中] 其他: 批处理契约解析未反转义 owner

## 最终结论

已完成对安装后启动链路的端到端审查。当前“CMD闪一下但未拉起 Chrome”并非单点问题，而是两个高风险缺口叠加造成：其一，启动器把 `start` 返回码当作浏览器启动成功，未验证 APS 专用浏览器是否真正拉起并稳定存活，也未对 `Chrome109Profile` 目录创建失败做失败即停处理；其二，双包打包链只验证主程序后端冷启动，不验证裁剪后的浏览器运行时与安装后快捷方式链路，因此浏览器运行时损坏、缺件、目录不可写等问题都可能直接流入现场。另有一处中风险问题：批处理对运行时契约中的 `owner` 字段未做 JSON 反转义，在契约回退路径下可能误判同一账户为其他账户占用。结论：该问题需要继续跟进并落地修复，优先级应放在浏览器拉起失败即停、打包期浏览器最小冒烟、契约回退解析归一化三项。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnnvubs6-exb2dl",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T00:35:19.838Z",
  "finalizedAt": "2026-04-07T00:35:19.838Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "APS安装后启动Chrome未拉起综合审查",
    "date": "2026-04-07",
    "overview": "排查安装后APS启动时命令行一闪而过且未能拉起Chrome的问题，聚焦启动脚本、运行时入口、浏览器探测与安装器集成链路。"
  },
  "scope": {
    "markdown": "# APS安装后启动Chrome未拉起综合审查\n\n- 日期：2026-04-07\n- 范围：安装器、启动脚本、运行时入口、浏览器探测、端口文件与启动契约\n- 目标：定位安装后“CMD闪一下，Chrome未拉起”的根因与风险扩散点，并给出可落地整改建议\n\n## 初始判断\n\n用户现象说明问题大概率发生在“启动脚本 → Python入口 → 运行时探测/写端口文件 → 浏览器拉起”链路中的前半段或浏览器探测分支。优先审查批处理脚本、桌面/安装器生成入口、运行时浏览器选择与失败降级路径。"
  },
  "summary": {
    "latestConclusion": "已完成对安装后启动链路的端到端审查。当前“CMD闪一下但未拉起 Chrome”并非单点问题，而是两个高风险缺口叠加造成：其一，启动器把 `start` 返回码当作浏览器启动成功，未验证 APS 专用浏览器是否真正拉起并稳定存活，也未对 `Chrome109Profile` 目录创建失败做失败即停处理；其二，双包打包链只验证主程序后端冷启动，不验证裁剪后的浏览器运行时与安装后快捷方式链路，因此浏览器运行时损坏、缺件、目录不可写等问题都可能直接流入现场。另有一处中风险问题：批处理对运行时契约中的 `owner` 字段未做 JSON 反转义，在契约回退路径下可能误判同一账户为其他账户占用。结论：该问题需要继续跟进并落地修复，优先级应放在浏览器拉起失败即停、打包期浏览器最小冒烟、契约回退解析归一化三项。",
    "recommendedNextAction": "立即按三步收口：1）启动器在拉起浏览器前后增加目录可写性校验与 APS 专用浏览器存活确认；2）打包脚本增加裁剪后 `chrome.exe --app` 最小冒烟与安装后快捷方式验收；3）修正批处理对运行时契约 owner 的反转义并补回归。",
    "reviewedModules": [
      "assets/启动_排产系统_Chrome.bat",
      "web/bootstrap/entrypoint.py",
      "web/bootstrap/launcher.py",
      "installer/aps_win7.iss",
      "installer/aps_win7_chrome.iss",
      ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
      "validate_dist_exe.py",
      "tests/test_win7_launcher_runtime_paths.py"
    ]
  },
  "stats": {
    "totalMilestones": 1,
    "completedMilestones": 1,
    "totalFindings": 3,
    "severity": {
      "high": 2,
      "medium": 1,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "启动器与安装链路首轮审查",
      "status": "completed",
      "recordedAt": "2026-04-07T00:34:47.610Z",
      "summaryMarkdown": "已完成对启动批处理、运行时入口、共享日志契约、主安装器与浏览器运行时打包脚本的联动审查。当前最贴近用户现象的风险点不在后端端口拉起，而在“浏览器启动成功判定”过于乐观：启动器只检查 `start` 命令返回码，未验证 APS 专用浏览器是否真正存活，也未对用户数据目录创建失败做失败即停处理；一旦浏览器因运行时缺件、目录不可写或配置损坏而瞬间退出，用户侧就只会看到命令行闪一下。与此同时，双包打包流程只验证主程序 `exe` 冷启动，不验证裁剪后的浏览器运行时 `chrome.exe --app` 最小可用性，也不覆盖安装后快捷方式链路，导致该类问题很容易漏到现场。另发现批处理对运行时契约中的 `owner` 字段采用文本截取但未做 JSON 反转义，命中契约回退路径时可能把同一账户误判为“其他账户占用”。",
      "conclusionMarkdown": "安装后“CMD闪一下但未拉起 Chrome”的主要风险集中在浏览器启动判定与打包验收缺口，两者叠加后会把运行时崩溃表现成无提示的静默失败。",
      "evidence": [
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
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "validate_dist_exe.py"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "web/bootstrap/entrypoint.py",
        "web/bootstrap/launcher.py",
        "installer/aps_win7.iss",
        "installer/aps_win7_chrome.iss",
        ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
        "validate_dist_exe.py",
        "tests/test_win7_launcher_runtime_paths.py"
      ],
      "recommendedNextAction": "基于上述三处问题，优先收口浏览器拉起的失败即停机制与打包期浏览器冒烟验收，然后再补齐契约回退场景的批处理解析回归。",
      "findingIds": [
        "launcher-silent-chrome-failure",
        "packaging-misses-browser-smoke",
        "bat-contract-owner-unescape"
      ]
    }
  ],
  "findings": [
    {
      "id": "launcher-silent-chrome-failure",
      "severity": "high",
      "category": "other",
      "title": "浏览器启动结果判定过于乐观",
      "descriptionMarkdown": "启动器在打开浏览器时仅根据 `start` 命令返回码判断成功，而批处理自身也已在注释中承认这无法证明浏览器稳定运行。当前链路不会校验 APS 专用浏览器进程是否真正拉起、是否仍然存活，也不会在浏览器瞬时崩溃后回写明确错误。再加上 `CHROME_PROFILE_DIR` 仅尝试 `mkdir` 而不校验创建结果或可写性，运行时缺件、目录不可写、用户数据损坏等情况都可能表现为“命令行一闪而过、浏览器没打开”。这与用户反馈现象直接吻合。",
      "recommendationMarkdown": "在打开浏览器前先校验用户数据目录可创建且可写；打开后按 `Chrome109Profile` 标识轮询确认 APS 专用浏览器进程已出现并短时存活，否则明确写入 `launcher.log` 与控制台错误并失败退出，而不是仅依赖 `start` 返回码。",
      "evidence": [
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
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "validate_dist_exe.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "packaging-misses-browser-smoke",
      "severity": "high",
      "category": "test",
      "title": "双包打包链缺少浏览器最小冒烟",
      "descriptionMarkdown": "当前打包流程会构建裁剪后的浏览器运行时并生成安装包，但实际自动验收只覆盖主程序 `validate_dist_exe.py`，并不执行 `chrome.exe --app` 最小可用性验证，也不覆盖安装后快捷方式/启动器链路。这样即使浏览器运行时 payload 被裁剪坏、目录结构与来源包不兼容，或安装后快捷方式链路失效，构建仍会被判定通过，问题只能在目标机暴露。",
      "recommendationMarkdown": "在打包阶段增加裁剪后运行时的最小冒烟验证，至少覆盖 `chrome.exe --app=http://127.0.0.1:{port}/` 可拉起；在交付验收中增加安装后通过快捷方式启动的自动或半自动验证，并将其纳入出包阻断条件。",
      "evidence": [
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
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "validate_dist_exe.py"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "bat-contract-owner-unescape",
      "severity": "medium",
      "category": "other",
      "title": "批处理契约解析未反转义 owner",
      "descriptionMarkdown": "启动器从 `aps_runtime.json` 读取 `owner` 时，采用 `findstr` 与简单文本替换提取字段，但没有把 JSON 中的转义反斜杠 `\\\\` 还原为 `\\`。Python 侧写入的 owner 形如 `DOMAIN\\\\user`，而批处理当前账户值是 `DOMAIN\\user`。在运行时锁缺失、查询失败或仅能依赖契约回退判定归属时，同一账户可能被误判为“其他账户正在使用”，造成错误阻止。",
      "recommendationMarkdown": "避免在批处理中手写 JSON 解析；至少在 owner 提取后增加反转义归一化，把 `\\\\` 还原为 `\\`，并补充针对契约回退场景的自动化回归。",
      "evidence": [
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
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": ".limcode/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        },
        {
          "path": "validate_dist_exe.py"
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
    "bodyHash": "sha256:66659cad9bb1bf5f75011d208835e6b063fd5f6be2f2c6122bea03373715e5b0",
    "generatedAt": "2026-04-07T00:35:19.838Z",
    "locale": "zh-CN"
  }
}
```
