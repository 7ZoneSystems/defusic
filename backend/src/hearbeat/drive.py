"""Google Drive integration for user-owned song storage.

Uses drive.file scope (narrowest practical). All Drive operations are
server-side, using tokens exchanged from the frontend OAuth flow.
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from hearbeat import cohesivity as coh
from hearbeat.token_encryption import encrypt_token, decrypt_token, is_encrypted

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"

HEARBEAT_FOLDER_NAME = "HearBeat"
SONGS_FOLDER_NAME = "Songs"

# Required scope for file-level access
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def _get_client_id() -> str:
    cid = os.getenv("GOOGLE_DRIVE_CLIENT_ID", "")
    if not cid:
        raise RuntimeError("GOOGLE_DRIVE_CLIENT_ID not configured")
    return cid


def _get_client_secret() -> str:
    cs = os.getenv("GOOGLE_DRIVE_CLIENT_SECRET", "")
    if not cs:
        raise RuntimeError("GOOGLE_DRIVE_CLIENT_SECRET not configured")
    return cs


def _get_redirect_uri() -> str:
    frontend = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return f"{frontend}/auth/drive-callback"


async def exchange_code(auth_code: str) -> dict[str, Any]:
    """Exchange authorization code for access + refresh tokens."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": auth_code,
                "client_id": _get_client_id(),
                "client_secret": _get_client_secret(),
                "redirect_uri": _get_redirect_uri(),
                "grant_type": "authorization_code",
            },
            headers={"User-Agent": "hearbeat-app/1.0"},
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any] | None:
    """Refresh an expired access token. Returns new token data or None."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": _get_client_id(),
                "client_secret": _get_client_secret(),
                "grant_type": "refresh_token",
            },
            headers={"User-Agent": "hearbeat-app/1.0"},
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Drive token refresh failed: %s", resp.status_code)
        return None


async def _get_valid_token(user: dict[str, Any]) -> str | None:
    """Get a valid access token, refreshing if needed. Returns None if not connected.

    Decrypts stored tokens and migrates legacy plaintext on first read.
    """
    raw_access = user.get("drive_access_token")
    raw_refresh = user.get("drive_refresh_token")
    expiry = user.get("drive_token_expiry")

    if not raw_access:
        return None

    # Decrypt stored tokens
    access_token = decrypt_token(raw_access)
    refresh_token = decrypt_token(raw_refresh) if raw_refresh else None

    # Migrate legacy plaintext: re-encrypt and persist
    if not is_encrypted(raw_access) or (raw_refresh and not is_encrypted(raw_refresh)):
        try:
            await _store_tokens(
                user["id"], access_token, refresh_token or "", 0
            )
        except Exception:
            logger.warning("Failed to migrate legacy plaintext tokens for user %s", user["id"])

    # Check if token is expired (with 5 min buffer)
    if expiry:
        if isinstance(expiry, str):
            expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        else:
            expiry_dt = expiry
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry_dt:
            if refresh_token:
                new_tokens = await refresh_access_token(refresh_token)
                if new_tokens:
                    access_token = new_tokens["access_token"]
                    await _store_tokens(
                        user["id"],
                        access_token,
                        new_tokens.get("refresh_token", refresh_token),
                        new_tokens.get("expires_in", 3600),
                    )
                else:
                    return None
            else:
                return None

    return access_token


async def _store_tokens(
    db_user_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> None:
    """Store Drive tokens in the database (encrypted at rest)."""
    expiry = datetime.now(timezone.utc).timestamp() + expires_in
    expiry_dt = datetime.fromtimestamp(expiry, tz=timezone.utc)
    await coh.db_query(
        """UPDATE users SET
            drive_access_token = $1,
            drive_refresh_token = $2,
            drive_token_expiry = $3
        WHERE id = $4""",
        [encrypt_token(access_token), encrypt_token(refresh_token), expiry_dt.isoformat(), db_user_id],
    )


async def _drive_request(
    method: str,
    url: str,
    token: str,
    **kwargs: Any,
) -> httpx.Response:
    """Make an authenticated request to Google Drive API."""
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    headers["User-Agent"] = "hearbeat-app/1.0"
    async with httpx.AsyncClient(timeout=60) as client:
        return await client.request(method, url, headers=headers, **kwargs)


async def _find_folder(token: str, name: str, parent_id: str = "root") -> str | None:
    """Find a folder by name under a parent. Returns folder ID or None."""
    query = (
        f"'{parent_id}' in parents and name='{name}' "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    resp = await _drive_request(
        "GET",
        f"{DRIVE_API_BASE}/files",
        token,
        params={"q": query, "fields": "files(id,name)", "pageSize": "1"},
    )
    resp.raise_for_status()
    files = resp.json().get("files", [])
    return files[0]["id"] if files else None


async def _create_folder(
    token: str, name: str, parent_id: str = "root"
) -> str:
    """Create a folder and return its ID."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    resp = await _drive_request(
        "POST",
        f"{DRIVE_API_BASE}/files",
        token,
        json=metadata,
        params={"fields": "id"},
    )
    resp.raise_for_status()
    return resp.json()["id"]


async def ensure_folder_structure(
    token: str,
) -> tuple[str, str]:
    """Ensure HearBeat/Songs/ folder structure exists. Returns (hearbeat_folder_id, songs_folder_id)."""
    # Find or create HearBeat folder
    hb_folder_id = await _find_folder(token, HEARBEAT_FOLDER_NAME)
    if not hb_folder_id:
        hb_folder_id = await _create_folder(token, HEARBEAT_FOLDER_NAME)
        logger.info("Created HearBeat folder: %s", hb_folder_id)

    # Find or create Songs subfolder
    songs_folder_id = await _find_folder(token, SONGS_FOLDER_NAME, hb_folder_id)
    if not songs_folder_id:
        songs_folder_id = await _create_folder(token, SONGS_FOLDER_NAME, hb_folder_id)
        logger.info("Created Songs folder: %s", songs_folder_id)

    return hb_folder_id, songs_folder_id


async def save_folder_ids(
    db_user_id: int, folder_id: str, songs_folder_id: str
) -> None:
    """Persist Drive folder IDs to user record."""
    await coh.db_query(
        "UPDATE users SET drive_folder_id = $1, drive_songs_folder_id = $2 WHERE id = $3",
        [folder_id, songs_folder_id, db_user_id],
    )


async def upload_file(
    token: str,
    songs_folder_id: str,
    filename: str,
    mime_type: str,
    file_bytes: bytes,
) -> str:
    """Upload a file to the Songs folder. Returns the Drive file ID."""
    metadata = {
        "name": filename,
        "parents": [songs_folder_id],
    }
    # Multipart upload: metadata + file content
    boundary = "hearbeat-boundary"
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{__import__('json').dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    resp = await _drive_request(
        "POST",
        f"{DRIVE_UPLOAD_BASE}/files",
        token,
        content=body,
        headers={
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
        params={"uploadType": "multipart", "fields": "id"},
    )
    resp.raise_for_status()
    return resp.json()["id"]


async def download_file(token: str, file_id: str) -> bytes:
    """Download a file from Drive. Returns file bytes."""
    resp = await _drive_request(
        "GET",
        f"{DRIVE_API_BASE}/files/{file_id}",
        token,
        params={"alt": "media"},
    )
    resp.raise_for_status()
    return resp.content


async def delete_file(token: str, file_id: str) -> bool:
    """Delete a file from Drive. Returns True on success."""
    resp = await _drive_request(
        "DELETE",
        f"{DRIVE_API_BASE}/files/{file_id}",
        token,
    )
    return resp.status_code == 204


async def get_file_metadata(token: str, file_id: str) -> dict[str, Any] | None:
    """Get metadata for a Drive file."""
    resp = await _drive_request(
        "GET",
        f"{DRIVE_API_BASE}/files/{file_id}",
        token,
        params={"fields": "id,name,mimeType,size,createdTime"},
    )
    if resp.status_code == 200:
        return resp.json()
    return None


async def verify_file_in_folder(token: str, file_id: str, folder_id: str) -> bool:
    """Verify that a file exists inside the specified folder.

    Queries Drive for the file and checks that one of its parents
    matches the expected folder ID. This prevents operations on
    arbitrary Drive files the user can access but that are not
    inside HearBeat/Songs/.
    """
    resp = await _drive_request(
        "GET",
        f"{DRIVE_API_BASE}/files/{file_id}",
        token,
        params={"fields": "id,parents", "supportsAllDrives": "true"},
    )
    if resp.status_code != 200:
        return False
    data = resp.json()
    parents = data.get("parents", [])
    return folder_id in parents


async def disconnect_drive(db_user_id: int) -> None:
    """Clear Drive tokens and folder IDs from user record."""
    await coh.db_query(
        """UPDATE users SET
            drive_access_token = NULL,
            drive_refresh_token = NULL,
            drive_token_expiry = NULL,
            drive_folder_id = NULL,
            drive_songs_folder_id = NULL
        WHERE id = $1""",
        [db_user_id],
    )
