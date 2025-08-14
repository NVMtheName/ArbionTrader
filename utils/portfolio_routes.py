from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.portfolio_analytics import PortfolioAnalytics
from utils.sample_data_generator import generate_sample_portfolio_data, clear_sample_data
import logging

logger = logging.getLogger(__name__)

portfolio_bp = Blueprint('portfolio', __name__, url_prefix='/portfolio')

@portfolio_bp.route('/dashboard')
@login_required
def dashboard():
    """Portfolio analytics dashboard"""
    try:
        analytics = PortfolioAnalytics()
        
        # Get overview data
        period_days = request.args.get('period', 30, type=int)
        overview = analytics.get_portfolio_overview(current_user.id, period_days)
        
        return render_template('portfolio/dashboard.html', 
                             overview=overview,
                             period_days=period_days)
    except Exception as e:
        logger.error(f"Error loading portfolio dashboard: {str(e)}")
        flash(f"Error loading dashboard: {str(e)}", 'error')
        return redirect(url_for('main.dashboard'))

@portfolio_bp.route('/api/overview')
@login_required
def api_overview():
    """API endpoint for portfolio overview data"""
    try:
        analytics = PortfolioAnalytics()
        period_days = request.args.get('period', 30, type=int)
        overview = analytics.get_portfolio_overview(current_user.id, period_days)
        return jsonify(overview)
    except Exception as e:
        logger.error(f"Error getting portfolio overview: {str(e)}")
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/api/strategy-comparison')
@login_required
def api_strategy_comparison():
    """API endpoint for strategy comparison data"""
    try:
        analytics = PortfolioAnalytics()
        period_days = request.args.get('period', 90, type=int)
        comparison = analytics.get_strategy_comparison(current_user.id, period_days)
        return jsonify(comparison)
    except Exception as e:
        logger.error(f"Error getting strategy comparison: {str(e)}")
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/api/risk-metrics')
@login_required
def api_risk_metrics():
    """API endpoint for risk metrics"""
    try:
        analytics = PortfolioAnalytics()
        risk_metrics = analytics.get_risk_metrics(current_user.id)
        return jsonify(risk_metrics)
    except Exception as e:
        logger.error(f"Error getting risk metrics: {str(e)}")
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/api/performance-timeline')
@login_required
def api_performance_timeline():
    """API endpoint for performance timeline data"""
    try:
        analytics = PortfolioAnalytics()
        period_days = request.args.get('period', 30, type=int)
        timeline = analytics.get_performance_timeline(current_user.id, period_days)
        return jsonify(timeline)
    except Exception as e:
        logger.error(f"Error getting performance timeline: {str(e)}")
        return jsonify({'error': str(e)}), 500

@portfolio_bp.route('/performance')
@login_required
def performance():
    """Detailed performance analytics page"""
    try:
        analytics = PortfolioAnalytics()
        
        # Get strategy comparison data
        strategy_comparison = analytics.get_strategy_comparison(current_user.id, 90)
        risk_metrics = analytics.get_risk_metrics(current_user.id)
        
        return render_template('portfolio/performance.html',
                             strategy_comparison=strategy_comparison,
                             risk_metrics=risk_metrics)
    except Exception as e:
        logger.error(f"Error loading performance page: {str(e)}")
        flash(f"Error loading performance data: {str(e)}", 'error')
        return redirect(url_for('portfolio.dashboard'))

@portfolio_bp.route('/risk-analysis')
@login_required
def risk_analysis():
    """Risk analysis and metrics page"""
    try:
        analytics = PortfolioAnalytics()
        risk_metrics = analytics.get_risk_metrics(current_user.id)
        
        return render_template('portfolio/risk_analysis.html',
                             risk_metrics=risk_metrics)
    except Exception as e:
        logger.error(f"Error loading risk analysis: {str(e)}")
        flash(f"Error loading risk analysis: {str(e)}", 'error')
        return redirect(url_for('portfolio.dashboard'))

@portfolio_bp.route('/generate-sample-data')
@login_required
def generate_sample_data():
    """Generate sample trading data for testing"""
    try:
        result = generate_sample_portfolio_data(current_user.id, 50)
        if result['success']:
            flash(f"Generated {result['trades_created']} sample trades for testing", 'success')
        else:
            flash(f"Error generating sample data: {result['error']}", 'error')
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
    
    return redirect(url_for('portfolio.dashboard'))

@portfolio_bp.route('/clear-sample-data')
@login_required
def clear_sample_data_route():
    """Clear all sample trading data"""
    try:
        result = clear_sample_data(current_user.id)
        if result['success']:
            flash(f"Cleared {result['deleted_count']} trades", 'success')
        else:
            flash(f"Error clearing data: {result['error']}", 'error')
    except Exception as e:
        flash(f"Error: {str(e)}", 'error')
    
    return redirect(url_for('portfolio.dashboard'))