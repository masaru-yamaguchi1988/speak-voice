import os
import tempfile
import time
from typing import List, Optional

import requests

from speak_voice.base import BaseEngine, Speaker
from speak_voice.voisona_config import get_voisona_config, normalize_local_base_url


class VoiSonaEngine(BaseEngine):
    """VoiSona TalkのローカルREST APIクライアント。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 60.0,
    ):
        configured = get_voisona_config()
        self.base_url = normalize_local_base_url(base_url or configured.base_url) + "/"
        self.username = configured.username if username is None else username
        self.password = configured.password if password is None else password
        self.timeout = timeout

    @property
    def engine_name(self) -> str:
        return "VoiSona Talk"

    @property
    def _auth(self) -> tuple[str, str]:
        return self.username, self.password

    def _has_credentials(self) -> bool:
        return bool(self.username and self.password)

    def _get_voice_libraries(self) -> list[dict]:
        if not self._has_credentials():
            return []
        response = requests.get(
            self.base_url + "voices",
            auth=self._auth,
            timeout=5.0,
        )
        response.raise_for_status()
        return response.json().get("items", [])

    def test_connection(self) -> int:
        """接続とBasic認証を検証し、利用可能なボイスライブラリ数を返す。"""
        if not self._has_credentials():
            raise RuntimeError("VoiSona APIのユーザー名とパスワードを入力してください。")
        return len(self._get_voice_libraries())

    def is_available(self) -> bool:
        try:
            self._get_voice_libraries()
            return self._has_credentials()
        except requests.RequestException:
            return False

    @staticmethod
    def _speaker_id(voice_name: str, voice_version: str, language: str) -> str:
        return "|".join((voice_name, voice_version, language))

    @staticmethod
    def _parse_speaker_id(speaker_id: str) -> tuple[str, str, str]:
        parts = speaker_id.split("|")
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                "VoiSona Talkの話者IDが不正です。list-speakersで取得したIDを指定してください。"
            )
        return parts[0], parts[1], parts[2]

    @staticmethod
    def _display_name(voice: dict, language: str) -> str:
        display_names = voice.get("display_names", [])
        localized = next(
            (
                item.get("name")
                for item in display_names
                if item.get("language") == language and item.get("name")
            ),
            None,
        )
        if localized:
            return localized
        return next(
            (item.get("name") for item in display_names if item.get("name")),
            voice.get("voice_name", "Unknown"),
        )

    def get_speakers(self) -> List[Speaker]:
        try:
            speakers = []
            for voice in self._get_voice_libraries():
                languages = voice.get("languages") or []
                for language in languages:
                    voice_name = voice.get("voice_name")
                    voice_version = voice.get("voice_version")
                    if not voice_name or not voice_version or not language:
                        continue
                    speakers.append(
                        Speaker(
                            id=self._speaker_id(voice_name, voice_version, language),
                            name=self._display_name(voice, language),
                            raw_info={
                                "voiceName": voice_name,
                                "version": voice_version,
                                "language": language,
                            },
                        )
                    )
            return speakers
        except (requests.RequestException, ValueError, TypeError):
            return []

    def _wait_for_synthesis(self, request_id: str) -> None:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            response = requests.get(
                self.base_url + f"speech-syntheses/{request_id}",
                auth=self._auth,
                timeout=5.0,
            )
            response.raise_for_status()
            result = response.json()
            state = result.get("state")
            if state == "succeeded":
                return
            if state not in {"queued", "processing", "running"}:
                detail = result.get("message") or result.get("detail") or state
                raise RuntimeError(f"VoiSona Talkの音声生成に失敗しました: {detail}")
            time.sleep(0.1)
        raise TimeoutError("VoiSona Talkの音声生成がタイムアウトしました。")

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
        if not self._has_credentials():
            raise RuntimeError("VOISONA_API_USERとVOISONA_API_PASSWORDを設定してください。")

        voice_name, voice_version, language = self._parse_speaker_id(speaker_id)
        fd, output_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        request_id = None

        payload = {
            "text": text,
            "language": language,
            "voice_name": voice_name,
            "voice_version": voice_version,
            "force_enqueue": True,
            "destination": "file",
            "output_file_path": os.path.abspath(output_path),
            "can_overwrite_file": True,
            "global_parameters": {
                "alp": 0.0,
                "huskiness": 0.0,
                "intonation": 1.0 if intonation is None else intonation,
                "pitch": 0.0 if pitch is None else pitch,
                "speed": 1.0 if speed is None else speed,
                "style_weights": [],
                "volume": 0.0 if volume is None else volume,
            },
        }

        try:
            response = requests.post(
                self.base_url + "speech-syntheses",
                auth=self._auth,
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()
            request_id = response.json()["uuid"]
            self._wait_for_synthesis(request_id)

            with open(output_path, "rb") as wav_file:
                wav_bytes = wav_file.read()
            if not wav_bytes:
                raise RuntimeError("VoiSona Talkが空の音声ファイルを返しました。")
            return wav_bytes
        finally:
            if request_id:
                try:
                    requests.delete(
                        self.base_url + f"speech-syntheses/{request_id}",
                        auth=self._auth,
                        timeout=5.0,
                    )
                except requests.RequestException:
                    pass
            try:
                os.remove(output_path)
            except OSError:
                pass
