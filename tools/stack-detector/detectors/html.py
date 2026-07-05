import re
from detectors.base import BaseDetector


class HTMLDetector(BaseDetector):
    def detect(self, data):
        results = []
        html = data.get("html", "")
        soup = data.get("soup")

        meta_generator = self._find_meta_generator(soup, html)
        if meta_generator:
            for info in self._match_value(meta_generator, self.fingerprints["html"]["generator"]):
                results.append({
                    "source": "meta:generator",
                    "name": info["name"],
                    "category": info["category"],
                    "confidence": 85,
                    "value": meta_generator,
                })

        if soup:
            for tag in soup.find_all(["script", "link", "img", "source"]):
                src = tag.get("src", "") or tag.get("href", "") or ""
                for pattern, info in self.fingerprints["html"]["script_src"].items():
                    if re.search(pattern, src, re.I):
                        results.append({
                            "source": "script_src",
                            "name": info["name"],
                            "category": info["category"],
                            "confidence": 80,
                            "value": src,
                        })

            for tag in soup.find_all(class_=True):
                classes = " ".join(tag.get("class", []))
                for pattern, info in self.fingerprints["html"]["body_class"].items():
                    if pattern.lower() in classes.lower():
                        results.append({
                            "source": "html:class",
                            "name": info["name"],
                            "category": info["category"],
                            "confidence": 75,
                            "value": classes[:100],
                        })

            attrs_inspected = set()
            for tag in soup.find_all(True):
                for attr in tag.attrs:
                    if attr in attrs_inspected:
                        continue
                    attrs_inspected.add(attr)
                    if attr in self.fingerprints["dom"]:
                        info = self.fingerprints["dom"][attr]
                        val = str(tag.get(attr, ""))[:100]
                        results.append({
                            "source": f"dom:attr:{attr}",
                            "name": info["name"],
                            "category": info["category"],
                            "confidence": 90,
                            "value": val,
                        })

        for attr_name in self.fingerprints["html"]["meta_specific"]:
            found = self._find_meta_property(soup, html, attr_name)
            if found:
                results.append({
                    "source": f"meta:{attr_name}",
                    "name": self.fingerprints["html"]["meta_specific"][attr_name]["name"],
                    "category": self.fingerprints["html"]["meta_specific"][attr_name]["category"],
                    "confidence": 70,
                    "value": found,
                })

        seen_src = set()
        deduped = []
        for r in results:
            key = (r["name"], r["category"])
            if key not in seen_src:
                seen_src.add(key)
                deduped.append(r)
        return deduped

    def _find_meta_generator(self, soup, html):
        if soup:
            for meta in soup.find_all("meta"):
                n = (meta.get("name") or "").lower()
                if n == "generator":
                    return meta.get("content", "")
                p = (meta.get("property") or "").lower()
                if p == "generator":
                    return meta.get("content", "")
        m = re.search(r'<meta[^>]+(?:name|property)\s*=\s*["\']generator["\'][^>]*content\s*=\s*["\']([^"\']+)', html, re.I)
        return m.group(1) if m else None

    def _find_meta_property(self, soup, html, prop_name):
        if soup:
            for meta in soup.find_all("meta"):
                n = (meta.get("name") or "").lower()
                p = (meta.get("property") or "").lower()
                if n == prop_name.lower() or p == prop_name.lower():
                    return meta.get("content", "")
        m = re.search(
            rf'<meta[^>]+(?:name|property)\s*=\s*["\']{re.escape(prop_name)}["\'][^>]*content\s*=\s*["\']([^"\']+)',
            html, re.I
        )
        return m.group(1) if m else None
