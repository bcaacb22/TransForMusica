; Transformusic — Windows Installer
; Installs: Python venv (all deps), backend, frontend, fpcalc, .env
; Downloads & installs MongoDB 8.3 at install time (needs internet)

#define MyAppName "Transformusic"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Transformusic"

[Setup]
AppId={{B7F3A2E1-4C5D-4E6F-8A9B-0C1D2E3F4A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=Transformusic-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Full Python venv (all deps incl torch/demucs/basic-pitch)
Source: "backend\.venv\*"; DestDir: "{app}\venv"; Flags: ignoreversion recursesubdirs createallsubdirs
; Backend
Source: "backend\server.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\morph_engine.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\style_engine.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\task_manager.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\run_app.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\demucs_server.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\xtts_server.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\f5tts_server.py"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\fpcalc.exe"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "backend\.env"; DestDir: "{app}\backend"; Flags: ignoreversion
; Pre-built frontend
Source: "frontend\dist\*"; DestDir: "{app}\frontend\dist"; Flags: ignoreversion recursesubdirs createallsubdirs
; Launcher
Source: "installer_support\launch.bat"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\mongodb\data"
Name: "{app}\mongodb\log"
Name: "{app}\backend\uploads"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\launch.bat"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\launch.bat"; Tasks: desktopicon

[Run]
Filename: "{app}\launch.bat"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent shellexec

[UninstallRun]
Filename: "net"; Parameters: "stop MongoDB"; Flags: runhidden; RunOnceId: "StopMongo"
Filename: "sc"; Parameters: "delete MongoDB"; Flags: runhidden; RunOnceId: "DeleteMongoSvc"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
const
  MONGO_URL = 'https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.3.0.zip';
  MONGO_ZIP = 'mongodb.zip';

function DownloadMongo(const DestDir: String): Boolean;
var
  ZipPath, ExtractDir, MongodSrc, MongodDst: String;
  ResultCode: Integer;
begin
  Result := False;
  ZipPath := DestDir + '\' + MONGO_ZIP;
  ExtractDir := DestDir + '\mongodb_tmp';
  WizardForm.StatusLabel.Caption := 'Downloading MongoDB 8.3 (~900 MB)...';
  WizardForm.ProgressGauge.Style := npbstMarquee;

  if not Exec('powershell', '-NoProfile -Command "Invoke-WebRequest -Uri ''' + MONGO_URL + ''' -OutFile ''' + ZipPath + '''"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    WizardForm.ProgressGauge.Style := npbstNormal;
    MsgBox('Failed to download MongoDB. You can install it manually later.', mbError, MB_OK);
    Exit;
  end;


  WizardForm.StatusLabel.Caption := 'Extracting MongoDB...';
  // Extract using PowerShell
  if not Exec('powershell', '-NoProfile -Command "Expand-Archive -Path ''' + ZipPath + ''' -DestinationPath ''' + ExtractDir + ''' -Force"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    WizardForm.ProgressGauge.Style := npbstNormal;
    MsgBox('Failed to extract MongoDB.', mbError, MB_OK);
    Exit;
  end;

  // Move mongod.exe to final location
  ForceDirectories(DestDir + '\mongodb\bin');
  if not CopyFile(MongodSrc, MongodDst, False) then
  begin
    WizardForm.ProgressGauge.Style := npbstNormal;
    MsgBox('Failed to install MongoDB binary.', mbError, MB_OK);
    Exit;
  end;

  // Cleanup
  DeleteFile(ZipPath);
  DelTree(ExtractDir, True, True, True);
  WizardForm.ProgressGauge.Style := npbstNormal;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  MongoExe, CfgPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Download + install MongoDB
    DownloadMongo(ExpandConstant('{app}'));

    MongoExe := ExpandConstant('{app}\mongodb\bin\mongod.exe');
    CfgPath := ExpandConstant('{app}\mongodb\bin\mongod.cfg');

    if FileExists(MongoExe) then
    begin
      SaveStringToFile(CfgPath,
        'storage:' + #13#10 +
        '  dbPath: ' + ExpandConstant('{app}\mongodb\data') + #13#10 +
        'systemLog:' + #13#10 +
        '  destination: file' + #13#10 +
        '  logAppend: true' + #13#10 +
        '  path: ' + ExpandConstant('{app}\mongodb\log\mongod.log') + #13#10 +
        'net:' + #13#10 +
        '  port: 27017' + #13#10 +
        '  bindIp: 127.0.0.1' + #13#10,
        False);

      Exec('sc', 'create MongoDB binPath= "' + MongoExe + ' --config ' + CfgPath + ' --service" start= auto', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Exec('net', 'start MongoDB', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;
