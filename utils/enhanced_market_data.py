"""
Enhanced Market Data Provider with real-time stock search and quotes
Provides comprehensive market data from multiple sources
"""

import logging
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import time

logger = logging.getLogger(__name__)

class EnhancedMarketDataProvider:
    """Enhanced market data provider with real-time capabilities"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 30  # 30 seconds cache
        
    def _get_cached_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if still valid"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_timeout:
                return data
        return None
    
    def _cache_data(self, key: str, data: Dict[str, Any]):
        """Cache data with timestamp"""
        self.cache[key] = (data, time.time())
    
    def search_symbols(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for stock symbols with company names
        
        Args:
            query: Search query (symbol or company name)
            limit: Maximum number of results
            
        Returns:
            List of matching symbols with metadata
        """
        try:
            cache_key = f"search_{query}_{limit}"
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Use Yahoo Finance search API
            url = f"https://query1.finance.yahoo.com/v1/finance/search"
            params = {
                'q': query,
                'lang': 'en-US',
                'region': 'US',
                'quotesCount': limit,
                'newsCount': 0,
                'enableFuzzyQuery': False,
                'quotesQueryId': 'tss_match_phrase_query',
                'multiQuoteQueryId': 'multi_quote_single_token_query'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            quotes = data.get('quotes', [])
            
            results = []
            for quote in quotes:
                if quote.get('isYahooFinance', False):
                    result = {
                        'symbol': quote.get('symbol', ''),
                        'name': quote.get('shortname', quote.get('longname', '')),
                        'exchange': quote.get('exchange', ''),
                        'type': quote.get('quoteType', ''),
                        'sector': quote.get('sector', ''),
                        'industry': quote.get('industry', ''),
                        'market_cap': quote.get('marketCap', 0),
                        'currency': quote.get('currency', 'USD')
                    }
                    results.append(result)
            
            self._cache_data(cache_key, results)
            logger.info(f"Found {len(results)} symbols for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching symbols for '{query}': {str(e)}")
            return []
    
    def get_real_time_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time quote for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Real-time quote data
        """
        try:
            cache_key = f"quote_{symbol}"
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Use yfinance for real-time data
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Get current price data
            hist = ticker.history(period="2d", interval="1m")
            if hist.empty:
                hist = ticker.history(period="1d")
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                previous_close = info.get('previousClose', hist['Close'].iloc[0])
                
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
                
                quote_data = {
                    'symbol': symbol,
                    'name': info.get('shortName', info.get('longName', symbol)),
                    'price': round(current_price, 2),
                    'change': round(change, 2),
                    'change_percent': round(change_percent, 2),
                    'volume': info.get('volume', 0),
                    'avg_volume': info.get('averageVolume', 0),
                    'market_cap': info.get('marketCap', 0),
                    'high': round(hist['High'].max(), 2),
                    'low': round(hist['Low'].min(), 2),
                    'open': round(hist['Open'].iloc[0], 2),
                    'previous_close': round(previous_close, 2),
                    'currency': info.get('currency', 'USD'),
                    'exchange': info.get('exchange', ''),
                    'sector': info.get('sector', ''),
                    'industry': info.get('industry', ''),
                    'pe_ratio': info.get('trailingPE', 0),
                    'dividend_yield': info.get('dividendYield', 0),
                    'beta': info.get('beta', 0),
                    'timestamp': datetime.utcnow().isoformat(),
                    'market_state': 'REGULAR' if self._is_market_open() else 'CLOSED'
                }
                
                self._cache_data(cache_key, quote_data)
                logger.info(f"Retrieved real-time quote for {symbol}: ${current_price:.2f}")
                return quote_data
            else:
                logger.warning(f"No historical data found for {symbol}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting real-time quote for {symbol}: {str(e)}")
            return {}
    
    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get real-time quotes for multiple symbols
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dictionary of symbol -> quote data
        """
        quotes = {}
        
        for symbol in symbols:
            quote = self.get_real_time_quote(symbol)
            if quote:
                quotes[symbol] = quote
        
        return quotes
    
    def get_trending_stocks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trending stocks from Yahoo Finance
        
        Args:
            limit: Maximum number of trending stocks
            
        Returns:
            List of trending stocks with basic data
        """
        try:
            cache_key = f"trending_{limit}"
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Get trending stocks from Yahoo Finance
            url = "https://query1.finance.yahoo.com/v1/finance/trending/US"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            quotes = data.get('finance', {}).get('result', [{}])[0].get('quotes', [])
            
            trending = []
            for quote in quotes[:limit]:
                symbol = quote.get('symbol', '')
                if symbol:
                    quote_data = self.get_real_time_quote(symbol)
                    if quote_data:
                        trending.append(quote_data)
            
            self._cache_data(cache_key, trending)
            logger.info(f"Retrieved {len(trending)} trending stocks")
            return trending
            
        except Exception as e:
            logger.error(f"Error getting trending stocks: {str(e)}")
            return []
    
    def get_crypto_price(self, symbol: str) -> Dict[str, Any]:
        """
        Get real-time cryptocurrency price
        
        Args:
            symbol: Crypto symbol (BTC, ETH, etc.)
            
        Returns:
            Crypto price data
        """
        try:
            cache_key = f"crypto_{symbol}"
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Use CoinGecko API for crypto prices
            symbol_map = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'LTC': 'litecoin',
                'BCH': 'bitcoin-cash',
                'ADA': 'cardano',
                'DOT': 'polkadot',
                'LINK': 'chainlink',
                'XRP': 'ripple'
            }
            
            coin_id = symbol_map.get(symbol.upper(), symbol.lower())
            
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true',
                'include_market_cap': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if coin_id in data:
                coin_data = data[coin_id]
                crypto_data = {
                    'symbol': symbol.upper(),
                    'name': symbol.upper(),
                    'price': coin_data.get('usd', 0),
                    'change': coin_data.get('usd_24h_change', 0),
                    'change_percent': coin_data.get('usd_24h_change', 0),
                    'volume': coin_data.get('usd_24h_vol', 0),
                    'market_cap': coin_data.get('usd_market_cap', 0),
                    'currency': 'USD',
                    'type': 'crypto',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                self._cache_data(cache_key, crypto_data)
                logger.info(f"Retrieved crypto price for {symbol}: ${coin_data.get('usd', 0):.2f}")
                return crypto_data
            
        except Exception as e:
            logger.error(f"Error getting crypto price for {symbol}: {str(e)}")
            return {}
    
    def get_market_movers(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get market movers (gainers, losers, most active)
        
        Returns:
            Dictionary with gainers, losers, and most active stocks
        """
        try:
            cache_key = "market_movers"
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Popular stocks to check for movers
            popular_stocks = [
                'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
                'SPY', 'QQQ', 'IWM', 'DIA', 'AMD', 'INTC', 'BABA', 'UBER',
                'COIN', 'SQ', 'PYPL', 'ZOOM', 'SHOP', 'ROKU', 'PELOTON'
            ]
            
            quotes = self.get_multiple_quotes(popular_stocks)
            
            # Sort by different criteria
            valid_quotes = [q for q in quotes.values() if q.get('change_percent', 0) != 0]
            
            gainers = sorted(valid_quotes, key=lambda x: x.get('change_percent', 0), reverse=True)[:10]
            losers = sorted(valid_quotes, key=lambda x: x.get('change_percent', 0))[:10]
            most_active = sorted(valid_quotes, key=lambda x: x.get('volume', 0), reverse=True)[:10]
            
            movers = {
                'gainers': gainers,
                'losers': losers,
                'most_active': most_active,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            self._cache_data(cache_key, movers)
            logger.info(f"Retrieved market movers: {len(gainers)} gainers, {len(losers)} losers, {len(most_active)} most active")
            return movers
            
        except Exception as e:
            logger.error(f"Error getting market movers: {str(e)}")
            return {'gainers': [], 'losers': [], 'most_active': []}
    
    def _is_market_open(self) -> bool:
        """Check if US market is currently open"""
        try:
            now = datetime.now()
            # Simple check for US market hours (9:30 AM - 4:00 PM ET, Monday-Friday)
            if now.weekday() >= 5:  # Weekend
                return False
            
            # This is a simplified check - in production, you'd want to account for holidays
            # and use proper timezone handling
            hour = now.hour
            return 9 <= hour <= 16
            
        except Exception:
            return False
    
    def get_historical_data(self, symbol: str, period: str = "1mo") -> Dict[str, Any]:
        """
        Get historical data for a symbol
        
        Args:
            symbol: Stock symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            
        Returns:
            Historical data
        """
        try:
            cache_key = f"historical_{symbol}_{period}"
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if not hist.empty:
                historical_data = {
                    'symbol': symbol,
                    'period': period,
                    'data': [
                        {
                            'date': index.strftime('%Y-%m-%d'),
                            'open': round(row['Open'], 2),
                            'high': round(row['High'], 2),
                            'low': round(row['Low'], 2),
                            'close': round(row['Close'], 2),
                            'volume': int(row['Volume'])
                        }
                        for index, row in hist.iterrows()
                    ],
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                self._cache_data(cache_key, historical_data)
                logger.info(f"Retrieved {len(historical_data['data'])} historical data points for {symbol}")
                return historical_data
            
        except Exception as e:
            logger.error(f"Error getting historical data for {symbol}: {str(e)}")
            return {}