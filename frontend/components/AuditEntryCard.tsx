// SPDX-License-Identifier: Apache-2.0
"use client";

import type { AuditEntry as AuditEntryType } from "@/lib/api";
import { CommitmentHash } from "./CommitmentHash";

export function AuditEntryCard({ entry }: { entry: AuditEntryType }) {
  const detailsStr = Object.keys(entry.details || {}).length > 0
    ? JSON.stringify(entry.details)
    : "—";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{entry.action_type.replace(/_/g, " ")}</p>
          <p className="text-sm text-slate-500">
            {new Date(entry.created_at).toLocaleString()} · {entry.actor_email}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Entry hash</span>
          <CommitmentHash hash={entry.entry_hash} title="Hash of this entry; chained to the previous for integrity." />
        </div>
      </div>
      {detailsStr !== "—" && (
        <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-600">
          {detailsStr}
        </pre>
      )}
    </div>
  );
}
