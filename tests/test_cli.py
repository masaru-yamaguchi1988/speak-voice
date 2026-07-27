from unittest.mock import MagicMock, patch

from speak_voice import cli


def test_engine_registry_contains_only_supported_engines():
    assert set(cli.ENGINES) == {"voicevox", "coeiroink", "voicepeak", "voisona"}


def test_hook_posts_text_to_web_server():
    response = MagicMock()
    args = MagicMock(
        text="読み上げテスト",
        clip=False,
        engine="voicevox",
        speaker="2",
        speed=1.2,
        pitch=None,
        intonation=None,
        volume=None,
        style=None,
        wait=True,
        server_url="http://127.0.0.1:8000/",
    )

    with patch("speak_voice.cli.requests.post", return_value=response) as post:
        cli.cmd_hook(args)

    post.assert_called_once_with(
        "http://127.0.0.1:8000/api/hook/speak",
        json={
            "engine": "voicevox",
            "speaker": "2",
            "text": "読み上げテスト",
            "speed": 1.2,
            "pitch": None,
            "intonation": None,
            "volume": None,
            "style": None,
            "wait": True,
        },
        timeout=300,
    )
    response.raise_for_status.assert_called_once()


def test_hook_reads_macos_clipboard():
    response = MagicMock()
    args = MagicMock(
        text="",
        clip=True,
        engine="voicevox",
        speaker="1",
        speed=None,
        pitch=None,
        intonation=None,
        volume=None,
        style=None,
        wait=False,
        server_url="http://127.0.0.1:8000",
    )

    with (
        patch("speak_voice.cli.read_clipboard", return_value="クリップボードの文章") as read,
        patch("speak_voice.cli.requests.post", return_value=response) as post,
    ):
        cli.cmd_hook(args)

    read.assert_called_once()
    assert post.call_args.kwargs["json"]["text"] == "クリップボードの文章"
    assert post.call_args.kwargs["timeout"] == 5


def test_read_clipboard_uses_macos_pbpaste():
    clipboard = MagicMock(stdout="クリップボードの文章\n")
    with (
        patch.object(cli.sys, "platform", "darwin"),
        patch("speak_voice.cli.shutil.which", return_value="/usr/bin/pbpaste"),
        patch("speak_voice.cli.subprocess.run", return_value=clipboard) as run,
    ):
        text = cli.read_clipboard()

    assert text == "クリップボードの文章"
    run.assert_called_once_with(
        ["pbpaste"],
        capture_output=True,
        text=True,
        check=True,
        timeout=3,
    )


def test_clip_main_forwards_arguments_to_hook():
    with (
        patch.object(cli.sys, "argv", ["speak-voice-clip", "--wait", "--speaker", "2"]),
        patch("speak_voice.cli.main") as main,
    ):
        cli.clip_main()

    main.assert_called_once_with(["hook", "--clip", "--wait", "--speaker", "2"])
