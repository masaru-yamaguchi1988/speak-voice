import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from speak_voice.engines import VoicepeakEngine, VoiSonaEngine
from speak_voice.voisona_config import VoiSonaConfig
from speak_voice.web.app import (
    ChatRequest,
    app,
    build_chat_messages,
    build_gemini_prompt,
    get_ollama_models,
    get_ollama_thinking_models,
    ollama_http_error,
    ollama_root_url,
)

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


def test_get_ollama_thinking_models_uses_model_capabilities():
    thinking = MagicMock()
    thinking.json.return_value = {"capabilities": ["completion", "thinking"]}
    normal = MagicMock()
    normal.json.return_value = {"capabilities": ["completion"]}
    with patch("speak_voice.web.app.requests.post", side_effect=[thinking, normal]) as post:
        models = get_ollama_thinking_models(
            "http://localhost:11434/v1",
            ["qwen3:8b", "gemma3:4b"],
        )

    assert models == ["qwen3:8b"]
    assert [call.kwargs["json"] for call in post.call_args_list] == [
        {"model": "qwen3:8b"},
        {"model": "gemma3:4b"},
    ]


def test_get_ollama_thinking_models_excludes_level_only_gpt_oss():
    response = MagicMock()
    response.json.return_value = {
        "capabilities": ["completion", "thinking"],
        "details": {"family": "gptoss"},
    }
    with patch("speak_voice.web.app.requests.post", return_value=response):
        models = get_ollama_thinking_models(
            "http://localhost:11434/v1",
            ["gpt-oss:20b"],
        )

    assert models == []


def test_ollama_http_error_includes_api_error_detail():
    response = MagicMock(status_code=404, ok=False, text="")
    response.json.return_value = {"error": "model 'qwen2.5' not found"}

    error = ollama_http_error(response)

    assert "model 'qwen2.5' not found" in str(error)


def test_chat_messages_include_system_prompt_history_and_current_prompt():
    request = ChatRequest(
        engine="voicevox",
        speaker="1",
        prompt="続けて",
        system_prompt="簡潔に答える",
        messages=[
            {"role": "user", "content": "最初の質問"},
            {"role": "assistant", "content": "最初の回答"},
        ],
        api_provider="mock",
    )

    assert build_chat_messages(request) == [
        {"role": "system", "content": "簡潔に答える"},
        {"role": "user", "content": "最初の質問"},
        {"role": "assistant", "content": "最初の回答"},
        {"role": "user", "content": "続けて"},
    ]


def test_gemini_prompt_keeps_conversation_roles():
    prompt = build_gemini_prompt(
        [
            {"role": "system", "content": "短く答える"},
            {"role": "user", "content": "質問"},
            {"role": "assistant", "content": "回答"},
        ]
    )

    assert "固定指示:\n短く答える" in prompt
    assert "ユーザー:\n質問" in prompt
    assert "アシスタント:\n回答" in prompt


def test_list_engines():
    response = client.get("/api/engines")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any("key" in item for item in data)


def test_voicepeak_diagnostics_endpoint():
    events = [{"event": "synthesis_attempt_failed", "request_id": "abc123"}]
    with (
        patch("speak_voice.web.app.get_voicepeak_events", return_value=events) as get,
        patch(
            "speak_voice.web.app.voicepeak_log_path",
            return_value="/tmp/voicepeak.log",
        ),
    ):
        response = client.get("/api/diagnostics/voicepeak", params={"limit": 10})

    assert response.status_code == 200
    assert response.json() == {
        "events": events,
        "log_file": "/tmp/voicepeak.log",
    }
    get.assert_called_once_with(10)


def test_list_ollama_models_endpoint():
    with (
        patch(
            "speak_voice.web.app.get_ollama_models",
            return_value=["gemma3:latest", "qwen3:8b"],
        ),
        patch(
            "speak_voice.web.app.get_ollama_thinking_models",
            return_value=["qwen3:8b"],
        ),
    ):
        response = client.get(
            "/api/models",
            params={
                "provider": "ollama",
                "base_url": "http://localhost:11434/v1",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "models": ["gemma3:latest", "qwen3:8b"],
        "thinking_models": ["qwen3:8b"],
    }


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


def test_voisona_engine_settings_match_global_parameters():
    response = client.get("/api/engine-settings", params={"engine": "voisona"})

    assert response.status_code == 200
    data = response.json()
    assert [parameter["id"] for parameter in data["parameters"]] == [
        "speed",
        "pitch",
        "intonation",
        "volume",
        "alp",
        "huskiness",
    ]
    volume = next(item for item in data["parameters"] if item["id"] == "volume")
    assert volume["default"] == 0.0
    huskiness = next(item for item in data["parameters"] if item["id"] == "huskiness")
    assert huskiness["min"] == 0.0
    assert huskiness["max"] == 1.0


def test_voisona_engine_settings_include_voice_specific_styles():
    engine = MagicMock(spec=VoiSonaEngine)
    engine.get_styles.return_value = ["Normal", "Happy", "Angry"]
    with patch.dict(
        "speak_voice.web.app.ENGINES",
        {"voisona": lambda: engine},
        clear=True,
    ):
        response = client.get(
            "/api/engine-settings",
            params={"engine": "voisona", "speaker": "voice|1.0.0|ja_JP"},
        )

    assert response.status_code == 200
    assert response.json()["styles"] == ["Normal", "Happy", "Angry"]


def test_voisona_config_update_tests_connection_without_exposing_password():
    existing = VoiSonaConfig()
    saved = VoiSonaConfig(
        username="user@example.com",
        password="api-password",
        source="session",
    )
    with (
        patch("speak_voice.web.app.get_voisona_config", return_value=existing),
        patch(
            "speak_voice.web.app.VoiSonaEngine.test_connection",
            return_value=2,
        ),
        patch(
            "speak_voice.web.app.set_voisona_config",
            return_value=saved,
        ) as save,
    ):
        response = client.put(
            "/api/engine-config/voisona",
            json={
                "base_url": "http://127.0.0.1:32766/api/talk/v1",
                "username": "user@example.com",
                "password": "api-password",
                "remember": False,
            },
        )

    assert response.status_code == 200
    assert response.json()["voice_count"] == 2
    assert response.json()["password_configured"] is True
    assert "password" not in response.json()
    save.assert_called_once()


def test_voisona_config_rejects_external_api_url():
    response = client.post(
        "/api/engine-config/voisona/test",
        json={
            "base_url": "https://example.com/api/talk/v1",
            "username": "user@example.com",
            "password": "api-password",
        },
    )

    assert response.status_code == 400
    assert "localhost" in response.json()["detail"]


def test_voisona_config_rejects_cross_origin_access():
    response = client.get(
        "/api/engine-config/voisona",
        headers={"Origin": "https://example.com"},
    )

    assert response.status_code == 403


def test_web_console_contains_voisona_connection_form():
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="voisona-config-card"' in response.text
    assert "この端末の資格情報ストアに保存する" in response.text
    assert "/api/engine-config/voisona/test" in response.text


def test_web_console_contains_voicepeak_diagnostics():
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="voicepeak-diagnostics-card"' in response.text
    assert "/api/diagnostics/voicepeak?limit=30" in response.text
    assert "読み上げ本文は保存しません" in response.text


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


def test_web_console_builds_voice_specific_style_sliders():
    response = client.get("/")

    assert response.status_code == 200
    assert "input.dataset.styleWeight = styleName;" in response.text
    assert 'document.querySelectorAll("[data-style-weight]")' in response.text
    assert "params.style_weights[input.dataset.styleWeight]" in response.text


def test_chat_input_supports_multiline_and_shift_enter_send():
    response = client.get("/")

    assert response.status_code == 200
    assert '<textarea\n          id="chat-input"' in response.text
    assert "Enterで改行・Shift + Enterで送信" in response.text
    assert 'e.key === "Enter" && e.shiftKey && !e.isComposing' in response.text


def test_web_console_contains_prompt_history_and_message_actions():
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="system-prompt-input"' in response.text
    assert 'id="conversation-select"' in response.text
    assert 'indexedDB.open("speak-voice-chat", 1)' in response.text
    assert '["copy", "コピー"]' in response.text
    assert '["regenerate", "再生成"]' in response.text
    assert 'id="auto-speak-response"' in response.text


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


def test_speak_rejects_symbols_only_before_queueing():
    response = client.post(
        "/api/speak",
        json={
            "engine": "voicepeak",
            "speaker": "Miyamai Moca",
            "text": ": ** 😊",
            "wait": False,
        },
    )

    assert response.status_code == 400
    assert "読み上げ可能な文字" in response.json()["detail"]


def test_speak_can_sanitize_markdown_for_replay():
    payload = {
        "engine": "voicevox",
        "speaker": "1",
        "text": "**説明** https://example.com",
        "sanitize_for_speech": True,
        "wait": False,
    }
    with patch("speak_voice.web.app.speak_queue.put") as put:
        response = client.post("/api/speak", json=payload)

    assert response.status_code == 200
    queued = put.call_args.args[0]
    assert queued[2] == "説明 URL"


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


def test_chat_can_generate_without_initializing_voice_bridge():
    payload = {
        "engine": "voicevox",
        "speaker": "",
        "prompt": "音声なし",
        "api_provider": "mock",
        "auto_speak": False,
    }
    with (
        patch("speak_voice.web.app.VoiceAgentBridge") as bridge_cls,
        patch("time.sleep"),
    ):
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    assert "音声なし" in response.text
    bridge_cls.assert_not_called()


def test_ollama_chat_can_disable_thinking_with_native_api():
    ollama_response = MagicMock(ok=True)
    ollama_response.iter_lines.return_value = [
        '{"message":{"content":"短い回答"},"done":false}'.encode(),
        b'{"message":{"content":""},"done":true}',
    ]
    payload = {
        "engine": "voicevox",
        "speaker": "",
        "prompt": "簡潔に答えて",
        "api_provider": "ollama",
        "base_url": "http://localhost:11434/v1",
        "model_name": "qwen3:8b",
        "disable_thinking": True,
        "auto_speak": False,
    }
    with patch("speak_voice.web.app.requests.post", return_value=ollama_response) as post:
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 200
    assert "短い回答" in response.text
    assert post.call_args.args[0] == "http://localhost:11434/api/chat"
    assert post.call_args.kwargs["json"]["think"] is False


def test_web_console_has_model_specific_thinking_control():
    response = client.get("/")

    assert response.status_code == 200
    assert 'id="disable-thinking"' in response.text
    assert "thinkingModels.has(modelSelect.value)" in response.text
    assert "disable_thinking: disableThinking.checked" in response.text
