// SPDX-License-Identifier: Apache-2.0
"use client";

import { StatCard } from "@/components/StatCard";
import { useEmail } from "@/lib/email-context";
import { getDatasets } from "@/lib/api";
import { getAccessList, getMyRequests } from "@/lib/my-access";
import { useCallback, useEffect, useState } from "react";

export default function ResearcherOverviewPage() {
  const { email } = useEmail();
  const [datasetsCount, setDatasetsCount] = useState(0);
  const [accessCount, setAccessCount] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const ds = await getDatasets();
      setDatasetsCount(ds.length);
      const access = getAccessList();
      const all = getMyRequests();
      setAccessCount(access.length);
      setPendingCount(all.filter((r) => r.status === "pending").length);
    } catch {
      setDatasetsCount(0);
      setAccessCount(0);
      setPendingCount(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Overview</h1>
      <p className="mt-1 text-slate-600">
        Browse datasets, request access, and run analyses on encrypted data.
      </p>
      {loading ? (
        <p className="mt-8 text-sm text-slate-500">Loading…</p>
      ) : (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <StatCard label="Available Datasets" value={datasetsCount} />
            <StatCard label="Datasets with Access" value={accessCount} />
            <StatCard label="Pending Requests" value={pendingCount} />
          </div>
          <div className="mt-10 rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-medium text-slate-900">Quick actions</h2>
            <p className="mt-2 text-sm text-slate-600">
              Go to Browse Datasets to request access, or Run Analysis to
              submit a computation on a dataset you already have access to.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
