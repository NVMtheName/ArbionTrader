"""Shared prompt templates for the swappable Neural Engine.

Every provider implementation (Claude, OpenAI, ...) uses these templates so
behaviour remains identical regardless of which AI is active. Templates use
``{variable}`` placeholders that are formatted at runtime via the
``build_*_prompt`` helpers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# System prompt (applied to every request from every provider)
# ---------------------------------------------------------------------------

TRADING_SYSTEM_PROMPT = """You are an elite quantitative trading analyst embedded in an algorithmic trading system called Arbion.
Your role is to analyze market data, technical signals, sentiment, and market regime to provide
precise, actionable trading decisions.

RULES:
- Always respond with valid JSON matching the requested schema. No markdown, no preamble.
- Base decisions on the data provided, not on general market commentary.
- Be specific: "RSI at 28 on the 1H showing oversold with bullish divergence" not "indicators look bullish"
- Always quantify confidence as a float 0.0-1.0 where:
  - 0.0-0.3 = low confidence (probably shouldn't trade)
  - 0.3-0.6 = moderate confidence (trade with reduced size)
  - 0.6-0.8 = high confidence (standard position size)
  - 0.8-1.0 = very high confidence (can increase size within risk limits)
- Always include a contrarian_view — what could invalidate this analysis
- Never recommend a trade with confidence > 0.9 unless there is extreme signal confluence
- Risk assessment must account for current volatility regime and portfolio exposure
"""


# ---------------------------------------------------------------------------
# Trade analysis
# ---------------------------------------------------------------------------

TRADE_ANALYSIS_PROMPT = """Analyze the following trade setup and provide your decision as JSON.

TICKER: {ticker}
ASSET CLASS: {asset_class}
CURRENT PRICE: {current_price}
TIMEFRAME: 1H

TECHNICAL SIGNALS:
{signals_json}

MARKET DATA (Last 50 bars):
- Price action: {price_summary}
- Volume trend: {volume_trend}
- Volatility (ATR): {atr_value} ({atr_percentile}th percentile vs 60-bar)

SENTIMENT (if available):
{sentiment_json}

CURRENT MARKET REGIME: {regime}

EXISTING PORTFOLIO EXPOSURE:
{portfolio_summary}

Respond ONLY with this JSON structure:
{{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<2-3 sentences>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "risk_assessment": "LOW" | "MEDIUM" | "HIGH" | "EXTREME",
  "suggested_position_size": <float 0.0-1.0>,
  "suggested_sl_pct": <float or null>,
  "suggested_tp_pct": <float or null>,
  "market_context": "<1 sentence>",
  "contrarian_view": "<1-2 sentences>"
}}
"""


# ---------------------------------------------------------------------------
# Portfolio review
# ---------------------------------------------------------------------------

PORTFOLIO_REVIEW_PROMPT = """Review the current portfolio and recommend adjustments. Respond ONLY with JSON.

ACCOUNT SUMMARY:
- Equity: {equity}
- Cash: {cash}
- Gross exposure: {gross_exposure}
- Net exposure: {net_exposure}
- Open P&L: {open_pnl}

OPEN POSITIONS:
{positions_json}

MARKET OVERVIEW:
{market_overview_json}

Evaluate each position for:
1. Whether to hold, trim, add, or close
2. Whether current stop-loss / take-profit levels are still appropriate
3. Correlated / concentrated exposure that increases portfolio risk
4. Any regime-driven adjustments (e.g. tighter stops in high volatility)

Respond ONLY with this JSON structure:
{{
  "overall_health": "STRONG" | "HEALTHY" | "CONCERNING" | "CRITICAL",
  "overall_risk": "LOW" | "MEDIUM" | "HIGH" | "EXTREME",
  "summary": "<2-3 sentence overview>",
  "position_actions": [
    {{
      "ticker": "<symbol>",
      "action": "HOLD" | "TRIM" | "ADD" | "CLOSE",
      "new_sl_pct": <float or null>,
      "new_tp_pct": <float or null>,
      "reasoning": "<1-2 sentences>",
      "urgency": "LOW" | "MEDIUM" | "HIGH"
    }}
  ],
  "concentration_warnings": ["<warning1>", "<warning2>"],
  "rebalance_suggestions": ["<suggestion1>", "<suggestion2>"],
  "contrarian_view": "<what could invalidate this review>"
}}
"""


# ---------------------------------------------------------------------------
# Trade explanation (post-mortem)
# ---------------------------------------------------------------------------

TRADE_EXPLANATION_PROMPT = """Explain what happened in this completed trade and extract the lesson.

TRADE RECORD:
- Ticker: {ticker}
- Direction: {direction}
- Entry price: {entry_price}
- Exit price: {exit_price}
- Entry time: {entry_time}
- Exit time: {exit_time}
- P&L: {pnl} ({pnl_pct}%)
- Outcome: {outcome}
- Exit reason: {exit_reason}

ORIGINAL THESIS / SIGNALS AT ENTRY:
{entry_signals_json}

MARKET CONDITIONS DURING TRADE:
{market_conditions_json}

ORIGINAL NEURAL ANALYSIS (if any):
{original_analysis_json}

Write a concise post-mortem (plain prose, not JSON) covering:
1. What the setup looked like at entry and whether the thesis was sound
2. What actually drove the outcome
3. Whether the stop-loss / take-profit placement was appropriate
4. One specific, actionable lesson for future trades on this ticker or setup
5. What, if anything, should change in the strategy going forward

Keep it under 250 words. Be honest — if the trade was lucky, say so.
"""


# ---------------------------------------------------------------------------
# Morning market brief
# ---------------------------------------------------------------------------

MARKET_BRIEF_PROMPT = """Produce a morning market brief for the trading desk. Plain prose, not JSON.

DATE: {date}
SESSION: {session}

WATCHLIST:
{watchlist_json}

MARKET OVERVIEW:
- Index levels: {index_levels}
- Macro / news headlines: {macro_headlines}
- Current regime: {regime}
- Overnight moves: {overnight_moves}

PER-TICKER DATA:
{ticker_data_json}

Write a tight, desk-ready brief covering:
1. Top-line market context (1-2 sentences)
2. For each ticker in the watchlist: key support/resistance levels, notable overnight catalysts,
   and the most probable setup to watch (breakout, pullback, reversal, no-trade, etc.)
3. Which tickers are highest-priority today and why
4. Risk flags — anything to avoid or size down for

Keep it under 400 words. Be specific with prices and levels. No fluff.
"""


# ---------------------------------------------------------------------------
# Strategy optimization
# ---------------------------------------------------------------------------

STRATEGY_OPTIMIZATION_PROMPT = """Analyze these backtest results and recommend parameter adjustments. Respond ONLY with JSON.

STRATEGY: {strategy_name}
CURRENT PARAMETERS:
{current_params_json}

BACKTEST RESULTS:
- Period: {start_date} to {end_date}
- Total trades: {total_trades}
- Win rate: {win_rate}%
- Profit factor: {profit_factor}
- Sharpe ratio: {sharpe}
- Max drawdown: {max_drawdown}%
- Avg win: {avg_win} / Avg loss: {avg_loss}
- Longest losing streak: {losing_streak}

PER-REGIME BREAKDOWN:
{regime_breakdown_json}

TRADE DISTRIBUTION:
{trade_distribution_json}

Respond ONLY with this JSON structure:
{{
  "diagnosis": "<2-3 sentences identifying the strategy's strengths and weaknesses>",
  "parameter_suggestions": [
    {{
      "param": "<parameter_name>",
      "current_value": <current>,
      "suggested_value": <new>,
      "rationale": "<why this change>",
      "expected_impact": "<what it should improve>"
    }}
  ],
  "regime_recommendations": [
    {{
      "regime": "<regime name>",
      "recommendation": "<action>",
      "reasoning": "<1-2 sentences>"
    }}
  ],
  "confidence": <float 0.0-1.0>,
  "contrarian_view": "<risks of making these changes or overfitting concerns>"
}}
"""


# ---------------------------------------------------------------------------
# Prompt builders — format templates with real runtime data
# ---------------------------------------------------------------------------

def _dump(obj: Any) -> str:
    """JSON-serialise with a readable fallback for non-JSON values."""
    if obj is None:
        return "null"
    try:
        return json.dumps(obj, indent=2, default=str)
    except Exception:
        return str(obj)


def build_trade_analysis_prompt(
    ticker: str,
    market_data: Dict,
    signals: Dict,
    sentiment: Optional[Dict] = None,
    regime: Optional[str] = None,
) -> str:
    return TRADE_ANALYSIS_PROMPT.format(
        ticker=ticker,
        asset_class=market_data.get("asset_class", "unknown"),
        current_price=market_data.get("current_price", "n/a"),
        signals_json=_dump(signals),
        price_summary=market_data.get("price_summary", "n/a"),
        volume_trend=market_data.get("volume_trend", "n/a"),
        atr_value=market_data.get("atr_value", "n/a"),
        atr_percentile=market_data.get("atr_percentile", "n/a"),
        sentiment_json=_dump(sentiment) if sentiment else "none",
        regime=regime or "unknown",
        portfolio_summary=_dump(market_data.get("portfolio_summary", "none")),
    )


def build_portfolio_review_prompt(
    positions: List[Dict],
    market_overview: Dict,
) -> str:
    return PORTFOLIO_REVIEW_PROMPT.format(
        equity=market_overview.get("equity", "n/a"),
        cash=market_overview.get("cash", "n/a"),
        gross_exposure=market_overview.get("gross_exposure", "n/a"),
        net_exposure=market_overview.get("net_exposure", "n/a"),
        open_pnl=market_overview.get("open_pnl", "n/a"),
        positions_json=_dump(positions),
        market_overview_json=_dump(market_overview),
    )


def build_trade_explanation_prompt(trade_record: Dict) -> str:
    return TRADE_EXPLANATION_PROMPT.format(
        ticker=trade_record.get("ticker", "n/a"),
        direction=trade_record.get("direction", "n/a"),
        entry_price=trade_record.get("entry_price", "n/a"),
        exit_price=trade_record.get("exit_price", "n/a"),
        entry_time=trade_record.get("entry_time", "n/a"),
        exit_time=trade_record.get("exit_time", "n/a"),
        pnl=trade_record.get("pnl", "n/a"),
        pnl_pct=trade_record.get("pnl_pct", "n/a"),
        outcome=trade_record.get("outcome", "n/a"),
        exit_reason=trade_record.get("exit_reason", "n/a"),
        entry_signals_json=_dump(trade_record.get("entry_signals")),
        market_conditions_json=_dump(trade_record.get("market_conditions")),
        original_analysis_json=_dump(trade_record.get("original_analysis")),
    )


def build_market_brief_prompt(
    watchlist: List[str],
    market_data: Dict,
) -> str:
    return MARKET_BRIEF_PROMPT.format(
        date=market_data.get("date", "today"),
        session=market_data.get("session", "pre-market"),
        watchlist_json=_dump(watchlist),
        index_levels=_dump(market_data.get("index_levels", "n/a")),
        macro_headlines=_dump(market_data.get("macro_headlines", [])),
        regime=market_data.get("regime", "unknown"),
        overnight_moves=_dump(market_data.get("overnight_moves", {})),
        ticker_data_json=_dump(market_data.get("tickers", {})),
    )


def build_strategy_optimization_prompt(
    backtest_results: Dict,
    current_params: Dict,
) -> str:
    return STRATEGY_OPTIMIZATION_PROMPT.format(
        strategy_name=backtest_results.get("strategy_name", "unknown"),
        current_params_json=_dump(current_params),
        start_date=backtest_results.get("start_date", "n/a"),
        end_date=backtest_results.get("end_date", "n/a"),
        total_trades=backtest_results.get("total_trades", "n/a"),
        win_rate=backtest_results.get("win_rate", "n/a"),
        profit_factor=backtest_results.get("profit_factor", "n/a"),
        sharpe=backtest_results.get("sharpe", "n/a"),
        max_drawdown=backtest_results.get("max_drawdown", "n/a"),
        avg_win=backtest_results.get("avg_win", "n/a"),
        avg_loss=backtest_results.get("avg_loss", "n/a"),
        losing_streak=backtest_results.get("losing_streak", "n/a"),
        regime_breakdown_json=_dump(backtest_results.get("regime_breakdown", {})),
        trade_distribution_json=_dump(backtest_results.get("trade_distribution", {})),
    )
