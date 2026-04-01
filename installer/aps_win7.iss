; Win7 主程序安装包（不含浏览器运行时）
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
OutputBaseFilename=APS_Main_Setup
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
; 1) 打包 onedir 产物（需先运行 build_win7_onedir.bat）
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 2) 安装启动器（从 assets 投放到安装目录根）
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
  SkipLegacyMigration: Boolean;

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

function LegacyLogDirPath: String;
begin
  Result := AddBackslash(LegacyDataRootPath) + 'logs';
end;

function RegisteredMainAppDirPath: String;
begin
  Result := '';
  RegQueryStringValue(HKLM, 'SOFTWARE\APS', 'MainAppDir', Result);
  Result := Trim(Result);
end;

function AppLogDirPath(const AppDir: String): String;
var
  AppDirValue: String;
begin
  AppDirValue := Trim(AppDir);
  if AppDirValue = '' then
    Result := ''
  else
    Result := AddBackslash(AppDirValue) + 'logs';
end;

function AppExePathFromDir(const AppDir: String): String;
var
  AppDirValue: String;
begin
  AppDirValue := Trim(AppDir);
  if AppDirValue = '' then
    Result := ''
  else
    Result := AddBackslash(AppDirValue) + '{#MyAppExeName}';
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

function TryLoadTextFile(const FileName: String; var Text: String): Boolean;
var
  RawText: AnsiString;
begin
  Text := '';
  if not FileExists(FileName) then
  begin
    Result := False;
    Exit;
  end;
  RawText := '';
  Result := LoadStringFromFile(FileName, RawText);
  if Result then
    Text := RawText;
end;

function ExtractKeyValue(const Text, KeyName: String): String;
var
  SearchText: String;
  Remaining: String;
  LineText: String;
  BreakPos: Integer;
begin
  Result := '';
  SearchText := KeyName + '=';
  Remaining := Text;
  while Remaining <> '' do
  begin
    BreakPos := Pos(#10, Remaining);
    if BreakPos > 0 then
    begin
      LineText := Copy(Remaining, 1, BreakPos - 1);
      Delete(Remaining, 1, BreakPos);
    end
    else
    begin
      LineText := Remaining;
      Remaining := '';
    end;
    if (LineText <> '') and (LineText[Length(LineText)] = #13) then
      Delete(LineText, Length(LineText), 1);
    if Pos(SearchText, LineText) = 1 then
    begin
      Result := Trim(Copy(LineText, Length(SearchText) + 1, MaxInt));
      Exit;
    end;
  end;
end;

function UnescapeJsonString(const Value: String): String;
var
  Index: Integer;
begin
  Result := '';
  Index := 1;
  while Index <= Length(Value) do
  begin
    if (Value[Index] = '\') and (Index < Length(Value)) then
    begin
      if (Value[Index + 1] = '\') or (Value[Index + 1] = '"') or (Value[Index + 1] = '/') then
      begin
        Result := Result + Value[Index + 1];
        Index := Index + 2;
        Continue;
      end;
    end;
    Result := Result + Value[Index];
    Index := Index + 1;
  end;
end;

function ExtractJsonStringValue(const Text, KeyName: String): String;
var
  Marker: String;
  Remaining: String;
  ColonPos: Integer;
  Index: Integer;
begin
  Result := '';
  Marker := '"' + KeyName + '"';
  ColonPos := Pos(Marker, Text);
  if ColonPos = 0 then
    Exit;
  Remaining := Copy(Text, ColonPos + Length(Marker), MaxInt);
  ColonPos := Pos(':', Remaining);
  if ColonPos = 0 then
    Exit;
  Delete(Remaining, 1, ColonPos);
  Remaining := Trim(Remaining);
  if (Remaining = '') or (Remaining[1] <> '"') then
    Exit;
  Delete(Remaining, 1, 1);
  Index := 1;
  while Index <= Length(Remaining) do
  begin
    if Remaining[Index] = '"' then
      Break;
    if (Remaining[Index] = '\') and (Index < Length(Remaining)) then
    begin
      Result := Result + Remaining[Index] + Remaining[Index + 1];
      Index := Index + 2;
      Continue;
    end;
    Result := Result + Remaining[Index];
    Index := Index + 1;
  end;
  Result := Trim(UnescapeJsonString(Result));
end;

function StateDirHasRuntimeSignals(const StateDir: String): Boolean;
var
  StateDirValue: String;
begin
  StateDirValue := Trim(StateDir);
  if StateDirValue = '' then
  begin
    Result := False;
    Exit;
  end;
  Result :=
    FileExists(AddBackslash(StateDirValue) + 'aps_runtime.json') or
    FileExists(AddBackslash(StateDirValue) + 'aps_runtime.lock') or
    FileExists(AddBackslash(StateDirValue) + 'aps_host.txt') or
    FileExists(AddBackslash(StateDirValue) + 'aps_port.txt') or
    FileExists(AddBackslash(StateDirValue) + 'aps_db_path.txt') or
    FileExists(AddBackslash(StateDirValue) + 'aps_launch_error.txt');
end;

function ResolveHelperExeFromStateDir(const StateDir: String): String;
var
  Text: String;
  Candidate: String;
begin
  Result := '';
  if Trim(StateDir) = '' then
    Exit;

  if TryLoadTextFile(AddBackslash(StateDir) + 'aps_runtime.lock', Text) then
  begin
    Candidate := ExtractKeyValue(Text, 'exe_path');
    if (Candidate <> '') and FileExists(Candidate) then
    begin
      Result := Candidate;
      Exit;
    end;
  end;

  if TryLoadTextFile(AddBackslash(StateDir) + 'aps_runtime.json', Text) then
  begin
    Candidate := ExtractJsonStringValue(Text, 'exe_path');
    if (Candidate <> '') and FileExists(Candidate) then
    begin
      Result := Candidate;
      Exit;
    end;
  end;
end;

function KnownRuntimeSignalsExist: Boolean;
var
  RegisteredAppDir: String;
begin
  RegisteredAppDir := RegisteredMainAppDirPath;
  Result :=
    StateDirHasRuntimeSignals(SharedLogDirPath) or
    StateDirHasRuntimeSignals(LegacyLogDirPath) or
    StateDirHasRuntimeSignals(AppLogDirPath(RegisteredAppDir)) or
    StateDirHasRuntimeSignals(AppLogDirPath(ExpandConstant('{app}')));
end;

function ResolveStopHelperExe: String;
var
  RegisteredAppDir: String;
  Candidate: String;
begin
  Result := ResolveHelperExeFromStateDir(SharedLogDirPath);
  if Result <> '' then
    Exit;

  Result := ResolveHelperExeFromStateDir(LegacyLogDirPath);
  if Result <> '' then
    Exit;

  RegisteredAppDir := RegisteredMainAppDirPath;
  if RegisteredAppDir <> '' then
  begin
    Result := ResolveHelperExeFromStateDir(AppLogDirPath(RegisteredAppDir));
    if Result <> '' then
      Exit;
    Candidate := AppExePathFromDir(RegisteredAppDir);
    if (Candidate <> '') and FileExists(Candidate) then
    begin
      Result := Candidate;
      Exit;
    end;
  end;

  Result := ResolveHelperExeFromStateDir(AppLogDirPath(ExpandConstant('{app}')));
  if Result <> '' then
    Exit;

  Candidate := AppExePathFromDir(ExpandConstant('{app}'));
  if (Candidate <> '') and FileExists(Candidate) then
    Result := Candidate;
end;

procedure AppendMessage(var Summary: String; const MessageLine: String);
begin
  if Trim(MessageLine) = '' then
    Exit;
  if Summary <> '' then
    Summary := Summary + #13#10;
  Summary := Summary + MessageLine;
end;

function TryDeleteDirTree(const DirName: String; var ErrorMessage: String): Boolean;
var
  DirValue: String;
  ResultCode: Integer;
  Attempt: Integer;
  Params: String;
begin
  ErrorMessage := '';
  DirValue := Trim(DirName);
  if DirValue = '' then
  begin
    Result := True;
    Exit;
  end;
  if Length(DirValue) <= 3 then
  begin
    Result := False;
    ErrorMessage := '拒绝删除异常目录：' + DirValue;
    Exit;
  end;
  if not DirExists(DirValue) then
  begin
    Result := True;
    Exit;
  end;

  Params := '/C if exist "' + DirValue + '" rd /s /q "' + DirValue + '"';
  for Attempt := 1 to 3 do
  begin
    if not Exec(ExpandConstant('{cmd}'), Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      ResultCode := -1;
    if not DirExists(DirValue) then
    begin
      Result := True;
      Exit;
    end;
  end;

  Result := False;
  ErrorMessage := '目录仍被占用或无法删除：' + DirValue;
end;

function HasInstallCleanupTargets: Boolean;
var
  RegisteredAppDir: String;
begin
  RegisteredAppDir := RegisteredMainAppDirPath;
  Result :=
    KnownRuntimeSignalsExist or
    DirExists(SharedDataRootPath) or
    DirExists(LegacyDataRootPath) or
    DirExists(ExpandConstant('{app}')) or
    ((RegisteredAppDir <> '') and DirExists(RegisteredAppDir));
end;

procedure MigrateLegacyDataIfNeeded;
var
  LegacyRoot: String;
  SharedRoot: String;
begin
  if SkipLegacyMigration then
  begin
    if MigrationNote = '' then
      MigrationNote := '本次安装前已执行强制清理，已跳过当前安装账户 legacy 数据迁移。';
    Exit;
  end;
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

function TryStopApsRuntimeAtDir(const HelperExePath: String; const RuntimeDir: String; const StopApsChrome: Boolean): Boolean;
var
  Params: String;
  ResultCode: Integer;
  RuntimeDirValue: String;
  StateDir: String;
begin
  Result := True;
  RuntimeDirValue := Trim(RuntimeDir);
  if RuntimeDirValue = '' then
    Exit;
  StateDir := AppLogDirPath(RuntimeDirValue);
  if (not DirExists(RuntimeDirValue)) and (not StateDirHasRuntimeSignals(StateDir)) then
    Exit;
  if Trim(HelperExePath) = '' then
  begin
    Result := False;
    Exit;
  end;

  Params := '--runtime-stop "' + RuntimeDirValue + '"';
  if StopApsChrome then
    Params := Params + ' --stop-aps-chrome';

  if not Exec(HelperExePath, Params, ExtractFileDir(HelperExePath), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := False;
    Exit;
  end;
  Result := ResultCode = 0;
end;

function TryStopKnownApsRuntime(const StopApsChrome: Boolean): Boolean;
var
  HelperExePath: String;
  RegisteredAppDir: String;
begin
  Result := True;
  HelperExePath := ResolveStopHelperExe;
  if Trim(HelperExePath) = '' then
  begin
    if KnownRuntimeSignalsExist then
      Result := False;
    Exit;
  end;
  if not TryStopApsRuntimeAtDir(HelperExePath, SharedDataRootPath, StopApsChrome) then
    Result := False;
  if not TryStopApsRuntimeAtDir(HelperExePath, LegacyDataRootPath, StopApsChrome) then
    Result := False;
  RegisteredAppDir := RegisteredMainAppDirPath;
  if (RegisteredAppDir <> '') and (CompareText(RegisteredAppDir, ExpandConstant('{app}')) <> 0) then
    if not TryStopApsRuntimeAtDir(HelperExePath, RegisteredAppDir, StopApsChrome) then
      Result := False;
  if not TryStopApsRuntimeAtDir(HelperExePath, ExpandConstant('{app}'), StopApsChrome) then
    Result := False;
end;

function RunPreInstallFullWipe(const StopApsChrome: Boolean; var FailureReason: String): Boolean;
var
  StopOk: Boolean;
  StopFailure: String;
  DeleteErrors: String;
  DeleteError: String;
  RegisteredAppDir: String;
begin
  FailureReason := '';
  DeleteErrors := '';
  StopFailure := '';
  StopOk := TryStopKnownApsRuntime(StopApsChrome);
  if not StopOk then
    StopFailure := '安装器未能确认 APS 已通过停机 helper 正常退出，将继续尝试删除残留目录。';

  if not TryDeleteDirTree(SharedDataRootPath, DeleteError) then
    AppendMessage(DeleteErrors, DeleteError);
  if not TryDeleteDirTree(LegacyDataRootPath, DeleteError) then
    AppendMessage(DeleteErrors, DeleteError);

  RegisteredAppDir := RegisteredMainAppDirPath;
  if (RegisteredAppDir <> '') and (CompareText(RegisteredAppDir, ExpandConstant('{app}')) <> 0) then
    if not TryDeleteDirTree(RegisteredAppDir, DeleteError) then
      AppendMessage(DeleteErrors, DeleteError);

  if not TryDeleteDirTree(ExpandConstant('{app}'), DeleteError) then
    AppendMessage(DeleteErrors, DeleteError);

  if DeleteErrors <> '' then
  begin
    FailureReason := '安装前强制清理未完成：' + #13#10 + DeleteErrors;
    if StopFailure <> '' then
      FailureReason := FailureReason + #13#10#13#10 + StopFailure;
    FailureReason := FailureReason + #13#10#13#10 + '请确认 APS 已关闭且目录未被占用后重试。';
    Result := False;
    Exit;
  end;

  SkipLegacyMigration := True;
  MigrationNote := '本次安装前已执行强制清理，已跳过当前安装账户 legacy 数据迁移。';
  Result := True;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  NeedsRestart := False;
  SkipLegacyMigration := False;
  if not HasInstallCleanupTargets then
    Exit;

  if MsgBox(
    '检测到本机存在 APS 运行实例或历史残留。继续安装前，安装器将强制清理：' + #13#10 +
    '1. 旧主程序安装目录' + #13#10 +
    '2. 共享数据目录（C:\ProgramData\APS\shared-data）' + #13#10 +
    '3. 当前安装账户的 legacy 目录（%LOCALAPPDATA%\APS\排产系统）' + #13#10#13#10 +
    '不会删除：%LOCALAPPDATA%\APS\Chrome109Profile 与独立 Chrome109 运行时目录。' + #13#10#13#10 +
    '注意：这是破坏性操作。若你确认后安装后续失败，机器会处于“已清空，需重新安装”的状态。是否继续？',
    mbConfirmation,
    MB_YESNO or MB_DEFBUTTON2
  ) <> IDYES then
  begin
    Result := '已取消安装，未执行安装前强制清理。';
    Exit;
  end;

  if not RunPreInstallFullWipe(True, Result) then
    Exit;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  DeleteSharedData := False;
  if UninstallSilent() then
  begin
    if not TryStopKnownApsRuntime(False) then
      Log('silent uninstall: failed to stop APS runtime before uninstall');
    Exit;
  end;

  Result :=
    MsgBox(
      '将卸载主程序“排产系统”。APS Chrome109 运行时需在“添加或删除程序”中单独卸载。是否继续？',
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

  if not TryStopKnownApsRuntime(False) then
    Result :=
      MsgBox(
        '未能自动关闭正在运行的 APS 后端。继续卸载可能导致文件残留。是否仍要继续？',
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
    '安装完成后，请使用开始菜单或桌面快捷方式“排产系统”启动。' + #13#10#13#10 +
    '不要直接双击 {app}\排产系统.exe；它只负责在后台启动本地服务。' + #13#10#13#10 +
    '共享数据目录：' + #13#10 +
    SharedDataRootPath + #13#10#13#10 +
    '若快捷方式只闪一下且未打开 Chrome，请查看：' + #13#10 +
    SharedLogDirPath + '\launcher.log' + #13#10 +
    '并将日志中的 chrome_cmd 复制到 cmd 中复现。' + #13#10#13#10 +
    '迁移说明：' + #13#10 +
    MigrationNote,
    mbInformation,
    MB_OK
  );
end;

