from typing import List, Optional

from speak_voice.base import BaseEngine, Speaker


class VoiSonaEngine(BaseEngine):
    """VoiSona Talk engine integration.

    Currently VoiSona Talk does not expose a standard public CLI or HTTP API.
    This class serves as a structured placeholder for future integration or custom integrations.
    """

    @property
    def engine_name(self) -> str:
        return "VoiSona Talk"

    def is_available(self) -> bool:
        # VoiSona Talk has no standard headless API currently.
        return False

    def get_speakers(self) -> List[Speaker]:
        # Return a list of known VoiSona Talk characters as mock/reference
        return [
            Speaker(id="chisato", name="Chisato (さとうささら)", styles=["Normal"]),
            Speaker(id="suzuki", name="Suzuki (すずきつづみ)", styles=["Normal"]),
        ]

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
        raise NotImplementedError(
            "VoiSona Talk does not support direct command-line or API synthesis yet. "
            "Please use the VoiSona Talk Editor GUI."
        )
