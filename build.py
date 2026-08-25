"""
build.py — Bidas PC Optimizer v2.0
====================================
Bundles the app with PyInstaller.
No pywebview required — uses stdlib http.server + PowerShell WebView2.

Requirements:
    pip install pyinstaller

Usage:
    python build.py              # build exe + generate .nsi
    python build.py --compile    # also compile installer with makensis
    python build.py --nsi-only   # regenerate .nsi only
"""

import os, sys, shutil, pathlib, subprocess, argparse

APP_NAME         = "Bidas PC Optimizer"
APP_VERSION      = "2.0"
APP_VERSION_VI   = "2"
APP_EXE_NAME     = "BidasPCOptimizer"
MAIN_SCRIPT      = "main.py"
PUBLISHER        = "Bidas"
NSI_FILE         = "BidasPCOptimizer_Setup.nsi"
OUTPUT_EXE       = f"BidasPCOptimizer_v{APP_VERSION}_Setup.exe"
REGISTRY_KEY     = "BidasPCOptimizer"
INSTALL_DIR_NAME = "Bidas PC Optimizer"


def step(msg): print(f"\n{'─'*60}\n  {msg}\n{'─'*60}")


def build_exe(root: pathlib.Path):
    step("Building executable with PyInstaller")
    dist_dir  = root / "dist"
    build_dir = root / "build"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",          # no console window
        "--uac-admin",         # request UAC elevation via manifest
        f"--name={APP_EXE_NAME}",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        # No pywebview — only stdlib needed, nothing extra to collect
        str(root / MAIN_SCRIPT),
    ]

    result = subprocess.run(cmd, cwd=root)
    if result.returncode != 0:
        print("❌ PyInstaller failed.")
        sys.exit(1)

    out_dir = dist_dir / APP_EXE_NAME

    # Copy scripts folder and ui.html next to the exe
    scripts_dst = out_dir / "scripts"
    if scripts_dst.exists():
        shutil.rmtree(scripts_dst)
    shutil.copytree(root / "scripts", scripts_dst)
    shutil.copy2(root / "ui.html", out_dir / "ui.html")

    print(f"  ✅ Built at: {out_dir}")
    return out_dir


def collect_files(src_dir: pathlib.Path):
    entries = []
    for root, dirs, files in os.walk(src_dir):
        if not files:
            continue
        rel      = pathlib.Path(root).relative_to(src_dir)
        rel_nsis = str(rel).replace("/", "\\") if str(rel) != "." else ""
        entries.append((rel_nsis, [pathlib.Path(root) / f for f in files]))
    return entries


def build_nsi(root: pathlib.Path, app_dir: pathlib.Path) -> pathlib.Path:
    step("Generating NSIS installer script")
    entries = collect_files(app_dir)

    install_lines = []
    for rel_sub, files in entries:
        install_lines.append(
            f'  SetOutPath "$INSTDIR\\{rel_sub}"' if rel_sub else '  SetOutPath "$INSTDIR"'
        )
        for fp in files:
            install_lines.append(f'  File "{fp}"')

    all_subdirs = set()
    for rel_sub, _ in entries:
        if rel_sub:
            parts = rel_sub.split("\\")
            for i in range(len(parts), 0, -1):
                all_subdirs.add("\\".join(parts[:i]))

    uninstall_lines = []
    for rel_sub, files in entries:
        for fp in files:
            path = (f'$INSTDIR\\{rel_sub}\\{fp.name}' if rel_sub
                    else f'$INSTDIR\\{fp.name}')
            uninstall_lines.append(f'  Delete "{path}"')
    for sd in sorted(all_subdirs, key=lambda x: x.count("\\"), reverse=True):
        uninstall_lines.append(f'  RMDir "$INSTDIR\\{sd}"')
    uninstall_lines.append('  RMDir "$INSTDIR"')

    install_block   = "\n".join(install_lines)
    uninstall_block = "\n".join(uninstall_lines)

    nsi = f"""\
; {APP_NAME} v{APP_VERSION} — NSIS Installer
Unicode True
!include "MUI2.nsh"

Name              "{APP_NAME} v{APP_VERSION}"
OutFile           "{OUTPUT_EXE}"
InstallDir        "$LOCALAPPDATA\\{INSTALL_DIR_NAME}"
InstallDirRegKey  HKCU "Software\\{APP_NAME}" "InstallDir"
RequestExecutionLevel admin

VIProductVersion  "{APP_VERSION_VI}.0.0.0"
VIAddVersionKey   "ProductName"     "{APP_NAME}"
VIAddVersionKey   "FileVersion"     "{APP_VERSION_VI}.0.0.0"
VIAddVersionKey   "ProductVersion"  "{APP_VERSION}"
VIAddVersionKey   "CompanyName"     "{PUBLISHER}"
VIAddVersionKey   "FileDescription" "{APP_NAME} Installer"
VIAddVersionKey   "LegalCopyright"  "(c) 2026 {PUBLISHER}"

!define MUI_ABORTWARNING
!define MUI_ICON              "${{NSISDIR}}\\Contrib\\Graphics\\Icons\\modern-install.ico"
!define MUI_UNICON            "${{NSISDIR}}\\Contrib\\Graphics\\Icons\\modern-uninstall.ico"
!define MUI_FINISHPAGE_RUN          "$INSTDIR\\{APP_EXE_NAME}.exe"
!define MUI_FINISHPAGE_RUN_TEXT     "Launch {APP_NAME}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "{APP_NAME} (required)" SecMain
  SectionIn RO
{install_block}
  WriteUninstaller "$INSTDIR\\Uninstall.exe"
  WriteRegStr HKCU "Software\\{APP_NAME}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "DisplayName"     "{APP_NAME} v{APP_VERSION}"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "UninstallString" '"$INSTDIR\\Uninstall.exe"'
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "Publisher"       "{PUBLISHER}"
  WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "DisplayVersion"  "{APP_VERSION}"
  WriteRegDWORD HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "NoModify" 1
  WriteRegDWORD HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}" "NoRepair"  1
  CreateDirectory "$SMPROGRAMS\\{APP_NAME}"
  CreateShortcut  "$SMPROGRAMS\\{APP_NAME}\\{APP_NAME}.lnk" "$INSTDIR\\{APP_EXE_NAME}.exe"
  CreateShortcut  "$SMPROGRAMS\\{APP_NAME}\\Uninstall.lnk"  "$INSTDIR\\Uninstall.exe"
SectionEnd

Section "Desktop Shortcut" SecDesktop
  CreateShortcut "$DESKTOP\\{APP_NAME}.lnk" "$INSTDIR\\{APP_EXE_NAME}.exe"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${{SecMain}}    "Core application files."
  !insertmacro MUI_DESCRIPTION_TEXT ${{SecDesktop}} "Add a shortcut to your Desktop."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  Delete "$SMPROGRAMS\\{APP_NAME}\\{APP_NAME}.lnk"
  Delete "$SMPROGRAMS\\{APP_NAME}\\Uninstall.lnk"
  RMDir  "$SMPROGRAMS\\{APP_NAME}"
  Delete "$DESKTOP\\{APP_NAME}.lnk"
  Delete "$INSTDIR\\Uninstall.exe"
{uninstall_block}
  DeleteRegKey HKCU "Software\\{APP_NAME}"
  DeleteRegKey HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{APP_NAME}"
SectionEnd
"""
    out_path = root / NSI_FILE
    out_path.write_text(nsi, encoding="utf-8")
    print(f"  ✅ Written to: {out_path}")
    return out_path


def compile_nsi(root, nsi_path):
    step("Compiling installer")
    makensis = shutil.which("makensis")
    for c in [r"C:\Program Files (x86)\NSIS\makensis.exe",
              r"C:\Program Files\NSIS\makensis.exe"]:
        if os.path.exists(c):
            makensis = c
            break
    if not makensis:
        print("  ⚠  makensis not found. Install NSIS: https://nsis.sourceforge.io/Download")
        print(f'  Then run: makensis "{nsi_path}"')
        return
    result = subprocess.run([makensis, str(nsi_path)], cwd=root)
    if result.returncode == 0:
        print(f"  ✅ Installer: {root / OUTPUT_EXE}")
    else:
        print("  ❌ Compilation failed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile",  action="store_true")
    parser.add_argument("--nsi-only", action="store_true")
    args = parser.parse_args()

    root = pathlib.Path(__file__).parent.resolve()

    if args.nsi_only:
        app_dir = root / "dist" / APP_EXE_NAME
        if not app_dir.exists():
            print("❌ Run without --nsi-only first.")
            sys.exit(1)
    else:
        app_dir = build_exe(root)

    nsi_path = build_nsi(root, app_dir)
    if args.compile:
        compile_nsi(root, nsi_path)

    step("Done!")
    print(f"""
Only one dependency needed:
  pip install pyinstaller

Build command:
  python build.py           # exe only
  python build.py --compile # exe + installer

Output: dist\\BidasPCOptimizer\\BidasPCOptimizer.exe
""")


if __name__ == "__main__":
    main()
