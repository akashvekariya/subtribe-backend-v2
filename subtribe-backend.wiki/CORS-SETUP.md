# CORS Configuration

## GitHub Variable Setup

Go to **Settings → Secrets and variables → Actions → Variables** and add:

### Variable: `CORS_ALLOWED_ORIGINS`

**Value** (copy this exactly):
```
^https?://(localhost(:\d+)?|([a-z0-9-]+\.)?thesubtribe\.com)$
```

This regex allows:
- ✅ `http://localhost` (any port)
- ✅ `http://localhost:3000`
- ✅ `http://localhost:5173`
- ✅ `https://thesubtribe.com`
- ✅ `https://app.thesubtribe.com`
- ✅ `https://staging.thesubtribe.com`
- ✅ Any subdomain of thesubtribe.com

---

## Local Development

Your `.env.*` file should have:
```bash
CORS_ALLOWED_ORIGINS=^https?://localhost(:\d+)?$
```

(Already added for you ✅)

---

## How It Works

**Regex Pattern Breakdown**:
```
^https?://                    # http:// or https://
(
  localhost(:\d+)?            # localhost with optional port
  |                           # OR
  ([a-z0-9-]+\.)?             # optional subdomain (app., staging., etc)
  thesubtribe\.com            # main domain
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
- Paste: `^https?://(localhost(:\d+)?|([a-z0-9-]+\.)?thesubtribe\.com)$`
- Test strings:
  - `http://localhost:3000` ✅
  - `https://app.thesubtribe.com` ✅
  - `https://random.com` ❌

---

## Security Note

This regex is **more secure** than `*`:
- Only allows your domains
- Blocks random external sites
- Allows credentials (JWT in headers)

---

**Status**: ✅ Ready to deploy after setting GitHub variable

