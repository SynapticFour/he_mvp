# SPDX-License-Identifier: Apache-2.0

# Architecture

Key design decisions for SecureCollab.

## Why FastAPI over Django/Flask

- **Async support** for I/O-bound operations (file uploads, external calls later).
- **OpenAPI out of the box** for SDK and frontend code generation.
- **Lightweight** and easy to wrap in a thin app factory for testing and deployment.
- **Type hints** and Pydantic integrate well with our config and request/response models.

## Why SQLite for Phase 0, PostgreSQL for Phase 1

- **Phase 0:** SQLite keeps setup minimal; no separate DB server. Single file, easy backup. Sufficient for demos and small multi-party trials.
- **Phase 1:** Switch by changing `DATABASE_URL` to a PostgreSQL connection string. SQLModel/SQLAlchemy work with both; no application code change. PostgreSQL gives concurrency, replication, and compliance-friendly tooling.

## Why TenSEAL/CKKS over TFHE

- **Floating point:** Clinical and GWAS data are continuous (lab values, dosages). CKKS supports approximate arithmetic on reals.
- **TFHE** is for exact integer/binary circuits; better for discrete logic, worse for statistics and regression.
- **Performance:** CKKS is orders of magnitude faster for large vectors; we need to run many scalar ops per column.

## Why the SDK is a separate installable package

- **Institutions** run the SDK on their own machines; it must install with `pip install ./sdk` without pulling the full backend.
- **Clear boundary:** Crypto and API client live in one package; the server never sees plaintext. Versioning the SDK independently allows safe upgrades.

## Router/service split: why business logic is not in routers

- **Routers** handle HTTP: validation, status codes, request/response shape. They call services and return results.
- **Services** hold all TenSEAL, audit, integrity, and schema logic. They are testable without FastAPI and reusable from jobs or CLI.
- **Single responsibility:** Changing an algorithm or the audit format does not touch route definitions.

## Why config comes entirely from environment variables

- **12-factor app:** Config varies per environment; no hardcoded paths or secrets. Same image can run in dev/staging/prod.
- **Secrets:** Keys and DB URLs are set in `.env` or the orchestrator; never in code or in repo.
- **Pydantic Settings** validates types and required fields at startup and documents env names in one place.

## Data flow: what is encrypted at each step

1. **Institution (SDK):** Raw CSV → encrypted per-column CKKS vectors → `.bin` bundle. Commitment = hash(ciphertext || public_key_fingerprint || timestamp || institution_id). Only ciphertext and commitment leave the machine.
2. **Upload:** Server stores `.bin` and commitment; never sees plaintext.
3. **Computation:** Server runs HE algorithms on ciphertext; result is still encrypted (or partially decrypted in threshold model).
4. **Result release:** After threshold decryption shares are submitted, the result is combined and returned. Server never sees raw data; only aggregated result after release.

```
[Institution] --(ciphertext + commitment)--> [Server] --(HE compute)--> [Encrypted result]
                                                                              |
[Institution] <--(decryption share)-------------------------------------------+
     + other institutions' shares => combined plaintext result
```
