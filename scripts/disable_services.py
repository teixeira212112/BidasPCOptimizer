"""
disable_services.py – Disable or revert Windows services with state backup.
"""

import subprocess
import sys
import ctypes
from .state_manager import backup_service, restore_service

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
        # Imprime o erro (pode ser registrado no log da GUI)
        print(f"ERRO em {' '.join(cmd)}: {result.stderr.strip()}")
    return result

def get_services_matching(pattern):
    """Use PowerShell to get service names matching a wildcard pattern."""
    ps_cmd = f'Get-Service -Name "{pattern}" | Select-Object -ExpandProperty Name'
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def disable_services(revert=False):
    if not is_admin():
        print("ERROR: Administrator rights required.")
        return

    services = [
        "ApxSvc", "PushToInstall", "midisrv", "FrameServerMonitor", "FrameServer",
        "WebClient", "NcaSvc", "NaturalAuthentication", "IKEEXT", "FDResPub",
        "fhsvc", "embeddedmode", "dcsvc", "CertPropSvc", "autotimesvc", "dot3svc",
        "WinRM", "wcncsvc", "SDRSVC", "WiaRpc", "SSDPSRV", "SstpSvc", "RpcLocator",
        "MSiSCSI", "McpManagementService", "lltdsvc", "fdPHost", "EapHost",
        "EntAppSvc", "DmEnrollmentSvc", "wbengine", "AppMgmt", "ALG", "Spooler",
        "PrintNotify", "WFDSConMgrSvc", "SysMain", "bthserv", "BTAGService",
        "RemoteRegistry", "diagsvc", "DPS", "WdiServiceHost", "WdiSystemHost",
        "SessionEnv", "TermService", "UmRdpService", "seclogon", "wisvc",
        "CscService", "AxInstSV", "BthAvctpSvc", "BDESVC", "DiagTrack", "TrkWks",
        "MapsBroker", "SharedAccess", "Netlogon", "PcaSvc", "WpcMonSvc", "WSearch",
        "lmhosts", "StiSvc", "XboxNetApiSvc", "XblGameSave", "XblAuthManager",
        "XboxGipSvc", "icssvc", "WwanSvc", "AssignedAccessManagerSvc", "lfsvc",
        "PhoneSvc", "SensorService", "SCardSvr", "ScDeviceEnum", "SCPolicySvc",
        "WbioSrvc", "WalletService", "QWAVE", "iphlpsvc", "DusmSvc", "DsSvc",
        "WinHttpAutoProxySvc", "BcastDVRUserService_*",
    ]

    expanded_services = []
    for svc in services:
        if '*' in svc:
            expanded_services.extend(get_services_matching(svc))
        else:
            expanded_services.append(svc)

    if revert:
        for svc in expanded_services:
            restore_service(svc)
        print("DONE_REVERT")
        return

    # Disable mode: backup and disable
    for svc in expanded_services:
        backup_service(svc)
        run_hidden(["net", "stop", svc, "/y"])
        run_hidden(["sc", "config", svc, "start=", "disabled"])
    print("DONE_SERVICES")

if __name__ == "__main__":
    revert = "-revert" in sys.argv or "--revert" in sys.argv
    disable_services(revert)