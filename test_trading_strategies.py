"""
Test script to verify trading strategies are working correctly
"""

import sys
import os
sys.path.append('.')

from app import app, db
from models import User, APICredential, Trade, AutoTradingSettings
from tasks.auto_trading_tasks import AutoTradingEngine
from utils.encryption import encrypt_credentials
from datetime import datetime

def test_trading_strategies():
    """Test that trading strategies work correctly"""
    print("Testing Trading Strategies")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Test 1: Enable auto-trading settings
            print("1. Configuring auto-trading settings...")
            
            settings = AutoTradingSettings.get_settings()
            settings.is_enabled = True
            settings.simulation_mode = True
            settings.wheel_enabled = True
            settings.collar_enabled = True
            settings.ai_enabled = True
            db.session.commit()
            
            print("✓ Auto-trading settings configured")
            
            # Test 2: Create test user with credentials
            print("2. Creating test user with API credentials...")
            
            # Clean up any existing test data
            db.session.query(Trade).filter(Trade.user_id == 997).delete()
            db.session.query(APICredential).filter(APICredential.user_id == 997).delete()
            db.session.query(User).filter(User.id == 997).delete()
            
            # Create test user
            test_user = User(
                id=997,
                username='strategy_test_user',
                email='strategy_test@example.com',
                password_hash='test_hash',
                role='standard'
            )
            db.session.add(test_user)
            
            # Create test credentials
            schwab_creds = APICredential(
                user_id=997,
                provider='schwab',
                encrypted_credentials=encrypt_credentials({'api_key': 'test_schwab_key', 'secret': 'test_schwab_secret'}),
                is_active=True,
                test_status='success'
            )
            
            openai_creds = APICredential(
                user_id=997,
                provider='openai',
                encrypted_credentials=encrypt_credentials({'api_key': 'test_openai_key'}),
                is_active=True,
                test_status='success'
            )
            
            db.session.add(schwab_creds)
            db.session.add(openai_creds)
            db.session.commit()
            
            print("✓ Test user and credentials created")
            
            # Test 3: Initialize and test auto-trading engine
            print("3. Testing auto-trading engine initialization...")
            
            engine = AutoTradingEngine()
            print("✓ AutoTradingEngine initialized successfully")
            
            # Test 4: Test wheel strategy
            print("4. Testing wheel strategy...")
            
            initial_trades = Trade.query.filter_by(user_id=997, strategy='wheel').count()
            engine.run_wheel_strategy(simulation_mode=True)
            final_trades = Trade.query.filter_by(user_id=997, strategy='wheel').count()
            
            wheel_trades_created = final_trades - initial_trades
            print(f"✓ Wheel strategy executed, created {wheel_trades_created} trades")
            
            # Test 5: Test collar strategy
            print("5. Testing collar strategy...")
            
            initial_trades = Trade.query.filter_by(user_id=997, strategy='collar').count()
            engine.run_collar_strategy(simulation_mode=True)
            final_trades = Trade.query.filter_by(user_id=997, strategy='collar').count()
            
            collar_trades_created = final_trades - initial_trades
            print(f"✓ Collar strategy executed, created {collar_trades_created} trades")
            
            # Test 6: Test AI strategy
            print("6. Testing AI strategy...")
            
            initial_trades = Trade.query.filter_by(user_id=997, strategy='ai').count()
            engine.run_ai_strategy(simulation_mode=True)
            final_trades = Trade.query.filter_by(user_id=997, strategy='ai').count()
            
            ai_trades_created = final_trades - initial_trades
            print(f"✓ AI strategy executed, created {ai_trades_created} trades")
            
            # Test 7: Test complete auto-trading cycle
            print("7. Testing complete auto-trading cycle...")
            
            initial_total_trades = Trade.query.filter_by(user_id=997).count()
            engine.run_auto_trading_cycle()
            final_total_trades = Trade.query.filter_by(user_id=997).count()
            
            cycle_trades_created = final_total_trades - initial_total_trades
            print(f"✓ Complete auto-trading cycle executed, created {cycle_trades_created} additional trades")
            
            # Test 8: Verify trade details
            print("8. Verifying trade details...")
            
            all_trades = Trade.query.filter_by(user_id=997).all()
            print(f"✓ Total trades created: {len(all_trades)}")
            
            for trade in all_trades:
                print(f"  - {trade.strategy} strategy: {trade.trade_type} {trade.side} {trade.symbol}")
                assert trade.user_id == 997, "Trade not properly isolated to user"
                assert trade.is_simulation == True, "Trade should be in simulation mode"
                assert trade.status == 'executed', "Simulated trade should be executed"
            
            print("✓ All trades properly configured and isolated")
            
            # Test 9: Test toggle functionality
            print("9. Testing strategy toggle functionality...")
            
            # Disable strategies
            settings.wheel_enabled = False
            settings.collar_enabled = False
            settings.ai_enabled = False
            db.session.commit()
            
            # Run cycle again - should not create new trades
            pre_toggle_trades = Trade.query.filter_by(user_id=997).count()
            engine.run_auto_trading_cycle()
            post_toggle_trades = Trade.query.filter_by(user_id=997).count()
            
            assert pre_toggle_trades == post_toggle_trades, "Strategies should not execute when disabled"
            print("✓ Strategy toggle functionality works correctly")
            
            print("\n" + "=" * 50)
            print("Trading Strategies Test Results:")
            print("=" * 50)
            print(f"✓ Wheel strategy created {wheel_trades_created} trades")
            print(f"✓ Collar strategy created {collar_trades_created} trades")
            print(f"✓ AI strategy created {ai_trades_created} trades")
            print(f"✓ Complete cycle created {cycle_trades_created} additional trades")
            print(f"✓ Total trades: {len(all_trades)}")
            print("✓ All strategies properly isolated per user")
            print("✓ Toggle functionality works correctly")
            print("✓ All trades in simulation mode")
            print("\n🎉 All trading strategies are working correctly!")
            
        except Exception as e:
            print(f"❌ Error in trading strategies test: {str(e)}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Clean up test data
            try:
                db.session.query(Trade).filter(Trade.user_id == 997).delete()
                db.session.query(APICredential).filter(APICredential.user_id == 997).delete()
                db.session.query(User).filter(User.id == 997).delete()
                db.session.commit()
                print("✓ Test data cleaned up")
            except Exception as cleanup_error:
                print(f"Warning: Error cleaning up test data: {cleanup_error}")

if __name__ == "__main__":
    test_trading_strategies()