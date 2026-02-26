// SPDX-License-Identifier: Apache-2.0
"use client";

import { useEmail } from "@/lib/email-context";
import { getStudies, type StudyListItem } from "@/lib/api";
import { useEffect, useState } from "react";
import Link from "next/link";
import { CryptoBadge } from "@/components/CryptoBadge";
import { Badge } from "@/components/Badge";

export default function StudiesPage() {
  const { email } = useEmail();
  const [studies, setStudies] = useState<StudyListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!email) return;
    getStudies(email)
      .then(setStudies)
      .catch(() => setStudies([]))
      .finally(() => setLoading(false));
  }, [email]);

  const statusVariant = (s: string) =>
    s === "active" ? "success" : s === "draft" ? "pending" : s === "completed" ? "default" : "warning";

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">My Studies</h1>
      <p className="mt-1 text-slate-600">
        Multi-party studies you are participating in. Each study is cryptographically protected.
      </p>

      {!email && (
        <p className="mt-4 rounded-lg bg-amber-50 p-4 text-amber-800">
          Enter your email (top of sidebar) to see studies for your institution.
        </p>
      )}

      {email && loading && <p className="mt-4 text-slate-500">Loading…</p>}

      {email && !loading && studies.length === 0 && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-8 text-center">
          <p className="text-slate-600">No studies yet.</p>
          <Link
            href="/studies/new"
            className="mt-4 inline-flex rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            Create New Study
          </Link>
        </div>
      )}

      {email && !loading && studies.length > 0 && (
        <div className="mt-6 space-y-4">
          {studies.map((s) => (
            <Link
              key={s.id}
              href={`/studies/${s.id}`}
              className="block rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-accent/30 hover:shadow-md"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-slate-900">{s.name}</h2>
                  {s.description && (
                    <p className="mt-1 text-sm text-slate-600 line-clamp-2">{s.description}</p>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={statusVariant(s.status)}>{s.status}</Badge>
                  {s.status === "active" && (
                    <CryptoBadge verified={s.status === "active"} label="Cryptographically Active" />
                  )}
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-6 text-sm text-slate-500">
                <span>Participants: {s.participant_count}</span>
                <span>Datasets: {s.dataset_count}</span>
                <span>Threshold: {s.threshold_t} of {s.threshold_n}</span>
                {s.pending_approvals > 0 && (
                  <span className="text-warning">{s.pending_approvals} pending approvals</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
