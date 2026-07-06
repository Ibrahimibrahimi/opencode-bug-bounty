# ALSCO / Secure Gateway Recon Report

**Target:** ALSCO — Secure Gateway® Bug Bounty Program (HackerOne)
**Recon Date:** 2026-07-05 to 2026-07-06
**Scope:** SECURE GATEWAY®, WEB SECURE GATEWAY™, Cloud SECURE GATEWAY™, E-Mail SECURE GATEWAY™, DataBase SECURE GATEWAY™

---

## Asset Inventory

### Primary Domains

| Domain | Type | IP / Hosting | Notes |
|--------|------|-------------|-------|
| `alsco.net` | Marketing site | Cloudflare (104.21.64.16, 172.67.174.27) | TXT: h1-domain-verification, SPF, Google/AbuseIPDB/FB verification |
| `www.alsco.net` | Marketing site | Cloudflare | Same as alsco.net |
| `alsco.com` | Landing page | Netlify | Redirects to https://alsco.com/ |
| `www.alsco.com` | Landing page | Netlify (13.215.239.219, 52.74.6.109) | Redirects to https://alsco.com/ |
| `api.alsco.com` | API | IIS/10.0 + ASP.NET (65.121.181.75) | Origin server, CenturyLink, Murray UT. Cert: *.alsco.com (Amazon Trust) |
| `portal.alscotoday.com` | **Secure Gateway App** | Cloudflare -> nginx -> IIS/10.0 | Main in-scope asset. JS challenge WAF. |
| `smtp.alsco.com` | SMTP Server | 65.121.181.71 | No HTTP response. Likely E-Mail Secure Gateway. |

### Discovery: sandbox.securegateway.com (key asset for testing)

| Domain | Type | IP / Hosting | Notes |
|--------|------|-------------|-------|
| `sandbox.securegateway.com` | **Secure Gateway Sandbox** | 188.34.187.32 (Hetzner, AS24940) | **NOT behind Cloudflare** — direct nginx 1.26.1, SG WAF |
| `msg.securegateway.com` | SG Block Page | 188.34.187.32 (behind Cloudflare) | Same Hetzner server, Cloudflare fronted |
| `securegateway.com` | Product domain | 188.34.187.32 (behind Cloudflare) | Same Hetzner server |

### Sandbox Infrastructure

```
sandbox.securegateway.com
  -> Direct connection (NO Cloudflare)
    -> nginx 1.26.1 (ZeroSSL *.securegateway.com cert)
      -> Secure Gateway WAF (ModSecurity CRS + custom rules)
        -> PHP application (nginx + PHP-FPM?)

Static assets (favicon.ico, style.css) last modified: Sep 2021
```

### Related Domains (Not ALSCO-owned)

| Domain | Status | Notes |
|--------|--------|-------|
| `alsco.cloud` | Cloudflare 403 | Behind Cloudflare, same as main site |
| `alsco.co` | Cloudflare 403 | Behind Cloudflare |
| `alsco.org` | For sale (5.8.93.86) | Domain squatter, openresty/1.31.1.1 |
| `alsco.us` | No response | Unreachable |
| `firewallgateway.com` | Redirect page | Excluded by program — "just a redirect page" |

### DNS Records

**alsco.net** (Cloudflare):
```
A:    104.21.64.16, 172.67.174.27
MX:   route1/2/3.mx.cloudflare.net
NS:   casey.ns.cloudflare.com, sarah.ns.cloudflare.com
TXT:  h1-domain-verification=MbFYxRbo..., SPF, google-site-verification, etc.
```

**Origin (65.121.181.75) — CenturyLink (AS209), Murray UT:**
```
Server: Microsoft-IIS/10.0
X-Powered-By: ASP.NET
Certificate: *.alsco.com (Amazon Trust Services)
```

**sandbox.securegateway.com (188.34.187.32) — Hetzner (AS24940), Germany:**
```
Server: nginx/1.26.1
Certificate: *.securegateway.com (ZeroSSL RSA Domain Secure Site CA)
Shodan: tagged "eol-product" with CVE-2025-23419
```

---

## Technology Stack

### Secure Gateway — Main Portal (portal.alscotoday.com)

| Layer | Technology | Evidence |
|-------|-----------|----------|
| CDN/WAF | **Cloudflare** | cf-ray, cf-cache-status, __cfduid cookies, nel/report-to headers |
| Reverse Proxy | **nginx** | `Server: nginx` header on 302 responses |
| Web Server | **IIS 10.0** | `Server: Microsoft-IIS/10.0` on origin direct access |
| Backend Framework | **ASP.NET** | `X-Powered-By: ASP.NET` on origin |
| SG Engine | **Secure Gateway** | `X-Server-Powered-By: Secure Gateway`, `X-Secure_Gateway_ID` headers |
| Base URL | `/msg/` | All app resources served from this path |
| WAF Rules | **ModSecurity CRS + Custom** | G.S.13, G.S.920180 (CRS), G.S.920600 (CRS) |

### Secure Gateway — Sandbox (sandbox.securegateway.com)

| Layer | Technology | Evidence |
|-------|-----------|----------|
| CDN | **None** — direct origin access | TLS handshake succeeds on hostname, fails on IP (SNI-based) |
| Web Server | **nginx 1.26.1** | `Server: nginx/1.26.1` header |
| SG Engine | **Secure Gateway** | Same X-Server-Powered-By, X-Secure_Gateway_ID headers |
| WAF Rules | **ModSecurity CRS + Custom** | Same G.S.13, G.S.920180 rules |
| Backend | **PHP** | `/auth/index.php`, `/auth/check.php`, `/setup.php`, `/install.php` |
| TLS | **SNI required** | IP:443 returns TLS alert; hostname works with ZeroSSL cert |

### Security Headers (Observed on sandbox)

```
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Referrer-Policy: strict-origin-when-cross-origin
X-XSS-Protection: 1; mode=block
X-Permitted-Cross-Domain-Policies: master-only
Expect-CT: enforce; max-age=3600
Feature-Policy: accelerometer 'none'; autoplay 'none'; ... (extensive deny list)
Cache-Control: no-cache
```

---

## WAF Behavior Analysis

### Error Code Matrix — Main Portal (portal.alscotoday.com via Cloudflare)

| Method | Path | Status | err | Rule | Notes |
|--------|------|--------|-----|------|-------|
| GET | `/msg/` | 200 | — | — | Block page (Cloudflare JS challenge) |
| GET | `/*` | 200/302 | 22 | G.S.13 | General GET block |
| HEAD | `/*` | 403 | — | — | Blocked at edge |
| POST | `/*` | 302 | 23 | G.S.920180 | Content-Type policy (ModSecurity CRS) |
| PUT/PATCH/DELETE | `/*` | 403 | — | — | Blocked at edge |
| OPTIONS | `/*` | 403 | — | — | Blocked at edge |
| TRACE | `/*` | 405 | — | — | Reached backend (IIS) |
| POST + `application/x-www-form-urlencoded` | `/*` | 302 | 23 | G.S.920180 | Same as no CT |
| POST + `multipart/form-data` | `/*` | 302 | 23 | G.S.920180 | Same |

### Error Code Matrix — Sandbox (sandbox.securegateway.com, direct, NO Cloudflare)

| Method | Path | Status | err | Rule | Notes |
|--------|------|--------|-----|------|-------|
| GET | `/msg/` | 200 | — | — | Block page with timer |
| GET | `/up/` | 406 | — | — | ModSecurity "Not Acceptable" |
| GET | `/` | 406 | — | — | ModSecurity "Not Acceptable" |
| GET | `/auth/index.php` | 200 | — | — | **Phone verification form** |
| GET | `/admin/` | 307 | — | — | Redirect to `/auth/index.php?url=/admin/` |
| POST | `/` | 302 | 23 | G.S.920180 | POST blocked (same as main portal) |
| PUT/PATCH/DELETE | `/` | 302 | — | — | Redirect to sg_err.php |
| OPTIONS | `/` | 403 | — | — | Block page returned |
| GET | `/setup.php` | 403 | — | — | **Exists! WAF blocked** |
| GET | `/install.php` | 403 | — | — | **Exists! WAF blocked** |
| GET | `/auth/register.php` | 429 | — | — | Rate limited |
| GET | `/auth/config.php` | 503 | — | — | Rate limited / blocked |
| GET | `/config.php` | 503 | — | — | Rate limited / blocked |
| GET | `/phpinfo.php` | 503 | — | — | Rate limited / blocked |
| GET | `/%2f` | 404 | 33 | — | Unique error — "File Or Directory Not Found" |

### Rule IDs Identified

| Rule | ModSecurity CRS Match | Description |
|------|----------------------|-------------|
| G.S.13 | — (custom) | General GET block |
| G.S.920180 | 920180 | Content-Type request header inspection |
| G.S.920600 | 920600 | Request body limit / POST parameter limit |

### Error Codes

| err | Meaning | Observed |
|-----|---------|----------|
| 22 | Blocked — rule G.S.13 | GET requests to protected paths |
| 23 | Blocked — rule G.S.920180 | POST requests (Content-Type policy) |
| 33 | File or directory not found | `/%2f` path |
| — | "Not Acceptable" | ModSecurity `tx.allowed_methods` or Accept header check |

### Block Page Annotations
- `[AS] (F5)` — "Automated Security"? F5 Networks BIG-IP?
- `[B] (F3)` — Different block mode (observed in Wayback Dec 2023)
- Transaction ID format: `8e07297d3adaa990b3b2a19991fb2782` (MD5 hash) — sandbox uses different format: `2504464489862982` (numeric)
- SG_ID format: `178329694362.361644` (epoch timestamp + counter)
- Timer: 30 seconds (main portal) / 60 seconds (sandbox) / 90 seconds (check.php code)

### Sandbox-Specific Headers
```
X-Secure_Gateway_ID: c301a86cb5fc83cb8814a3233fd55d7f  (MD5 hash per request)
X-Server-Powered-By: Secure Gateway (overwrites nginx Server header)
Server: nginx (initial) -> "Secure Gateway" (after WAF processing)
```

---

## Discovered Application Endpoints

### Authentication Flow

**Path:** `/auth/index.php`
**Status:** 200 (no WAF block)
**Content:** Phone Number Verification form
```
<form action="check.php" method="post" class="newsletterform">
  <input type="hidden" name="csrf_token_phone" value="<64-char hex>">
  <!-- Example: 9647711223344 -->  (Iraqi country code +964)
  <input type="text" name="phonenumber" onkeypress="return (event.charCode !=8 && event.charCode ==0 || (event.charCode >= 48 && event.charCode <= 57))">
  <input type="submit" name="SecureGateway_Button" value="Submit">
</form>
```

**Path:** `/auth/check.php`
**Status:** 200 (POST, if CSRF valid)
**Content:** Security code verification (90-second timer)
```
Input fields: alsco_input (security code), alsco_messageonboard (status)
Links to: index.php?action=false (expired/try again)
```

### Identified PHP Endpoints

| Path | HTTP Status | Notes |
|------|-------------|-------|
| `/auth/index.php` | 200 | Phone verification form |
| `/auth/check.php` | 200 (POST) | Security code verification |
| `/auth/register.php` | 429 | Rate limited — registration exists |
| `/auth/config.php` | 503 | Blocked — config file exists |
| `/admin/config.php` | 503 | Blocked — admin config |
| `/config.php` | 503 | Blocked — root config |
| `/phpinfo.php` | 503 | Blocked — PHP info |
| `/setup.php` | 403 | Blocked — setup script exists |
| `/install.php` | 403 | Blocked — install script exists |
| `/auth/login.php` | 404 | Does not exist |
| `/auth/admin.php` | 404 | Does not exist |
| `/auth/dashboard.php` | 404 | Does not exist |
| `/auth/db.php` | 404 | Does not exist |
| `/auth/logout.php` | 404 | Does not exist |
| `/auth/forgot.php` | 307 | Redirects to auth |
| `/auth/reset.php` | 307 | Redirects to auth |
| `/auth/profile.php` | 307 | Redirects to auth |
| `/auth/verify.php` | 307 | Redirects to auth |
| `/auth/user.php` | 307 | Redirects to auth |

### Redirect Chains

```
/admin/  -> 307 -> http://sandbox.securegateway.com/auth/index.php?url=/admin/
/admin   -> 307 -> /auth/index.php?url=/admin
/config  -> 307 -> /auth/index.php?url=/config
```

Note: The `/admin/` redirect goes to **HTTP** (not HTTPS), which is a potential security issue.

### Static Files (Publicly Accessible, Sep 2021)

| File | Size | Last Modified |
|------|------|---------------|
| `/msg/favicon.ico` | 1856 bytes | 2021-09-09 |
| `/msg/style.css` | 2106 bytes | 2021-09-09 |
| `/msg/securegateway.gif` | (referenced in block pages) | — |

---

## Path Behavior Discovery (sandbox.securegateway.com)

| Path | HTTP Status | WAF Behavior |
|------|-------------|-------------|
| `/msg/` | 200 | Block page with timer |
| `/up/` | 406 | ModSecurity "Not Acceptable" |
| `/` | 406 | ModSecurity "Not Acceptable" |
| `/api/` | 406 | ModSecurity "Not Acceptable" |
| `/login/` | 406 | ModSecurity "Not Acceptable" |
| `/register/` | 406 | ModSecurity "Not Acceptable" |
| `/upload/` | 406 | ModSecurity "Not Acceptable" |
| `/file/` | 406 | ModSecurity "Not Acceptable" |
| `/download/` | 406 | ModSecurity "Not Acceptable" |
| `/status/` | 406 | ModSecurity "Not Acceptable" |
| `/test/` | 406 | ModSecurity "Not Acceptable" |
| `/console/` | 406 | ModSecurity "Not Acceptable" |
| `/robots.txt` | 301 | Redirects to HTTPS |
| `/favicon.ico` | 200 | Server as `/msg/favicon.ico` |
| `/debug/` | 403 | WAF block page |
| `/setup.php` | 403 | WAF block page |
| `/install.php` | 403 | WAF block page |
| `/shell/` | 302 | Redirect to sg_err.php |
| `/cmd/` | 302 | Redirect to sg_err.php |
| `/exec/` | 302 | Redirect to sg_err.php |
| `/%2f` | 404 | err=33 "File Or Directory Not Found" |
| `/%252f` | 406 | ModSecurity "Not Acceptable" |
| `/./msg/` | 200 | WAF bypass but returns block page |
| `..;/..;/etc/passwd` | 503 | Path traversal blocked |
| `%00` (null byte) | 000 | Connection error |

---

## Findings & Observations

### F1 — Server Header Leaks "S.G WebServer" (Internal Name)
- **Endpoint:** `https://portal.alscotoday.com/clientarea.php`
- `Server: <center><br>S.G WebServer<br></center>` in nginx 302 response
- Internal codename for the Secure Gateway webserver

### F2 — Secure Gateway Headers Leak Internal ID
- `x-server-powered-by: Secure Gateway`
- `x-secure_gateway_id: a8c9f265fb643dd95083098ffedf12b4`
- Each request gets a unique SG_ID hash (MD5)

### F3 — Block Page Leaks IP / Transaction ID
- Block page leaks client IP and Transaction ID in HTML comments
- Transaction ID format differs between main portal (MD5) and sandbox (numeric)
- Timer-based retry (30s / 60s / 90s depending on context)

### F4 — ModSecurity CRS Rules Confirm WAF Stack
- Rules G.S.920180 and G.S.920600 map to OWASP ModSecurity CRS rule IDs
- Confirms ModSecurity running behind Cloudflare (portal) and natively (sandbox)

### F5 — POST Method Reaches Different WAF Rule
- POST triggers err=23 / G.S.920180 instead of err=22 / G.S.13
- Different Content-Types do not change the rule triggered
- Suggests POST has a separate handler in the WAF

### F6 — Origin IP Exposed via api.alsco.com
- `api.alsco.com` resolves directly to 65.121.181.75 (bypasses Cloudflare)
- Certificate: `*.alsco.com` issued by Amazon Trust Services
- Origin only responds 403/404 for all paths

### F7 — E-Mail Gateway Server Found
- `smtp.alsco.com` -> 65.121.181.71 (different IP)
- No HTTP services detected, likely SMTP-only

### F8 — WHMCS Integration Detected (Historical)
- Wayback Machine shows `/go/clientarea.php`, `/go/cart.php`, `/go/cart.php?a=add&pid=NNN`
- WHMCS client area was served under `/go/` path
- Currently all WHMCS paths blocked by WAF

### F9 — Sandbox Origin NOT Behind Cloudflare (critical finding)
- `sandbox.securegateway.com` -> 188.34.187.32 (Hetzner, Germany)
- Direct TLS connection works — no Cloudflare to bypass
- SNI required: IP:443 fails with TLS alert, hostname works
- nginx 1.26.1 — **potentially vulnerable to CVE-2025-23419** (TLS session resumption bypass)

### F10 — Phone Verification Authentication Flow Discovered
- `/auth/index.php` exposes a phone verification form (CSRF protected)
- Iraqi phone format (+964) in example — suggests target users/developers
- `/auth/check.php` expects a 6-digit? security code with 90-second expiry
- CSRF token validation fails without session cookies
- Registration endpoint exists (`/auth/register.php`, rate limited)

### F11 — Setup/Install Scripts Exist (403)
- `/setup.php` and `/install.php` return 403 (not 404)
- These scripts exist on the server but WAF blocks access
- Potential attack vector if bypass is found

### F12 — Config Files and phpinfo Return 503
- `/auth/config.php`, `/admin/config.php`, `/config.php`, `/phpinfo.php`
- All return 503 with block page HTML
- Suggests intentional blocking rather than non-existence

### F13 — Static Assets Dated September 2021
- favicon.ico, style.css last modified 2021-09-09
- Indicates the sandbox has been running since at least Sep 2021

---

## Bypass Attempts Summary

### Main Portal (portal.alscotoday.com via Cloudflare)

| Technique | Result |
|-----------|--------|
| Header injection (X-Forwarded-For, etc.) | All 1471 probes blocked |
| Path encoding (%2e, %252e, etc.) | Blocked |
| HTTP method tampering | POST gives different error (still blocked) |
| UA spoofing (Yandex, MJ12bot) | Still blocked |
| Origin direct access | 403/404 for all vhosts |
| Alternative ports | No services found beyond 80/443 |
| Wayback Machine old content | All snapshots show same block page (since Dec 2023) |

### Sandbox (sandbox.securegateway.com, direct, NO Cloudflare)

| Technique | Result |
|-----------|--------|
| Direct GET to `/` | 406 Not Acceptable (ModSecurity) |
| Direct GET to `/msg/` | 200 block page |
| Direct GET to `/auth/index.php` | **200 — phone form accessible** |
| POST to `/auth/index.php` | Without session: CSRF fails; With session: 307 redirect |
| Path traversal | 503 blocked |
| URL encoding (`%2f`, `%252f`) | 404/406 — bypasses WAF but no content |
| Alternative methods (POST/PUT/etc) | Redirected, not usable |
| `./msg/` traversal | 200 but returns block content |
| Null byte | Connection closed |

---

## Potential Attack Vectors

1. **Sandbox Authentication Bypass** — The phone verification at `/auth/index.php` may have vulnerabilities: CSRF bypass, SMS bombing, code interception, timing attacks
2. **Setup/Install Script Exploitation** — `/setup.php` and `/install.php` exist but return 403. If bypassed, could lead to full application compromise
3. **CVE-2025-23419** — TLS session resumption bypass on nginx 1.26.1 (sandbox)
4. **Config File Exposure** — `/auth/config.php`, `/config.php`, `/phpinfo.php` return 503 (not 404). May be accessible with bypass
5. **LFI/RFI via url Parameter** — `/auth/index.php?url=/admin/` suggests a redirect/forward mechanism that may be vulnerable to path traversal
6. **Subdomain Enumeration** — More test/staging instances of Secure Gateway may exist
7. **GitHub/Secret Leaks** — ALSCO may have leaked credentials in public repos
8. **Secure Gateway Product CVEs** — Search for known vulnerabilities in the Secure Gateway software
9. **Phone Verification Weaknesses** — No rate limiting on SMS? Predictable codes? No CAPTCHA?

---

## Next Steps

### High Priority
1. **Phone verification bypass** — Test CSRF, session manipulation, SMS bombing, code brute-force, code reuse
2. **Setup/install script bypass** — Try different methods, headers, and path variations on `/setup.php` and `/install.php`
3. **Session-based testing** — Maintain cookie jar to explore authenticated functionality

### Medium Priority
4. **CVE-2025-23419 research** — Determine if exploitable on nginx 1.26.1 for client cert bypass
5. **LFI/RFI testing** — `url` parameter in `/auth/index.php?url=` may be vulnerable
6. **Subdomain scan** — Use amass/subfinder/crt.sh to find more securegateway.com subdomains
7. **Config bypass** — Try to access config files and phpinfo with different approaches

### Low Priority
8. **Source code search** — Look for Secure Gateway product source on GitHub/GitLab
9. **Product research** — Find documentation or whitepapers for technical insights
10. **Monitor for new deployments** — New instances might temporarily bypass WAF

---

## Key URLs

```
BUG BOUNTY:        https://hackerone.com/alsco
SCOPE:             https://alsco.net/go/bug
MAIN PORTAL:       https://portal.alscotoday.com
API:               https://api.alsco.com
SANDBOX:           https://sandbox.securegateway.com
SANDBOX (IP):      https://188.34.187.32 (SNI required — fails via IP)
MSG PAGE:          https://msg.securegateway.com/msg/
AUTH PAGE:         https://sandbox.securegateway.com/auth/index.php
CHECK CODE:        https://sandbox.securegateway.com/auth/check.php
SETUP:             https://sandbox.securegateway.com/setup.php
INSTALL:           https://sandbox.securegateway.com/install.php
```
