"""
clear_ram.py – Clear Windows standby RAM cache using EmptyStandbyList.exe
"""

import subprocess
import sys
import ctypes
from pathlib import Path

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_base_dir():
    """Retorna a pasta onde está o executável (ou script em desenvolvimento)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent

def clear_ram_cache() -> bool:
    if not is_admin():
        print("Requer administrador.")
        return False

    base_dir = get_base_dir()
    exe_path = base_dir / "helpers" / "EmptyStandbyList.exe"

    if not exe_path.exists():
        print(f"EmptyStandbyList.exe não encontrado em: {exe_path}")
        return False

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    creationflags = 0x08000000  # CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            [str(exe_path), "standbylist"],
            capture_output=True,
            startupinfo=startupinfo,
            creationflags=creationflags
        )
        if result.returncode == 0:
            print("✅ Standby list limpa com sucesso")
            return True
        else:
            print(f"Erro: {result.returncode}")
            return False
    except Exception as e:
        print(f"Erro: {e}")
        return False

if __name__ == "__main__":
    if clear_ram_cache():
        print("Limpeza de RAM concluída.")
    else:
        print("Falha.")