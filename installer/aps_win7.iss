; Win7 离线安装包（含 Chrome109）
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
OutputBaseFilename=APS_Win7_Setup
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
Name: "{autoprograms}\{#MyAppName} (Chrome)"; Filename: "{app}\{#LauncherBatName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName} (Chrome)"; Filename: "{app}\{#LauncherBatName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#LauncherBatName}"; Description: "安装完成后启动 {#MyAppName} (Chrome)"; Flags: nowait postinstall skipifsilent

