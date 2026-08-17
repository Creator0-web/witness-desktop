#ifndef MyAppVersion
  #define MyAppVersion "7.52.1"
#endif

#define MyAppName "WITNESS"
#define MyAppExeName "WITNESS.exe"
#define MyAppPublisher "WITNESS"

[Setup]
AppId={{D799F424-20A6-42A4-AE05-79D42C827E50}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\WITNESS
DisableDirPage=yes
DefaultGroupName=WITNESS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=WITNESS-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
SetupIconFile=..\ui_qt\assets\branding\witness.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[InstallDelete]
; Program files are disposable; personal data lives separately under
; %LOCALAPPDATA%\WITNESS.  Clear the old app directory before copying the
; new onedir build so stale Python modules from an older/manual install can
; never survive an upgrade and shadow bundled canonical modules.
Type: filesandordirs; Name: "{app}\*"

[Files]
Source: "..\dist\WITNESS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WITNESS"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\WITNESS"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch WITNESS"; Flags: nowait postinstall skipifsilent
