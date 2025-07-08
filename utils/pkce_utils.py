import secrets
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)

def generate_pkce_pair():
    """Generate PKCE code verifier and challenge for OAuth2 flow"""
    try:
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        
        logger.info("Generated PKCE pair successfully")
        return code_verifier, code_challenge
    
    except Exception as e:
        logger.error(f"Error generating PKCE pair: {str(e)}")
        raise

def validate_pkce_pair(code_verifier, code_challenge):
    """Validate that code verifier matches the challenge"""
    try:
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")
        
        return expected_challenge == code_challenge
    
    except Exception as e:
        logger.error(f"Error validating PKCE pair: {str(e)}")
        return False