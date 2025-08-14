# Simple Database Fix (No Heroku CLI Needed)

## Problem
Heroku CLI authentication isn't working from Replit due to IP address mismatch.

## Easy Solution
Use the direct database connection method instead:

### Step 1: Get Your Database URL
1. Go to https://dashboard.heroku.com/apps/trading-botv1
2. Click "Settings" tab
3. Click "Reveal Config Vars"
4. Copy the entire DATABASE_URL value (starts with `postgres://`)

### Step 2: Edit the Migration Script
1. Open `run_db_migration.py` (I just created it)
2. Find this line: `DATABASE_URL = "YOUR_DATABASE_URL_HERE"`
3. Replace `YOUR_DATABASE_URL_HERE` with your actual DATABASE_URL

### Step 3: Run the Fix
```bash
python run_db_migration.py
```

### Alternative: Web Interface
If the Python method doesn't work, use Heroku's web interface:

1. Go to https://dashboard.heroku.com/apps/trading-botv1
2. Click on your PostgreSQL add-on
3. Click "Settings" → "View Credentials"
4. Use any PostgreSQL client with those credentials
5. Run the SQL commands from `quick_sql_fix.sql`

## What This Fixes
Adds the missing database columns that are causing your app to crash:
- `is_simulation` 
- `fees`
- `commission`
- And other analytics columns

## After the Fix
Your Heroku app will deploy and run without database errors.

The direct connection method bypasses all the Heroku CLI authentication issues!