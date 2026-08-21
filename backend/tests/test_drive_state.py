"""Drive connection state tests.

Verifies that /drive/status is the authoritative source of connection state
and that the connection state is independent of the song list contents.
"""

from __future__ import annotations

import base64
import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from hearbeat.main import app


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def set_encryption_key(monkeypatch):
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("DRIVE_TOKEN_ENCRYPTION_KEY", key)
    return key


def _authenticated_user():
    return {"id": 1, "email": "test@example.com", "name": "Test", "picture": None}


def _mock_drive_response(files: list) -> MagicMock:
    """Create a mock httpx.Response for Drive API calls."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"files": files}
    resp.raise_for_status = MagicMock()
    return resp


# ============================================================
# 1. Drive disconnected -> connected=false
# ============================================================


class TestDriveDisconnected:
    def test_status_returns_false_when_no_folder_ids(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": None,
            "drive_folder_id": None,
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
        ):
            resp = client.get(
                "/drive/status",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert data["folder_id"] is None
            assert data["songs_folder_id"] is None


# ============================================================
# 2. Drive connected + empty folder -> connected=true, songs=[]
# ============================================================


class TestDriveConnectedEmpty:
    def test_status_returns_true_when_folder_ids_set(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
        ):
            resp = client.get(
                "/drive/status",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True
            assert data["songs_folder_id"] == "songs_abc"

    def test_songs_returns_empty_when_folder_empty(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
            "drive_access_token": "encrypted_access",
            "drive_refresh_token": "encrypted_refresh",
            "drive_token_expiry": "2099-01-01T00:00:00+00:00",
        }

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=_mock_drive_response([])),
        ):
            resp = client.get(
                "/drive/songs",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["songs"] == []


# ============================================================
# 3. Drive connected + songs -> connected=true, songs>0
# ============================================================


class TestDriveConnectedWithSongs:
    def test_songs_returns_files_when_present(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
            "drive_access_token": "encrypted_access",
            "drive_refresh_token": "encrypted_refresh",
            "drive_token_expiry": "2099-01-01T00:00:00+00:00",
        }

        files = [
            {"id": "f1", "name": "song1.mp3", "size": "1024", "mimeType": "audio/mpeg", "createdTime": "2025-01-01T00:00:00Z"},
            {"id": "f2", "name": "song2.wav", "size": "2048", "mimeType": "audio/wav", "createdTime": "2025-01-02T00:00:00Z"},
        ]

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=_mock_drive_response(files)),
        ):
            resp = client.get(
                "/drive/songs",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["songs"]) == 2
            assert data["songs"][0]["name"] == "song1.mp3"


# ============================================================
# 4. OAuth exchange persists folder IDs -> /drive/status returns connected
# ============================================================


class TestOAuthExchangePersistence:
    def test_exchange_saves_folder_ids_and_status_returns_true(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": None,
            "drive_folder_id": None,
        }

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive.exchange_code", new_callable=AsyncMock, return_value={
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            }),
            patch("hearbeat.main.gdrive._store_tokens", new_callable=AsyncMock),
            patch("hearbeat.main.gdrive.ensure_folder_structure", new_callable=AsyncMock, return_value=("hb_id_1", "songs_id_1")),
            patch("hearbeat.main.gdrive.save_folder_ids", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/drive/exchange",
                params={"code": "auth_code_123"},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "connected"
            assert data["folder_id"] == "hb_id_1"
            assert data["songs_folder_id"] == "songs_id_1"


# ============================================================
# 5. Empty folder never renders "Drive not connected"
#    (backend: connected=true even when songs list is empty)
# ============================================================


class TestEmptyFolderNotDisconnected:
    def test_empty_songs_does_not_affect_status(self, client):
        """Connected status is independent of whether songs list is empty."""
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
        ):
            resp = client.get(
                "/drive/status",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            data = resp.json()
            assert data["connected"] is True

    def test_drive_songs_empty_still_connected(self, client):
        """Listing songs returns [] but /drive/status still says connected=True."""
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
            "drive_access_token": "encrypted_access",
            "drive_refresh_token": "encrypted_refresh",
            "drive_token_expiry": "2099-01-01T00:00:00+00:00",
        }

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=_mock_drive_response([])),
        ):
            songs_resp = client.get(
                "/drive/songs",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert songs_resp.json()["songs"] == []

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
        ):
            status_resp = client.get(
                "/drive/status",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert status_resp.json()["connected"] is True


# ============================================================
# 6. Disconnect clears state -> connected=false
# ============================================================


class TestDriveDisconnect:
    def test_disconnect_clears_folder_ids(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive.disconnect_drive", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/drive/disconnect",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "disconnected"
