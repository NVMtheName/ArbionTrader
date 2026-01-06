"""
Options Trading Utilities
Provides helpers for options trading strategies including pricing, Greeks calculations, and strategy logic
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import random

logger = logging.getLogger(__name__)


class OptionsCalculator:
    """Calculator for options pricing and Greeks"""

    @staticmethod
    def calculate_option_price(stock_price: float, strike: float, days_to_expiration: int,
                               volatility: float = 0.25, is_call: bool = True) -> float:
        """
        Simplified Black-Scholes option pricing

        Args:
            stock_price: Current stock price
            strike: Option strike price
            days_to_expiration: Days until expiration
            volatility: Implied volatility (default 25%)
            is_call: True for call options, False for puts

        Returns:
            Estimated option price
        """
        try:
            # Simplified pricing model for demonstration
            # In production, you'd use a proper Black-Scholes implementation
            time_value = days_to_expiration / 365.0

            if is_call:
                intrinsic_value = max(0, stock_price - strike)
            else:
                intrinsic_value = max(0, strike - stock_price)

            # Time value decreases as expiration approaches
            time_premium = stock_price * volatility * math.sqrt(time_value)

            option_price = intrinsic_value + time_premium

            return round(option_price, 2)

        except Exception as e:
            logger.error(f"Error calculating option price: {e}")
            return 0.0

    @staticmethod
    def calculate_delta(stock_price: float, strike: float, days_to_expiration: int,
                       volatility: float = 0.25, is_call: bool = True) -> float:
        """
        Calculate option delta (price sensitivity to underlying)

        Args:
            stock_price: Current stock price
            strike: Option strike price
            days_to_expiration: Days until expiration
            volatility: Implied volatility
            is_call: True for call, False for put

        Returns:
            Delta value between -1 and 1
        """
        try:
            # Simplified delta calculation
            moneyness = (stock_price - strike) / stock_price
            time_factor = math.sqrt(days_to_expiration / 365.0)

            if is_call:
                # Call delta ranges from 0 to 1
                if stock_price > strike:
                    delta = 0.5 + (moneyness * 2)
                else:
                    delta = 0.5 - abs(moneyness * 2)
            else:
                # Put delta ranges from -1 to 0
                if stock_price < strike:
                    delta = -0.5 - abs(moneyness * 2)
                else:
                    delta = -0.5 + (moneyness * 2)

            # Clamp delta to valid range
            if is_call:
                delta = max(0.05, min(0.95, delta))
            else:
                delta = max(-0.95, min(-0.05, delta))

            return round(delta, 2)

        except Exception as e:
            logger.error(f"Error calculating delta: {e}")
            return 0.5 if is_call else -0.5


class WheelStrategy:
    """Implements the Wheel options strategy"""

    def __init__(self):
        self.calculator = OptionsCalculator()

    def find_strike_for_target_delta(self, stock_price: float, target_delta: float,
                                     dte: int, is_call: bool = True) -> Tuple[float, float]:
        """
        Find strike price that matches target delta

        Args:
            stock_price: Current stock price
            target_delta: Target delta (e.g., 0.30 for 30 delta)
            dte: Days to expiration
            is_call: True for call, False for put

        Returns:
            Tuple of (strike_price, actual_delta)
        """
        try:
            # Start with ATM strike
            strike_increment = stock_price * 0.01  # 1% increments

            if is_call:
                # For calls, higher strike = lower delta
                strike = stock_price
                for _ in range(20):  # Try up to 20% OTM
                    delta = self.calculator.calculate_delta(stock_price, strike, dte, is_call=True)
                    if abs(delta - target_delta) < 0.05:
                        return round(strike, 2), delta
                    strike += strike_increment
            else:
                # For puts, lower strike = lower delta (less negative)
                strike = stock_price
                for _ in range(20):  # Try up to 20% OTM
                    delta = self.calculator.calculate_delta(stock_price, strike, dte, is_call=False)
                    if abs(abs(delta) - target_delta) < 0.05:
                        return round(strike, 2), delta
                    strike -= strike_increment

            # Default to reasonable OTM strike
            if is_call:
                return round(stock_price * 1.05, 2), target_delta
            else:
                return round(stock_price * 0.95, 2), -target_delta

        except Exception as e:
            logger.error(f"Error finding strike for delta: {e}")
            return stock_price, target_delta if is_call else -target_delta

    def get_cash_secured_put_details(self, symbol: str, stock_price: float,
                                    target_delta: float = 0.30, dte: int = 30) -> Dict:
        """
        Generate cash-secured put trade details

        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            target_delta: Target delta for the put
            dte: Days to expiration

        Returns:
            Dictionary with trade details
        """
        try:
            strike, actual_delta = self.find_strike_for_target_delta(
                stock_price, target_delta, dte, is_call=False
            )

            premium = self.calculator.calculate_option_price(
                stock_price, strike, dte, is_call=False
            )

            # Cash requirement is strike * 100 (shares per contract)
            cash_required = strike * 100

            # Calculate potential returns
            premium_collected = premium * 100
            return_on_risk = (premium_collected / cash_required) * 100
            annualized_return = (return_on_risk * 365 / dte)

            expiration_date = datetime.now() + timedelta(days=dte)

            return {
                'strategy': 'cash_secured_put',
                'symbol': symbol,
                'stock_price': stock_price,
                'strike': strike,
                'expiration_date': expiration_date.strftime('%Y-%m-%d'),
                'days_to_expiration': dte,
                'delta': actual_delta,
                'premium': premium,
                'premium_collected': premium_collected,
                'cash_required': cash_required,
                'return_on_risk': round(return_on_risk, 2),
                'annualized_return': round(annualized_return, 2),
                'max_profit': premium_collected,
                'max_loss': cash_required - premium_collected,
                'breakeven': round(strike - premium, 2)
            }

        except Exception as e:
            logger.error(f"Error generating CSP details: {e}")
            return {}

    def get_covered_call_details(self, symbol: str, stock_price: float,
                                target_delta: float = 0.30, dte: int = 30,
                                shares_owned: int = 100) -> Dict:
        """
        Generate covered call trade details

        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            target_delta: Target delta for the call
            dte: Days to expiration
            shares_owned: Number of shares owned (must be multiple of 100)

        Returns:
            Dictionary with trade details
        """
        try:
            strike, actual_delta = self.find_strike_for_target_delta(
                stock_price, target_delta, dte, is_call=True
            )

            premium = self.calculator.calculate_option_price(
                stock_price, strike, dte, is_call=True
            )

            # Calculate returns
            premium_collected = premium * 100
            position_value = stock_price * shares_owned
            return_on_position = (premium_collected / position_value) * 100
            annualized_return = (return_on_position * 365 / dte)

            # Calculate if called away
            capital_gain = (strike - stock_price) * shares_owned
            total_return = premium_collected + capital_gain

            expiration_date = datetime.now() + timedelta(days=dte)

            return {
                'strategy': 'covered_call',
                'symbol': symbol,
                'stock_price': stock_price,
                'strike': strike,
                'expiration_date': expiration_date.strftime('%Y-%m-%d'),
                'days_to_expiration': dte,
                'delta': actual_delta,
                'premium': premium,
                'premium_collected': premium_collected,
                'shares_covered': shares_owned,
                'position_value': position_value,
                'return_on_position': round(return_on_position, 2),
                'annualized_return': round(annualized_return, 2),
                'capital_gain_if_called': capital_gain,
                'total_return_if_called': round(total_return, 2),
                'upside_capped_at': strike
            }

        except Exception as e:
            logger.error(f"Error generating CC details: {e}")
            return {}


class CollarStrategy:
    """Implements the Collar options strategy"""

    def __init__(self):
        self.calculator = OptionsCalculator()

    def get_collar_details(self, symbol: str, stock_price: float,
                          shares_owned: int = 100,
                          put_delta: float = 0.20,
                          call_delta: float = 0.30,
                          dte: int = 30) -> Dict:
        """
        Generate collar strategy trade details

        A collar consists of:
        - Long stock position
        - Buy protective put (downside protection)
        - Sell covered call (finance the put)

        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            shares_owned: Shares owned
            put_delta: Target delta for protective put
            call_delta: Target delta for covered call
            dte: Days to expiration

        Returns:
            Dictionary with collar trade details
        """
        try:
            wheel_strategy = WheelStrategy()

            # Find protective put strike (below current price)
            put_strike, actual_put_delta = wheel_strategy.find_strike_for_target_delta(
                stock_price, put_delta, dte, is_call=False
            )

            # Find covered call strike (above current price)
            call_strike, actual_call_delta = wheel_strategy.find_strike_for_target_delta(
                stock_price, call_delta, dte, is_call=True
            )

            # Calculate option premiums
            put_premium = self.calculator.calculate_option_price(
                stock_price, put_strike, dte, is_call=False
            )

            call_premium = self.calculator.calculate_option_price(
                stock_price, call_strike, dte, is_call=True
            )

            # Net cost/credit
            put_cost = put_premium * 100
            call_credit = call_premium * 100
            net_cost = put_cost - call_credit

            # Calculate risk/reward
            position_value = stock_price * shares_owned
            downside_protection = (stock_price - put_strike) * shares_owned
            upside_capped = (call_strike - stock_price) * shares_owned
            max_loss = downside_protection + net_cost
            max_gain = upside_capped - net_cost

            expiration_date = datetime.now() + timedelta(days=dte)

            return {
                'strategy': 'collar',
                'symbol': symbol,
                'stock_price': stock_price,
                'shares_owned': shares_owned,
                'position_value': position_value,

                # Protective put details
                'put_strike': put_strike,
                'put_delta': actual_put_delta,
                'put_premium': put_premium,
                'put_cost': put_cost,

                # Covered call details
                'call_strike': call_strike,
                'call_delta': actual_call_delta,
                'call_premium': call_premium,
                'call_credit': call_credit,

                # Overall collar details
                'net_cost': net_cost,
                'net_debit_credit': 'CREDIT' if net_cost < 0 else 'DEBIT',
                'expiration_date': expiration_date.strftime('%Y-%m-%d'),
                'days_to_expiration': dte,

                # Risk/Reward
                'downside_protected_at': put_strike,
                'upside_capped_at': call_strike,
                'max_loss': round(max_loss, 2),
                'max_gain': round(max_gain, 2),
                'risk_reward_ratio': round(max_gain / max_loss, 2) if max_loss > 0 else 0,

                # Breakeven and ranges
                'protected_range': f"${put_strike:.2f} - ${call_strike:.2f}",
                'protection_percentage': round((put_strike / stock_price) * 100, 2)
            }

        except Exception as e:
            logger.error(f"Error generating collar details: {e}")
            return {}


class AIStrategyHelper:
    """Helper functions for AI-driven trading strategy"""

    @staticmethod
    def analyze_market_conditions(symbol: str, market_data: Dict) -> Dict:
        """
        Analyze market conditions for AI strategy decision making

        Args:
            symbol: Stock symbol
            market_data: Market data dictionary

        Returns:
            Analysis results
        """
        try:
            price = market_data.get('price', 0)
            change = market_data.get('change', 0)
            change_percent = market_data.get('change_percent', 0)
            volume = market_data.get('volume', 0)

            # Simple trend analysis
            if change_percent > 2:
                trend = 'strong_bullish'
            elif change_percent > 0.5:
                trend = 'bullish'
            elif change_percent < -2:
                trend = 'strong_bearish'
            elif change_percent < -0.5:
                trend = 'bearish'
            else:
                trend = 'neutral'

            # Volume analysis
            avg_volume = 1000000  # Placeholder
            volume_ratio = volume / avg_volume if avg_volume > 0 else 1

            if volume_ratio > 1.5:
                volume_signal = 'high'
            elif volume_ratio < 0.5:
                volume_signal = 'low'
            else:
                volume_signal = 'normal'

            return {
                'symbol': symbol,
                'trend': trend,
                'volume_signal': volume_signal,
                'momentum_score': round(change_percent / 10, 2),
                'volatility_estimate': abs(change_percent) * 2,
                'recommendation': AIStrategyHelper._get_recommendation(trend, volume_signal)
            }

        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return {
                'symbol': symbol,
                'trend': 'unknown',
                'recommendation': 'HOLD'
            }

    @staticmethod
    def _get_recommendation(trend: str, volume_signal: str) -> str:
        """Generate trading recommendation based on analysis"""
        if trend in ['strong_bullish', 'bullish'] and volume_signal in ['high', 'normal']:
            return 'BUY'
        elif trend in ['strong_bearish', 'bearish'] and volume_signal in ['high', 'normal']:
            return 'SELL'
        else:
            return 'HOLD'

    @staticmethod
    def calculate_position_size(account_value: float, risk_percentage: float = 0.02) -> float:
        """
        Calculate appropriate position size based on risk management

        Args:
            account_value: Total account value
            risk_percentage: Risk per trade as decimal (default 2%)

        Returns:
            Position size in dollars
        """
        return account_value * risk_percentage
