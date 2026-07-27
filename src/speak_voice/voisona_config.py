import ipaddress
import os
import threading
from dataclasses import dataclass, replace
from typing import Optional
from urllib.parse import urlparse

KEYRING_SERVICE = "speak-voice/voisona"
DEFAULT_BASE_URL = "http://127.0.0.1:32766/api/talk/v1"
_KEYRING_FIELDS = ("base_url", "username", "password")
_lock = threading.RLock()
_session_config: Optional["VoiSonaConfig"] = None


@dataclass(frozen=True)
class VoiSonaConfig:
    base_url: str = DEFAULT_BASE_URL
    username: str = ""
    password: str = ""
    source: str = "none"

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password)


def normalize_local_base_url(value: str) -> str:
    """認証情報を外部へ送らないようVoiSona APIの接続先をループバックに制限する。"""
    candidate = value.strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("VoiSona API URLにはlocalhostのHTTP URLを指定してください。")
    if parsed.query or parsed.fragment:
        raise ValueError("VoiSona API URLにクエリやフラグメントは指定できません。")
    if parsed.path.rstrip("/") != "/api/talk/v1":
        raise ValueError("VoiSona API URLのパスには/api/talk/v1を指定してください。")

    hostname = parsed.hostname.lower()
    is_loopback = hostname == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback:
        raise ValueError("VoiSona APIの接続先にはlocalhostのみ指定できます。")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("VoiSona API URLのポート番号が不正です。") from error
    if not port:
        raise ValueError("VoiSona API URLにはポート番号を指定してください。")
    return candidate


def _environment_config() -> VoiSonaConfig:
    port = os.environ.get("VOISONA_API_PORT", "32766")
    base_url = os.environ.get("VOISONA_API_URL", f"http://127.0.0.1:{port}/api/talk/v1")
    username = os.environ.get("VOISONA_API_USER", "")
    password = os.environ.get("VOISONA_API_PASSWORD", "")
    source = "environment" if username or password else "none"
    return VoiSonaConfig(
        base_url=normalize_local_base_url(base_url),
        username=username,
        password=password,
        source=source,
    )


def _load_keyring_config() -> Optional[VoiSonaConfig]:
    try:
        import keyring

        values = {field: keyring.get_password(KEYRING_SERVICE, field) for field in _KEYRING_FIELDS}
    except Exception:
        return None
    if not values["username"] or not values["password"]:
        return None
    try:
        base_url = normalize_local_base_url(values["base_url"] or DEFAULT_BASE_URL)
    except ValueError:
        return None
    return VoiSonaConfig(
        base_url=base_url,
        username=values["username"] or "",
        password=values["password"] or "",
        source="keyring",
    )


def get_voisona_config() -> VoiSonaConfig:
    with _lock:
        if _session_config is not None:
            return _session_config
        keyring_config = _load_keyring_config()
        if keyring_config:
            return keyring_config
        return _environment_config()


def set_voisona_config(config: VoiSonaConfig, remember: bool = False) -> VoiSonaConfig:
    normalized = replace(
        config,
        base_url=normalize_local_base_url(config.base_url),
        source="keyring" if remember else "session",
    )
    if not normalized.configured:
        raise ValueError("VoiSona APIのユーザー名とパスワードを入力してください。")

    if remember:
        try:
            import keyring

            for field in _KEYRING_FIELDS:
                keyring.set_password(KEYRING_SERVICE, field, getattr(normalized, field))
        except Exception as error:
            raise RuntimeError(
                "OSの資格情報ストアへ保存できませんでした。keyringの設定を確認してください。"
            ) from error

    global _session_config
    with _lock:
        _session_config = normalized
    return normalized


def clear_voisona_config(clear_keyring: bool = True) -> None:
    global _session_config
    with _lock:
        _session_config = None

    if not clear_keyring:
        return
    try:
        import keyring

        for field in _KEYRING_FIELDS:
            try:
                keyring.delete_password(KEYRING_SERVICE, field)
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception:
        # 資格情報ストアが利用できなくても、メモリ上の設定消去は成功扱いにする。
        pass
