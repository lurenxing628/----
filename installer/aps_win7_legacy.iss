; Win7 legacy full installer (internal fallback only)
; 依赖：Inno Setup 6.x（Unicode）

#define MyAppName "排产系统"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "APS"
#define MyAppExeName "排产系统.exe"
#define MyAppDirName "SchedulerApp"
#define SharedDataRoot "{commonappdata}\APS\shared-data"
#define SharedLogDir "{commonappdata}\APS\shared-data\logs"

#define DistDir "..\dist\排产系统"
#define LauncherBatSource "..\assets\启动_排产系统_Chrome.bat"
#define LauncherBatName "启动_排产系统_Chrome.bat"

[Setup]
AppId={{F1A7FE2B-09C7-4D54-9341-5F6D7E3B95A1}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\APS\{#MyAppDirName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir={#SourcePath}\output
OutputBaseFilename=APS_Legacy_Full_Setup
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
; 为了避免不同 Inno 安装包缺失语言文件导致编译失败，这里默认使用内置英文语言包。
; 如需中文安装界面，可后续在构建机上补齐 ChineseSimplified.isl 并改回该行。
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\APS"; Flags: uninsneveruninstall
Name: "{#SharedDataRoot}"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{#SharedDataRoot}\db"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{#SharedDataRoot}\logs"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{#SharedDataRoot}\backups"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{#SharedDataRoot}\templates_excel"; Permissions: users-modify; Flags: uninsneveruninstall

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#LauncherBatSource}"; DestDir: "{app}"; DestName: "{#LauncherBatName}"; Flags: ignoreversion

[Icons]
Name: "{commonprograms}\{#MyAppName}"; Filename: "{cmd}"; Parameters: "/c ""{app}\{#LauncherBatName}"""; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{cmd}"; Parameters: "/c ""{app}\{#LauncherBatName}"""; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "SOFTWARE\APS"; ValueType: string; ValueName: "MainAppDir"; ValueData: "{app}"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "SOFTWARE\APS"; ValueType: string; ValueName: "SharedDataRoot"; ValueData: "{#SharedDataRoot}"; Flags: uninsdeletevalue

[UninstallDelete]
Type: filesandordirs; Name: "{#SharedDataRoot}\db"; Check: ShouldDeleteSharedData
Type: filesandordirs; Name: "{#SharedDataRoot}\logs"; Check: ShouldDeleteSharedData
Type: filesandordirs; Name: "{#SharedDataRoot}\backups"; Check: ShouldDeleteSharedData
Type: filesandordirs; Name: "{#SharedDataRoot}\templates_excel"; Check: ShouldDeleteSharedData

[Code]
var
  DeleteSharedData: Boolean;
  MigrationNote: String;

function SharedDataRootPath: String;
begin
  Result := ExpandConstant('{#SharedDataRoot}');
end;

function SharedLogDirPath: String;
begin
  Result := ExpandConstant('{#SharedLogDir}');
end;

function LegacyDataRootPath: String;
begin
  Result := ExpandConstant('{localappdata}\APS\排产系统');
end;

function ShouldDeleteSharedData: Boolean;
begin
  Result := DeleteSharedData;
end;

function DirHasEntries(const DirName: String): Boolean;
var
  FindRec: TFindRec;
begin
  Result := False;
  if not DirExists(DirName) then
    Exit;
  if FindFirst(DirName + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          Result := True;
          Exit;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function HasLegacyData: Boolean;
begin
  Result :=
    DirHasEntries(LegacyDataRootPath + '\db') or
    DirHasEntries(LegacyDataRootPath + '\logs') or
    DirHasEntries(LegacyDataRootPath + '\backups') or
    DirHasEntries(LegacyDataRootPath + '\templates_excel');
end;

function HasSharedData: Boolean;
begin
  Result :=
    DirHasEntries(SharedDataRootPath + '\db') or
    DirHasEntries(SharedDataRootPath + '\logs') or
    DirHasEntries(SharedDataRootPath + '\backups') or
    DirHasEntries(SharedDataRootPath + '\templates_excel');
end;

procedure CopyDirTree(const SourceDir, DestDir: String);
var
  FindRec: TFindRec;
  SourcePath: String;
  DestPath: String;
begin
  if not DirExists(SourceDir) then
    Exit;
  ForceDirectories(DestDir);
  if FindFirst(SourceDir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name = '.') or (FindRec.Name = '..') then
          Continue;
        SourcePath := SourceDir + '\' + FindRec.Name;
        DestPath := DestDir + '\' + FindRec.Name;
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          CopyDirTree(SourcePath, DestPath)
        else
          CopyFile(SourcePath, DestPath, False);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure MigrateLegacyDataIfNeeded;
var
  LegacyRoot: String;
  SharedRoot: String;
begin
  MigrationNote := '';
  LegacyRoot := LegacyDataRootPath;
  SharedRoot := SharedDataRootPath;
  if HasSharedData then
  begin
    MigrationNote :=
      '已检测到共享数据目录中已有数据，安装器不会覆盖旧数据。';
    Exit;
  end;
  if not HasLegacyData then
  begin
    MigrationNote :=
      '未检测到当前安装账户下的旧版 per-user 数据，无需迁移。';
    Exit;
  end;
  try
    ForceDirectories(SharedRoot);
    CopyDirTree(LegacyRoot + '\db', SharedRoot + '\db');
    CopyDirTree(LegacyRoot + '\logs', SharedRoot + '\logs');
    CopyDirTree(LegacyRoot + '\backups', SharedRoot + '\backups');
    CopyDirTree(LegacyRoot + '\templates_excel', SharedRoot + '\templates_excel');
    SaveStringToFile(
      SharedRoot + '\migration_note.txt',
      'source=' + LegacyRoot + #13#10 +
      'mode=copy_only' + #13#10 +
      'note=legacy per-user data copied into shared-data root; source preserved for rollback' + #13#10,
      False
    );
    MigrationNote :=
      '已将当前安装账户下的旧版 per-user 数据复制到共享数据目录；旧目录未删除，可作为回退来源。';
  except
    MigrationNote :=
      '旧版 per-user 数据迁移失败；原始目录未被删除，可删除共享目录后重新安装以回退。';
  end;
end;

function TryStopApsRuntime(const StopApsChrome: Boolean): Boolean;
var
  ExePath: String;
  Params: String;
  ResultCode: Integer;
begin
  Result := True;
  ExePath := ExpandConstant('{app}\{#MyAppExeName}');
  if not FileExists(ExePath) then
    Exit;

  Params := '--runtime-stop "' + SharedLogDirPath + '"';
  if StopApsChrome then
    Params := Params + ' --stop-aps-chrome';

  if not Exec(ExePath, Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := False;
    Exit;
  end;
  Result := ResultCode = 0;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  DeleteSharedData := False;
  if UninstallSilent() then
  begin
    if not TryStopApsRuntime(True) then
      Log('silent uninstall: failed to stop APS runtime or bundled Chrome before uninstall');
    Exit;
  end;

  Result :=
    MsgBox(
      '将卸载 legacy 全量包（含内置浏览器）。是否继续？',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;
  if not Result then
    Exit;

  DeleteSharedData :=
    MsgBox(
      '是否同时清空共享数据目录中的本地数据（db、logs、backups、templates_excel）？' + #13#10 +
      '这些数据会影响所有使用这台机器的账户。选择“否”则仅卸载程序文件并保留共享数据。',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;

  if not TryStopApsRuntime(True) then
    Result :=
      MsgBox(
        '未能自动关闭正在运行的 APS 后端或内置浏览器。继续卸载可能导致文件残留。是否仍要继续？',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2
      ) = IDYES;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then
    Exit;

  MigrateLegacyDataIfNeeded;
  MsgBox(
    'legacy 全量包安装完成后，请使用开始菜单或桌面快捷方式“排产系统”启动。' + #13#10#13#10 +
    '共享数据目录：' + #13#10 +
    SharedDataRootPath + #13#10#13#10 +
    '若快捷方式只闪一下且未打开 Chrome，请查看：' + #13#10 +
    SharedLogDirPath + '\launcher.log' + #13#10 +
    '迁移说明：' + #13#10 +
    MigrationNote,
    mbInformation,
    MB_OK
  );
end;
