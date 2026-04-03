# installer `[Code]` 段同步清单

适用范围：
- `installer/aps_win7.iss`
- `installer/aps_win7_legacy.iss`

目的：
- 约束两份安装脚本中**必须保持一致**的共享实现。
- 在继续保留双脚本的前提下，先用清单与校验脚本避免隐性漂移。

## 必须同步的共享例程

以下例程在两份脚本中应保持逐字一致：

- `SharedDataRootPath`
- `SharedLogDirPath`
- `LegacyDataRootPath`
- `LegacyLogDirPath`
- `RegisteredMainAppDirPath`
- `AppLogDirPath`
- `AppExePathFromDir`
- `ShouldDeleteSharedData`
- `DirHasEntries`
- `HasLegacyData`
- `HasSharedData`
- `CopyDirTree`
- `TryLoadTextFile`
- `ExtractKeyValue`
- `UnescapeJsonString`
- `ExtractJsonStringValue`
- `StateDirHasRuntimeSignals`
- `ResolveHelperExeFromStateDir`
- `KnownRuntimeSignalsExist`
- `ResolveStopHelperExe`
- `AppendMessage`
- `TryDeleteDirTree`
- `HasInstallCleanupTargets`
- `CleanupMigrationPartialData`
- `TryMigrateLegacyDataBeforeInstall`
- `TryStopApsRuntimeAtDir`
- `TryStopKnownApsRuntime`
- `RunPreInstallFullWipe`
- `PrepareToInstall`

## 允许差异的例程

以下例程允许按包类型保留差异：

- `InitializeUninstall`
  - legacy 全量包需要同时关闭后端与内置浏览器。
  - 主程序包只关闭后端。
- `CurStepChanged`
  - 安装完成提示文案允许不同。

## 校验方式

执行：

```powershell
python tests/verify_installer_iss_sync.py
```

若脚本返回非零，说明共享实现已发生漂移，需要先修复再继续改动。
