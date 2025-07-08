# Heroku Custom Domain Setup for arbion.ai

## Prerequisites
- Heroku app deployed and running
- Domain `arbion.ai` registered and accessible
- Heroku CLI installed

## Step 1: Add Custom Domain to Heroku App

```bash
# Add the custom domain to your Heroku app
heroku domains:add arbion.ai --app your-app-name
heroku domains:add www.arbion.ai --app your-app-name

# Get the DNS target from Heroku
heroku domains --app your-app-name
```

## Step 2: Configure DNS Records

After adding the domain, Heroku will provide a DNS target. You'll need to add these records to your domain's DNS settings:

### For Root Domain (arbion.ai):
```
Type: ALIAS or ANAME
Name: @
Target: [DNS target from Heroku, e.g., sharp-rain-123.herokudns.com]
```

### For WWW Subdomain (www.arbion.ai):
```
Type: CNAME
Name: www
Target: [DNS target from Heroku, e.g., sharp-rain-123.herokudns.com]
```

## Step 3: SSL Certificate Configuration

Heroku automatically provisions SSL certificates for custom domains:

```bash
# Check SSL certificate status
heroku certs --app your-app-name

# If needed, you can force SSL certificate renewal
heroku certs:auto:refresh --app your-app-name
```

## Step 4: Update Application Configuration

Ensure your Flask application is configured to handle the custom domain properly.

## Step 5: Test Configuration

```bash
# Test domain resolution
nslookup arbion.ai

# Test HTTPS access
curl -I https://arbion.ai
```

## DNS Propagation
- DNS changes can take up to 24-48 hours to propagate globally
- Use tools like `dig` or online DNS checkers to verify propagation

## Common Issues and Solutions

### Issue: DNS Not Resolving
- Verify DNS records are correctly configured
- Check DNS propagation status
- Ensure ALIAS/ANAME record is used for root domain

### Issue: SSL Certificate Problems
- Wait for automatic SSL provisioning (can take up to 1 hour)
- Check that domain is properly validated
- Verify DNS records are correct

### Issue: Redirect Loops
- Ensure Flask app is configured for HTTPS
- Check proxy settings in application code