import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf

class MarketDataProvider:
    """Unified market data provider for real-time and historical data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def get_stock_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time stock quote using yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                'symbol': symbol,
                'price': info.get('regularMarketPrice', 0),
                'change': info.get('regularMarketChange', 0),
                'change_percent': info.get('regularMarketChangePercent', 0),
                'volume': info.get('regularMarketVolume', 0),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'beta': info.get('beta', 0),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh', 0),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow', 0),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error fetching stock quote for {symbol}: {str(e)}")
            return None
    
    def get_option_chain(self, symbol: str, expiration_date: str = None) -> Optional[Dict]:
        """Get option chain data for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get available expiration dates
            expirations = ticker.options
            
            if not expirations:
                return None
            
            # Use specified expiration or next available
            target_expiration = expiration_date or expirations[0]
            
            # Get option chain for the target expiration
            options = ticker.option_chain(target_expiration)
            
            # Process calls and puts
            calls_data = []
            puts_data = []
            
            for _, call in options.calls.iterrows():
                calls_data.append({
                    'strike': call['strike'],
                    'last_price': call['lastPrice'],
                    'bid': call['bid'],
                    'ask': call['ask'],
                    'volume': call['volume'],
                    'open_interest': call['openInterest'],
                    'implied_volatility': call['impliedVolatility'],
                    'delta': call.get('delta', 0),
                    'gamma': call.get('gamma', 0),
                    'theta': call.get('theta', 0),
                    'vega': call.get('vega', 0)
                })
            
            for _, put in options.puts.iterrows():
                puts_data.append({
                    'strike': put['strike'],
                    'last_price': put['lastPrice'],
                    'bid': put['bid'],
                    'ask': put['ask'],
                    'volume': put['volume'],
                    'open_interest': put['openInterest'],
                    'implied_volatility': put['impliedVolatility'],
                    'delta': put.get('delta', 0),
                    'gamma': put.get('gamma', 0),
                    'theta': put.get('theta', 0),
                    'vega': put.get('vega', 0)
                })
            
            return {
                'symbol': symbol,
                'expiration': target_expiration,
                'calls': calls_data,
                'puts': puts_data,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error fetching option chain for {symbol}: {str(e)}")
            return None
    
    def get_historical_data(self, symbol: str, period: str = '1mo') -> Optional[List[Dict]]:
        """Get historical price data"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            historical_data = []
            for date, row in hist.iterrows():
                historical_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'open': round(row['Open'], 2),
                    'high': round(row['High'], 2),
                    'low': round(row['Low'], 2),
                    'close': round(row['Close'], 2),
                    'volume': int(row['Volume'])
                })
            
            return historical_data
        
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return None
    
    def get_crypto_price(self, symbol: str) -> Optional[Dict]:
        """Get cryptocurrency price from CoinGecko API"""
        try:
            # Convert symbol to CoinGecko format
            crypto_map = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'LTC': 'litecoin',
                'BCH': 'bitcoin-cash',
                'ADA': 'cardano',
                'DOT': 'polkadot',
                'LINK': 'chainlink',
                'XRP': 'ripple'
            }
            
            crypto_id = crypto_map.get(symbol.upper(), symbol.lower())
            
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': crypto_id,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true',
                'include_market_cap': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if crypto_id in data:
                crypto_data = data[crypto_id]
                return {
                    'symbol': symbol,
                    'price': crypto_data['usd'],
                    'change_24h': crypto_data.get('usd_24h_change', 0),
                    'volume_24h': crypto_data.get('usd_24h_vol', 0),
                    'market_cap': crypto_data.get('usd_market_cap', 0),
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error fetching crypto price for {symbol}: {str(e)}")
            return None
    
    def calculate_technical_indicators(self, symbol: str) -> Optional[Dict]:
        """Calculate common technical indicators"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='3mo')
            
            if len(hist) < 50:
                return None
            
            # Calculate simple moving averages
            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            
            # Calculate RSI
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # Calculate MACD
            ema_12 = hist['Close'].ewm(span=12).mean()
            ema_26 = hist['Close'].ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal = macd.ewm(span=9).mean()
            histogram = macd - signal
            
            # Calculate Bollinger Bands
            bb_period = 20
            bb_std = 2
            bb_middle = hist['Close'].rolling(window=bb_period).mean()
            bb_std_dev = hist['Close'].rolling(window=bb_period).std()
            bb_upper = bb_middle + (bb_std_dev * bb_std)
            bb_lower = bb_middle - (bb_std_dev * bb_std)
            
            current_price = hist['Close'].iloc[-1]
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'sma_20': round(sma_20, 2),
                'sma_50': round(sma_50, 2),
                'rsi': round(rsi, 2),
                'macd': round(macd.iloc[-1], 2),
                'macd_signal': round(signal.iloc[-1], 2),
                'macd_histogram': round(histogram.iloc[-1], 2),
                'bb_upper': round(bb_upper.iloc[-1], 2),
                'bb_middle': round(bb_middle.iloc[-1], 2),
                'bb_lower': round(bb_lower.iloc[-1], 2),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error calculating technical indicators for {symbol}: {str(e)}")
            return None
    
    def get_market_sentiment(self, symbol: str) -> Optional[Dict]:
        """Get market sentiment indicators"""
        try:
            # This is a simplified sentiment analysis
            # In production, you could integrate with sentiment APIs
            
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Use various metrics to gauge sentiment
            pe_ratio = info.get('trailingPE', 0)
            beta = info.get('beta', 1)
            analyst_rating = info.get('recommendationKey', 'hold')
            
            # Simple sentiment scoring
            sentiment_score = 0
            
            if pe_ratio > 0 and pe_ratio < 15:
                sentiment_score += 1
            elif pe_ratio > 25:
                sentiment_score -= 1
            
            if beta < 1:
                sentiment_score += 0.5
            elif beta > 1.5:
                sentiment_score -= 0.5
            
            rating_scores = {
                'strong_buy': 2,
                'buy': 1,
                'hold': 0,
                'sell': -1,
                'strong_sell': -2
            }
            
            sentiment_score += rating_scores.get(analyst_rating, 0)
            
            # Normalize to 0-100 scale
            sentiment_percentage = max(0, min(100, (sentiment_score + 3) * 100 / 6))
            
            return {
                'symbol': symbol,
                'sentiment_score': round(sentiment_percentage, 1),
                'analyst_rating': analyst_rating,
                'pe_ratio': pe_ratio,
                'beta': beta,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error getting market sentiment for {symbol}: {str(e)}")
            return None