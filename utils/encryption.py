import os
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

def get_encryption_key():
    """Generate or retrieve encryption key for API credentials"""
    # Use a combination of environment variables to create a consistent key
    password = os.environ.get("SESSION_SECRET", "default-secret-key").encode()
    salt = b"arbion-salt-2024"  # Fixed salt for consistent key generation
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

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
