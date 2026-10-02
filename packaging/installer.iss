; Inno Setup 6 — produit "Arducam Capture Setup.exe"
; Prérequis de build : pyinstaller packaging/pyinstaller.spec puis iscc packaging/installer.iss
#define AppName "Arducam Capture"
#define AppVersion "0.1.0"

[Setup]
AppId={{6B1F6E0A-5C0D-4E57-9B0B-3A6E0C1D2F41}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=Arducam Capture Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\ArducamCapture.exe

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; Flags: checkedonce

[Files]
Source: "..\dist\ArducamCapture\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ArducamCapture.exe"; Tasks: desktopicon
Name: "{group}\{#AppName}"; Filename: "{app}\ArducamCapture.exe"

[Run]
Filename: "{app}\ArducamCapture.exe"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent
