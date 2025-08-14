# Heroku Deployment Database Fix

## Issue
Your Heroku deployment is failing because the production PostgreSQL database is missing required columns that were added to the Trade model. The error shows:

```
column "is_simulation" doesn't exist in table "trade"
column "fees" doesn't exist in table "trade"
```

## Solution
Run the following migration on your Heroku PostgreSQL database:

### Option 1: Using Heroku CLI
```bash
# Connect to your Heroku PostgreSQL database
heroku pg:psql --app your-app-name

# Then run the migration SQL
\i heroku_db_migration.sql
```

### Option 2: Manual Migration
Copy the contents of `heroku_db_migration.sql` and run it directly in your Heroku PostgreSQL database via:

1. **Heroku Dashboard Method:**
   - Go to your Heroku app dashboard
   - Click on the PostgreSQL add-on
   - Use the database console to run the SQL commands

2. **Command Line Method:**
```bash
heroku pg:psql --app your-app-name < heroku_db_migration.sql
```

### Option 3: Quick Fix Commands
If you prefer to run individual commands:

```bash
heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS is_simulation BOOLEAN DEFAULT false;"
heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS fees DECIMAL(15,8) DEFAULT 0.0;"
heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS commission DECIMAL(15,8) DEFAULT 0.0;"
```

## Key Missing Columns Added:
- `is_simulation` (BOOLEAN) - For simulation trading mode
- `fees` (DECIMAL) - Trading fees tracking
- `commission` (DECIMAL) - Commission tracking
- `realized_pnl`, `unrealized_pnl` - P&L tracking
- `market_value`, `cost_basis` - Position tracking
- `risk_score`, `confidence_score` - AI analytics
- `exit_price`, `exit_date` - Position exit tracking

## After Migration:
1. Your Heroku app should deploy successfully
2. All trading features will work properly
3. Analytics and reporting will function correctly
4. Database integrity will be maintained

## Prevention:
For future deployments, consider using Flask-Migrate for automatic database migrations:
```bash
flask db migrate -m "Add new trading columns"
flask db upgrade
```

This ensures development and production databases stay in sync automatically.