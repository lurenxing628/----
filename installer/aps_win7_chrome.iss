; Win7 browser runtime installer (Chrome109 runtime only)
; 依赖：Inno Setup 6.x（Unicode）

#define MyAppName "APS Chrome109 运行时"
#define MyAppVersion "109.0.5414.120"
#define MyAppPublisher "APS"
#ifndef RuntimeDir
  #define RuntimeDir "..\build\chrome109_runtime_payload"
#endif

[Setup]
AppId={{4B8D2DE0-6E0D-45B5-9F2C-50C77B5F6B70}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\APS\Chrome109
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ChangesEnvironment=yes
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
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "APS_CHROME_DIR"; ValueData: "{app}"; Flags: uninsdeletevalue
