import os
import subprocess
import sys
import tempfile
import threading
import time
from typing import List, Optional

from speak_voice.base import BaseEngine, Speaker


class VoicepeakEngine(BaseEngine):
    """Voicepeak engine wrapper running the official CLI executable."""

    # 公式CLIのセリフ入力上限。
    max_text_length = 140

    # VOICEPEAK CLIは複数プロセスから同時に呼ぶと不安定になるため、
    # エンジンインスタンスをまたいですべてのCLI操作を直列化する。
    _cli_lock = threading.Lock()
    _synthesis_attempts = 3

    def __init__(self, executable_path: Optional[str] = None):
        if executable_path:
            self.executable_path = executable_path
        else:
            # Default search paths
            if sys.platform == "darwin":
                self.executable_path = "/Applications/voicepeak.app/Contents/MacOS/voicepeak"
            elif sys.platform == "win32":
                self.executable_path = r"C:\Program Files\Voicepeak\voicepeak.exe"
            else:
                self.executable_path = "voicepeak"  # Assume in PATH for Linux/others

        # Allow override via environment variable
        env_path = os.environ.get("VOICEPEAK_PATH")
        if env_path:
            self.executable_path = env_path

    @property
    def engine_name(self) -> str:
        return "Voicepeak"

    def is_available(self) -> bool:
        try:
            # Quick run to check if executable runs
            with self._cli_lock:
                result = subprocess.run(
                    [self.executable_path, "--help"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def get_speakers(self) -> List[Speaker]:
        if not self.is_available():
            return []

        try:
            with self._cli_lock:
                result = subprocess.run(
                    [self.executable_path, "--list-narrator"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=3.0,
                )
            # Example output:
            # Male 1
            # Female 1
            # ...
            speakers = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.startswith("Narrator List:"):
                    speakers.append(
                        Speaker(
                            id=line,
                            name=line,
                            styles=[],  # Voicepeak emotions can vary per character
                        )
                    )
            return speakers
        except (subprocess.SubprocessError, FileNotFoundError):
            return []

    def get_emotions(self, speaker_id: str) -> List[str]:
        """指定ナレーターで利用可能な感情名を取得します。"""
        try:
            with self._cli_lock:
                result = subprocess.run(
                    [self.executable_path, "--list-emotion", speaker_id],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=3.0,
                )
            emotions = []
            for line in result.stdout.splitlines():
                name = line.strip()
                if name and not name.startswith("Emotion List:"):
                    emotions.append(name)
            return emotions
        except (subprocess.SubprocessError, FileNotFoundError):
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
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        try:
            # Build command line arguments
            cmd = [
                self.executable_path,
                "--say",
                text,
                "--narrator",
                speaker_id,
                "--out",
                temp_path,
            ]

            # Voicepeak speed is percentage (50 to 200)
            if speed is not None:
                # Map float (e.g. 1.0 -> 100)
                cmd.extend(["--speed", str(int(speed * 100))])

            # Voicepeak pitch is percentage (-150 to 150)
            if pitch is not None:
                cmd.extend(["--pitch", str(int(pitch * 100))])

            # Voicepeak volume is percentage (0 to 200)
            if volume is not None:
                cmd.extend(["--volume", str(int(volume * 100))])

            # Custom emotions parameter e.g., style="happy=50,sad=50"
            if style:
                cmd.extend(["--emotion", style])
            elif "emotion" in kwargs:
                cmd.extend(["--emotion", kwargs["emotion"]])

            # 長文では20秒を超える場合があるため、文字数に応じて待機時間を延長する。
            timeout = max(30.0, min(120.0, len(text) * 0.4))
            last_error: Optional[Exception] = None

            with self._cli_lock:
                for attempt in range(self._synthesis_attempts):
                    try:
                        subprocess.run(
                            cmd,
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            timeout=timeout,
                        )

                        with open(temp_path, "rb") as f:
                            wav_bytes = f.read()
                        if not wav_bytes:
                            raise RuntimeError("VOICEPEAKが空の音声ファイルを返しました。")
                        return wav_bytes
                    except (
                        subprocess.CalledProcessError,
                        subprocess.TimeoutExpired,
                        OSError,
                        RuntimeError,
                    ) as error:
                        last_error = error
                        if attempt + 1 < self._synthesis_attempts:
                            # CLIプロセス終了直後の再起動を避けるため少しずつ待機を延ばす。
                            time.sleep(0.4 * (attempt + 1))

            raise RuntimeError(
                f"VOICEPEAKの音声生成が{self._synthesis_attempts}回連続で失敗しました。"
            ) from last_error

        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass
