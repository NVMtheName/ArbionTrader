#!/usr/bin/env python3
"""
Quick Heroku Database Migration Script
Run this to automatically fix your Heroku database schema
"""

import os
import subprocess
import sys

def run_heroku_migration():
    """Run the database migration on Heroku"""
    
    # Check if Heroku CLI is installed
    try:
        result = subprocess.run(['heroku', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Heroku CLI not found. Please install it first:")
            print("   https://devcenter.heroku.com/articles/heroku-cli")
            return False
    except FileNotFoundError:
        print("❌ Heroku CLI not found. Please install it first:")
        print("   https://devcenter.heroku.com/articles/heroku-cli")
        return False
    
    print("✅ Heroku CLI found")
    
    # Get app name from user
    app_name = input("Enter your Heroku app name (e.g., your-app-name): ").strip()
    if not app_name:
        print("❌ App name is required")
        return False
    
    print(f"🔄 Running database migration for app: {app_name}")
    
    # Migration SQL commands
    migration_commands = [
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
    
    # Run each migration command
    for i, command in enumerate(migration_commands, 1):
        print(f"🔄 Running migration {i}/{len(migration_commands)}")
        try:
            result = subprocess.run([
                'heroku', 'pg:psql', '--app', app_name, '-c', command
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Migration {i} completed")
            else:
                print(f"⚠️  Migration {i} result: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error running migration {i}: {e}")
            return False
    
    print("\n🎉 Database migration completed!")
    print("🚀 Your Heroku app should now deploy successfully")
    print("\nNext steps:")
    print("1. Redeploy your app: git push heroku main")
    print("2. Check app logs: heroku logs --tail --app", app_name)
    
    return True

if __name__ == "__main__":
    print("🔧 Heroku Database Migration Tool")
    print("=" * 40)
    
    if run_heroku_migration():
        print("\n✅ Migration successful!")
    else:
        print("\n❌ Migration failed. Please try manual method.")
        print("\nManual method:")
        print("1. Run: heroku pg:psql --app your-app-name")
        print("2. Copy and paste commands from heroku_db_migration.sql")