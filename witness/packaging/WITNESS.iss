#ifndef MyAppVersion
  #define MyAppVersion "7.52.0"
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

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\WITNESS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WITNESS"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\WITNESS"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch WITNESS"; Flags: nowait postinstall skipifsilent
