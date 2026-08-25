# Bidas PC Optimizer v2.0
# Architecture: local HTTP server + system browser (Edge/Chrome/Firefox)
# Zero external dependencies — only Python stdlib needed

import sys
import os
import ctypes
import json
import subprocess
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

APP_NAME    = "Bidas PC Optimizer"
APP_VERSION = "2.0"
PORT        = 59821

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

SCRIPTS_DIR = BASE_DIR / "scripts"
UI_FILE     = BASE_DIR / "ui.html"


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_as_admin():
    if getattr(sys, 'frozen', False):
        target = sys.executable
        params = None
    else:
        target = sys.executable
        params = f'"{os.path.abspath(__file__)}"'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", target, params, None, 1)
    sys.exit()


def run_script(script: str, args: list) -> dict:
    path = SCRIPTS_DIR / script
    if not path.exists():
        return {"ok": False, "msg": f"Script not found: {path}"}

    args_str = " ".join(str(a) for a in args) if args else ""
    ps_cmd   = f'& "{path}" {args_str}'
    cmd = [
        "powershell.exe",
        "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-Command", ps_cmd,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        noise = ("Copyright", "All rights reserved", "Install the latest",
                 "aka.ms/PS", "Windows PowerShell")
        lines = (result.stdout + result.stderr).splitlines()
        clean = [l for l in lines if l.strip() and not any(n in l for n in noise)]
        msg   = " | ".join(clean[-6:]).strip() or "Done."
        return {"ok": result.returncode == 0, "msg": msg}
    except subprocess.TimeoutExpired:
        return {"ok": False, "msg": "Timed out after 5 minutes."}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _send_json(self, data: dict, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            content = UI_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/api/info":
            self._send_json({
                "admin": is_admin(),
                "base_dir": str(BASE_DIR),
                "scripts_dir": str(SCRIPTS_DIR),
                "version": APP_VERSION,
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            result = run_script(body.get("script", ""), body.get("args", []))
            self._send_json(result)
        elif self.path == "/api/quit":
            self._send_json({"ok": True})
            threading.Thread(target=lambda: (time.sleep(0.5), os._exit(0))).start()
        else:
            self.send_response(404)
            self.end_headers()


def main():
    if not is_admin():
        run_as_admin()
        return

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = f"http://127.0.0.1:{PORT}/"

    # Try to open in Edge app mode (looks like a proper window, no browser UI)
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    opened = False
    for edge in edge_paths:
        if os.path.exists(edge):
            subprocess.Popen([edge, f"--app={url}", "--window-size=1200,780"])
            opened = True
            break

    if not opened:
        # Fallback: default browser
        webbrowser.open(url)

    # Keep alive until user closes
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
