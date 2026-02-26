// SPDX-License-Identifier: Apache-2.0
"use client";

import { EmailModal } from "@/components/EmailModal";
import { Sidebar } from "@/components/Sidebar";

const providerNav = [
  { href: "/studies", label: "My Studies" },
  { href: "/provider", label: "Overview" },
  { href: "/provider/datasets", label: "My Datasets" },
  { href: "/provider/pending", label: "Pending Requests" },
  { href: "/provider/access", label: "Access Management" },
];

export default function ProviderLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar title="SecureCollab" navItems={providerNav} extraAction={{ href: "/studies/new", label: "Create New Study" }} />
      <main className="flex-1 overflow-auto">
        <div className="p-6 md:p-8">{children}</div>
      </main>
      <EmailModal />
    </div>
  );
}
