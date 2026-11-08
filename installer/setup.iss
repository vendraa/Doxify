; Skrip installer Doxify (Inno Setup 6). Dibuat lewat scripts\windows\build.ps1, yang mengirim versi:
;     ISCC.exe /DAppVersion=1.0.0 installer\setup.iss
; Nilai bawaan di bawah dipakai bila skrip ini dikompilasi langsung dari Inno Setup.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Doxify"
#define AppExe "Doxify.exe"

[Setup]
; AppId JANGAN DIUBAH setelah rilis pertama: Inno Setup memakainya untuk mengenali instalasi lama
; sehingga memasang ulang di atas versi lama berfungsi sebagai pembaruan (FR-54).
AppId={{27A7665A-64D9-43ED-AFEC-2BC8EFAE1439}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
VersionInfoVersion={#AppVersion}
; Pemasangan per-pengguna tanpa hak administrator dan tanpa prompt UAC (FR-51).
; Dengan PrivilegesRequired=lowest, {autopf} menjadi %LOCALAPPDATA%\Programs.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\dist\installer
; Nama file installer (FR-50)
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
SetupIconFile=..\assets\doxify.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Jika Doxify sedang terbuka saat memperbarui, tutup dulu agar file tidak terkunci.
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut di Desktop"; GroupDescription: "Shortcut tambahan:"; Flags: unchecked

[Files]
Source: "..\dist\Doxify\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
; Shortcut Start Menu (FR-52) dan shortcut Desktop opsional
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Jalankan {#AppName} sekarang"; Flags: nowait postinstall skipifsilent

[Code]
{ Saat uninstall: bersihkan sisa folder temp Doxify, lalu tanyakan apakah pengaturan ikut dihapus.
  Gambar dan PDF milik pengguna TIDAK PERNAH disentuh (FR-53). }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  FindRec: TFindRec;
  TempDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  TempDir := ExpandConstant('{%TEMP}');
  if (TempDir <> '') and FindFirst(TempDir + '\doxify_*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          DelTree(TempDir + '\' + FindRec.Name, True, True, True);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;

  if not UninstallSilent then
  begin
    if MsgBox('Hapus juga pengaturan Doxify (folder pengaturan di profil Anda)?' + #13#10 +
              'Gambar dan PDF Anda tidak akan dihapus.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{userappdata}\Doxify'), True, True, True);
  end;
end;
