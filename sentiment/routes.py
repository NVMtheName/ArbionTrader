"""
Sentiment Analysis API Routes for Arbion Trading Platform
Flask blueprint providing sentiment endpoints for tickers.
"""

import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required

logger = logging.getLogger(__name__)

sentiment_bp = Blueprint('sentiment', __name__)


def _get_engine():
    """Lazy import to avoid circular imports at module load time."""
    from sentiment.sentiment_engine import SentimentEngine
    return SentimentEngine()


def _get_aggregator():
    from sentiment.sentiment_aggregator import SentimentAggregator
    return SentimentAggregator()


# ------------------------------------------------------------------
# GET /api/sentiment/<ticker>
# ------------------------------------------------------------------
@sentiment_bp.route('/api/sentiment/<ticker>', methods=['GET'])
@login_required
def get_ticker_sentiment(ticker: str):
    """Return current sentiment signal for a single ticker."""
    try:
        ticker = ticker.upper().strip()
        engine = _get_engine()
        aggregator = _get_aggregator()

        analysis = engine.analyze_ticker(ticker)
        signal = aggregator.aggregate(analysis)

        return jsonify({
            'success': True,
            'sentiment': {
                'ticker': signal.ticker,
                'score': signal.score,
                'momentum': signal.momentum,
                'confidence': signal.confidence,
                'timestamp': signal.timestamp,
                'sources_count': signal.sources_count,
            },
        })

    except Exception as e:
        logger.error(f"Sentiment analysis failed for {ticker}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# GET /api/sentiment/batch?tickers=AAPL,BTC,SPY
# ------------------------------------------------------------------
@sentiment_bp.route('/api/sentiment/batch', methods=['GET'])
@login_required
def get_batch_sentiment():
    """Return sentiment signals for multiple tickers (comma-separated)."""
    try:
        raw = request.args.get('tickers', '')
        if not raw:
            return jsonify({'success': False, 'error': 'tickers query parameter is required'}), 400

        tickers = [t.strip().upper() for t in raw.split(',') if t.strip()]
        if not tickers:
            return jsonify({'success': False, 'error': 'No valid tickers provided'}), 400

        engine = _get_engine()
        aggregator = _get_aggregator()

        analyses = engine.analyze_tickers(tickers)
        signals = aggregator.aggregate_batch(analyses)

        results = {}
        for ticker, signal in signals.items():
            results[ticker] = {
                'ticker': signal.ticker,
                'score': signal.score,
                'momentum': signal.momentum,
                'confidence': signal.confidence,
                'timestamp': signal.timestamp,
                'sources_count': signal.sources_count,
            }

        return jsonify({
            'success': True,
            'sentiments': results,
            'count': len(results),
        })

    except Exception as e:
        logger.error(f"Batch sentiment analysis failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# GET /api/sentiment/trending
# ------------------------------------------------------------------
@sentiment_bp.route('/api/sentiment/trending', methods=['GET'])
@login_required
def get_trending_sentiment():
    """Return top 10 tickers ranked by absolute sentiment momentum.

    Analyses a default watchlist unless ?tickers= is supplied.
    """
    try:
        raw = request.args.get('tickers', '')
        if raw:
            tickers = [t.strip().upper() for t in raw.split(',') if t.strip()]
        else:
            # Default watchlist
            tickers = [
                'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA',
                'AMZN', 'META', 'BTC', 'ETH', 'SPY',
            ]

        engine = _get_engine()
        aggregator = _get_aggregator()

        analyses = engine.analyze_tickers(tickers)
        signals = aggregator.aggregate_batch(analyses)
        trending = aggregator.get_trending(signals, top_n=10)

        results = []
        for signal in trending:
            results.append({
                'ticker': signal.ticker,
                'score': signal.score,
                'momentum': signal.momentum,
                'confidence': signal.confidence,
                'timestamp': signal.timestamp,
                'sources_count': signal.sources_count,
            })

        return jsonify({
            'success': True,
            'trending': results,
            'count': len(results),
        })

    except Exception as e:
        logger.error(f"Trending sentiment analysis failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
