# SecureCollab SDK

Client SDK for SecureCollab: local homomorphic encryption, schema negotiation, and API interaction.

## Structure

- `securecollab/` – Python package
  - `client.py` – `SecureCollabClient`, main entry
  - `crypto.py` – HE operations (encrypt, decrypt share)
  - `schema.py` – Schema analysis and protocol negotiation
  - `audit.py` – Local audit log and verification
  - `exceptions.py` – SDK exceptions
- `cli.py` – CLI entry point (migrate from `backend/sdk.py`)
- `setup.py` / `pyproject.toml` – Packaging

## Install

From repo root:

```bash
pip install -e ./sdk
```

## Usage

```python
from securecollab import SecureCollabClient
client = SecureCollabClient("http://localhost:8000")
algorithms = client.get_algorithms()
```

Full CLI (generate-key-share, encrypt, upload, request-computation, approve, verify-audit) is currently in `backend/sdk.py`; it will be moved here.
