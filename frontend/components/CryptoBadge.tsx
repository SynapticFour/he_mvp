// SPDX-License-Identifier: Apache-2.0
"use client";

/**
 * Shows cryptographic verification status for non-technical users.
 * Green shield = verified; yellow = verification pending.
 */
export function CryptoBadge({
  verified,
  label,
}: {
  verified: boolean;
  label?: string;
}) {
  const text = label ?? (verified ? "Cryptographically Verified" : "Verification Pending");
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium ${
        verified
          ? "bg-success/15 text-success"
          : "bg-warning/15 text-amber-700"
      }`}
      title={verified ? "This item has been cryptographically verified." : "Verification is still pending."}
    >
      {verified ? (
        <ShieldCheckIcon className="h-3.5 w-3.5 shrink-0" />
      ) : (
        <ShieldAlertIcon className="h-3.5 w-3.5 shrink-0" />
      )}
      {text}
    </span>
  );
}

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}

function ShieldAlertIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  );
}
