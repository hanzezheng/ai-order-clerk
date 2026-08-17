from __future__ import annotations

import json
import socket

from fastapi.testclient import TestClient

from app.api.presence import PROBE, PRESENCE_PORT, PresenceBeacon, presence_doc
from app.bootstrap import build_app_world
from app.main import create_app


def test_presence_http_shape():
    client = TestClient(create_app(build_app_world()))
    res = client.get("/v1/presence")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["service"] == "ai-order-clerk"
    assert "http://127.0.0.1:8000" in body["urls"]


def test_presence_doc_includes_local():
    doc = presence_doc(8000)
    assert doc["urls"][0] == "http://127.0.0.1:8000"


def test_usable_lan_skips_vpn_and_apipa():
    from app.api.presence import _usable_lan

    assert _usable_lan("192.168.2.30") is True
    assert _usable_lan("198.18.0.1") is False
    assert _usable_lan("169.254.1.1") is False
    assert _usable_lan("127.0.0.1") is False


def test_udp_presence_replies():
    beacon = PresenceBeacon(http_port=8000, port=PRESENCE_PORT)
    beacon.start()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    try:
        sock.sendto(PROBE, ("127.0.0.1", PRESENCE_PORT))
        data, _addr = sock.recvfrom(4096)
        payload = json.loads(data.decode("utf-8"))
        assert payload["service"] == "ai-order-clerk"
        assert payload["urls"]
    finally:
        sock.close()
        beacon.stop()
