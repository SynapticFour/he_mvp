// SPDX-License-Identifier: Apache-2.0
"use client";

import { Badge } from "@/components/Badge";
import { useEmail } from "@/lib/email-context";
import { getDatasets, requestJob } from "@/lib/api";
import { addRequest, hasAccess } from "@/lib/my-access";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function BrowseDatasetsPage() {
  const { email } = useEmail();
  const [datasets, setDatasets] = useState<Awaited<ReturnType<typeof getDatasets>>>([]);
  const [loading, setLoading] = useState(true);
  const [requestingId, setRequestingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const d = await getDatasets();
      setDatasets(d);
    } catch {
      setDatasets([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRequestAccess(d: (typeof datasets)[0]) {
    if (!email) return;
    setRequestingId(d.id);
    setError(null);
    try {
      const res = await requestJob(d.id, email, "mean");
      addRequest({
        datasetId: d.id,
        datasetName: d.name,
        owner: d.owner_email,
        jobId: res.job_id,
        status: "pending",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setRequestingId(null);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">
        Browse Datasets
      </h1>
      <p className="mt-1 text-slate-600">
        Request access to encrypted datasets. After approval you can run analyses.
      </p>
      {error && (
        <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {loading ? (
        <p className="mt-8 text-sm text-slate-500">Loading…</p>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {datasets.map((d) => {
            const access = hasAccess(d.id);
            return (
              <div
                key={d.id}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <h2 className="font-medium text-slate-900">{d.name}</h2>
                <p className="mt-2 text-sm text-slate-600">{d.description}</p>
                <p className="mt-2 text-xs text-slate-500">
                  Owner: {d.owner_email}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Available algorithms: Mean (more coming soon)
                </p>
                <div className="mt-4">
                  {access ? (
                    <Link
                      href="/researcher/run"
                      className="inline-flex rounded-lg bg-success px-4 py-2 text-sm font-medium text-white hover:bg-success/90"
                    >
                      Run Analysis
                    </Link>
                  ) : (
                    <button
                      type="button"
                      disabled={requestingId !== null}
                      onClick={() => handleRequestAccess(d)}
                      className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
                    >
                      {requestingId === d.id ? "Requesting…" : "Request Access"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          {datasets.length === 0 && (
            <div className="col-span-full rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
              No datasets available.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
