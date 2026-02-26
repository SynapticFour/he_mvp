# How To Verify SecureCollab

This guide is for institutions that want to verify that the instance they use runs the code they have reviewed.

## Step 1: Review the Source Code

- **Repository:** [Your GitHub repository URL]
- **Critical paths:**
  - `backend/main.py` – API, upload handling, job execution, audit logging
  - `backend/algorithms.py` – Homomorphic computation (no plaintext access)
  - `backend/integrity.py` – Codebase hash computation
  - `backend/sdk.py` – Client-side key generation, encryption, secret key storage

Review these files (and dependencies in `backend/requirements.txt`) to satisfy yourself that the described guarantees hold.

## Step 2: Reproduce the Build

Build the image without cache and compute a digest:

```bash
docker build --no-cache -t securecollab:verify .
docker save securecollab:verify -o securecollab.tar
sha256sum securecollab.tar   # or shasum -a 256 on macOS
```

**Expected hash:** Will be updated for each release. Compare with the hash published for the version you deploy.

## Step 3: Verify the Running Instance

Query the integrity endpoint of the instance you use:

```bash
curl https://your-instance.com/system/integrity
```

You should see something like:

```json
{
  "codebase_hash": "a1b2c3...",
  "git_commit": "abc123...",
  "computed_at": "2025-...",
  "tenseal_version": "0.3.15",
  "fastapi_version": "0.115.x",
  "python_version": "3.11.x"
}
```

- **codebase_hash:** Compute this locally by running the same logic as `backend/integrity.py` (include the same files and exclusions). The hash must match the one you get from the server for the codebase you reviewed.
- **git_commit:** If the deployment was built from Git, this should match the commit you expect.

## Step 4: Verify Your Own Operations

After participating in a study, verify that your actions are correctly recorded:

```bash
python sdk.py verify-audit --study-id YOUR_STUDY_ID --url https://your-instance.com
```

This checks:

- The audit trail’s hash chain is intact.
- Your uploads and approvals appear as expected and match your local commitment logs (if you use them).

## Step 5: Verify the Audit Trail Anchor (Phase 2)

When blockchain anchoring is implemented (e.g. Polygon), you will be able to:

- Look up the transaction that stores the audit trail root hash.
- Confirm that the on-chain hash matches the root of the audit trail you retrieved from the API.

*(Instructions will be added when this feature is available.)*
