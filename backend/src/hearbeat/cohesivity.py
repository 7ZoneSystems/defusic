"""Cohesivity integration: auth, database, and cloud storage helpers.

All Cohesivity API calls are server-side only. Credentials come from .cohesivity.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

COHESIVITY_BASE = "https://cohesivity.ai"

_tenant_id: str | None = None
_management_key: str | None = None
_application_key: str | None = None


def _load_credentials() -> tuple[str, str, str]:
    """Load Cohesivity credentials from .cohesivity file or env vars."""
    global _tenant_id, _management_key, _application_key

    if _tenant_id and _management_key and _application_key:
        return _tenant_id, _management_key, _application_key

    # Try env vars first (for production)
    _tenant_id = os.getenv("COHESIVITY_TENANT_ID")
    _management_key = os.getenv("COHESIVITY_MANAGEMENT_KEY")
    _application_key = os.getenv("COHESIVITY_APPLICATION_KEY")

    if _tenant_id and _management_key and _application_key:
        return _tenant_id, _management_key, _application_key

    # Fall back to .cohesivity file
    cohesivity_path = Path(__file__).resolve().parent.parent.parent.parent / ".cohesivity"
    if not cohesivity_path.exists():
        raise RuntimeError(
            "Cohesivity not configured. Run: npx @cohesivity/init"
        )

    creds: dict[str, str] = {}
    for line in cohesivity_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        creds[key.strip()] = value.strip()

    _tenant_id = creds.get("tenant_id")
    _management_key = creds.get("coh_management_key")
    _application_key = creds.get("coh_application_key")

    if not all([_tenant_id, _management_key, _application_key]):
        raise RuntimeError("Incomplete .cohesivity credentials")

    return _tenant_id, _management_key, _application_key


def get_tenant_id() -> str:
    tid, _, _ = _load_credentials()
    return tid


# --- Database helpers ---


async def db_query(query: str, params: list[Any] | None = None) -> list[dict]:
    """Execute a SQL query via the Cohesivity Postgres edge."""
    _, _, app_key = _load_credentials()
    url = f"{COHESIVITY_BASE}/edge/postgres?key={app_key}"

    body: dict[str, Any] = {"query": query, "params": params or []}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json=body,
            headers={"User-Agent": "hearbeat-app/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("rows", [])


async def db_batch(statements: list[dict[str, Any]]) -> list[dict]:
    """Execute a batch of SQL statements in one atomic transaction."""
    _, _, app_key = _load_credentials()
    url = f"{COHESIVITY_BASE}/edge/postgres?key={app_key}"

    body = {"statements": statements}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json=body,
            headers={"User-Agent": "hearbeat-app/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])


# --- Auth helpers ---


async def verify_access_token(access_token: str) -> dict | None:
    """Verify a Cohesivity access token. Returns user dict or None."""
    tid, _, _ = _load_credentials()
    url = f"{COHESIVITY_BASE}/edge/auth/{tid}/verify"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={"access_token": access_token},
            headers={"User-Agent": "hearbeat-app/1.0"},
        )
        data = resp.json()
        if data.get("valid"):
            return data.get("user")
        return None


async def refresh_tokens(refresh_token: str) -> dict | None:
    """Refresh Cohesivity tokens. Returns new tokens dict or None."""
    tid, _, _ = _load_credentials()
    url = f"{COHESIVITY_BASE}/edge/auth/{tid}/refresh"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            json={"refresh_token": refresh_token},
            headers={"User-Agent": "hearbeat-app/1.0"},
        )
        data = resp.json()
        if data.get("access_token"):
            return data
        return None


async def get_auth_user(
    access_token: str | None,
    refresh_token: str | None,
) -> tuple[dict | None, dict | None]:
    """Get the current user from cookies, refreshing if needed.

    Returns (user_dict, new_tokens_or_None).
    """
    if not access_token:
        return None, None

    user = await verify_access_token(access_token)
    if user:
        return user, None

    if not refresh_token:
        return None, None

    new_tokens = await refresh_tokens(refresh_token)
    if not new_tokens:
        return None, None

    user = await verify_access_token(new_tokens["access_token"])
    if user:
        return user, new_tokens
    return None, None


def get_login_url(callback_url: str | None = None, return_to: str | None = None) -> str:
    """Build the Cohesivity Google login URL."""
    tid, _, _ = _load_credentials()
    url = f"{COHESIVITY_BASE}/edge/auth/{tid}/google"
    params: list[str] = []
    if callback_url:
        params.append(f"redirect_uri={callback_url}")
    if return_to:
        params.append(f"return_to={return_to}")
    if params:
        url += "?" + "&".join(params)
    return url


# --- User management ---


async def upsert_user(
    cohesivity_user_id: int,
    email: str,
    name: str | None,
    picture: str | None,
) -> dict:
    """Upsert a user in our local DB from Cohesivity auth data."""
    rows = await db_query(
        """
        INSERT INTO users (cohesivity_user_id, email, name, picture, last_login)
        VALUES ($1, $2, $3, $4, NOW())
        ON CONFLICT (cohesivity_user_id)
        DO UPDATE SET email = $2, name = $3, picture = $4, last_login = NOW()
        RETURNING id, cohesivity_user_id, email, name, picture, created_at, last_login
        """,
        [cohesivity_user_id, email, name, picture],
    )
    return rows[0] if rows else {}


async def get_user_by_cohesivity_id(cohesivity_user_id: int) -> dict | None:
    """Get a user by their Cohesivity user ID."""
    rows = await db_query(
        "SELECT id, cohesivity_user_id, email, name, picture, created_at, last_login FROM users WHERE cohesivity_user_id = $1",
        [cohesivity_user_id],
    )
    return rows[0] if rows else None


async def get_user_by_id(user_id: int) -> dict | None:
    """Get a user by internal DB ID."""
    rows = await db_query(
        "SELECT id, cohesivity_user_id, email, name, picture, created_at, last_login FROM users WHERE id = $1",
        [user_id],
    )
    return rows[0] if rows else None
