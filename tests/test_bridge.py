import threading
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


def test_bridge_cancel_stops_current_audio_and_discards_queue():
    engine = MagicMock()
    engine.synthesize_wav.return_value = b"wav"
    bridge = VoiceAgentBridge(engine, speaker_id="1")
    playback_started = threading.Event()

    def cancellable_playback(wav_bytes, stop_event):
        playback_started.set()
        stop_event.wait(1)
        return False

    with patch("speak_voice.bridge.play_wav", side_effect=cancellable_playback):
        bridge.speak("最初の文章")
        bridge.speak("未再生の文章")
        assert playback_started.wait(1)
        bridge.cancel()
        bridge.wait_until_done()
        bridge.stop()

    engine.synthesize_wav.assert_called_once()


def test_bridge_splits_text_to_engine_character_limit():
    engine = MagicMock()
    engine.max_text_length = 5
    engine.synthesize_wav.return_value = b"wav"
    bridge = VoiceAgentBridge(engine, speaker_id="1")

    with patch("speak_voice.bridge.play_wav", return_value=True):
        try:
            bridge.speak("12345678901")
            bridge.wait_until_done()
        finally:
            bridge.stop()

    texts = [call.kwargs["text"] for call in engine.synthesize_wav.call_args_list]
    assert texts == ["12345", "67890", "1"]
