# CORS Configuration

## Strategy: Environment-Specific CORS

### **Production** (GitHub Actions)
**Only allows thesubtribe.com domains** - No localhost, no IPs

### **Local Development**
**Allows localhost + 192.168.x.x IPs** - For testing from phones/tablets on local network

---

## 🚀 GitHub Environment Setup (Development)

Go to **Settings → Environments → Development** and add these secrets/variables:

### Environment: `Development`

#### Secrets (encrypted):
- `DATABASE_URL` - Dev Supabase database URL
- `JWT_SECRET_KEY` - Dev JWT secret
- `SUPABASE_URL` - Dev Supabase project URL
- `SUPABASE_ANON_KEY` - Dev Supabase anon key
- `SUPABASE_SERVICE_KEY` - Dev Supabase service key
- `SUPABASE_JWT_SECRET` - Dev Supabase JWT secret
- `GCS_BUCKET_NAME` - Dev GCS bucket name (e.g., `subtribe-ats-resumes-dev`)

#### Variable: `CORS_ALLOWED_ORIGINS`

**Value** (copy this exactly):
```
^https?://(localhost(:\d+)?|192\.168\.\d{1,3}\.\d{1,3}(:\d+)?|([a-z0-9-]+\.)?thesubtribe\.com)$
```

This regex allows:
- ✅ `http://localhost:3000` (local testing)
- ✅ `http://192.168.1.100:3000` (testing from devices on network)
- ✅ `https://thesubtribe.com` (production frontend)
- ✅ `https://app.thesubtribe.com` (production app)
- ✅ Any subdomain of thesubtribe.com

---

## 💻 Local Development

Your `.env.development` file should have:
```bash
CORS_ALLOWED_ORIGINS=^https?://(localhost(:\d+)?|192\.168\.\d{1,3}\.\d{1,3}(:\d+)?)$
```

This regex allows:
- ✅ `http://localhost` (any port)
- ✅ `http://localhost:3000`
- ✅ `http://192.168.1.100:3000` (any 192.168.x.x IP with optional port)
- ✅ `http://192.168.0.50:5173`
- ❌ `https://thesubtribe.com` (use production for that)

**Default value updated in `app/config.py` ✅**

---

## How It Works

### Production Pattern
```
^https?://([a-z0-9-]+\.)?thesubtribe\.com$
```
**Breakdown**:
```
^https?://                    # http:// or https://
([a-z0-9-]+\.)?              # optional subdomain (app., staging., etc)
thesubtribe\.com             # main domain only
$
```

### Development Pattern
```
^https?://(localhost(:\d+)?|192\.168\.\d{1,3}\.\d{1,3}(:\d+)?)$
```
**Breakdown**:
```
^https?://                    # http:// or https://
(
  localhost(:\d+)?            # localhost with optional port
  |                           # OR
  192\.168\.\d{1,3}\.\d{1,3}  # 192.168.x.x IP addresses
  (:\d+)?                     # optional port
)$
```

**CORS Settings**:
- `allow_origin_regex` - Pattern matching
- `allow_credentials=True` - Allows cookies/auth headers
- `allow_methods=["*"]` - All HTTP methods
- `allow_headers=["*"]` - All headers

---

## Testing

After deployment, test from:

1. **Frontend (localhost:3000)**:
   ```javascript
   fetch('https://your-api.run.app/auth/login', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({ email: '...', password: '...' })
   })
   ```

2. **Production (thesubtribe.com)**:
   - Should work automatically
   - Check browser console for CORS errors

---

## Troubleshooting

**If CORS still fails**:

1. Check GitHub variable is set correctly
2. Redeploy to update environment variables
3. Check browser console for actual origin value
4. Verify regex matches your origin

**Test regex online**:
- Go to https://regex101.com

**Production pattern**: `^https?://([a-z0-9-]+\.)?thesubtribe\.com$`
- Test strings:
  - `https://thesubtribe.com` ✅
  - `https://app.thesubtribe.com` ✅
  - `http://localhost:3000` ❌
  - `https://random.com` ❌

**Development pattern**: `^https?://(localhost(:\d+)?|192\.168\.\d{1,3}\.\d{1,3}(:\d+)?)$`
- Test strings:
  - `http://localhost:3000` ✅
  - `http://192.168.1.100:3000` ✅
  - `https://thesubtribe.com` ❌

---

## Security Note

This approach is **more secure** than using `*`:
- **Production**: Only allows your domains (no localhost/IPs leak)
- **Development**: Locked to local network (192.168.x.x) + localhost only
- Blocks random external sites
- Allows credentials (JWT in headers)
- Environment-specific: Production can't be accessed from dev tools

---

**Status**: ✅ Ready to deploy after setting GitHub variable

