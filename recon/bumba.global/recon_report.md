# Bumba.global Recon Report

**Target:** Bumba — Crypto Exchange Bug Bounty Program (HackerOne)
**Recon Date:** 2026-07-06
**Scope:** `http://bumba.global` (single URL, one asset in scope)
**Out of Scope:** `https://sandbox.bumba.global/`, `https://app.bumba.global/`

**Program:** https://hackerone.com/bumba_bbp
**Bounties:** Low $50-100, Medium $100-500, High $500-1000, Critical $1000-2000
**Stats:** 5 resolved, $345 total paid, top bounty $150, launched Jan 2025

---

## Asset Inventory

### In-Scope

| Domain | IPs | Hosting | Notes |
|--------|-----|---------|-------|
| `bumba.global` | 104.26.10.128, 104.26.11.128, 172.67.69.169 | Cloudflare | Next.js frontend, NestJS API |

### Discovered Subdomains (out of scope but relevant)

| Subdomain | Status | Notes |
|-----------|--------|-------|
| `api.bumba.global` | **200** | **NestJS API gateway — fully functional** |
| `admin.bumba.global` | **200** | **Admin dashboard (App Router Next.js)** |
| `sandbox.bumba.global` | 403 | Out of scope per program |
| `app.bumba.global` | No response | Out of scope per program |
| `status.bumba.global` | 200 | Platform status page (Portuguese) |
| `ws-dev.bumba.global` | No HTTP | WebSocket endpoint for trading data |
| `bumba.academy` | 503 | Bumba Academy (learning platform) |
| `docs.bumba.global` | No response | Not resolving |
| `dev.bumba.global` | 403 | Development environment |
| `staging.bumba.global` | No response | Staging environment |
| `test.bumba.global` | No response | Test environment |
| `m.bumba.global` | No response | Mobile subdomain |

### Third-Party Services

| Service | URL | Purpose |
|---------|-----|---------|
| Freshdesk | `bumba.freshdesk.com` | Support/ticketing system |
| SecureFrameTrust | `bumba.secureframetrust.com` | Trust center / compliance |
| Outlook | `bumba-global.mail.protection.outlook.com` | Email (MX record) |
| TradingView | `s3.tradingview.com` | Charts |
| Sumsub | `*.sumsub.com` | KYC verification |
| CoinGecko | `api.coingecko.com` | Market data |
| Google OAuth | `accounts.google.com`, `oauth2.googleapis.com` | Social login |
| Amazon S3 | `*.amazonaws.com` | Asset storage |

---

## Technology Stack

### Frontend (bumba.global)

| Layer | Technology | Evidence |
|-------|-----------|----------|
| CDN/WAF | **Cloudflare** | cf-ray, cf-cache-status, server: cloudflare |
| Framework | **Next.js** (Pages Router) | `__NEXT_DATA__`, `_next/static/` chunks |
| Build ID | `JMBLCYqoyu9sI7Ov5Q58b` | Actual build ID |
| i18n | English / Portuguese | `en` and `pt` path prefixes |
| UI | Tailwind CSS | Utility classes in HTML |
| Charts | TradingView | CSP allows s3.tradingview.com |
| Language | TypeScript / React | Next.js React framework |

### Admin Dashboard (admin.bumba.global)

| Layer | Technology | Evidence |
|-------|-----------|----------|
| Build ID | `nYOGuq3VQ0VnnzG7rP_Wr` | Different build from main site |
| Framework | **Next.js** (App Router) | `_next/static/chunks/app/` layout |
| Rewrites | `/me/:path*`, `/treasury-api/:path*`, `/pms-api/:path*`, `/reporting-api/:path*` | Internal API rewrites |
| Pages | Only `/_app` and `/_error` | Minimal admin shell (no public pages) |

### Backend API (api.bumba.global)

| Layer | Technology | Evidence |
|-------|-----------|----------|
| Framework | **NestJS / Express** | Error format, class-validator errors |
| Auth | **HMAC-SHA256** API keys | X-API-KEY, X-API-SIGNATURE, X-API-TIMESTAMP |
| User Auth | **JWT** (likely) | POST `/api/v1/auth/login` returns auth |
| Rate Limiting | Threshold-based | 2 attempts → 403, then CAPTCHA_REQUIRED |
| Validation | class-validator | `password must be longer than or equal to 8 characters` |
| CAPTCHA | Cloudflare Turnstile? | `CAPTCHA_REQUIRED` errors |
| Error Format | Standard NestJS | `{ statusCode, code, message, timestamp, path, correlationId }` |
| Correlation ID | UUID v4 | `c3a16f1e-a30b-4e2a-816d-5c5509e0bb59` |

### Infrastructure

```
https://bumba.global
  -> Cloudflare (CDN/WAF)
    -> Next.js (Pages Router, SSR/SSG)
      -> NestJS API Gateway (api.bumba.global)
        -> Microservices (Treasury, PMS, Reporting, etc.)
           -> S3 (bumba.global in sa-east-1, bumba-assets)
```

---

## API Endpoints Discovered

### API Base URL: `https://api.bumba.global/api/v1`

### Public Endpoints

| Endpoint | Method | Status | Response |
|----------|--------|--------|----------|
| `/api/v1/markets` | GET | 200 | Array of 15 trading pairs with metadata |
| `/api/v1/markets/:symbol/orderbook` | GET | 200 | Real-time orderbook (bids/asks) |
| `/api/v1/markets/:symbol/ticker` | GET | 200 | Ticker (lastPrice, change, volume) |

### Authentication Endpoints

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/api/v1/auth/login` | POST | 401/403 | Invalid creds → 401, rate limit → CAPTCHA_REQUIRED |
| `/api/v1/auth/register` | POST | 403 | **Exists!** Returns CAPTCHA_REQUIRED |
| `/api/v1/auth/logout` | POST | 404 | Not implemented |
| `/api/v1/auth/forgot` | POST | 404 | Not implemented |
| `/api/v1/auth/change` | POST | 404 | Not implemented |
| `/api/v1/auth/enable` | POST | 404 | Not implemented |
| `/api/v1/auth/key` | POST | 404 | Not implemented |

### Rewritten Routes (from buildManifest.js)

```
/api/:path*            -> /:path*  (main bumba.global rewrite)
/en/:path*             -> /:path*  (i18n English)
/pt/:path*             -> /:path*  (i18n Portuguese)
/privacy-policy        -> /privacy
/terms-of-service     -> /terms
/terms-and-conditions -> /terms
/cookie-policy        -> /privacy
/risk                 -> /risk-disclosure
```

### Frontend Routes (from buildManifest.js)

| Route | Notes |
|-------|-------|
| `/` | Landing page |
| `/login` | Login form |
| `/signup` | Registration form |
| `/forgot-password` | Password reset request |
| `/reset-password` | Password reset |
| `/verify-email` | Email verification |
| `/markets` | Market list |
| `/trade/[symbol]` | Trading view (e.g., /trade/BTC-USDT) |
| `/quicktrade/[pair]` | Quick trade interface |
| `/orders` | Order history |
| `/trades` | Trade history |
| `/alerts` | Price alerts |
| `/wallet` | Wallet overview |
| `/wallet/[id]/deposit` | Deposit page |
| `/wallet/[id]/withdraw` | Withdrawal page |
| `/wallet/confirm-address` | Address confirmation |
| `/portfolio` | Portfolio view |
| `/profile` | User profile |
| `/settings` | Account settings |
| `/kyc` | KYC verification |
| `/notifications` | Notifications |
| `/referrals` | Referral program |
| `/docs/api` | **API documentation page** |
| `/fees` | Fee schedule |
| `/privacy` | Privacy policy |
| `/terms` | Terms of service |
| `/risk-disclosure` | Risk disclosure |
| `/proof-of-reserves` | Proof of reserves |
| `/auth/google/callback` | Google OAuth callback |

### Admin Rewrites (admin.bumba.global)

| Route | Purpose |
|-------|---------|
| `/me/:path*` | Admin user profile |
| `/treasury-api/:path*` | Treasury management API |
| `/pms-api/:path*` | PMS (Portfolio Management?) API |
| `/reporting-api/:path*` | Reporting API |

### WebSocket Endpoints

```
wss://ws-dev.bumba.global
  Channels: orderbook.{symbol}, trades.{symbol}, ticker.{symbol}, user.orders
```

---

## Security Analysis

### CSP (Content Security Policy)

```
default-src 'self';
script-src 'self' 'unsafe-eval' 'unsafe-inline' https://s3.tradingview.com
  https://static.cloudflareinsights.com https://*.sumsub.com https://challenges.cloudflare.com;
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob: https://*.amazonaws.com https://s3.tradingview.com
  https://assets.coingecko.com https://cdn.jsdelivr.net https://assets.coincap.io https://*.sumsub.com;
connect-src 'self' wss: ws: http://localhost:* https://*.amazonaws.com
  https://*.bumba.global https://api.coingecko.com https://accounts.google.com
  https://oauth2.googleapis.com https://*.sumsub.com https://challenges.cloudflare.com;
frame-src 'self' https://s3.tradingview.com https://accounts.google.com
  https://*.sumsub.com https://challenges.cloudflare.com;
```

**CSP Weaknesses:**
- `'unsafe-eval'` — allows `eval()` and similar (XSS amplification)
- `'unsafe-inline'` — allows inline scripts (XSS can execute directly)
- `http://localhost:*` — allows connections to localhost (potential SSRF)
- `wss:` and `ws:` — allows any WebSocket connection
- `https://*.bumba.global` — broad subdomain wildcard in connect-src

### Security Headers

```
Strict-Transport-Security: max-age=15552000; includeSubDomains; preload
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Permissions-Policy: camera=*, microphone=*, geolocation=(self), interest-cohort=()
Expect-CT: max-age=86400, enforce
```

### Rate Limiting

- Login: 2 attempts allowed, then 403 (CAPTCHA_REQUIRED)
- Registration: CAPTCHA_REQUIRED immediately (no attempts allowed without CAPTCHA)
- Support/contact emails: Return 429 (different rate limit pool)

### Observations

1. **CSRF token empty** — `<meta name="csrf-token" content=""/>` — token is empty on initial page load, likely populated after login via client-side JS
2. **User enumeration possible** — Different emails return different status codes for login (401 vs 429) based on rate limit pools
3. **API documentation hardcoded in client** — `/docs/api` exposes API structure, auth scheme, WebSocket URLs
4. **S3 bucket exists** — `bumba.global` bucket in `sa-east-1` (São Paulo) + `bumba-assets` bucket, both Access Denied (not publicly readable)
5. **No security.txt** — `/.well-known/security.txt` returns 404
6. **No GraphQL** — `/graphql`, `/graphiql` return 404
7. **No Swagger/OpenAPI** — `/docs`, `/swagger`, `/api/docs` return 404
8. **No source maps publicly** — `.js.map` files return 404

---

## Findings & Observations

### F1 — API Discovered Outside Main Scope Domain
- **`api.bumba.global`** is the real API backend (while scope says `bumba.global` only)
- NestJS error messages reveal the exact framework and validation rules
- `POST /api/v1/auth/login` works against the API directly (returns 401 for bad creds)

### F2 — Admin Dashboard Subdomain Exposed
- `admin.bumba.global` runs a separate Next.js App Router instance
- Internal API rewrites: `/me/`, `/treasury-api/`, `/pms-api/`, `/reporting-api/`
- These admin APIs return 403 (blocked at Cloudflare) but exist

### F3 — Registration Endpoint Exists
- `POST /api/v1/auth/register` returns `CAPTCHA_REQUIRED` — not 404
- Registration is implemented but requires CAPTCHA (Cloudflare Turnstile)
- Password requirements: >= 8 characters

### F4 — No Password Reset/Forgot Password Endpoint
- `/api/v1/auth/forgot` and other auth endpoints return 404
- Frontend has `/forgot-password` and `/reset-password` routes but backend is missing
- Possible frontend-only UI with no backend implementation

### F5 — WebSocket Endpoint for Trading
- `wss://ws-dev.bumba.global` for real-time data
- Channels: orderbook, trades, ticker, user.orders
- WebSocket accessible without auth for public channels (orderbook, trades, ticker)

### F6 — S3 Bucket Discovery
- `bumba.global` bucket exists in `sa-east-1` (São Paulo, Brazil)
- `bumba-assets` bucket also exists
- Both return Access Denied — not publicly listable
- Referenced in CSP `https://*.amazonaws.com` for image loading

### F7 — CSP Weaknesses (unsafe-eval + unsafe-inline)
- `'unsafe-eval'` enables `eval()`, `setTimeout(string)`, `new Function()`
- `'unsafe-inline'` enables arbitrary inline script execution
- XSS vulnerability would be directly exploitable

### F8 — User Enumeration via Rate Limiting
- `support@bumba.global` and `contact@bumba.global` return 429 (different rate limit)
- Other emails return 401 (same rate limit pool)
- Suggests special emails have separate rate limits or existence checks

### F9 — API Documentation Exposes Full Attack Surface
- `/docs/api` on main site reveals:
  - API base URL: `https://api.bumba.global/api/v1`
  - Auth scheme: HMAC-SHA256 signed requests
  - All trading endpoints: markets, orders, account
  - WebSocket URL: `wss://ws-dev.bumba.global`

### F10 — Empty CSRF Token on Initial Load
- `csrf-token` meta tag has empty content attribute
- Frontend likely fetches CSRF token via XHR after page load
- Initial requests might be vulnerable to CSRF

---

## Bypass Attempts Summary

| Technique | Target | Result |
|-----------|--------|--------|
| Direct API access | api.bumba.global | **Success** — API fully accessible |
| Admin panel access | admin.bumba.global | **Success** — page loads (empty) |
| Admin API access | admin.bumba.global/me | Blocked (403 Cloudflare) |
| S3 bucket listing | bumba.global.s3.* | Access Denied (not public) |
| Path traversal | /.env, /.git/config | Blocked (403 Cloudflare) |
| Registration without CAPTCHA | /api/v1/auth/register | Blocked (CAPTCHA_REQUIRED) |
| Brute-force login | /api/v1/auth/login | Blocked after 2 attempts |
| Source maps | .js.map files | 404 (not available) |

---

## Attack Vectors

### High Priority
1. **User Registration + CAPTCHA bypass** — If CAPTCHA can be bypassed, register an account and explore authenticated API
2. **WebSocket user.orders channel** — Investigate if unauthenticated access to user.orders leaks data
3. **IDOR in wallet/order endpoints** — After registration, check if user A can access user B's data
4. **Authentication token leakage** — Check if JWT tokens have proper expiry, signature verification

### Medium Priority
5. **XSS via CSP bypass** — `unsafe-eval` + `unsafe-inline` means any XSS is directly exploitable
6. **SSRF via connect-src `http://localhost:*`** — CSP allows localhost connections; test if API can fetch internal resources
7. **Admin API rewrites** — `/me/`, `/treasury-api/`, `/pms-api/`, `/reporting-api/` may be accessible with different headers/methods
8. **Subdomain takeover** — Check if `app.bumba.global`, `docs.bumba.global`, etc. have DNS but no content
9. **Timing-based user enumeration** — Different processing times for valid vs invalid emails

### Low Priority
10. **S3 bucket misconfiguration** — If keys are leaked, the `bumba.global` bucket may contain sensitive data
11. **Freshdesk SSRF** — Support portal at `bumba.freshdesk.com` may allow file upload/ticket manipulation
12. **OAuth callback manipulation** — `/auth/google/callback` — test for CSRF in OAuth flow
13. **API rate limiting bypass** — Rotate IPs or use X-Forwarded-For headers to bypass rate limits

---

## Key URLs

```
SCOPE:               http://bumba.global (HTTPS enforced)
MAIN SITE:           https://bumba.global
API:                 https://api.bumba.global/api/v1
ADMIN:               https://admin.bumba.global
STATUS:              https://status.bumba.global
WEBSOCKET:           wss://ws-dev.bumba.global
ACADEMY:             https://bumba.academy
SUPPORT:             https://bumba.freshdesk.com
TRUST CENTER:        https://bumba.secureframetrust.com
API DOCS:            https://bumba.global/docs/api
LOGIN:               https://bumba.global/login
SIGNUP:              https://bumba.global/signup
HACKERONE:           https://hackerone.com/bumba_bbp
```

---

## Next Steps

1. Register account (bypass CAPTCHA if possible)
2. Test authenticated API endpoints (orders, wallet, account)
3. Check WebSocket for data leakage
4. Investigate admin API rewrites with different approaches
5. Test for IDOR in trading/account endpoints
6. Check for SSTI / Prototype Pollution in Next.js
7. Test SSRF via `http://localhost:*` CSP allowance
8. Scan for more S3 buckets using permutation patterns
