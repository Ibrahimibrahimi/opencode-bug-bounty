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
| Backend | ASP.NET (`ASP.NET_SessionId` cookie, HttpOnly Secure SameSite=Lax) + Ktor (Kotlin) on `booking-bff` |
| BFF Service | Ktor (`io.ktor.http.Parameters` in error messages) |
| GraphQL | `propertyapisearchdocker` v3.44.943.gl |
| CDN | Akamai (`akamai-grn`, DNS: `e7851.x.akamaiedge.net`) |
| Proxy | Envoy Proxy (`x-envoy-upstream-service-time`, `x-envoy-datacenter: hk`) |
| TLS | DigiCert / GeoTrust TLS RSA CA G1 — `*.agoda.com` / `agoda.com` |
| Fraud Detection | Riskified (`beacon.riskified.com`) |
| Observability | agobservabilityjs v1.0.0 → `bento.agoda.com/v2` |

### Frontend
| Component | Details |
|-----------|---------|
| Architecture | SPA (Single Page App) — JS-rendered, no forms in static HTML |
| Framework | React |
| Bundler | Webpack (vendor DLL pattern) |
| Design System | `agoda.css` v4.74.0 |
| HTTP Client | Axios |
| Date Library | Moment.js |
| Analytics | `@agoda/analytics-data-acquisition` |
| Auth/Cart | `@cart-js/core`, `@ewl/rta-headerfooter-client` |
| Google APIs | `apis.google.com/js/platform.js`, recaptcha, AppleID |
| CDN Hosts | cdn.agoda.net, cdn6.agoda.net, cdn10.agoda.net, cdn0.agoda.net, cdn2.agoda.net |

### npm Library Versions (from vendor.js)
| Version | Library |
|---------|---------|
| 3.25.1 | core-js |
| 3.26.0 | core-js |
| 4.74.0 | Agoda Design System |
| 1.3.2 | Unknown internal package |
| 2.6.9 | Unknown internal package |

### Service Versions Leaked
| Service | Version | Source |
|---------|---------|--------|
| `propertyapisearchdocker` | 3.44.943.gl | GraphQL response header `ag-service-version` |

---

## 2. Security Headers

| Header | Status | Risk |
|--------|--------|------|
| `Strict-Transport-Security` | ✅ `max-age=31536000` | Good |
| `X-Content-Type-Options` | ✅ `nosniff` | Good |
| `X-Frame-Options` | ❌ **MISSING** | Clickjacking |
| `Content-Security-Policy` | ❌ **MISSING** | XSS / data injection |
| `X-XSS-Protection` | ❌ **MISSING** | Legacy XSS filter |
| `Referrer-Policy` | ❌ **MISSING** | Referer leakage |
| `Permissions-Policy` | ❌ **MISSING** | Feature abuse |
| `Access-Control-Allow-Origin` | ❌ **MISSING** | CORS |

### TLS Protocols
| Protocol | Status | Notes |
|----------|--------|-------|
| TLS 1.0 | ⚠️ **Enabled** | POODLE (CVE-2014-3566), BEAST (CVE-2011-3389) |
| TLS 1.1 | ⚠️ **Enabled** | Deprecated |
| TLS 1.2 | ✅ | |
| TLS 1.3 | ✅ | |

---

## 3. API Endpoints Discovered (from JS Bundle Analysis)

### Booking API — Under www.agoda.com (likely in scope)
| Endpoint | Method | Response | Notes |
|----------|--------|----------|-------|
| `/api/gw/BookingsV3/Setup` | POST | 200 (734 bytes) | Booking gateway setup — full JSON schema |
| `/api/gw/BookingsV3/Continue` | POST | — | Booking continuation |
| `/api/gw/BookingsV3/Continue3DS2Challenge` | POST | — | 3DS2 challenge |
| `/api/gw/BookingsV3/Continue3DS2Devicefingerprint` | POST | — | 3DS2 fingerprint |
| `/api/gw/BookingsV3/ContinueRedirect` | POST | — | Redirect handler |
| `/api/gw/bcr` | POST | 400 | Gateway BCR |
| `/api/booking-bff/booking/setup` | POST | 200 (256 bytes) | BFF booking setup |
| `/api/booking-bff/booking/cr` | POST | 400 (needs StatusToken) | Booking creation |
| `/api/booking-bff/booking/continue` | POST | — | Booking continue |
| `/api/booking-bff/booking/pax-verification` | POST | — | Passenger verification |
| `/api/booking-bff/booking/status` | POST | — | Booking status |
| `/api/booking-bff/booking/traffic-message` | POST | — | Traffic message |
| `/api/booking-bff/saved-traveller/fetch` | POST | **401 Unauthorized** | Auth required — IDOR potential |
| `/api/booking-bff/saved-traveller/upsert` | POST | — | Upsert traveller |
| `/api/bookings/create` | POST | — | Create booking |
| `/api/cart/add` | POST | — | Add to cart |
| `/api/cart/items` | GET/POST | 405 | Cart items |
| `/api/cart/remove` | POST | — | Remove from cart |

### GraphQL Endpoints
| Endpoint | Method | Response |
|----------|--------|----------|
| `www.agoda.com/graphql` | POST | 200 — Gzipped, introspection disabled |
| `www.agoda.com/api/activities/graphql` | POST | 400 — Activities GraphQL |
| `www.agoda.com/cars/graphql` | POST | — Cars GraphQL |

### Public Data Endpoints
| Endpoint | Method | Response |
|----------|--------|----------|
| `/api/cronos/layout/culture/getlanguages` | GET | 200 — 37 languages |
| `/api/cronos/layout/currency/getlist` | GET | 200 — Full currency list |
| `/api/cronos/geo/country/topdestinations` | GET | 200 (13KB) |
| `/api/cronos/layout/login/params` | GET | — Login params |
| `/api/cronos/layout/notification/get` | GET | — Notifications |
| `/api/cronos/partnermember/partnerdata` | GET | — Partner data |
| `/api/cronos/mkt/GetConsentBanner` | GET | — Consent banner |
| `/api/cronos/layout/PageHeaderApi/UserMenuViewModel` | GET | — User menu |

---

## 4. Security Findings

### 🛑 4.1 Internal Infrastructure Leaked in Production JS
Multiple internal/dev endpoints found in production JavaScript:

| Endpoint | Type |
|----------|------|
| `hkg-gc-qa.agoda.local` | **QA telemetry endpoint** |
| `activity-search.privatecloud.qa.agoda.is` | QA Activities GraphQL |
| `car-search-qa.privatecloud.qa.agoda.is` | QA Cars GraphQL |
| `universal-login-api-qa.privatecloud.qa.agoda.is` | QA Universal Login API |
| `gitlab.agodadev.io` | Internal GitLab |
| `ads-theme-editor.agodadev.io` | Dev tool |

### 🛑 4.2 Service Version Leak
GraphQL endpoint returns `ag-service-version: 3.44.943.gl` and `ag-service-name: propertyapisearchdocker` in response headers.

### 🛑 4.3 Booking API Schema Discovery
`/api/gw/BookingsV3/Setup` returns a full JSON schema revealing the booking data model:
```json
{
  "paymentDetail": null,
  "products": null,
  "bookingToken": null,
  "serverStatus": {"status": 10, "category": 7},
  "pricing": null,
  "promotionInfo": {"isPromotionCodeEligible": false},
  "installmentPlanOptions": null,
  "externalLoyalty": null,
  "addOnsV2": [],
  "bookingConsentInfo": []
}
```

### 🛑 4.4 Auth-Protected Endpoint Discovered
`/api/booking-bff/saved-traveller/fetch` **requires authentication** (401). This endpoint returns saved traveller PII. **IDOR potential**: if user A can fetch user B's saved travellers by manipulating IDs.

### 🛑 4.5 Security Headers Missing
No CSP, X-Frame-Options, Referrer-Policy, or Permissions-Policy — enables clickjacking, XSS vectors, referer leakage.

### 🛑 4.6 TLS 1.0/1.1 Supported
Deprecated protocols accepted. PCI DSS non-compliant since 2018.

### 4.7 CORS Configuration
- OPTIONS preflight returns 204 with NO `Access-Control-Allow-Origin`
- Main responses set `Access-Control-Allow-Credentials: true` without origin validation
- `Access-Control-Allow-Methods: GET, POST`
- `Access-Control-Expose-Headers: ag-correlation-id`

### 4.8 GraphQL Introspection Disabled
All queries return: `"Introspection is not allowed."` — proper security control.

---

## 5. Interesting Observations

### robots.txt
- `/book/` is explicitly disallowed — despite being the only in-scope asset
- `/account/`, `/bookings/`, `/flights/results` also disallowed

### Subdomains Discovered
| Subdomain | Purpose |
|-----------|---------|
| `www.agoda.com` | **In scope** — booking |
| `gw.agoda.com` | Gateway API |
| `gwapi.agoda.com` | Gateway API (alternative) |
| `gwpci.agoda.com` | **PCI gateway** (payment sensitive) |
| `my.agoda.com` | User account portal |
| `hkg.agoda.com` | Hong Kong DC (Universal Login) |
| `master.wgpl.agoda.com` | Master WGP |
| `analytics.agoda.com` | Analytics |
| `bento.agoda.com` | Observability |
| `flights.agoda.com` | Flights |
| `notices.agoda.com` | Help center |
| `cdn*.agoda.net` | CDN assets |

### Security Contact
- `vulnerabilities@agoda.com` (via `/.well-known/security.txt`)
- `https://www.agoda.com/.well-known/security.txt` (properly configured)
- Hiring: `https://careersatagoda.com/vacancies/?teams[]=Technology`

---

## 6. Hunting Recommendations (Priority Order)

### High Priority
1. **IDOR on Saved Traveller API** — `/api/booking-bff/saved-traveller/fetch` requires auth; test if user A can access user B's PII by manipulating traveller IDs
2. **Booking Flow Manipulation** — `/api/gw/BookingsV3/Setup` returns full schema; test price manipulation, promo code abuse, payment bypass via `/api/gw/bcr`
3. **XSS** — No CSP means potential for stored/reflected XSS in SPA-rendered content

### Medium Priority
4. **Clickjacking** — No X-Frame-Options on booking page
5. **TLS 1.0/1.1** — Deprecated protocols (Low severity, config issue)
6. **CORS Misconfiguration** — Credentials allowed without origin validation

### Low Priority (Information Disclosure)
7. **Internal QA domain leak** — `hkg-gc-qa.agoda.local` exposed
8. **Service version leak** — `propertyapisearchdocker` v3.44.943.gl
9. **Internal GitLab/dev tools exposure** — `gitlab.agodadev.io`, `ads-theme-editor.agodadev.io`
