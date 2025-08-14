#!/usr/bin/env python3
"""
Direct Database Fix - No Heroku CLI needed
Connect directly to your PostgreSQL database
"""

import psycopg2
from urllib.parse import urlparse

def fix_database_directly():
    """Fix database using direct PostgreSQL connection"""
    
    print("Direct Database Fix Tool")
    print("=" * 30)
    print()
    print("Since Heroku CLI has authentication issues, we'll connect directly.")
    print()
    print("To get your DATABASE_URL:")
    print("1. Go to https://dashboard.heroku.com/apps/trading-botv1")
    print("2. Click 'Settings' tab")
    print("3. Click 'Reveal Config Vars'")
    print("4. Copy the DATABASE_URL value")
    print()
    print("Your DATABASE_URL should look like:")
    print("postgres://username:password@hostname:port/database")
    print()
    
    # For now, let's create the fix that can be run manually
    database_url = "YOUR_DATABASE_URL_HERE"  # User will replace this
    
    # Create the connection and migration code
    migration_code = '''
import psycopg2
from urllib.parse import urlparse

# Replace this with your actual DATABASE_URL from Heroku
DATABASE_URL = "YOUR_DATABASE_URL_HERE"

try:
    # Parse the database URL
    url = urlparse(DATABASE_URL)
    
    # Connect to the database
    print("Connecting to database...")
    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port or 5432,
        database=url.path[1:],  # Remove leading slash
        user=url.username,
        password=url.password,
        sslmode='require'
    )
    
    cursor = conn.cursor()
    print("Connected successfully!")
    
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
            print(f"Migration {i}/{len(migrations)} completed")
        except Exception as e:
            print(f"Migration {i} result: {str(e)}")
    
    # Commit changes
    conn.commit()
    print("All migrations completed!")
    print("Database schema is now fixed!")
    
    # Close connection
    cursor.close()
    conn.close()
    
    print("\\nYour Heroku app should now deploy successfully!")
    
except Exception as e:
    print(f"Error: {str(e)}")
    print("\\nDouble-check your DATABASE_URL is correct")

'''
    
    # Write the migration script
    with open('run_db_migration.py', 'w') as f:
        f.write(migration_code)
    
    print("✓ Created run_db_migration.py")
    print()
    print("Next steps:")
    print("1. Get your DATABASE_URL from Heroku (instructions above)")
    print("2. Edit run_db_migration.py")
    print("3. Replace YOUR_DATABASE_URL_HERE with your actual URL")
    print("4. Run: python run_db_migration.py")
    print()
    print("This will fix your database directly without needing Heroku CLI!")

if __name__ == "__main__":
    fix_database_directly()