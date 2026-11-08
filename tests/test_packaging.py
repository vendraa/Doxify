"""Tes statis dan fungsional untuk paket rilis (Fase 4). Build sungguhan hanya bisa dijalankan di Windows."""
import ast
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app import __version__
from scripts import make_icon, make_version_info, verify_build

ROOT = Path(__file__).resolve().parent.parent
ISS = (ROOT / "installer" / "setup.iss").read_text(encoding="utf-8")
BUILD_PS1 = (ROOT / "scripts" / "windows" / "build.ps1").read_text(encoding="utf-8")


def spec_tree():
    return ast.parse((ROOT / "build.spec").read_text(encoding="utf-8"))


def spec_call(name):
    for node in ast.walk(spec_tree()):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name:
            return {kw.arg: kw.value for kw in node.keywords}
    raise AssertionError(f"{name}(...) tidak ditemukan di build.spec")


def spec_excludes():
    for node in ast.walk(spec_tree()):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "EXCLUDES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("EXCLUDES tidak ditemukan")


class VersionTests(unittest.TestCase):
    def test_version_is_valid_for_windows(self):
        self.assertEqual(len(make_version_info.parse_version(__version__)), 4)

    def test_installer_default_version_matches_app_version(self):
        m = re.search(r'#define AppVersion "([^"]+)"', ISS)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), __version__, "ubah __version__ dan nilai bawaan di setup.iss bersamaan")

    def test_parse_version(self):
        self.assertEqual(make_version_info.parse_version("1.0.0"), (1, 0, 0, 0))
        self.assertEqual(make_version_info.parse_version("2.5"), (2, 5, 0, 0))
        self.assertEqual(make_version_info.parse_version("1.2.3.4"), (1, 2, 3, 4))
        for bad in ("", "1.0.0-beta", "a.b", "1..2", "70000.0.0", "1.2.3.4.5"):
            with self.assertRaises(ValueError, msg=bad):
                make_version_info.parse_version(bad)

    def test_rendered_version_file_is_valid_python_and_complete(self):
        text = make_version_info.render("1.2.3")
        ast.parse(text)
        for needle in ("filevers=(1, 2, 3, 0)", "'ProductVersion', '1.2.3.0'", "'ProductName', 'Doxify'", "'OriginalFilename', 'Doxify.exe'"):
            self.assertIn(needle, text)

    def test_write_version_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_version_info.write_version_file(Path(d) / "sub" / "v.txt")
            self.assertIn(__version__, p.read_text(encoding="utf-8"))


class IconTests(unittest.TestCase):
    def test_committed_icon_has_all_sizes(self):
        with Image.open(ROOT / "assets" / "doxify.ico") as ico:
            sizes = set(ico.info["sizes"])
        for s in (16, 24, 32, 48, 64, 128, 256):
            self.assertIn((s, s), sizes)

    def test_icon_is_rounded_with_transparent_corners_and_opaque_center(self):
        img = make_icon.draw_icon()
        self.assertEqual(img.getpixel((2, 2))[3], 0)
        self.assertEqual(img.getpixel((512, 300))[3], 255)

    def test_installer_icon_path_exists(self):
        self.assertTrue((ROOT / "installer" / ".." / "assets" / "doxify.ico").resolve().is_file())


class InstallerScriptTests(unittest.TestCase):
    def test_per_user_install_without_admin(self):
        self.assertRegex(ISS, r"(?m)^PrivilegesRequired=lowest\s*$")
        self.assertNotRegex(ISS, r"(?mi)^PrivilegesRequired=admin")
        self.assertNotIn("PrivilegesRequiredOverridesAllowed", ISS)
        self.assertIn("DefaultDirName={autopf}\\{#AppName}", ISS)

    def test_app_id_is_a_fixed_guid(self):
        self.assertRegex(ISS, r"(?m)^AppId=\{\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}\s*$")

    def test_installer_name_matches_prd(self):
        self.assertIn("OutputBaseFilename={#AppName}-Setup-{#AppVersion}", ISS)
        self.assertIn('#define AppName "Doxify"', ISS)

    def test_shortcuts(self):
        self.assertIn('Name: "{autoprograms}\\{#AppName}"', ISS)
        self.assertRegex(ISS, r'Name: "\{autodesktop\}\\\{#AppName\}".*Tasks: desktopicon')
        self.assertRegex(ISS, r'Name: "desktopicon".*Flags: unchecked')

    def test_files_come_from_pyinstaller_output_folder(self):
        self.assertIn('Source: "..\\dist\\Doxify\\*"', ISS)
        self.assertEqual(spec_call("COLLECT")["name"].value, "Doxify")

    def test_no_network_or_downloads_in_installer(self):
        self.assertNotRegex(ISS, r"(?i)https?://|ftp://|DownloadTemporaryFile|idp|InstallDelete.*http")
        run_section = ISS.split("[Run]")[1].split("[Code]")[0]
        for line in filter(str.strip, run_section.splitlines()):
            self.assertIn("{app}", line, "[Run] hanya boleh menjalankan Doxify sendiri")

    def test_upgrade_closes_running_app(self):
        self.assertIn("CloseApplications=yes", ISS)

    def test_uninstall_never_touches_user_documents(self):
        code = ISS.split("[Code]")[1]
        for forbidden in ("{userdocs}", "{userpictures}", "{userdesktop}", "{commondocs}", ".pdf", ".jpg", ".png", "{sd}"):
            self.assertNotIn(forbidden, code)
        deletes = re.findall(r"DelTree\(([^)]*)\)", code)
        self.assertEqual(len(deletes), 2)
        self.assertTrue(any("doxify_" in c or "FindRec.Name" in c for c in deletes))
        self.assertTrue(any("{userappdata}\\Doxify" in c for c in deletes))

    def test_settings_removal_is_opt_in_and_skipped_when_silent(self):
        code = ISS.split("[Code]")[1]
        self.assertIn("if not UninstallSilent", code)
        self.assertIn("MB_DEFBUTTON2", code)  # tombol bawaan = Tidak

    def test_setup_icon_and_uninstall_icon_set(self):
        self.assertIn("SetupIconFile=..\\assets\\doxify.ico", ISS)
        self.assertIn("UninstallDisplayIcon={app}\\{#AppExe}", ISS)


class SpecTests(unittest.TestCase):
    def test_folder_mode_windowed_no_upx(self):
        exe = spec_call("EXE")
        self.assertIs(exe["console"].value, False)
        self.assertIs(exe["upx"].value, False)
        self.assertIs(exe["exclude_binaries"].value, True, "mode folder (onedir) memakai exclude_binaries=True + COLLECT")
        self.assertEqual(exe["name"].value, "Doxify")
        self.assertIn("icon", exe)
        self.assertIn("version", exe)
        self.assertIs(spec_call("COLLECT")["upx"].value, False)

    def test_entry_point_exists(self):
        self.assertTrue((ROOT / "run_doxify.py").is_file())
        self.assertIn("run_doxify.py", (ROOT / "build.spec").read_text(encoding="utf-8"))

    def test_network_modules_are_excluded(self):
        ex = set(spec_excludes())
        for needed in ("ssl", "http", "urllib.request", "ftplib", "smtplib", "xmlrpc", "PySide6.QtNetwork", "PySide6.QtWebEngineCore"):
            self.assertIn(needed, ex)

    def test_modules_the_app_needs_are_not_excluded(self):
        ex = set(spec_excludes())
        for needed in ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PIL", "img2pdf", "pikepdf", "lxml", "app", "socket", "json", "urllib", "email"):
            self.assertNotIn(needed, ex)

    def test_core_works_when_all_excluded_stdlib_modules_are_unavailable(self):
        """Membuktikan pengecualian aman untuk inti non-Qt: jika modul-modul itu benar-benar tidak ada
        di paket, konversi dan self-test tetap berjalan."""
        blocked = sorted(m for m in spec_excludes() if not m.startswith("PySide6."))
        with tempfile.TemporaryDirectory() as d:
            site = Path(d) / "site"; site.mkdir()
            (site / "sitecustomize.py").write_text(
                "import sys\nBLOCKED = %r\n"
                "class Block:\n"
                "    def find_spec(self, name, path=None, target=None):\n"
                "        for b in BLOCKED:\n"
                "            if name == b or name.startswith(b + '.'):\n"
                "                raise ImportError('modul dikecualikan dari paket: ' + name)\n"
                "        return None\n"
                "sys.meta_path.insert(0, Block())\n" % (blocked,)
            )
            report = Path(d) / "r.txt"
            env = {"PYTHONPATH": f"{site}{__import__('os').pathsep}{ROOT}", "PATH": __import__("os").environ.get("PATH", "")}
            proc = subprocess.run([sys.executable, str(ROOT / "run_doxify.py"), "--self-test", "--no-gui", str(report)],
                                  cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
            detail = proc.stderr + (report.read_text(encoding="utf-8") if report.exists() else "")
            self.assertEqual(proc.returncode, 0, detail)


class VerifyBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dist = Path(self.tmp.name) / "Doxify"
        self.make("Doxify.exe", "_internal/PySide6/plugins/platforms/qwindows.dll",
                  "_internal/PySide6/plugins/imageformats/qjpeg.dll", "_internal/PySide6/Qt6Core.dll")

    def make(self, *rels):
        for rel in rels:
            p = self.dist / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"x")

    def levels(self):
        return [f.level for f in verify_build.verify(self.dist)]

    def test_good_build_has_no_errors(self):
        self.assertNotIn("ERROR", self.levels())

    def test_missing_exe_is_error(self):
        (self.dist / "Doxify.exe").unlink()
        self.assertIn("ERROR", self.levels())

    def test_qt_network_dll_is_error(self):
        self.make("_internal/PySide6/Qt6Network.dll")
        msgs = [f.message for f in verify_build.verify(self.dist) if f.level == "ERROR"]
        self.assertTrue(any("Qt6Network" in m for m in msgs), msgs)

    def test_ssl_module_is_error(self):
        self.make("_internal/_ssl.pyd")
        self.assertIn("ERROR", self.levels())

    def test_missing_required_plugins_are_errors(self):
        (self.dist / "_internal/PySide6/plugins/imageformats/qjpeg.dll").unlink()
        self.assertIn("ERROR", self.levels())
        self.make("_internal/PySide6/plugins/imageformats/qjpeg.dll")
        (self.dist / "_internal/PySide6/plugins/platforms/qwindows.dll").unlink()
        self.assertIn("ERROR", self.levels())

    def test_openssl_libs_only_warn(self):
        self.make("_internal/libssl-3-x64.dll", "_internal/libcrypto-3-x64.dll")
        lv = self.levels()
        self.assertIn("PERINGATAN", lv); self.assertNotIn("ERROR", lv)

    def test_stray_test_or_settings_files_are_errors(self):
        self.make("_internal/test_secret.py")
        self.assertIn("ERROR", self.levels())

    def test_missing_folder_is_error(self):
        self.assertEqual(verify_build.verify(Path(self.tmp.name) / "tidak_ada")[0].level, "ERROR")

    def test_cli_exit_codes(self):
        ok = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_build.py"), str(self.dist)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        (self.dist / "Doxify.exe").unlink()
        bad = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_build.py"), str(self.dist)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_build.py")], capture_output=True).returncode, 2)


class BuildScriptTests(unittest.TestCase):
    def test_all_steps_present(self):
        for needle in ("PyInstaller", "verify_build.py", "--self-test", "Compress-Archive", "/DAppVersion=",
                       "Get-FileHash", "SHA256", "SHA256SUMS.txt", "build-info.txt", "pip freeze", "-SkipInstaller", "-SkipTests"):
            self.assertIn(needle, BUILD_PS1)

    def test_self_test_failure_stops_build(self):
        self.assertRegex(BUILD_PS1, r"ExitCode -ne 0\)\s*\{\s*Fail")

    def test_build_script_uses_network_only_for_installing_build_tools(self):
        self.assertNotRegex(BUILD_PS1, r"(?i)Invoke-WebRequest|Invoke-RestMethod|\bcurl\b|\bwget\b|Start-BitsTransfer")
        # hanya hitung baris perintah sungguhan (bukan komentar atau teks pesan)
        commands = [l for l in BUILD_PS1.splitlines() if re.match(r"^\s*&\s+\$Python\s+-m\s+pip\s+install\b", l)]
        self.assertEqual(len(commands), 1, commands)
        self.assertIn("requirements-build.txt", commands[0], "yang dipasang hanya alat build, bukan paket lain")

    def test_requirements_build_lists_pyinstaller(self):
        self.assertIn("pyinstaller", (ROOT / "requirements-build.txt").read_text().lower())

    def test_versioned_artifact_names_consistent_with_installer(self):
        self.assertIn("Doxify-Setup-$version.exe", BUILD_PS1)
        self.assertIn("OutputBaseFilename={#AppName}-Setup-{#AppVersion}", ISS)


if __name__ == "__main__":
    unittest.main()
