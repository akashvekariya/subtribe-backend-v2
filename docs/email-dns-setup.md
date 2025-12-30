# Email DNS Setup Guide (SPF/DKIM/DMARC)

This guide explains how to configure DNS records for email authentication to ensure emails sent from Subtribe (via SendGrid) are properly authenticated and have good deliverability.

## Why Email Authentication Matters

Email authentication prevents:
- Emails landing in spam folders
- Email spoofing/phishing attacks using your domain
- Delivery issues and bounces

## Prerequisites

1. Access to your domain's DNS management (e.g., Cloudflare, Route53, GoDaddy)
2. SendGrid account with domain authentication enabled
3. Domain: `thesubtribe.com` (adjust for your domain)

---

## Step 1: SendGrid Domain Authentication

### 1.1 Access SendGrid Settings

1. Log in to SendGrid dashboard
2. Navigate to **Settings > Sender Authentication**
3. Click **Authenticate Your Domain**
4. Select your DNS host (or "Other" if not listed)
5. Enter your domain: `thesubtribe.com`

### 1.2 Get CNAME Records

SendGrid will provide CNAME records similar to:

```
Host: em1234.thesubtribe.com
Value: u12345678.wl.sendgrid.net

Host: s1._domainkey.thesubtribe.com
Value: s1.domainkey.u12345678.wl.sendgrid.net

Host: s2._domainkey.thesubtribe.com
Value: s2.domainkey.u12345678.wl.sendgrid.net
```

**Note:** The exact values will be provided by SendGrid. Do not use these examples.

---

## Step 2: Add DNS Records

### 2.1 SPF Record (TXT)

Add a TXT record for SPF to authorize SendGrid to send emails on behalf of your domain:

```
Type: TXT
Host: @  (or leave blank, depending on DNS provider)
Value: v=spf1 include:sendgrid.net ~all
TTL: 3600 (or default)
```

**If you have existing SPF record:** Merge the include statement:
```
# Before
v=spf1 include:_spf.google.com ~all

# After (merged)
v=spf1 include:_spf.google.com include:sendgrid.net ~all
```

### 2.2 DKIM Records (CNAME)

Add the CNAME records provided by SendGrid:

```
Type: CNAME
Host: s1._domainkey
Value: s1.domainkey.u12345678.wl.sendgrid.net
TTL: 3600

Type: CNAME
Host: s2._domainkey
Value: s2.domainkey.u12345678.wl.sendgrid.net
TTL: 3600

Type: CNAME
Host: em1234
Value: u12345678.wl.sendgrid.net
TTL: 3600
```

### 2.3 DMARC Record (TXT)

Add a DMARC policy to instruct receiving servers how to handle failed authentication:

```
Type: TXT
Host: _dmarc
Value: v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@thesubtribe.com
TTL: 3600
```

**DMARC Policy Options:**
- `p=none` - Monitor only (start here)
- `p=quarantine` - Send to spam if fails (recommended)
- `p=reject` - Reject emails that fail (strictest)

**Recommended rollout:**
1. Start with `p=none` to monitor
2. After 1-2 weeks, move to `p=quarantine`
3. After confirming no issues, optionally move to `p=reject`

---

## Step 3: Verify Configuration

### 3.1 Verify in SendGrid

1. Return to SendGrid **Sender Authentication**
2. Click **Verify** next to your domain
3. SendGrid will check your DNS records
4. Status should show "Verified"

### 3.2 Test with Command Line

```bash
# Check SPF record
dig TXT thesubtribe.com +short

# Check DKIM records
dig CNAME s1._domainkey.thesubtribe.com +short
dig CNAME s2._domainkey.thesubtribe.com +short

# Check DMARC record
dig TXT _dmarc.thesubtribe.com +short
```

### 3.3 Online Tools

Use these tools to verify your setup:

- **MXToolbox:** https://mxtoolbox.com/SuperTool.aspx
  - Enter domain, check SPF/DKIM/DMARC

- **Mail-Tester:** https://www.mail-tester.com/
  - Send a test email, get spam score

- **DMARC Analyzer:** https://dmarcian.com/dmarc-inspector/
  - Analyze DMARC policy

---

## Step 4: SendGrid Configuration

### 4.1 Environment Variables

Ensure these are set in your deployment:

```bash
# Email Settings
EMAIL_ENABLED=true
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxxxx
SENDGRID_SANDBOX_MODE=false

# Sender Details (must match authenticated domain)
EMAIL_FROM_ADDRESS=no-reply@thesubtribe.com
EMAIL_FROM_NAME=Subtribe
```

### 4.2 Verify From Address

The `EMAIL_FROM_ADDRESS` must use your authenticated domain:
- ✅ `no-reply@thesubtribe.com`
- ✅ `support@thesubtribe.com`
- ❌ `noreply@gmail.com` (not your domain)

---

## Troubleshooting

### Emails Going to Spam

1. Check SPF record is correct
2. Verify DKIM in SendGrid shows "Verified"
3. Send test email to mail-tester.com
4. Review spam score feedback

### DNS Changes Not Propagating

- DNS changes can take 24-48 hours
- Use https://dnschecker.org to check propagation
- Try flushing local DNS cache

### SendGrid Verification Failing

1. Double-check CNAME values (no trailing dots)
2. Ensure TTL is reasonable (3600 recommended)
3. Wait for DNS propagation
4. Contact SendGrid support if issues persist

---

## Summary Checklist

- [ ] SPF record added (`v=spf1 include:sendgrid.net ~all`)
- [ ] DKIM CNAME records added (s1._domainkey, s2._domainkey)
- [ ] Branded link CNAME added (em1234)
- [ ] DMARC record added (`v=DMARC1; p=quarantine; ...`)
- [ ] SendGrid domain verification passed
- [ ] Test email sent successfully
- [ ] Mail-tester score is 9/10 or higher

---

## Additional Resources

- [SendGrid Domain Authentication Guide](https://docs.sendgrid.com/ui/account-and-settings/how-to-set-up-domain-authentication)
- [SPF Record Syntax](https://dmarcian.com/spf-syntax-table/)
- [DMARC Setup Guide](https://dmarc.org/overview/)
