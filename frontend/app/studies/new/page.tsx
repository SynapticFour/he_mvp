// SPDX-License-Identifier: Apache-2.0
"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEmail } from "@/lib/email-context";
import { createStudy } from "@/lib/api";
import { ThresholdVisualizer } from "@/components/ThresholdVisualizer";

const ALGORITHMS: { id: string; label: string; description: string }[] = [
  { id: "descriptive_statistics", label: "Descriptive Statistics", description: "Mean, Std Dev, Variance, IQR, Skewness" },
  { id: "correlation", label: "Correlation Analysis", description: "Pearson correlation between two columns" },
  { id: "group_comparison", label: "Group Comparison (t-Test)", description: "Compare two groups" },
  { id: "linear_regression", label: "Linear Regression", description: "Slope and intercept (one predictor, one target)" },
  { id: "distribution", label: "Distribution Overview", description: "Histogram approximation" },
  { id: "multi_group_comparison", label: "Multi-Group Comparison", description: "ANOVA-style: mean/std per group, pairwise differences" },
  { id: "logistic_regression_approx", label: "Logistic Regression (Approx)", description: "Binary outcome; exploratory only" },
  { id: "pearson_correlation_matrix", label: "Pearson Correlation Matrix", description: "Full matrix for 2–6 columns (GWAS-style)" },
  { id: "survival_analysis_approx", label: "Survival Analysis (Approx)", description: "Hazard rate, median survival approximation" },
  { id: "prevalence_and_risk", label: "Prevalence and Risk", description: "Prevalence, Relative Risk, Odds Ratio" },
  { id: "federated_mean_aggregation", label: "Federated Mean Aggregation", description: "Weighted mean for meta-analysis" },
  { id: "subgroup_analysis", label: "Subgroup Analysis", description: "Stats per subgroup (mask columns)" },
];

const STEPS = ["Study Setup", "Allowed Algorithms", "Invite Participants", "Review & Create"];

export default function NewStudyPage() {
  const router = useRouter();
  const { email } = useEmail();
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [institutionName, setInstitutionName] = useState("");
  const [creatorEmail, setCreatorEmail] = useState(email ?? "");
  const [thresholdN, setThresholdN] = useState(3);
  const [thresholdT, setThresholdT] = useState(2);
  const [allowedAlgorithms, setAllowedAlgorithms] = useState<string[]>([]);
  const [participantEmails, setParticipantEmails] = useState<string[]>([""]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const toggleAlgorithm = (id: string) => {
    setAllowedAlgorithms((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  };

  const addParticipant = () => setParticipantEmails((p) => [...p, ""]);
  const setParticipantEmail = (i: number, v: string) => {
    setParticipantEmails((p) => {
      const next = [...p];
      next[i] = v;
      return next;
    });
  };
  const removeParticipant = (i: number) => {
    setParticipantEmails((p) => p.filter((_, j) => j !== i));
  };

  const handleCreate = async () => {
    setError("");
    setSubmitting(true);
    try {
      const { study_id } = await createStudy({
        name,
        description,
        creator_email: creatorEmail,
        institution_name: institutionName,
        threshold_n: thresholdN,
        threshold_t: Math.min(thresholdT, thresholdN),
        allowed_algorithms: allowedAlgorithms.length ? allowedAlgorithms : ALGORITHMS.map((a) => a.id),
      });
      router.push(`/studies/${study_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/studies" className="text-sm text-accent hover:underline">← Back to My Studies</Link>
      <h1 className="mt-4 text-2xl font-semibold text-slate-900">Create New Study</h1>
      <p className="mt-1 text-slate-600">Cryptographically protected multi-party analysis. Follow the four steps below.</p>

      <div className="mt-6 flex gap-2">
        {STEPS.map((label, i) => (
          <button
            key={label}
            type="button"
            onClick={() => setStep(i + 1)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              step === i + 1 ? "bg-primary text-white" : "bg-slate-200 text-slate-600 hover:bg-slate-300"
            }`}
          >
            {i + 1}. {label}
          </button>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        {step === 1 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Study Setup</h2>
            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">Study Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="e.g. Phase II Trial XYZ"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="Brief description of the study"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Institution Name</label>
                <input
                  type="text"
                  value={institutionName}
                  onChange={(e) => setInstitutionName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="e.g. University Hospital A"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Your Email</label>
                <input
                  type="email"
                  value={creatorEmail}
                  onChange={(e) => setCreatorEmail(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="you@institution.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Number of participating institutions (n)</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={thresholdN}
                  onChange={(e) => {
                    const n = Math.max(1, Math.min(10, parseInt(e.target.value, 10) || 1));
                    setThresholdN(n);
                    setThresholdT((t) => Math.min(t, n));
                  }}
                  className="mt-1 w-20 rounded-lg border border-slate-300 px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">
                  How many institutions must approve decryption? (t)
                </label>
                <input
                  type="range"
                  min={1}
                  max={thresholdN}
                  value={thresholdT}
                  onChange={(e) => setThresholdT(parseInt(e.target.value, 10))}
                  className="mt-2 w-full"
                />
                <p className="mt-1 text-sm text-slate-500">t = {thresholdT}</p>
              </div>
              <ThresholdVisualizer t={thresholdT} n={thresholdN} />
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Allowed Algorithms</h2>
            <p className="mt-2 text-sm text-slate-600">
              Only these algorithms can ever be run on the data in this study. This is cryptographically enforced and recorded in the audit trail.
            </p>
            <div className="mt-4 space-y-3">
              {ALGORITHMS.map((algo) => (
                <label key={algo.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={allowedAlgorithms.includes(algo.id)}
                    onChange={() => toggleAlgorithm(algo.id)}
                    className="mt-1"
                  />
                  <div>
                    <p className="font-medium text-slate-900">{algo.label}</p>
                    <p className="text-sm text-slate-500">{algo.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Invite Participants</h2>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50/50 p-4">
              {[1, 2, 3].map((i) => (
                <span key={i} className="flex items-center gap-2">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-primary bg-white text-sm font-medium text-primary">
                    {i}
                  </span>
                  {i < 3 && <span className="text-slate-400">→</span>}
                </span>
              ))}
              <span className="ml-2 text-sm font-medium text-slate-600">Combined Public Key</span>
            </div>
            <p className="mt-3 text-sm text-slate-600">
              Each institution generates their own key share locally. The complete private key never exists anywhere—not even on our servers.
            </p>
            <p className="mt-2 text-sm font-medium text-slate-700">Participant emails (share the Study ID with them after creation)</p>
            <div className="mt-3 space-y-2">
              {participantEmails.map((email, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setParticipantEmail(i, e.target.value)}
                    placeholder="institution@example.com"
                    className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => removeParticipant(i)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={addParticipant}
                className="text-sm text-accent hover:underline"
              >
                + Add another participant
              </button>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <h2 className="text-lg font-semibold text-slate-900">Review & Create</h2>
            <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
              Once created, the allowed algorithms and participants cannot be changed. This ensures the integrity of your study protocol.
            </p>
            <dl className="mt-4 space-y-2 text-sm">
              <div><dt className="font-medium text-slate-500">Name</dt><dd className="text-slate-900">{name || "—"}</dd></div>
              <div><dt className="font-medium text-slate-500">Description</dt><dd className="text-slate-900">{description || "—"}</dd></div>
              <div><dt className="font-medium text-slate-500">Institution</dt><dd className="text-slate-900">{institutionName || "—"}</dd></div>
              <div><dt className="font-medium text-slate-500">Creator</dt><dd className="text-slate-900">{creatorEmail || "—"}</dd></div>
              <div><dt className="font-medium text-slate-500">Threshold</dt><dd className="text-slate-900">{thresholdT} of {thresholdN}</dd></div>
              <div><dt className="font-medium text-slate-500">Algorithms</dt><dd className="text-slate-900">{allowedAlgorithms.length ? allowedAlgorithms.join(", ") : "All"}</dd></div>
            </dl>
            {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
            <button
              type="button"
              onClick={handleCreate}
              disabled={submitting || !name.trim() || !creatorEmail.trim()}
              className="mt-6 rounded-lg bg-primary px-4 py-2 font-medium text-white hover:bg-primary-hover disabled:opacity-50"
            >
              {submitting ? "Creating…" : "Create Study"}
            </button>
          </>
        )}

        <div className="mt-8 flex justify-between">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
          >
            Previous
          </button>
          {step < 4 ? (
            <button
              type="button"
              onClick={() => setStep((s) => Math.min(4, s + 1))}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
            >
              Next
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
