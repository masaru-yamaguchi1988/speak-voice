import subprocess
from unittest.mock import MagicMock, patch

import pytest

from speak_voice.engines.voicepeak import VoicepeakEngine
from speak_voice.voicepeak_diagnostics import get_voicepeak_events

VALID_WAV = b"RIFF\x10\x00\x00\x00WAVEfmt "


@pytest.fixture(autouse=True)
def reset_voicepeak_shared_state():
    VoicepeakEngine._last_cli_finished = 0.0
    VoicepeakEngine._speaker_cache = (0.0, [])
    VoicepeakEngine._emotion_cache = {}


def test_voicepeak_is_available():
    absolute_engine = VoicepeakEngine(executable_path="/dummy/voicepeak")
    path_engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    with (
        patch("speak_voice.engines.voicepeak.os.path.isfile", return_value=True),
        patch("speak_voice.engines.voicepeak.os.access", return_value=True),
    ):
        assert absolute_engine.is_available() is True

    with patch("speak_voice.engines.voicepeak.shutil.which") as which:
        which.return_value = "/usr/local/bin/dummy-voicepeak"
        assert path_engine.is_available() is True

        which.return_value = None
        assert path_engine.is_available() is False


def test_voicepeak_does_not_launch_cli_for_symbols_only():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")

    with patch("speak_voice.engines.voicepeak.subprocess.run") as run:
        with pytest.raises(ValueError, match="読み上げ可能な文字"):
            engine.synthesize_wav(":", speaker_id="Male 1")

    run.assert_not_called()


def test_voicepeak_get_emotions():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    engine.cooldown_seconds = 0
    with patch("speak_voice.engines.voicepeak.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Emotion List:\nhappy\nsad\n"

        assert engine.get_emotions("Female 1") == ["happy", "sad"]
        mock_run.assert_called_once_with(
            ["dummy-voicepeak", "--list-emotion", "Female 1"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,
        )


def test_voicepeak_get_speakers():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    engine.cooldown_seconds = 0
    with (
        patch.object(engine, "is_available", return_value=True),
        patch("speak_voice.engines.voicepeak.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Narrator List:\n  Male 1\n  Female 1\n",
        )
        speakers = engine.get_speakers()
        assert len(speakers) == 2
        assert speakers[0].id == "Male 1"
        assert speakers[1].id == "Female 1"


def test_voicepeak_synthesize():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    engine.cooldown_seconds = 0

    with (
        patch("speak_voice.engines.voicepeak.subprocess.run") as mock_run,
        patch("builtins.open", create=True) as mock_open,
        patch("os.remove"),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = VALID_WAV

        wav = engine.synthesize_wav(
            "こんにちは",
            speaker_id="Male 1",
            speed=1.2,
            pitch=-0.5,
        )
        assert wav == VALID_WAV

        called_args = mock_run.call_args[0][0]
        assert "dummy-voicepeak" in called_args
        assert "--say" in called_args
        assert "こんにちは" in called_args
        assert "--narrator" in called_args
        assert "Male 1" in called_args
        assert "--speed" in called_args
        assert "120" in called_args
        assert "--pitch" in called_args
        assert "-50" in called_args


def test_voicepeak_synthesize_retries_temporary_cli_failure():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    engine.cooldown_seconds = 0

    with (
        patch(
            "speak_voice.engines.voicepeak.subprocess.run",
            side_effect=[
                subprocess.CalledProcessError(1, ["dummy-voicepeak"]),
                MagicMock(),
            ],
        ) as mock_run,
        patch("builtins.open", create=True) as mock_open,
        patch("os.remove"),
        patch("time.sleep") as mock_sleep,
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = VALID_WAV

        wav = engine.synthesize_wav("こんにちは", speaker_id="Male 1")

    assert wav == VALID_WAV
    assert mock_run.call_count == 2
    mock_sleep.assert_called_once_with(1)


def test_voicepeak_synthesize_reports_repeated_cli_failure():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    engine.cooldown_seconds = 0
    engine.synthesis_attempts = 3

    with (
        patch(
            "speak_voice.engines.voicepeak.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["dummy-voicepeak"]),
        ) as mock_run,
        patch("os.remove"),
        patch("time.sleep"),
    ):
        with pytest.raises(RuntimeError, match="3回連続で失敗"):
            engine.synthesize_wav("こんにちは", speaker_id="Male 1")

    assert mock_run.call_count == 3


def test_voicepeak_diagnostics_do_not_keep_spoken_text():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    engine.cooldown_seconds = 0
    engine.synthesis_attempts = 1
    spoken_text = "ログに残してはいけない本文"
    error = subprocess.CalledProcessError(
        134,
        ["dummy-voicepeak"],
        stderr=f"aborted: {spoken_text}".encode(),
    )

    with (
        patch(
            "speak_voice.engines.voicepeak.subprocess.run",
            side_effect=error,
        ),
        patch("os.remove"),
    ):
        with pytest.raises(RuntimeError):
            engine.synthesize_wav(spoken_text, speaker_id="Male 1")

    event = get_voicepeak_events(2)[0]
    assert event["event"] == "synthesis_attempt_failed"
    assert event["exit_code"] == 134
    assert spoken_text not in event["stderr"]
    assert "[本文]" in event["stderr"]


def test_voicepeak_rejects_truncated_wav_and_retries():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    engine.cooldown_seconds = 0
    engine.synthesis_attempts = 2

    with (
        patch("speak_voice.engines.voicepeak.subprocess.run") as mock_run,
        patch("builtins.open", create=True) as mock_open,
        patch("os.remove"),
        patch("time.sleep"),
    ):
        mock_open.return_value.__enter__.return_value.read.side_effect = [
            b"not-a-wav",
            VALID_WAV,
        ]
        wav = engine.synthesize_wav("こんにちは", speaker_id="Male 1")

    assert wav == VALID_WAV
    assert mock_run.call_count == 2
