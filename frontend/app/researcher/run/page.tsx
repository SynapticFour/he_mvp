// SPDX-License-Identifier: Apache-2.0
"use client";

import { Badge } from "@/components/Badge";
import { useEmail } from "@/lib/email-context";
import { getJobResult, requestJob, getAlgorithms, type AlgorithmInfo } from "@/lib/api";
import { addRequest, getAccessList, getMyRequests, setRequestCompleted } from "@/lib/my-access";
import { useCallback, useEffect, useState } from "react";

export default function RunAnalysisPage() {
  const { email } = useEmail();
  const [accessList, setAccessList] = useState(getAccessList());
  const [algorithms, setAlgorithms] = useState<Record<string, AlgorithmInfo>>({});
  const [selectedDatasetId, setSelectedDatasetId] = useState<number | "">("");
  const [selectedAlgo, setSelectedAlgo] = useState<string>("descriptive_statistics");
  const [submittedJobId, setSubmittedJobId] = useState<number | null>(null);
  const [jobStatus, setJobStatus] = useState<"idle" | "pending" | "completed" | "rejected">("idle");
  const [resultValue, setResultValue] = useState<number | null>(null);
  const [resultJson, setResultJson] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRequests, setPendingRequests] = useState(getMyRequests().filter((r) => r.status === "pending"));

  const loadAccess = useCallback(() => {
    setAccessList(getAccessList());
  }, []);

  useEffect(() => {
    loadAccess();
    setPendingRequests(getMyRequests().filter((r) => r.status === "pending"));
  }, [loadAccess]);

  useEffect(() => {
    getAlgorithms().then(setAlgorithms);
  }, []);

  const algorithmList = Object.entries(algorithms).map(([id, info]) => ({ id, ...info }));

  async function checkJobStatus(jobId: number) {
    setLoading(true);
    setError(null);
    try {
      const job = await getJobResult(jobId);
      if (job.status === "completed") {
        setRequestCompleted(jobId);
        setSubmittedJobId(jobId);
        setJobStatus("completed");
        setResultValue(job.result ?? null);
        setResultJson(job.result_json ?? null);
        loadAccess();
        setPendingRequests(getMyRequests().filter((r) => r.status === "pending"));
      } else if (job.status === "rejected") {
        setJobStatus("rejected");
        setSubmittedJobId(jobId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!email || selectedDatasetId === "" || !accessList.length) return;
    setLoading(true);
    setError(null);
    try {
      const res = await requestJob(Number(selectedDatasetId), email, selectedAlgo);
      const ds = accessList.find((a) => a.datasetId === Number(selectedDatasetId));
      addRequest({
        datasetId: Number(selectedDatasetId),
        datasetName: ds?.datasetName ?? "",
        owner: ds?.owner ?? "",
        jobId: res.job_id,
        status: "pending",
      });
      setSubmittedJobId(res.job_id);
      setJobStatus("pending");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  function checkStatus() {
    if (submittedJobId != null) checkJobStatus(submittedJobId);
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Run Analysis</h1>
      <p className="mt-1 text-slate-600">
        Select a dataset you have access to and run an analysis. Results are computed on encrypted data.
      </p>
      {accessList.length === 0 ? (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
          You need access to at least one dataset. Request access from Browse Datasets first.
        </div>
      ) : (
        <div className="mt-8 grid gap-8 lg:grid-cols-2">
          <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <div>
              <label className="block text-sm font-medium text-slate-700">Dataset</label>
              <select
                value={selectedDatasetId}
                onChange={(e) =>
                  setSelectedDatasetId(e.target.value ? Number(e.target.value) : "")
                }
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900"
              >
                <option value="">Select dataset</option>
                {accessList.map((a) => (
                  <option key={a.jobId} value={a.datasetId}>
                    {a.datasetName}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Algorithm</label>
              <div className="mt-2 max-h-96 space-y-2 overflow-y-auto">
                {algorithmList.length === 0 ? (
                  <p className="text-sm text-slate-500">Loading algorithms…</p>
                ) : (
                  algorithmList.map((algo) => (
                    <label
                      key={algo.id}
                      className={`flex cursor-pointer flex-col rounded-lg border p-3 ${
                        selectedAlgo === algo.id
                          ? "border-accent bg-accent/5"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <input
                        type="radio"
                        name="algo"
                        value={algo.id}
                        checked={selectedAlgo === algo.id}
                        onChange={() => setSelectedAlgo(algo.id)}
                        className="sr-only"
                      />
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-medium text-slate-900">{algo.name}</p>
                          <p className="text-sm text-slate-600">{algo.description}</p>
                          <p className="mt-1 text-xs text-slate-500">
                            Est. {algo.estimated_seconds} s · {algo.clinical_use_case}
                          </p>
                        </div>
                        {algo.approximation_warning && (
                          <span
                            className="shrink-0 text-amber-600"
                            title={algo.approximation_warning}
                            aria-label="Approximation warning"
                          >
                            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                          </span>
                        )}
                      </div>
                      {algo.approximation_warning && (
                        <p className="mt-1 text-xs text-amber-700">{algo.approximation_warning}</p>
                      )}
                    </label>
                  ))
                )}
              </div>
            </div>
            <p className="text-xs text-slate-500">
              Column selection is determined by the algorithm. Results are computed on encrypted data.
            </p>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading || selectedDatasetId === ""}
              className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
            >
              {loading ? "Submitting…" : "Submit Request"}
            </button>
          </div>
          <div className="space-y-6">
            {pendingRequests.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="text-sm font-medium text-slate-900">Your pending requests</h3>
                <ul className="mt-2 space-y-2">
                  {pendingRequests.map((r) => (
                    <li
                      key={r.jobId}
                      className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
                    >
                      <span className="text-slate-700">{r.datasetName} (Job #{r.jobId})</span>
                      <button
                        type="button"
                        onClick={() => checkJobStatus(r.jobId)}
                        disabled={loading}
                        className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                      >
                        Check status
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-medium text-slate-900">Result</h2>
              {error && (
                <p className="mt-2 text-sm text-red-600">{error}</p>
              )}
              {jobStatus === "idle" && !submittedJobId && (
                <p className="mt-4 text-sm text-slate-500">
                  Submit a request to see status and result here.
                </p>
              )}
              {jobStatus === "pending" && (
                <div className="mt-4">
                  <Badge variant="pending">Waiting for owner approval…</Badge>
                  <p className="mt-2 text-sm text-slate-600">
                    Job ID: {submittedJobId}. The data owner must approve your request.
                  </p>
                  <button
                    type="button"
                    onClick={checkStatus}
                    disabled={loading}
                    className="mt-3 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                  >
                    {loading ? "Checking…" : "Check Status"}
                  </button>
                </div>
              )}
              {jobStatus === "rejected" && (
                <p className="mt-4 text-sm text-slate-600">
                  This request was rejected by the data owner.
                </p>
              )}
              {jobStatus === "completed" && (resultValue != null || resultJson) && (
                <div className="mt-4 rounded-lg bg-success/10 p-4">
                  {resultJson && typeof resultJson === "object" && Object.keys(resultJson).length > 0 ? (
                    <div className="space-y-2">
                      <pre className="overflow-x-auto rounded bg-white/50 p-2 text-sm text-slate-800">
                        {JSON.stringify(resultJson, null, 2)}
                      </pre>
                      {resultValue != null && (
                        <p className="text-lg font-semibold text-success">
                          Mean: {Number(resultValue).toFixed(2)}
                        </p>
                      )}
                      <p className="text-sm text-slate-600">
                        Computed on encrypted data – source data was never decrypted.
                      </p>
                    </div>
                  ) : (
                    <>
                      <p className="text-2xl font-semibold text-success">
                        Result: {resultValue != null ? Number(resultValue).toFixed(2) : "—"}
                      </p>
                      <p className="mt-2 text-sm text-slate-600">
                        Computed on encrypted data – source data was never decrypted.
                      </p>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
