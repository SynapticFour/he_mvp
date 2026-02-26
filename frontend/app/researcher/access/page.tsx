// SPDX-License-Identifier: Apache-2.0
"use client";

import Link from "next/link";
import { getAccessList } from "@/lib/my-access";
import { useEffect, useState } from "react";

function formatDate(_s: string) {
  return "After approval";
}

export default function MyAccessPage() {
  const [access, setAccess] = useState(getAccessList());

  useEffect(() => {
    setAccess(getAccessList());
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">My Access</h1>
      <p className="mt-1 text-slate-600">
        Datasets you have been granted access to. Run analyses from here or the Run Analysis page.
      </p>
      {access.length === 0 ? (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
          You don&apos;t have access to any datasets yet. Request access from Browse Datasets.
        </div>
      ) : (
        <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead>
              <tr>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Dataset
                </th>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Owner
                </th>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Access granted
                </th>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Available algorithms
                </th>
                <th className="bg-slate-50 px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {access.map((a) => (
                <tr key={a.jobId} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm font-medium text-slate-900">
                    {a.datasetName}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {a.owner}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {formatDate("")}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-600">
                    Mean, Descriptive Statistics, Correlation, t-Test, Regression, Distribution
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href="/researcher/run"
                      className="text-sm font-medium text-accent hover:underline"
                    >
                      Run Analysis
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
