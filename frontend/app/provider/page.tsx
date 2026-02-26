// SPDX-License-Identifier: Apache-2.0
"use client";

import { StatCard } from "@/components/StatCard";
import { useEmail } from "@/lib/email-context";
import {
  getDatasets,
  getPendingJobs,
  type Dataset,
  type PendingJob,
} from "@/lib/api";
import { useEffect, useState } from "react";

function formatDate(s: string) {
  try {
    return new Date(s).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return s;
  }
}

export default function ProviderOverviewPage() {
  const { email } = useEmail();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [pending, setPending] = useState<PendingJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!email) return;
    (async () => {
      try {
        const [d, p] = await Promise.all([
          getDatasets().then((list) => list.filter((x) => x.owner_email === email)),
          getPendingJobs(email),
        ]);
        setDatasets(d);
        setPending(p);
      } catch {
        setDatasets([]);
        setPending([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [email]);

  const activeResearchers = new Set(
    pending.map((j) => j.requester_email)
  ).size;

  const recentActivity = [
    ...pending.slice(0, 5).map((j) => ({
      type: "request" as const,
      text: `${j.requester_email} requested analysis on dataset #${j.dataset_id}`,
      time: j.created_at,
    })),
  ].sort(
    (a, b) =>
      new Date(b.time).getTime() - new Date(a.time).getTime()
  );

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Overview</h1>
      <p className="mt-1 text-slate-600">
        Your data provider dashboard and recent activity.
      </p>
      {loading ? (
        <p className="mt-6 text-sm text-slate-500">Loading…</p>
      ) : (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <StatCard label="Datasets Uploaded" value={datasets.length} />
            <StatCard label="Active Researchers" value={activeResearchers} />
            <StatCard label="Pending Approvals" value={pending.length} />
          </div>
          <div className="mt-10">
            <h2 className="text-lg font-medium text-slate-900">
              Recent activity
            </h2>
            <ul className="mt-4 space-y-3">
              {recentActivity.length === 0 ? (
                <li className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                  No recent activity.
                </li>
              ) : (
                recentActivity.map((a, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm"
                  >
                    <span className="text-slate-700">{a.text}</span>
                    <span className="text-slate-400">
                      {formatDate(a.time)}
                    </span>
                  </li>
                ))
              )}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
