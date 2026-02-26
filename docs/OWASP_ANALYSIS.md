# OWASP Security Analysis

Periodic review of SecureCollab against OWASP Top 10 and related checks. Last updated: 2025-02.

---

## A01 Broken Access Control

| Check | Status | Notes |
|-------|--------|------|
| Study/Job/Dataset access by ID | OK | No auth; IDs are opaque. In production add authz (e.g. participant must belong to study). |
| File path traversal | OK | `secure_filename()` and `resolve()` + `relative_to(uploads)` prevent path traversal on uploads. |
| Direct object reference | Mitigated | IDs are integers; no sensitive data in URL. Rate limiting on upload/approve reduces enumeration. |

---

## A02 Cryptographic Failures

| Check | Status | Notes |
|-------|--------|------|
| Secret key storage (SDK) | OK | PBKDF2 (600k iterations) + Fernet; password never leaves machine; chmod 0o600. |
| TLS | Config | Enforced via HSTS in production (`SECURECOLLAB_PRODUCTION`). |
| Sensitive data in logs | OK | No passwords or raw ciphertext in logs; exception messages not sent to client (see A09). |

---

## A03 Injection

| Check | Status | Notes |
|-------|--------|------|
| SQL injection | OK | SQLModel/ORM only; raw `text()` only for fixed ALTER TABLE list (no user input). |
| Algorithm injection | OK | `ALGORITHM_REGISTRY` single source of truth; request algorithm validated against registry; no `eval`/user code. |
| Command injection | OK | `subprocess.run(["git", ...])` with fixed args only; no user input. |
| Deserialization (pickle) | Risk | Uploaded `.bin` files are `pickle.load()`ed. **Mitigation:** Only trusted institutions upload; server does not re-serve pickles to others. Consider signing/validating bundle structure before use. |

---

## A04 Insecure Design

| Check | Status | Notes |
|-------|--------|------|
| Rate limiting | OK | slowapi on upload (10/h), job request (30/h), approve (60/h), integrity (100/h). |
| Computation queue | Partial | `MAX_CONCURRENT_COMPUTATIONS` documented; full FIFO queue not implemented. |

---

## A05 Security Misconfiguration

| Check | Status | Notes |
|-------|--------|------|
| Security headers | OK | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, CSP; HSTS in production. |
| CORS | OK | Configurable via `ALLOWED_ORIGINS`; no wildcard in production when set. |
| Default credentials | OK | No default passwords; `SECRET_KEY` has dev default only (documented). |

---

## A06 Vulnerable Components

| Check | Status | Notes |
|-------|--------|------|
| Pinned versions | OK | `requirements.txt` pins exact versions. |
| CVE scanning | OK | GitHub Actions `pip-audit` (security.yml) and optional npm audit. |

---

## A07 Auth Failures

| Check | Status | Notes |
|-------|--------|------|
| Authentication | N/A (Phase 0) | No user auth; identity is email/institution in request. Phase 1 should add auth. |
| Session/secret key | OK | No server-side sessions; SDK secret key stored with password-derived encryption. |

---

## A08 Software and Data Integrity

| Check | Status | Notes |
|-------|--------|------|
| Audit chain | OK | Hash-chained; tampering detectable. |
| Codebase hash | OK | In audit and `/system/integrity`; deterministic. |
| Pickle integrity | Mitigated | Bundles from participants; consider HMAC or structure validation. |

---

## A09 Logging and Monitoring / Information Disclosure

| Check | Status | Notes |
|-------|--------|------|
| Error messages to client | OK | 500 returns generic message + `error_id`; exception details only in server logs. |
| Stack traces | OK | Not returned to client. |
| Logging of failures | OK | HE computation failures logged with job/study id. |

---

## A10 Server-Side Request Forgery (SSRF)

| Check | Status | Notes |
|-------|--------|------|
| Outbound requests | Minimal | Integrity module runs `git` locally; no user-controlled URLs. |

---

## Dead Code

| Item | Location | Action |
|------|----------|--------|
| Legacy monolith | `backend/main.py` | ~1800 lines; not used when running `uvicorn app.main:app`. Kept for reference or remove once migration is final. |
| Custom exceptions | `app/core/exceptions.py` | `ValidationError`, `NotFoundError`, `AlgorithmNotAllowedError` defined but not used. Reserved for future; or use in routers and map to HTTP in handler. |
| StudyUploadDatasetForm | `app/schemas.py` | Defined, never referenced. Reserved for future or remove. |

---

## Inefficient Code (addressed)

| Issue | Location | Fix |
|-------|----------|-----|
| N+1 queries | `studies_list` | Replaced per-study participant/dataset/pending counts with batched aggregates (3 grouped queries + studies by id). |

---

## Recommendations

1. **Pickle:** Validate deserialized bundle structure (required keys, types) before passing to HE; reject malformed payloads.
2. **Auth (Phase 1):** Add authentication and enforce “participant of study” for study-scoped actions.
3. **Computation queue:** Implement FIFO queue when `MAX_CONCURRENT_COMPUTATIONS` is reached; set job status to `queued` until a slot is free.
