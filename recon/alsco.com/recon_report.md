# ALSCO / Secure Gateway Recon Report

**Target:** ALSCO — Secure Gateway® Bug Bounty Program (HackerOne)
**Recon Date:** 2026-07-05
**Scope:** SECURE GATEWAY®, WEB SECURE GATEWAY™, Cloud SECURE GATEWAY™, E-Mail SECURE GATEWAY™, DataBase SECURE GATEWAY™

---

## Asset Inventory

### Primary Domains

| Domain | Type | IP / Hosting | Notes |
|--------|------|-------------|-------|
| `alsco.net` | Marketing site | Cloudflare (104.21.64.16, 172.67.174.27) | TXT: h1-domain-verification, SPF, Google/AbuseIPDB/FB verification |
| `www.alsco.net` | Marketing site | Cloudflare (same as alsco.net) | Same as alsco.net |
| `alsco.com` | Landing page | Netlify (13.215.239.219, 52.74.6.109) | Redirects to https://alsco.com/ (Netlify) |
| `www.alsco.com` | Landing page | Netlify (same as alsco.com) | Redirects to https://alsco.com/ |
| `api.alsco.com` | API endpoint | IIS/10.0 + ASP.NET (65.121.181.75) | Origin server, CenturyLink, Murray UT |
| `portal.alscotoday.com` | **Secure Gateway® App** | Cloudflare (104.21.21.39, 172.67.196.95) | Main in-scope asset — SG product interface |

### Infrastructure Map

```
portal.alscotoday.com
  → Cloudflare (WAF, CDN, JS challenge)
    → nginx (reverse proxy, "S.G WebServer" header)
      → IIS/10.0 + ASP.NET (origin at 65.121.181.75, CenturyLink)

api.alsco.com → 65.121.181.75 (same origin, IIS/10.0 + ASP.NET)

alsco.com → Netlify (static marketing)
alsco.net → Cloudflare (marketing blog)
```

### DNS Records (alsco.net)

```
A:    104.21.64.16, 172.67.174.27
MX:   route1/2/3.mx.cloudflare.net
NS:   casey.ns.cloudflare.com, sarah.ns.cloudflare.com
TXT:  h1-domain-verification=MbFYxRbo..., SPF, google-site-verification, etc.
```

---

## Technology Stack

### Secure Gateway (portal.alscotoday.com)

| Layer | Technology | Evidence |
|-------|-----------|----------|
| CDN/WAF | **Cloudflare** | cf-ray, cf-cache-status, __cfduid cookies, nel/report-to headers |
| Reverse Proxy | **nginx** | `Server: nginx` header on 302 responses |
| Web Server | **IIS 10.0** | `Server: Microsoft-IIS/10.0` on origin direct access |
| Backend Framework | **ASP.NET** | `X-Powered-By: ASP.NET` on origin |
| SG Engine | **Secure Gateway®** | `X-Server-Powered-By: Secure Gateway®`, `X-Secure_Gateway_ID` headers |
| Base URL | `/msg/` | All app resources served from this path |

### Security Headers (Observed)

```
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Referrer-Policy: strict-origin-when-cross-origin / no-referrer
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'; script-src 'self' 'strict-dynamic' ...
Permissions-Policy: geolocation=(), camera=(), microphone=(), interest-cohort=()
Expect-CT: enforce; max-age=3600
Feature-Policy: accelerometer 'none'; ...
```

---

## Findings & Observations

### F1 — Server Header Leaks "S.G WebServer" (Internal Name)
- **Endpoint:** `https://portal.alscotoday.com/clientarea.php`
- First redirect response contains `Server: <center><br>S.G WebServer<br></center>`
- This reveals that the internal codename for the Secure Gateway webserver is "S.G WebServer"
- Likely a custom nginx build or branded server

### F2 — Secure Gateway Headers Leak Internal ID
- `x-server-powered-by: Secure Gateway®` — confirms product name
- `x-secure_gateway_id` header present in all responses with a hash value
  - Example: `a8c9f265fb643dd95083098ffedf12b4`
- These headers could help fingerprint the SG version/instance

### F3 — Cloudflare JS Challenge with IP/Transaction ID Leak
- App enforces Cloudflare JS challenge for all `/msg/` paths
- Block page HTML leaks:
  - **Client IP:** `35.221.174.247` (our IP)
  - **Transaction ID:** `8e07297d3adaa990b3b2a19991fb2782`
  - Also shown in HTML comment: `20260706-031728` (date-based ID)
- Error code: `G.S.13` (Gateway Security Rule #13)
- Error message: "Error, 403 - Access Denied [AS] (F5)"

### F4 — Origin Server IP Exposed via api.alsco.com
- `api.alsco.com` resolves directly to `65.121.181.75` (IIS/10.0)
- This bypasses Cloudflare protection for this hostname
- Running on CenturyLink (AS209) in Murray, Utah
- Certificate SAN: `*.alsco.com`

### F5 — Common WHMCS URL Patterns Present
- `/clientarea.php`, `/cart.php` paths respond (redirects to SG)
- Suggests portal uses WHMCS integrated with Secure Gateway

### F6 — No Subdomain Takeover Candidates Found
- Checked common subdomains for both alsco.net and alsco.com
- All resolved subdomains return valid HTTP responses (not available for takeover)

---

## Cloudflare WAF Bypass Attempts

### Block Baseline
- Normal request to portal → Cloudflare JS challenge (30s timer)
- Error 403 with `[AS] (F5)` — suggests F5 BIG-IP ASM or similar WAF integrated with Cloudflare

### Origin Direct Access
- `65.121.181.75:80/443` with `Host: portal.alscotoday.com` → 403 Forbidden (IIS)
- `65.121.181.75:80/443` with `Host: api.alsco.com` → 403 Forbidden (IIS)

---

## Potential Attack Vectors

1. **Cloudflare Bypass:** Find the true origin IP (not the CenturyLink one which returns 403 for SG paths)
2. **WHMCS Vulnerabilities:** If WHMCS is integrated, check for known CVE exploitation
3. **API Endpoints:** Discover hidden API routes under `/api/`, `/v1/`, `/v2/` on portal
4. **Path Traversal in `/msg/`:** Check if directory traversal works in SG paths
5. **IIS Tilde Enumeration:** Check for ASP.NET tilde vulnerability on origin
6. **ViewState Deserialization:** ASP.NET app — check for viewstate without MAC protection
7. **Open Redirect:** Check `ReturnUrl` patterns in login flow
8. **Subdomain Enumeration on *.alsco.com:** Wildcard cert suggests more subdomains exist

---

## Next Steps

- [ ] Run `bypass_403.sh` on `portal.alscotoday.com/msg/`
- [ ] Enumerate `*.alsco.com` subdomains (wildcard cert)
- [ ] Check for IIS/ASP.NET specific vulns (ViewState, tilde, traces)
- [ ] Try to register an account / access any login form directly
- [ ] Check HackerOne for disclosed ALSCO reports
- [ ] Look for the Secure Gateway product in CVE databases
- [ ] Test `api.alsco.com` for API endpoints
