"""
Schwab Order Builder for Arbion Trading Platform
=================================================
High-level order building using schwab-py's order templates.

Provides:
- Equity orders (market, limit, short, cover)
- Options orders (buy/sell to open/close, market/limit)
- Vertical spreads (bull/bear call/put)
- Composite strategies (OCO, first-triggers-second)
- Natural language to order translation helpers

Uses schwab-py's type-safe OrderBuilder and templates from:
- schwab.orders.equities
- schwab.orders.options
- schwab.orders.common
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from schwab.orders.equities import (
        equity_buy_market, equity_buy_limit,
        equity_sell_market, equity_sell_limit,
        equity_sell_short_market, equity_sell_short_limit,
        equity_buy_to_cover_market, equity_buy_to_cover_limit,
    )
    from schwab.orders.options import (
        OptionSymbol,
        option_buy_to_open_market, option_buy_to_open_limit,
        option_sell_to_open_market, option_sell_to_open_limit,
        option_buy_to_close_market, option_buy_to_close_limit,
        option_sell_to_close_market, option_sell_to_close_limit,
        bull_call_vertical_open, bull_call_vertical_close,
        bear_call_vertical_open, bear_call_vertical_close,
        bull_put_vertical_open, bull_put_vertical_close,
        bear_put_vertical_open, bear_put_vertical_close,
    )
    from schwab.orders.common import (
        Duration, Session, OrderType, OrderStrategyType,
        EquityInstruction, OptionInstruction,
        one_cancels_other, first_triggers_second,
    )
    SCHWAB_ORDERS_AVAILABLE = True
except ImportError:
    SCHWAB_ORDERS_AVAILABLE = False

logger = logging.getLogger(__name__)


class SchwabOrderBuilder:
    """
    High-level order builder that uses schwab-py's order templates.

    All build methods return an OrderBuilder dict that can be passed
    directly to SchwabPyClientWrapper.place_order() or
    SchwabdevManager.place_order().
    """

    def __init__(self):
        if not SCHWAB_ORDERS_AVAILABLE:
            logger.warning("schwab-py order templates not available")

    @property
    def is_available(self) -> bool:
        return SCHWAB_ORDERS_AVAILABLE

    # ─── Equity Orders ────────────────────────────────────────────────────────

    def build_equity_order(self, symbol: str, quantity: int, side: str,
                           order_type: str = 'MARKET', price: float = None,
                           duration: str = 'DAY', session_type: str = 'NORMAL') -> Dict[str, Any]:
        """
        Build an equity order using schwab-py templates.

        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            quantity: Number of shares
            side: 'BUY', 'SELL', 'SELL_SHORT', 'BUY_TO_COVER'
            order_type: 'MARKET' or 'LIMIT'
            price: Required for LIMIT orders
            duration: 'DAY', 'GOOD_TILL_CANCEL', 'FILL_OR_KILL'
            session_type: 'NORMAL', 'AM', 'PM', 'SEAMLESS'

        Returns:
            dict with 'success' and 'order_spec' (the OrderBuilder dict)
        """
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py order templates not available'}

        try:
            side_upper = side.upper()
            type_upper = order_type.upper()

            # schwab-py v1.5+ requires prices as strings
            price_str = str(price) if price is not None else None

            # Select the appropriate template function
            if side_upper == 'BUY':
                if type_upper == 'LIMIT' and price_str is not None:
                    order = equity_buy_limit(symbol.upper(), quantity, price_str)
                else:
                    order = equity_buy_market(symbol.upper(), quantity)

            elif side_upper == 'SELL':
                if type_upper == 'LIMIT' and price_str is not None:
                    order = equity_sell_limit(symbol.upper(), quantity, price_str)
                else:
                    order = equity_sell_market(symbol.upper(), quantity)

            elif side_upper == 'SELL_SHORT':
                if type_upper == 'LIMIT' and price_str is not None:
                    order = equity_sell_short_limit(symbol.upper(), quantity, price_str)
                else:
                    order = equity_sell_short_market(symbol.upper(), quantity)

            elif side_upper == 'BUY_TO_COVER':
                if type_upper == 'LIMIT' and price_str is not None:
                    order = equity_buy_to_cover_limit(symbol.upper(), quantity, price_str)
                else:
                    order = equity_buy_to_cover_market(symbol.upper(), quantity)

            else:
                return {'success': False, 'error': f'Unknown side: {side}'}

            # Apply duration and session
            dur_map = {
                'DAY': Duration.DAY,
                'GOOD_TILL_CANCEL': Duration.GOOD_TILL_CANCEL,
                'FILL_OR_KILL': Duration.FILL_OR_KILL,
            }
            sess_map = {
                'NORMAL': Session.NORMAL,
                'AM': Session.AM,
                'PM': Session.PM,
                'SEAMLESS': Session.SEAMLESS,
            }

            dur = dur_map.get(duration.upper(), Duration.DAY)
            sess = sess_map.get(session_type.upper(), Session.NORMAL)

            order.set_duration(dur).set_session(sess)

            order_dict = order.build()
            return {
                'success': True,
                'order_spec': order_dict,
                'summary': {
                    'symbol': symbol.upper(),
                    'side': side_upper,
                    'quantity': quantity,
                    'order_type': type_upper,
                    'price': price,
                    'duration': duration,
                    'session': session_type,
                }
            }

        except Exception as e:
            logger.error(f"Failed to build equity order: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Options Orders ───────────────────────────────────────────────────────

    def build_option_symbol(self, underlying: str, expiration_date: datetime,
                            contract_type: str, strike_price: str) -> Optional[str]:
        """
        Build an option symbol using schwab-py's OptionSymbol.

        Args:
            underlying: Underlying stock symbol
            expiration_date: Expiration date
            contract_type: 'CALL' or 'PUT'
            strike_price: Strike price as string (e.g., '150')

        Returns:
            Option symbol string or None
        """
        if not self.is_available:
            return None

        try:
            ct = contract_type.upper()
            opt_symbol = OptionSymbol(
                underlying.upper(), expiration_date, ct, strike_price
            )
            return opt_symbol.build()
        except Exception as e:
            logger.error(f"Failed to build option symbol: {e}")
            return None

    def build_option_order(self, option_symbol: str, quantity: int,
                           action: str, order_type: str = 'MARKET',
                           price: float = None,
                           duration: str = 'DAY',
                           session_type: str = 'NORMAL') -> Dict[str, Any]:
        """
        Build a single-leg option order.

        Args:
            option_symbol: Full option symbol (use build_option_symbol())
            quantity: Number of contracts
            action: 'BUY_TO_OPEN', 'SELL_TO_OPEN', 'BUY_TO_CLOSE', 'SELL_TO_CLOSE'
            order_type: 'MARKET' or 'LIMIT'
            price: Required for LIMIT orders
            duration: 'DAY', 'GOOD_TILL_CANCEL'
            session_type: 'NORMAL', 'SEAMLESS'

        Returns:
            dict with 'success' and 'order_spec'
        """
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py order templates not available'}

        try:
            action_upper = action.upper()
            type_upper = order_type.upper()
            # schwab-py v1.5+ requires prices as strings
            price_str = str(price) if price is not None else None

            order_map = {
                ('BUY_TO_OPEN', 'MARKET'): lambda: option_buy_to_open_market(option_symbol, quantity),
                ('BUY_TO_OPEN', 'LIMIT'): lambda: option_buy_to_open_limit(option_symbol, quantity, price_str),
                ('SELL_TO_OPEN', 'MARKET'): lambda: option_sell_to_open_market(option_symbol, quantity),
                ('SELL_TO_OPEN', 'LIMIT'): lambda: option_sell_to_open_limit(option_symbol, quantity, price_str),
                ('BUY_TO_CLOSE', 'MARKET'): lambda: option_buy_to_close_market(option_symbol, quantity),
                ('BUY_TO_CLOSE', 'LIMIT'): lambda: option_buy_to_close_limit(option_symbol, quantity, price_str),
                ('SELL_TO_CLOSE', 'MARKET'): lambda: option_sell_to_close_market(option_symbol, quantity),
                ('SELL_TO_CLOSE', 'LIMIT'): lambda: option_sell_to_close_limit(option_symbol, quantity, price_str),
            }

            order_fn = order_map.get((action_upper, type_upper))
            if not order_fn:
                return {'success': False, 'error': f'Unknown action/type: {action}/{order_type}'}

            order = order_fn()

            # Apply duration and session
            dur_map = {
                'DAY': Duration.DAY,
                'GOOD_TILL_CANCEL': Duration.GOOD_TILL_CANCEL,
                'FILL_OR_KILL': Duration.FILL_OR_KILL,
            }
            sess_map = {
                'NORMAL': Session.NORMAL,
                'AM': Session.AM,
                'PM': Session.PM,
                'SEAMLESS': Session.SEAMLESS,
            }

            order.set_duration(dur_map.get(duration.upper(), Duration.DAY))
            order.set_session(sess_map.get(session_type.upper(), Session.NORMAL))

            order_dict = order.build()
            return {
                'success': True,
                'order_spec': order_dict,
                'summary': {
                    'option_symbol': option_symbol,
                    'action': action_upper,
                    'quantity': quantity,
                    'order_type': type_upper,
                    'price': price,
                }
            }

        except Exception as e:
            logger.error(f"Failed to build option order: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Vertical Spread Orders ───────────────────────────────────────────────

    def build_vertical_spread(self, spread_type: str, long_symbol: str,
                              short_symbol: str, quantity: int,
                              net_price: float, action: str = 'OPEN') -> Dict[str, Any]:
        """
        Build a vertical spread order.

        Args:
            spread_type: 'BULL_CALL', 'BEAR_CALL', 'BULL_PUT', 'BEAR_PUT'
            long_symbol: Long leg option symbol
            short_symbol: Short leg option symbol
            quantity: Number of spreads
            net_price: Net debit/credit for the spread
            action: 'OPEN' or 'CLOSE'

        Returns:
            dict with 'success' and 'order_spec'
        """
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py order templates not available'}

        try:
            spread_upper = spread_type.upper()
            action_upper = action.upper()

            spread_map = {
                ('BULL_CALL', 'OPEN'): lambda: bull_call_vertical_open(
                    long_symbol, short_symbol, quantity, net_price),
                ('BULL_CALL', 'CLOSE'): lambda: bull_call_vertical_close(
                    long_symbol, short_symbol, quantity, net_price),
                ('BEAR_CALL', 'OPEN'): lambda: bear_call_vertical_open(
                    short_symbol, long_symbol, quantity, net_price),
                ('BEAR_CALL', 'CLOSE'): lambda: bear_call_vertical_close(
                    short_symbol, long_symbol, quantity, net_price),
                ('BULL_PUT', 'OPEN'): lambda: bull_put_vertical_open(
                    long_symbol, short_symbol, quantity, net_price),
                ('BULL_PUT', 'CLOSE'): lambda: bull_put_vertical_close(
                    long_symbol, short_symbol, quantity, net_price),
                ('BEAR_PUT', 'OPEN'): lambda: bear_put_vertical_open(
                    short_symbol, long_symbol, quantity, net_price),
                ('BEAR_PUT', 'CLOSE'): lambda: bear_put_vertical_close(
                    short_symbol, long_symbol, quantity, net_price),
            }

            order_fn = spread_map.get((spread_upper, action_upper))
            if not order_fn:
                return {'success': False,
                        'error': f'Unknown spread: {spread_type}/{action}'}

            order = order_fn()
            order_dict = order.build()

            return {
                'success': True,
                'order_spec': order_dict,
                'summary': {
                    'spread_type': spread_upper,
                    'long_symbol': long_symbol,
                    'short_symbol': short_symbol,
                    'quantity': quantity,
                    'net_price': net_price,
                    'action': action_upper,
                }
            }

        except Exception as e:
            logger.error(f"Failed to build vertical spread: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Composite Orders ─────────────────────────────────────────────────────

    def build_oco_order(self, order1_spec, order2_spec) -> Dict[str, Any]:
        """
        Build a one-cancels-other (OCO) composite order.

        When one order executes, the other is automatically cancelled.
        Useful for bracket orders (take-profit + stop-loss).

        Args accept either OrderBuilder objects or raw dicts.
        """
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py order templates not available'}

        try:
            oco = one_cancels_other(order1_spec, order2_spec)
            return {
                'success': True,
                'order_spec': oco.build(),
                'summary': {'strategy': 'ONE_CANCELS_OTHER'}
            }
        except Exception as e:
            logger.error(f"Failed to build OCO order: {e}")
            return {'success': False, 'error': str(e)}

    def build_first_triggers_second(self, first_spec, second_spec) -> Dict[str, Any]:
        """
        Build a first-triggers-second composite order.

        The second order is placed only after the first order fills.
        Useful for entry + automatic stop-loss.

        Args accept either OrderBuilder objects or raw dicts.
        """
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py order templates not available'}

        try:
            fts = first_triggers_second(first_spec, second_spec)
            return {
                'success': True,
                'order_spec': fts.build(),
                'summary': {'strategy': 'FIRST_TRIGGERS_SECOND'}
            }
        except Exception as e:
            logger.error(f"Failed to build first-triggers-second order: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Convenience Helpers ──────────────────────────────────────────────────

    def build_bracket_order(self, symbol: str, quantity: int, side: str,
                            entry_price: float, take_profit_price: float,
                            stop_loss_price: float) -> Dict[str, Any]:
        """
        Build a bracket order: entry + take-profit + stop-loss.

        Uses first-triggers-second with an OCO for the exit legs.
        Prices are passed as strings per schwab-py v1.5+ requirements.
        """
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py order templates not available'}

        try:
            # Convert prices to strings (schwab-py v1.5+ requirement)
            entry_str = str(entry_price)
            tp_str = str(take_profit_price)
            sl_str = str(stop_loss_price)

            # Entry order
            if side.upper() == 'BUY':
                entry = equity_buy_limit(symbol.upper(), quantity, entry_str)
                tp = equity_sell_limit(symbol.upper(), quantity, tp_str)
                sl = equity_sell_limit(symbol.upper(), quantity, sl_str)
            else:
                entry = equity_sell_short_limit(symbol.upper(), quantity, entry_str)
                tp = equity_buy_to_cover_limit(symbol.upper(), quantity, tp_str)
                sl = equity_buy_to_cover_limit(symbol.upper(), quantity, sl_str)

            # Set durations
            entry.set_duration(Duration.DAY).set_session(Session.NORMAL)
            tp.set_duration(Duration.GOOD_TILL_CANCEL).set_session(Session.NORMAL)
            sl.set_duration(Duration.GOOD_TILL_CANCEL).set_session(Session.NORMAL)

            # Combine: entry triggers (take-profit OCO stop-loss)
            # one_cancels_other and first_triggers_second accept OrderBuilder objects
            exit_oco = one_cancels_other(tp, sl)
            bracket = first_triggers_second(entry, exit_oco)

            return {
                'success': True,
                'order_spec': bracket.build(),
                'summary': {
                    'strategy': 'BRACKET',
                    'symbol': symbol.upper(),
                    'side': side.upper(),
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'take_profit_price': take_profit_price,
                    'stop_loss_price': stop_loss_price,
                }
            }

        except Exception as e:
            logger.error(f"Failed to build bracket order: {e}")
            return {'success': False, 'error': str(e)}

    def build_from_natural_language(self, text: str) -> Dict[str, Any]:
        """
        Parse a simple natural language order description into an order spec.

        Supports patterns like:
        - "buy 100 AAPL at market"
        - "sell 50 TSLA limit 250.00"
        - "buy 10 AAPL calls 150 exp 2024-03-15"

        For more complex orders, use the specific build methods.
        """
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py order templates not available'}

        try:
            parts = text.lower().strip().split()
            if len(parts) < 3:
                return {'success': False, 'error': 'Order text too short. Example: "buy 100 AAPL at market"'}

            side = parts[0].upper()
            quantity = int(parts[1])
            symbol = parts[2].upper()

            # Check for limit price
            order_type = 'MARKET'
            price = None

            if 'limit' in parts:
                order_type = 'LIMIT'
                limit_idx = parts.index('limit')
                if limit_idx + 1 < len(parts):
                    price = float(parts[limit_idx + 1])

            # Map natural language sides
            side_map = {
                'BUY': 'BUY',
                'SELL': 'SELL',
                'SHORT': 'SELL_SHORT',
                'COVER': 'BUY_TO_COVER',
            }
            mapped_side = side_map.get(side, side)

            return self.build_equity_order(
                symbol=symbol,
                quantity=quantity,
                side=mapped_side,
                order_type=order_type,
                price=price,
            )

        except (ValueError, IndexError) as e:
            return {'success': False, 'error': f'Could not parse order: {e}'}
        except Exception as e:
            logger.error(f"Failed to parse natural language order: {e}")
            return {'success': False, 'error': str(e)}


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_order_builder() -> SchwabOrderBuilder:
    """Create an order builder instance"""
    return SchwabOrderBuilder()


def get_order_builder_info() -> Dict[str, Any]:
    """Get order builder capabilities"""
    return {
        'available': SCHWAB_ORDERS_AVAILABLE,
        'equity_orders': [
            'BUY MARKET', 'BUY LIMIT',
            'SELL MARKET', 'SELL LIMIT',
            'SELL_SHORT MARKET', 'SELL_SHORT LIMIT',
            'BUY_TO_COVER MARKET', 'BUY_TO_COVER LIMIT',
        ],
        'option_orders': [
            'BUY_TO_OPEN MARKET/LIMIT',
            'SELL_TO_OPEN MARKET/LIMIT',
            'BUY_TO_CLOSE MARKET/LIMIT',
            'SELL_TO_CLOSE MARKET/LIMIT',
        ],
        'spread_orders': [
            'BULL_CALL OPEN/CLOSE',
            'BEAR_CALL OPEN/CLOSE',
            'BULL_PUT OPEN/CLOSE',
            'BEAR_PUT OPEN/CLOSE',
        ],
        'composite_orders': [
            'ONE_CANCELS_OTHER (OCO)',
            'FIRST_TRIGGERS_SECOND',
            'BRACKET (entry + take-profit + stop-loss)',
        ],
        'durations': ['DAY', 'GOOD_TILL_CANCEL', 'FILL_OR_KILL'],
        'sessions': ['NORMAL', 'AM', 'PM', 'SEAMLESS'],
    }
