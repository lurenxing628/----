; Win7 browser runtime installer (Chrome109 runtime only)
; 依赖：Inno Setup 6.x（Unicode）

#define MyAppName "APS Chrome109 运行时"
#define MyAppVersion "109.0.5414.120"
#define MyAppPublisher "APS"
#define MyChromeDirName "Chrome109"
#ifndef RuntimeDir
  #define RuntimeDir "..\build\chrome109_runtime_payload"
#endif

[Setup]
AppId={{9731D9A0-2287-4D67-B6AE-2B6F0658C4D6}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\APS\{#MyChromeDirName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; package_win7.ps1 prepares an APS-specific trimmed runtime payload.
; Use /DRuntimeDir=... only when troubleshooting an alternate payload.
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
OutputDir={#SourcePath}\output
OutputBaseFilename=APS_Chrome109_Runtime

[Languages]
; 为了避免不同 Inno 安装包缺失语言文件导致编译失败，这里默认使用内置英文语言包。
; 如需中文安装界面，可后续在构建机上补齐 ChineseSimplified.isl 并改回该行。
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#RuntimeDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKLM; Subkey: "SOFTWARE\APS"; ValueType: string; ValueName: "ChromeDir"; ValueData: "{app}"; Flags: uninsdeletevalue

[Code]
var
  DeleteChromeProfile: Boolean;

function ShouldDeleteChromeProfile: Boolean;
begin
  Result := DeleteChromeProfile;
end;

function TryStopApsChromeProcesses: Boolean;
var
  ResultCode: Integer;
  Params: String;
begin
  Params :=
    'process where "Name=''chrome.exe'' and CommandLine like ''%Chrome109Profile%''" call terminate';
  Result := Exec(ExpandConstant('{sys}\wbem\wmic.exe'), Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if Result then
    Result := ResultCode = 0;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  DeleteChromeProfile := False;
  if UninstallSilent() then
  begin
    if not TryStopApsChromeProcesses then
    begin
      Log('silent uninstall: failed to stop APS Chrome processes before uninstall');
      Result := False;
    end;
    Exit;
  end;

  Result :=
    MsgBox(
      '将卸载 APS Chrome109 运行时。是否继续？',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;
  if not Result then
    Exit;

  DeleteChromeProfile :=
    MsgBox(
      '是否在卸载说明中提示手动删除当前账户的 APS 浏览器用户数据目录（%LOCALAPPDATA%\APS\Chrome109Profile）？' + #13#10 +
      '为避免管理员卸载时误删错误账户的 profile，安装器不会自动删除任何账户的浏览器用户数据。',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;

  if not TryStopApsChromeProcesses then
    Result :=
      MsgBox(
        '未能自动关闭正在运行的 APS 浏览器窗口。继续卸载可能导致文件残留。是否仍要继续？',
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2
      ) = IDYES;
  if Result and DeleteChromeProfile then
    MsgBox(
      '请在需要时手动删除当前账户的浏览器用户数据目录：' + #13#10 +
      ExpandConstant('{localappdata}\APS\Chrome109Profile'),
      mbInformation,
      MB_OK
    );
end;
