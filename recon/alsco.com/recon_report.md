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
| `www.alsco.net` | Marketing site | Cloudflare | Same as alsco.net |
| `alsco.com` | Landing page | Netlify | Redirects to https://alsco.com/ |
| `www.alsco.com` | Landing page | Netlify (13.215.239.219, 52.74.6.109) | Redirects to https://alsco.com/ |
| `api.alsco.com` | API | IIS/10.0 + ASP.NET (65.121.181.75) | Origin server, CenturyLink, Murray UT. Cert: *.alsco.com (Amazon Trust) |
| `portal.alscotoday.com` | **Secure Gateway® App** | Cloudflare → nginx → IIS/10.0 | Main in-scope asset. JS challenge WAF. |
| `smtp.alsco.com` | SMTP Server | 65.121.181.71 | No HTTP response. Likely E-Mail Secure Gateway. |

### Related Domains (Not ALSCO-owned)

| Domain | Status | Notes |
|--------|--------|-------|
| `alsco.cloud` | Cloudflare 403 | Behind Cloudflare, same as main site |
| `alsco.co` | Cloudflare 403 | Behind Cloudflare |
| `alsco.org` | For sale (5.8.93.86) | Domain squatter, openresty/1.31.1.1 |
| `alsco.us` | No response | Unreachable |

### Infrastructure Map

```
portal.alscotoday.com
  → Cloudflare (WAF, CDN, JS challenge)
    → nginx (reverse proxy, "S.G WebServer" header)
      → IIS/10.0 + ASP.NET (origin at 65.121.181.75, CenturyLink)

api.alsco.com → 65.121.181.75 (same origin, IIS/10.0 + ASP.NET)
smtp.alsco.com → 65.121.181.71 (SMTP, no HTTP)

alsco.com → Netlify (static landing page)
alsco.net → Cloudflare (marketing blog)
```

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
| WAF Rules | **ModSecurity CRS + Custom** | G.S.13, G.S.920180 (CRS rule), G.S.920600 (CRS rule) |

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
```

---

## WAF Behavior Analysis

### Error Code Matrix

| Method | Path | Status | err | Rule | Notes |
|--------|------|--------|-----|------|-------|
| GET | `/msg/` | 200 | — | — | Block page (Cloudflare JS challenge) |
| GET | `/*` | 200/302 | 22 | G.S.13 | General GET block |
| HEAD | `/*` | 403 | — | — | Blocked at edge |
| POST | `/*` | 302 | **23** | **G.S.920180** | Content-Type policy (ModSecurity CRS) |
| PUT/PATCH/DELETE | `/*` | 403 | — | — | Blocked at edge |
| OPTIONS | `/*` | 403 | — | — | Blocked at edge |
| TRACE | `/*` | 405 | — | — | Reached backend (IIS) |
| POST + `application/x-www-form-urlencoded` | `/*` | 302 | 23 | G.S.920180 | Same as no CT |
| POST + `multipart/form-data` | `/*` | 302 | 23 | G.S.920180 | Same |

### Rule IDs Identified

| Rule | ModSecurity CRS Match | Description |
|------|----------------------|-------------|
| G.S.13 | — (custom) | General GET block |
| G.S.920180 | 920180 | Content-Type request header inspection |
| G.S.920600 | 920600 | Request body limit / POST parameter limit |

### Block Page Annotations
- `[AS] (F5)` — "Automated Security"? F5 Networks BIG-IP?
- `[B] (F3)` — Different block mode (observed in Wayback Dec 2023)
- Transaction ID format: `8e07297d3adaa990b3b2a19991fb2782` (MD5 hash)
- SG_ID format: `178329694362.361644` (epoch timestamp + counter)

---

## Findings & Observations

### F1 — Server Header Leaks "S.G WebServer" (Internal Name)
- **Endpoint:** `https://portal.alscotoday.com/clientarea.php`
- `Server: <center><br>S.G WebServer<br></center>` in nginx 302 response
- Internal codename for the Secure Gateway webserver

### F2 — Secure Gateway Headers Leak Internal ID
- `x-server-powered-by: Secure Gateway®`
- `x-secure_gateway_id: a8c9f265fb643dd95083098ffedf12b4`
- Each request gets a unique SG_ID hash

### F3 — Cloudflare JS Challenge with IP/Transaction ID Leak
- Block page leaks client IP and Transaction ID in HTML comments
- Error: "403 - Access Denied [AS] (F5)"
- Timer-based retry (30 second cooldown)

### F4 — ModSecurity CRS Rules Confirm WAF Stack
- Rules G.S.920180 and G.S.920600 map to OWASP ModSecurity CRS rule IDs
- Confirms ModSecurity running behind Cloudflare

### F5 — POST Method Reaches Different WAF Rule
- POST triggers err=23 / G.S.920180 instead of err=22 / G.S.13
- Different Content-Types do not change the rule triggered
- Suggests POST is handled differently at the WAF level

### F6 — Origin IP Exposed via api.alsco.com
- `api.alsco.com` resolves directly to 65.121.181.75 (bypasses Cloudflare)
- Certificate: `*.alsco.com` issued by Amazon Trust Services
- Origin only responds 403/404 for all paths

### F7 — E-Mail Gateway Server Found
- `smtp.alsco.com` → 65.121.181.71 (different IP)
- No HTTP services detected, likely SMTP-only

### F8 — WHMCS Integration Detected (Historical)
- Wayback Machine shows `/go/clientarea.php`, `/go/cart.php`, `/go/cart.php?a=add&pid=NNN`
- WHMCS client area was served under `/go/` path
- Currently all WHMCS paths blocked by WAF

---

## Bypass Attempts Summary

| Technique | Result |
|-----------|--------|
| Header injection (X-Forwarded-For, etc.) | All 1471 probes blocked |
| Path encoding (%2e, %252e, etc.) | Blocked |
| HTTP method tampering | POST gives different error (still blocked) |
| UA spoofing (Yandex, MJ12bot) | Still blocked |
| Origin direct access | 403/404 for all vhosts |
| Alternative ports | No services found beyond 80/443 |
| Wayback Machine old content | All snapshots show same block page (since Dec 2023) |

---

## Potential Attack Vectors

1. **Find true origin IP** — 65.121.181.75 returns 403, likely not the real origin. Cloudflare may proxy to a different backend.
2. **Solve Cloudflare JS challenge** — Not feasible programmatically; requires browser automation.
3. **Monitor for new subdomains** — New deployments might bypass WAF initially.
4. **Look for WHMCS CVEs** — If WHMCS version is identifiable, known CVEs might work.
5. **Check GitHub/Secret leaks** — ALSCO may have leaked credentials in public repos.
6. **Secure Gateway product CVEs** — Search for known vulnerabilities in the Secure Gateway software.

---

## Next Steps (Blocked)

The target (`portal.alscotoday.com` / Secure Gateway) is behind a multi-layered WAF (Cloudflare + ModSecurity + custom rules) that has been in place since at least Dec 2023. No bypass was found after extensive testing. 

**Recommendations:**
- Set up continuous subdomain monitoring for new ALSCO assets
- Search for Secure Gateway product documentation/whitepapers for technical insights
- Check if the Secure Gateway software is available for download (maybe demo/trial version)
- Consider switching to a different target
