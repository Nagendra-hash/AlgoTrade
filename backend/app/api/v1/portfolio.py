"""
Portfolio API — real data from Angel One or Zerodha when connected, sample data as fallback.
Path: backend/app/api/v1/portfolio.py
"""
import asyncio
import logging
import httpx
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.api.v1.users import get_current_user
from app.api.v1.market import _get_quote
from app.services.angel_one import get_session, get_holdings, get_positions, get_funds
from app.services.zerodha import get_session as get_zerodha_session

logger = logging.getLogger(__name__)
router = APIRouter()

# Fallback sample data when no broker is connected
SAMPLE_HOLDINGS = [
    {"symbol": "RELIANCE",  "exchange": "NSE", "quantity": 10, "average_price": 2450.0, "sector": "Energy"},
    {"symbol": "TCS",       "exchange": "NSE", "quantity": 5,  "average_price": 3200.0, "sector": "IT"},
    {"symbol": "INFY",      "exchange": "NSE", "quantity": 20, "average_price": 1450.0, "sector": "IT"},
    {"symbol": "HDFCBANK",  "exchange": "NSE", "quantity": 15, "average_price": 1580.0, "sector": "Banking"},
    {"symbol": "SBIN",      "exchange": "NSE", "quantity": 50, "average_price": 580.0,  "sector": "Banking"},
    {"symbol": "WIPRO",     "exchange": "NSE", "quantity": 30, "average_price": 420.0,  "sector": "IT"},
]


async def _enrich_with_ltp(holdings: list) -> list:
    """Add live LTP and P&L to holdings that don't already have it."""
    tasks = [_get_quote(h["symbol"], h.get("exchange", "NSE")) for h in holdings]
    quotes = await asyncio.gather(*tasks, return_exceptions=True)
    result = []
    for h, q in zip(holdings, quotes):
        if h.get("is_real"):
            # Real data already has ltp/pnl from Angel One
            result.append(h)
        else:
            # Sample data — enrich with live LTP
            ltp   = q.get("ltp", h["average_price"]) if isinstance(q, dict) else h["average_price"]
            qty   = h["quantity"]
            avg   = h["average_price"]
            cur   = qty * ltp
            inv   = qty * avg
            pnl   = cur - inv
            result.append({
                **h,
                "ltp":            round(ltp, 2),
                "current_value":  round(cur, 2),
                "invested_value": round(inv, 2),
                "pnl":            round(pnl, 2),
                "pnl_pct":        round((pnl / inv * 100) if inv else 0, 2),
                "change_pct":     q.get("change_pct", 0) if isinstance(q, dict) else 0,
                "is_real":        False,
            })
    return result


async def _get_zerodha_holdings(user_id: str) -> list:
    """Fetch holdings from Zerodha Kite Connect."""
    session = await get_zerodha_session(user_id)
    if not session or not session.get("access_token"):
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                "https://api.kite.trade/portfolio/holdings",
                headers={
                    "X-Kite-Version": "3",
                    "Authorization": f"token {session['api_key']}:{session['access_token']}",
                },
            )
            data = resp.json()
            if "data" in data and isinstance(data["data"], list):
                result = []
                for h in data["data"]:
                    qty = int(h.get("quantity", 0) or 0)
                    avg = float(h.get("average_price", 0) or 0)
                    ltp = float(h.get("last_price", avg) or avg)
                    pnl = float(h.get("pnl", 0) or 0)
                    pct = float(h.get("pnl_percentage", 0) or 0)
                    cur = float(h.get("current_value", qty * ltp) or qty * ltp)
                    result.append({
                        "symbol": h.get("tradingsymbol", ""),
                        "exchange": h.get("exchange", "NSE"),
                        "quantity": qty,
                        "average_price": round(avg, 2),
                        "ltp": round(ltp, 2),
                        "current_value": round(cur, 2),
                        "invested_value": round(qty * avg, 2),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round(pct, 2),
                        "change_pct": round(float(h.get("day_change_percentage", 0) or 0), 2),
                        "sector": "",
                        "product": h.get("product", "CNC"),
                        "is_real": True,
                    })
                return result
    except Exception as e:
        logger.warning(f"Zerodha holdings failed: {e}")
    return []


async def _get_zerodha_positions(user_id: str) -> list:
    """Fetch positions from Zerodha Kite Connect."""
    session = await get_zerodha_session(user_id)
    if not session or not session.get("access_token"):
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                "https://api.kite.trade/portfolio/positions",
                headers={
                    "X-Kite-Version": "3",
                    "Authorization": f"token {session['api_key']}:{session['access_token']}",
                },
            )
            data = resp.json()
            if "data" in data and isinstance(data["data"], list):
                result = []
                for p in data["data"]:
                    qty = int(p.get("quantity", 0) or 0)
                    if qty == 0:
                        continue
                    avg = float(p.get("average_price", 0) or 0)
                    ltp = float(p.get("last_price", avg) or avg)
                    pnl = float(p.get("pnl", 0) or 0)
                    result.append({
                        "symbol": p.get("tradingsymbol", ""),
                        "exchange": p.get("exchange", "NSE"),
                        "quantity": qty,
                        "average_price": round(avg, 2),
                        "ltp": round(ltp, 2),
                        "pnl": round(pnl, 2),
                        "pnl_pct": round((pnl / (avg * abs(qty)) * 100) if avg and qty else 0, 2),
                        "product_type": p.get("product", "MIS"),
                        "is_real": True,
                    })
                return result
    except Exception as e:
        logger.warning(f"Zerodha positions failed: {e}")
    return []


async def _get_zerodha_funds(user_id: str) -> dict:
    """Fetch funds/margins from Zerodha Kite Connect."""
    session = await get_zerodha_session(user_id)
    if not session or not session.get("access_token"):
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                "https://api.kite.trade/user/margins",
                headers={
                    "X-Kite-Version": "3",
                    "Authorization": f"token {session['api_key']}:{session['access_token']}",
                },
            )
            data = resp.json()
            if "data" in data:
                d = data["data"]
                equity = d.get("equity", {})
                available = equity.get("available", {})
                used = equity.get("utilised", {})
                return {
                    "available_cash": round(float(available.get("cash", 0) or 0), 2),
                    "available_margin": round(float(available.get("margin", 0) or 0), 2),
                    "used_margin": round(float(used.get("debits", 0) or 0), 2),
                    "net": round(float(available.get("cash", 0) or 0) - float(used.get("debits", 0) or 0), 2),
                    "is_real": True,
                }
    except Exception as e:
        logger.warning(f"Zerodha funds failed: {e}")
    return {}


@router.get("/holdings")
async def get_holdings_api(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = str(current_user.id)

    # Try Angel One first
    angel_session = await get_session(user_id)
    if angel_session:
        logger.info(f"Fetching real holdings from Angel One for user {current_user.email}")
        real_holdings = await get_holdings(user_id)
        if real_holdings:
            return {
                "holdings":    real_holdings,
                "source":      "angel_one",
                "is_real":     True,
                "client_id":   angel_session.get("client_id", ""),
                "fetched_at":  datetime.now(timezone.utc).isoformat(),
            }
        return {
            "holdings":  [],
            "source":    "angel_one",
            "is_real":   True,
            "message":   "No holdings found or session expired. Please reconnect in Settings.",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # Try Zerodha second
    zerodha_session = await get_zerodha_session(user_id)
    if zerodha_session:
        logger.info(f"Fetching real holdings from Zerodha for user {current_user.email}")
        real_holdings = await _get_zerodha_holdings(user_id)
        if real_holdings:
            return {
                "holdings":    real_holdings,
                "source":      "zerodha",
                "is_real":     True,
                "login_id":    zerodha_session.get("login_id", ""),
                "fetched_at":  datetime.now(timezone.utc).isoformat(),
            }
        return {
            "holdings":  [],
            "source":    "zerodha",
            "is_real":   True,
            "message":   "No holdings found or session expired. Please reconnect in Settings.",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # No broker connected — never return fake data (Phase 2: real data only)
    return {
        "holdings":     [],
        "source":       "none",
        "is_real":      True,
        "no_live_data": True,
        "message":      "No live data available. Connect Angel One or Zerodha in Broker Settings to load your portfolio.",
        "fetched_at":   datetime.now(timezone.utc).isoformat(),
    }


@router.get("/summary")
async def get_portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = str(current_user.id)

    # Try Angel One
    angel_session = await get_session(user_id)
    if angel_session:
        real_holdings = await get_holdings(user_id)
        funds         = await get_funds(user_id)
        if real_holdings:
            total_inv = sum(h["invested_value"] for h in real_holdings)
            total_cur = sum(h["current_value"]  for h in real_holdings)
            total_pnl = total_cur - total_inv
            pnl_pct   = (total_pnl / total_inv * 100) if total_inv else 0
            day_pnl   = sum(
                h["ltp"] * h["quantity"] * h.get("change_pct", 0) / 100
                for h in real_holdings
            )
            return {
                "total_invested":  round(total_inv, 2),
                "current_value":   round(total_cur, 2),
                "total_pnl":       round(total_pnl, 2),
                "total_pnl_pct":   round(pnl_pct, 2),
                "day_pnl":         round(day_pnl, 2),
                "holdings_count":  len(real_holdings),
                "available_cash":  funds.get("available_cash", 0),
                "available_margin":funds.get("available_margin", 0),
                "source":          "angel_one",
                "is_real":         True,
                "updated_at":      datetime.now(timezone.utc).isoformat(),
            }

    # Try Zerodha
    zerodha_session = await get_zerodha_session(user_id)
    if zerodha_session:
        real_holdings = await _get_zerodha_holdings(user_id)
        funds         = await _get_zerodha_funds(user_id)
        if real_holdings:
            total_inv = sum(h["invested_value"] for h in real_holdings)
            total_cur = sum(h["current_value"]  for h in real_holdings)
            total_pnl = total_cur - total_inv
            pnl_pct   = (total_pnl / total_inv * 100) if total_inv else 0
            day_pnl   = sum(
                h["ltp"] * h["quantity"] * h.get("change_pct", 0) / 100
                for h in real_holdings
            )
            return {
                "total_invested":  round(total_inv, 2),
                "current_value":   round(total_cur, 2),
                "total_pnl":       round(total_pnl, 2),
                "total_pnl_pct":   round(pnl_pct, 2),
                "day_pnl":         round(day_pnl, 2),
                "holdings_count":  len(real_holdings),
                "available_cash":  funds.get("available_cash", 0),
                "available_margin":funds.get("available_margin", 0),
                "source":          "zerodha",
                "is_real":         True,
                "updated_at":      datetime.now(timezone.utc).isoformat(),
            }

    # No broker connected — empty summary, never fake values (Phase 2)
    return {
        "total_invested":   0,
        "current_value":    0,
        "total_pnl":        0,
        "total_pnl_pct":    0,
        "day_pnl":          0,
        "holdings_count":   0,
        "available_cash":   0,
        "available_margin": 0,
        "source":           "none",
        "is_real":          True,
        "no_live_data":     True,
        "message":          "No live data available. Connect a broker in Broker Settings.",
        "updated_at":       datetime.now(timezone.utc).isoformat(),
    }


@router.get("/positions")
async def get_positions_api(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = str(current_user.id)

    angel_session = await get_session(user_id)
    if angel_session:
        real_positions = await get_positions(user_id)
        return {
            "positions": real_positions,
            "source":    "angel_one",
            "is_real":   True,
        }

    zerodha_session = await get_zerodha_session(user_id)
    if zerodha_session:
        real_positions = await _get_zerodha_positions(user_id)
        return {
            "positions": real_positions,
            "source":    "zerodha",
            "is_real":   True,
        }

    return {"positions": [], "source": "none", "is_real": True, "no_live_data": True}


@router.get("/funds")
async def get_funds_api(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = str(current_user.id)

    angel_session = await get_session(user_id)
    if angel_session:
        funds = await get_funds(user_id)
        return {**funds, "source": "angel_one"}

    zerodha_session = await get_zerodha_session(user_id)
    if zerodha_session:
        funds = await _get_zerodha_funds(user_id)
        return {**funds, "source": "zerodha"}

    return {
        "available_cash":   0,
        "available_margin": 0,
        "used_margin":      0,
        "net":              0,
        "source":           "none",
        "is_real":          True,
        "no_live_data":     True,
    }
