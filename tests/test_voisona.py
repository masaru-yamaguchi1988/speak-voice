from unittest.mock import MagicMock, patch

import pytest

from speak_voice.engines.voisona import VoiSonaEngine


def make_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    return response


def test_voisona_get_speakers_uses_downloaded_voice_libraries():
    engine = VoiSonaEngine(username="user@example.com", password="api-password")
    voices = {
        "items": [
            {
                "display_names": [
                    {"language": "ja_JP", "name": "田中傘"},
                    {"language": "en_US", "name": "Tanaka San"},
                ],
                "languages": ["ja_JP"],
                "voice_name": "tanaka-san_ja_JP",
                "voice_version": "2.0.0",
            }
        ]
    }

    with patch("speak_voice.engines.voisona.requests.get", return_value=make_response(voices)):
        speakers = engine.get_speakers()

    assert len(speakers) == 1
    assert speakers[0].id == "tanaka-san_ja_JP|2.0.0|ja_JP"
    assert speakers[0].name == "田中傘"
    assert speakers[0].raw_info["version"] == "2.0.0"


def test_voisona_get_styles_uses_voice_specific_order():
    engine = VoiSonaEngine(username="user@example.com", password="api-password")
    detail = {
        "styles": [
            "Normal",
            {"style_name": "Happy"},
            {
                "display_names": [
                    {"language": "ja_JP", "name": "怒り"},
                    {"language": "en_US", "name": "Angry"},
                ]
            },
        ]
    }

    with patch(
        "speak_voice.engines.voisona.requests.get",
        return_value=make_response(detail),
    ) as get:
        styles = engine.get_styles("tanaka-san_ja_JP|2.0.0|ja_JP")

    assert styles == ["Normal", "Happy", "怒り"]
    assert get.call_args.args[0].endswith("/voices/tanaka-san_ja_JP/2.0.0")


def test_voisona_synthesize_saves_wav_and_cleans_request():
    engine = VoiSonaEngine(
        base_url="http://localhost:32766/api/talk/v1/",
        username="user@example.com",
        password="api-password",
    )
    post_response = make_response({"uuid": "request-uuid"})
    status_response = make_response({"state": "succeeded"})
    delete_response = make_response({})

    with (
        patch("speak_voice.engines.voisona.requests.post", return_value=post_response) as post,
        patch("speak_voice.engines.voisona.requests.get", return_value=status_response) as get,
        patch(
            "speak_voice.engines.voisona.requests.delete", return_value=delete_response
        ) as delete,
        patch("builtins.open", create=True) as open_file,
        patch("speak_voice.engines.voisona.os.remove"),
    ):
        open_file.return_value.__enter__.return_value.read.return_value = b"voisona-wav"
        wav = engine.synthesize_wav(
            "こんにちは",
            "tanaka-san_ja_JP|2.0.0|ja_JP",
            speed=1.2,
            pitch=0.1,
            intonation=1.1,
            volume=2.0,
            alp=0.4,
            huskiness=0.3,
            style_weights=[0.25, 0.75],
        )

    assert wav == b"voisona-wav"
    payload = post.call_args.kwargs["json"]
    assert payload["text"] == "こんにちは"
    assert payload["language"] == "ja_JP"
    assert payload["voice_name"] == "tanaka-san_ja_JP"
    assert payload["voice_version"] == "2.0.0"
    assert payload["destination"] == "file"
    assert payload["force_enqueue"] is True
    assert payload["global_parameters"]["speed"] == 1.2
    assert payload["global_parameters"]["pitch"] == 0.1
    assert payload["global_parameters"]["intonation"] == 1.1
    assert payload["global_parameters"]["volume"] == 2.0
    assert payload["global_parameters"]["alp"] == 0.4
    assert payload["global_parameters"]["huskiness"] == 0.3
    assert payload["global_parameters"]["style_weights"] == [0.25, 0.75]
    get.assert_called_once_with(
        "http://localhost:32766/api/talk/v1/speech-syntheses/request-uuid",
        auth=("user@example.com", "api-password"),
        timeout=5.0,
    )
    delete.assert_called_once_with(
        "http://localhost:32766/api/talk/v1/speech-syntheses/request-uuid",
        auth=("user@example.com", "api-password"),
        timeout=5.0,
    )


def test_voisona_maps_named_style_weights_to_api_order():
    engine = VoiSonaEngine(username="user@example.com", password="api-password")

    with patch.object(engine, "get_styles", return_value=["Normal", "Happy", "Angry"]):
        weights = engine._style_weights(
            "voice|1.0.0|ja_JP",
            {"Angry": 0.8, "Happy": 0.25},
        )

    assert weights == [0.0, 0.25, 0.8]


def test_voisona_synthesize_requires_api_credentials():
    engine = VoiSonaEngine(username="", password="")

    with pytest.raises(RuntimeError, match="VOISONA_API_USER"):
        engine.synthesize_wav("こんにちは", "voice|1.0.0|ja_JP")


def test_voisona_synthesize_reports_failed_request():
    engine = VoiSonaEngine(username="user@example.com", password="api-password")

    with (
        patch(
            "speak_voice.engines.voisona.requests.post",
            return_value=make_response({"uuid": "request-uuid"}),
        ),
        patch(
            "speak_voice.engines.voisona.requests.get",
            return_value=make_response({"state": "failed", "message": "invalid voice"}),
        ),
        patch("speak_voice.engines.voisona.requests.delete"),
        patch("speak_voice.engines.voisona.os.remove"),
    ):
        with pytest.raises(RuntimeError, match="invalid voice"):
            engine.synthesize_wav("こんにちは", "voice|1.0.0|ja_JP")
