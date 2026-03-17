; Win7 legacy full installer (internal fallback only)
; 依赖：Inno Setup 6.x（Unicode）

#define MyAppName "排产系统"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "APS"
#define MyAppExeName "排产系统.exe"

#define DistDir "..\dist\排产系统"
#define LauncherBatSource "..\assets\启动_排产系统_Chrome.bat"
#define LauncherBatName "启动_排产系统_Chrome.bat"

[Setup]
AppId={{8A2F3E7A-9A9E-4C44-9E2D-2E79F6A3A7C1}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\APS\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
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

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#LauncherBatSource}"; DestDir: "{app}"; DestName: "{#LauncherBatName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#LauncherBatName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#LauncherBatName}"; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{app}\db"; Check: ShouldDeleteLocalData
Type: filesandordirs; Name: "{app}\logs"; Check: ShouldDeleteLocalData
Type: filesandordirs; Name: "{app}\backups"; Check: ShouldDeleteLocalData
Type: filesandordirs; Name: "{app}\templates_excel"; Check: ShouldDeleteLocalData

[Code]
var
  DeleteLocalData: Boolean;

function ShouldDeleteLocalData: Boolean;
begin
  Result := DeleteLocalData;
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

  Params := '--runtime-stop "' + ExpandConstant('{app}') + '"';
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
  DeleteLocalData := False;
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

  DeleteLocalData :=
    MsgBox(
      '是否同时彻底清空当前安装目录下的本地数据（db、logs、backups、templates_excel）？' + #13#10 +
      '选择“否”则仅卸载程序并保留这些数据。',
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
