// SPDX-License-Identifier: Apache-2.0
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEmail } from "@/lib/email-context";

type NavItem = { href: string; label: string };

export function Sidebar({
  title,
  navItems,
  extraAction,
}: {
  title: string;
  navItems: NavItem[];
  extraAction?: { href: string; label: string };
}) {
  const pathname = usePathname();
  const { email } = useEmail();

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-slate-200 bg-primary">
      <div className="flex h-14 items-center border-b border-white/10 px-4">
        <Link href="/" className="text-lg font-semibold text-white">
          {title}
        </Link>
      </div>
      <nav className="flex-1 space-y-0.5 p-2">
        {extraAction && (
          <Link
            href={extraAction.href}
            className="mb-2 flex items-center justify-center rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            {extraAction.label}
          </Link>
        )}
        {navItems.map(({ href, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={`block rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-white/15 text-white"
                  : "text-slate-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-white/10 p-3">
        <p className="truncate text-xs text-slate-400">Signed in as</p>
        <p className="truncate text-sm font-medium text-white">{email || "—"}</p>
      </div>
    </aside>
  );
}
