// SPDX-License-Identifier: Apache-2.0
"use client";

import { Badge } from "@/components/Badge";
import { Modal } from "@/components/Modal";
import { SlideOver } from "@/components/SlideOver";
import { useEmail } from "@/lib/email-context";
import {
  approveJob,
  getDatasets,
  getPendingJobs,
  uploadDataset,
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
    });
  } catch {
    return s;
  }
}

export default function MyDatasetsPage() {
  const { email } = useEmail();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [pending, setPending] = useState<PendingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [manageDataset, setManageDataset] = useState<Dataset | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [approvingId, setApprovingId] = useState<number | null>(null);

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

  const pendingByDataset = manageDataset
    ? pending.filter((j) => j.dataset_id === manageDataset.id)
    : [];

  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const name = (form.elements.namedItem("name") as HTMLInputElement).value.trim();
    const description = (form.elements.namedItem("description") as HTMLInputElement).value.trim();
    const file = (form.elements.namedItem("file") as HTMLInputElement).files?.[0];
    if (!file || !email) {
      setUploadError("Name, description and file are required.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      await uploadDataset(file, name, description, email);
      setUploadOpen(false);
      form.reset();
      load();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleApprove(jobId: number) {
    setApprovingId(jobId);
    try {
      await approveJob(jobId);
      await load();
      setManageDataset((prev) => (prev ? { ...prev } : null));
    } finally {
      setApprovingId(null);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">My Datasets</h1>
          <p className="mt-1 text-slate-600">
            Manage your uploaded encrypted datasets and access.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setUploadOpen(true)}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover"
        >
          Upload New Dataset
        </button>
      </div>

      {loading ? (
        <p className="mt-8 text-sm text-slate-500">Loading…</p>
      ) : (
        <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead>
              <tr>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Name
                </th>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Description
                </th>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Upload Date
                </th>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  # Researchers
                </th>
                <th className="bg-slate-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  Status
                </th>
                <th className="bg-slate-50 px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {datasets.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-500">
                    No datasets yet. Upload your first encrypted dataset.
                  </td>
                </tr>
              ) : (
                datasets.map((d) => {
                  const count = pending.filter((j) => j.dataset_id === d.id).length;
                  return (
                    <tr key={d.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 text-sm font-medium text-slate-900">
                        {d.name}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600">
                        {d.description}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600">
                        {formatDate(d.created_at)}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-600">
                        {count}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="success">active</Badge>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => setManageDataset(d)}
                          className="text-sm font-medium text-accent hover:underline"
                        >
                          Manage Access
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={uploadOpen}
        onClose={() => {
          setUploadOpen(false);
          setUploadError(null);
        }}
        title="Upload New Dataset"
      >
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Name
            </label>
            <input
              name="name"
              required
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Description
            </label>
            <input
              name="description"
              required
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Encrypted file (.bin)
            </label>
            <input
              name="file"
              type="file"
              accept=".bin"
              required
              className="mt-1 block w-full text-sm text-slate-600"
            />
          </div>
          {uploadError && (
            <p className="text-sm text-red-600">{uploadError}</p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setUploadOpen(false)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={uploading}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
            >
              {uploading ? "Uploading…" : "Upload"}
            </button>
          </div>
        </form>
      </Modal>

      <SlideOver
        open={!!manageDataset}
        onClose={() => setManageDataset(null)}
        title={manageDataset ? `Access: ${manageDataset.name}` : ""}
      >
        {manageDataset && (
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-medium text-slate-900">
                Pending requests
              </h3>
              {pendingByDataset.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">
                  No pending requests for this dataset.
                </p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {pendingByDataset.map((j) => (
                    <li
                      key={j.id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
                    >
                      <div>
                        <p className="font-medium text-slate-900">
                          {j.requester_email}
                        </p>
                        <p className="text-slate-500">
                          {j.computation_type} · {formatDate(j.created_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={approvingId !== null}
                        onClick={() => handleApprove(j.id)}
                        className="rounded bg-success px-3 py-1 text-xs font-medium text-white hover:bg-success/90 disabled:opacity-50"
                      >
                        {approvingId === j.id ? "…" : "Approve"}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="text-xs text-slate-500">
              Researchers with access are those who have received at least one
              approved result for this dataset.
            </p>
          </div>
        )}
      </SlideOver>
    </div>
  );
}
