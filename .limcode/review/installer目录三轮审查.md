# installer目录三轮审查
- 日期: 2026-04-03
- 概述: 针对 installer 目录进行三轮只读审查，重点检查静默回退、过度兜底与过度防御性编程风险。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# installer目录三轮审查

- 日期：2026-04-03
- 范围：`installer/` 及与安装包生成直接相关的入口说明文件
- 目标：执行三轮审查，重点识别安装脚本中的静默回退、过度兜底、可能掩盖 BUG 的异常处理，以及不必要的防御性编程。

## 审查策略
1. 第一轮：结构与安装入口梳理，确认文件职责与构建链路。
2. 第二轮：逐文件检查安装脚本逻辑与参数设置，定位静默回退与失败可见性问题。
3. 第三轮：交叉检查安装说明、启动器与运行时约束的一致性，评估风险闭环。

## 评审摘要

- 当前状态: 已完成
- 已审模块: installer/README_WIN7_INSTALLER.md, installer/aps_win7.iss, installer/aps_win7_legacy.iss, installer/aps_win7_chrome.iss, build_win7_installer.bat, build_win7_onedir.bat, stage_chrome109_to_dist.bat, .cursor/skills/aps-package-win7/scripts/package_win7.ps1, assets/启动_排产系统_Chrome.bat, validate_dist_exe.py, web/bootstrap/launcher.py, app.py
- 当前进度: 已记录 3 个里程碑；最新：round3-cross-check
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 8
- 问题严重级别分布: 高 1 / 中 1 / 低 6
- 最新结论: 已完成针对 installer 目录及其直接交付链路的三轮审查。总体判断：该目录不存在大面积无序兜底，但**确实存在数个会掩盖 BUG 的 fail-open 分支**。其中最严重的是主程序包与 legacy 包的旧数据迁移：复制结果未校验且异常被吞没，可能在安装成功后留下部分迁移、部分缺失的共享数据状态；其次是三份安装器的 silent uninstall 在停机失败后只记日志仍继续执行，会让自动化卸载拿不到明确失败信号。第三轮交叉审查表明，推荐的一键打包脚本与运行时契约总体一致、约束较强，问题主要集中在安装脚本本身以及少数兼容/手工路径的静默降级。建议先修复高优先级的迁移 fail-open 与 silent uninstall fail-open，再处理手工构建清理失败不可见和无 PowerShell 启动器降级。
- 下一步建议: 按优先级修复：1）旧数据迁移改为 fail-closed 并输出细粒度失败明细；2）silent uninstall 停机失败改为显式失败；3）手工打包脚本清理失败立即退出；4）启动器无 PowerShell 时禁用端口级猜测复用或补充最小健康探测。
- 总体结论: 需要后续跟进

## 评审发现

### :warning: installer 目录存在双份主脚本复制实现，后续需要核查是否造成风险分支修复不一致。

- ID: F-other-1
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round1-topology
- 证据:
  - `installer/README_WIN7_INSTALLER.md`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`

### 主安装脚本复制实现

- ID: installer-script-duplication
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round1-topology
- 说明:

  `aps_win7.iss` 与 `aps_win7_legacy.iss` 在停机 helper 解析、预清理、旧数据迁移、卸载确认等代码块上几乎全文复制。当前尚未看到行为分叉被抽象隔离，这会放大修复遗漏风险：一旦后续调整某个 BUG、静默回退或安全防护分支，很容易只改一份脚本，导致另一条交付路径继续保留旧问题。
- 建议:

  将公共逻辑收敛到共享 include 脚本，或至少建立逐段差异清单与同步校验，避免一条路径修复后另一条路径遗留。
- 证据:
  - `installer/aps_win7.iss:370-699`
  - `installer/aps_win7_legacy.iss:367-694`
  - `installer/README_WIN7_INSTALLER.md`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`

### [高] 旧数据迁移存在复制结果未校验与异常吞没问题。

- ID: F-高-旧数据迁移存在复制结果未校验与异常吞没问题
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round2-fallbacks
- 证据:
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`

### [中] silent uninstall 在停机失败后仅记日志仍继续卸载。

- ID: F-other-4
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round2-fallbacks
- 证据:
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`

### 旧数据迁移对复制失败 fail-open

- ID: installer-migration-fail-open
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round2-fallbacks
- 说明:

  `aps_win7.iss` 与 `aps_win7_legacy.iss` 的 `CopyDirTree` 对 `ForceDirectories` / `CopyFile` 的返回结果均未校验，`MigrateLegacyDataIfNeeded` 仍会继续写入“已复制”说明并把安装视为成功。即便复制过程抛出异常，外围 `except` 也只改写 `MigrationNote`，不会中止安装、不会回滚已复制目录。结果是：旧版 per-user 数据可能只迁移了一部分，安装器却仍然以成功态结束，真正的数据不一致 BUG 被留到运行时才暴露。
- 建议:

  将旧数据迁移改为 fail-closed：逐文件检查复制结果；任何失败都中止安装或至少阻止切换到共享数据目录；必要时记录详细失败清单，并在失败后清理已复制的半成品目录。
- 证据:
  - `installer/aps_win7.iss:172-198`
  - `installer/aps_win7.iss:470-515`
  - `installer/aps_win7_legacy.iss:169-195`
  - `installer/aps_win7_legacy.iss:467-512`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`

### silent uninstall 停机失败后仍继续

- ID: installer-silent-uninstall-log-only
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round2-fallbacks
- 说明:

  三份安装脚本在 `UninstallSilent()` 分支中，如果关闭 APS 运行时或 APS Chrome 失败，只执行 `Log(...)` 然后 `Exit`，而 `Result` 仍保持 `True`。这意味着静默卸载调用方拿不到明确失败信号，卸载流程会在运行实例未真正退出时继续尝试删文件，最终以残留文件、占用失败或现场状态不一致的形式暴露问题。该行为属于典型的日志型静默回退。
- 建议:

  为 silent uninstall 设定 fail-closed 语义：停机失败时直接返回 `False` 或显式错误码，让自动化脚本感知失败并终止后续步骤。
- 证据:
  - `installer/aps_win7.iss:644-652`
  - `installer/aps_win7_legacy.iss:641-649`
  - `installer/aps_win7_chrome.iss:63-71`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`

### 手工 onedir 清理旧产物时不校验删除结果

- ID: installer-manual-build-cleanup-fail-open
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round3-cross-check
- 说明:

  `build_win7_onedir.bat` 在删除旧 `build` / `dist` 目录时直接执行 `rmdir /s /q ... >nul 2>&1`，随后无论删除是否成功都继续构建。这意味着手工打包路径在目录被占用或部分删除失败时，可能把陈旧文件静默带入新一轮 `dist`，从而掩盖真正的构建环境问题。虽然推荐的一键脚本 `package_win7.ps1` 已通过更严格的 `Remove-PathWithRetry` 部分缓解，但 README 仍把该 bat 作为手工排障入口，因此该风险仍然存在。
- 建议:

  让 `build_win7_onedir.bat` 在删除后显式校验目录是否仍存在；若清理失败则立即退出，避免旧产物污染新的打包结果。
- 证据:
  - `build_win7_onedir.bat:23-25`
  - `installer/README_WIN7_INSTALLER.md:74-85`
  - `.cursor/skills/aps-package-win7/scripts/package_win7.ps1:260-269`
  - `build_win7_installer.bat`
  - `build_win7_onedir.bat`
  - `stage_chrome109_to_dist.bat`
  - `.cursor/skills/aps-package-win7/scripts/package_win7.ps1`
  - `assets/启动_排产系统_Chrome.bat`
  - `validate_dist_exe.py`
  - `web/bootstrap/launcher.py`
  - `app.py`
  - `installer/README_WIN7_INSTALLER.md`

### 启动器无 PowerShell 时退化为端口占用判断

- ID: installer-launcher-port-only-fallback
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round3-cross-check
- 说明:

  启动器优先使用 PowerShell 访问 `/system/health` 以确认现有实例确为 APS；但在缺少 PowerShell 时，会退化为仅检查端口是否处于监听状态，然后直接复用或判定被其他账户占用。这个降级分支把“确认目标服务身份”弱化成了“某个进程占用了该端口”，一旦共享日志中的 host/port 文件陈旧，而本机恰好有其他服务占用相同端口，就可能出现错误复用或错误阻止。该问题不影响常见环境，但本质上属于兼容性驱动的正确性让步。
- 建议:

  即使没有 PowerShell，也应引入最小 HTTP 探测能力或直接禁用“复用现有实例”分支，避免仅凭端口监听状态判定目标就是 APS。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:144-181`
  - `assets/启动_排产系统_Chrome.bat:275-297`
  - `assets/启动_排产系统_Chrome.bat:383-387`
  - `installer/README_WIN7_INSTALLER.md:191-193`
  - `build_win7_installer.bat`
  - `build_win7_onedir.bat`
  - `stage_chrome109_to_dist.bat`
  - `.cursor/skills/aps-package-win7/scripts/package_win7.ps1`
  - `assets/启动_排产系统_Chrome.bat`
  - `validate_dist_exe.py`
  - `web/bootstrap/launcher.py`
  - `app.py`
  - `installer/README_WIN7_INSTALLER.md`

## 评审里程碑

### round1-topology · 第一轮：安装包结构与职责边界梳理

- 状态: 已完成
- 记录时间: 2026-04-03T15:40:15.953Z
- 已审模块: installer/README_WIN7_INSTALLER.md, installer/aps_win7.iss, installer/aps_win7_legacy.iss, installer/aps_win7_chrome.iss
- 摘要:

  已完成 `installer/README_WIN7_INSTALLER.md`、`installer/aps_win7.iss`、`installer/aps_win7_legacy.iss`、`installer/aps_win7_chrome.iss` 的首轮结构审查。当前安装体系分为主程序包、浏览器运行时包与内部应急 legacy 全量包三条交付路径；主程序包与 legacy 包共享大段停机、清理、迁移逻辑，Chrome 运行时包则单独管理浏览器目录与卸载时关闭浏览器行为。

  首轮关注到两类需在后续深查的风险点：
  1. 主程序包与 legacy 包在安装/卸载/迁移逻辑上几乎全文复制，后续若修复某一处静默回退或停机失败分支，另一份脚本极易遗漏。
  2. 安装器编译语言被固定降级为内置英文，以避免构建机缺少语言文件时编译失败；这属于显式的构建期兜底，需要进一步判断是否会掩盖打包环境漂移。
- 结论:

  installer 目录的核心风险集中在两条主安装脚本的复制式实现，以及若干“为了继续安装/继续编译而不失败”的兜底分支。下一轮将逐段检查这些分支是否形成静默回退。
- 证据:
  - `installer/README_WIN7_INSTALLER.md:20-28`
  - `installer/aps_win7.iss:34-37`
  - `installer/aps_win7_legacy.iss:34-37`
  - `installer/aps_win7_chrome.iss:31-34`
  - `installer/README_WIN7_INSTALLER.md`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`
- 下一步建议:

  第二轮逐段审查安装/卸载/迁移代码，重点识别继续安装但只记日志、吞掉异常或自动降级的分支。
- 问题:
  - [低] 其他: :warning: installer 目录存在双份主脚本复制实现，后续需要核查是否造成风险分支修复不一致。
  - [低] 可维护性: 主安装脚本复制实现

### round2-fallbacks · 第二轮：安装/卸载/迁移分支的静默回退审查

- 状态: 已完成
- 记录时间: 2026-04-03T15:43:16.719Z
- 已审模块: installer/aps_win7.iss, installer/aps_win7_legacy.iss, installer/aps_win7_chrome.iss
- 摘要:

  已逐段审查三份安装脚本的 `[Code]` 逻辑，重点核查是否存在“继续执行但不失败”的分支。结论是：installer 目录确实存在会掩盖 BUG 的静默回退，且其中一处直接影响旧数据迁移的正确性。

  重点问题如下：
  1. 主程序包与 legacy 包的旧数据迁移实现没有校验目录创建与文件复制结果；即使复制失败，也可能被当作迁移成功继续安装。更糟的是，外围还用 `except` 吞掉异常，仅给出笼统提示，不中止安装也不回滚已复制内容。
  2. 三个安装器在 silent uninstall 分支里，如果停机失败，只写日志然后继续卸载；这会让自动化卸载场景在运行实例未真正关闭时也继续删除文件，失败只体现在残留或占用，不会以明确失败退出。

  同时确认到若干防御性代码是合理的，例如删除目录前的长度保护、停机 helper 的多来源解析、强制清理前的破坏性确认。这些分支虽然保守，但不会单独构成 BUG 掩盖。
- 结论:

  第二轮已确认两类核心风险：一是旧数据迁移对复制失败几乎 fail-open，二是 silent uninstall 对停机失败 fail-open。下一轮将与构建脚本、启动器和运行时契约交叉核对，确认这些回退是否被其他环节约束住，还是会扩散到交付链路。
- 证据:
  - `installer/aps_win7.iss:172-198`
  - `installer/aps_win7.iss:470-515`
  - `installer/aps_win7_legacy.iss:169-195`
  - `installer/aps_win7_legacy.iss:467-512`
  - `installer/aps_win7.iss:644-679`
  - `installer/aps_win7_legacy.iss:641-676`
  - `installer/aps_win7_chrome.iss:63-105`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`
- 下一步建议:

  第三轮交叉检查构建脚本、启动器与运行时契约，确认是否还存在为兼容环境而牺牲失败可见性的降级分支。
- 问题:
  - [低] 其他: [高] 旧数据迁移存在复制结果未校验与异常吞没问题。
  - [低] 其他: [中] silent uninstall 在停机失败后仅记日志仍继续卸载。
  - [高] 其他: 旧数据迁移对复制失败 fail-open
  - [中] 其他: silent uninstall 停机失败后仍继续

### round3-cross-check · 第三轮：构建脚本、启动器与运行时契约交叉审查

- 状态: 已完成
- 记录时间: 2026-04-03T15:44:24.594Z
- 已审模块: build_win7_installer.bat, build_win7_onedir.bat, stage_chrome109_to_dist.bat, .cursor/skills/aps-package-win7/scripts/package_win7.ps1, assets/启动_排产系统_Chrome.bat, validate_dist_exe.py, web/bootstrap/launcher.py, app.py
- 摘要:

  已完成交叉核对：`build_win7_installer.bat`、`build_win7_onedir.bat`、`stage_chrome109_to_dist.bat`、`.cursor/skills/aps-package-win7/scripts/package_win7.ps1`、`assets/启动_排产系统_Chrome.bat`、`validate_dist_exe.py`、`web/bootstrap/launcher.py`、`app.py`。

  第三轮结论分为两部分：
  1. **一致性方面是好的**：README、启动器批处理、运行时契约写入逻辑和 `app.py --runtime-stop` 基本一致，动态 host/port、共享数据目录、Chrome 路径查找、跨账户锁定这些关键语义能对上；推荐的一键打包脚本 `package_win7.ps1` 也明显比手工 bat 更严格，具备验证 `dist exe`、清理运行时痕迹、缺件即失败的闭环。
  2. **仍有两个兼容性降级点会牺牲失败可见性**：
     - 手工 onedir 构建脚本在清理旧 `build/dist` 目录时忽略删除失败，可能把旧产物静默带入新包。
     - 启动器在缺少 PowerShell 时，会把“确认现有实例确为 APS”降级成“端口在监听即可”，从而把健康校验退化为端口占用猜测。

  综合三轮结果，installer 相关链路中最值得优先处理的不是一般性的防御代码，而是那些为了“继续安装/继续卸载/继续兼容环境”而允许流程继续的 fail-open 分支。
- 结论:

  第三轮确认：推荐打包链路本身较严格，文档与运行时契约大体一致；真正的问题集中在少数兼容/手工路径的静默降级，以及第二轮已识别的安装脚本 fail-open 行为。可以收束审查并给出最终结论。
- 证据:
  - `installer/README_WIN7_INSTALLER.md:39-56`
  - `.cursor/skills/aps-package-win7/scripts/package_win7.ps1:260-289`
  - `build_win7_onedir.bat:23-25`
  - `installer/README_WIN7_INSTALLER.md:74-85`
  - `assets/启动_排产系统_Chrome.bat:144-181`
  - `assets/启动_排产系统_Chrome.bat:275-297`
  - `assets/启动_排产系统_Chrome.bat:383-387`
  - `app.py:123-155`
  - `web/bootstrap/launcher.py:482-620`
  - `web/bootstrap/launcher.py:859-932`
  - `build_win7_installer.bat`
  - `build_win7_onedir.bat`
  - `stage_chrome109_to_dist.bat`
  - `.cursor/skills/aps-package-win7/scripts/package_win7.ps1`
  - `assets/启动_排产系统_Chrome.bat`
  - `validate_dist_exe.py`
  - `web/bootstrap/launcher.py`
  - `app.py`
  - `installer/README_WIN7_INSTALLER.md`
- 下一步建议:

  汇总三轮结论，优先修复旧数据迁移 fail-open 与 silent uninstall fail-open，其次处理手工构建清理失败不可见和无 PowerShell 启动器降级。
- 问题:
  - [低] 其他: 手工 onedir 清理旧产物时不校验删除结果
  - [低] 其他: 启动器无 PowerShell 时退化为端口占用判断

## 最终结论

已完成针对 installer 目录及其直接交付链路的三轮审查。总体判断：该目录不存在大面积无序兜底，但**确实存在数个会掩盖 BUG 的 fail-open 分支**。其中最严重的是主程序包与 legacy 包的旧数据迁移：复制结果未校验且异常被吞没，可能在安装成功后留下部分迁移、部分缺失的共享数据状态；其次是三份安装器的 silent uninstall 在停机失败后只记日志仍继续执行，会让自动化卸载拿不到明确失败信号。第三轮交叉审查表明，推荐的一键打包脚本与运行时契约总体一致、约束较强，问题主要集中在安装脚本本身以及少数兼容/手工路径的静默降级。建议先修复高优先级的迁移 fail-open 与 silent uninstall fail-open，再处理手工构建清理失败不可见和无 PowerShell 启动器降级。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnj2kgpi-wsukh2",
  "createdAt": "2026-04-03T00:00:00.000Z",
  "updatedAt": "2026-04-03T15:44:40.634Z",
  "finalizedAt": "2026-04-03T15:44:40.634Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "installer目录三轮审查",
    "date": "2026-04-03",
    "overview": "针对 installer 目录进行三轮只读审查，重点检查静默回退、过度兜底与过度防御性编程风险。"
  },
  "scope": {
    "markdown": "# installer目录三轮审查\n\n- 日期：2026-04-03\n- 范围：`installer/` 及与安装包生成直接相关的入口说明文件\n- 目标：执行三轮审查，重点识别安装脚本中的静默回退、过度兜底、可能掩盖 BUG 的异常处理，以及不必要的防御性编程。\n\n## 审查策略\n1. 第一轮：结构与安装入口梳理，确认文件职责与构建链路。\n2. 第二轮：逐文件检查安装脚本逻辑与参数设置，定位静默回退与失败可见性问题。\n3. 第三轮：交叉检查安装说明、启动器与运行时约束的一致性，评估风险闭环。"
  },
  "summary": {
    "latestConclusion": "已完成针对 installer 目录及其直接交付链路的三轮审查。总体判断：该目录不存在大面积无序兜底，但**确实存在数个会掩盖 BUG 的 fail-open 分支**。其中最严重的是主程序包与 legacy 包的旧数据迁移：复制结果未校验且异常被吞没，可能在安装成功后留下部分迁移、部分缺失的共享数据状态；其次是三份安装器的 silent uninstall 在停机失败后只记日志仍继续执行，会让自动化卸载拿不到明确失败信号。第三轮交叉审查表明，推荐的一键打包脚本与运行时契约总体一致、约束较强，问题主要集中在安装脚本本身以及少数兼容/手工路径的静默降级。建议先修复高优先级的迁移 fail-open 与 silent uninstall fail-open，再处理手工构建清理失败不可见和无 PowerShell 启动器降级。",
    "recommendedNextAction": "按优先级修复：1）旧数据迁移改为 fail-closed 并输出细粒度失败明细；2）silent uninstall 停机失败改为显式失败；3）手工打包脚本清理失败立即退出；4）启动器无 PowerShell 时禁用端口级猜测复用或补充最小健康探测。",
    "reviewedModules": [
      "installer/README_WIN7_INSTALLER.md",
      "installer/aps_win7.iss",
      "installer/aps_win7_legacy.iss",
      "installer/aps_win7_chrome.iss",
      "build_win7_installer.bat",
      "build_win7_onedir.bat",
      "stage_chrome109_to_dist.bat",
      ".cursor/skills/aps-package-win7/scripts/package_win7.ps1",
      "assets/启动_排产系统_Chrome.bat",
      "validate_dist_exe.py",
      "web/bootstrap/launcher.py",
      "app.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 8,
    "severity": {
      "high": 1,
      "medium": 1,
      "low": 6
    }
  },
  "milestones": [
    {
      "id": "round1-topology",
      "title": "第一轮：安装包结构与职责边界梳理",
      "status": "completed",
      "recordedAt": "2026-04-03T15:40:15.953Z",
      "summaryMarkdown": "已完成 `installer/README_WIN7_INSTALLER.md`、`installer/aps_win7.iss`、`installer/aps_win7_legacy.iss`、`installer/aps_win7_chrome.iss` 的首轮结构审查。当前安装体系分为主程序包、浏览器运行时包与内部应急 legacy 全量包三条交付路径；主程序包与 legacy 包共享大段停机、清理、迁移逻辑，Chrome 运行时包则单独管理浏览器目录与卸载时关闭浏览器行为。\n\n首轮关注到两类需在后续深查的风险点：\n1. 主程序包与 legacy 包在安装/卸载/迁移逻辑上几乎全文复制，后续若修复某一处静默回退或停机失败分支，另一份脚本极易遗漏。\n2. 安装器编译语言被固定降级为内置英文，以避免构建机缺少语言文件时编译失败；这属于显式的构建期兜底，需要进一步判断是否会掩盖打包环境漂移。",
      "conclusionMarkdown": "installer 目录的核心风险集中在两条主安装脚本的复制式实现，以及若干“为了继续安装/继续编译而不失败”的兜底分支。下一轮将逐段检查这些分支是否形成静默回退。",
      "evidence": [
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 20,
          "lineEnd": 28,
          "excerptHash": "sha256:installer-readme-topology"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 34,
          "lineEnd": 37,
          "excerptHash": "sha256:aps-win7-language-fallback"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 34,
          "lineEnd": 37,
          "excerptHash": "sha256:aps-win7-legacy-language-fallback"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 31,
          "lineEnd": 34,
          "excerptHash": "sha256:aps-win7-chrome-language-fallback"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "reviewedModules": [
        "installer/README_WIN7_INSTALLER.md",
        "installer/aps_win7.iss",
        "installer/aps_win7_legacy.iss",
        "installer/aps_win7_chrome.iss"
      ],
      "recommendedNextAction": "第二轮逐段审查安装/卸载/迁移代码，重点识别继续安装但只记日志、吞掉异常或自动降级的分支。",
      "findingIds": [
        "F-other-1",
        "installer-script-duplication"
      ]
    },
    {
      "id": "round2-fallbacks",
      "title": "第二轮：安装/卸载/迁移分支的静默回退审查",
      "status": "completed",
      "recordedAt": "2026-04-03T15:43:16.719Z",
      "summaryMarkdown": "已逐段审查三份安装脚本的 `[Code]` 逻辑，重点核查是否存在“继续执行但不失败”的分支。结论是：installer 目录确实存在会掩盖 BUG 的静默回退，且其中一处直接影响旧数据迁移的正确性。\n\n重点问题如下：\n1. 主程序包与 legacy 包的旧数据迁移实现没有校验目录创建与文件复制结果；即使复制失败，也可能被当作迁移成功继续安装。更糟的是，外围还用 `except` 吞掉异常，仅给出笼统提示，不中止安装也不回滚已复制内容。\n2. 三个安装器在 silent uninstall 分支里，如果停机失败，只写日志然后继续卸载；这会让自动化卸载场景在运行实例未真正关闭时也继续删除文件，失败只体现在残留或占用，不会以明确失败退出。\n\n同时确认到若干防御性代码是合理的，例如删除目录前的长度保护、停机 helper 的多来源解析、强制清理前的破坏性确认。这些分支虽然保守，但不会单独构成 BUG 掩盖。",
      "conclusionMarkdown": "第二轮已确认两类核心风险：一是旧数据迁移对复制失败几乎 fail-open，二是 silent uninstall 对停机失败 fail-open。下一轮将与构建脚本、启动器和运行时契约交叉核对，确认这些回退是否被其他环节约束住，还是会扩散到交付链路。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 172,
          "lineEnd": 198,
          "excerptHash": "sha256:aps-win7-copydirtree-unchecked"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 470,
          "lineEnd": 515,
          "excerptHash": "sha256:aps-win7-migration-note-swallow"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 169,
          "lineEnd": 195,
          "excerptHash": "sha256:aps-win7-legacy-copydirtree-unchecked"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 467,
          "lineEnd": 512,
          "excerptHash": "sha256:aps-win7-legacy-migration-note-swallow"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 644,
          "lineEnd": 679,
          "excerptHash": "sha256:aps-win7-silent-uninstall-log-only"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 641,
          "lineEnd": 676,
          "excerptHash": "sha256:aps-win7-legacy-silent-uninstall-log-only"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 63,
          "lineEnd": 105,
          "excerptHash": "sha256:aps-win7-chrome-silent-uninstall-log-only"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "reviewedModules": [
        "installer/aps_win7.iss",
        "installer/aps_win7_legacy.iss",
        "installer/aps_win7_chrome.iss"
      ],
      "recommendedNextAction": "第三轮交叉检查构建脚本、启动器与运行时契约，确认是否还存在为兼容环境而牺牲失败可见性的降级分支。",
      "findingIds": [
        "F-高-旧数据迁移存在复制结果未校验与异常吞没问题",
        "F-other-4",
        "installer-migration-fail-open",
        "installer-silent-uninstall-log-only"
      ]
    },
    {
      "id": "round3-cross-check",
      "title": "第三轮：构建脚本、启动器与运行时契约交叉审查",
      "status": "completed",
      "recordedAt": "2026-04-03T15:44:24.594Z",
      "summaryMarkdown": "已完成交叉核对：`build_win7_installer.bat`、`build_win7_onedir.bat`、`stage_chrome109_to_dist.bat`、`.cursor/skills/aps-package-win7/scripts/package_win7.ps1`、`assets/启动_排产系统_Chrome.bat`、`validate_dist_exe.py`、`web/bootstrap/launcher.py`、`app.py`。\n\n第三轮结论分为两部分：\n1. **一致性方面是好的**：README、启动器批处理、运行时契约写入逻辑和 `app.py --runtime-stop` 基本一致，动态 host/port、共享数据目录、Chrome 路径查找、跨账户锁定这些关键语义能对上；推荐的一键打包脚本 `package_win7.ps1` 也明显比手工 bat 更严格，具备验证 `dist exe`、清理运行时痕迹、缺件即失败的闭环。\n2. **仍有两个兼容性降级点会牺牲失败可见性**：\n   - 手工 onedir 构建脚本在清理旧 `build/dist` 目录时忽略删除失败，可能把旧产物静默带入新包。\n   - 启动器在缺少 PowerShell 时，会把“确认现有实例确为 APS”降级成“端口在监听即可”，从而把健康校验退化为端口占用猜测。\n\n综合三轮结果，installer 相关链路中最值得优先处理的不是一般性的防御代码，而是那些为了“继续安装/继续卸载/继续兼容环境”而允许流程继续的 fail-open 分支。",
      "conclusionMarkdown": "第三轮确认：推荐打包链路本身较严格，文档与运行时契约大体一致；真正的问题集中在少数兼容/手工路径的静默降级，以及第二轮已识别的安装脚本 fail-open 行为。可以收束审查并给出最终结论。",
      "evidence": [
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 39,
          "lineEnd": 56,
          "excerptHash": "sha256:installer-readme-package-pipeline"
        },
        {
          "path": ".cursor/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 260,
          "lineEnd": 289,
          "excerptHash": "sha256:package-win7-main-chrome-strict"
        },
        {
          "path": "build_win7_onedir.bat",
          "lineStart": 23,
          "lineEnd": 25,
          "excerptHash": "sha256:build-win7-onedir-cleanup-ignore-failure"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 74,
          "lineEnd": 85,
          "excerptHash": "sha256:installer-readme-manual-build-route"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 144,
          "lineEnd": 181,
          "excerptHash": "sha256:launcher-powershell-or-port-probe"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 275,
          "lineEnd": 297,
          "excerptHash": "sha256:launcher-reuse-port-only-fallback"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 383,
          "lineEnd": 387,
          "excerptHash": "sha256:launcher-port-listening-only"
        },
        {
          "path": "app.py",
          "lineStart": 123,
          "lineEnd": 155,
          "excerptHash": "sha256:app-dynamic-host-port-contract"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 482,
          "lineEnd": 620,
          "excerptHash": "sha256:runtime-contract-writes"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 859,
          "lineEnd": 932,
          "excerptHash": "sha256:runtime-stop-contract"
        },
        {
          "path": "build_win7_installer.bat"
        },
        {
          "path": "build_win7_onedir.bat"
        },
        {
          "path": "stage_chrome109_to_dist.bat"
        },
        {
          "path": ".cursor/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "validate_dist_exe.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "app.py"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        }
      ],
      "reviewedModules": [
        "build_win7_installer.bat",
        "build_win7_onedir.bat",
        "stage_chrome109_to_dist.bat",
        ".cursor/skills/aps-package-win7/scripts/package_win7.ps1",
        "assets/启动_排产系统_Chrome.bat",
        "validate_dist_exe.py",
        "web/bootstrap/launcher.py",
        "app.py"
      ],
      "recommendedNextAction": "汇总三轮结论，优先修复旧数据迁移 fail-open 与 silent uninstall fail-open，其次处理手工构建清理失败不可见和无 PowerShell 启动器降级。",
      "findingIds": [
        "installer-manual-build-cleanup-fail-open",
        "installer-launcher-port-only-fallback"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-other-1",
      "severity": "low",
      "category": "other",
      "title": ":warning: installer 目录存在双份主脚本复制实现，后续需要核查是否造成风险分支修复不一致。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round1-topology"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "installer-script-duplication",
      "severity": "low",
      "category": "maintainability",
      "title": "主安装脚本复制实现",
      "descriptionMarkdown": "`aps_win7.iss` 与 `aps_win7_legacy.iss` 在停机 helper 解析、预清理、旧数据迁移、卸载确认等代码块上几乎全文复制。当前尚未看到行为分叉被抽象隔离，这会放大修复遗漏风险：一旦后续调整某个 BUG、静默回退或安全防护分支，很容易只改一份脚本，导致另一条交付路径继续保留旧问题。",
      "recommendationMarkdown": "将公共逻辑收敛到共享 include 脚本，或至少建立逐段差异清单与同步校验，避免一条路径修复后另一条路径遗留。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 370,
          "lineEnd": 699,
          "excerptHash": "sha256:aps-win7-shared-code-block"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 367,
          "lineEnd": 694,
          "excerptHash": "sha256:aps-win7-legacy-shared-code-block"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round1-topology"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-高-旧数据迁移存在复制结果未校验与异常吞没问题",
      "severity": "low",
      "category": "other",
      "title": "[高] 旧数据迁移存在复制结果未校验与异常吞没问题。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round2-fallbacks"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-4",
      "severity": "low",
      "category": "other",
      "title": "[中] silent uninstall 在停机失败后仅记日志仍继续卸载。",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round2-fallbacks"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "installer-migration-fail-open",
      "severity": "high",
      "category": "other",
      "title": "旧数据迁移对复制失败 fail-open",
      "descriptionMarkdown": "`aps_win7.iss` 与 `aps_win7_legacy.iss` 的 `CopyDirTree` 对 `ForceDirectories` / `CopyFile` 的返回结果均未校验，`MigrateLegacyDataIfNeeded` 仍会继续写入“已复制”说明并把安装视为成功。即便复制过程抛出异常，外围 `except` 也只改写 `MigrationNote`，不会中止安装、不会回滚已复制目录。结果是：旧版 per-user 数据可能只迁移了一部分，安装器却仍然以成功态结束，真正的数据不一致 BUG 被留到运行时才暴露。",
      "recommendationMarkdown": "将旧数据迁移改为 fail-closed：逐文件检查复制结果；任何失败都中止安装或至少阻止切换到共享数据目录；必要时记录详细失败清单，并在失败后清理已复制的半成品目录。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 172,
          "lineEnd": 198,
          "excerptHash": "sha256:aps-win7-copydirtree-unchecked"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 470,
          "lineEnd": 515,
          "excerptHash": "sha256:aps-win7-migration-note-swallow"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 169,
          "lineEnd": 195,
          "excerptHash": "sha256:aps-win7-legacy-copydirtree-unchecked"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 467,
          "lineEnd": 512,
          "excerptHash": "sha256:aps-win7-legacy-migration-note-swallow"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round2-fallbacks"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "installer-silent-uninstall-log-only",
      "severity": "medium",
      "category": "other",
      "title": "silent uninstall 停机失败后仍继续",
      "descriptionMarkdown": "三份安装脚本在 `UninstallSilent()` 分支中，如果关闭 APS 运行时或 APS Chrome 失败，只执行 `Log(...)` 然后 `Exit`，而 `Result` 仍保持 `True`。这意味着静默卸载调用方拿不到明确失败信号，卸载流程会在运行实例未真正退出时继续尝试删文件，最终以残留文件、占用失败或现场状态不一致的形式暴露问题。该行为属于典型的日志型静默回退。",
      "recommendationMarkdown": "为 silent uninstall 设定 fail-closed 语义：停机失败时直接返回 `False` 或显式错误码，让自动化脚本感知失败并终止后续步骤。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 644,
          "lineEnd": 652,
          "excerptHash": "sha256:aps-win7-silent-uninstall-log-only"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 641,
          "lineEnd": 649,
          "excerptHash": "sha256:aps-win7-legacy-silent-uninstall-log-only"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 63,
          "lineEnd": 71,
          "excerptHash": "sha256:aps-win7-chrome-silent-uninstall-log-only"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round2-fallbacks"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "installer-manual-build-cleanup-fail-open",
      "severity": "low",
      "category": "other",
      "title": "手工 onedir 清理旧产物时不校验删除结果",
      "descriptionMarkdown": "`build_win7_onedir.bat` 在删除旧 `build` / `dist` 目录时直接执行 `rmdir /s /q ... >nul 2>&1`，随后无论删除是否成功都继续构建。这意味着手工打包路径在目录被占用或部分删除失败时，可能把陈旧文件静默带入新一轮 `dist`，从而掩盖真正的构建环境问题。虽然推荐的一键脚本 `package_win7.ps1` 已通过更严格的 `Remove-PathWithRetry` 部分缓解，但 README 仍把该 bat 作为手工排障入口，因此该风险仍然存在。",
      "recommendationMarkdown": "让 `build_win7_onedir.bat` 在删除后显式校验目录是否仍存在；若清理失败则立即退出，避免旧产物污染新的打包结果。",
      "evidence": [
        {
          "path": "build_win7_onedir.bat",
          "lineStart": 23,
          "lineEnd": 25,
          "excerptHash": "sha256:build-win7-onedir-cleanup-ignore-failure"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 74,
          "lineEnd": 85,
          "excerptHash": "sha256:installer-readme-manual-build-route"
        },
        {
          "path": ".cursor/skills/aps-package-win7/scripts/package_win7.ps1",
          "lineStart": 260,
          "lineEnd": 269,
          "excerptHash": "sha256:package-win7-strict-clean-before-build"
        },
        {
          "path": "build_win7_installer.bat"
        },
        {
          "path": "build_win7_onedir.bat"
        },
        {
          "path": "stage_chrome109_to_dist.bat"
        },
        {
          "path": ".cursor/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "validate_dist_exe.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "app.py"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        }
      ],
      "relatedMilestoneIds": [
        "round3-cross-check"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "installer-launcher-port-only-fallback",
      "severity": "low",
      "category": "other",
      "title": "启动器无 PowerShell 时退化为端口占用判断",
      "descriptionMarkdown": "启动器优先使用 PowerShell 访问 `/system/health` 以确认现有实例确为 APS；但在缺少 PowerShell 时，会退化为仅检查端口是否处于监听状态，然后直接复用或判定被其他账户占用。这个降级分支把“确认目标服务身份”弱化成了“某个进程占用了该端口”，一旦共享日志中的 host/port 文件陈旧，而本机恰好有其他服务占用相同端口，就可能出现错误复用或错误阻止。该问题不影响常见环境，但本质上属于兼容性驱动的正确性让步。",
      "recommendationMarkdown": "即使没有 PowerShell，也应引入最小 HTTP 探测能力或直接禁用“复用现有实例”分支，避免仅凭端口监听状态判定目标就是 APS。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 144,
          "lineEnd": 181,
          "excerptHash": "sha256:launcher-powershell-or-port-probe"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 275,
          "lineEnd": 297,
          "excerptHash": "sha256:launcher-reuse-port-only-fallback"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 383,
          "lineEnd": 387,
          "excerptHash": "sha256:launcher-port-listening-only"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 191,
          "lineEnd": 193,
          "excerptHash": "sha256:installer-readme-launcher-contract"
        },
        {
          "path": "build_win7_installer.bat"
        },
        {
          "path": "build_win7_onedir.bat"
        },
        {
          "path": "stage_chrome109_to_dist.bat"
        },
        {
          "path": ".cursor/skills/aps-package-win7/scripts/package_win7.ps1"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "validate_dist_exe.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "app.py"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md"
        }
      ],
      "relatedMilestoneIds": [
        "round3-cross-check"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:4e89c2b0daf604d8509cb1596e02abd2bbcd3f961f2ffc3744d85ad1ea05ce29",
    "generatedAt": "2026-04-03T15:44:40.634Z",
    "locale": "zh-CN"
  }
}
```
