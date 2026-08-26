#ifndef MyAppVersion
  #define MyAppVersion "0.2.4"
#endif

#define MyAppName "Codex Controller for DualSense"
#define MyAppExeName "DualSenseCodex.exe"

[Setup]
AppId={{A1498B5D-2AA2-4E64-BD79-7D03BCDAE409}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Codex Controller for DualSense contributors
DefaultDirName={autopf}\Codex Controller for DualSense
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir=output
OutputBaseFilename=DualSense-Codex-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany=Codex Controller for DualSense contributors
VersionInfoDescription=DualSense controller integration for Codex Desktop
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (c) Codex Controller for DualSense contributors

[Languages]
Name: "chinesetraditional"; MessagesFile: "ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他選項："; Flags: unchecked

[Files]
Source: "dist\DualSenseCodex\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\停止 {#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--stop"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--install-startup"; Flags: runhidden waituntilterminated; StatusMsg: "正在設定登入後自動啟動…"
Filename: "{app}\{#MyAppExeName}"; Description: "開啟 DualSense Codex 控制中心"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\{#MyAppExeName}"; Parameters: "--uninstall-startup"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveStartup"
