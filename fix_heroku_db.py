#!/usr/bin/env python3
"""
Direct Heroku Database Fix Script
This connects directly to your Heroku PostgreSQL database and fixes the schema
"""

import os
import psycopg2
from urllib.parse import urlparse

def fix_heroku_database():
    """Fix the Heroku database schema directly"""
    
    print("Heroku Database Fix Tool")
    print("=" * 30)
    
    # Get database URL from user
    print("\nTo find your DATABASE_URL:")
    print("1. Go to https://dashboard.heroku.com/apps")
    print("2. Click your app name")
    print("3. Go to Settings > Config Vars")
    print("4. Copy the DATABASE_URL value")
    print()
    
    database_url = input("Paste your Heroku DATABASE_URL here: ").strip()
    
    if not database_url:
        print("Error: DATABASE_URL is required")
        return False
    
    try:
        # Parse the database URL
        url = urlparse(database_url)
        
        # Connect to the database
        print("Connecting to Heroku PostgreSQL...")
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            database=url.path[1:],  # Remove leading slash
            user=url.username,
            password=url.password,
            sslmode='require'
        )
        
        cursor = conn.cursor()
        print("✓ Connected successfully!")
        
        # Migration commands
        migrations = [
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS is_simulation BOOLEAN DEFAULT false;",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS fees DECIMAL(15,8) DEFAULT 0.0;",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS commission DECIMAL(15,8) DEFAULT 0.0;",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS realized_pnl DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS unrealized_pnl DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS market_value DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS cost_basis DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS portfolio_percentage DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS risk_score DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS confidence_score DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS exit_price DECIMAL(15,8);",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS exit_date TIMESTAMP;",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS holding_period_days INTEGER;",
            "ALTER TABLE trade ADD COLUMN IF NOT EXISTS trade_notes TEXT;"
        ]
        
        # Run migrations
        print("Running database migrations...")
        for i, migration in enumerate(migrations, 1):
            try:
                cursor.execute(migration)
                print(f"✓ Migration {i}/{len(migrations)} completed")
            except Exception as e:
                print(f"⚠ Migration {i}: {str(e)}")
        
        # Commit changes
        conn.commit()
        print("\n✓ All migrations completed!")
        print("✓ Database schema is now fixed!")
        
        # Close connection
        cursor.close()
        conn.close()
        
        print("\nNext steps:")
        print("1. Redeploy your Heroku app")
        print("2. Your app should now work without database errors")
        
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Make sure your DATABASE_URL is correct")
        print("2. Check that your Heroku PostgreSQL add-on is active")
        print("3. Verify you have database access permissions")
        return False

if __name__ == "__main__":
    success = fix_heroku_database()
    if success:
        print("\n🎉 Database fixed successfully!")
    else:
        print("\n❌ Fix failed. Please contact support.")