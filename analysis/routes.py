"""
Multi-Timeframe Analysis API Routes for Arbion Trading Platform.
Flask blueprint providing MTF and confluence endpoints.
"""

import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

analysis_bp = Blueprint('analysis', __name__)


def _get_analyzer():
    """Lazy import to avoid circular imports at module load time."""
    from analysis.multi_timeframe import MultiTimeframeAnalyzer
    user_id = str(current_user.id) if current_user and current_user.is_authenticated else None
    return MultiTimeframeAnalyzer(user_id=user_id)


def _get_filter():
    from analysis.confluence_filter import ConfluenceFilter
    return ConfluenceFilter()


# ------------------------------------------------------------------
# GET /api/analysis/mtf/<ticker>
# ------------------------------------------------------------------
@analysis_bp.route('/api/analysis/mtf/<ticker>', methods=['GET'])
@login_required
def get_multi_timeframe_analysis(ticker: str):
    """Return full multi-timeframe breakdown for a ticker."""
    try:
        ticker = ticker.upper().strip()
        analyzer = _get_analyzer()
        signals = analyzer.analyze(ticker)

        return jsonify({
            'success': True,
            'ticker': ticker,
            'timeframes': [s.to_dict() for s in signals],
        })

    except Exception as e:
        logger.error("MTF analysis failed for %s: %s", ticker, e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# GET /api/analysis/confluence/<ticker>
# ------------------------------------------------------------------
@analysis_bp.route('/api/analysis/confluence/<ticker>', methods=['GET'])
@login_required
def get_confluence_score(ticker: str):
    """Return confluence score and trade recommendation for a ticker."""
    try:
        ticker = ticker.upper().strip()
        analyzer = _get_analyzer()
        signals = analyzer.analyze(ticker)

        cf = _get_filter()
        result = cf.evaluate(signals)

        return jsonify({
            'success': True,
            'ticker': ticker,
            'confluence': result.to_dict(),
        })

    except Exception as e:
        logger.error("Confluence analysis failed for %s: %s", ticker, e)
        return jsonify({'success': False, 'error': str(e)}), 500
