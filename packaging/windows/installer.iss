#define MyAppName "FIRE-COMMAND STUDIO"
#define MyAppVersion "0.1.0"
#ifndef BundleDir
  #define BundleDir "..\..\runtime\desktop-dist\FIRECommandStudio"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\runtime\release"
#endif

[Setup]
AppId={{6AEB0A45-52B9-4864-B838-A7A911A827E9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=FIRE-COMMAND STUDIO Project
AppPublisherURL=https://github.com/leondic1976/FIRE-COMMAND-STUDIO-
AppSupportURL=https://github.com/leondic1976/FIRE-COMMAND-STUDIO-/issues
DefaultDirName={localappdata}\Programs\FIRECommandStudio
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=FIRE-Command-Studio-Setup-{#MyAppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\FIRECommandStudio.exe
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
SetupLogging=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면 바로가기 만들기"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\FIRECommandStudio.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\FIRECommandStudio.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\FIRECommandStudio.exe"; Description: "훈련 스튜디오 실행"; Flags: nowait postinstall skipifsilent

; User data lives outside {app}. Do not add it to uninstall/delete directives.
