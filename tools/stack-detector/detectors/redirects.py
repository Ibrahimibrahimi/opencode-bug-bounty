from detectors.base import BaseDetector


class RedirectDetector(BaseDetector):
    def detect(self, data):
        results = []
        chain = data.get("redirect_chain", [])

        for i, hop in enumerate(chain):
            results.append({
                "source": "redirect",
                "name": f"Redirect {i + 1}",
                "category": "redirect",
                "confidence": 100,
                "value": f"{hop.get('status_code', '?')} {hop.get('url', '?')}",
                "extra": {
                    "hop": i + 1,
                    "url": hop.get("url"),
                    "status": hop.get("status_code"),
                    "headers": dict(hop.get("headers", {})),
                },
            })

        if chain:
            first = chain[0]["url"]
            last = chain[-1]["url"]
            hops = len(chain)

            results.append({
                "source": "redirect_summary",
                "name": "Redirect Chain Summary",
                "category": "redirect",
                "confidence": 100,
                "value": f"{first} -> {last} ({hops} hop{'s' if hops > 1 else ''})",
                "extra": {
                    "total_hops": hops,
                    "start_url": first,
                    "final_url": last,
                    "chain": [
                        {"hop": i + 1, "url": h["url"], "status": h.get("status_code")}
                        for i, h in enumerate(chain)
                    ],
                },
            })

            if hops > 5:
                results.append({
                    "source": "redirect_warning",
                    "name": "Long Redirect Chain",
                    "category": "seo",
                    "confidence": 100,
                    "value": f"{hops} redirect hops — may impact SEO and load time",
                })

            statuses = [h.get("status_code") for h in chain]
            if 302 in statuses:
                results.append({
                    "source": "redirect_type",
                    "name": "Temporary Redirect (302)",
                    "category": "redirect",
                    "confidence": 100,
                    "value": "Found at hop " + str(statuses.index(302) + 1),
                })
            if 301 in statuses:
                results.append({
                    "source": "redirect_type",
                    "name": "Permanent Redirect (301)",
                    "category": "redirect",
                    "confidence": 100,
                    "value": "Found at hop " + str(statuses.index(301) + 1),
                })
            if 307 in statuses:
                results.append({
                    "source": "redirect_type",
                    "name": "Temporary Redirect (307)",
                    "category": "redirect",
                    "confidence": 100,
                    "value": "Found at hop " + str(statuses.index(307) + 1),
                })
            if 308 in statuses:
                results.append({
                    "source": "redirect_type",
                    "name": "Permanent Redirect (308)",
                    "category": "redirect",
                    "confidence": 100,
                    "value": "Found at hop " + str(statuses.index(308) + 1),
                })

            if any(h.get("url", "").startswith("https://") for h in chain):
                http_only = all(not h.get("url", "").startswith("https://") for h in chain)
                if http_only:
                    chain_has_https = [h for h in chain if h.get("url", "").startswith("https://")]
                    if chain_has_https:
                        results.append({
                            "source": "redirect_upgrade",
                            "name": "HTTPS Upgrade Detected",
                            "category": "security",
                            "confidence": 100,
                            "value": "HTTP -> HTTPS redirect at hop " + str(chain.index(chain_has_https[0]) + 1),
                        })
                else:
                    no_https = [h for h in chain if not h.get("url", "").startswith("https://")]
                    if not no_https:
                        pass

            for i, h in enumerate(chain):
                loc = dict(h.get("headers", {})).get("location", "")
                if "://" in loc and h.get("url", "") and loc != h["url"]:
                    if loc.split("://")[1].split("/")[0] != h["url"].split("://")[1].split("/")[0]:
                        results.append({
                            "source": "redirect_cross_domain",
                            "name": "Cross-Domain Redirect",
                            "category": "redirect",
                            "confidence": 100,
                            "value": f"Hop {i + 1}: {h['url']} -> {loc}",
                        })

        return results
