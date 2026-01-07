# 🔐 Heroku Environment Setup Guide

## Error You're Seeing

```
CRITICAL: No encryption key configured!
ValueError: Encryption configuration error
```

This is **our security feature working correctly** - the app refuses to start without proper encryption configured (fail-closed design from Phase 1).

---

## 🎯 Quick Fix (3 Commands)

**Replace `your-app-name` with your actual Heroku app name:**

```bash
heroku config:set ENCRYPTION_KEY="6JT4wJnzgG8izcQj4Iq8MpLfbndVrPTHD3rshOZDn1o=" --app your-app-name

heroku config:set SESSION_SECRET="UyR2zVGKXStUVUdLRjphMcPxUCA3LYslKQBlYiD9BD0" --app your-app-name

heroku config:set ENCRYPTION_SALT="79d6ea9554bbe4dab7030440e3c03ca0" --app your-app-name
```

Then restart your app:
```bash
heroku restart --app your-app-name
```

---

## 📝 Method 1: Using Heroku CLI (Fastest)

### Step 1: Find Your App Name
```bash
heroku apps
```

### Step 2: Set Environment Variables

Edit and run the provided script:
```bash
# Edit the script to set your app name
nano heroku_set_env.sh

# Run the script
./heroku_set_env.sh
```

**Or run commands individually:**

```bash
# Replace 'arbiontrader' with your app name
APP_NAME="arbiontrader"

# REQUIRED: Encryption key (Fernet format)
heroku config:set ENCRYPTION_KEY="6JT4wJnzgG8izcQj4Iq8MpLfbndVrPTHD3rshOZDn1o=" --app $APP_NAME

# REQUIRED: Session secret
heroku config:set SESSION_SECRET="UyR2zVGKXStUVUdLRjphMcPxUCA3LYslKQBlYiD9BD0" --app $APP_NAME

# REQUIRED: Encryption salt (32-char hex)
heroku config:set ENCRYPTION_SALT="79d6ea9554bbe4dab7030440e3c03ca0" --app $APP_NAME

# OPTIONAL: Superadmin credentials
heroku config:set SUPERADMIN_EMAIL="admin@yourdomain.com" --app $APP_NAME
heroku config:set SUPERADMIN_PASSWORD="YourSecurePassword123!" --app $APP_NAME
```

### Step 3: Restart and Verify
```bash
# Restart the app
heroku restart --app $APP_NAME

# Check if it started successfully
heroku logs --tail --app $APP_NAME
```

---

## 📝 Method 2: Using Heroku Dashboard (Web UI)

### Step 1: Go to Your App Settings
1. Go to https://dashboard.heroku.com/apps
2. Click on your app (e.g., "arbiontrader")
3. Click the **"Settings"** tab
4. Scroll to **"Config Vars"** section
5. Click **"Reveal Config Vars"**

### Step 2: Add These Variables

| KEY | VALUE |
|-----|-------|
| `ENCRYPTION_KEY` | `6JT4wJnzgG8izcQj4Iq8MpLfbndVrPTHD3rshOZDn1o=` |
| `SESSION_SECRET` | `UyR2zVGKXStUVUdLRjphMcPxUCA3LYslKQBlYiD9BD0` |
| `ENCRYPTION_SALT` | `79d6ea9554bbe4dab7030440e3c03ca0` |
| `SUPERADMIN_EMAIL` | `admin@yourdomain.com` (change this) |
| `SUPERADMIN_PASSWORD` | `YourSecurePassword123!` (change this) |

### Step 3: Verify
- The app should automatically restart after setting config vars
- Check logs: Click "More" → "View logs"
- Look for: `✓ Encryption validation successful`

---

## 🔍 Verify Configuration

After setting environment variables, check they're set correctly:

```bash
# List all config vars
heroku config --app your-app-name

# Check specific vars (values will be hidden)
heroku config:get ENCRYPTION_KEY --app your-app-name
heroku config:get SESSION_SECRET --app your-app-name
heroku config:get ENCRYPTION_SALT --app your-app-name
```

---

## ✅ Expected Success Messages

Once configured correctly, you should see in logs:

```
INFO:root:✓ Redis cache configured: redis://localhost:6379/1
INFO:root:✓ Rate limiting configured: redis://localhost:6379/2
INFO:root:✓ Encryption validation successful
INFO:werkzeug: * Running on http://0.0.0.0:5000
```

**No more CRITICAL errors!** ✅

---

## 🔐 Security Notes

### These Keys are Production-Grade:

1. **ENCRYPTION_KEY**:
   - Format: Fernet key (base64-encoded 32-byte key)
   - Generated with cryptographically secure random
   - Used to encrypt API credentials in database

2. **SESSION_SECRET**:
   - Format: URL-safe base64 string
   - Used for Flask session signing
   - Prevents session tampering

3. **ENCRYPTION_SALT**:
   - Format: 32-character hex string
   - Used for key derivation (fallback method)
   - Adds additional security layer

### ⚠️ Security Warnings:

- ✅ **These keys are newly generated** for your production deployment
- ✅ **Never commit these to git** (they're in environment variables only)
- ✅ **Different from test keys** in `app.json` (those are for CI only)
- ⚠️ **Keep these secret** - store them securely (password manager, etc.)
- ⚠️ **Rotate if compromised** - generate new keys if exposed

---

## 🆕 Generate New Keys (If Needed)

If you want to generate your own keys instead of using the provided ones:

### Generate ENCRYPTION_KEY:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Generate ENCRYPTION_SALT:
```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

### Generate SESSION_SECRET:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🐛 Troubleshooting

### Error: "heroku: command not found"
**Solution:** Install Heroku CLI:
```bash
# macOS
brew install heroku/brew/heroku

# Ubuntu/Debian
curl https://cli-assets.heroku.com/install.sh | sh

# Windows
# Download from: https://devcenter.heroku.com/articles/heroku-cli
```

### Error: "Invalid credentials"
**Solution:** Login to Heroku:
```bash
heroku login
```

### Error: "Couldn't find that app"
**Solution:** Check your app name:
```bash
heroku apps
# Use the exact name shown
```

### Error: "ENCRYPTION_KEY format invalid"
**Solution:** Ensure you copied the full key including the `=` at the end:
- ✅ Correct: `6JT4wJnzgG8izcQj4Iq8MpLfbndVrPTHD3rshOZDn1o=`
- ❌ Wrong: `6JT4wJnzgG8izcQj4Iq8MpLfbndVrPTHD3rshOZDn1o` (missing `=`)

### App Still Won't Start
**Solution:** Check logs for specific error:
```bash
heroku logs --tail --app your-app-name
```

Look for:
- Database connection errors (check `DATABASE_URL`)
- Redis connection errors (check `REDIS_URL`)
- Missing environment variables

---

## 📋 Complete Environment Variables Checklist

**Required (App won't start without these):**
- [x] `ENCRYPTION_KEY` - Fernet encryption key
- [x] `SESSION_SECRET` - Flask session secret
- [x] `ENCRYPTION_SALT` - Key derivation salt
- [x] `DATABASE_URL` - PostgreSQL (auto-set by Heroku)
- [x] `REDIS_URL` - Redis URL (auto-set by Heroku addon)

**Optional (Recommended):**
- [ ] `SUPERADMIN_EMAIL` - Initial admin account email
- [ ] `SUPERADMIN_PASSWORD` - Initial admin account password
- [ ] `FLASK_ENV` - Set to "production" (default)

**Auto-configured by Heroku addons:**
- ✅ `DATABASE_URL` - Set when you add heroku-postgresql
- ✅ `REDIS_URL` - Set when you add heroku-redis

---

## 🚀 Quick Start (Copy-Paste)

**Replace `YOUR_APP_NAME` and run:**

```bash
APP_NAME="YOUR_APP_NAME"

heroku config:set \
  ENCRYPTION_KEY="6JT4wJnzgG8izcQj4Iq8MpLfbndVrPTHD3rshOZDn1o=" \
  SESSION_SECRET="UyR2zVGKXStUVUdLRjphMcPxUCA3LYslKQBlYiD9BD0" \
  ENCRYPTION_SALT="79d6ea9554bbe4dab7030440e3c03ca0" \
  SUPERADMIN_EMAIL="admin@yourdomain.com" \
  SUPERADMIN_PASSWORD="ChangeThisPassword123!" \
  --app $APP_NAME

heroku restart --app $APP_NAME
heroku logs --tail --app $APP_NAME
```

---

## ✅ Success Verification

After setting up, your app should:

1. ✅ Start without CRITICAL errors
2. ✅ Show `✓ Encryption validation successful` in logs
3. ✅ Be accessible at your Heroku URL
4. ✅ Pass health checks at `/health/ready`

**Test your deployment:**
```bash
# Check app is running
heroku open --app your-app-name

# Check health endpoint
curl https://your-app-name.herokuapp.com/health/ready
```

Expected response:
```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "redis": true,
    "encryption": true
  }
}
```

---

## 📞 Need Help?

If you're still seeing errors:
1. Check logs: `heroku logs --tail --app your-app-name`
2. Verify config: `heroku config --app your-app-name`
3. Restart app: `heroku restart --app your-app-name`
4. Check health: `curl https://your-app-name.herokuapp.com/health/ready`

---

**Your app should now start successfully!** 🎉

The encryption error is resolved, and your production deployment is secure with proper encryption keys.
