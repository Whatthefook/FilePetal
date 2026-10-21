; ---------------------------------------------------------------------------
; FilePetal for Windows - Inno Setup 6 installer script
;
; Compile:
;     ISCC.exe /DAPPVER=1.11.0 packaging\installer.iss
;
; Produces: FilePetal-Setup.exe
; Per-user install, no UAC prompt, no admin rights required.
; ---------------------------------------------------------------------------

#ifndef APPVER
  #define APPVER "1.11.0"
#endif

#ifndef BUNDLEDIR
  #define BUNDLEDIR "..\dist\FilePetal"
#endif
#ifndef OUTPUTDIR
  #define OUTPUTDIR "..\dist"
#endif

#define AppName "FilePetal"
#define AppPublisher "FilePetal Contributors"
#define AppExeName "FilePetal.exe"

[Setup]
; Stable AppId so upgrades replace the previous install instead of stacking.
AppId={{8B3F9A1D-5E2C-4A7B-9D1E-3F5B8A1E7C41}
AppName={#AppName}
AppVersion={#APPVER}
AppVerName={#AppName} {#APPVER}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\FilePetal
DefaultGroupName=FilePetal
DisableProgramGroupPage=yes
; "lowest" = per-user install, no UAC prompt, no admin rights required.
PrivilegesRequired=lowest
OutputDir={#OUTPUTDIR}
OutputBaseFilename=FilePetal-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Start FilePetal automatically when I sign in to Windows"; GroupDescription: "Startup:"

[Files]
Source: "{#BUNDLEDIR}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FilePetal"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\FilePetal"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\FilePetal"; Filename: "{app}\{#AppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Parameters: "--register-shell"; Flags: runhidden waituntilterminated
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,FilePetal}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\{#AppExeName}"; Parameters: "--unregister-shell"; Flags: runhidden waituntilterminated
