// SPDX-License-Identifier: Apache-2.0
"use client";

import { useEmail } from "@/lib/email-context";
import { useEffect, useState } from "react";

export function EmailModal() {
  const { email, setEmail, isReady } = useEmail();
  const [input, setInput] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (isReady && !email) setOpen(true);
  }, [isReady, email]);

  const submit = () => {
    const v = input.trim();
    if (v) {
      setEmail(v);
      setOpen(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-slate-900">
          Welcome to SecureCollab
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          Enter your email to continue. It will be stored locally and used as
          your identity for requests and access.
        </p>
        <input
          type="email"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="you@company.com"
          className="mt-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder-slate-400 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={submit}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
