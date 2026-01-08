# Heroku Redis Setup Guide

## Issue
Celery worker cannot connect to Redis:
```
[ERROR] consumer: Cannot connect to redis://localhost:6379/0: Connection refused
```

## Root Cause
The Heroku app doesn't have a Redis addon provisioned, so `REDIS_URL` environment variable is not set.

## Solution: Add Heroku Redis

### Option 1: Using Heroku CLI (Recommended)

```bash
# Add Heroku Redis addon (free mini plan)
heroku addons:create heroku-redis:mini --app trading-botv1

# Verify Redis is provisioned
heroku addons:info heroku-redis --app trading-botv1

# Check that REDIS_URL is now set
heroku config:get REDIS_URL --app trading-botv1
```

### Option 2: Using Heroku Dashboard

1. Go to https://dashboard.heroku.com/apps/trading-botv1
2. Click on the **"Resources"** tab
3. In "Add-ons" search bar, type: **"Heroku Redis"**
4. Select **"Heroku Redis"** and choose a plan:
   - **Mini** (Free) - 25MB, good for development
   - **Premium-0** ($15/month) - 256MB, for production
5. Click **"Submit Order Form"**

### Option 3: Manual Redis URL Configuration

If you're using an external Redis service (like Redis Cloud, Upstash, etc.):

```bash
# Set the Redis URL manually
heroku config:set REDIS_URL="redis://username:password@your-redis-host:port" --app trading-botv1

# Or set Celery-specific variables
heroku config:set CELERY_BROKER_URL="redis://username:password@your-redis-host:port/0" --app trading-botv1
heroku config:set CELERY_RESULT_BACKEND="redis://username:password@your-redis-host:port/0" --app trading-botv1
```

## Verify Setup

After adding Redis, restart your app and check the logs:

```bash
# Restart the app
heroku restart --app trading-botv1

# Monitor logs
heroku logs --tail --app trading-botv1
```

You should see:
```
✓ Redis cache configured: redis://your-redis-url
✓ Rate limiting configured: redis://your-redis-url
[celery] Connected to redis://your-redis-url
```

No more "Connection refused" errors!

## Redis Plans Comparison

| Plan | Price | Storage | Connections | Best For |
|------|-------|---------|-------------|----------|
| Mini | Free | 25MB | 20 | Development/Testing |
| Premium-0 | $15/mo | 256MB | 40 | Small Production |
| Premium-1 | $50/mo | 1GB | 200 | Medium Production |
| Premium-2 | $200/mo | 5GB | 500 | Large Production |

## What Uses Redis in This App

1. **Celery Broker** - Task queue management
2. **Celery Results** - Stores task results
3. **Flask Cache** - API response caching
4. **Rate Limiting** - Request rate limiting

All of these require Redis to function properly.

## Alternative: Disable Celery Worker (Not Recommended)

If you don't want to use Redis, you can disable the worker dyno:

```bash
heroku ps:scale worker=0 beat=0 --app trading-botv1
```

**Warning:** This disables:
- Background tasks (stop-loss monitoring, token refresh)
- Scheduled jobs (log cleanup, API status updates)
- Async trading operations

Only use this for development/testing purposes.
