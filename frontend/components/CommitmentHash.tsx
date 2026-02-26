// SPDX-License-Identifier: Apache-2.0
"use client";

import { useState } from "react";

const TOOLTIP =
  "A commitment hash is a cryptographic fingerprint of your data and the key used to encrypt it. " +
  "You can save it locally and later verify that the server stores the same hash—proving your upload was recorded correctly.";

const TRUNCATE_LEN = 12;

export function CommitmentHash({
  hash,
  title,
}: {
  hash: string;
  title?: string;
}) {
  const [copied, setCopied] = useState(false);
  const display = hash.length > TRUNCATE_LEN * 2 ? `${hash.slice(0, TRUNCATE_LEN)}…${hash.slice(-TRUNCATE_LEN)}` : hash;

  const copy = () => {
    void navigator.clipboard.writeText(hash).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="flex items-center gap-2">
      <code
        className="rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700"
        title={title ?? TOOLTIP}
      >
        {display}
      </code>
      <button
        type="button"
        onClick={copy}
        className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-700"
        title="Copy full hash"
      >
        {copied ? (
          <span className="text-xs text-success">Copied</span>
        ) : (
          <CopyIcon className="h-3.5 w-3.5" />
        )}
      </button>
      <span className="text-slate-400" title={TOOLTIP}>
        <InfoIcon className="h-3.5 w-3.5" />
      </span>
    </div>
  );
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  );
}

function InfoIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
