// SPDX-License-Identifier: Apache-2.0
import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-primary text-white">
      <div className="mx-auto max-w-5xl px-6 py-20">
        <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
          Collaborate on sensitive clinical data without ever exposing it.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-slate-300">
          SecureCollab enables pharma companies to share encrypted datasets and
          researchers to run analyses on encrypted data. Results are computed
          without ever decrypting the source—privacy by design.
        </p>
        <div className="mt-12 grid gap-8 md:grid-cols-3">
          <div className="flex flex-col items-center rounded-xl border border-white/10 bg-white/5 p-6 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/20 text-accent">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
            </div>
            <h2 className="mt-4 font-semibold text-white">Upload Encrypted</h2>
            <p className="mt-2 text-sm text-slate-400">
              Data owners upload datasets that stay encrypted. No one can read raw values.
            </p>
          </div>
          <div className="flex flex-col items-center rounded-xl border border-white/10 bg-white/5 p-6 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/20 text-accent">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <h2 className="mt-4 font-semibold text-white">Request Analysis</h2>
            <p className="mt-2 text-sm text-slate-400">
              Researchers request computations (e.g. mean, regression). Owners approve or reject.
            </p>
          </div>
          <div className="flex flex-col items-center rounded-xl border border-white/10 bg-white/5 p-6 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/20 text-accent">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h2 className="mt-4 font-semibold text-white">Get Results</h2>
            <p className="mt-2 text-sm text-slate-400">
              After approval, results are computed on encrypted data and only the aggregate is revealed.
            </p>
          </div>
        </div>
        <div className="mt-16 flex flex-wrap gap-4">
          <Link
            href="/studies"
            className="rounded-lg border-2 border-white/40 px-6 py-3 font-medium text-white transition hover:bg-white/10"
          >
            My Studies
          </Link>
          <Link
            href="/provider"
            className="rounded-lg bg-accent px-6 py-3 font-medium text-white shadow-lg transition hover:bg-accent-hover"
          >
            I have data to share
          </Link>
          <Link
            href="/researcher"
            className="rounded-lg border-2 border-white/40 px-6 py-3 font-medium text-white transition hover:bg-white/10"
          >
            I want to analyze data
          </Link>
        </div>
      </div>
    </main>
  );
}
