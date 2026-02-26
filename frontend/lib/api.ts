// SPDX-License-Identifier: Apache-2.0
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type AlgorithmInfo = {
  name: string;
  description: string;
  required_columns: number;
  column_types: string[];
  parameters: Record<string, unknown>;
  estimated_seconds: number;
  approximation_warning: string | null;
  clinical_use_case: string;
};

export async function getAlgorithms(): Promise<Record<string, AlgorithmInfo>> {
  const res = await fetch(`${API_BASE}/algorithms`);
  if (!res.ok) return {};
  return res.json();
}

export type Dataset = {
  id: number;
  name: string;
  description: string;
  owner_email: string;
  created_at: string;
};

export type PendingJob = {
  id: number;
  dataset_id: number;
  requester_email: string;
  computation_type: string;
  status: string;
  created_at: string;
};

export type JobResult = {
  id: number;
  dataset_id: number;
  requester_email: string;
  computation_type: string;
  status: string;
  created_at: string;
  result?: number;
  result_json?: Record<string, unknown>;
};

// --- Study types & API ---

export type StudyListItem = {
  id: number;
  name: string;
  description: string;
  status: string;
  threshold_n: number;
  threshold_t: number;
  participant_count: number;
  dataset_count: number;
  pending_approvals: number;
  created_at: string;
};

export type StudyDetail = {
  id: number;
  name: string;
  description: string;
  status: string;
  threshold_n: number;
  threshold_t: number;
  public_key_fingerprint: string;
  combined_public_key: string | null;
  protocol: { allowed_algorithms?: string[]; column_definitions?: unknown[] };
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type StudyProtocol = {
  study_metadata: StudyDetail & { updated_at: string };
  participants: { institution_name: string; institution_email: string; joined_at: string }[];
  allowed_algorithms: string[];
  column_definitions: unknown[];
  datasets: { dataset_name: string; institution_email: string; commitment_hash: string; committed_at: string }[];
  jobs: { id: number; requester_email: string; algorithm: string; status: string; created_at: string }[];
  audit_summary: { total_entries: number; last_entry_hash: string | null };
};

export type AuditEntry = {
  id: number;
  action_type: string;
  actor_email: string;
  details: Record<string, unknown>;
  previous_hash: string;
  entry_hash: string;
  created_at: string;
};

export type StudyPublicKey = {
  combined_public_key: string | null;
  public_key_fingerprint: string;
  upload_commitments: { dataset_name: string; commitment_hash: string; institution_email: string }[];
};

export async function getStudies(participantEmail: string): Promise<StudyListItem[]> {
  const res = await fetch(`${API_BASE}/studies?participant_email=${encodeURIComponent(participantEmail)}`);
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function getStudy(studyId: number): Promise<StudyDetail> {
  const res = await fetch(`${API_BASE}/studies/${studyId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Study not found");
  }
  return res.json();
}

export async function createStudy(body: {
  name: string;
  description: string;
  creator_email: string;
  institution_name: string;
  threshold_t: number;
  threshold_n: number;
  allowed_algorithms: string[];
  column_definitions?: unknown[];
  public_key_share?: string;
}): Promise<{ study_id: number }> {
  const res = await fetch(`${API_BASE}/studies/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Create study failed");
  }
  return res.json();
}

export async function joinStudy(
  studyId: number,
  body: { institution_email: string; institution_name: string; public_key_share: string }
): Promise<{ study_id: number; status: string }> {
  const res = await fetch(`${API_BASE}/studies/${studyId}/join`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Join failed");
  }
  return res.json();
}

export async function getStudyPublicKey(studyId: number): Promise<StudyPublicKey> {
  const res = await fetch(`${API_BASE}/studies/${studyId}/public_key`);
  if (!res.ok) throw new Error("Failed to fetch public key");
  return res.json();
}

export async function uploadStudyDataset(
  studyId: number,
  file: File,
  institutionEmail: string,
  datasetName: string,
  columns: string[],
  commitmentTimestamp?: string
): Promise<{ commitment_hash: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("institution_email", institutionEmail);
  form.append("dataset_name", datasetName);
  form.append("columns", JSON.stringify(columns));
  if (commitmentTimestamp) form.append("commitment_timestamp", commitmentTimestamp);
  const res = await fetch(`${API_BASE}/studies/${studyId}/upload_dataset`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function requestStudyComputation(
  studyId: number,
  body: { requester_email: string; algorithm: string; selected_columns: string[]; parameters?: Record<string, unknown> }
): Promise<{ job_id: number }> {
  const res = await fetch(`${API_BASE}/studies/${studyId}/request_computation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export async function approveStudyJob(
  studyId: number,
  jobId: number,
  institutionEmail: string
): Promise<{ job_id: number; status: string; approvals?: number; required?: number }> {
  const res = await fetch(`${API_BASE}/studies/${studyId}/jobs/${jobId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ institution_email: institutionEmail }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Approve failed");
  }
  return res.json();
}

export async function submitDecryptionShare(
  studyId: number,
  jobId: number,
  institutionEmail: string,
  decryptionShare: string
): Promise<{ job_id: number; status: string; result_json?: unknown }> {
  const res = await fetch(`${API_BASE}/studies/${studyId}/jobs/${jobId}/submit_decryption_share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ institution_email: institutionEmail, decryption_share: decryptionShare }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Submit share failed");
  }
  return res.json();
}

export async function getStudyAuditTrail(studyId: number): Promise<AuditEntry[]> {
  const res = await fetch(`${API_BASE}/studies/${studyId}/audit_trail`);
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function getStudyProtocol(studyId: number): Promise<StudyProtocol> {
  const res = await fetch(`${API_BASE}/studies/${studyId}/protocol`);
  if (!res.ok) throw new Error("Failed to fetch protocol");
  return res.json();
}

export async function uploadDataset(
  file: File,
  name: string,
  description: string,
  owner_email: string
): Promise<{ dataset_id: number }> {
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  form.append("description", description);
  form.append("owner_email", owner_email);
  const res = await fetch(`${API_BASE}/datasets/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export async function getDatasets(): Promise<Dataset[]> {
  const res = await fetch(`${API_BASE}/datasets`);
  if (!res.ok) throw new Error("Failed to fetch datasets");
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function getPendingJobs(ownerEmail: string): Promise<PendingJob[]> {
  const res = await fetch(
    `${API_BASE}/jobs/pending/${encodeURIComponent(ownerEmail)}`
  );
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function approveJob(jobId: number): Promise<{ result: number }> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/approve`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Approve failed");
  }
  return res.json();
}

export async function rejectJob(jobId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/reject`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Reject failed");
  }
}

export async function requestJob(
  dataset_id: number,
  requester_email: string,
  algorithm: string = "mean",
  selected_columns: string[] = []
): Promise<{ job_id: number }> {
  const res = await fetch(`${API_BASE}/jobs/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id,
      requester_email,
      computation_type: algorithm,
      algorithm,
      selected_columns,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export async function getJobResult(jobId: number): Promise<JobResult> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/result`);
  if (!res.ok) throw new Error("Failed to fetch job");
  return res.json();
}
