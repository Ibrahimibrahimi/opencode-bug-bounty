from detectors.base import BaseDetector


class CookieDetector(BaseDetector):
    def detect(self, data):
        results = []
        cookies = data.get("cookies", {})

        for cookie_name in cookies:
            cn = str(cookie_name).lower()
            for pattern, info in self.fingerprints["cookies"].items():
                if pattern.lower() in cn:
                    results.append({
                        "source": "cookie",
                        "name": info["name"],
                        "category": info["category"],
                        "confidence": 80,
                        "value": cookie_name,
                    })

        seen = set()
        deduped = []
        for r in results:
            key = (r["name"], r["category"])
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped
