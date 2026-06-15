"""
Auto-Trading Engine — the brain of automated trading.

Monitors deployed strategies, generates real-time signals from market data,
executes orders via connected brokers, and manages positions with
stop-loss, take-profit, trailing stops, and risk limits.

Path: backend/app/services/auto_trade_engine.py
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.strategy import Strategy, StrategyStatus
from app.models.order import Order, OrderSide, OrderType, OrderStatus, ProductType
from app.websockets.notification_ws import notification_manager
from app.core.redis import redis_publish
from app.services.telegram_service import send_telegram_message

logger = logging.getLogger(__name__)

# ── NSE symbol → Yahoo Finance mapping ────────────────────────
NSE_TO_YF = {
    "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "WIPRO": "WIPRO.NS", "BAJFINANCE": "BAJFINANCE.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "ADANIENT": "ADANIENT.NS", "HINDUNILVR": "HINDUNILVR.NS", "MARUTI": "MARUTI.NS",
    "SUNPHARMA": "SUNPHARMA.NS", "BHARTIARTL": "BHARTIARTL.NS", "ASIANPAINT": "ASIANPAINT.NS",
    "NIFTY50": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN",
}


@dataclass
class Position:
    """Tracks an open position managed by the engine."""
    id: str
    user_id: str
    strategy_id: str
    symbol: str
    exchange: str
    side: str  # BUY or SELL
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    trailing_stop_pct: float = 0.0
    trailing_stop_price: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float("inf")
    entry_time: str = ""
    broker_order_id: str = ""
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    status: str = "OPEN"  # OPEN, STOPPED, TAKE_PROFIT, CLOSED


@dataclass
class EngineState:
    """Persistent state for the auto-trading engine."""
    is_running: bool = False
    mode: str = "paper"  # paper or live
    active_strategies: Dict[str, dict] = field(default_factory=dict)
    positions: Dict[str, Position] = field(default_factory=dict)
    today_trades: List[dict] = field(default_factory=list)
    today_pnl: float = 0.0
    total_trades_today: int = 0
    wins_today: int = 0
    losses_today: int = 0
    last_signal_time: Dict[str, datetime] = field(default_factory=dict)
    risk_config: dict = field(default_factory=lambda: {
        "max_daily_loss_pct": 5.0,
        "max_position_size_pct": 10.0,
        "max_open_positions": 5,
        "max_trades_per_day": 20,
        "trailing_stop_enabled": True,
        "trailing_stop_pct": 1.5,
    })


class AutoTradeEngine:
    """
    Core auto-trading engine.

    Lifecycle:
    1. Starts on server boot (called from main.py lifespan)
    2. Polls every 30 seconds for deployed strategies
    3. Fetches live market data for strategy symbols
    4. Generates buy/sell signals based on strategy logic
    5. Executes orders via connected broker (paper or live)
    6. Monitors open positions for stop-loss / take-profit
    7. Enforces risk limits (max drawdown, position sizing, daily loss)
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._state = EngineState()
        self._price_cache: Dict[str, dict] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._tick_lock = asyncio.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._state.is_running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("🤖 Auto-Trade Engine started")

    def stop(self) -> None:
        self._running = False
        self._state.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("🛑 Auto-Trade Engine stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def state(self) -> EngineState:
        return self._state

    def get_status(self) -> dict:
        """Return engine status for API / frontend."""
        return {
            "is_running": self._running,
            "mode": self._state.mode,
            "active_strategies": len(self._state.active_strategies),
            "open_positions": len([p for p in self._state.positions.values() if p.status == "OPEN"]),
            "today_trades": self._state.total_trades_today,
            "today_pnl": round(self._state.today_pnl, 2),
            "win_rate": round(
                (self._state.wins_today / self._state.total_trades_today * 100)
                if self._state.total_trades_today > 0 else 0, 2
            ),
            "risk_config": self._state.risk_config,
        }

    def get_positions(self) -> List[dict]:
        """Return all open positions."""
        return [
            {
                "id": p.id,
                "symbol": p.symbol,
                "exchange": p.exchange,
                "side": p.side,
                "entry_price": p.entry_price,
                "quantity": p.quantity,
                "current_price": p.current_price,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "pnl": round(p.pnl, 2),
                "pnl_pct": round(p.pnl_pct, 2),
                "entry_time": p.entry_time,
                "status": p.status,
                "strategy_id": p.strategy_id,
            }
            for p in self._state.positions.values()
        ]

    def get_today_activity(self) -> List[dict]:
        """Return today's trading activity."""
        return self._state.today_trades[-50:]  # Last 50 trades

    def update_risk_config(self, config: dict) -> None:
        """Update risk management configuration."""
        self._state.risk_config.update(config)
        logger.info(f"Risk config updated: {config}")

    def set_mode(self, mode: str) -> None:
        """Switch between paper and live trading."""
        if mode not in ("paper", "live"):
            return
        self._state.mode = mode
        logger.info(f"Trading mode set to: {mode}")

    # ── Main loop ───────────────────────────────────────────────

    async def _main_loop(self) -> None:
        """Main engine loop — runs every 30 seconds."""
        while self._running:
            try:
                if not self._tick_lock.locked():
                    async with self._tick_lock:
                        await self._tick()
            except Exception as e:
                logger.error(f"Auto-trade engine tick error: {e}", exc_info=True)
            await asyncio.sleep(30)

    async def _tick(self) -> None:
        """Single engine tick: refresh strategies → generate signals → execute → manage positions."""
        # 1. Refresh active strategies from DB
        await self._refresh_active_strategies()

        # 2. Check risk limits before trading
        if not self._check_risk_limits():
            logger.warning("⛔ Risk limits reached — skipping signal generation")
            return

        # 3. Fetch market data for all strategy symbols
        all_symbols = set()
        for strat in self._state.active_strategies.values():
            symbols = strat.get("symbols", [])
            if isinstance(symbols, list):
                all_symbols.update(s.upper() for s in symbols)

        if all_symbols:
            await self._fetch_market_prices(list(all_symbols))

        # 4. Generate signals and execute trades for each strategy
        for strat_id, strat in self._state.active_strategies.items():
            await self._process_strategy(strat_id, strat)

        # 5. Monitor open positions (stop-loss, take-profit, trailing stop)
        await self._manage_positions()

        # 6. Broadcast portfolio update
        await self._broadcast_update()

    # ── Strategy management ─────────────────────────────────────

    async def _refresh_active_strategies(self) -> None:
        """Load all deployed strategies from database."""
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Strategy).filter(
                        Strategy.status == "active",
                    )
                )
                strategies = result.scalars().all()

                active = {}
                for s in strategies:
                    if s.is_paper_active or s.is_live_active:
                        active[str(s.id)] = {
                            "id": str(s.id),
                            "user_id": str(s.user_id),
                            "name": s.name,
                            "strategy_type": s.strategy_type,
                            "symbols": s.symbols or [],
                            "timeframe": s.timeframe,
                            "exchange": s.exchange,
                            "parameters": s.parameters or {},
                            "stop_loss_pct": s.stop_loss_pct,
                            "take_profit_pct": s.take_profit_pct,
                            "trailing_stop_enabled": s.trailing_stop_enabled,
                            "trailing_stop_pct": s.trailing_stop_pct,
                            "max_position_size": s.max_position_size,
                            "max_drawdown_pct": s.max_drawdown_pct,
                            "is_paper_active": s.is_paper_active,
                            "is_live_active": s.is_live_active,
                            "python_code": s.python_code,
                        }

                self._state.active_strategies = active
        except Exception as e:
            logger.error(f"Failed to refresh strategies: {e}")

    # ── Market data ─────────────────────────────────────────────

    async def _fetch_market_prices(self, symbols: List[str]) -> None:
        """Fetch live prices for symbols using Yahoo Finance v8 API."""
        import httpx

        now = datetime.now()
        to_fetch = [
            s for s in symbols
            if s not in self._price_cache
            or (now - self._cache_time.get(s, datetime.min)).seconds > 25
        ]

        if not to_fetch:
            return

        loop = asyncio.get_event_loop()
        yf_base = "https://query1.finance.yahoo.com/v8/finance/chart"
        yf_headers = {"User-Agent": "Mozilla/5.0"}

        def _fetch_batch(syms: list) -> dict:
            results = {}
            for sym in syms:
                yf_sym = NSE_TO_YF.get(sym, sym + ".NS")
                try:
                    with httpx.Client(timeout=10) as client:
                        resp = client.get(
                            f"{yf_base}/{yf_sym}?interval=1d&range=1d",
                            headers=yf_headers,
                        )
                        resp.raise_for_status()
                        data = resp.json()

                    result = data["chart"]["result"][0]
                    meta = result["meta"]
                    ltp = float(meta.get("regularMarketPrice", 0) or 0)
                    prev = float(meta.get("chartPreviousClose", ltp) or ltp)
                    change_pct = ((ltp - prev) / prev * 100) if prev else 0
                    results[sym] = {
                        "ltp": ltp,
                        "prev_close": prev,
                        "change_pct": round(change_pct, 2),
                        "source": "yahoo_finance",
                    }
                except Exception as e:
                    logger.warning(f"Price fetch failed for {sym}: {e}")
            return results

        prices = await loop.run_in_executor(None, _fetch_batch, to_fetch)
        for sym, data in prices.items():
            self._price_cache[sym] = data
            self._cache_time[sym] = now

    def _get_price(self, symbol: str) -> Optional[float]:
        """Get cached LTP for a symbol."""
        cached = self._price_cache.get(symbol.upper())
        if cached:
            return cached.get("ltp")
        return None

    # ── Signal generation ───────────────────────────────────────

    @staticmethod
    def _get_param_value(params: dict, key: str, default):
        """
        Extract a parameter value, handling both flat values and nested
        {"value": X} dicts returned by the AI-generated strategy schemas.
        """
        val = params.get(key, default)
        if isinstance(val, dict) and "value" in val:
            return val["value"]
        return val

    async def _process_strategy(self, strat_id: str, strat: dict) -> None:
        """Process a single strategy: generate signals and execute trades."""
        symbols = strat.get("symbols", [])
        if not symbols:
            return

        timeframe = strat.get("timeframe", "1d")
        strategy_type = strat.get("strategy_type", "trend_following")
        params = strat.get("parameters", {})

        for symbol in symbols:
            symbol = symbol.upper()
            current_price = self._get_price(symbol)
            if not current_price or current_price <= 0:
                continue

            # Check if we already have a position for this symbol
            existing = self._find_position(symbol, strat_id)
            if existing and existing.status == "OPEN":
                continue  # Already in a position

            # Check cooldown (don't re-enter same symbol within 5 minutes)
            last_time = self._state.last_signal_time.get(f"{strat_id}:{symbol}")
            if last_time and (datetime.now(timezone.utc) - last_time).seconds < 300:
                continue

            # Generate signal — pass strat_id so ai_brain knows whose user to fetch AI config for
            strat["id"] = strat_id
            signal = await self._generate_signal(
                symbol, strategy_type, timeframe, params, strat
            )

            if signal == 1:  # BUY signal
                await self._execute_buy(strat_id, strat, symbol, current_price)
            elif signal == -1:  # SELL signal (for positions we might want to short)
                pass  # Only buy signals for equity market (no shorting in delivery)

    async def _generate_signal(
        self, symbol: str, strategy_type: str, timeframe: str,
        params: dict, strat: dict
    ) -> int:
        """
        Generate a trading signal based on strategy type.

        Returns: 1 (BUY), -1 (SELL), 0 (HOLD)
        """
        import numpy as np
        import httpx

        yf_sym = NSE_TO_YF.get(symbol, symbol + ".NS")

        try:
            loop = asyncio.get_event_loop()

            def _fetch_history() -> list:
                period_map = {
                    "1m": "5d", "5m": "5d", "15m": "5d", "30m": "5d",
                    "1h": "1mo", "1d": "6mo", "1w": "2y",
                }
                yf_interval_map = {
                    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                    "1h": "60m", "1d": "1d", "1w": "1wk",
                }
                yf_range = period_map.get(timeframe, "6mo")
                yf_iv = yf_interval_map.get(timeframe, "1d")

                try:
                    with httpx.Client(timeout=15) as client:
                        resp = client.get(
                            f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}?interval={yf_iv}&range={yf_range}",
                            headers={"User-Agent": "Mozilla/5.0"},
                        )
                        resp.raise_for_status()
                        data = resp.json()

                    result = data["chart"]["result"][0]
                    quotes = result["indicators"]["quote"][0]
                    closes = [c for c in (quotes.get("close") or []) if c is not None]
                    return closes if closes else []
                except Exception as e:
                    logger.warning(f"History fetch failed for {yf_sym}: {e}")
                    return []

            closes = await loop.run_in_executor(None, _fetch_history)

            if len(closes) < 30:
                return 0

            fast = int(self._get_param_value(params, "fast_period", 20))
            slow = int(self._get_param_value(params, "slow_period", 50))

            sma_fast = np.mean(closes[-fast:])
            sma_slow = np.mean(closes[-slow:])
            prev_fast = np.mean(closes[-(fast + 1):-1])
            prev_slow = np.mean(closes[-(slow + 1):-1])

            if strategy_type == "trend_following":
                # SMA crossover: fast crosses above slow = BUY
                if sma_fast > sma_slow and prev_fast <= prev_slow:
                    return 1
                elif sma_fast < sma_slow and prev_fast >= prev_slow:
                    return -1

            elif strategy_type == "hybrid_trend_momentum":
                # Hybrid: Trend Following + Momentum confirmation
                roc_period = int(self._get_param_value(params, "roc_period", 10))
                roc = ((closes[-1] / closes[-roc_period]) - 1) * 100 if len(closes) > roc_period else 0
                # Entry: SMA crossover AND momentum ROC > 1%
                if sma_fast > sma_slow and prev_fast <= prev_slow and roc > 1.0:
                    return 1
                # Exit: Trend reversal or momentum fizzled
                elif sma_fast < sma_slow and prev_fast >= prev_slow:
                    return -1
                elif roc < 0:
                    return -1

            elif strategy_type == "momentum":
                roc_period = int(self._get_param_value(params, "roc_period", 10))
                roc_threshold = float(self._get_param_value(params, "roc_threshold", 2.0))
                if len(closes) > roc_period:
                    roc = ((closes[-1] / closes[-roc_period]) - 1) * 100
                    if roc > roc_threshold:
                        return 1
                    elif roc < -roc_threshold:
                        return -1

            elif strategy_type == "mean_reversion":
                bb_std = float(self._get_param_value(params, "bb_std", 2.5))
                sma20 = np.mean(closes[-20:])
                std20 = np.std(closes[-20:])
                if closes[-1] < sma20 - bb_std * std20:
                    return 1  # Buy at lower band
                elif closes[-1] > sma20 + bb_std * std20:
                    return -1  # Sell at upper band

            elif strategy_type == "ai_brain":
                # LLM-driven decision — AI evaluates technicals + sentiment + news.
                # The AI's suggested SL/TP/qty_pct are stashed on the strategy dict
                # so _execute_buy can honour them. Falls back to rule-based if no AI.
                from app.services.ai_brain import make_decision
                from app.core.database import AsyncSessionLocal

                user_id = self._get_user_id_for_strategy(strat["id"]) if "id" in strat else strat.get("user_id")
                if not user_id:
                    return 0

                async with AsyncSessionLocal() as session:
                    decision = await make_decision(
                        db=session, user_id=str(user_id),
                        symbol=symbol, closes=closes,
                    )

                # Stash the decision back on the strat dict for _execute_buy to read
                strat["_ai_decision"] = decision.as_dict()
                logger.info(
                    f"🧠 AI-brain {symbol}: {decision.decision} "
                    f"(conf={decision.confidence}, sl={decision.sl_pct}%, tp={decision.tp_pct}%, "
                    f"qty={decision.qty_pct}%, via {decision.provider})"
                )

                if decision.decision == "BUY":
                    return 1
                if decision.decision == "SELL":
                    return -1
                return 0

            # Default: use saved python_code if available
            python_code = strat.get("python_code")
            if python_code:
                signal = self._execute_custom_code(python_code, closes)
                if signal is not None:
                    return signal

        except Exception as e:
            logger.warning(f"Signal generation failed for {symbol}: {e}")

        return 0

    def _execute_custom_code(self, code: str, closes: list) -> Optional[int]:
        """
        DEPRECATED — custom Python execution removed for security (was CVE risk via `exec()`).

        AI-generated strategies now route through the built-in strategy_type
        dispatch ('trend_following', 'momentum', 'mean_reversion', 'hybrid_trend_momentum').
        The AI populates `parameters` (fast_period, slow_period, roc_period, bb_std, etc.)
        which drive the safe built-in handlers above.

        Returns None — caller falls back to its strategy_type branch.
        """
        if code:
            logger.debug(
                "_execute_custom_code is deprecated and disabled for security. "
                "Use strategy_type + parameters instead. Code length: %d chars.",
                len(code or ""),
            )
        return None

    # ── Order execution ─────────────────────────────────────────

    async def _execute_buy(
        self, strat_id: str, strat: dict, symbol: str, price: float
    ) -> None:
        """Execute a buy order for a strategy signal.

        If the strategy generated an AI-brain decision (strat["_ai_decision"]),
        the AI's suggested SL/TP/position-size override the static config values.
        """
        # AI-brain decision overrides (if present)
        ai = strat.get("_ai_decision") or {}
        ai_qty_pct  = ai.get("qty_pct")
        ai_sl_pct   = ai.get("sl_pct")
        ai_tp_pct   = ai.get("tp_pct")
        ai_reason   = ai.get("reasoning")
        ai_conf     = ai.get("confidence")

        position_size_pct = (ai_qty_pct if ai_qty_pct is not None else strat.get("max_position_size", 10.0)) / 100.0
        stop_loss_pct     = (ai_sl_pct  if ai_sl_pct  is not None else strat.get("stop_loss_pct", 2.0))  / 100.0
        take_profit_pct   = (ai_tp_pct  if ai_tp_pct  is not None else strat.get("take_profit_pct", 4.0)) / 100.0

        # Calculate position size
        capital = self._state.risk_config.get("trading_capital", 100000)
        max_alloc = capital * position_size_pct
        qty = int(max_alloc / price) if price > 0 else 0

        if qty <= 0:
            return

        stop_loss = round(price * (1 - stop_loss_pct), 2)
        take_profit = round(price * (1 + take_profit_pct), 2)

        # Create order record
        order_id = str(uuid.uuid4())
        broker_order_id = ""

        # Execute via broker or paper trade
        if self._state.mode == "paper":
            broker_order_id = f"PAPER-{order_id[:8]}"
            logger.info(
                f"📋 Paper BUY: {qty} {symbol} @ ₹{price:,.2f} "
                f"(SL: ₹{stop_loss:,.2f}, TP: ₹{take_profit:,.2f})"
            )
        else:
            # Live trading — route to broker
            broker_order_id = await self._route_order_to_broker(
                symbol=symbol, exchange=strat.get("exchange", "NSE"),
                side="BUY", quantity=qty, price=price,
                order_type="MARKET", strategy_id=strat_id,
            )
            if not broker_order_id:
                logger.error(f"Failed to place live order for {symbol}")
                return

        # Save order to DB
        await self._save_order(
            user_id=self._get_user_id_for_strategy(strat_id),
            symbol=symbol, exchange=strat.get("exchange", "NSE"),
            side="BUY", quantity=qty, price=price,
            stop_loss=stop_loss, take_profit=take_profit,
            broker_order_id=broker_order_id, strategy_id=strat_id,
        )

        # Create position
        position = Position(
            id=order_id,
            user_id=self._get_user_id_for_strategy(strat_id),
            strategy_id=strat_id,
            symbol=symbol,
            exchange=strat.get("exchange", "NSE"),
            side="BUY",
            entry_price=price,
            quantity=qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_pct=strat.get("trailing_stop_pct", self._state.risk_config.get("trailing_stop_pct", 1.5)),
            highest_price=price,
            entry_time=datetime.now(timezone.utc).isoformat(),
            broker_order_id=broker_order_id,
            current_price=price,
        )
        self._state.positions[order_id] = position
        self._state.last_signal_time[f"{strat_id}:{symbol}"] = datetime.now(timezone.utc)

        # Log trade
        self._state.total_trades_today += 1
        self._state.today_trades.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "symbol": symbol,
            "action": "BUY",
            "qty": qty,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "COMPLETE",
            "mode": self._state.mode,
            "strategy": strat.get("name", ""),
            "reason": ai_reason if ai_reason else None,
            "ai_confidence": ai_conf if ai_conf else None,
            "ai_provider": ai.get("provider") if ai else None,
        })

        # Notify user
        await self._send_notification(
            position.user_id,
            f"🟢 BUY {qty} {symbol} @ ₹{price:,.2f}",
            f"Stop Loss: ₹{stop_loss:,.2f} | Take Profit: ₹{take_profit:,.2f}",
            symbol=symbol,
        )

    async def _execute_sell(self, position: Position, reason: str) -> None:
        """Execute a sell order to close a position."""
        price = position.current_price or self._get_price(position.symbol) or position.entry_price
        pnl = (price - position.entry_price) * position.quantity
        pnl_pct = ((price - position.entry_price) / position.entry_price * 100) if position.entry_price else 0

        broker_order_id = ""

        if self._state.mode == "paper":
            broker_order_id = f"PAPER-SELL-{position.id[:8]}"
            logger.info(
                f"📋 Paper SELL: {position.quantity} {position.symbol} @ ₹{price:,.2f} "
                f"(P&L: ₹{pnl:,.2f} / {pnl_pct:.2f}%) — {reason}"
            )
        else:
            broker_order_id = await self._route_order_to_broker(
                symbol=position.symbol, exchange=position.exchange,
                side="SELL", quantity=position.quantity, price=price,
                order_type="MARKET", strategy_id=position.strategy_id,
            )

        # Save order to DB
        await self._save_order(
            user_id=position.user_id,
            symbol=position.symbol, exchange=position.exchange,
            side="SELL", quantity=position.quantity, price=price,
            broker_order_id=broker_order_id, strategy_id=position.strategy_id,
        )

        # Update position
        position.status = "CLOSED"
        position.pnl = pnl
        position.pnl_pct = pnl_pct

        # Update daily stats
        self._state.today_pnl += pnl
        if pnl > 0:
            self._state.wins_today += 1
        else:
            self._state.losses_today += 1

        self._state.total_trades_today += 1
        self._state.today_trades.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "symbol": position.symbol,
            "action": "SELL",
            "qty": position.quantity,
            "price": price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "status": "COMPLETE",
            "mode": self._state.mode,
        })

        # Remove position
        self._state.positions.pop(position.id, None)

        # Notify user
        emoji = "🟢" if pnl > 0 else "🔴"
        await self._send_notification(
            position.user_id,
            f"{emoji} SELL {position.quantity} {position.symbol} @ ₹{price:,.2f}",
            f"P&L: ₹{pnl:,.2f} ({pnl_pct:.2f}%) — {reason}",
            symbol=position.symbol,
        )

    async def _route_order_to_broker(
        self, symbol: str, exchange: str, side: str, quantity: int,
        price: float, order_type: str, strategy_id: str,
    ) -> str:
        """Route an order to the connected broker (Angel One or Zerodha)."""
        # Try Angel One first
        from app.services.angel_one import get_session as get_angel
        from app.services.zerodha import get_session as get_zerodha

        # We need user_id — get it from strategy
        user_id = self._get_user_id_for_strategy(strategy_id)

        angel_session = await get_angel(user_id)
        if angel_session:
            return await self._place_angel_order(
                angel_session, symbol, exchange, side, quantity,
                price, order_type
            )

        zerodha_session = await get_zerodha(user_id)
        if zerodha_session:
            return await self._place_zerodha_order(
                zerodha_session, symbol, exchange, side, quantity,
                price, order_type
            )

        logger.warning(f"No broker connected for user {user_id[:8]}")
        return ""

    async def _place_angel_order(
        self, session: dict, symbol: str, exchange: str, side: str,
        quantity: int, price: float, order_type: str,
    ) -> str:
        """Place an order via Angel One SmartAPI."""
        import httpx
        from app.services.angel_one import get_symbol_token, _headers, _get_angel_symbol

        token = await get_symbol_token(symbol, exchange)
        if not token:
            logger.error(f"No Angel One token for {symbol}")
            return ""

        angel_sym = _get_angel_symbol(symbol, exchange)
        angel_order_type = {
            "MARKET": "MARKET", "LIMIT": "LIMIT",
            "STOP_LOSS": "STOP_LOSS_LIMIT", "STOP_LOSS_MARKET": "STOP_LOSS_MARKET",
        }.get(order_type, "MARKET")

        try:
            async with httpx.AsyncClient(timeout=15) as c:
                resp = await c.post(
                    f"https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/placeOrder",
                    headers=_headers(session["api_key"], session["jwt_token"]),
                    json={
                        "exchange": exchange,
                        "tradingsymbol": angel_sym,
                        "transactiontype": side,
                        "ordertype": angel_order_type,
                        "product": "INTRADAY",
                        "duration": "DAY",
                        "quantity": str(quantity),
                        "price": str(price) if order_type != "MARKET" else "0",
                    },
                )
                data = resp.json()
                if data.get("status") is True:
                    order_id = data.get("data", {}).get("orderid", "")
                    logger.info(f"Angel One order placed: {order_id}")
                    return str(order_id)
                else:
                    logger.error(f"Angel One order failed: {data.get('message')}")
                    return ""
        except Exception as e:
            logger.error(f"Angel One order error: {e}")
            return ""

    async def _place_zerodha_order(
        self, session: dict, symbol: str, exchange: str, side: str,
        quantity: int, price: float, order_type: str,
    ) -> str:
        """Place an order via Zerodha Kite Connect."""
        import httpx
        from app.services.zerodha import _kite_headers, _get_kite_symbol

        kite_sym = _get_kite_symbol(symbol, exchange)
        kite_order_type = {
            "MARKET": "MARKET", "LIMIT": "LIMIT",
            "STOP_LOSS": "SL", "STOP_LOSS_MARKET": "SL-M",
        }.get(order_type, "MARKET")

        try:
            async with httpx.AsyncClient(timeout=15) as c:
                resp = await c.post(
                    "https://api.kite.trade/orders",
                    headers=_kite_headers(session["access_token"], session["api_key"]),
                    data={
                        "exchange": exchange,
                        "tradingsymbol": kite_sym.replace(f"{exchange}:", ""),
                        "transaction_type": side,
                        "order_type": kite_order_type,
                        "product": "MIS",
                        "validity": "DAY",
                        "quantity": str(quantity),
                        "price": str(price) if order_type != "MARKET" else "",
                    },
                )
                data = resp.json()
                if "data" in data and data["data"].get("order_id"):
                    order_id = data["data"]["order_id"]
                    logger.info(f"Zerodha order placed: {order_id}")
                    return str(order_id)
                else:
                    logger.error(f"Zerodha order failed: {data}")
                    return ""
        except Exception as e:
            logger.error(f"Zerodha order error: {e}")
            return ""

    # ── Position management ─────────────────────────────────────

    async def _manage_positions(self) -> None:
        """Monitor all open positions for stop-loss, take-profit, and trailing stop."""
        positions_to_close: list = []

        for pos_id, pos in self._state.positions.items():
            if pos.status != "OPEN":
                continue

            current_price = self._get_price(pos.symbol)
            if not current_price:
                continue

            pos.current_price = current_price
            pos.pnl = (current_price - pos.entry_price) * pos.quantity
            pos.pnl_pct = ((current_price - pos.entry_price) / pos.entry_price * 100) if pos.entry_price else 0

            # Update trailing stop — per-strategy setting, falling back to global config
            strat_trailing = self._state.active_strategies.get(pos.strategy_id, {})
            trailing_enabled = strat_trailing.get("trailing_stop_enabled",
                                               self._state.risk_config.get("trailing_stop_enabled", True))
            if trailing_enabled:
                if current_price > pos.highest_price:
                    pos.highest_price = current_price
                    trailing_pct = pos.trailing_stop_pct / 100
                    new_trailing_stop = round(current_price * (1 - trailing_pct), 2)
                    if new_trailing_stop > pos.stop_loss:
                        pos.stop_loss = new_trailing_stop
                        logger.debug(f"Trailing stop updated for {pos.symbol}: ₹{pos.stop_loss:,.2f}")

            # Check stop-loss
            if current_price <= pos.stop_loss:
                pos.status = "STOPPED"
                positions_to_close.append((pos, "Stop Loss Hit"))
                continue

            # Check take-profit
            if current_price >= pos.take_profit:
                pos.status = "TAKE_PROFIT"
                positions_to_close.append((pos, "Take Profit Hit"))
                continue

        # Execute closes
        for pos, reason in positions_to_close:
            await self._execute_sell(pos, reason)

    # ── Risk management ─────────────────────────────────────────

    def _check_risk_limits(self) -> bool:
        """Check if we're within risk limits before placing new trades."""
        rc = self._state.risk_config

        # Max trades per day
        if self._state.total_trades_today >= rc.get("max_trades_per_day", 20):
            logger.warning("Max daily trades reached")
            return False

        # Max daily loss
        capital = rc.get("trading_capital", 100000)
        max_loss = capital * (rc.get("max_daily_loss_pct", 5.0) / 100)
        if self._state.today_pnl < -max_loss:
            logger.warning(f"Max daily loss reached: ₹{self._state.today_pnl:,.2f}")
            return False

        # Max open positions
        open_count = len([p for p in self._state.positions.values() if p.status == "OPEN"])
        if open_count >= rc.get("max_open_positions", 5):
            logger.warning("Max open positions reached")
            return False

        return True

    # ── Helpers ─────────────────────────────────────────────────

    def _find_position(self, symbol: str, strategy_id: str) -> Optional[Position]:
        """Find an open position for a symbol + strategy."""
        for pos in self._state.positions.values():
            if pos.symbol == symbol and pos.strategy_id == strategy_id and pos.status == "OPEN":
                return pos
        return None

    def _get_user_id_for_strategy(self, strategy_id: str) -> str:
        """Get user_id from active strategies cache."""
        strat = self._state.active_strategies.get(strategy_id)
        if strat:
            return strat.get("user_id", "unknown")
        return "unknown"

    async def _save_order(
        self, user_id: str, symbol: str, exchange: str, side: str,
        quantity: int, price: float, broker_order_id: str,
        strategy_id: str, stop_loss: float = 0, take_profit: float = 0,
    ) -> None:
        """Save order to database."""
        try:
            async with AsyncSessionLocal() as db:
                order = Order(
                    user_id=user_id,
                    symbol=symbol,
                    exchange=exchange,
                    side=OrderSide(side),
                    order_type=OrderType.MARKET,
                    product_type=ProductType.INTRADAY,
                    status=OrderStatus.COMPLETE,
                    quantity=quantity,
                    price=price,
                    average_price=price,
                    filled_quantity=quantity,
                    stop_loss=stop_loss if stop_loss > 0 else None,
                    take_profit=take_profit if take_profit > 0 else None,
                    broker_order_id=broker_order_id,
                    strategy_id=strategy_id,
                    is_paper_trade="true" if self._state.mode == "paper" else "false",
                    executed_at=datetime.now(timezone.utc),
                )
                db.add(order)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save order: {e}")

    async def _send_notification(
        self, user_id: str, title: str, message: str, symbol: str = ""
    ) -> None:
        """Send notification via WebSocket, Redis, and optionally Telegram."""
        payload = {
            "type": "auto_trade",
            "data": {
                "title": title,
                "message": message,
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        try:
            await notification_manager.send_to_user(user_id, payload)
            await redis_publish(f"notifications:{user_id}", payload)

            # Also send via Telegram if user has a bot configured
            try:
                from sqlalchemy import select
                from app.models.user import User
                async with AsyncSessionLocal() as db:
                    r = await db.execute(select(User).where(User.id == user_id))
                    user = r.scalar_one_or_none()
                    if user and user.telegram_bot_token and user.telegram_chat_id:
                        telegram_text = f"{title}\n{message}\n\n📋 Paper TradeAI" if self._state.mode == "paper" else f"{title}\n{message}\n\n💵 Live TradeAI"
                        await send_telegram_message(
                            bot_token=user.telegram_bot_token,
                            chat_id=user.telegram_chat_id,
                            text=telegram_text,
                        )
            except Exception as e:
                logger.debug(f"Telegram notification failed: {e}")
        except Exception as e:
            logger.debug(f"Notification send failed: {e}")

    async def _broadcast_update(self) -> None:
        """Broadcast portfolio update to all connected users."""
        try:
            for pos in self._state.positions.values():
                if pos.status == "OPEN" and pos.user_id:
                    payload = {
                        "type": "portfolio_update",
                        "data": {"timestamp": datetime.now(timezone.utc).isoformat()},
                    }
                    await notification_manager.send_to_user(pos.user_id, payload)
        except Exception:
            pass


# Singleton instance
auto_trade_engine = AutoTradeEngine()
