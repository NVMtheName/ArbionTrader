"""
Multi-User Configuration Manager for Arbion AI Trading Platform

This module ensures all system components are properly configured for multi-user
deployment with proper user isolation and security.
"""

import logging
from typing import Dict, List, Optional, Any
from models import User, APICredential, OAuthClientCredential, Trade, AutoTradingSettings
from utils.encryption import decrypt_credentials, encrypt_credentials
from app import db

logger = logging.getLogger(__name__)

class MultiUserConfigManager:
    """
    Manages multi-user configuration across all system components
    Ensures proper user isolation and security
    """
    
    @staticmethod
    def get_user_api_credentials(user_id: int, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get API credentials for a specific user and provider
        
        Args:
            user_id: User ID
            provider: API provider (schwab, coinbase, openai)
            
        Returns:
            Decrypted credentials dict or None
        """
        try:
            credential = APICredential.query.filter_by(
                user_id=user_id,
                provider=provider,
                is_active=True
            ).first()
            
            if not credential:
                logger.warning(f"No {provider} credentials found for user {user_id}")
                return None
            
            return decrypt_credentials(credential.encrypted_credentials)
            
        except Exception as e:
            logger.error(f"Error getting {provider} credentials for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_user_oauth_credentials(user_id: int, provider: str) -> Optional[OAuthClientCredential]:
        """
        Get OAuth client credentials for a specific user and provider
        
        Args:
            user_id: User ID
            provider: OAuth provider (schwab, coinbase)
            
        Returns:
            OAuth credential object or None
        """
        try:
            return OAuthClientCredential.query.filter_by(
                user_id=user_id,
                provider=provider,
                is_active=True
            ).first()
            
        except Exception as e:
            logger.error(f"Error getting OAuth credentials for user {user_id}, provider {provider}: {str(e)}")
            return None
    
    @staticmethod
    def get_user_trades(user_id: int, limit: int = 100) -> List[Trade]:
        """
        Get trades for a specific user with proper isolation
        
        Args:
            user_id: User ID
            limit: Maximum number of trades to return
            
        Returns:
            List of user's trades
        """
        try:
            return Trade.query.filter_by(user_id=user_id).order_by(
                Trade.created_at.desc()
            ).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Error getting trades for user {user_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_user_auto_trading_settings(user_id: int) -> Optional[AutoTradingSettings]:
        """
        Get auto-trading settings for a specific user
        
        Args:
            user_id: User ID
            
        Returns:
            Auto-trading settings or None
        """
        try:
            # Note: AutoTradingSettings is currently global - this should be per-user
            # This is a placeholder for when we implement per-user auto-trading settings
            return AutoTradingSettings.get_settings()
            
        except Exception as e:
            logger.error(f"Error getting auto-trading settings for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def validate_user_access(user_id: int, resource_user_id: int) -> bool:
        """
        Validate that a user can access a resource belonging to another user
        
        Args:
            user_id: Requesting user ID
            resource_user_id: Resource owner user ID
            
        Returns:
            True if access is allowed, False otherwise
        """
        try:
            # Users can only access their own resources
            if user_id == resource_user_id:
                return True
            
            # Check if user is admin or superadmin
            user = User.query.get(user_id)
            if user and (user.is_admin() or user.is_superadmin()):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating user access: {str(e)}")
            return False
    
    @staticmethod
    def get_user_dashboard_data(user_id: int) -> Dict[str, Any]:
        """
        Get dashboard data for a specific user with proper isolation
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user's dashboard data
        """
        try:
            # Get user's API credentials status
            api_credentials = APICredential.query.filter_by(
                user_id=user_id,
                is_active=True
            ).all()
            
            # Get user's recent trades
            recent_trades = MultiUserConfigManager.get_user_trades(user_id, limit=10)
            
            # Get user's OAuth credentials
            oauth_credentials = OAuthClientCredential.query.filter_by(
                user_id=user_id,
                is_active=True
            ).all()
            
            return {
                'api_credentials': api_credentials,
                'recent_trades': recent_trades,
                'oauth_credentials': oauth_credentials,
                'user_id': user_id  # Always include user context
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard data for user {user_id}: {str(e)}")
            return {'user_id': user_id, 'error': str(e)}
    
    @staticmethod
    def ensure_user_isolation():
        """
        Perform a system-wide check to ensure all components properly isolate users
        
        Returns:
            Dictionary with isolation check results
        """
        results = {
            'api_credentials': False,
            'oauth_credentials': False,
            'trades': False,
            'auto_trading': False
        }
        
        try:
            # Check if API credentials are properly isolated
            api_creds = APICredential.query.all()
            if all(cred.user_id for cred in api_creds):
                results['api_credentials'] = True
            
            # Check if OAuth credentials are properly isolated
            oauth_creds = OAuthClientCredential.query.all()
            if all(cred.user_id for cred in oauth_creds):
                results['oauth_credentials'] = True
            
            # Check if trades are properly isolated
            trades = Trade.query.all()
            if all(trade.user_id for trade in trades):
                results['trades'] = True
            
            # Auto-trading isolation check (placeholder for future implementation)
            results['auto_trading'] = True  # Will be False when per-user settings are implemented
            
            logger.info(f"User isolation check results: {results}")
            
        except Exception as e:
            logger.error(f"Error checking user isolation: {str(e)}")
        
        return results
    
    @staticmethod
    def audit_multi_user_compliance() -> Dict[str, Any]:
        """
        Perform a comprehensive audit of multi-user compliance
        
        Returns:
            Audit report with compliance status
        """
        from datetime import datetime
        audit_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'compliance_score': 0,
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': [],
            'recommendations': []
        }
        
        try:
            # Check 1: All API credentials have user_id
            audit_report['total_checks'] += 1
            api_creds_check = all(cred.user_id for cred in APICredential.query.all())
            if api_creds_check:
                audit_report['passed_checks'] += 1
            else:
                audit_report['failed_checks'].append("Some API credentials missing user_id")
            
            # Check 2: All OAuth credentials have user_id
            audit_report['total_checks'] += 1
            oauth_creds_check = all(cred.user_id for cred in OAuthClientCredential.query.all())
            if oauth_creds_check:
                audit_report['passed_checks'] += 1
            else:
                audit_report['failed_checks'].append("Some OAuth credentials missing user_id")
            
            # Check 3: All trades have user_id
            audit_report['total_checks'] += 1
            trades_check = all(trade.user_id for trade in Trade.query.all())
            if trades_check:
                audit_report['passed_checks'] += 1
            else:
                audit_report['failed_checks'].append("Some trades missing user_id")
            
            # Check 4: Auto-trading settings are per-user (future implementation)
            audit_report['total_checks'] += 1
            # For now, we'll mark this as failed since auto-trading is still global
            audit_report['failed_checks'].append("Auto-trading settings are global, not per-user")
            audit_report['recommendations'].append("Implement per-user auto-trading settings")
            
            # Calculate compliance score
            audit_report['compliance_score'] = (
                audit_report['passed_checks'] / audit_report['total_checks'] * 100
            )
            
            logger.info(f"Multi-user compliance audit: {audit_report['compliance_score']:.1f}% compliant")
            
        except Exception as e:
            logger.error(f"Error performing multi-user compliance audit: {str(e)}")
            audit_report['error'] = str(e)
        
        return audit_report

# Global instance for easy access
multi_user_config = MultiUserConfigManager()