"""
debloat.py – Remove bloatware apps and register removals for possible future revert.
"""

import subprocess
import winreg as reg
import sys
import ctypes
from .state_manager import backup_appx_package

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_hidden(cmd):
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    creationflags = 0x08000000
    subprocess.run(cmd, capture_output=True, startupinfo=startupinfo, creationflags=creationflags)

def debloat(revert=False):
    if not is_admin():
        print("ERROR: Administrator rights required.")
        return

    bloat_patterns = [
        "*Microsoft.549981C3F5F10*", "*Microsoft.BingWeather*", "*Microsoft.BingNews*",
        "*Microsoft.BingFinance*", "*Microsoft.BingSports*", "*Microsoft.GetHelp*",
        "*Microsoft.Getstarted*", "*Microsoft.Messaging*", "*Microsoft.Microsoft3DViewer*",
        "*Microsoft.MicrosoftSolitaireCollection*", "*Microsoft.MicrosoftStickyNotes*",
        "*Microsoft.MixedReality.Portal*", "*Microsoft.OneConnect*", "*Microsoft.People*",
        "*Microsoft.Print3D*", "*Microsoft.SkypeApp*", "*Microsoft.WindowsAlarms*",
        "*Microsoft.WindowsCamera*", "*microsoft.windowscommunicationsapps*",
        "*Microsoft.WindowsMaps*", "*Microsoft.WindowsFeedbackHub*",
        "*Microsoft.WindowsSoundRecorder*", "*Microsoft.YourPhone*", "*Microsoft.ZuneMusic*",
        "*Microsoft.ZuneVideo*", "*Microsoft.HEIFImageExtension*", "*Microsoft.WebMediaExtensions*",
        "*Microsoft.WebpImageExtension*", "*Microsoft.3dBuilder*", "*Microsoft.PowerAutomateDesktop*",
        "*Microsoft.Todos*", "*Microsoft.GamingApp*", "*Microsoft.Xbox.TCUI*", "*Microsoft.XboxApp*",
        "*Microsoft.XboxGameOverlay*", "*Microsoft.XboxGamingOverlay*", "*Microsoft.XboxIdentityProvider*",
        "*Microsoft.XboxSpeechToTextOverlay*", "*Microsoft.Windows.Ai.Copilot.Provider*",
        "*Microsoft.WindowsFeedback*", "*SpotifyAB.SpotifyMusic*", "*king.com*", "*Disney*",
        "*Netflix*", "*Amazon*", "*Hulu*", "*TikTok*", "*Facebook*", "*Twitter*", "*Instagram*"
    ]

    if revert:
        # Revert is complex (reinstall from Store). We just log.
        print("Reverting debloat is not fully supported. Reinstall apps manually from Microsoft Store if needed.")
        return

    # Remove Appx packages and backup their names
    for pattern in bloat_patterns:
        cmd_find = ["powershell", "-NoProfile", "-Command",
                    f"Get-AppxPackage -Name '{pattern}' -AllUsers | Select-Object -ExpandProperty PackageFullName"]
        result = subprocess.run(cmd_find, capture_output=True, text=True, shell=True)
        if result.stdout:
            for pkg in result.stdout.strip().splitlines():
                backup_appx_package(pkg)
                run_hidden(["powershell", "-NoProfile", "-Command",
                            f"Remove-AppxPackage -Package '{pkg}' -AllUsers -ErrorAction SilentlyContinue"])
        # Remove provisioned packages
        run_hidden(["powershell", "-NoProfile", "-Command",
                    f"Get-AppxProvisionedPackage -Online | Where-Object {{ $_.DisplayName -like '{pattern}' }} | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue"])

    # Disable telemetry (optional, but we also backup registry in core_tweaks)
    try:
        key = reg.OpenKey(reg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", 0, reg.KEY_SET_VALUE)
        reg.SetValueEx(key, "AllowTelemetry", 0, reg.REG_DWORD, 0)
        reg.CloseKey(key)
    except: pass
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Siuf\Rules", 0, reg.KEY_SET_VALUE)
        reg.SetValueEx(key, "NumberOfSIUFInPeriod", 0, reg.REG_DWORD, 0)
        reg.CloseKey(key)
    except: pass
    # Disable Copilot button
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", 0, reg.KEY_SET_VALUE)
        reg.SetValueEx(key, "ShowCopilotButton", 0, reg.REG_DWORD, 0)
        reg.CloseKey(key)
    except: pass

    print("DONE_DEBLOAT")

if __name__ == "__main__":
    revert = "-revert" in sys.argv
    debloat(revert)