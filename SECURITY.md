# Security Policy

## Cryptographic Guarantees

SecureCollab relies on the following cryptographic building blocks:

- **Homomorphic Encryption (CKKS):** Computations run on ciphertext; the platform never sees plaintext patient data. Only the combination of threshold key shares can decrypt results.
- **Threshold Key Generation:** The full secret key never exists in one place. Decryption requires at least `t` of `n` participants' key shares.
- **Cryptographic Commitments:** Every dataset upload is bound to a commitment hash `SHA3-256(ciphertext || public_key_fingerprint || timestamp || institution_id)`. This proves which key was used and that the data was not swapped after upload.
- **Audit Trail:** All operations are logged in an append-only, hash-chained audit trail. Each entry includes `entry_hash = SHA3-256(action_type || actor || details || timestamp || previous_hash)`. Tampering is detectable.
- **Codebase Integrity:** A deterministic hash of the deployed codebase is computed at startup and included in every audit log entry. Institutions can verify that the running instance matches a reviewed code version via `GET /system/integrity`.

- **Deserialization (pickle):** Uploaded `.bin` files are deserialized with `pickle`. Only trusted institutions upload; consider validating bundle structure before use (see `docs/OWASP_ANALYSIS.md`).

## Known Limitations

- **Side-channel attacks:** TenSEAL/SEAL are not formally hardened against all side-channel attacks. For highest assurance, consider future migration to TFHE-rs or formally verified runtimes (upstream and roadmap).
- **CKKS approximation errors:** Results are approximate (floating point). Documented per algorithm; not a security issue but relevant for interpretation.
- **No formal verification:** The application code has not undergone formal verification. Security relies on design, review, and standard library use.
- **Secret key storage (SDK):** Secret keys are protected by password-derived encryption (PBKDF2 + Fernet when `cryptography` is installed). The password never leaves the machine. Fallback uses a simpler scheme; prefer installing `cryptography` for production.

## Reporting Vulnerabilities

**Responsible disclosure:** Please do **not** report security vulnerabilities as public GitHub issues. Send details to:

**info@synapticfour.com**

- We aim to acknowledge within **48 hours** and to provide a fix or mitigation plan within **30 days** where feasible.
- We will coordinate with you before any public disclosure.

## Dependency Policy

- Dependencies are pinned in `backend/requirements.txt` (exact or minimal compatible versions).
- We run **pip-audit** (or equivalent) regularly (e.g. via CI) to check for known CVEs.
- Updates are applied after review; security-relevant patches are prioritised.

## What an External Audit Would Cover (Phase 2)

- Cryptographic design and key lifecycle.
- File upload and input validation (path traversal, size limits, allowed extensions).
- Algorithm registry and absence of code injection (no `eval`/user-supplied code execution).
- Rate limiting and denial-of-service resilience.
- Security headers and transport (TLS, HSTS in production).
- Error handling (no sensitive data or stack traces to clients).
- Dependency supply chain and CVE process.

**Honest statement:** This project has not yet undergone an independent external security audit. The above measures are implemented to follow OWASP and good practice; they do not replace a formal assessment for high-assurance deployments.
