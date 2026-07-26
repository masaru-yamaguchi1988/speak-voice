import sys
from typing import List, Optional

from speak_voice.base import BaseEngine, Speaker


class AIVoiceEngine(BaseEngine):
    """A.I.VOICE 2 engine integration.

    Currently supports Windows via COM interface, with placeholder / mock fallback on macOS.
    """

    def __init__(self):
        self._api = None
        self._initialized = False

    @property
    def engine_name(self) -> str:
        return "A.I.VOICE 2"

    def _init_com(self) -> bool:
        if self._initialized:
            return self._api is not None

        self._initialized = True
        if sys.platform != "win32":
            return False

        try:
            import win32com.client

            # A.I.VOICE 2 COM class name is usually 'AI.Talk.Editor.Api.TtsControl' or similar
            # Note: A.I.VOICE 2 uses a newer COM interface structure.
            self._api = win32com.client.Dispatch("AI.Talk.Editor.Api.TtsControl")
            self._api.Initialize()
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        return self._init_com()

    def get_speakers(self) -> List[Speaker]:
        if not self._init_com():
            # Mock / empty list if unavailable
            return []

        try:
            # Fetch voice names from COM interface
            # E.g., self._api.VoiceNames or similar
            names = list(self._api.VoiceNames)
            return [Speaker(id=name, name=name, styles=[]) for name in names]
        except Exception:
            return []

    def synthesize_wav(
        self,
        text: str,
        speaker_id: str,
        speed: Optional[float] = None,
        pitch: Optional[float] = None,
        intonation: Optional[float] = None,
        volume: Optional[float] = None,
        style: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        if not self._init_com():
            raise NotImplementedError(
                "A.I.VOICE 2 integration is only fully supported on Windows via COM API."
            )

        try:
            # Select voice
            self._api.CurrentVoiceName = speaker_id

            # Configure voice parameters
            # COM properties: Speed (0.5 to 4.0), Pitch (0.5 to 2.0), Volume (0.0 to 2.0), Intonation (0.0 to 2.0)
            if speed is not None:
                self._api.Speed = speed
            if pitch is not None:
                self._api.Pitch = pitch
            if intonation is not None:
                self._api.Intonation = intonation
            if volume is not None:
                self._api.Volume = volume

            # Synthesize to raw PCM or wave via temporary file
            # A.I.VOICE COM API typically uses:
            # self._api.SaveWav(text, file_path) or similar
            import os
            import tempfile

            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            try:
                # Some API versions might require:
                # self._api.Text = text
                # self._api.SaveWav(temp_path)
                self._api.SaveWav(text, temp_path)
                with open(temp_path, "rb") as f:
                    return f.read()
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        except Exception as e:
            raise RuntimeError(f"A.I.VOICE 2 Synthesis failed: {e}")
