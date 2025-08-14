# Simple Heroku Database Fix

## The Problem
Your Heroku app is crashing because the database is missing some columns that the code expects.

## 3 Easy Solutions (Choose One)

### Option 1: Automatic Script (Easiest)
```bash
python quick_heroku_fix.py
```
Just run this script and enter your Heroku app name when prompted.

### Option 2: Manual Commands (Simple)
Open your terminal and run these commands one by one:

Replace `your-app-name` with your actual Heroku app name:

```bash
heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS is_simulation BOOLEAN DEFAULT false;"

heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS fees DECIMAL(15,8) DEFAULT 0.0;"

heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS commission DECIMAL(15,8) DEFAULT 0.0;"
```

### Option 3: Heroku Dashboard (Web Interface)
1. Go to https://dashboard.heroku.com/apps
2. Click on your app
3. Click on the PostgreSQL add-on
4. Click "Settings" then "View Credentials"
5. Use the database URL with any PostgreSQL client
6. Run the SQL commands from `heroku_db_migration.sql`

## After Running the Fix
1. Your app should deploy without errors
2. All features will work properly
3. You can add your API credentials and start trading

## Need Help?
If you get stuck:
1. Make sure you have the Heroku CLI installed
2. Make sure you're logged in: `heroku login`
3. Check your app name: `heroku apps`

The fix only takes 2-3 minutes to complete!