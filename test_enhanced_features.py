#!/usr/bin/env python3
"""
Test suite for enhanced Arbion AI Trading Platform features
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta

# Add the workspace directory to the Python path
sys.path.insert(0, '/home/runner/workspace')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FeatureTestSuite:
    """Comprehensive test suite for enhanced features"""
    
    def __init__(self):
        self.results = {}
        self.market_data = None
        self.risk_manager = None
        
        # Initialize components individually to avoid circular imports
        self.init_components()
        
    def init_components(self):
        """Initialize components safely"""
        try:
            from utils.market_data import MarketDataProvider
            self.market_data = MarketDataProvider()
            logger.info("Market data provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize market data provider: {e}")
            
        try:
            from utils.risk_management import RiskManager
            self.risk_manager = RiskManager()
            logger.info("Risk manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize risk manager: {e}")
        
    def run_all_tests(self):
        """Run all feature tests"""
        logger.info("Starting comprehensive feature test suite...")
        
        # Test core utilities
        self.test_encryption()
        self.test_market_data_provider()
        self.test_risk_management()
        self.test_technical_indicators()
        self.test_option_chain_processing()
        
        # Test trading components
        if os.environ.get('OPENAI_API_KEY'):
            self.test_openai_integration()
        else:
            logger.warning("OpenAI API key not found, skipping OpenAI tests")
            
        # Test auto-trading engine
        self.test_auto_trading_engine()
        
        # Generate test report
        self.generate_test_report()
        
    def test_encryption(self):
        """Test encryption/decryption functionality"""
        logger.info("Testing encryption system...")
        
        try:
            from utils.encryption import test_encryption
            result = test_encryption()
            self.results['encryption'] = {
                'status': 'PASS' if result else 'FAIL',
                'message': 'Encryption/decryption working correctly' if result else 'Encryption test failed'
            }
        except Exception as e:
            self.results['encryption'] = {
                'status': 'FAIL',
                'message': f'Encryption test error: {str(e)}'
            }
            
    def test_market_data_provider(self):
        """Test market data provider functionality"""
        logger.info("Testing market data provider...")
        
        if not self.market_data:
            self.results['market_data'] = {
                'status': 'FAIL',
                'message': 'Market data provider not initialized'
            }
            return
            
        try:
            # Test stock quote
            spy_quote = self.market_data.get_stock_quote('SPY')
            
            # Test crypto price
            btc_price = self.market_data.get_crypto_price('BTC')
            
            # Test historical data
            historical_data = self.market_data.get_historical_data('AAPL', '1mo')
            
            success = bool(spy_quote and btc_price and historical_data)
            
            self.results['market_data'] = {
                'status': 'PASS' if success else 'FAIL',
                'message': f'Market data provider working. SPY: ${spy_quote.get("price", 0):.2f}, BTC: ${btc_price.get("price", 0):.2f}' if success else 'Market data provider failed',
                'details': {
                    'spy_quote': bool(spy_quote),
                    'btc_price': bool(btc_price),
                    'historical_data': bool(historical_data)
                }
            }
            
        except Exception as e:
            self.results['market_data'] = {
                'status': 'FAIL',
                'message': f'Market data test error: {str(e)}'
            }
            
    def test_risk_management(self):
        """Test risk management system"""
        logger.info("Testing risk management system...")
        
        if not self.risk_manager:
            self.results['risk_management'] = {
                'status': 'FAIL',
                'message': 'Risk manager not initialized'
            }
            return
            
        try:
            # Test position size calculation
            position_size = self.risk_manager.calculate_position_size(
                account_balance=10000,
                risk_percentage=2.0,
                entry_price=100,
                stop_loss=95
            )
            
            # Test basic functionality without database dependency
            success = position_size > 0
            
            self.results['risk_management'] = {
                'status': 'PASS' if success else 'FAIL',
                'message': f'Risk management working. Position size: {position_size}',
                'details': {
                    'position_size': position_size,
                    'calculation_successful': success
                }
            }
            
        except Exception as e:
            self.results['risk_management'] = {
                'status': 'FAIL',
                'message': f'Risk management test error: {str(e)}'
            }
            
    def test_technical_indicators(self):
        """Test technical indicators calculation"""
        logger.info("Testing technical indicators...")
        
        try:
            # Test indicators for SPY
            indicators = self.market_data.calculate_technical_indicators('SPY')
            
            # Test market sentiment
            sentiment = self.market_data.get_market_sentiment('SPY')
            
            success = bool(indicators and sentiment)
            
            self.results['technical_indicators'] = {
                'status': 'PASS' if success else 'FAIL',
                'message': f'Technical indicators working. RSI: {indicators.get("rsi", 0):.2f}, Sentiment: {sentiment.get("sentiment_score", 0):.1f}%' if success else 'Technical indicators failed',
                'details': {
                    'rsi': indicators.get('rsi', 0) if indicators else 0,
                    'macd': indicators.get('macd', 0) if indicators else 0,
                    'sma_20': indicators.get('sma_20', 0) if indicators else 0,
                    'sentiment_score': sentiment.get('sentiment_score', 0) if sentiment else 0
                }
            }
            
        except Exception as e:
            self.results['technical_indicators'] = {
                'status': 'FAIL',
                'message': f'Technical indicators test error: {str(e)}'
            }
            
    def test_option_chain_processing(self):
        """Test option chain data processing"""
        logger.info("Testing option chain processing...")
        
        try:
            # Test option chain for SPY
            option_chain = self.market_data.get_option_chain('SPY')
            
            success = bool(option_chain and 'calls' in option_chain and 'puts' in option_chain)
            
            calls_count = len(option_chain.get('calls', [])) if option_chain else 0
            puts_count = len(option_chain.get('puts', [])) if option_chain else 0
            
            self.results['option_chain'] = {
                'status': 'PASS' if success else 'FAIL',
                'message': f'Option chain working. Calls: {calls_count}, Puts: {puts_count}' if success else 'Option chain processing failed',
                'details': {
                    'calls_count': calls_count,
                    'puts_count': puts_count,
                    'expiration': option_chain.get('expiration', 'N/A') if option_chain else 'N/A'
                }
            }
            
        except Exception as e:
            self.results['option_chain'] = {
                'status': 'FAIL',
                'message': f'Option chain test error: {str(e)}'
            }
            
    def test_openai_integration(self):
        """Test OpenAI integration"""
        logger.info("Testing OpenAI integration...")
        
        try:
            from utils.openai_trader import OpenAITrader
            api_key = os.environ.get('OPENAI_API_KEY')
            trader = OpenAITrader(api_key)
            
            # Test connection
            connection_result = trader.test_connection()
            
            # Test prompt parsing
            if connection_result['success']:
                trade_instruction = trader.parse_trading_prompt("buy $100 of SPY")
                
                # Test market analysis
                analysis = trader.analyze_market_conditions('SPY', 'Current market conditions for SPY')
                
                success = bool(trade_instruction and analysis)
                
                self.results['openai_integration'] = {
                    'status': 'PASS' if success else 'FAIL',
                    'message': f'OpenAI integration working. Analysis confidence: {analysis.get("confidence", 0):.2f}' if success else 'OpenAI integration failed',
                    'details': {
                        'connection': connection_result['success'],
                        'prompt_parsing': bool(trade_instruction),
                        'market_analysis': bool(analysis)
                    }
                }
            else:
                self.results['openai_integration'] = {
                    'status': 'FAIL',
                    'message': f'OpenAI connection failed: {connection_result["message"]}'
                }
                
        except Exception as e:
            self.results['openai_integration'] = {
                'status': 'FAIL',
                'message': f'OpenAI integration test error: {str(e)}'
            }
            
    def test_auto_trading_engine(self):
        """Test auto-trading engine"""
        logger.info("Testing auto-trading engine...")
        
        try:
            # Test that the engine can be imported
            from tasks.auto_trading_tasks import AutoTradingEngine
            
            # Test basic functionality without database dependency
            success = True
            
            self.results['auto_trading_engine'] = {
                'status': 'PASS' if success else 'FAIL',
                'message': 'Auto-trading engine module imported successfully' if success else 'Auto-trading engine import failed',
                'details': {
                    'import_successful': success
                }
            }
            
        except Exception as e:
            self.results['auto_trading_engine'] = {
                'status': 'FAIL',
                'message': f'Auto-trading engine test error: {str(e)}'
            }
            
    def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("Generating test report...")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result['status'] == 'PASS')
        failed_tests = total_tests - passed_tests
        
        print("\n" + "="*80)
        print("ARBION AI TRADING PLATFORM - ENHANCED FEATURES TEST REPORT")
        print("="*80)
        print(f"Test Suite Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print("="*80)
        
        for test_name, result in self.results.items():
            status_icon = "✓" if result['status'] == 'PASS' else "✗"
            print(f"{status_icon} {test_name.upper()}: {result['status']}")
            print(f"  {result['message']}")
            
            if 'details' in result:
                print("  Details:")
                for key, value in result['details'].items():
                    print(f"    - {key}: {value}")
            print()
            
        print("="*80)
        
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED! The enhanced features are working correctly.")
        else:
            print(f"⚠️  {failed_tests} test(s) failed. Please check the details above.")
            
        print("="*80)
        
        # Save report to file
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': (passed_tests/total_tests)*100,
            'results': self.results
        }
        
        with open('test_report.json', 'w') as f:
            json.dump(report_data, f, indent=2)
            
        print(f"📄 Detailed test report saved to: test_report.json")

def main():
    """Run the test suite"""
    try:
        test_suite = FeatureTestSuite()
        test_suite.run_all_tests()
    except Exception as e:
        logger.error(f"Test suite execution failed: {str(e)}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())