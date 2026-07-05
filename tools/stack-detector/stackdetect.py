#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urlparse, urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install -r requirements.txt")
    sys.exit(1)

from detectors.headers import HeaderDetector
from detectors.html import HTMLDetector
from detectors.cookies import CookieDetector
from detectors.paths import PathDetector
from detectors.redirects import RedirectDetector
from detectors.errors import ErrorPageDetector


class StackDetect:
    def __init__(self, timeout=15, max_redirects=10, headers=None):
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.session = requests.Session()
        self.session.headers.update(headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.session.max_redirects = 0

        self.detectors = [
            HeaderDetector(),
            HTMLDetector(),
            CookieDetector(),
            PathDetector(),
            RedirectDetector(),
            ErrorPageDetector(),
        ]

        self.common_paths = [
            "/robots.txt", "/sitemap.xml", "/.env", "/wp-admin/",
            "/wp-content/", "/wp-json/", "/administrator/", "/admin/",
            "/.git/config", "/server-status", "/actuator/health",
            "/graphql", "/swagger.json", "/swagger-ui/", "/api/",
            "/phpmyadmin/", "/vendor/", "/composer.json", "/package.json",
            "/security.txt", "/.well-known/security.txt",
        ]

    def run(self, url, probe_paths=True, probe_count=0):
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url

        print(f"[*] Scanning: {url}")
        print()

        redirect_chain = []
        final_response = self._follow_redirects(url, redirect_chain)
        if final_response is None:
            return

        data = {
            "url": url,
            "final_url": final_response.url,
            "status_code": final_response.status_code,
            "headers": dict(final_response.headers),
            "cookies": dict(final_response.cookies),
            "html": final_response.text,
            "soup": BeautifulSoup(final_response.text, "html.parser"),
            "redirect_chain": redirect_chain,
            "error_body": final_response.text if final_response.status_code >= 400 else "",
        }

        if probe_paths:
            data["found_paths"] = self._probe_paths(url, probe_count)

        all_results = []
        for detector in self.detectors:
            try:
                all_results.extend(detector.detect(data))
            except Exception as e:
                print(f"  [!] {detector.__class__.__name__}: {e}", file=sys.stderr)

        return self._build_report(url, final_response, all_results, redirect_chain)

    def _follow_redirects(self, url, chain):
        seen = set()
        current = url
        for _ in range(self.max_redirects + 1):
            if current in seen:
                break
            seen.add(current)
            try:
                resp = self.session.get(current, timeout=self.timeout, allow_redirects=False)
                chain.append({
                    "url": current,
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                })
                if resp.status_code in (301, 302, 303, 307, 308):
                    loc = resp.headers.get("location", "")
                    if not loc:
                        return resp
                    current = urljoin(current, loc)
                    continue
                return resp
            except requests.RequestException as e:
                print(f"  [!] Request failed: {e}", file=sys.stderr)
                return None
        print(f"  [!] Too many redirects (>{self.max_redirects})", file=sys.stderr)
        return None


    def _probe_paths(self, base_url, max_count=0):
        found = {}
        paths = self.common_paths

        if max_count > 0:
            paths = paths[:max_count]

        for path in paths:
            url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=False)
                if resp.status_code != 404:
                    found[path] = resp.status_code
            except requests.RequestException:
                pass

        return found

    def _build_report(self, url, response, results, redirect_chain):
        tech = {}
        security = []
        redirects = []
        anomalies = []

        for r in results:
            entry = {
                "name": r["name"],
                "category": r["category"],
                "confidence": r["confidence"],
                "source": r["source"],
                "value": r.get("value", ""),
            }
            if r["category"] == "redirect":
                redirects.append(entry)
                if "extra" in r:
                    entry["extra"] = r["extra"]
            elif r["category"] in ("security", "vulnerability", "waf"):
                security.append(entry)
            else:
                key = r["name"]
                if key not in tech or r["confidence"] > tech[key]["confidence"]:
                    tech[key] = entry

        return {
            "target": url,
            "final_url": response.url,
            "status": response.status_code,
            "server": response.headers.get("Server", ""),
            "technology_stack": tech,
            "security": security,
            "redirects": redirects,
            "anomalies": anomalies,
        }


def print_report(report, verbose=False):
    print("=" * 60)
    print(f"  StackDetect Report")
    print("=" * 60)
    print(f"  Target:     {report['target']}")
    print(f"  Final URL:  {report['final_url']}")
    print(f"  Status:     {report['status']}")
    if report["server"]:
        print(f"  Server:     {report['server']}")
    print()

    tech = report.get("technology_stack", {})
    if tech:
        print(f"  {'Technology Stack':<30} {'Category':<20} {'Conf':<6}")
        print(f"  {'─' * 56}")
        by_cat = {}
        for name, info in sorted(tech.items(), key=lambda x: x[1]["category"]):
            by_cat.setdefault(info["category"], []).append((name, info))
        for cat in sorted(by_cat.keys()):
            items = by_cat[cat]
            for name, info in items:
                icon = {"framework": "⚙", "language": "🔤", "cdn": "☁", "server": "🖥",
                        "cms": "📝", "ecommerce": "🛒", "css-framework": "🎨",
                        "library": "📦", "analytics": "📊", "paas": "☁",
                        "cache": "💾", "lb": "⚖", "waf": "🛡", "api-gateway": "🚪",
                        "cloud": "☁", "website-builder": "🔧", "ssg": "🏗",
                        "page-builder": "🧩", "payment": "💳", "service": "🔌",
                        "seo": "🔍", "security": "🔒", "cors": "🌐", "panel": "📋",
                        "dev": "🛠", "config": "⚙", "api": "🔗", "auth": "🔑",
                        "standard": "📄", "compliance": "📋", "proxy": "🔀",
                        "editor": "✏", "unknown": "❓"}.get(cat, "  ")
                name_display = info["name"]
                conf = f"{info['confidence']}%"
                via = f" ({info['source']})" if verbose else ""
                print(f"  {icon} {name_display:<28} {cat:<20} {conf:<5}{via}")
            print()

    if report.get("redirects"):
        print(f"  {'Redirect Analysis':<30}")
        print(f"  {'─' * 30}")
        for r in report["redirects"]:
            if r["source"] == "redirect_summary":
                print(f"  {r['value']}")
                if verbose and "extra" in r:
                    for hop in r["extra"].get("chain", []):
                        print(f"    Hop {hop['hop']}: HTTP {hop['status']} {hop['url']}")
            elif r["source"] == "redirect":
                pass
            else:
                print(f"  ⤷ {r['name']}: {r['value']}")
        print()

    if report.get("security"):
        print(f"  {'Security & Anomalies':<30}")
        print(f"  {'─' * 30}")
        for s in report["security"]:
            print(f"  {'⚠' if s['category'] == 'vulnerability' else '🔒'} {s['name']:<35} {s['value'][:80]}")
        print()

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="StackDetect — Identify website technology stacks and detect redirect chains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python stackdetect.py example.com
  python stackdetect.py https://example.com -v
  python stackdetect.py https://example.com --probe
  python stackdetect.py https://example.com --json
  python stackdetect.py list.txt -o reports/
  python stackdetect.py https://example.com --probe --max-probe 50
        """,
    )
    parser.add_argument("target", help="URL, domain, or path to a file with URLs (one per line)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed source info")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-o", "--output", help="Save report to file (or directory for batch)")
    parser.add_argument("--probe", action="store_true", default=True, help="Probe common paths (default: on)")
    parser.add_argument("--no-probe", action="store_true", help="Disable path probing")
    parser.add_argument("--max-probe", type=int, default=0, help="Max paths to probe (0 = all)")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--max-redirects", type=int, default=10, help="Max redirect hops to follow")
    parser.add_argument("--user-agent", help="Custom User-Agent header")

    args = parser.parse_args()

    headers = {}
    if args.user_agent:
        headers["User-Agent"] = args.user_agent

    detector = StackDetect(
        timeout=args.timeout,
        max_redirects=args.max_redirects,
        headers=headers or None,
    )

    probe = not args.no_probe

    targets = []
    if args.target.startswith("http://") or args.target.startswith("https://") or "." in args.target:
        if args.target.endswith(".txt"):
            try:
                with open(args.target) as f:
                    targets = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except FileNotFoundError:
                print(f"File not found: {args.target}")
                sys.exit(1)
        else:
            targets = [args.target]
    else:
        try:
            with open(args.target) as f:
                targets = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except FileNotFoundError:
            targets = [args.target]

    for t in targets:
        report = detector.run(t, probe_paths=probe, probe_count=args.max_probe)
        if report is None:
            continue

        if args.json:
            output = json.dumps(report, indent=2)
            if args.output:
                if len(targets) > 1:
                    safe = re.sub(r'[^a-zA-Z0-9.-]', '_', report["target"])
                    fpath = f"{args.output.rstrip('/')}/{safe}.json"
                    with open(fpath, "w") as f:
                        f.write(output)
                    print(f"Saved: {fpath}")
                else:
                    with open(args.output, "w") as f:
                        f.write(output)
                    print(f"Saved: {args.output}")
            else:
                print(output)
        else:
            print_report(report, verbose=args.verbose)

        if args.output and not args.json and len(targets) == 1:
            safe = re.sub(r'[^a-zA-Z0-9.-]', '_', report["target"])
            fpath = args.output if args.output.endswith(".txt") else f"{args.output.rstrip('/')}/{safe}.txt"
            d = os.path.dirname(fpath)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(fpath, "w") as f:
                f.write(json.dumps(report, indent=2))
            print(f"Saved: {fpath}")

        if len(targets) > 1:
            print()


if __name__ == "__main__":
    main()
