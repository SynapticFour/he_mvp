// SPDX-License-Identifier: Apache-2.0
import { useState, useCallback } from "react";

export function useAuditTrail(studyId: number | null) {
  const [entries, setEntries] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(false);
  const fetchAuditTrail = useCallback(async () => {
    if (!studyId) return;
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiBase}/studies/${studyId}/audit_trail`);
      if (res.ok) setEntries(await res.json());
    } finally {
      setLoading(false);
    }
  }, [studyId]);
  return { entries, loading, fetchAuditTrail };
}
