// SPDX-License-Identifier: Apache-2.0
const STORAGE_KEY = "securecollab_my_requests";

export type MyRequest = {
  datasetId: number;
  datasetName: string;
  owner: string;
  jobId: number;
  status: "pending" | "completed";
};

export function getMyRequests(): MyRequest[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addRequest(req: MyRequest) {
  const list = getMyRequests();
  if (list.some((r) => r.jobId === req.jobId)) return;
  list.push(req);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

export function setRequestCompleted(jobId: number) {
  const list = getMyRequests();
  const i = list.findIndex((r) => r.jobId === jobId);
  if (i >= 0) {
    list[i].status = "completed";
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  }
}

export function hasAccess(datasetId: number): boolean {
  return getMyRequests().some(
    (r) => r.datasetId === datasetId && r.status === "completed"
  );
}

export function getAccessList(): MyRequest[] {
  return getMyRequests().filter((r) => r.status === "completed");
}
