import io
import os
import subprocess
import sys
import tempfile
import threading
import time
import wave


def _run_player(command: list[str], stop_event: threading.Event | None, **kwargs) -> bool:
    """外部プレイヤーを実行し、停止要求時はプロセスを終了します。"""
    process = subprocess.Popen(command, **kwargs)
    while process.poll() is None:
        if stop_event and stop_event.is_set():
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return False
        time.sleep(0.05)
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)
    return True


def _wav_duration(wav_bytes: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            return wav.getnframes() / wav.getframerate()
    except (wave.Error, ZeroDivisionError):
        return 60.0


def play_wav(wav_bytes: bytes, stop_event: threading.Event | None = None) -> bool:
    """WAV形式の音声バイナリデータをクロスプラットフォームで再生します。

    pyaudio や sounddevice などの重いC言語依存の外部ライブラリを避け、
    OS標準搭載のコマンドや標準ライブラリを使用して音声を再生します。
    - macOS: afplay コマンド
    - Windows: winsound 標準モジュール
    - Linux: aplay コマンド

    引数:
        wav_bytes: WAVファイルのバイナリデータ。

    戻り値:
        bool: 再生に成功した場合は True、失敗した場合は False。
    """
    if not wav_bytes or (stop_event and stop_event.is_set()):
        return False

    # Windowsでは非同期再生にして停止要求を監視する
    if sys.platform == "win32":
        try:
            import winsound

            flags = winsound.SND_MEMORY
            if stop_event:
                flags |= winsound.SND_ASYNC
            winsound.PlaySound(wav_bytes, flags)
            if stop_event:
                cancelled = stop_event.wait(_wav_duration(wav_bytes))
                if cancelled:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                    return False
            return True
        except Exception:
            pass

    # 一時ファイルを作成して再生する標準的なアプローチ
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(wav_bytes)

        if sys.platform == "darwin":
            return _run_player(["afplay", temp_path], stop_event)
        elif sys.platform == "win32":
            import winsound

            flags = winsound.SND_FILENAME | (winsound.SND_ASYNC if stop_event else 0)
            winsound.PlaySound(temp_path, flags)
            if stop_event:
                cancelled = stop_event.wait(_wav_duration(wav_bytes))
                if cancelled:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                    return False
            return True
        else:
            # Linuxなど: 代表的なCLIプレイヤー（aplay, paplay, play）を順に試す
            for player in ["aplay", "paplay", "play"]:
                try:
                    return _run_player(
                        [player, temp_path],
                        stop_event,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except (subprocess.SubprocessError, FileNotFoundError):
                    continue

            print(
                "Error: 再生可能なオーディオプレイヤーが見つかりませんでした (aplay, paplay, play を試行)。",
                file=sys.stderr,
            )
            return False

    except Exception as e:
        print(f"音声の再生に失敗しました: {e}", file=sys.stderr)
        return False
    finally:
        # 一時ファイルの削除処理
        try:
            os.remove(temp_path)
        except OSError:
            pass
