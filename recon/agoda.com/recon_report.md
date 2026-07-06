# Recon Report — https://www.agoda.com/book/

**Target:** https://www.agoda.com/book/
**Program:** Agoda Public (HackerOne)
**Scope:** Single URL — `https://www.agoda.com/book/` (Critical max severity, Bounty eligible)
**Date:** 2026-07-06

---

## 1. Tech Stack Analysis

### Backend / Infrastructure
| Component | Technology |
|-----------|-----------|
| Backend | ASP.NET (`ASP.NET_SessionId` cookie, HttpOnly Secure SameSite=Lax) |
| CDN | Akamai (`akamai-grn` header, `x-envoy-datacenter: hk`) |
| Proxy | Envoy Proxy (`x-envoy-upstream-service-time`) |
| TLS | DigiCert / GeoTrust TLS RSA CA G1 — *.agoda.com |
| Fraud Detection | Riskified (`beacon.riskified.com`) |

### Frontend
| Component | Notes |
|-----------|-------|
| Architecture | SPA (Single Page App) — JS-rendered, no forms in static HTML |
| Framework | React (detected: `createElement`, `useState`, React patterns in vendor bundle) |
| Bundler | Webpack (vendor DLL pattern) |
| Design System | `agoda.css` v4.74.0 (via `cdn10.agoda.net`) |
| HTTP Client | Axios |
| Date Library | Moment.js |
| Observability | `agobservabilityjs` v1.0.0 — sends to `bento.agoda.com/v2` |
| Analytics | `@agoda/analytics-data-acquisition` |
| Auth/Cart | `@cart-js/core`, `@ewl/rta-headerfooter-client` |
| CDN Hosts | cdn.agoda.net, cdn6.agoda.net, cdn10.agoda.net, cdn2.agoda.net |

### Detected Versions (from vendor JS bundle)
- `4.74.0` — Agoda Design System
- `3.26.0`, `3.25.1`, `3.20.1` — Likely React/Angular packages
- `2.6.9` — Unknown internal package
- `1.3.2` — Unknown internal package

---

## 2. Security Headers Audit

| Header | Status | Risk |
|--------|--------|------|
| `Strict-Transport-Security` | ✅ `max-age=31536000` | Good |
| `X-Content-Type-Options` | ✅ `nosniff` | Good |
| `X-Frame-Options` | ❌ **MISSING** | Clickjacking |
| `Content-Security-Policy` | ❌ **MISSING** | XSS mitigation |
| `X-XSS-Protection` | ❌ **MISSING** | Legacy XSS filter |
| `Referrer-Policy` | ❌ **MISSING** | Referer leakage |
| `Permissions-Policy` | ❌ **MISSING** | Feature abuse |
| `Access-Control-Allow-Origin` | ❌ **MISSING** | CORS policy |

### TLS Protocol Support
| Protocol | Status |
|----------|--------|
| TLS 1.0 | ⚠️ **Enabled** (deprecated, POODLE/BEAST) |
| TLS 1.1 | ⚠️ **Enabled** (deprecated) |
| TLS 1.2 | ✅ Enabled |
| TLS 1.3 | ✅ Enabled |

---

## 3. Forms Detected

**No forms found in static HTML** — the page is a JS-heavy SPA. All form rendering and POST submissions happen dynamically via client-side JavaScript. Forms were not detectable without a headless browser.

---

## 4. API and POST Endpoints (from HTML/JS analysis)

### Observability / Telemetry
- `POST` `https://bento.agoda.com/v2` — agobservability telemetry
- `POST` `https://hkg-gc-qa.agoda.local/v2` — **QA endpoint leaked in production JS**

### Core Endpoints
- `https://www.agoda.com/` — Main application entry
- `https://www.agoda.com/book/` — Booking page (in-scope)
- `https://www.agoda.com/flights` — Flight booking
- `https://www.agoda.com/account/bookings.html`
- `https://www.agoda.com/account/profile.html`
- `https://www.agoda.com/account/signin.html`
- `https://www.agoda.com/partner/paytm/logincallback` — OAuth callback

### CDN / Static Assets
- `cdn6.agoda.net/cdn-bfspa/js/mspa/` — JS bundle hosting
- `cdn6.agoda.net/cdn-activities/` — Activity images
- `cdn10.agoda.net/cdn-design-system/themes/4.74.0/` — Design system

---

## 5. Interesting Findings

### 5.1 TLS 1.0 / 1.1 Enabled
Both TLS 1.0 and 1.1 are accepted. These protocols are deprecated by PCI DSS and have known attacks (POODLE CVE-2014-3566, BEAST CVE-2011-3389).

### 5.2 Internal QA Domain in Production JS
`hkg-gc-qa.agoda.local` is referenced in the production JS bundle as an alternative telemetry endpoint. This leaks internal infrastructure.

### 5.3 Subdomains Discovered from JS
| Subdomain | Purpose |
|-----------|---------|
| `analytics.agoda.com` | Analytics |
| `bento.agoda.com` | Observability backend |
| `flights.agoda.com` | Flights booking |
| `notices.agoda.com` | Help center |
| `hkg-gc-qa.agoda.local` | **Internal QA (leaked)** |
| `careersatagoda.com` | Careers (separate domain) |

### 5.4 CORS Preflight
- OPTIONS requests return `204 No Content` with NO CORS headers (no `Access-Control-Allow-Origin`)
- `Access-Control-Allow-Credentials: true` is set on main responses but without proper origin validation

### 5.5 Security Contact
- `vulnerabilities@agoda.com` (via `/.well-known/security.txt`)
- Program contact: `agoda-public` on HackerOne

### 5.6 robots.txt
- `/book/` is explicitly disallowed (interesting for a scope asset)
- `/account/`, `/bookings/`, `/flights/results` also disallowed

---

## 6. CORS Test Results
```
Preflight OPTIONS to https://www.agoda.com/book/
  Origin: https://evil.com
  Result: 204 No Content (no ACAO header returned)
```

---

## 7. Recommendations (for hunting focus)

1. **TLS 1.0/1.1 deprecation** — Low severity, configuration issue
2. **Missing CSP** — Test XSS vectors in JS-rendered content
3. **Missing X-Frame-Options** — Test clickjacking on booking flow
4. **Internal domain leak** — `hkg-gc-qa.agoda.local` exposed
5. **CORS configuration** — Test credentialed CORS on API endpoints
6. **Focus hunting on:** Booking flow logic (IDOR in bookings, price manipulation, race conditions on payment)
