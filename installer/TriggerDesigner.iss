; Inno Setup 6. Build with:
;   iscc /DMyAppVersion=0.1.0-alpha.3 installer\TriggerDesigner.iss
; The version comes from the build; it is never typed here.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "..\dist\TriggerEditor"
#endif
#define MyAppName "Trigger Designer"
#define MyAppPublisher "Blue Octa Studios"
#define MyAppURL "https://github.com/AzadKshitij/TriggerEditor"
#define MyAppExeName "TriggerEditor.exe"
#define MyAppAssocName MyAppName + " File"
#define MyAppAssocExt ".tds"
#define MyAppAssocKey "TriggerDesigner.Workflow"
#define SystemEnvKey "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

[Setup]
AppId={{A19CEDC1-16D6-4F99-B585-C562029CAD21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
ChangesEnvironment=yes
DisableProgramGroupPage=yes
; Per user by default (no administrator needed); the setup dialog offers all users.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=TriggerDesigner-{#MyAppVersion}-setup
SetupIconFile=..\src\trigger_designer\resources\Icon.ico
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full: editor, command line and AI tools"
Name: "editor"; Description: "Editor only"
Name: "cli"; Description: "Command line and AI tools only"
Name: "custom"; Description: "Custom"; Flags: iscustom

[Components]
Name: "runtime"; Description: "Shared runtime (needed by everything)"; Types: full editor cli custom; Flags: fixed
Name: "editor"; Description: "Trigger Designer editor"; Types: full editor
Name: "cli"; Description: "Command-line program (tds)"; Types: full cli
Name: "mcp"; Description: "AI tool setup (tds mcp, default policy, guide)"; Types: full cli

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Components: editor; Flags: unchecked
Name: "addtopath"; Description: "Add the command-line tools (tds) to PATH"; GroupDescription: "Command line:"; Components: cli mcp; Flags: unchecked

[Files]
Source: "{#DistDir}\_internal\*"; DestDir: "{app}\_internal"; Components: runtime; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Components: runtime; Flags: ignoreversion
Source: "..\installer\README.txt"; DestDir: "{app}"; Components: runtime; Flags: ignoreversion
Source: "{#DistDir}\{#MyAppExeName}"; DestDir: "{app}"; Components: editor; Flags: ignoreversion
Source: "{#DistDir}\tds.exe"; DestDir: "{app}"; Components: cli mcp; Flags: ignoreversion
Source: "..\docs\guide\mcp-server.md"; DestDir: "{app}\docs"; Components: mcp; Flags: ignoreversion
Source: "..\installer\agent-policy.json"; DestDir: "{userappdata}\Trigger Designer"; Components: mcp; Flags: onlyifdoesntexist uninsneveruninstall

[Registry]
; PATH: per user, or machine-wide in an all-users install. Removed again on uninstall.
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: (not IsAdminInstallMode) and NeedsAddPath(False)
Root: HKLM; Subkey: "{#SystemEnvKey}"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: IsAdminInstallMode and NeedsAddPath(True)
; File type: the ProgID, "Open with", and the default only when nobody owns .tds yet
; (Tableau uses .tds too; Windows keeps the user's own choice).
; None of these keys is deleted on uninstall: they may already have been written
; by the app's Help menu item, and Inno cannot tell them apart. Remove the file
; association in Settings > Default apps if you want it gone.
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocName}"; Components: editor
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Components: editor
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Components: editor
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocExt}\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppAssocKey}"; ValueData: ""; Components: editor
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocExt}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocKey}"; Components: editor; Flags: createvalueifdoesntexist
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Components: editor

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Components: editor
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Components: editor; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppName} AI tools setup"; Filename: "{app}\docs\mcp-server.md"; Components: mcp

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; Components: editor

[Code]
function EnvKey(System: Boolean): string;
begin
  if System then Result := '{#SystemEnvKey}' else Result := 'Environment';
end;

function EnvRoot(System: Boolean): Integer;
begin
  if System then Result := HKLM else Result := HKCU;
end;

function NeedsAddPath(System: Boolean): Boolean;
var
  Existing: string;
begin
  if not RegQueryStringValue(EnvRoot(System), EnvKey(System), 'Path', Existing) then
    Existing := '';
  Result := Pos(';' + Uppercase(ExpandConstant('{app}')) + ';', ';' + Uppercase(Existing) + ';') = 0;
end;

procedure RemoveFromPath(System: Boolean);
var
  Existing, Wrapped, Mine: string;
  P: Integer;
begin
  if not RegQueryStringValue(EnvRoot(System), EnvKey(System), 'Path', Existing) then Exit;
  { Work on ";path;" so the first and last entries are found like any other. }
  Wrapped := ';' + Existing + ';';
  Mine := ';' + ExpandConstant('{app}') + ';';
  P := Pos(Uppercase(Mine), Uppercase(Wrapped));
  if P = 0 then Exit;
  Delete(Wrapped, P, Length(Mine) - 1);
  Existing := Copy(Wrapped, 2, Length(Wrapped) - 2);
  RegWriteExpandStringValue(EnvRoot(System), EnvKey(System), 'Path', Existing);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  { The AI tool setup runs through tds.exe, so it needs the command line. }
  if CurPageID = wpSelectComponents then
    if WizardIsComponentSelected('mcp') and not WizardIsComponentSelected('cli') then
    begin
      MsgBox('The AI tool setup runs through the command-line program, so that is installed too.', mbInformation, MB_OK);
      WizardSelectComponents('cli');
    end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RemoveFromPath(False);
    if IsAdminInstallMode then RemoveFromPath(True);
    if DirExists(ExpandConstant('{userappdata}\Trigger Designer')) and not UninstallSilent then
      if MsgBox('Also delete your Trigger Designer settings and AI policy file?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{userappdata}\Trigger Designer'), True, True, True);
  end;
end;
