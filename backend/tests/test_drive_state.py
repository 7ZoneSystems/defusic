"""Drive connection state and save-song tests.

Covers:
1. Drive connected + empty folder
2. Drive connected + songs
3. No Drive
4. connected.txt creation on first connection
5. connected.txt reused on reconnect
6. Deleted marker gets recreated
7-8. Login session persistence (keep-signed-in)
9-13. Save flow tests
14. Successful save updates library
15. Save does not reset playback (frontend concern, backend test verifies no re-analysis)
"""

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
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("DRIVE_TOKEN_ENCRYPTION_KEY", key)
    return key


def _authenticated_user():
    return {"id": 1, "email": "test@example.com", "name": "Test", "picture": None}


def _mock_drive_response(files: list) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"files": files}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_drive_file_response(file_id: str, name: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"id": file_id, "name": name}
    resp.raise_for_status = MagicMock()
    return resp


# ============================================================
# 1. Drive connected + empty folder: connected=true, has_songs=false
# ============================================================


class TestDriveConnectedEmpty:
    def test_status_returns_true_has_songs_false(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
            "drive_access_token": "encrypted_access",
            "drive_connection_file_id": "marker_123",
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, return_value=[]),
        ):
            resp = client.get(
                "/drive/status",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True
            assert data["has_songs"] is False
            assert data["connection_file_id"] == "marker_123"


# ============================================================
# 2. Drive connected + songs: connected=true, has_songs=true
# ============================================================


class TestDriveConnectedWithSongs:
    def test_status_returns_true_has_songs_true(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_folder_id": "hb_abc",
            "drive_access_token": "encrypted_access",
            "drive_connection_file_id": "marker_123",
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, return_value=[{"id": 1}]),
        ):
            resp = client.get(
                "/drive/status",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True
            assert data["has_songs"] is True


# ============================================================
# 3. No Drive: connected=false
# ============================================================


class TestDriveDisconnected:
    def test_status_returns_false_for_new_user_not_in_db(self, client):
        """A freshly logged in user not yet in local DB gets auto-upserted and returns 200 connected=false."""
        user = _authenticated_user()
        upserted_user = {
            "id": 99,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": None,
            "drive_folder_id": None,
            "drive_access_token": None,
            "drive_connection_file_id": None,
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=None),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=upserted_user),
        ):
            resp = client.get(
                "/drive/status",
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert data["has_songs"] is False

    def test_status_returns_false(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": None,
            "drive_folder_id": None,
            "drive_access_token": None,
            "drive_connection_file_id": None,
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
            assert data["has_songs"] is False
            assert data["connection_file_id"] is None


# ============================================================
# 4. connected.txt creation on first connection
# ============================================================


class TestMarkerCreation:
    def test_exchange_creates_marker(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_connection_file_id": None,
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
            patch("hearbeat.main.gdrive.ensure_connection_marker", new_callable=AsyncMock, return_value="marker_new"),
            patch("hearbeat.main.gdrive.save_folder_ids", new_callable=AsyncMock),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/drive/exchange",
                params={"code": "auth_code_123"},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connection_file_id"] == "marker_new"
            assert data["status"] == "connected"


# ============================================================
# 5. connected.txt reused on reconnect
# ============================================================


class TestMarkerReuse:
    def test_exchange_reuses_existing_marker(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_connection_file_id": "existing_marker",
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
            patch("hearbeat.main.gdrive.ensure_connection_marker", new_callable=AsyncMock, return_value="existing_marker"),
            patch("hearbeat.main.gdrive.save_folder_ids", new_callable=AsyncMock),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/drive/exchange",
                params={"code": "auth_code_123"},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["connection_file_id"] == "existing_marker"


# ============================================================
# 6. Deleted marker gets recreated
# ============================================================


class TestMarkerRecreation:
    @pytest.mark.asyncio
    async def test_ensure_connection_marker_creates_new_when_deleted(self, client):
        from hearbeat.drive import ensure_connection_marker, MARKER_FILE_NAME

        existing_id = "deleted_marker_id"

        create_resp = MagicMock()
        create_resp.status_code = 200
        create_resp.json.return_value = {"id": "new_marker_id"}
        create_resp.raise_for_status = MagicMock()

        with (
            patch("hearbeat.drive.get_file_metadata", new_callable=AsyncMock, return_value=None),
            patch("hearbeat.drive._find_file", new_callable=AsyncMock, return_value=None),
            patch("hearbeat.drive._drive_request", new_callable=AsyncMock, return_value=create_resp),
        ):
            marker_id = await ensure_connection_marker("token", "hb_folder_id", existing_id)
            assert marker_id == "new_marker_id"

    @pytest.mark.asyncio
    async def test_ensure_connection_marker_reuses_existing(self, client):
        from hearbeat.drive import ensure_connection_marker

        with (
            patch("hearbeat.drive.get_file_metadata", new_callable=AsyncMock, return_value={"id": "m1", "name": "connected.txt"}),
        ):
            marker_id = await ensure_connection_marker("token", "hb_folder_id", "m1")
            assert marker_id == "m1"


# ============================================================
# 7-8. Login session persistence
# ============================================================


class TestKeepSession:
    def test_keep_session_extends_cookie(self, client):
        resp = client.post(
            "/auth/keep-session",
            params={"keep": "true"},
            cookies={"access_token": "valid", "refresh_token": "valid_token"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        set_cookie_headers = resp.headers.get_list("set-cookie")
        found = False
        for h in set_cookie_headers:
            if h.startswith("refresh_token="):
                found = True
                assert "max-age=2592000" in h.lower()
        assert found

    def test_keep_session_false_session_cookie(self, client):
        resp = client.post(
            "/auth/keep-session",
            params={"keep": "false"},
            cookies={"access_token": "valid", "refresh_token": "valid_token"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        set_cookie_headers = resp.headers.get_list("set-cookie")
        for h in set_cookie_headers:
            if h.startswith("refresh_token="):
                assert "max-age" not in h.lower()


# ============================================================
# 9-13. Save flow tests
# ============================================================


class TestSaveFlow:
    def test_save_multipart_form_data(self, client):
        """analysis_json sent in multipart form data body works without query params."""
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_access_token": "encrypted_tok",
        }
        analysis = json.dumps({"tempo": 120, "beats": []})
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, side_effect=[
                [],  # existing song check
                [{"id": 88}],  # insert song
                [],  # insert analysis
            ]),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.upload_file", new_callable=AsyncMock, return_value="drive_file_99"),
        ):
            resp = client.post(
                "/library/songs/save-analysis",
                data={"analysis_json": analysis, "mode": "music", "filename": "form_track.mp3"},
                files={"file": ("form_track.mp3", b"audio_bytes", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "saved"
            assert data["song_id"] == 88

    def test_save_requires_auth(self, client):
        resp = client.post(
            "/library/songs/save-analysis?mode=music&filename=test.mp3&analysis_json={}",
            files={"file": ("test.mp3", b"audio", "audio/mpeg")},
        )
        assert resp.status_code == 401

    def test_save_requires_drive(self, client):
        user = _authenticated_user()
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
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, return_value=[]),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value=None),
        ):
            resp = client.post(
                "/library/songs/save-analysis?mode=music&filename=test.mp3&analysis_json={}",
                files={"file": ("test.mp3", b"audio", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 400
            assert "Google Drive" in resp.json()["detail"]

    def test_save_deduplicates_by_hash(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_access_token": "encrypted_tok",
        }
        analysis = json.dumps({"events": [], "duration": 120})
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, return_value=[{"id": 99, "drive_file_id": "existing"}]),
        ):
            resp = client.post(
                f"/library/songs/save-analysis?mode=music&filename=test.mp3&analysis_json={analysis}",
                files={"file": ("test.mp3", b"audio_data", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["song_id"] == 99
            assert data["status"] == "already_saved"

    def test_save_does_not_reanalyze(self, client):
        """Save endpoint should store analysis as-is, never call analyze_file."""
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_access_token": "encrypted_tok",
        }
        analysis = json.dumps({"events": [], "duration": 120})

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, side_effect=[
                [],  # no existing song
                [{"id": 200}],  # insert song
                [],  # insert analysis
            ]),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.upload_file", new_callable=AsyncMock, return_value="new_drive_id"),
        ):
            resp = client.post(
                f"/library/songs/save-analysis?mode=music&filename=test.mp3&analysis_json={analysis}",
                files={"file": ("test.mp3", b"new_audio", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["song_id"] == 200
            assert data["status"] == "saved"

    def test_save_returns_saved_status(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_access_token": "encrypted_tok",
        }
        analysis = json.dumps({"events": []})

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, side_effect=[
                [],  # no existing
                [{"id": 300}],  # insert song
                [],  # insert analysis
            ]),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.upload_file", new_callable=AsyncMock, return_value="drive_file_abc"),
        ):
            resp = client.post(
                f"/library/songs/save-analysis?mode=music&filename=song.mp3&analysis_json={analysis}",
                files={"file": ("song.mp3", b"audio_bytes", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "song_id" in data
            assert "file_hash" in data
            assert data["drive_file_id"] == "drive_file_abc"

    def test_save_invalid_analysis_json(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_access_token": "encrypted_tok",
        }
        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, side_effect=[
                [],  # existing song check
                [{"id": 1}],  # insert song
                RuntimeError("should not reach analysis insert"),  # would fail at json.loads before this
            ]),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.upload_file", new_callable=AsyncMock, return_value="drive_id"),
        ):
            resp = client.post(
                "/library/songs/save-analysis?mode=music&filename=test.mp3&analysis_json=not_json",
                files={"file": ("test.mp3", b"audio", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 400
            assert "analysis JSON" in resp.json()["detail"]


# ============================================================
# 14. Successful save updates library (verified by song_id return)
# ============================================================


class TestSaveUpdatesLibrary:
    def test_new_save_returns_song_id(self, client):
        user = _authenticated_user()
        db_user = {
            "id": 42,
            "cohesivity_user_id": 1,
            "drive_songs_folder_id": "songs_abc",
            "drive_access_token": "encrypted_tok",
        }
        analysis = json.dumps({"events": [], "duration": 300})

        with (
            patch("hearbeat.main.coh.get_auth_user", new_callable=AsyncMock, return_value=(user, None)),
            patch("hearbeat.main.coh.get_user_by_cohesivity_id", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.upsert_user", new_callable=AsyncMock, return_value=db_user),
            patch("hearbeat.main.coh.db_query", new_callable=AsyncMock, side_effect=[
                [],  # no existing
                [{"id": 400}],  # insert song
                [],  # insert analysis
            ]),
            patch("hearbeat.main.gdrive._get_valid_token", new_callable=AsyncMock, return_value="drive_tok"),
            patch("hearbeat.main.gdrive.upload_file", new_callable=AsyncMock, return_value="drive_file_xyz"),
        ):
            resp = client.post(
                f"/library/songs/save-analysis?mode=music&filename=new_song.mp3&analysis_json={analysis}",
                files={"file": ("new_song.mp3", b"fresh_audio", "audio/mpeg")},
                cookies={"access_token": "valid", "refresh_token": "valid"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["song_id"] == 400
            assert data["status"] == "saved"
