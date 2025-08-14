# Easy Heroku Database Fix

## What's Wrong?
Your Heroku app is crashing because the database is missing some columns.

## Quick Fix (2 minutes)
Run this command in the terminal below:

```bash
python fix_heroku_db.py
```

## What You Need:
1. Your Heroku DATABASE_URL (I'll show you how to get it)

## Step by Step:
1. **Get Your Database URL:**
   - Go to https://dashboard.heroku.com/apps
   - Click your app name
   - Click "Settings"
   - Click "Reveal Config Vars"
   - Copy the value next to "DATABASE_URL"

2. **Run the Fix:**
   - Type: `python fix_heroku_db.py`
   - Paste your DATABASE_URL when asked
   - Wait for "Database fixed successfully!"

3. **Redeploy Your App:**
   - Your app will now work without errors

## Alternative: Manual Commands
If you prefer using Heroku CLI:
```bash
heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS is_simulation BOOLEAN DEFAULT false;"
heroku pg:psql --app your-app-name -c "ALTER TABLE trade ADD COLUMN IF NOT EXISTS fees DECIMAL(15,8) DEFAULT 0.0;"
```

## Need Help?
Just tell me what error you see and I'll help you through it.

The fix only takes 2 minutes once you have your DATABASE_URL!