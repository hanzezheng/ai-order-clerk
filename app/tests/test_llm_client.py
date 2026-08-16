from __future__ import annotations

import json
from email.message import EmailMessage
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from app.agent.llm_client import HttpLlmClient, client_from_env


def _ok_response(content: str) -> MagicMock:
    payload = {"choices": [{"message": {"content": content}}]}
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


def _http_error(code: int, retry_after: str | None = None) -> HTTPError:
    headers = EmailMessage()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError("http://example/v1/chat/completions", code, "err", headers, BytesIO(b"{}"))


def test_retries_429_then_succeeds():
    sleeps: list[float] = []
    client = HttpLlmClient(
        api_key="k",
        base_url="http://example/v1",
        model="m",
        sleep=sleeps.append,
    )
    with patch(
        "app.agent.llm_client.urlopen",
        side_effect=[_http_error(429), _ok_response('{"acts":[]}')],
    ):
        text = client.complete(system="s", user="u")
    assert text == '{"acts":[]}'
    assert sleeps == [1.0]


def test_401_is_not_retried():
    sleeps: list[float] = []
    client = HttpLlmClient(
        api_key="k",
        base_url="http://example/v1",
        model="m",
        retries=3,
        sleep=sleeps.append,
    )
    with patch("app.agent.llm_client.urlopen", side_effect=_http_error(401)):
        try:
            client.complete(system="s", user="u")
        except RuntimeError as exc:
            assert str(exc) == "client_error:http_401"
        else:
            raise AssertionError("401 must fail")
    assert sleeps == []


def test_timeout_exhausted_is_labeled():
    sleeps: list[float] = []
    client = HttpLlmClient(
        api_key="k",
        base_url="http://example/v1",
        model="m",
        retries=2,
        sleep=sleeps.append,
    )
    with patch("app.agent.llm_client.urlopen", side_effect=TimeoutError("timed out")):
        try:
            client.complete(system="s", user="u")
        except RuntimeError as exc:
            assert str(exc) == "client_error:timeout"
        else:
            raise AssertionError("timeout must fail")
    assert sleeps == [1.0, 2.0]


def test_network_error_is_retryable():
    sleeps: list[float] = []
    client = HttpLlmClient(
        api_key="k",
        base_url="http://example/v1",
        model="m",
        retries=1,
        sleep=sleeps.append,
    )
    with patch(
        "app.agent.llm_client.urlopen",
        side_effect=[URLError("connection reset"), _ok_response("ok")],
    ):
        assert client.complete(system="s", user="u") == "ok"
    assert sleeps == [1.0]


def test_client_from_env_reads_timeout_and_retries(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_TIMEOUT", "60")
    monkeypatch.setenv("LLM_RETRIES", "1")
    client = client_from_env()
    assert isinstance(client, HttpLlmClient)
    assert client._timeout == 60.0
    assert client._retries == 1
