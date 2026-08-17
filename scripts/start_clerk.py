"""双击即可打开开单服务。不改 Runtime。"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("CLERK_HTTP_PORT", "8000"))


def _stdio_utf8() -> None:
    if sys.platform != "win32":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        return


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _adb_reverse() -> None:
    try:
        subprocess.run(
            ["adb", "reverse", f"tcp:{PORT}", f"tcp:{PORT}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        return


def _banner() -> None:
    sys.path.insert(0, str(ROOT))
    from app.api.presence import lan_http_urls

    urls = lan_http_urls(PORT)
    print()
    print("  今日开单")
    print(f"  本机    http://127.0.0.1:{PORT}")
    if urls:
        print(f"  局域网  {urls[0]}")
    print("  手机打开「今日开单」，会自动连上这台电脑。")
    print("  电脑和手机要在同一个 Wi-Fi。")
    print("  关掉本窗口即停止。")
    print()


def _open_browser_when_ready() -> None:
    for _ in range(50):
        if _port_open(PORT):
            webbrowser.open(f"http://127.0.0.1:{PORT}/")
            return
        time.sleep(0.12)


def main() -> int:
    _stdio_utf8()
    os.chdir(ROOT)
    os.environ["CLERK_PRESENCE"] = "1"
    os.environ["CLERK_HTTP_PORT"] = str(PORT)
    _adb_reverse()
    if _port_open(PORT):
        _banner()
        print("  服务已经在跑。这个窗口负责让手机找到它。关掉即停止寻找。")
        webbrowser.open(f"http://127.0.0.1:{PORT}/")
        from app.api.presence import PresenceBeacon

        beacon = PresenceBeacon(http_port=PORT)
        try:
            beacon.start()
        except OSError:
            beacon = None
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            if beacon is not None:
                beacon.stop()
        return 0
    _banner()
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
