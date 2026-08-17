"""局域网发现。Input 交付层，不进 Parser / Policy / Memory / ERP。"""

from __future__ import annotations

import json
import socket
import threading
from typing import Any

PRESENCE_PORT = 38471
PROBE = b"ai-order-clerk/1?"
SERVICE = "ai-order-clerk"


def _usable_lan(ip: str) -> bool:
    if not ip or ip.startswith("127.") or ip == "0.0.0.0" or ip.startswith("169.254."):
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        first, second = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    if first == 198 and 18 <= second <= 19:
        return False
    return True


def _lan_rank(ip: str) -> tuple[int, int, int]:
    first, second, third, _fourth = (int(part) for part in ip.split("."))
    vmware_like = first == 192 and second == 168 and third in {44, 56, 137, 242}
    if first == 192 and second == 168 and not vmware_like:
        return (0, second, third)
    if first == 10:
        return (1, second, third)
    if first == 172 and 16 <= second <= 31:
        return (2, second, third)
    return (9, first, second)


def lan_ipv4s() -> list[str]:
    found: list[str] = []
    try:
        _host, _aliases, ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in ips:
            if _usable_lan(ip) and ip not in found:
                found.append(ip)
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if _usable_lan(ip) and ip not in found:
                found.append(ip)
    except OSError:
        pass
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        probe.close()
        if _usable_lan(ip) and ip not in found:
            found.append(ip)
    except OSError:
        pass
    found.sort(key=_lan_rank)
    return found


def lan_http_urls(http_port: int) -> list[str]:
    return [f"http://{ip}:{http_port}" for ip in lan_ipv4s()]


def presence_doc(http_port: int) -> dict[str, Any]:
    urls = lan_http_urls(http_port)
    local = f"http://127.0.0.1:{http_port}"
    if local not in urls:
        urls = [local, *urls]
    return {"ok": True, "service": SERVICE, "urls": urls}


def encode_reply(http_port: int) -> bytes:
    return json.dumps(presence_doc(http_port), ensure_ascii=False).encode("utf-8")


class PresenceBeacon:
    def __init__(self, http_port: int, port: int = PRESENCE_PORT) -> None:
        self.http_port = http_port
        self.port = port
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", self.port))
        sock.settimeout(0.4)
        self._sock = sock
        self._thread = threading.Thread(target=self._loop, name="clerk-presence", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        thread = self._thread
        if thread is not None:
            thread.join(timeout=1.5)
        self._thread = None

    def _loop(self) -> None:
        sock = self._sock
        if sock is None:
            return
        reply = encode_reply(self.http_port)
        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(2048)
            except TimeoutError:
                continue
            except OSError:
                return
            if data.strip().startswith(b"ai-order-clerk/1"):
                try:
                    sock.sendto(reply, addr)
                except OSError:
                    return
