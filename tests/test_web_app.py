import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from speak_voice.engines import VoicepeakEngine
from speak_voice.web.app import app, get_ollama_models, ollama_http_error, ollama_root_url

client = TestClient(app)


def test_web_app_import_does_not_require_uvicorn():
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "..", "src")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            'import sys; sys.modules["uvicorn"] = None; import speak_voice.web.app',
        ],
        capture_output=True,
        env=env,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_ollama_root_url_accepts_openai_compatible_base_url():
    assert ollama_root_url("http://localhost:11434/v1/") == "http://localhost:11434"


def test_get_ollama_models_returns_installed_model_names():
    response = MagicMock()
    response.json.return_value = {"models": [{"name": "gemma3:latest"}, {"name": "qwen3:8b"}]}
    with patch("speak_voice.web.app.requests.get", return_value=response) as get:
        models = get_ollama_models("http://localhost:11434/v1")

    assert models == ["gemma3:latest", "qwen3:8b"]
    get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5)


def test_ollama_http_error_includes_api_error_detail():
    response = MagicMock(status_code=404, ok=False, text="")
    response.json.return_value = {"error": "model 'qwen2.5' not found"}

    error = ollama_http_error(response)

    assert "model 'qwen2.5' not found" in str(error)


def test_list_engines():
    response = client.get("/api/engines")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("key" in item for item in data)


def test_list_ollama_models_endpoint():
    with patch(
        "speak_voice.web.app.get_ollama_models",
        return_value=["gemma3:latest", "qwen3:8b"],
    ):
        response = client.get(
            "/api/models",
            params={
                "provider": "ollama",
                "base_url": "http://localhost:11434/v1",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"models": ["gemma3:latest", "qwen3:8b"]}


def test_voicevox_engine_settings_match_supported_ranges():
    response = client.get("/api/engine-settings", params={"engine": "voicevox"})

    assert response.status_code == 200
    data = response.json()
    assert [parameter["id"] for parameter in data["parameters"]] == [
        "speed",
        "pitch",
        "intonation",
        "volume",
    ]
    pitch = next(item for item in data["parameters"] if item["id"] == "pitch")
    assert pitch["min"] == -0.15
    assert pitch["max"] == 0.15
    assert data["emotions"] == []


def test_voicepeak_engine_settings_include_speaker_emotions():
    engine = VoicepeakEngine(executable_path="dummy")
    with (
        patch.object(engine, "get_emotions", return_value=["happy", "sad"]),
        patch.dict(
            "speak_voice.web.app.ENGINES",
            {"voicepeak": lambda: engine},
            clear=True,
        ),
    ):
        response = client.get(
            "/api/engine-settings",
            params={"engine": "voicepeak", "speaker": "Female 1"},
        )

    assert response.status_code == 200
    assert response.json()["emotions"] == ["happy", "sad"]


def test_grouped_speaker_option_includes_character_and_style():
    response = client.get("/")

    assert response.status_code == 200
    assert "opt.textContent = `${sp.speaker_name} - ${sp.style_name}`;" in response.text


def test_chat_input_supports_multiline_and_shift_enter_send():
    response = client.get("/")

    assert response.status_code == 200
    assert '<textarea\n          id="chat-input"' in response.text
    assert "Enterで改行・Shift + Enterで送信" in response.text
    assert 'e.key === "Enter" && e.shiftKey && !e.isComposing' in response.text


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
