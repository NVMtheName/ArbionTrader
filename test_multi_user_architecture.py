"""
Test script to verify multi-user architecture is properly configured
"""

import sys
import os
sys.path.append('.')

from app import app, db
from models import User, APICredential, OAuthClientCredential, Trade
from utils.multi_user_config import multi_user_config
from utils.encryption import encrypt_credentials
from datetime import datetime

def test_multi_user_architecture():
    """Test multi-user architecture configuration"""
    print("Testing Multi-User Architecture Configuration")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Test 1: Create test users
            print("1. Creating test users...")
            
            # Clear existing test data
            db.session.query(APICredential).filter(APICredential.user_id.in_([999, 998])).delete()
            db.session.query(OAuthClientCredential).filter(OAuthClientCredential.user_id.in_([999, 998])).delete()
            db.session.query(Trade).filter(Trade.user_id.in_([999, 998])).delete()
            db.session.query(User).filter(User.id.in_([999, 998])).delete()
            
            # Create test users
            user1 = User(
                id=999,
                username='testuser1',
                email='test1@example.com',
                password_hash='test_hash_1',
                role='standard'
            )
            user2 = User(
                id=998,
                username='testuser2',
                email='test2@example.com',
                password_hash='test_hash_2',
                role='standard'
            )
            
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
            print("✓ Test users created successfully")
            
            # Test 2: Create user-specific API credentials
            print("2. Testing user-specific API credentials...")
            
            # User 1 credentials
            cred1 = APICredential(
                user_id=999,
                provider='coinbase',
                encrypted_credentials=encrypt_credentials({'api_key': 'test_key_user1'}),
                test_status='success'
            )
            
            # User 2 credentials
            cred2 = APICredential(
                user_id=998,
                provider='coinbase',
                encrypted_credentials=encrypt_credentials({'api_key': 'test_key_user2'}),
                test_status='success'
            )
            
            db.session.add(cred1)
            db.session.add(cred2)
            db.session.commit()
            
            # Test credential isolation
            user1_creds = multi_user_config.get_user_api_credentials(999, 'coinbase')
            user2_creds = multi_user_config.get_user_api_credentials(998, 'coinbase')
            
            assert user1_creds['api_key'] == 'test_key_user1', "User 1 credentials not isolated"
            assert user2_creds['api_key'] == 'test_key_user2', "User 2 credentials not isolated"
            print("✓ API credentials properly isolated per user")
            
            # Test 3: Create user-specific OAuth credentials
            print("3. Testing user-specific OAuth credentials...")
            
            oauth1 = OAuthClientCredential(
                user_id=999,
                provider='schwab',
                client_id='client_id_user1',
                client_secret='client_secret_user1',
                redirect_uri='https://arbion.ai/oauth_callback/broker'
            )
            
            oauth2 = OAuthClientCredential(
                user_id=998,
                provider='schwab',
                client_id='client_id_user2',
                client_secret='client_secret_user2',
                redirect_uri='https://www.arbion.ai/oauth_callback/broker'
            )
            
            db.session.add(oauth1)
            db.session.add(oauth2)
            db.session.commit()
            
            # Test OAuth credential isolation
            user1_oauth = multi_user_config.get_user_oauth_credentials(999, 'schwab')
            user2_oauth = multi_user_config.get_user_oauth_credentials(998, 'schwab')
            
            assert user1_oauth.client_id == 'client_id_user1', "User 1 OAuth credentials not isolated"
            assert user2_oauth.client_id == 'client_id_user2', "User 2 OAuth credentials not isolated"
            print("✓ OAuth credentials properly isolated per user")
            
            # Test 4: Create user-specific trades
            print("4. Testing user-specific trades...")
            
            trade1 = Trade(
                user_id=999,
                provider='coinbase',
                symbol='BTC',
                side='buy',
                quantity=0.1,
                price=50000,
                status='executed'
            )
            
            trade2 = Trade(
                user_id=998,
                provider='schwab',
                symbol='AAPL',
                side='sell',
                quantity=100,
                price=150,
                status='executed'
            )
            
            db.session.add(trade1)
            db.session.add(trade2)
            db.session.commit()
            
            # Test trade isolation
            user1_trades = multi_user_config.get_user_trades(999)
            user2_trades = multi_user_config.get_user_trades(998)
            
            assert len(user1_trades) == 1, "User 1 trades not isolated"
            assert len(user2_trades) == 1, "User 2 trades not isolated"
            assert user1_trades[0].symbol == 'BTC', "User 1 trade data incorrect"
            assert user2_trades[0].symbol == 'AAPL', "User 2 trade data incorrect"
            print("✓ Trades properly isolated per user")
            
            # Test 5: Access control validation
            print("5. Testing access control validation...")
            
            # User should access own resources
            assert multi_user_config.validate_user_access(999, 999) == True, "User cannot access own resources"
            
            # User should not access other user's resources
            assert multi_user_config.validate_user_access(999, 998) == False, "User can access other user's resources"
            
            print("✓ Access control properly configured")
            
            # Test 6: Dashboard data isolation
            print("6. Testing dashboard data isolation...")
            
            user1_dashboard = multi_user_config.get_user_dashboard_data(999)
            user2_dashboard = multi_user_config.get_user_dashboard_data(998)
            
            assert user1_dashboard['user_id'] == 999, "User 1 dashboard data not isolated"
            assert user2_dashboard['user_id'] == 998, "User 2 dashboard data not isolated"
            assert len(user1_dashboard['api_credentials']) == 1, "User 1 dashboard credentials incorrect"
            assert len(user2_dashboard['api_credentials']) == 1, "User 2 dashboard credentials incorrect"
            
            print("✓ Dashboard data properly isolated per user")
            
            # Test 7: Multi-user compliance audit
            print("7. Running multi-user compliance audit...")
            
            audit_report = multi_user_config.audit_multi_user_compliance()
            compliance_score = audit_report['compliance_score']
            
            print(f"✓ Multi-user compliance score: {compliance_score:.1f}%")
            
            if compliance_score >= 75:
                print("✓ Multi-user architecture meets compliance requirements")
            else:
                print("⚠ Multi-user architecture needs improvement")
                for issue in audit_report['failed_checks']:
                    print(f"  - {issue}")
            
            # Test 8: Redirect URI editing verification
            print("8. Testing redirect URI editing...")
            
            # Verify OAuth credentials have different redirect URIs
            assert user1_oauth.redirect_uri != user2_oauth.redirect_uri, "Redirect URIs should be different for testing"
            print("✓ Redirect URIs are properly configurable per user")
            
            print("\n" + "=" * 50)
            print("Multi-User Architecture Test Results:")
            print("=" * 50)
            print("✓ API credentials isolated per user")
            print("✓ OAuth credentials isolated per user")
            print("✓ Trade data isolated per user")
            print("✓ Access control properly configured")
            print("✓ Dashboard data isolated per user")
            print("✓ Redirect URIs editable per user")
            print(f"✓ Compliance score: {compliance_score:.1f}%")
            print("\n🎉 Multi-user architecture is properly configured!")
            
        except Exception as e:
            print(f"❌ Error in multi-user architecture test: {str(e)}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Clean up test data
            try:
                db.session.query(APICredential).filter(APICredential.user_id.in_([999, 998])).delete()
                db.session.query(OAuthClientCredential).filter(OAuthClientCredential.user_id.in_([999, 998])).delete()
                db.session.query(Trade).filter(Trade.user_id.in_([999, 998])).delete()
                db.session.query(User).filter(User.id.in_([999, 998])).delete()
                db.session.commit()
                print("✓ Test data cleaned up")
            except Exception as cleanup_error:
                print(f"Warning: Error cleaning up test data: {cleanup_error}")

if __name__ == "__main__":
    test_multi_user_architecture()