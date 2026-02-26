# SecureCollab

Multi-party clinical data analysis using Homomorphic Encryption — compute statistics across encrypted datasets from multiple institutions without any party seeing each other's raw data.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Status

This is a hobby project / proof of concept. It demonstrates the full cryptographic concept with real HE (TenSEAL/CKKS), a working multi-party workflow, and a usable web UI. It has not undergone a formal security audit. It is not production-ready for real patient data.

Planned production-oriented features: [ROADMAP.md](ROADMAP.md).

## How it works

Homomorphic Encryption (HE) allows computation on ciphertext. We use the CKKS scheme (via TenSEAL / Microsoft SEAL) because it supports approximate arithmetic on real numbers — means, regression, correlation — which is what clinical statistics need. The server never decrypts; it runs the same operations on encrypted vectors and returns an encrypted result.

Threshold key generation means the decryption key never exists in one place. Each institution holds a key share locally. The server only has the combined public key (used to encrypt). To decrypt a result, a threshold of institutions must contribute their shares. So no single party — including the platform — can decrypt.

Cryptographic commitments are computed at upload: `SHA3-256(ciphertext || public_key_fingerprint || timestamp || institution)`. They prove which key was used and that the stored file matches what was uploaded. Anyone can verify this locally.

The audit trail is append-only and hash-chained. Each entry includes the hash of the previous one; tampering breaks the chain. Blockchain anchoring (Polygon) is planned so the trail root is published on-chain and the platform cannot alter history.

```
  Institution A          Institution B
  [CSV data]             [CSV data]
      |                      |
  [encrypt locally]      [encrypt locally]
      |                      |
  [upload ciphertext]    [upload ciphertext]
      |                      |
      +------+  Server  +----+
             |          |
        [HE computation on ciphertexts]
             |
        [encrypted result]
             |
    [A approves] + [B approves]
             |
        [decrypted result]
             |
       both institutions
       (neither saw the other's data)
```

## Cryptographic Guarantees

**Guaranteed:**

- Raw data is never decrypted on the server.
- Private key shares never leave the institution's machine (SDK runs locally).
- Every operation is recorded in a tamper-evident audit log (hash chain).
- Commitment hashes prove which key was used for each upload.
- Codebase hash is computed at startup and included in every audit entry; you can verify what code ran via `GET /system/integrity`.

**Not guaranteed (honest):**

- No formal security proof of the full system.
- No external audit yet (planned for Phase 2).
- CKKS is approximate — results have small floating-point errors; documented per algorithm.
- Side-channel attacks are not mitigated at hardware level (TEE planned for Phase 2).

## What the platform operator can see

| Can see | Cannot see |
|---------|------------|
| Encrypted datasets (ciphertexts) | Raw data (patient data, measurements) |
| Metadata (file sizes, timestamps, institution names) | Private key shares (stay on each institution's machine) |
| Audit trail entries (actions, not contents) | Decrypted results before explicit release by all participants |
| Commitment hashes | Which values are in a dataset |
| Combined public key fingerprint | |
| Encrypted intermediate results | |

The right column is not policy — under the cryptographic model it is infeasible for the platform to see those things.

## Quickstart

**Prerequisites:** Python 3.11, Node.js 18+, (optional) Docker

```bash
# Clone
git clone https://github.com/[username]/securecollab
cd securecollab

# Backend
cd backend
python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

In another terminal:

```bash
# Frontend
cd frontend
npm install && npm run dev
# Open http://localhost:3000
```

Create a study at http://localhost:3000/studies/new. For a single-institution demo you can upload an encrypted dataset from the study dashboard (use the SDK to encrypt locally first, or run the backend scripts):

```bash
cd backend
source .venv/bin/activate
python encrypt.py sample_clinical_data.csv
# Then upload the generated encrypted.bin via the UI (Study → Datasets) or POST /datasets/upload
```

Full local dev and SDK usage: [DOCUMENTATION.md](DOCUMENTATION.md#lokale-entwicklung).

## Algorithms

| Algorithm | Inputs | Approx. time (1k rows) | Clinical use case |
|-----------|--------|------------------------|-------------------|
| Descriptive Statistics | 1 numeric column | 2 s | First data exploration |
| Correlation | 2 columns | 2 s | Association between two markers |
| Group Comparison | 1 column (split by index) | 2 s | Treatment vs control |
| Linear Regression | 2 columns (predictor, target) | 2 s | Predict one variable from another |
| Distribution | 1 column | 1 s | Rough distribution shape |
| Mean (legacy) | 1 column | 1 s | Simple aggregate |
| Multi-Group Comparison | 1 value column + optional mask columns | 5 s | Treatment vs control vs placebo |
| Logistic Regression (approx) | Features + binary target | 4 s | Treatment response screening (exploratory only) |
| Pearson Correlation Matrix | 2–6 columns | 8 s | GWAS-style correlation matrix |
| Survival Analysis (approx) | Time + event columns | 3 s | Survival / hazard (rough estimate) |
| Prevalence and Risk | Outcome + exposure (binary) | 3 s | Epidemiology, risk factors |
| Federated Mean Aggregation | 1 value column, optional weight | 2 s | Meta-analysis across institutions |
| Subgroup Analysis | Value column + binary mask columns | 6 s | Subgroup efficacy |

Times are estimates on a typical single core; CKKS operations are CPU-bound.

## Verify the code

Check what code is running on a deployed instance:

```bash
curl https://your-instance.com/system/integrity
```

Returns `codebase_hash`, `git_commit`, and versions. Reproduce locally and compare:

```bash
git clone https://github.com/[username]/securecollab && cd securecollab
# Build or run integrity module; compare hash to codebase_hash from the response
```

Full steps (reproducible build, local hash computation): [VERIFY.md](VERIFY.md).

## Trust Model

The entire platform is open source, not only the crypto library. You can read every line that runs on your data. There is no external security audit yet; that is planned for Phase 2. Verification (codebase hash in every audit entry, reproducible builds, optional blockchain anchoring) is designed so you can check what ran — so trust is not required in the same way as with proprietary "trust us" systems.

## Competitive Landscape

Duality Technologies is the closest competitor: well-funded, strong academic founders (including a Turing Award recipient), existing institutional customers. Their crypto stack (OpenFHE) is open source; their platform is not. Differences: (1) We are fully open source — platform and SDK. (2) Codebase hash in every audit entry and planned blockchain anchoring make the running code and audit trail verifiable. (3) We target institutions that cannot afford enterprise contracts; Duality focuses on large enterprise deals.

## Roadmap

[ROADMAP.md](ROADMAP.md) — Phase 1 (current), Phase 2 (first institutional users, audit, TEE, blockchain anchoring), Phase 3 (scaling, genomics, marketplace).

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Contributing

Security issues: please report to [your-security@email] (responsible disclosure), not as a public GitHub issue. For other contributions: open an issue or pull request as usual.
