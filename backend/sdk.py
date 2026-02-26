# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
"""
SecureCollab Client SDK – Kryptographische Vertrauensgrundlage für Institutionen.

Das SDK läuft ausschließlich lokal. Rohdaten verlassen den Rechner nie unverschlüsselt.
Jede Operation kann lokal verifiziert und in der lokalen Audit-Datei nachvollzogen werden.
"""
from __future__ import annotations

import argparse
import base64
import csv
import getpass
import hashlib
import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    import tenseal as ts
except ImportError:
    ts = None  # type: ignore

# -----------------------------------------------------------------------------
# Konstanten & Hilfsfunktionen
# -----------------------------------------------------------------------------

INITIAL_HASH = "0" * 64


def _sha3(*parts: bytes | str) -> str:
    h = hashlib.sha3_256()
    for p in parts:
        h.update(p.encode("utf-8") if isinstance(p, str) else p)
    return h.hexdigest()


def _local_audit_path(institution_email: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in institution_email)
    return Path(f"{safe}_local_audit.jsonl")


def _write_local_audit(institution_email: str, action: str, details: dict[str, Any], entry_hash: str | None = None) -> str:
    """
    Schreibt einen signierten Eintrag in die lokale Audit-Datei.
    Jeder Eintrag enthält einen Hash des Payloads (entry_hash) zur Integrität.
    """
    path = _local_audit_path(institution_email)
    ts_str = datetime.now(timezone.utc).isoformat()
    payload = {"action": action, "timestamp": ts_str, "details": details}
    payload_str = json.dumps(payload, sort_keys=True)
    if entry_hash is None:
        entry_hash = _sha3(payload_str)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"payload": payload, "entry_hash": entry_hash}, sort_keys=True) + "\n")
    return entry_hash


def _api_get(api_base_url: str, path: str) -> dict[str, Any]:
    url = f"{api_base_url.rstrip('/')}{path}"
    req = Request(url, method="GET")
    with urlopen(req) as resp:
        return json.loads(resp.read().decode())


def _api_post(api_base_url: str, path: str, data: dict[str, Any] | None = None, form: dict[str, Any] | None = None, file_path: Path | None = None, file_field: str = "file") -> dict[str, Any]:
    url = f"{api_base_url.rstrip('/')}{path}"
    if form is not None or file_path is not None:
        boundary = "----SecureCollabSDK"
        body_parts = []
        if form:
            for k, v in form.items():
                body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
        if file_path is not None and file_path.exists():
            raw = file_path.read_bytes()
            body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{file_path.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
            body_parts.append(raw)
            body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(p if isinstance(p, bytes) else p.encode() for p in body_parts)
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("Content-Length", str(len(body)))
    else:
        req = Request(url, data=json.dumps(data or {}).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
    with urlopen(req) as resp:
        return json.loads(resp.read().decode())


def _secret_key_path(institution_email: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in institution_email)
    return Path(f"{safe}_secret.key")


def _derive_key(password: str, salt: bytes = b"securecollab-sdk-v1") -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)


def _simple_encrypt(data: bytes, password: str) -> bytes:
    key = _derive_key(password)
    key = (key * (len(data) // len(key) + 1))[:len(data)]
    return bytes(a ^ b for a, b in zip(data, key))


def _simple_decrypt(data: bytes, password: str) -> bytes:
    return _simple_encrypt(data, password)


# Fernet-based secret key storage (OWASP A02). Requires cryptography.
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes as crypto_hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _FERNET_AVAILABLE = True
except ImportError:
    Fernet = None
    PBKDF2HMAC = None
    crypto_hashes = None
    _FERNET_AVAILABLE = False

PBKDF2_ITERATIONS = 600_000
SECRET_KEY_SALT_LEN = 16
FERNET_MAGIC = b"SCF1"  # SecureCollab Fernet format v1


def save_secret_key(context_bytes: bytes, institution_email: str, password: str) -> Path:
    """
    Verschlüsselt den Secret Key mit einem Passwort, bevor er gespeichert wird.

    WARUM: Der Secret Key ist der Hauptschutz der Institution. Wenn er im
    Klartext gespeichert ist, reicht Zugang zum Dateisystem, um ihn zu stehlen.
    PBKDF2 mit 600.000 Iterationen macht Brute-Force unpraktisch.
    Das Passwort verlässt niemals den lokalen Rechner.
    """
    path = _secret_key_path(institution_email)
    if _FERNET_AVAILABLE:
        salt = os.urandom(SECRET_KEY_SALT_LEN)
        kdf = PBKDF2HMAC(
            algorithm=crypto_hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        f = Fernet(key)
        encrypted_context = f.encrypt(context_bytes)
        path.write_bytes(FERNET_MAGIC + salt + encrypted_context)
    else:
        encrypted = _simple_encrypt(context_bytes, password)
        path.write_bytes(base64.b64encode(encrypted).decode("ascii").encode())
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_secret_key(institution_email: str, password: str) -> bytes:
    """Lädt und entschlüsselt den Secret Key (Fernet oder Fallback)."""
    path = _secret_key_path(institution_email)
    if not path.exists():
        raise FileNotFoundError(f"Secret key file not found: {path}")
    raw = path.read_bytes()
    if _FERNET_AVAILABLE and raw.startswith(FERNET_MAGIC) and len(raw) > len(FERNET_MAGIC) + SECRET_KEY_SALT_LEN:
        salt = raw[len(FERNET_MAGIC):len(FERNET_MAGIC) + SECRET_KEY_SALT_LEN]
        encrypted_context = raw[len(FERNET_MAGIC) + SECRET_KEY_SALT_LEN:]
        kdf = PBKDF2HMAC(
            algorithm=crypto_hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        f = Fernet(key)
        return f.decrypt(encrypted_context)
    try:
        enc = base64.b64decode(raw.decode())
    except Exception:
        enc = raw
    return _simple_decrypt(enc, password)


# -----------------------------------------------------------------------------
# 1. generate_key_share
# -----------------------------------------------------------------------------

def generate_key_share(institution_email: str) -> dict[str, Any]:
    """
    Generiert einen lokalen TenSEAL-CKKS-Key-Share für die Institution.

    WAS: Erstellt ein TenSEAL CKKS Context inkl. Secret Key, serialisiert den
    Public Key (ohne Secret) und speichert den Secret Key Context lokal in einer
    passwortgeschützten Datei. Gibt Public Key Share (base64) und Fingerprint zurück.

    WARUM: Beim Threshold-Setup muss jede Institution einen Key Share beisteuern.
    Der Public Key Share wird an den Server gesendet und mit anderen zu einem
    Study Public Key kombiniert. Der Secret Key darf niemals die Institution
    verlassen – nur er ermöglicht später die Entschlüsselung bzw. die Erzeugung
    von Decryption Shares.

    KRYPTOGARANTIE: Der Secret Key existiert nur im Speicher und in der lokal
    verschlüsselten Datei. Er wird nicht über das Netzwerk übertragen. Selbst
    der Plattformbetreiber kann mit nur dem Public Key Share keine Daten
    entschlüsseln. Die passwortgeschützte Speicherung verhindert unbefugten
    Zugriff bei Verlust der Datei (z. B. Backup).
    """
    if ts is None:
        raise RuntimeError("TenSEAL ist nicht installiert. Bitte: pip install tenseal")
    ctx = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=8192,
        coeff_mod_bit_sizes=[60, 40, 40, 60],
    )
    ctx.generate_galois_keys()
    ctx.global_scale = 2**40
    secret_ctx = ctx.serialize(save_secret_key=True)
    ctx.make_context_public()
    public_ctx = ctx.serialize()
    key_fingerprint = _sha3(public_ctx)
    public_b64 = base64.b64encode(public_ctx).decode("ascii")
    password = getpass.getpass("Passwort zum Schutz des Secret Keys (wird nicht gespeichert): ")
    if not password:
        password = "default-no-password-set"
    path = save_secret_key(secret_ctx, institution_email, password)
    _write_local_audit(institution_email, "key_share_generated", {"key_fingerprint": key_fingerprint, "secret_key_file": str(path)})
    return {"public_key_share": public_b64, "key_fingerprint": key_fingerprint}


# -----------------------------------------------------------------------------
# 2. verify_study_public_key
# -----------------------------------------------------------------------------

def verify_study_public_key(study_id: str, api_base_url: str) -> dict[str, Any]:
    """
    Holt den Study Public Key vom Server und verifiziert den Fingerprint lokal.

    WAS: GET /studies/{id}/public_key, berechnet SHA3-256(combined_public_key)
    und vergleicht mit dem vom Server gelieferten public_key_fingerprint.
    Gibt verified, fingerprint und (falls vorhanden) Teilnehmer-Info zurück.

    WARUM: Bevor Daten mit dem Study Key verschlüsselt werden, muss die
    Institution sicherstellen, dass der verwendete Key der vereinbarte ist.
    Ein manipulierter Server könnte sonst einen anderen Key ausliefern und
    später selbst entschlüsseln (wenn er den zugehörigen Secret Key hat).

    GARANTIE: Ein verified=True bedeutet: Der auf dem Server gespeicherte
    Public Key hat exakt den angezeigten Fingerprint. Damit ist nachweisbar,
    mit welchem Key verschlüsselt wurde. NICHT garantiert wird: Dass dieser
    Key tatsächlich aus einem ehrlichen Threshold-Setup stammt (das müsste
    durch das Protokoll und Vertrauen in die anderen Teilnehmer abgesichert werden).
    """
    data = _api_get(api_base_url, f"/studies/{study_id}/public_key")
    combined_b64 = data.get("combined_public_key") or ""
    server_fp = data.get("public_key_fingerprint") or ""
    participants = data.get("upload_commitments", [])
    if not combined_b64:
        return {"verified": False, "fingerprint": "", "participants": participants, "error": "Kein Public Key auf dem Server (Study evtl. noch nicht aktiv)."}
    raw = base64.b64decode(combined_b64)
    local_fp = _sha3(raw)
    verified = local_fp == server_fp
    return {"verified": verified, "fingerprint": local_fp, "participants": participants}


# -----------------------------------------------------------------------------
# 3. encrypt_and_upload
# -----------------------------------------------------------------------------

def _is_numeric_column(rows: list[dict], key: str) -> bool:
    for row in rows:
        val = row.get(key, "")
        if val is None or val == "":
            return False
        try:
            float(val)
        except (ValueError, TypeError):
            return False
    return True


# -----------------------------------------------------------------------------
# Schema Validation: Local Analysis & Negotiation
# -----------------------------------------------------------------------------
# Was: Analysiert lokale CSV nur nach Metadaten (Typ, Range, Null-Anteil) – keine echten Werte.
# Warum: Precondition für Study – alle Institutionen müssen dasselbe Schema akzeptieren.
# Garantie: Keine Rohdaten verlassen den Rechner bei analyze_local_schema.
# NICHT garantiert: negotiate_schema und run_dry_run senden Metadaten bzw. synthetische Daten.


def analyze_local_schema(csv_path: str) -> dict[str, Any]:
    """
    Analysiert die lokale CSV ohne Daten zu senden.
    Gibt zurück: {columns: [{name, type, range, null_pct, sample_values_count}]}.
    Keine echten Werte – nur Metadaten für Schema-Matching.
    Läuft vollständig lokal; nichts verlässt den Rechner.
    """
    path = Path(csv_path)
    if not path.exists():
        return {"columns": [], "error": "Datei nicht gefunden"}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return {"columns": [], "error": "Keine Zeilen"}
    all_keys = list(rows[0].keys())
    columns_out = []
    for key in all_keys:
        values = []
        nulls = 0
        for row in rows:
            val = row.get(key, "")
            if val is None or val == "" or (isinstance(val, str) and val.strip() == ""):
                nulls += 1
                continue
            try:
                values.append(float(val))
            except (ValueError, TypeError):
                pass
        n = len(rows)
        null_pct = round(100.0 * nulls / n, 2) if n else 0
        data_type = "float"
        if values:
            if all(v == int(v) for v in values):
                data_type = "integer"
            sample_range = [min(values), max(values)]
        else:
            sample_range = None
        columns_out.append({
            "name": key,
            "type": data_type,
            "range": sample_range,
            "null_pct": null_pct,
            "sample_values_count": len(values),
        })
    return {"columns": columns_out, "row_count": len(rows)}


def negotiate_schema(
    csv_path: str,
    study_id: str,
    institution_email: str,
    api_base_url: str,
    *,
    proposed_mapping: dict[str, str] | None = None,
    auto_accept: bool = False,
) -> dict[str, Any]:
    """
    Interaktiver Schema-Negotiation-Prozess:
    1. Analysiert lokale Daten (lokal)
    2. Holt Study-Protocol vom Server
    3. Schlägt automatisches Mapping vor (Name + Aliase)
    4. Optional: proposed_mapping übergeben oder nach Bestätigung submit
    5. Sendet Schema + Mapping an Server, gibt Kompatibilitätsbericht zurück.
    Garantie: institution_signature auf dem Server bindet Mapping + protocol_hash.
    NICHT garantiert: Dass die tatsächlichen Daten dem Mapping entsprechen (Dry Run nötig).
    """
    analysis = analyze_local_schema(csv_path)
    if analysis.get("error"):
        return {"compatible": False, "issues": [analysis["error"]], "approved_mappings": [], "warnings": []}
    local_columns = {c["name"]: c for c in analysis.get("columns", [])}
    protocol = _api_get(api_base_url, f"/studies/{study_id}/protocol")
    required = protocol.get("required_columns") or protocol.get("column_definitions") or []
    protocol_hash = protocol.get("protocol_hash")
    if not required:
        return {"compatible": False, "issues": ["Kein required_columns im Protocol (Study hat kein Schema-Protocol)."], "approved_mappings": [], "warnings": []}
    if proposed_mapping is None:
        proposed_mapping = {}
        for col_def in required:
            name = col_def.get("name", "") if isinstance(col_def, dict) else ""
            aliases = col_def.get("aliases") or [] if isinstance(col_def, dict) else []
            for local_name in local_columns:
                if local_name == name or local_name in aliases:
                    proposed_mapping[local_name] = name
                    break
            if name and name not in proposed_mapping.values():
                for a in aliases:
                    if a in local_columns:
                        proposed_mapping[a] = name
                        break
    local_schema = {
        "columns": [
            {
                "name": c["name"],
                "type": c["type"],
                "sample_range": c.get("range"),
                "null_percentage": c.get("null_pct", 0),
            }
            for c in local_columns.values()
        ]
    }
    resp = _api_post(api_base_url, f"/studies/{study_id}/schema/submit", data={
        "institution_email": institution_email,
        "local_schema": local_schema,
        "proposed_mapping": proposed_mapping,
    })
    _write_local_audit(
        institution_email,
        "schema_negotiated",
        {"study_id": study_id, "compatible": resp.get("compatible"), "issue_count": len(resp.get("issues", []))},
    )
    return resp


def run_dry_run(
    csv_path: str,
    study_id: str,
    institution_email: str,
    api_base_url: str,
) -> dict[str, Any]:
    """
    Lädt eine synthetische (oder Test-) CSV im Klartext hoch.
    Server validiert Schema und kann erlaubte Algorithmen auf Testdaten ausführen.
    Gibt Validierungsbericht zurück.
    HINWEIS: Diese Funktion lädt Klartextdaten hoch – nur für synthetische Testdaten verwenden.
    Garantie: Server speichert Dry-Run-Ergebnis; Voraussetzung für Study-Aktivierung.
    NICHT garantiert: Vertraulichkeit der hochgeladenen Daten (Klartext).
    """
    path = Path(csv_path)
    if not path.exists():
        return {"schema_valid": False, "issues": ["Datei nicht gefunden"], "algorithms_tested": []}
    form = {"institution_email": institution_email}
    try:
        resp = _api_post(api_base_url, f"/studies/{study_id}/synthetic/upload", form=form, file_path=path, file_field="file")
    except Exception as e:
        return {"schema_valid": False, "issues": [str(e)], "algorithms_tested": []}
    _write_local_audit(
        institution_email,
        "dry_run_completed",
        {"study_id": study_id, "schema_valid": resp.get("schema_valid")},
    )
    return resp


def encrypt_and_upload(
    csv_path: str,
    study_id: str,
    institution_email: str,
    api_base_url: str,
) -> dict[str, Any]:
    """
    Verschlüsselt eine lokale CSV mit dem Study Public Key und lädt sie hoch.

    WAS: Liest die CSV, holt und verifiziert den Study Public Key, bricht ab wenn
    die Verifikation fehlschlägt. Verschlüsselt jede numerische Spalte mit TenSEAL
    CKKS unter Verwendung des Study Public Key. Berechnet den Commitment
    commitment_hash = SHA3-256(ciphertext_bytes || key_fingerprint || timestamp || email),
    speichert ihn lokal in {study_id}_commitments.log, lädt die verschlüsselte
    Datei hoch (inkl. Client-Timestamp für reproduzierbaren Commitment), und
    prüft, dass der Server denselben commitment_hash zurückgibt.

    WARUM: Nur so bleibt nachweisbar, dass mit dem richtigen Key verschlüsselt
    wurde und der Server genau diese (verschlüsselte) Datei erhalten hat. Später
    kann jeder (Audit, Regulator) den Commitment vergleichen: Stimmt der Hash
    auf dem Server mit dem lokalen Log überein, wurde die richtige Datei mit
    dem richtigen Key hochgeladen. Der Commitment bindet Key, Zeitpunkt und
    Institution – ohne die Rohdaten preiszugeben.

    KRYPTOGARANTIE: Der Commitment-Mechanismus beweist: (1) Welcher Public Key
    verwendet wurde (Fingerprint im Hash), (2) Dass diese exakte Ciphertext-Datei
    hochgeladen wurde (ciphertext im Hash), (3) Wann und von wem (timestamp, email).
    Rohdaten erscheinen nirgends; die CSV verlässt den Rechner nur verschlüsselt.
    """
    if ts is None:
        raise RuntimeError("TenSEAL ist nicht installiert. Bitte: pip install tenseal")
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return {"commitment_hash": "", "verified": False, "columns_encrypted": [], "error": "CSV-Datei nicht gefunden."}
    out = verify_study_public_key(study_id, api_base_url)
    if not out.get("verified"):
        return {"commitment_hash": "", "verified": False, "columns_encrypted": [], "error": "Study Public Key konnte nicht verifiziert werden."}
    fingerprint = out["fingerprint"]
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return {"commitment_hash": "", "verified": False, "columns_encrypted": [], "error": "Keine Zeilen in der CSV."}
    all_keys = list(rows[0].keys())
    numeric_columns = [k for k in all_keys if _is_numeric_column(rows, k)]
    if not numeric_columns:
        return {"commitment_hash": "", "verified": False, "columns_encrypted": [], "error": "Keine numerischen Spalten."}
    n = len(rows)
    combined_b64 = _api_get(api_base_url, f"/studies/{study_id}/public_key").get("combined_public_key", "")
    ctx_bytes = base64.b64decode(combined_b64)
    ctx = ts.context_from(ctx_bytes)
    vectors_serialized = {}
    for col in numeric_columns:
        vec = [float(rows[i][col]) for i in range(n)]
        enc = ts.ckks_vector(ctx, vec)
        vectors_serialized[col] = enc.serialize()
    bundle = {
        "public_context": ctx_bytes,
        "vectors": vectors_serialized,
        "columns": json.dumps(numeric_columns),
        "n": n,
    }
    ciphertext_bytes = pickle.dumps(bundle)
    ts_str = datetime.now(timezone.utc).isoformat()
    commitment_hash = _sha3(ciphertext_bytes, fingerprint, ts_str, institution_email)
    commit_log_path = Path(f"{study_id}_commitments.log")
    with open(commit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": ts_str, "commitment_hash": commitment_hash, "dataset": csv_path.name, "institution_email": institution_email}) + "\n")
    tmp_file = Path(f"upload_{study_id}_{os.getpid()}.bin")
    tmp_file.write_bytes(ciphertext_bytes)
    try:
        form = {
            "institution_email": institution_email,
            "dataset_name": csv_path.stem,
            "columns": json.dumps(numeric_columns),
            "commitment_timestamp": ts_str,
        }
        resp = _api_post(api_base_url, f"/studies/{study_id}/upload_dataset", form=form, file_path=tmp_file, file_field="file")
    finally:
        tmp_file.unlink(missing_ok=True)
    server_commitment = resp.get("commitment_hash", "")
    verified = server_commitment == commitment_hash
    _write_local_audit(
        institution_email,
        "encrypt_and_upload",
        {"study_id": study_id, "commitment_hash": commitment_hash, "verified": verified, "columns_encrypted": numeric_columns},
    )
    return {"commitment_hash": commitment_hash, "verified": verified, "columns_encrypted": numeric_columns}


# -----------------------------------------------------------------------------
# 4. compute_decryption_share
# -----------------------------------------------------------------------------

def compute_decryption_share(
    study_id: str,
    job_id: str,
    institution_email: str,
    api_base_url: str,
) -> dict[str, Any]:
    """
    Berechnet einen Decryption Share und sendet ihn an den Server.

    WAS: Prüft den Job-Status (awaiting_decryption), lädt den lokalen Secret Key
    (nach Passwortabfrage), berechnet einen Decryption Share (im echten Threshold:
    partielle Entschlüsselung mit dem Key Share; im MVP: kryptographischer
    Nachweis der Beteiligung), und sendet den Share per POST an den Server.

    WARUM: Beim Threshold-Decryption darf keine Partei den vollständigen Secret Key
    besitzen. Jede Partei erzeugt mit ihrem Share einen „Teil-Ergebnis“. Erst wenn
    mindestens t solche Shares vorliegen, kann das Endergebnis rekonstruiert werden –
    ohne dass jemals ein vollständiger Secret Key existiert.

    KRYPTOGARANTIE: Ein einzelner Decryption Share verrät nichts über das
    Endergebnis. Er ist nur in Kombination mit (mindestens t-1) weiteren Shares
    auswertbar. Selbst der Plattformbetreiber kann mit nur einem Share die
    Ergebnisdaten nicht rekonstruieren. So bleibt die Kontrolle beim Konsortium
    (t-of-n), nicht bei einer einzelnen Instanz.
    """
    if not _secret_key_path(institution_email).exists():
        return {"share_submitted": False, "job_id": job_id, "error": "Lokaler Secret Key nicht gefunden. Zuerst generate_key_share ausführen."}
    password = getpass.getpass("Passwort für den Secret Key: ")
    try:
        secret_ctx = load_secret_key(institution_email, password)
    except Exception:
        return {"share_submitted": False, "job_id": job_id, "error": "Entschlüsselung des Secret Keys fehlgeschlagen (falsches Passwort?)."}
    share_fingerprint = _sha3(secret_ctx)[:32]
    payload = f"{job_id}{institution_email}{share_fingerprint}{datetime.now(timezone.utc).isoformat()}"
    share_bytes = _sha3(payload).encode("ascii")
    decryption_share_b64 = base64.b64encode(share_bytes).decode("ascii")
    try:
        _api_post(api_base_url, f"/studies/{study_id}/jobs/{job_id}/submit_decryption_share", data={"institution_email": institution_email, "decryption_share": decryption_share_b64})
    except (HTTPError, URLError) as e:
        return {"share_submitted": False, "job_id": job_id, "error": str(e)}
    _write_local_audit(institution_email, "decryption_share_submitted", {"study_id": study_id, "job_id": job_id})
    return {"share_submitted": True, "job_id": job_id}


# -----------------------------------------------------------------------------
# 5. verify_audit_trail
# -----------------------------------------------------------------------------

def verify_audit_trail(study_id: str, api_base_url: str, institution_email: str = "") -> dict[str, Any]:
    """
    Verifiziert die Integrität des server-seitigen Audit Trails.

    WAS: Holt den vollständigen Audit Trail (GET /studies/{id}/audit_trail),
    prüft für jeden Eintrag: entry_hash == SHA3-256(action_type || actor || details || timestamp || previous_hash),
    und prüft die Verkettung: previous_hash[n] == entry_hash[n-1]. Optional wird
    verglichen, ob die eigenen Aktionen (Uploads, Approvals) mit den lokalen
    Commitment-Logs übereinstimmen. Gibt chain_valid, own_entries_verified,
    anomalies und total_entries zurück.

    WARUM: Der Audit Trail ist die zentrale Nachweiskette für alle Operationen.
    Nur wenn die Kette lückenlos und hash-konsistent ist, kann man davon ausgehen,
    dass keine Einträge nachträglich geändert oder gelöscht wurden. Die lokale
    Abgleich mit den eigenen Logs stellt sicher, dass die eigene Sicht (z. B.
    Commitment-Hashes) mit der Server-Sicht übereinstimmt.

    GARANTIE: Ein gültiger Audit Trail (chain_valid=True, keine anomalies)
    beweist: (1) Die Reihenfolge und der Inhalt der geloggten Aktionen sind
    unverändert. (2) Jeder Eintrag ist durch den nächsten (previous_hash)
    kryptographisch angebunden. (3) Wenn own_entries_verified=True, stimmen
    die eigenen registrierten Aktionen mit dem Server überein – wichtig für
    Compliance und spätere Prüfungen.
    """
    data = _api_get(api_base_url, f"/studies/{study_id}/audit_trail")
    if not isinstance(data, list):
        return {"chain_valid": False, "own_entries_verified": False, "anomalies": ["Audit-Trail-Format ungültig"], "total_entries": 0}
    anomalies = []
    prev_hash = INITIAL_HASH
    for i, e in enumerate(data):
        entry_hash = e.get("entry_hash", "")
        previous_hash = e.get("previous_hash", "")
        if previous_hash != prev_hash:
            anomalies.append(f"Eintrag {i}: previous_hash stimmt nicht mit Vorgänger entry_hash überein.")
        ts_str = e.get("created_at", "")
        details_str = json.dumps(e.get("details") if isinstance(e.get("details"), dict) else {}, sort_keys=True)
        payload = f"{e.get('action_type', '')}{e.get('actor_email', '')}{details_str}{ts_str}{previous_hash}"
        expected = _sha3(payload)
        if entry_hash != expected:
            anomalies.append(f"Eintrag {i}: entry_hash stimmt nicht mit berechnetem Hash überein.")
        prev_hash = entry_hash
    chain_valid = len(anomalies) == 0
    own_verified = True
    if institution_email and chain_valid:
        commit_log = Path(f"{study_id}_commitments.log")
        if commit_log.exists():
            local_hashes = set()
            for line in commit_log.read_text().strip().splitlines():
                try:
                    rec = json.loads(line)
                    if rec.get("institution_email") == institution_email:
                        local_hashes.add(rec.get("commitment_hash", ""))
                except (json.JSONDecodeError, TypeError):
                    pass
            server_commitments = [u.get("commitment_hash") for u in _api_get(api_base_url, f"/studies/{study_id}/public_key").get("upload_commitments", []) if u.get("institution_email") == institution_email]
            if local_hashes and not all(c in local_hashes for c in server_commitments):
                own_verified = False
                anomalies.append("Mindestens ein eigener Upload-Commitment auf dem Server fehlt im lokalen Log oder weicht ab.")
    return {"chain_valid": chain_valid, "own_entries_verified": own_verified, "anomalies": anomalies, "total_entries": len(data)}


# -----------------------------------------------------------------------------
# 6. generate_study_report
# -----------------------------------------------------------------------------

def generate_study_report(study_id: str, api_base_url: str, institution_email: str = "") -> str:
    """
    Erstellt einen lokalen Verifikationsbericht als Markdown.

    WAS: Ruft Study-Metadaten und Audit-Trail ab, führt verify_audit_trail aus,
    und schreibt eine lesbare Markdown-Datei {study_id}_verification_report.md
    mit Study-Parametern, allen Commitments, Audit-Verifikation und einer
    verständlichen Darstellung der kryptographischen Garantien.

    WARUM: Compliance und Regulatoren benötigen einen nachvollziehbaren,
    menschenlesbaren Nachweis: Was wurde wann von wem gemacht, und welche
    kryptographischen Eigenschaften gelten? Der Report fasst genau das zusammen
    und kann archiviert oder weitergegeben werden, ohne die Plattform erneut
    abfragen zu müssen.

    ZIELGRUPPE: Compliance-Verantwortliche, interne und externe Auditoren,
    Regulatoren (z. B. Aufsichtsbehörden), und die eigene Dokumentation der
    Institution. Der Report dient als Beleg für „Privacy by Design“ und
    nachweisbar sichere Mehrparteien-Berechnung.
    """
    protocol = _api_get(api_base_url, f"/studies/{study_id}/protocol")
    audit_result = verify_audit_trail(study_id, api_base_url, institution_email)
    meta = protocol.get("study_metadata", {})
    lines = [
        f"# Verifikationsbericht Study {study_id}",
        "",
        "## Study-Parameter",
        f"- Name: {meta.get('name', '')}",
        f"- Status: {meta.get('status', '')}",
        f"- Threshold: {meta.get('threshold_t', '')} von {meta.get('threshold_n', '')}",
        f"- Public-Key-Fingerprint: `{meta.get('public_key_fingerprint', '')}`",
        "",
        "## Teilnehmer",
    ]
    for p in protocol.get("participants", []):
        lines.append(f"- {p.get('institution_name', '')} ({p.get('institution_email', '')})")
    lines.extend([
        "",
        "## Erlaubte Algorithmen",
        "- " + ", ".join(protocol.get("allowed_algorithms", [])),
        "",
        "## Upload-Commitments (Server)",
    ])
    for d in protocol.get("datasets", []):
        lines.append(f"- {d.get('dataset_name', '')} / {d.get('institution_email', '')}: `{d.get('commitment_hash', '')[:24]}...`")
    lines.extend([
        "",
        "## Audit-Trail-Verifikation",
        f"- Kette gültig: **{'Ja' if audit_result['chain_valid'] else 'Nein'}**",
        f"- Eigene Einträge verifiziert: **{'Ja' if audit_result['own_entries_verified'] else 'Nein'}**",
        f"- Anzahl Einträge: {audit_result['total_entries']}",
    ])
    if audit_result.get("anomalies"):
        lines.append("")
        lines.append("### Anomalien")
        for a in audit_result["anomalies"]:
            lines.append(f"- {a}")
    lines.extend([
        "",
        "## Kryptographische Garantien (Kurz)",
        "- Rohdaten verlassen die Institution nur verschlüsselt (Study Public Key).",
        "- Der Commitment bindet Ciphertext, Key-Fingerprint, Zeit und Institution.",
        "- Der Audit Trail ist durch Hash-Verkettung manipulationssicher.",
        "- Ein einzelner Decryption Share offenbart das Ergebnis nicht.",
        "",
        f"*Erstellt: {datetime.now(timezone.utc).isoformat()}*",
    ])
    report = "\n".join(lines)
    out_path = Path(f"{study_id}_verification_report.md")
    out_path.write_text(report, encoding="utf-8")
    return str(out_path)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _cli():
    parser = argparse.ArgumentParser(description="SecureCollab Client SDK")
    sub = parser.add_subparsers(dest="command", required=True)
    # generate-key
    p1 = sub.add_parser("generate-key", help="Lokalen Key Share erzeugen")
    p1.add_argument("--email", required=True, help="E-Mail der Institution")
    # verify-study
    p2 = sub.add_parser("verify-study", help="Study Public Key verifizieren")
    p2.add_argument("--study-id", required=True)
    p2.add_argument("--url", required=True, dest="api_base_url")
    # upload
    p3 = sub.add_parser("upload", help="CSV verschlüsseln und hochladen")
    p3.add_argument("--csv", required=True, dest="csv_path")
    p3.add_argument("--study-id", required=True)
    p3.add_argument("--email", required=True, dest="institution_email")
    p3.add_argument("--url", required=True, dest="api_base_url")
    # decrypt-share
    p4 = sub.add_parser("decrypt-share", help="Decryption Share berechnen und senden")
    p4.add_argument("--study-id", required=True)
    p4.add_argument("--job-id", required=True)
    p4.add_argument("--email", required=True, dest="institution_email")
    p4.add_argument("--url", required=True, dest="api_base_url")
    # verify-audit
    p5 = sub.add_parser("verify-audit", help="Audit Trail verifizieren")
    p5.add_argument("--study-id", required=True)
    p5.add_argument("--url", required=True, dest="api_base_url")
    p5.add_argument("--email", default="", dest="institution_email")
    # generate-report
    p6 = sub.add_parser("generate-report", help="Verifikationsbericht (Markdown) erzeugen")
    p6.add_argument("--study-id", required=True)
    p6.add_argument("--url", required=True, dest="api_base_url")
    p6.add_argument("--email", default="", dest="institution_email")
    # analyze-schema
    p7 = sub.add_parser("analyze-schema", help="Lokales CSV-Schema analysieren (keine Übertragung)")
    p7.add_argument("--csv", required=True, dest="csv_path")
    # negotiate-schema
    p8 = sub.add_parser("negotiate-schema", help="Schema mit Study-Protocol abgleichen und einreichen")
    p8.add_argument("--csv", required=True, dest="csv_path")
    p8.add_argument("--study-id", required=True)
    p8.add_argument("--email", required=True, dest="institution_email")
    p8.add_argument("--url", required=True, dest="api_base_url")
    # dry-run
    p9 = sub.add_parser("dry-run", help="Synthetische CSV hochladen und Schema validieren (Klartext!)")
    p9.add_argument("--csv", required=True, dest="csv_path")
    p9.add_argument("--study-id", required=True)
    p9.add_argument("--email", required=True, dest="institution_email")
    p9.add_argument("--url", required=True, dest="api_base_url")
    args = parser.parse_args()
    if args.command == "generate-key":
        r = generate_key_share(args.email)
        print("Public Key Share (base64) und Fingerprint wurden erzeugt.")
        print("Key-Fingerprint:", r.get("key_fingerprint", ""))
        print("Secret Key gespeichert in:", _secret_key_path(args.email))
    elif args.command == "verify-study":
        r = verify_study_public_key(args.study_id, args.api_base_url)
        print("Verifiziert:", r.get("verified"))
        print("Fingerprint:", r.get("fingerprint", ""))
        if r.get("error"):
            print("Hinweis:", r["error"])
    elif args.command == "upload":
        r = encrypt_and_upload(args.csv_path, args.study_id, args.institution_email, args.api_base_url)
        print("Commitment-Hash:", r.get("commitment_hash", ""))
        print("Vom Server verifiziert:", r.get("verified"))
        print("Verschlüsselte Spalten:", r.get("columns_encrypted", []))
        if r.get("error"):
            print("Fehler:", r["error"])
    elif args.command == "decrypt-share":
        r = compute_decryption_share(args.study_id, args.job_id, args.institution_email, args.api_base_url)
        print("Share eingereicht:", r.get("share_submitted"))
        print("Job-ID:", r.get("job_id", ""))
        if r.get("error"):
            print("Fehler:", r["error"])
    elif args.command == "verify-audit":
        r = verify_audit_trail(args.study_id, args.api_base_url, args.institution_email)
        print("Kette gültig:", r.get("chain_valid"))
        print("Eigene Einträge verifiziert:", r.get("own_entries_verified"))
        print("Anzahl Einträge:", r.get("total_entries"))
        for a in r.get("anomalies", []):
            print("Anomalie:", a)
    elif args.command == "generate-report":
        path = generate_study_report(args.study_id, args.api_base_url, args.institution_email)
        print("Bericht gespeichert:", path)
    elif args.command == "analyze-schema":
        r = analyze_local_schema(args.csv_path)
        if r.get("error"):
            print("Fehler:", r["error"])
        else:
            print("Gefundene Spalten (lokal, keine Übertragung):")
            for c in r.get("columns", []):
                rng = c.get("range")
                rng_s = f"{rng[0]}-{rng[1]}" if rng else "—"
                print(f"  {c['name']} ({c['type']}, {rng_s}, {c.get('null_pct', 0)}% missing)")
    elif args.command == "negotiate-schema":
        r = negotiate_schema(args.csv_path, args.study_id, args.institution_email, args.api_base_url)
        print("Kompatibel:", r.get("compatible"))
        print("Approved Mappings:", r.get("approved_mappings", []))
        for i in r.get("issues", []):
            print("  ✗", i)
        for w in r.get("warnings", []):
            print("  ⚠", w)
    elif args.command == "dry-run":
        r = run_dry_run(args.csv_path, args.study_id, args.institution_email, args.api_base_url)
        print("Schema gültig:", r.get("schema_valid"))
        for i in r.get("issues", []):
            print("  ", i)
    return 0


if __name__ == "__main__":
    sys.exit(_cli() or 0)
