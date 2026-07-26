import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from speak_voice.web.app import app

client = TestClient(app)


def test_list_engines():
    response = client.get("/api/engines")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("key" in item for item in data)


def test_hook_speak_validation():
    # 不正なエンジンキーでのテスト
    payload = {
        "engine": "invalid_engine_name",
        "speaker": "1",
        "text": "テストテキスト",
    }
    response = client.post("/api/hook/speak", json=payload)
    assert response.status_code == 400
    assert "Unknown engine" in response.json()["detail"]


def test_hook_allows_bookmarklet_cors_request():
    response = client.options(
        "/api/hook/speak",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_speak_wait_reports_worker_failure():
    payload = {
        "engine": "voicevox",
        "speaker": "1",
        "text": "テスト",
        "wait": True,
    }
    engine = MagicMock()
    engine.synthesize_wav.side_effect = RuntimeError("synthesis failed")

    with patch.dict("speak_voice.web.app.ENGINES", {"voicevox": lambda: engine}, clear=True):
        response = client.post("/api/speak", json=payload)

    assert response.status_code == 500
    assert "synthesis failed" in response.json()["detail"]


def test_speak_without_wait_returns_queued_status():
    payload = {
        "engine": "voicevox",
        "speaker": "1",
        "text": "テスト",
        "wait": False,
    }
    response = client.post("/api/speak", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "queued", "queued": True, "completed": False}


def test_chat_mock_streams_text_and_done_event():
    payload = {
        "engine": "voicevox",
        "speaker": "1",
        "prompt": "こんにちは",
        "api_provider": "mock",
    }
    with (
        patch("speak_voice.web.app.VoiceAgentBridge") as bridge_cls,
        patch("time.sleep"),
    ):
        bridge = bridge_cls.return_value
        bridge.speak_stream.side_effect = lambda chunks: list(chunks)
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1] == {"type": "done"}
    assert "こんにちは！" in "".join(event["text"] for event in events if event["type"] == "text")
    bridge.wait_until_done.assert_called_once()
