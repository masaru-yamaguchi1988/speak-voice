import subprocess
from unittest.mock import MagicMock, patch

import pytest

from speak_voice.engines.voicepeak import VoicepeakEngine


def test_voicepeak_is_available():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        assert engine.is_available() is True

        mock_run.side_effect = FileNotFoundError()
        assert engine.is_available() is False


def test_voicepeak_get_speakers():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Narrator List:\n  Male 1\n  Female 1\n"
        speakers = engine.get_speakers()
        assert len(speakers) == 2
        assert speakers[0].id == "Male 1"
        assert speakers[1].id == "Female 1"


def test_voicepeak_synthesize():
    engine = VoicepeakEngine(executable_path="dummy-voicepeak")

    # We mock reading the output wav file by patching open() or mock open
    with (
        patch("subprocess.run") as mock_run,
        patch("builtins.open", create=True) as mock_open,
        patch("os.remove") as mock_remove,
    ):

        mock_file = MagicMock()
        mock_file.read.return_value = b"voicepeak-wav-bytes"
        mock_open.return_value.__enter__.return_value = mock_file

        wav = engine.synthesize_wav("こんにちは", speaker_id="Male 1", speed=1.2, pitch=-0.5)
        assert wav == b"voicepeak-wav-bytes"

        # Verify command arguments passed to subprocess
        called_args = mock_run.call_args[0][0]
        assert "dummy-voicepeak" in called_args
        assert "--say" in called_args
        assert "こんにちは" in called_args
        assert "--narrator" in called_args
        assert "Male 1" in called_args
        assert "--speed" in called_args
        assert "120" in called_args  # 1.2 * 100
        assert "--pitch" in called_args
        assert "-50" in called_args  # -0.5 * 100
