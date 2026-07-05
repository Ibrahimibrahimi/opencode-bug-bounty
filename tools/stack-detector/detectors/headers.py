from detectors.base import BaseDetector


class HeaderDetector(BaseDetector):
    def detect(self, data):
        results = []
        headers = data.get("headers", {})

        for header_name, header_value in headers.items():
            hn = header_name.lower()
            hv = str(header_value)

            if hn in self.fingerprints["headers"]:
                entry = self.fingerprints["headers"][hn]
                if isinstance(entry, dict):
                    if "name" in entry and "category" in entry:
                        if not self._is_common_header(hn):
                            results.append({
                                "source": f"header:{hn}",
                                "name": entry["name"],
                                "category": entry["category"],
                                "confidence": 85,
                                "value": hv,
                            })
                    else:
                        for key, info in self._match_value(hv, entry):
                            if key.lower() in hv.lower():
                                results.append({
                                    "source": f"header:{hn}",
                                    "name": info["name"],
                                    "category": info["category"],
                                    "confidence": 90,
                                    "value": hv,
                                })

        return results

    def _is_common_header(self, hn):
        common = {
            "date", "content-type", "content-length", "connection",
            "cache-control", "pragma", "expires", "age", "vary",
            "accept-ranges", "transfer-encoding", "set-cookie",
        }
        return hn in common
