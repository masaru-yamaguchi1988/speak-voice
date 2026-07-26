import os
import subprocess
import sys
import tempfile


def play_wav(wav_bytes: bytes) -> bool:
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
    if not wav_bytes:
        return False

    # Windowsの場合は、標準ライブラリの winsound を使用してメモリから直接再生を試みる
    if sys.platform == "win32":
        try:
            import winsound

            # winsound.PlaySound はファイルパスまたはバイト列（SND_MEMORYフラグ使用時）を受け取ることができます
            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            return True
        except Exception:
            # winsoundのメモリ再生に失敗した場合は、一時ファイル経由の再生にフォールバックします
            pass

    # 一時ファイルを作成して再生する標準的なアプローチ
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(wav_bytes)

        if sys.platform == "darwin":
            # macOS: 標準搭載の afplay コマンドを呼び出す
            subprocess.run(["afplay", temp_path], check=True)
            return True
        elif sys.platform == "win32":
            # winsoundのメモリ再生が何らかの理由で動かない場合のファイル再生フォールバック
            import winsound

            winsound.PlaySound(temp_path, winsound.SND_FILENAME)
            return True
        else:
            # Linuxなど: 代表的なCLIプレイヤー（aplay, paplay, play）を順に試す
            for player in ["aplay", "paplay", "play"]:
                try:
                    subprocess.run(
                        [player, temp_path],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
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
