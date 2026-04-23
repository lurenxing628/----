# APS启动链路与Chrome残余问题修复plan三轮深度审查
- 日期: 2026-04-07
- 概述: 对plan与其实际已落地实现进行三轮深度交叉审查，验证目标达成度、实现质量与残留风险。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# APS启动链路与Chrome残余问题修复plan三轮深度审查

- 日期：2026-04-07
- 范围：plan 本身与所有涉及文件的实际实现
- 审查目标：验证 plan 中四个任务的已实现状态与质量，识别残留BUG与设计缺陷

## 审查策略

**第一轮**：逐任务比对 plan 目标与实际代码，确认"是否真正做到了"。
**第二轮**：深入每段关键实现的逻辑链路，挖掘BUG与边界条件问题。
**第三轮**：跨端一致性交叉验证，评估三端（批处理/安装器/Python）语义是否真正统一。

## 评审摘要

- 当前状态: 已完成
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, tests/test_win7_launcher_runtime_paths.py, installer/README_WIN7_INSTALLER.md, DELIVERY_WIN7.md
- 当前进度: 已记录 3 个里程碑；最新：R3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 0 / 中 1 / 低 2
- 最新结论: ## 三轮深度审查总结 本次对 `APS启动链路与Chrome残余问题修复plan` 进行了三轮递进式深度审查，覆盖了 plan 中全部四个任务所涉及的 6 个核心文件和 676 行批处理、173 行安装器、995 行 Python、307 行测试以及两份关键文档。 ### 总体评价 **plan 达成度：高**。四个任务中三个代码任务已全部落地，第四个（现场验收）是合理的待办。plan 的问题定义清晰、步骤拆分合理、完成标准可验证。 **实现质量：优**。三端的核心改动（浏览器判活收紧、跨账户匹配、Python 注释）都做到了简洁精确、没有过度兜底、没有静默回退。所有失败路径都是严格闭合的——不存在"查询失败就假装成功"的降级分支。 **无严重BUG**。深入跟踪了 CimInstance/WmiObject 降级链条、单引号字符串注入防护、JSON 反转义全链路、跨账户进程可见性与关闭权限等边界条件，均未发现功能性缺陷。 ### 发现问题汇总 | 严重级别 | 数量 | 说明 | |---------|------|------| | 高 | 0 | 无 | | 中 | 1 | 关键行为变更仅有静态字符串守卫，缺乏运行时行为验证 | | 低 | 2 | 无 PowerShell 时用户提示不够明确；PowerShell 执行策略参数三端不一致 | 三个问题均不影响当前实现的正确性和安全性，都是可维护性层面的改进建议。 ### 设计亮点 1. **分层匹配策略**：批处理/Python 用精确路径、安装器用路径+后缀 marker，三者各取所需又共享同一核心语义"只认 APS 专用 `--user-data-dir` 命令行"。 2. **严格失败闭合**：三端在查询失败时都不做任何降级——不回退到旧的按镜像名宽匹配，不把"查不到"等价于"没进程"。 3. **最小改动原则**：Python 侧已有 `--user-data-dir` 检查，plan 明确判断后只补了三行注释，没有做无关扩散。 4. **文档即代码**：两份交付文档同步更新了"成功判定更严格"和"卸载匹配跨账户"的口径，并新增了现场验收段落。 ### 建议下一步 1. 在真实 Windows 机器上完成"普通 Chrome 共存"与"双账户卸载"两组现场验收。 2. 运行四条自动回归命令确认代码已到位的测试全部通过。 3. 择机把无 PowerShell 时的用户提示改得更具体一些（低优先级）。
- 下一步建议: 在真实 Windows 机器上完成"普通 Chrome 共存"与"双账户卸载"两组现场验收后，此 plan 可视为完全闭合。
- 总体结论: 有条件通过

## 评审发现

### 无 PowerShell 时失败提示未指出原因

- ID: no-ps-hint
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  批处理 :probe_aps_chrome_alive 的 no_powershell 分支（第609-612行）在 PowerShell 不可用时直接返回失败，但后续的用户提示（第262-266行）只写'未能确认 APS 专用浏览器已拉起'，没有提示原因是缺少 PowerShell。用户在极简 Win7 环境下遇到此失败时无法从屏幕提示中定位根因，只能去翻 launcher.log 找 chrome_alive_probe=no_powershell。影响：不影响安全性和正确性，但会增加现场排障时间。
- 建议:

  在 no_powershell 路径中增加用户可见提示，例如在 exit /b 11 前加 echo [launcher] PowerShell 不可用，无法验证浏览器启动状态。

### PowerShell 执行策略参数三端不一致

- ID: exec-policy-inconsistency
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  三端在调用 PowerShell 时，执行策略参数不一致：安装器 BuildStopChromePowerShellParams 使用 -ExecutionPolicy Bypass（第76行）；批处理 :probe_aps_chrome_alive 和 :probe_health 只使用 -NoProfile 不带 -ExecutionPolicy；Python _run_powershell_text 也只使用 -NoProfile（第748行）。从功能上看 -Command 参数天然绕过执行策略（策略只限制 .ps1 脚本文件），所以这不是功能性BUG。但三端风格不统一会让维护者困惑到底需不需要加 -ExecutionPolicy，增加将来误改的风险。
- 建议:

  统一到三端都加 -ExecutionPolicy Bypass -NoProfile 或三端都只用 -NoProfile。推荐前者因为最显式最防御。

### 关键行为变更仅有静态守卫无运行时验证

- ID: static-tests-only
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  当前所有与浏览器判活和安装器 stop helper 相关的测试都是静态字符串检查：读取源文件文本内容检查是否包含预期字符串。这类守卫能防止关键逻辑被意外删除，但无法验证运行时行为。例如：无法验证 PowerShell 脚本实际执行结果、无法验证 profile 路径匹配在实际 Chrome 进程上是否工作、无法验证安装器卸载时跨账户进程停止是否成功。plan 本身已经意识到这一点并在任务 3 中明确要求现场验收，但自动化测试的覆盖天花板是一个需要持续关注的结构性问题。
- 建议:

  长期考虑在打包流水线中增加一步端到端冒烟：在实际启动 Chrome 后执行 probe 验证至少覆盖启动加 probe 匹配这条主路径。

## 评审里程碑

### R1 · 第一轮：逐任务比对 plan 目标与实际实现

- 状态: 已完成
- 记录时间: 2026-04-07T05:01:11.026Z
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, tests/test_win7_launcher_runtime_paths.py
- 摘要:

  逐任务验证了 plan 中四个任务的实际落地状态。

  **任务 1（启动器浏览器判活收紧）**：已完全落地。批处理中新增了 `:probe_aps_chrome_alive` 子程序（第607-626行），使用 `Get-CimInstance`/`Get-WmiObject` 查询 `Win32_Process`，仅当命令行同时包含 `--user-data-dir` 和当前 `CHROME_PROFILE_DIR` 归一化路径时才判定成功。旧的按镜像名宽匹配判活逻辑已被移除，整个批处理中不存在任何 `tasklist /FI "IMAGENAME eq chrome.exe"` 的分支。没有 PowerShell 时明确记录 `chrome_alive_probe=no_powershell` 并按失败处理，不做任何降级。失败时以 `exit /b 11` 退出并显示"未能确认 APS 专用浏览器已拉起"提示。

  **任务 2（安装器跨账户匹配收紧）**：已完全落地。新增了 `ApsChromeProfileSuffixMarker()` 函数返回 `\aps\chrome109profile` 后缀；`BuildStopChromePowerShellParams` 同时接收精确路径和后缀 marker，生成的 PowerShell 中定义了 `Test-ApsChromeCommandLine` 函数，检查命令行包含 `--user-data-dir` 且匹配后缀 marker 或精确路径（逻辑或短路）。停止后执行二次查询验证，任何目标进程仍存在则 `exit 1`。`TryStopApsChromeProcesses` 正确调用了 `BuildStopChromePowerShellParams(CurrentUserChromeProfilePath(), ApsChromeProfileSuffixMarker())`。

  **任务 3（验证证据）**：自动化静态守卫已完成（`test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process`、`test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only` 等）；回归测试命令已列出。但 plan 明确标注的两组现场验收（普通 Chrome 共存 + 双账户卸载）标记为待现场执行，这是合理的——这类验收确实不能由自动化测试完成。

  **任务 4（Python 侧注释）**：已在 `_list_aps_chrome_pids()` 上方添加三行注释（第833-835行），清晰说明了三端的匹配口径差异和共同目标。Python 实现本身已经具备 `--user-data-dir` 条件检查（第859行），无需额外改代码。

  **`normalize_contract_owner` 修复**：第545行的 `set "CONTRACT_OWNER=!CONTRACT_OWNER:\\=\\!"` 正确实现了 JSON 反转义（`\\` → `\`），配合第518行的 `call :normalize_contract_owner`，消除了契约回退路径下同账户误判问题。

  **TODO 状态校验**：
  - `#p1` 标记完成 ✓ → 代码确认已落地
  - `#p2` 标记完成 ✓ → 代码确认已落地  
  - `#p3` 标记未完成 → 正确，现场验收确实待做
  - `#p4` 标记完成 ✓ → 注释确认已添加
- 结论:

  plan 中四个任务的代码落地部分全部到位，目标达成度高。唯一未闭合的是现场验收环节（#p3），但这是 plan 本身的有意安排，不是遗漏。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:607-626#probe_aps_chrome_alive`
  - `assets/启动_排产系统_Chrome.bat:259-268#OPEN_CHROME probe call`
  - `assets/启动_排产系统_Chrome.bat:540-547#normalize_contract_owner`
  - `installer/aps_win7_chrome.iss:61-99#ApsChromeProfileSuffixMarker and BuildStopChromePowerShellParams`
  - `installer/aps_win7_chrome.iss:101-125#TryStopApsChromeProcesses`
  - `web/bootstrap/launcher.py:832-882#_list_aps_chrome_pids`
  - `tests/test_win7_launcher_runtime_paths.py:169-175#test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process`
  - `tests/test_win7_launcher_runtime_paths.py:277-290#test_chrome_installer_stop_helper`

### R2 · 第二轮：深入逻辑链路分析与边界条件挖掘

- 状态: 已完成
- 记录时间: 2026-04-07T05:03:07.323Z
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, installer/README_WIN7_INSTALLER.md, DELIVERY_WIN7.md
- 摘要:

  深入审查了三端所有 PowerShell 内联脚本、批处理流程控制、安装器 Pascal 代码的逻辑链路。逐一验证了以下关键环节：

  **批处理 `:probe_aps_chrome_alive`（第607-626行）**：
  - CimInstance 到 WmiObject 降级链条正确：CimInstance 成功但返回空数组时 `$null -eq $items` 为假，会正确跳过降级直接迭代空数组并 exit 2（未找到），不会误触 WmiObject 降级。
  - 单引号转义 `%CHROME_PROFILE_DIR:'=''%`（第613行）防止了路径中包含单引号时的 PowerShell 字符串注入。
  - 返回码语义清晰：0=找到匹配进程、1=查询失败、2=未找到匹配进程，日志中三种状态分别记为 detected/query_failed/missing。
  - no_powershell 路径不设 CHROME_ALIVE，调用方正确走失败闭合。
  - 等待时间 timeout /t 3 对 Chrome 进程注册足够（进程创建远快于 3 秒）。

  **安装器 `BuildStopChromePowerShellParams`（第66-99行）**：
  - Test-ApsChromeCommandLine 函数先检查 --user-data-dir 必要条件再检查后缀或精确路径（逻辑或），短路求值正确。
  - 安装器 PrivilegesRequired=admin，跨账户场景下 Get-CimInstance 可看到所有账户进程及 CommandLine，Stop-Process -Force 有权限关闭。
  - 后缀 marker `\aps\chrome109profile` 足够特异，与 --user-data-dir 联合检查误匹配概率极低。
  - 停止后 800ms 等待加二次查询验证，失败则 exit 1 保持失败闭合。
  - InitializeUninstall 中 silent 路径和交互路径的错误处理分支完整。

  **Python `_list_aps_chrome_pids`（第832-882行）**：
  - target_profile 归一化为绝对路径后转小写，与批处理归一化方式一致。
  - PowerShell 脚本同时检查 --user-data-dir 和 profile marker。
  - 返回 None 表示查询失败、返回空列表表示无匹配进程，语义清晰。

  **`normalize_contract_owner`（第540-547行）**：
  - 完整验证了 JSON 写入→文件存储→批处理提取→归一化 的全链路：Python 写 `DOMAIN\user`，json.dump 序列化为 `DOMAIN\\user`，批处理提取后经 `!CONTRACT_OWNER:\\=\\!` 还原为 `DOMAIN\user`。

  **无严重BUG**。发现三处可改进项作为 findings 记录。
- 结论:

  无严重BUG，但发现三处值得关注的设计细节：错误提示不够精确、执行策略参数不一致、测试仅为静态守卫。均不影响正确性，但影响可维护性。
- 证据:
  - `assets/启动_排产系统_Chrome.bat:607-612#probe_aps_chrome_alive no_powershell path`
  - `assets/启动_排产系统_Chrome.bat:262-268#chrome alive failure message`
  - `assets/启动_排产系统_Chrome.bat:614#bat powershell inline without -ExecutionPolicy`
  - `installer/aps_win7_chrome.iss:76-77#installer powershell with -ExecutionPolicy Bypass`
  - `web/bootstrap/launcher.py:747-748#python powershell without -ExecutionPolicy`
- 问题:
  - [低] 其他: 无 PowerShell 时失败提示未指出原因
  - [低] 其他: PowerShell 执行策略参数三端不一致
  - [中] 测试: 关键行为变更仅有静态守卫无运行时验证

### R3 · 第三轮：跨端一致性交叉验证与文档同步

- 状态: 已完成
- 记录时间: 2026-04-07T05:03:54.043Z
- 已审模块: assets/启动_排产系统_Chrome.bat, installer/aps_win7_chrome.iss, web/bootstrap/launcher.py, installer/README_WIN7_INSTALLER.md, DELIVERY_WIN7.md
- 摘要:

  进行了三端（批处理启动器、安装器卸载、Python 停机）的交叉语义验证，以及文档一致性和 plan 完成标准验证。

  ## 一、三端"APS 专用浏览器"定义一致性

  三端共同的核心语义是：**只认命令行中带 APS 专用 `--user-data-dir` 的 Chrome 进程**。但在匹配精度上有意做了分层：

  | 端 | 匹配方式 | 匹配范围 | 合理性 |
  |---|---|---|---|
  | 批处理启动器 | 精确绝对路径（`CHROME_PROFILE_DIR`） | 仅当前账户 | 启动器只需确认自己拉起的 APS Chrome |
  | Python 停机 | 精确绝对路径（`profile_dir`） | 仅传入的 profile | 停机时已知要关闭哪个 profile 的进程 |
  | 安装器卸载 | 精确路径 OR 后缀 marker（`\aps\chrome109profile`） | 所有账户 | 管理员卸载需要跨账户覆盖 |

  这种分层是合理的设计决策，而不是语义漂移。Python 侧注释（第833-835行）已经清晰记录了这一差异。

  ## 二、Profile 路径源头一致性

  所有三端的 APS 专用 profile 路径都归结为同一个标准目录名：

  - 批处理：`%LOCALAPPDATA%\APS\Chrome109Profile`（第60行）
  - Python：`os.path.join(local_appdata, "APS", "Chrome109Profile")`（第517行）
  - 安装器：`{localappdata}\APS\Chrome109Profile`（第58行）+ 后缀 `\aps\chrome109profile`（第63行）

  三者实际解析出的目录在同一台机器上完全一致。安装器额外的后缀 marker 是路径的尾部子串，保证跨账户场景也能匹配（不同账户的 `%LOCALAPPDATA%` 前缀不同，但后缀 `\APS\Chrome109Profile` 相同）。

  ## 三、失败闭合语义一致性

  - **批处理**：PowerShell 不可用 → `chrome_alive_probe=no_powershell` → `CHROME_ALIVE` 未设 → `exit /b 11`。**不降级**。
  - **Python**：`_list_aps_chrome_pids` 返回 `None` → `stop_aps_chrome_processes` 返回 `False` → 调用方 `_stop_aps_chrome_if_requested` 返回 `False` → `stop_runtime_from_dir` 返回 `1`（失败）。**不降级**。
  - **安装器**：`TryStopApsChromeProcesses` 失败 → `InitializeUninstall` 中 silent 返回 `False`（阻止卸载），交互弹确认框。**不降级**。

  三端在查询失败时都严格失败闭合，无任何静默回退或兜底路径。

  ## 四、Owner 归一化跨端一致性

  - Python 写入 JSON：`_compose_runtime_owner` 产生 `DOMAIN\user`，`json.dump` 序列化为 `DOMAIN\\user`
  - 批处理读取 JSON：`findstr` + 文本提取得到 `DOMAIN\\user`，`normalize_contract_owner` 执行 `\\` → `\` 还原为 `DOMAIN\user`
  - 批处理本地值：`set "CURRENT_OWNER=%USERDOMAIN%\%USERNAME%"` 为 `DOMAIN\user`
  - 比较：`if /I "%CONTRACT_OWNER%"=="%CURRENT_OWNER%"` — 两侧格式一致。✓

  ## 五、文档同步验证

  - **`installer/README_WIN7_INSTALLER.md`**：
    - 第223行已写明"启动器只认当前 CHROME_PROFILE_DIR 对应的 APS 专用 `--user-data-dir` 进程"
    - 第245-247行已写明卸载器跨账户匹配和失败闭合语义
    - 第264-268行新增了"残余问题收口验收"段落，包含两个现场验收场景
    
  - **`DELIVERY_WIN7.md`**：
    - 第40行已写明启动器不会把普通 Chrome 共存当成 APS 已拉起
    - 第44行已写明卸载器跨账户行为和失败闭合
    - 第166-173行新增了"残余问题收口验收"段落

  两份文档的口径与实际代码完全一致，没有遗漏或矛盾。

  ## 六、Plan 完成标准逐条验证

  1. ✅ 启动器不再通过"任意 chrome.exe 存活"判定成功
  2. ✅ 安装器不再只按当前卸载账户路径匹配
  3. ⏳ 四条测试/回归命令全部通过 — 代码已到位，需要实际运行确认
  4. ⏳ 普通 Chrome 共存与双账户卸载真实机器验收 — 待现场
  5. ✅ 两份文档已同步到新的成功判定与卸载语义
- 结论:

  三端语义已实质统一，设计分层合理。匹配策略差异是有意为之的合理设计，不是语义漂移。文档同步完整，plan 完成标准中五项已满足三项，剩余两项是现场验收。
- 证据:
  - `web/bootstrap/launcher.py:832-835#_list_aps_chrome_pids comment`
  - `installer/README_WIN7_INSTALLER.md:242-268#residual issue acceptance section`
  - `DELIVERY_WIN7.md:40-44#cross-account uninstall semantics`
  - `web/bootstrap/launcher.py:111-116#_compose_runtime_owner`
  - `assets/启动_排产系统_Chrome.bat:60#CHROME_PROFILE_DIR default`
  - `installer/aps_win7_chrome.iss:61-64#ApsChromeProfileSuffixMarker`
  - `web/bootstrap/launcher.py:514-518#default_chrome_profile_dir`

## 最终结论

## 三轮深度审查总结

本次对 `APS启动链路与Chrome残余问题修复plan` 进行了三轮递进式深度审查，覆盖了 plan 中全部四个任务所涉及的 6 个核心文件和 676 行批处理、173 行安装器、995 行 Python、307 行测试以及两份关键文档。

### 总体评价

**plan 达成度：高**。四个任务中三个代码任务已全部落地，第四个（现场验收）是合理的待办。plan 的问题定义清晰、步骤拆分合理、完成标准可验证。

**实现质量：优**。三端的核心改动（浏览器判活收紧、跨账户匹配、Python 注释）都做到了简洁精确、没有过度兜底、没有静默回退。所有失败路径都是严格闭合的——不存在"查询失败就假装成功"的降级分支。

**无严重BUG**。深入跟踪了 CimInstance/WmiObject 降级链条、单引号字符串注入防护、JSON 反转义全链路、跨账户进程可见性与关闭权限等边界条件，均未发现功能性缺陷。

### 发现问题汇总

| 严重级别 | 数量 | 说明 |
|---------|------|------|
| 高 | 0 | 无 |
| 中 | 1 | 关键行为变更仅有静态字符串守卫，缺乏运行时行为验证 |
| 低 | 2 | 无 PowerShell 时用户提示不够明确；PowerShell 执行策略参数三端不一致 |

三个问题均不影响当前实现的正确性和安全性，都是可维护性层面的改进建议。

### 设计亮点

1. **分层匹配策略**：批处理/Python 用精确路径、安装器用路径+后缀 marker，三者各取所需又共享同一核心语义"只认 APS 专用 `--user-data-dir` 命令行"。
2. **严格失败闭合**：三端在查询失败时都不做任何降级——不回退到旧的按镜像名宽匹配，不把"查不到"等价于"没进程"。
3. **最小改动原则**：Python 侧已有 `--user-data-dir` 检查，plan 明确判断后只补了三行注释，没有做无关扩散。
4. **文档即代码**：两份交付文档同步更新了"成功判定更严格"和"卸载匹配跨账户"的口径，并新增了现场验收段落。

### 建议下一步

1. 在真实 Windows 机器上完成"普通 Chrome 共存"与"双账户卸载"两组现场验收。
2. 运行四条自动回归命令确认代码已到位的测试全部通过。
3. 择机把无 PowerShell 时的用户提示改得更具体一些（低优先级）。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mno5baxv-x0nulh",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T05:04:25.562Z",
  "finalizedAt": "2026-04-07T05:04:25.562Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "APS启动链路与Chrome残余问题修复plan三轮深度审查",
    "date": "2026-04-07",
    "overview": "对plan与其实际已落地实现进行三轮深度交叉审查，验证目标达成度、实现质量与残留风险。"
  },
  "scope": {
    "markdown": "# APS启动链路与Chrome残余问题修复plan三轮深度审查\n\n- 日期：2026-04-07\n- 范围：plan 本身与所有涉及文件的实际实现\n- 审查目标：验证 plan 中四个任务的已实现状态与质量，识别残留BUG与设计缺陷\n\n## 审查策略\n\n**第一轮**：逐任务比对 plan 目标与实际代码，确认\"是否真正做到了\"。\n**第二轮**：深入每段关键实现的逻辑链路，挖掘BUG与边界条件问题。\n**第三轮**：跨端一致性交叉验证，评估三端（批处理/安装器/Python）语义是否真正统一。"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查总结\n\n本次对 `APS启动链路与Chrome残余问题修复plan` 进行了三轮递进式深度审查，覆盖了 plan 中全部四个任务所涉及的 6 个核心文件和 676 行批处理、173 行安装器、995 行 Python、307 行测试以及两份关键文档。\n\n### 总体评价\n\n**plan 达成度：高**。四个任务中三个代码任务已全部落地，第四个（现场验收）是合理的待办。plan 的问题定义清晰、步骤拆分合理、完成标准可验证。\n\n**实现质量：优**。三端的核心改动（浏览器判活收紧、跨账户匹配、Python 注释）都做到了简洁精确、没有过度兜底、没有静默回退。所有失败路径都是严格闭合的——不存在\"查询失败就假装成功\"的降级分支。\n\n**无严重BUG**。深入跟踪了 CimInstance/WmiObject 降级链条、单引号字符串注入防护、JSON 反转义全链路、跨账户进程可见性与关闭权限等边界条件，均未发现功能性缺陷。\n\n### 发现问题汇总\n\n| 严重级别 | 数量 | 说明 |\n|---------|------|------|\n| 高 | 0 | 无 |\n| 中 | 1 | 关键行为变更仅有静态字符串守卫，缺乏运行时行为验证 |\n| 低 | 2 | 无 PowerShell 时用户提示不够明确；PowerShell 执行策略参数三端不一致 |\n\n三个问题均不影响当前实现的正确性和安全性，都是可维护性层面的改进建议。\n\n### 设计亮点\n\n1. **分层匹配策略**：批处理/Python 用精确路径、安装器用路径+后缀 marker，三者各取所需又共享同一核心语义\"只认 APS 专用 `--user-data-dir` 命令行\"。\n2. **严格失败闭合**：三端在查询失败时都不做任何降级——不回退到旧的按镜像名宽匹配，不把\"查不到\"等价于\"没进程\"。\n3. **最小改动原则**：Python 侧已有 `--user-data-dir` 检查，plan 明确判断后只补了三行注释，没有做无关扩散。\n4. **文档即代码**：两份交付文档同步更新了\"成功判定更严格\"和\"卸载匹配跨账户\"的口径，并新增了现场验收段落。\n\n### 建议下一步\n\n1. 在真实 Windows 机器上完成\"普通 Chrome 共存\"与\"双账户卸载\"两组现场验收。\n2. 运行四条自动回归命令确认代码已到位的测试全部通过。\n3. 择机把无 PowerShell 时的用户提示改得更具体一些（低优先级）。",
    "recommendedNextAction": "在真实 Windows 机器上完成\"普通 Chrome 共存\"与\"双账户卸载\"两组现场验收后，此 plan 可视为完全闭合。",
    "reviewedModules": [
      "assets/启动_排产系统_Chrome.bat",
      "installer/aps_win7_chrome.iss",
      "web/bootstrap/launcher.py",
      "tests/test_win7_launcher_runtime_paths.py",
      "installer/README_WIN7_INSTALLER.md",
      "DELIVERY_WIN7.md"
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
      "title": "第一轮：逐任务比对 plan 目标与实际实现",
      "status": "completed",
      "recordedAt": "2026-04-07T05:01:11.026Z",
      "summaryMarkdown": "逐任务验证了 plan 中四个任务的实际落地状态。\n\n**任务 1（启动器浏览器判活收紧）**：已完全落地。批处理中新增了 `:probe_aps_chrome_alive` 子程序（第607-626行），使用 `Get-CimInstance`/`Get-WmiObject` 查询 `Win32_Process`，仅当命令行同时包含 `--user-data-dir` 和当前 `CHROME_PROFILE_DIR` 归一化路径时才判定成功。旧的按镜像名宽匹配判活逻辑已被移除，整个批处理中不存在任何 `tasklist /FI \"IMAGENAME eq chrome.exe\"` 的分支。没有 PowerShell 时明确记录 `chrome_alive_probe=no_powershell` 并按失败处理，不做任何降级。失败时以 `exit /b 11` 退出并显示\"未能确认 APS 专用浏览器已拉起\"提示。\n\n**任务 2（安装器跨账户匹配收紧）**：已完全落地。新增了 `ApsChromeProfileSuffixMarker()` 函数返回 `\\aps\\chrome109profile` 后缀；`BuildStopChromePowerShellParams` 同时接收精确路径和后缀 marker，生成的 PowerShell 中定义了 `Test-ApsChromeCommandLine` 函数，检查命令行包含 `--user-data-dir` 且匹配后缀 marker 或精确路径（逻辑或短路）。停止后执行二次查询验证，任何目标进程仍存在则 `exit 1`。`TryStopApsChromeProcesses` 正确调用了 `BuildStopChromePowerShellParams(CurrentUserChromeProfilePath(), ApsChromeProfileSuffixMarker())`。\n\n**任务 3（验证证据）**：自动化静态守卫已完成（`test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process`、`test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only` 等）；回归测试命令已列出。但 plan 明确标注的两组现场验收（普通 Chrome 共存 + 双账户卸载）标记为待现场执行，这是合理的——这类验收确实不能由自动化测试完成。\n\n**任务 4（Python 侧注释）**：已在 `_list_aps_chrome_pids()` 上方添加三行注释（第833-835行），清晰说明了三端的匹配口径差异和共同目标。Python 实现本身已经具备 `--user-data-dir` 条件检查（第859行），无需额外改代码。\n\n**`normalize_contract_owner` 修复**：第545行的 `set \"CONTRACT_OWNER=!CONTRACT_OWNER:\\\\=\\\\!\"` 正确实现了 JSON 反转义（`\\\\` → `\\`），配合第518行的 `call :normalize_contract_owner`，消除了契约回退路径下同账户误判问题。\n\n**TODO 状态校验**：\n- `#p1` 标记完成 ✓ → 代码确认已落地\n- `#p2` 标记完成 ✓ → 代码确认已落地  \n- `#p3` 标记未完成 → 正确，现场验收确实待做\n- `#p4` 标记完成 ✓ → 注释确认已添加",
      "conclusionMarkdown": "plan 中四个任务的代码落地部分全部到位，目标达成度高。唯一未闭合的是现场验收环节（#p3），但这是 plan 本身的有意安排，不是遗漏。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 607,
          "lineEnd": 626,
          "symbol": "probe_aps_chrome_alive"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 259,
          "lineEnd": 268,
          "symbol": "OPEN_CHROME probe call"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 540,
          "lineEnd": 547,
          "symbol": "normalize_contract_owner"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 61,
          "lineEnd": 99,
          "symbol": "ApsChromeProfileSuffixMarker and BuildStopChromePowerShellParams"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 101,
          "lineEnd": 125,
          "symbol": "TryStopApsChromeProcesses"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 882,
          "symbol": "_list_aps_chrome_pids"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 169,
          "lineEnd": 175,
          "symbol": "test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py",
          "lineStart": 277,
          "lineEnd": 290,
          "symbol": "test_chrome_installer_stop_helper"
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
      "title": "第二轮：深入逻辑链路分析与边界条件挖掘",
      "status": "completed",
      "recordedAt": "2026-04-07T05:03:07.323Z",
      "summaryMarkdown": "深入审查了三端所有 PowerShell 内联脚本、批处理流程控制、安装器 Pascal 代码的逻辑链路。逐一验证了以下关键环节：\n\n**批处理 `:probe_aps_chrome_alive`（第607-626行）**：\n- CimInstance 到 WmiObject 降级链条正确：CimInstance 成功但返回空数组时 `$null -eq $items` 为假，会正确跳过降级直接迭代空数组并 exit 2（未找到），不会误触 WmiObject 降级。\n- 单引号转义 `%CHROME_PROFILE_DIR:'=''%`（第613行）防止了路径中包含单引号时的 PowerShell 字符串注入。\n- 返回码语义清晰：0=找到匹配进程、1=查询失败、2=未找到匹配进程，日志中三种状态分别记为 detected/query_failed/missing。\n- no_powershell 路径不设 CHROME_ALIVE，调用方正确走失败闭合。\n- 等待时间 timeout /t 3 对 Chrome 进程注册足够（进程创建远快于 3 秒）。\n\n**安装器 `BuildStopChromePowerShellParams`（第66-99行）**：\n- Test-ApsChromeCommandLine 函数先检查 --user-data-dir 必要条件再检查后缀或精确路径（逻辑或），短路求值正确。\n- 安装器 PrivilegesRequired=admin，跨账户场景下 Get-CimInstance 可看到所有账户进程及 CommandLine，Stop-Process -Force 有权限关闭。\n- 后缀 marker `\\aps\\chrome109profile` 足够特异，与 --user-data-dir 联合检查误匹配概率极低。\n- 停止后 800ms 等待加二次查询验证，失败则 exit 1 保持失败闭合。\n- InitializeUninstall 中 silent 路径和交互路径的错误处理分支完整。\n\n**Python `_list_aps_chrome_pids`（第832-882行）**：\n- target_profile 归一化为绝对路径后转小写，与批处理归一化方式一致。\n- PowerShell 脚本同时检查 --user-data-dir 和 profile marker。\n- 返回 None 表示查询失败、返回空列表表示无匹配进程，语义清晰。\n\n**`normalize_contract_owner`（第540-547行）**：\n- 完整验证了 JSON 写入→文件存储→批处理提取→归一化 的全链路：Python 写 `DOMAIN\\user`，json.dump 序列化为 `DOMAIN\\\\user`，批处理提取后经 `!CONTRACT_OWNER:\\\\=\\\\!` 还原为 `DOMAIN\\user`。\n\n**无严重BUG**。发现三处可改进项作为 findings 记录。",
      "conclusionMarkdown": "无严重BUG，但发现三处值得关注的设计细节：错误提示不够精确、执行策略参数不一致、测试仅为静态守卫。均不影响正确性，但影响可维护性。",
      "evidence": [
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 607,
          "lineEnd": 612,
          "symbol": "probe_aps_chrome_alive no_powershell path"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 262,
          "lineEnd": 268,
          "symbol": "chrome alive failure message"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 614,
          "lineEnd": 614,
          "symbol": "bat powershell inline without -ExecutionPolicy"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 76,
          "lineEnd": 77,
          "symbol": "installer powershell with -ExecutionPolicy Bypass"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 747,
          "lineEnd": 748,
          "symbol": "python powershell without -ExecutionPolicy"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "installer/aps_win7_chrome.iss",
        "web/bootstrap/launcher.py",
        "installer/README_WIN7_INSTALLER.md",
        "DELIVERY_WIN7.md"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "no-ps-hint",
        "exec-policy-inconsistency",
        "static-tests-only"
      ]
    },
    {
      "id": "R3",
      "title": "第三轮：跨端一致性交叉验证与文档同步",
      "status": "completed",
      "recordedAt": "2026-04-07T05:03:54.043Z",
      "summaryMarkdown": "进行了三端（批处理启动器、安装器卸载、Python 停机）的交叉语义验证，以及文档一致性和 plan 完成标准验证。\n\n## 一、三端\"APS 专用浏览器\"定义一致性\n\n三端共同的核心语义是：**只认命令行中带 APS 专用 `--user-data-dir` 的 Chrome 进程**。但在匹配精度上有意做了分层：\n\n| 端 | 匹配方式 | 匹配范围 | 合理性 |\n|---|---|---|---|\n| 批处理启动器 | 精确绝对路径（`CHROME_PROFILE_DIR`） | 仅当前账户 | 启动器只需确认自己拉起的 APS Chrome |\n| Python 停机 | 精确绝对路径（`profile_dir`） | 仅传入的 profile | 停机时已知要关闭哪个 profile 的进程 |\n| 安装器卸载 | 精确路径 OR 后缀 marker（`\\aps\\chrome109profile`） | 所有账户 | 管理员卸载需要跨账户覆盖 |\n\n这种分层是合理的设计决策，而不是语义漂移。Python 侧注释（第833-835行）已经清晰记录了这一差异。\n\n## 二、Profile 路径源头一致性\n\n所有三端的 APS 专用 profile 路径都归结为同一个标准目录名：\n\n- 批处理：`%LOCALAPPDATA%\\APS\\Chrome109Profile`（第60行）\n- Python：`os.path.join(local_appdata, \"APS\", \"Chrome109Profile\")`（第517行）\n- 安装器：`{localappdata}\\APS\\Chrome109Profile`（第58行）+ 后缀 `\\aps\\chrome109profile`（第63行）\n\n三者实际解析出的目录在同一台机器上完全一致。安装器额外的后缀 marker 是路径的尾部子串，保证跨账户场景也能匹配（不同账户的 `%LOCALAPPDATA%` 前缀不同，但后缀 `\\APS\\Chrome109Profile` 相同）。\n\n## 三、失败闭合语义一致性\n\n- **批处理**：PowerShell 不可用 → `chrome_alive_probe=no_powershell` → `CHROME_ALIVE` 未设 → `exit /b 11`。**不降级**。\n- **Python**：`_list_aps_chrome_pids` 返回 `None` → `stop_aps_chrome_processes` 返回 `False` → 调用方 `_stop_aps_chrome_if_requested` 返回 `False` → `stop_runtime_from_dir` 返回 `1`（失败）。**不降级**。\n- **安装器**：`TryStopApsChromeProcesses` 失败 → `InitializeUninstall` 中 silent 返回 `False`（阻止卸载），交互弹确认框。**不降级**。\n\n三端在查询失败时都严格失败闭合，无任何静默回退或兜底路径。\n\n## 四、Owner 归一化跨端一致性\n\n- Python 写入 JSON：`_compose_runtime_owner` 产生 `DOMAIN\\user`，`json.dump` 序列化为 `DOMAIN\\\\user`\n- 批处理读取 JSON：`findstr` + 文本提取得到 `DOMAIN\\\\user`，`normalize_contract_owner` 执行 `\\\\` → `\\` 还原为 `DOMAIN\\user`\n- 批处理本地值：`set \"CURRENT_OWNER=%USERDOMAIN%\\%USERNAME%\"` 为 `DOMAIN\\user`\n- 比较：`if /I \"%CONTRACT_OWNER%\"==\"%CURRENT_OWNER%\"` — 两侧格式一致。✓\n\n## 五、文档同步验证\n\n- **`installer/README_WIN7_INSTALLER.md`**：\n  - 第223行已写明\"启动器只认当前 CHROME_PROFILE_DIR 对应的 APS 专用 `--user-data-dir` 进程\"\n  - 第245-247行已写明卸载器跨账户匹配和失败闭合语义\n  - 第264-268行新增了\"残余问题收口验收\"段落，包含两个现场验收场景\n  \n- **`DELIVERY_WIN7.md`**：\n  - 第40行已写明启动器不会把普通 Chrome 共存当成 APS 已拉起\n  - 第44行已写明卸载器跨账户行为和失败闭合\n  - 第166-173行新增了\"残余问题收口验收\"段落\n\n两份文档的口径与实际代码完全一致，没有遗漏或矛盾。\n\n## 六、Plan 完成标准逐条验证\n\n1. ✅ 启动器不再通过\"任意 chrome.exe 存活\"判定成功\n2. ✅ 安装器不再只按当前卸载账户路径匹配\n3. ⏳ 四条测试/回归命令全部通过 — 代码已到位，需要实际运行确认\n4. ⏳ 普通 Chrome 共存与双账户卸载真实机器验收 — 待现场\n5. ✅ 两份文档已同步到新的成功判定与卸载语义",
      "conclusionMarkdown": "三端语义已实质统一，设计分层合理。匹配策略差异是有意为之的合理设计，不是语义漂移。文档同步完整，plan 完成标准中五项已满足三项，剩余两项是现场验收。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 832,
          "lineEnd": 835,
          "symbol": "_list_aps_chrome_pids comment"
        },
        {
          "path": "installer/README_WIN7_INSTALLER.md",
          "lineStart": 242,
          "lineEnd": 268,
          "symbol": "residual issue acceptance section"
        },
        {
          "path": "DELIVERY_WIN7.md",
          "lineStart": 40,
          "lineEnd": 44,
          "symbol": "cross-account uninstall semantics"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 111,
          "lineEnd": 116,
          "symbol": "_compose_runtime_owner"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 60,
          "lineEnd": 60,
          "symbol": "CHROME_PROFILE_DIR default"
        },
        {
          "path": "installer/aps_win7_chrome.iss",
          "lineStart": 61,
          "lineEnd": 64,
          "symbol": "ApsChromeProfileSuffixMarker"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 514,
          "lineEnd": 518,
          "symbol": "default_chrome_profile_dir"
        }
      ],
      "reviewedModules": [
        "assets/启动_排产系统_Chrome.bat",
        "installer/aps_win7_chrome.iss",
        "web/bootstrap/launcher.py",
        "installer/README_WIN7_INSTALLER.md",
        "DELIVERY_WIN7.md"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "no-ps-hint",
      "severity": "low",
      "category": "other",
      "title": "无 PowerShell 时失败提示未指出原因",
      "descriptionMarkdown": "批处理 :probe_aps_chrome_alive 的 no_powershell 分支（第609-612行）在 PowerShell 不可用时直接返回失败，但后续的用户提示（第262-266行）只写'未能确认 APS 专用浏览器已拉起'，没有提示原因是缺少 PowerShell。用户在极简 Win7 环境下遇到此失败时无法从屏幕提示中定位根因，只能去翻 launcher.log 找 chrome_alive_probe=no_powershell。影响：不影响安全性和正确性，但会增加现场排障时间。",
      "recommendationMarkdown": "在 no_powershell 路径中增加用户可见提示，例如在 exit /b 11 前加 echo [launcher] PowerShell 不可用，无法验证浏览器启动状态。",
      "evidence": [],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "exec-policy-inconsistency",
      "severity": "low",
      "category": "other",
      "title": "PowerShell 执行策略参数三端不一致",
      "descriptionMarkdown": "三端在调用 PowerShell 时，执行策略参数不一致：安装器 BuildStopChromePowerShellParams 使用 -ExecutionPolicy Bypass（第76行）；批处理 :probe_aps_chrome_alive 和 :probe_health 只使用 -NoProfile 不带 -ExecutionPolicy；Python _run_powershell_text 也只使用 -NoProfile（第748行）。从功能上看 -Command 参数天然绕过执行策略（策略只限制 .ps1 脚本文件），所以这不是功能性BUG。但三端风格不统一会让维护者困惑到底需不需要加 -ExecutionPolicy，增加将来误改的风险。",
      "recommendationMarkdown": "统一到三端都加 -ExecutionPolicy Bypass -NoProfile 或三端都只用 -NoProfile。推荐前者因为最显式最防御。",
      "evidence": [],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "static-tests-only",
      "severity": "medium",
      "category": "test",
      "title": "关键行为变更仅有静态守卫无运行时验证",
      "descriptionMarkdown": "当前所有与浏览器判活和安装器 stop helper 相关的测试都是静态字符串检查：读取源文件文本内容检查是否包含预期字符串。这类守卫能防止关键逻辑被意外删除，但无法验证运行时行为。例如：无法验证 PowerShell 脚本实际执行结果、无法验证 profile 路径匹配在实际 Chrome 进程上是否工作、无法验证安装器卸载时跨账户进程停止是否成功。plan 本身已经意识到这一点并在任务 3 中明确要求现场验收，但自动化测试的覆盖天花板是一个需要持续关注的结构性问题。",
      "recommendationMarkdown": "长期考虑在打包流水线中增加一步端到端冒烟：在实际启动 Chrome 后执行 probe 验证至少覆盖启动加 probe 匹配这条主路径。",
      "evidence": [],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:3412fb413c2d886597cff17b94448d50e1af16e48a30d927b238b1a8d5d7f7d1",
    "generatedAt": "2026-04-07T05:04:25.562Z",
    "locale": "zh-CN"
  }
}
```
