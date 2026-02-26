# SPDX-License-Identifier: Apache-2.0
"""
Codebase Integrity – deterministischer Hash der gesamten Codebase.

WARUM: Kunden müssen dem Code vertrauen können. Open Source zeigt, was der Code
tun soll. Dieser Hash beweist, was tatsächlich läuft. Institutionen können
GET /system/integrity aufrufen und den codebase_hash mit ihrem lokalen
Code-Review-Hash vergleichen.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Project root: parent of backend/
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

# Inclusions: extensions and exact file names
INCLUDE_EXTENSIONS = {".py", ".ts", ".tsx"}
INCLUDE_FILES = {"requirements.txt", "Dockerfile", "package.json"}

# Exclusions (path segments or patterns)
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".next", "uploads", "logs", ".venv", "venv"}
EXCLUDE_PATTERNS = [re.compile(r"\.env$"), re.compile(r"\.bin$"), re.compile(r"deployment_integrity\.json$")]


def _should_include(path: Path, relative: Path) -> bool:
    if path.is_dir():
        return False
    name = path.name
    if name in INCLUDE_FILES:
        return True
    if path.suffix.lower() in INCLUDE_EXTENSIONS:
        return True
    return False


def _should_exclude(path: Path, relative: Path) -> bool:
    parts = relative.parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    for pat in EXCLUDE_PATTERNS:
        if pat.search(path.name):
            return True
    return False


def compute_codebase_hash() -> dict:
    """
    Berechnet einen deterministischen Hash der gesamten Codebase.

    Inkludiert: alle .py, .ts, .tsx Dateien, requirements.txt, Dockerfiles.
    Exkludiert: __pycache__, .env, *.bin (Daten), logs, uploads/, .git/

    Gibt zurück:
    {
        "codebase_hash": "sha3_256_hex",
        "git_commit": "current_commit_hash_or_unknown",
        "git_tag": "current_tag_or_none",
        "computed_at": "iso_timestamp",
        "file_count": int,
        "files_included": ["path1", "path2", ...]
    }
    Speichert Ergebnis in deployment_integrity.json (im Backend-Verzeichnis).
    """
    collected: list[tuple[str, bytes]] = []

    for root, dirs, files in os.walk(REPO_ROOT, topdown=True):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

        for name in files:
            path = root_path / name
            try:
                rel = path.relative_to(REPO_ROOT)
            except ValueError:
                continue
            if _should_exclude(path, rel):
                continue
            if not _should_include(path, rel):
                continue
            try:
                content = path.read_bytes()
            except (OSError, IOError):
                continue
            rel_str = str(rel).replace("\\", "/")
            collected.append((rel_str, content))

    collected.sort(key=lambda x: x[0])
    files_included = [p for p, _ in collected]
    hasher = hashlib.sha3_256()
    for rel_str, content in collected:
        hasher.update(rel_str.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(content)
        hasher.update(b"\0")
    codebase_hash = hasher.hexdigest()

    git_commit = "unknown"
    git_tag = None
    try:
        commit_out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if commit_out.returncode == 0 and commit_out.stdout.strip():
            git_commit = commit_out.stdout.strip()
        tag_out = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if tag_out.returncode == 0 and tag_out.stdout.strip():
            git_tag = tag_out.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    computed_at = datetime.now(timezone.utc).isoformat()
    result = {
        "codebase_hash": codebase_hash,
        "git_commit": git_commit,
        "git_tag": git_tag,
        "computed_at": computed_at,
        "file_count": len(files_included),
        "files_included": files_included,
    }

    out_path = BACKEND_DIR / "deployment_integrity.json"
    try:
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except (OSError, IOError):
        pass

    return result


def verify_codebase_hash(expected_hash: str) -> dict:
    """
    Verifiziert, dass der aktuelle Code mit einem erwarteten Hash übereinstimmt.
    Institutionen können damit prüfen, ob ihr Code-Review noch gültig ist.
    """
    current = compute_codebase_hash()
    match = current["codebase_hash"] == expected_hash
    return {
        "verified": match,
        "expected_hash": expected_hash,
        "current_hash": current["codebase_hash"],
        "computed_at": current["computed_at"],
        "file_count": current["file_count"],
    }
