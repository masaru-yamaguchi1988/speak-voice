import sys
from unittest.mock import MagicMock, patch

import pytest

from speak_voice import voisona_config
from speak_voice.voisona_config import (
    VoiSonaConfig,
    get_voisona_config,
    normalize_local_base_url,
    set_voisona_config,
)


@pytest.fixture(autouse=True)
def reset_session_config():
    with patch.object(voisona_config, "_session_config", None):
        yield


def test_voisona_url_accepts_only_loopback_http():
    assert (
        normalize_local_base_url("http://localhost:32766/api/talk/v1/")
        == "http://localhost:32766/api/talk/v1"
    )
    assert (
        normalize_local_base_url("http://127.0.0.1:32766/api/talk/v1")
        == "http://127.0.0.1:32766/api/talk/v1"
    )

    with pytest.raises(ValueError, match="localhost"):
        normalize_local_base_url("https://example.com/api/talk/v1")

    with pytest.raises(ValueError, match="/api/talk/v1"):
        normalize_local_base_url("http://127.0.0.1:32766/unrelated-service")


def test_voisona_session_config_takes_priority():
    config = VoiSonaConfig(
        username="user@example.com",
        password="secret",
    )

    with patch.object(voisona_config, "_load_keyring_config", return_value=None):
        saved = set_voisona_config(config)
        loaded = get_voisona_config()

    assert saved.source == "session"
    assert loaded.username == "user@example.com"
    assert loaded.password == "secret"


def test_voisona_remember_uses_os_keyring():
    keyring = MagicMock()
    config = VoiSonaConfig(
        username="user@example.com",
        password="secret",
    )

    with patch.dict(sys.modules, {"keyring": keyring}):
        saved = set_voisona_config(config, remember=True)

    assert saved.source == "keyring"
    assert keyring.set_password.call_count == 3
    keyring.set_password.assert_any_call("speak-voice/voisona", "password", "secret")
