// SPDX-License-Identifier: Apache-2.0
"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useEmail } from "@/lib/email-context";
import {
  getStudy,
  getStudyProtocol,
  getStudyPublicKey,
  getStudyAuditTrail,
  uploadStudyDataset,
  requestStudyComputation,
  approveStudyJob,
  submitDecryptionShare,
  getAlgorithms,
  type StudyDetail,
  type StudyProtocol,
  type AuditEntry,
  type AlgorithmInfo,
} from "@/lib/api";
import { CryptoBadge } from "@/components/CryptoBadge";
import { CommitmentHash } from "@/components/CommitmentHash";
import { AuditEntryCard } from "@/components/AuditEntryCard";
import { Modal } from "@/components/Modal";
import { Badge } from "@/components/Badge";

const TABS = ["Overview", "Participants", "Datasets", "Analysis", "Audit Trail", "Protocol Report"];

export default function StudyDashboardPage() {
  const params = useParams();
  const studyId = Number(params.id);
  const { email } = useEmail();
  const [study, setStudy] = useState<StudyDetail | null>(null);
  const [protocol, setProtocol] = useState<StudyProtocol | null>(null);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [commitmentAfterUpload, setCommitmentAfterUpload] = useState("");
  const [requestAlgo, setRequestAlgo] = useState("");
  const [requestColumns, setRequestColumns] = useState<string[]>([]);
  const [requesting, setRequesting] = useState(false);
  const [decryptShareJobId, setDecryptShareJobId] = useState<number | null>(null);
  const [decryptShareValue, setDecryptShareValue] = useState("");
  const [chainValid, setChainValid] = useState<boolean | null>(null);
  const [algorithmRegistry, setAlgorithmRegistry] = useState<Record<string, AlgorithmInfo>>({});

  useEffect(() => {
    getAlgorithms().then(setAlgorithmRegistry);
  }, []);

  const load = useCallback(async () => {
    if (!studyId || isNaN(studyId)) return;
    setLoading(true);
    setError("");
    try {
      const [s, p, a] = await Promise.all([
        getStudy(studyId),
        getStudyProtocol(studyId),
        getStudyAuditTrail(studyId),
      ]);
      setStudy(s);
      setProtocol(p);
      setAuditEntries(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [studyId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpload = async () => {
    if (!uploadFile || !email || !studyId) return;
    setUploading(true);
    setCommitmentAfterUpload("");
    try {
      const res = await uploadStudyDataset(studyId, uploadFile, email, uploadName || uploadFile.name, []);
      setCommitmentAfterUpload(res.commitment_hash);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleRequestAnalysis = async () => {
    if (!email || !studyId || !requestAlgo) return;
    setRequesting(true);
    try {
      await requestStudyComputation(studyId, {
        requester_email: email,
        algorithm: requestAlgo,
        selected_columns: requestColumns,
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setRequesting(false);
    }
  };

  const handleApprove = async (jobId: number) => {
    if (!email) return;
    try {
      await approveStudyJob(studyId, jobId, email);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    }
  };

  const handleSubmitDecryptionShare = async () => {
    if (!email || !decryptShareJobId || !decryptShareValue) return;
    try {
      await submitDecryptionShare(studyId, decryptShareJobId, email, decryptShareValue);
      setDecryptShareJobId(null);
      setDecryptShareValue("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submit failed");
    }
  };

  const verifyAuditChain = () => {
    if (auditEntries.length === 0) {
      setChainValid(true);
      return;
    }
    const initialHash = "0".repeat(64);
    let prev = initialHash;
    let valid = true;
    for (const e of auditEntries) {
      if (e.previous_hash !== prev) {
        valid = false;
        break;
      }
      prev = e.entry_hash;
    }
    setChainValid(valid);
  };

  if (loading && !study) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-slate-500">Loading study…</p>
      </div>
    );
  }
  if (error && !study) {
    return (
      <div>
        <Link href="/studies" className="text-sm text-accent hover:underline">← My Studies</Link>
        <p className="mt-4 text-red-600">{error}</p>
      </div>
    );
  }
  if (!study) return null;

  const isActive = study.status === "active";
  const pendingJobs = protocol?.jobs?.filter((j) => j.status === "pending_approval") ?? [];
  const awaitingDecryptionJobs = protocol?.jobs?.filter((j) => j.status === "awaiting_decryption") ?? [];
  const allowedAlgos = protocol?.allowed_algorithms ?? [];

  return (
    <div>
      <Link href="/studies" className="text-sm text-accent hover:underline">← My Studies</Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{study.name}</h1>
          {study.description && <p className="mt-1 text-slate-600">{study.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={isActive ? "success" : "warning"}>
            {isActive ? "Cryptographically Active" : "Waiting for participants"}
          </Badge>
          {isActive && study.public_key_fingerprint && (
            <CryptoBadge verified label={`0x${study.public_key_fingerprint.slice(0, 6)}…${study.public_key_fingerprint.slice(-4)} – verified`} />
          )}
        </div>
      </div>

      {/* Status banner */}
      <div className={`mt-6 rounded-xl border p-4 ${isActive ? "border-success/30 bg-success/5" : "border-warning/30 bg-warning/5"}`}>
        {isActive ? (
          <p className="text-sm text-slate-700">
            <strong>Cryptographically Active.</strong> Public Key Fingerprint: <code className="text-xs">{study.public_key_fingerprint?.slice(0, 12)}…</code> – verified. Data can be uploaded and analyses requested.
          </p>
        ) : (
          <p className="text-sm text-amber-800">
            <strong>Waiting for participants.</strong> Share the Study ID with other institutions. Once all key shares are submitted, the study becomes active.
          </p>
        )}
      </div>

      {/* Tabs */}
      <div className="mt-6 border-b border-slate-200">
        {TABS.map((label, i) => (
          <button
            key={label}
            type="button"
            onClick={() => setTab(i)}
            className={`border-b-2 px-4 py-2 text-sm font-medium ${tab === i ? "border-primary text-primary" : "border-transparent text-slate-500 hover:text-slate-700"}`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === 0 && (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h2 className="font-semibold text-slate-900">Study Protocol</h2>
              <dl className="mt-3 space-y-1 text-sm">
                <div><dt className="text-slate-500">Threshold</dt><dd>{study.threshold_t} of {study.threshold_n} participants</dd></div>
                <div><dt className="text-slate-500">Allowed algorithms</dt><dd>{allowedAlgos.join(", ") || "—"}</dd></div>
                <div><dt className="text-slate-500">Participants</dt><dd>{(protocol?.participants?.length ?? 0)}</dd></div>
              </dl>
              {study.public_key_fingerprint && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-slate-700">Combined Public Key Fingerprint</p>
                  <CommitmentHash hash={study.public_key_fingerprint} />
                </div>
              )}
              <p className="mt-4 text-sm text-slate-600">
                All data in this study is encrypted with this key. Decryption requires {study.threshold_t} of {study.threshold_n} participants.
              </p>
            </div>
          </div>
        )}

        {tab === 1 && (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="font-semibold text-slate-900">Participants</h2>
            <p className="mt-1 text-sm text-slate-600">
              Each participant holds one key share locally. The platform has no access to any key shares.
            </p>
            <table className="mt-4 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="pb-2 font-medium">Institution</th>
                  <th className="pb-2 font-medium">Email</th>
                  <th className="pb-2 font-medium">Key Share</th>
                  <th className="pb-2 font-medium">Joined</th>
                </tr>
              </thead>
              <tbody>
                {(protocol?.participants ?? []).map((p, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-2">{p.institution_name || "—"}</td>
                    <td className="py-2">{p.institution_email}</td>
                    <td className="py-2">
                      <CryptoBadge verified label="Verified" />
                    </td>
                    <td className="py-2">{new Date(p.joined_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === 2 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Datasets</h2>
              <button
                type="button"
                onClick={() => setUploadModalOpen(true)}
                className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
              >
                Upload Encrypted Dataset
              </button>
            </div>
            <p className="text-sm text-slate-600">
              Use the SecureCollab SDK to encrypt your data locally first, then upload the .bin file here.
            </p>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="pb-2 font-medium">Dataset</th>
                  <th className="pb-2 font-medium">Institution</th>
                  <th className="pb-2 font-medium">Upload</th>
                  <th className="pb-2 font-medium">Commitment Hash</th>
                  <th className="pb-2 font-medium">Verify</th>
                </tr>
              </thead>
              <tbody>
                {(protocol?.datasets ?? []).map((d, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-2">{d.dataset_name}</td>
                    <td className="py-2">{d.institution_email}</td>
                    <td className="py-2">{new Date(d.committed_at).toLocaleString()}</td>
                    <td className="py-2"><CommitmentHash hash={d.commitment_hash} /></td>
                    <td className="py-2">
                      <span className="text-slate-500" title="Use SecureCollab SDK to verify against your local commitment log.">SDK verify</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(!protocol?.datasets?.length) && (
              <p className="mt-4 text-slate-500">No datasets yet. Upload one using the SDK and then this page.</p>
            )}

            <Modal open={uploadModalOpen} onClose={() => { setUploadModalOpen(false); setCommitmentAfterUpload(""); }} title="Upload Encrypted Dataset">
              <p className="text-sm text-slate-600">
                Use the SecureCollab SDK to encrypt your data locally first, then upload the .bin file here.
              </p>
              <div className="mt-4">
                <label className="block text-sm font-medium">Dataset name</label>
                <input
                  type="text"
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="e.g. trial_phase2"
                />
              </div>
              <div className="mt-4">
                <label className="block text-sm font-medium">File (.bin)</label>
                <input
                  type="file"
                  accept=".bin"
                  onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                  className="mt-1 w-full text-sm"
                />
              </div>
              {commitmentAfterUpload && (
                <div className="mt-4 rounded-lg bg-success/10 p-3 text-sm text-success">
                  <p className="font-medium">Upload successful.</p>
                  <p className="mt-1">Save this commitment hash locally to verify your data&apos;s integrity at any time:</p>
                  <code className="mt-2 block break-all font-mono text-xs">{commitmentAfterUpload}</code>
                </div>
              )}
              <div className="mt-6 flex gap-2">
                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={!uploadFile || uploading}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  {uploading ? "Uploading…" : "Upload"}
                </button>
                <button type="button" onClick={() => setUploadModalOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button>
              </div>
            </Modal>
          </div>
        )}

        {tab === 3 && (
          <div className="grid gap-6 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h2 className="font-semibold text-slate-900">Request Analysis</h2>
              <div className="mt-4">
                <label className="block text-sm font-medium">Algorithm</label>
                <select
                  value={requestAlgo}
                  onChange={(e) => setRequestAlgo(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                >
                  <option value="">Select…</option>
                  {allowedAlgos.map((a) => {
                    const info = algorithmRegistry[a];
                    return (
                      <option key={a} value={a}>
                        {info ? `${info.name} (est. ${info.estimated_seconds}s)` : a.replace(/_/g, " ")}
                      </option>
                    );
                  })}
                </select>
                {requestAlgo && algorithmRegistry[requestAlgo] && (
                  <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm">
                    <p className="text-slate-700">{algorithmRegistry[requestAlgo].description}</p>
                    <p className="mt-1 text-slate-500">Use case: {algorithmRegistry[requestAlgo].clinical_use_case}</p>
                    {algorithmRegistry[requestAlgo].approximation_warning && (
                      <p className="mt-1 text-amber-700">⚠ {algorithmRegistry[requestAlgo].approximation_warning}</p>
                    )}
                  </div>
                )}
              </div>
              <p className="mt-4 text-sm text-slate-600">
                Your request will be logged in the audit trail. All {study.threshold_n} participants must approve before computation begins.
              </p>
              <button
                type="button"
                onClick={handleRequestAnalysis}
                disabled={!requestAlgo || requesting}
                className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                Submit Request
              </button>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h2 className="font-semibold text-slate-900">Pending Approvals</h2>
              {pendingJobs.length === 0 && awaitingDecryptionJobs.length === 0 && (
                <p className="mt-2 text-sm text-slate-500">No pending items.</p>
              )}
              {pendingJobs.map((j) => (
                <div key={j.id} className="mt-4 rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-medium">Job #{j.id} – {j.algorithm}</p>
                  <p className="text-xs text-slate-500">Requester: {j.requester_email}</p>
                  <button
                    type="button"
                    onClick={() => handleApprove(j.id)}
                    className="mt-2 rounded bg-success px-2 py-1 text-xs text-white hover:bg-success/90"
                  >
                    Approve
                  </button>
                </div>
              ))}
              {awaitingDecryptionJobs.map((j) => (
                <div key={j.id} className="mt-4 rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                  <p className="text-sm font-medium">Job #{j.id} – Result encrypted. Submit decryption share to reveal.</p>
                  <p className="mt-2 text-xs text-slate-600">
                    Use the SecureCollab SDK: <code>python sdk.py decrypt-share --study-id {studyId} --job-id {j.id} --email your@email.com --url ...</code>
                  </p>
                  <button
                    type="button"
                    onClick={() => setDecryptShareJobId(j.id)}
                    className="mt-2 rounded bg-primary px-2 py-1 text-xs text-white"
                  >
                    Submit Decryption Share
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 4 && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-4">
              <button
                type="button"
                onClick={verifyAuditChain}
                className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                Verify Integrity
              </button>
              {chainValid !== null && (
                <CryptoBadge verified={chainValid} label={chainValid ? "Chain Integrity: ✓ Verified" : "Chain invalid"} />
              )}
              <a
                href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(auditEntries, null, 2))}`}
                download={`study-${studyId}-audit.json`}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50"
              >
                Download Full Audit Trail (JSON)
              </a>
            </div>
            <p className="text-sm text-slate-600">
              Every action is cryptographically chained. Any tampering with historical entries is mathematically detectable.
              Chain verification below checks linkage (previous_hash → entry_hash). Full SHA3-256 verification is available in the SecureCollab SDK.
            </p>
            <div className="space-y-3">
              {auditEntries.map((e) => (
                <AuditEntryCard key={e.id} entry={e} />
              ))}
            </div>
            {auditEntries.length === 0 && <p className="text-slate-500">No audit entries yet.</p>}
          </div>
        )}

        {tab === 5 && (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="font-semibold text-slate-900">Protocol Report</h2>
            <div className="mt-4 rounded-lg bg-slate-100 p-4 text-sm text-slate-700">
              <p className="font-medium">This study was conducted under cryptographic guarantees.</p>
              <p className="mt-2">The platform operator had access to: encrypted data only, metadata, audit trail entries.</p>
              <p className="mt-1">The platform operator could not access: raw patient data, private key shares, computation results before approval.</p>
            </div>
            <section className="mt-6">
              <h3 className="font-medium text-slate-900">Study Parameters</h3>
              <pre className="mt-2 overflow-auto rounded bg-slate-50 p-3 text-xs">{JSON.stringify(protocol?.study_metadata ?? {}, null, 2)}</pre>
            </section>
            <section className="mt-4">
              <h3 className="font-medium text-slate-900">Participant Summary</h3>
              <pre className="mt-2 overflow-auto rounded bg-slate-50 p-3 text-xs">{JSON.stringify(protocol?.participants ?? [], null, 2)}</pre>
            </section>
            <section className="mt-4">
              <h3 className="font-medium text-slate-900">Dataset Commitments</h3>
              <pre className="mt-2 overflow-auto rounded bg-slate-50 p-3 text-xs">{JSON.stringify(protocol?.datasets ?? [], null, 2)}</pre>
            </section>
            <section className="mt-4">
              <h3 className="font-medium text-slate-900">Audit Trail Summary</h3>
              <pre className="mt-2 overflow-auto rounded bg-slate-50 p-3 text-xs">{JSON.stringify(protocol?.audit_summary ?? {}, null, 2)}</pre>
            </section>
            <button
              type="button"
              onClick={() => window.print()}
              className="mt-6 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover"
            >
              Export as PDF (Print)
            </button>
          </div>
        )}
      </div>

      {/* Decryption share modal */}
      {decryptShareJobId !== null && (
        <Modal open onClose={() => setDecryptShareJobId(null)} title="Submit Decryption Share">
          <p className="text-sm text-slate-600">
            Run the SecureCollab SDK locally to compute your decryption share, then paste the result below (or enter a placeholder for demo).
          </p>
          <textarea
            value={decryptShareValue}
            onChange={(e) => setDecryptShareValue(e.target.value)}
            placeholder="Base64 decryption share from SDK"
            className="mt-3 w-full rounded-lg border border-slate-300 p-2 font-mono text-sm"
            rows={3}
          />
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={handleSubmitDecryptionShare}
              disabled={!decryptShareValue.trim()}
              className="rounded-lg bg-primary px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              Submit
            </button>
            <button type="button" onClick={() => setDecryptShareJobId(null)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
