from unittest.mock import MagicMock, patch

import pytest
import requests

from speak_voice.engines.coeiroink import CoeiroinkEngine


def test_coeiroink_is_available():
    engine = CoeiroinkEngine()
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        assert engine.is_available() is True

        import requests

        mock_get.side_effect = requests.RequestException("Connection error")
        assert engine.is_available() is False

    mock_get.assert_called_with("http://127.0.0.1:50032/v1/engine_info", timeout=1.0)


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
        mock_get.assert_called_once_with(
            "http://127.0.0.1:50032/v1/speakers_path_variant", timeout=5.0
        )


def test_coeiroink_get_speakers_falls_back_for_older_engine():
    engine = CoeiroinkEngine()
    path_response = MagicMock(status_code=404)
    speaker_response = MagicMock(status_code=200)
    speaker_response.json.return_value = []

    with patch("requests.get", side_effect=[path_response, speaker_response]) as mock_get:
        assert engine.get_speakers() == []

    assert mock_get.call_args_list[1].args[0].endswith("/v1/speakers")


def test_coeiroink_synthesize():
    engine = CoeiroinkEngine()

    with patch("requests.post") as mock_post:
        mock_synth_resp = MagicMock()
        mock_synth_resp.status_code = 200
        mock_synth_resp.content = b"fake-wav-bytes"
        mock_post.return_value = mock_synth_resp

        wav = engine.synthesize_wav("こんにちは", speaker_id="tsukuyomi-uuid:0", speed=1.5)
        assert wav == b"fake-wav-bytes"

        mock_post.assert_called_once()
        call = mock_post.call_args
        assert call.args[0] == "http://127.0.0.1:50032/v1/synthesis"
        synth_payload = call.kwargs["json"]
        assert synth_payload["speakerUuid"] == "tsukuyomi-uuid"
        assert synth_payload["styleId"] == 0
        assert synth_payload["speedScale"] == 1.5
        assert synth_payload["pitchScale"] == 0.0
        assert synth_payload["intonationScale"] == 1.0
        assert synth_payload["volumeScale"] == 1.0
        assert synth_payload["prePhonemeLength"] == 0.1
        assert synth_payload["postPhonemeLength"] == 0.1
        assert synth_payload["outputSamplingRate"] == 44100
        assert call.kwargs["headers"] == {"Accept": "audio/wav"}
        assert call.kwargs["timeout"] == 60.0


def test_coeiroink_synthesize_reports_validation_detail():
    engine = CoeiroinkEngine()
    response = MagicMock(status_code=422, text="")
    response.raise_for_status.side_effect = requests.HTTPError()
    response.json.return_value = {"detail": [{"msg": "invalid style"}]}

    with patch("requests.post", return_value=response):
        with pytest.raises(RuntimeError, match="invalid style"):
            engine.synthesize_wav("こんにちは", speaker_id="speaker:999")
