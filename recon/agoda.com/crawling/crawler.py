import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import time
import re
import json

TARGET = "https://www.agoda.com/book/"
MAX_URLS = 100
MAX_DEPTH = 20
DELAY = 1
OUTPUT = "recon/agoda.com/crawling/crawled_urls.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "X-Bug-Bounty": "HackerOne-agoda-hunter",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SKIP_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".css", ".woff", ".woff2", ".ttf", ".pdf", ".zip", ".js")
SKIP_PATTERNS = (".onetrust", "cdn6.agoda.net", "cdn.agoda.net", "cdn2.agoda.net", "beacon.riskified", "bento.agoda.com")

def is_same_domain(url, base_domain):
    return urlparse(url).netloc.endswith(base_domain)

def clean_url(url):
    url = url.strip().strip('"').strip("'")
    if "\\u0026" in url:
        url = url.replace("\\u0026", "&")
    url = url.split("\\u0022")[0]
    url = urldefrag(url)[0]
    return url

def extract_api_routes(html):
    routes = set()
    patterns = [
        r'/api/[a-zA-Z0-9_/.-]+',
        r'/v[0-9]/[a-zA-Z0-9_/.-]+',
        r'/graphql',
        r'/rest/[a-zA-Z0-9_/.-]+',
    ]
    for pat in patterns:
        for m in re.finditer(pat, html):
            routes.add(m.group())
    return routes

def extract_json_urls(text):
    urls = set()
    for m in re.finditer(r'https?://[^"\'\\\s,>)]+', text):
        u = m.group()
        if any(p in u for p in SKIP_PATTERNS):
            continue
        if is_same_domain(u, "agoda.com") or is_same_domain(u, "www.agoda.com"):
            u = clean_url(u.split("\\u")[0])
            if not u.lower().endswith(SKIP_EXTS):
                urls.add(u)
    return urls

def crawl():
    visited = set()
    found_urls = set()
    queue = [(TARGET, 0)]
    base_domain = urlparse(TARGET).netloc

    print(f"[*] Starting crawl: {TARGET}")
    print(f"[*] Max depth: {MAX_DEPTH}, Max URLs: {MAX_URLS}")

    while queue and len(visited) < MAX_URLS:
        url, depth = queue.pop(0)
        if url in visited:
            continue
        if depth > MAX_DEPTH:
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            visited.add(url)
            actual_url = resp.url
            if actual_url != url:
                visited.add(actual_url)

            # Extract URLs from page source
            page_urls = extract_json_urls(resp.text)
            for u in page_urls:
                if u not in visited and len(visited) < MAX_URLS:
                    found_urls.add(u)
                    if depth < MAX_DEPTH and is_same_domain(u, base_domain):
                        queue.append((u, depth + 1))

            # Extract API routes
            apis = extract_api_routes(resp.text)
            for a in apis:
                full = "https://www.agoda.com" + a
                if full not in visited:
                    found_urls.add(full)

            print(f"[{len(visited):>3}/{MAX_URLS}] depth={depth} {resp.status_code} {actual_url} ({len(page_urls)} urls found)")

            # Parse HTML for links too
            if "text/html" in (resp.headers.get("Content-Type", "") or ""):
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup.find_all(["a", "link", "form", "iframe"]):
                    href = tag.get("href") or tag.get("src") or tag.get("action")
                    if not href:
                        continue
                    full = urljoin(actual_url, href)
                    if not full.startswith("http"):
                        continue
                    full = urldefrag(full)[0]
                    if not is_same_domain(full, base_domain):
                        continue
                    if full.lower().endswith(SKIP_EXTS):
                        continue
                    if any(p in full for p in SKIP_PATTERNS):
                        continue
                    if full not in visited and len(visited) < MAX_URLS:
                        found_urls.add(full)
                        queue.append((full, depth + 1))

            time.sleep(DELAY)

        except Exception as e:
            print(f"[!] Error: {url} -> {e}")
            visited.add(url)
            continue

    all_urls = sorted(visited | found_urls)
    with open(OUTPUT, "w") as f:
        for u in all_urls:
            f.write(u + "\n")

    print(f"\n[*] Done. {len(all_urls)} URLs saved to {OUTPUT}")
    print("[*] Sample URLs:")
    for u in all_urls[:20]:
        print(f"    {u}")

if __name__ == "__main__":
    crawl()
