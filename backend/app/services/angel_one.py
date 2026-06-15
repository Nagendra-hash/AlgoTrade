"""
Angel One SmartAPI service — persistent sessions via PostgreSQL/Supabase.
Path: backend/app/services/angel_one.py

Session data is stored in the broker_connections table so connections
survive server restarts and page navigations without reconnecting.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.broker import BrokerConnection

logger = logging.getLogger(__name__)
ANGEL_BASE = "https://apiconnect.angelone.in"

# In-memory LRU cache for fast session lookups (avoids DB query on every request)
# Keyed by user_id string, auto-populated from DB on first access
_session_cache: dict = {}


def _headers(api_key: str, jwt_token: str) -> dict:
    return {
        "Authorization":    f"Bearer {jwt_token}",
        "Content-Type":     "application/json",
        "Accept":           "application/json",
        "X-UserType":       "USER",
        "X-SourceID":       "WEB",
        "X-ClientLocalIP":  "127.0.0.1",
        "X-ClientPublicIP": "127.0.0.1",
        "X-MACAddress":     "AA:BB:CC:DD:EE:FF",
        "X-PrivateKey":     api_key,
    }


# ── DB-backed session helpers ──────────────────────────────────

async def _load_from_db(user_id: str) -> Optional[dict]:
    """Load session from database and populate the in-memory cache."""
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.user_id == user_id,
                    BrokerConnection.is_active == True,
                    BrokerConnection.broker_name == "angel_one",
                ).order_by(BrokerConnection.created_at.desc()).limit(1)
            )
            bc = r.scalar_one_or_none()
            if bc and bc.jwt_token:
                data = {
                    "jwt_token":     bc.jwt_token,
                    "refresh_token": bc.refresh_token,
                    "feed_token":    bc.feed_token,
                    "api_key":       bc.api_key,
                    "client_id":     bc.client_id,
                    "encrypted_password": bc.encrypted_password,
                    "encrypted_totp_secret": bc.encrypted_totp_secret,
                    "token_expires_at": bc.token_expires_at,
                    "db_id":         str(bc.id),
                }
                _session_cache[str(user_id)] = data
                logger.info(f"Loaded broker session from DB for user {user_id[:8]}")
                return data
            else:
                # Log why nothing was returned to help diagnose "not showing real data"
                if not bc:
                    logger.warning(f"No active broker_connection found in DB for user {user_id[:8]}")
                elif not bc.jwt_token:
                    logger.warning(f"Broker_connection found for user {user_id[:8]} but jwt_token is empty/missing")
    except Exception as e:
        err_str = str(e)
        # Gracefully handle missing table (migration not run yet)
        if "relation" in err_str and "broker_connections" in err_str:
            logger.warning("broker_connections table does not exist yet — run 'alembic upgrade head'")
        else:
            logger.error(f"Failed to load broker session from DB for user {user_id[:8]}: {e}", exc_info=True)
    return None


async def _save_to_db(user_id: str, data: dict) -> None:
    """Save or update the broker connection record in the database."""
    try:
        async with AsyncSessionLocal() as db:
            # Check if a record already exists
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.user_id == user_id,
                    BrokerConnection.broker_name == "angel_one",
                    BrokerConnection.is_active == True,
                )
            )
            bc = r.scalar_one_or_none()
            now = datetime.now(timezone.utc)

            if bc:
                # Update existing record
                bc.jwt_token = data.get("jwt_token", bc.jwt_token)
                bc.refresh_token = data.get("refresh_token", bc.refresh_token)
                bc.feed_token = data.get("feed_token", bc.feed_token)
                bc.api_key = data.get("api_key", bc.api_key)
                bc.client_id = data.get("client_id", bc.client_id)
                bc.encrypted_password = data.get("encrypted_password", bc.encrypted_password)
                bc.encrypted_totp_secret = data.get("encrypted_totp_secret", bc.encrypted_totp_secret)
                bc.last_connected_at = now
                bc.is_active = True
                bc.error_message = None
                if data.get("jwt_token"):
                    bc.token_expires_at = now + timedelta(hours=24)
            else:
                # Create new record
                import uuid
                bc = BrokerConnection(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    broker_name="angel_one",
                    api_key=data.get("api_key", ""),
                    client_id=data.get("client_id", ""),
                    encrypted_password=data.get("encrypted_password"),
                    encrypted_totp_secret=data.get("encrypted_totp_secret"),
                    jwt_token=data.get("jwt_token"),
                    refresh_token=data.get("refresh_token"),
                    feed_token=data.get("feed_token"),
                    is_active=True,
                    last_connected_at=now,
                    token_expires_at=now + timedelta(hours=24) if data.get("jwt_token") else None,
                )
                db.add(bc)

            await db.commit()
            # Store DB id in cache (only after successful DB write)
            # Guard: caller may not have set cache yet (e.g. store_session writes DB first)
            if str(user_id) in _session_cache:
                _session_cache[str(user_id)]["db_id"] = str(bc.id)
            logger.info(f"Broker session saved to DB for user {user_id[:8]}")
    except Exception as e:
        logger.error(f"Failed to save broker session to DB: {e}")


async def get_session(user_id: str) -> Optional[dict]:
    """Get session — checks in-memory cache first, then loads from DB if needed."""
    uid = str(user_id)
    if uid in _session_cache:
        return _session_cache[uid]
    return await _load_from_db(uid)


async def store_session(
    user_id: str, jwt_token: str, refresh_token: str,
    api_key: str, client_id: str,
    encrypted_password: Optional[str] = None,
    encrypted_totp_secret: Optional[str] = None,
    feed_token: Optional[str] = None,
) -> None:
    """Store session in database first, then cache on success."""
    data = {
        "jwt_token":     jwt_token,
        "refresh_token": refresh_token,
        "api_key":       api_key,
        "client_id":     client_id,
        "feed_token":    feed_token or "",
        "encrypted_password": encrypted_password,
        "encrypted_totp_secret": encrypted_totp_secret,
    }
    # Write to DB first — only cache on success
    await _save_to_db(str(user_id), data)
    _session_cache[str(user_id)] = {**data, "token_expires_at": None, "db_id": None}
    logger.info(f"Angel One session stored for user {str(user_id)[:8]}")


async def clear_session(user_id: str) -> None:
    """Remove session from cache and mark inactive in DB."""
    _session_cache.pop(str(user_id), None)
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.user_id == user_id,
                    BrokerConnection.broker_name == "angel_one",
                    BrokerConnection.is_active == True,
                )
            )
            bc = r.scalar_one_or_none()
            if bc:
                bc.is_active = False
                bc.jwt_token = None
                bc.refresh_token = None
                await db.commit()
                logger.info(f"Broker session cleared from DB for user {user_id[:8]}")
    except Exception as e:
        logger.error(f"Failed to clear broker session: {e}")


async def load_all_active_sessions() -> int:
    """Load all active broker sessions from DB into cache on startup."""
    count = 0
    try:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BrokerConnection).where(
                    BrokerConnection.is_active == True,
                    BrokerConnection.broker_name == "angel_one",
                    BrokerConnection.jwt_token.isnot(None),
                )
            )
            connections = r.scalars().all()
            for bc in connections:
                uid = str(bc.user_id)
                _session_cache[uid] = {
                    "jwt_token":     bc.jwt_token,
                    "refresh_token": bc.refresh_token,
                    "feed_token":    bc.feed_token,
                    "api_key":       bc.api_key,
                    "client_id":     bc.client_id,
                    "encrypted_password": bc.encrypted_password,
                    "encrypted_totp_secret": bc.encrypted_totp_secret,
                    "token_expires_at": bc.token_expires_at,
                    "db_id":         str(bc.id),
                }
                count += 1
        if count:
            logger.info(f"Loaded {count} active broker session(s) from database")
    except Exception as e:
        logger.error(f"Failed to load active sessions: {e}")
    return count


# ── Angel One API calls ───────────────────────────────────────

async def login(api_key: str, client_id: str,
                password: str, totp_secret: str) -> dict:
    """Login to Angel One and return JWT tokens.

    Notes on common user errors (all of these surface as the unhelpful Angel One
    response "Invalid totp and client combination"):

      • `password` must be the 4-digit trading **MPIN**, NOT the web login password.
      • `totp_secret` must be the base32 secret (e.g. "JBSWY3DPEHPK3PXP…"), NOT
        the rotating 6-digit code.
      • `client_id` is the alphanumeric Angel One client code (e.g. "A123456"),
        case-sensitive. Email addresses are rejected by Angel One.
      • `api_key` must be the **SmartAPI** key from smartapi.angelone.in → My Apps.

    This function pre-validates inputs so we return a clear actionable error
    instead of passing junk to Angel One and getting their generic message back.
    """
    api_key     = (api_key or "").strip()
    client_id   = (client_id or "").strip().upper()  # Angel One client IDs are upper-case
    password    = (password or "").strip()
    totp_secret = (totp_secret or "").strip().replace(" ", "")  # base32 secrets often pasted with spaces

    # ── Pre-flight validation ────────────────────────────────────
    if "@" in client_id:
        return {"success": False, "error":
                "Client ID looks like an email. Use your Angel One client code "
                "(e.g. A123456), not your login email."}

    if len(password) > 12 or not password.isdigit():
        # SmartAPI's "password" is actually the trading MPIN (4-6 digits)
        return {"success": False, "error":
                "Password must be your numeric trading MPIN (4 digits), not your "
                "web login password."}

    # TOTP secret must be base32. A 6-digit number means the user pasted the
    # *current code* by mistake — that won't work because it's already expired
    # by the time we send it.
    if totp_secret.isdigit() and len(totp_secret) == 6:
        return {"success": False, "error":
                "TOTP Secret should be the long base32 secret from "
                "smartapi.angelone.in/enable-totp (e.g. JBSWY3DPEHPK3PXP…), "
                "not the rotating 6-digit code shown in your authenticator app."}

    import pyotp, base64
    try:
        # Validate base32 by attempting to decode (pyotp does this lazily)
        base64.b32decode(totp_secret.upper(), casefold=True)
        totp = pyotp.TOTP(totp_secret).now()
    except Exception:
        return {"success": False, "error":
                "TOTP Secret is not a valid base32 string. Re-copy it from "
                "smartapi.angelone.in/enable-totp."}

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.post(
                f"{ANGEL_BASE}/rest/auth/angelbroking/user/v1/loginByPassword",
                headers={
                    "Content-Type": "application/json", "Accept": "application/json",
                    "X-UserType": "USER", "X-SourceID": "WEB",
                    "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "127.0.0.1",
                    "X-MACAddress": "AA:BB:CC:DD:EE:FF", "X-PrivateKey": api_key,
                },
                json={"clientcode": client_id, "password": password, "totp": totp},
            )
            data = resp.json()
            if data.get("status") is True:
                d = data.get("data", {})
                return {
                    "success":       True,
                    "jwt_token":     d.get("jwtToken", ""),
                    "refresh_token": d.get("refreshToken", ""),
                    "feed_token":    d.get("feedToken", ""),
                }
            # Translate Angel One's vague messages into something actionable
            raw = (data.get("message") or "Login failed").strip()
            code = (data.get("errorcode") or data.get("errorCode") or "").strip()
            translated = _translate_angel_error(raw, code)
            logger.warning(f"Angel One login failed: code={code} raw='{raw}' translated='{translated}'")
            return {"success": False, "error": translated}
    except Exception as e:
        return {"success": False, "error": f"Could not reach Angel One: {e}"}


def _translate_angel_error(message: str, code: str) -> str:
    """Convert Angel One's terse error messages into actionable hints."""
    m = message.lower()
    if "totp" in m and ("client" in m or "combination" in m):
        return ("Angel One rejected the credentials. Most common causes:\n"
                "  1. The Password field must be your 4-digit trading MPIN, not the web login password.\n"
                "  2. The TOTP Secret must be the base32 secret from smartapi.angelone.in/enable-totp, "
                "not the rotating 6-digit code.\n"
                "  3. The Client ID must be in upper-case (e.g. A123456).\n"
                "  4. Your server clock may be out of sync (TOTP is time-based).")
    if "client" in m and "exist" in m:
        return "Client ID not recognised by Angel One. Double-check your client code."
    if "invalid password" in m or "password is wrong" in m:
        return "Trading MPIN is wrong. Note: this is the 4-digit PIN, not your web login password."
    if "invalid totp" in m:
        return ("TOTP is invalid — either the secret is wrong, or the server time is out of sync. "
                "Make sure you pasted the base32 secret from smartapi.angelone.in/enable-totp.")
    if "rate" in m or "too many" in m:
        return "Angel One rate-limited the login. Wait a minute before retrying."
    return f"Angel One: {message}"


async def _refresh_token(api_key: str, refresh_token: str) -> Optional[str]:
    """Try to refresh the JWT token using the refresh token."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(
                f"{ANGEL_BASE}/rest/auth/angelbroking/jwt/v1/generate",
                headers={
                    "Content-Type": "application/json",
                    "X-PrivateKey": api_key,
                },
                json={"refreshToken": refresh_token},
            )
            data = resp.json()
            if data.get("status") is True:
                return data.get("data", {}).get("jwtToken", "")
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
    return None


async def _ensure_valid_session(user_id: str) -> Optional[dict]:
    """Check if session exists and JWT is still valid. Try to refresh if expired."""
    session = await get_session(user_id)
    if not session:
        return None

    # Check if token might be expired (Angel One tokens last ~24 hours)
    expires_at = session.get("token_expires_at")
    if expires_at and datetime.now(timezone.utc) > expires_at:
        # Try to refresh using refresh token
        if session.get("refresh_token") and session.get("api_key"):
            logger.info(f"Token expired for user {user_id[:8]}, attempting refresh...")
            new_jwt = await _refresh_token(session["api_key"], session["refresh_token"])
            if new_jwt:
                session["jwt_token"] = new_jwt
                session["token_expires_at"] = datetime.now(timezone.utc) + timedelta(hours=24)
                _session_cache[str(user_id)] = session
                await _save_to_db(str(user_id), {"jwt_token": new_jwt})
                logger.info(f"Token refreshed successfully for user {user_id[:8]}")
                return session
            else:
                logger.warning(f"Token refresh failed for user {user_id[:8]}, will try re-login")
                # Try re-login with stored credentials
                if session.get("encrypted_password") and session.get("encrypted_totp_secret"):
                    pw = session["encrypted_password"]
                    totp = session["encrypted_totp_secret"]
                    if pw and totp:
                        result = await login(session["api_key"], session["client_id"], pw, totp)
                        if result["success"]:
                            session["jwt_token"] = result["jwt_token"]
                            session["refresh_token"] = result["refresh_token"]
                            session["feed_token"] = result["feed_token"]
                            session["token_expires_at"] = datetime.now(timezone.utc) + timedelta(hours=24)
                            _session_cache[str(user_id)] = session
                            await _save_to_db(str(user_id), {
                                "jwt_token": result["jwt_token"],
                                "refresh_token": result["refresh_token"],
                            })
                            logger.info(f"Re-login successful for user {user_id[:8]}")
                            return session
                logger.warning(f"Token fully expired for user {user_id[:8]}")
                return None

    return session


# ── Portfolio API methods ─────────────────────────────────────

async def get_holdings(user_id: str) -> list:
    session = await _ensure_valid_session(user_id)
    if not session:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{ANGEL_BASE}/rest/secure/angelbroking/portfolio/v1/getAllHolding",
                headers=_headers(session["api_key"], session["jwt_token"]),
            )
            data = resp.json()
            if data.get("status") is True:
                hdata = data.get("data", {})
                raw = hdata.get("holdings", []) if isinstance(hdata, dict) else (hdata or [])
                result = []
                for h in raw:
                    qty   = int(h.get("quantity", 0) or 0)
                    avg   = float(h.get("averageprice", 0) or 0)
                    ltp   = float(h.get("ltp", avg) or avg)
                    pnl   = float(h.get("profitandloss", 0) or 0)
                    pct   = float(h.get("pnlpercentage", 0) or 0)
                    cur   = float(h.get("holdingvalue", qty * ltp) or qty * ltp)
                    result.append({
                        "symbol":         h.get("tradingsymbol", ""),
                        "exchange":       h.get("exchange", "NSE"),
                        "isin":           h.get("isin", ""),
                        "quantity":       qty,
                        "average_price":  round(avg, 2),
                        "ltp":            round(ltp, 2),
                        "current_value":  round(cur, 2),
                        "invested_value": round(qty * avg, 2),
                        "pnl":            round(pnl, 2),
                        "pnl_pct":        round(pct, 2),
                        "change_pct":     round(float(h.get("changepct", 0) or 0), 2),
                        "sector":         "",
                        "product":        h.get("product", "CNC"),
                        "is_real":        True,
                    })
                return result
            logger.warning(f"Holdings API: {data.get('message')}")
            return []
    except Exception as e:
        logger.error(f"get_holdings: {e}")
        return []


async def get_positions(user_id: str) -> list:
    session = await _ensure_valid_session(user_id)
    if not session:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{ANGEL_BASE}/rest/secure/angelbroking/order/v1/getPosition",
                headers=_headers(session["api_key"], session["jwt_token"]),
            )
            data = resp.json()
            if data.get("status") is True:
                raw = data.get("data", []) or []
                result = []
                for p in raw:
                    qty = int(p.get("netqty", 0) or 0)
                    if qty == 0:
                        continue
                    avg = float(p.get("netprice", 0) or 0)
                    ltp = float(p.get("ltp", avg) or avg)
                    pnl = float(p.get("pnl", 0) or 0)
                    result.append({
                        "symbol":        p.get("tradingsymbol", ""),
                        "exchange":      p.get("exchange", "NSE"),
                        "quantity":      qty,
                        "average_price": round(avg, 2),
                        "ltp":           round(ltp, 2),
                        "pnl":           round(pnl, 2),
                        "pnl_pct":       round((pnl / (avg * abs(qty)) * 100) if avg and qty else 0, 2),
                        "product_type":  p.get("producttype", "INTRADAY"),
                        "is_real":       True,
                    })
                return result
            return []
    except Exception as e:
        logger.error(f"get_positions: {e}")
        return []


async def get_funds(user_id: str) -> dict:
    session = await _ensure_valid_session(user_id)
    if not session:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{ANGEL_BASE}/rest/secure/angelbroking/user/v1/getRMS",
                headers=_headers(session["api_key"], session["jwt_token"]),
            )
            data = resp.json()
            if data.get("status") is True:
                d = data.get("data", {}) or {}
                return {
                    "available_cash":   round(float(d.get("availablecash", 0) or 0), 2),
                    "available_margin": round(float(d.get("availablemargin", 0) or 0), 2),
                    "used_margin":      round(float(d.get("utilisedmargin", 0) or 0), 2),
                    "net":              round(float(d.get("net", 0) or 0), 2),
                    "is_real":          True,
                }
            return {}
    except Exception as e:
        logger.error(f"get_funds: {e}")
        return {}


# ── Market Data API methods ─────────────────────────────────

# Master contract cache: lazy-loaded from Angel One's OpenAPI scrip master
# Maps (exchange, symbol) -> token
_master_contract: dict[str, dict[str, str]] | None = None
_master_contract_fetched_at: datetime | None = None
MASTER_CONTRACT_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# Fallback token mapping for common NSE symbols when master contract unavailable
_FALLBACK_TOKENS: dict[str, str] = {
    "RELIANCE": "2885", "TCS": "11536", "INFY": "1594",
    "HDFCBANK": "341249", "ICICIBANK": "4963", "SBIN": "3045",
    "WIPRO": "3787", "BAJFINANCE": "1660", "TATAMOTORS": "3456",
    "HINDUNILVR": "1394", "ADANIENT": "25", "BHARTIARTL": "1065",
    "ASIANPAINT": "113", "MARUTI": "2506", "SUNPHARMA": "3383",
    "NIFTY50": "99926000", "BANKNIFTY": "99926012", "SENSEX": "99919000",
}

# Reverse mapping of what the token would be as a symbol suffix (NSE equity uses -EQ)
_NSE_EQUITY_SYMBOLS: set[str] = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "WIPRO",
    "BAJFINANCE", "TATAMOTORS", "HINDUNILVR", "ADANIENT", "BHARTIARTL",
    "ASIANPAINT", "MARUTI", "SUNPHARMA",
}


async def _ensure_master_contract() -> dict[str, dict[str, str]]:
    """
    Fetch and cache the Angel One master contract (symbol -> token mapping).
    Returns dict: {exchange: {symbol: token}}
    Refetches once per hour.
    """
    global _master_contract, _master_contract_fetched_at
    now = datetime.now(timezone.utc)
    if _master_contract is not None and _master_contract_fetched_at and (now - _master_contract_fetched_at).total_seconds() < 3600:
        return _master_contract

    try:
        logger.info("Fetching Angel One master contract...")
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.get(MASTER_CONTRACT_URL)
            if resp.status_code == 200:
                data = resp.json()
                contract: dict[str, dict[str, str]] = {}
                if isinstance(data, list):
                    for entry in data:
                        exch = (entry.get("exch_seg") or "").strip()
                        sym = (entry.get("symbol") or "").strip()
                        token = (entry.get("token") or "").strip()
                        if exch and sym and token:
                            if exch not in contract:
                                contract[exch] = {}
                            # Store both symbol and symboltoken fields
                            contract[exch][sym] = token
                            st = (entry.get("symboltoken") or "").strip()
                            if st and st != token:
                                contract[exch][sym + "_token"] = st
                _master_contract = contract
                _master_contract_fetched_at = now
                nse_count = len(contract.get("NSE", {}))
                logger.info(f"Master contract loaded: {len(contract)} exchanges, {nse_count} NSE symbols")
                return contract
            else:
                logger.warning(f"Master contract fetch returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Failed to fetch master contract: {e}")

    # Use empty dict if fetch fails - fallback tokens will be used
    if _master_contract is None:
        _master_contract = {}
        _master_contract_fetched_at = now
    return _master_contract


def _get_angel_symbol(symbol: str, exchange: str) -> str:
    """Convert our symbol format to Angel One's tradingsymbol format."""
    sym = symbol.upper()
    if exchange == "NSE" and sym in _NSE_EQUITY_SYMBOLS:
        return f"{sym}-EQ"
    if exchange == "NSE" and sym in ("NIFTY50", "BANKNIFTY", "SENSEX"):
        return sym  # Indices use the same name
    return sym


async def get_symbol_token(symbol: str, exchange: str = "NSE") -> Optional[str]:
    """
    Look up a symbol's Angel One token. Checks master contract first,
    then falls back to hardcoded mapping.
    """
    sym = symbol.upper()
    angel_sym = _get_angel_symbol(sym, exchange)

    # Try master contract first
    contract = await _ensure_master_contract()
    exch_map = contract.get(exchange, {})
    if angel_sym in exch_map:
        return exch_map[angel_sym]

    # Try without -EQ suffix in case master contract has it differently
    if angel_sym.endswith("-EQ") and angel_sym[:-3] in exch_map:
        return exch_map[angel_sym[:-3]]

    # Fallback to hardcoded tokens
    token = _FALLBACK_TOKENS.get(sym)
    if token:
        return token

    logger.warning(f"No Angel One token found for {exchange}:{symbol}")
    return None


async def get_market_quote_angel(user_id: str, symbol: str, exchange: str = "NSE") -> Optional[dict]:
    """
    Get real-time quote from Angel One SmartAPI.
    Returns None if unavailable (will fall back to yfinance).
    """
    session = await _ensure_valid_session(user_id)
    if not session:
        return None

    sym = symbol.upper()
    token = await get_symbol_token(sym, exchange)
    if not token:
        return None

    angel_sym = _get_angel_symbol(sym, exchange)

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(
                f"{ANGEL_BASE}/rest/secure/angelbroking/order/v1/getLtpData",
                headers=_headers(session["api_key"], session["jwt_token"]),
                json={
                    "exchange": exchange,
                    "tradingsymbols": [angel_sym],
                    "symboltokens": [token],
                },
            )
            data = resp.json()
            if data.get("status") is True:
                ltp_data = data.get("data", {}) or {}
                ltp = float(ltp_data.get("ltp", 0) or 0)

                # Also fetch full quote for open/high/low/change
                return await _get_full_quote(session, exchange, angel_sym, token, ltp)
            else:
                logger.warning(f"Angel One LTP API error for {sym}: {data.get('message')}")
                return None
    except Exception as e:
        logger.warning(f"Angel One market quote failed for {sym}: {e}")
        return None


async def _get_full_quote(session: dict, exchange: str, angel_sym: str, token: str, ltp: float) -> dict:
    """Fetch full quote data from Angel One market quote endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(
                f"{ANGEL_BASE}/rest/secure/angelbroking/market/v1/quote",
                headers=_headers(session["api_key"], session["jwt_token"]),
                json={
                    "exchange": exchange,
                    "tradingsymbols": [angel_sym],
                    "symboltokens": [token],
                },
            )
            data = resp.json()
            if data.get("status") is True and data.get("data"):
                raw = data["data"]
                # Response can be a list or dict
                if isinstance(raw, list) and len(raw) > 0:
                    q = raw[0]
                elif isinstance(raw, dict):
                    q = raw
                else:
                    return _build_minimal_quote(ltp)

                open_p = float(q.get("open", 0) or 0)
                high = float(q.get("high", 0) or 0)
                low = float(q.get("low", 0) or 0)
                close_p = float(q.get("close", 0) or 0)
                prev = float(q.get("previous_close", close_p) or close_p) or ltp
                change = ltp - prev
                change_pct = (change / prev * 100) if prev else 0
                volume = int(q.get("volume", 0) or 0)

                return {
                    "ltp": round(ltp, 2),
                    "open": round(open_p or ltp, 2),
                    "high": round(high or ltp, 2),
                    "low": round(low or ltp, 2),
                    "prev_close": round(prev, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "volume": volume,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "angel_one",
                }
            else:
                return _build_minimal_quote(ltp)
    except Exception as e:
        logger.warning(f"Full quote fetch failed: {e}")
        return _build_minimal_quote(ltp)


def _build_minimal_quote(ltp: float) -> dict:
    """Build a minimal quote object when only LTP is available."""
    return {
        "ltp": round(ltp, 2),
        "open": round(ltp, 2),
        "high": round(ltp, 2),
        "low": round(ltp, 2),
        "prev_close": round(ltp, 2),
        "change": 0,
        "change_pct": 0,
        "volume": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "angel_one",
    }


INTERVAL_MAP = {
    "1m": "ONE_MINUTE", "5m": "FIVE_MINUTES", "15m": "FIFTEEN_MINUTES",
    "30m": "THIRTY_MINUTES", "1h": "ONE_HOUR", "1d": "ONE_DAY",
    "1w": "ONE_WEEK",
}


async def get_market_candles_angel(
    user_id: str, symbol: str, exchange: str,
    interval: str, from_date: str, to_date: str,
) -> Optional[list]:
    """
    Get historical candle data from Angel One SmartAPI.
    Returns None if unavailable (will fall back to yfinance).
    """
    session = await _ensure_valid_session(user_id)
    if not session:
        return None

    sym = symbol.upper()
    token = await get_symbol_token(sym, exchange)
    if not token:
        return None

    angel_interval = INTERVAL_MAP.get(interval)
    if not angel_interval:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(
                f"{ANGEL_BASE}/rest/secure/angelbroking/historical/v1/getCandleData",
                headers=_headers(session["api_key"], session["jwt_token"]),
                json={
                    "exchange": exchange,
                    "symboltoken": token,
                    "interval": angel_interval,
                    "fromdate": from_date,
                    "todate": to_date,
                },
            )
            data = resp.json()
            if data.get("status") is True:
                raw = data.get("data", [])
                if isinstance(raw, list) and len(raw) > 0:
                    result = []
                    for entry in raw:
                        # Format: [timestamp_ms, open, high, low, close, volume]
                        if isinstance(entry, list) and len(entry) >= 6:
                            t_ms = entry[0]
                            t = int(t_ms) // 1000 if t_ms > 1e11 else int(t_ms)
                            result.append({
                                "time": t,
                                "open": round(float(entry[1]), 2),
                                "high": round(float(entry[2]), 2),
                                "low": round(float(entry[3]), 2),
                                "close": round(float(entry[4]), 2),
                                "volume": int(entry[5]),
                                "source": "angel_one",
                            })
                    if result:
                        return sorted(result, key=lambda x: x["time"])
    except Exception as e:
        logger.warning(f"Angel One candles failed for {sym}: {e}")

    return None


async def get_order_book(user_id: str) -> list:
    session = await _ensure_valid_session(user_id)
    if not session:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{ANGEL_BASE}/rest/secure/angelbroking/order/v1/getOrderBook",
                headers=_headers(session["api_key"], session["jwt_token"]),
            )
            data = resp.json()
            if data.get("status") is True:
                raw = data.get("data", []) or []
                return [{
                    "order_id":      o.get("orderid", ""),
                    "symbol":        o.get("tradingsymbol", ""),
                    "exchange":      o.get("exchange", "NSE"),
                    "side":          o.get("transactiontype", ""),
                    "order_type":    o.get("ordertype", ""),
                    "product_type":  o.get("producttype", ""),
                    "quantity":      int(o.get("quantity", 0) or 0),
                    "price":         float(o.get("price", 0) or 0),
                    "average_price": float(o.get("averageprice", 0) or 0),
                    "filled_qty":    int(o.get("filledshares", 0) or 0),
                    "status":        o.get("status", ""),
                    "placed_at":     o.get("updatetime", ""),
                    "is_real":       True,
                } for o in raw]
            return []
    except Exception as e:
        logger.error(f"get_order_book: {e}")
        return []
