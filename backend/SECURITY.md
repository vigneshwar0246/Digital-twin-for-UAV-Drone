# Prototype security architecture

This is production-oriented application scaffolding for a prototype. It is not
defence-certified, airworthiness-approved, or a substitute for an organizational
identity and security architecture.

## Authentication and authorization

Clients obtain a time-limited signed bearer token from `POST /api/v1/auth/token`.
Passwords are stored as randomly salted PBKDF2-HMAC-SHA256 hashes (310,000
iterations); plaintext passwords are neither stored nor included in tokens or
audit events. Tokens are HMAC-SHA256 signed and contain subject, role, issue and
expiry times, issuer, and a unique token ID.

Roles have the following access:

| Role | Primary permissions |
|---|---|
| `ADMIN` | User administration, audit records, and all API operations |
| `OPERATOR` | Telemetry/adapter ingestion, simulation and replay control, operational reads |
| `MAINTENANCE_ENGINEER` | Engine/report reads, model report, adapter health |
| `ANALYST` | Engine/report reads, simulation/replay, model report |
| `VIEWER` | Read-only engine, mission, replay, and report access |

Health, readiness, demo status, and token acquisition are intentionally public. Other routes require a bearer token when `DIGITAL_TWIN_DEMO_MODE=false`. Demo mode deliberately bypasses route authorization for a local presentation; do not enable it on a network-accessible or production service. Authorization remains server-side outside demo mode; UI controls must not be treated as an access boundary.

Every response has `X-Request-ID`. A valid caller-supplied ID is preserved;
otherwise a UUID is generated. Request audits include timestamp, request ID,
authenticated actor and role when known, route, status, event type, and client
address. The SQLite audit trail is useful for the demonstrator but is not an
immutable compliance log.

## Configuration

Development defaults to a 30-minute token lifetime and 120 protected requests
per user/route/minute. If no development secret is supplied, startup creates an
ephemeral secret, so tokens become invalid after restart.

```powershell
$env:DIGITAL_TWIN_ENV = "development"
$env:DIGITAL_TWIN_TOKEN_SECRET = "replace-with-at-least-32-random-characters"
$env:DIGITAL_TWIN_TOKEN_MINUTES = "30"
$env:DIGITAL_TWIN_RATE_LIMIT = "120"
$env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME = "admin"
$env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD = "use-a-strong-unique-password"
```

The bootstrap account is created only when the database has no users. Remove
the bootstrap password from the environment immediately after provisioning.
The Windows demo launcher no longer supplies a fixed bootstrap password or token secret, and the frontend no longer embeds development login credentials. A former fixed development password exists in Git history; rotate any account or secret that reused it. The demo launcher intentionally bypasses authorization on loopback and is unsuitable for network exposure.
Production mode refuses startup without a persistent secret of at least 32
characters:

```powershell
$env:DIGITAL_TWIN_ENV = "production"
$env:DIGITAL_TWIN_TOKEN_SECRET = "a-high-entropy-secret-from-a-secret-manager"
```

The in-process rate limiter is a replaceable hook, not a distributed control.
Multiple workers require a shared, atomic rate-limit store.

Research ML is disabled by default with `AERION_ENABLE_ML_DIAGNOSTICS=0`. Development use of the release-failing candidate also requires `DIGITAL_TWIN_ML_ALLOW_UNVALIDATED=true`; production rejects that override. The runtime loader accepts only the known repository artifact after checksum and metadata checks. Its uncalibrated output is identified as research evidence, not a safety-approved probability or diagnosis. See the [backend guide](README.md) for the diagnostic contract.

## Required future security work

Before operational deployment, provide and validate:

- an approved identity provider and lifecycle/provisioning process;
- multi-factor authentication;
- centralized key management, rotation, revocation, and certificate authentication;
- hardware-backed keys for sensitive identities and signing operations;
- secure telemetry signing with anti-replay protection;
- encrypted transport (TLS/mTLS) across every telemetry and API boundary;
- organizational/fleet RBAC integration and separation-of-duty policy;
- shared rate limiting, token revocation/session controls, and abuse monitoring;
- immutable, access-controlled audit export and SIEM integration;
- independent threat modelling, penetration testing, and applicable certification review.
