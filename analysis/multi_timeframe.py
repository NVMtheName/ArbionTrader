"""
Multi-Timeframe Analysis Module for Arbion Trading Platform.

Fetches OHLCV data across 5-minute, 1-hour, and daily timeframes for both
equities (via yfinance / Schwab API) and crypto (via Coinbase Advanced Trade
candles endpoint).  Computes EMA crossover trend, RSI-14, MACD, Bollinger Band
position, and relative volume per timeframe.
"""

import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeframe constants
# ---------------------------------------------------------------------------
TIMEFRAMES = ["5m", "1h", "1d"]

# yfinance interval strings
YF_INTERVALS = {"5m": "5m", "1h": "1h", "1d": "1d"}
# yfinance lookback periods (need enough bars for indicator calculation)
YF_PERIODS = {"5m": "5d", "1h": "60d", "1d": "6mo"}

# Coinbase Advanced Trade granularity strings
CB_GRANULARITIES = {
    "5m": "FIVE_MINUTES",
    "1h": "ONE_HOUR",
    "1d": "ONE_DAY",
}
# Lookback durations in seconds per timeframe
CB_LOOKBACKS = {
    "5m": 5 * 24 * 3600,      # 5 days
    "1h": 60 * 24 * 3600,     # 60 days
    "1d": 180 * 24 * 3600,    # ~6 months
}

# Well-known crypto tickers (checked case-insensitively)
CRYPTO_TICKERS = {
    "BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "AVAX", "DOT", "MATIC",
    "LINK", "UNI", "SHIB", "LTC", "BCH", "ATOM", "NEAR", "APT", "ARB",
    "OP", "FIL", "SUI", "PEPE", "BONK",
}


# ---------------------------------------------------------------------------
# Dataclass returned per timeframe
# ---------------------------------------------------------------------------
@dataclass
class TimeframeSignal:
    """Analysis result for a single timeframe."""
    timeframe: str                    # "5m", "1h", "1d"
    trend: str                        # "bullish", "bearish", "neutral"
    strength: int                     # 0-100
    indicators: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Technical indicator helpers (pure pandas/numpy — no ta-lib required)
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma = series.rolling(window=period).mean()
    rolling_std = series.rolling(window=period).std()
    upper = sma + std_dev * rolling_std
    lower = sma - std_dev * rolling_std
    return upper, sma, lower


def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute all technical indicators on an OHLCV DataFrame.

    Expected columns: open, high, low, close, volume.
    Returns a dict suitable for TimeframeSignal.indicators.
    """
    close = df["close"]
    volume = df["volume"]

    # --- EMAs & trend ---
    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)
    last_ema20 = ema20.iloc[-1]
    last_ema50 = ema50.iloc[-1]
    prev_ema20 = ema20.iloc[-2] if len(ema20) >= 2 else last_ema20
    prev_ema50 = ema50.iloc[-2] if len(ema50) >= 2 else last_ema50

    # Crossover detection: current above and previous below (or vice versa)
    if last_ema20 > last_ema50:
        trend = "bullish"
    elif last_ema20 < last_ema50:
        trend = "bearish"
    else:
        trend = "neutral"

    fresh_cross = (last_ema20 > last_ema50) != (prev_ema20 > prev_ema50)

    # --- RSI ---
    rsi_series = _rsi(close)
    last_rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    # --- MACD ---
    macd_line, signal_line, histogram = _macd(close)
    last_macd = float(macd_line.iloc[-1]) if not macd_line.empty else 0.0
    last_signal = float(signal_line.iloc[-1]) if not signal_line.empty else 0.0
    last_hist = float(histogram.iloc[-1]) if not histogram.empty else 0.0
    prev_hist = float(histogram.iloc[-2]) if len(histogram) >= 2 else 0.0
    macd_crossover = "bullish" if last_hist > 0 and prev_hist <= 0 else (
        "bearish" if last_hist < 0 and prev_hist >= 0 else "none"
    )

    # --- Bollinger Bands ---
    bb_upper, bb_mid, bb_lower = _bollinger_bands(close)
    last_close = float(close.iloc[-1])
    last_bb_upper = float(bb_upper.iloc[-1]) if not bb_upper.empty else last_close
    last_bb_lower = float(bb_lower.iloc[-1]) if not bb_lower.empty else last_close
    last_bb_mid = float(bb_mid.iloc[-1]) if not bb_mid.empty else last_close

    if last_close > last_bb_upper:
        bb_position = "above"
    elif last_close < last_bb_lower:
        bb_position = "below"
    else:
        bb_position = "inside"

    # --- Relative volume ---
    vol_avg_20 = volume.rolling(window=20).mean()
    last_vol = float(volume.iloc[-1]) if not volume.empty else 0
    last_vol_avg = float(vol_avg_20.iloc[-1]) if not vol_avg_20.empty else 1
    relative_volume = round(last_vol / last_vol_avg, 2) if last_vol_avg > 0 else 0.0

    # --- Strength score (0-100) ---
    # Weighted composite: trend alignment + RSI zone + MACD momentum + volume confirmation
    strength = 50  # neutral baseline
    # Trend contribution (+/- 20)
    if trend == "bullish":
        strength += 20
    elif trend == "bearish":
        strength -= 20
    if fresh_cross:
        strength += 5 if trend == "bullish" else -5

    # RSI contribution (+/- 15)
    if last_rsi > 60:
        strength += min(15, int((last_rsi - 60) * 0.375))
    elif last_rsi < 40:
        strength -= min(15, int((40 - last_rsi) * 0.375))

    # MACD contribution (+/- 10)
    if macd_crossover == "bullish":
        strength += 10
    elif macd_crossover == "bearish":
        strength -= 10
    elif last_hist > 0:
        strength += 5
    elif last_hist < 0:
        strength -= 5

    # Volume confirmation (+/- 5)
    if relative_volume > 1.5:
        strength += 5 if trend == "bullish" else -5

    strength = max(0, min(100, strength))

    return {
        "trend": trend,
        "strength": strength,
        "ema20": round(last_ema20, 4),
        "ema50": round(last_ema50, 4),
        "ema_cross": fresh_cross,
        "rsi": round(last_rsi, 2),
        "macd": round(last_macd, 4),
        "macd_signal": round(last_signal, 4),
        "macd_histogram": round(last_hist, 4),
        "macd_crossover": macd_crossover,
        "bb_upper": round(last_bb_upper, 4),
        "bb_mid": round(last_bb_mid, 4),
        "bb_lower": round(last_bb_lower, 4),
        "bb_position": bb_position,
        "relative_volume": relative_volume,
        "last_close": round(last_close, 4),
    }


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def _is_crypto(ticker: str) -> bool:
    """Heuristic: treat as crypto if the base symbol is in CRYPTO_TICKERS or
    if the ticker contains a dash (e.g. BTC-USD)."""
    base = ticker.upper().split("-")[0].split("/")[0]
    return base in CRYPTO_TICKERS


def _fetch_yfinance(ticker: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from yfinance for equities."""
    try:
        import yfinance as yf
        data = yf.download(
            ticker,
            period=YF_PERIODS[timeframe],
            interval=YF_INTERVALS[timeframe],
            progress=False,
            auto_adjust=True,
        )
        if data.empty:
            return None
        # Flatten multi-level columns from yfinance if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        df = data.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        # Ensure required columns exist
        for col in ("open", "high", "low", "close", "volume"):
            if col not in df.columns:
                return None
        return df
    except Exception as e:
        logger.error("yfinance fetch failed for %s/%s: %s", ticker, timeframe, e)
        return None


def _fetch_coinbase_candles(ticker: str, timeframe: str, user_id: str = None) -> Optional[pd.DataFrame]:
    """Fetch OHLCV candles from Coinbase Advanced Trade API.

    Falls back to yfinance with a -USD suffix when the user has no Coinbase
    credentials configured (common for lightweight / demo usage).
    """
    base = ticker.upper().split("-")[0].split("/")[0]
    product_id = f"{base}-USD"

    try:
        from utils.coinbase_advanced_trade import CoinbaseAdvancedTradeClient
        client = CoinbaseAdvancedTradeClient(user_id=user_id or "0")
        if not client.api_key:
            raise ValueError("No Coinbase credentials")

        now = int(time.time())
        start = str(now - CB_LOOKBACKS[timeframe])
        end = str(now)
        granularity = CB_GRANULARITIES[timeframe]

        resp = client.get_product_candles(product_id, start, end, granularity)
        candles = resp.get("candles", [])
        if not candles:
            raise ValueError("Empty candle response")

        rows = []
        for c in candles:
            rows.append({
                "timestamp": int(c["start"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c["volume"]),
            })
        df = pd.DataFrame(rows)
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    except Exception as e:
        logger.warning("Coinbase candle fetch failed for %s/%s (%s); falling back to yfinance",
                        product_id, timeframe, e)
        return _fetch_yfinance(product_id, timeframe)


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

class MultiTimeframeAnalyzer:
    """Fetches OHLCV across 3 timeframes and computes technical indicators."""

    def __init__(self, user_id: str = None):
        self.user_id = user_id

    def analyze(self, ticker: str) -> List[TimeframeSignal]:
        """Run multi-timeframe analysis for *ticker*.

        Returns a list of 3 TimeframeSignal objects (5m, 1h, 1d).
        If data for a timeframe is unavailable, a neutral signal with
        strength 0 is returned so callers always receive 3 items.
        """
        ticker = ticker.upper().strip()
        crypto = _is_crypto(ticker)
        signals: List[TimeframeSignal] = []

        for tf in TIMEFRAMES:
            try:
                if crypto:
                    df = _fetch_coinbase_candles(ticker, tf, self.user_id)
                else:
                    df = _fetch_yfinance(ticker, tf)

                if df is None or len(df) < 50:
                    logger.warning("Insufficient data for %s/%s (%d rows)",
                                   ticker, tf, len(df) if df is not None else 0)
                    signals.append(TimeframeSignal(
                        timeframe=tf, trend="neutral", strength=0,
                        indicators={"error": "insufficient_data"},
                    ))
                    continue

                indicators = compute_indicators(df)
                signals.append(TimeframeSignal(
                    timeframe=tf,
                    trend=indicators["trend"],
                    strength=indicators["strength"],
                    indicators=indicators,
                ))
            except Exception as e:
                logger.error("Multi-timeframe analysis error for %s/%s: %s", ticker, tf, e)
                signals.append(TimeframeSignal(
                    timeframe=tf, trend="neutral", strength=0,
                    indicators={"error": str(e)},
                ))

        return signals
