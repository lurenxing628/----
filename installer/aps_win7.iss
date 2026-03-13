; Win7 主程序安装包（不含浏览器运行时）
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
OutputBaseFilename=APS_Main_Setup
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
; 为了避免不同 Inno 安装包缺失语言文件导致编译失败，这里默认使用内置英文语言包。
; 如需中文安装界面，可后续在构建机上补齐 ChineseSimplified.isl 并改回该行。
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
; 1) 打包 onedir 产物（需先运行 build_win7_onedir.bat）
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 2) 安装启动器（从 assets 投放到安装目录根）
Source: "{#LauncherBatSource}"; DestDir: "{app}"; DestName: "{#LauncherBatName}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{cmd}"; Parameters: "/c ""{app}\{#LauncherBatName}"""; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{cmd}"; Parameters: "/c ""{app}\{#LauncherBatName}"""; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
  if UninstallSilent() then
    Exit;

  Result :=
    MsgBox(
      '卸载将删除安装目录下的程序文件与本地数据（包括 db、logs、backups、templates_excel）。如需保留，请先备份后再继续。',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then
    Exit;

  MsgBox(
    '安装完成后，请使用开始菜单或桌面快捷方式“排产系统”启动。' + #13#10#13#10 +
    '不要直接双击 {app}\排产系统.exe；它只负责在后台启动本地服务。' + #13#10#13#10 +
    '若快捷方式只闪一下且未打开 Chrome，请查看：' + #13#10 +
    ExpandConstant('{app}\logs\launcher.log') + #13#10 +
    '并将日志中的 chrome_cmd 复制到 cmd 中复现。',
    mbInformation,
    MB_OK
  );
end;

