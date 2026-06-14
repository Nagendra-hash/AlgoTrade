"""
Broker connection API — persistent sessions via PostgreSQL/Supabase.
Path: backend/app/api/v1/brokers.py

Connections survive server restarts and page navigations.
No need to reconnect on every page load — connect once, use everywhere.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from app.api.v1.users import get_current_user
from app.models.user import User
from app.services.angel_one import (
    login, store_session, get_session, clear_session, _session_cache,
)
from app.services.zerodha import (
    login as zerodha_login,
    store_session as zerodha_store_session,
    get_session as zerodha_get_session,
    clear_session as zerodha_clear_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class AngelOneConnectRequest(BaseModel):
    api_key:     str
    client_id:   str
    password:    str
    totp_secret: str


class ZerodhaConnectRequest(BaseModel):
    api_key:    str
    api_secret: str


@router.post("/angel-one/connect")
async def connect_angel_one(
    req: AngelOneConnectRequest,
    current_user: User = Depends(get_current_user),
):
    """Connect Angel One — stores session in PostgreSQL/Supabase persistently."""
    if not all([req.api_key.strip(), req.client_id.strip(),
                req.password.strip(), req.totp_secret.strip()]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "All fields are required")

    result = await login(
        req.api_key.strip(), req.client_id.strip(),
        req.password.strip(), req.totp_secret.strip(),
    )

    if result["success"]:
        # Store session in DATABASE (not just memory) so it survives restarts
        await store_session(
            user_id=str(current_user.id),
            jwt_token=result["jwt_token"],
            refresh_token=result["refresh_token"],
            feed_token=result.get("feed_token", ""),
            api_key=req.api_key.strip(),
            client_id=req.client_id.strip(),
            encrypted_password=req.password.strip(),
            encrypted_totp_secret=req.totp_secret.strip(),
        )
        logger.info(f"Angel One connected (persistent): {current_user.email} / {req.client_id}")
        return {
            "success":      True,
            "message":      f"Connected to Angel One as {req.client_id}. Session saved — no need to reconnect on page changes.",
            "broker":       "angel_one",
            "client_id":    req.client_id,
            "is_connected": True,
        }
    raise HTTPException(status.HTTP_400_BAD_REQUEST, result.get("error", "Login failed"))


@router.post("/zerodha/connect")
async def connect_zerodha(
    req: ZerodhaConnectRequest,
    current_user: User = Depends(get_current_user),
):
    if not req.api_key.strip() or not req.api_secret.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "API Key and Secret are required")
    login_url = f"https://kite.zerodha.com/connect/login?api_key={req.api_key.strip()}&v=3"
    return {
        "success":   True,
        "message":   "Complete OAuth login via the link below, then paste the request_token from the callback URL.",
        "login_url": login_url,
        "api_key":   req.api_key.strip(),
        "api_secret": req.api_secret.strip(),
        "broker":    "zerodha",
    }


@router.get("/status")
async def broker_status(current_user: User = Depends(get_current_user)):
    """Check broker status — loads from database if not in cache."""
    uid = str(current_user.id)
    brokers = []

    # Check Angel One
    angel_session = await get_session(uid)
    if angel_session:
        brokers.append({
            "broker":         "angel_one",
            "is_connected":   True,
            "client_id":      angel_session.get("client_id"),
            "last_connected":  None,
            "error_message":  None,
        })

    # Check Zerodha
    zerodha_session = await zerodha_get_session(uid)
    if zerodha_session:
        brokers.append({
            "broker":         "zerodha",
            "is_connected":   True,
            "client_id":      zerodha_session.get("login_id"),
            "last_connected":  None,
            "error_message":  None,
        })

    logger.info(f"Broker status for user {uid[:8]}: {len(brokers)} connected")
    return brokers


@router.get("/debug")
async def broker_debug(current_user: User = Depends(get_current_user)):
    """Diagnostic endpoint to debug broker connection issues."""
    uid = str(current_user.id)
    angel_session = await get_session(uid)
    zerodha_session = await zerodha_get_session(uid)
    return {
        "user_id": uid[:16] + "...",
        "angel_one": {
            "in_cache": uid in _session_cache,
            "session_found": angel_session is not None,
            "session_has_token": bool(angel_session.get("jwt_token") if angel_session else False),
            "client_id": angel_session.get("client_id") if angel_session else None,
        },
        "zerodha": {
            "in_cache": uid in _session_cache,
            "session_found": zerodha_session is not None,
            "session_has_token": bool(zerodha_session.get("access_token") if zerodha_session else False),
            "login_id": zerodha_session.get("login_id") if zerodha_session else None,
        },
        "angel_cache_keys": list(_session_cache.keys()),
    }


@router.post("/zerodha/callback")
async def zerodha_callback(
    request_token: str = Body(..., embed=True),
    api_key: str = Body(..., embed=True),
    api_secret: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
):
    """
    Complete Zerodha OAuth flow: exchange request_token for access_token.
    Called after the user logs in via Zerodha and pastes the request_token.
    """
    result = await zerodha_login(api_key, api_secret, request_token)
    if result["success"]:
        await zerodha_store_session(
            user_id=str(current_user.id),
            access_token=result["access_token"],
            api_key=api_key,
            login_id=result["login_id"],
        )
        logger.info(f"Zerodha connected (OAuth): {current_user.email}")
        return {
            "success":      True,
            "message":      f"Connected to Zerodha as {result['login_id']}.",
            "broker":       "zerodha",
            "is_connected": True,
            "login_id":     result["login_id"],
        }
    raise HTTPException(status.HTTP_400_BAD_REQUEST, result.get("error", "Token exchange failed"))


@router.post("/disconnect/{broker}")
async def disconnect_broker(
    broker: str,
    current_user: User = Depends(get_current_user),
):
    """Disconnect broker — removes session from cache and marks inactive in DB."""
    uid = str(current_user.id)
    if broker == "angel_one":
        await clear_session(uid)
    elif broker == "zerodha":
        await zerodha_clear_session(uid)
        from app.services.zerodha import stop_ticker
        stop_ticker(uid)
    return {"success": True, "message": f"Disconnected from {broker}"}
