<!-- LIMCODE_SOURCE_ARTIFACT_START -->
{"type":"review","path":".limcode/review/installer综合修复计划三轮审查.md","contentHash":"sha256:ca4ff75ec70485204afaaec03d70ee7f562b83f4fa11af16b424874a461140b2"}
<!-- LIMCODE_SOURCE_ARTIFACT_END -->

## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [x] 阶段1: 编写并执行 T1/T2/T3 基础测试脚本（vendor 目录、WMIC 可用性、start ERRORLEVEL）  `#stage1-tests-base`
- [x] 阶段2: 迁移动作前移到安装前 + CopyDirTree 失败闭合 + 半成品清理（aps_win7.iss + aps_win7_legacy.iss）  `#stage2-m1-preinstall-migration`
- [x] 阶段3: WMIC 锁检查从开放式放行改为失败闭合（启动_排产系统_Chrome.bat）  `#stage3-m3-wmic-fail-closed`
- [x] 阶段4: 锁缺失时走运行时契约回退；无法证明归属则失败闭合（启动_排产系统_Chrome.bat）  `#stage4-m4-contract-fallback`
- [x] 阶段5: 静默卸载停机失败改为失败闭合（三份 ISS 同步）  `#stage5-m2-silent-uninstall`
- [x] 阶段6: RunPreInstallFullWipe 展示停机失败警告（两份 ISS 同步）  `#stage6-m5-preinstall-warning`
- [x] 阶段7: 端口文件读取增加数字验证（启动_排产系统_Chrome.bat）  `#stage7-m7-port-validate`
- [x] 阶段8: validate_dist_exe.py 区分文件不存在与解析失败  `#stage8-m12-validate-parse`
- [x] 阶段9: P2 批量修复（M8/M10/M11/M13/M14/M16 小项修复）  `#stage9-p2-batch`
- [x] 阶段10: ISS 同步校验清单 + verify_installer_iss_sync.py  `#stage10-m9-sync`
- [ ] 阶段11前置: 目标 Win7 机执行 T4（PowerShell JSON 能力门禁）  `#stage11-gate-t4`
- [ ] 阶段11: 仅在 T4 通过后删除健康检查正则回退分支  `#stage11-m6-health-json`
<!-- LIMCODE_TODO_LIST_END -->

# installer 目录综合修复计划

## 一、两份报告发现去重与合并

| 合并后编号 | 来源报告1 | 来源报告2 | 严重级别 | 修复优先级 | 概要 |
|---|---|---|---|---|---|
| M1 | installer-migration-fail-open | ISS-COPY-SILENT + ISS-MIGRATE-PARTIAL | **高** | **P0** | `CopyDirTree` 不校验复制结果 + 迁移失败不清理半成品 |
| M2 | installer-silent-uninstall-log-only | ISS-SILENT-UNINSTALL-SWALLOW | **中** | **P1** | 三份脚本静默卸载停机失败仅记录日志仍继续 |
| M3 | — | BAT-WMIC-FAIL-UNSAFE | **高** | **P0** | WMIC 查询失败时锁检查降级为开放式放行 |
| M4 | — | BAT-REUSE-LOCK-GAP | **高** | **P0** | 健康检查通过但锁文件缺失时缺少运行时契约回退，可能误双开或误复用 |
| M5 | — | BAT-WIPE-STOP-SWALLOW | **高** | **P1** | `RunPreInstallFullWipe` 中停机失败被完全吞没 |
| M6 | installer-launcher-port-only-fallback | BAT-HEALTH-COMPLEXITY | **中** | **P2** | 健康检查正则回退收敛需目标机 `PowerShell` JSON 能力门禁 |
| M7 | — | BAT-PORT-NO-VALIDATE | **中** | **P1** | 端口文件读取无数字验证 |
| M8 | — | BAT-START-RC-DEAD | **中** | **P2** | Chrome `start` 返回码检查价值极低 |
| M9 | installer-script-duplication | ISS-DUP | **中** | **P2** | 主程序包与 legacy 包 `[Code]` 段近乎全文复制 |
| M10 | installer-manual-build-cleanup-fail-open | BUILD-CLEAN-NO-CONFIRM | **低** | **P2** | `build_win7_onedir.bat` 清理旧产物不校验删除结果 |
| M11 | — | BUILD-MISSING-VENDOR | **中→低** | **P2** | 构建脚本无条件引用 `vendor` 目录（目录存在但仍需加保护） |
| M12 | — | VALIDATE-PARSE-SWALLOW | **中** | **P1** | `validate_dist_exe.py` 契约文件解析失败被吞没为超时 |
| M13 | — | VALIDATE-KILL-SWALLOW | **低** | **P2** | `validate_dist_exe.py` 进程清理失败被静默吞没 |
| M14 | — | ISS-RETRY-NO-DELAY | **低** | **P2** | `TryDeleteDirTree` 重试之间无延迟 |
| M15 | — | ISS-VERSION-HARDCODE | **低** | **P2** | 版本号硬编码为 `1.0.0` |
| M16 | — | BUILD-LAUNCHER-FUZZY | **低** | **P2** | 构建脚本用模糊匹配查找启动器文件 |

> 说明：原 M6 同时覆盖“无 `PowerShell` 时只靠端口猜测复用”和“健康检查正则回退”两部分。本次计划修订中，前者并入 M4 的“锁 → 运行时契约 → 失败闭合”方案；阶段 11 仅处理 `probe_health` 的正则回退收敛，并新增目标机门禁 T4。

---

## 二、不确定项测试结果与目标机门禁

### T1: `vendor` 目录（M11）— ✅ 已验证
- **脚本**：`tests/verify_installer_vendor_dir.py`
- **结果**：当前仓库中 `vendor/` 实际存在，包含 2 项，并被 `.gitignore` 排除。
- **结论**：当前仓库/当前机器不会因缺少 `vendor/` 立即失败；但 `build_win7_onedir.bat` 仍然无条件引用该目录，换一台缺少 `vendor/` 的构建机会失败。
- **处理**：降为 P2，在 `--add-data "vendor;vendor"` 前增加 `if exist vendor` 条件保护。

### T2: WMIC 可用性（M3）— ✅ 已验证
- **脚本**：`tests/verify_installer_wmic_availability.bat`
- **结果**：当前 Win10 (10.0.26100) 机器上 `where wmic` 直接返回非零，说明 `wmic.exe` 已不可用。
- **结论**：M3 不是 Win7 特例，而是在较新的 Windows 上也会真实触发的兼容风险。`LOCK_ACTIVE` 不能继续把“查询失败”解释成“进程不存在”。
- **处理**：保持 P0，按失败闭合修复。

### T3: `start` 命令返回码（M8）— ✅ 已验证
- **脚本**：`tests/verify_installer_start_errorlevel.bat`
- **结果**：
  - `start "" "%ComSpec%" /c exit 0` → `ERRORLEVEL=0`
  - `start "" "C:\__nonexistent_path_test_12345\fake_app.exe"` → `ERRORLEVEL=9059`
- **结论**：`start` 返回码检查**不是纯死代码**；但在当前启动器里，Chrome 路径已提前校验存在，因此这段检查只能覆盖“路径在校验后到执行前被删掉”的极端竞态，价值很低。
- **处理**：保留检查，但补充注释澄清其边界；不再把 M8 写成“直接删除”。

### T4: `PowerShell` JSON 能力（M6）— ⚠ 目标 Win7 机待验证
- **脚本**：`tests/verify_installer_powershell_json_support.bat`
- **当前开发机结果**：
  - `PowerShell` 命令存在
  - `ConvertFrom-Json` 可用
  - 最小健康检查 JSON 解析成功
- **结论**：这只能证明当前开发机可以走 `ConvertFrom-Json` 路径，**不能替代目标 Win7 机验证**。
- **处理**：将 T4 设为阶段 11 的前置门禁。只有目标 Win7 机执行该脚本成功后，才允许删除 `probe_health` 中的正则回退。

---

## 三、P0 修复（数据安全 + 单活约束）

### P0-1: 迁移动作前移到安装前 + `CopyDirTree` 失败闭合 + 半成品清理（M1）

**涉及文件**：`installer/aps_win7.iss`、`installer/aps_win7_legacy.iss`

**本项计划修订点**：
不再沿用“在 `CurStepChanged(ssPostInstall)` 中做迁移，再试图中止安装”的写法。迁移动作必须前移到真正可以失败中止的安装前阶段。

#### 改动 A：`CopyDirTree` 返回失败计数
将：

```pascal
procedure CopyDirTree(const SourceDir, DestDir: String);
```

改为：

```pascal
function CopyDirTree(const SourceDir, DestDir: String): Integer;
```

具体改动：
1. 对 `ForceDirectories(DestDir)` 的返回值做校验，失败时累加失败计数并记录日志。
2. 对 `CopyFile(SourcePath, DestPath, False)` 的返回值做校验，失败时累加失败计数并记录文件名。
3. 递归调用时累加子目录失败计数。
4. `SourceDir` 不存在时返回 `0`，表示“无需复制”，而不是失败。

#### 改动 B：新增安装前迁移函数
新增：

```pascal
function TryMigrateLegacyDataBeforeInstall(var FailureReason: String): Boolean;
```

具体改动：
1. 把当前 `MigrateLegacyDataIfNeeded` 的前置判断（`SkipLegacyMigration` / `HasSharedData` / `HasLegacyData`）抽到安装前函数里。
2. 在 `PrepareToInstall` 中，在安装前强制清理逻辑结束后、真正开始复制安装文件前调用该函数。
3. 若 `SkipLegacyMigration = True`，则直接返回成功，并保留现有 `MigrationNote` 语义。
4. `CurStepChanged(ssPostInstall)` 不再执行真正的数据迁移，只负责展示最终 `MigrationNote`。

#### 改动 C：迁移失败的明确处理
1. 对 `ForceDirectories(SharedRoot)`、四次 `CopyDirTree(...)`、`SaveStringToFile(migration_note.txt, ...)` 的结果统一做失败闭合处理。
2. 若累计失败数 `FailCount > 0`，或 `migration_note.txt` 写入失败，删除 `SharedRoot` 下的四个子目录半成品：
   - `db`
   - `logs`
   - `backups`
   - `templates_excel`
3. 将失败原因写成精确信息，例如：
   - `旧版数据迁移失败：共有 X 个文件复制失败，已清理共享目录半成品。`
   - `旧版数据迁移失败：写入 migration_note.txt 失败，已清理共享目录半成品。`
4. 若发生异常，保留异常详情，例如：
   - `旧版数据迁移失败：<异常信息>；已清理共享目录半成品。`
5. `PrepareToInstall` 通过返回非空 `Result` 中止安装，避免“安装已完成但迁移失败”的语义错位。

### P0-2: WMIC 锁检查改为失败闭合（M3）

**涉及文件**：`assets/启动_排产系统_Chrome.bat`

**当前行为**：WMIC 执行失败时，`LOCK_ACTIVE` 可能保持未定义，后续路径把它当作“锁不存在”，从而继续放行。

**修复方案**：
1. 在 `:lock_is_active` 开始前先检查 `where wmic`。
2. 若 `wmic.exe` 缺失，则设置：
   - `LOCK_ACTIVE=UNKNOWN`
   - `LOCK_QUERY_ERROR=wmic_missing`
3. 若 WMIC 命令存在，但查询本身返回非零，则设置：
   - `LOCK_ACTIVE=UNKNOWN`
   - `LOCK_QUERY_ERROR=wmic_failed`
4. 调用方不得再把“未知”解释成“不存在”；未知必须进入失败闭合分支，由后续的运行时契约证明或明确提示接手。

### P0-3: 锁缺失时走运行时契约回退；无法证明归属则失败闭合（M4）

**涉及文件**：`assets/启动_排产系统_Chrome.bat`

**本项计划修订点**：
不再写成“健康检查通过但锁文件缺失时仍复用”。新的规则是：**锁 → 运行时契约 → 失败闭合**。

#### 改动 A：引入运行时契约读取
1. 新增：
   - `RUNTIME_CONTRACT_FILE=%LOG_DIR%\aps_runtime.json`
2. 新增批处理辅助逻辑，读取运行时契约中的最小字段：
   - `owner`
   - `pid`
   - `contract_version`
3. 在阶段 11 完成前，可暂时复用当前 `PowerShell` JSON 解析路径与正则回退；阶段 11 通过 T4 门禁后再收敛分支。

#### 改动 B：`try_reuse_existing` 三段式决策
1. **锁有效**：沿用现有逻辑。
   - 同账户 → 可复用
   - 其他账户 → 明确阻止
2. **锁缺失或锁无效，但运行时契约可证明归属**：
   - 契约证明当前账户，且服务健康 → 可复用
   - 契约证明其他账户，且服务健康 → 明确阻止
3. **锁缺失或锁无效，且无法从运行时契约证明归属**：
   - 即使健康检查通过，仍不得新开实例
   - 设置诸如 `BLOCKED_BY_UNCERTAIN=1`
   - 提示用户：`无法确认现有实例归属，已阻止新实例启动，请先关闭现有实例或清理运行时信号后重试。`

#### 改动 C：端口只作为“活性提示”，不再作为“身份证明”
1. `PORT_READY` 只能证明“某个进程在监听该端口”，不能证明“它就是当前账户的 APS 实例”。
2. 无 `PowerShell` 环境下，不得再仅凭端口监听状态设置 `CAN_REUSE_EXISTING=1`。
3. 这意味着“无锁 + 无契约 + 仅端口监听”的场景改为失败闭合，而不是继续放行或盲目复用。

---

## 四、P1 修复（失败可见性）

### P1-1: 静默卸载停机失败改为失败闭合（M2）

**涉及文件**：`installer/aps_win7.iss`、`installer/aps_win7_legacy.iss`、`installer/aps_win7_chrome.iss`

**修复方案**：
在三份脚本的 `InitializeUninstall()` 中，`UninstallSilent()` 路径下只要停机失败，就设置 `Result := False` 并返回，让自动化调用方拿到明确失败信号。

### P1-2: `RunPreInstallFullWipe` 展示停机失败警告（M5）

**涉及文件**：`installer/aps_win7.iss`、`installer/aps_win7_legacy.iss`

**修复方案**：
当 `StopOk = False` 且 `DeleteErrors = ''` 时：
1. 安装仍可继续；
2. 但必须通过 `MsgBox` 明确提示“目录已清理，但无法确认 APS 已正常退出”；
3. 同时把该信息保留到 `FailureReason`/日志，避免彻底吞没。

### P1-3: 端口文件读取增加数字验证（M7）

**涉及文件**：`assets/启动_排产系统_Chrome.bat`

**修复方案**：
在 `:read_port_file` 末尾增加数字校验，非数字时记录日志并清空 `PORT`：

```bat
echo !PORT! | findstr /R "^[0-9][0-9]*$" >nul
if not !errorlevel!==0 (
  call :log port_file_invalid=!PORT!
  set "PORT="
)
```

### P1-4: `validate_dist_exe.py` 区分“文件不存在”与“解析失败”（M12）

**涉及文件**：`validate_dist_exe.py`

**修复方案**：
1. 三个契约文件缺任何一个 → 返回 `None`，继续等待；
2. 三个文件都存在，但解析失败或值无效 → 立即抛出异常；
3. 不再把“解析失败”伪装成“超时未生成契约”。

---

## 五、P2 修复（可维护性与代码清理）

### P2-1: Chrome `start` 返回码检查（M8）
- 保留检查。
- 增加注释说明：它只能覆盖“路径在校验后到执行前消失”的极端竞态，不能证明 Chrome 启动后是否真的稳定运行。

### P2-2: `build_win7_onedir.bat` 清理旧产物后校验（M10）
- 在删除 `build/` 与 `dist/` 后增加 `if exist` 校验；清理失败则立即退出。

### P2-3: `TryDeleteDirTree` 重试间加 `Sleep(1000)`（M14）
- 在重试循环中增加延迟，避免连续三次紧贴重试。

### P2-4: `validate_dist_exe.py` 进程清理失败打印警告（M13）
- 把 `p.kill()` 的 `except: pass` 改成显式警告输出。

### P2-5: 构建脚本启动器文件查找改为精确路径（M16）
- `build_win7_installer.bat` 直接引用：`assets\启动_排产系统_Chrome.bat`
- 不再使用模糊匹配。

### P2-6: `vendor` 目录条件引用（M11）
- `build_win7_onedir.bat` 在追加 `--add-data "vendor;vendor"` 前增加 `if exist vendor` 条件。

### P2-7: ISS 代码去重（M9）
- 短期：建立 `installer/SYNC_CHECKLIST.md` 与 `tests/verify_installer_iss_sync.py`
- 长期：抽取共享 include 文件

### P2-8: 健康检查正则回退收敛（M6）
**前置门禁**：目标 Win7 机必须先执行 `tests/verify_installer_powershell_json_support.bat`

具体方案：
1. 若目标 Win7 机脚本通过，才删除 `:probe_health` 中 `\x22...` 的正则回退，仅保留 `ConvertFrom-Json` 路径。
2. 若目标 Win7 机脚本不通过，本阶段不执行删分支动作；可维持现状，或单独立项把“缺少 `PowerShell` / `ConvertFrom-Json`”改成显式失败提示。
3. 阶段 11 只处理 JSON 解析分支收敛；“无锁时只靠端口猜测”的问题已在 M4 中通过运行时契约回退解决。

### P2-9: ISS 版本号（M15）
- 暂不修改 `.iss` 文件中的默认值。
- 在 `package_win7.ps1` 中通过 ISCC 参数注入实际版本号。

---

## 六、验证脚本

| 脚本 | 验证内容 |
|---|---|
| `tests/verify_installer_vendor_dir.py` | 检查 `.gitignore` 对 `vendor` 的规则，并确认构建脚本是否对 `vendor` 缺失做条件保护 |
| `tests/verify_installer_wmic_availability.bat` | 验证 `wmic` 是否存在、查询现有进程是否成功，以及查询失败时的风险 |
| `tests/verify_installer_start_errorlevel.bat` | 验证 `start` 对无效路径与有效命令的返回码行为 |
| `tests/verify_installer_powershell_json_support.bat` | 在目标 Win7 机验证 `PowerShell`、`ConvertFrom-Json` 与最小 JSON 解析是否可用 |
| `tests/verify_installer_iss_sync.py` | 对比 `aps_win7.iss` 与 `aps_win7_legacy.iss` 的 `[Code]` 段，建立同步校验基线 |

---

## 七、实施顺序

```
阶段 1（已完成）→ 编写并执行 T1/T2/T3 基础测试脚本
阶段 2（P0）→ M1: 迁移动作前移到安装前 + CopyDirTree 失败闭合 + 半成品清理
阶段 3（P0）→ M3: WMIC 锁检查失败闭合
阶段 4（P0）→ M4: 锁缺失时走运行时契约回退；无法证明归属则失败闭合
阶段 5（P1）→ M2: 静默卸载失败闭合
阶段 6（P1）→ M5: RunPreInstallFullWipe 展示停机失败警告
阶段 7（P1）→ M7: 端口文件数字验证
阶段 8（P1）→ M12: validate_dist_exe.py 解析失败立即报错
阶段 9（P2）→ M8/M10/M11/M13/M14/M16: 小项修复
阶段 10（P2）→ M9: ISS 同步校验清单 + verify_installer_iss_sync.py
阶段 11 前置门禁 → 在目标 Win7 机执行 T4: verify_installer_powershell_json_support.bat
阶段 11（P2）→ M6: 仅在 T4 通过后删除健康检查正则回退
```
