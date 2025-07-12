#!/usr/bin/env python3
"""
Migration script to clean up legacy Schwab API credentials and prompt users to set up OAuth2
"""

from app import create_app
app = create_app()

def migrate_schwab_to_oauth():
    """Migrate existing Schwab API credentials to OAuth2"""
    with app.app_context():
        from models import APICredential, User
        from utils.encryption import decrypt_credentials
        from app import db
        
        print("=== Schwab OAuth2 Migration ===")
        
        # Find all Schwab credentials
        schwab_creds = APICredential.query.filter_by(provider='schwab').all()
        print(f"Found {len(schwab_creds)} Schwab credential records")
        
        legacy_count = 0
        oauth_count = 0
        
        for cred in schwab_creds:
            user = User.query.get(cred.user_id)
            username = user.username if user else "Unknown"
            
            try:
                decrypted_creds = decrypt_credentials(cred.encrypted_credentials)
                
                if 'api_key' in decrypted_creds and 'secret' in decrypted_creds:
                    # Legacy API key format
                    legacy_count += 1
                    print(f"User {username} (ID: {cred.user_id}): Legacy API keys detected")
                    
                    # Mark as needing OAuth2 setup
                    cred.test_status = 'oauth_required'
                    cred.is_active = False
                    
                elif 'access_token' in decrypted_creds:
                    # OAuth2 format
                    oauth_count += 1
                    print(f"User {username} (ID: {cred.user_id}): OAuth2 tokens present")
                    cred.is_active = True
                    
                else:
                    print(f"User {username} (ID: {cred.user_id}): Unknown credential format")
                    
            except Exception as e:
                print(f"User {username} (ID: {cred.user_id}): Error processing credentials - {e}")
        
        try:
            db.session.commit()
            print(f"\nMigration completed successfully:")
            print(f"- Legacy API key users: {legacy_count}")
            print(f"- OAuth2 users: {oauth_count}")
            print(f"- Total users needing OAuth2 setup: {legacy_count}")
            
            if legacy_count > 0:
                print(f"\nUsers with legacy credentials will see a message to set up OAuth2")
                print(f"They need to:")
                print(f"1. Go to API Settings")
                print(f"2. Configure OAuth2 client credentials")
                print(f"3. Complete the OAuth2 authorization flow")
                
        except Exception as e:
            print(f"Error saving migration changes: {e}")
            db.session.rollback()

if __name__ == "__main__":
    migrate_schwab_to_oauth()