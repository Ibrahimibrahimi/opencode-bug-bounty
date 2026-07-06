# 8x8 Recon Report

**Target:** 8x8 — Unified Communications & Contact Center
**Program:** https://hackerone.com/8x8-bounty
**Recon Date:** 2026-07-06
**Bounties:** $100-$3,000
**Stats:** 615 reports, 157 resolved, 100% efficiency
**Scope:** Wildcard (39), Domain (30), Other (21), Executable (1), Android (1), API (1) + 2 more

---

## Program Scope Assets

### In-Scope Products

| Product | Assets | Notes |
|---|---|---|
| **8x8 Work** | `work.8x8.com`, `work-staging.8x8.com`, Desktop App, iOS, Android | No test credentials provided |
| **Virtual Contact Center** | `vcc-*.8x8.com` (wildcard), `vcc-ce.8x8.com`, `superx.8x8.com`, `analytics-*.8x8.com` | CM/AGUI/QM paths |
| **8x8 VOAPI** | `voapi.8x8.com`, `voapi-au.8x8.com`, `voapi-uk.8x8.com` | Cloudflare + F5 BIG-IP ASM + Java Spring |
| **8x8 Video** | `8x8.vc` | Jitsi Meet |
| **Jitsi as a Service** | `jaas.8x8.vc` | Signup at `jaas.8x8.vc` |
| **8x8 Connect (CPaaS)** | `connect.8x8.com`, SMS APIs (sms.8x8.com, sms.8x8.uk, sms.8x8.id, sms.us.8x8.com, chatapps.8x8.com) | Self sign-up available |
| **Other** | `vap.8x8.com`, `user-profile.8x8.com`, `user-profile-staging.8x8.com`, `uc.8x8pilot.com`, `sso.8x8pilot.com` | |

### Jitsi Open Source (In Scope)

Repositories: `jitsi/jitsi`, `jitsi/lib-jitsi-meet`, `jitsi/jicofo`, `jitsi/jitsi-videobridge`, etc.

---

## Infrastructure Overview

### DNS Map

| Domain | IPs | CDN | Tech |
|---|---|---|---|
| `8x8.com` | 54.69.33.46 | None (AWS EC2) | Apache |
| `www.8x8.com` | Cloudflare | Cloudflare | 429 rate limited |
| `work.8x8.com` | 104.16.109-110.61 | Cloudflare | React SPA + Java Spring OAuth2 |
| `work-staging.8x8.com` | 104.16.109-110.61 | Cloudflare | Staging |
| `voapi.8x8.com` | 104.16.109-110.61 | Cloudflare + F5 BIG-IP ASM | Java Spring |
| `vcc-*.8x8.com` | Cloudflare | Cloudflare | PHP + nginx |
| `superx.8x8.com` | 104.16.109-110.61 | Cloudflare | |
| `8x8.vc` | 104.18.34.134, 172.64.153.122 | Cloudflare | Jitsi Meet |
| `jaas.8x8.vc` | 104.18.34.134, 172.64.153.122 | Cloudflare | Jitsi as a Service |
| `connect.8x8.com` | 54.192.248.x | AWS CloudFront | Salesforce + SystemJS |
| `sso.8x8pilot.com` | 172.64.154.168, 104.18.33.88 | Cloudflare | |
| `uc.8x8pilot.com` | 8.25.218.38 (DEAD) | None | DNS SERVFAIL |
| `developer.8x8.com` | Cloudflare | Cloudflare | nginx |

---

## Service Deep Dives

### 1. work.8x8.com — 8x8 Work (Primary Target)

**Status:** Returns 302 → `/oauth2/authorization/vos-work` (Spring Security OAuth2)
**Login page:** Returns full SSO page with:
- Bootstrap 4.5.3
- Google Sign-In button integration
- Form action: `/v2/login/options`
- Background image: `/v2/images/vom-graphic-*.jpg`
- Favicon: `/v2/images/favicon-96x96-*.png`
- JS bundles: `static/runtime.*.js`, `static/uiBundle.*.js` (Webpack with hash `4f20fa117e4607a133d3`)
- CSS bundle: `/v2/css/sso-*.css`
- SPA shell: React-based (empty div#root + splash screen)

**OAuth2 Flow:**
```
GET /oauth2/authorization/vos-work → 302 redirect to /v2/login/options
GET /v2/login/options → SSO login page with Google option
```

**`.well-known/openid-configuration`:** Returns SPA shell (200, React app) — NOT OIDC metadata (likely misconfigured or behind auth)

**Accessible paths:**
- `/oauth2/authorization/vos-work` — 302 (OAuth2 authorization)
- `/oauth2/authorization/superx-workspace` — 302 (cross-app)
- `/login` — 302
- `/oauth2/token` — 302
- `/.well-known/openid-configuration` — 200 (SPA shell)
- `/sso` — 302
- `/auth` — 302
- `/api` — 302

---

### 2. vcc-*.8x8.com — Virtual Contact Center

**Wildcard scope:** `vcc-*.8x8.com`

**Live regions discovered:**
```
vcc-na1.8x8.com    vcc-na2.8x8.com    vcc-na3.8x8.com
vcc-na4.8x8.com    vcc-na5.8x8.com    vcc-na10.8x8.com
vcc-na20.8x8.com   vcc-na30.8x8.com   vcc-eu2.8x8.com
vcc-eu3.8x8.com    vcc-eu10.8x8.com
```

**Tech Stack:** PHP + nginx
**VCC Components:**
| Path | Description |
|---|---|
| `/CM/login.php` | Configuration Manager — "ADMINISTRATOR LOGIN" |
| `/AGUI/login.php` | Agent Workspace — "Login" |
| `/QM/login.php` | Quality Management |
| `/GEN/js/` | Shared JS library (403 — exists) |
| `/api` | 301 redirect |

**VCC na30 Analysis:**
- jQuery 1.9.1 (CM) / jQuery 1.8.2 (AGUI) — **both outdated, vulnerable**
- Bootstrap dark_blue theme
- Session cookies: `WPJ_CM` (CM), `wpj_agui` (AGUI)
  - Domain-wide: `.8x8.com`
  - httponly + secure + samesite=none
  - 24-hour expiry
  - Hash-like values (SHA-256 of session data)
- AGUI login script: `login.js?_v=e742d79`
- **Hardcoded analytics key:** `analyticKey = '4541aba6a8122b2dd53c1d05e233c8da'`
- **CWE-798 reference in source:** `// CWE ID 798 - can be mitigated, values came from LDAP, this is just a placeholder`
- Cookie deletion on login page load: `vcc-web-apps=deleted`

**CSP:** `frame-ancestors 'self' vcc-na30.8x8.com vcc-na30-vip.8x8.com vcc-na30b.8x8.com vcc-na30b-vip.8x8.com`

**VIP Subdomains (all live):**
| Subdomain | Status | Notes |
|---|---|---|
| `vcc-na30-vip.8x8.com` | 200 | Same VCC app (VIP endpoint) |
| `vcc-na30b.8x8.com` | 200 | Same VCC app (backup/backend) |
| `vcc-na30b-vip.8x8.com` | 200 | Same VCC app (backup VIP) |

---

### 3. 8x8.vc — Jitsi Video Conferencing

**Status:** 200 — Jitsi Meet instance
**Version:** `lib-jitsi-meet.min.js?v=9168.6241`
**App bundle:** `app.bundle.min.js?v=9168.6241`

**config.js (public — contains message to hackers):**
```
"Hey there Hacker One bounty hunters! None of the contents of this file
are security sensitive. Sorry, but your princess is in another castle :-)"
```

**SSO Configuration (from config.js):**
```javascript
tokenAuthUrl: 'https://sso.8x8.com/v2/login/meetings_web_sso?code_challenge_method=S256&code_challenge={code_challenge}&state={state}',
tokenAuthInline: true,
sso: {
    ssoService: 'sso.8x8.com',
    tokenService: 'api-vo.cloudflare.jitsi.net',
    clientId: 'meetings_web_sso'
},
tokenRespectTenant: true,
```

**Architecture:**
- Domain: `8x8.vc`
- MUC: `conference.8x8.vc`
- Focus: `focus.8x8.vc`
- SSO: `sso.8x8.com` (new subdomain discovered!)
- Token service: `api-vo.cloudflare.jitsi.net` (Cloudflare Jitsi integration)
- Auth flow: PKCE (S256 code challenge)
- Client ID: `meetings_web_sso`

**Credentials cookie system (from 8x8.vc HTML):**
```javascript
const cookieName = subdomain === 'stage'
    ? 'credentialsForPilot'
    : 'credentialsFor';
const credentialsUrl = cookieMap.get(cookieName);
```
Reads credentials from cookie `credentialsFor` (or `credentialsForPilot` for staging).

---

### 4. connect.8x8.com — 8x8 Connect (CPaaS)

**Status:** 200
**CDN:** AWS CloudFront
**CSP:** `upgrade-insecure-requests; frame-ancestors 'self' *.force.com`
**Dev/Staging:** `connect-stg.wavecell.dev` (200), `app.wavecell.dev` (401)
**Tech:**
- SystemJS import maps
- Google Material Icons + Inter font
- Salesforce integration (`*.force.com`)
- Google Consent Mode v2
- UI framework: Material + Inter font

---

### 5. superx.8x8.com — Supervisor Workspace

**Status:** 302 → `/oauth2/authorization/superx-workspace`
Same OAuth2 Spring Security pattern as work.8x8.com.

---

### 6. sso.8x8.com (New Discovery)

Referenced in Jitsi config as SSO service. Not yet probed.

---

## Vulnerability Leads

| # | Finding | Target | Severity | Priority |
|---|---|---|---|---|
| 1 | **VCC jQuery 1.8.2/1.9.1** — Known CVEs (XSS, prototype pollution) | `vcc-*.8x8.com` | HIGH | Test next |
| 2 | **VCC Hardcoded CWE-798 Comment** — Possible hardcoded credentials placeholder | `vcc-*.8x8.com/AGUI/login.php` | MEDIUM | Investigate |
| 3 | **VCC Analytics Key Leak** — Hardcoded key `4541aba6a8122b2dd53c1d05e233c8da` | `vcc-*.8x8.com/AGUI/login.php` | LOW | Check |
| 4 | **OAuth2 Redirect URI Validation** — work.8x8.com and superx.8x8.com | `work.8x8.com`, `superx.8x8.com` | HIGH | Test |
| 5 | **Jitsi SSO Token Service** — Cloudflare Jitsi endpoint exposed | `api-vo.cloudflare.jitsi.net` | MEDIUM | Probe |
| 6 | **Connect Salesforce CSP** — `frame-ancestors *.force.com` | `connect.8x8.com` | MEDIUM | Test clickjacking |
| 7 | **VCC VIP Subdomains** — Internal endpoints publicly accessible | `vcc-*-vip.8x8.com`, `vcc-*b.8x8.com` | MEDIUM | Test differ |
| 8 | **8x8.vc Credentials Cookie** — Auth via cookie named `credentialsFor` | `8x8.vc` | MEDIUM | Test |
| 9 | **Spring Boot / Actuator** — Possible on work.8x8.com or voapi.8x8.com | `work.8x8.com`, `voapi.8x8.com` | MEDIUM | Probe |
| 10 | **work.8x8.com SPA Config** — `config.js` loaded before auth | `work.8x8.com/config.js` | LOW | Check |

---

## Attack Vectors

### 1. VCC Session Hijacking
VCC cookies are domain-wide (`.8x8.com`) with `samesite=none`. If XSS is achieved on any `*.8x8.com` subdomain, VCC sessions can be hijacked.

### 2. OAuth2 Authorization Code Interception
Both work.8x8.com and superx.8x8.com use Spring Security OAuth2 with redirect-based flow. Test for:
- Open redirect in `redirect_uri` parameter
- CSRF on authorization endpoint
- Code leakage via referer header

### 3. Jitsi SSO Token Forge
If the PKCE flow or JWT signing is weak, could forge meeting auth tokens via `sso.8x8.com` and `api-vo.cloudflare.jitsi.net`.

### 4. VCC PHP Vulnerabilities
Legacy PHP codebase with outdated jQuery suggests poor maintenance:
- SQL injection in login forms
- Directory traversal in static file serving
- Session fixation

### 5. Cross-Region Access
VCC has multiple regional instances (na1-30, eu2-10). Check if credentials from one region work in another.

---

## Subdomains Reference

### Discovered During Recon

| Subdomain | Status | Source |
|---|---|---|
| `work.8x8.com` | 302 | Scope |
| `work-staging.8x8.com` | — | Scope |
| `vcc-na1.8x8.com` | 200 | Brute-force |
| `vcc-na2.8x8.com` | 200 | Brute-force |
| `vcc-na3.8x8.com` | 200 | Brute-force |
| `vcc-na4.8x8.com` | 200 | Brute-force |
| `vcc-na5.8x8.com` | 200 | Brute-force |
| `vcc-na10.8x8.com` | 200 | Brute-force |
| `vcc-na20.8x8.com` | 200 | Brute-force |
| `vcc-na30.8x8.com` | 200 | Scope |
| `vcc-eu2.8x8.com` | 200 | Brute-force |
| `vcc-eu3.8x8.com` | 200 | Brute-force |
| `vcc-eu10.8x8.com` | 200 | Brute-force |
| `vcc-na30-vip.8x8.com` | 200 | CSP leak |
| `vcc-na30b.8x8.com` | 200 | CSP leak |
| `vcc-na30b-vip.8x8.com` | 200 | CSP leak |
| `voapi.8x8.com` | 403 | Scope |
| `8x8.vc` | 200 | Scope |
| `jaas.8x8.vc` | 200 | Scope |
| `connect.8x8.com` | 200 | Scope |
| `superx.8x8.com` | 302 | Scope |
| `sso.8x8.com` | — | Jitsi config |
| `developer.8x8.com` | 200 | Discovered |
| `connect-stg.wavecell.dev` | 200 | Connect staging |
| `app.wavecell.dev` | 401 | Connect dev |
| `sso.8x8pilot.com` | — | Scope |
| `uc.8x8pilot.com` | SERVFAIL | Scope (dead) |

---

## Next Steps

1. **OAuth2 redirect URI validation** — Test open redirect on work.8x8.com OAuth flow
2. **VCC deep dive** — SQL injection, directory traversal, session testing on na30
3. **Jitsi SSO analysis** — Probe `sso.8x8.com` and `api-vo.cloudflare.jitsi.net`
4. **voapi.8x8.com bypass** — Cloudflare WAF + F5 BIG-IP ASM bypass techniques
5. **VCC cookie domain abuse** — Test if VCC cookies work on other 8x8.com subdomains
6. **Connect staging** — Probe `connect-stg.wavecell.dev` and `app.wavecell.dev`
7. **Spring Boot actuator** — Check for `/actuator` on work.8x8.com and voapi.8x8.com
