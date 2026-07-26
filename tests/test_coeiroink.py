from unittest.mock import MagicMock, patch

import pytest

from speak_voice.engines.coeiroink import CoeiroinkEngine


def test_coeiroink_is_available():
    engine = CoeiroinkEngine()
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert engine.is_available() is True

        import requests

        mock_get.side_effect = requests.RequestException("Connection error")
        assert engine.is_available() is False


def test_coeiroink_get_speakers():
    engine = CoeiroinkEngine()
    mock_speakers_response = [
        {
            "speakerName": "つくよみちゃん",
            "speakerUuid": "tsukuyomi-uuid",
            "styles": [
                {"styleName": "れいむ", "styleId": 0},
            ],
        }
    ]

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_speakers_response

        speakers = engine.get_speakers()
        assert len(speakers) == 1
        assert speakers[0].id == "tsukuyomi-uuid:0"
        assert speakers[0].name == "つくよみちゃん (れいむ)"


def test_coeiroink_synthesize():
    engine = CoeiroinkEngine()

    with patch("requests.post") as mock_post:
        # Mocking audio_query
        mock_query_resp = MagicMock()
        mock_query_resp.status_code = 200
        mock_query_resp.json.return_value = {
            "speedScale": 1.0,
            "volumeScale": 1.0,
        }

        # Mocking synthesis
        mock_synth_resp = MagicMock()
        mock_synth_resp.status_code = 200
        mock_synth_resp.content = b"fake-wav-bytes"

        mock_post.side_effect = [mock_query_resp, mock_synth_resp]

        wav = engine.synthesize_wav("こんにちは", speaker_id="tsukuyomi-uuid:0", speed=1.5)
        assert wav == b"fake-wav-bytes"

        call_args_list = mock_post.call_args_list
        assert len(call_args_list) == 2
        # Check v2 API request format
        synth_payload = call_args_list[1].kwargs["json"]
        assert synth_payload["speakerUuid"] == "tsukuyomi-uuid"
        assert synth_payload["styleId"] == 0
        assert synth_payload["audioQuery"]["speedScale"] == 1.5
