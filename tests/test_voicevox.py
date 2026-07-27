from unittest.mock import MagicMock, patch

import pytest

from speak_voice.engines.voicevox import VoicevoxEngine


def test_voicevox_is_available():
    engine = VoicevoxEngine()
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert engine.is_available() is True

        import requests

        mock_get.side_effect = requests.RequestException("Connection error")
        assert engine.is_available() is False


def test_voicevox_get_speakers():
    engine = VoicevoxEngine()
    mock_speakers_response = [
        {
            "name": "四国めたん",
            "speaker_uuid": "mock-uuid-metan",
            "styles": [{"name": "あまあま", "id": 0}, {"name": "ツンツン", "id": 2}],
        }
    ]

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_speakers_response

        speakers = engine.get_speakers()
        assert len(speakers) == 2
        assert speakers[0].id == "0"
        assert speakers[0].name == "四国めたん (あまあま)"
        assert speakers[0].raw_info["speakerName"] == "四国めたん"
        assert speakers[0].raw_info["styleName"] == "あまあま"
        assert speakers[1].id == "2"
        assert speakers[1].name == "四国めたん (ツンツン)"


def test_voicevox_synthesize():
    engine = VoicevoxEngine()

    with patch("requests.post") as mock_post:
        # Mocking audio_query
        mock_query_resp = MagicMock()
        mock_query_resp.status_code = 200
        mock_query_resp.json.return_value = {
            "speedScale": 1.0,
            "pitchScale": 0.0,
            "intonationScale": 1.0,
            "volumeScale": 1.0,
        }

        # Mocking synthesis
        mock_synth_resp = MagicMock()
        mock_synth_resp.status_code = 200
        mock_synth_resp.content = b"fake-wav-bytes"

        mock_post.side_effect = [mock_query_resp, mock_synth_resp]

        wav = engine.synthesize_wav("こんにちは", speaker_id="2", speed=1.2, pitch=0.1)
        assert wav == b"fake-wav-bytes"

        # Check configuration logic
        call_args_list = mock_post.call_args_list
        assert len(call_args_list) == 2
        # Check query modulation
        query_payload = call_args_list[1].kwargs["json"]
        assert query_payload["speedScale"] == 1.2
        assert query_payload["pitchScale"] == 0.1
