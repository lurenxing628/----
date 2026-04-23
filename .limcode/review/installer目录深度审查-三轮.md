# installer目录深度审查_三轮
- 日期: 2026-04-03
- 概述: 对 installer/ 目录及关联的构建/启动脚本进行三轮深度审查，重点关注过度兜底、静默回退与过度防御性编程
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# installer 目录深度审查（三轮）

**审查日期**: 2026-04-01  
**审查范围**: `installer/` 目录下全部 `.iss` 脚本，以及关联的 `assets/启动_排产系统_Chrome.bat`、`build_win7_installer.bat`、`build_win7_onedir.bat`、`stage_chrome109_to_dist.bat`、`validate_dist_exe.py`  
**审查重点**: 过度兜底、静默回退导致 BUG 无法抛出、过度防御性编程  

## 审查计划

- **第一轮（结构与语义审查）**: 审查三个 `.iss` 安装脚本的代码结构、重复度、语义正确性
- **第二轮（防御性编程与静默回退审查）**: 重点审查启动器 `.bat`、安装脚本 `[Code]` 段中的错误处理链路，识别过度兜底和静默吞错
- **第三轮（构建流水线与验证脚本审查）**: 审查 `build_*.bat`、`stage_*.bat`、`validate_dist_exe.py` 的健壮性与错误可见性

## 评审摘要

- 当前状态: 已完成
- 已审模块: installer/aps_win7.iss, installer/aps_win7_chrome.iss, installer/aps_win7_legacy.iss, assets/启动_排产系统_Chrome.bat, installer/aps_win7.iss（[Code]段错误处理）, installer/aps_win7_chrome.iss（[Code]段错误处理）, build_win7_installer.bat, build_win7_onedir.bat, stage_chrome109_to_dist.bat, validate_dist_exe.py
- 当前进度: 已记录 3 个里程碑；最新：round3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 17
- 问题严重级别分布: 高 5 / 中 7 / 低 5
- 最新结论: ## 三轮审查总结 对 `installer/` 目录及关联的构建、启动、验证脚本共 10 个文件（约 2,800 行代码）进行了三轮深度审查，重点关注过度兜底、静默回退导致 BUG 无法暴露、以及过度防御性编程。 ### 审查范围与规模 - **安装脚本**：`aps_win7.iss`（702行）、`aps_win7_chrome.iss`（106行）、`aps_win7_legacy.iss`（696行） - **启动器**：`启动_排产系统_Chrome.bat`（408行） - **构建流水线**：`build_win7_installer.bat`（95行）、`build_win7_onedir.bat`（51行）、`stage_chrome109_to_dist.bat`（77行） - **验证脚本**：`validate_dist_exe.py`（245行） - **文档**：`README_WIN7_INSTALLER.md`（257行） ### 发现统计 共发现 **17 个问题**：高 5 / 中 7 / 低 5。 ### 最严重的问题（需优先修复） 1. **ISS-COPY-SILENT** [高]：数据迁移中单文件复制失败被静默忽略，可能导致用户获得损坏的数据库而不自知 2. **ISS-MIGRATE-PARTIAL** [高]：迁移中途失败不清理半成品数据，且下次安装时半成品会被固化 3. **BAT-WIPE-STOP-SWALLOW** [高]：安装前清理中进程停机失败被完全吞没，可能导致安装覆盖正在运行的实例 4. **BAT-REUSE-LOCK-GAP** [高]：健康检查通过但锁文件缺失时，启动器会删除运行实例的信号文件并尝试创建冲突实例 5. **BAT-WMIC-FAIL-UNSAFE** [高]：WMI 不可用时锁检查降级为 fail-open，违反单用户约束 ### 核心模式总结 **静默回退模式**：整个安装/启动链路中存在大量"操作失败 → 设置一个变量 → 仅在后续某些条件下展示该变量"的模式，导致多处关键失败信号被吞没（ISS-COPY-SILENT、BAT-WIPE-STOP-SWALLOW、ISS-SILENT-UNINSTALL-SWALLOW）。 **过度防御性编程模式**：健康检查的 PowerShell 内联命令包含双重解析回退（ConvertFrom-Json + 正则），但两个路径行为不一致；Chrome 启动后的返回码检查是永远不触发的死代码，给维护者虚假的安全感。 **fail-open 模式**：锁检查（BAT-WMIC-FAIL-UNSAFE）和实例复用（BAT-REUSE-LOCK-GAP）中，当底层机制不可用时默认放行而非阻止，违反了系统的单用户约束设计。 ### 建议修复优先级 1. **P0**：修复迁移链路的静默吞错（ISS-COPY-SILENT + ISS-MIGRATE-PARTIAL），这直接影响用户数据安全 2. **P0**：将锁检查从 fail-open 改为 fail-closed（BAT-WMIC-FAIL-UNSAFE），修复实例复用逻辑（BAT-REUSE-LOCK-GAP） 3. **P1**：展示停机失败警告（BAT-WIPE-STOP-SWALLOW），修复静默卸载吞错（ISS-SILENT-UNINSTALL-SWALLOW） 4. **P2**：消除安装脚本代码重复（ISS-DUP）、简化健康检查（BAT-HEALTH-COMPLEXITY）、修复构建脚本问题
- 下一步建议: 优先修复 P0 级问题：迁移链路的静默吞错（ISS-COPY-SILENT + ISS-MIGRATE-PARTIAL）和锁检查的 fail-open 行为（BAT-WMIC-FAIL-UNSAFE + BAT-REUSE-LOCK-GAP），这些直接影响数据安全和单用户约束。
- 总体结论: 需要后续跟进

## 评审发现

### 主程序包与 legacy 包 [Code] 段近乎完全重复

- ID: ISS-DUP
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round1
- 说明:

  aps_win7.iss 和 aps_win7_legacy.iss 的 [Code] 段约 630 行代码几乎完全一致，仅 InitializeUninstall 的提示文本和 StopApsChrome 参数值（False vs True）、CurStepChanged 的提示文本有差异。任何一处修复或逻辑变更都必须在两个文件中同步完成，极易遗漏。
- 建议:

  将公共的 [Code] 段抽取到 .iss include 文件中，用 #include 引入；或用条件编译 #ifdef LEGACY / #ifndef LEGACY 区分差异点。
- 证据:
  - `installer/aps_win7.iss:71-701`
  - `installer/aps_win7_legacy.iss:68-696`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`

### CopyDirTree 单文件复制失败被静默忽略

- ID: ISS-COPY-SILENT
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round1
- 说明:

  CopyDirTree 中 CopyFile(SourcePath, DestPath, False) 的返回值未被检查。如果某个文件因为权限不足、磁盘空间不够或文件锁定而复制失败，该失败不会被任何层面感知——外层 try/except 不会触发，MigrationNote 会报告'迁移成功'。这意味着用户可能得到一个部分损坏的数据库迁移结果而完全不知情。
- 建议:

  让 CopyDirTree 返回一个失败计数或失败文件列表；MigrateLegacyDataIfNeeded 应检查该返回值并在 MigrationNote 中明确告知用户有文件复制失败。
- 证据:
  - `installer/aps_win7.iss:172-198#CopyDirTree`
  - `installer/aps_win7_legacy.iss:169-195#CopyDirTree`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`

### 迁移失败后不清理半成品数据

- ID: ISS-MIGRATE-PARTIAL
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round1
- 说明:

  MigrateLegacyDataIfNeeded 中的 try/except 在 CopyDirTree 抛出异常时只设置一条 MigrationNote 文本，但不回滚已经复制的部分数据。如果 db 目录已复制成功但 logs 目录复制时出错，共享数据目录会处于不一致状态：有 db 无 logs。更严重的是，由于 HasSharedData 检查 db 是否有内容，下次安装时会认为'已有数据不覆盖'，使得这个半成品状态固化下来。
- 建议:

  迁移失败时应删除已部分复制的共享数据目录内容，或在 MigrationNote 中明确提示用户需要手动清理共享数据目录后重新安装。
- 证据:
  - `installer/aps_win7.iss:496-514#MigrateLegacyDataIfNeeded`
  - `installer/aps_win7.iss`

### TryDeleteDirTree 重试之间无延迟

- ID: ISS-RETRY-NO-DELAY
- 严重级别: 低
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round1
- 说明:

  TryDeleteDirTree 对 rd /s /q 重试3次但相邻重试之间无任何 Sleep。如果目录被占用是因为进程刚收到停止信号正在退出，三次重试会在几十毫秒内全部完成并全部失败。
- 建议:

  在重试之间加入 Sleep(1000) 或 Sleep(500)，给进程退出和文件句柄释放留出时间。
- 证据:
  - `installer/aps_win7.iss:442-451#TryDeleteDirTree`
  - `installer/aps_win7.iss`

### 版本号硬编码为 1.0.0

- ID: ISS-VERSION-HARDCODE
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: round1
- 说明:

  aps_win7.iss 和 aps_win7_legacy.iss 中 MyAppVersion 硬编码为 '1.0.0'，但 README 文档提及当前交付边界为 v1.3.x。版本号与实际交付版本不一致，可能影响 Inno Setup 的升级检测逻辑（同版本号不触发升级覆盖）。
- 建议:

  从外部参数或版本文件注入版本号（如 ISCC /DMyAppVersion=1.3.0），确保与实际交付版本一致。
- 证据:
  - `installer/aps_win7.iss:5`
  - `installer/aps_win7_legacy.iss:5`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`

### 安装前清理中停机失败被静默吞没

- ID: BAT-WIPE-STOP-SWALLOW
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  RunPreInstallFullWipe 在 TryStopKnownApsRuntime 返回失败时仅设置 StopFailure 字符串，然后继续执行目录删除。如果所有目录删除都成功（DeleteErrors 为空），函数返回 True 且 StopFailure 字符串永远不会展示给用户。即：'停机 helper 未确认退出'这一重要警告被完全吞没。这在生产环境中可能导致：进程仍在运行、文件句柄仍被占用，但安装器认为清理成功继续安装，造成数据损坏或文件锁冲突。
- 建议:

  当 StopOk 为 False 但目录删除成功时，仍应通过 MsgBox 或 Log 向用户展示 StopFailure 信息，至少作为警告而非静默忽略。
- 证据:
  - `installer/aps_win7.iss:574-615#RunPreInstallFullWipe`
  - `installer/aps_win7.iss`

### 健康检查通过但锁文件缺失时启动器会创建冲突实例

- ID: BAT-REUSE-LOCK-GAP
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  启动器的 :try_reuse_existing 分支在健康检查通过但锁文件不存在或锁文件中无 PID 时（LOCK_ACTIVE 未定义），不会设置 CAN_REUSE_EXISTING，导致启动器进入'启动新实例'流程。新启动流程会先删除已有的 host/port/db 信号文件（第153-156行），然后启动新的 exe。如果旧进程确实在运行（健康检查已验证），这将：1）删除正在运行的实例的信号文件使其变成孤儿进程；2）新实例尝试绑定已占用端口而失败。根本原因是启动器将'健康检查通过'与'锁文件有效'做了 AND 逻辑判断，但锁文件可能因清理或竞争条件而丢失。
- 建议:

  当健康检查通过时，即使锁文件不可靠，也应设置 CAN_REUSE_EXISTING 或至少跳过'启动新实例'流程。可以增加一个分支：健康通过且无可靠锁 → 复用且记录警告。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:265-297`
  - `assets/启动_排产系统_Chrome.bat`

### 健康检查 PowerShell 内联命令过度复杂且含双重回退

- ID: BAT-HEALTH-COMPLEXITY
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  probe_health（第305行）是一个约 500 字符的 PowerShell 单行内联命令，包含：1）HttpWebRequest 创建与执行；2）ConvertFrom-Json 解析；3）ConvertFrom-Json 不可用时的正则回退；4）三字段严格匹配（app=aps, status=ok, contract_version=1）。这种极端压缩使得该命令几乎无法调试——Win7 的 cmd 中 PowerShell 内联错误不会输出到任何可观察的位置。更重要的是，正则回退分支使用 \x22 转义引号匹配 JSON，如果服务端响应格式略有变化（如字段顺序、空格差异），正则可能失败但 ConvertFrom-Json 可能成功，或反之，两个分支的行为不一致。
- 建议:

  将 PowerShell 健康检查逻辑拆分到独立的 .ps1 文件中，启动器调用该文件并检查退出码。删除正则回退分支——目标平台 Win7 的 PowerShell 2.0+ 已内置 ConvertFrom-Json（PS 3.0+），如果确需兼容 PS 2.0，可只检查 HTTP 状态码而不解析响应体。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:299-313#probe_health`
  - `assets/启动_排产系统_Chrome.bat`

### 端口文件读取无数字验证

- ID: BAT-PORT-NO-VALIDATE
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  read_port_file（第397-402行）读取端口文件后仅去除空格，不验证内容是否为有效数字。如果端口文件被损坏或包含非数字内容，PORT 变量会携带无效值。后续的健康检查 URL 会构造成类似 http://127.0.0.1:abc/system/health，PowerShell 探测会失败但失败原因对用户不透明——日志只会显示 health_fail=<malformed_url>。
- 建议:

  在 read_port_file 后增加一个数字验证步骤：用 set /a 或 findstr 验证 PORT 是否为纯数字；如果不是，记录错误并退出。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:397-402#read_port_file`
  - `assets/启动_排产系统_Chrome.bat`

### Chrome 启动后返回码检查是死代码

- ID: BAT-START-RC-DEAD
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  start 命令（第210行）启动 Chrome 后，第211行 set START_RC=%ERRORLEVEL% 获取的是 start 命令本身的返回码（通常始终为 0），而非 Chrome 进程的退出码。start 是异步启动，即使 Chrome 路径无效或 Chrome 立即崩溃，start 的返回码仍为 0。因此第213行的检查是死代码，永远不会触发错误路径。这给了维护者一种'已处理 Chrome 启动失败'的假象。
- 建议:

  删除这段死代码检查，或改用 start /wait 加超时的方式检测 Chrome 是否存活（例如启动后短暂等待再检查进程是否存在）。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:210-218`
  - `assets/启动_排产系统_Chrome.bat`

### WMI 查询失败时锁检查降级为 fail-open

- ID: BAT-WMIC-FAIL-UNSAFE
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  lock_is_active（第352-358行）使用 wmic process where 来检查进程是否存在。WMIC 在新版 Windows 中已被标记为弃用，但在 Win7 目标环境下可用。更大的问题是：如果 wmic 命令本身执行失败（如权限不足、WMI 服务未运行），for 循环不会匹配到任何输出，LOCK_ACTIVE 保持未定义。这意味着'WMI 不可用'会被误解释为'锁对应的进程不存在'，导致本应被阻止的第二个用户被放行。
- 建议:

  在 wmic 调用后检查 ERRORLEVEL，如果非零则视为'无法确认锁状态'，按保守策略应阻止新用户进入（fail-closed），而非放行（fail-open）。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:352-358#lock_is_active`
  - `assets/启动_排产系统_Chrome.bat`

### 静默卸载时停机失败被完全吞没

- ID: ISS-SILENT-UNINSTALL-SWALLOW
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  InitializeUninstall 中 UninstallSilent() 为 True 时，TryStopKnownApsRuntime 失败仅调用 Log() 记录到 Inno Setup 的内部日志（默认不生成），然后静默继续卸载。这意味着静默卸载场景下，如果 APS 进程无法停止，卸载会继续进行但因文件被占用而残留大量文件，且无任何外部可见的错误信号。
- 建议:

  静默卸载场景下，停机失败应返回 False 以阻止卸载继续，或至少在共享日志目录中写入一个错误标记文件供后续排查。
- 证据:
  - `installer/aps_win7.iss:648-653#InitializeUninstall`
  - `installer/aps_win7.iss`

### 构建脚本引用不存在的 vendor 目录

- ID: BUILD-MISSING-VENDOR
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  build_win7_onedir.bat 第29-38行硬编码了 --add-data "vendor;vendor" 将 vendor 目录打包进 exe，但仓库根目录下不存在 vendor 目录。PyInstaller 在 --add-data 指定的源目录不存在时会报错并止构建。这意味着当前的构建脚本在没有 vendor 目录时无法成功执行，或者该目录被 .gitignore 排除了。
- 建议:

  确认 vendor 目录是否存在；如果是可选依赖，在打包前检查并有条件地添加 --add-data 参数。
- 证据:
  - `build_win7_onedir.bat:29-38`
  - `build_win7_onedir.bat`

### 验证脚本契约文件解析失败被静默吁没为超时

- ID: VALIDATE-PARSE-SWALLOW
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  validate_dist_exe.py 第91-92行的 _read_runtime_contract 在读取 host/port/db 文件时，如果任何一个解析失败（如端口文件内容不是数字），整个 except 块会返回 None。调用方 _wait_for_runtime_contract 将继续等待直到超时，最终报出一个模糊的'未生成运行时契约文件'错误，而不是告诉用户'契约文件存在但格式无效'。这是一个典型的过度兆底导致错误信息丢失的案例。
- 建议:

  区分'文件不存在'和'文件存在但解析失败'两种情况；后者应立即报错而不是继续等待。
- 证据:
  - `validate_dist_exe.py:83-95#_read_runtime_contract`
  - `validate_dist_exe.py`

### 验证脚本进程清理失败被静默吞没

- ID: VALIDATE-KILL-SWALLOW
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  validate_dist_exe.py 第231-239行的 finally 块先调用 p.terminate()，等待5秒；如果 terminate 失败或超时，再调用 p.kill()。两个操作的异常都被完全吞没（裸 except: pass）。如果进程既无法 terminate 也无法 kill，会留下一个孤儿进程占用端口，影响后续构建或测试。验证脚本不会给出任何提示。
- 建议:

  在 p.kill() 失败时打印警告信息，告知用户需要手动结束残留进程。
- 证据:
  - `validate_dist_exe.py:231-239`
  - `validate_dist_exe.py`

### 构建脚本无确认删除上一次产物

- ID: BUILD-CLEAN-NO-CONFIRM
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  build_win7_onedir.bat 在执行 PyInstaller 前无条件删除整个 build 和 dist 目录（第24-25行）。如果 dist 目录中包含用户手动放置的文件或上一次构建的重要产物，将被静默删除且不可恢复。脚本不会提示用户确认。
- 建议:

  在删除 dist 目录前检查是否存在并提示用户，或改为在开头添加注释说明会删除旧产物。
- 证据:
  - `build_win7_onedir.bat:24-25`
  - `build_win7_onedir.bat`

### 构建脚本用模糊匹配查找启动器文件

- ID: BUILD-LAUNCHER-FUZZY
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round3
- 说明:

  build_win7_installer.bat 第32-33行通过 dir /b /s 搜索包含 '*Chrome*.bat' 的文件作为启动器。这个模糊匹配可能匹配到非预期的文件（如临时文件或其他包含 'Chrome' 的脚本），并且只取第一个结果。安装脚本 aps_win7.iss 中已用 #define LauncherBatSource 确定了确切路径，但构建脚本使用模糊匹配与之不一致。
- 建议:

  直接引用 assets 目录下的确切文件名，而不是通过通配符模糊搜索。
- 证据:
  - `build_win7_installer.bat:32-33`
  - `build_win7_installer.bat`

## 评审里程碑

### round1 · 第一轮：结构与语义审查（三个 .iss 安装脚本）

- 状态: 已完成
- 记录时间: 2026-04-03T15:41:12.099Z
- 已审模块: installer/aps_win7.iss, installer/aps_win7_chrome.iss, installer/aps_win7_legacy.iss
- 摘要:

  对 `aps_win7.iss`（702行）、`aps_win7_chrome.iss`（106行）、`aps_win7_legacy.iss`（696行）进行了结构与语义层面的审查。主要发现：三个脚本中主程序包与 legacy 包共享约 95% 的 `[Code]` 段代码，存在严重的代码重复维护负担；数据迁移过程中单文件复制失败被静默忽略；迁移的异常处理过于宽泛，可能导致半成品数据残留无法被用户感知。
- 结论:

  对 `aps_win7.iss`（702行）、`aps_win7_chrome.iss`（106行）、`aps_win7_legacy.iss`（696行）进行了结构与语义层面的审查。主要发现：三个脚本中主程序包与 legacy 包共享约 95% 的 `[Code]` 段代码，存在严重的代码重复维护负担；数据迁移过程中单文件复制失败被静默忽略；迁移的异常处理过于宽泛，可能导致半成品数据残留无法被用户感知。
- 问题:
  - [中] 可维护性: 主程序包与 legacy 包 [Code] 段近乎完全重复
  - [高] JavaScript: CopyDirTree 单文件复制失败被静默忽略
  - [高] JavaScript: 迁移失败后不清理半成品数据
  - [低] JavaScript: TryDeleteDirTree 重试之间无延迟
  - [低] 可维护性: 版本号硬编码为 1.0.0

### round2 · 第二轮：防御性编程与静默回退审查（启动器 + 安装脚本错误链路）

- 状态: 已完成
- 记录时间: 2026-04-03T15:42:17.380Z
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7.iss（[Code]段错误处理）, installer/aps_win7_chrome.iss（[Code]段错误处理）
- 摘要:

  对启动器脚本 `启动_排产系统_Chrome.bat`（408行）和安装脚本 `[Code]` 段的错误处理链路进行了深度审查。发现了多个严重的静默回退问题：安装前清理中停机失败被完全吞没、健康检查通过但锁文件缺失时会创建冲突实例、WMI 查询失败导致单用户锁降级为 fail-open。另外发现了过度防御性编程的典型案例：健康检查的 PowerShell 内联命令包含双重解析回退，以及 Chrome 启动后的返回码检查是永远不会触发的死代码。
- 结论:

  对启动器脚本 `启动_排产系统_Chrome.bat`（408行）和安装脚本 `[Code]` 段的错误处理链路进行了深度审查。发现了多个严重的静默回退问题：安装前清理中停机失败被完全吞没、健康检查通过但锁文件缺失时会创建冲突实例、WMI 查询失败导致单用户锁降级为 fail-open。另外发现了过度防御性编程的典型案例：健康检查的 PowerShell 内联命令包含双重解析回退，以及 Chrome 启动后的返回码检查是永远不会触发的死代码。
- 问题:
  - [高] JavaScript: 安装前清理中停机失败被静默吞没
  - [高] JavaScript: 健康检查通过但锁文件缺失时启动器会创建冲突实例
  - [中] JavaScript: 健康检查 PowerShell 内联命令过度复杂且含双重回退
  - [中] JavaScript: 端口文件读取无数字验证
  - [中] JavaScript: Chrome 启动后返回码检查是死代码
  - [高] JavaScript: WMI 查询失败时锁检查降级为 fail-open
  - [中] JavaScript: 静默卸载时停机失败被完全吞没

### round3 · 第三轮：构建流水线与验证脚本审查

- 状态: 已完成
- 记录时间: 2026-04-03T15:43:26.408Z
- 已审模块: build_win7_installer.bat, build_win7_onedir.bat, stage_chrome109_to_dist.bat, validate_dist_exe.py
- 摘要:

  对构建流水线脚本 `build_win7_installer.bat`（95行）、`build_win7_onedir.bat`（51行）、`stage_chrome109_to_dist.bat`（77行）和验证脚本 `validate_dist_exe.py`（245行）进行了审查。主要发现：构建脚本硬编码引用不存在的 vendor 目录会导致构建直接失败；验证脚本中契约文件解析失败被静默吞没为超时，丢失了真实错误信息；进程清理失败也被完全静默。构建流水线整体设计较为合理，各步骤之间有明确的错误码传递，`stage_chrome109_to_dist.bat` 的 robocopy 返回码处理正确（区分了 0-7 成功与 ≥8 失败）。
- 结论:

  对构建流水线脚本 `build_win7_installer.bat`（95行）、`build_win7_onedir.bat`（51行）、`stage_chrome109_to_dist.bat`（77行）和验证脚本 `validate_dist_exe.py`（245行）进行了审查。主要发现：构建脚本硬编码引用不存在的 vendor 目录会导致构建直接失败；验证脚本中契约文件解析失败被静默吞没为超时，丢失了真实错误信息；进程清理失败也被完全静默。构建流水线整体设计较为合理，各步骤之间有明确的错误码传递，`stage_chrome109_to_dist.bat` 的 robocopy 返回码处理正确（区分了 0-7 成功与 ≥8 失败）。
- 问题:
  - [中] 其他: 构建脚本引用不存在的 vendor 目录
  - [中] 其他: 验证脚本契约文件解析失败被静默吁没为超时
  - [低] 其他: 验证脚本进程清理失败被静默吞没
  - [低] 其他: 构建脚本无确认删除上一次产物
  - [低] 其他: 构建脚本用模糊匹配查找启动器文件

## 最终结论

## 三轮审查总结

对 `installer/` 目录及关联的构建、启动、验证脚本共 10 个文件（约 2,800 行代码）进行了三轮深度审查，重点关注过度兜底、静默回退导致 BUG 无法暴露、以及过度防御性编程。

### 审查范围与规模
- **安装脚本**：`aps_win7.iss`（702行）、`aps_win7_chrome.iss`（106行）、`aps_win7_legacy.iss`（696行）
- **启动器**：`启动_排产系统_Chrome.bat`（408行）
- **构建流水线**：`build_win7_installer.bat`（95行）、`build_win7_onedir.bat`（51行）、`stage_chrome109_to_dist.bat`（77行）
- **验证脚本**：`validate_dist_exe.py`（245行）
- **文档**：`README_WIN7_INSTALLER.md`（257行）

### 发现统计
共发现 **17 个问题**：高 5 / 中 7 / 低 5。

### 最严重的问题（需优先修复）

1. **ISS-COPY-SILENT** [高]：数据迁移中单文件复制失败被静默忽略，可能导致用户获得损坏的数据库而不自知
2. **ISS-MIGRATE-PARTIAL** [高]：迁移中途失败不清理半成品数据，且下次安装时半成品会被固化
3. **BAT-WIPE-STOP-SWALLOW** [高]：安装前清理中进程停机失败被完全吞没，可能导致安装覆盖正在运行的实例
4. **BAT-REUSE-LOCK-GAP** [高]：健康检查通过但锁文件缺失时，启动器会删除运行实例的信号文件并尝试创建冲突实例
5. **BAT-WMIC-FAIL-UNSAFE** [高]：WMI 不可用时锁检查降级为 fail-open，违反单用户约束

### 核心模式总结

**静默回退模式**：整个安装/启动链路中存在大量"操作失败 → 设置一个变量 → 仅在后续某些条件下展示该变量"的模式，导致多处关键失败信号被吞没（ISS-COPY-SILENT、BAT-WIPE-STOP-SWALLOW、ISS-SILENT-UNINSTALL-SWALLOW）。

**过度防御性编程模式**：健康检查的 PowerShell 内联命令包含双重解析回退（ConvertFrom-Json + 正则），但两个路径行为不一致；Chrome 启动后的返回码检查是永远不触发的死代码，给维护者虚假的安全感。

**fail-open 模式**：锁检查（BAT-WMIC-FAIL-UNSAFE）和实例复用（BAT-REUSE-LOCK-GAP）中，当底层机制不可用时默认放行而非阻止，违反了系统的单用户约束设计。

### 建议修复优先级
1. **P0**：修复迁移链路的静默吞错（ISS-COPY-SILENT + ISS-MIGRATE-PARTIAL），这直接影响用户数据安全
2. **P0**：将锁检查从 fail-open 改为 fail-closed（BAT-WMIC-FAIL-UNSAFE），修复实例复用逻辑（BAT-REUSE-LOCK-GAP）
3. **P1**：展示停机失败警告（BAT-WIPE-STOP-SWALLOW），修复静默卸载吞错（ISS-SILENT-UNINSTALL-SWALLOW）
4. **P2**：消除安装脚本代码重复（ISS-DUP）、简化健康检查（BAT-HEALTH-COMPLEXITY）、修复构建脚本问题

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnj2kf39-znfnsx",
  "createdAt": "2026-04-03T00:00:00.000Z",
  "updatedAt": "2026-04-03T15:43:57.403Z",
  "finalizedAt": "2026-04-03T15:43:57.403Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "installer目录深度审查_三轮",
    "date": "2026-04-03",
    "overview": "对 installer/ 目录及关联的构建/启动脚本进行三轮深度审查，重点关注过度兜底、静默回退与过度防御性编程"
  },
  "scope": {
    "markdown": "# installer 目录深度审查（三轮）\n\n**审查日期**: 2026-04-01  \n**审查范围**: `installer/` 目录下全部 `.iss` 脚本，以及关联的 `assets/启动_排产系统_Chrome.bat`、`build_win7_installer.bat`、`build_win7_onedir.bat`、`stage_chrome109_to_dist.bat`、`validate_dist_exe.py`  \n**审查重点**: 过度兜底、静默回退导致 BUG 无法抛出、过度防御性编程  \n\n## 审查计划\n\n- **第一轮（结构与语义审查）**: 审查三个 `.iss` 安装脚本的代码结构、重复度、语义正确性\n- **第二轮（防御性编程与静默回退审查）**: 重点审查启动器 `.bat`、安装脚本 `[Code]` 段中的错误处理链路，识别过度兜底和静默吞错\n- **第三轮（构建流水线与验证脚本审查）**: 审查 `build_*.bat`、`stage_*.bat`、`validate_dist_exe.py` 的健壮性与错误可见性"
  },
  "summary": {
    "latestConclusion": "## 三轮审查总结\n\n对 `installer/` 目录及关联的构建、启动、验证脚本共 10 个文件（约 2,800 行代码）进行了三轮深度审查，重点关注过度兜底、静默回退导致 BUG 无法暴露、以及过度防御性编程。\n\n### 审查范围与规模\n- **安装脚本**：`aps_win7.iss`（702行）、`aps_win7_chrome.iss`（106行）、`aps_win7_legacy.iss`（696行）\n- **启动器**：`启动_排产系统_Chrome.bat`（408行）\n- **构建流水线**：`build_win7_installer.bat`（95行）、`build_win7_onedir.bat`（51行）、`stage_chrome109_to_dist.bat`（77行）\n- **验证脚本**：`validate_dist_exe.py`（245行）\n- **文档**：`README_WIN7_INSTALLER.md`（257行）\n\n### 发现统计\n共发现 **17 个问题**：高 5 / 中 7 / 低 5。\n\n### 最严重的问题（需优先修复）\n\n1. **ISS-COPY-SILENT** [高]：数据迁移中单文件复制失败被静默忽略，可能导致用户获得损坏的数据库而不自知\n2. **ISS-MIGRATE-PARTIAL** [高]：迁移中途失败不清理半成品数据，且下次安装时半成品会被固化\n3. **BAT-WIPE-STOP-SWALLOW** [高]：安装前清理中进程停机失败被完全吞没，可能导致安装覆盖正在运行的实例\n4. **BAT-REUSE-LOCK-GAP** [高]：健康检查通过但锁文件缺失时，启动器会删除运行实例的信号文件并尝试创建冲突实例\n5. **BAT-WMIC-FAIL-UNSAFE** [高]：WMI 不可用时锁检查降级为 fail-open，违反单用户约束\n\n### 核心模式总结\n\n**静默回退模式**：整个安装/启动链路中存在大量\"操作失败 → 设置一个变量 → 仅在后续某些条件下展示该变量\"的模式，导致多处关键失败信号被吞没（ISS-COPY-SILENT、BAT-WIPE-STOP-SWALLOW、ISS-SILENT-UNINSTALL-SWALLOW）。\n\n**过度防御性编程模式**：健康检查的 PowerShell 内联命令包含双重解析回退（ConvertFrom-Json + 正则），但两个路径行为不一致；Chrome 启动后的返回码检查是永远不触发的死代码，给维护者虚假的安全感。\n\n**fail-open 模式**：锁检查（BAT-WMIC-FAIL-UNSAFE）和实例复用（BAT-REUSE-LOCK-GAP）中，当底层机制不可用时默认放行而非阻止，违反了系统的单用户约束设计。\n\n### 建议修复优先级\n1. **P0**：修复迁移链路的静默吞错（ISS-COPY-SILENT + ISS-MIGRATE-PARTIAL），这直接影响用户数据安全\n2. **P0**：将锁检查从 fail-open 改为 fail-closed（BAT-WMIC-FAIL-UNSAFE），修复实例复用逻辑（BAT-REUSE-LOCK-GAP）\n3. **P1**：展示停机失败警告（BAT-WIPE-STOP-SWALLOW），修复静默卸载吞错（ISS-SILENT-UNINSTALL-SWALLOW）\n4. **P2**：消除安装脚本代码重复（ISS-DUP）、简化健康检查（BAT-HEALTH-COMPLEXITY）、修复构建脚本问题",
    "recommendedNextAction": "优先修复 P0 级问题：迁移链路的静默吞错（ISS-COPY-SILENT + ISS-MIGRATE-PARTIAL）和锁检查的 fail-open 行为（BAT-WMIC-FAIL-UNSAFE + BAT-REUSE-LOCK-GAP），这些直接影响数据安全和单用户约束。",
    "reviewedModules": [
      "installer/aps_win7.iss",
      "installer/aps_win7_chrome.iss",
      "installer/aps_win7_legacy.iss",
      "assets/启动_排产系统_Chrome.bat",
      "installer/aps_win7.iss（[Code]段错误处理）",
      "installer/aps_win7_chrome.iss（[Code]段错误处理）",
      "build_win7_installer.bat",
      "build_win7_onedir.bat",
      "stage_chrome109_to_dist.bat",
      "validate_dist_exe.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 17,
    "severity": {
      "high": 5,
      "medium": 7,
      "low": 5
    }
  },
  "milestones": [
    {
      "id": "round1",
      "title": "第一轮：结构与语义审查（三个 .iss 安装脚本）",
      "status": "completed",
      "recordedAt": "2026-04-03T15:41:12.099Z",
      "summaryMarkdown": "对 `aps_win7.iss`（702行）、`aps_win7_chrome.iss`（106行）、`aps_win7_legacy.iss`（696行）进行了结构与语义层面的审查。主要发现：三个脚本中主程序包与 legacy 包共享约 95% 的 `[Code]` 段代码，存在严重的代码重复维护负担；数据迁移过程中单文件复制失败被静默忽略；迁移的异常处理过于宽泛，可能导致半成品数据残留无法被用户感知。",
      "conclusionMarkdown": "对 `aps_win7.iss`（702行）、`aps_win7_chrome.iss`（106行）、`aps_win7_legacy.iss`（696行）进行了结构与语义层面的审查。主要发现：三个脚本中主程序包与 legacy 包共享约 95% 的 `[Code]` 段代码，存在严重的代码重复维护负担；数据迁移过程中单文件复制失败被静默忽略；迁移的异常处理过于宽泛，可能导致半成品数据残留无法被用户感知。",
      "evidence": [],
      "reviewedModules": [
        "installer/aps_win7.iss",
        "installer/aps_win7_chrome.iss",
        "installer/aps_win7_legacy.iss"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "ISS-DUP",
        "ISS-COPY-SILENT",
        "ISS-MIGRATE-PARTIAL",
        "ISS-RETRY-NO-DELAY",
        "ISS-VERSION-HARDCODE"
      ]
    },
    {
      "id": "round2",
      "title": "第二轮：防御性编程与静默回退审查（启动器 + 安装脚本错误链路）",
      "status": "completed",
      "recordedAt": "2026-04-03T15:42:17.380Z",
      "summaryMarkdown": "对启动器脚本 `启动_排产系统_Chrome.bat`（408行）和安装脚本 `[Code]` 段的错误处理链路进行了深度审查。发现了多个严重的静默回退问题：安装前清理中停机失败被完全吞没、健康检查通过但锁文件缺失时会创建冲突实例、WMI 查询失败导致单用户锁降级为 fail-open。另外发现了过度防御性编程的典型案例：健康检查的 PowerShell 内联命令包含双重解析回退，以及 Chrome 启动后的返回码检查是永远不会触发的死代码。",
      "conclusionMarkdown": "对启动器脚本 `启动_排产系统_Chrome.bat`（408行）和安装脚本 `[Code]` 段的错误处理链路进行了深度审查。发现了多个严重的静默回退问题：安装前清理中停机失败被完全吞没、健康检查通过但锁文件缺失时会创建冲突实例、WMI 查询失败导致单用户锁降级为 fail-open。另外发现了过度防御性编程的典型案例：健康检查的 PowerShell 内联命令包含双重解析回退，以及 Chrome 启动后的返回码检查是永远不会触发的死代码。",
      "evidence": [],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "installer/aps_win7.iss（[Code]段错误处理）",
        "installer/aps_win7_chrome.iss（[Code]段错误处理）"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "BAT-WIPE-STOP-SWALLOW",
        "BAT-REUSE-LOCK-GAP",
        "BAT-HEALTH-COMPLEXITY",
        "BAT-PORT-NO-VALIDATE",
        "BAT-START-RC-DEAD",
        "BAT-WMIC-FAIL-UNSAFE",
        "ISS-SILENT-UNINSTALL-SWALLOW"
      ]
    },
    {
      "id": "round3",
      "title": "第三轮：构建流水线与验证脚本审查",
      "status": "completed",
      "recordedAt": "2026-04-03T15:43:26.408Z",
      "summaryMarkdown": "对构建流水线脚本 `build_win7_installer.bat`（95行）、`build_win7_onedir.bat`（51行）、`stage_chrome109_to_dist.bat`（77行）和验证脚本 `validate_dist_exe.py`（245行）进行了审查。主要发现：构建脚本硬编码引用不存在的 vendor 目录会导致构建直接失败；验证脚本中契约文件解析失败被静默吞没为超时，丢失了真实错误信息；进程清理失败也被完全静默。构建流水线整体设计较为合理，各步骤之间有明确的错误码传递，`stage_chrome109_to_dist.bat` 的 robocopy 返回码处理正确（区分了 0-7 成功与 ≥8 失败）。",
      "conclusionMarkdown": "对构建流水线脚本 `build_win7_installer.bat`（95行）、`build_win7_onedir.bat`（51行）、`stage_chrome109_to_dist.bat`（77行）和验证脚本 `validate_dist_exe.py`（245行）进行了审查。主要发现：构建脚本硬编码引用不存在的 vendor 目录会导致构建直接失败；验证脚本中契约文件解析失败被静默吞没为超时，丢失了真实错误信息；进程清理失败也被完全静默。构建流水线整体设计较为合理，各步骤之间有明确的错误码传递，`stage_chrome109_to_dist.bat` 的 robocopy 返回码处理正确（区分了 0-7 成功与 ≥8 失败）。",
      "evidence": [],
      "reviewedModules": [
        "build_win7_installer.bat",
        "build_win7_onedir.bat",
        "stage_chrome109_to_dist.bat",
        "validate_dist_exe.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "BUILD-MISSING-VENDOR",
        "VALIDATE-PARSE-SWALLOW",
        "VALIDATE-KILL-SWALLOW",
        "BUILD-CLEAN-NO-CONFIRM",
        "BUILD-LAUNCHER-FUZZY"
      ]
    }
  ],
  "findings": [
    {
      "id": "ISS-DUP",
      "severity": "medium",
      "category": "maintainability",
      "title": "主程序包与 legacy 包 [Code] 段近乎完全重复",
      "descriptionMarkdown": "aps_win7.iss 和 aps_win7_legacy.iss 的 [Code] 段约 630 行代码几乎完全一致，仅 InitializeUninstall 的提示文本和 StopApsChrome 参数值（False vs True）、CurStepChanged 的提示文本有差异。任何一处修复或逻辑变更都必须在两个文件中同步完成，极易遗漏。",
      "recommendationMarkdown": "将公共的 [Code] 段抽取到 .iss include 文件中，用 #include 引入；或用条件编译 #ifdef LEGACY / #ifndef LEGACY 区分差异点。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 71,
          "lineEnd": 701
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 68,
          "lineEnd": 696
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "ISS-COPY-SILENT",
      "severity": "high",
      "category": "javascript",
      "title": "CopyDirTree 单文件复制失败被静默忽略",
      "descriptionMarkdown": "CopyDirTree 中 CopyFile(SourcePath, DestPath, False) 的返回值未被检查。如果某个文件因为权限不足、磁盘空间不够或文件锁定而复制失败，该失败不会被任何层面感知——外层 try/except 不会触发，MigrationNote 会报告'迁移成功'。这意味着用户可能得到一个部分损坏的数据库迁移结果而完全不知情。",
      "recommendationMarkdown": "让 CopyDirTree 返回一个失败计数或失败文件列表；MigrateLegacyDataIfNeeded 应检查该返回值并在 MigrationNote 中明确告知用户有文件复制失败。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 172,
          "lineEnd": 198,
          "symbol": "CopyDirTree"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 169,
          "lineEnd": 195,
          "symbol": "CopyDirTree"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "ISS-MIGRATE-PARTIAL",
      "severity": "high",
      "category": "javascript",
      "title": "迁移失败后不清理半成品数据",
      "descriptionMarkdown": "MigrateLegacyDataIfNeeded 中的 try/except 在 CopyDirTree 抛出异常时只设置一条 MigrationNote 文本，但不回滚已经复制的部分数据。如果 db 目录已复制成功但 logs 目录复制时出错，共享数据目录会处于不一致状态：有 db 无 logs。更严重的是，由于 HasSharedData 检查 db 是否有内容，下次安装时会认为'已有数据不覆盖'，使得这个半成品状态固化下来。",
      "recommendationMarkdown": "迁移失败时应删除已部分复制的共享数据目录内容，或在 MigrationNote 中明确提示用户需要手动清理共享数据目录后重新安装。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 496,
          "lineEnd": 514,
          "symbol": "MigrateLegacyDataIfNeeded"
        },
        {
          "path": "installer/aps_win7.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "ISS-RETRY-NO-DELAY",
      "severity": "low",
      "category": "javascript",
      "title": "TryDeleteDirTree 重试之间无延迟",
      "descriptionMarkdown": "TryDeleteDirTree 对 rd /s /q 重试3次但相邻重试之间无任何 Sleep。如果目录被占用是因为进程刚收到停止信号正在退出，三次重试会在几十毫秒内全部完成并全部失败。",
      "recommendationMarkdown": "在重试之间加入 Sleep(1000) 或 Sleep(500)，给进程退出和文件句柄释放留出时间。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 442,
          "lineEnd": 451,
          "symbol": "TryDeleteDirTree"
        },
        {
          "path": "installer/aps_win7.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "ISS-VERSION-HARDCODE",
      "severity": "low",
      "category": "maintainability",
      "title": "版本号硬编码为 1.0.0",
      "descriptionMarkdown": "aps_win7.iss 和 aps_win7_legacy.iss 中 MyAppVersion 硬编码为 '1.0.0'，但 README 文档提及当前交付边界为 v1.3.x。版本号与实际交付版本不一致，可能影响 Inno Setup 的升级检测逻辑（同版本号不触发升级覆盖）。",
      "recommendationMarkdown": "从外部参数或版本文件注入版本号（如 ISCC /DMyAppVersion=1.3.0），确保与实际交付版本一致。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 5
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 5
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BAT-WIPE-STOP-SWALLOW",
      "severity": "high",
      "category": "javascript",
      "title": "安装前清理中停机失败被静默吞没",
      "descriptionMarkdown": "RunPreInstallFullWipe 在 TryStopKnownApsRuntime 返回失败时仅设置 StopFailure 字符串，然后继续执行目录删除。如果所有目录删除都成功（DeleteErrors 为空），函数返回 True 且 StopFailure 字符串永远不会展示给用户。即：'停机 helper 未确认退出'这一重要警告被完全吞没。这在生产环境中可能导致：进程仍在运行、文件句柄仍被占用，但安装器认为清理成功继续安装，造成数据损坏或文件锁冲突。",
      "recommendationMarkdown": "当 StopOk 为 False 但目录删除成功时，仍应通过 MsgBox 或 Log 向用户展示 StopFailure 信息，至少作为警告而非静默忽略。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 574,
          "lineEnd": 615,
          "symbol": "RunPreInstallFullWipe"
        },
        {
          "path": "installer/aps_win7.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BAT-REUSE-LOCK-GAP",
      "severity": "high",
      "category": "javascript",
      "title": "健康检查通过但锁文件缺失时启动器会创建冲突实例",
      "descriptionMarkdown": "启动器的 :try_reuse_existing 分支在健康检查通过但锁文件不存在或锁文件中无 PID 时（LOCK_ACTIVE 未定义），不会设置 CAN_REUSE_EXISTING，导致启动器进入'启动新实例'流程。新启动流程会先删除已有的 host/port/db 信号文件（第153-156行），然后启动新的 exe。如果旧进程确实在运行（健康检查已验证），这将：1）删除正在运行的实例的信号文件使其变成孤儿进程；2）新实例尝试绑定已占用端口而失败。根本原因是启动器将'健康检查通过'与'锁文件有效'做了 AND 逻辑判断，但锁文件可能因清理或竞争条件而丢失。",
      "recommendationMarkdown": "当健康检查通过时，即使锁文件不可靠，也应设置 CAN_REUSE_EXISTING 或至少跳过'启动新实例'流程。可以增加一个分支：健康通过且无可靠锁 → 复用且记录警告。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 265,
          "lineEnd": 297
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BAT-HEALTH-COMPLEXITY",
      "severity": "medium",
      "category": "javascript",
      "title": "健康检查 PowerShell 内联命令过度复杂且含双重回退",
      "descriptionMarkdown": "probe_health（第305行）是一个约 500 字符的 PowerShell 单行内联命令，包含：1）HttpWebRequest 创建与执行；2）ConvertFrom-Json 解析；3）ConvertFrom-Json 不可用时的正则回退；4）三字段严格匹配（app=aps, status=ok, contract_version=1）。这种极端压缩使得该命令几乎无法调试——Win7 的 cmd 中 PowerShell 内联错误不会输出到任何可观察的位置。更重要的是，正则回退分支使用 \\x22 转义引号匹配 JSON，如果服务端响应格式略有变化（如字段顺序、空格差异），正则可能失败但 ConvertFrom-Json 可能成功，或反之，两个分支的行为不一致。",
      "recommendationMarkdown": "将 PowerShell 健康检查逻辑拆分到独立的 .ps1 文件中，启动器调用该文件并检查退出码。删除正则回退分支——目标平台 Win7 的 PowerShell 2.0+ 已内置 ConvertFrom-Json（PS 3.0+），如果确需兼容 PS 2.0，可只检查 HTTP 状态码而不解析响应体。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 299,
          "lineEnd": 313,
          "symbol": "probe_health"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BAT-PORT-NO-VALIDATE",
      "severity": "medium",
      "category": "javascript",
      "title": "端口文件读取无数字验证",
      "descriptionMarkdown": "read_port_file（第397-402行）读取端口文件后仅去除空格，不验证内容是否为有效数字。如果端口文件被损坏或包含非数字内容，PORT 变量会携带无效值。后续的健康检查 URL 会构造成类似 http://127.0.0.1:abc/system/health，PowerShell 探测会失败但失败原因对用户不透明——日志只会显示 health_fail=<malformed_url>。",
      "recommendationMarkdown": "在 read_port_file 后增加一个数字验证步骤：用 set /a 或 findstr 验证 PORT 是否为纯数字；如果不是，记录错误并退出。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 397,
          "lineEnd": 402,
          "symbol": "read_port_file"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BAT-START-RC-DEAD",
      "severity": "medium",
      "category": "javascript",
      "title": "Chrome 启动后返回码检查是死代码",
      "descriptionMarkdown": "start 命令（第210行）启动 Chrome 后，第211行 set START_RC=%ERRORLEVEL% 获取的是 start 命令本身的返回码（通常始终为 0），而非 Chrome 进程的退出码。start 是异步启动，即使 Chrome 路径无效或 Chrome 立即崩溃，start 的返回码仍为 0。因此第213行的检查是死代码，永远不会触发错误路径。这给了维护者一种'已处理 Chrome 启动失败'的假象。",
      "recommendationMarkdown": "删除这段死代码检查，或改用 start /wait 加超时的方式检测 Chrome 是否存活（例如启动后短暂等待再检查进程是否存在）。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 210,
          "lineEnd": 218
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BAT-WMIC-FAIL-UNSAFE",
      "severity": "high",
      "category": "javascript",
      "title": "WMI 查询失败时锁检查降级为 fail-open",
      "descriptionMarkdown": "lock_is_active（第352-358行）使用 wmic process where 来检查进程是否存在。WMIC 在新版 Windows 中已被标记为弃用，但在 Win7 目标环境下可用。更大的问题是：如果 wmic 命令本身执行失败（如权限不足、WMI 服务未运行），for 循环不会匹配到任何输出，LOCK_ACTIVE 保持未定义。这意味着'WMI 不可用'会被误解释为'锁对应的进程不存在'，导致本应被阻止的第二个用户被放行。",
      "recommendationMarkdown": "在 wmic 调用后检查 ERRORLEVEL，如果非零则视为'无法确认锁状态'，按保守策略应阻止新用户进入（fail-closed），而非放行（fail-open）。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 352,
          "lineEnd": 358,
          "symbol": "lock_is_active"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "ISS-SILENT-UNINSTALL-SWALLOW",
      "severity": "medium",
      "category": "javascript",
      "title": "静默卸载时停机失败被完全吞没",
      "descriptionMarkdown": "InitializeUninstall 中 UninstallSilent() 为 True 时，TryStopKnownApsRuntime 失败仅调用 Log() 记录到 Inno Setup 的内部日志（默认不生成），然后静默继续卸载。这意味着静默卸载场景下，如果 APS 进程无法停止，卸载会继续进行但因文件被占用而残留大量文件，且无任何外部可见的错误信号。",
      "recommendationMarkdown": "静默卸载场景下，停机失败应返回 False 以阻止卸载继续，或至少在共享日志目录中写入一个错误标记文件供后续排查。",
      "evidence": [
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 648,
          "lineEnd": 653,
          "symbol": "InitializeUninstall"
        },
        {
          "path": "installer/aps_win7.iss"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BUILD-MISSING-VENDOR",
      "severity": "medium",
      "category": "other",
      "title": "构建脚本引用不存在的 vendor 目录",
      "descriptionMarkdown": "build_win7_onedir.bat 第29-38行硬编码了 --add-data \"vendor;vendor\" 将 vendor 目录打包进 exe，但仓库根目录下不存在 vendor 目录。PyInstaller 在 --add-data 指定的源目录不存在时会报错并止构建。这意味着当前的构建脚本在没有 vendor 目录时无法成功执行，或者该目录被 .gitignore 排除了。",
      "recommendationMarkdown": "确认 vendor 目录是否存在；如果是可选依赖，在打包前检查并有条件地添加 --add-data 参数。",
      "evidence": [
        {
          "path": "build_win7_onedir.bat",
          "lineStart": 29,
          "lineEnd": 38
        },
        {
          "path": "build_win7_onedir.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "VALIDATE-PARSE-SWALLOW",
      "severity": "medium",
      "category": "other",
      "title": "验证脚本契约文件解析失败被静默吁没为超时",
      "descriptionMarkdown": "validate_dist_exe.py 第91-92行的 _read_runtime_contract 在读取 host/port/db 文件时，如果任何一个解析失败（如端口文件内容不是数字），整个 except 块会返回 None。调用方 _wait_for_runtime_contract 将继续等待直到超时，最终报出一个模糊的'未生成运行时契约文件'错误，而不是告诉用户'契约文件存在但格式无效'。这是一个典型的过度兆底导致错误信息丢失的案例。",
      "recommendationMarkdown": "区分'文件不存在'和'文件存在但解析失败'两种情况；后者应立即报错而不是继续等待。",
      "evidence": [
        {
          "path": "validate_dist_exe.py",
          "lineStart": 83,
          "lineEnd": 95,
          "symbol": "_read_runtime_contract"
        },
        {
          "path": "validate_dist_exe.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "VALIDATE-KILL-SWALLOW",
      "severity": "low",
      "category": "other",
      "title": "验证脚本进程清理失败被静默吞没",
      "descriptionMarkdown": "validate_dist_exe.py 第231-239行的 finally 块先调用 p.terminate()，等待5秒；如果 terminate 失败或超时，再调用 p.kill()。两个操作的异常都被完全吞没（裸 except: pass）。如果进程既无法 terminate 也无法 kill，会留下一个孤儿进程占用端口，影响后续构建或测试。验证脚本不会给出任何提示。",
      "recommendationMarkdown": "在 p.kill() 失败时打印警告信息，告知用户需要手动结束残留进程。",
      "evidence": [
        {
          "path": "validate_dist_exe.py",
          "lineStart": 231,
          "lineEnd": 239
        },
        {
          "path": "validate_dist_exe.py"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BUILD-CLEAN-NO-CONFIRM",
      "severity": "low",
      "category": "other",
      "title": "构建脚本无确认删除上一次产物",
      "descriptionMarkdown": "build_win7_onedir.bat 在执行 PyInstaller 前无条件删除整个 build 和 dist 目录（第24-25行）。如果 dist 目录中包含用户手动放置的文件或上一次构建的重要产物，将被静默删除且不可恢复。脚本不会提示用户确认。",
      "recommendationMarkdown": "在删除 dist 目录前检查是否存在并提示用户，或改为在开头添加注释说明会删除旧产物。",
      "evidence": [
        {
          "path": "build_win7_onedir.bat",
          "lineStart": 24,
          "lineEnd": 25
        },
        {
          "path": "build_win7_onedir.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "BUILD-LAUNCHER-FUZZY",
      "severity": "low",
      "category": "other",
      "title": "构建脚本用模糊匹配查找启动器文件",
      "descriptionMarkdown": "build_win7_installer.bat 第32-33行通过 dir /b /s 搜索包含 '*Chrome*.bat' 的文件作为启动器。这个模糊匹配可能匹配到非预期的文件（如临时文件或其他包含 'Chrome' 的脚本），并且只取第一个结果。安装脚本 aps_win7.iss 中已用 #define LauncherBatSource 确定了确切路径，但构建脚本使用模糊匹配与之不一致。",
      "recommendationMarkdown": "直接引用 assets 目录下的确切文件名，而不是通过通配符模糊搜索。",
      "evidence": [
        {
          "path": "build_win7_installer.bat",
          "lineStart": 32,
          "lineEnd": 33
        },
        {
          "path": "build_win7_installer.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:7d653ebd7a7c5c1d21cdedd92b3628878f4bc04c82493e6b7b48651227fc2053",
    "generatedAt": "2026-04-03T15:43:57.403Z",
    "locale": "zh-CN"
  }
}
```
