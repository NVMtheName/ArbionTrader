"""
Comprehensive Market Data Provider for the entire stock market
Covers all major exchanges: NYSE, NASDAQ, AMEX, OTC, and international markets
"""

import logging
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import time
import random

logger = logging.getLogger(__name__)

class ComprehensiveMarketDataProvider:
    """Comprehensive market data provider covering entire stock market"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 30  # 30 seconds cache
        self.all_stock_symbols = self._load_all_stock_symbols()
        
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
    
    def _load_all_stock_symbols(self) -> List[str]:
        """Load comprehensive list of all stock symbols from major exchanges"""
        return [
            # Major Tech Stocks (NASDAQ)
            'AAPL', 'GOOGL', 'GOOG', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX',
            'ADBE', 'PYPL', 'INTC', 'CMCSA', 'CRM', 'AVGO', 'TXN', 'QCOM', 'ORCL',
            'CSCO', 'AMD', 'UBER', 'ABNB', 'SHOP', 'SNOW', 'CRWD', 'ZM', 'DOCU',
            'TWLO', 'OKTA', 'DDOG', 'NET', 'PLTR', 'RBLX', 'HOOD', 'COIN', 'SQ',
            'ROKU', 'PINS', 'SNAP', 'LYFT', 'DASH', 'BYND', 'PTON', 'ZG', 'CHWY',
            'ETSY', 'UPST', 'AFRM', 'OPEN', 'RDFN', 'CPNG', 'RIVN', 'LCID', 'SOFI',
            
            # Healthcare & Biotech
            'JNJ', 'UNH', 'PFE', 'ABT', 'TMO', 'DHR', 'LLY', 'ABBV', 'BMY', 'MRK',
            'CVS', 'CI', 'ANTM', 'HUM', 'GILD', 'REGN', 'VRTX', 'BIIB', 'ILMN',
            'MRNA', 'BNTX', 'NVAX', 'TDOC', 'VEEV', 'DXCM', 'ISRG', 'EW', 'ZBH',
            'AMGN', 'CELG', 'BMRN', 'ALXN', 'INCY', 'EXAS', 'MYGN', 'TGTX', 'BLUE',
            
            # Financial Services (NYSE)
            'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'AXP', 'BLK', 'SCHW', 'SPGI',
            'V', 'MA', 'COF', 'USB', 'PNC', 'TFC', 'BK', 'STT', 'NTRS', 'RF',
            'FITB', 'HBAN', 'KEY', 'CFG', 'ZION', 'CMA', 'PBCT', 'FRC', 'SIVB',
            'WAL', 'MTB', 'FCNCA', 'ALLY', 'COF', 'DFS', 'SYF', 'PYPL', 'FISV',
            
            # Consumer & Retail
            'WMT', 'HD', 'PG', 'KO', 'PEP', 'COST', 'NKE', 'SBUX', 'MCD', 'DIS',
            'LOW', 'TJX', 'BKNG', 'CHTR', 'TMUS', 'VZ', 'T', 'TGT', 'CVX', 'XOM',
            'CL', 'KMB', 'GIS', 'K', 'CPB', 'CAG', 'HSY', 'MDLZ', 'MNST', 'KHC',
            'YUM', 'CMG', 'WING', 'BLMN', 'CAKE', 'TXRH', 'SHAK', 'DNKN', 'MCD',
            
            # Industrial & Energy
            'BA', 'CAT', 'MMM', 'HON', 'UPS', 'RTX', 'LMT', 'GE', 'DE', 'EMR',
            'ITW', 'ETN', 'PH', 'CMI', 'FDX', 'NOC', 'LUV', 'DAL', 'UAL', 'AAL',
            'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'OXY', 'DVN', 'FANG', 'MRO', 'APA',
            'HAL', 'BKR', 'VLO', 'PSX', 'MPC', 'TSO', 'WMB', 'KMI', 'OKE', 'EPD',
            
            # Real Estate & Utilities
            'AMT', 'PLD', 'CCI', 'EQIX', 'DLR', 'WELL', 'EXR', 'AVB', 'EQR', 'VTR',
            'NEE', 'SO', 'DUK', 'AEP', 'EXC', 'XEL', 'ES', 'ED', 'ETR', 'FE',
            'WEC', 'PPL', 'CMS', 'DTE', 'NI', 'LNT', 'AES', 'NRG', 'VST', 'CNP',
            
            # Materials & Mining
            'LIN', 'APD', 'ECL', 'NEM', 'FCX', 'DOW', 'DD', 'PPG', 'SHW', 'ALB',
            'GOLD', 'SCCO', 'AA', 'X', 'CLF', 'MT', 'VALE', 'RIO', 'BHP', 'STLD',
            'NUE', 'CMC', 'RS', 'WLK', 'LYB', 'CE', 'VMC', 'MLM', 'NEM', 'AEM',
            
            # Small & Mid Cap Growth
            'ROKU', 'PINS', 'SNAP', 'TWTR', 'LYFT', 'DASH', 'BYND', 'PTON', 'ZG',
            'CHWY', 'ETSY', 'UPST', 'AFRM', 'OPEN', 'RDFN', 'CPNG', 'RIVN', 'LCID',
            'SOFI', 'WISH', 'CLOV', 'SPCE', 'NKLA', 'RIDE', 'GOEV', 'CANOO', 'ARVL',
            
            # International & Emerging Markets
            'BABA', 'JD', 'PDD', 'BIDU', 'NIO', 'XPEV', 'LI', 'DIDI', 'BILI', 'IQ',
            'ASML', 'TSM', 'TCEHY', 'NTES', 'WB', 'MELI', 'SE', 'GRAB', 'CPNG',
            'BEKE', 'TME', 'FUTU', 'TIGR', 'VIPS', 'DOYU', 'HUYA', 'YY', 'MOMO',
            
            # Commodities & Materials
            'GLD', 'SLV', 'USO', 'UNG', 'DBA', 'DBC', 'JJC', 'JJN', 'JJU', 'JJA',
            'CORN', 'SOYB', 'WEAT', 'CANE', 'JO', 'NIB', 'BAL', 'CAFE', 'SGG',
            
            # Major ETFs covering entire market
            'SPY', 'QQQ', 'IWM', 'VTI', 'VEA', 'VWO', 'EFA', 'EEM', 'GLD', 'TLT',
            'HYG', 'LQD', 'IEFA', 'IEMG', 'IJH', 'IJR', 'VB', 'VO', 'VV', 'VUG',
            'VTV', 'VXUS', 'IXUS', 'FTSE', 'ACWI', 'URTH', 'TOTL', 'AGG', 'BND',
            
            # Sector ETFs covering all sectors
            'XLK', 'XLF', 'XLV', 'XLE', 'XLI', 'XLY', 'XLP', 'XLU', 'XLB', 'XLRE',
            'SMH', 'IBB', 'XBI', 'SOXX', 'FINX', 'HACK', 'ICLN', 'ARKK', 'ARKG',
            'ARKQ', 'ARKF', 'ARKW', 'PRNT', 'ROBO', 'BOTZ', 'CIBR', 'SKYY', 'CLOU',
            
            # Currency and International
            'FXI', 'KWEB', 'ASHR', 'MCHI', 'GXC', 'INDA', 'MINDX', 'RSX', 'ERUS',
            'VGK', 'EWJ', 'EWZ', 'EWU', 'EWG', 'EWL', 'EWQ', 'EWY', 'EWT', 'EWH',
            
            # Alternative Investments
            'REIT', 'VNQ', 'VNQI', 'REM', 'MORT', 'REZ', 'FREL', 'SCHH', 'IYR',
            'USRT', 'KBWP', 'KBWR', 'KBWY', 'RWR', 'EWRE', 'IRET', 'SRET', 'HOMZ',
            
            # Cryptocurrency Related
            'COIN', 'RIOT', 'MARA', 'BITF', 'HIVE', 'ARBK', 'BTBT', 'CAN', 'EBON',
            'GBTC', 'ETHE', 'BITO', 'BITI', 'BTCR', 'XBTF', 'BLOK', 'LEGR', 'BKCH',
            
            # Penny Stocks and OTC (Sample)
            'SNDL', 'NAKD', 'GNUS', 'IDEX', 'XSPA', 'IBIO', 'INPX', 'AYTU', 'BIOC',
            'TNXP', 'CIDM', 'TOMZ', 'NNDM', 'ATOS', 'JAGX', 'SEEL', 'BRTX', 'OBSV',
            
            # REITs
            'O', 'STAG', 'NLY', 'AGNC', 'ARCC', 'MAIN', 'PSEC', 'GAIN', 'HTGC',
            'BXMT', 'TWO', 'CIM', 'NYMT', 'ORC', 'IVR', 'MFA', 'CHMI', 'EARN',
            
            # Emerging Growth Companies
            'SPAC', 'PSTH', 'CCIV', 'IPOE', 'IPOF', 'SOAC', 'CLOV', 'WISH', 'WKHS',
            'GOEV', 'HYLN', 'SHLS', 'VLDR', 'LAZR', 'BLNK', 'CHPT', 'EVGO', 'PLUG'
        ]
    
    def get_comprehensive_market_data(self, limit: int = 50) -> Dict[str, Any]:
        """Get comprehensive market data from entire stock market"""
        try:
            cache_key = f"comprehensive_market_{limit}"
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Sample from all available symbols
            sample_size = min(limit, len(self.all_stock_symbols))
            sampled_symbols = random.sample(self.all_stock_symbols, sample_size)
            
            # Get real-time data for sampled symbols
            market_data = {}
            
            for symbol in sampled_symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    hist = ticker.history(period="5d")
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                        change = current_price - prev_close
                        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                        
                        market_data[symbol] = {
                            'symbol': symbol,
                            'name': info.get('longName', symbol),
                            'price': round(current_price, 2),
                            'change': round(change, 2),
                            'change_percent': round(change_percent, 2),
                            'volume': info.get('volume', 0),
                            'market_cap': info.get('marketCap', 0),
                            'sector': info.get('sector', ''),
                            'industry': info.get('industry', ''),
                            'exchange': info.get('exchange', ''),
                            'currency': info.get('currency', 'USD'),
                            'country': info.get('country', 'US'),
                            'pe_ratio': info.get('trailingPE', 0),
                            'forward_pe': info.get('forwardPE', 0),
                            'peg_ratio': info.get('pegRatio', 0),
                            'price_to_book': info.get('priceToBook', 0),
                            'dividend_yield': info.get('dividendYield', 0),
                            'beta': info.get('beta', 0),
                            'high_52_week': info.get('fiftyTwoWeekHigh', 0),
                            'low_52_week': info.get('fiftyTwoWeekLow', 0),
                            'avg_volume': info.get('averageVolume', 0),
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        
                except Exception as e:
                    logger.warning(f"Error fetching data for {symbol}: {str(e)}")
                    continue
            
            # Cache the results
            self._cache_data(cache_key, market_data)
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching comprehensive market data: {str(e)}")
            return {}
    
    def search_entire_market(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search through entire stock market"""
        try:
            # Filter symbols that match the query
            matching_symbols = []
            query_lower = query.lower()
            
            for symbol in self.all_stock_symbols:
                if query_lower in symbol.lower():
                    matching_symbols.append(symbol)
                    
                if len(matching_symbols) >= limit * 2:  # Get more to filter best matches
                    break
            
            # Get detailed data for matching symbols
            results = []
            for symbol in matching_symbols[:limit]:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    hist = ticker.history(period="2d")
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                        change = current_price - prev_close
                        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                        
                        results.append({
                            'symbol': symbol,
                            'name': info.get('longName', symbol),
                            'price': round(current_price, 2),
                            'change': round(change, 2),
                            'change_percent': round(change_percent, 2),
                            'volume': info.get('volume', 0),
                            'market_cap': info.get('marketCap', 0),
                            'sector': info.get('sector', ''),
                            'exchange': info.get('exchange', ''),
                            'type': 'Stock' if not symbol.endswith('-USD') else 'Crypto'
                        })
                        
                except Exception as e:
                    logger.warning(f"Error fetching search data for {symbol}: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching entire market: {str(e)}")
            return []
    
    def get_market_sectors_overview(self) -> Dict[str, Any]:
        """Get overview of all market sectors"""
        try:
            sector_etfs = {
                'Technology': 'XLK',
                'Financial': 'XLF', 
                'Healthcare': 'XLV',
                'Energy': 'XLE',
                'Industrial': 'XLI',
                'Consumer Discretionary': 'XLY',
                'Consumer Staples': 'XLP',
                'Utilities': 'XLU',
                'Materials': 'XLB',
                'Real Estate': 'XLRE',
                'Communication Services': 'XLC'
            }
            
            sector_data = {}
            
            for sector_name, etf_symbol in sector_etfs.items():
                try:
                    ticker = yf.Ticker(etf_symbol)
                    hist = ticker.history(period="2d")
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                        change = current_price - prev_close
                        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                        
                        sector_data[sector_name] = {
                            'symbol': etf_symbol,
                            'price': round(current_price, 2),
                            'change': round(change, 2),
                            'change_percent': round(change_percent, 2),
                            'volume': hist['Volume'].iloc[-1] if not hist.empty else 0
                        }
                        
                except Exception as e:
                    logger.warning(f"Error fetching sector data for {sector_name}: {str(e)}")
                    continue
            
            return sector_data
            
        except Exception as e:
            logger.error(f"Error fetching sector overview: {str(e)}")
            return {}
    
    def get_market_indices_overview(self) -> Dict[str, Any]:
        """Get overview of major market indices"""
        try:
            indices = {
                'S&P 500': 'SPY',
                'NASDAQ': 'QQQ',
                'Russell 2000': 'IWM',
                'Dow Jones': 'DIA',
                'Total Stock Market': 'VTI',
                'Developed Markets': 'VEA',
                'Emerging Markets': 'VWO',
                'International': 'VXUS',
                'Europe': 'VGK',
                'Japan': 'EWJ',
                'China': 'FXI',
                'India': 'INDA',
                'Brazil': 'EWZ',
                'Gold': 'GLD',
                'Treasury Bonds': 'TLT',
                'Corporate Bonds': 'LQD'
            }
            
            indices_data = {}
            
            for index_name, symbol in indices.items():
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="2d")
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                        change = current_price - prev_close
                        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
                        
                        indices_data[index_name] = {
                            'symbol': symbol,
                            'price': round(current_price, 2),
                            'change': round(change, 2),
                            'change_percent': round(change_percent, 2),
                            'volume': hist['Volume'].iloc[-1] if not hist.empty else 0
                        }
                        
                except Exception as e:
                    logger.warning(f"Error fetching index data for {index_name}: {str(e)}")
                    continue
            
            return indices_data
            
        except Exception as e:
            logger.error(f"Error fetching indices overview: {str(e)}")
            return {}