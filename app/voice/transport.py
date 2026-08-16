from __future__ import annotations

from fastapi.testclient import TestClient


class HttpTurnsTransport:
    """Voice Adapter 只当 HTTP 客户端。不 import Runner / Intake。"""

    def __init__(self, client: TestClient) -> None:
        self._client = client
        self.posts: list[dict] = []

    def create_session(self) -> dict:
        response = self._client.post("/v1/sessions")
        response.raise_for_status()
        return response.json()

    def post_turn(self, session_id: str, payload: dict) -> tuple[int, dict]:
        self.posts.append({"session_id": session_id, **payload})
        response = self._client.post(f"/v1/sessions/{session_id}/turns", json=payload)
        try:
            body = response.json()
        except ValueError:
            body = {"detail": response.text}
        return response.status_code, body
