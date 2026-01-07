import os
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

logger = logging.getLogger(__name__)

def get_encryption_key():
    """
    Generate or retrieve encryption key for API credentials

    SECURITY: This function requires ENCRYPTION_KEY or SESSION_SECRET to be set.
    No default fallback to prevent weak encryption in production.

    Environment Variables (in priority order):
    1. ENCRYPTION_KEY: Direct Fernet key (base64-encoded, 32 bytes)
    2. ENCRYPTION_SECRET + ENCRYPTION_SALT: Password + salt for key derivation
    3. SESSION_SECRET + ENCRYPTION_SALT: Fallback to session secret

    Raises:
        ValueError: If no encryption key material is available
    """
    # Priority 1: Use direct encryption key if provided (recommended for production)
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if encryption_key:
        try:
            # Validate it's a proper Fernet key
            Fernet(encryption_key.encode())
            return encryption_key.encode()
        except Exception as e:
            logger.error("ENCRYPTION_KEY is set but invalid. Key must be base64-encoded 32-byte string.")
            raise ValueError(f"Invalid ENCRYPTION_KEY: {str(e)}")

    # Priority 2: Derive key from ENCRYPTION_SECRET + ENCRYPTION_SALT
    encryption_secret = os.environ.get("ENCRYPTION_SECRET")
    encryption_salt = os.environ.get("ENCRYPTION_SALT")

    if encryption_secret and encryption_salt:
        password = encryption_secret.encode()
        salt = encryption_salt.encode()
    elif os.environ.get("SESSION_SECRET") and encryption_salt:
        # Priority 3: Fallback to SESSION_SECRET (for backward compatibility)
        logger.warning(
            "Using SESSION_SECRET for encryption. "
            "Set ENCRYPTION_SECRET for better security separation."
        )
        password = os.environ.get("SESSION_SECRET").encode()
        salt = encryption_salt.encode()
    else:
        # No valid encryption configuration found
        error_msg = (
            "No encryption key configured! Set one of:\n"
            "  1. ENCRYPTION_KEY (recommended): Direct Fernet key\n"
            "  2. ENCRYPTION_SECRET + ENCRYPTION_SALT: For key derivation\n"
            "  3. SESSION_SECRET + ENCRYPTION_SALT: Fallback option\n\n"
            "To generate a new key: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'\n"
            "To generate salt: python -c 'import secrets; print(secrets.token_hex(16))'"
        )
        logger.critical(error_msg)
        raise ValueError(error_msg)

    # Derive key using PBKDF2
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    except Exception as e:
        logger.error(f"Failed to derive encryption key: {str(e)}")
        raise ValueError(f"Key derivation failed: {str(e)}")

def validate_encryption_config():
    """
    Validate encryption configuration on application startup

    Returns:
        tuple: (is_valid: bool, message: str)
    """
    try:
        # Try to get the encryption key
        key = get_encryption_key()

        # Test encryption/decryption
        test_data = {'test': 'validation'}
        encrypted = encrypt_credentials(test_data)
        decrypted = decrypt_credentials(encrypted)

        if decrypted == test_data:
            config_method = None
            if os.environ.get("ENCRYPTION_KEY"):
                config_method = "ENCRYPTION_KEY (direct)"
            elif os.environ.get("ENCRYPTION_SECRET"):
                config_method = "ENCRYPTION_SECRET + ENCRYPTION_SALT"
            else:
                config_method = "SESSION_SECRET + ENCRYPTION_SALT (fallback)"

            return True, f"Encryption configured correctly using: {config_method}"
        else:
            return False, "Encryption test failed: decrypted data doesn't match original"

    except Exception as e:
        return False, f"Encryption validation failed: {str(e)}"

def encrypt_credentials(credentials_dict):
    """Encrypt API credentials dictionary"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        
        # Convert dict to JSON string
        credentials_json = json.dumps(credentials_dict)
        
        # Encrypt the JSON string
        encrypted_data = f.encrypt(credentials_json.encode())
        
        return encrypted_data
    
    except Exception as e:
        logging.error(f"Error encrypting credentials: {str(e)}")
        raise

def decrypt_credentials(encrypted_data):
    """Decrypt API credentials and return as dictionary"""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        
        # Decrypt the data
        decrypted_data = f.decrypt(encrypted_data)
        
        # Convert back to dictionary
        credentials_dict = json.loads(decrypted_data.decode())
        
        return credentials_dict
    
    except Exception as e:
        logging.error(f"Error decrypting credentials: {str(e)}")
        raise

def test_encryption():
    """Test encryption/decryption functionality"""
    test_data = {
        'api_key': 'test_key_123',
        'secret': 'test_secret_456',
        'passphrase': 'test_passphrase_789'
    }
    
    try:
        encrypted = encrypt_credentials(test_data)
        decrypted = decrypt_credentials(encrypted)
        
        assert decrypted == test_data
        logging.info("Encryption test passed")
        return True
    
    except Exception as e:
        logging.error(f"Encryption test failed: {str(e)}")
        return False
