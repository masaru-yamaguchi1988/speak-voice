import argparse
import shutil
import subprocess
import sys
from typing import Dict, Type

import requests

from speak_voice.base import BaseEngine
from speak_voice.engines import (
    CoeiroinkEngine,
    VoicepeakEngine,
    VoicevoxEngine,
    VoiSonaEngine,
)
from speak_voice.player import play_wav

# エンジン名のキーとクラスの対応マッピング
ENGINES: Dict[str, Type[BaseEngine]] = {
    "voicevox": VoicevoxEngine,
    "coeiroink": CoeiroinkEngine,
    "voicepeak": VoicepeakEngine,
    "voisona": VoiSonaEngine,
}


def get_engine(name: str) -> BaseEngine:
    engine_cls = ENGINES.get(name.lower())
    if not engine_cls:
        raise ValueError(f"Unknown engine: {name}. Available: {list(ENGINES.keys())}")
    return engine_cls()


def cmd_list_engines(args):
    print("Available Engines:")
    for key, engine_cls in ENGINES.items():
        name = key.upper()
        try:
            inst = engine_cls()
            name = inst.engine_name
            status = "Available" if inst.is_available() else "Not Installed/Running"
        except Exception:
            status = "Error checking status"
        print(f"  - {key:<12}: {name} ({status})")


def cmd_list_speakers(args):
    try:
        engine = get_engine(args.engine)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    if not engine.is_available():
        print(
            f"Warning: Engine '{args.engine}' does not seem to be running or installed.",
            file=sys.stderr,
        )

    speakers = engine.get_speakers()
    if not speakers:
        print(f"No speakers found for engine '{args.engine}'.")
        return

    print(f"Speakers for {engine.engine_name}:")
    print(f"  {'ID':<30} | {'Name'}")
    print("-" * 50)
    for speaker in speakers:
        print(f"  {speaker.id:<30} | {speaker.name}")


def cmd_speak(args):
    try:
        engine = get_engine(args.engine)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    print(f"Synthesizing text using {engine.engine_name}...")
    try:
        wav_bytes = engine.synthesize_wav(
            text=args.text,
            speaker_id=args.speaker,
            speed=args.speed,
            pitch=args.pitch,
            intonation=args.intonation,
            volume=args.volume,
            style=args.style,
        )
    except Exception as e:
        print(f"Error during synthesis: {e}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        try:
            with open(args.out, "wb") as f:
                f.write(wav_bytes)
            print(f"Saved audio to {args.out}")
        except Exception as e:
            print(f"Failed to save audio file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Playing audio...")
        success = play_wav(wav_bytes)
        if not success:
            sys.exit(1)


def read_clipboard() -> str:
    """OS標準または一般的なコマンドからクリップボード文字列を取得します。"""
    if sys.platform == "darwin":
        commands = [["pbpaste"]]
    elif sys.platform == "win32":
        commands = [
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-Clipboard -Raw",
            ]
        ]
    else:
        commands = [
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ]

    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
            text = result.stdout.strip()
            if text:
                return text
        except (OSError, subprocess.SubprocessError):
            continue
    return ""


def cmd_hook(args):
    text = args.text
    if args.clip or not text:
        text = read_clipboard()

    if not text:
        print(
            "エラー: 読み上げるテキストが指定されていないか、クリップボードが空です。",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "engine": args.engine or "voicevox",
        "speaker": args.speaker or "1",
        "text": text,
        "speed": args.speed,
        "pitch": args.pitch,
        "intonation": args.intonation,
        "volume": args.volume,
        "style": args.style,
        "wait": args.wait,
    }

    url = f"{args.server_url.rstrip('/')}/api/hook/speak"
    try:
        timeout = 300 if args.wait else 5
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        print(f"成功: Webサーバー ({url}) にテキストフックを送信しました: 「{text[:30]}...」")
    except Exception as e:
        print(
            f"Web サーバー未起動または接続エラー ({e})。ローカル直接再生にフォールバックします..."
        )
        engine = get_engine(payload["engine"])
        wav_bytes = engine.synthesize_wav(
            text=text,
            speaker_id=payload["speaker"],
            speed=payload["speed"],
            pitch=payload["pitch"],
            intonation=payload["intonation"],
            volume=payload["volume"],
            style=payload["style"],
        )
        if not play_wav(wav_bytes):
            print("音声の再生に失敗しました。", file=sys.stderr)
            sys.exit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Unified CLI for Japanese Voice Synthesis Engines")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-engines サブコマンド
    subparsers.add_parser("list-engines", help="対応エンジン一覧と起動状態を表示")

    # list-speakers サブコマンド
    list_speakers_parser = subparsers.add_parser(
        "list-speakers", help="指定エンジンの話者一覧を表示"
    )
    list_speakers_parser.add_argument(
        "-e", "--engine", required=True, choices=list(ENGINES.keys()), help="Engine to query"
    )

    # speak サブコマンド
    speak_parser = subparsers.add_parser("speak", help="テキストを音声合成して再生")
    speak_parser.add_argument("text", help="Text to speak")
    speak_parser.add_argument(
        "-e", "--engine", required=True, choices=list(ENGINES.keys()), help="Engine to use"
    )
    speak_parser.add_argument("-s", "--speaker", required=True, help="Speaker/Character ID or Name")
    speak_parser.add_argument("--speed", type=float, help="Speed ratio/multiplier")
    speak_parser.add_argument("--pitch", type=float, help="Pitch ratio/offset")
    speak_parser.add_argument("--intonation", type=float, help="Intonation ratio")
    speak_parser.add_argument("--volume", type=float, help="Volume ratio")
    speak_parser.add_argument("--style", help="Specific emotion style (if supported)")
    speak_parser.add_argument(
        "-o", "--out", help="Save WAV audio to this file path instead of playing"
    )

    # hook サブコマンド
    hook_parser = subparsers.add_parser(
        "hook", help="Web サーバーまたはローカルフック経由でテキストを読み上げ"
    )
    hook_parser.add_argument(
        "text", nargs="?", default="", help="Text to speak (クリップボードを使用する場合は省略可能)"
    )
    hook_parser.add_argument(
        "-e", "--engine", default="voicevox", choices=list(ENGINES.keys()), help="Engine to use"
    )
    hook_parser.add_argument("-s", "--speaker", default="1", help="Speaker/Character ID")
    hook_parser.add_argument(
        "--clip", action="store_true", help="クリップボードのテキストを自動取得して読み上げ"
    )
    hook_parser.add_argument("--wait", action="store_true", help="再生完了まで待機")
    hook_parser.add_argument(
        "--server-url", default="http://127.0.0.1:8000", help="speak-voice Web サーバーのURL"
    )
    hook_parser.add_argument("--speed", type=float)
    hook_parser.add_argument("--pitch", type=float)
    hook_parser.add_argument("--intonation", type=float)
    hook_parser.add_argument("--volume", type=float)
    hook_parser.add_argument("--style")

    args = parser.parse_args(argv)

    if args.command == "list-engines":
        cmd_list_engines(args)
    elif args.command == "list-speakers":
        cmd_list_speakers(args)
    elif args.command == "speak":
        cmd_speak(args)
    elif args.command == "hook":
        cmd_hook(args)


def clip_main():
    """クリップボードのテキストを読み上げる専用エントリーポイント。"""
    main(["hook", "--clip", *sys.argv[1:]])


if __name__ == "__main__":
    main()
