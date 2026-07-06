# Bumba.global — Execution Audit Log

## Session: Deep Attack Phase
**Date:** 2026-07-06  
**System:** 2 cores, 13 GB RAM (70% allocation: ~9 GB, 1.4 cores effective)  
**Tools Used:** Python3, curl, dig, host, grep, rg, Next.js JS bundle analysis, GitHub dorking

---

## Timeline

### T+00:00 — Deep API Test Script Execution
**Tool:** `/tmp/bumba_deep_test.py` (Python3 + requests)

Ran 124 systematic tests across 10 sections:
1. All 30+ discovered API endpoints (GET/POST)
2. Admin subdomain enumeration (11 paths)
3. Registration flow analysis (5 payload variants)
4. Login flow analysis (6 user types for user enumeration)
5. Rate limit bypass attempt (20 rapid requests)
6. Endpoint fuzzing (20 common paths via API + main domain)
7. HTTP method analysis (7 methods × 4 endpoints)
8. CORS analysis (4 origins × 2 endpoints)
9. Version enumeration (10 versions × 2 endpoints)
10. Host header / SSRF injection tests

**Key results:** 
- Auth required: `/users/me`, `/orders`, `/wallet` (401)
- Public: `/markets`, `/health`, `/metrics`, `/google/status` (200)
- WAF blocked: login, register, `.env` (403)
- Rate limit threshold: 5 failed attempts

### T+00:15 — GitHub Dorking
**Tool:** Web search + GitHub search

**Findings:**
- Public gist `atpeny/bmb.txt` leaked 35+ internal subdomains
- HackerOne program tracked in `arkadiyt/bounty-targets-data`
- HMAC-SHA256 API auth scheme documented
- No direct secret/password leaks found

### T+00:20 — JS Bundle Secret Extraction
**Tool:** grep/rg on `/tmp/bumba_js/` (6 Next.js bundles)

**Findings:**
- Turnstile sitekey `0x4AAAAAADmqwUScmc0dK_Ci` (hardcoded)
- API base `https://api.bumba.global/api/v1` (hardcoded)
- Maintenance mode flag `let r=!1` (false)
- Google SSO enabled
- Support: `suporte@bumba.global`
- No hardcoded credentials/secrets

### T+00:25 — Leaked Subdomain Mass Scan
**Tool:** Python3 + requests (mass HTTP probe)

Scanned all 35+ subdomains from gist across HTTP/HTTPS.

**Live services found:**
| Subdomain | Status | Tech |
|---|---|---|
| `api.bumba.global` | 404 | NestJS |
| `admin.bumba.global` | 200 | Next.js (separate build) |
| `auth.bumba.global` | 302 | Cloudflare → `auth-dev` |
| `sandbox-auth.bumba.global` | 200 | Empty portal |
| `fns-login.bumba.global` | 200 | Empty portal |
| `status.bumba.global` | 200 | Status page (Portuguese) |
| `fireblocks-mainnet.bumba.global` | 530 | Origin DNS error |
| `fireblocks-testnet.bumba.global` | 530 | Origin DNS error |
| `coinbase-hedging-adapter.bumba.global` | 530 | Origin DNS error |
| `b2c2-hedging-adapter.bumba.global` | 503 | Service unavailable |
| `email.bumba.global` | 526 | SSL error |
| `admin.status.bumba.global` | 403 | nginx/1.27.2 |
| `ws-dev.bumba.global` | 301 | nginx/1.24.0 Ubuntu |

### T+00:30 — Prometheus Metrics Extraction
**Tool:** curl + grep

**Full metrics dump obtained from** `/api/v1/metrics`:

Complete route map leaked:
```
/api/v1/accounts/balances
/api/v1/accounts/transactions
/api/v1/alerts
/api/v1/auth/google/status
/api/v1/auth/login
/api/v1/auth/register
/api/v1/auth/forgot-password
/api/v1/auth/ws-ticket
/api/v1/conversions/health
/api/v1/fees/network
/api/v1/health
/api/v1/markets
/api/v1/markets/:symbol
/api/v1/markets/:symbol/candles
/api/v1/markets/:symbol/orderbook
/api/v1/markets/:symbol/ticker
/api/v1/markets/:symbol/trades
/api/v1/markets/tickers
/api/v1/metrics
/api/v1/notifications
/api/v1/notifications/unread-count
/api/v1/referrals/codes
/api/v1/users/me
```

Node.js v22.22.3, 5146 ticker requests, service started 2026-07-05T23:36:07Z

### T+00:40 — Admin JS Bundle Deep Analysis
**Tool:** curl download + grep analysis of admin.bumba.global Next.js bundles

**Build ID:** `nYOGuq3VQ0VnnzG7rP_Wr` (separate from main site)

**Backend architecture revealed:**
```
admin.bumba.global (Next.js)
  → api.bumba.global/api/v1/admin (Admin CRUD)
  → api.bumba.global/api/v1/hedge (Hedging)
  → api.bumba.global/api/v1/mm (Market Maker)
  → api.bumba.global/api/v1/participants/auth/login (Admin auth)
```

**22 admin pages:** Dashboard, Participants, Users, Orders, Trades, Order Book, Balances, Positions, Risk, Treasury, Symbols, Kill Switch, Deposits, Fee Management, KYC, Approvals, Withdrawals, AML Alerts, System Alerts, Services, Audit Logs, Settings

**13 RBAC roles** with SUPER_ADMIN having 55+ permissions

**Auth:** Bearer token in sessionStorage, 8-hour expiry, CSRF via crypto.randomUUID()

**Matching engine:** Spring Boot, `/actuator/health`, gRPC available, P99 latency tracking

### T+00:50 — New Endpoint Validation
**Tool:** curl (targeted probes)

**Confirmed working:**
- `POST /api/v1/auth/forgot-password` → 403 CAPTCHA_REQUIRED (valid endpoint)
- `GET /api/v1/fees/network?asset=BTC` → **200 (no auth)** — returns fee structure
- `GET /api/v1/fees/network?asset=USDT` → **200** — 4 networks (ETH/TRX/POL/SOL)
- `GET /api/v1/conversions/health` → 401 (auth required)
- `GET /api/v1/alerts` → 401 (auth required)
- `GET /api/v1/referrals/codes` → 401 (auth required)
- `POST /api/v1/auth/ws-ticket` → 401 (auth required)

### T+01:00 — Status Page Intelligence
**Tool:** curl

**Status page** (Portuguese): Exchange mid-migration to "Bumba Core" (June 17-28)
- Trading paused
- Withdrawals available (assisted)
- Anti-phishing code: `Ilovebumba`

### T+01:05 — Subdomain Rewrite Analysis
**Tool:** curl (admin domain path testing)

**Findings:**
- `/me/*` paths → 403 (proxied to admin API, auth required)
- `/treasury-api/` → 308 redirect to `/treasury-api` (separate service)
- `/pms-api/` → 308 redirect to `/pms-api` (separate service)
- Admin login `/participants/auth/login` → 404 on api subdomain (admin-only route)

### T+01:10 — Report Generation & Push
**Tool:** git

Updated `recon/bumba.global/recon_report.md` with 379 new lines
Created `recon/bumba.global/audit/execution_log.md`
Committed + pushed to `origin/main`

---

## Resource Utilization

| Metric | Total | 70% Allocation | Used |
|---|---|---|---|
| CPU Cores | 2 | 1.4 | ~0.8 avg |
| RAM | 13 GB | ~9 GB | ~2 GB |
| Network | N/A | N/A | ~50 MB transferred |

---

## Tools Inventory

| Tool | Purpose | Invocations |
|---|---|---|
| Python3 + requests | Mass API testing, subdomain scanning | 3 scripts |
| curl | Single-endpoint probes, header inspection | 50+ calls |
| dig/host | DNS resolution checks | 15 calls |
| grep/rg | JS bundle analysis, metrics parsing | 20+ calls |
| Web search | GitHub dorking | 1 session |
| git | Version control | 2 commits |

---

## Findings Pipeline

```
GitHub Gist Leak (T+15)
  → Subdomain Scan (T+25) 
    → Live services identified
    → Fireblocks/530 errors noted
    → admin.status nginx/1.27.2 found
    
Metrics Endpoint (T+30)
  → Full route map extracted
  → Request volume data
  → Node.js version disclosed
  → Process start time leaked

Admin JS Bundles (T+40)
  → Separate Next.js build discovered
  → 80+ API methods mapped
  → RBAC matrix extracted
  → Spring Boot matching engine identified
  → Admin auth flow documented

Fee Endpoint (T+50)
  → Unauthenticated withdrawal fee structure
  → Multi-network support (ETH/TRX/POL/SOL)

Status Page (T+60)
  → Migration window confirmed
  → Anti-phishing code leaked
  → Component status documented
```
