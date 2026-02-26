"use client";

import { useEmail } from "@/lib/email-context";
import { getDatasets, getPendingJobs, type Dataset, type PendingJob } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

export default function AccessManagementPage() {
  const { email } = useEmail();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [pending, setPending] = useState<PendingJob[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!email) return;
    try {
      const [d, p] = await Promise.all([
        getDatasets(),
        getPendingJobs(email),
      ]);
      setDatasets(d.filter((x) => x.owner_email === email));
      setPending(p);
    } catch {
      setDatasets([]);
      setPending([]);
    } finally {
      setLoading(false);
    }
  }, [email]);

  useEffect(() => {
    load();
  }, [load]);

  const pendingByDataset = datasets.map((ds) => ({
    dataset: ds,
    requests: pending.filter((j) => j.dataset_id === ds.id),
  }));

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">
        Access Management
      </h1>
      <p className="mt-1 text-slate-600">
        Overview of your datasets and pending access requests.
      </p>
      {loading ? (
        <p className="mt-8 text-sm text-slate-500">Loading…</p>
      ) : (
        <div className="mt-6 space-y-6">
          {pendingByDataset.map(({ dataset, requests }) => (
            <div
              key={dataset.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-medium text-slate-900">{dataset.name}</h2>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                  {requests.length} pending
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">{dataset.description}</p>
              {requests.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {requests.map((j) => (
                    <li
                      key={j.id}
                      className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm"
                    >
                      <span className="text-slate-700">{j.requester_email}</span>
                      <span className="text-slate-500">{j.computation_type}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          {datasets.length === 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
              No datasets. Upload one from My Datasets.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
