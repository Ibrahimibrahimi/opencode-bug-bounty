import re
from detectors.base import BaseDetector


class ErrorPageDetector(BaseDetector):
    def detect(self, data):
        results = []
        error_body = data.get("error_body", "")
        status = data.get("status_code", 0)

        if status not in (403, 404, 500, 502, 503) or not error_body:
            return results

        for _, info in self.fingerprints["error_pages"].items():
            for p in info.get("patterns", []):
                if re.search(p, error_body, re.I):
                    results.append({
                        "source": "error_page",
                        "name": info["name"],
                        "category": info["category"],
                        "confidence": 75,
                        "value": f"HTTP {status} — matched pattern: {p}",
                    })
                    break

        return results
