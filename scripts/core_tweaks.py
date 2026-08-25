"""
core_tweaks.py – All system tweaks with persistent state backup.
"""

import subprocess
import sys
import ctypes
import winreg
from .state_manager import backup_reg_value, restore_reg_value, powercfg_list

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
    result = subprocess.run(cmd, capture_output=True, text=True,
                            startupinfo=startupinfo, creationflags=creationflags)
    if result.returncode != 0:
        with open("C:\\debug_power.txt", "a") as f:
            f.write(f"COMANDO: {cmd}\nRETORNO: {result.returncode}\nSTDERR: {result.stderr}\n\n")
    return result

# ----------------------------------------------------------------------

def delete_power_scheme(guid):
    """Remove um esquema de energia pelo GUID (se existir e não for o ativo)."""
    run_hidden(["powercfg", "-delete", guid])

def tweak_power():
    backup_reg_value(winreg.HKEY_LOCAL_MACHINE,
                     r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes",
                     "ActivePowerScheme")
    
    original_ultimate_guid = "e9a42b02-d5df-448d-aa00-03f14749eb61"
    existing = powercfg_list()
    
    ultimate_guid = None
    for guid, name in existing.items():
        if "ultimate" in name.lower():
            ultimate_guid = guid
            break
    
    if ultimate_guid:
        run_hidden(["powercfg", "-setactive", ultimate_guid])
    else:
        import time
        from .state_manager import save_custom

        # Guarda a lista de planos ANTES de duplicar
        before = set(powercfg_list().keys())

        # Duplica o plano oculto.
        # Com CREATE_NO_WINDOW o stdout do powercfg vem vazio,
        # por isso detectamos o novo GUID por diferença de listas.
        run_hidden(["powercfg", "-duplicatescheme", original_ultimate_guid])

        # Polling: espera até aparecer um GUID novo na lista (máx. 20 s)
        new_guid = None
        for _ in range(20):
            time.sleep(1)
            after = powercfg_list()
            diff = set(after.keys()) - before
            if diff:
                new_guid = diff.pop()
                break

        if new_guid:
            save_custom("created_ultimate_guid", new_guid)
            run_hidden(["powercfg", "-setactive", new_guid])
        else:
            # Fallback: tenta pelo GUID fixo original
            run_hidden(["powercfg", "-setactive", original_ultimate_guid])
    
    # Restante dos ajustes...
    run_hidden(["powercfg", "-h", "off"])
    run_hidden(["powercfg", "/setACvalueindex", "scheme_current", "SUB_PROCESSOR", "SYSCOOLPOL", "0"])
    run_hidden(["powercfg", "/setACvalueindex", "scheme_current", "sub_processor", "PROCTHROTTLEMIN", "100"])
    run_hidden(["powercfg", "/setACvalueindex", "scheme_current", "sub_processor", "IDLESCALING", "0"])
    run_hidden(["bcdedit", "/set", "hypervisorlaunchtype", "off"])
    print("DONE_POWER")

def revert_power():
    # 1. Restaura o valor do registro (apenas para manter o backup consistente)
    restore_reg_value(winreg.HKEY_LOCAL_MACHINE,
                      r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes",
                      "ActivePowerScheme")
    
    # 2. Ativa o plano Balanced diretamente (GUID universal)
    balanced_guid = "381b4222-f694-41f0-9685-ff5bb260df2e"
    run_hidden(["powercfg", "-setactive", balanced_guid])
    
    # 3. Remove o plano Ultimate que foi criado pelo Apply (se existir)
    from .state_manager import get_custom, clear_custom
    created_guid = get_custom("created_ultimate_guid")
    if created_guid:
        existing = powercfg_list()
        if created_guid.lower() in existing:
            run_hidden(["powercfg", "-delete", created_guid])
        clear_custom("created_ultimate_guid")
    
    # 4. Reativa hibernação e hypervisor
    run_hidden(["powercfg", "-h", "on"])
    run_hidden(["bcdedit", "/set", "hypervisorlaunchtype", "auto"])
    print("DONE_REVERT_POWER")

# ----------------------------------------------------------------------
def open_performance_options():
    """Opens Performance Options window (visual effects)."""
    try:
        subprocess.Popen(["SystemPropertiesPerformance.exe"], shell=False)
    except:
        subprocess.Popen(["rundll32.exe", "shell32.dll,Control_RunDLL", "sysdm.cpl,,3"])
    print("Opened Performance Options window.")

tweak_visuals = open_performance_options
revert_visuals = open_performance_options

# ----------------------------------------------------------------------
def tweak_network():
    backup_reg_value(winreg.HKEY_LOCAL_MACHINE,
                     r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                     "TCPAutotuningLevel")
    
    run_hidden(["netsh", "interface", "tcp", "set", "global", "autotuninglevel=highlyrestricted"])
    run_hidden(["netsh", "interface", "tcp", "set", "global", "rss=enabled"])
    run_hidden(["netsh", "interface", "tcp", "set", "global", "chimney=disabled"])
    run_hidden(["netsh", "int", "tcp", "set", "heuristics", "disabled"])
    run_hidden(["ipconfig", "/flushdns"])
    print("DONE_NETWORK")

def revert_network():
    restore_reg_value(winreg.HKEY_LOCAL_MACHINE,
                      r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters",
                      "TCPAutotuningLevel")
    run_hidden(["netsh", "interface", "tcp", "set", "global", "autotuninglevel=normal"])
    run_hidden(["netsh", "interface", "tcp", "set", "global", "rss=enabled"])
    run_hidden(["netsh", "interface", "tcp", "set", "global", "chimney=enabled"])
    run_hidden(["netsh", "int", "tcp", "set", "heuristics", "enabled"])
    run_hidden(["ipconfig", "/flushdns"])
    print("DONE_REVERT_NETWORK")

# ----------------------------------------------------------------------
def tweak_explorer():
    backup_reg_value(winreg.HKEY_CURRENT_USER,
                     r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                     "LaunchTo")
    backup_reg_value(winreg.HKEY_CURRENT_USER,
                     r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                     "HideFileExt")
    
    run_hidden(["reg", "add", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced", "/v", "LaunchTo", "/t", "REG_DWORD", "/d", "1", "/f"])
    run_hidden(["reg", "add", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced", "/v", "HideFileExt", "/t", "REG_DWORD", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer", "/v", "ShowRecent", "/t", "REG_DWORD", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer", "/v", "ShowFrequent", "/t", "REG_DWORD", "/d", "0", "/f"])
    print("DONE_EXPLORER")

def revert_explorer():
    restore_reg_value(winreg.HKEY_CURRENT_USER,
                      r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                      "LaunchTo")
    restore_reg_value(winreg.HKEY_CURRENT_USER,
                      r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
                      "HideFileExt")
    run_hidden(["reg", "add", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer", "/v", "ShowRecent", "/t", "REG_DWORD", "/d", "1", "/f"])
    run_hidden(["reg", "add", "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer", "/v", "ShowFrequent", "/t", "REG_DWORD", "/d", "1", "/f"])
    print("DONE_REVERT_EXPLORER")

# ----------------------------------------------------------------------
def tweak_mouse():
    backup_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseSpeed")
    backup_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold1")
    backup_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold2")
    backup_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", "MouseTrails")
    
    run_hidden(["reg", "add", "HKCU\\Control Panel\\Mouse", "/v", "MouseSpeed", "/t", "REG_SZ", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKCU\\Control Panel\\Mouse", "/v", "MouseThreshold1", "/t", "REG_SZ", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKCU\\Control Panel\\Mouse", "/v", "MouseThreshold2", "/t", "REG_SZ", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKCU\\Control Panel\\Desktop", "/v", "MouseTrails", "/t", "REG_SZ", "/d", "0", "/f"])
    run_hidden(["rundll32.exe", "USER32.DLL,UpdatePerUserSystemParameters", "1", "True"])
    print("DONE_MOUSE")

def revert_mouse():
    restore_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseSpeed")
    restore_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold1")
    restore_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold2")
    restore_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", "MouseTrails")
    run_hidden(["rundll32.exe", "USER32.DLL,UpdatePerUserSystemParameters", "1", "True"])
    print("DONE_REVERT_MOUSE")

# ----------------------------------------------------------------------
def tweak_gaming():
    backup_reg_value(winreg.HKEY_LOCAL_MACHINE,
                     r"SOFTWARE\Policies\Microsoft\Windows\GameDVR",
                     "AllowGameDVR")
    backup_reg_value(winreg.HKEY_CURRENT_USER,
                     r"System\GameConfigStore",
                     "GameDVR_Enabled")
    backup_reg_value(winreg.HKEY_LOCAL_MACHINE,
                     r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                     "HwSchMode")
    
    games = ["FortniteClient-Win64-Shipping.exe", "GTA5.exe", "FiveM_b2372_GTAProcess.exe",
             "cs2.exe", "RainbowSix.exe", "Warzone.exe", "valorant.exe", "EscapeFromTarkov.exe"]
    for game in games:
        key_path = f"HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Image File Execution Options\\{game}\\PerfOptions"
        run_hidden(["reg", "add", key_path, "/f"])
        run_hidden(["reg", "add", key_path, "/v", "CpuPriorityClass", "/t", "REG_DWORD", "/d", "3", "/f"])
        run_hidden(["reg", "add", key_path, "/v", "IoPriority", "/t", "REG_DWORD", "/d", "3", "/f"])
    run_hidden(["reg", "add", "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\GameDVR", "/v", "AllowGameDVR", "/t", "REG_DWORD", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKCU\\System\\GameConfigStore", "/v", "GameDVR_Enabled", "/t", "REG_DWORD", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers", "/v", "HwSchMode", "/t", "REG_DWORD", "/d", "2", "/f"])
    print("DONE_GAMING")

def revert_gaming():
    restore_reg_value(winreg.HKEY_LOCAL_MACHINE,
                      r"SOFTWARE\Policies\Microsoft\Windows\GameDVR",
                      "AllowGameDVR")
    restore_reg_value(winreg.HKEY_CURRENT_USER,
                      r"System\GameConfigStore",
                      "GameDVR_Enabled")
    restore_reg_value(winreg.HKEY_LOCAL_MACHINE,
                      r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                      "HwSchMode")
    print("DONE_REVERT_GAMING")

# ----------------------------------------------------------------------
def tweak_ram():
    backup_reg_value(winreg.HKEY_LOCAL_MACHINE,
                     r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                     "DisablePagingExecutive")
    backup_reg_value(winreg.HKEY_LOCAL_MACHINE,
                     r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                     "ClearPageFileAtShutdown")
    backup_reg_value(winreg.HKEY_LOCAL_MACHINE,
                     r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                     "LargeSystemCache")
    
    run_hidden(["reg", "add", "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management", "/v", "DisablePagingExecutive", "/t", "REG_DWORD", "/d", "1", "/f"])
    run_hidden(["reg", "add", "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management", "/v", "ClearPageFileAtShutdown", "/t", "REG_DWORD", "/d", "0", "/f"])
    run_hidden(["reg", "add", "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management", "/v", "LargeSystemCache", "/t", "REG_DWORD", "/d", "1", "/f"])
    print("DONE_RAM")

# ----------------------------------------------------------------------
def main():
    if not is_admin():
        print("ERROR: Administrator rights required.")
        sys.exit(1)

    action = sys.argv[sys.argv.index("-Action")+1] if "-Action" in sys.argv else None
    if not action:
        print("Usage: tweaks.py -Action <power|visuals|network|explorer|mouse|gaming|ram|all|revert_...>")
        sys.exit(1)

    actions = {
        "power": tweak_power, "visuals": tweak_visuals, "network": tweak_network,
        "explorer": tweak_explorer, "mouse": tweak_mouse, "gaming": tweak_gaming,
        "ram": tweak_ram,
        "revert_power": revert_power, "revert_visuals": revert_visuals,
        "revert_network": revert_network, "revert_explorer": revert_explorer,
        "revert_mouse": revert_mouse, "revert_gaming": revert_gaming,
        "all": lambda: (tweak_power(), tweak_visuals(), tweak_network(), tweak_ram(), tweak_explorer(), tweak_mouse(), tweak_gaming())
    }
    if action in actions:
        actions[action]()
    else:
        print(f"Unknown action: {action}")

if __name__ == "__main__":
    main()