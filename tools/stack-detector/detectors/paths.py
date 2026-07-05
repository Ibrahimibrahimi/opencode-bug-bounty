from detectors.base import BaseDetector


class PathDetector(BaseDetector):
    def detect(self, data):
        results = []
        found_paths = data.get("found_paths", {})

        for path, status in found_paths.items():
            pl = path.lower()
            for pattern, info in self.fingerprints["paths"].items():
                if pl == pattern.lower().rstrip("/") or (
                    pattern.endswith("/") and pl.startswith(pattern.lower().rstrip("/"))
                ):
                    results.append({
                        "source": "path",
                        "name": info["name"],
                        "category": info["category"],
                        "confidence": info["confidence"],
                        "value": f"{path} (HTTP {status})",
                    })
                    break

        seen = set()
        deduped = []
        for r in results:
            key = (r["name"], r["category"])
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped
