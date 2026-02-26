// SPDX-License-Identifier: Apache-2.0
"use client";

import { EmailModal } from "@/components/EmailModal";
import { Sidebar } from "@/components/Sidebar";

const researcherNav = [
  { href: "/studies", label: "My Studies" },
  { href: "/researcher", label: "Overview" },
  { href: "/researcher/browse", label: "Browse Datasets" },
  { href: "/researcher/access", label: "My Access" },
  { href: "/researcher/run", label: "Run Analysis" },
];

export default function ResearcherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar title="SecureCollab" navItems={researcherNav} extraAction={{ href: "/studies/new", label: "Create New Study" }} />
      <main className="flex-1 overflow-auto">
        <div className="p-6 md:p-8">{children}</div>
      </main>
      <EmailModal />
    </div>
  );
}
