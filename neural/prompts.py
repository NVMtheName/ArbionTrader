from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

TRADING_SYSTEM_PROMPT = """You are an elite quantitative trading analyst embedded in an algorithmic trading system called Arbion.
Your role is to analyze market data, technical signals, sentiment, and market regime to provide
precise, actionable trading decisions.

RULES:
- Always respond with valid JSON matching the requested schema. No markdown, no preamble.
- Base decisions on the data provided, not on general market commentary.
- Be specific: \"RSI at 28 on the 1H showing oversold with bullish divergence\" not \"indicators look bullish\"
- Always quantify confidence as a float 0.0-1.0 where:
  0.0-0.3 = low confidence (probably shouldn't trade)
  0.3-0.6 = moderate confidence (trade with reduced size)
  0.6-0.8 = high confidence (standard position size)
  0.8-1.0 = very high confidence (can increase size within risk limits)
- Always include a contrarian_view — what could invalidate this analysis
- Never recommend a trade with confidence > 0.9 unless there is extreme signal confluence
- Risk assessment must account for current volatility regime and portfolio exposure"""

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
}}"""

PORTFOLIO_REVIEW_PROMPT = """Review this portfolio and return JSON recommendations.

POSITIONS:
{positions_json}

MARKET OVERVIEW:
{market_overview_json}

Return JSON:
{{
  "overall_risk": "LOW|MEDIUM|HIGH|EXTREME",
  "net_exposure": "<summary>",
  "adjustments": [
    {{"ticker": "<symbol>", "action": "HOLD|TRIM|ADD|EXIT", "reason": "<reason>"}}
  ],
  "hedge_ideas": ["<hedge 1>", "<hedge 2>"],
  "notes": "<brief notes>"
}}"""

TRADE_EXPLANATION_PROMPT = """Explain this completed trade and provide lessons learned in JSON.

TRADE RECORD:
{trade_record_json}

Return JSON:
{{
  "what_happened": "<brief recap>",
  "what_worked": ["<item1>", "<item2>"],
  "what_failed": ["<item1>", "<item2>"],
  "lesson": "<single key lesson>",
  "next_time_adjustments": ["<adj1>", "<adj2>"]
}}"""

MARKET_BRIEF_PROMPT = """Generate a morning market brief in JSON.

WATCHLIST:
{watchlist_json}

MARKET DATA:
{market_data_json}

Return JSON:
{{
  "macro_context": "<1-2 sentences>",
  "watchlist_brief": [
    {{"ticker": "<symbol>", "bias": "BULLISH|BEARISH|NEUTRAL", "key_levels": ["<level>"]}}
  ],
  "top_setups": ["<setup1>", "<setup2>"],
  "risk_events": ["<event1>", "<event2>"]
}}"""

STRATEGY_OPTIMIZATION_PROMPT = """Review backtest output and suggest optimization changes in JSON.

BACKTEST RESULTS:
{backtest_results_json}

CURRENT PARAMS:
{params_json}

Return JSON:
{{
  "keep": ["<param>", "<param>"],
  "adjust": [{{"parameter": "<name>", "from": "<old>", "to": "<new>", "reason": "<why>"}}],
  "discard": ["<pattern>", "<pattern>"],
  "expected_impact": "<summary>"
}}"""


def _pretty(data: Optional[Any], fallback: str = "null") -> str:
    if data is None:
        return fallback
    return json.dumps(data, indent=2, default=str)


def build_trade_analysis_prompt(
    ticker: str,
    market_data: Dict[str, Any],
    signals: Dict[str, Any],
    sentiment: Optional[Dict[str, Any]] = None,
    regime: Optional[str] = None,
    portfolio_summary: Optional[Dict[str, Any]] = None,
) -> str:
    return TRADE_ANALYSIS_PROMPT.format(
        ticker=ticker,
        asset_class=market_data.get("asset_class", "UNKNOWN"),
        current_price=market_data.get("current_price", market_data.get("price", "unknown")),
        signals_json=_pretty(signals, "{}"),
        price_summary=market_data.get("price_summary", "Unavailable"),
        volume_trend=market_data.get("volume_trend", "Unavailable"),
        atr_value=market_data.get("atr", "N/A"),
        atr_percentile=market_data.get("atr_percentile", "N/A"),
        sentiment_json=_pretty(sentiment, "null"),
        regime=regime or "UNKNOWN",
        portfolio_summary=_pretty(portfolio_summary, "{}"),
    )


def build_portfolio_review_prompt(positions: List[Dict[str, Any]], market_overview: Dict[str, Any]) -> str:
    return PORTFOLIO_REVIEW_PROMPT.format(
        positions_json=_pretty(positions, "[]"),
        market_overview_json=_pretty(market_overview, "{}"),
    )


def build_trade_explanation_prompt(trade_record: Dict[str, Any]) -> str:
    return TRADE_EXPLANATION_PROMPT.format(trade_record_json=_pretty(trade_record, "{}"))


def build_market_brief_prompt(watchlist: List[str], market_data: Dict[str, Any]) -> str:
    return MARKET_BRIEF_PROMPT.format(
        watchlist_json=_pretty(watchlist, "[]"),
        market_data_json=_pretty(market_data, "{}"),
    )


def build_strategy_optimization_prompt(backtest_results: Dict[str, Any], params: Dict[str, Any]) -> str:
    return STRATEGY_OPTIMIZATION_PROMPT.format(
        backtest_results_json=_pretty(backtest_results, "{}"),
        params_json=_pretty(params, "{}"),
    )
