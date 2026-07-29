import json
import logging
import os
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("speak_voice.voicepeak")
_events: deque[dict[str, Any]] = deque(maxlen=200)
_lock = threading.Lock()
_max_log_bytes = 2 * 1024 * 1024
_backup_count = 3


def voicepeak_log_path() -> Path:
    configured = os.environ.get("VOICEPEAK_LOG_FILE")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "speak-voice" / "voicepeak.log"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "speak-voice" / "logs" / "voicepeak.log"
    return Path.home() / ".local" / "state" / "speak-voice" / "voicepeak.log"


def _rotate_log(path: Path) -> None:
    if not path.exists() or path.stat().st_size < _max_log_bytes:
        return
    oldest = path.with_suffix(path.suffix + f".{_backup_count}")
    if oldest.exists():
        oldest.unlink()
    for index in range(_backup_count - 1, 0, -1):
        source = path.with_suffix(path.suffix + f".{index}")
        if source.exists():
            source.replace(path.with_suffix(path.suffix + f".{index + 1}"))
    path.replace(path.with_suffix(path.suffix + ".1"))


def record_voicepeak_event(level: str, event: str, **details: Any) -> None:
    """VOICEPEAK診断イベントをメモリとローテーションログへ記録する。"""
    item = {
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds"),
        "level": level,
        "event": event,
        **{key: value for key, value in details.items() if value is not None},
    }
    with _lock:
        _events.append(item)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            try:
                path = voicepeak_log_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                _rotate_log(path)
                with path.open("a", encoding="utf-8") as log_file:
                    log_file.write(json.dumps(item, ensure_ascii=False) + "\n")
            except OSError:
                # ログ保存失敗が音声合成そのものを妨げないようにする。
                pass

    message = json.dumps(item, ensure_ascii=False)
    getattr(logger, level if level in {"debug", "info", "warning", "error"} else "info")(message)


def get_voicepeak_events(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 200))
    with _lock:
        return list(_events)[-safe_limit:]
