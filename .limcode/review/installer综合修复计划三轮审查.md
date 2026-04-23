# installer 综合修复计划三轮审查
- 日期: 2026-04-03
- 概述: 针对 .limcode/plans/installer-目录综合修复计划.plan.md 进行三轮计划审查，并把不明确项落成可执行测试脚本。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# installer 综合修复计划三轮审查

- 日期：2026-04-03
- 范围：`.limcode/plans/installer-目录综合修复计划.plan.md` 及其直接涉及的安装器/启动器/验证脚本
- 目标：执行三轮计划审查，识别计划本身的阶段错位、单活约束冲突、环境假设缺口，并把不明确项转化为可执行测试脚本

## 审查策略
1. 第一轮：检查计划结构、优先级、证据链是否完整。
2. 第二轮：把计划动作逐条映射回当前实现，确认是否可落地。
3. 第三轮：检查环境假设与测试闭环，把不明确项沉淀为脚本。

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/installer-目录综合修复计划.plan.md, installer/aps_win7.iss, installer/aps_win7_legacy.iss, assets/启动_排产系统_Chrome.bat, web/routes/system_health.py, web/bootstrap/launcher.py, tests/verify_installer_vendor_dir.py, tests/verify_installer_wmic_availability.bat, tests/verify_installer_start_errorlevel.bat, tests/verify_installer_powershell_json_support.bat, build_win7_onedir.bat
- 当前进度: 已记录 3 个里程碑；最新：round3-tests-and-env
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 2 / 中 1 / 低 0
- 最新结论: 已完成对 installer 综合修复计划的三轮审查。结论不是“整份计划不可用”，而是“在进入实现前必须先修两处高风险表述，并补上一处环境门禁”。具体来说：P0-1 不能继续写成当前调用点下可直接“中止安装”；P0-3 不能继续写成“健康检查通过即无锁复用”；M6 不能在没有目标机 PowerShell/JSON 证据的前提下直接删除正则回退。与此同时，T1/T2/T3/T4 已把 vendor、WMIC、start 返回码、PowerShell JSON 能力这些不明确项转成了可执行脚本，其中 T2 已在当前机器直接复现 WMIC 缺失，T3 已确认 start 返回码检查不是纯死代码但价值很低，T4 已成为 M6 的必要门禁。
- 下一步建议: 先把计划重写为：① M1 明确“前移迁移阶段”或“后置失败可见”二选一；② M4 改成“锁→运行时契约→失败闭合”的三段式；③ 阶段11 前强制执行 T4，再决定是否删除正则回退。完成这三点后，再进入实际修复。
- 总体结论: 需要后续跟进

## 评审发现

### M1 失败闭合阶段错位

- ID: plan-m1-phase-mismatch
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round2-code-mapping
- 说明:

  计划把“迁移失败即中止安装”写成当前实现可直接落地的改法，但现有 `MigrateLegacyDataIfNeeded` 实际在 `CurStepChanged(ssPostInstall)` 执行。也就是说，调用点已经晚于 `PrepareToInstall`。如果不先调整迁移发生阶段，计划里的“设置 PrepareToInstall 的 Result 中止安装”就无法生效。继续按原表述实施，结果大概率只是把 `MigrationNote` 改得更详细，而不是得到真正的失败闭合。
- 建议:

  先在计划里明确二选一：A）把迁移动作前移到真正可以失败中止的安装前阶段；B）保留后置迁移，但把目标改成“失败可见 + 半成品清理 + 明确提示”，不要继续写成“中止安装”。
- 证据:
  - `.limcode/plans/installer-目录综合修复计划.plan.md:66-85`
  - `installer/aps_win7.iss:470-515#MigrateLegacyDataIfNeeded`
  - `installer/aps_win7.iss:681-699#CurStepChanged`
  - `installer/aps_win7_legacy.iss:467-512#MigrateLegacyDataIfNeeded`
  - `installer/aps_win7_legacy.iss:678-694#CurStepChanged`
  - `.limcode/plans/installer-目录综合修复计划.plan.md`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `assets/启动_排产系统_Chrome.bat`
  - `web/routes/system_health.py`
  - `web/bootstrap/launcher.py`

### M4 无锁复用缺少 owner 证明

- ID: plan-m4-owner-gap
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round2-code-mapping
- 说明:

  计划建议“健康检查通过但锁文件缺失时仍复用实例”，这个修法虽然能避免新开冲突实例，但会削弱单活用户约束。原因是 `/system/health` 只证明服务身份与状态，不包含 owner；如果锁文件丢失，而后台实例属于别的账户，按计划直接复用就会把第二个账户接入现有实例。现有运行时契约 `aps_runtime.json` 已经提供 owner/pid/contract_version，可作为更安全的回退来源。
- 建议:

  把 P0-3 改写为“三段式”：先看锁；锁缺失时读取 `aps_runtime.json` 中的 owner/pid 做回退判断；若仍无法证明归属，则失败闭合并提示用户，而不是无条件复用。
- 证据:
  - `.limcode/plans/installer-目录综合修复计划.plan.md:97-117`
  - `assets/启动_排产系统_Chrome.bat:241-297#try_reuse_existing`
  - `web/routes/system_health.py:15-27#health`
  - `web/bootstrap/launcher.py:379-439#acquire_runtime_lock`
  - `web/bootstrap/launcher.py:524-566#_runtime_contract_payload`
  - `.limcode/plans/installer-目录综合修复计划.plan.md`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `assets/启动_排产系统_Chrome.bat`
  - `web/routes/system_health.py`
  - `web/bootstrap/launcher.py`

### M6 缺少目标机 PowerShell JSON 门禁

- ID: plan-m6-target-gate
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: round3-tests-and-env
- 说明:

  计划当前把 M6 写成直接删除健康检查正则回退，但当前仓库并没有在执行顺序里要求先验证目标机是否具备 `ConvertFrom-Json`。第三轮已新增 `tests/verify_installer_powershell_json_support.bat`，当前开发机通过不代表实际 Win7 目标机通过。如果不把 T4 作为门禁写进计划，M6 仍然是基于环境假设而不是基于证据推进。
- 建议:

  在计划里新增 T4 门禁：只有目标机执行 `tests/verify_installer_powershell_json_support.bat` 成功后，阶段11 才允许删除正则回退；否则应保留回退，或把该分支改成显式失败而不是直接删掉。
- 证据:
  - `.limcode/plans/installer-目录综合修复计划.plan.md:168-169`
  - `tests/verify_installer_powershell_json_support.bat:17-73`
  - `assets/启动_排产系统_Chrome.bat:299-313#probe_health`
  - `tests/verify_installer_vendor_dir.py`
  - `tests/verify_installer_wmic_availability.bat`
  - `tests/verify_installer_start_errorlevel.bat`
  - `tests/verify_installer_powershell_json_support.bat`
  - `.limcode/plans/installer-目录综合修复计划.plan.md`
  - `build_win7_onedir.bat`
  - `assets/启动_排产系统_Chrome.bat`

## 评审里程碑

### round1-structure · 第一轮：计划结构、优先级与证据链检查

- 状态: 已完成
- 记录时间: 2026-04-03T16:10:03.828Z
- 已审模块: .limcode/plans/installer-目录综合修复计划.plan.md
- 摘要:

  已审阅 `.limcode/plans/installer-目录综合修复计划.plan.md` 的任务拆分、优先级与测试前置项。总体上，计划已经把高风险项集中在 M1/M3/M4，且已把 T1/T2/T3 作为前置验证落地，这一点是正确的。当前计划也已经根据 T1/T3 的最新结果把 M11 降到 P2，并把 M8 从“删除”调整为“保留但注明局限性”，说明计划具备自我修正能力。

  本轮同时确认两个需要进入下一轮深查的点：
  1. P0-1 对“迁移失败即中止安装”的表述，需要回到现有 Inno 执行阶段核对，确认是不是能在当前调用点真正失败闭合。
  2. P0-3 对“健康检查通过但无锁仍复用”的描述，需要回到单活约束与 owner 证明机制核对，避免把“防止双开”误写成“允许跨账户复用”。
- 结论:

  第一轮结论：计划总体排序是对的，但 P0-1 与 P0-3 仍有实现级语义风险，不能直接进入编码，需要第二轮按当前代码调用点逐条映射。
- 证据:
  - `.limcode/plans/installer-目录综合修复计划.plan.md:1-19`
  - `.limcode/plans/installer-目录综合修复计划.plan.md:42-60`
  - `.limcode/plans/installer-目录综合修复计划.plan.md:64-119`
  - `.limcode/plans/installer-目录综合修复计划.plan.md`
- 下一步建议:

  第二轮把 P0-1/P0-3 映射回当前安装器与启动器实现，确认计划表述是否需要改写。

### round2-code-mapping · 第二轮：计划动作与当前实现逐条映射

- 状态: 已完成
- 记录时间: 2026-04-03T16:10:32.179Z
- 已审模块: .limcode/plans/installer-目录综合修复计划.plan.md, installer/aps_win7.iss, installer/aps_win7_legacy.iss, assets/启动_排产系统_Chrome.bat, web/routes/system_health.py, web/bootstrap/launcher.py
- 摘要:

  已把 P0/P1 关键动作逐条映射回当前实现。结果表明，计划里有两处需要先改写再实施：

  1. **P0-1 的失败闭合路径写错阶段了。** 计划希望在旧数据迁移失败时“中止安装”，但当前 `MigrateLegacyDataIfNeeded` 并不在 `PrepareToInstall` 内，而是在 `CurStepChanged(ssPostInstall)` 里执行。也就是说，现有调用点已经处于安装后阶段；此时单纯设置 `MigrationNote`，或者试图通过 `PrepareToInstall` 的返回值中止，都无法达到计划描述的效果。
  2. **P0-3 的“健康检查通过但无锁仍复用”会冲撞单活用户约束。** 当前 `/system/health` 只证明“这是 APS 且状态正常”，并不返回 owner；而批处理启动器当前也只看锁文件里的 owner。若锁文件缺失但后台实例属于别的账户，按计划直接复用，就会把“避免冲突新实例”变成“允许第二个账户接入现有单活实例”。

  同时也确认到，现有运行时契约 `aps_runtime.json` 本身已经携带 `owner`、`pid`、`contract_version` 等信息，所以 P0-3 更合理的修复方向不是“无锁就直接复用”，而是“无锁时转而读取运行时契约；能证明 owner 再决定复用/阻止，证明不了就失败闭合”。
- 结论:

  第二轮结论：P0-1 与 P0-3 需要先修计划再动代码。P0-1 应先决定是否前移迁移阶段；P0-3 应改成“契约级 owner 回退或失败闭合”，不能写成“健康通过即无锁复用”。
- 证据:
  - `.limcode/plans/installer-目录综合修复计划.plan.md:66-85`
  - `installer/aps_win7.iss:470-515#MigrateLegacyDataIfNeeded`
  - `installer/aps_win7.iss:681-699#CurStepChanged`
  - `installer/aps_win7_legacy.iss:467-512#MigrateLegacyDataIfNeeded`
  - `installer/aps_win7_legacy.iss:678-694#CurStepChanged`
  - `.limcode/plans/installer-目录综合修复计划.plan.md:97-117`
  - `assets/启动_排产系统_Chrome.bat:241-297#try_reuse_existing`
  - `web/routes/system_health.py:15-27#health`
  - `web/bootstrap/launcher.py:379-439#acquire_runtime_lock`
  - `web/bootstrap/launcher.py:524-566#_runtime_contract_payload`
  - `.limcode/plans/installer-目录综合修复计划.plan.md`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `assets/启动_排产系统_Chrome.bat`
  - `web/routes/system_health.py`
  - `web/bootstrap/launcher.py`
- 下一步建议:

  先修正计划表述，再进入实际编码；否则会把阶段错位和单活语义问题直接写进实现。
- 问题:
  - [高] 其他: M1 失败闭合阶段错位
  - [高] 其他: M4 无锁复用缺少 owner 证明

### round3-tests-and-env · 第三轮：不明确项脚本化与环境门禁验证

- 状态: 已完成
- 记录时间: 2026-04-03T16:10:59.790Z
- 已审模块: tests/verify_installer_vendor_dir.py, tests/verify_installer_wmic_availability.bat, tests/verify_installer_start_errorlevel.bat, tests/verify_installer_powershell_json_support.bat, build_win7_onedir.bat, assets/启动_排产系统_Chrome.bat, .limcode/plans/installer-目录综合修复计划.plan.md
- 摘要:

  已把计划里的不明确项转成可执行脚本，并在当前机器完成一轮验证：

  1. `tests/verify_installer_vendor_dir.py`：确认当前仓库中 `vendor/` 实际存在，因此 M11 不再是“当前仓库必现”的问题；但 `build_win7_onedir.bat` 仍无条件引用 `vendor`，换机仍可能失败，因此保留为 P2 加固项。
  2. `tests/verify_installer_wmic_availability.bat`：当前 Win10 环境已经直接复现 `wmic` 缺失，说明 M3 不是 Win7 特例，而是新系统上也会真实触发的高优先级兼容风险。
  3. `tests/verify_installer_start_errorlevel.bat`：已修正脚本并重新执行，结果是“无效路径返回 9059、有效命令返回 0”。这说明 M8 不应再写成“死代码删除”，而应写成“保留但明确其只覆盖极端竞态，价值很低”。
  4. `tests/verify_installer_powershell_json_support.bat`：这是本轮新增脚本。当前开发机具备 PowerShell + ConvertFrom-Json + 最小 JSON 解析能力，但这**不能外推到实际 Win7 目标机**。

  因此，第三轮最重要的新结论不是“马上删除正则回退”，而是“先在目标机跑 T4，再决定 M6 是否能做分支收敛”。
- 结论:

  第三轮结论：T1/T2/T3 已把 M11/M3/M8 的不确定性压实；新增 T4 后，M6 也从主观假设变成了可验证门禁。计划若要继续推进，应把“先跑 T4 再做 M6”写进执行顺序。
- 证据:
  - `tests/verify_installer_vendor_dir.py:19-103#main`
  - `build_win7_onedir.bat:23-35`
  - `tests/verify_installer_wmic_availability.bat:17-90`
  - `tests/verify_installer_start_errorlevel.bat:11-55`
  - `tests/verify_installer_powershell_json_support.bat:17-73`
  - `assets/启动_排产系统_Chrome.bat:299-313#probe_health`
  - `.limcode/plans/installer-目录综合修复计划.plan.md:147-172`
  - `tests/verify_installer_vendor_dir.py`
  - `tests/verify_installer_wmic_availability.bat`
  - `tests/verify_installer_start_errorlevel.bat`
  - `tests/verify_installer_powershell_json_support.bat`
  - `.limcode/plans/installer-目录综合修复计划.plan.md`
  - `build_win7_onedir.bat`
  - `assets/启动_排产系统_Chrome.bat`
- 下一步建议:

  把 T4 加入计划前置门禁，并按第二轮结论重写 P0-1/P0-3 后，再开始实际修复。
- 问题:
  - [中] 测试: M6 缺少目标机 PowerShell JSON 门禁

## 最终结论

已完成对 installer 综合修复计划的三轮审查。结论不是“整份计划不可用”，而是“在进入实现前必须先修两处高风险表述，并补上一处环境门禁”。具体来说：P0-1 不能继续写成当前调用点下可直接“中止安装”；P0-3 不能继续写成“健康检查通过即无锁复用”；M6 不能在没有目标机 PowerShell/JSON 证据的前提下直接删除正则回退。与此同时，T1/T2/T3/T4 已把 vendor、WMIC、start 返回码、PowerShell JSON 能力这些不明确项转成了可执行脚本，其中 T2 已在当前机器直接复现 WMIC 缺失，T3 已确认 start 返回码检查不是纯死代码但价值很低，T4 已成为 M6 的必要门禁。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnj3mr57-s89d5l",
  "createdAt": "2026-04-03T00:00:00.000Z",
  "updatedAt": "2026-04-03T16:11:12.981Z",
  "finalizedAt": "2026-04-03T16:11:12.981Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "installer 综合修复计划三轮审查",
    "date": "2026-04-03",
    "overview": "针对 .limcode/plans/installer-目录综合修复计划.plan.md 进行三轮计划审查，并把不明确项落成可执行测试脚本。"
  },
  "scope": {
    "markdown": "# installer 综合修复计划三轮审查\n\n- 日期：2026-04-03\n- 范围：`.limcode/plans/installer-目录综合修复计划.plan.md` 及其直接涉及的安装器/启动器/验证脚本\n- 目标：执行三轮计划审查，识别计划本身的阶段错位、单活约束冲突、环境假设缺口，并把不明确项转化为可执行测试脚本\n\n## 审查策略\n1. 第一轮：检查计划结构、优先级、证据链是否完整。\n2. 第二轮：把计划动作逐条映射回当前实现，确认是否可落地。\n3. 第三轮：检查环境假设与测试闭环，把不明确项沉淀为脚本。"
  },
  "summary": {
    "latestConclusion": "已完成对 installer 综合修复计划的三轮审查。结论不是“整份计划不可用”，而是“在进入实现前必须先修两处高风险表述，并补上一处环境门禁”。具体来说：P0-1 不能继续写成当前调用点下可直接“中止安装”；P0-3 不能继续写成“健康检查通过即无锁复用”；M6 不能在没有目标机 PowerShell/JSON 证据的前提下直接删除正则回退。与此同时，T1/T2/T3/T4 已把 vendor、WMIC、start 返回码、PowerShell JSON 能力这些不明确项转成了可执行脚本，其中 T2 已在当前机器直接复现 WMIC 缺失，T3 已确认 start 返回码检查不是纯死代码但价值很低，T4 已成为 M6 的必要门禁。",
    "recommendedNextAction": "先把计划重写为：① M1 明确“前移迁移阶段”或“后置失败可见”二选一；② M4 改成“锁→运行时契约→失败闭合”的三段式；③ 阶段11 前强制执行 T4，再决定是否删除正则回退。完成这三点后，再进入实际修复。",
    "reviewedModules": [
      ".limcode/plans/installer-目录综合修复计划.plan.md",
      "installer/aps_win7.iss",
      "installer/aps_win7_legacy.iss",
      "assets/启动_排产系统_Chrome.bat",
      "web/routes/system_health.py",
      "web/bootstrap/launcher.py",
      "tests/verify_installer_vendor_dir.py",
      "tests/verify_installer_wmic_availability.bat",
      "tests/verify_installer_start_errorlevel.bat",
      "tests/verify_installer_powershell_json_support.bat",
      "build_win7_onedir.bat"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 2,
      "medium": 1,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "round1-structure",
      "title": "第一轮：计划结构、优先级与证据链检查",
      "status": "completed",
      "recordedAt": "2026-04-03T16:10:03.828Z",
      "summaryMarkdown": "已审阅 `.limcode/plans/installer-目录综合修复计划.plan.md` 的任务拆分、优先级与测试前置项。总体上，计划已经把高风险项集中在 M1/M3/M4，且已把 T1/T2/T3 作为前置验证落地，这一点是正确的。当前计划也已经根据 T1/T3 的最新结果把 M11 降到 P2，并把 M8 从“删除”调整为“保留但注明局限性”，说明计划具备自我修正能力。\n\n本轮同时确认两个需要进入下一轮深查的点：\n1. P0-1 对“迁移失败即中止安装”的表述，需要回到现有 Inno 执行阶段核对，确认是不是能在当前调用点真正失败闭合。\n2. P0-3 对“健康检查通过但无锁仍复用”的描述，需要回到单活约束与 owner 证明机制核对，避免把“防止双开”误写成“允许跨账户复用”。",
      "conclusionMarkdown": "第一轮结论：计划总体排序是对的，但 P0-1 与 P0-3 仍有实现级语义风险，不能直接进入编码，需要第二轮按当前代码调用点逐条映射。",
      "evidence": [
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 1,
          "lineEnd": 19,
          "excerptHash": "sha256:plan-header-todos"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 42,
          "lineEnd": 60,
          "excerptHash": "sha256:plan-test-results"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 64,
          "lineEnd": 119,
          "excerptHash": "sha256:plan-p0-items"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/installer-目录综合修复计划.plan.md"
      ],
      "recommendedNextAction": "第二轮把 P0-1/P0-3 映射回当前安装器与启动器实现，确认计划表述是否需要改写。",
      "findingIds": []
    },
    {
      "id": "round2-code-mapping",
      "title": "第二轮：计划动作与当前实现逐条映射",
      "status": "completed",
      "recordedAt": "2026-04-03T16:10:32.179Z",
      "summaryMarkdown": "已把 P0/P1 关键动作逐条映射回当前实现。结果表明，计划里有两处需要先改写再实施：\n\n1. **P0-1 的失败闭合路径写错阶段了。** 计划希望在旧数据迁移失败时“中止安装”，但当前 `MigrateLegacyDataIfNeeded` 并不在 `PrepareToInstall` 内，而是在 `CurStepChanged(ssPostInstall)` 里执行。也就是说，现有调用点已经处于安装后阶段；此时单纯设置 `MigrationNote`，或者试图通过 `PrepareToInstall` 的返回值中止，都无法达到计划描述的效果。\n2. **P0-3 的“健康检查通过但无锁仍复用”会冲撞单活用户约束。** 当前 `/system/health` 只证明“这是 APS 且状态正常”，并不返回 owner；而批处理启动器当前也只看锁文件里的 owner。若锁文件缺失但后台实例属于别的账户，按计划直接复用，就会把“避免冲突新实例”变成“允许第二个账户接入现有单活实例”。\n\n同时也确认到，现有运行时契约 `aps_runtime.json` 本身已经携带 `owner`、`pid`、`contract_version` 等信息，所以 P0-3 更合理的修复方向不是“无锁就直接复用”，而是“无锁时转而读取运行时契约；能证明 owner 再决定复用/阻止，证明不了就失败闭合”。",
      "conclusionMarkdown": "第二轮结论：P0-1 与 P0-3 需要先修计划再动代码。P0-1 应先决定是否前移迁移阶段；P0-3 应改成“契约级 owner 回退或失败闭合”，不能写成“健康通过即无锁复用”。",
      "evidence": [
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 66,
          "lineEnd": 85,
          "excerptHash": "sha256:plan-m1-fail-closed"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 470,
          "lineEnd": 515,
          "symbol": "MigrateLegacyDataIfNeeded",
          "excerptHash": "sha256:main-installer-migrate"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 681,
          "lineEnd": 699,
          "symbol": "CurStepChanged",
          "excerptHash": "sha256:main-installer-postinstall-migrate"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 467,
          "lineEnd": 512,
          "symbol": "MigrateLegacyDataIfNeeded",
          "excerptHash": "sha256:legacy-installer-migrate"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 678,
          "lineEnd": 694,
          "symbol": "CurStepChanged",
          "excerptHash": "sha256:legacy-installer-postinstall-migrate"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 97,
          "lineEnd": 117,
          "excerptHash": "sha256:plan-m4-lockless-reuse"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 241,
          "lineEnd": 297,
          "symbol": "try_reuse_existing",
          "excerptHash": "sha256:launcher-try-reuse-existing"
        },
        {
          "path": "web/routes/system_health.py",
          "lineStart": 15,
          "lineEnd": 27,
          "symbol": "health",
          "excerptHash": "sha256:health-payload-no-owner"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 379,
          "lineEnd": 439,
          "symbol": "acquire_runtime_lock",
          "excerptHash": "sha256:runtime-lock-owner"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 524,
          "lineEnd": 566,
          "symbol": "_runtime_contract_payload",
          "excerptHash": "sha256:runtime-contract-owner"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "web/routes/system_health.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/installer-目录综合修复计划.plan.md",
        "installer/aps_win7.iss",
        "installer/aps_win7_legacy.iss",
        "assets/启动_排产系统_Chrome.bat",
        "web/routes/system_health.py",
        "web/bootstrap/launcher.py"
      ],
      "recommendedNextAction": "先修正计划表述，再进入实际编码；否则会把阶段错位和单活语义问题直接写进实现。",
      "findingIds": [
        "plan-m1-phase-mismatch",
        "plan-m4-owner-gap"
      ]
    },
    {
      "id": "round3-tests-and-env",
      "title": "第三轮：不明确项脚本化与环境门禁验证",
      "status": "completed",
      "recordedAt": "2026-04-03T16:10:59.790Z",
      "summaryMarkdown": "已把计划里的不明确项转成可执行脚本，并在当前机器完成一轮验证：\n\n1. `tests/verify_installer_vendor_dir.py`：确认当前仓库中 `vendor/` 实际存在，因此 M11 不再是“当前仓库必现”的问题；但 `build_win7_onedir.bat` 仍无条件引用 `vendor`，换机仍可能失败，因此保留为 P2 加固项。\n2. `tests/verify_installer_wmic_availability.bat`：当前 Win10 环境已经直接复现 `wmic` 缺失，说明 M3 不是 Win7 特例，而是新系统上也会真实触发的高优先级兼容风险。\n3. `tests/verify_installer_start_errorlevel.bat`：已修正脚本并重新执行，结果是“无效路径返回 9059、有效命令返回 0”。这说明 M8 不应再写成“死代码删除”，而应写成“保留但明确其只覆盖极端竞态，价值很低”。\n4. `tests/verify_installer_powershell_json_support.bat`：这是本轮新增脚本。当前开发机具备 PowerShell + ConvertFrom-Json + 最小 JSON 解析能力，但这**不能外推到实际 Win7 目标机**。\n\n因此，第三轮最重要的新结论不是“马上删除正则回退”，而是“先在目标机跑 T4，再决定 M6 是否能做分支收敛”。",
      "conclusionMarkdown": "第三轮结论：T1/T2/T3 已把 M11/M3/M8 的不确定性压实；新增 T4 后，M6 也从主观假设变成了可验证门禁。计划若要继续推进，应把“先跑 T4 再做 M6”写进执行顺序。",
      "evidence": [
        {
          "path": "tests/verify_installer_vendor_dir.py",
          "lineStart": 19,
          "lineEnd": 103,
          "symbol": "main",
          "excerptHash": "sha256:t1-vendor-script"
        },
        {
          "path": "build_win7_onedir.bat",
          "lineStart": 23,
          "lineEnd": 35,
          "excerptHash": "sha256:build-vendor-unguarded"
        },
        {
          "path": "tests/verify_installer_wmic_availability.bat",
          "lineStart": 17,
          "lineEnd": 90,
          "excerptHash": "sha256:t2-wmic-script"
        },
        {
          "path": "tests/verify_installer_start_errorlevel.bat",
          "lineStart": 11,
          "lineEnd": 55,
          "excerptHash": "sha256:t3-start-script"
        },
        {
          "path": "tests/verify_installer_powershell_json_support.bat",
          "lineStart": 17,
          "lineEnd": 73,
          "excerptHash": "sha256:t4-powershell-json-script"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 299,
          "lineEnd": 313,
          "symbol": "probe_health",
          "excerptHash": "sha256:launcher-health-fallback"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 147,
          "lineEnd": 172,
          "excerptHash": "sha256:plan-p2-items"
        },
        {
          "path": "tests/verify_installer_vendor_dir.py"
        },
        {
          "path": "tests/verify_installer_wmic_availability.bat"
        },
        {
          "path": "tests/verify_installer_start_errorlevel.bat"
        },
        {
          "path": "tests/verify_installer_powershell_json_support.bat"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md"
        },
        {
          "path": "build_win7_onedir.bat"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "reviewedModules": [
        "tests/verify_installer_vendor_dir.py",
        "tests/verify_installer_wmic_availability.bat",
        "tests/verify_installer_start_errorlevel.bat",
        "tests/verify_installer_powershell_json_support.bat",
        "build_win7_onedir.bat",
        "assets/启动_排产系统_Chrome.bat",
        ".limcode/plans/installer-目录综合修复计划.plan.md"
      ],
      "recommendedNextAction": "把 T4 加入计划前置门禁，并按第二轮结论重写 P0-1/P0-3 后，再开始实际修复。",
      "findingIds": [
        "plan-m6-target-gate"
      ]
    }
  ],
  "findings": [
    {
      "id": "plan-m1-phase-mismatch",
      "severity": "high",
      "category": "other",
      "title": "M1 失败闭合阶段错位",
      "descriptionMarkdown": "计划把“迁移失败即中止安装”写成当前实现可直接落地的改法，但现有 `MigrateLegacyDataIfNeeded` 实际在 `CurStepChanged(ssPostInstall)` 执行。也就是说，调用点已经晚于 `PrepareToInstall`。如果不先调整迁移发生阶段，计划里的“设置 PrepareToInstall 的 Result 中止安装”就无法生效。继续按原表述实施，结果大概率只是把 `MigrationNote` 改得更详细，而不是得到真正的失败闭合。",
      "recommendationMarkdown": "先在计划里明确二选一：A）把迁移动作前移到真正可以失败中止的安装前阶段；B）保留后置迁移，但把目标改成“失败可见 + 半成品清理 + 明确提示”，不要继续写成“中止安装”。",
      "evidence": [
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 66,
          "lineEnd": 85,
          "excerptHash": "sha256:plan-m1-fail-closed"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 470,
          "lineEnd": 515,
          "symbol": "MigrateLegacyDataIfNeeded",
          "excerptHash": "sha256:main-installer-migrate"
        },
        {
          "path": "installer/aps_win7.iss",
          "lineStart": 681,
          "lineEnd": 699,
          "symbol": "CurStepChanged",
          "excerptHash": "sha256:main-installer-postinstall-migrate"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 467,
          "lineEnd": 512,
          "symbol": "MigrateLegacyDataIfNeeded",
          "excerptHash": "sha256:legacy-installer-migrate"
        },
        {
          "path": "installer/aps_win7_legacy.iss",
          "lineStart": 678,
          "lineEnd": 694,
          "symbol": "CurStepChanged",
          "excerptHash": "sha256:legacy-installer-postinstall-migrate"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "web/routes/system_health.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2-code-mapping"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-m4-owner-gap",
      "severity": "high",
      "category": "other",
      "title": "M4 无锁复用缺少 owner 证明",
      "descriptionMarkdown": "计划建议“健康检查通过但锁文件缺失时仍复用实例”，这个修法虽然能避免新开冲突实例，但会削弱单活用户约束。原因是 `/system/health` 只证明服务身份与状态，不包含 owner；如果锁文件丢失，而后台实例属于别的账户，按计划直接复用就会把第二个账户接入现有实例。现有运行时契约 `aps_runtime.json` 已经提供 owner/pid/contract_version，可作为更安全的回退来源。",
      "recommendationMarkdown": "把 P0-3 改写为“三段式”：先看锁；锁缺失时读取 `aps_runtime.json` 中的 owner/pid 做回退判断；若仍无法证明归属，则失败闭合并提示用户，而不是无条件复用。",
      "evidence": [
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 97,
          "lineEnd": 117,
          "excerptHash": "sha256:plan-m4-lockless-reuse"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 241,
          "lineEnd": 297,
          "symbol": "try_reuse_existing",
          "excerptHash": "sha256:launcher-try-reuse-existing"
        },
        {
          "path": "web/routes/system_health.py",
          "lineStart": 15,
          "lineEnd": 27,
          "symbol": "health",
          "excerptHash": "sha256:health-payload-no-owner"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 379,
          "lineEnd": 439,
          "symbol": "acquire_runtime_lock",
          "excerptHash": "sha256:runtime-lock-owner"
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 524,
          "lineEnd": 566,
          "symbol": "_runtime_contract_payload",
          "excerptHash": "sha256:runtime-contract-owner"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "web/routes/system_health.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2-code-mapping"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-m6-target-gate",
      "severity": "medium",
      "category": "test",
      "title": "M6 缺少目标机 PowerShell JSON 门禁",
      "descriptionMarkdown": "计划当前把 M6 写成直接删除健康检查正则回退，但当前仓库并没有在执行顺序里要求先验证目标机是否具备 `ConvertFrom-Json`。第三轮已新增 `tests/verify_installer_powershell_json_support.bat`，当前开发机通过不代表实际 Win7 目标机通过。如果不把 T4 作为门禁写进计划，M6 仍然是基于环境假设而不是基于证据推进。",
      "recommendationMarkdown": "在计划里新增 T4 门禁：只有目标机执行 `tests/verify_installer_powershell_json_support.bat` 成功后，阶段11 才允许删除正则回退；否则应保留回退，或把该分支改成显式失败而不是直接删掉。",
      "evidence": [
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md",
          "lineStart": 168,
          "lineEnd": 169,
          "excerptHash": "sha256:plan-m6-delete-regex"
        },
        {
          "path": "tests/verify_installer_powershell_json_support.bat",
          "lineStart": 17,
          "lineEnd": 73,
          "excerptHash": "sha256:t4-powershell-json-script"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat",
          "lineStart": 299,
          "lineEnd": 313,
          "symbol": "probe_health",
          "excerptHash": "sha256:launcher-health-fallback"
        },
        {
          "path": "tests/verify_installer_vendor_dir.py"
        },
        {
          "path": "tests/verify_installer_wmic_availability.bat"
        },
        {
          "path": "tests/verify_installer_start_errorlevel.bat"
        },
        {
          "path": "tests/verify_installer_powershell_json_support.bat"
        },
        {
          "path": ".limcode/plans/installer-目录综合修复计划.plan.md"
        },
        {
          "path": "build_win7_onedir.bat"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        }
      ],
      "relatedMilestoneIds": [
        "round3-tests-and-env"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:34e8fd1fcbc1c17ba38f4d251271474dbae0677d2f5027e5e32ddadba96221e8",
    "generatedAt": "2026-04-03T16:11:12.981Z",
    "locale": "zh-CN"
  }
}
```
