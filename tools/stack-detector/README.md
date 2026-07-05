# StackDetector

Identify what a website is built with — frameworks, languages, CDNs, CMS, analytics, and more. Tracks redirect chains, probes common paths, and fingerprints responses from headers, HTML, cookies, and error pages.

## Features

- **Header analysis** — Server, X-Powered-By, X-Generator, cache headers (CF-Ray, X-Varnish, Via, etc.)
- **HTML/JS fingerprinting** — Meta generator, script sources, DOM attributes (React root, Next.js data, Vue SSR, etc.), CSS frameworks, analytics, payment providers
- **Cookie analysis** — Session cookies (PHPSESSID, JSESSIONID, laravel_session, etc.), CDN/WAF cookies (cf_clearance, incap_ses_, etc.)
- **Path probing** — Detects CMS paths, exposed config files, admin panels, API endpoints, and vulnerable paths
- **Redirect chain tracking** — Follows 301/302/307/308 chains, detects HTTPS upgrades, cross-domain redirects, and long chains
- **Error page fingerprinting** — Matches server signatures in 403/404/500 error pages
- **Batch scanning** — Supply a file with one URL per line
- **JSON output** — Machine-readable reports with confidence scoring

## Quick Start

```bash
pip install -r requirements.txt

# Single target
python stackdetect.py example.com

# Verbose with source info
python stackdetect.py https://example.com -v

# Batch scan from file
python stackdetect.py urls.txt -o reports/

# JSON output
python stackdetect.py example.com --json

# Custom probe limit
python stackdetect.py example.com --max-probe 20

# Custom User-Agent
python stackdetect.py example.com --user-agent "MyBot/1.0"
```

## Output

```
============================================================
  StackDetect Report
============================================================
  Target:     https://example.com
  Final URL:  https://www.example.com
  Status:     200
  Server:     cloudflare

  Technology Stack
  ────────────────────────────────────────────────────────
  ⚙ Express.js          framework            90% (header:X-Powered-By)
  🔤 PHP                language             80% (header:X-Powered-By)
  ☁ Cloudflare          cdn                  95% (header:cf-ray)
  🖥 Nginx              server               85% (header:server)
  📝 WordPress          cms                  85% (meta:generator)
  📊 Google Analytics   analytics            80% (cookie:_ga)
  🛡 HSTS               security            100% (header:strict-transport-security)

  Redirect Analysis
  ──────────────────────────────
  https://example.com -> https://www.example.com (1 hop)
  ⤷ HTTPS Upgrade Detected: HTTP -> HTTPS redirect at hop 1
```

## Fingerprint Database

All fingerprints live in `fingerprints.json`. Add or override entries without touching the code:

```json
{
  "headers": {
    "x-my-custom-header": {
      "MyFramework": {"name": "MyFramework", "category": "framework"}
    }
  }
}
```

## Options

| Flag | Description |
|------|-------------|
| `target` | URL, domain, or `.txt` file with URLs |
| `-v` | Verbose — show detection source |
| `--json` | JSON output |
| `-o PATH` | Save report to file or directory |
| `--no-probe` | Disable path probing |
| `--max-probe N` | Max paths to probe (0 = all) |
| `--timeout N` | Request timeout (default 15s) |
| `--max-redirects N` | Max redirect hops (default 10) |
| `--user-agent UA` | Custom User-Agent |
