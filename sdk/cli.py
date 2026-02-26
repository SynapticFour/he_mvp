# SPDX-License-Identifier: Apache-2.0
"""Click CLI entry point for SecureCollab SDK."""
# Full CLI: migrate from backend/sdk.py (argparse commands: generate-key-share, encrypt, upload, request-computation, approve, submit-decryption-share, verify-audit).
import sys

def main():
    print("SecureCollab SDK CLI. Use backend/sdk.py for full commands until migration complete.", file=sys.stderr)
    sys.exit(0)

if __name__ == "__main__":
    main()
