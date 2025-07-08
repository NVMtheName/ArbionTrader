# DNS Configuration for arbion.ai

## Current Heroku Configuration
- **DNS Target**: `fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com`
- **SSL Certificate**: `parasaurolophus-89788`

## DNS Records to Configure

### Root Domain (arbion.ai)
```
Type: ALIAS or ANAME
Name: @
Value: fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com
TTL: 300 (or your registrar's default)
```

### WWW Subdomain (www.arbion.ai)
```
Type: CNAME
Name: www
Value: hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com
TTL: 300 (or your registrar's default)
```

## Quick Setup Commands

```bash
# Verify domains are added to Heroku
heroku domains --app your-app-name

# Check SSL certificate status
heroku certs --app your-app-name

# Test DNS resolution after configuration
nslookup arbion.ai
nslookup www.arbion.ai

# Test HTTPS access
curl -I https://arbion.ai
curl -I https://www.arbion.ai
```

## Common Domain Registrars

### Cloudflare
1. Go to DNS settings for arbion.ai
2. Add CNAME record: `@` → `fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com`
3. Add CNAME record: `www` → `hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com`

### Namecheap
1. Go to Advanced DNS settings
2. Add ALIAS record: `@` → `fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com`
3. Add CNAME record: `www` → `hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com`

### GoDaddy
1. Go to DNS Management
2. Add CNAME record: `@` → `fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com`
3. Add CNAME record: `www` → `hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com`

## Status Check
After configuring DNS records, you can check the status:

```bash
# Check if DNS has propagated
dig arbion.ai
dig www.arbion.ai

# Check SSL certificate
openssl s_client -connect arbion.ai:443 -servername arbion.ai
```

## Expected Timeline
- DNS propagation: 15 minutes to 24 hours
- SSL certificate activation: Automatic (already provisioned)
- Full HTTPS availability: After DNS propagation

## Next Steps
1. Configure the DNS records above at your domain registrar
2. Wait for DNS propagation
3. Test access to https://arbion.ai
4. Verify SSL certificate is working