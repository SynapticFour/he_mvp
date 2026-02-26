// SPDX-License-Identifier: Apache-2.0
"use client";

import { Badge } from "@/components/Badge";
import { useEmail } from "@/lib/email-context";
import {
  approveJob,
  getDatasets,
  getPendingJobs,
  rejectJob,
  type Dataset,
  type PendingJob,
} from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

function formatDate(s: string) {
  try {
    return new Date(s).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return s;
  }
}

export default function PendingRequestsPage() {
  const { email } = useEmail();
  const [pending, setPending] = useState<PendingJob[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [approvedResult, setApprovedResult] = useState<{
    jobId: number;
    result: number;
  } | null>(null);

  const load = useCallback(async () => {
    if (!email) return;
    try {
      const [p, d] = await Promise.all([
        getPendingJobs(email),
        getDatasets(),
      ]);
      setPending(p);
      setDatasets(d);
    } catch {
      setPending([]);
      setDatasets([]);
    } finally {
      setLoading(false);
    }
  }, [email]);

  useEffect(() => {
    load();
  }, [load]);

  const datasetMap = new Map(datasets.map((x) => [x.id, x]));

  async function handleApprove(job: PendingJob) {
    setApprovingId(job.id);
    setApprovedResult(null);
    try {
      const res = await approveJob(job.id);
      setApprovedResult({ jobId: job.id, result: res.result });
      await load();
    } finally {
      setApprovingId(null);
    }
  }

  async function handleReject(job: PendingJob) {
    setRejectingId(job.id);
    try {
      await rejectJob(job.id);
      await load();
    } finally {
      setRejectingId(null);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">
        Pending Requests
      </h1>
      <p className="mt-1 text-slate-600">
        Review and approve or reject analysis requests from researchers.
      </p>
      {loading ? (
        <p className="mt-8 text-sm text-slate-500">Loading…</p>
      ) : pending.length === 0 ? (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
          No pending requests.
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {pending.map((job) => {
            const ds = datasetMap.get(job.dataset_id);
            const showResult = approvedResult?.jobId === job.id;
            return (
              <div
                key={job.id}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <p className="text-sm font-medium text-slate-900">
                  {job.requester_email}
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  Dataset: {ds?.name ?? `#${job.dataset_id}`}
                </p>
                <p className="text-sm text-slate-500">
                  Algorithm: {job.computation_type}
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  {formatDate(job.created_at)}
                </p>
                {showResult && (
                  <div className="mt-3 rounded-lg bg-success/10 p-3 text-sm text-success">
                    <strong>Result: {Number(approvedResult!.result).toFixed(2)}</strong>
                    <br />
                    <span className="text-xs">
                      Computed on encrypted data – source never decrypted.
                    </span>
                  </div>
                )}
                {!showResult && (
                  <div className="mt-4 flex gap-2">
                    <button
                      type="button"
                      disabled={approvingId !== null}
                      onClick={() => handleApprove(job)}
                      className="rounded-lg bg-success px-3 py-1.5 text-sm font-medium text-white hover:bg-success/90 disabled:opacity-50"
                    >
                      {approvingId === job.id ? "…" : "Approve"}
                    </button>
                    <button
                      type="button"
                      disabled={rejectingId !== null}
                      onClick={() => handleReject(job)}
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                    >
                      {rejectingId === job.id ? "…" : "Reject"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
