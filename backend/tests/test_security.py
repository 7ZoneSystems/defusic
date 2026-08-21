"""Security tests for auth callback, Drive ownership, and library storage."""

from __future__ import annotations

import base64
import json
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
    """Set a consistent test encryption key."""
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("DRIVE_TOKEN_ENCRYPTION_KEY", key)
    return key


# ============================================================
# 1. OAuth callback must not expose tokens in Location URL
# ============================================================


class TestOAuthCallbackTokenExposure:
    """The backend /auth/callback must set tokens as HttpOnly cookies
    and never include them in the redirect Location header."""

    def test_callback_sets_cookies_not_url_tokens(self, client):
        """Tokens are in Set-Cookie headers, not in the Location URL."""
        resp = client.get(
            "/auth/callback",
            params={
                "access_token": "secret_access_123",
                "refresh_token": "secret_refresh_456",
                "return_to": "/library",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 307

        location = resp.headers.get("location", "")
        # Tokens must NOT appear in the redirect URL
        assert "secret_access_123" not in location
        assert "secret_refresh_456" not in location
        # Should redirect to the return_to path
        assert "/library" in location

    def test_callback_sets_httponly_cookies(self, client):
        """access_token and refresh_token are set as HttpOnly cookies."""
        resp = client.get(
            "/auth/callback",
            params={
                "access_token": "token_abc",
                "refresh_token": "token_def",
                "return_to": "/",
            },
            follow_redirects=False,
        )
        set_cookie_headers = resp.headers.get_list("set-cookie")

        access_found = False
        refresh_found = False
        for header in set_cookie_headers:
            if header.startswith("access_token="):
                access_found = True
                assert "httponly" in header.lower()
                assert "secure" in header.lower()
            if header.startswith("refresh_token="):
                refresh_found = True
                assert "httponly" in header.lower()
                assert "secure" in header.lower()

        assert access_found, "access_token cookie not set"
        assert refresh_found, "refresh_token cookie not set"

    def test_callback_error_no_cookies(self, client):
        """Error callbacks do not set token cookies."""
        resp = client.get(
            "/auth/callback",
            params={"error": "access_denied"},
            follow_redirects=False,
        )
        set_cookie_headers = resp.headers.get_list("set-cookie")
        token_cookies = [h for h in set_cookie_headers if "access_token" in h or "refresh_token" in h]
        assert len(token_cookies) == 0

    def test_callback_no_token_no_cookies(self, client):
        """Missing access_token does not set cookies."""
        resp = client.get(
            "/auth/callback",
            params={"return_to": "/"},
            follow_redirects=False,
        )
        set_cookie_headers = resp.headers.get_list("set-cookie")
        token_cookies = [h for h in set_cookie_headers if "access_token" in h or "refresh_token" in h]
        assert len(token_cookies) == 0

    def test_callback_refresh_token_optional(self, client):
        """If refresh_token is not provided, only access_token cookie is set."""
        resp = client.get(
            "/auth/callback",
            params={
                "access_token": "only_access",
                "return_to": "/",
            },
            follow_redirects=False,
        )
        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_found = any("access_token=" in h for h in set_cookie_headers)
        refresh_found = any("refresh_token=" in h for h in set_cookie_headers)
        assert access_found
        assert not refresh_found


# ============================================================
# 2. Drive file ownership: files outside HearBeat/Songs rejected
# ============================================================


def _mock_user_and_drive():
    """Return common mocks for authenticated user with Drive connected."""
    user = {"id": 1, "email": "test@example.com", "name": "Test", "picture": None}
    db_user = {
        "id": 42,
        "cohesivity_user_id": 1,
        "email": "test@example.com",
        "drive_songs_folder_id": "songs_folder_abc",
        "drive_folder_id": "hb_folder_abc",
        "drive_access_token": "encrypted_access",
        "drive_refresh_token": "encrypted_refresh",
        "drive_token_expiry": "2099-01-01T00:00:00+00:00",
    }
    return user, db_user


class TestDriveFileOwnership:
    """Drive download/delete/analyze must reject files outside HearBeat/Songs."""

    @pytest.mark.asyncio
    async def test_download_rejects_file_outside_folder(self, client):
        user, db_user = _mock_user_and_drive()

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.verify_file_in_folder", new_callable=AsyncMock, return_value=False),
        ):
            resp = client.get(
                "/drive/download/evil_file_id_123",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 403
            assert "HearBeat/Songs" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_rejects_file_outside_folder(self, client):
        user, db_user = _mock_user_and_drive()

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.verify_file_in_folder", new_callable=AsyncMock, return_value=False),
        ):
            resp = client.delete(
                "/drive/file/evil_file_id_456",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 403
            assert "HearBeat/Songs" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_analyze_rejects_file_outside_folder(self, client):
        user, db_user = _mock_user_and_drive()

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.verify_file_in_folder", new_callable=AsyncMock, return_value=False),
        ):
            resp = client.post(
                "/drive/analyze/evil_file_id_789",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 403
            assert "HearBeat/Songs" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_download_allows_file_inside_folder(self, client):
        user, db_user = _mock_user_and_drive()

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.verify_file_in_folder", new_callable=AsyncMock, return_value=True),
            patch("hearbeat.main.gdrive.download_file", new_callable=AsyncMock, return_value=b"audio_bytes"),
            patch("hearbeat.main.gdrive.get_file_metadata", new_callable=AsyncMock, return_value={"name": "song.mp3", "mimeType": "audio/mpeg"}),
        ):
            resp = client.get(
                "/drive/download/good_file_id",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_allows_file_inside_folder(self, client):
        user, db_user = _mock_user_and_drive()

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.verify_file_in_folder", new_callable=AsyncMock, return_value=True),
            patch("hearbeat.main.gdrive.delete_file", new_callable=AsyncMock, return_value=True),
        ):
            resp = client.delete(
                "/drive/file/good_file_id",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "deleted"


# ============================================================
# 3. Library save: authenticated save without Drive fails
# ============================================================


class TestLibrarySaveDriveRequired:
    """Authenticated library saves must require Drive connection."""

    @pytest.mark.asyncio
    async def test_save_fails_without_drive(self, client):
        user = {"id": 1, "email": "test@example.com", "name": "Test", "picture": None}
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": None,
            "drive_access_token": None,
        }

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value=None),
        ):
            resp = client.post(
                "/library/songs?mode=music",
                files={"file": ("test.mp3", b"fake_audio_data", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 400
            detail = resp.json()["detail"]
            assert "Connect Google Drive" in detail

    @pytest.mark.asyncio
    async def test_save_succeeds_with_drive(self, client):
        user = {"id": 1, "email": "test@example.com", "name": "Test", "picture": None}
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_folder_abc",
            "drive_access_token": "encrypted_tok",
            "drive_refresh_token": "encrypted_refresh",
            "drive_token_expiry": "2099-01-01T00:00:00+00:00",
        }

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.upload_file", new_callable=AsyncMock, return_value="new_drive_id"),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, side_effect=[
                [],  # existing song check
                [{"id": 100}],  # insert result
            ]),
        ):
            resp = client.post(
                "/library/songs?mode=music",
                files={"file": ("test.mp3", b"fake_audio_data", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["song_id"] == 100
            assert data["drive_file_id"] == "new_drive_id"

    @pytest.mark.asyncio
    async def test_existing_song_does_not_require_drive(self, client):
        """If the song already exists (by hash), just mark as played — no Drive needed."""
        user = {"id": 1, "email": "test@example.com", "name": "Test", "picture": None}
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": None,
            "drive_access_token": None,
        }

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, side_effect=[
                [{"id": 50, "drive_file_id": "existing_drive_id"}],  # existing song found
                None,  # update last_played
            ]),
        ):
            resp = client.post(
                "/library/songs?mode=music",
                files={"file": ("test.mp3", b"fake_audio_data", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["song_id"] == 50


# ============================================================
# 4. verify_file_in_folder logic
# ============================================================


class TestVerifyFileInFolder:
    """Unit tests for the Drive file ownership verification helper."""

    @pytest.mark.asyncio
    async def test_returns_true_when_parent_matches(self):
        from hearbeat.drive import verify_file_in_folder

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "file1", "parents": ["songs_folder_abc"]}

        with patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await verify_file_in_folder("tok", "file1", "songs_folder_abc")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_parent_differs(self):
        from hearbeat.drive import verify_file_in_folder

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "file1", "parents": ["some_other_folder"]}

        with patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await verify_file_in_folder("tok", "file1", "songs_folder_abc")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_file_not_found(self):
        from hearbeat.drive import verify_file_in_folder

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await verify_file_in_folder("tok", "nonexistent", "songs_folder_abc")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_parents(self):
        from hearbeat.drive import verify_file_in_folder

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "file1", "parents": []}

        with patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=mock_resp):
            result = await verify_file_in_folder("tok", "file1", "songs_folder_abc")
            assert result is False
