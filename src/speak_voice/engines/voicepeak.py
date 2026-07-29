import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from typing import List, Optional

from speak_voice.base import BaseEngine, Speaker
from speak_voice.text_utils import has_speakable_text
from speak_voice.voicepeak_diagnostics import record_voicepeak_event


class VoicepeakEngine(BaseEngine):
    """VOICEPEAK公式CLIを安定して利用するためのエンジンラッパー。"""

    max_text_length = 140
    _cli_lock = threading.Lock()
    _last_cli_finished = 0.0
    _speaker_cache: tuple[float, list[Speaker]] = (0.0, [])
    _emotion_cache: dict[str, tuple[float, list[str]]] = {}

    def __init__(self, executable_path: Optional[str] = None):
        if executable_path:
            self.executable_path = executable_path
        elif sys.platform == "darwin":
            self.executable_path = "/Applications/voicepeak.app/Contents/MacOS/voicepeak"
        elif sys.platform == "win32":
            self.executable_path = r"C:\Program Files\Voicepeak\voicepeak.exe"
        else:
            self.executable_path = "voicepeak"

        env_path = os.environ.get("VOICEPEAK_PATH")
        if env_path:
            self.executable_path = env_path

        self.synthesis_attempts = self._positive_int_env("VOICEPEAK_RETRY_ATTEMPTS", 4)
        self.cooldown_seconds = self._positive_float_env("VOICEPEAK_COOLDOWN_SECONDS", 1.0)

    @staticmethod
    def _positive_int_env(name: str, default: int) -> int:
        try:
            return max(1, int(os.environ.get(name, default)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _positive_float_env(name: str, default: float) -> float:
        try:
            return max(0.0, float(os.environ.get(name, default)))
        except (TypeError, ValueError):
            return default

    @property
    def engine_name(self) -> str:
        return "Voicepeak"

    def is_available(self) -> bool:
        """起動確認のためだけにCLIを実行せず、実行ファイルの存在で判定する。"""
        if os.path.isabs(self.executable_path):
            return os.path.isfile(self.executable_path) and os.access(self.executable_path, os.X_OK)
        return shutil.which(self.executable_path) is not None

    def _wait_for_cooldown(self) -> float:
        elapsed = time.monotonic() - type(self)._last_cli_finished
        wait_seconds = max(0.0, self.cooldown_seconds - elapsed)
        if wait_seconds:
            time.sleep(wait_seconds)
        return wait_seconds

    def _mark_cli_finished(self) -> None:
        type(self)._last_cli_finished = time.monotonic()

    def get_speakers(self) -> List[Speaker]:
        if not self.is_available():
            return []
        cached_at, cached_speakers = type(self)._speaker_cache
        if cached_at and time.monotonic() - cached_at < 60.0:
            return list(cached_speakers)

        try:
            with self._cli_lock:
                self._wait_for_cooldown()
                try:
                    result = subprocess.run(
                        [self.executable_path, "--list-narrator"],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=10.0,
                    )
                finally:
                    self._mark_cli_finished()
            speakers = [
                Speaker(id=line, name=line, styles=[])
                for raw_line in result.stdout.splitlines()
                if (line := raw_line.strip()) and not line.startswith("Narrator List:")
            ]
            type(self)._speaker_cache = (time.monotonic(), speakers)
            return list(speakers)
        except (subprocess.SubprocessError, FileNotFoundError) as error:
            record_voicepeak_event(
                "warning",
                "speaker_list_failed",
                error_type=type(error).__name__,
            )
            return []

    def get_emotions(self, speaker_id: str) -> List[str]:
        cached_at, cached_emotions = type(self)._emotion_cache.get(speaker_id, (0.0, []))
        if cached_at and time.monotonic() - cached_at < 300.0:
            return list(cached_emotions)

        try:
            with self._cli_lock:
                self._wait_for_cooldown()
                try:
                    result = subprocess.run(
                        [self.executable_path, "--list-emotion", speaker_id],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=10.0,
                    )
                finally:
                    self._mark_cli_finished()
            emotions = [
                name
                for raw_line in result.stdout.splitlines()
                if (name := raw_line.strip()) and not name.startswith("Emotion List:")
            ]
            type(self)._emotion_cache[speaker_id] = (time.monotonic(), emotions)
            return list(emotions)
        except (subprocess.SubprocessError, FileNotFoundError) as error:
            record_voicepeak_event(
                "warning",
                "emotion_list_failed",
                speaker=speaker_id,
                error_type=type(error).__name__,
            )
            return []

    @staticmethod
    def _safe_stderr(error: Exception, text: str) -> str:
        stderr = getattr(error, "stderr", b"") or b""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        message = str(stderr).strip().replace(text, "[本文]")
        return message[-500:] if message else ""

    @staticmethod
    def _error_kind(error: Exception) -> str:
        if isinstance(error, subprocess.TimeoutExpired):
            return "timeout"
        if isinstance(error, subprocess.CalledProcessError):
            return "process_exit"
        if isinstance(error, OSError):
            return "io_error"
        return "invalid_output"

    @staticmethod
    def _is_valid_wav(wav_bytes: bytes) -> bool:
        return (
            len(wav_bytes) >= 12
            and wav_bytes[:4] in {b"RIFF", b"RIFX"}
            and wav_bytes[8:12] == b"WAVE"
        )

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
        if not has_speakable_text(text):
            raise ValueError("VOICEPEAKで読み上げ可能な文字が含まれていません。")

        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        request_id = uuid.uuid4().hex[:10]

        cmd = [
            self.executable_path,
            "--say",
            text,
            "--narrator",
            speaker_id,
            "--out",
            temp_path,
        ]
        if speed is not None:
            cmd.extend(["--speed", str(int(speed * 100))])
        if pitch is not None:
            cmd.extend(["--pitch", str(int(pitch * 100))])
        if volume is not None:
            cmd.extend(["--volume", str(int(volume * 100))])
        if style:
            cmd.extend(["--emotion", style])
        elif "emotion" in kwargs:
            cmd.extend(["--emotion", kwargs["emotion"]])

        timeout = max(30.0, min(120.0, len(text) * 0.4))
        last_error: Optional[Exception] = None
        record_voicepeak_event(
            "info",
            "synthesis_started",
            request_id=request_id,
            text_length=len(text),
            speaker=speaker_id,
            timeout_seconds=timeout,
            max_attempts=self.synthesis_attempts,
        )

        try:
            with self._cli_lock:
                for attempt in range(1, self.synthesis_attempts + 1):
                    cooldown_wait = self._wait_for_cooldown()
                    started_at = time.monotonic()
                    retry_delay = 0.0
                    try:
                        os.truncate(temp_path, 0)
                        subprocess.run(
                            cmd,
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=timeout,
                        )
                        with open(temp_path, "rb") as wav_file:
                            wav_bytes = wav_file.read()
                        if not self._is_valid_wav(wav_bytes):
                            raise RuntimeError("VOICEPEAKが不正なWAVデータを返しました。")

                        duration = round(time.monotonic() - started_at, 3)
                        record_voicepeak_event(
                            "info",
                            "synthesis_succeeded",
                            request_id=request_id,
                            attempt=attempt,
                            duration_seconds=duration,
                            cooldown_wait_seconds=round(cooldown_wait, 3),
                            wav_bytes=len(wav_bytes),
                        )
                        return wav_bytes
                    except (
                        subprocess.CalledProcessError,
                        subprocess.TimeoutExpired,
                        OSError,
                        RuntimeError,
                    ) as error:
                        last_error = error
                        duration = round(time.monotonic() - started_at, 3)
                        exit_code = (
                            error.returncode
                            if isinstance(error, subprocess.CalledProcessError)
                            else None
                        )
                        record_voicepeak_event(
                            "warning",
                            "synthesis_attempt_failed",
                            request_id=request_id,
                            attempt=attempt,
                            duration_seconds=duration,
                            error_kind=self._error_kind(error),
                            error_type=type(error).__name__,
                            exit_code=exit_code,
                            stderr=self._safe_stderr(error, text),
                        )
                        if attempt < self.synthesis_attempts:
                            # 短時間の連続再起動を避け、1秒、2秒、4秒…と待機する。
                            retry_delay = min(8.0, 2 ** (attempt - 1))
                    finally:
                        self._mark_cli_finished()
                    if retry_delay:
                        time.sleep(retry_delay)

            record_voicepeak_event(
                "error",
                "synthesis_failed",
                request_id=request_id,
                attempts=self.synthesis_attempts,
                last_error_kind=self._error_kind(last_error) if last_error else None,
            )
            raise RuntimeError(
                f"VOICEPEAKの音声生成が{self.synthesis_attempts}回連続で失敗しました。"
                f"診断ID: {request_id}"
            ) from last_error
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
