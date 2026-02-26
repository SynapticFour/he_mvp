// SPDX-License-Identifier: Apache-2.0
"use client";

import { EmailModal } from "@/components/EmailModal";
import { Sidebar } from "@/components/Sidebar";

const studiesNav = [
  { href: "/studies", label: "My Studies" },
  { href: "/provider", label: "Provider Dashboard" },
  { href: "/researcher", label: "Researcher Dashboard" },
];

export default function StudiesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar
        title="SecureCollab"
        navItems={studiesNav}
        extraAction={{ href: "/studies/new", label: "Create New Study" }}
      />
      <main className="flex-1 overflow-auto">
        <div className="p-6 md:p-8">{children}</div>
      </main>
      <EmailModal />
    </div>
  );
}
