import json
import os
import re


class BaseDetector:
    def __init__(self):
        self.fingerprints = self._load_fingerprints()

    def _load_fingerprints(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fingerprints.json")
        with open(path) as f:
            return json.load(f)

    def _match_value(self, value, patterns):
        if isinstance(patterns, dict):
            for key, info in patterns.items():
                if key.lower() in str(value).lower():
                    yield info
        elif isinstance(patterns, list):
            for p in patterns:
                if re.search(p, str(value), re.I):
                    yield {"name": p, "category": "unknown"}

    def detect(self, data):
        raise NotImplementedError
