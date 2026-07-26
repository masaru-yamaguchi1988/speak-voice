from unittest.mock import MagicMock, patch

import pytest

from speak_voice.bridge import SentenceSplitter, VoiceAgentBridge, VoiceBridgeError


def test_sentence_splitter_handles_streamed_japanese_sentences():
    splitter = SentenceSplitter()

    assert splitter.append("こんにちは。次") == ["こんにちは。"]
    assert splitter.append("の文です！残り") == ["次の文です！"]
    assert splitter.flush() == ["残り"]


def test_bridge_raises_synthesis_error_after_queue_finishes():
    engine = MagicMock()
    engine.synthesize_wav.side_effect = RuntimeError("engine unavailable")
    bridge = VoiceAgentBridge(engine, speaker_id="1")

    try:
        bridge.speak("こんにちは")
        with pytest.raises(VoiceBridgeError, match="engine unavailable"):
            bridge.wait_until_done()
    finally:
        bridge.stop()


def test_bridge_raises_when_audio_player_returns_false():
    engine = MagicMock()
    engine.synthesize_wav.return_value = b"wav"
    bridge = VoiceAgentBridge(engine, speaker_id="1")

    with patch("speak_voice.bridge.play_wav", return_value=False):
        try:
            bridge.speak("こんにちは")
            with pytest.raises(VoiceBridgeError, match="再生に失敗"):
                bridge.wait_until_done()
        finally:
            bridge.stop()
